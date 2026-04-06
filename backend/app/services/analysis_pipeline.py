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

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID
from app.models.analysis import Analysis, AnalysisStatus
from app.services.analysis_identity_service import (
    derive_decision_status,
    maybe_promote_analysis_after_success,
    trust_gate_allows_trusted_status,
)
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
from app.models.analysis_pipeline_stage import PipelineStageName, PipelineStageStatus
from app.services.pipeline_stage_service import (
    PipelineStageContext,
    build_trust_contract_metadata,
    upsert_stage,
)
from app.services.regulatory_evaluation_service import delete_regulatory_evaluations_for_analysis
from app.services.review_snapshot_derivation import materialize_review_object_snapshot
from app.services.provenance_snapshot_persistence import replace_line_provenance_snapshots_for_analysis

logger = logging.getLogger(__name__)


async def _delete_regulatory_children_for_review(
    db: AsyncSession,
    *,
    review_id: UUID,
) -> None:
    """Legacy: delete by review_id (pre–analysis_id migrations). Prefer delete_regulatory_evaluations_for_analysis."""
    res = await db.execute(
        select(RegulatoryEvaluation.id).where(RegulatoryEvaluation.review_id == review_id)
    )
    for eid in res.scalars().all():
        await db.execute(delete(RegulatoryCondition).where(RegulatoryCondition.evaluation_id == eid))
    await db.execute(delete(RegulatoryEvaluation).where(RegulatoryEvaluation.review_id == review_id))


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
    analysis_id: UUID,
    clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
    analysis_path: str = "celery",
) -> Dict[str, Any]:
    """
    Run engines, persist review + regulatory rows, commit analysis COMPLETE.

    Preconditions (caller): Analysis row exists for analysis_id, status set RUNNING, shipment ANALYZING if desired.
    """
    result = await db.execute(
        select(Analysis).where(
            and_(
                Analysis.id == analysis_id,
                Analysis.shipment_id == shipment_id,
                Analysis.organization_id == organization_id,
            )
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise ValueError(f"Analysis record not found: {analysis_id} for shipment {shipment_id}")

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, organization_id)
    shipment.status = ShipmentStatus.ANALYZING
    await db.commit()

    stage_ctx = PipelineStageContext(
        db,
        analysis_id=analysis.id,
        shipment_id=shipment_id,
        organization_id=organization_id,
    )
    analysis_service = ShipmentAnalysisService(db)
    result_json, review_snapshot, blockers = await analysis_service.run_full_shipment_analysis(
        shipment_id=shipment_id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        clarification_responses=clarification_responses,
        analysis_id=analysis.id,
        stage_ctx=stage_ctx,
    )

    pipeline_mode = (result_json or {}).get("mode")
    provenance = build_analysis_provenance(analysis_path=analysis_path, pipeline_mode=pipeline_mode)
    if isinstance(result_json, dict):
        result_json = dict(result_json)
        result_json["analysis_provenance"] = provenance
        result_json["trust_contract"] = build_trust_contract_metadata()

    review_snapshot["analysis_id"] = str(analysis.id)

    await upsert_stage(
        db,
        analysis_id=analysis.id,
        shipment_id=shipment_id,
        organization_id=organization_id,
        stage=PipelineStageName.REVIEW_REGULATORY_PERSIST,
        status=PipelineStageStatus.RUNNING,
        ordinal=50,
    )
    try:
        rr_row = await db.execute(select(ReviewRecord).where(ReviewRecord.analysis_id == analysis.id))
        review_record = rr_row.scalar_one_or_none()
        target_status = ReviewStatus.REVIEW_REQUIRED if blockers else ReviewStatus.DRAFT
        if review_record:
            review_record.status = target_status
        else:
            review_record = ReviewRecord(
                analysis_id=analysis.id,
                object_type=ReviewableObjectType.CLASSIFICATION,
                object_snapshot=sanitize_for_jsonb(
                    {"shipment_id": str(shipment_id), "items": [], "_snapshot_placeholder": True}
                ),
                hts_version_id=AUTHORITATIVE_HTS_VERSION_ID,
                status=target_status,
                created_by=str(actor_user_id),
                review_reason_code=ReviewReasonCode.AUTO_CREATED,
            )
            db.add(review_record)
        await db.flush()

        await delete_regulatory_evaluations_for_analysis(db, analysis_id=analysis.id)

        regulatory_evaluations_data = (result_json or {}).get("regulatory_evaluations") or []
        for reg_eval_data in regulatory_evaluations_data:
            regulator = reg_eval_data["regulator"]
            if isinstance(regulator, str):
                regulator = Regulator(regulator)
            outcome = reg_eval_data["outcome"]
            if isinstance(outcome, str):
                outcome = RegulatoryOutcome(outcome)

            item_uuid: Optional[UUID] = None
            raw_item = reg_eval_data.get("item_id")
            if raw_item:
                try:
                    item_uuid = UUID(str(raw_item))
                except (ValueError, TypeError):
                    item_uuid = None

            reg_eval = RegulatoryEvaluation(
                analysis_id=analysis.id,
                review_id=review_record.id,
                shipment_item_id=item_uuid,
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

        await replace_line_provenance_snapshots_for_analysis(
            db,
            analysis_id=analysis.id,
            shipment_id=shipment_id,
            organization_id=organization_id,
        )

        final_snapshot = await materialize_review_object_snapshot(
            db,
            analysis_id=analysis.id,
            shipment_id=shipment_id,
            organization_id=organization_id,
            engine_result_json=result_json if isinstance(result_json, dict) else {},
        )
        review_record.object_snapshot = sanitize_for_jsonb(final_snapshot)

        analysis.review_record_id = review_record.id
    except Exception as e:
        await upsert_stage(
            db,
            analysis_id=analysis.id,
            shipment_id=shipment_id,
            organization_id=organization_id,
            stage=PipelineStageName.REVIEW_REGULATORY_PERSIST,
            status=PipelineStageStatus.FAILED,
            error_code="REVIEW_REGULATORY_PERSIST_FAILED",
            error_message=str(e),
            ordinal=50,
        )
        raise

    await upsert_stage(
        db,
        analysis_id=analysis.id,
        shipment_id=shipment_id,
        organization_id=organization_id,
        stage=PipelineStageName.REVIEW_REGULATORY_PERSIST,
        status=PipelineStageStatus.SUCCEEDED,
        ordinal=50,
    )

    shipment.status = ShipmentStatus.COMPLETE
    analysis.status = AnalysisStatus.COMPLETE
    analysis.completed_at = datetime.utcnow()
    analysis.result_json = sanitize_for_jsonb(result_json)
    await db.flush()
    trust_ok = await trust_gate_allows_trusted_status(
        db,
        analysis_id=analysis.id,
        shipment_id=shipment_id,
        items_count=len(shipment.items or []),
        result_json=result_json if isinstance(result_json, dict) else None,
        blockers=blockers,
    )
    analysis.decision_status = derive_decision_status(
        execution_status=AnalysisStatus.COMPLETE,
        result_json=result_json if isinstance(result_json, dict) else None,
        blockers=blockers,
        trust_eligible=trust_ok,
    )
    await maybe_promote_analysis_after_success(
        db,
        analysis_id=analysis.id,
        shipment_id=shipment_id,
        decision_status=analysis.decision_status,
    )
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
