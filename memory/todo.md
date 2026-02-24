# Project Todo

使用規則：
- 開始任務前標記 `[~]`，完成後標記 `[x]`
- 每個任務附上背景說明與完成標準
- 完成後在底部 **Review** 區段記錄結果

---

## 進行中 (In Progress)

### [~] Gemini 2-bet 聯合驗證 (branch: verify-gemini-2bet)
- 背景：Gemini 提出的 2注威力彩策略需 Claude 獨立驗證
- 狀態：Phase 13-17 已驗證（commit d3df866）
- 待完成：
  - [ ] 確認所有 Phase 結果符合 1500期三窗口標準
  - [ ] 將通過驗證的策略記錄至 `lottery_api/CLAUDE.md`
  - [ ] 將失敗策略記錄至 `rejected/`
  - [ ] Merge 或關閉此分支

---

## 待辦 Backlog

### 策略研究

- [ ] **每日539策略驗證**
  - 目前 MEMORY.md 無今彩539已驗證策略記錄
  - 需建立 baseline 並驗證至少一個 Edge > 0 的方法

- [ ] **大樂透 RSM 持續監控**
  - `data/rolling_monitor_BIG_LOTTO.json` 需定期更新
  - 監控 Triple Strike + TS3+Markov(w=30) 趨勢是否仍 STABLE

- [ ] **威力彩 RSM 持續監控**
  - `data/rolling_monitor_POWER_LOTTO.json` 需定期更新
  - 監控 PP3 3注（近30期爆發 +22.16%）是否持續或回歸

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

### 2026-02-24 — strategies/ 目錄建立
- 結果：8個採納策略（大樂透5、威力彩3）建立完整生命週期文件
- 文件：strategy.yaml / backtest_report.md / stat_test.txt / version_tag.txt
- 待補：sim_result.json / performance_log.json（Monitor 階段尚未建立）
