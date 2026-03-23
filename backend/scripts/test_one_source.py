#!/usr/bin/env python3
"""
Test a single regulatory source by name.
Usage: python scripts/test_one_source.py SOURCE_NAME

Example: python scripts/test_one_source.py CBP_CSMS
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.sources_config import get_sources
from app.services.regulatory_feed_poller import _test_one_source


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_one_source.py SOURCE_NAME")
        print("Example: python scripts/test_one_source.py CBP_CSMS")
        sources = get_sources()
        print("\nAvailable sources:", ", ".join(s["name"] for s in sources))
        sys.exit(1)

    name = sys.argv[1].upper()
    sources = get_sources()
    match = next((s for s in sources if s.get("name", "").upper() == name), None)

    if not match:
        print(f"Source '{name}' not found. Available: {', '.join(s['name'] for s in sources)}")
        sys.exit(1)

    r = _test_one_source(match)
    icon = "✓" if r["status"] == "ok" else "○" if r["status"] == "empty" else "✗" if r["status"] == "fail" else "-"
    print(f"{icon} {r['name']:25} {r['status']:8} items={r['items_count']}")
    if r.get("error"):
        print(f"   Error: {r['error']}")
    sys.exit(0 if r["status"] in ("ok", "empty") else 1)


if __name__ == "__main__":
    main()
