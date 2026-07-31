# PROJECT_PROFILE - Betting-pool

> template_version: v1.0 (2026-07-07)
> 本檔是專案差異的唯一住所。共用 prompt 位於 `/Users/kelvin/Kelvin-WorkSpace/personal-ai-flow`。
> 建立來源：personal-ai-flow Bootstrap Phase 4；依 owner decisions 與 repo 靜態盤點建立。

## 1. 基本資料

```yaml
project:
  name: Betting-pool
  type: research / data-pipeline / paper-betting-tool
  description: WBC/MLB 紙上投注與量化研究平台，聚焦統計驗證、資料隔離、模型/市場訊號與研究報告。
  prompts_home: /Users/kelvin/Kelvin-WorkSpace/personal-ai-flow
paths:
  project_path: /Users/kelvin/Kelvin-WorkSpace/Betting-pool
  workspace_path: /Users/kelvin/Kelvin-WorkSpace/Betting-pool/.ai
  canonical_branch: main
stack:
  language: Python 3.10+ per claude.md；ruff target-version = py39；workflow 使用 Python 3.10
  framework: pytest；pandas/numpy/scipy；scikit-learn/xgboost/lightgbm/catboost；FastAPI/orchestrator tooling present
  runtime_notes: Bootstrap / RE-ANALYSIS 只做靜態盤點；服務、排程與資料寫入指令不可在知識更新流程執行；production_ready=false；diagnostic_only=true
commands:
  test: pytest tests/ [未驗證]
  test_single: pytest tests/<file>.py [未驗證]
  run: 見 RUNBOOK；啟動、排程、資料匯入、回補與 migration 均需任務授權
  build: N/A
freshness:
  last_bootstrap: 2026-07-07
  last_reanalysis: 2026-07-07
  last_analysis: N/A
  last_verified: 2026-07-07
  baseline_commit: ff6c5b29c1158e172b265d357eda82003a3b5609
  bootstrap_commit: 143b2c86daab40c57ae372488a5d511a44bf6332
research_governance: 研究/回測任務需遵守 wiki/GOVERNANCE.md、wiki/RESEARCH_LAYER.md、wiki/PIPELINES.md 與 docs/MODE_GUIDE.md；工程變更才走 personal-ai-flow 2.5
operating_mode:
  paper_only: true
  no_real_bet: true
  production_ready: false
  diagnostic_only: true
```

## 2. 風險域宣告（risk_domains）

```yaml
risk_domains:
  - stats-methodology
  - market-data-api
  - data-ingestion
  - scheduled-jobs
  - timezone-date
  - compliance-disclaimer
  - worktree-debt
  - data-provenance
  - secrets-hygiene
  - task-authorization
not_selected_risk_domains:
  - real-money
  - settlement-core
  - bet-limits-riskcontrol
  - trading-execution
  - canonical-db
  - backtest-lookahead
```

## 3. 硬 Gate（hard_gates）

```yaml
hard_gates:
  - MLB live transport HOLD：不得自動存取或啟用 MLB live transport；如需解除，必須另立 Task 並取得具名授權。
  - PAPER_ONLY：預設 `NO_REAL_BET=true`；目前不涉及真實金流或真實下注。
  - data/logs/runtime/outputs 預設唯讀：未取得該任務具名授權前，不得寫入、回補、清理或重建。
  - 排程與服務變更需破壞性操作 Gate：launchd、cron、GitHub Actions、daemon、service start/stop/reload 皆需逐項確認。
  - 防洩漏 / PIT 資料隔離：所有預測、回測、特徵、賠率與結果 join 必須維持 point-in-time，禁止使用未來資訊。
  - 部署門檻不可由 AI 放寬：sample、Brier/calibration、significance、stability、EV/ROI 等 gate 只可由 owner 明確決策調整。
  - 研究任務授權句不可跨任務繼承：一次授權僅限同一任務、同一範圍。
  - worktree / branch / stash 清理永遠另立 Task：不得在 Bootstrap 或其他任務順手清理。
  - secrets-hygiene：不得把 API key、token、cookie、私人 URL 或 provider secret 寫入 repo、任務文件或報告。
  - task-authorization：資料寫入、排程觸發、服務啟動、外部 API 抓取、root url 處理與真實 provider 使用都需明確任務授權。
  - persistent governance：no DB write、no live/paid provider call、no production betting、no registry mutation、no controlled apply、no EV/CLV/Kelly unlock、no strategy-weight/champion auto-mutation。
  - production_ready=false / diagnostic_only=true：任何報告、推薦列、scorecard、runner 或 dashboard 不得被描述為 production-ready；解除需 owner 明確授權與獨立 review。
  - fail-closed provenance：涉及 recommendation、source_trace、learning_eligible、game-specific provenance、outcome join 或 duplicate-ticket policy 的任務，一律至少 Standard 2.5；命中資料/模型/學習 eligibility 時升級 Full 2.5。
```

## 4. 禁區（do_not_touch）

