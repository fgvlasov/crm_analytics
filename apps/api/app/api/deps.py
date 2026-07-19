from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_token
from app.core.tenancy import assert_min_role
from app.db.models.tenant import TenantUser, TenantUserRole, TenantUserStatus
from app.db.session import get_db
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(db, settings)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> TenantUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Not authenticated", "details": {}},
        )
    try:
        payload = decode_token(credentials.credentials, settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid token", "details": {}},
        ) from exc
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid token type", "details": {}},
        )

    user = auth.get_user_by_id(UUID(payload["user_id"]), UUID(payload["tenant_id"]))
    if user is None or user.status != TenantUserStatus.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "User not found or disabled", "details": {}},
        )
    return user


def require_roles(*roles: TenantUserRole):
    min_role = min(roles, key=lambda r: {
        TenantUserRole.auditor: 10,
        TenantUserRole.analyst: 20,
        TenantUserRole.sales_user: 30,
        TenantUserRole.sales_manager: 40,
        TenantUserRole.admin: 50,
        TenantUserRole.owner: 60,
    }[r]) if roles else TenantUserRole.sales_user

    def _dep(user: TenantUser = Depends(get_current_user)) -> TenantUser:
        assert_min_role(user, min_role)
        return user

    return _dep
