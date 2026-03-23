"""CBP Ruling model - GAP 4 CBP CROSS Rulings"""

from sqlalchemy import Column, String, DateTime, Date, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class CBPRuling(Base):
    """CBP CROSS ruling with HTS mapping"""

    __tablename__ = "cbp_rulings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ruling_number = Column(String(50), nullable=False, index=True)
    hts_codes = Column(JSONB, nullable=True)
    description = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    ruling_date = Column(Date, nullable=True)
    source_url = Column(String(1000), nullable=True)
    raw_signal_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
