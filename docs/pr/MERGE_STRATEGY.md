# Merge strategy: Patches A–F (stacked PRs)

The working tree combines **Patch B** (provenance), **Patch D** (classification facts), **Patch C** (family router / product analysis), **Patch E** (heading trace), **Patch F** (grounded chat), and **Patch A** (memo strict alignment), plus follow-ups.

`backend/app/services/shipment_analysis_service.py` is a **shared integration point** for B, D, C, and E. It cannot be split by path alone without interactive staging or sequential merges.

## Recommended approach

1. **Land `integration/patches-complete` first** (single branch, one commit), **or**
2. **Stacked PRs** (merge order matters):
   - **PR1** `patch-b-d-foundation` ← `main` — migrations 016/017, provenance + facts models/services, pipeline wiring, import summary `provenance_skipped`, UI.
   - **PR2** `patch-c-e-f-reasoning` ← **PR1 branch** — family router, `required_attributes` / `product_analysis`, heading trace, grounded chat API + UI, suppress-alternatives trace behavior.
   - **PR3** `patch-a-memo-alignment` ← **PR2 branch** (or `main` if memo module is fully isolated) — `classification_memo.py`, strict memo tests, `status_model`, `engine` quality-gate metadata fix.

To produce **true separate commits** from one tree, use **interactive staging** on `shipment_analysis_service.py` per PR, or **merge PR1 → main → rebase PR2** with conflict resolution.

## Branch pointers

After `integration/patches-complete` exists, optional convenience branches (same tip as integration until split):

- `patch-b-d-foundation` — target PR1 file set (see `PR01_PATCH_B_D_FOUNDATION.md`).
- `patch-c-e-f-reasoning` — target PR2 file set.
- `patch-a-memo-alignment` — target PR3 file set.

Scripts: `scripts/git/create_pr_branches.sh` (if present).
