"""
P277A — Historical Observation Status Reclassification Audit

Deterministic, read-only audit of all committed historical strategy-cell and
P276B portfolio evidence under the Owner's revised DUAL-GATE rule:

  GATE 1 (retention): beating the governed RANDOM baseline is SUFFICIENT to
          retain a strategy/portfolio as an OBSERVATION CANDIDATE.
  GATE 2 (promotion):  beating the BEST EQUAL-BUDGET strategy is a STRONGER
          priority/promotion criterion — NOT the minimum retention criterion.

FORBIDDEN INTERFACES (statically verified by test):
  - sqlite3 / DB open / write
  - requests / urllib / socket / subprocess / os.system
  - any registry / production mutation

DETERMINISM
-----------
Two regenerations yield byte-identical JSON (except possibly generated_at)
and identical canonical_payload_digest.  Wall-clock time is EXCLUDED from
the digest.

ALLOWED FILE WHITELIST (four files only):
  analysis/p277a_historical_observation_status_reclassification.py
  tests/test_p277a_historical_observation_status_reclassification.py
  outputs/research/p277a_historical_observation_status_reclassification_20260617.json
  outputs/research/p277a_historical_observation_status_reclassification_20260617.md
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance constants
# ---------------------------------------------------------------------------

TASK_ID = "P277A_HISTORICAL_OBSERVATION_STATUS_RECLASSIFICATION_AUDIT"
DATE_CONSTANT = "2026-06-17"
GENERATED_AT_PINNED = "2026-06-17T00:00:00+00:00"
SOURCE_COMMIT = "b6dd42f14e822a186187b90c50acdfedebe3fd07"

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs" / "research"

# ---------------------------------------------------------------------------
# Source artifact manifest (deterministic)
# ---------------------------------------------------------------------------

SOURCE_ARTIFACTS = {
    "p222": OUTPUTS / "p222_cross_lottery_feature_discovery_scan_20260603.json",
    "p223b": OUTPUTS / "p223b_candidate_oos_cross_year_validation_20260603.json",
    "p224": OUTPUTS / "p224_daily539_midfreq_fourier_2bet_deeper_validation_20260603.json",
    "p224b": OUTPUTS / "p224b_daily539_survivor_future_oos_monitoring_protocol_20260603.json",
    "p227c": OUTPUTS / "p227c_star_box_play_dryrun_scan_20260603.json",
    "p230b1": OUTPUTS / "p230b1_daily539_backward_oos_dryrun_20260603.json",
    "p231b": OUTPUTS / "p231b_powerlotto_first_zone_backward_oos_dryrun_20260604.json",
    "p267c": OUTPUTS / "p267c_m3plus_strategy_revalidation_20260610.json",
    "p273a_identity": OUTPUTS / "p273a_distinct_ticket_identity_20260615.json",
    "p273a_primary": OUTPUTS / "p273a_primary_window_observed_counts_20260615.json",
    "p273a_inferential": OUTPUTS / "p273a_prize_aware_inferential_validation_20260615.json",
    "p273a_prizeaware_ref": OUTPUTS / "p273a_prizeaware_observed_counts_20260614.json",
    "p275b": OUTPUTS / "p275b_unified_prize_aware_success_matrix_20260616.json",
    "p276b": OUTPUTS / "p276b_fixed_n_coverage_complementarity_20260617.json",
    "p252c": OUTPUTS / "p252c_baseline_calculator_ssot_20260607.json",
    "p252d": OUTPUTS / "p252d_correction_gate_ssot_20260607.json",
    "p252e": OUTPUTS / "p252e_permutation_test_ssot_20260607.json",
    "p252f": OUTPUTS / "p252f_rolling_window_statistics_ssot_20260607.json",
}

# ---------------------------------------------------------------------------
# Classification taxonomy (verbatim from spec)
# ---------------------------------------------------------------------------

TAXONOMY = [
    "OBSERVATION_POTENTIAL_ABOVE_RANDOM",
    "OBSERVATION_SUPPORTED_ABOVE_RANDOM",
    "COMPETITIVE_OBSERVATION_STRATEGY",
    "STRONG_RESEARCH_CANDIDATE",
    "UNDERPOWERED_OBSERVATION_POTENTIAL",
    "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL",
    "NO_EVIDENCE_OVER_RANDOM",
    "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE",
    "INSUFFICIENT_SUPPORT",
    "NOT_APPLICABLE_ENDPOINT",
]

# Evidence precedence levels
EVIDENCE_PRECEDENCE = {
    1: "future-only/genuinely-independent OOS",
    2: "backward-OOS/walk-forward",
    3: "corrected exact inference",
    4: "corrected retrospective inference",
    5: "descriptive w/ valid random baseline",
    6: "point estimate w/ valid baseline",
    7: "no valid baseline",
}

# ---------------------------------------------------------------------------
# Utility: SHA-256 hash a committed JSON artifact
# ---------------------------------------------------------------------------

def sha256_artifact(path: Path) -> str:
    """Return hex SHA-256 of the committed artifact bytes."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def build_artifact_hashes() -> dict:
    """Hash all source artifacts deterministically."""
    hashes = {}
    for key, path in sorted(SOURCE_ARTIFACTS.items()):
        if path.exists():
            hashes[key] = sha256_artifact(path)
        else:
            hashes[key] = "MISSING"
    return hashes


def verify_artifact_hashes(hashes: dict) -> list[str]:
    """Return list of missing artifact keys."""
    return [k for k, v in hashes.items() if v == "MISSING"]


# ---------------------------------------------------------------------------
# Load all source data
# ---------------------------------------------------------------------------

def load_all_sources() -> dict:
    sources = {}
    for key, path in SOURCE_ARTIFACTS.items():
        if path.exists():
            sources[key] = load_json(path)
        else:
            sources[key] = None
    return sources


# ---------------------------------------------------------------------------
# Helper: derive random baseline status
# ---------------------------------------------------------------------------

def _random_baseline_status(obs_rate, random_baseline, evidence_type: str) -> str:
    """
    Returns 'ABOVE_RANDOM', 'AT_OR_BELOW_RANDOM', 'UNKNOWN_BASELINE', or
    'INSUFFICIENT_SUPPORT'.
    """
    if obs_rate is None or random_baseline is None:
        if evidence_type == "INSUFFICIENT_SUPPORT":
            return "INSUFFICIENT_SUPPORT"
        return "UNKNOWN_BASELINE"
    if obs_rate > random_baseline:
        return "ABOVE_RANDOM"
    return "AT_OR_BELOW_RANDOM"


def _corrected_support_status(p_corr, p_value, obs_above_random: bool) -> str:
    """
    Returns 'CORRECTED_SIGNIFICANT', 'DESCRIPTIVE_ONLY', 'NULL', or
    'NO_INFERENCE_PERFORMED'.
    """
    if p_corr is None and p_value is None:
        return "NO_INFERENCE_PERFORMED"
    if p_corr is not None:
        if p_corr < 0.05 and obs_above_random:
            return "CORRECTED_SIGNIFICANT"
        if p_corr >= 0.05 and obs_above_random:
            return "DESCRIPTIVE_ONLY_ABOVE_RANDOM"
        return "CORRECTED_NULL"
    if p_value is not None:
        if p_value < 0.05 and obs_above_random:
            return "UNCORRECTED_SIGNIFICANT_ONLY"
        return "UNCORRECTED_NULL"
    return "NO_INFERENCE_PERFORMED"


# ---------------------------------------------------------------------------
# Core classification function under dual-gate rule
# ---------------------------------------------------------------------------

def classify_record(
    *,
    random_baseline_status: str,
    corrected_support_status: str,
    oos_status: str,
    original_classification: str,
    evidence_level: int,  # 1..7 per EVIDENCE_PRECEDENCE
    has_valid_baseline: bool,
    support_adequate: bool,
) -> str:
    """
    Apply the Owner dual-gate rule deterministically.

    Returns one of the TAXONOMY labels.
    """
    # No valid baseline at all
    if not has_valid_baseline:
        return "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"

    # Insufficient support (e.g. < 30 draws, < 5 expected successes)
    if not support_adequate:
        return "INSUFFICIENT_SUPPORT"

    # OOS superseded
    if oos_status == "OOS_NULL":
        return "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"

    # Below random
    if random_baseline_status == "AT_OR_BELOW_RANDOM":
        return "NO_EVIDENCE_OVER_RANDOM"

    # Below random (unknown / no inference)
    if random_baseline_status in ("UNKNOWN_BASELINE", "INSUFFICIENT_SUPPORT"):
        return "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"

    # Above random: apply dual-gate
    # Gate 1 PASSED (above random).  Now classify strength:
    if corrected_support_status == "CORRECTED_SIGNIFICANT":
        if oos_status == "OOS_POSITIVE":
            return "STRONG_RESEARCH_CANDIDATE"
        return "OBSERVATION_SUPPORTED_ABOVE_RANDOM"

    if corrected_support_status in ("DESCRIPTIVE_ONLY_ABOVE_RANDOM",
                                    "UNCORRECTED_SIGNIFICANT_ONLY"):
        if evidence_level <= 2:
            # Backward-OOS or better — strong
            return "OBSERVATION_SUPPORTED_ABOVE_RANDOM"
        return "OBSERVATION_POTENTIAL_ABOVE_RANDOM"

    # Corrected NULL but still above random (point estimate only)
    if corrected_support_status in ("CORRECTED_NULL", "NO_INFERENCE_PERFORMED",
                                    "UNCORRECTED_NULL"):
        if evidence_level <= 4:
            return "UNDERPOWERED_OBSERVATION_POTENTIAL"
        return "OBSERVATION_POTENTIAL_ABOVE_RANDOM"

    return "NO_EVIDENCE_OVER_RANDOM"


