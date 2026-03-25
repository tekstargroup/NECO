# Sprint 20: Source Setup Guide — Get the Intelligence Layer Working

**Non-technical leader?** Start here instead: **[REGULATORY_SOURCES_LEADER_PLAYBOOK.md](REGULATORY_SOURCES_LEADER_PLAYBOOK.md)** — checklist, no jargon.

**Purpose:** Make every regulatory source return real data. **March 2026:** URLs, poller behavior, and docs were updated so **most** sources return data in routine tests; a few remain **empty by design** (USITC HTS diff) or **network-dependent** (USDA FSIS). This guide is the setup checklist; the full change log is in **[SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md)** (*Source validation, feed hardening & docs*).

**Sprint context:** Only Sprint 13 is currently in progress (separate agent). Sprints 14–19 are not yet executed. Sprint 20 (Compliance Signal Engine) is this sprint — source validation and setup.

**Last updated:** March 24, 2026

---

## Sprint 20 Phases & Tiers (Reference)

| Phase | Scope | Status |
|-------|--------|--------|
| **Phase 1** | Base pipeline (schema, poller, classification, scoring, PSC alerts) | Done |
| **Phase 2** | Source tiers 1–8 (config + handlers) | Done — source URLs and poller hardened March 2026 (see progress log) |
| **Phase 3** | GAPs 1–10 | Done |
| **Phase 4** | Migration 012 | Done |
| **Phase 5** | Pinned priorities | Done |

**Source tiers:** 1 (CBP, FR, USTR, CROSS) → 2 (OFAC, FDA, USDA, BIS, ITA) → 3 (WTO, EU, WCO) → 4 (White House, Congress) → 5 (Quota, UBR) → 6 (FreightWaves, JOC, SupplyChainDive, Loadstar) → 7 (CBP CROSS vectorization, pending) → 8 (Importer HTS usage, internal).

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

### Tier 1 — Special cases (not “broken”)

| Source | Type | Notes | What to do |
|--------|------|-------|------------|
| **CBP_DUTY_RATES** | RSS | Uses **main trade RSS** with CSMS (deduped by URL) | **Resolved March 2026.** Empty in DB only if that URL already ingested under another source name. |
| **CBP_LEGAL_DECISIONS** | RSS | Same as duty rates | **Resolved March 2026** — shared trade feed by design. |
| **USITC_HTS** | API | Diff-based; **empty is normal** until HTS release changes | Handler: `https://hts.usitc.gov/reststop/releaseList` — see `regulatory_feed_poller.py` (`usitc_hts`). |
| **CBP_CROSS** | XML export | Prefer XML over HTML search | **Setup:** `CBP_CROSS_XML_URL` or `CBP_CROSS_LOCAL_FILE` — [CBP_CROSS_SETUP.md](CBP_CROSS_SETUP.md). |

---

### Tier 2 — Working (no action)

| Source | Type | Status | Action |
|--------|------|--------|--------|
| OFAC_RECENT_ACTIONS | Scrape | ✅ Working | None |
| FDA_IMPORT_ALERTS | Scrape | ✅ Working | None |
| BIS_FEDERAL_REGISTER | API | ✅ Working | None |

---

### Tier 2 — USDA FSIS only (network-sensitive)

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **USDA_FSIS** | API + RSS fallback | Some networks get HTML “Access Denied” | Poller tries recall API then FSIS RSS with browser-like headers. Try `REGULATORY_NO_PROXY=1`, different network, or GovDelivery — see [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md). |
| **ITA_ADCVD** | RSS | — | **Working:** `https://www.cbp.gov/rss/trade-adcvd` (verified March 2026). |

---

### Tier 3 — Working (verify if you fork)

| Source | Type | Notes |
|--------|------|--------|
| **WTO_DISPUTES** | RSS | `http://www.wto.org/library/rss/latest_news_e.xml` — gateway: https://www.wto.org/english/res_e/webcas_e/rss_e.htm |
| **EU_TAXUD** | RSS | `https://taxation-customs.ec.europa.eu/node/2/rss_en` |
| **WCO_NEWS** | Scrape | Can be slow; retry if timeout. |

---

