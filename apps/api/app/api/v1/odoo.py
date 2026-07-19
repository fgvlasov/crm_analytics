from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.tenancy import require_feature
from app.db.models.odoo import OdooInstance
from app.db.models.tenant import TenantUser, TenantUserRole
from app.db.session import get_db
from app.integrations.odoo_client import OdooClient
from app.schemas.odoo import (
    AssessmentCallbackRequest,
    OdooInstanceCreateRequest,
    OdooInstanceCreateResponse,
    OdooInstanceOut,
    OdooLeadUpsertRequest,
    OdooLeadUpsertResponse,
    OdooRegisterRequest,
    OdooRegisterResponse,
)
from app.services.odoo_service import OdooService, verify_odoo_request_signature

router = APIRouter(prefix="/odoo", tags=["odoo"])
bearer = HTTPBearer(auto_error=False)


def _odoo_enabled(settings: Settings = Depends(get_settings)) -> None:
    require_feature("odoo_connector", settings)


def get_odoo_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OdooService:
    return OdooService(db, settings)


def get_odoo_instance_from_headers(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_leadintel_tenant: str | None = Header(default=None, alias="X-LeadIntel-Tenant"),
    x_leadintel_odoo_instance: str | None = Header(
        default=None, alias="X-LeadIntel-Odoo-Instance"
    ),
    service: OdooService = Depends(get_odoo_service),
    settings: Settings = Depends(get_settings),
) -> OdooInstance:
    require_feature("odoo_connector", settings)
    if credentials is None or not x_leadintel_odoo_instance:
        raise AppError("Missing Odoo auth headers", code="odoo_auth_missing", status_code=401)

    tenant_id = UUID(x_leadintel_tenant) if x_leadintel_tenant else None
    return service.authenticate_instance(
        instance_id=UUID(x_leadintel_odoo_instance),
        bearer_token=credentials.credentials,
        tenant_id=tenant_id,
    )


async def _maybe_verify_signature(
    request: Request,
    instance: OdooInstance,
    service: OdooService,
) -> None:
    signature = request.headers.get("X-LeadIntel-Signature")
    timestamp = request.headers.get("X-LeadIntel-Timestamp")
    if not signature or not timestamp:
        return
    raw_body = await request.body()
    secret = service.get_webhook_secret(instance)
    verify_odoo_request_signature(
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        raw_body=raw_body,
        signature=signature,
        secret=secret,
    )


@router.post("/instances/register", response_model=OdooRegisterResponse)
def register_instance(
    body: OdooRegisterRequest,
    _: None = Depends(_odoo_enabled),
    service: OdooService = Depends(get_odoo_service),
) -> OdooRegisterResponse:
    instance, token, webhook_secret = service.register_from_odoo(body)
    return OdooRegisterResponse(
        odoo_instance_id=instance.id,
        integration_token=token,
        webhook_secret=webhook_secret,
        status=instance.status.value,
    )


@router.get("/instances", response_model=list[OdooInstanceOut])
def list_instances(
    _: None = Depends(_odoo_enabled),
    user: TenantUser = Depends(get_current_user),
    service: OdooService = Depends(get_odoo_service),
) -> list[OdooInstanceOut]:
    items = service.list_for_tenant(user.tenant_id)
    return [OdooInstanceOut.model_validate(i) for i in items]


@router.post("/instances", response_model=OdooInstanceCreateResponse, status_code=201)
def create_instance(
    body: OdooInstanceCreateRequest,
    _: None = Depends(_odoo_enabled),
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    service: OdooService = Depends(get_odoo_service),
) -> OdooInstanceCreateResponse:
    instance, token, webhook_secret = service.create_for_tenant(
        tenant_id=user.tenant_id, body=body
    )
    return OdooInstanceCreateResponse(
        instance=OdooInstanceOut.model_validate(instance),
        integration_token=token,
        webhook_secret=webhook_secret,
    )


@router.get("/instances/{instance_id}", response_model=OdooInstanceOut)
def get_instance(
    instance_id: UUID,
    _: None = Depends(_odoo_enabled),
    user: TenantUser = Depends(get_current_user),
    service: OdooService = Depends(get_odoo_service),
) -> OdooInstanceOut:
    instance = service.get_for_tenant(user.tenant_id, instance_id)
    if instance is None:
        raise AppError("Odoo instance not found", code="odoo_not_found", status_code=404)
    return OdooInstanceOut.model_validate(instance)


@router.post("/leads/upsert", response_model=OdooLeadUpsertResponse)
async def upsert_lead(
    request: Request,
    body: OdooLeadUpsertRequest,
    instance: OdooInstance = Depends(get_odoo_instance_from_headers),
    service: OdooService = Depends(get_odoo_service),
) -> OdooLeadUpsertResponse:
    await _maybe_verify_signature(request, instance, service)
    lead, created, _resp = service.upsert_lead(instance=instance, body=body)
    return OdooLeadUpsertResponse(
        lead_id=lead.id,
        status="accepted",
        queued_jobs=[],
        created=created,
    )


@router.post("/callback/assessment-test")
def test_assessment_callback(
    body: AssessmentCallbackRequest,
    _: None = Depends(_odoo_enabled),
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    service: OdooService = Depends(get_odoo_service),
) -> dict:
    """Manual test of SaaS→Odoo webhook path (admin only)."""
    lead = service.get_lead(user.tenant_id, body.lead_id)
    if lead is None or not lead.odoo_instance_id:
        raise AppError(
            "Lead not found or not linked to Odoo",
            code="lead_not_found",
            status_code=404,
        )
    instance = service.get_for_tenant(user.tenant_id, lead.odoo_instance_id)
    if instance is None:
        raise AppError("Odoo instance not found", code="odoo_not_found", status_code=404)
    secret = service.get_webhook_secret(instance)
    client = OdooClient()
    payload = client.build_assessment_payload(
        event_id=body.event_id,
        lead_id=body.lead_id,
        odoo_res_id=body.odoo_res_id,
        assessment_type=body.assessment_type,
        status=body.status,
        score_total=body.score_total,
        temperature=body.temperature,
        summary=body.summary,
    )
    result = client.push_assessment_result(
        instance=instance, webhook_secret=secret, payload=payload
    )
    return {"callback": result, "payload": payload}
