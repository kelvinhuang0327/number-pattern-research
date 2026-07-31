#!/usr/bin/env python3
"""
Operator Decision Card — single-screen system readiness surface.

Read-only. DOES NOT run pipelines, fetch data, or consume API credits.

Usage:
  python3 scripts/ops_decision_card.py          # Standard decision card
  python3 scripts/ops_decision_card.py --json   # Machine-readable output

Data sources (read-only):
  - data/mlb_context/odds_timeline.jsonl
  - data/mlb_context/external_closing_state.json
  - logs/odds_capture.log
  - logs/daemon_heartbeat.jsonl (if present)
  - data/wbc_backend/reports/mlb_decision_quality_report.json (optional)
  - data/wbc_backend/reports/mlb_paper_tracking_report.json   (optional)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Ensure orchestrator package is importable from scripts/
import sys as _sys
if str(ROOT) not in _sys.path:
    _sys.path.insert(0, str(ROOT))

# ──────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────
TIMELINE        = ROOT / "data" / "mlb_context" / "odds_timeline.jsonl"
EXT_STATE       = ROOT / "data" / "mlb_context" / "external_closing_state.json"
CAPTURE_LOG     = ROOT / "logs" / "odds_capture.log"
HEARTBEAT_LOG   = ROOT / "logs" / "daemon_heartbeat.jsonl"
DECISION_Q_RPT  = ROOT / "data" / "wbc_backend" / "reports" / "mlb_decision_quality_report.json"
PAPER_TRACK_RPT = ROOT / "data" / "wbc_backend" / "reports" / "mlb_paper_tracking_report.json"
# Research layer paths
TRADE_LEDGER    = ROOT / "research" / "trade_ledger.jsonl"
ROI_TRACKING    = ROOT / "research" / "roi_tracking.json"
POSTMORTEM_DIR  = ROOT / "research" / "postmortem_reports"
WBC_SNAPSHOT    = ROOT / "data" / "wbc_2026_authoritative_snapshot.json"
WBC_LIVE_SCORES = ROOT / "data" / "wbc_2026_live_scores.json"


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────
def _safe_load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# S1. System Health
# ──────────────────────────────────────────────────────────────────────────
def compute_system_health() -> dict[str, Any]:
    """Read-only health summary of the research layer and daemon."""
    # Trade ledger stats
    predictions, settlements = 0, 0
    for row in _iter_jsonl(TRADE_LEDGER):
        et = row.get("event_type", "")
        if et == "prediction":
            predictions += 1
        elif et == "settlement":
            settlements += 1

    # Daemon heartbeat
    last_hb_age_min: float | None = None
    last_hb_ts: str | None = None
    last_hb_row: dict | None = None
    if HEARTBEAT_LOG.exists():
        for row in _iter_jsonl(HEARTBEAT_LOG):
            last_hb_row = row
        if last_hb_row:
            last_hb_ts = last_hb_row.get("timestamp", "")
            ts = _parse_ts(last_hb_ts or "")
            if ts:
                last_hb_age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0

    # ROI tracking freshness
    roi_updated_at: str | None = None
    roi_sample_size: int = 0
    if ROI_TRACKING.exists():
        roi = _safe_load_json(ROI_TRACKING) or {}
        if isinstance(roi, dict):
            roi_updated_at = roi.get("updated_at")
            roi_sample_size = int(roi.get("sample_size", 0))

    research_mode = bool(predictions > 0 or settlements > 0)

    return {
        "predictions": predictions,
        "settlements": settlements,
        "research_mode_active": research_mode,
        "roi_sample_size": roi_sample_size,
        "roi_updated_at": roi_updated_at or "unknown",
        "last_heartbeat_ts": last_hb_ts or "unknown",
        "last_heartbeat_age_min": round(last_hb_age_min, 1) if last_hb_age_min is not None else None,
    }


# ──────────────────────────────────────────────────────────────────────────
# S2. Today's WBC Games
# ──────────────────────────────────────────────────────────────────────────
_WBC_CODE_TO_NAME: dict[str, str] = {
    "AUS": "Australia", "BRA": "Brazil", "CAN": "Canada", "COL": "Colombia",
    "CUB": "Cuba", "CZE": "Czechia", "DOM": "Dominican Republic",
    "GBR": "Great Britain", "ISR": "Israel", "ITA": "Italy", "JPN": "Japan",
    "KOR": "Korea", "MEX": "Mexico", "NED": "Kingdom of the Netherlands",
    "NIC": "Nicaragua", "PAN": "Panama", "PUR": "Puerto Rico",
    "TPE": "Chinese Taipei", "USA": "United States", "VEN": "Venezuela",
}


def compute_today_wbc() -> dict[str, Any]:
    """Find WBC games scheduled today (or most recent), with final scores if available."""
    snap_data = _safe_load_json(WBC_SNAPSHOT)
    if not isinstance(snap_data, dict):
        return {"games": [], "today": "-", "note": "snapshot unavailable"}

    live_data = _safe_load_json(WBC_LIVE_SCORES)
    live_lookup: dict[tuple, dict] = {}
    if isinstance(live_data, dict):
        for g in (live_data.get("games") or []):
            key = (g.get("date", ""), g.get("home", ""), g.get("away", ""))
            live_lookup[key] = g
            # also swapped
            key2 = (g.get("date", ""), g.get("away", ""), g.get("home", ""))
            if key2 not in live_lookup:
                live_lookup[key2] = g

    today = datetime.now(timezone.utc).date().isoformat()
    all_dates: list[str] = sorted(
        {g.get("date", "") for g in (snap_data.get("games") or [])}
    )

    # Prefer today; fall back to nearest past date
    target_date = today
    if today not in all_dates and all_dates:
        past = [d for d in all_dates if d <= today]
        target_date = past[-1] if past else all_dates[0]

    games_out: list[dict] = []
    for g in (snap_data.get("games") or []):
        if g.get("date", "") != target_date:
            continue
        gid = g.get("canonical_game_id", "?")
        home_code = g.get("home", "?")
        away_code = g.get("away", "?")
        hname = _WBC_CODE_TO_NAME.get(home_code, home_code)
        aname = _WBC_CODE_TO_NAME.get(away_code, away_code)

        # Try to find live score
        score_str = "TBD"
        status = "scheduled"
        for delta in (-1, 0, 1):
            from datetime import date as _date, timedelta as _td
            dd = (_date.fromisoformat(target_date) + _td(days=delta)).isoformat()
            lg = live_lookup.get((dd, hname, aname)) or live_lookup.get((dd, aname, hname))
            if lg:
                hs = lg.get("home_score")
                as_ = lg.get("away_score")
                if hs is not None and as_ is not None:
                    # Determine orientation vs snap
                    if lg.get("home") == hname:
                        score_str = f"{hs}-{as_}"
                    else:
                        score_str = f"{as_}-{hs}"
                status = lg.get("status", "Final")
                break

        games_out.append({
            "game_id": gid,
            "matchup": f"{away_code}@{home_code}",
            "home": home_code,
            "away": away_code,
            "score": score_str,
            "status": status,
        })

    return {"games": games_out, "date": target_date, "note": "" if games_out else "no games on date"}


# ──────────────────────────────────────────────────────────────────────────
# S3. Recent Performance (from ROI tracker)
# ──────────────────────────────────────────────────────────────────────────
def compute_recent_performance() -> dict[str, Any]:
    """Read ROI tracking for bankroll curve summary and last-N bet results."""
    if not ROI_TRACKING.exists():
        return {"available": False}

    roi = _safe_load_json(ROI_TRACKING) or {}
    if not isinstance(roi, dict):
        return {"available": False}

    curve = roi.get("bankroll_curve") or []
    sample_size = int(roi.get("sample_size", 0))
    current_bankroll = float(roi.get("current_bankroll", 100.0))
    initial_bankroll = float(roi.get("initial_bankroll", 100.0))
    bankroll_change = float(roi.get("bankroll_change", 0.0))
    max_dd = float(roi.get("max_drawdown_pct", 0.0))

    # Last 5 bets
    last5 = curve[-5:] if len(curve) >= 5 else curve
    last5_out: list[dict] = []
    for e in last5:
        pnl = float(e.get("pnl", 0))
        eid = str(e.get("event_id", ""))
        game_id = eid.split(":")[0] if ":" in eid else eid
        last5_out.append({"game_id": game_id, "pnl": round(pnl, 4)})

    wins = sum(1 for e in curve if float(e.get("pnl", 0)) > 0)
    win_rate = (wins / len(curve) * 100) if curve else 0.0
    roi_pct = ((current_bankroll - initial_bankroll) / initial_bankroll * 100) if initial_bankroll else 0.0

    return {
        "available": True,
        "sample_size": sample_size,
        "current_bankroll": round(current_bankroll, 4),
        "bankroll_change": round(bankroll_change, 4),
        "roi_pct": round(roi_pct, 2),
        "win_rate_pct": round(win_rate, 1),
        "max_drawdown_pct": round(max_dd, 2),
        "last_5_bets": last5_out,
        "updated_at": roi.get("updated_at", "unknown"),
    }


# ──────────────────────────────────────────────────────────────────────────
# S4. Last Postmortem
# ──────────────────────────────────────────────────────────────────────────
def compute_last_postmortem() -> dict[str, Any]:
    """Read the most recent postmortem report for a quick summary."""
    if not POSTMORTEM_DIR.exists():
        return {"available": False, "count": 0}

    pm_files = sorted(POSTMORTEM_DIR.glob("*.md"))
    count = len(pm_files)
    if not pm_files:
        return {"available": False, "count": 0}

    latest = pm_files[-1]
    lines = latest.read_text(encoding="utf-8").splitlines()

    # Extract key lines: headings + first non-empty line under each heading
    summary_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            summary_lines.append(stripped)
        elif stripped.startswith("-") and len(summary_lines) < 12:
            summary_lines.append(stripped)

    return {
        "available": True,
        "count": count,
        "filename": latest.name,
        "preview": summary_lines[:10],
    }


# ──────────────────────────────────────────────────────────────────────────
# 1. CLV coverage & std
# ──────────────────────────────────────────────────────────────────────────
def compute_clv_metrics() -> dict[str, Any]:
    total_live = 0
    ext_non_null = 0
    clv_values: list[float] = []

    for row in _iter_jsonl(TIMELINE):
        source = (row.get("source") or "")
        if source.startswith("historical"):
            continue
        total_live += 1
        if row.get("external_closing_home_ml") is not None:
            ext_non_null += 1

    # CLV std: pull from decision quality report if present
    dq = _safe_load_json(DECISION_Q_RPT)
    if isinstance(dq, dict):
        for row in (dq.get("per_game") or []):
            clv = row.get("clv")
            if isinstance(clv, (int, float)) and row.get("clv_available"):
                clv_values.append(float(clv))

    coverage_pct = (ext_non_null / total_live * 100.0) if total_live else 0.0
    clv_std = statistics.pstdev(clv_values) if len(clv_values) >= 2 else 0.0

    return {
        "total_live_rows": total_live,
        "external_closing_rows": ext_non_null,
        "coverage_pct": round(coverage_pct, 2),
        "clv_samples": len(clv_values),
        "clv_std": round(clv_std, 4),
    }


# ──────────────────────────────────────────────────────────────────────────
# 2. Scheduler status
# ──────────────────────────────────────────────────────────────────────────
def compute_scheduler_status() -> dict[str, Any]:
    state = _safe_load_json(EXT_STATE) or {}
    fetched_today = bool(state.get("fetched", False))
    api_calls = int(state.get("api_calls_today", 0))
    state_date = state.get("date", "-")

    # Last daemon run — parse log
    last_run_ts: str | None = None
    last_wait_minutes: float | None = None
    if CAPTURE_LOG.exists():
        tail = CAPTURE_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-400:]
        for line in reversed(tail):
            if "Capture cycle #" in line and last_run_ts is None:
                m = re.search(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if m:
                    last_run_ts = m.group(1)
            if "Daily closing: waiting" in line and last_wait_minutes is None:
                m = re.search(r"waiting\s+—\s+(\d+)\s*min", line)
                if m:
                    last_wait_minutes = float(m.group(1))
            if last_run_ts and last_wait_minutes is not None:
                break

    # Heartbeat override (authoritative when present)
    hb_row: dict | None = None
    if HEARTBEAT_LOG.exists():
        for row in _iter_jsonl(HEARTBEAT_LOG):
            hb_row = row  # keep last

    if hb_row:
        last_run_ts = hb_row.get("timestamp", last_run_ts)
        next_trigger_min = hb_row.get("next_trigger_minutes", last_wait_minutes)
    else:
        next_trigger_min = last_wait_minutes

    return {
        "state_date": state_date,
        "fetched_today": fetched_today,
        "api_calls_today": api_calls,
        "api_cap": 2,
        "last_run_ts": last_run_ts or "unknown",
        "next_trigger_minutes": next_trigger_min,
        "heartbeat_present": hb_row is not None,
    }


# ──────────────────────────────────────────────────────────────────────────
# 3. Flag consolidation
# ──────────────────────────────────────────────────────────────────────────
_FLAG_READABLE = {
    "PAPER_ONLY":        "No live betting — paper-only mode",
    "SANDBOX_ONLY":      "Sandbox observation only",
    "UNAVAILABLE":       "Metric unavailable (data gap)",
    "HOLDOUT_REQUIRED":  "Governance requires holdout A/B before deploy",
    "KEEP_MLB_FROZEN":   "MLB paper pipeline stays frozen",
    "FROZEN":            "Pipeline frozen pending genuine pregame odds",
}


def _walk_flags(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                up = v.upper()
                for key in _FLAG_READABLE:
                    if key in up:
                        out.add(key)
                if "FROZEN_UNTIL" in up:
                    out.add("FROZEN")
            else:
                _walk_flags(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_flags(item, out)


def collect_flags() -> list[str]:
    found: set[str] = set()
    for p in (DECISION_Q_RPT, PAPER_TRACK_RPT):
        doc = _safe_load_json(p)
        if doc is not None:
            _walk_flags(doc, found)
    # De-duplicate & order
    order = ["FROZEN", "KEEP_MLB_FROZEN", "HOLDOUT_REQUIRED",
             "PAPER_ONLY", "SANDBOX_ONLY", "UNAVAILABLE"]
    ordered = [f for f in order if f in found]
    return [f"[{f}] {_FLAG_READABLE[f]}" for f in ordered]


# ──────────────────────────────────────────────────────────────────────────
# 4. Status evaluation
# ──────────────────────────────────────────────────────────────────────────
def evaluate_status(clv: dict, sched: dict) -> tuple[str, list[str]]:
    coverage = clv["coverage_pct"]
    std = clv["clv_std"]
    reasons: list[str] = []

    if coverage < 5.0:
        status = "RED"
        reasons.append(f"external_closing coverage {coverage:.2f}% < 5% — CLV pipeline blocked")
    elif coverage < 20.0:
        status = "YELLOW"
        reasons.append(f"external_closing coverage {coverage:.2f}% (partial) — below GREEN target 20%")
    else:
        status = "GREEN" if std > 0.005 else "YELLOW"
        if status == "YELLOW":
            reasons.append(f"CLV std {std:.4f} ≤ 0.005 — signal not yet meaningful")
        else:
            reasons.append(f"coverage {coverage:.2f}% and CLV std {std:.4f} meet GREEN thresholds")

    if sched["api_calls_today"] >= sched["api_cap"] and not sched["fetched_today"]:
        reasons.append("API cap hit today without successful fetch")
        if status == "GREEN":
            status = "YELLOW"

    if not sched["heartbeat_present"]:
        reasons.append("daemon heartbeat log missing — observability degraded")

    return status, reasons


# ──────────────────────────────────────────────────────────────────────────
# 5. Today-action decision
# ──────────────────────────────────────────────────────────────────────────
def recommend_action(status: str, clv: dict, sched: dict) -> str:
    if sched["fetched_today"]:
        return "DONE: external closing captured today — review CLV results, do not force re-fetch."
    if sched["api_calls_today"] >= sched["api_cap"]:
        return "HOLD: API cap reached today. Wait for next UTC day reset; investigate failure in logs."
    ntm = sched.get("next_trigger_minutes")
    if ntm is None:
        return "INVESTIGATE: scheduler state unknown. Check `launchctl list | grep com.mlb.odds`."
    if ntm <= 30:
        return f"WATCH: trigger fires in ~{ntm:.0f} min. No action; do not run manual pipelines."
    return (
        f"WAIT: trigger in ~{ntm:.0f} min. Operator idle. "
        f"Status={status}; do NOT consume API credits manually."
    )


# ──────────────────────────────────────────────────────────────────────────
# 6. Render
# ──────────────────────────────────────────────────────────────────────────
def render_card(payload: dict[str, Any]) -> str:
    bar = "=" * 40
    sub = "-" * 40

    clv = payload["clv"]
    sched = payload["scheduler"]
    status = payload["status"]
    reasons = payload["reasons"]
    flags = payload["flags"]
    action = payload["action"]

    lines: list[str] = []
    lines.append(bar)
    lines.append("📊 SYSTEM STATUS")
    lines.append(bar)
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("Reason:")
    for r in reasons:
        lines.append(f"- {r}")

    lines.append("")
    lines.append(sub)
    lines.append("📈 CLV STATUS")
    lines.append(sub)
    lines.append(f"Coverage: {clv['coverage_pct']:.2f}%  "
                 f"({clv['external_closing_rows']}/{clv['total_live_rows']} live rows)")
    lines.append(f"CLV Samples: {clv['clv_samples']}")
    lines.append(f"CLV Std: {clv['clv_std']:.4f}")

    lines.append("")
    lines.append(sub)
    lines.append("🎯 TODAY ACTION")
    lines.append(sub)
    lines.append("Recommended Action:")
    lines.append(f"- {action}")

    lines.append("")
    lines.append(sub)
    lines.append("⏱ SCHEDULER")
    lines.append(sub)
    lines.append(f"Last Run: {sched['last_run_ts']}")
    ntm = sched.get("next_trigger_minutes")
    if ntm is None:
        lines.append("Next Trigger In: unknown")
    else:
        lines.append(f"Next Trigger In: {ntm:.0f} min")
    lines.append(f"API Calls Today: {sched['api_calls_today']} / {sched['api_cap']}")
    lines.append(f"State Date: {sched['state_date']}  Fetched: {sched['fetched_today']}")
    if not sched["heartbeat_present"]:
        lines.append("Heartbeat: MISSING (logs/daemon_heartbeat.jsonl not found)")

    lines.append("")
    lines.append(sub)
    lines.append("⚠ FLAGS")
    lines.append(sub)
    if flags:
        for f in flags:
            lines.append(f)
    else:
        lines.append("- (no governance flags detected)")

    lines.append("")

    # ── System Health ──────────────────────────────────────────────
    sh = payload.get("system_health", {})
    lines.append(sub)
    lines.append("🔬 SYSTEM HEALTH (Research Layer)")
    lines.append(sub)
    lines.append(f"Research mode active : {sh.get('research_mode_active', False)}")
    lines.append(f"Trade ledger         : {sh.get('predictions', 0)} predictions / "
                 f"{sh.get('settlements', 0)} settlements")
    lines.append(f"ROI sample size      : {sh.get('roi_sample_size', 0)}")
    lines.append(f"ROI last updated     : {sh.get('roi_updated_at', 'unknown')}")
    hb_age = sh.get("last_heartbeat_age_min")
    hb_ts = sh.get("last_heartbeat_ts", "unknown")
    if hb_age is not None:
        lines.append(f"Daemon heartbeat     : {hb_ts}  ({hb_age:.0f} min ago)")
    else:
        lines.append(f"Daemon heartbeat     : {hb_ts}")

    # ── Today's WBC ───────────────────────────────────────────────
    wbc = payload.get("today_wbc", {})
    lines.append("")
    lines.append(sub)
    lines.append(f"⚾ TODAY'S WBC — {wbc.get('date', 'unknown')}")
    lines.append(sub)
    games = wbc.get("games", [])
    if games:
        for g in games:
            score = g.get("score", "TBD")
            status_str = g.get("status", "")
            lines.append(f"  [{g['game_id']}]  {g['matchup']}  {score}  [{status_str}]")
    else:
        lines.append(f"  {wbc.get('note', 'no games')}")

    # ── Recent Performance ────────────────────────────────────────
    rp = payload.get("recent_performance", {})
    lines.append("")
    lines.append(sub)
    lines.append("📉 RECENT PERFORMANCE")
    lines.append(sub)
    if rp.get("available"):
        change = rp.get('bankroll_change', 0)
        lines.append(f"Bankroll   : {rp.get('current_bankroll', 0):.4f}  "
                     f"(change: {change:+.4f}  ROI: {rp.get('roi_pct', 0):+.2f}%)")
        lines.append(f"Win rate   : {rp.get('win_rate_pct', 0):.1f}%  "
                     f"(n={rp.get('sample_size', 0)})")
        lines.append(f"Max DD     : {rp.get('max_drawdown_pct', 0):.2f}%")
        last5 = rp.get("last_5_bets", [])
        if last5:
            lines.append("Last 5 bets:")
            for bet in last5:
                pnl = bet.get('pnl', 0)
                marker = "W" if pnl > 0 else ("L" if pnl < 0 else "-")
                lines.append(f"  [{marker}] {bet.get('game_id', '?')}  pnl={pnl:+.4f}")
    else:
        lines.append("  (no ROI data available)")

    # ── Last Postmortem ───────────────────────────────────────────
    pm = payload.get("last_postmortem", {})
    lines.append("")
    lines.append(sub)
    lines.append(f"📋 LAST POSTMORTEM  ({pm.get('count', 0)} total)")
    lines.append(sub)
    if pm.get("available"):
        lines.append(f"File: {pm.get('filename', 'unknown')}")
        for line in (pm.get("preview") or []):
            lines.append(f"  {line}")
    else:
        lines.append("  (no postmortem reports found)")

    lines.append("")
    lines.append(bar)

    # ── Phase 6 Pipeline ───────────────────────────────────────────
    p6 = payload.get("phase6", {})
    lines.append(sub)
    lines.append("🔬 PHASE 6 PIPELINE STATUS")
    lines.append(sub)
    if not p6.get("available"):
        lines.append(f"  (unavailable: {p6.get('error', 'orchestrator not loaded')})")
    else:
        dates_str = ", ".join(p6.get("dates", [])) or "(none)"
        lines.append(f"Dates with data  : {dates_str}")
        lines.append(f"Registry rows    : {p6.get('registry_rows', 0)}")
        lines.append(f"CLV COMPUTED     : {p6.get('clv_computed', 0)}")
        lines.append(f"CLV PENDING      : {p6.get('clv_pending_closing', 0)}")
        lines.append(f"CLV BLOCKED      : {p6.get('clv_blocked', 0)}")
        lines.append(f"Eligible (EV>0)  : {p6.get('eligible_for_simulation', 0)}")
        if p6.get("all_clv_pending"):
            lines.append("Status           : WAITING_FOR_MARKET_SETTLEMENT")
        elif p6.get("clv_computed", 0) > 0:
            lines.append("Status           : PARTIAL_OR_FULL_COMPUTED")
        else:
            lines.append("Status           : NO_PHASE6_DATA")
        nre = p6.get("next_required_event", "")
        if nre:
            lines.append(f"Next event       : {nre}")

    lines.append("")
    lines.append(bar)

    # ── Phase 7 Closing Monitor ────────────────────────────────────
    p7 = payload.get("phase7", {})
    lines.append(sub)
    lines.append("📡 PHASE 7 CLOSING MONITOR")
    lines.append(sub)
    if not p7.get("available"):
        lines.append(f"  (unavailable: {p7.get('error', 'monitor state not found')})")
    else:
        lines.append(f"Last monitor run : {p7.get('last_run_at', '(never)')}")
        lines.append(f"Dates scanned    : {', '.join(p7.get('dates_scanned', [])) or '(none)'}")
        lines.append(f"CLV PENDING      : {p7.get('pending_clv', 0)}")
        lines.append(f"CLV COMPUTED     : {p7.get('computed_clv', 0)}")
        lines.append(f"Stale rejected   : {p7.get('stale_closing_rejected', 0)}")
        lines.append(f"Learning unlocked: {p7.get('learning_unlocked_count', 0)}")
        # Status label
        computed = p7.get("computed_clv", 0)
        pending = p7.get("pending_clv", 0)
        if computed > 0:
            lines.append("Status           : CLV_COMPUTED_READY_FOR_LEARNING")
        elif pending > 0:
            lines.append("Status           : WAITING_FOR_MARKET_SETTLEMENT")
        else:
            lines.append("Status           : BLOCKED_NO_VALID_CLOSING")

    lines.append("")
    lines.append(bar)

    # ── Phase 8 Optimization Governance ───────────────────────────
    p8 = payload.get("phase8", {})
    lines.append(sub)
    lines.append("🏛 PHASE 8 OPTIMIZATION GOVERNANCE")
    lines.append(sub)
    if not p8.get("available"):
        lines.append(f"  (unavailable: {p8.get('error', 'classifier not loaded')})")
    else:
        lines.append(f"Optimization state   : {p8.get('current_state', 'UNKNOWN')}")
        lines.append(f"Recommended action   : {p8.get('recommended_next_action', '')}")
        allowed = p8.get("allowed_task_families", [])
        blocked = p8.get("blocked_task_families", [])
        lines.append(f"Allowed families     : {', '.join(allowed) if allowed else '(all)'}")
        lines.append(f"Blocked families     : {', '.join(blocked) if blocked else '(none)'}")
        gov_reasons = p8.get("reasons", [])
        if gov_reasons:
            lines.append("Governance reasons   :")
            for r in gov_reasons:
                lines.append(f"  - {r}")
        # DATA_WAITING: explicitly surface that safe non-learning work is enabled
        if p8.get("current_state") == "DATA_WAITING":
            lines.append("Learning             : BLOCKED (CLV pending market settlement)")
            lines.append("Safe Work            : ENABLED")
            lines.append("Next safe action     : run closing-monitor / data freshness audit")

    lines.append("")
    lines.append(bar)

    # ── Phase 9 Autonomous Ops Summary ────────────────────────────
    p9 = payload.get("phase9_ops", {})
    lines.append(sub)
    lines.append("📊 AUTONOMOUS OPS SUMMARY (last 8h)")
    lines.append(sub)
    if not p9.get("available"):
        lines.append(f"  (unavailable: {p9.get('error', 'ops reporter not loaded')})")
    else:
        cl = p9.get("classification", "UNKNOWN")
        emoji_map = {
            "EFFECTIVE": "✅", "PARTIAL": "⚠️", "IDLE": "💤",
            "DEGRADED": "🔴", "BLOCKED": "🚫", "WAITING_ACTIVE": "⏳",
        }
        lines.append(f"Status               : {emoji_map.get(cl, '❓')} {cl}")
        lines.append(f"Completed tasks      : {p9.get('tasks_completed', 0)}")
        lines.append(f"Governance blocked   : {p9.get('governance_blocked', 0)}")
        lines.append(f"Patches kept         : {p9.get('patches_kept', 0)} / {p9.get('patches_validated', 0)}")
        lines.append(f"Patches rejected     : {p9.get('patches_rejected', 0)}")
        lines.append(f"CLV computed         : {p9.get('clv_computed', 0)}")
        lines.append(f"Next focus           : {p9.get('next_focus', '')}")
        # Phase 10 quality warnings
        empty_ct = p9.get("completed_empty_artifact", 0)
        noop_ct  = p9.get("completed_noop", 0)
        eff_ct   = p9.get("effective_completed_tasks", p9.get("tasks_completed", 0))
        lines.append(f"Effective completions: {eff_ct} / {p9.get('tasks_completed', 0)}")
        if empty_ct > 0 or noop_ct > 0:
            lines.append(f"⚠️  Empty artifact       : {empty_ct}")
            lines.append(f"⚠️  No-op completions    : {noop_ct}")
            lines.append("   └─ LLM provider may lack an active session (check copilot-daemon)")

    lines.append("")

    # ── Phase 13 Autonomous Readiness ─────────────────────────────
    r = payload.get("readiness", {})
    lines.append(sub)
    lines.append("🎯 AUTONOMOUS READINESS")
    lines.append(sub)
    if not r.get("available"):
        lines.append(f"  (unavailable: {r.get('error', 'readiness module not loaded')})")
    else:
        SEV_ICON = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴"}
        sev_icon = SEV_ICON.get(r.get("severity", ""), "❓")
        lines.append(f"State          : {sev_icon} {r.get('readiness_state', 'UNKNOWN')}  [{r.get('severity', '?')}]")
        lines.append(f"Learning       : {'✅ ALLOWED' if r.get('learning_allowed') else '❌ BLOCKED'}")
        lines.append(f"Reason         : {r.get('reason', '')}")
        lines.append(f"Next event     : {r.get('next_required_event', '')}")
        lines.append(f"Action         : {r.get('recommended_next_action', '')}")
        sh = r.get("skip_health", {})
        if sh:
            lines.append(f"Skip health    : {sh.get('skip_health', '?')}  "
                         f"(unexplained={sh.get('unexplained_consecutive', 0)}, "
                         f"protected={sh.get('hard_off_protected', 0)})")
        cq = r.get("completion_quality", {})
        if cq.get("total_completed", 0) > 0:
            lines.append(f"Quality        : {'✅ OK' if cq.get('quality_ok') else '⚠️  WARN'}  "
                         f"(eff={cq.get('effective_completed', 0)}/{cq.get('total_completed', 0)})")
    lines.append("")

    # ── Phase 15 Closing Odds Availability ────────────────────────
    ca = payload.get("closing_availability", {})
    lines.append(sub)
    lines.append("🔍 CLOSING ODDS AVAILABILITY")
    lines.append(sub)
    if not ca.get("available"):
        lines.append(f"  (unavailable: {ca.get('error', 'closing_odds_monitor not loaded')})")
    else:
        lines.append(f"Pending CLV          : {ca.get('pending_total', 0)}")
        lines.append(f"Computed CLV         : {ca.get('computed_total', 0)}")
        lines.append(f"External valid       : {ca.get('external_available_valid', 0)}")
        lines.append(f"External invalid     : {ca.get('external_available_invalid', 0)}")
        lines.append(f"TSL valid            : {ca.get('tsl_available_valid', 0)}")
        lines.append(f"TSL invalid          : {ca.get('tsl_available_invalid', 0)}")
        lines.append(f"Missing all sources  : {ca.get('missing_all_sources', 0)}")
        lines.append(f"Before prediction    : {ca.get('invalid_before_prediction', 0)}")
        lines.append(f"Same snapshot        : {ca.get('invalid_same_snapshot', 0)}")
        lines.append(f"Ready to upgrade     : {ca.get('ready_to_upgrade', 0)}")
        next_act = ca.get("next_closing_action", "")
        if next_act:
            lines.append(f"Next action          : {next_act}")
    lines.append("")

    # ── Phase 17 Closing Refresh Feedback ──────────────────────
    crf = payload.get("closing_refresh_feedback", {})
    if crf.get("available"):
        lines.append(sub)
        lines.append("🔄 CLOSING REFRESH FEEDBACK")
        lines.append(sub)
        improved_str = (
            "YES ✅" if crf.get("last_refresh_improved") is True
            else ("NO ❌" if crf.get("last_refresh_improved") is False else "—")
        )
        esc_str = "⚠️ YES" if crf.get("escalation_recommended") else "✅ NO"
        lines.append(f"Last action          : {crf.get('last_refresh_action') or '—'}")
        lines.append(f"Last improved        : {improved_str}")
        lines.append(f"No-imp streak        : {crf.get('consecutive_no_improvement', 0)}")
        lines.append(f"Escalation           : {esc_str}")
        lines.append(f"Next action          : {crf.get('recommended_escalation_action', 'continue')}")
        lines.append("")

    # ── Usage 詳細 ────────────────────────────────────────────────
    ud = payload.get("usage_detail", {})
    if ud:
        lines.append(sub)
        lines.append("🤖 USAGE 詳細 (LLM / AI)")
        lines.append(sub)

        # 全域告警
        for w in ud.get("warnings", []):
            lines.append(w)
        if ud.get("warnings"):
            lines.append("")

        total = ud.get("total", {})
        from orchestrator.llm_usage_summary import format_tokens
        total_tok = format_tokens(
            total.get("input_tokens", 0),
            total.get("output_tokens", 0),
            total.get("cached_tokens", 0),
        )
        window = ud.get("window", "today")
        lines.append(f"Tokens ({window})  {total_tok}")
        lines.append("")

        # 逐 role 顯示
        roles = ud.get("roles", {})
        for role_name in ("planner", "worker", "cto"):
            r = roles.get(role_name, {})
            calls = r.get("calls", 0)
            header = role_name.upper()
            lines.append(f"{header}")
            if calls == 0:
                lines.append("  今日尚無 LLM 呼叫紀錄")
            else:
                role_tok = format_tokens(
                    r.get("input_tokens", 0),
                    r.get("output_tokens", 0),
                    r.get("cached_tokens", 0),
                )
                blocked = r.get("blocked", 0)
                lines.append(f"  {calls} 次  (封鎖 {blocked})  Tokens {role_tok}")
                for agent_name, adat in r.get("agents", {}).items():
                    agent_tok = format_tokens(
                        adat.get("input_tokens", 0),
                        adat.get("output_tokens", 0),
                        adat.get("cached_tokens", 0),
                    )
                    lines.append(f"  [{agent_name}]  {adat.get('calls', 0)} 次  Tokens {agent_tok}")
            lines.append("")

        # Recent 明細表格
        recent = ud.get("recent", [])
        if recent:
            lines.append(f"最近 {len(recent)} 筆 Usage 明細")
            lines.append("| Time     | Role    | Agent           | Task  | Parsed | Premium | Tokens              | RL |")
            lines.append("|----------|---------|-----------------|-------|--------|---------|---------------------|----|")
            for row in recent:
                parsed_icon = "✅" if row.get("parsed") else "—"
                blocked_icon = " 🚫" if row.get("blocked") else ""
                lines.append(
                    f"| {row.get('time','—'):8} "
                    f"| {row.get('role','—'):7} "
                    f"| {str(row.get('agent','—'))[:15]:15} "
                    f"| {str(row.get('task_id') or '—'):5} "
                    f"| {parsed_icon:6} "
                    f"| {row.get('premium_requests',0):7} "
                    f"| {str(row.get('tokens_text','—'))[:19]:19} "
                    f"| {row.get('rate_limit','—')}{blocked_icon} |"
                )
        if ud.get("malformed_count", 0):
            lines.append(f"  ⚠️  {ud['malformed_count']} 筆損壞記錄已略過")
        lines.append("")

    lines.append(bar)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Phase 13 Autonomous Readiness
# ──────────────────────────────────────────────────────────────────────────
def compute_readiness_status() -> dict[str, Any]:
    """
    Phase 13: Aggregate all phase states into a single readiness summary.
    Read-only — never writes state.
    """
    try:
        from orchestrator.optimization_readiness import get_readiness_summary
        summary = get_readiness_summary()
        return {
            "available": True,
            "readiness_state": summary.get("readiness_state", "UNKNOWN"),
            "severity": summary.get("severity", "?"),
            "reason": summary.get("reason", ""),
            "learning_allowed": summary.get("learning_allowed", False),
            "next_required_event": summary.get("next_required_event", ""),
            "recommended_next_action": summary.get("recommended_next_action", ""),
            "safe_work_status": summary.get("safe_work", {}),
            "skip_health": summary.get("skip_health", {}),
            "completion_quality": summary.get("completion_quality", {}),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
# S5. Phase 6 pipeline status
# ──────────────────────────────────────────────────────────────────────────
def compute_phase6_status() -> dict[str, Any]:
    """
    Read Phase 6T/6U pipeline outputs (read-only via phase6_data_registry).
    Returns a dict suitable for decision card rendering.
    """
    try:
        from orchestrator import phase6_data_registry  # lazy import — optional
        p6 = phase6_data_registry.get_phase6_status()
        return {
            "available": True,
            "dates": p6.get("dates", []),
            "registry_rows": p6.get("registry_rows", 0),
            "clv_computed": p6.get("clv_computed", 0),
            "clv_pending_closing": p6.get("clv_pending_closing", 0),
            "clv_blocked": p6.get("clv_blocked", 0),
            "eligible_for_simulation": p6.get("eligible_for_simulation", 0),
            "all_clv_pending": p6.get("all_clv_pending", False),
            "next_required_event": p6.get("next_required_event", ""),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
# S6. Phase 7 closing monitor status
# ──────────────────────────────────────────────────────────────────────────
def compute_phase7_status() -> dict[str, Any]:
    """
    Read Phase 7 closing monitor state (read-only via closing_odds_monitor).
    Returns a dict suitable for decision card rendering.
    """
    try:
        from orchestrator.closing_odds_monitor import get_monitor_state  # lazy import
        state = get_monitor_state()
        if not state:
            return {"available": True, "last_run_at": None, "pending_clv": 0,
                    "computed_clv": 0, "stale_closing_rejected": 0,
                    "learning_unlocked_count": 0, "dates_scanned": []}
        return {
            "available": True,
            "last_run_at": state.get("last_run_at"),
            "dates_scanned": state.get("dates_scanned", []),
            "pending_clv": state.get("total_still_pending", 0),
            "computed_clv": state.get("total_upgraded", 0),
            "stale_closing_rejected": state.get("stale_closing_rejected", 0),
            "learning_unlocked_count": state.get("learning_unlocked_count", 0),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def compute_phase8_status(partial_payload: dict | None = None) -> dict[str, Any]:
    """
    Read Phase 8 optimization governance state (read-only via optimization_state).
    Accepts an optional partial_payload (phase6/phase7 already computed) so the
    OPERATOR_UX_GAP check can inspect the card without re-calling build_payload().
    Returns a dict suitable for decision card rendering.
    """
    try:
        from orchestrator import optimization_state  # lazy import
        result = optimization_state.classify(
            decision_card_payload=partial_payload,
        )
        return {
            "available": True,
            "current_state": result.get("state"),
            "reasons": result.get("reasons", []),
            "allowed_task_families": result.get("allowed_task_families", []),
            "blocked_task_families": result.get("blocked_task_families", []),
            "recommended_next_action": result.get("recommended_next_action", ""),
            "classified_at": result.get("classified_at"),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def compute_phase9_ops_status(window: str = "8h") -> dict[str, Any]:
    """
    Read Phase 9 ops report summary (read-only).
    Returns a condensed dict for the decision card.
    """
    try:
        from orchestrator.optimization_ops_report import generate_report
        report = generate_report(window=window)
        return {
            "available": True,
            "window": report.get("window"),
            "classification": report.get("classification"),
            "tasks_completed": report.get("tasks_completed", 0),
            "governance_blocked": report.get("governance_blocked", 0),
            "patches_validated": report.get("patches_validated", 0),
            "patches_kept": report.get("patches_kept", 0),
            "patches_rejected": report.get("patches_rejected", 0),
            "clv_computed": report.get("clv_computed", 0),
            "next_focus": report.get("next_recommended_focus", ""),
            "generated_at": report.get("generated_at"),
            # Phase 10 quality fields
            "completed_valid_tasks": report.get("completed_valid_tasks", report.get("tasks_completed", 0)),
            "completed_diagnostic_only": report.get("completed_diagnostic_only", 0),
            "completed_empty_artifact": report.get("completed_empty_artifact", 0),
            "completed_noop": report.get("completed_noop", 0),
            "effective_completed_tasks": report.get("effective_completed_tasks", report.get("tasks_completed", 0)),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
# Phase 15 — Closing Odds Availability
# ──────────────────────────────────────────────────────────────────────────
def compute_closing_availability() -> dict[str, Any]:
    """
    Phase 15: Read closing odds availability diagnostics from closing_odds_monitor.
    Read-only — never modifies files.
    """
    try:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        diag = get_pending_diagnostics()
        ss = diag.get("source_summary", {})
        return {
            "available": True,
            "pending_total":                ss.get("pending_total", 0),
            "computed_total":               ss.get("computed_total", 0),
            "external_available_valid":     ss.get("external_available_valid", 0),
            "external_available_invalid":   ss.get("external_available_invalid", 0),
            "tsl_available_valid":          ss.get("tsl_available_valid", 0),
            "tsl_available_invalid":        ss.get("tsl_available_invalid", 0),
            "missing_all_sources":          ss.get("missing_all_sources", 0),
            "invalid_before_prediction":    ss.get("invalid_before_prediction", 0),
            "invalid_same_snapshot":        ss.get("invalid_same_snapshot", 0),
            "stale_candidates":             ss.get("stale_candidates", 0),
            "ready_to_upgrade":             ss.get("ready_to_upgrade", 0),
            "recommended_refresh_tsl":      ss.get("recommended_refresh_tsl", 0),
            "recommended_refresh_external": ss.get("recommended_refresh_external", 0),
            "manual_review_required":       ss.get("manual_review_required", 0),
            "next_closing_action":          ss.get("next_closing_action", ""),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
# Phase 17 — Closing Refresh Feedback
# ──────────────────────────────────────────────────────────────────────────
def compute_closing_refresh_feedback() -> dict[str, Any]:
    """
    Phase 17: Read refresh outcome memory from closing_refresh_memory.
    Read-only — never modifies state.
    """
    try:
        from orchestrator.closing_refresh_memory import get_refresh_feedback_summary
        return get_refresh_feedback_summary()
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────
# LLM Usage Detail
# ──────────────────────────────────────────────────────────────────────────
def compute_llm_usage_detail(window: str = "today", limit: int = 10) -> dict[str, Any]:
    """讀取 llm_usage.jsonl 並回傳結構化 Usage 摘要供 Decision Card 使用。"""
    try:
        from orchestrator.llm_usage_summary import get_usage_summary
        return get_usage_summary(window=window, limit=limit)
    except Exception as exc:
        return {"available": False, "error": str(exc), "roles": {}, "recent": [], "warnings": []}


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def build_payload() -> dict[str, Any]:
    clv = compute_clv_metrics()
    sched = compute_scheduler_status()
    status, reasons = evaluate_status(clv, sched)
    flags = collect_flags()
    action = recommend_action(status, clv, sched)
    system_health = compute_system_health()
    today_wbc = compute_today_wbc()
    recent_perf = compute_recent_performance()
    last_pm = compute_last_postmortem()
    phase6 = compute_phase6_status()
    phase7 = compute_phase7_status()
    # Pass partial_payload so classify() can run OPERATOR_UX_GAP check
    # without calling build_payload() again → prevents infinite recursion.
    phase8 = compute_phase8_status(partial_payload={"phase6": phase6, "phase7": phase7})
    phase9_ops = compute_phase9_ops_status(window="8h")
    readiness = compute_readiness_status()
    closing_availability = compute_closing_availability()
    closing_refresh_feedback = compute_closing_refresh_feedback()
    usage_detail = compute_llm_usage_detail()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "reasons": reasons,
        "clv": clv,
        "scheduler": sched,
        "flags": flags,
        "action": action,
        "system_health": system_health,
        "today_wbc": today_wbc,
        "recent_performance": recent_perf,
        "last_postmortem": last_pm,
        "phase6": phase6,
        "phase7": phase7,
        "phase8": phase8,
        "phase9_ops": phase9_ops,
        "readiness": readiness,
        "closing_availability": closing_availability,
        "closing_refresh_feedback": closing_refresh_feedback,
        "usage_detail": usage_detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Operator decision card (read-only).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    payload = build_payload()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_card(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
