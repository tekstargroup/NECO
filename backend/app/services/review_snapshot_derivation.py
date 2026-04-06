"""
Materialized review object_snapshot from canonical DB artifacts + advisory engine JSON overlay.

**Materialization (pipeline):** After facts, reasoning traces, and regulatory rows are persisted,
we rebuild `review_records.object_snapshot` from DB-backed fields and merge non-canonical
advisory fields (duty, PSC, etc.) from the in-memory engine result.

**On-demand:** API consumers may use `analysis.result_json` (also merged for reasoning in
`get_analysis_status`) or the review snapshot; both should agree on canonical dimensions
after a successful pipeline run.

This module does not introduce a second source of truth: the snapshot is a denormalized
projection for workflow/immutability, not authoritative over the tables above.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument
from app.models.shipment_item_classification_facts import ShipmentItemClassificationFacts
from app.models.analysis_line_provenance_snapshot import AnalysisLineProvenanceSnapshot
from app.models.shipment_item_line_provenance import ShipmentItemLineProvenance
from app.services.regulatory_evaluation_service import fetch_regulatory_evaluations_engine_json
from app.services.reasoning_trace_persistence import merge_reasoning_traces_into_result_json

logger = logging.getLogger(__name__)


def format_line_provenance_for_items_from_snapshots(
    snap_rows: List[AnalysisLineProvenanceSnapshot],
    documents: List[Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group API-shaped line provenance dicts by shipment_item_id (canonical replay path)."""
    by_item: Dict[str, List[AnalysisLineProvenanceSnapshot]] = {}
    for s in snap_rows:
        by_item.setdefault(str(s.shipment_item_id), []).append(s)
    return {
        iid: _format_line_provenance_rows(rows, documents)
        for iid, rows in by_item.items()
    }


def _format_line_provenance_rows(
    rows: List[Any],
    documents: List[ShipmentDocument],
) -> List[Dict[str, Any]]:
    """Match ShipmentAnalysisService._line_provenance_api_rows shape (no service import)."""
    doc_map = {d.id: d for d in (documents or [])}
    out: List[Dict[str, Any]] = []
    for p in rows:
        d = doc_map.get(p.shipment_document_id)
        dt = d.document_type.value if d and d.document_type else "UNKNOWN"
        label = "Commercial Invoice" if dt == "COMMERCIAL_INVOICE" else (
            "Entry Summary" if dt == "ENTRY_SUMMARY" else dt.replace("_", " ").title()
        )
        display_ln = p.logical_line_number if p.logical_line_number is not None else (p.line_index + 1)
        out.append(
            {
                "shipment_document_id": str(p.shipment_document_id),
                "document_type": dt,
                "filename": d.filename if d else None,
                "line_index": p.line_index,
                "logical_line_number": p.logical_line_number,
                "mapping_method": p.mapping_method,
                "summary": f"Linked to {label} line {display_ln} (array index {p.line_index})",
                "raw_line_text": (p.raw_line_text or "")[:2000],
                "structured_snapshot": p.structured_snapshot,
            }
        )
    return out


async def materialize_review_object_snapshot(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
    engine_result_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build review `object_snapshot` JSON: canonical DB overlays + engine advisory fields.

    Preserves keys expected by exports/UI (evidence_map, import_summary, items[].duty, …).
    """
    out = copy.deepcopy(engine_result_json)
    out["_snapshot_derivation"] = {
        "mode": "materialized_post_persist",
        "schema_version": "1",
        "canonical_sources": [
            "regulatory_evaluations.analysis_id",
            "shipment_item_classification_facts.analysis_id",
            "analysis_item_reasoning_traces.analysis_id",
            "analysis_line_provenance_snapshots (frozen per analysis; shipment_item_line_provenance is live import truth)",
        ],
        "advisory_overlay_keys": [
            "items[].duty",
            "items[].psc",
            "items[].prior_knowledge",
            "prior_knowledge_lookup_errors",
        ],
    }

    shipment_result = await db.execute(
        select(Shipment)
        .where(Shipment.id == shipment_id, Shipment.organization_id == organization_id)
        .options(selectinload(Shipment.documents), selectinload(Shipment.items))
    )
    shipment = shipment_result.scalar_one_or_none()
    if not shipment:
        logger.warning(
            "materialize_review_object_snapshot: shipment %s not found for org %s",
            shipment_id,
            organization_id,
        )
        await merge_reasoning_traces_into_result_json(db, analysis_id=analysis_id, result_json=out)
        return out

    documents: List[Any] = list(shipment.documents or [])

    reg_flat = await fetch_regulatory_evaluations_engine_json(db, analysis_id=analysis_id)
    out["regulatory_evaluations"] = reg_flat

    facts_res = await db.execute(
        select(ShipmentItemClassificationFacts).where(
            ShipmentItemClassificationFacts.analysis_id == analysis_id
        )
    )
    facts_by_item = {str(r.shipment_item_id): r.facts_json for r in facts_res.scalars().all()}

    item_ids: List[UUID] = []
    for it in out.get("items") or []:
        if isinstance(it, dict) and it.get("id"):
            try:
                item_ids.append(UUID(str(it["id"])))
            except (ValueError, TypeError):
                pass

    prov_by_item: Dict[str, List[Any]] = {}
    snap_res = await db.execute(
        select(AnalysisLineProvenanceSnapshot).where(
            AnalysisLineProvenanceSnapshot.analysis_id == analysis_id
        )
    )
    snap_rows = list(snap_res.scalars().all())
    if snap_rows:
        for row in snap_rows:
            prov_by_item.setdefault(str(row.shipment_item_id), []).append(row)
    elif item_ids:
        pv = await db.execute(
            select(ShipmentItemLineProvenance).where(
                ShipmentItemLineProvenance.shipment_item_id.in_(item_ids)
            )
        )
        for row in pv.scalars().all():
            prov_by_item.setdefault(str(row.shipment_item_id), []).append(row)

    for it in out.get("items") or []:
        if not isinstance(it, dict):
            continue
        iid = it.get("id")
        if not iid:
            continue
        sid = str(iid)
        if sid in facts_by_item:
            it["classification_facts"] = facts_by_item[sid]
        prov_rows = prov_by_item.get(sid, [])
        it["line_provenance"] = _format_line_provenance_rows(prov_rows, documents)
        it["regulatory"] = [r for r in reg_flat if r.get("item_id") == sid]

    await merge_reasoning_traces_into_result_json(db, analysis_id=analysis_id, result_json=out)
    return out
