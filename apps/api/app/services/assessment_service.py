"""Fast Lead Assessment orchestration: queue, fingerprint skip, validate, persist, Odoo callback."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.models.ai import (
    AssessmentEvidence,
    AssessmentJob,
    AssessmentStatus,
    AssessmentWorkflow,
    JobStatus,
    LeadAssessment,
)
from app.db.models.odoo import Lead
from app.db.models.tenant import Tenant
from app.integrations.odoo_client import OdooClient
from app.integrations.web_research import build_web_research_provider
from app.services.ai_clients import build_client
from app.services.ai_provider_service import AiProviderService
from app.services.ai_schemas import (
    DEEP_RESEARCH_RESPONSE_SCHEMA,
    DEEP_RESEARCH_SYSTEM_PROMPT,
    FAST_ASSESSMENT_RESPONSE_SCHEMA,
    FAST_ASSESSMENT_SYSTEM_PROMPT,
    deep_input_fingerprint,
    fast_input_fingerprint,
    validate_deep_and_finalize,
    validate_and_finalize,
)
from app.services.object_storage import ObjectStorageService
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
        idempotency_key = f"fast:{lead.id}:{provider.id}:{fingerprint}:{int(force)}"

        existing = self.db.scalar(
            select(AssessmentJob).where(
                AssessmentJob.tenant_id == tenant_id,
                AssessmentJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.status in {JobStatus.failed, JobStatus.cancelled}:
                existing.status = JobStatus.queued
                existing.provider_id = provider.id
                existing.error_message = None
                existing.started_at = None
                existing.finished_at = None
                existing.assessment_id = None
                lead.latest_assessment_status = "queued"
                self.db.commit()
                self.db.refresh(existing)
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

    def _deep_payload(
        self,
        lead: Lead,
        fast_assessment: LeadAssessment,
    ) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        if lead.raw_payload_json:
            try:
                raw = json.loads(lead.raw_payload_json)
            except json.JSONDecodeError:
                pass

        similar_leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.tenant_id == lead.tenant_id, Lead.id != lead.id)
                .order_by(Lead.updated_at.desc())
                .limit(20)
            ).all()
        )
        tenant = self.db.scalar(select(Tenant).where(Tenant.id == lead.tenant_id))
        lead_payload = self._lead_payload(lead)
        web_research = build_web_research_provider().research_company(
            {
                "company_name": lead.company_name,
                "website": lead.website,
                "canonical_domain": lead.canonical_company_domain,
                "country_code": lead.country_code,
                "city": lead.city,
            }
        )
        return {
            "lead": lead_payload,
            "fast_assessment": json.loads(fast_assessment.result_json or "{}"),
            "internal_history": (raw.get("history") or raw.get("messages") or [])[:20],
            "similar_deals": [
                {
                    "similar_deal_id": str(item.id),
                    "name": item.name,
                    "company_name": item.company_name,
                    "stage_name": item.stage_name,
                    "status": item.status.value,
                    "expected_revenue": (
                        str(item.expected_revenue) if item.expected_revenue is not None else None
                    ),
                }
                for item in similar_leads
            ],
            "tenant_business_profile": {
                "name": tenant.name if tenant else None,
                "primary_country": tenant.primary_country if tenant else None,
            },
            "web_research": web_research,
        }

    def _latest_fast_success(self, tenant_id: UUID, lead_id: UUID) -> LeadAssessment | None:
        return self.db.scalar(
            select(LeadAssessment)
            .where(
                LeadAssessment.tenant_id == tenant_id,
                LeadAssessment.lead_id == lead_id,
                LeadAssessment.workflow == AssessmentWorkflow.fast_lead_assessment,
                LeadAssessment.status == AssessmentStatus.succeeded,
            )
            .order_by(LeadAssessment.created_at.desc())
        )

    def queue_deep(
        self,
        *,
        tenant_id: UUID,
        lead_id: UUID,
        force: bool = False,
        provider_id: UUID | None = None,
    ) -> AssessmentJob:
        if not self.settings.feature_deep_research:
            raise AppError(
                "FEATURE_DEEP_RESEARCH is disabled",
                code="feature_disabled",
                status_code=403,
                details={"feature": "deep_research"},
            )
        lead = self.db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        if lead is None:
            raise AppError("Lead not found", code="lead_not_found", status_code=404)
        fast_assessment = self._latest_fast_success(tenant_id, lead_id)
        if fast_assessment is None:
            raise AppError(
                "A successful Fast Assessment is required before Deep Research",
                code="fast_assessment_required",
                status_code=409,
            )

        provider = (
            self.providers.get_for_tenant(tenant_id, provider_id)
            if provider_id
            else self.providers.ensure_mock_default(tenant_id)
        )
        if provider is None:
            raise AppError("Provider not found", code="provider_not_found", status_code=404)

        fingerprint = deep_input_fingerprint(self._deep_payload(lead, fast_assessment))
        idempotency_key = f"deep:{lead.id}:{provider.id}:{fingerprint}:{int(force)}"
        existing = self.db.scalar(
            select(AssessmentJob).where(
                AssessmentJob.tenant_id == tenant_id,
                AssessmentJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.status in {JobStatus.failed, JobStatus.cancelled}:
                existing.status = JobStatus.queued
                existing.provider_id = provider.id
                existing.base_assessment_id = fast_assessment.id
                existing.error_message = None
                existing.started_at = None
                existing.finished_at = None
                existing.assessment_id = None
                self.db.commit()
                self.db.refresh(existing)
            return existing

        if not force:
            prior = self.db.scalar(
                select(LeadAssessment)
                .where(
                    LeadAssessment.tenant_id == tenant_id,
                    LeadAssessment.lead_id == lead_id,
                    LeadAssessment.workflow == AssessmentWorkflow.deep_lead_research,
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
                    workflow=AssessmentWorkflow.deep_lead_research,
                    status=JobStatus.succeeded,
                    force=False,
                    input_fingerprint=fingerprint,
                    idempotency_key=idempotency_key,
                    assessment_id=prior.id,
                    base_assessment_id=fast_assessment.id,
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
            workflow=AssessmentWorkflow.deep_lead_research,
            status=JobStatus.queued,
            force=force,
            input_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            base_assessment_id=fast_assessment.id,
        )
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

    def latest_assessment(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        workflow: AssessmentWorkflow = AssessmentWorkflow.fast_lead_assessment,
    ) -> LeadAssessment | None:
        return self.db.scalar(
            select(LeadAssessment)
            .where(
                LeadAssessment.tenant_id == tenant_id,
                LeadAssessment.lead_id == lead_id,
                LeadAssessment.workflow == workflow,
            )
            .order_by(LeadAssessment.created_at.desc())
        )

    def claim_next_queued_job(self) -> AssessmentJob | None:
        """Worker helper: claim one queued job for an enabled workflow."""
        workflows = [AssessmentWorkflow.fast_lead_assessment]
        if self.settings.feature_deep_research:
            workflows.append(AssessmentWorkflow.deep_lead_research)
        job = self.db.scalar(
            select(AssessmentJob)
            .where(
                AssessmentJob.status == JobStatus.queued,
                AssessmentJob.workflow.in_(workflows),
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
        if job.workflow == AssessmentWorkflow.deep_lead_research:
            return self._process_deep_job(job)

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
                response_schema=FAST_ASSESSMENT_RESPONSE_SCHEMA,
            )
            try:
                result = validate_and_finalize(raw)
            except (ValidationError, ValueError) as validation_error:
                repair_prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous JSON did not match the required response schema. "
                    "Return a complete replacement object and do not omit required fields.\n"
                    f"VALIDATION_ERROR:\n{str(validation_error)[:2000]}\n"
                    f"PREVIOUS_JSON:\n{json.dumps(raw, default=str)[:12000]}"
                )
                repaired = client.complete_json(
                    system=FAST_ASSESSMENT_SYSTEM_PROMPT,
                    user=repair_prompt,
                    model=provider.default_model,
                    response_schema=FAST_ASSESSMENT_RESPONSE_SCHEMA,
                )
                result = validate_and_finalize(repaired)
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

        if self.settings.feature_deep_research and result.deep_research_recommended:
            try:
                self.queue_deep(
                    tenant_id=lead.tenant_id,
                    lead_id=lead.id,
                    force=False,
                    provider_id=provider.id,
                )
            except Exception as exc:  # noqa: BLE001 — Fast Assessment remains successful
                logger.warning(
                    "Could not queue recommended Deep Research lead_id=%s error=%s",
                    lead.id,
                    type(exc).__name__,
                )

        if self.settings.feature_odoo_connector:
            self._callback_odoo(lead, assessment)

        return assessment

    def _process_deep_job(self, job: AssessmentJob) -> LeadAssessment:
        if not self.settings.feature_deep_research:
            raise AppError(
                "FEATURE_DEEP_RESEARCH is disabled",
                code="feature_disabled",
                status_code=403,
            )
        lead = self.db.scalar(
            select(Lead).where(Lead.id == job.lead_id, Lead.tenant_id == job.tenant_id)
        )
        fast_assessment = (
            self.db.get(LeadAssessment, job.base_assessment_id)
            if job.base_assessment_id
            else None
        )
        if lead is None or fast_assessment is None:
            return self._fail_deep_job(job, lead, "Lead or base Fast Assessment is missing")

        payload = self._deep_payload(lead, fast_assessment)
        current_fingerprint = deep_input_fingerprint(payload)
        if current_fingerprint != job.input_fingerprint:
            return self._mark_deep_stale(job, lead)

        provider = (
            self.providers.get_for_tenant(job.tenant_id, job.provider_id)
            if job.provider_id
            else self.providers.ensure_mock_default(job.tenant_id)
        )
        if provider is None:
            return self._fail_deep_job(job, lead, "AI provider is missing")

        allowed_ids = {
            str(item["similar_deal_id"]) for item in payload.get("similar_deals", [])
        }
        user_prompt = (
            "Research this B2B lead using only the supplied data and allowed candidate IDs. "
            "Respond with JSON only.\n"
            f"DEEP_RESEARCH_DATA:\n{json.dumps(payload, default=str)}"
        )
        try:
            client = build_client(
                provider_type=provider.provider_type.value,
                api_key=self.providers.reveal_api_key(provider),
                base_url=provider.base_url,
            )
            raw = client.complete_json(
                system=DEEP_RESEARCH_SYSTEM_PROMPT,
                user=user_prompt,
                model=provider.default_model,
                response_schema=DEEP_RESEARCH_RESPONSE_SCHEMA,
            )
            try:
                result = validate_deep_and_finalize(
                    raw,
                    allowed_similar_deal_ids=allowed_ids,
                )
            except (ValidationError, ValueError) as validation_error:
                repair_prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous JSON did not match the required response schema or "
                    "selected a similar deal outside the allowed list. Return a complete "
                    "replacement object.\n"
                    f"VALIDATION_ERROR:\n{str(validation_error)[:2000]}\n"
                    f"PREVIOUS_JSON:\n{json.dumps(raw, default=str)[:12000]}"
                )
                repaired = client.complete_json(
                    system=DEEP_RESEARCH_SYSTEM_PROMPT,
                    user=repair_prompt,
                    model=provider.default_model,
                    response_schema=DEEP_RESEARCH_RESPONSE_SCHEMA,
                )
                result = validate_deep_and_finalize(
                    repaired,
                    allowed_similar_deal_ids=allowed_ids,
                )
        except Exception as exc:  # noqa: BLE001
            logger.info("Deep research failed job_id=%s error=%s", job.id, type(exc).__name__)
            return self._fail_deep_job(
                job,
                lead,
                str(exc),
                provider_id=provider.id,
                model_name=provider.default_model,
            )

        # Re-read after the provider call so edits made while research was running
        # cannot be published as a current result.
        self.db.expire_all()
        lead = self.db.scalar(
            select(Lead).where(Lead.id == job.lead_id, Lead.tenant_id == job.tenant_id)
        )
        fast_assessment = (
            self.db.get(LeadAssessment, job.base_assessment_id)
            if job.base_assessment_id
            else None
        )
        if (
            lead is None
            or fast_assessment is None
            or deep_input_fingerprint(self._deep_payload(lead, fast_assessment))
            != job.input_fingerprint
        ):
            if lead is None:
                return self._fail_deep_job(job, None, "Lead was deleted during Deep Research")
            return self._mark_deep_stale(job, lead)

        assessment = LeadAssessment(
            tenant_id=job.tenant_id,
            lead_id=lead.id,
            job_id=job.id,
            provider_id=provider.id,
            workflow=AssessmentWorkflow.deep_lead_research,
            status=AssessmentStatus.succeeded,
            model_name=provider.default_model,
            input_fingerprint=job.input_fingerprint,
            score_total=result.score_total,
            temperature=result.temperature,
            confidence=result.overall_assessment_confidence,
            summary=result.company_profile,
            recommended_action=result.recommended_action,
            result_json=result.model_dump_json(),
        )
        self.db.add(assessment)
        self.db.flush()

        storage = ObjectStorageService(self.settings)
        for source in result.sources:
            evidence = AssessmentEvidence(
                tenant_id=job.tenant_id,
                assessment_id=assessment.id,
                source_url=str(source.source_url),
                title=source.title,
                short_quote=source.short_quote,
                claim_supported=source.claim_supported,
                confidence=source.confidence,
                object_key=(
                    f"tenants/{job.tenant_id}/assessments/{assessment.id}/"
                    f"evidence/{uuid4()}.json"
                ),
            )
            storage.put_json(
                evidence.object_key,
                source.model_dump(mode="json"),
            )
            self.db.add(evidence)

        job.status = JobStatus.succeeded
        job.assessment_id = assessment.id
        job.finished_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(assessment)
        if self.settings.feature_odoo_connector:
            self._callback_odoo(lead, assessment)
        return assessment

    def _mark_deep_stale(self, job: AssessmentJob, lead: Lead) -> LeadAssessment:
        stale = LeadAssessment(
            tenant_id=job.tenant_id,
            lead_id=lead.id,
            job_id=job.id,
            provider_id=job.provider_id,
            workflow=AssessmentWorkflow.deep_lead_research,
            status=AssessmentStatus.stale,
            input_fingerprint=job.input_fingerprint,
            error_message="Input changed while this Deep Research job was pending or running",
        )
        job.status = JobStatus.cancelled
        job.error_message = stale.error_message
        job.finished_at = datetime.now(UTC)
        self.db.add(stale)
        self.db.commit()
        self.queue_deep(
            tenant_id=job.tenant_id,
            lead_id=lead.id,
            force=False,
            provider_id=job.provider_id,
        )
        self.db.refresh(stale)
        return stale

    def _fail_deep_job(
        self,
        job: AssessmentJob,
        lead: Lead | None,
        error: str,
        *,
        provider_id: UUID | None = None,
        model_name: str | None = None,
    ) -> LeadAssessment:
        failed = LeadAssessment(
            tenant_id=job.tenant_id,
            lead_id=job.lead_id,
            job_id=job.id,
            provider_id=provider_id or job.provider_id,
            workflow=AssessmentWorkflow.deep_lead_research,
            status=AssessmentStatus.failed,
            model_name=model_name,
            input_fingerprint=job.input_fingerprint,
            error_message=error[:2000],
        )
        job.status = JobStatus.failed
        job.error_message = error[:2000]
        job.finished_at = datetime.now(UTC)
        self.db.add(failed)
        self.db.commit()
        self.db.refresh(failed)
        return failed

    def list_evidence(
        self,
        tenant_id: UUID,
        assessment_id: UUID,
    ) -> list[AssessmentEvidence]:
        return list(
            self.db.scalars(
                select(AssessmentEvidence)
                .where(
                    AssessmentEvidence.tenant_id == tenant_id,
                    AssessmentEvidence.assessment_id == assessment_id,
                )
                .order_by(AssessmentEvidence.created_at.asc())
            ).all()
        )

    def get_evidence(self, tenant_id: UUID, evidence_id: UUID) -> AssessmentEvidence | None:
        return self.db.scalar(
            select(AssessmentEvidence).where(
                AssessmentEvidence.id == evidence_id,
                AssessmentEvidence.tenant_id == tenant_id,
            )
        )

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
            structured_result: dict[str, Any] = {}
            if assessment.result_json:
                try:
                    decoded_result = json.loads(assessment.result_json)
                    if isinstance(decoded_result, dict):
                        structured_result = decoded_result
                except json.JSONDecodeError:
                    logger.warning(
                        "Assessment result JSON could not be decoded assessment_id=%s",
                        assessment.id,
                    )
            payload = client.build_assessment_payload(
                event_id=str(uuid4()),
                lead_id=lead.id,
                odoo_res_id=lead.odoo_res_id,
                assessment_type=(
                    "deep"
                    if assessment.workflow == AssessmentWorkflow.deep_lead_research
                    else "fast"
                ),
                status="succeeded",
                score_total=assessment.score_total,
                temperature=assessment.temperature,
                summary=assessment.summary,
                recommended_action=assessment.recommended_action,
                confidence=assessment.confidence,
                project_type=assessment.project_type,
                customer_industry=assessment.customer_industry,
                result_json=structured_result,
            )
            result = client.push_assessment_result(
                instance=instance, webhook_secret=secret, payload=payload
            )
            if result.get("ok"):
                assessment.odoo_callback_status = (
                    f"ok:{result.get('status_code')}:{result.get('body_status')}"
                )
            else:
                detail = (
                    result.get("body_status")
                    or result.get("error")
                    or "invalid_odoo_response"
                )
                msg = result.get("body_message")
                assessment.odoo_callback_status = (
                    f"fail:{result.get('status_code')}:{detail}"
                    + (f":{msg}" if msg else "")
                )[:64]
        except Exception as exc:  # noqa: BLE001
            assessment.odoo_callback_status = f"error:{type(exc).__name__}"
        self.db.commit()
