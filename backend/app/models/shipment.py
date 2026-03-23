"""
Shipment model - Sprint 12

Primary object for importer workflow.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class ShipmentStatus(str, enum.Enum):
    """Shipment status (kept simple - derived/updated by analysis workflow)"""
    DRAFT = "DRAFT"
    READY = "READY"  # Eligible docs present
    ANALYZING = "ANALYZING"
    COMPLETE = "COMPLETE"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


class Shipment(Base):
    """Shipment - primary object for importer workflow"""
    
    __tablename__ = "shipments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Organization (tenant isolation)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Creator
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Shipment details
    name = Column(String(255), nullable=False, index=True)
    # Status derived/updated by analysis workflow (users cannot set it)
    status = Column(
        SQLEnum(ShipmentStatus),
        default=ShipmentStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="shipments")
    references = relationship("ShipmentReference", back_populates="shipment", cascade="all, delete-orphan")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")
    # RESTRICT delete for documents/analyses - audit history should not be cascade deleted
    documents = relationship("ShipmentDocument", back_populates="shipment")  # No cascade - RESTRICT at FK level
    analyses = relationship("Analysis", back_populates="shipment")  # No cascade - RESTRICT at FK level
    
    def __repr__(self):
        return f"<Shipment {self.name} ({self.status.value})>"


class ShipmentReference(Base):
    """Key/value reference pairs for shipments (PO, Entry, Invoice, BOL, etc.)"""
    
    __tablename__ = "shipment_references"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    
    # Key/value pair
    reference_type = Column(String(50), nullable=False, index=True)  # e.g., "PO", "ENTRY", "INVOICE", "BOL"
    reference_value = Column(String(255), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="references")
    
    # Unique constraint: one reference per type per shipment
    __table_args__ = (
        {"comment": "Key/value reference pairs for shipments (PO, Entry, Invoice, BOL, etc.)"}
    )
    
    def __repr__(self):
        return f"<ShipmentReference {self.reference_type}={self.reference_value}>"


class ShipmentItem(Base):
    """Items within a shipment"""
    
    __tablename__ = "shipment_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    
    # Item details
    label = Column(String(255), nullable=False)  # Item label/description
    declared_hts = Column(String(10), nullable=True, index=True)  # Optional declared HTS code
    supplemental_evidence_text = Column(Text, nullable=True)  # Extracted text from Amazon scrape or PDF
    supplemental_evidence_source = Column(String(50), nullable=True)  # 'amazon_url' or 'pdf'
    value = Column(String(50))  # Value (stored as string to handle currencies)
    currency = Column(String(3), default="USD")  # Currency code (ISO 4217)
    quantity = Column(String(50))  # Quantity (stored as string for flexibility)
    unit_of_measure = Column(String(20))  # UOM (PCS, KG, etc.)
    country_of_origin = Column(String(2))  # Country of origin (ISO 3166-1 alpha-2)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="items")
    
    def __repr__(self):
        return f"<ShipmentItem {self.label} (HTS: {self.declared_hts})>"

