# PROJECT_CONTEXT — LotteryNew

> template_version: v1.0（2026-07-07）
> bootstrap_mode: BOOTSTRAP Phase 4
> bootstrap_base: `ac8ff5a54fb90c04c9d0ed201b6b82e2e836a783`
> 目的：讓任何 AI/人在 10 分鐘內建立對系統的正確心智模型。Bootstrap v1 僅做蒸餾與索引；深掃請另行執行 MODE=RE-ANALYSIS。

## 1. 系統目的

LotteryNew 是樂透研究與預測工作區，包含 FastAPI 後端、靜態前端、歷史資料/SQLite、策略研究腳本、回測與 replay governance 文件。README 將專案定位為 statistical research and entertainment purposes only；所有投注/預測結論需保留娛樂/研究免責聲明。

## 2. 架構總覽

```text
外部/歷史開獎資料
  -> ingestion / backfill / replay scripts
  -> SQLite / JSON / artifacts / reports
  -> FastAPI routes under lottery_api/routes
  -> static frontend at index.html / src / public
  -> research and replay reports under docs, outputs, artifacts
```

Bootstrap 只做靜態盤點；尚未確認實際排程、production DB 正本、服務狀態或資料新鮮度。

## 3. 模組地圖

| 模組/目錄 | 職責 | 狀態 | 備註 |
|---|---|---|---|
| `lottery_api/` | FastAPI backend、routes、scheduler、資料/模型工具 | active | `app.py` 註冊 prediction/data/optimization/admin/backtest/replay/ingest 等 routers；啟動會 load scheduler data。 |
| `index.html`, `src/`, `public/` | 靜態前端與 UI assets | active | `start_all.sh` 以 Python HTTP server 服務 8081。 |
| `scripts/` | replay、ingestion、backfill、audit、research 任務腳本 | active / mixed | 多數腳本可能碰 DB 或輸出；Bootstrap 不執行。 |
| `tools/` | active prediction/backtest/maintenance tooling | active / mixed | README 標為 active tools。 |
| `docs/`, `docs/replay/` | 技術文件、回測協議、replay 任務證據與 SOP | canonical | 原地保留，只索引不複製。 |
| `00-Plan/roadmap/` | roadmap、決策、agent bootstrap governance | canonical | 原地保留，只索引不修改。 |
| `memory/` | lessons/todo/research plan template | canonical | 原地保留；Bootstrap 不修改。 |
| `wiki/` | 既有 wiki | canonical / legacy | 原地保留，只索引。 |
| `data/`, `lottery_api/data/` | DB / JSON / ingest log / data assets | high-risk | 禁區；不得由 Bootstrap 讀寫變更。 |
| `outputs/`, `artifacts/` | 研究輸出與證據包 | high-risk evidence | 禁區；不得由 Bootstrap 清理或改寫。 |
| `.claude/`, `.agent/` | 工具層設定、skills、commands 與 agent 文件 | active / tool-specific | 原地保留；personal-ai-flow 不取代。 |
| `.ai/` | personal-ai-flow workspace | active | 本次 Bootstrap 新建。 |

## 4. 資料流

資料流目前以靜態資訊判斷：

1. 開獎/歷史資料由 fetcher、ingest routes、scripts 或手動檔案進入。
2. replay / backtest / strategy scripts 消費 SQLite、JSON 或 fixture，產出 reports、outputs、artifacts。
3. FastAPI 後端提供 prediction、data、optimization、backtest、replay、ingest、best-strategy-overview 等 API。
4. 靜態前端呼叫後端 API 呈現 dashboard / replay / prediction 結果。

正本 DB 尚未由 Bootstrap 實證確認；依 Owner decision 先將 `lottery_api/data/lottery_v2.db` 視為 canonical DB 高風險禁區，其他 `data/*.db` 視為可能副本或高風險資料。

## 5. 外部依賴

| 類型 | 來源 | 失效模式 |
|---|---|---|
| Python backend | `lottery_api/requirements.txt`：FastAPI, uvicorn, pandas, numpy, pydantic, APScheduler, Prophet, ML libraries | 安裝時間長、平台相依、版本衝突、啟動時 scheduler load data。 |
| Frontend/static serving | `start_all.sh` 使用 Python HTTP server | 會寫 pid/log，可能與既有 8081 process 衝突。 |
| Lottery data sources | fetcher/ingest/backfill scripts and docs | 官方來源改版、缺期、重複匯入、資料污染。 |
| Local DB/files | SQLite / JSON / artifacts | canonical / 副本界線需另行盤點；寫入需 Gate。 |
| Scheduling | `APScheduler`, `com.kelvin.lottery.dev.plist`, docs/replay scheduled monitor files | 文件與實際 launchd/cron/systemd 狀態可能不一致；Bootstrap 未實查。 |

