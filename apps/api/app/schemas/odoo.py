from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OdooRegisterRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=100)
    instance_name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=8, max_length=512)
    odoo_version: str | None = None
    database_name: str | None = None
    company_name: str | None = None
    module_version: str | None = None


class OdooRegisterResponse(BaseModel):
    odoo_instance_id: UUID
    integration_token: str
    webhook_secret: str
    status: str


class OdooInstanceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=8, max_length=512)
    odoo_version: str | None = None
    database_name: str | None = None
    company_name: str | None = None


class OdooInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    base_url: str
    odoo_version: str | None
    company_name: str | None
    database_name: str | None
    module_version: str | None
    status: str
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class OdooInstanceCreateResponse(BaseModel):
    instance: OdooInstanceOut
    integration_token: str
    webhook_secret: str


class OdooLeadPayload(BaseModel):
    name: str
    company_name: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    country_code: str | None = None
    city: str | None = None
    description: str | None = None
    expected_revenue: Decimal | None = None
    stage_name: str | None = None
    salesperson_name: str | None = None
    team_name: str | None = None


class OdooMessagePayload(BaseModel):
    message_id: str
    date: datetime | None = None
    author_email: str | None = None
    subject: str | None = None
    body_text: str | None = None


class OdooAttachmentPayload(BaseModel):
    id: str
    filename: str
    mimetype: str | None = None
    size: int | None = None


class OdooLeadUpsertRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    odoo_instance_id: UUID
    model: str = "crm.lead"
    res_id: str
    write_date: datetime | None = None
    lead: OdooLeadPayload
    messages: list[OdooMessagePayload] = Field(default_factory=list)
    attachments: list[OdooAttachmentPayload] = Field(default_factory=list)


class OdooLeadUpsertResponse(BaseModel):
    lead_id: UUID
    status: str
    queued_jobs: list[str] = Field(default_factory=list)
    created: bool = False


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    source_type: str
    odoo_instance_id: UUID | None
    odoo_model: str | None
    odoo_res_id: str | None
    name: str
    company_name: str | None
    contact_name: str | None
    email: str | None
    phone: str | None
    website: str | None
    country_code: str | None
    city: str | None
    description: str | None
    expected_revenue: Decimal | None
    stage_name: str | None
    salesperson_name: str | None
    team_name: str | None
    status: str
    sync_status: str
    latest_score_total: int | None = None
    latest_temperature: str | None = None
    latest_assessment_status: str | None = None
    latest_assessment_at: datetime | None = None
    latest_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadOut]
    total: int


class AssessmentCallbackRequest(BaseModel):
    """SaaS → Odoo callback payload skeleton (Phase 2 stores log; Phase 3 fills scores)."""

    event_id: str
    lead_id: UUID
    odoo_model: str = "crm.lead"
    odoo_res_id: str
    assessment_type: str = "fast"
    status: str = "succeeded"
    score_total: int | None = None
    temperature: str | None = None
    summary: str | None = None


class DashboardSummaryOut(BaseModel):
    leads_total: int
    leads_from_odoo: int
    odoo_instances: int
    odoo_connected: int
    features: dict[str, bool]
