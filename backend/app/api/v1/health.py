"""
Health Check Endpoints

Provides system health and HTS data quality metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Dict, Any

from app.core.database import get_db
from app.api.dependencies import get_current_client

router = APIRouter()


@router.get("/knowledge-base")
async def get_knowledge_base_health(
    db: AsyncSession = Depends(get_db),
    current_client = Depends(get_current_client)
) -> Dict[str, Any]:
    """
    Knowledge Base Health Check
    
    Returns comprehensive health metrics for the entire knowledge base:
    - HTS data (records, codes, duty rates, confidence)
    - CFR regulations
    - Entry Summary guide
    - HTS headings
    - ACE sections
    """
    
    # HTS Data
    result = await db.execute(text("SELECT COUNT(*) FROM hts_versions"))
    total_hts_records = result.scalar()
    
    result = await db.execute(text("SELECT COUNT(DISTINCT hts_code) FROM hts_versions"))
    distinct_hts_codes = result.scalar()
    
    result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_general IS NOT NULL"))
    with_general = result.scalar()
    
    result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_special IS NOT NULL"))
    with_special = result.scalar()
    
    result = await db.execute(text("SELECT COUNT(*) FROM hts_versions WHERE duty_rate_column2 IS NOT NULL"))
    with_column2 = result.scalar()
    
    result = await db.execute(text("""
        SELECT parse_confidence, COUNT(*) as count
        FROM hts_versions
        GROUP BY parse_confidence
    """))
    confidence_dist = {row[0].value if row[0] else "NULL": row[1] for row in result.all()}
    
    # CFR Regulations
    result = await db.execute(text("SELECT COUNT(*) FROM customs_regulations"))
    cfr_sections = result.scalar()
    
    # Entry Summary Guide
    result = await db.execute(text("SELECT COUNT(*) FROM entry_summary_guide"))
    es_fields = result.scalar()
    
    # HTS Headings
    result = await db.execute(text("SELECT COUNT(*) FROM hts_headings_docs"))
    headings_count = result.scalar()
    
    # ACE Instructions
    result = await db.execute(text("SELECT COUNT(*) FROM ace_instructions"))
    ace_instructions_count = result.scalar()
    
    # ACE BRPD
    result = await db.execute(text("SELECT COUNT(*) FROM ace_brpd"))
    ace_brpd_count = result.scalar()
    
    ace_total = ace_instructions_count + ace_brpd_count
    
    return {
        "status": "healthy",
        "knowledge_base": {
            "hts_data": {
                "total_records": total_hts_records,
                "distinct_codes": distinct_hts_codes,
                "duty_rate_coverage": {
                    "general": {
                        "count": with_general,
                        "percentage": round(with_general / total_hts_records * 100, 2) if total_hts_records > 0 else 0
                    },
                    "special": {
                        "count": with_special,
                        "percentage": round(with_special / total_hts_records * 100, 2) if total_hts_records > 0 else 0
                    },
                    "column2": {
                        "count": with_column2,
                        "percentage": round(with_column2 / total_hts_records * 100, 2) if total_hts_records > 0 else 0
                    }
                },
                "parse_confidence": confidence_dist
            },
            "cfr_regulations": {
                "section_count": cfr_sections
            },
            "entry_summary_guide": {
                "field_count": es_fields
            },
            "hts_headings": {
                "heading_count": headings_count
            },
            "ace_sections": {
                "instructions": ace_instructions_count,
                "brpd": ace_brpd_count,
                "total": ace_total
            }
        },
        "timestamp": date.today().isoformat()
    }

