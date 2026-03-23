"""
SKU model - Product/Item tracking
"""

from sqlalchemy import Column, String, DateTime, Numeric, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class SKU(Base):
    """SKU/Product model"""
    
    __tablename__ = "skus"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    
    # SKU identification
    sku_code = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Classification
    hts_declared = Column(String(10), index=True)
    country_of_origin = Column(String(2), index=True)
    
    # Valuation
    average_value = Column(Numeric(12, 2))
    currency = Column(String(3), default="USD")
    
    # Statistics
    last_imported_date = Column(DateTime)
    total_entries_count = Column(Integer, default=0)
    total_quantity_imported = Column(Numeric(15, 3))
    annual_volume = Column(Integer)  # Number of shipments per year
    
    # Additional data
    supplier_name = Column(String(255))
    manufacturer_name = Column(String(255))
    
    # Additional attributes (flexible JSON field)
    additional_data = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="skus")
    line_items = relationship("LineItem", back_populates="sku")
    classification_alternatives = relationship("ClassificationAlternative", back_populates="sku")
    classification_audits = relationship("ClassificationAudit", back_populates="sku")
    
    def __repr__(self):
        return f"<SKU {self.sku_code}: {self.description[:50]}>"

