"""
H6 Daily Operations Report Generator
======================================
為 DAILY_539 H6 策略生成每日營運報告（JSON + Markdown）。

報告涵蓋：
  - 本期預測 / 開獎結果 / 命中表現
  - Live monitoring 指標（live edge / rollback / bear warning）
  - 最近 10 期趨勢摘要
  - 風險評估（LOW / MEDIUM / HIGH）
  - 行動建議（CONTINUE_H6 / MONITOR_CLOSELY / PREPARE_ROLLBACK /
               ROLLBACK_ACTIVE / MANUAL_REVIEW_REQUIRED）

2026-04-29  Created (H6 Daily Operations Report, Phase 6)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from engine.draw_no_hygiene import is_production_draw_no, is_test_draw_no, production_draw_no_sql_filter

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────────────

def _get_project_root() -> str:
    # lottery_api/engine/h6_report_generator.py → project root = ../../../
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", ".."))


def _get_db_path() -> str:
    return os.path.join(
        _get_project_root(), "runtime", "agent_orchestrator", "orchestrator.db"
    )


def _default_output_dir() -> str:
    return os.path.join(_get_project_root(), "runtime", "h6_daily_reports")


# ── constants ────────────────────────────────────────────────────────────────

PAYOUT_TABLE = {5: 2400.0, 4: 20.0, 3: 3.0, 2: 0.0, 1: 0.0, 0: 0.0}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── DB helpers ────────────────────────────────────────────────────────────────

def _fetch_prediction(conn: sqlite3.Connection, game_type: str, draw_no: str, strategy_name: str) -> Optional[dict]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT id, game_type, draw_no, strategy_name, active_strategy,
                  shadow_strategy, predicted_numbers, generated_at
           FROM live_strategy_predictions
           WHERE game_type=? AND draw_no=? AND strategy_name=?""",
        (game_type, draw_no, strategy_name),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["predicted_numbers"] = json.loads(d["predicted_numbers"] or "[]")
    except Exception:
        d["predicted_numbers"] = []
    return d


def _fetch_outcome(conn: sqlite3.Connection, game_type: str, draw_no: str, strategy_name: str) -> Optional[dict]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """SELECT id, strategy_id, game_type, draw_id, recorded_at,
                  predicted_json, actual_json, match_count, bet_units,
                  payout_units, pnl, roi, accuracy_score
           FROM live_strategy_outcomes
           WHERE game_type=? AND draw_id=? AND strategy_id=?""",
        (game_type, draw_no, strategy_name),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    for k in ("predicted_json", "actual_json"):
        try:
            d[k] = json.loads(d[k] or "[]")
        except Exception:
            d[k] = []
    return d


def _fetch_latest_draw_no(conn: sqlite3.Connection, game_type: str, strategy_name: str) -> Optional[str]:
    """Return draw_no of the most recent *production* prediction (by generated_at DESC)."""
    sql_filter = production_draw_no_sql_filter("draw_no", game_type)
    row = conn.execute(
        f"""SELECT draw_no FROM live_strategy_predictions
           WHERE game_type=? AND strategy_name=?
             AND {sql_filter}
           ORDER BY generated_at DESC LIMIT 1""",
        (game_type, strategy_name),
    ).fetchone()
    return row[0] if row else None


