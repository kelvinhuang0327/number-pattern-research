# PROJECT_CONTEXT - Betting-pool

> template_version: v1.0 (2026-07-07)
> 目的：讓任何 AI/人在 10 分鐘內建立對系統的正確心智模型。

## 1. 系統目的

Betting-pool 是 WBC/MLB 量化研究與紙上投注平台，核心工作包含賽事資料/賠率資料蒐集、point-in-time 特徵建構、模型與校準評估、EV/Kelly 紙上建議、CLV/賽後評估、研究報告與 agent/orchestrator 自動化。

目前 owner decision 明確指定：`NO_REAL_BET=true` / paper-only，不涉及真實金流或真實下注。所有投注語彙在本 Profile 下均視為研究、模擬或 paper recommendation。

## 2. 架構總覽

```text
外部資料/API/手動資料
  -> data ingestion scripts / wbc_backend.ingestion / MLB context collectors
  -> data/, reports/, outputs/ 等本地 artifacts
  -> wbc_backend.features / prediction / models / calibration / strategy
  -> paper recommendation, backtest, replay, CLV/evaluation reports
  -> orchestrator / scheduler / launchd / GitHub Actions automation
  -> wiki/docs/report/00-BettingPlan knowledge and evidence layer
```

既有 `wiki/ARCHITECTURE.md` 指出 repo 仍有 root legacy layer 與 `wbc_backend/` 新層並存。`wbc_backend/` 是長期 canonical implementation 方向，但 root `models/`、`strategy/`、`main.py` 等仍有 active import 或相容路徑，不能視為死碼。

## 3. 模組地圖

| 模組/目錄 | 職責 | 狀態 | 備註 |
|---|---|---|---|
| `wbc_backend/` | 新式 WBC/MLB backend：api、pipeline、models、prediction、features、reporting、scheduler、strategy、ingestion、evaluation | active / target canonical | 長期主要方向，但需依任務逐步驗證 |
| `wbc_backend/recommendation/` | paper recommendation contract、provenance contract、learning outcome join、duplicate ticket policy、run line/total scorecards、pybaseball adapters | active / sensitive | P205-P236 後快速擴張；所有 recommendation/source_trace/learning_eligible 變更需 fail-closed gate |
| `models/` | legacy/root 模型實作 | active legacy | 仍不可刪 |
| `strategy/` | legacy/root 策略、Kelly、風控、value detector | active legacy | 與 `wbc_backend/strategy/` 並存 |
| `scripts/` | 任務 runner、研究腳本、資料/報告產生器、orchestrator 操作 | active | 多數可能寫資料或輸出，Bootstrap 不執行 |
| `orchestrator/` | Planner/Worker/CTO review/scheduler/API 等 agent orchestration | active | 搭配 `runtime/agent_orchestrator/` |
| `start_all.sh`, `stop_all.sh`, `scripts/launchd/` | 本機服務啟停、health/smoke check、launchd 管理 | active ops | 啟停/排程變更需破壞性操作 Gate |
| `.github/workflows/` | GitHub Actions 排程與 replay validation | active automation | `daily_update.yml` 會寫 data/reports/outputs 並 push bot branch |
| `data/` | local datasets、snapshots、cache、derived artifacts | active artifact | 預設唯讀 |
| `outputs/` | replay/recommendation/simulation outputs | active artifact | 預設唯讀 |
| `reports/`, `report/` | 研究/評估產物、HTML/CSV/MD/JSON 報告 | active mixed artifacts | `report/` 內有 formatter code，也有大量 artifacts |
| `docs/` | 歷史與架構文件、mode guide、orchestration reports | canonical/historical knowledge | 本次只索引 |
| `wiki/` | repo 既有 canonical knowledge layer | canonical knowledge | `.ai` 不取代，只索引 |
| `00-BettingPlan/` | 研究計畫、phase/task evidence、paper workflow 文檔 | active knowledge/evidence | 本次只索引 |
| `00-Plan/roadmap/` | roadmap、active task、shared agent bootstrap、templates | active governance | 本次限制明確禁止修改 |
| `memory/` | LLM/research todo 或歷史記憶 | active knowledge | 本次只索引 |
| `live/` | live betting 相關程式 | hold / sensitive | MLB live transport HOLD |
| `telegram_bot/` | Telegram bot / notification / command interface | active but sensitive | 啟動需 env/secrets |
| `.ai/` | personal-ai-flow workspace | active workflow metadata | Phase 4 初建；入版控 |