# ---------------------------------------------------------------------------
# Build strategy records from P275B (primary source of truth for 36 cells)
# ---------------------------------------------------------------------------

def _p275b_best_window_record(rows: list, lottery: str, strategy: str) -> dict | None:
    """
    Return the most informative window row for the given strategy cell
    from P275B matrix_rows.  Priority: LONG > MID > SHORT.
    """
    window_priority = {"LONG": 0, "MID": 1, "SHORT": 2}
    matching = [r for r in rows
                if r["lottery_type"] == lottery and r["strategy_id"] == strategy]
    if not matching:
        return None
    return min(matching, key=lambda r: window_priority.get(r["window_type"], 99))


def _p275b_window_stats(rows: list, lottery: str, strategy: str) -> list:
    """Return all windows for a given cell, sorted SHORT/MID/LONG."""
    order = {"SHORT": 0, "MID": 1, "LONG": 2}
    matching = [r for r in rows
                if r["lottery_type"] == lottery and r["strategy_id"] == strategy]
    return sorted(matching, key=lambda r: order.get(r["window_type"], 99))


def _infer_best_equal_budget_from_p275b(p275b_data: dict, lottery: str,
                                         strategy: str) -> dict:
    """
    For a given strategy, find the best-equal-budget comparator from P275B
    group_decisions (which records the stability_fail_reasons including
    constituent comparisons).
    """
    for gd in p275b_data.get("group_decisions", []):
        if gd["lottery_type"] == lottery and gd["strategy_id"] == strategy:
            return gd
    return {}


def _obs_above_best_eq(
    obs_rate: float | None,
    best_eq_rate: float | None,
) -> str:
    if obs_rate is None or best_eq_rate is None:
        return "UNKNOWN"
    if obs_rate > best_eq_rate:
        return "ABOVE_BEST_EQUAL_BUDGET"
    if abs(obs_rate - best_eq_rate) < 1e-9:
        return "EQUAL_TO_BEST_EQUAL_BUDGET"
    return "BELOW_BEST_EQUAL_BUDGET"


# ---------------------------------------------------------------------------
# Build the 36 strategy-cell records (P275B-sourced, P273A endpoints)
# ---------------------------------------------------------------------------

def build_strategy_records(sources: dict) -> list[dict]:
    """
    Build one record per (lottery_type, strategy_id) cell from the 36-cell
    frozen universe.  P275B is the canonical evidence source; P273A, P230B1,
    P231B, P224 augment the OOS picture.
    """
    p275b = sources["p275b"]
    p273a_inf = sources["p273a_inferential"]
    p230b1 = sources["p230b1"]
    p231b = sources["p231b"]
    p224 = sources["p224"]

    matrix_rows = p275b.get("matrix_rows", [])
    group_decisions = p275b.get("group_decisions", [])

    # Build per-group OOS augmentation:
    # P230B1: DAILY_539/midfreq_fourier_2bet backward-OOS → BELOW baseline (NULL)
    p230b1_status = "OOS_NULL"  # z=-0.32, p=0.626, direction=below

    # P231B: POWER_LOTTO/midfreq_fourier_mk_3bet backward-OOS → direction=above but p=0.302 (not significant)
    p231b_status = "OOS_INCONCLUSIVE"  # above baseline but p=0.302

    # P224: DAILY_539/midfreq_fourier_2bet full 1500-draw OOS → p=0.067 (not corrected-significant, needs more OOS)
    p224_status = "NEEDS_MORE_OOS"  # p=0.067, not corrected-significant

    records = []
    # Collect all cells from group_decisions (defines the 36-cell universe)
    for gd in group_decisions:
        lottery = gd["lottery_type"]
        strategy = gd["strategy_id"]
        lifecycle = gd["lifecycle_status"]
        group_dec = gd["overall_group_decision"]
        is_go_candidate = gd.get("is_go_candidate_research_only", False)
        stability = gd["stability_status"]

        # Get window-level rows
        win_rows = _p275b_window_stats(matrix_rows, lottery, strategy)

        # Determine best representative window for overall metrics
        best_row = _p275b_best_window_record(matrix_rows, lottery, strategy)

        if best_row is None:
            # This should not happen if P275B is well-formed
            continue

        # Extract metrics from LONG window if available, else best available
        long_rows = [r for r in win_rows if r["window_type"] == "LONG" and (r.get("eligible_draws") or 0) > 0]
        mid_rows = [r for r in win_rows if r["window_type"] == "MID" and (r.get("eligible_draws") or 0) > 0]
        short_rows = [r for r in win_rows if r["window_type"] == "SHORT" and (r.get("eligible_draws") or 0) > 0]

        # Pick primary row for metrics: prefer LONG, then MID, then SHORT
        primary_row = (long_rows[0] if long_rows else
                       mid_rows[0] if mid_rows else
                       short_rows[0] if short_rows else best_row)

        n = primary_row.get("eligible_draws", 0) or 0
        obs_success = primary_row.get("success_draws")
        obs_rate = (obs_success / n) if (n > 0 and obs_success is not None) else None
        baseline = primary_row.get("baseline_success_rate")
        abs_lift = primary_row.get("absolute_lift")
        p_value = primary_row.get("p_value")
        p_corr = primary_row.get("corrected_p_value")
        ev_status = primary_row.get("evidence_status", "")
        stat_status = primary_row.get("statistical_status", "")
        window_type = primary_row.get("window_type", "")
        ticket_budget = primary_row.get("ticket_budget", 1)

        # Determine support adequacy — at least one non-insufficient window
        support_adequate = (n >= 30) and (baseline is not None and
                            n * (baseline if baseline else 0) >= 5)
        has_valid_baseline = baseline is not None

        # Also check if ANY evaluable window has valid baseline (for POWER_LOTTO
        # strategies that have no prize-aware replay data at all)
        any_evaluable = any(
            (r.get("eligible_draws") or 0) >= 30
            and r.get("baseline_success_rate") is not None
            for r in win_rows
        )
        if not any_evaluable and not has_valid_baseline:
            support_adequate = False

        # Random baseline status
        # Use LONG window if available; otherwise use any available window
        # that has valid baseline (not INSUFFICIENT_SUPPORT)
        if not has_valid_baseline and not any_evaluable:
            rbs = "INSUFFICIENT_SUPPORT"
        elif all(
            r.get("evidence_status") == "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
            or (r.get("eligible_draws") or 0) == 0
            for r in win_rows
        ):
            rbs = "INSUFFICIENT_SUPPORT"
        elif obs_rate is not None and baseline is not None:
            rbs = "ABOVE_RANDOM" if obs_rate > baseline else "AT_OR_BELOW_RANDOM"
        else:
            rbs = "UNKNOWN_BASELINE"

        # Corrected support status — determined from ALL windows (any-window rule)
        # If ANY window has PRIZE_AWARE_EDGE_CORRECTION_SURVIVING, the group
        # has corrected support. This matches the P275B GO_CANDIDATE_RESEARCH_ONLY
        # designation which requires at least one surviving window.
        above_random = (obs_rate is not None and baseline is not None and
                        obs_rate > baseline)
        any_corrected_surviving = any(
            r.get("evidence_status") == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
            for r in win_rows
        )
        any_descriptive = any(
            r.get("evidence_status") == "PRIZE_AWARE_DESCRIPTIVE_ONLY"
            for r in win_rows
            if (r.get("eligible_draws") or 0) > 0
        )
        all_null_or_insufficient = all(
            r.get("evidence_status") in (
                "PRIZE_AWARE_NULL", "PRIZE_AWARE_INSUFFICIENT_SUPPORT",
                None, ""
            )
            for r in win_rows
        )
        all_insufficient = all(
            r.get("evidence_status") == "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
            or (r.get("eligible_draws") or 0) == 0
            for r in win_rows
        )

        # P275B group decision as primary signal
        if is_go_candidate or any_corrected_surviving:
            css = "CORRECTED_SIGNIFICANT"
        elif any_descriptive and not all_null_or_insufficient:
            css = "DESCRIPTIVE_ONLY_ABOVE_RANDOM"
        elif all_insufficient:
            css = "NO_INFERENCE_PERFORMED"
        elif above_random and all_null_or_insufficient:
            css = "CORRECTED_NULL"
        elif not above_random:
            css = "CORRECTED_NULL"
        else:
            css = "NO_INFERENCE_PERFORMED"

        # OOS status augmentation
        oos_status = "NO_OOS_AVAILABLE"
        if lottery == "DAILY_539" and strategy == "midfreq_fourier_2bet":
            # P230B1: backward-OOS is NULL (below baseline, p=0.626)
            oos_status = "OOS_NULL"
        elif lottery == "POWER_LOTTO" and strategy == "midfreq_fourier_mk_3bet":
            # P231B: backward-OOS above but p=0.302, inconclusive
            oos_status = "OOS_INCONCLUSIVE_ABOVE_RANDOM"

        # Determine evidence_level for classification
        if oos_status == "OOS_NULL":
            evidence_level = 2  # backward-OOS (but NULL)
        elif oos_status == "OOS_INCONCLUSIVE_ABOVE_RANDOM":
            evidence_level = 2  # backward-OOS
        elif css == "CORRECTED_SIGNIFICANT":
            evidence_level = 4  # corrected retrospective inference
        elif css == "DESCRIPTIVE_ONLY_ABOVE_RANDOM":
            evidence_level = 5  # descriptive with valid random baseline
        elif css == "CORRECTED_NULL" and above_random:
            evidence_level = 6  # point estimate with valid baseline
        elif not has_valid_baseline:
            evidence_level = 7
        else:
            evidence_level = 6

        # Apply dual-gate classification
        current_mapping = classify_record(
            random_baseline_status=rbs,
            corrected_support_status=css,
            oos_status=oos_status,
            original_classification=group_dec,
            evidence_level=evidence_level,
            has_valid_baseline=has_valid_baseline,
            support_adequate=support_adequate,
        )

        # Best equal-budget comparator: within P275B matrix
        # For single strategies, we compare against the best LONG-window performance
        # among same lottery_type strategies with the same bet budget
        best_eq_budget_comparator = _find_best_equal_budget(
            matrix_rows, lottery, ticket_budget, strategy,
            group_decisions
        )
        best_eq_strat = best_eq_budget_comparator.get("strategy_id", "N/A")
        best_eq_rate = best_eq_budget_comparator.get("success_rate")
        delta_vs_best_eq = (
            round((obs_rate - best_eq_rate), 6)
            if (obs_rate is not None and best_eq_rate is not None)
            else None
        )
        best_eq_status = _obs_above_best_eq(obs_rate, best_eq_rate)

        # Stability windows
        windows_available = sorted({r.get("window_type") for r in win_rows
                                     if (r.get("eligible_draws") or 0) > 0})

        # Determine observation_retention (Gate 1)
        observation_retention = (rbs == "ABOVE_RANDOM" and support_adequate and
                                  oos_status != "OOS_NULL")

        # Reclassification reason
        reason = _build_reclassification_reason(
            group_dec, current_mapping, rbs, css, oos_status,
            is_go_candidate, lottery, strategy
        )

        record = {
            "identity": f"{lottery}/{strategy}",
            "lottery_type": lottery,
            "strategy_id": strategy,
            "endpoint": _endpoint_for_lottery(lottery),
            "bet_budget": ticket_budget,
            "windows_available": windows_available,
            "evidence_family": "PRIZE_AWARE_RETROSPECTIVE_CORRECTED",
            "original_classification": group_dec,
            "original_source_artifacts": ["p275b", "p273a_inferential",
                                           "p273a_primary", "p273a_identity",
                                           "p267c"],
            "source_metrics": {
                "primary_window": window_type,
                "n_draws": n,
                "observed_success_rate": obs_rate,
                "observed_successes": obs_success,
                "p_value": p_value,
                "p_bonferroni_corrected": p_corr,
                "evidence_status_p275b": ev_status,
                "statistical_status_p275b": stat_status,
                "lifecycle_status": lifecycle,
                "stability_status": stability,
                "is_go_candidate_research_only": is_go_candidate,
            },
            "baseline_type": "GOVERNED_EXACT_DISTINCT_TICKET_RANDOM_NULL",
            "random_baseline_value": baseline,
            "observed_value": obs_rate,
            "delta_vs_random": round(abs_lift, 6) if abs_lift is not None else None,
            "random_baseline_status": rbs,
            "corrected_support_status": css,
            "stability_status": stability,
            "OOS_status": oos_status,
            "best_equal_budget_comparator": best_eq_strat,
            "delta_vs_best_equal_budget": delta_vs_best_eq,
            "best_equal_budget_status": best_eq_status,
            "observation_retention_status": (
                "OBSERVATION_RETAINED" if observation_retention
                else "OBSERVATION_NOT_RETAINED"
            ),
            "promotion_status": "NOT_PROMOTED",
            "future_confirmation_status": "FUTURE_CONFIRMATION_PENDING",
            "evidence_completeness": "RETROSPECTIVE_ONLY" if oos_status == "NO_OOS_AVAILABLE" else "INCLUDES_OOS",
            "current_mapping": current_mapping,
            "reclassification_reason": reason,
            "historical_artifact_unchanged": True,
            "limitations": _limitations_for(lottery, strategy, oos_status,
                                            current_mapping),
        }
        records.append(record)

    return records


