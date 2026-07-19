#!/usr/bin/env bash
set -euo pipefail
docker compose -f infra/docker-compose.yml exec postgres \
  psql -U leadintel -d leadintel -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
docker compose -f infra/docker-compose.yml exec api python -m app.scripts.seed
