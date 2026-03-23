"""
Enrichment Bundle Model - Sprint 10

Canonical data object for document enrichment.

Key principles:
- Extract facts present in documents only
- Attach evidence pointers everywhere
- Never infer missing facts
- Handle conflicts explicitly
- Maintain replayability
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Document types supported for enrichment."""
    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE"
    PACKING_LIST = "PACKING_LIST"
    TECHNICAL_SPEC = "TECHNICAL_SPEC"


class FieldConfidence(str, Enum):
    """Confidence level for extracted fields (based on extraction quality only)."""
    HIGH = "HIGH"  # Clear extraction, unambiguous
    MEDIUM = "MEDIUM"  # Some ambiguity but extractable
    LOW = "LOW"  # Ambiguous or unclear extraction
    CONFLICT = "CONFLICT"  # Multiple conflicting values


class FieldWarning(str, Enum):
    """Warnings for extracted fields."""
    AMBIGUOUS = "AMBIGUOUS"  # Field value is ambiguous
    MULTIPLE_VALUES = "MULTIPLE_VALUES"  # Multiple values found, using first
    CONFLICT = "CONFLICT"  # Conflicting values detected
    UNREADABLE = "UNREADABLE"  # Section unreadable


@dataclass
class Evidence:
    """Evidence pointer for extracted fields."""
    document_id: str
    page_number: int
    bbox: Optional[Dict[str, float]] = None  # {"x1": float, "y1": float, "x2": float, "y2": float}
    line_span: Optional[Dict[str, int]] = None  # {"start_line": int, "end_line": int}
    raw_text_snippet: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_id": self.document_id,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "line_span": self.line_span,
            "raw_text_snippet": self.raw_text_snippet
        }


@dataclass
class ExtractedField:
    """Single extracted field with evidence."""
    field_name: str
    value: Any  # Can be str, float, datetime, etc.
    raw_value: str  # Original text as extracted
    evidence: List[Evidence] = field(default_factory=list)
    confidence: FieldConfidence = FieldConfidence.MEDIUM
    warnings: List[FieldWarning] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field_name": self.field_name,
            "value": self.value,
            "raw_value": self.raw_value,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence.value,
            "warnings": [w.value for w in self.warnings]
        }


@dataclass
class LineItem:
    """Extracted line item from invoice or packing list."""
    item_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_of_measure: Optional[str] = None
    unit_price: Optional[float] = None
    line_value: Optional[float] = None
    country_of_origin: Optional[str] = None
    material_composition: Optional[str] = None
    brand_model: Optional[str] = None
    evidence: List[Evidence] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_number": self.item_number,
            "description": self.description,
            "quantity": self.quantity,
            "unit_of_measure": self.unit_of_measure,
            "unit_price": self.unit_price,
            "line_value": self.line_value,
            "country_of_origin": self.country_of_origin,
            "material_composition": self.material_composition,
            "brand_model": self.brand_model,
            "evidence": [e.to_dict() for e in self.evidence]
        }


@dataclass
class EnrichmentBundle:
    """
    Canonical enrichment bundle from document extraction.
    
    Contains extracted fields with evidence, conflicts, and warnings.
    """
    # Document metadata
    document_id: str
    document_type: DocumentType
    document_hash: str
    parser_version: str = "1.0"
    
    # Extracted fields (structured)
    extracted_fields: List[ExtractedField] = field(default_factory=list)
    
    # Line items (for invoices/packing lists)
    line_items: List[LineItem] = field(default_factory=list)
    
    # Aggregated values (if unambiguous)
    total_quantity: Optional[float] = None
    total_value: Optional[float] = None
    currency: Optional[str] = None
    
    # Missing required fields
    missing_required_fields: List[str] = field(default_factory=list)
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    # Conflicts
    conflicts: List[Dict[str, Any]] = field(default_factory=list)  # {"field": str, "values": List[Any], "evidence": List[Evidence]}
    
    # Timestamps
    extracted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.value,
            "document_hash": self.document_hash,
            "parser_version": self.parser_version,
            "extracted_fields": [f.to_dict() for f in self.extracted_fields],
            "line_items": [li.to_dict() for li in self.line_items],
            "total_quantity": self.total_quantity,
            "total_value": self.total_value,
            "currency": self.currency,
            "missing_required_fields": self.missing_required_fields,
            "warnings": self.warnings,
            "conflicts": self.conflicts,
            "extracted_at": self.extracted_at.isoformat()
        }
    
    def get_field(self, field_name: str) -> Optional[ExtractedField]:
        """Get extracted field by name."""
        for field in self.extracted_fields:
            if field.field_name == field_name:
                return field
        return None
    
    def has_conflict(self, field_name: str) -> bool:
        """Check if field has conflicts."""
        for conflict in self.conflicts:
            if conflict.get("field") == field_name:
                return True
        field = self.get_field(field_name)
        if field and FieldWarning.CONFLICT in field.warnings:
            return True
        return False
    
    def is_unambiguous(self, field_name: str) -> bool:
        """Check if field value is unambiguous."""
        if self.has_conflict(field_name):
            return False
        field = self.get_field(field_name)
        if not field:
            return False
        if FieldWarning.AMBIGUOUS in field.warnings:
            return False
        return field.confidence in [FieldConfidence.HIGH, FieldConfidence.MEDIUM]
