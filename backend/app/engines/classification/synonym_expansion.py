"""
Synonym Expansion - Deterministic and Auditable

This module provides per-product-family synonym expansion for query enhancement.
All expansions are deterministic, logged, and auditable.
"""
from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class SynonymMap:
    """A synonym map for a product family."""
    product_family: str
    synonyms: Dict[str, List[str]]  # term -> [synonym1, synonym2, ...]
    max_expansions: int = 10  # Cap to avoid query bloat


# Per-product-family synonym maps
SYNONYM_MAPS: Dict[str, SynonymMap] = {
    "audio_devices": SynonymMap(
        product_family="audio_devices",
        synonyms={
            "earbuds": ["earphones", "headphones", "headset", "earpieces", "earphone"],
            "earphone": ["earbuds", "earphones", "headphones", "headset", "earpieces"],
            "earphones": ["earbuds", "earphone", "headphones", "headset", "earpieces"],
            "headphones": ["earbuds", "earphones", "headset", "earpieces", "earphone"],
            "headset": ["earbuds", "earphones", "headphones", "earpieces", "earphone"],
            "bluetooth": ["wireless", "radio frequency"],
            "wireless": ["bluetooth", "cordless", "radio frequency"],
            "charging case": ["charger", "case", "charging cradle", "charging dock"],
            "charger": ["charging case", "case", "charging cradle"],
            "case": ["charging case", "charger", "charging cradle"],
        },
        max_expansions=10
    ),
    
    "networking_equipment": SynonymMap(
        product_family="networking_equipment",
        synonyms={
            "router": ["routing apparatus", "switch", "access point", "gateway", "routing device"],
            "switch": ["router", "routing apparatus", "switching apparatus", "network switch"],
            "access point": ["router", "gateway", "wireless access point", "ap"],
            "gateway": ["router", "routing apparatus", "access point"],
        },
        max_expansions=10
    ),
    
    "consumer_electronics": SynonymMap(
        product_family="consumer_electronics",
        synonyms={
            "earbuds": ["earphones", "headphones", "headset", "earpieces"],
            "bluetooth": ["wireless", "radio frequency"],
            "wireless": ["bluetooth", "cordless"],
        },
        max_expansions=10
    ),
}


def expand_query_terms(
    query: str,
    product_family: str,
    max_expansions: int = 10
) -> tuple[str, List[str]]:
    """
    Expand query terms using product-family-specific synonyms.
    
    Args:
        query: Original query text
        product_family: Product family (e.g., "audio_devices")
        max_expansions: Maximum number of terms to add (default 10)
    
    Returns:
        Tuple of (expanded_query, expanded_terms_list)
        - expanded_query: Original query with expanded terms added
        - expanded_terms_list: List of terms that were added (for audit logging)
    """
    if product_family not in SYNONYM_MAPS:
        return query, []
    
    synonym_map = SYNONYM_MAPS[product_family]
    
    # Tokenize query (simple word-based)
    query_lower = query.lower()
    words = query_lower.split()
    
    # Track expanded terms to avoid duplicates
    expanded_terms: Set[str] = set()
    original_terms: Set[str] = set(words)
    
    # Check each word/phrase against synonym map
    for term, synonyms in synonym_map.synonyms.items():
        term_lower = term.lower()
        
        # Check if term appears in query (exact match or as part of phrase)
        if term_lower in query_lower:
            # Add synonyms that aren't already in the query
            for synonym in synonyms:
                synonym_lower = synonym.lower()
                if synonym_lower not in original_terms and len(expanded_terms) < max_expansions:
                    expanded_terms.add(synonym)
        
        # Also check for multi-word phrases (e.g., "charging case")
        if " " in term:
            if term_lower in query_lower:
                for synonym in synonyms:
                    synonym_lower = synonym.lower()
                    if synonym_lower not in original_terms and len(expanded_terms) < max_expansions:
                        expanded_terms.add(synonym)
    
    # Build expanded query (additive - keep original terms)
    expanded_query = query
    expanded_terms_list = sorted(list(expanded_terms))
    
    if expanded_terms_list:
        # Add expanded terms to query
        expanded_query = f"{query} {' '.join(expanded_terms_list)}"
    
    return expanded_query, expanded_terms_list


def get_synonym_map_for_family(product_family: str) -> Dict[str, List[str]]:
    """Get synonym map for a product family."""
    if product_family in SYNONYM_MAPS:
        return SYNONYM_MAPS[product_family].synonyms
    return {}