def _endpoint_for_lottery(lottery: str) -> str:
    endpoints = {
        "DAILY_539": "D539_ANY_PRIZE_AWARE_WIN (hit_count >= 2)",
        "BIG_LOTTO": "BIG_ANY_PRIZE_AWARE_WIN (hit_count >= 3 OR (hit_count=2 AND special_hit=1))",
        "POWER_LOTTO": "POWER_ANY_PRIZE_AWARE_WIN (hit_count >= 3 OR (hit_count >= 1 AND special_hit=1))",
    }
    return endpoints.get(lottery, "UNKNOWN_ENDPOINT")


def _find_best_equal_budget(matrix_rows: list, lottery: str,
                             ticket_budget: int, exclude_strategy: str,
                             group_decisions: list) -> dict:
    """
    Find best LONG-window performance for same lottery + same ticket_budget,
    excluding the current strategy.  Uses P275B matrix_rows.
    """
    candidates = []
    for r in matrix_rows:
        if (r["lottery_type"] == lottery
                and r["strategy_id"] != exclude_strategy
                and r["window_type"] == "LONG"
                and r.get("ticket_budget") == ticket_budget
                and (r.get("eligible_draws") or 0) >= 30
                and r.get("baseline_success_rate") is not None):
            n = r.get("eligible_draws", 0) or 0
            obs = r.get("success_draws", 0) or 0
            rate = obs / n if n > 0 else None
            if rate is not None:
                candidates.append({
                    "strategy_id": r["strategy_id"],
                    "success_rate": rate,
                    "eligible_draws": n,
                    "evidence_status": r.get("evidence_status"),
                })
    if not candidates:
        # No same-budget comparator found; return empty
        return {"strategy_id": "NO_EQUAL_BUDGET_COMPARATOR", "success_rate": None}
    # Best = highest success rate
    return max(candidates, key=lambda c: c["success_rate"] or 0)


def _build_reclassification_reason(
    original: str, current: str, rbs: str, css: str,
    oos_status: str, is_go_candidate: bool,
    lottery: str, strategy: str
) -> str:
    parts = []
    if oos_status == "OOS_NULL":
        parts.append(
            f"P230B1 backward-OOS evidence (4265 draws) showed mean below "
            f"baseline (z=-0.32, p=0.626). Under dual-gate rule, earlier "
            f"in-window observation is superseded by OOS null."
        )
    elif oos_status == "OOS_INCONCLUSIVE_ABOVE_RANDOM":
        parts.append(
            f"P231B backward-OOS evidence (382 draws) showed direction=above "
            f"but p=0.302. Inconclusive — retains OBSERVATION_POTENTIAL."
        )

    if rbs == "ABOVE_RANDOM":
        parts.append(
            f"Beats governed random baseline (GATE 1 PASS). "
            f"Observation retention applies."
        )
    elif rbs == "AT_OR_BELOW_RANDOM":
        parts.append("Does NOT beat random baseline (GATE 1 FAIL).")
    elif rbs == "INSUFFICIENT_SUPPORT":
        parts.append("Insufficient draws/expected successes for valid inference.")

    if css == "CORRECTED_SIGNIFICANT":
        parts.append("Bonferroni-corrected p < 0.05 in at least one primary window.")
    elif css == "DESCRIPTIVE_ONLY_ABOVE_RANDOM":
        parts.append("Above random but corrected p >= 0.05; descriptive evidence only.")
    elif css == "CORRECTED_NULL":
        parts.append("Corrected p >= 0.05; null result under correction.")

    if is_go_candidate:
        parts.append(
            "P273A/P275B designated GO_CANDIDATE_RESEARCH_ONLY: "
            "retrospective corrected-inference evidence survives Bonferroni correction "
            "in at least one primary window. Prediction success NOT claimed; "
            "strategy NOT promoted; future confirmation required."
        )

    if original != current:
        parts.append(
            f"Original P275B group decision '{original}' remapped to "
            f"'{current}' under Owner dual-gate rule."
        )
    else:
        parts.append(f"Classification consistent with original P275B decision '{original}'.")

    return " | ".join(parts)


