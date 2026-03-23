"""Import restriction model - GAP 3 FDA/Admissibility Engine"""

from sqlalchemy import Column, String, DateTime, Date, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from app.core.database import Base


class ImportRestriction(Base):
    """FDA/agency import restrictions for matching against shipments"""

    __tablename__ = "import_restrictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency = Column(String(100), nullable=False, index=True)
    product_keywords = Column(JSONB, nullable=True)
    hts_codes = Column(JSONB, nullable=True)
    country = Column(String(2), nullable=True, index=True)
    severity = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    effective_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
