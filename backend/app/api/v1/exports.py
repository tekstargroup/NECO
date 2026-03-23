"""
Export API - Sprint 12

Endpoints for generating and downloading exports.
Exports are immutable and consume ReviewRecord snapshots only.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from datetime import timedelta
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.models.export import Export, ExportType, ExportStatus
from app.models.review_record import ReviewRecord
from app.models.shipment import Shipment
from app.services.export_service import ExportService
from app.services.s3_upload_service import get_s3_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Note: Export endpoints use two different prefixes:
# - Creation: /api/v1/reviews/{review_id}/exports/*
# - Status/Download: /api/v1/exports/*
router = APIRouter(tags=["exports"])


class ExportResponse(BaseModel):
    """Export response."""
    id: str
    review_id: str
    export_type: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    blocked_reason: Optional[str] = None
    blockers: Optional[list] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class ExportDownloadResponse(BaseModel):
    """Export download URL response."""
    download_url: str
    expires_in_seconds: int = 3600


@router.post("/{review_id}/exports/audit-pack", response_model=ExportResponse)
async def create_audit_pack(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Generate audit pack export for a review.
    
    Creates immutable export from ReviewRecord snapshot only.
    Blocks if review_status = REVIEW_REQUIRED or any regulatory outcome = CONDITIONAL.
    """
    export_service = ExportService(db)
    
    try:
        export = await export_service.generate_audit_pack(
            review_id=review_id,
            organization_id=current_org.id,
            created_by=current_user.id
        )
        
        # Emit telemetry
        # TODO: events.emit("export_attempted", {...})
        if export.status == ExportStatus.BLOCKED:
            # TODO: events.emit("export_blocked", {"export_id": str(export.id), "reason": export.blocked_reason})
            logger.info(f"Export blocked: {export.id} - {export.blocked_reason}")
        elif export.status == ExportStatus.COMPLETED:
            # TODO: events.emit("export_completed", {"export_id": str(export.id)})
            logger.info(f"Export completed: {export.id}")
        
        return ExportResponse(
            id=str(export.id),
            review_id=str(export.review_id),
            export_type=export.export_type.value,
            status=export.status.value,
            created_at=export.created_at.isoformat(),
            completed_at=export.completed_at.isoformat() if export.completed_at else None,
            blocked_reason=export.blocked_reason,
            blockers=export.blockers,
            error_message=export.error_message
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export generation failed"
        )


@router.post("/{review_id}/exports/broker-prep", response_model=ExportResponse)
async def create_broker_prep(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Generate broker filing-prep bundle for a review.
    
    Creates immutable export from ReviewRecord snapshot only.
    Returns BLOCKED status if review_status = REVIEW_REQUIRED or any regulatory outcome = CONDITIONAL.
    """
    export_service = ExportService(db)
    
    try:
        export = await export_service.generate_broker_prep(
            review_id=review_id,
            organization_id=current_org.id,
            created_by=current_user.id
        )
        
        # Emit telemetry
        # TODO: events.emit("export_attempted", {...})
        if export.status == ExportStatus.BLOCKED:
            # TODO: events.emit("export_blocked", {"export_id": str(export.id), "reason": export.blocked_reason})
            logger.info(f"Export blocked: {export.id} - {export.blocked_reason}")
        elif export.status == ExportStatus.COMPLETED:
            # TODO: events.emit("export_completed", {"export_id": str(export.id)})
            logger.info(f"Export completed: {export.id}")
        
        return ExportResponse(
            id=str(export.id),
            review_id=str(export.review_id),
            export_type=export.export_type.value,
            status=export.status.value,
            created_at=export.created_at.isoformat(),
            completed_at=export.completed_at.isoformat() if export.completed_at else None,
            blocked_reason=export.blocked_reason,
            blockers=export.blockers,
            error_message=export.error_message
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export generation failed"
        )


@router.get("/{export_id}/status", response_model=ExportResponse)
async def get_export_status(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Get export status.
    
    Org-scoped via review -> shipment -> organization_id
    """
    # Load export with org-scoping
    result = await db.execute(
        select(Export, ReviewRecord, Shipment)
        .join(ReviewRecord, Export.review_id == ReviewRecord.id)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                Export.id == export_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or access denied"
        )
    
    export = row[0]
    
    return ExportResponse(
        id=str(export.id),
        review_id=str(export.review_id),
        export_type=export.export_type.value,
        status=export.status.value,
        created_at=export.created_at.isoformat(),
        completed_at=export.completed_at.isoformat() if export.completed_at else None,
        blocked_reason=export.blocked_reason,
        blockers=export.blockers,
        error_message=export.error_message
    )


def _local_export_path(s3_key: str) -> Path:
    """Path to export file when stored on LOCAL_FS."""
    return Path("backend/data/local_exports") / s3_key


@router.get("/{export_id}/download", response_class=FileResponse)
async def download_export_file(
    export_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Stream export file for download (used when S3 is not configured, LOCAL_FS).
    Org-scoped via review -> shipment -> organization_id.
    """
    result = await db.execute(
        select(Export, ReviewRecord, Shipment)
        .join(ReviewRecord, Export.review_id == ReviewRecord.id)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                Export.id == export_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or access denied"
        )
    export = row[0]
    if export.status != ExportStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export not ready for download. Status: {export.status.value}"
        )
    if export.s3_bucket != "LOCAL_FS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use download-url for S3-backed exports"
        )
    path = _local_export_path(export.s3_key)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found on disk"
        )
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/zip"
    )


@router.get("/{export_id}/download-url", response_model=ExportDownloadResponse)
async def get_export_download_url(
    export_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Get presigned S3 download URL for export.
    
    Org-scoped via review -> shipment -> organization_id
    """
    # Load export with org-scoping
    result = await db.execute(
        select(Export, ReviewRecord, Shipment)
        .join(ReviewRecord, Export.review_id == ReviewRecord.id)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                Export.id == export_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or access denied"
        )
    export = row[0]
    if export.status != ExportStatus.COMPLETED and export.status != ExportStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export not ready for download. Status: {export.status.value}"
        )
    
    # Local storage: return URL to our stream endpoint (same auth)
    if export.s3_bucket == "LOCAL_FS":
        base = str(request.base_url).rstrip("/")
        local_url = f"{base}/api/v1/exports/{export_id}/download"
        return ExportDownloadResponse(
            download_url=local_url,
            expires_in_seconds=3600
        )

    s3_client = get_s3_client()
    download_url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': export.s3_bucket,
            'Key': export.s3_key
        },
        ExpiresIn=3600
    )
    
    return ExportDownloadResponse(
        download_url=download_url,
        expires_in_seconds=3600
    )
