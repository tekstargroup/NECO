"""
Patch D — Normalized classification facts (facts before HTS prediction).

Built from product analysis + shipment line context. Persisted per analysis run for
audit, chat, and stable re-runs after user corrections.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.models.shipment import ShipmentItem


def _wrap_fact(
    value: Any,
    *,
    source: str,
    detail: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    ev: Dict[str, Any] = {"source": source}
    if detail:
        ev.update(detail)
    out: Dict[str, Any] = {"value": value, "evidence": ev}
    if confidence is not None:
        out["confidence"] = confidence
    return out


def _extract_attr_value(extracted_attributes: Dict[str, Any], name: str) -> Any:
    raw = extracted_attributes.get(name)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


def _extract_attr_bundle(extracted_attributes: Dict[str, Any], name: str, source: str) -> Dict[str, Any]:
    raw = extracted_attributes.get(name)
    if not isinstance(raw, dict):
        return _wrap_fact(None, source=source, detail={"attribute": name})
    return {
        "value": raw.get("value"),
        "confidence": raw.get("confidence"),
        "evidence": {
            "source": source,
            "attribute": name,
            "source_tokens": raw.get("source_tokens") or [],
        },
    }


def _infer_machine_unit_part_accessory(description_lower: str) -> str:
    if any(
        w in description_lower
        for w in (
            " spare part",
            " replacement part",
            " part only",
            "parts for",
            "component for",
            "subassembly",
        )
    ):
        return "part"
    if any(w in description_lower for w in ("accessory for", "accessories for", "addon", "add-on")):
        return "accessory"
    if any(w in description_lower for w in ("complete machine", "fully assembled", "turnkey")):
        return "machine"
    if "rack mount" in description_lower or "rackmount" in description_lower or "server" in description_lower:
        return "unit"
    return "unknown"


def _infer_energy_domain(extracted_attributes: Dict[str, Any], description_lower: str) -> str:
    if _extract_attr_value(extracted_attributes, "is_electrical") is True:
        return "electrical"
    ps = (_extract_attr_value(extracted_attributes, "power_source") or "").lower() if _extract_attr_value(
        extracted_attributes, "power_source"
    ) else ""
    if ps in ("battery", "usb", "ac_adapter", "wired"):
        return "electronic" if "battery" in ps or "usb" in ps else "electrical"
    if any(
        w in description_lower
        for w in (
            "motor",
            "mechanical",
            "pump",
            "valve",
            "bearing",
            "gear",
            "screw",
            "bolt",
        )
    ):
        if any(e in description_lower for e in ("sensor", "controller", "electronic", "pcb", "circuit")):
            return "mixed"
        return "mechanical"
    if any(e in description_lower for e in ("electronic", "pcb", "semiconductor", "sensor", "controller")):
        return "electronic"
    return "unknown"


def _infer_form_factor(description_lower: str) -> Optional[str]:
    patterns = (
        (r"\brack\s*mount", "rack_mount"),
        (r"\bhandheld", "handheld"),
        (r"\bportable\b", "portable"),
        (r"\bwall\s*mount", "wall_mount"),
        (r"\bdesktop\b", "desktop"),
        (r"\b1u\b|\b2u\b|\b4u\b", "rack_unit"),
    )
    for pat, label in patterns:
        if re.search(pat, description_lower):
            return label
    return None


def _components_guess(description_lower: str) -> List[str]:
    """Lightweight token hints — not exhaustive BOM extraction."""
    hints: List[str] = []
    for term in (
        "battery",
        "charger",
        "adapter",
        "cable",
        "antenna",
        "sensor",
        "display",
        "keyboard",
        "fan",
        "heatsink",
    ):
        if term in description_lower:
            hints.append(term)
    return sorted(set(hints))[:12]


def build_classification_facts_payload(
    *,
    product_analysis: Dict[str, Any],
    shipment_item: ShipmentItem,
    description_used: str,
) -> Dict[str, Any]:
    """
    Normalize facts + evidence pointers from serialized product_analysis and line item.

    This is the durable layer consumed by UI, audit, and future chat — not raw retrieval scores.
    """
    desc_lower = (description_used or "").lower()
    ext = product_analysis.get("extracted_attributes") or {}

    missing = list(product_analysis.get("missing_required_attributes") or [])

    family = product_analysis.get("product_family")
    facts_core: Dict[str, Any] = {
        "product_family": _wrap_fact(
            family,
            source="product_analysis",
            detail={
                "router_rule": product_analysis.get("family_matched_rule"),
                "family_selection_confidence": product_analysis.get("family_selection_confidence"),
            },
            confidence=product_analysis.get("family_selection_confidence"),
        ),
        "principal_function": _extract_attr_bundle(ext, "primary_function", "extracted_attribute"),
        "product_type": _wrap_fact(
            product_analysis.get("product_type"),
            source="product_analysis",
            detail={"field": "product_type"},
        ),
        "machine_unit_part_accessory": _wrap_fact(
            _infer_machine_unit_part_accessory(desc_lower),
            source="inferred",
            detail={"method": "description_heuristic"},
        ),
        "energy_domain": _wrap_fact(
            _infer_energy_domain(ext, desc_lower),
            source="inferred",
            detail={"method": "attributes_and_description"},
        ),
        "material_composition": _extract_attr_bundle(ext, "material_composition", "extracted_attribute"),
        "material": _extract_attr_bundle(ext, "material", "extracted_attribute"),
        "key_included_components": _wrap_fact(
            _components_guess(desc_lower),
            source="inferred",
            detail={"method": "keyword_hints"},
        ),
        "form_factor": _wrap_fact(
            _infer_form_factor(desc_lower),
            source="inferred",
            detail={"method": "description_heuristic"},
        ),
        "country_of_origin": _wrap_fact(
            getattr(shipment_item, "country_of_origin", None),
            source="shipment_item",
            detail={"field": "country_of_origin"},
        ),
    }

    # Optional: power / wireless if present (common gates)
    if "power_source" in ext or _extract_attr_value(ext, "power_source"):
        facts_core["power_source"] = _extract_attr_bundle(ext, "power_source", "extracted_attribute")
    if "wireless_capability" in ext or "wireless" in ext:
        key = "wireless_capability" if "wireless_capability" in ext else "wireless"
        facts_core["wireless"] = _extract_attr_bundle(ext, key, "extracted_attribute")

    payload = {
        "schema_version": "1",
        "facts": facts_core,
        "missing_facts": missing,
        "analysis_confidence": product_analysis.get("analysis_confidence"),
        "rationale": product_analysis.get("rationale"),
        "suggested_chapters": product_analysis.get("suggested_chapters"),
    }
    return payload
