"""
Regulatory Feed Poller - Compliance Signal Engine

Fetches RSS/API/scrape per sources config, parses items, dedupes by URL, inserts into raw_signals.
Supports all tiers: CBP, Federal Register, USITC, USTR, CROSS, OFAC, FDA, USDA, BIS, WTO, EU, White House,
Congress, CBP Quota, FreightWaves, JOC, SupplyChainDive, Loadstar.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sources_config import get_sources
from app.core.config import settings
from app.models.raw_signal import RawSignal

logger = logging.getLogger(__name__)

# User-Agent for RSS/API requests (some servers block default)
USER_AGENT = "NECO-Compliance-Signal-Engine/1.0 (Trade Compliance Monitoring)"
DEFAULT_TIMEOUT = 30
REQUEST_HEADERS = {"User-Agent": USER_AGENT}
# Some .gov hosts return empty bodies or 403 for bot-like User-Agents.
BROWSER_LIKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/xml, text/xml, application/rss+xml, text/html, */*",
}
# Alias for CROSS XML fetch (Accept tuned for XML only)
CBP_CROSS_HEADERS = {
    "User-Agent": BROWSER_LIKE_HEADERS["User-Agent"],
    "Accept": "application/xml, text/xml, */*",
}


def _http_headers_for_url(url: str) -> dict:
    """Use browser-like UA for hosts that block NECO's default bot string."""
    u = (url or "").lower()
    if "rulings.cbp.gov" in u or "fsis.usda.gov" in u:
        return dict(BROWSER_LIKE_HEADERS)
    return dict(REQUEST_HEADERS)
# Bypass HTTP_PROXY by default (corporate proxies often block gov sites). Set REGULATORY_USE_PROXY=1 to use system proxy.
USE_PROXY = os.environ.get("REGULATORY_USE_PROXY", "").lower() in ("1", "true", "yes")
REQUEST_KWARGS = {} if USE_PROXY else {"proxies": {"http": None, "https": None}}

# Path for storing last-known state (e.g. USITC HTS release)
STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "regulatory_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def _parse_rss_feed(url: str, source_name: str) -> List[Dict[str, Any]]:
    """
    Fetch and parse RSS feed.
    Returns list of dicts with: source, title, content, url, published_at
    Uses requests for fetch (feedparser has no timeout support).
    """
    items = []
    try:
        resp = requests.get(url, headers=_http_headers_for_url(url), timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            link = entry.get("link") or ""
            if not link and entry.get("links"):
                link = entry.links[0].get("href", "")
            if not link:
                continue

            title = entry.get("title") or "Untitled"
            content = entry.get("summary") or entry.get("description") or ""
            if hasattr(content, "value"):
                content = content.value

            published_at = None
            if entry.get("published_parsed"):
                try:
                    from time import mktime
                    published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
                except (ValueError, TypeError):
                    pass
            elif entry.get("updated_parsed"):
                try:
                    from time import mktime
                    published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))
                except (ValueError, TypeError):
                    pass

            items.append({
                "source": source_name,
                "title": title[:500] if len(title) > 500 else title,
                "content": (content or "")[:50000] if content else None,
                "url": link[:1000] if len(link) > 1000 else link,
                "published_at": published_at,
            })
    except Exception as e:
        logger.warning("Failed to fetch RSS %s: %s", url, e)
    return items


