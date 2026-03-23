# Sprints 13–16 – High-Level Map

**Purpose:** What’s next after Sprint 12 (document-driven analysis). Includes section definitions and detailed task breakdowns for Sprints 13–16.

**Decisions locked for this map:** Same-user review for MVP (role checks later if needed). One export format for MVP. Sections 1–3 prioritized; 4–8 “good enough” for MVP; all eight defined below.

---

## Analysis View: 8 Sections Defined

Order is fixed. All sections visible in one vertical scroll. Language: compliance-grade (no “AI,” “confidence,” “recommended”; use “Requires review,” “Alternative identified,” “System analysis”).

### Section 1 — Outcome Summary

**Purpose:** Answer “What is the status of this analysis?” at a glance.

**Content:**
- **Declared HTS** – Per item or shipment-level: the HTS code(s) from the entry/document or current classification.
- **Review status** – One of: DRAFT, REVIEW_REQUIRED, REVIEWED_ACCEPTED, REVIEWED_REJECTED. Shown clearly (e.g. “Review Status: REVIEW_REQUIRED”).
- **Flags** – Short list of non-OK conditions: e.g. “PSC risk detected,” “Missing quantity,” “Requires review.” No hype; factual only.

**Display rules:** Always show review status. If there are blockers/flags from the analysis, list them. If none, state “No flags” or equivalent. Clear, neutral language.

**Data source:** `result_json.review_status`, `result_json.blockers`, item-level flags from classification/PSC/regulatory.

---

### Section 2 — Money Impact

**Purpose:** Show duty impact: declared vs alternative duty and any potential savings (or state no material difference).

**Content:**
- **When savings identified:** Declared duty (rate + dollar amount), alternative duty (rate + amount), potential savings (delta % and $), alternative HTS code. Per item when multiple items.
- **When no material difference:** “No material duty difference detected.” Optionally show declared duty and range of alternative duties (e.g. “Declared: 8.3%; Alternatives: 8.3%–8.5%”).

**Display rules:** Lead with the outcome (savings vs no difference). No “recommended action” or sales language. Money prominent but calm.

**Data source:** `result_json.items[].duty` (resolved_general_raw, resolved_special_raw, or backend equivalent); classification alternatives for “alternative HTS”; item value/quantity for dollar amounts.

---

### Section 3 — Risk Summary

**Purpose:** Make risk explicit and user-visible: level, short explanation, and (optionally) risk tolerance.

**Content:**
- **Risk level** – e.g. LOW / MEDIUM / HIGH or similar; can be derived from blockers and regulatory/classification signals.
- **Explanation** – One or two sentences: e.g. “Alternative classification differs at heading level.” “Historical entries show different chapter usage.” Factual only.
- **Risk Tolerance** – Dropdown: Conservative | Standard | Permissive. Expand for MVP: **Conservative** = flag more (e.g. any heading-level difference); **Standard** = typical flagging (e.g. chapter/heading divergence); **Permissive** = flag only when high confidence of material risk. Note: “Tolerance affects flagging, not computation.” Store preference (e.g. user or org level) for consistency.

**Display rules:** If there are risk flags/blockers, show level and explanation. If none, “No risk flags identified.” User should never be surprised by risk later.

**Data source:** `result_json.blockers`, regulatory_evaluations, PSC flags; optional backend “risk level” if present.

---

### Section 4 — Structural Analysis (What Was / Was Not Evaluated)

**Purpose:** Defensibility and transparency: explicitly show what NECO *did* evaluate (and what evidence was used) and what it *did not* evaluate. Critical for MVP.

**Content:**
- **What NECO evaluated:** Per item: declared HTS, alternative HTS (if any), and evidence used (e.g. “Commercial Invoice (page 1); extracted: quantity, value, description”). Short list of evaluation inputs (documents, fields, classification/duty sources).
- **What NECO did NOT evaluate:** Fixed, explicit list. For example: trade program eligibility (GSP, etc.); country-specific preferences; quota or safeguard measures; legal interpretation of HTSUS notes; valuation method; origin rules beyond declared COO. No legal causality; factual only.

**Display rules:** Two clear blocks: “What was evaluated” (items + evidence) and “What was not evaluated” (static list). Order: evaluated first, then not evaluated. Full chapter/heading breakdown can be expanded later.

**Data source:** `result_json.items[]` (hts_code, classification.primary_candidate); evidence_map or document refs; static copy for “did not evaluate.”

---

### Section 5 — PSC Radar

**Purpose:** Read-only intelligence on possible overpayment or historical divergence; no filing recommendation. Will become more relevant post-MVP; keep MVP version light.

