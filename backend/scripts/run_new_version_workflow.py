"""
Workflow Script: Create NEW clean version and validate - Sprint 5.3

Step A: Generate NEW clean version (authoritative)
1. Create NEW_UUID
2. Run fixed extractor to JSONL
3. Load JSONL into NEW_UUID
4. Run cleanup dry-run on NEW_UUID (expect ~0 synthetic)
5. Run Page 2198 goldens against NEW_UUID
6. Run validate_duty_resolution.py against NEW_UUID
"""

import sys
import asyncio
import uuid
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.load_structured_codes_to_hts_nodes import load_structured_codes_to_hts_nodes
from scripts.cleanup_bogus_00_codes import find_synthetic_10_digit_codes
from scripts.validate_duty_resolution import VALIDATION_CODES, validate_resolved_duty
from scripts.duty_resolution import resolve_duty, ResolvedDuty
from app.core.database import async_session_maker
from sqlalchemy import select, text
from app.models.hts_node import HTSNode

NEW_UUID = "792bb867-c549-4769-80ca-d9d1adc883a3"  # Generated UUID
JSONL_PATH = Path("data/hts_tariff/structured_hts_codes_v2_clean.jsonl")

async def check_page_2198_codes(hts_version_id: str) -> dict:
    """Check Page 2198 codes."""
    expected_codes = [
        "6112201010", "6112201020", "6112201030", "6112201040", "6112201090",
        "6112202010", "6112202020", "6112202030",
    ]
    
    async with async_session_maker() as db:
        found = {}
        for code in expected_codes:
            query = select(HTSNode).where(
                HTSNode.code_normalized == code,
                HTSNode.level == 10
            )
            if hts_version_id:
                query = query.where(HTSNode.hts_version_id == hts_version_id)
            else:
                query = query.where(HTSNode.hts_version_id.is_(None))
            
            result = await db.execute(query)
            node = result.scalar_one_or_none()
            
            if node:
                # Check if valid
                is_valid = not (node.source_lineage and node.source_lineage.get("is_valid") is False)
                found[code] = {
                    "exists": True,
                    "valid": is_valid,
                    "has_duties": bool(node.duty_general_raw or node.duty_special_raw or node.duty_column2_raw),
                    "duty_general": node.duty_general_raw,
                    "duty_special": node.duty_special_raw,
                    "duty_col2": node.duty_column2_raw,
                }
            else:
                found[code] = {"exists": False, "valid": False, "has_duties": False}
        
        return found

async def get_node_counts(hts_version_id: str) -> dict:
    """Get node counts by level."""
    async with async_session_maker() as db:
        query = select(HTSNode).where(HTSNode.hts_version_id == hts_version_id)
        result = await db.execute(query)
        nodes = list(result.scalars().all())
        
        counts = {"6": 0, "8": 0, "10": 0, "total": len(nodes)}
        for node in nodes:
            if node.level == 6:
                counts["6"] += 1
            elif node.level == 8:
                counts["8"] += 1
            elif node.level == 10:
                counts["10"] += 1
        
        return counts

