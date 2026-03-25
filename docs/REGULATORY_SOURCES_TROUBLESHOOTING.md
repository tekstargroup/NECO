# Regulatory Sources — Troubleshooting

**Last updated:** March 24, 2026

---

## "No data" or all sources empty

### 1. **feedparser timeout** (fixed)

Older feedparser versions don't support `timeout`. We now use `requests.get()` first, then `feedparser.parse(content)`.

### 2. **Corporate proxy blocking requests**

If you see `ProxyError` or `403 Forbidden` when fetching gov sites:

```bash
export REGULATORY_NO_PROXY=1
```

Then run Celery or the test script. This bypasses `HTTP_PROXY`/`HTTPS_PROXY` for regulatory fetches.

### 3. **Test from CLI**

```bash
cd backend
source venv/bin/activate
export REGULATORY_NO_PROXY=1   # if behind corporate proxy
python scripts/test_regulatory_sources.py
```

To test a single source:
```bash
python scripts/test_one_source.py CBP_CSMS
```

See **`docs/SOURCE_VALIDATION_GUIDE.md`** for per-source status and how to fix URLs.

Expected (good network + `CONGRESS_API_KEY`): **most sources OK**; common **empty** cases: **USITC_HTS** (diff-based), **USDA_FSIS** (WAF/proxy). Full change log: [SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md) → *Source validation, feed hardening & docs*.

### 4. **Poll now, Process, Refresh HTS**

- **UI:** Signal Health page:
  - **Poll now** — fetch from all sources, insert raw_signals
  - **Process now** — normalize, classify, score, create alerts
  - **Refresh HTS** — refresh importer HTS usage from shipment data
- **API:** `POST /api/v1/regulatory-updates/poll`, `.../process`, `.../refresh-hts-usage`
- **Celery:** Ensure worker + beat are running

---

## Sources that may be empty (404, moved, or no items)

| Source | Notes |
|--------|-------|
| CBP_DUTY_RATES, CBP_LEGAL_DECISIONS, CBP_UBR, CBP_QUOTA_BULLETINS | Share **main trade RSS** with CSMS — **deduped by URL**; “empty” can mean URLs already stored under another source name. |
| USITC_HTS | **Diff-based** — empty until USITC release changes. |
| USDA_FSIS | API + RSS fallback; still **blocked** on some IPs (HTML error page). Poller uses browser-like **User-Agent**. |
| CONGRESS_GOV | Requires `CONGRESS_API_KEY` env var |
| JOC, SUPPLY_CHAIN_DIVE, LOADSTAR, EU_TAXUD, WHITE_HOUSE_BRIEFING | URLs fixed March 2026; if a site moves again, update `sources_config.json` — see [SOURCE_VALIDATION_GUIDE.md](SOURCE_VALIDATION_GUIDE.md) |

---

## Verify Celery is running

```bash
# Terminal 1
cd backend && source venv/bin/activate
celery -A app.core.celery_app worker -l info

# Terminal 2
cd backend && source venv/bin/activate
celery -A app.core.celery_app beat -l info
```
