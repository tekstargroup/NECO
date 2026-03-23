#!/usr/bin/env python3
"""
HTS Coverage and Duty Rate Validation Script

Validates HTS ingestion accuracy by:
- Counting total codes and duty rate coverage
- Analyzing parsing patterns
- Identifying NULL cases for review
"""

import asyncio
import sys
from pathlib import Path
from collections import Counter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from sqlalchemy import text


async def validate_hts_coverage():
    """Main validation function"""
    async for db in get_db():
        print("=" * 80)
        print("📊 HTS COVERAGE & DUTY RATE VALIDATION REPORT")
        print("=" * 80)
        print()
        
        # 1. Total HTS codes
        result = await db.execute(text("SELECT COUNT(*) FROM hts_versions"))
        total_codes = result.scalar()
        print(f"1️⃣  TOTAL HTS CODES: {total_codes:,}")
        print()
        
        # 2. Duty rate coverage
        result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_general IS NOT NULL"))
        with_general = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_special IS NOT NULL"))
        with_special = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_column2 IS NOT NULL"))
        with_column2 = result.scalar()
        
        print("2️⃣  DUTY RATE COVERAGE:")
        print(f"   General Rate (Column 1, MFN): {with_general:,} ({with_general/total_codes*100:.1f}%)")
        print(f"   Special Rate (Column 1, FTA): {with_special:,} ({with_special/total_codes*100:.1f}%)")
        print(f"   Column 2 Rate (non-MFN): {with_column2:,} ({with_column2/total_codes*100:.1f}%)")
        print()
        
        # 3. Most common parsing patterns for general rate
        result = await db.execute(text("SELECT duty_rate_general FROM hts_versions WHERE duty_rate_general IS NOT NULL LIMIT 10000"))
        rates = [row[0] for row in result.all()]
        
        # Analyze patterns
        patterns = Counter()
        for rate in rates:
            if rate:
                rate_str = str(rate).strip()
                # Categorize patterns
                if rate_str.lower() == "free":
                    patterns["Free"] += 1
                elif "%" in rate_str:
                    # Extract percentage value
                    try:
                        pct = float(rate_str.replace("%", "").strip())
                        if pct == 0:
                            patterns["0%"] += 1
                        elif pct < 5:
                            patterns["<5%"] += 1
                        elif pct < 10:
                            patterns["5-10%"] += 1
                        elif pct < 20:
                            patterns["10-20%"] += 1
                        elif pct < 50:
                            patterns["20-50%"] += 1
                        else:
                            patterns[">50%"] += 1
                    except ValueError:
                        patterns["Invalid % format"] += 1
                elif "¢" in rate_str or "cents" in rate_str.lower():
                    patterns["Specific duty (cents)"] += 1
                elif "$" in rate_str:
                    patterns["Specific duty ($)"] += 1
                elif "+" in rate_str:
                    patterns["Compound rate"] += 1
                elif "see" in rate_str.lower():
                    patterns["See reference"] += 1
                else:
                    patterns["Other format"] += 1
        
        print("3️⃣  MOST COMMON GENERAL RATE PATTERNS (Top 20):")
        for pattern, count in patterns.most_common(20):
            print(f"   {pattern:30} {count:6,} ({count/len(rates)*100:.1f}%)")
        print()
        
        # 4. Random rows where general_rate IS NULL
        result = await db.execute(text("""
            SELECT hts_code, hts_chapter, hts_heading_6, duty_rate_special, duty_rate_column2, 
                   source_page, parse_confidence, tariff_text_short
            FROM hts_versions
            WHERE duty_rate_general IS NULL
            ORDER BY RANDOM()
            LIMIT 20
        """))
        null_examples = result.all()
        
        print("4️⃣  RANDOM ROWS WHERE GENERAL_RATE IS NULL (20 examples):")
        print()
        for row in null_examples:
            print(f"   Code: {row[0]}")
            print(f"   Chapter: {row[1]}, Heading: {row[2]}")
            print(f"   Special Rate: {row[3] or 'NULL'}")
            print(f"   Column 2 Rate: {row[4] or 'NULL'}")
            print(f"   Source Page: {row[5] or 'N/A'}")
            print(f"   Confidence: {row[6].value if row[6] else 'N/A'}")
            print(f"   Description: {(row[7][:100] if row[7] else 'N/A')}...")
            print()
        
        # 5. Summary statistics
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NULL
              AND duty_rate_special IS NULL
              AND duty_rate_column2 IS NULL
        """))
        all_null = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND duty_rate_special IS NOT NULL
              AND duty_rate_column2 IS NOT NULL
        """))
        all_populated = result.scalar()
        
        print("5️⃣  SUMMARY STATISTICS:")
        print(f"   Codes with ALL 3 rates: {all_populated:,} ({all_populated/total_codes*100:.1f}%)")
        print(f"   Codes with NO rates: {all_null:,} ({all_null/total_codes*100:.1f}%)")
        print(f"   Codes with at least one rate: {total_codes - all_null:,} ({(total_codes - all_null)/total_codes*100:.1f}%)")
        print()
        
        print("=" * 80)
        print("✅ VALIDATION COMPLETE")
        print("=" * 80)
        print()
        print("📝 REVIEW NOTES:")
        print("   - Check NULL examples above to determine if they are:")
        print("     • Real edge cases (notes, annexes, special chapters)")
        print("     • Parser bugs (should have extracted rate)")
        print("   - Review parsing patterns to ensure they match expected formats")
        print("   - Coverage should be >95% for general rates in tariff chapters (01-97)")
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(validate_hts_coverage())