**Content:**
- **When signals exist:** Historical divergence (e.g. different chapter/heading used historically). Structural reason (codes differ at X level; duties differ accordingly). Duty delta (historical avg vs declared; delta % and $).
- **Disclaimer:** “No filing recommendation is made. This analysis is for informational purposes only.” (Or similar.)
- **When no signals:** “No material duty difference detected” or “No PSC flags for this item.”

**Display rules:** Per item if multiple. Always include disclaimer when PSC content is shown. No recommendation language.

**Data source:** `result_json.items[].psc` (summary, alternatives, flags).

---

### Section 6 — Enrichment Evidence (Document Evidence)

**Purpose:** Show what the system pulled from the uploaded documents (Entry Summary, Commercial Invoice) so the user can see the evidence behind the analysis. Not “enrichment” in the abstract—concretely: which documents were used, what fields were extracted (e.g. line items, HTS, quantity, value), and whether any conflicts were found (e.g. two different values for country of origin). Conflicts are shown, not auto-resolved.

**Content:**
- **Documents used** – List of documents that fed the analysis (name, type).
- **Extracted fields** – Key fields taken from those docs (e.g. line items with HTS, quantity, value; invoice number; COO) and, if available, source (e.g. “Page 1,” “Line 12”).
- **Conflicts** – If the same field had multiple values (e.g. COO on two pages), show both and mark clearly: “Multiple values detected. Not auto-resolved.”

**Display rules:** Conflicts must be visually distinct. MVP: documents used + extraction errors if any + conflicts if present. Full source refs/snippets can be expanded later.

**Data source:** `result_json.evidence_map`, extraction_errors, document list; structured_data if exposed.

---

### Section 7 — Review Status

**Purpose:** Current review state, actions (submit for review, accept/reject, override), and history for accountability. Must be clean and user-friendly (current version is not).

**Content:**
- **Current status** – One clear line: DRAFT | REVIEW_REQUIRED | REVIEWED_ACCEPTED | REVIEWED_REJECTED. Created date and by whom.
- **Actions** – One primary action per state: “Submit for Review” (DRAFT); “Accept” / “Reject” with notes (REVIEW_REQUIRED); “Override Classification” (frictionful, with audit warning and justification). Buttons and flow must be obvious, not buried.
- **Review history** – Simple timeline or list: what happened when (submitted, accepted/rejected, override), who, and notes. Easy to scan.

**Display rules:** Clean layout: status first, then one clear CTA, then history. Override must show audit warning. Same-user flow for MVP. Avoid jargon and nested UI.

**Data source:** Review API (review record, status, history); override API for actions.

---

### Section 8 — Audit Trail

**Purpose:** Resolver inputs/outputs and optional audit replay for defensibility. Same as section 7: needs to be cleaner and more user-friendly (current version is not).

**Content:**
- **Summary line** – Shipment ID, analysis generated_at, HTS version (if available). One scannable line.
- **Resolver inputs** – HTS code(s), HTS version ID, other inputs used. Collapsible or secondary so it doesn’t dominate.
- **Resolver outputs** – General/special duty text, source level. Collapsible.
- **Export Audit Pack** – Single clear button/link to download audit bundle (Sprint 14/16).

**Display rules:** Lead with summary (who, when, what). Full I/O in expand/collapse or “Show details.” No wall of technical text by default.

**Data source:** `result_json` (shipment_id, generated_at); review/analysis APIs for resolver details if exposed.

---

## Sprint 13: Analysis View (MVP Critical Path)

**Goal:** Shipment detail reliably shows full analysis after “Analyze” runs, with clear states and MVP-ready UX.

**What’s already there (from Sprint 12):**
- Analysis tab: trigger Analyze, progress tracker (phases + countdown), poll for COMPLETE/FAILED
- 8-section result view (Outcome Summary, Money Impact, Risk Summary, Structural Analysis, PSC Radar, Enrichment Evidence, Review Status, Audit Trail)
- Link from shipments list to shipment detail

**Sprint 13 focus (high level):**
- **Polish the 8 sections** – Match Sprint 11 language and order; ensure all sections show real data when present (no generic “No X” when backend has content).
- **Loading and error states** – Refine beyond the progress tracker: empty/partial result, timeout, clear error copy and recovery (e.g. Re-run).
- **Outcome clarity** – Make “what happened” obvious: review status, money impact, and risk summary readable at a glance.
- **Success definition:** Create shipment → Upload docs → Analyze → See complete, accurate analysis on detail page with no dead ends.

