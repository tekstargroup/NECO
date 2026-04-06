"""Phase 2 — canonical heading reasoning trace per analysis line (JSONB, idempotent upsert)."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AnalysisItemReasoningTrace(Base):
    """
    One row per (analysis, shipment_item): durable reasoning trace for audit/replay.

    Retries: ON CONFLICT (analysis_id, shipment_item_id) DO UPDATE — safe for Celery retries.
    """

    __tablename__ = "analysis_item_reasoning_traces"
    __table_args__ = (
        UniqueConstraint("analysis_id", "shipment_item_id", name="uq_reasoning_trace_analysis_item"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=False, index=True)

    trace_json = Column(JSONB, nullable=False)
    schema_version = Column(String(16), nullable=False, default="1")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    analysis = relationship("Analysis", back_populates="item_reasoning_traces")
    shipment = relationship("Shipment")
    item = relationship("ShipmentItem")
