"""
Duty Rates Backfill Script - Sprint 5 Phase 2.1

Reads from hts_versions, parses duty rates using DutyParser, and populates duty_rates table
with batching and upsert support for safe reruns.
"""

import sys
import asyncio
import argparse
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import json
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, select, bindparam, literal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.engines.duty.duty_parser import DutyParser, ParsedDutyRate
from app.models.duty_rate import DutyType, DutyConfidence, DutySourceLevel


def normalize_hts_code(code: str) -> str:
    """Normalize HTS code to digits only (remove dots, spaces)."""
    if not code:
        return ""
    return re.sub(r'[^\d]', '', code)


def determine_source_level(hts_code: str) -> Optional[DutySourceLevel]:
    """Determine source level from HTS code length."""
    normalized = normalize_hts_code(hts_code)
    if len(normalized) == 10:
        return DutySourceLevel.TEN_DIGIT
    elif len(normalized) == 8:
        return DutySourceLevel.EIGHT_DIGIT
    elif len(normalized) == 6:
        return DutySourceLevel.SIX_DIGIT
    return None


def get_canonical_duty_text(row: Dict[str, Any], duty_column: str) -> Optional[str]:
    """
    Get canonical duty text field in priority order:
    1. duty_rate_{column} (the actual duty rate text field from hts_versions)
    2. tariff_text_short (fallback)
    3. tariff_text (last resort)
    
    Note: duty_rate_general/special/column2 in hts_versions contain the parsed duty text
    like "4.9%", "Free", etc. These are what we want to parse.
    """
    # Primary: duty rate column (duty_rate_general, duty_rate_special, duty_rate_column2)
    duty_field = f"duty_rate_{duty_column}" if duty_column != "column2" else "duty_rate_column2"
    if duty_field in row and row[duty_field] is not None:
        duty_text = str(row[duty_field]).strip()
        if duty_text and duty_text.upper() not in ["NULL", "N/A", "NONE", ""]:
            return duty_text
    
    # Fallback: tariff_text_short (may contain duty info)
    if row.get("tariff_text_short"):
        tariff_short = str(row["tariff_text_short"]).strip()
        if tariff_short:
            return tariff_short
    
    # Last resort: tariff_text
    if row.get("tariff_text"):
        tariff_text = str(row["tariff_text"]).strip()
        if tariff_text:
            return tariff_text
    
    return None


def has_9903_contamination(text: Optional[str]) -> bool:
    """Check if duty text contains 9903 contamination."""
    if not text:
        return False
    return "9903." in str(text).upper() or "9903" in str(text).upper()


def is_cross_reference(text: Optional[str]) -> bool:
    """Check if text looks like a cross-reference (See subheading, See note, etc.)."""
    if not text:
        return False
    text_lower = str(text).lower()
    return bool(
        re.search(r'see\s+(subheading|heading|note)', text_lower) or
        re.search(r'as\s+provided\s+for', text_lower) or
        re.search(r'subject\s+to\s+note', text_lower)
    )


async def get_latest_hts_version_id(db: AsyncSession) -> Optional[str]:
    """Get the latest active hts_version_id (or generate synthetic if needed)."""
    # For now, since hts_versions might not have explicit versioning,
    # we'll use NULL or a synthetic identifier
    # This can be enhanced in Phase 3 when we have proper versioning
    return None


