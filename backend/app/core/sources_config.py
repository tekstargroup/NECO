"""
Sources config loader - Compliance Signal Engine

Loads regulatory feed sources from JSON config.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default path relative to backend root
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sources_config.json"


def load_sources_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load sources config from JSON file.

    Returns:
        Dict with "sources" key containing list of source configs.
        Each source has: name, type, url, frequency
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.warning("Sources config not found at %s, using empty sources", path)
        return {"sources": []}

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load sources config from %s: %s", path, e)
        return {"sources": []}


def get_sources(config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Get list of source configs.

    Returns:
        List of dicts with name, type, url, frequency
    """
    config = load_sources_config(config_path)
    return config.get("sources", [])


def get_sources_by_type(source_type: str, config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Get sources filtered by type (rss, api, scrape)."""
    sources = get_sources(config_path)
    return [s for s in sources if s.get("type") == source_type]


def get_sources_by_frequency(frequency: str, config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Get sources filtered by frequency (5min, 15min, 1h, 6h, 1d). GAP 5."""
    sources = get_sources(config_path)
    return [s for s in sources if s.get("frequency") == frequency]
