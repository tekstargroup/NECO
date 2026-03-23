"""
Status Model - Finalized Output States (Workstream E)

Defines exactly 4 status states with strict semantics.
No ambiguity allowed.
"""
from enum import Enum
from typing import Dict, Any, Optional, List


class ClassificationStatus(str, Enum):
    """
    Finalized status model with strict definitions.
    
    Every classification result must fall into exactly one of these states.
    """
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    NO_CONFIDENT_MATCH = "NO_CONFIDENT_MATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUCCESS = "SUCCESS"


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
        "description": "Best similarity score is below confidence threshold. No confident match available.",
        "criteria": [
            "best_similarity < 0.18",
            "Classification was attempted",
            "Candidates were scored but none meet confidence threshold"
        ],
        "response": {
            "candidates": "Top 5 candidates as 'untrusted' for human review",
            "best_similarity": "Best similarity score",
            "threshold_used": "0.18"
        },
        "next_action": "Human review required - candidates are untrusted"
    },
    
    ClassificationStatus.REVIEW_REQUIRED: {
        "description": "Ambiguity remains but candidates are plausible. Human review recommended.",
        "criteria": [
            "best_similarity >= 0.18 but < 0.25",
            "OR multiple candidates with similar scores",
            "OR analysis_confidence < 0.7",
            "Classification was attempted and candidates exist"
        ],
        "response": {
            "candidates": "Top candidates with scores",
            "best_similarity": "Best similarity score",
            "ambiguity_reason": "Why review is required"
        },
        "next_action": "Human review recommended before final classification"
    },
    
    ClassificationStatus.SUCCESS: {
        "description": "Confident classification with resolved attributes and high-quality candidates.",
        "criteria": [
            "All required attributes are resolved (missing_required_attributes is empty)",
            "best_similarity >= 0.25",
            "top_candidate_score >= 0.20",
            "analysis_confidence >= 0.7"
        ],
        "response": {
            "candidates": "Top candidates with full scores",
            "top_candidate_hts": "Recommended HTS code",
            "top_candidate_score": "Top candidate score"
        },
        "next_action": "Classification complete - candidates can be persisted"
    }
}


def determine_status(
    missing_required_attributes: List[str],
    best_similarity: float,
    top_candidate_score: float,
    analysis_confidence: float,
    candidates_exist: bool
) -> ClassificationStatus:
    """
    Determine classification status based on strict criteria.
    
    Args:
        missing_required_attributes: List of missing required attributes
        best_similarity: Best similarity score from candidates
        top_candidate_score: Top candidate final score
        analysis_confidence: Product analysis confidence
        candidates_exist: Whether any candidates were found
    
    Returns:
        ClassificationStatus
    """
    # CLARIFICATION_REQUIRED: Missing required attributes
    if missing_required_attributes:
        return ClassificationStatus.CLARIFICATION_REQUIRED
    
    # NO_CONFIDENT_MATCH: Best similarity below threshold
    if best_similarity < 0.18:
        return ClassificationStatus.NO_CONFIDENT_MATCH
    
    # REVIEW_REQUIRED: Ambiguity but plausible candidates
    # Conditions:
    # 1. Attributes are resolved (already checked above)
    # 2. Candidates are plausible (best_similarity >= 0.18)
    # 3. Confidence is mid-range (best_similarity < 0.25 OR analysis_confidence < 0.7)
    # 4. But not high enough for SUCCESS
    
    # Check if we meet SUCCESS criteria first
    meets_success_criteria = (
        best_similarity >= 0.25 and 
        top_candidate_score >= 0.20 and 
        analysis_confidence >= 0.7 and
        candidates_exist
    )
    
    if meets_success_criteria:
        return ClassificationStatus.SUCCESS
    
    # If not SUCCESS, check for REVIEW_REQUIRED
    # REVIEW_REQUIRED: Attributes resolved, similarity >= 0.18, but either:
    # - Similarity is mid-range (0.18 <= similarity < 0.25), OR
    # - Analysis confidence is low (< 0.7)
    if best_similarity >= 0.18:
        if best_similarity < 0.25 or analysis_confidence < 0.7:
            return ClassificationStatus.REVIEW_REQUIRED
    
    # Default fallback
    if candidates_exist:
        return ClassificationStatus.REVIEW_REQUIRED
    else:
        return ClassificationStatus.NO_CONFIDENT_MATCH


def get_status_definition(status: ClassificationStatus) -> Dict[str, Any]:
    """Get the definition and criteria for a status."""
    return STATUS_DEFINITIONS.get(status, {})
