"""
Sprint H — trust-layer benchmark and regression tests.

Covers:
  - build_classification_memo shape and state transitions
  - no_classification / insufficient_support / weak_support / supported / needs_input
  - duty gating via _get_hts_if_supported
  - evidence_used population via _build_item_evidence_used
  - gold-set parametrized tests for classification outcomes
  - false-confidence and correct-refusal metrics (printed, not enforced yet)
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.shipment_analysis_service import (
    build_classification_memo,
    _get_hts_if_supported,
    _get_hts_from_classification,
    _build_item_evidence_used,
)
from app.services.analysis_pipeline import build_analysis_provenance

GOLD_SET_PATH = Path(__file__).parent / "benchmark" / "classification_gold_set.json"


# ────────────────────────────────────────────
# Provenance
# ────────────────────────────────────────────

def test_build_analysis_provenance_keys():
    p = build_analysis_provenance(analysis_path="celery", pipeline_mode="FULL")
    assert p["analysis_path"] == "celery"
    assert p["schema_version"] == "2.0"
    assert "classification_rule_mode" in p
    assert "hts_version_id" in p
    assert "neco_version" in p
    assert "generated_at" in p
    assert "rule_registry_hash" in p
    assert isinstance(p["dev_flags"], dict)


# ────────────────────────────────────────────
# build_classification_memo — state transitions
# ────────────────────────────────────────────

def test_memo_none_input():
    m = build_classification_memo(None)
    assert m["support_level"] == "no_classification"
    assert m["suppress_alternatives"] is True


def test_memo_empty_dict():
    m = build_classification_memo({})
    assert m["support_level"] == "no_classification"
    assert m["suppress_alternatives"] is True


def test_memo_clarification():
    m = build_classification_memo({"status": "CLARIFICATION_REQUIRED", "questions": ["Voltage?"]})
    assert m["support_level"] == "needs_input"
    assert m["suppress_alternatives"] is True
    assert "Voltage?" in m["open_questions"]


def test_memo_no_confident_match_low_sim():
    """Extremely low similarity + NO_CONFIDENT_MATCH → no_classification."""
    m = build_classification_memo({
        "status": "NO_CONFIDENT_MATCH",
        "success": False,
        "candidates": [{"hts_code": "9999", "similarity_score": 0.08}],
    })
    assert m["support_level"] == "no_classification"
    assert m["suppress_alternatives"] is True


def test_memo_no_confident_match_moderate_sim():
    """Moderate similarity + NO_CONFIDENT_MATCH → insufficient_support (not no_classification)."""
    m = build_classification_memo({
        "status": "NO_CONFIDENT_MATCH",
        "success": False,
        "candidates": [{"hts_code": "9018", "similarity_score": 0.19}],
    })
    assert m["support_level"] == "insufficient_support"
    assert m["suppress_alternatives"] is False


def test_memo_no_good_match():
    m = build_classification_memo({
        "status": "NO_GOOD_MATCH",
        "success": False,
        "candidates": [{"hts_code": "9018", "similarity_score": 0.12}],
    })
    assert m["support_level"] == "no_classification"


def test_memo_success_false_with_error():
    m = build_classification_memo({"success": False, "error": "timeout"})
    assert m["support_level"] in ("no_classification", "insufficient_support")


def test_memo_weak_similarity():
    m = build_classification_memo({
        "primary_candidate": {"hts_code": "8518300090", "similarity_score": 0.18},
        "candidates": [],
    })
    assert m["support_level"] == "weak_support"
    assert m.get("similarity_score") == pytest.approx(0.18)
    assert m["suppress_alternatives"] is False


def test_memo_very_low_similarity_on_success():
    """Even a 'successful' return with sim < 0.15 gets no_classification."""
    m = build_classification_memo({
        "primary_candidate": {"hts_code": "7209000000", "similarity_score": 0.10},
        "candidates": [],
    })
    assert m["support_level"] == "no_classification"
    assert m["suppress_alternatives"] is True
    assert m.get("proposed_hts") is None


def test_memo_supported():
    m = build_classification_memo({
        "primary_candidate": {"hts_code": "9018901500", "similarity_score": 0.45},
        "candidates": [{"hts_code": "9018901500", "similarity_score": 0.45}],
    })
    assert m["support_level"] == "supported"
    assert m["proposed_hts"] == "9018901500"
    assert m["suppress_alternatives"] is False


def test_memo_always_has_suppress_alternatives():
    """Every memo output must include the suppress_alternatives flag."""
    test_cases = [
        None,
        {},
        {"status": "CLARIFICATION_REQUIRED", "questions": ["Q1"]},
        {"status": "NO_CONFIDENT_MATCH"},
        {"primary_candidate": {"hts_code": "1234", "similarity_score": 0.50}},
    ]
    for case in test_cases:
        m = build_classification_memo(case)
        assert "suppress_alternatives" in m, f"Missing suppress_alternatives for input: {case}"


# ────────────────────────────────────────────
# _get_hts_if_supported — duty gating
# ────────────────────────────────────────────

def test_hts_gated_on_no_classification():
    clf = {"primary_candidate": {"hts_code": "9018900000"}}
    memo = {"support_level": "no_classification"}
    assert _get_hts_if_supported(clf, memo) is None


def test_hts_gated_on_insufficient():
    clf = {"primary_candidate": {"hts_code": "9018900000"}}
    memo = {"support_level": "insufficient_support"}
    assert _get_hts_if_supported(clf, memo) is None


def test_hts_gated_on_needs_input():
    clf = {"primary_candidate": {"hts_code": "9018900000"}}
    memo = {"support_level": "needs_input"}
    assert _get_hts_if_supported(clf, memo) is None


def test_hts_passes_on_supported():
    clf = {"primary_candidate": {"hts_code": "9018900000"}}
    memo = {"support_level": "supported"}
    assert _get_hts_if_supported(clf, memo) == "9018900000"


def test_hts_blocked_on_weak_support():
    """P2.4-F: Only 'supported' passes; weak_support is now blocked."""
    clf = {"primary_candidate": {"hts_code": "9018900000"}}
    memo = {"support_level": "weak_support"}
    assert _get_hts_if_supported(clf, memo) is None


def test_duty_none_when_memo_no_classification():
    """End-to-end: build memo from bad classification, confirm HTS blocked."""
    clf = {"status": "NO_CONFIDENT_MATCH", "success": False, "candidates": [{"similarity_score": 0.05}]}
    memo = build_classification_memo(clf)
    assert _get_hts_if_supported(clf, memo) is None


# ────────────────────────────────────────────
# _build_item_evidence_used
# ────────────────────────────────────────────

def _make_doc(filename, doc_type="data_sheet", text="Sample extracted text content"):
    from app.models.shipment_document import ShipmentDocumentType
    doc = MagicMock()
    doc.id = uuid4()
    doc.filename = filename
    doc.document_type = ShipmentDocumentType.DATA_SHEET if doc_type == "data_sheet" else (
        ShipmentDocumentType.COMMERCIAL_INVOICE if doc_type == "commercial_invoice" else
        ShipmentDocumentType.ENTRY_SUMMARY if doc_type == "entry_summary" else
        ShipmentDocumentType.DATA_SHEET
    )
    doc.extracted_text = text
    return doc


def test_evidence_used_from_item_doc_link():
    doc = _make_doc("Gripper_spec.pdf")
    item_id = uuid4()
    result = _build_item_evidence_used(
        "Gripper", [doc], item_id, {str(item_id): [doc.id]}
    )
    assert len(result) == 1
    assert result[0]["match_reason"] == "item_doc_link"
    assert result[0]["filename"] == "Gripper_spec.pdf"


def test_evidence_used_filename_heuristic():
    doc = _make_doc("gripper_datasheet.pdf")
    result = _build_item_evidence_used("Gripper", [doc])
    assert len(result) == 1
    assert result[0]["match_reason"] == "filename_heuristic"


def test_evidence_used_no_duplicate():
    """Same doc matched by link AND heuristic should appear only once."""
    doc = _make_doc("gripper_datasheet.pdf")
    item_id = uuid4()
    result = _build_item_evidence_used(
        "Gripper", [doc], item_id, {str(item_id): [doc.id]}
    )
    assert len(result) == 1


def test_evidence_used_includes_all_docs_type():
    inv = _make_doc("invoice_2024.pdf", "commercial_invoice", "Line items list")
    result = _build_item_evidence_used("Motor", [inv])
    assert len(result) == 1
    assert result[0]["match_reason"] == "all_docs"


def test_evidence_used_empty_when_no_docs():
    result = _build_item_evidence_used("Motor", [])
    assert result == []


def test_evidence_used_match_confidence_high():
    """P2.3: item_doc_link should have match_confidence='high'."""
    doc = _make_doc("Gripper_spec.pdf")
    item_id = uuid4()
    result = _build_item_evidence_used("Gripper", [doc], item_id, {str(item_id): [doc.id]})
    assert result[0]["match_confidence"] == "high"


def test_evidence_used_match_confidence_low_filename():
    """P2.3: filename_heuristic should have match_confidence='low'."""
    doc = _make_doc("gripper_datasheet.pdf")
    result = _build_item_evidence_used("Gripper", [doc])
    assert result[0]["match_confidence"] == "low"


def test_evidence_used_match_confidence_medium_all_docs():
    """P2.3: all_docs (invoice/ES) should have match_confidence='medium'."""
    inv = _make_doc("invoice_2024.pdf", "commercial_invoice", "Line items list")
    result = _build_item_evidence_used("Motor", [inv])
    assert result[0]["match_confidence"] == "medium"


def test_evidence_used_snippet_truncated():
    long_text = "A" * 1000
    doc = _make_doc("spec.pdf", text=long_text)
    item_id = uuid4()
    result = _build_item_evidence_used("spec", [doc], item_id, {str(item_id): [doc.id]})
    assert len(result[0]["snippet"]) <= 300


# ────────────────────────────────────────────
# Gold set parametrized tests
# ────────────────────────────────────────────

def _load_gold_set():
    if not GOLD_SET_PATH.exists():
        return []
    with open(GOLD_SET_PATH) as f:
        return json.load(f)


GOLD_SET = _load_gold_set()


@pytest.mark.parametrize(
    "item",
    [g for g in GOLD_SET if g["expected_outcome"] == "no_classification"],
    ids=lambda g: g["id"],
)
def test_memo_refusal_on_empty_evidence(item):
    """Items with vague/empty descriptions and no extracted text should yield no_classification."""
    clf = {
        "status": "NO_CONFIDENT_MATCH",
        "success": False,
        "candidates": [],
    } if item["description"].strip() else None
    memo = build_classification_memo(clf)
    assert memo["support_level"] in ("no_classification", "insufficient_support", "needs_input"), (
        f"Gold item {item['id']} should refuse classification but got {memo['support_level']}"
    )


@pytest.mark.parametrize(
    "item",
    [g for g in GOLD_SET if g["expected_outcome"] == "needs_input"],
    ids=lambda g: g["id"],
)
def test_memo_needs_input_items(item):
    """Items explicitly needing user input should NOT produce 'supported'."""
    clf = {
        "status": "CLARIFICATION_REQUIRED",
        "questions": [{"attribute": "material", "question": "What material?"}],
        "blocking_reason": "Critical attributes missing",
    }
    memo = build_classification_memo(clf)
    assert memo["support_level"] == "needs_input"


@pytest.mark.parametrize(
    "item",
    [g for g in GOLD_SET if g["expected_outcome"] == "supported" and g["difficulty"] == "easy"],
    ids=lambda g: g["id"],
)
def test_memo_supported_on_good_classification(item):
    """Easy items with good similarity should yield 'supported'."""
    clf = {
        "primary_candidate": {"hts_code": f"{item['expected_hts_heading']}000000", "similarity_score": 0.55},
        "candidates": [{"hts_code": f"{item['expected_hts_heading']}000000", "similarity_score": 0.55}],
        "success": True,
    }
    memo = build_classification_memo(clf)
    assert memo["support_level"] == "supported", (
        f"Gold item {item['id']} with good sim should be supported, got {memo['support_level']}"
    )
    assert memo["proposed_hts"].startswith(item["expected_hts_heading"])


# ────────────────────────────────────────────
# Metrics summary (runs as a single test, prints report)
# ────────────────────────────────────────────

def test_benchmark_metrics_report():
    """Print benchmark metrics. Does not fail — observational only for now."""
    if not GOLD_SET:
        pytest.skip("No gold set loaded")

    supported_correct = 0
    supported_wrong_heading = 0
    false_confidence = 0
    correct_refusal = 0
    missed_refusal = 0
    total = len(GOLD_SET)

    for item in GOLD_SET:
        expected = item["expected_outcome"]
        heading = item.get("expected_hts_heading")

        if expected in ("no_classification", "needs_input"):
            clf_none = None if not item["description"].strip() else {
                "status": "NO_CONFIDENT_MATCH",
                "success": False,
                "candidates": [],
            }
            memo = build_classification_memo(clf_none)
            if memo["support_level"] in ("no_classification", "insufficient_support", "needs_input"):
                correct_refusal += 1
            else:
                missed_refusal += 1
        elif expected == "supported" and heading:
            clf_good = {
                "primary_candidate": {"hts_code": f"{heading}000000", "similarity_score": 0.55},
                "candidates": [{"hts_code": f"{heading}000000", "similarity_score": 0.55}],
                "success": True,
            }
            memo = build_classification_memo(clf_good)
            if memo["support_level"] == "supported":
                if memo.get("proposed_hts", "")[:4] == heading:
                    supported_correct += 1
                else:
                    supported_wrong_heading += 1
            else:
                false_confidence += 1

    report = (
        f"\n{'='*50}\n"
        f"BENCHMARK METRICS ({total} items)\n"
        f"{'='*50}\n"
        f"Supported + correct heading : {supported_correct}\n"
        f"Supported + wrong heading   : {supported_wrong_heading}\n"
        f"False confidence (supported said not): {false_confidence}\n"
        f"Correct refusal             : {correct_refusal}\n"
        f"Missed refusal (should refuse, said supported): {missed_refusal}\n"
        f"{'='*50}\n"
    )
    print(report)
