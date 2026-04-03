"""
Patch D — Persisted normalized classification facts per shipment line item per analysis run.

Facts are produced before / alongside HTS prediction; stable across re-runs (new analysis_id).

Cardinality / constraint:
    Exactly one row per (analysis_id, shipment_item_id); see uq_classification_facts_analysis_item.
    Re-executing the pipeline for the same analysis_id without removing prior rows will violate
    that unique constraint (e.g. Celery retry or accidental double-invoke). New runs normally
    use a new Analysis row (new analysis_id); see AnalysisOrchestrationService.start_analysis.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ShipmentItemClassificationFacts(Base):
    """
    One row per (analysis, shipment_item): durable fact bundle for audit and chat.

    `facts_json` matches `build_classification_facts_payload` output (schema_version, facts, missing_facts, ...).

    Retries: Inserts assume a fresh analysis_id per run. Same analysis_id + same item twice → DB unique
    violation unless facts rows are deleted first or replaced (not automatic here).
    """

    __tablename__ = "shipment_item_classification_facts"
    __table_args__ = (
        UniqueConstraint("analysis_id", "shipment_item_id", name="uq_classification_facts_analysis_item"),
        {"comment": "Normalized classification facts before HTS prediction (Patch D)"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="CASCADE"), nullable=False, index=True)

    facts_json = Column(JSONB, nullable=False)
    missing_facts_json = Column(JSONB, nullable=False, default=list)  # redundant list for queries / dashboards
    schema_version = Column(String(16), nullable=False, default="1")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    analysis = relationship("Analysis", back_populates="item_classification_facts")
    shipment = relationship("Shipment")
    item = relationship("ShipmentItem")
