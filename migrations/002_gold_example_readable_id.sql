-- migrations/002_gold_example_readable_id.sql
-- Dev DB only: truncate all data in FK order, then convert uuid PKs to text.
-- No BEGIN/COMMIT — the applier (shared/db/migrations.py) owns the transaction.

TRUNCATE TABLE judgement, result, run, gold_example, gold_set_version CASCADE;

ALTER TABLE gold_example ALTER COLUMN example_id TYPE text;
ALTER TABLE result ALTER COLUMN example_id TYPE text;
