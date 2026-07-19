# 16 — Roadmap Tasks for Cursor

Use this file as the working task list in Cursor.

## Phase 0 — Repository bootstrap

### Task 0.1 — Create monorepo skeleton

Create full folder structure from `03_MONOREPO_STRUCTURE.md`.

Acceptance:

- folders exist;
- root README explains product;
- `.env.example` exists;
- Makefile has placeholder commands.

### Task 0.2 — Docker Compose local stack

Create local compose with:

- PostgreSQL;
- Redis;
- MinIO;
- API placeholder;
- dashboard placeholder;
- workers placeholder.

Acceptance:

- `docker compose up` starts services;
- DB is reachable;
- MinIO reachable;
- Redis reachable.

## Phase 1 — Backend foundation

### Task 1.1 — FastAPI app foundation

Implement:

- config;
- logging;
- health endpoints;
- DB session;
- Alembic;
- base models.

Acceptance:

- `/healthz` returns OK;
- migration creates DB tables;
- tests pass.

### Task 1.2 — Auth and tenants

Implement:

- Tenant;
- TenantUser;
- login;
- current user;
- role checks;
- seed Coldex Demo.

Acceptance:

- seeded user can login;
- unauthorized request rejected;
- tenant membership enforced.

### Task 1.3 — Secret service

Implement encrypted secret storage.

Acceptance:

- secret stored encrypted;
- API never returns plaintext;
- logs redacted.

## Phase 2 — Odoo integration

### Task 2.1 — Odoo instance model/API

Implement SaaS-side Odoo instance CRUD and registration.

Acceptance:

- tenant admin can create Odoo integration;
- token generated once;
- token hash stored.

### Task 2.2 — Odoo addon skeleton

Create `leadintel_connector` Odoo 19 addon.

Acceptance:

- module installs on Odoo 19 CRM;
- settings page exists;
- no external calls during install.

### Task 2.3 — Odoo lead sync

Implement payload builder and sync cron/button.

Acceptance:

- CRM lead sends payload to `/odoo/leads/upsert`;
- SaaS stores normalized lead;
- Odoo UI shows sync status.

### Task 2.4 — Odoo webhook result update

Implement Odoo webhook and SaaS callback.

Acceptance:

- SaaS result updates Odoo lead fields;
- duplicate event ignored;
- signature verified.

## Phase 3 — AI provider and lead assessment

### Task 3.1 — AI provider CRUD

Implement provider connection and test endpoint.

Acceptance:

- OpenAI provider can be saved;
- key encrypted;
- test connection works with mock provider first.

### Task 3.2 — Fast assessment

Implement structured fast assessment with mock provider, then real provider.

Acceptance:

- lead queues fast job;
- worker saves score breakdown;
- dashboard shows result;
- Odoo receives result.

### Task 3.3 — Deep research

Implement deep workflow:

- internal context;
- similar deals candidates;
- optional web research;
- structured output;
- evidence.

Acceptance:

- deep job runs asynchronously;
- sources saved;
- stale/fingerprint behavior works;
- Odoo updated.

## Phase 4 — Dashboard MVP

### Task 4.1 — Dashboard auth/layout

Implement login and main layout.

Acceptance:

- user can login;
- tenant name shown;
- protected routes enforced.

### Task 4.2 — Leads list/detail

Implement leads table and detail page.

Acceptance:

- leads visible;
- filters work;
- assessment details visible;
- queue buttons work.

### Task 4.3 — Integrations/settings

Implement Odoo integrations and AI provider pages.

Acceptance:

- provider configured;
- Odoo instance configured;
- test actions visible.

## Phase 5 — Tender collector MVP

### Task 5.1 — Source model/API

Implement source CRUD.

Acceptance:

- tenant can create Smart RPT source draft;
- credentials encrypted.

### Task 5.2 — Smart RPT adapter skeleton

Implement Playwright adapter with login/test using configurable selectors.

Acceptance:

- login success/failure captured;
- screenshots on failure;
- credentials redacted.

### Task 5.3 — Tender item normalization

Implement listing/detail extraction and SourceItem persistence.

Acceptance:

- source run creates SourceItems;
- duplicates suppressed.

### Task 5.4 — Tender candidate scoring

Implement AI tender scoring and candidate creation.

Acceptance:

- relevant tender becomes candidate;
- candidate has score/evidence.

## Phase 6 — Web/news collector MVP

### Task 6.1 — Generic RSS collector

Implement RSS fetch and SourceItem creation.

Acceptance:

- RSS source creates SourceItems;
- duplicates suppressed.

### Task 6.2 — Generic article extractor

Implement URL fetch and article text extraction.

Acceptance:

- title/text/date extracted;
- source evidence stored.

### Task 6.3 — AI signal detection

Implement AI classification into CandidateLead.

Acceptance:

- relevant article creates candidate;
- evidence shown in dashboard.

## Phase 7 — Candidate workflow

### Task 7.1 — Candidate list/detail dashboard

Acceptance:

- candidates visible;
- review/ignore/approve actions work.

### Task 7.2 — Push candidate to Odoo

Acceptance:

- approved candidate creates crm.lead in Odoo;
- idempotent push;
- source evidence included in description.

## Phase 8 — Subscription/usage MVP

### Task 8.1 — Plan and usage models

Acceptance:

- tenant has plan;
- usage increments;
- limits enforce.

### Task 8.2 — Usage dashboard

Acceptance:

- usage bars visible;
- limit exceeded blocks paid jobs only.

## Phase 9 — Production hardening

### Task 9.1 — Tenant isolation tests

Acceptance:

- all cross-tenant access tests pass.

### Task 9.2 — Observability

Acceptance:

- structured logs;
- job health;
- failed job retry UI.

### Task 9.3 — Security checklist

Acceptance:

- no secrets in logs;
- HMAC verified;
- object signed URLs;
- production env checklist complete.

## First Cursor prompt

Use this prompt in Cursor after adding all `.cursorrules/*.md` files:

```text
Read all files in .cursorrules. Build the initial monorepo skeleton for the AI Lead Intelligence SaaS exactly according to the requirements. Start with Phase 0 and Phase 1 only. Do not implement tender scraping or AI calls yet. Create clean code, Docker Compose, FastAPI health endpoint, PostgreSQL/Alembic setup, Tenant/User models, auth skeleton, and tests. Keep all tenant isolation and security rules from the requirements. After implementation, show file tree and commands to run locally.
```