def _limitations_for(lottery: str, strategy: str, oos_status: str,
                      current_mapping: str) -> list[str]:
    lims = [
        "Retrospective evidence only; all draws within the frozen in-window period.",
        "No future-only/genuinely-independent confirmatory evidence available.",
        "No strategy promotion, no registry mutation, no DB write.",
        "Prize-tier semantics carry source_verification_status=MANUAL_VERIFICATION_REQUIRED (P271B/P271C).",
        "Correction family size=108 (36 cells x 3 windows); Bonferroni per-test alpha=0.000463.",
        "prediction_success_claim=false; strategy_promoted=false.",
    ]
    if oos_status == "OOS_NULL":
        lims.append(
            "P230B1 backward-OOS NULL evidence supersedes earlier in-window estimate."
        )
    elif oos_status == "OOS_INCONCLUSIVE_ABOVE_RANDOM":
        lims.append(
            "P231B backward-OOS is above random but not statistically significant (p=0.302). "
            "Inconclusive. Additional OOS required."
        )
    if lottery == "POWER_LOTTO" and strategy in (
            "fourier_rhythm_3bet", "power_fourier_rhythm_2bet",
            "power_orthogonal_5bet", "power_precision_3bet"):
        lims.append(
            "No prize-aware replay data available for this POWER_LOTTO strategy; "
            "classified INSUFFICIENT_SUPPORT."
        )
    return lims


# ---------------------------------------------------------------------------
# Build P276B portfolio records
# ---------------------------------------------------------------------------

def build_portfolio_records(sources: dict) -> list[dict]:
    """
    Build one record per P276B portfolio.  Each portfolio includes:
    - vs ordinary random baseline
    - vs diversified random baseline
    - vs each constituent
    - vs best equal-budget constituent
    - observation-retention eligibility
    """
    p276b = sources["p276b"]
    if p276b is None:
        return []

    scientific_verdict = p276b.get("scientific_verdict",
                                    "NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE")
    portfolio_results = p276b.get("portfolio_results", [])
    records = []

    for pr in portfolio_results:
        pid = pr["portfolio_id"]
        lottery = pr["lottery_type"]
        budget = pr["ticket_budget"]
        kind = pr["kind"]
        source_cells = pr.get("source_cells", [])
        eq_budget_constituents = pr.get("equal_budget_constituents", [])

        # Aggregate across windows: use LONG (750) window as primary
        windows = pr.get("windows", [])
        long_wins = [w for w in windows if w.get("support_draws", 0) == 750]
        mid_wins = [w for w in windows if w.get("support_draws", 0) == 300]
        short_wins = [w for w in windows if w.get("support_draws", 0) == 50]

        primary_win = (long_wins[0] if long_wins else
                       mid_wins[0] if mid_wins else
                       short_wins[0] if windows else None)

        if primary_win is None:
            records.append({
                "identity": f"PORTFOLIO:{pid}",
                "portfolio_id": pid,
                "lottery_type": lottery,
                "ticket_budget": budget,
                "kind": kind,
                "source_cells": source_cells,
                "equal_budget_constituents": eq_budget_constituents,
                "current_mapping": "INSUFFICIENT_SUPPORT",
                "promotion_status": "NOT_PROMOTED",
                "scientific_verdict_preserved": scientific_verdict,
                "limitations": ["No window data available."],
            })
            continue

        pa = primary_win.get("prize_aware", {})
        obs_rate = pa.get("union_success_rate")
        ord_base = pa.get("random_baselines", {}).get("ordinary", {}).get(
            "baseline_union_win_probability")
        div_base = pa.get("random_baselines", {}).get("diversified", {}).get(
            "baseline_union_win_probability")
        ord_p = pa.get("random_baselines", {}).get("ordinary", {}).get(
            "mc_p_value_one_sided_upper")
        div_p = pa.get("random_baselines", {}).get("diversified", {}).get(
            "mc_p_value_one_sided_upper")
        best_eq = pa.get("best_equal_budget_constituent", {})
        best_eq_strat = best_eq.get("strategy_id", "N/A")
        best_eq_rate = best_eq.get("union_success_rate")
        mcnemar_p = best_eq.get("mcnemar_p_value_exact")

        # Random baseline status
        ord_rbs = ("ABOVE_RANDOM" if (obs_rate is not None and ord_base is not None
                                       and obs_rate > ord_base)
                   else "AT_OR_BELOW_RANDOM" if obs_rate is not None and ord_base is not None
                   else "UNKNOWN_BASELINE")
        div_rbs = ("ABOVE_RANDOM" if (obs_rate is not None and div_base is not None
                                       and obs_rate > div_base)
                   else "AT_OR_BELOW_RANDOM" if obs_rate is not None and div_base is not None
                   else "UNKNOWN_BASELINE")

        # Best equal-budget status
        best_eq_status = _obs_above_best_eq(obs_rate, best_eq_rate)

        # Classify portfolio
        n = primary_win.get("support_draws", 0)
        support_ok = n >= 30

        # Classification: use ordinary baseline as the random baseline
        if not support_ok:
            current_mapping = "INSUFFICIENT_SUPPORT"
        elif ord_rbs == "AT_OR_BELOW_RANDOM":
            current_mapping = "NO_EVIDENCE_OVER_RANDOM"
        elif ord_rbs == "ABOVE_RANDOM":
            # Gate 1 pass
            if ord_p is not None and ord_p < 0.05:
                if div_rbs == "ABOVE_RANDOM" and div_p is not None and div_p < 0.05:
                    current_mapping = "OBSERVATION_SUPPORTED_ABOVE_RANDOM"
                else:
                    current_mapping = "OBSERVATION_POTENTIAL_ABOVE_RANDOM"
            else:
                current_mapping = "OBSERVATION_POTENTIAL_ABOVE_RANDOM"
        else:
            current_mapping = "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE"

        # Collect window summaries
        win_summaries = []
        for w in windows:
            wpa = w.get("prize_aware", {})
            wm3 = w.get("m3_plus", {})
            win_ord_p = wpa.get("random_baselines", {}).get("ordinary", {}).get(
                "mc_p_value_one_sided_upper")
            win_div_p = wpa.get("random_baselines", {}).get("diversified", {}).get(
                "mc_p_value_one_sided_upper")
            win_best_eq = wpa.get("best_equal_budget_constituent", {})
            win_summaries.append({
                "n_draws": w.get("support_draws"),
                "prize_aware_obs_rate": wpa.get("union_success_rate"),
                "ordinary_random_baseline": wpa.get("random_baselines", {}).get(
                    "ordinary", {}).get("baseline_union_win_probability"),
                "diversified_random_baseline": wpa.get("random_baselines", {}).get(
                    "diversified", {}).get("baseline_union_win_probability"),
                "ordinary_p_value": win_ord_p,
                "diversified_p_value": win_div_p,
                "best_eq_constituent_rate": win_best_eq.get("union_success_rate"),
                "mcnemar_p_vs_best_eq": win_best_eq.get("mcnemar_p_value_exact"),
                "portfolio_vs_best_eq": _obs_above_best_eq(
                    wpa.get("union_success_rate"),
                    win_best_eq.get("union_success_rate"),
                ),
            })

        record = {
            "identity": f"PORTFOLIO:{pid}",
            "portfolio_id": pid,
            "lottery_type": lottery,
            "ticket_budget": budget,
            "kind": kind,
            "source_cells": source_cells,
            "equal_budget_constituents": eq_budget_constituents,
            "primary_window_n": n,
            "prize_aware_obs_rate": obs_rate,
            "ordinary_random_baseline": ord_base,
            "diversified_random_baseline": div_base,
            "delta_vs_ordinary_random": (
                round(obs_rate - ord_base, 6) if obs_rate is not None
                and ord_base is not None else None
            ),
            "delta_vs_diversified_random": (
                round(obs_rate - div_base, 6) if obs_rate is not None
                and div_base is not None else None
            ),
            "ordinary_random_status": ord_rbs,
            "diversified_random_status": div_rbs,
            "ordinary_p_value": ord_p,
            "diversified_p_value": div_p,
            "best_equal_budget_constituent": best_eq_strat,
            "best_equal_budget_rate": best_eq_rate,
            "mcnemar_p_vs_best_equal_budget": mcnemar_p,
            "best_equal_budget_status": best_eq_status,
            "current_mapping": current_mapping,
            "observation_retention_status": (
                "OBSERVATION_RETAINED"
                if (ord_rbs == "ABOVE_RANDOM" and support_ok)
                else "OBSERVATION_NOT_RETAINED"
            ),
            "promotion_status": "PROMOTION_REVIEW_NOT_AUTHORIZED",
            "future_confirmation_status": "FUTURE_CONFIRMATION_PENDING",
            "scientific_verdict_preserved": scientific_verdict,
            "historical_artifact_unchanged": True,
            "window_summaries": win_summaries,
            "reclassification_reason": (
                f"P276B scientific verdict '{scientific_verdict}' preserved. "
                f"Portfolio {'beats' if ord_rbs == 'ABOVE_RANDOM' else 'does NOT beat'} "
                f"ordinary random baseline (Gate 1). "
                f"Portfolio {'beats' if best_eq_status == 'ABOVE_BEST_EQUAL_BUDGET' else 'does NOT beat'} "
                f"best equal-budget constituent (Gate 2). "
                f"Mapped to '{current_mapping}' under dual-gate rule."
            ),
            "limitations": [
                "All evidence is retrospective; NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE verdict preserved.",
                "Ticket-level complementarity (cross-strategy union coverage) measured only for the prize-aware endpoint.",
                "No strategy promotion, no registry mutation, no DB write.",
                "prediction_success_claim=false; strategy_promoted=false.",
                "Future-only confirmatory evidence required to change the scientific verdict.",
            ],
        }
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# Build evidence gap records
# ---------------------------------------------------------------------------