## 4. 資料流

1. 外部來源：MLB Stats API、官方 WBC schedule/roster、odds providers、TSL snapshots、pybaseball、手動/fixture 資料。
2. 擷取/匯入：`scripts/run_mlb_*`、`scripts/build_*`、`wbc_backend/ingestion/`、`data/*crawler*`、GitHub Actions `daily_update.yml`。
3. 本地落地：`data/`、`data/mlb_context*`、`data/mlb_2025`、`data/mlb_2026`、`data/paper_recommendations`、`reports/`、`outputs/`、`runtime/`。
4. 特徵與模型：`wbc_backend/features/`、`wbc_backend/prediction/`、`wbc_backend/models/`、root `models/`。
5. 策略/建議：`wbc_backend/strategy/`、root `strategy/`、paper recommendation outputs。
6. 評估與回饋：CLV、賽後結果、replay、backtest、monthly/shadow tracker reports。

正本/副本狀態尚未在 Bootstrap 深掃到可安全宣告唯一 canonical DB；owner 也明確不勾選 `canonical-db`。因此所有資料寫入、回補、migration、seed、匯入都需另立任務確認。

## 5. 外部依賴

| 依賴 | 用途 | 失效模式 / 注意事項 |
|---|---|---|
| MLB Stats API / `statsapi.mlb.com` | MLB 賽程、boxscore、球員/投手上下文 | rate limit、schema 變動、probable starter 時間點與 PIT 風險 |
| The Odds API / odds providers | 賠率與市場資料 | secrets、條款、rate limit、closing/pregame 時間戳與缺值 |
| TSL snapshots | 台灣運彩/市場可用性與 odds history | v1/v2 crawler 並存，需確認 active integration |
| pybaseball | 歷史 MLB 資料樣本/品質 dashboard | 套件版本固定 `pybaseball==2.2.7`，資料品質與可用性需 gate |
| GitHub Actions | daily data sync、replay validation | `daily_update.yml` 會寫資料與 push bot branch；不可在本地 Bootstrap 觸發 |
| local launchd / daemon scripts | 本機 orchestrator/service 自動化 | 變更、安裝、reload、啟停均需破壞性操作 Gate |
| Telegram / Telethon | bot/通知/指令介面 | 需 env/secrets；不得把 token 寫入 repo |

## 6. 環境與版本

- Python：`claude.md` 寫 Python 3.10+；`ruff.toml` target-version 是 `py39`；GitHub workflows 使用 Python 3.10。
- 主要依賴：pandas、numpy、scipy、scikit-learn、xgboost、lightgbm、catboost、requests、pybaseball。
- 測試：`pytest.ini` 設定 `testpaths = tests`，`pythonpath = .`，排除 archive/quarantine/build/.venv/venv/node_modules。
- 服務 port：`scripts/launchd/common.sh` 預設 backend `8787`、frontend `8788`、proxy `8789`，host `127.0.0.1`。
- Runtime 位置：`runtime/agent_orchestrator/`，包含 run/log/service/frontend 等狀態；本次預設唯讀。
- root `README.md` 在 Phase 4 worktree 的 `HEAD` 不存在；主要專案說明檔是 root `claude.md` 與 `ORCHESTRATOR_README.md`。

## 7. 已知陷阱（Gotchas）

