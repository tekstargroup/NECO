"""
Required attributes map for product families.

This is a deterministic, versioned mapping of product families to required
classification attributes. If any required attribute is missing, classification
must be blocked and clarification questions must be asked.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import re


class ProductFamily(str, Enum):
    """Product family categories for attribute requirements."""
    AUDIO_DEVICES = "audio_devices"  # earbuds, headphones, speakers
    APPAREL = "apparel"  # clothing, textiles
    CONTAINERS = "containers"  # bottles, boxes, bags
    CONSUMER_ELECTRONICS = "consumer_electronics"  # phones, tablets, laptops, smart devices
    NETWORKING_EQUIPMENT = "networking_equipment"  # routers, switches, modems, network cards
    POWER_SUPPLIES = "power_supplies"  # chargers, adapters, power banks, transformers
    MEDICAL_DEVICES = "medical_devices"  # non-pharma, non-implant medical equipment
    ELECTRONICS = "electronics"  # generic electronics (fallback)
    FURNITURE = "furniture"  # tables, chairs, beds
    TEXTILES = "textiles"  # fabrics, sheets, towels
    FOOD_CONTAINERS = "food_containers"  # food-grade containers
    FOOTWEAR = "footwear"  # shoes, boots
    ELECTRONICS_COMPUTING = "electronics_computing"  # servers, compute nodes, GPUs
    FASTENERS_HARDWARE = "fasteners_hardware"  # screws, bolts, washers, nuts (Ch. 73–83)
    UNKNOWN = "unknown"  # default fallback


@dataclass(frozen=True)
class FamilySelection:
    """Result of product-family routing (Patch C — confidence + audit trail)."""
    family: ProductFamily
    confidence: float  # 0.0–1.0
    matched_rule: str  # which rule won (for logs / UI)


# Required attributes per product family
REQUIRED_ATTRIBUTES: Dict[ProductFamily, List[str]] = {
    ProductFamily.AUDIO_DEVICES: [
        "power_source",
        "wireless",
        "housing_material",
    ],
    ProductFamily.APPAREL: [
        "material_composition",
        "knit_or_woven",
        "gender_or_age",
    ],
    ProductFamily.CONTAINERS: [
        "material",
        "capacity_relevance",
        "food_grade",
    ],
    ProductFamily.FOOD_CONTAINERS: [
        "material",
        "food_grade",
        "capacity_relevance",
    ],
    ProductFamily.CONSUMER_ELECTRONICS: [
        "power_source",
        "primary_function",
        "wireless_capability",
    ],
    ProductFamily.ELECTRONICS_COMPUTING: [
        "power_source",
        "primary_function",
        "wireless_capability",
    ],
    ProductFamily.NETWORKING_EQUIPMENT: [
        "network_function",
        "data_transmission_method",
        "power_source",
    ],
    ProductFamily.POWER_SUPPLIES: [
        "output_type",
        "power_rating",
        "portable_vs_fixed",
    ],
    ProductFamily.MEDICAL_DEVICES: [
        "intended_medical_use",
        "is_electrical",
        "is_patient_contacting",
        "is_disposable",
    ],
    ProductFamily.ELECTRONICS: [
        "power_source",
        "primary_function",
    ],
    ProductFamily.FURNITURE: [
        "material",
        "primary_use",
    ],
    ProductFamily.TEXTILES: [
        "material_composition",
        "knit_or_woven",
        "end_use",
    ],
    ProductFamily.FOOTWEAR: [
        "material_composition",
        "gender_or_age",
        "upper_material",
    ],
    ProductFamily.FASTENERS_HARDWARE: [
        "material",
        "fastener_category",
    ],
    ProductFamily.UNKNOWN: [],
}


ATTRIBUTE_QUESTIONS: Dict[str, str] = {
    "power_source": "What is the power source for this device (battery, wired, USB, AC adapter, other)? This determines whether the device is battery-operated or AC-powered, which affects duty rates and classification.",
    "wireless": "Is this device wireless (yes/no)? Wireless capability distinguishes between wired and wireless devices, affecting heading selection within Chapter 85.",
    "wireless_capability": "Does this device have wireless capability (yes/no)? This affects heading selection within Chapter 85 (wireless communication apparatus vs other headings).",
    "housing_material": "What is the primary material of the device housing (plastic, metal, other)? Material affects classification and duty rates for audio devices.",
    "material_composition": "What is the material composition (e.g., 100% cotton, polyester blend, etc.)? Material composition determines classification within Chapters 61-63.",
    "knit_or_woven": "Is the fabric knit or woven? This determines whether the item is classified in Chapter 61 (knit) or Chapter 62 (woven).",
    "gender_or_age": "What is the target gender or age group (men's, women's, children's, unisex)? Gender/age affects specific heading selection within Chapters 61-64.",
    "material": "What is the primary material (plastic, glass, metal, wood, other)? Material determines the chapter (e.g., plastic=39, glass=70, metal=73-76, wood=44).",
    "capacity_relevance": "Does the capacity or size affect the classification (yes/no)?",
    "food_grade": "Is this container food-grade or food-safe (yes/no/not applicable)?",
    "primary_function": "What is the primary function of this device (communication, computing, display, storage, audio, video)? Primary function determines specific heading within Chapter 85 or 84.",
    "network_function": "What is the network function (routing, switching, modulation, transmission, access)? This determines specific heading within 8517 (routers/switches are 8517.62, modems are 8517.62 or 8517.69).",
    "data_transmission_method": "What is the data transmission method (wired, wireless, fiber, mixed)? Transmission method affects heading selection - wireless networking equipment is 8517.62, wired may be 8517.69 or 8517.70.",
    "output_type": "What is the output type (AC, DC, USB, wireless)? Output type determines heading - AC adapters are 8504.40, DC chargers may be 8504.40 or 8516.50.",
    "power_rating": "What is the power rating in watts? Power rating affects specific heading within 8504 - low power (< 1W) may be 8504.40.90, higher power may be 8504.40.95.",
    "portable_vs_fixed": "Is this device portable or fixed installation (portable/fixed)? Portable chargers/power banks are 8507.60, fixed power supplies are 8504.40.",
    "intended_medical_use": "What is the intended medical use (diagnostic, therapeutic, surgical, monitoring)? Intended use determines chapter - diagnostic devices are typically 9018, therapeutic devices are 9019.",
    "is_electrical": "Is this device electrical (yes/no)? Electrical vs non-electrical determines heading within Chapter 90 - electrical medical devices are 9018.11-9018.19 or 9019.10-9019.20.",
    "is_patient_contacting": "Does this device contact the patient (yes/no)? Patient-contacting devices may have different classification - non-contact devices (imaging) are 9022, contact devices are 9018 or 9019.",
    "is_disposable": "Is this device disposable or single-use (yes/no)? Disposable vs reusable affects classification - disposable medical devices may be classified differently depending on material and use.",
    "primary_use": "What is the primary use of this furniture item?",
    "end_use": "What is the end use of this textile (bedding, clothing, household, other)?",
    "upper_material": "What is the material of the upper part of the footwear?",
    "fastener_category": "What type of fastener is this (machine screw, wood screw, bolt, nut, washer, rivet, other)? Head style and drive type affect classification in Chapters 73–83.",
}


# Family-specific wording overrides (legal / HTS context). Fallback: ATTRIBUTE_QUESTIONS[attr].
FAMILY_ATTRIBUTE_QUESTION_OVERRIDES: Dict[Tuple[ProductFamily, str], str] = {
    (ProductFamily.MEDICAL_DEVICES, "intended_medical_use"): (
        "For Chapter 90 medical apparatus: is this primarily diagnostic, therapeutic, surgical, or patient monitoring? "
        "The intended clinical use drives whether headings 9018, 9019, or 9020 apply."
    ),
    (ProductFamily.MEDICAL_DEVICES, "is_electrical"): (
        "Is this apparatus electrically powered (yes/no)? Electrical vs non-electrical apparatus splits headings within Chapter 90."
    ),
    (ProductFamily.FOOD_CONTAINERS, "food_grade"): (
        "Will this container contact food or beverages for human consumption (yes/no)? Food-contact articles are classified differently than general plastic or metal articles."
    ),
    (ProductFamily.FOOD_CONTAINERS, "material"): (
        "What is the primary material of this food-contact container (plastic, glass, metal, coated paper)? Material determines whether Chapter 39, 70, 73/76, or 48 applies."
    ),
    (ProductFamily.CONTAINERS, "material"): (
        "What is the primary material of this container (plastic, glass, metal, wood, other)? For general containers, material selects among Chapters 39, 44, 70, 73, 76."
    ),
    (ProductFamily.CONTAINERS, "food_grade"): (
        "Is this container intended for food or beverage contact (yes/no/not applicable)? Food/beverage use can move classification toward food-contact provisions."
    ),
    (ProductFamily.ELECTRONICS_COMPUTING, "primary_function"): (
        "What is the primary function of this computing product (e.g., data processing server, storage appliance, GPU compute unit, network-attached storage)? "
        "Chapter 84 (ADP, 8471) vs parts/accessories depends on whether the good is a complete machine or a specific part."
    ),
    (ProductFamily.ELECTRONICS_COMPUTING, "power_source"): (
        "How is this unit powered (AC rack PSU, redundant supplies, DC bus, other)? Power entry configuration affects accessories vs complete machine treatment."
    ),
    (ProductFamily.FASTENERS_HARDWARE, "material"): (
        "What is the base metal or material of the fastener (steel, stainless steel, brass, aluminum, other)? Chapter 73 vs 74 vs 83 depends on base metal and article form."
    ),
    (ProductFamily.FASTENERS_HARDWARE, "fastener_category"): (
        "Describe the fastener form (machine screw, cap screw, hex bolt, nut, lock washer, rivet, etc.). Thread pitch and head/drive style affect subheading within Chapters 73–83."
    ),
    (ProductFamily.ELECTRONICS, "primary_function"): (
        "What is the primary electrical function (sensing, switching, measuring, signaling)? Industrial sensors and instruments often fall under Chapter 85 or 90 depending on function."
    ),
    (ProductFamily.ELECTRONICS, "power_source"): (
        "How is this apparatus powered (loop-powered 4–20mA, DC supply, battery, other)? Supply type affects whether the good is classified as the instrument or as a part."
    ),
}


def get_required_attributes(product_family: ProductFamily) -> List[str]:
    """Get required attributes for a product family."""
    return REQUIRED_ATTRIBUTES.get(product_family, [])


def get_question_for_attribute(attribute: str) -> str:
    """Legacy: question for attribute without family context."""
    return ATTRIBUTE_QUESTIONS.get(attribute, f"What is the {attribute}?")


def get_question_for_family_attribute(product_family: ProductFamily, attribute: str) -> str:
    """
    Clarification question with legal/HTS context for the resolved product family.

    Prefer family-specific wording; fall back to generic ATTRIBUTE_QUESTIONS.
    """
    override = FAMILY_ATTRIBUTE_QUESTION_OVERRIDES.get((product_family, attribute))
    if override:
        return override
    return ATTRIBUTE_QUESTIONS.get(attribute, f"What is the {attribute.replace('_', ' ')}?")


# --- Patch C: rule-first router + keyword fallback ---------------------------------

_COMPUTE_TOKENS: Tuple[str, ...] = (
    "server",
    "rack server",
    "rackmount",
    "rack mount",
    "gpu",
    "cpu",
    # Note: do not use bare "compute" — it matches inside "computer" and misroutes monitors.
    "compute node",
    "compute module",
    "computing",
    "data center",
    "datacenter",
    "blade server",
    "blade",
    "workstation",
    "motherboard",
    "chassis",
    "hyperconverged",
    "storage server",
    "storage array",
    "system unit",
    "computer system",
    "enterprise server",
)

_DISPLAY_MONITOR_MARKERS: Tuple[str, ...] = (
    "lcd",
    "led",
    "oled",
    "hdmi",
    "displayport",
    "4k",
    "uhd",
    "computer monitor",
    "monitor for",
    "gaming monitor",
    "hd monitor",
)

_MEDICAL_STRONG: Tuple[str, ...] = (
    "medical device",
    "medical equipment",
    "surgical",
    "patient monitor",
    "vital sign",
    "diagnostic",
    "therapeutic",
    "infusion",
    "sterile",
    "hospital",
    "clinical",
    "stethoscope",
    "defibrillator",
    "endoscope",
    "fda",
    "510(k)",
    "implant",
)

_ELECTRONICS_STRONG: Tuple[str, ...] = (
    "electronic",
    "sensor",
    "transducer",
    "plc",
    "i/o module",
    "industrial control",
)


def _has_any(hay: str, needles: Tuple[str, ...]) -> bool:
    return any(n in hay for n in needles)


def _word_re(pattern: str, hay: str) -> bool:
    return re.search(pattern, hay, re.IGNORECASE) is not None


def _electronics_or_compute_context(desc: str) -> bool:
    return _has_any(desc, _COMPUTE_TOKENS) or _has_any(desc, _ELECTRONICS_STRONG) or _has_any(
        desc,
        ("router", "switch", "modem", "ethernet", "processor", "microcontroller", "controller card"),
    )


def _medical_route_allowed(desc: str) -> bool:
    """Do not route to medical on weak tokens like 'monitor' or 'device' alone."""
    if _has_any(desc, _MEDICAL_STRONG):
        return True
    if "monitor" in desc and not _has_any(desc, _DISPLAY_MONITOR_MARKERS):
        if "patient" in desc or "vital" in desc or "medical" in desc or "clinical" in desc:
            return True
        return False
    if "device" in desc and not _has_any(desc, ("medical", "surgical", "patient", "diagnostic", "therapeutic", "hospital", "clinical")):
        return False
    return False


def _food_container_strong(desc: str) -> bool:
    fk = ("food", "beverage", "drink", "water bottle", "milk", "juice", "edible", "food-grade", "food grade")
    return any(k in desc for k in fk)


def select_product_family(description: str, extracted_attributes: Optional[Dict[str, Any]] = None) -> FamilySelection:
    """
    Rule-first product family selection with confidence scores.

    Uses explicit high-precision rules before the legacy keyword router.
    `extracted_attributes` can disambiguate when the user or extraction provided fields.
    """
    extracted_attributes = extracted_attributes or {}
    desc = (description or "").lower().strip()
    if not desc:
        return FamilySelection(ProductFamily.UNKNOWN, 0.2, "empty_description")

    # Extracted hints (clarification / prior extraction)
    mat = extracted_attributes.get("material")
    if isinstance(mat, str) and mat:
        mat_l = mat.lower()
    else:
        mat_l = ""

    intended = str(extracted_attributes.get("intended_medical_use", "") or "").lower()
    if "diagnostic" in intended or "surgical" in intended or "therapeutic" in intended:
        return FamilySelection(ProductFamily.MEDICAL_DEVICES, 0.88, "extracted_intended_medical_use")

    # Rule 1 — Fasteners (before generic "container" / "bottle")
    # Exclude bottle/jar closures: "screw cap" on a bottle is not a fastener article.
    _fastener_m = _word_re(
        r"\b(screws?|bolts?|washers?|nuts?|rivets?|fasteners?|hex\s*head|socket\s*cap)\b",
        desc,
    )
    _bottle_closure = ("bottle" in desc or "jar" in desc) and "screw" in desc and "cap" in desc
    if _fastener_m and not _bottle_closure:
        return FamilySelection(ProductFamily.FASTENERS_HARDWARE, 0.9, "rule_fasteners_hardware")

    # Rule 2 — Computing / servers
    if _has_any(desc, _COMPUTE_TOKENS):
        return FamilySelection(ProductFamily.ELECTRONICS_COMPUTING, 0.92, "rule_computing_server")

    # Rule 3 — Industrial sensors & process transmitters (not medical)
    #
    # BACKLOG / TAXONOMY: Today this maps to generic ProductFamily.ELECTRONICS so clarification
    # and attribute gates stay in Chapter 85-ish territory. Many of these goods are legally
    # borderline vs Chapter 90 (measuring instruments). When we add an explicit
    # instruments/measuring family (or heading-level split), re-home this rule — do not
    # treat ELECTRONICS here as a permanent legal endpoint.
    #
    # Phrases: pressure/flow/level/temperature transmitters and common industrial instrument wording.
    if any(
        p in desc
        for p in (
            "pressure sensor",
            "pressure transducer",
            "pressure transmitter",
            "differential pressure transmitter",
            "temperature transmitter",
            "flow transmitter",
            "level transmitter",
            "load cell",
            "strain gauge",
            "industrial sensor",
            "industrial transmitter",
            "proximity sensor",
        )
    ):
        return FamilySelection(ProductFamily.ELECTRONICS, 0.86, "rule_industrial_sensor")

    # Rule 4 — Audio
    audio_keywords = (
        "earbud",
        "headphone",
        "earphone",
        "speaker",
        "audio",
        "sound",
        "bluetooth",
        "wireless audio",
    )
    if any(kw in desc for kw in audio_keywords):
        return FamilySelection(ProductFamily.AUDIO_DEVICES, 0.85, "keyword_audio")

    # Rule 5 — Apparel
    apparel_keywords = (
        "shirt",
        "t-shirt",
        "pants",
        "dress",
        "jacket",
        "sweater",
        "apparel",
        "clothing",
        "garment",
    )
    if any(kw in desc for kw in apparel_keywords):
        return FamilySelection(ProductFamily.APPAREL, 0.82, "keyword_apparel")

    # Rule 6 — Containers (guardrail: not electronics context)
    container_markers = (
        "bottle",
        "jar",
        "can ",
        "container",
        "tumbler",
        "flask",
        "vessel",
        "box",
        "bag",
    )
    if any(m in desc for m in container_markers) and not _electronics_or_compute_context(desc):
        reusable = "reusable" in desc or "refillable" in desc
        if _food_container_strong(desc):
            conf = 0.88 if reusable else 0.82
            return FamilySelection(ProductFamily.FOOD_CONTAINERS, conf, "rule_food_or_beverage_container")
        if reusable and ("bottle" in desc or "tumbler" in desc):
            return FamilySelection(ProductFamily.CONTAINERS, 0.84, "rule_reusable_bottle")
        if "bottle" in desc or "jar" in desc or "container" in desc:
            return FamilySelection(ProductFamily.CONTAINERS, 0.78, "keyword_container_general")
        return FamilySelection(ProductFamily.CONTAINERS, 0.75, "keyword_container")

    # Rule 7 — Medical (strict — no weak 'monitor' / bare 'device')
    medical_keywords = (
        "medical",
        "diagnostic",
        "therapeutic",
        "surgical",
        "patient",
        "hospital",
        "clinic",
        "stethoscope",
        "thermometer",
        "heart rate",
        "pulse ox",
        "oximeter",
        "infusion pump",
    )
    if any(kw in desc for kw in medical_keywords) and _medical_route_allowed(desc):
        return FamilySelection(ProductFamily.MEDICAL_DEVICES, 0.87, "keyword_medical_strict")

    # Networking
    networking_keywords = (
        "router",
        "switch",
        "modem",
        "gateway",
        "access point",
        "network",
        "ethernet",
        "wifi",
        "wireless router",
    )
    if any(kw in desc for kw in networking_keywords):
        return FamilySelection(ProductFamily.NETWORKING_EQUIPMENT, 0.86, "keyword_networking")

    # Power supplies
    power_keywords = (
        "charger",
        "adapter",
        "power supply",
        "power bank",
        "transformer",
        "converter",
        "ac adapter",
        "dc adapter",
    )
    if any(kw in desc for kw in power_keywords):
        return FamilySelection(ProductFamily.POWER_SUPPLIES, 0.84, "keyword_power")

    # Consumer electronics (displays — not patient monitors)
    consumer_keywords = (
        "smartphone",
        "phone",
        "tablet",
        "laptop",
        "computer",
        "smart watch",
        "smart device",
        "display",
        "monitor",
    )
    if any(kw in desc for kw in consumer_keywords):
        if "monitor" in desc and _has_any(desc, _DISPLAY_MONITOR_MARKERS):
            return FamilySelection(ProductFamily.CONSUMER_ELECTRONICS, 0.83, "keyword_display_monitor")
        if "monitor" in desc and not _has_any(desc, _DISPLAY_MONITOR_MARKERS):
            if _medical_route_allowed(desc):
                return FamilySelection(ProductFamily.MEDICAL_DEVICES, 0.8, "keyword_monitor_medical_context")
            return FamilySelection(ProductFamily.CONSUMER_ELECTRONICS, 0.72, "keyword_monitor_ambiguous")
        return FamilySelection(ProductFamily.CONSUMER_ELECTRONICS, 0.82, "keyword_consumer_electronics")

    # Generic electronics
    if "electronic" in desc or ("device" in desc and _electronics_or_compute_context(desc)):
        return FamilySelection(ProductFamily.ELECTRONICS, 0.68, "keyword_electronics_generic")

    # Furniture
    furniture_keywords = ("table", "chair", "desk", "bed", "sofa", "cabinet", "furniture")
    if any(kw in desc for kw in furniture_keywords):
        return FamilySelection(ProductFamily.FURNITURE, 0.8, "keyword_furniture")

    # Textiles
    textile_keywords = ("sheet", "towel", "fabric", "textile", "cloth", "linen")
    if any(kw in desc for kw in textile_keywords):
        return FamilySelection(ProductFamily.TEXTILES, 0.78, "keyword_textiles")

    # Footwear
    footwear_keywords = ("shoe", "boot", "sandal", "sneaker", "footwear")
    if any(kw in desc for kw in footwear_keywords):
        return FamilySelection(ProductFamily.FOOTWEAR, 0.8, "keyword_footwear")

    # Metal material + no better rule → lean hardware (optional hint)
    if mat_l and any(m in mat_l for m in ("steel", "stainless", "brass", "aluminum")):
        if any(w in desc for w in ("bolt", "screw", "washer", "nut")):
            return FamilySelection(ProductFamily.FASTENERS_HARDWARE, 0.75, "extracted_metal_plus_fastener_word")

    return FamilySelection(ProductFamily.UNKNOWN, 0.45, "no_rule_matched")


def identify_product_family(description: str, extracted_attributes: Dict) -> ProductFamily:
    """Backward-compatible: returns only the family enum."""
    return select_product_family(description, extracted_attributes or {}).family
