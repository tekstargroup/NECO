"""
Analysis Celery Task - Sprint 12

Async analysis orchestration job.
Job steps in order:
1. Load shipment + items + references + shipment_documents (org-scoped)
2. Parse PDFs and build evidence pointers
3. Run existing engines: classification, duty resolver, PSC radar, enrichment
4. Run Side Sprint A regulatory applicability evaluation
5. Create ReviewRecord + persist regulatory rows to it
6. Update shipment.status = COMPLETE (or REVIEW_REQUIRED if blockers)
7. Update analysis.status = COMPLETE and store result_json for Sprint 11 rendering
8. Emit analysis_completed, review_required_triggered if applicable
"""

import enum
import logging
import math
import traceback
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import Base
from app.models.shipment import Shipment, ShipmentStatus
from app.models.shipment_document import ShipmentDocument
from app.models.analysis import Analysis, AnalysisStatus
from app.models.review_record import ReviewRecord, ReviewableObjectType, ReviewStatus, ReviewReasonCode
from app.models.regulatory_evaluation import RegulatoryEvaluation, RegulatoryCondition, Regulator, RegulatoryOutcome, ConditionState
from app.repositories.org_scoped_repository import OrgScopedRepository
from app.services.shipment_eligibility_service import ShipmentEligibilityService
from app.services.shipment_analysis_service import ShipmentAnalysisService
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID

logger = logging.getLogger(__name__)


def _sanitize_for_jsonb(obj: Any) -> Any:
    """Recursively sanitize for JSONB: NaN/inf/numpy -> JSON-serializable. Prevents InvalidTextRepresentationError."""
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
        return {k: _sanitize_for_jsonb(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_jsonb(v) for v in obj]
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, (UUID, datetime)):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return _sanitize_for_jsonb(obj.__dict__)
    return obj


