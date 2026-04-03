"""
Workstream 4.2-B: REVIEW_REQUIRED Explanation Layer

Generates deterministic, structured explanations for why review is required.
Each reason maps to a known gate or rule (not lexical similarity bands).
"""

from typing import Any, Dict, List, Optional

from app.engines.classification.status_model import ClassificationStatus, MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS


def generate_review_explanation(
    status: ClassificationStatus,
    best_similarity: float,
    top_candidate_score: float,
    analysis_confidence: float,
    product_family: Optional[str],
    candidates: List[Dict[str, Any]],
    reason_code: Optional[str],
    best_8518_similarity: Optional[float] = None,
    missing_required_attributes: Optional[List[str]] = None,
    ambiguity_reason: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    Generate structured explanation for REVIEW_REQUIRED status.

    Rules:
    - Deterministic
    - Driven by gates that triggered REVIEW_REQUIRED
    - No free-form AI text
    - Lexical similarity (best_similarity) is diagnostic only — not framed as success/failure bands

    Returns:
        {
            "primary_reasons": [...],
            "what_would_increase_confidence": [...]
        }
    """
    _ = best_similarity  # Retained for API compatibility; explanations do not use similarity bands.
    _ = best_8518_similarity

    primary_reasons = []
    what_would_increase_confidence = []

    # Multiple plausible subheadings (audio / 8518)
    if product_family == "audio_devices" and candidates:
        hts_codes = [c.get("hts_code", "") for c in candidates[:3]]
        subheadings = set()
        for code in hts_codes:
            if code.startswith("8518") and len(code) >= 6:
                subheadings.add(code[:6])

        if len(subheadings) > 1:
            primary_reasons.append(
                f"Multiple plausible subheadings within heading 8518: {', '.join(sorted(subheadings))}"
            )
            what_would_increase_confidence.append(
                "Confirm the primary function: Is this primarily an earphone/headphone device or a microphone device?"
            )

    # Engine-provided structured notes first (avoid duplicating the same gate below)
    if ambiguity_reason:
        for reason in ambiguity_reason:
            if reason not in primary_reasons:
                primary_reasons.append(reason)

    # Analysis confidence (fact completeness)
    if analysis_confidence < 0.7 and not any(
        "Product analysis confidence" in r for r in primary_reasons
    ):
        primary_reasons.append(
            f"Product analysis confidence ({analysis_confidence:.2f}) is below the level "
            "used for unattended classification (0.70)"
        )
        what_would_increase_confidence.append(
            "Provide more explicit product attributes in the description"
        )

    # Family-aware gate (multiple 8518 lines)
    if reason_code == "FAMILY_AWARE_GATE_8518":
        if not any("8518" in r for r in primary_reasons):
            primary_reasons.append(
                "Multiple plausible candidates within audio device heading (8518); human review is required."
            )
        what_would_increase_confidence.append(
            "Clarify specific subheading: Confirm whether the device is primarily earphones/headphones (8518.30) "
            "or a microphone (8518.10)"
        )

    # Standard gate with multiple candidates
    if reason_code == "STANDARD_GATE" and len(candidates) > 1:
        if not any("Multiple plausible" in r or "close combined" in r for r in primary_reasons):
            primary_reasons.append(
                "Multiple candidates with similar combined scores; human review is needed to select the best line."
            )
        what_would_increase_confidence.append(
            "Provide additional product specifications or intended use details to narrow classification"
        )

    # Top candidate combined score (quality), aligned with status_model / quality gate
    if top_candidate_score < MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS and not any(
        "Top candidate combined score" in r for r in primary_reasons
    ):
        primary_reasons.append(
            f"Top candidate combined score ({top_candidate_score:.3f}) is below the level "
            f"used for unattended classification ({MIN_TOP_CANDIDATE_SCORE_FOR_SUCCESS:.2f})"
        )
        if "Provide more explicit" not in str(what_would_increase_confidence):
            what_would_increase_confidence.append(
                "Provide more detailed product description with specific technical specifications"
            )

    # Ensure at least one reason exists (Workstream 4.2-C invariant)
    if not primary_reasons:
        primary_reasons.append(
            "Classification requires review: candidate quality, fact completeness, or unresolved ambiguity."
        )

    # Ensure at least one actionable clarification exists
    if not what_would_increase_confidence:
        what_would_increase_confidence.append(
            "Provide additional product details or specifications to increase classification confidence"
        )

    return {
        "primary_reasons": primary_reasons,
        "what_would_increase_confidence": what_would_increase_confidence,
    }
