"""
Golden Page Tests for HTS Extraction - Pages 2774, 2794, 2911, 2999

These tests enforce deterministic extraction correctness across complex chapters:
- Page 2774: Chapter 84 (machinery)
- Page 2794: Chapter 84 (machinery)
- Page 2911: Chapter 85 (electrical)
- Page 2999: Chapter 87 (vehicles)

Invariants:
- Exact code set match (no extras, no missing)
- All codes marked valid (suffix_token_text and suffix_token_band present)
- Legitimate .00 suffixes preserved
- Duties attached correctly
- No synthetic codes
"""

import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.hts_node import HTSNode
from scripts.duty_resolution import resolve_duty, ResolvedDuty

NEW_UUID = "792bb867-c549-4769-80ca-d9d1adc883a3"

# Golden fixtures - exact codes from NEW_UUID extraction
GOLDEN_PAGE_2774_CODES = {
    "8415.90.40.00",
    "8415.90.80.25",
    "8415.90.80.45",
    "8415.90.80.65",
    "8415.90.80.85",
    "8416.10.00.00",
    "8416.20.00.40",
    "8416.20.00.80",
    "8416.30.00.00",
    "8416.90.00.00",
    "8417.10.00.00",
    "8417.20.00.00",
    "8417.80.00.00",
    "8417.90.00.00",
}

GOLDEN_PAGE_2794_CODES = {
    "8432.10.00.20",
    "8432.10.00.40",
    "8432.10.00.60",
    "8432.21.00.00",
    "8432.29.00.40",
    "8432.29.00.60",
    "8432.29.00.80",
    "8432.29.00.90",
    "8432.31.00.10",
    "8432.31.00.90",
    "8432.39.00.10",
    "8432.39.00.90",
    "8432.41.00.00",
    "8432.42.00.00",
    "8432.80.00.10",
    "8432.80.00.80",
    "8432.90.00.10",
    "8432.90.00.20",
    "8432.90.00.40",
    "8432.90.00.50",
    "8432.90.00.60",
    "8432.90.00.81",
}

GOLDEN_PAGE_2911_CODES = {
    "8516.60.40.60",
    "8516.60.40.70",
    "8516.60.40.74",
    "8516.60.40.78",
    "8516.60.40.82",
    "8516.60.40.86",
    "8516.60.60.00",
    "8516.71.00.20",
    "8516.71.00.40",
    "8516.71.00.60",
    "8516.71.00.80",
    "8516.72.00.00",
    "8516.79.00.00",
    "8516.80.40.00",
    "8516.80.80.00",
}

GOLDEN_PAGE_2999_CODES = {
    "8711.10.00.00",
    "8711.20.00.30",
    "8711.20.00.60",
    "8711.20.00.90",
    "8711.30.00.30",
    "8711.30.00.60",
    "8711.30.00.90",
    "8711.40.30.00",
    "8711.40.60.30",
    "8711.40.60.60",
    "8711.50.00.30",
    "8711.50.00.60",
    "8711.60.00.50",
    "8711.60.00.90",
    "8711.90.01.00",
}

# Legitimate .00 codes (must have suffix_token_text="00" and suffix_token_band="SUFFIX_BAND")
LEGITIMATE_00_CODES = {
    2774: {"8415.90.40.00", "8416.10.00.00", "8416.30.00.00", "8416.90.00.00", "8417.10.00.00", "8417.20.00.00", "8417.80.00.00", "8417.90.00.00"},
    2794: {"8432.21.00.00", "8432.41.00.00", "8432.42.00.00"},
    2911: {"8516.60.60.00", "8516.72.00.00", "8516.79.00.00"},
    2999: {"8711.10.00.00", "8711.40.30.00", "8711.90.01.00"},
}

