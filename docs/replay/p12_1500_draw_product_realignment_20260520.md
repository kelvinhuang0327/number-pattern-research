# P12 1500-Draw Product Realignment
**Date:** 2026-05-20  
**Classification:** P12_1500_DRAW_BACKFILL_PLAN_READY  
**Branch:** feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Production rows at entry:** 460 (unchanged)

---

## 1. 本輪重新校準的原因

P11 完成後，系統已具備：
- 460 production replay rows（6 個 ONLINE strategies × ~50 期）
- 351/351 tests PASS
- drift guard PASS
- PR draft 已準備

然而 CEO 重新校準確認：**460 rows 和 P7 28-row apply 候選，都不是最終產品目標**。  
本輪（P12）目的是在 merge / apply 前，先確立正確的產品目標規模，以及達到目標所需的架構計畫。

---

## 2. 為什麼 28 rows apply 不等於產品完成

P7 控制性 apply 候選是：
- 從現有 460 rows 中篩選出 ONLINE lifecycle 的 28 rows
- Apply 後 production rows: 460 → 488
- 488 rows 仍只覆蓋 ~50 期 × 6 strategies

**28 rows apply 問題：**

| 面向 | 現狀 | 產品目標 |
|------|------|---------|
| 期數覆蓋 | ~50 期 | 1500 期 |
| 策略數 | 6 | 8 (ONLINE) |
| 總 rows | 460 → 488 | 12,000 (8 ONLINE × 1500) |
| 歷史完整性 | 片段 | 系統性回放 |

把 28-row apply 描述為「產品完成」是根本性錯誤校準。

---

## 3. CEO 真正產品目標

歷史回放頁面要能針對所有可執行策略，至少最近 1500 期，顯示每一期的完整比對記錄：

```
strategy_id | strategy_name | draw_number | draw_date
predicted_numbers | actual_numbers | hit_numbers
hit_count | special_hit | lifecycle_status | truth_level | source_trace
```

**目標：所有策略的預測與實際獎號比對清單，1500 期級別。**

---

## 4. 1500 期 Replay Target

| 指標 | 數值 |
|------|------|
| 目標期數 | 1,500 期 |
| 可執行策略 (ONLINE) | 8 |
| 最大目標 rows (8 ONLINE × 1500) | 12,000 |
| 理論 rows (18 registry × 1500) | 27,000 |
| 目前 rows | 460 |
| 缺口 (vs 8 ONLINE) | 11,540 |
| 缺口 (vs 18 registry) | 26,540 |

---

## 5. 18 Strategies × 1500 Draws 資料量估算

```
18 (registry 全策略) × 1500 draws = 27,000 rows   [理論上限]
 8 (ONLINE 可執行)   × 1500 draws = 12,000 rows   [可達目標]
 4 (REJECTED)        × 1500 draws = 0 rows        [禁止執行]
 5 (RETIRED)         × 1500 draws = 0 rows        [需獨立授權]
 1 (OBSERVATION)     × 1500 draws = 0 rows        [觀察期，不可用]
```

**Draw data 充分性：**

| Lottery Type | 可用期數 | 是否足夠 1500 期 |
|-------------|---------|----------------|
| BIG_LOTTO | 2,135 | ✓ |
| DAILY_539 | 5,865 | ✓ |
| POWER_LOTTO | 1,912 | ✓ |

三種彩票類型都有充分的歷史資料支援 1500 期回放（含 100 期 min_history buffer）。

---

## 6. 59 Catalog Universe 的限制

| 分類 | 數量 | 說明 |
|------|------|------|
| Registry 已登錄 | 18 | 完整生命週期追蹤 |
| Artifact-only | 41 | 僅有程式碼/artifact 掃描記錄，未登錄 registry |
| **總計** | **59** | |

**41 ARTIFACT_CANDIDATE 絕對不可計算為 executable。**  
它們沒有策略函式、沒有 registry adapter、無法生成 predicted_numbers。  
任何把 artifact-only 當作 executable 的設計都必須立即拒絕。

---

## 7. 目前 460 Rows 的缺口

**現狀 by strategy：**

