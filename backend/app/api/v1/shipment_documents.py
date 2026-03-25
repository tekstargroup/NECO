"""
Shipment Documents API - Sprint 12

Two-step S3 upload: presign and confirm.
New shipment workflow uses this ONLY (not legacy /api/v1/documents).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.services.s3_upload_service import S3UploadService
from app.repositories.org_scoped_repository import OrgScopedRepository

router = APIRouter()


# Request/Response Models
# Allowed content types (must match s3_upload_service.ALLOWED_CONTENT_TYPES)
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}


class PresignUploadRequest(BaseModel):
    """Presign upload request"""
    shipment_id: UUID
    document_type: ShipmentDocumentType
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., description="PDF, Word, Excel, or CSV")
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """Content type must be one of the allowed types"""
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                "Only PDF, Word (.docx), Excel (.xlsx, .xls), and CSV files are allowed"
            )
        return v
    
    @validator("filename")
    def validate_filename(cls, v):
        """Filename should end in allowed extension"""
        ext = v.lower().rsplit(".", 1)[-1] if "." in v else ""
        if ext not in ("pdf", "docx", "xlsx", "xls", "csv"):
            pass  # Warning only
        return v


class PresignUploadResponse(BaseModel):
    """Presign upload response"""
    upload_url: str
    s3_key: str
    required_headers: dict = Field(default_factory=dict)
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    """Confirm upload request"""
    shipment_id: UUID
    document_type: ShipmentDocumentType
    s3_key: str = Field(..., min_length=1, max_length=500)
    sha256_hash: str = Field(..., min_length=64, max_length=64, description="SHA256 hash (64 hex chars)")
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., description="PDF, Word, Excel, or CSV")
    file_size: str = Field(..., description="File size in bytes (string for flexibility)")
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """Content type must be one of the allowed types"""
        if v not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                "Only PDF, Word (.docx), Excel (.xlsx, .xls), and CSV files are allowed"
            )
        return v
    
    @validator("sha256_hash")
    def validate_hash(cls, v):
        """SHA256 hash must be 64 hex characters"""
        if len(v) != 64 or not all(c in '0123456789abcdefABCDEF' for c in v):
            raise ValueError("sha256_hash must be 64 hexadecimal characters")
        return v.lower()  # Normalize to lowercase


class ConfirmUploadResponse(BaseModel):
    """Confirm upload response"""
    document_id: str
    shipment_id: str
    is_new: bool
    eligibility: dict
    warnings: List[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    """Document response"""
    id: str
    shipment_id: str
    document_type: str
    filename: str
    file_size: Optional[str]
    uploaded_at: str
    retention_expires_at: str
    processing_status: Optional[str] = None
    extraction_method: Optional[str] = None
    ocr_used: Optional[bool] = None
    page_count: Optional[int] = None
    char_count: Optional[int] = None
    table_detected: Optional[bool] = None
    extraction_status: Optional[str] = None
    usable_for_analysis: Optional[bool] = None
    data_sheet_user_confirmed: bool = False


def _shipment_document_to_response(doc: ShipmentDocument) -> dict:
    text = doc.extracted_text or ""
    char_count = doc.char_count
    if char_count is None and doc.extracted_text is not None:
        char_count = len(text)
    return {
        "id": str(doc.id),
        "shipment_id": str(doc.shipment_id),
        "document_type": doc.document_type.value,
        "filename": doc.filename,
        "file_size": doc.file_size,
        "uploaded_at": doc.uploaded_at.isoformat(),
        "retention_expires_at": doc.retention_expires_at.isoformat(),
        "processing_status": doc.processing_status,
        "extraction_method": doc.extraction_method,
        "ocr_used": doc.ocr_used,
        "page_count": doc.page_count,
        "char_count": char_count,
        "table_detected": doc.table_detected,
        "extraction_status": doc.extraction_status,
        "usable_for_analysis": doc.usable_for_analysis,
        "data_sheet_user_confirmed": bool(getattr(doc, "data_sheet_user_confirmed", False)),
    }


class DataSheetConfirmRequest(BaseModel):
    """User attestation that a data sheet is acceptable as evidence (Sprint B)."""
    confirmed: bool = True


class UpdateDocumentTypeRequest(BaseModel):
    """Update document type (metadata only; blob unchanged)."""
    document_type: ShipmentDocumentType


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document_type(
    document_id: UUID,
    request: UpdateDocumentTypeRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Update document type for an already-uploaded document.
    Org-scoped (404 on org mismatch). Only metadata is updated; the file blob is unchanged.
    """
    result = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == document_id,
                ShipmentDocument.organization_id == current_org.id
            )
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )
    doc.document_type = request.document_type
    await db.commit()
    await db.refresh(doc)
    return _shipment_document_to_response(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an uploaded document. Org-scoped (404 on org mismatch).
    Existing analysis for this shipment may be invalid; user should re-run analysis after re-uploading if needed.
    """
    result = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == document_id,
                ShipmentDocument.organization_id == current_org.id
            )
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )
    await db.delete(doc)
    await db.commit()


@router.post("/presign", response_model=PresignUploadResponse)
async def presign_upload(
    request: PresignUploadRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate presigned PUT URL for S3 upload.
    
    Must be org-scoped. Never allow presigning for shipment outside user's org.
    Returns 404 on org mismatch.
    
    Enforces:
    - content_type must be application/pdf
    - filename should end in .pdf (nice to have)
    """
    # Verify shipment exists and belongs to org (404 on mismatch)
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(request.shipment_id, current_org.id)
    
    # Generate presigned URL
    s3_service = S3UploadService(db)
    result = await s3_service.presign_upload(
        shipment_id=request.shipment_id,
        organization_id=current_org.id,
        document_type=request.document_type,
        filename=request.filename,
        content_type=request.content_type,
        local_upload_base_url=str(http_request.base_url).rstrip("/")
    )
    
    # TODO: Emit event - document_presigned
    # events.emit("document_presigned", {...})
    
    return result


@router.put("/mock-upload/{upload_id}", status_code=status.HTTP_200_OK)
async def mock_upload(
    upload_id: str,
    http_request: Request,
):
    """
    Dev-only local upload fallback when S3 is not configured.
    Accepts bytes and returns 200 to emulate a successful object upload.
    If X-S3-Key header is present, stores at path derived from s3_key for later retrieval.
    """
    import logging
    from pathlib import Path
    from app.core.config import settings

    logger = logging.getLogger(__name__)
    body = await http_request.body()
    upload_dir = settings.MOCK_UPLOADS_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    s3_key = http_request.headers.get("X-S3-Key")
    if s3_key:
        # Store by s3_key so analysis can find the file (path: neco/dev/org_x/ship_x/docs/TYPE/uuid.ext)
        safe_name = s3_key.replace("/", "_")
        file_path = upload_dir / safe_name
    else:
        file_path = upload_dir / f"{upload_id}.pdf"

    with open(file_path, "wb") as f:
        f.write(body)

    logger.info("Mock upload saved: path=%s bytes=%s s3_key=%s", file_path, len(body), s3_key or "(none)")
    return {"uploaded": True, "upload_id": upload_id, "bytes": len(body)}


@router.post("/confirm", response_model=ConfirmUploadResponse, status_code=status.HTTP_201_CREATED)
async def confirm_upload(
    request: ConfirmUploadRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm S3 upload and create ShipmentDocument record.
    
    Must be org-scoped. Handles dedupe: if duplicate (shipment_id, sha256_hash), returns existing document.
    
    After confirm:
    - Updates shipment.status to READY if eligible, else DRAFT
    - Returns eligibility and missing requirements
    - Computes eligibility for UI readiness indicator
    """
    # Verify shipment exists and belongs to org (404 on mismatch)
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(request.shipment_id, current_org.id)
    
    # Confirm upload
    s3_service = S3UploadService(db)
    result = await s3_service.confirm_upload(
        shipment_id=request.shipment_id,
        organization_id=current_org.id,
        document_type=request.document_type,
        s3_key=request.s3_key,
        sha256_hash=request.sha256_hash,
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
        uploaded_by=current_user.id
    )
    
    return result


@router.get("/shipments/{shipment_id}/documents", response_model=List[DocumentResponse])
async def list_shipment_documents(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    List documents for a shipment.
    
    Org-scoped (404 on org mismatch).
    """
    # Verify shipment exists and belongs to org
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    
    # Get documents
    result = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.shipment_id == shipment_id,
                ShipmentDocument.organization_id == current_org.id
            )
        ).order_by(ShipmentDocument.uploaded_at.desc())
    )
    documents = result.scalars().all()
    
    return [_shipment_document_to_response(doc) for doc in documents]