def build_evidence_gaps(sources: dict) -> list[dict]:
    """Identify committed evidence gaps."""
    gaps = []

    # P230C: not found in committed artifacts
    gaps.append({
        "artifact_id": "p230c",
        "description": "P230C (DAILY_539 backward-OOS apply) — no committed artifact found at outputs/research/p230c_*.json",
        "impact": "Backward-OOS for DAILY_539 covered only by P230B1 (dry-run); P230C was not committed to origin/main.",
        "resolution": "Use P230B1 dry-run evidence; treat as evidence gap for DAILY_539 backward-OOS real-apply.",
    })

    # P245A: referenced in git status as untracked but not committed
    gaps.append({
        "artifact_id": "p245a",
        "description": "P245A (external predictive method scouting) — untracked file, not committed to origin/main.",
        "impact": "External method scouting evidence not available for classification.",
        "resolution": "Excluded from universe; record as evidence gap.",
    })

    # P276B bet-index or special-zone dimension for POWER_LOTTO
    gaps.append({
        "artifact_id": "power_lotto_second_zone_inference",
        "description": "POWER_LOTTO second-zone (special number) separate inference not committed as standalone artifact.",
        "impact": "POWER_ANY_PRIZE_AWARE_WIN combines first-zone and second-zone. No separate second-zone-only inference available.",
        "resolution": "Record as evidence gap; combined prize-aware endpoint used for all POWER_LOTTO classifications.",
    })

    # BIG_LOTTO hit_count (M3+ endpoint) separate from prize-aware endpoint
    gaps.append({
        "artifact_id": "big_lotto_m3plus_standalone_inference",
        "description": "BIG_LOTTO M3+ standalone corrected inference (P267C) found NO corrected-significant cells. "
                       "Prize-aware (P275B) adds special-hit dimension. No standalone BIG_LOTTO prize-aware corrected-significant cell found.",
        "impact": "BIG_LOTTO strategies classifiable as at most OBSERVATION_POTENTIAL_ABOVE_RANDOM under prize-aware endpoint.",
        "resolution": "Classification applied consistently; BIG_LOTTO strategies reflect combined prize-aware evidence.",
    })

    return gaps


# ---------------------------------------------------------------------------
# Identify contradictions
# ---------------------------------------------------------------------------

def build_contradictions(strategy_records: list[dict]) -> list[dict]:
    """
    Identify structural contradictions in the evidence record.
    """
    contradictions = []

    for rec in strategy_records:
        lot = rec["lottery_type"]
        strat = rec["strategy_id"]
        oos = rec["OOS_status"]
        orig = rec["original_classification"]
        curr = rec["current_mapping"]
        rbs = rec["random_baseline_status"]
        css = rec["corrected_support_status"]

        # Contradiction: GO_CANDIDATE superseded by OOS_NULL
        if (rec["source_metrics"].get("is_go_candidate_research_only")
                and oos == "OOS_NULL"):
            contradictions.append({
                "identity": f"{lot}/{strat}",
                "type": "GO_CANDIDATE_WITH_OOS_NULL",
                "description": (
                    f"{lot}/{strat} was P275B GO_CANDIDATE_RESEARCH_ONLY but "
                    f"P230B1 backward-OOS is NULL (below baseline, p=0.626). "
                    f"Under dual-gate, OOS_NULL supersedes in-window corrected inference. "
                    f"Reclassified to HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL."
                ),
                "resolution": "OOS_NULL takes precedence per EVIDENCE_PRECEDENCE rule (L1 > L4).",
            })

    # Check for any strategy above random in ALL windows without any corrected support
    for rec in strategy_records:
        lot = rec["lottery_type"]
        strat = rec["strategy_id"]
        if (rec["current_mapping"] == "OBSERVATION_POTENTIAL_ABOVE_RANDOM"
                and rec["corrected_support_status"] == "CORRECTED_NULL"
                and rec["random_baseline_status"] == "ABOVE_RANDOM"):
            contradictions.append({
                "identity": f"{lot}/{strat}",
                "type": "POSITIVE_POINT_ESTIMATE_CORRECTED_NULL",
                "description": (
                    f"{lot}/{strat} has positive absolute lift in primary window "
                    f"but corrected p >= 0.05. Classified as "
                    f"OBSERVATION_POTENTIAL_ABOVE_RANDOM (Gate 1 pass, Gate 2 not reached)."
                ),
                "resolution": "This is expected behavior under the dual-gate rule; not a true contradiction.",
            })

    return contradictions


# ---------------------------------------------------------------------------
# Answer the 11 required research questions
# ---------------------------------------------------------------------------

