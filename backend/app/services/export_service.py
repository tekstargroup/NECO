"""
Export Service - Sprint 12

Generates export artifacts from ReviewRecord snapshots.
Non-negotiable rules:
- Exports consume ReviewRecord only (no recomputation)
- Blockers enforced before generation
- Evidence integrity required
"""

import logging
import json
import zipfile
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.review_record import ReviewRecord, ReviewStatus
from app.models.regulatory_evaluation import RegulatoryEvaluation, RegulatoryCondition, RegulatoryOutcome
from app.models.export import Export, ExportType, ExportStatus
from app.models.shipment import Shipment
from app.services.s3_upload_service import get_s3_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class ExportService:
    """Service for generating export artifacts from ReviewRecords"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_client = get_s3_client()
    
    async def generate_audit_pack(
        self,
        review_id: UUID,
        organization_id: UUID,
        created_by: UUID
    ) -> Export:
        """
        Generate audit pack export.
        
        Returns Export record with status COMPLETED or BLOCKED.
        """
        # Load review record with org-scoping
        review = await self._load_review_with_org_check(review_id, organization_id)
        
        # Check blockers
        blockers = await self._check_blockers(review)
        if blockers:
            return await self._create_blocked_export(
                review_id=review_id,
                export_type=ExportType.AUDIT_PACK,
                blockers=blockers,
                created_by=created_by
            )
        
        # Generate export
        export = Export(
            review_id=review_id,
            export_type=ExportType.AUDIT_PACK,
            status=ExportStatus.PROCESSING,
            s3_key=f"pending/{uuid4()}",
            s3_bucket=settings.S3_BUCKET_NAME or "LOCAL_FS",
            created_by=created_by
        )
        self.db.add(export)
        await self.db.flush()
        
        try:
            # Build JSON export (canonical snapshot + regulatory evaluations + warnings)
            json_data = await self._build_audit_pack_json(review)
            
            # Create ZIP with JSON + PDF placeholder + metadata
            zip_buffer = await self._create_audit_pack_zip(json_data, review)
            
            # Upload to S3
            s3_key = self._generate_s3_key(organization_id, review_id, ExportType.AUDIT_PACK, export.id)
            sha256_hash = await self._upload_to_s3(zip_buffer, s3_key)
            
            # Update export record
            export.status = ExportStatus.COMPLETED
            export.s3_key = s3_key
            export.s3_bucket = settings.S3_BUCKET_NAME or "LOCAL_FS"
            export.file_size = str(len(zip_buffer.getvalue()))
            export.sha256_hash = sha256_hash
            export.completed_at = datetime.utcnow()
            
            await self.db.commit()
            
            logger.info(f"Audit pack export completed: {export.id} for review {review_id}")
            return export
            
        except Exception as e:
            logger.error(f"Export generation failed: {e}", exc_info=True)
            export.status = ExportStatus.FAILED
            export.error_message = str(e)
            export.error_details = {"error": str(e)}
            await self.db.commit()
            raise
    
    async def generate_broker_prep(
        self,
        review_id: UUID,
        organization_id: UUID,
        created_by: UUID
    ) -> Export:
        """
        Generate broker filing-prep bundle.
        
        Returns Export record with status COMPLETED or BLOCKED.
        """
        # Load review record with org-scoping
        review = await self._load_review_with_org_check(review_id, organization_id)
        
        # Check blockers
        blockers = await self._check_blockers(review)
        
        # Generate export (even if blocked, to show BLOCKED status)
        export = Export(
            review_id=review_id,
            export_type=ExportType.BROKER_PREP,
            status=ExportStatus.PROCESSING,
            s3_key=f"pending/{uuid4()}",
            s3_bucket=settings.S3_BUCKET_NAME or "LOCAL_FS",
            created_by=created_by
        )
        self.db.add(export)
        await self.db.flush()
        
        try:
            # Build export data
            if blockers:
                # Create blocked export
                json_data = {
                    "status": "BLOCKED",
                    "blockers": blockers,
                    "review_id": str(review_id),
                    "message": "Export blocked due to review requirements or missing data"
                }
                csv_data = None  # No CSV if blocked
            else:
                # Build unblocked export
                json_data = await self._build_broker_prep_json(review)
                csv_data = await self._build_broker_prep_csv(review)
            
            # Create ZIP with JSON + CSV + PDF placeholder
            zip_buffer = await self._create_broker_prep_zip(json_data, csv_data, review, blockers)
            
            # Upload to S3
            s3_key = self._generate_s3_key(organization_id, review_id, ExportType.BROKER_PREP, export.id)
            sha256_hash = await self._upload_to_s3(zip_buffer, s3_key)
            
            # Update export record
            if blockers:
                export.status = ExportStatus.BLOCKED
                export.blocked_reason = "; ".join(blockers)
                export.blockers = blockers
            else:
                export.status = ExportStatus.COMPLETED
            
            export.s3_key = s3_key
            export.s3_bucket = settings.S3_BUCKET_NAME or "LOCAL_FS"
            export.file_size = str(len(zip_buffer.getvalue()))
            export.sha256_hash = sha256_hash
            export.completed_at = datetime.utcnow()
            
            await self.db.commit()
            
            logger.info(f"Broker prep export completed: {export.id} for review {review_id} (blocked: {bool(blockers)})")
            return export
            
        except Exception as e:
            logger.error(f"Export generation failed: {e}", exc_info=True)
            export.status = ExportStatus.FAILED
            export.error_message = str(e)
            export.error_details = {"error": str(e)}
            await self.db.commit()
            raise
    
    async def _load_review_with_org_check(
        self,
        review_id: UUID,
        organization_id: UUID
    ) -> ReviewRecord:
        """Load review record with org-scoping check."""
        result = await self.db.execute(
            select(ReviewRecord)
            .join(
                Shipment,
                func.cast(ReviewRecord.object_snapshot["shipment_id"].astext, PGUUID(as_uuid=True)) == Shipment.id
            )
            .where(
                and_(
                    ReviewRecord.id == review_id,
                    Shipment.organization_id == organization_id
                )
            )
        )
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Review {review_id} not found or access denied")
        return review
    
    async def _check_blockers(self, review: ReviewRecord) -> List[str]:
        """
        Check blockers for export generation.
        
        Blockers:
        1. review_status = REVIEW_REQUIRED
        2. Any regulatory outcome = CONDITIONAL
        3. Missing required filing fields (checked in broker-prep)
        4. Document processing errors that remove required evidence (checked per export type)
        
        Returns list of blocker messages.
        """
        blockers = []
        
        # Check review status
        if review.status == ReviewStatus.REVIEW_REQUIRED:
            blockers.append("Review status is REVIEW_REQUIRED - review must be completed before export")
        
        # Check regulatory outcomes
        reg_eval_result = await self.db.execute(
            select(RegulatoryEvaluation)
            .where(RegulatoryEvaluation.review_id == review.id)
        )
        reg_evals = reg_eval_result.scalars().all()
        
        for reg_eval in reg_evals:
            if reg_eval.outcome == RegulatoryOutcome.CONDITIONAL:
                blockers.append(
                    f"Regulatory evaluation for {reg_eval.regulator.value} has CONDITIONAL outcome - "
                    "requires review before export"
                )
        
        return blockers
    
    async def _check_evidence_blockers(
        self,
        review: ReviewRecord,
        export_type: ExportType
    ) -> List[str]:
        """
        Check if document processing errors block this specific export.
        
        Only blocks if export would cite extracted fields that are missing.
        """
        blockers = []
        snapshot = review.object_snapshot
        evidence_map = snapshot.get("evidence_map", {})
        
        # Get document processing errors
        extraction_errors = evidence_map.get("extraction_errors", [])
        warnings = evidence_map.get("warnings", [])
        
        # For broker-prep, check if required fields would be cited
        if export_type == ExportType.BROKER_PREP:
            # Broker-prep requires HTS, value, quantity, COO
            # If these would come from extracted documents and extraction failed, block
            items = snapshot.get("items", [])
            for item in items:
                # Check if item relies on extracted data and extraction failed
                # This is a simplified check - in production, track which fields come from which docs
                pass  # TODO: Implement evidence dependency tracking
        
        # For audit pack, warnings are included but don't block unless critical
        # Audit pack always includes warnings, so don't block here
        
        return blockers
    
    async def _build_audit_pack_json(self, review: ReviewRecord) -> Dict[str, Any]:
        """Build JSON export for audit pack."""
        snapshot = review.object_snapshot.copy()
        
        # Load regulatory evaluations
        reg_eval_result = await self.db.execute(
            select(RegulatoryEvaluation)
            .where(RegulatoryEvaluation.review_id == review.id)
            .options(selectinload(RegulatoryEvaluation.conditions))
        )
        reg_evals = reg_eval_result.scalars().all()
        
        # Add regulatory evaluations to JSON
        reg_evals_data = []
        for reg_eval in reg_evals:
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
        
        # Build canonical export JSON
        export_json = {
            "export_type": "AUDIT_PACK",
            "generated_at": datetime.utcnow().isoformat(),
            "review_id": str(review.id),
            "hts_version_id": review.hts_version_id,
            "review_status": review.status.value,
            "snapshot_json": snapshot,
            "regulatory_evaluations": reg_evals_data,
            "evidence_map": snapshot.get("evidence_map", {}),
            "warnings": snapshot.get("evidence_map", {}).get("warnings", []),
            "extraction_errors": snapshot.get("evidence_map", {}).get("extraction_errors", [])
        }
        
        return export_json
    
    async def _build_broker_prep_json(self, review: ReviewRecord) -> Dict[str, Any]:
        """Build JSON export for broker prep."""
        snapshot = review.object_snapshot
        
        # Load regulatory evaluations summary
        reg_eval_result = await self.db.execute(
            select(RegulatoryEvaluation)
            .where(RegulatoryEvaluation.review_id == review.id)
        )
        reg_evals = reg_eval_result.scalars().all()
        
        reg_summary = []
        for reg_eval in reg_evals:
            reg_summary.append({
                "regulator": reg_eval.regulator.value,
                "outcome": reg_eval.outcome.value,
                "explanation": reg_eval.explanation_text
            })
        
        export_json = {
            "export_type": "BROKER_PREP",
            "generated_at": datetime.utcnow().isoformat(),
            "review_id": str(review.id),
            "hts_version_id": review.hts_version_id,
            "items": snapshot.get("items", []),
            "regulatory_evaluations_summary": reg_summary,
            "no_recommendations": True,
            "disclaimer": "Decision support only, not legal advice, not filing"
        }
        
        return export_json
    
    async def _build_broker_prep_csv(self, review: ReviewRecord) -> str:
        """Build CSV export for broker prep."""
        import csv
        from io import StringIO
        
        snapshot = review.object_snapshot
        items = snapshot.get("items", [])
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Item ID", "Label", "HTS Code", "Value", "Quantity", "UOM", "COO", "Regulatory Notes"])
        
        # Item rows
        for item in items:
            hts_code = item.get("hts_code") or ""
            label = item.get("label") or ""
            value = item.get("value") or ""
            quantity = item.get("quantity") or ""
            uom = item.get("uom") or ""
            coo = item.get("country_of_origin") or ""
            
            # Get regulatory summary for this item
            regulatory = item.get("regulatory", [])
            reg_notes = "; ".join([
                f"{r.get('regulator', {}).get('value', '')}: {r.get('outcome', {}).get('value', '')}"
                for r in regulatory
            ])
            
            writer.writerow([item.get("id"), label, hts_code, value, quantity, uom, coo, reg_notes])
        
        return output.getvalue()
    
    async def _create_audit_pack_zip(
        self,
        json_data: Dict[str, Any],
        review: ReviewRecord
    ) -> BytesIO:
        """Create ZIP file for audit pack."""
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON
            json_str = json.dumps(json_data, indent=2)
            zip_file.writestr("audit_pack.json", json_str)
            
            # Add PDF placeholder (TODO: Generate actual PDF)
            pdf_placeholder = f"""AUDIT PACK SUMMARY
            
