"""
Entry and LineItem models - Entry tracking
"""

from sqlalchemy import Column, String, DateTime, Numeric, Integer, Boolean, ForeignKey, Text, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.core.database import Base


class Entry(Base):
    """Customs Entry model"""
    
    __tablename__ = "entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    
    # Entry identification
    entry_number = Column(String(20), unique=True, nullable=False, index=True)
    entry_type = Column(String(2), index=True)  # 01, 03, 11, 23, etc.
    entry_date = Column(Date, nullable=False, index=True)
    
    # Liquidation tracking
    liquidation_date = Column(Date, index=True)  # entry_date + 314 days
    is_liquidated = Column(Boolean, default=False, index=True)
    actual_liquidation_date = Column(Date)
    
    # Filing information
    filer = Column(String(100))  # Broker/filer name
    port_of_entry = Column(String(10), index=True)
    
    # Totals
    total_entered_value = Column(Numeric(15, 2))
    total_duty_paid = Column(Numeric(15, 2))
    
    # Additional data
    additional_data = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="entries")
    line_items = relationship("LineItem", back_populates="entry", cascade="all, delete-orphan")
    psc_opportunities = relationship("PSCOpportunity", back_populates="entry")
    
    def calculate_liquidation_date(self):
        """Calculate liquidation date (entry_date + 314 days)"""
        if self.entry_date:
            self.liquidation_date = self.entry_date + timedelta(days=314)
    
    def days_to_liquidation(self):
        """Calculate days remaining until liquidation"""
        if self.is_liquidated:
            return 0
        if self.liquidation_date:
            delta = self.liquidation_date - datetime.now().date()
            return max(0, delta.days)
        return None
    
    def __repr__(self):
        return f"<Entry {self.entry_number}>"


class LineItem(Base):
    """Entry line item model"""
    
    __tablename__ = "line_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id"), nullable=False, index=True)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("skus.id"), index=True)
    
    # Line identification
    line_number = Column(Integer, nullable=False)
    
    # Product information
    description = Column(Text, nullable=False)
    hts_code = Column(String(10), nullable=False, index=True)
    country_of_origin = Column(String(2), index=True)
    
    # Quantity
    quantity = Column(Numeric(15, 3))
    unit = Column(String(20))
    
    # Valuation
    unit_price = Column(Numeric(12, 2))
    entered_value = Column(Numeric(12, 2), nullable=False)
    
    # Duty
    duty_rate = Column(Numeric(7, 4))  # e.g., 4.9000 for 4.9%
    duty_amount = Column(Numeric(12, 2))
    
    # Section 301/232
    section_301_applicable = Column(Boolean, default=False)
    section_301_rate = Column(Numeric(7, 4))
    section_232_applicable = Column(Boolean, default=False)
    section_232_rate = Column(Numeric(7, 4))
    
    # ADD/CVD
    add_cvd_applicable = Column(Boolean, default=False)
    add_cvd_rate = Column(Numeric(7, 4))
    add_cvd_case_number = Column(String(50))
    
    # Additional data
    additional_data = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    entry = relationship("Entry", back_populates="line_items")
    sku = relationship("SKU", back_populates="line_items")
    classification_alternatives = relationship("ClassificationAlternative", back_populates="line_item")
    psc_opportunities = relationship("PSCOpportunity", back_populates="line_item")
    
    def __repr__(self):
        return f"<LineItem {self.entry_id} Line {self.line_number}>"

