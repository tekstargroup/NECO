"""Shipment item classification facts (Patch D — persisted facts layer)

Revision ID: 017_classification_facts
Revises: 016_line_provenance
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "017_classification_facts"
down_revision = "016_line_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shipment_item_classification_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_facts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("analysis_id", "shipment_item_id", name="uq_classification_facts_analysis_item"),
    )
    op.create_index(
        "ix_shipment_item_classification_facts_analysis",
        "shipment_item_classification_facts",
        ["analysis_id"],
    )
    op.create_index(
        "ix_shipment_item_classification_facts_item",
        "shipment_item_classification_facts",
        ["shipment_item_id"],
    )


def downgrade():
    op.drop_table("shipment_item_classification_facts")
