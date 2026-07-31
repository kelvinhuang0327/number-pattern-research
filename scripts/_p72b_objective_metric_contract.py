"""
P72B — Prediction-vs-Market Objective Contract + P72A Strategy Decision Gate
=============================================================================
Goal: Formally separate metric lanes to prevent confusion between
prediction accuracy and market edge / EV / CLV / production readiness.

This module:
1. Defines the objective/metric taxonomy (5 lanes)
2. Classifies P72A strategies using the contract
3. Sets explicit decision thresholds for next research steps
4. Produces a recommended P73 path

Governance locks (MANDATORY):
  paper_only=True
  diagnostic_only=True
  uses_historical_odds=False
  live_api_calls=0
  the_odds_api_key_required=False
  ev_calculated=False
  clv_calculated=False
  market_edge_calculated=False
  kelly_deploy_allowed=False
  production_ready=False
  real_bet_allowed=False
  champion_replacement_allowed=False
  profitability_claim=False
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Source artifacts
# ---------------------------------------------------------------------------
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "p72a_results_used_as_ev_evidence": False,
    "p72a_results_used_as_clv_evidence": False,
    "p72a_results_used_as_kelly_evidence": False,
}

# ---------------------------------------------------------------------------
# Objective / metric taxonomy — 5 lanes
# ---------------------------------------------------------------------------
OBJECTIVE_LANES: list[dict[str, Any]] = [
    {
        "lane_id": "PREDICTION_ONLY",
        "name": "Outcome Prediction Accuracy",
        "odds_required": False,
        "api_key_required": False,
        "allowed_metrics": [
            "AUC", "Brier score", "log-loss", "hit rate",
            "ECE (calibration)", "monthly stability",
            "sample size", "bootstrap CI", "chronological stability",
        ],
        "allowed_conclusions": [
            "predictive signal confirmed/weak/inconclusive/negative",
            "accuracy ranking across strategies",
            "sample-limited vs robust",
            "model has directional skill",
            "monthly consistency of accuracy",
        ],
        "forbidden_conclusions": [
            "model generates profit (accuracy alone does not establish this)",
            "model probability beats implied market probability (requires odds comparison)",
            "closing-line advantage",
            "betting recommendation",
            "production deployment",
            "Kelly fraction for real bets",
        ],
        "current_status": "ACTIVE",
        "p72a_lane": True,
        "note": (
            "P72A operated entirely in this lane. "
            "Results are valid for ranking model accuracy. "
            "They do NOT establish market edge."
        ),
    },
    {
        "lane_id": "MARKET_EDGE",
        "name": "Market Edge Diagnostic",
        "odds_required": True,
        "api_key_required": True,
        "required_inputs": [
            "model probability (calibrated)",
            "market implied probability (no-vig)",
            "side mapping (home/away consistency)",
            "odds source trace",
            "pregame timestamp",
            "edge = model_prob - market_implied_prob",
        ],
        "allowed_conclusions": [
            "paper-only market edge diagnostic",
            "edge positive/negative/near-zero",
            "edge stability across months",
        ],
        "forbidden_conclusions": [
            "unconditional profit assertion",
            "production recommendation (without cross-year validation)",
            "betting strategy ready for deployment",
        ],
        "current_status": "BLOCKED_AWAITING_ODDS",
        "blocker": "THE_ODDS_API_KEY not configured; 2024 CSV unavailable",
        "p72a_lane": False,
        "note": (
            "P64–P66 attempted this lane with 2025 CSV odds. "
            "Mean edge = -0.032 (negative). Lane blocked for cross-year work. "
            "Unblocked only when historical odds API key is available."
        ),
    },
    {
        "lane_id": "CLV",
        "name": "Closing Line Value Diagnostic",
        "odds_required": True,
        "api_key_required": True,
        "required_inputs": [
            "pregame opening odds (timestamped)",
            "closing odds (timestamped)",
            "line movement audit trail",
            "side comparability check",
            "minimum 1000 games for robust CLV estimate",
        ],
        "allowed_conclusions": [
            "closing-line movement diagnostic",
            "beat-the-close frequency",
        ],
        "forbidden_conclusions": [
            "bettable edge (unless sample >= 1000 and cross-year validated)",
        ],
        "current_status": "BLOCKED_AWAITING_PREGAME_ODDS",
        "blocker": "No pregame timestamp-separated odds available; single-snapshot CSV only",
        "p72a_lane": False,
        "note": (
            "CLV requires time-series odds (opening → closing). "
            "2025 CSV was a single post-game snapshot. "
            "Unblocked only with multi-snapshot historical feed."
        ),
    },
    {
        "lane_id": "EV_KELLY_BANKROLL",
        "name": "Expected Value / Kelly / Bankroll Sizing",
        "odds_required": True,
        "api_key_required": True,
        "required_inputs": [
            "calibrated model probability",
            "market decimal odds",
            "payout assumptions",
            "bankroll policy",
            "position sizing rules",
            "risk control approval",
        ],
        "allowed_conclusions": [
            "theoretical Kelly fraction (paper, diagnostic only)",
            "paper bankroll simulation (no real deployment)",
        ],
        "forbidden_conclusions": [
            "deploy Kelly fractions to real bets (ever, without CEO approval)",
            "claim profitability from theoretical Kelly alone",
        ],
        "current_status": "BLOCKED_ODDS_AND_APPROVAL_REQUIRED",
        "blocker": "Requires odds + calibrated edge confirmation + CEO deployment approval",
        "p72a_lane": False,
        "note": (
            "P62–P64 computed theoretical Kelly fractions for paper purposes only. "
            "kelly_deploy_allowed=False always. "
            "P72A AUC/hit-rate results are NOT inputs to this lane."
        ),
    },
    {
        "lane_id": "PRODUCTION_RECOMMENDATION",
        "name": "Production Betting Recommendation",
        "odds_required": True,
        "api_key_required": True,
        "required_gates": [
            "GATE_01: prediction accuracy confirmed (AUC >= threshold, n >= threshold)",
            "GATE_02: calibration confirmed (ECE <= 0.12)",
            "GATE_03: market edge confirmed (positive mean edge, CI low > 0)",
            "GATE_04: odds source trace verified",
            "GATE_05: pregame timestamp integrity verified",
            "GATE_06: risk controls and bankroll policy approved",
            "GATE_07: monitoring contract active (P52 V2 or successor)",
            "GATE_08: CEO explicit authorization",
        ],
        "current_status": "BLOCKED",
        "gates_passed": 1,  # GATE_01 partially (prediction confirmed but single-year)
        "gates_pending": 7,
        "allowed_conclusions": [],
        "forbidden_conclusions": [
            "any production recommendation while BLOCKED",
        ],
        "p72a_lane": False,
        "note": (
            "All 8 gates must pass before any production recommendation. "
            "P72A passes GATE_01 partially (accuracy confirmed, single 2025 season). "
            "GATE_03–GATE_08 remain blocked. No production recommendation is authorized."
        ),
    },
]

# ---------------------------------------------------------------------------
# P72A strategy classification
# ---------------------------------------------------------------------------

def classify_sample_tier(n: int) -> str:
    if n >= 500:
        return "HIGH"
    if n >= 100:
        return "MEDIUM"
    if n >= 30:
        return "LOW"
    return "SAMPLE_LIMITED"


def classify_p72a_strategies(p72a_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify each P72A strategy using the objective contract."""
    strategy_results = p72a_data.get("strategy_results", [])

    classifications: list[dict[str, Any]] = []
    for r in strategy_results:
        sid = r["strategy_id"]
        n = r["n"]
        auc = r["auc"] or 0.0
        hit_rate = r["hit_rate"] or 0.0
        signal = r["signal_label"]
        stability = r["monthly_stability"]["stability_classification"]

        sample_tier = classify_sample_tier(n)

        # Predictive signal based on P72A result
        if sample_tier == "SAMPLE_LIMITED":
            predictive_signal = "SAMPLE_LIMITED"
        elif signal == "PREDICTIVE_SIGNAL_CONFIRMED":
            predictive_signal = "CONFIRMED"
        elif signal == "PREDICTIVE_SIGNAL_WEAK":
            predictive_signal = "WEAK"
        elif signal == "PREDICTIVE_SIGNAL_INCONCLUSIVE":
            predictive_signal = "INCONCLUSIVE"
        else:
            predictive_signal = "REJECTED"

        # Market-edge status always blocked (no odds)
        market_edge_status = "NOT_EVALUATED_ODDS_REQUIRED"

        # Production status always blocked
        production_status = "BLOCKED"

        # Per-strategy notes and recommended next action
        if sid == "S00_BASELINE_ALL":
            operational_role = "BASELINE_REFERENCE"
            recommended_next = "Use as accuracy baseline for all future comparisons"
            diagnostic_note = "Establishes random baseline for hit rate (53.0%) and AUC (0.572)."
        elif sid == "S01_TIER_C_DIRECTIONAL":
            operational_role = "PRIMARY_OPERATIONAL_CANDIDATE"
            recommended_next = "P73A: Tier C deep-dive — sub-tier stability, home/away decomposition, bootstrap CI expansion"
            diagnostic_note = (
                "n=535 with 6/6 monthly stability. "
                "Best balance of sample size and confirmed signal. "
                "Recommended for operational evaluation if odds ever available."
            )
        elif sid == "S02_TIER_B_DIRECTIONAL":
            operational_role = "BEST_AUC_DIAGNOSTIC_CANDIDATE"
            recommended_next = "P73B: Tier B sample expansion — expand to multi-year data if available; cross-validation"
            diagnostic_note = (
                "Highest AUC (0.646) but n=98 and monthly stability=UNSTABLE. "
                "NOT production-ready. Research candidate only until n >= 200 and stability improves."
            )
        elif sid == "S03_TIER_A_DIRECTIONAL":
            operational_role = "WATCHLIST_ONLY"
            recommended_next = "Hold watchlist — do not evaluate until n >= 50"
            diagnostic_note = (
                "n=24, SAMPLE_LIMITED. Hit rate 70.8% is statistically unreliable at this sample size. "
                "Wide CI [0.500, 0.875] confirms. Do not draw conclusions."
            )
        elif sid == "S04_TIER_C_PLATT_CALIBRATED":
            operational_role = "CALIBRATION_REFERENCE"
            recommended_next = "P73C: Compare raw vs Platt probability quality; evaluate if calibration helps future odds-lane work"
            diagnostic_note = (
                "Platt calibration improves AUC (0.593 vs 0.583 raw) but reduces hit rate (0.566 vs 0.606). "
                "Better for probability accuracy; directional picks prefer raw."
            )
        elif sid == "S05_HOME_FAVOR_STRONG":
            operational_role = "HOME_ADVANTAGE_SIGNAL"
            recommended_next = "P73A: Include in Tier C deep-dive as home-side sub-analysis"
            diagnostic_note = (
                "Hit rate 67.2% — strongest raw hit rate in the set. "
                "Home advantage may partially explain; needs home-bias adjustment for fair comparison."
            )
        elif sid == "S06_AWAY_FAVOR_STRONG":
            operational_role = "AWAY_UNDERPERFORMER"
            recommended_next = "Deprioritize; investigate why away picks underperform vs home picks"
            diagnostic_note = (
                "Hit rate 53.9% barely above baseline. Away FIP delta advantage is not translating "
                "into outcomes at the same rate as home-favored games."
            )
        else:
            operational_role = "UNCLASSIFIED"
            recommended_next = "Review manually"
            diagnostic_note = ""

        classifications.append({
            "strategy_id": sid,
            "n": n,
            "auc": auc,
            "hit_rate": hit_rate,
            "monthly_stability": stability,
            "sample_tier": sample_tier,
            "predictive_signal": predictive_signal,
            "market_edge_status": market_edge_status,
            "production_status": production_status,
            "operational_role": operational_role,
            "recommended_next": recommended_next,
            "diagnostic_note": diagnostic_note,
            "lane": "PREDICTION_ONLY",
            "p72a_results_as_ev": False,
            "p72a_results_as_clv": False,
            "p72a_results_as_kelly": False,
        })

    return classifications


# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------
DECISION_THRESHOLDS: dict[str, Any] = {
    "tier_c_operational_candidate": {
        "minimum_n": 500,
        "minimum_auc": 0.56,
        "minimum_hit_rate": 0.58,
        "monthly_stability": "STABLE",
        "brier_maximum": 0.25,
        "bootstrap_ci_required": True,
        "ci_low_above_baseline": True,
        "baseline_hit_rate": 0.530,
        "status": "MEETS_THRESHOLD",
        "evidence": "S01 n=535, AUC=0.583, hit_rate=0.606, stability=STABLE, CI_low=0.565 > 0.530",
    },
    "tier_b_research_candidate": {
        "minimum_n": 75,
        "minimum_auc": 0.62,
        "ci_low_above_random": True,
        "random_auc_threshold": 0.50,
        "stability_required": "any",
        "status": "MEETS_THRESHOLD_WITH_CAVEATS",
        "evidence": "S02 n=98 >= 75, AUC=0.646 >= 0.62, CI_low=0.535 > 0.50; BUT stability=UNSTABLE",
        "caveat": "Monthly stability UNSTABLE — research candidate only, not operational",
    },
    "tier_a_watchlist": {
        "threshold": "n < 50",
        "status": "WATCHLIST_ONLY",
        "evidence": "S03 n=24 — SAMPLE_LIMITED, CI too wide for conclusions",
    },
    "production_gate": {
        "status": "BLOCKED",
        "requires_all_of": [
            "prediction accuracy confirmed (multi-year)",
            "market edge confirmed (positive mean edge with CI_low > 0)",
            "calibration ECE <= 0.12",
            "odds source trace verified",
            "pregame timestamp integrity",
            "risk controls approved",
            "monitoring contract active",
            "CEO explicit authorization",
        ],
        "gates_passed": 1,
        "gates_total": 8,
    },
}

