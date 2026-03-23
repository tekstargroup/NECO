# Manual QA Checklist — Sprints 13 & 14

Use this checklist after implementing Sprints 13 and 14. Run through every item manually in your local (or staging) environment.

**Prerequisites:** Backend and frontend running (e.g. `./start_neco.sh` or equivalent). Dev auth or Clerk configured so you can log in.

---

## Sprint 13 — Analysis View (8 Sections)

### Access and flow

- [ ] **Login** — Sign in (dev-login or Clerk). No errors; dashboard or shipment list loads.
- [ ] **Create shipment** — Create a new shipment (if needed). Shipment appears in list; can open it.
- [ ] **Documents tab** — Upload at least one **Entry Summary** (PDF) and one **Commercial Invoice** (XLSX or CSV). Documents list shows them with type and filename.
- [ ] **Run analysis** — Go to Analysis tab. Click **Run analysis** (or equivalent). Request starts.
- [ ] **Progress / tracker** — While analysis runs, a progress indicator or phase tracker is visible (e.g. phases like “Uploading”, “Classifying”, “Evaluating” or a countdown). No blank screen.
- [ ] **Analysis completes** — When status is **COMPLETE**, the full analysis view (8 sections) is visible without needing to click “Show details” (or equivalent).

### Section 1 — Outcome Summary

- [ ] **Declared HTS** — Each line item (or shipment) shows declared HTS code(s). Source is clearly from entry/document or current classification.
- [ ] **Review status** — A single review status is visible: one of DRAFT, REVIEW_REQUIRED, REVIEWED_ACCEPTED, REVIEWED_REJECTED (e.g. “Review Status: REVIEW_REQUIRED”).
- [ ] **Flags** — If the run produced blockers or flags (e.g. “PSC risk”, “Missing quantity”, “Requires review”), they are listed. If none, “No flags” (or equivalent) is shown. Wording is factual, not salesy.

### Section 2 — Money Impact

- [ ] **When savings identified** — Declared duty (rate and $), alternative duty (rate and $), potential savings (delta % and $), and alternative HTS are shown per item where applicable.
- [ ] **When no material difference** — “No material duty difference detected” (or similar) is shown; no misleading savings messaging.

### Section 3 — Risk Summary

- [ ] **Risk level / explanation** — If risk flags exist, a risk level (e.g. LOW / MEDIUM / HIGH) and short explanation are shown. If none, “No risk flags identified” (or equivalent).
- [ ] **Risk Tolerance dropdown** — Dropdown is present with: **Conservative** | **Standard** | **Permissive**. Short description or tooltip explains that tolerance affects flagging, not computation. Changing the dropdown does not break the page (UI-only for MVP).

### Section 4 — What Was / Was Not Evaluated

- [ ] **What was evaluated** — Block lists items and evidence used (e.g. documents, fields, classification sources). Matches the run (items + evidence).
- [ ] **What was not evaluated** — A fixed list is shown (e.g. trade program eligibility, country-specific preferences, quota/safeguards, legal interpretation of HTSUS notes, valuation method, origin rules beyond declared COO). No legal causality; factual only.

### Section 5 — PSC Radar

- [ ] **Content** — When PSC signals exist: historical divergence and/or duty delta described. When none: “No material duty difference” or “No PSC flags” (or equivalent).
- [ ] **Disclaimer** — When PSC content is shown, a disclaimer is visible (e.g. “No filing recommendation is made. This analysis is for informational purposes only.”).

### Section 6 — Document Evidence

- [ ] **Title/copy** — Section is clearly “Document Evidence” (or equivalent). Copy explains that evidence comes from uploaded documents.
- [ ] **Documents used** — List of documents used in the analysis is visible.
- [ ] **Errors/conflicts** — Any extraction errors or conflicts from documents are listed (or “None” if applicable).

### Section 7 — Review Status

- [ ] **Single status line** — One clear line for overall review status (consistent with Section 1). No duplicate or conflicting status.

### Section 8 — Audit Trail

- [ ] **Summary** — Shipment ID, generated_at (or equivalent), and warning/flag count (or “No warnings”) are visible. Layout is compact and readable.

### Edge cases (Sprint 13)

- [ ] **Empty state** — For a run with no items in `result_json` (or equivalent), an empty state is shown: message to upload ES/CI and Re-run (or similar). No raw JSON dump or crash.
- [ ] **Re-run when FAILED** — If analysis fails (FAILED status), a Re-run (or “Run again”) action is available and triggers a new run.
- [ ] **Error message** — When analysis fails, an error message is shown (e.g. “Analysis failed: …”) and is user-readable.

### Decision validation (MANDATORY)

