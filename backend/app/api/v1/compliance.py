"""
Compliance API Endpoints - Sprint 8

Read-only endpoints for compliance visibility and audit readiness.

Key principles:
- Read-only (no mutations)
- Aggregated metrics
- Exportable reports
- Audit pack generation
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID

from app.core.database import get_db
from app.core.sources_config import get_sources
from app.services.compliance_dashboard_service import ComplianceDashboardService
from app.services.reporting_service import ReportingService
from app.services.audit_pack_service import AuditPackService
from app.models.review_record import ReviewableObjectType
from app.models.raw_signal import RawSignal
from app.models.normalized_signal import NormalizedSignal
from app.models.psc_alert import PSCAlert
from app.services.regulatory_feed_poller import test_all_sources

router = APIRouter()

# Frequency (str) -> max minutes before "stale"
FREQ_MINUTES = {"5min": 10, "15min": 30, "1h": 120, "6h": 720, "1d": 2880}


@router.get("/dashboard/summary")
async def get_compliance_summary(
    time_range_start: Optional[datetime] = Query(None, description="Start of time range"),
    time_range_end: Optional[datetime] = Query(None, description="End of time range"),
    hts_chapter: Optional[str] = Query(None, description="Filter by HTS chapter"),
    reviewer: Optional[str] = Query(None, description="Filter by reviewer"),
    object_type: Optional[str] = Query(None, description="Filter by object type (CLASSIFICATION or PSC_RADAR)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get compliance summary dashboard metrics.
    
    Read-only aggregations for management visibility.
    """
    service = ComplianceDashboardService(db)
    
    obj_type = None
    if object_type:
        try:
            obj_type = ReviewableObjectType(object_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid object_type: {object_type}. Must be CLASSIFICATION or PSC_RADAR"
            )
    
    summary = await service.get_summary(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        hts_chapter=hts_chapter,
        reviewer=reviewer,
        object_type=obj_type
    )
    
    return summary


@router.get("/signal-health")
async def get_signal_health(
    db: AsyncSession = Depends(get_db)
):
    """
    Compliance Signal Engine health dashboard.

    Returns per-source status (RSS/API/scrape), pipeline totals, and alert counts.
    Use for manager visibility: ensure feeds are polling, signals processing, alerts populating.
    """
    now = datetime.utcnow()
    sources_config = get_sources()

    # Per-source: count, last_ingested_at from raw_signals
    q = select(
        RawSignal.source,
        func.count(RawSignal.id).label("count"),
        func.max(RawSignal.ingested_at).label("last_ingested_at"),
    ).group_by(RawSignal.source)
    result = await db.execute(q)
    rows = {r.source: {"count": r.count, "last_ingested_at": r.last_ingested_at} for r in result.all()}

    # Build source status list
    sources_status = []
    ok_count = stale_count = no_data_count = 0
    for src in sources_config:
        name = src.get("name", "")
        freq = src.get("frequency", "1d")
        src_type = src.get("type", "rss")
        tier = src.get("tier", 0)
        data = rows.get(name, {})
        count = data.get("count", 0)
        last_at = data.get("last_ingested_at")
        max_min = FREQ_MINUTES.get(freq, 2880)
        if last_at is None:
            status = "no_data"
            no_data_count += 1
        else:
            delta_min = (now - last_at).total_seconds() / 60
            status = "ok" if delta_min <= max_min else "stale"
            if status == "ok":
                ok_count += 1
            else:
                stale_count += 1
        sources_status.append({
            "name": name,
            "type": src_type,
            "tier": tier,
            "frequency": freq,
            "count": count,
            "last_ingested_at": last_at.isoformat() if last_at else None,
            "status": status,
        })

    # Pipeline totals
    raw_total = sum(r.get("count", 0) for r in rows.values())
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    q_norm = select(func.count()).select_from(NormalizedSignal)
    norm_result = await db.execute(q_norm)
    norm_total = norm_result.scalar() or 0

    q_alert = select(func.count()).select_from(PSCAlert)
    alert_result = await db.execute(q_alert)
    alert_total = alert_result.scalar() or 0

    q_alert_24 = select(func.count()).select_from(PSCAlert).where(PSCAlert.created_at >= since_24h)
    alert_24_result = await db.execute(q_alert_24)
    alert_24h = alert_24_result.scalar() or 0

    q_alert_7 = select(func.count()).select_from(PSCAlert).where(PSCAlert.created_at >= since_7d)
    alert_7_result = await db.execute(q_alert_7)
    alert_7d = alert_7_result.scalar() or 0

    # Overall health
    total_sources = len(sources_config)
    pipeline_ok = raw_total > 0 and norm_total >= 0
    overall = "ok" if (ok_count > 0 and pipeline_ok) else "warning" if (stale_count > 0 or raw_total > 0) else "critical"

    return {
        "overall": overall,
        "generated_at": now.isoformat(),
        "summary": {
            "sources_ok": ok_count,
            "sources_stale": stale_count,
            "sources_no_data": no_data_count,
            "sources_total": total_sources,
            "raw_signals_total": raw_total,
            "normalized_signals_total": norm_total,
            "alerts_total": alert_total,
            "alerts_last_24h": alert_24h,
            "alerts_last_7d": alert_7d,
        },
        "sources": sources_status,
        "celery_schedule": {
            "poll_5min": "every 5 min",
            "poll_15min": "every 15 min",
            "poll_1h": "every 1 hour",
            "poll_6h": "every 6 hours",
            "poll_1d": "every 24 hours",
            "process_signals": "every hour (+100s after poll)",
            "refresh_hts_usage": "daily",
        },
    }


