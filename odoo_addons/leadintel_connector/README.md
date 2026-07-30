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

## Webhook (SaaS → Odoo)

After Fast AI finishes, LeadIntel POSTs plain JSON to:

```text
POST {web.base.url}/leadintel/webhook/assessment-result
```

Headers: `X-LeadIntel-Signature`, `X-LeadIntel-Timestamp`, etc.

Requirements:

1. Module `leadintel_connector` installed and upgraded on that database
2. Parameter `web.base.url` must be the **public** Odoo URL (e.g. `https://stage-hub.coldex.fi`) — this is stored on SaaS as the Odoo instance `base_url` at Connect/Register time
3. `leadintel.webhook_secret` in Odoo must match the secret issued at registration
4. Route is `type=http` (plain JSON), not JSON-RPC

Check logs: LeadIntel → Webhook Logs. On SaaS, `odoo_callback_status` should become `ok:200`.

Quick check from any machine:

```bash
curl -i -X POST https://stage-hub.coldex.fi/leadintel/webhook/assessment-result \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"ping-1"}'
```

Expect JSON (401 invalid signature is OK if secret/HMAC missing — proves route exists). **404 means module/route not loaded or wrong host.**

## Security

Groups: User / Manager / Administrator. Secrets visible to LeadIntel Administrators only.

Odoo 19 note: groups use `privilege_id` / `res.groups.privilege` (not `category_id` on `res.groups`).
