"""
Signal Scoring Service - Compliance Signal Engine

Relevance scoring: FINAL_SCORE = (HTS_MATCH * 0.35) + (COUNTRY_MATCH * 0.20) + (IMPORTER_HISTORY * 0.25) + (FINANCIAL_IMPACT * 0.20)
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized_signal import NormalizedSignal
from app.models.importer_hts_usage import ImporterHTSUsage
from app.models.shipment import Shipment, ShipmentItem

logger = logging.getLogger(__name__)


async def get_importer_profile(db: AsyncSession, organization_id: UUID) -> Dict[str, Any]:
    """
    Build importer profile from importer_hts_usage and/or ShipmentItem data.

    Returns:
        {
            hts_codes: set of HTS codes used,
            countries: set of country codes (COO),
            total_value: approximate total value,
            hts_frequency: dict hts -> count
        }
    """
    profile = {
        "hts_codes": set(),
        "countries": set(),
        "total_value": 0,
        "hts_frequency": {},
    }

    # From importer_hts_usage table
    result = await db.execute(
        select(ImporterHTSUsage)
        .where(ImporterHTSUsage.organization_id == organization_id)
    )
    for row in result.scalars().all():
        usage = row
        profile["hts_codes"].add(usage.hts_code)
        profile["hts_frequency"][usage.hts_code] = profile["hts_frequency"].get(usage.hts_code, 0) + usage.frequency
        if usage.total_value:
            profile["total_value"] += float(usage.total_value)

    # Fallback: derive from ShipmentItem (shipments in this org)
    if not profile["hts_codes"]:
        result = await db.execute(
            select(ShipmentItem.declared_hts, ShipmentItem.country_of_origin)
            .join(Shipment, ShipmentItem.shipment_id == Shipment.id)
            .where(Shipment.organization_id == organization_id)
            .where(ShipmentItem.declared_hts.isnot(None))
        )
        for row in result.all():
            hts, coo = row
            if hts:
                profile["hts_codes"].add(hts)
                profile["hts_frequency"][hts] = profile["hts_frequency"].get(hts, 0) + 1
            if coo:
                profile["countries"].add(coo)

    return profile


def _hts_match_score(signal_hts: List[str], importer_hts: set) -> float:
    """0-100: Does signal mention HTS used by importer?"""
    if not importer_hts:
        return 50.0  # Neutral when no history
    if not signal_hts:
        return 0.0
    # Normalize: compare first 4 digits
    importer_prefixes = {h[:4] for h in importer_hts}
    for sh in signal_hts:
        prefix = (sh.replace(".", "")[:4]) if sh else ""
        if prefix and prefix in importer_prefixes:
            return 100.0
        # Chapter match (first 2 digits)
        for ih in importer_hts:
            if ih[:2] == sh[:2]:
                return 60.0
    return 0.0


def _country_match_score(signal_countries: List[str], importer_countries: set) -> float:
    """0-100: Does signal affect importer's countries?"""
    if not importer_countries:
        return 50.0
    if not signal_countries:
        return 0.0
    overlap = importer_countries & set(c.upper() for c in signal_countries)
    return 100.0 if overlap else 0.0


def _importer_history_score(signal_hts: List[str], hts_frequency: Dict[str, int]) -> float:
    """0-100: Has importer used affected HTS before?"""
    if not signal_hts or not hts_frequency:
        return 50.0
    for sh in signal_hts:
        prefix = sh.replace(".", "")[:4]
        for hts, freq in hts_frequency.items():
            if hts.replace(".", "")[:4] == prefix and freq > 0:
                return min(100, 50 + freq * 10)
    return 0.0


def _financial_impact_score(signal: Dict[str, Any]) -> float:
    """0-100: Estimate based on duty delta potential (category heuristics)."""
    category = (signal.get("category") or "").upper()
    impact_type = (signal.get("impact_type") or "").lower()
    if "TARIFF" in category or "duty" in impact_type:
        return 80.0
    if "RULING" in category or "HTS" in category:
        return 70.0
    if "QUOTA" in category or "SANCTION" in category:
        return 75.0
    if "RESTRICTION" in category:
        return 65.0
    return 40.0


async def score_signal(
    db: AsyncSession,
    signal: NormalizedSignal,
    organization_id: UUID,
    classification_override: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Compute weighted relevance score for a signal for an organization.

    Formula: FINAL_SCORE = (HTS_MATCH * 0.35) + (COUNTRY_MATCH * 0.20) + (IMPORTER_HISTORY * 0.25) + (FINANCIAL_IMPACT * 0.20)

    Returns:
        final_score 0-100
    """
    profile = await get_importer_profile(db, organization_id)

    signal_hts = list(signal.hts_codes or [])
    signal_countries = list(signal.countries or [])

    # Get category from classification (override or from relationship)
    signal_dict = {"category": None, "impact_type": None}
    if classification_override:
        signal_dict["category"] = classification_override.get("category")
        signal_dict["impact_type"] = classification_override.get("impact_type")
    elif signal.classifications:
        c = signal.classifications[0]
        signal_dict["category"] = c.category.value if hasattr(c.category, "value") else str(c.category)
        signal_dict["impact_type"] = c.impact_type

    hts_match = _hts_match_score(signal_hts, profile["hts_codes"])
    country_match = _country_match_score(signal_countries, profile["countries"])
    importer_history = _importer_history_score(signal_hts, profile["hts_frequency"])
    financial_impact = _financial_impact_score(signal_dict)

    final = (hts_match * 0.35) + (country_match * 0.20) + (importer_history * 0.25) + (financial_impact * 0.20)
    return min(100.0, max(0.0, final))
