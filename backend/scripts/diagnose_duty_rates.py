#!/usr/bin/env python3
"""
Duty Rate Diagnostic Script

Phase 1.1 of Duty Rate Investigation Plan
Analyzes patterns in missing vs present duty rates to identify root causes.
"""

import asyncio
import sys
import re
from pathlib import Path
from collections import defaultdict
from sqlalchemy import text
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


async def diagnose_duty_rates():
    """Run comprehensive duty rate diagnostic"""
    async for db in get_db():
        print("=" * 100)
        print("🔍 DUTY RATE DIAGNOSTIC ANALYSIS")
        print("=" * 100)
        print()
        
        # ========================================================================
        # 1. PATTERN ANALYSIS: Codes WITH vs WITHOUT duty rates
        # ========================================================================
        print("1️⃣  PATTERN ANALYSIS: Codes WITH vs WITHOUT Duty Rates")
        print("-" * 100)
        
        # Sample codes WITH General duty rate
        result = await db.execute(text("""
            SELECT 
                hts_code,
                hts_chapter,
                tariff_text_short,
                tariff_text,
                duty_rate_general,
                duty_rate_special,
                duty_rate_column2,
                source_page,
                parse_confidence
            FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
            AND hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
            ORDER BY RANDOM()
            LIMIT 100
        """))
        with_duty = result.all()
        
        # Sample codes WITHOUT any duty rate
        result = await db.execute(text("""
            SELECT 
                hts_code,
                hts_chapter,
                tariff_text_short,
                tariff_text,
                duty_rate_general,
                duty_rate_special,
                duty_rate_column2,
                source_page,
                parse_confidence
            FROM hts_versions
            WHERE duty_rate_general IS NULL
            AND duty_rate_special IS NULL
            AND duty_rate_column2 IS NULL
            AND hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
            ORDER BY RANDOM()
            LIMIT 100
        """))
        without_duty = result.all()
        
        print(f"   ✅ Sampled {len(with_duty)} codes WITH General duty rate")
        print(f"   ❌ Sampled {len(without_duty)} codes WITHOUT any duty rate")
        print()
        
        # Analyze text patterns
        with_patterns = defaultdict(int)
        without_patterns = defaultdict(int)
        
        # Look for common patterns in tariff_text
        for row in with_duty:
            text_combined = (row[2] or "") + " " + (row[3] or "")
            # Check for percentage signs (indicates duty rate in text)
            if "%" in text_combined:
                with_patterns["has_percent_sign"] += 1
            # Check for "Free" text
            if "free" in text_combined.lower():
                with_patterns["has_free_text"] += 1
            # Check for numeric patterns that might be duty rates
            if re.search(r'\d+\.?\d*\s*%', text_combined):
                with_patterns["has_percent_pattern"] += 1
        
        for row in without_duty:
            text_combined = (row[2] or "") + " " + (row[3] or "")
            if "%" in text_combined:
                without_patterns["has_percent_sign"] += 1
            if "free" in text_combined.lower():
                without_patterns["has_free_text"] += 1
            if re.search(r'\d+\.?\d*\s*%', text_combined):
                without_patterns["has_percent_pattern"] += 1
        
        print("   📊 Text Pattern Analysis:")
        print(f"      Codes WITH duty rate:")
        print(f"         - Has '%' sign: {with_patterns['has_percent_sign']}/{len(with_duty)} ({with_patterns['has_percent_sign']/len(with_duty)*100 if with_duty else 0:.1f}%)")
        print(f"         - Has 'Free' text: {with_patterns['has_free_text']}/{len(with_duty)} ({with_patterns['has_free_text']/len(with_duty)*100 if with_duty else 0:.1f}%)")
        print(f"         - Has % pattern: {with_patterns['has_percent_pattern']}/{len(with_duty)} ({with_patterns['has_percent_pattern']/len(with_duty)*100 if with_duty else 0:.1f}%)")
        print(f"      Codes WITHOUT duty rate:")
        print(f"         - Has '%' sign: {without_patterns['has_percent_sign']}/{len(without_duty)} ({without_patterns['has_percent_sign']/len(without_duty)*100 if without_duty else 0:.1f}%)")
        print(f"         - Has 'Free' text: {without_patterns['has_free_text']}/{len(without_duty)} ({without_patterns['has_free_text']/len(without_duty)*100 if without_duty else 0:.1f}%)")
        print(f"         - Has % pattern: {without_patterns['has_percent_pattern']}/{len(without_duty)} ({without_patterns['has_percent_pattern']/len(without_duty)*100 if without_duty else 0:.1f}%)")
        print()
        
        # ========================================================================
        # 2. SOURCE PAGE ANALYSIS
        # ========================================================================
        print("2️⃣  SOURCE PAGE ANALYSIS: Duty Rate Coverage by Page")
        print("-" * 100)
        
        result = await db.execute(text("""
            SELECT 
                source_page,
                COUNT(*) as total_codes,
                COUNT(CASE WHEN duty_rate_general IS NOT NULL THEN 1 END) as with_general,
                COUNT(CASE WHEN duty_rate_special IS NOT NULL THEN 1 END) as with_special,
                COUNT(CASE WHEN duty_rate_column2 IS NOT NULL THEN 1 END) as with_column2,
                COUNT(CASE WHEN duty_rate_general IS NOT NULL 
                              OR duty_rate_special IS NOT NULL 
                              OR duty_rate_column2 IS NOT NULL THEN 1 END) as with_any
            FROM hts_versions
            WHERE hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
            AND source_page IS NOT NULL
            GROUP BY source_page
            ORDER BY 
                CASE WHEN COUNT(CASE WHEN duty_rate_general IS NOT NULL THEN 1 END) = 0 THEN 1 ELSE 0 END,
                (COUNT(CASE WHEN duty_rate_general IS NOT NULL THEN 1 END)::float / COUNT(*)) ASC
            LIMIT 20
        """))
        page_analysis = result.all()
        
        if page_analysis:
            table_data = []
            for row in page_analysis:
                page, total, with_gen, with_spec, with_col2, with_any = row
                gen_pct = (with_gen / total * 100) if total > 0 else 0
                any_pct = (with_any / total * 100) if total > 0 else 0
                
                status = "❌ FAIL" if gen_pct == 0 else ("⚠️  POOR" if gen_pct < 50 else "✅ OK")
                
                table_data.append([
                    page,
                    total,
                    f"{with_gen} ({gen_pct:.1f}%)",
                    f"{with_any} ({any_pct:.1f}%)",
                    status
                ])
            
            headers = ["Page", "Total Codes", "With General", "With ANY", "Status"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print()
            print("   📝 Shows pages with WORST duty rate coverage (first 20)")
        print()
        
        # ========================================================================
        # 3. CHAPTER ANALYSIS
        # ========================================================================
        print("3️⃣  CHAPTER ANALYSIS: Duty Rate Coverage by Chapter")
        print("-" * 100)
        
        result = await db.execute(text("""
            SELECT 
                hts_chapter,
                COUNT(*) as total_codes,
                COUNT(CASE WHEN duty_rate_general IS NOT NULL THEN 1 END) as with_general,
                COUNT(CASE WHEN duty_rate_special IS NOT NULL THEN 1 END) as with_special,
                COUNT(CASE WHEN duty_rate_column2 IS NOT NULL THEN 1 END) as with_column2,
                COUNT(CASE WHEN duty_rate_general IS NOT NULL 
                              OR duty_rate_special IS NOT NULL 
                              OR duty_rate_column2 IS NOT NULL THEN 1 END) as with_any
            FROM hts_versions
            WHERE hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
            GROUP BY hts_chapter
            ORDER BY 
                (COUNT(CASE WHEN duty_rate_general IS NOT NULL THEN 1 END)::float / COUNT(*)) ASC
            LIMIT 15
        """))
        chapter_analysis = result.all()
        
        if chapter_analysis:
            table_data = []
            for row in chapter_analysis:
                chapter, total, with_gen, with_spec, with_col2, with_any = row
                gen_pct = (with_gen / total * 100) if total > 0 else 0
                any_pct = (with_any / total * 100) if total > 0 else 0
                
                status = "❌ FAIL" if gen_pct == 0 else ("⚠️  POOR" if gen_pct < 50 else "✅ OK")
                
                table_data.append([
                    chapter,
                    total,
                    f"{with_gen} ({gen_pct:.1f}%)",
                    f"{with_any} ({any_pct:.1f}%)",
                    status
                ])
            
            headers = ["Chapter", "Total Codes", "With General", "With ANY", "Status"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print()
            print("   📝 Shows chapters with WORST duty rate coverage (first 15)")
        print()
        
        # ========================================================================
        # 4. RAW PDF COMPARISON (Sample)
        # ========================================================================
        print("4️⃣  RAW PDF COMPARISON: Check if duty rates exist in raw PDF")
        print("-" * 100)
        
        # Get 20 codes missing duty rates
        result = await db.execute(text("""
            SELECT 
                v.hts_code,
                v.source_page,
                v.tariff_text_short,
                v.duty_rate_general,
                v.duty_rate_special,
                v.duty_rate_column2
            FROM hts_versions v
            WHERE v.duty_rate_general IS NULL
            AND v.duty_rate_special IS NULL
            AND v.duty_rate_column2 IS NULL
            AND v.hts_chapter NOT IN ('98', '99')
            AND v.hts_code NOT LIKE '9903%'
            AND v.source_page IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 20
        """))
        missing_codes = result.all()
        
        print(f"   Checking {len(missing_codes)} codes missing duty rates...")
        print()
        
        found_in_raw = 0
        not_found_in_raw = 0
        examples = []
        
        for row in missing_codes[:10]:  # Check first 10
            hts_code = row[0]
            source_page = row[1]
            
            # Look up in raw PDF
            result = await db.execute(text("""
                SELECT 
                    hts_code,
                    context,
                    source_page
                FROM hts_codes_raw_pdf
                WHERE hts_code = :hts_code
                AND source_page = :source_page
                LIMIT 1
            """), {"hts_code": hts_code, "source_page": source_page})
            
            raw_row = result.fetchone()
            
            if raw_row:
                context = raw_row[1] or ""
                # Check if context has duty rate patterns
                has_duty_pattern = bool(re.search(r'\d+\.?\d*\s*%|Free|free', context))
                
                if has_duty_pattern:
                    found_in_raw += 1
                    examples.append({
                        "hts_code": hts_code,
                        "page": source_page,
                        "status": "✅ FOUND in raw",
                        "context_snippet": context[:100] + "..." if len(context) > 100 else context
                    })
                else:
                    not_found_in_raw += 1
                    examples.append({
                        "hts_code": hts_code,
                        "page": source_page,
                        "status": "❌ NOT in raw",
                        "context_snippet": context[:100] + "..." if len(context) > 100 else context
                    })
            else:
                not_found_in_raw += 1
                examples.append({
                    "hts_code": hts_code,
                    "page": source_page,
                    "status": "❌ NOT in raw PDF",
                    "context_snippet": "N/A"
                })
        
        print(f"   Results (first 10 checked):")
        print(f"      ✅ Duty rate pattern found in raw PDF: {found_in_raw}")
        print(f"      ❌ No duty rate pattern in raw PDF: {not_found_in_raw}")
        print()
        
        if examples:
            print("   Examples:")
            for ex in examples[:5]:
                print(f"      {ex['hts_code']} (Page {ex['page']}): {ex['status']}")
                print(f"         Context: {ex['context_snippet']}")
                print()
        
        # ========================================================================
        # 5. DATA QUALITY CHECKS
        # ========================================================================
        print("5️⃣  DATA QUALITY CHECKS")
        print("-" * 100)
        
        # Check for malformed duty rate strings
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IN ('NULL', 'N/A', 'null', 'n/a', '')
            OR duty_rate_special IN ('NULL', 'N/A', 'null', 'n/a', '')
            OR duty_rate_column2 IN ('NULL', 'N/A', 'null', 'n/a', '')
        """))
        malformed = result.scalar()
        print(f"   Malformed duty rate strings (NULL/N/A as text): {malformed:,}")
        
        # Check codes with Column 2 but no General
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NULL
            AND duty_rate_column2 IS NOT NULL
            AND hts_chapter NOT IN ('98', '99')
        """))
        col2_no_gen = result.scalar()
        print(f"   Codes with Column 2 but NO General: {col2_no_gen:,}")
        
        # Check codes with all 3 NULL
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NULL
            AND duty_rate_special IS NULL
            AND duty_rate_column2 IS NULL
            AND hts_chapter NOT IN ('98', '99')
            AND hts_code NOT LIKE '9903%'
        """))
        all_null = result.scalar()
        print(f"   Codes with ALL 3 duty rates NULL: {all_null:,}")
        
        print()
        
        # ========================================================================
        # SUMMARY & RECOMMENDATIONS
        # ========================================================================
        print("=" * 100)
        print("📊 SUMMARY & ROOT CAUSE HYPOTHESES")
        print("=" * 100)
        print()
        
        # Calculate percentages
        total_leaf = 23818  # From sanity check
        with_any = 15228
        coverage_pct = (with_any / total_leaf * 100) if total_leaf > 0 else 0
        
        print(f"Current Coverage: {coverage_pct:.1f}% of leaf codes have ANY duty rate")
        print()
        
        print("🔍 ROOT CAUSE HYPOTHESES:")
        print()
        
        if found_in_raw > 0:
            print(f"   ✅ HYPOTHESIS A: Parsing Logic Issue")
            print(f"      - {found_in_raw} codes have duty rates in raw PDF but not in structured data")
            print(f"      - Likely cause: Regex/parsing logic not extracting duty rates correctly")
            print(f"      - Fix: Improve duty rate extraction patterns")
            print()
        
        if not_found_in_raw > 0:
            print(f"   ⚠️  HYPOTHESIS B: Source Data Issue")
            print(f"      - {not_found_in_raw} codes don't have duty rates in raw PDF either")
            print(f"      - Likely cause: Some pages/sections don't contain duty rate data")
            print(f"      - Fix: May need alternative data source or accept missing rates")
            print()
        
        if malformed > 0:
            print(f"   ⚠️  HYPOTHESIS C: Storage Issue")
            print(f"      - {malformed} codes have malformed duty rate strings")
            print(f"      - Likely cause: Parsing succeeded but stored as text 'NULL' instead of NULL")
            print(f"      - Fix: Clean up malformed strings, improve validation")
            print()
        
        if col2_no_gen > 0:
            print(f"   ℹ️  HYPOTHESIS D: Column Detection Issue")
            print(f"      - {col2_no_gen} codes have Column 2 but no General")
            print(f"      - Likely cause: Column detection logic may be reversed or incorrect")
            print(f"      - Fix: Review column detection/parsing logic")
            print()
        
        print("=" * 100)
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 100)
        print()
        print("📝 NEXT STEPS:")
        print("   1. Review page/chapter analysis to identify systematic issues")
        print("   2. Run compare_duty_rates_raw_vs_structured.py for detailed comparison")
        print("   3. Review ingestion code to understand parsing logic")
        print("   4. Prioritize fixes based on impact (pages/chapters with most codes)")
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(diagnose_duty_rates())
