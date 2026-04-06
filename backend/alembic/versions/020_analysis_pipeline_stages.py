"""Analysis pipeline stages — one row per (analysis_id, stage) for truth + retries

Revision ID: 020_analysis_pipeline_stages
Revises: 019_phase1_active_integrity
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "020_analysis_pipeline_stages"
down_revision = "019_phase1_active_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE pipelinestagestatus AS ENUM (
                'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'SKIPPED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    status_enum = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        name="pipelinestagestatus",
        create_type=False,
    )
    op.create_table(
        "analysis_pipeline_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="PENDING"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("analysis_id", "stage", name="uq_pipeline_stages_analysis_stage"),
    )
    op.create_index("ix_pipeline_stages_analysis", "analysis_pipeline_stages", ["analysis_id"])
    op.create_index("ix_pipeline_stages_shipment", "analysis_pipeline_stages", ["shipment_id"])


def downgrade():
    op.drop_index("ix_pipeline_stages_shipment", table_name="analysis_pipeline_stages")
    op.drop_index("ix_pipeline_stages_analysis", table_name="analysis_pipeline_stages")
    op.drop_table("analysis_pipeline_stages")
    op.execute("DROP TYPE IF EXISTS pipelinestagestatus")
