"""
User model - Authentication and authorization
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class User(Base):
    """User model for authentication (Sprint 12: Clerk integration)"""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True)  # Nullable for Sprint 12 migration
    
    # Clerk integration (Sprint 12)
    # NOTE: Nullable in DB for migration, but required in service layer (no anonymous users)
    clerk_user_id = Column(String(255), unique=True, nullable=True, index=True)  # Clerk user ID (required for Sprint 12)
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable if using Clerk
    full_name = Column(String(255))
    
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)
    
    # Relationships
    client = relationship("Client", back_populates="users")
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")  # Sprint 12
    entitlements = relationship("Entitlement", back_populates="user", cascade="all, delete-orphan")  # Sprint 12
    
    def __repr__(self):
        return f"<User {self.email} (Clerk: {self.clerk_user_id})>"


