import enum
import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.tenant import Tenant


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class OdooConnectionMode(str, enum.Enum):
    module_callback = "module_callback"
    jsonrpc = "jsonrpc"
    xmlrpc = "xmlrpc"


class OdooInstanceStatus(str, enum.Enum):
    draft = "draft"
    connected = "connected"
    error = "error"
    disabled = "disabled"


class LeadSourceType(str, enum.Enum):
    odoo = "odoo"
    tender = "tender"
    web = "web"
    manual = "manual"
    api = "api"


class LeadStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    converted = "converted"
    lost = "lost"


class OdooInstance(TimestampMixin, Base):
    __tablename__ = "odoo_instances"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    odoo_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connection_mode: Mapped[OdooConnectionMode] = mapped_column(
        Enum(
            OdooConnectionMode,
            name="odoo_connection_mode",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=OdooConnectionMode.module_callback,
        nullable=False,
    )
    status: Mapped[OdooInstanceStatus] = mapped_column(
        Enum(
            OdooInstanceStatus,
            name="odoo_instance_status",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=OdooInstanceStatus.draft,
        nullable=False,
    )
    api_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship()
    leads: Mapped[list["Lead"]] = relationship(back_populates="odoo_instance")


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "odoo_instance_id",
            "odoo_model",
            "odoo_res_id",
            name="uq_leads_odoo_external",
        ),
        Index("ix_leads_tenant_source", "tenant_id", "source_type"),
        Index("ix_leads_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[LeadSourceType] = mapped_column(
        Enum(
            LeadSourceType,
            name="lead_source_type",
            values_callable=_enum_values,
            native_enum=False,
        ),
        default=LeadSourceType.odoo,
        nullable=False,
    )
    odoo_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("odoo_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    odoo_model: Mapped[str | None] = mapped_column(String(64), nullable=True, default="crm.lead")
    odoo_res_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    odoo_write_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    stage_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    salesperson_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", values_callable=_enum_values, native_enum=False),
        default=LeadStatus.active,
        nullable=False,
    )
    sync_status: Mapped[str] = mapped_column(String(32), default="synced", nullable=False)
    last_idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cached latest fast assessment summary (Phase 3) for list views
    latest_score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_temperature: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_assessment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_assessment_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship()
    odoo_instance: Mapped[OdooInstance | None] = relationship(back_populates="leads")


class OdooIdempotencyRecord(TimestampMixin, Base):
    """Deduplicate Odoo upsert / webhook events per tenant."""

    __tablename__ = "odoo_idempotency_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", "key", name="uq_odoo_idempotency_tenant_scope_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)


def hash_integration_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
