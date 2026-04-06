"""Optional analysis_id on line provenance for audit/replay alignment

Revision ID: 025_line_provenance_analysis_id
Revises: 024_regulatory_evaluations_analysis_scope
Create Date: 2026-04-03

Contract: rows remain shipment-scoped (unique item/doc/line). analysis_id is optional
metadata pointing at the analysis run used when the linkage was established or last validated.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "025_line_provenance_analysis_id"
down_revision = "024_regulatory_evaluations_analysis_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "shipment_item_line_provenance",
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_line_provenance_analysis_id",
        "shipment_item_line_provenance",
        ["analysis_id"],
    )

    op.execute(
        text(
            """
            UPDATE shipment_item_line_provenance p
            SET analysis_id = i.active_analysis_id
            FROM shipment_items i
            WHERE p.shipment_item_id = i.id
              AND i.active_analysis_id IS NOT NULL
            """
        )
    )


def downgrade():
    op.drop_index("ix_line_provenance_analysis_id", table_name="shipment_item_line_provenance")
    op.drop_column("shipment_item_line_provenance", "analysis_id")
