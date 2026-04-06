"""
Authoritative line-level provenance for shipment items (Patch B).

Created at structured-import time from Commercial Invoice / Entry Summary line_items.
Similarity/hash linking is fallback-only.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class LineProvenanceMappingMethod:
    """How the item-to-document line binding was established."""

    STRUCTURED_IMPORT_ES = "STRUCTURED_IMPORT_ES"
    STRUCTURED_IMPORT_CI = "STRUCTURED_IMPORT_CI"
    # PATCH B: User picked rows from extracted table UI (linked to source shipment document).
    USER_SELECTION_FROM_TABLE = "USER_SELECTION_FROM_TABLE"
    # PATCH B: Explicit manual provenance from API (document + line index).
    MANUAL_API = "MANUAL_API"


class ShipmentItemLineProvenance(Base):
    """
    One row per (item, source document, array index) from structured extraction.

    Multiple rows per item are normal when both ES and CI contribute to the same logical line.
    """

    __tablename__ = "shipment_item_line_provenance"
    __table_args__ = (
        UniqueConstraint(
            "shipment_item_id",
            "shipment_document_id",
            "line_index",
            name="uq_item_doc_line_index",
        ),
        {"comment": "Authoritative CI/ES line provenance for shipment items"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id"), nullable=False, index=True)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shipment_document_id = Column(
        UUID(as_uuid=True), ForeignKey("shipment_documents.id"), nullable=False, index=True
    )

    line_index = Column(Integer, nullable=False)  # index in structured_data.line_items array
    logical_line_number = Column(Integer, nullable=True)  # extracted line_number / business line

    raw_line_text = Column(Text, nullable=True)
    mapping_method = Column(String(64), nullable=False)
    structured_snapshot = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="item_line_provenance")
    item = relationship("ShipmentItem", back_populates="line_provenance")
    document = relationship("ShipmentDocument", back_populates="item_line_provenance")
    analysis = relationship("Analysis", foreign_keys=[analysis_id])
