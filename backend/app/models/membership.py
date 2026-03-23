"""
Membership model - Sprint 12

User-Organization membership with roles (stored in NECO DB, not Clerk).
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User roles (stored in NECO DB, not Clerk)"""
    ANALYST = "ANALYST"  # Default role for importer users
    REVIEWER = "REVIEWER"
    ADMIN = "ADMIN"


class Membership(Base):
    """User-Organization membership with role"""
    
    __tablename__ = "memberships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Role (stored in NECO DB, not Clerk)
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.ANALYST,
        nullable=False,
        index=True
    )
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")
    
    # Unique constraint: one membership per user-org pair
    __table_args__ = (
        {"comment": "User-Organization membership with role. Roles stored in NECO DB, not Clerk."}
    )
    
    def __repr__(self):
        return f"<Membership user={self.user_id} org={self.organization_id} role={self.role.value}>"

