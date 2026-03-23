"""
Workstream 4.2-B: REVIEW_REQUIRED Explanation Layer

Generates deterministic, structured explanations for why review is required.
Each reason maps to a known gate or rule.
"""

from typing import Dict, List, Optional, Any
from app.engines.classification.status_model import ClassificationStatus


def generate_review_explanation(
    status: ClassificationStatus,
    best_similarity: float,
    top_candidate_score: float,
    analysis_confidence: float,
    product_family: Optional[str],
    candidates: List[Dict],
    reason_code: Optional[str],
    best_8518_similarity: Optional[float] = None,
    missing_required_attributes: Optional[List[str]] = None,
    ambiguity_reason: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Generate structured explanation for REVIEW_REQUIRED status.
    
    Rules:
    - Deterministic
    - Driven by gates that triggered REVIEW_REQUIRED
    - No free-form AI text
    - Each reason maps to a known gate or rule
    
    Returns:
        {
            "primary_reasons": [...],
            "what_would_increase_confidence": [...]
        }
    """
    primary_reasons = []
    what_would_increase_confidence = []
    
    # Reason 1: Similarity below high-confidence threshold
    if best_similarity >= 0.18 and best_similarity < 0.25:
        primary_reasons.append(
            f"Similarity score ({best_similarity:.3f}) is above minimum threshold but below high-confidence threshold (0.25)"
        )
        what_would_increase_confidence.append(
            "Provide more detailed product description with specific technical specifications"
        )
    
    # Reason 2: Multiple plausible subheadings
    if product_family == "audio_devices" and candidates:
        hts_codes = [c.get("hts_code", "") for c in candidates[:3]]
        # Check if multiple different subheadings are present
        subheadings = set()
        for code in hts_codes:
            if code.startswith("8518"):
                # Extract subheading (e.g., "851830" from "8518301000")
                if len(code) >= 6:
                    subheading = code[:6]
                    subheadings.add(subheading)
        
        if len(subheadings) > 1:
            primary_reasons.append(
                f"Multiple plausible subheadings within the same heading (8518): {', '.join(sorted(subheadings))}"
            )
            what_would_increase_confidence.append(
                "Confirm the primary function: Is this primarily an earphone/headphone device or a microphone device?"
            )
    
    # Reason 3: Analysis confidence below threshold
    if analysis_confidence < 0.7:
        primary_reasons.append(
            f"Product analysis confidence ({analysis_confidence:.2f}) is below high-confidence threshold (0.70)"
        )
        what_would_increase_confidence.append(
            "Provide more explicit product attributes in the description"
        )
    
    # Reason 4: Ambiguity reasons from status determination
    if ambiguity_reason:
        for reason in ambiguity_reason:
            if reason not in primary_reasons:
                primary_reasons.append(reason)
    
    # Reason 5: Family-aware gate (audio with 8518 candidates)
    if reason_code == "FAMILY_AWARE_GATE_8518":
        primary_reasons.append(
            "Multiple plausible candidates within audio device heading (8518) with acceptable similarity"
        )
        if best_8518_similarity:
            primary_reasons.append(
                f"Best 8518 candidate similarity ({best_8518_similarity:.3f}) is above family-aware threshold (0.16) but requires review"
            )
        what_would_increase_confidence.append(
            "Clarify specific subheading: Confirm whether device is primarily earphones/headphones (8518.30) or microphone (8518.10)"
        )
    
    # Reason 6: Standard gate with multiple candidates
    if reason_code == "STANDARD_GATE" and len(candidates) > 1:
        if not any("Multiple plausible" in r for r in primary_reasons):
            primary_reasons.append(
                "Multiple candidates with similar scores, requiring human review to select the most appropriate classification"
            )
        what_would_increase_confidence.append(
            "Provide additional product specifications or intended use details to narrow classification"
        )
    
    # Reason 7: Top candidate score below strong confidence
    if top_candidate_score < 0.25:
        primary_reasons.append(
            f"Top candidate final score ({top_candidate_score:.3f}) is below strong confidence threshold (0.25)"
        )
        if "Provide more detailed" not in str(what_would_increase_confidence):
            what_would_increase_confidence.append(
                "Provide more detailed product description with specific technical specifications"
            )
    
    # Ensure at least one reason exists (Workstream 4.2-C invariant)
    if not primary_reasons:
        primary_reasons.append(
            "Classification requires review due to multiple plausible options or moderate confidence levels"
        )
    
    # Ensure at least one actionable clarification exists
    if not what_would_increase_confidence:
        what_would_increase_confidence.append(
            "Provide additional product details or specifications to increase classification confidence"
        )
    
    return {
        "primary_reasons": primary_reasons,
        "what_would_increase_confidence": what_would_increase_confidence
    }
