"""
PSC Radar API - Compliance Signal Engine

List and update PSC alerts from compliance signals.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.models.psc_alert import PSCAlert, PSCAlertStatus
from app.models.normalized_signal import NormalizedSignal
from app.models.raw_signal import RawSignal

router = APIRouter()


class PSCAlertStatusUpdate(BaseModel):
    status: str  # "reviewed" | "dismissed"


@router.get("/psc-radar/alerts")
async def get_psc_radar_alerts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: new, reviewed, dismissed"),
    shipment_id: Optional[UUID] = Query(None, description="Filter by shipment (GAP 10 shipment integration)"),
    min_score: Optional[float] = Query(50, ge=0, le=100, description="Minimum score to include"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    List PSC alerts for the current organization.
    Use shipment_id to get alerts for a specific shipment (shipment detail integration).
    """
    q = (
        select(PSCAlert)
        .where(PSCAlert.organization_id == org.id)
        .options(selectinload(PSCAlert.signal).selectinload(NormalizedSignal.raw_signal))
    )
    if shipment_id:
        q = q.where(PSCAlert.shipment_id == shipment_id)
    if status_filter:
        try:
            st = PSCAlertStatus(status_filter)
            q = q.where(PSCAlert.status == st)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
    q = q.order_by(desc(PSCAlert.created_at)).limit(limit)
    result = await db.execute(q)
    alerts = result.scalars().all()
    items = []
    for a in alerts:
        raw = a.signal.raw_signal if a.signal else None
        exp = a.explanation or {}
        items.append({
            "id": str(a.id),
            "signal_id": str(a.signal_id),
            "hts_code": a.hts_code,
            "alert_type": a.alert_type,
            "duty_delta_estimate": a.duty_delta_estimate,
            "reason": a.reason,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "explanation": a.explanation,
            "evidence_links": a.evidence_links,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "source_url": raw.url if raw else None,
            "source_title": raw.title if raw else None,
            "shipment_id": str(a.shipment_id) if a.shipment_id else None,
            "confidence_score": a.confidence_score,
            "priority": a.priority,
            "signal_source": a.signal_source,
            "fill_rate_pct": exp.get("fill_rate"),
        })
    return {"items": items, "count": len(items)}


@router.patch("/psc-radar/alerts/{alert_id}")
async def update_psc_alert_status(
    alert_id: UUID,
    body: PSCAlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    org: Organization = Depends(get_current_organization),
):
    """
    Update PSC alert status (reviewed/dismissed).
    """
    result = await db.execute(
        select(PSCAlert).where(
            PSCAlert.id == alert_id,
            PSCAlert.organization_id == org.id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        new_status = PSCAlertStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    if new_status not in (PSCAlertStatus.REVIEWED, PSCAlertStatus.DISMISSED):
        raise HTTPException(status_code=400, detail="Status must be reviewed or dismissed")
    alert.status = new_status
    await db.commit()
    return {"id": str(alert.id), "status": new_status.value}
