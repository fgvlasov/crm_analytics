{
    "name": "LeadIntel Connector",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Connect Odoo CRM to LeadIntel SaaS for lead sync and AI assessments",
    "description": """
LeadIntel Connector
===================
Bridges Odoo 19 CRM with the LeadIntel SaaS platform.

* Configure SaaS URL, tenant slug, integration token
* Sync CRM leads asynchronously (never blocks create/write)
* Receive assessment webhooks (HMAC-signed)
* Display AI score fields on crm.lead

Install is safe: no external HTTP calls during module installation.
""",
    "author": "Coldex / LeadIntel",
    "license": "LGPL-3",
    "depends": ["base", "crm", "mail", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/crm_lead_views.xml",
        "views/leadintel_views.xml",
        "views/menus.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
