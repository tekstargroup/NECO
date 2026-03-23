"""
Regenerate and Persist Structured HTS Codes - Sprint 5.1.5

This script:
1. Re-extracts structured HTS codes from the PDF (all levels: 6, 8, 10-digit)
2. Persists them to JSONL file for permanent storage
3. Can be used to populate hts_nodes with complete duty text for all levels

Output: data/hts_tariff/structured_hts_codes.jsonl
"""

import sys
import json
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import pdfplumber
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_hts_code(code: str) -> str:
    """Normalize HTS code to digits only."""
    if not code:
        return ""
    return re.sub(r'[^\d]', '', code)


def extract_hts_code_from_text(text: str) -> Optional[str]:
    """Extract HTS code pattern from text (e.g., 8518.30.10.00 or 8518301000)."""
    # Pattern: 4 digits, optional dot, 2 digits, optional dot, 2 digits, optional dot, 2 digits
    pattern = r'\b(\d{4}(?:\.\d{2}){0,3})\b'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]
    return None


def determine_level(code_normalized: str) -> int:
    """Determine HTS code level from length."""
    if len(code_normalized) == 10:
        return 10
    elif len(code_normalized) == 8:
        return 8
    elif len(code_normalized) == 6:
        return 6
    elif len(code_normalized) == 4:
        return 4
    elif len(code_normalized) == 2:
        return 2
    return 0


def parse_duty_columns(text: str) -> Dict[str, Optional[str]]:
    """
    Parse duty columns from HTS table row.
    
    Returns:
        {
            "duty_general_raw": "...",
            "duty_special_raw": "...",
            "duty_column2_raw": "..."
        }
    """
    # This is a simplified parser - in reality, you'd need to parse the table structure
    # For now, we'll extract what we can from the text
    duties = {
        "duty_general_raw": None,
        "duty_special_raw": None,
        "duty_column2_raw": None,
    }
    
    # Look for percentage patterns, "Free", etc.
    # This is a placeholder - actual parsing would need table structure
    return duties


