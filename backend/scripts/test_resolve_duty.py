"""
Test script for resolve_duty() database integration - Sprint 5.3 Step 4

Usage:
    python scripts/test_resolve_duty.py "6112.20.20.30"
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session_maker
from scripts.duty_resolution import resolve_duty
import json


async def main():
    """Test resolve_duty() with database."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_resolve_duty.py <hts_code>")
        print("Example: python scripts/test_resolve_duty.py '6112.20.20.30'")
        sys.exit(1)
    
    hts_code = sys.argv[1]
    
    print(f"Resolving duty for: {hts_code}")
    print("-" * 60)
    
    try:
        async with async_session_maker() as db:
            resolved = await resolve_duty(hts_code, db)
            
            print("\n=== ResolvedDuty Result ===")
            print(json.dumps(resolved.to_dict(), indent=2))
            
            print("\n=== Key Fields ===")
            print(f"HTS Code: {resolved.hts_code}")
            print(f"\nGeneral Duty: {resolved.resolved_general_raw}")
            print(f"  Explanation: {resolved.explanation_general}")
            print(f"\nSpecial Duty: {resolved.resolved_special_raw}")
            print(f"  Explanation: {resolved.explanation_special}")
            print(f"\nColumn 2 Duty: {resolved.resolved_col2_raw}")
            print(f"  Explanation: {resolved.explanation_col2}")
            print(f"\nInheritance Path: {resolved.explanation_path}")
            print(f"\nFlags: {[f.value for f in resolved.flags]}")
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
