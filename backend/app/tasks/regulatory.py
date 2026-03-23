"""
Regulatory Celery Task - Compliance Signal Engine

Scheduled task to poll regulatory feeds and insert raw signals.
Task to process raw signals (normalize, classify, score, create alerts).
"""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.regulatory_feed_poller import poll_regulatory_feeds
from app.services.psc_alert_service import process_raw_signals_for_org
from app.services.importer_hts_usage_service import refresh_importer_hts_usage
from app.models.organization import Organization

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=None)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def _run_poller(frequency_filter: str = None, source_names: list = None) -> dict:
    """Run the feed poller and return counts."""
    async with AsyncSessionLocal() as db:
        totals = await poll_regulatory_feeds(db, frequency_filter=frequency_filter, source_names=source_names)
        await db.commit()
        return totals


async def _run_process_signals(limit: int = 50) -> dict:
    """Process raw signals for all orgs."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization.id))
        org_ids = [r[0] for r in result.all()]
        totals = {"normalized": 0, "scored": 0, "alerts_created": 0}
        for org_id in org_ids:
            r = await process_raw_signals_for_org(db, org_id, raw_signal_ids=None, limit=limit)
            totals["normalized"] += r.get("normalized", 0)
            totals["scored"] += r.get("scored", 0)
            totals["alerts_created"] += r.get("alerts_created", 0)
        await db.commit()
        return totals


@celery_app.task(name="app.tasks.regulatory.poll_regulatory_feeds", bind=True)
def poll_regulatory_feeds_task(self, frequency_filter: str = None, source_names: list = None):
    """
    Celery task: poll regulatory feeds and insert new raw_signals.

    If frequency_filter is set (5min, 15min, 1h, 6h, 1d), only polls sources with that frequency. GAP 5.
    """
    try:
        totals = asyncio.run(_run_poller(frequency_filter=frequency_filter, source_names=source_names))
        logger.info("Regulatory poll completed: %s", totals)
        return {"status": "ok", "inserted": totals}
    except Exception as e:
        logger.exception("Regulatory poll failed: %s", e)
        raise


@celery_app.task(name="app.tasks.regulatory.process_regulatory_signals", bind=True)
def process_regulatory_signals_task(self, limit: int = 50):
    """
    Celery task: process raw signals for all orgs (normalize, classify, score, create alerts).
    """
    try:
        totals = asyncio.run(_run_process_signals(limit=limit))
        logger.info("Regulatory process completed: %s", totals)
        return {"status": "ok", **totals}
    except Exception as e:
        logger.exception("Regulatory process failed: %s", e)
        raise


async def _run_refresh_hts_usage(organization_id=None) -> dict:
    """Refresh importer_hts_usage from ShipmentItem data."""
    async with AsyncSessionLocal() as db:
        result = await refresh_importer_hts_usage(db, organization_id=organization_id)
        await db.commit()
        return result


@celery_app.task(name="app.tasks.regulatory.refresh_importer_hts_usage", bind=True)
def refresh_importer_hts_usage_task(self, organization_id=None):
    """
    Celery task: refresh importer_hts_usage from ShipmentItem (Tier 8 internal data).
    Run daily or after bulk analysis.
    """
    try:
        result = asyncio.run(_run_refresh_hts_usage(organization_id=organization_id))
        logger.info("Importer HTS usage refresh completed: %s", result)
        return {"status": "ok", **result}
    except Exception as e:
        logger.exception("Importer HTS usage refresh failed: %s", e)
        raise
