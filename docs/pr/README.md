# PR bundles (Patches A–F)

| Branch (local) | Doc | Contents |
|----------------|-----|----------|
| `patch-b-d-foundation` | [PR01_PATCH_B_D_FOUNDATION.md](./PR01_PATCH_B_D_FOUNDATION.md) | Patch B + D + follow-ups |
| `patch-c-e-f-reasoning` | [PR02_PATCH_C_E_F_REASONING.md](./PR02_PATCH_C_E_F_REASONING.md) | Patch C + E + F + follow-ups |
| `patch-a-memo-alignment` | [PR03_PATCH_A_MEMO_ALIGNMENT.md](./PR03_PATCH_A_MEMO_ALIGNMENT.md) | Patch A + engine follow-up |

**Integration branch:** `integration/patches-complete` — mergeable commits at branch tip containing the full stack.

**Named branches** are created with `scripts/git/create_pr_branches.sh` and currently **point at the same commit** as `integration/patches-complete`. Use them as **PR targets / labels**; for **three different diffs** from `main`, split `shipment_analysis_service.py` (and other shared files) via interactive staging or land PRs **sequentially** rebasing each branch onto `main` after the prior merge (see [MERGE_STRATEGY.md](./MERGE_STRATEGY.md)).

## Quick test matrix

```bash
cd backend
# B/D
alembic upgrade head
# C/E/F
python3 -m pytest tests/test_product_family_router.py tests/test_heading_reasoning_trace.py \
  tests/test_grounded_classification_chat.py -q
# A
python3 -m pytest tests/test_classification_memo_strict.py tests/test_patch_a_status_model.py -q
```
