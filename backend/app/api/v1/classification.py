"""
Classification API Endpoints

Endpoints for generating and retrieving HTS code alternatives.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_client
from app.models.user import User
from app.models.client import Client
from app.models.sku import SKU
from app.models.classification import ClassificationAlternative
from app.models.classification_audit import ClassificationAudit
from app.engines.classification.engine import ClassificationEngine

router = APIRouter()


class ClassificationRequest(BaseModel):
    """Request payload for classification generation"""
    description: str = Field(..., description="Product description")
    country_of_origin: Optional[str] = Field(None, description="2-letter country code (e.g., CN, MX)")
    value: Optional[float] = Field(None, description="Product value")
    quantity: Optional[float] = Field(None, description="Product quantity")
    current_hts_code: Optional[str] = Field(None, description="Current HTS code if known")
    sku_id: Optional[UUID] = Field(None, description="SKU ID if available")
    clarification_responses: Optional[Dict[str, Any]] = Field(
        None,
        description="Responses to clarification questions (attribute -> value mapping)"
    )


class ClassificationResponse(BaseModel):
    """Response for classification generation"""
    success: bool
    status: str  # REQUIRED - must never be None
    candidates: List[dict]
    metadata: dict
    error: Optional[str] = None
    product_analysis: Optional[dict] = None  # For CLARIFICATION_REQUIRED
    questions: Optional[List[dict]] = None  # For CLARIFICATION_REQUIRED
    blocking_reason: Optional[str] = None  # For CLARIFICATION_REQUIRED
    audit_id: Optional[str] = None  # For CLARIFICATION_REQUIRED


@router.post("/generate", response_model=ClassificationResponse)
async def generate_classification(
    request: ClassificationRequest,
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate alternative HTS codes for a product.
    
    Can be called with either:
    - A payload containing description, COO, etc.
    - A sku_id (will extract data from SKU record)
    """
    try:
        # Get SKU data if sku_id provided
        sku_id = request.sku_id
        sku = None
        
        if sku_id:
            result = await db.execute(
                select(SKU).where(SKU.id == sku_id, SKU.client_id == current_client.id)
            )
            sku = result.scalar_one_or_none()
            
            if not sku:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SKU {sku_id} not found"
                )
            
            # Use SKU data, but allow request to override
            description = request.description or sku.description
            country_of_origin = request.country_of_origin or sku.country_of_origin
            current_hts_code = request.current_hts_code or sku.hts_declared
            value = request.value or (float(sku.average_value) if sku.average_value else None)
            quantity = request.quantity
        else:
            description = request.description
            country_of_origin = request.country_of_origin
            current_hts_code = request.current_hts_code
            value = request.value
            quantity = request.quantity
        
        if not description:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Description is required"
            )
        
        # Generate alternatives
        engine = ClassificationEngine(db)
        result = await engine.generate_alternatives(
            description=description,
            country_of_origin=country_of_origin,
            value=value,
            quantity=quantity,
            current_hts_code=current_hts_code,
            sku_id=str(sku_id) if sku_id else None,
            client_id=str(current_client.id),
            clarification_responses=request.clarification_responses
        )
        
        if not result.get("success"):
            # Handle different failure types
            metadata = result.get("metadata", {})
            error = result.get("error", "Unknown error")
            error_reason = result.get("error_reason", "")
            status = result.get("status", "FAILED")
            
            # Handle CLARIFICATION_REQUIRED status
            # CRITICAL: Validate status is not None
            if not status:
                raise ValueError("Status is None - this is a critical bug. Status must always be set.")
            
            if status == "CLARIFICATION_REQUIRED":
                # Create audit record for clarification request
                product_analysis = metadata.get("product_analysis", {}) or result.get("product_analysis", {})
                questions = result.get("questions", [])
                
                # CRITICAL: Ensure product_analysis and questions are not None
                if not product_analysis:
                    raise ValueError("product_analysis is None for CLARIFICATION_REQUIRED - this is a critical bug")
                if not questions:
                    raise ValueError("questions is None for CLARIFICATION_REQUIRED - this is a critical bug")
                
                audit = ClassificationAudit(
                    sku_id=sku_id,
                    client_id=current_client.id,
                    input_description=description,
                    input_coo=country_of_origin,
                    input_value=str(value) if value else None,
                    input_qty=str(quantity) if quantity else None,
                    input_current_hts=current_hts_code,
                    engine_version=engine.engine_version,
                    error_message=error_reason or error,
                    candidates_generated="0",
                    processing_time_ms=str(metadata.get("processing_time_ms", 0)),
                    status=status,  # REQUIRED - must be CLARIFICATION_REQUIRED
                    reason_code="MISSING_REQUIRED_ATTRIBUTES",  # Changed from CLARIFICATION_REQUIRED to be more specific
                    applied_filters=[],
                    candidate_counts=None,  # NULL for CLARIFICATION_REQUIRED (no candidates retrieved)
                    product_analysis=product_analysis,  # REQUIRED - must not be None
                    clarification_questions=questions,  # REQUIRED - must not be None
                    clarification_responses=request.clarification_responses
                )
                db.add(audit)
                await db.flush()  # Get audit.id
                await db.commit()
                
                # Validate audit was persisted correctly
                verify_result = await db.execute(
                    select(ClassificationAudit).where(ClassificationAudit.id == audit.id)
                )
                verify_audit = verify_result.scalar_one_or_none()
                if not verify_audit:
                    raise ValueError("Audit record was not persisted - critical bug")
                if not verify_audit.product_analysis:
                    raise ValueError("product_analysis is NULL in persisted audit - critical bug")
                if not verify_audit.clarification_questions:
                    raise ValueError("clarification_questions is NULL in persisted audit - critical bug")
                
                # Return clarification questions with all required fields
                return ClassificationResponse(
                    success=False,
                    status=status,  # REQUIRED
                    candidates=[],
                    metadata=metadata,
                    error=error,
                    product_analysis=product_analysis,  # REQUIRED for CLARIFICATION_REQUIRED
                    questions=questions,  # REQUIRED for CLARIFICATION_REQUIRED
                    blocking_reason=result.get("blocking_reason", "Required classification attributes missing"),
                    audit_id=str(audit.id)  # REQUIRED for CLARIFICATION_REQUIRED
                )
            
            # Create audit record for tracking with full audit fields
            audit = ClassificationAudit(
                sku_id=sku_id,
                client_id=current_client.id,
                input_description=description,
                input_coo=country_of_origin,
                input_value=str(value) if value else None,
                input_qty=str(quantity) if quantity else None,
                input_current_hts=current_hts_code,
                engine_version=engine.engine_version,
                error_message=error_reason or error,
                candidates_generated=str(len(result.get("candidates", []))),
                processing_time_ms=str(metadata.get("processing_time_ms", 0)),
                status=status,
                similarity_top=str(metadata.get("best_similarity", 0.0)),
                threshold_used=str(metadata.get("threshold_used", "0.20")),
                reason_code=metadata.get("reason_code", error),
                applied_filters=metadata.get("applied_filters", []),
                candidate_counts={
                    "pre_filter_count": metadata.get("pre_filter_count", 0),
                    "post_filter_count": metadata.get("post_filter_count", 0),
                    "post_score_count": metadata.get("post_score_count", 0)
                },
                product_analysis=metadata.get("product_analysis"),
                clarification_responses=request.clarification_responses
            )
            db.add(audit)
            await db.commit()
            
            # CRITICAL: Validate status is not None
            if not status:
                raise ValueError("Status is None - this is a critical bug. Status must always be set.")
            
            # For NO_CONFIDENT_MATCH, return candidates as "untrusted" for human review
            if status == "NO_CONFIDENT_MATCH":
                return ClassificationResponse(
                    success=False,
                    status=status,  # REQUIRED
                    candidates=result.get("candidates", []),  # Top 5 as "untrusted"
                    metadata=metadata,
                    error=error
                )
            
            # For REVIEW_REQUIRED, return candidates but flag for review
            if status == "REVIEW_REQUIRED":
                return ClassificationResponse(
                    success=True,  # Candidates exist but need review
                    status=status,  # REQUIRED
                    candidates=result.get("candidates", []),
                    metadata=metadata,
                    error=None
                )
            
            return ClassificationResponse(
                success=False,
                status=status,  # REQUIRED
                candidates=[],
                metadata=metadata,
                error=error
            )
        
        # Persist results (only if quality gate passed)
        candidates = result.get("candidates", [])
        context_payload = result.get("context_payload")
        provenance = result.get("provenance", {})
        metadata = result.get("metadata", {})
        
        # Quality gate check: Don't persist if top_score < 0.20
        top_score = metadata.get("top_candidate_score", 0.0)
        if isinstance(top_score, str):
            try:
                top_score = float(top_score)
            except (ValueError, TypeError):
                top_score = 0.0
        
        if top_score < 0.20:
            # Create audit record but don't persist alternatives
            audit = ClassificationAudit(
                sku_id=sku_id,
                client_id=current_client.id,
                input_description=description,
                input_coo=country_of_origin,
                input_value=str(value) if value else None,
                input_qty=str(quantity) if quantity else None,
                input_current_hts=current_hts_code,
                engine_version=engine.engine_version,
                error_message=f"Quality gate: top_score {top_score:.4f} < 0.20 threshold",
                candidates_generated=str(len(candidates)),
                processing_time_ms=str(metadata.get("processing_time_ms", 0)),
                status="NO_GOOD_MATCH",
                similarity_top=str(metadata.get("best_similarity", 0.0)),
                threshold_used="0.20",
                reason_code="QUALITY_GATE_FAILED",
                applied_filters=metadata.get("applied_filters", []),
                candidate_counts={
                    "pre_filter_count": metadata.get("pre_filter_count", 0),
                    "post_filter_count": metadata.get("post_filter_count", 0),
                    "post_score_count": metadata.get("post_score_count", 0)
                },
                product_analysis=metadata.get("product_analysis"),
                clarification_responses=request.clarification_responses
            )
            db.add(audit)
            await db.commit()
            
            return ClassificationResponse(
                success=False,
                status="NO_GOOD_MATCH",  # REQUIRED - must not be None
                candidates=[],
                metadata=metadata,
                error="NO_GOOD_MATCH"
            )
        
            # Create audit record with full audit fields
        audit = ClassificationAudit(
            sku_id=sku_id,
            client_id=current_client.id,
            input_description=description,
            input_coo=country_of_origin,
            input_value=str(value) if value else None,
            input_qty=str(quantity) if quantity else None,
            input_current_hts=current_hts_code,
            engine_version=engine.engine_version,
            context_payload=context_payload,
            provenance=provenance,
            candidates_generated=str(len(candidates)),
            top_candidate_hts=metadata.get("top_candidate_hts"),
            top_candidate_score=metadata.get("top_candidate_score"),
            processing_time_ms=str(metadata.get("processing_time_ms", 0)),
            status="SUCCESS",
            similarity_top=str(metadata.get("best_similarity", 0.0)),
            threshold_used=str(metadata.get("threshold_used", "0.20")),
            reason_code=None,
            applied_filters=metadata.get("applied_filters", []),
            candidate_counts={
                "pre_filter_count": metadata.get("pre_filter_count", 0),
                "post_filter_count": metadata.get("post_filter_count", 0),
                "post_score_count": metadata.get("post_score_count", 0)
            },
            product_analysis=metadata.get("product_analysis"),
            clarification_responses=request.clarification_responses
        )
        db.add(audit)
        await db.flush()  # Get audit.id
        
        # Create classification alternatives (only if quality gate passed)
        for i, candidate in enumerate(candidates):
            # Calculate duty difference if current HTS provided
            current_duty = None
            alternative_duty = None
            duty_difference = None
            
            if current_hts_code and candidate.get("duty_rate_numeric") is not None:
                # TODO: Get current duty from current_hts_code
                # For now, set alternative_duty
                alternative_duty = candidate.get("duty_rate_numeric")
            
            # Determine recommendation level
            is_recommended = 0
            if i == 0:
                is_recommended = 2  # Primary recommendation
            elif i < 3:
                is_recommended = 1  # Alternative
            
            alt = ClassificationAlternative(
                sku_id=sku_id,  # Can be None if called without sku_id
                alternative_hts=candidate["hts_code"],
                alternative_duty=alternative_duty,
                current_duty=current_duty,
                duty_difference=duty_difference,
                risk_score=_calculate_risk_score(candidate),
                confidence_score=candidate.get("final_score", 0.0),
                justification=f"Similarity: {candidate.get('similarity_score', 0):.2f}, "
                             f"Final Score: {candidate.get('final_score', 0):.3f}",
                is_recommended=is_recommended,
                recommendation_reason="Top candidate" if i == 0 else "Alternative option",
                created_by="system",
                analysis_version=engine.engine_version
            )
            db.add(alt)
        
        await db.commit()
        
        # CRITICAL: Validate status is not None
        final_status = metadata.get("status") or result.get("status") or "SUCCESS"
        if not final_status:
            raise ValueError("Status is None in SUCCESS path - this is a critical bug")
        
        return ClassificationResponse(
            success=True,
            status=final_status,  # REQUIRED
            candidates=candidates,
            metadata=metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating classification: {str(e)}"
        )