**Rough scope:** 2–3 days. Mostly frontend polish and edge cases; backend already returns `result_json` and status.

**Sprint 13 — Detailed breakdown**

- **Section 1 (Outcome Summary):** Render declared HTS (per item or summary), review status from `result_json.review_status`, and blockers as flags (PSC risk, missing qty, etc.). If no blockers, show “No flags.” Match Section 1 definition above.
- **Section 2 (Money Impact):** When duty data exists, show declared vs alternative duty (rate + $), potential savings or “No material duty difference.” Use `items[].duty` and classification alternative; support multiple items. Match Section 2 definition; no recommendation language.
- **Section 3 (Risk Summary):** Derive risk level from blockers/regulatory; show short explanation. “No risk flags identified” when none. Risk Tolerance dropdown deferred to post-MVP unless trivial to add.
- **Sections 4–8 (good enough for MVP):** Section 4: items with HTS + primary alternative + one-line evidence; static “What NECO did not evaluate.” Section 5: PSC summary + disclaimer when present. Section 6: document list + extraction errors; conflicts if present. Section 7: review status + history (read-only if review API not wired yet). Section 8: shipment ID, generated_at, optional expand for resolver I/O.
- **Loading/error states:** If analysis fails, show error message and Re-run. If result is empty/partial (e.g. no items), show clear empty state. Timeout or poll failure: “Analysis is taking longer than expected. You can Re-run or check back later.”
- **Copy and order:** Align all section titles and body copy with Sprint 11 / NECO language guide. Order strictly 1 → 8.
- **Acceptance:** Create shipment → upload docs → analyze → see all 8 sections with real data where backend provides it; no dead ends; sections 1–3 are clearly correct and readable.

---

## Sprint 14: Document Upload + Export

**Goal:** Upload flow is solid and export (filing-prep bundle) is available from the UI, with correct gating.

**What’s already there (from Sprint 12):**
- Document upload on shipment (presign → mock upload or S3 → confirm); type per file (Entry Summary, Commercial Invoice, etc.).
- Backend: extraction and line item import from ES/CI; filing-prep/export APIs exist.

**Sprint 14 focus (high level):**
- **Upload UX** – Confirm flow for multiple files and types; clear success/error and doc list; any validation or limits (size, type) surfaced in UI.
- **Export button** – On shipment detail (e.g. Exports tab or Analysis/Review area): “Download filing-prep” (or equivalent) that calls backend and triggers download of the bundle.
- **Export gating** – Block or clearly warn when status is REVIEW_REQUIRED (per roadmap); show why export is blocked if applicable.
- **Success definition:** Upload ES + CI → Analyze → Export filing-prep bundle from UI; export blocked (or warned) when review required.

**Rough scope:** 1–2 days. Mix of frontend (export button, gating UI) and wiring to existing backend export API.

**Sprint 14 — Detailed breakdown**

- **Upload UX:** Confirm multi-file flow and type-per-file work; success shows doc in list with type and filename. On error (size, type, network), show clear message and retry/change file. Surface any backend validation (e.g. file type, size limit) in UI.
- **Export button:** Add “Download filing-prep” (or “Export for broker”) on Exports tab or Analysis/Review area. Call backend export API (e.g. GET or POST per existing API); trigger browser download. One format for MVP (choose PDF or CSV per backend capability).
- **Export gating:** Before calling export, check review status (or call an “export allowed?” endpoint). If REVIEW_REQUIRED (or other blocker), disable button or show modal: “Export is blocked until review is complete. Resolve review requirements in the Reviews tab.” List specific reasons if API returns them.
- **Exports tab:** If Exports tab is placeholder, add export button + short copy (e.g. “Download filing-prep bundle for broker handoff”). Link to Reviews tab when blocked.
- **Acceptance:** Upload ES + CI → Analyze → Export button downloads one filing-prep file; when review required, export is blocked with clear copy and path to fix.

---

## Sprint 15: Review UI + Polish

**Goal:** Compliance director can see review status, accept/reject with notes, and override (with audit warning) so the “review” step of the MVP path is real, not placeholder.

**What’s already there:**
- Reviews tab on shipment detail (likely placeholder or minimal).
- Backend: ReviewRecord, status (DRAFT | REVIEW_REQUIRED | REVIEWED_ACCEPTED | REVIEWED_REJECTED), override API with justification; review created at end of analysis.

