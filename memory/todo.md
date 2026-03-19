# Project Todo

使用規則：
- 開始任務前標記 `[~]`，完成後標記 `[x]`
- 每個任務附上背景說明與完成標準
- 完成後在底部 **Review** 區段記錄結果

---

## 進行中 (In Progress)

- [x] **Frontend 全階段執行 + 熱門UI風格改版** (2026-03-13)
  - 目標: 在不改動後端與核心業務流程下，完成控制器拆分與前端視覺升級
  - 範圍: `index.html`, `styles.css`, 新增風格覆寫檔，並更新 phase 報告文件
  - 完成標準:
    - `App.js` 主要預測/模擬流程委派到 handlers
    - UI 採用新設計語言（字體、色彩、背景、動效、RWD）
    - 靜態診斷與關鍵不變性搜尋通過

- [x] **539 結構化選號與微調優化 (Structural Optimization V8)** ❌ 2026-03-11 **REJECTED**
  - 觸發: 115000062期檢討 — 強回頭號與鄰號盲點
  - 結果: 實作 `HabitFourier`。正式驗證失敗：150期 Edge=-0.98%, Perm p=0.175。
  - **L69 警示**: 嚴禁「先部署後驗證」。此策略已從 `quick_predict.py` 移除。
  - 歸檔: `rejected/habit_aware_fourier_v8_539.json`

---

## 待辦 Backlog

### 策略研究

- [x] **539 正交溫度帶策略 (P0-P5)** ✅ 2026-03-01 完成 → 修正
  - 觸發: 115000054期檢討 — ACB 0命中，溫號組合期
  - P0: Markov 轉移注 — 1500p Edge +1.22%, z=1.22 (p≈0.11) **→ REJECTED** (rejected/markov_1bet_539.json)
  - P1: MidFreq 均值回歸注 — 1500p Edge +1.02%, z=1.94, **MODERATE_DECAY** (150p=+5.68%→1500p=+1.02%)，降為觀察
  - P2c: MidFreq+ACB 2注 — 1500p Edge +4.44%, z=3.16 (p≈0.001) **→ PENDING_VALIDATION** (待 McNemar)
  - P3a: Markov+MidFreq+ACB 3注 — 1500p Edge +5.77%, z=2.23 (p≈0.013) **→ PENDING_VALIDATION** (待 McNemar vs F4Cold)
  - P4a: Bandit 2注 — Edge +1.84%, 低於人工設計, REJECTED → rejected/bandit_ucb1_2bet_539.json
  - P4b: Bandit 3注 — Edge +3.10%, 低於人工設計, 保留觀察
  - P5: Lift pair 單注 — 1500p Edge -0.38%, UNSTABLE, REJECTED → rejected/lift_pair_single_539.json
  - ⚠️ 原報告 perm p=0.005 是200次shuffle的報告下限 (L47)，已改用 z-score p-value
  - **正進行500次shuffle正式驗證 + McNemar對比 (tools/validate_539_p2c_p3a.py)**

- [x] **P0★ quick_predict.py 539 F4Cold+ACB 整合** ✅ 2026-02-28 → 2026-03-01 修正還原
  - 原: 1注→ACB, 3注→F4Cold前3, 5注→F4Cold全5注
  - ~~新: 1注→ACB, 2注→MidFreq+ACB, 3注→Markov+MidFreq+ACB~~ (已還原，L48)
  - **現: 1注→ACB(ADOPTED), 2注→MidFreq+ACB(PENDING), 3-5注→F4Cold(PROVISIONAL)**
  - 3注路徑已還原為F4Cold前3注，待P3a通過McNemar後再決定是否替換

- [x] **P1 RSM 滾動監控加入 539** ✅ 2026-02-28 完成
  - rolling_strategy_monitor.py: DAILY_539 BASELINES + M2+ metric 支援
  - rsm_bootstrap.py: get_daily_539_strategies_inline() + DAILY_539 分支
  - 300期 bootstrap 結果:
    - acb_1bet: M2+ 15.00% (Edge +3.60%), STABLE
    - f4cold_3bet: M2+ 30.67% (Edge +0.17%), STABLE
    - f4cold_5bet: M2+ 52.33% (Edge +6.94%), STABLE

