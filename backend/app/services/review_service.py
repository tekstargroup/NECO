"""
Review Service - Sprint 7

Service layer for review, override, and audit operations.

Key principles:
- Immutable snapshots
- Explicit state transitions
- Complete audit trail
- RBAC enforcement
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.review_record import (
    ReviewRecord,
    ReviewableObjectType,
    ReviewStatus,
    ReviewReasonCode
)
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID, validate_hts_version_id

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing review records and state transitions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_review_record(
        self,
        object_type: ReviewableObjectType,
        object_snapshot: Dict[str, Any],
        created_by: str,
        hts_version_id: Optional[str] = None,
        initial_status: ReviewStatus = ReviewStatus.DRAFT
    ) -> ReviewRecord:
        """
        Create a new review record with immutable snapshot.
        
        Args:
            object_type: Type of object being reviewed
            object_snapshot: Immutable snapshot of object state
            created_by: User ID creating the record
            hts_version_id: HTS version ID (defaults to authoritative)
            initial_status: Initial status (default: DRAFT)
        
        Returns:
            Created ReviewRecord
        """
        # Validate HTS version
        validated_version = validate_hts_version_id(hts_version_id)
        
        # Ensure snapshot includes required fields
        snapshot = {
            **object_snapshot,
            "_snapshot_created_at": datetime.utcnow().isoformat(),
            "_snapshot_version": "1.0"
        }
        
        record = ReviewRecord(
            object_type=object_type,
            object_snapshot=snapshot,
            hts_version_id=validated_version,
            status=initial_status,
            created_by=created_by,
            review_reason_code=ReviewReasonCode.AUTO_CREATED if initial_status == ReviewStatus.DRAFT else None
        )
        
        self.db.add(record)
        await self.db.flush()
        
        logger.info(
            f"Created review record {record.id} for {object_type.value} "
            f"by {created_by}, status={initial_status.value}"
        )
        
        return record
    
    async def transition_status(
        self,
        review_id: UUID,
        new_status: ReviewStatus,
        reviewed_by: str,
        user_role: str,
        reason_code: ReviewReasonCode,
        notes: Optional[str] = None
    ) -> ReviewRecord:
        """
        Transition review record to new status.
        
        Enforces:
        - Valid state transitions
        - RBAC (only REVIEWER can finalize)
        - Reviewer cannot review own submission
        
        Args:
            review_id: Review record ID
            new_status: Target status
            reviewed_by: User ID performing review
            user_role: Role of user (VIEWER, ANALYST, REVIEWER)
            reason_code: Reason for transition
            notes: Optional notes
        
        Returns:
            Updated ReviewRecord
        
        Raises:
            ValueError: If transition is invalid
        """
        # Fetch record
        result = await self.db.execute(
            select(ReviewRecord).where(ReviewRecord.id == review_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            raise ValueError(f"Review record {review_id} not found")
        
        # Check if reviewer is reviewing own submission
        if reviewed_by == record.created_by and new_status in [ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED]:
            raise ValueError("Reviewer cannot review their own submission")
        
        # Validate transition
        is_valid, error_msg = record.can_transition_to(new_status, user_role)
        if not is_valid:
            raise ValueError(error_msg)
        
        previous_status = record.status
        record.status = new_status
        record.reviewed_at = datetime.utcnow()
        record.reviewed_by = reviewed_by
        record.review_reason_code = reason_code
        record.review_notes = notes
        
        await self.db.flush()

        if new_status == ReviewStatus.REVIEWED_ACCEPTED:
            await self._record_product_knowledge(record, reviewed_by)

        logger.info(
            f"Transitioned review record {review_id} from {previous_status.value} "
            f"to {new_status.value} by {reviewed_by} ({user_role})"
        )
        
        return record
    
    async def create_override(
        self,
        original_review_id: UUID,
        new_object_snapshot: Dict[str, Any],
        created_by: str,
        reason_code: ReviewReasonCode,
        justification: str,
        hts_version_id: Optional[str] = None
    ) -> ReviewRecord:
        """
        Create an override record.
        
        Overrides create a NEW record linked to the original.
        They do NOT mutate the original record.
        
        Args:
            original_review_id: ID of original review record
            new_object_snapshot: New snapshot for override
            created_by: User ID creating override
            reason_code: Reason for override
            justification: Free-text justification (required)
            hts_version_id: HTS version ID (defaults to authoritative)
        
        Returns:
            New ReviewRecord (override)
        
        Raises:
            ValueError: If original record not found or justification missing
        """
        if not justification or not justification.strip():
            raise ValueError("Override requires justification")
        
        # Fetch original record
        result = await self.db.execute(
            select(ReviewRecord).where(ReviewRecord.id == original_review_id)
        )
        original = result.scalar_one_or_none()
        
        if not original:
            raise ValueError(f"Original review record {original_review_id} not found")
        
        # Validate HTS version
        validated_version = validate_hts_version_id(hts_version_id)
        
        # Create new record with override linkage
        override_snapshot = {
            **new_object_snapshot,
            "_snapshot_created_at": datetime.utcnow().isoformat(),
            "_snapshot_version": "1.0",
            "_override_of": str(original_review_id),
            "_override_reason": reason_code.value,
            "_override_justification": justification
        }
        
        override_record = ReviewRecord(
            object_type=original.object_type,
            object_snapshot=override_snapshot,
            hts_version_id=validated_version,
            status=ReviewStatus.DRAFT,  # Override starts as draft
            created_by=created_by,
            override_of_review_id=original_review_id,
            review_reason_code=reason_code,
            review_notes=justification
        )
        
        self.db.add(override_record)
        await self.db.flush()
        
        logger.info(
            f"Created override record {override_record.id} for original {original_review_id} "
            f"by {created_by}, reason={reason_code.value}"
        )
        
        return override_record
    
    async def get_review_record(self, review_id: UUID) -> Optional[ReviewRecord]:
        """Get review record by ID."""
        result = await self.db.execute(
            select(ReviewRecord).where(ReviewRecord.id == review_id)
        )
        return result.scalar_one_or_none()
    
    async def get_review_history(self, review_id: UUID) -> List[ReviewRecord]:
        """
        Get full review history including overrides.
        
        Returns list ordered by creation time (original first, then overrides).
        """
        # Get original
        original = await self.get_review_record(review_id)
        if not original:
            return []
        
        # Get all overrides
        result = await self.db.execute(
            select(ReviewRecord)
            .where(ReviewRecord.override_of_review_id == review_id)
            .order_by(ReviewRecord.created_at)
        )
        overrides = list(result.scalars().all())
        
        return [original] + overrides

    async def _record_product_knowledge(self, record: ReviewRecord, accepted_by: str) -> None:
        """On acceptance, record each item's HTS in the product knowledge base."""
        try:
            from app.services.product_knowledge_service import ProductKnowledgeService
            from app.models.shipment import Shipment
            knowledge_svc = ProductKnowledgeService(self.db)
            snapshot = record.object_snapshot or {}
            items = snapshot.get("items") or []
            shipment_id_str = snapshot.get("shipment_id")
            if not shipment_id_str:
                return
            shipment_result = await self.db.execute(
                select(Shipment).where(Shipment.id == UUID(shipment_id_str))
            )
            shipment_obj = shipment_result.scalar_one_or_none()
            if not shipment_obj:
                return
            org_id = shipment_obj.organization_id
            provenance = snapshot.get("analysis_provenance")

            for it in items:
                hts = it.get("hts_code")
                label = it.get("label")
                if not hts or not label:
                    continue
                memo = it.get("classification_memo") or {}
                if memo.get("support_level") != "supported":
                    continue
                await knowledge_svc.record_acceptance(
                    organization_id=org_id,
                    description=label,
                    hts_code=hts,
                    country_of_origin=it.get("country_of_origin"),
                    confidence=memo.get("proposed_hts_confidence"),
                    source_review_id=record.id,
                    source_shipment_id=UUID(shipment_id_str) if shipment_id_str else None,
                    source_item_id=UUID(it["id"]) if it.get("id") else None,
                    accepted_by=accepted_by,
                    provenance=provenance,
                )
        except Exception as e:
            logger.warning(f"Failed to record product knowledge on acceptance: {e}", exc_info=True)
