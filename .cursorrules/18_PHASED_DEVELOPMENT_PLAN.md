# 18 — Phased Development Plan + Feature Flags

Authoritative development order for the AI Lead Intelligence SaaS.

- Product entry point: `00_README.md`
- Detailed task backlog (legacy numbering): `16_ROADMAP_TASKS_FOR_CURSOR.md`
- Ready-to-paste Cursor prompts: `17_CURSOR_BOOTSTRAP_PROMPTS.md`

This file defines **what to build in which order**, when each phase is “done”, and how to **enable/disable** optional phases via environment variables.

## Goal

Ship a working vertical slice after each phase. Phase 1 is always on. Phases 2–6 are independently toggleable (with documented dependencies). Turning a flag off must not break the running stack.

## Feature flags

Phase 1 (monorepo / backend / tenants / auth) has **no** flag — it is always required.

```env
# Phase 1 — always on (no FEATURE_* flag)

FEATURE_ODOO_CONNECTOR=false       # Phase 2
FEATURE_FAST_AI=false              # Phase 3
FEATURE_DEEP_RESEARCH=false        # Phase 4
FEATURE_SMART_RPT=false            # Phase 5
FEATURE_WEB_NEWS_COLLECTORS=false  # Phase 6
```

### Where flags live

| Location | Role |
| --- | --- |
| Root `.env.example` | Document all flags with defaults `false` for phases 2–6 |
| `apps/api/app/core/config.py` | Load and validate flags at API startup |
| Workers / collectors config | Same flags; skip task registration when off |
| Dashboard | Read `/api/v1/features` (or equivalent) and hide disabled UI |

### Behavior when a flag is `false`

- API routes for that phase return a consistent `403 FeatureDisabled` (or `404` if preferred project-wide — pick one and keep it).
- Use a single helper, e.g. `require_feature("odoo_connector")`.
- Workers / collectors do **not** register or consume jobs for the disabled phase.
- Dashboard hides menus, settings pages, and actions for the disabled phase.
- Disabled phases must not be required for health checks or process startup.

### Dependency rules

| Flag | Requires | Startup validation |
| --- | --- | --- |
| `FEATURE_ODOO_CONNECTOR` | Phase 1 only | — |
| `FEATURE_FAST_AI` | Phase 1 only | — |
| `FEATURE_DEEP_RESEARCH` | `FEATURE_FAST_AI=true` | Fail fast with clear config error if Deep is on and Fast is off |
| `FEATURE_SMART_RPT` | Phase 1 only | Collection works without Fast AI; scoring/candidates skip or status `awaiting_ai` |
| `FEATURE_WEB_NEWS_COLLECTORS` | Phase 1 only | Same as Smart RPT for AI-dependent steps |

Soft dependencies (runtime, not hard config errors):

- Push candidates to Odoo needs `FEATURE_ODOO_CONNECTOR`.
- Tender / news scoring and signal detection need `FEATURE_FAST_AI`.
- Deep research callbacks to Odoo need Phase 2 when Odoo sync is desired.

### Dependency diagram

```text
Phase1_Foundation
  ├── Phase2_Odoo          (FEATURE_ODOO_CONNECTOR)
  ├── Phase3_FastAI        (FEATURE_FAST_AI)
  │     └── Phase4_Deep    (FEATURE_DEEP_RESEARCH)
  ├── Phase5_SmartRPT      (FEATURE_SMART_RPT)  --scoring--> FastAI
  └── Phase6_WebNews       (FEATURE_WEB_NEWS_COLLECTORS) --signals--> FastAI
```

---

## Phase 1 — Monorepo / Backend / Tenants / Auth

**Flag:** none (always on)

**Goal:** Local stack and authenticated multi-tenant API without Odoo, AI, or collectors.

### Scope

