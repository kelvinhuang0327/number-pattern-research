# P3B-C Controlled Draw Import Report
**Date**: 2026-05-16  
**controlled_import_id**: P3BC_20260516  
**Branch**: chore/p3bc-controlled-draw-import-20260516  

---

## 1. 本輪目標

P3B-C 目標：將 P3B-B dry-run 驗證的 2 筆官方 draw 寫入 DB，並重新執行
剩餘 6 筆 PENDING prediction_items 的 replay dry-run 以確認可解析性。

**本輪嚴格限制**：
- ✅ 允許：INSERT 2 筆 draw row 至 draws 表
- ❌ 禁止：replay row 寫入
- ❌ 禁止：prediction_items 更新
- ❌ 禁止：prediction_runs 更新
- ❌ 禁止：strategy 邏輯修改
- ❌ 禁止：API/UI/backend 行為改動

---

## 2. Authorization

```
controlled_import_id: P3BC_20260516
Authorization confirmed by user.

YES import draws:
  - DAILY_539: 115000106 / 2026/04/30 / [6,15,27,30,31]
  - POWER_LOTTO: 115000035 / 2026/04/30 / [1,4,13,19,27,30] / special=8
```

---

## 3. Imported Draws Table

| lottery_type | draw      | date       | numbers              | special |
|---|---|---|---|---|
| DAILY_539    | 115000106 | 2026/04/30 | [6, 15, 27, 30, 31]  | —       |
| POWER_LOTTO  | 115000035 | 2026/04/30 | [1, 4, 13, 19, 27, 30] | 8     |

Receipt: `outputs/replay/p3bc_controlled_draw_import_receipt_20260516.json`

---

## 4. Post-import DB Verification

| Check | Expected | Result | PASS/FAIL |
|---|---|---|---|
| DAILY_539 115000106 in draws | present | `date=2026/04/30 numbers=[6,15,27,30,31]` | ✅ PASS |
| POWER_LOTTO 115000035 in draws | present | `date=2026/04/30 numbers=[1,4,13,19,27,30] special=8` | ✅ PASS |
| replay_rows_inserted | False | False | ✅ PASS |
| replay_total | 969 | 969 | ✅ PASS |

---

## 5. Prediction Items Unchanged Confirmation

All 6 target items remain **PENDING** after draw import:

| item_id | run_id | status   |
|---|---|---|
| 1072    | 168    | PENDING  |
| 1073    | 168    | PENDING  |
| 1074    | 168    | PENDING  |
| 1087    | 173    | PENDING  |
| 1088    | 173    | PENDING  |
| 1089    | 173    | PENDING  |

---

## 6. Replay Rows Unchanged Confirmation

- `strategy_prediction_replays` count before import: **969**
- `strategy_prediction_replays` count after import: **969**
- Delta: **0** — no replay rows were inserted in P3B-C ✅

---

## 7. Remaining 6 Replay Dry-Run Result

Script: `scripts/p3bc_remaining_pending_replay_dryrun.py`  
Output: `outputs/replay/p3bc_remaining_pending_replay_dryrun_20260516.json`

**Summary**:
- `eligible_count`: **6**
- `blocked_count`: **0**
- `replay_rows_inserted`: **False**
- `prediction_items_modified`: **False**
- `final_classification`: **P3BC_REMAINING_PENDING_REPLAY_DRYRUN_READY**

**Per-item results**:

| item_id | lottery_type | target_draw | predicted                | actual                  | matched   | hits |
|---|---|---|---|---|---|---|
| 1072    | POWER_LOTTO  | 115000035   | [12,22,24,26,29,37]      | [1,4,13,19,27,30]       | []        | 0    |
| 1073    | POWER_LOTTO  | 115000035   | (from run 168)           | [1,4,13,19,27,30]       | [4,27]    | 2    |
| 1074    | POWER_LOTTO  | 115000035   | (from run 168)           | [1,4,13,19,27,30]       | [13]      | 1    |
| 1087    | DAILY_539    | 115000106   | [9,16,23,37,39]          | [6,15,27,30,31]         | []        | 0    |
| 1088    | DAILY_539    | 115000106   | (from run 173)           | [6,15,27,30,31]         | [30]      | 1    |
| 1089    | DAILY_539    | 115000106   | (from run 173)           | [6,15,27,30,31]         | [31]      | 1    |

---

## 8. Safety Confirmation

| Safety Check | Result |
|---|---|
| Only 2 authorized draws inserted | ✅ PASS |
| No unauthorized draws inserted | ✅ PASS |
| No replay rows inserted (replay_total=969) | ✅ PASS |
| No prediction_items updated (all 6 still PENDING) | ✅ PASS |
| No prediction_runs updated | ✅ PASS |
| No strategy logic changed | ✅ PASS |
| No API/UI/backend modified | ✅ PASS |
| Idempotency check implemented | ✅ PASS |
| --apply required flag implemented | ✅ PASS |
| --controlled-import-id validation | ✅ PASS |

**Note**: A previous P3B-C session (commit 4252972) had exceeded scope by inserting replay rows
and resolving prediction_items. This session rolled back those over-scope DB changes and
re-executed P3B-C strictly within authorized scope before creating this commit.

---

## 9. Remaining Risks

1. **Replay apply (P3B-D) pending**: The 6 PENDING items have draws available and dry-run is READY.
   Operator must authorize P3B-D to actually resolve them.
2. **Data integrity**: POWER_LOTTO item 1072 has 0 hits (predicted [12,22,24,26,29,37] vs actual [1,4,13,19,27,30]).
   This is expected — some predictions will miss.
3. **P3B-B PR #119** remains as draft (replay-default-validation failing). P3B-C builds on top of
   P3B-B branch. Ensure P3B-B is merged or P3B-C is rebased onto main when P3B-B merges.

---

## 10. Next Step Recommendation

**P3BC_REMAINING_PENDING_REPLAY_DRYRUN_READY** — Recommend proceeding to **P3B-D**.

P3B-D scope:
- Authorized operator approval for controlled replay apply
- Apply 6 OFFICIAL replay rows for items 1087–1089 (DAILY_539) and 1072–1074 (POWER_LOTTO)
- Update prediction_items 1072–1074 and 1087–1089 status from PENDING → RESOLVED
- Update drift guard baseline: 969 → 975
- Run 109/109 tests to confirm PASS

---

*Generated by P3B-C Controlled Draw Import Agent — controlled_import_id: P3BC_20260516*
