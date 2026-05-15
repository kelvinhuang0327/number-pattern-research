# Agent Orchestrator Backlog

## 北極星目標 (North Star)

在**大樂透、威力彩、今彩539**三種台灣公益彩券中，透過統計方法找到相對於隨機基準具有穩定正 Edge 的選號策略，部署至生產系統並持續監控。

**若三種彩種的信號空間均已窮盡（無任何新假說通過驗證），在 completed 中標記 `[SIGNAL_EXHAUSTED_ALL]` 並通知使用者停止研究。**

---

## 驗證標準（任何策略必須全部通過）

1. 三窗口全正：150期、500期、1500期 Edge 均 > 0
2. permutation test p < 0.05（200 shuffles, seed=42）
3. Cohen's d > 1.0
4. 替換現有策略需 McNemar p < 0.05
5. 多注策略每注邊際效率 > 80%
6. 無數據洩漏：通過 `tools/verify_no_data_leakage.py`

---

## 各彩種現狀與研究優先順序

### 今彩539（DAILY_539）— 信號高度飽和
現役策略（RSM 監控）：
- 1注 `acb_1bet`：edge300=+3.27%，Sharpe=0.092
- 2注 `midfreq_acb_2bet`：edge300=+8.46%，Sharpe=0.185 ★最佳
- 3注 `acb_markov_midfreq_3bet`：edge300=+8.50%

已結案：H001~H010 全部 REJECT（詳見 `memory/lessons.md` L79-L106）

優先研究：
1. H011 起的新假說（跨期叢集、週間效應、彩池規模影響）
2. 現役三信號以外的第四正交信號
3. 全 FAST_REJECT 時記錄「539信號空間完全窮盡」，停止分配539研究任務

### 威力彩（POWER_LOTTO）— 有待驗證方向
現役策略（RSM 監控）：
- 3注 `fourier_rhythm_3bet`：edge300=+3.16%，Sharpe=0.090 ★主力
- 4注 `pp3_freqort_4bet`：edge300=+3.40%，Sharpe=0.088
- 5注 `orthogonal_5bet`：edge300=+2.76%
- PROVISIONAL：`midfreq_fourier_2bet`（perm p=0.030，McNemar 未達 p<0.05）

優先研究：
1. **[RETRY_REQUIRED] PROVISIONAL 策略升格**：`midfreq_fourier_2bet` McNemar 驗證（500期 OOS）
2. **[RETRY_REQUIRED]** `fourier_rhythm_3bet` 500期 OOS 驗證確認長期穩定
3. **[BLOCKED_ENV]** Winning Quality proxy（`lottery_api/engine/winning_quality.py`）P2-1 回測驗證
4. **[TODO]** 探索 PP3 + MidFreq 正交新組合
5. **[TODO]** 威力彩特別號 V3 改善（目前 Edge=+2.20%）

### 大樂透（BIG_LOTTO）— 維護模式
現役策略：
- 4注 `p1_deviation_4bet`：290期實測 p=0.035 ✅ PRODUCTION ★主力
- 5注 `p1_dev_sum5bet`：290期實測 p=0.033 ✅

信號邊界：L91 確認 49C6 與公平隨機無法區分，6項隨機性全通過。

優先研究：
1. 監控 `p1_deviation_4bet` 與 `p1_dev_sum5bet` 是否維持 p<0.05（目標 500期實測）
2. 若現役策略 500期後 edge < 0 → 降權，尋找替代
3. 嘗試彩池累積金額對選號行為的影響（市場行為信號）
4. 若無新信號通過 → 維護模式，不分配新策略研究任務

---

## 執行狀態快照（截至 2026/04/22 14:20，依 `orchestrator.db`）