- Monorepo layout from `03_MONOREPO_STRUCTURE.md`
- Docker Compose: PostgreSQL, Redis, MinIO, API, workers stub, dashboard stub
- FastAPI: config, logging, `/healthz`, DB session, Alembic
- Models: Tenant, TenantUser, roles
- Auth: email/password login, current user, role checks, tenant membership
- Encrypted secret storage service
- Seed: Coldex Demo tenant + user (demo only; no Coldex hard-code elsewhere)
- Tenant isolation tests

### Key modules / paths

```text
apps/api/
apps/workers/          (stub)
apps/dashboard/        (stub login shell optional)
infra/docker-compose*.yml
.env.example           (include FEATURE_* defaults)
packages/shared-schemas/
```

### Tasks

1. Create monorepo skeleton + root README + Makefile placeholders.
2. Docker Compose local stack (DB, Redis, MinIO reachable).
3. FastAPI foundation + Alembic migrations.
4. Auth + tenants + seed Coldex Demo.
5. Secret service (encrypt at rest; never return plaintext).
6. Wire feature-flag config (all optional flags default `false`); expose `/api/v1/features`.

### Acceptance

- `docker compose up` starts core services.
- `/healthz` returns OK.
- Migrations create tables.
- Seeded user can log in; unauthorized requests rejected; tenant membership enforced.
- Secrets stored encrypted; logs redacted.
- App starts cleanly with all `FEATURE_*=false`.

### Explicitly out of scope

- Odoo addon / sync
- AI providers / assessment jobs
- Playwright / tender / news collectors
- Billing / subscriptions UI

### Definition of Done

- Unit/integration tests for auth and tenant isolation pass.
- Compose + migrate + seed documented in root README.
- Feature flag names match this document.

---

## Phase 2 — Odoo connector

**Flag:** `FEATURE_ODOO_CONNECTOR`

**Goal:** Full Odoo ↔ SaaS lead sync without AI.

### Scope

- SaaS: Odoo instance CRUD, registration token (hash stored, plaintext once)
- Odoo 19 addon `leadintel_connector`
- Lead upsert + idempotency
- Webhook / callback skeleton with sync status
- Dashboard/API integration status

### Key modules / paths

```text
apps/api/app/api/v1/odoo.py
apps/api/app/services/odoo_service.py
apps/api/app/integrations/odoo_client.py
odoo_addons/leadintel_connector/
```

### Tasks

1. Odoo instance model/API + token registration.
2. Addon skeleton: install-safe (no external calls on install).
3. CRM lead payload builder + sync cron/button → `POST /api/v1/odoo/leads/upsert`.
4. SaaS→Odoo webhook callback + signature verify + duplicate event ignore.
5. Gate all Odoo SaaS routes behind `FEATURE_ODOO_CONNECTOR`.

### Acceptance

- Tenant admin can create Odoo integration; token generated once.
- Module installs on Odoo 19 CRM; settings page exists.
- CRM lead appears as normalized Lead in SaaS.
- SaaS downtime never blocks `crm.lead` create/write.
- With flag `false`, SaaS Odoo endpoints are disabled; stack still healthy.

### Explicitly out of scope

- AI scoring fields population (Phase 3+)
- Candidate push from collectors (Phases 5–6)

### Definition of Done

- Addon static validation + packaging script.
- Upsert idempotency and HMAC/signature tests.
- Manual E2E: Odoo lead → SaaS lead visible via API/dashboard stub.

---

## Phase 3 — Fast AI

**Flag:** `FEATURE_FAST_AI`

**Goal:** Fast lead assessment end-to-end (queue → validated score → storage → optional Odoo callback).

### Scope

- AI provider CRUD (BYOK, encrypted keys)
- Mock provider first, then OpenAI / OpenAI-compatible
- Fast Assessment: strict schema, score clamp, temperature, fingerprint
- Async worker job (not inside HTTP request)
- Persist assessment + explanation
- Callback to Odoo if Phase 2 enabled
- Minimal dashboard: leads list/detail + score + queue action

### Key modules / paths

```text
apps/api/app/api/v1/providers.py
apps/api/app/api/v1/jobs.py
apps/api/app/services/ai_provider_service.py
apps/api/app/services/assessment_service.py
apps/workers/app/tasks/fast_assessment.py
apps/dashboard/   (leads + providers pages)
```

