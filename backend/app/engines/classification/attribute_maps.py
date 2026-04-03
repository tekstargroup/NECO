"""
Formal Required Attribute Maps for Product Families

Each map defines:
- Required attributes
- Why they matter legally
- Which chapter decision they influence
- Attribute extraction rules
"""
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from app.engines.classification.required_attributes import ProductFamily


@dataclass
class AttributeRequirement:
    """A required attribute with legal rationale and chapter influence."""
    attribute_name: str
    legal_rationale: str  # Why this attribute matters for classification
    chapter_influence: List[str]  # Which chapters this attribute affects
    extraction_keywords: List[str]  # Keywords to look for in description
    value_options: List[str]  # Valid values (if applicable)


# CONSUMER ELECTRONICS
CONSUMER_ELECTRONICS_MAP = {
    "required_attributes": [
        AttributeRequirement(
            attribute_name="power_source",
            legal_rationale="Power source determines whether device is battery-operated (heading 8517) or AC-powered (heading 8517 or 8528). Battery vs AC affects duty rates and classification.",
            chapter_influence=["85"],
            extraction_keywords=["battery", "rechargeable", "AC", "USB", "wired", "adapter", "charger"],
            value_options=["battery", "AC", "USB", "wired", "adapter"]
        ),
        AttributeRequirement(
            attribute_name="primary_function",
            legal_rationale="Primary function determines specific heading within Chapter 85. Communication devices (8517), computing devices (8471), display devices (8528), etc. have different classifications.",
            chapter_influence=["85", "84"],
            extraction_keywords=["communication", "computing", "display", "storage", "processing", "transmission"],
            value_options=["communication", "computing", "display", "storage", "audio", "video"]
        ),
        AttributeRequirement(
            attribute_name="wireless_capability",
            legal_rationale="Wireless capability distinguishes between wired and wireless devices, affecting heading selection within 8517 (wireless communication apparatus) vs other headings.",
            chapter_influence=["85"],
            extraction_keywords=["wireless", "bluetooth", "wifi", "wlan", "cellular", "radio"],
            value_options=["true", "false"]
        ),
    ],
    "product_family": ProductFamily.CONSUMER_ELECTRONICS,
    "primary_chapters": ["85", "84"]
}

# NETWORKING EQUIPMENT
NETWORKING_EQUIPMENT_MAP = {
    "required_attributes": [
        AttributeRequirement(
            attribute_name="network_function",
            legal_rationale="Network function (routing, switching, transmission) determines specific heading within 8517. Routers/switches are 8517.62, modems are 8517.62 or 8517.69.",
            chapter_influence=["85"],
            extraction_keywords=["router", "switch", "modem", "gateway", "access point", "repeater", "bridge"],
            value_options=["routing", "switching", "modulation", "transmission", "access"]
        ),
        AttributeRequirement(
            attribute_name="data_transmission_method",
            legal_rationale="Transmission method (wired vs wireless) affects heading selection. Wireless networking equipment is 8517.62, wired may be 8517.69 or 8517.70.",
            chapter_influence=["85"],
            extraction_keywords=["ethernet", "wifi", "wireless", "fiber", "copper", "cable"],
            value_options=["wired", "wireless", "fiber", "mixed"]
        ),
        AttributeRequirement(
            attribute_name="power_source",
            legal_rationale="Power source (AC vs DC/PoE) affects classification and duty rates. PoE devices may have different treatment than AC-powered.",
            chapter_influence=["85"],
            extraction_keywords=["AC", "DC", "PoE", "power over ethernet", "adapter"],
            value_options=["AC", "DC", "PoE", "adapter"]
        ),
    ],
    "product_family": ProductFamily.NETWORKING_EQUIPMENT,
    "primary_chapters": ["85"]
}

