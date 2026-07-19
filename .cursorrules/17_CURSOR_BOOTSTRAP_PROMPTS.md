# 17 — Cursor Bootstrap Prompts

Prompts align with phases in `18_PHASED_DEVELOPMENT_PLAN.md`.
Set the listed feature flags before implementing each slice.

## Prompt 1 — Phase 1: Monorepo / Backend / Tenants / Auth

**Flags:** all `FEATURE_*=false` (Phase 1 has no flag)

```text
Read .cursorrules/00_README.md and .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 1). Build the initial monorepo skeleton for the AI Lead Intelligence SaaS exactly according to the requirements. Implement Phase 1 only. Do not implement Odoo sync, tender scraping, or AI calls yet. Create clean code, Docker Compose, FastAPI health endpoint, PostgreSQL/Alembic setup, Tenant/User models, auth, secret service, seed Coldex Demo, feature-flag config (all FEATURE_* default false) with /api/v1/features, and tests. Keep all tenant isolation and security rules from the requirements. After implementation, show file tree and commands to run locally.
```

## Prompt 2 — Phase 2: Odoo connector

**Flags:** `FEATURE_ODOO_CONNECTOR=true`

```text
Read .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 2), .cursorrules/06_ODOO_MODULE_REQUIREMENTS.md, and the existing backend code. Implement the Odoo 19 addon leadintel_connector and the backend endpoints needed for Odoo registration and CRM lead upsert. Gate all Odoo SaaS routes behind FEATURE_ODOO_CONNECTOR. Do not add AI yet. Ensure Odoo install is safe, no external calls happen during installation, and SaaS downtime never blocks crm.lead create/write. Add tests/static validation and packaging script.
```

## Prompt 3 — Phase 3: Fast AI assessment

**Flags:** `FEATURE_FAST_AI=true` (optionally `FEATURE_ODOO_CONNECTOR=true` for Odoo callback)

```text
Read .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 3) and .cursorrules/11_AI_ANALYTICS_REQUIREMENTS.md. Implement Fast Lead Assessment behind FEATURE_FAST_AI with a mock AI provider first, strict schema validation, server-side score clamping, temperature calculation, fingerprints, async queue job, and SaaS-to-Odoo callback when FEATURE_ODOO_CONNECTOR is on. Do not implement deep web research yet. Add tests for invalid AI outputs and prompt injection. Without Odoo, operate on API/seed leads.
```

## Prompt 4 — Phase 4: Deep research

**Flags:** `FEATURE_FAST_AI=true`, `FEATURE_DEEP_RESEARCH=true`

```text
Read .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 4). Implement Deep Lead Research behind FEATURE_DEEP_RESEARCH according to .cursorrules/11_AI_ANALYTICS_REQUIREMENTS.md. Enforce startup validation that Deep requires FEATURE_FAST_AI=true. Use internal Odoo history, similar deal candidates, tenant business profile, optional web research provider abstraction, evidence storage, source validation, stale/fingerprint behavior and Odoo callback when the connector flag is on. Keep all long operations in workers. Add tests for stale runs, requeue after lead update, invalid similar deal IDs and tenant isolation.
```

## Prompt 5 — Phase 5: Smart RPT tender collector

**Flags:** `FEATURE_SMART_RPT=true` (add `FEATURE_FAST_AI=true` for tender scoring)

```text
Read .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 5) and .cursorrules/09_TENDER_COLLECTORS.md. Implement the Smart RPT tender source adapter behind FEATURE_SMART_RPT using Playwright workers. Portal has no API — password login only (https://smart.rpt.fi/login). Use encrypted tenant credentials, isolated browser context, login test, listing extraction interface, screenshots on failure and source item persistence. Do not bypass MFA/CAPTCHA; use manual handoff mode. If FEATURE_FAST_AI is off, leave items awaiting_ai instead of scoring. Add fixtures/mocks if real portal credentials are unavailable.
```

## Prompt 6 — Phase 6: Web/news collector

**Flags:** `FEATURE_WEB_NEWS_COLLECTORS=true` (add Fast AI / Odoo flags as needed)

```text
Read .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md (Phase 6) and .cursorrules/10_WEB_NEWS_COLLECTORS.md. Implement generic RSS and custom URL source collectors behind FEATURE_WEB_NEWS_COLLECTORS with article extraction, canonical URL deduplication, source item storage and AI signal detection with mock AI provider first when FEATURE_FAST_AI is on. Add candidate creation and dashboard review flow. If FEATURE_ODOO_CONNECTOR is on, support idempotent push of approved candidates to Odoo.
```

## Prompt 7 — Post-MVP: Production hardening

**Flags:** as deployed for implemented phases

```text
Review the entire codebase against .cursorrules/12_SECURITY_COMPLIANCE.md, .cursorrules/15_TESTING_ACCEPTANCE.md, and feature-flag behavior in .cursorrules/18_PHASED_DEVELOPMENT_PLAN.md. Add tenant isolation tests, secret redaction tests, HMAC replay tests, object storage signed URL checks, role permission checks, feature-disabled route tests, and production security checklist documentation. Do not add features until these tests pass.
```
