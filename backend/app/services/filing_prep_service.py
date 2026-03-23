"""
Filing Prep Service - Sprint 9

Service for generating broker-ready filing prep bundles.

Key principles:
- Read-only intelligence
- Explicit blockers
- Conservative defaults
- Human review required
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.filing_prep_bundle import (
    FilingPrepBundle,
    DutyBreakdown,
    ReviewStatus,
    ExportBlockReason
)
from app.models.review_record import ReviewRecord, ReviewStatus as ReviewRecordStatus
from app.services.review_service import ReviewService
from app.services.audit_replay_service import AuditReplayService
from app.engines.psc_radar import PSCRadar, PSCRadarFlag
from app.engines.regulatory_applicability import RegulatoryApplicabilityEngine
from scripts.duty_resolution import resolve_duty
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID
from sqlalchemy import select
from app.models.document import Document, DocumentType

logger = logging.getLogger(__name__)


class FilingPrepService:
    """Service for generating filing prep bundles."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.review_service = ReviewService(db)
        self.audit_replay_service = AuditReplayService(db)
        self.psc_radar = PSCRadar(db)
        self.regulatory_engine = RegulatoryApplicabilityEngine(db)
    
    async def create_filing_prep_bundle(
        self,
        declared_hts_code: str,
        quantity: Optional[float] = None,
        unit_of_measure: Optional[str] = None,
        customs_value: Optional[float] = None,
        country_of_origin: Optional[str] = None,
        product_description: Optional[str] = None,
        review_id: Optional[UUID] = None,
        block_on_unresolved_psc: bool = True,
        client_id: Optional[UUID] = None
    ) -> FilingPrepBundle:
        """
        Create filing prep bundle for broker handoff.
        
        Args:
            declared_hts_code: 10-digit HTS code
            quantity: Product quantity
            unit_of_measure: Unit of measure
            customs_value: Customs value
            country_of_origin: Country of origin (context only)
            product_description: Product description (for PSC Radar)
            review_id: Optional review record ID (if already reviewed)
            block_on_unresolved_psc: Block export if unresolved PSC flags (default: True)
        
        Returns:
            FilingPrepBundle with validation and blockers
        """
        # Resolve duty
        resolved_duty = await resolve_duty(
            declared_hts_code,
            db=self.db,
            hts_version_id=AUTHORITATIVE_HTS_VERSION_ID
        )
        
        if not resolved_duty:
            raise ValueError(f"Could not resolve duty for HTS code {declared_hts_code}")
        
        # Build duty breakdown
        duty_breakdown = DutyBreakdown(
            general_duty=resolved_duty.resolved_general_raw,
            special_duty=resolved_duty.resolved_special_raw,
            column2_duty=resolved_duty.resolved_col2_raw
        )
        
        # Check review status
        review_status = ReviewStatus.REVIEW_REQUIRED
        review_metadata = {}
        
        if review_id:
            # Fetch review record
            review_record = await self.review_service.get_review_record(review_id)
            if review_record:
                if review_record.status == ReviewRecordStatus.REVIEWED_ACCEPTED:
                    review_status = ReviewStatus.REVIEWED_ACCEPTED
                elif review_record.status == ReviewRecordStatus.REVIEWED_REJECTED:
                    review_status = ReviewStatus.REVIEWED_REJECTED
                
                review_metadata = {
                    "review_id": str(review_record.id),
                    "reviewed_by": review_record.reviewed_by,
                    "reviewed_at": review_record.reviewed_at,
                    "review_notes": review_record.review_notes,
                    "is_override": review_record.override_of_review_id is not None,
                    "override_of_review_id": str(review_record.override_of_review_id) if review_record.override_of_review_id else None,
                    "override_justification": review_record.review_notes if review_record.override_of_review_id else None
                }
        
        # Check PSC flags (if product description provided)
        psc_flags = []
        if product_description and customs_value and quantity:
            try:
                psc_result = await self.psc_radar.analyze(
                    product_description=product_description,
                    declared_hts_code=declared_hts_code,
                    quantity=quantity,
                    customs_value=customs_value,
                    country_of_origin=country_of_origin
                )
                psc_flags = [f.value for f in psc_result.flags]
            except Exception as e:
                logger.warning(f"PSC Radar analysis failed: {e}")
                # Don't block on PSC Radar failure, but note it
        
        # Evaluate regulatory applicability (Side Sprint A)
        regulatory_evaluations = []
        try:
            # Fetch document evidence (datasheets, etc.) if client_id provided
            document_evidence = []
            if client_id:
                # Get recent documents (datasheets, specs) for evidence
                documents_result = await self.db.execute(
                    select(Document)
                    .where(
                        Document.client_id == client_id,
                        Document.processing_status == "completed",
                        Document.document_type.in_([DocumentType.OTHER, DocumentType.COMMERCIAL_INVOICE])
                    )
                    .order_by(Document.uploaded_at.desc())
                    .limit(10)  # Get recent documents
                )
                documents = documents_result.scalars().all()
                
                # Build evidence list
                for doc in documents:
                    if doc.extracted_text or doc.structured_data:
                        document_evidence.append({
                            "document_id": str(doc.id),
                            "document_type": doc.document_type.value if doc.document_type else "other",
                            "extracted_text": doc.extracted_text or "",
                            "structured_data": doc.structured_data or {}
                        })
            
            # Run regulatory evaluation
            regulatory_results = await self.regulatory_engine.evaluate_regulatory_applicability(
                declared_hts_code=declared_hts_code,
                product_description=product_description,
                document_evidence=document_evidence
            )
            
            # Convert to serializable format
            for result in regulatory_results:
                regulatory_evaluations.append({
                    "regulator": result.regulator.value,
                    "outcome": result.outcome.value,
                    "explanation_text": result.explanation_text,
                    "triggered_by_hts_code": result.triggered_by_hts_code,
                    "condition_evaluations": [
                        {
                            "condition_id": ce.condition_id,
                            "state": ce.state.value,
                            "evidence_refs": ce.evidence_refs
                        }
                        for ce in result.condition_evaluations
                    ]
                })
        except Exception as e:
            logger.warning(f"Regulatory evaluation failed: {e}")
            # Don't block on regulatory evaluation failure, but note it
        
        # Build broker notes
        broker_notes = self._build_broker_notes(
            resolved_duty,
            review_metadata,
            psc_flags,
            block_on_unresolved_psc,
            regulatory_evaluations
        )
        
        # Build disclaimers
        disclaimers = self._build_disclaimers()
        
        # Create bundle
        bundle = FilingPrepBundle(
            declared_hts_code=declared_hts_code,
            duty_breakdown=duty_breakdown,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            customs_value=customs_value,
            country_of_origin=country_of_origin,
            review_status=review_status,
            psc_flags=psc_flags,
            hts_version_id=AUTHORITATIVE_HTS_VERSION_ID,
            review_id=review_metadata.get("review_id"),
            reviewed_by=review_metadata.get("reviewed_by"),
            reviewed_at=review_metadata.get("reviewed_at"),
            review_notes=review_metadata.get("review_notes"),
            is_override=review_metadata.get("is_override", False),
            override_of_review_id=review_metadata.get("override_of_review_id"),
            override_justification=review_metadata.get("override_justification"),
            disclaimers=disclaimers,
            broker_notes=broker_notes,
            regulatory_evaluations=regulatory_evaluations
        )
        
        # Validate and set blockers
        self._validate_and_set_blockers(bundle, block_on_unresolved_psc)
        
        return bundle
    
    def _validate_and_set_blockers(
        self,
        bundle: FilingPrepBundle,
        block_on_unresolved_psc: bool
    ) -> None:
        """
        Validate bundle and set export blockers.
        
        Hard gates - no soft warnings.
        """
        blockers = []
        
        # Block if REVIEW_REQUIRED
        if bundle.review_status == ReviewStatus.REVIEW_REQUIRED:
            blockers.append(ExportBlockReason.REVIEW_REQUIRED)
        
        # Block if missing quantity
        if bundle.quantity is None:
            blockers.append(ExportBlockReason.MISSING_QUANTITY)
        
        # Block if missing value
        if bundle.customs_value is None:
            blockers.append(ExportBlockReason.MISSING_VALUE)
        
        # Block if missing duty fields
        if not bundle.duty_breakdown.general_duty:
            blockers.append(ExportBlockReason.MISSING_DUTY_FIELDS)
        
        # Block if unresolved PSC flags (if configured)
        if block_on_unresolved_psc and bundle.psc_flags:
            blockers.append(ExportBlockReason.UNRESOLVED_PSC_FLAGS)
        
        # Block if conditional regulatory flags (Side Sprint A)
        if bundle.regulatory_evaluations:
            for reg_eval in bundle.regulatory_evaluations:
                if reg_eval.get("outcome") == "CONDITIONAL":
                    blockers.append(ExportBlockReason.REVIEW_REQUIRED)
                    break  # One conditional is enough to require review
        
        bundle.export_blocked = len(blockers) > 0
        bundle.export_block_reasons = blockers
    
    def _build_broker_notes(
        self,
        resolved_duty: Any,
        review_metadata: Dict[str, Any],
        psc_flags: List[str],
        block_on_unresolved_psc: bool,
        regulatory_evaluations: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build structured broker notes."""
        notes = {
            "what_was_reviewed": [],
            "what_was_overridden": [],
            "what_risks_were_flagged": [],
            "what_neco_did_not_evaluate": []
        }
        
        # What was reviewed
        if review_metadata.get("review_id"):
            notes["what_was_reviewed"].append(
                f"Classification reviewed by {review_metadata.get('reviewed_by')} "
                f"on {review_metadata.get('reviewed_at')}"
            )
            if review_metadata.get("review_notes"):
                notes["what_was_reviewed"].append(f"Review notes: {review_metadata.get('review_notes')}")
        
        # What was overridden
        if review_metadata.get("is_override"):
            notes["what_was_overridden"].append(
                f"Original classification was overridden. "
                f"Override justification: {review_metadata.get('override_justification')}"
            )
        
        # What risks were flagged
        if psc_flags:
            notes["what_risks_were_flagged"].extend([
                f"PSC Radar flag: {flag}" for flag in psc_flags
            ])
        
        # Regulatory evaluations (Side Sprint A)
        if regulatory_evaluations:
            for reg_eval in regulatory_evaluations:
                regulator = reg_eval.get("regulator", "")
                outcome = reg_eval.get("outcome", "")
                explanation = reg_eval.get("explanation_text", "")
                
                if outcome == "APPLIES":
                    notes["what_risks_were_flagged"].append(
                        f"{regulator} applicability identified: {explanation}"
                    )
                elif outcome == "SUPPRESSED":
                    # Note suppression but don't flag as risk
                    if "regulatory_suppressions" not in notes:
                        notes["regulatory_suppressions"] = []
                    notes["regulatory_suppressions"].append(
                        f"{regulator} applicability evaluated and suppressed: {explanation}"
                    )
                elif outcome == "CONDITIONAL":
                    notes["what_risks_were_flagged"].append(
                        f"{regulator} applicability conditional - review required: {explanation}"
                    )
        
        # What NECO did NOT evaluate
        notes["what_neco_did_not_evaluate"] = [
            "Trade program eligibility (GSP, AGOA, etc.)",
            "Country-specific duty rates beyond general/special/column2",
            "Quota or safeguard measures",
            "Section 301/232 applicability",
            "ADD/CVD orders",
            "PSC filing eligibility or timelines",
            "Legal interpretation of HTS notes or rulings"
        ]
        
        return notes
    
    def _build_disclaimers(self) -> List[str]:
        """Build disclaimers for broker handoff."""
        return [
            "This is not a filing. Broker review required before submission.",
            "NECO does not provide legal advice or filing recommendations.",
            "Duty rates are based on general/special/column2 only. Trade programs, quotas, and other measures not evaluated.",
            "Country of origin is provided for context only. NECO does not evaluate origin rules or preferences.",
            "PSC Radar flags indicate potential risks but do not constitute filing advice.",
            "All classifications should be verified against current HTSUS and applicable rulings.",
            "Broker assumes full responsibility for final classification and filing decisions."
        ]
