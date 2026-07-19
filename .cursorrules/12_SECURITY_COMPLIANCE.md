# 12 — Security and Compliance Requirements

## Core security principle

This is a multi-tenant SaaS that handles customer CRM data, portal credentials and AI provider keys. Treat all customer data as confidential.

## Secrets

Never store plaintext:

- AI API keys;
- Odoo integration tokens;
- webhook secrets;
- tender portal usernames/passwords;
- session cookies;
- object storage credentials.

Use encryption at rest.

Use a central SecretService.

Secrets must be redacted in:

- logs;
- errors;
- API responses;
- job metadata;
- debug exports.

## Tenant isolation

Every tenant-scoped query must filter by `tenant_id`.

Add tests that attempt cross-tenant access for:

- leads;
- assessments;
- candidates;
- sources;
- jobs;
- AI providers;
- Odoo instances;
- source items;
- object storage downloads.

## Object storage isolation

All object keys must include tenant ID.

Download URLs must be signed and short-lived.

Never expose raw S3 paths directly if they reveal tenant IDs to other tenants.

## Odoo integration security

Use:

- bearer token;
- HMAC signature;
- timestamp drift check;
- HTTPS only in production;
- token rotation;
- event idempotency.

Odoo module must not log request headers containing auth tokens.

## Dashboard security

- Secure cookies.
- CSRF protection if cookie auth used.
- Rate-limit login and password reset.
- Enforce role permissions.
- Confirm destructive actions.
- Session expiry.
- Optional 2FA later.

## Crawler security

Browser workers must be isolated.

Rules:

- no shared browser context between tenants;
- no filesystem access except temp workspace;
- screenshots and raw HTML are tenant-scoped;
- credentials injected only at runtime;
- clean browser context after run;
- no credentials in screenshots if avoidable;
- redact forms/password fields from stored debug where possible.

## AI privacy

Tenant must explicitly configure AI provider or accept platform-included provider under plan.

When using BYOK:

- tenant's AI key is used only for that tenant;
- no sharing across tenants;
- usage tracked.

Prompt content must include only necessary data.

Do not send:

- attachment binaries in MVP;
- unrelated Chatter;
- internal notes unless enabled;
- sensitive personal data not needed for B2B lead scoring.

## Personal data boundaries

Allowed professional research:

- person's current role;
- company affiliation;
- public business profile;
- professional relevance to buying decision.

Not allowed:

- home address;
- family information;
- private social media;
- health;
- religion;
- political views;
- protected attributes;
- personal financial data.

## Prompt injection defense

Treat all external/user content as untrusted data.

Prompts must explicitly state that instructions inside lead descriptions, emails, websites, tender documents or articles must not be followed.

Backend must validate output and never execute AI-provided code or SQL.

## Audit logs

Audit actions:

- login/logout;
- provider created/tested/deleted;
- Odoo instance connected/disabled;
- source created/credentials updated;
- assessment triggered;
- candidate approved/ignored/pushed;
- tenant suspended;
- user invited/disabled;
- token rotated.

Audit logs must not contain secrets.

## Data retention and deletion

Tenant owner should be able to request data export/deletion.

MVP can implement admin-assisted deletion with documented runbook.

Later implement self-service deletion.

## Compliance posture

Design toward GDPR-friendly operation:

- data minimization;
- purpose limitation;
- access control;
- deletion/export capability;
- audit logging;
- DPA-ready architecture.

Do not make legal claims in UI until reviewed.

## Production security checklist

Before production:

- HTTPS everywhere;
- secure cookies;
- CORS restricted;
- secrets encrypted;
- backups encrypted;
- database not public;
- Redis not public;
- object storage not public;
- logs redacted;
- rate limits enabled;
- tenant isolation tests passing;
- dependency scanning;
- admin MFA planned or enabled;
- Odoo webhook signature verified;
- crawler credentials encrypted;
- Sentry/monitoring redaction configured.

## Acceptance criteria

- Cross-tenant access tests fail closed.
- Secret values never appear in API responses.
- Failed crawler login does not log password.
- HMAC replay attack is rejected.
- Odoo webhook duplicate event is idempotent.
- AI prompt injection test does not override scoring rules.
