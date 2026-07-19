# 04 — Data Model Requirements

## General database rules

- Use PostgreSQL.
- All tenant-scoped records must have `tenant_id`.
- Use UUID primary keys for SaaS tables.
- Use `created_at`, `updated_at`, `deleted_at` where appropriate.
- Use soft delete for customer-facing business objects.
- Use hard delete only for ephemeral job logs where retention policy allows it.
- All external IDs must be stored as strings, not integers, because different systems use different formats.

## Core entities

### Tenant

Represents one customer account.

Fields:

```text
id UUID PK
name string
slug string unique
status enum(active, trial, suspended, cancelled)
plan_id UUID nullable
primary_country string nullable
timezone string default Europe/Helsinki
created_at timestamp
updated_at timestamp
```

### TenantUser

Fields:

```text
id UUID PK
tenant_id UUID FK
email string
name string
role enum(owner, admin, sales_manager, sales_user, analyst, auditor)
status enum(invited, active, disabled)
last_login_at timestamp nullable
created_at timestamp
updated_at timestamp
```

Unique:

```text
unique(tenant_id, email)
```

### OdooInstance

One connected Odoo installation.

Fields:

```text
id UUID PK
tenant_id UUID FK
name string
base_url string
odoo_version string nullable
company_name string nullable
database_name string nullable
connection_mode enum(module_callback, jsonrpc, xmlrpc)
status enum(draft, connected, error, disabled)
api_token_hash string nullable
webhook_secret_encrypted text nullable
last_seen_at timestamp nullable
last_sync_at timestamp nullable
created_at timestamp
updated_at timestamp
```

Do not store Odoo admin password unless absolutely necessary. Prefer integration module token and signed callbacks.

### AiProviderConnection

Fields:

```text
id UUID PK
tenant_id UUID FK
name string
provider_type enum(openai, azure_openai, openai_compatible, gemini, anthropic)
base_url string nullable
api_key_encrypted text
organization_id_encrypted text nullable
project_id_encrypted text nullable
status enum(draft, active, error, disabled)
last_test_at timestamp nullable
last_error text nullable
created_at timestamp
updated_at timestamp
```

### AiModelProfile

Configurable model profile per workflow.

Fields:

```text
id UUID PK
tenant_id UUID FK
provider_connection_id UUID FK
workflow enum(fast_lead_assessment, deep_lead_research, tender_scoring, web_signal_detection, summarization)
model_name string
reasoning_effort string nullable
max_output_tokens int nullable
timeout_seconds int
is_default bool
created_at timestamp
updated_at timestamp
```

### Lead

Normalized lead, usually mirrored from Odoo or created from candidate.

Fields:

```text
id UUID PK
tenant_id UUID FK
source_type enum(odoo, tender, web, manual, api)
odoo_instance_id UUID nullable
odoo_model string nullable default crm.lead
odoo_res_id string nullable
odoo_write_date timestamp nullable
name string
company_name string nullable
contact_name string nullable
email string nullable
phone string nullable
website string nullable
country_code string nullable
city string nullable
address text nullable
description text nullable
expected_revenue numeric nullable
stage_name string nullable
salesperson_name string nullable
team_name string nullable
external_created_at timestamp nullable
external_updated_at timestamp nullable
raw_payload_json jsonb
canonical_company_domain string nullable
status enum(active, archived, converted, lost)
created_at timestamp
updated_at timestamp
```

Indexes:

```text
(tenant_id, source_type)
(tenant_id, odoo_instance_id, odoo_res_id)
(tenant_id, canonical_company_domain)
(tenant_id, created_at)
```

### LeadAssessment

Latest and historical AI assessment.

Fields:

```text
id UUID PK
tenant_id UUID FK
lead_id UUID FK
assessment_type enum(fast, deep)
status enum(queued, running, succeeded, failed, stale, cancelled)
score_total int nullable
business_fit int nullable
project_potential int nullable
customer_quality int nullable
urgency int nullable
technical_completeness int nullable
geography int nullable
temperature enum(hot, warm, low, not_relevant) nullable
confidence int nullable
relevant_to_customer bool nullable
project_type string nullable
customer_industry string nullable
project_size string nullable
estimated_value_band string nullable
summary text nullable
positive_signals jsonb
risks jsonb
missing_information jsonb
recommended_action text nullable
company_profile_json jsonb
contact_profile_json jsonb
market_signals_json jsonb
similar_deals_json jsonb
source_refs_json jsonb
raw_model_output_json jsonb
input_fingerprint string
model_name string nullable
provider_type string nullable
started_at timestamp nullable
finished_at timestamp nullable
error_message text nullable
created_at timestamp
updated_at timestamp
```

Rules:

- Store every run, not only latest.
- Lead should have pointers to latest fast and latest deep assessment.
- Failed runs must preserve error details without secrets.

### ExternalSource

Configured source for tenders/news/directories.

Fields:

```text
id UUID PK
tenant_id UUID FK
name string
source_type enum(tender_portal, news_site, directory, custom_url, rss, search_query)
adapter_key string
base_url string nullable
status enum(active, paused, error, disabled)
login_required bool
credentials_secret_id UUID nullable
schedule_cron string nullable
country_code string nullable
language string nullable
config_json jsonb
last_run_at timestamp nullable
last_success_at timestamp nullable
last_error text nullable
created_at timestamp
updated_at timestamp
```

### SourceItem

Raw or normalized discovered item from external source.

Fields:

```text
id UUID PK
tenant_id UUID FK
source_id UUID FK
item_type enum(tender, article, directory_company, project_listing, unknown)
external_id string nullable
canonical_url text nullable
canonical_url_hash string nullable
title string
description text nullable
published_at timestamp nullable
deadline_at timestamp nullable
buyer_name string nullable
company_name string nullable
country_code string nullable
city string nullable
raw_html_object_key string nullable
screenshot_object_key string nullable
raw_payload_json jsonb
content_hash string nullable
status enum(new, processed, duplicate, ignored, error)
created_at timestamp
updated_at timestamp
```

Unique:

```text
unique(tenant_id, source_id, external_id) where external_id is not null
unique(tenant_id, source_id, canonical_url_hash) where canonical_url_hash is not null
```

### CandidateLead

Potential lead discovered externally but not yet pushed to Odoo.

Fields:

```text
id UUID PK
tenant_id UUID FK
source_item_id UUID nullable
source_type enum(tender, web_news, directory, manual)
name string
company_name string nullable
contact_name string nullable
email string nullable
phone string nullable
website string nullable
country_code string nullable
city string nullable
description text nullable
deadline_at timestamp nullable
estimated_value numeric nullable
score_total int nullable
temperature enum(hot, warm, low, not_relevant) nullable
confidence int nullable
summary text nullable
recommended_action text nullable
evidence_json jsonb
status enum(new, reviewed, approved, pushed_to_odoo, ignored, duplicate)
pushed_odoo_instance_id UUID nullable
pushed_odoo_res_id string nullable
created_at timestamp
updated_at timestamp
```

### JobRun

Fields:

```text
id UUID PK
tenant_id UUID FK nullable
job_type string
status enum(queued, running, succeeded, failed, retrying, cancelled)
queue_name string
entity_type string nullable
entity_id UUID nullable
attempt int
max_attempts int
scheduled_at timestamp
started_at timestamp nullable
finished_at timestamp nullable
error_code string nullable
error_message text nullable
metadata_json jsonb
created_at timestamp
updated_at timestamp
```

### AuditLog

Fields:

```text
id UUID PK
tenant_id UUID FK nullable
actor_type enum(user, system, worker, odoo_module)
actor_user_id UUID nullable
action string
entity_type string
entity_id string
ip_address string nullable
user_agent text nullable
metadata_json jsonb
created_at timestamp
```

### UsageMetric

Tracks subscription usage.

Fields:

```text
id UUID PK
tenant_id UUID FK
period_start date
period_end date
metric_type enum(ai_fast_assessment, ai_deep_research, tender_items, web_items, odoo_pushes, users, sources)
quantity int
cost_estimate numeric nullable
created_at timestamp
updated_at timestamp
```

## Secret storage model

Create `SecretRef` table.

```text
id UUID PK
tenant_id UUID FK nullable
secret_type enum(ai_api_key, odoo_token, portal_password, portal_cookie, webhook_secret)
name string
ciphertext text
key_version string
created_by_user_id UUID nullable
created_at timestamp
updated_at timestamp
last_used_at timestamp nullable
```

Never return ciphertext or plaintext secret through normal API responses.

## Object storage

Use S3-compatible object storage for:

- crawler raw HTML;
- screenshots;
- downloaded public tender documents if permitted;
- AI prompt/debug payload snapshots in staging only;
- export reports.

Object key convention:

```text
tenants/{tenant_id}/sources/{source_id}/items/{source_item_id}/raw.html
tenants/{tenant_id}/sources/{source_id}/items/{source_item_id}/screenshot.png
tenants/{tenant_id}/jobs/{job_id}/debug.json
```

## Retention policy

Default retention:

- AI run logs: 12 months;
- crawler raw HTML: 6 months;
- screenshots: 3 months;
- audit logs: 24 months;
- active lead/candidate data: until tenant deletes or subscription ends;
- secrets: until deleted or tenant account closed.

Tenant plan may override retention.
