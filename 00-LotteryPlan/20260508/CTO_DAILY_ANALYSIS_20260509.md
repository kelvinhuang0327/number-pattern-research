已完成 CTO 重新校準，並直接更新 roadmap：

[lottery_roadmap_20260508.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-LotteryPlan/20260508/lottery_roadmap_20260508.md)

**核心結論**
下一階段最值得優化的方向是：

```text
Finish the protected delivery loop, then make CI governance observable.
```

也就是今天不要開新策略、不要 full replay、不要改 Replay API。最高 ROI 是先把 protected main flow 真正跑完。

**我更新的重點**
- 將 roadmap 升級為 `2026-05-09 CTO recalibration v1.1`。
- 把原本 P0.5 replay cutoff audit 從「今日主軸」改為「已完成/保留 drift guard」。
- 重新排序 P0/P1/P2/P3：
  - `P0`: PR #2 approval、protected merge、遠端 main 狀態校正、report branch 處理、worktree isolation。
  - `P1`: CI summary annotation、dedicated lane observation log、fixture schema drift guard、branch protection runbook。
  - `P2`: Strategy Eval metadata、Multiple Testing Registry、EvidenceCollector、Replay freshness/run consistency guard。
  - `P3`: Strategy Eval v1、BFF、Frontend E2E、schema migration registry。
- 明確列出 stop rules：不 direct push main、不 force push、不 admin override、不 commit DB、不做策略 mining。

**關鍵阻塞**
我用 GitHub CLI 即時驗證後發現一個重要落差：

```text
remote main = a13e1aa
PR #2 head = 32fc1c8
PR #2 = OPEN / BLOCKED / REVIEW_REQUIRED
replay-default-validation = SUCCESS
replay-dedicated-db-validation = SKIPPED, not required
```

所以交接裡「main 已含 32fc1c8」這點，和 GitHub 遠端狀態不一致。roadmap 已把這點標成高優先阻塞，後續應以 GitHub remote 為 source of truth。

**今天最應聚焦**
1. 取得 PR #2 reviewer approval。
2. 用正常 protected flow merge PR #2。
3. 確認 remote `main` 真的包含 `32fc1c8`。
4. 再處理 `codex/p1-6g-pr-validation-merge` 報告分支。
5. 之後才進 P1-6H：CI summary annotations + dedicated lane observation log。

沒有跑測試，因為這次是 roadmap / CTO analysis 文件更新；也沒有 stage 或 commit，避免在目前 noisy worktree 中誤包 unrelated delta。

# CEO 二次審查（針對 2026-05-08 → 2026-05-09 交接）

## 一、昨天成果是否真的推進系統成熟度？

**結論：工程基礎成熟度 ✅ 推進；產品價值成熟度 ❌ 未推進。**

P1-6A → P1-6G 把 Replay Governance CI hardening 整條治理鏈完成（default lane / dedicated DB lane / synthetic fixture / integrity gate / required check / branch protection），這是真實的工程資產，並且建立了第一條「不能 direct push main」的治理紀律，這部分成熟度推進是真的，**不是表面 KPI**。

但是：

```text
昨天交付的全部都是「保護開發流程的工具」
沒有任何一項是「使用者打開頁面會看到的東西」
```

也就是說，工程線在進步，**產品線是停滯的**。
若我們持續在 CI / governance / fixture 上累積，最終會出現「治理品質很高但沒有產品上線」的失衡。

---

## 二、CTO 判斷是否合理？盲點與誤判在哪？

CTO 分析在工程層內部是高品質、邏輯一致的：
- 正確點出 PR #2 與遠端 main 的狀態落差。
- 正確點出 worktree noisy 風險。
- 正確阻擋了「今天又開新治理任務」這種行為。
- 正確保留 dedicated DB lane 在 observation mode。

但 CTO 有三個明確盲點：

```text
盲點 1：產品目標失焦
  CTO 把「protected delivery loop」當成北極星，
  但這只是工程紀律，不是商業目標。
  使用者真正要的是：策略歷史回放頁面上線。

盲點 2：策略涵蓋範圍誤判
  目前 replay_strategy_registry 只有 ACTIVE / RETIRED 兩種狀態，
  使用者要求顯示「上線 / 下線 / 拒絕 / 觀察」全部策略，
  這代表現在的 registry schema 不足以支撐使用者要的頁面。
  CTO roadmap 完全沒有提到這個 gap。

盲點 3：把 Strategy Eval v1 / BFF / Frontend E2E 全部排到 P3
  這在「治理優先」的世界觀下看似合理，
  但若產品目標是策略歷史回放上線，這幾項其中至少
  「策略生命週期狀態源（lifecycle catalog）」與
  「前端完整度驗證（replay UI E2E）」應提前到 P0/P1，
  否則該頁面永遠不會 production-ready。
```

CTO 的 recalibration v1.1 不是錯，而是**在錯的座標系裡是對的**。
今天必須切回正確座標系：產品目標 = 策略歷史回放頁面上線。

