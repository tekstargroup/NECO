# Sprint 11 - Hard UX (Infrastructure-Grade Trust, Money-First)

## Overview

Sprint 11 introduces zero logic changes. This is UX, language, hierarchy, and flow only.

**Primary User:** Compliance Director  
**Primary "Holy Sh*t" Moment:** "This saved me money — safely."  
**Tone:** Conservative, calm, precise, serious, zero AI vibes

## Core Principle

Make NECO feel like regulatory infrastructure:
- Trustworthy before impressive
- Explicit before implicit
- Conservative before helpful

## Entry Point (Locked)

### Default Landing Experience

**"Analyze a shipment"**

This screen must allow:
- Upload documents (CI, PL, TDS)
- Paste or enter shipment details manually
- Optional historical entry reference

**No dashboards first. Action first.**

### Secondary Entry

**"Review historical shipments"** (optional, not default)

---

## Core Screen: Shipment Analysis View

**This is the most important screen in NECO.**

Vertical layout. No buried tabs. Order matters.

### Section 1 — Outcome Summary (Top)

Show immediately:

```
┌─────────────────────────────────────────────────────────┐
│ SHIPMENT ANALYSIS                                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Declared HTS Code: 6112.20.20.30                         │
│                                                           │
│ Review Status: REVIEW_REQUIRED                           │
│                                                           │
│ Flags:                                                    │
│   • PSC risk detected                                    │
│   • Missing quantity                                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Clear, neutral language. No hype.**

### Section 2 — Money Impact (Prominent, but Calm)

Lead with:

```
┌─────────────────────────────────────────────────────────┐
│ POTENTIAL DUTY SAVINGS IDENTIFIED                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Declared Duty:        8.3%  ($415.00)                   │
│ Alternative Duty:     6.5%  ($325.00)                   │
│                                                           │
│ Potential Savings:    1.8%  ($90.00)                    │
│                                                           │
│ Alternative HTS: 6112.20.10.10                           │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**If no savings:**

```
┌─────────────────────────────────────────────────────────┐
│ DUTY ANALYSIS                                            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ No material duty difference detected.                    │
│                                                           │
│ Declared Duty:        8.3%  ($415.00)                   │
│ Alternative Duties:   8.3% - 8.5%                       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**No hype. No "recommended action".**

### Section 3 — Risk Summary (Explicit, User-Controlled)

```
┌─────────────────────────────────────────────────────────┐
│ RISK SUMMARY                                             │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Risk Level: MEDIUM [B]                                   │
│                                                           │
│ Explanation:                                             │
│ Alternative classification differs at heading level.    │
│ Historical entries show different chapter usage.        │
│                                                           │
│ Risk Tolerance: [Conservative ▼]                        │
│   Conservative | Standard | Permissive                  │
│                                                           │
│ Note: Tolerance affects flagging, not computation.      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Risk is explicit, not hidden. User-controlled tolerance.**

### Section 4 — Why This Is Defensible

```
┌─────────────────────────────────────────────────────────┐
│ STRUCTURAL ANALYSIS                                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Declared HTS: 6112.20.20.30                             │
│   Chapter: 61                                             │
│   Heading: 6112                                           │
│   Subheading: 6112.20.20                                 │
│   Statistical: 30                                         │
│                                                           │
│ Alternative HTS: 6112.20.10.10                          │
│   Chapter: 61 (same)                                      │
│   Heading: 6112 (same)                                    │
│   Subheading: 6112.20.10 (differs)                       │
│   Statistical: 10 (differs)                              │
│                                                           │
│ Evidence Used:                                           │
│   • Commercial Invoice (page 1)                          │
│   • Extracted attributes: quantity, value, description    │
│                                                           │
│ What NECO Did NOT Evaluate:                              │
│   • Trade program eligibility                             │
│   • Country-specific preferences                         │
│   • Quota or safeguard measures                          │
│   • Legal interpretation of HTS notes                    │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Factual only. No legal causality. No interpretation.**

### Section 5 — PSC Radar (Read-Only, Careful Language)

```
┌─────────────────────────────────────────────────────────┐
│ POSSIBLE OVERPAYMENT DETECTED                            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Historical Divergence:                                   │
│   • Different chapter used historically (Chapter 62)     │
│   • Different heading used historically (6203)            │
│                                                           │
│ Structural Reason:                                       │
│   Codes differ at chapter/heading level.                 │
│   Duties differ accordingly.                             │
│                                                           │
│ Duty Delta:                                              │
│   Historical average: 6.5%                               │
│   Current declared: 8.3%                                 │
│   Delta: 1.8% ($90.00)                                   │
│                                                           │
│ DISCLAIMER:                                              │
│   No filing recommendation is made.                     │
│   This analysis is for informational purposes only.     │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Explicit disclaimer. No recommendations.**

