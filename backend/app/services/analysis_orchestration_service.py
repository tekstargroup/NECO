"""
Analysis Orchestration Service - Sprint 12

Orchestrates analysis execution with strict ordering:
1. Org scope check
2. Eligibility gate
3. Entitlement check and increment (atomic)
4. Idempotency guard
5. Enqueue Celery job
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.shipment import Shipment, ShipmentStatus
from app.models.analysis import Analysis, AnalysisStatus, RefusalReasonCode
from app.repositories.org_scoped_repository import OrgScopedRepository
from app.services.entitlement_service import EntitlementService
from app.services.shipment_eligibility_service import ShipmentEligibilityService
from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisOrchestrationService:
    """Service for orchestrating shipment analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.entitlement_service = EntitlementService(db)
        self.eligibility_service = ShipmentEligibilityService(db)
    
    async def start_analysis(
        self,
        shipment_id: UUID,
        organization_id: UUID,
        actor_user_id: UUID,
        force_new: bool = False,
        clarification_responses: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Start analysis with strict ordering:
        1. Org scope check (404 on mismatch)
        2. Eligibility gate (if not eligible: create Analysis REFUSED, no entitlement increment)
        3. Entitlement check and increment (atomic, if exceeded: Analysis REFUSED)
        4. Idempotency guard (if QUEUED/RUNNING exists, return that)
        5. Enqueue Celery job
        
        Args:
            shipment_id: Shipment ID
            organization_id: Organization ID
            actor_user_id: User ID who initiated analysis
        
        Returns:
            Analysis creation result
        
        Raises:
            HTTPException: 404 on org mismatch, 403 on entitlement exceeded
        """
        # Step 1: Org scope check (404 on mismatch)
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        
        # Step 2: Eligibility gate
        eligibility = await self.eligibility_service.compute_eligibility(shipment_id)
        
        if not eligibility["eligible"]:
            # Create Analysis REFUSED with INSUFFICIENT_DOCUMENTS
            analysis = Analysis(
                shipment_id=shipment_id,
                organization_id=organization_id,
                status=AnalysisStatus.REFUSED,
                refusal_reason_code=RefusalReasonCode.INSUFFICIENT_DOCUMENTS,
                refusal_reason_text="; ".join(eligibility["missing_requirements"])
            )
            self.db.add(analysis)
            await self.db.commit()
            await self.db.refresh(analysis)
            
            # Emit event: analysis_refused
            # TODO: events.emit("analysis_refused", {...})
            
            logger.info(f"Analysis refused for shipment {shipment_id}: {eligibility['missing_requirements']}")
            
            return {
                "analysis_id": str(analysis.id),
                "status": analysis.status.value,
                "refusal_reason_code": analysis.refusal_reason_code.value if analysis.refusal_reason_code else None,
                "refusal_reason_text": analysis.refusal_reason_text,
                "eligibility": eligibility
            }
        
        # Step 3: Entitlement check and increment (atomic with transaction)
        try:
            entitlement = await self.entitlement_service.increment_on_analysis_start(
                user_id=actor_user_id,
                shipment_id=shipment_id
            )
        except HTTPException as e:
            # Entitlement exceeded - create Analysis REFUSED
            detail = e.detail
            if isinstance(detail, dict):
                message = detail.get("message", "Monthly entitlement limit exceeded")
            else:
                message = str(detail)
            
            analysis = Analysis(
                shipment_id=shipment_id,
                organization_id=organization_id,
                status=AnalysisStatus.REFUSED,
                refusal_reason_code=RefusalReasonCode.ENTITLEMENT_EXCEEDED,
                refusal_reason_text=message
            )
            self.db.add(analysis)
            await self.db.commit()
            await self.db.refresh(analysis)
            
            # Emit event: analysis_refused
            # TODO: events.emit("analysis_refused", {...})
            
            logger.info(f"Analysis refused for shipment {shipment_id}: entitlement exceeded")
            
            return {
                "analysis_id": str(analysis.id),
                "status": analysis.status.value,
                "refusal_reason_code": analysis.refusal_reason_code.value if analysis.refusal_reason_code else None,
                "refusal_reason_text": analysis.refusal_reason_text
            }
        
        # Step 4: Idempotency guard (check for QUEUED/RUNNING analysis)
        result = await self.db.execute(
            select(Analysis).where(
                and_(
                    Analysis.shipment_id == shipment_id,
                    Analysis.status.in_([AnalysisStatus.QUEUED, AnalysisStatus.RUNNING])
                )
            ).order_by(Analysis.created_at.desc())
        )
        existing_analysis = result.scalar_one_or_none()

        # force_new: user requested a fresh run (e.g. Re-run); supersede any QUEUED/RUNNING
        if force_new and existing_analysis:
            existing_analysis.status = AnalysisStatus.FAILED
            existing_analysis.failed_at = datetime.utcnow()
            existing_analysis.error_message = "Superseded by new run (Re-run)."
            existing_analysis.error_details = {"force_new": True}
            await self.db.commit()
            logger.info("Force new run: marked analysis %s as FAILED for shipment %s", existing_analysis.id, shipment_id)
            existing_analysis = None

        # If RUNNING for too long, treat as stale so Re-run can start a fresh analysis (short window so user isn't stuck)
        if not force_new and existing_analysis:
            STALE_RUNNING_MINUTES = 1
            if (
                existing_analysis.status == AnalysisStatus.RUNNING
                and existing_analysis.started_at
                and (datetime.utcnow() - existing_analysis.started_at) > timedelta(minutes=STALE_RUNNING_MINUTES)
            ):
                existing_analysis.status = AnalysisStatus.FAILED
                existing_analysis.failed_at = datetime.utcnow()
                existing_analysis.error_message = "Analysis timed out or was interrupted; Re-run to try again."
                existing_analysis.error_details = {"stale_running_minutes": STALE_RUNNING_MINUTES}
                await self.db.commit()
                logger.warning(
                    "Marked stale RUNNING analysis as FAILED for shipment %s (started %s min ago); allowing new run.",
                    shipment_id,
                    (datetime.utcnow() - existing_analysis.started_at).total_seconds() / 60,
                )
                existing_analysis = None

        if existing_analysis:
            if (
                settings.SPRINT12_INLINE_ANALYSIS_DEV
                and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}
                and existing_analysis.status == AnalysisStatus.QUEUED
                and existing_analysis.started_at is None
            ):
                # Re-dispatch stale queued analysis in local/dev when no worker consumed it.
                from app.tasks.analysis import _run_analysis_async

                if not existing_analysis.celery_task_id:
                    existing_analysis.celery_task_id = f"inline-{existing_analysis.id}"
                    await self.db.commit()

                asyncio.create_task(
                    _run_analysis_async(
                        shipment_id=shipment_id,
                        organization_id=organization_id,
                        actor_user_id=actor_user_id,
                        celery_task_id=existing_analysis.celery_task_id,
                    )
                )

            # Idempotency: return existing analysis
            logger.info(f"Analysis already in progress for shipment {shipment_id}: {existing_analysis.id}")
            return {
                "analysis_id": str(existing_analysis.id),
                "status": existing_analysis.status.value,
                "celery_task_id": existing_analysis.celery_task_id,
                "queued_at": existing_analysis.queued_at.isoformat() if existing_analysis.queued_at else None,
                "message": "Analysis already in progress"
            }
        
        # Step 5: Create Analysis QUEUED and enqueue Celery job
        instant_dev = getattr(settings, "SPRINT12_INSTANT_ANALYSIS_DEV", False)
        inline = settings.SPRINT12_INLINE_ANALYSIS_DEV and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}
        sync = getattr(settings, "SPRINT12_SYNC_ANALYSIS_DEV", True)
        logger.info(
            "Analysis start shipment_id=%s INSTANT_DEV=%s INLINE_DEV=%s SYNC_DEV=%s ENV=%s",
            shipment_id, instant_dev, settings.SPRINT12_INLINE_ANALYSIS_DEV, getattr(settings, "SPRINT12_SYNC_ANALYSIS_DEV", True),
            settings.ENVIRONMENT,
        )
        analysis = Analysis(
            shipment_id=shipment_id,
            organization_id=organization_id,
            status=AnalysisStatus.QUEUED
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)

        # Dev-only: return immediately with minimal COMPLETE result so the UI shows results while the real pipeline is fixed.
        if getattr(settings, "SPRINT12_INSTANT_ANALYSIS_DEV", False) and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
            logger.info("SPRINT12_INSTANT_ANALYSIS_DEV: returning minimal COMPLETE result immediately for shipment %s", shipment_id)
            repo = OrgScopedRepository(self.db, Shipment)
            shipment = await repo.get_by_id(shipment_id, organization_id)
            await self.db.refresh(shipment, ["items"])
            minimal_result = {
                "shipment_id": str(shipment_id),
                "items": [
                    {
                        "id": str(i.id),
                        "label": i.label,
                        "hts_code": getattr(i, "declared_hts", None) or getattr(i, "declared_hts_code", None),
                        "classification": None,
                        "duty": None,
                        "psc": None,
                        "regulatory": [],
                    }
                    for i in (shipment.items or [])
                ],
                "evidence_map": {"documents": [], "warnings": [], "extraction_errors": []},
                "blockers": [],
                "review_status": "DRAFT",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "INSTANT_DEV",
            }
            analysis.status = AnalysisStatus.COMPLETE
            analysis.started_at = analysis.started_at or datetime.utcnow()
            analysis.completed_at = datetime.utcnow()
            analysis.result_json = minimal_result
            analysis.celery_task_id = analysis.celery_task_id or f"instant-{analysis.id}"
            await self.db.commit()
            payload = await self.get_analysis_status(shipment_id=shipment_id, organization_id=organization_id)
            payload["sync"] = True
            return payload

        if settings.SPRINT12_INLINE_ANALYSIS_DEV and settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
            from app.tasks.analysis import _run_analysis_async
            inline_task_id = f"inline-{analysis.id}"
            analysis.celery_task_id = inline_task_id
            await self.db.commit()

            if getattr(settings, "SPRINT12_SYNC_ANALYSIS_DEV", True):
                # Run analysis in this request with a hard timeout so the request cannot hang forever.
                SYNC_TIMEOUT_SECONDS = 4 * 60  # 4 minutes
                logger.info(
                    "Running analysis synchronously (SPRINT12_SYNC_ANALYSIS_DEV); request will block up to %s seconds.",
                    SYNC_TIMEOUT_SECONDS,
                )
                try:
                    await asyncio.wait_for(
                        _run_analysis_async(
                            shipment_id=shipment_id,
                            organization_id=organization_id,
                            actor_user_id=actor_user_id,
                            celery_task_id=inline_task_id,
                            clarification_responses=clarification_responses,
                        ),
                        timeout=SYNC_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Sync analysis timed out after %s seconds for shipment %s; marking FAILED.", SYNC_TIMEOUT_SECONDS, shipment_id)
                    await self.db.refresh(analysis)
                    analysis.status = AnalysisStatus.FAILED
                    analysis.failed_at = datetime.utcnow()
                    analysis.error_message = f"Analysis timed out after {SYNC_TIMEOUT_SECONDS // 60} minutes. The pipeline may be slow or stuck—try Re-run or check backend logs."
                    analysis.error_details = {"sync_timeout_seconds": SYNC_TIMEOUT_SECONDS}
                    # Clear shipment.status from ANALYZING so Re-run is not blocked (task was cancelled, never reached COMPLETE)
                    repo = OrgScopedRepository(self.db, Shipment)
                    shipment = await repo.get_by_id(shipment_id, organization_id)
                    if shipment.status == ShipmentStatus.ANALYZING:
                        shipment.status = ShipmentStatus.FAILED
                    await self.db.commit()
                except Exception as e:
                    logger.exception("Sync analysis failed: %s", e)
                    # #region agent log
                    import json
                    _log_path = "/Users/stevenbigio/Cursor Projects/NECO/logs/debug_analysis_aa7c8f.log"
                    with open(_log_path, "a") as _f:
                        _f.write(json.dumps({"sessionId":"aa7c8f","location":"orchestration:sync_exception","message":"Sync analysis exception","data":{"error":str(e)[:300],"error_type":type(e).__name__},"hypothesisId":"H6","timestamp":int(__import__("time").time()*1000)}) + "\n")
                    # #endregion
                    # Clear shipment.status from ANALYZING if stuck (task may have set it before raising)
                    repo = OrgScopedRepository(self.db, Shipment)
                    shipment = await repo.get_by_id(shipment_id, organization_id)
                    if shipment.status == ShipmentStatus.ANALYZING:
                        shipment.status = ShipmentStatus.FAILED
                        await self.db.commit()
                # Return full status (same shape as get_analysis_status) so frontend can show results immediately.
                payload = await self.get_analysis_status(shipment_id=shipment_id, organization_id=organization_id)
                payload["sync"] = True
                return payload
            asyncio.create_task(
                _run_analysis_async(
                    shipment_id=shipment_id,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    celery_task_id=inline_task_id,
                    clarification_responses=clarification_responses,
                )
            )
        else:
            # Enqueue Celery job
            task = celery_app.send_task(
                "app.tasks.analysis.run_shipment_analysis",
                args=[str(shipment_id), str(organization_id), str(actor_user_id)],
                kwargs={"clarification_responses": clarification_responses} if clarification_responses else {},
                task_id=str(analysis.id)  # Use analysis ID as task ID for tracking
            )

            # Update analysis with Celery task ID
            analysis.celery_task_id = task.id
            await self.db.commit()
        
        # Emit event: analysis_started
        # TODO: events.emit("analysis_started", {...})
        
        logger.info(f"Analysis queued for shipment {shipment_id}: {analysis.id} (task: {analysis.celery_task_id})")
        
        return {
            "analysis_id": str(analysis.id),
            "status": analysis.status.value,
            "celery_task_id": analysis.celery_task_id,
            "queued_at": analysis.queued_at.isoformat() if analysis.queued_at else None
        }
    
    async def get_analysis_status(
        self,
        shipment_id: UUID,
        organization_id: UUID
    ) -> Dict[str, Any]:
        """
        Get latest analysis status for shipment.
        
        Returns:
            Latest Analysis + linked ReviewRecord info
        """
        # Verify shipment belongs to org
        repo = OrgScopedRepository(self.db, Shipment)
        shipment = await repo.get_by_id(shipment_id, organization_id)
        
        # Get latest analysis
        result = await self.db.execute(
            select(Analysis).where(
                and_(
                    Analysis.shipment_id == shipment_id,
                    Analysis.organization_id == organization_id
                )
            ).order_by(Analysis.created_at.desc()).limit(1)
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found for this shipment"
            )
        
        # Get linked ReviewRecord (if exists)
        review_record_info = None
        if analysis.review_record_id:
            from app.models.review_record import ReviewRecord
            result = await self.db.execute(
                select(ReviewRecord).where(ReviewRecord.id == analysis.review_record_id)
            )
            review_record = result.scalar_one_or_none()
            if review_record:
                review_record_info = {
                    "id": str(review_record.id),
                    "status": review_record.status.value,
                    "reviewed_by": review_record.reviewed_by,
                    "reviewed_at": review_record.reviewed_at.isoformat() if review_record.reviewed_at else None
                }
        
        payload = {
            "analysis_id": str(analysis.id),
            "status": analysis.status.value,
            "celery_task_id": analysis.celery_task_id,
            "queued_at": analysis.queued_at.isoformat() if analysis.queued_at else None,
            "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "failed_at": analysis.failed_at.isoformat() if analysis.failed_at else None,
            "refusal_reason_code": analysis.refusal_reason_code.value if analysis.refusal_reason_code else None,
            "refusal_reason_text": analysis.refusal_reason_text,
            "error_message": analysis.error_message,
            "review_record": review_record_info,
            "has_result": analysis.result_json is not None,
        }
        if analysis.result_json is not None:
            payload["result_json"] = analysis.result_json
        return payload