| strategy_id | lifecycle | rows | 覆蓋期數 | 距 1500 期缺口 |
|-------------|-----------|------|---------|--------------|
| biglotto_deviation_2bet | ONLINE | 70 | ~50 | 1,430 |
| biglotto_triple_strike | ONLINE | 70 | ~50 | 1,430 |
| daily539_f4cold | ONLINE | 90* | ~50 | 1,450 |
| daily539_markov_cold | ONLINE | 90* | ~50 | 1,450 |
| power_orthogonal_5bet | ONLINE | 70 | ~50 | 1,430 |
| power_precision_3bet | ONLINE | 70 | ~50 | 1,430 |
| fourier_rhythm_3bet | ONLINE | 0 | 0 | 1,500 |
| ts3_regime_3bet | ONLINE | 0 | 0 | 1,500 |

*含 REPLAY_ERROR rows（daily539: 20 × 2 strategy）

**覆蓋期範圍（目前）：**
- BIG_LOTTO: 99000056–99000105（50 期）
- DAILY_539: 99000212–99000261（50 期）
- POWER_LOTTO: 99000055–99000104（50 期）

---

## 8. 哪些策略可能可重跑（Executable）

以下 8 個 ONLINE 策略，配備 replay adapter，min_history=100，可重跑：

| strategy_id | lottery_type | min_history | 備註 |
|-------------|-------------|-------------|------|
| power_precision_3bet | POWER_LOTTO | 100 | 有現有 rows，proven |
| power_orthogonal_5bet | POWER_LOTTO | 100 | 有現有 rows，proven |
| fourier_rhythm_3bet | POWER_LOTTO | 100 | 0 rows，RECONSTRUCTIBLE |
| biglotto_triple_strike | BIG_LOTTO | 100 | 有現有 rows，proven |
| biglotto_deviation_2bet | BIG_LOTTO | 100 | 有現有 rows，proven |
| ts3_regime_3bet | BIG_LOTTO | 100 | 0 rows，RECONSTRUCTIBLE |
| daily539_f4cold | DAILY_539 | 100 | 有現有 rows，proven |
| daily539_markov_cold | DAILY_539 | 100 | 有現有 rows，proven |

---

## 9. 哪些策略不可重跑（Blocked）

| strategy_id | lifecycle | 封鎖原因 |
|-------------|-----------|---------|
| biglotto_ts3_acb_4bet | REJECTED | 治理審查拒絕 |
| biglotto_ts3_markov_freq_5bet | REJECTED | 治理審查拒絕 |
| power_shlc_midfreq | REJECTED | 治理審查拒絕 |
| p1_deviation_2bet_539 | REJECTED | 治理審查拒絕 |
| acb_1bet | RETIRED | 需獨立人工審查授權 |
| acb_markov_midfreq | RETIRED | 需獨立人工審查授權 |
| acb_markov_midfreq_3bet | RETIRED | 需獨立人工審查授權 |
| midfreq_acb_2bet | RETIRED | 需獨立人工審查授權 |
| midfreq_fourier_2bet | RETIRED | 需獨立人工審查授權 |
| h6_gate_mk20_ew85 | OBSERVATION | 觀察期中，未授權量產 |

---

## 10. 新 Roadmap 建議

| Phase | 目標 | 說明 |
|-------|------|------|
| **P12** | 1500-draw gap analysis & architecture | ✅ 本輪完成 |
| **P13** | Backfill engine skeleton, dry-run only | 建立執行框架，無 DB 寫入 |
| **P14** | 2 ONLINE strategies × 1500 draws dry-run | daily539_f4cold + power_precision_3bet |
| **P15** | Apply gate for Phase 1 backfill | CEO 明確授權後才 apply |
| **P16** | 擴展到全 8 ONLINE strategies | Phase 2 dry-run → apply |
| **P17** | API pagination / query optimization | 12,000 rows 的查詢效能 |
| **P18** | UI history list integration | 頁面整合 1500 期顯示 |
| **P19** | RETIRED / OBSERVATION / REJECTED governance | 獨立授權流程 |
| **P20** | Production launch checklist | 正式上線驗收 |

---

## 禁止事項（本 Roadmap 全程適用）

- ❌ 不得 fabricate predicted_numbers
- ❌ 不得把 artifact-only 算作 executable
- ❌ 不得把 NO_DATA 算作 success
- ❌ REJECTED/RETIRED/OBSERVATION 策略不得進入 backfill pipeline（無授權）
- ❌ 不得在未獲 CEO 明確授權前 apply 任何新 rows
- ❌ 不得把「28 rows apply」描述為「產品完成」

---

*Generated by P12 realignment analysis. Production rows remain 460 (unchanged).*
