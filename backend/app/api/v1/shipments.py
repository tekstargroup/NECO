"""
Shipments API - Sprint 12

CRUD minimal: create, list, get detail
Add items and references
No delete endpoints
Org-scoped with entitlement checking
"""

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import DataError
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
import re

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.user import User
from app.models.organization import Organization
from app.models.shipment import Shipment, ShipmentStatus, ShipmentReference, ShipmentItem
from app.models.shipment_document import ShipmentDocument
from app.models.shipment_item_document import ShipmentItemDocument, ItemDocumentMappingStatus
from app.models.shipment_item_line_provenance import ShipmentItemLineProvenance
from app.services.shipment_analysis_service import ShipmentAnalysisService
from app.models.analysis import Analysis
from app.models.review_record import ReviewRecord
from app.repositories.org_scoped_repository import OrgScopedRepository
from app.services.entitlement_service import EntitlementService
from app.services.shipment_eligibility_service import ShipmentEligibilityService
from app.core.config import settings

router = APIRouter()


def _normalize_declared_hts(raw_value: Optional[str]) -> Optional[str]:
    """Normalize declared HTS to compact digits (max 10)."""
    if raw_value is None:
        return None
    compact = str(raw_value).replace(".", "").strip()
    if not compact:
        return None
    return compact


# Request/Response Models

class ShipmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    references: Optional[List[dict]] = Field(default_factory=list)
    items: Optional[List[dict]] = Field(default_factory=list)
    
    @validator("references")
    def validate_references(cls, v):
        for ref in v:
            if not isinstance(ref, dict):
                raise ValueError("Each reference must be a dict")
            if "key" not in ref or "value" not in ref:
                raise ValueError("Each reference must have 'key' and 'value'")
            if not ref["key"] or not ref["value"]:
                raise ValueError("Reference key and value cannot be empty")
        return v
    
    @validator("items")
    def validate_items(cls, v):
        for item in v:
            if not isinstance(item, dict):
                raise ValueError("Each item must be a dict")
            # Validate numeric fields
            if "value" in item:
                try:
                    float(item["value"])
                    if float(item["value"]) < 0:
                        raise ValueError("Item value cannot be negative")
                except (ValueError, TypeError):
                    raise ValueError("Item value must be a non-negative number")
            # Validate COO (2-letter ISO if present)
            if "country_of_origin" in item and item["country_of_origin"]:
                coo = item["country_of_origin"]
                if not isinstance(coo, str) or len(coo) != 2 or not coo.isalpha():
                    raise ValueError("Country of origin must be a 2-letter ISO code")
            # Validate HTS (digits and dots only if present)
            if "declared_hts_code" in item and item["declared_hts_code"]:
                hts = item["declared_hts_code"]
                if not isinstance(hts, str) or not re.match(r"^[\d.]+$", hts):
                    raise ValueError("HTS code must contain only digits and dots")
                compact = _normalize_declared_hts(hts)
                if compact and len(compact) > 10:
                    raise ValueError("HTS code cannot exceed 10 digits (excluding dots)")
        return v


class ShipmentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class ShipmentResponse(BaseModel):
    shipment_id: str
    organization_id: str
    created_by: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    eligibility: dict
    
    class Config:
        from_attributes = True


class ShipmentDetailResponse(BaseModel):
    shipment_id: str
    organization_id: str
    created_by: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    references: List[dict]
    items: List[dict]
    documents: List[dict]
    latest_analysis_status: Optional[str]
    latest_review_status: Optional[str]
    eligibility: dict


# Endpoints

