#!/usr/bin/env python3
"""
Functional Test: 20 Random HTS Codes

Picks 20 random HTS codes across chapters and displays:
- Code, description, all 3 duty rates, source page, confidence
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text, select
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


async def functional_test():
    """Functional test with 20 random HTS codes"""
    async for db in get_db():
        print("=" * 100)
        print("🧪 FUNCTIONAL TEST: 20 RANDOM HTS CODES")
        print("=" * 100)
        print()
        
        # Get 20 random codes across different chapters using raw SQL
        result = await db.execute(text("""
            SELECT 
                hts_code,
                hts_chapter,
                tariff_text_short,
                tariff_text,
                duty_rate_general,
                duty_rate_special,
                duty_rate_column2,
                special_countries,
                source_page,
                duty_rate_confidence
            FROM hts_versions
            WHERE hts_chapter NOT IN ('98', '99')
              AND duty_rate_general IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 20
        """))
        rows = result.all()
        
        # Build table data
        table_data = []
        for row in rows:
            hts_code = row[0]
            hts_chapter = row[1]
            tariff_text_short = row[2]
            tariff_text = row[3]
            duty_rate_general = row[4]
            duty_rate_special = row[5]
            duty_rate_column2 = row[6]
            special_countries = row[7]  # This is an array
            source_page = row[8]
            duty_rate_confidence = row[9]
            
            # Format special countries
            if special_countries:
                countries_list = special_countries if isinstance(special_countries, list) else []
                if countries_list:
                    countries = ", ".join(countries_list[:3])
                    if len(countries_list) > 3:
                        countries += f" (+{len(countries_list) - 3})"
                else:
                    countries = "None"
            else:
                countries = "None"
            
            # Format description (truncate)
            desc = tariff_text_short or tariff_text or "N/A"
            if desc and len(desc) > 60:
                desc = desc[:57] + "..."
            
            # Format confidence (treat as string, not enum)
            conf = str(duty_rate_confidence) if duty_rate_confidence else "N/A"
            # Remove enum prefix if present (e.g., "HTSDutyRateConfidence.HIGH" -> "HIGH")
            if "." in conf:
                conf = conf.split(".")[-1]
            
            table_data.append([
                hts_code,
                hts_chapter,
                desc,
                duty_rate_general or "NULL",
                duty_rate_special or "NULL",
                duty_rate_column2 or "NULL",
                countries,
                source_page or "N/A",
                conf
            ])
        
        # Print table
        headers = [
            "HTS Code",
            "Ch",
            "Description",
            "General",
            "Special",
            "Column 2",
            "Special Countries",
            "Page",
            "Confidence"
        ]
        
        print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[10, 3, 30, 10, 10, 10, 20, 5, 10]))
        print()
        
        # Summary statistics
        print("=" * 100)
        print("📊 SUMMARY")
        print("=" * 100)
        
        all_three = sum(1 for row in rows if row[4] and row[5] and row[6])
        high_conf = sum(1 for row in rows if row[9] and str(row[9]).upper().endswith("HIGH"))
        medium_conf = sum(1 for row in rows if row[9] and str(row[9]).upper().endswith("MEDIUM"))
        low_conf = sum(1 for row in rows if row[9] and str(row[9]).upper().endswith("LOW"))
        
        print(f"Codes with all 3 rates: {all_three}/20 ({all_three/20*100:.0f}%)")
        print(f"High confidence: {high_conf}/20 ({high_conf/20*100:.0f}%)")
        print(f"Medium confidence: {medium_conf}/20 ({medium_conf/20*100:.0f}%)")
        print(f"Low confidence: {low_conf}/20 ({low_conf/20*100:.0f}%)")
        print()
        
        print("=" * 100)
        print("✅ FUNCTIONAL TEST COMPLETE")
        print("=" * 100)
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(functional_test())

