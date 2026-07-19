from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import FeatureDisabledError
from app.db.models.tenant import Tenant, TenantUser, TenantUserRole
from app.db.session import get_db


ROLE_RANK: dict[TenantUserRole, int] = {
    TenantUserRole.auditor: 10,
    TenantUserRole.analyst: 20,
    TenantUserRole.sales_user: 30,
    TenantUserRole.sales_manager: 40,
    TenantUserRole.admin: 50,
    TenantUserRole.owner: 60,
}


def require_feature(feature: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not cfg.is_feature_enabled(feature):
        raise FeatureDisabledError(feature)


def ensure_same_tenant(object_tenant_id: UUID, current_tenant_id: UUID) -> None:
    if object_tenant_id != current_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Resource not found", "details": {}},
        )


def parse_tenant_header(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> UUID | None:
    if not x_tenant_id:
        return None
    try:
        return UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_tenant_header",
                "message": "X-Tenant-Id must be a UUID",
                "details": {},
            },
        ) from exc


def get_tenant_by_id(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": "Tenant not found", "details": {}},
        )
    return tenant


def assert_min_role(user: TenantUser, min_role: TenantUserRole) -> None:
    if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role",
                "message": "Insufficient role for this action",
                "details": {"required": min_role.value, "actual": user.role.value},
            },
        )


def get_settings_dep() -> Settings:
    return get_settings()
