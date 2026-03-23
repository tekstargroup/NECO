"""
Signal Classification Engine - Compliance Signal Engine

LLM + rules hybrid: classifies raw signal content into category, hts_codes, countries, impact_type.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.models.signal_classification import SignalCategory

logger = logging.getLogger(__name__)

# HTS pattern: 4-10 digits, optionally with dots (e.g. 8471.30, 9903.88.15)
HTS_PATTERN = re.compile(r"\b(\d{4}\.?\d{0,2}\.?\d{0,2})\b")
# Country pattern: 2-letter codes (ISO 3166-1 alpha-2)
COUNTRY_PATTERN = re.compile(r"\b([A-Z]{2})\b")

# Keyword -> category mapping for rules-based fallback
KEYWORD_CATEGORY_MAP = {
    "tariff": SignalCategory.TARIFF_CHANGE,
    "duty": SignalCategory.TARIFF_CHANGE,
    "section 301": SignalCategory.TARIFF_CHANGE,
    "section 232": SignalCategory.TARIFF_CHANGE,
    "hts": SignalCategory.HTS_UPDATE,
    "harmonized": SignalCategory.HTS_UPDATE,
    "classification": SignalCategory.HTS_UPDATE,
    "quota": SignalCategory.QUOTA_UPDATE,
    "sanction": SignalCategory.SANCTION,
    "ofac": SignalCategory.SANCTION,
    "restriction": SignalCategory.IMPORT_RESTRICTION,
    "ruling": SignalCategory.RULING,
    "cross": SignalCategory.RULING,
    "hq ": SignalCategory.RULING,  # CBP ruling prefix
    "trade action": SignalCategory.TRADE_ACTION,
    "documentation": SignalCategory.DOCUMENTATION_RULE,
    "entry": SignalCategory.DOCUMENTATION_RULE,
    "ace": SignalCategory.DOCUMENTATION_RULE,
}


def _extract_hts_codes(text: str) -> List[str]:
    """Extract HTS-like codes from text using regex."""
    if not text:
        return []
    matches = HTS_PATTERN.findall(text.upper().replace(" ", ""))
    # Normalize: keep first 4 digits + up to 2 subparts
    seen = set()
    result = []
    for m in matches:
        normalized = m.replace(".", "")[:10]
        if len(normalized) >= 4 and normalized not in seen:
            seen.add(normalized)
            result.append(normalized[:4] + ("." + normalized[4:6] if len(normalized) > 4 else ""))
    return result[:20]  # Limit


def _parse_numeric(val: Any) -> Optional[float]:
    """Parse numeric from string or number."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", "").strip()
        return float(re.sub(r"[^\d.-]", "", s) or 0)
    except (ValueError, TypeError):
        return None


def _extract_countries(text: str) -> List[str]:
    """Extract 2-letter country codes from text (common trade countries)."""
    if not text:
        return []
    common = {"CN", "MX", "VN", "IN", "JP", "KR", "DE", "US", "CA", "GB", "TW", "TH", "MY", "ID"}
    matches = COUNTRY_PATTERN.findall(text.upper())
    return list(dict.fromkeys([m for m in matches if m in common]))[:10]


def _rules_based_classify(text: str) -> Optional[Dict[str, Any]]:
    """Rules-based classification fallback."""
    if not text or len(text) < 20:
        return None
    text_lower = text.lower()
    for keyword, category in KEYWORD_CATEGORY_MAP.items():
        if keyword in text_lower:
            return {
                "category": category.value,
                "hts_codes": _extract_hts_codes(text),
                "countries": _extract_countries(text),
                "impact_type": "compliance_risk" if category in (SignalCategory.RULING, SignalCategory.SANCTION) else "duty_increase",
                "summary": text[:500] if len(text) > 500 else text,
                "confidence": 0.5,
            }
    return {
        "category": SignalCategory.TRADE_ACTION.value,
        "hts_codes": _extract_hts_codes(text),
        "countries": _extract_countries(text),
        "impact_type": "compliance_risk",
        "summary": text[:500] if len(text) > 500 else text,
        "confidence": 0.3,
    }