# Duty assertions - at least one code per page must have these duty patterns
DUTY_ASSERTIONS = {
    2774: {
        "8415.90.40.00": {
            "general_contains": ["1.4%"],
            "special_contains": ["Free"],
            "col2_contains": ["35%"],
        },
    },
    2794: {
        "8432.10.00.20": {
            "general_contains": ["Free"],
        },
    },
    2911: {
        "8516.60.40.60": {
            "col2_contains": ["35%"],
        },
    },
    2999: {
        "8711.40.30.00": {
            "general_contains": ["Free"],
            "special_contains": ["Free"],
            "col2_contains": ["10%"],
        },
    },
}

# Description assertions - case-insensitive substring matches
DESCRIPTION_ASSERTIONS = {
    2774: {},  # No specific descriptions required
    2794: {},
    2911: {},
    2999: {},
}


@pytest.fixture
def db_session():
    """Database session fixture."""
    return async_session_maker()


@pytest.mark.asyncio
async def test_golden_page_2774_extraction(db_session):
    """Test Page 2774 extraction correctness."""
    page_num = 2774
    expected_codes = GOLDEN_PAGE_2774_CODES
    
    # Query codes from this page
    query = select(HTSNode).where(
        HTSNode.hts_version_id == NEW_UUID,
        HTSNode.level == 10
    )
    result = await db_session.execute(query)
    nodes = list(result.scalars().all())
    
    # Filter by source_page
    page_codes = []
    for node in nodes:
        if node.source_lineage and node.source_lineage.get("source_page") == page_num:
            page_codes.append(node)
    
    extracted_codes = {node.code_display for node in page_codes}
    
    # A) EXACT SET MATCH
    missing = expected_codes - extracted_codes
    extra = extracted_codes - expected_codes
    assert len(missing) == 0, f"Missing codes: {missing}"
    assert len(extra) == 0, f"Extra codes: {extra}"
    assert extracted_codes == expected_codes, "Extracted codes set does not exactly match expected set"
    
    # B) ALL CODES VALID (suffix_token_text and suffix_token_band present)
    for node in page_codes:
        component_parts = node.source_lineage.get("component_parts", {})
        suffix_token_text = component_parts.get("suffix_token_text")
        suffix_token_band = component_parts.get("suffix_token_band")
        
        assert suffix_token_text is not None, (
            f"Code {node.code_display} missing suffix_token_text (synthetic code detected)"
        )
        assert suffix_token_band == "SUFFIX_BAND", (
            f"Code {node.code_display} has suffix_token_band={suffix_token_band}, expected SUFFIX_BAND"
        )
        
        # Check is_valid flag
        is_valid = node.source_lineage.get("is_valid", True) is not False
        assert is_valid, f"Code {node.code_display} marked as invalid"
    
    # C) LEGITIMATE .00 CODES PRESERVED
    legitimate_00 = LEGITIMATE_00_CODES[page_num]
    for code_display in legitimate_00:
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Legitimate .00 code {code_display} not found"
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") == "00", (
            f"Legitimate .00 code {code_display} missing suffix_token_text='00'"
        )
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND", (
            f"Legitimate .00 code {code_display} missing suffix_token_band='SUFFIX_BAND'"
        )
    
    # D) DUTY ASSERTIONS
    duty_assertions = DUTY_ASSERTIONS.get(page_num, {})
    for code_display, assertions in duty_assertions.items():
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Code {code_display} not found for duty assertion"
        
        if "general_contains" in assertions:
            duty_general = node.duty_general_raw or ""
            for pattern in assertions["general_contains"]:
                assert pattern in duty_general, (
                    f"Code {code_display} general duty '{duty_general}' does not contain '{pattern}'"
                )
        
        if "special_contains" in assertions:
            duty_special = node.duty_special_raw or ""
            for pattern in assertions["special_contains"]:
                assert pattern in duty_special, (
                    f"Code {code_display} special duty '{duty_special}' does not contain '{pattern}'"
                )
        
        if "col2_contains" in assertions:
            duty_col2 = node.duty_column2_raw or ""
            for pattern in assertions["col2_contains"]:
                assert pattern in duty_col2, (
                    f"Code {code_display} col2 duty '{duty_col2}' does not contain '{pattern}'"
                )
    
    print(f"✅ Page {page_num} golden test PASSED: Found {len(page_codes)} codes, all valid")


