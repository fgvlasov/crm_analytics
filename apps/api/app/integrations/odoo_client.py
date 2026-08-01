"""HTTP client for SaaS → Odoo callbacks (Phase 2 skeleton)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID

import httpx

from app.core.logging import get_logger
from app.db.models.odoo import OdooInstance

logger = get_logger(__name__)

# Odoo Selection: hot|warm|low|cold (SaaS also uses not_relevant)
_ODOO_TEMPERATURE = {
    "hot": "hot",
    "warm": "warm",
    "low": "low",
    "cold": "cold",
    "not_relevant": "cold",
}


class OdooClient:
    def __init__(self, *, connect_timeout: float = 5.0, read_timeout: float = 30.0) -> None:
        self.timeout = httpx.Timeout(read_timeout, connect=connect_timeout)

    def _sign(
        self, *, method: str, path: str, timestamp: str, body: bytes, secret: str
    ) -> str:
        body_hash = hashlib.sha256(body).hexdigest()
        payload = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _callback_headers(
        self,
        *,
        instance: OdooInstance,
        path: str,
        body: bytes,
        webhook_secret: str,
    ) -> dict[str, str]:
        timestamp = str(int(time.time()))
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-LeadIntel-Tenant": str(instance.tenant_id),
            "X-LeadIntel-Odoo-Instance": str(instance.id),
            "X-LeadIntel-Timestamp": timestamp,
            "X-LeadIntel-Signature": self._sign(
                method="POST",
                path=path,
                timestamp=timestamp,
                body=body,
                secret=webhook_secret,
            ),
        }

    def _post_callback(
        self,
        *,
        client: httpx.Client,
        url: str,
        path: str,
        instance: OdooInstance,
        webhook_secret: str,
        wire_payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = json.dumps(wire_payload, default=str).encode("utf-8")
        response = client.post(
            url,
            content=body,
            headers=self._callback_headers(
                instance=instance,
                path=path,
                body=body,
                webhook_secret=webhook_secret,
            ),
        )
        body_status = None
        body_message = None
        try:
            data = response.json()
            if isinstance(data, dict):
                result_data = data.get("result")
                if isinstance(result_data, dict):
                    body_status = result_data.get("status")
                    body_message = result_data.get("message")
                else:
                    body_status = data.get("status")
                    body_message = data.get("message")
        except ValueError:
            pass
        return {
            "ok": response.is_success and body_status in {"processed", "duplicate"},
            "status_code": response.status_code,
            "body_status": body_status,
            "body_message": body_message,
            "url": url,
        }

    def push_assessment_result(
        self,
        *,
        instance: OdooInstance,
        webhook_secret: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST assessment result to Odoo webhook.

        Success requires HTTP 2xx AND JSON body status in {processed, duplicate}.
        """
        path = "/leadintel/webhook/assessment-result"
        url = f"{instance.base_url.rstrip('/')}{path}"
        # Multi-DB Odoo needs explicit db so the webhook hits the same database as Connect.
        if instance.database_name:
            url = f"{url}?db={instance.database_name}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                result = self._post_callback(
                    client=client,
                    url=url,
                    path=path,
                    instance=instance,
                    webhook_secret=webhook_secret,
                    wire_payload=payload,
                )
                # Older Odoo JSON routes require a JSON-RPC envelope. The event ID makes
                # this fallback safe when the first request was processed but its response
                # could not be decoded.
                needs_jsonrpc_fallback = (
                    not result["ok"]
                    and (
                        result["body_status"] is None
                        or (
                            result["body_status"] == "error"
                            and result["body_message"] == "event_id required"
                        )
                    )
                )
                if needs_jsonrpc_fallback:
                    result = self._post_callback(
                        client=client,
                        url=url,
                        path=path,
                        instance=instance,
                        webhook_secret=webhook_secret,
                        wire_payload={
                            "jsonrpc": "2.0",
                            "method": "call",
                            "params": payload,
                            "id": payload.get("event_id"),
                        },
                    )
            logger.info(
                "Odoo webhook callback status=%s body_status=%s instance_id=%s",
                result["status_code"],
                result["body_status"],
                instance.id,
            )
            return result
        except httpx.HTTPError as exc:
            logger.info(
                "Odoo webhook callback failed instance_id=%s error=%s",
                instance.id,
                type(exc).__name__,
            )
            return {"ok": False, "error": type(exc).__name__}

    def build_assessment_payload(
        self,
        *,
        event_id: str,
        lead_id: UUID,
        odoo_res_id: str,
        assessment_type: str = "fast",
        status: str = "succeeded",
        score_total: int | None = None,
        temperature: str | None = None,
        summary: str | None = None,
        recommended_action: str | None = None,
        confidence: int | None = None,
        project_type: str | None = None,
        customer_industry: str | None = None,
    ) -> dict[str, Any]:
        mapped_temp = None
        if temperature:
            mapped_temp = _ODOO_TEMPERATURE.get(temperature, temperature)
        return {
            "event_id": event_id,
            "lead_id": str(lead_id),
            "odoo_model": "crm.lead",
            "odoo_res_id": odoo_res_id,
            "assessment_type": assessment_type,
            "status": status,
            "score_total": score_total,
            "temperature": mapped_temp,
            "summary": summary,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "project_type": project_type,
            "customer_industry": customer_industry,
        }
