"""
Importer HTS usage model - Compliance Signal Engine

Derived HTS usage per organization for relevance scoring.
"""

from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class ImporterHTSUsage(Base):
    """HTS code usage per organization (for scoring)"""

    __tablename__ = "importer_hts_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    hts_code = Column(String(10), nullable=False, index=True)
    frequency = Column(Integer, nullable=False, default=0)
    total_value = Column(Numeric(15, 2), nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ImporterHTSUsage org={self.organization_id} hts={self.hts_code} freq={self.frequency}>"
