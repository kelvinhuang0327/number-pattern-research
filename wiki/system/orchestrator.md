# Agent Orchestrator

## 架構總覽

- 原始碼目錄：orchestrator/
- runtime backlog：runtime/agent_orchestrator/backlog.md
- SQLite DB：runtime/agent_orchestrator/orchestrator.db
- 任務檔案：runtime/agent_orchestrator/tasks/<date>/
- logs / locks：runtime/agent_orchestrator/logs/, runtime/agent_orchestrator/locks/

## 目錄結構

| 路徑 | 角色 |
|---|---|
| orchestrator/common.py | 共用路徑、prompt、provider、檔案命名 |
| orchestrator/db.py | 任務表、tick log、設定表、worker lock |
| orchestrator/planner_tick.py | 讀 backlog / 歷史，產出下一個任務 prompt |
| orchestrator/worker_tick.py | claim QUEUED 任務、寫 completed 檔、更新狀態 |
| orchestrator/api.py | UI / API 查詢與 provider 設定 |
| orchestrator/readme.md | 人工操作與設計說明 |

## Planner / Worker 角色

- Planner：Claude CLI 或 Codex CLI；負責閱讀 backlog、近期任務與 wiki 摘要，產出 8 小時 prompt。
- Worker：Codex CLI / Copilot CLI / Claude CLI；負責執行 prompt、寫變更、輸出 completed 摘要。
- Planner 不直接寫業務檔；Worker 不負責排程決策。

## 狀態機

- QUEUED：planner 已建立 prompt，等待 worker claim。
- RUNNING：worker 已啟動並綁定 pid / lock。
- COMPLETED：worker 有輸出或變更，任務結案。
- FAILED：prompt 缺失、provider 不可用、或 worker 無任何輸出即結束。

## 重要路徑

- backlog.md：runtime/agent_orchestrator/backlog.md
- orchestrator.db：runtime/agent_orchestrator/orchestrator.db
- completed 檔命名：runtime/agent_orchestrator/tasks/<date>/<slot>-completed-<slug>.md

## Planner 注入規則

- Planner 會讀 backlog、最近 5 筆任務歷史，以及 wiki 摘要。
- 若 backlog 指向特定彩種，對應 wiki/games 頁面會優先注入。
- Handoff Notes 需回寫 wiki 是否更新、哪些策略表更新、是否新增 lesson。