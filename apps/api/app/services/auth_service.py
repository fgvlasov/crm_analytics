from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.tenant import (
    Tenant,
    TenantStatus,
    TenantUser,
    TenantUserRole,
    TenantUserStatus,
)


class AuthService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def login(self, *, email: str, password: str, tenant_slug: str) -> tuple[str, str, TenantUser]:
        tenant = self.db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None or tenant.status in {TenantStatus.suspended, TenantStatus.cancelled}:
            raise AppError(
                "Invalid credentials",
                code="invalid_credentials",
                status_code=401,
            )

        user = self.db.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.email == email.lower(),
            )
        )
        if user is None or user.status != TenantUserStatus.active:
            raise AppError(
                "Invalid credentials",
                code="invalid_credentials",
                status_code=401,
            )
        if not verify_password(password, user.password_hash):
            raise AppError(
                "Invalid credentials",
                code="invalid_credentials",
                status_code=401,
            )

        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(user)

        access = create_access_token(
            settings=self.settings,
            subject=user.email,
            tenant_id=tenant.id,
            user_id=user.id,
            role=user.role.value,
        )
        refresh = create_refresh_token(
            settings=self.settings,
            subject=user.email,
            tenant_id=tenant.id,
            user_id=user.id,
        )
        return access, refresh, user

    def refresh(self, refresh_token: str) -> tuple[str, str, TenantUser]:
        try:
            payload = decode_token(refresh_token, self.settings)
        except ValueError as exc:
            raise AppError("Invalid refresh token", code="invalid_token", status_code=401) from exc
        if payload.get("type") != "refresh":
            raise AppError("Invalid refresh token", code="invalid_token", status_code=401)

        user_id = UUID(payload["user_id"])
        tenant_id = UUID(payload["tenant_id"])
        user = self.db.scalar(
            select(TenantUser)
            .options(joinedload(TenantUser.tenant))
            .where(TenantUser.id == user_id, TenantUser.tenant_id == tenant_id)
        )
        if user is None or user.status != TenantUserStatus.active:
            raise AppError("Invalid refresh token", code="invalid_token", status_code=401)

        access = create_access_token(
            settings=self.settings,
            subject=user.email,
            tenant_id=user.tenant_id,
            user_id=user.id,
            role=user.role.value,
        )
        new_refresh = create_refresh_token(
            settings=self.settings,
            subject=user.email,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        return access, new_refresh, user

    def get_user_by_id(self, user_id: UUID, tenant_id: UUID) -> TenantUser | None:
        return self.db.scalar(
            select(TenantUser)
            .options(joinedload(TenantUser.tenant))
            .where(TenantUser.id == user_id, TenantUser.tenant_id == tenant_id)
        )


class TenantService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_slug(self, slug: str) -> Tenant | None:
        return self.db.scalar(select(Tenant).where(Tenant.slug == slug))

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def create_tenant_with_owner(
        self,
        *,
        name: str,
        slug: str,
        owner_email: str,
        owner_name: str,
        owner_password: str,
        status: TenantStatus = TenantStatus.trial,
    ) -> tuple[Tenant, TenantUser]:
        if self.get_by_slug(slug) is not None:
            raise AppError("Tenant slug already exists", code="tenant_exists", status_code=409)

        tenant = Tenant(name=name, slug=slug, status=status)
        self.db.add(tenant)
        self.db.flush()

        owner = TenantUser(
            tenant_id=tenant.id,
            email=owner_email.lower(),
            name=owner_name,
            password_hash=hash_password(owner_password),
            role=TenantUserRole.owner,
            status=TenantUserStatus.active,
        )
        self.db.add(owner)
        self.db.commit()
        self.db.refresh(tenant)
        self.db.refresh(owner)
        return tenant, owner
