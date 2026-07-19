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
        """POST assessment result to Odoo webhook. Failures are logged, not raised to callers by default."""
        path = "/leadintel/webhook/assessment-result"
        url = f"{instance.base_url.rstrip('/')}{path}"
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
            logger.info(
                "Odoo webhook callback status=%s instance_id=%s",
                response.status_code,
                instance.id,
            )
            return {"ok": response.is_success, "status_code": response.status_code}
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
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "lead_id": str(lead_id),
            "odoo_model": "crm.lead",
            "odoo_res_id": odoo_res_id,
            "assessment_type": assessment_type,
            "status": status,
            "score_total": score_total,
            "temperature": temperature,
            "summary": summary,
        }