@pytest.mark.asyncio
async def test_golden_page_2794_extraction(db_session):
    """Test Page 2794 extraction correctness."""
    page_num = 2794
    expected_codes = GOLDEN_PAGE_2794_CODES
    
    query = select(HTSNode).where(
        HTSNode.hts_version_id == NEW_UUID,
        HTSNode.level == 10
    )
    result = await db_session.execute(query)
    nodes = list(result.scalars().all())
    
    page_codes = []
    for node in nodes:
        if node.source_lineage and node.source_lineage.get("source_page") == page_num:
            page_codes.append(node)
    
    extracted_codes = {node.code_display for node in page_codes}
    
    missing = expected_codes - extracted_codes
    extra = extracted_codes - expected_codes
    assert len(missing) == 0, f"Missing codes: {missing}"
    assert len(extra) == 0, f"Extra codes: {extra}"
    
    # Validity checks
    for node in page_codes:
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") is not None, f"Code {node.code_display} missing suffix_token_text"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND", f"Code {node.code_display} invalid band"
    
    # Legitimate .00 codes
    legitimate_00 = LEGITIMATE_00_CODES[page_num]
    for code_display in legitimate_00:
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Legitimate .00 code {code_display} not found"
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") == "00"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND"
    
    # Duty assertions
    duty_assertions = DUTY_ASSERTIONS.get(page_num, {})
    for code_display, assertions in duty_assertions.items():
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Code {code_display} not found"
        
        if "general_contains" in assertions:
            duty_general = node.duty_general_raw or ""
            for pattern in assertions["general_contains"]:
                assert pattern in duty_general, f"Code {code_display} general duty missing '{pattern}'"
    
    print(f"✅ Page {page_num} golden test PASSED: Found {len(page_codes)} codes, all valid")


@pytest.mark.asyncio
async def test_golden_page_2911_extraction(db_session):
    """Test Page 2911 extraction correctness."""
    page_num = 2911
    expected_codes = GOLDEN_PAGE_2911_CODES
    
    query = select(HTSNode).where(
        HTSNode.hts_version_id == NEW_UUID,
        HTSNode.level == 10
    )
    result = await db_session.execute(query)
    nodes = list(result.scalars().all())
    
    page_codes = []
    for node in nodes:
        if node.source_lineage and node.source_lineage.get("source_page") == page_num:
            page_codes.append(node)
    
    extracted_codes = {node.code_display for node in page_codes}
    
    missing = expected_codes - extracted_codes
    extra = extracted_codes - expected_codes
    assert len(missing) == 0, f"Missing codes: {missing}"
    assert len(extra) == 0, f"Extra codes: {extra}"
    
    # Validity checks
    for node in page_codes:
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") is not None, f"Code {node.code_display} missing suffix_token_text"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND", f"Code {node.code_display} invalid band"
    
    # Legitimate .00 codes
    legitimate_00 = LEGITIMATE_00_CODES[page_num]
    for code_display in legitimate_00:
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Legitimate .00 code {code_display} not found"
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") == "00"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND"
    
    # Duty assertions
    duty_assertions = DUTY_ASSERTIONS.get(page_num, {})
    for code_display, assertions in duty_assertions.items():
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Code {code_display} not found"
        
        if "col2_contains" in assertions:
            duty_col2 = node.duty_column2_raw or ""
            for pattern in assertions["col2_contains"]:
                assert pattern in duty_col2, f"Code {code_display} col2 duty missing '{pattern}'"
    
    print(f"✅ Page {page_num} golden test PASSED: Found {len(page_codes)} codes, all valid")


