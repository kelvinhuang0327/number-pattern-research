# Strategy Catalog 全量盤點
**生成時間:** 2026-05-12  
**負責人:** Strategy Historical Replay Product Coverage Agent  
**任務:** Stage A — 全量盤點（read-only）  
**來源:** main branch (7d80a03) + lottery_api/data/lottery_v2.db + rejected/ folder  

---

## 一、Canonical Lifecycle Registry（16 條）

> 來源：`lottery_api/models/replay_strategy_registry.py` (main branch)  
> 含 6 個 ONLINE adapter + 10 個 `_LifecycleStub`（非可執行，僅供生命週期追蹤）

| strategy_id | strategy_name | lifecycle | lottery_type | source | has_production_replay | production_row_count | has_fixture_rows | fixture_row_count | eligible_for_display | eligible_for_generation | provenance_note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| power_precision_3bet | 威力彩 Precision 3注 | ONLINE | POWER_LOTTO | adapter | ✅ | 70 | ✅ | synthetic | ✅ | ✅ | run #2,#6 DONE |
| power_orthogonal_5bet | 威力彩 Orthogonal 5注 | ONLINE | POWER_LOTTO | adapter | ✅ | 70 | ✅ | synthetic | ✅ | ✅ | run #2,#6 DONE |
| biglotto_triple_strike | 大樂透 Triple Strike | BIG_LOTTO | ONLINE | adapter | ✅ | 70 | ✅ | synthetic | ✅ | ✅ | run #1,#5 DONE |
| biglotto_deviation_2bet | 大樂透 Deviation 2注 | ONLINE | BIG_LOTTO | adapter | ✅ | 70 | ✅ | synthetic | ✅ | ✅ | run #1,#5 DONE |
| daily539_f4cold | 今彩539 F4 Cold | ONLINE | DAILY_539 | adapter | ✅ | 90 | ✅ | synthetic | ✅ | ✅ | run #3 FAILED_LEGACY (20 errors), run #4,#7 DONE |
| daily539_markov_cold | 今彩539 Markov Cold | ONLINE | DAILY_539 | adapter | ✅ | 90 | ✅ | synthetic | ✅ | ✅ | run #3 FAILED_LEGACY (20 errors), run #4,#7 DONE |
| biglotto_ts3_acb_4bet | 大樂透 TS3+ACB 4注 | REJECTED | BIG_LOTTO | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | rejected/ folder |
| biglotto_ts3_markov_freq_5bet | 大樂透 TS3+Markov 頻率正交 5注 | REJECTED | BIG_LOTTO | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | rejected/ folder |
| power_shlc_midfreq | 威力彩 SHLC 中頻指標 | REJECTED | POWER_LOTTO | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | rejected/ folder |
| p1_deviation_2bet_539 | 今彩539 P1鄰號+偏差互補 2注 | REJECTED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | rejected/ folder |
| acb_1bet | 今彩539 ACB 1注 | RETIRED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | 已退役；曾為主策略之一 |
| acb_markov_midfreq | 今彩539 ACB+Markov 中頻 | RETIRED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | 已退役 |
| acb_markov_midfreq_3bet | 今彩539 ACB+Markov 中頻 3注 | RETIRED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | 已退役 |
| midfreq_acb_2bet | 今彩539 中頻 ACB 2注 | RETIRED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | 已退役；曾為主策略之一 |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | RETIRED | DAILY_539 | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | 已退役 |
| h6_gate_mk20_ew85 | 威力彩 H6 Gate mk20 ew85 | OBSERVATION | POWER_LOTTO | lifecycle_stub | ❌ | 0 | ✅ | 1 synthetic | ✅ | ❌ | H6 live production strategy, shadow eval |

---

## 二、Canonical Registry 統計摘要

| lifecycle | count | production_rows | catalog_w_0_rows |
|---|---|---|---|
| ONLINE | 6 | 460 | 0 |
| REJECTED | 4 | 0 | 4 |
| RETIRED | 5 | 0 | 5 |
| OBSERVATION | 1 | 0 | 1 |
| OFFLINE | 0 | 0 | 0 |
| **TOTAL** | **16** | **460** | **10** |

