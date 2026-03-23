"""
Classification Context Builder

Builds comprehensive context for classification candidates using:
- HTS versions (tariff text, duty rates, special countries)
- CFR regulations (general rules, chapter-specific)
- HTS headings documentation
- Entry Summary guide requirements

Ensures LLM only sees trusted internal data, never open web.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import date
from sqlalchemy import select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ClassificationContextBuilder:
    """
    Builds context for classification candidates from trusted internal sources.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def build_context(
        self,
        hts_code: str,
        hts_heading_6: Optional[str] = None,
        hts_chapter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for a candidate HTS code.
        
        Args:
            hts_code: 10-digit HTS code
            hts_heading_6: 6-digit heading (optional, for fallback)
            hts_chapter: 2-digit chapter (optional, for fallback)
        
        Returns:
            Compact context JSON with all relevant data
        """
        context = {
            "hts_code": hts_code,
            "hts_heading_6": hts_heading_6 or hts_code[:6] if len(hts_code) >= 6 else None,
            "hts_chapter": hts_chapter or hts_code[:2] if len(hts_code) >= 2 else None,
            "hts_data": None,
            "cfr_regulations": [],
            "hts_heading": None,
            "entry_summary_guidance": None,
            "data_completeness": {
                "hts_found": False,
                "cfr_found": False,
                "heading_found": False,
                "es_guide_found": False
            }
        }
        
        # 1. Get HTS version data
        hts_data = await self._get_hts_data(hts_code, hts_heading_6, hts_chapter)
        if hts_data:
            context["hts_data"] = hts_data
            context["data_completeness"]["hts_found"] = True
        
        # 2. Get CFR regulations
        cfr_sections = await self._get_cfr_regulations(
            hts_chapter=context["hts_chapter"],
            hts_heading_6=context["hts_heading_6"]
        )
        if cfr_sections:
            context["cfr_regulations"] = cfr_sections
            context["data_completeness"]["cfr_found"] = True
        
        # 3. Get HTS heading description
        heading_data = await self._get_hts_heading(context["hts_heading_6"])
        if heading_data:
            context["hts_heading"] = heading_data
            context["data_completeness"]["heading_found"] = True
        
        # 4. Get Entry Summary guide requirements
        es_guidance = await self._get_entry_summary_guidance()
        if es_guidance:
            context["entry_summary_guidance"] = es_guidance
            context["data_completeness"]["es_guide_found"] = True
        
        return context
    
    async def _get_hts_data(
        self,
        hts_code: str,
        hts_heading_6: Optional[str],
        hts_chapter: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get HTS version data including:
        - tariff_text
        - all three duty columns
        - special countries
        - effective dates
        - parse_confidence
        """
        today = date.today()
        
        # Try exact 10-digit match first
        result = await self.db.execute(text("""
            SELECT 
                hts_code,
                tariff_text,
                duty_rate_general,
                duty_rate_special,
                duty_rate_column2,
                special_countries,
                effective_from,
                effective_to,
                parse_confidence,
                source_page
            FROM hts_versions
            WHERE hts_code = :hts_code
              AND effective_from <= :today
              AND (effective_to IS NULL OR effective_to >= :today)
              AND parse_confidence != 'low'
            ORDER BY effective_from DESC
            LIMIT 1
        """), {
            "hts_code": hts_code,
            "today": today
        })
        
        row = result.first()
        if row:
            return {
                "hts_code": row[0],
                "tariff_text": row[1],
                "duty_rate_general": row[2],
                "duty_rate_special": row[3],
                "duty_rate_column2": row[4],
                "special_countries": row[5] or [],
                "effective_from": row[6].isoformat() if row[6] else None,
                "effective_to": row[7].isoformat() if row[7] else None,
                "parse_confidence": str(row[8]) if row[8] else None,
                "source_page": row[9]
            }
        
        # Fallback to 6-digit heading
        if hts_heading_6:
            result = await self.db.execute(text("""
                SELECT 
                    hts_code,
                    tariff_text,
                    duty_rate_general,
                    duty_rate_special,
                    duty_rate_column2,
                    special_countries,
                    effective_from,
                    effective_to,
                    parse_confidence,
                    source_page
                FROM hts_versions
                WHERE hts_heading_6 = :heading
                  AND effective_from <= :today
                  AND (effective_to IS NULL OR effective_to >= :today)
                  AND parse_confidence != 'low'
                ORDER BY effective_from DESC
                LIMIT 1
            """), {
                "heading": hts_heading_6,
                "today": today
            })
            
            row = result.first()
            if row:
                return {
                    "hts_code": row[0],
                    "tariff_text": row[1],
                    "duty_rate_general": row[2],
                    "duty_rate_special": row[3],
                    "duty_rate_column2": row[4],
                    "special_countries": row[5] or [],
                    "effective_from": row[6].isoformat() if row[6] else None,
                    "effective_to": row[7].isoformat() if row[7] else None,
                    "parse_confidence": str(row[8]) if row[8] else None,
                    "source_page": row[9]
                }
        
        # Fallback to 2-digit chapter
        if hts_chapter:
            result = await self.db.execute(text("""
                SELECT 
                    hts_code,
                    tariff_text,
                    duty_rate_general,
                    duty_rate_special,
                    duty_rate_column2,
                    special_countries,
                    effective_from,
                    effective_to,
                    parse_confidence,
                    source_page
                FROM hts_versions
                WHERE hts_chapter = :chapter
                  AND effective_from <= :today
                  AND (effective_to IS NULL OR effective_to >= :today)
                  AND parse_confidence != 'low'
                ORDER BY effective_from DESC
                LIMIT 1
            """), {
                "chapter": hts_chapter,
                "today": today
            })
            
            row = result.first()
            if row:
                return {
                    "hts_code": row[0],
                    "tariff_text": row[1],
                    "duty_rate_general": row[2],
                    "duty_rate_special": row[3],
                    "duty_rate_column2": row[4],
                    "special_countries": row[5] or [],
                    "effective_from": row[6].isoformat() if row[6] else None,
                    "effective_to": row[7].isoformat() if row[7] else None,
                    "parse_confidence": str(row[8]) if row[8] else None,
                    "source_page": row[9]
                }
        
        return None
    
    async def _get_cfr_regulations(
        self,
        hts_chapter: Optional[str] = None,
        hts_heading_6: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant CFR regulations:
        - General interpretation rules (always included)
        - Chapter-specific sections (if chapter provided)
        """
        regulations = []
        
        # 1. General interpretation rules (sections 152.101-152.106)
        result = await self.db.execute(text("""
            SELECT section_number, subsection, title, full_text
            FROM customs_regulations
            WHERE section_number LIKE '152.10%'
              AND full_text IS NOT NULL
            ORDER BY section_number, subsection
            LIMIT 10
        """))
        
        for row in result.all():
            regulations.append({
                "section": row[0],
                "subsection": row[1],
                "title": row[2],
                "text": row[3][:2000] if row[3] and len(row[3]) > 2000 else row[3]  # Truncate for context
            })
        
        # 2. Chapter-specific sections (simple mapping: chapter number to CFR chapter)
        if hts_chapter:
            # Map HTS chapter to CFR chapter (simplified - can be enhanced)
            # For now, get sections that mention the chapter
            result = await self.db.execute(text("""
                SELECT section_number, subsection, title, full_text
                FROM customs_regulations
                WHERE full_text LIKE :chapter_pattern
                  AND full_text IS NOT NULL
                ORDER BY section_number
                LIMIT 5
            """), {
                "chapter_pattern": f"%Chapter {hts_chapter}%"
            })
            
            for row in result.all():
                regulations.append({
                    "section": row[0],
                    "subsection": row[1],
                    "title": row[2],
                    "text": row[3][:2000] if row[3] and len(row[3]) > 2000 else row[3]
                })
        
        return regulations
    
    async def _get_hts_heading(self, hts_heading_6: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Get HTS heading description from hts_headings_docs.
        """
        if not hts_heading_6:
            return None
        
        # Extract 4-digit heading from 6-digit
        heading_4 = hts_heading_6[:4] if len(hts_heading_6) >= 4 else None
        if not heading_4:
            return None
        
        result = await self.db.execute(text("""
            SELECT heading, description, full_text
            FROM hts_headings_docs
            WHERE heading = :heading
            LIMIT 1
        """), {
            "heading": heading_4
        })
        
        row = result.first()
        if row:
            return {
                "heading": row[0],
                "description": row[1],
                "full_text": row[2]
            }
        
        return None
    
    async def _get_entry_summary_guidance(self) -> Optional[Dict[str, Any]]:
        """
        Get Entry Summary guide requirements, particularly for description field.
        """
        # Get Column 28 (Description of Merchandise) guidance
        result = await self.db.execute(text("""
            SELECT field_type, field_number, title, description
            FROM entry_summary_guide
            WHERE field_type = 'column' AND field_number = '28'
            LIMIT 1
        """))
        
        row = result.first()
        if row:
            return {
                "field": f"{row[0]} {row[1]}",
                "title": row[2],
                "description": row[3]
            }
        
        return None
    
    def build_compact_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a compact, LLM-ready context JSON from the full context.
        This is what gets stored in classification_audit.context_payload.
        """
        compact = {
            "hts_code": context.get("hts_code"),
            "hts_data": context.get("hts_data"),
            "cfr_summary": [
                {
                    "section": r.get("section"),
                    "title": r.get("title"),
                    "excerpt": r.get("text", "")[:500] if r.get("text") else None
                }
                for r in context.get("cfr_regulations", [])[:5]  # Limit to 5 most relevant
            ],
            "heading_description": context.get("hts_heading", {}).get("description") if context.get("hts_heading") else None,
            "entry_summary_requirement": context.get("entry_summary_guidance", {}).get("description") if context.get("entry_summary_guidance") else None,
            "data_completeness": context.get("data_completeness", {})
        }
        
        return compact


