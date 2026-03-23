"""
HTS Nodes Backfill Script - Sprint 5.1.5

Populates hts_nodes table with multi-level HTS hierarchy (6, 8, 10-digit codes).

This script:
1. Reads from hts_versions (10-digit codes)
2. Extracts parent nodes (8-digit, 6-digit) from existing data
3. Populates hts_nodes with all levels

Note: If the original 69,430 extracted structured codes are available as JSON/CSV,
this script can be extended to read from that source instead.
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.models.hts_node import HTSNode


def normalize_hts_code(code: str) -> str:
    """Normalize HTS code to digits only (remove dots, spaces)."""
    if not code:
        return ""
    return re.sub(r'[^\d]', '', code)


def get_parent_code(code_normalized: str, target_level: int) -> Optional[str]:
    """Get parent code at target level (6 or 8 digits)."""
    if len(code_normalized) < target_level:
        return None
    return code_normalized[:target_level]


def determine_level(code_normalized: str) -> int:
    """Determine HTS code level from length."""
    if len(code_normalized) == 10:
        return 10
    elif len(code_normalized) == 8:
        return 8
    elif len(code_normalized) == 6:
        return 6
    return 0


async def extract_nodes_from_hts_versions(
    db: AsyncSession,
    hts_version_id: Optional[str] = None
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """
    Extract multi-level nodes from hts_versions table.
    
    For each 10-digit code, creates:
    - 10-digit node (from hts_versions row)
    - 8-digit parent node (aggregated from children)
    - 6-digit parent node (aggregated from children)
    
    Returns:
        Dict mapping level -> {code_normalized -> node_data}
    """
    nodes_by_level = defaultdict(dict)  # level -> {code -> node_data}
    
    # Fetch all 10-digit codes from hts_versions
    query = text("""
        SELECT 
            hts_code,
            hts_chapter,
            hts_heading_6,
            tariff_text_short,
            tariff_text,
            duty_rate_general,
            duty_rate_special,
            duty_rate_column2,
            source_page,
            effective_from,
            effective_to
        FROM hts_versions
        WHERE hts_chapter NOT IN ('98', '99')
          AND hts_code NOT LIKE '98%'
          AND hts_code NOT LIKE '99%'
          AND LENGTH(REPLACE(REPLACE(hts_code, '.', ''), ' ', '')) = 10
        ORDER BY hts_code
    """)
    
    result = await db.execute(query)
    rows = result.fetchall()
    
    print(f"Found {len(rows)} 10-digit codes in hts_versions")
    
    # Process each 10-digit code
    for row in rows:
        hts_code = row[0]
        code_normalized = normalize_hts_code(hts_code)
        
        if len(code_normalized) != 10:
            continue
        
        # Create 10-digit node
        nodes_by_level[10][code_normalized] = {
            "code_normalized": code_normalized,
            "code_display": hts_code,
            "level": 10,
            "parent_code_normalized": get_parent_code(code_normalized, 8),
            "description_short": row[3],  # tariff_text_short
            "description_long": row[4],  # tariff_text
            "duty_general_raw": row[5],  # duty_rate_general
            "duty_special_raw": row[6],  # duty_rate_special
            "duty_column2_raw": row[7],  # duty_rate_column2
            "source_lineage": {
                "source_page": row[8],
                "effective_from": str(row[9]) if row[9] else None,
                "effective_to": str(row[10]) if row[10] else None,
            } if row[8] else None,
        }
        
        # Create 8-digit parent node (if not already created)
        code_8 = get_parent_code(code_normalized, 8)
        if code_8 and code_8 not in nodes_by_level[8]:
            # For parent nodes, we'll use the first child's description as placeholder
            # In a proper extraction, these would come from the PDF directly
            nodes_by_level[8][code_8] = {
                "code_normalized": code_8,
                "code_display": f"{code_8[:4]}.{code_8[4:6]}.{code_8[6:8]}",
                "level": 8,
                "parent_code_normalized": get_parent_code(code_8, 6),
                "description_short": None,  # Will be populated from PDF extraction
                "description_long": None,
                "duty_general_raw": None,  # Will be populated from PDF extraction
                "duty_special_raw": None,
                "duty_column2_raw": None,
                "source_lineage": None,
            }
        
        # Create 6-digit parent node (if not already created)
        code_6 = get_parent_code(code_normalized, 6)
        if code_6 and code_6 not in nodes_by_level[6]:
            nodes_by_level[6][code_6] = {
                "code_normalized": code_6,
                "code_display": f"{code_6[:4]}.{code_6[4:6]}",
                "level": 6,
                "parent_code_normalized": None,  # 6-digit is typically top-level heading
                "description_short": None,
                "description_long": None,
                "duty_general_raw": None,
                "duty_special_raw": None,
                "duty_column2_raw": None,
                "source_lineage": None,
            }
    
    print(f"Extracted nodes: {len(nodes_by_level[10])} 10-digit, {len(nodes_by_level[8])} 8-digit, {len(nodes_by_level[6])} 6-digit")
    
    return dict(nodes_by_level)


async def upsert_hts_nodes_batch(
    db: AsyncSession,
    nodes: List[Dict[str, Any]],
    hts_version_id: Optional[str] = None
) -> int:
    """
    Upsert a batch of HTS nodes.
    
    Uses ON CONFLICT to handle duplicates safely.
    """
    if not nodes:
        return 0
    
    # Prepare values for insert
    values_list = []
    for node in nodes:
        values_list.append({
            "hts_version_id": hts_version_id,
            "code_normalized": node["code_normalized"],
            "code_display": node.get("code_display"),
            "level": node["level"],
            "parent_code_normalized": node.get("parent_code_normalized"),
            "description_short": node.get("description_short"),
            "description_long": node.get("description_long"),
            "duty_general_raw": node.get("duty_general_raw"),
            "duty_special_raw": node.get("duty_special_raw"),
            "duty_column2_raw": node.get("duty_column2_raw"),
            "source_lineage": node.get("source_lineage"),
        })
    
    # Use SQLAlchemy insert with ON CONFLICT
    stmt = pg_insert(HTSNode).values(values_list)
    
    stmt = stmt.on_conflict_do_update(
        index_elements=['hts_version_id', 'level', 'code_normalized'],
        set_={
            "code_display": stmt.excluded.code_display,
            "parent_code_normalized": stmt.excluded.parent_code_normalized,
            "description_short": stmt.excluded.description_short,
            "description_long": stmt.excluded.description_long,
            "duty_general_raw": stmt.excluded.duty_general_raw,
            "duty_special_raw": stmt.excluded.duty_special_raw,
            "duty_column2_raw": stmt.excluded.duty_column2_raw,
            "source_lineage": stmt.excluded.source_lineage,
            "updated_at": text("now()"),
        }
    )
    
    await db.execute(stmt)
    await db.commit()
    
    return len(nodes)


async def backfill_hts_nodes(
    hts_version_id: Optional[str] = None,
    batch_size: int = 1000,
    dry_run: bool = False
):
    """
    Main backfill function to populate hts_nodes from hts_versions.
    """
    engine = create_async_engine(settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("=" * 80)
        print("HTS Nodes Backfill - Sprint 5.1.5")
        print("=" * 80)
        print(f"HTS Version ID: {hts_version_id or 'NULL (latest)'}")
        print(f"Batch Size: {batch_size}")
        print(f"Dry Run: {dry_run}")
        print()
        
        # Extract nodes from hts_versions
        print("Extracting nodes from hts_versions...")
        nodes_by_level = await extract_nodes_from_hts_versions(db, hts_version_id)
        
        if dry_run:
            print("\n[DRY RUN] Would insert:")
            for level in [6, 8, 10]:
                count = len(nodes_by_level.get(level, {}))
                print(f"  Level {level}: {count} nodes")
            return
        
        # Upsert nodes by level
        total_inserted = 0
        for level in [6, 8, 10]:
            nodes = list(nodes_by_level.get(level, {}).values())
            if not nodes:
                continue
            
            print(f"\nUpserting {len(nodes)} level-{level} nodes...")
            
            # Process in batches
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                inserted = await upsert_hts_nodes_batch(db, batch, hts_version_id)
                total_inserted += inserted
                print(f"  Batch {i//batch_size + 1}: {inserted} nodes upserted")
        
        print(f"\nTotal nodes upserted: {total_inserted}")
        
        # Verify counts
        result = await db.execute(text("""
            SELECT level, COUNT(*) as count
            FROM hts_nodes
            GROUP BY level
            ORDER BY level
        """))
        
        print("\nFinal node counts by level:")
        for row in result:
            print(f"  Level {row[0]}: {row[1]:,} nodes")
        
        # Sample parent chain verification
        result = await db.execute(text("""
            SELECT code_normalized, level, parent_code_normalized
            FROM hts_nodes
            WHERE level = 10
            ORDER BY RANDOM()
            LIMIT 10
        """))
        
        print("\nSample parent chain verification (10 random 10-digit codes):")
        for row in result:
            code_10 = row[0]
            parent_8 = get_parent_code(code_10, 8)
            parent_6 = get_parent_code(code_10, 6)
            
            # Check if parents exist
            parent_8_exists = await db.execute(
                text("SELECT COUNT(*) FROM hts_nodes WHERE code_normalized = :code AND level = 8"),
                {"code": parent_8}
            )
            parent_8_count = parent_8_exists.scalar()
            
            parent_6_exists = await db.execute(
                text("SELECT COUNT(*) FROM hts_nodes WHERE code_normalized = :code AND level = 6"),
                {"code": parent_6}
            )
            parent_6_count = parent_6_exists.scalar()
            
            status = "✅" if (parent_8_count > 0 and parent_6_count > 0) else "❌"
            print(f"  {status} {code_10}: 8-digit parent {parent_8} ({'exists' if parent_8_count > 0 else 'missing'}), "
                  f"6-digit parent {parent_6} ({'exists' if parent_6_count > 0 else 'missing'})")
    
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill hts_nodes from hts_versions")
    parser.add_argument("--hts-version-id", type=str, default=None, help="HTS version ID (default: NULL)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size (default: 1000)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database writes)")
    
    args = parser.parse_args()
    
    asyncio.run(backfill_hts_nodes(
        hts_version_id=args.hts_version_id,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    ))