def classify_signal(content: str, title: str = "") -> Dict[str, Any]:
    """
    Classify raw signal content using LLM + rules hybrid.

    Input: raw_signal.content (and optionally title)
    Output: {
        category: str (SignalCategory value),
        hts_codes: list[str],
        countries: list[str],
        impact_type: str,
        summary: str,
        confidence: float 0-1
    }
    """
    text = f"{title}\n\n{content}" if title else (content or "")
    if not text.strip():
        return {
            "category": SignalCategory.TRADE_ACTION.value,
            "hts_codes": [],
            "countries": [],
            "impact_type": "compliance_risk",
            "summary": "",
            "confidence": 0.0,
        }

    # Try rules first (fast path)
    rules_result = _rules_based_classify(text)
    if rules_result and rules_result.get("confidence", 0) >= 0.6:
        # Add quota/tariff extraction from text for rules path
        if rules_result.get("category") == "QUOTA_UPDATE":
            m1 = re.search(r"quota[:\s]+([\d,\.]+)", text, re.I)
            m2 = re.search(r"(?:used|filled)[:\s]+([\d,\.]+)", text, re.I)
            rules_result["quota_limit"] = _parse_numeric(m1.group(1)) if m1 else None
            rules_result["quota_used"] = _parse_numeric(m2.group(1)) if m2 else None
        if rules_result.get("category") == "TARIFF_CHANGE":
            rates = re.findall(r"(\d+\.?\d*)\s*%", text)
            if len(rates) >= 2:
                rules_result["old_duty_rate"] = float(rates[0]) / 100
                rules_result["new_duty_rate"] = float(rates[1]) / 100
                rules_result["duty_rate_change"] = rules_result["new_duty_rate"] - rules_result["old_duty_rate"]
        return rules_result

    # LLM classification when available
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = f"""Classify this trade/compliance signal. Return ONLY valid JSON.

Categories: TARIFF_CHANGE, HTS_UPDATE, QUOTA_UPDATE, SANCTION, IMPORT_RESTRICTION, RULING, TRADE_ACTION, DOCUMENTATION_RULE
Impact types: duty_increase, duty_decrease, compliance_risk, documentation

JSON format:
{{"category": "...", "hts_codes": ["1234.56", ...], "countries": ["CN", "MX", ...], "impact_type": "...", "summary": "...", "confidence": 0.0-1.0}}
For QUOTA_UPDATE also include: "quota_limit": number, "quantity_used": number
For TARIFF_CHANGE also include: "old_rate": number, "new_rate": number

Signal:
{text[:8000]}"""
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        category = data.get("category", "TRADE_ACTION")
        if category not in [c.value for c in SignalCategory]:
            category = "TRADE_ACTION"
        result = {
            "category": category,
            "hts_codes": data.get("hts_codes", [])[:20],
            "countries": data.get("countries", [])[:10],
            "impact_type": data.get("impact_type", "compliance_risk"),
            "summary": (data.get("summary") or text)[:2000],
            "confidence": min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
        }
        # GAP 1 - Quota extraction
        if category == "QUOTA_UPDATE":
            result["quota_limit"] = _parse_numeric(data.get("quota_limit"))
            result["quota_used"] = _parse_numeric(data.get("quantity_used"))
            result["country"] = (data.get("countries") or [None])[0] if data.get("countries") else None
        # GAP 2 - Tariff extraction
        if category == "TARIFF_CHANGE":
            result["old_duty_rate"] = _parse_numeric(data.get("old_rate"))
            result["new_duty_rate"] = _parse_numeric(data.get("new_rate"))
            if result.get("old_duty_rate") is not None and result.get("new_duty_rate") is not None:
                result["duty_rate_change"] = float(result["new_duty_rate"]) - float(result["old_duty_rate"])
        return result
    except Exception as e:
        logger.warning("LLM classification failed, using rules: %s", e)
        fallback = rules_result or {
            "category": SignalCategory.TRADE_ACTION.value,
            "hts_codes": _extract_hts_codes(text),
            "countries": _extract_countries(text),
            "impact_type": "compliance_risk",
            "summary": text[:500],
            "confidence": 0.4,
        }
        # GAP 6 - Fallback: try keyword->HTS inference when no HTS found
        if not fallback.get("hts_codes") and fallback.get("category") in ("TARIFF_CHANGE", "QUOTA_UPDATE", "HTS_UPDATE"):
            fallback["hts_codes"] = _extract_hts_codes(text)
        return fallback
