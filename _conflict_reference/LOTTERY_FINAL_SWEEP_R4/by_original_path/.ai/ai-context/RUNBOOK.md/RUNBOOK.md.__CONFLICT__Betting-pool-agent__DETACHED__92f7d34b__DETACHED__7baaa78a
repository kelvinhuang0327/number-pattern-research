# RUNBOOK - Betting-pool

> template_version: v1.1 (2026-07-07)
> 原則：指令實測過才算轉正；沒測過的標 `[未驗證]`。Bootstrap 階段只做靜態盤點與唯讀驗證，不跑測試、不啟動服務、不碰資料。

## 0. Bootstrap 驗證狀態

本 RUNBOOK 於 Bootstrap Phase 4 建立。依本次限制：

- 未跑測試。
- 未啟動服務。
- 未觸發排程。
- 未執行資料匯入、migration、seed、回補。
- 未寫入 `data/`, `runtime/`, `logs/`, `outputs/`。
- 未處理 root `url` 檔。
- 未 push、未 merge。

以下指令均為靜態盤點結果，除明確標示已執行的 git/讀檔查詢外，全部視為 `[未驗證]`。

## 0.1 Gate 分類

| 分類 | 可否在一般任務直接執行 | 判定 |
|---|---|---|
| read-only git/file inspection | 可在任務範圍內執行 | `git status`, `git log`, `git diff --name-only`, `sed`, `rg`, `find` 等純讀查詢 |
| report artifact generation | 需具名授權 | 任何會寫 `report/`, `reports/`, `outputs/` 的 runner/build script |
| data write | 需資料寫入 Gate | 任何會寫 `data/`, `research/`, DB、registry、JSONL/CSV snapshot 的指令 |
| service / scheduler | 需破壞性操作 Gate | `start_all.sh`, `stop_all.sh`, launchd, daemon, GitHub Actions workflow_dispatch |
| external API / provider | 需外部存取授權與 secrets-hygiene | MLB/StatsAPI、The Odds API、TSL crawler、Telegram、pybaseball live download、任何 provider key |

## 1. 啟動 / 停止

```bash
# [未驗證] user-facing mode dashboard
python scripts/run_mode.py

# [未驗證] WBC mode
python scripts/run_mode.py --mode wbc

# [未驗證] MLB paper-only modes
python scripts/run_mode.py --mode mlb-paper
python scripts/run_mode.py --mode mlb-benchmark
python scripts/run_mode.py --mode mlb-alpha

# [未驗證] report-only view
python scripts/report_center.py

# [未驗證] backend pipeline examples
python -m wbc_backend.run
python -m wbc_backend.run --train
python -m wbc_backend.run --backtest

# [未驗證] local services；需服務/排程 Gate
./start_all.sh
./start_all.sh --foreground

# [未驗證] stop local services；可能 kill pid/port owner，需破壞性操作 Gate
./stop_all.sh
```

服務與 port：

- `scripts/launchd/common.sh` 預設 `SERVICE_HOST=127.0.0.1`
- backend port `8787`
- frontend port `8788`
- proxy port `8789`

log / runtime 位置：

- `runtime/agent_orchestrator/run/`
- `runtime/agent_orchestrator/logs/launchd/`
- `runtime/agent_orchestrator/logs/service/`
- `runtime/agent_orchestrator/frontend/`

啟停注意：

- `start_all.sh` 會建立 runtime dirs、啟動 backend/frontend/proxy、跑 health/smoke。
- `scripts/launchd/smoke_check.sh` 會執行 `scripts/agent_orchestrator.py init` 與 `summary`，可能寫 runtime。
- `stop_all.sh` 會停止 pid file 並 kill port owner，必須逐項具名授權。

## 2. 測試

```bash
# [未驗證] 全部測試
pytest tests/

# [未驗證] 單一測試檔
pytest tests/<file>.py

# [未驗證] root orchestrator functional test；可能需啟動服務或寫 runtime，執行前需確認
python test_orchestrator.py

# [未驗證] shell parity test
./test_parity.sh
```

