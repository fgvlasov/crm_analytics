# -*- coding: utf-8 -*-
from odoo import fields, models


class LeadIntelSyncLog(models.Model):
    _name = "leadintel.sync.log"
    _description = "LeadIntel Sync Log"
    _order = "create_date desc"

    operation = fields.Selection(
        [
            ("sync_lead", "Sync Lead"),
            ("queue_assessment", "Queue Assessment"),
            ("webhook", "Webhook"),
            ("poll", "Poll"),
            ("push_candidate", "Push Candidate"),
        ],
        required=True,
    )
    lead_id = fields.Many2one("crm.lead", ondelete="set null")
    status = fields.Selection(
        [("success", "Success"), ("failed", "Failed")],
        required=True,
    )
    request_id = fields.Char()
    error_message = fields.Text()
    payload_hash = fields.Char()