# Create async engine for Celery tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=None)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="app.tasks.analysis.run_shipment_analysis", bind=True)
def run_shipment_analysis(
    self,
    shipment_id: str,
    organization_id: str,
    actor_user_id: str,
    clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Celery task to run shipment analysis.
    
    Args:
        shipment_id: Shipment ID (UUID string)
        organization_id: Organization ID (UUID string)
        actor_user_id: User ID who initiated analysis (UUID string)
    
    Returns:
        Task result dict
    """
    shipment_uuid = UUID(shipment_id)
    org_uuid = UUID(organization_id)
    user_uuid = UUID(actor_user_id)
    
    # Run async analysis - create session inside async context
    import asyncio
    try:
        result = asyncio.run(_run_analysis_async(
            shipment_uuid, org_uuid, user_uuid, self.request.id,
            clarification_responses=clarification_responses,
        ))
        return result
    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)
        # Update analysis status to FAILED - create new session for error handling
        try:
            asyncio.run(_mark_analysis_failed(shipment_uuid, str(e)))
        except Exception as error_handler_error:
            logger.error(f"Failed to mark analysis as failed: {error_handler_error}", exc_info=True)
        raise


async def _run_analysis_async(
    shipment_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID,
    celery_task_id: str,
    clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Async analysis execution."""
    
    # Create async session inside async context
    async with AsyncSessionLocal() as db:
        # Get analysis record
        result = await db.execute(
            select(Analysis).where(
                and_(
                    Analysis.shipment_id == shipment_id,
                    Analysis.organization_id == organization_id
                )
            ).order_by(Analysis.created_at.desc()).limit(1)
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            raise ValueError(f"Analysis record not found for shipment {shipment_id}")
        
        # Update status to RUNNING
        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.utcnow()
        analysis.celery_task_id = celery_task_id
        await db.commit()
        logger.info("Analysis task RUNNING for shipment %s (analysis_id=%s)", shipment_id, analysis.id)

        try:
            # Update shipment status to ANALYZING
            repo = OrgScopedRepository(db, Shipment)
            shipment = await repo.get_by_id(shipment_id, organization_id)
            shipment.status = ShipmentStatus.ANALYZING
            await db.commit()
            
            # Run full analysis (wraps all engines)
            analysis_service = ShipmentAnalysisService(db)
            result_json, review_snapshot, blockers = await analysis_service.run_full_shipment_analysis(
                shipment_id=shipment_id,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                clarification_responses=clarification_responses,
            )
            
            # Update review_snapshot with analysis_id
            review_snapshot["analysis_id"] = str(analysis.id)
            
            # Step 5: Create ReviewRecord snapshot (sanitize for JSONB - NaN/non-serializable cause InvalidTextRepresentationError)
            snapshot_sanitized = _sanitize_for_jsonb(review_snapshot)
            review_record = ReviewRecord(
                object_type=ReviewableObjectType.CLASSIFICATION,  # Using CLASSIFICATION for now
                object_snapshot=snapshot_sanitized,
                hts_version_id=AUTHORITATIVE_HTS_VERSION_ID,
                status=ReviewStatus.REVIEW_REQUIRED if blockers else ReviewStatus.DRAFT,
                created_by=str(actor_user_id),
                review_reason_code=ReviewReasonCode.AUTO_CREATED
            )
            db.add(review_record)
            await db.flush()  # Flush to get review_record.id
            
            # Step 6: Persist regulatory evaluations linked to review_id
            regulatory_evaluations_data = review_snapshot.get("regulatory_evaluations", [])
            
            for reg_eval_data in regulatory_evaluations_data:
                # Handle regulator and outcome (they may be Enum values or strings)
                regulator = reg_eval_data["regulator"]
                if isinstance(regulator, str):
                    regulator = Regulator(regulator)
                outcome = reg_eval_data["outcome"]
                if isinstance(outcome, str):
                    outcome = RegulatoryOutcome(outcome)
                
                # Create RegulatoryEvaluation
                reg_eval = RegulatoryEvaluation(
                    review_id=review_record.id,
                    regulator=regulator,
                    outcome=outcome,
                    explanation_text=reg_eval_data["explanation_text"],
                    triggered_by_hts_code=reg_eval_data["triggered_by_hts_code"]
                )
                db.add(reg_eval)
                await db.flush()  # Flush to get reg_eval.id
                
                # Create RegulatoryConditions
                condition_evaluations = reg_eval_data.get("condition_evaluations", [])
                for condition_eval in condition_evaluations:
                    # Handle condition_eval - could be dataclass instance or dict
                    if hasattr(condition_eval, "condition_id"):
                        # It's a ConditionEvaluation dataclass
                        condition_id = condition_eval.condition_id
                        state = condition_eval.state
                        if isinstance(state, str):
                            state = ConditionState(state)
                        evidence_refs = condition_eval.evidence_refs
                    else:
                        # It's a dict
                        condition_id = condition_eval.get("condition_id")
                        state = condition_eval.get("state")
                        if isinstance(state, str):
                            state = ConditionState(state)
                        evidence_refs = condition_eval.get("evidence_refs", [])
                    
                    # Convert evidence_refs to JSON-serializable format
                    evidence_refs_json = []
                    for ev_ref in evidence_refs:
                        if hasattr(ev_ref, "__dict__"):
                            evidence_refs_json.append(ev_ref.__dict__)
                        elif isinstance(ev_ref, dict):
                            evidence_refs_json.append(ev_ref)
                        else:
                            # Fallback: convert to dict if possible
                            evidence_refs_json.append(str(ev_ref))
                    
                    reg_condition = RegulatoryCondition(
                        evaluation_id=reg_eval.id,
                        condition_id=condition_id,
                        condition_description=None,  # TODO: Get from definition if available
                        state=state,
                        evidence_refs=evidence_refs_json
                    )
                    db.add(reg_condition)
            
            # Link analysis to review_record
            analysis.review_record_id = review_record.id
            
            # Step 7: Update shipment and analysis status
            # Determine final status based on blockers
            if blockers:
                shipment.status = ShipmentStatus.COMPLETE  # Keep COMPLETE, REVIEW_REQUIRED is on ReviewRecord
                review_required_triggered = True
            else:
                shipment.status = ShipmentStatus.COMPLETE
                review_required_triggered = False
            
            # Step 8: Store result_json for Sprint 11 rendering (sanitize - same NaN/numpy issue as object_snapshot)
            analysis.status = AnalysisStatus.COMPLETE
            analysis.completed_at = datetime.utcnow()
            analysis.result_json = _sanitize_for_jsonb(result_json)
            
            await db.commit()
            
            # Emit events (TODO: wire up event emitter)
            # events.emit("analysis_completed", {...})
            # if review_required_triggered:
            #     events.emit("review_required_triggered", {...})
            
            logger.info(f"Analysis completed for shipment {shipment_id}: {analysis.id}, review_record: {review_record.id}")
            
            return {
                "status": "complete",
                "analysis_id": str(analysis.id),
                "review_record_id": str(review_record.id),
                "blockers": blockers
            }
            
        except Exception as e:
            logger.error(f"Analysis execution failed: {e}", exc_info=True)
            # Use fresh session - task's db may be rolled back and cannot be used
            await _mark_analysis_failed(shipment_id, str(e))
            raise


async def _mark_analysis_failed(
    shipment_id: UUID,
    error_message: str
) -> None:
    """Mark analysis as failed - creates its own session."""
    async with AsyncSessionLocal() as db:
        await _mark_analysis_failed_internal(db, shipment_id, error_message)


async def _mark_analysis_failed_internal(
    db: AsyncSession,
    shipment_id: UUID,
    error_message: str
) -> None:
    """Mark analysis as failed - uses provided session."""
    result = await db.execute(
        select(Analysis).where(Analysis.shipment_id == shipment_id).order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = result.scalar_one_or_none()
    
    if analysis:
        analysis.status = AnalysisStatus.FAILED
        analysis.failed_at = datetime.utcnow()
        analysis.error_message = error_message
        analysis.error_details = {"error": str(error_message)}
        await db.commit()
    
    # Update shipment status
    result = await db.execute(select(Shipment).where(Shipment.id == shipment_id))
    shipment = result.scalar_one_or_none()
    if shipment:
        shipment.status = ShipmentStatus.FAILED
        await db.commit()