---

## 三、Extended Catalog（rejected/ folder）

> 來源：`rejected/` 目錄（73 個 JSON 文件）+ `lottery_api/data/rejected/`（4 個 JSON）

以下為不在 canonical 16-entry registry 中、但明確在系統中開發並被拒絕的策略。  
這些策略**未在 `replay_strategy_registry.py` 中登錄**，是擴展 catalog 的補充資料。

| 類型 | 數量 | 說明 |
|---|---|---|
| rejected/ 目錄 | 73 | 所有被 governance 正式拒絕的策略 |
| lottery_api/data/rejected/ | 4 | API 層 rejected (sgp_v3/v9/v10/v11) |
| 重複 (canonical 已含) | 估計 ~4 | canonical REJECTED stubs 來自此目錄 |
| Extended REJECTED (net) | ~73 | 待與 canonical 對照確認 |

**注意**: extended catalog 策略未在 registry 中登錄，因此：
- `eligible_for_display` = 暫定 ❌（無 registry 支援）
- `eligible_for_generation` = ❌

---

## 四、Memory 中的策略名稱（非正式）

> 來源：`memory/MEMORY.md` + wiki/games/*.md  

以下策略名稱出現在 wiki/memory 中，屬於系統歷史上使用過的策略，但生命週期分類需通過 registry 驗證：

| strategy_id（近似） | 出現位置 | lifecycle_status | 備註 |
|---|---|---|---|
| regime_2bet | wiki/games/big_lotto.md | UNKNOWN | 參考策略，僅監控用 |
| ts3_regime_3bet | wiki/games/big_lotto.md | UNKNOWN | 參考策略 |
| p1_dev_sum5bet | wiki/games/big_lotto.md | UNKNOWN | 主生產策略之一（監控中）|
| acb_1bet | wiki/games/daily_539.md | RETIRED | 已在 canonical registry |
| midfreq_acb_2bet | wiki/games/daily_539.md | RETIRED | 已在 canonical registry |
| acb_markov_midfreq_3bet | wiki/games/daily_539.md | RETIRED | 已在 canonical registry |
| microfish_midfreq_2bet | wiki/games/daily_539.md | UNKNOWN | McNemar REJECT，未進 RSM |
| midfreq_fourier_2bet | wiki/games/power_lotto.md | RETIRED | 已在 canonical registry |
| h6_gate_mk20_ew85 | wiki/games/daily_539.md | OBSERVATION | 已在 canonical registry |

---

## 五、Database 盤點（Production DB）

> 來源：`lottery_api/data/lottery_v2.db`（production）  
> **注意：`data/lottery_v2.db` 是 schema-only，replay 表格為空**

### strategy_prediction_replays 表格
| strategy_id | strategy_name | lottery_type | total_rows | error_rows | earliest_date | latest_date |
|---|---|---|---|---|---|---|
| biglotto_deviation_2bet | 大樂透 Deviation 2注 | BIG_LOTTO | 70 | 0 | 2010/07/13 | 2010/12/31 |
| biglotto_triple_strike | 大樂透 Triple Strike | BIG_LOTTO | 70 | 0 | 2010/07/13 | 2010/12/31 |
| daily539_f4cold | 今彩539 F4 Cold | DAILY_539 | 90 | 20 | 2010/10/25 | 2010/12/31 |
| daily539_markov_cold | 今彩539 Markov Cold | DAILY_539 | 90 | 20 | 2010/10/25 | 2010/12/31 |
| power_orthogonal_5bet | 威力彩 Orthogonal 5注 | POWER_LOTTO | 70 | 0 | 2010/07/12 | 2010/12/30 |
| power_precision_3bet | 威力彩 Precision 3注 | POWER_LOTTO | 70 | 0 | 2010/07/12 | 2010/12/30 |
| **TOTAL** | | | **460** | **40** | | |

### strategy_replay_runs 表格
| run_id | lottery_type | status | notes |
|---|---|---|---|
| 1 | BIG_LOTTO | DONE | window [2110..2129] |
| 2 | POWER_LOTTO | DONE | window [1886..1905] |
| 3 | DAILY_539 | FAILED_LEGACY | adapter bug; 40 REPLAY_ERROR rows retained |
| 4 | DAILY_539 | DONE | window [5829..5848] |
| 5 | BIG_LOTTO | DONE | window [2080..2129] |
| 6 | POWER_LOTTO | DONE | window [1856..1905] |
| 7 | DAILY_539 | DONE | window [5799..5848] |

---

## 六、Gap 分析

### 6.1 在 canonical catalog 但無 production rows（10 個）

| strategy_id | lifecycle | root_cause |
|---|---|---|
| biglotto_ts3_acb_4bet | REJECTED | 未執行 replay；只有 lifecycle stub |
| biglotto_ts3_markov_freq_5bet | REJECTED | 未執行 replay；只有 lifecycle stub |
| power_shlc_midfreq | REJECTED | 未執行 replay；只有 lifecycle stub |
| p1_deviation_2bet_539 | REJECTED | 未執行 replay；只有 lifecycle stub |
| acb_1bet | RETIRED | 未執行 replay；只有 lifecycle stub |
| acb_markov_midfreq | RETIRED | 未執行 replay；只有 lifecycle stub |
| acb_markov_midfreq_3bet | RETIRED | 未執行 replay；只有 lifecycle stub |
| midfreq_acb_2bet | RETIRED | 未執行 replay；只有 lifecycle stub |
| midfreq_fourier_2bet | RETIRED | 未執行 replay；只有 lifecycle stub |
| h6_gate_mk20_ew85 | OBSERVATION | 未執行 replay；只有 lifecycle stub |

**結論**: 所有 10 個非 ONLINE 策略均無 production replay rows。  
**原因**: replay generation 只針對 ONLINE/ACTIVE 策略（_GENERATION_STATUSES）。  
**建議**: Production Backfill Decision Memo（需 CEO 主持）決定是否補充。

### 6.2 在 memory/wiki 中但 canonical catalog 缺失

| strategy_id | 出現位置 | 現況 | 建議 |
|---|---|---|---|
| regime_2bet | wiki/games/big_lotto.md | UNKNOWN（監控參考策略）| 需 governance 決定是否加入 registry |
| ts3_regime_3bet | wiki/games/big_lotto.md | UNKNOWN（監控參考策略）| 同上 |
| p1_dev_sum5bet | wiki/games/big_lotto.md | UNKNOWN（生產策略）| 需調查是否應加入 ONLINE stub |
| microfish_midfreq_2bet | wiki/games/daily_539.md | UNKNOWN（McNemar REJECT）| 考慮加入 REJECTED stub |

### 6.3 Lifecycle 不一致

| strategy_id | registry_status | wiki/memory_mention | 不一致點 |
|---|---|---|---|
| h6_gate_mk20_ew85 | OBSERVATION | 在 wiki 中為 DAILY_539 主力策略 | registry 中的 lottery_type 為 POWER_LOTTO，與 wiki 記載有差異，需核實 |

### 6.4 Extended catalog vs. Registry 差距

- **rejected/ folder**: 73 個策略文件
- **canonical registry REJECTED stubs**: 4 個
- **差距**: 69 個策略在 rejected/ folder 但未加入 canonical registry
- **建議**: 這些 69 個策略是否需要加入 registry stubs 取決於 CEO 對 "operator visibility" 的定義範疇

---

## 七、OFFLINE 狀態

- **canonical registry OFFLINE**: 0 個
- **production replay OFFLINE rows**: 0 個
- **fixture OFFLINE rows**: 0 個
- **結論**: OFFLINE 是預留 lifecycle，目前無任何策略處於此狀態

---

## 八、Summary Table（人類可讀）

| 統計項 | 數值 |
|---|---|
| Canonical lifecycle registry 總數 | **16** |
| ONLINE | 6 |
| REJECTED（canonical）| 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |
| OFFLINE | 0 |
| Production replay rows（總計）| 460 |
| 有 production rows 的策略 | 6（均為 ONLINE）|
| 無 production rows 的 catalog 策略 | 10 |
| Extended catalog（rejected/ folder）| 73 |
| Memory-only UNKNOWN 策略 | ~5 |
| DB clean（無異常寫入）| ✅ |
