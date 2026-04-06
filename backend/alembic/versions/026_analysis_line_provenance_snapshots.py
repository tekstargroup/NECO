"""Immutable per-analysis line provenance snapshots for replay (Phase 2c)

Revision ID: 026_analysis_line_provenance_snapshots
Revises: 025_line_provenance_analysis_id
Create Date: 2026-04-03

Shipment-scoped `shipment_item_line_provenance` remains the live import truth.
This table freezes the links that applied to a given analysis_id so later shipment
edits do not rewrite historical explanation context.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "026_analysis_line_provenance_snapshots"
down_revision = "025_line_provenance_analysis_id"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_line_provenance_snapshots",
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
        sa.Column(
            "shipment_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipment_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("logical_line_number", sa.Integer(), nullable=True),
        sa.Column("mapping_method", sa.String(length=64), nullable=False),
        sa.Column("raw_line_text", sa.Text(), nullable=True),
        sa.Column("structured_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "analysis_id",
            "shipment_item_id",
            "shipment_document_id",
            "line_index",
            name="uq_analysis_line_prov_snapshot",
        ),
    )
    op.create_index(
        "ix_analysis_line_prov_snap_analysis",
        "analysis_line_provenance_snapshots",
        ["analysis_id"],
    )
    op.create_index(
        "ix_analysis_line_prov_snap_item",
        "analysis_line_provenance_snapshots",
        ["shipment_item_id"],
    )


def downgrade():
    op.drop_index("ix_analysis_line_prov_snap_item", table_name="analysis_line_provenance_snapshots")
    op.drop_index("ix_analysis_line_prov_snap_analysis", table_name="analysis_line_provenance_snapshots")
    op.drop_table("analysis_line_provenance_snapshots")
