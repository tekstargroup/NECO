"""
Document model - Uploaded document tracking
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class DocumentType(str, enum.Enum):
    """Document type classification"""
    COMMERCIAL_INVOICE = "commercial_invoice"
    ENTRY_SUMMARY = "entry_summary"
    PACKING_LIST = "packing_list"
    BILL_OF_LADING = "bill_of_lading"
    CERTIFICATE_ORIGIN = "certificate_origin"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """Uploaded document tracking"""
    
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    
    # File information
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # Size in bytes
    mime_type = Column(String(100))
    
    # Document classification
    document_type = Column(
        SQLEnum(DocumentType),
        default=DocumentType.OTHER,
        nullable=False,
        index=True
    )
    
    # Processing status
    processing_status = Column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.UPLOADED,
        nullable=False,
        index=True
    )
    
    # Extracted data
    extracted_text = Column(Text)  # Full extracted text
    structured_data = Column(JSONB)  # Parsed structured data
    confidence_score = Column(Integer)  # 0-100
    
    # Linking
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id"), index=True)
    po_number = Column(String(50), index=True)
    
    # Processing metadata
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_error = Column(Text)
    processing_duration_seconds = Column(Integer)
    
    # Vector database
    vector_db_added = Column(Boolean, default=False)
    vector_db_chunk_count = Column(Integer)
    
    # Additional flexible data
    extra_data = Column(JSONB)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    client = relationship("Client", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.filename} ({self.document_type})>"

