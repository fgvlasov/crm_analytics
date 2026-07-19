# 13 — Subscription and Billing Requirements

## Purpose

The SaaS should monetize through subscription plans for B2B customers.

Billing automation can be phased, but usage tracking must exist from MVP.

## Plan model

Plans should define limits:

```text
max_users
max_odoo_instances
max_ai_fast_assessments_per_month
max_ai_deep_research_per_month
max_tender_sources
max_web_sources
max_collector_runs_per_month
max_candidates_per_month
data_retention_days
byok_allowed
included_ai_credits optional
```

## Suggested plans

### Trial

```text
1 Odoo instance
3 users
100 fast assessments/month
20 deep research/month
1 tender source
2 web sources
14-day retention for raw evidence
BYOK required or limited demo provider
```

### Professional

```text
2 Odoo instances
10 users
2,000 fast assessments/month
300 deep research/month
5 tender sources
20 web sources
6-month evidence retention
BYOK allowed
```

### Enterprise

```text
custom Odoo instances
custom users
custom AI usage
custom collectors
longer retention
SLA/support
SSO later
```

## Usage enforcement

Before queuing any paid/limited job, check:

- tenant status active/trial;
- plan limit;
- provider configured;
- source enabled;
- Odoo instance enabled.

If exceeded:

```text
status = rejected
error_code = subscription_limit_exceeded
```

Do not charge/consume usage for rejected jobs.

## Usage metering events

Record events for:

```text
fast_assessment_started
fast_assessment_succeeded
deep_research_started
deep_research_succeeded
tender_item_processed
web_item_processed
candidate_created
odoo_push_succeeded
```

Which one counts against plan depends on plan policy. MVP can count successful jobs.

## BYOK vs included AI

### BYOK

Tenant pays AI provider directly. SaaS still tracks usage counts for subscription limits.

### Included AI credits

Platform pays provider. Track cost estimates and enforce credit limits.

MVP: implement BYOK first.

## Billing provider

MVP can start with manual invoicing.

Later add:

- Stripe subscriptions;
- invoice history;
- payment status webhooks;
- automatic suspension after grace period.

## Dashboard billing UI

Show:

- current plan;
- billing period;
- usage bars;
- overage warnings;
- upgrade/contact sales CTA;
- BYOK provider status.

## Admin billing UI

Super admin can:

- set tenant plan;
- override limits;
- suspend/reactivate tenant;
- view usage;
- export usage CSV.

## Grace behavior

If monthly limit exceeded:

- do not break Odoo sync;
- continue storing incoming leads;
- do not run paid AI jobs;
- show status in dashboard and Odoo assessment error if triggered.

## Acceptance criteria

- Tenant has a plan.
- Usage increments when assessment succeeds.
- Limit blocks new deep research when exceeded.
- Odoo lead sync continues even when AI limit exceeded.
- Dashboard shows current usage.
- Super admin can change plan/limits.
