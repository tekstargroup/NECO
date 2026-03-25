"""
Broker Export Service - Sprint 9

Export generators for broker handoff.

Formats:
- JSON (canonical)
- CSV (broker-friendly)
- PDF summary (human-readable)

Key principles:
- Clarity over beauty
- Disclaimers always present
- No styling beyond readability
"""

import logging
import json
import csv
import io
from typing import Dict, Any
from datetime import datetime

from app.models.filing_prep_bundle import FilingPrepBundle, ExportBlockReason

logger = logging.getLogger(__name__)


class BrokerExportService:
    """Service for generating broker exports."""
    
    def export_json(self, bundle: FilingPrepBundle) -> str:
        """
        Export as JSON (canonical format).
        
        Returns:
            JSON string
        """
        data = bundle.to_dict()
        data["export_provenance"] = {
            "exported_at": datetime.utcnow().isoformat(),
        }
        return json.dumps(data, indent=2, default=str)
    
    def export_csv(self, bundle: FilingPrepBundle) -> str:
        """
        Export as CSV (broker-friendly format).
        
        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Field", "Value"
        ])
        
        # Data rows
        writer.writerow(["Declared HTS Code", bundle.declared_hts_code])
        writer.writerow(["General Duty", bundle.duty_breakdown.general_duty or ""])
        writer.writerow(["Special Duty", bundle.duty_breakdown.special_duty or ""])
        writer.writerow(["Column 2 Duty", bundle.duty_breakdown.column2_duty or ""])
        writer.writerow(["Quantity", bundle.quantity or ""])
        writer.writerow(["Unit of Measure", bundle.unit_of_measure or ""])
        writer.writerow(["Customs Value", bundle.customs_value or ""])
        writer.writerow(["Country of Origin", bundle.country_of_origin or ""])
        writer.writerow(["Review Status", bundle.review_status.value])
        writer.writerow(["PSC Flags", ", ".join(bundle.psc_flags) if bundle.psc_flags else ""])
        writer.writerow(["HTS Version ID", bundle.hts_version_id])
        writer.writerow(["Export Blocked", "YES" if bundle.export_blocked else "NO"])
        writer.writerow(["Export Block Reasons", ", ".join([r.value for r in bundle.export_block_reasons]) if bundle.export_block_reasons else ""])
        
        # Disclaimers
        writer.writerow([])
        writer.writerow(["DISCLAIMERS"])
        for disclaimer in bundle.disclaimers:
            writer.writerow(["", disclaimer])
        
        # Broker notes
        if bundle.broker_notes:
            writer.writerow([])
            writer.writerow(["BROKER NOTES"])
            for section, items in bundle.broker_notes.items():
                if items:
                    writer.writerow([section.replace("_", " ").title(), ""])
                    for item in items:
                        writer.writerow(["", item])
        
        return output.getvalue()
    
    def export_pdf_summary(self, bundle: FilingPrepBundle) -> str:
        """
        Export as PDF summary (human-readable, simple text format).
        
        Note: This is a simplified text-based format. For production, use a PDF library.
        
        Returns:
            Text content (can be converted to PDF)
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("NECO FILING PREP SUMMARY")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}")
        lines.append("")
        
        # Export status
        if bundle.export_blocked:
            lines.append("⚠️  EXPORT BLOCKED")
            lines.append("")
            for reason in bundle.export_block_reasons:
                lines.append(f"  Block Reason: {reason.value}")
            lines.append("")
            lines.append("This export is blocked and should not be used for filing.")
            lines.append("")
        else:
            lines.append("✓ Export Ready (Broker Review Still Required)")
            lines.append("")
        
        # HTS Code and Duties
        lines.append("-" * 80)
        lines.append("CLASSIFICATION & DUTIES")
        lines.append("-" * 80)
        lines.append(f"Declared HTS Code: {bundle.declared_hts_code}")
        lines.append(f"General Duty: {bundle.duty_breakdown.general_duty or 'Not available'}")
        lines.append(f"Special Duty: {bundle.duty_breakdown.special_duty or 'Not available'}")
        lines.append(f"Column 2 Duty: {bundle.duty_breakdown.column2_duty or 'Not available'}")
        lines.append(f"HTS Version: {bundle.hts_version_id}")
        lines.append("")
        
        # Quantity and Value
        lines.append("-" * 80)
        lines.append("QUANTITY & VALUE")
        lines.append("-" * 80)
        lines.append(f"Quantity: {bundle.quantity or 'Not provided'}")
        lines.append(f"Unit of Measure: {bundle.unit_of_measure or 'Not provided'}")
        lines.append(f"Customs Value: ${bundle.customs_value:,.2f}" if bundle.customs_value else "Customs Value: Not provided")
        lines.append(f"Country of Origin: {bundle.country_of_origin or 'Not provided'}")
        lines.append("")
        
        # Review Status
        lines.append("-" * 80)
        lines.append("REVIEW STATUS")
        lines.append("-" * 80)
        lines.append(f"Status: {bundle.review_status.value}")
        if bundle.reviewed_by:
            lines.append(f"Reviewed By: {bundle.reviewed_by}")
        if bundle.reviewed_at:
            lines.append(f"Reviewed At: {bundle.reviewed_at.isoformat()}")
        if bundle.review_notes:
            lines.append(f"Review Notes: {bundle.review_notes}")
        if bundle.is_override:
            lines.append("⚠️  This is an override of a previous classification")
            if bundle.override_justification:
                lines.append(f"Override Justification: {bundle.override_justification}")
        lines.append("")
        
        # PSC Flags
        if bundle.psc_flags:
            lines.append("-" * 80)
            lines.append("PSC RADAR FLAGS")
            lines.append("-" * 80)
            for flag in bundle.psc_flags:
                lines.append(f"  • {flag}")
            lines.append("")
        
        # Broker Notes
        if bundle.broker_notes:
            lines.append("-" * 80)
            lines.append("BROKER NOTES")
            lines.append("-" * 80)
            
            if bundle.broker_notes.get("what_was_reviewed"):
                lines.append("What Was Reviewed:")
                for item in bundle.broker_notes["what_was_reviewed"]:
                    lines.append(f"  • {item}")
                lines.append("")
            
            if bundle.broker_notes.get("what_was_overridden"):
                lines.append("What Was Overridden:")
                for item in bundle.broker_notes["what_was_overridden"]:
                    lines.append(f"  • {item}")
                lines.append("")
            
            if bundle.broker_notes.get("what_risks_were_flagged"):
                lines.append("What Risks Were Flagged:")
                for item in bundle.broker_notes["what_risks_were_flagged"]:
                    lines.append(f"  • {item}")
                lines.append("")
            
            if bundle.broker_notes.get("what_neco_did_not_evaluate"):
                lines.append("What NECO Did NOT Evaluate:")
                for item in bundle.broker_notes["what_neco_did_not_evaluate"]:
                    lines.append(f"  • {item}")
                lines.append("")
        
        # Disclaimers
        lines.append("=" * 80)
        lines.append("DISCLAIMERS")
        lines.append("=" * 80)
        for disclaimer in bundle.disclaimers:
            lines.append(disclaimer)
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF FILING PREP SUMMARY")
        lines.append("=" * 80)
        
        return "\n".join(lines)
