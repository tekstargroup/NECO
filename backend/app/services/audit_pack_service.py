"""
Audit Pack Generator - Sprint 8

Critical feature: Generate complete audit packs for compliance.

Key principles:
- Complete (all inputs, outputs, reviews, overrides)
- Deterministic (same inputs = same pack)
- Exportable (JSON canonical, PDF human-readable, ZIP bundle)
- No formatting beauty - clarity only
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.review_record import ReviewRecord
from app.services.audit_replay_service import AuditReplayService
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID

logger = logging.getLogger(__name__)


class AuditPackService:
    """Service for generating audit packs."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_replay_service = AuditReplayService(db)
    
    async def generate_audit_pack(
        self,
        review_ids: Optional[List[UUID]] = None,
        time_range_start: Optional[datetime] = None,
        time_range_end: Optional[datetime] = None,
        include_audit_replay: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete audit pack.
        
        Args:
            review_ids: Specific review IDs to include (optional)
            time_range_start: Start of time range (optional)
            time_range_end: End of time range (optional)
            include_audit_replay: Whether to include audit replay results
        
        Returns:
            Dictionary with complete audit pack data
        """
        # Collect review records
        records = []
        
        if review_ids:
            # Fetch specific records
            for rid in review_ids:
                result = await self.db.execute(
                    select(ReviewRecord).where(ReviewRecord.id == rid)
                )
                record = result.scalar_one_or_none()
                if record:
                    records.append(record)
        else:
            # Fetch by time range
            filters = []
            if time_range_start:
                filters.append(ReviewRecord.created_at >= time_range_start)
            if time_range_end:
                filters.append(ReviewRecord.created_at <= time_range_end)
            
            if filters:
                query = select(ReviewRecord).where(and_(*filters))
            else:
                query = select(ReviewRecord)
            
            result = await self.db.execute(query)
            records = list(result.scalars().all())
        
        # Build audit pack
        pack = {
            "audit_pack_version": "1.0",
            "generated_at": datetime.utcnow().isoformat(),
            "hts_version_id": AUTHORITATIVE_HTS_VERSION_ID,
            "disclaimer": self._get_disclaimer(),
            "summary": {
                "total_records": len(records),
                "time_range": {
                    "start": time_range_start.isoformat() if time_range_start else None,
                    "end": time_range_end.isoformat() if time_range_end else None
                },
                "review_ids": [str(rid) for rid in review_ids] if review_ids else None
            },
            "review_records": [],
            "audit_replay_results": []
        }
        
        # Include review records with full snapshots
        for record in records:
            record_data = {
                "review_id": str(record.id),
                "object_type": record.object_type.value,
                "status": record.status.value,
                "hts_version_id": record.hts_version_id,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "created_by": record.created_by,
                "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
                "reviewed_by": record.reviewed_by,
                "review_reason_code": record.review_reason_code.value if record.review_reason_code else None,
                "review_notes": record.review_notes,
                "override_of_review_id": str(record.override_of_review_id) if record.override_of_review_id else None,
                "object_snapshot": record.object_snapshot
            }
            pack["review_records"].append(record_data)
            
            # Include audit replay if requested
            if include_audit_replay:
                replay_result = await self.audit_replay_service.verify_review_record(record.id)
                pack["audit_replay_results"].append({
                    "review_id": str(record.id),
                    "replay_result": replay_result.to_dict()
                })
        
        return pack
    
    def _get_disclaimer(self) -> str:
        """Get disclaimer text for audit pack."""
        return (
            "AUDIT PACK DISCLAIMER\n\n"
            "This audit pack contains a complete snapshot of classification and PSC Radar "
            "decisions for the specified time period or review records.\n\n"
            "Contents:\n"
            "- Inputs: Product descriptions, HTS codes, values, quantities\n"
            "- Outputs: Classification results, PSC Radar signals, duty resolutions\n"
            "- Review Records: All review decisions, acceptances, rejections, overrides\n"
            "- Audit Replay: Verification that stored outputs match current resolver logic\n\n"
            "This pack is generated for compliance and audit purposes only.\n"
            "NECO does not provide legal advice or filing recommendations.\n\n"
            f"HTS Version: {AUTHORITATIVE_HTS_VERSION_ID}\n"
            f"Generated: {datetime.utcnow().isoformat()}"
        )
    
    def export_json(self, audit_pack: Dict[str, Any]) -> str:
        """Export audit pack as JSON (canonical format)."""
        return json.dumps(audit_pack, indent=2, default=str)
    
    def export_pdf(self, audit_pack: Dict[str, Any]) -> str:
        """
        Export audit pack as PDF (human-readable, simple).
        
        Note: This is a simplified text-based PDF. For production, use a PDF library.
        """
        lines = []
        lines.append("=" * 80)
        lines.append("NECO AUDIT PACK")
        lines.append("=" * 80)
        lines.append("")
        lines.append(audit_pack["disclaimer"])
        lines.append("")
        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Total Records: {audit_pack['summary']['total_records']}")
        lines.append(f"Generated: {audit_pack['generated_at']}")
        lines.append(f"HTS Version: {audit_pack['hts_version_id']}")
        lines.append("")
        
        for record in audit_pack["review_records"]:
            lines.append("-" * 80)
            lines.append(f"Review ID: {record['review_id']}")
            lines.append(f"Object Type: {record['object_type']}")
            lines.append(f"Status: {record['status']}")
            lines.append(f"Created: {record['created_at']} by {record['created_by']}")
            if record['reviewed_at']:
                lines.append(f"Reviewed: {record['reviewed_at']} by {record['reviewed_by']}")
            if record['review_notes']:
                lines.append(f"Notes: {record['review_notes']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def export_zip(self, audit_pack: Dict[str, Any]) -> bytes:
        """
        Export audit pack as ZIP bundle.
        
        Includes:
        - audit_pack.json (canonical)
        - audit_pack.txt (human-readable)
        - README.txt (instructions)
        
        Returns:
            ZIP file as bytes
        """
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON
            json_content = self.export_json(audit_pack)
            zip_file.writestr("audit_pack.json", json_content)
            
            # Add text/PDF
            txt_content = self.export_pdf(audit_pack)
            zip_file.writestr("audit_pack.txt", txt_content)
            
            # Add README
            readme = (
                "NECO AUDIT PACK\n\n"
                "This ZIP bundle contains:\n"
                "- audit_pack.json: Complete audit pack in JSON format (canonical)\n"
                "- audit_pack.txt: Human-readable text version\n"
                "- README.txt: This file\n\n"
                "The JSON file is the authoritative source. Use it for programmatic access.\n"
                "The text file is for human review.\n\n"
                f"Generated: {audit_pack['generated_at']}\n"
                f"HTS Version: {audit_pack['hts_version_id']}"
            )
            zip_file.writestr("README.txt", readme)
        
        zip_buffer.seek(0)
        return zip_buffer.read()
