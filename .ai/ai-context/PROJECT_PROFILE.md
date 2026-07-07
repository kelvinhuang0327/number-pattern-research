# PROJECT_PROFILE — LotteryNew

> template_version: v1.0（2026-07-07）
> bootstrap_mode: BOOTSTRAP Phase 4
> bootstrap_base: `ac8ff5a54fb90c04c9d0ed201b6b82e2e836a783`
> 本檔是專案差異的唯一住所；共用 prompt（`PERSONAL_*`）不寫死專案細節。

---

## 1. 基本資料

```yaml
project:
  name: LotteryNew
  type: research-data-pipeline-web-app
  description: 樂透資料、策略研究、回測與預測 API / 靜態前端整合專案。
  prompts_home: /Users/kelvin/Kelvin-WorkSpace/personal-ai-flow
paths:
  project_path: /Users/kelvin/Kelvin-WorkSpace/LotteryNew
  workspace_path: /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.ai
  bootstrap_worktree_path: /Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/ai-flow-bootstrap
  canonical_branch: main
  current_branch: ai-flow/bootstrap
git:
  baseline_commit: ac8ff5a54fb90c04c9d0ed201b6b82e2e836a783
  bootstrap_commit: 1594987cc73b802b64e89433c9da397e18039461
  origin_main_at_reanalysis: 18c0d25
status:
  production_ready: false
  diagnostic_only: true
stack:
  language: Python, JavaScript, HTML/CSS
  framework: FastAPI backend; static frontend served by Python HTTP server; research scripts
  runtime_notes: Bootstrap only performed static inspection. `start_all.sh` uses `PYTHON_BIN=${PYTHON_BIN:-/usr/bin/python3}`, writes pid/log files, may install requirements, and starts services; do not run during Bootstrap.
commands:
  test: pytest
  test_single: pytest <path>
  run: ./start_all.sh
  stop: ./stop_all.sh
  quick_predict: "[未驗證] python3 tools/quick_predict.py <lottery|all> [bets]；預設會解析 lottery_api/data/lottery_v2.db，dry-run/read-only 使用方式需逐次確認"
  build: N/A
freshness:
  last_bootstrap: 2026-07-07
  last_analysis: 2026-07-07
  last_verified: 2026-07-07
  last_reanalysis_update: 2026-07-07
research_governance: 研究線維持既有治理流程與文件脈絡（例如 00-Plan/roadmap、docs/replay、memory/、研究報告與任務證據）。personal-ai-flow 2.5 只接工程任務；不得自動取代既有研究治理。
```

## 2. 風險域宣告（risk_domains）

```yaml
risk_domains:
  - data-ingestion
  - canonical-db
  - scheduled-jobs
  - timezone-date
  - stats-methodology
  - compliance-disclaimer
  - worktree-debt
```

## 3. 硬 Gate（hard_gates）

