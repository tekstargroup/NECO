"""
Raw signal model - Compliance Signal Engine

Stores raw ingestion from RSS/API sources.
"""

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class RawSignal(Base):
    """Raw signal from external feed (RSS, API, scrape)"""

    __tablename__ = "raw_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    url = Column(String(1000), nullable=False, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    normalized = relationship("NormalizedSignal", back_populates="raw_signal", uselist=False)

    def __repr__(self):
        return f"<RawSignal {self.source} {self.title[:50]}>"