- `Task #17` `檢查 backlog 並產出下一個可驗證任務`：`RUNNING`
- `Task #16` `檢查 backlog 並產出下一個可驗證任務`：`FAILED`
- `Task #15` `威力彩 WQ P2-1 無洩漏驗證`：`FAILED`（環境權限阻塞，未完成正式驗證）
- `Task #14` `檢查 backlog 並產出下一個可驗證任務`：`FAILED`
- `Task #13` `威力彩 P2-1 Winning Quality 驗證`：`FAILED`
- `Task #12/#11/#3/#2` `fourier_rhythm_3bet` OOS 驗證：`FAILED`（多次因 Copilot 配額/執行失敗未取得有效驗證結論）
- `Task #6` `威力彩 Winning Quality P2-1 驗證`：任務狀態 `COMPLETED`，但 worker 輸出顯示 `402 no quota`，不視為有效研究完成
- `Task #5` `midfreq_fourier_2bet McNemar 500期 OOS 升格驗證`：任務狀態 `COMPLETED`，但驗證門檻未過

### Task #5 關鍵數值（`runtime/power_midfreq_oos500_wq_p21_20260421_seed42.json`）

- 三窗口：150 期 edge = `-0.923%`（未達全正）
- McNemar：`p=0.1354`（未達 `<0.05`）
- 多注邊際效率：`0.7857`（未達 `>0.8`）
- 結論：`midfreq_fourier_2bet` 目前仍為 PROVISIONAL，不可升格替換現役策略

---

## Planner 任務分配邏輯

每次 tick 依序判斷：
1. **有 PROVISIONAL 策略** → 優先完成 McNemar/OOS 驗證升格
2. **現役策略需監控** → 確認 RSM edge 未轉負，若轉負立刻降權
3. **新信號探索** → 按彩種優先順序（威力彩 > 539 > 大樂透）
4. **系統維護** → 前端改善、DB 整理、測試補強（前三項無待辦時才執行）

每個 prompt 必須包含：
- **Objective**：具體假說或目標（含彩種和期數窗口）
- **Scope**：涉及的策略、檔案、工具
- **Constraints**：seed=42、不修改 RSM 配置、不降低現有 Edge
- **Acceptance Criteria**：具體數值目標
- **Handoff Notes**：給下一輪 Planner 的關鍵發現

---

## 禁止事項

- 不得刪除現有的 `lottery_api/engine/` 和 `lottery_api/routes/` 生產邏輯
- 不得修改 RSM 策略配置（`lottery_api/data/strategy_states_*.json`）而不經過 McNemar 驗證
- 不得部署任何 Edge < 0 的策略
- 不得繞過 `lottery_api/CLAUDE.md` 和 `CLAUDE.md` 的驗證標準
- 不得直接修改生產資料庫 `lottery_api/data/lottery_v2.db`
- 新假說結果必須記錄至 `memory/lessons.md`（接續 L107 之後）

---

## 參考資源

- 策略規範：`lottery_api/CLAUDE.md`（含完整歷史策略表）
- 研究記憶：`memory/MEMORY.md`、`memory/lessons.md`（L1~L107）
- 預測入口：`tools/quick_predict.py`
- RSM：`lottery_api/engine/rolling_strategy_monitor.py`
- 標準回測：`lottery_api/utils/benchmark_framework.py`
- Permutation test：`lottery_api/engine/perm_test.py`

---

## 配額阻塞待重跑清單（2026/04/23 盤點）

以下任務在 DB 內目前為 `COMPLETED`，但 completed 檔案實際包含 `weekly rate limit` / `no quota` / `switch to auto model to continue`，屬**假完成**，不得視為有效研究結論。已重新加入 backlog 等待可用 runner / model 後重跑。

重跑原則：
- 優先改走本地可重現流程或非 quota 阻塞 runner
- 若仍使用 Copilot，必須先確認 model / quota 可用
- 相同主題的假完成任務合併為一筆 backlog，不逐筆重複排入
- 單純「修復配額假完成」類系統任務不逐筆重排，由一條總括治理任務承接

待重跑項目：
- **[RETRY_REQUIRED][POWER_LOTTO]** `威力彩 WQ P2-1` 正式驗證重跑
  來源假完成：Task `#6`、`#43`、`#50`、`#56`
  要求：改用本地可重現驗證流程，留下正式 result artifact；若外部模型不可用，直接標記 `BLOCKED_ENV`，不得再次標 `COMPLETED`
