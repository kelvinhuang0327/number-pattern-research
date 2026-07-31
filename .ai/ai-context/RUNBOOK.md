# RUNBOOK — LotteryNew

> template_version: v1.1（2026-07-07）
> bootstrap_mode: BOOTSTRAP Phase 4
> last_reanalysis_update: 2026-07-07
> 原則：指令實測過才算轉正；沒測過的標 `[未驗證]`。Bootstrap 階段只做靜態盤點，不跑測試、不啟動服務、不碰資料。

## 1. 啟動 / 停止

```bash
# [未驗證] 啟動全部服務；會安裝依賴、啟 backend/frontend、寫 pid/log
./start_all.sh

# [未驗證] 停止服務；會 kill process、刪 pid
./stop_all.sh

# [未驗證] Backend health, start_all.sh 記載
curl -s http://localhost:8002/health

# [未驗證] Frontend health, start_all.sh 記載
curl -s http://localhost:8081
```

服務與 port：

| 服務 | 指令來源 | port | 狀態 |
|---|---|---|---|
| Backend FastAPI | `start_all.sh`, `lottery_api/app.py` | 8002 | `[未驗證]` |
| Frontend static server | `start_all.sh` | 8081 | `[未驗證]` |
| Backend dev mode | `lottery_api/README.md` | 5000 | `[未驗證]`；與 root script/app.py 不一致，需後續釐清。 |

log 位置（未執行，僅靜態盤點）：`backend.log`, `frontend.log`。

`start_all.sh` 靜態副作用：

- 可能執行 `pip3 install -r lottery_api/requirements.txt`。
- 以 `nohup "$PYTHON_BIN" app.py` 啟動 backend，寫入 `backend.pid` / `backend.log`。
- 以 `python3 -m http.server 8081` 啟動 frontend，寫入 `frontend.pid` / `frontend.log`。
- 檢查 8002/8081 port；不得在 Bootstrap/Re-Analysis 中執行。

`stop_all.sh` 靜態副作用：

- 讀取並刪除 `backend.pid` / `frontend.pid`。
- 對 pid 與 8002/8081 port process 執行 `kill` / `kill -9`；需另立維運 Task。

## 2. 測試

```bash
# [未驗證] 全部測試；Bootstrap 禁止執行
pytest

# [未驗證] 單一檔案
pytest tests/<file>.py

# [未驗證] DB 相關測試 marker 來自 pytest.ini
pytest -m requires_db

# [未驗證] P523A-P529A replay/evidence dashboard static tests；未執行
pytest tests/test_p523a_stale_snapshot_warning_banner.py
pytest tests/test_p524b_evidence_row_semantics.py
pytest tests/test_p526a_replay_run_status_monitor.py
pytest tests/test_p526b_run_status_scope_denominator.py
pytest tests/test_p527a_replay_freshness_refresh_control.py
pytest tests/test_p528a_public_strategy_filter.py
pytest tests/test_p528b_replay_summary_scope_denominator.py
pytest tests/test_p529_predicted_coverage_ratio.py
pytest tests/test_p529a_replay_runs_lottery_filter.py
```

已知測試陷阱：

- `pytest.ini` 設定 `pythonpath = .`。
- `requires_db` marker 表示有些測試需要 local SQLite replay database fixture。
- 本專案有 canonical DB 風險域；任何需要 DB 的驗證需先確認唯讀/副本策略。
- 上列 P523A-P529A 測試名稱為 replay/evidence dashboard 靜態驗證清單；本次只做靜態盤點，未確認檔案存在、未執行、未宣稱通過。

## 3. 建置 / 部署

```bash
# [未驗證] Backend dependency install, lottery_api/README.md 記載
cd lottery_api
pip install -r requirements.txt

# [未驗證] Backend dev server, lottery_api/README.md 記載
uvicorn app:app --reload --port 5000

# [未驗證] Backend direct run, app.py 使用 8002
cd lottery_api
python app.py
```

Bootstrap 未找到 root `package.json`；repo 內有 `node_modules/` 與靜態前端資產，但本次未做 build/toolchain 實測。
Bootstrap/Re-Analysis 靜態掃描未找到 root `package.json` 或 `vite.config.*`；前端目前以 `index.html` + `src/main.js` + static server 盤點，不以 README 的 Vite/React 描述為準。

## 4. 資料操作

```bash
# [未驗證] CLI 快速預測；預設解析 lottery_api/data/lottery_v2.db，命中 canonical DB gate
python3 tools/quick_predict.py all

# [未驗證] 備份 / snapshot 類腳本；需另行盤點是否唯讀
python scripts/snapshot_replay_db.py

# [未驗證] 匯入 / 回補 / migration 類腳本，全部屬資料寫入 Gate
python scripts/apply_p0_schema_migration.py
python scripts/backfill_replay_history_cutoff.py
python scripts/p2e_controlled_official_draw_import.py
python scripts/p3bc_controlled_draw_import.py
```

