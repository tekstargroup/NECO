"""
Regulatory Evaluation Models - Side Sprint A

Evidence-driven regulatory applicability evaluation.

Key principles:
- HTS codes trigger questions, not conclusions
- Conditions must be evaluated with evidence
- Flags are suppressed when evidence negates applicability
- REVIEW_REQUIRED when evidence is missing or ambiguous
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class Regulator(str, enum.Enum):
    """Regulatory bodies."""
    EPA = "EPA"  # Environmental Protection Agency (Pesticides/Biocides)
    FDA = "FDA"  # Food and Drug Administration
    LACEY_ACT = "LACEY_ACT"  # Lacey Act (Plant-based materials)


class RegulatoryOutcome(str, enum.Enum):
    """Regulatory applicability outcome."""
    APPLIES = "APPLIES"  # Flag applies - regulatory requirements exist
    SUPPRESSED = "SUPPRESSED"  # Flag suppressed - evidence negates applicability
    CONDITIONAL = "CONDITIONAL"  # Conditional - requires review due to missing/ambiguous evidence


class ConditionState(str, enum.Enum):
    """Condition evaluation state."""
    CONFIRMED_TRUE = "CONFIRMED_TRUE"  # Evidence supports condition
    CONFIRMED_FALSE = "CONFIRMED_FALSE"  # Evidence negates condition
    UNKNOWN = "UNKNOWN"  # No evidence or ambiguous


class RegulatoryEvaluation(Base):
    """
    Regulatory applicability evaluation persisted per analysis run.

    Primary access for replay/exports: ``analysis_id``. ``review_id`` links the workflow/review row.
    ``shipment_item_id`` ties the evaluation to a line when the engine emitted ``item_id``.
    """

    __tablename__ = "regulatory_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_id = Column(UUID(as_uuid=True), ForeignKey("review_records.id"), nullable=False, index=True)
    shipment_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipment_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Regulatory body
    regulator = Column(SQLEnum(Regulator), nullable=False, index=True)
    
    # Evaluation outcome
    outcome = Column(SQLEnum(RegulatoryOutcome), nullable=False, index=True)
    
    # Explanation (traceable logic with cited evidence)
    explanation_text = Column(Text, nullable=False)
    
    # HTS code that triggered this evaluation
    triggered_by_hts_code = Column(String(10), nullable=False, index=True)
    
    # Metadata
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    evaluation_version = Column(String(20), default="1.0")  # Track engine version
    
    # Relationships
    analysis = relationship("Analysis", back_populates="regulatory_evaluations")
    review_record = relationship("ReviewRecord", back_populates="regulatory_evaluations")
    shipment_item = relationship("ShipmentItem", foreign_keys=[shipment_item_id])
    conditions = relationship(
        "RegulatoryCondition",
        back_populates="evaluation",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<RegulatoryEvaluation {self.regulator.value}: {self.outcome.value} for HTS {self.triggered_by_hts_code}>"


class RegulatoryCondition(Base):
    """
    Individual condition evaluation within a regulatory evaluation.
    
    Links to specific evidence (documents, pages, snippets).
    """
    
    __tablename__ = "regulatory_conditions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("regulatory_evaluations.id"), nullable=False, index=True)
    
    # Condition identification
    condition_id = Column(String(100), nullable=False, index=True)  # e.g., "INTENDED_PESTICIDAL_USE"
    condition_description = Column(Text)  # Human-readable description
    
    # Evaluation state
    state = Column(SQLEnum(ConditionState), nullable=False, index=True)
    
    # Evidence references (JSON array)
    # Each evidence ref: {"document_id": "...", "page_number": 1, "snippet": "..."}
    # Using server_default from migration ('[]'::jsonb), so no ORM default needed (avoids mutable default issue)
    evidence_refs = Column(JSONB, server_default=text("'[]'::jsonb"))  # Array of evidence references
    
    # Metadata
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    evaluation = relationship("RegulatoryEvaluation", back_populates="conditions")
    
    def __repr__(self):
        return f"<RegulatoryCondition {self.condition_id}: {self.state.value}>"
