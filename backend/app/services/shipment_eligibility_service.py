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
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from app.models.shipment import Shipment
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType

# Eligibility requirements
REQUIRED_FOR_ENTRY_SUMMARY_PATH = [ShipmentDocumentType.ENTRY_SUMMARY]
REQUIRED_FOR_COMMERCIAL_INVOICE_PATH = [ShipmentDocumentType.COMMERCIAL_INVOICE, ShipmentDocumentType.DATA_SHEET]


class ShipmentEligibilityService:
    """Service for computing shipment eligibility for analysis"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def compute_eligibility(
        self,
        shipment_id: UUID
    ) -> Dict[str, Any]:
        """
        Compute eligibility for shipment analysis.
        
        Eligible if:
        - Entry Summary present, OR
        - (Commercial Invoice + Data Sheet) present
        
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
            .options(joinedload(Shipment.documents))
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
        
        # Check Entry Summary path
        has_entry_summary = ShipmentDocumentType.ENTRY_SUMMARY in doc_types
        
        if has_entry_summary:
            return {
                "eligible": True,
                "missing_requirements": [],
                "satisfied_path": "ENTRY_SUMMARY"
            }
        
        # Check Commercial Invoice + Data Sheet path
        has_commercial_invoice = ShipmentDocumentType.COMMERCIAL_INVOICE in doc_types
        has_data_sheet = ShipmentDocumentType.DATA_SHEET in doc_types
        
        if has_commercial_invoice and has_data_sheet:
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

