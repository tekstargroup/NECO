"""
Duty Rate Data Model - Sprint 5 Phase 1

This model preserves all legal duty meaning in a lossless, auditable format.
Supports: Free, Ad valorem, Specific, Compound, Conditional, and Text-only duties.

Core Principles:
- Never discard legal text
- Store structure even if not computable
- Maintain inheritance chain for auditability
- "Free" is first-class data, not NULL
- Compound/conditional duties are representable even if not calculable
"""

from sqlalchemy import Column, String, DateTime, Numeric, Integer, Text, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class DutyType(str, enum.Enum):
    """
    Duty rate type classification.
    
    AD_VALOREM: Percentage-based (e.g., "4.9%")
    SPECIFIC: Per-unit amount (e.g., "$0.50/kg")
    COMPOUND: Combination of ad valorem + specific (e.g., "4.9% + $0.50/kg")
    CONDITIONAL: Rate depends on conditions (e.g., "See subheading 1234.56.78")
    FREE: No duty (e.g., "Free")
    TEXT_ONLY: Cannot be parsed but text preserved (e.g., "As provided for in Note 2")
    """
    AD_VALOREM = "ad_valorem"
    SPECIFIC = "specific"
    COMPOUND = "compound"
    CONDITIONAL = "conditional"
    FREE = "free"
    TEXT_ONLY = "text_only"


