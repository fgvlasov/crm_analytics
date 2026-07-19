from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.models.tenant import TenantUser
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TenantOut,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    access, refresh, _user = AuthService(db, settings).login(
        email=str(body.email),
        password=body.password,
        tenant_slug=body.tenant_slug,
    )
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    access, new_refresh, _user = AuthService(db, settings).refresh(body.refresh_token)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    # JWT is stateless in Phase 1; client discards tokens.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def me(user: TenantUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(user.tenant),
    )
