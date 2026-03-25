"""
Review Record Model - Sprint 7

Enterprise trust layer for reviewing and overriding classification and PSC Radar outputs.

Key principles:
- Immutable snapshots
- Explicit state transitions
- Complete audit trail
- No mutations, only new records for overrides
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Tuple
import uuid
import enum

from app.core.database import Base


class ReviewableObjectType(str, enum.Enum):
    """Types of objects that can be reviewed."""
    CLASSIFICATION = "CLASSIFICATION"
    PSC_RADAR = "PSC_RADAR"


class ReviewStatus(str, enum.Enum):
    """Review status - finite state machine."""
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWED_ACCEPTED = "REVIEWED_ACCEPTED"
    REVIEWED_REJECTED = "REVIEWED_REJECTED"


class ReviewReasonCode(str, enum.Enum):
    """Reason codes for review actions."""
    # Creation
    AUTO_CREATED = "AUTO_CREATED"
    MANUAL_CREATION = "MANUAL_CREATION"
    
    # Review actions
    ACCEPTED_AS_IS = "ACCEPTED_AS_IS"
    REJECTED_INCORRECT = "REJECTED_INCORRECT"
    REJECTED_INSUFFICIENT_INFO = "REJECTED_INSUFFICIENT_INFO"
    
    # Override reasons
    OVERRIDE_MANUAL_CLASSIFICATION = "OVERRIDE_MANUAL_CLASSIFICATION"
    OVERRIDE_RISK_ACCEPTED = "OVERRIDE_RISK_ACCEPTED"
    OVERRIDE_EXPERT_JUDGMENT = "OVERRIDE_EXPERT_JUDGMENT"
    OVERRIDE_ADDITIONAL_EVIDENCE = "OVERRIDE_ADDITIONAL_EVIDENCE"


class ReviewRecord(Base):
    """
    Review record for classification or PSC Radar outputs.
    
    Immutable snapshot-based model with explicit state transitions.
    """
    
    __tablename__ = "review_records"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Object identification
    object_type = Column(
        SQLEnum(ReviewableObjectType),
        nullable=False,
        index=True
    )
    
    # Immutable snapshot (JSONB for flexibility)
    object_snapshot = Column(JSONB, nullable=False)

    # Per-item review decisions: { item_id: { status, notes, updated_at, updated_by } } (Sprint E)
    item_decisions = Column(JSONB, nullable=True)
    
    # HTS version (must match AUTHORITATIVE_HTS_VERSION_ID)
    hts_version_id = Column(String(36), nullable=False, index=True)
    
    # State machine
    status = Column(
        SQLEnum(ReviewStatus),
        nullable=False,
        default=ReviewStatus.DRAFT,
        index=True
    )
    
    # Creation metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by = Column(String(100), nullable=False)  # User ID or system
    
    # Review metadata (nullable until reviewed)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    reviewed_by = Column(String(100), nullable=True)  # User ID
    
    # Review details
    review_reason_code = Column(
        SQLEnum(ReviewReasonCode),
        nullable=True
    )
    review_notes = Column(Text, nullable=True)
    
    # Override linkage (if this is an override, link to original)
    override_of_review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("review_records.id"),
        nullable=True,
        index=True
    )
    
    # Relationships
    override_of = relationship(
        "ReviewRecord",
        remote_side=[id],
        backref="overrides"
    )
    regulatory_evaluations = relationship(
        "RegulatoryEvaluation",
        back_populates="review_record",
        cascade="all, delete-orphan"
    )
    exports = relationship(
        "Export",
        back_populates="review_record"
    )
    
    def __repr__(self):
        return f"<ReviewRecord {self.id} {self.object_type.value} {self.status.value}>"
    
    def can_transition_to(self, new_status: ReviewStatus, user_role: str) -> Tuple[bool, str]:
        """
        Check if state transition is valid.
        
        Returns:
            (is_valid, error_message)
        """
        # Terminal states cannot transition
        if self.status in [ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED]:
            return False, f"Cannot transition from terminal state {self.status.value}"
        
        # Only REVIEWER can finalize
        if new_status in [ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED]:
            if user_role != "REVIEWER":
                return False, f"Only REVIEWER can transition to {new_status.value}"
        
        # Valid transitions
        valid_transitions = {
            ReviewStatus.DRAFT: [ReviewStatus.REVIEW_REQUIRED, ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED],
            ReviewStatus.REVIEW_REQUIRED: [ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED],
        }
        
        if new_status not in valid_transitions.get(self.status, []):
            return False, f"Invalid transition from {self.status.value} to {new_status.value}"
        
        return True, ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "object_type": self.object_type.value,
            "status": self.status.value,
            "hts_version_id": self.hts_version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "review_reason_code": self.review_reason_code.value if self.review_reason_code else None,
            "review_notes": self.review_notes,
            "override_of_review_id": str(self.override_of_review_id) if self.override_of_review_id else None,
            "object_snapshot": self.object_snapshot
        }
