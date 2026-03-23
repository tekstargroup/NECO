"""
Required attributes map for product families.

This is a deterministic, versioned mapping of product families to required
classification attributes. If any required attribute is missing, classification
must be blocked and clarification questions must be asked.
"""
from typing import Dict, List, Set
from enum import Enum


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
    UNKNOWN = "unknown"  # default fallback


# Required attributes per product family
REQUIRED_ATTRIBUTES: Dict[ProductFamily, List[str]] = {
    ProductFamily.AUDIO_DEVICES: [
        "power_source",  # battery, wired, USB, etc.
        "wireless",  # true/false
        "housing_material",  # plastic, metal, other
    ],
    ProductFamily.APPAREL: [
        "material_composition",  # cotton, polyester, blend, etc.
        "knit_or_woven",  # knit, woven, or null if not applicable
        "gender_or_age",  # men's, women's, children's, unisex
    ],
    ProductFamily.CONTAINERS: [
        "material",  # plastic, glass, metal, etc.
        "capacity_relevance",  # true if capacity matters for classification
        "food_grade",  # true/false/null if food-safe
    ],
    ProductFamily.FOOD_CONTAINERS: [
        "material",  # plastic, glass, metal, etc.
        "food_grade",  # must be true
        "capacity_relevance",  # true if capacity matters
    ],
    ProductFamily.CONSUMER_ELECTRONICS: [
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
        "power_source",  # battery, AC, USB, etc.
        "primary_function",  # communication, computing, display, etc.
    ],
    ProductFamily.FURNITURE: [
        "material",  # wood, metal, plastic, composite
        "primary_use",  # seating, storage, surface, etc.
    ],
    ProductFamily.TEXTILES: [
        "material_composition",  # cotton, polyester, blend, etc.
        "knit_or_woven",  # knit, woven, or null
        "end_use",  # bedding, clothing, household, etc.
    ],
    ProductFamily.FOOTWEAR: [
        "material_composition",  # leather, synthetic, textile, etc.
        "gender_or_age",  # men's, women's, children's, unisex
        "upper_material",  # if applicable
    ],
    ProductFamily.UNKNOWN: [],  # No requirements for unknown products
}


# Attribute question templates with "why it matters" explanations
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
}


def get_required_attributes(product_family: ProductFamily) -> List[str]:
    """Get required attributes for a product family."""
    return REQUIRED_ATTRIBUTES.get(product_family, [])


def get_question_for_attribute(attribute: str) -> str:
    """Get the clarifying question for a missing attribute."""
    return ATTRIBUTE_QUESTIONS.get(attribute, f"What is the {attribute}?")


def identify_product_family(description: str, extracted_attributes: Dict) -> ProductFamily:
    """
    Identify product family from description and extracted attributes.
    
    This is a simple keyword-based classifier. In production, this could be
    enhanced with ML, but for now we use deterministic rules.
    """
    description_lower = description.lower()
    
    # Audio devices
    audio_keywords = ["earbud", "headphone", "earphone", "speaker", "audio", "sound", "bluetooth", "wireless audio"]
    if any(kw in description_lower for kw in audio_keywords):
        return ProductFamily.AUDIO_DEVICES
    
    # Apparel
    apparel_keywords = ["shirt", "t-shirt", "pants", "dress", "jacket", "sweater", "apparel", "clothing", "garment"]
    if any(kw in description_lower for kw in apparel_keywords):
        return ProductFamily.APPAREL
    
    # Containers
    container_keywords = ["bottle", "container", "jar", "can", "box", "bag", "vessel"]
    if any(kw in description_lower for kw in container_keywords):
        # Check if food-related
        food_keywords = ["food", "beverage", "drink", "water", "juice", "milk"]
        if any(kw in description_lower for kw in food_keywords):
            return ProductFamily.FOOD_CONTAINERS
        return ProductFamily.CONTAINERS
    
    # Medical devices (check before electronics to avoid false matches)
    medical_keywords = ["medical", "diagnostic", "therapeutic", "surgical", "patient", "hospital", "clinic", "stethoscope", "thermometer", "monitor", "device"]
    if any(kw in description_lower for kw in medical_keywords):
        return ProductFamily.MEDICAL_DEVICES
    
    # Networking equipment (check before generic electronics)
    networking_keywords = ["router", "switch", "modem", "gateway", "access point", "network", "ethernet", "wifi", "wireless router"]
    if any(kw in description_lower for kw in networking_keywords):
        return ProductFamily.NETWORKING_EQUIPMENT
    
    # Power supplies / chargers
    power_keywords = ["charger", "adapter", "power supply", "power bank", "transformer", "converter", "AC adapter", "DC adapter"]
    if any(kw in description_lower for kw in power_keywords):
        return ProductFamily.POWER_SUPPLIES
    
    # Consumer electronics (phones, tablets, laptops, smart devices)
    consumer_electronics_keywords = ["smartphone", "phone", "tablet", "laptop", "computer", "smart watch", "smart device", "display", "monitor"]
    if any(kw in description_lower for kw in consumer_electronics_keywords):
        return ProductFamily.CONSUMER_ELECTRONICS
    
    # Generic electronics (fallback)
    electronics_keywords = ["electronic", "device"]
    if any(kw in description_lower for kw in electronics_keywords):
        return ProductFamily.ELECTRONICS
    
    # Furniture
    furniture_keywords = ["table", "chair", "desk", "bed", "sofa", "cabinet", "furniture"]
    if any(kw in description_lower for kw in furniture_keywords):
        return ProductFamily.FURNITURE
    
    # Textiles
    textile_keywords = ["sheet", "towel", "fabric", "textile", "cloth", "linen"]
    if any(kw in description_lower for kw in textile_keywords):
        return ProductFamily.TEXTILES
    
    # Footwear
    footwear_keywords = ["shoe", "boot", "sandal", "sneaker", "footwear"]
    if any(kw in description_lower for kw in footwear_keywords):
        return ProductFamily.FOOTWEAR
    
    return ProductFamily.UNKNOWN
