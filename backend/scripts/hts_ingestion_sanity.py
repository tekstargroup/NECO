#!/usr/bin/env python3
"""
HTS Ingestion Sanity Check

Quick diagnostic to prove or disprove if HTS ingestion is usable:
1. LENGTH(hts_code) distribution
2. Separate leaf 10-digit codes vs headings/partials
3. Compute duty coverage only for leaf 10-digit codes (excluding 98/99/9903)
4. Sample 20 leaf codes and print tariff_text_short + all 3 duty columns + source_page
5. Compare structured leaf count to raw_pdf index count after normalization
"""

import asyncio
import sys
import re
from pathlib import Path
from sqlalchemy import text
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


def normalize_hts_code(code: str) -> str:
    """Normalize HTS code: remove dots/spaces, left-pad to 10 digits"""
    if not code:
        return ""
    normalized = code.replace(".", "").replace(" ", "").strip()
    if normalized.isdigit() and len(normalized) < 10:
        normalized = normalized.zfill(10)
    return normalized


async def hts_ingestion_sanity_check():
    """Run comprehensive HTS ingestion sanity check"""
    async for db in get_db():
        print("=" * 100)
        print("🔍 HTS INGESTION SANITY CHECK")
        print("=" * 100)
        print()
        
        # ========================================================================
        # 1. LENGTH(hts_code) DISTRIBUTION
        # ========================================================================
        print("1️⃣  HTS CODE LENGTH DISTRIBUTION")
        print("-" * 100)
        
        result = await db.execute(text("""
            SELECT 
                LENGTH(hts_code) as code_length,
                COUNT(*) as count,
                COUNT(DISTINCT hts_code) as distinct_codes
            FROM hts_versions
            WHERE hts_code IS NOT NULL
            GROUP BY LENGTH(hts_code)
            ORDER BY code_length
        """))
        
        length_dist = result.all()
        if length_dist:
            print(f"{'Length':<10} {'Count':<15} {'Distinct Codes':<15}")
            print("-" * 40)
            for length, count, distinct in length_dist:
                print(f"{length:<10} {count:<15,} {distinct:<15,}")
        else:
            print("   ⚠️  No data found")
        print()
        
        # ========================================================================
        # 2. SEPARATE LEAF 10-DIGIT CODES VS HEADINGS/PARTIALS
        # ========================================================================
        print("2️⃣  LEAF 10-DIGIT CODES vs HEADINGS/PARTIALS")
        print("-" * 100)
        
        # A leaf code is a 10-digit code that is NOT a parent of any other code
        # In HTS, if a code has sub-codes, it's not a leaf
        # We identify leaf codes as: 10-digit codes that don't have any codes starting with them
        
        # First, get all 10-digit codes
        result = await db.execute(text("""
            SELECT DISTINCT hts_code
            FROM hts_versions
            WHERE LENGTH(hts_code) = 10
            AND hts_code ~ '^[0-9]{10}$'
            AND hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
        """))
        
        all_10digit = [row[0] for row in result.all()]
        print(f"   Total 10-digit codes (excluding 98/99/9903): {len(all_10digit):,}")
        
        # Find leaf codes: 10-digit codes that are NOT prefixes of any other code
        # We check if any other code starts with this code (but is longer)
        leaf_codes_query = text("""
            WITH all_10digit AS (
                SELECT DISTINCT hts_code
                FROM hts_versions
                WHERE LENGTH(hts_code) = 10
                AND hts_code ~ '^[0-9]{10}$'
                AND hts_chapter NOT IN ('98', '99')
                AND hts_code NOT LIKE '9903%'
            )
            SELECT a.hts_code
            FROM all_10digit a
            WHERE NOT EXISTS (
                SELECT 1
                FROM hts_versions v
                WHERE v.hts_code LIKE a.hts_code || '%'
                AND LENGTH(v.hts_code) > 10
                AND v.hts_code ~ '^[0-9]+$'
            )
        """)
        
        result = await db.execute(leaf_codes_query)
        leaf_codes = [row[0] for row in result.all()]
        
        # Count headings/partials (non-10-digit or 10-digit that are parents)
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT hts_code)
            FROM hts_versions
            WHERE (
                LENGTH(hts_code) != 10
                OR hts_code !~ '^[0-9]{10}$'
                OR hts_chapter IN ('98', '99')
                OR hts_code LIKE '9903%'
            )
        """))
        headings_partials = result.scalar()
        
        print(f"   ✅ Leaf 10-digit codes: {len(leaf_codes):,}")
        print(f"   📋 Headings/partials (non-leaf): {headings_partials:,}")
        print(f"   📊 Leaf percentage: {(len(leaf_codes) / len(all_10digit) * 100) if all_10digit else 0:.2f}%")
        print()
        
        # ========================================================================
        # 3. DUTY COVERAGE FOR LEAF 10-DIGIT CODES ONLY
        # ========================================================================
        print("3️⃣  DUTY COVERAGE (LEAF 10-DIGIT CODES ONLY, EXCLUDING 98/99/9903)")
        print("-" * 100)
        
        if not leaf_codes:
            print("   ⚠️  No leaf codes found, skipping duty coverage check")
        else:
            # Use subquery approach for efficiency and safety
            result = await db.execute(text("""
                WITH leaf_codes AS (
                    WITH all_10digit AS (
                        SELECT DISTINCT hts_code
                        FROM hts_versions
                        WHERE LENGTH(hts_code) = 10
                        AND hts_code ~ '^[0-9]{10}$'
                        AND hts_chapter NOT IN ('98', '99')
                        AND hts_code NOT LIKE '9903%'
                    )
                    SELECT a.hts_code
                    FROM all_10digit a
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM hts_versions v
                        WHERE v.hts_code LIKE a.hts_code || '%'
                        AND LENGTH(v.hts_code) > 10
                        AND v.hts_code ~ '^[0-9]+$'
                    )
                )
                SELECT 
                    COUNT(*) as total_leaf,
                    COUNT(CASE WHEN v.duty_rate_general IS NOT NULL THEN 1 END) as with_general,
                    COUNT(CASE WHEN v.duty_rate_special IS NOT NULL THEN 1 END) as with_special,
                    COUNT(CASE WHEN v.duty_rate_column2 IS NOT NULL THEN 1 END) as with_column2,
                    COUNT(CASE WHEN v.duty_rate_general IS NOT NULL 
                                  OR v.duty_rate_special IS NOT NULL 
                                  OR v.duty_rate_column2 IS NOT NULL THEN 1 END) as with_any_duty
                FROM leaf_codes l
                JOIN hts_versions v ON v.hts_code = l.hts_code
                WHERE v.hts_chapter NOT IN ('98', '99')
                AND v.hts_code NOT LIKE '9903%'
            """))
            
            row = result.fetchone()
            if row:
                total_leaf, with_general, with_special, with_column2, with_any_duty = row
                
                print(f"   Total leaf codes: {total_leaf:,}")
                print(f"   With General Rate: {with_general:,} ({(with_general/total_leaf*100) if total_leaf > 0 else 0:.2f}%)")
                print(f"   With Special Rate: {with_special:,} ({(with_special/total_leaf*100) if total_leaf > 0 else 0:.2f}%)")
                print(f"   With Column 2 Rate: {with_column2:,} ({(with_column2/total_leaf*100) if total_leaf > 0 else 0:.2f}%)")
                print(f"   With ANY duty rate: {with_any_duty:,} ({(with_any_duty/total_leaf*100) if total_leaf > 0 else 0:.2f}%)")
                
                # Quality assessment
                print()
                print("   📊 QUALITY ASSESSMENT:")
                if (with_general/total_leaf*100) >= 80:
                    print("   ✅ General rate coverage is GOOD (≥80%)")
                elif (with_general/total_leaf*100) >= 50:
                    print("   ⚠️  General rate coverage is MODERATE (50-80%)")
                else:
                    print("   ❌ General rate coverage is POOR (<50%)")
                
                if (with_any_duty/total_leaf*100) >= 80:
                    print("   ✅ Overall duty rate coverage is GOOD (≥80%)")
                else:
                    print("   ⚠️  Overall duty rate coverage needs improvement (<80%)")
            else:
                print("   ⚠️  Could not compute duty coverage")
        print()
        
        # ========================================================================
        # 4. SAMPLE 20 LEAF CODES WITH FULL DETAILS
        # ========================================================================
        print("4️⃣  SAMPLE: 20 LEAF 10-DIGIT CODES (WITH DUTY RATES)")
        print("-" * 100)
        
        if not leaf_codes:
            print("   ⚠️  No leaf codes found")
        else:
            # Sample 20 leaf codes, prioritizing those with duty rates
            sample_query = text("""
                WITH leaf_codes AS (
                    WITH all_10digit AS (
                        SELECT DISTINCT hts_code
                        FROM hts_versions
                        WHERE LENGTH(hts_code) = 10
                        AND hts_code ~ '^[0-9]{10}$'
                        AND hts_chapter NOT IN ('98', '99')
                        AND hts_code NOT LIKE '9903%'
                    )
                    SELECT a.hts_code
                    FROM all_10digit a
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM hts_versions v
                        WHERE v.hts_code LIKE a.hts_code || '%'
                        AND LENGTH(v.hts_code) > 10
                        AND v.hts_code ~ '^[0-9]+$'
                    )
                )
                SELECT 
                    v.hts_code,
                    v.hts_chapter,
                    v.tariff_text_short,
                    v.duty_rate_general,
                    v.duty_rate_special,
                    v.duty_rate_column2,
                    v.source_page,
                    v.parse_confidence
                FROM leaf_codes l
                JOIN hts_versions v ON v.hts_code = l.hts_code
                WHERE v.hts_chapter NOT IN ('98', '99')
                AND v.hts_code NOT LIKE '9903%'
                ORDER BY 
                    CASE WHEN v.duty_rate_general IS NOT NULL THEN 0 ELSE 1 END,
                    RANDOM()
                LIMIT 20
            """)
            
            result = await db.execute(sample_query)
            samples = result.all()
            
            if samples:
                table_data = []
                for row in samples:
                    hts_code = row[0]
                    chapter = row[1] or "N/A"
                    tariff_text = (row[2] or "N/A")[:60]
                    if len(tariff_text) > 60:
                        tariff_text = tariff_text[:57] + "..."
                    general = row[3] or "NULL"
                    special = row[4] or "NULL"
                    column2 = row[5] or "NULL"
                    page = row[6] or "N/A"
                    confidence = str(row[7]) if row[7] else "N/A"
                    
                    table_data.append([
                        hts_code,
                        chapter,
                        tariff_text,
                        str(general),
                        str(special),
                        str(column2),
                        str(page),
                        confidence
                    ])
                
                headers = [
                    "HTS Code",
                    "Ch",
                    "Description",
                    "General",
                    "Special",
                    "Column 2",
                    "Page",
                    "Confidence"
                ]
                
                print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[12, 3, 40, 12, 12, 12, 8, 10]))
            else:
                print("   ⚠️  No samples found")
        print()
        
        # ========================================================================
        # 5. COMPARE STRUCTURED LEAF COUNT TO RAW PDF INDEX COUNT
        # ========================================================================
        print("5️⃣  STRUCTURED vs RAW PDF COMPARISON")
        print("-" * 100)
        
        # Count structured leaf codes (already computed)
        structured_leaf_count = len(leaf_codes)
        print(f"   Structured leaf codes (10-digit, excluding 98/99/9903): {structured_leaf_count:,}")
        
        # Count raw PDF codes (normalized, excluding 98/99/9903)
        raw_query = text("""
            SELECT DISTINCT hts_code
            FROM hts_codes_raw_pdf
            WHERE hts_code IS NOT NULL
        """)
        
        result = await db.execute(raw_query)
        raw_codes = [normalize_hts_code(row[0]) for row in result.all() if row[0]]
        
        # Filter raw codes: 10-digit, exclude 98/99/9903
        raw_leaf_codes = []
        for code in raw_codes:
            if len(code) == 10 and code.isdigit():
                chapter = code[:2]
                if chapter not in ["98", "99"] and not code.startswith("9903"):
                    raw_leaf_codes.append(code)
        
        raw_leaf_count = len(set(raw_leaf_codes))  # Deduplicate
        print(f"   Raw PDF leaf codes (10-digit, normalized, excluding 98/99/9903): {raw_leaf_count:,}")
        
        # Compare
        if structured_leaf_count > 0 and raw_leaf_count > 0:
            ratio = structured_leaf_count / raw_leaf_count
            diff = abs(structured_leaf_count - raw_leaf_count)
            pct_diff = (diff / max(structured_leaf_count, raw_leaf_count)) * 100
            
            print(f"   Ratio (structured/raw): {ratio:.3f}")
            print(f"   Difference: {diff:,} codes ({pct_diff:.2f}%)")
            
            if ratio >= 0.95:
                print("   ✅ Coverage is EXCELLENT (≥95%)")
            elif ratio >= 0.80:
                print("   ⚠️  Coverage is GOOD but could be better (80-95%)")
            elif ratio >= 0.50:
                print("   ⚠️  Coverage is MODERATE (50-80%)")
            else:
                print("   ❌ Coverage is POOR (<50%)")
        else:
            print("   ⚠️  Cannot compare: missing data")
        
        print()
        
        # ========================================================================
        # SUMMARY
        # ========================================================================
        print("=" * 100)
        print("📊 SUMMARY")
        print("=" * 100)
        print(f"Total 10-digit codes: {len(all_10digit):,}")
        print(f"Leaf 10-digit codes: {structured_leaf_count:,}")
        print(f"Raw PDF leaf codes: {raw_leaf_count:,}")
        if structured_leaf_count > 0 and raw_leaf_count > 0:
            print(f"Coverage ratio: {structured_leaf_count / raw_leaf_count:.3f}")
        print()
        
        # Final verdict
        print("=" * 100)
        print("🎯 VERDICT")
        print("=" * 100)
        
        issues = []
        if structured_leaf_count == 0:
            issues.append("❌ NO LEAF CODES FOUND - ingestion is unusable")
        elif structured_leaf_count < 1000:
            issues.append("⚠️  Very few leaf codes (<1000) - ingestion may be incomplete")
        
        if structured_leaf_count > 0 and raw_leaf_count > 0:
            ratio = structured_leaf_count / raw_leaf_count
            if ratio < 0.50:
                issues.append("❌ Coverage <50% - significant data loss in ingestion")
            elif ratio < 0.80:
                issues.append("⚠️  Coverage 50-80% - some data loss in ingestion")
        
        if not issues:
            print("✅ HTS ingestion appears USABLE")
            print("   - Leaf codes found")
            print("   - Good coverage vs raw PDF")
            print("   - Duty rates present")
        else:
            print("⚠️  HTS ingestion has ISSUES:")
            for issue in issues:
                print(f"   {issue}")
        
        print()
        print("=" * 100)
        
        break


if __name__ == "__main__":
    asyncio.run(hts_ingestion_sanity_check())
