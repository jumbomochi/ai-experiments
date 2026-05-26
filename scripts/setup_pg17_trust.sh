#!/usr/bin/env bash
# Idempotent bootstrap for the ai-experiments eval substrate against PG17.
# Run with: sudo /tmp/setup_pg17_trust.sh
set -eu

PG=/Library/PostgreSQL/17/bin
DATA=/Library/PostgreSQL/17/data
HBA=$DATA/pg_hba.conf
USER_TO_TRUST=huiliang

echo "==> 1. Create role $USER_TO_TRUST if missing"
sudo -u postgres "$PG/psql" -d postgres -v ON_ERROR_STOP=1 -c "
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$USER_TO_TRUST') THEN
    CREATE ROLE $USER_TO_TRUST WITH LOGIN CREATEDB;
    RAISE NOTICE 'role $USER_TO_TRUST created';
  ELSE
    RAISE NOTICE 'role $USER_TO_TRUST already exists';
  END IF;
END \$\$;
"

echo "==> 2. Create databases ai_experiments and ai_experiments_test (idempotent)"
sudo -u postgres "$PG/createdb" -O "$USER_TO_TRUST" ai_experiments 2>/dev/null \
    && echo "   ai_experiments created" \
    || echo "   ai_experiments already exists"
sudo -u postgres "$PG/createdb" -O "$USER_TO_TRUST" ai_experiments_test 2>/dev/null \
    && echo "   ai_experiments_test created" \
    || echo "   ai_experiments_test already exists"

echo "==> 3. Prepend trust line to pg_hba.conf if not present"
if ! grep -qE "^local[[:space:]]+all[[:space:]]+$USER_TO_TRUST[[:space:]]+trust" "$HBA"; then
    cp "$HBA" "$HBA.bak.$(date +%s)"
    {
        echo "local   all   $USER_TO_TRUST   trust"
        cat "$HBA.bak."*
    } | tail -n +1 > "$HBA.new"
    # Simpler: write our line + original contents
    ( echo "local   all   $USER_TO_TRUST   trust"; cat "$HBA" ) > "$HBA.new"
    mv "$HBA.new" "$HBA"
    chown postgres:postgres "$HBA"
    chmod 600 "$HBA"
    echo "   pg_hba.conf updated (backup saved)"
else
    echo "   trust line already present in pg_hba.conf"
fi

echo "==> 4. Reload Postgres config"
sudo -u postgres "$PG/pg_ctl" -D "$DATA" reload

echo "==> 5. Verify connection as $USER_TO_TRUST (should NOT prompt for password)"
"$PG/psql" -U "$USER_TO_TRUST" -d ai_experiments -c "SELECT current_user, current_database(), substring(version() for 60)" || {
    echo "FAILED — connection still asks for password; check pg_hba.conf"
    exit 1
}

echo
echo "✓ Bootstrap complete. ai_experiments + ai_experiments_test ready; trust auth enabled for $USER_TO_TRUST."
