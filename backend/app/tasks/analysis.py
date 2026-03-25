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

import logging
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
from app.models.analysis import Analysis, AnalysisStatus
from app.services.analysis_pipeline import execute_shipment_analysis_pipeline

logger = logging.getLogger(__name__)


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
            return await execute_shipment_analysis_pipeline(
                db,
                shipment_id=shipment_id,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                celery_task_id=celery_task_id,
                clarification_responses=clarification_responses,
                analysis_path="celery",
            )
            
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
