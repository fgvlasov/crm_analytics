# 05 — API Contracts

## API style

Use REST JSON API under:

```text
/api/v1
```

Use OpenAPI schema generated from backend.

All API responses must include a request ID header:

```text
X-Request-Id
```

## Authentication

### Dashboard user auth

Use session cookie or JWT with refresh token.

Required endpoints:

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
POST /api/v1/auth/invite
POST /api/v1/auth/accept-invite
```

### Odoo module auth

Odoo module uses:

```text
Authorization: Bearer <integration_token>
X-LeadIntel-Tenant: <tenant_id>
X-LeadIntel-Odoo-Instance: <odoo_instance_id>
X-LeadIntel-Signature: <hmac_sha256>
X-LeadIntel-Timestamp: <unix_ts>
```

Signature payload:

```text
METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + RAW_BODY_SHA256
```

Reject request if timestamp drift is more than 5 minutes.

## Odoo integration endpoints

### Register / test Odoo instance

```http
POST /api/v1/odoo/instances/register
```

Request:

```json
{
  "tenant_slug": "coldex",
  "instance_name": "Coldex Stage",
  "base_url": "https://stage-hub.coldex.fi",
  "odoo_version": "19.0",
  "database_name": "stage-hub",
  "company_name": "Coldex Oy",
  "module_version": "19.0.1.0.0"
}
```

Response:

```json
{
  "odoo_instance_id": "uuid",
  "integration_token": "shown-once-token",
  "webhook_secret": "shown-once-secret",
  "status": "connected"
}
```

Tokens are shown once and must be stored encrypted/hashed server-side.

### Upsert lead from Odoo

```http
POST /api/v1/odoo/leads/upsert
```

Request:

```json
{
  "idempotency_key": "crm.lead:123:2026-07-12T10:30:00Z",
  "odoo_instance_id": "uuid",
  "model": "crm.lead",
  "res_id": "123",
  "write_date": "2026-07-12T10:30:00Z",
  "lead": {
    "name": "Freezer warehouse request",
    "company_name": "Example Food Oy",
    "contact_name": "Matti Virtanen",
    "email": "matti@examplefood.fi",
    "phone": "+358...",
    "website": "https://examplefood.fi",
    "country_code": "FI",
    "city": "Tampere",
    "description": "Need freezer warehouse -25 C...",
    "expected_revenue": 150000,
    "stage_name": "New",
    "salesperson_name": "Alex",
    "team_name": "Sales"
  },
  "messages": [
    {
      "message_id": "456",
      "date": "2026-07-12T09:50:00Z",
      "author_email": "matti@examplefood.fi",
      "subject": "Freezer warehouse",
      "body_text": "..."
    }
  ],
  "attachments": [
    {
      "id": "789",
      "filename": "layout.pdf",
      "mimetype": "application/pdf",
      "size": 234567
    }
  ]
}
```

Response:

```json
{
  "lead_id": "uuid",
  "status": "accepted",
  "queued_jobs": ["fast_assessment"]
}
```

Rules:

- Do not send attachment binary content in MVP.
- Send attachment metadata only.
- Body text should be sanitized in Odoo module.

### Trigger assessment

```http
POST /api/v1/odoo/leads/{lead_id}/assessments/queue
```

Request:

```json
{
  "assessment_mode": "fast|deep|full",
  "force": false
}
```

Response:

```json
{
  "status": "queued",
  "job_id": "uuid"
}
```

### Get assessment status

```http
GET /api/v1/odoo/leads/{lead_id}/assessments/latest
```

Response:

```json
{
  "lead_id": "uuid",
  "fast": {
    "status": "succeeded",
    "score_total": 82,
    "temperature": "hot",
    "summary": "..."
  },
  "deep": {
    "status": "running",
    "started_at": "2026-07-12T10:35:00Z"
  }
}
```

## SaaS dashboard endpoints

### Leads

```text
GET    /api/v1/leads
GET    /api/v1/leads/{id}
POST   /api/v1/leads/{id}/assessments/queue
GET    /api/v1/leads/{id}/assessments
GET    /api/v1/leads/{id}/sources
```

Filter parameters:

```text
score_min
score_max
temperature
source_type
project_type
industry
created_from
created_to
search
```

### Candidate leads

```text
GET    /api/v1/candidates
GET    /api/v1/candidates/{id}
POST   /api/v1/candidates/{id}/approve
POST   /api/v1/candidates/{id}/ignore
POST   /api/v1/candidates/{id}/push-to-odoo
```

Push request:

```json
{
  "odoo_instance_id": "uuid",
  "salesperson_id": null,
  "team_id": null,
  "create_activity": true,
  "note": "Created from LeadIntel tender discovery"
}
```

### AI providers

```text
GET    /api/v1/providers
POST   /api/v1/providers
GET    /api/v1/providers/{id}
PATCH  /api/v1/providers/{id}
DELETE /api/v1/providers/{id}
POST   /api/v1/providers/{id}/test
```

Create request:

```json
{
  "name": "Coldex OpenAI",
  "provider_type": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "organization_id": null,
  "project_id": null
}
```

Response must never return `api_key`.

### Model profiles

```text
GET    /api/v1/model-profiles
POST   /api/v1/model-profiles
PATCH  /api/v1/model-profiles/{id}
DELETE /api/v1/model-profiles/{id}
```

### External sources

```text
GET    /api/v1/sources
POST   /api/v1/sources
GET    /api/v1/sources/{id}
PATCH  /api/v1/sources/{id}
DELETE /api/v1/sources/{id}
POST   /api/v1/sources/{id}/test
POST   /api/v1/sources/{id}/run-now
GET    /api/v1/sources/{id}/items
```

### Jobs

```text
GET /api/v1/jobs
GET /api/v1/jobs/{id}
POST /api/v1/jobs/{id}/cancel
POST /api/v1/jobs/{id}/retry
```

### Usage

```text
GET /api/v1/usage/current
GET /api/v1/usage/history
```

## Webhooks to Odoo

SaaS can call Odoo webhook endpoint exposed by Odoo module.

Endpoint in Odoo:

```text
POST /leadintel/webhook/assessment-result
```

Payload:

```json
{
  "event": "lead.assessment.updated",
  "event_id": "uuid",
  "leadintel_lead_id": "uuid",
  "odoo_model": "crm.lead",
  "odoo_res_id": "123",
  "assessment": {
    "type": "deep",
    "status": "succeeded",
    "score_total": 86,
    "temperature": "hot",
    "confidence": 91,
    "summary": "...",
    "recommended_action": "Call today and ask for drawings.",
    "dashboard_url": "https://app.leadintel.example/leads/uuid"
  }
}
```

Odoo response:

```json
{
  "status": "ok"
}
```

Webhook must be idempotent by `event_id`.

## Error format

All errors:

```json
{
  "error": {
    "code": "subscription_limit_exceeded",
    "message": "Monthly deep research limit exceeded.",
    "request_id": "...",
    "details": {}
  }
}
```

## Pagination

Use cursor pagination for lists.

Request:

```text
GET /api/v1/leads?limit=50&cursor=...
```

Response:

```json
{
  "items": [],
  "next_cursor": "..."
}
```

## API versioning

- Use `/api/v1` initially.
- Breaking changes require `/api/v2`.
- Odoo module must send its module version in every request.
