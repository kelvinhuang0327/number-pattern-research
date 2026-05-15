#!/usr/bin/env python3
"""
Claude Planner tick — triggered every 10 min by launchd.
Reads backlog.md + recent completed tasks, calls `claude -p` to produce next 8h prompt.
"""

import argparse
import sys
import os
import json
import glob
import time
import logging
import subprocess
import re
import random
import tempfile
from datetime import datetime, timezone
from typing import Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common, prompt_generator, execution_policy, health, planner_guard, planner_decision, task_scorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [planner] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

RUNNER = "planner"
WIKI_ROOT = os.path.join(common.ROOT, "wiki")
FALLBACK_WARNING = "%s — using local fallback payload"
DRY_RUN_HISTORY = "（dry-run：略過資料庫任務歷史）"
TERMINAL_TASK_STATUSES = {
    "COMPLETED",
    "FAILED",
    "FAILED_ACCEPTANCE",
    "FAILED_RATE_LIMIT",
    "FAILED_NO_EDGE",
    "FAILED_WEAK_EDGE",
    "CANCELLED",
    "CANCELLED_DUPLICATE",
    "SKIPPED_DUPLICATE",
    "REPLAN_REQUIRED",
}
BLOCKED_ENV_MAX_AGE_SECONDS = 600


def _parse_utc_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _looks_like_rate_limit_message(*parts: str) -> bool:
    text = "\n".join(str(part or "") for part in parts).lower()
    markers = (
        "you've hit your rate limit",
        "rate limit",
        "limit to reset",
        "docs.github.com/en/copilot/concepts/rate-limits",
        "github.com/en/copilot/concepts/rate-limits",
        "premium",
        "429",
        "copilot_rate_limit",
    )
    return any(marker in text for marker in markers)


def _resolve_previous_task_blocker(latest: Optional[dict]) -> tuple[bool, Optional[str]]:
    if not latest:
        return False, None

    status = str(latest.get("status") or "").upper()
    if status in TERMINAL_TASK_STATUSES:
        return False, None

    if status != "BLOCKED_ENV":
        return True, f"Previous task {latest['id']} still {latest['status']} — skip"

    now = datetime.now(timezone.utc)
    age_anchor = (
        _parse_utc_ts(latest.get("updated_at"))
        or _parse_utc_ts(latest.get("completed_at"))
        or _parse_utc_ts(latest.get("started_at"))
        or _parse_utc_ts(latest.get("created_at"))
    )
    age_seconds = int((now - age_anchor).total_seconds()) if age_anchor else BLOCKED_ENV_MAX_AGE_SECONDS + 1
    if age_seconds < BLOCKED_ENV_MAX_AGE_SECONDS:
        return True, f"Previous task {latest['id']} still {latest['status']} — skip"

    combined_reason = "\n".join(
        [
            str(latest.get("error_message") or ""),
            str(latest.get("completed_text") or ""),
        ]
    )
    final_status = "FAILED_RATE_LIMIT" if _looks_like_rate_limit_message(combined_reason) else "FAILED"
    failure_reason = "copilot_rate_limit" if final_status == "FAILED_RATE_LIMIT" else "blocked_env_timeout"
    final_message = (
        "provider = copilot; reason = rate_limit"
        if final_status == "FAILED_RATE_LIMIT"
        else f"BLOCKED_ENV expired after {BLOCKED_ENV_MAX_AGE_SECONDS}s"
    )
    db.update_task(
        latest["id"],
        status=final_status,
        completed_at=latest.get("completed_at") or now.isoformat(),
        error_message=f"{failure_reason}: {final_message}",
    )
    msg = f"Previous task {latest['id']} auto-resolved from BLOCKED_ENV to {final_status} after {age_seconds}s"
    logger.warning(msg)
    db.log_tick(RUNNER, "PLANNER_RESOLVED_STALE_BLOCKED_ENV", task_id=latest["id"], message=msg)
    common.log_jsonl(
        RUNNER,
        "PLANNER_RESOLVED_STALE_BLOCKED_ENV",
        task_id=latest["id"],
        previous_status="BLOCKED_ENV",
        final_status=final_status,
        failure_reason=failure_reason,
        age_seconds=age_seconds,
    )
    return False, None


def _classify_task_run_state(latest: Optional[dict]) -> str:
    """Return 'NORMAL', 'LONG_RUNNING', or 'STUCK' for an in-flight task.

    Delegates to common.classify_task_run_state; maps RUNNING→NORMAL so callers
    can use the three-way branch cleanly.
    """
    if not latest:
        return "NORMAL"
    state = common.classify_task_run_state(latest)
    return "NORMAL" if state == "RUNNING" else state


def _task_elapsed_seconds(latest: Optional[dict]) -> float:
    """Return elapsed seconds since task started (or 0 if unknown)."""
    if not latest:
        return 0.0
    raw = latest.get("started_at") or latest.get("created_at")
    if not raw:
        return 0.0
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except Exception:
        return 0.0


def _recent_history_summary(n=5) -> str:
    """Return recent tasks regardless of status so planner knows about failures."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        tasks = [dict(r) for r in rows]
    finally:
        conn.close()

    if not tasks:
        return "（尚無任何歷史任務）"
    parts = []
    for t in tasks:
        status = t.get("status", "UNKNOWN")
        summary = (t.get("completed_text") or t.get("error_message") or "")[:400]
        parts.append(
            f"### [{status}] {t['title']} ({t['slot_key']})\n{summary}"
        )
    return "\n\n".join(parts)


def _get_recent_task_titles(n: int = 10) -> list[str]:
    """Return recent task titles for prompt deduplication context."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT title FROM agent_tasks ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [row["title"] for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def _build_generator_context(signal_state: dict, backlog: str) -> dict:
    """
    Build the context dict passed to prompt_generator.build_long_task_prompt().
    Aggregates signal_state fields and recent task history into a single snapshot.
    """
    return {
        "current_state":     signal_state.get("state", ""),
        "confidence_score":  signal_state.get("confidence_score", 0.5),
        "confidence_label":  signal_state.get("confidence_label", "uncertain"),
        "reason":            signal_state.get("reason", ""),
        "recent_task_titles": _get_recent_task_titles(n=10),
        "game_summaries":    signal_state.get("game_summaries", {}),
        "policy":            signal_state.get("policy", {}),
    }


def _extract_backlog_priorities(backlog: str, limit: int = 2) -> list[str]:
    items = []
    for line in backlog.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ["):
            item = re.sub(r"^- \[[ xX]\]\s*", "", stripped)
            if item:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def _fallback_payload(backlog: str) -> dict:
    priorities = _extract_backlog_priorities(backlog)
    primary = priorities[0] if priorities else "檢查 backlog 並產出下一個可驗證任務"
    secondary = priorities[1] if len(priorities) > 1 else "整理驗證步驟、阻塞與後續 handoff"

    title_base = primary.split("：", 1)[-1].strip()
    title = title_base[:40] or "Backlog Validation Task"
    slug_hint = None
    match = re.search(r"`([^`]+)`", primary)
    if match:
        slug_hint = match.group(1)
    else:
        ascii_hint = re.sub(r"[^a-zA-Z0-9\s_-]", " ", primary).strip()
        slug_hint = ascii_hint
    slug = common.slugify(slug_hint or title) or "backlog-validation-task"

    prompt_markdown = f"""## Objective

從 backlog 的最高優先任務開始，完成一個可驗證、可交接的實作或驗證循環。

## Scope

1. 聚焦處理：{primary}
2. 次要延伸：{secondary}
3. 盤點相關程式與資料檔，確認現況、限制與可驗證方式
4. 完成最小必要修改或驗證，並保留清楚的完成摘要

## Constraints

- 不得修改 lottery_v2.db
- 不得繞過 lottery_api/CLAUDE.md 的驗證標準
- 優先採用最小變更，避免擴散到無關模組

## Acceptance Criteria

- 有明確的完成摘要或驗證結論
- 有列出異動檔案或確認無異動
- 有記錄尚未解決的風險與下一步

## Handoff Notes

- backlog 來源：runtime/agent_orchestrator/backlog.md
- orchestrator DB：runtime/agent_orchestrator/orchestrator.db
- 若有新策略驗證結果（PASS/REJECT），更新 wiki/games/<game>.md 的現役策略表
- 若為新教訓，在 wiki/lessons/key_lessons.md 末尾新增（格式：**L<N>** 說明）
- 若無新發現，Handoff Notes 填「wiki 無需更新」
- 完成後需在 completed 檔案留下人工可讀的摘要
"""

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
    }


def _read_wiki_excerpt(path: str, max_lines: int = 60) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = []
            for _, line in zip(range(max_lines), handle):
                lines.append(line.rstrip("\n"))
        return "\n".join(lines).strip()
    except OSError:
        return ""


def _load_wiki_context(backlog: str) -> tuple[str, list[str]]:
    pages = [
        (
            "BIG_LOTTO",
            os.path.join(WIKI_ROOT, "games", "big_lotto.md"),
            ["BIG_LOTTO", "big_lotto", "大樂透", "49c6"],
        ),
        (
            "DAILY_539",
            os.path.join(WIKI_ROOT, "games", "daily_539.md"),
            ["DAILY_539", "daily_539", "今彩539", "539"],
        ),
        (
            "POWER_LOTTO",
            os.path.join(WIKI_ROOT, "games", "power_lotto.md"),
            ["POWER_LOTTO", "power_lotto", "威力彩", "38c6"],
        ),
    ]
    backlog_lower = backlog.lower()
    prioritized = []
    deferred = []
    for label, path, keywords in pages:
        entry = (label, path)
        if any(keyword.lower() in backlog_lower for keyword in keywords):
            prioritized.append(entry)
        else:
            deferred.append(entry)

    loaded = []
    labels = []
    for label, path in prioritized + deferred:
        excerpt = _read_wiki_excerpt(path)
        if excerpt:
            loaded.append(f"## {label}\n{excerpt}")
            labels.append(label)

    if labels:
        logger.info("Loaded wiki context from %d page(s): %s", len(labels), ", ".join(labels))
    else:
        logger.info("Wiki context unavailable; planner proceeding without injection")
    return "\n\n".join(loaded), labels


def _check_signal_exhaustion(backlog: str) -> bool:
    """
    Legacy helper — kept for backward compatibility with existing tests.
    Returns True if [SIGNAL_EXHAUSTED_ALL] is found in the backlog.
    Use _classify_signal_state() for the full 3-state regime-aware decision.
    """
    return "[SIGNAL_EXHAUSTED_ALL]" in backlog


# ─── Adaptive Signal State Classifier ────────────────────────────────────────
#
# Replaces the static SIGNAL_EXHAUSTED_ALL gate with a 3-state decision:
#
#   TRUE_EXHAUSTED    → completely stop (no data, no strategies, no signals)
#   SIGNAL_SATURATED  → switch to meta-level / quality tasks, do NOT stop
#   COLD_REGIME       → generate regime-aware tasks (analysis + adaptation)
#
# ─────────────────────────────────────────────────────────────────────────────

_STRATEGY_STATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lottery_api", "data",
)
_GAMES = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")


