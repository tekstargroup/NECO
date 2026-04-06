"""Analysis-scoped regulatory evaluation persistence and serialization (Phase 2b)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.regulatory_evaluation import RegulatoryCondition, RegulatoryEvaluation
from app.models.review_record import ReviewRecord

logger = logging.getLogger(__name__)


async def delete_regulatory_evaluations_for_analysis(db: AsyncSession, *, analysis_id: UUID) -> None:
    """Remove all regulatory rows for an analysis (conditions first) — idempotent pipeline retries."""
    res = await db.execute(
        select(RegulatoryEvaluation.id).where(RegulatoryEvaluation.analysis_id == analysis_id)
    )
    for eid in res.scalars().all():
        await db.execute(delete(RegulatoryCondition).where(RegulatoryCondition.evaluation_id == eid))
    await db.execute(delete(RegulatoryEvaluation).where(RegulatoryEvaluation.analysis_id == analysis_id))


def regulatory_select_for_review(review: ReviewRecord):
    """Prefer analysis_id (canonical); fall back to review_id for pre-migration rows."""
    if review.analysis_id:
        return select(RegulatoryEvaluation).where(RegulatoryEvaluation.analysis_id == review.analysis_id)
    return select(RegulatoryEvaluation).where(RegulatoryEvaluation.review_id == review.id)


async def fetch_regulatory_evaluations_engine_json(
    db: AsyncSession,
    *,
    analysis_id: UUID,
) -> List[Dict[str, Any]]:
    """Serialize DB rows to the same shape as the regulatory engine / result_json list."""
    res = await db.execute(
        select(RegulatoryEvaluation)
        .where(RegulatoryEvaluation.analysis_id == analysis_id)
        .options(selectinload(RegulatoryEvaluation.conditions))
        .order_by(RegulatoryEvaluation.evaluated_at)
    )
    rows = res.scalars().all()
    out: List[Dict[str, Any]] = []
    for reg_eval in rows:
        conditions_data = [
            {
                "condition_id": cond.condition_id,
                "condition_description": cond.condition_description,
                "state": cond.state.value if hasattr(cond.state, "value") else str(cond.state),
                "evidence_refs": cond.evidence_refs or [],
            }
            for cond in reg_eval.conditions
        ]
        item: Dict[str, Any] = {
            "regulator": reg_eval.regulator.value if hasattr(reg_eval.regulator, "value") else str(reg_eval.regulator),
            "outcome": reg_eval.outcome.value if hasattr(reg_eval.outcome, "value") else str(reg_eval.outcome),
            "explanation_text": reg_eval.explanation_text,
            "triggered_by_hts_code": reg_eval.triggered_by_hts_code,
            "condition_evaluations": conditions_data,
        }
        if reg_eval.shipment_item_id:
            item["item_id"] = str(reg_eval.shipment_item_id)
        out.append(item)
    return out
