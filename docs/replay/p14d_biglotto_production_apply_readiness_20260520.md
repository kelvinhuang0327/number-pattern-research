# P14D — Big Lotto Production Apply Readiness Review

**Date:** 2026-05-20  
**Phase:** P14D_BIGLOTTO_PRODUCTION_APPLY_READINESS  
**Apply Authorization:** PRESENT — `YES apply Big Lotto single strategy replay rows`

---

## 1. Objective

Review all prerequisites before writing 1500 `ts3_regime_3bet` BIG_LOTTO replay
rows to the production `strategy_prediction_replays` table. Apply is executed
only if this review passes all gates.

---

## 2. Production Apply Authorization Gate

| Gate | Status |
|------|--------|
| Branch authorization phrase | PRESENT ✓ |
| Production apply phrase | PRESENT ✓ |
| Required phrase | `YES apply Big Lotto single strategy replay rows` |

---

## 3. Selected Strategy

| Field | Value |
|-------|-------|
| strategy_id | `ts3_regime_3bet` |
| strategy_name | 大樂透 TS3+Regime 3注 |
| lifecycle_status | ONLINE |
| RSM edge (300p) | +3.51% |
| Sharpe | 0.123 |

---

## 4. BIG_LOTTO Draw Data Status

| Field | Value |
|-------|-------|
| Total BIG_LOTTO draws | 2135 |
| Draw range | 96000001 – 115000053 |
| Target window | 1500 most recent draws |
| numbers/special parseable | ✓ |

---

## 5. P14B Dry-Run Summary

| Metric | Value |
|--------|-------|
| ready_candidates | 1500 |
| blocked_candidates | 0 |
| fake_success_count | 0 |
| production_rows_before/after | 460 / 460 |

---

## 6. P14C Temp DB Rehearsal Summary

| Metric | Value |
|--------|-------|
| temp apply (460→1960) | ✓ inserted=1500, errors=0 |
| idempotency rerun | ✓ inserted=0, dupes=1500 |
| rollback (1960→460) | ✓ deleted=1500 |
| production rows unchanged | ✓ |
| classification | P14C_TEMP_DB_REHEARSAL_READY |

---

## 7. Expected Rows Before / After Apply

| Metric | Value |
|--------|-------|
| production_rows_before | 460 |
| planned_insert_count | 1500 |
| expected_rows_after | **1960** |

---

## 8. Apply Metadata

| Field | Value |
|-------|-------|
| controlled_apply_id | `P14D_BIGLOTTO_TS3_1500_PROD_20260520` |
| truth_level | `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` |
| source | `P14D_BIGLOTTO_PRODUCTION_APPLY` |
| dry_run flag | 0 (production) |
| duplicate detection key | `(strategy_id, lottery_type, target_draw)` |

---

## 9. Duplicate Detection Policy

Apply uses `(strategy_id, lottery_type, target_draw)` as the natural key to
detect duplicates. Any row already present with the same combination is
skipped (idempotent). This matches the P14C rehearsal behavior.

---

## 10. Rollback Plan

```bash
python3 scripts/p14d_biglotto_production_apply.py \
  --rollback \
  --expected-rows 1960
```

Rollback deletes all rows WHERE `controlled_apply_id = P14D_BIGLOTTO_TS3_1500_PROD_20260520`.
Returns production rows to 460.

---

## 11. Post-Apply Verification Steps

```bash
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# Expected: 1960

.venv/bin/python scripts/replay_lifecycle_drift_guard.py --strict
# Expected: PASS (legacy=460, p14d=1500, total=1960)

.venv/bin/python scripts/replay_branch_governance_guard.py \
  --expected-branch main --expected-rows 1960
# Expected: PASS

.venv/bin/python -m pytest -q
# All tests must PASS after test baseline updates
```

---

## 12. Drift Guard Impact

After apply, the drift guard baseline must reflect:

| Bucket | Before | After |
|--------|--------|-------|
| legacy (apply_id IS NULL) | 460 | 460 (unchanged) |
| P14D (`P14D_BIGLOTTO_TS3_1500_PROD_20260520`) | 0 | 1500 |
| total | 460 | **1960** |

`BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` added to `ALLOWED_TRUTH_LEVELS`.

---

## 13. Governance Guard Impact

Post-apply governance guard must be called with `--expected-rows 1960`.
Tests updated from 460 → 1960.

---

## 14. Tests Requiring Baseline Update After Apply

| Test file | Change |
|-----------|--------|
| `test_replay_lifecycle_drift_guard.py` | total=460→1960, p14d=1500, allow new truth_level |
| `test_replay_branch_governance_guard.py` | expected-rows 460→1960, production_rows 460→1960 |
| `test_p14b_biglotto_single_strategy_replay_dry_run.py` | live DB check updated to PROD_ROWS_CURRENT=1960 |
| `test_p14c_biglotto_single_strategy_tempdb_rehearsal.py` | temp_db fixture isolated to legacy-only rows; live DB check updated |

---

## 15. Final Recommendation

All gates PASS. Production apply is authorized and safe to execute.

**Production apply was performed in this session (P14D).**  
Production rows: 460 → **1960**.  
controlled_apply_id: `P14D_BIGLOTTO_TS3_1500_PROD_20260520`