- [x] **P2 「高頻突斷」監控指標** ✅ 2026-02-28 結案
  - 200期回測: Edge -1.01%, z=-0.34, p=0.672 — NOT SIGNIFICANT
  - 四種 gap 閾值 (15/20/25/30) 均無統計顯著信號
  - **決策: NOT_ACTIONABLE — 維持 ACB 權重不變**
  - 教訓 L41 已記錄

- [x] **P3 連號對偵測器** ✅ 2026-02-28 歸檔
  - Lift=1.08x 不可操作
  - 歸檔: rejected/consecutive_pair_detector_539.json

- [x] **539 3注策略全面研究 (4種設計)** ✅ 2026-02-27 全部 FAIL
  - GapPressure+ZoneShift: perm p=0.71 — 覆蓋率問題
  - 正交化版: perm p=0.24 — 信號品質不足
  - P0-B F+Cold+Fmid: perm p=0.71, Signal Edge=-0.976% — 幾何效益假象
  - P0-C F+Cold+Cold2nd: perm p=0.56, Signal Edge=-0.176% — 幾何效益假象
  - 根因(L37): 非重疊3注的幾何效益+2.13%，超過所有3注設計的Signal Edge
  - **結論: 539 3注策略研究暫停。需新信號源(單注Edge>2%)才能突破**
  - **唯一可用策略: 5注 5bet_fourier4_cold (PROVISIONAL, perm p=0.030)**

- [x] **每日539策略驗證** ✅ 2026-02-25 完成
  - 首個通過三窗口驗證策略: `5bet_fourier4_cold` (PROVISIONAL)
  - 1500p Edge +1.35% (z=2.4), Permutation p=0.030 (SIGNAL_DETECTED)
  - 腳本: `tools/predict_539_5bet_f4cold.py`
  - **⚠️ 下次驗證: 5992期 (再200期後)**

- [x] **大樂透 RSM 持續監控 + P1+Dev 4注加入RSM** ✅ 2026-02-28 完成
  - 更新至 2111期，新增 p1_deviation_4bet 和 p1_dev_sum5bet 監控
  - 結果: p1_deviation_4bet 300p=+1.08%(STABLE); p1_dev_sum5bet 300p=+3.37%(最高，但30p=-2.29%)
  - 系統推薦: 4注=ts3_markov_4bet_w30(300p+2.42%), 5注=ts3_markov_freq_5bet_w30(300p+2.71%)
  - **下次更新: 2111+100=2211期**

- [x] **威力彩 RSM 持續監控** ✅ 2026-02-28 完成
  - 更新至 1889期
  - 結果: fourier_rhythm_3bet 持續ACCELERATING(z=+1.72), 30p=+15.50% (熱！)
  - orthogonal_5bet: 30p=-1.24%→STABLE，100p/300p全正 ★推薦
  - **下次更新: 1889+100=1989期**

- [x] **539 ACB 替換 F4Cold 注5 研究** ✅ 2026-02-27 結案
  - 結果: 替換後5注 Signal Edge +8.25% vs F4Cold +8.21% (差+0.04pp)
  - McNemar net=+1 hit, p=1.000 — **統計上無法區分**
  - 注5成分: ACB edge +1.336% vs Cold edge +0.803% (+0.53pp)
  - 折合5注: +0.25pp ≈ 3.7期/1500期改善 → 低於統計可偵測門檻
  - **根因: Fourier Top-20佔用最強信號空間，注5在殘餘池(rank21-39)中兩種方法幾乎等效**
  - **決策: 維持 F4Cold，不替換。ACB最佳用途為獨立單注策略**

- [x] **大樂透 6注策略研究** ❌ 2026-03-12 **REJECTED**
  - 三種方法（Zone Balance / Residual Hot / Cold）獨立命中率 1.60~2.27%，均≤隨機基準 1.86%
  - 幾何效益陷阱（同 L37）：5注已覆蓋 30/49，殘餘池無可預測結構
  - 歸檔：`rejected/biglotto_6bet_zone_residual.json`，**大樂透維持 5注架構**

- [x] **威力彩 4注策略** ✅ 2026-03-03 完成
  - 回測腳本: `tools/backtest_power_4bet.py`（N=1890期，三策略全部通過）
  - **採納: PP3+FreqOrt** — 150p=+5.40%, 500p=+3.60%, 1500p=+3.33%, perm p=0.000
  - McNemar vs PP3: net=+65 (全新增，0損失)
  - 備選通過: ACB-Power (perm p=0.010, 1500p +3.06%), FourierResidual (perm p=0.010, 1500p +2.66%)
  - Production: `tools/quick_predict.py 威力彩 4`

