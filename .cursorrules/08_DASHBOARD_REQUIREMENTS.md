# 08 — Dashboard Requirements

## Dashboard app

Use Next.js + TypeScript unless changed explicitly.

The dashboard is the main customer-facing portal.

## Main navigation

```text
Dashboard
Leads
Candidate Leads
Tender Sources
Web Sources
Odoo Integrations
AI Providers
Jobs
Usage & Billing
Settings
Admin
```

Admin visible only to super admin or tenant admin depending on context.

## Login

Pages:

```text
/login
/accept-invite
/forgot-password later
```

Login must be tenant-aware but not require tenant slug in URL for MVP. After login, user lands in selected tenant.

## Tenant switcher

If a user belongs to multiple tenants, show tenant switcher in header.

## Main dashboard page

Show cards:

```text
Hot leads this week
Warm leads this week
New external candidates
Tenders due soon
AI jobs failed
Odoo sync health
Monthly usage
```

Show charts:

- leads by temperature;
- leads by source;
- candidates by status;
- AI usage over time;
- tenders by deadline.

## Leads list

Columns:

```text
Score
Temperature
Lead name
Company
Source
Project type
Industry
Stage
Salesperson
Last assessment
Status
Actions
```

Filters:

```text
Search
Temperature
Score range
Project type
Industry
Source type
Odoo instance
Date range
Status
```

Actions:

```text
Open details
Queue fast
Queue deep
Queue full
Open in Odoo
```

## Lead detail page

Sections:

1. Header summary
2. AI score breakdown
3. Fast assessment
4. Deep research
5. Internal Odoo history
6. Sources/evidence
7. Similar deals
8. AI run history
9. Sync history

### Header summary

Show:

```text
Lead title
Company
Score / Temperature
Recommended action
Odoo link
Last updated
```

### Score breakdown

Show components:

```text
Business fit 0–30
Project potential 0–20
Customer quality 0–15
Urgency 0–15
Technical completeness 0–10
Geography 0–10
```

### Evidence

Each claim should show source if available:

```text
Source type
Title
URL
Published date
Confidence
```

## Candidate leads list

Columns:

```text
Score
Temperature
Candidate title
Company
Source type
Source name
Deadline
Confidence
Status
Actions
```

Actions:

```text
Review
Approve
Ignore
Push to Odoo
```

## Candidate detail page

Sections:

- summary;
- AI reasoning;
- evidence;
- original source item;
- tender details if tender;
- suggested Odoo fields;
- push-to-Odoo form.

Push-to-Odoo form:

```text
Odoo instance
Sales team optional
Salesperson optional
Stage optional
Create next activity bool
Activity note
```

## Odoo Integrations page

List connected Odoo instances.

For each:

```text
Name
Base URL
Status
Last seen
Last sync
Module version
Actions
```

Actions:

```text
Connect new
Test connection
Rotate token
Disable
View logs
```

Connection wizard:

1. create integration in SaaS;
2. show token and webhook secret once;
3. instruct user to paste into Odoo module;
4. test connection from Odoo or dashboard.

## AI Providers page

List providers.

Fields:

```text
Name
Provider type
Base URL
Status
Last test
Models configured
Actions
```

Provider form:

```text
Provider type
Name
Base URL
API key
Organization ID optional
Project ID optional
```

Never display saved API key.

Add button:

```text
Test Provider
```

Model profiles table:

```text
Workflow
Provider
Model name
Reasoning effort
Timeout
Default
```

## Tender Sources page

Sources table:

```text
Name
Adapter
Status
Schedule
Last run
Last success
Items found
Errors
Actions
```

Smart RPT source config form:

```text
Portal URL
Username
Password
MFA notes/manual mode
Search filters
Keywords
Regions
Categories
Schedule
Max items per run
```

Password must be write-only.

## Web Sources page

Config types:

```text
RSS feed
News site URL
Directory page
Search query
Custom source adapter
```

Fields:

```text
Name
Base URL/query
Country
Language
Keywords
Negative keywords
Schedule
Max pages per run
Allowed domains
```

## Jobs page

Show:

```text
Job type
Entity
Status
Attempts
Started
Finished
Duration
Error
Actions
```

Actions:

```text
Retry
Cancel
Open entity
```

## Usage & Billing page

Show current plan and usage:

```text
Fast assessments used / limit
Deep research used / limit
Tender sources used / limit
Web sources used / limit
Users used / limit
Odoo instances used / limit
```

Show monthly history.

## Settings page

Tenant settings:

```text
Company name
Timezone
Country
Default Odoo instance
Default AI provider
Default language
Internal domains
Lead scoring profile
Notification settings
```

## UX rules

- Always show when data is stale.
- Always show if AI result came from fast or deep run.
- Never hide failed jobs; show clear error.
- Never expose raw secrets.
- All destructive actions require confirmation.
- Pushing candidate to Odoo requires explicit user confirmation.

## Design style

Professional B2B SaaS.

Visual priorities:

- clear score badges;
- source evidence cards;
- compact tables;
- filters and saved views later;
- clean admin forms.

## Dashboard acceptance criteria

- User can login.
- User can configure OpenAI provider.
- User can see leads synced from Odoo.
- User can trigger full/deep assessment.
- User can see scoring details and sources.
- User can configure Smart RPT source.
- User can see candidate leads.
- User can push candidate to Odoo.
- Tenant user cannot see other tenant data.
