"""
Golden Page Test for HTS Extraction - Page 2198

This test enforces deterministic extraction correctness for a known-good page.
Once this passes, we can scale to full extraction.

Expected codes from page 2198:
- 6112.20.10.10 through 6112.20.10.90 (9 codes)
- 6112.20.20.10, 6112.20.20.20 (2 codes)
Total: 11 ten-digit codes

Invariants:
- No missing codes
- No extra codes
- Duty columns attached correctly to suffix children
- Base codes (8-digit) present
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.regenerate_structured_hts_codes_v2 import (
    extract_codes_from_page,
    normalize_hts_code,
)
import pdfplumber


GOLDEN_PAGE = 2198
EXPECTED_10_DIGIT_CODES = {
    "6112.20.10.10",
    "6112.20.10.20",
    "6112.20.10.30",
    "6112.20.10.40",
    "6112.20.10.50",
    "6112.20.10.60",
    "6112.20.10.70",
    "6112.20.10.80",
    "6112.20.10.90",
    "6112.20.20.10",
    "6112.20.20.20",
    "6112.20.20.30",
}

# Expected base/suffix mappings
EXPECTED_BASE_SUFFIX_MAP = {
    "6112.20.10": ["10", "20", "30", "40", "50", "60", "70", "80", "90"],
    "6112.20.20": ["10", "20", "30"],
}

# Expected duty rates by base
EXPECTED_DUTY_RATES = {
    "6112.20.10": {
        "general": "28.2%",
        "special_contains": ["Free", "AU", "BH", "CL", "CO", "IL", "JO", "KR", "MA", "OM", "P", "PA", "PE", "S", "SG"],
        "column2": "72%",
    },
    "6112.20.20": {
        "general": "8.3%",
        "special_contains": ["Free", "AU", "BH", "CL", "CO", "E*", "IL", "JO", "KR", "MA", "OM", "P", "PA", "PE", "S", "SG"],
        "column2": "90%",
    },
}

# Expected description patterns by code
EXPECTED_DESCRIPTIONS = {
    "6112.20.20.10": "Of cotton",
    "6112.20.20.20": "Of wool or fine animal hair",
    "6112.20.20.30": "Other (859)",
}

EXPECTED_8_DIGIT_CODES = {
    "6112.20.10",
    "6112.20.20",
}


def find_pdf_path():
    """Find the HTS PDF file."""
    pdf_paths = [
        Path("CBP Docs/2025HTS.pdf"),
        Path("../CBP Docs/2025HTS.pdf"),
        Path("data/hts_tariff/2025HTS.pdf"),
    ]
    
    for path in pdf_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError("HTS PDF not found. Please specify path.")


@pytest.fixture
def pdf_page():
    """Load page 2198 from PDF."""
    pdf_path = find_pdf_path()
    pdf = pdfplumber.open(pdf_path)
    if GOLDEN_PAGE > len(pdf.pages):
        pdf.close()
        pytest.fail(f"Page {GOLDEN_PAGE} does not exist in PDF")
    page = pdf.pages[GOLDEN_PAGE - 1]
    # Keep PDF open - caller must close it
    yield page
    pdf.close()


def test_golden_page_2198_extraction(pdf_page):
    """Test that page 2198 extracts exactly the expected codes with hard correctness assertions."""
    extraction_metadata = {}
    codes = extract_codes_from_page(pdf_page, GOLDEN_PAGE, extraction_metadata)
    
    # Separate by level
    codes_8 = {c["code_display"] for c in codes if c["level"] == 8}
    codes_10 = {c["code_display"] for c in codes if c["level"] == 10}
    
    # A) EXACT SET MATCH
    missing_8 = EXPECTED_8_DIGIT_CODES - codes_8
    extra_8 = codes_8 - EXPECTED_8_DIGIT_CODES
    assert len(missing_8) == 0, f"Missing 8-digit codes: {missing_8}"
    assert len(extra_8) == 0, f"Extra 8-digit codes: {extra_8}"
    
    missing_10 = EXPECTED_10_DIGIT_CODES - codes_10
    extra_10 = codes_10 - EXPECTED_10_DIGIT_CODES
    assert len(missing_10) == 0, f"Missing 10-digit codes: {missing_10}"
    assert len(extra_10) == 0, f"Extra 10-digit codes: {extra_10}"
    assert codes_10 == EXPECTED_10_DIGIT_CODES, "Extracted codes set does not exactly match expected set"
    
    # B) BASE/SUFFIX CORRECTNESS
    codes_10_dict = {c["code_display"]: c for c in codes if c["level"] == 10}
    
    for code_display, code_obj in codes_10_dict.items():
        # Normalized full_code must be 10 digits, digits only
        normalized = code_obj["code_normalized"]
        assert len(normalized) == 10, f"Code {code_display} normalized to {normalized} (length {len(normalized)}, expected 10)"
        assert normalized.isdigit(), f"Code {code_display} normalized to {normalized} (contains non-digits)"
        
        # Component parts correctness
        component_parts = code_obj.get("source_lineage", {}).get("component_parts", {})
        assert "base" in component_parts, f"Code {code_display} missing 'base' in component_parts"
        assert "suffix" in component_parts, f"Code {code_display} missing 'suffix' in component_parts"
        
        base = component_parts["base"]
        suffix = component_parts["suffix"]
        
        # Base must be one of expected bases
        assert base in EXPECTED_BASE_SUFFIX_MAP, f"Code {code_display} has unexpected base {base}"
        
        # Suffix must be valid for this base
        valid_suffixes = EXPECTED_BASE_SUFFIX_MAP[base]
        assert suffix in valid_suffixes, (
            f"Code {code_display} has suffix {suffix} which is not valid for base {base}. "
            f"Valid suffixes: {valid_suffixes}"
        )
        
        # Reconstructed code must match
        reconstructed = f"{base}.{suffix}"
        assert reconstructed == code_display, (
            f"Code {code_display} component_parts mismatch: "
            f"base={base}, suffix={suffix}, reconstructed={reconstructed}"
        )
        
        # Parent code must be correct
        parent = code_obj["parent_code_normalized"]
        expected_parent_normalized = normalize_hts_code(base)
        assert parent == expected_parent_normalized, (
            f"Code {code_display} has parent {parent}, expected {expected_parent_normalized}"
        )
    
    # C) DUTY ANCHORING CORRECTNESS
    for code_display, code_obj in codes_10_dict.items():
        base = code_obj.get("source_lineage", {}).get("component_parts", {}).get("base")
        assert base in EXPECTED_DUTY_RATES, f"Code {code_display} has unknown base {base}"
        
        expected_duty = EXPECTED_DUTY_RATES[base]
        
        # Duty must be attached at child record level
        duty_general = code_obj.get("duty_general_raw", "")
        duty_special = code_obj.get("duty_special_raw", "")
        duty_column2 = code_obj.get("duty_column2_raw", "")
        
        assert duty_general is not None, f"Code {code_display} missing duty_general_raw"
        assert duty_special is not None, f"Code {code_display} missing duty_special_raw"
        assert duty_column2 is not None, f"Code {code_display} missing duty_column2_raw"
        
        # General rate must match
        assert expected_duty["general"] in duty_general, (
            f"Code {code_display} general duty '{duty_general}' does not contain expected '{expected_duty['general']}'"
        )
        
        # Special rate must contain all expected program codes
        for program in expected_duty["special_contains"]:
            assert program in duty_special, (
                f"Code {code_display} special duty '{duty_special}' does not contain expected program '{program}'"
            )
        
        # Column 2 must match
        assert expected_duty["column2"] in duty_column2, (
            f"Code {code_display} column2 duty '{duty_column2}' does not contain expected '{expected_duty['column2']}'"
        )
    
    # D) DESCRIPTION ATTACHMENT SANITY
    for code_display, expected_desc_pattern in EXPECTED_DESCRIPTIONS.items():
        if code_display in codes_10_dict:
            code_obj = codes_10_dict[code_display]
            description = code_obj.get("description_short", "") or code_obj.get("description_long", "")
            assert expected_desc_pattern.lower() in description.lower(), (
                f"Code {code_display} description '{description}' does not contain expected pattern '{expected_desc_pattern}'"
            )
    
    print(f"✅ Golden page test PASSED: Found {len(codes_8)} 8-digit and {len(codes_10)} 10-digit codes")
    print(f"   All {len(codes_10)} codes passed base/suffix correctness, duty anchoring, and description checks")


def test_golden_page_2198_duty_attachment(pdf_page):
    """Test that duty columns are correctly attached to suffix children."""
    extraction_metadata = {}
    codes = extract_codes_from_page(pdf_page, GOLDEN_PAGE, extraction_metadata)
    
    # Group codes by base
    codes_by_base = {}
    for code_obj in codes:
        if code_obj["level"] == 10:
            base = code_obj.get("source_lineage", {}).get("component_parts", {}).get("base")
            if base:
                if base not in codes_by_base:
                    codes_by_base[base] = []
                codes_by_base[base].append(code_obj)
    
    # For each base, verify suffix children have duty information
    for base, children in codes_by_base.items():
        assert len(children) > 0, f"Base {base} has no children"
        
        # At least some children should have duty information
        # (exact duty values depend on PDF content, but structure must be present)
        for child in children:
            assert "duty_general_raw" in child, f"Child {child['code_display']} missing duty_general_raw"
            assert "duty_special_raw" in child, f"Child {child['code_display']} missing duty_special_raw"
            assert "duty_column2_raw" in child, f"Child {child['code_display']} missing duty_column2_raw"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
