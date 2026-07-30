from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.tenancy import require_feature
from app.db.models.tenant import TenantUser, TenantUserRole
from app.db.session import get_db
from app.schemas.ai import ProviderCreateRequest, ProviderOut
from app.services.ai_provider_service import AiProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


def _fast_ai_enabled(settings: Settings = Depends(get_settings)) -> None:
    require_feature("fast_ai", settings)


def get_provider_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AiProviderService:
    return AiProviderService(db, settings)


@router.get("", response_model=list[ProviderOut])
def list_providers(
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AiProviderService = Depends(get_provider_service),
) -> list[ProviderOut]:
    items = service.list_for_tenant(user.tenant_id)
    return [ProviderOut.model_validate(i) for i in items]


@router.post("", response_model=ProviderOut, status_code=201)
def create_provider(
    body: ProviderCreateRequest,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    service: AiProviderService = Depends(get_provider_service),
) -> ProviderOut:
    row = service.create(
        tenant_id=user.tenant_id,
        name=body.name,
        provider_type=body.provider_type,
        api_key=body.api_key,
        base_url=body.base_url,
        default_model=body.default_model,
        is_default=body.is_default,
    )
    return ProviderOut.model_validate(row)


@router.post("/{provider_id}/test")
def test_provider(
    provider_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    service: AiProviderService = Depends(get_provider_service),
) -> dict:
    return service.test_connection(user.tenant_id, provider_id)


@router.get("/{provider_id}", response_model=ProviderOut)
def get_provider(
    provider_id: UUID,
    _: None = Depends(_fast_ai_enabled),
    user: TenantUser = Depends(get_current_user),
    service: AiProviderService = Depends(get_provider_service),
) -> ProviderOut:
    row = service.get_for_tenant(user.tenant_id, provider_id)
    if row is None:
        raise AppError("Provider not found", code="provider_not_found", status_code=404)
    return ProviderOut.model_validate(row)