⚠️ 資料寫入 Gate：

- `lottery_api/data/lottery_v2.db`：依 Owner decision 視為 canonical DB 高風險禁區。
- `data/*.db`：視為可能 DB 副本或高風險資料。
- `tools/quick_predict.py` 有 readonly helper，但預設 `load_history(..., dry_run=False)` 會透過 `DatabaseManager(db_path=DB_PATH)`；執行前需明確確認 dry-run/唯讀路徑或取得授權。
- migration、seed、匯入、回補、production apply、controlled apply 等指令一律不得在 Bootstrap 執行；需獨立 Task 與具名確認。

## 5. 排程實況

| 作業 | 實際啟動方式（launchd/cron/systemd/手動） | 排程檔位置 | log | 失敗補跑 |
|---|---|---|---|---|
| local dev plist | `[未驗證]` | `com.kelvin.lottery.dev.plist` | `[未驗證]` | `[未驗證]` |
| APScheduler backend jobs | `[未驗證]` startup loads scheduler data | `lottery_api/utils/scheduler.py`（未深讀） | `[未驗證]` | `[未驗證]` |
| replay scheduled monitor docs | `[未驗證]` | `docs/replay/*scheduled*`, `scripts/p123_scheduled_trigger_recheck.py` | `[未驗證]` | `[未驗證]` |

注意：這張表只記 Bootstrap 靜態盤點，不代表「實際在跑」。實查 launchd/cron/systemd 需另立 Task，且不得在 Bootstrap 順手清理。

`com.kelvin.lottery.dev.plist` 靜態內容：`ProgramArguments` 指向 `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/start_all.sh --foreground`，`RunAtLoad=true`，`KeepAlive=true`，stdout/stderr 寫到主 worktree log。實際是否已載入 launchd 未查；不得在本流程觸發或卸載。

## 5.1 Gate Classification

| 類型 | 允許狀態 | Gate |
|---|---|---|
| read-only inspection | 可在 Bootstrap/Re-Analysis 使用 | 僅限 `git status/log/show/diff`、純讀檔、靜態搜尋；不得讀寫 DB 或 runtime 狀態。 |
| static report artifact | 可建議，不自動產生 | 新增 artifact/report 需 Create Manifest 或獨立 Task；不得寫入 `outputs/` / `artifacts/`。 |
| DB / data write Gate | 預設禁止 | `lottery_api/data/lottery_v2.db`、`data/*.db`、migration、seed、匯入、回補需具名授權與獨立 Task。 |
| service / scheduler Gate | 預設禁止 | 不啟動/停止服務，不觸發 launchd/cron/APScheduler，不執行 `start_all.sh` / `stop_all.sh`。 |
| external legacy overlay / copy-in Gate | 預設只讀 | `workspace-AI/LotteryNew/**` 原始檔不得修改；copy-in 只可依核准 manifest，且需保留 source metadata。 |

## 6. 緊急處置

Bootstrap 不執行緊急處置。若服務或資料異常：

1. 先確認當前 branch/worktree 與 dirty status。
2. 不直接跑 `stop_all.sh`，因其會 kill process 與刪 pid；需先確認 pid 來源。
3. DB 異常先建立唯讀快照/證據，不直接 migration 或回補。
4. 涉及 canonical DB 寫入需具名確認該次寫入。

## 7. 常見錯誤速查

| 症狀 | 原因 | 處置 |
|---|---|---|
| Backend port 5000/8002 混淆 | `lottery_api/README.md` 與 `start_all.sh` / `app.py` 記載不同 | 後續 Re-Analysis 釐清實際標準 port。 |
| README 架構描述過時 | root README 說 Flask/Vite；`app.py` 與前端靜態掃描顯示 FastAPI + vanilla/static SPA | production 文件另立 Task 修正；本 RUNBOOK 以靜態掃描為準。 |
| CLAUDE memory path missing | `CLAUDE.md` 指向 `memory/MEMORY.md`，但該檔不存在 | 另立 Task 修正 production 文件或建立治理替代方案。 |
| legacy orchestration wiki stale | `orchestrator/` 目錄不存在，runtime paths 屬禁區且未驗證 | 以 PROJECT_CONTEXT / RUNBOOK 為準，legacy wiki 只作歷史參考。 |
| 測試需要 DB | `pytest.ini` 有 `requires_db` marker，部分測試依賴 local SQLite | 用唯讀/副本策略，必要時升級 Full 2.5。 |
| Bootstrap 期間看到大量 worktree/branch | `worktree-debt` 風險域 | 不清理；另立 Task。 |
| 服務啟動產生 pid/log | `start_all.sh` 設計會寫 runtime 狀態 | Bootstrap 不執行。 |
| ingestion/backfill 腳本看似 dry-run 但可能寫檔 | 命名與副作用需逐檔確認 | 不確定是否唯讀就不執行。 |