### Tasks

1. Provider connection + test endpoint (mock first).
2. Fast assessment workflow per `11_AI_ANALYTICS_REQUIREMENTS.md`.
3. Queue job + worker persistence.
4. Odoo result update when `FEATURE_ODOO_CONNECTOR=true`.
5. Without Phase 2: operate on API/seed leads.
6. Gate routes/jobs behind `FEATURE_FAST_AI`.

### Acceptance

- OpenAI (or mock) provider saved; key never returned plaintext.
- Lead queues fast job; worker saves score breakdown.
- Invalid AI output rejected; scores clamped server-side.
- Dashboard shows result; Odoo updated when Phase 2 on.

### Explicitly out of scope

- Deep research / web research (Phase 4)
- Tender/news scoring pipelines (Phases 5–6 can call Fast AI later)

### Definition of Done

- Tests: invalid AI JSON, prompt injection hardening, tenant isolation on assessments.
- Flag off → no fast jobs registered; provider UI hidden.

---

## Phase 4 — Deep Research

**Flag:** `FEATURE_DEEP_RESEARCH` (requires `FEATURE_FAST_AI=true`)

**Goal:** Asynchronous deep enrichment on top of Fast Assessment.

### Scope

- Deep job workflow
- Internal Odoo history + similar deal candidates
- Optional web research provider abstraction
- Evidence storage + source validation
- Stale / fingerprint behavior + requeue after lead update
- Odoo callback when Phase 2 on

### Key modules / paths

```text
apps/workers/app/tasks/deep_research.py
apps/api/app/services/assessment_service.py
apps/api/app/integrations/   (web research abstraction)
```

### Tasks

1. Deep workflow from `11_AI_ANALYTICS_REQUIREMENTS.md`.
2. Similar deals selection with validation (reject invalid IDs).
3. Evidence objects in storage; signed URLs only.
4. Stale run + fingerprint tests.
5. Startup validation: Deep implies Fast AI.
6. Gate behind `FEATURE_DEEP_RESEARCH`.

### Acceptance

- Deep job runs asynchronously; sources/evidence saved.
- Stale/fingerprint behavior works; requeue after lead update.
- Odoo updated when connector enabled.
- Config refuses `FEATURE_DEEP_RESEARCH=true` with Fast AI off.

### Explicitly out of scope

- Tender portal scraping
- Billing limits UI (post-MVP)

### Definition of Done

- Tests: stale runs, invalid similar deal IDs, tenant isolation, evidence redaction.
- Flag off → deep endpoints/jobs absent; Fast AI still works alone.

---

## Phase 5 — Smart RPT (login-based, no API)

**Flag:** `FEATURE_SMART_RPT`

**Goal:** Collect tenders from Smart RPT via password login (Playwright/RPA). Portal has **no public API** — only browser login.

**Portal:** `https://smart.rpt.fi/login`

### Scope

- Source CRUD for tender sources
- Playwright adapter `smart_rpt`
- Encrypted username/password (SecretRef)
- `test_login`, listing/detail extraction, SourceItem persistence, dedup
- Screenshots / HTML evidence on failure
- MFA/CAPTCHA → manual handoff mode (never bypass)
- If Fast AI on: tender relevance scoring → CandidateLead
- If Odoo on: later push of approved candidates (may land with Phase 6 candidate workflow)

### Key modules / paths

```text
apps/collectors/app/adapters/smart_rpt/
apps/api/app/api/v1/sources.py
apps/workers/ or apps/collectors/  (scheduled runs)
```

### Tasks

1. Source model/API + encrypted credentials.
2. Smart RPT adapter skeleton with configurable selectors.
3. Collect run lifecycle + SourceItem normalize/dedup.
4. Fixtures/mocks when real credentials unavailable.
5. Optional AI scoring when `FEATURE_FAST_AI=true`; else `awaiting_ai`.
6. Gate behind `FEATURE_SMART_RPT`.

