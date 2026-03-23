"""
Normalized signal model - Compliance Signal Engine

Parsed and normalized signal with extracted metadata.
"""

from sqlalchemy import Column, String, DateTime, Date, Float, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class NormalizedSignal(Base):
    """Normalized signal with extracted HTS, countries, keywords"""

    __tablename__ = "normalized_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_signal_id = Column(UUID(as_uuid=True), ForeignKey("raw_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    signal_type = Column(String(50), nullable=True, index=True)
    countries = Column(JSONB, nullable=True)
    hts_codes = Column(JSONB, nullable=True)
    keywords = Column(JSONB, nullable=True)
    effective_date = Column(Date, nullable=True)
    confidence = Column(Float, nullable=True)
    # GAP 2 - Tariff mapping
    duty_rate_change = Column(Numeric(7, 4), nullable=True)
    affected_hts_codes = Column(JSONB, nullable=True)
    old_duty_rate = Column(Numeric(7, 4), nullable=True)
    new_duty_rate = Column(Numeric(7, 4), nullable=True)
    # GAP 1 - Quota
    quota_limit = Column(Numeric(15, 3), nullable=True)
    quota_used = Column(Numeric(15, 3), nullable=True)

    raw_signal = relationship("RawSignal", back_populates="normalized")
    classifications = relationship("SignalClassification", back_populates="signal", cascade="all, delete-orphan")
    scores = relationship("SignalScore", back_populates="signal", cascade="all, delete-orphan")
    psc_alerts = relationship("PSCAlert", back_populates="signal", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<NormalizedSignal {self.id}>"
