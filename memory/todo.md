# Project Todo

使用規則：
- 開始任務前標記 `[~]`，完成後標記 `[x]`
- 每個任務附上背景說明與完成標準
- 完成後在底部 **Review** 區段記錄結果

---

## 進行中 (In Progress)

_（目前無進行中任務）_

### P246F BIG_LOTTO 研究呼叫端 canonical 化掃描 ✅ 2026-06-05 完成
- [x] 確認 PR #320 (P246E) CI PASS，合併至 main
- [x] 掃描 get_all_draws/get_canonical_draws 全呼叫端並分類
- [x] 更新 tools/rsm_bootstrap.py:118 → get_canonical_draws()（P246F）
- [x] 更新 lottery_api/engine/core_satellite.py:373 → get_canonical_draws()（P246F）
- [x] 確認 drift_detector、advanced_learning、backtest_framework 延後至 P246G
- [x] 測試 199/199 PASS；產出 P246F 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L111）
- 完成標準：3 個確認研究呼叫端已 canonical 化；加碼記錄 raw 存取保留；無 DB 寫入

### P246E BIG_LOTTO canonical draw helper 實作 ✅ 2026-06-05 完成
- [x] 確認 PR #319 (P246D) CI PASS，合併至 main
- [x] 在 database.py 新增 get_canonical_draws()：三層過濾（SQL×2 + Python×1）
- [x] canonical=2113，raw=22238，ADD_ON 19,100 筆保留在 DB
- [x] 更新 quick_predict.py load_history() 使用 get_canonical_draws()
- [x] 非 BIG_LOTTO 類型通過 (POWER_LOTTO、DAILY_539 count 不變)
- [x] 測試 165/165 PASS；產出 P246E 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L110）
- 完成標準：isolation checks all pass；無 DB 寫入；加碼記錄 raw 存取保留

### P246D BIG_LOTTO 加碼記錄隔離設計 ✅ 2026-06-05 完成
- [x] 確認 PR #318 (P246C) CI PASS，合併至 main
- [x] 讀取 DB read-only：確認無 canonical view，共 22,238 筆 BIG_LOTTO
- [x] 評估 5 個隔離選項（OPT-A/B/C/D/E）；拒絕直接刪除（OPT-E）
- [x] 推薦四階段隔離路徑：Phase 1 code helper（無 DB 寫入）→ Phase 2 SQL view → Phase 3 annotation table → Phase 4 re-validate
- [x] 確認 Phase 1 立即可實作：新增 get_canonical_draws()，filter draw NOT LIKE '%-%'
- [x] 確認 quick_predict.py:169 是 Phase 1 首要更新目標
- [x] 產出 P246D 文物（JSON+MD）+ 測試 45/45 PASS（全 133 PASS）
- [x] 更新 memory/lessons.md（L109）
- 完成標準：隔離設計已明確；保留加碼記錄；P247 apply 仍需 Type D 授權

### P246C BIG_LOTTO 加碼記錄影響範圍審計 ✅ 2026-06-05 完成
- [x] 確認 PR #317 (P246B) CI PASS，合併至 main
- [x] 掃描全 repo：database.py get_all_draws/get_draws 無 canonical filter（DIRECTLY_AFFECTED）
- [x] 確認 P219 已正確過濾（draw NOT LIKE '%-%'）→ NOT_AFFECTED
- [x] 確認 P238B NIST 文物以 sample_size=22238 建立（含加碼記錄）→ DIRECTLY_AFFECTED
- [x] 發現 2 個測試硬編碼 22238（P238B test + P243A fixture）→ 隔離後需更新
- [x] 產出 P246C 文物（JSON+MD）+ 測試 41/41 PASS
- [x] 更新 memory/todo.md + lessons.md
- 完成標準：影響範圍已記錄；無 DB 寫入；P247 apply 仍需 Type D 授權

### P246B BIG_LOTTO 分類修正 ✅ 2026-06-05 完成
- [x] 修正 P246 SIM_HYPHEN 標籤 → ADD_ON_PRIZE_EXCLUDED
- [x] 確認 19,100 筆連字號列為加碼/特別獎記錄，非偽造資料
- [x] 產出 P246B 分類修正文物（JSON+MD）
- [x] 產出 P247 修正版排除計畫文物（JSON+MD，計畫 only，無 DB 寫入）
- [x] 測試 47/47 PASS
- [x] 更新 memory/lessons.md（L107）
- 完成標準：修正文物在 main 上；BIG_LOTTO 研究 gate 維持封鎖；不含 DB 寫入

