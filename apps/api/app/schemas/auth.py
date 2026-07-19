from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.tenant import TenantStatus, TenantUserRole, TenantUserStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    tenant_slug: str = Field(min_length=2, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: TenantStatus
    primary_country: str | None
    timezone: str
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    email: EmailStr
    name: str
    role: TenantUserRole
    status: TenantUserStatus
    last_login_at: datetime | None
    created_at: datetime


class MeResponse(BaseModel):
    user: UserOut
    tenant: TenantOut


class FeaturesResponse(BaseModel):
    features: dict[str, bool]


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    purpose: str = Field(default="generic", max_length=100)
    value: str = Field(min_length=1)


class SecretOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    purpose: str
    key_version: str
    created_at: datetime
    updated_at: datetime
