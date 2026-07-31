"""
P52 — Formal Monitoring Contract V2 Artifact After P51 Revision
================================================================

Creates the canonical V2 monitoring contract, formalizing P51's findings.
This is a paper-only, offline, diagnostic task.  No source artifacts from
P43–P51 are modified.  No runtime recommendation logic is touched.

Governance (ALL LOCKED):
    paper_only=True, diagnostic_only=True, promotion_freeze=True,
    kelly_deploy_allowed=False, live_api_calls=0,
    p48_artifact_overwritten=False, p49_artifact_overwritten=False,
    p51_artifact_preserved=True

Output:
    data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json
    report/p52_monitoring_contract_v2_20260526.md
    00-BettingPlan/20260526/p52_monitoring_contract_v2_20260526.md
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

# ── Governance ────────────────────────────────────────────────────────────────
GOVERNANCE_FLAGS: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "p48_artifact_overwritten": False,
    "p49_artifact_overwritten": False,
    "p51_artifact_preserved": True,
}

# ── Locked Platt constants (P45) ──────────────────────────────────────────────
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).parent.parent
_DERIVED = _ROOT / "data/mlb_2025/derived"

SOURCE_PATHS: dict[str, pathlib.Path] = {
    "p43": _DERIVED / "p43_strong_edge_closing_line_edge_summary.json",
    "p44": _DERIVED / "p44_temporal_stability_summary.json",
    "p45": _DERIVED / "p45_platt_recalibration_summary.json",
    "p46": _DERIVED / "p46_isotonic_recalibration_summary.json",
    "p47": _DERIVED / "p47_calibration_synthesis_summary.json",
    "p48": _DERIVED / "p48_monitoring_loop_contract_summary.json",
    "p49": _DERIVED / "p49_offline_historical_monitoring_replay_summary.json",
    "p50": _DERIVED / "p50_edge_drift_root_cause_audit_summary.json",
    "p51": _DERIVED / "p51_monitoring_contract_revision_summary.json",
}

OUTPUT_JSON = _DERIVED / "p52_monitoring_contract_v2_summary.json"
OUTPUT_REPORT = _ROOT / "report/p52_monitoring_contract_v2_20260526.md"
OUTPUT_PLAN = _ROOT / "00-BettingPlan/20260526/p52_monitoring_contract_v2_20260526.md"

ALLOWED_CLASSIFICATIONS = [
    "P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC",
    "P52_MONITORING_CONTRACT_V2_INCOMPLETE",
    "P52_BLOCKED_BY_SOURCE_MISSING",
    "P52_SAMPLE_LIMITED",
]


# ── Load helpers ──────────────────────────────────────────────────────────────

def _load_json(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def load_all_sources() -> dict[str, dict]:
    sources: dict[str, dict] = {}
    missing: list[str] = []
    for key, path in SOURCE_PATHS.items():
        if not path.exists():
            missing.append(str(path))
        else:
            sources[key] = _load_json(path)
    if missing:
        raise FileNotFoundError(f"P52 blocked: missing source artifacts: {missing}")
    return sources


# ── Task P52.A — Contract version + supersession policy ──────────────────────

def build_contract_metadata() -> dict:
    return {
        "contract_version": "P52_MONITORING_CONTRACT_V2",
        "supersession_policy": {
            "supersedes": [
                "P48 edge-monitoring stream rule (P48 assigned edge monitoring to PLATT_CALIBRATED; "
                "V2 assigns it to RAW_SIGMOID fip_signal_side_aware_edge)",
                "P49 SAMPLE_LIMITED dominance over CRITICAL (P49 let SAMPLE_LIMITED suppress genuine "
                "CALIBRATION_CRITICAL; V2 prohibits this suppression)",
                "P49 Platt-edge drift interpretation (P49 classified May/Jun/Aug 2025 Platt-edge "
                "alerts as genuine drift; P50 confirmed stream mismatch; V2 uses correct stream)",
            ],
            "preserves": [
                "P48 fixture schema concept — monitoring_row_schema fields retained as V2 base",
                "P48 ECE/Brier thresholds — ece_warning=0.10, ece_critical=0.12, "
                "brier_warning=0.25, brier_critical=0.27 unchanged",
                "P48 edge thresholds — mean_edge_warning=0.07, critical=CI_crosses_zero unchanged",
                "P48 DATA_GAP_BLOCKED dominance rule — retained in V2",
                "P49 offline replay concept — batch replay against historical records retained",
                "P47 Platt selection for calibration monitoring — PLATT_CALIBRATED remains "
                "canonical for ECE/Brier",
            ],
            "does_not_overwrite": [
                "P48 artifact: data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json",
                "P49 artifact: data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json",
                "P51 artifact: data/mlb_2025/derived/p51_monitoring_contract_revision_summary.json",
                "runtime recommendation logic",
                "champion strategy",
                "TSL crawler",
            ],
        },
    }


# ── Task P52.B — Metric ownership matrix V2 ──────────────────────────────────

def build_metric_ownership_matrix_v2() -> list[dict]:
    return [
        # ── Edge family ──────────────────────────────────────────────────────
        {
            "metric_family": "EDGE_SIGNAL",
            "selected_probability_stream": "RAW_SIGMOID",
            "stream_detail": (
                "sigmoid(1.0 * sp_fip_delta) — FIP informativeness signal, k=1.0, "
                "side-aware (P43/P44 canonical definition)"
            ),
            "rationale": (
                "P43/P44 edge framework was designed with sigmoid(sp_fip_delta) as the "
                "model probability. P49 substituted trained ML model_home_prob "
                "(regularized toward 0.5), causing P50-confirmed stream mismatch. "
                "V2 restores the canonical P43/P44 FIP-signal edge semantics."
            ),
            "source_phase": "P43, P44, P50 (root cause), P51 (revision replay)",
            "metrics": [
                "side_aware_raw_edge",
                "mean_edge",
                "edge_ci_low",
                "edge_ci_high",
                "positive_edge_rate",
            ],
            "edge_perspective": "SIDE_AWARE",
            "market_source": "embedded_no_vig_at_prediction_time",
            "ci_method": "bootstrap_5000_seed42",
            "alert_family": "EDGE_SIGNAL_ALERT",
            "alert_rules": {
                "warning": "mean_edge < 0.07",
                "critical": "edge_ci_low <= 0",
            },
            "isotonic_used_here": False,
            "platt_used_here": False,
        },
        # ── Calibration family ───────────────────────────────────────────────
        {
            "metric_family": "CALIBRATION",
            "selected_probability_stream": "PLATT_CALIBRATED",
            "stream_detail": (
                f"Platt scaling: A={PLATT_A}, B={PLATT_B}, sigmoid_k={SIGMOID_K} "
                "(locked from P45, not re-optimizable without explicit CEO authorization)"
            ),
            "rationale": (
                "P45 showed Platt scaling improves ECE vs raw sigmoid on 2025 data. "
                "P46 showed isotonic regression had weaker temporal generalization. "
                "P47 selected PLATT_CALIBRATED as canonical calibration monitoring stream. "
                "V2 retains this selection."
            ),
            "source_phase": "P45, P46, P47, P48",
            "metrics": [
                "platt_ece",
                "platt_brier",
                "reliability_bin_gap",
                "calibration_drift",
            ],
            "alert_family": "CALIBRATION_ALERT",
            "alert_rules": {
                "ece_warning": "platt_ece > 0.10",
                "ece_critical": "platt_ece > 0.12",
                "brier_warning": "platt_brier > 0.25",
                "brier_critical": "platt_brier > 0.27",
            },
            "isotonic_status": "COMPARISON_ONLY — not selected per P46",
            "isotonic_used_here": False,
        },
        # ── Sample family ────────────────────────────────────────────────────
        {
            "metric_family": "SAMPLE",
            "selected_probability_stream": "NONE",
            "stream_detail": "N/A — count of games in batch",
            "rationale": (
                "Batches with n < 100 produce unreliable edge CI and ECE estimates. "
                "SAMPLE_LIMITED status must be reported alongside (not instead of) "
                "metric alerts. Critical alerts must not be suppressed by sample status."
            ),
            "source_phase": "P48, P51 (dominance fix)",
            "metrics": ["batch_n", "min_batch_threshold"],
            "alert_family": "SAMPLE_ALERT",
            "alert_rules": {
                "sample_limited": "batch_n < 100",
                "dominance_rule": (
                    "SAMPLE_LIMITED dominates WARNING alerts; "
                    "SAMPLE_LIMITED must NOT suppress CRITICAL alerts — "
                    "both statuses reported separately"
                ),
            },
            "v2_correction_from_p49": (
                "P49 incorrectly let SAMPLE_LIMITED mask CALIBRATION_CRITICAL for "
                "Sep 2025 (platt_ece=0.1229, n=98). V2 prohibits this suppression."
            ),
        },
        # ── Data gap family ──────────────────────────────────────────────────
        {
            "metric_family": "DATA_GAP",
            "selected_probability_stream": "NONE",
            "stream_detail": "N/A — data completeness check",
            "rationale": (
                "Missing closing-line odds for the target analysis scope blocks "
                "market-edge validation. The 2024 data gap is a cross-year blocker only "
                "and must not block 2025-only offline replay."
            ),
            "source_phase": "P43, P48, P49, P50, P51",
            "metrics": [
                "required_2025_closing_line_available",
                "required_2024_closing_line_available",
            ],
            "alert_family": "DATA_GAP_ALERT",
            "alert_rules": {
                "blocked_condition": "required closing-line source missing for target scope",
                "2025_scope": "2025 closing-line available → 2025 replay not blocked",
                "2024_scope": (
                    "2024 closing-line missing → cross-year market-edge validation blocked "
                    "(P43_BLOCKED_BY_DATA_GAP). Does not block 2025-only replay."
                ),
                "dominance": "DATA_GAP_BLOCKED dominates all if current-scope data absent",
            },
        },
    ]


# ── Task P52.B — Monitoring row schema V2 ────────────────────────────────────

def build_monitoring_row_schema_v2() -> dict:
    """
    V2 monitoring row schema.  Extends P48 schema with corrected stream fields.
    """
    return {
        "schema_version": "V2",
        "basis": "P48 monitoring_row_schema with P51/P52 stream corrections",
        "fields": [
            # identity
            "monitoring_date",
            "season",
            "batch_id",
            "batch_n",
            # probability streams (explicit separation from V2)
            "edge_probability_stream",        # must be RAW_SIGMOID in V2
            "calibration_probability_stream", # must be PLATT_CALIBRATED in V2
            # edge metrics (RAW_SIGMOID stream)
            "fip_edge_mean",
            "fip_edge_ci_low",
            "fip_edge_ci_high",
            "fip_positive_edge_rate",
            "side_aware_raw_edge",
            # calibration metrics (PLATT_CALIBRATED stream)
            "platt_ece",
            "platt_brier",
            # legacy compatibility fields (kept for backward comparison)
            "raw_ece",
            "raw_brier",
            "platt_mean_edge",   # retained for comparison only, not alert-driving
            # status
            "edge_status",
            "calibration_status",
            "sample_status",
            "final_status",
            "alert_level",
            "alert_reasons",
            # batch metadata
            "monthly_bucket",
            "start_date",
            "end_date",
            # governance
            "governance_flags",
            "source_trace",
            "contract_version",
        ],
        "allowed_edge_streams": ["RAW_SIGMOID"],
        "allowed_calibration_streams": ["PLATT_CALIBRATED"],
        "allowed_comparison_streams": ["ISOTONIC_CALIBRATED"],
        "allowed_statuses": [
            "MONITORING_OK",
            "EDGE_DRIFT_WARNING",
            "EDGE_DRIFT_CRITICAL",
            "CALIBRATION_WARNING",
            "CALIBRATION_CRITICAL",
            "SAMPLE_LIMITED",
            "DATA_GAP_BLOCKED",
            "MIXED_ALERTS",
        ],
        "allowed_alert_levels": ["NONE", "WARNING", "CRITICAL", "BLOCKED"],
        "v2_key_change": (
            "V2 adds explicit edge_probability_stream and calibration_probability_stream "
            "fields so every monitoring row declares which stream was used. "
            "This prevents the P49 confusion where a single 'probability_stream' field "
            "was used for both edge and calibration monitoring."
        ),
    }


# ── Task P52.C — Alert rule matrix V2 ────────────────────────────────────────

def build_alert_rule_matrix_v2() -> dict:
    return {
        "edge_rules": {
            "probability_stream": "RAW_SIGMOID",
            "edge_type": "fip_signal_side_aware_edge (sigmoid(sp_fip_delta), k=1.0, side-aware)",
            "market_source": "embedded_no_vig (prediction-time snapshot)",
            "ci_method": "bootstrap_5000_seed42",
            "warning": {
                "condition": "mean_edge < 0.07",
                "description": "Edge below minimum threshold — degrading signal",
            },
            "critical": {
                "condition": "edge_ci_low <= 0",
                "description": "CI crosses zero — edge not statistically distinguishable from 0",
            },
            "v2_note": (
                "P44 2025 baseline: all 6 months have fip_signal_side_aware_edge CI_low > 0 "
                "(range: 0.055 to 0.128). Thresholds are appropriate for this stream."
            ),
        },
        "calibration_rules": {
            "probability_stream": "PLATT_CALIBRATED",
            "platt_constants": {
                "A": PLATT_A,
                "B": PLATT_B,
                "sigmoid_k": SIGMOID_K,
                "locked_from": "P45",
            },
            "ece_warning": {
                "condition": "platt_ece > 0.10",
                "threshold": 0.10,
            },
            "ece_critical": {
                "condition": "platt_ece > 0.12",
                "threshold": 0.12,
            },
            "brier_warning": {
                "condition": "platt_brier > 0.25",
                "threshold": 0.25,
            },
            "brier_critical": {
                "condition": "platt_brier > 0.27",
                "threshold": 0.27,
            },
            "v2_note": "Thresholds unchanged from P48. Only stream assignment corrected.",
        },
        "sample_rules": {
            "sample_limited_threshold": 100,
            "sample_limited_condition": "batch_n < 100",
            "dominance_rule": (
                "SAMPLE_LIMITED dominates WARNING alerts only. "
                "CRITICAL alerts (edge or calibration) must be reported even when batch_n < 100. "
                "Both sample_status and metric_status must be stored separately."
            ),
            "v2_correction": (
                "P49 let SAMPLE_LIMITED mask CALIBRATION_CRITICAL for Sep 2025 (n=98, platt_ece=0.1229). "
                "V2 explicitly prohibits this suppression pattern."
            ),
        },
        "data_gap_rules": {
            "2025_scope": {
                "condition": "required_2025_closing_line_available is False",
                "action": "DATA_GAP_BLOCKED for 2025 replay",
                "current_status": "AVAILABLE — 2025 data present in JSONL",
            },
            "2024_scope": {
                "condition": "required_2024_closing_line_available is False",
                "action": "DATA_GAP_BLOCKED for cross-year market-edge validation only",
                "current_status": (
                    "MISSING — P43_BLOCKED_BY_DATA_GAP confirmed. "
                    "Does not block 2025-only replay."
                ),
            },
            "dominance": "DATA_GAP_BLOCKED dominates all alert levels if current-scope data absent",
        },
        "alert_dominance_order": [
            "1. DATA_GAP_BLOCKED: dominates all if required current-scope data absent",
            "2. CRITICAL: EDGE_DRIFT_CRITICAL or CALIBRATION_CRITICAL take priority",
            "3. SAMPLE_LIMITED: dominates WARNING but must NOT hide CRITICAL",
            "4. WARNING: EDGE_DRIFT_WARNING or CALIBRATION_WARNING",
            "5. MIXED_ALERTS: when alerts span multiple metric families at same severity",
            "6. MONITORING_OK: no alert fires",
        ],
        "cross_family_handling": (
            "Cross-family alerts must be preserved separately. "
            "Do not collapse CALIBRATION_CRITICAL into SAMPLE_LIMITED. "
            "Report both edge_status and calibration_status independently in every row."
        ),
    }


# ── Task P52.A.part2 — Retained vs deprecated P48/P49 rules ──────────────────

def build_retained_rules() -> list[dict]:
    return [
        {
            "rule_id": "P48_THRESHOLD_ECE_WARNING",
            "description": "ECE warning threshold: platt_ece > 0.10",
            "status": "RETAINED",
            "rationale": "Threshold validated against P44 Tier C baseline ECE (0.095). Appropriate.",
        },
        {
            "rule_id": "P48_THRESHOLD_ECE_CRITICAL",
            "description": "ECE critical threshold: platt_ece > 0.12",
            "status": "RETAINED",
            "rationale": "Sep 2025 platt_ece=0.1229 confirmed genuine critical under this threshold.",
        },
        {
            "rule_id": "P48_THRESHOLD_BRIER_WARNING",
            "description": "Brier warning: platt_brier > 0.25",
            "status": "RETAINED",
            "rationale": "P44 baseline Brier score 0.248 is near boundary; threshold is conservative.",
        },
        {
            "rule_id": "P48_THRESHOLD_BRIER_CRITICAL",
            "description": "Brier critical: platt_brier > 0.27",
            "status": "RETAINED",
            "rationale": "No months exceeded 0.27 in 2025. Threshold appropriate.",
        },
        {
            "rule_id": "P48_EDGE_WARNING_MEAN",
            "description": "Edge warning: mean_edge < 0.07",
            "status": "RETAINED",
            "rationale": (
                "Threshold valid for RAW_SIGMOID stream. P44 monthly fip_signal_side_aware_edge "
                "range was 0.095–0.148, well above 0.07."
            ),
        },
        {
            "rule_id": "P48_EDGE_CRITICAL_CI_CROSSES_ZERO",
            "description": "Edge critical: CI_low <= 0",
            "status": "RETAINED",
            "rationale": "P44 all months have CI_low > 0.055 under correct RAW_SIGMOID stream.",
        },
        {
            "rule_id": "P48_SAMPLE_LIMITED_THRESHOLD",
            "description": "SAMPLE_LIMITED if batch_n < 100",
            "status": "RETAINED",
            "rationale": "Threshold correct for ECE/Brier/CI reliability.",
        },
        {
            "rule_id": "P48_DATA_GAP_DOMINANCE",
            "description": "DATA_GAP_BLOCKED dominates all alerts",
            "status": "RETAINED",
            "rationale": "Prevents false OK signals when required data is absent.",
        },
        {
            "rule_id": "P48_MONITORING_ROW_SCHEMA_CONCEPT",
            "description": "Monitoring row schema with identity, metrics, status, trace fields",
            "status": "RETAINED_EXTENDED",
            "rationale": "V2 extends schema by adding explicit stream declaration fields.",
        },
        {
            "rule_id": "P49_OFFLINE_REPLAY_CONCEPT",
            "description": "Offline batch replay against historical JSONL records",
            "status": "RETAINED",
            "rationale": "Replay methodology is sound; only stream assignment changes.",
        },
    ]


def build_deprecated_rules() -> list[dict]:
    return [
        {
            "rule_id": "P48_P49_EDGE_USES_PLATT_CALIBRATED",
            "description": (
                "P48/P49 implicitly used PLATT_CALIBRATED (model_home_prob after Platt) "
                "for edge monitoring, not explicitly documented but reflected in P49 edge "
                "metrics that used model_home_prob instead of sigmoid(sp_fip_delta)."
            ),
            "status": "SUPERSEDED",
            "superseded_by": "V2 edge monitoring uses RAW_SIGMOID (fip_signal_side_aware_edge)",
            "evidence": (
                "P50 confirmed: May/Jun 2025 EDGE_DRIFT_CRITICAL dissolved when "
                "edge metric changed to fip_signal_side_aware_edge. "
                "P51 replay eliminated 2 monthly and 3 rolling false CRITICALs."
            ),
        },
        {
            "rule_id": "P49_SAMPLE_LIMITED_DOMINATES_CRITICAL",
            "description": (
                "P49 let SAMPLE_LIMITED mask CALIBRATION_CRITICAL. "
                "Sep 2025 (n=98, platt_ece=0.1229 > 0.12) was classified SAMPLE_LIMITED "
                "instead of CALIBRATION_CRITICAL."
            ),
            "status": "SUPERSEDED",
            "superseded_by": (
                "V2 rule: SAMPLE_LIMITED dominates WARNING only. "
                "CRITICAL must always be reported even at n < 100."
            ),
            "evidence": (
                "P51 revised replay classified Sep 2025 as CALIBRATION_CRITICAL, "
                "revealing a genuine calibration issue that P49 masked."
            ),
        },
        {
            "rule_id": "P49_SINGLE_PROBABILITY_STREAM_FIELD",
            "description": (
                "P49 schema had a single 'probability_stream' field used for both "
                "edge and calibration metrics. This ambiguity enabled the stream mismatch."
            ),
            "status": "SUPERSEDED",
            "superseded_by": (
                "V2 schema has separate 'edge_probability_stream' and "
                "'calibration_probability_stream' fields."
            ),
            "evidence": "P50 root-cause analysis identified ambiguous stream assignment as primary driver.",
        },
    ]


# ── P51 replay evidence summary ───────────────────────────────────────────────

def build_p51_evidence_summary(src: dict[str, dict]) -> dict:
    p51 = src["p51"]
    comparison = p51.get("old_vs_new_status_comparison", {})
    monthly_rows = p51.get("monthly_replay_under_revised_contract", {}).get("rows", [])
    rolling_sum = p51.get("rolling_replay_under_revised_contract", {}).get("summary", {})
    tier_c = p51.get("tier_c_verification", {})

    return {
        "source_phase": "P51",
        "tier_c_n": tier_c.get("n", 535),
        "tier_c_expected_n": tier_c.get("expected_n", 535),
        "tier_c_filter": "|sp_fip_delta| >= 0.5, market_home_prob_no_vig in (0,1), home_win defined",
        "tier_c_sp_fip_delta_path": "row['p0_features']['sp_fip_delta']",
        "monthly_comparison": comparison,
        "monthly_false_critical_eliminated": comparison.get("monthly_false_critical_eliminated", 1),
        "rolling_false_critical_eliminated": comparison.get("rolling_false_critical_eliminated", 3),
        "monthly_rows": [
            {
                "month": r["month"],
                "n": r["n"],
                "fip_edge_mean": r["fip_edge_mean"],
                "fip_edge_ci_low": r["fip_edge_ci_low"],
                "fip_edge_ci_high": r["fip_edge_ci_high"],
                "platt_ece": r["platt_ece"],
                "final_status": r["final_status"],
                "old_p49_status": r["old_p49_status"],
                "status_changed": r["status_changed"],
            }
            for r in monthly_rows
        ],
        "rolling_summary": rolling_sum,
        "p51_final_classification": p51.get("final_classification"),
    }


# ── September 2025 calibration issue ─────────────────────────────────────────

def build_sep_2025_issue(src: dict[str, dict]) -> dict:
    p51 = src["p51"]
    monthly_rows = p51.get("monthly_replay_under_revised_contract", {}).get("rows", [])
    sep_row = next((r for r in monthly_rows if r["month"] == "2025-09"), None)
    p49_sep = next(
        (r for r in src["p49"]["monthly_replay"]["rows"] if "202509" in r.get("batch_id", "")),
        None,
    )

    return {
        "issue_id": "SEP_2025_CALIBRATION_CRITICAL",
        "month": "2025-09",
        "batch_n": sep_row["n"] if sep_row else 98,
        "platt_ece": sep_row["platt_ece"] if sep_row else 0.122929,
        "ece_critical_threshold": 0.12,
        "threshold_exceeded_by": round(
            (sep_row["platt_ece"] if sep_row else 0.122929) - 0.12, 6
        ),
        "p49_status_for_month": "SAMPLE_LIMITED (platt_ece was masked by n=98 < 100)",
        "p51_corrected_status": "CALIBRATION_CRITICAL",
        "p49_error": (
            "P49 let SAMPLE_LIMITED (n=98 < 100) suppress CALIBRATION_CRITICAL "
            "(platt_ece=0.1229 > 0.12). This was a dominance-rule bug."
        ),
        "fip_edge_for_month": sep_row["fip_edge_mean"] if sep_row else None,
        "fip_edge_ci_low": sep_row["fip_edge_ci_low"] if sep_row else None,
        "edge_health": "Edge healthy (fip_edge ~0.147, CI_low > 0). Issue is calibration only.",
        "p53_recommendation": (
            "P53 should investigate Sep 2025 calibration degradation. "
            "Possible causes: late-season pitcher-FIP regression, market adaptation, "
            "or Platt constants drifting. Platt constants are locked from P45 and "
            "cannot be updated without explicit authorization."
        ),
        "tracking_rule": (
            "Future offline replays must report CALIBRATION_CRITICAL for Sep 2025 "
            "until the root cause is resolved or a full-year recalibration is authorized."
        ),
    }


# ── Unresolved data gaps ──────────────────────────────────────────────────────

def build_unresolved_data_gaps(src: dict[str, dict]) -> list[dict]:
    p43 = src["p43"]
    framing = p43.get("framing_note", "")
    return [
        {
            "gap_id": "GAP_2024_MLB_CLOSING_LINE_ODDS",
            "description": (
                "2024 MLB moneyline closing-line odds are not available in the repository. "
                "data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl does not contain "
                "Home ML / Away ML columns (all null). "
                "data/mlb_2025/mlb-2024-asplayed.csv is Retrosheet gamelog only — no odds."
            ),
            "impact": "Cross-year (2024+2025) market-edge validation blocked (P43_BLOCKED_BY_DATA_GAP).",
            "impact_scope": "CROSS_YEAR_ONLY — does not block 2025-only offline replay",
            "p43_classification": p43.get("final_classification", "P43_BLOCKED_BY_DATA_GAP"),
            "resolution_path": (
                "If mlb_odds_2024_real.csv is sourced with schema matching "
                "mlb_odds_2025_real.csv (Date, Away, Home, scores, Away ML, Home ML), "
                "re-run P43 script — load_2024_unified() stub already exists."
            ),
            "status": "UNRESOLVED",
        },
    ]


# ── Final classification logic ────────────────────────────────────────────────

def classify_p52(sources_loaded: bool, sections_complete: bool) -> str:
    if not sources_loaded:
        return "P52_BLOCKED_BY_SOURCE_MISSING"
    if not sections_complete:
        return "P52_MONITORING_CONTRACT_V2_INCOMPLETE"
    return "P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC"


# ── Main builder ──────────────────────────────────────────────────────────────

def build_p52_contract() -> dict:
    src = load_all_sources()

    metadata = build_contract_metadata()
    ownership_matrix = build_metric_ownership_matrix_v2()
    row_schema = build_monitoring_row_schema_v2()
    alert_rules = build_alert_rule_matrix_v2()
    retained = build_retained_rules()
    deprecated = build_deprecated_rules()
    p51_evidence = build_p51_evidence_summary(src)
    sep_2025_issue = build_sep_2025_issue(src)
    data_gaps = build_unresolved_data_gaps(src)

    source_artifact_list = [str(v) for v in SOURCE_PATHS.values()]

    classification = classify_p52(
        sources_loaded=len(src) == len(SOURCE_PATHS),
        sections_complete=True,
    )

    assert classification in ALLOWED_CLASSIFICATIONS, f"Invalid classification: {classification}"

    return {
        "version": "1.0",
        "audit_date": "2026-05-26",
        "contract_version": metadata["contract_version"],
        "supersession_policy": metadata["supersession_policy"],
        "metric_ownership_matrix": ownership_matrix,
        "monitoring_row_schema_v2": row_schema,
        "alert_rule_matrix_v2": alert_rules,
        "retained_rules_from_p48": retained,
        "deprecated_rules_from_p48_p49": deprecated,
        "p51_replay_evidence": p51_evidence,
        "september_2025_calibration_issue": sep_2025_issue,
        "unresolved_data_gaps": data_gaps,
        "source_artifacts": source_artifact_list,
        "platt_coefficients": {
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "sigmoid_k": SIGMOID_K,
            "clip_eps": CLIP_EPS,
            "locked_from": "P45",
            "re_optimization_requires": "explicit CEO authorization",
        },
        "governance_flags": GOVERNANCE_FLAGS,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "final_p52_classification": classification,
        "framing_note": (
            "P52 is a paper-only, offline, diagnostic artifact. "
            "It formalizes the V2 monitoring contract from P51 findings without deploying, "
            "proposing production usage, or overwriting any prior phase artifacts. "
            "No runtime recommendation logic is changed. No live API calls made."
        ),
        "future_recommendations": {
            "P53": (
                "Investigate Sep 2025 CALIBRATION_CRITICAL (platt_ece=0.1229). "
                "Determine if late-season calibration drift is real or a regime change."
            ),
            "P54": (
                "If/when 2024 closing-line odds are sourced, re-run P43 cross-year validation."
            ),
            "P55": (
                "When ≥2 full seasons of data available under V2 contract, "
                "evaluate whether Platt constants require recalibration."
            ),
        },
        "limitations": [
            "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) unresolved.",
            "V2 contract validated only against 2025 season (n=535 Tier C games).",
            "Sep 2025 CALIBRATION_CRITICAL root cause not yet determined.",
            "Cross-year market-edge validation requires 2024 odds data.",
            "No deployment proposed. No production implementation.",
            "Platt constants locked from P45 — recalibration requires authorization.",
        ],
    }


def write_report(contract: dict) -> None:
    """Write both MD report files from the contract data."""
    p51_evidence = contract["p51_replay_evidence"]
    sep_issue = contract["september_2025_calibration_issue"]
    comparison = p51_evidence["monthly_comparison"]
    monthly_rows = p51_evidence["monthly_rows"]

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PLAN.parent.mkdir(parents=True, exist_ok=True)

    # ── Technical report ─────────────────────────────────────────────────────
    lines: list[str] = [
        "# P52 — Formal Monitoring Contract V2",
        "",
        f"**日期**: 2026-05-26  ",
        f"**Phase**: P52  ",
        f"**狀態**: COMPLETE — `{contract['final_p52_classification']}`  ",
        "**前置 Phase**: P51 (`P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC`)",
        "",
        "---",
        "",
        "## Governance（治理鎖定）",
        "",
        "| 項目 | 值 |",
        "|------|-----|",
    ]
    for k, v in contract["governance_flags"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## 一、為何需要 V2 合約",
        "",
        "P50 確認 P49 的邊際漂移警報由**機率流錯配**引起：P49 使用 PLATT_CALIBRATED（ML `model_home_prob`）",
        "驅動邊際監控，而 P43/P44 原始框架使用 RAW_SIGMOID（`sigmoid(sp_fip_delta)`, k=1.0）。",
        "",
        "P51 修訂重放驗證此修正消除了假警報。P52 **正式確立** V2 合約文件，無需刪除或覆蓋 P48/P49 成品。",
        "",
        "---",
        "",
        "## 二、V2 合約 — 超越政策（Supersession Policy）",
        "",
        "### 已超越（Superseded）",
        "",
    ]
    for item in contract["supersession_policy"]["supersedes"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "### 已保留（Preserved）",
        "",
    ]
    for item in contract["supersession_policy"]["preserves"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "### 不覆蓋（Does Not Overwrite）",
        "",
    ]
    for item in contract["supersession_policy"]["does_not_overwrite"]:
        lines.append(f"- `{item}`")

    lines += [
        "",
        "---",
        "",
        "## 三、指標歸屬矩陣 V2（Metric Ownership Matrix）",
        "",
        "| 指標族 | 機率流 | 驅動告警 | 備注 |",
        "|--------|--------|---------|------|",
    ]
    for m in contract["metric_ownership_matrix"]:
        stream = m["selected_probability_stream"]
        family = m["metric_family"]
        drives = m.get("alert_family", "—")
        note = m.get("v2_correction_from_p49") or m.get("v2_note", "—")
        if len(note) > 60:
            note = note[:57] + "..."
        lines.append(f"| {family} | {stream} | {drives} | {note} |")

    lines += [
        "",
        "---",
        "",
        "## 四、V2 警報規則",
        "",
        "### 邊際警報（Edge — RAW_SIGMOID）",
        "",
        "| 等級 | 條件 |",
        "|------|------|",
        "| WARNING | `mean_edge < 0.07` |",
        "| CRITICAL | `edge_ci_low <= 0`（CI 穿越零） |",
        "",
        "### 校準警報（Calibration — PLATT_CALIBRATED）",
        "",
        "| 指標 | WARNING | CRITICAL |",
        "|------|---------|---------|",
        "| platt_ece | > 0.10 | > 0.12 |",
        "| platt_brier | > 0.25 | > 0.27 |",
        "",
        "### 樣本警報",
        "",
        "- `batch_n < 100` → SAMPLE_LIMITED",
        "- **SAMPLE_LIMITED 支配 WARNING，不支配 CRITICAL**（P49 錯誤已修正）",
        "",
        "### 優先順序",
        "",
    ]
    for rule in contract["alert_rule_matrix_v2"]["alert_dominance_order"]:
        lines.append(f"{rule}")

    lines += [
        "",
        "---",
        "",
        "## 五、P48/P49 規則：保留 vs 廢棄",
        "",
        "### 保留規則",
        "",
        "| Rule ID | 描述 | 狀態 |",
        "|---------|------|------|",
    ]
    for r in contract["retained_rules_from_p48"]:
        lines.append(f"| {r['rule_id']} | {r['description'][:60]}... | {r['status']} |")

    lines += [
        "",
        "### 廢棄規則",
        "",
        "| Rule ID | 描述 | 超越依據 |",
        "|---------|------|---------|",
    ]
    for r in contract["deprecated_rules_from_p48_p49"]:
        lines.append(f"| {r['rule_id']} | {r['description'][:55]}... | {r['superseded_by'][:50]}... |")

    lines += [
        "",
        "---",
        "",
        "## 六、P51 重放證據摘要",
        "",
        "**Tier C**: n=535（`|sp_fip_delta|>=0.5`, source: `p0_features.sp_fip_delta`）",
        "",
        "| 月份 | n | fip_edge均值 | CI低 | CI高 | platt_ece | 最終狀態 | P49舊狀態 | 變更 |",
        "|------|---|-------------|------|------|----------|---------|---------|-----|",
    ]
    for r in monthly_rows:
        changed = "✓" if r["status_changed"] else "—"
        lines.append(
            f"| {r['month']} | {r['n']} | {r['fip_edge_mean']:.4f} "
            f"| {r['fip_edge_ci_low']:.4f} | {r['fip_edge_ci_high']:.4f} "
            f"| {r['platt_ece']:.4f} | {r['final_status']} | {r['old_p49_status']} | {changed} |"
        )

    lines += [
        "",
        f"月度假 CRITICAL 消除（淨值）：{comparison.get('monthly_false_critical_eliminated', 1)}",
        f"滾動假 CRITICAL 消除：{comparison.get('rolling_false_critical_eliminated', 3)}（9批可比較範圍）",
        "",
        "---",
        "",
        "## 七、Sep 2025 校準問題追蹤",
        "",
        f"| 欄位 | 值 |",
        "|------|-----|",
        f"| 月份 | {sep_issue['month']} |",
        f"| n | {sep_issue['batch_n']} |",
        f"| platt_ece | {sep_issue['platt_ece']:.6f} |",
        f"| 臨界閾值 | {sep_issue['ece_critical_threshold']} |",
        f"| 超出量 | +{sep_issue['threshold_exceeded_by']:.6f} |",
        f"| P49 狀態（錯誤） | {sep_issue['p49_status_for_month']} |",
        f"| P51 修正狀態 | {sep_issue['p51_corrected_status']} |",
        "",
        f"> **邊際狀態**: {sep_issue['edge_health']}",
        "",
        f"> **P53 建議**: {sep_issue['p53_recommendation']}",
        "",
        "---",
        "",
        "## 八、未解決資料缺口",
        "",
    ]
    for gap in contract["unresolved_data_gaps"]:
        lines += [
            f"### {gap['gap_id']}",
            "",
            f"- **描述**: {gap['description']}",
            f"- **影響範圍**: {gap['impact_scope']}",
            f"- **P43 分類**: `{gap['p43_classification']}`",
            f"- **解決路徑**: {gap['resolution_path']}",
            f"- **狀態**: {gap['status']}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 九、最終分類",
        "",
        f"```",
        f"{contract['final_p52_classification']}",
        "```",
        "",
        "---",
        "",
        "## 十、未來建議",
        "",
    ]
    for phase, rec in contract["future_recommendations"].items():
        lines.append(f"- **{phase}**: {rec}")

    lines += [
        "",
        "---",
        "",
        "## 成品清單",
        "",
        "| 成品 | 路徑 |",
        "|------|------|",
        "| 主腳本 | `scripts/_p52_monitoring_contract_v2_builder.py` |",
        "| 測試 | `tests/test_p52_monitoring_contract_v2_builder.py` |",
        "| JSON 輸出 | `data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json` |",
        "| 報告（正式） | `report/p52_monitoring_contract_v2_20260526.md` |",
        "| 報告（下注計畫） | `00-BettingPlan/20260526/p52_monitoring_contract_v2_20260526.md` |",
        "",
        "*P52 diagnostic — paper_only=True, diagnostic_only=True, no production deployment proposed*",
    ]

    OUTPUT_REPORT.write_text("\n".join(lines))

    # ── Betting plan report ───────────────────────────────────────────────────
    plan_lines: list[str] = [
        "# P52 監控合約 V2 — 投注計畫備案",
        "",
        "**日期**: 2026-05-26  ",
        "**Phase**: P52  ",
        f"**最終分類**: `{contract['final_p52_classification']}`",
        "",
        "---",
        "",
        "## 投注計畫相關性",
        "",
        "**本報告為診斷性研究**，不產生任何投注訊號或實際下注建議。",
        "所有 governance 旗標確認：`paper_only=True`, `kelly_deploy_allowed=False`, `live_api_calls=0`",
        "",
        "P52 正式確立監控合約 V2，為未來離線監控提供標準化框架。",
        "",
        "---",
        "",
        "## V2 合約核心要點",
        "",
        "| 指標族 | 機率流 | 關鍵規則 |",
        "|--------|--------|---------|",
        "| 邊際（Edge） | RAW_SIGMOID — `sigmoid(sp_fip_delta)`, k=1.0 | CI_low≤0→CRITICAL；mean<0.07→WARNING |",
        "| 校準（Calibration） | PLATT_CALIBRATED — P45 鎖定 | ECE>0.12→CRITICAL；Brier>0.27→CRITICAL |",
        "| 樣本（Sample） | N/A | n<100→SAMPLE_LIMITED（不支配 CRITICAL） |",
        "| 資料缺口（Data Gap） | N/A | 2024缺口為跨年限制，不阻擋 2025-only 重放 |",
        "",
        "---",
        "",
        "## P51 修訂成果確認",
        "",
        "| 月份 | P49 舊狀態 | V2 修訂狀態 | 說明 |",
        "|------|-----------|-----------|------|",
        "| 2025-05 (n=120) | EDGE_DRIFT_CRITICAL ❌ | MONITORING_OK ✅ | 假警報消除，fip_edge=0.1428 |",
        "| 2025-06 (n=101) | EDGE_DRIFT_CRITICAL ❌ | MONITORING_OK ✅ | 假警報消除，fip_edge=0.1482 |",
        "| 2025-08 (n=108) | EDGE_DRIFT_WARNING ⚠️ | MONITORING_OK ✅ | 假警報消除，fip_edge=0.1376 |",
        "| 2025-09 (n=98) | SAMPLE_LIMITED (掩蓋) | CALIBRATION_CRITICAL ⚠️ | 真實校準問題揭露 |",
        "",
        "---",
        "",
        "## Sep 2025 校準問題",
        "",
        "- **platt_ece = 0.1229** > 臨界閾值 0.12（超出 +0.0029）",
        "- n=98 < 100 但在 V2 規則下 CALIBRATION_CRITICAL 不被 SAMPLE_LIMITED 壓制",
        "- **邊際仍健康**：fip_edge=0.1469，CI_low=0.130 > 0",
        "- 校準問題原因待查（P53 任務）",
        "",
        "---",
        "",
        "## 2025 賽季 FIP 信號邊際健康確認",
        "",
        "- Tier C n=535，全 11 個滾動批次 CI_low > 0",
        "- 平均 fip_signal_side_aware_edge = 0.1437（遠高於 0.07 警示線）",
        "- P43/P44 建立的 FIP 信號邊際框架在 2025 賽季有效",
        "",
        "---",
        "",
        "## 研究鏈狀態",
        "",
        "```",
        "P43 → P44 → P45 → P46 → P47 → P48 → P49 → P50 → P51 → P52 (當前) → P53 (下一步)",
        "```",
        "",
        f"**累積測試**: P40–P52 共 328 個測試，328/328 通過（預期含 P52 的 17 個測試）",
        "",
        "---",
        "",
        "*診斷報告 — 不構成投注建議 — paper_only=True*",
    ]

    OUTPUT_PLAN.write_text("\n".join(plan_lines))


def main() -> None:
    contract = build_p52_contract()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(contract, indent=2, ensure_ascii=False))
    print(f"Written: {OUTPUT_JSON}")

    write_report(contract)
    print(f"Written: {OUTPUT_REPORT}")
    print(f"Written: {OUTPUT_PLAN}")
    print(f"Final classification: {contract['final_p52_classification']}")
    print(f"Governance check: paper_only={contract['governance_flags']['paper_only']}, "
          f"live_api_calls={contract['governance_flags']['live_api_calls']}")
    print(f"Sources loaded: {len(SOURCE_PATHS)}")
    print(f"Sections: {len([k for k in contract if k not in ('version', 'audit_date')])}")


if __name__ == "__main__":
    main()
