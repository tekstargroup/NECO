# NECO — Next Steps: From Process to Decision Product

**Purpose:** Clear, actionable guide to close the gap between "analysis works" and "user can confidently approve or reject."

**Created:** February 2026

---

## The Gap

Right now NECO has:
- Strong engine
- Cleaner UI
- Good process

But it has **not** built a **decision product**. The product is done when a compliance manager says: *"I understand this, I trust it, I'll act on it."*

Missing piece: **explainability + evidence + control**

---

## Priority Order (Do in This Order)

### 1. Rename Language (Quick Win)

| Current | Replace With |
|---------|-------------|
| Recommended HTS | **Alternative HTS identified** (or "Alternative HTS identified for review") |
| Confidence | **Evidence strength** |
| Risk | **Review level** |

**Scope:** Search and replace across Analysis tab, Reviews tab, Recommendation drawer. Same meaning, safer language.

---

### 2. Build Real Evidence Layer

**Status:** Implemented (Feb 2026). Evidence mapping model is in place:
- **DB tables:** source_documents, document_pages, extracted_fields, authority_references, recommendation_evidence_links, recommendation_summaries
- **API:** GET `/api/v1/shipments/{id}/analysis/items/{item_id}/evidence` returns evidence bundle
- **Service:** RecommendationEvidenceService derives from result_json when no structured evidence; uses DB when populated
- **Drawer:** Accepts evidenceBundle with supporting/conflicting/warning, document_refs, authority_refs

**Next:** Populate structured evidence during analysis (extract fields, link to items, create recommendation_summaries). See [EVIDENCE_MAPPING_MODEL.md](EVIDENCE_MAPPING_MODEL.md).

---

### 3. Add Per-Item Decision Control

**Current problem:** Accept/Reject applies to whole shipment. Real world: 1 item may be correct, 1 may be risky. No one approves everything blindly.

**Needed:**
- **Per item:** Accept | Override | Skip (or "Leave for later")
- **Optional:** "Accept all safe items" (only when high evidence strength)

**Scope:** PSC table row actions + Reviews tab. Wire to backend if per-item review API exists; otherwise design for it.

---

### 4. Improve Explanation Drawer

**Current:** Drawer has structure but content is derived from limited data.

**Add/strengthen:**
- **Why it fits** — 3–5 bullets with real rationale (not generic)
- **Why it may not** — 2–4 bullets on uncertainty
- **What data supports it** — Use real evidence (see #2) when available

---

### 5. Export Gating — Clear Block + CTA

**Current:** Block export when REVIEW_REQUIRED.

**Add:**
- Message: *"2 items require review before export is available"*
- CTA: **"Go to Review"** (links to Reviews tab)

---

### 6. Add Decision Validation Test (Sprint 13 Checklist)

**New section — Decision validation (MANDATORY)**

For each flagged item, test manually:

1. **Can I explain in 1 sentence why NECO surfaced this?**  
   → If no: UI is not done

2. **Can I explain why the alternative HTS might be better?**  
   → If no: UI is not done

3. **Can I explain what the risk is if I'm wrong?**  
   → If no: UI is not done

4. **Can I decide accept vs reject in under 30 seconds?**  
   → If no: UI is not done

---

### 7. Time-to-Value Tests

| Test | Target |
|------|--------|
| Full flow (login → export) | < 5 minutes |
| **First decision** (understand + act on one item) | **< 60 seconds** |

If first decision takes > 60 seconds: UI is still too heavy or explanation too weak.

---

## Summary Checklist

- [ ] **1. Rename** — Recommended → Alternative identified; Confidence → Evidence strength; Risk → Review level
- [x] **2. Evidence** — Evidence mapping model implemented (tables, API, service, drawer)
- [ ] **3. Per-item** — Accept | Override | Skip per row; optional "Accept all safe"
- [ ] **4. Drawer** — Strengthen why it fits / why it may not with real data
- [ ] **5. Export block** — "X items require review" + "Go to Review" CTA
- [ ] **6. Decision test** — Run 4-question validation for each flagged item
- [ ] **7. Time test** — First decision < 60 seconds

---

## Related Documents

- [SPRINT_ROADMAP_LOCKED.md](SPRINT_ROADMAP_LOCKED.md) — Sprint flow
- [SPRINT13_STATUS.md](SPRINT13_STATUS.md) — Current status
- [QA_MANUAL_SPRINT13_14.md](QA_MANUAL_SPRINT13_14.md) — Manual QA