async def fetch_hts_nodes(
    db: AsyncSession,
    hts_version_id: Optional[str],
    levels: List[int],
    duty_column: str,
    batch_size: int,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Fetch HTS nodes from hts_nodes table (Sprint 5.1.5).
    
    Returns:
        Tuple of (rows, has_more)
    """
    # Build WHERE clause for source levels
    level_conditions = []
    for level in levels:
        level_conditions.append(f"level = {level}")
    
    if not level_conditions:
        return [], False
    
    where_clause = "(" + " OR ".join(level_conditions) + ")"
    
    # Exclude 98/99 chapters and 9903 codes (hard exclusions)
    where_clause += """
        AND code_normalized NOT LIKE '98%'
        AND code_normalized NOT LIKE '99%'
        AND COALESCE(description_long, '') NOT ILIKE '%9903.%'
        AND COALESCE(description_short, '') NOT ILIKE '%9903.%'
    """
    
    # Only fetch nodes that have duty text for the requested column
    duty_field_map = {
        "general": "duty_general_raw",
        "special": "duty_special_raw",
        "column2": "duty_column2_raw",
    }
    duty_field = duty_field_map.get(duty_column, "duty_general_raw")
    where_clause += f" AND {duty_field} IS NOT NULL"
    
    query = f"""
        SELECT 
            code_normalized,
            code_display,
            level,
            parent_code_normalized,
            description_short,
            description_long,
            duty_general_raw,
            duty_special_raw,
            duty_column2_raw,
            source_lineage
        FROM hts_nodes
        WHERE {where_clause}
        ORDER BY level, code_normalized
        LIMIT :limit OFFSET :offset
    """
    
    result = await db.execute(
        text(query),
        {"limit": batch_size + 1, "offset": offset}  # Fetch one extra to check if more
    )
    
    rows = result.fetchall()
    has_more = len(rows) > batch_size
    
    if has_more:
        rows = rows[:batch_size]
    
    # Convert to dicts (matching the format expected by process_batch)
    row_dicts = []
    for row in rows:
        # Extract chapter from code (first 2 digits)
        chapter = row[0][:2] if len(row[0]) >= 2 else None
        
        row_dicts.append({
            "hts_code": row[1] or row[0],  # code_display or code_normalized
            "hts_chapter": chapter,
            "tariff_text_short": row[4],  # description_short
            "tariff_text": row[5],  # description_long
            "duty_rate_general": row[6],  # duty_general_raw
            "duty_rate_special": row[7],  # duty_special_raw
            "duty_rate_column2": row[8],  # duty_column2_raw
            "source_page": row[9].get("source_page") if row[9] else None,  # from source_lineage
            "effective_from": row[9].get("effective_from") if row[9] else None,
            "effective_to": row[9].get("effective_to") if row[9] else None,
            "_node_level": row[2],  # Store level for later use
        })
    
    return row_dicts, has_more


async def process_batch(
    db: AsyncSession,
    parser: DutyParser,
    hts_rows: List[Dict[str, Any]],
    hts_version_id: Optional[str],
    duty_column: str,
    dry_run: bool,
    stats: Dict[str, Any]
) -> None:
    """Process a batch of HTS rows and upsert duty_rates."""
    
    duty_rate_rows = []
    
    for row in hts_rows:
        hts_code = row["hts_code"]
        source_code = normalize_hts_code(hts_code)
        source_level = determine_source_level(hts_code)
        
        if not source_level:
            stats["skipped_invalid_code"] += 1
            continue
        
        # Get canonical duty text for the specified column
        duty_text = get_canonical_duty_text(row, duty_column)
        
        # Guardrails: Check for 9903 contamination or cross-references BEFORE parsing
        if has_9903_contamination(duty_text) or is_cross_reference(duty_text):
            # Force CONDITIONAL or TEXT_ONLY with LOW confidence, no numeric parsing
            # Guardrail: Do not misparse numeric even if percent appears
            if is_cross_reference(duty_text):
                parsed = ParsedDutyRate(
                    raw_text=duty_text,
                    duty_type=DutyType.CONDITIONAL,
                    duty_confidence=DutyConfidence.LOW,
                    structure={"text": duty_text, "reason": "cross_reference_detected"},
                    numeric_value=None,
                    is_free=False,
                    parse_errors=["Cross-reference detected - numeric parsing blocked by guardrail"],
                    parse_method="guardrail_blocked"
                )
            else:
                # 9903 contamination
                parsed = ParsedDutyRate(
                    raw_text=duty_text,
                    duty_type=DutyType.TEXT_ONLY,
                    duty_confidence=DutyConfidence.LOW,
                    structure={"text": duty_text, "reason": "9903_contamination_detected"},
                    numeric_value=None,
                    is_free=False,
                    parse_errors=["9903 contamination detected - numeric parsing blocked by guardrail"],
                    parse_method="guardrail_blocked"
                )
        elif not duty_text or not duty_text.strip():
            # Empty/null duty text - skip (per requirement: "store nothing")
            stats["missing_duty_text"] += 1
            continue  # Skip this row
        else:
            # Normal parsing
            parsed = parser.parse_duty_rate(duty_text, hts_code=hts_code, source_level=source_level)
        
        # Track stats
        stats["total_parsed"] += 1
        stats["by_type"][parsed.duty_type.value] += 1
        stats["by_confidence"][parsed.duty_confidence.value] += 1
        if parsed.is_free:
            stats["free_count"] += 1
        if parsed.numeric_value is not None:
            stats["numeric_computable"] += 1
        if parsed.duty_type == DutyType.COMPOUND:
            stats["compound_count"] += 1
        if parsed.duty_type == DutyType.CONDITIONAL:
            stats["conditional_count"] += 1
        if parsed.duty_type == DutyType.TEXT_ONLY:
            stats["text_only_count"] += 1
        
        # Track unparsed patterns for reporting
        if parsed.duty_type == DutyType.TEXT_ONLY and parsed.raw_text:
            pattern_key = parsed.raw_text[:50]  # First 50 chars as pattern key
            stats["unparsed_patterns"][pattern_key] += 1
        
        # Build duty_rate row
        # Note: Enum values are already lowercase strings (e.g., "ten_digit", "ad_valorem")
        duty_rate_row = {
            "hts_version_id": hts_version_id,
            "hts_code": source_code,  # Normalized
            "source_code": source_code,
            "duty_column": duty_column,
            "source_level": source_level.value,  # Already lowercase from enum
            "duty_type": parsed.duty_type.value,  # Already lowercase from enum
            "duty_rate_raw_text": parsed.raw_text if parsed.raw_text else None,
            "duty_rate_structure": parsed.structure,
            "duty_rate_numeric": parsed.numeric_value,
            "duty_confidence": parsed.duty_confidence.value,  # Already lowercase from enum
            "is_free": parsed.is_free,
            "source_page": str(row.get("source_page")) if row.get("source_page") is not None else None,
            "effective_start_date": row.get("effective_from"),
            "effective_end_date": row.get("effective_to"),
            "additional_metadata": {
                "parse_method": parsed.parse_method,
                "parse_errors": parsed.parse_errors,
            } if parsed.parse_errors else None,
        }
        
        duty_rate_rows.append(duty_rate_row)
        stats["by_source_level"][source_level.value] += 1
    
    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(duty_rate_rows)} duty_rate rows")
        return
    
    # Batch upsert using INSERT...ON CONFLICT DO UPDATE (with automatic chunking)
    if duty_rate_rows:
        await upsert_duty_rates_batch(db, duty_rate_rows)
        stats["upserted_count"] += len(duty_rate_rows)


async def upsert_duty_rates_batch(db: AsyncSession, rows: List[Dict[str, Any]]) -> None:
    """
    Upsert a batch of duty_rates using INSERT...ON CONFLICT DO UPDATE.
    
    Automatically chunks large batches to avoid PostgreSQL parameter limits.
    """
    
    if not rows:
        return
    
    # PostgreSQL has parameter limits (~65k), but SQLAlchemy converts named params to positional
    # Each row uses ~15 parameters, so max ~200 rows per chunk is safer
    CHUNK_SIZE = 200
    
    if len(rows) > CHUNK_SIZE:
        # Split into chunks and process sequentially
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            await _upsert_duty_rates_chunk(db, chunk)
        return
    
    # Process single chunk
    await _upsert_duty_rates_chunk(db, rows)


async def _upsert_duty_rates_chunk(db: AsyncSession, rows: List[Dict[str, Any]]) -> None:
    """
    Upsert a single chunk of duty_rates (max 250 rows to avoid parameter limits).
    """
    
    if not rows:
        return
    
    # Use positional parameters for asyncpg compatibility
    # Build raw SQL with $1, $2, etc. positional parameters
    values_clauses = []
    params = []
    param_idx = 1
    
    for row in rows:
        # Handle NULL hts_version_id
        if row["hts_version_id"] is None:
            hts_version_id_sql = "NULL"
        else:
            hts_version_id_sql = f"${param_idx}"
            params.append(str(row["hts_version_id"]))
            param_idx += 1
        
        # Build VALUES clause with positional parameters
        values_clauses.append(f"""(
            gen_random_uuid(),
            {hts_version_id_sql},
            ${param_idx}, ${param_idx+1}, ${param_idx+2}, ${param_idx+3}::dutysourcelevel,
            ${param_idx+4}::dutytype, ${param_idx+5}, ${param_idx+6}::jsonb, ${param_idx+7},
            ${param_idx+8}::dutyconfidence, ${param_idx+9}, ${param_idx+10}, ${param_idx+11}, ${param_idx+12},
            NULL, NULL, ${param_idx+13}::jsonb,
            now(), now()
        )""")
        
        # Add parameters in order
        params.extend([
            row["hts_code"],
            row["source_code"],
            row["duty_column"],
            row["source_level"],
            row["duty_type"],
            row["duty_rate_raw_text"],
            json.dumps(row["duty_rate_structure"]) if row["duty_rate_structure"] else None,
            float(row["duty_rate_numeric"]) if row["duty_rate_numeric"] is not None else None,
            row["duty_confidence"],
            bool(row["is_free"]),
            row.get("source_page"),
            row.get("effective_start_date"),
            row.get("effective_end_date"),
            json.dumps(row.get("additional_metadata")) if row.get("additional_metadata") else None,
        ])
        param_idx += 14  # 14 parameters per row (excluding hts_version_id which may be NULL)
    
    values_sql = ",\n            ".join(values_clauses)
    
    # ON CONFLICT references unique constraint: (source_code, source_level, duty_column)
    # Note: When hts_version_id is added, we'll migrate this constraint
    upsert_sql = f"""
        INSERT INTO duty_rates (
            id, hts_version_id, hts_code, source_code, duty_column, source_level,
            duty_type, duty_rate_raw_text, duty_rate_structure, duty_rate_numeric,
            duty_confidence, is_free, source_page, effective_start_date, effective_end_date,
            duty_inheritance_chain, trade_program_info, additional_metadata,
            created_at, updated_at
        ) VALUES
            {values_sql}
        ON CONFLICT (source_code, source_level, duty_column)
        DO UPDATE SET
            hts_version_id = EXCLUDED.hts_version_id,
            duty_type = EXCLUDED.duty_type,
            duty_rate_raw_text = EXCLUDED.duty_rate_raw_text,
            duty_rate_structure = EXCLUDED.duty_rate_structure,
            duty_rate_numeric = EXCLUDED.duty_rate_numeric,
            duty_confidence = EXCLUDED.duty_confidence,
            is_free = EXCLUDED.is_free,
            source_page = EXCLUDED.source_page,
            effective_start_date = EXCLUDED.effective_start_date,
            effective_end_date = EXCLUDED.effective_end_date,
            additional_metadata = EXCLUDED.additional_metadata,
            updated_at = now()
        WHERE duty_rates.duty_rate_raw_text IS DISTINCT FROM EXCLUDED.duty_rate_raw_text
           OR duty_rates.duty_rate_structure IS DISTINCT FROM EXCLUDED.duty_rate_structure
           OR duty_rates.duty_rate_numeric IS DISTINCT FROM EXCLUDED.duty_rate_numeric
    """
    
    try:
        # Deduplicate rows by (source_code, source_level, duty_column) to avoid ON CONFLICT errors
        seen_keys = set()
        unique_rows = []
        for row in rows:
            key = (row["source_code"], row["source_level"] if isinstance(row["source_level"], str) else row["source_level"].value, row["duty_column"])
            if key not in seen_keys:
                seen_keys.add(key)
                unique_rows.append(row)
        
        if len(unique_rows) < len(rows):
            # Log if we dropped duplicates
            print(f"  Deduplicated {len(rows) - len(unique_rows)} duplicate rows in batch")
        
        # Use raw SQL with explicit string enum values to avoid SQLAlchemy enum conversion issues
        # Build VALUES clause with positional parameters
        values_clauses = []
        params = []
        param_idx = 1
        
        for row in unique_rows:
            # Ensure enum values are lowercase strings (they should already be from .value)
            source_level_val = str(row["source_level"]) if isinstance(row["source_level"], str) else str(row["source_level"].value)
            duty_type_val = str(row["duty_type"]) if isinstance(row["duty_type"], str) else str(row["duty_type"].value)
            duty_confidence_val = str(row["duty_confidence"]) if isinstance(row["duty_confidence"], str) else str(row["duty_confidence"].value)
            
            # Build VALUES clause - use CAST() function instead of :: syntax for asyncpg compatibility
            values_clauses.append(f"""(
                gen_random_uuid(),
                :param_{param_idx}, :param_{param_idx+1}, :param_{param_idx+2}, :param_{param_idx+3},
                CAST(:param_{param_idx+4} AS dutysourcelevel), CAST(:param_{param_idx+5} AS dutytype), :param_{param_idx+6},
                CAST(:param_{param_idx+7} AS jsonb), :param_{param_idx+8}, CAST(:param_{param_idx+9} AS dutyconfidence),
                :param_{param_idx+10}, :param_{param_idx+11}, :param_{param_idx+12}, :param_{param_idx+13},
                NULL, NULL, CAST(:param_{param_idx+14} AS jsonb),
                now(), now()
            )""")
            
            # Add parameters in order
            params.extend([
                row["hts_version_id"],
                row["hts_code"],
                row["source_code"],
                row["duty_column"],
                source_level_val,  # Explicit lowercase string
                duty_type_val,  # Explicit lowercase string
                row["duty_rate_raw_text"],
                json.dumps(row["duty_rate_structure"]) if row["duty_rate_structure"] else None,
                float(row["duty_rate_numeric"]) if row["duty_rate_numeric"] is not None else None,
                duty_confidence_val,  # Explicit lowercase string
                bool(row["is_free"]),
                str(row.get("source_page")) if row.get("source_page") is not None else None,
                row.get("effective_start_date"),
                row.get("effective_end_date"),
                json.dumps(row.get("additional_metadata")) if row.get("additional_metadata") else None,
            ])
            param_idx += 15
        
        values_sql = ",\n            ".join(values_clauses)
        
        upsert_sql = f"""
            INSERT INTO duty_rates (
                id, hts_version_id, hts_code, source_code, duty_column, source_level,
                duty_type, duty_rate_raw_text, duty_rate_structure, duty_rate_numeric,
                duty_confidence, is_free, source_page, effective_start_date, effective_end_date,
                duty_inheritance_chain, trade_program_info, additional_metadata,
                created_at, updated_at
            ) VALUES
                {values_sql}
            ON CONFLICT (source_code, source_level, duty_column)
            DO UPDATE SET
                hts_version_id = EXCLUDED.hts_version_id,
                duty_type = EXCLUDED.duty_type,
                duty_rate_raw_text = EXCLUDED.duty_rate_raw_text,
                duty_rate_structure = EXCLUDED.duty_rate_structure,
                duty_rate_numeric = EXCLUDED.duty_rate_numeric,
                duty_confidence = EXCLUDED.duty_confidence,
                is_free = EXCLUDED.is_free,
                source_page = EXCLUDED.source_page,
                effective_start_date = EXCLUDED.effective_start_date,
                effective_end_date = EXCLUDED.effective_end_date,
                additional_metadata = EXCLUDED.additional_metadata,
                updated_at = now()
            WHERE duty_rates.duty_rate_raw_text IS DISTINCT FROM EXCLUDED.duty_rate_raw_text
               OR duty_rates.duty_rate_structure IS DISTINCT FROM EXCLUDED.duty_rate_structure
               OR duty_rates.duty_rate_numeric IS DISTINCT FROM EXCLUDED.duty_rate_numeric
        """
        
        # Execute with named parameters (already in SQL as :param_N)
        param_dict = {f"param_{i}": val for i, val in enumerate(params, 1)}
        
        await db.execute(text(upsert_sql), param_dict)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise Exception(f"Batch upsert failed: {e}") from e


async def generate_coverage_report(
    db: AsyncSession,
    hts_version_id: Optional[str],
    stats: Dict[str, Any],
    sample_rows: List[Dict[str, Any]]
) -> str:
    """Generate coverage report markdown."""
    
    total = stats["total_parsed"]
    if total == 0:
        return "# Duty Backfill Coverage Report\n\nNo rows processed.\n"
    
    report = f"""# Duty Backfill Coverage Report

**Generated:** {datetime.utcnow().isoformat()}  
**HTS Version ID:** {hts_version_id or "NULL (latest active)"}

## Summary Statistics

### Counts by Source Level
- **10-digit:** {stats["by_source_level"]["ten_digit"]:,}
- **8-digit:** {stats["by_source_level"]["eight_digit"]:,}
- **6-digit:** {stats["by_source_level"]["six_digit"]:,}

### Counts by Duty Type
"""
    
    for duty_type, count in sorted(stats["by_type"].items(), key=lambda x: x[1], reverse=True):
        pct = (count / total * 100) if total > 0 else 0
        report += f"- **{duty_type}:** {count:,} ({pct:.2f}%)\n"
    
    report += f"""
### Percentages
- **Numeric Computable:** {stats["numeric_computable"]:,} ({(stats["numeric_computable"] / total * 100) if total > 0 else 0:.2f}%)
- **Free:** {stats["free_count"]:,} ({(stats["free_count"] / total * 100) if total > 0 else 0:.2f}%)
- **Compound:** {stats["compound_count"]:,} ({(stats["compound_count"] / total * 100) if total > 0 else 0:.2f}%)
- **Conditional:** {stats["conditional_count"]:,} ({(stats["conditional_count"] / total * 100) if total > 0 else 0:.2f}%)
- **Text-Only:** {stats["text_only_count"]:,} ({(stats["text_only_count"] / total * 100) if total > 0 else 0:.2f}%)
- **Missing Duty Text:** {stats["missing_duty_text"]:,} ({(stats["missing_duty_text"] / total * 100) if total > 0 else 0:.2f}%)

### Confidence Distribution
"""
    
    for conf, count in sorted(stats["by_confidence"].items(), key=lambda x: x[1], reverse=True):
        pct = (count / total * 100) if total > 0 else 0
        report += f"- **{conf}:** {count:,} ({pct:.2f}%)\n"
    
    # Top 20 unparsed patterns
    report += "\n## Top 20 Unparsed Patterns (Text-Only Duties)\n\n"
    top_patterns = sorted(stats["unparsed_patterns"].items(), key=lambda x: x[1], reverse=True)[:20]
    if top_patterns:
        for pattern, count in top_patterns:
            report += f"- `{pattern[:100]}`: {count} occurrences\n"
    else:
        report += "No unparsed patterns found.\n"
    
    # Sample rows
    report += "\n## 20 Random Sample Rows\n\n"
    report += "| source_code | raw_text (first 100 chars) | duty_type | confidence | numeric | structure_summary |\n"
    report += "|------------|----------------------------|-----------|------------|---------|-------------------|\n"
    
    display_samples = random.sample(sample_rows, min(20, len(sample_rows))) if len(sample_rows) > 20 else sample_rows[:20]
    
    for sample in display_samples:
        raw_text_preview = (sample.get("raw_text") or "")[:100] if sample.get("raw_text") else "NULL"
        structure_summary = str(sample.get("structure"))[:80] if sample.get("structure") else "NULL"
        numeric_val = sample.get("numeric")
        numeric_str = f"{numeric_val:.4f}" if numeric_val is not None else "NULL"
        report += f"| {sample.get('source_code', '')} | {raw_text_preview[:100]} | {sample.get('duty_type', '')} | {sample.get('confidence', '')} | {numeric_str} | {structure_summary[:80]} |\n"
    
    return report


async def main():
    parser = argparse.ArgumentParser(description="Backfill duty_rates from hts_versions")
    parser.add_argument("--hts-version-id", type=str, default=None, help="HTS version ID (default: latest active)")
    parser.add_argument("--levels", type=str, default="10", help="Comma-separated levels: 10,8,6 (default: 10)")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch size for processing (default: 250, max recommended: 250 due to SQL parameter limits)")
    parser.add_argument("--duty-column", type=str, default="general", choices=["general", "special", "column2"], help="Duty column to process (default: general)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database writes)")
    
    args = parser.parse_args()
    
    # Parse levels
    levels = [int(l.strip()) for l in args.levels.split(",") if l.strip().isdigit()]
    if not levels:
        print("Error: No valid levels specified")
        return 1
    
    print(f"Starting duty rates backfill...")
    print(f"  HTS Version ID: {args.hts_version_id or 'NULL (latest active)'}")
    print(f"  Levels: {levels}")
    print(f"  Duty Column: {args.duty_column}")
    print(f"  Batch Size: {args.batch_size}")
    print(f"  Dry Run: {args.dry_run}")
    print()
    
    # Initialize parser
    duty_parser = DutyParser()
    
    # Initialize stats
    stats = {
        "total_parsed": 0,
        "upserted_count": 0,
        "skipped_invalid_code": 0,
        "missing_duty_text": 0,
        "free_count": 0,
        "numeric_computable": 0,
        "compound_count": 0,
        "conditional_count": 0,
        "text_only_count": 0,
        "by_type": Counter(),
        "by_confidence": Counter(),
        "by_source_level": Counter(),
        "unparsed_patterns": Counter(),
    }
    
    sample_rows = []
    start_time = datetime.utcnow()
    
    # Create async engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get hts_version_id if not provided
        hts_version_id = args.hts_version_id if args.hts_version_id else await get_latest_hts_version_id(db)
        
        offset = 0
        batch_num = 0
        
        while True:
            batch_num += 1
            batch_start = datetime.utcnow()
            print(f"Processing batch {batch_num} (offset {offset})...", end=" ", flush=True)
            
            hts_rows, has_more = await fetch_hts_nodes(db, hts_version_id, levels, args.duty_column, args.batch_size, offset)
            
            if not hts_rows:
                break
            
            # Process batch
            await process_batch(db, duty_parser, hts_rows, hts_version_id, args.duty_column, args.dry_run, stats)
            
                    # Collect samples (random sampling across batches)
            for row in random.sample(hts_rows, min(3, len(hts_rows))):  # Sample 3 random rows per batch
                duty_text = get_canonical_duty_text(row, args.duty_column)
                if duty_text:
                    parsed = duty_parser.parse_duty_rate(duty_text)
                    sample_rows.append({
                        "source_code": normalize_hts_code(row["hts_code"]),
                        "raw_text": parsed.raw_text,
                        "duty_type": parsed.duty_type.value,
                        "confidence": parsed.duty_confidence.value,
                        "numeric": parsed.numeric_value,
                        "structure": parsed.structure,
                    })
            
            batch_duration = (datetime.utcnow() - batch_start).total_seconds()
            print(f"Processed {len(hts_rows)} rows in {batch_duration:.2f}s (total: {stats['total_parsed']:,})")
            
            # Progress logging every N batches
            if batch_num % 10 == 0:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                rate = stats['total_parsed'] / elapsed if elapsed > 0 else 0
                print(f"  Progress: {stats['total_parsed']:,} rows processed, {rate:.0f} rows/sec")
            
            if not has_more:
                break
            
            offset += args.batch_size
        
        # Generate report
        report = await generate_coverage_report(db, hts_version_id, stats, sample_rows)
        
        # Write report
        report_path = Path(__file__).parent.parent / "DUTY_BACKFILL_REPORT.md"
        report_path.write_text(report)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        print()
        print("=" * 80)
        print("Backfill Complete")
        print("=" * 80)
        print(f"Total rows processed: {stats['total_parsed']:,}")
        print(f"Rows upserted: {stats['upserted_count']:,}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Report saved to: {report_path}")
        print("=" * 80)
    
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
