# Regulatory Sources — Troubleshooting

**Last updated:** March 18, 2026

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

Expected: 10+ OK, some empty (feeds with no items).

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
| CBP_DUTY_RATES, CBP_LEGAL_DECISIONS | URL exists but feed may have no items |
| WHITE_HOUSE_BRIEFING | Feed URL may have changed |
| EU_TAXUD | EU moved to taxation-customs.ec.europa.eu |
| JOC, SUPPLY_CHAIN_DIVE, FLEXPORT_BLOG | Commercial feeds may have changed |
| USDA_FSIS | May block non-browser User-Agent |
| CONGRESS_GOV | Requires `CONGRESS_API_KEY` env var |

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
