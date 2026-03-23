"""
Classification Audit model - Audit trail for classification decisions
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ClassificationAudit(Base):
    """Audit trail for classification engine decisions"""
    
    __tablename__ = "classification_audit"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=True, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True)
    
    # Input data
    input_description = Column(Text, nullable=False)
    input_coo = Column(String(2))  # Country of Origin
    input_value = Column(String(50))  # Product value
    input_qty = Column(String(50))  # Quantity
    input_current_hts = Column(String(10))  # Current HTS code if provided
    
    # Engine metadata
    engine_version = Column(String(20), default="v1.0")
    analysis_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Context and LLM interaction
    context_payload = Column(JSONB)  # Full context from ClassificationContextBuilder
    prompt = Column(Text)  # LLM prompt (if used in future)
    response = Column(Text)  # LLM response (if used in future)
    
    # Provenance
    provenance = Column(JSONB)  # Source pages, code IDs, etc.
    
    # Results summary
    candidates_generated = Column(String(10))  # Number of candidates
    top_candidate_hts = Column(String(10))  # Top recommended HTS code
    top_candidate_score = Column(String(20))  # Top candidate score
    
    # Additional metadata
    processing_time_ms = Column(String(20))  # Processing time in milliseconds
    error_message = Column(Text)  # Error if processing failed
    
    # Audit replayability fields
    applied_filters = Column(JSONB)  # List of filters applied: ["exclude_9903_text", "exclude_ch98_99", "exclude_noisy_desc"]
    candidate_counts = Column(JSONB)  # {"pre_filter_count": int, "post_filter_count": int, "post_score_count": int}
    similarity_top = Column(String(20))  # Best similarity score
    threshold_used = Column(String(20))  # Confidence threshold used (e.g., "0.18")
    reason_code = Column(String(50))  # Reason for rejection: "LOW_SIMILARITY_GATE", "NO_GOOD_MATCH", etc.
    status = Column(String(50))  # Status: "SUCCESS", "NO_CONFIDENT_MATCH", "NO_GOOD_MATCH", "CLARIFICATION_REQUIRED", etc.
    
    # Product analysis and clarification fields
    product_analysis = Column(JSONB)  # Full product analysis output (extracted attributes, missing attributes, etc.)
    clarification_questions = Column(JSONB)  # Questions asked to user: [{"attribute": "housing_material", "question": "..."}]
    clarification_responses = Column(JSONB)  # User responses: {"housing_material": "plastic", ...}
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    sku = relationship("SKU", back_populates="classification_audits")
    client = relationship("Client", back_populates="classification_audits")
    
    def __repr__(self):
        return f"<ClassificationAudit {self.id} for SKU {self.sku_id}>"

