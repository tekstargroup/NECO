"""
Canonical shipment analysis pipeline — single code path for Celery and sync inline runs.

Both `run_shipment_analysis` (Celery) and `AnalysisOrchestrationService` (inline/sync)
must use `execute_shipment_analysis_pipeline` so persistence, review records, and
result_json shape stay identical.
"""

from __future__ import annotations

import enum
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID
from app.models.analysis import Analysis, AnalysisStatus
from app.models.regulatory_evaluation import (
    RegulatoryCondition,
    RegulatoryEvaluation,
    Regulator,
    RegulatoryOutcome,
    ConditionState,
)
from app.models.review_record import (
    ReviewRecord,
    ReviewableObjectType,
    ReviewReasonCode,
    ReviewStatus,
)
from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.org_scoped_repository import OrgScopedRepository
from app.services.shipment_analysis_service import ShipmentAnalysisService

logger = logging.getLogger(__name__)


def sanitize_for_jsonb(obj: Any) -> Any:
    """Recursively sanitize for JSONB: NaN/inf/numpy -> JSON-serializable."""
    if obj is None:
        return None
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        import numpy as np

        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: sanitize_for_jsonb(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_jsonb(v) for v in obj]
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, (UUID, datetime)):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return sanitize_for_jsonb(obj.__dict__)
    return obj


def _rule_registry_hash() -> str:
    """Stable fingerprint of the active rule registry for change detection."""
    import hashlib, json
    from app.engines.classification.rule_based_classifier import RULE_REGISTRY
    enforced = sorted(
        [r["rule_id"] for r in RULE_REGISTRY if r.get("enforce")]
    )
    return hashlib.sha256(json.dumps(enforced).encode()).hexdigest()[:12]


def build_analysis_provenance(*, analysis_path: str, pipeline_mode: Optional[str] = None) -> Dict[str, Any]:
    """Embedded in every result_json for audits (Sprint A/H)."""
    from datetime import datetime, timezone
    env = (settings.ENVIRONMENT or "").lower()
    return {
        "schema_version": "2.0",
        "neco_version": getattr(settings, "APP_VERSION", "unknown"),
        "hts_version_id": AUTHORITATIVE_HTS_VERSION_ID,
        "environment": env,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_path": analysis_path,
        "pipeline_mode": pipeline_mode,
        "classification_rule_mode": getattr(settings, "CLASSIFICATION_RULE_MODE", "enforce"),
        "rule_registry_hash": _rule_registry_hash(),
        "dev_flags": {
            "sprint12_fast_analysis_dev": bool(getattr(settings, "SPRINT12_FAST_ANALYSIS_DEV", False)),
            "sprint12_instant_analysis_dev": bool(getattr(settings, "SPRINT12_INSTANT_ANALYSIS_DEV", False)),
            "sprint12_sync_analysis_dev": bool(getattr(settings, "SPRINT12_SYNC_ANALYSIS_DEV", True)),
            "sprint12_inline_analysis_dev": bool(getattr(settings, "SPRINT12_INLINE_ANALYSIS_DEV", False)),
        },
    }


async def execute_shipment_analysis_pipeline(
    db: AsyncSession,
    *,
    shipment_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    celery_task_id: str,
    clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
    analysis_path: str = "celery",
) -> Dict[str, Any]:
    """
    Run engines, persist review + regulatory rows, commit analysis COMPLETE.

    Preconditions (caller): Analysis row exists, status set RUNNING, shipment ANALYZING if desired.
    """
    result = await db.execute(
        select(Analysis).where(
            and_(
                Analysis.shipment_id == shipment_id,
                Analysis.organization_id == organization_id,
            )
        ).order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise ValueError(f"Analysis record not found for shipment {shipment_id}")

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, organization_id)
    shipment.status = ShipmentStatus.ANALYZING
    await db.commit()

    analysis_service = ShipmentAnalysisService(db)
    result_json, review_snapshot, blockers = await analysis_service.run_full_shipment_analysis(
        shipment_id=shipment_id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        clarification_responses=clarification_responses,
    )

    pipeline_mode = (result_json or {}).get("mode")
    provenance = build_analysis_provenance(analysis_path=analysis_path, pipeline_mode=pipeline_mode)
    if isinstance(result_json, dict):
        result_json = dict(result_json)
        result_json["analysis_provenance"] = provenance

    review_snapshot["analysis_id"] = str(analysis.id)
    snapshot_sanitized = sanitize_for_jsonb(review_snapshot)
    review_record = ReviewRecord(
        object_type=ReviewableObjectType.CLASSIFICATION,
        object_snapshot=snapshot_sanitized,
        hts_version_id=AUTHORITATIVE_HTS_VERSION_ID,
        status=ReviewStatus.REVIEW_REQUIRED if blockers else ReviewStatus.DRAFT,
        created_by=str(actor_user_id),
        review_reason_code=ReviewReasonCode.AUTO_CREATED,
    )
    db.add(review_record)
    await db.flush()

    regulatory_evaluations_data = review_snapshot.get("regulatory_evaluations", [])
    for reg_eval_data in regulatory_evaluations_data:
        regulator = reg_eval_data["regulator"]
        if isinstance(regulator, str):
            regulator = Regulator(regulator)
        outcome = reg_eval_data["outcome"]
        if isinstance(outcome, str):
            outcome = RegulatoryOutcome(outcome)

        reg_eval = RegulatoryEvaluation(
            review_id=review_record.id,
            regulator=regulator,
            outcome=outcome,
            explanation_text=reg_eval_data["explanation_text"],
            triggered_by_hts_code=reg_eval_data["triggered_by_hts_code"],
        )
        db.add(reg_eval)
        await db.flush()

        for condition_eval in reg_eval_data.get("condition_evaluations", []):
            if hasattr(condition_eval, "condition_id"):
                condition_id = condition_eval.condition_id
                state = condition_eval.state
                if isinstance(state, str):
                    state = ConditionState(state)
                evidence_refs = condition_eval.evidence_refs
            else:
                condition_id = condition_eval.get("condition_id")
                state = condition_eval.get("state")
                if isinstance(state, str):
                    state = ConditionState(state)
                evidence_refs = condition_eval.get("evidence_refs", [])

            evidence_refs_json = []
            for ev_ref in evidence_refs:
                if hasattr(ev_ref, "__dict__"):
                    evidence_refs_json.append(ev_ref.__dict__)
                elif isinstance(ev_ref, dict):
                    evidence_refs_json.append(ev_ref)
                else:
                    evidence_refs_json.append(str(ev_ref))

            reg_condition = RegulatoryCondition(
                evaluation_id=reg_eval.id,
                condition_id=condition_id,
                condition_description=None,
                state=state,
                evidence_refs=evidence_refs_json,
            )
            db.add(reg_condition)

    analysis.review_record_id = review_record.id
    shipment.status = ShipmentStatus.COMPLETE
    analysis.status = AnalysisStatus.COMPLETE
    analysis.completed_at = datetime.utcnow()
    analysis.result_json = sanitize_for_jsonb(result_json)
    await db.commit()

    logger.info(
        "Analysis pipeline complete shipment=%s analysis=%s review_record=%s",
        shipment_id,
        analysis.id,
        review_record.id,
    )
    return {
        "status": "complete",
        "analysis_id": str(analysis.id),
        "review_record_id": str(review_record.id),
        "blockers": blockers,
    }
