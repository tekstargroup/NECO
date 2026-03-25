# Regulatory sources — solo execution checklist

**No frontend needed.** Run tests from the `backend` folder only.

**Last updated:** March 24, 2026 (aligned with Sprint 20 source-validation work — see [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md).)

---

## Part A — “Which are missing?” (do this first)

### 1. Open a terminal and run (copy as one block)

```bash
cd "/Users/stevenbigio/Cursor Projects/NECO/backend"
source venv/bin/activate
export REGULATORY_NO_PROXY=1
python scripts/test_regulatory_sources.py
```

### 2. What to send back

Paste the **Summary** line and the full list (✓ / ○ lines), or a screenshot of the terminal.

That output is the **source of truth** for what’s missing *on your machine today*. The table below is from the **last run we discussed** — yours may differ slightly.

---

## Part B — Reference status (March 2026 — re-run Part A for truth on your machine)

| Status | Sources |
|--------|---------|
| **Usually OK in CLI test** | Most of the 25 sources, including WHITE_HOUSE_BRIEFING, SUPPLY_CHAIN_DIVE, LOADSTAR, CBP_DUTY_RATES / LEGAL / UBR / QUOTA (via shared trade RSS), CBP_CROSS (with `CBP_CROSS_XML_URL` or local XML). |
| **Often empty / blocked** | **USITC_HTS** (diff-based until HTS release changes). **USDA_FSIS** (WAF/network — API + RSS fallback in code). **CBP_ACE** can show 0 *new* rows vs CSMS when URLs dedupe. |
| **Full write-up** | [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md) → *Source validation, feed hardening & docs* |

**Total configured:** 25 sources.

---

## Part C — Your to-do’s (technical owner = you)

Check each box, then paste results in chat or fill the “Report back” lines.

### Config & keys (backend `.env`)

- [ ] **T1** — `CONGRESS_API_KEY` is set in `backend/.env` (you already have a key; confirm the line exists and has no typos).
- [ ] **T2** — **CROSS XML URL:** On https://rulings.cbp.gov/ → What’s New → right-click **XML** (All Latest Rulings) → Copy link. Add to `.env`:  
  `CBP_CROSS_XML_URL=<paste URL here>`  
  Then **comment out or remove** `CBP_CROSS_LOCAL_FILE` (so you’re not tied to one Mac path).
- [ ] **T3** — If FSIS still fails after tests: keep `REGULATORY_NO_PROXY=1` in the same terminal when testing; for **Celery/production**, document whether you need that env var on the server (same idea).

### Verify after `.env` changes

- [ ] **T4** — Run:  
  `python scripts/test_one_source.py CONGRESS_GOV`  
  **Report back:** OK or empty? (and any error line)
- [ ] **T5** — Run:  
  `python scripts/test_one_source.py CBP_CROSS`  
  **Report back:** item count (expect many if XML URL or local file works)
- [ ] **T6** — Run:  
  `python scripts/test_one_source.py USDA_FSIS`  
  **Report back:** OK or 403 / empty?

### Find replacement URLs (browser only — no code)

For each, open the site, look for **RSS**, **Subscribe**, or **Feed**, copy the **full URL** that returns XML or a feed.

- [ ] **T7** — **WHITE_HOUSE_BRIEFING** — config: `https://www.whitehouse.gov/presidential-actions/feed/`. Confirm in browser.  
  **Report back:** “loads” / broken
- [ ] **T8** — **LOADSTAR** — `https://theloadstar.com/feed/` (replaces Flexport blog RSS).  
  **Report back:** new URL or “none found”
- [ ] **T9** — **SUPPLY_CHAIN_DIVE** — config: `https://www.supplychaindive.com/feeds/news/`. Confirm in browser.  
  **Report back:** “loads” / broken
- [ ] **T10** — **CBP_UBR** — open https://www.cbp.gov/rss/trade — confirm UBR feed still listed; copy exact URL if different.  
  **Report back:** URL or “same as config / broken”
- [ ] **T11** — **CBP_DUTY_RATES** & **CBP_LEGAL_DECISIONS** — both use main trade RSS `https://www.cbp.gov/rss/trade` (deduped). Confirm feed loads.  
  **Report back:** “loads” / broken

### Optional: full re-test

- [ ] **T12** — Run full test again (Part A) after T2 and any URL updates you apply to `sources_config.json`.  
  **Report back:** new Summary line (e.g. `18 OK, 7 empty`)

---

## When you message back

Include:

1. Output of **Part A** (or T12).  
2. Results for **T4–T6** if you changed `.env`.  
3. **T7–T11** findings (URLs or “none found”).  

I’ll turn URLs into exact `sources_config.json` edits and any code tweaks if needed.
