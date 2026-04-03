"""
Product Analysis Module

Extracts structured attributes from product descriptions using LLM.
Does NOT propose HTS codes or rank candidates.
Only extracts what is explicitly present in the description.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from app.engines.classification.required_attributes import (
    ProductFamily,
    select_product_family,
    get_required_attributes,
)
from app.engines.classification.attribute_maps import (
    get_attribute_map,
    get_required_attributes_with_rationale,
    get_primary_chapters,
)
from app.engines.classification.chapter_clusters import (
    get_chapter_numbers,
    explain_chapter_cluster,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedAttribute:
    """An extracted attribute with its source tokens."""
    value: Any  # str, bool, int, float, or None
    source_tokens: List[str]  # Tokens from description that support this value
    confidence: float  # 0.0 to 1.0


@dataclass
class ProductAnalysis:
    """Structured product analysis output."""
    product_type: str  # General product category
    product_family: ProductFamily
    family_selection_confidence: float  # Router confidence for chosen family (Patch C)
    family_matched_rule: str  # Which routing rule matched (audit)
    extracted_attributes: Dict[str, ExtractedAttribute]
    missing_required_attributes: List[str]
    suggested_chapters: List[Dict[str, Any]]  # [{"chapter": 85, "confidence": 0.85}]
    analysis_confidence: float  # 0.0 to 1.0
    rationale: str
    source_tokens: Dict[str, List[str]]  # All tokens used in analysis


class ProductAnalyzer:
    """
    Analyzes product descriptions to extract structured attributes.
    
    Uses LLM only for extraction, never for guessing.
    If an attribute is not explicitly present, it must be null.
    """
    
    def __init__(self):
        self.analyzer_version = "1.0.0"
    
    async def analyze(
        self,
        description: str,
        country_of_origin: Optional[str] = None
    ) -> ProductAnalysis:
        """
        Analyze product description and extract structured attributes.
        
        Args:
            description: Raw product description
            country_of_origin: Optional COO
            
        Returns:
            ProductAnalysis with extracted attributes and missing requirements
        """
        logger.info(f"Analyzing product: {description[:100]}...")
        
        # Patch C: rule-first family selection, then extract; refine family using extracted hints
        fs_initial = select_product_family(description, {})
        extracted_attributes = await self._extract_attributes(description, fs_initial.family)
        slim = {
            k: ext.value
            for k, ext in extracted_attributes.items()
            if ext.value is not None and ext.value != ""
        }
        fs_refined = select_product_family(description, slim)
        product_family = fs_refined.family
        family_selection_confidence = fs_refined.confidence
        family_matched_rule = fs_refined.matched_rule
        if fs_refined.family != fs_initial.family:
            extracted_attributes = await self._extract_attributes(description, product_family)
            fs_refined = select_product_family(
                description,
                {
                    k: ext.value
                    for k, ext in extracted_attributes.items()
                    if ext.value is not None and ext.value != ""
                },
            )
            product_family = fs_refined.family
            family_selection_confidence = fs_refined.confidence
            family_matched_rule = fs_refined.matched_rule
        
        # Identify missing required attributes
        required_attrs = get_required_attributes(product_family)
        missing_required = [
            attr for attr in required_attrs
            if attr not in extracted_attributes or extracted_attributes[attr].value is None
        ]
        
        # Suggest likely chapters (informational, not classification)
        suggested_chapters = self._suggest_chapters(description, product_family, extracted_attributes)
        
        # Compute analysis confidence (UNKNOWN is never "full confidence")
        analysis_confidence = self._compute_confidence(
            extracted_attributes,
            required_attrs,
            missing_required,
            product_family,
            family_selection_confidence,
        )
        
        # Generate rationale
        rationale = self._generate_rationale(
            description, product_family, extracted_attributes, missing_required, family_matched_rule
        )
        
        # Collect all source tokens
        source_tokens = {
            attr: ext_attr.source_tokens
            for attr, ext_attr in extracted_attributes.items()
        }
        
        # Determine product type
        product_type = self._determine_product_type(description, product_family)
        
        return ProductAnalysis(
            product_type=product_type,
            product_family=product_family,
            family_selection_confidence=family_selection_confidence,
            family_matched_rule=family_matched_rule,
            extracted_attributes=extracted_attributes,
            missing_required_attributes=missing_required,
            suggested_chapters=suggested_chapters,
            analysis_confidence=analysis_confidence,
            rationale=rationale,
            source_tokens=source_tokens,
        )
    
    async def _extract_attributes(
        self,
        description: str,
        product_family: ProductFamily
    ) -> Dict[str, ExtractedAttribute]:
        """
        Extract attributes from description using rule-based extraction.
        
        Only extracts what is explicitly present. No guessing.
        Logs source tokens for each extracted attribute for provenance.
        """
        description_lower = description.lower()
        description_words = description.split()
        extracted = {}
        
        # Get formal attribute map if available
        attr_map = get_attribute_map(product_family)
        attribute_requirements = get_required_attributes_with_rationale(product_family)
        
        # If we have a formal map, use it for extraction
        if attribute_requirements:
            for req in attribute_requirements:
                # Check if any extraction keywords match
                matched_keywords = [kw for kw in req.extraction_keywords if kw.lower() in description_lower]
                if matched_keywords:
                    # Extract value based on keywords
                    value = self._extract_value_from_keywords(
                        description_lower,
                        description_words,
                        req.attribute_name,
                        req.value_options,
                        matched_keywords
                    )
                    if value is not None:
                        # Find source tokens
                        source_tokens = self._find_source_tokens(description_words, matched_keywords)
                        extracted[req.attribute_name] = ExtractedAttribute(
                            value=value,
                            source_tokens=source_tokens,
                            confidence=self._calculate_extraction_confidence(matched_keywords, req.extraction_keywords)
                        )
        
        # Fallback to generic extraction for families without formal maps
        if not extracted:
            extracted.update(self._extract_generic_attributes(description_lower, description_words, product_family))
        
        return extracted
    
    def _extract_value_from_keywords(
        self,
        description_lower: str,
        description_words: List[str],
        attribute_name: str,
        value_options: List[str],
        matched_keywords: List[str]
    ) -> Any:
        """Extract attribute value from matched keywords."""
        # For boolean attributes
        if attribute_name in ["wireless_capability", "is_electrical", "is_patient_contacting", "is_disposable"]:
            return True  # If keyword matched, assume true
        
        # For enumerated attributes, try to match value options
        for option in value_options:
            if option.lower() in description_lower:
                return option
        
        # For power_source, try to infer from keywords
        if attribute_name == "power_source":
            if "battery" in description_lower or "rechargeable" in description_lower:
                return "battery"
            elif "usb" in description_lower:
                return "USB"
            elif "ac" in description_lower and "adapter" in description_lower:
                return "AC"
            elif "wired" in description_lower:
                return "wired"
        
        # For power_rating, try to extract numeric value
        if attribute_name == "power_rating":
            import re
            # Look for patterns like "5W", "10 watt", "100W"
            power_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:w|watt|W)', description_lower)
            if power_match:
                return float(power_match.group(1))
        
        # For portable_vs_fixed
        if attribute_name == "portable_vs_fixed":
            if "portable" in description_lower or "mobile" in description_lower:
                return "portable"
            elif "fixed" in description_lower or "stationary" in description_lower or "wall" in description_lower:
                return "fixed"
        
        # Default: return first matched keyword as value
        return matched_keywords[0] if matched_keywords else None
    
    def _find_source_tokens(self, description_words: List[str], matched_keywords: List[str]) -> List[str]:
        """Find source tokens in description that match keywords."""
        source_tokens = []
        description_lower = ' '.join(description_words).lower()
        for word in description_words:
            word_lower = word.lower()
            for keyword in matched_keywords:
                if keyword.lower() in word_lower or word_lower in keyword.lower():
                    source_tokens.append(word)
                    break
        return source_tokens[:5]  # Limit to 5 tokens
    
    def _calculate_extraction_confidence(self, matched_keywords: List[str], all_keywords: List[str]) -> float:
        """Calculate confidence based on keyword match strength."""
        if not matched_keywords:
            return 0.0
        # Higher confidence if multiple keywords match
        match_ratio = len(matched_keywords) / max(len(all_keywords), 1)
        return min(0.95, 0.7 + (match_ratio * 0.25))
    
    def _extract_generic_attributes(
        self,
        description_lower: str,
        description_words: List[str],
        product_family: ProductFamily
    ) -> Dict[str, ExtractedAttribute]:
        """Fallback generic attribute extraction for families without formal maps."""
        extracted = {}
        
        # Power source
        power_tokens = []
        if "battery" in description_lower or "rechargeable" in description_lower:
            power_tokens = [t for t in description_words if "battery" in t.lower() or "rechargeable" in t.lower()]
            extracted["power_source"] = ExtractedAttribute(
                value="battery",
                source_tokens=power_tokens[:3],
                confidence=0.9
            )
        elif "wired" in description_lower:
            power_tokens = [t for t in description_words if "wired" in t.lower()]
            extracted["power_source"] = ExtractedAttribute(
                value="wired",
                source_tokens=power_tokens[:3],
                confidence=0.9
            )
        elif "usb" in description_lower:
            power_tokens = [t for t in description_words if "usb" in t.lower()]
            extracted["power_source"] = ExtractedAttribute(
                value="usb",
                source_tokens=power_tokens[:3],
                confidence=0.9
            )
        elif "ac" in description_lower and "adapter" in description_lower:
            power_tokens = [t for t in description_words if "ac" in t.lower() or "adapter" in t.lower()]
            extracted["power_source"] = ExtractedAttribute(
                value="ac_adapter",
                source_tokens=power_tokens[:3],
                confidence=0.9
            )
        
        # Wireless
        if "wireless" in description_lower or "bluetooth" in description_lower:
            wireless_tokens = [t for t in description_words if "wireless" in t.lower() or "bluetooth" in t.lower()]
            extracted["wireless"] = ExtractedAttribute(
                value=True,
                source_tokens=wireless_tokens[:3],
                confidence=0.95
            )
        elif "wired" in description_lower:
            wired_tokens = [t for t in description_words if "wired" in t.lower()]
            extracted["wireless"] = ExtractedAttribute(
                value=False,
                source_tokens=wired_tokens[:3],
                confidence=0.9
            )
        
        # Material composition (for apparel/textiles)
        if product_family in [ProductFamily.APPAREL, ProductFamily.TEXTILES]:
            material_keywords = ["cotton", "polyester", "wool", "silk", "linen", "nylon", "spandex", "elastane"]
            for mat in material_keywords:
                if mat in description_lower:
                    mat_tokens = [t for t in description_words if mat.lower() in t.lower()]
                    extracted["material_composition"] = ExtractedAttribute(
                        value=mat,
                        source_tokens=mat_tokens[:3],
                        confidence=0.85
                    )
                    break
        
        # Knit or woven
        if "knit" in description_lower:
            knit_tokens = [t for t in description_words if "knit" in t.lower()]
            extracted["knit_or_woven"] = ExtractedAttribute(
                value="knit",
                source_tokens=knit_tokens[:3],
                confidence=0.9
            )
        elif "woven" in description_lower:
            woven_tokens = [t for t in description_words if "woven" in t.lower()]
            extracted["knit_or_woven"] = ExtractedAttribute(
                value="woven",
                source_tokens=woven_tokens[:3],
                confidence=0.9
            )
        
        # Gender/age
        gender_keywords = {
            "men's": "men's",
            "mens": "men's",
            "men": "men's",
            "women's": "women's",
            "womens": "women's",
            "women": "women's",
            "children's": "children's",
            "childrens": "children's",
            "kids": "children's",
            "unisex": "unisex"
        }
        for kw, value in gender_keywords.items():
            if kw in description_lower:
                gender_tokens = [t for t in description_words if kw in t.lower()]
                extracted["gender_or_age"] = ExtractedAttribute(
                    value=value,
                    source_tokens=gender_tokens[:3],
                    confidence=0.9
                )
                break
        
        # Material (for containers, furniture)
        if product_family in [ProductFamily.CONTAINERS, ProductFamily.FOOD_CONTAINERS, ProductFamily.FURNITURE]:
            material_keywords = {
                "stainless steel": "stainless_steel",
                "steel": "steel",
                "aluminum": "aluminum",
                "plastic": "plastic",
                "glass": "glass",
                "wood": "wood",
                "wooden": "wood",
                "ceramic": "ceramic"
            }
            for kw, value in material_keywords.items():
                if kw in description_lower:
                    mat_tokens = [t for t in description_words if kw in t.lower()]
                    extracted["material"] = ExtractedAttribute(
                        value=value,
                        source_tokens=mat_tokens[:3],
                        confidence=0.85
                    )
                    break
        
        # Capacity relevance (for containers)
        if product_family in [ProductFamily.CONTAINERS, ProductFamily.FOOD_CONTAINERS]:
            capacity_keywords = ["ounce", "oz", "liter", "l", "ml", "gallon", "capacity", "size"]
            if any(kw in description_lower for kw in capacity_keywords):
                cap_tokens = [t for t in description_words if any(kw in t.lower() for kw in capacity_keywords)]
                extracted["capacity_relevance"] = ExtractedAttribute(
                    value=True,
                    source_tokens=cap_tokens[:3],
                    confidence=0.8
                )
        
        # Food grade
        if product_family == ProductFamily.FOOD_CONTAINERS:
            food_keywords = ["food", "beverage", "drink", "water", "juice"]
            if any(kw in description_lower for kw in food_keywords):
                food_tokens = [t for t in description_words if any(kw in t.lower() for kw in food_keywords)]
                extracted["food_grade"] = ExtractedAttribute(
                    value=True,
                    source_tokens=food_tokens[:3],
                    confidence=0.85
                )
        
        if product_family == ProductFamily.FASTENERS_HARDWARE:
            for term, label in (
                ("machine screw", "machine_screw"),
                ("wood screw", "wood_screw"),
                ("hex bolt", "hex_bolt"),
                ("bolt", "bolt"),
                ("screw", "screw"),
                ("washer", "washer"),
                ("nut", "nut"),
                ("rivet", "rivet"),
            ):
                if term in description_lower:
                    extracted["fastener_category"] = ExtractedAttribute(
                        value=label,
                        source_tokens=[term.split()[-1]],
                        confidence=0.82,
                    )
                    break
            for kw, val in (
                ("stainless steel", "stainless_steel"),
                ("steel", "steel"),
                ("brass", "brass"),
                ("aluminum", "aluminum"),
            ):
                if kw in description_lower:
                    extracted["material"] = ExtractedAttribute(
                        value=val,
                        source_tokens=[kw.split()[0]],
                        confidence=0.82,
                    )
                    break
        
        return extracted
    
    def _suggest_chapters(
        self,
        description: str,
        product_family: ProductFamily,
        extracted_attributes: Dict[str, ExtractedAttribute]
    ) -> List[Dict[str, Any]]:
        """
        Suggest likely HTS chapters based on product family and attributes.
        
        This is informational only, not a classification.
        Capped to max 3 chapters as per Workstream A requirement.
        """
        suggestions = []
        
        # Use explicit chapter clusters from chapter_clusters.py
        # This ensures clusters are explicit and reviewable, not emergent
        chapter_numbers = get_chapter_numbers(product_family.value)
        if chapter_numbers:
            for ch in chapter_numbers[:3]:  # Cap to 3
                suggestions.append({
                    "chapter": ch,
                    "confidence": 0.85,
                    "reason": f"{product_family.value} typically classified in Chapter {ch} (see chapter_clusters.py for rationale)"
                })
            return suggestions[:3]  # Ensure max 3
        
        # Fallback to primary chapters from attribute maps if no explicit cluster
        primary_chapters = get_primary_chapters(product_family)
        if primary_chapters:
            for ch in primary_chapters[:3]:  # Cap to 3
                suggestions.append({
                    "chapter": int(ch),
                    "confidence": 0.85,
                    "reason": f"{product_family.value} typically classified in Chapter {ch}"
                })
            return suggestions[:3]  # Ensure max 3
        
        # Fallback to generic suggestions
        if product_family == ProductFamily.AUDIO_DEVICES:
            suggestions.append({"chapter": 85, "confidence": 0.85, "reason": "Audio devices typically classified in Chapter 85"})
        elif product_family == ProductFamily.APPAREL:
            suggestions.append({"chapter": 61, "confidence": 0.8, "reason": "Knit apparel typically in Chapter 61"})
            suggestions.append({"chapter": 62, "confidence": 0.8, "reason": "Woven apparel typically in Chapter 62"})
        elif product_family == ProductFamily.CONTAINERS:
            material = extracted_attributes.get("material")
            if material and material.value == "stainless_steel":
                suggestions.append({"chapter": 73, "confidence": 0.85, "reason": "Stainless steel containers typically in Chapter 73"})
            elif material and material.value == "plastic":
                suggestions.append({"chapter": 39, "confidence": 0.8, "reason": "Plastic containers typically in Chapter 39"})
            elif material and material.value == "glass":
                suggestions.append({"chapter": 70, "confidence": 0.8, "reason": "Glass containers typically in Chapter 70"})
        elif product_family == ProductFamily.FURNITURE:
            material = extracted_attributes.get("material")
            if material and material.value == "wood":
                suggestions.append({"chapter": 94, "confidence": 0.8, "reason": "Wooden furniture typically in Chapter 94"})
        elif product_family == ProductFamily.FASTENERS_HARDWARE:
            suggestions.append({"chapter": 73, "confidence": 0.82, "reason": "Steel threaded fasteners and washers commonly in Chapter 73"})
            suggestions.append({"chapter": 83, "confidence": 0.75, "reason": "Miscellaneous base metal articles may fall in Chapter 83"})
        
        # Cap to max 3 chapters
        return suggestions[:3]
    
    def _compute_confidence(
        self,
        extracted_attributes: Dict[str, ExtractedAttribute],
        required_attrs: List[str],
        missing_required: List[str],
        product_family: ProductFamily,
        family_selection_confidence: float,
    ) -> float:
        """
        Compute overall analysis confidence.
        
        Derived from:
        - % of required attributes resolved
        - Strength of keyword evidence (individual attribute confidence)
        - UNKNOWN family is never treated as full confidence (Patch C)
        """
        keyword_evidence_strength = 0.0
        if extracted_attributes:
            confidences = [attr.confidence for attr in extracted_attributes.values()]
            keyword_evidence_strength = sum(confidences) / len(confidences) if confidences else 0.0

        if not required_attrs:
            if product_family == ProductFamily.UNKNOWN:
                # No mandatory attributes: still uncertain — blend extraction + router
                base = 0.32 + 0.22 * float(family_selection_confidence or 0.0)
                if extracted_attributes:
                    base = min(0.62, base + 0.15 * keyword_evidence_strength)
                return min(0.65, max(0.25, base))
            return 1.0
        
        # Component 1: % of required attributes resolved
        found_count = len(required_attrs) - len(missing_required)
        attribute_coverage = found_count / len(required_attrs) if required_attrs else 1.0
        
        # Weighted combination: 60% attribute coverage, 40% keyword evidence strength
        confidence = (attribute_coverage * 0.6) + (keyword_evidence_strength * 0.4)
        confidence = min(1.0, max(0.0, confidence))
        if product_family == ProductFamily.UNKNOWN:
            confidence = min(confidence, 0.62)
        return confidence
    
    def _generate_rationale(
        self,
        description: str,
        product_family: ProductFamily,
        extracted_attributes: Dict[str, ExtractedAttribute],
        missing_required: List[str],
        family_matched_rule: str = "",
    ) -> str:
        """Generate human-readable rationale for the analysis."""
        parts = []
        
        parts.append(f"Product family identified as: {product_family.value}")
        if family_matched_rule:
            parts.append(f"Family router rule: {family_matched_rule}")
        
        if extracted_attributes:
            attr_summary = ", ".join([
                f"{attr}={ext_attr.value}"
                for attr, ext_attr in extracted_attributes.items()
                if ext_attr.value is not None
            ])
            parts.append(f"Extracted attributes: {attr_summary}")
        
        if missing_required:
            parts.append(f"Missing required attributes: {', '.join(missing_required)}")
        else:
            parts.append("All required attributes present")
        
        return ". ".join(parts) + "."
    
    def _determine_product_type(self, description: str, product_family: ProductFamily) -> str:
        """Determine general product type from description."""
        description_lower = description.lower()
        
        if product_family == ProductFamily.AUDIO_DEVICES:
            if "earbud" in description_lower:
                return "wireless earbuds" if "wireless" in description_lower or "bluetooth" in description_lower else "earbuds"
            elif "headphone" in description_lower:
                return "headphones"
            elif "speaker" in description_lower:
                return "speaker"
            return "audio device"
        elif product_family == ProductFamily.APPAREL:
            if "shirt" in description_lower or "t-shirt" in description_lower:
                return "t-shirt"
            elif "pants" in description_lower:
                return "pants"
            return "apparel"
        elif product_family == ProductFamily.CONTAINERS:
            if "bottle" in description_lower:
                return "bottle"
            elif "container" in description_lower:
                return "container"
            return "container"
        elif product_family == ProductFamily.FASTENERS_HARDWARE:
            return "fastener or hardware article"
        
        return product_family.value.replace("_", " ")


def serialize_analysis(analysis: ProductAnalysis) -> Dict[str, Any]:
    """Serialize ProductAnalysis to JSON-serializable dict."""
    return {
        "product_type": analysis.product_type,
        "product_family": analysis.product_family.value,
        "family_selection_confidence": getattr(analysis, "family_selection_confidence", 0.0),
        "family_matched_rule": getattr(analysis, "family_matched_rule", ""),
        "extracted_attributes": {
            attr: {
                "value": ext_attr.value,
                "source_tokens": ext_attr.source_tokens,
                "confidence": ext_attr.confidence
            }
            for attr, ext_attr in analysis.extracted_attributes.items()
        },
        "missing_required_attributes": analysis.missing_required_attributes,
        "suggested_chapters": analysis.suggested_chapters,
        "analysis_confidence": analysis.analysis_confidence,
        "rationale": analysis.rationale,
        "source_tokens": analysis.source_tokens
    }
