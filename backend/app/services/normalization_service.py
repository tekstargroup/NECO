"""
Normalization Service - Sprint 10

Safe normalization without guessing.

Key principles:
- Normalize formats without changing meaning
- Never normalize by guessing
- Retain raw values
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

logger = logging.getLogger(__name__)


class NormalizationService:
    """Service for safe normalization."""
    
    # Controlled vocabulary for UOM
    UOM_VOCABULARY = {
        "PCS": ["PCS", "PIECE", "PIECES", "PC", "PCE"],
        "KG": ["KG", "KILOGRAM", "KILOGRAMS", "KGS"],
        "LB": ["LB", "POUND", "POUNDS", "LBS"],
        "M": ["M", "METER", "METERS", "METRE", "METRES"],
        "M2": ["M2", "SQM", "SQUARE METER", "SQUARE METERS"],
        "M3": ["M3", "CBM", "CUBIC METER", "CUBIC METERS"],
        "L": ["L", "LITER", "LITERS", "LITRE", "LITRES"],
        "EA": ["EA", "EACH"],
        "SET": ["SET", "SETS"],
        "PAIR": ["PAIR", "PAIRS", "PR"],
        "DOZ": ["DOZ", "DOZEN", "DOZENS"],
        "CTN": ["CTN", "CARTON", "CARTONS"],
        "BOX": ["BOX", "BOXES"],
        "PKG": ["PKG", "PACKAGE", "PACKAGES"]
    }
    
    # Currency codes
    CURRENCY_CODES = {
        "USD": ["USD", "US$", "$", "US DOLLAR", "US DOLLARS"],
        "EUR": ["EUR", "€", "EURO", "EUROS"],
        "GBP": ["GBP", "£", "POUND", "POUNDS STERLING"],
        "CNY": ["CNY", "CN¥", "RMB", "YUAN"],
        "JPY": ["JPY", "¥", "YEN"],
        "CAD": ["CAD", "C$", "CANADIAN DOLLAR"],
        "AUD": ["AUD", "A$", "AUSTRALIAN DOLLAR"]
    }
    
    def normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date to ISO format.
        
        Only normalizes if parseable. Returns None if cannot parse.
        """
        if not date_str:
            return None
        
        # Common date formats
        date_formats = [
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y"
        ]
        
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                return parsed.isoformat()
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def normalize_currency(self, currency_str: str) -> Optional[str]:
        """
        Normalize currency code.
        
        Returns standard 3-letter code if recognized, None otherwise.
        """
        if not currency_str:
            return None
        
        currency_upper = currency_str.upper().strip()
        
        # Check against vocabulary
        for code, variants in self.CURRENCY_CODES.items():
            if currency_upper in variants:
                return code
        
        # If already a 3-letter code, return as-is
        if len(currency_upper) == 3 and currency_upper.isalpha():
            return currency_upper
        
        logger.warning(f"Unrecognized currency: {currency_str}")
        return None
    
    def normalize_quantity(self, quantity_str: str) -> Optional[float]:
        """
        Normalize quantity to float.
        
        Returns None if cannot parse.
        """
        if not quantity_str:
            return None
        
        try:
            # Remove commas and whitespace
            cleaned = str(quantity_str).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse quantity: {quantity_str}")
            return None
    
    def normalize_uom(self, uom_str: str) -> Dict[str, str]:
        """
        Normalize unit of measure to controlled vocabulary.
        
        Returns dict with:
        - normalized: Standard UOM code (if recognized)
        - raw: Original value (always preserved)
        """
        if not uom_str:
            return {"normalized": None, "raw": None}
        
        uom_upper = uom_str.upper().strip()
        
        # Check against vocabulary
        for normalized, variants in self.UOM_VOCABULARY.items():
            if uom_upper in variants:
                return {"normalized": normalized, "raw": uom_str}
        
        # If not recognized, return raw only
        return {"normalized": None, "raw": uom_str}
    
    def normalize_value(self, value_str: str) -> Optional[float]:
        """
        Normalize monetary value to float.
        
        Handles currency symbols and commas.
        """
        if not value_str:
            return None
        
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.]', '', str(value_str).replace(",", ""))
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse value: {value_str}")
            return None
