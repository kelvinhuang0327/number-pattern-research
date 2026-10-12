"""P11-E CLV / Promotion Freeze Refresh runner."""
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

base = Path(__file__).parent.parent

# --- Read P10 CLV gate status ---
p10_clv_path = base / "data/paper_recommendations/p10_clv_gate_status_refresh_20260526.json"
p10_clv = json.loads(p10_clv_path.read_text()) if p10_clv_path.exists() else {}

# --- Read P11 CEO follow-up ---
p11_ceo_path = base / "data/paper_recommendations/p11_ceo_decision_followup_20260527.json"
p11_ceo = json.loads(p11_ceo_path.read_text()) if p11_ceo_path.exists() else {}

# --- Read P11-D forward monitor ---
p11_fwd_path = base / "data/paper_recommendations/p11_forward_collection_readiness_20260527.json"
p11_fwd = json.loads(p11_fwd_path.read_text()) if p11_fwd_path.exists() else {}

# Current actual state
current_pairs = p11_fwd.get("pair_count", 0)
current_coverage_pct = p11_fwd.get("pair_coverage_pct", 0.0)
fwd_status = p11_fwd.get("clv_readiness_status", "ACCUMULATION_INSUFFICIENT")

# CLV projection with current state
inp = CLVReadinessInput(
    path=BackfillPath.FORWARD_COLLECTION,
    paper_only=True,
    forward_has_closing_line=False,
    forward_current_pair_coverage_pct=current_coverage_pct,
    forward_projected_pair_coverage_pct=0.0,
    forward_current_pairs=current_pairs,
    forward_projected_pairs=0,
)
proj = project_clv_readiness(inp)

# Determine blocker and owner
if fwd_status == "CLV_READY_CANDIDATE":
    clv_status = "CLV_READY_CANDIDATE"
    blocker = "NONE"
    next_owner = "ENGINEER_PROMOTE_TO_CLV_VALIDATION"
    promotion_frozen = False
elif fwd_status == "BLOCKED_LOW_COVERAGE":
    clv_status = "BLOCKED_LOW_COVERAGE"
    blocker = f"Forward pairs {current_pairs} below 200 or coverage {current_coverage_pct}% below 90%"
    next_owner = "TSL_COLLECTION_CONTINUE"
    promotion_frozen = True
else:
    clv_status = proj.status.value
    blocker = (
        "CEO has not approved PATH A. "
        f"PATH B: {current_pairs}/200 pairs ({fwd_status}). "
        "No pregame+closing pairs available."
    )
    next_owner = "CEO_DECISION_PENDING"
    promotion_frozen = True

output = {
    "task": "P11-E",
    "title": "CLV / Promotion Freeze Refresh",
    "run_date": datetime.now(timezone.utc).isoformat(),
    "paper_only": True,
    "live_api_called": False,
    "production_write": False,
    "sources": {
        "p10_clv_status": p10_clv.get("current_clv_status"),
        "p11_ceo_classification": p11_ceo.get("current_classification"),
        "p11_forward_readiness_status": fwd_status,
    },
    "ceo_decision_status": "DEFER_DECISION",
    "path_a_status": "BLOCKED_NEEDS_CEO_APPROVAL_AND_API_KEY",
    "path_b_accumulation_status": fwd_status,
    "current_clv_status": clv_status,
    "forward_current_pairs": current_pairs,
    "forward_target_pairs": 200,
    "forward_pair_coverage_pct": current_coverage_pct,
    "blocker": blocker,
    "next_owner": next_owner,
    "fixed_edge_5pct_champion_preserved": True,
    "promotion_frozen": promotion_frozen,
    "clv_gate_passed": clv_status == "CLV_READY_CANDIDATE",
    "p12_unblock_conditions": {
        "PATH_A": "CEO approves + API key + ALLOW_SAMPLE_API_CALL=true → P11-C sample gate → 1800 pairs backfill",
        "PATH_B": "TSL forward collection reaches 200 pairs @ 90% coverage",
    },
    "annotation": (
        "paper_only=true。此為 P11-E CLV / 策略推廣凍結狀態更新。"
        "CLV 驗證凍結直到 PATH A 或 PATH B 達標。"
        "fixed_edge_5pct 為當前 champion。不代表任何實盤獲利能力。"
    ),
}

out_path = base / "data/paper_recommendations/p11_system_status_refresh_20260527.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Written: {out_path.relative_to(base)}")
print(f"  ceo_decision_status:  {output['ceo_decision_status']}")
print(f"  current_clv_status:   {output['current_clv_status']}")
print(f"  path_b_status:        {output['path_b_accumulation_status']}")
print(f"  promotion_frozen:     {output['promotion_frozen']}")
print(f"  champion_preserved:   {output['fixed_edge_5pct_champion_preserved']}")
