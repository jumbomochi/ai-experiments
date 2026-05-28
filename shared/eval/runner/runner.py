"""Campaign runner: preflight → per-example dispatch → judges → finalize.

One linear pass through the gold-set examples. Per spec §1 + §5.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.db.connection import connect
from shared.eval.cost.accountant import CostAccountant, load_rate_card
from shared.eval.judges import (
    DeterministicConfig,
    Judgement,
    aggregate,
    deterministic_score,
)
from shared.eval.runner.preflight import PreflightFailure, preflight_or_raise
from shared.eval.runner.teardown import LocalTeardownHook, TeardownHook
from shared.goldsets.render import render_prompt
from shared.goldsets.schema import Expected
from shared.inference.client import ChatRequest, InferenceClient, Message
from shared.inference.errors import ErrorClass, InferenceError
from shared.models.manifest import ModelManifest
from shared.models.registry import resolve


@dataclass(frozen=True)
class RunResult:
    run_id: uuid.UUID
    status: str
    cost_actual_usd: float
    n_examples_scored: int
    n_examples_errored: int


def run_campaign(
    model_id: str,
    gold_set_version: str,
    judge_config_version: str,
    max_cost_usd: float,
    template_root: Path,
    experiment_id: str | None = None,
    test: bool = False,
    teardown_hook: TeardownHook | None = None,
    inference_client_factory=None,  # for test injection
) -> RunResult:
    teardown_hook = teardown_hook or LocalTeardownHook()
    run_id = uuid.uuid4()
    started_at = time.time()

    # --- Preflight (steps 1–5; step 6 = write `run` row, just below) ---
    try:
        manifest = preflight_or_raise(
            check_postgres=lambda: _check_postgres(test=test),
            check_manifest=lambda: resolve(model_id, test=test),
            check_trust_gate=lambda: _check_trust_gate(judge_config_version, gold_set_version, test=test),
            check_rate_card=lambda host: load_rate_card(host),
            check_endpoint_ready=lambda url, t: None,   # Ollama exposes /v1 immediately; skip in v0.1
        )
    except PreflightFailure as f:
        # postgres step failed → we can't write a run row; bubble up
        if f.step == "postgres":
            raise
        # otherwise write a halted_setup row and return
        _write_run_row(
            run_id=run_id, model_id=model_id, model_manifest={},
            gold_set_version=gold_set_version,
            judge_config_version=judge_config_version, judge_config={},
            max_cost_usd=max_cost_usd, n_examples_total=0,
            status="halted_setup",
            error={"step": f.step, "cause": str(f.cause)},
            experiment_id=experiment_id, test=test,
        )
        teardown_hook.teardown(f"halted_setup at {f.step}")
        return RunResult(run_id=run_id, status="halted_setup",
                         cost_actual_usd=0.0, n_examples_scored=0, n_examples_errored=0)

    # --- Load fixtures ---
    examples = _fetch_examples(gold_set_version, test=test)
    bundle = _fetch_bundle(judge_config_version, test=test)
    cost_accountant = CostAccountant.for_target(manifest.target_host)

    # --- Privacy guardrail (spec §5) ---
    # Mac is sovereign Tier 1 → no examples can violate. Check exists for future-proofing.
    try:
        _enforce_privacy_guardrail(manifest, examples)
    except PreflightFailure as f:
        _write_run_row(
            run_id=run_id, model_id=model_id, model_manifest=manifest.model_dump(),
            gold_set_version=gold_set_version,
            judge_config_version=judge_config_version, judge_config=bundle,
            max_cost_usd=max_cost_usd, n_examples_total=len(examples),
            status="halted_setup",
            error={"step": f.step, "cause": str(f.cause)},
            experiment_id=experiment_id, test=test,
        )
        teardown_hook.teardown(f"halted_setup at {f.step}")
        return RunResult(run_id=run_id, status="halted_setup",
                         cost_actual_usd=0.0, n_examples_scored=0, n_examples_errored=0)

    # --- Write initial run row (step 6) ---
    _write_run_row(
        run_id=run_id, model_id=model_id,
        model_manifest=manifest.model_dump(),
        gold_set_version=gold_set_version,
        judge_config_version=judge_config_version,
        judge_config=bundle,
        max_cost_usd=max_cost_usd,
        n_examples_total=len(examples),
        status="running",
        experiment_id=experiment_id,
        test=test,
    )

    # --- Build client ---
    client = (inference_client_factory or _default_client_factory)(manifest)

    # --- Linear loop ---
    cost_accumulated = 0.0
    n_scored = 0
    n_errored = 0
    status = "completed"
    halt_error: dict | None = None

    for ex in examples:
        # Render
        rendered = render_prompt(template_root, ex["prompt_template"], ex["inputs"])

        # Inference
        call_started = time.time()
        result_id = uuid.uuid4()
        try:
            req = ChatRequest(
                messages=[Message(role="user", content=rendered)],
                temperature=manifest.default_sampling.temperature,
                top_p=manifest.default_sampling.top_p,
                max_tokens=manifest.default_sampling.max_tokens,
            )
            resp = client.chat(req)
            response_text = resp.content
            prompt_tokens = resp.usage.prompt_tokens
            completion_tokens = resp.usage.completion_tokens
            error_class = None
            error_body = None
        except InferenceError as e:
            response_text = None
            prompt_tokens = None
            completion_tokens = None
            if e.error_class is ErrorClass.CATASTROPHIC:
                status = "halted_endpoint_error"
                halt_error = {"cause": str(e), "error_class": e.error_class.value}
            error_class = "client_fatal" if e.error_class is ErrorClass.CLIENT_FATAL else (
                "retryable_exhausted" if e.error_class is ErrorClass.RETRYABLE else "catastrophic"
            )
            error_body = {"message": str(e), "body": e.body}
        wall_ms = int((time.time() - call_started) * 1000)

        # Cost
        cost_inc = cost_accountant.cost_per_call(prompt_tokens, completion_tokens, wall_ms)
        cost_accumulated += cost_inc

        # Score (deterministic only in v0.1)
        agg_score: float | None = None
        agg_kind: str | None = None
        judgement_row: Judgement | None = None
        if response_text is not None:
            expected = Expected(**ex["expected"])
            cfg = DeterministicConfig(**bundle["judges"]["deterministic"]["config"])
            try:
                if expected.type in {"exact", "set"}:
                    raw_score = deterministic_score(response_text, expected, cfg)
                    judgement_row = Judgement(
                        judge_role="deterministic",
                        score=raw_score,
                        score_kind="binary" if expected.type == "exact" else "scalar",
                    )
                    agg_score, agg_kind = aggregate(
                        [judgement_row], bundle["aggregation"]["weights"]
                    )
                else:
                    # No specialist in v0.1 → mark as parse-failed-style error on the result
                    error_class = "judge_parse_failed"
                    error_body = {"reason": "rubric routing not implemented in Sprint 1"}
            except Exception as e:
                error_class = "judge_parse_failed"
                error_body = {"reason": str(e)}

        # Persist `result`
        _write_result_row(
            id=result_id, run_id=run_id, example=ex,
            gold_set_version=gold_set_version,
            rendered=rendered, response=response_text,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cost_inc=cost_inc, wall_ms=wall_ms,
            score=agg_score, score_kind=agg_kind,
            error_class=error_class, error_body=error_body,
            nondeterministic_runtime="seed" not in manifest.capabilities,
            test=test,
        )

        # Persist `judgement`
        if judgement_row is not None:
            _write_judgement_row(
                result_id=result_id, judgement=judgement_row, bundle=bundle, test=test,
            )

        if error_class is None:
            n_scored += 1
        else:
            n_errored += 1

        if status == "halted_endpoint_error":
            break

        # Budget check
        if cost_accumulated > max_cost_usd:
            status = "halted_budget"
            halt_error = {"cause": "max_cost_usd exceeded",
                          "cost_accumulated": cost_accumulated, "max": max_cost_usd}
            break

    # --- Teardown + finalize ---
    teardown_receipt = teardown_hook.teardown(f"run_finalize_{status}")
    finished_at = time.time()
    _finalize_run_row(
        run_id=run_id, status=status, finished_at=finished_at,
        wall_seconds=int(finished_at - started_at),
        cost_actual_usd=cost_accumulated,
        n_examples_scored=n_scored, n_examples_errored=n_errored,
        summary_scores=_compute_summary(run_id, test=test),
        error=halt_error,
        notes=f"teardown_receipt={json.dumps(teardown_receipt)}",
        test=test,
    )

    return RunResult(
        run_id=run_id, status=status,
        cost_actual_usd=cost_accumulated,
        n_examples_scored=n_scored, n_examples_errored=n_errored,
    )


# ----- helpers -----

def _check_postgres(test: bool) -> None:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        if cur.fetchone() != (1,):
            raise RuntimeError("postgres healthcheck returned non-1")


def _check_trust_gate(judge_config_version: str, gold_set_version: str, test: bool) -> None:
    """Stub for v0.1: deterministic-only routing is always trusted."""
    bundle = _fetch_bundle(judge_config_version, test=test)
    if bundle["trust"]["enforcement"] == "lenient":
        return
    # Strict mode would enforce per-task kappas here; Sprint 1 bundle is lenient.
    raise NotImplementedError("strict trust gate arrives in Sprint 3 plan")


def _enforce_privacy_guardrail(manifest: ModelManifest, examples: list[dict]) -> None:
    tier1_hosts = {"mac", "spark", "cloud-burst-a3", "cloud-burst-p5"}
    if manifest.target_host in tier1_hosts:
        return
    for ex in examples:
        if ex.get("never_to_third_party"):
            raise PreflightFailure(
                "privacy_violation",
                RuntimeError(f"example {ex['example_id']} cannot reach non-Tier-1 host "
                             f"{manifest.target_host}"),
            )


def _fetch_examples(gold_set_version: str, test: bool) -> list[dict[str, Any]]:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT example_id::text, lane, prompt_template, inputs, expected, "
            "       never_to_third_party "
            "FROM gold_example WHERE version = %s ORDER BY example_id",
            (gold_set_version,),
        )
        rows = cur.fetchall()
    return [
        {"example_id": r[0], "lane": r[1], "prompt_template": r[2],
         "inputs": r[3], "expected": r[4], "never_to_third_party": r[5]}
        for r in rows
    ]


def _fetch_bundle(version: str, test: bool) -> dict:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute("SELECT bundle FROM judge_config WHERE version = %s", (version,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"no judge_config with version={version!r}")
    return row[0]


def _default_client_factory(manifest: ModelManifest) -> InferenceClient:
    return InferenceClient(endpoint=manifest.endpoint, model=manifest.id, timeout_s=60.0)


def _write_run_row(
    *, run_id, model_id, model_manifest, gold_set_version, judge_config_version,
    judge_config, max_cost_usd, n_examples_total, status,
    error=None, experiment_id=None, test=False,
):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO run (
                id, model_id, model_manifest, gold_set_version,
                judge_config_version, judge_config,
                max_cost_usd, n_examples_total, status, error, experiment_id
            ) VALUES (
                %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s
            )
            """,
            (run_id, model_id, json.dumps(model_manifest), gold_set_version,
             judge_config_version, json.dumps(judge_config),
             max_cost_usd, n_examples_total, status,
             json.dumps(error) if error is not None else None, experiment_id),
        )


