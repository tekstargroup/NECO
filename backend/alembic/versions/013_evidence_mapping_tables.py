"""Evidence mapping tables - source_documents, document_pages, extracted_fields, authority_references, recommendation_evidence_links, recommendation_summaries

Revision ID: 013
Revises: 012
Create Date: 2026-02-24

Implements structured evidence layer per EVIDENCE_MAPPING_MODEL.md:
- source_documents: canonical document record (links to shipment_documents)
- document_pages: page-level tracking
- extracted_fields: structured field extraction
- authority_references: CBP rulings, HTS notes, etc.
- recommendation_evidence_links: maps evidence to alternative HTS
- recommendation_summaries: final explanation payload per PSC row
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # source_documents - canonical document record for evidence layer
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sourcedocumenttype AS ENUM (
                'ENTRY_SUMMARY',
                'COMMERCIAL_INVOICE',
                'PACKING_LIST',
                'BILL_OF_LADING',
                'BROKER_WORKSHEET',
                'OTHER'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("shipment_document_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("document_type", sa.String(50), nullable=False, index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_storage_url", sa.String(500), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), index=True),
        sa.Column("parser_status", sa.String(50), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_document_id"], ["shipment_documents.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_source_documents_shipment", "source_documents", ["shipment_id"])

    # document_pages
    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_document_pages_source", "document_pages", ["source_document_id"])

    # extracted_fields
    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("field_name", sa.String(100), nullable=False, index=True),
        sa.Column("field_value_raw", sa.Text(), nullable=True),
        sa.Column("field_value_normalized", sa.Text(), nullable=True),
        sa.Column("field_type", sa.String(50), nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("bounding_box_json", postgresql.JSONB(), nullable=True),
        sa.Column("row_reference", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shipment_item_id"], ["shipment_items.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_extracted_fields_doc", "extracted_fields", ["source_document_id"])
    op.create_index("idx_extracted_fields_item", "extracted_fields", ["shipment_item_id"])

    # authority_references
    op.create_table(
        "authority_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("authority_type", sa.String(50), nullable=False, index=True),
        sa.Column("reference_id", sa.String(100), nullable=True, index=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_agency", sa.String(100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("hts_codes", postgresql.ARRAY(sa.String(10)), nullable=True),
        sa.Column("countries", postgresql.ARRAY(sa.String(2)), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_authority_references_type", "authority_references", ["authority_type"])

    # recommendation_evidence_links
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE evidencesourcetype AS ENUM (
                'DOCUMENT_FIELD',
                'DOCUMENT_PAGE',
                'REGULATORY_REFERENCE',
                'CBP_RULING',
                'SIGNAL',
                'HISTORICAL_PATTERN',
                'MANUAL_NOTE'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE evidencerole AS ENUM (
                'SUPPORTING',
                'CONFLICTING',
                'CONTEXTUAL',
                'WARNING'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE evidencestrength AS ENUM (
                'STRONG',
                'MODERATE',
                'WEAK'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "recommendation_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("declared_hts", sa.String(10), nullable=True, index=True),
        sa.Column("alternative_hts", sa.String(10), nullable=True, index=True),
        sa.Column("evidence_source_type", sa.String(50), nullable=False, index=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("extracted_field_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("authority_reference_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("evidence_role", sa.String(20), nullable=False, index=True),
        sa.Column("evidence_strength", sa.String(20), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detail_text", sa.Text(), nullable=True),
        sa.Column("supports_declared", sa.Boolean(), nullable=True),
        sa.Column("supports_alternative", sa.Boolean(), nullable=True),
        sa.Column("is_conflicting", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_item_id"], ["shipment_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["page_id"], ["document_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["extracted_field_id"], ["extracted_fields.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["authority_reference_id"], ["authority_references.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_rec_evidence_links_item", "recommendation_evidence_links", ["shipment_item_id"])
    op.create_index("idx_rec_evidence_links_shipment", "recommendation_evidence_links", ["shipment_id"])

    # recommendation_summaries
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE reviewlevel AS ENUM (
                'LOW',
                'MEDIUM',
                'HIGH',
                'BLOCKING'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.create_table(
        "recommendation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("shipment_item_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("declared_hts", sa.String(10), nullable=True, index=True),
        sa.Column("alternative_hts", sa.String(10), nullable=True, index=True),
        sa.Column("estimated_savings", sa.Numeric(15, 2), nullable=True),
        sa.Column("estimated_savings_percent", sa.Float(), nullable=True),
        sa.Column("evidence_strength", sa.String(20), nullable=True),
        sa.Column("review_level", sa.String(20), nullable=True),
        sa.Column("support_summary", sa.Text(), nullable=True),
        sa.Column("risk_summary", sa.Text(), nullable=True),
        sa.Column("next_step_summary", sa.Text(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_item_id"], ["shipment_items.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_rec_summaries_item", "recommendation_summaries", ["shipment_item_id"])
    op.create_index("idx_rec_summaries_shipment", "recommendation_summaries", ["shipment_id"])


def downgrade():
    op.drop_table("recommendation_summaries")
    op.drop_table("recommendation_evidence_links")
    op.drop_table("extracted_fields")
    op.drop_table("document_pages")
    op.drop_table("source_documents")
    op.drop_table("authority_references")
    op.execute("DROP TYPE IF EXISTS reviewlevel")
    op.execute("DROP TYPE IF EXISTS evidencestrength")
    op.execute("DROP TYPE IF EXISTS evidencerole")
    op.execute("DROP TYPE IF EXISTS evidencesourcetype")
    op.execute("DROP TYPE IF EXISTS sourcedocumenttype")
