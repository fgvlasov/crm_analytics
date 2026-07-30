#!/usr/bin/env bash
# Redeploy LeadIntel stack from the current git checkout (usually branch main).
# Usage on VPS:
#   cd /opt/leadintel && ./scripts/deploy.sh
# Or via GitHub Actions SSH after merge to main.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BRANCH="${DEPLOY_BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-infra/.env}"
PROJECT="${COMPOSE_PROJECT_NAME:-leadintel}"

echo "==> Deploy root: $ROOT"
echo "==> Branch: $BRANCH"

if [[ -d .git ]]; then
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
else
  echo "WARNING: not a git checkout; skipping pull"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: missing $ENV_FILE — copy from .env.example and configure secrets first"
  exit 1
fi

# Keep root .env in sync if present (optional convenience)
if [[ -f .env.example ]] && [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> Building and restarting stack ($PROJECT)"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" -p "$PROJECT" up -d --build --remove-orphans

echo "==> Status"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" -p "$PROJECT" ps

echo "==> Health"
sleep 3
curl -fsS "http://127.0.0.1:8000/healthz" || echo "WARN: healthz not ready yet — check api logs"
echo
echo "Deploy finished."