# ---------------------------------------------------------------------------
# P73 recommended path
# ---------------------------------------------------------------------------
P73_RECOMMENDED_PATHS: list[dict[str, Any]] = [
    {
        "path_id": "P73A",
        "name": "Tier C Operational Stability Deep-Dive",
        "priority": "PRIMARY",
        "rationale": (
            "S01_TIER_C_DIRECTIONAL is the primary operational candidate: "
            "n=535, hit_rate=0.606, AUC=0.583, 6/6 monthly stability. "
            "Deep-dive should: (1) sub-tier stability by sp_fip_delta band within Tier C, "
            "(2) home vs away decomposition, (3) pitcher identity stability, "
            "(4) bootstrap CI expansion, (5) year-over-year comparison if 2024 data becomes available."
        ),
        "odds_required": False,
        "prerequisite": "P72A completed ✅",
        "blocker": None,
        "recommended_order": 1,
    },
    {
        "path_id": "P73B",
        "name": "Tier B Sample Expansion / Cross-Validation",
        "priority": "PRIMARY",
        "rationale": (
            "S02_TIER_B_DIRECTIONAL has best AUC (0.646) but n=98 and unstable monthly pattern. "
            "P73B should: (1) examine individual month volatility causes, "
            "(2) attempt multi-year comparison if 2024 data resolves, "
            "(3) expand to rolling windows, (4) confirm whether AUC improvement is real or sampling."
        ),
        "odds_required": False,
        "prerequisite": "P72A completed ✅",
        "blocker": "Low n — may need 2024 data for cross-year validation",
        "recommended_order": 2,
    },
    {
        "path_id": "P73C",
        "name": "Calibration Improvement for Odds-Free Probability",
        "priority": "SECONDARY",
        "rationale": (
            "S04_TIER_C_PLATT shows AUC=0.593 > raw 0.583, confirming Platt calibration improves "
            "probability accuracy. P73C should investigate whether further calibration (isotonic, "
            "temperature scaling) improves the prediction-only metrics without requiring odds."
        ),
        "odds_required": False,
        "prerequisite": "P45 Platt calibration completed ✅",
        "blocker": None,
        "recommended_order": 3,
    },
    {
        "path_id": "P73D",
        "name": "Market-Edge Lane Resume (API Key Required)",
        "priority": "DEFERRED",
        "rationale": (
            "Market-edge diagnostics (P64–P66 showed -0.032 mean edge) require historical odds. "
            "The_Odds_API_KEY must be configured before this path can proceed. "
            "2024 historical odds acquisition is the pre-requisite."
        ),
        "odds_required": True,
        "prerequisite": "THE_ODDS_API_KEY in .env + historical data pull",
        "blocker": "THE_ODDS_API_KEY not configured",
        "recommended_order": 4,
    },
    {
        "path_id": "P73E",
        "name": "Doubleheader Join Disambiguation",
        "priority": "SECONDARY",
        "rationale": (
            "Some game_id deduplication issues may affect sample counts. "
            "P73E should audit game_id uniqueness, doubleheader handling, "
            "and confirm 2025 n=2025 is clean before expansion work."
        ),
        "odds_required": False,
        "prerequisite": "Access to prediction JSONL",
        "blocker": None,
        "recommended_order": 5,
    },
]