@router.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_shipment(
    shipment_data: ShipmentCreateRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new shipment.
    
    Org-scoped, checks entitlement availability (does not increment at creation).
    Increment happens at analysis start.
    """
    # Check entitlement availability (but do not increment)
    entitlement_service = EntitlementService(db)
    has_entitlement, entitlement = await entitlement_service.check_entitlement_available(current_user.id)
    
    if not has_entitlement:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "ENTITLEMENT_EXCEEDED",
                "message": f"Monthly limit of {entitlement.shipments_limit} shipments exceeded",
                "shipments_used": entitlement.shipments_used,
                "shipments_limit": entitlement.shipments_limit,
                "period_start": entitlement.period_start.isoformat()
            }
        )
    
    # Create shipment
    repo = OrgScopedRepository(db, Shipment)
    shipment = Shipment(
        organization_id=current_org.id,
        created_by=current_user.id,
        name=shipment_data.name,
        status=ShipmentStatus.DRAFT
    )
    shipment = await repo.create(shipment)
    
    # Add references if provided
    if shipment_data.references:
        for ref_data in shipment_data.references:
            ref = ShipmentReference(
                shipment_id=shipment.id,
                reference_type=ref_data["key"],
                reference_value=ref_data["value"]
            )
            db.add(ref)
    
    # Add items if provided
    if shipment_data.items:
        for item_data in shipment_data.items:
            normalized_hts = _normalize_declared_hts(item_data.get("declared_hts_code"))
            item = ShipmentItem(
                shipment_id=shipment.id,
                label=item_data.get("label", ""),
                declared_hts=normalized_hts,
                value=str(float(item_data["value"])) if "value" in item_data and item_data.get("value") is not None else None,
                currency=item_data.get("currency", "USD"),
                quantity=str(float(item_data["quantity"])) if "quantity" in item_data and item_data.get("quantity") is not None else None,
                unit_of_measure=item_data.get("unit_of_measure"),
                country_of_origin=item_data.get("country_of_origin")
            )
            db.add(item)

    try:
        await db.commit()
    except DataError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid shipment item payload (field length/format constraint violated)"
        )
    await db.refresh(shipment, ["references", "items"])
    
    # Compute eligibility
    eligibility_service = ShipmentEligibilityService(db)
    eligibility = await eligibility_service.compute_eligibility(shipment.id)
    
    return {
        "shipment_id": str(shipment.id),
        "organization_id": str(shipment.organization_id),
        "created_by": str(shipment.created_by),
        "name": shipment.name,
        "status": shipment.status.value,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "eligibility": eligibility
    }


@router.get("/entitlement")
async def get_entitlement(
    current_user: User = Depends(get_current_user_sprint12),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's entitlement usage for the month.
    Used for display: "X of 15 shipments used"
    """
    entitlement_service = EntitlementService(db)
    _, entitlement = await entitlement_service.check_entitlement_available(current_user.id)
    return {
        "shipments_used": entitlement.shipments_used,
        "shipments_limit": entitlement.shipments_limit,
    }


@router.get("", response_model=List[ShipmentResponse])
async def list_shipments(
    status_filter: Optional[ShipmentStatus] = Query(None, alias="status"),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    List shipments for organization.
    
    Filters: status, created_at range (optional)
    Pagination: limit, offset
    """
    repo = OrgScopedRepository(db, Shipment)
    
    # Build query
    query = select(Shipment).where(Shipment.organization_id == current_org.id)
    
    if status_filter:
        query = query.where(Shipment.status == status_filter)
    
    if created_after:
        query = query.where(Shipment.created_at >= created_after)
    
    if created_before:
        query = query.where(Shipment.created_at <= created_before)
    
    query = query.order_by(desc(Shipment.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    shipments = result.scalars().all()
    
    # Compute eligibility for each
    eligibility_service = ShipmentEligibilityService(db)
    responses = []
    for shipment in shipments:
        eligibility = await eligibility_service.compute_eligibility(shipment.id)
        responses.append({
            "shipment_id": str(shipment.id),
            "organization_id": str(shipment.organization_id),
            "created_by": str(shipment.created_by),
            "name": shipment.name,
            "status": shipment.status.value,
            "created_at": shipment.created_at,
            "updated_at": shipment.updated_at,
            "eligibility": eligibility
        })
    
    return responses


@router.get("/{shipment_id}", response_model=ShipmentDetailResponse)
async def get_shipment(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Get shipment detail.
    
    Includes items, references, documents, latest analysis status, latest review status.
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    
    # Load relationships
    await db.refresh(shipment, ["references", "items", "documents", "analyses"])
    
    # Get latest analysis status
    latest_analysis_status = None
    if shipment.analyses:
        latest_analysis = max(shipment.analyses, key=lambda a: a.created_at)
        latest_analysis_status = latest_analysis.status.value
    
    # Get latest review status (if linked)
    latest_review_status = None
    if shipment.analyses:
        for analysis in sorted(shipment.analyses, key=lambda a: a.created_at, reverse=True):
            if analysis.review_record_id:
                result = await db.execute(
                    select(ReviewRecord).where(ReviewRecord.id == analysis.review_record_id)
                )
                review_record = result.scalar_one_or_none()
                if review_record:
                    latest_review_status = review_record.status.value
                    break
    
    # Format references
    references = [{"key": ref.reference_type, "value": ref.reference_value} for ref in shipment.references]
    
    # Format items
    items = []
    for item in shipment.items:
        items.append({
            "id": str(item.id),
            "label": item.label,
            "declared_hts_code": item.declared_hts,
            "value": float(item.value) if item.value is not None else None,
            "currency": item.currency,
            "quantity": float(item.quantity) if item.quantity is not None else None,
            "unit_of_measure": item.unit_of_measure,
            "country_of_origin": item.country_of_origin
        })
    
    # Format documents
    documents = []
    for doc in shipment.documents:
        documents.append({
            "id": str(doc.id),
            "type": doc.document_type.value,
            "filename": doc.filename,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "retention_expires_at": doc.retention_expires_at.isoformat() if doc.retention_expires_at else None
        })
    
    # Compute eligibility
    eligibility_service = ShipmentEligibilityService(db)
    eligibility = await eligibility_service.compute_eligibility(shipment.id)
    
    return {
        "shipment_id": str(shipment.id),
        "organization_id": str(shipment.organization_id),
        "created_by": str(shipment.created_by),
        "name": shipment.name,
        "status": shipment.status.value,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "references": references,
        "items": items,
        "documents": documents,
        "latest_analysis_status": latest_analysis_status,
        "latest_review_status": latest_review_status,
        "eligibility": eligibility
    }


@router.delete("/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a shipment. Only allowed when shipment has no documents and no analyses.
    Returns 409 if shipment has documents or analyses (cannot delete).
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)

    # Check for documents (RESTRICT FK - cannot delete shipment with documents)
    docs_result = await db.execute(
        select(ShipmentDocument).where(ShipmentDocument.shipment_id == shipment_id)
    )
    docs = docs_result.scalars().all()
    if docs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete: shipment has {len(docs)} document(s). Remove documents first."
        )

    # Check for analyses (RESTRICT FK - cannot delete shipment with analyses)
    analyses_result = await db.execute(
        select(Analysis).where(Analysis.shipment_id == shipment_id)
    )
    analyses = analyses_result.scalars().all()
    if analyses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: shipment has analysis history. Only draft shipments with no analyses can be deleted."
        )

    await db.delete(shipment)
    await db.commit()


class LineItemFromSelectionRow(BaseModel):
    """One row from user selection (e.g. from table_preview)."""
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None
    hts_code: Optional[str] = None
    country_of_origin: Optional[str] = None


class LineItemsFromSelectionRequest(BaseModel):
    """Request to create shipment line items from user-selected rows (when auto-extraction found none)."""
    items: List[LineItemFromSelectionRow] = Field(..., min_length=1)
    replace_items: bool = Field(False, description="If true, delete existing items first and replace with new selection")
    source_shipment_document_id: Optional[UUID] = Field(
        None,
        description="PATCH B: When set, provenance rows link each new line to this document's table row index.",
    )


@router.post("/{shipment_id}/line-items-from-selection", status_code=status.HTTP_201_CREATED)
async def create_line_items_from_selection(
    shipment_id: UUID,
    body: LineItemsFromSelectionRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Create shipment line items from user-selected rows when analysis found no line items.
    Only allowed when the shipment currently has no items, unless replace_items=true.
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])
    if shipment.items and not body.replace_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment already has line items. Use replace_items=true to replace them."
        )
    if shipment.items and body.replace_items:
        for item in list(shipment.items):
            await db.delete(item)
        await db.flush()
    created_items: List[ShipmentItem] = []
    for i, row in enumerate(body.items):
        label = (row.description or "").strip() or f"Line {i + 1}"
        if not label or len(label) > 255:
            label = f"Line {i + 1}"
        total_val = row.total
        if total_val is None and row.unit_price is not None and row.quantity is not None:
            total_val = row.unit_price * row.quantity
        val_str = str(total_val) if total_val is not None else None
        qty_str = str(row.quantity) if row.quantity is not None else None
        raw_hts = str(row.hts_code).strip() if row.hts_code else None
        clean_hts = re.sub(r"[^0-9]", "", raw_hts)[:10] if raw_hts else None
        coo = (str(row.country_of_origin or "").strip().upper())[:2] or None
        item = ShipmentItem(
            shipment_id=shipment.id,
            label=label[:255],
            declared_hts=clean_hts,
            value=val_str[:50] if val_str else None,
            quantity=qty_str[:50] if qty_str else None,
            unit_of_measure=None,
            country_of_origin=coo,
        )
        db.add(item)
        created_items.append(item)
    await db.flush()
    if (
        getattr(settings, "PROVENANCE_ON_SELECTION_LINE_ITEMS", True)
        and body.source_shipment_document_id
        and created_items
    ):
        from app.services.shipment_item_provenance_service import ensure_provenance_user_selection_from_table

        await ensure_provenance_user_selection_from_table(
            db, shipment, created_items, body.source_shipment_document_id
        )
    await db.commit()
    return {"created": len(body.items), "message": "Line items added. Re-run analysis to use them."}


class SupplementalEvidenceRequest(BaseModel):
    """Request to add supplemental evidence for a line item (Amazon URL or existing document)."""
    type: str = Field(..., description="'amazon_url' or 'document'")
    amazon_url: Optional[str] = Field(None, description="Amazon product URL (required when type=amazon_url)")
    document_id: Optional[UUID] = Field(None, description="Shipment document ID (required when type=document)")


class ShipmentItemUpdateRequest(BaseModel):
    """Patch shipment item fields used for pre-compliance clarifications."""
    country_of_origin: Optional[str] = Field(
        None,
        description="ISO 3166-1 alpha-2 country code (e.g. US, CN, MX). Use null/empty to clear.",
    )

    @validator("country_of_origin")
    def validate_country_of_origin(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if len(s) != 2 or not s.isalpha():
            raise ValueError("country_of_origin must be a 2-letter ISO code")
        return s.upper()


@router.patch("/{shipment_id}/items/{item_id}", status_code=status.HTTP_200_OK)
async def update_shipment_item(
    shipment_id: UUID,
    item_id: UUID,
    body: ShipmentItemUpdateRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Update shipment item clarifications (MVP: country_of_origin).
    Used by pre-compliance flow to strengthen likely HS code determination.
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])

    item = next((i for i in shipment.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    item.country_of_origin = body.country_of_origin
    await db.commit()
    await db.refresh(item)
    return {
        "item_id": str(item.id),
        "country_of_origin": item.country_of_origin,
        "message": "Line item updated. Re-run analysis to refresh likely HS code confidence."
    }


@router.post("/{shipment_id}/items/{item_id}/supplemental-evidence", status_code=status.HTTP_200_OK)
async def add_supplemental_evidence(
    shipment_id: UUID,
    item_id: UUID,
    body: SupplementalEvidenceRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Add supplemental evidence to a line item to improve HTS classification.
    Supports: Amazon product URL (scraped) or existing shipment document (PDF data sheet).
    Re-run analysis after adding to use the evidence.
    """
    from app.services.amazon_scraper_service import scrape_amazon_product, is_valid_amazon_url

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])

    item = next((i for i in shipment.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    if body.type == "amazon_url":
        if not body.amazon_url or not body.amazon_url.strip():
            raise HTTPException(status_code=400, detail="amazon_url is required when type=amazon_url")
        if not is_valid_amazon_url(body.amazon_url):
            raise HTTPException(status_code=400, detail="Invalid Amazon URL. Use a product page like https://www.amazon.com/dp/...")

        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, scrape_amazon_product, body.amazon_url)
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        if not result.get("full_text"):
            raise HTTPException(status_code=422, detail="Could not extract product information from this page.")

        item.supplemental_evidence_text = result["full_text"][:50000]  # Cap at 50k chars
        item.supplemental_evidence_source = "amazon_url"

    elif body.type == "document":
        if not body.document_id:
            raise HTTPException(status_code=400, detail="document_id is required when type=document")

        doc_result = await db.execute(
            select(ShipmentDocument).where(
                and_(
                    ShipmentDocument.id == body.document_id,
                    ShipmentDocument.shipment_id == shipment_id,
                    ShipmentDocument.organization_id == current_org.id
                )
            )
        )
        doc = doc_result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found or does not belong to this shipment")

        text = doc.extracted_text if doc.extracted_text else ""
        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="Document has no extracted text. Processing may not have completed yet.")

        item.supplemental_evidence_text = text[:50000]
        item.supplemental_evidence_source = "pdf"

    else:
        raise HTTPException(status_code=400, detail="type must be 'amazon_url' or 'document'")

    await db.commit()
    await db.refresh(item)
    return {
        "item_id": str(item.id),
        "supplemental_evidence_source": item.supplemental_evidence_source,
        "message": "Supplemental evidence added. Re-run analysis to use it for classification."
    }


