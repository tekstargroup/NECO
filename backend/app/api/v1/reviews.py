"""
Review API - Sprint 12

Endpoints for viewing and overriding review records.
Review records are immutable snapshots of analysis outputs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from uuid import UUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.dependencies_sprint12 import get_current_user_sprint12, get_current_organization
from app.models.review_record import ReviewRecord, ReviewStatus, ReviewReasonCode
from app.models.shipment import Shipment
from app.models.regulatory_evaluation import RegulatoryEvaluation, RegulatoryCondition
from app.models.user import User
from app.models.organization import Organization

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewResponse(BaseModel):
    """Review record response."""
    id: str
    object_type: str
    status: str
    review_reason_code: Optional[str] = None
    created_at: str
    created_by: str
    prior_review_id: Optional[str] = None
    snapshot_json: dict
    regulatory_evaluations: List[dict] = Field(default_factory=list)
    item_decisions: Optional[dict] = None
    
    class Config:
        from_attributes = True


class ReviewListItem(BaseModel):
    """Review list item (minimal fields)."""
    id: str
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    prior_review_id: Optional[str] = None

    class Config:
        from_attributes = True


class OverrideRequest(BaseModel):
    """Request to override a review."""
    justification: str = Field(..., min_length=10, max_length=2000)


class AcceptRejectRequest(BaseModel):
    """Request to accept or reject a review."""
    action: str = Field(..., pattern="^(accept|reject)$")
    notes: Optional[str] = Field(None, max_length=2000)


class ItemDecisionEntry(BaseModel):
    """Per-line review decision (Sprint E)."""
    status: str = Field(..., pattern="^(pending|accepted|rejected)$")
    notes: Optional[str] = Field(None, max_length=2000)


class PatchItemDecisionsRequest(BaseModel):
    """Merge updates into review_records.item_decisions keyed by item_id (UUID string)."""
    decisions: Dict[str, ItemDecisionEntry]


class OverrideResponse(BaseModel):
    """Response after creating override."""
    new_review_id: str
    prior_review_id: str
    status: str


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Get review record by ID.
    
    Org-scoped via join: review_records -> shipments -> organization_id
    Returns immutable snapshot_json and regulatory evaluations.
    """
    # Query with org-scoping via shipment join
    # Note: We need to extract shipment_id from snapshot_json and join
    from sqlalchemy import func
    result = await db.execute(
        select(ReviewRecord, Shipment)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                ReviewRecord.id == review_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or access denied"
        )
    review = row[0]
    
    # Load regulatory evaluations
    reg_eval_result = await db.execute(
        select(RegulatoryEvaluation)
        .where(RegulatoryEvaluation.review_id == review_id)
        .options(selectinload(RegulatoryEvaluation.conditions))
    )
    regulatory_evaluations = reg_eval_result.scalars().all()
    
    # Build regulatory evaluations response
    reg_evals_data = []
    for reg_eval in regulatory_evaluations:
        conditions_data = [
            {
                "condition_id": cond.condition_id,
                "condition_description": cond.condition_description,
                "state": cond.state.value if hasattr(cond.state, "value") else str(cond.state),
                "evidence_refs": cond.evidence_refs
            }
            for cond in reg_eval.conditions
        ]
        reg_evals_data.append({
            "id": str(reg_eval.id),
            "regulator": reg_eval.regulator.value if hasattr(reg_eval.regulator, "value") else str(reg_eval.regulator),
            "outcome": reg_eval.outcome.value if hasattr(reg_eval.outcome, "value") else str(reg_eval.outcome),
            "explanation_text": reg_eval.explanation_text,
            "triggered_by_hts_code": reg_eval.triggered_by_hts_code,
            "condition_evaluations": conditions_data
        })
    
    return ReviewResponse(
        id=str(review.id),
        object_type=review.object_type.value if hasattr(review.object_type, "value") else str(review.object_type),
        status=review.status.value if hasattr(review.status, "value") else str(review.status),
        review_reason_code=review.review_reason_code.value if hasattr(review.review_reason_code, "value") else str(review.review_reason_code),
        created_at=review.created_at.isoformat(),
        created_by=str(review.created_by),
        prior_review_id=str(review.override_of_review_id) if review.override_of_review_id else None,
        snapshot_json=review.object_snapshot,
        regulatory_evaluations=reg_evals_data,
        item_decisions=review.item_decisions if getattr(review, "item_decisions", None) else None,
    )


