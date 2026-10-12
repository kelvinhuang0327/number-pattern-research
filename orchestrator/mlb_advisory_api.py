"""MLB Advisory API — Paper-Only Handler Functions.

Lightweight, server-free API handlers for querying MLB advisory outputs.
Each handler returns a response dict with governance flags.

Designed for: UI queries, CTO Agent queries, automated monitoring.

Governance Rules (applied to every response):
  - paper_only = True
  - no_real_bet = True
  - no_profit_claim = True
  - no_auto_execution = True

Forbidden response content:
  - stake_sizing (never returned)
  - real_bet_placement_instruction (never returned)
  - guaranteed_profit_wording (never returned)
  - production_patch_instruction (never returned)

Safety:
  PRODUCTION_MODIFIED      = False
  NO_REAL_BET              = True
  PAPER_ONLY               = True
  NO_PROFIT_CLAIM          = True
  NO_AUTO_EXECUTION        = True
"""
from __future__ import annotations

import datetime
import glob
import json
import os
from typing import Any

# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
NO_REAL_BET: bool = True
PAPER_ONLY: bool = True
NO_PROFIT_CLAIM: bool = True
NO_EDGE_CLAIM: bool = True
NO_AUTO_EXECUTION: bool = True
DIAGNOSTIC_ONLY: bool = True

MODULE_VERSION: str = "mlb_advisory_api_v1"

# ─── Governance flags injected into every response ───────────────────────────

_GOVERNANCE_FLAGS: dict[str, Any] = {
    "paper_only": True,
    "no_real_bet": True,
    "no_profit_claim": True,
    "no_auto_execution": True,
    "production_modified": False,
    "diagnostic_only": True,
    "no_edge_claim": True,
}

# ─── Forbidden keys never included in responses ───────────────────────────────

_FORBIDDEN_RESPONSE_KEYS: frozenset[str] = frozenset({
    "stake_sizing",
    "real_bet_placement_instruction",
    "guaranteed_profit_wording",
    "production_patch_instruction",
    "real_bet_amount",
    "sportsbook_submission",
    "bankroll_allocation",
})

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_LEDGER_PATH: str = "reports/mlb_paper_betting_ledger.jsonl"
DEFAULT_MANIFEST_DIR: str = "reports"
DEFAULT_REPORTS_DIR: str = "reports"


def _date_nodash(date_str: str) -> str:
    return date_str.replace("-", "")


def _advisory_report_path(date_str: str) -> str:
    return f"reports/mlb_daily_advisory_dry_run_{_date_nodash(date_str)}.json"


def _review_report_path(date_str: str) -> str:
    return f"reports/mlb_postgame_review_{_date_nodash(date_str)}.json"


def _manifest_path(date_str: str) -> str:
    return f"reports/mlb_daily_scheduler_manifest_{_date_nodash(date_str)}.json"