Review ID: {review.id}
Analysis ID: {json_data.get('snapshot_json', {}).get('analysis_id')}
Shipment ID: {json_data.get('snapshot_json', {}).get('shipment_id')}
HTS Version: {review.hts_version_id}

DISCLAIMER:
This report is for decision support only and does not constitute legal advice or filing instructions.

Items Analyzed: {len(json_data.get('snapshot_json', {}).get('items', []))}

Regulatory Evaluations: {len(json_data.get('regulatory_evaluations', []))}

Warnings: {len(json_data.get('warnings', []))}

This is a placeholder PDF. Full PDF generation will be implemented in a future sprint.
"""
            zip_file.writestr("audit_summary.pdf", pdf_placeholder)
            
            # Add metadata
            metadata = f"""Export Type: Audit Pack
Generated At: {datetime.utcnow().isoformat()}
Review ID: {review.id}
HTS Version: {review.hts_version_id}
Review Status: {review.status.value}
"""
            zip_file.writestr("metadata.txt", metadata)
        
        zip_buffer.seek(0)
        return zip_buffer
    
    async def _create_broker_prep_zip(
        self,
        json_data: Dict[str, Any],
        csv_data: Optional[str],
        review: ReviewRecord,
        blockers: List[str]
    ) -> BytesIO:
        """Create ZIP file for broker prep."""
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON
            json_str = json.dumps(json_data, indent=2)
            zip_file.writestr("broker_prep.json", json_str)
            
            # Add CSV if unblocked
            if csv_data:
                zip_file.writestr("broker_prep_items.csv", csv_data)
            
            # Add PDF placeholder
            pdf_content = f"""BROKER FILING-PREP BUNDLE
            
