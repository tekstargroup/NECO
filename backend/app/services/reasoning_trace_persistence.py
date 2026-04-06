"""Persist and merge analysis-scoped heading reasoning traces (Phase 2)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_item_reasoning_trace import AnalysisItemReasoningTrace

logger = logging.getLogger(__name__)


async def upsert_analysis_item_reasoning_trace(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
    shipment_item_id: UUID,
    trace_json: Dict[str, Any],
    schema_version: str = "1",
) -> None:
    """Idempotent upsert per (analysis_id, shipment_item_id)."""
    tbl = AnalysisItemReasoningTrace
    now = datetime.utcnow()
    ins = pg_insert(tbl).values(
        analysis_id=analysis_id,
        shipment_id=shipment_id,
        organization_id=organization_id,
        shipment_item_id=shipment_item_id,
        trace_json=trace_json,
        schema_version=schema_version,
        created_at=now,
        updated_at=now,
    )
    stmt = ins.on_conflict_do_update(
        constraint="uq_reasoning_trace_analysis_item",
        set_={
            "trace_json": ins.excluded.trace_json,
            "shipment_id": ins.excluded.shipment_id,
            "organization_id": ins.excluded.organization_id,
            "schema_version": ins.excluded.schema_version,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)


async def persist_reasoning_traces_from_result_items(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
    items: List[Dict[str, Any]],
) -> None:
    """Write one trace row per item that exposes heading_reasoning_trace."""
    for it in items:
        iid = it.get("id")
        trace = it.get("heading_reasoning_trace")
        if not iid or trace is None:
            continue
        try:
            sid = UUID(str(iid))
        except (ValueError, TypeError):
            logger.warning("persist_reasoning_traces: skip item with invalid id %r", iid)
            continue
        if not isinstance(trace, dict):
            trace = {"_raw": trace}
        await upsert_analysis_item_reasoning_trace(
            db,
            analysis_id=analysis_id,
            shipment_id=shipment_id,
            organization_id=organization_id,
            shipment_item_id=sid,
            trace_json=trace,
        )


async def merge_reasoning_traces_into_result_json(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    result_json: Dict[str, Any],
) -> None:
    """
    Overlay items[].heading_reasoning_trace from DB when rows exist (canonical over embedded JSON).
    Mutates result_json in place.
    """
    items = result_json.get("items")
    if not isinstance(items, list) or not items:
        return
    res = await db.execute(
        select(AnalysisItemReasoningTrace).where(AnalysisItemReasoningTrace.analysis_id == analysis_id)
    )
    rows = list(res.scalars().all())
    if not rows:
        return
    by_item = {str(r.shipment_item_id): r.trace_json for r in rows}
    for it in items:
        if not isinstance(it, dict):
            continue
        iid = it.get("id")
        if iid is None:
            continue
        tj = by_item.get(str(iid))
        if tj is not None:
            it["heading_reasoning_trace"] = tj
