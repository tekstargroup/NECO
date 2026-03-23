#!/usr/bin/env python3
"""
Populate Duty Rate Confidence Score

Adds duty_rate_confidence enum and duty_rate_source_page to hts_versions,
then populates confidence based on duty rate column completeness.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db


async def populate_duty_rate_confidence():
    """Populate duty rate confidence scores"""
    async for db in get_db():
        print("=" * 80)
        print("📊 POPULATING DUTY RATE CONFIDENCE SCORES")
        print("=" * 80)
        print()
        
        # First, check if enum exists, create if not
        print("1️⃣  Creating duty_rate_confidence enum if needed...")
        try:
            await db.execute(text("""
                DO $$ BEGIN
                    CREATE TYPE duty_rate_confidence AS ENUM ('high', 'medium', 'low');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))
            await db.commit()
            print("   ✅ Enum created or already exists")
        except Exception as e:
            print(f"   ⚠️  Enum creation: {e}")
        
        # Add column if it doesn't exist
        print()
        print("2️⃣  Adding duty_rate_confidence column if needed...")
        try:
            await db.execute(text("""
                ALTER TABLE hts_versions
                ADD COLUMN IF NOT EXISTS duty_rate_confidence duty_rate_confidence;
            """))
            await db.commit()
            print("   ✅ Column added or already exists")
        except Exception as e:
            print(f"   ⚠️  Column addition: {e}")
        
        # Add duty_rate_source_page if it doesn't exist
        print()
        print("3️⃣  Adding duty_rate_source_page column if needed...")
        try:
            await db.execute(text("""
                ALTER TABLE hts_versions
                ADD COLUMN IF NOT EXISTS duty_rate_source_page INTEGER;
            """))
            await db.commit()
            print("   ✅ Column added or already exists")
        except Exception as e:
            print(f"   ⚠️  Column addition: {e}")
        
        # Populate confidence scores
        print()
        print("4️⃣  Populating confidence scores...")
        
        # HIGH: All 3 columns populated
        result = await db.execute(text("""
            UPDATE hts_versions
            SET duty_rate_confidence = 'high'
            WHERE duty_rate_general IS NOT NULL
              AND duty_rate_special IS NOT NULL
              AND duty_rate_column2 IS NOT NULL
        """))
        high_count = result.rowcount
        await db.commit()
        print(f"   ✅ HIGH confidence: {high_count:,} records")
        
        # MEDIUM: General present but at least one other missing
        result = await db.execute(text("""
            UPDATE hts_versions
            SET duty_rate_confidence = 'medium'
            WHERE duty_rate_confidence IS NULL
              AND duty_rate_general IS NOT NULL
              AND (duty_rate_special IS NULL OR duty_rate_column2 IS NULL)
        """))
        medium_count = result.rowcount
        await db.commit()
        print(f"   ✅ MEDIUM confidence: {medium_count:,} records")
        
        # LOW: General missing
        result = await db.execute(text("""
            UPDATE hts_versions
            SET duty_rate_confidence = 'low'
            WHERE duty_rate_confidence IS NULL
              AND duty_rate_general IS NULL
        """))
        low_count = result.rowcount
        await db.commit()
        print(f"   ✅ LOW confidence: {low_count:,} records")
        
        # Copy source_page to duty_rate_source_page
        print()
        print("5️⃣  Copying source_page to duty_rate_source_page...")
        result = await db.execute(text("""
            UPDATE hts_versions
            SET duty_rate_source_page = source_page
            WHERE duty_rate_source_page IS NULL
              AND source_page IS NOT NULL
        """))
        copied_count = result.rowcount
        await db.commit()
        print(f"   ✅ Copied source_page for {copied_count:,} records")
        
        # Summary
        print()
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        result = await db.execute(text("""
            SELECT duty_rate_confidence, COUNT(*) as count
            FROM hts_versions
            GROUP BY duty_rate_confidence
            ORDER BY duty_rate_confidence
        """))
        summary = result.all()
        
        total = sum(row[1] for row in summary)
        for conf, count in summary:
            pct = (count / total * 100) if total > 0 else 0
            print(f"   {conf or 'NULL':10} {count:6,} ({pct:.1f}%)")
        
        print()
        print("=" * 80)
        print("✅ CONFIDENCE POPULATION COMPLETE")
        print("=" * 80)
        print()
        print("📝 NOTES:")
        print("   - HIGH: All 3 duty rate columns populated")
        print("   - MEDIUM: General rate present, but at least one other missing")
        print("   - LOW: General rate missing")
        print("   - Use duty_rate_confidence for risk intelligence in classification")
        print()
        
        break


if __name__ == "__main__":
    asyncio.run(populate_duty_rate_confidence())