- **[RETRY_REQUIRED][POWER_LOTTO]** `威力彩主線健康監控 / 降權決策` 重跑
  來源假完成：Task `#42`、`#49`、`#51`
  要求：完成 RSM 本地監控、降權判定與可驗證輸出，禁止只留下 rate-limit 訊息
- **[RETRY_REQUIRED][DAILY_539]** `MicroFish 升格驗證` 重跑
  來源假完成：Task `#41`
  要求：保留完整驗證結果與是否可升格的明確結論
- **[RETRY_REQUIRED][DAILY_539]** `彩池 / trusted pool-data / H013` 整合重跑
  來源假完成：Task `#44`、`#45`、`#52`、`#55`、`#57`、`#58`
  要求：先確認資料來源與欄位可信度，再重跑 H013 / poolsize 正式驗證；不可把資料修復與正式驗證拆成多筆空跑
- **[RETRY_REQUIRED][BIG_LOTTO]** `500 期監控與降權判定` 重跑
  來源假完成：Task `#53`、`#59`
  要求：用本地監控腳本重建 150/500/1500 期判定與降權結論
- **[TODO][SYSTEM]** `quota / model / fallback 治理任務`
  來源假完成：Task `#46`、`#47`、`#48`、`#54`
  要求：統一整理 CLI model 設定、quota 偵測、fallback runner、假完成回補規則；不要再逐筆重跑同型修復任務

盤點備註：
- Task `#7`、`#8` 為早期樣板 placeholder 任務且同樣命中 `you have no quota`，不直接加入研究 backlog；僅作歷史異常證據
- 後續若掃描到新的 `COMPLETED + quota/rate-limit` 任務，應併入上述主題，不另起重複 backlog

---

## Deep Research Update (2026-04-25)

- Task: Deep Research — Adaptive Bet Sizing + Signal Reconstruction + Coverage Optimization (Focus: G,F,A)
- Artifacts produced: predictions/bet_sizing_policy.json, outputs/coverage_regime_rules.json, outputs/cold_phase_strategy_set.json, outputs/hybrid_strategy_candidates.json, outputs/task_result.json, outputs/completed_markdown.md
- Summary: Generated 3 adaptive bet-sizing candidates, multiple cold-phase candidates per game, and hybrid ensemble combos. Monte Carlo (seed=42, n=1000) completed for all phases. Top adaptive candidate: `hybrid_conservative_0p55_1p45x` (composite score≈0.7736). No candidate passed all strict permutation/McNemar gates across 150/500/1500 windows; results are reproducible in outputs/.
- Recommendation: Schedule formal three-window backtests (150/500/1500) using `lottery_api` benchmark framework and `perm_test.py` for the top candidates; perform McNemar vs incumbents before any state changes. Do NOT modify `lottery_api/data/strategy_states_*.json` in-place; record follow-up tasks in backlog for targeted OOS/McNemar runs.

<!-- AUTO_STATUS_START -->

## 自動狀態快照（Auto-generated）

- 更新時間（Asia/Taipei）：`2026/04/30 13:19:36`
- 最近任務總數（查詢範圍）：`50`

### 研究任務摘要
- midfreq_fourier_2bet McNemar 驗證：`NO_RECORD`
- fourier_rhythm_3bet 500期 OOS 驗證：`NO_RECORD`
- Winning Quality P2-1 驗證：`NO_RECORD`

### 最近 8 筆任務
- #370 | 20260430131705pd | COMPLETED | 耗時 2m21s | 完成 2026/04/30 13:19:36 | [POST-DEPLOY] H6 Rollback Simulation — DAILY_539
- #369 | 20260430130705pd | COMPLETED | 耗時 2m11s | 完成 2026/04/30 13:09:27 | [POST-DEPLOY] H6 Live Monitoring Calibration — DAILY_539
- #368 | 20260430125646 | COMPLETED | 耗時 6m54s | 完成 2026/04/30 13:04:01 | [VALIDATION] Exploration follow-up (cross_lottery_transfer) 
- #367 | 20260430124645 | COMPLETED | 耗時 3m22s | 完成 2026/04/30 12:50:10 | [VALIDATION] Exploration follow-up (ux_decision_quality) — 2
- #366 | 20260430123645 | COMPLETED | 耗時 4m12s | 完成 2026/04/30 12:41:13 | [VALIDATION] Exploration follow-up (constraint_postprocess) 
- #365 | 20260430122645 | COMPLETED | 耗時 1m21s | 完成 2026/04/30 12:28:11 | [EXPLORE-B] Constraint / Postprocess Hypothesis Research
- #364 | 20260430121642 | COMPLETED | 耗時 2m44s | 完成 2026/04/30 12:19:33 | [EXPLORE-A] External Signal Hypothesis Research
- #363 | 20260430120642 | COMPLETED | 耗時 2m53s | 完成 2026/04/30 12:09:42 | [EXPLORE-F] UX / Decision Quality Research

