"""
Organization model - Sprint 12

Multi-tenant organizations (mapped to Clerk orgs).
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Organization(Base):
    """Organization model (maps to Clerk organization)"""
    
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Clerk integration
    clerk_org_id = Column(String(255), unique=True, nullable=False, index=True)  # Clerk organization ID
    
    # Organization details
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, index=True)  # URL-friendly identifier
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Organization {self.name} (Clerk: {self.clerk_org_id})>"

