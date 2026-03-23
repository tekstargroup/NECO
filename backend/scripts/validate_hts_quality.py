#!/usr/bin/env python3
"""
HTS Quality Validation Script

Comprehensive validation of HTS data quality:
- Report A: Global (all HTS data)
- Report B: Latest HTSUS ingest only (2025HTS.pdf)
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


async def validate_hts_quality_global(db):
    """Report A: Global validation (all HTS data)"""
    print("=" * 100)
    print("📊 REPORT A: GLOBAL HTS QUALITY VALIDATION")
    print("=" * 100)
    print()
    
    # 1. Total rows
    result = await db.execute(text("SELECT COUNT(*) FROM hts_versions"))
    total_rows = result.scalar()
    print(f"1️⃣  TOTAL HTS_VERSIONS ROWS: {total_rows:,}")
    print()
    
    # 2. Distinct HTS codes
    result = await db.execute(text("SELECT COUNT(DISTINCT hts_code) FROM hts_versions"))
    distinct_codes = result.scalar()
    print(f"2️⃣  DISTINCT HTS CODES: {distinct_codes:,}")
    print()
    
    # 3. Duty rate coverage
    result = await db.execute(text("""
        SELECT COUNT(*) FROM hts_versions WHERE duty_rate_general IS NOT NULL
    """))
    with_general = result.scalar()
    pct_general = (with_general / total_rows * 100) if total_rows > 0 else 0
    
    result = await db.execute(text("""
        SELECT COUNT(*) FROM hts_versions WHERE duty_rate_special IS NOT NULL
    """))
    with_special = result.scalar()
    pct_special = (with_special / total_rows * 100) if total_rows > 0 else 0
    
    result = await db.execute(text("""
        SELECT COUNT(*) FROM hts_versions WHERE duty_rate_column2 IS NOT NULL
    """))
    with_column2 = result.scalar()
    pct_column2 = (with_column2 / total_rows * 100) if total_rows > 0 else 0
    
    print("3️⃣  DUTY RATE COVERAGE:")
    print(f"   General Rate (Column 1, MFN):")
    print(f"      Count: {with_general:,}")
    print(f"      Percentage: {pct_general:.2f}%")
    print()
    print(f"   Special Rate (Column 1, FTA):")
    print(f"      Count: {with_special:,}")
    print(f"      Percentage: {pct_special:.2f}%")
    print()
    print(f"   Column 2 Rate (non-MFN):")
    print(f"      Count: {with_column2:,}")
    print(f"      Percentage: {pct_column2:.2f}%")
    print()
    
    # 4. Parse confidence distribution
    result = await db.execute(text("""
        SELECT parse_confidence, COUNT(*) as count
        FROM hts_versions
        GROUP BY parse_confidence
        ORDER BY parse_confidence
    """))
    confidence_data = result.all()
    
    print("4️⃣  PARSE CONFIDENCE DISTRIBUTION:")
    for conf, count in confidence_data:
        pct = (count / total_rows * 100) if total_rows > 0 else 0
        conf_str = str(conf) if conf is not None else "NULL"
        print(f"   {conf_str:10} {count:8,} ({pct:6.2f}%)")
    print()
    
    # 5. Random sample of 20 codes
    result = await db.execute(text("""
        SELECT 
            hts_code,
            tariff_text_short,
            duty_rate_general,
            duty_rate_special,
            duty_rate_column2,
            source_page,
            parse_confidence
        FROM hts_versions
        WHERE hts_chapter NOT IN ('98', '99')
        ORDER BY RANDOM()
        LIMIT 20
    """))
    samples = result.all()
    
    print("5️⃣  RANDOM SAMPLE (20 codes):")
    print()
    
    # Build table data
    table_data = []
    for row in samples:
        hts_code = row[0]
        tariff_text = row[1] or "N/A"
        if len(tariff_text) > 60:
            tariff_text = tariff_text[:57] + "..."
        
        general = row[2] or "NULL"
        special = row[3] or "NULL"
        column2 = row[4] or "NULL"
        page = row[5] or "N/A"
        confidence = str(row[6]) if row[6] is not None else "N/A"
        
        table_data.append([
            hts_code,
            tariff_text,
            general,
            special,
            column2,
            page,
            confidence
        ])
    
    headers = [
        "HTS Code",
        "Description",
        "General Rate",
        "Special Rate",
        "Column 2 Rate",
        "Source Page",
        "Confidence"
    ]
    
    print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[12, 40, 12, 12, 12, 10, 10]))
    print()
    
    # Summary
    print("=" * 100)
    print("📊 SUMMARY")
    print("=" * 100)
    print(f"Total Records: {total_rows:,}")
    print(f"Unique Codes: {distinct_codes:,}")
    print(f"General Rate Coverage: {pct_general:.1f}%")
    print(f"Special Rate Coverage: {pct_special:.1f}%")
    print(f"Column 2 Rate Coverage: {pct_column2:.1f}%")
    print()
    
    # Quality assessment
    print("✅ QUALITY ASSESSMENT:")
    if pct_general >= 95:
        print("   ✓ General rate coverage is excellent (≥95%)")
    elif pct_general >= 80:
        print("   ⚠ General rate coverage is good but could be improved (80-95%)")
    else:
        print("   ✗ General rate coverage needs attention (<80%)")
    
    if pct_special >= 10:
        print("   ✓ Special rate coverage is adequate (≥10%)")
    else:
        print("   ⚠ Special rate coverage may be low (<10%)")
    
    if pct_column2 >= 30:
        print("   ✓ Column 2 rate coverage is adequate (≥30%)")
    else:
        print("   ⚠ Column 2 rate coverage may be low (<30%)")
    
    print()
    print("=" * 100)
    print("✅ REPORT A COMPLETE")
    print("=" * 100)
    print()
    print()


async def validate_hts_quality_latest_ingest(db):
    """Report B: Latest HTSUS ingest only (2025HTS.pdf)"""
    print("=" * 100)
    print("📊 REPORT B: LATEST HTSUS INGEST (2025HTS.pdf)")
    print("=" * 100)
    print()
    
    # Build WHERE clause - filter for latest 2025HTS.pdf ingest
    # Handle cases where source columns might not exist or be NULL
    where_clause = """
        hts_chapter NOT IN ('98', '99')
        AND hts_code NOT LIKE '9903%'
        AND (
            source_type = 'pdf' OR source_type IS NULL
        )
        AND (
            (source_url IS NOT NULL AND source_url LIKE '%2025HTS.pdf%')
            OR (source_file IS NOT NULL AND source_file LIKE '%2025HTS.pdf%')
            OR (source_url IS NULL AND source_file IS NULL)
        )
    """
    
    # 1. Distinct HTS codes
    result = await db.execute(text(f"""
        SELECT COUNT(DISTINCT hts_code)
        FROM hts_versions
        WHERE {where_clause}
    """))
    distinct_codes = result.scalar()
    print(f"1️⃣  DISTINCT HTS CODES: {distinct_codes:,}")
    print()
    
    # 2. Total rows (for percentage calculations)
    result = await db.execute(text(f"""
        SELECT COUNT(*)
        FROM hts_versions
        WHERE {where_clause}
    """))
    total_rows = result.scalar()
    print(f"2️⃣  TOTAL ROWS: {total_rows:,}")
    print()
    
    # 3. Duty rate coverage percentages
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM hts_versions
        WHERE {where_clause} AND duty_rate_general IS NOT NULL
    """))
    with_general = result.scalar()
    pct_general = (with_general / total_rows * 100) if total_rows > 0 else 0
    
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM hts_versions
        WHERE {where_clause} AND duty_rate_column2 IS NOT NULL
    """))
    with_column2 = result.scalar()
    pct_column2 = (with_column2 / total_rows * 100) if total_rows > 0 else 0
    
    # Special countries or special rate
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM hts_versions
        WHERE {where_clause}
        AND (
            (special_countries IS NOT NULL AND array_length(special_countries, 1) > 0)
            OR duty_rate_special IS NOT NULL
        )
    """))
    with_special = result.scalar()
    pct_special = (with_special / total_rows * 100) if total_rows > 0 else 0
    
    print("3️⃣  DUTY RATE COVERAGE:")
    print(f"   General Rate (Column 1, MFN):")
    print(f"      Count: {with_general:,}")
    print(f"      Percentage: {pct_general:.2f}%")
    print()
    print(f"   Column 2 Rate (non-MFN):")
    print(f"      Count: {with_column2:,}")
    print(f"      Percentage: {pct_column2:.2f}%")
    print()
    print(f"   Special Rate or Countries:")
    print(f"      Count: {with_special:,}")
    print(f"      Percentage: {pct_special:.2f}%")
    print()
    
    # 4. Random sample of 20 codes
    result = await db.execute(text(f"""
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
            parse_confidence
        FROM hts_versions
        WHERE {where_clause}
        ORDER BY RANDOM()
        LIMIT 20
    """))
    samples = result.all()
    
    print("4️⃣  RANDOM SAMPLE (20 codes):")
    print()
    
    # Build table data
    table_data = []
    for row in samples:
        hts_code = row[0]
        hts_chapter = row[1]
        tariff_text_short = row[2]
        tariff_text = row[3]
        duty_rate_general = row[4]
        duty_rate_special = row[5]
        duty_rate_column2 = row[6]
        special_countries = row[7]
        source_page = row[8]
        parse_confidence = row[9]
        
        # Format description
        desc = tariff_text_short or tariff_text or "N/A"
        if desc and len(desc) > 50:
            desc = desc[:47] + "..."
        
        # Format special countries
        if special_countries and isinstance(special_countries, list) and len(special_countries) > 0:
            countries = ", ".join(special_countries[:3])
            if len(special_countries) > 3:
                countries += f" (+{len(special_countries) - 3})"
        else:
            countries = "None"
        
        # Format confidence
        confidence = str(parse_confidence) if parse_confidence is not None else "N/A"
        if "." in confidence:
            confidence = confidence.split(".")[-1]
        
        table_data.append([
            hts_code,
            hts_chapter,
            desc,
            duty_rate_general or "NULL",
            duty_rate_special or "NULL",
            duty_rate_column2 or "NULL",
            countries,
            source_page or "N/A",
            confidence
        ])
    
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
    
    print(tabulate(table_data, headers=headers, tablefmt="grid", maxcolwidths=[12, 3, 30, 12, 12, 12, 20, 8, 10]))
    print()
    
    # Summary
    print("=" * 100)
    print("📊 SUMMARY (Latest HTSUS Ingest)")
    print("=" * 100)
    print(f"Distinct Codes: {distinct_codes:,}")
    print(f"Total Rows: {total_rows:,}")
    print(f"General Rate Coverage: {pct_general:.2f}%")
    print(f"Column 2 Rate Coverage: {pct_column2:.2f}%")
    print(f"Special Rate/Countries Coverage: {pct_special:.2f}%")
    print()
    
    print("=" * 100)
    print("✅ REPORT B COMPLETE")
    print("=" * 100)
    print()


async def validate_hts_quality():
    """Main validation function - runs both reports"""
    async for db in get_db():
        # Report A: Global
        await validate_hts_quality_global(db)
        
        # Report B: Latest ingest only
        await validate_hts_quality_latest_ingest(db)
        
        print("=" * 100)
        print("✅ ALL VALIDATIONS COMPLETE")
        print("=" * 100)
        
        break


if __name__ == "__main__":
    asyncio.run(validate_hts_quality())

