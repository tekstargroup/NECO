"""
Status Model - Finalized Output States (Workstream E)

Defines exactly 4 status states with strict semantics.
No ambiguity allowed.

PATCH A — Memo layer: `ClassificationStatus` is authoritative for trust. Lexical / pg_trgm
`similarity_score` on candidates ranks retrieval only; it must not override SUCCESS/REVIEW_REQUIRED
when `CLASSIFICATION_MEMO_STRICT_STATUS_ALIGNMENT` is enabled in `build_classification_memo`.
"""
from enum import Enum
from typing import Any, Dict, List


class ClassificationStatus(str, Enum):
    """
    Finalized status model with strict definitions.

    Every classification result must fall into exactly one of these states.
    """
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    NO_CONFIDENT_MATCH = "NO_CONFIDENT_MATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUCCESS = "SUCCESS"


# Minimum combined candidate score and analysis confidence for unattended SUCCESS.
# Lexical similarity (pg_trgm) is not used here — it only ranks retrieval.
MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS = 0.20
MIN_ANALYSIS_CONFIDENCE_FOR_SUCCESS = 0.7


def competitive_ambiguity_requires_review(
    final_candidates: List[Dict[str, Any]],
    *,
    score_gap: float = 0.08,
) -> bool:
    """
    True when the top two candidates are close in combined score (unresolved ambiguity).

    Similarity_score / pg_trgm is not consulted — only final_score (candidate quality).
    """
    if len(final_candidates) < 2:
        return False
    s0 = float(final_candidates[0].get("final_score", 0.0))
    s1 = float(final_candidates[1].get("final_score", 0.0))
    return (s0 - s1) <= score_gap


# Status definitions and criteria
STATUS_DEFINITIONS: Dict[ClassificationStatus, Dict[str, Any]] = {
    ClassificationStatus.CLARIFICATION_REQUIRED: {
        "description": "Required classification attributes are missing. Classification cannot proceed.",
        "criteria": [
            "missing_required_attributes is non-empty",
            "No classification has been run",
            "No candidates have been scored"
        ],
        "response": {
            "candidates": [],
            "questions": "List of clarification questions",
            "product_analysis": "Full product analysis output"
        },
        "next_action": "User must provide clarification responses"
    },

    ClassificationStatus.NO_CONFIDENT_MATCH: {
        "description": "No usable HTS candidates were produced from the current inputs (retrieval/scoring empty).",
        "criteria": [
            "No candidates after filtering/scoring",
            "Not driven by low lexical similarity when candidates exist"
        ],
        "response": {
            "candidates": "Usually empty; if present, context-only",
            "note": "Empty candidate set vs. review when alternatives exist"
        },
        "next_action": "Improve inputs or document extraction"
    },

    ClassificationStatus.REVIEW_REQUIRED: {
        "description": "Ambiguity remains but candidates are plausible. Human review recommended.",
        "criteria": [
            "Fact completeness below bar (analysis_confidence < 0.7), or",
            "Candidate quality below SUCCESS bar (top combined score), or",
            "Competitive top candidates (close final scores), or",
            "Family/product-line ambiguity (e.g. multiple plausible subheadings)"
        ],
        "response": {
            "candidates": "Top candidates with scores",
            "ambiguity_reason": "Why review is required"
        },
        "next_action": "Human review recommended before final classification"
    },

    ClassificationStatus.SUCCESS: {
        "description": "Confident classification with resolved attributes and strong candidate quality.",
        "criteria": [
            "All required attributes are resolved (missing_required_attributes is empty)",
            "top_candidate_score >= 0.20 (combined score, not lexical similarity)",
            "analysis_confidence >= 0.7",
            "No competitive ambiguity between top candidates",
            "Candidates exist"
        ],
        "response": {
            "candidates": "Top candidates with full scores",
            "top_candidate_hts": "Recommended HTS code",
            "top_candidate_score": "Top candidate combined score"
        },
        "next_action": "Classification complete - candidates can be persisted"
    }
}


def determine_status(
    missing_required_attributes: List[str],
    top_candidate_score: float,
    analysis_confidence: float,
    candidates_exist: bool,
    *,
    ambiguity_requires_review: bool = False,
) -> ClassificationStatus:
    """
    Determine classification status from fact completeness, candidate quality, and ambiguity.

    Lexical similarity to tariff text is intentionally not a gate — use it for ranking only.

    Args:
        missing_required_attributes: Missing required attributes (blocks all outcomes except CLARIFICATION).
        top_candidate_score: Top candidate combined (final) score.
        analysis_confidence: Product analysis confidence (fact completeness proxy).
        candidates_exist: Whether any scored candidates exist.
        ambiguity_requires_review: Unresolved ambiguity (e.g. competitive top scores).

    Returns:
        ClassificationStatus
    """
    if missing_required_attributes:
        return ClassificationStatus.CLARIFICATION_REQUIRED

    if not candidates_exist:
        return ClassificationStatus.NO_CONFIDENT_MATCH

    meets_success_criteria = (
        top_candidate_score >= MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS
        and analysis_confidence >= MIN_ANALYSIS_CONFIDENCE_FOR_SUCCESS
        and not ambiguity_requires_review
    )

    if meets_success_criteria:
        return ClassificationStatus.SUCCESS

    return ClassificationStatus.REVIEW_REQUIRED


def get_status_definition(status: ClassificationStatus) -> Dict[str, Any]:
    """Get the definition and criteria for a status."""
    return STATUS_DEFINITIONS.get(status, {})