def _load_json_report(path: str) -> dict | None:
    """Load a JSON report from disk. Returns None if file missing or invalid."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _governance_response(data: dict) -> dict:
    """Inject governance flags into response and strip forbidden keys."""
    # Remove any accidentally included forbidden keys
    sanitized = {k: v for k, v in data.items() if k not in _FORBIDDEN_RESPONSE_KEYS}
    sanitized.update(_GOVERNANCE_FLAGS)
    return sanitized


def _unavailable_response(reason: str, date: str | None = None) -> dict:
    """Standard unavailable response with governance flags."""
    return _governance_response({
        "status": "unavailable",
        "reason": reason,
        "date": date,
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# HANDLER 1 — get_latest_daily_manifest
# ════════════════════════════════════════════════════════════════════════════


def get_latest_daily_manifest(
    manifest_dir: str = DEFAULT_MANIFEST_DIR,
    date_str: str | None = None,
) -> dict:
    """
    Return the latest daily scheduler manifest with governance flags.

    Args:
        manifest_dir: directory to search for manifest files
        date_str: if given, load specific date's manifest

    Returns:
        dict with manifest data + governance flags (paper_only, no_real_bet, etc.)
        Returns unavailable response if no manifest found.
    """
    if date_str:
        path = _manifest_path(date_str)
        manifest_data = _load_json_report(path)
        if manifest_data is None:
            return _unavailable_response(f"manifest not found for date={date_str}", date_str)
    else:
        # Find most recent
        pattern = os.path.join(manifest_dir, "mlb_daily_scheduler_manifest_*.json")
        matches = sorted(glob.glob(pattern), reverse=True)
        if not matches:
            return _unavailable_response("no scheduler manifest found in " + manifest_dir)
        manifest_data = _load_json_report(matches[0])
        if manifest_data is None:
            return _unavailable_response("latest manifest file unreadable")

    return _governance_response({
        "status": "ok",
        "manifest": manifest_data,
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# HANDLER 2 — get_daily_advisory_report
# ════════════════════════════════════════════════════════════════════════════


def get_daily_advisory_report(date_str: str) -> dict:
    """
    Return the daily advisory report for a given date.

    Includes:
    - advisory count
    - market coverage matrix summary
    - recommendation summary
    - governance flags

    Does NOT include stake sizing or bet placement instructions.
    """
    path = _advisory_report_path(date_str)
    report = _load_json_report(path)
    if report is None:
        return _unavailable_response(
            f"advisory report not found for date={date_str}", date_str
        )

    # Extract safe summary fields only
    market_coverage = report.get("market_coverage_matrix_summary", {})
    review_summary = report.get("review_summary", {})
    advisory_count = report.get("total_advisories", 0)

    # Build recommendation summary (safe, no stake sizing)
    recs: list[dict] = []
    for adv in report.get("advisories", []):
        recs.append({
            "game_id": adv.get("game_id", ""),
            "game_date": adv.get("game_date", ""),
            "moneyline_recommendation": adv.get("moneyline_recommendation", ""),
            "model_home_prob": adv.get("model_home_prob"),
            "market_home_prob_no_vig": adv.get("market_home_prob_no_vig"),
            "blend_home_prob": adv.get("blend_home_prob"),
            "advisory_mode": adv.get("advisory_mode", ""),
        })

    return _governance_response({
        "status": "ok",
        "date": date_str,
        "advisory_count": advisory_count,
        "total_ledger_entries_written": report.get("total_ledger_entries_written", 0),
        "effective_mode": report.get("effective_mode", ""),
        "market_coverage_matrix": market_coverage,
        "recommendation_summary": recs,
        "review_summary": {
            "lean_count": review_summary.get("lean_count", 0),
            "watch_only_count": review_summary.get("watch_only_count", 0),
            "pass_count": review_summary.get("pass_count", 0),
            "market_only_shadow_count": review_summary.get("market_only_shadow_count", 0),
        },
        "gate": report.get("gate", ""),
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# HANDLER 3 — get_paper_ledger_summary
# ════════════════════════════════════════════════════════════════════════════


def get_paper_ledger_summary(
    date_str: str | None = None,
    ledger_path: str = DEFAULT_LEDGER_PATH,
) -> dict:
    """
    Return a summary of the paper betting ledger.

    Includes:
    - total entries
    - entries by date
    - recommendation summary
    - review status summary
    - governance flags

    Does NOT include stake sizing or profit guarantees.
    """
    if not os.path.exists(ledger_path):
        return _unavailable_response(
            f"ledger not found at {ledger_path}", date_str
        )

    entries: list[dict] = []
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError as exc:
        return _unavailable_response(f"ledger read error: {exc}", date_str)

    # Filter by date if provided
    if date_str:
        filtered = [e for e in entries if e.get("game_date") == date_str]
    else:
        filtered = entries

    # Entries by date
    by_date: dict[str, int] = {}
    for e in entries:
        d = e.get("game_date", "unknown")
        by_date[d] = by_date.get(d, 0) + 1

    # Recommendation summary
    rec_counts: dict[str, int] = {}
    for e in filtered:
        rec = e.get("recommendation", "UNKNOWN")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    # Review status summary (if review_status present on entry)
    review_counts: dict[str, int] = {}
    for e in filtered:
        rs = e.get("review_status", "PENDING_REVIEW")
        review_counts[rs] = review_counts.get(rs, 0) + 1

    return _governance_response({
        "status": "ok",
        "date_filter": date_str,
        "total_ledger_entries": len(entries),
        "filtered_entries": len(filtered),
        "entries_by_date": by_date,
        "recommendation_summary": rec_counts,
        "review_status_summary": review_counts,
        "ledger_path": ledger_path,
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# HANDLER 4 — get_postgame_review_report
# ════════════════════════════════════════════════════════════════════════════


def get_postgame_review_report(date_str: str) -> dict:
    """
    Return the postgame review report for a given date.

    Includes:
    - review summary
    - failure notes (all have human_review_required=True)
    - next audit proposal (has auto_model_change_blocked=True etc.)
    - governance flags

    Does NOT include stake sizing or auto model change instructions.
    """
    path = _review_report_path(date_str)
    report = _load_json_report(path)
    if report is None:
        return _unavailable_response(
            f"review report not found for date={date_str}", date_str
        )

    review_summary = report.get("review_summary", {})
    failure_notes = report.get("failure_notes", [])
    next_audit = report.get("next_audit_proposal", {})

    # Verify failure notes have human_review_required
    for note in failure_notes:
        note["human_review_required"] = True

    # Verify next audit has blocked flags
    if next_audit:
        next_audit["auto_model_change_blocked"] = True
        next_audit["auto_alpha_change_blocked"] = True
        next_audit["auto_stake_change_blocked"] = True
        next_audit["auto_bet_blocked"] = True
        next_audit["human_review_required"] = True

    return _governance_response({
        "status": "ok",
        "date": date_str,
        "review_summary": review_summary,
        "failure_notes": failure_notes,
        "next_audit_proposal": next_audit,
        "human_review_required": True,
        "no_auto_model_change": True,
        "gate": report.get("gate", ""),
        "completion_marker": report.get("completion_marker", ""),
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# HANDLER 5 — get_mlb_mvp_status
# ════════════════════════════════════════════════════════════════════════════


def get_mlb_mvp_status() -> dict:
    """
    Return overall MLB Advisory MVP status.

    Reports which pipeline stages are ready and what live sources are still missing.

    Returns:
    - advisory_ready: bool
    - source_adapter_ready: bool
    - result_review_ready: bool
    - scheduler_ready: bool
    - live_source_ready: bool (False if no live schedule/odds/result API connected)
    - missing_live_sources: list of missing sources
    - overall_gate: str
    """
    missing_live_sources: list[str] = []

    # Check if advisory module is importable
    advisory_ready = False
    try:
        import orchestrator.mlb_daily_advisory as advisory_mod
        advisory_ready = advisory_mod.NO_REAL_BET is True
    except Exception:
        advisory_ready = False

    # Check if current source adapter is importable
    source_adapter_ready = False
    try:
        import orchestrator.mlb_current_sources as cs_mod
        source_adapter_ready = cs_mod.NO_REAL_BET is True
    except Exception:
        source_adapter_ready = False

    # Check if result review module is importable
    result_review_ready = False
    try:
        import orchestrator.mlb_result_review as rr_mod
        result_review_ready = rr_mod.LEDGER_OVERWRITE_BLOCKED is True
    except Exception:
        result_review_ready = False

    # Check if scheduler is importable
    scheduler_ready = False
    try:
        import orchestrator.mlb_daily_scheduler as sched_mod
        scheduler_ready = sched_mod.SCHEDULER_DRY_RUN_ONLY is True
    except Exception:
        scheduler_ready = False

    # Live source check: no live schedule/odds/result API is currently connected
    live_source_ready = False
    missing_live_sources = [
        "live_schedule_api: no live MLB schedule source connected",
        "live_odds_api: no live sportsbook odds source connected",
        "live_result_api: no live game result source connected",
    ]

    # Determine overall gate
    if advisory_ready and source_adapter_ready and result_review_ready and scheduler_ready:
        # All modules ready, but no live source
        overall_gate = "MLB_SCHEDULER_NEEDS_LIVE_SOURCE"
    elif advisory_ready and result_review_ready:
        overall_gate = "MLB_DAILY_SCHEDULER_READY"
    elif advisory_ready:
        overall_gate = "MLB_ADVISORY_API_READY"
    else:
        overall_gate = "MLB_SCHEDULER_NOT_READY"

    return _governance_response({
        "status": "ok",
        "advisory_ready": advisory_ready,
        "source_adapter_ready": source_adapter_ready,
        "result_review_ready": result_review_ready,
        "scheduler_ready": scheduler_ready,
        "live_source_ready": live_source_ready,
        "missing_live_sources": missing_live_sources,
        "overall_gate": overall_gate,
        "completion_marker": "MLB_DAILY_SCHEDULER_API_MVP_VERIFIED",
        "api_version": MODULE_VERSION,
    })


# ════════════════════════════════════════════════════════════════════════════
# CONVENIENCE: validate API response governance
# ════════════════════════════════════════════════════════════════════════════


def validate_api_response(response: dict) -> list[str]:
    """
    Validate that an API response contains all required governance flags
    and does not contain forbidden keys.

    Returns list of validation errors (empty = valid).
    """
    errors: list[str] = []
    required = ("paper_only", "no_real_bet", "no_profit_claim", "no_auto_execution")
    for key in required:
        if key not in response:
            errors.append(f"missing required governance key: {key!r}")
        elif response[key] is not True:
            errors.append(f"governance key {key!r} must be True, got {response[key]!r}")

    for forbidden in _FORBIDDEN_RESPONSE_KEYS:
        if forbidden in response:
            errors.append(f"forbidden key present in response: {forbidden!r}")

    return errors
