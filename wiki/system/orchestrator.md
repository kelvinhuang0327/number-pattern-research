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

---

## AUTO-MONITOR Prompt Contract

**Source**: `orchestrator/planner_decision.py` → `_build_replacement_payload(REPLACE_WITH_MONITORING, ...)`

### 觸發條件

當 planner_decision 判定某個 deep_research_cold / deep_research_hot 任務應被擋下（REPLACE_WITH_MONITORING），或 taxonomy 無強訊號時，自動產出一筆 `worker_type=light` 的 monitoring 任務。
dedupe_key 格式：`monitoring:{source_task_type}:{today_utc}`（每日唯一，不重複建立）。

### 必查 DB Tables

| Table | 查詢目的 |
|---|---|
| `active_strategy_state` | 各彩種 active/shadow 策略名稱、edge、planner_focus |
| `strategy_reviews` | 近期決策紀錄（decision 分佈） |
| `strategy_live_state` | live ROI / drift_score / consecutive_losses（若無此表則明確標 NO_LIVE_OUTCOME_DATA_AVAILABLE） |
| `agent_tasks` (WHERE failure_category IS NOT NULL) | 近 24h 失敗分類計數 |

### 三彩種 Monitoring Rules

**BIG_LOTTO**
- 預期 mode: MAINTENANCE、active: `p1_dev_sum5bet`、shadow: `regime_2bet`
- 若 active_strategy_state 缺失或策略異常 → flag ESCALATE
- 除非官方規則或外部資料有變，不得建議新 deep research

**DAILY_539**
- 預期 mode: WATCH_MAINTENANCE、active: `acb_markov_midfreq_3bet`、shadow: `midfreq_acb_2bet`
- Watchdog：若 3000p edge ≤ +2.0pp → flag DEGRADED，觸發 CTO review
- 若 planner_focus 未含 WATCH_MAINTENANCE → flag ESCALATE
- 不得建議同家族新研究

**POWER_LOTTO**
- 預期 mode: MONITOR、active: `pp3_freqort_4bet`、shadow: `orthogonal_5bet`
- 若 shadow 仍為 `fourier_rhythm_3bet` → flag ESCALATE
- 不得重啟 Fourier / PP3 / MidFreq 同家族研究
- 僅允許低成本測試：special_number_conditional_dist、jackpot carryover、sell_amount Layer-1、3000p+ residue

### Watchdog Rules

| Game | 指標 | 閾值 | 結果 |
|---|---|---|---|
| DAILY_539 | 3000p edge | ≤ +2.0pp | DEGRADED → CTO review |
| All | drift_score (strategy_live_state) | > 0.50 | DEGRADED |
| All | consecutive_losses | 超過配置閾值 | DEGRADED |

### Final Status Enum

- **OK**: 所有 active/shadow 符合預期、無 watchdog breach、無高 drift
- **WATCH**: 輕微退化或缺少 live data，暫無立即行動
- **ESCALATE**: active/shadow mismatch、pipeline 中斷、重複 FORMAT_CONTRACT/VALIDATION 失敗
- **DEGRADED**: DAILY_539 edge ≤ +2.0pp；drift_score > 0.50；連敗超閾值

### Required Output

`outputs/monitoring_status.md`，必須包含 7 sections：
1. Summary（final status）
2. Active Strategy State Table
3. Watchdog Check Table
4. Live Outcome / Drift Check（或 NO_LIVE_OUTCOME_DATA_AVAILABLE）
5. Recent Failure Check Table
6. Action Items
7. Evidence（含原始 SQL 結果）

### Forbidden

不得：建立新策略、修改 active_strategy_state、修改 strategy_states 檔、修改 lottery_v2.db、執行重型 deep research、在無 SQL 證據下宣稱改善。

### Failure Condition

若 AUTO-MONITOR prompt 僅含「check active strategies」等泛化描述，而無 SQL / watchdog / 三彩種規則，視為 prompt contract 退化，應立即修復 `_build_replacement_payload()`。
- Handoff Notes 需回寫 wiki 是否更新、哪些策略表更新、是否新增 lesson。

---

## Date Label Convention

**適用範圍**：所有 orchestrator 產生的 dedupe_key、檔案命名、UI 顯示、報告日期標籤。

### 核心規則

| 用途 | 時區 | 格式 | 範例 |
|---|---|---|---|
| dedupe_key（DB 儲存、排重）| **UTC** | `YYYY-MM-DD` | `forced_exploration:external_signal:2026-04-28` |
| 任務檔案命名（slot_key / date_folder）| local（系統預設）| `YYYYMMDDHHMMSS` / `YYYYMMDD` | `20260429143000` |
| UI 顯示、backlog status | **Asia/Taipei（UTC+8）** | `YYYY/MM/DD HH:MM:SS` | `2026/04/29 14:30:00` |
| 報告標題 / wiki 條目 | Asia/Taipei local date | `YYYY-MM-DD` | `2026-04-29` |

### 問題根源（2026-04-29 記錄）

UTC 與 Asia/Taipei 之間存在 +8h 時差。台灣時間 2026-04-29 00:00–07:59 對應 UTC 2026-04-28，導致：
- dedupe_key 使用 UTC date（`2026-04-28`），但 UI / wiki 顯示 Asia/Taipei date（`2026-04-29`）
- 若用 local date 建立 dedupe_key，會在同一 UTC 日產生兩份不同 key，破壞排重邏輯

**決策**：dedupe_key 固定用 UTC date；UI / 報告顯示 Asia/Taipei。不得混用。

### Helper 函數（`orchestrator/common.py`）

```python
def dedupe_day_utc() -> str:
    """Return today's date in UTC as YYYY-MM-DD. Use for dedupe_key building."""

def display_day_local() -> str:
    """Return today's date in Asia/Taipei (UTC+8) as YYYY-MM-DD. Use for UI display."""
```

### dedupe_key 格式範例

| 類型 | 格式 | 時區 |
|---|---|---|
| forced_exploration | `forced_exploration:{lane}:{dedupe_day_utc}` | UTC |
| fallback | `fallback:{type}:{dedupe_day_utc}` | UTC |
| monitoring | `monitoring:{source}:{dedupe_day_utc}` | UTC |
| validation | `validation:{lane}:{dedupe_day_utc}` | UTC |

### 嚴格禁止

- 不得將 local date（Asia/Taipei）直接嵌入 dedupe_key，除非同時做 DB 全量遷移
- 不得在現有 DB 中修改舊 dedupe_key 格式（遷移需獨立任務）
- 不得在同一 key 空間混用 UTC / local date

### 未來工作

- TODO（低優先）：將 `planner_tick.py` 中所有 `datetime.now(timezone.utc).strftime("%Y-%m-%d")` 替換為 `common.dedupe_day_utc()`，已有 helper 可用