# RUNBOOK — LotteryNew

> template_version: v1.1（2026-07-07）
> bootstrap_mode: BOOTSTRAP Phase 4
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

## 2. 測試

```bash
# [未驗證] 全部測試；Bootstrap 禁止執行
pytest

# [未驗證] 單一檔案
pytest tests/<file>.py

# [未驗證] DB 相關測試 marker 來自 pytest.ini
pytest -m requires_db
```

已知測試陷阱：

- `pytest.ini` 設定 `pythonpath = .`。
- `requires_db` marker 表示有些測試需要 local SQLite replay database fixture。
- 本專案有 canonical DB 風險域；任何需要 DB 的驗證需先確認唯讀/副本策略。

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

## 4. 資料操作

```bash
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
- migration、seed、匯入、回補、production apply、controlled apply 等指令一律不得在 Bootstrap 執行；需獨立 Task 與具名確認。

## 5. 排程實況

| 作業 | 實際啟動方式（launchd/cron/systemd/手動） | 排程檔位置 | log | 失敗補跑 |
|---|---|---|---|---|
| local dev plist | `[未驗證]` | `com.kelvin.lottery.dev.plist` | `[未驗證]` | `[未驗證]` |
| APScheduler backend jobs | `[未驗證]` startup loads scheduler data | `lottery_api/utils/scheduler.py`（未深讀） | `[未驗證]` | `[未驗證]` |
| replay scheduled monitor docs | `[未驗證]` | `docs/replay/*scheduled*`, `scripts/p123_scheduled_trigger_recheck.py` | `[未驗證]` | `[未驗證]` |

注意：這張表只記 Bootstrap 靜態盤點，不代表「實際在跑」。實查 launchd/cron/systemd 需另立 Task，且不得在 Bootstrap 順手清理。

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
| 測試需要 DB | `pytest.ini` 有 `requires_db` marker，部分測試依賴 local SQLite | 用唯讀/副本策略，必要時升級 Full 2.5。 |
| Bootstrap 期間看到大量 worktree/branch | `worktree-debt` 風險域 | 不清理；另立 Task。 |
| 服務啟動產生 pid/log | `start_all.sh` 設計會寫 runtime 狀態 | Bootstrap 不執行。 |
| ingestion/backfill 腳本看似 dry-run 但可能寫檔 | 命名與副作用需逐檔確認 | 不確定是否唯讀就不執行。 |
