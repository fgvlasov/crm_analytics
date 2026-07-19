# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    leadintel_enabled = fields.Boolean(
        string="Enable LeadIntel",
        config_parameter="leadintel.enabled",
    )
    leadintel_saas_base_url = fields.Char(
        string="SaaS Base URL",
        config_parameter="leadintel.saas_base_url",
    )
    leadintel_tenant_slug = fields.Char(
        string="Tenant Slug",
        config_parameter="leadintel.tenant_slug",
    )
    leadintel_instance_name = fields.Char(
        string="Odoo Instance Name",
        config_parameter="leadintel.instance_name",
    )
    leadintel_odoo_instance_id = fields.Char(
        string="LeadIntel Instance ID",
        config_parameter="leadintel.odoo_instance_id",
    )
    leadintel_integration_token = fields.Char(
        string="Integration Token",
        config_parameter="leadintel.integration_token",
    )
    leadintel_webhook_secret = fields.Char(
        string="Webhook Secret",
        config_parameter="leadintel.webhook_secret",
    )
    leadintel_sync_mode = fields.Selection(
        [("manual", "Manual"), ("automatic", "Automatic")],
        string="Sync Mode",
        default="manual",
        config_parameter="leadintel.sync_mode",
    )
    leadintel_auto_sync_new = fields.Boolean(
        string="Auto Sync New Leads",
        config_parameter="leadintel.auto_sync_new",
    )
    leadintel_auto_sync_updated = fields.Boolean(
        string="Auto Sync Updated Leads",
        config_parameter="leadintel.auto_sync_updated",
    )
    leadintel_auto_pull_results = fields.Boolean(
        string="Auto Pull Results",
        config_parameter="leadintel.auto_pull_results",
    )
    leadintel_max_messages = fields.Integer(
        string="Max Messages Per Lead",
        default=10,
        config_parameter="leadintel.max_messages",
    )

    def action_leadintel_register(self):
        """Call SaaS registration endpoint. Safe to fail without breaking settings."""
        self.ensure_one()
        from odoo.addons.leadintel_connector.services.api_client import LeadIntelApiClient

        client = LeadIntelApiClient(self.env)
        result = client.register_instance()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("leadintel.odoo_instance_id", result.get("odoo_instance_id") or "")
        ICP.set_param("leadintel.integration_token", result.get("integration_token") or "")
        ICP.set_param("leadintel.webhook_secret", result.get("webhook_secret") or "")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "LeadIntel",
                "message": "Registration successful. Tokens stored.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_leadintel_test_connection(self):
        self.ensure_one()
        from odoo.addons.leadintel_connector.services.api_client import LeadIntelApiClient

        client = LeadIntelApiClient(self.env)
        ok = client.test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "LeadIntel",
                "message": "Connection OK" if ok else "Connection failed — check URL/token",
                "type": "success" if ok else "danger",
                "sticky": False,
            },
        }
