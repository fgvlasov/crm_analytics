# -*- coding: utf-8 -*-
"""HTTP webhook endpoints for LeadIntel SaaS → Odoo callbacks.

Uses type=http (not type=json) so external plain JSON POSTs work.
Odoo type=json routes expect a JSON-RPC envelope and often return 404 to plain JSON.
"""

import json
import logging

from odoo import fields, http
from odoo.http import request, Response

from odoo.addons.leadintel_connector.services.signature import verify_signature

_logger = logging.getLogger(__name__)


class LeadIntelWebhookController(http.Controller):
    @http.route(
        "/leadintel/webhook/assessment-result",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def assessment_result(self, **kwargs):
        """Receive assessment callbacks from SaaS. Idempotent by event_id."""
        raw_body = request.httprequest.get_data() or b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json_response({"status": "error", "message": "invalid json"}, status=400)

        if not isinstance(payload, dict):
            return self._json_response({"status": "error", "message": "payload must be object"}, status=400)

        headers = request.httprequest.headers
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
            return self._json_response(
                {"status": "error", "message": "invalid signature"}, status=401
            )

        event_id = payload.get("event_id") or ""
        if not event_id:
            return self._json_response(
                {"status": "error", "message": "event_id required"}, status=400
            )

        Log = request.env["leadintel.webhook.log"].sudo()
        existing = Log.search([("event_id", "=", event_id)], limit=1)
        if existing:
            return self._json_response({"status": "duplicate"})

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
                if payload.get("recommended_action"):
                    vals["leadintel_recommended_action"] = payload["recommended_action"]
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
                        "recommended_action": payload.get("recommended_action"),
                        "raw_json": json.dumps(payload),
                    }
                )
            else:
                _logger.warning(
                    "LeadIntel webhook: crm.lead id=%s not found", odoo_res_id
                )

            Log.create(
                {
                    "event_id": event_id,
                    "event_type": "assessment-result",
                    "status": "processed",
                    "payload_json": json.dumps(payload),
                }
            )
            return self._json_response({"status": "processed"})
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
            return self._json_response(
                {"status": "error", "message": str(exc)}, status=500
            )

    @staticmethod
    def _json_response(payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )
