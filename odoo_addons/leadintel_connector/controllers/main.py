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

            result_json = payload.get("result_json")
            if isinstance(result_json, dict):
                if payload.get("assessment_type") == "deep":
                    vals.update(self._deep_result_values(result_json))
                else:
                    vals.update(self._fast_result_values(result_json))
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

    @classmethod
    def _fast_result_values(cls, result):
        scoring = result.get("scoring_breakdown") or {}
        return {
            "leadintel_fast_business_fit": scoring.get("business_fit") or 0,
            "leadintel_fast_project_potential": scoring.get("project_potential") or 0,
            "leadintel_fast_customer_quality": scoring.get("customer_quality") or 0,
            "leadintel_fast_urgency": scoring.get("urgency") or 0,
            "leadintel_fast_technical_completeness": (
                scoring.get("technical_completeness") or 0
            ),
            "leadintel_fast_geography": scoring.get("geography") or 0,
            "leadintel_fast_score": result.get("score_total") or 0,
            "leadintel_fast_temperature": cls._map_temperature(result.get("temperature")),
            "leadintel_fast_confidence": result.get("confidence") or 0,
            "leadintel_fast_relevant": bool(result.get("relevant_to_customer")),
            "leadintel_fast_project_type": result.get("project_type") or False,
            "leadintel_fast_customer_industry": result.get("customer_industry") or False,
            "leadintel_fast_summary": result.get("summary") or False,
            "leadintel_fast_positive_signals": cls._format_items(
                result.get("positive_signals")
            ),
            "leadintel_fast_risks": cls._format_items(result.get("risks")),
            "leadintel_fast_missing_information": cls._format_items(
                result.get("missing_information")
            ),
            "leadintel_fast_recommended_action": (
                result.get("recommended_action") or False
            ),
            "leadintel_fast_deep_recommended": bool(
                result.get("deep_research_recommended")
            ),
        }

    @classmethod
    def _deep_result_values(cls, result):
        scoring = result.get("enhanced_scoring_breakdown") or {}
        return {
            "leadintel_deep_business_fit": scoring.get("business_fit") or 0,
            "leadintel_deep_project_potential": scoring.get("project_potential") or 0,
            "leadintel_deep_customer_quality": scoring.get("customer_quality") or 0,
            "leadintel_deep_urgency": scoring.get("urgency") or 0,
            "leadintel_deep_technical_completeness": (
                scoring.get("technical_completeness") or 0
            ),
            "leadintel_deep_geography": scoring.get("geography") or 0,
            "leadintel_deep_score": result.get("score_total") or 0,
            "leadintel_deep_temperature": cls._map_temperature(result.get("temperature")),
            "leadintel_deep_identity_confidence": (
                result.get("identity_confidence") or 0
            ),
            "leadintel_deep_commercial_confidence": (
                result.get("commercial_relevance_confidence") or 0
            ),
            "leadintel_deep_overall_confidence": (
                result.get("overall_assessment_confidence") or 0
            ),
            "leadintel_deep_company_profile": result.get("company_profile") or False,
            "leadintel_deep_contact_profile": (
                result.get("contact_professional_profile") or False
            ),
            "leadintel_deep_market_signals": cls._format_items(
                result.get("market_signals")
            ),
            "leadintel_deep_internal_relationship": (
                result.get("internal_relationship_summary") or False
            ),
            "leadintel_deep_similar_deal_ids": cls._format_items(
                result.get("similar_deal_ids")
            ),
            "leadintel_deep_risks": cls._format_items(result.get("risks")),
            "leadintel_deep_recommended_action": (
                result.get("recommended_action") or False
            ),
            "leadintel_deep_sources": cls._format_sources(result.get("sources")),
        }

    @staticmethod
    def _format_items(items):
        if not isinstance(items, list):
            return False
        values = [str(item).strip() for item in items if str(item).strip()]
        return "\n".join(f"• {item}" for item in values) or False

    @staticmethod
    def _format_sources(sources):
        if not isinstance(sources, list):
            return False
        lines = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            title = source.get("title") or source.get("source_url") or "Source"
            url = source.get("source_url") or ""
            claim = source.get("claim_supported") or ""
            confidence = source.get("confidence")
            header = f"• {title}"
            if confidence is not None:
                header += f" ({confidence}%)"
            lines.append("\n".join(part for part in (header, url, claim) if part))
        return "\n\n".join(lines) or False

    @staticmethod
    def _json_response(payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type="application/json",
        )
