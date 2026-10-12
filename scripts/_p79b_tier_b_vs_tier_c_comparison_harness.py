"""
scripts/_p79b_tier_b_vs_tier_c_comparison_harness.py

P79B — Tier B vs Tier C Comparison Harness Fixture Dry-Run

Governance: paper_only=True | diagnostic_only=True | production_ready=False
NO_REAL_BET=True | live_api_calls=0 | ev_calculated=False
clv_calculated=False | kelly_calculated=False

This is a fixture dry-run using 2025 data. It does NOT constitute a 2026
live performance claim and does NOT change champion strategy.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

GOVERNANCE: dict = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "odds_used": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "promotion_freeze": True,
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_ID = "tier_b_snapshot_2025_202507"
CUTOFF_MONTH = "2025-07"
SNAPSHOT_MONTHS = ["2025-04", "2025-05", "2025-06", "2025-07"]
TIER_B_TRIGGER_N = 200
TIER_B_LOW_ABS_DELTA = 0.25
TIER_B_HIGH_ABS_DELTA = 0.50
PRIMARY_HOME_ABS_DELTA = 0.50
PRIMARY_AWAY_ABS_DELTA = 1.25
SHADOW_AWAY_ABS_DELTA = 1.00
BASELINE_ABS_DELTA = 0.50

COMPARISON_SCHEMA_SECTIONS = [
    "metadata",
    "governance",
    "source_snapshot",
    "candidate_rule_metrics",
    "head_to_head_comparison",
    "operational_research_gate",
    "stability_diagnostics",
    "calibration_diagnostics",
    "decision_summary",
    "next_phase_recommendation",
]

CANDIDATE_KEYS = ["tier_b", "primary_125", "shadow_100", "baseline_50"]

# Tolerance for snapshot reconstruction counts vs P79A reference
SNAPSHOT_COUNT_TOLERANCE = 5

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PATHS: dict = {
    "p79a_summary": ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json",
    "p79a_report": ROOT / "report/p79a_tier_b_trigger_readiness_contract_20260526.md",
    "p79a_script": ROOT / "scripts/_p79a_tier_b_trigger_readiness_contract.py",
    "p78_summary": ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_summary": ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_summary": ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_summary": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_summary": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_summary": ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_summary": ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_summary": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_summary": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "predictions_jsonl": ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    # outputs
    "output_json": ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "output_report": ROOT / "report/p79b_tier_b_vs_tier_c_comparison_harness_20260526.md",
    "output_betting_plan": ROOT / "00-BettingPlan/20260526/p79b_tier_b_vs_tier_c_comparison_harness_20260526.md",
}

SOURCE_ARTIFACT_KEYS = [
    "p79a_summary", "p79a_report", "p79a_script",
    "p78_summary", "p77_summary", "p76_summary",
    "p75b_summary", "p75a_summary", "p74_summary",
    "p73_summary", "p72b_summary", "p72a_summary",
    "predictions_jsonl",
]

# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _wilson_ci(n: int, hits: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _compute_auc(scores: list[float], labels: list[int]) -> Optional[float]:
    """AUC via Mann-Whitney U statistic."""
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    u = sum(
        1.0 if p > n else 0.5 if p == n else 0.0
        for p in pos
        for n in neg
    )
    return u / (len(pos) * len(neg))


def _auc_ci(auc: float, n_pos: int, n_neg: int, z: float = 1.96) -> tuple[float, float]:
    """AUC confidence interval via Hanley-McNeil formula."""
    if n_pos == 0 or n_neg == 0:
        return (0.0, 1.0)
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    var = (
        auc * (1 - auc)
        + (n_pos - 1) * (q1 - auc**2)
        + (n_neg - 1) * (q2 - auc**2)
    ) / (n_pos * n_neg)
    se = max(0.0, var) ** 0.5
    return (max(0.0, auc - z * se), min(1.0, auc + z * se))


def _compute_brier(probs: list[float], labels: list[int]) -> Optional[float]:
    """Mean squared error between predicted probability and outcome."""
    if not probs:
        return None
    return sum((p - l) ** 2 for p, l in zip(probs, labels)) / len(probs)


def _compute_log_loss(probs: list[float], labels: list[int]) -> Optional[float]:
    """Binary cross-entropy log-loss."""
    if not probs:
        return None
    eps = 1e-12
    return -sum(
        l * math.log(max(eps, p)) + (1 - l) * math.log(max(eps, 1 - p))
        for p, l in zip(probs, labels)
    ) / len(probs)


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> Optional[float]:
    """Expected Calibration Error (uniform binning)."""
    if not probs:
        return None
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, l in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, l))
    ece = 0.0
    n_total = len(probs)
    for b in bins:
        if b:
            avg_conf = sum(x[0] for x in b) / len(b)
            avg_acc = sum(x[1] for x in b) / len(b)
            ece += abs(avg_conf - avg_acc) * len(b) / n_total
    return ece

# ---------------------------------------------------------------------------
# Row classification helpers
# ---------------------------------------------------------------------------

def _get_abs_fip(row: dict) -> Optional[float]:
    p0 = row.get("p0_features", {})
    if not p0.get("sp_fip_delta_available", False):
        return None
    fip = p0.get("sp_fip_delta")
    if fip is None:
        return None
    return abs(fip)


def _is_tier_b_row(row: dict) -> bool:
    abs_fip = _get_abs_fip(row)
    if abs_fip is None:
        return False
    return TIER_B_LOW_ABS_DELTA <= abs_fip < TIER_B_HIGH_ABS_DELTA


def _is_primary_row(row: dict) -> bool:
    abs_fip = _get_abs_fip(row)
    if abs_fip is None:
        return False
    home_pick = row.get("model_home_prob", 0.5) > 0.5
    if home_pick:
        return abs_fip >= PRIMARY_HOME_ABS_DELTA
    return abs_fip >= PRIMARY_AWAY_ABS_DELTA


def _is_shadow_row(row: dict) -> bool:
    abs_fip = _get_abs_fip(row)
    if abs_fip is None:
        return False
    home_pick = row.get("model_home_prob", 0.5) > 0.5
    if home_pick:
        return abs_fip >= PRIMARY_HOME_ABS_DELTA
    return abs_fip >= SHADOW_AWAY_ABS_DELTA


def _is_baseline_row(row: dict) -> bool:
    abs_fip = _get_abs_fip(row)
    if abs_fip is None:
        return False
    return abs_fip >= BASELINE_ABS_DELTA


def _get_is_correct(row: dict) -> Optional[int]:
    """Return 1 if model pick is correct, 0 if wrong, None if unknown."""
    home_win = row.get("home_win")
    if home_win is None:
        return None
    home_pick = row.get("model_home_prob", 0.5) > 0.5
    if home_pick:
        return 1 if home_win == 1 else 0
    else:
        return 1 if home_win == 0 else 0


def _get_pick_prob(row: dict) -> float:
    """Return model's probability for its own pick (confidence)."""
    home_prob = row.get("model_home_prob", 0.5)
    if home_prob > 0.5:
        return float(home_prob)
    return float(1.0 - home_prob)

# ---------------------------------------------------------------------------
# Stability classification
# ---------------------------------------------------------------------------

def _classify_stability(
    monthly_hit_rates: list[float],
    monthly_ns: list[int],
) -> str:
    """Classify monthly hit_rate stability as STRONG/MODERATE/WEAK/INSUFFICIENT."""
    eligible = [(hr, n) for hr, n in zip(monthly_hit_rates, monthly_ns) if n >= 5]
    if len(eligible) < 3:
        return "INSUFFICIENT"

    hit_rates = [hr for hr, _ in eligible]
    red_months = sum(1 for hr, n in eligible if hr < 0.48 or n < 10)

    all_strong = all(hr >= 0.55 for hr in hit_rates) and red_months == 0
    if all_strong:
        return "STRONG"
    most_moderate = sum(1 for hr in hit_rates if hr >= 0.52) >= len(hit_rates) * 0.6
    if most_moderate and red_months <= 1:
        return "MODERATE"
    if red_months >= 2 or sum(1 for hr in hit_rates if hr < 0.52) > len(hit_rates) // 2:
        return "WEAK"
    return "MODERATE"  # borderline → err conservative


def _concentration_risk(n_home: int, n_away: int) -> str:
    """Classify concentration risk by home/away split."""
    total = n_home + n_away
    if total == 0:
        return "UNKNOWN"
    pct = max(n_home, n_away) / total
    if pct > 0.90:
        return "SEVERE"
    elif pct > 0.70:
        return "MODERATE"
    return "LOW"

# ---------------------------------------------------------------------------
# Core metric computation for a candidate
# ---------------------------------------------------------------------------

def _compute_metrics(
    candidate_rows: list[dict],
    total_snapshot_n: int,
    candidate_key: str,
) -> dict:
    """Compute all required metrics for a single candidate."""
    if not candidate_rows:
        return {
            "candidate_key": candidate_key,
            "n": 0,
            "coverage": 0.0,
            "hit_rate": None,
            "insufficient": True,
        }

    # Extract data
    correct_flags: list[int] = []
    probs: list[float] = []
    dates: list[str] = []
    pick_sides: list[str] = []

    for row in candidate_rows:
        c = _get_is_correct(row)
        if c is None:
            continue
        correct_flags.append(c)
        probs.append(_get_pick_prob(row))
        dates.append(row.get("game_date", ""))
        pick_sides.append("home" if row.get("model_home_prob", 0.5) > 0.5 else "away")

    n_valid = len(correct_flags)
    hits = sum(correct_flags)

    if n_valid == 0:
        return {
            "candidate_key": candidate_key,
            "n": 0,
            "coverage": 0.0,
            "hit_rate": None,
            "insufficient": True,
        }

    # Basic metrics
    hit_rate = hits / n_valid
    ci_low, ci_high = _wilson_ci(n_valid, hits)
    auc = _compute_auc(probs, correct_flags)
    auc_ci_low, auc_ci_high = (None, None)
    if auc is not None:
        n_pos = hits
        n_neg = n_valid - hits
        auc_ci_low, auc_ci_high = _auc_ci(auc, n_pos, n_neg)
    brier = _compute_brier(probs, correct_flags)
    ll = _compute_log_loss(probs, correct_flags)
    ece = _compute_ece(probs, correct_flags)

    # Monthly stability
    monthly_results: dict[str, dict] = {}
    for month in SNAPSHOT_MONTHS:
        m_pairs = [
            (c, p)
            for c, p, d in zip(correct_flags, probs, dates)
            if len(d) >= 7 and d[:7] == month
        ]
        if m_pairs:
            m_n = len(m_pairs)
            m_hits = sum(c for c, _ in m_pairs)
            m_hr = m_hits / m_n
            m_ci = _wilson_ci(m_n, m_hits)
            monthly_results[month] = {
                "n": m_n,
                "hits": m_hits,
                "hit_rate": round(m_hr, 4),
                "ci_lower": round(m_ci[0], 4),
                "ci_upper": round(m_ci[1], 4),
            }
        else:
            monthly_results[month] = {"n": 0, "hits": 0, "hit_rate": None}

    monthly_hit_rates = [
        v["hit_rate"]
        for v in monthly_results.values()
        if v["hit_rate"] is not None
    ]
    monthly_ns = [v["n"] for v in monthly_results.values() if v["n"] > 0]
    stability = _classify_stability(monthly_hit_rates, monthly_ns)

    # Chronological thirds (if n >= 30)
    chrono_thirds: Optional[list[dict]] = None
    if n_valid >= 30:
        sorted_idx = sorted(range(n_valid), key=lambda i: dates[i])
        t = n_valid // 3
        slices = [sorted_idx[:t], sorted_idx[t : 2 * t], sorted_idx[2 * t :]]
        chrono_thirds = []
        for sl in slices:
            sl_n = len(sl)
            sl_hits = sum(correct_flags[i] for i in sl)
            chrono_thirds.append({
                "n": sl_n,
                "hit_rate": round(sl_hits / sl_n, 4) if sl_n > 0 else None,
            })

    # Rolling 100 (if n >= 100)
    rolling_100: Optional[float] = None
    if n_valid >= 100:
        sorted_idx = sorted(range(n_valid), key=lambda i: dates[i])
        last_100 = sorted_idx[-100:]
        r100_hits = sum(correct_flags[i] for i in last_100)
        rolling_100 = round(r100_hits / 100, 4)

    # Home/away split
    n_home = sum(1 for s in pick_sides if s == "home")
    n_away = n_valid - n_home
    home_hits = sum(c for c, s in zip(correct_flags, pick_sides) if s == "home")
    away_hits = sum(c for c, s in zip(correct_flags, pick_sides) if s == "away")
    home_hit_rate = round(home_hits / n_home, 4) if n_home > 0 else None
    away_hit_rate = round(away_hits / n_away, 4) if n_away > 0 else None
    concentration = _concentration_risk(n_home, n_away)

    return {
        "candidate_key": candidate_key,
        "n": n_valid,
        "coverage": round(n_valid / total_snapshot_n, 4) if total_snapshot_n > 0 else 0.0,
        "hits": hits,
        "hit_rate": round(hit_rate, 4),
        "hit_rate_ci_lower": round(ci_low, 4),
        "hit_rate_ci_upper": round(ci_high, 4),
        "auc": round(auc, 4) if auc is not None else None,
        "auc_ci_lower": round(auc_ci_low, 4) if auc_ci_low is not None else None,
        "auc_ci_upper": round(auc_ci_high, 4) if auc_ci_high is not None else None,
        "brier": round(brier, 4) if brier is not None else None,
        "log_loss": round(ll, 4) if ll is not None else None,
        "ece": round(ece, 4) if ece is not None else None,
        "monthly_stability": stability,
        "monthly_results": monthly_results,
        "rolling_100_hit_rate": rolling_100,
        "chronological_thirds": chrono_thirds,
        "n_home": n_home,
        "n_away": n_away,
        "home_hit_rate": home_hit_rate,
        "away_hit_rate": away_hit_rate,
        "concentration_risk": concentration,
        "insufficient": False,
    }

# ---------------------------------------------------------------------------
# Step 1 — Verify P79A trigger readiness
# ---------------------------------------------------------------------------

def step1_verify_p79a() -> dict:
    """Load P79A summary and confirm trigger readiness."""
    path = PATHS["p79a_summary"]
    if not path.exists():
        return {"verified": False, "error": f"Missing: {path}"}

    with open(path, encoding="utf-8") as fh:
        p79a = json.load(fh)

    errors: list[str] = []

    cls = p79a.get("p79a_classification", "")
    if cls != "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY":
        errors.append(f"classification mismatch: {cls!r}")

    s6 = p79a.get("step6_fixture_validation", {})
    if not s6.get("trigger_fires"):
        errors.append("trigger_fires is not True")

    frozen = s6.get("frozen_package") or {}
    sid = frozen.get("snapshot_id", "")
    if sid != SNAPSHOT_ID:
        errors.append(f"snapshot_id mismatch: {sid!r} != {SNAPSHOT_ID!r}")

    trigger_n = s6.get("trigger_n", 0) or 0
    if trigger_n < TIER_B_TRIGGER_N:
        errors.append(f"trigger_n={trigger_n} < {TIER_B_TRIGGER_N}")

    if not p79a.get("step4_comparison_contract"):
        errors.append("comparison_contract missing from P79A")

    gov = p79a.get("governance_snapshot", {})
    if gov.get("production_ready") is not False:
        errors.append("production_ready must be False")
    if gov.get("ev_calculated") is not False:
        errors.append("ev_calculated must be False")

    market_edge = p79a.get("market_edge_lane", "")
    if market_edge != "blocked":
        errors.append(f"market_edge_lane: {market_edge!r} != 'blocked'")

    scan = p79a.get("step7_forbidden_scan", {})
    if not scan.get("scan_passed"):
        errors.append("P79A forbidden scan did not pass")

    return {
        "verified": len(errors) == 0,
        "errors": errors,
        "classification": cls,
        "snapshot_id": sid,
        "trigger_n": trigger_n,
        "trigger_month": s6.get("trigger_month"),
        "comparison_contract_present": bool(p79a.get("step4_comparison_contract")),
        "market_edge_lane": market_edge,
        "governance_clean": len([e for e in errors if "governance" in e.lower()]) == 0,
        "primary_rule_snapshot_n": frozen.get("primary_rule_snapshot_n"),
        "shadow_rule_snapshot_n": frozen.get("shadow_rule_snapshot_n"),
    }

# ---------------------------------------------------------------------------
# Step 2 — Comparison harness schema
# ---------------------------------------------------------------------------

