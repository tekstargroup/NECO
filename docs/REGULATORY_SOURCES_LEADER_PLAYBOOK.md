# NECO Regulatory Feeds — Leader Playbook

**Last updated:** March 24, 2026

**Doing this yourself (no separate engineer)?** Use **[REGULATORY_SOURCES_SOLO_CHECKLIST.md](REGULATORY_SOURCES_SOLO_CHECKLIST.md)** — test without the frontend, then paste results back to Cursor.

**What this is:** A simple checklist so every government and trade news source can flow into NECO. No coding required for most steps.

**Sprint 20 update (March 2026):** Engineering refreshed feed URLs, poller behavior (including USDA FSIS fallbacks and browser-like headers for picky sites), CLI test scripts, and Signal Health actions. The **single master list** of what changed is **[SPRINT20_PROGRESS.md](SPRINT20_PROGRESS.md)** → section *“Source validation, feed hardening & docs.”* This playbook stays focused on **what you do** in the app.

**Why it matters:** NECO’s intelligence layer depends on these feeds. If a feed is broken or blocked, NECO misses updates that could affect your shipments, duties, and risk.

**Your goal:** Get as many sources as possible showing **healthy** in NECO, and document anything that must stay manual or wait on IT.

---

## How to think about “compliant” sources

| What we mean | Plain English |
|--------------|----------------|
| **Public, official data** | NECO uses **public** RSS feeds, APIs, and downloads that agencies or publishers **offer** for reuse (CBP, Federal Register, Congress.gov, etc.). |
| **Your responsibility** | Register for keys only where the provider **asks** you to (e.g. Congress.gov). Follow each site’s terms of use. Don’t share API keys. |
| **Not “compliance” in the legal audit sense** | This playbook is about **making feeds work** and using **allowed** public channels—not replacing your lawyer or trade counsel. |

If you want a formal legal review of data use, that’s a separate conversation with counsel.

---

## Where you work in NECO

1. **Signal Health** (in the app): see which feeds have data and which don’t.  
2. **Your technical teammate** (or contractor): updates URLs, keys, and server settings when you hand them clear instructions from this doc.

You can do **Steps 1–3** yourself. **Steps 4–5** are “assign to technical owner.”

---

## Step 1 — Run a health check (5 minutes)

**Do this:** Open NECO → go to **Signal Health** → click **Test all sources** (wait until it finishes).

**What you’re looking for:**

- **OK** = NECO successfully pulled items from that source. Good.
- **Empty** = NECO reached the source but got nothing (broken link, blocking, or no new items).
- **Fail** = Something errored.

Write down **which names are not OK**. That’s your working list.

---

## Step 2 — One key you should have (10 minutes)

**Congress (bills related to trade)**

1. Go to: **https://api.congress.gov/sign-up**  
2. Sign up for a free API key (if you haven’t already).  
3. Give the key **only** to whoever manages NECO’s server settings (`backend/.env`). They add: `CONGRESS_API_KEY=...`  
4. After they save and restart NECO, run **Test all sources** again — **CONGRESS_GOV** should show OK.

**You:** Keep the key private; rotate it if it was ever exposed.

---

## Step 3 — CBP rulings (CROSS) — finish automation (15 minutes)

NECO reads a **download file** CBP publishes (“What’s New” on the CROSS site). You already proved the format works.

**For full automation (no manual download every time):**

1. Open **https://rulings.cbp.gov/**  
2. Find **“What’s New”** → **All Latest Rulings**  
3. **Right-click** the **XML** button → **Copy link** (or “Copy link address”).  
4. Send that link to your technical owner with this instruction: *“Please set `CBP_CROSS_XML_URL` in NECO’s environment to this URL.”*  
5. Once that’s done, they can **remove** any temporary setting that pointed to a file on one person’s computer (`CBP_CROSS_LOCAL_FILE`).

**Until the URL is set:** NECO may rely on a **local file path** on one machine — that does **not** work for a shared server or overnight jobs. Getting the real URL fixes that.

*More detail (optional):* `docs/CBP_CROSS_SETUP.md`

---

## Step 4 — Assign to technical owner: “unblock” feeds (checklist to forward)

Copy this block to your IT / developer. They use the existing guides in `docs/` for exact URLs and env vars.

| Source | What’s wrong (typical) | What to try |
|--------|-------------------------|-------------|
| **USDA FSIS** | Often **403** (blocked) | Try `REGULATORY_NO_PROXY=1` on the server; if still blocked, consider FSIS API docs or email alerts as a backup *strategy* (not automatic in NECO today). |
| **White House RSS** | Was **404** | Config now uses `whitehouse.gov/presidential-actions/feed/` — if it breaks again, find the current feed on whitehouse.gov. |
| **The Loadstar (tier-6 RSS)** | Replaces Flexport blog | `theloadstar.com/feed/` — if it fails, update `sources_config.json`. |
| **Supply Chain Dive** | Was **403** on old URL | Config now uses `supplychaindive.com/feeds/news/` — if blocked again, try another network or contact the site. |
| **CBP duty rates / legal decisions / UBR** | Share **main trade RSS** | Same URL as CSMS in config; items dedupe in DB — not “broken” if counts look shared. |
| **USITC HTS** | Shows empty in a one-off test | Often **normal** until HTS release changes — verify with technical owner, not a broken feed. |

**Reference docs for them:**  
`docs/SPRINT20_SOURCE_SETUP_GUIDE.md`, `docs/SOURCE_VALIDATION_GUIDE.md`, `docs/REGULATORY_SOURCES_TROUBLESHOOTING.md`

---

## Step 5 — Keep it running (ongoing)

| Cadence | Action |
|---------|--------|
| **Weekly** | Open **Signal Health**; note any feed that flipped to empty or stale. |
| **After big news** | Run **Poll now** once if you want fresh pulls without waiting for the schedule. |
| **When a site redesigns** | Government sites change URLs — repeat Step 1 and send the broken names to your technical owner. |

---

## What “every source feeding NECO” really means

- **25 configured sources** — not all will be perfect forever (sites move, block bots, or publish rarely).  
- **Success** = **all Tier 1 (highest priority) sources** working, **Congress** keyed, **CROSS** on automatic XML URL, and a **clear plan** for each stubborn feed (fix URL vs. replace vs. accept gap).  
- **Tier 7 (advanced CROSS matching)** is **future enhancement** — it does not block “feeds into NECO.”

---

## One-page priority order (for you)

1. **Signal Health → Test all sources** → list problems.  
2. **Congress API key** → confirm with tech it’s on the server.  
3. **CROSS XML link** → copy from website → tech sets `CBP_CROSS_XML_URL`.  
4. **Forward Step 4 table** to tech until empty count is as low as possible.  
5. **Weekly** glance at Signal Health.

---

## Questions to ask your technical owner

- “Are **Poll** and **Process** running on a schedule (or manually), and is **Refresh HTS** run when we have shipment data?”  
- “Is **`.env`** only on our servers, never in email or chat?”  
- “After you change URLs or keys, did **Test all sources** go green for those names?”

---

**Last updated:** February 2026  
**Related:** `docs/SPRINT20_SOURCE_SETUP_GUIDE.md` (technical detail), `docs/CBP_CROSS_SETUP.md` (CROSS only)
