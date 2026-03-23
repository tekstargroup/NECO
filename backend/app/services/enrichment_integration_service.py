"""
Enrichment Integration Service - Sprint 10

Non-invasive integration hooks for enrichment into existing systems.

Key principles:
- Non-invasive (does not modify existing logic)
- Only populates if unambiguous
- Maintains blockers if enrichment is ambiguous
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment_bundle import EnrichmentBundle
from app.models.filing_prep_bundle import FilingPrepBundle
from app.services.filing_prep_service import FilingPrepService

logger = logging.getLogger(__name__)


class EnrichmentIntegrationService:
    """Service for integrating enrichment into existing systems."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def enrich_classification_input(
        self,
        enrichment_bundle: EnrichmentBundle,
        base_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich classification input with extracted fields.
        
        Adds extracted fields as additional evidence.
        Does not modify base input structure.
        """
        enriched = base_input.copy()
        
        # Add enrichment evidence
        enriched["enrichment_evidence"] = {
            "document_id": enrichment_bundle.document_id,
            "document_type": enrichment_bundle.document_type.value,
            "extracted_fields": [f.to_dict() for f in enrichment_bundle.extracted_fields],
            "line_items": [li.to_dict() for li in enrichment_bundle.line_items]
        }
        
        # Add product description if extracted and unambiguous
        description_field = enrichment_bundle.get_field("item_description")
        if description_field and enrichment_bundle.is_unambiguous("item_description"):
            if "product_description" not in enriched or not enriched["product_description"]:
                enriched["product_description"] = description_field.value
        
        return enriched
    
    def enrich_psc_radar_input(
        self,
        enrichment_bundle: EnrichmentBundle,
        base_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich PSC Radar input with extracted fields.
        
        Adds extracted fields as additional evidence.
        """
        enriched = base_input.copy()
        
        # Add enrichment evidence
        enriched["enrichment_evidence"] = {
            "document_id": enrichment_bundle.document_id,
            "document_type": enrichment_bundle.document_type.value,
            "extracted_fields": [f.to_dict() for f in enrichment_bundle.extracted_fields]
        }
        
        # Add country of origin if unambiguous
        coo_field = enrichment_bundle.get_field("country_of_origin")
        if coo_field and enrichment_bundle.is_unambiguous("country_of_origin"):
            enriched["country_of_origin"] = coo_field.value
        
        return enriched
    
    async def enrich_filing_prep_bundle(
        self,
        enrichment_bundle: EnrichmentBundle,
        filing_prep_service: FilingPrepService,
        declared_hts_code: str,
        review_id: Optional[str] = None
    ) -> FilingPrepBundle:
        """
        Enrich filing prep bundle with extracted fields.
        
        Only populates if unambiguous.
        Maintains blockers if enrichment is ambiguous.
        """
        # Extract unambiguous values
        quantity = None
        customs_value = None
        unit_of_measure = None
        country_of_origin = None
        
        # Get quantity (only if unambiguous)
        if enrichment_bundle.total_quantity is not None:
            quantity = enrichment_bundle.total_quantity
        elif enrichment_bundle.line_items:
            # Check if all line items have same quantity
            quantities = [li.quantity for li in enrichment_bundle.line_items if li.quantity is not None]
            if len(set(quantities)) == 1:
                quantity = quantities[0]
        
        # Get value (only if unambiguous)
        value_field = enrichment_bundle.get_field("total_value")
        if value_field and enrichment_bundle.is_unambiguous("total_value"):
            customs_value = value_field.value
        
        # Get UOM (only if unambiguous)
        if enrichment_bundle.line_items:
            uoms = [li.unit_of_measure for li in enrichment_bundle.line_items if li.unit_of_measure is not None]
            if len(set(uoms)) == 1:
                unit_of_measure = uoms[0]
        
        # Get country of origin (only if unambiguous and no conflicts)
        coo_field = enrichment_bundle.get_field("country_of_origin")
        if coo_field and enrichment_bundle.is_unambiguous("country_of_origin"):
            country_of_origin = coo_field.value
        
        # Create filing prep bundle (will still validate and set blockers)
        bundle = await filing_prep_service.create_filing_prep_bundle(
            declared_hts_code=declared_hts_code,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            customs_value=customs_value,
            country_of_origin=country_of_origin,
            review_id=review_id
        )
        
        # Add enrichment metadata
        bundle.broker_notes["enrichment_source"] = {
            "document_id": enrichment_bundle.document_id,
            "document_type": enrichment_bundle.document_type.value,
            "extracted_at": enrichment_bundle.extracted_at.isoformat()
        }
        
        # Note if enrichment was ambiguous
        if enrichment_bundle.conflicts:
            bundle.broker_notes["enrichment_warnings"] = [
                f"Conflict in {c['field']}: {c['values']}" for c in enrichment_bundle.conflicts
            ]
        
        return bundle