```yaml
hard_gates:
  - canonical DB 寫入需使用者具名確認該次寫入；分析/回測一律使用唯讀連線或副本。
  - `tools/quick_predict.py` 等 CLI 若會接觸 `lottery_api/data/lottery_v2.db`，需先確認 dry-run/唯讀連線或取得 canonical DB 寫入具名授權。
  - replay/evidence dashboard 相關變更只能在授權任務中修改；不得由 Bootstrap/Re-Analysis 順手改 production UI/API。
  - replay/evidence dashboard static tests 未實際執行並留下證據前，不得宣稱該 dashboard 可用或已驗證。
  - replay/evidence dashboard 的分母、scope、freshness、filter 行為屬使用者可見語義，不得由 AI 自行改動；需核准計畫與驗證證據。
  - tests / services / scheduler / DB writes 均需明確授權；未授權時只允許靜態讀取與文件更新。
  - legacy overlay 內容不得當 canonical；與 PROJECT_CONTEXT / RUNBOOK 衝突時，以 PROJECT_CONTEXT / RUNBOOK 為準。
  - worktree / branch / stash 清理一律另立 Task，需隔離優先與逐項具名確認；不得併入 Bootstrap 或順手處理。
  - DB / pid / runtime / outputs / artifacts 不得由 Bootstrap 觸碰；涉及資料寫入、migration、seed、匯入、回補皆需另立 Task 並通過資料寫入 Gate。
  - 研究線維持既有治理流程；personal-ai-flow 2.5 只接工程任務，不自動取代研究流程。
  - G3 前不得修改 production code；production code 定義為 repo 內 `.ai/` 以外任何檔案。
  - Bootstrap 只允許建立已核准 Create Manifest 中的 `.ai/**` 新檔；不得執行 Update Manifest、External / Destructive Suggestions。
  - 不啟動服務、不跑測試、不觸發排程、不執行資料匯入 / migration / 回補。
```

## 4. 禁區（do_not_touch）

```yaml
do_not_touch:
  - path: lottery_api/data/lottery_v2.db
    reason: canonical DB / 正本資料高風險；任何 AI workflow 階段不得推定可寫。
    exception: 僅在獨立 Task 中經使用者具名確認該次寫入。
  - path: data/*.db
    reason: 本地資料庫與可能副本，Bootstrap 不得讀寫變更。
    exception: 僅在獨立 Task 中以唯讀或副本方式處理；寫入需具名確認。
  - path: "*.pid"
    reason: runtime process 狀態檔；AI workflow 不得未授權啟停服務或清理 pid。
    exception: 獨立維運 Task 並逐項確認。
  - path: runtime/
    reason: runtime 狀態與輸出禁區；排程/服務實況需另立維運 Task。
    exception: 獨立 Task。
  - path: outputs/
    reason: 研究與執行輸出禁區；不得由 Bootstrap/Re-Analysis 清理或改寫。
    exception: 獨立 Task。
  - path: artifacts/
    reason: 既有任務證據與 artifact 禁區；不得由 Bootstrap/Re-Analysis 清理或改寫。
    exception: 獨立 Task。
  - path: worktree / branch / stash
    reason: agent 殘留債清理具破壞性與歷史追溯風險。
    exception: 獨立清理 Task，逐項具名確認。
  - path: task/p273a dirty files (25 items)
    reason: 當前工作區髒檔不納入 Bootstrap。
    exception: 本次無例外。
  - path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/**
    reason: repo 外 legacy overlay 原始檔；本次只讀、只複製，來源原地保留。
    exception: 本次無例外；不得改、不刪、不改名。
  - path: /Users/kelvin/Kelvin-WorkSpace/personal-ai-flow/**
    reason: 共用 prompt 原始檔；本次只讀。
    exception: 本次無例外。
  - path: README.md
    reason: 使用者明示 Bootstrap 不修改。
    exception: 另立 Task。
  - path: CLAUDE.md
    reason: 使用者明示 Bootstrap 不修改。
    exception: 另立 Task。
  - path: lottery_api/CLAUDE.md
    reason: 使用者明示 Bootstrap 不修改。
    exception: 另立 Task。
  - path: memory/
    reason: 既有治理/記憶資料；Bootstrap 不修改。
    exception: 另立 Task。
  - path: docs/
    reason: 既有文件體系；Bootstrap 不修改。
    exception: 另立 Task。
  - path: wiki/
    reason: 既有 wiki；Bootstrap 不修改。
    exception: 另立 Task。
  - path: 00-Plan/
    reason: 既有 roadmap / governance；Bootstrap 不修改。
    exception: 另立 Task。
```

---

## 5. 風險域選單（附檢查清單）

本專案目前勾選：`data-ingestion`, `canonical-db`, `scheduled-jobs`, `timezone-date`, `stats-methodology`, `compliance-disclaimer`, `worktree-debt`。

### `data-ingestion` — 外部資料匯入
- [ ] 資料來源是否官方/穩定？來源異常（改版、擋擋、缺期）時的偵測與手動匯入備援為何？
- [ ] 重複匯入防護：唯一鍵約束？永不覆寫或明確衝突處理？
- [ ] 歷史回補路徑存在且與日常匯入走同一驗證？
- [ ] 匯入有稽核紀錄（log/ledger）？

### `canonical-db` — 正本資料庫 ⛔（寫入面）
- [ ] 正本路徑唯一且明確；其他副本已盤點並標註「非正本」？
- [ ] 任何寫入需具名確認；分析/回測一律唯讀連線或副本？
- [ ] 有基線（hash/行數/期數）可偵測意外變更？
- [ ] 備份與還原步驟寫在 RUNBOOK？

### `scheduled-jobs` — 排程與背景作業
- [ ] 「文件說在跑的」與「實際在跑的」一致？（launchd/cron/systemd 實查）
- [ ] 失敗時看得到（log 位置、告警）？失敗補跑步驟？
- [ ] 是否存在幽靈自動化（程式引用不存在的 hook/腳本）？

### `timezone-date` — 時區與日期
- [ ] 時區處理是否集中？跨日/夏令時間邊界？
- [ ] 特殊曆制轉換（民國年、交易日曆、休市日）在哪處理？
- [ ] 日期欄位型別與排序正確（字串排序陷阱）？

### `stats-methodology` — 統計/回測方法
- [ ] 訓練/驗證切片嚴格用過去資料（不偷看未來）？
- [ ] 基準（baseline）與比較對象對齊（同注數/同成本/同期間）？
- [ ] 固定 seed、可重現、報告含樣本數與變異？
- [ ] 結論有多窗口/樣本外驗證，避免幸運窗口？

### `compliance-disclaimer` — 合規聲明
- [ ] 所有分析結論輸出附「僅供研究/娛樂，非投資或投注建議」？
- [ ] README 與對外介面含免責聲明？
- [ ] 涉及在地法規的功能（如博弈）有明確界線紀錄？

### `worktree-debt` — Agent 殘留債
- [ ] worktree / 本地分支 / stash 數量已盤點？
- [ ] 同層殘留目錄（`<專案>-*`、`<專案>.worktrees/`、時間戳資料夾）已盤點？
- [ ] 清理一律獨立 Task＋隔離優先＋逐項核實（PR/合併證據）後才刪；永不併入 Bootstrap 或其他任務順手做？
