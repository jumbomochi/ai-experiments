# Migrations

Plain SQL files, sequentially numbered (`001_init.sql`, `002_*.sql`, ...).

## Apply

    uv run python -m shared.db.migrations apply         # production
    uv run python -m shared.db.migrations apply --test  # test database

Applied IDs are recorded in the `schema_migrations` table; re-applying is a no-op.

## Why this and not Alembic / sqitch

YAGNI for a single-developer, single-machine setup. Revisit when the project
needs multi-developer migrations, rollback support, or branch-aware ordering.

## Add a migration

1. Create `migrations/NNN_<slug>.sql` (NNN = next zero-padded integer).
2. Record the rationale in `docs/notes/instrumentation.md` per the ROADMAP
   instrumentation track.
3. Apply: `uv run python -m shared.db.migrations apply`.
