# 02 — System Architecture

## High-level architecture

```text
+-------------------------+          +-----------------------------+
| Customer Odoo 19        |          | LeadIntel SaaS Dashboard    |
| Odoo Addon              |          | Next.js / React             |
+-----------+-------------+          +---------------+-------------+
            |                                        |
            | HTTPS API / Webhooks                   | HTTPS
            v                                        v
+-------------------------------------------------------------+
| LeadIntel Backend API                                       |
| FastAPI / PostgreSQL / Redis / Object Storage               |
+-------------+----------------+------------------+-------------+
              |                |                  |
              v                v                  v
+-------------------+  +------------------+  +-------------------+
| AI Workers        |  | Tender Workers   |  | Web/News Workers  |
| scoring/research  |  | Playwright/RPA   |  | crawler/extractor |
+---------+---------+  +---------+--------+  +---------+---------+
          |                      |                     |
          v                      v                     v
+-------------------+  +------------------+  +-------------------+
| AI Providers      |  | Tender Portals   |  | Websites/News     |
| OpenAI/BYOK       |  | Smart RPT etc.   |  | Directories       |
+-------------------+  +------------------+  +-------------------+
```

## System boundaries

### Odoo module responsibilities

The Odoo addon must:

- register the Odoo instance in SaaS;
- send CRM lead payloads to SaaS;
- receive/store assessment summaries;
- show AI score/status in CRM;
- allow manual trigger from lead form;
- provide webhook endpoints for SaaS callbacks;
- keep local fallback state if SaaS is down;
- never store tenant AI provider keys unless explicitly required by a customer policy.

### SaaS backend responsibilities

The SaaS backend must:

- own tenants, users, roles, subscriptions;
- store integration credentials securely;
- schedule and execute AI jobs;
- manage AI providers per tenant;
- normalize leads from Odoo, tenders and web sources;
- deduplicate and rank candidate leads;
- expose dashboard APIs;
- push approved candidates to Odoo;
- maintain audit logs and evidence.

### Dashboard responsibilities

The dashboard must:

- provide tenant login;
- connect Odoo instance;
- configure AI provider;
- configure tender/web sources;
- show lead intelligence pipeline;
- review and approve candidates;
- inspect sources and AI run history;
- manage usage/subscription.

### Workers responsibilities

Workers must:

- run slow AI assessments outside HTTP request lifecycle;
- run browser automation in isolated sessions;
- crawl configured sources;
- enforce per-tenant rate limits;
- store raw evidence and extracted structured data;
- retry transient failures safely.

## Multi-tenancy model

Use strict tenant isolation.

Every major table must include `tenant_id`, unless it is truly global metadata.

Never query tenant-scoped data without filtering by `tenant_id`.

Use database indexes:

```sql
(tenant_id, external_id)
(tenant_id, created_at)
(tenant_id, status)
```

Do not rely only on application code for isolation. Add unique constraints scoped by tenant.

Examples:

```text
unique(tenant_id, odoo_instance_id, odoo_model, odoo_res_id)
unique(tenant_id, source_id, source_external_id)
```

## Data flow: incoming Odoo lead

```text
Odoo crm.lead created/updated
    ↓
Odoo addon computes payload + idempotency key
    ↓
POST /api/v1/odoo/leads/upsert
    ↓
SaaS stores/updates Lead record
    ↓
Queue Fast Assessment
    ↓
AI Worker runs fast scoring
    ↓
If relevant or configured: Queue Deep Research
    ↓
Deep AI + Odoo history + web research
    ↓
Assessment saved in SaaS
    ↓
Callback to Odoo / Odoo polls status
    ↓
Odoo updates AI fields
```

## Data flow: tender discovery

```text
Scheduled collector
    ↓
Portal login/session
    ↓
Tender listing scrape
    ↓
Detail pages and documents metadata
    ↓
Normalize TenderOpportunity
    ↓
Deduplicate
    ↓
AI relevance scoring
    ↓
Candidate lead appears in dashboard
    ↓
User approves
    ↓
Push to Odoo as crm.lead
```

## Data flow: news/source discovery

```text
Source schedule
    ↓
Fetch page/feed/search result
    ↓
Extract article/listing/company signal
    ↓
Normalize SourceItem
    ↓
AI commercial signal detection
    ↓
Candidate lead created
    ↓
Optional deep enrichment
    ↓
User approves to Odoo
```

## Idempotency

All external writes must be idempotent.

Required idempotency keys:

- Odoo lead upsert: `tenant_id + odoo_instance_id + model + res_id + write_date`
- Tender item: `tenant_id + source_id + source_external_id OR canonical_url_hash`
- Web source item: `tenant_id + source_id + canonical_url_hash`
- Push candidate to Odoo: `candidate_id + target_odoo_instance_id`

## Queue design

Use queue jobs for:

- AI assessment;
- deep research;
- web search;
- tender collection;
- source crawling;
- Odoo push;
- Odoo callback;
- large sync operations.

Do not run these inside synchronous HTTP handlers.

Job states:

```text
queued
running
succeeded
failed
retrying
cancelled
stale
```

## Retry policy

Retry transient failures:

- network timeout;
- HTTP 429;
- HTTP 5xx;
- browser crash;
- provider temporary error.

Do not retry automatically:

- authentication failed;
- invalid credentials;
- tenant disabled;
- subscription limit exceeded;
- schema validation failed due to programmer error.

## Tenant rate limits

Each tenant must have limits:

- max AI jobs per minute/hour/day;
- max crawler jobs per hour;
- max concurrent browser sessions;
- max source pages per run;
- max Odoo writes per minute.

## Environments

Required environments:

```text
local
staging
production
```

Each environment must have independent DB, Redis, object storage bucket and secret keys.

## Observability

Implement:

- structured JSON logs;
- request ID;
- tenant ID in logs, but no secrets;
- job run logs;
- AI provider usage metrics;
- crawler screenshots for debug stored securely;
- health endpoints;
- metrics endpoint for Prometheus later.
