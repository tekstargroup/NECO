"""
PSC Opportunity model - Post Summary Correction tracking
"""

from sqlalchemy import Column, String, DateTime, Numeric, Integer, ForeignKey, Text, Enum as SQLEnum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class PSCStatus(str, enum.Enum):
    """PSC opportunity status"""
    IDENTIFIED = "identified"
    UNDER_REVIEW = "under_review"
    APPROVED_TO_FILE = "approved_to_file"
    FILED = "filed"
    APPROVED = "approved"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


class PSCOpportunity(Base):
    """PSC opportunity tracking"""
    
    __tablename__ = "psc_opportunities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id"), nullable=False, index=True)
    line_item_id = Column(UUID(as_uuid=True), ForeignKey("line_items.id"), nullable=False, index=True)
    alternative_id = Column(UUID(as_uuid=True), ForeignKey("classification_alternatives.id"), index=True)
    
    # Savings calculation
    potential_savings = Column(Numeric(12, 2), nullable=False)
    expected_savings = Column(Numeric(12, 2))  # After considering risk
    actual_savings = Column(Numeric(12, 2))  # After resolution
    
    # Priority
    priority_score = Column(Integer, index=True)  # Calculated priority (0-100)
    days_to_liquidation = Column(Integer, index=True)  # Days remaining
    
    # Risk
    risk_level = Column(String(20))  # LOW, MEDIUM, HIGH
    risk_score = Column(Integer)  # 1-10
    
    # Status tracking
    status = Column(
        SQLEnum(PSCStatus),
        default=PSCStatus.IDENTIFIED,
        nullable=False,
        index=True
    )
    
    # Filing information
    filed_date = Column(Date)
    filed_by = Column(String(100))
    psc_reference_number = Column(String(50))
    
    # Resolution
    resolution_date = Column(Date)
    resolution_notes = Column(Text)
    
    # Analysis
    current_hts = Column(String(10))
    proposed_hts = Column(String(10))
    justification_summary = Column(Text)
    
    # Notes
    internal_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entry = relationship("Entry", back_populates="psc_opportunities")
    line_item = relationship("LineItem", back_populates="psc_opportunities")
    
    def __repr__(self):
        return f"<PSCOpportunity Entry:{self.entry_id} Savings:${self.potential_savings}>"


