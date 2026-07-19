from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models.tenant import TenantUser
from app.db.session import get_db
from app.schemas.odoo import DashboardSummaryOut, LeadListResponse, LeadOut
from app.services.odoo_service import OdooService

router = APIRouter(tags=["leads"])


def get_odoo_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OdooService:
    return OdooService(db, settings)


@router.get("/leads", response_model=LeadListResponse)
def list_leads(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: TenantUser = Depends(get_current_user),
    service: OdooService = Depends(get_odoo_service),
) -> LeadListResponse:
    items, total = service.list_leads(
        user.tenant_id, search=search, limit=limit, offset=offset
    )
    return LeadListResponse(
        items=[LeadOut.model_validate(i) for i in items],
        total=total,
    )


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: UUID,
    user: TenantUser = Depends(get_current_user),
    service: OdooService = Depends(get_odoo_service),
) -> LeadOut:
    lead = service.get_lead(user.tenant_id, lead_id)
    if lead is None:
        raise AppError("Lead not found", code="lead_not_found", status_code=404)
    return LeadOut.model_validate(lead)


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    user: TenantUser = Depends(get_current_user),
    service: OdooService = Depends(get_odoo_service),
    settings: Settings = Depends(get_settings),
) -> DashboardSummaryOut:
    stats = service.dashboard_summary(user.tenant_id)
    return DashboardSummaryOut(**stats, features=settings.feature_map())
