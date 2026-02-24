# Project Todo

使用規則：
- 開始任務前標記 `[~]`，完成後標記 `[x]`
- 每個任務附上背景說明與完成標準
- 完成後在底部 **Review** 區段記錄結果

---

## 進行中 (In Progress)

_（目前無進行中任務）_

---

## 待辦 Backlog

### 策略研究

- [ ] **每日539策略驗證**
  - 目前 MEMORY.md 無今彩539已驗證策略記錄
  - 需建立 baseline 並驗證至少一個 Edge > 0 的方法

- [ ] **大樂透 RSM 持續監控**
  - `data/rolling_monitor_BIG_LOTTO.json` 需定期更新（下次建議每100期）
  - 監控重點：ts3_markov_freq_5bet_w30 的 100p Edge(+0.04%) 是否回升

- [ ] **威力彩 RSM 持續監控**
  - `data/rolling_monitor_POWER_LOTTO.json` 需定期更新
  - 監控重點：fourier_rhythm_3bet ACCELERATING(z=+2.18) 是否持續或回歸；orthogonal_5bet 30p(-1.24%) 是否改善

- [ ] **大樂透 6注策略研究**
  - 目前最佳：5注 Edge +1.97%
  - 研究第6注是否可用「殘餘號碼按Zone平衡」填補

- [ ] **威力彩 4注策略**
  - 目前 3注 PP3 Edge +2.30%，5注正交 +3.53%
  - 4注是否存在有效組合？

### 系統建設

- [x] **建立策略生命週期文件夾**
  - 依 CLAUDE.md 規範建立 `strategies/` 目錄
  - 每個採納策略需有 `strategy.yaml` + `backtest_report.md`

- [ ] **rejected/ 重測條件觸發機制**
  - 定期（每100期新資料）掃描 rejected/*.json 的 `retest_conditions`
  - 確認是否有策略達到重測門檻

- [ ] **自動 Permutation Test 整合**
  - 目前 P3 shuffle test 是手動執行
  - 考慮整合至回測腳本，新策略自動跑200次shuffle

- [ ] **Sharpe Ratio 計算整合**
  - CLAUDE.md 要求 Sharpe Ratio > 0 才標記為有效
  - 目前回測腳本尚未輸出 Sharpe Ratio

### 文件補完

- [ ] **更新 lottery_api/CLAUDE.md 策略評分**
  - 已有 Edge 數據，但缺少 Stability / Significance / Complexity 欄位
  - 補充 Score 公式計算結果

- [x] **建立 strategies/ 目錄**
  - 為現有採納策略補充 strategy.yaml（Idea 階段文件）
  - **補齊 sim_result.json + performance_log.json (2026-02-24)**
    - 8策略 × 2文件 = 16個文件全部完成
  - **RSM 掃描補齊三個 PENDING 策略 (2026-02-24)**
    - BL 4注: STABLE z=+0.06，三窗口全正(+2.75/+1.75/+2.42%)
    - BL 5注: STABLE z=-0.22，(+1.04/+0.04/+2.37%)
    - PL 5注: STABLE z=-0.60，(-1.24/+3.09/+3.42%)

- [x] **補齊 2注策略 backtest_report.md**
  - big_lotto/2bet_fourier_rhythm, 2bet_deviation_complement
  - power_lotto/2bet_fourier_rhythm

- [x] **建立 research_plan_template.md**
  - 路徑：`memory/research_plan_template.md`
  - 新研究開始前複製使用

---

## 已完成 (Done)

### Workflow 基礎建設 (2026-02-24)
- [x] 建立根目錄 `CLAUDE.md`（策略生命週期、評分公式、驗證標準）
- [x] 建立 `rejected/` 目錄 + 12個已拒絕策略歸檔
- [x] 建立 `memory/lessons.md`（22條教訓）
- [x] 建立 `memory/todo.md`（本檔）
- [x] 建立 `strategies/` 目錄（8個採納策略完整生命週期文件）

### 1500期全面驗證 (2026-02-10)
- [x] 大樂透 8策略 × 3窗口驗證完成
- [x] 採納：Fourier Rhythm 2注、Triple Strike v2 3注、TS3+Markov(w=30) 4注、5注正交
- [x] 拒絕：Cluster Pivot、Cold Complement、Markov單注、Fourier30+Markov30

### P3 Permutation Test (2026-02-18)
- [x] 大樂透 5注 BL TS3+M4+FO：p=0.030, Cohen's d=2.13 ✅ SIGNAL DETECTED
- [x] 威力彩 PP3 3注：p=0.015, Cohen's d=2.18 ✅ SIGNAL DETECTED

### Gemini 2-bet 聯合驗證 (2026-02-24 結案)
- [x] Phase 13-17 驗證完成（commit d3df866）
- [x] Merge verify-gemini-2bet → main（commit ce7c10f）
- [x] 刪除分支 verify-gemini-2bet

### Gemini 協作驗證架構 (2026-01-26)
- [x] 建立 `.claude/gemini_collaboration_protocol.md`
- [x] 確立 Gemini 策略必須 Claude 獨立驗證規則

---

## Review 區段

> 每個任務完成後在此記錄：結果摘要、遇到的問題、後續影響

### 2026-02-24 — Workflow 基礎建設
- 結果：CLAUDE.md + rejected/ + memory/ + strategies/ 四件套建立完成
- 問題：`tasks/` 路徑不符合專案結構，已改為 `memory/`
- 影響：後續所有教訓追蹤統一寫入 `memory/lessons.md`

### 2026-02-24 — strategies/ 生命週期文件全部補完
- 結果：8策略 × 6文件 = 48個文件全部就位（含 sim_result.json + performance_log.json）
- RSM 掃描（2026-02-24，BIG_LOTTO 2105期 / POWER_LOTTO 1887期）：
  - BL 4注 ts3_markov_4bet_w30: **STABLE** 三窗口全正 (+2.75/+1.75/+2.42%) z=+0.06
  - BL 5注 ts3_markov_freq_5bet_w30: **STABLE** (+1.04/+0.04/+2.37%) z=-0.22，100p近中性需持續觀察
  - PL 5注 orthogonal_5bet: **STABLE** (-1.24/+3.09/+3.42%) z=-0.60，30p短暫負Edge屬正常波動
- 同步更新：BASELINES 支援4/5注、rsm_bootstrap.py 加入三個新策略