def _load_strategy_states_all() -> dict[str, dict]:
    """Load strategy_states_{game}.json for all three games. Returns {game: {name: state}}."""
    result: dict[str, dict] = {}
    for game in _GAMES:
        path = os.path.join(_STRATEGY_STATES_DIR, f"strategy_states_{game}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                result[game] = json.load(fh)
        except OSError:
            result[game] = {}
    return result


def _game_signal_summary(states: dict) -> dict:
    """
    Derive per-game signal health from strategy_states.
    Returns:
      has_strategies         bool
      has_validated          bool   — any strategy with validated_status 'validated'|'active'
      best_edge_long         float  — best edge_1500p (or edge_500p fallback, then edge_150p)
      best_edge_short        float  — best edge_30p
      cold_count             int    — strategies with consecutive_neg_30p >= 3
      total                  int
    """
    if not states:
        return {
            "has_strategies": False, "has_validated": False,
            "best_edge_long": None, "best_edge_short": None,
            "cold_count": 0, "total": 0,
        }

    total = len(states)
    validated = {
        "validated", "active", "VALIDATED", "ACTIVE",
        "PROMOTED", "promoted", "conditional",
    }
    has_validated = any(
        (s.get("validated_status") or "") in validated for s in states.values()
    )

    # Long edge: prefer edge_1500p → edge_500p → edge_150p (all may be None)
    long_edges = []
    short_edges = []
    cold_count = 0
    for s in states.values():
        long_val = s.get("edge_1500p") or s.get("edge_500p") or s.get("edge_150p")
        if long_val is not None:
            long_edges.append(float(long_val))
        short_val = s.get("edge_30p")
        if short_val is not None:
            short_edges.append(float(short_val))
        neg_streak = s.get("consecutive_neg_30p") or 0
        if neg_streak >= 3:
            cold_count += 1

    return {
        "has_strategies": total > 0,
        "has_validated": has_validated,
        "best_edge_long": max(long_edges) if long_edges else None,
        "best_edge_short": max(short_edges) if short_edges else None,
        "cold_count": cold_count,
        "total": total,
    }


# State constants
SIGNAL_STATE_TRUE_EXHAUSTED = "TRUE_EXHAUSTED"
SIGNAL_STATE_SATURATED      = "SIGNAL_SATURATED"
SIGNAL_STATE_COLD_REGIME    = "COLD_REGIME"

# Dedupe / cooldown constants
_TASK_COOLDOWN_SECONDS   = 30 * 60   # 30 minutes — completed task cooldown
_CONFIDENCE_CHANGE_GATE  = 0.20      # bypass cooldown if confidence shifts by more than this


def _build_task_dedupe_key(task_type: str, regime_state: str) -> str:
    """
    Build a dedupe key that uniquely identifies a task category.
    Format: "{task_type}:{regime_state}"
    Example: "cold_phase_analysis:COLD_REGIME"
    """
    return f"{task_type}:{regime_state}"


def _check_task_dedupe(
    dedupe_key: str,
    signal_state: dict,
    monitor_source_task_type: str = "",
    cooldown_seconds: int = _TASK_COOLDOWN_SECONDS,
) -> tuple[bool, str]:
    """
    Check whether a new task with the given dedupe_key should be suppressed.

    Returns: (should_skip: bool, reason: str)

    Guard order:
    0.  Monitoring source suppression — RUNNING/QUEUED monitor for same source → skip
    0.5 Daily cap for date-keyed monitoring — any QUEUED/RUNNING/COMPLETED today → skip
    1.  In-flight guard  — QUEUED or RUNNING task exists → always skip
    2.  Cooldown guard   — COMPLETED task within cooldown window → skip
                           UNLESS confidence changed significantly vs. last emission
                           OR regime_state changed
    """
    try:
        # 0. Monitoring source suppression (replacement task guard)
        source = (monitor_source_task_type or "").strip()
        if dedupe_key.startswith("monitoring:") and source:
            inflight_monitor = db.get_inflight_auto_monitor_by_source_task_type(source)
            if inflight_monitor:
                return True, (
                    "DUPLICATE_MONITORING_SOURCE:"
                    f"source={source};existing_task_id={inflight_monitor['id']};"
                    f"existing_status={inflight_monitor['status']};"
                    f"existing_key={inflight_monitor.get('dedupe_key')!r};"
                    f"new_key={dedupe_key!r}"
                )

        # 0.5. Daily cap for date-based monitoring keys  (monitoring:{source}:{YYYY-MM-DD})
        # Replacement tasks store confidence_snapshot=NULL, causing the confidence-delta
        # bypass in guard 2 to fire on every tick (|any_value - 0.0| > 0.20).  The daily
        # cap is a hard gate: one monitoring task per (source_type, calendar day), regardless
        # of confidence changes.  FAILED tasks are excluded so a bad run doesn't block the day.
        _key_parts = dedupe_key.split(":")
        if dedupe_key.startswith("monitoring:") and len(_key_parts) == 3 and len(_key_parts[2]) == 10:
            today_task = db.get_today_auto_monitor_by_dedupe_key(dedupe_key)
            if today_task:
                return True, (
                    "DAILY_CAP_MONITORING_SOURCE:"
                    f"existing_task_id={today_task['id']};"
                    f"existing_status={today_task['status']};"
                    f"key={dedupe_key!r}"
                )

        # 1. In-flight guard
        inflight = db.get_inflight_task_by_dedupe_key(dedupe_key)
        if inflight:
            return True, (
                f"已存在相同分析任務（冷卻中）— "
                f"task_id={inflight['id']}, status={inflight['status']}, "
                f"key={dedupe_key!r}"
            )

        # 2. Cooldown guard
        recent_completed = db.get_recent_completed_task_by_dedupe_key(dedupe_key, cooldown_seconds)
        if not recent_completed:
            return False, ""  # No cooldown — allow

        # State-change trigger: if regime_state or confidence changed enough → bypass cooldown
        current_confidence = signal_state.get("confidence_score", 0.0)
        current_state      = signal_state.get("state") or ""

        last_state_info = db.get_planner_dedupe_state(dedupe_key)
        if last_state_info:
            last_confidence = last_state_info.get("last_confidence") or 0.0
            last_regime     = last_state_info.get("last_regime_state") or ""
            confidence_delta = abs(current_confidence - last_confidence)

            if last_regime and last_regime != current_state:
                # Regime changed — bypass cooldown; different state means task_type already differs,
                # so dedupe_key would be different — this is a safety fallback
                return False, ""
            if confidence_delta > _CONFIDENCE_CHANGE_GATE:
                logger.info(
                    "[DEDUPE] Confidence shift %.2f → %.2f (Δ=%.2f > %.2f gate) — bypassing cooldown for %r",
                    last_confidence, current_confidence, confidence_delta,
                    _CONFIDENCE_CHANGE_GATE, dedupe_key,
                )
                return False, ""

        completed_at = recent_completed.get("completed_at") or ""
        expiry_info = ""
        if completed_at:
            try:
                from datetime import datetime as _dt, timedelta as _td
                _completed_dt = _dt.fromisoformat(completed_at)
                _expires_dt   = _completed_dt + _td(seconds=cooldown_seconds)
                expiry_info   = f"，冷卻至 {_expires_dt.strftime('%H:%M:%S')} UTC"
            except Exception:
                pass
        return True, (
            f"已存在相同分析任務（冷卻中）— "
            f"task_id={recent_completed['id']} 完成於 {completed_at}{expiry_info}，"
            f"冷卻 {cooldown_seconds // 60} 分鐘，"
            f"key={dedupe_key!r}"
        )

    except Exception as exc:
        # Dedupe check failure must NEVER block task creation — log and allow
        logger.warning("[DEDUPE] Guard check failed (non-blocking): %s", exc)
        return False, ""


def _compute_confidence_score(
    state: str,
    cold_signals: list,
    game_summaries: dict,
    policy: dict,
    thresholds: dict,
) -> tuple[float, str]:
    """
    Compute a confidence score (0.0–1.0) for a classification decision.

    Scoring factors (weighted sum, capped to [0.1, 0.95]):
    ─────────────────────────────────────────────────────
    COLD_REGIME:
      • Number of triggering games   × weight_cold_streak (default 1.0) × 0.20
      • Edge-divergence games        × weight_edge_divergence (1.5)     × 0.20
      • Policy confidence support    × weight_policy_support (0.5)      × 0.10
      • Multiple-game corroboration  +0.10

    SIGNAL_SATURATED:
      • Has validated strategies     +0.20
      • Overall merge rate > 0.3     +0.20 (proven meaningful activity)
      • runs_analyzed > 10           +0.15
      • Policy confidence high       +0.10

    TRUE_EXHAUSTED:
      • Near-certain by construction → fixed 0.90 (strong)

    Labels: strong_cold / cold / weak_cold / strong_saturated / saturated /
            uncertain / strong_exhausted
    """
    w_streak   = float(thresholds.get("weight_cold_streak",     1.0))
    w_div      = float(thresholds.get("weight_edge_divergence",  1.5))
    w_policy   = float(thresholds.get("weight_policy_support",   0.5))
    runs       = int(policy.get("runs_analyzed", 0))
    confidence = policy.get("confidence", "low")
    overall_mr = float(policy.get("overall_merge_rate", 0.0))

    if state == SIGNAL_STATE_TRUE_EXHAUSTED:
        return 0.90, "strong_exhausted"

    if state == SIGNAL_STATE_COLD_REGIME:
        score = 0.0
        n_games = len(cold_signals)
        score += n_games * w_streak * 0.20

        divergence_games = [s for s in cold_signals if "long-term edge" in s]
        score += len(divergence_games) * w_div * 0.20

        if confidence in ("medium", "high") and runs >= 5:
            score += w_policy * 0.10

        if n_games >= 2:
            score += 0.10  # corroboration bonus

        score = max(0.1, min(0.95, score))
        if score >= 0.75:
            label = "strong_cold"
        elif score >= 0.50:
            label = "cold"
        elif score >= 0.30:
            label = "weak_cold"
        else:
            label = "uncertain"
        return round(score, 4), label

    if state == SIGNAL_STATE_SATURATED:
        score = 0.10  # base
        any_validated = any(g["has_validated"] for g in game_summaries.values())
        if any_validated:
            score += 0.20
        if overall_mr >= 0.30:
            score += 0.20
        if runs >= 10:
            score += 0.15
        elif runs >= 5:
            score += 0.08
        if confidence == "high":
            score += 0.10
        elif confidence == "medium":
            score += 0.05

        score = max(0.1, min(0.95, score))
        if score >= 0.65:
            label = "strong_saturated"
        elif score >= 0.40:
            label = "saturated"
        else:
            label = "uncertain"
        return round(score, 4), label

    return 0.5, "uncertain"


def _classify_signal_state(backlog: str) -> dict:
    """
    Classify the current signal exhaustion state using adaptive, data-driven rules.

    Decision tree:
    ─────────────────────────────────────────────────────────────────────────
    NOT [SIGNAL_EXHAUSTED_ALL] in backlog → normal planning, not classified
    ─────────────────────────────────────────────────────────────────────────
    [SIGNAL_EXHAUSTED_ALL] present:

    1. Load dynamic thresholds from classifier_thresholds (self-calibrating).
    2. Load strategy_states for all games.
    3. Load adaptive_policy (intent_stats, merge rates, confidence).
    4. Per-game signal summary.

    Classification rules (evaluated in order):

    TRUE_EXHAUSTED  — only when ALL of:
      • No strategies across any game (total == 0)
      • No intent signal history (runs_analyzed <= exhausted_max_runs_analyzed)
      • No positive short-term edge in any game

    COLD_REGIME — when ANY game shows:
      • best_edge_long > cold_edge_long_min AND best_edge_short < cold_edge_short_max
      • OR cold_count / total >= cold_streak_ratio (AND total >= cold_min_total_strategies)
      • OR best_edge_short < cold_edge_absolute_max (AND total >= cold_min_total_strategies)

    SIGNAL_SATURATED — everything else.

    Each classification is logged to classifier_calibration_log for accuracy tracking.
    The returned dict includes confidence_score, confidence_label, calibration_id.
    ─────────────────────────────────────────────────────────────────────────
    """
    if not _check_signal_exhaustion(backlog):
        return {"state": None, "reason": "no exhaustion marker"}

    # ── Load dynamic thresholds ────────────────────────────────────────────
    try:
        thresholds = db.get_classifier_thresholds()
    except Exception:
        thresholds = {
            "cold_streak_ratio": 0.5, "cold_edge_long_min": 0.0,
            "cold_edge_short_max": 0.0, "cold_edge_absolute_max": -0.05,
            "cold_min_total_strategies": 2, "exhausted_max_runs_analyzed": 0,
            "weight_cold_streak": 1.0, "weight_edge_divergence": 1.5,
            "weight_policy_support": 0.5,
        }

    cold_streak_ratio = float(thresholds.get("cold_streak_ratio", 0.5))
    cold_edge_long_min = float(thresholds.get("cold_edge_long_min", 0.0))
    cold_edge_short_max = float(thresholds.get("cold_edge_short_max", 0.0))
    cold_edge_abs_max = float(thresholds.get("cold_edge_absolute_max", -0.05))
    cold_min_total = int(thresholds.get("cold_min_total_strategies", 2))
    exhausted_max_runs = int(thresholds.get("exhausted_max_runs_analyzed", 0))

    # ── Load signals ───────────────────────────────────────────────────────
    all_states = _load_strategy_states_all()
    game_summaries: dict[str, dict] = {}
    for game in _GAMES:
        game_summaries[game] = _game_signal_summary(all_states.get(game, {}))

    # ── Load adaptive policy ───────────────────────────────────────────────
    try:
        policy = db.get_adaptive_policy(max_age_seconds=7200)
    except Exception:
        policy = {}

    runs_analyzed      = int(policy.get("runs_analyzed") or 0)
    retry_merge_rate   = float(policy.get("retry_merge_rate") or 0.0)
    overall_merge_rate = float(policy.get("overall_merge_rate") or 0.0)
    policy_confidence  = policy.get("policy_confidence") or "low"

    total_strategies  = sum(g["total"] for g in game_summaries.values())
    any_positive_short = any(
        (g["best_edge_short"] or 0.0) > 0.0 for g in game_summaries.values()
    )
    any_strategies = total_strategies > 0

    # Helper: build compact policy context for confidence scoring
    policy_ctx = {
        "runs_analyzed": runs_analyzed,
        "confidence": policy_confidence,
        "retry_merge_rate": retry_merge_rate,
        "overall_merge_rate": overall_merge_rate,
    }

    def _log_event(state: str, reason: str, cold_signals: list) -> int:
        """Record event and return calibration_id (0 on error)."""
        try:
            import json as _json
            features = {
                "game_summaries": {
                    g: {k: v for k, v in s.items()} for g, s in game_summaries.items()
                },
                "total_strategies": total_strategies,
                "runs_analyzed": runs_analyzed,
                "policy_confidence": policy_confidence,
                "overall_merge_rate": overall_merge_rate,
            }
            score, label = _compute_confidence_score(state, cold_signals, game_summaries, policy_ctx, thresholds)
            cal_id = db.record_classifier_event(
                state=state,
                confidence_score=score,
                confidence_label=label,
                reason=reason,
                features_json=_json.dumps(features, ensure_ascii=False),
                thresholds_json=_json.dumps(thresholds, ensure_ascii=False),
            )
            return cal_id, score, label
        except Exception:
            return 0, 0.5, "uncertain"

    # ── Rule 1: TRUE_EXHAUSTED ─────────────────────────────────────────────
    if not any_strategies and runs_analyzed <= exhausted_max_runs and not any_positive_short:
        reason = "No strategies + no signal history + no positive edge"
        cal_id, score, label = _log_event(SIGNAL_STATE_TRUE_EXHAUSTED, reason, [])
        return {
            "state":            SIGNAL_STATE_TRUE_EXHAUSTED,
            "reason":           reason,
            "game_summaries":   game_summaries,
            "confidence_score": score,
            "confidence_label": label,
            "calibration_id":   cal_id,
            "policy": {"runs_analyzed": runs_analyzed, "confidence": policy_confidence},
        }

    # ── Rule 2: COLD_REGIME (using dynamic thresholds) ────────────────────
    cold_game_signals: list[str] = []
    for game, g in game_summaries.items():
        long_e  = g["best_edge_long"]
        short_e = g["best_edge_short"] or 0.0
        total_g = g["total"]
        cold_ratio = g["cold_count"] / max(total_g, 1)

        # Condition A: edge divergence (long-term positive, short-term negative)
        if (long_e is not None
                and long_e > cold_edge_long_min
                and short_e < cold_edge_short_max):
            cold_game_signals.append(
                f"{game}: long-term edge {long_e:+.3f} but short-term {short_e:+.3f}"
            )
        # Condition B: majority of strategies in cold streak
        elif cold_ratio >= cold_streak_ratio and total_g >= cold_min_total:
            cold_game_signals.append(
                f"{game}: {g['cold_count']}/{total_g} strategies in neg streak"
                f" (≥{cold_streak_ratio:.0%})"
            )
        # Condition C: absolute short-term edge below threshold
        elif (g["best_edge_short"] is not None
              and short_e < cold_edge_abs_max
              and total_g >= cold_min_total):
            cold_game_signals.append(
                f"{game}: short-term edge {short_e:+.3f} (below {cold_edge_abs_max:+.3f})"
            )

    if cold_game_signals:
        reason = "; ".join(cold_game_signals)
        cal_id, score, label = _log_event(SIGNAL_STATE_COLD_REGIME, reason, cold_game_signals)
        return {
            "state":            SIGNAL_STATE_COLD_REGIME,
            "reason":           reason,
            "game_summaries":   game_summaries,
            "confidence_score": score,
            "confidence_label": label,
            "calibration_id":   cal_id,
            "policy": {
                "runs_analyzed":    runs_analyzed,
                "confidence":       policy_confidence,
                "retry_merge_rate": retry_merge_rate,
                "overall_merge_rate": overall_merge_rate,
            },
        }

    # ── Rule 3: SIGNAL_SATURATED (default when exhausted but not cold) ─────
    validated_games = [g for g in _GAMES if game_summaries[g]["has_validated"]]
    reason = (
        f"Strategies exist ({total_strategies} total"
        + (f", validated in: {', '.join(validated_games)}" if validated_games else "")
        + ") but no new signals — switch to meta-level research"
    )
    cal_id, score, label = _log_event(SIGNAL_STATE_SATURATED, reason, [])
    return {
        "state":            SIGNAL_STATE_SATURATED,
        "reason":           reason,
        "game_summaries":   game_summaries,
        "confidence_score": score,
        "confidence_label": label,
        "calibration_id":   cal_id,
        "policy": {
            "runs_analyzed":      runs_analyzed,
            "confidence":         policy_confidence,
            "retry_merge_rate":   retry_merge_rate,
            "overall_merge_rate": overall_merge_rate,
        },
    }


# ─── Regime-Aware Task Builders ───────────────────────────────────────────────

def _build_cold_regime_payload(signal_state: dict, backlog: str) -> dict:
    """
    Build a research task payload for COLD_REGIME state.
    Generates cold-phase analysis + regime-detection tasks.
    """
    reason = signal_state.get("reason", "")
    policy = signal_state.get("policy", {})
    retry_rate = policy.get("retry_merge_rate", 0.0)
    confidence = policy.get("confidence", "low")

    # Determine which task sub-type to generate based on adaptive policy
    # If retry has been effective → push adaptive_bet_sizing task first
    # Otherwise start with cold_phase_analysis → regime_detection → adaptive_bet_sizing
    if retry_rate >= 0.4 and confidence in ("medium", "high"):
        sub_type = "adaptive_bet_sizing"
        title = "Adaptive Bet Sizing — Cold Phase 降注策略設計"
        slug = "adaptive-bet-sizing-cold-phase"
        objective = "基於 regime 狀態設計降注（冷期）/ 升注（熱期）規則，與現有策略整合。"
        scope_lines = [
            "1. 定義 cold / hot regime 切換條件（基於 edge_30p / consecutive_neg_30p）",
            "2. 設計 bet_size_multiplier：cold_phase × 0.5, hot_phase × 1.5（可調）",
            "3. 回測 BIG_LOTTO / DAILY_539 / POWER_LOTTO 的降注效果（最近 300 期）",
            "4. 計算 regime-aware 預期收益 vs. 固定注額基準",
            "5. 整合至 strategy_states 的 `regime_bet_size` 欄位",
        ]
    elif reason and "cold_phase_analysis" not in str(backlog):
        sub_type = "cold_phase_analysis"
        title = "Cold Phase Analysis — 冷期特徵分析（Regime-Aware）"
        slug = "cold-phase-analysis-regime"
        objective = "分析當前冷期的長度、分佈、頻率，建立 regime 基準線，供後續模型使用。"
        scope_lines = [
            f"1. 背景：{reason[:200]}",
            "2. 計算各彩種（BIG_LOTTO / DAILY_539 / POWER_LOTTO）歷史冷期：",
            "   - 平均冷期長度（連續 edge < 0 的 periods）",
            "   - 最長冷期、中位數冷期",
            "   - 冷期後反彈概率（edge 從負轉正的速度）",
            "3. 建立 cold_regime_baseline.json：記錄各彩種冷期統計",
            "4. 評估當前冷期是否在歷史分佈範圍內（Z-score 或 percentile）",
            "5. 輸出結論：預計冷期結束時機（統計性）",
        ]
    else:
        sub_type = "regime_detection_model"
        title = "Regime Detection Model — 建立冷/熱期分類器"
        slug = "regime-detection-model"
        objective = "基於 cold_phase_analysis 結論，建立 binary regime classifier（cold / hot）。"
        scope_lines = [
            "1. 特徵工程：consecutive_neg_30p, edge_30p rolling mean, trend, z_score",
            "2. 訓練簡單閾值分類器（無需 ML，使用規則+統計）",
            "3. 回測分類準確率（以歷史冷/熱期標記為 ground truth）",
            "4. 輸出 regime_classifier.json：各彩種的分類規則與閾值",
            "5. 整合至 decision_engine_v3.py：影響 bet_sizing 和任務生成",
        ]

    prompt_markdown = f"""## Objective

{objective}

**類型**: `{sub_type}` — Regime-Aware Research（非傳統信號搜索）

**觸發原因**: Signal Exhaustion → COLD_REGIME 判定
{f'**冷期信號**: {reason[:300]}' if reason else ''}

## Scope

{chr(10).join(scope_lines)}

## Adaptive Policy Context

- 系統信心度：{confidence}
- retry merge rate：{retry_rate:.1%}（{'高 — 建議多重試舊候選' if retry_rate >= 0.4 else '低 — 建議分析而非重試'}）

## Constraints

- 不得修改 lottery_api/data/lottery_v2.db
- 分析結果必須有統計顯著性依據（n >= 30 draws）
- 不得基於 < 30 期數據聲稱找到 edge

## Acceptance Criteria

- 有量化的冷期特徵（平均長度、分佈、Z-score）
- 有基準線比較（vs. 歷史平均）
- 結論明確說明：此冷期是 normal / abnormal
- 有後續任務建議（下一個 regime-aware 研究方向）

## Handoff Notes

- backlog 來源：runtime/agent_orchestrator/backlog.md
- strategy_states 位置：lottery_api/data/strategy_states_*.json
- 完成後更新 wiki/games/<game>.md 的 regime 狀態區段
- 若確認為 normal cold phase：在 completed 文件標記 COLD_PHASE_NORMAL
- 若 abnormal：標記 COLD_PHASE_ANOMALY + 建議提高研究優先度
"""

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "_signal_state_type": sub_type,
    }


def _build_saturated_payload(signal_state: dict, backlog: str) -> dict:
    """
    Build a meta-level research task for SIGNAL_SATURATED state.
    System has validated strategies but no new edge — switch research mode.
    """
    reason = signal_state.get("reason", "")
    policy = signal_state.get("policy", {})
    confidence = policy.get("confidence", "low")
    retry_rate = policy.get("retry_merge_rate", 0.0)
    overall_rate = policy.get("overall_merge_rate", 0.0)

    game_summaries = signal_state.get("game_summaries", {})

    # Determine sub-task based on what's missing in the system
    # Priority: signal_quality_filter → shadow_strategy_tracking
    has_shadow = any("shadow" in s.lower() for s in (backlog or "").splitlines())
    if overall_rate < 0.30 and confidence in ("medium", "high"):
        sub_type = "signal_quality_filter"
        title = "Signal Quality Filter — 識別並過濾 noise 信號"
        slug = "signal-quality-filter"
        objective = "分析各彩種現有策略的信號品質，過濾 noise，保留真實 edge 候選。"
        scope_lines = [
            "1. 對每個策略計算 signal-to-noise ratio（基於 z_score, perm_p, mcnemar_p）",
            "2. 識別「假 edge」：edge_30p > 0 但 perm_p > 0.1 的策略",
            "3. 分類：NOISE / BORDERLINE / SIGNAL（各策略打標記）",
            "4. 輸出 signal_quality_report.json：各策略品質等級",
            "5. 建議：NOISE 策略暫停、BORDERLINE 追蹤、SIGNAL 加大 coverage",
            f"6. 整體合併率 {overall_rate:.0%} 偏低 — 分析原因（gate 過嚴 or 真無 edge）",
        ]
    elif not has_shadow:
        sub_type = "shadow_strategy_tracking"
        title = "Shadow Strategy Tracking — 建立 shadow_C 候選追蹤系統"
        slug = "shadow-strategy-tracking"
        objective = "建立自動 shadow 策略追蹤機制，讓系統在 SIGNAL_SATURATED 期間持續積累候選。"
        scope_lines = [
            "1. 定義 shadow 策略標準：edge_30p > 0.03, 連續 10 期正, perm_p < 0.2",
            "2. 掃描 strategy_states 中所有 None/unvalidated 策略，識別潛在 shadow_C",
            "3. 建立 shadow_tracking.json：追蹤每個候選的近期表現",
            "4. 設計自動升級規則：shadow_C → 正式研究任務的觸發條件",
            "5. 輸出第一批 shadow_C 候選清單（if any）",
        ]
    else:
        sub_type = "meta_level_review"
        title = "Meta-Level Strategy Review — 飽和期系統性複查"
        slug = "meta-level-strategy-review"
        objective = "系統進入 SIGNAL_SATURATED 狀態。進行跨彩種策略複查，確認現役策略健康度。"
        scope_lines = [
            "1. 複查三個彩種的現役策略 composite_score（是否仍 >= 0.5）",
            "2. 確認 RSM（Rolling Signal Monitor）是否需要更新基準期",
            "3. 評估是否有 strategy 應該從 validated → monitoring → pause",
            "4. 整理「下一批研究方向」候選（基於 backlog 殘餘項目）",
            "5. 若無新方向：建立「維護模式任務計劃」（每 N 期複查一次）",
        ]

    # Include adaptive policy recommendations
    policy_notes = []
    if retry_rate >= 0.4:
        policy_notes.append(f"retry 合併率 {retry_rate:.0%}（高）— 建議增加 retry 任務")
    if confidence == "low":
        policy_notes.append("policy 信心度低 — 積累更多 run 後策略將自動調整")

    # Build game signal summary lines outside f-string (no backslash in f-string)
    game_signal_lines = []
    for game, g in game_summaries.items():
        if g["total"] > 0:
            edge_str = (
                f"{g['best_edge_short']:+.3f}"
                if g["best_edge_short"] is not None
                else "無資料"
            )
            status_str = "已驗證" if g["has_validated"] else "未驗證"
            game_signal_lines.append(
                f"- **{game}**: {g['total']} 策略, {status_str}, 短期最佳 edge={edge_str}"
            )
    game_signal_block = "\n".join(game_signal_lines) if game_signal_lines else "（無策略資料）"
    policy_notes_block = "\n".join(f"- {note}" for note in policy_notes) if policy_notes else "- 建議：繼續積累 run 資料以提升信心度"

    prompt_markdown = f"""## Objective

{objective}

**類型**: `{sub_type}` — Meta-Level Research（SIGNAL_SATURATED 模式）

**觸發原因**: Signal Exhaustion → SIGNAL_SATURATED 判定
{f'**飽和原因**: {reason[:300]}' if reason else ''}

## System Signal Summary

{game_signal_block}

## Adaptive Policy Context

- 系統信心度：{confidence}
{policy_notes_block}

## Scope

{chr(10).join(scope_lines)}

## Constraints

- 不得修改 lottery_api/data/lottery_v2.db
- 不得基於 < 30 期數據聲稱找到新 edge
- 飽和期不應強制生成「新策略」任務 — 應聚焦品質與追蹤

## Acceptance Criteria

- 有清楚的現役策略健康度評估
- 有後續追蹤計劃（shadow 清單 or 複查時間表）
- 結論明確說明：SIGNAL_SATURATED 是否轉為 TRUE_EXHAUSTED 或 COLD_REGIME

## Handoff Notes

- backlog 來源：runtime/agent_orchestrator/backlog.md
- strategy_states 位置：lottery_api/data/strategy_states_*.json
- 完成後在 wiki/games/<game>.md 的 regime_status 標記：SATURATED
- 若發現任何 shadow_C 候選：加入 backlog 優先隊列
- 完成後需在 completed 文件留下摘要 + 下一個建議任務
"""

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "_signal_state_type": sub_type,
    }