@router.get("/{sku_id}/alternatives")
async def get_alternatives(
    sku_id: UUID,
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Get classification alternatives for a SKU.
    """
    # Verify SKU belongs to client
    result = await db.execute(
        select(SKU).where(SKU.id == sku_id, SKU.client_id == current_client.id)
    )
    sku = result.scalar_one_or_none()
    
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU {sku_id} not found"
        )
    
    # Get alternatives
    result = await db.execute(
        select(ClassificationAlternative)
        .where(ClassificationAlternative.sku_id == sku_id)
        .order_by(ClassificationAlternative.is_recommended.desc(), ClassificationAlternative.confidence_score.desc())
    )
    alternatives = result.scalars().all()
    
    return {
        "sku_id": str(sku_id),
        "sku_description": sku.description,
        "alternatives": [
            {
                "id": str(alt.id),
                "alternative_hts": alt.alternative_hts,
                "confidence_score": float(alt.confidence_score) if alt.confidence_score else 0.0,
                "risk_score": alt.risk_score,
                "alternative_duty": float(alt.alternative_duty) if alt.alternative_duty else None,
                "current_duty": float(alt.current_duty) if alt.current_duty else None,
                "duty_difference": float(alt.duty_difference) if alt.duty_difference else None,
                "is_recommended": alt.is_recommended,
                "justification": alt.justification,
                "created_at": alt.created_at.isoformat() if alt.created_at else None
            }
            for alt in alternatives
        ]
    }


def _calculate_risk_score(candidate: dict) -> int:
    """Calculate risk score (1-10) for a candidate"""
    risk = 5  # Base risk
    
    # Lower risk for high confidence
    parse_conf = candidate.get("parse_confidence", "medium")
    if "high" in str(parse_conf).lower():
        risk -= 2
    elif "medium" in str(parse_conf).lower():
        risk -= 1
    
    # Lower risk for good similarity
    similarity = candidate.get("similarity_score", 0.0)
    if similarity > 0.7:
        risk -= 2
    elif similarity > 0.5:
        risk -= 1
    
    # Higher risk if duty rate missing
    if not candidate.get("duty_rate_general"):
        risk += 2
    
    return max(1, min(10, risk))