### 系統建設

- [x] **Phase 2 — Multi-Provider LLM 自動化分析** ✅ 2026-03-12 完成（Mock 框架已上線）
  - **背景**: MiroFish 評估後確認 LLM Agent 可自動化策略分析與 RSM 監控報告
  - **解鎖條件**: 系統實際產生獲利後再實施（用戶決策 2026-03-12）
  - **設計規格（預先記錄）**:
    - Provider 優先順序: **Groq（免費 + 最快）** → Anthropic Claude → OpenAI GPT-4o-mini
    - Token 估算: 每場彩票分析 ≈ 500 tokens，每天 3 彩種 × 10 calls = 1,500 tokens/day
    - 日額度: Groq 免費層 ~14,400 TPM（14.4K requests/day），遠低於需求
    - **實作要點**:
      1. `lottery_api/engine/llm_analyzer.py` — 多 Provider 路由器
         ```python
         PROVIDERS = ['groq', 'anthropic', 'openai']  # 優先順序
         def analyze(prompt) -> str:  # 自動 fallback
         ```
      2. Groq SDK: `pip install groq`，MODEL = `llama-3.3-70b-versatile` 或 `mixtral-8x7b`
      3. 觸發時機: `quick_predict.py` 執行後 → 自動分析 RSM 狀態 → 生成中文建議
      4. 輸出: append 至 `lottery_api/data/llm_analysis_log.jsonl`
    - **Phase 2-A（先實作）**: Groq 單 provider，僅分析 RSM 警示策略
    - **Phase 2-B（後實作）**: Multi-provider fallback + 完整三彩種每日分析
  - **參考**: MiroFish multi-agent 設計、ReACT reasoning pattern

- [x] **建立策略生命週期文件夾**
  - 依 CLAUDE.md 規範建立 `strategies/` 目錄
  - 每個採納策略需有 `strategy.yaml` + `backtest_report.md`

- [x] **rejected/ 重測條件觸發機制** ✅ 2026-03-12 完成
  - `tools/scan_rejected.py` — 自動偵測資料量門檻 + RSM 條件
  - 目前觸發: **0項**（bug修正後重掃: BL=2115, PL=1892, 539=5806 均未達門檻）
  - 用法: `python3 tools/scan_rejected.py` / `--triggered` / `--lottery 大樂透`

- [x] **自動 Permutation Test 整合** ✅ 2026-03-13 完成
  - `lottery_api/engine/perm_test.py` — 通用 temporal-shuffle perm test 共用模組
  - `perm_test(history, predict_fn, baseline, n_perm=200)` → p_emp / cohens_d / verdict
  - 正確方法：shuffle draw order（非 hits array），保留號碼分布，破壞時序結構
  - 任何回測腳本 `from lottery_api.engine.perm_test import perm_test` 即可使用

- [x] **Sharpe Ratio 計算整合** ✅ 2026-03-12 完成
  - `StrategyState.sharpe_300p` — Bernoulli Sharpe = edge / sqrt(rate*(1-rate))
  - `status_line()` 已加入 Sharpe 輸出（含 ✓/✗ 標記）
  - Sharpe > 0 ≡ Edge > 0（對 CLAUDE.md 規範滿足充要條件）

### 文件補完

- [x] **更新 lottery_api/CLAUDE.md 策略評分** ✅ 2026-03-13 完成
  - 新增「📊 策略評分」章節，含公式定義 + 10個採納策略 Score 計算結果
  - Score = (ROI × Stability × Significance) ÷ Complexity
  - 539 MidFreq+ACB 最高(1.30)，大樂透 P1+Dev 最低(0.07)
  - 同步加入 perm_test.py 模組使用範例

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

- [x] **P1+偏差互補 4注 Permutation Test** ✅ 2026-02-25 完成
  - p=0.010, Cohen's d=2.66 → **SIGNAL DETECTED**，正式採納取代 TS3+Markov 4注
  - 附帶發現：TS3+Markov 4注(p=0.080) 和 5注(p=0.075) 均降為 MARGINAL
  - 腳本：`tools/p3_shuffle_permutation_test.py --lottery BIG_LOTTO --shuffles 200`

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