# POWER SUPPLIES / CHARGERS
POWER_SUPPLIES_MAP = {
    "required_attributes": [
        AttributeRequirement(
            attribute_name="output_type",
            legal_rationale="Output type (AC vs DC) determines heading. AC adapters are 8504.40, DC chargers may be 8504.40 or 8516.50 depending on output characteristics.",
            chapter_influence=["85"],
            extraction_keywords=["AC", "DC", "adapter", "charger", "converter", "transformer"],
            value_options=["AC", "DC", "USB", "wireless"]
        ),
        AttributeRequirement(
            attribute_name="power_rating",
            legal_rationale="Power rating (wattage) affects specific heading within 8504. Low power (< 1W) may be 8504.40.90, higher power may be 8504.40.95 or other subheadings.",
            chapter_influence=["85"],
            extraction_keywords=["watt", "W", "voltage", "V", "current", "A", "amp", "power"],
            value_options=[]  # Numeric value
        ),
        AttributeRequirement(
            attribute_name="portable_vs_fixed",
            legal_rationale="Portable vs fixed installation affects classification. Portable chargers/power banks are 8507.60, fixed power supplies are 8504.40.",
            chapter_influence=["85"],
            extraction_keywords=["portable", "mobile", "fixed", "stationary", "wall", "desk"],
            value_options=["portable", "fixed"]
        ),
    ],
    "product_family": ProductFamily.POWER_SUPPLIES,
    "primary_chapters": ["85"]
}

# MEDICAL DEVICES (non-pharma, non-implant)
MEDICAL_DEVICES_MAP = {
    "required_attributes": [
        AttributeRequirement(
            attribute_name="intended_medical_use",
            legal_rationale="Intended use (diagnostic vs therapeutic) determines chapter. Diagnostic devices are typically 9018, therapeutic devices are 9019. Surgical instruments are 9018.90.",
            chapter_influence=["90"],
            extraction_keywords=["diagnostic", "therapeutic", "surgical", "monitoring", "treatment", "therapy"],
            value_options=["diagnostic", "therapeutic", "surgical", "monitoring"]
        ),
        AttributeRequirement(
            attribute_name="is_electrical",
            legal_rationale="Electrical vs non-electrical determines heading within Chapter 90. Electrical medical devices are 9018.11-9018.19 or 9019.10-9019.20, non-electrical are 9018.90 or 9019.90.",
            chapter_influence=["90"],
            extraction_keywords=["electrical", "electronic", "battery", "powered", "AC", "DC"],
            value_options=["true", "false"]
        ),
        AttributeRequirement(
            attribute_name="is_patient_contacting",
            legal_rationale="Patient-contacting devices may have different regulatory requirements and classification. Non-contact devices (imaging) are 9022, contact devices are 9018 or 9019.",
            chapter_influence=["90"],
            extraction_keywords=["patient", "contact", "invasive", "non-invasive", "external", "internal"],
            value_options=["true", "false"]
        ),
        AttributeRequirement(
            attribute_name="is_disposable",
            legal_rationale="Disposable vs reusable affects classification. Disposable medical devices may be classified differently (e.g., 9018.90 vs 9018.11) depending on material and use.",
            chapter_influence=["90"],
            extraction_keywords=["disposable", "single-use", "reusable", "sterile", "sterilization"],
            value_options=["true", "false"]
        ),
    ],
    "product_family": ProductFamily.MEDICAL_DEVICES,
    "primary_chapters": ["90"]
}

ELECTRONICS_COMPUTING_MAP = {
    "required_attributes": CONSUMER_ELECTRONICS_MAP["required_attributes"],
    "product_family": ProductFamily.ELECTRONICS_COMPUTING,
    "primary_chapters": ["84", "85"],
}

# Map product families to their attribute maps
PRODUCT_FAMILY_MAPS: Dict[ProductFamily, Dict[str, Any]] = {
    ProductFamily.CONSUMER_ELECTRONICS: CONSUMER_ELECTRONICS_MAP,
    ProductFamily.ELECTRONICS_COMPUTING: ELECTRONICS_COMPUTING_MAP,
    ProductFamily.NETWORKING_EQUIPMENT: NETWORKING_EQUIPMENT_MAP,
    ProductFamily.POWER_SUPPLIES: POWER_SUPPLIES_MAP,
    ProductFamily.MEDICAL_DEVICES: MEDICAL_DEVICES_MAP,
}


def get_attribute_map(product_family: ProductFamily) -> Dict[str, Any]:
    """Get the formal attribute map for a product family."""
    return PRODUCT_FAMILY_MAPS.get(product_family, {})


def get_required_attributes_with_rationale(product_family: ProductFamily) -> List[AttributeRequirement]:
    """Get required attributes with legal rationale for a product family."""
    attr_map = get_attribute_map(product_family)
    return attr_map.get("required_attributes", [])


def get_primary_chapters(product_family: ProductFamily) -> List[str]:
    """Get primary chapters for a product family."""
    attr_map = get_attribute_map(product_family)
    return attr_map.get("primary_chapters", [])
