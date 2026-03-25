# Regulatory Source Validation Guide

**Purpose:** Test each source, fix broken URLs, and add new ones.

**Last updated:** March 24, 2026

**See also:** [SPRINT20_SOURCE_SETUP_GUIDE.md](SPRINT20_SOURCE_SETUP_GUIDE.md) — Full setup checklist (API keys, URL fixes, research tasks) to get the intelligence layer working.

---

## How to Test

### 1. Test all sources (CLI)
```bash
cd backend && source venv/bin/activate
python scripts/test_regulatory_sources.py
```

### 2. Test one source by name
```bash
cd backend && source venv/bin/activate
python scripts/test_one_source.py CBP_CSMS
```

### 3. Test all sources (UI)
Signal Health page → **Test all sources**

---

## Source Status & Fixes

| Source | Status | Issue | Fix / Alternative |
|--------|--------|-------|-------------------|
| **CBP_CSMS** | ✅ OK | — | — |
| **CBP_ACE** | ⚠️ 0 count | Same content as CBP_CSMS; deduped by URL | Works; shows 0 because URLs already in DB from CBP_CSMS. No fix needed. |
| **CBP_DUTY_RATES** | ✅ OK | Shares main CBP trade RSS | `https://www.cbp.gov/rss/trade` — same URL as CSMS; deduped in DB. |
| **CBP_LEGAL_DECISIONS** | ✅ OK | Same as above | Intentionally same feed for coverage; deduped. |
| **FEDERAL_REGISTER** | ✅ OK | — | — |
| **USITC_HTS** | ○ empty | Diff-based: only emits when release changes | Poller uses `https://hts.usitc.gov/reststop/releaseList` (config `url` may differ; handler is authoritative). |
| **USTR_NEWS** | ✅ OK | — | — |
| **USTR_PRESS** | ✅ OK | — | — |
| **CBP_CROSS** | ✅ OK | Uses XML export (local file or CBP_CROSS_XML_URL) | Set `CBP_CROSS_XML_URL` from rulings.cbp.gov What's New → XML button. Or `CBP_CROSS_LOCAL_FILE` for testing. |
| **OFAC_RECENT_ACTIONS** | ✅ OK | — | — |
| **FDA_IMPORT_ALERTS** | ✅ OK | — | — |
| **USDA_FSIS** | ○ empty* | *Often blocked (HTML “Access Denied”) on some networks | Recall API in config + **RSS fallback** in poller (news-release, then recalls) with browser-like headers. |
| **BIS_FEDERAL_REGISTER** | ✅ OK | — | — |
| **ITA_ADCVD** | ✅ OK | — | `https://www.cbp.gov/rss/trade-adcvd` |
| **WTO_DISPUTES** | ✅ OK | — | `http://www.wto.org/library/rss/latest_news_e.xml` |
| **EU_TAXUD** | ○→✅ | 404; **fixed** to `taxation-customs.ec.europa.eu/node/2/rss_en` | URL updated in sources_config. |
| **WCO_NEWS** | ✅ OK | Slow (timeout sometimes) | — |
| **WHITE_HOUSE_BRIEFING** | ✅ OK | — | `https://www.whitehouse.gov/presidential-actions/feed/` |
| **CONGRESS_GOV** | ✅ OK* | *Requires `CONGRESS_API_KEY` in `.env` | Without key, test may fail. |
| **CBP_QUOTA_BULLETINS** | ✅ OK | Shares main trade RSS | Deduped with CSMS when URL matches. |
| **CBP_UBR** | ✅ OK | Shares main trade RSS | Same dedupe behavior as other CBP trade sources. |
| **FREIGHTWAVES** | ✅ OK | — | — |
| **JOC** | ○→✅ | 404; **fixed** to `joc.com/api/rssfeed` | URL updated in sources_config. |
| **SUPPLY_CHAIN_DIVE** | ✅ OK | — | `https://www.supplychaindive.com/feeds/news/` |
| **LOADSTAR** | ✅ OK | — | `https://theloadstar.com/feed/` (replaces Flexport blog RSS). |

---

## How to Add or Fix a Source

1. **Edit** `backend/config/sources_config.json`
2. **Add** or update the source object:
   ```json
   {
     "name": "SOURCE_NAME",
     "type": "rss",
     "url": "https://...",
     "frequency": "6h",
     "tier": 1,
     "description": "..."
   }
   ```
3. **Test** with `python scripts/test_one_source.py SOURCE_NAME`
4. **Restart** backend if needed; Celery will pick up new config on next poll.

---

## URLs to Try (Alternatives)

| Source | Current | Alternative to try |
|--------|---------|--------------------|
| WTO_DISPUTES | `https://www.wto.org/english/news_e/news_e.xml` | `http://www.wto.org/library/rss/latest_news_e.xml` |
| USDA_FSIS | `https://www.fsis.usda.gov/news-events/news-releases/rss` | Check GovDelivery page for RSS links |
| CONGRESS_GOV | — | Set `CONGRESS_API_KEY` in .env (get from api.congress.gov) |

---

## Deduped Sources (No Fix Needed)

- **CBP_ACE** and **CBP_CSMS** return the same items (same URLs). First poll wins; second shows 0 new inserts.
- **CBP_QUOTA_BULLETINS** uses CBP trade feed; same as above.

---

## Changelog (Sprint 20 — documented March 2026)

| Area | What changed |
|------|----------------|
| **Poller** | Per-URL HTTP headers (browser-like for FSIS, CBP rulings); RSS uses `_http_headers_for_url`. |
| **USDA FSIS** | JSON API first, then FSIS RSS feeds if API returns non-JSON or HTML. |
| **CBP RSS** | Duty rates, legal decisions, UBR, quota bulletins aligned to main **trade** RSS where sub-feeds were empty or stale; dedupe by URL. |
| **WHITE_HOUSE_BRIEFING** | `presidential-actions/feed/`. |
| **SUPPLY_CHAIN_DIVE** | `feeds/news/`. |
| **LOADSTAR** | Replaces **FLEXPORT_BLOG** name and URL (The Loadstar). |
| **Testing** | `scripts/test_regulatory_sources.py`, `test_one_source.py`. |
| **UI** | Signal Health: Process now, Refresh HTS, Poll now, Test all sources. |
| **Master log** | [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md) — section *Source validation, feed hardening & docs*. |