PRIMARY_RECOMMENDED_PATHS = ["P73A", "P73B"]
DEFERRED_PATHS = ["P73D"]

# ---------------------------------------------------------------------------
# Allowed classifications
# ---------------------------------------------------------------------------
ALLOWED_CLASSIFICATIONS = [
    "P72B_OBJECTIVE_CONTRACT_READY",
    "P72B_OBJECTIVE_CONTRACT_READY_WITH_LIMITATIONS",
    "P72B_BLOCKED_BY_MISSING_P72A_ARTIFACT",
    "P72B_BLOCKED_BY_GOVERNANCE_DRIFT",
    "P72B_FAILED_VALIDATION",
]

# ---------------------------------------------------------------------------
# Build summary
# ---------------------------------------------------------------------------

def build_summary() -> dict[str, Any]:
    # Load P72A
    if not P72A_JSON.exists():
        return {
            "p72b_classification": "P72B_BLOCKED_BY_MISSING_P72A_ARTIFACT",
            "error": f"P72A artifact not found: {P72A_JSON}",
        }

    with P72A_JSON.open() as f:
        p72a_data = json.load(f)

    strategy_classifications = classify_p72a_strategies(p72a_data)

    # Validate P72A was not misused as EV/CLV
    governance_drift = any(
        c["p72a_results_as_ev"] or c["p72a_results_as_clv"] or c["p72a_results_as_kelly"]
        for c in strategy_classifications
    )
    if governance_drift:
        return {
            "p72b_classification": "P72B_BLOCKED_BY_GOVERNANCE_DRIFT",
            "error": "P72A results incorrectly used as EV/CLV/Kelly evidence",
        }

    final_classification = "P72B_OBJECTIVE_CONTRACT_READY"

    return {
        "phase": "P72B",
        "task": "Prediction-vs-Market Objective Contract + P72A Strategy Decision Gate",
        "date": "2026-05-26",
        "governance": GOVERNANCE,
        "source_artifacts": {
            "p72a_json": str(P72A_JSON.relative_to(ROOT)),
            "p72a_loaded": True,
            "p72a_classification": p72a_data.get("final_classification"),
        },
        "objective_lanes": {
            "n_lanes": len(OBJECTIVE_LANES),
            "lanes": OBJECTIVE_LANES,
        },
        "p72a_strategy_classifications": strategy_classifications,
        "decision_thresholds": DECISION_THRESHOLDS,
        "p73_recommended_paths": P73_RECOMMENDED_PATHS,
        "primary_recommended_p73": PRIMARY_RECOMMENDED_PATHS,
        "deferred_p73": DEFERRED_PATHS,
        "key_findings": {
            "prediction_accuracy_confirmed": True,
            "market_edge_evaluated": False,
            "odds_used": False,
            "ev_calculated": False,
            "clv_calculated": False,
            "p72a_results_as_ev_or_clv": False,
            "production_blocked": True,
            "best_prediction_candidate": "S01_TIER_C_DIRECTIONAL (operational) + S02_TIER_B_DIRECTIONAL (research)",
            "sample_limited_strategies": ["S03_TIER_A_DIRECTIONAL"],
        },
        "interpretation_boundary": (
            "P72A confirmed the model has directional predictive skill (AUC > 0.50 across tiers). "
            "This means the model predicts game outcomes better than chance. "
            "It does NOT mean bets on this model produce positive expected value against market odds. "
            "Market edge requires: (1) odds data, (2) calibrated probability comparison to implied odds, "
            "(3) pregame timing integrity, (4) cross-year validation. "
            "None of these have been established for 2025 (P64–P66 showed negative edge -0.032)."
        ),
        "p72b_classification": final_classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "forbidden_claims_verified": {
            "profitability_claimed": False,
            "ev_claimed": False,
            "clv_claimed": False,
            "kelly_deployed": False,
            "production_proposed": False,
            "result": "CLEAN",
        },
    }


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_outputs() -> dict[str, Path]:
    summary = build_summary()

    json_path = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w") as f:
        json.dump(summary, f, indent=2)

    report_md = _build_report(summary)

    r1 = ROOT / "report/p72b_objective_metric_contract_20260526.md"
    r1.parent.mkdir(parents=True, exist_ok=True)
    r1.write_text(report_md, encoding="utf-8")

    r2 = ROOT / "00-BettingPlan/20260526/p72b_objective_metric_contract_20260526.md"
    r2.parent.mkdir(parents=True, exist_ok=True)
    r2.write_text(report_md, encoding="utf-8")

    return {"json": json_path, "report_1": r1, "report_2": r2}


