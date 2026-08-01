from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.tenancy import require_feature
from app.db.models.ai import AssessmentWorkflow, JobStatus
from app.db.models.tenant import TenantUser
from app.db.session import get_db
from app.schemas.ai import (
    AssessmentOut,
    EvidenceOut,
    EvidenceUrlOut,
    JobOut,
    QueueAssessmentRequest,
)
from app.services.assessment_service import AssessmentService
from app.services.object_storage import ObjectStorageService

router = APIRouter(tags=["jobs"])


def _fast_ai_enabled(settings: Settings = Depends(get_settings)) -> None:
    require_feature("fast_ai", settings)


def _deep_research_enabled(settings: Settings = Depends(get_settings)) -> None:
    require_feature("deep_research", settings)


def get_assessment_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AssessmentService:
    return AssessmentService(db, settings)


@router.post("/leads/{lead_id}/assessments/queue", response_model=JobOut)
def queue_assessment(
    lead_id: UUID,
    body: QueueAssessmentRequest,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> JobOut:
    if body.assessment_mode not in {"fast", "full", "deep"}:
        raise AppError(
            "assessment_mode must be fast, deep, or full",
            code="unsupported_mode",
            status_code=400,
        )
    if body.assessment_mode == "deep":
        require_feature("deep_research", service.settings)
        job = service.queue_deep(
            tenant_id=user.tenant_id,
            lead_id=lead_id,
            force=body.force,
            provider_id=body.provider_id,
        )
    else:
        job = service.queue_fast(
            tenant_id=user.tenant_id,
            lead_id=lead_id,
            force=body.force,
            provider_id=body.provider_id,
        )
    return JobOut.model_validate(job)


@router.get("/leads/{lead_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(
    lead_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> list[AssessmentOut]:
    items = service.list_assessments(user.tenant_id, lead_id)
    return [AssessmentOut.model_validate(i) for i in items]


@router.get("/leads/{lead_id}/assessments/latest", response_model=AssessmentOut)
def latest_assessment(
    lead_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentOut:
    row = service.latest_assessment(user.tenant_id, lead_id)
    if row is None:
        raise AppError("No assessment yet", code="assessment_not_found", status_code=404)
    return AssessmentOut.model_validate(row)


@router.get("/leads/{lead_id}/assessments/deep/latest", response_model=AssessmentOut)
def latest_deep_assessment(
    lead_id: UUID,
    _: None = Depends(_deep_research_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentOut:
    row = service.latest_assessment(
        user.tenant_id,
        lead_id,
        AssessmentWorkflow.deep_lead_research,
    )
    if row is None:
        raise AppError("No Deep Research result yet", code="assessment_not_found", status_code=404)
    return AssessmentOut.model_validate(row)


@router.get(
    "/assessments/{assessment_id}/evidence",
    response_model=list[EvidenceOut],
)
def list_assessment_evidence(
    assessment_id: UUID,
    _: None = Depends(_deep_research_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> list[EvidenceOut]:
    return [
        EvidenceOut.model_validate(item)
        for item in service.list_evidence(user.tenant_id, assessment_id)
    ]


@router.post("/evidence/{evidence_id}/signed-url", response_model=EvidenceUrlOut)
def create_evidence_signed_url(
    evidence_id: UUID,
    _: None = Depends(_deep_research_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
    settings: Settings = Depends(get_settings),
) -> EvidenceUrlOut:
    evidence = service.get_evidence(user.tenant_id, evidence_id)
    if evidence is None:
        raise AppError("Evidence not found", code="evidence_not_found", status_code=404)
    expires_in = 300
    url = ObjectStorageService(settings).signed_get_url(
        evidence.object_key,
        expires_seconds=expires_in,
    )
    return EvidenceUrlOut(evidence_id=evidence.id, url=url, expires_in=expires_in)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> list[JobOut]:
    return [JobOut.model_validate(j) for j in service.list_jobs(user.tenant_id)]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> JobOut:
    job = service.get_job(user.tenant_id, job_id)
    if job is None:
        raise AppError("Job not found", code="job_not_found", status_code=404)
    return JobOut.model_validate(job)


@router.post("/jobs/{job_id}/run", response_model=AssessmentOut)
def run_job_now(
    job_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentOut:
    """Process a job synchronously (dev/admin). Workers normally poll the queue."""
    job = service.get_job(user.tenant_id, job_id)
    if job is None:
        raise AppError("Job not found", code="job_not_found", status_code=404)
    if job.status == JobStatus.queued:
        job.status = JobStatus.running
        service.db.commit()
    result = service.process_job(job.id)
    return AssessmentOut.model_validate(result)