**Sprint 15 focus (high level):**
- **Review status display** – Current status (DRAFT, REVIEW_REQUIRED, etc.), who/when if reviewed, and what’s blocking export if applicable.
- **Accept/reject** – Actions with notes (e.g. “Accept classification” / “Reject – needs verification”); call backend; update UI and possibly unblock export when status moves to REVIEWED_ACCEPTED.
- **Override UI** – Frictionful flow per Sprint 11: audit warning, required justification, confirm; wire to override API; show in review history.
- **Review history** – Timeline or list of status changes, reviewer, notes, overrides (so the flow is auditable from the UI).
- **Error and empty states** – Clear copy when no review yet, API errors, or invalid state transitions.
- **Success definition:** After analysis, user sees REVIEW_REQUIRED where applicable → accepts or rejects (with notes) or overrides (with justification) → status and export gating update correctly.

**Rough scope:** 1–2 days. Frontend-heavy; backend review/override APIs exist.

**Sprint 15 — Detailed breakdown**

- **Review status display:** On Reviews tab (and optionally in Analysis section 7), show current status (DRAFT, REVIEW_REQUIRED, REVIEWED_ACCEPTED, REVIEWED_REJECTED), created date, created by. If REVIEW_REQUIRED, show “Export is blocked until review is complete.”
- **Accept / Reject:** When status is REVIEW_REQUIRED, show “Accept classification” and “Reject” (or “Reject – needs verification”). Each action opens notes field (required for reject); submit calls backend; on success, refresh status and unblock export if status became REVIEWED_ACCEPTED. Same-user flow: any user with access can accept/reject (no reviewer ≠ submitter check for MVP).
- **Override UI:** “Override Classification” button when appropriate (e.g. when REVIEW_REQUIRED or after reject). Flow: select/new HTS, required justification text, audit warning (“This action will be logged and auditable”), confirm. Call override API; on success, add entry to review history and refresh.
- **Review history:** List or timeline of events: created, submitted for review, reviewed (accepted/rejected + reviewer + notes), override (original HTS, new HTS, justification, by whom, when). Read-only; newest first or chronological.
- **Error and empty states:** No review yet (e.g. analysis not run) → “No review record. Run analysis to create one.” API errors → show message and retry. Invalid transition → “This action is not available in the current status.”
- **Acceptance:** After analysis with REVIEW_REQUIRED, user can accept (with optional notes) or reject (with notes) or override (with justification); status and export gating update; history is visible.

---

## Sprint 16: MVP Hardening & Polish

**Goal:** The full path is reliable, explainable, and ready for a limited pilot or stakeholder demo—not “feature complete” in every corner, but no obvious dead ends or broken states.

**What’s already there:**
- Dev auth, shipments, documents, analysis, (after 15) review/override, (after 14) export. Backend org-scoping, entitlement, eligibility.

**Sprint 16 focus (high level):**
- **End-to-end reliability** – Happy path (create → upload → analyze → review → export) works without surprises; timeouts and failures show clear messages and recovery (e.g. Re-run, retry export).
- **Empty and edge states** – No shipments yet; shipment with no docs; analysis refused (eligibility/entitlement); analysis failed; review required blocking export. Each has consistent copy and, where relevant, a next action.
- **Language and tone** – Align with Sprint 11 / NECO UX map: no “AI” or “confidence”; use “Requires review,” “Alternative identified,” “System analysis,” etc.
- **Optional: UI QA gate with dev auth** – Playwright (or similar) that logs in via dev-login, then runs a small set of UI checks (list, open shipment, maybe trigger analyze). Unblocks regression confidence without Clerk.
- **Optional: Clerk JWT validation (pre-pilot)** – If first real users will use Clerk, validate JWT and org in backend so production auth is ready; can be minimal (validate + 403 on invalid).
- **Success definition:** A compliance director can complete the MVP path in under 5 minutes (login → create/upload → analyze → review → export) with no unexplained errors; edge cases have clear copy and next steps.

**Rough scope:** 1–2 days. Mostly frontend polish, copy, and optional QA/auth work; no new features.

**Sprint 16 — Detailed breakdown**

