"""
PATCH C — Family router for clarification guardrails.

Maps description heuristics → family key and critical attribute set used to filter
``missing_required_attributes`` before CLARIFICATION_REQUIRED short-circuit.
"""

from __future__ import annotations

from typing import FrozenSet, List

# Same logical groups as legacy CRITICAL_ATTRIBUTES_BY_FAMILY; kept centralized for tuning.
CRITICAL_ATTRIBUTES_BY_FAMILY: dict[str, FrozenSet[str]] = {
    "medical": frozenset({"intended_use", "used_on_humans", "disposable"}),
    "textile": frozenset({"material_composition", "fiber_content"}),
    "machinery": frozenset({"intended_use"}),
    "chemical": frozenset({"material_composition"}),
    "default": frozenset({"intended_use", "material"}),
}


def infer_family_key(description: str) -> str:
    d = (description or "").lower()
    if any(kw in d for kw in ("surgical", "endoscop", "medical", "clinical", "patient")):
        return "medical"
    if any(kw in d for kw in ("woven", "knitted", "cotton", "polyester", "fiber", "fabric", "textile")):
        return "textile"
    if any(kw in d for kw in ("machine", "motor", "pump", "cnc", "robot")):
        return "machinery"
    if any(kw in d for kw in ("chemical", "solution", "hydroxide", "acid", "compound")):
        return "chemical"
    return "default"


def critical_missing_for_family(missing_attrs: List[str], description: str) -> List[str]:
    """
    Return missing attributes that are critical for the inferred family (ordering preserved).
    """
    fam = infer_family_key(description)
    critical = CRITICAL_ATTRIBUTES_BY_FAMILY.get(fam, CRITICAL_ATTRIBUTES_BY_FAMILY["default"])
    return [a for a in missing_attrs if a in critical]
