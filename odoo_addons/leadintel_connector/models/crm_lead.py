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

    # Latest Fast Assessment structured result
    leadintel_fast_business_fit = fields.Integer(string="Business Fit", copy=False, readonly=True)
    leadintel_fast_project_potential = fields.Integer(
        string="Project Potential", copy=False, readonly=True
    )
    leadintel_fast_customer_quality = fields.Integer(
        string="Customer Quality", copy=False, readonly=True
    )
    leadintel_fast_urgency = fields.Integer(string="Urgency", copy=False, readonly=True)
    leadintel_fast_technical_completeness = fields.Integer(
        string="Technical Completeness", copy=False, readonly=True
    )
    leadintel_fast_geography = fields.Integer(string="Geography", copy=False, readonly=True)
    leadintel_fast_score = fields.Integer(string="Total Score", copy=False, readonly=True)
    leadintel_fast_temperature = fields.Selection(
        [("hot", "Hot"), ("warm", "Warm"), ("low", "Low"), ("cold", "Cold")],
        string="Temperature",
        copy=False,
        readonly=True,
    )
    leadintel_fast_confidence = fields.Integer(string="Confidence", copy=False, readonly=True)
    leadintel_fast_relevant = fields.Boolean(
        string="Relevant to Customer", copy=False, readonly=True
    )
    leadintel_fast_project_type = fields.Char(string="Project Type", copy=False, readonly=True)
    leadintel_fast_customer_industry = fields.Char(
        string="Customer Industry", copy=False, readonly=True
    )
    leadintel_fast_summary = fields.Text(string="Summary", copy=False, readonly=True)
    leadintel_fast_positive_signals = fields.Text(
        string="Positive Signals", copy=False, readonly=True
    )
    leadintel_fast_risks = fields.Text(string="Risks", copy=False, readonly=True)
    leadintel_fast_missing_information = fields.Text(
        string="Missing Information", copy=False, readonly=True
    )
    leadintel_fast_recommended_action = fields.Text(
        string="Recommended Action", copy=False, readonly=True
    )
    leadintel_fast_deep_recommended = fields.Boolean(
        string="Deep Research Recommended", copy=False, readonly=True
    )

    # Latest Deep Research structured result
    leadintel_deep_business_fit = fields.Integer(string="Business Fit", copy=False, readonly=True)
    leadintel_deep_project_potential = fields.Integer(
        string="Project Potential", copy=False, readonly=True
    )
    leadintel_deep_customer_quality = fields.Integer(
        string="Customer Quality", copy=False, readonly=True
    )
    leadintel_deep_urgency = fields.Integer(string="Urgency", copy=False, readonly=True)
    leadintel_deep_technical_completeness = fields.Integer(
        string="Technical Completeness", copy=False, readonly=True
    )
    leadintel_deep_geography = fields.Integer(string="Geography", copy=False, readonly=True)
    leadintel_deep_score = fields.Integer(string="Enhanced Score", copy=False, readonly=True)
    leadintel_deep_temperature = fields.Selection(
        [("hot", "Hot"), ("warm", "Warm"), ("low", "Low"), ("cold", "Cold")],
        string="Temperature",
        copy=False,
        readonly=True,
    )
    leadintel_deep_identity_confidence = fields.Integer(
        string="Identity Confidence", copy=False, readonly=True
    )
    leadintel_deep_commercial_confidence = fields.Integer(
        string="Commercial Relevance Confidence", copy=False, readonly=True
    )
    leadintel_deep_overall_confidence = fields.Integer(
        string="Overall Assessment Confidence", copy=False, readonly=True
    )
    leadintel_deep_company_profile = fields.Text(
        string="Company Profile", copy=False, readonly=True
    )
    leadintel_deep_contact_profile = fields.Text(
        string="Contact Professional Profile", copy=False, readonly=True
    )
    leadintel_deep_market_signals = fields.Text(
        string="Market Signals", copy=False, readonly=True
    )
    leadintel_deep_internal_relationship = fields.Text(
        string="Internal Relationship Summary", copy=False, readonly=True
    )
    leadintel_deep_similar_deal_ids = fields.Text(
        string="Similar Deal IDs", copy=False, readonly=True
    )
    leadintel_deep_risks = fields.Text(string="Risks", copy=False, readonly=True)
    leadintel_deep_recommended_action = fields.Text(
        string="Recommended Action", copy=False, readonly=True
    )
    leadintel_deep_sources = fields.Text(string="Sources", copy=False, readonly=True)

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
            to_mark = self.filtered(
                lambda lead: lead.leadintel_sync_status != "pending_sync"
            )
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
