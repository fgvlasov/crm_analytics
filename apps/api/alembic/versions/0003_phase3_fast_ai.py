"""Phase 3: AI providers, assessments, jobs, and lead score cache columns.

Revision ID: 0003_phase3
Revises: 0002_phase2
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase3"
down_revision: Union[str, None] = "0002_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("latest_score_total", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("latest_temperature", sa.String(length=32), nullable=True))
    op.add_column(
        "leads", sa.Column("latest_assessment_status", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "leads", sa.Column("latest_assessment_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("leads", sa.Column("latest_summary", sa.Text(), nullable=True))

    op.create_table(
        "ai_provider_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("default_model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_ai_provider_connections_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_provider_connections")),
    )
    op.create_index(
        op.f("ix_ai_provider_connections_tenant_id"),
        "ai_provider_connections",
        ["tenant_id"],
    )

    op.create_table(
        "assessment_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("workflow", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("force", sa.Boolean(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_assessment_jobs_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_provider_connections.id"],
            name=op.f("fk_assessment_jobs_provider_id_ai_provider_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_assessment_jobs_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_jobs")),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_assessment_jobs_tenant_idem"
        ),
    )
    op.create_index(op.f("ix_assessment_jobs_tenant_id"), "assessment_jobs", ["tenant_id"])
    op.create_index(op.f("ix_assessment_jobs_lead_id"), "assessment_jobs", ["lead_id"])
    op.create_index(op.f("ix_assessment_jobs_status"), "assessment_jobs", ["status"])

    op.create_table(
        "lead_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("workflow", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("score_total", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("project_type", sa.String(length=128), nullable=True),
        sa.Column("customer_industry", sa.String(length=128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("deep_research_recommended", sa.Boolean(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("odoo_callback_status", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["assessment_jobs.id"],
            name=op.f("fk_lead_assessments_job_id_assessment_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_assessments_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_provider_connections.id"],
            name=op.f("fk_lead_assessments_provider_id_ai_provider_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_lead_assessments_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_assessments")),
    )
    op.create_index(op.f("ix_lead_assessments_tenant_id"), "lead_assessments", ["tenant_id"])
    op.create_index(op.f("ix_lead_assessments_lead_id"), "lead_assessments", ["lead_id"])
    op.create_index(
        op.f("ix_lead_assessments_input_fingerprint"),
        "lead_assessments",
        ["input_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_assessments_input_fingerprint"), table_name="lead_assessments")
    op.drop_index(op.f("ix_lead_assessments_lead_id"), table_name="lead_assessments")
    op.drop_index(op.f("ix_lead_assessments_tenant_id"), table_name="lead_assessments")
    op.drop_table("lead_assessments")
    op.drop_index(op.f("ix_assessment_jobs_status"), table_name="assessment_jobs")
    op.drop_index(op.f("ix_assessment_jobs_lead_id"), table_name="assessment_jobs")
    op.drop_index(op.f("ix_assessment_jobs_tenant_id"), table_name="assessment_jobs")
    op.drop_table("assessment_jobs")
    op.drop_index(
        op.f("ix_ai_provider_connections_tenant_id"), table_name="ai_provider_connections"
    )
    op.drop_table("ai_provider_connections")
    op.drop_column("leads", "latest_summary")
    op.drop_column("leads", "latest_assessment_at")
    op.drop_column("leads", "latest_assessment_status")
    op.drop_column("leads", "latest_temperature")
    op.drop_column("leads", "latest_score_total")