def _write_result_row(
    *, id, run_id, example, gold_set_version, rendered, response,
    prompt_tokens, completion_tokens,
    cost_inc, wall_ms, score, score_kind, error_class, error_body,
    nondeterministic_runtime, test=False,
):
    usage = (
        {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        if prompt_tokens is not None else None
    )
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO result (
                id, run_id, example_id, gold_set_version, rendered_prompt,
                response, usage, cost_increment_usd, wall_ms,
                score, score_kind, error_class, error_body,
                nondeterministic_runtime, started_at, finished_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s, %s,
                %s, %s, %s, %s::jsonb,
                %s, now(), now()
            )
            """,
            (
                id, run_id, example["example_id"], gold_set_version, rendered,
                response, json.dumps(usage) if usage else None, cost_inc, wall_ms,
                score, score_kind, error_class,
                json.dumps(error_body) if error_body else None,
                nondeterministic_runtime,
            ),
        )


def _write_judgement_row(*, result_id, judgement: Judgement, bundle, test=False):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO judgement (
                id, result_id, judge_role, judge_manifest,
                score, score_kind, parse_error
            ) VALUES (
                %s, %s, %s, %s::jsonb, %s, %s, %s
            )
            """,
            (
                uuid.uuid4(), result_id, judgement.judge_role,
                json.dumps(bundle["judges"].get(judgement.judge_role, {})),
                judgement.score, judgement.score_kind, judgement.parse_error,
            ),
        )


def _compute_summary(run_id, test=False) -> dict:
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT avg(score) FROM result "
            "WHERE run_id = %s AND score IS NOT NULL",
            (run_id,),
        )
        avg = cur.fetchone()[0]
    return {"avg_score": float(avg) if avg is not None else None}


def _finalize_run_row(
    *, run_id, status, finished_at, wall_seconds, cost_actual_usd,
    n_examples_scored, n_examples_errored, summary_scores, error, notes, test=False,
):
    with connect(test=test) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE run SET
                finished_at = to_timestamp(%s),
                wall_seconds = %s,
                cost_actual_usd = %s,
                n_examples_scored = %s,
                n_examples_errored = %s,
                summary_scores = %s::jsonb,
                status = %s,
                error = %s::jsonb,
                notes = %s
            WHERE id = %s
            """,
            (
                finished_at, wall_seconds, cost_actual_usd,
                n_examples_scored, n_examples_errored,
                json.dumps(summary_scores), status,
                json.dumps(error) if error is not None else None,
                notes, run_id,
            ),
        )