### Section 6 — Enrichment Evidence

```
┌─────────────────────────────────────────────────────────┐
│ DOCUMENT EVIDENCE                                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Commercial Invoice: invoice_123.pdf                      │
│                                                           │
│ Extracted Fields:                                        │
│   • Invoice Number: INV-12345                            │
│     Source: Page 1, Line 5                               │
│     Snippet: "Invoice No: INV-12345"                     │
│                                                           │
│   • Quantity: 100.0 PCS                                  │
│     Source: Page 1, Line 12                              │
│     Snippet: "Quantity: 100 PCS"                        │
│                                                           │
│   • Total Value: $5,000.00                               │
│     Source: Page 1, Line 15                              │
│     Snippet: "Total: $5,000.00"                         │
│                                                           │
│   ⚠️ Country of Origin: CONFLICT                         │
│     Source: Page 1 (CN), Page 2 (US)                     │
│     Multiple values detected. Not auto-resolved.         │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Conflicts must be visually uncomfortable. Do not auto-resolve. Do not hide.**

### Section 7 — Review & Accountability

```
┌─────────────────────────────────────────────────────────┐
│ REVIEW STATUS                                            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ Current Status: REVIEW_REQUIRED                          │
│                                                           │
│ Created: 2024-01-31 10:30 AM                            │
│ Created By: analyst_1                                    │
│                                                           │
│ [Submit for Review]                                      │
│                                                           │
│ ───────────────────────────────────────────────────────  │
│                                                           │
│ Review History:                                          │
│   • 2024-01-31 11:00 AM - REVIEWED_ACCEPTED             │
│     Reviewed By: reviewer_1                              │
│     Notes: "Classification verified against HTSUS"       │
│                                                           │
│   • 2024-01-31 10:45 AM - OVERRIDE                      │
│     Overridden By: reviewer_1                            │
│     Original: 6112.20.20.30                              │
│     Override: 6112.20.10.10                              │
│     Justification: "Product description matches 10.10"   │
│                                                           │
│ [Override Classification]                                │
│   ⚠️ This action will be logged and auditable.          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Override UX: Serious, frictionful, clear audit warning.**

### Section 8 — Audit Trail (Expandable)

```
┌─────────────────────────────────────────────────────────┐
│ AUDIT TRAIL                                              │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ [▼] Expand Full Audit Replay                             │
│                                                           │
│ Resolver Inputs:                                         │
│   • HTS Code: 6112.20.20.30                             │
│   • HTS Version: 792bb867-c549-4769-80ca-d9d1adc883a3  │
│                                                           │
│ Resolver Outputs:                                        │
│   • General Duty: 8.3% (inherited from 6112.20.20)     │
│   • Special Duty: Free(...) (inherited from 6112.20.20)│
│   • Column 2: 90% (inherited from 6112.20.20)            │
│                                                           │
│ Audit Replay:                                            │
│   • Status: MATCH                                        │
│   • Replayed: 2024-01-31 15:30 PM                       │
│   • Result: Current logic matches stored output         │
│                                                           │
│ [Export Audit Pack]                                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**This should feel boring and official.**

---

## Broker Handoff View

**Design for: Printing, PDF, Email forwarding**

```
┌─────────────────────────────────────────────────────────┐
│ NECO FILING PREP SUMMARY                                │
│                                                           │
│ Generated: 2024-01-31 15:30:00 UTC                      │
│ HTS Version: 792bb867-c549-4769-80ca-d9d1adc883a3      │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ CLASSIFICATION & DUTIES                                  │
│                                                           │
│ Declared HTS Code: 6112.20.20.30                        │
│ General Duty: 8.3%                                       │
│ Special Duty: Free(AU,BH,CL,CO,E*,IL,JO,KR,MA,OM,P,PA,  │
│              PE,S,SG)                                    │
│ Column 2 Duty: 90%                                       │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ QUANTITY & VALUE                                         │
│                                                           │
│ Quantity: 100.0                                          │
│ Unit of Measure: PCS                                     │
│ Customs Value: $5,000.00                                  │
│ Country of Origin: CN                                    │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ REVIEW STATUS                                            │
│                                                           │
│ Status: REVIEWED_ACCEPTED                                │
│ Reviewed By: reviewer_1                                   │
│ Reviewed At: 2024-01-31 11:00 AM                        │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│ DISCLAIMERS                                              │
│                                                           │
│ This is not a filing. Broker review required before     │
│ submission.                                               │
│                                                           │
│ NECO does not provide legal advice or filing             │
│ recommendations.                                          │
│                                                           │
│ Duty rates are based on general/special/column2 only.    │
│ Trade programs, quotas, and other measures not           │
│ evaluated.                                                │
│                                                           │
│ Broker assumes full responsibility for final            │
│ classification and filing decisions.                     │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Must look conservative. Contain disclaimers everywhere. Avoid any implied advice.**

