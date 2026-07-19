# 03 — Monorepo Structure

## Required repository structure

```text
leadintel/
├── .cursorrules/
│   └── *.md
├── apps/
│   ├── api/
│   │   ├── app/
│   │   ├── alembic/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── workers/
│   │   ├── app/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── dashboard/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── package.json
│   └── collectors/
│       ├── app/
│       ├── adapters/
│       │   ├── smart_rpt/
│       │   ├── generic_news/
│       │   └── generic_directory/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
├── odoo_addons/
│   └── leadintel_connector/
│       ├── __manifest__.py
│       ├── __init__.py
│       ├── models/
│       ├── controllers/
│       ├── security/
│       ├── views/
│       ├── data/
│       ├── tests/
│       └── README.md
├── packages/
│   ├── shared-schemas/
│   └── openapi/
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.local.yml
│   ├── nginx/
│   ├── minio/
│   └── postgres/
├── scripts/
│   ├── dev.sh
│   ├── test.sh
│   ├── lint.sh
│   └── db-reset.sh
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   └── security.md
├── .env.example
├── Makefile
└── README.md
```

## Backend app structure

```text
apps/api/app/
├── main.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── logging.py
│   ├── errors.py
│   └── tenancy.py
├── db/
│   ├── base.py
│   ├── session.py
│   └── models/
├── schemas/
├── api/
│   ├── deps.py
│   └── v1/
│       ├── auth.py
│       ├── tenants.py
│       ├── odoo.py
│       ├── leads.py
│       ├── candidates.py
│       ├── providers.py
│       ├── sources.py
│       ├── jobs.py
│       └── billing.py
├── services/
│   ├── auth_service.py
│   ├── tenant_service.py
│   ├── odoo_service.py
│   ├── lead_service.py
│   ├── ai_provider_service.py
│   ├── assessment_service.py
│   ├── candidate_service.py
│   └── secret_service.py
└── integrations/
    ├── odoo_client.py
    ├── openai_client.py
    └── webhooks.py
```

## Worker app structure

```text
apps/workers/app/
├── worker.py
├── tasks/
│   ├── ai_assessment_tasks.py
│   ├── odoo_sync_tasks.py
│   ├── crawler_tasks.py
│   ├── tender_tasks.py
│   └── webhook_tasks.py
├── services/
│   ├── ai_fast_assessment.py
│   ├── ai_deep_research.py
│   ├── source_extraction.py
│   └── deduplication.py
└── utils/
```

## Dashboard structure

```text
apps/dashboard/
├── app/
│   ├── login/
│   ├── dashboard/
│   ├── leads/
│   ├── candidates/
│   ├── sources/
│   ├── integrations/
│   ├── billing/
│   └── settings/
├── components/
│   ├── layout/
│   ├── leads/
│   ├── candidates/
│   ├── integrations/
│   ├── sources/
│   └── ui/
├── lib/
│   ├── api-client.ts
│   ├── auth.ts
│   ├── types.ts
│   └── utils.ts
└── tests/
```

## Odoo addon structure

```text
odoo_addons/leadintel_connector/
├── __manifest__.py
├── __init__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py
│   ├── crm_lead.py
│   ├── leadintel_assessment.py
│   ├── leadintel_instance.py
│   ├── leadintel_sync_log.py
│   └── leadintel_webhook_log.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── services/
│   ├── __init__.py
│   ├── api_client.py
│   ├── payload_builder.py
│   └── signature.py
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── views/
│   ├── crm_lead_views.xml
│   ├── res_config_settings_views.xml
│   ├── leadintel_assessment_views.xml
│   └── menus.xml
├── data/
│   ├── ir_cron.xml
│   └── server_actions.xml
└── tests/
```

## Coding standards

### Python

- Use type hints everywhere.
- Use pydantic schemas for API validation.
- Use SQLAlchemy 2 style.
- Use explicit transactions.
- Never silently swallow exceptions.
- Never log secrets.
- Keep service-layer business logic separate from route handlers.

### TypeScript

- Use strict TypeScript.
- Use generated API types where possible.
- Avoid `any` unless justified.
- Components should be small and testable.
- All network calls go through `lib/api-client.ts`.

### Odoo

- Follow Odoo addon conventions.
- No direct SQL unless necessary and reviewed.
- Never block user HTTP request with long SaaS calls.
- Use cron/queue for sync and retries.
- Store tokens in `ir.config_parameter` with restricted group access.
- Keep UI simple and non-invasive.

## Development commands

Provide these commands:

```bash
make dev
make test
make lint
make format
make migrate
make worker
make dashboard
make odoo-package
```

## Required generated docs

The repository must maintain:

```text
docs/api.md
docs/odoo_install.md
docs/security.md
docs/source_adapters.md
docs/billing.md
docs/tenant_isolation.md
```
