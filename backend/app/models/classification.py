"""
Classification Alternative model - HTS code alternatives
"""

from sqlalchemy import Column, String, DateTime, Numeric, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ClassificationAlternative(Base):
    """Alternative HTS classification suggestions"""
    
    __tablename__ = "classification_alternatives"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=True, index=True)
    line_item_id = Column(UUID(as_uuid=True), ForeignKey("line_items.id"), index=True)
    
    # Alternative classification
    alternative_hts = Column(String(10), nullable=False, index=True)
    
    # Duty impact
    current_duty = Column(Numeric(12, 2))
    alternative_duty = Column(Numeric(12, 2))
    duty_difference = Column(Numeric(12, 2))  # Positive = savings
    
    # Risk assessment
    risk_score = Column(Integer)  # 1-10, where 10 is highest risk
    confidence_score = Column(Numeric(3, 2))  # 0.00-1.00
    
    # Justification
    justification = Column(Text)  # GRI analysis, reasoning
    gri_analysis = Column(Text)  # Specific GRI application
    
    # Supporting evidence
    supporting_rulings = Column(JSONB)  # Array of ruling references
    contradicting_rulings = Column(JSONB)  # Rulings that contradict this
    explanatory_notes = Column(Text)  # Relevant HTS notes
    
    # Recommendation
    is_recommended = Column(Integer, default=0)  # 0=not recommended, 1=alternative, 2=primary recommendation
    recommendation_reason = Column(Text)
    
    # Source tracking
    created_by = Column(String(50))  # 'system' or user_id
    analysis_version = Column(String(20))  # Track which version of engine created this
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    sku = relationship("SKU", back_populates="classification_alternatives")
    line_item = relationship("LineItem", back_populates="classification_alternatives")
    
    def __repr__(self):
        return f"<ClassificationAlternative {self.alternative_hts} (Risk: {self.risk_score}/10)>"