---

## 三、CEO 重新校準後的優化方向

```text
今日北極星：
讓策略歷史回放頁面，能顯示「系統上開發過的所有策略」，
針對每一期進行「預測 vs 實際開獎」對照清單。
顯示風格沿用現有歷史預測清單，不重新發明 UX。
```

工程紀律不放掉，但**從主軸降為支援軌道**：

| 軌道 | 角色 | 今日是否擋路 |
|---|---|---|
| 產品軌（策略歷史回放頁面 GA）| 主軸 | 是 |
| 工程紀律軌（PR #2 merge / branch protection）| 支援 | 不擋路就好 |
| 治理擴張軌（CI annotation / dedicated lane promotion）| 暫緩 | 不做 |

具體 P0 範圍重新定義：

```text
P0-A  策略生命週期 SSOT：
      把「上線 / 下線 / 拒絕 / 觀察」狀態納入單一可信來源
      （擴 replay_strategy_registry 或新增 strategy_lifecycle 表）

P0-B  Replay 覆蓋盤點：
      確認所有 lifecycle 狀態的策略在 strategy_prediction_replays 都有對應 row
      （含 REJECTED / OBSERVATION / RETIRED 也要被頁面看見）

P0-C  /api/replay/strategies 與 /api/replay/history 補齊 lifecycle filter
      讓前端可以同時切「上線 / 下線 / 拒絕 / 觀察 / 全部」

P0-D  前端歷史回放頁面 UI 補強：
      lifecycle 狀態 badge、依策略分組、預測 vs 實際對照欄位齊備
      顯示樣式對齊現有歷史預測清單

P0-E  PR #2 走完 protected merge（保留，但不阻擋產品線並行進行）
```

P1（本週）：頁面 E2E smoke、lifecycle drift guard、replay coverage gap report。
P2（下週）：CI summary annotation、dedicated lane promotion evidence、Strategy Eval metadata。
P3：原 P3 不變。

停止規則維持：不做 strategy mining、不做 edge discovery、不寫 production outcome、不 direct push main、不 commit DB binary。

---

## 四、今日最新任務 Prompt（請直接交給下一個執行 agent）

```text
# ROLE
你是 LotteryNew 的 Strategy Replay UI Launch Worker（P0-Replay-UI Executor），向 CTO agent 回報；CTO 向 CEO 回報。

# MISSION
把「策略歷史回放頁面」推到上線可用狀態。
頁面必須能顯示系統上「所有開發過的策略」，
含 上線 / 下線 / 拒絕 / 觀察 四種生命週期狀態，
針對每一期顯示「預測 vs 實際開獎」對照清單。
顯示風格沿用現有歷史預測清單，不重新發明 UX。

本輪不做策略研究、不做 edge discovery、不做 replay 重新生成（除非為補 coverage 缺口），
不修改 main branch protection 設定。

# KNOWLEDGE GATE（強制）
讀取順序必須是：
1. wiki/README.md
2. wiki/system/governance.md
3. wiki/system/validation_gates.md
4. wiki/system/replay_data_hygiene.md
5. memory/lessons.md（若有相關）
其他 root-level *.md / archive / legacy / *_report.md 預設不讀。

# CONTEXT
- 既有 API：lottery_api/routes/replay.py
  - GET /api/replay/strategies
  - GET /api/replay/history
  - GET /api/replay/summary
  - GET /api/replay/runs
- 既有 registry：lottery_api/models/replay_strategy_registry.py
  目前 status 只有 ACTIVE / RETIRED，需擴充。
- 既有頁面：index.html `#replay-section`「🎬 策略歷史回放」。
- DB 表：strategy_replay_runs、strategy_prediction_replays。
- main 已被 branch protection 保護，不得 direct push。
- PR #2（commit 32fc1c8）目前 OPEN / BLOCKED / REVIEW_REQUIRED，required check 已 PASS。

# PRIMARY GOAL（P0 順序，不得跳號）

P0-A  Strategy Lifecycle SSOT
  - 在 replay_strategy_registry（或新增 strategy_lifecycle 表）擴充 status 為：
    ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED
  - 將原本只有 ACTIVE / RETIRED 的對應映射為新枚舉
  - 提供 list_strategies(lifecycle_status=...) 介面
  - 不得在此步寫入 production DB；先用 read-only adapter + 測試 fixture 驗證
  - 產出 schema diff / migration plan（暫不執行 migration）

P0-B  Replay Coverage Audit
  - 對每個 lifecycle 狀態的策略，盤點在 strategy_prediction_replays 是否有對應 row
  - 缺口列為 coverage_gap，輸出 outputs/replay/p0_replay_lifecycle_coverage_<date>.md
  - 不得在這一步觸發 replay generation；只盤點

P0-C  Replay API Lifecycle Filter
  - /api/replay/strategies 增加 lifecycle_status query
  - /api/replay/history 增加 lifecycle_status query
  - 回傳 payload 增加 strategy_lifecycle_status 欄位
  - API 必須維持 read-only / no edge claim disclaimer 不變

