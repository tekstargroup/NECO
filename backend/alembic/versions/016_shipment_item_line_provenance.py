"""Shipment item line provenance (Patch B — authoritative CI/ES lineage at import)

Revision ID: 016_line_provenance
Revises: 015_product_knowledge
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "016_line_provenance"
down_revision = "015_product_knowledge"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shipment_item_line_provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "shipment_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipment_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_index", sa.Integer(), nullable=False),
        sa.Column("logical_line_number", sa.Integer(), nullable=True),
        sa.Column("raw_line_text", sa.Text(), nullable=True),
        sa.Column("mapping_method", sa.String(length=64), nullable=False),
        sa.Column("structured_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("shipment_item_id", "shipment_document_id", "line_index", name="uq_item_doc_line_index"),
    )
    op.create_index(
        "ix_shipment_item_line_provenance_shipment",
        "shipment_item_line_provenance",
        ["shipment_id"],
    )
    op.create_index(
        "ix_shipment_item_line_provenance_item",
        "shipment_item_line_provenance",
        ["shipment_item_id"],
    )
    op.create_index(
        "ix_shipment_item_line_provenance_document",
        "shipment_item_line_provenance",
        ["shipment_document_id"],
    )


def downgrade():
    op.drop_table("shipment_item_line_provenance")