- **End-to-end reliability:** Run full path (create → upload → analyze → review → export). Fix any broken links, missing loading states, or silent failures. Timeouts: show “Request timed out. Please try again (Re-run analysis / Retry export).” Network errors: clear message and retry.
- **Empty states:** No shipments → “No shipments yet. Create your first shipment to get started.” Shipment with no docs → Documents tab explains “Upload Entry Summary or Commercial Invoice to run analysis.” Analysis refused (eligibility/entitlement) → show refusal reason and what’s missing. Analysis failed → show error and Re-run. Export blocked → show “Export blocked: [reason]” and link to Reviews or Analysis as appropriate.
- **Language and tone:** Audit UI copy against NECO language guide: remove “AI,” “confidence,” “recommended,” “smart”; use “Requires review,” “Alternative identified,” “System analysis,” “Detected,” “Observed.” Section titles and body copy consistent with Section definitions above.
- **Optional — UI QA gate with dev auth:** Script (e.g. Playwright) that hits `/dev-login`, clicks “Login as test user,” then: load shipments list, open one shipment, optionally trigger analyze or check Analysis tab. Save storage state for dev-auth so gate can run without Clerk. Integrate into `sprint12_qa_gate.sh` when `USE_DEV_AUTH=1`.
- **Optional — Clerk JWT validation:** If first pilot uses Clerk, ensure backend validates Clerk JWT and org; return 401/403 on invalid or missing token. No new UI; backend-only.
- **Acceptance:** Full MVP path completes in under 5 minutes with no unexplained errors; every edge state has clear copy and a next action; optional gate and auth ready if chosen.

---

## What’s Everything That Should Be Next?

| Order | Sprint   | One-line focus                                                                 |
|-------|----------|--------------------------------------------------------------------------------|
| 1     | **13**   | Analysis view polish: 8 sections, loading/errors, outcome clarity.            |
| 2     | **14**   | Upload UX confirmation + Export button + REVIEW_REQUIRED gating.               |
| 3     | **15**   | Review UI: status, accept/reject with notes, override with audit, history.    |
| 4     | **16**   | MVP hardening: E2E reliability, empty/edge states, language, optional QA/auth.|

---

## MVP: What’s Needed (Detailed Opinion)

**MVP definition (from roadmap):** Core happy path in &lt; 5 minutes — log in → create shipment (or upload CI) → see analysis → review (accept/reject) → export filing-prep for broker.

**Must-have for MVP (in order):**

1. **Analysis visible and trustworthy (13)** – The 8 sections are the product. If they’re empty, wrong, or confusing, nothing else matters. Polish so outcome, money impact, and risk are obvious; loading and errors don’t leave the user stuck.
2. **Export usable (14)** – Without “Download filing-prep,” there’s no handoff to the broker. Export button + gating (REVIEW_REQUIRED) makes the workflow complete. Upload UX confirmation is part of “create shipment or upload CI” and should feel solid.
3. **Review real (15)** – If the director can’t accept/reject or override with justification, “review” is theater. Review status, actions, and history make the system defensible and close the loop with export (accept → export allowed when not blocked).
4. **No broken paths (16)** – Edge cases (no data, refused, failed, blocked export) need clear copy and one obvious next step. Language should match compliance tone. Optional: automated UI smoke test and Clerk-ready auth so you can invite one real org without last-minute surprises.

**Nice-to-have but not MVP-blocking:** Risk Tolerance dropdown (Conservative/Standard/Permissive) in section 3; full audit-pack export in UI; reviewer ≠ submitter enforcement in UI; entitlement usage beyond “X of 15”; multiple formats for filing-prep (CSV vs PDF). Those can follow in a “post-MVP polish” sprint.

**Summary:** 13 → 14 → 15 → 16 gets you to a shippable MVP: analysis you can trust, export you can use, review you can defend, and a path that doesn’t break in front of a stakeholder.

---

**Next:** Start with Sprint 13 — implement section definitions 1–3 in full, sections 4–8 “good enough,” plus loading/error states and copy pass.

---

## What's Next After 16

After MVP hardening (Sprint 16), the backlog continues with post-MVP sprints. See **[docs/SPRINT17_PLUS_BACKLOG.md](SPRINT17_PLUS_BACKLOG.md)** for:

| Sprint | Focus |
|--------|-------|
| **17** | User-Selectable Analysis Preferences |
| **18** | Bulk Import (zip/folder) |
| **19** | Duty Rates Accuracy + Section 301 Overlay |
| **20** | Compliance Signal Engine (regulatory monitoring, PSC Radar alerts) |

The Compliance Signal Engine (Sprint 20) ingests CBP, Federal Register, USTR, and CROSS rulings; classifies and scores signals; and produces actionable PSC Radar alerts. See [docs/COMPLIANCE_SIGNAL_ENGINE.md](COMPLIANCE_SIGNAL_ENGINE.md) and [docs/REGULATORY_MONITORING.md](REGULATORY_MONITORING.md).

---

## Sprint Backlog / Open Questions

**Entitlement wording and model (important for next sprint):**
- Is the monthly limit **per shipment** or **per line item**? Current implementation: per shipment (each analysis start consumes 1 entitlement). Need to review and clarify in UI copy (e.g. "X of 15 shipments" vs "X of 15 analyses").
