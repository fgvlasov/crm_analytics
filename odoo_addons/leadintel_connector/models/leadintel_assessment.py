# -*- coding: utf-8 -*-
from odoo import fields, models


class LeadIntelAssessment(models.Model):
    _name = "leadintel.assessment"
    _description = "LeadIntel Assessment Snapshot"
    _order = "received_at desc, id desc"

    lead_id = fields.Many2one("crm.lead", required=True, ondelete="cascade", index=True)
    leadintel_assessment_id = fields.Char(index=True)
    assessment_type = fields.Selection(
        [("fast", "Fast"), ("deep", "Deep")],
        required=True,
        default="fast",
    )
    status = fields.Selection(
        [
            ("queued", "Queued"),
            ("running", "Running"),
            ("succeeded", "Succeeded"),
            ("failed", "Failed"),
        ],
        default="succeeded",
    )
    score_total = fields.Integer()
    temperature = fields.Selection(
        [("hot", "Hot"), ("warm", "Warm"), ("low", "Low"), ("cold", "Cold")]
    )
    confidence = fields.Integer()
    summary = fields.Text()
    recommended_action = fields.Text()
    raw_json = fields.Text()
    received_at = fields.Datetime(default=fields.Datetime.now)
