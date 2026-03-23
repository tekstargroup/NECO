"""Quota status model - GAP 1 Quota Intelligence Engine"""

from sqlalchemy import Column, String, DateTime, Date, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


class QuotaStatus(Base):
    """Structured quota data from signals"""

    __tablename__ = "quota_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hts_code = Column(Text, nullable=False, index=True)
    country = Column(Text, nullable=True, index=True)
    quota_type = Column(Text, nullable=True)
    quota_limit = Column(Numeric(15, 3), nullable=True)
    quantity_used = Column(Numeric(15, 3), nullable=True)
    fill_rate = Column(Numeric(5, 4), nullable=True)
    status = Column(String(20), nullable=True, index=True)  # open, near_limit, filled
    effective_date = Column(Date, nullable=True)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    source_signal_id = Column(UUID(as_uuid=True), nullable=True, index=True)
