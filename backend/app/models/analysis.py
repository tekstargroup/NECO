"""
Analysis model - Sprint 12

Analysis runs for shipments (Celery job orchestration).
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class AnalysisStatus(str, enum.Enum):
    """Analysis status"""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    REFUSED = "REFUSED"  # Eligibility gate failed


class RefusalReasonCode(str, enum.Enum):
    """Reason codes for analysis refusal (small, stable enum + text field for detail)"""
    INSUFFICIENT_DOCUMENTS = "INSUFFICIENT_DOCUMENTS"  # Entry Summary OR (Commercial Invoice + Data Sheet) required
    ENTITLEMENT_EXCEEDED = "ENTITLEMENT_EXCEEDED"  # Monthly limit (15 shipments) exceeded
    OTHER = "OTHER"  # Use refusal_reason_text for detail


class Analysis(Base):
    """Analysis run for a shipment"""
    
    __tablename__ = "analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    
    # Organization (tenant isolation - prefer stored for faster scoping)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Status
    status = Column(
        SQLEnum(AnalysisStatus),
        default=AnalysisStatus.QUEUED,
        nullable=False,
        index=True
    )
    
    # Refusal information (if status = REFUSED)
    refusal_reason_code = Column(SQLEnum(RefusalReasonCode), nullable=True)
    refusal_reason_text = Column(Text, nullable=True)
    
    # Celery job tracking
    celery_task_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Timing
    queued_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Error information (if status = FAILED)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)  # Stack traces, context (internal only)
    
    # Analysis result (Sprint 11 view JSON)
    result_json = Column(JSONB, nullable=True)  # Full analysis result for rendering Sprint 11 view
    
    # Review record link (created at end of analysis)
    # RESTRICT delete - review_records should not be cascade deleted
    review_record_id = Column(UUID(as_uuid=True), ForeignKey("review_records.id", ondelete="RESTRICT"), nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="analyses")
    review_record = relationship("ReviewRecord", backref="analyses")
    item_classification_facts = relationship(
        "ShipmentItemClassificationFacts",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self):
        return f"<Analysis {self.id} ({self.status.value})>"

