"""
PSC Alert model - Compliance Signal Engine

Actionable alerts from signals, linked to shipments/entries.
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class PSCAlertStatus(str, enum.Enum):
    """PSC alert status"""
    NEW = "new"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class PSCAlert(Base):
    """Actionable PSC alert from compliance signal"""

    __tablename__ = "psc_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("normalized_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True, index=True)
    shipment_item_id = Column(UUID(as_uuid=True), ForeignKey("shipment_items.id", ondelete="SET NULL"), nullable=True, index=True)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="SET NULL"), nullable=True, index=True)
    line_item_id = Column(UUID(as_uuid=True), ForeignKey("line_items.id", ondelete="SET NULL"), nullable=True, index=True)
    hts_code = Column(String(10), nullable=True, index=True)
    alert_type = Column(String(100), nullable=True)
    duty_delta_estimate = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    evidence_links = Column(JSONB, nullable=True)
    status = Column(SQLEnum(PSCAlertStatus, name="pscalertstatus", create_type=False), nullable=False, default=PSCAlertStatus.NEW, index=True)
    explanation = Column(JSONB, nullable=True)
    confidence_score = Column(Float, nullable=True)
    priority = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    signal_source = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    signal = relationship("NormalizedSignal", back_populates="psc_alerts")

    def __repr__(self):
        return f"<PSCAlert {self.alert_type} status={self.status.value}>"
