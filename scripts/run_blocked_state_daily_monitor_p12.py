"""P12-D — Blocked-State Daily Monitor.

Reads current state files (CEO decision, API key flag, forward pair coverage,
CLV gate status) and outputs a single-snapshot governance summary:
  - current blocker
  - allowed next action
  - forbidden next action
  - whether P13 may start
  - paper_only=true

No network calls. No TSL crawler modification. Read-only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedStateGovernance,
    ForbiddenAction,
    PaperOnlyViolationError,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent.parent

DEFAULT_CEO_DECISION_PATH = BASE / "data/paper_recommendations/p11_ceo_odds_source_decision_20260527.json"
DEFAULT_API_KEY_FLAG_PATH = BASE / "data/paper_recommendations/api_key_readiness_flag.json"
DEFAULT_FORWARD_READINESS_PATH = BASE / "data/paper_recommendations/p11_forward_collection_readiness_20260527.json"
DEFAULT_CLV_STATUS_PATH = BASE / "data/paper_recommendations/p11_system_status_refresh_20260527.json"
DEFAULT_OUTPUT_PATH = BASE / "data/paper_recommendations/p12_daily_monitor_result_20260528.json"

# Thresholds (must match P8-P11)
MIN_PAIRS_FOR_CLV: int = 200
MIN_PAIR_COVERAGE_PCT: float = 90.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json_safe(path: Path) -> dict | None:
    """Return parsed JSON or None if file missing / unparseable."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _assess_state(
    ceo_decision_path: Path = DEFAULT_CEO_DECISION_PATH,
    api_key_flag_path: Path = DEFAULT_API_KEY_FLAG_PATH,
    forward_readiness_path: Path = DEFAULT_FORWARD_READINESS_PATH,
    clv_status_path: Path = DEFAULT_CLV_STATUS_PATH,
    paper_only: bool = True,
) -> dict:
    """Read all state files and derive governance flags.

    Returns a dict of raw boolean flags and source data.
    Does NOT perform any network calls.
    """
    if not paper_only:
        raise PaperOnlyViolationError(
            "run_blocked_state_daily_monitor_p12 must run with paper_only=True."
        )

    # --- CEO decision ---
    ceo_data = _read_json_safe(ceo_decision_path)
    ceo_decision_pending: bool
    ceo_decision_value: str
    if ceo_data is None:
        ceo_decision_pending = True
        ceo_decision_value = "DEFER_DECISION"
    else:
        ceo_decision_value = ceo_data.get("ceo_decision", "DEFER_DECISION")
        ceo_decision_pending = ceo_decision_value not in (
            "APPROVE_PATH_A_WITH_API_KEY",
            "REJECT_PATH_A_USE_FORWARD_ONLY",
        )

    # --- API key flag ---
    ceo_approved_path_a = ceo_decision_value == "APPROVE_PATH_A_WITH_API_KEY"
    api_key_data = _read_json_safe(api_key_flag_path)
    api_key_ready = bool(
        api_key_data is not None
        and api_key_data.get("api_key_available") is True
        and api_key_data.get("allow_sample_api_call") is True
    )
    api_key_missing = ceo_approved_path_a and not api_key_ready

    # --- Forward coverage ---
    fwd_data = _read_json_safe(forward_readiness_path)
    forward_pairs: int = int(fwd_data.get("pair_count", 0)) if fwd_data else 0
    forward_coverage_pct: float = float(fwd_data.get("pair_coverage_pct", 0.0)) if fwd_data else 0.0
    forward_clv_status: str = fwd_data.get("clv_readiness_status", "ACCUMULATION_INSUFFICIENT") if fwd_data else "ACCUMULATION_INSUFFICIENT"

    clv_ready_candidate = forward_clv_status == "CLV_READY_CANDIDATE"
    forward_accumulation_insufficient = not clv_ready_candidate and forward_pairs < MIN_PAIRS_FOR_CLV
    no_closing_line = not clv_ready_candidate and forward_pairs > 0 and forward_coverage_pct < MIN_PAIR_COVERAGE_PCT

    # --- CLV status ---
    clv_data = _read_json_safe(clv_status_path)
    clv_status_raw: str = (
        clv_data.get("current_clv_status", "BLOCKED_NO_CLOSING_LINE") if clv_data else "BLOCKED_NO_CLOSING_LINE"
    )
    clv_not_ready = clv_status_raw not in ("CLV_READY_CANDIDATE",)
    promotion_frozen = bool(clv_data.get("promotion_frozen", True)) if clv_data else True

    return {
        "ceo_decision_pending": ceo_decision_pending,
        "ceo_decision_value": ceo_decision_value,
        "api_key_missing": api_key_missing,
        "post_game_proxy_only": False,  # not detectable from these files alone
        "no_closing_line": no_closing_line,
        "forward_accumulation_insufficient": forward_accumulation_insufficient,
        "clv_not_ready": clv_not_ready,
        "promotion_frozen": promotion_frozen,
        "forward_pairs": forward_pairs,
        "forward_coverage_pct": forward_coverage_pct,
        "forward_clv_status": forward_clv_status,
        "clv_status_raw": clv_status_raw,
    }


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def run_daily_monitor(
    ceo_decision_path: Path = DEFAULT_CEO_DECISION_PATH,
    api_key_flag_path: Path = DEFAULT_API_KEY_FLAG_PATH,
    forward_readiness_path: Path = DEFAULT_FORWARD_READINESS_PATH,
    clv_status_path: Path = DEFAULT_CLV_STATUS_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    paper_only: bool = True,
) -> dict:
    """Run the daily blocked-state monitor and write a JSON result.

    Returns the result dict.
    """
    state = _assess_state(
        ceo_decision_path=ceo_decision_path,
        api_key_flag_path=api_key_flag_path,
        forward_readiness_path=forward_readiness_path,
        clv_status_path=clv_status_path,
        paper_only=paper_only,
    )

    gov = BlockedStateGovernance(
        ceo_decision_pending=state["ceo_decision_pending"],
        api_key_missing=state["api_key_missing"],
        post_game_proxy_only=state["post_game_proxy_only"],
        no_closing_line=state["no_closing_line"],
        forward_accumulation_insufficient=state["forward_accumulation_insufficient"],
        clv_not_ready=state["clv_not_ready"],
        promotion_frozen=state["promotion_frozen"],
        paper_only=True,
    )

    gov_dict = gov.to_dict()

    # Derive primary blocker label
    if state["ceo_decision_pending"]:
        primary_blocker = "CEO_DECISION_PENDING"
        allowed_next_action = AllowedAction.CEO_FOLLOWUP.value
        forbidden_next_action = ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL.value
    elif state["api_key_missing"]:
        primary_blocker = "API_KEY_MISSING"
        allowed_next_action = AllowedAction.API_KEY_READINESS_CHECK.value
        forbidden_next_action = ForbiddenAction.HISTORICAL_API_CALL_WITHOUT_APPROVAL.value
    elif state["forward_accumulation_insufficient"] or state["no_closing_line"]:
        primary_blocker = "FORWARD_ACCUMULATION_INSUFFICIENT"
        allowed_next_action = AllowedAction.FORWARD_COVERAGE_READINESS_CHECK.value
        forbidden_next_action = ForbiddenAction.OPTIMIZER_PROMOTION.value
    elif state["clv_not_ready"]:
        primary_blocker = "CLV_NOT_READY"
        allowed_next_action = AllowedAction.PAPER_ONLY_MONITORING.value
        forbidden_next_action = ForbiddenAction.OPTIMIZER_PROMOTION.value
    else:
        primary_blocker = "NONE"
        allowed_next_action = AllowedAction.REPORT_ONLY.value
        forbidden_next_action = "NONE"

    result = {
        "task": "P12-D",
        "title": "Blocked-State Daily Monitor Result",
        "run_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "network_call": False,
        "crawler_modified": False,
        "ceo_decision_status": state["ceo_decision_value"],
        "api_key_ready": not state["api_key_missing"],
        "forward_pairs": state["forward_pairs"],
        "forward_pairs_target": MIN_PAIRS_FOR_CLV,
        "forward_coverage_pct": state["forward_coverage_pct"],
        "forward_clv_status": state["forward_clv_status"],
        "current_clv_status": state["clv_status_raw"],
        "is_blocked": gov_dict["is_blocked"],
        "blocked_reasons": gov_dict["blocked_reasons"],
        "primary_blocker": primary_blocker,
        "allowed_next_action": allowed_next_action,
        "forbidden_next_action": forbidden_next_action,
        "p13_allowed": gov_dict["p13_allowed"],
        "promotion_frozen": state["promotion_frozen"],
        "fixed_edge_5pct_champion_preserved": True,
        "annotation": (
            "paper_only=true。此為 P12-D 每日 blocked-state monitor 快照。"
            "不代表任何實盤獲利能力。TSL crawler 未修改。無網路呼叫。"
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_daily_monitor()
    print(f"Written: {DEFAULT_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  primary_blocker:      {result['primary_blocker']}")
    print(f"  allowed_next_action:  {result['allowed_next_action']}")
    print(f"  forbidden_next_action:{result['forbidden_next_action']}")
    print(f"  p13_allowed:          {result['p13_allowed']}")
    print(f"  is_blocked:           {result['is_blocked']}")
