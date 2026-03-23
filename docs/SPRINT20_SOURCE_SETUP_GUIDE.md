# Sprint 20: Source Setup Guide — Get the Intelligence Layer Working

**Non-technical leader?** Start here instead: **[REGULATORY_SOURCES_LEADER_PLAYBOOK.md](REGULATORY_SOURCES_LEADER_PLAYBOOK.md)** — checklist, no jargon.

**Purpose:** Make every regulatory source return real data. Right now many return empty — this guide tells you exactly what to do for each.

**Sprint context:** Only Sprint 13 is currently in progress (separate agent). Sprints 14–19 are not yet executed. Sprint 20 (Compliance Signal Engine) is this sprint — source validation and setup.

**Last updated:** March 18, 2026

---

## Sprint 20 Phases & Tiers (Reference)

| Phase | Scope | Status |
|-------|--------|--------|
| **Phase 1** | Base pipeline (schema, poller, classification, scoring, PSC alerts) | Done |
| **Phase 2** | Source tiers 1–8 (config + handlers) | Done — but many sources return empty |
| **Phase 3** | GAPs 1–10 | Done |
| **Phase 4** | Migration 012 | Done |
| **Phase 5** | Pinned priorities | Done |

**Source tiers:** 1 (CBP, FR, USTR, CROSS) → 2 (OFAC, FDA, USDA, BIS, ITA) → 3 (WTO, EU, WCO) → 4 (White House, Congress) → 5 (Quota, UBR) → 6 (FreightWaves, JOC, SupplyChainDive, Flexport) → 7 (CBP CROSS vectorization, pending) → 8 (Importer HTS usage, internal).

---

## What You Need to Do

**Goal:** Every source that can return data should return data. For each broken source, you need to either:
- Fix the URL
- Add an API key
- Or accept that the source is unavailable and document why

---

## Source-by-Source Setup

### Tier 1 — Working (no action)

| Source | Type | Status | Action |
|--------|------|--------|--------|
| CBP_CSMS | RSS | ✅ Working | None |
| CBP_ACE | RSS | ✅ Working (deduped with CSMS) | None |
| FEDERAL_REGISTER | API | ✅ Working | None |
| USTR_NEWS | RSS | ✅ Working | None |
| USTR_PRESS | RSS | ✅ Working | None |

---

### Tier 1 — Needs Fix or Research

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **CBP_DUTY_RATES** | RSS | Often 0 items | URL may be correct; feed may be sparse. **Test:** `python scripts/test_one_source.py CBP_DUTY_RATES`. If still empty, check https://www.cbp.gov/rss for alternate duty feeds. |
| **CBP_LEGAL_DECISIONS** | RSS | Often 0 items | Same as above. Feed may publish rarely. |
| **USITC_HTS** | API | Diff-based; only emits when release changes | Handler uses `https://hts.usitc.gov/reststop/releaseList` or search API. May need to verify handler logic — check `regulatory_feed_poller.py` usitc_hts handler. |
| **CBP_CROSS** | XML export | Use "What's New" XML/CSV downloads | **Setup:** 1) Right-click XML button on rulings.cbp.gov → Copy link. 2) Add `CBP_CROSS_XML_URL=<url>` to .env. Or temporarily: `CBP_CROSS_LOCAL_FILE=/path/to/latest_rulings_ALL.xml` to test with a local file. |

---

### Tier 2 — Working (no action)

| Source | Type | Status | Action |
|--------|------|--------|--------|
| OFAC_RECENT_ACTIONS | Scrape | ✅ Working | None |
| FDA_IMPORT_ALERTS | Scrape | ✅ Working | None |
| BIS_FEDERAL_REGISTER | API | ✅ Working | None |

---

### Tier 2 — Needs Fix

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **USDA_FSIS** | RSS | 403 or wrong URL | **Fix:** Update URL to `https://www.fsis.usda.gov/fsis-content/rss/news-release` or `https://www.fsis.usda.gov/fsis-content/rss/recalls`. Edit `sources_config.json`. If 403 persists, try FSIS API: https://www.fsis.usda.gov/api |
| **ITA_ADCVD** | RSS | URL may be wrong | Current: `https://www.cbp.gov/rss/trade-adcvd`. **Test** — if 404, search CBP RSS index for AD/CVD feed. |

---

### Tier 3 — Needs Fix

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **WTO_DISPUTES** | RSS | May 404/500 | Current: `http://www.wto.org/library/rss/latest_news_e.xml`. Official gateway: https://www.wto.org/english/res_e/webcas_e/rss_e.htm. **Test** — if fail, WTO may have moved feeds. |
| **EU_TAXUD** | RSS | 404 — EU moved domain | **Fix:** Update URL to `https://taxation-customs.ec.europa.eu/node/2/rss_en` (confirmed working). Edit `sources_config.json`. |
| **WCO_NEWS** | Scrape | Slow/timeout | May work; increase timeout if needed. |

