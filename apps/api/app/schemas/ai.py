from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.ai import AiProviderType


class ProviderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: AiProviderType = AiProviderType.mock
    api_key: str | None = None
    base_url: str | None = None
    default_model: str = "gpt-4o-mini"
    is_default: bool = False


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    provider_type: str
    base_url: str | None
    default_model: str
    status: str
    is_default: bool
    last_test_at: datetime | None
    last_error: str | None
    created_at: datetime
    # api_key intentionally omitted — never returned


class QueueAssessmentRequest(BaseModel):
    assessment_mode: str = "fast"
    force: bool = False
    provider_id: UUID | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    lead_id: UUID
    provider_id: UUID | None
    workflow: str
    status: str
    force: bool
    input_fingerprint: str
    error_message: str | None
    assessment_id: UUID | None
    base_assessment_id: UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    source_url: str
    title: str | None
    short_quote: str | None
    claim_supported: str
    confidence: int
    created_at: datetime


class EvidenceUrlOut(BaseModel):
    evidence_id: UUID
    url: str
    expires_in: int


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    lead_id: UUID
    job_id: UUID | None
    workflow: str
    status: str
    model_name: str | None
    score_total: int | None
    temperature: str | None
    confidence: int | None
    project_type: str | None
    customer_industry: str | None
    summary: str | None
    recommended_action: str | None
    deep_research_recommended: bool | None
    result_json: str | None
    error_message: str | None
    odoo_callback_status: str | None
    created_at: datetime
