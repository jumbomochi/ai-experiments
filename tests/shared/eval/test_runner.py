"""Tests for the campaign runner — happy path, budget halt, privacy guardrail."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from shared.db.connection import connect
from shared.db.migrations import apply_all
from shared.eval.judges import register_bundle
from shared.eval.runner import run_campaign
from shared.goldsets.loader import load_jsonl_to_postgres
from shared.models.manifest import load_manifest_yaml
from shared.models.registry import sync_to_postgres


def _reset_test_db() -> None:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    apply_all(test=True)


def _bootstrap_fixtures(tmp_path: Path) -> None:
    """Set up: judge_config v0.1, qwen0.5b manifest, smoke seed."""
    _reset_test_db()
    register_bundle("v0.1", test=True)

    manifest_yaml = tmp_path / "m.yaml"
    manifest_yaml.write_text(
        'id: "qwen2.5:0.5b-instruct"\n'
        'family: qwen2.5\nsize: 0.5b\nrevision: "2024-09-19"\n'
        'runtime: ollama\nruntime_version: "0.15.1"\n'
        'target_host: mac\nendpoint: "http://localhost:11434/v1"\n'
        'capabilities: [chat]\ncontext_window: 32768\n'
        'default_sampling: {temperature: 0.0, top_p: 1.0, max_tokens: 8}\n'
    )
    sync_to_postgres([load_manifest_yaml(manifest_yaml)], test=True)

    seed = tmp_path / "seed.jsonl"
    with seed.open("w") as f:
        f.write(json.dumps({
            "example_id": "ex_general_seed0001", "lane": "general",
            "source": "x", "annotator": "j", "annotated_at": "2026-05-26",
            "prompt_template": "general/multi-choice.j2",
            "inputs": {"question": "2+2?", "choices": {"A": "3", "B": "4", "C": "5", "D": "22"}},
            "expected": {"type": "exact", "value": "B"},
            "provenance_tag": "public", "never_to_third_party": False,
            "tags": [], "contamination_risk": "none",
        }) + "\n")
    load_jsonl_to_postgres(seed, version="smoke-v0.0", git_commit_sha="t", test=True)


def _stub_inference_response(content: str):
    """Build a canned ChatResponse for InferenceClient.chat to return."""
    from shared.inference.client import ChatResponse, Usage
    return ChatResponse(
        content=content,
        usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
        raw={"choices": [{"message": {"content": content}}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}},
    )


def test_happy_path_completes(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text(
        "Q: {{ question }}\nA. {{ choices.A }}\nB. {{ choices.B }}\nC. {{ choices.C }}\nD. {{ choices.D }}\nAnswer:"
    )

    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=1.00,
            template_root=template_root,
            test=True,
        )

    assert rr.status == "completed"
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT score, score_kind FROM result WHERE run_id = %s", (rr.run_id,))
        rows = cur.fetchall()
    assert rows == [(1.0, "binary")]

    # And the run row itself is finalized:
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, cost_actual_usd, n_examples_scored, n_examples_errored, "
            "       summary_scores "
            "FROM run WHERE id = %s",
            (rr.run_id,),
        )
        run_row = cur.fetchone()
    assert run_row[0] == "completed"
    assert float(run_row[1]) >= 0.0
    assert run_row[2] == 1
    assert run_row[3] == 0
    assert run_row[4] == {"avg_score": 1.0}


def test_budget_halt(tmp_path: Path) -> None:
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("Q: {{ question }} A.")

    # max_cost_usd=-1e-9 → cost_accumulated (0.0) > -1e-9 is True after the first
    # example, tripping the budget halt. The mac rate card has prompt_usd_per_mtok=0.0
    # and completion_usd_per_mtok=0.0, so token cost is $0; wall_ms from a mock call
    # rounds to 0ms, making cost_inc also $0. Using a sub-zero threshold ensures
    # cost_accumulated > max_cost_usd evaluates True on the first example regardless
    # of timing granularity in CI.
    with patch("shared.inference.client.InferenceClient.chat",
               return_value=_stub_inference_response("B")):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=-1e-9,
            template_root=template_root,
            test=True,
        )

    assert rr.status == "halted_budget"


def test_catastrophic_error_halts_with_status(tmp_path: Path) -> None:
    """A catastrophic inference error halts the run and writes the partial result."""
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("Q: {{ question }} A.")

    from shared.inference.errors import ErrorClass, InferenceError

    catastrophic = InferenceError(
        "OOM", ErrorClass.CATASTROPHIC, status=500,
        body={"error": {"message": "CUDA out of memory"}},
    )

    with patch("shared.inference.client.InferenceClient.chat", side_effect=catastrophic):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=1.00,
            template_root=template_root,
            test=True,
        )

    assert rr.status == "halted_endpoint_error"


def test_rate_limit_exhausted_labelled_retryable_exhausted(tmp_path: Path) -> None:
    """Exhausted RATE_LIMIT retries get labelled retryable_exhausted on the result row,
    NOT catastrophic. The campaign continues (rate_limit is not a halt trigger)."""
    _bootstrap_fixtures(tmp_path)
    template_root = tmp_path / "tpl"
    (template_root / "general").mkdir(parents=True)
    (template_root / "general" / "multi-choice.j2").write_text("Q: {{ question }} A.")

    from shared.inference.errors import ErrorClass, InferenceError

    rate_limit_exhausted = InferenceError(
        "rate-limited", ErrorClass.RATE_LIMIT, status=429,
        body={"error": {"message": "too many"}},
    )

    with patch("shared.inference.client.InferenceClient.chat", side_effect=rate_limit_exhausted):
        rr = run_campaign(
            model_id="qwen2.5:0.5b-instruct",
            gold_set_version="smoke-v0.0",
            judge_config_version="v0.1",
            max_cost_usd=1.00,
            template_root=template_root,
            test=True,
        )

    # Run completes (1 example, all errored), no halt
    assert rr.status == "completed"
    with connect(test=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT error_class FROM result WHERE run_id = %s", (rr.run_id,))
        rows = cur.fetchall()
    assert rows == [("retryable_exhausted",)]
