# Phase 6 — Pre-launch smoke checklist and user test script

**Master copy (Phase 6 + pre-flight + QA harness inventory + implementation list):** [PHASE6_MANUAL_TESTING_AND_QA_HARNESS.md](./PHASE6_MANUAL_TESTING_AND_QA_HARNESS.md). **PDF:** run `python scripts/generate_phase6_qa_pdf.py` → `output/PHASE6_QA_Harness_NECO.pdf`.

Run **6A smoke** before external user sessions. Use **6B** during sessions. If you hit a P0 trust break, stop and fix before continuing.

**Local dev-login prerequisite:** With `NEXT_PUBLIC_DEV_AUTH=true`, `NEXT_PUBLIC_API_URL` must point at your running API (see `frontend/.env.example`). Backend `ENVIRONMENT` must be `development`, `dev`, or `local` so `/api/v1/auth/dev-token` exists. Seed the Sprint 12 dev user/org (`./scripts/sprint12_loop.sh` with Docker, or `backend/scripts/seed_sprint12_dev_login.py`) or authenticated calls after login will return 403.

## 6A — Trust-focused smoke pass (operators)

Check each item and note pass/fail.

1. **Snapshot vs Reviews**  
   Upload docs → run analysis → open **Reviews**. Confirm line items come from the review **snapshot** (`snapshot_json`), not live analysis. If you re-ran analysis after the review was created, confirm a drift warning appears when applicable.

2. **Accept → knowledge**  
   Accept a review. Confirm the path goes through the API (no silent local-only state). Optionally verify a `product_hts_map` row or server logs for knowledge recording.

3. **422 not 500**  
   Trigger a known client/validation failure on analyze (e.g. missing required preconditions your API documents). Response must be **422** (or appropriate 4xx), not **500**.

4. **No `dev_context` in non-local**  
   On staging/production (or any `ENVIRONMENT` outside `development`/`dev`/`local`), inspect analysis status JSON in the network tab: **`dev_context` must be absent**.

5. **Duplicate analyze (optional)**  
   While analysis is **RUNNING**, confirm the UI does not start a second overlapping run without an explicit re-run.

6. **Export parity**  
   After accept, generate an **export** (audit pack / broker prep as you use). Open JSON and/or CSV. Confirm review state and line-level outcomes **match** what the Reviews tab showed (HTS, outcomes, counts—no cross-surface drift).

---

## 6B — User test script (5–8 tasks)

Adapt filenames and org to your pilot.

1. Create a shipment and upload a **commercial invoice** (and any second doc your flow expects).  
2. Run **analysis**; wait until complete. Note anything confusing in progress or errors.  
3. Open **Analysis** tab: scan classification, duty, regulatory cards for one “hard” line. Open the detail drawer if present.  
4. Open **Reviews** tab: confirm items match what you expect from analysis; note any mismatch.  
5. Make **per-line review decisions** (accept/override as supported), then **accept** the review at shipment level.  
6. Download or open an **export**; confirm it matches Reviews (Phase 6A item 6).  
7. (Optional) **Re-run analysis** on the same shipment; return to Reviews and confirm snapshot vs live behavior matches your expectations.  
8. (Optional) **Second user / second org** (if multi-tenant): repeat sign-in and confirm org scoping.

---

## Observation log (template)

| Time | Task # | Quote or behavior | Severity (P0–P3) | Hypothesis |
|------|--------|-------------------|------------------|------------|
|      |        |                   |                  |            |

**P0 trust breaks (stop testing):** snapshot vs export mismatch; accept not persisted; auth bypass; data from another org visible.

---

## Stop rule

If any **P0** appears, **stop sessions**, fix, re-run **6A smoke**, then resume user tests.
