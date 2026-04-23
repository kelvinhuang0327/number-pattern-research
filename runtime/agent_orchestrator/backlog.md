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

<!-- AUTO_STATUS_START -->

## 自動狀態快照（Auto-generated）

- 更新時間（Asia/Taipei）：`2026/04/23 14:02:27`
- 最近任務總數（查詢範圍）：`50`

### 研究任務摘要
- midfreq_fourier_2bet McNemar 驗證：`NO_RECORD`
- fourier_rhythm_3bet 500期 OOS 驗證：`COMPLETED` (Task #31, 2026/04/23 00:10)
- Winning Quality P2-1 驗證：`NO_RECORD`

### 最近 8 筆任務
- #67 | 2026/04/23 13:55 | FAILED | 耗時 6m33s | 完成 2026/04/23 14:02:27 | 治理 quota 假完成與本地 fallback
- #66 | 2026/04/23 13:34 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 13:35:43 | 大樂透500期本地監控定案
- #65 | 2026/04/23 13:24 | REPLAN_REQUIRED | 耗時 27s | 完成 2026/04/23 13:24:41 | 大樂透500期本地監控重建
- #64 | 2026/04/23 13:13 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 13:14:14 | 威力彩外生訊號本地盤點
- #63 | 2026/04/23 13:02 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 13:02:56 | 修復 quota 假完成與本地 fallback
- #62 | 2026/04/23 12:55 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 12:56:32 | 威力彩新外生訊號可行性盤點
- #61 | 2026/04/23 12:51 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 12:51:59 | 治理 quota 假完成與本地 fallback
- #60 | 2026/04/23 12:40 | REPLAN_REQUIRED | 耗時 40s | 完成 2026/04/23 12:41:22 | BIG_LOTTO 500期本地監控定案

<!-- AUTO_STATUS_END -->
