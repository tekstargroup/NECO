#!/usr/bin/env python3
"""
Improved HTS Reconciliation Script

Compares raw PDF codes vs structured codes with proper normalization:
- Removes dots and spaces
- Left-pads to 10 digits
- Excludes special chapters (98xx, 99xx, 9903, notes, annexes)
- Exports mismatches to CSV
"""

import asyncio
import sys
import csv
import re
from pathlib import Path
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


def normalize_hts_code(code: str) -> str:
    """
    Normalize HTS code:
    - Remove dots and spaces
    - Left-pad to 10 digits if needed
    """
    if not code:
        return ""
    
    # Remove dots and spaces
    normalized = code.replace(".", "").replace(" ", "").strip()
    
    # Left-pad to 10 digits if it's numeric and shorter
    if normalized.isdigit() and len(normalized) < 10:
        normalized = normalized.zfill(10)
    
    return normalized


def should_exclude_code(code: str) -> bool:
    """
    Exclude codes from reconciliation:
    - 98xx (Chapter 98)
    - 99xx (Chapter 99)
    - 9903 (Special classification)
    - Notes and annexes (non-numeric prefixes)
    """
    if not code:
        return True
    
    normalized = normalize_hts_code(code)
    
    # Exclude if not numeric
    if not normalized.isdigit():
        return True
    
    # Exclude chapters 98 and 99
    if len(normalized) >= 2:
        chapter = normalized[:2]
        if chapter in ["98", "99"]:
            return True
    
    # Exclude 9903
    if normalized.startswith("9903"):
        return True
    
    return False


