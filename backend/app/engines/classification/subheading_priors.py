"""
Workstream 4.2-A: Generic Subheading Prior Framework

A deterministic, configuration-driven framework for applying subheading priors
based on product family and HTS prefix patterns.

Rules:
- Prefix-based, not code-specific
- Driven by product_family
- No ML
- Applied after similarity, before final ranking
- Logged per candidate with applied_priors and prior_reason
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from app.engines.classification.required_attributes import ProductFamily


@dataclass
class SubheadingPriorRule:
    """A single subheading prior rule."""
    match: Dict[str, Any]  # e.g., {"hts_prefix": "851830"}
    reason: str  # Explanation for the prior (required field)
    bonus: Optional[float] = None  # Positive bonus value
    penalty: Optional[float] = None  # Negative penalty value (will be applied as negative)
    condition: Optional[Dict[str, Any]] = None  # Optional condition dict for exceptions


# Subheading priors configuration by product family
# Format: product_family -> list of prior rules
SUBHEADING_PRIORS: Dict[ProductFamily, List[SubheadingPriorRule]] = {
    ProductFamily.AUDIO_DEVICES: [
        SubheadingPriorRule(
            match={"hts_prefix": "851830"},
            bonus=0.15,
            reason="Earphones/headphones subheading - preferred for ear-type audio devices"
        ),
        SubheadingPriorRule(
            match={"hts_prefix": "851810"},
            penalty=0.12,
            reason="Microphones subheading - not preferred for ear-type devices unless microphone-centric",
            condition={
                "exception_if": "microphone_centric",  # Can be overridden if product is microphone-centric
                "check_description": ["microphone", "mic", "recording", "voice capture", "audio input"]
            }
        ),
    ],
    # Add more families as needed:
    # ProductFamily.MEDICAL_DEVICES: [
    #     SubheadingPriorRule(...)
    # ],
}


def get_subheading_priors(product_family: ProductFamily) -> List[SubheadingPriorRule]:
    """Get subheading prior rules for a product family."""
    return SUBHEADING_PRIORS.get(product_family, [])


def apply_subheading_prior(
    candidate: Dict[str, Any],
    product_family: ProductFamily,
    description: str,
    product_analysis: Optional[Any] = None
) -> tuple[float, List[str]]:
    """
    Apply subheading priors to a candidate.
    
    Returns:
        (prior_value, applied_prior_reasons)
        - prior_value: total prior adjustment (positive for bonus, negative for penalty)
        - applied_prior_reasons: list of reasons for applied priors
    """
    rules = get_subheading_priors(product_family)
    if not rules:
        return 0.0, []
    
    candidate_code = candidate.get("hts_code", "")
    prior_value = 0.0
    applied_reasons = []
    
    description_lower = description.lower()
    
    for rule in rules:
        # Check if rule matches
        hts_prefix = rule.match.get("hts_prefix")
        if hts_prefix and candidate_code.startswith(hts_prefix):
            # Check for exception conditions
            should_apply = True
            if rule.condition:
                exception_if = rule.condition.get("exception_if")
                if exception_if == "microphone_centric":
                    # Check if product is microphone-centric
                    is_microphone_centric = False
                    if product_analysis and hasattr(product_analysis, 'extracted_attributes'):
                        primary_func = product_analysis.extracted_attributes.get("primary_function")
                        if primary_func and primary_func.value and "microphone" in str(primary_func.value).lower():
                            is_microphone_centric = True
                    
                    # Check description for microphone-dominant signals
                    check_keywords = rule.condition.get("check_description", [])
                    if any(kw in description_lower for kw in check_keywords):
                        is_microphone_centric = True
                    
                    # If microphone-centric, don't apply the penalty
                    if is_microphone_centric:
                        should_apply = False
            
            if should_apply:
                if rule.bonus:
                    prior_value += rule.bonus
                    applied_reasons.append(f"{rule.reason} (bonus: +{rule.bonus:.2f})")
                elif rule.penalty:
                    prior_value -= rule.penalty
                    applied_reasons.append(f"{rule.reason} (penalty: -{rule.penalty:.2f})")
    
    return prior_value, applied_reasons
