# 06 — Odoo 19 Integration Module Requirements

## Module name

```text
leadintel_connector
```

## Odoo version

Target: Odoo 19.

## Module purpose

The module is the integration bridge between a customer's Odoo CRM and the SaaS platform.

It should not contain heavy AI logic. AI analytics live in the SaaS backend.

## Dependencies

Required:

```python
'depends': ['base', 'crm', 'mail', 'web']
```

Optional later:

```python
'sale_management'
'website_crm'
'utm'
```

Do not require Enterprise-only modules unless needed. The connector should work with standard CRM if possible.

## Configuration

Add settings under:

```text
Settings → LeadIntel
```

Fields:

```text
Enabled bool
SaaS Base URL char
Tenant Slug char
Odoo Instance Name char
Integration Token password/encrypted
Webhook Secret password/encrypted
Sync Mode selection(manual, automatic)
Auto Sync New Leads bool
Auto Sync Updated Leads bool
Auto Pull Results bool
Auto Push Results via Webhook bool
Sync Incoming Messages bool
Max Messages Per Lead int default 10
Send Attachment Metadata bool default true
Send Attachment Binary bool default false for MVP
```

## Registration wizard

Provide a wizard:

```text
Connect to LeadIntel
```

Flow:

1. User enters SaaS base URL and tenant slug.
2. Odoo module sends registration request.
3. SaaS returns integration token and webhook secret.
4. Odoo stores credentials.
5. Odoo tests connection.
6. User enables integration.

If automatic registration is not ready, allow manual token input.

## CRM Lead UI changes

Add to `crm.lead`:

### Header buttons

```text
LeadIntel Full Assessment
LeadIntel Fast Assessment
LeadIntel Deep Research
Open LeadIntel Dashboard
```

Button behavior:

- Fast: sync current lead, queue fast assessment.
- Deep: sync current lead, queue deep research.
- Full: sync current lead, queue fast + deep.
- Dashboard: open SaaS lead page if known.

Do not block UI waiting for AI result.

### Smart button

Add smart button:

```text
AI Assessment
```

Shows status and opens local assessment records.

### Form tab

Add tab:

```text
LeadIntel AI
```

Fields shown:

```text
AI Score
Temperature
Confidence
Assessment Status
Last Sync At
Last Assessment At
Project Type
Customer Industry
Summary
Recommended Action
Missing Information
Risks
Positive Signals
Dashboard Link
```

### Kanban/List fields

Show compact badge:

```text
🔥 86 Hot
🟡 64 Warm
🔵 31 Low
```

Use text badges, not heavy JS if avoidable.

## Odoo models

### crm.lead extensions

Fields:

```python
leadintel_external_id = fields.Char(index=True)
leadintel_last_sync_at = fields.Datetime()
leadintel_last_assessment_at = fields.Datetime()
leadintel_sync_status = fields.Selection([...])
leadintel_assessment_status = fields.Selection([...])
leadintel_score = fields.Integer()
leadintel_temperature = fields.Selection([...])
leadintel_confidence = fields.Integer()
leadintel_project_type = fields.Char()
leadintel_customer_industry = fields.Char()
leadintel_summary = fields.Text()
leadintel_recommended_action = fields.Text()
leadintel_dashboard_url = fields.Char()
leadintel_error_message = fields.Text()
```

### leadintel.assessment

Stores local assessment snapshots.

Fields:

```text
lead_id Many2one crm.lead
leadintel_assessment_id Char
assessment_type Selection(fast, deep)
status Selection
score_total Integer
temperature Selection
confidence Integer
summary Text
recommended_action Text
raw_json Json/Text
received_at Datetime
```

### leadintel.sync.log

Fields:

```text
operation Selection(sync_lead, queue_assessment, webhook, poll, push_candidate)
lead_id Many2one crm.lead optional
status Selection(success, failed)
request_id Char
error_message Text
payload_hash Char
created_at Datetime
```

### leadintel.webhook.log

Fields:

```text
event_id Char unique
event_type Char
status Selection(processed, duplicate, failed)
payload_json Text
error_message Text
received_at Datetime
```

## Data payload builder

Build sanitized lead payload.

Include:

- lead fields;
- partner fields;
- UTM/source fields when available;
- tags;
- latest external incoming Chatter messages;
- attachment metadata;
- Odoo record metadata.

Exclude:

- internal notes unless explicitly enabled;
- attachment binary by default;
- unrelated Chatter;
- passwords/secrets.

Incoming message detection:

- Include messages where author email domain is not customer's own company domain.
- Include email messages linked to the lead.
- Strip HTML to text.
- Limit message count and max characters.

## Sync triggers

### Manual sync

Button on lead.

### Automatic sync

On `crm.lead.create` and relevant `write` changes, enqueue sync.

Do not call SaaS synchronously inside create/write transaction. Instead:

- mark lead `pending_sync`;
- cron processes pending sync;
- or use Odoo queue if available.

### Cron jobs

Required crons:

```text
LeadIntel: Sync pending leads every 2 minutes
LeadIntel: Poll assessment results every 5 minutes if webhooks disabled
LeadIntel: Retry failed sync every 10 minutes
```

## Webhook controller

Endpoint:

```text
/leadintel/webhook/assessment-result
```

Requirements:

- accept POST JSON;
- verify HMAC signature;
- reject old timestamp;
- idempotent by event_id;
- update crm.lead AI fields;
- create `leadintel.assessment` snapshot;
- log success/failure.

## Security groups

Groups:

```text
leadintel_user
leadintel_manager
leadintel_admin
```

Access:

- users can see AI fields on leads they can access;
- managers can trigger assessments;
- admins can configure integration and see logs;
- secrets only editable by system admin / LeadIntel admin.

## Odoo connection client

Create service:

```python
services/api_client.py
```

Responsibilities:

- sign requests;
- add headers;
- timeouts;
- retry only safe transient failures;
- raise user-friendly errors;
- never log token.

Timeouts:

```text
connect timeout: 5s
read timeout: 30s
```

Long operations must only queue work, not wait for result.

## Candidate push from SaaS into Odoo

Odoo webhook endpoint or API call to create lead:

```text
POST /leadintel/webhook/candidate-lead
```

Payload:

```json
{
  "event_id": "uuid",
  "candidate_id": "uuid",
  "name": "Tender: Freezer warehouse",
  "company_name": "...",
  "contact_name": "...",
  "email": "...",
  "phone": "...",
  "website": "...",
  "description": "...",
  "source_url": "...",
  "score_total": 84,
  "summary": "..."
}
```

Odoo creates `crm.lead` and stores `leadintel_external_candidate_id` to prevent duplicates.

## Acceptance criteria

- Module installs on clean Odoo 19 with CRM.
- Admin can configure SaaS URL and token.
- Lead can be manually synced.
- SaaS can return assessment result via webhook.
- Odoo lead shows score and summary.
- User can open dashboard link.
- No AI provider key is required in Odoo.
- If SaaS is down, Odoo create/write still works.
- Webhook replay is idempotent.
- All secrets are hidden in UI and logs.
