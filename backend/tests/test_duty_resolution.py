"""
Unit tests for duty inheritance resolver - Sprint 5.3 Step 2

Test cases:
A: Starting node has all three fields populated
B: Starting node missing special but parent has special
C: Starting node missing general across whole chain
D: Independent resolution (general from child, special from parent, col2 from grandparent)
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.duty_resolution import (
    resolve_duty_inheritance,
    ResolvedDuty,
    DutyFlag,
    normalize_hts_code,
)


def create_mock_node_fetcher(nodes: dict) -> callable:
    """
    Create a mock node fetcher for testing.
    
    Args:
        nodes: Dict mapping (code_normalized, level) -> node dict
    
    Returns:
        Function that fetches nodes from the dict
    """
    def node_fetcher(code_normalized: str, level: int) -> dict:
        key = (code_normalized, level)
        return nodes.get(key)
    return node_fetcher


def test_case_a_full_duty_at_starting_node():
    """
    Case A: Starting node has all three fields populated.
    Expected: No INHERITED flags, no REVIEW_REQUIRED.
    """
    # Setup: 10-digit node with all duties
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": "28.2%",
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.hts_code == "6112201010"
    assert result.resolved_general_raw == "28.2%"
    assert result.resolved_special_raw == "Free(AU,BH,...)"
    assert result.resolved_col2_raw == "72%"
    
    assert result.source_level_general == "10"
    assert result.source_level_special == "10"
    assert result.source_level_col2 == "10"
    
    assert result.source_hts_general == "6112201010"
    assert result.source_hts_special == "6112201010"
    assert result.source_hts_col2 == "6112201010"
    
    # Inheritance path includes all nodes visited (10 -> 8 -> 6)
    assert "6112201010" in result.inheritance_path
    assert len(result.inheritance_path) >= 1
    
    assert not result.has_flag(DutyFlag.INHERITED_FROM_PARENT)
    assert not result.has_flag(DutyFlag.MISSING_DUTY)
    assert not result.has_flag(DutyFlag.REVIEW_REQUIRED)


def test_case_b_special_inherited_from_parent():
    """
    Case B: Starting node missing special but parent has special.
    Expected: Special inherited, flags include INHERITED_FROM_PARENT, no MISSING_DUTY for special.
    """
    # Setup: 10-digit missing special, 8-digit parent has special
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": "28.2%",
            "duty_special_raw": None,  # Missing
            "duty_column2_raw": "72%",
        },
        ("61122010", 8): {
            "code_normalized": "61122010",
            "level": 8,
            "duty_general_raw": "28.2%",
            "duty_special_raw": "Free(AU,BH,...)",  # Parent has it
            "duty_column2_raw": "72%",
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.resolved_general_raw == "28.2%"  # From child
    assert result.resolved_special_raw == "Free(AU,BH,...)"  # From parent
    assert result.resolved_col2_raw == "72%"  # From child
    
    assert result.source_level_general == "10"
    assert result.source_level_special == "8"  # Inherited from parent
    assert result.source_level_col2 == "10"
    
    assert result.source_hts_general == "6112201010"
    assert result.source_hts_special == "61122010"  # Parent code
    assert result.source_hts_col2 == "6112201010"
    
    # Inheritance path includes all nodes visited (10 -> 8 -> 6)
    assert "6112201010" in result.inheritance_path
    assert "61122010" in result.inheritance_path
    assert len(result.inheritance_path) >= 2
    
    assert result.has_flag(DutyFlag.INHERITED_FROM_PARENT)
    assert not result.has_flag(DutyFlag.MISSING_DUTY)
    assert not result.has_flag(DutyFlag.REVIEW_REQUIRED)


def test_case_c_missing_general_across_chain():
    """
    Case C: Starting node missing general across whole chain.
    Expected: Flags include MISSING_DUTY and REVIEW_REQUIRED.
    """
    # Setup: All nodes missing general duty
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        },
        ("61122010", 8): {
            "code_normalized": "61122010",
            "level": 8,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        },
        ("611220", 6): {
            "code_normalized": "611220",
            "level": 6,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": None,
            "duty_column2_raw": None,
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.resolved_general_raw is None
    assert result.resolved_special_raw == "Free(AU,BH,...)"
    assert result.resolved_col2_raw == "72%"
    
    assert result.source_level_general == "none"
    assert result.source_level_special == "10"
    assert result.source_level_col2 == "10"
    
    assert result.source_hts_general is None
    assert result.source_hts_special == "6112201010"
    assert result.source_hts_col2 == "6112201010"
    
    assert result.inheritance_path == ["6112201010", "61122010", "611220"]
    
    assert result.has_flag(DutyFlag.MISSING_DUTY)
    assert result.has_flag(DutyFlag.REVIEW_REQUIRED)


def test_case_d_independent_resolution():
    """
    Case D: Independent resolution - general from child, special from parent, col2 from grandparent.
    Expected: Sources differ correctly, path includes all visited nodes.
    """
    # Setup: Different duties at different levels
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": "28.2%",  # Child has general
            "duty_special_raw": None,  # Missing
            "duty_column2_raw": None,  # Missing
        },
        ("61122010", 8): {
            "code_normalized": "61122010",
            "level": 8,
            "duty_general_raw": None,
            "duty_special_raw": "Free(AU,BH,...)",  # Parent has special
            "duty_column2_raw": None,  # Missing
        },
        ("611220", 6): {
            "code_normalized": "611220",
            "level": 6,
            "duty_general_raw": None,
            "duty_special_raw": None,
            "duty_column2_raw": "72%",  # Grandparent has col2
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.resolved_general_raw == "28.2%"  # From child
    assert result.resolved_special_raw == "Free(AU,BH,...)"  # From parent
    assert result.resolved_col2_raw == "72%"  # From grandparent
    
    assert result.source_level_general == "10"
    assert result.source_level_special == "8"
    assert result.source_level_col2 == "6"
    
    assert result.source_hts_general == "6112201010"
    assert result.source_hts_special == "61122010"
    assert result.source_hts_col2 == "611220"
    
    assert result.inheritance_path == ["6112201010", "61122010", "611220"]
    
    assert result.has_flag(DutyFlag.INHERITED_FROM_PARENT)  # Special and col2 inherited
    assert not result.has_flag(DutyFlag.MISSING_DUTY)
    assert not result.has_flag(DutyFlag.REVIEW_REQUIRED)


def test_explanation_resolved_at_child():
    """
    Test explanation for duty resolved at child node.
    Expected: explanation contains "defined at {hts_code}"
    """
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": "28.2%",
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.explanation_general is not None
    assert "present on" in result.explanation_general.lower()
    assert "6112.20.10.10" in result.explanation_general
    assert "28.2%" in result.explanation_general
    
    assert result.explanation_special is not None
    assert "present on" in result.explanation_special.lower()
    assert "6112.20.10.10" in result.explanation_special
    
    assert result.explanation_col2 is not None
    assert "present on" in result.explanation_col2.lower()


def test_explanation_inherited_from_parent():
    """
    Test explanation for inherited duty.
    Expected: explanation contains "inherited from {source_hts}"
    """
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": "28.2%",
            "duty_special_raw": None,  # Missing
            "duty_column2_raw": "72%",
        },
        ("61122010", 8): {
            "code_normalized": "61122010",
            "level": 8,
            "duty_general_raw": "28.2%",
            "duty_special_raw": "Free(AU,BH,...)",  # Parent has it
            "duty_column2_raw": "72%",
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.explanation_special is not None
    assert "inherited from" in result.explanation_special
    assert "6112.20.10" in result.explanation_special
    assert "6112.20.10.10" in result.explanation_special
    assert "Free(AU,BH,...)" in result.explanation_special


def test_explanation_missing_duty():
    """
    Test explanation for missing duty.
    Expected: explanation contains "Review required"
    """
    nodes = {
        ("6112201010", 10): {
            "code_normalized": "6112201010",
            "level": 10,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        },
        ("61122010", 8): {
            "code_normalized": "61122010",
            "level": 8,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": "Free(AU,BH,...)",
            "duty_column2_raw": "72%",
        },
        ("611220", 6): {
            "code_normalized": "611220",
            "level": 6,
            "duty_general_raw": None,  # Missing
            "duty_special_raw": None,
            "duty_column2_raw": None,
        }
    }
    
    fetcher = create_mock_node_fetcher(nodes)
    result = resolve_duty_inheritance("6112.20.10.10", fetcher)
    
    # Assertions
    assert result.explanation_general is not None
    assert "not found" in result.explanation_general
    assert "Review required" in result.explanation_general
    assert "6112.20.10.10" in result.explanation_general


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