def step2_comparison_schema() -> dict:
    """Define the comparison harness schema structure."""
    return {
        "schema_name": "P79B_TIER_B_VS_TIER_C_COMPARISON_HARNESS",
        "schema_version": "p79b-v1",
        "top_level_sections": COMPARISON_SCHEMA_SECTIONS,
        "section_definitions": {
            "metadata": "script version, run timestamp, fixture season, snapshot_id, cutoff_month",
            "governance": "all 16 governance flags (paper_only=True, production_ready=False, etc.)",
            "source_snapshot": "frozen snapshot reconstruction summary (id, months, row counts)",
            "candidate_rule_metrics": "per-candidate metrics (Tier B, Primary, Shadow, Baseline)",
            "head_to_head_comparison": "Tier B vs each Tier C variant (deltas for each metric)",
            "operational_research_gate": "6-condition gate: n≥200, AUC/hit_rate, stability, ECE, concentration, prediction_only",
            "stability_diagnostics": "monthly hit_rates, chronological thirds, rolling 100",
            "calibration_diagnostics": "ECE, Brier, log_loss per candidate",
            "decision_summary": "fixture dry-run classification and rationale",
            "next_phase_recommendation": "future P79 execution prompt template",
        },
        "governance_enforcement": {
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "ev_calculated": False,
            "clv_calculated": False,
            "kelly_calculated": False,
            "production_ready": False,
            "live_api_calls": 0,
        },
        "candidate_definitions": {
            "tier_b": {
                "label": "Tier B Candidate",
                "condition": f"abs_sp_fip_delta in [{TIER_B_LOW_ABS_DELTA}, {TIER_B_HIGH_ABS_DELTA})",
                "directional": False,
            },
            "primary_125": {
                "label": "Tier C Primary — HOME_PLUS_AWAY_125",
                "condition": (
                    f"(home_pick AND abs_sp_fip_delta >= {PRIMARY_HOME_ABS_DELTA}) OR "
                    f"(away_pick AND abs_sp_fip_delta >= {PRIMARY_AWAY_ABS_DELTA})"
                ),
                "directional": True,
            },
            "shadow_100": {
                "label": "Tier C Shadow — HOME_PLUS_AWAY_100",
                "condition": (
                    f"(home_pick AND abs_sp_fip_delta >= {PRIMARY_HOME_ABS_DELTA}) OR "
                    f"(away_pick AND abs_sp_fip_delta >= {SHADOW_AWAY_ABS_DELTA})"
                ),
                "directional": True,
            },
            "baseline_50": {
                "label": "Tier C Baseline — abs_sp_fip_delta >= 0.50",
                "condition": f"abs_sp_fip_delta >= {BASELINE_ABS_DELTA}",
                "directional": False,
            },
        },
        "operational_gate_conditions": [
            f"n >= {TIER_B_TRIGGER_N}",
            "AUC >= 0.60 OR hit_rate >= primary_hit_rate + 0.02",
            "monthly_stability in [STRONG, MODERATE]",
            "ECE delta vs primary_125 < 0.03",
            "concentration_risk != SEVERE",
            "prediction_only (GOVERNANCE.production_ready=False)",
        ],
    }

# ---------------------------------------------------------------------------
# Step 3 — Reconstruct fixture snapshot
# ---------------------------------------------------------------------------

