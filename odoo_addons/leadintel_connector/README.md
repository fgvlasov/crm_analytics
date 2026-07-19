# LeadIntel Connector (Odoo 19)

Integrates Odoo CRM with LeadIntel SaaS.

## Install

1. Copy `odoo_addons/leadintel_connector` into your Odoo addons path.
2. Update Apps list and install **LeadIntel Connector**.
3. No external HTTP calls run during install.

## Configure

Settings → LeadIntel:

1. Set SaaS Base URL (e.g. `http://host.docker.internal:8000`)
2. Set Tenant Slug (`coldex-demo`)
3. Set Instance Name
4. Click **Connect / Register** (requires `FEATURE_ODOO_CONNECTOR=true` on SaaS)
5. Tokens are stored in `ir.config_parameter`
6. Enable LeadIntel and choose sync mode

## Sync behaviour

- Lead create/write never blocks on SaaS.
- Leads are marked `pending_sync`; cron syncs every 2 minutes.
- Manual **LeadIntel Sync** button on the lead form.

## Webhook

`POST /leadintel/webhook/assessment-result` — HMAC verified, idempotent by `event_id`.

## Security

Groups: User / Manager / Administrator. Secrets visible to LeadIntel Administrators only.
