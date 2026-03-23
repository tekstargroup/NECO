"""
Intelligent Field Detection using Claude
Extracts structured data from unstructured documents
"""

from anthropic import Anthropic
from typing import Dict, Any, List, Optional
import json
import re
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class FieldDetector:
    """
    Use Claude AI to intelligently extract fields from documents
    """
    
    # Max characters sent to Claude per extraction call (~3k tokens, keeps under 10k/min rate limit)
    MAX_TEXT_CHARS = 12000

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-3-5-haiku-20241022"
    
    def detect_document_type(self, text: str) -> str:
        """
        Determine what type of document this is
        
        Args:
            text: Document text
        
        Returns:
            Document type string
        """
        # Quick keyword-based detection first
        text_lower = text.lower()
        
        if "commercial invoice" in text_lower:
            return "commercial_invoice"
        elif "entry summary" in text_lower or "7501" in text or "cbp form 7501" in text_lower:
            return "entry_summary"
        elif "packing list" in text_lower or "packing slip" in text_lower:
            return "packing_list"
        elif "bill of lading" in text_lower or "b/l" in text:
            return "bill_of_lading"
        elif "certificate of origin" in text_lower:
            return "certificate_origin"
        
        # If unclear, use Claude
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze this document excerpt and identify the document type.
Return ONLY one of these exact values:
- commercial_invoice
- entry_summary
- packing_list
- bill_of_lading
- certificate_origin
- other

Document excerpt:
{text[:1000]}

Document type:"""
                }]
            )
            
            doc_type = response.content[0].text.strip().lower()
            return doc_type if doc_type in ["commercial_invoice", "entry_summary", "packing_list", "bill_of_lading", "certificate_origin"] else "other"
        
        except Exception as e:
            logger.error(f"Error detecting document type: {e}")
            return "other"
    
    def extract_commercial_invoice_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from commercial invoice
        
        Args:
            text: Invoice text
        
        Returns:
            Structured invoice data
        """
        prompt = f"""Extract all relevant information from this commercial invoice and return it as JSON.

Required fields (use null if not found):
- po_number: Purchase order number
- invoice_number: Invoice number  
- invoice_date: Invoice date
- country_of_origin: Country of origin (2-letter code if possible, e.g. "CN" for China)
- incoterm: Incoterm (e.g. FOB, CIF, EXW)
- currency: Currency code (e.g. USD)
- total_value: Total invoice value (number only)
- supplier_name: Supplier/exporter name
- supplier_address: Supplier address
- buyer_name: Buyer/importer name
- buyer_address: Buyer address
- line_items: Array of line items, each with:
  - line_number: Line number
  - description: Product description
  - quantity: Quantity (number)
  - unit: Unit of measure
  - unit_price: Price per unit (number)
  - total: Total line value (number)
  - hts_code: HTS/HS code if present
  - country_of_origin: Country if specified per line

Return ONLY valid JSON, no other text.

Commercial Invoice:
{text[:self.MAX_TEXT_CHARS]}"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Extract JSON from response (in case Claude adds explanatory text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response_text)
            
            return data
        
        except Exception as e:
            logger.error(f"Error extracting invoice data: {e}")
            return {"error": str(e)}
    
    def extract_entry_summary_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from 7501 Entry Summary
        
        Args:
            text: Entry summary text
        
        Returns:
            Structured entry data
        """
        prompt = f"""Extract all relevant information from this CBP Form 7501 Entry Summary and return it as JSON.

Required fields (use null if not found):
- entry_number: 11-digit entry number (XXX-XXXXXXX-X)
- entry_type: Entry type code (01, 03, 11, etc.)
- entry_date: Entry date
- port_of_entry: Port code
- importer_number: Importer of record number
- filer: Filer/broker name
- total_entered_value: Total entered value (number)
- total_duty: Total duty amount (number)
- line_items: Array of line items, each with:
  - line_number: Line number
  - description: Merchandise description
  - hts_code: HTS classification (10-digit)
  - country_of_origin: Country code
  - quantity: Quantity (number)
  - unit: Unit of measure
  - entered_value: Entered value (number)
  - duty_rate: Duty rate (number, e.g. 4.9 for 4.9%)
  - duty_amount: Duty amount (number)
  - section_301_rate: Section 301 rate if applicable (number)
  - section_301_amount: Section 301 amount if applicable (number)

Return ONLY valid JSON, no other text.

Entry Summary:
{text[:self.MAX_TEXT_CHARS]}"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response_text)
            
            return data
        
        except Exception as e:
            logger.error(f"Error extracting entry summary data: {e}")
            return {"error": str(e)}
    
    def extract_generic_fields(self, text: str, fields: List[str]) -> Dict[str, Any]:
        """
        Extract specific fields from any document
        
        Args:
            text: Document text
            fields: List of field names to extract
        
        Returns:
            Dictionary of extracted fields
        """
        prompt = f"""Extract the following fields from this document:
{', '.join(fields)}

Return as JSON with field names as keys. Use null if field not found.

Document:
{text[:2000]}"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response_text)
            
            return data
        
        except Exception as e:
            logger.error(f"Error extracting generic fields: {e}")
            return {}