<!-- AUTO_STATUS_END -->
---

## [SIGNAL_EXHAUSTED_ALL] — 三彩種信號窮盡收斂（2026/04/23）

**Conclusion**: All three lottery games (BIG_LOTTO, DAILY_539, POWER_LOTTO) have **exhausted actionable research directions** within the established validation framework as of 2026-04-23T16:11:18+08:00.

**Audit Evidence**: See `runtime/agent_orchestrator/signal_exhaustion_closure_20260423.md/json` for formal audit trail.

### 停止新研究分配原則 (NO_NEW_RESEARCH Policy)

**Effective Immediately**: Planner MUST NOT generate new strategy research, hypothesis validation, or parameter micro-tuning tasks for BIG_LOTTO, DAILY_539, or POWER_LOTTO.

**Rationale Per Game**:

#### BIG_LOTTO (L90/L91 Confirmed)
- **Signal Boundary**: 49C6 geometry proves indistinguishable from fair random (L91)
- **All Frequencies Exhausted**: L90 confirms complete signal space exhaustion
- **MicroFish Attempt Failed**: L89 documented and closed
- **Current Strategy**: Maintain `p1_deviation_4bet` + `p1_dev_sum5bet` for monitoring only
- **Next Allowed**: RSM edge tracking, downgrade trigger detection, no new research

#### DAILY_539 (H001~H013 Exhaustion Confirmed)
- **H001~H010 (Frequency Family)**: L82 confirms exhaustion; all variants tested and REJECT
- **H011 (Weekday/Calendar)**: REJECT (chi-sq p=0.9281, no 150/500p signal) — L117
- **H012 (Cross-Draw Cluster)**: REJECT (lag overlap ≈random, 150/500p unmet) — L118
- **H013 (Pool-Size)**: **NEW FORMAL CLOSURE** (2026-04-23)
  - 100% data backfill from official Taiwan Lottery API (sell_amount, total_amount)
  - Formal test: edge≈0%, p≈1.0 across all windows
  - Verdict: Pool-size provides zero predictive power — L129
  - Do NOT retry same family
- **MicroFish+MidFreq Promotion**: McNemar p=0.1797 (insufficient vs <0.05 threshold) — L128
- **Current Strategies**: Maintain `acb_1bet`, `midfreq_acb_2bet`, `acb_markov_midfreq_3bet` for monitoring only
- **Next Allowed**: RSM McNemar monitoring, hit-rate KPI tracking, no new research

#### POWER_LOTTO (Mainline Mature, All Extensions Exhausted)
- **Fourier Rhythm 3bet**: Downgraded to WATCH (150/500p perm failed, 1500p only) — L126
- **PP3+MidFreq Orthogonal V2**: WATCH/REJECT (6 candidates, 150/500p unmet, <80% efficiency) — L123
- **MidFreq Regime Gate V1**: REJECT (150p perm p=0.0995 ≥0.05) — L122
- **Non-Family Layer-1 3bet**: **EXHAUSTIVE RESEARCH COMPLETE**
  - 4-family search: dispersion, odd-tail, zone tensor, residue stability
  - All passed leakage check; none passed permutation on all windows simultaneously
  - McNemar never entered
  - Formal closure: L127 "REJECT_ALL_NONFAMILY_LAYER1_3BET"
  - Do NOT continue nonfamily Layer-1 variants