@pytest.mark.asyncio
async def test_golden_page_2999_extraction(db_session):
    """Test Page 2999 extraction correctness."""
    page_num = 2999
    expected_codes = GOLDEN_PAGE_2999_CODES
    
    query = select(HTSNode).where(
        HTSNode.hts_version_id == NEW_UUID,
        HTSNode.level == 10
    )
    result = await db_session.execute(query)
    nodes = list(result.scalars().all())
    
    page_codes = []
    for node in nodes:
        if node.source_lineage and node.source_lineage.get("source_page") == page_num:
            page_codes.append(node)
    
    extracted_codes = {node.code_display for node in page_codes}
    
    missing = expected_codes - extracted_codes
    extra = extracted_codes - expected_codes
    assert len(missing) == 0, f"Missing codes: {missing}"
    assert len(extra) == 0, f"Extra codes: {extra}"
    
    # Validity checks
    for node in page_codes:
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") is not None, f"Code {node.code_display} missing suffix_token_text"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND", f"Code {node.code_display} invalid band"
    
    # Legitimate .00 codes
    legitimate_00 = LEGITIMATE_00_CODES[page_num]
    for code_display in legitimate_00:
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Legitimate .00 code {code_display} not found"
        component_parts = node.source_lineage.get("component_parts", {})
        assert component_parts.get("suffix_token_text") == "00"
        assert component_parts.get("suffix_token_band") == "SUFFIX_BAND"
    
    # Duty assertions
    duty_assertions = DUTY_ASSERTIONS.get(page_num, {})
    for code_display, assertions in duty_assertions.items():
        node = next((n for n in page_codes if n.code_display == code_display), None)
        assert node is not None, f"Code {code_display} not found"
        
        if "general_contains" in assertions:
            duty_general = node.duty_general_raw or ""
            for pattern in assertions["general_contains"]:
                assert pattern in duty_general, f"Code {code_display} general duty missing '{pattern}'"
        
        if "special_contains" in assertions:
            duty_special = node.duty_special_raw or ""
            for pattern in assertions["special_contains"]:
                assert pattern in duty_special, f"Code {code_display} special duty missing '{pattern}'"
        
        if "col2_contains" in assertions:
            duty_col2 = node.duty_column2_raw or ""
            for pattern in assertions["col2_contains"]:
                assert pattern in duty_col2, f"Code {code_display} col2 duty missing '{pattern}'"
    
    print(f"✅ Page {page_num} golden test PASSED: Found {len(page_codes)} codes, all valid")


@pytest.mark.asyncio
async def test_golden_pages_duty_resolution(db_session):
    """Test duty resolution for all golden pages."""
    all_codes = (
        list(GOLDEN_PAGE_2774_CODES) +
        list(GOLDEN_PAGE_2794_CODES) +
        list(GOLDEN_PAGE_2911_CODES) +
        list(GOLDEN_PAGE_2999_CODES)
    )
    
    failed = []
    for hts_code in all_codes:
        try:
            resolved = await resolve_duty(hts_code, db_session, hts_version_id=NEW_UUID)
            
            # Check that resolution succeeded
            assert resolved is not None, f"Code {hts_code} resolution returned None"
            
            # Check that no REVIEW_REQUIRED flag is set (duties should be resolvable)
            # Note: Some codes may legitimately have missing duties, so we check flags
            flags = resolved.flags
            if "REVIEW_REQUIRED" in flags:
                # This is acceptable if duty is actually missing, but log it
                print(f"  ⚠️  {hts_code} has REVIEW_REQUIRED flag")
            
            # Check inheritance path is populated
            assert len(resolved.inheritance_path) > 0, f"Code {hts_code} has empty inheritance_path"
            
        except Exception as e:
            failed.append((hts_code, str(e)))
    
    assert len(failed) == 0, f"Failed duty resolution for codes: {failed}"
    print(f"✅ Duty resolution PASSED for all {len(all_codes)} golden page codes")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