def _fetch_recent_outcomes(
    conn: sqlite3.Connection, game_type: str, strategy_name: str, limit: int = 10
) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT draw_id, match_count, roi, pnl, payout_units, recorded_at
           FROM live_strategy_outcomes
           WHERE game_type=? AND strategy_id=?
           ORDER BY draw_id DESC LIMIT ?""",
        (game_type, strategy_name, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_ass(conn: sqlite3.Connection, game_type: str) -> dict:
    """Fetch active_strategy_state row."""
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM active_strategy_state WHERE game_type=?", (game_type,)
    ).fetchone()
    return dict(row) if row else {}


# ── compute helpers ───────────────────────────────────────────────────────────

def _compute_hit_counts_per_bet(predicted_numbers: list, winning_set: set) -> list:
    """Given multi-bet list (list of lists) or flat list, return hits per bet."""
    if not predicted_numbers:
        return [0]
    if isinstance(predicted_numbers[0], list):
        return [len(set(int(n) for n in bet) & winning_set) for bet in predicted_numbers]
    # flat single bet
    return [len(set(int(n) for n in predicted_numbers) & winning_set)]


def _compute_risk_assessment(
    rollback_status: str,
    live_30p_edge: Optional[float],
    consecutive_neg: int,
    bear_warning: bool,
    recent_match_counts: list,
) -> dict:
    edge_30 = live_30p_edge or 0.0
    risk_factors = []
    risk_level = "LOW"

    if rollback_status != "ACTIVE":
        risk_level = "HIGH"
        risk_factors.append(f"rollback_status={rollback_status}")

    if edge_30 < -0.02:
        if risk_level != "HIGH":
            risk_level = "HIGH"
        risk_factors.append(f"live_30p_edge={edge_30:.4f} < -0.02 (threshold)")

    if bear_warning:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        risk_factors.append("bear_regime_warning=true")

    if -0.02 <= edge_30 < -0.01:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        risk_factors.append(f"live_30p_edge={edge_30:.4f} < -0.01")

    if consecutive_neg >= 5:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        risk_factors.append(f"consecutive_negative_30p={consecutive_neg} >= 5")
    elif consecutive_neg >= 3:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        risk_factors.append(f"consecutive_negative_30p={consecutive_neg} >= 3")

    # Recent hit trend: if last 5 outcomes all have match_count <= 1
    if len(recent_match_counts) >= 5:
        last5 = recent_match_counts[:5]
        if all(m <= 1 for m in last5):
            if risk_level == "LOW":
                risk_level = "MEDIUM"
            risk_factors.append(f"last 5 draws: max_hit={max(last5)} (all ≤1)")

    return {"risk_level": risk_level, "risk_factors": risk_factors}


def _compute_action(risk_assessment: dict, rollback_status: str) -> dict:
    risk_level = risk_assessment["risk_level"]
    risk_factors = risk_assessment["risk_factors"]

    if rollback_status == "ROLLBACK_TRIGGERED":
        return {
            "action": "ROLLBACK_ACTIVE",
            "reason": "Rollback has been triggered. Shadow strategy is now active. CTO review required.",
        }
    if risk_level == "HIGH":
        return {
            "action": "PREPARE_ROLLBACK",
            "reason": f"High risk detected: {'; '.join(risk_factors)}. Monitor next 1-2 draws closely.",
        }
    if risk_level == "MEDIUM":
        return {
            "action": "MONITOR_CLOSELY",
            "reason": f"Medium risk: {'; '.join(risk_factors)}. Continue but watch edge trend.",
        }
    return {
        "action": "CONTINUE_H6",
        "reason": "Strategy performing within expected parameters. No action required.",
    }


def _compute_losing_streak(recent_rois: list) -> int:
    streak = 0
    for roi in recent_rois:
        if roi is not None and roi < 0:
            streak += 1
        else:
            break
    return streak


# ── markdown builder ──────────────────────────────────────────────────────────

def _build_markdown(report: dict) -> str:
    meta = report["report_meta"]
    strat = report["strategy"]
    pred = report["this_draw_prediction"]
    outcome = report["this_draw_outcome"]
    mon = report["live_monitoring"]
    recent = report["recent_outcomes_summary"]
    risk = report["risk_assessment"]
    action = report["action_recommendation"]

    lines = []

    def h(level: int, text: str):
        lines.append(f"\n{'#' * level} {text}\n")

    def row(label: str, val):
        lines.append(f"- **{label}**: {val}")

    h(1, f"H6 DAILY_539 — Daily Operations Report")
    lines.append(f"> draw_no: `{meta['draw_no']}` | generated: `{meta['generated_at'][:19]}Z` | status: **{meta['report_status']}**")

    h(2, "1. Report Header")
    row("report_date", meta["report_date"])
    row("game_type", meta["game_type"])
    row("active_strategy", strat["active_strategy"])
    row("shadow_strategy", strat["shadow_strategy"] or "N/A")
    row("rollback_status", f"**{strat['rollback_status']}**")
    row("planner_focus", strat.get("planner_focus") or "N/A")

    h(2, "2. 本期預測")
    if pred.get("found"):
        row("draw_no", pred["draw_no"])
        row("prediction_record_id", pred.get("prediction_record_id", "N/A"))
        row("generated_at", pred.get("generated_at", "N/A"))
        row("bet_count", pred.get("bet_count", 1))
        for i, bet in enumerate(pred.get("predicted_bets", []), 1):
            row(f"bet_{i}", bet)
    else:
        lines.append("⚠️  **本期無預測記錄**（draw_no 不存在於 live_strategy_predictions）")

    h(2, "3. 本期開獎結果")
    if outcome.get("status") == "PENDING_OUTCOME":
        lines.append("⏳ **PENDING_OUTCOME** — 開獎結果尚未記錄。請執行：")
        lines.append(f"```bash\npython3 scripts/h6_record_outcome.py --draw_no {meta['draw_no']} --winning \"N1,N2,N3,N4,N5\"\n```")
    elif outcome.get("status") == "RECORDED":
        row("winning_numbers", outcome.get("winning_numbers", []))
        row("recorded_at", outcome.get("recorded_at", "N/A"))
        hit_per_bet = outcome.get("hit_counts_per_bet", [])
        for i, h_cnt in enumerate(hit_per_bet, 1):
            row(f"bet_{i}_hits", h_cnt)
        row("best_hit_count", outcome.get("best_hit_count", 0))
        row("match_count (stored)", outcome.get("match_count", 0))
        row("roi", f"{outcome.get('roi', 0):.4f}")
        row("pnl", f"{outcome.get('pnl', 0):.4f}")
    else:
        lines.append("❓ 開獎資料不完整")

    h(2, "4. Live Monitoring")
    edge_30 = mon.get("live_30p_edge")
    edge_50 = mon.get("live_50p_edge")
    row("live_30p_edge", f"{edge_30:.4f}" if edge_30 is not None else "N/A")
    row("live_50p_edge", f"{edge_50:.4f}" if edge_50 is not None else "N/A")
    row("consecutive_negative_30p", mon.get("consecutive_negative_30p", 0))
    row("current_regime", mon.get("current_regime") or "N/A")
    row("bear_regime_warning", "⚠️  **true**" if mon.get("bear_regime_warning") else "false")
    row("rollback_triggered", "🚨 **true**" if mon.get("rollback_triggered") else "false")
    row("rollback_reason", mon.get("rollback_reason") or "—")

    h(2, "5. Recent Outcomes (last 10)")
    row("count", recent.get("count", 0))
    row("avg_roi", f"{recent.get('avg_roi', 0):.4f}" if recent.get("avg_roi") is not None else "N/A")
    row("avg_match_count", f"{recent.get('avg_match_count', 0):.2f}" if recent.get("avg_match_count") is not None else "N/A")
    row("max_hit", recent.get("max_hit", 0))
    row("losing_streak (roi<0)", recent.get("losing_streak", 0))
    trend = recent.get("best_hit_trend", [])
    row("best_hit_trend (newest→oldest)", trend)

    h(2, "6. Risk Assessment")
    risk_icon = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🚨"}.get(risk["risk_level"], "")
    lines.append(f"\n**Risk Level: {risk_icon} {risk['risk_level']}**\n")
    if risk["risk_factors"]:
        for f_item in risk["risk_factors"]:
            lines.append(f"- {f_item}")
    else:
        lines.append("- No risk factors detected")

    h(2, "7. Action Recommendation")
    action_icon = {
        "CONTINUE_H6": "✅",
        "MONITOR_CLOSELY": "🔍",
        "PREPARE_ROLLBACK": "⚠️",
        "ROLLBACK_ACTIVE": "🚨",
        "MANUAL_REVIEW_REQUIRED": "❓",
    }.get(action["action"], "")
    lines.append(f"\n**{action_icon} {action['action']}**\n")
    lines.append(f"> {action['reason']}")

    lines.append(f"\n---\n*Generated by H6 Daily Operations Report | {meta['generated_at'][:19]}Z*")

    return "\n".join(lines)


# ── main public function ──────────────────────────────────────────────────────

def generate_report(
    game_type: str = "DAILY_539",
    draw_no: Optional[str] = None,
    latest: bool = False,
    output_dir: Optional[str] = None,
    strategy_name: Optional[str] = None,
) -> dict:
    """
    Generate H6 daily operations report for a given draw_no.

    Parameters
    ----------
    game_type   : target game (default "DAILY_539")
    draw_no     : explicit draw number; mutually exclusive with latest=True
    latest      : if True, auto-detect the most recent draw_no from DB
    output_dir  : where to write .json and .md files
                  (default: runtime/h6_daily_reports/)
    strategy_name: defaults to H6_STRATEGY_ID

    Returns
    -------
    dict — full report structure; also writes JSON + Markdown files.
    Raises ValueError only for invalid draw_no format.
    """
    # ── lazy import to avoid circular deps ──────────────────────────────────
    try:
        from engine.h6_live_monitor import H6_STRATEGY_ID, SHADOW_STRATEGY_ID, get_monitoring_state
    except ModuleNotFoundError:
        # when called from scripts/ with explicit sys.path
        import sys as _sys
        _here = os.path.dirname(os.path.abspath(__file__))
        _sys.path.insert(0, os.path.dirname(_here))
        from engine.h6_live_monitor import H6_STRATEGY_ID, SHADOW_STRATEGY_ID, get_monitoring_state

    _strategy = strategy_name or H6_STRATEGY_ID
    out_dir = output_dir or _default_output_dir()
    os.makedirs(out_dir, exist_ok=True)

    generated_at = _now_iso()
    today = generated_at[:10]

    # ── open DB ──────────────────────────────────────────────────────────────
    db_path = _get_db_path()
    db_ok = os.path.exists(db_path)

    conn: Optional[sqlite3.Connection] = None
    if db_ok:
        conn = sqlite3.connect(db_path, timeout=5)

    # ── resolve draw_no ──────────────────────────────────────────────────────
    if draw_no is None:
        if latest and conn:
            draw_no = _fetch_latest_draw_no(conn, game_type, _strategy)
        if not draw_no:
            draw_no = "UNKNOWN"

    # ── validate draw_no (only block truly bad input) ────────────────────────
    if draw_no.upper() == "PENDING":
        if conn:
            conn.close()
        raise ValueError("draw_no='PENDING' is invalid for report generation")

    # ── fetch data ───────────────────────────────────────────────────────────
    pred_row: Optional[dict] = None
    outcome_row: Optional[dict] = None
    recent_outcomes: list = []
    ass: dict = {}

    if conn:
        pred_row = _fetch_prediction(conn, game_type, draw_no, _strategy)
        outcome_row = _fetch_outcome(conn, game_type, draw_no, _strategy)
        recent_outcomes = _fetch_recent_outcomes(conn, game_type, _strategy, limit=10)
        ass = _fetch_ass(conn, game_type)
        conn.close()

    # ── monitoring state ─────────────────────────────────────────────────────
    try:
        mon = get_monitoring_state(game_type)
    except Exception:
        mon = {
            "live_30p_edge": None,
            "live_50p_edge": None,
            "consecutive_negative_30p": 0,
            "current_regime": None,
            "bear_regime_warning": False,
            "rollback_triggered": False,
            "rollback_status": "ACTIVE",
            "rollback_reason": None,
        }

    rollback_status = ass.get("rollback_status") or mon.get("rollback_status") or "ACTIVE"
    active_strategy = ass.get("active_strategy") or H6_STRATEGY_ID
    shadow_strategy = ass.get("shadow_strategy") or SHADOW_STRATEGY_ID
    planner_focus = ass.get("planner_focus") or "MONITOR"

    # ── determine report_status ──────────────────────────────────────────────
    if pred_row is None and outcome_row is None:
        report_status = "NO_DATA"
    elif outcome_row is None:
        report_status = "PENDING_OUTCOME"
    else:
        report_status = "COMPLETE"

    # ── this_draw_prediction section ─────────────────────────────────────────
    if pred_row:
        pred_nums = pred_row.get("predicted_numbers", [])
        # Normalize to list-of-lists
        if pred_nums and not isinstance(pred_nums[0], list):
            pred_nums = [pred_nums]  # single bet
        this_pred = {
            "found": True,
            "draw_no": draw_no,
            "predicted_bets": pred_nums,
            "generated_at": pred_row.get("generated_at"),
            "prediction_record_id": pred_row.get("id"),
            "bet_count": len(pred_nums),
        }
    else:
        this_pred = {
            "found": False,
            "draw_no": draw_no,
            "predicted_bets": [],
            "generated_at": None,
            "prediction_record_id": None,
            "bet_count": 0,
        }

    # ── this_draw_outcome section ─────────────────────────────────────────────
    if outcome_row:
        winning_set = set(int(n) for n in outcome_row.get("actual_json", []))
        pred_nums_for_hits = this_pred["predicted_bets"] if this_pred["found"] else []
        hit_counts = _compute_hit_counts_per_bet(pred_nums_for_hits, winning_set)
        best_hit = max(hit_counts) if hit_counts else 0
        this_outcome = {
            "status": "RECORDED",
            "winning_numbers": sorted(winning_set),
            "recorded_at": outcome_row.get("recorded_at"),
            "hit_counts_per_bet": hit_counts,
            "best_hit_count": best_hit,
            "match_count": outcome_row.get("match_count", 0),
            "roi": outcome_row.get("roi", -1.0),
            "pnl": outcome_row.get("pnl", -1.0),
            "payout_units": outcome_row.get("payout_units", 0.0),
            "bet_units": outcome_row.get("bet_units", 1.0),
        }
    else:
        this_outcome = {
            "status": "PENDING_OUTCOME",
            "winning_numbers": None,
            "recorded_at": None,
            "hit_counts_per_bet": [],
            "best_hit_count": None,
            "match_count": None,
            "roi": None,
            "pnl": None,
            "payout_units": None,
            "bet_units": None,
        }

    # ── recent_outcomes_summary ───────────────────────────────────────────────
    match_counts = [r.get("match_count", 0) for r in recent_outcomes]
    rois = [r.get("roi") for r in recent_outcomes if r.get("roi") is not None]
    avg_roi = sum(rois) / len(rois) if rois else None
    avg_match = sum(match_counts) / len(match_counts) if match_counts else None
    losing_streak = _compute_losing_streak(
        [r.get("roi", 0) for r in recent_outcomes]
    )
    recent_summary = {
        "count": len(recent_outcomes),
        "best_hit_trend": match_counts,
        "avg_roi": avg_roi,
        "avg_match_count": avg_match,
        "max_hit": max(match_counts) if match_counts else 0,
        "losing_streak": losing_streak,
    }

    # ── risk assessment ───────────────────────────────────────────────────────
    risk = _compute_risk_assessment(
        rollback_status=rollback_status,
        live_30p_edge=mon.get("live_30p_edge"),
        consecutive_neg=mon.get("consecutive_negative_30p") or 0,
        bear_warning=bool(mon.get("bear_regime_warning")),
        recent_match_counts=match_counts,
    )

    # ── action recommendation ─────────────────────────────────────────────────
    action = _compute_action(risk, rollback_status)

    # ── assemble report ───────────────────────────────────────────────────────
    report = {
        "report_meta": {
            "report_date": today,
            "generated_at": generated_at,
            "game_type": game_type,
            "draw_no": draw_no,
            "report_status": report_status,
            "strategy_name": _strategy,
            "environment": "test" if is_test_draw_no(draw_no, game_type) else "production",
        },
        "strategy": {
            "active_strategy": active_strategy,
            "shadow_strategy": shadow_strategy,
            "rollback_status": rollback_status,
            "planner_focus": planner_focus,
        },
        "this_draw_prediction": this_pred,
        "this_draw_outcome": this_outcome,
        "live_monitoring": {
            "live_30p_edge": mon.get("live_30p_edge"),
            "live_50p_edge": mon.get("live_50p_edge"),
            "consecutive_negative_30p": mon.get("consecutive_negative_30p", 0),
            "current_regime": mon.get("current_regime"),
            "bear_regime_warning": bool(mon.get("bear_regime_warning")),
            "rollback_triggered": bool(mon.get("rollback_triggered")),
            "rollback_reason": mon.get("rollback_reason"),
            "thresholds": {
                "rollback_edge": -0.02,
                "bear_edge": -0.0193,
                "consecutive_neg_limit": 5,
            },
        },
        "recent_outcomes_summary": recent_summary,
        "risk_assessment": risk,
        "action_recommendation": action,
    }

    # ── write output files ────────────────────────────────────────────────────
    safe_draw = draw_no.replace("/", "-").replace("\\", "-")
    base_name = f"H6_{game_type}_REPORT_{safe_draw}"
    json_path = os.path.join(out_dir, f"{base_name}.json")
    md_path = os.path.join(out_dir, f"{base_name}.md")

    report["output"] = {
        "json_path": json_path,
        "markdown_path": md_path,
    }

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("h6_report_generator: could not write JSON: %s", exc)

    try:
        md_content = _build_markdown(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
    except Exception as exc:
        logger.warning("h6_report_generator: could not write Markdown: %s", exc)

    return report


def get_latest_report_summary(game_type: str = "DAILY_539") -> Optional[dict]:
    """
    Return a brief summary of the latest daily operations report.
    Used by orchestrator summary endpoint.
    """
    try:
        report = generate_report(game_type=game_type, latest=True)
        meta = report.get("report_meta", {})
        risk = report.get("risk_assessment", {})
        action = report.get("action_recommendation", {})
        mon = report.get("live_monitoring", {})
        return {
            "draw_no": meta.get("draw_no"),
            "report_status": meta.get("report_status"),
            "report_date": meta.get("report_date"),
            "risk_level": risk.get("risk_level"),
            "action": action.get("action"),
            "rollback_status": report.get("strategy", {}).get("rollback_status"),
            "live_30p_edge": mon.get("live_30p_edge"),
            "json_path": report.get("output", {}).get("json_path"),
            "markdown_path": report.get("output", {}).get("markdown_path"),
        }
    except Exception as exc:
        logger.warning("h6_report_generator.get_latest_report_summary error: %s", exc)
        return None
