#!/usr/bin/env python3
"""
Test all regulatory sources from the command line.
Run from backend dir: python scripts/test_regulatory_sources.py

Bypasses API/frontend to verify feeds work.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.regulatory_feed_poller import test_all_sources


def main():
    print("Testing all regulatory sources...")
    print("-" * 60)
    results = test_all_sources()
    ok = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r["status"] == "empty")
    fail = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"Summary: {ok} OK, {empty} empty, {fail} fail, {skipped} skipped")
    print("-" * 60)
    for r in results:
        status_icon = "✓" if r["status"] == "ok" else "○" if r["status"] == "empty" else "✗" if r["status"] == "fail" else "-"
        err = f" | {r['error'][:50]}..." if r.get("error") else ""
        print(f"  {status_icon} {r['name']:25} {r['status']:8} items={r['items_count']:3}{err}")
    print("-" * 60)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
