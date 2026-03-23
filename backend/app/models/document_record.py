"""
Document Record Model - Sprint 10

Persistent record for ingested documents.

Key principles:
- Read-only storage
- Hash-based deduplication
- Tokenized representation
- Evidence tracking
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()


class DocumentRecord(Base):
    """Persistent document record."""
    
    __tablename__ = "document_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String, unique=True, nullable=False, index=True)
    document_type = Column(String, nullable=False)  # COMMERCIAL_INVOICE, PACKING_LIST, TECHNICAL_SPEC
    filename = Column(String, nullable=False)
    document_hash = Column(String, nullable=False, index=True)  # SHA256 hash for deduplication
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_at = Column(DateTime, nullable=True)
    page_count = Column(Integer, nullable=True)
    
    # Tokenized representation and text spans
    tokenized_content = Column(JSON, nullable=True)  # Structured token representation
    text_spans = Column(JSON, nullable=True)  # Page-by-page text with bbox info
    
    # Document metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    document_metadata = Column(JSON, nullable=True)  # Additional metadata
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "document_id": self.document_id,
            "document_type": self.document_type,
            "filename": self.filename,
            "document_hash": self.document_hash,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
            "page_count": self.page_count,
            "tokenized_content": self.tokenized_content,
            "text_spans": self.text_spans,
            "document_metadata": self.document_metadata
        }