@router.patch("/{document_id}/data-sheet-confirmation", response_model=DocumentResponse)
async def patch_data_sheet_confirmation(
    document_id: UUID,
    request: DataSheetConfirmRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Record explicit user confirmation for a data sheet (in addition to extraction truth)."""
    result = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == document_id,
                ShipmentDocument.organization_id == current_org.id,
            )
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied")
    if doc.document_type != ShipmentDocumentType.DATA_SHEET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation is only applicable to DATA_SHEET documents",
        )
    doc.data_sheet_user_confirmed = bool(request.confirmed)
    await db.commit()
    await db.refresh(doc)
    return _shipment_document_to_response(doc)


@router.get("/{document_id}/table-preview")
async def get_document_table_preview(
    document_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Return table preview (columns + rows) for Excel/CSV documents.
    Used so the UI can show "confirm which columns are line items" (MailChimp-style) after upload.
    Org-scoped.
    """
    from pathlib import Path
    from app.core.config import settings
    from app.engines.ingestion.excel_parser import ExcelParser

    repo = OrgScopedRepository(db, ShipmentDocument)
    doc = await repo.get_by_id(document_id, current_org.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    ext = (Path(doc.filename).suffix or "").lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(status_code=400, detail="Table preview is only available for Excel or CSV files")

    local_path = None
    if not settings.S3_BUCKET_NAME:
        safe_name = doc.s3_key.replace("/", "_")
        local_path = settings.MOCK_UPLOADS_DIR / safe_name
        if not local_path.exists():
            for candidate in (
                Path("backend/data/mock_uploads") / safe_name,
                Path.cwd() / "data" / "mock_uploads" / safe_name,
            ):
                if candidate.exists():
                    local_path = candidate
                    break
        if not local_path.exists() and doc.filename and settings.MOCK_UPLOADS_DIR.exists():
            for f in settings.MOCK_UPLOADS_DIR.iterdir():
                if f.is_file() and f.name == doc.filename:
                    local_path = f
                    break
    if not local_path or not local_path.exists():
        raise HTTPException(status_code=404, detail="File not found for preview (local storage)")

    parser = ExcelParser()
    result = parser.parse_file(local_path)
    if not result.get("success") or not result.get("sheets"):
        raise HTTPException(status_code=422, detail=result.get("error") or "Could not parse file")
    sheet = result["sheets"][0]
    rows = (sheet.get("data") or [])[:100]
    columns = sheet.get("columns") or (list(rows[0].keys()) if rows else [])
    return {"columns": columns, "rows": rows, "filename": doc.filename}


@router.get("/{document_id}/download-url")
async def get_download_url(
    document_id: UUID,
    expires_in: int = Query(3600, ge=60, le=86400, description="URL expiration in seconds (60-86400)"),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate presigned GET URL for document download/viewing.
    
    Org-scoped (404 on org mismatch).
    Useful for PDF viewer in UI.
    """
    s3_service = S3UploadService(db)
    download_url = await s3_service.presign_download(
        document_id=document_id,
        organization_id=current_org.id,
        expires_in=expires_in
    )
    
    return {
        "download_url": download_url,
        "expires_in": expires_in
    }


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Re-extract text and structured data for a single document."""
    import asyncio
    from pathlib import Path
    from app.core.config import settings
    from app.engines.ingestion.document_processor import DocumentProcessor
    from app.services.shipment_analysis_service import (
        apply_ingestion_metadata_to_shipment_document,
        enrich_structured_data_with_extraction,
    )

    result = await db.execute(
        select(ShipmentDocument).where(
            and_(ShipmentDocument.id == document_id, ShipmentDocument.organization_id == current_org.id)
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    local_path = None
    if not settings.S3_BUCKET_NAME:
        safe_name = doc.s3_key.replace("/", "_")
        local_path = settings.MOCK_UPLOADS_DIR / safe_name
        for candidate in (
            Path("backend/data/mock_uploads") / safe_name,
            Path.cwd() / "data" / "mock_uploads" / safe_name,
        ):
            if not local_path.exists() and candidate.exists():
                local_path = candidate
        if local_path and not local_path.exists() and doc.filename and settings.MOCK_UPLOADS_DIR.exists():
            for f in settings.MOCK_UPLOADS_DIR.iterdir():
                if f.is_file() and f.name == doc.filename:
                    local_path = f
                    break
    if not local_path or not local_path.exists():
        raise HTTPException(status_code=404, detail="File not found for reprocessing (local storage)")

    processor = DocumentProcessor()
    hint = doc.document_type.value if doc.document_type else None
    try:
        process_result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: processor.process_document(local_path, document_type_hint=hint)
            ),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Reprocessing timed out")

    if not process_result.get("success"):
        raise HTTPException(status_code=422, detail=process_result.get("error", "Extraction failed"))

    doc.extracted_text = process_result.get("extracted_text")
    doc.structured_data = enrich_structured_data_with_extraction(
        process_result.get("structured_data"),
        process_result.get("extracted_text") or "",
    )
    apply_ingestion_metadata_to_shipment_document(doc, process_result)
    doc.processing_status = "COMPLETED"
    await db.commit()
    await db.refresh(doc)
    return _shipment_document_to_response(doc)
