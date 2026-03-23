"""
ShipmentDocument model - Sprint 12

Links documents to shipments with S3 metadata (immutable blobs).
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import enum

from app.core.database import Base


class ShipmentDocumentType(str, enum.Enum):
    """Document types for shipments"""
    ENTRY_SUMMARY = "ENTRY_SUMMARY"  # CBP 7501 or 3461 PDF
    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE"
    PACKING_LIST = "PACKING_LIST"
    DATA_SHEET = "DATA_SHEET"  # Datasheet PDF for regulatory evaluation


class ShipmentDocument(Base):
    """Document linked to a shipment (immutable S3 blob)"""
    
    __tablename__ = "shipment_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False, index=True)
    
    # Organization (tenant isolation - prefer stored for faster scoping)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Document type
    document_type = Column(
        SQLEnum(ShipmentDocumentType),
        nullable=False,
        index=True
    )
    
    # File metadata
    filename = Column(String(255), nullable=False)
    file_size = Column(String(20))  # Size in bytes (string for flexibility)
    mime_type = Column(String(100), default="application/pdf")
    
    # S3 storage (immutable)
    s3_key = Column(String(500), nullable=False, unique=True, index=True)  # S3 object key
    sha256_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 hash for deduplication
    
    # Retention (60 days from upload)
    retention_expires_at = Column(DateTime, nullable=False, index=True)
    
    # Upload metadata
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Processing status (optional, for compatibility with existing document processor)
    processing_status = Column(String(50), default="UPLOADED")  # UPLOADED, PROCESSING, COMPLETED, FAILED
    processing_error = Column(String(500))  # Error message if processing failed
    
    # Extracted data (cached after processing)
    extracted_text = Column(Text)  # Full extracted text
    structured_data = Column(JSONB)  # Structured data (JSONB)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    shipment = relationship("Shipment", back_populates="documents")
    
    # Immutable: no update/delete of blob (soft delete via status if needed later)
    __table_args__ = (
        {"comment": "Documents linked to shipments. Blobs are immutable. Use soft delete if needed."}
    )
    
    def __repr__(self):
        return f"<ShipmentDocument {self.filename} ({self.document_type.value})>"

