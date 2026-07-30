from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.tenancy import require_feature
from app.db.models.ai import JobStatus
from app.db.models.tenant import TenantUser
from app.db.session import get_db
from app.schemas.ai import AssessmentOut, JobOut, QueueAssessmentRequest
from app.services.assessment_service import AssessmentService

router = APIRouter(tags=["jobs"])


def _fast_ai_enabled(settings: Settings = Depends(get_settings)) -> None:
    require_feature("fast_ai", settings)


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
    if body.assessment_mode not in {"fast", "full"}:
        raise AppError(
            "Only assessment_mode=fast|full supported in Phase 3 (deep is Phase 4)",
            code="unsupported_mode",
            status_code=400,
        )
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