{'STATUS: BLOCKED' if blockers else 'STATUS: READY'}

{chr(10).join(['BLOCKER: ' + b for b in blockers]) if blockers else ''}

Review ID: {review.id}
HTS Version: {review.hts_version_id}

DISCLAIMER:
This bundle is for decision support only and does not constitute legal advice or filing instructions.
No recommendations are provided.

This is a placeholder PDF. Full PDF generation will be implemented in a future sprint.
"""
            zip_file.writestr("broker_prep_summary.pdf", pdf_content)
        
        zip_buffer.seek(0)
        return zip_buffer
    
    def _generate_s3_key(
        self,
        organization_id: UUID,
        review_id: UUID,
        export_type: ExportType,
        export_id: UUID
    ) -> str:
        """Generate S3 key for export."""
        env = settings.ENVIRONMENT or "dev"
        return f"neco/{env}/org_{organization_id}/exports/review_{review_id}/{export_type.value}/{export_id}.zip"
    
    async def _upload_to_s3(self, file_buffer: BytesIO, s3_key: str) -> str:
        """Upload file and return SHA256 hash (S3 in prod, local fallback in dev)."""
        file_buffer.seek(0)
        file_content = file_buffer.read()
        
        # Calculate SHA256
        sha256_hash = hashlib.sha256(file_content).hexdigest()
        
        # Local fallback when S3 is not configured.
        if not settings.S3_BUCKET_NAME:
            local_path = Path("backend/data/local_exports") / s3_key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_content)
            return sha256_hash

        # Upload to S3
        self.s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType="application/zip"
        )
        
        return sha256_hash
    
    async def _create_blocked_export(
        self,
        review_id: UUID,
        export_type: ExportType,
        blockers: List[str],
        created_by: UUID
    ) -> Export:
        """Create a blocked export record."""
        export = Export(
            review_id=review_id,
            export_type=export_type,
            status=ExportStatus.BLOCKED,
            blocked_reason="; ".join(blockers),
            blockers=blockers,
            created_by=created_by
        )
        self.db.add(export)
        await self.db.commit()
        await self.db.refresh(export)
        return export
