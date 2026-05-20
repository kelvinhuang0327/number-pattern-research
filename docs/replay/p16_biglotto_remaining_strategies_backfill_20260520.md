# P16 — Big Lotto Remaining ONLINE Strategies Backfill

**Date:** 2026-05-20  
**Branch:** p16-biglotto-remaining-strategies-backfill  
**Classification:** P16_PENDING_APPLY_AUTHORIZATION

---

## 1. 本輪目標

P14D 已完成 `ts3_regime_3bet` 的 1500 draws backfill（1500 rows，production 共 1960 rows）。
P16 目標：對另外兩個 ONLINE BIG_LOTTO 策略執行相同流程。

- `biglotto_triple_strike`
- `biglotto_deviation_2bet`

---

## 2. Remaining Strategies

| strategy_id | lifecycle_status | supported_lottery_types | adapter | existing legacy rows |
|---|---|---|---|---|
| biglotto_triple_strike | ONLINE | BIG_LOTTO | `_BigLottoTripleStrikeAdapter` | 70 |
| biglotto_deviation_2bet | ONLINE | BIG_LOTTO | `_BigLottoDeviation2BetAdapter` | 70 |

Both adapters are callable via `get_one_bet(history, "BIG_LOTTO")`.  
No external data sources required.

---

## 3. Dry-Run Result

**Output:** `outputs/replay/p16_biglotto_remaining_strategies_dry_run_20260520.json`

| metric | value |
|---|---|
| target_draw_window | 1500 |
| generated_candidates | 3000 |
| ready_candidates | 3000 |
| blocked_candidates | 0 |
| fake_success_count | 0 |
| dry_run_only | true |
| production_rows_before | 1960 |

Per-strategy breakdown:

| strategy_id | ready | blocked | duplicate |
|---|---|---|---|
| biglotto_triple_strike | 1500 | 0 | 0 |
| biglotto_deviation_2bet | 1500 | 0 | 0 |

---

## 4. Existing Duplicate Analysis

The 70 legacy rows for each strategy cover draws **`99000056`–`99000105`** (year ~1999/2000).  
The 1500-draw backfill window begins at draw **`102000009`** (2013/01/29).

Since all legacy rows predate the window, **there are 0 duplicates** within the 1500-draw target window.  
The `duplicate_existing_count = 0` is derived from real DB dedup detection, not hardcoded.

Legacy rows will remain untouched after production apply.

---

## 5. Planned Insert Count

| strategy | draws in window | duplicates in window | planned new rows |
|---|---|---|---|
| biglotto_triple_strike | 1500 | 0 | 1500 |
| biglotto_deviation_2bet | 1500 | 0 | 1500 |
| **total** | **3000** | **0** | **3000** |

---

## 6. Temp DB Rehearsal Result

**Output:** `outputs/replay/p16_biglotto_remaining_strategies_tempdb_rehearsal_20260520.json`

| metric | value |
|---|---|
| initial_rows | 1960 |
| planned_insert_count | 3000 |
| r1_inserted_count | 3000 |
| r1_duplicate_count | 0 |
| temp_applied_rows | 4960 |
| final_classification | P16_TEMP_REHEARSAL_PASS |

---

## 7. Idempotency Result

| metric | value |
|---|---|
| r2_inserted_count | 0 |
| r2_duplicate_count | 3000 |
| idempotency_pass | true |

Rerun inserted exactly 0 rows — all candidates recognized as duplicates of the just-inserted rows.

---

## 8. Rollback Result

| metric | value |
|---|---|
| rollback_deleted_count | 3000 |
| rows_after_rollback | 1960 |
| rollback_pass | true |

Production DB restored to 1960 rows after rollback. Confirmed by `SELECT COUNT(*)`.

---

## 9. Production Apply Authorization Status

**Status: PENDING_AUTHORIZATION**

- Branch authorization: **PRESENT** (`YES create new branch for P16 Big Lotto remaining strategies backfill`)
- Production apply phrase: **NOT PRESENT** (`YES apply Big Lotto remaining strategies replay rows`)

No production DB write has been performed. Production rows remain = **1960**.

---

## 10. Expected Rows After Apply

If production apply is authorized:

| phase | rows |
|---|---|
| before apply | 1960 |
| + biglotto_triple_strike new rows | +1500 |
| + biglotto_deviation_2bet new rows | +1500 |
| **after apply** | **4960** |

Legacy rows (70 × 2 = 140) remain untouched.

---

## 11. API / Page Implication

After production apply, the replay history API will serve:

- `GET /api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_triple_strike` → total=1570 (1500 new + 70 legacy)
- `GET /api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_deviation_2bet` → total=1570 (1500 new + 70 legacy)

The `display_status`, `visibility_state`, `should_count_as_success`, and all 15 required replay fields will be present.

---

## 12. Next Recommendation

To complete P16 production apply:

1. Provide explicit phrase: `YES apply Big Lotto remaining strategies replay rows`
2. P16 script will:
   - Verify production rows = 1960
   - Create backup at `backups/lottery_v2_pre_p16_biglotto_remaining_apply_20260520.db`
   - Insert 3000 rows with `controlled_apply_id=P16_BIGLOTTO_REMAINING_1500_PROD_20260520`
   - Verify rows = 4960 after apply
   - Update drift guard expected rows to 4960
   - Update governance guard expected rows to 4960
   - Run full test suite

After apply, update the following expected-rows baselines:
- `scripts/replay_lifecycle_drift_guard.py`
- `scripts/replay_branch_governance_guard.py`
- `tests/test_replay_branch_governance_guard.py`
- `tests/test_replay_lifecycle_drift_guard.py`

Merge into main and verify CI: `replay-default-validation`, `replay-browser-e2e`.
