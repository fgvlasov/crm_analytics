#!/usr/bin/env bash
set -euo pipefail
cp -n .env.example .env || true
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