測試設定：

- `pytest.ini`：`testpaths = tests`，`pythonpath = .`
- 排除：`archive quarantine build .git .venv venv node_modules`
- `ruff.toml`：line-length 100，target-version `py39`
- `requirements.txt`：含 `pybaseball==2.2.7`；pybaseball 相關指令仍視為 external/data-source sensitive，需任務授權。

## 3. 建置 / 部署

```bash
# N/A：目前未盤點到傳統 build 指令
```

部署/自動化相關：

- `.github/workflows/daily_update.yml`：每天 UTC 00:00；會安裝依賴、跑 MLB daily scheduler、WBC data update、寫入 data/reports/outputs，並 push `bot/daily-wbc-data`。
- `.github/workflows/replay_default_validation.yml`：pull_request/push/main/workflow_dispatch；會跑 replay default validation 並上傳 `outputs/replay/` artifact。
- `deploy/launchd-orchestrator/*.sh` 與 `scripts/launchd/*.sh`：本機 launchd/service 管理。

規則：

- workflow、launchd、daemon、scheduler 變更一律需破壞性操作 Gate。
- Bootstrap 不觸發任何 workflow 或本機排程。

## 4. 資料操作

```bash
# [未驗證] 多數 build/run/ingest 類腳本都可能寫 data/report/outputs/runtime
# 執行前必須先讀腳本並建立任務級 allowlist。

# [未驗證] examples from static inventory；資料寫入 Gate
python scripts/legacy_entrypoints/fetch_wbc_all_players.py
python data/live_updater.py
python scripts/run_mlb_daily_scheduler.py --date YYYY-MM-DD --mode today --source fixture --limit 15 --run-paper-recommendation true --run-paper-evaluation true
```

資料寫入 Gate：

- `data/`, `outputs/`, `reports/`, `report/`, `runtime/`, `research/patch_snapshots/`, `research/postmortem_reports/` 寫入前需任務授權。
- 匯入、回補、migration、seed、資料修復、artifact regeneration 不得混入一般 code 任務。
- 必須記錄來源、抓取時間、provider/raw timestamp、hash/行數、輸出路徑與 rollback/隔離策略。

正本資料位置：

- Bootstrap 尚未深掃至可宣告唯一 canonical DB。
- 目前 `canonical-db` 未勾選；如後續發現正本 DB 或唯一 production data store，需先更新 Profile。

## 4.1 Research / Scorecard Runner Inventory

以下為 RE-ANALYSIS 靜態盤點到的新增或高風險 runner/build scripts。全部 `[未驗證]`，且多數會寫 `report/`、`reports/`、`outputs/` 或讀取外部/資料來源；不得在 Bootstrap / RE-ANALYSIS 直接執行。

```bash
# [未驗證] report artifact Gate
python scripts/run_mlb_prediction_workflow_snapshot.py
python scripts/run_mlb_local_retrain_scorecard.py
python scripts/run_mlb_duplicate_ticket_dry_run.py
python scripts/run_mlb_run_line_total_scorecard.py
python scripts/run_mlb_total_calibration_scorecard.py
python scripts/run_mlb_run_line_robustness_scorecard.py
python scripts/run_mlb_run_line_feature_ablation_scorecard.py
python scripts/run_mlb_run_line_backtest_explorer.py

# [未驗證] report artifact Gate / historical data Gate
python scripts/build_historical_sample_feature_table.py
python scripts/build_historical_feature_baseline_evaluation.py
python scripts/build_historical_time_split_baseline_evaluation.py
python scripts/build_historical_time_split_error_dashboard.py
python scripts/build_historical_baseline_error_dashboard.py
python scripts/build_historical_evaluation_evidence_index.py

# [未驗證] external/data-source Gate；pybaseball dependency pinned in requirements.txt
python scripts/audit_pybaseball_dependency.py
python scripts/build_pybaseball_historical_sample_smoke.py
python scripts/build_pybaseball_multidate_sample_pack.py
python scripts/build_pybaseball_sample_quality_dashboard.py
python scripts/build_pybaseball_multidate_quality_dashboard.py

# [未驗證] governance/report artifact Gate
python scripts/plan_mlb_open_source_dependency_adoption.py
python scripts/audit_mlb_open_source_data_libraries.py
python scripts/build_pit_feature_contract_leakage_audit.py
python scripts/build_p229a_run_line_evidence_boundary_pack.py
python scripts/build_p230a_local_multiseason_runline_data_audit.py
python scripts/build_p235a_final_2025_runline_backtest_package.py
```

