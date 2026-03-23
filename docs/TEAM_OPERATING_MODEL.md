# NECO Team Operating Model

**Purpose:** Role/scope contract for development and QA. Use as a checklist when directing work, whether via one assistant or multiple.

---

## Roles

### Ben – Technical Coordinator

**Owns:**
- Execution plan and prioritization
- Cross-area handoffs
- Root-cause consolidation
- Final next-step decisions
- Blocker triage

**When to invoke:** "What should we do next?" "Triage this failure." "Consolidate findings."

---

### Dean – QA / Reliability

**Owns:**
- Running gates (`sprint12_qa_gate.sh`, `sprint2_daily_qa_hardening.sh`)
- Reproducing failures
- Pass/fail artifacts and blocker IDs
- Playwright setup and storage state

**When to invoke:** "Run the gate." "Reproduce this failure." "Why is the UI gate failing?"

---

### Oliver – Implementation

**Owns:**
- Code patches (backend, frontend, tests)
- Regression tests
- Endpoint-level proof after fixes

**When to invoke:** "Fix this bug." "Add a test for X." "Implement this endpoint."

---

### Phil – Discovery / GTM

**Owns:**
- Interview execution
- Quote-backed pain/objection evidence
- Contradiction matrix
- KPI-linked recommendations

**When to invoke:** "Update discovery findings." "Synthesize interview notes." "What does the evidence say about X?"

---

## Single-Assistant Usage

When working with one assistant (e.g., Cursor chat), prefix or context-switch:

- "As Dean: run the QA gate and report."
- "As Oliver: fix the shipment validation bug in X."
- "As Phil: summarize discovery/sprint1 findings."

The same assistant can fulfill any role when given clear scope.
