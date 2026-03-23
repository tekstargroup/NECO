# NECO — Analysis Page UI Rebuild Spec (Cursor Ready)

**Product goal:** Rebuild the shipment Analysis page so a compliance manager, founder, or CFO can understand the situation and act in under 10 seconds.

**Primary actions:** Review items, Approve recommendation, Export / send to broker

**Primary UX principles:** Show money first, Show recommendation second, Show evidence third, Collapse everything else

---

## Page Architecture (Exact Order)

1. Sticky page header
2. Executive decision strip
3. PSC Radar table
4. Money impact panel
5. Why this applies / evidence summary
6. Collapsible advanced sections
7. Sticky footer action bar on long pages

---

## 1. ShipmentAnalysisHeader (Sticky)

- **Content:** Shipment/PO number, analysis status, eligibility badge, timestamp, Re-run, Export, Review Items
- **Layout:** Full-width, left: metadata, right: action buttons
- **Tailwind:** `sticky top-0 z-30 bg-white/95 backdrop-blur border-b px-6 py-4 flex items-center justify-between`
- **CTAs:** Review Items (primary), Export to Broker (secondary), Re-run (tertiary/ghost)

---

## 2. DecisionSummaryStrip (Hero)

**5 cards:** Potential Savings | Recommended Action | Confidence | Risk Level | Items Requiring Review

- **Potential Savings:** Most visually prominent (larger card)
- **Layout:** `grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4`
- **Card style:** `rounded-2xl border bg-white shadow-sm p-5` — large number on top, short label below

**Copy rules:**
- NOT: "Could not confidently pick one" → USE: "Best alternative identified. Review recommended."
- NOT: "Needs your review" → USE: "2 items require approval before export."
- NOT: "Risk level: Requires review" → USE: "Medium risk — review recommended before filing."

---

## 3. PscRadarPrimaryTable (Core)

**Columns:** Item | Product Description | Declared HTS | Recommended HTS | Estimated Savings | Confidence | Risk | Reason | Actions

**Row actions:** Accept | Override | View Evidence

**Behavior:** Sort by estimated savings desc, then confidence desc. Highlight Recommended HTS. Savings in bold. Confidence/Risk as color-coded badges.

**Toolbar:** Search, filter by confidence/risk, expand all evidence toggle

---

## 4. MoneyImpactPanel

- **Left:** Large total number + short explanation
- **Right:** Vertical list of per-item savings
- **Example:** Total $26,875 | Item 1: $20,425, Item 2: $6,450
- **Support copy:** "Based on identified alternative classifications. Confirm with broker before filing."

---

## 5. WhyThisAppliesPanel (Trust Layer)

Per item: Short explanation (max 2 lines), evidence chips (Entry Summary, Commercial Invoice, HTS Notes, CBP Ruling, etc.)

---

## 6. AdvancedAnalysisAccordion (Collapsed by Default)

Sections: Structural Analysis, Full Evidence, Enrichment Evidence, Review Status, Audit Trail, Resolver Details, Raw Flags

All default collapsed. Use accordion with clean labels.

---

## 7. AnalysisActionBar (Sticky Footer)

Buttons: Review Items | Approve All Safe Recommendations | Export to Broker | Save for Later

Appears when user scrolls below hero. `sticky bottom-0 z-30 border-t bg-white/95 backdrop-blur`

---

## Visual Rules (Non-Negotiable)

- No long paragraphs
- Max 2 lines per explanation
- Numbers must be bold and large
- Tables > text
- Default collapsed sections
- Conservative palette: navy/slate, green (safe), amber (review), red (high risk only)

---

## Copy Rules

**Good:** Potential Savings, Recommended HTS, Review Recommended, Medium Risk, Evidence Available, Ready to Export

**Bad:** Outcome Summary, Structural Analysis, Could not confidently pick one, Needs your review, What was considered and reviewed

---

## Success Criteria

User can answer within 10 seconds:
1. How much money is at stake?
2. What does NECO recommend?
3. How risky is it?
4. What do I do next?
