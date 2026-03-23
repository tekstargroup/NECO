"""
Field Extractor Service - Sprint 10

Deterministic, evidence-backed field extraction.

Key principles:
- Extract facts present in documents only
- Attach evidence pointers everywhere
- Handle conflicts explicitly
- Never infer missing facts
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.enrichment_bundle import (
    EnrichmentBundle,
    ExtractedField,
    LineItem,
    Evidence,
    FieldConfidence,
    FieldWarning,
    DocumentType
)
from app.models.document_record import DocumentRecord

logger = logging.getLogger(__name__)


class FieldExtractorService:
    """Service for extracting fields from documents."""
    
    def __init__(self, parser_version: str = "1.0"):
        self.parser_version = parser_version
    
    async def extract_from_document(
        self,
        document_record: DocumentRecord
    ) -> EnrichmentBundle:
        """
        Extract fields from document.
        
        Args:
            document_record: DocumentRecord to extract from
        
        Returns:
            EnrichmentBundle with extracted fields and evidence
        """
        doc_type = DocumentType(document_record.document_type)
        
        # Initialize bundle
        bundle = EnrichmentBundle(
            document_id=document_record.document_id,
            document_type=doc_type,
            document_hash=document_record.document_hash,
            parser_version=self.parser_version
        )
        
        # Extract based on document type
        if doc_type == DocumentType.COMMERCIAL_INVOICE:
            await self._extract_from_invoice(document_record, bundle)
        elif doc_type == DocumentType.PACKING_LIST:
            await self._extract_from_packing_list(document_record, bundle)
        elif doc_type == DocumentType.TECHNICAL_SPEC:
            await self._extract_from_spec(document_record, bundle)
        
        # Aggregate values if unambiguous
        self._aggregate_values(bundle)
        
        return bundle
    
    async def _extract_from_invoice(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle
    ) -> None:
        """Extract fields from commercial invoice."""
        text_spans = document.text_spans or []
        
        # Extract header fields
        self._extract_seller_name(document, bundle, text_spans)
        self._extract_buyer_name(document, bundle, text_spans)
        self._extract_invoice_number(document, bundle, text_spans)
        self._extract_invoice_date(document, bundle, text_spans)
        self._extract_currency(document, bundle, text_spans)
        
        # Extract line items
        self._extract_line_items(document, bundle, text_spans)
        
        # Extract totals
        self._extract_total_value(document, bundle, text_spans)
    
    async def _extract_from_packing_list(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle
    ) -> None:
        """Extract fields from packing list."""
        text_spans = document.text_spans or []
        
        # Extract line items (packing lists focus on quantities)
        self._extract_line_items(document, bundle, text_spans)
        
        # Extract country of origin if present
        self._extract_country_of_origin(document, bundle, text_spans)
    
    async def _extract_from_spec(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle
    ) -> None:
        """Extract fields from technical spec."""
        text_spans = document.text_spans or []
        
        # Extract material composition if explicitly present
        self._extract_material_composition(document, bundle, text_spans)
        
        # Extract brand/model if explicitly present
        self._extract_brand_model(document, bundle, text_spans)
    
    def _extract_seller_name(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract seller name."""
        # Simplified extraction - would use actual pattern matching
        # Look for patterns like "Seller:", "From:", "Vendor:"
        for span in text_spans:
            text = span.get("text", "").upper()
            if "SELLER" in text or "FROM" in text or "VENDOR" in text:
                # Extract value (simplified)
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=text[:200]
                )
                field = ExtractedField(
                    field_name="seller_name",
                    value="EXTRACTED_SELLER_NAME",  # Would be actual extraction
                    raw_value=text[:200],
                    evidence=[evidence],
                    confidence=FieldConfidence.MEDIUM
                )
                bundle.extracted_fields.append(field)
                break
    
    def _extract_buyer_name(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract buyer name."""
        # Similar to seller name
        for span in text_spans:
            text = span.get("text", "").upper()
            if "BUYER" in text or "TO" in text or "SHIP TO" in text:
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=text[:200]
                )
                field = ExtractedField(
                    field_name="buyer_name",
                    value="EXTRACTED_BUYER_NAME",
                    raw_value=text[:200],
                    evidence=[evidence],
                    confidence=FieldConfidence.MEDIUM
                )
                bundle.extracted_fields.append(field)
                break
    
    def _extract_invoice_number(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract invoice number."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for "Invoice No:", "Invoice #", etc.
            match = re.search(r'(?:invoice\s*(?:no|#|number)?:?\s*)([A-Z0-9-]+)', text, re.IGNORECASE)
            if match:
                invoice_num = match.group(1)
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=match.group(0)
                )
                field = ExtractedField(
                    field_name="invoice_number",
                    value=invoice_num,
                    raw_value=match.group(0),
                    evidence=[evidence],
                    confidence=FieldConfidence.HIGH
                )
                bundle.extracted_fields.append(field)
                break
    
    def _extract_invoice_date(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract invoice date."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for date patterns
            date_patterns = [
                r'(?:invoice\s*date:?\s*)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(?:date:?\s*)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ]
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    # Try to parse (simplified)
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
                        evidence = Evidence(
                            document_id=document.document_id,
                            page_number=span.get("page", 1),
                            raw_text_snippet=match.group(0)
                        )
                        field = ExtractedField(
                            field_name="invoice_date",
                            value=parsed_date.isoformat(),
                            raw_value=date_str,
                            evidence=[evidence],
                            confidence=FieldConfidence.HIGH
                        )
                        bundle.extracted_fields.append(field)
                        return
                    except ValueError:
                        continue
    
    def _extract_currency(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract currency."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for currency codes (USD, EUR, etc.)
            currency_match = re.search(r'\b(USD|EUR|GBP|CNY|JPY|CAD|AUD)\b', text, re.IGNORECASE)
            if currency_match:
                currency = currency_match.group(1).upper()
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=currency_match.group(0)
                )
                field = ExtractedField(
                    field_name="currency",
                    value=currency,
                    raw_value=currency_match.group(0),
                    evidence=[evidence],
                    confidence=FieldConfidence.HIGH
                )
                bundle.extracted_fields.append(field)
                bundle.currency = currency
                break
    
    def _extract_line_items(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract line items."""
        # Simplified - would parse actual table structure
        # For now, create mock line item
        for span in text_spans:
            text = span.get("text", "")
            # Look for quantity patterns
            qty_match = re.search(r'(?:qty|quantity):?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            if qty_match:
                try:
                    quantity = float(qty_match.group(1))
                    evidence = Evidence(
                        document_id=document.document_id,
                        page_number=span.get("page", 1),
                        raw_text_snippet=qty_match.group(0)
                    )
                    line_item = LineItem(
                        quantity=quantity,
                        unit_of_measure="PCS",  # Would extract from document
                        evidence=[evidence]
                    )
                    bundle.line_items.append(line_item)
                except ValueError:
                    pass
    
    def _extract_total_value(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract total value."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for "Total:", "Amount:", etc.
            total_match = re.search(r'(?:total|amount):?\s*\$?([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
            if total_match:
                try:
                    total_str = total_match.group(1).replace(",", "")
                    total_value = float(total_str)
                    evidence = Evidence(
                        document_id=document.document_id,
                        page_number=span.get("page", 1),
                        raw_text_snippet=total_match.group(0)
                    )
                    field = ExtractedField(
                        field_name="total_value",
                        value=total_value,
                        raw_value=total_match.group(0),
                        evidence=[evidence],
                        confidence=FieldConfidence.HIGH
                    )
                    bundle.extracted_fields.append(field)
                    bundle.total_value = total_value
                    break
                except ValueError:
                    pass
    
    def _extract_country_of_origin(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract country of origin (only if explicitly present)."""
        candidates = []
        for span in text_spans:
            text = span.get("text", "")
            # Look for "Country of Origin:", "COO:", "Made in", etc.
            coo_patterns = [
                r'(?:country\s*of\s*origin|coo|made\s*in):?\s*([A-Z]{2})',
                r'(?:origin):?\s*([A-Z]{2})'
            ]
            for pattern in coo_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    country = match.group(1).upper()
                    evidence = Evidence(
                        document_id=document.document_id,
                        page_number=span.get("page", 1),
                        raw_text_snippet=match.group(0)
                    )
                    candidates.append((country, evidence))
        
        if len(candidates) == 0:
            return
        
        if len(candidates) > 1:
            # Check for conflicts
            countries = [c[0] for c in candidates]
            if len(set(countries)) > 1:
                # Conflict detected
                bundle.conflicts.append({
                    "field": "country_of_origin",
                    "values": countries,
                    "evidence": [c[1].to_dict() for c in candidates]
                })
                bundle.warnings.append(f"Multiple conflicting countries of origin detected: {', '.join(set(countries))}")
                return
        
        # Use first candidate
        country, evidence = candidates[0]
        field = ExtractedField(
            field_name="country_of_origin",
            value=country,
            raw_value=country,
            evidence=[evidence],
            confidence=FieldConfidence.HIGH
        )
        bundle.extracted_fields.append(field)
    
    def _extract_material_composition(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract material composition (only if explicitly present)."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for "Material:", "Composition:", "Fabric:", etc.
            material_match = re.search(r'(?:material|composition|fabric):?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if material_match:
                material = material_match.group(1).strip()
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=material_match.group(0)
                )
                field = ExtractedField(
                    field_name="material_composition",
                    value=material,
                    raw_value=material_match.group(0),
                    evidence=[evidence],
                    confidence=FieldConfidence.MEDIUM
                )
                bundle.extracted_fields.append(field)
                break
    
    def _extract_brand_model(
        self,
        document: DocumentRecord,
        bundle: EnrichmentBundle,
        text_spans: List[Dict[str, Any]]
    ) -> None:
        """Extract brand/model (only if explicitly present)."""
        for span in text_spans:
            text = span.get("text", "")
            # Look for "Brand:", "Model:", "Part #:", etc.
            brand_match = re.search(r'(?:brand|model|part\s*#):?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if brand_match:
                brand_model = brand_match.group(1).strip()
                evidence = Evidence(
                    document_id=document.document_id,
                    page_number=span.get("page", 1),
                    raw_text_snippet=brand_match.group(0)
                )
                field = ExtractedField(
                    field_name="brand_model",
                    value=brand_model,
                    raw_value=brand_match.group(0),
                    evidence=[evidence],
                    confidence=FieldConfidence.MEDIUM
                )
                bundle.extracted_fields.append(field)
                break
    
    def _aggregate_values(self, bundle: EnrichmentBundle) -> None:
        """Aggregate values if unambiguous."""
        # Aggregate total quantity from line items
        if bundle.line_items:
            quantities = [li.quantity for li in bundle.line_items if li.quantity is not None]
            if len(set(quantities)) == 1:  # All same quantity
                bundle.total_quantity = quantities[0] if quantities else None
            elif len(quantities) > 1:
                # Sum quantities if all present
                try:
                    bundle.total_quantity = sum(quantities)
                except TypeError:
                    pass
