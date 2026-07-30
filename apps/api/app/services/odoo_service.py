import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models.odoo import (
    Lead,
    LeadSourceType,
    LeadStatus,
    OdooIdempotencyRecord,
    OdooInstance,
    OdooInstanceStatus,
    hash_integration_token,
)
from app.db.models.tenant import Tenant
from app.schemas.odoo import (
    OdooInstanceCreateRequest,
    OdooLeadUpsertRequest,
    OdooRegisterRequest,
)
from app.services.secret_service import SecretService


def _canonical_domain(email: str | None, website: str | None) -> str | None:
    if email and "@" in email:
        return email.split("@", 1)[1].lower().strip()
    if website:
        raw = website if "://" in website else f"https://{website}"
        host = urlparse(raw).hostname
        if host:
            return host.lower().removeprefix("www.")
    return None


class OdooService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.secrets = SecretService(db, settings)

    def _new_token(self) -> str:
        return secrets.token_urlsafe(32)

    def register_from_odoo(self, body: OdooRegisterRequest) -> tuple[OdooInstance, str, str]:
        tenant = self.db.scalar(select(Tenant).where(Tenant.slug == body.tenant_slug))
        if tenant is None:
            raise AppError("Tenant not found", code="tenant_not_found", status_code=404)

        existing = self.db.scalar(
            select(OdooInstance).where(
                OdooInstance.tenant_id == tenant.id,
                OdooInstance.base_url == body.base_url.rstrip("/"),
                OdooInstance.name == body.instance_name,
            )
        )
        token = self._new_token()
        webhook_secret = self._new_token()
        if existing is not None:
            instance = existing
            instance.odoo_version = body.odoo_version
            instance.database_name = body.database_name
            instance.company_name = body.company_name
            instance.module_version = body.module_version
            instance.api_token_hash = hash_integration_token(token)
            instance.webhook_secret_encrypted = self.secrets.encrypt(webhook_secret)
            instance.status = OdooInstanceStatus.connected
            instance.last_seen_at = datetime.now(UTC)
            instance.last_error = None
        else:
            instance = OdooInstance(
                tenant_id=tenant.id,
                name=body.instance_name,
                base_url=body.base_url.rstrip("/"),
                odoo_version=body.odoo_version,
                database_name=body.database_name,
                company_name=body.company_name,
                module_version=body.module_version,
                api_token_hash=hash_integration_token(token),
                webhook_secret_encrypted=self.secrets.encrypt(webhook_secret),
                status=OdooInstanceStatus.connected,
                last_seen_at=datetime.now(UTC),
            )
            self.db.add(instance)

        self.db.commit()
        self.db.refresh(instance)
        return instance, token, webhook_secret

    def create_for_tenant(
        self, *, tenant_id: UUID, body: OdooInstanceCreateRequest
    ) -> tuple[OdooInstance, str, str]:
        token = self._new_token()
        webhook_secret = self._new_token()
        instance = OdooInstance(
            tenant_id=tenant_id,
            name=body.name,
            base_url=body.base_url.rstrip("/"),
            odoo_version=body.odoo_version,
            database_name=body.database_name,
            company_name=body.company_name,
            api_token_hash=hash_integration_token(token),
            webhook_secret_encrypted=self.secrets.encrypt(webhook_secret),
            status=OdooInstanceStatus.connected,
            last_seen_at=datetime.now(UTC),
        )
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance, token, webhook_secret

    def list_for_tenant(self, tenant_id: UUID) -> list[OdooInstance]:
        return list(
            self.db.scalars(
                select(OdooInstance)
                .where(OdooInstance.tenant_id == tenant_id)
                .order_by(OdooInstance.created_at.desc())
            ).all()
        )

    def get_for_tenant(self, tenant_id: UUID, instance_id: UUID) -> OdooInstance | None:
        return self.db.scalar(
            select(OdooInstance).where(
                OdooInstance.id == instance_id,
                OdooInstance.tenant_id == tenant_id,
            )
        )

    def authenticate_instance(
        self,
        *,
        instance_id: UUID,
        bearer_token: str,
        tenant_id: UUID | None = None,
    ) -> OdooInstance:
        instance = self.db.get(OdooInstance, instance_id)
        if instance is None:
            raise AppError("Odoo instance not found", code="odoo_not_found", status_code=404)
        if tenant_id is not None and instance.tenant_id != tenant_id:
            raise AppError("Odoo instance not found", code="odoo_not_found", status_code=404)
        if instance.status == OdooInstanceStatus.disabled:
            raise AppError("Odoo instance disabled", code="odoo_disabled", status_code=403)
        if not instance.api_token_hash or instance.api_token_hash != hash_integration_token(
            bearer_token
        ):
            raise AppError("Invalid integration token", code="invalid_token", status_code=401)
        instance.last_seen_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def _idempotent_get(self, tenant_id: UUID, scope: str, key: str) -> dict[str, Any] | None:
        row = self.db.scalar(
            select(OdooIdempotencyRecord).where(
                OdooIdempotencyRecord.tenant_id == tenant_id,
                OdooIdempotencyRecord.scope == scope,
                OdooIdempotencyRecord.key == key,
            )
        )
        if row is None or not row.response_json:
            return None
        return json.loads(row.response_json)

    def _idempotent_save(
        self, tenant_id: UUID, scope: str, key: str, response: dict[str, Any]
    ) -> None:
        existing = self.db.scalar(
            select(OdooIdempotencyRecord).where(
                OdooIdempotencyRecord.tenant_id == tenant_id,
                OdooIdempotencyRecord.scope == scope,
                OdooIdempotencyRecord.key == key,
            )
        )
        payload = json.dumps(response, default=str)
        if existing is None:
            self.db.add(
                OdooIdempotencyRecord(
                    tenant_id=tenant_id,
                    scope=scope,
                    key=key,
                    response_json=payload,
                )
            )
        else:
            existing.response_json = payload
        self.db.commit()

    def upsert_lead(
        self, *, instance: OdooInstance, body: OdooLeadUpsertRequest
    ) -> tuple[Lead, bool, dict[str, Any]]:
        cached = self._idempotent_get(instance.tenant_id, "lead_upsert", body.idempotency_key)
        if cached is not None:
            lead = self.db.get(Lead, UUID(cached["lead_id"]))
            if lead is not None:
                return lead, False, cached

        if body.odoo_instance_id != instance.id:
            raise AppError(
                "odoo_instance_id mismatch",
                code="instance_mismatch",
                status_code=400,
            )

        lead = self.db.scalar(
            select(Lead).where(
                Lead.tenant_id == instance.tenant_id,
                Lead.odoo_instance_id == instance.id,
                Lead.odoo_model == body.model,
                Lead.odoo_res_id == body.res_id,
            )
        )
        created = lead is None
        payload = body.model_dump(mode="json")
        email = str(body.lead.email) if body.lead.email else None
        fields = {
            "name": body.lead.name,
            "company_name": body.lead.company_name,
            "contact_name": body.lead.contact_name,
            "email": email,
            "phone": body.lead.phone,
            "website": body.lead.website,
            "country_code": body.lead.country_code,
            "city": body.lead.city,
            "description": body.lead.description,
            "expected_revenue": body.lead.expected_revenue,
            "stage_name": body.lead.stage_name,
            "salesperson_name": body.lead.salesperson_name,
            "team_name": body.lead.team_name,
            "odoo_write_date": body.write_date,
            "canonical_company_domain": _canonical_domain(email, body.lead.website),
            "raw_payload_json": json.dumps(payload, default=str),
            "last_idempotency_key": body.idempotency_key,
            "sync_status": "synced",
            "status": LeadStatus.active,
            "source_type": LeadSourceType.odoo,
        }
        if created:
            lead = Lead(
                tenant_id=instance.tenant_id,
                odoo_instance_id=instance.id,
                odoo_model=body.model,
                odoo_res_id=body.res_id,
                **fields,
            )
            self.db.add(lead)
        else:
            assert lead is not None
            for key, value in fields.items():
                setattr(lead, key, value)

        instance.last_sync_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(lead)

        queued_jobs: list[str] = []
        if self.settings.feature_fast_ai:
            from app.services.assessment_service import AssessmentService

            job = AssessmentService(self.db, self.settings).queue_fast(
                tenant_id=instance.tenant_id,
                lead_id=lead.id,
                force=False,
            )
            queued_jobs.append(str(job.id))

        response = {
            "lead_id": str(lead.id),
            "status": "accepted",
            "queued_jobs": queued_jobs,
            "created": created,
        }
        self._idempotent_save(instance.tenant_id, "lead_upsert", body.idempotency_key, response)
        return lead, created, response

    def list_leads(
        self,
        tenant_id: UUID,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Lead], int]:
        q = select(Lead).where(Lead.tenant_id == tenant_id)
        count_q = select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant_id)
        if search:
            like = f"%{search}%"
            filt = (
                (Lead.name.ilike(like))
                | (Lead.company_name.ilike(like))
                | (Lead.email.ilike(like))
            )
            q = q.where(filt)
            count_q = count_q.where(filt)
        total = int(self.db.scalar(count_q) or 0)
        items = list(
            self.db.scalars(q.order_by(Lead.updated_at.desc()).limit(limit).offset(offset)).all()
        )
        return items, total

    def get_lead(self, tenant_id: UUID, lead_id: UUID) -> Lead | None:
        return self.db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )

    def dashboard_summary(self, tenant_id: UUID) -> dict[str, int]:
        leads_total = int(
            self.db.scalar(select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant_id))
            or 0
        )
        leads_odoo = int(
            self.db.scalar(
                select(func.count())
                .select_from(Lead)
                .where(Lead.tenant_id == tenant_id, Lead.source_type == LeadSourceType.odoo)
            )
            or 0
        )
        odoo_total = int(
            self.db.scalar(
                select(func.count())
                .select_from(OdooInstance)
                .where(OdooInstance.tenant_id == tenant_id)
            )
            or 0
        )
        odoo_connected = int(
            self.db.scalar(
                select(func.count())
                .select_from(OdooInstance)
                .where(
                    OdooInstance.tenant_id == tenant_id,
                    OdooInstance.status == OdooInstanceStatus.connected,
                )
            )
            or 0
        )
        return {
            "leads_total": leads_total,
            "leads_from_odoo": leads_odoo,
            "odoo_instances": odoo_total,
            "odoo_connected": odoo_connected,
        }

    def get_webhook_secret(self, instance: OdooInstance) -> str:
        if not instance.webhook_secret_encrypted:
            raise AppError("Webhook secret missing", code="webhook_secret_missing", status_code=500)
        return self.secrets.decrypt(instance.webhook_secret_encrypted)


def verify_odoo_request_signature(
    *,
    method: str,
    path: str,
    timestamp: str,
    raw_body: bytes,
    signature: str,
    secret: str,
    max_skew_seconds: int = 300,
) -> None:
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise AppError("Invalid timestamp", code="invalid_timestamp", status_code=401) from exc
    now = int(time.time())
    if abs(now - ts) > max_skew_seconds:
        raise AppError("Timestamp drift too large", code="timestamp_skew", status_code=401)

    body_hash = hashlib.sha256(raw_body).hexdigest()
    payload = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AppError("Invalid signature", code="invalid_signature", status_code=401)
