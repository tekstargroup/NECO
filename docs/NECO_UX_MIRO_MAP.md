# NECO UX Map for Miro

Use this document to structure your Miro board. Each section below maps to a suggested Miro frame or swimlane.

---

## 1. Product Overview (Frame: Top of board)

**NECO** = Next-Gen Compliance Engine

| Element | Value |
|--------|-------|
| **Purpose** | AI-powered customs compliance for U.S. importers |
| **Primary User** | Compliance Director |
| **Value Proposition** | "This saved me money — safely." |
| **Tone** | Conservative, calm, precise, serious, zero AI vibes |
| **Target Use Case** | Process 25+ AURA shipments → find duty savings via better HTS classification + PSC filings |

**Core Features:**
- HS classification (alternative HTS codes)
- PSC Radar (classification-driven risk signals)
- Document ingestion (CI, PL, TDS)
- Duty analysis (declared vs. alternative)
- Review workflow (audit trail)
- Broker handoff (filing-prep export)

---

## 2. User Flows (Swimlanes)

### Flow A: Primary — Analyze a Shipment
```
[Sign In] → [Org Select] → [Shipments List] → [New Shipment] → [Shipment Detail]
                                                                    ↓
                                            [Overview] ← [Documents] ← [Analysis] ← [Reviews] ← [Exports]
                                                                    ↓
                                            [8-Section Analysis Results]
                                                                    ↓
                                            [Review / Override] → [Export to Broker]
```

### Flow B: Secondary — Review Historical Shipments
```
[Sign In] → [Org Select] → [Shipments List] → [Click Shipment] → [Shipment Detail (read-only)]
```

### Flow C: Auth & Setup
```
[/] → [Sign In or Dev Login] → [Org Select] → [/app/shipments]
```

---

## 3. Screen Inventory (Cards / Sticky Notes)

### Auth & Setup
| Screen | Route | Purpose |
|--------|-------|---------|
| Sign In | `/sign-in` | Clerk authentication |
| Sign Up | `/sign-up` | Clerk registration |
| Dev Login | `/dev-login` | Dev auth bypass (local only) |
| Org Select | `/app/organizations/select` | Select active organization |
| Create Org | `/app/organizations/new` | Create organization |

### Shipments
| Screen | Route | Purpose |
|--------|-------|---------|
| Shipments List | `/app/shipments` | View all shipments, entitlement usage |
| Create Shipment | `/app/shipments/new` | Add name, references, items |
| Shipment Detail | `/app/shipments/[id]` | Tabbed container (5 tabs) |

### Shipment Detail Tabs
| Tab | Purpose |
|-----|---------|
| **Overview** | Summary, eligibility, items, references |
| **Documents** | Upload CI/PL/TDS (presigned S3) |
| **Analysis** | Trigger analysis + 8-section results |
| **Reviews** | Review status, history, override |
| **Exports** | Download filing-prep bundle |

---

## 4. Analysis Results — 8 Sections (Vertical Order)

**Critical:** Order matters. All visible, no tabs. Vertical scroll.

| # | Section Name | Content |
|---|--------------|---------|
| 1 | **Outcome Summary** | Declared HTS, review status, flags (PSC risk, missing qty) |
| 2 | **Money Impact** | Declared vs alternative duty, potential savings (or "No material difference") |
| 3 | **Risk Summary** | Risk level, explanation, Risk Tolerance dropdown (Conservative/Standard/Permissive) |
| 4 | **Structural Analysis** | HTS breakdown, evidence used, "What NECO Did NOT Evaluate" |
| 5 | **PSC Radar** | Historical divergence, duty delta, disclaimer |
| 6 | **Enrichment Evidence** | Extracted fields, source refs, conflicts (visually uncomfortable) |
| 7 | **Review Status** | Current status, history, Submit for Review, Override (frictionful) |
| 8 | **Audit Trail** | Resolver inputs/outputs, audit replay, Export Audit Pack |

---

## 5. Broker Handoff View

**Design for:** Printing, PDF, Email forwarding

**Sections:**
- Classification & Duties
- Quantity & Value
- Review Status
- **Disclaimers** (required everywhere)

**Format:** Conservative, no implied advice, broker assumes responsibility.

---

## 6. UX Principles (Sticky Notes / Text Blocks)

### Design Principles
- **Trustworthy before impressive**
- **Explicit before implicit**
- **Conservative before helpful**
- **Action first** — no dashboards first
- **Vertical layout** — no buried tabs
- **Money-first** — savings obvious but never pushy

### Language Guidelines — DO NOT USE
- AI, Confidence score, Recommended, Optimized, Smart
- Machine learning, Algorithm, Automated, Intelligent

### Language Guidelines — USE INSTEAD
- Detected, Observed, Alternative identified
- Requires review, Possible overpayment detected
- System, Analysis, Computation, Deterministic, Rule-based

### Tone
- Sounds like: CBP, Accounting, Compliance, Regulatory filings
- Does NOT sound like: Tech, Marketing, Startup

---

## 7. Component Library (Component Cards)

### Layout
- AppShell (header, nav, content)
- ShipmentDetailShell (tabbed container)
- Left nav: Shipments → /app/shipments

### UI Components
- Status pill (DRAFT, READY, etc.)
- Eligibility badge
- Blocker box (missing requirements)
- Warning box
- Key-value row
- Monospace code

### Header Elements
- NECO logo → /app/shipments
- OrganizationSwitcher (Clerk)
- UserButton (Clerk)

---

## 8. States & Edge Cases

| State | UX Treatment |
|-------|--------------|
| **Eligibility blocked** | Blocker box, no Analyze button |
| **Analysis in progress** | Poll status, loading state |
| **Analysis error** | Error message, retry option |
| **Conflict in documents** | Visually uncomfortable, do not auto-resolve |
| **No savings** | "No material duty difference detected" |
| **Override** | Frictionful, audit warning, justification required |
| **Empty shipment** | Prompt to add items + documents |

---

## 9. Suggested Miro Board Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ROW 1: Product Overview + UX Principles                                     │
│  [NECO Overview] [Design Principles] [Language Guidelines]                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ROW 2: User Flows (Swimlanes)                                               │
│  [Flow A: Analyze Shipment] [Flow B: Review Historical] [Flow C: Auth]       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ROW 3: Screen Inventory                                                     │
│  [Auth] [Shipments List] [Create] [Detail + 5 Tabs] [8 Sections] [Broker]    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ROW 4: Analysis View (8 Sections — Vertical)                                │
│  [1] [2] [3] [4] [5] [6] [7] [8]                                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ROW 5: Components + States                                                  │
│  [Component Library] [Edge Cases / States]                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Quick Reference: Route Map

```
/                          → Redirect to /app/shipments
/sign-in                   → Clerk sign-in
/sign-up                   → Clerk sign-up
/dev-login                 → Dev auth bypass
/app/organizations/select  → Org selection
/app/organizations/new     → Create org
/app/shipments             → Shipments list (default landing)
/app/shipments/new         → Create shipment
/app/shipments/[id]        → Shipment detail (5 tabs)
```

---

*Source: NECO codebase + docs/archive/backend/SPRINT11_UX_DESIGN.md, SPRINT11_UX_EXAMPLES.md*
