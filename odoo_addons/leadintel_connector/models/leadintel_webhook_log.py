# -*- coding: utf-8 -*-
from odoo import fields, models


class LeadIntelWebhookLog(models.Model):
    _name = "leadintel.webhook.log"
    _description = "LeadIntel Webhook Log"
    _order = "received_at desc"

    event_id = fields.Char(required=True, index=True)
    event_type = fields.Char()
    status = fields.Selection(
        [
            ("processed", "Processed"),
            ("duplicate", "Duplicate"),
            ("failed", "Failed"),
        ],
        required=True,
    )
    payload_json = fields.Text()
    error_message = fields.Text()
    received_at = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        ("event_id_uniq", "unique(event_id)", "Webhook event_id must be unique."),
    ]