For each flagged item, test manually. If **any** answer is no → UI is not done.

- [ ] **1. Why surfaced?** — Can I explain in 1 sentence why NECO surfaced this item?
- [ ] **2. Why alternative?** — Can I explain why the alternative HTS might be better?
- [ ] **3. What risk?** — Can I explain what the risk is if I'm wrong?
- [ ] **4. Decide fast** — Can I decide accept vs reject in under 30 seconds?

### Time-to-value

- [ ] **Full flow** — Login → analysis → first decision → export in < 5 minutes.
- [ ] **First decision** — Understand and act on one item in < 60 seconds. If not: UI too heavy or explanation too weak.

---

## Sprint 14 — Upload UX and Export

### Documents tab (Upload UX)

- [ ] **Multi-file select** — Can select multiple files at once (file picker or drag-and-drop). Allowed types: PDF, Word (.docx), Excel (.xlsx, .xls, .csv).
- [ ] **Type per file** — Each pending file has a document type selector (Entry Summary, Commercial Invoice, Packing List, Data Sheet). Default is sensible (e.g. Commercial Invoice); user can change before upload.
- [ ] **Upload success** — After uploading, a short success message appears (e.g. “Uploaded N file(s).”) and the document list refreshes with the new files. Success message disappears after a few seconds.
- [ ] **Upload error** — If upload fails (e.g. network, validation), an error message is shown and is clear (e.g. file type/size or “Cannot reach API”).
- [ ] **Helper text** — Helper text is visible (e.g. “Upload Entry Summary (PDF) and Commercial Invoice (XLSX) for best results.”). Document list shows filename and document type for each doc.

### Exports tab — Gating and copy

- [ ] **Review list** — Exports tab loads and shows a list of reviews for the shipment (from Analysis). Each review shows ID and status (e.g. REVIEW_REQUIRED, REVIEWED_ACCEPTED).
- [ ] **REVIEW_REQUIRED gating** — When the **selected** review has status **REVIEW_REQUIRED**:
  - A clear banner is shown with item count when available: e.g. “X items require review before export is available.“
  - CTA: **“Go to Review“** (links to Reviews tab).
  - The **Download filing-prep** (primary) button is **disabled**.
  - User can still switch to another review; if that review is not REVIEW_REQUIRED, the banner is not shown and the button is enabled.
- [ ] **Primary action** — The main export action is “Download filing-prep” (broker-prep bundle). “Generate Audit Pack” is available as secondary (outline button).

### Exports tab — Generate and download

- [ ] **Generate broker-prep** — With a review that is **not** REVIEW_REQUIRED, click “Download filing-prep”. Request starts; “Generating…” (or similar) is shown. No error if backend is healthy.
- [ ] **Export completes** — When the export completes (status COMPLETED), “Latest Export” card shows type (e.g. broker-prep), status COMPLETED, and a **Download filing-prep** (or “Download Export”) button that is **enabled**.
- [ ] **Export blocked** — If you trigger export for a review that is REVIEW_REQUIRED (e.g. by switching after opening the tab), the backend may return BLOCKED; the card shows blocked reason and the Download button remains disabled for non-COMPLETED exports.
- [ ] **Download (S3)** — If your environment uses S3, clicking Download opens or downloads the filing-prep bundle (zip with JSON/CSV/PDF or equivalent). File name and content are correct.
- [ ] **Download (local / no S3)** — If your environment uses local export storage (no S3):
  - Clicking Download should still work: the app uses the stream endpoint with auth and triggers a zip download (e.g. `filing-prep-<export_id>.zip`).
  - No 422 “Download URL is unavailable in local export storage mode” from the UI; the error is not shown to the user and the file is delivered via the stream endpoint.

### Exports tab — Refresh and status

- [ ] **Refresh status** — “Refresh Status” (or equivalent) updates the latest export status without leaving the page.
- [ ] **Error display** — If getting download URL or generating export fails, the error message is shown in the red banner and is readable.

---

## Quick smoke (both sprints)

- [ ] **No console errors** — Browser console has no uncaught errors while doing the above flows.
- [ ] **No layout break** — Analysis view and Exports/Documents tabs render without overlapping or broken layout on a normal viewport.
- [ ] **Navigation** — Can move between Shipments list, shipment detail, Documents, Analysis, Reviews, and Exports tabs without losing state or getting stuck.

---

## Sign-off

- [ ] **Sprint 13** — All Section 1–8, edge-case, decision validation, and time-to-value items above passed.
- [ ] **Sprint 14** — All Upload UX and Export items above passed.
- [ ] **Notes:** _(Add any environment-specific notes, e.g. “Tested with local export storage only” or “S3 tested in staging.”)_
