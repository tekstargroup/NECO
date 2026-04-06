"""
Pipeline stage ledger: idempotent updates per (analysis_id, stage) for worker retries and TRUSTED gating.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analysis_pipeline_stage import (
    AnalysisPipelineStage,
    PipelineStageName,
    PipelineStageStatus,
)

logger = logging.getLogger(__name__)

# Base mandatory stages for TRUSTED (Phase 1 — see docs/PHASE1_TRUSTED_SEMANTICS.md).
# Phase 2 may append REASONING_TRACE_PERSIST when PHASE2_REASONING_TRACE_TRUSTED_REQUIRED is True.
_BASE_MANDATORY_STAGES_FOR_TRUSTED: Sequence[str] = (
    PipelineStageName.DOCUMENT_EVIDENCE,
    PipelineStageName.LINE_ITEM_IMPORT,
    PipelineStageName.CLASSIFICATION,
    PipelineStageName.FACT_PERSIST,
    PipelineStageName.REGULATORY_ENGINE,
    PipelineStageName.REVIEW_REGULATORY_PERSIST,
)

MANDATORY_STAGES_FOR_TRUSTED: Sequence[str] = _BASE_MANDATORY_STAGES_FOR_TRUSTED


def mandatory_stages_for_trusted() -> Sequence[str]:
    """Stages required for decision_status=TRUSTED; includes Phase 2 reasoning when enabled."""
    out: list[str] = list(_BASE_MANDATORY_STAGES_FOR_TRUSTED)
    if getattr(settings, "PHASE2_REASONING_TRACE_TRUSTED_REQUIRED", False):
        # Insert after FACT_PERSIST so ledger order matches pipeline semantics.
        idx = out.index(PipelineStageName.FACT_PERSIST) + 1
        out.insert(idx, PipelineStageName.REASONING_TRACE_PERSIST)
    return tuple(out)


def build_trust_contract_metadata() -> Dict[str, Any]:
    """Embedded under result_json.trust_contract for API/UI and audits."""
    mandatory = list(mandatory_stages_for_trusted())
    phase2_reasoning_gate = bool(getattr(settings, "PHASE2_REASONING_TRACE_TRUSTED_REQUIRED", False))
    return {
        "version": "phase2_v3",
        "stage_ledger_schema_version": 2,
        "deprecated_stage_ids": [
            PipelineStageName.CORE_ANALYSIS,
            PipelineStageName.CLASSIFICATION_AND_FACTS,
        ],
        "legacy_stage_equivalence": {
            PipelineStageName.CLASSIFICATION_AND_FACTS: [
                PipelineStageName.CLASSIFICATION,
                PipelineStageName.FACT_PERSIST,
            ],
        },
        "programmatic_consumer_rule": (
            "Use artifact_matrix[].in_trusted_contract (or trust_contract_consumer.classify_artifact_scope) "
            "per artifact; decision_status=TRUSTED does not authorize advisory fields for compliance by itself."
        ),
        "mandatory_stages_for_trusted": mandatory,
        "phase2_reasoning_trace_trusted_gate_enabled": phase2_reasoning_gate,
        "phase2b_regulatory_primary_key": "regulatory_evaluations.analysis_id",
        "phase2b_review_snapshot_derivation": "materialized_post_persist_from_canonical_db",
        "phase2c_line_provenance_model": "analysis_line_provenance_snapshots (frozen per analysis; live shipment_item_line_provenance is import truth)",
        "canonical_loader": "app.services.canonical_analysis_artifacts.load_canonical_analysis_artifacts",
        "tracked_advisory_stages": [PipelineStageName.DUTY_PSC_ADVISORY],
        "outputs_advisory_only": [
            "items[].duty",
            "items[].psc",
            "items[].prior_knowledge",
            "prior_knowledge_lookup_errors",
        ],
        "consumer_invariant": (
            "Do not treat decision_status=TRUSTED as a guarantee for duty, PSC, or product knowledge. "
            "Line provenance for explanation: canonical rows are analysis_line_provenance_snapshots "
            "(frozen at pipeline); live shipment_item_line_provenance may differ after later edits. "
            "heading_reasoning_trace: analysis_item_reasoning_traces; result_json is projection. "
            "Use trust_contract.outputs_advisory_only and artifact_matrix."
        ),
        "artifact_matrix": [
            {
                "artifact": "classification_engine_output",
                "canonical_source": "result_json.items[].classification",
                "retry_policy": "recompute_each_run",
                "in_trusted_contract": True,
                "stage": PipelineStageName.CLASSIFICATION,
            },
            {
                "artifact": "classification_facts_db",
                "canonical_source": "shipment_item_classification_facts",
                "retry_policy": "upsert_per_analysis_item",
                "in_trusted_contract": True,
                "stage": PipelineStageName.FACT_PERSIST,
            },
            {
                "artifact": "review_snapshot_db",
                "canonical_source": "review_records.object_snapshot (materialized projection; not parallel truth)",
                "retry_policy": "replace_after_pipeline_derives_from_db_plus_advisory_overlay",
                "in_trusted_contract": True,
                "stage": PipelineStageName.REVIEW_REGULATORY_PERSIST,
            },
            {
                "artifact": "regulatory_evaluations_db",
                "canonical_source": "regulatory_evaluations.analysis_id",
                "retry_policy": "delete_all_for_analysis_id_then_reinsert_from_engine_json",
                "in_trusted_contract": True,
                "advisory_scope": "none",
                "projection_status": "db_authoritative",
                "stage": PipelineStageName.REVIEW_REGULATORY_PERSIST,
            },
            {
                "artifact": "regulatory_conditions_db",
                "canonical_source": "regulatory_conditions via regulatory_evaluations.analysis_id FK chain",
                "retry_policy": "cascade_delete_with_parent_evaluation",
                "in_trusted_contract": True,
                "advisory_scope": "none",
                "projection_status": "db_authoritative",
                "stage": PipelineStageName.REVIEW_REGULATORY_PERSIST,
            },
            {
                "artifact": "duty_resolution_json",
                "canonical_source": "result_json.items[].duty",
                "retry_policy": "recomputed_json_not_authoritative_db",
                "in_trusted_contract": False,
                "stage": PipelineStageName.DUTY_PSC_ADVISORY,
            },
            {
                "artifact": "psc_json",
                "canonical_source": "result_json.items[].psc",
                "retry_policy": "recomputed_json_not_authoritative_db",
                "in_trusted_contract": False,
                "stage": PipelineStageName.DUTY_PSC_ADVISORY,
            },
            {
                "artifact": "heading_reasoning_trace",
                "canonical_source": "analysis_item_reasoning_traces.trace_json",
                "retry_policy": "upsert_per_analysis_item",
                "in_trusted_contract": phase2_reasoning_gate,
                "advisory_scope": "none",
                "projection_status": "result_json_derived_merge_on_read",
                "stage": PipelineStageName.REASONING_TRACE_PERSIST,
                "notes": "TRUSTED only when phase2_reasoning_trace_trusted_gate_enabled and stage SUCCEEDED",
            },
            {
                "artifact": "line_provenance_live_import",
                "canonical_source": "shipment_item_line_provenance",
                "retry_policy": "upsert_at_import_unique_item_doc_line",
                "in_trusted_contract": False,
                "advisory_scope": "import_truth_may_change",
                "projection_status": "live_shipment_state",
                "notes": "Not used for analysis replay; see line_provenance_snapshot",
            },
            {
                "artifact": "line_provenance_snapshot",
                "canonical_source": "analysis_line_provenance_snapshots",
                "retry_policy": "delete_all_for_analysis_then_copy_from_live_provenance",
                "in_trusted_contract": True,
                "advisory_scope": "none",
                "projection_status": "db_authoritative_for_analysis_replay",
                "stage": PipelineStageName.REVIEW_REGULATORY_PERSIST,
                "notes": "Frozen links for this analysis_id; explains classification/evidence context for the run",
            },
        ],
        "trusted_implies": [
            "document_evidence_stage_succeeded",
            "line_item_import_succeeded",
            "classification_stage_succeeded",
            "classification_facts_persist_stage_succeeded",
            "regulatory_engine_evaluation_succeeded",
            "review_and_regulatory_rows_persisted",
            "classification_facts_rows_present_per_item",
            "no_review_blockers",
            "no_critical_pipeline_errors",
            "all_mandatory_pipeline_stages_succeeded",
        ],
        "trusted_does_not_imply": [
            "duty_resolution_complete_or_authoritative",
            "psc_analysis_complete",
            "product_knowledge_lookup_succeeded",
            "provenance_line_completeness",
            "reasoning_trace_persisted_to_db",
            "every_optional_engine_output_succeeded",
            "duty_psc_advisory_stage_succeeded",
        ]
        if not phase2_reasoning_gate
        else [
            "duty_resolution_complete_or_authoritative",
            "psc_analysis_complete",
            "product_knowledge_lookup_succeeded",
            "provenance_line_completeness",
            "every_optional_engine_output_succeeded",
            "duty_psc_advisory_stage_succeeded",
        ],
    }


class PipelineStageContext:
    """Bound upserts for one analysis run — pass into run_full_shipment_analysis."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        analysis_id: UUID,
        shipment_id: UUID,
        organization_id: UUID,
    ) -> None:
        self.db = db
        self.analysis_id = analysis_id
        self.shipment_id = shipment_id
        self.organization_id = organization_id

    async def mark(
        self,
        stage: str,
        status: PipelineStageStatus,
        *,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        ordinal: int = 0,
    ) -> None:
        await upsert_stage(
            self.db,
            analysis_id=self.analysis_id,
            shipment_id=self.shipment_id,
            organization_id=self.organization_id,
            stage=stage,
            status=status,
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
            ordinal=ordinal,
        )


