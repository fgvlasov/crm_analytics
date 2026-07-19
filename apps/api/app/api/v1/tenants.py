from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.core.tenancy import ensure_same_tenant
from app.db.models.tenant import TenantUser, TenantUserRole
from app.db.session import get_db
from app.schemas.auth import SecretCreateRequest, SecretOut, TenantOut
from app.services.auth_service import TenantService
from app.services.secret_service import SecretService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantOut)
def get_current_tenant(user: TenantUser = Depends(get_current_user)) -> TenantOut:
    return TenantOut.model_validate(user.tenant)


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: str,
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    db: Session = Depends(get_db),
) -> TenantOut:
    from uuid import UUID

    tid = UUID(tenant_id)
    ensure_same_tenant(tid, user.tenant_id)
    tenant = TenantService(db).get_by_id(tid)
    assert tenant is not None
    return TenantOut.model_validate(tenant)


@router.post("/current/secrets", response_model=SecretOut, status_code=201)
def create_secret(
    body: SecretCreateRequest,
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SecretOut:
    secret = SecretService(db, settings).create(
        tenant_id=user.tenant_id,
        name=body.name,
        value=body.value,
        purpose=body.purpose,
    )
    return SecretOut.model_validate(secret)


@router.get("/current/secrets", response_model=list[SecretOut])
def list_secrets(
    user: TenantUser = Depends(require_roles(TenantUserRole.admin)),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[SecretOut]:
    secrets = SecretService(db, settings).list_for_tenant(tenant_id=user.tenant_id)
    return [SecretOut.model_validate(s) for s in secrets]
