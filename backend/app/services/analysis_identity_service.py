"""
Phase 1 — Analysis identity, active promotion, and decision_status derivation.

**Invariant (Phase 1):** An `Analysis` row is an immutable snapshot of the **full shipment**
(all line items) for that run version. Promotion is shipment-wide: one active analysis per
shipment; every `shipment_item` points at the same `active_analysis_id`.

Primary key for a run remains `analyses.id` (APIs may call this `analysis_id`).

Resolution **never** uses `created_at` as authority. Tie-breakers use `version` (monotonic per
shipment) and explicit `status`, never timestamps.

**Resolution contract (critical):**

- ``resolve_display_analysis`` — **UI / continuity / admin read shim only.** May return an
  in-flight row, the promoted ``is_active`` row, or a **terminal fallback** (highest
  ``version``) when nothing is promoted. That fallback is *not* authoritative for compliance,
  filing, duty, grounded chat, or any decision that must not depend on “best available.”

- ``resolve_authoritative_analysis`` — **promoted snapshot only** (``is_active``). This is the
  shipment-level authoritative analysis for “what the platform has elevated,” or ``None`` if
  nothing is promoted yet.

- **Explicit ``analysis_id``** — Any decision-critical path that refers to a *specific* run
  (including in-flight) must load that row by id after org scope checks — do not infer from
  display resolution alone.

See ``docs/PHASE1_RESOLUTION_CONTRACT.md``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analysis import Analysis, AnalysisStatus, DecisionStatus
from app.models.shipment import ShipmentItem
from app.models.shipment_item_classification_facts import ShipmentItemClassificationFacts
from app.services.pipeline_stage_service import all_mandatory_stages_succeeded

logger = logging.getLogger(__name__)


class AnalysisIntegrityError(RuntimeError):
    """Data or configuration violates Phase 1 analysis invariants."""


async def next_analysis_version(db: AsyncSession, shipment_id: UUID) -> int:
    """Monotonic version per shipment (new row for each run)."""
    result = await db.execute(
        select(func.coalesce(func.max(Analysis.version), 0)).where(Analysis.shipment_id == shipment_id)
    )
    return int(result.scalar_one()) + 1


async def promote_analysis_to_active(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
) -> None:
    """
    Mark this analysis as the active run for the shipment and point all line items at it.
    Clears is_active on sibling analyses. Idempotent for same analysis_id.

    Phase 1: one authoritative snapshot per shipment; item pointers mirror that row.
    DB enforces at most one is_active per shipment (partial unique index, migration 019+).
    """
    await db.execute(
        update(Analysis)
        .where(and_(Analysis.shipment_id == shipment_id, Analysis.id != analysis_id))
        .values(is_active=False)
    )
    await db.execute(update(Analysis).where(Analysis.id == analysis_id).values(is_active=True))
    await db.execute(
        update(ShipmentItem)
        .where(ShipmentItem.shipment_id == shipment_id)
        .values(active_analysis_id=analysis_id)
    )


def _is_explicit_local_dev() -> bool:
    return (settings.ENVIRONMENT or "").lower() in {"development", "dev", "local"}


async def maybe_promote_analysis_after_success(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    decision_status: Optional[DecisionStatus],
) -> bool:
    """
    Promotion = authoritative surfaced analysis. Rules:

    - TRUSTED: auto-promote (full trust gate passed in derive + pipeline).
    - REVIEW_REQUIRED: promote only if ANALYSIS_PROMOTE_REVIEW_REQUIRED is True (product: “active but pending review”).
    - DEGRADED: promote only if ANALYSIS_ALLOW_DEGRADED_PROMOTION is True **and** explicit local dev —
      never in staging/production-like environments by default.
    - Other / None: do not promote.
    """
    if decision_status == DecisionStatus.TRUSTED:
        await promote_analysis_to_active(db, analysis_id=analysis_id, shipment_id=shipment_id)
        return True
    if decision_status == DecisionStatus.REVIEW_REQUIRED:
        if getattr(settings, "ANALYSIS_PROMOTE_REVIEW_REQUIRED", False):
            await promote_analysis_to_active(db, analysis_id=analysis_id, shipment_id=shipment_id)
            return True
        return False
    if decision_status == DecisionStatus.DEGRADED:
        if getattr(settings, "ANALYSIS_ALLOW_DEGRADED_PROMOTION", False) and _is_explicit_local_dev():
            await promote_analysis_to_active(db, analysis_id=analysis_id, shipment_id=shipment_id)
            return True
        logger.info(
            "Skipping promotion for DEGRADED analysis %s (set ANALYSIS_ALLOW_DEGRADED_PROMOTION=true in local dev if needed)",
            analysis_id,
        )
        return False
    return False


async def trust_gate_allows_trusted_status(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    shipment_id: UUID,
    items_count: int,
    result_json: Optional[Dict[str, Any]],
    blockers: Optional[List[Any]],
) -> bool:
    """
    TRUSTED is gated — not the default residue of COMPLETE.

    **Phase 1 slice:** TRUSTED requires ``SUCCEEDED`` on all mandatory stages listed in
    ``MANDATORY_STAGES_FOR_TRUSTED`` (see ``docs/PHASE1_TRUSTED_SEMANTICS.md`` and
    ``result_json.trust_contract``), plus the checks below. Duty/PSC/product-knowledge outputs
    are not part of that mandatory set unless explicitly promoted later.

    Required for True:
    - No review blockers
    - Not a degraded dev mode (INSTANT_DEV / FAST_LOCAL_DEV)
    - One classification-facts row per line item when items_count > 0
    - No critical_pipeline_errors in payload (when present)
    - All mandatory pipeline stage rows exist and are ``SUCCEEDED``
    """
    if blockers:
        return False
    payload = result_json if isinstance(result_json, dict) else {}
    mode = payload.get("mode")
    if mode in ("INSTANT_DEV", "FAST_LOCAL_DEV"):
        return False
    crit = payload.get("critical_pipeline_errors") or []
    if isinstance(crit, list) and len(crit) > 0:
        return False
    if items_count > 0:
        r = await db.execute(
            select(func.count())
            .select_from(ShipmentItemClassificationFacts)
            .where(ShipmentItemClassificationFacts.analysis_id == analysis_id)
        )
        fact_rows = int(r.scalar_one() or 0)
        if fact_rows < items_count:
            logger.warning(
                "Trust gate: expected %s classification_facts rows for analysis %s, found %s",
                items_count,
                analysis_id,
                fact_rows,
            )
            return False
    if not await all_mandatory_stages_succeeded(db, analysis_id=analysis_id):
        return False
    return True


def derive_decision_status(
    *,
    execution_status: AnalysisStatus,
    result_json: Optional[Dict[str, Any]],
    blockers: Optional[List[Any]],
    trust_eligible: bool = False,
) -> Optional[DecisionStatus]:
    """
    Decision layer (orthogonal to execution). TRUSTED requires trust_eligible=True from
    trust_gate_allows_trusted_status — never inferred from “COMPLETE and empty blockers” alone.
    """
    if execution_status != AnalysisStatus.COMPLETE:
        return None
    payload = result_json if isinstance(result_json, dict) else {}
    mode = payload.get("mode")
    if mode == "INSTANT_DEV":
        return DecisionStatus.DEGRADED
    if mode == "FAST_LOCAL_DEV":
        return DecisionStatus.DEGRADED
    if blockers:
        return DecisionStatus.REVIEW_REQUIRED
    if not trust_eligible:
        return DecisionStatus.REVIEW_REQUIRED
    return DecisionStatus.TRUSTED


async def resolve_authoritative_analysis(
    db: AsyncSession,
    *,
    shipment_id: UUID,
    organization_id: UUID,
) -> Optional[Analysis]:
    """
    **Authoritative** shipment-level analysis: the single promoted row ``is_active == True``.

    Use for any logic that must align with “what the platform treats as the active snapshot”
    (filing, compliance hooks, exports keyed to active run, etc.). Returns ``None`` if nothing
    has been promoted yet.

    Does **not** include in-flight QUEUED/RUNNING rows and does **not** use terminal
    highest-version fallback — those are not authoritative completed snapshots.
    """
    r = await db.execute(
        select(Analysis).where(
            and_(
                Analysis.shipment_id == shipment_id,
                Analysis.organization_id == organization_id,
                Analysis.is_active.is_(True),
            )
        )
    )
    rows = r.scalars().all()
    if len(rows) == 0:
        return None
    if len(rows) > 1:
        raise AnalysisIntegrityError(
            f"Multiple authoritative (is_active) analyses for shipment {shipment_id}"
        )
    return rows[0]


async def get_scoped_analysis(
    db: AsyncSession,
    *,
    analysis_id: UUID,
    organization_id: UUID,
    shipment_id: Optional[UUID] = None,
) -> Optional[Analysis]:
    """
    Load a specific analysis by id with org scope (and optional shipment scope).

    Use for **explicit** ``analysis_id`` from clients or jobs — required for decision-critical
    paths that refer to a particular run (including in-flight).
    """
    q = select(Analysis).where(
        Analysis.id == analysis_id,
        Analysis.organization_id == organization_id,
    )
    if shipment_id is not None:
        q = q.where(Analysis.shipment_id == shipment_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()


async def resolve_display_analysis(
    db: AsyncSession,
    *,
    shipment_id: UUID,
    organization_id: UUID,
) -> Optional[Analysis]:
    """
    **Display / read shim — not authoritative for compliance or filing.**

    Choose a reasonable row for “what to show” (status strings, list/detail summaries).

    Ordering rules (no created_at authority):
    1. In-flight QUEUED / RUNNING — highest `version` if multiple (bug / race).
    2. Promoted row (`is_active`); DB guarantees at most one per shipment when index present.
    3. No rows → None.
    4. **Temporary shim:** otherwise terminal rows — **highest `version`** only (unpromoted
       runs). Acceptable for display continuity **only**; do not treat as equivalent to
       ``resolve_authoritative_analysis``.

    For duty, chat, export, or regulatory decisions, use ``resolve_authoritative_analysis``,
    ``get_scoped_analysis(analysis_id=...)``, or an API that requires explicit ``analysis_id``.

    Multiple `is_active=true` rows for one shipment raises `AnalysisIntegrityError`
    (should be impossible once partial unique index `019` is applied).
    """
    base = and_(Analysis.shipment_id == shipment_id, Analysis.organization_id == organization_id)

    r_inf = await db.execute(
        select(Analysis)
        .where(
            base,
            Analysis.status.in_((AnalysisStatus.QUEUED, AnalysisStatus.RUNNING)),
        )
        .order_by(Analysis.version.desc())
    )
    inflight = r_inf.scalars().all()
    if inflight:
        if len(inflight) > 1:
            logger.error(
                "Multiple in-flight analyses for shipment %s (versions %s); using highest version",
                shipment_id,
                [x.version for x in inflight],
            )
        return inflight[0]

    r_act = await db.execute(select(Analysis).where(base, Analysis.is_active.is_(True)))
    actives = r_act.scalars().all()
    if len(actives) == 1:
        return actives[0]
    if len(actives) > 1:
        raise AnalysisIntegrityError(
            f"Multiple is_active analyses for shipment {shipment_id}; violates partial unique index"
        )

    r_any = await db.execute(select(func.count()).select_from(Analysis).where(base))
    total = int(r_any.scalar_one() or 0)
    if total == 0:
        return None

    r_term = await db.execute(select(Analysis).where(base).order_by(Analysis.version.desc()).limit(1))
    return r_term.scalar_one_or_none()