def _build_meta_prompt(planner_provider: str, recent_completed: str) -> tuple[str, list[str], str]:
    backlog = common.read_backlog()
    if not backlog:
        raise ValueError("backlog.md missing or empty — skip")

    wiki_context, wiki_labels = _load_wiki_context(backlog)

    # ── CTO Strategy Focus injection ─────────────────────────────────────────
    # Read active/shadow strategy state set by cto_review_tick strategy review.
    # Append a concise focus block so the LLM planner is aware of CTO decisions.
    try:
        strat_states = db.get_all_active_strategy_states()
        if strat_states:
            focus_lines = ["## CTO Strategy Focus (auto-injected)"]
            for s in strat_states:
                game = s.get("game_type", "")
                focus_raw = s.get("planner_focus") or "{}"
                try:
                    import json as _json
                    focus = _json.loads(focus_raw)
                except Exception:
                    focus = {}
                focus_mode = focus.get("focus", "unknown")
                active = s.get("active_strategy") or "—"
                active_edge = s.get("active_edge")
                shadow = s.get("shadow_strategy") or "—"
                shadow_edge = s.get("shadow_edge")
                edge_str = f"edge={active_edge:.3f}" if active_edge is not None else ""
                shadow_edge_str = f"edge={shadow_edge:.3f}" if shadow_edge is not None else ""
                focus_lines.append(
                    f"- **{game}**: focus=`{focus_mode}` | active=`{active}` {edge_str} | shadow=`{shadow}` {shadow_edge_str}"
                )
            strategy_focus_block = "\n".join(focus_lines)
            wiki_context = (wiki_context.rstrip() + "\n\n" + strategy_focus_block).strip()
    except Exception:
        pass  # Strategy focus is non-critical; never block planning

    # ── CTO Directives + Negative Space injection ─────────────────────────────
    try:
        wiki_context, seen_directive_ids = _build_directive_context(wiki_context)
        if seen_directive_ids:
            db.tick_planner_directive_cycles(seen_directive_ids)
    except Exception:
        pass  # Directive injection is non-critical

    meta_prompt = common.build_planner_meta_prompt(
        backlog=backlog,
        recent_completed=recent_completed,
        wiki_context=wiki_context,
        planner_provider=planner_provider,
    )
    return backlog, wiki_labels, meta_prompt


def _build_directive_context(wiki_context: str) -> tuple[str, list]:
    """
    Read active CTO→Planner directives + Negative Space Registry.
    Returns (augmented_wiki_context, [directive_ids_seen]).
    """
    import json as _json
    blocks = []
    directive_ids = []

    # ── CTO→Planner Directives ───────────────────────────────────────────────
    try:
        directives = db.get_active_planner_directives()
        if directives:
            lines = ["## CTO→Planner Directives (active — do NOT ignore)"]
            for d in directives:
                directive_ids.append(d["directive_id"])
                lines.append(
                    f"\n### {d['directive_id']} [{d.get('game_type','?')}] focus={d['focus_direction']}"
                )
                if d.get("forbidden_families"):
                    lines.append(f"- **FORBIDDEN signal families**: {', '.join(d['forbidden_families'])}")
                if d.get("required_validation"):
                    lines.append(f"- **Required validation steps**: {', '.join(d['required_validation'])}")
                if d.get("promotion_targets"):
                    lines.append(f"- **Promotion audit targets**: {', '.join(d['promotion_targets'])}")
                if d.get("kill_targets"):
                    lines.append(f"- **Kill targets** (deprecate immediately): {', '.join(d['kill_targets'])}")
                if d.get("budget_hint"):
                    lines.append(f"- budget_hint: {d['budget_hint']}")
                if d.get("note"):
                    lines.append(f"- note: {d['note']}")
                remaining = max(0, d.get("expires_after_cycles", 10) - d.get("cycle_count", 0))
                lines.append(f"- Expires in: {remaining} planner cycles")
            blocks.append("\n".join(lines))
    except Exception:
        pass

    # ── Negative Space Registry ──────────────────────────────────────────────
    try:
        ns_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "runtime", "agent_orchestrator", "research_registry", "negative_space.json",
        )
        if os.path.exists(ns_path):
            with open(ns_path, "r", encoding="utf-8") as _f:
                ns_data = _json.load(_f)
            lines = ["## Negative Space Registry (MUST NOT re-research these families)"]
            for game, entries in ns_data.items():
                if game.startswith("_") or not entries:
                    continue
                lines.append(f"\n### {game}")
                for e in entries:
                    status = e.get("status", "REJECT")
                    family = e.get("family", "?")
                    reason = e.get("reason", "")
                    retry = e.get("retry_condition", "不重試")
                    lines.append(f"- **{family}** [{status}]: {reason} | retry: {retry}")
            blocks.append("\n".join(lines))
    except Exception:
        pass

    if blocks:
        wiki_context = (wiki_context.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(blocks)).strip()

    return wiki_context, directive_ids


def _print_dry_run_preview(meta_prompt: str, wiki_labels: list[str]):
    preview = meta_prompt[:2000]
    print("Loaded wiki context from %d page(s): %s" % (len(wiki_labels), ", ".join(wiki_labels) or "none"))
    print("=== DRY-RUN: meta-prompt preview ===")
    print(preview)
    if len(meta_prompt) > len(preview):
        print("\n=== meta-prompt truncated at 2000 chars ===")
    print("\n=== wiki_context loaded from %d page(s) ===" % len(wiki_labels))
    if wiki_labels:
        print("\n".join(wiki_labels))


def _call_planner(meta_prompt: str, planner_provider: str) -> tuple[str, str]:
    output_last_message_path = None
    try:
        runtime, command = common.planner_command(meta_prompt, planner_provider)
        decision = execution_policy.evaluate("planner.call", scope="main", provider=runtime)
        if not decision.allowed:
            execution_policy.record_skip(decision, requested_provider=planner_provider)
            return "fallback", decision.skip_reason or "SAFE_RUN_BLOCK"
        execution_policy.record_pre_call(decision, requested_provider=planner_provider)
        if runtime == "codex":
            with tempfile.NamedTemporaryFile(prefix="planner-last-message-", suffix=".txt", delete=False) as handle:
                output_last_message_path = handle.name
            prompt_arg = command[-1]
            command = [*command[:-1], "--output-last-message", output_last_message_path, prompt_arg]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if output_last_message_path and os.path.exists(output_last_message_path):
            with open(output_last_message_path, "r", encoding="utf-8") as handle:
                last_message = handle.read().strip()
            if last_message:
                return runtime, last_message
        return runtime, result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        raw = f"{planner_provider} planner timed out (180s)"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw
    except Exception as exc:
        raw = f"{planner_provider} planner error: {exc}"
        logger.warning(FALLBACK_WARNING, raw)
        return "fallback", raw
    finally:
        if output_last_message_path and os.path.exists(output_last_message_path):
            try:
                os.remove(output_last_message_path)
            except OSError:
                pass


def _extract_planner_payload(raw: str) -> Optional[dict]:
    json_str = raw.strip()
    if "```" in json_str:
        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", json_str)
        if fenced:
            json_str = fenced.group(1).strip()
    if not json_str.startswith("{"):
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start != -1 and end > start:
            json_str = json_str[start:end]
    try:
        return json.loads(json_str)
    except Exception:
        return None


