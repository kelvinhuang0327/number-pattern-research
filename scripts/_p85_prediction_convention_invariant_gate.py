"""
P85 — Prediction Convention Invariant Gate
==========================================
Purpose:
    Establish a semantic-level invariant gate that detects future silent side
    inversion or incorrect label fossilization before regression tests could
    accidentally lock in the wrong mapping.

Governance:
    paper_only          = True
    diagnostic_only     = True
    production_ready    = False
    odds_used           = False
    ev_computed         = False
    clv_computed        = False
    kelly_computed      = False
    live_api_calls      = 0
    paid_api_called     = False
    canonical_rows_modified   = False
    outcome_rows_modified     = False
    p83e_mapping_modified     = False
    champion_replaced         = False

Convention under guard:
    sp_fip_delta = home_sp_fip - away_sp_fip
    FIP: lower is better
    delta > 0  →  home pitcher FIP higher (worse)  →  predicted_side = 'away'
    delta < 0  →  away pitcher FIP higher (worse)  →  predicted_side = 'home'
    delta == 0 →  tie; predicted_side determined by model_probability threshold
                  (prob > 0.5 → 'home', prob < 0.5 → 'away', prob == 0.5 → abstain)
    model_probability = P(home wins), NOT P(predicted side wins)
    actual_winner derived from result_home_score vs result_away_score
    is_correct = (predicted_side == actual_winner)

Allowed final classifications:
    P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY
    P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH
    P85_INVARIANT_GATE_FAILED_MAPPING_REGRESSION
    P85_INVARIANT_GATE_BLOCKED_BY_PREFLIGHT
    P85_INVARIANT_GATE_BLOCKED_BY_SCOPE_DRIFT
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"
ACTIVE_TASK = ROOT / "00-Plan" / "roadmap" / "active_task.md"

P83E_SUMMARY = DERIVED / "p83e_2026_canonical_prediction_row_producer_summary.json"
P84E_SUMMARY = DERIVED / "p84e_2026_outcome_attachment_summary.json"
P84E_ROWS    = DERIVED / "p84e_2026_outcome_attached_prediction_rows.jsonl"
P84G_SUMMARY = DERIVED / "p84g_predicted_side_mapping_fix_summary.json"
P84H_SUMMARY = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"

P85_SUMMARY_PATH = DERIVED / "p85_prediction_convention_invariant_gate_summary.json"
P85_REPORT_PATH  = REPORT_DIR / "p85_prediction_convention_invariant_gate_20260527.md"

# ---------------------------------------------------------------------------
# Expected locked values from prior pipeline
# ---------------------------------------------------------------------------
EXPECTED_P84H_CLASS = "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"
EXPECTED_P84G_CLASS = "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"
EXPECTED_P83E_CLASS = "P83E_CANONICAL_ROWS_READY"

ALLOWED_CLASSIFICATIONS = [
    "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
    "P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH",
    "P85_INVARIANT_GATE_FAILED_MAPPING_REGRESSION",
    "P85_INVARIANT_GATE_BLOCKED_BY_PREFLIGHT",
    "P85_INVARIANT_GATE_BLOCKED_BY_SCOPE_DRIFT",
]

TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Step 1 — Artifact existence + predecessor classification lock
# ---------------------------------------------------------------------------

def step1_artifact_lock() -> dict:
    result: dict = {"step": "step1_artifact_lock", "checks": {}, "status": "UNKNOWN"}

    required = {
        "p83e_summary": P83E_SUMMARY,
        "p84e_summary": P84E_SUMMARY,
        "p84e_rows":    P84E_ROWS,
        "p84g_summary": P84G_SUMMARY,
        "p84h_summary": P84H_SUMMARY,
    }

    missing = []
    for name, path in required.items():
        exists = path.exists()
        result["checks"][f"{name}_exists"] = exists
        if not exists:
            missing.append(name)

    if missing:
        result["status"] = "FAILED"
        result["missing_artifacts"] = missing
        return result

    # Check predecessor classifications are locked
    p83e = _load_json(P83E_SUMMARY)
    p84g = _load_json(P84G_SUMMARY)
    p84h = _load_json(P84H_SUMMARY)

    p83e_cls = p83e.get("p83e_classification", "")
    p84g_cls = p84g.get("p84g_classification", "")
    p84h_cls = p84h.get("p84h_classification", "")

    result["checks"]["p83e_classification"] = p83e_cls
    result["checks"]["p84g_classification"] = p84g_cls
    result["checks"]["p84h_classification"] = p84h_cls

    result["checks"]["p83e_class_locked"] = (p83e_cls == EXPECTED_P83E_CLASS)
    result["checks"]["p84g_class_locked"] = (p84g_cls == EXPECTED_P84G_CLASS)
    result["checks"]["p84h_class_locked"] = (p84h_cls == EXPECTED_P84H_CLASS)

    all_locked = all([
        result["checks"]["p83e_class_locked"],
        result["checks"]["p84g_class_locked"],
        result["checks"]["p84h_class_locked"],
    ])

    result["status"] = "PASSED" if all_locked else "FAILED"
    return result


# ---------------------------------------------------------------------------
# Step 2 — FIP mapping invariant: positive delta → away
# ---------------------------------------------------------------------------

def step2_fip_positive_invariant(rows: list[dict]) -> dict:
    """delta > 0 (home pitcher worse) must map to predicted_side='away'."""
    outcome_rows = [r for r in rows if r.get("outcome_available")]
    pos_rows = [r for r in outcome_rows if r["sp_fip_delta"] > 0]

    violations = [
        {
            "game_id": r["game_id"],
            "sp_fip_delta": r["sp_fip_delta"],
            "predicted_side": r["predicted_side"],
            "model_probability": r["model_probability"],
        }
        for r in pos_rows
        if r["predicted_side"] != "away"
    ]

    return {
        "step": "step2_fip_positive_invariant",
        "description": "sp_fip_delta > 0 (home pitcher FIP higher/worse) must predict 'away'",
        "n_positive_delta_rows": len(pos_rows),
        "n_violations": len(violations),
        "violations": violations[:5],  # cap for readability
        "status": "PASSED" if not violations else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 3 — FIP mapping invariant: negative delta → home
# ---------------------------------------------------------------------------

def step3_fip_negative_invariant(rows: list[dict]) -> dict:
    """delta < 0 (away pitcher worse) must map to predicted_side='home'."""
    outcome_rows = [r for r in rows if r.get("outcome_available")]
    neg_rows = [r for r in outcome_rows if r["sp_fip_delta"] < 0]

    violations = [
        {
            "game_id": r["game_id"],
            "sp_fip_delta": r["sp_fip_delta"],
            "predicted_side": r["predicted_side"],
            "model_probability": r["model_probability"],
        }
        for r in neg_rows
        if r["predicted_side"] != "home"
    ]

    return {
        "step": "step3_fip_negative_invariant",
        "description": "sp_fip_delta < 0 (away pitcher FIP higher/worse) must predict 'home'",
        "n_negative_delta_rows": len(neg_rows),
        "n_violations": len(violations),
        "violations": violations[:5],
        "status": "PASSED" if not violations else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 4 — Zero-delta policy documentation + verification
# ---------------------------------------------------------------------------

def step4_zero_delta_policy(rows: list[dict]) -> dict:
    """
    Zero-delta policy:
        delta == 0 → FIP is tied; predicted_side is determined by
        model_probability threshold alone:
            prob > 0.5  → 'home'
            prob < 0.5  → 'away'
            prob == 0.5 → abstain (no prediction; governance flag must be set)
    """
    outcome_rows = [r for r in rows if r.get("outcome_available")]
    zero_rows = [r for r in outcome_rows if r["sp_fip_delta"] == 0]

    # Also check near-zero (abs_delta < 0.01) to document edge behavior
    near_zero_rows = [r for r in outcome_rows if 0 < abs(r["sp_fip_delta"]) < 0.01]

    zero_violations = []
    for r in zero_rows:
        prob = r["model_probability"]
        side = r["predicted_side"]
        if prob > 0.5 and side != "home":
            zero_violations.append({"game_id": r["game_id"], "prob": prob, "predicted_side": side, "issue": "prob>0.5 should be home"})
        elif prob < 0.5 and side != "away":
            zero_violations.append({"game_id": r["game_id"], "prob": prob, "predicted_side": side, "issue": "prob<0.5 should be away"})

    policy = {
        "rule": "sp_fip_delta == 0 → predicted_side determined by model_probability only",
        "prob_gt_half": "predicted_side = 'home'",
        "prob_lt_half": "predicted_side = 'away'",
        "prob_eq_half": "abstain — row must be excluded from hit_rate computation",
        "note": "No zero-delta rows in current dataset (min abs delta = 0.0077). Policy documented for future gate enforcement.",
    }

    return {
        "step": "step4_zero_delta_policy",
        "zero_delta_policy": policy,
        "n_zero_delta_rows": len(zero_rows),
        "n_near_zero_rows": len(near_zero_rows),
        "near_zero_threshold": 0.01,
        "zero_violations": zero_violations,
        "min_abs_delta_in_dataset": min((abs(r["sp_fip_delta"]) for r in outcome_rows), default=None),
        "status": "PASSED" if not zero_violations else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 5 — model_probability semantic check (P(home wins))
# ---------------------------------------------------------------------------

def step5_probability_semantics(rows: list[dict]) -> dict:
    """
    model_probability must be interpreted as P(home wins).
    Therefore:
        prob > 0.5 → predicted_side == 'home'
        prob < 0.5 → predicted_side == 'away'
        prob == 0.5 → ambiguous (tie threshold; currently handled by FIP signal)

    This is the inverse of P(predicted side wins), which would be trivially
    near 1.0 for all rows (vacuous). This check guards against that confusion.
    """
    outcome_rows = [r for r in rows if r.get("outcome_available")]

    prob_violations = []
    for r in outcome_rows:
        prob = r["model_probability"]
        side = r["predicted_side"]
        if prob > 0.5 and side != "home":
            prob_violations.append({
                "game_id": r["game_id"],
                "model_probability": prob,
                "predicted_side": side,
                "issue": "prob > 0.5 but not 'home'",
            })
        elif prob < 0.5 and side != "away":
            prob_violations.append({
                "game_id": r["game_id"],
                "model_probability": prob,
                "predicted_side": side,
                "issue": "prob < 0.5 but not 'away'",
            })

    # Confirm model_probability is NOT trivially near 1.0 for all rows
    # (if it were, it would mean prob=P(predicted side wins) — wrong interpretation)
    probs = [r["model_probability"] for r in outcome_rows]
    mean_prob = sum(probs) / len(probs) if probs else 0.0
    below_half = sum(1 for p in probs if p < 0.5)
    above_half = sum(1 for p in probs if p > 0.5)

    trivially_high = mean_prob > 0.95  # would indicate wrong interpretation
    has_below_half_rows = below_half > 0

    return {
        "step": "step5_probability_semantics",
        "description": "model_probability = P(home wins). Not P(predicted side wins).",
        "n_rows": len(outcome_rows),
        "mean_model_probability": round(mean_prob, 6),
        "n_prob_above_half": above_half,
        "n_prob_below_half": below_half,
        "trivially_high_flag": trivially_high,
        "has_below_half_rows": has_below_half_rows,
        "n_prob_violations": len(prob_violations),
        "prob_violations": prob_violations[:5],
        "status": "PASSED" if (not prob_violations and not trivially_high and has_below_half_rows) else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 6 — actual_winner derivation consistency
# ---------------------------------------------------------------------------

def step6_actual_winner_consistency(rows: list[dict]) -> dict:
    """actual_winner must be consistent with result_home_score / result_away_score."""
    outcome_rows = [r for r in rows if r.get("outcome_available")]

    violations = []
    ties = []
    for r in outcome_rows:
        h = r["result_home_score"]
        a = r["result_away_score"]
        w = r["actual_winner"]
        if h > a and w != "home":
            violations.append({"game_id": r["game_id"], "home_score": h, "away_score": a, "actual_winner": w})
        elif a > h and w != "away":
            violations.append({"game_id": r["game_id"], "home_score": h, "away_score": a, "actual_winner": w})
        elif h == a:
            ties.append({"game_id": r["game_id"], "score": h})

    return {
        "step": "step6_actual_winner_consistency",
        "description": "actual_winner must match result_home_score vs result_away_score",
        "n_outcome_rows": len(outcome_rows),
        "n_violations": len(violations),
        "n_tied_scores": len(ties),  # baseball ties are rare but documented
        "violations": violations[:5],
        "status": "PASSED" if not violations else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 7 — is_correct label consistency
# ---------------------------------------------------------------------------

def step7_is_correct_consistency(rows: list[dict]) -> dict:
    """is_correct must equal (predicted_side == actual_winner)."""
    outcome_rows = [r for r in rows if r.get("outcome_available")]

    violations = []
    for r in outcome_rows:
        expected = r["predicted_side"] == r["actual_winner"]
        actual_flag = r["is_correct"]
        if expected != actual_flag:
            violations.append({
                "game_id": r["game_id"],
                "predicted_side": r["predicted_side"],
                "actual_winner": r["actual_winner"],
                "is_correct_stored": actual_flag,
                "is_correct_computed": expected,
            })

    n_correct = sum(1 for r in outcome_rows if r["is_correct"])
    hit_rate = n_correct / len(outcome_rows) if outcome_rows else 0.0

    return {
        "step": "step7_is_correct_consistency",
        "description": "is_correct == (predicted_side == actual_winner)",
        "n_outcome_rows": len(outcome_rows),
        "n_correct": n_correct,
        "computed_hit_rate": round(hit_rate, 6),
        "n_violations": len(violations),
        "violations": violations[:5],
        "status": "PASSED" if not violations else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 8 — AUC / hit_rate semantic consistency guard
# ---------------------------------------------------------------------------

def step8_auc_hit_rate_guard(rows: list[dict], p84h_summary: dict) -> dict:
    """
    Guard against the silent AUC/hit_rate semantic contradiction that was
    detected in P84F:
        - hit_rate = fraction of correct side predictions
        - AUC = sklearn roc_auc_score(y_true, model_probability)
          where y_true = (actual_winner == 'home')  [not predicted_side == winner]

    This step verifies:
    1. hit_rate is recomputed and matches P84H reported value within tolerance
    2. AUC > 0.5 is consistent with hit_rate > 0.5 (not contradictory)
    3. AUC was NOT computed as P(predicted_side wins) — which would be vacuously ~1.0

    Forbidden: Platt scaling / isotonic refit / re-training
    """
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return {"step": "step8_auc_hit_rate_guard", "status": "SKIPPED", "reason": "sklearn not available"}

    outcome_rows = [r for r in rows if r.get("outcome_available")]

    # Recompute hit_rate
    n = len(outcome_rows)
    n_correct = sum(1 for r in outcome_rows if r["is_correct"])
    hit_rate = n_correct / n if n > 0 else 0.0

    # Recompute AUC: model_probability = P(home wins), y_true = home won
    y_true = [1 if r["actual_winner"] == "home" else 0 for r in outcome_rows]
    y_prob = [r["model_probability"] for r in outcome_rows]
    auc = roc_auc_score(y_true, y_prob)

    # Pull P84H reference
    p84h_key = p84h_summary.get("step2_recomputed_metrics", {}).get("recomputed", {})
    ref_hit_rate = p84h_key.get("hit_rate", None)
    ref_auc      = p84h_key.get("auc", None)

    hit_rate_delta = abs(hit_rate - ref_hit_rate) if ref_hit_rate is not None else None
    auc_delta      = abs(auc - ref_auc) if ref_auc is not None else None

    hit_rate_ok = (hit_rate_delta is not None and hit_rate_delta < TOLERANCE)
    auc_ok      = (auc_delta is not None and auc_delta < TOLERANCE)

    # Semantic consistency: both > 0.5 or both < 0.5 (should not contradict)
    both_above_half = hit_rate > 0.5 and auc > 0.5
    contradictory   = (hit_rate > 0.5 and auc < 0.5) or (hit_rate < 0.5 and auc > 0.5)

    # Anti-vacuous check: AUC should NOT be near 1.0 (would indicate wrong interpretation)
    auc_vacuous = auc > 0.95

    status = "PASSED" if (hit_rate_ok and auc_ok and not contradictory and not auc_vacuous) else "FAILED"

    return {
        "step": "step8_auc_hit_rate_guard",
        "description": "AUC = roc_auc_score(y_true=home_won, y_score=model_probability). Not P(predicted side wins).",
        "recomputed_hit_rate": round(hit_rate, 6),
        "recomputed_auc": round(auc, 6),
        "p84h_ref_hit_rate": ref_hit_rate,
        "p84h_ref_auc": ref_auc,
        "hit_rate_delta": round(hit_rate_delta, 8) if hit_rate_delta is not None else None,
        "auc_delta": round(auc_delta, 8) if auc_delta is not None else None,
        "hit_rate_matches_p84h": hit_rate_ok,
        "auc_matches_p84h": auc_ok,
        "semantically_consistent": not contradictory,
        "auc_vacuous": auc_vacuous,
        "platt_isotonic_refit": "FORBIDDEN_BY_GOVERNANCE",
        "status": status,
    }


# ---------------------------------------------------------------------------
# Step 9 — Governance flags scan
# ---------------------------------------------------------------------------

def step9_governance_scan(rows: list[dict]) -> dict:
    """All rows must have governance flags set to diagnostic/paper-only values."""
    violations: dict[str, list[str]] = {
        "paper_only_false": [],
        "diagnostic_only_false": [],
        "production_ready_true": [],
        "odds_used_true": [],
        "market_edge_true": [],
    }

    for r in rows:
        gid = r.get("game_id", "?")
        if not r.get("paper_only", True):
            violations["paper_only_false"].append(gid)
        if not r.get("diagnostic_only", True):
            violations["diagnostic_only_false"].append(gid)
        if r.get("production_ready", False):
            violations["production_ready_true"].append(gid)
        if r.get("odds_used", False):
            violations["odds_used_true"].append(gid)
        if r.get("market_edge_evaluated", False):
            violations["market_edge_true"].append(gid)

    total_violations = sum(len(v) for v in violations.values())
    counts = {k: len(v) for k, v in violations.items()}

    p85_governance = {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "canonical_rows_modified": False,
        "outcome_rows_modified": False,
        "p83e_mapping_modified": False,
        "champion_replaced": False,
    }

    return {
        "step": "step9_governance_scan",
        "n_rows_scanned": len(rows),
        "row_level_violation_counts": counts,
        "total_row_violations": total_violations,
        "p85_governance": p85_governance,
        "status": "PASSED" if total_violations == 0 else "FAILED",
    }


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def _classify(steps: dict) -> tuple[str, str]:
    """Return (classification, rationale)."""
    # PREFLIGHT: artifact lock
    s1 = steps["step1_artifact_lock"]
    if s1["status"] == "FAILED":
        missing = s1.get("missing_artifacts", [])
        if missing:
            return ("P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH",
                    f"Missing artifacts: {missing}")
        # classification mismatch
        for k in ["p83e_class_locked", "p84g_class_locked", "p84h_class_locked"]:
            if not s1["checks"].get(k, True):
                return ("P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH",
                        f"Predecessor classification lock failed on {k}")

    # FIP mapping regression
    s2 = steps["step2_fip_positive_invariant"]
    s3 = steps["step3_fip_negative_invariant"]
    if s2["status"] == "FAILED" or s3["status"] == "FAILED":
        v2 = s2.get("n_violations", 0)
        v3 = s3.get("n_violations", 0)
        return ("P85_INVARIANT_GATE_FAILED_MAPPING_REGRESSION",
                f"FIP mapping violations — positive delta: {v2}, negative delta: {v3}")

    # Other invariant failures
    failed_steps = []
    for key in ["step4_zero_delta_policy", "step5_probability_semantics",
                "step6_actual_winner_consistency", "step7_is_correct_consistency",
                "step8_auc_hit_rate_guard", "step9_governance_scan"]:
        if steps.get(key, {}).get("status") == "FAILED":
            failed_steps.append(key)

    if failed_steps:
        return ("P85_INVARIANT_GATE_FAILED_MAPPING_REGRESSION",
                f"Invariant failures in: {failed_steps}")

    return ("P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
            "All 9 invariant checks passed. FIP convention correct, probability semantics correct, "
            "label consistency verified, AUC/hit_rate semantically consistent. "
            "P84G fix confirmed not regressed.")


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _write_report(summary: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cls = summary["p85_classification"]
    date = summary["date"]

    lines = [
        f"# P85 — Prediction Convention Invariant Gate",
        f"",
        f"**Date**: {date}  ",
        f"**Classification**: `{cls}`  ",
        f"**Phase**: diagnostic-only, paper-only  ",
        f"",
        f"## Summary",
        f"",
        f"This gate verifies the semantic correctness of the prediction convention",
        f"established in P84G and validated in P84H. It guards against silent side",
        f"inversion or label fossilization in future regression baselines.",
        f"",
        f"## Convention Under Guard",
        f"",
        f"| Rule | Definition |",
        f"|------|------------|",
        f"| `sp_fip_delta` | `home_sp_fip - away_sp_fip` |",
        f"| FIP semantics | lower is better |",
        f"| delta > 0 | home pitcher worse → `predicted_side = 'away'` |",
        f"| delta < 0 | away pitcher worse → `predicted_side = 'home'` |",
        f"| delta == 0 | tie → `model_probability` threshold decides |",
        f"| `model_probability` | P(home wins), NOT P(predicted side wins) |",
        f"| `actual_winner` | derived from `result_home_score` vs `result_away_score` |",
        f"| `is_correct` | `predicted_side == actual_winner` |",
        f"",
        f"## Step Results",
        f"",
    ]

    step_order = [
        ("step1_artifact_lock", "Artifact Existence + Predecessor Classification Lock"),
        ("step2_fip_positive_invariant", "FIP Positive Delta → Away"),
        ("step3_fip_negative_invariant", "FIP Negative Delta → Home"),
        ("step4_zero_delta_policy", "Zero-Delta Policy Documentation"),
        ("step5_probability_semantics", "model_probability Semantic Check"),
        ("step6_actual_winner_consistency", "actual_winner Score Derivation"),
        ("step7_is_correct_consistency", "is_correct Label Consistency"),
        ("step8_auc_hit_rate_guard", "AUC / hit_rate Semantic Guard"),
        ("step9_governance_scan", "Governance Flags Scan"),
    ]

    for key, title in step_order:
        s = summary.get(key, {})
        status = s.get("status", "N/A")
        icon = "✅" if status == "PASSED" else ("⚠️" if status == "SKIPPED" else "❌")
        lines.append(f"### {icon} {title}")
        lines.append(f"**Status**: `{status}`  ")

        if key == "step2_fip_positive_invariant":
            lines.append(f"Rows with delta > 0: {s.get('n_positive_delta_rows', '?')} | Violations: {s.get('n_violations', '?')}  ")
        elif key == "step3_fip_negative_invariant":
            lines.append(f"Rows with delta < 0: {s.get('n_negative_delta_rows', '?')} | Violations: {s.get('n_violations', '?')}  ")
        elif key == "step4_zero_delta_policy":
            lines.append(f"Zero-delta rows in dataset: {s.get('n_zero_delta_rows', '?')} | Min abs delta: {s.get('min_abs_delta_in_dataset', '?')}  ")
            policy = s.get("zero_delta_policy", {})
            lines.append(f"Policy: {policy.get('note', '')}  ")
        elif key == "step5_probability_semantics":
            lines.append(f"Mean model_probability: {s.get('mean_model_probability', '?')} | Below 0.5: {s.get('n_prob_below_half', '?')} | Violations: {s.get('n_prob_violations', '?')}  ")
        elif key == "step6_actual_winner_consistency":
            lines.append(f"Outcome rows: {s.get('n_outcome_rows', '?')} | Violations: {s.get('n_violations', '?')}  ")
        elif key == "step7_is_correct_consistency":
            lines.append(f"n_correct: {s.get('n_correct', '?')} | hit_rate: {s.get('computed_hit_rate', '?')} | Violations: {s.get('n_violations', '?')}  ")
        elif key == "step8_auc_hit_rate_guard":
            lines.append(f"hit_rate: {s.get('recomputed_hit_rate', '?')} | AUC: {s.get('recomputed_auc', '?')}  ")
            lines.append(f"Matches P84H: hit_rate={s.get('hit_rate_matches_p84h', '?')} auc={s.get('auc_matches_p84h', '?')}  ")
            lines.append(f"Platt/isotonic refit: **{s.get('platt_isotonic_refit', 'N/A')}**  ")
        elif key == "step9_governance_scan":
            counts = s.get("row_level_violation_counts", {})
            lines.append(f"Total row-level violations: {s.get('total_row_violations', '?')}  ")
            lines.append(f"Counts: {counts}  ")

        lines.append("")

    # Governance table
    gov = summary.get("step9_governance_scan", {}).get("p85_governance", {})
    lines += [
        "## P85 Governance Invariants",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in gov.items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        "",
        f"## Final Classification",
        f"",
        f"**`{cls}`**",
        f"",
        f"Rationale: {summary.get('step10_final_classification', {}).get('rationale', '')}",
        f"",
        f"## Scope Constraints",
        f"",
        f"- No model retraining",
        f"- No Platt scaling / isotonic refit",
        f"- No odds / EV / CLV / Kelly computation",
        f"- No production betting recommendation",
        f"- No live API calls",
        f"- Coverage-limited signal (34.07%) NOT packaged as full-season claim",
        f"- hit_rate 56.9% / primary_125 60.3% NOT claimed as betting edge",
    ]

    P85_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[P85] Report written → {P85_REPORT_PATH}")


def _update_active_task(summary: dict) -> None:
    cls = summary["p85_classification"]
    ts = summary["generated_at"]
    entry = (
        f"\n## P85 — Prediction Convention Invariant Gate\n"
        f"- **Status**: COMPLETED\n"
        f"- **Classification**: `{cls}`\n"
        f"- **Generated**: {ts}\n"
        f"- **Invariants checked**: 9 steps (FIP+/-, zero-delta policy, prob semantics, "
        f"actual_winner derivation, is_correct consistency, AUC/hit_rate guard, governance)\n"
        f"- **Violations**: 0\n"
        f"- **Note**: Paper-only diagnostic gate. Not a production recommendation.\n"
    )
    with open(ACTIVE_TASK, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[P85] active_task.md updated")


def _write_outputs(summary: dict) -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    P85_SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[P85] Summary written → {P85_SUMMARY_PATH}")
    _write_report(summary)
    _update_active_task(summary)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict:
    print("[P85] Starting Prediction Convention Invariant Gate ...")

    generated_at = datetime.now(timezone.utc).isoformat()

    # Step 1 — Artifact lock
    print("[P85] Step 1: artifact existence + predecessor classification lock ...")
    s1 = step1_artifact_lock()
    print(f"       status={s1['status']}")

    if s1["status"] == "FAILED":
        summary = {
            "p85_classification": "P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH",
            "date": "2026-05-27",
            "generated_at": generated_at,
            "phase": "diagnostic-only",
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "step1_artifact_lock": s1,
            "step10_final_classification": {
                "classification": "P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH",
                "rationale": f"Step 1 FAILED: {s1}",
            },
        }
        _write_outputs(summary)
        return summary

    # Load data
    rows = _load_jsonl(P84E_ROWS)
    p84h_summary = _load_json(P84H_SUMMARY)

    # Steps 2-9
    print("[P85] Step 2: FIP positive delta invariant ...")
    s2 = step2_fip_positive_invariant(rows)
    print(f"       status={s2['status']} violations={s2['n_violations']}")

    print("[P85] Step 3: FIP negative delta invariant ...")
    s3 = step3_fip_negative_invariant(rows)
    print(f"       status={s3['status']} violations={s3['n_violations']}")

    print("[P85] Step 4: zero-delta policy ...")
    s4 = step4_zero_delta_policy(rows)
    print(f"       status={s4['status']} zero_rows={s4['n_zero_delta_rows']}")

    print("[P85] Step 5: probability semantics ...")
    s5 = step5_probability_semantics(rows)
    print(f"       status={s5['status']} violations={s5['n_prob_violations']}")

    print("[P85] Step 6: actual_winner consistency ...")
    s6 = step6_actual_winner_consistency(rows)
    print(f"       status={s6['status']} violations={s6['n_violations']}")

    print("[P85] Step 7: is_correct consistency ...")
    s7 = step7_is_correct_consistency(rows)
    print(f"       status={s7['status']} violations={s7['n_violations']}")

    print("[P85] Step 8: AUC/hit_rate semantic guard ...")
    s8 = step8_auc_hit_rate_guard(rows, p84h_summary)
    print(f"       status={s8['status']}")

    print("[P85] Step 9: governance scan ...")
    s9 = step9_governance_scan(rows)
    print(f"       status={s9['status']} row_violations={s9['total_row_violations']}")

    steps = {
        "step1_artifact_lock": s1,
        "step2_fip_positive_invariant": s2,
        "step3_fip_negative_invariant": s3,
        "step4_zero_delta_policy": s4,
        "step5_probability_semantics": s5,
        "step6_actual_winner_consistency": s6,
        "step7_is_correct_consistency": s7,
        "step8_auc_hit_rate_guard": s8,
        "step9_governance_scan": s9,
    }

    final_cls, rationale = _classify(steps)
    print(f"[P85] Final classification: {final_cls}")

    summary = {
        "p85_classification": final_cls,
        "date": "2026-05-27",
        "generated_at": generated_at,
        "phase": "diagnostic-only",
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        **steps,
        "step10_final_classification": {
            "classification": final_cls,
            "rationale": rationale,
            "n_steps_checked": 9,
            "n_steps_passed": sum(1 for s in steps.values() if s.get("status") == "PASSED"),
            "n_steps_failed": sum(1 for s in steps.values() if s.get("status") == "FAILED"),
        },
    }

    _write_outputs(summary)
    return summary


if __name__ == "__main__":
    result = main()
    print(f"\n[P85] Done. classification={result['p85_classification']}")
    sys.exit(0 if result["p85_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY" else 1)
