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
        body = json.dumps(payload, default=str).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = self._sign(
            method="POST", path=path, timestamp=timestamp, body=body, secret=webhook_secret
        )
        headers = {
            "Content-Type": "application/json",
            "X-LeadIntel-Tenant": str(instance.tenant_id),
            "X-LeadIntel-Odoo-Instance": str(instance.id),
            "X-LeadIntel-Timestamp": timestamp,
            "X-LeadIntel-Signature": signature,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, content=body, headers=headers)
            body_status = None
            body_message = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    body_status = data.get("status")
                    body_message = data.get("message")
            except ValueError:
                data = None
            http_ok = response.is_success
            # Only treat as success when Odoo confirms processing (or idempotent replay).
            ok = http_ok and body_status in {"processed", "duplicate"}
            logger.info(
                "Odoo webhook callback status=%s body_status=%s instance_id=%s",
                response.status_code,
                body_status,
                instance.id,
            )
            return {
                "ok": ok,
                "status_code": response.status_code,
                "body_status": body_status,
                "body_message": body_message,
                "url": url,
            }
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
