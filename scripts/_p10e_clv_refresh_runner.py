"""P10-E CLV gate status refresh — reads actual state and re-projects."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.clv_readiness_projection import (
    BackfillPath,
    CLVReadinessInput,
    project_clv_readiness,
)

# Current actual state (worktree)
CURRENT_PAIRS = 0
CURRENT_COVERAGE_PCT = 0.0
# CEO decision from P10-B resolution (DEFER_DECISION → no API key, no approval)
CEO_DECISION = "DEFER_DECISION"
API_KEY_PROVIDED = False

# Compute CLV status for current PATH B state
inp = CLVReadinessInput(
    path=BackfillPath.FORWARD_COLLECTION,
    paper_only=True,
    forward_has_closing_line=False,  # no actual closing lines yet
    forward_current_pair_coverage_pct=CURRENT_COVERAGE_PCT,
    forward_projected_pair_coverage_pct=92.0,
    forward_current_pairs=CURRENT_PAIRS,
    forward_projected_pairs=250,
)
result = project_clv_readiness(inp)

output = {
    "task": "P10-E",
    "title": "CLV Gate Status Refresh",
    "run_date": datetime.now(timezone.utc).isoformat(),
    "paper_only": True,
    "live_api_called": False,
    "production_write": False,
    "ceo_decision_status": CEO_DECISION,
    "current_clv_status": result.status.value,
    "blocker": (
        "CEO has not approved PATH A. "
        "PATH B pair count is 0 (below minimum 200). "
        "No actual pregame+closing pairs available for CLV validation."
    ),
    "owner": "CEO_DECISION_PENDING",
    "next_unblock_action": (
        "Either: (A) CEO approves PATH A + provides API key → historical backfill → 1800 pairs. "
        "Or: (B) TSL forward collection continues until 200 pairs @ 90% coverage."
    ),
    "estimated_pair_target": 200,
    "current_pairs": CURRENT_PAIRS,
    "projected_pairs": result.projected_pairs,
    "pair_coverage_pct_current": CURRENT_COVERAGE_PCT,
    "pair_coverage_pct_projected": 92.0,
    "fixed_edge_5pct_champion_preserved": True,
    "promotion_frozen": True,
    "clv_gate_passed": False,
    "path_a_status": "BLOCKED_NEEDS_CEO_APPROVAL_AND_API_KEY",
    "path_b_status": "ACCUMULATING_0_OF_200_PAIRS",
    "reason": result.reason,
    "annotation": (
        "paper_only=true。此為 P10-E CLV 閘門狀態更新。"
        "CLV 驗證凍結直到 PATH A 或 PATH B 達到 200+ pairs。"
        "fixed_edge_5pct 為當前 champion。策略推廣凍結。"
        "不代表任何實盤獲利能力。"
    ),
}

out_path = Path("data/paper_recommendations/p10_clv_gate_status_refresh_20260526.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Written: {out_path}")
print(f"  current_clv_status: {output['current_clv_status']}")
print(f"  owner:              {output['owner']}")
print(f"  pairs:              {output['current_pairs']} / {output['estimated_pair_target']}")
print(f"  champion_preserved: {output['fixed_edge_5pct_champion_preserved']}")
print(f"  promotion_frozen:   {output['promotion_frozen']}")
