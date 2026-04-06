"""Analysis-scoped heading reasoning traces (JSONB, upsert per item)

Revision ID: 023_analysis_item_reasoning_traces
Revises: 022_backfill_classification_fact_stages_from_legacy
Create Date: 2026-04-03

Canonical structured trace per (analysis_id, shipment_item_id) for replay and audits.
result_json.items[].heading_reasoning_trace remains a derived projection for API compatibility.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "023_analysis_item_reasoning_traces"
down_revision = "022_backfill_classification_fact_stages_from_legacy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_item_reasoning_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shipment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "shipment_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipment_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trace_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("analysis_id", "shipment_item_id", name="uq_reasoning_trace_analysis_item"),
    )
    op.create_index("ix_reasoning_trace_analysis", "analysis_item_reasoning_traces", ["analysis_id"])
    op.create_index("ix_reasoning_trace_item", "analysis_item_reasoning_traces", ["shipment_item_id"])
    op.create_index(
        "ix_reasoning_trace_org_analysis",
        "analysis_item_reasoning_traces",
        ["organization_id", "analysis_id"],
    )


def downgrade():
    op.drop_index("ix_reasoning_trace_org_analysis", table_name="analysis_item_reasoning_traces")
    op.drop_index("ix_reasoning_trace_item", table_name="analysis_item_reasoning_traces")
    op.drop_index("ix_reasoning_trace_analysis", table_name="analysis_item_reasoning_traces")
    op.drop_table("analysis_item_reasoning_traces")