class DutyConfidence(str, enum.Enum):
    """
    Confidence level in duty rate interpretation.
    
    HIGH: Parsed with high certainty (e.g., clear "4.9%" or "Free")
    MEDIUM: Parsed but some ambiguity (e.g., compound rate structure inferred)
    LOW: Text preserved but parsing uncertain (e.g., conditional/see reference)
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DutySourceLevel(str, enum.Enum):
    """
    Source HTS code precision level.
    
    SIX_DIGIT: 6-digit heading level (e.g., "8518.30")
    EIGHT_DIGIT: 8-digit subheading level (e.g., "8518.30.10")
    TEN_DIGIT: 10-digit statistical level (e.g., "8518.30.1000")
    """
    SIX_DIGIT = "six_digit"
    EIGHT_DIGIT = "eight_digit"
    TEN_DIGIT = "ten_digit"


class DutyRate(Base):
    """
    Comprehensive duty rate data model.
    
    Preserves raw legal text, structured interpretation, numeric values when computable,
    confidence levels, source precision, and inheritance chain for full auditability.
    
    Sprint 5 Workstream 5.A: Duty Data Model (core)
    """
    
    __tablename__ = "duty_rates"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # HTS version reference (links to hts_versions table record - nullable for flexibility)
    # Note: hts_versions is a raw SQL table without ORM model, so this is a loose reference
    hts_version_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Target HTS code (the code this duty rate applies to)
    hts_code = Column(String(10), nullable=False, index=True)
    
    # Source code (the actual 6/8/10 digit code string the rate was derived from)
    # This may differ from hts_code if the rate was inherited
    # Example: rate parsed from "8518.30" but applies to "8518.30.1000"
    source_code = Column(String(10), nullable=False, index=True)
    
    # Duty column type (General/MFN, Special/FTA, Column 2)
    duty_column = Column(String(20), nullable=False, index=True)  # 'general', 'special', 'column2'
    
    # Source precision level
    source_level = Column(
        SQLEnum(DutySourceLevel, native_enum=False),
        nullable=False,
        index=True
    )
    
    # Duty type classification
    duty_type = Column(
        SQLEnum(DutyType, native_enum=False),
        nullable=False,
        index=True
    )
    
    # Raw legal text (NEVER discard, NEVER clean)
    # Stores the EXACT wording from HTS source document, verbatim
    # No normalization, no cleaning, no abbreviation expansion
    # This is the source of truth for what CBP actually says
    duty_rate_raw_text = Column(Text, nullable=False)
    
    # Structured interpretation (JSONB for flexibility)
    # Examples:
    # - Ad valorem: {"percentage": 4.9}
    # - Specific: {"amount": 0.50, "unit": "kg", "currency": "USD", "unit_normalized": "kg", "quantity_basis": "net_weight"}
    #   unit: original unit from text (kg, no, m2, etc.)
    #   unit_normalized: normalized unit code (kg, g, m, cm, pcs, m2, etc.)
    #   quantity_basis: "net_weight", "gross_weight", "units", "area", "volume", etc.
    # - Compound: {"components": [{"type": "ad_valorem", "percentage": 4.9}, {"type": "specific", "amount": 0.50, "unit": "kg", "unit_normalized": "kg", "quantity_basis": "net_weight"}]}
    # - Conditional: {"condition_type": "subheading_reference", "reference": "1234.56.78"}
    # - Free: {"is_free": true} (may include conditions: {"is_free": true, "condition": "See subheading..."})
    # - Text-only: {"text": "As provided for in Note 2"}
    duty_rate_structure = Column(JSONB, nullable=True)
    
    # Numeric value when computable (nullable if compound/conditional/text-only)
    # For ad valorem: percentage as decimal (4.9% → 0.049 or 4.9, depending on convention)
    # For specific: amount per unit (not final duty, requires quantity)
    # For FREE: 0.0
    # For compound/conditional/text-only: NULL (requires calculation or resolution)
    duty_rate_numeric = Column(Numeric(10, 6), nullable=True)
    
    # Confidence level
    duty_confidence = Column(
        SQLEnum(DutyConfidence, native_enum=False),
        nullable=False,
        default=DutyConfidence.MEDIUM,
        index=True
    )
    
    # First-class "Free" flag (explicit, not inferred from numeric = 0)
    # Note: "Free" can be conditional (e.g., "Free (See subheading...)")
    # is_free = True does NOT imply HIGH confidence - check duty_confidence separately
    is_free = Column(Boolean, nullable=False, default=False, index=True)
    
    # Inheritance chain (JSONB array of inheritance steps with full metadata)
    # Each step is an object with: from_code, from_level, reason, timestamp, source_document/version_id
    # Example: [
    #   {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": "uuid"},
    #   {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": "uuid"},
    #   {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": "uuid"}
    # ]
    # This allows full audit trail with provenance for each inheritance step
    duty_inheritance_chain = Column(JSONB, nullable=True)
    
    # Source metadata
    source_page = Column(String(20), nullable=True)  # Page number from HTS PDF
    
    # Time context - when this duty rate is effective
    effective_start_date = Column(DateTime, nullable=True, index=True)  # Effective date range start
    effective_end_date = Column(DateTime, nullable=True, index=True)  # Effective date range end
    
    # Legacy aliases (for backward compatibility with hts_versions table naming)
    # These properties map to effective_start_date/effective_end_date
    @property
    def effective_from(self):
        """Legacy alias for effective_start_date (backward compatibility with hts_versions table)"""
        return self.effective_start_date
    
    @effective_from.setter
    def effective_from(self, value):
        """Legacy alias setter for effective_start_date"""
        self.effective_start_date = value
    
    @property
    def effective_to(self):
        """Legacy alias for effective_end_date (backward compatibility with hts_versions table)"""
        return self.effective_end_date
    
    @effective_to.setter
    def effective_to(self, value):
        """Legacy alias setter for effective_end_date"""
        self.effective_end_date = value
    
    # Trade program / country-specific information (JSONB for flexibility)
    # Examples:
    # - {"programs": ["USMCA", "GSP"], "countries": ["CA", "MX"]}
    # - {"programs": ["NAFTA"], "countries": ["CA", "MX"]}
    trade_program_info = Column(JSONB, nullable=True)
    
    # Additional metadata (JSONB for extensibility)
    # Examples:
    # - {"parse_method": "regex", "parse_version": "1.0", "parse_confidence_score": 0.95}
    # - {"special_conditions": "Subject to quota", "quota_id": "QR123"}
    additional_metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_duty_rates_hts_column', 'hts_code', 'duty_column'),
        Index('idx_duty_rates_type_confidence', 'duty_type', 'duty_confidence'),
        Index('idx_duty_rates_source_level_hts', 'source_level', 'hts_code'),
    )
    
    def __repr__(self):
        return f"<DutyRate {self.hts_code} {self.duty_column} ({self.duty_type.value})>"
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "hts_version_id": str(self.hts_version_id) if self.hts_version_id else None,
            "hts_code": self.hts_code,
            "source_code": self.source_code,
            "duty_column": self.duty_column,
            "source_level": self.source_level.value if self.source_level else None,
            "duty_type": self.duty_type.value if self.duty_type else None,
            "duty_rate_raw_text": self.duty_rate_raw_text,
            "duty_rate_structure": self.duty_rate_structure,
            "duty_rate_numeric": float(self.duty_rate_numeric) if self.duty_rate_numeric is not None else None,
            "duty_confidence": self.duty_confidence.value if self.duty_confidence else None,
            "is_free": self.is_free,
            "duty_inheritance_chain": self.duty_inheritance_chain,
            "source_page": self.source_page,
            "effective_start_date": self.effective_start_date.isoformat() if self.effective_start_date else None,
            "effective_end_date": self.effective_end_date.isoformat() if self.effective_end_date else None,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,  # Legacy alias
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,  # Legacy alias
            "trade_program_info": self.trade_program_info,
            "additional_metadata": self.additional_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
