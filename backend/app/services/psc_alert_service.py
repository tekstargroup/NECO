"""
PSC Alert Service - Compliance Signal Engine (GAPs 1-9)

Creates PSC alerts when signal final_score > 70.
- GAP 1: Quota alerts when fill_rate > 0.9
- GAP 2: Tariff mapping, link to shipments, compute duty delta
- GAP 3: FDA/import restriction matching
- GAP 4: CBP rulings linkage
- GAP 6: HTS-centric filtering (suppress if no HTS)
- GAP 7: Importer-aware mapping
- GAP 8: Financial impact (duty_delta_estimate)
- GAP 9: Link shipment_id, confidence_score, signal_source, priority
"""

import logging
import re
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.raw_signal import RawSignal
from app.models.normalized_signal import NormalizedSignal
from app.models.signal_classification import SignalClassification, SignalCategory
from app.models.signal_score import SignalScore
from app.models.psc_alert import PSCAlert, PSCAlertStatus
from app.models.shipment import Shipment, ShipmentItem
from app.models.quota_status import QuotaStatus
from app.models.import_restriction import ImportRestriction
from app.models.cbp_ruling import CBPRuling
from app.engines.signal_classification import classify_signal
from app.services.signal_scoring_service import score_signal

logger = logging.getLogger(__name__)

ALERT_THRESHOLD = 70.0
QUOTA_FILL_THRESHOLD = 0.9  # GAP 1: alert when fill_rate > 0.9


def _parse_duty_rate(raw: Optional[str]) -> Optional[float]:
    """Parse duty string (e.g. '4.9%', 'Free') to float rate."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s or s.lower() == "free":
        return 0.0
    m = re.search(r"([\d.]+)\s*%?", s)
    if m:
        return float(m.group(1)) / 100.0
    try:
        return float(re.sub(r"[^\d.-]", "", s))
    except (ValueError, TypeError):
        return None


def _parse_value(val: Any) -> Optional[float]:
    """Parse customs value from string/number."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", "").replace("$", "").strip()
        return float(re.sub(r"[^\d.-]", "", s) or 0)
    except (ValueError, TypeError):
        return None


async def _find_shipments_for_hts(
    db: AsyncSession, organization_id: UUID, hts_code: str
) -> List[Tuple[UUID, UUID, Optional[float]]]:
    """Find (shipment_id, shipment_item_id, value) for org using this HTS."""
    if not hts_code or len(hts_code) < 4:
        return []
    hts_clean = re.sub(r"[^\d]", "", hts_code)[:10]
    hts_prefix = hts_clean[:4]
    result = await db.execute(
        select(ShipmentItem.id, ShipmentItem.shipment_id, ShipmentItem.value, ShipmentItem.declared_hts)
        .join(Shipment, ShipmentItem.shipment_id == Shipment.id)
        .where(Shipment.organization_id == organization_id)
        .where(ShipmentItem.declared_hts.isnot(None))
    )
    out = []
    for row in result.all():
        item_id, ship_id, val, decl_hts = row
        decl_clean = re.sub(r"[^\d]", "", decl_hts or "")[:10]
        if decl_clean.startswith(hts_prefix) or hts_clean.startswith(decl_clean[:4]):
            out.append((ship_id, item_id, _parse_value(val)))
    return out[:10]


async def create_psc_alert(
    db: AsyncSession,
    organization_id: UUID,
    signal_id: UUID,
    raw_source: str,
    hts_code: Optional[str] = None,
    alert_type: str = "regulatory_signal",
    duty_delta_estimate: Optional[str] = None,
    reason: str = "",
    evidence_links: Optional[Dict[str, Any]] = None,
    explanation: Optional[Dict[str, Any]] = None,
    shipment_id: Optional[UUID] = None,
    shipment_item_id: Optional[UUID] = None,
    confidence_score: Optional[float] = None,
    priority: Optional[str] = None,
) -> PSCAlert:
    """Create a PSC alert (GAP 9: full output structure)."""
    alert = PSCAlert(
        organization_id=organization_id,
        signal_id=signal_id,
        shipment_id=shipment_id,
        shipment_item_id=shipment_item_id,
        hts_code=hts_code,
        alert_type=alert_type,
        duty_delta_estimate=duty_delta_estimate,
        reason=reason,
        evidence_links=evidence_links or [],
        status=PSCAlertStatus.NEW,
        explanation=explanation or {},
        confidence_score=confidence_score,
        priority=priority or "MEDIUM",
        signal_source=raw_source,
    )
    db.add(alert)
    return alert


