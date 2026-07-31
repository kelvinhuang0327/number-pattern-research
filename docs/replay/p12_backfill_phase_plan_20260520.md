# P12 Backfill Phase Plan
**Date:** 2026-05-20  
**Classification:** P12_1500_DRAW_BACKFILL_PLAN_READY  
**Production rows at time of plan:** 460 (unchanged)  
**Target:** 8 ONLINE strategies × 1500 draws = 12,000 rows

---

## Phase 0 — Baseline (已完成)

| 項目 | 狀態 |
|------|------|
| Production rows | 460 |
| Baseline tests | 351/351 PASS |
| Drift guard | PASS |
| Branch | feat/p0-single-repo-stabilization-p1-catalog-plan-20260519 |
| Registry strategies | 18 total (8 ONLINE) |
| Catalog universe | 59 total (41 ARTIFACT_ONLY) |

---

## Phase 1 — 2 ONLINE Strategies × 1500 Draws (Dry-run)

**目標：** 驗證 backfill engine 可正確執行  
**策略選擇：**
- `daily539_f4cold` (DAILY_539, 90 existing rows, proven)
- `power_precision_3bet` (POWER_LOTTO, 70 existing rows, proven)

**執行參數：**
```
draw_window:    1500 draws
strategy_count: 2
estimated_rows: 3,000
dry_run:        True (dry_run=1, no DB write)
```

**接受標準：**
- ✅ 全 3000 rows 有合法 predicted_numbers（從 adapter 執行得出）
- ✅ 全 3000 rows 有合法 actual_numbers（從 draws 表讀取）
- ✅ hit_count 計算正確（交集）
- ✅ 無 fabricated rows
- ✅ 無 future data leakage
- ✅ production DB rows 仍為 460（dry-run 不寫入）
- ✅ 輸出 JSON dry-run report

**執行 script（待 P13 建立）：**
```
scripts/p13_backfill_engine_dryrun.py \
  --strategies daily539_f4cold,power_precision_3bet \
  --draw-window 1500 \
  --dry-run
```

**STOP conditions：**
- dry-run JSON 中有任何 fake_numbers_detected=true → STOP
- 任何 adapter 執行出現 causal slice violation → STOP
- production rows 變動 → STOP

---

## Phase 2 — Phase 1 Apply Gate

**前提：**
- Phase 1 dry-run 通過所有接受標準
- CEO 明確授權 phrase: `"YES apply P12 Phase 1 backfill rows"`

**執行：**
```
scripts/p13_backfill_engine_apply.py \
  --dry-run-json outputs/replay/p13_phase1_dryrun_<timestamp>.json \
  --authorization "YES apply P12 Phase 1 backfill rows"
```

**Apply 後：**
- Production rows: 460 + 3,000 = 3,460（預期，扣除已有 rows 的 dedup）
- Rollback ID: `P12_PHASE1_APPLY_<timestamp>`

**Rollback 方式：**
```sql
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P12_PHASE1_APPLY_<timestamp>';
```

**授權等級：** CEO 授權 required. No engineer can self-authorize.

---

## Phase 3 — All 8 ONLINE Strategies × 1500 Draws (Dry-run)

**目標：** 擴展到全 8 ONLINE strategies  
**新增策略（相對 Phase 1）：**
- `power_orthogonal_5bet` (POWER_LOTTO)
- `fourier_rhythm_3bet` (POWER_LOTTO, 目前 0 rows)
- `biglotto_triple_strike` (BIG_LOTTO)
- `biglotto_deviation_2bet` (BIG_LOTTO)
- `ts3_regime_3bet` (BIG_LOTTO, 目前 0 rows)
- `daily539_markov_cold` (DAILY_539)

**估算：**
```
8 strategies × 1500 draws = 12,000 rows (理論)
實際 = 12,000 - 已有 460 rows (dedup) ≈ 11,540 new rows
```

**特別注意：**
- `fourier_rhythm_3bet` 和 `ts3_regime_3bet` 目前 0 rows
- 這兩個策略需要額外驗證（dry-run 先確認 adapter 正確執行）
- 這兩個策略的 dry-run 結果需獨立 CEO review 後再 apply

