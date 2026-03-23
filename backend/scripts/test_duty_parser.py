"""
Test script for Duty Parser - Sprint 5 Phase 2

Tests lossless parsing of various duty rate formats.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engines.duty.duty_parser import DutyParser
from app.models.duty_rate import DutyType, DutyConfidence


def test_duty_parser():
    """Test duty parser with various examples."""
    parser = DutyParser()
    
    test_cases = [
        # Free duties - Case A: True Free
        ("Free", DutyType.FREE, DutyConfidence.HIGH, True),
        ("Free.", DutyType.FREE, DutyConfidence.HIGH, True),
        ("Free\nFree", DutyType.FREE, DutyConfidence.HIGH, True),
        
        # Free duties - Case B: Free with program list
        ("Free (A+, AU, BH, CL)", DutyType.FREE, DutyConfidence.MEDIUM, True),
        ("Free (CA, MX)", DutyType.FREE, DutyConfidence.MEDIUM, True),
        
        # Ad valorem
        ("4.9%", DutyType.AD_VALOREM, DutyConfidence.HIGH, False),
        ("6.5 percent", DutyType.AD_VALOREM, DutyConfidence.HIGH, False),
        
        # Ad valorem with secondary Free note - Case C
        ("20%\nFree (A+, AU, BH)", DutyType.AD_VALOREM, DutyConfidence.HIGH, False),
        ("6.6¢/kg\nFree", DutyType.SPECIFIC, DutyConfidence.HIGH, False),
        
        # Specific
        ("$0.50/kg", DutyType.SPECIFIC, DutyConfidence.HIGH, False),
        ("1.25 per kg", DutyType.SPECIFIC, DutyConfidence.HIGH, False),  # HIGH because unit is clearly identifiable
        
        # Compound
        ("4.9% + $0.50/kg", DutyType.COMPOUND, DutyConfidence.HIGH, False),
        ("6.5% and $1.00/kg", DutyType.COMPOUND, DutyConfidence.HIGH, False),
        
        # Conditional
        ("See subheading 1234.56.78", DutyType.CONDITIONAL, DutyConfidence.MEDIUM, False),
        ("As provided for in Note 2 to Chapter 85", DutyType.CONDITIONAL, DutyConfidence.MEDIUM, False),
        
        # Text-only (fallback)
        ("Subject to quota", DutyType.TEXT_ONLY, DutyConfidence.LOW, False),
    ]
    
    print("=" * 80)
    print("Duty Parser Test - Sprint 5 Phase 2")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for i, (text, expected_type, expected_confidence, expected_free) in enumerate(test_cases, 1):
        print(f"Test {i}: {text}")
        print("-" * 80)
        
        result = parser.parse_duty_rate(text)
        
        # Check type
        type_match = result.duty_type == expected_type
        confidence_match = result.duty_confidence == expected_confidence
        free_match = result.is_free == expected_free
        
        if type_match and confidence_match and free_match:
            print(f"✅ PASS")
            passed += 1
        else:
            print(f"❌ FAIL")
            failed += 1
            if not type_match:
                print(f"   Expected type: {expected_type.value}, got: {result.duty_type.value}")
            if not confidence_match:
                print(f"   Expected confidence: {expected_confidence.value}, got: {result.duty_confidence.value}")
            if not free_match:
                print(f"   Expected is_free: {expected_free}, got: {result.is_free}")
        
        print(f"   Type: {result.duty_type.value}")
        print(f"   Confidence: {result.duty_confidence.value}")
        print(f"   Is Free: {result.is_free}")
        print(f"   Numeric: {result.numeric_value}")
        print(f"   Structure: {result.structure}")
        print(f"   Parse Method: {result.parse_method}")
        if result.parse_errors:
            print(f"   Parse Errors: {result.parse_errors}")
        print()
    
    print("=" * 80)
    print(f"Summary: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = test_duty_parser()
    sys.exit(0 if success else 1)
