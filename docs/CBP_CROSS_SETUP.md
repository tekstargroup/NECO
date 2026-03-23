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
2. Find the **"What's New"** section (left side)
3. Under **"All Latest Rulings"**, right-click the **XML** button
4. Choose **Copy link address**
5. Add to `backend/.env`:
   ```
   CBP_CROSS_XML_URL=<paste the URL here>
   ```
6. Remove or comment out `CBP_CROSS_LOCAL_FILE` once the URL works

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
