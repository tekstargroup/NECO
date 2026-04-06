"""Regulatory evaluations: analysis_id + shipment_item_id for analysis-scoped access

Revision ID: 024_regulatory_evaluations_analysis_scope
Revises: 023_analysis_item_reasoning_traces
Create Date: 2026-04-03

Primary access path for loads: analysis_id. review_id retained for workflow/history FK.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "024_regulatory_evaluations_analysis_scope"
down_revision = "023_analysis_item_reasoning_traces"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "regulatory_evaluations",
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "regulatory_evaluations",
        sa.Column(
            "shipment_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipment_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_regulatory_evaluations_analysis_id", "regulatory_evaluations", ["analysis_id"])
    op.create_index(
        "ix_regulatory_evaluations_analysis_item",
        "regulatory_evaluations",
        ["analysis_id", "shipment_item_id"],
    )

    op.execute(
        text(
            """
            UPDATE regulatory_evaluations re
            SET analysis_id = rr.analysis_id
            FROM review_records rr
            WHERE re.review_id = rr.id
              AND rr.analysis_id IS NOT NULL
            """
        )
    )

    # Rows that could not be linked (legacy) are removed — they cannot be replayed safely.
    op.execute(
        text(
            """
            DELETE FROM regulatory_conditions
            WHERE evaluation_id IN (
                SELECT id FROM regulatory_evaluations WHERE analysis_id IS NULL
            )
            """
        )
    )
    op.execute(text("DELETE FROM regulatory_evaluations WHERE analysis_id IS NULL"))

    op.alter_column("regulatory_evaluations", "analysis_id", nullable=False)


def downgrade():
    op.alter_column("regulatory_evaluations", "analysis_id", nullable=True)
    op.drop_index("ix_regulatory_evaluations_analysis_item", table_name="regulatory_evaluations")
    op.drop_index("ix_regulatory_evaluations_analysis_id", table_name="regulatory_evaluations")
    op.drop_column("regulatory_evaluations", "shipment_item_id")
    op.drop_column("regulatory_evaluations", "analysis_id")
