"""
Workstream 4.1-B: Medical Candidate Display Cleanup

Improves candidate display text for medical devices by:
- Cleaning generic "Other…" text
- Extracting meaningful noun phrases from tariff_text
- Stripping dot leaders and boilerplate
"""

import re
from typing import Optional


def clean_medical_candidate_text(
    tariff_text_short: Optional[str],
    tariff_text: Optional[str],
    hts_code: str
) -> str:
    """
    Clean and improve medical candidate display text.
    
    Workstream 4.1-B: For medical candidates, display:
    - tariff_text_short
    - PLUS a cleaned noun-phrase snippet from tariff_text
    - Strip "Other…", dot leaders, boilerplate
    
    This is presentation-only, not similarity.
    
    Args:
        tariff_text_short: Short tariff text
        tariff_text: Full tariff text
        hts_code: HTS code for context
    
    Returns:
        Cleaned, reviewer-friendly display text
    """
    # Start with tariff_text_short if available
    display_text = tariff_text_short or ""
    
    # If we have full tariff_text, extract meaningful snippet
    if tariff_text:
        # Strip common boilerplate
        cleaned = tariff_text
        
        # Remove "Other..." patterns
        cleaned = re.sub(r'Other\.+', '', cleaned)
        cleaned = re.sub(r'Other\s*:?\s*', '', cleaned)
        
        # Remove dot leaders (multiple dots/ellipses)
        cleaned = re.sub(r'\.{3,}', ' ', cleaned)
        cleaned = re.sub(r'\.{2,}', ' ', cleaned)
        
        # Remove common HTS boilerplate patterns
        cleaned = re.sub(r'\d+%', '', cleaned)  # Remove percentage patterns
        cleaned = re.sub(r'\d+/\s*(No|Yes)', '', cleaned, flags=re.IGNORECASE)  # Remove "5/No" patterns
        cleaned = re.sub(r'Free\s*\d*/', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'No\.+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'Yes\.+', '', cleaned, flags=re.IGNORECASE)
        
        # Extract noun phrases (sequences of capitalized words or medical terms)
        # Look for patterns like "Blood pressure monitor", "Diagnostic device", etc.
        noun_phrase_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        noun_phrases = re.findall(noun_phrase_pattern, cleaned)
        
        # Filter meaningful phrases (length > 5 chars, not just single words)
        meaningful_phrases = [
            phrase for phrase in noun_phrases
            if len(phrase) > 5 and not phrase.isdigit()
        ]
        
        # Also look for medical device keywords
        medical_keywords = [
            "monitor", "device", "instrument", "apparatus", "equipment",
            "diagnostic", "therapeutic", "surgical", "medical",
            "blood pressure", "heart rate", "temperature", "pulse",
            "patient", "clinical", "hospital"
        ]
        
        # Extract sentences containing medical keywords
        sentences = re.split(r'[.!?;]\s+', cleaned)
        medical_sentences = [
            sent.strip() for sent in sentences
            if any(kw in sent.lower() for kw in medical_keywords)
        ]
        
        # Build display text: tariff_text_short + meaningful snippet
        if display_text:
            display_text = display_text.strip()
        
        # Add cleaned snippet if available
        if meaningful_phrases:
            snippet = " ".join(meaningful_phrases[:3])  # Take first 3 meaningful phrases
            if snippet and snippet not in display_text:
                display_text = f"{display_text} — {snippet}".strip()
        elif medical_sentences:
            snippet = medical_sentences[0][:150]  # First meaningful sentence, max 150 chars
            if snippet and snippet not in display_text:
                display_text = f"{display_text} — {snippet}".strip()
        elif cleaned.strip():
            # Fallback: cleaned text (first 150 chars)
            snippet = cleaned.strip()[:150]
            if snippet and snippet not in display_text:
                display_text = f"{display_text} — {snippet}".strip()
    
    # Final cleanup: remove extra whitespace, normalize
    display_text = re.sub(r'\s+', ' ', display_text).strip()
    
    # If still empty or too generic, return basic info
    if not display_text or len(display_text) < 10:
        display_text = f"HTS {hts_code} — Medical device classification"
    
    return display_text