## 4.2 Skill Invocation Boundary

`.github/skills/analyze-wbc-betting/SKILL.md` 與 `.github/skills/update-wbc-data/SKILL.md` 是既有工具說明，不等同 personal-ai-flow 授權。

- `/update-wbc-data` 內含 MLB Stats API、名單/球員統計抓取、權威快照重建、TSL odds 抓取與 `data/` 寫入；需 data write Gate + external API Gate。
- `/analyze-wbc-betting` 內含 odds 抓取、TSL crawler、`main.py --game/--all`、EV/Kelly/TSL 建議輸出；在本 Profile 下仍是 paper-only，且需 external API Gate / report artifact Gate。
- 任何 skill 指令若會啟動服務、觸發排程、寫 data/report/output/runtime 或使用 secrets，必須另立任務並明列 allowlist。

## 5. 排程實況

| 作業 | 實際啟動方式 | 排程檔位置 | log | 失敗補跑 |
|---|---|---|---|---|
| Daily WBC Data Sync | GitHub Actions schedule + workflow_dispatch | `.github/workflows/daily_update.yml` | GitHub Actions logs；產物可能寫 `data/`, `reports/`, `outputs/` | [未驗證] 需另立資料/排程任務 |
| replay-default-validation | GitHub Actions pull_request/push/main/workflow_dispatch | `.github/workflows/replay_default_validation.yml` | GitHub Actions logs；artifact `outputs/replay/` | [未驗證] 需另立 CI 任務 |
| local launchd orchestrator | local launchd scripts | `deploy/launchd-orchestrator/`, `scripts/launchd/` | `runtime/agent_orchestrator/logs/` | [未驗證] 需維運授權 |
| local backend/frontend/proxy | `start_all.sh` / `stop_all.sh` | root scripts + `scripts/launchd/common.sh` | `runtime/agent_orchestrator/logs/service/` | [未驗證] 需服務授權 |
| odds capture / daemon scripts | static inventory only | `scripts/com.mlb.odds_capture.plist`, `scripts/odds_capture_daemon.py`, `scripts/check_odds_daemon.py` | [未驗證] | MLB live transport HOLD；不得自動 access |

注意：這張表是 Bootstrap 靜態盤點，不代表實際正在跑。確認實況需另立維運任務，並先取得排程/服務查核授權。

## 6. 緊急處置

```bash
# [未驗證] 僅查詢 repo 狀態
git status --short --branch

# [未驗證] 查看 worktree debt；清理另立 Task
git worktree list --porcelain

# [未驗證] 查看 launchd helper 狀態；可能讀本機服務狀態，執行前需確認
deploy/launchd-orchestrator/status.sh
```

事故/異常第一反應：

1. 先判斷是否涉及資料寫入、排程、服務、外部 API、secrets 或 real-money。
2. 若涉及 `data/`, `runtime/`, `logs/`, `outputs/`，先停止手動操作並保留現場。
3. 用只讀方式收集 `git status`、相關 log 路徑與最後輸出檔 mtime；不要清理。
4. 另立 Task，寫明要查的路徑、指令、是否允許服務/排程操作。

## 6.1 Post-Merge Isolated Worktree Cleanup Gate

Task-specific isolated Git worktrees and task branches must not accumulate after their PR lifecycle is complete. After a PR is successfully merged and post-merge verification passes, remove only the task-owned isolated worktree and then remove the merged task branch.

Scope:

