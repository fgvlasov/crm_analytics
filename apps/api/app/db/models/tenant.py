import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TenantStatus(str, enum.Enum):
    active = "active"
    trial = "trial"
    suspended = "suspended"
    cancelled = "cancelled"


class TenantUserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    sales_manager = "sales_manager"
    sales_user = "sales_user"
    analyst = "analyst"
    auditor = "auditor"


class TenantUserStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    disabled = "disabled"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status", values_callable=_enum_values, native_enum=False),
        default=TenantStatus.active,
        nullable=False,
    )
    primary_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Helsinki", nullable=False)

    users: Mapped[list["TenantUser"]] = relationship(back_populates="tenant")
    secrets: Mapped[list["SecretRef"]] = relationship(back_populates="tenant")


class TenantUser(TimestampMixin, Base):
    __tablename__ = "tenant_users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_tenant_users_tenant_email"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[TenantUserRole] = mapped_column(
        Enum(
            TenantUserRole,
            name="tenant_user_role",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=TenantUserRole.sales_user,
        nullable=False,
    )
    status: Mapped[TenantUserStatus] = mapped_column(
        Enum(
            TenantUserStatus,
            name="tenant_user_status",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=TenantUserStatus.active,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class SecretRef(TimestampMixin, Base):
    """Encrypted secret storage. Plaintext is never returned by API."""

    __tablename__ = "secret_refs"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_secret_refs_tenant_name"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False, default="generic")
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="secrets")
