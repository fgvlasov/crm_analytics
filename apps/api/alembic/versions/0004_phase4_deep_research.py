"""Phase 4: deep research job inputs and private evidence metadata.

Revision ID: 0004_phase4
Revises: 0003_phase3
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase4"
down_revision: Union[str, None] = "0003_phase3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessment_jobs", sa.Column("base_assessment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_assessment_jobs_base_assessment_id_lead_assessments"),
        "assessment_jobs",
        "lead_assessments",
        ["base_assessment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "assessment_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("short_quote", sa.String(length=500), nullable=True),
        sa.Column("claim_supported", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["lead_assessments.id"],
            name=op.f("fk_assessment_evidence_assessment_id_lead_assessments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_assessment_evidence_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_evidence")),
        sa.UniqueConstraint("object_key", name=op.f("uq_assessment_evidence_object_key")),
    )
    op.create_index(
        op.f("ix_assessment_evidence_tenant_id"),
        "assessment_evidence",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_assessment_evidence_assessment_id"),
        "assessment_evidence",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assessment_evidence_assessment_id"),
        table_name="assessment_evidence",
    )
    op.drop_index(
        op.f("ix_assessment_evidence_tenant_id"),
        table_name="assessment_evidence",
    )
    op.drop_table("assessment_evidence")
    op.drop_constraint(
        op.f("fk_assessment_jobs_base_assessment_id_lead_assessments"),
        "assessment_jobs",
        type_="foreignkey",
    )
    op.drop_column("assessment_jobs", "base_assessment_id")
