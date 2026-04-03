"""Patch E — heading reasoning trace (pure unit tests)."""

from app.engines.classification.heading_reasoning_trace import build_heading_reasoning_trace


def test_trace_empty_classification():
    t = build_heading_reasoning_trace(None)
    assert t["schema_version"] == "1"
    assert "notes" in t["unresolved_ambiguity"]


def test_trace_none_still_attaches_line_evidence():
    """When classification is withheld (e.g. suppress_alternatives), trace has no candidates but keeps doc hooks."""
    t = build_heading_reasoning_trace(
        None,
        evidence_used=[{"document_id": "d1", "snippet": "x"}],
        line_provenance=[{"document_id": "d1", "page": 2}],
    )
    assert t["heading_candidates"] == []
    assert t["rejected_alternatives"] == []
    assert t["source_evidence"]["document_evidence_refs"][0]["document_id"] == "d1"
    assert t["source_evidence"]["line_provenance"][0]["page"] == 2


def test_trace_ranked_candidates_and_rejected():
    clf = {
        "success": True,
        "status": "SUCCESS",
        "candidates": [
            {
                "hts_code": "8518.30.20",
                "hts_chapter": "85",
                "final_score": 0.9,
                "similarity_score": 0.4,
                "tariff_text_short": "Headphones",
                "_applied_priors": ["prior_a"],
            },
            {
                "hts_code": "8518.50.00",
                "hts_chapter": "85",
                "final_score": 0.5,
                "similarity_score": 0.35,
            },
        ],
        "metadata": {
            "gating_mode": "two_stage",
            "headings_used": ["8518"],
            "candidate_counts": {"pre_filter": 40, "post_filter": 12, "post_score": 2},
            "expanded_terms": ["earphone"],
            "applied_filters": ["exclude_9903_text"],
            "applied_priors": ["prior_a"],
            "reason_code": "SUCCESS",
            "product_analysis": {
                "product_family": "audio_devices",
                "suggested_chapters": [
                    {"chapter": 85, "confidence": 0.85, "reason": "Audio in Ch85"},
                ],
            },
        },
        "provenance": {"source_pages": [12], "code_ids": ["8518.30.20"]},
    }
    t = build_heading_reasoning_trace(
        clf,
        evidence_used=[{"document_id": "x", "snippet": "earbuds"}],
        line_provenance=[{"page": 1}],
    )
    assert len(t["heading_candidates"]) == 2
    assert t["heading_candidates"][0]["role"] == "selected_primary"
    assert t["rejected_alternatives"][0]["reason"]
    assert t["retrieval_and_narrowing"]["gating_mode"] == "two_stage"
    assert t["subheading_narrowing"]
    assert t["source_evidence"]["document_evidence_refs"][0]["document_id"] == "x"
    assert t["source_evidence"]["tariff_context"]["code_ids"] == ["8518.30.20"]


def test_trace_clarification_merge():
    orig = {
        "success": False,
        "status": "CLARIFICATION_REQUIRED",
        "candidates": [],
        "metadata": {
            "reason_code": "MISSING_REQUIRED_ATTRIBUTES",
            "missing_required_attributes": ["material"],
            "product_analysis": {
                "suggested_chapters": [{"chapter": 39, "confidence": 0.8, "reason": "plastic"}],
            },
        },
    }
    clf = {
        "status": "CLARIFICATION_REQUIRED",
        "questions": [{"attribute": "material", "question": "What material?"}],
        "blocking_reason": "missing material",
        "original_classification": orig,
    }
    t = build_heading_reasoning_trace(clf)
    assert t["unresolved_ambiguity"].get("blocking") is True
    assert t["unresolved_ambiguity"]["classification_status"] == "CLARIFICATION_REQUIRED"
    assert t["chapter_and_heading_rationale"][0]["chapter"] == 39
