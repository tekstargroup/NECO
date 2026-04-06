"""
Analysis model - Sprint 12

Analysis runs for shipments (Celery job orchestration).
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Boolean
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


class DecisionStatus(str, enum.Enum):
    """
    Outcome semantics after execution completes (Phase 1 — orthogonal to execution status).

    TRUSTED: full pipeline success without review-forcing blockers (see derive in analysis_identity_service).
    """

    TRUSTED = "TRUSTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


class Analysis(Base):
    """Analysis run for a shipment"""
    
    __tablename__ = "analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    
    # Organization (tenant isolation - prefer stored for faster scoping)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Execution status (queued / running / failed / complete / refused — see AnalysisStatus)
    status = Column(
        SQLEnum(AnalysisStatus),
        default=AnalysisStatus.QUEUED,
        nullable=False,
        index=True
    )

    # Phase 1 — one execution per row; monotonic version per shipment
    version = Column(Integer, nullable=False, default=1)
    # Decision outcome once execution finishes (nullable while running / legacy rows)
    decision_status = Column(SQLEnum(DecisionStatus), nullable=True, index=True)
    supersedes_analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True)
    # Exactly one active completed analysis per shipment (promoted explicitly after successful pipeline)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    
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
    # Pointer from analysis row → review snapshot row (distinct from ReviewRecord.analysis_id which links review → analysis run).
    review_record = relationship(
        "ReviewRecord",
        primaryjoin="Analysis.review_record_id==ReviewRecord.id",
        foreign_keys=[review_record_id],
    )
    item_classification_facts = relationship(
        "ShipmentItemClassificationFacts",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    item_reasoning_traces = relationship(
        "AnalysisItemReasoningTrace",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    regulatory_evaluations = relationship(
        "RegulatoryEvaluation",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    line_provenance_snapshots = relationship(
        "AnalysisLineProvenanceSnapshot",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    active_for_shipment_items = relationship(
        "ShipmentItem",
        foreign_keys="ShipmentItem.active_analysis_id",
        back_populates="active_analysis",
    )

    def __repr__(self):
        return f"<Analysis {self.id} ({self.status.value})>"

