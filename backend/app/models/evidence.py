"""
Evidence mapping models - structured evidence layer for NECO recommendations.

Per EVIDENCE_MAPPING_MODEL.md:
- SourceDocument: canonical document record
- DocumentPage: page-level tracking
- ExtractedField: structured field extraction
- AuthorityReference: CBP rulings, HTS notes, etc.
- RecommendationEvidenceLink: maps evidence to alternative HTS
- RecommendationSummary: final explanation payload per PSC row
"""

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Text, Boolean, Integer, Float, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base


class SourceDocument(Base):
    """Canonical document record for evidence layer. Links to shipment_documents."""

    __tablename__ = "source_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_document_id = Column(UUID(as_uuid=True), ForeignKey("shipment_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    document_type = Column(String(50), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_storage_url = Column(String(500), nullable=True)
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    parser_status = Column(String(50), nullable=True)
    page_count = Column(Integer, nullable=True)
    checksum = Column(String(64), nullable=True)

    pages = relationship("DocumentPage", back_populates="source_document", cascade="all, delete-orphan")
    extracted_fields = relationship("ExtractedField", back_populates="source_document", cascade="all, delete-orphan")


class DocumentPage(Base):
    """Page or logical section within a document."""

    __tablename__ = "document_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    image_url = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    source_document = relationship("SourceDocument", back_populates="pages")


class ExtractedField(Base):
    """Structured field extraction from documents."""

    __tablename__ = "extracted_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="SET NULL"), nullable=True, index=True)

    field_name = Column(String(100), nullable=False, index=True)
    field_value_raw = Column(Text, nullable=True)
    field_value_normalized = Column(Text, nullable=True)
    field_type = Column(String(50), nullable=True)
    extraction_method = Column(String(50), nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    bounding_box_json = Column(JSONB, nullable=True)
    row_reference = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    source_document = relationship("SourceDocument", back_populates="extracted_fields")


class AuthorityReference(Base):
    """External legal or regulatory support (CBP ruling, HTS note, etc.)."""

    __tablename__ = "authority_references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority_type = Column(String(50), nullable=False, index=True)
    reference_id = Column(String(100), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    url = Column(String(1000), nullable=True)
    effective_date = Column(Date, nullable=True)
    source_agency = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    hts_codes = Column(ARRAY(String), nullable=True)
    countries = Column(ARRAY(String), nullable=True)
    keywords = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RecommendationEvidenceLink(Base):
    """Maps evidence directly to an alternative HTS decision."""

    __tablename__ = "recommendation_evidence_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=True, index=True)
    declared_hts = Column(String(10), nullable=True, index=True)
    alternative_hts = Column(String(10), nullable=True, index=True)

    evidence_source_type = Column(String(50), nullable=False, index=True)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    extracted_field_id = Column(UUID(as_uuid=True), ForeignKey("extracted_fields.id", ondelete="SET NULL"), nullable=True, index=True)
    authority_reference_id = Column(UUID(as_uuid=True), ForeignKey("authority_references.id", ondelete="SET NULL"), nullable=True, index=True)

    evidence_role = Column(String(20), nullable=False, index=True)
    evidence_strength = Column(String(20), nullable=True)
    summary = Column(Text, nullable=True)
    detail_text = Column(Text, nullable=True)
    supports_declared = Column(Boolean, nullable=True)
    supports_alternative = Column(Boolean, nullable=True)
    is_conflicting = Column(Boolean, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RecommendationSummary(Base):
    """Final explanation payload for each row in PSC Radar."""

    __tablename__ = "recommendation_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=True, index=True)
    declared_hts = Column(String(10), nullable=True, index=True)
    alternative_hts = Column(String(10), nullable=True, index=True)

    estimated_savings = Column(Numeric(15, 2), nullable=True)
    estimated_savings_percent = Column(Float, nullable=True)
    evidence_strength = Column(String(20), nullable=True)
    review_level = Column(String(20), nullable=True)
    support_summary = Column(Text, nullable=True)
    risk_summary = Column(Text, nullable=True)
    next_step_summary = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
