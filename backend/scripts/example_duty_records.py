"""
Example Duty Records - Sprint 5 Phase 1

This script demonstrates how to create example duty records for:
1. Free duty
2. Ad valorem duty
3. Compound duty
4. Text-only duty
5. Conditional duty

These examples show the proper structure for each duty type.
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.duty_rate import DutyRate, DutyType, DutyConfidence, DutySourceLevel


def example_1_free_duty():
    """
    Example 1: Free Duty
    
    Raw Text: "Free"
    
    Key Points:
    - is_free = True (first-class flag)
    - duty_rate_numeric = 0.0 (computable)
    - duty_confidence = HIGH (clear "Free" text)
    - source_code = hts_code (parsed directly from this code)
    """
    record = {
        "hts_version_id": None,  # Would link to hts_versions.id if available
        "hts_code": "8518301000",  # Target code (the code this rate applies to)
        "source_code": "8518301000",  # Source code (the code this rate was derived from)
        "duty_column": "general",
        "source_level": DutySourceLevel.TEN_DIGIT,
        "duty_type": DutyType.FREE,
        "duty_rate_raw_text": "Free",
        "duty_rate_structure": {
            "is_free": True
        },
        "duty_rate_numeric": 0.0,
        "duty_confidence": DutyConfidence.HIGH,
        "is_free": True,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,  # Ongoing
    }
    
    return record


def example_2_ad_valorem_duty():
    """
    Example 2: Ad Valorem Duty
    
    Raw Text: "4.9%"
    
    Key Points:
    - Numeric value directly computable
    - Structure preserves percentage as number
    - High confidence (clear format)
    - source_code = hts_code (parsed directly from this code)
    """
    record = {
        "hts_version_id": None,
        "hts_code": "8518301000",
        "source_code": "8518301000",
        "duty_column": "general",
        "source_level": DutySourceLevel.TEN_DIGIT,
        "duty_type": DutyType.AD_VALOREM,
        "duty_rate_raw_text": "4.9%",
        "duty_rate_structure": {
            "percentage": 4.9
        },
        "duty_rate_numeric": 4.9,
        "duty_confidence": DutyConfidence.HIGH,
        "is_free": False,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,
    }
    
    return record


def example_3_compound_duty():
    """
    Example 3: Compound Duty
    
    Raw Text: "4.9% + $0.50/kg"
    
    Key Points:
    - duty_rate_numeric = None (requires quantity + value for calculation)
    - Structure preserves all components with normalized unit fields
    - Still high confidence (components clearly identified)
    - Raw text preserved (never discarded)
    
    Calculation Note:
    To compute duty for this compound rate:
    duty = (entered_value * 0.049) + (quantity_kg * 0.50)
    """
    record = {
        "hts_version_id": None,
        "hts_code": "8518301000",
        "source_code": "8518301000",
        "duty_column": "general",
        "source_level": DutySourceLevel.TEN_DIGIT,
        "duty_type": DutyType.COMPOUND,
        "duty_rate_raw_text": "4.9% + $0.50/kg",
        "duty_rate_structure": {
            "components": [
                {
                    "type": "ad_valorem",
                    "percentage": 4.9
                },
                {
                    "type": "specific",
                    "amount": 0.50,
                    "unit": "kg",  # Original unit from text
                    "unit_normalized": "kg",  # Normalized unit code
                    "quantity_basis": "net_weight",  # net_weight, gross_weight, units, area, volume, etc.
                    "currency": "USD"
                }
            ]
        },
        "duty_rate_numeric": None,  # Cannot compute without quantity
        "duty_confidence": DutyConfidence.HIGH,
        "is_free": False,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,
    }
    
    return record


def example_4_text_only_duty():
    """
    Example 4: Text-Only Duty
    
    Raw Text: "As provided for in Note 2 to Chapter 85"
    
    Key Points:
    - duty_rate_numeric = None (requires external resolution)
    - Low confidence (cannot parse into computable structure)
    - Raw text preserved (critical for audit trail)
    - Structure attempts to extract reference but preserves original text
    - source_code may differ if inherited from heading
    """
    record = {
        "hts_version_id": None,
        "hts_code": "8518301000",  # Target code
        "source_code": "8518",  # Rate was derived from heading 8518
        "duty_column": "general",
        "source_level": DutySourceLevel.SIX_DIGIT,  # Rate from 6-digit heading
        "duty_type": DutyType.TEXT_ONLY,
        "duty_rate_raw_text": "As provided for in Note 2 to Chapter 85",
        "duty_rate_structure": {
            "text": "As provided for in Note 2 to Chapter 85",
            "reference_type": "chapter_note",
            "reference": "Note 2 to Chapter 85"
        },
        "duty_rate_numeric": None,  # Cannot compute - requires external resolution
        "duty_confidence": DutyConfidence.LOW,
        "is_free": False,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,
        "additional_metadata": {
            "requires_resolution": True,
            "resolution_source": "chapter_notes"
        }
    }
    
    return record


def example_5_conditional_duty():
    """
    Example 5: Conditional Duty
    
    Raw Text: "See subheading 1234.56.78"
    
    Key Points:
    - duty_rate_numeric = None (requires resolution)
    - Medium confidence (reference identified but not resolved)
    - Structure captures the condition type and reference
    - Raw text preserved for auditability
    """
    record = {
        "hts_version_id": None,
        "hts_code": "8518301000",
        "source_code": "8518301000",
        "duty_column": "general",
        "source_level": DutySourceLevel.TEN_DIGIT,
        "duty_type": DutyType.CONDITIONAL,
        "duty_rate_raw_text": "See subheading 1234.56.78",
        "duty_rate_structure": {
            "condition_type": "subheading_reference",
            "reference": "1234.56.78",
            "reference_type": "subheading"
        },
        "duty_rate_numeric": None,  # Requires resolution to referenced subheading
        "duty_confidence": DutyConfidence.MEDIUM,
        "is_free": False,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,
        "additional_metadata": {
            "requires_resolution": True,
            "resolution_target": "1234.56.78"
        }
    }
    
    return record


def example_6_specific_duty():
    """
    Example 6: Specific Duty (per-unit)
    
    Raw Text: "$0.50/kg"
    
    Key Points:
    - duty_rate_numeric stores the per-unit amount (0.50)
    - Structure preserves unit with normalized fields
    - Cannot compute final duty without quantity
    - unit_normalized and quantity_basis are normalized fields
    """
    record = {
        "hts_version_id": None,
        "hts_code": "8518301000",
        "source_code": "8518301000",
        "duty_column": "general",
        "source_level": DutySourceLevel.TEN_DIGIT,
        "duty_type": DutyType.SPECIFIC,
        "duty_rate_raw_text": "$0.50/kg",
        "duty_rate_structure": {
            "amount": 0.50,
            "unit": "kg",  # Original unit from text
            "unit_normalized": "kg",  # Normalized unit code (kg, g, m, cm, pcs, etc.)
            "quantity_basis": "per_unit",  # per_unit, per_100, per_1000, etc.
            "currency": "USD"
        },
        "duty_rate_numeric": 0.50,  # Per-unit amount (not final duty)
        "duty_confidence": DutyConfidence.HIGH,
        "is_free": False,
        "duty_inheritance_chain": [
            {"from_code": "8518", "from_level": "six_digit", "reason": "heading_rate", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30", "from_level": "eight_digit", "reason": "subheading_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None},
            {"from_code": "8518.30.10", "from_level": "ten_digit", "reason": "statistical_inheritance", "timestamp": "2025-01-01T00:00:00", "hts_version_id": None}
        ],
        "source_page": "HTS-2025-85-12",
        "effective_start_date": datetime(2025, 1, 1),
        "effective_end_date": None,
    }
    
    return record


def print_all_examples():
    """Print all example records as JSON for inspection."""
    examples = [
        ("Example 1: Free Duty", example_1_free_duty()),
        ("Example 2: Ad Valorem Duty", example_2_ad_valorem_duty()),
        ("Example 3: Compound Duty", example_3_compound_duty()),
        ("Example 4: Text-Only Duty", example_4_text_only_duty()),
        ("Example 5: Conditional Duty", example_5_conditional_duty()),
        ("Example 6: Specific Duty", example_6_specific_duty()),
    ]
    
    for title, record in examples:
        print(f"\n{'=' * 80}")
        print(f"{title}")
        print('=' * 80)
        
        # Convert to serializable format
        serializable = {}
        for key, value in record.items():
            if isinstance(value, (DutyType, DutyConfidence, DutySourceLevel)):
                serializable[key] = value.value
            elif isinstance(value, datetime):
                serializable[key] = value.isoformat()
            elif value is None:
                serializable[key] = None
            else:
                serializable[key] = value
        
        print(json.dumps(serializable, indent=2, default=str))


if __name__ == "__main__":
    print_all_examples()
