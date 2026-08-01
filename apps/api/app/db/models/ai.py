"""Phase 3 models: AI providers, assessment jobs, and lead assessments."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class AiProviderType(str, enum.Enum):
    mock = "mock"
    openai = "openai"
    openai_compatible = "openai_compatible"


class AiProviderStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    error = "error"
    disabled = "disabled"


class AssessmentWorkflow(str, enum.Enum):
    fast_lead_assessment = "fast_lead_assessment"
    deep_lead_research = "deep_lead_research"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AssessmentStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    stale = "stale"


class AiProviderConnection(TimestampMixin, Base):
    """Tenant BYOK AI provider. API keys are encrypted; never returned plaintext."""

    __tablename__ = "ai_provider_connections"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[AiProviderType] = mapped_column(
        Enum(
            AiProviderType,
            name="ai_provider_type",
            values_callable=_enum_values,
            native_enum=False,
        ),
        nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_model: Mapped[str] = mapped_column(String(128), default="gpt-4o-mini", nullable=False)
    status: Mapped[AiProviderStatus] = mapped_column(
        Enum(
            AiProviderStatus,
            name="ai_provider_status",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=AiProviderStatus.active,
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentJob(TimestampMixin, Base):
    """Async work unit for AI workflows. Processed by workers, never inside HTTP."""

    __tablename__ = "assessment_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_assessment_jobs_tenant_idem"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_provider_connections.id", ondelete="SET NULL"), nullable=True
    )
    workflow: Mapped[AssessmentWorkflow] = mapped_column(
        Enum(
            AssessmentWorkflow,
            name="assessment_workflow",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=AssessmentWorkflow.fast_lead_assessment,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=_enum_values, native_enum=False),
        default=JobStatus.queued,
        nullable=False,
        index=True,
    )
    force: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assessment_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    base_assessment_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "lead_assessments.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_assessment_jobs_base_assessment_id_lead_assessments",
        ),
        nullable=True,
    )


class LeadAssessment(TimestampMixin, Base):
    """Persisted structured AI assessment. Invalid model output must not create succeeded rows."""

    __tablename__ = "lead_assessments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("assessment_jobs.id", ondelete="SET NULL"), nullable=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_provider_connections.id", ondelete="SET NULL"), nullable=True
    )
    workflow: Mapped[AssessmentWorkflow] = mapped_column(
        Enum(
            AssessmentWorkflow,
            name="assessment_workflow_result",
            values_callable=_enum_values,
            native_enum=False,
        ),
        nullable=False,
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(
            AssessmentStatus,
            name="assessment_status",
            values_callable=_enum_values,
            native_enum=False,
        ),
        nullable=False,
    )
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    deep_research_recommended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    odoo_callback_status: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AssessmentEvidence(TimestampMixin, Base):
    """Validated evidence metadata. Object keys are private and exposed via signed URLs only."""

    __tablename__ = "assessment_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("lead_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    short_quote: Mapped[str | None] = mapped_column(String(500), nullable=True)
    claim_supported: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
