"""
Links shipment line items to evidence documents (Sprint C — explicit mapping).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ItemDocumentMappingStatus:
    AUTO = "AUTO"
    USER_CONFIRMED = "USER_CONFIRMED"
    REJECTED = "REJECTED"


class ShipmentItemDocument(Base):
    __tablename__ = "shipment_item_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id"), nullable=False, index=True)
    shipment_document_id = Column(UUID(as_uuid=True), ForeignKey("shipment_documents.id"), nullable=False, index=True)
    mapping_status = Column(String(32), nullable=False, default=ItemDocumentMappingStatus.AUTO)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="item_document_links")
    item = relationship("ShipmentItem", back_populates="document_links")
    document = relationship("ShipmentDocument", back_populates="item_links")