## 6. 環境與版本

- Python backend dependencies declared in `lottery_api/requirements.txt`.
- `pytest.ini` 設定 `pythonpath = .`，並有 `requires_db` marker。
- `start_all.sh` 預設 `PYTHON_BIN=/usr/bin/python3`，會安裝 requirements、啟動 backend 8002、frontend 8081、寫 `backend.pid` / `frontend.pid` / logs。
- `lottery_api/README.md` 另載開發模式 `uvicorn app:app --reload --port 5000`；與 `app.py` / `start_all.sh` 的 8002 有差異，需在後續任務釐清。

## 7. 已知陷阱（Gotchas）

- Bootstrap 不得跑 `start_all.sh`：它會安裝依賴、啟服務、寫 pid/log。
- Bootstrap 不得跑 `stop_all.sh`：它會 kill process、刪 pid。
- `lottery_api/app.py` startup event 會呼叫 `scheduler.load_data()`；啟動服務可能讀取資料或觸發 runtime 行為。
- `pytest` 可能包含 DB fixture / local SQLite 依賴；本次不跑測試。
- `origin/main` 在 2026-07-07 已不同於 Phase 1-3 基準；本次依 Owner decision 從 commit `ac8ff5a` 建立 branch/worktree。
- repo 內存在大量 historical reports / outputs / artifacts；Bootstrap 不清理、不分類處置到破壞性操作。
- 研究線與 replay governance 已有既有流程；personal-ai-flow 2.5 只接工程任務，不自動替代研究治理。
- 時區/日期、民國年或 draw period 排序可能影響資料正確性；命中相關任務需升級審查。

## 8. Canonical 知識索引（重要：只索引，不複製內容）

| 主題 | 位置 | 狀態 | 一句摘要 |
|---|---|---|---|
| 專案總覽 | `README.md` | canonical | 專案入口、active tools、免責聲明。 |
| Backend API | `lottery_api/README.md` | canonical / partially stale | FastAPI API 與啟動方式；port 與 root script 需後續釐清。 |
| 專案工作規範 | `CLAUDE.md`, `lottery_api/CLAUDE.md` | canonical | 既有 tool/agent 指令，本次不修改。 |
| Roadmap / governance | `00-Plan/roadmap/` | canonical | 決策、active task、agent bootstrap 與 roadmap。 |
| Replay docs | `docs/replay/` | canonical evidence | replay/backfill/monitoring 任務證據與 SOP。 |
| Research docs | `docs/`, root reports, `research/`, `analysis/` | canonical / mixed freshness | 研究報告、策略分析、方法文件。 |
| Memory | `memory/` | canonical（只可依既有治理追加） | lessons、todo、research plan template。 |
| Tool settings | `.claude/`, `.agent/` | tool-specific canonical | Claude commands/skills/settings 與 agent 文件。 |
| Legacy overlay context | `.ai/ai-context/LEARNING_REVIEW_REQUIRED.md`, `.ai/ai-context/ORCHESTRATION_EXECPLAN.md` | migrated legacy copy | 從 repo 外 workspace-AI copy-in；檔頭附來源與 hash。 |
| Legacy overlay wiki | `.ai/ai-wiki/**` | migrated legacy copy | 舊 overlay 模組/流程文件；標註 stale warning。 |
| Legacy overlay zerospec | `.ai/ai-zerospec/**` | migrated legacy copy | 舊 orchestration 原型/規格程式；標註 stale warning。 |
| Legacy overlay memory | `.ai/ai-memory/legacy/**` | migrated legacy copy | 舊 MEMORY_LOG / MEMORY_SYSTEM；為避免覆寫新核心 log，放入 legacy 子目錄。 |

## 9. 變更紀錄

| 日期 | 模式 | 摘要 |
|---|---|---|
| 2026-07-07 | BOOTSTRAP | 依 Create Manifest 新建 `.ai/**` 骨架、Profile、Context、Runbook、Memory Log，並 copy-in legacy overlay。 |
