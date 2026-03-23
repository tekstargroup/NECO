# Sprint 13 Kickoff — UI: Analysis View + Review

**Sprint:** 13 (UI Part 1)  
**Goal:** Shipment detail shows full analysis with clear states; review flow (accept/reject/override) is real and usable.  
**Estimate:** 3–4 days

---

## Scope (Consolidated UI Sprint)

Sprint 13 now includes **all** analysis and review UI work. Apply your feedback and comments here.

### Part A: Analysis View (8 Sections)

| Section | Focus |
|---------|--------|
| **1. Outcome Summary** | Declared HTS, review status, flags. Clear, factual. |
| **2. Money Impact** | Duty paid vs alternative; $ estimates; "Could not resolve" when needed. |
| **3. Risk Summary** | Risk level, explanation, status labels (friendly, not technical). |
| **4. Structural Analysis** | What NECO evaluated; what it did not. |
| **5. PSC Radar** | Alerts per shipment; disclaimer. |
| **6. Enrichment Evidence** | Documents used; conflicts if any. |
| **7. Review Status** | Current status; actions (Submit, Accept, Reject, Override); history. |
| **8. Audit Trail** | Shipment ID, generated_at; collapsible resolver I/O. |

### Part B: Loading & Error States

- Empty/partial result → clear copy and Re-run
- Timeout → "Analysis is taking longer than expected. Re-run or check back later."
- Failed → error message + Re-run
- No dead ends

### Part C: Review UI

- **Status display:** DRAFT, REVIEW_REQUIRED, REVIEWED_ACCEPTED, REVIEWED_REJECTED
- **Accept / Reject:** With notes; wire to backend; update export gating
- **Override:** Audit warning, required justification, confirm
- **Review history:** Timeline of status changes, reviewer, notes, overrides

---

## Key Files

| Area | File |
|------|------|
| Analysis tab | `frontend/src/components/shipment-tabs/analysis-tab.tsx` |
| Reviews tab | `frontend/src/components/shipment-tabs/reviews-tab.tsx` (or equivalent) |
| Section definitions | `docs/SPRINT13_14_MAP.md` |
| Language guide | Sprint 11 / NECO UX map — no "AI," "confidence," "recommended" |

---

## Success Criteria

1. All 8 sections render real data when backend provides it
2. Empty/partial/timeout states have clear copy and Re-run
3. Sections 1–3 (Outcome, Money Impact, Risk) are clearly correct and readable
4. Review status displayed; Accept/Reject with notes wired; Override flow with audit warning; Review history visible
5. Manual acceptance: full path works

---

## Your Feedback

Use this sprint to apply all UI feedback. Sections 1–3 are highest priority; 4–8 "good enough" for MVP but should match the section definitions in SPRINT13_14_MAP.md.
