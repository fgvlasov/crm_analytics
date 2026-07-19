# 09 — Tender Collectors Requirements

## Purpose

Tender collectors are the first external lead discovery flow.

They log into tender systems, collect tender opportunities, normalize data, score relevance and create candidate leads.

Initial test portal:

```text
https://smart.rpt.fi/login
```

## Important legal/operational rule

The platform must use customer-provided credentials and respect source access rules. Do not bypass authentication, paywalls, CAPTCHAs, rate limits or access controls.

If a portal blocks automation or requires MFA/CAPTCHA, implement manual handoff mode rather than bypassing it.

## Collector architecture

Each source adapter implements:

```python
class TenderAdapter:
    adapter_key: str

    async def test_login(self, config, credentials) -> TestResult: ...
    async def collect_listings(self, run_context) -> list[RawTenderListing]: ...
    async def collect_detail(self, listing) -> RawTenderDetail: ...
    async def normalize(self, raw) -> NormalizedTender: ...
```

## Smart RPT adapter MVP

Adapter key:

```text
smart_rpt
```

Config:

```json
{
  "login_url": "https://smart.rpt.fi/login",
  "base_url": "https://smart.rpt.fi",
  "search_keywords": ["cold room", "freezer", "refrigeration"],
  "languages": ["fi", "en"],
  "regions": ["FI"],
  "max_items_per_run": 50,
  "collect_documents": false,
  "manual_mfa_mode": true
}
```

Credentials:

```text
username
password
```

Credentials are stored encrypted in SecretRef.

## Browser automation

Use Playwright.

Requirements:

- isolated browser context per tenant/source run;
- no shared cookies between tenants;
- persistent session storage only if encrypted and tenant-scoped;
- screenshots on failure;
- HTML snapshot of relevant pages where allowed;
- human-readable failure reason.

## Collector run lifecycle

```text
queued
running_login
running_listing
running_detail
running_normalization
running_ai_scoring
succeeded
failed
partial_success
```

Store run stats:

```text
items_seen
items_new
items_duplicate
items_failed
candidates_created
started_at
finished_at
error_message
```

## Normalized tender fields

```text
title
buyer_name
buyer_business_id optional
country_code
city/region optional
publication_date optional
deadline_date optional
estimated_value optional
currency optional
cpv_codes optional
category optional
description
requirements_summary
source_url
portal_external_id optional
documents metadata optional
language
raw_text
```

## Evidence storage

For each tender item store:

- source URL;
- title;
- raw text excerpt;
- HTML snapshot key if allowed;
- screenshot key on detail page if useful;
- document metadata;
- timestamps.

## AI tender scoring

AI should evaluate:

```text
business fit
project potential
customer/buyer quality
urgency based on deadline
technical relevance
geography
```

For Coldex sample profile, relevant tender terms include:

```text
cold room
freezer room
freezer warehouse
cold warehouse
industrial refrigeration
refrigeration plant
cooling system
food production facility
cold chain logistics
varasto
pakastevarasto
kylmähuone
jäähdytys
kylmälaitos
```

But this must be configurable per tenant.

## Deduplication

Deduplicate by:

1. source external ID;
2. canonical URL hash;
3. title + buyer + deadline similarity;
4. content hash.

If duplicate found, update existing source item and candidate rather than creating new.

## Manual MFA mode

Some portals may require MFA.

Implement later:

```text
run pauses at login challenge
user receives dashboard notification
user opens remote browser session or uploads session cookie manually
run resumes
```

For MVP, if MFA appears:

```text
status = failed
error_code = mfa_required
```

## Tender source schedule

Configurable schedule:

```text
every 1 hour
every 6 hours
daily
weekly
custom cron
```

Respect plan limits.

## Candidate creation rule

Create candidate if:

```text
score_total >= tenant_threshold
```

Default thresholds:

```text
hot: 80+
warm: 50+
create candidate: 40+
```

Low/non-relevant items remain SourceItems but not CandidateLead unless configured.

## Push to Odoo

When approved, create Odoo CRM Lead with:

```text
Lead name: Tender: {title}
Company: buyer_name
Description: summary + evidence + source URL + deadline
Tags: LeadIntel, Tender, source name, AI temperature
Expected revenue: estimated_value if known
Deadline: next activity date if available
```

## Acceptance criteria

- Tenant can configure Smart RPT source credentials.
- Test login returns success or clear error.
- Scheduled run collects listings.
- Duplicate tenders are not repeated.
- Relevant tender creates candidate lead.
- Candidate has score and explanation.
- User can push candidate to Odoo.
- Failed login does not leak password in logs.
- Browser screenshots are tenant-scoped and protected.
