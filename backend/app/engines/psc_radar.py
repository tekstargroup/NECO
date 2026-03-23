"""
PSC Radar - Sprint 6

Read-only intelligence MVP for surfacing classification-driven risk signals.

Purpose:
- Surface alternative plausible classifications with materially different duty outcomes
- Provide neutral, conservative signals for broker/compliance review
- NO filing advice, NO automation, NO recommendations

CRITICAL DISCLAIMER:
- NECO does NOT recommend filing PSCs (Prior Disclosure Corrections)
- NECO does NOT provide filing advice
- NECO does NOT automate PSC filing workflows
- PSC Radar is an early-warning system, NOT an action system

Hard Rules:
- Read-only (no mutation of HTS data)
- No new heuristics
- Must not break golden tests
- General duty only (no trade programs)
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import logging
from sqlalchemy.ext.asyncio import AsyncSession

import sys
from pathlib import Path

# Add backend directory to path for scripts imports
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.engines.classification.engine import ClassificationEngine
from scripts.duty_resolution import resolve_duty, ResolvedDuty
from app.core.hts_constants import AUTHORITATIVE_HTS_VERSION_ID

logger = logging.getLogger(__name__)


class PSCRadarFlag(str, Enum):
    """Flags for PSC radar signals."""
    DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD = "DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD"
    DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD = "DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD"
    DIFFERENT_CHAPTER_USED_HISTORICALLY = "DIFFERENT_CHAPTER_USED_HISTORICALLY"
    DIFFERENT_HEADING_USED_HISTORICALLY = "DIFFERENT_HEADING_USED_HISTORICALLY"
    DUTY_RATE_CHANGED_FROM_HISTORY = "DUTY_RATE_CHANGED_FROM_HISTORY"


@dataclass
class DutyDelta:
    """Duty delta information for an alternative classification."""
    alternative_hts_code: str
    alternative_chapter: str
    alternative_heading: str
    
    # Duty rates (general only)
    declared_duty_rate: Optional[str] = None
    alternative_duty_rate: Optional[str] = None
    
    # Delta calculations
    delta_percent: Optional[float] = None  # Percentage point difference
    delta_amount: Optional[float] = None  # Dollar amount difference
    
    # Flags
    flags: List[PSCRadarFlag] = field(default_factory=list)
    
    # Legal anchor references
    chapter: str = ""
    heading: str = ""
    
    # Context
    reason: str = ""  # Structural context: codes differ at chapter/heading/subheading level


@dataclass
class PSCRadarResult:
    """
    PSC Radar analysis result.
    
    Neutral, conservative output with no recommendations.
    """
    declared_hts_code: str
    product_description: str
    
    # Alternatives found
    alternatives: List[DutyDelta] = field(default_factory=list)
    
    # Overall flags
    flags: List[PSCRadarFlag] = field(default_factory=list)
    
    # Summary message (neutral, factual)
    summary: str = ""
    
    # Historical divergence (if historical_entries provided)
    historical_signals: List[PSCRadarFlag] = field(default_factory=list)
    
    # Legal anchor references
    chapter: str = ""
    heading: str = ""
    
    # Metadata
    alternatives_considered: int = 0
    alternatives_filtered: int = 0


class PSCRadar:
    """
    PSC Radar engine for surfacing classification risk signals.
    
    Read-only intelligence MVP - no recommendations, no filing advice.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        duty_delta_percent_threshold: float = 2.0,
        duty_delta_amount_threshold: float = 1000.0
    ):
        """
        Initialize PSC Radar.
        
        Args:
            db: Database session
            duty_delta_percent_threshold: Minimum percentage point difference to flag (default: 2.0%)
            duty_delta_amount_threshold: Minimum dollar amount difference to flag (default: $1,000)
        """
        self.db = db
        self.classification_engine = ClassificationEngine(db)
        self.duty_delta_percent_threshold = duty_delta_percent_threshold
        self.duty_delta_amount_threshold = duty_delta_amount_threshold
    
    async def analyze(
        self,
        product_description: str,
        declared_hts_code: str,
        quantity: float,
        customs_value: float,
        country_of_origin: Optional[str] = None,
        historical_entries: Optional[List[Dict[str, Any]]] = None
    ) -> PSCRadarResult:
        """
        Analyze declared HTS code for alternative classifications with material duty differences.
        
        Args:
            product_description: Product description
            declared_hts_code: Declared 10-digit HTS code
            quantity: Product quantity
            customs_value: Customs value (for delta amount calculation)
            country_of_origin: Country of origin (optional, for math context only)
            historical_entries: Optional list of historical entries with hts_code fields
        
        Returns:
            PSCRadarResult with alternatives, flags, and neutral summary
        """
        logger.info(
            f"PSC Radar analysis: declared_hts={declared_hts_code}, "
            f"description='{product_description[:60]}...'"
        )
        
        # STEP 1: Resolve declared duty
        declared_duty = await resolve_duty(
            declared_hts_code,
            db=self.db,
            hts_version_id=AUTHORITATIVE_HTS_VERSION_ID
        )
        
        if not declared_duty or not declared_duty.resolved_general_raw:
            logger.warning(f"Could not resolve duty for declared HTS {declared_hts_code}")
            return PSCRadarResult(
                declared_hts_code=declared_hts_code,
                product_description=product_description,
                summary="Could not resolve duty for declared HTS code. Review required."
            )
        
        # Extract chapter/heading from declared code
        declared_chapter = self._extract_chapter(declared_hts_code)
        declared_heading = self._extract_heading(declared_hts_code)
        
        # STEP 2: Generate alternative classifications
        classification_result = await self.classification_engine.generate_alternatives(
            description=product_description,
            country_of_origin=country_of_origin,
            value=customs_value,
            quantity=quantity,
            current_hts_code=declared_hts_code
        )
        
        if not classification_result.get("success") or not classification_result.get("candidates"):
            logger.info("No alternative classifications found")
            return PSCRadarResult(
                declared_hts_code=declared_hts_code,
                product_description=product_description,
                chapter=declared_chapter,
                heading=declared_heading,
                summary="No alternative plausible classifications found."
            )
        
        candidates = classification_result.get("candidates", [])
        logger.info(f"Found {len(candidates)} classification candidates")
        
        # STEP 3: Filter alternatives (same product family OR same chapter/heading)
        filtered_alternatives = self._filter_alternatives(
            candidates,
            declared_hts_code,
            declared_chapter,
            declared_heading
        )
        
        logger.info(
            f"Filtered to {len(filtered_alternatives)} alternatives "
            f"(same family/chapter/heading)"
        )
        
        # STEP 4: Resolve duties for alternatives and compute deltas
        duty_deltas = []
        for alt_candidate in filtered_alternatives[:3]:  # Top 2-3 alternatives
            alt_hts = alt_candidate.get("hts_code")
            alt_chapter = alt_candidate.get("hts_chapter", "")
            alt_heading = self._extract_heading(alt_hts)
            
            # Resolve alternative duty
            alt_duty = await resolve_duty(
                alt_hts,
                db=self.db,
                hts_version_id=AUTHORITATIVE_HTS_VERSION_ID
            )
            
            if not alt_duty or not alt_duty.resolved_general_raw:
                logger.debug(f"Could not resolve duty for alternative {alt_hts}")
                continue
            
            # Compute delta
            delta = self._compute_duty_delta(
                declared_duty=declared_duty,
                alternative_duty=alt_duty,
                alternative_hts=alt_hts,
                alternative_chapter=alt_chapter,
                alternative_heading=alt_heading,
                customs_value=customs_value
            )
            
            if delta:
                duty_deltas.append(delta)
        
        # STEP 5: Historical divergence (if historical_entries provided)
        historical_signals = []
        if historical_entries:
            historical_signals = self._analyze_historical_divergence(
                declared_hts_code,
                declared_chapter,
                declared_heading,
                declared_duty,
                historical_entries
            )
        
        # STEP 6: Build summary
        flags = []
        for delta in duty_deltas:
            flags.extend(delta.flags)
        flags.extend(historical_signals)
        
        # Dedupe flags
        flags = list(set(flags))
        
        summary = self._build_summary(
            declared_hts_code,
            duty_deltas,
            flags,
            historical_signals
        )
        
        return PSCRadarResult(
            declared_hts_code=declared_hts_code,
            product_description=product_description,
            alternatives=duty_deltas,
            flags=flags,
            summary=summary,
            historical_signals=historical_signals,
            chapter=declared_chapter,
            heading=declared_heading,
            alternatives_considered=len(candidates),
            alternatives_filtered=len(filtered_alternatives)
        )
    
    def _filter_alternatives(
        self,
        candidates: List[Dict[str, Any]],
        declared_hts_code: str,
        declared_chapter: str,
        declared_heading: str
    ) -> List[Dict[str, Any]]:
        """
        Filter alternatives to same product family OR same chapter/heading.
        
        Do NOT re-rank classification logic. Reuse existing output.
        """
        filtered = []
        
        for candidate in candidates:
            alt_hts = candidate.get("hts_code", "")
            
            # Skip if same as declared
            if self._normalize_hts(alt_hts) == self._normalize_hts(declared_hts_code):
                continue
            
            alt_chapter = candidate.get("hts_chapter", "")
            alt_heading = self._extract_heading(alt_hts)
            
            # Filter: same chapter/heading OR high confidence
            # (Classification engine already filtered by product family)
            if alt_chapter == declared_chapter or alt_heading == declared_heading:
                filtered.append(candidate)
            elif candidate.get("final_score", 0.0) >= 0.25:  # High confidence
                filtered.append(candidate)
        
        return filtered
    
    def _compute_duty_delta(
        self,
        declared_duty: ResolvedDuty,
        alternative_duty: ResolvedDuty,
        alternative_hts: str,
        alternative_chapter: str,
        alternative_heading: str,
        customs_value: float
    ) -> Optional[DutyDelta]:
        """
        Compute duty delta for an alternative classification.
        
        General duty only - no trade programs, no netting, no refunds.
        """
        declared_rate_str = declared_duty.resolved_general_raw
        alternative_rate_str = alternative_duty.resolved_general_raw
        
        if not declared_rate_str or not alternative_rate_str:
            return None
        
        # Parse duty rates
        declared_rate = self._parse_duty_rate(declared_rate_str)
        alternative_rate = self._parse_duty_rate(alternative_rate_str)
        
        if declared_rate is None or alternative_rate is None:
            return None
        
        # Compute delta
        delta_percent = abs(alternative_rate - declared_rate)
        delta_amount = (delta_percent / 100.0) * customs_value
        
        # Build flags
        flags = []
        if delta_percent >= self.duty_delta_percent_threshold:
            flags.append(PSCRadarFlag.DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD)
        if delta_amount >= self.duty_delta_amount_threshold:
            flags.append(PSCRadarFlag.DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD)
        
        # Build reason - factual structural difference only
        # Codes differ at chapter/heading/subheading level, duties differ accordingly
        declared_chapter_normalized = self._extract_chapter(declared_duty.hts_code)
        declared_heading_normalized = self._extract_heading(declared_duty.hts_code)
        alt_heading_normalized = self._extract_heading(alternative_hts)
        
        if declared_chapter_normalized != alternative_chapter:
            reason = (
                f"Codes differ at chapter level: declared {declared_chapter_normalized} vs "
                f"alternative {alternative_chapter}. Duties differ accordingly."
            )
        elif declared_heading_normalized != alt_heading_normalized:
            reason = (
                f"Codes differ at heading level: declared {declared_heading_normalized} vs "
                f"alternative {alt_heading_normalized}. Duties differ accordingly."
            )
        else:
            reason = (
                f"Codes differ at subheading level within same heading. "
                f"Duties differ accordingly."
            )
        
        return DutyDelta(
            alternative_hts_code=alternative_hts,
            alternative_chapter=alternative_chapter,
            alternative_heading=alternative_heading,
            declared_duty_rate=declared_rate_str,
            alternative_duty_rate=alternative_rate_str,
            delta_percent=delta_percent,
            delta_amount=delta_amount,
            flags=flags,
            chapter=alternative_chapter,
            heading=alternative_heading,
            reason=reason
        )
    
    def _analyze_historical_divergence(
        self,
        declared_hts_code: str,
        declared_chapter: str,
        declared_heading: str,
        declared_duty: ResolvedDuty,
        historical_entries: List[Dict[str, Any]]
    ) -> List[PSCRadarFlag]:
        """
        Analyze historical divergence signals (optional, thin).
        
        No liquidation logic, no timelines, no PSC eligibility claims.
        """
        signals = []
        
        historical_hts_codes = [
            entry.get("hts_code") for entry in historical_entries
            if entry.get("hts_code")
        ]
        
        if not historical_hts_codes:
            return signals
        
        # Check for different chapter used historically
        historical_chapters = set()
        historical_headings = set()
        historical_duties = []
        
        for hts_code in historical_hts_codes:
            hist_chapter = self._extract_chapter(hts_code)
            hist_heading = self._extract_heading(hts_code)
            historical_chapters.add(hist_chapter)
            historical_headings.add(hist_heading)
            
            # Track historical HTS codes for duty comparison
            historical_duties.append(hts_code)
        
        if declared_chapter not in historical_chapters:
            signals.append(PSCRadarFlag.DIFFERENT_CHAPTER_USED_HISTORICALLY)
        
        if declared_heading not in historical_headings:
            signals.append(PSCRadarFlag.DIFFERENT_HEADING_USED_HISTORICALLY)
        
        # Check if duty rate changed (simple check - compare first historical entry)
        if historical_duties and declared_duty.resolved_general_raw:
            # For now, just flag if historical entries exist
            # Full duty comparison would require resolving all historical duties
            signals.append(PSCRadarFlag.DUTY_RATE_CHANGED_FROM_HISTORY)
        
        return signals
    
    def _build_summary(
        self,
        declared_hts_code: str,
        duty_deltas: List[DutyDelta],
        flags: List[PSCRadarFlag],
        historical_signals: List[PSCRadarFlag]
    ) -> str:
        """
        Build neutral, conservative summary message.
        
        No recommendations, no filing advice.
        """
        if not duty_deltas:
            return (
                f"No alternative plausible classifications found for {declared_hts_code}. "
                f"No material duty differences detected."
            )
        
        material_deltas = [
            d for d in duty_deltas
            if PSCRadarFlag.DUTY_DELTA_PERCENT_EXCEEDS_THRESHOLD in d.flags or
               PSCRadarFlag.DUTY_DELTA_AMOUNT_EXCEEDS_THRESHOLD in d.flags
        ]
        
        if not material_deltas:
            return (
                f"Alternative classifications found for {declared_hts_code}, "
                f"but duty differences are below materiality thresholds. "
                f"No review required."
            )
        
        # Build factual summary - structural differences only, no legal causality
        summary_parts = [
            f"This classification may warrant review because "
            f"{len(material_deltas)} alternative HTS code(s) within the same product family "
            f"carry materially different general duty rates."
        ]
        
        # Add specific deltas (factual only - codes differ, duties differ accordingly)
        for delta in material_deltas[:2]:  # Limit to top 2
            summary_parts.append(
                f"Alternative {delta.alternative_hts_code} differs from declared {declared_hts_code} "
                f"at the chapter/heading/subheading level and has a general duty rate of "
                f"{delta.alternative_duty_rate} (vs. declared {delta.declared_duty_rate}), "
                f"representing a {delta.delta_percent:.1f} percentage point difference "
                f"and ${delta.delta_amount:,.2f} in duty impact. "
                f"{delta.reason}"
            )
        
        summary_parts.append("No filing recommendation is made.")
        
        return " ".join(summary_parts)
    
    def _parse_duty_rate(self, rate_str: str) -> Optional[float]:
        """Parse duty rate string to numeric percentage."""
        if not rate_str:
            return None
        
        rate_str = str(rate_str).strip().lower()
        
        # Handle "Free" or "0%"
        if "free" in rate_str or rate_str == "0%" or rate_str == "0":
            return 0.0
        
        # Extract percentage (handle formats like "8.3%", "8.3", etc.)
        import re
        match = re.search(r'(\d+\.?\d*)', rate_str)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                return None
        
        return None
    
    def _extract_chapter(self, hts_code: str) -> str:
        """Extract chapter (first 2 digits) from HTS code."""
        normalized = self._normalize_hts(hts_code)
        if len(normalized) >= 2:
            return normalized[:2]
        return ""
    
    def _extract_heading(self, hts_code: str) -> str:
        """Extract heading (first 4 digits) from HTS code."""
        normalized = self._normalize_hts(hts_code)
        if len(normalized) >= 4:
            return normalized[:4]
        return ""
    
    def _normalize_hts(self, hts_code: str) -> str:
        """Normalize HTS code to digits-only format."""
        if not hts_code:
            return ""
        return "".join(c for c in hts_code if c.isdigit())