```yaml
do_not_touch:
  - path: data/
    reason: 資料與研究/執行產物；Bootstrap 與一般工程任務預設唯讀。
    exception: 僅具名授權的資料任務可寫入，且需記錄來源、時間、hash/行數與回滾策略。
  - path: logs/
    reason: runtime log；不可在 Bootstrap 清理或改寫。
    exception: 維運任務具名授權。
  - path: runtime/
    reason: orchestrator 執行狀態、pid、log、DB 與產物；含服務副作用。
    exception: 維運任務具名授權，且需先停止/隔離風險。
  - path: outputs/
    reason: replay、recommendation、simulation 等輸出；可能被 workflow 或報告引用。
    exception: 產物再生或清理任務具名授權。
  - path: 00-Plan/roadmap/
    reason: roadmap/active task/agent bootstrap 治理文件；本次 Bootstrap 明確禁止修改。
    exception: roadmap 任務具名授權。
  - path: 00-BettingPlan/
    reason: 研究計畫與證據記錄；不得順手整理。
    exception: 研究任務具名授權，優先追加而非覆寫。
  - path: wiki/
    reason: repo 既有 canonical knowledge layer；本次 `.ai` 只索引，不取代。
    exception: 文件維護任務具名授權。
  - path: docs/
    reason: 歷史與架構文件；本次 Bootstrap 禁止修改。
    exception: 文件維護任務具名授權。
  - path: claude.md
    reason: 既有 agent/project guidance；本次 Bootstrap 禁止修改。
    exception: agent guidance 任務具名授權。
  - path: README.md
    reason: 若後續出現或恢復 root README，Bootstrap 不修改。
    exception: 文件任務具名授權。
  - path: .github/workflows/
    reason: 排程與 CI 可能寫入資料、outputs 與 bot branch；不可在一般任務順手改。
    exception: CI/排程任務具名授權。
  - path: deploy/
    reason: launchd/service 操作面；可能影響本機服務。
    exception: 維運任務具名授權。
  - path: url
    reason: root url 檔已完成 secrets triage 且本次限制明確禁止處理。
    exception: secrets-hygiene 任務具名授權。
  - path: report/
    reason: 混合 code、Markdown、JSON、CSV、HTML 等研究/評估 artifacts；大量檔案由 runners 生成。
    exception: 報告產物任務具名授權，需明列輸出檔 allowlist。
  - path: reports/
    reason: runtime/research outputs；可能被 daily scheduler 或歷史證據引用。
    exception: 報告產物任務具名授權，需明列輸出檔 allowlist。
  - path: research/
    reason: research registry、settlement ingestion、postmortem、patch snapshots；可能影響研究證據鏈。
    exception: 研究任務具名授權，需資料來源與可重現證據。
  - path: .env*
    reason: secrets-hygiene；不得讀寫或提交本機憑證。
    exception: 僅可在 secrets-hygiene 任務中檢查是否被追蹤，不輸出內容。
  - path: .cursor/rules/
    reason: 既有工具/agent 規則；改動會影響模型行為與任務邊界。
    exception: agent governance 任務具名授權。
  - path: .github/skills/
    reason: skill 內含會抓外部 API、寫 data/report 的流程說明；改動需同步 personal-ai-flow gate。
    exception: skill governance 任務具名授權。
```

## 5. 已勾選風險域檢查重點

| 風險域 | 本專案檢查重點 |
|---|---|
| `stats-methodology` | 時序切片、baseline 對齊、sample size、Brier/calibration、rolling stability、seed 與可重現證據。 |
| `market-data-api` | provider 條款、rate limit、timestamp、快取落地、免費源缺值與品質陷阱。 |
| `data-ingestion` | 匯入來源、重複匯入防護、回補路徑、audit log、fixture/source 分界。 |
| `scheduled-jobs` | GitHub Actions、launchd、daemon 實況與文件一致性；變更需 Gate。 |
| `timezone-date` | 台灣時間、UTC、MLB game date、opening/decision/pregame/closing timestamp 單調性。 |
| `compliance-disclaimer` | 對外輸出需標示研究/娛樂用途，非投資或投注建議。 |
| `worktree-debt` | 既有 worktree/branch/stash 殘留只盤點、不清理；清理永遠另立 Task。 |
| `data-provenance` | 每份分析可追溯來源、抓取時間、raw timestamp、hash/行數與轉換步驟。 |
| `secrets-hygiene` | 不把 API key、token、cookie、私人 URL 或 provider secret 寫入 repo/任務文件/報告。 |
| `task-authorization` | 授權句必須指出任務、路徑、資料源、寫入/啟動/外部存取範圍；不可跨任務繼承。 |

## 6. 專案類型補充

本專案目前採 paper-only 研究定位，owner 已明確 `real-money: NO`，因此不勾選 `real-money`、`trading-execution`、`settlement-core`。若未來改為真實下注或實單交易，必須先更新本 Profile，且相關任務自動升級 Full 2.5＋獨立 review。
