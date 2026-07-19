# 14 — DevOps and Deployment Requirements

## Deployment phases

### Phase 1 — Local Docker Compose

Everything runs locally:

```text
PostgreSQL
Redis
MinIO
API
Workers
Collectors
Dashboard
```

### Phase 2 — Single VPS / Docker Compose production

Good for first pilots.

### Phase 3 — Kubernetes / managed services

For scaling later.

## Local docker-compose services

```yaml
services:
  postgres:
  redis:
  minio:
  api:
  workers:
  collectors:
  dashboard:
  nginx:
```

## Required environment files

```text
.env.example
.env.local.example
apps/api/.env.example
apps/dashboard/.env.example
apps/collectors/.env.example
```

No real secrets committed.

## Database migrations

Use Alembic.

Rules:

- every model change has migration;
- migrations are reviewed;
- production migrations are backward-compatible where possible;
- no destructive migrations without backup.

## Backups

Back up:

- PostgreSQL;
- object storage;
- configuration/secrets metadata.

Secrets master key must be backed up separately and securely.

## CI checks

Required checks:

```text
Python lint
Python type check
Python tests
TypeScript lint
TypeScript type check
Dashboard tests
Odoo addon static validation
XML validation
Docker build
Secret scan
```

## Logging

Use structured JSON logs.

Fields:

```text
timestamp
level
service
request_id
tenant_id nullable
job_id nullable
message
error_code nullable
```

Never log:

- passwords;
- API keys;
- tokens;
- cookies;
- raw portal credentials;
- full AI prompt in production unless debug mode explicitly enabled.

## Health endpoints

API:

```text
GET /healthz
GET /readyz
```

Checks:

- DB connectivity;
- Redis connectivity;
- object storage connectivity optional;
- migrations current.

## Worker health

Workers should emit heartbeat.

Dashboard/admin should show:

- last heartbeat;
- queues length;
- failed jobs;
- running jobs too long.

## Domain strategy

Example:

```text
app.leadintel.example      dashboard
api.leadintel.example      API
```

Or single domain:

```text
leadintel.example          dashboard
leadintel.example/api      API
```

For MVP, use one domain with reverse proxy.

## TLS

Production requires HTTPS.

Use:

- Let's Encrypt;
- reverse proxy Nginx/Traefik/Caddy.

## Scaling considerations

Scale independently:

- API;
- AI workers;
- collector workers;
- browser workers;
- dashboard.

Browser workers are resource-heavy. Limit concurrent sessions per tenant and per server.

## Release process

1. Merge to main.
2. CI passes.
3. Build images.
4. Run migrations.
5. Deploy API/workers/dashboard.
6. Smoke test login, provider test, lead sync.
7. Monitor errors.

## Odoo module packaging

Provide script:

```bash
make odoo-package
```

Output:

```text
dist/leadintel_connector-19.0.x.y.z.zip
```

Package must not include:

- `.git`;
- test cache;
- local env;
- pycache;
- secrets.

## Acceptance criteria

- `docker compose up` starts full local stack.
- API health endpoint works.
- Dashboard can login to seeded tenant.
- Worker processes a sample job.
- MinIO stores source evidence.
- Odoo module ZIP builds.
- CI rejects secret patterns.
