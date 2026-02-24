# Research Plan — {策略名稱}

> 複製此模板，重命名為 `research_plan_{strategy_name}.md`，置於研究分支根目錄。
> 策略研究開始前必須完成此文件。

---

## 研究動機

- **問題**：（說明目前策略的不足，或要填補的空缺）
- **假設**：（預期這個方法能改善什麼，為什麼）
- **來源**：（靈感來源：期檢討 / 文獻 / Gemini建議 / 自動發現）

---

## 彩種與注數

- **彩種**: BIG_LOTTO / POWER_LOTTO / DAILY_539
- **注數**: N 注
- **Baseline**: `1 - (1 - P_single)^N`
  - BIG_LOTTO P_single = 1.86%
  - POWER_LOTTO P_single = 3.87%

---

## 方法設計

### 注1
- 方法：
- 邏輯：
- 參數：

### 注2（如有）
- 方法：
- 邏輯：
- 參數：

### 正交約束（如有）
- 規則：

---

## 驗證計劃

| 步驟 | 內容 | 通過標準 |
|------|------|----------|
| 1. Simulation | 初步跑150期 | Edge > 0 |
| 2. Backtest | 三窗口 150/500/1500 | 三窗口全正 |
| 3. Stat Test | Z-test / McNemar | p < 0.05 |
| 4. P3 Test | 200 shuffles × 1500期 | p < 0.05 |
| 5. Sharpe | 計算 Sharpe Ratio | Sharpe > 0 |

- **Seed**: 42（固定）
- **資料範圍**: 全期（嚴格時序隔離）

---

## 風險評估

- **主要風險**：（SHORT_MOMENTUM / LATE_BLOOMER / STATISTICAL_ILLUSION 等）
- **護衛條件**：（哪些情況下需要中止研究）
- **與現有策略衝突**：（是否會損害注2-3品質，見 L13）

---

## 預期產出

- [ ] `sim_result.json`
- [ ] `backtest_report.md`
- [ ] `stat_test.txt`
- [ ] `strategy.yaml`（採納後）
- [ ] `rejected/{name}.json`（拒絕時）
