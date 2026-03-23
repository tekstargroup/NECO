"""
Parent Duty Backfill Script - Sprint 5.3

Backfills parent node duty fields (6-digit and 8-digit) based on child consensus.
Only backfills when there is positive evidence (high coverage, no conflicts).
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import Counter, defaultdict
import re
import json
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import async_session_maker
from app.models.hts_node import HTSNode


# Normalization helpers (for comparison only; store raw)

def normalize_pct(value: str) -> str:
    """Normalize percentage string for comparison."""
    if not value:
        return ""
    # Remove footnote markers like "1/" at end
    value = re.sub(r'\d+/\s*$', '', value.strip())
    # Normalize comma to dot
    value = value.replace(',', '.')
    # Ensure ends with %
    if value and not value.endswith('%'):
        value += '%'
    return value.strip()


def normalize_special(value: str) -> str:
    """Normalize special duty string for comparison."""
    if not value:
        return ""
    # Collapse whitespace
    value = re.sub(r'\s+', ' ', value.strip())
    # Strip footnote markers like "1/" at end
    value = re.sub(r'\d+/\s*$', '', value)
    return value.strip()


def normalize_col2(value: str) -> str:
    """Normalize column 2 duty string for comparison (similar to pct)."""
    return normalize_pct(value)


# Coverage thresholds

COVERAGE_THRESHOLDS = {
    8: {
        "minimum_non_null_children": 3,
        "coverage_ratio": 0.80,
    },
    6: {
        "minimum_non_null_children": 2,
        "coverage_ratio": 0.80,
    },
}


async def get_children_for_parent(
    db: AsyncSession,
    parent_code: str,
    parent_level: int,
    hts_version_id: Optional[str]
) -> List[HTSNode]:
    """
    Get eligible children for a parent node.
    
    For 8-digit parent: returns all 10-digit descendants
    For 6-digit parent: returns all 8-digit descendants (prefer 8-digit if available)
    """
    if parent_level == 8:
        # Get 10-digit children
        query = select(HTSNode).where(
            HTSNode.level == 10,
            HTSNode.code_normalized.like(f"{parent_code}%")
        )
        if hts_version_id:
            query = query.where(HTSNode.hts_version_id == hts_version_id)
        else:
            query = query.where(HTSNode.hts_version_id.is_(None))
    elif parent_level == 6:
        # Prefer 8-digit children, but can also check 10-digit if needed
        query = select(HTSNode).where(
            HTSNode.level == 8,
            HTSNode.code_normalized.like(f"{parent_code}%")
        )
        if hts_version_id:
            query = query.where(HTSNode.hts_version_id == hts_version_id)
        else:
            query = query.where(HTSNode.hts_version_id.is_(None))
    else:
        return []
    
    result = await db.execute(query)
    nodes = list(result.scalars().all())
    
    # Filter out invalid nodes (bogus synthetic codes)
    valid_nodes = []
    for node in nodes:
        if node.source_lineage and node.source_lineage.get("is_valid") is False:
            continue
        valid_nodes.append(node)
    
    return valid_nodes


def analyze_child_consensus(
    children: List[HTSNode],
    field_name: str
) -> Dict[str, Any]:
    """
    Analyze child consensus for a duty field.
    
    Returns:
        {
            "non_null_count": int,
            "total_count": int,
            "coverage_ratio": float,
            "normalized_values": Counter,  # normalized -> count
            "raw_value_groups": Dict[str, List[str]],  # normalized -> list of raw values
            "conflicts": bool,
            "unique_normalized_value": Optional[str],
            "representative_raw": Optional[str],
        }
    """
    total_count = len(children)
    non_null_children = [c for c in children if getattr(c, field_name) is not None]
    non_null_count = len(non_null_children)
    
    if non_null_count == 0:
        return {
            "non_null_count": 0,
            "total_count": total_count,
            "coverage_ratio": 0.0,
            "normalized_values": Counter(),
            "raw_value_groups": {},
            "conflicts": False,
            "unique_normalized_value": None,
            "representative_raw": None,
        }
    
    # Normalize values and group by normalized value
    normalize_func = {
        "duty_general_raw": normalize_pct,
        "duty_special_raw": normalize_special,
        "duty_column2_raw": normalize_col2,
    }[field_name]
    
    normalized_values = Counter()
    raw_value_groups = defaultdict(list)
    
    for child in non_null_children:
        raw_value = getattr(child, field_name)
        normalized = normalize_func(raw_value)
        normalized_values[normalized] += 1
        raw_value_groups[normalized].append(raw_value)
    
    # Check for conflicts
    unique_normalized = None
    conflicts = len(normalized_values) > 1
    
    if not conflicts:
        unique_normalized = list(normalized_values.keys())[0] if normalized_values else None
    
    # Select representative raw value (mode, or longest if tie)
    representative_raw = None
    if unique_normalized:
        raw_candidates = raw_value_groups[unique_normalized]
        if raw_candidates:
            # Count frequency of each raw value
            raw_counter = Counter(raw_candidates)
            # Get most common
            most_common_raw, most_common_count = raw_counter.most_common(1)[0]
            # If tie, pick longest
            if most_common_count == 1 and len(raw_candidates) > 1:
                representative_raw = max(raw_candidates, key=len)
            else:
                representative_raw = most_common_raw
    
    coverage_ratio = non_null_count / total_count if total_count > 0 else 0.0
    
    return {
        "non_null_count": non_null_count,
        "total_count": total_count,
        "coverage_ratio": coverage_ratio,
        "normalized_values": normalized_values,
        "raw_value_groups": dict(raw_value_groups),
        "conflicts": conflicts,
        "unique_normalized_value": unique_normalized,
        "representative_raw": representative_raw,
    }


def check_backfill_eligibility(
    analysis: Dict[str, Any],
    parent_level: int
) -> Tuple[bool, Optional[str]]:
    """
    Check if backfill is eligible based on analysis and thresholds.
    
    Returns:
        (eligible: bool, reason: Optional[str])
    """
    thresholds = COVERAGE_THRESHOLDS[parent_level]
    
    if analysis["non_null_count"] == 0:
        return False, "No non-null children"
    
    if analysis["non_null_count"] < thresholds["minimum_non_null_children"]:
        return False, f"Too few non-null children ({analysis['non_null_count']} < {thresholds['minimum_non_null_children']})"
    
    if analysis["coverage_ratio"] < thresholds["coverage_ratio"]:
        return False, f"Coverage too low ({analysis['coverage_ratio']:.2%} < {thresholds['coverage_ratio']:.2%})"
    
    if analysis["conflicts"]:
        return False, f"Conflicting values: {list(analysis['normalized_values'].keys())}"
    
    return True, None


async def backfill_parent_duties(
    db: AsyncSession,
    hts_version_id: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Backfill parent duties based on child consensus.
    
    Args:
        db: Database session
        hts_version_id: Optional HTS version ID (defaults to AUTHORITATIVE_HTS_VERSION_ID)
        dry_run: If True, don't write changes
    
    Returns:
        Report dictionary
    """
    from app.core.hts_constants import validate_hts_version_id
    
    # Validate and set default version
    hts_version_id = validate_hts_version_id(hts_version_id)
    
    report = {
        "hts_version_id": hts_version_id,
        "dry_run": dry_run,
        "parents_considered": 0,
        "parents_updated": {
            "level_6": {"general": 0, "special": 0, "col2": 0},
            "level_8": {"general": 0, "special": 0, "col2": 0},
        },
        "conflicts_detected": 0,
        "parents_skipped_low_coverage": 0,
        "parents_skipped_existing_value": 0,
        "updated_parents": [],
        "conflict_examples": [],
        "low_coverage_examples": [],
    }
    
    # Get all parent nodes (6-digit and 8-digit) for this version
    query = select(HTSNode).where(
        HTSNode.level.in_([6, 8])
    )
    if hts_version_id:
        query = query.where(HTSNode.hts_version_id == hts_version_id)
    else:
        query = query.where(HTSNode.hts_version_id.is_(None))
    query = query.order_by(HTSNode.level, HTSNode.code_normalized)
    
    report["hts_version_id"] = hts_version_id or "None"
    
    result = await db.execute(query)
    parent_nodes = list(result.scalars().all())
    
    report["parents_considered"] = len(parent_nodes)
    
    for parent in parent_nodes:
        # Get children
        children = await get_children_for_parent(
            db, parent.code_normalized, parent.level, hts_version_id
        )
        
        if not children:
            continue
        
        # Process each duty field
        for field_name in ["duty_general_raw", "duty_special_raw", "duty_column2_raw"]:
            # Skip if parent already has non-null value
            if getattr(parent, field_name) is not None:
                report["parents_skipped_existing_value"] += 1
                continue
            
            # Analyze child consensus
            analysis = analyze_child_consensus(children, field_name)
            
            # Check eligibility
            eligible, reason = check_backfill_eligibility(analysis, parent.level)
            
            if not eligible:
                if analysis["conflicts"]:
                    report["conflicts_detected"] += 1
                    if len(report["conflict_examples"]) < 5:
                        report["conflict_examples"].append({
                            "parent_code": parent.code_display or parent.code_normalized,
                            "parent_level": parent.level,
                            "field": field_name,
                            "conflicting_values": list(analysis["normalized_values"].keys()),
                        })
                elif "coverage" in reason.lower() or "few" in reason.lower():
                    report["parents_skipped_low_coverage"] += 1
                    if len(report["low_coverage_examples"]) < 5:
                        report["low_coverage_examples"].append({
                            "parent_code": parent.code_display or parent.code_normalized,
                            "parent_level": parent.level,
                            "field": field_name,
                            "reason": reason,
                            "coverage": analysis["coverage_ratio"],
                            "non_null_count": analysis["non_null_count"],
                        })
                continue
            
            # Eligible for backfill
            representative_raw = analysis["representative_raw"]
            
            if not dry_run:
                # Update parent
                setattr(parent, field_name, representative_raw)
                
                # Update backfill metadata in source_lineage
                meta = parent.source_lineage or {}
                backfill_meta = meta.get("duty_backfill", {})
                backfill_meta[field_name] = {
                    "backfilled": True,
                    "source": "children_consensus",
                    "child_count": analysis["non_null_count"],
                    "total_children": analysis["total_count"],
                    "coverage_ratio": analysis["coverage_ratio"],
                    "example_child_codes": [
                        c.code_display or c.code_normalized
                        for c in children[:5]
                        if getattr(c, field_name) is not None
                    ],
                }
                meta["duty_backfill"] = backfill_meta
                parent.source_lineage = meta
            
            # Track update
            level_key = f"level_{parent.level}"
            # Map field names: duty_general_raw -> general, duty_special_raw -> special, duty_column2_raw -> col2
            field_mapping = {
                "duty_general_raw": "general",
                "duty_special_raw": "special",
                "duty_column2_raw": "col2",
            }
            field_short = field_mapping.get(field_name, field_name.replace("duty_", "").replace("_raw", ""))
            report["parents_updated"][level_key][field_short] += 1
            
            if len(report["updated_parents"]) < 10:
                report["updated_parents"].append({
                    "parent_code": parent.code_display or parent.code_normalized,
                    "parent_level": parent.level,
                    "field": field_name,
                    "value": representative_raw,
                    "coverage": analysis["coverage_ratio"],
                    "non_null_count": analysis["non_null_count"],
                    "total_children": analysis["total_count"],
                    "example_children": [
                        c.code_display or c.code_normalized
                        for c in children[:3]
                        if getattr(c, field_name) is not None
                    ],
                })
    
    if not dry_run:
        await db.commit()
    
    return report


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill parent node duties based on child consensus"
    )
    parser.add_argument(
        "--hts-version-id",
        required=False,
        default=None,
        help="HTS version ID to process (use 'None' for null version_id)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no database writes)"
    )
    
    args = parser.parse_args()
    
    hts_version_id = None
    if args.hts_version_id and args.hts_version_id.lower() != "none":
        try:
            hts_version_id = str(UUID(args.hts_version_id))
        except ValueError:
            print(f"ERROR: Invalid UUID format: {args.hts_version_id}")
            sys.exit(1)
    
    print("=" * 80)
    print("Parent Duty Backfill - Sprint 5.3")
    print("=" * 80)
    print(f"HTS Version ID: {hts_version_id}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    async with async_session_maker() as db:
        report = await backfill_parent_duties(
            db, hts_version_id, dry_run=args.dry_run
        )
        
        # Print report
        print("=" * 80)
        print("Backfill Report")
        print("=" * 80)
        print(f"Parents considered: {report['parents_considered']}")
        print()
        print("Parents updated:")
        print(f"  6-digit: general={report['parents_updated']['level_6']['general']}, "
              f"special={report['parents_updated']['level_6']['special']}, "
              f"col2={report['parents_updated']['level_6']['col2']}")
        print(f"  8-digit: general={report['parents_updated']['level_8']['general']}, "
              f"special={report['parents_updated']['level_8']['special']}, "
              f"col2={report['parents_updated']['level_8']['col2']}")
        print()
        print(f"Conflicts detected: {report['conflicts_detected']}")
        print(f"Parents skipped (low coverage): {report['parents_skipped_low_coverage']}")
        print(f"Parents skipped (existing value): {report['parents_skipped_existing_value']}")
        print()
        
        if report["updated_parents"]:
            print("Example updated parents:")
            for ex in report["updated_parents"][:5]:
                print(f"  {ex['parent_code']} (level {ex['parent_level']}): "
                      f"{ex['field']} = {ex['value']} "
                      f"(coverage: {ex['coverage']:.2%}, "
                      f"{ex['non_null_count']}/{ex['total_children']} children)")
        
        if report["conflict_examples"]:
            print()
            print("Example conflicts:")
            for ex in report["conflict_examples"][:3]:
                print(f"  {ex['parent_code']}: {ex['field']} has conflicting values: {ex['conflicting_values']}")
        
        if report["low_coverage_examples"]:
            print()
            print("Example low coverage:")
            for ex in report["low_coverage_examples"][:3]:
                print(f"  {ex['parent_code']}: {ex['field']} - {ex['reason']}")
        
        # Save full report to JSON
        output_file = Path(__file__).parent / f"backfill_report_{hts_version_id}.json"
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print()
        print(f"Full report saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
