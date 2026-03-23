"""
Regulatory Updates API - Compliance Signal Engine

List signals (raw/normalized), filter by tag, date range.
Trigger signal processing (normalize, classify, score, create alerts).
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.models.raw_signal import RawSignal
from app.models.normalized_signal import NormalizedSignal
from app.services.psc_alert_service import process_raw_signals_for_org
from app.services.importer_hts_usage_service import refresh_importer_hts_usage
from app.services.regulatory_feed_poller import poll_regulatory_feeds

router = APIRouter()


@router.get("/regulatory-updates")
async def get_regulatory_updates(
    tag: Optional[str] = Query(None, description="Filter by tag (duty, section_301, tariff, etc.)"),
    source: Optional[str] = Query(None, description="Filter by source name"),
    days: int = Query(7, ge=1, le=90, description="Days back to include"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    List recent regulatory updates (raw signals).

    Org-scoped for future filtering; currently returns global signals.
    """
    since = datetime.utcnow() - timedelta(days=days)
    q = select(RawSignal).where(RawSignal.ingested_at >= since)
    if source:
        q = q.where(RawSignal.source == source)
    q = q.order_by(desc(RawSignal.ingested_at)).limit(limit)
    result = await db.execute(q)
    signals = result.scalars().all()
    return {
        "items": [
            {
                "id": str(s.id),
                "source": s.source,
                "title": s.title,
                "url": s.url,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "ingested_at": s.ingested_at.isoformat() if s.ingested_at else None,
            }
            for s in signals
        ],
        "count": len(signals),
    }


@router.post("/regulatory-updates/process")
async def process_regulatory_signals(
    limit: int = Query(20, ge=1, le=100, description="Max raw signals to process"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    Process unprocessed raw signals for the current org: normalize, classify, score, create PSC alerts when score > 70.
    """
    result = await process_raw_signals_for_org(db, org.id, raw_signal_ids=None, limit=limit)
    await db.commit()
    return {"status": "ok", **result}


@router.post("/regulatory-updates/poll")
async def poll_regulatory_feeds_now(
    frequency: Optional[str] = Query(None, description="Optional: 5min, 15min, 1h, 6h, 1d. If omitted, polls ALL sources."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    Manually trigger poll of regulatory feeds. Inserts new raw_signals.
    Use when Celery Beat isn't running or to populate data immediately.
    """
    totals = await poll_regulatory_feeds(db, frequency_filter=frequency, source_names=None)
    await db.commit()
    return {"status": "ok", "inserted": totals}


@router.post("/regulatory-updates/refresh-hts-usage")
async def refresh_hts_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    Refresh importer_hts_usage from ShipmentItem data (Tier 8 internal data).
    Improves relevance scoring for PSC Radar alerts.
    """
    result = await refresh_importer_hts_usage(db, organization_id=org.id)
    await db.commit()
    return {"status": "ok", **result}
