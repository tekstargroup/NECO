# CBP CROSS Setup — Automated Rulings Ingestion

**Purpose:** Ingest CBP rulings from the "What's New" XML/CSV exports without manual downloads.

---

## Current Setup

CBP_CROSS now parses the XML export format (`ArrayOfRulingExport` / `RulingExport`). You can use either:

1. **Local file (testing):** `CBP_CROSS_LOCAL_FILE=/path/to/latest_rulings_ALL.xml` in `.env`
2. **Download URL (automation):** `CBP_CROSS_XML_URL=<url>` in `.env`

---

## Finding the Download URL

To automate (no manual download):

1. Go to **https://rulings.cbp.gov/**
2. Find **"What's New"** → **"All Latest Rulings"**
3. **Option A:** Right-click the **XML** control → **Copy link** (if your browser shows it).  
4. **Option B:** Open **Inspect** → **Network** → click **XML** on the page → copy **Request URL** from that request.
5. Add to `backend/.env`:
   ```
   CBP_CROSS_XML_URL=<paste the URL here>
   ```
   The URL usually looks like:  
   `https://rulings.cbp.gov/api/stat/recentRulings?format=xml&collection=`  
   (**`collection=`** empty is correct for “all latest”; `collection=ALL` returns an empty feed.)
6. Remove or comment out `CBP_CROSS_LOCAL_FILE` once the URL works.

**Note:** NECO uses a browser-like `User-Agent` for this host only — CBP returns an empty XML list for custom/bot user agents.

---

## Testing

```bash
cd backend
source venv/bin/activate
python scripts/test_one_source.py CBP_CROSS
```

Expected: `✓ CBP_CROSS ok items=264` (or similar count).

---

## XML Format (Reference)

The export contains:

```xml
<RulingExport>
  <RulingNumber>H337323</RulingNumber>
  <Collection>HQ</Collection>
  <DateModified>3/12/2026</DateModified>
  <Url>https://rulings.cbp.gov/docs/hq/2026/h337323</Url>
</RulingExport>
```

Each ruling becomes a raw_signal with title, content, url, published_at.