**接受標準（同 Phase 1，加上）：**
- ✅ `fourier_rhythm_3bet` dry-run 無 REPLAY_ERROR（或有紀錄說明的 INSUFFICIENT_HISTORY）
- ✅ `ts3_regime_3bet` dry-run 同上

---

## Phase 4 — API Pagination / Query Optimization

**觸發條件：** Phase 3 dry-run 或 apply 完成後  
**目標 rows：** 12,000  
**任務：**

1. **Composite index 評估：**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_spr_strategy_lottery_draw
   ON strategy_prediction_replays(strategy_id, lottery_type, target_draw DESC);
   ```

2. **API pagination 實作：**
   ```
   GET /api/replay/history?page=1&per_page=50&strategy_id=X&lottery_type=Y
   ```
   - cursor-based pagination（避免 OFFSET）
   - 最大 per_page=200

3. **Query plan 驗證：**
   ```sql
   EXPLAIN QUERY PLAN
   SELECT * FROM strategy_prediction_replays
   WHERE strategy_id=? AND lottery_type=? ORDER BY target_draw DESC LIMIT 50;
   ```

4. **Load test：** 12,000 rows 下 P95 query < 100ms

---

## Phase 5 — OBSERVATION / REJECTED / RETIRED Governance

**目標：** 決定是否重新啟用或永久封存非 ONLINE 策略  

**OBSERVATION (h6_gate_mk20_ew85)：**
- 目前 shadow evaluation 中
- 若 shadow eval 通過 → PROMOTE to ONLINE → Phase 3.5 dry-run
- 若失敗 → RETIRE with documented reason

**REJECTED (4 strategies)：**
- 可重新評估（新資料、新方法）
- 必須先 unREJECT → OBSERVATION → ONLINE 流程
- 不得 skip governance 直接 backfill

**RETIRED (5 strategies)：**
- 需獨立人工授權 + 獨立 replay run ID
- 需額外的 truth_level 標記（不與 ONLINE 策略混用）
- 不在 P12–P20 主線路徑

---

## Phase 6 — Production Launch

**前提：**
- Phase 3 apply 完成（8 strategies × 1500 draws ≥ 11,540 new rows）
- Phase 4 API pagination 實作並通過測試
- UI 歷史清單整合完成（Phase 5b）
- 全量 tests PASS（原 351 + 新增 P12–P20 tests）
- drift guard PASS
- CEO launch checklist 完成

**Launch checklist（示例，P20 定義詳細版）：**
- [ ] production rows ≥ 12,000
- [ ] all 8 ONLINE strategies covered
- [ ] UI pagination 正常
- [ ] API p95 latency < 200ms
- [ ] no fake rows in DB
- [ ] all drift guard checks PASS
- [ ] rollback procedure tested
- [ ] monitoring alerts configured

---

## 各 Phase 輸出文件

| Phase | 必要輸出 |
|-------|---------|
| P12 | gap_analysis JSON + realignment doc + architecture doc + phase plan |
| P13 | backfill_engine.py + dry-run result JSON |
| P14 | phase1_dryrun_report.md + apply gate script |
| P15 | phase1_apply_result.json + rollback verification |
| P16 | phase3_all_online_dryrun_report.md |
| P17 | api_pagination_design.md + index migration |
| P18 | UI integration PR |
| P19 | governance_review_OBSERVATION.md + governance_review_RETIRED.md |
| P20 | launch_checklist.md |

---

## 禁止事項（全 Phase 適用）

- ❌ 不得 fabricate predicted_numbers / actual_numbers / hit_count
- ❌ 不得把 artifact-only 算作 executable
- ❌ 不得把 NO_DATA 算作 success
- ❌ 不得在 CEO 授權前 apply 任何 rows
- ❌ 不得跳過 dry-run 直接 apply
- ❌ 不得把 28-row P7 apply 描述為產品完成
- ❌ 不得優先 merge branch（P12 backfill plan 先於 merge 決策）

---

*Plan only. No implementation. Production rows remain 460.*
