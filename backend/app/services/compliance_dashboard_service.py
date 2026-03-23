"""
Compliance Dashboard Service - Sprint 8

Read-only aggregations for compliance visibility.

Key principles:
- Read-only (no mutations)
- Aggregated metrics only
- Explainable and exportable
- No drill-down logic changes
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType, ReviewReasonCode
from app.models.classification_audit import ClassificationAudit

logger = logging.getLogger(__name__)


class ComplianceDashboardService:
    """Service for compliance dashboard aggregations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_summary(
        self,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None,
        hts_chapter: Optional[str] = None,
        reviewer: Optional[str] = None,
        object_type: Optional[ReviewableObjectType] = None
    ) -> Dict[str, Any]:
        """
        Get compliance summary dashboard metrics.
        
        Args:
            time_range_start: Start of time range (default: 30 days ago)
            time_range_end: End of time range (default: now)
            hts_chapter: Filter by HTS chapter (optional)
            reviewer: Filter by reviewer (optional)
            object_type: Filter by object type (optional)
        
        Returns:
            Dictionary with aggregated metrics
        """
        # Default time range: last 30 days
        if time_range_end is None:
            time_range_end = datetime.utcnow()
        if time_range_start is None:
            time_range_start = time_range_end - timedelta(days=30)
        
        # Build filters
        filters = [
            ReviewRecord.created_at >= time_range_start,
            ReviewRecord.created_at <= time_range_end
        ]
        
        if hts_chapter:
            # Extract chapter from snapshot (simplified - would need proper extraction)
            # For now, filter by object_snapshot containing chapter
            filters.append(
                ReviewRecord.object_snapshot['hts_version_id'].astext.isnot(None)
            )
        
        if reviewer:
            filters.append(
                or_(
                    ReviewRecord.created_by == reviewer,
                    ReviewRecord.reviewed_by == reviewer
                )
            )
        
        if object_type:
            filters.append(ReviewRecord.object_type == object_type)
        
        # Total classifications
        total_classifications_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.object_type == ReviewableObjectType.CLASSIFICATION
        )
        total_classifications_result = await self.db.execute(total_classifications_query)
        total_classifications = total_classifications_result.scalar() or 0
        
        # Auto-resolved vs REVIEW_REQUIRED
        auto_resolved_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.object_type == ReviewableObjectType.CLASSIFICATION,
            ReviewRecord.status == ReviewStatus.REVIEWED_ACCEPTED,
            ReviewRecord.review_reason_code == ReviewReasonCode.AUTO_CREATED
        )
        auto_resolved_result = await self.db.execute(auto_resolved_query)
        auto_resolved = auto_resolved_result.scalar() or 0
        
        review_required_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.object_type == ReviewableObjectType.CLASSIFICATION,
            ReviewRecord.status == ReviewStatus.REVIEW_REQUIRED
        )
        review_required_result = await self.db.execute(review_required_query)
        review_required = review_required_result.scalar() or 0
        
        # Reviewed vs overridden
        reviewed_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.status.in_([ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED]),
            ReviewRecord.override_of_review_id.is_(None)  # Not an override
        )
        reviewed_result = await self.db.execute(reviewed_query)
        reviewed = reviewed_result.scalar() or 0
        
        overridden_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.override_of_review_id.isnot(None)
        )
        overridden_result = await self.db.execute(overridden_query)
        overridden = overridden_result.scalar() or 0
        
        # PSC flags count
        psc_flags_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.object_type == ReviewableObjectType.PSC_RADAR,
            ReviewRecord.object_snapshot['output']['flags'].astext.isnot(None)
        )
        psc_flags_result = await self.db.execute(psc_flags_query)
        psc_flags_count = psc_flags_result.scalar() or 0
        
        # High-duty-delta cases (from PSC Radar snapshots)
        # Simplified: count PSC records with duty_delta_amount > threshold
        high_delta_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.object_type == ReviewableObjectType.PSC_RADAR,
            # Check if alternatives have high delta (simplified check)
            ReviewRecord.object_snapshot['output']['flags'].astext.contains('DUTY_DELTA')
        )
        high_delta_result = await self.db.execute(high_delta_query)
        high_delta_count = high_delta_result.scalar() or 0
        
        # Open vs closed review items
        open_reviews_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.status.in_([ReviewStatus.DRAFT, ReviewStatus.REVIEW_REQUIRED])
        )
        open_reviews_result = await self.db.execute(open_reviews_query)
        open_reviews = open_reviews_result.scalar() or 0
        
        closed_reviews_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.status.in_([ReviewStatus.REVIEWED_ACCEPTED, ReviewStatus.REVIEWED_REJECTED])
        )
        closed_reviews_result = await self.db.execute(closed_reviews_query)
        closed_reviews = closed_reviews_result.scalar() or 0
        
        # Calculate percentages
        auto_resolved_pct = (auto_resolved / total_classifications * 100) if total_classifications > 0 else 0.0
        review_required_pct = (review_required / total_classifications * 100) if total_classifications > 0 else 0.0
        
        return {
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat()
            },
            "filters": {
                "hts_chapter": hts_chapter,
                "reviewer": reviewer,
                "object_type": object_type.value if object_type else None
            },
            "metrics": {
                "total_classifications": total_classifications,
                "auto_resolved": {
                    "count": auto_resolved,
                    "percentage": round(auto_resolved_pct, 2)
                },
                "review_required": {
                    "count": review_required,
                    "percentage": round(review_required_pct, 2)
                },
                "reviewed": reviewed,
                "overridden": overridden,
                "psc_flags_count": psc_flags_count,
                "high_duty_delta_cases": high_delta_count,
                "open_reviews": open_reviews,
                "closed_reviews": closed_reviews
            }
        }