- 本專案目前是 paper-only；任何 real-money、實單、真實下注、provider secret、外部 live transport 都不得從既有語彙推定已授權。
- `wiki/` 是既有 canonical knowledge layer；`.ai` 只做 personal-ai-flow profile/context/runbook，不取代 wiki。
- root legacy 與 `wbc_backend/` 並存，不能因目標方向是 `wbc_backend/` 就刪或改 legacy path。
- `data/`, `logs/`, `runtime/`, `outputs/` 可能被 service/workflow/研究報告使用，預設唯讀。
- `daily_update.yml` 含 scheduled job、資料更新、generated outputs commit/push 行為；不可在 Bootstrap 或一般任務順手觸發。
- `start_all.sh` 會建立 runtime dir、啟動 backend/frontend/proxy 並跑 health/smoke；`smoke_check.sh` 會執行 `agent_orchestrator.py init`，可能寫 runtime。
- `stop_all.sh` 會 kill pid/port owner，屬服務/破壞性操作範圍。
- `data/tsl_crawler.py` vs `data/tsl_crawler_v2.py` 並存，需任務內確認 active import。
- 報告資料夾混合 code、knowledge 與 artifact，不能一概清理。
- worktree debt 已存在，清理永遠另立 Task。
- `.github/skills/analyze-wbc-betting` 與 `.github/skills/update-wbc-data` 包含外部 API 抓取、資料更新、report/data 寫入與投注建議語彙；在 personal-ai-flow 下不構成授權，必須另立任務並通過 data/API/service gates。
- `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md` 是重要治理來源，但內容更新於 2026-06-14，記錄的 HEAD / `origin/main` 仍是 `e7ac8f7`，已落後目前 baseline `ff6c5b2`；讀取時需標註 stale，不可盲信最新狀態。

## 8. Canonical 知識索引（重要：只索引，不複製內容）

| 主題 | 位置 | 狀態 | 一句摘要 |
|---|---|---|---|
| Personal AI workflow prompts | `/Users/kelvin/Kelvin-WorkSpace/personal-ai-flow/` | external canonical | 共用 prompt 與模板來源 |
| Project guidance | `claude.md` | canonical | 技術棧、開發規範、常用指令與 agent 溝通約定 |
| Orchestrator overview | `ORCHESTRATOR_README.md` | canonical/ops | Planner/Worker/CTO/API/DB 與啟動/驗證說明 |
| Mode guide | `docs/MODE_GUIDE.md` | canonical | WBC production、MLB paper-only、spring sandbox 模式界線 |
| Wiki index | `wiki/INDEX.md` | canonical | 宣告 `wiki/` 是 repo 的 human/agent-readable knowledge layer |
| Architecture | `wiki/ARCHITECTURE.md` | canonical | root legacy layer 與 `wbc_backend/` 並存及目標方向 |
| Entrypoints | `wiki/ENTRYPOINTS.md` | canonical | `scripts/run_mode.py`、`main.py`、`wbc_backend/run.py` 用途邊界 |
| Governance | `wiki/GOVERNANCE.md` | canonical | production/research 分界、sample/calibration/significance/stability/market gates |
| Pipelines | `wiki/PIPELINES.md` | canonical | ingestion -> feature -> model -> adjustment -> simulation -> EV -> reporting |
| Research layer | `wiki/RESEARCH_LAYER.md` | canonical | 研究 gate、Brier/EV/window/walk-forward 等方法學 |
| Data sources | `wiki/DATA_SOURCES.md` | canonical | feed、schema、timestamp、coverage 與 QA 約束 |
| Known issues | `wiki/KNOWN_ISSUES.md` | canonical | duplicated code paths、entrypoints、crawler、mixed reports folder |
| Cleanup policy | `wiki/CLEANUP_POLICY.md` | canonical | artifact/knowledge 分類與刪除前 safety gates |
| Active roadmap | `00-Plan/roadmap/` | active governance | roadmap、active task、shared bootstrap、task templates；本次不修改 |
| Agent bootstrap state | `00-Plan/roadmap/agent_bootstrap/` | active governance（部分 stale） | Shared agent bootstrap、task templates、current state；`CURRENT_STATE.md` 仍停在 2026-06-14 / `e7ac8f7` |
| Cursor project rules | `.cursorrules`, `.cursor/rules/` | tool guidance | 平台核心、WBC betting、stats/model、Telegram bot 規範；只索引，不取代 personal-ai-flow gates |
| GitHub skills | `.github/skills/analyze-wbc-betting/`, `.github/skills/update-wbc-data/` | tool guidance / high-risk | 內含外部 API、資料寫入、TSL/odds 更新與投注建議流程；執行需任務授權 |
| Betting plan evidence | `00-BettingPlan/` | active evidence | 研究 phase/task 文檔與決策證據 |
| Historical docs | `docs/` | canonical/historical | 架構、orchestration、feature repair、reference、reports |
| Memory todo | `memory/todo.md` | active memory | WBC 2026 strategy governance/optimization plan 與 gate snapshot |

