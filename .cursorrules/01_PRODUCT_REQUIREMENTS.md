# 01 — Product Requirements

## Product name

Working name: **LeadIntel SaaS**  
Alternative brand names can be decided later.

## Product vision

Build a subscription SaaS platform for companies using Odoo 19 that want AI-based lead qualification, tender discovery, news monitoring and commercial opportunity intelligence.

The service should not be a plugin-only feature. It must be an independent platform with its own dashboard, customer accounts, billing, API, AI provider management, collectors and Odoo integrations.

## Primary customers

Target customers:

- medium and large B2B companies;
- companies with complex sales cycles;
- companies using Odoo 19 CRM/Sales;
- companies that need tender monitoring;
- companies that want AI to evaluate incoming leads and discover external opportunities.

Initial demo/customer profile:

- Coldex Oy;
- refrigeration / cold rooms / freezer warehouses / industrial refrigeration;
- Odoo 19;
- OpenAI provider for AI analytics;
- tender sources such as Smart RPT;
- news/catalogue/industry source monitoring.

## Core value proposition

The SaaS should answer these questions:

1. Which incoming Odoo leads are worth immediate attention?
2. Why is this lead hot/warm/low/not relevant?
3. What is missing before sales can qualify it?
4. What previous deals/customers in Odoo are similar?
5. What external company/news/project signals increase opportunity potential?
6. What new external leads can be found from tenders, news and directories?
7. Which discovered opportunities should be pushed into Odoo CRM?

## Main product modules

### 1. Odoo Lead Assessment

- Receives Odoo CRM leads/opportunities.
- Runs fast AI scoring from Odoo data.
- Runs deep AI research with internal Odoo history and external sources.
- Sends assessment back to Odoo.
- Shows AI status and score in Odoo CRM.

### 2. Tender Lead Discovery

- Connects to tender portals with customer credentials.
- Logs in and collects tenders.
- Classifies tender relevance.
- Extracts deadline, buyer, location, CPV/category, documents, links and summary.
- Generates lead/opportunity candidates.
- Allows user to push selected tender leads to Odoo.

### 3. Web / News / Directory Discovery

- Monitors configured sources.
- Detects commercial signals:
  - new construction;
  - factory expansion;
  - new warehouse;
  - refrigeration/cold-chain projects;
  - industrial investment;
  - public procurement signs;
  - business expansion;
  - company growth;
  - relevant project announcements.
- Converts signals into candidate leads.

### 4. Customer Dashboard

- Multi-tenant web portal.
- Tenant admin can connect Odoo, AI providers and lead sources.
- Users can review leads, candidates, scores, sources, runs and billing.
- Role-based access.

### 5. AI Provider Management

- Each tenant may bring own AI keys.
- Supported providers:
  - OpenAI;
  - Azure OpenAI;
  - OpenAI-compatible providers;
  - Gemini later;
  - Anthropic later.
- Provider can be selected per tenant and per workflow.

### 6. Subscription / Billing

- SaaS subscription model.
- Subscription limits should support:
  - number of Odoo instances;
  - number of CRM leads assessed per month;
  - number of tender sources;
  - number of crawler sources;
  - number of users;
  - AI BYOK vs included AI credits;
  - data retention period.

## User roles

### Platform Super Admin

Owner/operator of SaaS.

Can:

- view all tenants;
- manage subscriptions;
- inspect system health;
- configure global source adapters;
- handle support;
- never view tenant secrets in plaintext.

### Tenant Owner

Customer account owner.

Can:

- manage tenant settings;
- connect Odoo instances;
- configure AI providers;
- invite users;
- configure tender and web sources;
- see billing usage.

### Tenant Admin

Can manage integrations and users but not billing owner-level actions unless granted.

### Sales Manager

Can view lead analytics, trigger assessments, approve candidate leads to Odoo.

### Sales User

Can view assigned leads and candidates, depending on tenant policy.

### Analyst

Can manage source monitoring and review external findings.

### Read-only Auditor

Can view reports and audit logs but cannot run actions.

## MVP scope

The MVP must include:

1. SaaS backend with tenants and auth.
2. Odoo 19 integration module.
3. Odoo lead sync to SaaS.
4. Fast AI lead scoring.
5. Deep AI assessment with web research.
6. Dashboard showing lead assessments.
7. Tenant AI provider settings with OpenAI support.
8. Smart RPT collector adapter prototype.
9. Web/news source collector prototype.
10. Push candidate lead to Odoo.
11. Audit logs.
12. Docker Compose deployment.

## Explicit non-goals for MVP

Do not implement in MVP:

- full billing automation with invoices if it delays core product;
- complex CRM pipeline replacement;
- email campaign sending;
- autonomous write actions in client Odoo without human approval;
- scraping any source in a way that ignores customer credentials or portal terms;
- personal/private social media profiling.

## Success criteria

MVP is successful when:

- Coldex can connect its Odoo 19 staging instance;
- Coldex can connect OpenAI credentials;
- a new Odoo lead is scored and visible in both SaaS and Odoo;
- Smart RPT test login can collect at least one tender listing into candidate leads;
- a configured news/source page can produce at least one candidate signal;
- a user can approve a candidate and create/update an Odoo CRM lead;
- all AI decisions include score breakdown, evidence and sources;
- tenant isolation tests pass.
