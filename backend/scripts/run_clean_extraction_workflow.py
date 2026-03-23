"""
Workflow Script: Clean Extraction + Validation - Sprint 5.3

Runs the complete workflow:
1. Extract codes with fixed extractor (no .00 synthetic codes)
2. Load to new hts_version_id
3. Verify no .00 codes
4. Cleanup old version
5. Re-run validation and backfill
"""

import sys
import asyncio
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.regenerate_structured_hts_codes_v2 import extract_structured_codes_from_pdf, persist_to_jsonl, generate_extraction_report
from scripts.load_structured_codes_to_hts_nodes import load_structured_codes_to_hts_nodes
from scripts.cleanup_bogus_00_codes import find_synthetic_10_digit_codes
from scripts.validate_duty_resolution import run_validation
from scripts.backfill_parent_duties import backfill_parent_duties
from app.core.database import async_session_maker
from sqlalchemy import select, text
from app.models.hts_node import HTSNode
import json

async def check_00_codes(hts_version_id: str) -> dict:
    """Check for .00 codes in a version."""
    async with async_session_maker() as db:
        query = select(HTSNode).where(
            HTSNode.level == 10,
            HTSNode.code_normalized.like("%00")
        )
        if hts_version_id:
            query = query.where(HTSNode.hts_version_id == hts_version_id)
        else:
            query = query.where(HTSNode.hts_version_id.is_(None))
        
        result = await db.execute(query)
        nodes = list(result.scalars().all())
        
        # Filter valid ones (not marked invalid)
        valid_00 = []
        invalid_00 = []
        for node in nodes:
            if node.source_lineage and node.source_lineage.get("is_valid") is False:
                invalid_00.append(node.code_normalized)
            else:
                valid_00.append(node.code_normalized)
        
        return {
            "total_ending_00": len(nodes),
            "valid_ending_00": len(valid_00),
            "invalid_ending_00": len(invalid_00),
            "valid_codes": valid_00[:10],  # First 10
        }

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
                }
            else:
                found[code] = {"exists": False, "valid": False, "has_duties": False}
        
        return found

async def main():
    """Run complete workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean extraction workflow")
    parser.add_argument("--pdf-path", type=str, help="Path to HTS PDF")
    parser.add_argument("--old-version-id", type=str, default=None, help="Old version ID to cleanup")
    parser.add_argument("--skip-extraction", action="store_true", help="Skip extraction (use existing JSONL)")
    parser.add_argument("--jsonl-path", type=str, default="data/hts_tariff/structured_hts_codes_v2.jsonl", help="JSONL file path")
    
    args = parser.parse_args()
    
    # Generate new version ID
    new_version_id = str(uuid.uuid4())
    print("=" * 80)
    print("Clean Extraction Workflow - Sprint 5.3")
    print("=" * 80)
    print(f"New HTS Version ID: {new_version_id}")
    print(f"Old HTS Version ID: {args.old_version_id or 'None (NULL)'}")
    print()
    
    # Step 1: Extract (if not skipped)
    jsonl_path = Path(args.jsonl_path)
    if not args.skip_extraction:
        if not args.pdf_path:
            print("ERROR: --pdf-path required for extraction")
            sys.exit(1)
        
        pdf_path = Path(args.pdf_path)
        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}")
            sys.exit(1)
        
        print("Step 1: Extracting codes from PDF...")
        structured_codes, extraction_metadata = extract_structured_codes_from_pdf(pdf_path)
        
        if not jsonl_path.is_absolute():
            jsonl_path = Path(__file__).parent.parent.parent / jsonl_path
        
        persist_to_jsonl(structured_codes, jsonl_path)
        print(f"✅ Extracted {len(structured_codes):,} codes to {jsonl_path}")
    else:
        print(f"Step 1: Skipping extraction, using existing JSONL: {jsonl_path}")
    
    # Step 2: Load to new version
    print()
    print("Step 2: Loading codes to database with new version ID...")
    await load_structured_codes_to_hts_nodes(
        jsonl_path=jsonl_path,
        hts_version_id=new_version_id,
        batch_size=1000,
        dry_run=False
    )
    
    # Step 3: Verify no .00 codes in new version
    print()
    print("Step 3: Verifying no .00 codes in new version...")
    check_result = await check_00_codes(new_version_id)
    print(f"  Total codes ending in '00': {check_result['total_ending_00']}")
    print(f"  Valid codes ending in '00': {check_result['valid_ending_00']}")
    print(f"  Invalid codes ending in '00': {check_result['invalid_ending_00']}")
    
    if check_result['valid_ending_00'] > 0:
        print(f"  ⚠️  WARNING: Found {check_result['valid_ending_00']} valid .00 codes!")
        print(f"  Examples: {check_result['valid_codes'][:5]}")
    else:
        print("  ✅ No valid .00 codes found")
    
    # Step 4: Check Page 2198 codes
    print()
    print("Step 4: Checking Page 2198 codes...")
    page2198 = await check_page_2198_codes(new_version_id)
    found_count = sum(1 for v in page2198.values() if v.get("exists") and v.get("valid"))
    print(f"  Found {found_count}/{len(page2198)} expected codes")
    for code, info in page2198.items():
        status = "✅" if info.get("exists") and info.get("valid") else "❌"
        print(f"    {status} {code}: exists={info.get('exists')}, valid={info.get('valid')}, has_duties={info.get('has_duties')}")
    
    # Step 5: Cleanup old version
    if args.old_version_id:
        print()
        print(f"Step 5: Cleaning up old version {args.old_version_id}...")
        cleanup_report = await find_synthetic_10_digit_codes(args.old_version_id, dry_run=False)
        print(f"  Marked {cleanup_report['bogus_codes_marked']} bogus codes as invalid")
    
    # Step 6: Re-run validation
    print()
    print("Step 6: Running validation...")
    # Note: validation script needs to be updated to accept version_id
    print("  (Validation script needs version_id parameter - manual run required)")
    
    # Step 7: Re-run backfill
    print()
    print("Step 7: Running backfill...")
    async with async_session_maker() as db:
        backfill_report = await backfill_parent_duties(db, new_version_id, dry_run=False)
        print(f"  Parents updated: {sum(backfill_report['parents_updated']['level_6'].values()) + sum(backfill_report['parents_updated']['level_8'].values())}")
    
    print()
    print("=" * 80)
    print("Workflow Complete")
    print("=" * 80)
    print(f"New Version ID: {new_version_id}")
    print(f"Valid .00 codes: {check_result['valid_ending_00']} (must be 0)")
    print(f"Page 2198 codes found: {found_count}/{len(page2198)}")

if __name__ == "__main__":
    asyncio.run(main())
