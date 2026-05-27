-- 001_init.sql
-- Initial schema for the eval substrate.
-- See docs/superpowers/specs/2026-05-14-evaluation-system-design.md §2 (run-storage).
--
-- No BEGIN/COMMIT — the applier (shared/db/migrations.py) owns the transaction
-- so the DDL and the schema_migrations INSERT commit atomically.

-- Reference: registry of all model manifests (loaded from shared/models/registry/*.yaml).
CREATE TABLE model_manifest (
    id              text PRIMARY KEY,
    family          text NOT NULL,
    size            text NOT NULL,
    revision        text NOT NULL,
    quantization    text,
    runtime         text NOT NULL,
    runtime_version text NOT NULL,
    target_host     text NOT NULL,
    endpoint        text NOT NULL,
    capabilities    text[] NOT NULL DEFAULT '{}',
    context_window  int  NOT NULL,
    default_sampling jsonb NOT NULL,
    raw             jsonb NOT NULL,
    loaded_at       timestamptz NOT NULL DEFAULT now()
);

-- Reference: released gold-set snapshots.
CREATE TABLE gold_set_version (
    version        text PRIMARY KEY,
    released_at    timestamptz NOT NULL DEFAULT now(),
    git_commit_sha text,
    lane_counts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    released       bool NOT NULL DEFAULT false,
    notes          text
);

-- Reference: examples in each released snapshot.
CREATE TABLE gold_example (
    version              text NOT NULL REFERENCES gold_set_version(version),
    example_id           uuid NOT NULL,
    lane                 text NOT NULL,
    source               text,
    annotator            text,
    annotated_at         date,
    prompt_template      text NOT NULL,
    inputs               jsonb NOT NULL,
    expected             jsonb NOT NULL,
    provenance_tag       text NOT NULL DEFAULT 'private',
    never_to_third_party bool NOT NULL DEFAULT true,
    tags                 text[] NOT NULL DEFAULT '{}',
    contamination_risk   text NOT NULL DEFAULT 'none',
    PRIMARY KEY (version, example_id)
);
CREATE INDEX gold_example_lane_version_idx ON gold_example (lane, version);

-- Trigger: once gold_set_version.released is true, no more inserts into gold_example for that version.
CREATE OR REPLACE FUNCTION gold_example_immutability() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM gold_set_version
        WHERE version = NEW.version AND released = true
    ) THEN
        RAISE EXCEPTION 'gold_set_version % is released; no new inserts allowed', NEW.version;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER gold_example_immutability_trigger
    BEFORE INSERT OR UPDATE ON gold_example
    FOR EACH ROW EXECUTE FUNCTION gold_example_immutability();

-- Reference: versioned judge bundles.
CREATE TABLE judge_config (
    version     text PRIMARY KEY,
    released_at timestamptz NOT NULL DEFAULT now(),
    bundle      jsonb NOT NULL,
    notes       text
);

-- Spine: one campaign per row.
CREATE TABLE run (
    id                   uuid PRIMARY KEY,
    started_at           timestamptz NOT NULL DEFAULT now(),
    finished_at          timestamptz,
    status               text NOT NULL,
    model_id             text NOT NULL,
    model_manifest       jsonb NOT NULL,
    gold_set_version     text NOT NULL REFERENCES gold_set_version(version),
    judge_config_version text NOT NULL REFERENCES judge_config(version),
    judge_config         jsonb NOT NULL,
    max_cost_usd         numeric(10,4) NOT NULL,
    cost_actual_usd      numeric(10,4),
    wall_seconds         int,
    n_examples_total     int NOT NULL,
    n_examples_scored    int NOT NULL DEFAULT 0,
    n_examples_errored   int NOT NULL DEFAULT 0,
    summary_scores       jsonb,
    experiment_id        text,
    notes                text,
    error                jsonb
);
CREATE INDEX run_status_started_at_idx ON run (status, started_at);
CREATE INDEX run_model_id_started_at_idx ON run (model_id, started_at);
CREATE INDEX run_gold_set_version_idx ON run (gold_set_version);

-- Spine: one row per example per run.
CREATE TABLE result (
    id                       uuid PRIMARY KEY,
    run_id                   uuid NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    example_id               uuid NOT NULL,
    gold_set_version         text NOT NULL,
    rendered_prompt          text NOT NULL,
    response                 text,
    response_logprobs        jsonb,
    usage                    jsonb,
    cost_increment_usd       numeric(10,6) NOT NULL DEFAULT 0,
    wall_ms                  int,
    score                    numeric(6,4),
    score_kind               text,
    error_class              text,
    error_body               jsonb,
    nondeterministic_runtime bool NOT NULL DEFAULT false,
    started_at               timestamptz NOT NULL,
    finished_at              timestamptz
);
CREATE INDEX result_run_id_idx ON result (run_id);
CREATE INDEX result_run_id_example_id_idx ON result (run_id, example_id);
CREATE INDEX result_run_id_error_idx ON result (run_id) WHERE error_class IS NOT NULL;

-- Spine: one row per (result, judge).
CREATE TABLE judgement (
    id                 uuid PRIMARY KEY,
    result_id          uuid NOT NULL REFERENCES result(id) ON DELETE CASCADE,
    judge_role         text NOT NULL,
    judge_manifest     jsonb NOT NULL,
    rubric_id          text,
    rendered_prompt    text,
    raw_response       text,
    score              numeric(6,4),
    score_kind         text NOT NULL,
    rationale          text,
    parse_error        bool NOT NULL DEFAULT false,
    usage              jsonb,
    cost_increment_usd numeric(10,6) NOT NULL DEFAULT 0,
    wall_ms            int,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX judgement_result_id_idx ON judgement (result_id);
CREATE INDEX judgement_result_id_role_idx ON judgement (result_id, judge_role);
