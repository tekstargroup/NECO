"""Product HTS knowledge layer — stores accepted classifications per product hash.

This model supports knowledge reuse across shipments while maintaining
a clear audit boundary: prior decisions are offered as suggestions,
never silently applied as classifications.
"""

from sqlalchemy import Column, String, DateTime, Float, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class ProductHTSMap(Base):
    """Maps products (by description hash) to previously accepted HTS codes."""

    __tablename__ = "product_hts_map"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    description_hash = Column(String(64), nullable=False, index=True)
    description_text = Column(Text, nullable=True)
    hts_code = Column(String(10), nullable=False, index=True)
    hts_heading = Column(String(4), nullable=True)
    country_of_origin = Column(String(3), nullable=True)

    confidence = Column(Float, nullable=True)
    source = Column(String(50), nullable=False, default="review_accepted")

    source_review_id = Column(UUID(as_uuid=True), nullable=True)
    source_shipment_id = Column(UUID(as_uuid=True), nullable=True)
    source_item_id = Column(UUID(as_uuid=True), nullable=True)

    provenance = Column(JSONB, nullable=True)

    accepted_by = Column(String(255), nullable=True)
    accepted_at = Column(DateTime, nullable=True)

    superseded = Column(Boolean, nullable=False, default=False)
    superseded_by_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