- Applies only to task-owned isolated worktrees whose path exactly matches the expected task worktree path, for example `/Users/kelvin/Kelvin-WorkSpace/Betting-pool-pXXX...`.
- Does not apply to `/Users/kelvin/Kelvin-WorkSpace/Betting-pool`.
- Does not apply to committed repo `report/` artifacts; those are durable evidence, not cleanup targets.
- Does not apply to `.ai` files.
- Does not apply to DB, `data/`, `runtime/`, `logs/`, dependency files, source files, tests, unrelated dirty files, unrelated branches, or unrelated worktrees.
- During the PR-open phase, retain the task worktree when needed for audit, review, fixes, or verification.
- During the PR-merged phase, clean the task worktree only after the required post-merge checks below pass.

Required preconditions before cleanup:

- PR state is `MERGED`.
- `origin/main` contains the PR merge commit.
- Post-merge verification passed, or omitted checks are explicitly marked `NOT RUN` with a reason.
- Task worktree path exactly matches the expected task-owned isolated worktree path.
- `git status --short` inside the task worktree is empty.
- The task branch head is included in `origin/main`.
- No unrelated dirty files are staged or modified.
- Cleanup does not require force.

Allowed cleanup commands only:

```bash
git worktree remove <task-owned-worktree-path>
git branch -d <task-branch>
git push origin --delete <task-branch>
git worktree prune
```

Command limits:

- `git worktree remove <task-owned-worktree-path>` is allowed only for the exact task-owned isolated worktree path.
- `git branch -d <task-branch>` is allowed only after confirming the task branch is merged into `origin/main`.
- `git push origin --delete <task-branch>` is allowed only if the PR is merged and the remote branch still exists.
- `git worktree prune` is allowed only after successful `git worktree remove`.

Explicitly forbidden:

- `rm -rf`.
- Force deletion.
- Deleting or modifying the canonical repo.
- Deleting committed `report/` artifacts.
- Deleting `.ai` files.
- Deleting DB, `data/`, `runtime/`, `logs/`, or dependency files.
- Cleaning unrelated dirty files.
- Deleting a dirty worktree.
- Deleting an unmerged branch.
- Deleting any path outside the exact task-owned isolated worktree.
- Broad cleanup under `/Users/kelvin/Kelvin-WorkSpace`.

STOP and report instead of deleting if:

- PR is not merged.
- Post-merge verification did not pass.
- Worktree has dirty or staged files.
- Branch head is not included in `origin/main`.
- Path does not exactly match the expected task-owned isolated worktree.
- Deletion would require force.
- Cleanup would touch unrelated files or directories.

Owner Override:

This cleanup gate is the default policy. The Owner may explicitly override it for a specific task by stating:

```text
Retain this task worktree after merge: <reason>
```

If this override is present in the current task prompt, the Worker must not remove the task worktree, but must report:

- Retained worktree path.
- Retained branch.
- Reason for retention.
- Cleanup still pending.

## 7. 常見錯誤速查

| 症狀 | 原因 | 處置 |
|---|---|---|
| `README.md` 找不到 | Phase 4 worktree 的 `HEAD` 沒有 root README；主要說明在 `claude.md`、`ORCHESTRATOR_README.md`、`wiki/` | 不要新建或補 README；文件任務另立 |
| 測試或腳本產生大量 data/report/output 變更 | 許多 runner 是研究/產物生成腳本 | 停手，改走資料/研究任務授權與 allowlist |
| port 8787/8788/8789 被占用 | local service 已啟動或殘留 pid | 不要直接 kill；維運任務逐項確認 |
| CLV/odds timeline 對不上 | timestamp/PIT/市場 availability 或 crawler v1/v2 混用 | 依 `wiki/DATA_SOURCES.md` 與 relevant tests 建立專項分析 |
| backtest 看起來過好 | 可能有 look-ahead、樣本太小、regime 或 calibration drift | 套用 stats-methodology/data-provenance checklist |
| worktree 很多或 prunable | 既有 agent 殘留債，或 PR merged 後未清 task-owned isolated worktree | 依 `Post-Merge Isolated Worktree Cleanup Gate`；未滿 preconditions 時 STOP，不清理 |
