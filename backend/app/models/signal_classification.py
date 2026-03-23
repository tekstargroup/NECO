"""
Signal classification model - Compliance Signal Engine

Category and impact type for normalized signals.
"""

from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class SignalCategory(str, enum.Enum):
    """Signal category enum"""
    TARIFF_CHANGE = "TARIFF_CHANGE"
    HTS_UPDATE = "HTS_UPDATE"
    QUOTA_UPDATE = "QUOTA_UPDATE"
    SANCTION = "SANCTION"
    IMPORT_RESTRICTION = "IMPORT_RESTRICTION"
    RULING = "RULING"
    TRADE_ACTION = "TRADE_ACTION"
    DOCUMENTATION_RULE = "DOCUMENTATION_RULE"


class SignalClassification(Base):
    """Classification of a normalized signal"""

    __tablename__ = "signal_classifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(SQLEnum(SignalCategory, name="signalcategory", create_type=False), nullable=False, index=True)
    impact_type = Column(String(100), nullable=True)
    affected_entities = Column(JSONB, nullable=True)

    signal = relationship("NormalizedSignal", back_populates="classifications")

    def __repr__(self):
        return f"<SignalClassification {self.category.value}>"