def step3_reconstruct_snapshot(predictions_path: Path) -> dict:
    """
    Load 2025 JSONL, filter to snapshot window (2025-04 to 2025-07),
    classify into 4 candidates, and return classified snapshot data.
    """
    all_rows: list[dict] = []
    with open(predictions_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                all_rows.append(json.loads(line))

    # Filter to snapshot window
    snapshot_rows: list[dict] = [
        r for r in all_rows
        if len(r.get("game_date", "")) >= 7
        and r["game_date"][:7] in SNAPSHOT_MONTHS
    ]

    total_n = len(snapshot_rows)

    # Classify each row (a row can appear in multiple candidates)
    candidate_rows: dict[str, list[dict]] = {k: [] for k in CANDIDATE_KEYS}
    for row in snapshot_rows:
        if _is_tier_b_row(row):
            candidate_rows["tier_b"].append(row)
        if _is_primary_row(row):
            candidate_rows["primary_125"].append(row)
        if _is_shadow_row(row):
            candidate_rows["shadow_100"].append(row)
        if _is_baseline_row(row):
            candidate_rows["baseline_50"].append(row)

    # Monthly breakdown
    monthly_n: dict[str, int] = {m: 0 for m in SNAPSHOT_MONTHS}
    for row in snapshot_rows:
        gdate = row.get("game_date", "")
        if len(gdate) >= 7:
            monthly_n[gdate[:7]] = monthly_n.get(gdate[:7], 0) + 1

    return {
        "snapshot_id": SNAPSHOT_ID,
        "cutoff_month": CUTOFF_MONTH,
        "snapshot_months": SNAPSHOT_MONTHS,
        "total_snapshot_rows": total_n,
        "total_all_season_rows": len(all_rows),
        "monthly_row_counts": monthly_n,
        "candidate_counts": {k: len(v) for k, v in candidate_rows.items()},
        "candidate_rows": candidate_rows,
    }

# ---------------------------------------------------------------------------
# Step 4 — Compute candidate metrics
# ---------------------------------------------------------------------------

def step4_compute_candidate_metrics(snapshot_data: dict) -> dict:
    """Compute all metrics for each candidate using snapshot data."""
    total_n = snapshot_data["total_snapshot_rows"]
    candidate_rows = snapshot_data["candidate_rows"]
    metrics: dict[str, dict] = {}

    for key in CANDIDATE_KEYS:
        rows = candidate_rows.get(key, [])
        metrics[key] = _compute_metrics(rows, total_n, key)

    return metrics

# ---------------------------------------------------------------------------
# Step 5 — Head-to-head comparison
# ---------------------------------------------------------------------------

def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(a - b, 4)


def step5_head_to_head(metrics: dict[str, dict]) -> dict:
    """Compare Tier B against each Tier C variant."""
    tb = metrics.get("tier_b", {})
    p125 = metrics.get("primary_125", {})
    s100 = metrics.get("shadow_100", {})
    b50 = metrics.get("baseline_50", {})

    comparisons: dict[str, dict] = {}

    for comparator_key, comp in [
        ("vs_primary_125", p125),
        ("vs_shadow_100", s100),
        ("vs_baseline_50", b50),
    ]:
        hit_delta = _delta(tb.get("hit_rate"), comp.get("hit_rate"))
        auc_delta = _delta(tb.get("auc"), comp.get("auc"))
        brier_delta = _delta(tb.get("brier"), comp.get("brier"))
        ece_delta = _delta(tb.get("ece"), comp.get("ece"))
        n_delta = (tb.get("n", 0) or 0) - (comp.get("n", 0) or 0)

        comparisons[comparator_key] = {
            "tier_b_n": tb.get("n"),
            "comparator_n": comp.get("n"),
            "n_delta": n_delta,
            "hit_rate_delta": hit_delta,
            "auc_delta": auc_delta,
            "brier_delta": brier_delta,  # negative = Tier B better (lower Brier)
            "ece_delta": ece_delta,       # negative = Tier B better (lower ECE)
            "tier_b_stability": tb.get("monthly_stability"),
            "comparator_stability": comp.get("monthly_stability"),
            "tier_b_concentration": tb.get("concentration_risk"),
            "comparator_concentration": comp.get("concentration_risk"),
        }

    # Operational research gate vs primary_125
    tb_n = tb.get("n", 0) or 0
    tb_hit = tb.get("hit_rate") or 0.0
    p125_hit = p125.get("hit_rate") or 0.0
    tb_auc = tb.get("auc") or 0.0
    tb_stability = tb.get("monthly_stability", "INSUFFICIENT")
    tb_ece = tb.get("ece")
    p125_ece = p125.get("ece")
    ece_delta_vs_primary = _delta(tb_ece, p125_ece)
    tb_concentration = tb.get("concentration_risk", "UNKNOWN")

    gate_conditions: dict[str, bool] = {
        "n_gte_200": tb_n >= TIER_B_TRIGGER_N,
        "performance_ok": (tb_auc >= 0.60) or (tb_hit >= p125_hit + 0.02),
        "stability_ok": tb_stability in ("STRONG", "MODERATE"),
        "ece_ok": (ece_delta_vs_primary is None) or (ece_delta_vs_primary < 0.03),
        "concentration_ok": tb_concentration != "SEVERE",
        "prediction_only": True,  # enforced by GOVERNANCE.production_ready=False
    }
    gate_passes = all(gate_conditions.values())

    return {
        "comparisons": comparisons,
        "operational_research_gate": {
            "conditions": gate_conditions,
            "gate_passes": gate_passes,
            "gate_fail_reasons": [
                k for k, v in gate_conditions.items() if not v
            ],
        },
        "tier_b_cannot_become_production_ready": True,
        "market_edge_lane": "blocked",
    }

# ---------------------------------------------------------------------------
# Step 6 — Fixture dry-run classification
# ---------------------------------------------------------------------------

def step6_fixture_classification(
    metrics: dict[str, dict],
    head_to_head: dict,
) -> dict:
    """Classify the fixture dry-run result."""
    tb = metrics.get("tier_b", {})
    p125 = metrics.get("primary_125", {})
    gate = head_to_head.get("operational_research_gate", {})
    gate_passes = gate.get("gate_passes", False)

    tb_n = tb.get("n", 0) or 0
    tb_hit = tb.get("hit_rate") or 0.0
    p125_hit = p125.get("hit_rate") or 0.0
    hit_delta = tb_hit - p125_hit

    if tb_n < TIER_B_TRIGGER_N:
        fixture_class = "TIER_B_FIXTURE_INCONCLUSIVE"
        rationale = f"Tier B n={tb_n} < {TIER_B_TRIGGER_N}. Insufficient sample for fixture classification."
    elif gate_passes and hit_delta > 0.03:
        fixture_class = "TIER_B_OUTPERFORMS_TIER_C_FIXTURE"
        rationale = (
            f"Gate passes. Tier B hit_rate={tb_hit:.3f} > primary_125 hit_rate={p125_hit:.3f} "
            f"by {hit_delta:.3f} (> 0.03 threshold)."
        )
    elif gate_passes and hit_delta >= -0.02:
        fixture_class = "TIER_B_COMPETITIVE_WITH_TIER_C_FIXTURE"
        rationale = (
            f"Gate passes. Tier B hit_rate={tb_hit:.3f} is competitive with "
            f"primary_125 hit_rate={p125_hit:.3f} (delta={hit_delta:.3f})."
        )
    elif gate_passes:
        # Gate passes but hit_rate lags > 0.02 below primary
        fixture_class = "TIER_B_RESEARCH_ONLY_FIXTURE"
        rationale = (
            f"Gate passes but Tier B hit_rate={tb_hit:.3f} lags "
            f"primary_125={p125_hit:.3f} by {abs(hit_delta):.3f}. Research-only."
        )
    elif sum(gate.get("conditions", {}).values()) >= 4:
        fixture_class = "TIER_B_RESEARCH_ONLY_FIXTURE"
        fail_reasons = gate.get("gate_fail_reasons", [])
        rationale = (
            f"Gate fails on: {fail_reasons}. "
            f"Enough conditions pass for research-only status."
        )
    else:
        fixture_class = "TIER_B_UNDERPERFORMS_TIER_C_FIXTURE"
        fail_reasons = gate.get("gate_fail_reasons", [])
        rationale = (
            f"Gate fails on: {fail_reasons}. "
            f"Tier B hit_rate={tb_hit:.3f} lags primary_125={p125_hit:.3f}."
        )

    return {
        "fixture_dry_run_classification": fixture_class,
        "rationale": rationale,
        "is_2026_live_conclusion": False,
        "fixture_only_disclaimer": (
            "This classification is based on 2025 fixture data only. "
            "It does NOT constitute a 2026 live performance claim. "
            "Champion strategy unchanged. No bets recommended."
        ),
        "tier_b_fixture_hit_rate": tb_hit,
        "primary_125_fixture_hit_rate": p125_hit,
        "hit_rate_delta": round(hit_delta, 4),
        "gate_passes": gate_passes,
        "gate_conditions": gate.get("conditions", {}),
    }

# ---------------------------------------------------------------------------
# Step 7 — Future P79 execution prompt
# ---------------------------------------------------------------------------

def step7_future_p79_prompt(
    fixture_classification: str,
    metrics: dict[str, dict],
) -> dict:
    tb_n = (metrics.get("tier_b") or {}).get("n", 0) or 0
    prompt_text = f"""[P79 — Tier B Sample Expansion Analysis vs Tier C Finalists on 2026 Live Data]
================================================================================

TRIGGER CONDITION: Tier B cumulative n >= {TIER_B_TRIGGER_N} in 2026 live accumulation

REQUIRED SNAPSHOT PACKAGE:
  - snapshot_id: tier_b_snapshot_2026_<YYYYMM>       ← set at trigger month
  - trigger_date: <YYYY-MM>                           ← first month n >= 200
  - season: 2026
  - data_cutoff: <YYYY-MM-DD>                        ← last game date in trigger month
  - tier_b_n: <int>                                   ← cumulative Tier B count
  - tier_b_months_covered: list[str]
  - governance_snapshot: all 9 flags from P79A schema

REQUIRED SOURCE FILES:
  - data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json
  - data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json
  - data/mlb_2026/derived/mlb_2026_per_game_predictions_<version>.jsonl
  - scripts/_p79b_tier_b_vs_tier_c_comparison_harness.py  ← run on 2026 data

EXPECTED TRIGGER STATE: TIER_B_TRIGGER_FROZEN

COMPARISON HARNESS COMMAND:
  .venv/bin/python scripts/_p79b_tier_b_vs_tier_c_comparison_harness.py \\
      --snapshot-id tier_b_snapshot_2026_<YYYYMM> \\
      --predictions data/mlb_2026/derived/mlb_2026_per_game_predictions_<ver>.jsonl \\
      --output-dir data/mlb_2026/derived/

OUTPUT LOCATIONS:
  - data/mlb_2026/derived/p79_tier_b_comparison_harness_summary.json
  - report/p79_tier_b_comparison_harness_<YYYYMMDD>.md

STOP CONDITIONS:
  - predictions JSONL not found or empty
  - trigger_n < {TIER_B_TRIGGER_N}
  - governance_snapshot.production_ready == True
  - governance_snapshot.ev_calculated == True
  - governance_snapshot.odds_used == True
  - governance_snapshot.live_api_calls > 0

GOVERNANCE INVARIANTS (must all hold):
  paper_only=True | diagnostic_only=True | production_ready=False
  ev_calculated=False | clv_calculated=False | kelly_calculated=False
  odds_used=False | market_edge_evaluated=False | live_api_calls=0

EXPECTED CLASSIFICATION LIST:
  - P79_TIER_B_FIXTURE_OUTPERFORMS_TIER_C
  - P79_TIER_B_FIXTURE_COMPETITIVE_WITH_TIER_C
  - P79_TIER_B_FIXTURE_RESEARCH_ONLY
  - P79_TIER_B_FIXTURE_UNDERPERFORMS_TIER_C
  - P79_TIER_B_FIXTURE_INCONCLUSIVE
  - P79_BLOCKED_BY_MISSING_SOURCE_ARTIFACT
  - P79_FAILED_VALIDATION

MARKET-EDGE: DEFERRED to P80 (pending odds API key)
PRODUCTION READINESS: NOT achievable in P79

2025 FIXTURE DRY-RUN REFERENCE:
  - P79B fixture classification: {fixture_classification}
  - 2025 Tier B fixture n at trigger: {tb_n}
  - Fixture snapshot: {SNAPSHOT_ID}
================================================================================"""

    return {
        "prompt_text": prompt_text,
        "trigger_condition": f"2026 live Tier B n >= {TIER_B_TRIGGER_N}",
        "expected_trigger_season": "2026",
        "market_edge_note": "DEFERRED to P80",
        "production_readiness_note": "NOT achievable in P79",
        "fixture_reference_classification": fixture_classification,
        "fixture_reference_snapshot_id": SNAPSHOT_ID,
    }

# ---------------------------------------------------------------------------
# Step 8 — Forbidden scan
# ---------------------------------------------------------------------------

def step8_forbidden_scan() -> dict:
    """Verify GOVERNANCE dict has no forbidden violations."""
    violations: list[str] = []
    checks = {
        "paper_only": (True, "must be True"),
        "diagnostic_only": (True, "must be True"),
        "uses_historical_odds": (False, "must be False"),
        "live_api_calls": (0, "must be 0"),
        "odds_used": (False, "must be False"),
        "ev_calculated": (False, "must be False"),
        "clv_calculated": (False, "must be False"),
        "market_edge_evaluated": (False, "must be False"),
        "kelly_calculated": (False, "must be False"),
        "kelly_deploy_allowed": (False, "must be False"),
        "production_ready": (False, "must be False"),
        "real_bet_allowed": (False, "must be False"),
        "champion_replacement_allowed": (False, "must be False"),
        "profitability_claim": (False, "must be False"),
        "promotion_freeze": (True, "must be True"),
    }
    for key, (expected, note) in checks.items():
        actual = GOVERNANCE.get(key)
        if actual != expected:
            violations.append(
                f"GOVERNANCE[{key!r}]={actual!r}, expected={expected!r} ({note})"
            )
    return {
        "scan_passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }

# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _fmt(v: Optional[float], decimals: int = 4) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}"


def _write_report(summary: dict, path: Path) -> None:
    cls = summary.get("p79b_classification", "UNKNOWN")
    s3 = summary.get("step3_source_snapshot", {})
    s4 = summary.get("step4_candidate_metrics", {})
    s5 = summary.get("step5_head_to_head", {})
    s6 = summary.get("step6_fixture_classification", {})
    s7 = summary.get("step7_future_p79_prompt", {})

    lines: list[str] = [
        "# P79B — Tier B vs Tier C Comparison Harness Fixture Dry-Run",
        "",
        f"> **Classification**: `{cls}`",
        f"> **Schema Version**: `{summary.get('schema_version', 'UNKNOWN')}`",
        f"> **Generated**: {summary.get('generated_at', '')}",
        "> **Mode**: `paper_only=True | diagnostic_only=True | production_ready=False`",
        "> **Fixture Disclaimer**: 2025 data dry-run only. NOT a 2026 live performance claim.",
        "",
        "---",
        "",
        "## Source Artifacts Verified",
        "",
    ]
    for art in summary.get("source_artifacts_verified", []):
        lines.append(f"- ✅ {art}")

    lines += [
        "",
        "## P79A Trigger Readiness Verification",
        "",
    ]
    s1 = summary.get("step1_p79a_verification", {})
    lines += [
        f"- Classification: `{s1.get('classification', 'N/A')}`",
        f"- Snapshot ID: `{s1.get('snapshot_id', 'N/A')}`",
        f"- Trigger n: {s1.get('trigger_n', 0)}",
        f"- Trigger month: `{s1.get('trigger_month', 'N/A')}`",
        f"- Market-edge lane: `{s1.get('market_edge_lane', 'N/A')}`",
        f"- **Verified**: {s1.get('verified', False)}",
    ]

    lines += [
        "",
        "## Fixture Snapshot Reconstruction",
        "",
        f"- Snapshot ID: `{s3.get('snapshot_id', 'N/A')}`",
        f"- Cutoff month: `{s3.get('cutoff_month', 'N/A')}`",
        f"- Snapshot months: {', '.join(s3.get('snapshot_months', []))}",
        f"- Total snapshot rows: {s3.get('total_snapshot_rows', 0)}",
        "",
        "| Candidate | n |",
        "|-----------|---|",
    ]
    for k, n in s3.get("candidate_counts", {}).items():
        lines.append(f"| `{k}` | {n} |")

    lines += [
        "",
        "## Candidate Metrics Table",
        "",
        "| Candidate | n | Hit Rate | CI Lower | CI Upper | AUC | Brier | ECE | Stability | Concentration |",
        "|-----------|---|----------|----------|----------|-----|-------|-----|-----------|---------------|",
    ]
    for key in CANDIDATE_KEYS:
        m = s4.get(key, {})
        lines.append(
            f"| `{key}` | {m.get('n', 0)} "
            f"| {_fmt(m.get('hit_rate'), 3)} "
            f"| {_fmt(m.get('hit_rate_ci_lower'), 3)} "
            f"| {_fmt(m.get('hit_rate_ci_upper'), 3)} "
            f"| {_fmt(m.get('auc'), 3)} "
            f"| {_fmt(m.get('brier'), 3)} "
            f"| {_fmt(m.get('ece'), 3)} "
            f"| {m.get('monthly_stability', 'N/A')} "
            f"| {m.get('concentration_risk', 'N/A')} |"
        )

    lines += [
        "",
        "### Home/Away Split",
        "",
        "| Candidate | n_home | home_hit_rate | n_away | away_hit_rate | Rolling 100 |",
        "|-----------|--------|---------------|--------|---------------|-------------|",
    ]
    for key in CANDIDATE_KEYS:
        m = s4.get(key, {})
        lines.append(
            f"| `{key}` | {m.get('n_home', 0)} "
            f"| {_fmt(m.get('home_hit_rate'), 3)} "
            f"| {m.get('n_away', 0)} "
            f"| {_fmt(m.get('away_hit_rate'), 3)} "
            f"| {_fmt(m.get('rolling_100_hit_rate'), 3)} |"
        )

    lines += [
        "",
        "## Head-to-Head Comparison",
        "",
        "| vs | hit_rate_delta | auc_delta | brier_delta | ece_delta |",
        "|----|---------------|-----------|-------------|-----------|",
    ]
    for ckey, comp in s5.get("comparisons", {}).items():
        lines.append(
            f"| `{ckey}` "
            f"| {_fmt(comp.get('hit_rate_delta'), 4)} "
            f"| {_fmt(comp.get('auc_delta'), 4)} "
            f"| {_fmt(comp.get('brier_delta'), 4)} "
            f"| {_fmt(comp.get('ece_delta'), 4)} |"
        )

    lines += [
        "",
        "## Operational Research Gate",
        "",
    ]
    gate = s5.get("operational_research_gate", {})
    for cond, result in gate.get("conditions", {}).items():
        emoji = "✅" if result else "❌"
        lines.append(f"- {emoji} `{cond}`: {result}")
    lines.append(f"\n**Gate passes**: {gate.get('gate_passes', False)}")
    if gate.get("gate_fail_reasons"):
        lines.append(f"**Fail reasons**: {gate.get('gate_fail_reasons')}")

    lines += [
        "",
        "## Fixture Dry-Run Decision",
        "",
        f"**Classification**: `{s6.get('fixture_dry_run_classification', 'UNKNOWN')}`",
        "",
        f"> {s6.get('rationale', '')}",
        "",
        f"**⚠️ Disclaimer**: {s6.get('fixture_only_disclaimer', '')}",
        "",
        "## Monthly Stability Diagnostics",
        "",
    ]
    for key in CANDIDATE_KEYS:
        m = s4.get(key, {})
        mr = m.get("monthly_results", {})
        if mr:
            lines.append(f"### {key}")
            lines.append("")
            lines.append("| Month | n | hit_rate | ci_lower | ci_upper |")
            lines.append("|-------|---|----------|----------|----------|")
            for month, v in mr.items():
                lines.append(
                    f"| {month} | {v.get('n', 0)} "
                    f"| {_fmt(v.get('hit_rate'), 3)} "
                    f"| {_fmt(v.get('ci_lower'), 3)} "
                    f"| {_fmt(v.get('ci_upper'), 3)} |"
                )
            lines.append("")

    lines += [
        "",
        "## Future P79 Execution Prompt",
        "",
        "```",
        s7.get("prompt_text", ""),
        "```",
        "",
        "## Governance Invariants",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in GOVERNANCE.items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        "",
        "## Forbidden Scan",
        "",
    ]
    scan = summary.get("step8_forbidden_scan", {})
    lines.append(f"- **Result**: {'✅ PASS' if scan.get('scan_passed') else '❌ FAIL'}")
    lines.append(f"- **Violations**: {scan.get('violations_count', 0)}")

    lines += [
        "",
        "---",
        "",
        "*P79B — Fixture dry-run only. No live data fetched. No production modification.*",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== P79B Tier B vs Tier C Comparison Harness Fixture Dry-Run ===")
    print(f"Mode: paper_only={GOVERNANCE['paper_only']} | diagnostic_only={GOVERNANCE['diagnostic_only']}")
    print(f"live_api_calls={GOVERNANCE['live_api_calls']} | production_ready={GOVERNANCE['production_ready']}")

    # Verify source artifacts
    missing = [str(PATHS[k]) for k in SOURCE_ARTIFACT_KEYS if not PATHS[k].exists()]
    if missing:
        print(f"STOP — Missing source artifacts:\n" + "\n".join(missing))
        return
    artifact_names = [PATHS[k].name for k in SOURCE_ARTIFACT_KEYS]
    print(f"✓ All {len(artifact_names)} source artifacts verified")

    # Step 1
    s1 = step1_verify_p79a()
    if not s1["verified"]:
        print(f"STOP — P79A verification failed: {s1['errors']}")
        return
    print(
        f"✓ P79A verified: {s1['classification']} | "
        f"trigger_n={s1['trigger_n']} | snapshot={s1['snapshot_id']}"
    )

    # Step 2
    s2 = step2_comparison_schema()
    print(f"✓ Comparison harness schema defined: {len(s2['top_level_sections'])} sections")

    # Step 3
    s3 = step3_reconstruct_snapshot(PATHS["predictions_jsonl"])
    tier_b_n = s3["candidate_counts"].get("tier_b", 0)
    if abs(tier_b_n - (s1["trigger_n"] or 0)) > SNAPSHOT_COUNT_TOLERANCE:
        print(
            f"WARN — Tier B snapshot n={tier_b_n} differs from P79A trigger_n="
            f"{s1['trigger_n']} by more than tolerance={SNAPSHOT_COUNT_TOLERANCE}"
        )
    print(
        f"✓ Fixture snapshot reconstructed: total_rows={s3['total_snapshot_rows']} | "
        f"tier_b_n={tier_b_n}"
    )
    for k, n in s3["candidate_counts"].items():
        print(f"  {k}: n={n}")

    # Step 4
    s4 = step4_compute_candidate_metrics(s3)
    print("✓ Candidate metrics computed:")
    for key in CANDIDATE_KEYS:
        m = s4[key]
        print(
            f"  {key}: n={m.get('n', 0)}, "
            f"hit_rate={_fmt(m.get('hit_rate'), 3)}, "
            f"auc={_fmt(m.get('auc'), 3)}, "
            f"stability={m.get('monthly_stability', 'N/A')}"
        )

    # Step 5
    s5 = step5_head_to_head(s4)
    gate = s5["operational_research_gate"]
    print(f"✓ Head-to-head comparison done | gate_passes={gate['gate_passes']}")
    if gate.get("gate_fail_reasons"):
        print(f"  Gate fail reasons: {gate['gate_fail_reasons']}")

    # Step 6
    s6 = step6_fixture_classification(s4, s5)
    fixture_class = s6["fixture_dry_run_classification"]
    print(f"✓ Fixture dry-run classification: {fixture_class}")

    # Step 7
    s7 = step7_future_p79_prompt(fixture_class, s4)
    print(f"✓ Future P79 execution prompt generated")

    # Step 8
    s8 = step8_forbidden_scan()
    print(f"✓ Forbidden scan: {'PASS' if s8['scan_passed'] else 'FAIL'} ({s8['violations_count']} violations)")

    # P79B final classification
    if fixture_class == "TIER_B_OUTPERFORMS_TIER_C_FIXTURE":
        p79b_cls = "P79B_TIER_B_FIXTURE_OUTPERFORMS_TIER_C"
    elif fixture_class == "TIER_B_COMPETITIVE_WITH_TIER_C_FIXTURE":
        p79b_cls = "P79B_TIER_B_FIXTURE_COMPETITIVE_WITH_TIER_C"
    elif fixture_class == "TIER_B_RESEARCH_ONLY_FIXTURE":
        p79b_cls = "P79B_TIER_B_FIXTURE_RESEARCH_ONLY"
    elif fixture_class == "TIER_B_UNDERPERFORMS_TIER_C_FIXTURE":
        p79b_cls = "P79B_TIER_B_FIXTURE_UNDERPERFORMS_TIER_C"
    else:
        p79b_cls = "P79B_TIER_B_COMPARISON_HARNESS_READY"

    # Remove candidate_rows (large, not needed in JSON)
    s3_out = {k: v for k, v in s3.items() if k != "candidate_rows"}
    s4_out = {k: {kk: vv for kk, vv in v.items() if kk != "insufficient"} for k, v in s4.items()}

    summary = {
        "p79b_classification": p79b_cls,
        "schema_version": "p79b-v1",
        "generated_at": datetime.now().isoformat(),
        "governance_snapshot": GOVERNANCE,
        "source_artifacts_verified": artifact_names,
        "step1_p79a_verification": s1,
        "step2_comparison_schema": s2,
        "step3_source_snapshot": s3_out,
        "step4_candidate_metrics": s4_out,
        "step5_head_to_head": s5,
        "step6_fixture_classification": s6,
        "step7_future_p79_prompt": s7,
        "step8_forbidden_scan": s8,
        "market_edge_lane": "blocked",
        "fixture_dry_run_classification": fixture_class,
        "fixture_is_2026_live_conclusion": False,
    }

    # Write JSON
    out_json = PATHS["output_json"]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"✓ JSON written: {out_json.name}")

    # Write report
    _write_report(summary, PATHS["output_report"])
    print(f"✓ Report written: {PATHS['output_report'].name}")

    # BettingPlan copy
    bp_path = PATHS["output_betting_plan"]
    bp_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PATHS["output_report"], bp_path)
    print(f"✓ BettingPlan copy written: {bp_path.name}")

    print(f"\nClassification: {p79b_cls}")
    print(f"Fixture result: {fixture_class}")
    print(f"Forbidden: {'PASS' if s8['scan_passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