- **Special V4 Reweighting**: REJECT (no baseline beat) — L121
- **Winning Quality P2-1**: REJECT (500/1500p permutation fail; popularity_score insufficient without real commerce data) — L130
- **Current Strategies**: Maintain `fourier_rhythm_3bet` + `pp3_freqort_4bet` + `orthogonal_5bet` with WATCH monitoring
- **Next Allowed**: Mainline drift monitoring, WATCH candidate shadow tracking, no new research

### 维护政策 (Maintenance-Only Policy)

**Allowed Activities**:
✅ RSM health monitoring (edge drift, Sharpe stability)
✅ Drift/PSI monitoring (concept drift detection on features)
✅ Dashboard / reporting maintenance (UI fixes, data freshness)
✅ DB / task governance repairs (narrow scope, not wholesale backfill)

**Forbidden Activities**:
❌ New strategy research or hypothesis validation
❌ Reopening H001~H013 hypothesis families or variants
❌ Parameter micro-tuning on defeated signal families
❌ Quota workarounds or fake-completion simulation
❌ Non-family Layer-1 reweighting attempts (L127 closure)
❌ WQ-based filtering without real commerce data (L130)

### 信號窮盡後的Planner分流 (Next Cycle Instructions)

**Next Task Type**: System maintenance, RSM monitoring, governance repairs (NOT research)

**Planner Must Skip**:
- "Explore one more pool-size variant"
- "Try Special V4 with different orthogonal axis"
- "Retry WQ with alternative proxy"
- "Quad-check MicroFish with new window size"

**Reopening Triggers** (Only if true external change):
1. Lottery rule change (odds, pool structure, draw frequency)
2. New authenticated data source (real prize-payout records, not proxy)
3. New mathematical signal family (not orthogonal to existing PP3/Fourier/MidFreq)

### Reference Artifacts

- **Formal Audit**: `runtime/agent_orchestrator/signal_exhaustion_closure_20260423.md`
- **JSON Equivalent**: `runtime/agent_orchestrator/signal_exhaustion_closure_20260423.json`
- **Validation Results**:
  - BIG_LOTTO: `analysis/results/biglotto_monitor_500p_20260423.md`
  - DAILY_539: `analysis/results/daily539_h013_backfill_final_report_20260423.md`, `daily539_microfish_midfreq_promotion_validation_20260423.json`
  - POWER_LOTTO: `analysis/results/power_watch_downgrade_decision_20260423.json`, `power_pp3_midfreq_orthogonal_v2_20260423.json`, `power_midfreq2bet_regime_gate_v1_20260423.json`, `power_layer1_nonfamily_3bet_validation_20260423.json`, `power_special_v4_validation_20260423.json`, `power_wq_p21_validation_20260423.md`
- **Lessons**: `memory/lessons.md` (L82, L85~L93, L115~L130)

---

## Deep Research Update (2026-04-24)
- Task: Deep Research — Cold-phase + Signal Reconstruction + Adaptive Bet Sizing
- Artifacts: tools/deep_research_cold_results.json, outputs/task_result_deep_research.json
- Next: perm test for cold_low_freq_2bet (300/500/1500p), run 150p quick benchmarks for signal reconstruction candidates, pilot adaptive bet sizing with monitoring.

- Deep Research run: Adaptive Bet Sizing + Signal Reconstruction (2026-04-24T15:38:00+08:00)
  artifacts: outputs/deep_research_initial.json, outputs/deep_research_mc.json, outputs/deep_research_mc_existing.json
  note: initial 3 candidates evaluated (150p); none passed edge>0.01. Recommended next: focus on existing best strategies for deeper regime-aware sizing and permutation testing.

- [AUTO] Deep Research run produced candidates and artifacts: outputs/deep_research_candidates.json, outputs/deep_research_mc_summary.json, outputs/coverage_regime_rules.json

# Deep Research Follow-up (auto-appended)
- 2026-04-25: Temporal overdue candidate DAILY_539 produced edge_150=+0.01846 but failed vs incumbent. Schedule three-window backtests (150/500/1500) and McNemar vs incumbent. Use local benchmark framework; do NOT modify strategy_states files.
- Assign: run_500w for temporal_overdue_daily_539; run McNemar when 500w completes.