def _fetch_federal_register(source_name: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Fetch recent documents from Federal Register API."""
    items = []
    url = "https://www.federalregister.gov/api/v1/documents"
    base_params = {"per_page": 50, "order": "newest"}
    if params:
        base_params.update(params)
    try:
        resp = requests.get(
            url,
            params=base_params,
            headers=REQUEST_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            **REQUEST_KWARGS,
        )
        resp.raise_for_status()
        data = resp.json()
        for doc in data.get("results", []):
            doc_url = doc.get("html_url") or doc.get("pdf_url") or ""
            if not doc_url:
                continue
            title = doc.get("title", "Untitled")[:500]
            abstract = doc.get("abstract", "") or ""
            if isinstance(abstract, str) and len(abstract) > 50000:
                abstract = abstract[:50000]
            published = doc.get("publication_date")
            published_at = None
            if published:
                try:
                    published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            items.append({
                "source": source_name,
                "title": title,
                "content": abstract,
                "url": doc_url[:1000],
                "published_at": published_at,
            })
    except Exception as e:
        logger.warning("Failed to fetch Federal Register API: %s", e)
    return items


def _fetch_usitc_hts(source_name: str) -> List[Dict[str, Any]]:
    """
    USITC HTS diff-based: fetch release list, emit signal when release changes.
    Uses hts.usitc.gov/reststop API.
    """
    items = []
    state_file = STATE_DIR / "usitc_hts_release.json"
    try:
        url = "https://hts.usitc.gov/reststop/releaseList"
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        if resp.status_code != 200:
            logger.debug("USITC HTS API unavailable: %s", resp.status_code)
            return []

        data = resp.json()
        # releaseList returns array of release IDs, e.g. ["2024BasicDec", "2024BasicJun", ...]
        releases = data if isinstance(data, list) else data.get("releases") or data.get("releaseList") or []
        release_id = releases[0] if releases else "unknown"

        current = {"release_id": str(release_id), "checked_at": datetime.utcnow().isoformat()}
        last = {}
        if state_file.exists():
            try:
                with open(state_file) as f:
                    last = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        if last.get("release_id") != current["release_id"]:
            with open(state_file, "w") as f:
                json.dump(current, f, indent=2)
            items.append({
                "source": source_name,
                "title": f"USITC HTS Update - Release {release_id}",
                "content": f"USITC Harmonized Tariff Schedule update detected. Release ID: {release_id}. "
                          "Check https://hts.usitc.gov for tariff changes.",
                "url": f"https://hts.usitc.gov/release/{release_id}",
                "published_at": datetime.utcnow(),
            })
    except Exception as e:
        logger.warning("Failed to fetch USITC HTS: %s", e)
    return items


def _parse_cbp_cross_xml(content: bytes) -> List[Dict[str, Any]]:
    """Parse CROSS XML export (ArrayOfRulingExport / RulingExport)."""
    import xml.etree.ElementTree as ET

    items = []
    try:
        root = ET.fromstring(content)
        ns = {}  # no namespace in sample
        for elem in root.findall(".//RulingExport"):
            num = elem.find("RulingNumber")
            coll = elem.find("Collection")
            date_mod = elem.find("DateModified")
            url_elem = elem.find("Url")
            ruling_num = num.text.strip() if num is not None and num.text else "UNKNOWN"
            collection = coll.text or "HQ"
            url_val = url_elem.text.strip() if url_elem is not None and url_elem.text else ""
            if not url_val:
                continue
            title = f"CBP Ruling {ruling_num} ({collection})"
            published_at = None
            if date_mod is not None and date_mod.text:
                try:
                    published_at = datetime.strptime(date_mod.text.strip(), "%m/%d/%Y")
                except (ValueError, TypeError):
                    pass
            items.append({
                "source": "CBP_CROSS",
                "title": title[:500],
                "content": f"CBP {collection} ruling {ruling_num} modified {date_mod.text if date_mod is not None else ''}",
                "url": url_val[:1000],
                "published_at": published_at,
            })
    except ET.ParseError as e:
        logger.warning("CBP CROSS XML parse error: %s", e)
    return items


def _fetch_cbp_cross(source_name: str, base_url: str) -> List[Dict[str, Any]]:
    """
    CBP CROSS rulings: fetch XML/CSV export from "What's New" download links.
    Set CBP_CROSS_XML_URL in .env to the XML download URL (right-click XML button → Copy link).
    Falls back to trying common CBP export URLs.
    """
    items = []
    # 1. Env override (user copies URL from rulings.cbp.gov What's New → XML button)
    xml_url = getattr(settings, "CBP_CROSS_XML_URL", None) or os.environ.get("CBP_CROSS_XML_URL")
    urls_to_try = []
    if xml_url:
        urls_to_try.append(xml_url)
    # 2. Default export (same as site "All Latest Rulings" XML; collection= empty = all)
    urls_to_try.append("https://rulings.cbp.gov/api/stat/recentRulings?format=xml&collection=")
    for url in urls_to_try:
        try:
            headers = CBP_CROSS_HEADERS if "rulings.cbp.gov" in url else {**REQUEST_HEADERS, "Accept": "application/xml, text/xml, */*"}
            resp = requests.get(
                url,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
                **REQUEST_KWARGS,
            )
            if resp.status_code != 200:
                continue
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "xml" in ct or resp.content.strip().startswith(b"<?xml") or b"<ArrayOfRulingExport" in resp.content:
                items = _parse_cbp_cross_xml(resp.content)
                for it in items:
                    it["source"] = source_name
                if items:
                    return items
        except Exception as e:
            logger.debug("CBP CROSS fetch %s: %s", url[:50], e)
            continue

    # 3. Local file fallback (for testing: CBP_CROSS_LOCAL_FILE=/path/to/latest_rulings_ALL.xml)
    local_path = getattr(settings, "CBP_CROSS_LOCAL_FILE", None) or os.environ.get("CBP_CROSS_LOCAL_FILE")
    if local_path and Path(local_path).exists():
        try:
            with open(local_path, "rb") as f:
                items = _parse_cbp_cross_xml(f.read())
            for it in items:
                it["source"] = source_name
            return items
        except Exception as e:
            logger.warning("CBP CROSS local file read failed: %s", e)

    return items


def _fetch_ofac_recent_actions(source_name: str, url: str) -> List[Dict[str, Any]]:
    """Scrape OFAC recent actions page (RSS retired Jan 2025)."""
    items = []
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        if resp.status_code != 200:
            return items
        soup = BeautifulSoup(resp.text, "lxml")
        for row in soup.select("tr, .views-row, .recent-action")[:30]:
            links = row.select("a[href*='recent-actions']")
            for a in links:
                href = a.get("href", "")
                full_url = href if href.startswith("http") else f"https://ofac.treasury.gov{href}"
                title = (a.get_text(strip=True) or "OFAC Recent Action")[:500]
                if len(title) < 10:
                    continue
                items.append({
                    "source": source_name,
                    "title": title,
                    "content": f"OFAC action: {title}",
                    "url": full_url[:1000],
                    "published_at": None,
                })
        if not items:
            # Fallback: use page itself as signal
            items.append({
                "source": source_name,
                "title": "OFAC Recent Actions",
                "content": "OFAC sanctions list updated. See recent actions.",
                "url": url,
                "published_at": datetime.utcnow(),
            })
    except Exception as e:
        logger.warning("Failed to fetch OFAC recent actions: %s", e)
    return items


def _fetch_fda_import_alerts(source_name: str, url: str) -> List[Dict[str, Any]]:
    """Scrape FDA import alerts by publish date."""
    items = []
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        if resp.status_code != 200:
            return items
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.select("a[href*='import'], a[href*='alert']")[:25]:
            href = a.get("href", "")
            full_url = href if href.startswith("http") else f"https://www.accessdata.fda.gov{href}"
            title = (a.get_text(strip=True) or "FDA Import Alert")[:500]
            if len(title) < 5:
                continue
            items.append({
                "source": source_name,
                "title": title,
                "content": f"FDA import alert: {title}",
                "url": full_url[:1000],
                "published_at": None,
            })
        if not items:
            items.append({
                "source": source_name,
                "title": "FDA Import Alerts",
                "content": "FDA import alerts database. Check for product admissibility updates.",
                "url": url,
                "published_at": datetime.utcnow(),
            })
    except Exception as e:
        logger.warning("Failed to fetch FDA import alerts: %s", e)
    return items


def _fetch_wco_news(source_name: str, url: str) -> List[Dict[str, Any]]:
    """Scrape WCO newsroom for HS/customs updates."""
    items = []
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        if resp.status_code != 200:
            return items
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.select("a[href*='newsroom'], a[href*='wcoomd']")[:15]:
            href = a.get("href", "")
            full_url = href if href.startswith("http") else f"https://www.wcoomd.org{href}"
            title = (a.get_text(strip=True) or "WCO News")[:500]
            if len(title) < 5:
                continue
            items.append({
                "source": source_name,
                "title": title,
                "content": f"WCO: {title}",
                "url": full_url[:1000],
                "published_at": None,
            })
    except Exception as e:
        logger.warning("Failed to fetch WCO news: %s", e)
    return items


def _fetch_usda_fsis_recall(source_name: str) -> List[Dict[str, Any]]:
    """
    USDA FSIS — try Recall JSON API, then public RSS (news-release / recalls).
    FSIS often blocks non-browser User-Agents on both.
    """
    items = []
    api_url = "https://www.fsis.usda.gov/fsis/api/recall/v/1"
    h = _http_headers_for_url(api_url)
    try:
        resp = requests.get(api_url, headers=h, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        ct = (resp.headers.get("Content-Type") or "").lower()
        if resp.status_code == 200 and "json" in ct and not resp.content.strip().startswith(b"<"):
            data = resp.json()
            if isinstance(data, list) and data:
                for rec in data[:50]:
                    title = rec.get("field_title") or "FSIS Recall"
                    summary = rec.get("field_summary") or ""
                    recall_num = rec.get("field_recall_number") or ""
                    recall_date = rec.get("field_recall_date") or ""
                    risk = rec.get("field_risk_level") or ""
                    content = f"{summary[:2000]}..." if len(summary) > 2000 else summary
                    if risk:
                        content = f"[{risk}] {content}"
                    rec_url = (
                        f"https://www.fsis.usda.gov/recalls-alerts/recall-{recall_num.lower().replace(' ', '-')}"
                        if recall_num
                        else "https://www.fsis.usda.gov/recalls-alerts"
                    )
                    published_at = None
                    if recall_date:
                        try:
                            published_at = datetime.strptime(recall_date, "%Y-%m-%d")
                        except (ValueError, TypeError):
                            pass
                    items.append({
                        "source": source_name,
                        "title": str(title)[:500],
                        "content": content[:50000] if content else None,
                        "url": rec_url[:1000],
                        "published_at": published_at,
                    })
                return items
        if resp.status_code != 200:
            logger.debug("USDA FSIS Recall API status %s, trying RSS fallback", resp.status_code)
    except Exception as e:
        logger.debug("USDA FSIS Recall API: %s, trying RSS fallback", e)

    for rss_url in (
        "https://www.fsis.usda.gov/fsis-content/rss/news-release",
        "https://www.fsis.usda.gov/fsis-content/rss/recalls",
    ):
        try:
            r = requests.get(rss_url, headers=h, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
            if r.status_code != 200:
                continue
            parsed = feedparser.parse(r.content)
            for entry in parsed.entries[:50]:
                link = entry.get("link") or ""
                if not link and entry.get("links"):
                    link = entry.links[0].get("href", "")
                if not link:
                    continue
                title = entry.get("title") or "FSIS News"
                content = entry.get("summary") or entry.get("description") or ""
                if hasattr(content, "value"):
                    content = content.value
                published_at = None
                if entry.get("published_parsed"):
                    try:
                        from time import mktime
                        published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
                    except (ValueError, TypeError):
                        pass
                items.append({
                    "source": source_name,
                    "title": str(title)[:500],
                    "content": (content or "")[:50000] if content else None,
                    "url": str(link)[:1000],
                    "published_at": published_at,
                })
            if items:
                return items
        except Exception as e:
            logger.debug("USDA FSIS RSS %s: %s", rss_url, e)
    return items


def _fetch_congress(source_name: str) -> List[Dict[str, Any]]:
    """Congress.gov API - bills affecting trade (requires CONGRESS_API_KEY)."""
    items = []
    api_key = getattr(settings, "CONGRESS_API_KEY", None) or os.environ.get("CONGRESS_API_KEY")
    if not api_key:
        logger.debug("CONGRESS_API_KEY not set, skipping Congress.gov")
        return items
    try:
        url = "https://api.congress.gov/v3/bill/118"
        params = {"api_key": api_key, "limit": 25, "sort": "updateDate+desc"}
        resp = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=DEFAULT_TIMEOUT, **REQUEST_KWARGS)
        if resp.status_code != 200:
            logger.warning("Congress API error: %s", resp.status_code)
            return items
        data = resp.json()
        bills = data.get("bills") or []
        for b in bills:
            title = b.get("title") or b.get("shortTitle") or "Bill"
            congress_url = b.get("url") or f"https://www.congress.gov/bill/118th-congress/{b.get('type', 'bill')}/{b.get('number', '')}"
            summary = b.get("latestAction", {}).get("text") or b.get("summary") or ""
            items.append({
                "source": source_name,
                "title": str(title)[:500],
                "content": str(summary)[:50000] if summary else None,
                "url": congress_url[:1000],
                "published_at": None,
            })
    except Exception as e:
        logger.warning("Failed to fetch Congress API: %s", e)
    return items


def _fetch_by_handler(handler: str, source_name: str, url: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Route to specific API/scrape handler."""
    if handler == "federal_register":
        return _fetch_federal_register(source_name)
    if handler == "federal_register_search":
        return _fetch_federal_register(source_name, params=params)
    if handler == "usitc_hts":
        return _fetch_usitc_hts(source_name)
    if handler == "cbp_cross":
        return _fetch_cbp_cross(source_name, url)
    if handler == "ofac_recent_actions":
        return _fetch_ofac_recent_actions(source_name, url)
    if handler == "fda_import_alerts":
        return _fetch_fda_import_alerts(source_name, url)
    if handler == "wco_news":
        return _fetch_wco_news(source_name, url)
    if handler == "congress":
        return _fetch_congress(source_name)
    if handler == "usda_fsis_recall":
        return _fetch_usda_fsis_recall(source_name)
    logger.warning("Unknown handler: %s", handler)
    return []


async def _dedupe_and_insert(
    db: AsyncSession,
    items: List[Dict[str, Any]],
) -> int:
    """Dedupe by URL and insert new raw_signals. Returns count of newly inserted rows."""
    if not items:
        return 0

    inserted = 0
    for item in items:
        url = item.get("url")
        if not url:
            continue
        result = await db.execute(select(RawSignal.id).where(RawSignal.url == url))
        if result.scalar_one_or_none():
            continue
        raw = RawSignal(
            source=item["source"],
            title=item["title"],
            content=item.get("content"),
            url=url,
            published_at=item.get("published_at"),
        )
        db.add(raw)
        inserted += 1
    return inserted


def _test_one_source(src: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single source. Used by test_all_sources for parallel execution."""
    name = src.get("name", "unknown")
    stype = src.get("type", "rss")
    tier = src.get("tier", 0)
    url = src.get("url", "")
    handler = src.get("handler")
    params = src.get("params")

    if not url and stype != "api":
        return {
            "name": name,
            "type": stype,
            "tier": tier,
            "status": "skipped",
            "items_count": 0,
            "error": "No URL configured",
        }

    items = []
    error_msg = None
    try:
        if stype == "rss":
            items = _parse_rss_feed(url, name)
        elif stype == "api":
            if handler:
                items = _fetch_by_handler(handler, name, url or "", params=params)
            elif "federalregister" in (url or "").lower():
                items = _fetch_federal_register(name)
            else:
                error_msg = "Unknown API source (no handler)"
        elif stype == "scrape":
            if handler:
                items = _fetch_by_handler(handler, name, url or "")
            else:
                error_msg = "Scrape source has no handler"
    except Exception as e:
        error_msg = str(e)[:200]
        logger.warning("Test source %s failed: %s", name, e)

    if error_msg:
        status = "fail"
    elif items:
        status = "ok"
    else:
        status = "empty"

    return {
        "name": name,
        "type": stype,
        "tier": tier,
        "status": status,
        "items_count": len(items),
        "error": error_msg,
    }


def test_all_sources() -> List[Dict[str, Any]]:
    """
    Test each configured source: fetch without inserting.
    Runs sources in parallel with 20s timeout each to avoid long waits.
    Returns list of {name, type, tier, status, items_count, error?}.
    status: ok (items fetched), empty (0 items, no error), fail (exception), skipped (no API key, etc).
    """
    from app.core.sources_config import get_sources

    sources = get_sources()
    results = []
    timeout_per_source = 20

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_test_one_source, src): src for src in sources}
        for future in as_completed(futures, timeout=len(sources) * timeout_per_source + 10):
            try:
                result = future.result(timeout=timeout_per_source + 5)
                results.append(result)
            except Exception as e:
                src = futures.get(future, {})
                name = src.get("name", "unknown")
                results.append({
                    "name": name,
                    "type": src.get("type", "rss"),
                    "tier": src.get("tier", 0),
                    "status": "fail",
                    "items_count": 0,
                    "error": str(e)[:200],
                })
                logger.warning("Test source %s timed out or failed: %s", name, e)

    # Sort by tier then name for consistent display
    results.sort(key=lambda r: (r["tier"], r["name"]))
    return results


async def poll_regulatory_feeds(
    db: AsyncSession,
    frequency_filter: Optional[str] = None,
    source_names: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    Poll configured sources and insert new raw_signals.

    Args:
        frequency_filter: If set, only poll sources with this frequency (5min, 15min, 1h, 6h, 1d). GAP 5.
        source_names: If set, only poll these source names.

    Returns dict with source -> count of new items inserted.
    """
    from app.core.sources_config import get_sources_by_frequency

    if source_names:
        all_sources = get_sources()
        sources = [s for s in all_sources if s.get("name") in source_names]
    elif frequency_filter:
        sources = get_sources_by_frequency(frequency_filter)
    else:
        sources = get_sources()
    totals = {}

    for src in sources:
        name = src.get("name", "unknown")
        stype = src.get("type", "rss")
        url = src.get("url", "")
        handler = src.get("handler")
        params = src.get("params")

        if not url and stype != "api":
            logger.warning("Source %s has no URL", name)
            continue

        items = []
        if stype == "rss":
            items = _parse_rss_feed(url, name)
        elif stype == "api":
            if handler:
                items = _fetch_by_handler(handler, name, url or "", params=params)
            elif "federalregister" in (url or "").lower():
                items = _fetch_federal_register(name)
            else:
                logger.warning("Unknown API source: %s (no handler)", name)
        elif stype == "scrape":
            if handler:
                items = _fetch_by_handler(handler, name, url or "")
            else:
                logger.warning("Scrape source %s has no handler", name)

        if items:
            count = await _dedupe_and_insert(db, items)
            totals[name] = count
            if count > 0:
                logger.info("Poller: %s inserted %d new signals", name, count)

    return totals
