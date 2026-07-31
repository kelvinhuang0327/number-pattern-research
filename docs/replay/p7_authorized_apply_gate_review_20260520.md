# P7 Authorized Apply Gate Review — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Date**: 2026-05-20  
**Path**: **B — Gate Review Only (no apply)**

---

## Authorization Status

| Item | Status |
|------|--------|
| CEO phrase `YES apply P7 controlled replay rows` | **NOT RECEIVED** |
| Production apply executed | **NO** |
| Path taken | **B (gate review only)** |
| Gate classification | `P7_APPLY_BLOCKED_AWAITING_CEO_PHRASE` |

---

## Readiness Checklist (all PASS)

| Check | Result |
|-------|--------|
| `test_p7_controlled_apply_actual_gate.py` 17/17 | ✅ PASS |
| `test_replay_api_contract.py` 44/44 | ✅ PASS |
| All 148 tests combined | ✅ PASS |
| Drift guard `--strict` | ✅ PASS |
| Production rows = 460 | ✅ PASS |
| FK root cause fixed (`replay_run_id=None`) | ✅ Fixed in commit 0a722dc |
| Temp DB rehearsal 460→488 verified | ✅ Verified |
| Idempotency (second run = 0 inserts) | ✅ Verified |
| Rollback via `controlled_apply_id` | ✅ Verified |
| Zero duplicates in ONLINE scope | ✅ Confirmed |
| Backup procedure documented | ✅ In p7_readiness_report_20260520.md |
| P7 dry-run JSON frozen | ✅ Committed |

**All readiness conditions met. The only blocker is the CEO authorization phrase.**

---

## ONLINE Scope (28 rows) — Ready, Blocked

| Strategy | Lottery | Draws | Draw Range |
|----------|---------|-------|-----------|
| fourier_rhythm_3bet | POWER_LOTTO | 12 | 115000016–115000030 |
| ts3_regime_3bet | BIG_LOTTO | 16 | 115000025–115000044 |
| **Total** | | **28** | |

Projected result: 460 → **488** rows.

---

## RETIRED Scope (93 rows) — Deferred

Not included in this gate review. Requires:
1. Human review of lifecycle warnings
2. `--scope INCLUDE_RETIRED_WITH_WARNING --include-retired-reviewed`
3. Separate CEO authorization

---

## P8 Dry-Run Findings (supporting data)

The P8 dry-run confirms all 121 RECONSTRUCTIBLE rows are complete:

| Metric | Value |
|--------|-------|
| Total candidates | 121 |
| Have prediction_items | 121/121 (100%) |
| Have draw result | 121/121 (100%) |
| Have both complete | 121/121 (100%) |
| READY_FOR_ONLINE_APPLY | **28** (ONLINE strategies) |
| PENDING_HUMAN_REVIEW_RETIRED | **93** (RETIRED strategies) |

No missing fields. All 28 ONLINE rows can be inserted immediately upon authorization.

---

## Apply Command (for when phrase is received)

```bash
# Step 1: Create backup
sqlite3 lottery_api/data/lottery_v2.db \
  ".backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db"

# Step 2: Verify backup row count = 460
sqlite3 backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"

# Step 3: Execute apply
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply \
  --scope ONLINE_ONLY \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --expected-rows 460

# Expected: 488 rows after apply
# Rollback if needed:
# .venv/bin/python scripts/p7_controlled_replay_row_apply.py \
#   --apply --rollback-plan <controlled_apply_id> --rollback-apply ...
```

---

## Current Classification

```
P7_APPLY_BLOCKED_AWAITING_CEO_PHRASE
```

To authorize P7 ONLINE apply (28 rows, 460→488):
```
YES apply P7 controlled replay rows
```