@router.get("/shipments/{shipment_id}/reviews", response_model=List[ReviewListItem])
async def list_shipment_reviews(
    shipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    List reviews for a shipment.
    
    Org-scoped, ordered by created_at desc.
    """
    # First verify shipment belongs to org
    shipment_result = await db.execute(
        select(Shipment).where(
            and_(
                Shipment.id == shipment_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    shipment = shipment_result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found or access denied"
        )
    
    # Get reviews linked to this shipment (via snapshot_json)
    # Note: This is a simplified approach - in production you might want a direct FK
    result = await db.execute(
        select(ReviewRecord)
        .where(
            ReviewRecord.object_snapshot["shipment_id"].astext == str(shipment_id)
        )
        .order_by(desc(ReviewRecord.created_at))
    )
    reviews = result.scalars().all()
    
    return [
        ReviewListItem(
            id=str(review.id),
            status=review.status.value if hasattr(review.status, "value") else str(review.status),
            created_at=review.created_at.isoformat(),
            reviewed_at=review.reviewed_at.isoformat() if review.reviewed_at else None,
            reviewed_by=review.reviewed_by,
            review_notes=review.review_notes,
            prior_review_id=str(review.override_of_review_id) if review.override_of_review_id else None,
        )
        for review in reviews
    ]


@router.patch("/{review_id}")
async def accept_or_reject_review(
    review_id: UUID,
    request: AcceptRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Accept or reject a review via ReviewService.transition_status.
    
    All accept/reject actions go through one centralized path so that
    governance rules (self-review check) and side effects (knowledge
    recording, audit trail) always fire.
    """
    from sqlalchemy import func
    from app.services.review_service import ReviewService

    # Org-scoped access check
    result = await db.execute(
        select(ReviewRecord, Shipment)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                ReviewRecord.id == review_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or access denied"
        )

    new_status = (
        ReviewStatus.REVIEWED_ACCEPTED if request.action == "accept"
        else ReviewStatus.REVIEWED_REJECTED
    )
    if request.action == "reject" and (not request.notes or len(request.notes.strip()) < 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notes are required when rejecting"
        )

    reason_code = (
        ReviewReasonCode.ACCEPTED_AS_IS if request.action == "accept"
        else ReviewReasonCode.REJECTED_INCORRECT
    )

    try:
        svc = ReviewService(db)
        review = await svc.transition_status(
            review_id=review_id,
            new_status=new_status,
            reviewed_by=str(current_user.id),
            user_role="REVIEWER",
            reason_code=reason_code,
            notes=request.notes,
        )
        await db.commit()
        await db.refresh(review)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return {
        "id": str(review.id),
        "status": review.status.value if hasattr(review.status, "value") else str(review.status),
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewed_by": str(review.reviewed_by),
    }


@router.patch("/{review_id}/item-decisions")
async def patch_review_item_decisions(
    review_id: UUID,
    request: PatchItemDecisionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization),
):
    """
    Update per-item decisions on a review record (auditable JSON merge).
    Does not replace immutable snapshot_json; records who updated each line.
    """
    from sqlalchemy import func

    result = await db.execute(
        select(ReviewRecord, Shipment)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id,
        )
        .where(
            and_(
                ReviewRecord.id == review_id,
                Shipment.organization_id == current_org.id,
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or access denied",
        )
    review = row[0]
    prior = dict(review.item_decisions or {})
    now_iso = datetime.utcnow().isoformat() + "Z"
    uid = str(current_user.id)
    for item_id, entry in request.decisions.items():
        prior[item_id] = {
            "status": entry.status,
            "notes": entry.notes,
            "updated_at": now_iso,
            "updated_by": uid,
        }
    review.item_decisions = prior
    await db.commit()
    await db.refresh(review)
    return {"item_decisions": review.item_decisions}


@router.post("/{review_id}/override", response_model=OverrideResponse)
async def override_review(
    review_id: UUID,
    override_request: OverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_sprint12),
    current_org: Organization = Depends(get_current_organization)
):
    """
    Create a new ReviewRecord as an override of an existing one.
    
    Creates new ReviewRecord with prior_review_id.
    Requires justification.
    Does not mutate prior snapshots.
    """
    # Get the prior review (org-scoped)
    from sqlalchemy import func
    prior_result = await db.execute(
        select(ReviewRecord, Shipment)
        .join(
            Shipment,
            func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
        )
        .where(
            and_(
                ReviewRecord.id == review_id,
                Shipment.organization_id == current_org.id
            )
        )
    )
    row = prior_result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or access denied"
        )
    prior_review = row[0]
    
    # Create new review record with prior_review_id
    # Copy snapshot but mark as override
    new_snapshot = prior_review.object_snapshot.copy()
    new_snapshot["override_justification"] = override_request.justification
    new_snapshot["override_created_by"] = str(current_user.id)
    new_snapshot["override_created_at"] = datetime.utcnow().isoformat()
    
    new_review = ReviewRecord(
        object_type=prior_review.object_type,
        object_snapshot=new_snapshot,
        hts_version_id=prior_review.hts_version_id,
        status=ReviewStatus.DRAFT,  # New override starts as DRAFT
        created_by=str(current_user.id),
        review_reason_code=ReviewReasonCode.OVERRIDE_MANUAL_CLASSIFICATION,  # Or appropriate code
        override_of_review_id=prior_review.id
    )
    
    db.add(new_review)
    await db.flush()  # Get new_review.id
    
    # If override changes regulatory applicability, create new evaluation set
    # For now, copy prior evaluations (in future, re-run regulatory engine if needed)
    prior_reg_evals_result = await db.execute(
        select(RegulatoryEvaluation)
        .where(RegulatoryEvaluation.review_id == review_id)
        .options(selectinload(RegulatoryEvaluation.conditions))
    )
    prior_reg_evals = prior_reg_evals_result.scalars().all()
    
    for prior_eval in prior_reg_evals:
        # Create new evaluation linked to new review
        new_eval = RegulatoryEvaluation(
            review_id=new_review.id,
            regulator=prior_eval.regulator,
            outcome=prior_eval.outcome,
            explanation_text=prior_eval.explanation_text,
            triggered_by_hts_code=prior_eval.triggered_by_hts_code
        )
        db.add(new_eval)
        await db.flush()
        
        # Copy conditions
        for prior_cond in prior_eval.conditions:
            new_cond = RegulatoryCondition(
                evaluation_id=new_eval.id,
                condition_id=prior_cond.condition_id,
                condition_description=prior_cond.condition_description,
                state=prior_cond.state,
                evidence_refs=prior_cond.evidence_refs
            )
            db.add(new_cond)
    
    await db.commit()
    
    return OverrideResponse(
        new_review_id=str(new_review.id),
        prior_review_id=str(review_id),
        status=new_review.status.value if hasattr(new_review.status, "value") else str(new_review.status)
    )