async def process_raw_signals_for_org(
    db: AsyncSession,
    organization_id: UUID,
    raw_signal_ids: Optional[List[UUID]] = None,
    limit: int = 100,
) -> Dict[str, int]:
    """
    Process raw signals: normalize, classify, score, create alerts.
    GAP 6: Suppress signals without HTS (unless fallback extracted some).
    GAP 1: Quota alerts when fill_rate > 0.9
    GAP 2: Tariff mapping, link to shipments, duty delta
    GAP 8: Compute duty_delta_estimate
    GAP 9: Link shipment_id, confidence_score, signal_source
    """
    from app.models.organization import Organization

    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    if not result.scalar_one_or_none():
        return {"normalized": 0, "scored": 0, "alerts_created": 0, "suppressed_no_hts": 0}

    if raw_signal_ids:
        q = select(RawSignal).where(RawSignal.id.in_(raw_signal_ids)).limit(limit)
    else:
        subq = select(NormalizedSignal.raw_signal_id)
        q = select(RawSignal).where(~RawSignal.id.in_(subq)).limit(limit)
    result = await db.execute(q)
    raw_signals = result.scalars().all()

    normalized_count = 0
    scored_count = 0
    alerts_created = 0
    suppressed_no_hts = 0

    for raw in raw_signals:
        classification_result = classify_signal(raw.content or "", raw.title or "")
        hts_codes = classification_result.get("hts_codes") or []
        category = classification_result.get("category", "TRADE_ACTION")

        # GAP 6: Suppress if no HTS (mandatory)
        if not hts_codes:
            # Fallback: use affected_hts_codes or extract from text again
            hts_codes = classification_result.get("affected_hts_codes") or []
        if not hts_codes and category not in ("SANCTION", "DOCUMENTATION_RULE"):
            suppressed_no_hts += 1
            continue

        primary_hts = hts_codes[0] if hts_codes else None
        affected_hts = hts_codes  # GAP 2

        # Build normalized signal with GAP 2/1 fields
        duty_rate_change = classification_result.get("duty_rate_change")
        old_rate = classification_result.get("old_duty_rate")
        new_rate = classification_result.get("new_duty_rate")
        quota_limit = classification_result.get("quota_limit")
        quota_used = classification_result.get("quota_used")

        norm = NormalizedSignal(
            raw_signal_id=raw.id,
            summary=classification_result.get("summary"),
            full_text=(raw.content or "")[:50000],
            signal_type=category,
            countries=classification_result.get("countries"),
            hts_codes=hts_codes,
            keywords=[],
            confidence=classification_result.get("confidence"),
            duty_rate_change=float(duty_rate_change) if duty_rate_change is not None else None,
            affected_hts_codes=affected_hts,
            old_duty_rate=float(old_rate) if old_rate is not None else None,
            new_duty_rate=float(new_rate) if new_rate is not None else None,
            quota_limit=float(quota_limit) if quota_limit is not None else None,
            quota_used=float(quota_used) if quota_used is not None else None,
        )
        db.add(norm)
        await db.flush()
        normalized_count += 1

        # Classification record
        try:
            cat = SignalCategory(category)
        except ValueError:
            cat = SignalCategory.TRADE_ACTION
        sc = SignalClassification(
            signal_id=norm.id,
            category=cat,
            impact_type=classification_result.get("impact_type"),
            affected_entities={"countries": classification_result.get("countries"), "hts": hts_codes},
        )
        db.add(sc)
        await db.flush()

        # GAP 4: CBP CROSS - insert into cbp_rulings when source is CBP_CROSS
        if raw.source == "CBP_CROSS" and (primary_hts or hts_codes):
            ruling_num = re.search(r"(?:HQ|H\d{6}|NY\s*\d+)", raw.title or "", re.I)
            ruling_num = ruling_num.group(0) if ruling_num else raw.title[:50] if raw.title else "UNKNOWN"
            cbp_r = CBPRuling(
                ruling_number=ruling_num,
                hts_codes=hts_codes,
                description=classification_result.get("summary"),
                full_text=(raw.content or "")[:10000],
                source_url=raw.url,
                raw_signal_id=raw.id,
            )
            db.add(cbp_r)
            await db.flush()

        # GAP 3: FDA - insert into import_restrictions when IMPORT_RESTRICTION from FDA
        if raw.source == "FDA_IMPORT_ALERTS" and category == "IMPORT_RESTRICTION" and hts_codes:
            ir = ImportRestriction(
                agency="FDA",
                hts_codes=hts_codes,
                product_keywords=[],  # Could extract from classification
                description=classification_result.get("summary"),
                source_url=raw.url,
                severity="HIGH",
            )
            db.add(ir)
            await db.flush()

        # Score
        final_score = await score_signal(
            db, norm, organization_id,
            classification_override={"category": category, "impact_type": classification_result.get("impact_type")},
        )
        scored_count += 1

        score_row = SignalScore(
            signal_id=norm.id,
            organization_id=organization_id,
            final_score=final_score,
        )
        db.add(score_row)
        await db.flush()

        # GAP 1: Quota - compute fill_rate, upsert quota_status, create QUOTA_RISK if > 0.9
        if category == "QUOTA_UPDATE" and quota_limit and quota_limit > 0 and quota_used is not None:
            fill_rate = float(quota_used) / float(quota_limit)
            status = "filled" if fill_rate >= 1.0 else ("near_limit" if fill_rate >= QUOTA_FILL_THRESHOLD else "open")
            qs = QuotaStatus(
                hts_code=primary_hts or "UNKNOWN",
                country=classification_result.get("country") or (classification_result.get("countries") or [None])[0],
                quota_type="tariff_rate",
                quota_limit=Decimal(str(quota_limit)),
                quantity_used=Decimal(str(quota_used)),
                fill_rate=Decimal(str(round(fill_rate, 4))),
                status=status,
                source_signal_id=norm.id,
            )
            db.add(qs)
            await db.flush()
            if fill_rate >= QUOTA_FILL_THRESHOLD:
                explanation = {
                    "hts_match": bool(primary_hts),
                    "country_match": bool(classification_result.get("countries")),
                    "historical_usage": True,
                    "source": raw.source,
                    "fill_rate": round(fill_rate * 100, 1),
                }
                await create_psc_alert(
                    db, organization_id, norm.id, raw.source,
                    hts_code=primary_hts,
                    alert_type="QUOTA_RISK",
                    duty_delta_estimate=None,
                    reason=f"Quota nearly filled ({round(fill_rate*100, 1)}%)",
                    evidence_links=[{"url": raw.url, "title": raw.title}],
                    explanation=explanation,
                    confidence_score=classification_result.get("confidence"),
                    priority="HIGH",
                )
                alerts_created += 1

        # GAP 2/8: Tariff - link to shipments, compute duty delta
        if category == "TARIFF_CHANGE" and primary_hts:
            shipments_matched = await _find_shipments_for_hts(db, organization_id, primary_hts)
            rate_delta = (float(new_rate) - float(old_rate)) if (new_rate is not None and old_rate is not None) else None
            for ship_id, item_id, customs_val in shipments_matched[:3]:  # Limit to 3 per signal
                duty_delta_str = None
                if rate_delta is not None and customs_val and customs_val > 0:
                    delta_usd = rate_delta * customs_val
                    pct = (rate_delta / float(old_rate) * 100) if old_rate else None
                    duty_delta_str = f"${delta_usd:,.2f}" + (f" ({pct:+.1f}%)" if pct else "")
                explanation = {
                    "hts_match": True,
                    "country_match": bool(classification_result.get("countries")),
                    "historical_usage": True,
                    "source": raw.source,
                }
                await create_psc_alert(
                    db, organization_id, norm.id, raw.source,
                    hts_code=primary_hts,
                    alert_type="TARIFF_CHANGE",
                    duty_delta_estimate=duty_delta_str,
                    reason="Tariff change affects this HTS",
                    evidence_links=[{"url": raw.url, "title": raw.title}],
                    explanation=explanation,
                    shipment_id=ship_id,
                    shipment_item_id=item_id,
                    confidence_score=classification_result.get("confidence"),
                    priority="HIGH",
                )
                alerts_created += 1
            if not shipments_matched and final_score >= ALERT_THRESHOLD:
                # No matching shipments but high score - create alert without shipment link
                duty_delta_str = f"{rate_delta*100:+.1f}%" if rate_delta is not None else None
                explanation = {
                    "hts_match": bool(primary_hts),
                    "country_match": bool(classification_result.get("countries")),
                    "historical_usage": True,
                    "source": raw.source,
                }
                await create_psc_alert(
                    db, organization_id, norm.id, raw.source,
                    hts_code=primary_hts,
                    alert_type="TARIFF_CHANGE",
                    duty_delta_estimate=duty_delta_str,
                    reason=classification_result.get("summary", "Tariff change")[:500],
                    evidence_links=[{"url": raw.url, "title": raw.title}],
                    explanation=explanation,
                    confidence_score=classification_result.get("confidence"),
                    priority="HIGH",
                )
                alerts_created += 1

        # GAP 3: FDA/Import restriction - match to shipment items
        if category == "IMPORT_RESTRICTION" and primary_hts and final_score >= ALERT_THRESHOLD:
            shipments_matched = await _find_shipments_for_hts(db, organization_id, primary_hts)
            for ship_id, item_id, _ in shipments_matched[:3]:
                explanation = {
                    "hts_match": True,
                    "country_match": bool(classification_result.get("countries")),
                    "historical_usage": True,
                    "source": raw.source,
                }
                await create_psc_alert(
                    db, organization_id, norm.id, raw.source,
                    hts_code=primary_hts,
                    alert_type="FDA_RISK",
                    reason="FDA import alert applies to this product",
                    evidence_links=[{"url": raw.url, "title": raw.title}],
                    explanation=explanation,
                    shipment_id=ship_id,
                    shipment_item_id=item_id,
                    confidence_score=classification_result.get("confidence"),
                    priority="HIGH",
                )
                alerts_created += 1
            if not shipments_matched:
                explanation = {
                    "hts_match": bool(primary_hts),
                    "country_match": bool(classification_result.get("countries")),
                    "historical_usage": True,
                    "source": raw.source,
                }
                await create_psc_alert(
                    db, organization_id, norm.id, raw.source,
                    hts_code=primary_hts,
                    alert_type="FDA_RISK",
                    reason=classification_result.get("summary", "Import restriction")[:500],
                    evidence_links=[{"url": raw.url, "title": raw.title}],
                    explanation=explanation,
                    confidence_score=classification_result.get("confidence"),
                    priority="HIGH",
                )
                alerts_created += 1

        # Standard path: score >= threshold, create alert
        if final_score >= ALERT_THRESHOLD and category not in ("QUOTA_UPDATE", "TARIFF_CHANGE", "IMPORT_RESTRICTION"):
            explanation = {
                "hts_match": bool(primary_hts),
                "country_match": bool(classification_result.get("countries")),
                "historical_usage": True,
                "source": raw.source,
            }
            # GAP 9: Try to link to shipment
            shipment_id = None
            shipment_item_id = None
            if primary_hts:
                matches = await _find_shipments_for_hts(db, organization_id, primary_hts)
                if matches:
                    shipment_id, shipment_item_id, _ = matches[0]
            await create_psc_alert(
                db,
                organization_id=organization_id,
                signal_id=norm.id,
                raw_source=raw.source,
                hts_code=primary_hts,
                alert_type="regulatory_signal",
                reason=classification_result.get("summary", "")[:500],
                evidence_links=[{"url": raw.url, "title": raw.title}],
                explanation=explanation,
                shipment_id=shipment_id,
                shipment_item_id=shipment_item_id,
                confidence_score=classification_result.get("confidence"),
                priority="HIGH" if final_score >= 85 else "MEDIUM",
            )
            alerts_created += 1

    return {
        "normalized": normalized_count,
        "scored": scored_count,
        "alerts_created": alerts_created,
        "suppressed_no_hts": suppressed_no_hts,
    }