### Tier 4 — Congress API key only

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **WHITE_HOUSE_BRIEFING** | RSS | ✅ Working | **URL:** `https://www.whitehouse.gov/presidential-actions/feed/` |
| **CONGRESS_GOV** | API | Requires API key | **Setup:** 1. Go to https://api.congress.gov/sign-up 2. Register for free API key 3. Add to `.env`: `CONGRESS_API_KEY=your_key` 4. Restart backend |

---

### Tier 5 — Deduped or Needs Fix

| Source | Type | Issue | What to do |
|--------|------|-------|------------|
| **CBP_QUOTA_BULLETINS** | RSS | Same URL as CBP_CSMS; deduped | No fix — intentionally shares trade feed. Will show 0 new when CSMS already polled. |
| **CBP_UBR** | RSS | Shares main trade feed | Same URL as CSMS (`https://www.cbp.gov/rss/trade`); deduped in DB. |

---

### Tier 6 — Working

| Source | Type | Notes |
|--------|------|--------|
| **FREIGHTWAVES** | RSS | `https://www.freightwaves.com/feed` |
| **JOC** | RSS | `https://www.joc.com/api/rssfeed` |
| **SUPPLY_CHAIN_DIVE** | RSS | `https://www.supplychaindive.com/feeds/news/` |
| **LOADSTAR** | RSS | `https://theloadstar.com/feed/` (replaces **FLEXPORT_BLOG**; new `raw_signals` use source name **LOADSTAR**). |

---

## Action Checklist

### 1. API keys (do once)

- [ ] **CONGRESS_GOV:** Register at https://api.congress.gov/sign-up, add `CONGRESS_API_KEY` to `backend/.env`

### 2. URL fixes (already applied in `sources_config.json` — verify if you fork)

- [ ] **EU_TAXUD:** `https://taxation-customs.ec.europa.eu/node/2/rss_en`
- [ ] **JOC:** `https://www.joc.com/api/rssfeed`
- [ ] **WHITE_HOUSE_BRIEFING:** `https://www.whitehouse.gov/presidential-actions/feed/`
- [ ] **SUPPLY_CHAIN_DIVE:** `https://www.supplychaindive.com/feeds/news/`
- [ ] **LOADSTAR:** `https://theloadstar.com/feed/`
- [ ] **USDA_FSIS:** API `https://www.fsis.usda.gov/fsis/api/recall/v/1` with RSS fallback in poller

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

### 5. Sources that may still need attention

| Source | Notes |
|-------|--------|
| CBP_CROSS | Prefer `CBP_CROSS_XML_URL` or local file; search HTML URL is a fallback |
| USDA_FSIS | Recall API + RSS fallback; some networks return HTML “Access Denied” — try another network or GovDelivery |
| USITC_HTS | Diff-based — **empty is normal** until HTS release changes |
| LOADSTAR | If feed moves, update `sources_config.json` |
| WTO_DISPUTES | If library RSS fails, check WTO RSS gateway page |

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
| `backend/config/sources_config.json` | All Sprint 20 source URLs and names (see [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md)) |
| `backend/.env` | `CONGRESS_API_KEY`, optional `CBP_CROSS_XML_URL` / `CBP_CROSS_LOCAL_FILE`, `REGULATORY_NO_PROXY=1` if needed |

---

## Success Criteria

**Sprint 20 source validation is done when:**

1. All Tier 1 sources that have working URLs/APIs return data (or are confirmed sparse by design — shared CBP trade RSS, USITC diff)
2. CONGRESS_GOV works with API key
3. EU_TAXUD, JOC, White House, Supply Chain Dive, Loadstar URLs applied and verified in `test_regulatory_sources.py` (March 2026)
4. CBP_CROSS: XML URL or local file documented; HTML-only fallback understood
5. USDA_FSIS / USITC_HTS: team understands when **empty is expected** (network / diff-based) — see [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md)

---

## Related

- [SOURCE_VALIDATION_GUIDE.md](SOURCE_VALIDATION_GUIDE.md) — How to test, add, fix sources
- [REGULATORY_SOURCES_TROUBLESHOOTING.md](REGULATORY_SOURCES_TROUBLESHOOTING.md) — Proxy, CLI, general troubleshooting
