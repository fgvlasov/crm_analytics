"""Fast Lead Assessment orchestration: queue, fingerprint skip, validate, persist, Odoo callback."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models.ai import (
    AssessmentJob,
    AssessmentStatus,
    AssessmentWorkflow,
    JobStatus,
    LeadAssessment,
)
from app.db.models.odoo import Lead
from app.integrations.odoo_client import OdooClient
from app.services.ai_clients import build_client
from app.services.ai_provider_service import AiProviderService
from app.services.ai_schemas import (
    FAST_ASSESSMENT_SYSTEM_PROMPT,
    fast_input_fingerprint,
    validate_and_finalize,
)
from app.services.odoo_service import OdooService

logger = get_logger(__name__)


class AssessmentService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.providers = AiProviderService(db, settings)

    def _lead_payload(self, lead: Lead) -> dict[str, Any]:
        messages: list[Any] = []
        attachments: list[Any] = []
        if lead.raw_payload_json:
            try:
                raw = json.loads(lead.raw_payload_json)
                messages = raw.get("messages") or []
                attachments = raw.get("attachments") or []
            except json.JSONDecodeError:
                pass
        return {
            "name": lead.name,
            "company_name": lead.company_name,
            "contact_name": lead.contact_name,
            "email": lead.email,
            "phone": lead.phone,
            "website": lead.website,
            "country_code": lead.country_code,
            "city": lead.city,
            "description": (lead.description or "")[:10000],
            "expected_revenue": str(lead.expected_revenue) if lead.expected_revenue else None,
            "stage_name": lead.stage_name,
            "messages": messages[:10],
            "attachments": attachments[:20],
        }

    def queue_fast(
        self,
        *,
        tenant_id: UUID,
        lead_id: UUID,
        force: bool = False,
        provider_id: UUID | None = None,
    ) -> AssessmentJob:
        if not self.settings.feature_fast_ai:
            raise AppError(
                "FEATURE_FAST_AI is disabled",
                code="feature_disabled",
                status_code=403,
                details={"feature": "fast_ai"},
            )

        lead = self.db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        if lead is None:
            raise AppError("Lead not found", code="lead_not_found", status_code=404)

        provider = None
        if provider_id:
            provider = self.providers.get_for_tenant(tenant_id, provider_id)
            if provider is None:
                raise AppError("Provider not found", code="provider_not_found", status_code=404)
        else:
            provider = self.providers.ensure_mock_default(tenant_id)

        fingerprint = fast_input_fingerprint(self._lead_payload(lead))
        idempotency_key = f"fast:{lead.id}:{fingerprint}:{int(force)}"

        existing = self.db.scalar(
            select(AssessmentJob).where(
                AssessmentJob.tenant_id == tenant_id,
                AssessmentJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        # Skip provider call for unchanged input unless forced — reuse succeeded assessment.
        if not force:
            prior = self.db.scalar(
                select(LeadAssessment)
                .where(
                    LeadAssessment.tenant_id == tenant_id,
                    LeadAssessment.lead_id == lead_id,
                    LeadAssessment.workflow == AssessmentWorkflow.fast_lead_assessment,
                    LeadAssessment.status == AssessmentStatus.succeeded,
                    LeadAssessment.input_fingerprint == fingerprint,
                )
                .order_by(LeadAssessment.created_at.desc())
            )
            if prior is not None:
                job = AssessmentJob(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    provider_id=provider.id,
                    workflow=AssessmentWorkflow.fast_lead_assessment,
                    status=JobStatus.succeeded,
                    force=False,
                    input_fingerprint=fingerprint,
                    idempotency_key=idempotency_key,
                    assessment_id=prior.id,
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                )
                self.db.add(job)
                self.db.commit()
                self.db.refresh(job)
                return job

        job = AssessmentJob(
            tenant_id=tenant_id,
            lead_id=lead_id,
            provider_id=provider.id,
            workflow=AssessmentWorkflow.fast_lead_assessment,
            status=JobStatus.queued,
            force=force,
            input_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        lead.latest_assessment_status = "queued"
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, tenant_id: UUID, *, limit: int = 50) -> list[AssessmentJob]:
        return list(
            self.db.scalars(
                select(AssessmentJob)
                .where(AssessmentJob.tenant_id == tenant_id)
                .order_by(AssessmentJob.created_at.desc())
                .limit(limit)
            ).all()
        )

    def get_job(self, tenant_id: UUID, job_id: UUID) -> AssessmentJob | None:
        return self.db.scalar(
            select(AssessmentJob).where(
                AssessmentJob.id == job_id, AssessmentJob.tenant_id == tenant_id
            )
        )

    def list_assessments(self, tenant_id: UUID, lead_id: UUID) -> list[LeadAssessment]:
        return list(
            self.db.scalars(
                select(LeadAssessment)
                .where(
                    LeadAssessment.tenant_id == tenant_id,
                    LeadAssessment.lead_id == lead_id,
                )
                .order_by(LeadAssessment.created_at.desc())
            ).all()
        )

    def latest_assessment(self, tenant_id: UUID, lead_id: UUID) -> LeadAssessment | None:
        return self.db.scalar(
            select(LeadAssessment)
            .where(
                LeadAssessment.tenant_id == tenant_id,
                LeadAssessment.lead_id == lead_id,
                LeadAssessment.workflow == AssessmentWorkflow.fast_lead_assessment,
            )
            .order_by(LeadAssessment.created_at.desc())
        )

    def claim_next_queued_job(self) -> AssessmentJob | None:
        """Worker helper: claim one queued fast job."""
        job = self.db.scalar(
            select(AssessmentJob)
            .where(
                AssessmentJob.status == JobStatus.queued,
                AssessmentJob.workflow == AssessmentWorkflow.fast_lead_assessment,
            )
            .order_by(AssessmentJob.created_at.asc())
            .limit(1)
        )
        if job is None:
            return None
        job.status = JobStatus.running
        job.started_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(job)
        return job

    def process_job(self, job_id: UUID) -> LeadAssessment:
        job = self.db.get(AssessmentJob, job_id)
        if job is None:
            raise AppError("Job not found", code="job_not_found", status_code=404)

        lead = self.db.get(Lead, job.lead_id)
        if lead is None:
            job.status = JobStatus.failed
            job.error_message = "Lead missing"
            job.finished_at = datetime.now(UTC)
            self.db.commit()
            raise AppError("Lead not found", code="lead_not_found", status_code=404)

        provider = None
        if job.provider_id:
            provider = self.providers.get_for_tenant(job.tenant_id, job.provider_id)
        if provider is None:
            provider = self.providers.ensure_mock_default(job.tenant_id)

        payload = self._lead_payload(lead)
        user_prompt = (
            "Score this B2B CRM lead. Respond with JSON only.\n"
            f"LEAD_DATA:\n{json.dumps(payload, default=str)}"
        )

        try:
            client = build_client(
                provider_type=provider.provider_type.value,
                api_key=self.providers.reveal_api_key(provider),
                base_url=provider.base_url,
            )
            raw = client.complete_json(
                system=FAST_ASSESSMENT_SYSTEM_PROMPT,
                user=user_prompt,
                model=provider.default_model,
            )
            result = validate_and_finalize(raw)
        except Exception as exc:  # noqa: BLE001 — failed runs must be stored, not corrupt data
            logger.info("Fast assessment failed job_id=%s error=%s", job.id, type(exc).__name__)
            failed = LeadAssessment(
                tenant_id=job.tenant_id,
                lead_id=lead.id,
                job_id=job.id,
                provider_id=provider.id,
                workflow=AssessmentWorkflow.fast_lead_assessment,
                status=AssessmentStatus.failed,
                model_name=provider.default_model,
                input_fingerprint=job.input_fingerprint,
                error_message=str(exc)[:2000],
            )
            job.status = JobStatus.failed
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            lead.latest_assessment_status = "failed"
            self.db.add(failed)
            self.db.commit()
            self.db.refresh(failed)
            return failed

        assessment = LeadAssessment(
            tenant_id=job.tenant_id,
            lead_id=lead.id,
            job_id=job.id,
            provider_id=provider.id,
            workflow=AssessmentWorkflow.fast_lead_assessment,
            status=AssessmentStatus.succeeded,
            model_name=provider.default_model,
            input_fingerprint=job.input_fingerprint,
            score_total=result.score_total,
            temperature=result.temperature,
            confidence=result.confidence,
            project_type=result.project_type,
            customer_industry=result.customer_industry,
            summary=result.summary,
            recommended_action=result.recommended_action,
            deep_research_recommended=result.deep_research_recommended,
            result_json=result.model_dump_json(),
        )
        self.db.add(assessment)
        self.db.flush()

        job.status = JobStatus.succeeded
        job.assessment_id = assessment.id
        job.finished_at = datetime.now(UTC)
        lead.latest_score_total = result.score_total
        lead.latest_temperature = result.temperature
        lead.latest_assessment_status = "succeeded"
        lead.latest_assessment_at = datetime.now(UTC)
        lead.latest_summary = result.summary

        self.db.commit()
        self.db.refresh(assessment)

        if self.settings.feature_odoo_connector:
            self._callback_odoo(lead, assessment)

        return assessment

    def _callback_odoo(self, lead: Lead, assessment: LeadAssessment) -> None:
        if not lead.odoo_instance_id or not lead.odoo_res_id:
            assessment.odoo_callback_status = "skipped_no_odoo_link"
            self.db.commit()
            return
        odoo = OdooService(self.db, self.settings)
        instance = odoo.get_for_tenant(lead.tenant_id, lead.odoo_instance_id)
        if instance is None:
            assessment.odoo_callback_status = "skipped_instance_missing"
            self.db.commit()
            return
        try:
            secret = odoo.get_webhook_secret(instance)
            client = OdooClient()
            payload = client.build_assessment_payload(
                event_id=str(uuid4()),
                lead_id=lead.id,
                odoo_res_id=lead.odoo_res_id,
                assessment_type="fast",
                status="succeeded",
                score_total=assessment.score_total,
                temperature=assessment.temperature,
                summary=assessment.summary,
                recommended_action=assessment.recommended_action,
                confidence=assessment.confidence,
                project_type=assessment.project_type,
                customer_industry=assessment.customer_industry,
            )
            result = client.push_assessment_result(
                instance=instance, webhook_secret=secret, payload=payload
            )
            if result.get("ok"):
                assessment.odoo_callback_status = (
                    f"ok:{result.get('status_code')}:{result.get('body_status')}"
                )
            else:
                detail = result.get("body_status") or result.get("error") or result
                msg = result.get("body_message")
                assessment.odoo_callback_status = (
                    f"fail:{result.get('status_code')}:{detail}"
                    + (f":{msg}" if msg else "")
                )[:64]
        except Exception as exc:  # noqa: BLE001
            assessment.odoo_callback_status = f"error:{type(exc).__name__}"
        self.db.commit()
