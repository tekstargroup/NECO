"""
Entitlement Service - Sprint 12

Monthly entitlement tracking (15 shipments per user per month).
Period: calendar month in America/New_York timezone.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.entitlement import Entitlement
from app.models.shipment import Shipment
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)

# America/New_York timezone for monthly reset
NY_TZ = ZoneInfo("America/New_York")


class EntitlementService:
    """Service for managing monthly entitlements (15 shipments/user/month)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _get_period_start(self, dt: Optional[datetime] = None) -> date:
        """
        Get period start (first day of calendar month in America/New_York).
        
        Args:
            dt: Datetime (default: now in NY timezone)
        
        Returns:
            First day of month as date
        """
        if dt is None:
            dt = datetime.now(NY_TZ)
        else:
            # Convert to NY timezone if needed
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=NY_TZ)
            else:
                dt = dt.astimezone(NY_TZ)
        
        # First day of month
        return date(dt.year, dt.month, 1)
    
    async def get_or_create(
        self,
        user_id: UUID,
        period_start: Optional[date] = None
    ) -> Entitlement:
        """
        Get or create entitlement for user and period.
        
        Args:
            user_id: User ID
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            Entitlement record
        """
        if period_start is None:
            period_start = self._get_period_start()
        
        # Try to get existing
        result = await self.db.execute(
            select(Entitlement).where(
                and_(
                    Entitlement.user_id == user_id,
                    Entitlement.period_start == period_start
                )
            )
        )
        entitlement = result.scalar_one_or_none()
        
        if entitlement:
            return entitlement
        
        # Create new
        entitlement = Entitlement(
            user_id=user_id,
            period_start=period_start,
            shipments_used=0,
            shipments_limit=15
        )
        self.db.add(entitlement)
        await self.db.flush()
        
        logger.info(f"Created entitlement for user {user_id} period {period_start}")
        
        return entitlement
    
    async def check_entitlement(
        self,
        user_id: UUID,
        period_start: Optional[date] = None
    ) -> tuple[bool, Optional[Entitlement]]:
        """
        Check if user has entitlement available.
        
        Args:
            user_id: User ID
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            (has_entitlement, entitlement_record)
        """
        entitlement = await self.get_or_create(user_id, period_start)
        
        has_entitlement = entitlement.shipments_used < entitlement.shipments_limit
        
        return has_entitlement, entitlement
    
    async def _is_unlimited_user(self, user_id: UUID) -> bool:
        """Check if user has unlimited entitlement (e.g. testing accounts)."""
        emails_raw = getattr(settings, "ENTITLEMENT_UNLIMITED_EMAILS", "") or ""
        emails = [e.strip().lower() for e in emails_raw.split(",") if e.strip()]
        if not emails:
            return False
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user and user.email and user.email.strip().lower() in emails

    async def check_entitlement_available(
        self,
        user_id: UUID,
        period_start: Optional[date] = None
    ) -> tuple[bool, Entitlement]:
        """
        Check entitlement availability (does not increment).
        
        Used at shipment creation to check quota before allowing creation.
        Increment happens at analysis start (increment_on_analysis_start).
        
        Args:
            user_id: User ID
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            (has_entitlement, entitlement_record)
        
        Note: Does not raise exception - returns bool for flexibility
        """
        # Unlimited users (e.g. testing) bypass limit
        if await self._is_unlimited_user(user_id):
            entitlement = await self.get_or_create(user_id, period_start)
            return True, entitlement

        entitlement = await self.get_or_create(user_id, period_start)
        
        # Check if exceeded (do not increment here)
        has_entitlement = entitlement.shipments_used < entitlement.shipments_limit
        
        return has_entitlement, entitlement
    
    async def require_entitlement_available(
        self,
        user_id: UUID,
        period_start: Optional[date] = None
    ) -> Entitlement:
        """
        Require entitlement availability (raises if exceeded).
        
        Used at shipment creation to check quota before allowing creation.
        
        Args:
            user_id: User ID
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            Entitlement record
        
        Raises:
            HTTPException: 403 if entitlement exceeded
        """
        if await self._is_unlimited_user(user_id):
            return await self.get_or_create(user_id, period_start)
        has_entitlement, entitlement = await self.check_entitlement_available(user_id, period_start)
        
        if not has_entitlement:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ENTITLEMENT_EXCEEDED",
                    "message": f"Monthly limit of {entitlement.shipments_limit} shipments exceeded",
                    "shipments_used": entitlement.shipments_used,
                    "shipments_limit": entitlement.shipments_limit,
                    "period_start": entitlement.period_start.isoformat()
                }
            )
        
        return entitlement
    
    async def increment_on_analysis_start(
        self,
        user_id: UUID,
        shipment_id: UUID,
        period_start: Optional[date] = None
    ) -> Entitlement:
        """
        Increment entitlement usage on analysis start.
        
        This is when quota is consumed (not at shipment creation).
        Prevents burning quota on drafts that are never analyzed.
        
        Args:
            user_id: User ID
            shipment_id: Shipment ID (for logging)
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            Updated entitlement record
        
        Raises:
            HTTPException: 403 if entitlement exceeded
        """
        # Unlimited users (e.g. testing) bypass limit and do not increment
        if await self._is_unlimited_user(user_id):
            return await self.get_or_create(user_id, period_start)

        entitlement = await self.get_or_create(user_id, period_start)
        
        # Check if exceeded
        if entitlement.shipments_used >= entitlement.shipments_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ENTITLEMENT_EXCEEDED",
                    "message": f"Monthly limit of {entitlement.shipments_limit} shipments exceeded",
                    "shipments_used": entitlement.shipments_used,
                    "shipments_limit": entitlement.shipments_limit,
                    "period_start": entitlement.period_start.isoformat()
                }
            )
        
        # Increment (only at analysis start)
        entitlement.shipments_used += 1
        await self.db.flush()
        
        logger.info(f"Incremented entitlement for user {user_id} shipment {shipment_id} at analysis start: {entitlement.shipments_used}/{entitlement.shipments_limit}")
        
        return entitlement
    
    async def get_current_usage(
        self,
        user_id: UUID,
        period_start: Optional[date] = None
    ) -> dict:
        """
        Get current entitlement usage for user.
        
        Args:
            user_id: User ID
            period_start: Period start date (default: current month first day in NY timezone)
        
        Returns:
            Usage information dict
        """
        entitlement = await self.get_or_create(user_id, period_start)
        
        return {
            "user_id": str(user_id),
            "period_start": entitlement.period_start.isoformat(),
            "shipments_used": entitlement.shipments_used,
            "shipments_limit": entitlement.shipments_limit,
            "remaining": entitlement.shipments_limit - entitlement.shipments_used,
            "has_entitlement": entitlement.shipments_used < entitlement.shipments_limit
        }
