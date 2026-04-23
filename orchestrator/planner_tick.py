#!/usr/bin/env python3
"""
Claude Planner tick — triggered every 10 min by launchd.
Reads backlog.md + recent completed tasks, calls `claude -p` to produce next 8h prompt.
"""

import argparse
import sys
import os
import json
import time
import logging
import subprocess
import re
import tempfile
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [planner] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

RUNNER = "planner"
WIKI_ROOT = os.path.join(common.ROOT, "wiki")
FALLBACK_WARNING = "%s — using local fallback payload"
DRY_RUN_HISTORY = "（dry-run：略過資料庫任務歷史）"


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
    meta_prompt = common.build_planner_meta_prompt(
        backlog=backlog,
        recent_completed=recent_completed,
        wiki_context=wiki_context,
        planner_provider=planner_provider,
    )
    return backlog, wiki_labels, meta_prompt


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

    contract = {
        "version": "1.0",
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
    return contract


def _build_worker_prompt_with_contract(prompt_markdown: str, contract: dict) -> str:
    contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
    return (
        "## Task Contract (Orchestrator Enforced)\n\n"
        "Worker 必須遵守以下契約，否則任務會被標記為 REPLAN_REQUIRED：\n\n"
        f"```json\n{contract_json}\n```\n\n"
        "---\n\n"
        f"{prompt_markdown.strip()}\n"
    )


def run(dry_run: bool = False, force: bool = False):
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

    if not force and not db.is_scheduler_enabled():
        msg = "Scheduler is disabled — planner skip"
        logger.info(msg)
        db.log_tick(RUNNER, "PLANNER_SKIP_DISABLED", message=msg, request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SKIP_DISABLED")
        return

    latest = db.get_latest_task()

    if latest and latest["status"] not in ("COMPLETED", "FAILED", "CANCELLED", "REPLAN_REQUIRED"):
        msg = f"Previous task {latest['id']} still {latest['status']} — skip"
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
        # Cold regime — generate cold-phase / regime-detection task, do NOT stop
        logger.info("[COLD_REGIME] %s — generating regime-aware task", signal_state.get("reason", ""))
        payload = _build_cold_regime_payload(signal_state, backlog)
        db.log_tick(RUNNER, "PLANNER_COLD_REGIME_TASK",
                    message=f"Cold regime task: {payload['title']}",
                    request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_COLD_REGIME_TASK",
                         exhaustion_state="COLD_REGIME",
                         task_type=payload.get("_signal_state_type"),
                         reason=signal_state.get("reason"))

    elif state == SIGNAL_STATE_SATURATED:
        # Saturated — generate meta-level / quality task, do NOT stop
        logger.info("[SIGNAL_SATURATED] %s — generating meta-level task", signal_state.get("reason", ""))
        payload = _build_saturated_payload(signal_state, backlog)
        db.log_tick(RUNNER, "PLANNER_SATURATED_TASK",
                    message=f"Saturated task: {payload['title']}",
                    request_id=request_id)
        common.log_jsonl(RUNNER, "PLANNER_SATURATED_TASK",
                         exhaustion_state="SIGNAL_SATURATED",
                         task_type=payload.get("_signal_state_type"),
                         reason=signal_state.get("reason"))

    else:
        # No exhaustion marker — normal LLM planner path
        payload = None

    if payload is not None:
        # Regime/saturated task: bypass LLM, use the pre-built payload directly
        planner_source = "adaptive_regime"
        effective_planner_provider = "local"
        requested_planner_provider = planner_provider
        planner_error = None

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
    force_run = str(os.environ.get("ORCHESTRATOR_FORCE_RUN", "")).strip().lower() in ("1", "true", "yes", "on")
    run(dry_run=args.dry_run, force=force_run)
