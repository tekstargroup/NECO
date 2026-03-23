"""
Export Model - Sprint 12

Tracks export artifacts stored in S3.
Exports are immutable once created.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class ExportType(str, enum.Enum):
    """Export types."""
    AUDIT_PACK = "AUDIT_PACK"
    BROKER_PREP = "BROKER_PREP"


class ExportStatus(str, enum.Enum):
    """Export generation status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class Export(Base):
    """Export record tracking"""
    
    __tablename__ = "exports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to review record
    review_id = Column(UUID(as_uuid=True), ForeignKey("review_records.id"), nullable=False, index=True)
    
    # Export metadata
    export_type = Column(SQLEnum(ExportType), nullable=False, index=True)
    status = Column(SQLEnum(ExportStatus), default=ExportStatus.PENDING, nullable=False, index=True)
    
    # S3 storage
    s3_key = Column(String(500), nullable=False, unique=True)
    s3_bucket = Column(String(255), nullable=False)
    file_size = Column(String(50))  # Size in bytes as string
    sha256_hash = Column(String(64))  # SHA256 hash of the export artifact
    
    # Blocker information (if blocked)
    blocked_reason = Column(Text, nullable=True)
    blockers = Column(JSONB, nullable=True)  # Array of blocker strings
    
    # Error information (if failed)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    
    # Created by
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    review_record = relationship("ReviewRecord", back_populates="exports")
    
    def __repr__(self):
        return f"<Export {self.id} {self.export_type.value} {self.status.value}>"