### Acceptance

- Login success/failure captured; credentials never in logs.
- Source run creates SourceItems; duplicates suppressed.
- Failure screenshots stored with redacted secrets.
- No MFA/CAPTCHA bypass; manual handoff documented.
- Flag off → collector not scheduled; Smart RPT UI hidden.

### Explicitly out of scope

- Other tender portals
- Bypassing paywalls, CAPTCHA, or rate limits

### Definition of Done

- Adapter tests with fixtures; isolation of browser context per tenant/run.
- Legal/ops rules from `09_TENDER_COLLECTORS.md` respected.

---

## Phase 6 — Web / News collectors

**Flag:** `FEATURE_WEB_NEWS_COLLECTORS`

**Goal:** RSS + article extraction + optional AI signals into candidates.

### Scope

- Generic RSS collector
- URL / article text extractor
- Canonical URL deduplication
- SourceItem storage + evidence
- If Fast AI on: signal detection → CandidateLead
- Dashboard review (approve / ignore)
- Push approved candidate to Odoo if Phase 2 on

### Key modules / paths

```text
apps/collectors/app/adapters/generic_news/
apps/api/app/api/v1/candidates.py
apps/api/app/api/v1/sources.py
apps/dashboard/   (candidates review)
```

### Tasks

1. RSS fetch → SourceItems.
2. Article extractor (title/text/date) + evidence.
3. AI signal detection (mock first) when Fast AI on.
4. Candidate list/detail + review actions.
5. Idempotent push to Odoo when connector on.
6. Gate behind `FEATURE_WEB_NEWS_COLLECTORS`.

### Acceptance

- RSS/URL sources create SourceItems; duplicates suppressed.
- Relevant article can become candidate when Fast AI on.
- Evidence visible in dashboard.
- Approved candidate creates `crm.lead` in Odoo when Phase 2 on (idempotent).

### Explicitly out of scope

- Smart RPT (Phase 5)
- Full billing enforcement (post-MVP)

### Definition of Done

- Tests for dedup, signal schema validation, tenant isolation.
- Flag off → web/news jobs and UI disabled.

---

## Per-phase Definition of Done (checklist)

For every phase before moving on:

- [ ] Feature flag documented in `.env.example` and loaded in config
- [ ] Disabled mode verified (API + workers + UI)
- [ ] Acceptance criteria above met
- [ ] Tests for the phase’s critical paths pass
- [ ] No plaintext secrets in logs or API responses
- [ ] Long-running work only via queue/workers
- [ ] README notes how to run this phase locally (which flags to set)

---

## Post-MVP (after Phase 6)

Not gated by the flags above; schedule after the six phases work:

- Subscription / usage metering (`13_SUBSCRIPTION_BILLING.md`, old roadmap Phase 8)
- Production hardening, observability, security checklist (`12_`, `15_`, old roadmap Phase 9)
- Additional tender portals and directory adapters

---

## Recommended Cursor prompts

Use prompts in `17_CURSOR_BOOTSTRAP_PROMPTS.md`. Mapping:

| Prompt in `17_` | This plan phase | Flags to enable for the slice |
| --- | --- | --- |
| Prompt 1 | Phase 1 | all `FEATURE_*=false` |
| Prompt 2 | Phase 2 | `FEATURE_ODOO_CONNECTOR=true` |
| Prompt 3 | Phase 3 | `FEATURE_FAST_AI=true` (+ Odoo optional) |
| Prompt 4 | Phase 4 | `FEATURE_FAST_AI=true`, `FEATURE_DEEP_RESEARCH=true` |
| Prompt 5 | Phase 5 | `FEATURE_SMART_RPT=true` (+ Fast AI for scoring) |
| Prompt 6 | Phase 6 | `FEATURE_WEB_NEWS_COLLECTORS=true` (+ Fast AI / Odoo as needed) |
| Prompt 7 | Post-MVP hardening | all implemented flags as deployed |

Always start Cursor work with: read `00_README.md`, this file (`18_`), then the phase-specific requirement docs.
