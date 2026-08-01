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

# SaaS may send "not_relevant"; Odoo Selection only has hot/warm/low/cold.
_TEMPERATURE_MAP = {
    "hot": "hot",
    "warm": "warm",
    "low": "low",
    "cold": "cold",
    "not_relevant": "cold",
}


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
        raw_body = request.httprequest.get_data(cache=True) or b"{}"
        try:
            wire_payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json_response({"status": "error", "message": "invalid json"}, status=400)

        if not isinstance(wire_payload, dict):
            return self._json_response({"status": "error", "message": "payload must be object"}, status=400)

        # Accept both direct JSON and a JSON-RPC envelope used by older Odoo JSON routes.
        params = wire_payload.get("params")
        payload = params if isinstance(params, dict) else wire_payload

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
            return self._json_response({"status": "duplicate", "event_id": event_id})

        try:
            odoo_res_id = int(payload.get("odoo_res_id") or 0)
            lead = request.env["crm.lead"].sudo().browse(odoo_res_id)
            if not lead.exists():
                _logger.warning(
                    "LeadIntel webhook: crm.lead id=%s not found (db=%s)",
                    odoo_res_id,
                    request.env.cr.dbname,
                )
                Log.create(
                    {
                        "event_id": event_id,
                        "event_type": "assessment-result",
                        "status": "failed",
                        "payload_json": json.dumps(payload),
                        "error_message": f"crm.lead {odoo_res_id} not found",
                    }
                )
                return self._json_response(
                    {
                        "status": "error",
                        "message": f"crm.lead {odoo_res_id} not found",
                        "odoo_res_id": odoo_res_id,
                    },
                    status=404,
                )

            temperature = self._map_temperature(payload.get("temperature"))
            vals = {
                "leadintel_assessment_status": payload.get("status") or "succeeded",
                "leadintel_last_assessment_at": fields.Datetime.now(),
                "leadintel_error_message": False,
            }
            if payload.get("score_total") is not None:
                vals["leadintel_score"] = int(payload["score_total"])
            if temperature:
                vals["leadintel_temperature"] = temperature
            if payload.get("summary"):
                vals["leadintel_summary"] = payload["summary"]
            if payload.get("recommended_action"):
                vals["leadintel_recommended_action"] = payload["recommended_action"]
            if payload.get("confidence") is not None:
                vals["leadintel_confidence"] = int(payload["confidence"])
            if payload.get("project_type"):
                vals["leadintel_project_type"] = payload["project_type"]
            if payload.get("customer_industry"):
                vals["leadintel_customer_industry"] = payload["customer_industry"]
            lead.write(vals)
            request.env["leadintel.assessment"].sudo().create(
                {
                    "lead_id": lead.id,
                    "leadintel_assessment_id": event_id,
                    "assessment_type": payload.get("assessment_type") or "fast",
                    "status": payload.get("status") or "succeeded",
                    "score_total": payload.get("score_total"),
                    "temperature": temperature,
                    "confidence": payload.get("confidence"),
                    "summary": payload.get("summary"),
                    "recommended_action": payload.get("recommended_action"),
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
            return self._json_response(
                {"status": "processed", "odoo_res_id": lead.id, "lead_name": lead.name}
            )
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
    def _map_temperature(value):
        if not value:
            return False
        return _TEMPERATURE_MAP.get(str(value).strip().lower()) or False

    @staticmethod
    def _json_response(payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )
