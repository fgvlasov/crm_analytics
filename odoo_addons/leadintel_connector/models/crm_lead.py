# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    leadintel_external_id = fields.Char(index=True, copy=False)
    leadintel_last_sync_at = fields.Datetime(copy=False)
    leadintel_last_assessment_at = fields.Datetime(copy=False)
    leadintel_sync_status = fields.Selection(
        [
            ("idle", "Idle"),
            ("pending_sync", "Pending Sync"),
            ("syncing", "Syncing"),
            ("synced", "Synced"),
            ("error", "Error"),
        ],
        default="idle",
        copy=False,
    )
    leadintel_assessment_status = fields.Selection(
        [
            ("none", "None"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("succeeded", "Succeeded"),
            ("failed", "Failed"),
        ],
        default="none",
        copy=False,
    )
    leadintel_score = fields.Integer(copy=False)
    leadintel_temperature = fields.Selection(
        [("hot", "Hot"), ("warm", "Warm"), ("low", "Low"), ("cold", "Cold")],
        copy=False,
    )
    leadintel_confidence = fields.Integer(copy=False)
    leadintel_project_type = fields.Char(copy=False)
    leadintel_customer_industry = fields.Char(copy=False)
    leadintel_summary = fields.Text(copy=False)
    leadintel_recommended_action = fields.Text(copy=False)
    leadintel_dashboard_url = fields.Char(copy=False)
    leadintel_error_message = fields.Text(copy=False)
    leadintel_assessment_ids = fields.One2many(
        "leadintel.assessment", "lead_id", string="LeadIntel Assessments"
    )

    def action_leadintel_sync(self):
        """Mark for async sync — never call SaaS inside create/write."""
        for lead in self:
            lead.leadintel_sync_status = "pending_sync"
            lead.leadintel_error_message = False
        return True

    def action_leadintel_fast_assessment(self):
        self.action_leadintel_sync()
        self.leadintel_assessment_status = "queued"
        return True

    def action_leadintel_deep_research(self):
        self.action_leadintel_sync()
        self.leadintel_assessment_status = "queued"
        return True

    def action_open_leadintel_dashboard(self):
        self.ensure_one()
        url = self.leadintel_dashboard_url
        if not url:
            base = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("leadintel.saas_base_url", "http://localhost:3000")
            )
            url = base.rstrip("/")
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("leadintel.enabled") == "True" and ICP.get_param(
            "leadintel.auto_sync_new"
        ) in ("True", "true", "1"):
            # Do not call SaaS here — only mark pending for cron.
            leads.write({"leadintel_sync_status": "pending_sync"})
        return leads

    def write(self, vals):
        res = super().write(vals)
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("leadintel.enabled") != "True":
            return res
        if ICP.get_param("leadintel.auto_sync_updated") not in ("True", "true", "1"):
            return res
        tracked = {
            "name",
            "partner_id",
            "email_from",
            "phone",
            "description",
            "stage_id",
            "expected_revenue",
        }
        if tracked.intersection(vals.keys()):
            # Never block write with HTTP — cron will sync.
            to_mark = self.filtered(lambda l: l.leadintel_sync_status != "pending_sync")
            if to_mark:
                super(CrmLead, to_mark).write({"leadintel_sync_status": "pending_sync"})
        return res

    @api.model
    def _cron_leadintel_sync_pending(self):
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("leadintel.enabled") != "True":
            return
        leads = self.search([("leadintel_sync_status", "=", "pending_sync")], limit=50)
        from odoo.addons.leadintel_connector.services.api_client import LeadIntelApiClient
        from odoo.addons.leadintel_connector.services.payload_builder import build_lead_payload

        client = LeadIntelApiClient(self.env)
        for lead in leads:
            try:
                lead.leadintel_sync_status = "syncing"
                payload = build_lead_payload(lead)
                result = client.upsert_lead(payload)
                lead.write(
                    {
                        "leadintel_sync_status": "synced",
                        "leadintel_last_sync_at": fields.Datetime.now(),
                        "leadintel_external_id": result.get("lead_id"),
                        "leadintel_error_message": False,
                        "leadintel_dashboard_url": (
                            f"{(ICP.get_param('leadintel.saas_base_url') or '').rstrip('/')}"
                            f"/#leads/{result.get('lead_id')}"
                            if result.get("lead_id")
                            else False
                        ),
                    }
                )
                self.env["leadintel.sync.log"].sudo().create(
                    {
                        "operation": "sync_lead",
                        "lead_id": lead.id,
                        "status": "success",
                        "request_id": result.get("lead_id"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 — cron must not abort batch
                lead.write(
                    {
                        "leadintel_sync_status": "error",
                        "leadintel_error_message": str(exc)[:2000],
                    }
                )
                self.env["leadintel.sync.log"].sudo().create(
                    {
                        "operation": "sync_lead",
                        "lead_id": lead.id,
                        "status": "failed",
                        "error_message": str(exc)[:2000],
                    }
                )