async def upsert_stage(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    organization_id: UUID,
    stage: str,
    status: PipelineStageStatus,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    error_details: Optional[Dict[str, Any]] = None,
    ordinal: int = 0,
) -> None:
    """
    Idempotent stage row update — safe for Celery retries on the same analysis_id.

    Uses SELECT + UPDATE or INSERT so retries replace the same logical stage row.
    """
    now = datetime.utcnow()
    r = await db.execute(
        select(AnalysisPipelineStage).where(
            and_(
                AnalysisPipelineStage.analysis_id == analysis_id,
                AnalysisPipelineStage.stage == stage,
            )
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        row = AnalysisPipelineStage(
            analysis_id=analysis_id,
            shipment_id=shipment_id,
            organization_id=organization_id,
            stage=stage,
            status=status,
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
            ordinal=ordinal,
        )
        if status == PipelineStageStatus.RUNNING:
            row.started_at = now
        if status in (
            PipelineStageStatus.SUCCEEDED,
            PipelineStageStatus.FAILED,
            PipelineStageStatus.SKIPPED,
        ):
            row.completed_at = now
        db.add(row)
    else:
        row.status = status
        row.error_code = error_code
        row.error_message = error_message
        row.error_details = error_details
        row.ordinal = ordinal
        if status == PipelineStageStatus.RUNNING:
            row.started_at = now
            row.completed_at = None
        if status in (
            PipelineStageStatus.SUCCEEDED,
            PipelineStageStatus.FAILED,
            PipelineStageStatus.SKIPPED,
        ):
            row.completed_at = now


def _legacy_classification_and_facts_succeeded(rows: Dict[str, AnalysisPipelineStage]) -> bool:
    """Pre-split ledger: one row CLASSIFICATION_AND_FACTS SUCCEEDED covered engine + facts."""
    leg = rows.get(PipelineStageName.CLASSIFICATION_AND_FACTS)
    return bool(leg and leg.status == PipelineStageStatus.SUCCEEDED)


async def all_mandatory_stages_succeeded(
    db: AsyncSession,
    *,
    analysis_id: UUID,
) -> bool:
    """True iff every mandatory stage row exists and is SUCCEEDED (with legacy equivalence)."""
    result = await db.execute(
        select(AnalysisPipelineStage).where(AnalysisPipelineStage.analysis_id == analysis_id)
    )
    rows = {r.stage: r for r in result.scalars().all()}
    legacy_cf = _legacy_classification_and_facts_succeeded(rows)
    for st in mandatory_stages_for_trusted():
        row = rows.get(st)
        if row and row.status == PipelineStageStatus.SUCCEEDED:
            continue
        if legacy_cf and st in (
            PipelineStageName.CLASSIFICATION,
            PipelineStageName.FACT_PERSIST,
        ):
            continue
        logger.warning(
            "Trust gate: stage %s missing or not SUCCEEDED for analysis %s (got %s, legacy_cf=%s)",
            st,
            analysis_id,
            row.status if row else None,
            legacy_cf,
        )
        return False
    return True
