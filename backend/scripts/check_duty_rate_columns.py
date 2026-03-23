#!/usr/bin/env python3
"""
Check Duty Rate Columns Per Row

Verifies that each HTS code has all 3 duty rate columns populated.
Special is considered 'present' if special_countries is non-empty OR duty_rate_special is non-null.
Shows examples where rates are missing.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


async def check_duty_rate_columns():
    """Check duty rate column coverage"""
    async for db in get_db():
        print("=" * 80)
        print("🔍 DUTY RATE COLUMN COVERAGE CHECK")
        print("=" * 80)
        print()
        
        # Total codes
        result = await db.execute(text("SELECT COUNT(*) FROM hts_versions"))
        total = result.scalar()
        print(f"Total HTS records: {total:,}")
        print()
        
        # Count by column
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions WHERE duty_rate_general IS NOT NULL
        """))
        with_general = result.scalar()
        
        # Special: present if special_countries is non-empty OR duty_rate_special is non-null
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE (
                (special_countries IS NOT NULL AND array_length(special_countries, 1) > 0)
                OR duty_rate_special IS NOT NULL
            )
        """))
        with_special = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions WHERE duty_rate_column2 IS NOT NULL
        """))
        with_column2 = result.scalar()
        
        print("1️⃣  COLUMN POPULATION:")
        print(f"   General Rate: {with_general:,} ({with_general/total*100:.1f}%)")
        print(f"   Special Rate/Countries: {with_special:,} ({with_special/total*100:.1f}%)")
        print(f"      (Special = duty_rate_special OR special_countries non-empty)")
        print(f"   Column 2 Rate: {with_column2:,} ({with_column2/total*100:.1f}%)")
        print()
        
        # Count combinations
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND (
                  (special_countries IS NOT NULL AND array_length(special_countries, 1) > 0)
                  OR duty_rate_special IS NOT NULL
              )
              AND duty_rate_column2 IS NOT NULL
        """))
        all_three = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND (
                  (special_countries IS NULL OR array_length(special_countries, 1) = 0)
                  AND duty_rate_special IS NULL
              )
              AND duty_rate_column2 IS NULL
        """))
        only_general = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND (
                  (special_countries IS NOT NULL AND array_length(special_countries, 1) > 0)
                  OR duty_rate_special IS NOT NULL
              )
              AND duty_rate_column2 IS NULL
        """))
        general_and_special = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND (
                  (special_countries IS NULL OR array_length(special_countries, 1) = 0)
                  AND duty_rate_special IS NULL
              )
              AND duty_rate_column2 IS NOT NULL
        """))
        general_and_column2 = result.scalar()
        
        result = await db.execute(text("""
            SELECT COUNT(*) FROM hts_versions
            WHERE duty_rate_general IS NULL
               OR (
                  (special_countries IS NULL OR array_length(special_countries, 1) = 0)
                  AND duty_rate_special IS NULL
              )
               OR duty_rate_column2 IS NULL
        """))
        at_least_one_null = result.scalar()
        
        print("2️⃣  COMBINATION ANALYSIS:")
        print(f"   All 3 rates populated: {all_three:,} ({all_three/total*100:.1f}%)")
        print(f"   Only General rate: {only_general:,} ({only_general/total*100:.1f}%)")
        print(f"   General + Special (no Column 2): {general_and_special:,} ({general_and_special/total*100:.1f}%)")
        print(f"   General + Column 2 (no Special): {general_and_column2:,} ({general_and_column2/total*100:.1f}%)")
        print(f"   At least one NULL: {at_least_one_null:,} ({at_least_one_null/total*100:.1f}%)")
        print()
        
        # Examples where general exists but special is NULL
        result = await db.execute(text("""
            SELECT 
                hts_code,
                duty_rate_general,
                duty_rate_special,
                duty_rate_column2,
                special_countries,
                source_page,
                tariff_text_short
            FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND (
                  (special_countries IS NULL OR array_length(special_countries, 1) = 0)
                  AND duty_rate_special IS NULL
              )
            LIMIT 20
        """))
        examples = result.all()
        
        print("3️⃣  EXAMPLES: General Rate exists but Special Rate/Countries is NULL (20 examples):")
        print()
        for row in examples:
            hts_code = row[0]
            duty_rate_general = row[1]
            duty_rate_special = row[2]
            duty_rate_column2 = row[3]
            special_countries = row[4]
            source_page = row[5]
            tariff_text_short = row[6]
            
            countries = ", ".join(special_countries[:5]) if special_countries and len(special_countries) > 0 else "None"
            if special_countries and len(special_countries) > 5:
                countries += f" (+{len(special_countries) - 5} more)"
            
            print(f"   Code: {hts_code}")
            print(f"   General Rate: {duty_rate_general}")
            print(f"   Special Rate: {duty_rate_special or 'NULL'}")
            print(f"   Column 2 Rate: {duty_rate_column2 or 'NULL'}")
            print(f"   Special Countries: {countries}")
            print(f"   Source Page: {source_page or 'N/A'}")
            print(f"   Description: {(tariff_text_short[:80] + '...') if tariff_text_short and len(tariff_text_short) > 80 else (tariff_text_short or 'N/A')}")
            print()
        
        # Examples where general exists but column2 is NULL
        result = await db.execute(text("""
            SELECT 
                hts_code,
                duty_rate_general,
                duty_rate_special,
                source_page
            FROM hts_versions
            WHERE duty_rate_general IS NOT NULL
              AND duty_rate_column2 IS NULL
            LIMIT 10
        """))
        examples_col2 = result.all()
        
        print("4️⃣  EXAMPLES: General Rate exists but Column 2 Rate is NULL (10 examples):")
        print()
        for row in examples_col2:
            hts_code = row[0]
            duty_rate_general = row[1]
            duty_rate_special = row[2]
            source_page = row[3]
            
            print(f"   Code: {hts_code}")
            print(f"   General Rate: {duty_rate_general}")
            print(f"   Special Rate: {duty_rate_special or 'NULL'}")
            print(f"   Column 2 Rate: NULL")
            print(f"   Source Page: {source_page or 'N/A'}")
            print()
        
        print("=" * 80)
        print("✅ CHECK COMPLETE")
        print("=" * 80)
        print()
        print("📝 REVIEW NOTES:")
        print("   - Special is considered 'present' if special_countries is non-empty OR duty_rate_special is non-null")
        print("   - Codes with only General rate may be legitimate (no Special/Column 2 rates)")
        print("   - Codes with General + Special but no Column 2 may indicate parser missed Column 2")
        print("   - Review examples above to determine if NULLs are expected or parser bugs")
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(check_duty_rate_columns())

