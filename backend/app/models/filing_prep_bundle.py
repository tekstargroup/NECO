"""
Filing Prep Bundle Model - Sprint 9

Canonical data object for broker handoff.

Key principles:
- Read-only intelligence
- Explicit blockers
- Conservative defaults
- Human review required
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ReviewStatus(str, Enum):
    """Review status for filing prep."""
    REVIEWED_ACCEPTED = "REVIEWED_ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEWED_REJECTED = "REVIEWED_REJECTED"
    DRAFT = "DRAFT"


class ExportBlockReason(str, Enum):
    """Reasons why export may be blocked."""
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MISSING_QUANTITY = "MISSING_QUANTITY"
    MISSING_VALUE = "MISSING_VALUE"
    MISSING_DUTY_FIELDS = "MISSING_DUTY_FIELDS"
    UNRESOLVED_PSC_FLAGS = "UNRESOLVED_PSC_FLAGS"


@dataclass
class DutyBreakdown:
    """Duty breakdown for filing prep."""
    general_duty: Optional[str] = None
    special_duty: Optional[str] = None  # Raw text only
    column2_duty: Optional[str] = None


@dataclass
class FilingPrepBundle:
    """
    Canonical filing prep bundle for broker handoff.
    
    Single source of truth for all broker exports.
    """
    # Identification
    declared_hts_code: str  # 10-digit
    
    # Duty breakdown
    duty_breakdown: DutyBreakdown
    
    # Quantity and value
    quantity: Optional[float] = None
    unit_of_measure: Optional[str] = None
    customs_value: Optional[float] = None
    
    # Country of origin (context only)
    country_of_origin: Optional[str] = None
    
    # Review status
    review_status: ReviewStatus = ReviewStatus.REVIEW_REQUIRED
    
    # PSC flags (if any)
    psc_flags: List[str] = field(default_factory=list)
    
    # Regulatory evaluations (Side Sprint A - evidence-driven flags)
    regulatory_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    
    # HTS version
    hts_version_id: str = ""
    
    # Review metadata
    review_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    # Override metadata (if applicable)
    is_override: bool = False
    override_of_review_id: Optional[str] = None
    override_justification: Optional[str] = None
    
    # Disclaimers
    disclaimers: List[str] = field(default_factory=list)
    
    # Export blockers
    export_blocked: bool = False
    export_block_reasons: List[ExportBlockReason] = field(default_factory=list)
    
    # Broker notes
    broker_notes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "declared_hts_code": self.declared_hts_code,
            "duty_breakdown": {
                "general_duty": self.duty_breakdown.general_duty,
                "special_duty": self.duty_breakdown.special_duty,
                "column2_duty": self.duty_breakdown.column2_duty
            },
            "quantity": self.quantity,
            "unit_of_measure": self.unit_of_measure,
            "customs_value": self.customs_value,
            "country_of_origin": self.country_of_origin,
            "review_status": self.review_status.value,
            "psc_flags": self.psc_flags,
            "regulatory_evaluations": self.regulatory_evaluations,
            "hts_version_id": self.hts_version_id,
            "review_id": self.review_id,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "is_override": self.is_override,
            "override_of_review_id": self.override_of_review_id,
            "override_justification": self.override_justification,
            "disclaimers": self.disclaimers,
            "export_blocked": self.export_blocked,
            "export_block_reasons": [r.value for r in self.export_block_reasons],
            "broker_notes": self.broker_notes
        }
