"""
Broker API Endpoints - Sprint 9

Read-only endpoints for broker filing prep.

Key principles:
- Read-only (no mutations)
- Explicit blockers
- Conservative defaults
- Human review required
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.services.filing_prep_service import FilingPrepService
from app.services.broker_export_service import BrokerExportService
from app.models.filing_prep_bundle import ExportBlockReason

router = APIRouter()


@router.get("/filing-prep")
async def get_filing_prep_bundle(
    declared_hts_code: str = Query(..., description="10-digit HTS code"),
    quantity: Optional[float] = Query(None, description="Product quantity"),
    unit_of_measure: Optional[str] = Query(None, description="Unit of measure"),
    customs_value: Optional[float] = Query(None, description="Customs value"),
    country_of_origin: Optional[str] = Query(None, description="Country of origin (context only)"),
    product_description: Optional[str] = Query(None, description="Product description (for PSC Radar)"),
    review_id: Optional[UUID] = Query(None, description="Review record ID (if already reviewed)"),
    block_on_unresolved_psc: bool = Query(True, description="Block export if unresolved PSC flags"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get filing prep bundle for broker handoff.
    
    Read-only. Returns canonical FilingPrepBundle with validation and blockers.
    """
    service = FilingPrepService(db)
    
    try:
        bundle = await service.create_filing_prep_bundle(
            declared_hts_code=declared_hts_code,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            customs_value=customs_value,
            country_of_origin=country_of_origin,
            product_description=product_description,
            review_id=review_id,
            block_on_unresolved_psc=block_on_unresolved_psc
        )
        
        return bundle.to_dict()
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/filing-prep/export")
async def export_filing_prep(
    declared_hts_code: str = Query(..., description="10-digit HTS code"),
    quantity: Optional[float] = Query(None),
    unit_of_measure: Optional[str] = Query(None),
    customs_value: Optional[float] = Query(None),
    country_of_origin: Optional[str] = Query(None),
    product_description: Optional[str] = Query(None),
    review_id: Optional[UUID] = Query(None),
    block_on_unresolved_psc: bool = Query(True),
    format: str = Query("json", description="Export format: json, csv, pdf"),
    db: AsyncSession = Depends(get_db)
):
    """
    Export filing prep bundle in specified format.
    
    Formats:
    - json: Canonical JSON format
    - csv: Broker-friendly CSV
    - pdf: Human-readable text summary
    
    Export will be blocked if validation fails.
    """
    service = FilingPrepService(db)
    export_service = BrokerExportService()
    
    try:
        bundle = await service.create_filing_prep_bundle(
            declared_hts_code=declared_hts_code,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            customs_value=customs_value,
            country_of_origin=country_of_origin,
            product_description=product_description,
            review_id=review_id,
            block_on_unresolved_psc=block_on_unresolved_psc
        )
        
        # Check if export is blocked
        if bundle.export_blocked:
            error_messages = []
            for reason in bundle.export_block_reasons:
                if reason == ExportBlockReason.REVIEW_REQUIRED:
                    error_messages.append("Export blocked: classification not reviewed")
                elif reason == ExportBlockReason.MISSING_QUANTITY:
                    error_messages.append("Export blocked: missing quantity")
                elif reason == ExportBlockReason.MISSING_VALUE:
                    error_messages.append("Export blocked: missing customs value")
                elif reason == ExportBlockReason.MISSING_DUTY_FIELDS:
                    error_messages.append("Export blocked: missing duty fields")
                elif reason == ExportBlockReason.UNRESOLVED_PSC_FLAGS:
                    error_messages.append("Export blocked: unresolved PSC risk")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "export_blocked": True,
                    "errors": error_messages,
                    "bundle": bundle.to_dict()
                }
            )
        
        # Export in requested format
        if format == "json":
            import json as json_module
            content = export_service.export_json(bundle)
            return JSONResponse(
                content=json_module.loads(content),
                headers={"Content-Disposition": f'attachment; filename="filing_prep_{declared_hts_code.replace(".", "_")}.json"'}
            )
        elif format == "csv":
            content = export_service.export_csv(bundle)
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="filing_prep_{declared_hts_code.replace(".", "_")}.csv"'}
            )
        elif format == "pdf":
            content = export_service.export_pdf_summary(bundle)
            return Response(
                content=content,
                media_type="text/plain",
                headers={"Content-Disposition": f'attachment; filename="filing_prep_{declared_hts_code.replace(".", "_")}.txt"'}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid format: {format}. Must be json, csv, or pdf"
            )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/filing-prep/view/{review_id}")
async def get_broker_view(
    review_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get read-only broker view for a review record.
    
    Broker can see:
    - Filing-prep bundle
    - Review trail
    - Audit replay snapshot
    
    Broker cannot:
    - Edit
    - Approve
    - Override
    
    This is consumption, not collaboration.
    """
    from sqlalchemy import select
    from app.models.review_record import ReviewRecord
    from app.services.review_service import ReviewService
    from app.services.audit_replay_service import AuditReplayService
    
    # Fetch review record
    review_service = ReviewService(db)
    review_record = await review_service.get_review_record(review_id)
    
    if not review_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review record {review_id} not found"
    )
    
    # Get review history
    history = await review_service.get_review_history(review_id)
    
    # Get audit replay
    audit_service = AuditReplayService(db)
    replay_result = await audit_service.verify_review_record(review_id)
    
    # Extract HTS code from snapshot
    snapshot = review_record.object_snapshot
    declared_hts = snapshot.get("inputs", {}).get("declared_hts_code") or snapshot.get("inputs", {}).get("hts_code")
    
    return {
        "review_id": str(review_id),
        "object_type": review_record.object_type.value,
        "status": review_record.status.value,
        "declared_hts_code": declared_hts,
        "snapshot": snapshot,
        "review_history": [r.to_dict() for r in history],
        "audit_replay": replay_result.to_dict(),
        "read_only": True,
        "note": "This is a read-only view. No edits, approvals, or overrides allowed."
    }
