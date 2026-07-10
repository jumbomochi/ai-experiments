#!/bin/bash
# GCE startup script — rendered by Terraform templatefile().
set -euo pipefail

ARGILLA_USERNAME="${argilla_username}"
ARGILLA_PASSWORD="${argilla_password}"

echo "[startup] Installing Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

echo "[startup] Writing docker-compose.yml..."
mkdir -p /opt/argilla
cat > /opt/argilla/docker-compose.yml << 'EOF'
version: "3.9"
services:
  argilla:
    image: argilla/argilla-server:latest
    restart: unless-stopped
    ports:
      - "6900:6900"
    environment:
      ARGILLA_HOME_PATH: /var/lib/argilla
      ARGILLA_DATABASE_URL: postgresql://argilla:argilla_db_pass@postgres:5432/argilla
      OWNER_USERNAME: ${argilla_username}
      OWNER_PASSWORD: ${argilla_password}
      OWNER_API_KEY: ${argilla_username}.apikey
    depends_on:
      - postgres
    volumes:
      - argilla_data:/var/lib/argilla

  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_USER: argilla
      POSTGRES_PASSWORD: argilla_db_pass
      POSTGRES_DB: argilla
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  argilla_data:
  postgres_data:
EOF

echo "[startup] Starting argilla..."
cd /opt/argilla
docker compose up -d

echo "[startup] Waiting for argilla to become ready..."
MAX_WAIT=120
WAITED=0
until curl -sf http://localhost:6900/api/v1/status >/dev/null 2>&1; do
  sleep 5
  WAITED=$((WAITED + 5))
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[startup] ERROR: argilla did not start after ${MAX_WAIT}s"
    docker compose logs 2>&1 | tail -30
    exit 1
  fi
done
echo "[startup] argilla ready at http://localhost:6900"
