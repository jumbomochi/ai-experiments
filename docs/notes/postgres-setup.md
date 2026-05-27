# Postgres setup on the Mac mini

Single-user, single-machine, no remote access. Sufficient for the eval substrate
through Phase 6.

## What we're using

**PostgreSQL 17.5** from the EnterpriseDB installer at `/Library/PostgreSQL/17/`
(not brew). Already running as a launchd service from a prior install
(May 2026). Reusing it instead of running a parallel `postgresql@16` keeps
the Mac mini quieter and avoids a port conflict on 5432.

- `psql` path: `/Library/PostgreSQL/17/bin/psql`
- Data dir: `/Library/PostgreSQL/17/data`
- Listening on `localhost:5432` (Unix socket `/tmp/.s.PGSQL.5432`)

## Databases

```
ai_experiments       owner=huiliang
ai_experiments_test  owner=huiliang
```

Both were created via:

```
sudo -u postgres /Library/PostgreSQL/17/bin/createdb -O huiliang ai_experiments
sudo -u postgres /Library/PostgreSQL/17/bin/createdb -O huiliang ai_experiments_test
```

## Auth — local trust for `huiliang`

The default install uses password auth for all local connections. We prepended
one trust line to `pg_hba.conf` so the developer user can connect to either
database without supplying a password:

```
local   all   huiliang   trust   # added 2026-05-26 for the ai-experiments substrate
```

This line lives at the **top** of `/Library/PostgreSQL/17/data/pg_hba.conf`
(before the install defaults), so it wins. A timestamped backup of the
pre-edit file sits beside it as `pg_hba.conf.bak.<epoch>`. The `postgres`
superuser still requires its install-time password — only the `huiliang`
local role is trust-auth.

The one-shot bootstrap that did all of this is at
`scripts/setup_pg17_trust.sh` in the repo (mirrored from `/tmp/`); idempotent,
re-runnable.

## Connection strings (stored in `.env`, gitignored)

```
DATABASE_URL=postgresql://huiliang@/ai_experiments?host=/tmp
DATABASE_URL_TEST=postgresql://huiliang@/ai_experiments_test?host=/tmp
```

The `?host=/tmp` query parameter makes `psycopg` connect via the Unix socket
at `/tmp/.s.PGSQL.5432` rather than TCP loopback. This matters because the
trust line we added covers `local` (Unix socket) only; TCP (`host` lines)
would still require the postgres password. Socket connections are also
slightly faster.

The `shared/db/connection.py` module reads these via `python-dotenv`.

## Sanity check

```
/Library/PostgreSQL/17/bin/psql -U huiliang -d ai_experiments -c \
  "SELECT current_user, current_database(), substring(version() for 60)"
```

Expected: row with `huiliang | ai_experiments | PostgreSQL 17.5 …` and no
password prompt. (`psql` defaults to Unix socket on macOS so this works
out of the box; only TCP-over-loopback would require a password.)

## pgvector — DEFERRED to Phase 5

pgvector is **not installed** for PG17 (the install only ships `cube` /
plpgsql / a few standard extensions). The repo-design and spec call for
pgvector but only the **memory adapter** in Phase 5 actually uses vector
columns. Sprint 1's `001_init.sql` and tests don't reference vectors.

When Phase 5 starts:

1. `git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git`
2. `cd pgvector && make USE_PGXS=1 PG_CONFIG=/Library/PostgreSQL/17/bin/pg_config`
3. `sudo make USE_PGXS=1 PG_CONFIG=/Library/PostgreSQL/17/bin/pg_config install`
4. `psql -U huiliang -d ai_experiments -c 'CREATE EXTENSION vector;'`

(Brew's `pgvector` formula links against brew Postgres only, so it doesn't
help here.)

## Notes

- No replication, no remote auth, no backups. Time Machine on the Mac mini
  is the disaster-recovery story for v0.1.
- If PG17 is ever uninstalled, the eval substrate will lose its data; the
  schema is reproducible from `migrations/`, the run records are not.
- If at any point we need an isolated cluster (e.g., to test schema
  migrations against a clean PG without touching live data), `brew install
  postgresql@16` + reconfigure to port 5433 is the documented path.
