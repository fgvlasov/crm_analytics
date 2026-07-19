# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, http
from odoo.http import request

from odoo.addons.leadintel_connector.services.signature import verify_signature

_logger = logging.getLogger(__name__)


class LeadIntelWebhookController(http.Controller):
    @http.route(
        "/leadintel/webhook/assessment-result",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def assessment_result(self, **kwargs):
        """Receive assessment callbacks from SaaS. Idempotent by event_id."""
        # Odoo type=json puts payload in kwargs / request.jsonrequest
        payload = request.jsonrequest if hasattr(request, "jsonrequest") else kwargs
        if not isinstance(payload, dict):
            payload = {}

        # Prefer raw body for HMAC when available
        raw = getattr(request, "httprequest", None)
        raw_body = raw.get_data() if raw is not None else json.dumps(payload).encode("utf-8")
        headers = raw.headers if raw is not None else {}
        signature = headers.get("X-LeadIntel-Signature", "")
        timestamp = headers.get("X-LeadIntel-Timestamp", "")
        secret = (
            request.env["ir.config_parameter"].sudo().get_param("leadintel.webhook_secret") or ""
        )

        if secret and not verify_signature(
            "POST",
            "/leadintel/webhook/assessment-result",
            timestamp,
            raw_body,
            signature,
            secret,
        ):
            return {"status": "error", "message": "invalid signature"}

        event_id = payload.get("event_id") or ""
        if not event_id:
            return {"status": "error", "message": "event_id required"}

        Log = request.env["leadintel.webhook.log"].sudo()
        existing = Log.search([("event_id", "=", event_id)], limit=1)
        if existing:
            return {"status": "duplicate"}

        try:
            odoo_res_id = int(payload.get("odoo_res_id") or 0)
            lead = request.env["crm.lead"].sudo().browse(odoo_res_id)
            if lead.exists():
                vals = {
                    "leadintel_assessment_status": payload.get("status") or "succeeded",
                    "leadintel_last_assessment_at": fields.Datetime.now(),
                }
                if payload.get("score_total") is not None:
                    vals["leadintel_score"] = int(payload["score_total"])
                if payload.get("temperature"):
                    vals["leadintel_temperature"] = payload["temperature"]
                if payload.get("summary"):
                    vals["leadintel_summary"] = payload["summary"]
                lead.write(vals)
                request.env["leadintel.assessment"].sudo().create(
                    {
                        "lead_id": lead.id,
                        "leadintel_assessment_id": event_id,
                        "assessment_type": payload.get("assessment_type") or "fast",
                        "status": payload.get("status") or "succeeded",
                        "score_total": payload.get("score_total"),
                        "temperature": payload.get("temperature"),
                        "summary": payload.get("summary"),
                        "raw_json": json.dumps(payload),
                    }
                )
            Log.create(
                {
                    "event_id": event_id,
                    "event_type": "assessment-result",
                    "status": "processed",
                    "payload_json": json.dumps(payload),
                }
            )
            return {"status": "processed"}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("LeadIntel webhook failed")
            Log.create(
                {
                    "event_id": event_id,
                    "event_type": "assessment-result",
                    "status": "failed",
                    "payload_json": json.dumps(payload),
                    "error_message": str(exc)[:2000],
                }
            )
            return {"status": "error", "message": str(exc)}