async def main():
    """Run complete workflow."""
    print("=" * 80)
    print("NEW Clean Version Workflow - Sprint 5.3")
    print("=" * 80)
    print(f"NEW_UUID: {NEW_UUID}")
    print()
    
    # Step 1: Check if JSONL exists
    jsonl_path = Path(__file__).parent.parent.parent / JSONL_PATH
    if not jsonl_path.exists():
        print(f"❌ JSONL file not found: {jsonl_path}")
        print("   Please run extractor first:")
        print(f"   python scripts/regenerate_structured_hts_codes_v2.py --pdf-path '../CBP Docs/2025HTS.pdf' --output '{JSONL_PATH}'")
        return
    
    print(f"✅ JSONL file found: {jsonl_path}")
    print(f"   Size: {jsonl_path.stat().st_size / 1024 / 1024:.2f} MB")
    print()
    
    # Step 2: Load JSONL into NEW_UUID
    print("Step 2: Loading JSONL into NEW_UUID...")
    await load_structured_codes_to_hts_nodes(
        jsonl_path=jsonl_path,
        hts_version_id=NEW_UUID,
        batch_size=1000,
        dry_run=False
    )
    print()
    
    # Step 3: Get node counts
    print("Step 3: Getting node counts...")
    counts = await get_node_counts(NEW_UUID)
    print(f"   Total nodes: {counts['total']:,}")
    print(f"   Level 6: {counts['6']:,}")
    print(f"   Level 8: {counts['8']:,}")
    print(f"   Level 10: {counts['10']:,}")
    print()
    
    # Step 4: Run cleanup dry-run
    print("Step 4: Running cleanup dry-run on NEW_UUID...")
    cleanup_report = await find_synthetic_10_digit_codes(NEW_UUID, dry_run=True)
    synthetic_count = len(cleanup_report["synthetic_codes_found"])
    total_10_digit = cleanup_report["total_10_digit_checked"]
    valid_00_count = cleanup_report["valid_00_codes_found"]
    
    print(f"   Total 10-digit codes checked: {total_10_digit:,}")
    print(f"   Synthetic codes found: {synthetic_count}")
    print(f"   Valid .00 codes found: {valid_00_count}")
    
    if synthetic_count > 10:
        print(f"   ⚠️  WARNING: Found {synthetic_count} synthetic codes (expected ~0)")
        print("   First 10 synthetic codes:")
        for code_info in cleanup_report["synthetic_codes_found"][:10]:
            print(f"     {code_info['code_display']}: {code_info['reason']}")
    else:
        print(f"   ✅ Synthetic count is {synthetic_count} (near zero as expected)")
    print()
    
    # Step 5: Check Page 2198 codes
    print("Step 5: Checking Page 2198 codes...")
    page2198 = await check_page_2198_codes(NEW_UUID)
    found_count = sum(1 for v in page2198.values() if v.get("exists") and v.get("valid"))
    print(f"   Found {found_count}/{len(page2198)} expected codes")
    
    missing = []
    for code, info in page2198.items():
        if info.get("exists") and info.get("valid"):
            print(f"   ✅ {code}: exists={info.get('exists')}, valid={info.get('valid')}, has_duties={info.get('has_duties')}")
        else:
            missing.append(code)
            print(f"   ❌ {code}: exists={info.get('exists')}, valid={info.get('valid')}")
    
    if missing:
        print(f"   ⚠️  Missing codes: {missing}")
    else:
        print(f"   ✅ All Page 2198 codes found and valid")
    print()
    
    # Step 6: Run validation
    print("Step 6: Running validate_duty_resolution.py...")
    print("   (Note: This may take a few minutes)")
    
    validation_results = []
    passed = 0
    failed = 0
    
    async with async_session_maker() as db:
        for hts_code in VALIDATION_CODES:
            try:
                resolved = await resolve_duty(hts_code, db, hts_version_id=NEW_UUID)
                validation = validate_resolved_duty(resolved, hts_code)
                validation_results.append({
                    "hts_code": hts_code,
                    "valid": validation.get("valid", False),
                    "resolved": resolved.__dict__ if resolved else None,
                    "issues": validation.get("issues", []),
                    "warnings": validation.get("warnings", []),
                })
                if validation.get("valid", False):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                validation_results.append({
                    "hts_code": hts_code,
                    "valid": False,
                    "error": str(e),
                })
                failed += 1
    
    validation_result = {
        "total_tested": len(VALIDATION_CODES),
        "passed": passed,
        "failed": failed,
        "results": validation_results,
    }
    
    print(f"   Total codes tested: {len(VALIDATION_CODES)}")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    if failed > 0:
        print("   Failed codes:")
        for r in validation_results:
            if not r.get("valid", False):
                print(f"     - {r['hts_code']}: {r.get('issues', r.get('error', 'Unknown error'))}")
    print()
    
    # Summary
    print("=" * 80)
    print("WORKFLOW SUMMARY")
    print("=" * 80)
    print(f"NEW_UUID: {NEW_UUID}")
    print(f"Total nodes: {counts['total']:,}")
    print(f"   Level 6: {counts['6']:,}")
    print(f"   Level 8: {counts['8']:,}")
    print(f"   Level 10: {counts['10']:,}")
    print()
    print(f"Synthetic codes (dry-run): {synthetic_count} (expected ~0)")
    print(f"Valid .00 codes: {valid_00_count}")
    print()
    print(f"Page 2198 codes found: {found_count}/{len(page2198)}")
    print()
    print("Validation summary:")
    print(json.dumps(validation_result, indent=2, default=str))
    print()
    
    # Save report
    report = {
        "new_uuid": NEW_UUID,
        "node_counts": counts,
        "cleanup_report": {
            "synthetic_count": synthetic_count,
            "total_10_digit": total_10_digit,
            "valid_00_count": valid_00_count,
        },
        "page_2198": page2198,
        "validation_result": validation_result,
    }
    
    report_file = Path(__file__).parent / f"new_version_workflow_report_{NEW_UUID[:8]}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Full report saved to: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())