P0-D  Frontend 策略歷史回放頁面補強
  - 在 index.html `#replay-section` 加入：
    a) lifecycle filter（全部 / 上線 / 下線 / 拒絕 / 觀察）
    b) 表格欄位：target_draw、target_date、strategy_id、lifecycle badge、
       predicted_numbers、actual_numbers、hit_numbers、hit_count、replay_status、reject_reason
    c) 顯示風格沿用現有歷史預測清單
    d) 保留現有 disclaimer 文案
  - 不引入新前端框架，沿用現有原生 JS 結構

P0-E  Protected Merge Hygiene
  - 不阻擋產品線執行；只在 commit 時遵守：
    新分支命名：codex/p0-replay-lifecycle-ui-<short>
    commit 經 PR / required check / review 流程
    不得 direct push main、不得 force push、不得 admin override

# HARD SCOPE（不得做）
- 不得跑 strategy mining / edge discovery
- 不得改 active strategy state
- 不得修改 branch protection 設定
- 不得 commit lottery_v2.db / *.db / *.db-wal / *.db-shm
- 不得 force push、不得 direct push main
- 不得讓 dedicated DB lane 升級為 required
- 不得改變 Replay API 的 disclaimer 與 read-only 性質
- 不得寫 production outcome、不得改 H6 active strategy

# REQUIRED INSPECTION
工作目錄使用 clean worktree（不要在現有 noisy worktree 寫入新功能）。
先檢查：
  git branch --show-current
  git status --short
  git log --oneline -5

讀取：
  wiki/README.md
  wiki/system/governance.md
  wiki/system/replay_data_hygiene.md
  lottery_api/routes/replay.py
  lottery_api/models/replay_strategy_registry.py
  index.html `#replay-section` 區塊
  outputs/replay/p1_6g_*（若需要參考）

# REQUIRED VALIDATION
每完成一個 P0-x 步驟即執行：
  /Library/Developer/CommandLineTools/usr/bin/python3 \
    scripts/run_replay_ci_default_validation.py
Expected: 維持 57 passed / 32 skipped 等價結果，不退步。

P0-D 完成後執行 replay browser smoke：
  pytest tests/test_replay_browser_smoke.py -v
若無瀏覽器環境，明確標記 SKIPPED 而非假 PASS。

# REQUIRED REPORT
產出：
  outputs/replay/p0_replay_lifecycle_ui_<date>.md
  outputs/replay/p0_replay_lifecycle_coverage_<date>.md
  outputs/replay/p0_replay_lifecycle_schema_diff_<date>.json

報告必須包含：
1. Executive Summary
2. Lifecycle SSOT 擴充內容與 migration plan（未執行）
3. Coverage audit：每彩種 / 每策略 / lifecycle 是否齊備
4. API contract 變更清單
5. Frontend 變更清單
6. Validation results
7. What Was Not Changed（含 active strategy / branch protection / DB 資料）
8. Remaining risks
9. Follow-up tasks（含 P1-replay-ui-e2e、P1-lifecycle-drift-guard）
10. Final marker

# COMMIT RULES
僅允許 commit：
- lottery_api/routes/replay.py（新增 lifecycle filter）
- lottery_api/models/replay_strategy_registry.py（擴枚舉，read 範圍）
- index.html（#replay-section UI 補強）
- outputs/replay/p0_replay_lifecycle_*
不得 commit：
- *.db / *.db-wal / *.db-shm
- 任何 active strategy state 檔
- 任何 unrelated frontend 改動
- 任何 docs/archive 內容變動

Commit 訊息建議：
feat(replay-ui): expose all-lifecycle strategy replay history
docs(replay): record replay lifecycle ui coverage audit

# FINAL REPORT FORMAT
## Completed
## Lifecycle SSOT Schema
## Coverage Audit
## API Contract Diff
## Frontend Changes
## Validation Results
## Files Created / Modified
## Commit / PR Result
## What Was Not Changed
## Remaining Risks
## Follow-up Tasks
## Final Marker

成功完成 P0-A ~ P0-D 並建立 PR：
  P0_REPLAY_LIFECYCLE_UI_READY_FOR_REVIEW

若任一步因環境受限無法完成：
  P0_REPLAY_LIFECYCLE_UI_BLOCKED_<reason>

# PARALLEL PROTECTED FLOW NOTE
PR #2（codex/p1-6g-branch-protection-execution）仍為 open。
本輪不負責 merge PR #2，僅在新分支上獨立進行 P0-Replay-UI 工作。
若 PR #2 在期間被 reviewer approve 並 merge，請 rebase 本輪分支至最新 main。
```

---

**CEO 一句話結論**

```text
昨天工程紀律是真的推進了，但產品線停了一天。
今天回到正軌：策略歷史回放頁面上線是北極星，
工程紀律退為支援軌，PR #2 走完是順手的事，不是主軸。
```