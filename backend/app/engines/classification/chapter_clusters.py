"""
Chapter Clusters - Explicit and Reviewable

This file defines all chapter clusters used in classification.
These clusters are NOT emergent from LLM output - they are explicit,
deterministic mappings that can be reviewed and audited.

You can point to this file and say "this is why chapters 39 and 85 are considered together"
for a specific product family.
"""
from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class ChapterCluster:
    """A cluster of related HTS chapters for a product family."""
    product_family: str
    chapters: List[int]  # List of chapter numbers
    rationale: str  # Why these chapters are grouped together
    use_case: str  # When this cluster is used


# Explicit chapter clusters by product family
# These are NOT emergent - they are deterministic mappings

CHAPTER_CLUSTERS: Dict[str, List[ChapterCluster]] = {
    "consumer_electronics": [
        ChapterCluster(
            product_family="consumer_electronics",
            chapters=[85, 84],
            rationale="Consumer electronics can be classified in Chapter 85 (electrical machinery) or Chapter 84 (computing machinery). Chapter 85 covers communication devices, audio/video equipment. Chapter 84 covers computers and data processing machines.",
            use_case="Primary function determines which chapter: communication/audio devices → 85, computing devices → 84"
        )
    ],
    
    "networking_equipment": [
        ChapterCluster(
            product_family="networking_equipment",
            chapters=[85],
            rationale="All networking equipment (routers, switches, modems) is classified in Chapter 85 under heading 8517 (transmission apparatus).",
            use_case="All networking equipment uses Chapter 85 cluster"
        )
    ],
    
    "power_supplies": [
        ChapterCluster(
            product_family="power_supplies",
            chapters=[85],
            rationale="Power supplies and chargers are classified in Chapter 85. AC adapters are 8504.40, portable chargers/power banks are 8507.60.",
            use_case="All power supplies use Chapter 85 cluster"
        )
    ],
    
    "medical_devices": [
        ChapterCluster(
            product_family="medical_devices",
            chapters=[90],
            rationale="Medical devices (non-pharma, non-implant) are classified in Chapter 90. Diagnostic devices are typically 9018, therapeutic devices are 9019.",
            use_case="All medical devices use Chapter 90 cluster"
        )
    ],
    
    "audio_devices": [
        ChapterCluster(
            product_family="audio_devices",
            chapters=[84, 85, 90],
            rationale="Audio devices are primarily in Chapter 85 (electrical machinery). Chapter 84 covers computing machinery and some electronics. Chapter 90 covers high-precision audio measurement instruments. Including 84 ensures we don't miss borderline electronics descriptions.",
            use_case="Standard audio devices → 85, computing/electronics → 84, precision measurement instruments → 90"
        )
    ],
    
    "apparel": [
        ChapterCluster(
            product_family="apparel",
            chapters=[61, 62],
            rationale="Apparel is classified in Chapter 61 (knit) or Chapter 62 (woven). The knit_or_woven attribute determines which chapter.",
            use_case="Knit apparel → 61, Woven apparel → 62"
        )
    ],
    
    "containers": [
        ChapterCluster(
            product_family="containers",
            chapters=[39, 70, 73, 76],
            rationale="Containers are classified by material: plastic → 39, glass → 70, stainless steel → 73, aluminum → 76. Material attribute determines which chapter.",
            use_case="Material attribute determines chapter: plastic=39, glass=70, stainless_steel=73, aluminum=76"
        )
    ],
    
    "textiles": [
        ChapterCluster(
            product_family="textiles",
            chapters=[61, 62, 63],
            rationale="Textiles are classified in Chapter 61 (knit), 62 (woven), or 63 (other made-up articles). Knit_or_woven and end_use attributes determine which chapter.",
            use_case="Knit → 61, Woven → 62, Other made-up articles → 63"
        )
    ],
    
    "furniture": [
        ChapterCluster(
            product_family="furniture",
            chapters=[94, 44],
            rationale="Furniture is primarily in Chapter 94 (furniture and bedding). However, unfinished wood furniture may be in Chapter 44 (wood).",
            use_case="Finished furniture → 94, Unfinished wood furniture → 44"
        )
    ],
}


def get_chapter_cluster(product_family: str) -> List[ChapterCluster]:
    """
    Get chapter clusters for a product family.
    
    Args:
        product_family: Product family name (e.g., "consumer_electronics")
    
    Returns:
        List of ChapterCluster objects
    """
    return CHAPTER_CLUSTERS.get(product_family, [])


def get_chapter_numbers(product_family: str) -> List[int]:
    """
    Get list of chapter numbers for a product family.
    
    Args:
        product_family: Product family name
    
    Returns:
        List of chapter numbers (flattened from all clusters)
    """
    clusters = get_chapter_cluster(product_family)
    chapters = set()
    for cluster in clusters:
        chapters.update(cluster.chapters)
    return sorted(list(chapters))


def get_cluster_rationale(product_family: str, chapter: int) -> str:
    """
    Get rationale for why a chapter is in a cluster for a product family.
    
    Args:
        product_family: Product family name
        chapter: Chapter number
    
    Returns:
        Rationale string explaining why this chapter is in the cluster
    """
    clusters = get_chapter_cluster(product_family)
    for cluster in clusters:
        if chapter in cluster.chapters:
            return cluster.rationale
    return f"Chapter {chapter} is not in any defined cluster for {product_family}"


def explain_chapter_cluster(product_family: str) -> str:
    """
    Generate a human-readable explanation of chapter clusters for a product family.
    
    Args:
        product_family: Product family name
    
    Returns:
        Explanation string
    """
    clusters = get_chapter_cluster(product_family)
    if not clusters:
        return f"No chapter clusters defined for {product_family}"
    
    parts = [f"Chapter clusters for {product_family}:"]
    for cluster in clusters:
        parts.append(f"  Chapters {cluster.chapters}: {cluster.rationale}")
        parts.append(f"    Use case: {cluster.use_case}")
    
    return "\n".join(parts)
