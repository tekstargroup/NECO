# Reconciliation: Other-Agent Sprints 13–16 vs This Session’s Improvements

This doc records what comes from **the other agent’s** Sprint 13–16 work vs **this session’s** improvements, so we avoid rework and don’t cancel either set.

**Status:** The codebase currently contains **both**. No conflicts found; wording is aligned (e.g. “Re-run” used consistently).

---

## From the other agent (Sprint 13–16) — keep as-is

- **Analysis tab:** “Re-run” (not “Re-analyze” / “Re-run analysis”); “Analysis failed” (not “didn’t complete”); loading message: “Analysis is running. If it takes longer than expected, you can Re-run or check back later.”
- **Analysis:** Simplified empty-state copy for no line items; PSC disclaimer when PSC content is shown; Section 6 conflict display: “Multiple values detected. Not auto-resolved.” when blockers mention conflicts.
- **Exports tab:** “Go to Reviews tab” when export is blocked by REVIEW_REQUIRED; `onSwitchToReviews` passed from `ShipmentDetailShell`.
- **ShipmentDetailShell:** Header button “Re-run” (not “Re-run analysis”); passes `onSwitchToReviews` to `ExportsTab`.
- **Overview tab:** “Re-run” in the analysis-failed hint.
- **Documents tab (empty state):** “Upload Entry Summary or Commercial Invoice to run analysis.”
- **Reviews tab (Sprint 15):** Status display, “Accept classification” / “Reject – needs verification”, reject flow with required notes, review history, override section with audit warning.
- **Backend:** PATCH `/api/v1/reviews/{review_id}` for accept/reject; `ReviewListItem` extended with `reviewed_at`, `reviewed_by`, `review_notes`, `prior_review_id`.

---

## From this session’s improvements — do not remove

- **Documents tab:** Submit button to lock in document type (dropdown + Submit → “Saved”); View on the left; PDF vs Excel icons (`DocumentIcon`: FileText for PDF, FileSpreadsheet for .xlsx/.xls/.csv); Delete (trash) with confirm: “Are you sure you want to delete this document? Existing analysis will be cleared and you will need to re-run analysis after re-uploading.”; `pendingType` state and `handleSubmitType` / `handleDelete`.
- **Backend documents:** DELETE `/api/v1/shipment-documents/{document_id}` (org-scoped).
- **Analysis tab (recovery):** When analysis fails or there are no line items: “What you can do” list and Re-run button; Dismiss for generic API error; `no_items_hint`: when `files_not_found`, show “Document files weren’t found on the server…” and re-upload instructions; extraction_errors recovery copy: “Fix document types… then use Re-run at the top…”
- **Backend analysis:** `no_items_hint` (`files_not_found` | `extraction_returned_no_lines`) in `result_json`; extra mock_uploads path fallbacks; Excel fallback to build line items from sheet when Claude returns none; header-row detection for “Unnamed” columns.
- **Shipment list:** Row click opens shipment; delete button uses `stopPropagation`.
- **ShipmentDetailShell:** Default tab “Documents”; on Documents tab when not eligible, show “Upload documents to get started.” instead of full “Not eligible” badge.
- **Upload flow:** Categorize block above drag area; smart default doc type from filename; success message after upload.

---

## Wording alignment (already consistent)

- Use **“Re-run”** everywhere (analysis, overview, header, no-line-items card). Do not reintroduce “Re-analyze” or “Re-run analysis” in those places.
- Use **“Analysis failed”** for the analysis error_message block (not “Analysis didn’t complete”).

---

## If you merge or re-apply the other agent’s branch

1. **Do not overwrite:** Documents tab (Submit, View left, icons, Delete, confirm), analysis-tab recovery blocks and `no_items_hint` UI, backend DELETE document and `no_items_hint`/path/Excel fallback logic.
2. **Keep from other agent:** “Re-run” copy, “Analysis failed”, timeout message, PSC disclaimer, Section 6 conflict display, Export “Go to Reviews tab”, `onSwitchToReviews`, Overview “Re-run”, Documents empty-state line, Reviews tab Sprint 15 and backend PATCH review.
3. **QA:** Run `USE_DEV_AUTH=1 ./scripts/sprint12_qa_gate.sh` (with Docker, backend, frontend and `NEXT_PUBLIC_DEV_AUTH=true`).
