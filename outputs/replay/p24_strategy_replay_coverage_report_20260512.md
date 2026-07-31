# P24 Strategy Replay Coverage Report — CEO Review
**版本:** 20260512  
**任務:** Stage E — CEO-facing coverage report  
**分類:** PRODUCT COVERAGE / OPERATOR VISIBILITY  
**狀態:** CEO_REVIEW_20260512_PRODUCT_COVERAGE_PRIORITY_LOCKED

---

## 摘要（Executive Summary）

本報告盤點彩券回放系統中所有已開發策略的 **顯示完整性** 與 **產品覆蓋範圍**。

**關鍵發現**: 系統目前有 16 個 canonical lifecycle 策略，但 Replay 頁面只有在 `ONLINE` lifecycle 下才能正常顯示 6 個策略的歷史回放。其餘 10 個 REJECTED/RETIRED/OBSERVATION 策略雖存在於 catalog，但在 UI 上**無法被使用者發現**，形成產品透明度缺口。

---

## 一、策略覆蓋全景

### 1.1 生命週期覆蓋

```
ONLINE       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  6 個策略 / 460 production replay rows
REJECTED     ▓▓▓▓░░░░░░░░░░░░░░  4 個策略 / 0 production replay rows (catalog only)
RETIRED      ▓▓▓▓▓░░░░░░░░░░░░░  5 個策略 / 0 production replay rows (catalog only)
OBSERVATION  ▓░░░░░░░░░░░░░░░░░  1 個策略 / 0 production replay rows (catalog only)
OFFLINE      ░░░░░░░░░░░░░░░░░░  0 個策略 (reserved, not yet used)
UNKNOWN      ░░░░░░░░░░░░░░░░░░  ~5 個在 wiki/memory (not in registry)
```

### 1.2 Operator Visibility（目前）

| 策略 | lifecycle | 在 UI 可見? | 備註 |
|---|---|---|---|
| power_precision_3bet | ONLINE | ✅ 完整顯示 | |
| power_orthogonal_5bet | ONLINE | ✅ 完整顯示 | |
| biglotto_triple_strike | ONLINE | ✅ 完整顯示 | |
| biglotto_deviation_2bet | ONLINE | ✅ 完整顯示 | |
| daily539_f4cold | ONLINE | ✅ 完整顯示（含 20 error rows）| |
| daily539_markov_cold | ONLINE | ✅ 完整顯示（含 20 error rows）| |
| biglotto_ts3_acb_4bet | REJECTED | ❌ **不可見** | lifecycle filter 無 rows → 空白 |
| biglotto_ts3_markov_freq_5bet | REJECTED | ❌ **不可見** | 同上 |
| power_shlc_midfreq | REJECTED | ❌ **不可見** | 同上 |
| p1_deviation_2bet_539 | REJECTED | ❌ **不可見** | 同上 |
| acb_1bet | RETIRED | ❌ **不可見** | 同上 |
| acb_markov_midfreq | RETIRED | ❌ **不可見** | 同上 |
| acb_markov_midfreq_3bet | RETIRED | ❌ **不可見** | 同上 |
| midfreq_acb_2bet | RETIRED | ❌ **不可見** | 同上 |
| midfreq_fourier_2bet | RETIRED | ❌ **不可見** | 同上 |
| h6_gate_mk20_ew85 | OBSERVATION | ❌ **不可見** | 同上 |

**結論**: 16 個 canonical 策略中，只有 6 個（37.5%）在 UI 上可見。  
剩下 10 個（62.5%）雖存在於 catalog，但在 Replay 頁面上是隱形的。

---

## 二、Display Gap 根因分析

### 2.1 技術根因

1. `GET /api/replay/history?lifecycle_status=REJECTED` → `SELECT FROM strategy_prediction_replays WHERE strategy_id IN (REJECTED strategies)`
2. 因為無 production replay rows → `total: 0, records: []`
3. 前端收到 empty → 渲染空白

**系統設計假設**: replay history endpoint 假設「策略存在 = 有 production rows」，但 non-ONLINE 策略根本不會被生成 replay rows。

### 2.2 Business Impact

- **透明度不足**: 使用者無法知道哪些策略被拒絕及原因
- **決策可追溯性降低**: 研究員無法通過 UI 驗收 governance 決策
- **OBSERVATION 策略不可見**: h6_gate_mk20_ew85 正在 shadow evaluation，但在 UI 上完全看不到

---

## 三、修復方案

詳見 `p24_display_only_catalog_spec_20260512.md`（Stage B）。