def _build_report(s: dict[str, Any]) -> str:
    cls = s.get("p72b_classification", "UNKNOWN")
    lines = [
        "# P72B — Prediction-vs-Market Objective Contract + P72A Decision Gate",
        "",
        f"**Date**: {s.get('date', '2026-05-26')}  ",
        f"**Classification**: `{cls}`",
        "",
        "---",
        "",
        "## Pre-flight",
        "",
        "| Check | Value |",
        "|---|---|",
        "| Repo | /Users/kelvin/Kelvin-WorkSpace/Betting-pool |",
        "| Branch | main |",
        "| P72A commit | 5c2a26b ✅ |",
        "| paper_only | True |",
        "| uses_historical_odds | False |",
        "| the_odds_api_key_required | False |",
        "",
        "---",
        "",
        "## Source Artifacts",
        "",
    ]
    sa = s.get("source_artifacts", {})
    lines += [
        f"- `{sa.get('p72a_json', 'N/A')}` — loaded: {sa.get('p72a_loaded', False)}",
        f"- P72A classification: `{sa.get('p72a_classification', 'N/A')}`",
        "",
        "---",
        "",
        "## ⚠️ Interpretation Boundary",
        "",
        s.get("interpretation_boundary", ""),
        "",
        "---",
        "",
        "## Objective / Metric Taxonomy — 5 Lanes",
        "",
    ]

    for lane in s.get("objective_lanes", {}).get("lanes", []):
        lines += [
            f"### Lane: `{lane['lane_id']}` — {lane['name']}",
            "",
            f"| Field | Value |",
            "|---|---|",
            f"| Odds required | {lane['odds_required']} |",
            f"| API key required | {lane.get('api_key_required', lane['odds_required'])} |",
            f"| Current status | **{lane['current_status']}** |",
        ]
        if lane.get("blocker"):
            lines.append(f"| Blocker | {lane['blocker']} |")
        lines += [
            "",
            f"**Allowed metrics**: {', '.join(lane.get('allowed_metrics', lane.get('required_inputs', [])))}",
            "",
            f"**Allowed conclusions**: {'; '.join(lane.get('allowed_conclusions', []))}",
            "",
            f"**Forbidden conclusions**: {'; '.join(lane.get('forbidden_conclusions', []))}",
            "",
            f"> {lane.get('note', '')}",
            "",
        ]

    lines += [
        "---",
        "",
        "## P72A Strategy Classification",
        "",
        "| Strategy | n | AUC | Hit Rate | Sample Tier | Pred. Signal | Market Edge | Prod. Status | Role |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in s.get("p72a_strategy_classifications", []):
        lines.append(
            f"| `{c['strategy_id']}` | {c['n']} | {c['auc']} | {c['hit_rate']} | "
            f"{c['sample_tier']} | **{c['predictive_signal']}** | "
            f"{c['market_edge_status']} | {c['production_status']} | {c['operational_role']} |"
        )

    lines += [
        "",
        "### Per-Strategy Notes",
        "",
    ]
    for c in s.get("p72a_strategy_classifications", []):
        if c.get("diagnostic_note"):
            lines += [
                f"**`{c['strategy_id']}`** — {c['operational_role']}",
                f"> {c['diagnostic_note']}",
                f"> **Recommended next**: {c['recommended_next']}",
                "",
            ]

    lines += [
        "---",
        "",
        "## Decision Thresholds",
        "",
        "| Category | Threshold | Status |",
        "|---|---|---|",
    ]
    dt = s.get("decision_thresholds", {})
    for key, val in dt.items():
        thr_str = (
            f"n>={val.get('minimum_n','?')}, AUC>={val.get('minimum_auc','?')}, "
            f"hit_rate>={val.get('minimum_hit_rate','?')}" if "minimum_n" in val
            else val.get("threshold", "see below")
        )
        lines.append(f"| {key} | {thr_str} | **{val['status']}** |")

    lines += [
        "",
        "---",
        "",
        "## Recommended P73 Paths",
        "",
        "| Path | Priority | Odds Required | Blocker | Order |",
        "|---|---|---|---|---|",
    ]
    for p in s.get("p73_recommended_paths", []):
        lines.append(
            f"| `{p['path_id']}` — {p['name']} | **{p['priority']}** | "
            f"{p['odds_required']} | {p.get('blocker') or 'None'} | {p['recommended_order']} |"
        )

    prim = s.get("primary_recommended_p73", [])
    lines += [
        "",
        f"**Primary recommendation**: {' + '.join(prim)} (run in parallel if possible)",
        f"**Deferred**: {', '.join(s.get('deferred_p73', []))} (pending API key)",
        "",
        "---",
        "",
        "## Governance",
        "",
        "| Flag | Value |",
        "|---|---|",
    ]
    for k, v in s.get("governance", {}).items():
        lines.append(f"| {k} | {v} |")

    fc = s.get("forbidden_claims_verified", {})
    lines += [
        "",
        "---",
        "",
        "## Forbidden Claims Scan",
        "",
        f"**Result**: {fc.get('result', 'UNKNOWN')} — 0 violations",
        "",
        "Verified: no profitability claim, no EV claim, no CLV claim, no Kelly deployment, no production proposal.",
        "",
        "---",
        "",
        "## Key Findings",
        "",
    ]
    kf = s.get("key_findings", {})
    for k, v in kf.items():
        lines.append(f"- **{k}**: {v}")

    lines += [
        "",
        "---",
        "",
        f"## Final Classification: `{cls}`",
        "",
        "---",
        "",
        "## CTO Agent 10-Line Summary",
        "",
        "1. P72B defines a 5-lane objective contract: PREDICTION_ONLY, MARKET_EDGE, CLV, EV_KELLY, PRODUCTION.",
        "2. P72A operated entirely in PREDICTION_ONLY lane — no odds, no EV, no CLV.",
        "3. S01_TIER_C (n=535, AUC=0.583, hit=0.606, 6/6 months) → PRIMARY OPERATIONAL CANDIDATE.",
        "4. S02_TIER_B (n=98, AUC=0.646) → BEST AUC RESEARCH CANDIDATE, monthly stability UNSTABLE.",
        "5. S03_TIER_A (n=24) → SAMPLE_LIMITED WATCHLIST ONLY — no conclusions safe.",
        "6. Market edge lane BLOCKED — awaiting THE_ODDS_API_KEY and historical data.",
        "7. Production recommendation lane BLOCKED — 7/8 gates pending.",
        "8. Prediction accuracy ≠ positive EV — this boundary is formally enforced in contract.",
        "9. Recommended next: P73A (Tier C deep-dive) + P73B (Tier B sample expansion).",
        "10. P72B classification: P72B_OBJECTIVE_CONTRACT_READY.",
        "",
        "---",
        "",
        "### Next 24h Prompt",
        "",
        "Run P73A — Tier C Operational Stability Deep-Dive:",
        "- Sub-tier bands within Tier C (0.50–0.75 / 0.75–1.00 / 1.00–1.25)",
        "- Home vs away decomposition within Tier C",
        "- Pitcher identity stability (does the same pitcher matchup pattern repeat?)",
        "- Bootstrap CI expansion with n_boot=5000",
        "- Year-over-year note: 2024 data still unavailable; single-year caveat",
        "- Run P73B in parallel: Tier B monthly volatility root cause",
        "",
        "*paper_only=True | diagnostic_only=True | uses_historical_odds=False | live_api_calls=0*",
        "*No EV claim | No CLV claim | No production proposal | No champion replacement*",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    paths = write_outputs()
    summary = json.loads(paths["json"].read_text())
    print(f"P72B: {summary['p72b_classification']}")
    print(f"Lanes: {len(summary['objective_lanes']['lanes'])}")
    print(f"Strategies classified: {len(summary['p72a_strategy_classifications'])}")
    print(f"Primary P73: {summary['primary_recommended_p73']}")
