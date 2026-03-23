# Sprint 13: Analysis View Polish — Status

**Started:** February 24, 2026

---

## Goal

Shipment detail reliably shows full analysis after "Analyze" runs, with clear states and MVP-ready UX.

---

## Completed

### Section 1 (Outcome Summary)
- Declared HTS, review status, blockers/flags
- Origin mismatches from `result_json.origin_mismatches` shown as flags with dollar framing
- COO confirmation prompt
- "No flags" when none

### Section 2 (Money Impact)
- Declared vs alternative duty, duty from Entry Summary, Section 301
- Per-item `origin_mismatch` display (CI vs ES country, duty paid)
- Potential savings identified / no material duty difference
- Removed sales language ("Are you leaving money on the table?")
- Duty disclaimer

### Section 3 (Risk Summary)
- Replaced "Confidence" with "Extraction quality" (Sprint 11 language)
- Replaced "Risk: ~X%" with "Divergence: ~X%"
- Risk level and explanation from blockers

### Sections 4–8
- Section 4: Structural Analysis — what was / was not evaluated
- Section 5: PSC Radar — disclaimer, alternatives
- Section 6: Renamed to "Enrichment Evidence" with document evidence subtitle
- Section 7: Review Status
- Section 8: Audit Trail — added collapsible "Show resolver details"

### Language (Sprint 11)
- "Confidence" → "Extraction quality"
- "What would increase confidence" → "What would improve certainty"
- "Alternative codes (risk %)" → "Alternative codes (divergence vs declared)"

### Loading/Error States (already in place)
- Analysis fails → error message + Re-run
- No line items → NoLineItemsCard with clear copy
- Timeout (4 min) → "Analysis is taking longer than expected" + Re-run / Check for results

---

## Mark Complete When

1. All 8 sections render real data when backend provides it — **Done**
2. Empty/partial/timeout states have clear copy and Re-run — **Done**
3. Sections 1–3 (Outcome, Money Impact, Risk) are clearly correct and readable — **Done**
4. Manual acceptance: full path works — **Pending**

---

## Manual Acceptance Checklist

- [ ] Create shipment → Upload ES + CI → Analyze → See all 8 sections with real data
- [ ] Verify origin mismatch displays when CI vs ES COO differs
- [ ] Verify duty from Entry Summary and Section 301 display
- [ ] Verify "No flags" when no blockers
- [ ] Verify timeout message at 4 min with Re-run / Check for results
- [ ] Verify analysis failure shows error + Re-run
- [ ] Verify no "AI," "confidence," or "recommended" language