### 2026-02-26 — 539 Zone-Gap 3注策略回測 FAIL
- 觸發: 115000050期檢討會議 P0 action items
- 實作: GapPressureScorer + ZoneShiftDetector 兩個新模組
- 結果: **FAIL** — 策略 M2+ 31.60% 不優於 random 3-bet 32.56% (perm p=0.71)
- 但: 策略顯著優於舊策略 (McNemar p=0.0152, +29 draws)
- 根因: 3注之間 overlap 過大 (13.4 unique vs random 15 unique)
- 處置: 記錄至 `rejected/zone_gap_3bet_539.json`, 回退至舊策略
- 新發現: **舊策略也未通過驗證** (25.80% M2+ vs 30.44% baseline = -4.64% edge)
- 教訓: L30 — 3-bet individual quality < inter-bet diversity
- 模組保留: gap_pressure.py + zone_shift_detector.py 作為建構元件

### 2026-02-26 — 539 3-bet 正交化回測 FAIL
- 觸發: L30 根因修正 — chain exclusion 消除 bet overlap
- 實作: 為 GapPressure + ZoneShift 加入 `exclude` 參數，chain exclusion
- 結果: **FAIL** — M2+ 34.00% vs random 32.56%, perm p=0.2388 (edge +1.44%, Z=0.69)
- 正面: 正交化機制有效 — overlap 從 13.4→15 unique, M2+ 從 31.60%→34.00%
- 正面: McNemar vs old p=0.0009 (+40 draws)，正交版顯著優於現行策略
- 根因: GapPressure + ZoneShift 個別信號品質不足 (各注僅略優於 random)
- 處置: 記錄至 `rejected/539_3bet_orthogonal.json`, 無生產部署變更
- 教訓: L31 — 覆蓋率是必要但非充分條件
- **現狀: 539 2注和3注策略候選 PENDING_VALIDATION (2026-03-01 修正)**

### 2026-03-01 — 115000054 期檢討 → 正交溫度帶策略研究
- 觸發: ACB(主力策略)在第054期命中0個，原因分析：4/5為WARM號碼，ACB專抓COLD
- 發現:
  1. Markov 轉移矩陣從上期號碼可預測3/5 (08,29,31)
  2. 均值回歸(MidFreq)選擇最接近期望頻率的號碼可命中2/5 (15,29)
  3. ACB+Markov+MidFreq 三注覆蓋 COLD/WARM/HOT 全溫度帶
- 實作: P0~P5 共11種策略設計，全部完成三窗口驗證+permutation test
- 結果 (⚠️ 修正: 原 perm p=0.005 是200次shuffle下限, 改用z-score):
  - P2c MidFreq+ACB 2注: 1500p Edge +4.44%, z=3.16 (p≈0.001) → **PENDING_VALIDATION**
  - P3a Markov+MidFreq+ACB 3注: 1500p Edge +5.77%, z=2.23 (p≈0.013) → **PENDING_VALIDATION**
  - P0 Markov 單注: z=1.22 (p≈0.11) → **REJECTED** (rejected/markov_1bet_539.json)
  - P1 MidFreq 單注: z=1.94, MODERATE_DECAY → 降為觀察
  - P5 Lift pair: 1500p UNSTABLE → rejected
  - P4a Bandit 2注: Edge +1.84% (不及人工設計) → rejected
- 修正動作 (用戶指正):
  - quick_predict.py 3注路徑已還原為 F4Cold 前3注
  - P2c/P3a 500次shuffle正式驗證完成 ✅ (tools/validate_539_p2c_p3a.py)
  - 新增教訓: L47 (p-value floor), L48 (McNemar gate)
- 關鍵教訓: L42 — 多注策略的信號正交性比單注信號強度更重要（概念正確，但驗證標準需完善）

### 2026-03-01 — P2c/P3a 500-shuffle 正式驗證結果
- 腳本: tools/validate_539_p2c_p3a.py (seed=42, 500 shuffles)
- **P2c (MidFreq+ACB 2注):**
  - 三窗口: 150p=+9.79%, 500p=+5.26%, 1500p=+4.79% → **MODERATE_DECAY** (150p/1500p=2.04x)
  - Permutation: z=2.08, p_z=0.019, p_emp=0.028 → **SIGNAL ✅**
  - 決定: **PENDING** — 信號真實但衰減模式需觀察。2注路徑維持 MidFreq+ACB 但標記 PENDING
