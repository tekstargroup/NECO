"""
Cleanup Script: Remove Bogus ".00" 10-digit Codes - Sprint 5.3

Finds and marks/removes synthetic 10-digit codes ending in "00" that were created
from base rows without actual suffix tokens.
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text, and_
from app.core.database import async_session_maker
from app.models.hts_node import HTSNode


async def find_synthetic_10_digit_codes(
    hts_version_id: Optional[str],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Find and mark synthetic 10-digit codes (emitted without real suffix token).
    
    A code is considered synthetic (bogus) if:
    - It's a 10-digit code (level == 10)
    - Source lineage shows NO valid suffix token evidence:
      - suffix_token_text is missing/null, OR
      - suffix_token_band != "SUFFIX_BAND", OR
      - component_parts/suffix provenance missing
    
    NOTE: Codes ending in "00" are VALID if they have suffix_token_text == "00" and suffix_token_band == "SUFFIX_BAND"
    """
    report = {
        "hts_version_id": hts_version_id or "None",
        "dry_run": dry_run,
        "synthetic_codes_found": [],
        "synthetic_codes_marked": 0,
        "total_10_digit_checked": 0,
        "valid_00_codes_found": 0,
    }
    
    async with async_session_maker() as db:
        # Find ALL 10-digit codes (not just those ending in "00")
        query = select(HTSNode).where(
            HTSNode.level == 10
        )
        if hts_version_id:
            query = query.where(HTSNode.hts_version_id == hts_version_id)
        else:
            query = query.where(HTSNode.hts_version_id.is_(None))
        
        result = await db.execute(query)
        nodes = list(result.scalars().all())
        
        report["total_10_digit_checked"] = len(nodes)
        
        for node in nodes:
            # Check if this is a synthetic code (missing suffix token evidence)
            is_synthetic = False
            reason = None
            
            if node.source_lineage:
                component_parts = node.source_lineage.get("component_parts", {})
                suffix_token_text = component_parts.get("suffix_token_text")
                suffix_token_band = component_parts.get("suffix_token_band")
                suffix_provenance = node.source_lineage.get("suffix_provenance", {})
                
                # Check for missing suffix token evidence
                if suffix_token_text is None:
                    # Missing suffix_token_text - synthetic
                    is_synthetic = True
                    reason = "Missing suffix_token_text in component_parts (synthetic emission)"
                elif suffix_token_band != "SUFFIX_BAND":
                    # Suffix token not in SUFFIX_BAND - synthetic
                    is_synthetic = True
                    reason = f"Suffix token not in SUFFIX_BAND (band: {suffix_token_band})"
                elif not suffix_provenance:
                    # Missing suffix_provenance - likely old extraction, check if component_parts has required fields
                    if not component_parts.get("suffix_token_text") or not component_parts.get("suffix_token_band"):
                        is_synthetic = True
                        reason = "Missing suffix_provenance and incomplete component_parts (likely synthetic)"
            else:
                # No source lineage at all - likely old extraction, treat as synthetic
                is_synthetic = True
                reason = "No source_lineage metadata (likely synthetic from old extractor)"
            
            # Track valid .00 codes for reporting
            if node.code_normalized.endswith("00") and not is_synthetic:
                report["valid_00_codes_found"] += 1
            
            if is_synthetic:
                report["synthetic_codes_found"].append({
                    "code_normalized": node.code_normalized,
                    "code_display": node.code_display,
                    "reason": reason,
                    "source_lineage": node.source_lineage,
                })
                
                if not dry_run:
                    # Mark as invalid in source_lineage
                    meta = node.source_lineage or {}
                    meta["is_valid"] = False
                    meta["invalid_reason"] = "SYNTHETIC_10_DIGIT_WITHOUT_SUFFIX_TOKEN"
                    node.source_lineage = meta
                    report["synthetic_codes_marked"] += 1
                
        if not dry_run:
            await db.commit()
    
    return report


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup synthetic 10-digit codes (emitted without real suffix token)"
    )
    parser.add_argument(
        "--hts-version-id",
        required=False,
        default=None,
        help="HTS version ID to process (use 'None' for null version_id)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no database writes)"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete bogus codes instead of just marking them (use with caution)"
    )
    
    args = parser.parse_args()
    
    hts_version_id = None
    if args.hts_version_id and args.hts_version_id.lower() != "none":
        try:
            hts_version_id = str(UUID(args.hts_version_id))
        except ValueError:
            print(f"ERROR: Invalid UUID format: {args.hts_version_id}")
            sys.exit(1)
    
    print("=" * 80)
    print("Cleanup Synthetic 10-digit Codes - Sprint 5.3")
    print("=" * 80)
    print(f"HTS Version ID: {hts_version_id or 'None'}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    report = await find_synthetic_10_digit_codes(hts_version_id, dry_run=args.dry_run)
    
    print("=" * 80)
    print("Cleanup Report")
    print("=" * 80)
    print(f"Total 10-digit codes checked: {report['total_10_digit_checked']}")
    print(f"Synthetic codes found: {len(report['synthetic_codes_found'])}")
    print(f"Synthetic codes marked: {report['synthetic_codes_marked']}")
    print(f"Valid .00 codes found: {report['valid_00_codes_found']}")
    print()
    
    if report["synthetic_codes_found"]:
        print("Synthetic codes found (missing suffix token evidence):")
        for code_info in report["synthetic_codes_found"][:20]:  # Show first 20
            print(f"  {code_info['code_display']} ({code_info['code_normalized']}): {code_info['reason']}")
        if len(report["synthetic_codes_found"]) > 20:
            print(f"  ... and {len(report['synthetic_codes_found']) - 20} more")
    
    if report["valid_00_codes_found"] > 0:
        print()
        print(f"✅ Found {report['valid_00_codes_found']} valid .00 codes (with suffix_token_text='00' and suffix_token_band='SUFFIX_BAND')")
    
    # Save full report
    import json
    output_file = Path(__file__).parent / f"cleanup_synthetic_codes_report_{hts_version_id or 'None'}.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
