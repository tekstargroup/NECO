# Sprint 11 - UX Examples (Complete Shipment Analysis)

## Example 1: Complete Shipment Analysis View

### Scenario
- Declared HTS: 6112.20.20.30
- Alternative identified: 6112.20.10.10
- Potential savings: $90.00 (1.8%)
- PSC risk detected
- Review status: REVIEW_REQUIRED
- Documents: Commercial Invoice uploaded

---

## Full Screen Layout

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ NECO - Shipment Analysis                                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 1: OUTCOME SUMMARY                                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Declared HTS Code: 6112.20.20.30                                             │
│                                                                               │
│ Review Status: REVIEW_REQUIRED                                                │
│                                                                               │
│ Flags:                                                                        │
│   • PSC risk detected                                                         │
│   • Missing quantity                                                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 2: MONEY IMPACT                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ POTENTIAL DUTY SAVINGS IDENTIFIED                                            │
│                                                                               │
│ Declared Duty:        8.3%  ($415.00)                                        │
│ Alternative Duty:     6.5%  ($325.00)                                        │
│                                                                               │
│ Potential Savings:    1.8%  ($90.00)                                         │
│                                                                               │
│ Alternative HTS: 6112.20.10.10                                               │
│                                                                               │
│ Note: No filing recommendation is made. This analysis is for informational   │
│ purposes only.                                                                │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 3: RISK SUMMARY                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Risk Level: MEDIUM [B]                                                       │
│                                                                               │
│ Explanation:                                                                  │
│ Alternative classification differs at heading level. Historical entries show │
│ different chapter usage.                                                      │
│                                                                               │
│ Risk Tolerance: [Conservative ▼]                                             │
│   Conservative | Standard | Permissive                                        │
│                                                                               │
│ Note: Tolerance affects flagging, not computation.                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 4: STRUCTURAL ANALYSIS                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Declared HTS: 6112.20.20.30                                                  │
│   Chapter: 61 (Knitted or crocheted articles)                                 │
│   Heading: 6112 (Track suits, ski-suits and swimwear)                        │
│   Subheading: 6112.20.20 (Other, of cotton)                                   │
│   Statistical: 30                                                             │
│                                                                               │
│ Alternative HTS: 6112.20.10.10                                               │
│   Chapter: 61 (same)                                                           │
│   Heading: 6112 (same)                                                         │
│   Subheading: 6112.20.10 (differs)                                            │
│   Statistical: 10 (differs)                                                   │
│                                                                               │
│ Evidence Used:                                                                │
│   • Commercial Invoice (invoice_123.pdf, page 1)                              │
│   • Extracted attributes: quantity, value, description                       │
│                                                                               │
│ What NECO Did NOT Evaluate:                                                   │
│   • Trade program eligibility (GSP, AGOA, etc.)                              │
│   • Country-specific preferences                                              │
│   • Quota or safeguard measures                                               │
│   • Section 301/232 applicability                                            │
│   • ADD/CVD orders                                                            │
│   • Legal interpretation of HTS notes or rulings                             │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 5: POSSIBLE OVERPAYMENT DETECTED                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Historical Divergence:                                                       │
│   • Different chapter used historically (Chapter 62)                          │
│   • Different heading used historically (6203)                                │
│                                                                               │
│ Structural Reason:                                                            │
│   Codes differ at chapter/heading level. Duties differ accordingly.          │
│                                                                               │
│ Duty Delta:                                                                   │
│   Historical average: 6.5%                                                    │
│   Current declared: 8.3%                                                      │
│   Delta: 1.8% ($90.00)                                                        │
│                                                                               │
│ DISCLAIMER:                                                                   │
│   No filing recommendation is made. This analysis is for informational       │
│   purposes only.                                                              │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 6: DOCUMENT EVIDENCE                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Commercial Invoice: invoice_123.pdf                                           │
│ Uploaded: 2024-01-31 10:30 AM                                               │
│                                                                               │
│ Extracted Fields:                                                             │
│                                                                               │
│   Invoice Number: INV-12345                                                   │
│     Source: Page 1, Line 5                                                    │
│     Snippet: "Invoice No: INV-12345"                                          │
│     Extraction Quality: High                                                  │
│                                                                               │
│   Invoice Date: 2024-01-15                                                    │
│     Source: Page 1, Line 6                                                    │
│     Snippet: "Date: 01/15/2024"                                               │
│     Extraction Quality: High                                                  │
│                                                                               │
│   Currency: USD                                                               │
│     Source: Page 1, Line 7                                                   │
│     Snippet: "Currency: USD"                                                  │
│     Extraction Quality: High                                                  │
│                                                                               │
│   Quantity: 100.0 PCS                                                         │
│     Source: Page 1, Line 12                                                   │
│     Snippet: "Quantity: 100 PCS"                                              │
│     Extraction Quality: High                                                  │
│                                                                               │
│   Total Value: $5,000.00                                                      │
│     Source: Page 1, Line 15                                                   │
│     Snippet: "Total: $5,000.00"                                                │
│     Extraction Quality: High                                                  │
│                                                                               │
│   ⚠️ Country of Origin: CONFLICT                                              │
│     Source: Page 1 (CN), Page 2 (US)                                          │
│     Multiple values detected: CN, US                                          │
│     Not auto-resolved. Manual review required.                                │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 7: REVIEW STATUS                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Current Status: REVIEW_REQUIRED                                               │
│                                                                               │
│ Created: 2024-01-31 10:30 AM                                                 │
│ Created By: analyst_1                                                         │
│                                                                               │
│ [Submit for Review]                                                           │
│                                                                               │
│ ──────────────────────────────────────────────────────────────────────────── │
│                                                                               │
│ Review History:                                                               │
│   (No review history)                                                         │
│                                                                               │
│ [Override Classification]                                                     │
│   ⚠️ This action will be logged and auditable.                               │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 8: AUDIT TRAIL                                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ [▼] Expand Full Audit Replay                                                  │
│                                                                               │
│ Resolver Inputs:                                                             │
│   • HTS Code: 6112.20.20.30                                                   │
│   • HTS Version: 792bb867-c549-4769-80ca-d9d1adc883a3                        │
│                                                                               │
│ Resolver Outputs:                                                             │
│   • General Duty: 8.3% (inherited from 6112.20.20)                          │
│   • Special Duty: Free(...) (inherited from 6112.20.20)                      │
│   • Column 2: 90% (inherited from 6112.20.20)                                │
│                                                                               │
│ Inheritance Path:                                                             │
│   6112.20.20.30 → 6112.20.20 → 6112.20                                       │
│                                                                               │
│ Audit Replay:                                                                 │
│   • Status: MATCH                                                             │
│   • Replayed: 2024-01-31 15:30 PM                                           │
│   • Result: Current logic matches stored output                              │
│                                                                               │
│ [Export Audit Pack]                                                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