def _payload_has_template_placeholders(payload: dict) -> bool:
    title = str(payload.get("title", "")).strip()
    slug = str(payload.get("slug", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()
    markers = [
        "<任務標題",
        "<kebab-case",
        "<完整的 8 小時任務 prompt",
        "任務標題，中英文皆可",
        "kebab-case 英文識別碼",
        "完整的 8 小時任務 prompt",
        "{{",
        "}}",
    ]
    combined = "\n".join([title, slug, prompt_markdown])
    return any(marker in combined for marker in markers)


def _validate_payload(payload: dict) -> tuple[bool, str]:
    title = str(payload.get("title", "")).strip()
    slug = str(payload.get("slug", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()

    if not title or not slug or not prompt_markdown:
        return False, "payload missing required keys: title/slug/prompt_markdown"
    if len(title) > 40:
        return False, "title exceeds 40 characters"
    if _payload_has_template_placeholders(payload):
        return False, "planner output still contains template placeholders"
    if not re.fullmatch(r"[a-z0-9-]{3,40}", common.slugify(slug) or ""):
        return False, "slug is not valid kebab-case after normalization"
    required_sections = [
        "## Objective",
        "## Scope",
        "## Constraints",
        "## Acceptance Criteria",
        "## Handoff Notes",
    ]
    for section in required_sections:
        if section not in prompt_markdown:
            return False, f"prompt_markdown missing section: {section}"
    if len(prompt_markdown) < 200:
        return False, "prompt_markdown too short"
    return True, ""


def _build_retry_prompt(meta_prompt: str, reason: str) -> str:
    return (
        meta_prompt
        + "\n\n"
        + "上一輪輸出無效，請重新輸出，且只輸出 JSON。\n"
        + f"無效原因：{reason}\n"
        + "請輸出實際值，不得包含模板詞或佔位符。"
    )


def _planner_candidates(provider: str) -> list[str]:
    requested = common.normalize_planner_provider(provider)
    ordered = [requested]
    ordered.append("claude" if requested == "codex" else "codex")
    deduped = []
    for item in ordered:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _attempt_planner_payload(meta_prompt: str, planner_provider: str) -> tuple[Optional[dict], str, str, str]:
    planner_source, raw = _call_planner(meta_prompt, planner_provider)
    parse_or_validate_error = ""
    payload = None

    if planner_source in ("claude", "codex"):
        payload = _extract_planner_payload(raw)
        if payload is None:
            parse_or_validate_error = "failed to parse planner JSON output"
        else:
            ok, reason = _validate_payload(payload)
            if not ok:
                parse_or_validate_error = reason

        if parse_or_validate_error:
            retry_prompt = _build_retry_prompt(meta_prompt, parse_or_validate_error)
            retry_source, retry_raw = _call_planner(retry_prompt, planner_provider)
            if retry_source in ("claude", "codex"):
                retry_payload = _extract_planner_payload(retry_raw)
                if retry_payload is not None:
                    ok, reason = _validate_payload(retry_payload)
                    if ok:
                        payload = retry_payload
                        raw = retry_raw
                        planner_source = retry_source
                        parse_or_validate_error = ""
                    else:
                        raw = retry_raw
                        parse_or_validate_error = reason
                else:
                    raw = retry_raw

    return payload, planner_source, raw, parse_or_validate_error


def _generate_planner_payload(meta_prompt: str, planner_provider: str) -> tuple[Optional[dict], str, str, str, str]:
    requested_provider = common.normalize_planner_provider(planner_provider)
    last_raw = ""
    attempt_errors = []

    for candidate in _planner_candidates(requested_provider):
        available, reason = common.provider_available("planner", candidate)
        if not available:
            attempt_errors.append(f"{candidate} unavailable: {reason}")
            continue

        logger.info("Calling %s to generate next task prompt...", common.planner_provider_label(candidate))
        payload, planner_source, raw, parse_error = _attempt_planner_payload(meta_prompt, candidate)
        last_raw = raw
        if payload is not None:
            return payload, planner_source, candidate, requested_provider, ""

        if _planner_error_is_runtime_blocker(raw):
            detail = raw
        elif parse_error and raw:
            detail = f"{parse_error}; raw={raw[:300]}"
        else:
            detail = parse_error or raw or f"{candidate} returned no usable output"
        attempt_errors.append(f"{candidate}: {detail}")

    reason = " | ".join(attempt_errors) if attempt_errors else "no planner providers available"
    return None, "fallback", requested_provider, requested_provider, reason


def _planner_error_is_runtime_blocker(reason: str) -> bool:
    lowered = str(reason or "").lower()
    markers = [
        "usage limit",
        "hit your limit",
        "hit your usage limit",
        "quota",
        "not logged in",
        "auth failed",
        "permission denied",
        "timed out",
    ]
    return any(marker in lowered for marker in markers)


def _extract_section_lines(markdown: str, header: str) -> list[str]:
    """
    Extract bullet/number lines under a markdown header, stopping at next header.
    """
    lines = str(markdown or "").splitlines()
    out = []
    in_section = False
    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("## "):
            if in_section:
                break
            in_section = (line.strip() == header)
            continue
        if not in_section:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"^\d+\.\s+", "", stripped)
        if stripped:
            out.append(stripped)
    return out


def _build_task_contract(payload: dict) -> dict:
    title = str(payload.get("title", "")).strip()
    prompt_markdown = str(payload.get("prompt_markdown", "")).strip()
    objective_lines = _extract_section_lines(prompt_markdown, "## Objective")
    scope = _extract_section_lines(prompt_markdown, "## Scope")
    constraints = _extract_section_lines(prompt_markdown, "## Constraints")
    acceptance = _extract_section_lines(prompt_markdown, "## Acceptance Criteria")
    handoff = _extract_section_lines(prompt_markdown, "## Handoff Notes")

    # Detect task type:
    # - explicit payload.task_type from planner/prompt generator
    # - fallback to internal signal type for replacement tasks (e.g. monitoring)
    task_type = str(
        payload.get("task_type")
        or payload.get("_signal_state_type")
        or ""
    ).strip()

    contract = {
        "version": "1.0",
        "task_type": task_type,
        "objective": objective_lines[0] if objective_lines else title,
        "scope": scope or [f"完成任務：{title}"],
        "constraints": constraints or [
            "seed=42",
            "不得修改 lottery_api/data/lottery_v2.db",
            "不得直接改寫 strategy_states 配置檔",
        ],
        "acceptance_tests": acceptance or [
            "輸出需包含可驗證結論與證據",
            "列出異動檔案或明確標註無異動",
        ],
        "required_outputs": [
            "completed_markdown",
            "task_result_json",
            "changed_files_list",
        ],
        "forbidden_changes": [
            "lottery_api/data/lottery_v2.db",
            "lottery_api/data/strategy_states_",
        ],
        "handoff_questions": handoff or [
            "本輪結論是否達到 Acceptance Criteria？",
            "若未達標，下一輪需要調整哪個假設或範圍？",
        ],
    }

    # ── Deep Research strategy requirements ───────────────────────────────────
    if task_type == "deep_research":
        contract["strategy_min_count"] = 3
        contract["mc_min_n"] = 1000
        contract["backtest_windows"] = [150, 500, 1500]
        contract["required_strategy_fields"] = [
            "strategy_name",
            "family",
            "edge_150",
            "edge_500",
            "edge_1000",          # edge_1000 OR edge_1500 required
            "mc_status",          # "PASS" | "FAIL" | "N/A"
            "vs_incumbent",       # float: edge difference vs current best (positive = better)
            "incumbent_name",     # name of strategy being compared against
            "validation_tier",    # T0_IDEA | T1_MC_PASS | T2_THREE_WINDOW_PASS | T3_INCUMBENT_PASS | T4_DEPLOYABLE
            "promotion_blocker",  # reason why NOT promoted (or "NONE" if T3+)
            "next_action",        # e.g. "McNemar vs incumbent" | "deploy" | "shadow_watch" | "reject"
        ]
        contract["acceptance_tests"] = contract["acceptance_tests"] + [
            "## Strategy Output Table section present with ≥3 distinct strategy names",
            "Each strategy row includes ALL required_strategy_fields (no blank cells)",
            "At least one strategy edge_150 > 0 (else mark FAILED_NO_EDGE); if all edges <= 0 mark FAILED_NO_EDGE",
            "If any strategy edge > 0 but vs_incumbent <= 0 for all candidates → mark FAILED_WEAK_EDGE (not FAILED_NO_EDGE)",
            "Monte Carlo completed: seed=42, n≥1000",
            "validation_tier field set for every strategy row (T0–T4 as defined in wiki/system/validation_gates.md)",
            "promotion_blocker field filled for every non-T4 strategy (never blank)",
            "No strategy with mc_status=PASS and vs_incumbent<=0 may have promotion_blocker='NONE'",
            "If all candidates vs_incumbent <= 0 → output must contain FAILED_WEAK_EDGE verdict, not promotion candidate",
        ]
        contract["failure_classifications"] = {
            "FAILED_NO_EDGE":   "All strategy edges ≤ 0 across all windows",
            "FAILED_WEAK_EDGE": "Positive edge exists but vs_incumbent ≤ 0 for all candidates; no promotion warranted",
            "REPLAN_REQUIRED":  "Missing required_strategy_fields or promotion_blocker blank for non-T4 strategies",
            "FAILED_ACCEPTANCE":"Output present but acceptance_tests not satisfied (e.g. missing Strategy Output Table)",
        }

    return contract


_STRATEGY_TABLE_FORMAT_NOTE = (
    "\n---\n"
    "## Strategy Output Table Format (Orchestrator Enforced)\n\n"
    "⚠️ **每個策略只能佔一行（一行 = 一個策略，非一個視窗）**。\n"
    "Use English column headers. Do NOT use Chinese columns or per-window-row format.\n\n"
    "Required format:\n\n"
    "```\n"
    "## Strategy Output Table\n\n"
    "| strategy_name | family | edge_150 | edge_500 | edge_1000 | mc_status | vs_incumbent | incumbent_name | validation_tier | promotion_blocker | next_action |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
    "| my_strategy | POWER_LOTTO | +0.039 | +0.041 | — | PASS | +0.031 | freq_rev_v2 | T3_INCUMBENT_PASS | NONE | shadow_watch |\n"
    "```\n\n"
    "Column rules:\n"
    "- `edge_150`: required (must be a numeric value — this is the primary backtest evidence)\n"
    "- `edge_500` / `edge_1000`: optional — use `—` if that window was not yet run\n"
    "- `edge_1000`: acceptable blank if 1000-draw window not run\n"
    "- `mc_status`: PASS | FAIL | N/A — never blank\n"
    "- `vs_incumbent`: float, positive = better than current best — never blank\n"
    "- `validation_tier`: T0_IDEA | T1_MC_PASS | T2_THREE_WINDOW_PASS | T3_INCUMBENT_PASS | T4_DEPLOYABLE\n"
    "- `promotion_blocker`: reason NOT promoted, or NONE for T3+ (never blank for non-T4 strategies)\n"
    "- `T1_MC_PASS` is NOT a promotion candidate: do not use `promotion_blocker=NONE`; use `MC_ONLY_NO_THREE_WINDOW` and a non-promotion `next_action` such as `run_500w` or `shadow_watch`\n\n"
)


def _build_worker_prompt_with_contract(prompt_markdown: str, contract: dict) -> str:
    contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
    # Inject table format spec for deep_research tasks
    strategy_table_note = _STRATEGY_TABLE_FORMAT_NOTE if contract.get("required_strategy_fields") else ""
    return (
        "## Task Contract (Orchestrator Enforced)\n\n"
        "Worker 必須遵守以下契約，否則任務會被標記為 REPLAN_REQUIRED：\n\n"
        f"```json\n{contract_json}\n```\n"
        f"{strategy_table_note}"
        "---\n\n"
        f"{prompt_markdown.strip()}\n"
    )


# ---------------------------------------------------------------------------
# Idle fallback task policy
# ---------------------------------------------------------------------------
# When the primary task AND the AUTO-MONITOR replacement are both blocked
# (e.g. daily cap), the planner tries P1→P6 light fallback tasks so it never
# idles unnecessarily.  Each candidate is date-keyed so it runs at most once
# per UTC calendar day.  FAILED tasks do NOT block the day (retry allowed).

_FALLBACK_PRIORITY_ORDER = [
    "watchdog",
    "cto_precheck",
    "queue_hygiene",
    "kb_sync",
    "ux_observability",
    "light_health",
]


def _build_fallback_candidates(today_label: str) -> list[dict]:
    """Return ordered list of fallback task payload dicts (P1 → P6)."""
    return [
        {
            "title": "[FALLBACK-P1] 系統看門狗狀態巡查",
            "slug": f"fallback-watchdog-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "巡查系統看門狗狀態：active_strategy_state、DAILY_539 3000p edge、POWER_LOTTO shadow 追蹤狀態。\n\n"
                "## Scope\n"
                "- 查詢 runtime/agent_orchestrator/orchestrator.db 中 active_strategy_state、strategy_live_state、strategy_reviews 表\n"
                "- 確認 DAILY_539 最佳邊際是否有 3000p 以上資料\n"
                "- 確認 POWER_LOTTO shadow 策略是否在追蹤\n"
                "- 輸出結果到 outputs/watchdog_status.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改 DB\n"
                "- seed=42\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/watchdog_status.md 包含 active_strategy_state 快照\n"
                "- 列出 DAILY_539 / POWER_LOTTO / BIG_LOTTO 各遊戲最新邊際值\n"
                "- 標注任何異常狀態（edge 下滑、shadow 停止追蹤等）\n\n"
                "## Handoff Notes\n"
                "- 若發現 active_strategy_state 異常或 edge 下滑，提出建議行動\n"
            ),
            "_dedupe_key": f"fallback:watchdog:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
        {
            "title": "[FALLBACK-P2] CTO 每日預檢報告",
            "slug": f"fallback-cto-precheck-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "彙整今日任務執行摘要：已完成、失敗、跳過的任務，識別需要人工介入的事項。\n\n"
                "## Scope\n"
                "- 查詢最近 24h 內 agent_tasks 各狀態分佈\n"
                "- 列出 FAILED / REPLAN_REQUIRED 任務及其錯誤訊息\n"
                "- 列出 SKIPPED_DUPLICATE_DAILY_CAP 任務（防止監控氾濫）\n"
                "- 摘要目前 active_strategy_state 與最新 strategy_reviews\n"
                "- 輸出到 outputs/cto_daily_precheck.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改 DB\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/cto_daily_precheck.md 包含任務狀態統計表\n"
                "- 列出所有需要人工介入的任務（含錯誤原因）\n"
                "- 提供今日系統健康度評估（良好 / 需注意 / 異常）\n\n"
                "## Handoff Notes\n"
                "- 若有超過 2 個 FAILED 任務，標記為需要 CTO 審查\n"
            ),
            "_dedupe_key": f"fallback:cto_precheck:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
        {
            "title": "[FALLBACK-P3] 任務佇列衛生檢查",
            "slug": f"fallback-queue-hygiene-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "檢查任務佇列健康狀態：識別卡住的任務、重複任務、孤立的 agent_locks。\n\n"
                "## Scope\n"
                "- 查詢 agent_tasks 中 QUEUED 超過 30 分鐘的任務\n"
                "- 查詢 agent_tasks 中 RUNNING 超過 2 小時的任務\n"
                "- 查詢 agent_locks 表，確認無孤立鎖\n"
                "- 找出 dedupe_key 重複的 QUEUED 任務（應只保留最新）\n"
                "- 輸出到 outputs/queue_hygiene.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改 DB（發現問題僅記錄，不自動清除）\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/queue_hygiene.md 列出所有可疑任務\n"
                "- 對每個問題任務提供建議行動（手動清除 / 等待 / 無需處理）\n"
                "- 列出 agent_locks 當前狀態\n\n"
                "## Handoff Notes\n"
                "- 若發現超過 3 個卡住任務，提升為 CTO 行動項\n"
            ),
            "_dedupe_key": f"fallback:queue_hygiene:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
        {
            "title": "[FALLBACK-P4] 知識庫同步確認",
            "slug": f"fallback-kb-sync-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "確認知識庫（wiki/lessons）與最新程式碼變更同步，並驗證 AUTO-MONITOR Prompt Contract。\n\n"
                "## Scope\n"
                "- 列出最近 7 天 git log 中異動的主要模組（orchestrator/*.py, lottery_api/*.py）\n"
                "- 確認 wiki/ 目錄中對應文件是否已更新\n"
                "- 驗證 orchestrator/planner_decision.py 中 AUTO-MONITOR prompt template 格式正確\n"
                "- 確認 wiki/lessons/ 中最新 lesson 與近期 FAILED 任務原因對應\n"
                "- 輸出到 outputs/kb_sync_status.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改任何檔案\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/kb_sync_status.md 列出同步狀態\n"
                "- 列出所有「程式碼已改但 wiki 未更新」的項目\n"
                "- 驗證 AUTO-MONITOR prompt 包含 7 個必要輸出區塊\n\n"
                "## Handoff Notes\n"
                "- 若有超過 5 個未同步項目，建議排入 wiki_update 任務\n"
            ),
            "_dedupe_key": f"fallback:kb_sync:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
        {
            "title": "[FALLBACK-P5] UX 可觀測性巡查",
            "slug": f"fallback-ux-observability-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "巡查 orchestration UI 覆蓋率，確認 tick_events 中所有事件類型都有對應的 UI 展示。\n\n"
                "## Scope\n"
                "- 列出最近 24h tick_log 中出現的所有 event_type\n"
                "- 確認每個 event_type 是否有對應的 UI 標籤或顯示邏輯（在 lottery_api/ 中搜尋）\n"
                "- 識別新增的事件類型（如 PLANNER_SKIP_MONITORING_DAILY_CAP、PLANNER_CREATE_FALLBACK_TASK）是否已有 UI 支援\n"
                "- 輸出到 outputs/ux_observability.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改任何檔案\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/ux_observability.md 列出事件覆蓋情況\n"
                "- 標注「有事件但無 UI 支援」的項目\n"
                "- 提供 UI gap 修復優先順序建議\n\n"
                "## Handoff Notes\n"
                "- 若 PLANNER_CREATE_FALLBACK_TASK 事件無 UI 支援，標記為高優先級\n"
            ),
            "_dedupe_key": f"fallback:ux_observability:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
        {
            "title": "[FALLBACK-P6] Light Worker 健康檢查",
            "slug": f"fallback-light-health-{today_label}",
            "prompt_markdown": (
                "## Objective\n"
                "檢查 light worker 運作健康狀態：launchd 註冊、最近 tick 記錄、jsonl 錯誤。\n\n"
                "## Scope\n"
                "- 確認 ~/Library/LaunchAgents/com.kelvin.lottery.light-worker.plist 存在且已載入\n"
                "- 查詢最近 2h light_worker.jsonl 中的 event_type 分佈\n"
                "- 識別 LIGHT_WORKER_FAILED / LIGHT_WORKER_SKIP_IDLE_NO_TASK 的頻率\n"
                "- 確認 light worker 平均延遲在 60s 以內\n"
                "- 輸出到 outputs/light_worker_health.md\n\n"
                "## Constraints\n"
                "- 限讀取，不得修改任何檔案\n"
                "- 不得修改 lottery_api/data/lottery_v2.db\n"
                "- 不得直接改寫 strategy_states 配置檔\n\n"
                "## Acceptance Criteria\n"
                "- 輸出 outputs/light_worker_health.md 包含 launchd 狀態\n"
                "- 列出最近 2h 的 event_type 統計\n"
                "- 標注任何 FAILED 或異常狀態\n\n"
                "## Handoff Notes\n"
                "- 若 launchd 未載入或最近 2h 無 tick，標記為緊急問題\n"
            ),
            "_dedupe_key": f"fallback:light_health:{today_label}",
            "_regime_state": "fallback_idle",
            "_confidence_snapshot": None,
        },
    ]


# ---------------------------------------------------------------------------
# Winner Follow-up Lane
# ---------------------------------------------------------------------------
# When a verified winner / candidate strategy is found (classification=WINNER,
# or backlog contains winner markers), the planner emits targeted follow-up
# research tasks even when SIGNAL_EXHAUSTED_ALL is active.
#
# Subtypes (daily cap: 1 per subtype per winner per day):
#   param_opt        — gate-size / ewma-decay parameter optimisation
#   prod_validation  — production-depth validation (150/500/1000/1500, MC n≥5000)
#   deployment       — strategy spec, state update, fallback/rollback plan
# ---------------------------------------------------------------------------

_WINNER_SUBTYPES = ["param_opt", "prod_validation", "deployment"]


# ---------------------------------------------------------------------------
# Post-Deployment Optimization Lane
# ---------------------------------------------------------------------------
# Purpose: keep research momentum after winner deployment by generating
# concrete optimization / risk-control tasks for active deployed strategies.
#
# Trigger (evaluated only on pre-idle path):
#   1) active_strategy_state has active strategy
#   2) active strategy classified as WINNER/VALIDATED/APPROVE_STRATEGY
#      (or inferred from today's completed winner_followup lifecycle)
#   3) today's winner_followup lifecycle completed for that strategy
#   4) fallback / forced exploration / exploration-router did not create tasks
#   5) daily cap not exhausted
#
# Daily cap: independent from fallback/monitoring/forced exploration.
# ---------------------------------------------------------------------------
POST_DEPLOYMENT_OPTIMIZATION_DAILY_CAP = 2
_POST_DEPLOYMENT_SUBTYPES = [
    "live_monitoring_calibration",
    "rollback_simulation",
    "shadow_strategy_challenge",
    "h6_variant_hardening",
    "prediction_output_quality_audit",
    "production_drift_detection",
]
_POST_DEPLOYMENT_SUBTYPE_TITLES = {
    "live_monitoring_calibration": "Live Monitoring Calibration",
    "rollback_simulation": "Rollback Simulation",
    "shadow_strategy_challenge": "Shadow Strategy Challenge",
    "h6_variant_hardening": "Variant Hardening",
    "prediction_output_quality_audit": "Prediction Output Quality Audit",
    "production_drift_detection": "Production Drift Detection",
    "rollback_followup": "Rollback Follow-up Validation",
}

# Patterns that indicate a winner / candidate strategy in backlog text.
# NOTE: avoid broad case-insensitive \bWINNER\b which matches 'winner' in
# 'no winner strategies'. Only match uppercase WINNER or structural markers.
_WINNER_BACKLOG_PATTERNS = [
    r"\bclassification\s*[=:]\s*WINNER\b",   # classification = WINNER (case-insensitive key, uppercase val)
    r"\bH\d+_gate_mk\d+",                     # H6_gate_mk20 style
    r"\bew\d+\b",                              # ew85 style
    r"\bcandidate.*MC\s+PASS",
    r"\bMC\s+PASS.*edge\s*[+>]",
    r"\[STRATEGY_WINNER\]",
    r"\[WINNER_CANDIDATE\]",
]

import re as _re


def _detect_winner_strategies(backlog: str) -> list[dict]:
    """Scan backlog text for winner / candidate strategy markers.

    Returns a list of winner info dicts:
      {game, strategy_name, edge_150p, edge_1500p, mc_pass, classification, raw_line}

    Each dict is built from the matching line and surrounding context (±5 lines);
    fields may be None when the regex cannot extract a precise value.
    """
    winners: list[dict] = []
    seen_strategies: set[str] = set()
    lines = backlog.splitlines()

    for idx, line in enumerate(lines):
        matched = any(_re.search(pat, line, _re.IGNORECASE) for pat in _WINNER_BACKLOG_PATTERNS)
        if not matched:
            continue

        # Build context window: ±5 lines around the matching line
        ctx_start = max(0, idx - 5)
        ctx_end = min(len(lines), idx + 6)
        context = "\n".join(lines[ctx_start:ctx_end])

        # Try to extract strategy name from the matching line or context.
        # Search in priority order (most specific first) to avoid matching a
        # short bare 'H6' that appears in a heading before 'H6_gate_mk20→ew85'.
        _STRAT_PRIO = [
            r"H\d+_gate_mk\d+(?:[→>→]\S+)?",  # H6_gate_mk20→ew85
            r"\b\w+_gate_\w+\b",               # any_gate_xxx
            r"H\d+[a-zA-Z_]\w*",               # H6_xxx (not bare H6)
        ]
        strategy_name = "UNKNOWN"
        for _sp in _STRAT_PRIO:
            _sm = _re.search(_sp, context, _re.IGNORECASE)
            if _sm:
                strategy_name = _sm.group(0)
                break

        if strategy_name in seen_strategies:
            continue
        seen_strategies.add(strategy_name)

        # Try to extract game type from context
        game_match = _re.search(
            r"\b(DAILY_539|BIG_LOTTO|POWER_LOTTO|539|BIG|POWER)\b", context, _re.IGNORECASE
        )
        game_raw = game_match.group(1).upper() if game_match else "DAILY_539"
        game = (
            "DAILY_539" if "539" in game_raw
            else "BIG_LOTTO" if "BIG" in game_raw
            else "POWER_LOTTO" if "POWER" in game_raw
            else game_raw
        )

        # Try to extract edge values
        edge_150p = None
        edge_1500p = None
        edge_match_150 = _re.search(r"150[p期]?\s*[\s:=]\s*([+\-]?\d+\.?\d*)%?", context, _re.IGNORECASE)
        if not edge_match_150:
            edge_match_150 = _re.search(r"150[p期]?\s+edge[:\s]+([+\-]?\d+\.?\d*)%?", context, _re.IGNORECASE)
        if edge_match_150:
            try:
                val = float(edge_match_150.group(1))
                # Values like 9.5 mean 9.5% — normalize to fraction only if > 1
                edge_150p = val / 100.0 if abs(val) > 1 else val
            except ValueError:
                pass
        edge_match_1500 = _re.search(r"(?:1000|1500)[p期]?\s*[\s:=]\s*([+\-]?\d+\.?\d*)%?", context, _re.IGNORECASE)
        if not edge_match_1500:
            edge_match_1500 = _re.search(r"(?:1000|1500)[p期]?\s+edge[:\s]+([+\-]?\d+\.?\d*)%?", context, _re.IGNORECASE)
        if edge_match_1500:
            try:
                val = float(edge_match_1500.group(1))
                edge_1500p = val / 100.0 if abs(val) > 1 else val
            except ValueError:
                pass

        mc_pass = bool(_re.search(r"\bMC\s+PASS\b", context, _re.IGNORECASE))

        winners.append({
            "game": game,
            "strategy_name": strategy_name,
            "edge_150p": edge_150p,
            "edge_1500p": edge_1500p,
            "mc_pass": mc_pass,
            "classification": "WINNER",
            "raw_line": line[:200],
        })
        logger.debug("[WinnerFollowup] Detected winner from backlog: %s / %s", game, strategy_name)

    # Also scan strategy_states JSON files for validated strategies with positive edge
    try:
        import glob as _glob
        state_files = _glob.glob("lottery_api/data/strategy_states_*.json")
        for path in state_files:
            try:
                with open(path) as _f:
                    states = json.load(_f)
                for strat_name, s in states.items():
                    if strat_name in seen_strategies:
                        continue
                    cls = (s.get("classification") or "").upper()
                    vs = (s.get("validated_status") or "").lower()
                    e150 = s.get("edge_150p")
                    e1500 = s.get("edge_1500p") or s.get("edge_500p")
                    if (
                        cls in ("WINNER", "PROMOTED", "APPROVED")
                        or vs in ("validated", "active", "promoted")
                    ) and e150 is not None and e150 > 0 and e1500 is not None and e1500 > 0:
                        game_raw = s.get("lottery_type", path.replace("lottery_api/data/strategy_states_", "").replace(".json", ""))
                        seen_strategies.add(strat_name)
                        winners.append({
                            "game": game_raw,
                            "strategy_name": strat_name,
                            "edge_150p": e150,
                            "edge_1500p": e1500,
                            "mc_pass": True,
                            "classification": cls or vs.upper(),
                            "raw_line": f"strategy_states: {path}",
                        })
                        logger.debug("[WinnerFollowup] Detected winner from strategy_states: %s / %s", game_raw, strat_name)
            except Exception as _ex:
                logger.debug("[WinnerFollowup] Could not read %s: %s", path, _ex)
    except Exception as _ex:
        logger.debug("[WinnerFollowup] strategy_states scan error: %s", _ex)

    return winners


def _build_winner_followup_payload(winner: dict, subtype: str, today_label: str) -> dict:
    """Build the task payload dict for a winner follow-up task.

    subtype: 'param_opt' | 'prod_validation' | 'deployment'
    """
    game = winner["game"]
    strategy_name = winner["strategy_name"]
    edge_150p = winner.get("edge_150p")
    edge_1500p = winner.get("edge_1500p")
    mc_pass_str = "MC PASS ✅" if winner.get("mc_pass") else "MC status unknown"

    safe_strat = strategy_name.replace("→", "_").replace("/", "_")
    dedupe_key = f"winner_followup:{safe_strat}:{subtype}:{today_label}"

    edge_str = ""
    if edge_150p is not None:
        edge_str += f"- 150期 edge: {edge_150p*100:+.2f}%\n"
    if edge_1500p is not None:
        edge_str += f"- 1500期 edge: {edge_1500p*100:+.2f}%\n"

    if subtype == "param_opt":
        title = f"[WINNER-FOLLOWUP] {game} {strategy_name} — Parameter Optimisation"
        slug = f"winner_followup_{safe_strat}_param_opt_{today_label}"
        prompt_markdown = f"""# {title}

## Context
Winner / candidate strategy detected: **{strategy_name}** ({game})
{edge_str}{mc_pass_str}

## Objective
Systematically optimise gate and decay parameters to improve robustness.

## Tasks (4–8 hours)

### 1. Gate-Size Grid Search
- gate_size ∈ {{10, 15, 20, 25, 30}}
- For each value, recompute Strategy Output Table:
  - 150期, 500期, 1000期, 1500期 edge, win-rate, Sharpe
  - permutation test p < 0.05 (200 shuffles, seed=42)
  - Cohen's d > 1.0
- Identify gate_size that maximises 1500期 edge while maintaining all windows > 0

### 2. EWMA Decay Grid Search
- ewma_decay ∈ {{0.80, 0.82, 0.85, 0.88, 0.90}}
- Same validation windows as above
- Identify best decay that improves 150期 stability

### 3. Combined Best Parameters
- Run best gate_size × best ewma_decay combination
- Full Strategy Output Table at 150/500/1000/1500 periods
- MC simulation n ≥ 1000 (permutation p < 0.05 required)
- Compare vs baseline (current strategy_name): McNemar p < 0.05 preferred

### 4. Data Leakage Check
- Run `tools/verify_no_data_leakage.py` on optimised parameters

## Constraints
- seed=42 for all tests
- No modification to currently active strategies in RSM
- Validation windows: 150/500/1000/1500 (all must be positive)
- Record all results in `runtime/winner_followup/{safe_strat}_param_opt_{today_label}.json`

## Acceptance Criteria
- All 4 windows edge > 0 for best parameters
- permutation p < 0.05
- No data leakage detected
- Comparison table vs baseline recorded

## Handoff Notes
- If optimised params pass all criteria → proceed to `prod_validation` subtype
- If no improvement found → record findings, do NOT discard current params
"""

    elif subtype == "prod_validation":
        title = f"[WINNER-FOLLOWUP] {game} {strategy_name} — Production Validation"
        slug = f"winner_followup_{safe_strat}_prod_validation_{today_label}"
        prompt_markdown = f"""# {title}

## Context
Winner / candidate strategy: **{strategy_name}** ({game})
{edge_str}{mc_pass_str}

## Objective
Production-grade validation: full MC simulation, all windows, vs baseline.

## Tasks (4–8 hours)

### 1. Full Window Validation
- Compute Strategy Output Table at **150, 500, 1000, 1500 periods**
- For each window: edge, win-rate, Sharpe, max_drawdown_rate
- All windows must show edge > 0

### 2. MC Simulation (Production Grade)
- n ≥ 5000 permutation shuffles, seed=42
- p < 0.01 target (p < 0.05 minimum)
- Record exact p-value and confidence interval

### 3. Cohen's d
- Compute effect size: target d > 1.0

### 4. Regime Split Analysis
- Split data into: Bull (edge trend positive), Bear (edge trend negative), Neutral
- Report per-regime performance separately

### 5. Baseline Comparison (McNemar)
- Compare vs current active strategy for {game}
- McNemar test p < 0.05 for upgrade eligibility
- If McNemar fails: record as CANDIDATE (not WINNER_CONFIRMED)

### 6. Multi-Bet Marginal Efficiency
- If multi-bet: each bet's marginal efficiency > 80%

## Constraints
- seed=42
- MC n ≥ 5000
- Run `tools/verify_no_data_leakage.py`
- Record all results in `runtime/winner_followup/{safe_strat}_prod_validation_{today_label}.json`

## Acceptance Criteria
- All 4 windows edge > 0
- MC p < 0.05 (target p < 0.01)
- Cohen's d > 1.0
- No data leakage
- McNemar p recorded (p < 0.05 = upgrade eligible)

## Handoff Notes
- If WINNER_CONFIRMED → proceed to `deployment` subtype
- If only CANDIDATE → record, queue H7 deep validation next
"""

    else:  # deployment
        title = f"[WINNER-FOLLOWUP] {game} {strategy_name} — Deployment Plan"
        slug = f"winner_followup_{safe_strat}_deployment_{today_label}"
        prompt_markdown = f"""# {title}

## Context
Winner / candidate strategy ready for deployment: **{strategy_name}** ({game})
{edge_str}{mc_pass_str}

## Objective
Write strategy spec, update strategy state, define fallback / rollback.

## Tasks (4–8 hours)

### 1. Strategy Specification
- Write formal spec to `strategies/{safe_strat}_spec.md`:
  - Parameters: gate_size, ewma_decay, num_bets
  - Validation evidence: edge at 150/500/1000/1500, MC p-value, Cohen's d
  - Comparison vs baseline: McNemar p, win-rate delta

### 2. Strategy State Update
- Update `lottery_api/data/strategy_states_{game}.json`:
  - validated_status: "validated"
  - classification: "WINNER"
  - edge_150p, edge_500p, edge_1500p: from prod_validation results
  - last_updated: today's ISO timestamp

### 3. Active Strategy State Update
- Update `active_strategy_state` in DB via `orchestrator.db`:
  - active_strategy = "{strategy_name}"
  - active_edge = best edge value (1500p preferred)
  - planner_focus = "MONITOR"

### 4. Fallback / Rollback Plan
- Define rollback trigger: if 30-period live edge < -2%, revert to previous strategy
- Write rollback instructions to spec file
- Set `monitoring_threshold` in orchestrator settings

### 5. RSM Configuration
- Confirm RSM monitoring is active for {game}
- Set monitoring interval and edge alert thresholds

## Constraints
- No live bets placed by this agent
- All file changes must be committed with descriptive messages
- Rollback plan must be defined before deployment
- Run `tools/verify_no_data_leakage.py` one final time

## Acceptance Criteria
- spec file written and committed
- strategy_states JSON updated
- active_strategy_state DB updated
- Fallback trigger defined

## Handoff Notes
- After deployment: planner transitions to MONITOR mode for {game}
- Monitor 30-period live edge; rollback if edge < -2%
"""

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "_dedupe_key": dedupe_key,
        "_winner_info": winner,
        "_subtype": subtype,
        "_regime_state": f"WINNER_FOLLOWUP:{subtype}",
        "_confidence_snapshot": None,
        "objective": title,
        "worker_type": "research",
    }


def _try_emit_winner_followup_task(
    request_id: Optional[str],
    latest: Optional[dict],
    t0: float,
    backlog: str = "",
) -> bool:
    """Attempt to create a winner follow-up task.

    Scans backlog for winner strategy markers, then tries each subtype
    (param_opt → prod_validation → deployment) in priority order.
    Daily cap: 1 task per subtype per winner per day.

    Returns True if a task was created, False if no winner found or all
    subtypes already done today.
    """
    winners = _detect_winner_strategies(backlog)
    if not winners:
        logger.debug("[WinnerFollowup] No winner strategies detected — skipping winner followup lane")
        return False

    today_label = common.local_day_label()

    for winner in winners:
        strategy_name = winner["strategy_name"]
        safe_strat = strategy_name.replace("→", "_").replace("/", "_")

        for subtype in _WINNER_SUBTYPES:
            dedupe_key = f"winner_followup:{safe_strat}:{subtype}:{today_label}"
            existing = db.get_nonfailed_task_by_dedupe_key(dedupe_key)
            if existing:
                logger.debug("[WinnerFollowup] %s already exists (id=%s status=%s) — skip",
                             dedupe_key, existing.get("id"), existing.get("status"))
                continue

            # Build payload and evaluate through planner_decision
            candidate_payload = _build_winner_followup_payload(winner, subtype, today_label)
            fallback_key = candidate_payload["_dedupe_key"]

            from orchestrator import planner_decision
            backlog_flags = tuple(planner_decision.extract_backlog_flags(backlog))
            candidate = planner_decision.CandidateTask(
                task_type=f"winner_followup_{subtype}",
                dedupe_key=fallback_key,
                title=candidate_payload["title"],
                backlog_flags=backlog_flags,
            )
            decision = planner_decision.evaluate_candidate(candidate)
            if planner_decision.is_block_decision(decision):
                logger.info("[WinnerFollowup] Decision blocked %s: %s", fallback_key, decision.reason)
                continue

            # Create task artifacts
            title = candidate_payload["title"]
            slug = common.slugify(candidate_payload["slug"])
            prompt_markdown = candidate_payload["prompt_markdown"]
            contract = _build_task_contract(candidate_payload)
            contract_ok, contract_reason = common.validate_task_contract(contract)
            if not contract_ok:
                logger.warning("[WinnerFollowup] Invalid contract for %s: %s", fallback_key, contract_reason)
                continue

            slot_key = f"{common.slot_key_now()}wf{subtype[:3]}"
            date_folder = common.date_folder_now()
            p_path = common.prompt_path(slot_key, slug, date_folder)
            contract_file_path = common.contract_path(slot_key, slug, date_folder)
            worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

            with open(p_path, "w") as _f:
                _f.write(f"# {title}\n\n")
                _f.write(worker_prompt)
            with open(contract_file_path, "w", encoding="utf-8") as _f:
                json.dump(contract, _f, ensure_ascii=False, indent=2)

            previous_task_id = latest["id"] if latest else None
            task_id = db.create_task(
                slot_key=slot_key,
                date_folder=date_folder,
                title=title,
                slug=slug,
                prompt_text=prompt_markdown,
                prompt_file_path=p_path,
                previous_task_id=previous_task_id,
                dedupe_key=fallback_key,
                regime_state=candidate_payload.get("_regime_state"),
                confidence_snapshot=None,
                value_score=None,
                worker_type="research",
            )
            db.update_task(task_id, planner_agent_label="Local")

            common.write_meta(
                slot_key, date_folder,
                task_id=task_id, title=title, slug=slug,
                status="QUEUED", previous_task_id=previous_task_id,
                planner_source="winner_followup",
                planner_provider="local",
                planner_requested_provider="local",
                task_contract_path=contract_file_path,
                task_contract_version=contract.get("version"),
            )

            elapsed = int((time.time() - t0) * 1000)
            msg = (
                f"Winner followup task {task_id} created: {title} "
                f"[{slug}] winner={strategy_name} subtype={subtype} dedupe={fallback_key}"
            )
            logger.info(msg)
            db.log_tick(
                RUNNER, "PLANNER_CREATE_WINNER_FOLLOWUP",
                task_id=task_id, message=msg, duration_ms=elapsed,
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_CREATE_WINNER_FOLLOWUP",
                task_id=task_id,
                title=title,
                slug=slug,
                winner=strategy_name,
                subtype=subtype,
                dedupe_key=fallback_key,
            )
            return True

    logger.debug("[WinnerFollowup] All winner followup subtypes exhausted for today (%s)", today_label)
    return False


def _strategy_short_label(strategy_name: str) -> str:
    m = re.match(r"^(H\d+)", str(strategy_name or ""), re.I)
    if m:
        return m.group(1).upper()
    return (str(strategy_name or "").split("_", 1)[0] or "ACTIVE").upper()


def _normalize_strategy_name(name: str) -> str:
    """Normalize strategy names for robust matching across arrow/case variants."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    normalized = raw.lower()
    normalized = normalized.replace("→", "_").replace("->", "_").replace("=>", "_").replace("/", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _extract_winner_followup_strategy_from_key(dedupe_key: str) -> str:
    parts = str(dedupe_key or "").split(":")
    if len(parts) != 4 or parts[0] != "winner_followup":
        return ""
    return _normalize_strategy_name(parts[1])


def _winner_followup_completed_today(game_type: str, strategy_name: str, today_label: str) -> tuple[bool, Optional[int]]:
    normalized_target = _normalize_strategy_name(strategy_name)
    if not normalized_target:
        return False, None

    required_subtypes = {"param_opt", "prod_validation", "deployment"}
    seen_subtypes: set[str] = set()
    deployment_id: Optional[int] = None

    conn = db.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, dedupe_key
            FROM agent_tasks
            WHERE status = 'COMPLETED'
              AND dedupe_key LIKE ?
            ORDER BY id DESC
            """,
            (f"winner_followup:%:%:{today_label}",),
        ).fetchall()

        for row in rows:
            key = str(row["dedupe_key"] or "")
            parts = key.split(":")
            if len(parts) != 4 or parts[0] != "winner_followup":
                continue

            strategy_part = _extract_winner_followup_strategy_from_key(key)
            if strategy_part != normalized_target:
                continue

            subtype = parts[2]
            if subtype in required_subtypes:
                seen_subtypes.add(subtype)
                if subtype == "deployment" and deployment_id is None:
                    deployment_id = int(row["id"])

        ok = required_subtypes.issubset(seen_subtypes)
        return ok, deployment_id if ok else None
    finally:
        conn.close()


def _active_strategy_classification(game_type: str, strategy_name: str) -> tuple[str, str]:
    path = os.path.join(_STRATEGY_STATES_DIR, f"strategy_states_{game_type}.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            states = json.load(fh)

        state = states.get(strategy_name) or {}
        if not state:
            target_norm = _normalize_strategy_name(strategy_name)
            for k, v in (states or {}).items():
                if _normalize_strategy_name(k) == target_norm:
                    state = v or {}
                    break

        classification = str(state.get("classification") or "").strip().upper()
        validated_status = str(state.get("validated_status") or "").strip().upper()
        return classification, validated_status
    except Exception:
        return "", ""


def _is_deployed_strategy_classified_ok(classification: str, validated_status: str) -> bool:
    cls = str(classification or "").upper()
    vs = str(validated_status or "").upper()
    if cls in {"WINNER", "VALIDATED", "APPROVE_STRATEGY", "APPROVED", "PROMOTED"}:
        return True
    return vs in {"VALIDATED", "ACTIVE", "PROMOTED", "APPROVED"}


def _planner_focus_text(raw_focus: Any) -> str:
    value = str(raw_focus or "").strip()
    if not value:
        return ""
    if value.startswith("{"):
        try:
            obj = json.loads(value)
            for k in ("planner_focus", "signal_status", "focus", "reason"):
                if obj.get(k):
                    return str(obj.get(k))
        except Exception:
            return value
    return value


def _detect_active_deployed_strategy_diagnostic(backlog: str = "") -> tuple[Optional[dict], str, list[dict]]:
    today_label = common.local_day_label()
    states = db.get_all_active_strategy_states() or []
    if not states:
        return None, "no_active_strategy_row", []

    candidates: list[dict] = []
    diag: list[dict] = []
    saw_any_active = False

    for state in states:
        game = str(state.get("game_type") or "").strip()
        active_strategy = str(state.get("active_strategy") or "").strip()
        rollback_status = str(state.get("rollback_status") or "ACTIVE").strip().upper() or "ACTIVE"
        if not game:
            continue
        if not active_strategy:
            diag.append(
                {
                    "game": game,
                    "reason": "active_strategy_empty",
                    "active_strategy": active_strategy,
                    "rollback_status": rollback_status,
                }
            )
            continue
        saw_any_active = True

        normalized_name = _normalize_strategy_name(active_strategy)
        if not normalized_name:
            diag.append(
                {
                    "game": game,
                    "reason": "unsupported_strategy_name",
                    "active_strategy": active_strategy,
                    "rollback_status": rollback_status,
                }
            )
            continue

        winner_done, deployment_task_id = _winner_followup_completed_today(game, active_strategy, today_label)
        classification, validated_status = _active_strategy_classification(game, active_strategy)
        classified_ok = _is_deployed_strategy_classified_ok(classification, validated_status)
        if not (winner_done or classified_ok):
            diag.append(
                {
                    "game": game,
                    "reason": "strategy_state_not_validated",
                    "active_strategy": active_strategy,
                    "classification": classification,
                    "validated_status": validated_status,
                    "winner_followup_completed": winner_done,
                    "rollback_status": rollback_status,
                }
            )
            continue

        focus_text = _planner_focus_text(state.get("planner_focus"))
        rollback_triggered = bool(state.get("rollback_triggered"))
        if rollback_status != "ACTIVE" and not rollback_triggered:
            diag.append(
                {
                    "game": game,
                    "reason": "rollback_status_not_active",
                    "active_strategy": active_strategy,
                    "rollback_status": rollback_status,
                }
            )
            continue

        if not winner_done:
            diag.append(
                {
                    "game": game,
                    "reason": "no_winner_followup_completed",
                    "active_strategy": active_strategy,
                    "classification": classification,
                    "validated_status": validated_status,
                    "rollback_status": rollback_status,
                }
            )

        candidates.append(
            {
                "game": game,
                "active_strategy": active_strategy,
                "active_edge": state.get("active_edge"),
                "shadow_strategy": str(state.get("shadow_strategy") or "").strip(),
                "shadow_edge": state.get("shadow_edge"),
                "planner_focus": focus_text,
                "classification": classification or "WINNER",
                "validated_status": validated_status or "VALIDATED",
                "deployment_task_id": deployment_task_id,
                "updated_at": state.get("updated_at"),
                "rollback_status": rollback_status,
                "rollback_triggered": rollback_triggered,
                "normalized_strategy": normalized_name,
            }
        )

    if not candidates:
        if not saw_any_active:
            return None, "active_strategy_empty", diag
        if diag:
            preferred = [d for d in diag if str(d.get("game") or "").upper() == "DAILY_539"] or diag
            reason_order = [
                "no_active_strategy_row",
                "active_strategy_empty",
                "unsupported_strategy_name",
                "rollback_status_not_active",
                "no_winner_followup_completed",
                "strategy_state_not_validated",
            ]
            reasons = [str(d.get("reason") or "") for d in preferred]
            for code in reason_order:
                if code in reasons:
                    return None, code, diag
            return None, preferred[0].get("reason", "no_active_strategy_row"), diag
        return None, "no_active_strategy_row", diag

    def _sort_key(item: dict) -> tuple[int, str]:
        focus = str(item.get("planner_focus") or "").upper()
        monitor_priority = 0 if "MONITOR" in focus else 1
        updated = str(item.get("updated_at") or "")
        return (monitor_priority, updated)

    candidates.sort(key=_sort_key, reverse=False)
    return candidates[0], "ok", diag


def _detect_active_deployed_strategy(backlog: str = "") -> Optional[dict]:
    candidate, _reason, _diag = _detect_active_deployed_strategy_diagnostic(backlog=backlog)
    return candidate


def _build_post_deployment_payload(strategy: dict, subtype: str, today_label: str) -> dict:
    game = str(strategy.get("game") or "").strip()
    active = str(strategy.get("active_strategy") or "").strip()
    shadow = str(strategy.get("shadow_strategy") or "").strip() or "N/A"
    focus = str(strategy.get("planner_focus") or "").strip() or "MONITOR"
    h_label = _strategy_short_label(active)
    active_key = active.replace(":", "_")
    subtype_title = _POST_DEPLOYMENT_SUBTYPE_TITLES.get(subtype, subtype.replace("_", " ").title())
    title = f"[POST-DEPLOY] {h_label} {subtype_title} — {game}"
    slug = common.slugify(f"post-deploy-{game}-{h_label}-{subtype}-{today_label}") or f"post-deploy-{subtype}-{today_label}"
    report_base = f"{game.lower()}_{common.slugify(active) or h_label.lower()}_{subtype}_{today_label}"
    report_md = f"runtime/post_deployment/{report_base}.md"
    report_json = f"runtime/post_deployment/{report_base}.json"
    dedupe_key = f"post_deploy:{game}:{active_key}:{subtype}:{today_label}"

    shared_constraints = (
        "- 任務規模必須為 4-8 小時，禁止縮成 2-5 分鐘短任務\n"
        "- 不得修改 `lottery_api/data/lottery_v2.db`\n"
        "- 不得直接修改 `active_strategy_state`（除非任務明確要求 rollback follow-up 記錄）\n"
        "- 所有實驗需固定 `seed=42`\n"
        "- 若未產生指定 artifact，禁止標記 COMPLETED"
    )

    scope_by_subtype = {
        "live_monitoring_calibration": (
            f"- Active strategy: `{active}` / Shadow: `{shadow}`\n"
            "- 建立 live_30p_edge、live_50p_edge、rolling hit rate、current_regime 指標定義\n"
            "- 定義 bear regime warning 與 rollback_status 寫入規則\n"
            "- 進行 alert threshold calibration（含觸發靈敏度與誤報率）\n"
            "- 產出監控設定提案與驗證樣本"
        ),
        "rollback_simulation": (
            f"- 模擬 `{active}` 在 live_30p_edge < -2% 情境下的回滾流程\n"
            f"- 驗證 active/shadow 切換（`{active}` -> `{shadow}`）與 rollback_reason 記錄\n"
            "- 驗證 prediction API 行為與回滾後輸出一致性\n"
            "- 驗證 UI/report disclosure 是否正確顯示 rollback 狀態\n"
            "- 產出 rollback runbook 與風險清單"
        ),
        "shadow_strategy_challenge": (
            f"- 比較 `{active}` vs `{shadow}`，並納入 `H7_intersect_top15`\n"
            "- 針對 rolling 30/50/100 進行 edge / hit-rate 對照\n"
            "- 給出 keep active / keep shadow / rotate 的可執行建議\n"
            "- 標註切換門檻與觀察週期"
        ),
        "h6_variant_hardening": (
            "- 以 gate=20, decay=0.88 當前 variant 為 baseline\n"
            "- 比較 neighboring variants（gate ±5, decay ±0.02）\n"
            "- 做 regime split（bull/bear/neutral）穩定性分析\n"
            "- 做 drawdown stress test 與 MC n >= 5000\n"
            "- 輸出 hardening 建議與禁用區間"
        ),
        "prediction_output_quality_audit": (
            f"- 審計 `{active}` 當前生成號碼品質\n"
            "- 必查：generated numbers、coverage、overlap、entropy\n"
            "- 必查：sum/zone/odd-even 結構是否符合策略意圖\n"
            "- 給出品質告警規則與 auto-check 清單"
        ),
        "production_drift_detection": (
            f"- 比較 validation edge 與 `{active}` live proxy edge\n"
            "- 分析 recent draw drift、EWMA signal drift、Markov candidate pool drift\n"
            "- 形成 drift alert rule（含 threshold 與 rollback 連動）\n"
            "- 輸出 drift dashboard 欄位與觸發條件"
        ),
        "rollback_followup": (
            f"- `planner_focus={focus}` 顯示 rollback 已啟動，停止 `{active}` optimization\n"
            "- 建立 rollback 後續驗證任務：狀態一致性、風險封存、監控回復條件\n"
            "- 驗證 shadow strategy 接手後的指標基準與警戒線"
        ),
    }
    acceptance_common = (
        f"- 產出 `{report_md}` 與 `{report_json}`\n"
        "- 報告需包含明確驗收結論（PASS/FAIL）與證據\n"
        "- 報告需列出至少一個可追蹤配置或腳本異動（若無異動需說明阻塞）\n"
        "- 明確列出 fail conditions 與下一步任務建議"
    )
    prompt_markdown = (
        "## Objective\n"
        f"Perform post-deployment optimization for active strategy `{active}` on `{game}` "
        f"via subtype `{subtype}`.\n\n"
        "## Scope\n"
        "- Task budget: 4-8 hours\n"
        f"- Game: `{game}`\n"
        f"- Active strategy: `{active}`\n"
        f"- Shadow strategy: `{shadow}`\n"
        f"- Source deployment task id: `{strategy.get('deployment_task_id') or 'N/A'}`\n"
        f"{scope_by_subtype.get(subtype, '-')}\n\n"
        "## Constraints\n"
        f"{shared_constraints}\n\n"
        "## Acceptance Criteria\n"
        f"{acceptance_common}\n\n"
        "## Handoff Notes\n"
        f"- planner_focus: `{focus}`\n"
        f"- required artifacts: `{report_md}`, `{report_json}`\n"
        "- 如果發現 rollback trigger 已達標，請在報告中附 rollback follow-up prompt\n"
    )

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "task_type": f"post_deployment_optimization_{subtype}",
        "_signal_state_type": "post_deployment_optimization",
        "_dedupe_key": dedupe_key,
        "_regime_state": "post_deployment_optimization",
        "_confidence_snapshot": None,
        "_post_deploy_subtype": subtype,
        "worker_type": "research",
    }


def _count_post_deployment_tasks_today(today_label: str) -> int:
    conn = db.get_conn()
    try:
        row = conn.execute(
            """
            SELECT COUNT(1) AS cnt
            FROM agent_tasks
            WHERE status IN ('QUEUED', 'RUNNING', 'COMPLETED')
              AND dedupe_key LIKE ?
            """,
            (f"post_deploy:%:{today_label}",),
        ).fetchone()
        return int((row["cnt"] if row else 0) or 0)
    finally:
        conn.close()


def _try_emit_post_deployment_optimization_task(
    request_id: Optional[str],
    latest: Optional[dict],
    t0: float,
    backlog: str = "",
) -> bool:
    today_label = common.local_day_label()
    strategy, detect_reason, detect_diag = _detect_active_deployed_strategy_diagnostic(backlog=backlog)
    if not strategy:
        msg = (
            "No eligible active deployed strategy for post-deployment optimization "
            f"(reason={detect_reason}; db_path={db.DB_PATH})"
        )
        db.log_tick(
            RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_NO_ACTIVE_STRATEGY",
            message=msg, request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_NO_ACTIVE_STRATEGY",
            today=today_label,
            reason=detect_reason,
            db_path=db.DB_PATH,
            diagnostics=detect_diag[:6],
        )
        return False

    already = _count_post_deployment_tasks_today(today_label)
    if already >= POST_DEPLOYMENT_OPTIMIZATION_DAILY_CAP:
        msg = (
            f"post_deploy daily cap exhausted: {already}/"
            f"{POST_DEPLOYMENT_OPTIMIZATION_DAILY_CAP} ({today_label})"
        )
        db.log_tick(
            RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_DAILY_CAP",
            message=msg[:600], request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_DAILY_CAP",
            today=today_label,
            count_today=already,
            cap=POST_DEPLOYMENT_OPTIMIZATION_DAILY_CAP,
        )
        return False

    focus_upper = str(strategy.get("planner_focus") or "").upper()
    if "ROLLBACK" in focus_upper:
        candidate_subtypes = ["rollback_followup"]
    else:
        candidate_subtypes = list(_POST_DEPLOYMENT_SUBTYPES)

    for subtype in candidate_subtypes:
        payload = _build_post_deployment_payload(strategy, subtype, today_label)
        dedupe_key = payload["_dedupe_key"]
        existing = db.get_nonfailed_task_by_dedupe_key(dedupe_key)
        if existing:
            msg = (
                f"post_deploy dedupe skip: subtype={subtype} "
                f"existing_task_id={existing.get('id')} status={existing.get('status')} "
                f"dedupe={dedupe_key}"
            )
            db.log_tick(
                RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_DEDUPE",
                message=msg[:600], request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_POST_DEPLOYMENT_DEDUPE",
                subtype=subtype,
                dedupe_key=dedupe_key,
                existing_task_id=existing.get("id"),
                existing_status=existing.get("status"),
            )
            continue

        title = payload["title"]
        slug = common.slugify(payload["slug"])
        prompt_markdown = payload["prompt_markdown"]
        contract = _build_task_contract(payload)
        contract_ok, contract_reason = common.validate_task_contract(contract)
        if not contract_ok:
            logger.warning("post_deploy contract invalid (%s): %s", dedupe_key, contract_reason)
            continue

        slot_key = f"{common.slot_key_now()}pd"
        date_folder = common.date_folder_now()
        p_path = common.prompt_path(slot_key, slug, date_folder)
        contract_file_path = common.contract_path(slot_key, slug, date_folder)
        worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

        with open(p_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(worker_prompt)
        with open(contract_file_path, "w", encoding="utf-8") as f:
            json.dump(contract, f, ensure_ascii=False, indent=2)

        previous_task_id = latest["id"] if latest else None
        task_id = db.create_task(
            slot_key=slot_key,
            date_folder=date_folder,
            title=title,
            slug=slug,
            prompt_text=prompt_markdown,
            prompt_file_path=p_path,
            previous_task_id=previous_task_id,
            dedupe_key=dedupe_key,
            regime_state=payload.get("_regime_state"),
            confidence_snapshot=payload.get("_confidence_snapshot"),
            value_score=None,
            worker_type=payload.get("worker_type", "research"),
        )
        db.update_task(task_id, planner_agent_label="Local")

        common.write_meta(
            slot_key, date_folder,
            task_id=task_id, title=title, slug=slug,
            status="QUEUED", previous_task_id=previous_task_id,
            planner_source="post_deployment_optimization",
            planner_provider="local",
            planner_requested_provider="local",
            task_contract_path=contract_file_path,
            task_contract_version=contract.get("version"),
        )

        elapsed = int((time.time() - t0) * 1000)
        msg = (
            f"Post-deployment task {task_id} created: {title} "
            f"[{slug}] subtype={subtype} dedupe={dedupe_key}"
        )
        logger.info(msg)
        db.log_tick(
            RUNNER, "PLANNER_CREATE_POST_DEPLOYMENT_OPTIMIZATION",
            task_id=task_id, message=msg, duration_ms=elapsed, request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_CREATE_POST_DEPLOYMENT_OPTIMIZATION",
            task_id=task_id,
            game=strategy.get("game"),
            active_strategy=strategy.get("active_strategy"),
            subtype=subtype,
            dedupe_key=dedupe_key,
        )
        return True

    return False


def _try_emit_fallback_task(
    request_id: Optional[str],
    latest: Optional[dict],
    t0: float,
) -> bool:
    """Attempt to create the highest-priority fallback task not yet run today.

    Returns True if a fallback task was created, False if all P1-P6 are blocked.
    """
    from datetime import timezone as _tz  # already imported at top; local alias avoids shadowing
    today_label = common.local_day_label()
    candidates = _build_fallback_candidates(today_label)

    for candidate in candidates:
        fallback_key = candidate["_dedupe_key"]
        existing = db.get_today_task_by_dedupe_key(fallback_key)
        if existing:
            msg = (
                f"Fallback {fallback_key} already exists today "
                f"(task_id={existing['id']} status={existing['status']}) — skip"
            )
            logger.debug(msg)
            db.log_tick(
                RUNNER, "PLANNER_SKIP_FALLBACK_DAILY_CAP",
                message=msg[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_FALLBACK_DAILY_CAP",
                dedupe_key=fallback_key,
                existing_task_id=existing["id"],
                existing_status=existing["status"],
            )
            continue

        # Build task artifacts
        title = candidate["title"]
        slug = common.slugify(candidate["slug"])
        prompt_markdown = candidate["prompt_markdown"]
        contract = _build_task_contract(candidate)
        contract_ok, contract_reason = common.validate_task_contract(contract)
        if not contract_ok:
            logger.warning("Fallback %s invalid contract: %s", fallback_key, contract_reason)
            continue

        slot_key = common.slot_key_now()
        date_folder = common.date_folder_now()
        p_path = common.prompt_path(slot_key, slug, date_folder)
        contract_file_path = common.contract_path(slot_key, slug, date_folder)
        worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

        with open(p_path, "w") as f:
            f.write(f"# {title}\n\n")
            f.write(worker_prompt)
        with open(contract_file_path, "w", encoding="utf-8") as f:
            json.dump(contract, f, ensure_ascii=False, indent=2)

        previous_task_id = latest["id"] if latest else None
        task_id = db.create_task(
            slot_key=slot_key,
            date_folder=date_folder,
            title=title,
            slug=slug,
            prompt_text=prompt_markdown,
            prompt_file_path=p_path,
            previous_task_id=previous_task_id,
            dedupe_key=fallback_key,
            regime_state=candidate.get("_regime_state"),
            confidence_snapshot=candidate.get("_confidence_snapshot"),
            value_score=None,
            worker_type="light",
        )
        db.update_task(task_id, planner_agent_label="Local")

        common.write_meta(
            slot_key, date_folder,
            task_id=task_id, title=title, slug=slug,
            status="QUEUED", previous_task_id=previous_task_id,
            planner_source="fallback_idle",
            planner_provider="local",
            planner_requested_provider="local",
            task_contract_path=contract_file_path,
            task_contract_version=contract.get("version"),
        )

        elapsed = int((time.time() - t0) * 1000)
        msg = f"Fallback task {task_id} created: {title} [{slug}] dedupe={fallback_key}"
        logger.info(msg)
        db.log_tick(
            RUNNER, "PLANNER_CREATE_FALLBACK_TASK",
            task_id=task_id, message=msg, duration_ms=elapsed,
            request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_CREATE_FALLBACK_TASK",
            task_id=task_id,
            title=title,
            slug=slug,
            dedupe_key=fallback_key,
        )
        return True

    # All P1-P6 candidates blocked today
    return False


# ---------------------------------------------------------------------------
# Forced Exploration Mode
# ---------------------------------------------------------------------------
# Triggered when P1–P6 fallback maintenance tasks are ALL blocked for today.
# The planner generates one research-class task cycling A→F in round-robin.
# worker_type = research  (not light — these are substantive research tasks)
# dedupe_key  = forced_exploration:{lane}:{YYYY-MM-DD}  (at most 1 per day)

_EXPLORATION_LANES = [
    "external_signal",
    "constraint_postprocess",
    "long_window_residual",
    "cross_lottery_transfer",
    "reject_rule",
    "ux_decision_quality",
]

_EXPLORATION_LANE_TITLES = {
    "external_signal":        "[EXPLORE-A] External Signal Hypothesis Research",
    "constraint_postprocess": "[EXPLORE-B] Constraint / Postprocess Hypothesis Research",
    "long_window_residual":   "[EXPLORE-C] Long-Window Residual Hypothesis Research",
    "cross_lottery_transfer": "[EXPLORE-D] Cross-Lottery Transfer Audit",
    "reject_rule":            "[EXPLORE-E] Anti-Strategy / Reject Rule Hypothesis Research",
    "ux_decision_quality":    "[EXPLORE-F] UX / Decision Quality Research",
}

_EXPLORATION_LANE_TASK_TYPES = {
    "external_signal":        "forced_exploration_external_signal",
    "constraint_postprocess": "forced_exploration_constraint",
    "long_window_residual":   "forced_exploration_long_window",
    "cross_lottery_transfer": "forced_exploration_cross_lottery",
    "reject_rule":            "forced_exploration_reject_rule",
    "ux_decision_quality":    "forced_exploration_ux",
}

# Forbidden directions injected into every exploration prompt
_FE_CONSTRAINTS = (
    "不得新增 frequency / Fourier / Markov 變體\n"
    "- 不得重跑已飽和 strategy family（anti_correlation, freq_rev, shadow_gap, cold_lowfreq 等）\n"
    "- 不得直接宣稱 ROI 改善（需驗證後才能宣稱）\n"
    "- 不得更新 active_strategy_state 或 strategy_live_state\n"
    "- 不得直接替換 active strategy\n"
    "- 不得在沒有 CTO review 的情況下升格策略\n"
    "- 僅產生 research report / hypothesis / validation plan / small diagnostic script\n"
    "- seed=42\n"
    "- 不得修改 lottery_api/data/lottery_v2.db\n"
    "- 不得直接改寫 strategy_states 配置檔"
)

# Required 7-section output format appended to every exploration prompt
_FE_OUTPUT_FORMAT = (
    "---\n\n"
    "## Required Report Sections\n\n"
    "Your output MUST contain all 7 sections. Missing any = REPLAN_REQUIRED.\n\n"
    "### 1. New Hypothesis\n"
    "State the specific hypothesis. Explain how it differs from saturated families "
    "(frequency, Fourier, Markov, anti_correlation, freq_rev, shadow_gap, cold_lowfreq). "
    "The hypothesis MUST be genuinely new.\n\n"
    "### 2. Why This Could Improve Success Rate\n"
    "Explain the causal/statistical mechanism. Be specific. "
    "Do NOT claim ROI improvement without evidence.\n\n"
    "### 3. Required Data\n"
    "List: existing DB tables/columns, external data (state if unavailable), "
    "generated features, data known to be missing.\n\n"
    "### 4. Minimal Validation Plan\n"
    "| Field | Value |\n"
    "|---|---|\n"
    "| sample_size | e.g. 150 draws |\n"
    "| test_window | e.g. last 500p |\n"
    "| baseline | e.g. current best edge |\n"
    "| statistical_test | e.g. McNemar, permutation |\n"
    "| expected_output | e.g. edge_150 > 0.03 |\n\n"
    "### 5. Risk / Overfit Check\n"
    "Rate each risk low/medium/high with reason:\n"
    "- sample_size_risk\n"
    "- multiple_testing_risk\n"
    "- data_leakage_risk\n"
    "- overfit_risk\n\n"
    "### 6. Decision\n"
    "Choose EXACTLY ONE:\n"
    "- **WORTH_VALIDATION** — evidence suggests real signal; proceed to validation task\n"
    "- **WATCH_ONLY** — interesting but insufficient; monitor for 2+ weeks\n"
    "- **REJECT** — not worth pursuing; explain why\n\n"
    "### 7. Next Task If Worth Validation\n"
    "If WORTH_VALIDATION: write the complete next validation task prompt.\n"
    "If WATCH_ONLY or REJECT: write N/A.\n"
)


def _build_forced_exploration_payload(lane: str, today_label: str) -> dict:
    """Build a Forced Exploration task payload for the given lane."""
    title = _EXPLORATION_LANE_TITLES[lane]
    task_type = _EXPLORATION_LANE_TASK_TYPES[lane]
    slug = f"forced-exploration-{lane.replace('_', '-')}-{today_label}"

    if lane == "external_signal":
        objective = (
            "研究外部信號（jackpot carryover、sell_amount、weekday/holiday、"
            "month-end/start 效應）是否能作為彩票邊際改善的新假說方向。"
        )
        scope_lines = (
            "分析 DB 中是否已有 jackpot / sell_amount / date 相關欄位\n"
            "- 研究 weekday 分佈（Mon–Sun）在 DAILY_539 / POWER_LOTTO / BIG_LOTTO 的 win pattern\n"
            "- 研究 month-end / month-start 效應（最後 3 天 / 前 3 天）\n"
            "- 研究 holiday 前後是否有異常分佈\n"
            "- 禁止：不得研究 frequency / Fourier / Markov 方向"
        )
        output_path = f"research/external_signal_hypothesis_{today_label}.md"

    elif lane == "constraint_postprocess":
        objective = (
            "研究後處理約束（sum band、odd/even ratio、span、consecutive count、"
            "AC value、zone coverage）是否能作為 filter 提升邊際。"
        )
        scope_lines = (
            "計算現有投注候選在各約束維度上的分佈\n"
            "- 分析哪些約束 bucket 有更高 win rate（按 bucket 分組統計）\n"
            "- 研究約束組合（sum band + zone coverage）是否比單一約束更穩定\n"
            "- 禁止：不得新增新的 bet generation strategy family"
        )
        output_path = f"research/constraint_postprocess_hypothesis_{today_label}.md"

    elif lane == "long_window_residual":
        objective = (
            "研究長窗口（2500p / 3000p / 4000p / full history）殘差與 rolling decay，"
            "確認是否有可用的長期 edge pattern。"
        )
        scope_lines = (
            "計算 DAILY_539 / POWER_LOTTO / BIG_LOTTO 在 2500p、3000p、4000p 窗口的 edge\n"
            "- 比較長窗口 vs 短窗口 edge 的衰減斜率（edge attenuation curve）\n"
            "- 研究 rolling decay：邊際是否在 recent 200p 顯著低於 historical 200p\n"
            "- 禁止：不得重跑已完成的標準 150p/500p/1500p backtests"
        )
        output_path = f"research/long_window_residual_hypothesis_{today_label}.md"

    elif lane == "cross_lottery_transfer":
        objective = (
            "跨彩種審計：分析 DAILY_539 / POWER_LOTTO / BIG_LOTTO 之間"
            "哪些特徵共同失效、哪些可能轉移，產出轉移 filter 假說。"
        )
        scope_lines = (
            "比較三彩種現有 strategy 的 edge pattern 與衰退趨勢\n"
            "- 識別哪些特徵在所有彩種都衰退（可能是市場結構問題）\n"
            "- 識別哪些特徵只在單一彩種有效（彩種特有信號）\n"
            "- 研究是否有可轉移的 reject rule（某特徵 → 預測失敗）\n"
            "- 禁止：不得跨彩種合併策略或修改 active strategy"
        )
        output_path = f"research/cross_lottery_transfer_audit_{today_label}.md"

    elif lane == "reject_rule":
        objective = (
            "研究如何識別並排除爛投注：哪些候選條件代表 fake edge、"
            "容易 overfit、在 live outcome 衰退，產出 reject rule 假說。"
        )
        scope_lines = (
            "分析歷史 FAILED / FAILED_WEAK_EDGE 任務的共同特徵\n"
            "- 研究哪些策略在 T1/T2 通過但在 live 衰退（false positive pattern）\n"
            "- 研究 overfit 指標：edge_150 >> edge_1500p 的差距分佈\n"
            "- 研究哪些 candidate 應加入 blacklist 或 rejection heuristic\n"
            "- 禁止：不得直接修改 active strategy 或 strategy_live_state"
        )
        output_path = f"research/reject_rule_hypothesis_{today_label}.md"

    else:  # ux_decision_quality
        objective = (
            "研究如何提升 orchestration UI 的決策品質：active/shadow dashboard、"
            "drift alert、strategy confidence explanation、CTO daily summary。"
        )
        scope_lines = (
            "審計 tick_log 中哪些事件類型在 UI 中沒有視覺化\n"
            "- 研究 drift alert：如何在 edge 下滑時自動觸發警告\n"
            "- 研究 strategy confidence explanation：讓 CTO 理解信心分數變化\n"
            "- 研究 task value ranking：讓 Planner 的決策可解釋\n"
            "- 禁止：不得直接修改 lottery_api 的 production endpoints"
        )
        output_path = f"research/ux_decision_quality_research_{today_label}.md"

    prompt_markdown = (
        f"## Objective\n{objective}\n\n"
        f"## Scope\n{scope_lines}\n\n"
        f"## Constraints\n{_FE_CONSTRAINTS}\n\n"
        f"## Acceptance Criteria\n"
        f"- 輸出 `{output_path}` 包含所有 7 個必要區塊（見 Required Report Sections）\n"
        f"- Section 1（New Hypothesis）明確說明與已飽和 family 的差異\n"
        f"- Section 4（Minimal Validation Plan）包含 sample_size、baseline、statistical_test\n"
        f"- Section 5（Risk / Overfit Check）評估所有 4 個 risk 維度\n"
        f"- Section 6（Decision）選擇 WORTH_VALIDATION / WATCH_ONLY / REJECT 其中一個\n"
        f"- 若 Decision = WORTH_VALIDATION，Section 7 包含完整下一步 validation task prompt\n"
        f"- 不得包含 frequency / Fourier / Markov 相關假說\n\n"
        f"## Handoff Notes\n"
        f"- 若 Decision = WORTH_VALIDATION，建議下一個 Planner tick 排入 validation task\n"
        f"- 若 Decision = WATCH_ONLY，記錄到 wiki/exploration_watchlist.md（若存在）\n"
        f"- 若 Decision = REJECT，記錄拒絕原因以避免重複探索\n\n"
        f"{_FE_OUTPUT_FORMAT}"
        f"---\n\n"
        f"## Output Path\n"
        f"請將完整報告輸出到：`{output_path}`\n"
    )

    return {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "task_type": task_type,
        "_dedupe_key": f"forced_exploration:{lane}:{today_label}",
        "_regime_state": "forced_exploration",
        "_confidence_snapshot": None,
    }


def _get_next_exploration_lane(today_label: str) -> Optional[str]:
    """Pick the next exploration lane in A→F round-robin order.

    Reads the most recently created forced_exploration task (any date) to
    determine which lane ran last, then advances by one step.  Skips any
    lane whose today-scoped dedupe_key already exists (QUEUED/RUNNING/COMPLETED).
    Returns the lane key, or None if all 6 lanes are already done today.
    """
    last_task = db.get_last_forced_exploration_task()
    if last_task:
        last_key = last_task.get("dedupe_key", "")
        parts = last_key.split(":")
        if len(parts) >= 2 and parts[1] in _EXPLORATION_LANES:
            start_idx = (_EXPLORATION_LANES.index(parts[1]) + 1) % len(_EXPLORATION_LANES)
        else:
            start_idx = 0
    else:
        start_idx = 0

    for i in range(len(_EXPLORATION_LANES)):
        lane = _EXPLORATION_LANES[(start_idx + i) % len(_EXPLORATION_LANES)]
        dedupe_key = f"forced_exploration:{lane}:{today_label}"
        # Use key-only check (no DATE filter) — the date is already embedded in the key.
        # get_nonfailed_task_by_dedupe_key blocks on QUEUED/RUNNING/COMPLETED/SKIPPED_DUPLICATE*
        # so it's robust even if a task was created on a prior UTC day with the same key.
        if not db.get_nonfailed_task_by_dedupe_key(dedupe_key):
            return lane
    return None  # all 6 lanes used today


def _try_emit_forced_exploration_task(
    request_id: Optional[str],
    latest: Optional[dict],
    t0: float,
) -> bool:
    """Attempt to create a Forced Exploration task for the next unused lane today.

    Returns True if a task was created, False if all lanes are blocked (daily cap
    exhausted for every lane today → allow PLANNER_IDLE_NO_ELIGIBLE_TASK).
    """
    from datetime import timezone as _tz
    today_label = common.local_day_label()

    lane = _get_next_exploration_lane(today_label)
    if lane is None:
        # All 6 lanes already done today — log daily cap and return False
        msg = f"All forced_exploration lanes blocked for {today_label} — daily cap exhausted"
        logger.debug(msg)
        db.log_tick(
            RUNNER, "PLANNER_SKIP_FORCED_EXPLORATION_DAILY_CAP",
            message=msg[:600],
            request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_SKIP_FORCED_EXPLORATION_DAILY_CAP",
            reason="all_lanes_exhausted",
            today=today_label,
        )
        return False

    candidate = _build_forced_exploration_payload(lane, today_label)
    fallback_key = candidate["_dedupe_key"]

    # Strong second guard — key-only check (no DATE filter) catches any task with this
    # dedupe_key regardless of creation date, including SKIPPED_DUPLICATE* rows.
    existing = db.get_nonfailed_task_by_dedupe_key(fallback_key)
    if existing:
        existing_id = existing.get("id")
        existing_status = existing.get("status")
        msg = (
            f"Forced exploration {fallback_key} already exists "
            f"(id={existing_id} status={existing_status}) — skip"
        )
        logger.info(msg)
        db.log_tick(
            RUNNER, "PLANNER_SKIP_FORCED_EXPLORATION_DAILY_CAP",
            message=msg[:600],
            request_id=request_id,
        )
        common.log_jsonl(
            RUNNER, "PLANNER_SKIP_FORCED_EXPLORATION_DAILY_CAP",
            dedupe_key=fallback_key,
            existing_task_id=existing_id,
            existing_status=existing_status,
        )
        return False

    # Build task artifacts
    title = candidate["title"]
    slug = common.slugify(candidate["slug"])
    prompt_markdown = candidate["prompt_markdown"]
    contract = _build_task_contract(candidate)
    contract_ok, contract_reason = common.validate_task_contract(contract)
    if not contract_ok:
        logger.warning("Forced exploration %s invalid contract: %s", fallback_key, contract_reason)
        return False

    slot_key = common.slot_key_now()
    date_folder = common.date_folder_now()
    p_path = common.prompt_path(slot_key, slug, date_folder)
    contract_file_path = common.contract_path(slot_key, slug, date_folder)
    worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

    with open(p_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(worker_prompt)
    with open(contract_file_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)

    previous_task_id = latest["id"] if latest else None
    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=title,
        slug=slug,
        prompt_text=prompt_markdown,
        prompt_file_path=p_path,
        previous_task_id=previous_task_id,
        dedupe_key=fallback_key,
        regime_state=candidate.get("_regime_state"),
        confidence_snapshot=candidate.get("_confidence_snapshot"),
        value_score=None,
        worker_type="research",
    )
    db.update_task(task_id, planner_agent_label="Local")

    common.write_meta(
        slot_key, date_folder,
        task_id=task_id, title=title, slug=slug,
        status="QUEUED", previous_task_id=previous_task_id,
        planner_source="forced_exploration",
        planner_provider="local",
        planner_requested_provider="local",
        task_contract_path=contract_file_path,
        task_contract_version=contract.get("version"),
    )

    elapsed = int((time.time() - t0) * 1000)
    msg = (
        f"Forced exploration task {task_id} created: {title} "
        f"[{slug}] lane={lane} dedupe={fallback_key}"
    )
    logger.info(msg)
    db.log_tick(
        RUNNER, "PLANNER_CREATE_FORCED_EXPLORATION",
        task_id=task_id, message=msg, duration_ms=elapsed,
        request_id=request_id,
    )
    common.log_jsonl(
        RUNNER, "PLANNER_CREATE_FORCED_EXPLORATION",
        task_id=task_id,
        title=title,
        slug=slug,
        lane=lane,
        dedupe_key=fallback_key,
    )
    return True


def _extract_exploration_lane(dedupe_key: str) -> str:
    parts = str(dedupe_key or "").split(":")
    if len(parts) >= 2 and parts[0] == "forced_exploration":
        return parts[1]
    return ""


def _normalize_exploration_decision(raw: str) -> str:
    v = (raw or "").strip().upper()
    if not v:
        return ""
    if "WORTH_VALIDATION" in v:
        return "WORTH_VALIDATION"
    if "INCONCLUSIVE" in v:
        return "INCONCLUSIVE_NEED_DATA"
    if "WATCH" in v:
        return "WATCH_ONLY"
    if "REJECT_FOR_NOW" in v or v == "REJECT":
        return "REJECT_FOR_NOW"
    if "REJECT" in v:
        return "REJECT_FOR_NOW"
    return ""


def _extract_json_after_label(text: str, labels: list[str]) -> Optional[dict[str, Any]]:
    if not text:
        return None
    decoder = json.JSONDecoder()
    lower = text.lower()
    for label in labels:
        idx = lower.find(label.lower())
        if idx < 0:
            continue
        brace = text.find("{", idx)
        if brace < 0:
            continue
        try:
            obj, _end = decoder.raw_decode(text[brace:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _extract_report_decision_and_section7(report_path: str) -> tuple[str, str]:
    if not report_path or not os.path.exists(report_path):
        return "", ""
    try:
        text = open(report_path, "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        return "", ""

    # Prefer explicit "Final Decision:" marker.
    m = re.search(r"Final\s*Decision\s*:\s*([A-Z_]+)", text, re.I)
    if m:
        decision = _normalize_exploration_decision(m.group(1))
    else:
        # Fallback to section-6 decision block.
        decision = ""
        m6 = re.search(
            r"(?:##|###)\s*6\.\s*Decision(.*?)(?:(?:##|###)\s*7\.|$)",
            text, re.I | re.S,
        )
        if m6:
            blk = m6.group(1)
            m6d = re.search(
                r"\b(WORTH_VALIDATION|WATCH_ONLY|REJECT_FOR_NOW|REJECT|INCONCLUSIVE_NEED_DATA)\b",
                blk,
                re.I,
            )
            if m6d:
                decision = _normalize_exploration_decision(m6d.group(1))

    section7 = ""
    m7 = re.search(r"(?:##|###)\s*7\..*?(?=(?:\n##\s*\d+\.|\Z))", text, re.I | re.S)
    if m7:
        section7 = m7.group(0).strip()
    return decision, section7


def _derive_exploration_result(task: dict) -> dict[str, Any]:
    lane = _extract_exploration_lane(task.get("dedupe_key", ""))
    slot_key = task.get("slot_key") or ""
    date_folder = task.get("date_folder") or ""
    completed_text = str(task.get("completed_text") or "")

    result_obj = None
    result_path = ""
    report_path = ""
    decision = ""
    section7 = ""

    if slot_key and date_folder:
        task_dir = os.path.join(common.TASKS_ROOT, date_folder)
        matches = sorted(glob.glob(os.path.join(task_dir, f"{slot_key}-result-*.json")))
        if matches:
            result_path = matches[0]
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    result_obj = json.load(f)
            except Exception:
                result_obj = None

    task_result_json = _extract_json_after_label(
        completed_text,
        labels=["task_result_json:", "task result json:", "task result json：", "task_result_json："],
    )

    # Report path candidates (prefer task_result_json)
    for candidate in (
        (task_result_json or {}).get("report_path"),
        (result_obj or {}).get("report_path"),
        (result_obj or {}).get("output_path"),
        (result_obj or {}).get("artifact"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            p = candidate.strip()
            if not os.path.isabs(p):
                p = os.path.join(common.ROOT, p)
            report_path = p
            break

    if not report_path and isinstance(result_obj, dict):
        for path in (result_obj.get("changed_files") or []):
            if isinstance(path, str) and path.startswith("research/") and path.endswith(".md"):
                report_path = os.path.join(common.ROOT, path)
                break

    # Decision candidates (prefer explicit task_result_json)
    for raw in (
        (task_result_json or {}).get("decision"),
        (result_obj or {}).get("decision") if isinstance(result_obj, dict) else None,
        (result_obj or {}).get("final_decision") if isinstance(result_obj, dict) else None,
    ):
        if isinstance(raw, str):
            decision = _normalize_exploration_decision(raw)
            if decision:
                break

    # Report fallback parser (handles rich markdown reports).
    report_decision, report_section7 = _extract_report_decision_and_section7(report_path)
    if not decision:
        decision = report_decision
    if report_section7:
        section7 = report_section7

    # Last fallback: scan completed_text for token.
    if not decision:
        m = re.search(
            r"\b(WORTH_VALIDATION|WATCH_ONLY|REJECT_FOR_NOW|REJECT|INCONCLUSIVE_NEED_DATA)\b",
            completed_text,
            re.I,
        )
        if m:
            decision = _normalize_exploration_decision(m.group(1))

    if not section7 and isinstance(task_result_json, dict):
        nxt = task_result_json.get("next_task_prompt")
        if isinstance(nxt, str) and nxt.strip():
            section7 = nxt.strip()

    return {
        "task_id": task.get("id"),
        "lane": lane,
        "decision": decision,
        "report_path": report_path,
        "result_path": result_path,
        "section7": section7,
    }


def _upsert_exploration_routing_state(
    *,
    source_task_id: int,
    source_dedupe_key: str,
    source_lane: str,
    decision: str,
    route_action: str,
    source_report: str = "",
    followup_task_id: Optional[int] = None,
    note: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = db.get_conn()
    try:
        conn.execute(
            """
            INSERT INTO exploration_routing_state
                (source_task_id, source_dedupe_key, source_lane, decision,
                 route_action, source_report, followup_task_id, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_task_id) DO UPDATE SET
                source_dedupe_key = excluded.source_dedupe_key,
                source_lane       = excluded.source_lane,
                decision          = excluded.decision,
                route_action      = excluded.route_action,
                source_report     = excluded.source_report,
                followup_task_id  = excluded.followup_task_id,
                note              = excluded.note,
                updated_at        = excluded.updated_at
            """,
            (
                source_task_id,
                source_dedupe_key,
                source_lane,
                decision,
                route_action,
                source_report,
                followup_task_id,
                note,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _is_exploration_already_routed(source_task_id: int) -> bool:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM exploration_routing_state WHERE source_task_id = ? LIMIT 1",
            (source_task_id,),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def _append_exploration_note(today_label: str, line: str) -> str:
    notes_dir = os.path.join(common.ROOT, "runtime", "agent_orchestrator", "reports")
    os.makedirs(notes_dir, exist_ok=True)
    path = os.path.join(notes_dir, f"exploration_router_notes_{today_label}.md")
    prefix = "" if os.path.exists(path) else "# Exploration Router Notes\n\n"
    with open(path, "a", encoding="utf-8") as f:
        if prefix:
            f.write(prefix)
        f.write(f"- {line}\n")
    return path


def _create_exploration_validation_task(
    *,
    lane: str,
    source_task_id: int,
    source_report: str,
    section7: str,
    latest: Optional[dict],
    t0: float,
    request_id: Optional[str],
) -> tuple[Optional[int], str]:
    today_label = common.local_day_label()
    dedupe_key = f"validation:{lane}:{today_label}"
    existing = db.get_nonfailed_task_by_dedupe_key(dedupe_key)
    if existing:
        return None, dedupe_key

    title = f"[VALIDATION] Exploration follow-up ({lane}) — {today_label}"
    slug = common.slugify(f"validation-{lane}-{today_label}") or f"validation-{lane}"
    section7_text = section7.strip() if section7 else "N/A"
    if section7_text.upper().startswith("## 7"):
        section7_text = section7_text.split("\n", 1)[1].strip() if "\n" in section7_text else section7_text

    prompt_markdown = (
        "## Objective\n"
        f"Execute a formal validation task for forced exploration lane `{lane}`.\n\n"
        "## Scope\n"
        f"1. Source task id: `{source_task_id}`\n"
        f"2. Source lane: `{lane}`\n"
        f"3. Source report: `{source_report}`\n"
        "4. Decision: `WORTH_VALIDATION`\n"
        "5. Implement and run the proposed validation plan with reproducible evidence\n\n"
        "## Constraints\n"
        "- seed=42\n"
        "- read-only on `lottery_api/data/lottery_v2.db`\n"
        "- do not modify `active_strategy_state` / `strategy_live_state`\n"
        "- no direct strategy promotion or replacement in this task\n\n"
        "## Acceptance Criteria\n"
        "- validation objective and baseline are explicit\n"
        "- statistical test + sample size + window are explicit\n"
        "- output contains pass/fail verdict with evidence\n"
        "- required outputs produced (completed markdown + task result json + changed files)\n\n"
        "## Handoff Notes\n"
        "- fail conditions: missing statistical test, missing baseline, missing reproducible outputs\n"
        "- if data unavailable, return explicit gap list and actionable data-quality follow-up\n\n"
        "## Source Validation Prompt (Section 7)\n"
        f"{section7_text}\n"
    )

    payload = {
        "title": title,
        "slug": slug,
        "prompt_markdown": prompt_markdown,
        "task_type": "validation",
        "_signal_state_type": "validation",
        "_dedupe_key": dedupe_key,
        "_regime_state": "exploration_router",
        "_confidence_snapshot": None,
    }

    contract = _build_task_contract(payload)
    contract_ok, contract_reason = common.validate_task_contract(contract)
    if not contract_ok:
        logger.warning("Exploration validation contract invalid (%s): %s", dedupe_key, contract_reason)
        return None, dedupe_key

    slot_key = common.slot_key_now()
    date_folder = common.date_folder_now()
    p_path = common.prompt_path(slot_key, slug, date_folder)
    contract_file_path = common.contract_path(slot_key, slug, date_folder)
    worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

    with open(p_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(worker_prompt)
    with open(contract_file_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)

    previous_task_id = latest["id"] if latest else None
    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=title,
        slug=slug,
        prompt_text=prompt_markdown,
        prompt_file_path=p_path,
        previous_task_id=previous_task_id,
        dedupe_key=dedupe_key,
        regime_state=payload.get("_regime_state"),
        confidence_snapshot=payload.get("_confidence_snapshot"),
        value_score=None,
        worker_type="research",
    )
    db.update_task(task_id, planner_agent_label="Local")

    common.write_meta(
        slot_key, date_folder,
        task_id=task_id, title=title, slug=slug,
        status="QUEUED", previous_task_id=previous_task_id,
        planner_source="exploration_router",
        planner_provider="local",
        planner_requested_provider="local",
        task_contract_path=contract_file_path,
        task_contract_version=contract.get("version"),
    )

    elapsed = int((time.time() - t0) * 1000)
    msg = (
        f"Exploration validation task {task_id} created: lane={lane} "
        f"source_task_id={source_task_id} dedupe={dedupe_key}"
    )
    logger.info(msg)
    db.log_tick(
        RUNNER, "PLANNER_CREATE_EXPLORATION_VALIDATION",
        task_id=task_id, message=msg, duration_ms=elapsed,
        request_id=request_id,
    )
    common.log_jsonl(
        RUNNER, "PLANNER_CREATE_EXPLORATION_VALIDATION",
        task_id=task_id,
        source_task_id=source_task_id,
        source_lane=lane,
        source_report=source_report,
        decision="WORTH_VALIDATION",
        dedupe_key=dedupe_key,
    )
    return task_id, dedupe_key


def process_completed_exploration_tasks(
    *,
    request_id: Optional[str],
    latest: Optional[dict],
    t0: float,
) -> bool:
    """Route completed forced_exploration outputs into follow-up tasks.

    Returns True if at least one follow-up task (validation / data-quality) was created.
    """
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_tasks
            WHERE dedupe_key LIKE 'forced_exploration:%'
              AND status='COMPLETED'
            ORDER BY id DESC
            LIMIT 40
            """
        ).fetchall()
        tasks = [dict(r) for r in rows]
    finally:
        conn.close()

    created_any = False
    today_label = common.local_day_label()

    for task in tasks:
        source_task_id = int(task["id"])
        if _is_exploration_already_routed(source_task_id):
            continue

        parsed = _derive_exploration_result(task)
        lane = parsed.get("lane") or _extract_exploration_lane(task.get("dedupe_key", ""))
        decision = parsed.get("decision") or ""
        source_report = parsed.get("report_path") or ""
        section7 = parsed.get("section7") or ""

        if not decision:
            note_path = _append_exploration_note(
                today_label,
                f"task={source_task_id} lane={lane} decision=UNPARSABLE report={source_report or 'N/A'}",
            )
            _upsert_exploration_routing_state(
                source_task_id=source_task_id,
                source_dedupe_key=task.get("dedupe_key", ""),
                source_lane=lane or "unknown",
                decision="UNPARSABLE",
                route_action="UNPARSABLE_RECORDED",
                source_report=source_report,
                note=note_path,
            )
            continue

        if decision == "WORTH_VALIDATION":
            created_task_id, validation_key = _create_exploration_validation_task(
                lane=lane,
                source_task_id=source_task_id,
                source_report=source_report,
                section7=section7,
                latest=latest,
                t0=t0,
                request_id=request_id,
            )
            if created_task_id is None:
                msg = (
                    f"Exploration validation dedupe skip: source_task_id={source_task_id} "
                    f"lane={lane} dedupe={validation_key}"
                )
                db.log_tick(
                    RUNNER, "PLANNER_SKIP_EXPLORATION_VALIDATION_DEDUPE",
                    message=msg[:600], request_id=request_id,
                )
                common.log_jsonl(
                    RUNNER, "PLANNER_SKIP_EXPLORATION_VALIDATION_DEDUPE",
                    source_task_id=source_task_id,
                    source_lane=lane,
                    decision=decision,
                    dedupe_key=validation_key,
                )
                _upsert_exploration_routing_state(
                    source_task_id=source_task_id,
                    source_dedupe_key=task.get("dedupe_key", ""),
                    source_lane=lane,
                    decision=decision,
                    route_action="VALIDATION_DEDUPE_SKIPPED",
                    source_report=source_report,
                    note=validation_key,
                )
                continue

            created_any = True
            # One validation task per planner tick to avoid slot_key collision
            # and keep queue growth controlled.
            return True

        if decision == "WATCH_ONLY":
            note_path = _append_exploration_note(
                today_label,
                f"task={source_task_id} lane={lane} decision=WATCH_ONLY report={source_report or 'N/A'}",
            )
            db.log_tick(
                RUNNER, "PLANNER_SKIP_EXPLORATION_ROUTED_WATCH",
                message=f"Exploration WATCH_ONLY recorded for task {source_task_id}",
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_EXPLORATION_ROUTED_WATCH",
                source_task_id=source_task_id,
                source_lane=lane,
                source_report=source_report,
            )
            _upsert_exploration_routing_state(
                source_task_id=source_task_id,
                source_dedupe_key=task.get("dedupe_key", ""),
                source_lane=lane,
                decision=decision,
                route_action="WATCH_ONLY_RECORDED",
                source_report=source_report,
                note=note_path,
            )
            continue

        if decision == "REJECT_FOR_NOW":
            note_path = _append_exploration_note(
                today_label,
                f"task={source_task_id} lane={lane} decision=REJECT_FOR_NOW report={source_report or 'N/A'}",
            )
            db.log_tick(
                RUNNER, "PLANNER_SKIP_EXPLORATION_ROUTED_REJECT",
                message=f"Exploration REJECT recorded for task {source_task_id}",
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_EXPLORATION_ROUTED_REJECT",
                source_task_id=source_task_id,
                source_lane=lane,
                source_report=source_report,
            )
            _upsert_exploration_routing_state(
                source_task_id=source_task_id,
                source_dedupe_key=task.get("dedupe_key", ""),
                source_lane=lane,
                decision=decision,
                route_action="ARCHIVED_RECORDED",
                source_report=source_report,
                note=note_path,
            )
            continue

        if decision == "INCONCLUSIVE_NEED_DATA":
            note_path = _append_exploration_note(
                today_label,
                f"task={source_task_id} lane={lane} decision=INCONCLUSIVE_NEED_DATA report={source_report or 'N/A'}",
            )
            _upsert_exploration_routing_state(
                source_task_id=source_task_id,
                source_dedupe_key=task.get("dedupe_key", ""),
                source_lane=lane,
                decision=decision,
                route_action="INCONCLUSIVE_RECORDED",
                source_report=source_report,
                note=note_path,
            )

    return created_any


def run(dry_run: bool = False):
    common.ensure_dirs()
    t0 = time.time()
    planner_provider = "claude" if dry_run else db.get_planner_provider()
    request_id = str(os.environ.get("ORCHESTRATOR_REQUEST_ID", "")).strip() or None

    if dry_run:
        _, wiki_labels, meta_prompt = _build_meta_prompt(
            planner_provider=planner_provider,
            recent_completed=DRY_RUN_HISTORY,
        )
        _print_dry_run_preview(meta_prompt, wiki_labels)
        return

    # Health gate — block if system is marked BROKEN
    _gate_ok, _gate_reason = health.check_and_gate("planner")
    if not _gate_ok:
        logger.error("[health] Planner blocked: %s", _gate_reason)
        db.log_tick(RUNNER, "PLANNER_BLOCKED_HEALTH", message=_gate_reason, request_id=request_id)
        return

    decision = execution_policy.evaluate("planner.run", scope="main", provider=planner_provider)
    if not decision.allowed:
        msg = f"{decision.skip_reason} — skip execution"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_GLOBAL_GUARD", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_GLOBAL_GUARD", reason=decision.skip_reason)
        execution_policy.record_skip(decision, request_id=request_id)
        return

    latest = db.get_latest_task()

    should_block, blocker_msg = _resolve_previous_task_blocker(latest)
    if should_block:
        run_state = _classify_task_run_state(latest)
        elapsed_s = _task_elapsed_seconds(latest)

        if run_state == "STUCK":
            # Log idle too long — hard block, require manual recovery
            msg = (
                f"Task {latest['id']} classified STUCK — "
                f"{elapsed_s / 60:.1f}min elapsed, log idle "
                f">{common.STUCK_LOG_IDLE_THRESHOLD_SECONDS}s; manual recovery required"
            )
            logger.warning(msg)
            db.log_tick(RUNNER, "PLANNER_SKIP_STUCK_TASK", task_id=latest["id"], message=msg, request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_SKIP_STUCK_TASK", task_id=latest["id"], elapsed_seconds=int(elapsed_s))
            return

        if run_state == "LONG_RUNNING":
            # Task is legitimately long-running; allow planner to generate monitoring tasks only.
            # Temporarily suppress FORCE_RESEARCH_MODE so Layer 1 gate redirects research→monitoring.
            msg = (
                f"Task {latest['id']} LONG_RUNNING — "
                f"{elapsed_s / 60:.1f}min; allowing monitoring tasks only"
            )
            logger.info(msg)
            db.log_tick(RUNNER, "PLANNER_LONG_RUNNER_ACTIVE", task_id=latest["id"], message=msg, request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_LONG_RUNNER_ACTIVE", task_id=latest["id"], elapsed_seconds=int(elapsed_s))
            os.environ.pop("FORCE_RESEARCH_MODE", None)
            os.environ["LONG_RUNNER_ACTIVE"] = "1"  # Layer 0.5: block heavy research tasks
            # Fall through to planner execution
        else:
            # NORMAL short-running task — skip as before
            msg = blocker_msg or f"Previous task {latest['id']} still {latest['status']} — skip"
            logger.info(msg)
            db.log_tick(RUNNER, "PLANNER_SKIP_PREV_RUNNING", task_id=latest["id"], message=msg, request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_SKIP_PREV_RUNNING", task_id=latest["id"])
            return

    try:
        backlog, wiki_labels, meta_prompt = _build_meta_prompt(
            planner_provider=planner_provider,
            recent_completed=_recent_history_summary(),
        )
    except ValueError as exc:
        msg = str(exc)
        logger.warning(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_NO_BACKLOG", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_NO_BACKLOG")
        return

    # ── Adaptive Signal State Classification (3-state regime-aware gate) ─────
    signal_state = _classify_signal_state(backlog)
    state = signal_state.get("state")

    # ── Priority 0: Winner Follow-up (overrides SIGNAL_EXHAUSTED_ALL) ────────
    # When a verified winner / candidate strategy exists in the backlog, emit
    # targeted follow-up research even if TRUE_EXHAUSTED / SATURATED is active.
    if _try_emit_winner_followup_task(
        request_id=request_id, latest=latest, t0=t0, backlog=backlog
    ):
        return

    if state == SIGNAL_STATE_TRUE_EXHAUSTED:
        # Only truly stop when there is genuinely nothing to work with
        msg = (
            "[TRUE_EXHAUSTED] No strategies, no signal history, no positive edge. "
            "Cannot generate meaningful research tasks. Planner stopping."
        )
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_TRUE_EXHAUSTED", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_TRUE_EXHAUSTED",
                         exhaustion_state="TRUE_EXHAUSTED",
                         reason=signal_state.get("reason"))
        return

    if state == SIGNAL_STATE_COLD_REGIME:
        # Cold regime — generate long deep-research task via prompt_generator
        logger.info("[COLD_REGIME] %s — building long research task", signal_state.get("reason", ""))
        payload = prompt_generator.build_long_task_prompt(
            _build_generator_context(signal_state, backlog)
        )

    elif state == SIGNAL_STATE_SATURATED:
        # Saturated — generate long deep-research task via prompt_generator
        logger.info("[SIGNAL_SATURATED] %s — building long research task", signal_state.get("reason", ""))
        payload = prompt_generator.build_long_task_prompt(
            _build_generator_context(signal_state, backlog)
        )

    else:
        # No exhaustion marker — normal LLM planner path
        payload = None

    if payload is not None:
        # ── Dedupe guard for regime / saturated tasks ─────────────────────────
        task_type  = payload.get("_signal_state_type", "unknown")
        focus_hash = payload.get("_focus_hash", "")
        # Use focus_hash as variant component so different focus combinations
        # get distinct dedupe keys (they are semantically different tasks).
        # Falls back to state-based key when no focus_hash (e.g. legacy payloads).
        if focus_hash:
            regime_key = f"{task_type}:{focus_hash}"
        else:
            regime_key = _build_task_dedupe_key(task_type, state or "UNKNOWN")

        # ── Unified Planner Decision Policy ───────────────────────────────────
        # Evaluate candidate task through three layers:
        #   1. Backlog Policy Gate (SIGNAL_EXHAUSTED_ALL / NO_NEW_RESEARCH)
        #   2. Negative Space Memory gate (planner_guard)
        #   3. Taxonomy Pattern gate (accumulated category failures)
        _backlog_flags = planner_decision.extract_backlog_flags(backlog)
        _ng_result = planner_guard.check_suppressed(regime_key)
        _candidate = planner_decision.CandidateTask(
            task_type=task_type,
            dedupe_key=regime_key,
            title=payload.get("title", ""),
            backlog_flags=_backlog_flags,
        )
        pd_result = planner_decision.evaluate_candidate(_candidate, guard_result=_ng_result)

        if pd_result.action == planner_decision.ALLOW_LOW_CONFIDENCE:
            # Stochastic sampling gate — only a fraction proceed
            if random.random() > pd_result.sampling_rate:
                skip_reason = (
                    f"SOFT_SUPPRESS(sampling={pd_result.sampling_rate:.0%}): {pd_result.reason}"
                )
                logger.info("[PLANNER-DECISION] Soft suppress skip: %s", skip_reason)
                db.log_tick(
                    RUNNER, "PLANNER_SKIP_SOFT_SUPPRESS",
                    message=skip_reason[:600],
                    request_id=request_id,
                )
                common.log_jsonl(
                    RUNNER, "PLANNER_SKIP_SOFT_SUPPRESS",
                    dedupe_key=regime_key, task_type=task_type, reason=skip_reason[:300],
                )
                db.increment_dedupe_skip_count(regime_key)
                return
            # Passed sampling — proceed with low-confidence markers
            payload["title"] = f"[LOW-CONF] {payload['title']}"
            payload["_low_confidence"] = True
            payload["_label"] = _ng_result.label if _ng_result else "low-confidence"
            logger.info("[PLANNER-DECISION] %s: %s", pd_result.action, pd_result.reason)

        elif pd_result.action == planner_decision.ALLOW_RETRY:
            logger.info("[PLANNER-DECISION] %s: %s", pd_result.action, pd_result.reason)
            db.log_tick(
                RUNNER, "PLANNER_RETRY_TYPE_BLOCK",
                message=pd_result.reason[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_RETRY_TYPE_BLOCK",
                dedupe_key=regime_key, task_type=task_type,
                label=(_ng_result.label if _ng_result else ""),
            )
            # Add [CONTROLLED-RETRY] prefix
            if pd_result.title_prefix:
                payload["title"] = f"{pd_result.title_prefix} {payload['title']}"

        elif pd_result.action == planner_decision.BLOCK_NEGATIVE_SPACE:
            skip_reason = pd_result.reason
            logger.info("[PLANNER-DECISION] Hard block (negative space): %s", skip_reason)
            db.log_tick(
                RUNNER, "PLANNER_SKIP_NEGATIVE_SPACE",
                message=skip_reason[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_NEGATIVE_SPACE",
                dedupe_key=regime_key, task_type=task_type,
                label=(_ng_result.label if _ng_result else ""),
                reason=skip_reason[:300],
            )
            db.increment_dedupe_skip_count(regime_key)
            return

        elif pd_result.action == planner_decision.BLOCK_POLICY_EXHAUSTED:
            skip_reason = pd_result.reason
            logger.info("[PLANNER-DECISION] Block (policy exhausted): %s", skip_reason)
            db.log_tick(
                RUNNER, "PLANNER_SKIP_POLICY_EXHAUSTED",
                message=skip_reason[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_POLICY_EXHAUSTED",
                dedupe_key=regime_key, task_type=task_type, reason=skip_reason[:300],
            )
            db.increment_dedupe_skip_count(regime_key)
            return

        elif planner_decision.is_replace_decision(pd_result):
            # Swap in the replacement payload — block the original task
            replacement = pd_result.replacement_payload
            if replacement:
                logger.info(
                    "[PLANNER-DECISION] %s — replacing `%s` with `%s`: %s",
                    pd_result.action, task_type,
                    replacement.get("_signal_state_type", "?"), pd_result.reason,
                )
                db.log_tick(
                    RUNNER, f"PLANNER_{pd_result.action}",
                    message=pd_result.reason[:600],
                    request_id=request_id,
                )
                common.log_jsonl(
                    RUNNER, f"PLANNER_{pd_result.action}",
                    original_task_type=task_type,
                    replacement_type=replacement.get("_signal_state_type"),
                    dedupe_key=regime_key,
                    reason=pd_result.reason[:300],
                )
                # Replace payload; state/source metadata will be set below
                payload    = replacement
                task_type  = replacement.get("_signal_state_type", "replacement")
                regime_key = replacement.get("_dedupe_key", regime_key)
            else:
                # No replacement payload — fall back to plain skip
                db.increment_dedupe_skip_count(regime_key)
                return

        # pd_result.action == ALLOW → no modification

        # ── Value Scoring Gate ───────────────────────────────────────────────
        # Score the (potentially swapped) candidate before dedupe / task creation.
        # Even at MIN_VALUE_THRESHOLD=0.0 the scores are logged for analytics.
        _score_ctx = task_scorer.ScorerContext(
            task_type=payload.get("_signal_state_type", task_type),
            dedupe_key=regime_key,
            title=payload.get("title", ""),
            regime_state=state or "",
            confidence=signal_state.get("confidence_score", 0.5) if signal_state else 0.5,
            backlog_flags=_backlog_flags,
        )
        _vscore = task_scorer.score_candidate(_score_ctx)
        payload["_value_score"] = round(_vscore.total, 4)
        payload["_value_label"] = _vscore.label
        common.log_jsonl(
            RUNNER, "PLANNER_VALUE_SCORE",
            dedupe_key=regime_key,
            task_type=payload.get("_signal_state_type", task_type),
            total=round(_vscore.total, 4),
            label=_vscore.label,
            expected_edge=round(_vscore.expected_edge, 3),
            novelty_score=round(_vscore.novelty_score, 3),
            learning_value=round(_vscore.learning_value, 3),
            exploration_bonus=round(_vscore.exploration_bonus, 3),
            failure_risk=round(_vscore.failure_risk, 3),
            redundancy_penalty=round(_vscore.redundancy_penalty, 3),
            data_confidence=round(_vscore.data_confidence, 3),
        )
        if _vscore.total < task_scorer.MIN_VALUE_THRESHOLD:
            skip_reason = (
                f"VALUE_SCORE_GATE: score={_vscore.total:.3f} < "
                f"threshold={task_scorer.MIN_VALUE_THRESHOLD:.3f} "
                f"({_vscore.label}): {payload.get('_signal_state_type', task_type)}"
            )
            logger.info("[TASK-SCORER] Low-value gate: %s", skip_reason)
            db.log_tick(
                RUNNER, "PLANNER_SKIP_LOW_VALUE",
                message=skip_reason[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, "PLANNER_SKIP_LOW_VALUE",
                dedupe_key=regime_key,
                task_type=payload.get("_signal_state_type", task_type),
                score=_vscore.total,
                label=_vscore.label,
            )
            db.increment_dedupe_skip_count(regime_key)
            return

        monitor_source = (
            payload.get("_monitor_source_task_type")
            or payload.get("_replaced_task_type")
            or ""
        )
        should_skip, skip_reason = _check_task_dedupe(
            regime_key,
            signal_state,
            monitor_source_task_type=monitor_source,
        )
        if should_skip:
            logger.info("[DEDUPE] Skipping task: %s", skip_reason)
            tick_event = "PLANNER_SKIP_DEDUPE"
            if skip_reason.startswith("DUPLICATE_MONITORING_SOURCE:"):
                tick_event = "PLANNER_SKIP_DUPLICATE_MONITORING"
            elif skip_reason.startswith("DAILY_CAP_MONITORING_SOURCE:"):
                tick_event = "PLANNER_SKIP_MONITORING_DAILY_CAP"
            db.log_tick(
                RUNNER, tick_event,
                message=skip_reason[:600],
                request_id=request_id,
            )
            common.log_jsonl(
                RUNNER, tick_event,
                dedupe_key=regime_key,
                task_type=task_type,
                regime_state=state,
                skip_reason=skip_reason[:300],
                source_task_type=monitor_source or None,
            )
            db.increment_dedupe_skip_count(regime_key)
            # When monitoring replacement is blocked (daily cap or duplicate in-flight),
            # attempt winner follow-up → fallback/forced-exploration routing before idling.
            if skip_reason.startswith("DAILY_CAP_MONITORING_SOURCE:") or skip_reason.startswith("DUPLICATE_MONITORING_SOURCE:"):
                # Winner follow-up lane supersedes SIGNAL_EXHAUSTED_ALL
                if _try_emit_winner_followup_task(
                    request_id=request_id, latest=latest, t0=t0, backlog=backlog
                ):
                    return
                if not _try_emit_fallback_task(request_id=request_id, latest=latest, t0=t0):
                    # P1–P6 all blocked — try Forced Exploration (research lane) before idling
                    if not _try_emit_forced_exploration_task(
                        request_id=request_id, latest=latest, t0=t0
                    ):
                        # Forced exploration also blocked — route completed exploration
                        # outputs into validation/data follow-up tasks before idling.
                        if process_completed_exploration_tasks(
                            request_id=request_id, latest=latest, t0=t0
                        ):
                            return
                        if _try_emit_post_deployment_optimization_task(
                            request_id=request_id, latest=latest, t0=t0, backlog=backlog
                        ):
                            return
                        msg = (
                            "All P1-P6 fallback and forced exploration lanes blocked "
                            "for today — planner idle"
                        )
                        logger.info(msg)
                        db.log_tick(RUNNER, "PLANNER_IDLE_NO_ELIGIBLE_TASK",
                                    message=msg, request_id=request_id)
                        common.log_jsonl(RUNNER, "PLANNER_IDLE_NO_ELIGIBLE_TASK")
            return

        # Dedupe passed — emit regime task log only now (avoids "task logged then skipped" confusion)
        if state == SIGNAL_STATE_COLD_REGIME:
            db.log_tick(RUNNER, "PLANNER_COLD_REGIME_TASK",
                        message=f"Cold regime task: {payload['title']}",
                        request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_COLD_REGIME_TASK",
                             exhaustion_state="COLD_REGIME",
                             task_type=payload.get("_signal_state_type"),
                             reason=signal_state.get("reason"))
        elif state == SIGNAL_STATE_SATURATED:
            db.log_tick(RUNNER, "PLANNER_SATURATED_TASK",
                        message=f"Saturated task: {payload['title']}",
                        request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_SATURATED_TASK",
                             exhaustion_state="SIGNAL_SATURATED",
                             task_type=payload.get("_signal_state_type"),
                             reason=signal_state.get("reason"))

        # Regime/saturated task: bypass LLM, use the pre-built payload directly
        planner_source = "adaptive_regime"
        effective_planner_provider = "local"
        requested_planner_provider = planner_provider
        planner_error = None
        # Attach regime metadata for create_task (skip if it's a replacement payload
        # which already has its own _dedupe_key/_regime_state)
        if not payload.get("_is_replacement"):
            payload["_dedupe_key"]           = regime_key
            payload["_regime_state"]         = state
            payload["_confidence_snapshot"]  = signal_state.get("confidence_score")

    else:
        # Normal LLM planner path — no exhaustion marker
        payload, planner_source, effective_planner_provider, requested_planner_provider, planner_error = _generate_planner_payload(
            meta_prompt,
            planner_provider,
        )

    if payload is None:
        msg = f"Planner output invalid: {planner_error}"
        logger.warning(FALLBACK_WARNING, msg)
        db.log_tick(RUNNER, "PLANNER_FALLBACK_LOCAL", message=msg[:600], request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", error=msg[:600])
        if _planner_error_is_runtime_blocker(planner_error):
            skip_msg = f"Planner runtime blocked; no task created: {planner_error}"
            logger.warning(skip_msg)
            db.log_tick(RUNNER, "PLANNER_SKIP_PROVIDER_FAILURE", message=skip_msg[:600], request_id=request_id)
            common.log_jsonl(RUNNER, "PLANNER_SKIP_PROVIDER_FAILURE", error=skip_msg[:600])
            return
    elif effective_planner_provider != requested_planner_provider:
        msg = (
            f"Planner provider fallback: requested {requested_planner_provider}, "
            f"used {effective_planner_provider}"
        )
        db.log_tick(RUNNER, "PLANNER_PROVIDER_FALLBACK", message=msg, request_id=request_id)
        common.log_jsonl(
            RUNNER,
            "PLANNER_PROVIDER_FALLBACK",
            requested_provider=requested_planner_provider,
            effective_provider=effective_planner_provider,
        )

    if payload is None:
        payload = _fallback_payload(backlog)
        if planner_source == "fallback":
            common.log_jsonl(RUNNER, "PLANNER_FALLBACK_LOCAL", fallback_title=payload.get("title"))

    title = payload["title"]
    slug = common.slugify(payload["slug"])
    prompt_markdown = payload["prompt_markdown"]
    contract = _build_task_contract(payload)
    contract_ok, contract_reason = common.validate_task_contract(contract)
    if not contract_ok:
        msg = f"Planner generated invalid task contract: {contract_reason}"
        logger.warning(msg)
        db.log_tick(RUNNER, "PLANNER_INVALID_CONTRACT", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_INVALID_CONTRACT", error=contract_reason)
        return

    slot_key = common.slot_key_now()
    date_folder = common.date_folder_now()
    p_path = common.prompt_path(slot_key, slug, date_folder)
    contract_file_path = common.contract_path(slot_key, slug, date_folder)
    worker_prompt = _build_worker_prompt_with_contract(prompt_markdown, contract)

    with open(p_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(worker_prompt)
    with open(contract_file_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)

    previous_task_id = latest["id"] if latest else None
    task_id = db.create_task(
        slot_key=slot_key,
        date_folder=date_folder,
        title=title,
        slug=slug,
        prompt_text=prompt_markdown,
        prompt_file_path=p_path,
        previous_task_id=previous_task_id,
        dedupe_key=payload.get("_dedupe_key") if payload else None,
        regime_state=payload.get("_regime_state") if payload else None,
        confidence_snapshot=payload.get("_confidence_snapshot") if payload else None,
        value_score=payload.get("_value_score") if payload else None,
        worker_type=common.classify_worker_type(payload.get("_dedupe_key") if payload else None),
    )
    _pa_label = common.normalize_llm_agent_label(effective_planner_provider)["display_label"]
    db.update_task(task_id, planner_agent_label=_pa_label)
    if effective_planner_provider not in ("local", "adaptive_regime", "", None):
        db.log_llm_usage_event(
            task_id=task_id,
            runner_type="planner",
            usage_role="planner",
            provider=effective_planner_provider,
            model="",
            agent_label=_pa_label,
            call_count=1,
            event_type="task_plan",
            day_label=common.local_day_label(),
        )

    common.write_meta(slot_key, date_folder,
                      task_id=task_id, title=title, slug=slug,
                      status="QUEUED", previous_task_id=previous_task_id,
                      planner_source=planner_source,
                      planner_provider=effective_planner_provider,
                      planner_requested_provider=requested_planner_provider,
                      task_contract_path=contract_file_path,
                      task_contract_version=contract.get("version"))

    elapsed = int((time.time() - t0) * 1000)
    msg = f"Task {task_id} created: {title} [{slug}] via {planner_source}"
    logger.info(msg)
    db.log_tick(RUNNER, "PLANNER_PRODUCED", task_id=task_id, message=msg, duration_ms=elapsed, request_id=request_id)
    common.log_jsonl(
        RUNNER,
        "PLANNER_PRODUCED",
        task_id=task_id,
        title=title,
        slug=slug,
        planner_source=planner_source,
        planner_provider=effective_planner_provider,
        planner_requested_provider=requested_planner_provider,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        db.init_db()
    run(dry_run=args.dry_run)