- **P3a (Markov+MidFreq+ACB 3注):**
  - 三窗口: 150p=+6.83%, 500p=+5.50%, 1500p=+6.03% → **STABLE ✅**
  - Permutation: z=1.87, p_z=0.030, p_emp=0.040 → **SIGNAL ✅**
  - McNemar vs F4Cold: chi2=0.694, p=0.405, net=+23 → **NOT SIGNIFICANT ❌**
  - 決定: **PENDING** — 信號真實且穩定，但未能顯著優於F4Cold。3注路徑維持 F4Cold
- **F4Cold 3bet (baseline):**
  - 三窗口: 150p=-0.50%, 500p=+2.10%, 1500p=+4.50% → **UNSTABLE** (150p negative!)
  - 發現: F4Cold 3注本身也不穩定，呈 LATE_BLOOMER 模式
- **結論:** 維持現狀不變。P3a有更好的信號但McNemar未通過。F4Cold 3注和P3a在配對比較下無顯著差異(p=0.40)。兩者都是有效策略，但都還需觀察。

### 2026-03-03 — 威力彩 4注策略研究 (PP3+FreqOrt 採納)
- 觸發: 3注→5注 Edge 跳躍缺口 (+2.43%→+3.89%)，研究4注中間選項
- 三候選: FreqOrt / ACB-Power / FourierResidual
- 結果 (N=1890期, 100次permutation):
  - FreqOrt:      150p=+5.40%, 500p=+3.60%, 1500p=+3.33%, perm p=0.000 ★最佳
  - ACB-Power:    150p=+4.73%, 500p=+2.00%, 1500p=+3.06%, perm p=0.010
  - FourierResid: 150p=+2.06%, 500p=+1.80%, 1500p=+2.66%, perm p=0.010
  - 三策略全部通過: 三窗口全正 + perm p≤0.05 + McNemar vs PP3 全正向
- 決策: **採納 PP3+FreqOrt** (信號最強, 架構最簡, 與5注完全一致)
- 重要發現: 4注=5注的前4注子集，Edge 平滑遞增: +2.43%→+3.33%→+3.89%
- 變更: quick_predict.py 4注/5注路徑修正 (原有 num_bets≥4 的 routing bug)
- 教訓 L54: 威力彩注級跨越可直接切片5注正交架構，無需設計新信號

### 2026-03-06 — 威力彩 PP3v2 研究結案 (115000019期檢討)
- 觸發: 115000019 (07,11,14,32,36,38+sp02) — 32,36 未被 PP3 捕捉
- 最近方法: 4bet ClusterPivot 命中 4/6(07,11,14,38)+特別號sp02✅，但 ClusterPivot 已因 SHORT_MOMENTUM 被拒
- 三個改進假說驗證 (三窗口 150/500/1500, N=1890期, Perm N=200):
  - **PP3-EchoBoost** (Lag-1 echo boost×1.5): 150p=+4.16%, 500p=+2.43%, 1500p=+1.56%, p=0.130 → **❌ SHORT_MOMENTUM REJECTED**
  - **PP3-Z3Gap** (Bet3 改 Z3 高gap注入): 150p=+0.16%, 500p=+0.83%, 1500p=+1.64%, p=0.045 → **⚠️ WATCH 300期**
  - **PP3v2-Combined** (EchoBoost+Z3Gap): 150p=+1.50%, 500p=+0.43%, 1500p=+0.34%, p=0.420 → **❌ REJECTED**
  - **PP3-Baseline 重確認**: 150p=+3.50%, 500p=+2.23%, 1500p=+2.43%, p=0.025 → **✅ STABLE 維持**
- 歸檔: rejected/power_echo_boost.json, rejected/power_pp3v2_combined.json, rejected/power_z3gap_watch.json
- 教訓 L55: Lag-1 Echo Boost 是 SHORT_MOMENTUM 陷阱（與 ClusterPivot 同類）— 近期回聲不是真實週期信號
- 教訓 L56: 時間尺度不同的信號不應疊加（SHORT_MOMENTUM×1 + LONG_SIGNAL×1 = 互相干擾）
- 教訓 L57: 115000019 的未命中(32,36)是 Fourier 正常方差，非系統盲區，無需或無法修正
- **下次 PP3-Z3Gap 重評: 2026-06 (~300期後)**
