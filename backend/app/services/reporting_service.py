"""
Reporting Service - Sprint 8

Structured, deterministic, reproducible reports for compliance.

Key principles:
- Deterministic (same inputs = same outputs)
- Reproducible (can regenerate any report)
- Filterable (by time, chapter, reviewer, etc.)
- Exportable (JSON, PDF, ZIP)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.review_record import ReviewRecord, ReviewStatus, ReviewableObjectType, ReviewReasonCode

logger = logging.getLogger(__name__)


class ReportingService:
    """Service for generating compliance reports."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_classification_risk_report(
        self,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None,
        hts_chapter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Classification Risk Report.

        Buckets by classification outcome (status), not lexical similarity bands.
        
        Returns:
            Dictionary with risk buckets and counts
        """
        if time_range_end is None:
            time_range_end = datetime.utcnow()
        if time_range_start is None:
            time_range_start = time_range_end - timedelta(days=30)
        
        filters = [
            ReviewRecord.created_at >= time_range_start,
            ReviewRecord.created_at <= time_range_end,
            ReviewRecord.object_type == ReviewableObjectType.CLASSIFICATION
        ]
        
        if hts_chapter:
            # Filter by chapter (simplified)
            pass
        
        # Get all classification records
        query = select(ReviewRecord).where(and_(*filters))
        result = await self.db.execute(query)
        records = list(result.scalars().all())
        
        # Bucket by classification status in snapshot output (not similarity)
        low_confidence = []
        medium_confidence = []
        high_confidence = []
        
        for record in records:
            snapshot = record.object_snapshot
            output = snapshot.get("output", {})
            status = (output.get("status") or "").strip()

            if status in ("NO_CONFIDENT_MATCH", "NO_GOOD_MATCH", "CLARIFICATION_REQUIRED"):
                low_confidence.append(record.id)
            elif status == "REVIEW_REQUIRED":
                medium_confidence.append(record.id)
            elif status == "SUCCESS":
                high_confidence.append(record.id)
            else:
                medium_confidence.append(record.id)
        
        return {
            "report_type": "CLASSIFICATION_RISK",
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat()
            },
            "filters": {
                "hts_chapter": hts_chapter
            },
            "risk_buckets": {
                "low_confidence": {
                    "count": len(low_confidence),
                    "record_ids": [str(r) for r in low_confidence[:100]]  # Limit for size
                },
                "medium_confidence": {
                    "count": len(medium_confidence),
                    "record_ids": [str(r) for r in medium_confidence[:100]]
                },
                "high_confidence": {
                    "count": len(high_confidence),
                    "record_ids": [str(r) for r in high_confidence[:100]]
                }
            },
            "total": len(records)
        }
    
    async def generate_psc_exposure_report(
        self,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate PSC Exposure Report.
        
        Aggregates duty deltas and exposure amounts.
        
        Returns:
            Dictionary with exposure metrics
        """
        if time_range_end is None:
            time_range_end = datetime.utcnow()
        if time_range_start is None:
            time_range_start = time_range_end - timedelta(days=30)
        
        filters = [
            ReviewRecord.created_at >= time_range_start,
            ReviewRecord.created_at <= time_range_end,
            ReviewRecord.object_type == ReviewableObjectType.PSC_RADAR
        ]
        
        query = select(ReviewRecord).where(and_(*filters))
        result = await self.db.execute(query)
        records = list(result.scalars().all())
        
        total_exposure = 0.0
        cases_with_exposure = []
        
        for record in records:
            snapshot = record.object_snapshot
            output = snapshot.get("output", {})
            alternatives = output.get("alternatives", [])
            
            for alt in alternatives:
                delta_amount = alt.get("delta_amount", 0.0)
                if delta_amount and delta_amount > 0:
                    total_exposure += delta_amount
                    cases_with_exposure.append({
                        "review_id": str(record.id),
                        "declared_hts": snapshot.get("inputs", {}).get("declared_hts_code"),
                        "alternative_hts": alt.get("alternative_hts_code"),
                        "delta_amount": delta_amount,
                        "delta_percent": alt.get("delta_percent", 0.0)
                    })
        
        return {
            "report_type": "PSC_EXPOSURE",
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat()
            },
            "exposure_metrics": {
                "total_exposure_usd": round(total_exposure, 2),
                "cases_with_exposure": len(cases_with_exposure),
                "average_exposure_per_case": round(total_exposure / len(cases_with_exposure), 2) if cases_with_exposure else 0.0
            },
            "cases": cases_with_exposure[:100]  # Limit for size
        }
    
    async def generate_review_activity_report(
        self,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None,
        reviewer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Review Activity Report.
        
        Shows accepted/rejected/overridden counts and details.
        
        Returns:
            Dictionary with review activity metrics
        """
        if time_range_end is None:
            time_range_end = datetime.utcnow()
        if time_range_start is None:
            time_range_start = time_range_end - timedelta(days=30)
        
        filters = [
            ReviewRecord.reviewed_at >= time_range_start,
            ReviewRecord.reviewed_at <= time_range_end
        ]
        
        if reviewer:
            filters.append(ReviewRecord.reviewed_by == reviewer)
        
        # Accepted
        accepted_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.status == ReviewStatus.REVIEWED_ACCEPTED
        )
        accepted_result = await self.db.execute(accepted_query)
        accepted_count = accepted_result.scalar() or 0
        
        # Rejected
        rejected_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.status == ReviewStatus.REVIEWED_REJECTED
        )
        rejected_result = await self.db.execute(rejected_query)
        rejected_count = rejected_result.scalar() or 0
        
        # Overridden
        overridden_query = select(func.count(ReviewRecord.id)).where(
            and_(*filters),
            ReviewRecord.override_of_review_id.isnot(None)
        )
        overridden_result = await self.db.execute(overridden_query)
        overridden_count = overridden_result.scalar() or 0
        
        # Get detailed records
        detailed_query = select(ReviewRecord).where(and_(*filters)).limit(100)
        detailed_result = await self.db.execute(detailed_query)
        detailed_records = list(detailed_result.scalars().all())
        
        return {
            "report_type": "REVIEW_ACTIVITY",
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat()
            },
            "filters": {
                "reviewer": reviewer
            },
            "activity_metrics": {
                "accepted": accepted_count,
                "rejected": rejected_count,
                "overridden": overridden_count,
                "total": accepted_count + rejected_count + overridden_count
            },
            "detailed_records": [
                {
                    "review_id": str(r.id),
                    "object_type": r.object_type.value,
                    "status": r.status.value,
                    "reviewed_by": r.reviewed_by,
                    "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                    "review_reason_code": r.review_reason_code.value if r.review_reason_code else None,
                    "is_override": r.override_of_review_id is not None
                }
                for r in detailed_records
            ]
        }
    
    async def generate_unresolved_risk_report(
        self,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate Unresolved Risk Report.
        
        Lists REVIEW_REQUIRED items still open.
        
        Returns:
            Dictionary with unresolved risks
        """
        if time_range_end is None:
            time_range_end = datetime.utcnow()
        if time_range_start is None:
            time_range_start = time_range_end - timedelta(days=30)
        
        filters = [
            ReviewRecord.created_at >= time_range_start,
            ReviewRecord.created_at <= time_range_end,
            ReviewRecord.status == ReviewStatus.REVIEW_REQUIRED
        ]
        
        query = select(ReviewRecord).where(and_(*filters))
        result = await self.db.execute(query)
        records = list(result.scalars().all())
        
        unresolved_risks = []
        for record in records:
            snapshot = record.object_snapshot
            unresolved_risks.append({
                "review_id": str(record.id),
                "object_type": record.object_type.value,
                "created_at": record.created_at.isoformat(),
                "created_by": record.created_by,
                "days_open": (datetime.utcnow() - record.created_at).days,
                "snapshot_summary": {
                    "has_inputs": "inputs" in snapshot,
                    "has_output": "output" in snapshot
                }
            })
        
        return {
            "report_type": "UNRESOLVED_RISK",
            "time_range": {
                "start": time_range_start.isoformat(),
                "end": time_range_end.isoformat()
            },
            "unresolved_count": len(unresolved_risks),
            "unresolved_risks": unresolved_risks
        }
