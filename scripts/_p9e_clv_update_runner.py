"""P9-E CLV readiness projection update — 3 scenarios."""
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

scenarios = []

# ── Scenario 1: CEO approved + key present → HISTORICAL_BACKFILL_READY ───────
inp1 = CLVReadinessInput(
    path=BackfillPath.HISTORICAL_API,
    paper_only=True,
    historical_api_key_provided=True,
    historical_projected_pairs=1800,
    historical_all_post_game_proxy=False,
    historical_has_closing_line=True,
)
r1 = project_clv_readiness(inp1)
scenarios.append({
    "scenario": "PATH_A_ceo_approved_key_present",
    "status": r1.status.value,
    "projected_pairs": r1.projected_pairs,
    "pair_coverage_pct": r1.pair_coverage_pct,
    "api_key_required": r1.api_key_required,
    "ceo_action_required": r1.ceo_action_required,
    "next_action_owner": "CTO_EXECUTE",
    "reason": r1.reason,
    "annotation": r1.annotation,
})

# ── Scenario 2: CEO approved + key missing → BLOCKED_NEEDS_API_KEY ───────────
inp2 = CLVReadinessInput(
    path=BackfillPath.HISTORICAL_API,
    paper_only=True,
    historical_api_key_provided=False,
    historical_projected_pairs=1800,
    historical_all_post_game_proxy=False,
    historical_has_closing_line=True,
)
r2 = project_clv_readiness(inp2)
scenarios.append({
    "scenario": "PATH_A_ceo_approved_key_missing",
    "status": r2.status.value,
    "projected_pairs": r2.projected_pairs,
    "pair_coverage_pct": r2.pair_coverage_pct,
    "api_key_required": r2.api_key_required,
    "ceo_action_required": r2.ceo_action_required,
    "next_action_owner": "CEO_PURCHASE_KEY",
    "reason": r2.reason,
    "annotation": r2.annotation,
})

# ── Scenario 3: Forward-only → FORWARD_COLLECTION_ACCUMULATING ───────────────
inp3 = CLVReadinessInput(
    path=BackfillPath.FORWARD_COLLECTION,
    paper_only=True,
    forward_has_closing_line=True,
    forward_current_pair_coverage_pct=85.0,
    forward_projected_pair_coverage_pct=92.0,
    forward_current_pairs=180,
    forward_projected_pairs=250,
)
r3 = project_clv_readiness(inp3)
scenarios.append({
    "scenario": "PATH_B_forward_only_accumulating",
    "status": r3.status.value,
    "projected_pairs": r3.projected_pairs,
    "pair_coverage_pct": r3.pair_coverage_pct,
    "api_key_required": r3.api_key_required,
    "ceo_action_required": r3.ceo_action_required,
    "next_action_owner": "TSL_ACCUMULATION",
    "reason": r3.reason,
    "annotation": r3.annotation,
})

output = {
    "task": "P9-E",
    "title": "CLV Readiness Projection Update",
    "run_date": datetime.now(timezone.utc).isoformat(),
    "paper_only": True,
    "live_api_called": False,
    "production_write": False,
    "current_ceo_decision": "DEFER_DECISION",
    "current_classification": "P9_CEO_DECISION_PENDING",
    "clv_gate_status": "BLOCKED",
    "clv_blocked_reason": (
        "CEO has not approved PATH A, and PATH B pair count (0) is below "
        "minimum threshold (200). CLV validation frozen until either PATH A "
        "or PATH B reaches 200+ pregame/closing pairs."
    ),
    "scenarios": scenarios,
    "summary": {
        "PATH_A_ready_when": "CEO approves + API key purchased + CTO executes backfill",
        "PATH_B_ready_when": "TSL forward collection reaches 200 pairs at 90%+ coverage",
        "fixed_edge_5pct_champion": True,
        "optimizer_promotion_frozen": True,
        "clv_gate_passed": False,
    },
    "p10_recommendation": (
        "CEO returns decision → P10 executes approved path. "
        "If PATH A: purchase API key, run backfill gate, validate 1800 pairs. "
        "If PATH B: continue daily forward collection until 200 pairs @ 90% coverage."
    ),
    "annotation": (
        "paper_only=true。此為 P9-E CLV 就緒度更新。不代表任何實盤獲利能力。"
        "策略推廣凍結。fixed_edge_5pct 為當前 champion。"
    ),
}

out_path = Path("data/paper_recommendations/p9_clv_readiness_projection_update_20260525.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Written: {out_path}")
for s in scenarios:
    print(f"  {s['scenario']}: {s['status']} | pairs={s['projected_pairs']} | owner={s['next_action_owner']}")