def answer_required_questions(
    strategy_records: list[dict],
    portfolio_records: list[dict],
) -> dict:
    """
    Answer all 11 required research questions deterministically.
    """
    # Q1: How many strategy cells pass the random-baseline observation gate?
    q1_pass = [r for r in strategy_records
                if r["random_baseline_status"] == "ABOVE_RANDOM"
                and r["observation_retention_status"] == "OBSERVATION_RETAINED"]

    # Q2: How many are point-estimate observations only?
    q2_point_only = [r for r in strategy_records
                      if r["current_mapping"] == "OBSERVATION_POTENTIAL_ABOVE_RANDOM"
                      and r["corrected_support_status"] not in (
                          "CORRECTED_SIGNIFICANT",)]

    # Q3: How many have corrected support?
    q3_corrected = [r for r in strategy_records
                     if r["corrected_support_status"] == "CORRECTED_SIGNIFICANT"]

    # Q4: How many beat random but not the best strategy?
    q4_beat_rand_not_best = [r for r in strategy_records
                               if r["random_baseline_status"] == "ABOVE_RANDOM"
                               and r["best_equal_budget_status"] != "ABOVE_BEST_EQUAL_BUDGET"]

    # Q5: How many beat both random and best strategy?
    q5_beat_both = [r for r in strategy_records
                     if r["random_baseline_status"] == "ABOVE_RANDOM"
                     and r["best_equal_budget_status"] == "ABOVE_BEST_EQUAL_BUDGET"]

    # Q6: How many remain NULL vs random?
    q6_null = [r for r in strategy_records
                if r["current_mapping"] in ("NO_EVIDENCE_OVER_RANDOM",
                                             "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL")]

    # Q7: How many earlier observations are superseded by OOS NULL?
    q7_oos_superseded = [r for r in strategy_records
                          if r["current_mapping"] == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL"]

    # Q8: Which P276B portfolios beat random but not the best constituent?
    q8_portfolios = [p for p in portfolio_records
                      if p["ordinary_random_status"] == "ABOVE_RANDOM"
                      and p["best_equal_budget_status"] != "ABOVE_BEST_EQUAL_BUDGET"]

    # Q9: Which identities lack valid baseline evidence?
    q9_no_baseline = [r for r in strategy_records
                       if r["current_mapping"] in ("INSUFFICIENT_RANDOM_BASELINE_EVIDENCE",
                                                    "INSUFFICIENT_SUPPORT")]

    # Q10: Which candidates should appear on the future hit-spectrum page?
    q10_hit_spectrum = [r for r in strategy_records
                         if r["current_mapping"] in (
                             "STRONG_RESEARCH_CANDIDATE",
                             "OBSERVATION_SUPPORTED_ABOVE_RANDOM",
                             "COMPETITIVE_OBSERVATION_STRATEGY",
                         )]

    # Q11: Which items require new evidence rather than status remapping?
    q11_needs_new_evidence = [r for r in strategy_records
                               if r["current_mapping"] in (
                                   "UNDERPOWERED_OBSERVATION_POTENTIAL",
                                   "OBSERVATION_POTENTIAL_ABOVE_RANDOM",
                               )]

    return {
        "q1_strategy_cells_passing_random_gate": {
            "count": len(q1_pass),
            "identities": [r["identity"] for r in q1_pass],
            "answer": (
                f"{len(q1_pass)} strategy cells pass the random-baseline observation gate "
                f"(observed prize-aware success rate > governed random null baseline, "
                f"adequate support, OOS not NULL)."
            ),
        },
        "q2_point_estimate_only": {
            "count": len(q2_point_only),
            "identities": [r["identity"] for r in q2_point_only],
            "answer": (
                f"{len(q2_point_only)} strategy cells have point-estimate observation only "
                f"(above random but corrected p >= 0.05 or no inference possible)."
            ),
        },
        "q3_corrected_supported": {
            "count": len(q3_corrected),
            "identities": [r["identity"] for r in q3_corrected],
            "answer": (
                f"{len(q3_corrected)} strategy cells have Bonferroni-corrected support "
                f"(corrected p < 0.05 in at least one primary window of the 108-hypothesis family)."
            ),
        },
        "q4_beat_random_not_best_strategy": {
            "count": len(q4_beat_rand_not_best),
            "identities": [r["identity"] for r in q4_beat_rand_not_best],
            "answer": (
                f"{len(q4_beat_rand_not_best)} strategy cells beat random but do not "
                f"beat the best equal-budget strategy in the same lottery/budget bucket."
            ),
        },
        "q5_beat_both_random_and_best": {
            "count": len(q5_beat_both),
            "identities": [r["identity"] for r in q5_beat_both],
            "answer": (
                f"{len(q5_beat_both)} strategy cells beat both the random baseline "
                f"AND the best equal-budget strategy."
            ),
        },
        "q6_null_vs_random": {
            "count": len(q6_null),
            "identities": [r["identity"] for r in q6_null],
            "answer": (
                f"{len(q6_null)} strategy cells remain NULL vs random "
                f"(NO_EVIDENCE_OVER_RANDOM or superseded by OOS null)."
            ),
        },
        "q7_oos_superseded": {
            "count": len(q7_oos_superseded),
            "identities": [r["identity"] for r in q7_oos_superseded],
            "answer": (
                f"{len(q7_oos_superseded)} earlier observation(s) superseded by OOS NULL: "
                + ", ".join(r["identity"] for r in q7_oos_superseded)
                if q7_oos_superseded else
                f"{len(q7_oos_superseded)} strategy cells superseded by OOS NULL."
            ),
        },
        "q8_portfolios_beat_random_not_best_constituent": {
            "count": len(q8_portfolios),
            "portfolio_ids": [p["portfolio_id"] for p in q8_portfolios],
            "answer": (
                f"{len(q8_portfolios)} P276B portfolio(s) beat ordinary random "
                f"but do NOT beat the best equal-budget constituent: "
                + ", ".join(p["portfolio_id"] for p in q8_portfolios)
                if q8_portfolios else
                f"{len(q8_portfolios)} P276B portfolios beat random but not best constituent."
            ),
        },
        "q9_no_valid_baseline": {
            "count": len(q9_no_baseline),
            "identities": [r["identity"] for r in q9_no_baseline],
            "answer": (
                f"{len(q9_no_baseline)} strategy cells lack valid random baseline evidence "
                f"(INSUFFICIENT_SUPPORT or INSUFFICIENT_RANDOM_BASELINE_EVIDENCE)."
            ),
        },
        "q10_hit_spectrum_page_candidates": {
            "count": len(q10_hit_spectrum),
            "identities": [r["identity"] for r in q10_hit_spectrum],
            "answer": (
                f"{len(q10_hit_spectrum)} identities suitable for the future hit-spectrum page: "
                + ", ".join(r["identity"] for r in q10_hit_spectrum)
                if q10_hit_spectrum else
                "No identities currently suitable for the hit-spectrum page."
            ),
        },
        "q11_need_new_evidence": {
            "count": len(q11_needs_new_evidence),
            "identities": [r["identity"] for r in q11_needs_new_evidence],
            "answer": (
                f"{len(q11_needs_new_evidence)} strategy cells require new evidence "
                f"(additional OOS draws) rather than status remapping."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Build classification summary
# ---------------------------------------------------------------------------

def build_classification_summary(
    strategy_records: list[dict],
    portfolio_records: list[dict],
) -> dict:
    """Build the required classification summary."""
    from collections import Counter

    orig_counts = Counter(r["original_classification"] for r in strategy_records)
    new_counts = Counter(r["current_mapping"] for r in strategy_records)

    # Counts by type
    corrected_supported = sum(1 for r in strategy_records
                               if r["corrected_support_status"] == "CORRECTED_SIGNIFICANT")
    point_estimate_only = sum(1 for r in strategy_records
                               if r["current_mapping"] == "OBSERVATION_POTENTIAL_ABOVE_RANDOM"
                               and r["corrected_support_status"] != "CORRECTED_SIGNIFICANT")
    competitive = sum(1 for r in strategy_records
                       if r["current_mapping"] == "COMPETITIVE_OBSERVATION_STRATEGY")
    strong_candidate = sum(1 for r in strategy_records
                            if r["current_mapping"] == "STRONG_RESEARCH_CANDIDATE")
    underpowered = sum(1 for r in strategy_records
                       if r["current_mapping"] == "UNDERPOWERED_OBSERVATION_POTENTIAL")
    oos_superseded = sum(1 for r in strategy_records
                          if r["current_mapping"] == "HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL")
    no_evidence = sum(1 for r in strategy_records
                       if r["current_mapping"] == "NO_EVIDENCE_OVER_RANDOM")
    missing_baseline = sum(1 for r in strategy_records
                            if r["current_mapping"] in (
                                "INSUFFICIENT_RANDOM_BASELINE_EVIDENCE",
                                "INSUFFICIENT_SUPPORT"))
    beat_random_not_best = sum(1 for r in strategy_records
                                if r["random_baseline_status"] == "ABOVE_RANDOM"
                                and r["best_equal_budget_status"] != "ABOVE_BEST_EQUAL_BUDGET")
    beat_both = sum(1 for r in strategy_records
                     if r["random_baseline_status"] == "ABOVE_RANDOM"
                     and r["best_equal_budget_status"] == "ABOVE_BEST_EQUAL_BUDGET")
    observation_supported = sum(1 for r in strategy_records
                                  if r["current_mapping"] == "OBSERVATION_SUPPORTED_ABOVE_RANDOM")

    # P276B portfolio table
    p276b_table = []
    for p in portfolio_records:
        p276b_table.append({
            "portfolio_id": p["portfolio_id"],
            "kind": p["kind"],
            "budget": p["ticket_budget"],
            "lottery": p["lottery_type"],
            "obs_rate": p.get("prize_aware_obs_rate"),
            "ordinary_random_baseline": p.get("ordinary_random_baseline"),
            "diversified_random_baseline": p.get("diversified_random_baseline"),
            "ordinary_random_status": p.get("ordinary_random_status"),
            "diversified_random_status": p.get("diversified_random_status"),
            "best_equal_budget_status": p.get("best_equal_budget_status"),
            "current_mapping": p["current_mapping"],
            "observation_retention": p["observation_retention_status"],
        })

    return {
        "unique_strategy_cell_count": len(strategy_records),
        "portfolio_count": len(portfolio_records),
        "endpoint_count": 3,
        "source_artifact_count": len(SOURCE_ARTIFACTS),
        "count_by_original_classification": dict(orig_counts),
        "count_by_new_classification": dict(new_counts),
        "point_estimate_observations": point_estimate_only,
        "corrected_supported_observations": corrected_supported,
        "competitive_observations": competitive,
        "strong_research_candidates": strong_candidate,
        "underpowered_observations": underpowered,
        "oos_superseded_observations": oos_superseded,
        "no_evidence_over_random": no_evidence,
        "missing_baseline_items": missing_baseline,
        "items_beating_random_not_best_strategy": beat_random_not_best,
        "items_beating_both_random_and_best_strategy": beat_both,
        "observation_supported_above_random": observation_supported,
        "p276b_portfolio_table": p276b_table,
        "supported_lotteries": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
        "endpoints": {
            "DAILY_539": "D539_ANY_PRIZE_AWARE_WIN (hit_count >= 2)",
            "BIG_LOTTO": "BIG_ANY_PRIZE_AWARE_WIN (hit_count >= 3 OR hit_count=2+special)",
            "POWER_LOTTO": "POWER_ANY_PRIZE_AWARE_WIN (hit_count >= 3 OR hit_count>=1+special)",
        },
    }


# ---------------------------------------------------------------------------
# Canonical payload digest (excludes generated_at, absolute paths, self-hash)
# ---------------------------------------------------------------------------

def compute_canonical_digest(payload: dict) -> str:
    """
    Compute SHA-256 of the deterministic payload (excludes generated_at,
    source_artifact_hashes with path-absolute values, self-hash).
    """
    # Build the digest-stable subset
    stable = {
        "task_id": payload["task_id"],
        "source_commit": payload["source_commit"],
        "source_artifact_manifest": sorted(payload["source_artifact_manifest"]),
        "universe_counts": payload["universe_counts"],
        "endpoint_counts": payload["endpoint_counts"],
        "classification_summary": {
            k: v for k, v in payload["classification_summary"].items()
            if k != "p276b_portfolio_table"
        },
        "classification_summary_p276b_portfolio_table": [
            {kk: vv for kk, vv in row.items()}
            for row in payload["classification_summary"].get("p276b_portfolio_table", [])
        ],
        "strategies": [
            {kk: vv for kk, vv in s.items()
             if kk not in ("reclassification_reason",)}
            for s in payload["strategies"]
        ],
        "portfolios": [
            {kk: vv for kk, vv in p.items()
             if kk not in ("reclassification_reason",)}
            for p in payload["portfolios"]
        ],
        "evidence_gaps_count": len(payload["evidence_gaps"]),
        "prediction_success_claim": payload["prediction_success_claim"],
        "strategy_promoted": payload["strategy_promoted"],
        "database_opened": payload["database_opened"],
        "database_write": payload["database_write"],
        "historical_artifacts_unchanged": payload["historical_artifacts_unchanged"],
    }
    stable_str = json.dumps(stable, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"))
    return hashlib.sha256(stable_str.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Recommended follow-ups
# ---------------------------------------------------------------------------

RECOMMENDED_FOLLOWUPS = [
    {
        "id": "RFU-01",
        "description": "DAILY_539 acb_markov_midfreq_3bet: Collect 300+ new prospective draws for "
                       "the independent confirmatory gate (P272B power analysis: needs ~300 new draws "
                       "for 80% power to detect +9.5pp above random).",
        "strategy": "DAILY_539/acb_markov_midfreq_3bet",
        "priority": "HIGH",
    },
    {
        "id": "RFU-02",
        "description": "DAILY_539 daily539_f4cold_5bet: Collect 300+ new prospective draws. "
                       "Strongest corrected signal (p_corr=4.3e-8 in LONG window). "
                       "Most promising candidate for hit-spectrum page.",
        "strategy": "DAILY_539/daily539_f4cold_5bet",
        "priority": "HIGH",
    },
    {
        "id": "RFU-03",
        "description": "DAILY_539 daily539_f4cold_3bet: Corrected-significant in LONG window "
                       "(p_corr=0.017). Collect 300+ new prospective draws.",
        "strategy": "DAILY_539/daily539_f4cold_3bet",
        "priority": "HIGH",
    },
    {
        "id": "RFU-04",
        "description": "DAILY_539 midfreq_fourier_2bet: P230B1 backward-OOS (4265 draws) showed "
                       "below-baseline performance. No further investment recommended without "
                       "architectural change.",
        "strategy": "DAILY_539/midfreq_fourier_2bet",
        "priority": "LOW",
    },
    {
        "id": "RFU-05",
        "description": "P276B portfolios: All cross-strategy portfolios underperform best constituent "
                       "(NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE). Additional OOS draws needed "
                       "before cross-strategy portfolio deployment can be reconsidered.",
        "scope": "all_p276b_portfolios",
        "priority": "MEDIUM",
    },
    {
        "id": "RFU-06",
        "description": "POWER_LOTTO all strategies: 4 strategies have no prize-aware replay data "
                       "(INSUFFICIENT_SUPPORT). Consider generating replay data for "
                       "fourier_rhythm_3bet, power_fourier_rhythm_2bet, power_orthogonal_5bet, "
                       "power_precision_3bet under read-only conditions.",
        "scope": "POWER_LOTTO",
        "priority": "MEDIUM",
    },
    {
        "id": "RFU-07",
        "description": "BIG_LOTTO all strategies: No corrected-significant cells found under "
                       "prize-aware endpoint. L91 finding (49C6 pool is fair-random indistinguishable) "
                       "remains operative. No further investment recommended.",
        "scope": "BIG_LOTTO",
        "priority": "LOW",
    },
]


# ---------------------------------------------------------------------------
# Main artifact builder
# ---------------------------------------------------------------------------

def build_artifact(generated_at: str = GENERATED_AT_PINNED) -> dict:
    """
    Build the complete P277A JSON artifact deterministically.
    Two calls with the same generated_at MUST yield identical canonical_payload_digest.
    """
    # Fail closed: verify no forbidden imports have leaked in
    _static_forbidden_check()

    # Hash source artifacts
    artifact_hashes = build_artifact_hashes()
    missing = verify_artifact_hashes(artifact_hashes)

    # Load all sources
    sources = load_all_sources()

    # Build records
    strategy_records = build_strategy_records(sources)
    portfolio_records = build_portfolio_records(sources)
    evidence_gaps = build_evidence_gaps(sources)
    contradictions = build_contradictions(strategy_records)
    classification_summary = build_classification_summary(
        strategy_records, portfolio_records
    )
    required_questions = answer_required_questions(
        strategy_records, portfolio_records
    )

    # Universe counts
    universe_counts = {
        "total_strategy_cells": len(strategy_records),
        "total_portfolios": len(portfolio_records),
        "total_evidence_artifacts": len(SOURCE_ARTIFACTS),
        "missing_artifacts": len(missing),
        "lotteries": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
        "windows_per_cell": 3,
        "correction_family_size": 108,
    }

    payload = {
        "task_id": TASK_ID,
        "generated_at": generated_at,
        "source_commit": SOURCE_COMMIT,
        "source_artifact_manifest": sorted(
            p.relative_to(ROOT).as_posix() for p in SOURCE_ARTIFACTS.values()
        ),
        "source_artifact_hashes": artifact_hashes,
        "universe_definition": (
            "All committed strategy-cell and portfolio evidence under "
            "outputs/research/ on origin/main commit b6dd42f. "
            "36 strategy cells (P267C/P275B frozen universe) x 3 primary windows. "
            "8 P276B portfolios. Evidence precedence: future-OOS > backward-OOS > "
            "corrected inference > descriptive > point estimate > no baseline."
        ),
        "universe_counts": universe_counts,
        "endpoint_counts": {
            "DAILY_539": 1,
            "BIG_LOTTO": 1,
            "POWER_LOTTO": 1,
        },
        "classification_taxonomy": TAXONOMY,
        "evidence_precedence": EVIDENCE_PRECEDENCE,
        "owner_dual_gate_rule": {
            "gate_1_retention": (
                "Beating the governed RANDOM baseline is SUFFICIENT to retain "
                "a strategy/portfolio as an OBSERVATION CANDIDATE. "
                "This is the minimum retention criterion."
            ),
            "gate_2_promotion": (
                "Beating the BEST EQUAL-BUDGET strategy is a STRONGER priority/"
                "promotion criterion — NOT the minimum observation-retention criterion."
            ),
            "implication": (
                "A strategy MAY beat random (Gate 1 PASS) while ALSO failing to beat "
                "the best equal-budget strategy. This is ALLOWED and not contradictory. "
                "Gate 1 alone is sufficient for OBSERVATION_POTENTIAL classification."
            ),
        },
        "historical_artifacts_unchanged": True,
        "database_opened": False,
        "database_write": False,
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "classification_summary": classification_summary,
        "strategies": strategy_records,
        "portfolios": portfolio_records,
        "evidence_gaps": evidence_gaps,
        "contradictions": contradictions,
        "required_questions": required_questions,
        "recommended_followups": RECOMMENDED_FOLLOWUPS,
        "canonical_payload_digest": "",  # placeholder, computed below
    }

    # Compute canonical digest (excludes generated_at, paths, self-hash)
    digest = compute_canonical_digest(payload)
    payload["canonical_payload_digest"] = digest

    return payload


def _static_forbidden_check() -> None:
    """
    Verify at runtime that no forbidden interface is present in this module.
    This is also verified statically by the test suite.
    """
    # Use Path(__file__) to read source bytes directly — avoids inspect.getsource
    # failures when module is loaded via importlib.util.spec_from_file_location
    src = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("sqlite3", "requests", "urllib", "socket",
                      "subprocess", "os.system"):
        # Allow the string to appear in comments/docs, but NOT as an import
        # Check for actual import patterns
        import_patterns = [
            f"import {forbidden}",
            f"from {forbidden}",
        ]
        for pat in import_patterns:
            if pat in src:
                raise RuntimeError(
                    f"FORBIDDEN INTERFACE DETECTED: '{pat}' in "
                    f"p277a_historical_observation_status_reclassification.py"
                )


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def render_markdown(payload: dict) -> str:
    """
    Deterministically render the JSON payload as Markdown.
    All numbers come from the JSON; no independent computation.
    """
    lines = []
    cs = payload["classification_summary"]
    rq = payload["required_questions"]
    dg = payload["canonical_payload_digest"]
    sc = payload["source_commit"]

    lines += [
        "# P277A — Historical Observation Status Reclassification Audit",
        "",
        f"**Generated:** {payload['generated_at']}",
        f"**Source commit (origin/main):** `{sc}`",
        f"**Canonical payload digest:** `{dg}`",
        f"**prediction_success_claim:** {payload['prediction_success_claim']}",
        f"**strategy_promoted:** {payload['strategy_promoted']}",
        f"**database_opened:** {payload['database_opened']}",
        f"**database_write:** {payload['database_write']}",
        "",
        "---",
        "",
        "## Owner Dual-Gate Rule",
        "",
        "| Gate | Rule |",
        "|------|------|",
        f"| Gate 1 (retention) | {payload['owner_dual_gate_rule']['gate_1_retention']} |",
        f"| Gate 2 (promotion) | {payload['owner_dual_gate_rule']['gate_2_promotion']} |",
        "",
        "> **Implication:** A strategy MAY beat random (Gate 1 PASS) while ALSO failing "
        "to beat the best equal-budget strategy. This is ALLOWED and not contradictory. "
        "Gate 1 alone is sufficient for OBSERVATION_POTENTIAL classification.",
        "",
        "---",
        "",
        "## Classification Summary",
        "",
        f"- Unique strategy-cell count: **{cs['unique_strategy_cell_count']}**",
        f"- Portfolio count: **{cs['portfolio_count']}**",
        f"- Endpoint count: **{cs['endpoint_count']}**",
        f"- Source artifact count: **{cs['source_artifact_count']}**",
        "",
        "### Original Classifications (P275B)",
        "",
        "| Original Classification | Count |",
        "|------------------------|-------|",
    ]
    for k, v in sorted(cs["count_by_original_classification"].items()):
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "### New Classifications (P277A Dual-Gate)",
        "",
        "| New Classification | Count |",
        "|-------------------|-------|",
    ]
    for k, v in sorted(cs["count_by_new_classification"].items()):
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "### Observation Counts",
        "",
        f"- Point-estimate observations only: **{cs['point_estimate_observations']}**",
        f"- Corrected-supported observations: **{cs['corrected_supported_observations']}**",
        f"- Competitive observations: **{cs['competitive_observations']}**",
        f"- Strong research candidates: **{cs['strong_research_candidates']}**",
        f"- Underpowered observations: **{cs['underpowered_observations']}**",
        f"- OOS-superseded observations: **{cs['oos_superseded_observations']}**",
        f"- No evidence over random: **{cs['no_evidence_over_random']}**",
        f"- Missing-baseline items: **{cs['missing_baseline_items']}**",
        f"- Items beating random but NOT best strategy: **{cs['items_beating_random_not_best_strategy']}**",
        f"- Items beating BOTH random AND best strategy: **{cs['items_beating_both_random_and_best_strategy']}**",
        "",
        "---",
        "",
        "## P276B Portfolio Table",
        "",
        "Scientific verdict (preserved): **NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE**",
        "",
        "| Portfolio ID | Kind | Budget | Lottery | Obs Rate | Ord Rand Base | Div Rand Base | Ord Status | Div Status | Best EQ Status | Current Mapping |",
        "|-------------|------|--------|---------|----------|---------------|---------------|------------|------------|----------------|-----------------|",
    ]
    for row in cs["p276b_portfolio_table"]:
        obs = f"{row['obs_rate']:.4f}" if row.get("obs_rate") is not None else "N/A"
        ordb = f"{row['ordinary_random_baseline']:.4f}" if row.get("ordinary_random_baseline") is not None else "N/A"
        divb = f"{row['diversified_random_baseline']:.4f}" if row.get("diversified_random_baseline") is not None else "N/A"
        lines.append(
            f"| {row['portfolio_id']} | {row['kind']} | {row['budget']} | "
            f"{row['lottery']} | {obs} | {ordb} | {divb} | "
            f"{row.get('ordinary_random_status','?')} | "
            f"{row.get('diversified_random_status','?')} | "
            f"{row.get('best_equal_budget_status','?')} | "
            f"{row['current_mapping']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Required Research Questions",
        "",
    ]
    q_nums = [
        ("q1_strategy_cells_passing_random_gate", "Q1"),
        ("q2_point_estimate_only", "Q2"),
        ("q3_corrected_supported", "Q3"),
        ("q4_beat_random_not_best_strategy", "Q4"),
        ("q5_beat_both_random_and_best", "Q5"),
        ("q6_null_vs_random", "Q6"),
        ("q7_oos_superseded", "Q7"),
        ("q8_portfolios_beat_random_not_best_constituent", "Q8"),
        ("q9_no_valid_baseline", "Q9"),
        ("q10_hit_spectrum_page_candidates", "Q10"),
        ("q11_need_new_evidence", "Q11"),
    ]
    q_texts = {
        "q1_strategy_cells_passing_random_gate":
            "How many strategy cells pass the random-baseline observation gate?",
        "q2_point_estimate_only":
            "How many are point-estimate observations only?",
        "q3_corrected_supported":
            "How many have corrected support?",
        "q4_beat_random_not_best_strategy":
            "How many beat random but not the best strategy?",
        "q5_beat_both_random_and_best":
            "How many beat both random and best strategy?",
        "q6_null_vs_random":
            "How many remain NULL vs random?",
        "q7_oos_superseded":
            "How many earlier observations are superseded by OOS NULL?",
        "q8_portfolios_beat_random_not_best_constituent":
            "Which P276B portfolios beat random but not the best constituent?",
        "q9_no_valid_baseline":
            "Which identities lack valid baseline evidence?",
        "q10_hit_spectrum_page_candidates":
            "Which candidates should appear on the future strategy hit-spectrum page?",
        "q11_need_new_evidence":
            "Which items require new evidence rather than status remapping?",
    }
    for key, label in q_nums:
        q = rq.get(key, {})
        lines += [
            f"### {label}: {q_texts.get(key, key)}",
            "",
            f"**Answer:** {q.get('answer', 'N/A')}",
            "",
        ]
        # For questions with identity lists, show them
        identities = q.get("identities") or q.get("portfolio_ids", [])
        if identities:
            lines.append("**Identities:**")
            for ident in identities:
                lines.append(f"- `{ident}`")
            lines.append("")

    lines += [
        "---",
        "",
        "## Strategy Records",
        "",
        "| Identity | Current Mapping | Obs Rate | Base | Delta | Corrected Support | OOS Status | Observation Retention |",
        "|----------|-----------------|----------|------|-------|-------------------|------------|-----------------------|",
    ]
    for r in sorted(payload["strategies"],
                    key=lambda x: (x["lottery_type"], x["strategy_id"])):
        obs = f"{r['observed_value']:.4f}" if r.get("observed_value") is not None else "N/A"
        base = f"{r['random_baseline_value']:.4f}" if r.get("random_baseline_value") is not None else "N/A"
        delta = f"{r['delta_vs_random']:+.4f}" if r.get("delta_vs_random") is not None else "N/A"
        lines.append(
            f"| `{r['identity']}` | {r['current_mapping']} | {obs} | {base} | {delta} | "
            f"{r['corrected_support_status']} | {r['OOS_status']} | "
            f"{r['observation_retention_status']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Evidence Gaps",
        "",
    ]
    for gap in payload["evidence_gaps"]:
        lines += [
            f"### {gap['artifact_id']}",
            "",
            f"**Description:** {gap['description']}",
            "",
            f"**Impact:** {gap['impact']}",
            "",
            f"**Resolution:** {gap['resolution']}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Recommended Follow-ups",
        "",
    ]
    for rfu in payload["recommended_followups"]:
        lines += [
            f"### {rfu['id']} (Priority: {rfu['priority']})",
            "",
            f"{rfu['description']}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Governance",
        "",
        "- All source artifacts are read-only committed JSON files on origin/main.",
        "- No SQLite DB opened. No production DB accessed or written.",
        "- No strategy promotion. No registry mutation. No controlled_apply.",
        "- No historical artifact modified.",
        "- prediction_success_claim=false; strategy_promoted=false.",
        f"- Canonical payload digest: `{dg}`",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Write JSON and Markdown artifacts to outputs/research/."""
    import sys

    out_json = OUTPUTS / "p277a_historical_observation_status_reclassification_20260617.json"
    out_md = OUTPUTS / "p277a_historical_observation_status_reclassification_20260617.md"

    print(f"Building {TASK_ID} artifact...", file=sys.stderr)
    payload = build_artifact(generated_at=GENERATED_AT_PINNED)

    # Write JSON
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Written: {out_json}", file=sys.stderr)

    # Write Markdown
    md = render_markdown(payload)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Written: {out_md}", file=sys.stderr)

    print(f"canonical_payload_digest: {payload['canonical_payload_digest']}", file=sys.stderr)
    print("DONE", file=sys.stderr)


if __name__ == "__main__":
    main()
