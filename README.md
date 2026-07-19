# LeadIntel — AI Lead Intelligence SaaS

Multi-tenant B2B lead intelligence platform: Odoo integration, AI scoring, tender and web collectors, client dashboard.

This repository is in **Phase 1**: monorepo, backend foundation, tenants, auth, secrets, feature flags.

Requirements pack: [`.cursorrules/`](.cursorrules/) — start with [`00_README.md`](.cursorrules/00_README.md) and [`18_PHASED_DEVELOPMENT_PLAN.md`](.cursorrules/18_PHASED_DEVELOPMENT_PLAN.md).

## Stack

- API: Python 3.12, FastAPI, SQLAlchemy 2, Alembic
- DB: PostgreSQL 16
- Queue: Redis (workers stub in Phase 1)
- Object storage: MinIO
- Dashboard: placeholder (Next.js later)
- Odoo 19 addon: Phase 2

## Quick start (Phase 1)

```bash
cp .env.example .env
cp .env infra/.env
make up
# wait for API healthy, then:
curl -s http://localhost:8000/healthz
```

Docker Desktop looks for `infra/.env` (project directory). Keep root `.env` and `infra/.env` in sync (`make sync-env` / `make up` does this on Windows Make).

Stop without removing volumes:

```bash
make stop
# or:
docker compose -f infra/docker-compose.yml --env-file infra/.env -p leadintel stop
```

Demo login (from `.env.example` defaults):

- Email: `admin@coldex-demo.example`
- Password: `ChangeMeDemo123!`

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@coldex-demo.example","password":"ChangeMeDemo123!","tenant_slug":"coldex-demo"}'
```

## Feature flags

Phase 1 has no flag. Phase 2 Odoo connector is enabled in `.env.example` for local/dev:

```env
FEATURE_ODOO_CONNECTOR=true
FEATURE_FAST_AI=false
FEATURE_DEEP_RESEARCH=false
FEATURE_SMART_RPT=false
FEATURE_WEB_NEWS_COLLECTORS=false
```

Inspect active flags: `GET /api/v1/features`

## Local tests (API)

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Tests use SQLite in-memory by default (`APP_ENV=test`).

## Useful commands

| Command | Purpose |
| --- | --- |
| `make up` | Build and start Compose stack |
| `make stop` | Stop containers (keep volumes) |
| `make down` | Stop and remove containers |
| `make test` | Run API tests |
| `make health` | Hit `/healthz` |
| `make logs` | Follow Compose logs |

## Phase roadmap

See [`.cursorrules/18_PHASED_DEVELOPMENT_PLAN.md`](.cursorrules/18_PHASED_DEVELOPMENT_PLAN.md).
