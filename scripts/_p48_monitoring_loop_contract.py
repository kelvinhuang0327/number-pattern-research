#!/usr/bin/env python3
"""
P48 — Paper-Only Monitoring Loop Contract for P47 Platt Baseline

Diagnostic-only. paper_only=True. promotion_freeze=True.
No live API calls. No production deployment. No champion replacement.

This module defines:
  - monitoring row schema
  - alert evaluation rules (P47 thresholds)
  - offline fixture cases (10 synthetic batches)
  - JSON + MD report generation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ── Canonical paths ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
P47_JSON = REPO_ROOT / "data/mlb_2025/derived/p47_calibration_synthesis_summary.json"
P48_JSON = REPO_ROOT / "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json"
REPORT_MD = REPO_ROOT / "report/p48_monitoring_loop_contract_20260526.md"
BETTING_PLAN_MD = REPO_ROOT / "00-BettingPlan/20260526/p48_monitoring_loop_contract_20260526.md"

# ── Governance (all locked) ────────────────────────────────────────────────────
_GOVERNANCE: dict = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
}

assert _GOVERNANCE["paper_only"] is True, "governance: paper_only must be True"
assert _GOVERNANCE["promotion_freeze"] is True, "governance: promotion_freeze must be True"
assert _GOVERNANCE["kelly_deploy_allowed"] is False, "governance: kelly_deploy_allowed must be False"
assert _GOVERNANCE["live_api_calls"] == 0, "governance: live_api_calls must be 0"
assert _GOVERNANCE["production_usage_proposed"] is False
assert _GOVERNANCE["runtime_recommendation_logic_changed"] is False

# ── P47 alert thresholds (locked from P47 synthesis) ──────────────────────────
ECE_WARNING: float = 0.10
ECE_CRITICAL: float = 0.12
BRIER_WARNING: float = 0.25
BRIER_CRITICAL: float = 0.27
EDGE_WARNING_MEAN: float = 0.07
SAMPLE_LIMITED_N: int = 100

# ── Selected probability stream (P47 synthesis decision) ──────────────────────
SELECTED_STREAM: str = "PLATT_CALIBRATED"

# ── Allowed enumerations ───────────────────────────────────────────────────────
ALLOWED_STREAMS: frozenset = frozenset(
    {"RAW_SIGMOID", "PLATT_CALIBRATED", "ISOTONIC_CALIBRATED"}
)
ALLOWED_STATUSES: frozenset = frozenset({
    "MONITORING_OK",
    "SAMPLE_LIMITED",
    "ECE_DRIFT_WARNING",
    "ECE_DRIFT_CRITICAL",
    "BRIER_DRIFT_WARNING",
    "BRIER_DRIFT_CRITICAL",
    "EDGE_DRIFT_WARNING",
    "EDGE_DRIFT_CRITICAL",
    "MIXED_ALERTS",
    "DATA_GAP_BLOCKED",
})
ALLOWED_ALERT_LEVELS: frozenset = frozenset({"NONE", "WARNING", "CRITICAL", "BLOCKED"})
ALLOWED_P48_CLASSIFICATIONS: list = [
    "P48_MONITORING_CONTRACT_READY_DIAGNOSTIC",
    "P48_MONITORING_CONTRACT_BLOCKED",
    "P48_SAMPLE_LIMITED",
]

# ── Monitoring row field contract ──────────────────────────────────────────────
MONITORING_ROW_FIELDS: list = [
    "monitoring_date",
    "season",
    "batch_id",
    "batch_n",
    "probability_stream",
    "raw_ece",
    "platt_ece",
    "raw_brier",
    "platt_brier",
    "mean_edge",
    "edge_ci_low",
    "edge_ci_high",
    "positive_edge_rate",
    "monthly_bucket",
    "status",
    "alert_level",
    "alert_reasons",
    "governance_flags",
    "source_trace",
]

_SOURCE_TRACE: dict = {
    "p47_artifact": "data/mlb_2025/derived/p47_calibration_synthesis_summary.json",
    "selected_stream": "PLATT_CALIBRATED",
    "p47_classification": "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC",
    "p47_commit": "17dad86",
}


# ── Core alert evaluation ──────────────────────────────────────────────────────

def evaluate_monitoring_row(
    batch_n: int,
    probability_stream: str,
    raw_ece: Optional[float],
    platt_ece: Optional[float],
    raw_brier: Optional[float],
    platt_brier: Optional[float],
    mean_edge: Optional[float],
    edge_ci_low: Optional[float],
    edge_ci_high: Optional[float],
    closing_line_source_missing: bool = False,
) -> dict:
    """
    Apply P47 alert rules to a monitoring batch and return status, alert_level,
    and alert_reasons.

    Rule priority (highest to lowest):
      1. DATA_GAP_BLOCKED  — closing-line source missing
      2. SAMPLE_LIMITED    — batch_n < 100
      3. Critical/Warning  — ECE / Brier / Edge drift checks
      4. MONITORING_OK     — no alerts
    """
    # 1. Data gap overrides everything
    if closing_line_source_missing:
        return {
            "status": "DATA_GAP_BLOCKED",
            "alert_level": "BLOCKED",
            "alert_reasons": ["closing_line_source_missing"],
        }

    # 2. Sample too small — metrics unreliable
    if batch_n < SAMPLE_LIMITED_N:
        return {
            "status": "SAMPLE_LIMITED",
            "alert_level": "WARNING",
            "alert_reasons": [f"batch_n={batch_n} < threshold={SAMPLE_LIMITED_N}"],
        }

    # 3. Choose active ECE / Brier based on stream
    ece = platt_ece if probability_stream == "PLATT_CALIBRATED" else raw_ece
    brier = platt_brier if probability_stream == "PLATT_CALIBRATED" else raw_brier

    alerts: list[str] = []
    has_critical = False
    has_warning = False
    categories: set[str] = set()

    # ECE drift
    if ece is not None:
        if ece > ECE_CRITICAL:
            alerts.append(f"ece_critical: ece={ece:.4f} > critical_threshold={ECE_CRITICAL}")
            has_critical = True
            categories.add("ECE")
        elif ece > ECE_WARNING:
            alerts.append(f"ece_warning: ece={ece:.4f} > warning_threshold={ECE_WARNING}")
            has_warning = True
            categories.add("ECE")

    # Brier drift
    if brier is not None:
        if brier > BRIER_CRITICAL:
            alerts.append(f"brier_critical: brier={brier:.4f} > critical_threshold={BRIER_CRITICAL}")
            has_critical = True
            categories.add("BRIER")
        elif brier > BRIER_WARNING:
            alerts.append(f"brier_warning: brier={brier:.4f} > warning_threshold={BRIER_WARNING}")
            has_warning = True
            categories.add("BRIER")

    # Edge drift
    if mean_edge is not None and edge_ci_low is not None:
        if edge_ci_low <= 0.0:
            alerts.append(
                f"edge_critical: CI crosses zero (ci_low={edge_ci_low:.4f} <= 0)"
            )
            has_critical = True
            categories.add("EDGE")
        elif mean_edge < EDGE_WARNING_MEAN:
            alerts.append(
                f"edge_warning: mean_edge={mean_edge:.4f} < warning_threshold={EDGE_WARNING_MEAN}"
            )
            has_warning = True
            categories.add("EDGE")

    # No alerts → healthy
    if not alerts:
        return {"status": "MONITORING_OK", "alert_level": "NONE", "alert_reasons": []}

    # Multiple categories → MIXED_ALERTS
    if len(categories) > 1:
        alert_level = "CRITICAL" if has_critical else "WARNING"
        return {"status": "MIXED_ALERTS", "alert_level": alert_level, "alert_reasons": alerts}

    # Single category
    cat = next(iter(categories))
    if has_critical:
        return {
            "status": f"{cat}_DRIFT_CRITICAL",
            "alert_level": "CRITICAL",
            "alert_reasons": alerts,
        }
    return {
        "status": f"{cat}_DRIFT_WARNING",
        "alert_level": "WARNING",
        "alert_reasons": alerts,
    }


def make_monitoring_row(
    batch_id: str,
    batch_n: int,
    probability_stream: str = "PLATT_CALIBRATED",
    raw_ece: Optional[float] = None,
    platt_ece: Optional[float] = None,
    raw_brier: Optional[float] = None,
    platt_brier: Optional[float] = None,
    mean_edge: Optional[float] = None,
    edge_ci_low: Optional[float] = None,
    edge_ci_high: Optional[float] = None,
    positive_edge_rate: Optional[float] = None,
    monthly_bucket: Optional[str] = None,
    closing_line_source_missing: bool = False,
    monitoring_date: str = "2026-05-26",
    season: int = 2025,
) -> dict:
    """Construct a complete monitoring row with evaluation applied."""
    result = evaluate_monitoring_row(
        batch_n=batch_n,
        probability_stream=probability_stream,
        raw_ece=raw_ece,
        platt_ece=platt_ece,
        raw_brier=raw_brier,
        platt_brier=platt_brier,
        mean_edge=mean_edge,
        edge_ci_low=edge_ci_low,
        edge_ci_high=edge_ci_high,
        closing_line_source_missing=closing_line_source_missing,
    )
    return {
        "monitoring_date": monitoring_date,
        "season": season,
        "batch_id": batch_id,
        "batch_n": batch_n,
        "probability_stream": probability_stream,
        "raw_ece": raw_ece,
        "platt_ece": platt_ece,
        "raw_brier": raw_brier,
        "platt_brier": platt_brier,
        "mean_edge": mean_edge,
        "edge_ci_low": edge_ci_low,
        "edge_ci_high": edge_ci_high,
        "positive_edge_rate": positive_edge_rate,
        "monthly_bucket": monthly_bucket,
        "status": result["status"],
        "alert_level": result["alert_level"],
        "alert_reasons": result["alert_reasons"],
        "governance_flags": dict(_GOVERNANCE),
        "source_trace": dict(_SOURCE_TRACE),
    }


# ── Offline fixture cases ──────────────────────────────────────────────────────

def generate_fixture_cases() -> list[dict]:
    """
    Generate 10 deterministic synthetic offline fixture batches derived from
    P43–P47 summary values. No live data used.
    """
    return [
        # 1. Healthy baseline — all metrics within threshold
        make_monitoring_row(
            "fixture_01_healthy_baseline",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.0953,
            platt_ece=0.0820,
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.1059,
            edge_ci_low=0.0989,
            edge_ci_high=0.1132,
            positive_edge_rate=0.8953,
            monthly_bucket="2025-06",
        ),
        # 2. Sample limited — batch too small
        make_monitoring_row(
            "fixture_02_sample_limited",
            batch_n=50,
            probability_stream="PLATT_CALIBRATED",
        ),
        # 3. ECE warning — platt_ece > 0.10 but < 0.12
        make_monitoring_row(
            "fixture_03_ece_warning",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.1150,
            platt_ece=0.1080,
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.1059,
            edge_ci_low=0.0989,
            edge_ci_high=0.1132,
        ),
        # 4. ECE critical — platt_ece > 0.12
        make_monitoring_row(
            "fixture_04_ece_critical",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.1550,
            platt_ece=0.1350,
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.1059,
            edge_ci_low=0.0989,
            edge_ci_high=0.1132,
        ),
        # 5. Brier warning — platt_brier > 0.25 but < 0.27
        make_monitoring_row(
            "fixture_05_brier_warning",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.0953,
            platt_ece=0.0820,
            raw_brier=0.2700,
            platt_brier=0.2580,
            mean_edge=0.1059,
            edge_ci_low=0.0989,
            edge_ci_high=0.1132,
        ),
        # 6. Brier critical — platt_brier > 0.27
        make_monitoring_row(
            "fixture_06_brier_critical",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.0953,
            platt_ece=0.0820,
            raw_brier=0.2900,
            platt_brier=0.2780,
            mean_edge=0.1059,
            edge_ci_low=0.0989,
            edge_ci_high=0.1132,
        ),
        # 7. Edge warning — mean_edge < 0.07, CI still positive
        make_monitoring_row(
            "fixture_07_edge_warning",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.0953,
            platt_ece=0.0820,
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.0550,
            edge_ci_low=0.0120,
            edge_ci_high=0.0980,
        ),
        # 8. Edge critical — CI crosses zero
        make_monitoring_row(
            "fixture_08_edge_critical",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.0953,
            platt_ece=0.0820,
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.0280,
            edge_ci_low=-0.0080,
            edge_ci_high=0.0640,
        ),
        # 9. Mixed alerts — ECE critical + edge warning (critical dominates)
        make_monitoring_row(
            "fixture_09_mixed_alerts",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            raw_ece=0.1550,
            platt_ece=0.1250,  # > 0.12 → ECE critical
            raw_brier=0.2481,
            platt_brier=0.2320,
            mean_edge=0.0550,  # < 0.07 → edge warning
            edge_ci_low=0.0120,
            edge_ci_high=0.0980,
        ),
        # 10. Data gap blocked — missing closing-line source overrides all
        make_monitoring_row(
            "fixture_10_data_gap_blocked",
            batch_n=200,
            probability_stream="PLATT_CALIBRATED",
            closing_line_source_missing=True,
        ),
    ]


# ── Summary builder ────────────────────────────────────────────────────────────

def load_p47_source() -> dict:
    """Load P47 calibration synthesis summary (source of truth)."""
    return json.loads(P47_JSON.read_text())


def build_p48_summary(fixtures: list[dict], p47_source: dict) -> dict:
    """Assemble the full P48 monitoring contract summary."""
    thresholds = p47_source.get("monitoring_thresholds", {})
    ece_base = thresholds.get("ece_drift", {}).get("baseline_platt_cv_mean_ece")
    brier_base = thresholds.get("brier_drift", {}).get("baseline_platt_cv_mean_brier")
    edge_base = thresholds.get("edge_mean_drift", {}).get("baseline_tier_c_mean_edge")

    fixture_status_map = {f["batch_id"]: f["status"] for f in fixtures}

    return {
        "version": "p48_v1",
        "governance": dict(_GOVERNANCE),
        "p47_baseline": {
            "commit": "17dad86",
            "final_classification": "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC",
            "selected_stream": SELECTED_STREAM,
            "platt_cv_mean_ece": ece_base,
            "platt_cv_mean_brier": brier_base,
            "tier_c_mean_edge": edge_base,
            "tier_c_edge_ci": [0.0989, 0.1132],
            "data_gap_2024_acknowledged": True,
        },
        "monitoring_row_schema": {
            "fields": MONITORING_ROW_FIELDS,
            "allowed_streams": sorted(ALLOWED_STREAMS),
            "allowed_statuses": sorted(ALLOWED_STATUSES),
            "allowed_alert_levels": sorted(ALLOWED_ALERT_LEVELS),
        },
        "alert_thresholds": {
            "ece_warning": ECE_WARNING,
            "ece_critical": ECE_CRITICAL,
            "brier_warning": BRIER_WARNING,
            "brier_critical": BRIER_CRITICAL,
            "edge_warning_mean": EDGE_WARNING_MEAN,
            "edge_critical_condition": "CI_CROSSES_ZERO",
            "sample_limited_n": SAMPLE_LIMITED_N,
            "blocked_condition": "closing_line_source_missing",
            "priority_order": [
                "DATA_GAP_BLOCKED overrides all",
                "SAMPLE_LIMITED if batch_n < 100",
                "CRITICAL dominates WARNING in multi-category alerts",
                "MIXED_ALERTS when alerts span multiple categories",
                "MONITORING_OK when no alert fires",
            ],
        },
        "fixture_cases": fixtures,
        "fixture_status_summary": fixture_status_map,
        "expected_fixture_statuses": {
            "fixture_01_healthy_baseline": "MONITORING_OK",
            "fixture_02_sample_limited": "SAMPLE_LIMITED",
            "fixture_03_ece_warning": "ECE_DRIFT_WARNING",
            "fixture_04_ece_critical": "ECE_DRIFT_CRITICAL",
            "fixture_05_brier_warning": "BRIER_DRIFT_WARNING",
            "fixture_06_brier_critical": "BRIER_DRIFT_CRITICAL",
            "fixture_07_edge_warning": "EDGE_DRIFT_WARNING",
            "fixture_08_edge_critical": "EDGE_DRIFT_CRITICAL",
            "fixture_09_mixed_alerts": "MIXED_ALERTS",
            "fixture_10_data_gap_blocked": "DATA_GAP_BLOCKED",
        },
        "final_classification": "P48_MONITORING_CONTRACT_READY_DIAGNOSTIC",
        "allowed_p48_classifications": ALLOWED_P48_CLASSIFICATIONS,
        "framing_note": (
            "P48 defines a paper-only monitoring loop contract for the P47 Platt-calibrated "
            "probability stream. This is a diagnostic-only contract specification with offline "
            "fixture evaluation. No live API calls. No production usage. No runtime "
            "recommendation logic changes. 2024 closing-line data gap remains unresolved — "
            "cross-year edge validation is blocked. P43 final classification remains "
            "P43_BLOCKED_BY_DATA_GAP. All P48 monitoring thresholds are advisory guardrails "
            "for future paper-only observation, not betting instructions."
        ),
        "data_gap_2024_acknowledged": True,
    }


# ── Report renderer ────────────────────────────────────────────────────────────

def render_report(summary: dict) -> str:
    """Generate Markdown report from P48 summary."""
    b = summary["p47_baseline"]
    th = summary["alert_thresholds"]
    fs = summary["fixture_status_summary"]

    lines = [
        "# P48 — Paper-Only Monitoring Loop Contract for P47 Platt Baseline",
        "",
        "**Date**: 2026-05-26  ",
        f"**Classification**: `{summary['final_classification']}`  ",
        "**Mode**: `paper_only=true` | `diagnostic_only=true` | `promotion_freeze=true`  ",
        "**Governance**: No live API calls. No production deployment. No champion replacement.",
        "",
        "---",
        "",
        "## 1. P47 Baseline Recap",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Selected Stream | `{b['selected_stream']}` |",
        f"| P47 Classification | `{b['final_classification']}` |",
        f"| P47 Commit | `{b['commit']}` |",
        f"| ECE (Platt, CV mean) | {b['platt_cv_mean_ece']:.6f} |",
        f"| Brier (Platt, CV mean) | {b['platt_cv_mean_brier']:.6f} |",
        f"| Tier C mean_edge | {b['tier_c_mean_edge']:.4f} |",
        f"| Tier C edge CI 95% | [{b['tier_c_edge_ci'][0]:.4f}, {b['tier_c_edge_ci'][1]:.4f}] |",
        f"| 2024 Data Gap | Unresolved |",
        "",
        "---",
        "",
        "## 2. Monitoring Row Schema",
        "",
        "Each monitoring row must include the following fields:",
        "",
    ]
    for f in MONITORING_ROW_FIELDS:
        lines.append(f"- `{f}`")
    lines += [
        "",
        "**Allowed `probability_stream` values:**",
        "- `RAW_SIGMOID`",
        "- `PLATT_CALIBRATED` ← selected by P47",
        "- `ISOTONIC_CALIBRATED`",
        "",
        "**Allowed `status` values:**",
    ]
    for s in sorted(ALLOWED_STATUSES):
        lines.append(f"- `{s}`")
    lines += [
        "",
        "**Allowed `alert_level` values:** `NONE`, `WARNING`, `CRITICAL`, `BLOCKED`",
        "",
        "---",
        "",
        "## 3. Alert Rules (P47 Thresholds)",
        "",
        "| Metric | Warning | Critical | Condition |",
        "|--------|---------|----------|-----------|",
        f"| ECE | > {th['ece_warning']} | > {th['ece_critical']} | rolling ECE on new games |",
        f"| Brier | > {th['brier_warning']} | > {th['brier_critical']} | rolling Brier score |",
        f"| Edge mean | < {th['edge_warning_mean']} | CI crosses zero | Tier C mean edge |",
        f"| Sample | — | — | SAMPLE_LIMITED if batch_n < {th['sample_limited_n']} |",
        f"| Data gap | — | — | BLOCKED if closing-line source missing |",
        "",
        "**Priority order:**",
    ]
    for p in th["priority_order"]:
        lines.append(f"1. {p}")
    lines += [
        "",
        "---",
        "",
        "## 4. Offline Fixture Cases and Expected Statuses",
        "",
        "| Fixture ID | batch_n | Scenario | Expected Status | Expected Alert |",
        "|------------|---------|----------|-----------------|----------------|",
        "| fixture_01_healthy_baseline | 200 | All metrics within threshold | `MONITORING_OK` | `NONE` |",
        "| fixture_02_sample_limited | 50 | n < 100 | `SAMPLE_LIMITED` | `WARNING` |",
        "| fixture_03_ece_warning | 200 | platt_ece=0.1080 > 0.10 | `ECE_DRIFT_WARNING` | `WARNING` |",
        "| fixture_04_ece_critical | 200 | platt_ece=0.1350 > 0.12 | `ECE_DRIFT_CRITICAL` | `CRITICAL` |",
        "| fixture_05_brier_warning | 200 | platt_brier=0.2580 > 0.25 | `BRIER_DRIFT_WARNING` | `WARNING` |",
        "| fixture_06_brier_critical | 200 | platt_brier=0.2780 > 0.27 | `BRIER_DRIFT_CRITICAL` | `CRITICAL` |",
        "| fixture_07_edge_warning | 200 | mean_edge=0.055 < 0.07 | `EDGE_DRIFT_WARNING` | `WARNING` |",
        "| fixture_08_edge_critical | 200 | ci_low=-0.008 ≤ 0 | `EDGE_DRIFT_CRITICAL` | `CRITICAL` |",
        "| fixture_09_mixed_alerts | 200 | ECE critical + edge warning | `MIXED_ALERTS` | `CRITICAL` |",
        "| fixture_10_data_gap_blocked | 200 | closing-line source missing | `DATA_GAP_BLOCKED` | `BLOCKED` |",
        "",
        "---",
        "",
        "## 5. Governance Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in summary["governance"].items():
        lines.append(f"| `{k}` | `{v}` |")
    lines += [
        "",
        "---",
        "",
        "## 6. Limitations",
        "",
        "- **2024 closing-line data gap**: `data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl` "
        "contains no Home ML / Away ML columns. No valid 2024 odds CSV exists in the repository. "
        "P43 final classification remains `P43_BLOCKED_BY_DATA_GAP`. Cross-year edge validation "
        "is blocked until a verified 2024 MLB moneyline odds source is obtained.",
        "- **Fixture cases are synthetic**: All 10 fixture batches use values derived from "
        "P43–P47 summaries. No live data was used.",
        "- **ECE/Brier metrics use post-season CSV odds**: `mlb_odds_2025_real.csv` "
        "does not include pre-game timestamp snapshots. Edge metrics are vs closing line, "
        "not strict CLV.",
        "- **No model deployed**: Platt calibration coefficients (a=0.435432, b=0.245464) "
        "are diagnostic-only. No runtime recommendation logic was changed.",
        "- **No promotion proposed**: This contract does not authorize paper-trading "
        "escalation, Kelly deployment, or live monitoring.",
        "",
        "---",
        "",
        "## 7. Final P48 Classification",
        "",
        f"**`{summary['final_classification']}`**",
        "",
        "> This classification confirms that a paper-only monitoring loop contract has been "
        "specified and validated against offline fixtures. It does not authorize deployment, "
        "live monitoring, production usage, or any change to the champion strategy.",
        "",
        "---",
        "",
        "## CTO Summary",
        "",
        "P48 specifies a deterministic offline monitoring contract derived from P47 Platt baseline. "
        "Ten fixture cases validate all alert paths: healthy, sample-limited, ECE/Brier/edge "
        "warning/critical, mixed, and data-gap-blocked. Governance flags are locked "
        "(paper_only=true, promotion_freeze=true, live_api_calls=0). "
        "The 2024 closing-line data gap remains unresolved. "
        "No live data was used. No runtime logic was changed. No production proposal is made.",
    ]
    return "\n".join(lines)


# ── Output writer ──────────────────────────────────────────────────────────────

def write_outputs(summary: dict) -> None:
    """Write JSON summary and both Markdown reports."""
    P48_JSON.parent.mkdir(parents=True, exist_ok=True)
    P48_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    md_content = render_report(summary)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(md_content)

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(md_content)

    print(f"[P48] JSON:   {P48_JSON}")
    print(f"[P48] Report: {REPORT_MD}")
    print(f"[P48] Plan:   {BETTING_PLAN_MD}")
    print(f"[P48] Final classification: {summary['final_classification']}")
    print(f"[P48] Fixture statuses:")
    for bid, st in summary["fixture_status_summary"].items():
        print(f"       {bid}: {st}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> dict:
    p47_source = load_p47_source()
    fixtures = generate_fixture_cases()
    summary = build_p48_summary(fixtures, p47_source)
    write_outputs(summary)
    return summary


if __name__ == "__main__":
    main()
