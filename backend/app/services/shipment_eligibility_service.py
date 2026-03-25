"""
Shipment Eligibility Service - Sprint 12

Centralized eligibility computation:
- Eligible if Entry Summary present OR (CI + Data Sheet present)
- Returns missing requirements
- Used in: shipment detail, analyze gate, UI readiness indicator
"""

from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import joinedload

from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.models.analysis import Analysis, AnalysisStatus

# Eligibility requirements
REQUIRED_FOR_ENTRY_SUMMARY_PATH = [ShipmentDocumentType.ENTRY_SUMMARY]
REQUIRED_FOR_COMMERCIAL_INVOICE_PATH = [ShipmentDocumentType.COMMERCIAL_INVOICE, ShipmentDocumentType.DATA_SHEET]


class ShipmentEligibilityService:
    """Service for computing shipment eligibility for analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _pending_classification_inputs(self, shipment_id: UUID) -> List[str]:
        """
        If the latest completed analysis still has open classification clarifications,
        block a fresh run until the user supplies answers (re-run with clarification payload).
        """
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.shipment_id == shipment_id)
            .order_by(desc(Analysis.created_at))
            .limit(1)
        )
        analysis = result.scalar_one_or_none()
        if not analysis or analysis.status != AnalysisStatus.COMPLETE or not analysis.result_json:
            return []
        msgs: List[str] = []
        for it in analysis.result_json.get("items") or []:
            cl = it.get("classification") or {}
            if not isinstance(cl, dict):
                continue
            label = it.get("label") or it.get("id")
            if cl.get("status") == "CLARIFICATION_REQUIRED":
                msgs.append(
                    f'Resolve classification clarifications for "{label}" (previous run) before starting analysis again.'
                )
                continue
            qs = cl.get("questions") or []
            if qs:
                msgs.append(
                    f'Open classification questions remain for "{label}"; re-run analysis with clarification answers.'
                )
        return msgs
    
    async def compute_eligibility(
        self,
        shipment_id: UUID
    ) -> Dict[str, Any]:
        """
        Compute eligibility for shipment analysis.
        
        Eligible if:
        - Pre-Compliance shipments: at least one document uploaded (advisory analysis allowed)
        - Entry-Compliance shipments: Entry Summary present OR (Commercial Invoice + Data Sheet) present
        
        Args:
            shipment_id: Shipment ID
        
        Returns:
            {
                "eligible": bool,
                "missing_requirements": List[str],
                "satisfied_path": str | None  # "ENTRY_SUMMARY" or "COMMERCIAL_INVOICE_DATA_SHEET"
            }
        """
        # Get shipment with documents
        result = await self.db.execute(
            select(Shipment)
            .options(
                joinedload(Shipment.documents),
                joinedload(Shipment.references),
                joinedload(Shipment.items),
            )
            .where(Shipment.id == shipment_id)
        )
        shipment = result.unique().scalar_one_or_none()
        
        if not shipment:
            return {
                "eligible": False,
                "missing_requirements": ["Shipment not found"],
                "satisfied_path": None
            }
        
        # Get document types present
        doc_types = {doc.document_type for doc in shipment.documents}
        ref_map = {str(ref.reference_type).upper(): str(ref.reference_value).upper() for ref in (shipment.references or [])}
        shipment_type = ref_map.get("SHIPMENT_TYPE", "PRE_COMPLIANCE")
        is_pre_compliance = shipment_type != "ENTRY_COMPLIANCE"

        if is_pre_compliance:
            if len(doc_types) > 0:
                missing_coo_items = [
                    item.label or f"Line item {idx + 1}"
                    for idx, item in enumerate(shipment.items or [])
                    if not (item.country_of_origin and str(item.country_of_origin).strip())
                ]
                if missing_coo_items:
                    preview = ", ".join(missing_coo_items[:3])
                    if len(missing_coo_items) > 3:
                        preview += f" (+{len(missing_coo_items) - 3} more)"
                    return {
                        "eligible": False,
                        "missing_requirements": [
                            "Country of Origin is required for all pre-compliance line items before analysis can run",
                            f"Missing COO: {preview}",
                        ],
                        "satisfied_path": None,
                    }
                pending = await self._pending_classification_inputs(shipment_id)
                if pending:
                    return {
                        "eligible": False,
                        "missing_requirements": pending,
                        "satisfied_path": None,
                    }
                return {
                    "eligible": True,
                    "missing_requirements": [],
                    "satisfied_path": "PRE_COMPLIANCE_DOCUMENTS"
                }
            return {
                "eligible": False,
                "missing_requirements": ["Upload at least one document to start pre-compliance analysis"],
                "satisfied_path": None
            }
        
        # Check Entry Summary path
        has_entry_summary = ShipmentDocumentType.ENTRY_SUMMARY in doc_types
        
        if has_entry_summary:
            pending = await self._pending_classification_inputs(shipment_id)
            if pending:
                return {
                    "eligible": False,
                    "missing_requirements": pending,
                    "satisfied_path": None,
                }
            return {
                "eligible": True,
                "missing_requirements": [],
                "satisfied_path": "ENTRY_SUMMARY"
            }
        
        # Check Commercial Invoice + Data Sheet path
        has_commercial_invoice = ShipmentDocumentType.COMMERCIAL_INVOICE in doc_types
        has_data_sheet = ShipmentDocumentType.DATA_SHEET in doc_types
        
        if has_commercial_invoice and has_data_sheet:
            pending = await self._pending_classification_inputs(shipment_id)
            if pending:
                return {
                    "eligible": False,
                    "missing_requirements": pending,
                    "satisfied_path": None,
                }
            return {
                "eligible": True,
                "missing_requirements": [],
                "satisfied_path": "COMMERCIAL_INVOICE_DATA_SHEET"
            }
        
        # Not eligible - determine missing requirements
        missing_requirements = []
        
        if not has_entry_summary and not (has_commercial_invoice and has_data_sheet):
            # Neither path satisfied
            missing_requirements.append("Entry Summary document required OR (Commercial Invoice + Data Sheet) required")
        
        if has_commercial_invoice and not has_data_sheet:
            missing_requirements.append("Data Sheet document required (Commercial Invoice present)")
        
        if has_data_sheet and not has_commercial_invoice:
            missing_requirements.append("Commercial Invoice document required (Data Sheet present)")
        
        if not has_commercial_invoice and not has_data_sheet and not has_entry_summary:
            missing_requirements.append("Entry Summary document required OR (Commercial Invoice + Data Sheet) required")
        
        return {
            "eligible": False,
            "missing_requirements": missing_requirements,
            "satisfied_path": None
        }
    
    async def get_missing_requirements(
        self,
        shipment_id: UUID
    ) -> List[str]:
        """
        Get missing requirements for shipment eligibility.
        
        Args:
            shipment_id: Shipment ID
        
        Returns:
            List of missing requirement messages
        """
        eligibility = await self.compute_eligibility(shipment_id)
        return eligibility["missing_requirements"]

