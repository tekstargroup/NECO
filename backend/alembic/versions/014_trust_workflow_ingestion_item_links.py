"""Trust workflow: ingestion observability + item-document links + review item decisions

Revision ID: 014_trust
Revises: 013_evidence_mapping
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014_trust"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shipment_documents", sa.Column("extraction_method", sa.String(32), nullable=True))
    op.add_column("shipment_documents", sa.Column("ocr_used", sa.Boolean(), nullable=True))
    op.add_column("shipment_documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("shipment_documents", sa.Column("char_count", sa.Integer(), nullable=True))
    op.add_column("shipment_documents", sa.Column("table_detected", sa.Boolean(), nullable=True))
    op.add_column("shipment_documents", sa.Column("extraction_status", sa.String(32), nullable=True))
    op.add_column("shipment_documents", sa.Column("usable_for_analysis", sa.Boolean(), nullable=True))
    op.add_column(
        "shipment_documents",
        sa.Column("data_sheet_user_confirmed", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "shipment_item_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipment_items.id"), nullable=False),
        sa.Column("shipment_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipment_documents.id"), nullable=False),
        sa.Column("mapping_status", sa.String(32), nullable=False, server_default="AUTO"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_shipment_item_documents_shipment_id", "shipment_item_documents", ["shipment_id"])
    op.create_index("ix_shipment_item_documents_item", "shipment_item_documents", ["shipment_item_id"])
    op.create_index("ix_shipment_item_documents_doc", "shipment_item_documents", ["shipment_document_id"])

    op.add_column(
        "review_records",
        sa.Column("item_decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("review_records", "item_decisions")
    op.drop_index("ix_shipment_item_documents_doc", table_name="shipment_item_documents")
    op.drop_index("ix_shipment_item_documents_item", table_name="shipment_item_documents")
    op.drop_index("ix_shipment_item_documents_shipment_id", table_name="shipment_item_documents")
    op.drop_table("shipment_item_documents")
    op.drop_column("shipment_documents", "data_sheet_user_confirmed")
    op.drop_column("shipment_documents", "usable_for_analysis")
    op.drop_column("shipment_documents", "extraction_status")
    op.drop_column("shipment_documents", "table_detected")
    op.drop_column("shipment_documents", "char_count")
    op.drop_column("shipment_documents", "page_count")
    op.drop_column("shipment_documents", "ocr_used")
    op.drop_column("shipment_documents", "extraction_method")