@router.post("/{shipment_id}/items/{item_id}/supplemental-evidence/upload", status_code=status.HTTP_200_OK)
async def upload_supplemental_evidence_pdf(
    shipment_id: UUID,
    item_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a PDF data sheet as supplemental evidence for a line item.
    Extracts text and stores for classification. Re-run analysis after adding.
    """
    import tempfile
    from pathlib import Path
    import pdfplumber

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])

    item = next((i for i in shipment.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    def _extract_pdf_text(content_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content_bytes)
            tmp_path = Path(tmp.name)
        try:
            with pdfplumber.open(tmp_path) as pdf:
                parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text and text.strip():
                        parts.append(text.strip())
                return "\n\n".join(parts) if parts else ""
        finally:
            tmp_path.unlink(missing_ok=True)

    try:
        import asyncio
        extracted = await asyncio.get_event_loop().run_in_executor(None, _extract_pdf_text, content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract text from PDF: {str(e)[:200]}")

    if not extracted or not extracted.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from this PDF")

    item.supplemental_evidence_text = extracted[:50000]
    item.supplemental_evidence_source = "pdf"
    await db.commit()
    await db.refresh(item)
    return {
        "item_id": str(item.id),
        "supplemental_evidence_source": item.supplemental_evidence_source,
        "message": "Supplemental evidence added. Re-run analysis to use it for classification."
    }


@router.delete("/{shipment_id}/items/{item_id}/supplemental-evidence", status_code=status.HTTP_200_OK)
async def clear_supplemental_evidence(
    shipment_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """Clear supplemental evidence for a line item (mark as N/A)."""
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])

    item = next((i for i in shipment.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    item.supplemental_evidence_text = None
    item.supplemental_evidence_source = None
    await db.commit()
    return {"item_id": str(item.id), "message": "Supplemental evidence cleared."}


@router.get("/{shipment_id}/items/{item_id}/line-provenance")
async def get_item_line_provenance(
    shipment_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Internal/debug: authoritative structured-import lineage (CI/ES line index and document).
    Same payload shape as `line_provenance` on analysis `items[]`.
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["documents", "items"])

    if not any(i.id == item_id for i in (shipment.items or [])):
        raise HTTPException(status_code=404, detail="Line item not found")

    result = await db.execute(
        select(ShipmentItemLineProvenance).where(ShipmentItemLineProvenance.shipment_item_id == item_id)
    )
    rows = list(result.scalars().all())
    svc = ShipmentAnalysisService(db)
    return {
        "shipment_id": str(shipment_id),
        "item_id": str(item_id),
        "line_provenance": svc._line_provenance_api_rows(rows, shipment.documents or []),
    }


@router.post("/{shipment_id}/items", status_code=status.HTTP_201_CREATED)
async def add_shipment_item(
    shipment_id: UUID,
    item_data: dict,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """Add item to shipment."""
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    
    # Validate item data (same as create_shipment)
    # ... validation logic ...
    
    item = ShipmentItem(
        shipment_id=shipment.id,
        label=item_data.get("label", ""),
        declared_hts=_normalize_declared_hts(item_data.get("declared_hts_code")),
        value=str(float(item_data["value"])) if "value" in item_data and item_data.get("value") is not None else None,
        currency=item_data.get("currency", "USD"),
        quantity=str(float(item_data["quantity"])) if "quantity" in item_data and item_data.get("quantity") is not None else None,
        unit_of_measure=item_data.get("unit_of_measure"),
        country_of_origin=item_data.get("country_of_origin")
    )
    db.add(item)
    await db.flush()
    if getattr(settings, "PROVENANCE_ON_MANUAL_ITEM_PROVENANCE", False):
        raw_pd = item_data.get("provenance_document_id") or item_data.get("provenance_shipment_document_id")
        raw_li = item_data.get("provenance_line_index")
        if raw_pd is not None and raw_li is not None:
            try:
                pd = UUID(str(raw_pd))
                pli = int(raw_li)
            except (ValueError, TypeError):
                pd = None
                pli = None
            if pd is not None and pli is not None:
                from app.services.shipment_item_provenance_service import ensure_provenance_manual_api

                await ensure_provenance_manual_api(db, shipment, item, shipment_document_id=pd, line_index=pli)
    await db.commit()
    await db.refresh(item)
    
    return {"item_id": str(item.id)}


@router.post("/{shipment_id}/references", status_code=status.HTTP_201_CREATED)
async def add_shipment_reference(
    shipment_id: UUID,
    reference_data: dict,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """Add reference to shipment."""
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    
    if "key" not in reference_data or "value" not in reference_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reference requires both 'key' and 'value'"
        )

    ref = ShipmentReference(
        shipment_id=shipment.id,
        reference_type=reference_data["key"],
        reference_value=reference_data["value"]
    )
    db.add(ref)
    await db.commit()
    await db.refresh(ref)
    
    return {"reference_id": str(ref.id)}


@router.patch("/{shipment_id}")
async def update_shipment(
    shipment_id: UUID,
    update_data: ShipmentUpdateRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Update shipment (rename only).
    
    Status cannot be set by user - it's derived/updated by analysis workflow.
    """
    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    
    # Only allow rename (status is controlled by analysis workflow)
    shipment.name = update_data.name
    await db.commit()
    await db.refresh(shipment)
    
    # Compute eligibility
    eligibility_service = ShipmentEligibilityService(db)
    eligibility = await eligibility_service.compute_eligibility(shipment.id)
    
    return {
        "shipment_id": str(shipment.id),
        "organization_id": str(shipment.organization_id),
        "created_by": str(shipment.created_by),
        "name": shipment.name,
        "status": shipment.status.value,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "eligibility": eligibility
    }


@router.post("/{shipment_id}/extract-preview")
async def extract_preview(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Run document parsing and line item import only. Returns summary for user confirmation.
    Use before full analysis: "Y line items / $XXX duty paid" for user to confirm.
    """
    from app.services.shipment_analysis_service import ShipmentAnalysisService

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    if not shipment.documents:
        raise HTTPException(status_code=400, detail="No documents uploaded. Upload Entry Summary and Commercial Invoice first.")

    service = ShipmentAnalysisService(db)
    result = await service.extract_preview(shipment_id=shipment_id, organization_id=current_org.id)
    return result


class AnalyzeRequest(BaseModel):
    """Optional body for analyze endpoint (e.g. clarification answers for re-run)."""
    clarification_responses: Optional[dict] = Field(
        default=None,
        description="Per-item clarification answers: { item_id: { attribute: value } }"
    )


@router.post("/{shipment_id}/analyze")
async def start_shipment_analysis(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    force_new: bool = Query(False, description="If true, supersede any RUNNING/QUEUED analysis and start a fresh run"),
    request_body: Optional[AnalyzeRequest] = Body(None),
):
    """
    Start analysis for shipment.
    In dev with sync mode, runs analysis in this request and returns 200 with full status (including result_json when complete).
    Otherwise returns 202 Accepted with analysis_id.
    Use force_new=1 when Re-run should start a new run even if one is already RUNNING (e.g. stuck).
    """
    import logging
    from fastapi.responses import JSONResponse
    from app.services.analysis_orchestration_service import AnalysisOrchestrationService

    logger = logging.getLogger(__name__)
    logger.info("POST /analyze shipment_id=%s force_new=%s", shipment_id, force_new)

    try:
        # Enforce mandatory COO for Pre-Compliance before running analysis when shipment has line items.
        repo = OrgScopedRepository(db, Shipment)
        shipment = await repo.get_by_id(shipment_id, current_org.id)
        await db.refresh(shipment, ["references", "items"])
        ref_map = {str(ref.reference_type).upper(): str(ref.reference_value).upper() for ref in (shipment.references or [])}
        shipment_type = ref_map.get("SHIPMENT_TYPE", "PRE_COMPLIANCE")
        is_pre_compliance = shipment_type != "ENTRY_COMPLIANCE"
        if is_pre_compliance and (shipment.items or []):
            missing_coo = [it for it in shipment.items if not (it.country_of_origin and str(it.country_of_origin).strip())]
            if missing_coo:
                missing_names = [it.label or f"Line item {idx + 1}" for idx, it in enumerate(missing_coo)]
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Country of Origin is required for all pre-compliance line items before analysis can run. "
                        f"Missing COO for: {', '.join(missing_names[:5])}"
                        + (f" (+{len(missing_names)-5} more)" if len(missing_names) > 5 else "")
                    ),
                )

        orchestration_service = AnalysisOrchestrationService(db)
        clarification_responses = request_body.clarification_responses if request_body else None
        result = await orchestration_service.start_analysis(
            shipment_id=shipment_id,
            organization_id=current_org.id,
            actor_user_id=current_user.id,
            force_new=force_new,
            clarification_responses=clarification_responses,
        )
        if result.get("sync"):
            return JSONResponse(status_code=status.HTTP_200_OK, content=result)
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analyze endpoint failed: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "sync": True,
                "status": "FAILED",
                "error_message": str(e),
                "has_result": False,
            },
        )


@router.get("/{shipment_id}/analysis/items/{item_id}/evidence")
async def get_item_evidence(
    shipment_id: UUID,
    item_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Get evidence bundle for a shipment item (PSC recommendation drawer).

    Returns supporting/conflicting evidence, document refs, authority refs.
    Uses structured evidence when available; otherwise derives from analysis result_json.
    """
    from app.services.recommendation_evidence_service import RecommendationEvidenceService
    from app.services.analysis_orchestration_service import AnalysisOrchestrationService
    from app.repositories.org_scoped_repository import OrgScopedRepository

    repo = OrgScopedRepository(db, Shipment)
    shipment = await repo.get_by_id(shipment_id, current_org.id)
    await db.refresh(shipment, ["items"])

    item = next((i for i in (shipment.items or []) if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Shipment item not found")

    result_json = None
    orchestration = AnalysisOrchestrationService(db)
    status_resp = await orchestration.get_analysis_status(shipment_id=shipment_id, organization_id=current_org.id)
    if status_resp and status_resp.get("result_json"):
        result_json = status_resp["result_json"]

    service = RecommendationEvidenceService(db)
    bundle = await service.build_item_evidence_bundle(
        shipment_id=shipment_id,
        item_id=item_id,
        result_json=result_json,
    )
    return bundle


@router.get("/{shipment_id}/analysis-status")
async def get_analysis_status(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db)
):
    """
    Get latest analysis status for shipment.
    
    Returns: Latest Analysis + linked ReviewRecord id + status
    """
    from app.services.analysis_orchestration_service import AnalysisOrchestrationService
    from app.models.review_record import ReviewRecord
    from sqlalchemy import select
    
    orchestration_service = AnalysisOrchestrationService(db)
    
    result = await orchestration_service.get_analysis_status(
        shipment_id=shipment_id,
        organization_id=current_org.id
    )
    
    return result


class GroundedChatRequest(BaseModel):
    """Patch F — cite-or-refuse chat grounded in stored analysis only."""

    message: str = Field(..., min_length=1, max_length=4000)
    shipment_item_id: Optional[UUID] = Field(
        default=None,
        description="Optional line item; defaults to first line when omitted.",
    )


@router.post("/{shipment_id}/grounded-chat")
async def post_grounded_classification_chat(
    shipment_id: UUID,
    body: GroundedChatRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """
    Answer from facts, heading trace, evidence, and classification output only (no web / no free-form LLM).
    """
    from app.services.analysis_orchestration_service import AnalysisOrchestrationService
    from app.services.grounded_classification_chat_service import build_grounded_answer

    repo = OrgScopedRepository(db, Shipment)
    await repo.get_by_id(shipment_id, current_org.id)

    orchestration = AnalysisOrchestrationService(db)
    try:
        status_payload = await orchestration.get_analysis_status(
            shipment_id=shipment_id,
            organization_id=current_org.id,
        )
    except HTTPException:
        raise
    result_json = status_payload.get("result_json")
    if not result_json or not isinstance(result_json, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed analysis result available for this shipment. Run analysis first.",
        )
    return build_grounded_answer(
        result_json,
        body.message,
        shipment_item_id=body.shipment_item_id,
    )


@router.get("/{shipment_id}/trust-workflow")
async def get_shipment_trust_workflow(
    shipment_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Derived trust states for documents, items, analysis, and review (Sprint A)."""
    from app.services.trust_workflow_service import TrustWorkflowService

    repo = OrgScopedRepository(db, Shipment)
    await repo.get_by_id(shipment_id, current_org.id)
    svc = TrustWorkflowService(db)
    return await svc.compute_trust_workflow(shipment_id, current_org.id)


class ItemDocumentLinkCreateRequest(BaseModel):
    shipment_item_id: UUID
    shipment_document_id: UUID
    mapping_status: Optional[str] = Field(
        default=ItemDocumentMappingStatus.USER_CONFIRMED,
        description="AUTO | USER_CONFIRMED | REJECTED",
    )


@router.post("/{shipment_id}/item-document-links", status_code=status.HTTP_201_CREATED)
async def create_item_document_link(
    shipment_id: UUID,
    body: ItemDocumentLinkCreateRequest,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Attach a shipment document to a line item (explicit evidence mapping, Sprint C)."""
    repo = OrgScopedRepository(db, Shipment)
    await repo.get_by_id(shipment_id, current_org.id)

    status_val = (body.mapping_status or ItemDocumentMappingStatus.USER_CONFIRMED).strip().upper()
    if status_val not in (
        ItemDocumentMappingStatus.AUTO,
        ItemDocumentMappingStatus.USER_CONFIRMED,
        ItemDocumentMappingStatus.REJECTED,
    ):
        raise HTTPException(status_code=400, detail="Invalid mapping_status")

    item_r = await db.execute(
        select(ShipmentItem).where(
            and_(
                ShipmentItem.id == body.shipment_item_id,
                ShipmentItem.shipment_id == shipment_id,
            )
        )
    )
    item = item_r.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Shipment item not found")

    doc_r = await db.execute(
        select(ShipmentDocument).where(
            and_(
                ShipmentDocument.id == body.shipment_document_id,
                ShipmentDocument.shipment_id == shipment_id,
                ShipmentDocument.organization_id == current_org.id,
            )
        )
    )
    doc = doc_r.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    link = ShipmentItemDocument(
        shipment_id=shipment_id,
        organization_id=current_org.id,
        shipment_item_id=body.shipment_item_id,
        shipment_document_id=body.shipment_document_id,
        mapping_status=status_val,
    )
    db.add(link)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create link (duplicate or invalid reference)",
        )
    await db.refresh(link)
    return {
        "id": str(link.id),
        "shipment_id": str(shipment_id),
        "shipment_item_id": str(link.shipment_item_id),
        "shipment_document_id": str(link.shipment_document_id),
        "mapping_status": link.mapping_status,
    }


@router.delete("/{shipment_id}/item-document-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_document_link(
    shipment_id: UUID,
    link_id: UUID,
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    repo = OrgScopedRepository(db, Shipment)
    await repo.get_by_id(shipment_id, current_org.id)
    lr = await db.execute(
        select(ShipmentItemDocument).where(
            and_(
                ShipmentItemDocument.id == link_id,
                ShipmentItemDocument.shipment_id == shipment_id,
                ShipmentItemDocument.organization_id == current_org.id,
            )
        )
    )
    row = lr.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(row)
    await db.commit()