---

### Tier 4 — Needs Setup

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **WHITE_HOUSE_BRIEFING** | RSS | 404 — feed moved | **Research:** Visit https://www.whitehouse.gov/briefing-room/, look for RSS link in page source or footer. May need to use different URL or accept no RSS. |
| **CONGRESS_GOV** | API | Requires API key | **Setup:** 1. Go to https://api.congress.gov/sign-up 2. Register for free API key 3. Add to `.env`: `CONGRESS_API_KEY=your_key` 4. Restart backend |

---

### Tier 5 — Deduped or Needs Fix

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **CBP_QUOTA_BULLETINS** | RSS | Same URL as CBP_CSMS; deduped | No fix — intentionally shares trade feed. Will show 0 new when CSMS already polled. |
| **CBP_UBR** | RSS | May 404 | Current: `https://www.cbp.gov/rss/trade/unified-business-resumption-messaging`. **Test** — if 404, check CBP RSS index. |

---

### Tier 6 — Needs Fix

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **FREIGHTWAVES** | RSS | ✅ Working | None |
| **JOC** | RSS | 404 — old URL | **Fix:** Update URL to `https://www.joc.com/api/rssfeed` (All News). Edit `sources_config.json`. |
| **SUPPLY_CHAIN_DIVE** | RSS | 404 — no native RSS | **Research:** Site may not offer RSS. Options: (1) Use rss.app to generate feed from https://www.supplychaindive.com/ (2) Or remove source if not critical |
| **FLEXPORT_BLOG** | RSS | 404 — feed may have moved | **Research:** Visit https://www.flexport.com/blog/, check for RSS link. If none, consider removing or using third-party RSS generator. |

---

## Action Checklist

### 1. API keys (do once)

- [ ] **CONGRESS_GOV:** Register at https://api.congress.gov/sign-up, add `CONGRESS_API_KEY` to `backend/.env`

### 2. URL fixes (edit sources_config.json)

- [ ] **EU_TAXUD:** Change URL to `https://taxation-customs.ec.europa.eu/node/2/rss_en`
- [ ] **JOC:** Change URL to `https://www.joc.com/api/rssfeed`
- [ ] **USDA_FSIS:** Change URL to `https://www.fsis.usda.gov/fsis-content/rss/news-release` (or `/recalls`)

### 3. Test each source

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO/backend"
source venv/bin/activate
python scripts/test_one_source.py EU_TAXUD
python scripts/test_one_source.py JOC
python scripts/test_one_source.py USDA_FSIS
python scripts/test_one_source.py CONGRESS_GOV   # after adding API key
```

### 4. Run full test

```bash
python scripts/test_regulatory_sources.py
```

### 5. Sources that need manual research

| Source | Research task |
|-------|---------------|
| CBP_CROSS | Inspect rulings.cbp.gov network calls; consider Playwright if no API |
| WHITE_HOUSE_BRIEFING | Find current RSS URL on whitehouse.gov |
| SUPPLY_CHAIN_DIVE | Confirm if RSS exists; else use rss.app or remove |
| FLEXPORT_BLOG | Confirm if RSS exists |
| WTO_DISPUTES | Verify library RSS works; check WTO gateway if not |

---

## Email / GovDelivery (Alternative for Some Sources)

If RSS/API is unavailable, some agencies offer **email subscriptions** that you could process manually or via email-to-webhook:

| Source | Email option |
|--------|-------------|
| USDA FSIS | https://public.govdelivery.com/accounts/USFSIS/subscriber/new |
| SupplyChainDive | Newsletter signup on site |
| JOC | May require subscription |

**Note:** Email is not automated in the current pipeline. Would require separate integration (e.g., parse forwarded emails, or use a service that converts email to webhook).

---

## Files to Edit

| File | Purpose |
|------|---------|
| `backend/config/sources_config.json` | Update URLs for EU_TAXUD, JOC, USDA_FSIS |
| `backend/.env` | Add CONGRESS_API_KEY |

---

## Success Criteria

**Sprint 20 source validation is done when:**

1. All Tier 1 sources that have working URLs/APIs return data (or are confirmed sparse by design)
2. CONGRESS_GOV works with API key
3. EU_TAXUD, JOC, USDA_FSIS return data after URL fix
4. CBP_CROSS: either fixed or documented as "requires Playwright / manual research"
5. Remaining broken sources (White House, SupplyChainDive, Flexport, WTO) either fixed or explicitly deferred with reason

---

## Related

- [SOURCE_VALIDATION_GUIDE.md](SOURCE_VALIDATION_GUIDE.md) — How to test, add, fix sources
- [REGULATORY_SOURCES_TROUBLESHOOTING.md](REGULATORY_SOURCES_TROUBLESHOOTING.md) — Proxy, CLI, general troubleshooting