---

## Language Guidelines

### Replace Everywhere

**DO NOT USE:**
- "AI"
- "Confidence score"
- "Recommended"
- "Optimized"
- "Smart"
- "Machine learning"
- "Algorithm"
- "Automated"
- "Intelligent"

**USE INSTEAD:**
- "Detected"
- "Observed"
- "Alternative identified"
- "Requires review"
- "Possible overpayment detected"
- "System"
- "Analysis"
- "Computation"
- "Deterministic"
- "Rule-based"

### Tone Examples

**WRONG:**
- "Our AI recommends..."
- "Smart classification detected..."
- "Optimized for maximum savings..."
- "Confidence: 95%"

**RIGHT:**
- "Alternative classification identified..."
- "Possible overpayment detected..."
- "Requires review..."
- "Extraction quality: High"

### Language Must Sound Like:
- CBP
- Accounting
- Compliance
- Regulatory filings

**Not tech. Not marketing. Not startup.**

---

## UX Flow Documentation

### Primary Flow: Analyze a Shipment

1. **Landing Screen**
   - "Analyze a shipment" (prominent)
   - Upload documents OR enter details manually
   - No dashboards, no metrics, no charts

2. **Shipment Analysis View**
   - All 8 sections visible (vertical scroll)
   - No tabs, no hidden information
   - Order matters: Outcome → Money → Risk → Defensibility → PSC → Evidence → Review → Audit

3. **Review Actions**
   - Submit for review (if DRAFT)
   - Override (if REVIEWER role, with friction)
   - Export (always available)

4. **Broker Handoff**
   - Export as PDF/CSV/JSON
   - Conservative formatting
   - Disclaimers everywhere

### Secondary Flow: Review Historical Shipments

1. **Historical List**
   - Simple table: Date, HTS Code, Status, Actions
   - No charts, no dashboards

2. **Shipment Detail**
   - Same 8-section view as analysis
   - Read-only (no edits)

---

## UX Validation Criteria

Sprint 11 is complete when:

1. ✅ You can walk through a shipment in under 3 minutes
2. ✅ A compliance director understands it without questions
3. ✅ The system feels conservative, not clever
4. ✅ Money impact is obvious but never pushy
5. ✅ Risk acceptance feels serious

---

## Why NECO Feels Safe to Relieve On

1. **Explicit, Not Implicit**
   - Every decision point is visible
   - Every risk is stated
   - Every override is logged

2. **Conservative, Not Clever**
   - No AI language
   - No confidence scores
   - No recommendations
   - No hype

3. **Money-First, But Calm**
   - Savings are obvious
   - But never pushy
   - No "optimization" claims

4. **Auditable, Not Black Box**
   - Full audit trail
   - Evidence everywhere
   - Replayable logic

5. **Compliance-Grade Language**
   - Sounds like CBP
   - Sounds like accounting
   - Sounds like regulatory filings
   - Does NOT sound like tech

---

## Deliverables

- ✅ Screen layouts documented
- ✅ Language guidelines established
- ✅ UX flow documented
- ✅ Examples provided
- ✅ Validation criteria defined

**Sprint 11 is CLOSED. NECO UX is infrastructure-grade and trustworthy.**
