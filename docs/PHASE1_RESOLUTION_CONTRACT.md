# Phase 1 — Resolution contract (display vs authoritative)

This document captures **non-negotiable semantics** for analysis resolution so we do not
accidentally treat “best available” reads as **authoritative** for compliance, filing, duty,
grounded chat, or other decision-critical behavior.

---

## 1. Three ways to get an `Analysis` row

| Mechanism | Purpose | Authority |
|-----------|---------|-----------|
| `resolve_display_analysis` | UI continuity, status summaries, admin/migration reads | **Not** authoritative for decisions |
| `resolve_authoritative_analysis` | Promoted shipment snapshot (`is_active`) | **Authoritative** for “what the platform elevated” |
| `get_scoped_analysis(analysis_id=...)` | Client or job names a **specific** run | **Authoritative for that run** after org (and optional shipment) scope checks |

**Invariant:** `resolve_display_analysis` **≠** `resolve_authoritative_analysis`.

---

## 2. Why display resolution includes a terminal fallback

When there is no in-flight row and no promoted `is_active` row, display resolution may return
the **highest-`version`** terminal row. That removes `created_at` as authority but still
implements a **weak “best available”** choice for **display only**.

**Allowed uses:** labels, progress, migration tooling, “something to show.”

**Forbidden uses (without additional checks):** filing, duty, regulatory submission,
compliance conclusions, grounded chat grounding, or any automation that assumes this row is
the **endorsed** snapshot.

**Mitigation:** For those uses, require **`is_active`** (via `resolve_authoritative_analysis`)
or an **explicit `analysis_id`** agreed for that operation.

---

## 3. API surfacing (current)

- **`GET /shipments/{id}`** includes `display_analysis_id`, `authoritative_analysis_id`, and
  `display_matches_authoritative` so clients can detect when the display shim disagrees with
  the promoted snapshot.
- **Analysis status** payload (`get_analysis_status`) includes `authoritative_analysis_id` and
  `display_matches_authoritative` alongside `analysis_id` (display resolution).

Downstream services (chat, export, audit) should be updated over time to use authoritative or
explicit id — **do not** assume `analysis_id` from older clients is always promoted.

---

## 4. TRUSTED gating (current vs target)

**Today:** `trust_gate_allows_trusted_status` uses heuristic signals (blockers, mode, fact row
count, optional JSON error list). That is **progress** but **not** a durable production trust
contract by itself.

**Target:** `TRUSTED` requires **all mandatory pipeline stages** to record `SUCCEEDED` (stage
ledger) — extraction, itemization, classification, fact persistence, provenance, and
regulatory/duty when those are part of the promised output. Until the ledger exists and is
wired into the gate, **TRUSTED remains a service-layer heuristic** (documented in code).

---

## 5. Top priority: silent failure elimination

Mandatory stages must not use “log and continue” for required work. Each mandatory stage needs:

- an explicit **stage row** (or equivalent persisted record),
- **typed** failure,
- explicit effect on **execution** and **decision** state.

Until then, `COMPLETE` may still mean “best-effort complete” in parts of the stack — **see**
`shipment_analysis_service.py` exception handling in the hardening increment.

---

## 6. Retry semantics (must be operationally closed)

| Pathway | Rule |
|---------|------|
| Worker retry | Same `analysis_id`; **upserts** / replace-in-transaction; no duplicate facts/reviews |
| User rerun | New `analysis_id` / `version`; supersession explicit; **no** in-place mutation of prior trusted rows |

Details: `docs/PHASE1_HARDENING_INCREMENT.md`.

---

## 7. Remaining Phase 1 closure order (recommended)

Identity is ahead of truth; the next risks are sharper if we normalize artifacts before we have
a **stage ledger + typed errors**.

1. **Stage ledger + typed errors** (+ silent failure elimination in mandatory paths)
2. **Retry semantics** end-to-end (task id ↔ `analysis_id`, idempotent writes)
3. **Canonical regulatory** (DB-first, keyed by `analysis_id`)
4. **Canonical duty**
5. **Reasoning / provenance / review derivation** cleanup (JSON as projection only)

---

## 8. DB vs service enforcement (summary)

| Concern | Enforcement |
|---------|-------------|
| One active analysis per shipment | DB (partial unique index, migration `019`) |
| Display vs authoritative | **Service** + API fields |
| TRUSTED predicate | **Service** (future: optional DB CHECK on aggregate flags) |
| Stage success | **DB** rows + **service** gate into `TRUSTED` |
