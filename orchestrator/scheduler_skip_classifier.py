"""
Phase 12 — Scheduler Skip Reason Classifier

依 agent_task_runs 的 message 欄位將每個 SKIPPED 結果分類為具體原因，
讓 ops report 能區分「合理保護性跳過」與「真正的系統退化」。

Skip reason constants
─────────────────────
SKIP_HARD_OFF        — GLOBAL_HARD_OFF 或 llm_execution_mode=hard-off
SKIP_NO_QUEUED       — 佇列中沒有 QUEUED 任務
SKIP_DAILY_CAP       — 每日上限已建立同類任務
SKIP_GOVERNANCE      — governance / 封鎖家族 阻止執行
SKIP_PROVIDER        — LLM provider 不可用（rate-limit / env-block）
SKIP_DUPLICATE       — 相同安全任務在有效期內已存在
SKIP_SCHEDULER_OFF   — scheduler_enabled = False
SKIP_UNKNOWN         — 無法解析的原因
"""
from __future__ import annotations

SKIP_HARD_OFF      = "hard_off_protection"
SKIP_NO_QUEUED     = "no_queued_tasks"
SKIP_DAILY_CAP     = "daily_cap"
SKIP_GOVERNANCE    = "governance_blocked"
SKIP_PROVIDER      = "worker_provider_unavailable"
SKIP_DUPLICATE     = "duplicate_safe_task"
SKIP_SCHEDULER_OFF = "scheduler_disabled"
SKIP_UNKNOWN       = "unknown"

# ── 關鍵字 → 原因 映射（按優先序排列）────────────────────────────────
_REASON_PATTERNS: list[tuple[list[str], str]] = [
    (["global_hard_off", "hard_off", "hard-off"], SKIP_HARD_OFF),
    (["planner_skip_daily_cap", "daily_cap", "already created today",
      "skip_daily_cap", "planner_skip_cadence", "skip_cadence",
      "cadence slot"], SKIP_DAILY_CAP),
    (["duplicate_safe_task", "duplicate safe", "same task ran recently"],
     SKIP_DUPLICATE),
    (["no queued tasks", "no queued task", "no_queued_tasks",
      "mining_needed", "replan_required"], SKIP_NO_QUEUED),
    (["governance", "governance_blocked", "blocked by governance",
      "all candidates blocked", "family blocked"], SKIP_GOVERNANCE),
    (["rate limit", "rate_limit", "provider unavailable", "blocked_env",
      "failed_rate_limit", "worker_blocked_env", "llm blocked",
      "mcp servers are disabled"], SKIP_PROVIDER),
    (["scheduler-disabled", "scheduler_disabled",
      "scheduler not enabled"], SKIP_SCHEDULER_OFF),
]


def classify_skip_reason(run: dict) -> str:
    """
    Parse a single run row's ``message`` field and return a skip reason constant.

    Only meaningful when ``run["outcome"]`` is a skip variant (SKIPPED / SKIP / NOTHING).
    For non-skip outcomes returns SKIP_UNKNOWN (callers should filter upstream).
    """
    message = (run.get("message") or "").lower()
    if not message:
        return SKIP_UNKNOWN

    for keywords, reason in _REASON_PATTERNS:
        if any(kw in message for kw in keywords):
            return reason

    return SKIP_UNKNOWN


def is_hard_off_skip(run: dict) -> bool:
    """Return True if this run was skipped due to GLOBAL_HARD_OFF."""
    return classify_skip_reason(run) == SKIP_HARD_OFF


def classify_all_skips(runs: list[dict]) -> dict[str, int]:
    """
    Return a summary of skip reasons across *all* SKIPPED-outcome runs in the list.

    Example return value::
        {
            "hard_off_protection": 8,
            "no_queued_tasks": 2,
            "daily_cap": 1,
        }
    """
    _skip_outcomes = {"SKIPPED", "NOTHING", "SKIP"}
    counts: dict[str, int] = {}
    for run in runs:
        if run.get("outcome", "").upper() not in _skip_outcomes:
            continue
        reason = classify_skip_reason(run)
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def count_unexplained_consecutive_skips(runs: list[dict]) -> int:
    """
    Count consecutive SKIPPED runs at the HEAD of ``runs`` that are NOT
    explained by hard-off protection or scheduler-disabled.

    Runs must be sorted **most-recent-first**.

    Only the following reasons count as "unexplained" (implying real degradation):
    - SKIP_NO_QUEUED
    - SKIP_GOVERNANCE
    - SKIP_PROVIDER
    - SKIP_DAILY_CAP   (borderline — task cap hit, but still shows activity)
    - SKIP_DUPLICATE
    - SKIP_UNKNOWN

    Protected reasons (do NOT count against health):
    - SKIP_HARD_OFF
    - SKIP_SCHEDULER_OFF
    """
    _protected = {SKIP_HARD_OFF, SKIP_SCHEDULER_OFF}
    _skip_outcomes = {"SKIPPED", "NOTHING", "SKIP"}

    consecutive = 0
    for run in runs:
        outcome = run.get("outcome", "").upper()
        if outcome not in _skip_outcomes:
            break  # hit a non-skip → stop counting
        reason = classify_skip_reason(run)
        if reason in _protected:
            continue  # protected skip — keep scanning but don't count
        consecutive += 1

    return consecutive


def all_consecutive_skips_are_protected(runs: list[dict]) -> bool:
    """
    Return True if every consecutive SKIPPED run at the head of ``runs``
    is explained by a protected reason (hard-off / scheduler-disabled).

    Useful for classify_window to distinguish WAITING_ACTIVE from DEGRADED.
    Runs must be sorted most-recent-first.
    """
    _protected = {SKIP_HARD_OFF, SKIP_SCHEDULER_OFF}
    _skip_outcomes = {"SKIPPED", "NOTHING", "SKIP"}

    found_any_skip = False
    for run in runs:
        outcome = run.get("outcome", "").upper()
        if outcome not in _skip_outcomes:
            break
        found_any_skip = True
        if classify_skip_reason(run) not in _protected:
            return False

    return found_any_skip  # True only when ≥1 skip and all are protected
