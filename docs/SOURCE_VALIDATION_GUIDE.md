# Regulatory Source Validation Guide

**Purpose:** Test each source, fix broken URLs, and add new ones.

**Last updated:** March 18, 2026

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
| **CBP_DUTY_RATES** | ○ empty | Feed exists but often has no items | URL correct. May need to wait for content. |
| **CBP_LEGAL_DECISIONS** | ○ empty | Feed exists but often has no items | URL correct. |
| **FEDERAL_REGISTER** | ✅ OK | — | — |
| **USITC_HTS** | ○ empty | Diff-based: only emits when release changes | URL: `https://hts.usitc.gov/reststop/releaseList`. Check handler. |
| **USTR_NEWS** | ✅ OK | — | — |
| **USTR_PRESS** | ✅ OK | — | — |
| **CBP_CROSS** | ✅ OK | Uses XML export (local file or CBP_CROSS_XML_URL) | Set `CBP_CROSS_XML_URL` from rulings.cbp.gov What's New → XML button. Or `CBP_CROSS_LOCAL_FILE` for testing. |
| **OFAC_RECENT_ACTIONS** | ✅ OK | — | — |
| **FDA_IMPORT_ALERTS** | ✅ OK | — | — |
| **USDA_FSIS** | ○→? | 403; **try** `fsis-content/rss/news-release` | URL updated; test to confirm. |
| **BIS_FEDERAL_REGISTER** | ✅ OK | — | — |
| **ITA_ADCVD** | ○ empty | URL may have changed | Try `https://www.cbp.gov/rss/trade-adcvd` |
| **WTO_DISPUTES** | ○ empty | Original 404; updated to library RSS | `http://www.wto.org/library/rss/latest_news_e.xml` (official gateway) |
| **EU_TAXUD** | ○→✅ | 404; **fixed** to `taxation-customs.ec.europa.eu/node/2/rss_en` | URL updated in sources_config. |
| **WCO_NEWS** | ✅ OK | Slow (timeout sometimes) | — |
| **WHITE_HOUSE_BRIEFING** | ○ empty | 404 (feed moved) | Find new RSS at whitehouse.gov. |
| **CONGRESS_GOV** | ○ empty | Requires CONGRESS_API_KEY | Add key to .env. |
| **CBP_QUOTA_BULLETINS** | ○ empty | Uses same URL as CBP_CSMS | Deduped. Same as CBP_ACE. |
| **CBP_UBR** | ○ empty | URL may have changed | `https://www.cbp.gov/rss/trade/unified-business-resumption-messaging` |
| **FREIGHTWAVES** | ✅ OK | — | — |
| **JOC** | ○→✅ | 404; **fixed** to `joc.com/api/rssfeed` | URL updated in sources_config. |
| **SUPPLY_CHAIN_DIVE** | ○ empty | 404 (feed moved) | Find new RSS. |
| **FLEXPORT_BLOG** | ○ empty | 404 (feed moved) | Find new RSS. |

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
