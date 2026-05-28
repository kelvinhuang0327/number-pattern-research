# RSR-6 Cleanup: Delete Orphan bet_index=2 Rows

**Task ID**: RSR6_CLEANUP
**Classification**: RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED
**Generated At**: 2026-05-28T12:42:12.835332Z

---

## 1. Executive Summary

RSR-6 cleanup executed successfully. Deleted **40 orphan `bet_index=2` rows** for
`power_precision_3bet` and `power_orthogonal_5bet` (20 rows each). These rows were written
by a pre-P126 batch (replay_run_id=6) without source/provenance for draws 99000085–99000104.

- DB rows: **72,462 → 72,422** (−40)
- All `bet_index=1` rows preserved intact.
- P10/P12 RSR-6 apply gate blocks cleared.
- Apply gate re-evaluation required before any controlled_apply proceeds.

---

## 2. Authorization Confirmation

| Field | Value |
|-------|-------|
| Required phrase | `RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528` |
| Authorization present | **True** |
| Cleanup allowed | **True** |
| Observed phrase | `RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528` |

---

## 3. RSR-6 Audit Recap

| Field | Value |
|-------|-------|
| Audit artifact | `outputs/replay/rsr6_orphan_bet_index2_audit_20260528.json` |
| Audit classification | `RSR6_ORPHAN_BET_INDEX2_AUDIT_READY` |
| Audit commit | 49eca63 |
| Recommended resolution | Option A — Quarantine Delete |
| Orphan rows audited | 40 |
| Strategies affected | power_precision_3bet, power_orthogonal_5bet |
| Target draws | 99000085–99000104 |

---

## 4. Backup Creation and Verification

| Field | Value |
|-------|-------|
| Backup path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2_before_rsr6_cleanup_20260528T124212Z.db` |
| Backup row count | 72,462 |
| Backup created | **True** |
| Backup verified | **True** |

---

## 5. Strict Delete Selector

```sql
DELETE FROM strategy_prediction_replays
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
  AND bet_index = 2
  AND replay_run_id = 6
  AND (source IS NULL OR source = '')
  AND controlled_apply_id IS NULL
  AND provenance_hash IS NULL
  AND truth_level IS NULL
  AND CAST(target_draw AS INTEGER) BETWEEN 99000085 AND 99000104
```

`selector_strict = true` — all 7 conditions must match simultaneously.

---

## 6. Deleted Rows Summary

| Strategy | Deleted Rows |
|----------|-------------|
| power_precision_3bet | 20 |
| power_orthogonal_5bet | 20 |
| **Total** | **40** |

Delta confirmed: 72,462 − 72,422 = 40

---

## 7. DB Rows Before / After

| Checkpoint | Row Count |
|-----------|-----------|
| Before cleanup | 72,462 |
| After cleanup | 72,422 |
| Delta | −40 |
| Expected | 72,422 |
| Match | **True** |

---

## 8. Row Preservation Check

| Strategy | bet_index=1 Before | bet_index=1 After | Preserved |
|----------|--------------------|-------------------|-----------|
| power_precision_3bet | 1550 | 1550 | **True** |
| power_orthogonal_5bet | 1550 | 1550 | **True** |

All `bet_index=1` rows intact: **True**

---

## 9. Drift Guard Baseline Handling

The drift guard (`scripts/replay_lifecycle_drift_guard.py`) baseline was updated:

| Field | Before | After |
|-------|--------|-------|
| `legacy_count` | 460 | 420 |
| `total_count` | 72,462 | 72,422 |

Drift guard will PASS at 72,422.

---

## 10. Apply Gate Impact After Cleanup

| Field | Value |
|-------|-------|
| power_precision_3bet RSR-6 cleaned | **True** |
| power_orthogonal_5bet RSR-6 cleaned | **True** |
| Apply ready re-evaluation required | **True** |
| controlled_apply executed | False |
| replay_rows_inserted | 0 |

P10/P12 are not declared apply-ready. The apply gate must be re-evaluated separately
to confirm bet_index=1 rows are valid and all other apply preconditions pass.

---

## 11. Rollback Reference / Backup Path

| Field | Value |
|-------|-------|
| Backup path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2_before_rsr6_cleanup_20260528T124212Z.db` |
| Restore command | `cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2_before_rsr6_cleanup_20260528T124212Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'` |
| Verify after restore | `sqlite3 /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"` |

To rollback: copy the backup over the production DB and verify row count = 72,462.

---

## 12. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No controlled_apply in RSR-6 cleanup | ✓ |
| No replay rows inserted | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler / cron / launchd install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |
| P126B–P126F rows untouched | ✓ |

---

## 13. Remaining Risks

1. `power_precision_3bet` and `power_orthogonal_5bet` have `bet_index=1` rows with
   `replay_run_id=2,6` and `controlled_apply_id IS NULL` — these are **not orphans** but
   must be reviewed in the apply gate re-evaluation.
2. P10/P12 apply gate re-evaluation must verify `bet_index=1` rows are valid before
   any `controlled_apply` proceeds.
3. P128 Phase 3 dry-run scope must exclude `bet_index=2` rows for P10/P12.

---

## 14. Recommended Next Task

**P128 Phase 3**: dry-run / apply readiness re-evaluation for safe Wave 2 candidates.
Order: P7/P8/P9/P11 first (no RSR-6 blocks), then P10/P12 after apply gate re-evaluation.

---

## 15. Final Classification

```text
RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED
```

Orphan selector count after cleanup: **0** (expected 0) ✓
