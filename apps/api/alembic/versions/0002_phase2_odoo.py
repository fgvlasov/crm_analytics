"""Phase 2: Odoo instances, leads, idempotency.

Revision ID: 0002_phase2
Revises: 0001_phase1
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2"
down_revision: Union[str, None] = "0001_phase1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "odoo_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("odoo_version", sa.String(length=32), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("module_version", sa.String(length=64), nullable=True),
        sa.Column("connection_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("api_token_hash", sa.String(length=128), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_odoo_instances_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_odoo_instances")),
    )
    op.create_index(op.f("ix_odoo_instances_tenant_id"), "odoo_instances", ["tenant_id"])

    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("odoo_instance_id", sa.Uuid(), nullable=True),
        sa.Column("odoo_model", sa.String(length=64), nullable=True),
        sa.Column("odoo_res_id", sa.String(length=64), nullable=True),
        sa.Column("odoo_write_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expected_revenue", sa.Numeric(14, 2), nullable=True),
        sa.Column("stage_name", sa.String(length=128), nullable=True),
        sa.Column("salesperson_name", sa.String(length=255), nullable=True),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("canonical_company_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["odoo_instance_id"],
            ["odoo_instances.id"],
            name=op.f("fk_leads_odoo_instance_id_odoo_instances"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_leads_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint(
            "tenant_id",
            "odoo_instance_id",
            "odoo_model",
            "odoo_res_id",
            name="uq_leads_odoo_external",
        ),
    )
    op.create_index(op.f("ix_leads_tenant_id"), "leads", ["tenant_id"])
    op.create_index(op.f("ix_leads_odoo_instance_id"), "leads", ["odoo_instance_id"])
    op.create_index("ix_leads_tenant_source", "leads", ["tenant_id", "source_type"])
    op.create_index("ix_leads_tenant_created", "leads", ["tenant_id", "created_at"])

    op.create_table(
        "odoo_idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_odoo_idempotency_records_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_odoo_idempotency_records")),
        sa.UniqueConstraint(
            "tenant_id", "scope", "key", name="uq_odoo_idempotency_tenant_scope_key"
        ),
    )
    op.create_index(
        op.f("ix_odoo_idempotency_records_tenant_id"),
        "odoo_idempotency_records",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_odoo_idempotency_records_tenant_id"),
        table_name="odoo_idempotency_records",
    )
    op.drop_table("odoo_idempotency_records")
    op.drop_index("ix_leads_tenant_created", table_name="leads")
    op.drop_index("ix_leads_tenant_source", table_name="leads")
    op.drop_index(op.f("ix_leads_odoo_instance_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_tenant_id"), table_name="leads")
    op.drop_table("leads")
    op.drop_index(op.f("ix_odoo_instances_tenant_id"), table_name="odoo_instances")
    op.drop_table("odoo_instances")
