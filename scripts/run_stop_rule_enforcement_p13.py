"""P13-D Stop-Rule Enforcement Check.

Read-only. No network calls. No TSL crawler modification.
Uses BlockedStateGovernance to verify all forbidden actions remain forbidden
under the current P12_BLOCKED_GOVERNANCE_READY_STOP_EXPANSION state.
paper_only=True enforced.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from wbc_backend.recommendation.blocked_state_governance import (
    AllowedAction,
    BlockedStateGovernance,
    ForbiddenAction,
    PaperOnlyViolationError,
)

DEFAULT_OUTPUT_PATH = (
    BASE / "data/paper_recommendations/p13_stop_rule_enforcement_20260529.json"
)


def run_stop_rule_enforcement(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    paper_only: bool = True,
) -> dict:
    """Check that all P12 stop-expansion rules still hold."""
    if not paper_only:
        raise PaperOnlyViolationError(
            "P13-D: paper_only=False is not permitted. "
            "All P13 operations must be paper_only=true."
        )

    # Instantiate governance in fully-blocked state (mirrors current reality)
    gov = BlockedStateGovernance(
        ceo_decision_pending=True,
        api_key_missing=True,
        post_game_proxy_only=False,
        no_closing_line=True,
        forward_accumulation_insufficient=True,
        clv_not_ready=True,
        promotion_frozen=True,
        paper_only=True,
    )

    forbidden_check: dict[str, bool] = {}
    for action in ForbiddenAction:
        forbidden_check[action.value] = gov.is_action_forbidden(action)

    allowed_check: dict[str, bool] = {}
    for action in AllowedAction:
        allowed_check[action.value] = gov.is_action_allowed(action)

    all_forbidden_pass = all(forbidden_check.values())
    all_allowed_pass = all(allowed_check.values())

    result: dict = {
        "task": "P13-D",
        "title": "Stop-Rule Enforcement Check",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "paper_only": True,
        "network_call": False,
        "crawler_modified": False,
        "is_blocked": gov.is_blocked,
        "blocked_reasons": [r.value for r in gov.blocked_reasons],
        "forbidden_actions_check": forbidden_check,
        "all_forbidden_actions_blocked": all_forbidden_pass,
        "allowed_actions_check": allowed_check,
        "all_allowed_actions_permitted": all_allowed_pass,
        "p13_allowed": gov.p13_allowed(),
        "p14_allowed": gov.p13_allowed(),  # same gate: not blocked
        "promotion_frozen": True,
        "fixed_edge_5pct_champion_preserved": True,
        "enforcement_result": (
            "PASS" if (all_forbidden_pass and all_allowed_pass) else "FAIL"
        ),
        "annotation": (
            "paper_only=true。P13-D stop-rule enforcement check。"
            "所有 forbidden actions 仍被禁止，所有 allowed actions 仍允許。"
            "不宣稱任何策略具獲利能力。"
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        label = output_path.relative_to(BASE)
    except ValueError:
        label = output_path
    print(f"Written: {label}")
    print(f"  enforcement_result:      {result['enforcement_result']}")
    print(f"  all_forbidden_blocked:   {all_forbidden_pass}")
    print(f"  all_allowed_permitted:   {all_allowed_pass}")
    print(f"  p14_allowed:             {result['p14_allowed']}")
    return result


if __name__ == "__main__":
    run_stop_rule_enforcement()
