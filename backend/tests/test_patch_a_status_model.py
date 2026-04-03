"""
Patch A — Status and similarity cleanup (regression tests).

Similarity does not gate SUCCESS/REVIEW; outcomes use fact completeness,
candidate quality (combined score), competitive ambiguity, and engine notes.
"""

import pytest

from app.engines.classification.review_explanation import generate_review_explanation
from app.engines.classification.status_model import (
    ClassificationStatus,
    MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS,
    competitive_ambiguity_requires_review,
    determine_status,
)


def test_determine_status_clarification_when_missing_attributes():
    assert (
        determine_status(["color"], 0.99, 0.99, True, ambiguity_requires_review=False)
        == ClassificationStatus.CLARIFICATION_REQUIRED
    )


def test_determine_status_no_confident_match_when_no_candidates():
    assert (
        determine_status([], 0.0, 0.0, False, ambiguity_requires_review=False)
        == ClassificationStatus.NO_CONFIDENT_MATCH
    )


def test_determine_status_success_when_bars_met_and_no_ambiguity():
    assert (
        determine_status([], 0.25, 0.8, True, ambiguity_requires_review=False)
        == ClassificationStatus.SUCCESS
    )


def test_determine_status_review_when_low_analysis_confidence():
    assert (
        determine_status([], 0.25, 0.69, True, ambiguity_requires_review=False)
        == ClassificationStatus.REVIEW_REQUIRED
    )


def test_determine_status_review_when_low_top_score():
    assert (
        determine_status([], 0.19, 0.9, True, ambiguity_requires_review=False)
        == ClassificationStatus.REVIEW_REQUIRED
    )


def test_determine_status_review_when_ambiguity_flag():
    assert (
        determine_status([], 0.99, 0.99, True, ambiguity_requires_review=True)
        == ClassificationStatus.REVIEW_REQUIRED
    )


def test_determine_status_ignores_lexical_similarity_concept():
    """Patch A: there is no best_similarity parameter — high lexical similarity alone is meaningless here."""
    # Same numeric inputs always yield same status; no hidden similarity gate.
    assert determine_status([], 0.25, 0.8, True, ambiguity_requires_review=False) == ClassificationStatus.SUCCESS


def test_competitive_ambiguity_requires_review_gap():
    c = [
        {"final_score": 0.5},
        {"final_score": 0.45},
    ]
    assert competitive_ambiguity_requires_review(c, score_gap=0.08) is True

    c2 = [
        {"final_score": 0.5},
        {"final_score": 0.35},
    ]
    assert competitive_ambiguity_requires_review(c2, score_gap=0.08) is False


def test_competitive_ambiguity_single_candidate():
    assert competitive_ambiguity_requires_review([{"final_score": 0.4}]) is False


def test_review_explanation_no_lexical_similarity_band_copy():
    """Explanations must not frame outcomes in 0.18 / 0.25 lexical similarity bands."""
    out = generate_review_explanation(
        status=ClassificationStatus.REVIEW_REQUIRED,
        best_similarity=0.10,
        top_candidate_score=0.15,
        analysis_confidence=0.8,
        product_family="generic",
        candidates=[{"hts_code": "1234567890"}],
        reason_code="STANDARD_GATE",
        ambiguity_reason=None,
    )
    joined = " ".join(out["primary_reasons"] + out["what_would_increase_confidence"])
    assert "0.18" not in joined
    assert "high-confidence threshold (0.25)" not in joined
    assert "above minimum threshold" not in joined
    assert "lexical" not in joined.lower()
    assert "pg_trgm" not in joined.lower()


def test_review_explanation_mentions_combined_score_not_similarity_threshold():
    out = generate_review_explanation(
        status=ClassificationStatus.REVIEW_REQUIRED,
        best_similarity=0.99,
        top_candidate_score=0.10,
        analysis_confidence=0.9,
        product_family=None,
        candidates=[{"hts_code": "1111111111"}],
        reason_code="STANDARD_GATE",
        ambiguity_reason=None,
    )
    assert any("combined score" in r.lower() for r in out["primary_reasons"])
    assert any(
        str(MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS) in r for r in out["primary_reasons"]
    )