**方案摘要**: 前端 Catalog Display Mode — 當 lifecycle 篩選返回 empty，從 `/api/replay/strategies` 獲取 catalog 策略清單並顯示為 placeholder 行，附上 lifecycle badge。

**方案特點**:
- ✅ 純前端 JavaScript 改動（最小影響範圍）
- ✅ 不需要 DB 寫入或 backfill
- ✅ 不需要 registry schema 變更  
- ✅ 不需要 API 新 endpoint（`/api/replay/strategies` 已存在）
- ✅ 符合 replay_data_hygiene.md §4（無下注推薦語句）

---

## 四、UX Parity 差距

詳見 `p24_ux_parity_gap_20260512.md`（Stage C）。

**P1 Gap 清單**:
1. `CATALOG_DISPLAY_MODE_REQUIRED` — 修復 non-ONLINE lifecycle 空白問題
2. `EMPTY_STATE_MESSAGE_FIX_REQUIRED` — 修復 ONLINE 查無資料時的空白

**P2 Gap 清單（backlog）**:
3. `SEARCH_INPUT_BACKLOG` — 文字搜尋
4. `SORT_CONTROL_BACKLOG` — 排序切換

---

## 五、Extended Catalog 决策點

### 5.1 rejected/ folder vs. canonical registry

| 來源 | 策略數 | 在 registry | 在 UI |
|---|---|---|---|
| canonical registry REJECTED stubs | 4 | ✅ | ❌ (gap) |
| rejected/ folder（net additional）| ~69 | ❌ | ❌ |

**CEO 決策問題**: 是否需要將 rejected/ folder 中的 ~69 個策略加入 canonical registry stubs，使其在 UI 上可見？

**建議**: 
- **短期**: 先修復 4 個 canonical REJECTED stubs 的顯示問題（Stage B spec）
- **長期**: 由 CEO + governance 決定 extended catalog registry admission 範圍

### 5.2 Production Replay Backfill 決策點

**CEO 決策問題**: 是否需要為 REJECTED/RETIRED 策略生成 historical replay rows？

**建議**: 
- **非必要**: display-only catalog mode 已足夠滿足可見性需求
- **若需要**: 需新的 replay runner job、governance 審核、data hygiene 規則更新

---

## 六、h6_gate_mk20_ew85 特殊處理建議

**當前狀態**: 
- wiki 記載為 DAILY_539 live production strategy（shadow evaluation）
- canonical registry 中 `lifecycle = OBSERVATION`, `supported_lottery_types = ["POWER_LOTTO"]`
- **不一致**: lottery_type 不匹配

**建議**: 由工程師核實 h6_gate_mk20_ew85 在 registry 中的 `supported_lottery_types`，確認是否應為 `["DAILY_539"]` 或 `["POWER_LOTTO"]`。

**行動碼**: `H6_LOTTERY_TYPE_REGISTRY_DISCREPANCY_CHECK`

---

## 七、PR #64 狀態

**PR #64** (`docs/p23-fixture-mode-ui-toggle-final-validation-20260511`):
- 狀態: OPEN / MERGEABLE / CLEAN
- CI 通過: `replay-browser-e2e-validation` ✅, `replay-default-validation` ✅
- **等待 CEO 授權 merge**

**行動碼**: `WAITING_FOR_USER_YES_GATE_PR64`

---

## 八、優先行動清單（CEO 視角）

| 優先 | 行動 | 工作量估計 | 阻塞點 |
|---|---|---|---|
| **P0** | Merge PR #64 | 0（已就緒）| 等待 CEO 授權 |
| **P1** | 實作 Catalog Display Mode | M（~1hr frontend JS）| None |
| **P1** | 修復 Empty State 文字 | S（~10min）| None |
| **P2** | h6 lottery_type 核實 | S（~15min review）| None |
| **P3** | extended catalog admission policy | XL（governance）| CEO decision |
| **P3** | Production replay backfill decision | XL（governance）| CEO decision |

---

## 九、Safety Invariants（本報告期間）

| 項目 | 值 |
|---|---|
| production DB write | ❌ 無 |
| lottery_api/data/lottery_v2.db | READ-ONLY |
| data/lottery_v2.db | UNTOUCHED |
| registry schema change | ❌ 無 |
| new betting recommendation | ❌ 禁止 |
| DB backfill | ❌ 無 |
| strategy mining | ❌ 無 |
| fixture artifacts created | ❌ 無 |

---

**P24_POST_RUN_DB_CLEAN**  
**CEO_REVIEW_20260512_PRODUCT_COVERAGE_PRIORITY_LOCKED**
