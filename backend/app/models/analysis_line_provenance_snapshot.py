"""Frozen line→document provenance per analysis run (audit-grade explanation context)."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AnalysisLineProvenanceSnapshot(Base):
    """
    One row per (analysis, item, document, line_index) at snapshot time.

    Replaces reading live `shipment_item_line_provenance` for analysis-scoped replay.
    Retry: delete-all-for-analysis then reinsert (see provenance_snapshot_persistence).
    """

    __tablename__ = "analysis_line_provenance_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "shipment_item_id",
            "shipment_document_id",
            "line_index",
            name="uq_analysis_line_prov_snapshot",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_document_id = Column(
        UUID(as_uuid=True), ForeignKey("shipment_documents.id", ondelete="CASCADE"), nullable=False
    )
    line_index = Column(Integer, nullable=False)
    logical_line_number = Column(Integer, nullable=True)
    mapping_method = Column(String(64), nullable=False)
    raw_line_text = Column(Text, nullable=True)
    structured_snapshot = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analysis = relationship("Analysis", back_populates="line_provenance_snapshots")
    shipment = relationship("Shipment")
    item = relationship("ShipmentItem")
