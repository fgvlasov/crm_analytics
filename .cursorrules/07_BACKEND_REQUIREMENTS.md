# 07 — Backend SaaS Requirements

## Backend app

Use FastAPI unless changed explicitly.

The backend must provide:

- authentication;
- tenant management;
- Odoo integration APIs;
- lead storage;
- assessment orchestration;
- AI provider management;
- source and collector management;
- dashboard APIs;
- subscription and usage tracking;
- audit logs.

## Core modules

```text
auth
tenants
users
subscriptions
odoo_instances
leads
assessments
ai_providers
sources
candidates
jobs
audit
usage
```

## Configuration

Environment variables:

```env
APP_ENV=local
APP_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=...
ENCRYPTION_MASTER_KEY=...
S3_ENDPOINT=http://minio:9000
S3_BUCKET=leadintel-local
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

## Authentication

MVP can use email/password with invited users.

Requirements:

- password hashing with Argon2id or bcrypt;
- email verification optional in local, required in production;
- tenant-scoped roles;
- session expiry;
- audit login/logout;
- rate limit login attempts.

## Authorization

Every route must check:

1. authenticated user;
2. tenant membership;
3. role permission;
4. object tenant ownership.

Implement central dependency:

```python
require_tenant_user(role_min=...)
```

## Odoo integration service

Responsibilities:

- register Odoo instance;
- validate signed Odoo requests;
- store normalized leads;
- enqueue assessment jobs;
- send callbacks to Odoo;
- push candidate leads to Odoo;
- handle Odoo unavailable state.

## Lead service

Must support:

- upsert by Odoo external ID;
- normalize domain from email/website;
- store raw payload;
- calculate fingerprints;
- deduplicate candidate leads;
- merge/link external source items to existing leads.

## Assessment orchestration

Fast path:

```text
Lead upserted
    ↓
Create LeadAssessment fast queued
    ↓
Worker executes
    ↓
Save result
    ↓
If score >= threshold or explicit full mode: queue deep
    ↓
Send Odoo callback for fast result
```

Deep path:

```text
Collect internal context
Collect source evidence
Run web research if allowed
Run structured AI
Validate output
Save deep assessment
Update latest assessment pointers
Send Odoo callback
```

## Fingerprints

Use separate fingerprints:

```text
fast_input_fingerprint
deep_input_fingerprint
```

Fast fingerprint should include:

- lead normalized fields;
- latest incoming message texts;
- attachment metadata;
- relevant Odoo metadata.

Deep fingerprint should include:

- fast fingerprint;
- internal history summary hash;
- similar deals candidate hash;
- source context hash.

If fingerprint unchanged and not forced, skip provider call and reuse latest assessment.

## Job handling

Use Celery/Dramatiq/RQ.

Each job must:

- create/update `JobRun`;
- record attempts;
- support retries;
- use tenant rate limits;
- be idempotent;
- never leave entity permanently running after crash.

## AI provider abstraction

Create interface:

```python
class AiProviderClient:
    async def structured_response(self, request: StructuredAiRequest) -> StructuredAiResponse: ...
    async def test_connection(self) -> ProviderTestResult: ...
```

Provider implementations:

```text
OpenAIProviderClient
AzureOpenAIProviderClient
OpenAICompatibleProviderClient
```

Do not hard-code OpenAI in business logic.

## Secret service

Requirements:

- encrypt secrets at rest;
- support key rotation later;
- never return plaintext through API except immediately after generation where needed;
- redact secrets from logs and exceptions.

## Source collection service

Must support:

- source config;
- scheduling;
- run now;
- pause/resume;
- per-source credentials;
- store raw evidence;
- normalize items;
- queue AI scoring.

## Candidate service

Must support:

- candidate creation from source item;
- duplicate detection against existing candidates and leads;
- status transitions;
- review workflow;
- approval;
- push to Odoo;
- ignore with reason;
- audit all transitions.

## Usage tracking

Track usage for:

- fast assessments;
- deep research;
- tender items processed;
- web/news items processed;
- AI provider calls;
- Odoo pushes;
- active sources;
- active users.

Usage must be tenant-scoped and plan-enforced.

## Background schedules

Required schedules:

```text
process queued AI jobs continuously
run due tender sources every N minutes
run due web/news sources every N minutes
sync Odoo callbacks retry queue
detect stuck jobs every 10 minutes
roll up usage daily
cleanup expired raw evidence daily
```

## Admin operations

Super admin backend functionality:

- list tenants;
- inspect tenant health;
- suspend tenant;
- view job failures;
- retry failed jobs;
- see usage aggregates;
- never reveal secrets.

## Error handling

Use typed domain errors:

```text
TenantNotFound
PermissionDenied
SubscriptionLimitExceeded
ProviderAuthFailed
ProviderRateLimited
OdooConnectionFailed
SourceAuthFailed
CrawlerBlocked
SchemaValidationFailed
```

Map errors to API codes.

## Local development seed

Create seed data:

- tenant: Coldex Demo;
- user: admin@example.com;
- Odoo instance draft;
- OpenAI provider draft;
- sample lead;
- sample source: Smart RPT draft;
- sample news source.

No real credentials in seed.