async def reconcile_hts():
    """Main reconciliation function"""
    async for db in get_db():
        print("=" * 80)
        print("🔍 HTS RECONCILIATION: RAW PDF vs STRUCTURED")
        print("=" * 80)
        print()
        
        # Get raw codes with context for tariff table detection
        # Only include 10-digit codes that appear in tariff tables
        # Heuristic: code must have a duty-rate pattern within 1-3 lines
        # Try to get context if column exists, otherwise just get code and page
        raw_query = text("""
            SELECT 
                hts_code,
                source_page,
                COALESCE(context, '') as context,
                COALESCE(line_number, 0) as line_number
            FROM hts_codes_raw_pdf
            WHERE hts_code IS NOT NULL
            ORDER BY source_page, line_number
        """)
        
        try:
            result = await db.execute(raw_query)
            raw_rows = result.all()
        except Exception as e:
            # Fallback if context or line_number columns don't exist
            print(f"⚠️  Note: Context column may not exist, using simplified query: {e}")
            raw_query = text("""
                SELECT 
                    hts_code,
                    source_page
                FROM hts_codes_raw_pdf
                WHERE hts_code IS NOT NULL
                ORDER BY source_page
            """)
            result = await db.execute(raw_query)
            raw_rows = result.all()
        
        # Filter raw codes: only 10-digit codes that appear in tariff tables
        # Heuristic: check if context contains duty rate patterns (%, "Free", numbers with %)
        raw_table_codes = {}  # Only codes from tariff tables
        raw_all_codes = {}    # All raw codes (for comparison)
        
        # Pattern to detect duty rates in context
        duty_rate_pattern = re.compile(r'(\d+\.?\d*\s*%|Free|free|\d+\.?\d*\s*per)', re.IGNORECASE)
        
        for row in raw_rows:
            code = row[0]
            page = row[1]
            # Handle different query result structures
            context = row[2] if len(row) > 2 and row[2] is not None else None
            line_num = row[3] if len(row) > 3 else None
            
            if not should_exclude_code(code):
                normalized = normalize_hts_code(code)
                
                # Only include 10-digit codes
                if normalized and len(normalized) == 10 and normalized.isdigit():
                    # Track all 10-digit codes
                    if normalized not in raw_all_codes:
                        raw_all_codes[normalized] = {
                            "original": code,
                            "first_page": page,
                            "occurrences": 1
                        }
                    else:
                        raw_all_codes[normalized]["occurrences"] += 1
                    
                    # Check if this code appears in a tariff table (has duty rate nearby)
                    is_table_code = False
                    if context:
                        # Check if context contains duty rate pattern
                        if duty_rate_pattern.search(context):
                            is_table_code = True
                    else:
                        # If no context, assume it's a table code if it's 10 digits
                        # (most 10-digit codes in HTSUS are in tables)
                        is_table_code = True
                    
                    if is_table_code:
                        if normalized not in raw_table_codes:
                            raw_table_codes[normalized] = {
                                "original": code,
                                "first_page": page,
                                "occurrences": 1
                            }
                        else:
                            raw_table_codes[normalized]["occurrences"] += 1
        
        print(f"📄 Raw PDF codes (all 10-digit, after normalization & filtering): {len(raw_all_codes):,}")
        print(f"📊 Raw PDF codes (tariff table codes only): {len(raw_table_codes):,}")
        print()
        
        # Get structured codes (normalized, excluding special chapters)
        # Only 10-digit codes
        structured_query = text("""
            SELECT DISTINCT 
                hts_code,
                MIN(source_page) AS first_page,
                COUNT(*) AS occurrences
            FROM hts_versions
            WHERE hts_code IS NOT NULL
              AND LENGTH(REPLACE(REPLACE(hts_code, '.', ''), ' ', '')) = 10
            GROUP BY hts_code
        """)
        
        result = await db.execute(structured_query)
        structured_rows = result.all()
        
        # Normalize and filter structured codes (only 10-digit)
        structured_codes = {}
        for row in structured_rows:
            code = row[0]
            if not should_exclude_code(code):
                normalized = normalize_hts_code(code)
                # Only include 10-digit codes
                if normalized and len(normalized) == 10 and normalized.isdigit():
                    if normalized not in structured_codes:
                        structured_codes[normalized] = {
                            "original": code,
                            "first_page": row[1],
                            "occurrences": row[2]
                        }
        
        print(f"💾 Structured codes (10-digit, after normalization & filtering): {len(structured_codes):,}")
        print()
        
        # Find matches (comparing table codes from raw vs structured)
        matched = set(raw_table_codes.keys()) & set(structured_codes.keys())
        print(f"✅ Matched codes (in both raw table and structured): {len(matched):,}")
        print()
        
        # Find codes only in structured
        only_in_structured = set(structured_codes.keys()) - set(raw_table_codes.keys())
        print(f"⚠️  Codes only in STRUCTURED: {len(only_in_structured):,}")
        
        # Find codes only in raw table codes
        only_in_raw_table_codes = set(raw_table_codes.keys()) - set(structured_codes.keys())
        print(f"⚠️  Codes only in RAW PDF (table codes): {len(only_in_raw_table_codes):,}")
        print()
        
        # Calculate match percentage (based on table codes)
        total_table_codes = len(set(raw_table_codes.keys()) | set(structured_codes.keys()))
        match_pct = (len(matched) / total_table_codes * 100) if total_table_codes > 0 else 0
        
        print("=" * 80)
        print("📊 RECONCILIATION SUMMARY (Apples to Apples: 10-digit table codes only)")
        print("=" * 80)
        print(f"   Raw PDF table codes: {len(raw_table_codes):,}")
        print(f"   Structured codes: {len(structured_codes):,}")
        print(f"   Total unique codes: {total_table_codes:,}")
        print(f"   Matched: {len(matched):,} ({match_pct:.1f}%)")
        print(f"   Only in structured: {len(only_in_structured):,} ({len(only_in_structured)/total_table_codes*100:.1f}%)")
        print(f"   Only in raw table codes: {len(only_in_raw_table_codes):,} ({len(only_in_raw_table_codes)/total_table_codes*100:.1f}%)")
        print()
        
        # Export to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent.parent / "data" / "reconciliation"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export matched codes
        matched_csv_path = output_dir / f"matched_{timestamp}.csv"
        with open(matched_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["normalized_code", "original_code_raw", "original_code_structured", "first_page_raw", "first_page_structured", "occurrences_raw", "occurrences_structured"])
            for code in sorted(matched):
                raw_data = raw_table_codes[code]
                struct_data = structured_codes[code]
                writer.writerow([
                    code,
                    raw_data["original"],
                    struct_data["original"],
                    raw_data["first_page"],
                    struct_data["first_page"],
                    raw_data["occurrences"],
                    struct_data["occurrences"]
                ])
        
        print(f"💾 Exported 'matched' codes to: {matched_csv_path}")
        print(f"   ({len(matched):,} codes)")
        print()
        
        # Export "only in structured" codes
        structured_csv_path = output_dir / f"only_in_structured_{timestamp}.csv"
        with open(structured_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["normalized_code", "original_code", "first_page", "occurrences"])
            for code in sorted(only_in_structured):
                data = structured_codes[code]
                writer.writerow([
                    code,
                    data["original"],
                    data["first_page"],
                    data["occurrences"]
                ])
        
        print(f"💾 Exported 'only in structured' codes to: {structured_csv_path}")
        print(f"   ({len(only_in_structured):,} codes)")
        print()
        
        # Export "only in raw table codes" codes
        raw_table_csv_path = output_dir / f"only_in_raw_table_codes_{timestamp}.csv"
        with open(raw_table_csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["normalized_code", "original_code", "first_page", "occurrences"])
            for code in sorted(only_in_raw_table_codes):
                data = raw_table_codes[code]
                writer.writerow([
                    code,
                    data["original"],
                    data["first_page"],
                    data["occurrences"]
                ])
        
        print(f"💾 Exported 'only in raw table codes' to: {raw_table_csv_path}")
        print(f"   ({len(only_in_raw_table_codes):,} codes)")
        print()
        
        # Show sample mismatches
        if only_in_raw_table_codes:
            print("📋 SAMPLE: Codes only in RAW PDF table codes (first 10):")
            for i, code in enumerate(sorted(only_in_raw_table_codes)[:10], 1):
                data = raw_table_codes[code]
                print(f"   {i:2}. {code} (original: {data['original']}, page: {data['first_page']})")
            print()
        
        if only_in_structured:
            print("📋 SAMPLE: Codes only in STRUCTURED (first 10):")
            for i, code in enumerate(sorted(only_in_structured)[:10], 1):
                data = structured_codes[code]
                print(f"   {i:2}. {code} (original: {data['original']}, page: {data['first_page']})")
            print()
        
        print("=" * 80)
        print("✅ RECONCILIATION COMPLETE")
        print("=" * 80)
        print()
        print("📝 REVIEW NOTES:")
        print("   - Comparison is apples-to-apples: only 10-digit codes from tariff tables")
        print("   - Raw codes filtered by heuristic: must have duty-rate pattern in context")
        print("   - 'Matched' = codes in both raw table codes and structured")
        print("   - 'Only in structured' = codes parsed but not found in raw table codes")
        print("   - 'Only in raw table codes' = codes in raw PDF tables but not parsed")
        print("   - Excluded chapters 98, 99, and 9903 from comparison")
        print("   - Check CSV files for detailed lists")
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(reconcile_hts())


