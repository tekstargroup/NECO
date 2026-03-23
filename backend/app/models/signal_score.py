"""
Signal score model - Compliance Signal Engine

Relevance scoring per organization.
"""

from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class SignalScore(Base):
    """Scored signal for an organization"""

    __tablename__ = "signal_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    relevance_score = Column(Integer, nullable=True)
    financial_impact_score = Column(Integer, nullable=True)
    urgency_score = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    final_score = Column(Float, nullable=True, index=True)

    signal = relationship("NormalizedSignal", back_populates="scores")

    def __repr__(self):
        return f"<SignalScore signal={self.signal_id} final={self.final_score}>"
