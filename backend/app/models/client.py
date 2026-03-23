"""
Client model - Multi-tenant support
"""

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    """Subscription tier levels"""
    TIER_1_CLASSIFICATION = "tier_1_classification"
    TIER_2_PRESHIPMENT = "tier_2_preshipment"
    TIER_3_AUDIT = "tier_3_audit"
    TIER_4_FULLSERVICE = "tier_4_fullservice"


class Client(Base):
    """Client/Importer model"""
    
    __tablename__ = "clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=False, index=True)
    importer_number = Column(String(50), unique=True, index=True)
    
    subscription_tier = Column(
        SQLEnum(SubscriptionTier),
        default=SubscriptionTier.TIER_1_CLASSIFICATION,
        nullable=False
    )
    
    # Contact information
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    
    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    country = Column(String(2), default="US")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="client", cascade="all, delete-orphan")
    skus = relationship("SKU", back_populates="client", cascade="all, delete-orphan")
    entries = relationship("Entry", back_populates="client", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="client", cascade="all, delete-orphan")
    classification_audits = relationship("ClassificationAudit", back_populates="client")
    
    def __repr__(self):
        return f"<Client {self.company_name}>"