@router.get("/test-sources/diagnostic")
async def test_sources_diagnostic():
    """
    Quick diagnostic: try to fetch one feed (CBP) and return success/failure.
    Use to check if the backend can reach external sites.
    """
    import requests
    url = "https://www.cbp.gov/rss/trade"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "NECO-Compliance-Signal-Engine/1.0"},
            timeout=15,
            proxies={"http": None, "https": None},
        )
        ok = resp.status_code == 200 and len(resp.content) > 500
        return {
            "reachable": ok,
            "status_code": resp.status_code,
            "content_length": len(resp.content),
            "error": None if ok else f"status={resp.status_code}",
        }
    except Exception as e:
        return {
            "reachable": False,
            "status_code": None,
            "content_length": 0,
            "error": str(e)[:200],
        }


@router.get("/test-sources")
async def test_regulatory_sources():
    """
    Test all configured regulatory sources (RSS, API, scrape).
    Fetches from each source without inserting. Use to validate feeds before proceeding.
    """
    results = test_all_sources()
    summary = {
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "empty": sum(1 for r in results if r["status"] == "empty"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "total": len(results),
    }
    return {"summary": summary, "sources": results}


@router.get("/reports/classification-risk")
async def get_classification_risk_report(
    time_range_start: Optional[datetime] = Query(None),
    time_range_end: Optional[datetime] = Query(None),
    hts_chapter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate Classification Risk Report."""
    service = ReportingService(db)
    report = await service.generate_classification_risk_report(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        hts_chapter=hts_chapter
    )
    return report


@router.get("/reports/psc-exposure")
async def get_psc_exposure_report(
    time_range_start: Optional[datetime] = Query(None),
    time_range_end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate PSC Exposure Report."""
    service = ReportingService(db)
    report = await service.generate_psc_exposure_report(
        time_range_start=time_range_start,
        time_range_end=time_range_end
    )
    return report


@router.get("/reports/review-activity")
async def get_review_activity_report(
    time_range_start: Optional[datetime] = Query(None),
    time_range_end: Optional[datetime] = Query(None),
    reviewer: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate Review Activity Report."""
    service = ReportingService(db)
    report = await service.generate_review_activity_report(
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        reviewer=reviewer
    )
    return report


@router.get("/reports/unresolved-risk")
async def get_unresolved_risk_report(
    time_range_start: Optional[datetime] = Query(None),
    time_range_end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Generate Unresolved Risk Report."""
    service = ReportingService(db)
    report = await service.generate_unresolved_risk_report(
        time_range_start=time_range_start,
        time_range_end=time_range_end
    )
    return report


@router.get("/audit-pack")
async def get_audit_pack(
    review_ids: Optional[List[UUID]] = Query(None, description="Specific review IDs"),
    time_range_start: Optional[datetime] = Query(None),
    time_range_end: Optional[datetime] = Query(None),
    include_audit_replay: bool = Query(True, description="Include audit replay results"),
    format: str = Query("json", description="Export format: json, pdf, zip"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate audit pack.
    
    Critical feature: Complete audit trail for compliance.
    """
    service = AuditPackService(db)
    
    pack = await service.generate_audit_pack(
        review_ids=review_ids,
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        include_audit_replay=include_audit_replay
    )
    
    if format == "json":
        return JSONResponse(content=pack)
    elif format == "pdf":
        pdf_content = service.export_pdf(pack)
        return Response(
            content=pdf_content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="audit_pack_{datetime.utcnow().strftime("%Y%m%d")}.txt"'}
        )
    elif format == "zip":
        zip_content = service.export_zip(pack)
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="audit_pack_{datetime.utcnow().strftime("%Y%m%d")}.zip"'}
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {format}. Must be json, pdf, or zip"
        )


@router.get("/drilldown/{review_id}")
async def get_drilldown_view(
    review_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get read-only drilldown view for a review record.
    
    Links to:
    - Classification/PSC snapshot
    - Review/override history
    - Audit replay output
    
    Read-only: No edits, re-review, or overrides allowed.
    """
    from sqlalchemy import select
    from app.models.review_record import ReviewRecord
    from app.services.review_service import ReviewService
    from app.services.audit_replay_service import AuditReplayService
    
    # Fetch record
    result = await db.execute(
        select(ReviewRecord).where(ReviewRecord.id == review_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review record {review_id} not found"
        )
    
    # Get review history
    review_service = ReviewService(db)
    history = await review_service.get_review_history(review_id)
    
    # Get audit replay
    audit_service = AuditReplayService(db)
    replay_result = await audit_service.verify_review_record(review_id)
    
    return {
        "review_id": str(review_id),
        "object_type": record.object_type.value,
        "status": record.status.value,
        "snapshot": record.object_snapshot,
        "review_history": [r.to_dict() for r in history],
        "audit_replay": replay_result.to_dict(),
        "read_only": True,
        "note": "This is a read-only view. No edits, re-review, or overrides allowed."
    }