def extract_structured_codes_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extract structured HTS codes from PDF.
    
    This is a simplified extractor. For production, you'd want to use the original
    comprehensive parser that used LLM/Claude to understand the complex table structure.
    
    Returns list of code objects with all levels (6, 8, 10-digit).
    """
    structured_codes = []
    seen_codes = set()  # Track by (level, normalized_code)
    
    logger.info(f"Extracting structured codes from {pdf_path}")
    logger.warning("⚠️  This is a simplified extractor. For full accuracy, use the original comprehensive parser.")
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"Total pages: {total_pages}")
        
        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num % 100 == 0:
                logger.info(f"Processed {page_num}/{total_pages} pages... Found {len(structured_codes)} codes")
            
            # Extract text
            text = page.extract_text()
            if not text:
                continue
            
            # Extract tables (HTS codes are typically in structured tables)
            tables = page.extract_tables()
            
            # Process tables
            for table_idx, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue
                
                # Process each row (skip header row if present)
                for row_idx, row in enumerate(table):
                    if not row or len(row) < 2:
                        continue
                    
                    # First column typically has HTS code
                    code_text = str(row[0]) if row[0] else ""
                    
                    # Look for HTS code pattern
                    code = extract_hts_code_from_text(code_text)
                    
                    if not code:
                        continue
                    
                    code_normalized = normalize_hts_code(code)
                    level = determine_level(code_normalized)
                    
                    if level == 0 or level not in [6, 8, 10]:
                        continue
                    
                    # Skip if already seen
                    code_key = (level, code_normalized)
                    if code_key in seen_codes:
                        continue
                    seen_codes.add(code_key)
                    
                    # Extract description (typically second column)
                    description = str(row[1]) if len(row) > 1 and row[1] else ""
                    description = description.strip() if description else ""
                    
                    # Extract duty columns
                    # HTS tables typically have: Code | Description | General | Special | Column 2
                    duty_general = str(row[2]).strip() if len(row) > 2 and row[2] else None
                    duty_special = str(row[3]).strip() if len(row) > 3 and row[3] else None
                    duty_column2 = str(row[4]).strip() if len(row) > 4 and row[4] else None
                    
                    # Clean duty text (remove None strings)
                    if duty_general == "None" or not duty_general:
                        duty_general = None
                    if duty_special == "None" or not duty_special:
                        duty_special = None
                    if duty_column2 == "None" or not duty_column2:
                        duty_column2 = None
                    
                    # Determine parent codes
                    parent_8 = code_normalized[:8] if len(code_normalized) >= 8 else None
                    parent_6 = code_normalized[:6] if len(code_normalized) >= 6 else None
                    
                    code_obj = {
                        "code_normalized": code_normalized,
                        "code_display": code,
                        "level": level,
                        "parent_code_normalized": parent_8 if level == 10 else (parent_6 if level == 8 else None),
                        "description_short": description[:200] if description else None,
                        "description_long": description if description else None,
                        "duty_general_raw": duty_general,
                        "duty_special_raw": duty_special,
                        "duty_column2_raw": duty_column2,
                        "source_lineage": {
                            "source_page": page_num,
                            "table_index": table_idx,
                            "row_index": row_idx,
                            "extracted_at": datetime.utcnow().isoformat(),
                            "extraction_method": "table_parsing",
                        },
                    }
                    
                    structured_codes.append(code_obj)
            
            # Also process text directly for codes not in tables
            # Look for HTS code patterns in running text
            text_codes = re.findall(r'\b(\d{4}(?:\.\d{2}){0,3})\b', text)
            for code in text_codes:
                code_normalized = normalize_hts_code(code)
                level = determine_level(code_normalized)
                
                if level == 0 or level not in [6, 8, 10]:
                    continue
                
                code_key = (level, code_normalized)
                if code_key in seen_codes:
                    continue
                seen_codes.add(code_key)
                
                code_obj = {
                    "code_normalized": code_normalized,
                    "code_display": code,
                    "level": level,
                    "parent_code_normalized": code_normalized[:8] if level == 10 else (code_normalized[:6] if level == 8 else None),
                    "description_short": None,
                    "description_long": None,
                    "duty_general_raw": None,
                    "duty_special_raw": None,
                    "duty_column2_raw": None,
                    "source_lineage": {
                        "source_page": page_num,
                        "extracted_at": datetime.utcnow().isoformat(),
                        "extraction_method": "text_extraction",
                    },
                }
                
                structured_codes.append(code_obj)
    
    logger.info(f"✅ Extracted {len(structured_codes)} structured codes")
    return structured_codes


def persist_to_jsonl(codes: List[Dict[str, Any]], output_path: Path):
    """Persist structured codes to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Persisting {len(codes)} codes to {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for code in codes:
            f.write(json.dumps(code, ensure_ascii=False) + '\n')
    
    logger.info(f"✅ Persisted to {output_path}")
    
    # Print summary by level
    by_level = {}
    for code in codes:
        level = code.get("level", 0)
        by_level[level] = by_level.get(level, 0) + 1
    
    logger.info("Summary by level:")
    for level in sorted(by_level.keys()):
        logger.info(f"  Level {level}: {by_level[level]:,} codes")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate and persist structured HTS codes from PDF")
    parser.add_argument("--pdf-path", type=str, help="Path to HTS PDF file (default: auto-detect)")
    parser.add_argument("--output", type=str, default="data/hts_tariff/structured_hts_codes.jsonl",
                        help="Output JSONL file path")
    
    args = parser.parse_args()
    
    # Find PDF file
    if args.pdf_path:
        pdf_path = Path(args.pdf_path)
        if not pdf_path.exists():
            logger.error(f"❌ PDF not found: {pdf_path}")
            return
    else:
        pdf_paths = [
            Path("CBP Docs/2025HTS.pdf"),
            Path("../CBP Docs/2025HTS.pdf"),
            Path("data/hts_tariff/2025HTS.pdf"),
        ]
        
        pdf_path = None
        for path in pdf_paths:
            if path.exists():
                pdf_path = path
                break
        
        if not pdf_path:
            logger.error("❌ HTS PDF not found. Please specify --pdf-path")
            logger.error("Expected locations:")
            for path in pdf_paths:
                logger.error(f"  - {path}")
            return
    
    logger.info(f"📄 Using PDF: {pdf_path}")
    
    # Extract structured codes
    structured_codes = extract_structured_codes_from_pdf(pdf_path)
    
    # Persist to JSONL
    output_path = Path(args.output)
    persist_to_jsonl(structured_codes, output_path)
    
    logger.info("✅ Done! Structured codes persisted to JSONL file.")
    logger.info(f"   File: {output_path.absolute()}")
    logger.info(f"   Total codes: {len(structured_codes):,}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Review the JSONL file to verify extraction quality")
    logger.info("  2. Use scripts/load_structured_codes_to_hts_nodes.py to populate hts_nodes")


if __name__ == "__main__":
    main()
