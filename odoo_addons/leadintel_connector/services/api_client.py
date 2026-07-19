# -*- coding: utf-8 -*-
"""HTTP client for LeadIntel SaaS. Never logs tokens."""

import json
import logging
import time
import urllib.error
import urllib.request

from odoo.addons.leadintel_connector.services.signature import sign_payload
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LeadIntelApiClient:
    def __init__(self, env):
        self.env = env
        self.ICP = env["ir.config_parameter"].sudo()

    def _base_url(self):
        url = (self.ICP.get_param("leadintel.saas_base_url") or "").rstrip("/")
        if not url:
            raise UserError("LeadIntel SaaS Base URL is not configured.")
        return url

    def _headers(self, path, raw_body: bytes, with_auth=True):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if not with_auth:
            return headers
        token = self.ICP.get_param("leadintel.integration_token") or ""
        instance_id = self.ICP.get_param("leadintel.odoo_instance_id") or ""
        tenant = self.ICP.get_param("leadintel.tenant_id") or ""
        secret = self.ICP.get_param("leadintel.webhook_secret") or ""
        timestamp = str(int(time.time()))
        headers["Authorization"] = f"Bearer {token}"
        headers["X-LeadIntel-Odoo-Instance"] = instance_id
        if tenant:
            headers["X-LeadIntel-Tenant"] = tenant
        if secret:
            headers["X-LeadIntel-Timestamp"] = timestamp
            headers["X-LeadIntel-Signature"] = sign_payload(
                "POST", path, timestamp, raw_body, secret
            )
        return headers

    def _request(self, method, path, payload=None, with_auth=True, timeout=30):
        url = f"{self._base_url()}{path}"
        raw = json.dumps(payload or {}, default=str).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=raw if method != "GET" else None,
            headers=self._headers(path, raw, with_auth=with_auth),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            _logger.warning("LeadIntel HTTP %s on %s", exc.code, path)
            raise UserError(f"LeadIntel API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            _logger.warning("LeadIntel unreachable: %s", type(exc.reason).__name__)
            raise UserError(
                "LeadIntel SaaS is unreachable. Lead was saved locally; sync will retry."
            ) from exc

    def register_instance(self):
        payload = {
            "tenant_slug": self.ICP.get_param("leadintel.tenant_slug") or "",
            "instance_name": self.ICP.get_param("leadintel.instance_name")
            or self.env.company.name
            or "Odoo",
            "base_url": self.ICP.get_param("web.base.url") or "http://localhost:8069",
            "odoo_version": "19.0",
            "database_name": self.env.cr.dbname,
            "company_name": self.env.company.name,
            "module_version": "19.0.1.0.0",
        }
        return self._request(
            "POST",
            "/api/v1/odoo/instances/register",
            payload,
            with_auth=False,
            timeout=15,
        )

    def test_connection(self):
        instance_id = self.ICP.get_param("leadintel.odoo_instance_id")
        if not instance_id:
            return False
        try:
            # Lightweight authenticated call: list is JWT-only; use register echo via features
            # For MVP, hit public features after checking token presence.
            self._request("GET", "/api/v1/features", with_auth=False, timeout=5)
            return bool(self.ICP.get_param("leadintel.integration_token"))
        except Exception:  # noqa: BLE001
            return False

    def upsert_lead(self, payload: dict):
        return self._request("POST", "/api/v1/odoo/leads/upsert", payload, timeout=30)
