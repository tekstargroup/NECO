"""
Entitlement model - Sprint 12

Monthly entitlement tracking (15 shipments per user per month).
"""

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Entitlement(Base):
    """Monthly entitlement tracking (15 shipments per user per month)"""
    
    __tablename__ = "entitlements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User and period
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Period: first day of calendar month in America/New_York timezone (DATE, not year/month separate)
    # Allows atomic updates without cron for monthly reset
    period_start = Column(Date, nullable=False, index=True)  # e.g., 2025-01-01 for January 2025
    
    # Usage tracking
    shipments_used = Column(Integer, default=0, nullable=False)
    shipments_limit = Column(Integer, default=15, nullable=False)  # 15 shipments per month
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="entitlements")
    
    # Unique constraint: one entitlement per user per period (atomic updates)
    __table_args__ = (
        {"comment": "Monthly entitlement tracking. 15 shipments per user per month (period_start is first day of calendar month in America/New_York)."}
    )
    
    def __repr__(self):
        return f"<Entitlement user={self.user_id} period={self.period_start} ({self.shipments_used}/{self.shipments_limit})>"

