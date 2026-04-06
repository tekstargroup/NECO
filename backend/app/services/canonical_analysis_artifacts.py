"""
Single DB-first assembly of canonical analysis artifacts for API, exports, chat, and review.

`result_json` on `analyses` is a compatibility projection; authoritative dimensions are loaded here.
Duty/PSC remain advisory unless separately promoted in trust_contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import Analysis
from app.models.analysis_line_provenance_snapshot import AnalysisLineProvenanceSnapshot
from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument
from app.models.shipment_item_classification_facts import ShipmentItemClassificationFacts
from app.models.analysis_item_reasoning_trace import AnalysisItemReasoningTrace
from app.services.pipeline_stage_service import build_trust_contract_metadata
from app.services.regulatory_evaluation_service import fetch_regulatory_evaluations_engine_json
from app.services.review_snapshot_derivation import format_line_provenance_for_items_from_snapshots


async def load_canonical_analysis_artifacts(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    organization_id: UUID,
    *,
    include_advisory_from_result_json: bool = True,
) -> Dict[str, Any]:
    """
    Return canonical bundles keyed by artifact class.

    - classification_facts: list of {shipment_item_id, facts_json}
    - reasoning_traces: list of {shipment_item_id, trace_json}
    - regulatory_evaluations: engine-shaped list (includes conditions)
    - line_provenance_snapshots: ORM rows serialized to dicts (or grouped by item in ``line_provenance_by_item``)
    - trust_contract: embedded metadata
    - advisory_overlay: subset from analysis.result_json when include_advisory_from_result_json
    """
    ar = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.organization_id == organization_id,
        )
    )
    analysis = ar.scalar_one_or_none()
    if not analysis:
        raise ValueError(f"Analysis not found: {analysis_id}")

    facts_res = await db.execute(
        select(ShipmentItemClassificationFacts).where(
            ShipmentItemClassificationFacts.analysis_id == analysis_id
        )
    )
    facts_rows = list(facts_res.scalars().all())
    classification_facts: List[Dict[str, Any]] = [
        {"shipment_item_id": str(r.shipment_item_id), "facts_json": r.facts_json}
        for r in facts_rows
    ]

    rt_res = await db.execute(
        select(AnalysisItemReasoningTrace).where(AnalysisItemReasoningTrace.analysis_id == analysis_id)
    )
    rt_rows = list(rt_res.scalars().all())
    reasoning_traces: List[Dict[str, Any]] = [
        {"shipment_item_id": str(r.shipment_item_id), "trace_json": r.trace_json}
        for r in rt_rows
    ]

    regulatory_evaluations = await fetch_regulatory_evaluations_engine_json(db, analysis_id=analysis_id)

    snap_res = await db.execute(
        select(AnalysisLineProvenanceSnapshot).where(
            AnalysisLineProvenanceSnapshot.analysis_id == analysis_id
        )
    )
    snap_rows = list(snap_res.scalars().all())
    line_provenance_snapshots = [
        {
            "shipment_item_id": str(r.shipment_item_id),
            "shipment_document_id": str(r.shipment_document_id),
            "line_index": r.line_index,
            "logical_line_number": r.logical_line_number,
            "mapping_method": r.mapping_method,
            "raw_line_text": r.raw_line_text,
            "structured_snapshot": r.structured_snapshot,
        }
        for r in snap_rows
    ]

    sh = await db.execute(
        select(Shipment)
        .where(Shipment.id == analysis.shipment_id)
        .options(selectinload(Shipment.documents))
    )
    shipment = sh.scalar_one_or_none()
    documents: List[Any] = list(shipment.documents or []) if shipment else []
    line_provenance_by_item = format_line_provenance_for_items_from_snapshots(snap_rows, documents)

    out: Dict[str, Any] = {
        "analysis_id": str(analysis_id),
        "shipment_id": str(analysis.shipment_id),
        "classification_facts": classification_facts,
        "reasoning_traces": reasoning_traces,
        "regulatory_evaluations": regulatory_evaluations,
        "line_provenance_snapshots": line_provenance_snapshots,
        "line_provenance_by_item_id": line_provenance_by_item,
        "trust_contract": build_trust_contract_metadata(),
    }

    if include_advisory_from_result_json and isinstance(analysis.result_json, dict):
        rj = analysis.result_json
        out["advisory_overlay"] = {
            "items_duty_psc_prior": [
                {
                    "id": it.get("id"),
                    "duty": it.get("duty"),
                    "psc": it.get("psc"),
                    "prior_knowledge": it.get("prior_knowledge"),
                }
                for it in (rj.get("items") or [])
                if isinstance(it, dict)
            ],
            "prior_knowledge_lookup_errors": rj.get("prior_knowledge_lookup_errors"),
        }
    else:
        out["advisory_overlay"] = None

    return out


async def build_analysis_snapshot_from_canonical_artifacts(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    organization_id: UUID,
    engine_result_json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Preferred name for review/object snapshot rebuild: delegates to materialize_review_object_snapshot
    when engine JSON is provided; otherwise builds a minimal envelope from canonical rows only.
    """
    from app.services.review_snapshot_derivation import materialize_review_object_snapshot

    ar = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.organization_id == organization_id,
        )
    )
    analysis = ar.scalar_one_or_none()
    if not analysis:
        raise ValueError(f"Analysis not found: {analysis_id}")

    base = engine_result_json if isinstance(engine_result_json, dict) else (
        analysis.result_json if isinstance(analysis.result_json, dict) else {}
    )
    return await materialize_review_object_snapshot(
        db,
        analysis_id=analysis_id,
        shipment_id=analysis.shipment_id,
        organization_id=organization_id,
        engine_result_json=dict(base),
    )