## 9. Freshness / Staleness Notes

| 項目 | 狀態 |
|---|---|
| `.ai` Bootstrap commit | `143b2c86daab40c57ae372488a5d511a44bf6332` |
| current baseline commit | `ff6c5b29c1158e172b265d357eda82003a3b5609` |
| stale governance source | `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md` 更新於 2026-06-14，記錄 HEAD / `origin/main` = `e7ac8f7d...`，落後目前 baseline |
| commit delta since `e7ac8f7` | PR #27-P236/P205-P236 系列進入 main，包含 provenance hardening、learning guard、duplicate-ticket dry-run、pybaseball/open-source data probes、PIT leakage audit、run line/total scorecards/backtest explorer |
| current `.ai` stance | `.ai` 是 personal-ai-flow 摘要層；若 roadmap/CURRENT_STATE 與 git reality 衝突，以實際 git 狀態為準並在 Handoff 建議修正 governance 文件 |

## 10. P205-P236 摘要（RE-ANALYSIS 補掃）

| 範圍 | 摘要 | `.ai` 影響 |
|---|---|---|
| P205A | 新增 versioned recommendation provenance contract，`source_trace` 缺欄位或 legacy eligibility fail-closed | `wbc_backend/recommendation/` 應列為敏感模組；source_trace/learning_eligible 變更需 Gate |
| P205B | 新增 learning outcome join guard，要求 stable identity、有效 provenance、observed market odds、prediction_as_of_utc 早於 result timestamp | 學習 eligibility 不可由報告語彙推定，需合約證據 |
| P206A | duplicate-ticket dry-run policy，描述性 replay，不 mutation scheduler/evaluator/leaderboard | duplicate suppression/票券邏輯屬敏感 paper workflow |
| P207A-P223A | local retrain、scorecard dashboard、open-source dependency/pybaseball probes、historical sample/evaluation artifacts | 大量 runner/build scripts 會生成 `report/` artifacts；RUNBOOK 需標 `[未驗證]` 與 report artifact Gate |
| P224A | PIT feature contract leakage audit | 加強 PIT / data-provenance / stats-methodology gate |
| P226A-P236A | run line、total、robustness、feature ablation、final 2025 backtest package、backtest explorer | 新市場 scorecards 仍是 paper/replay research，不是 production betting 或 EV/Kelly unlock |

## 11. 變更紀錄

| 日期 | 模式 | 摘要 |
|---|---|---|
| 2026-07-07 | BOOTSTRAP | 初版 `.ai` workspace：依 owner decisions 建立 Profile、Context、Runbook 與 Memory 首筆；未執行測試、服務、排程、資料匯入或外部 API。 |
| 2026-07-07 | RE-ANALYSIS | 補標 baseline/staleness、P205-P236 摘要、recommendation/provenance 敏感模組、skill/API/data-write gate；未執行測試、服務、排程、資料匯入或外部 API。 |
