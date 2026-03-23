"""
Enrichment API Endpoints - Sprint 10

Read-only endpoints for document enrichment.

Key principles:
- Document ingestion
- Field extraction
- Evidence tracking
- No inference or conclusions
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.field_extractor_service import FieldExtractorService
from app.services.enrichment_audit_service import EnrichmentAuditService
from app.models.enrichment_bundle import DocumentType

router = APIRouter()


@router.post("/documents/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    document_type: str = Query(..., description="Document type: COMMERCIAL_INVOICE, PACKING_LIST, TECHNICAL_SPEC"),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a document and create DocumentRecord.
    
    Returns document_id for use in extraction.
    """
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type: {document_type}. Must be COMMERCIAL_INVOICE, PACKING_LIST, or TECHNICAL_SPEC"
        )
    
    # Read file content
    file_content = await file.read()
    
    # Ingest document
    ingestion_service = DocumentIngestionService(db)
    doc_record = await ingestion_service.ingest_document(
        file_content=file_content,
        filename=file.filename or "unknown",
        document_type=doc_type
    )
    
    await db.commit()
    
    return {
        "document_id": doc_record.document_id,
        "document_hash": doc_record.document_hash,
        "document_type": doc_record.document_type,
        "page_count": doc_record.page_count
    }


@router.post("/documents/{document_id}/extract")
async def extract_fields(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Extract fields from a document.
    
    Returns EnrichmentBundle with extracted fields and evidence.
    """
    # Get document
    ingestion_service = DocumentIngestionService(db)
    doc_record = await ingestion_service.get_document(document_id)
    
    if not doc_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    # Extract fields
    extractor_service = FieldExtractorService()
    enrichment_bundle = await extractor_service.extract_from_document(doc_record)
    
    # Persist snapshot
    audit_service = EnrichmentAuditService(db)
    enrichment_id = await audit_service.persist_enrichment_snapshot(enrichment_bundle)
    
    return {
        "enrichment_id": enrichment_id,
        "enrichment_bundle": enrichment_bundle.to_dict()
    }


@router.get("/enrichment/{enrichment_id}")
async def get_enrichment(
    enrichment_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get enrichment snapshot by ID."""
    audit_service = EnrichmentAuditService(db)
    snapshot = await audit_service.get_enrichment_snapshot(enrichment_id)
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrichment snapshot {enrichment_id} not found"
        )
    
    return snapshot.to_dict()


@router.get("/enrichment/review/{review_id}")
async def get_enrichments_for_review(
    review_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all enrichment snapshots linked to a review."""
    audit_service = EnrichmentAuditService(db)
    snapshots = await audit_service.get_enrichments_for_review(review_id)
    
    return {
        "review_id": review_id,
        "enrichments": [s.to_dict() for s in snapshots]
    }