### P219 外部10法診斷掃描 ✅ 2026-06-05 完成（predictive-NULL）
- [x] 背景：用戶（cost-no-object）授權跑全部10類外部方法，目標提高預測成功率
- [x] Pre-register（P221F gate）：`outputs/research/p219_..._plan_20260605.md`
- [x] 鎖定 clean distinct-real-draw 宇宙（BIG_LOTTO 排除 19,100 模擬列）
- [x] 實作 read-only 引擎（pure stdlib, MC/permutation nulls）：`analysis/p219_external_method_diagnostic_sweep.py`
- [x] 跑 10 families × 5 games = 44 tests，Bonferroni+BH 校正
- [x] 測試 10/10 PASS（假陽性控制 + 注入偏差功率 + 校正單調性 + 可重現 + 模擬列排除）
- [x] 裁決：predictive 家族全 NULL；唯一 corrected-sig 全為 BIG_LOTTO 資料污染 artifact
- [x] 完成標準：predictive-NULL 證明 + 資料污染根因（≥3 來源）+ feature-bottleneck report

---

## 待辦 Backlog

### 策略研究

- [x] **每日539策略驗證** ✅ 2026-02-25 完成
  - 首個通過三窗口驗證策略: `5bet_fourier4_cold` (PROVISIONAL)
  - 1500p Edge +1.35% (z=2.4), Permutation p=0.030 (SIGNAL_DETECTED)
  - 腳本: `tools/predict_539_5bet_f4cold.py`
  - **⚠️ 下次驗證: 5992期 (再200期後)**

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

### 2026-06-05 — P219 外部10法診斷掃描（predictive-NULL + 資料污染發現）
- 結果：10 families × 5 games = 44 multiplicity-corrected tests。**forward-predictive 家族（M5/M8/M9）在所有遊戲全 NULL**（最佳 +0.49pp p=0.226 在污染資料上）。MI≈0，無 exploitable edge。再確認 L82/L91/P178A/P236A。
- 唯一 corrected-significant：全在 BIG_LOTTO（M1/M2/M3/M4/M6）+ 弱 539:M3（BH-only Bonferroni-FAIL）。
- 根因（裁決）：**非彩票偏差，而是 BIG_LOTTO `draws` 表資料污染** — 22,238 列僅 ~2,113 為真 6/49（19,100 模擬 + 375 date-format 異種 + 650 小池異種）。drift/changepoint 偵測到的是「資料管線斷點」，anomaly≠predictor。
- 問題：BIG_LOTTO raw `draws` 會污染任何分析；統計單位必須 = distinct real 6/49。
- 影響：(1) 用戶目標「提高預測成功率」= 無外部方法可達（fair-random）；(2) **flag 資料完整性任務**（read-only audit + quarantine plan，需另開 Type B/D，不在本任務改 DB）；(3) 教訓 L_P219_A/B/C 入 lessons.md。
- 產出：`analysis/p219_external_method_diagnostic_sweep.py`, `outputs/research/p219_..._{plan_,}20260605.{md,json}`, `tests/test_p219_..._sweep.py`（10/10 PASS）。

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

### 2026-06-05 — P245B 偏差閘門層設計（corrected, builds on P237C/P238B/P219）
- 結果：P245B 確立 sequential e-value + BOCD + 多重校正 + 資料完整性 閘門設計。P245A 缺席確認，不依賴。當前閘門：DAILY_539/POWER/3_STAR/4_STAR = YELLOW；BIG_LOTTO = GATE_RED_DATA_CONTAMINATION。GATE_OPEN 8 條件無一達成。24/24 tests PASS。
- 影響：偏差研究重啟有清晰、可審計的門檻；anomaly≠prediction 強制語言；BIG_LOTTO 資料清理仍需另開 Type D 授權。
- 產出：outputs/research/p245b_bias_gate_layer_20260605.{md,json}, tests/test_p245b_bias_gate_layer.py。

### 2026-06-05 — P246 BIG_LOTTO Data-Integrity Audit (GATE_RED confirmed, quarantine plan produced)
- 結果：22,238 rows = 2,113 canonical + 20,125 contaminated (90.5%). 三個污染家族：SIM_HYPHEN 19,100 / DATE_FORMAT_ALIEN 375 / SMALL_POOL_ALIEN 650（主要 P219 信號來源）。全部 P219 BIG_LOTTO corrected-significant signals 已解釋為資料污染。23/23 tests PASS。
- 影響：GATE_RED_DATA_CONTAMINATION 維持不變。Type D 授權 + 執行 quarantine + re-audit 方可升門。不授權任何策略/預測/生產推薦。
- 產出：analysis/p246_…py, outputs/research/p246_…20260605.{md,json}, tests/test_p246_….py。
