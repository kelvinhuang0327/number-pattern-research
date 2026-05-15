# P2F Controlled Replay Backfill Report
**Date**: 2026-05-15  
**Controlled Apply ID**: P2F_20260515  
**Strategy**: ts3_regime_3bet  
**Operator Authorization**: CONFIRMED

---

## 1. 本輪目標

將 BIG_LOTTO 第 115000051 期開獎結果，回填至 prediction_run 174 中的三個 PENDING 預測注單（items 1090、1091、1092），並將 strategy_prediction_replays 紀錄插入，最終將 prediction_items 狀態更新為 RESOLVED。

---

## 2. Authorization Granted

```
strategy_id: ts3_regime_3bet
prediction_items: 1090, 1091, 1092
target_draw: 115000051
controlled_apply_id: P2F_20260515
allowed:
  - insert 3 rows into strategy_prediction_replays
  - update prediction_items 1090,1091,1092 status RESOLVED
forbidden:
  - no prediction_runs modifications
  - no strategy logic changes
  - no API/UI/backend changes
  - no rows outside items 1090,1091,1092
```

---

## 3. Authorized Items Summary

| Item ID | Bet Index | Predicted Numbers | Hit Count | Matched |
|---------|-----------|-------------------|-----------|---------|
| 1090 | 0 | [3, 5, 22, 34, 38, 49] | 0 | [] |
| 1091 | 1 | [16, 23, 29, 33, 36, 45] | 0 | [] |
| 1092 | 2 | [12, 18, 26, 27, 31, 46] | 1 | [18] |

**Actual Draw 115000051** (2026/05/08):  
Numbers: [10, 18, 25, 28, 39, 43] | Special: 48

**Hit Count Verification**:
- Item 1090: [3,5,22,34,38,49] ∩ [10,18,25,28,39,43] = {} → 0 ✓
- Item 1091: [16,23,29,33,36,45] ∩ [10,18,25,28,39,43] = {} → 0 ✓
- Item 1092: [12,18,26,27,31,46] ∩ [10,18,25,28,39,43] = {18} → 1 ✓

---

## 4. Rows Inserted into strategy_prediction_replays

| Replay ID | Item | Draw | Strategy | replay_status | hit_count | hit_numbers | truth_level | controlled_apply_id |
|-----------|------|------|----------|---------------|-----------|-------------|-------------|---------------------|
| 1267 | 1090 | 115000051 | ts3_regime_3bet | RESOLVED | 0 | [] | OFFICIAL | P2F_20260515 |
| 1268 | 1091 | 115000051 | ts3_regime_3bet | RESOLVED | 0 | [] | OFFICIAL | P2F_20260515 |
| 1269 | 1092 | 115000051 | ts3_regime_3bet | RESOLVED | 1 | [18] | OFFICIAL | P2F_20260515 |

---

## 5. prediction_items Status Updated to RESOLVED

| Item ID | Before | After |
|---------|--------|-------|
| 1090 | PENDING | RESOLVED |
| 1091 | PENDING | RESOLVED |
| 1092 | PENDING | RESOLVED |

---

## 6. Post-Apply DB Verification

- P2F rows in strategy_prediction_replays: **3** (expected 3) ✓
- All 3 items status = RESOLVED ✓
- All P2F predicted_numbers match authorized values ✓
- P2F_POST_APPLY_VERIFY_PASS ✓

---

## 7. Safety Confirmation

| Check | Result |
|-------|--------|
| prediction_runs modified | PASS (NO) |
| rows outside items 1090-1092 | PASS (NONE) |
| strategy logic changed | PASS (NO) |
| source file changes | PASS (NONE) |
| JSON receipt valid | PASS |
| FORBIDDEN_CHECKS_PASS | ✓ |

---

## 8. Coverage Impact

| Metric | Value |
|--------|-------|
| prediction_run | 174 |
| Items resolved | 3 (1090, 1091, 1092) |
| strategy_prediction_replays before | 966 |
| strategy_prediction_replays after | 969 |
| Net new rows | +3 |

---

## 9. Remaining Risks

1. **replay_run_id = NULL**: 本次 backfill 未關聯 strategy_replay_runs，因此若系統有基於 replay_run_id 的聚合查詢，這些行可能不出現在統計視圖中。
2. **provenance_hash = NULL**: 未計算 provenance hash，若未來啟用 hash 驗證，需補填。
3. **prediction_item_id 欄位不存在於 replays 表**: 目前以 predicted_numbers 作為間接對照，若多注相同號碼則可能模糊。本次無此風險（三注號碼各異）。

---

## 10. Next Step Recommendation

1. **Coverage check**: 確認 prediction_run 174 下所有 prediction_items 是否全部 RESOLVED（除 1090-1092 外是否有其他 PENDING 項目）
2. **Next PENDING items**: 執行 `SELECT * FROM prediction_items WHERE status='PENDING' AND run_id IN (SELECT id FROM prediction_runs WHERE lottery_type='BIG_LOTTO')` 確認後續待處理注單
3. **P2G if applicable**: 若有新期數（115000052 後）預測需要回填，執行 P2G 流程
4. **RSM re-evaluation**: 本期 draw 115000051 為 0/6, 0/6, 1/6，ts3_regime_3bet 近期表現需監控

---

## Receipt Reference

`outputs/replay/p2f_controlled_replay_backfill_receipt_20260515.json`