[Export for Broker]  [Save]  [Close]
```

---

## Example 2: Broker Handoff PDF

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║                    NECO FILING PREP SUMMARY                                   ║
║                                                                                ║
║  Generated: 2024-01-31 15:30:00 UTC                                          ║
║  HTS Version: 792bb867-c549-4769-80ca-d9d1adc883a3                           ║
║                                                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│ CLASSIFICATION & DUTIES                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Declared HTS Code: 6112.20.20.30                                              │
│                                                                               │
│ General Duty: 8.3%                                                            │
│ Special Duty: Free(AU,BH,CL,CO,E*,IL,JO,KR,MA,OM,P,PA,PE,S,SG)              │
│ Column 2 Duty: 90%                                                            │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ QUANTITY & VALUE                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Quantity: 100.0                                                               │
│ Unit of Measure: PCS                                                          │
│ Customs Value: $5,000.00                                                      │
│ Country of Origin: CN                                                         │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ REVIEW STATUS                                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Status: REVIEWED_ACCEPTED                                                     │
│ Reviewed By: reviewer_1                                                       │
│ Reviewed At: 2024-01-31 11:00 AM                                            │
│ Review Notes: Classification verified against HTSUS                          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ DISCLAIMERS                                                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ This is not a filing. Broker review required before submission.               │
│                                                                               │
│ NECO does not provide legal advice or filing recommendations.                │
│                                                                               │
│ Duty rates are based on general/special/column2 only. Trade programs,        │
│ quotas, and other measures not evaluated.                                     │
│                                                                               │
│ Country of origin is provided for context only. NECO does not evaluate       │
│ origin rules or preferences.                                                  │
│                                                                               │
│ PSC Radar flags indicate potential risks but do not constitute filing        │
│ advice.                                                                       │
│                                                                               │
│ All classifications should be verified against current HTSUS and applicable  │
│ rulings.                                                                      │
│                                                                               │
│ Broker assumes full responsibility for final classification and filing        │
│ decisions.                                                                    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Example 3: No Savings Case

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 2: MONEY IMPACT                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ DUTY ANALYSIS                                                                 │
│                                                                               │
│ No material duty difference detected.                                         │
│                                                                               │
│ Declared Duty:        8.3%  ($415.00)                                        │
│ Alternative Duties:   8.3% - 8.5%                                            │
│                                                                               │
│ Alternative HTS codes analyzed:                                              │
│   • 6112.20.10.10: 8.3%                                                      │
│   • 6112.20.20.20: 8.5%                                                      │
│                                                                               │
│ Note: Duty rates are within normal variance. No material difference          │
│ observed.                                                                     │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Example 4: Conflict Handling

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SECTION 6: DOCUMENT EVIDENCE                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ⚠️ Country of Origin: CONFLICT                                              │
│     Multiple values detected. Not auto-resolved.                              │
│                                                                               │
│     Value 1: CN                                                               │
│       Source: Page 1, Line 8                                                  │
│       Snippet: "Country of Origin: CN"                                        │
│                                                                               │
│     Value 2: US                                                               │
│       Source: Page 2, Line 3                                                 │
│       Snippet: "Origin: US"                                                   │
│                                                                               │
│     Action Required: Manual review needed to determine correct value.        │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Example 5: Override Warning

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ OVERRIDE CLASSIFICATION                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ Current Classification: 6112.20.20.30                                        │
│                                                                               │
│ Override Classification: [6112.20.10.10]                                     │
│                                                                               │
│ Justification (Required):                                                     │
│ [________________________________________________________]                   │
│                                                                               │
│ ⚠️ WARNING: This action will be logged and auditable.                       │
│                                                                               │
│ By overriding, you acknowledge:                                             │
│   • This decision will be permanently recorded                               │
│   • Audit trail will show override reason                                    │
│   • This may be reviewed in future audits                                    │
│                                                                               │
│ [Cancel]  [Confirm Override]                                                 │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Key UX Principles Demonstrated

1. **Vertical Layout**: All sections visible, no tabs
2. **Order Matters**: Outcome → Money → Risk → Defensibility → PSC → Evidence → Review → Audit
3. **Conservative Language**: No AI, no recommendations, no hype
4. **Explicit Conflicts**: Conflicts are visually uncomfortable, not hidden
5. **Serious Overrides**: Frictionful, with clear audit warnings
6. **Money-First**: Savings obvious but never pushy
7. **Compliance-Grade**: Sounds like CBP, accounting, regulatory filings
