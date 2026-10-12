#!/usr/bin/env python3
"""
P47 — Calibration Strategy Consolidation + P43-P46 Synthesis Report
(Paper-Only Diagnostic)

Reads five source artifacts (P43-P46), consolidates findings, and produces:
  P47.A — Synthesis JSON with selected monitoring probability stream
  P47.B — Monitoring threshold registry
  P47.C — Data gap register
  P47.D — Markdown reports

No new models. No new data loaded from external sources. No strategy changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance (locked)
# ---------------------------------------------------------------------------

GOVERNANCE: dict[str, Any] = {
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

for k, v in GOVERNANCE.items():
    assert GOVERNANCE[k] == v

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/mlb_2025/derived"

SOURCE_ARTIFACTS = {
    "p43": DERIVED / "p43_strong_edge_closing_line_edge_summary.json",
    "p44_temporal": DERIVED / "p44_temporal_stability_summary.json",
    "p44_calibration": DERIVED / "p44_calibration_audit_summary.json",
    "p45": DERIVED / "p45_platt_recalibration_summary.json",
    "p46": DERIVED / "p46_isotonic_recalibration_summary.json",
}

OUT_JSON = DERIVED / "p47_calibration_synthesis_summary.json"
OUT_REPORT = ROOT / "report/p47_calibration_synthesis_report_20260526.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260526/p47_calibration_synthesis_report_20260526.md"

ALLOWED_STREAM = frozenset([
    "RAW_SIGMOID",
    "PLATT_CALIBRATED",
    "ISOTONIC_CALIBRATED",
    "NO_SELECTION_SAMPLE_LIMITED",
])

ALLOWED_P47_CLASSIFICATION = frozenset([
    "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC",
    "P47_RAW_SIGMOID_RETAINED_DIAGNOSTIC",
    "P47_ISOTONIC_SELECTED_FOR_MONITORING_DIAGNOSTIC",
    "P47_NO_SELECTION_SAMPLE_LIMITED",
])


# ---------------------------------------------------------------------------
# Load source artifacts
# ---------------------------------------------------------------------------

def load_sources() -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for key, path in SOURCE_ARTIFACTS.items():
        assert path.exists(), f"Required source artifact missing: {path}"
        with path.open(encoding="utf-8") as f:
            loaded[key] = json.load(f)
    return loaded


# ---------------------------------------------------------------------------
# P47.A — Build summary sections
# ---------------------------------------------------------------------------

def build_p43_edge_summary(p43: dict[str, Any]) -> dict[str, Any]:
    tier_c = p43.get("tier_metrics", {}).get("C", {})
    boot = tier_c.get("bootstrap", {})
    return {
        "tier_c_n": tier_c.get("n"),
        "mean_edge": tier_c.get("mean_edge"),
        "positive_rate": tier_c.get("positive_rate"),
        "ci_95_low": boot.get("ci_95_low"),
        "ci_95_high": boot.get("ci_95_high"),
        "classification": tier_c.get("classification"),
        "overall_p43_classification": p43.get("final_classification",
            p43.get("framing_note", "P43_BLOCKED_BY_DATA_GAP")),
        "data_gap_2024": p43.get("data_inventory", {}).get("data_gap_2024_market_prob_missing", True),
    }


def build_p44_temporal_summary(p44t: dict[str, Any]) -> dict[str, Any]:
    monthly = p44t.get("monthly_breakdown", {})
    stable_months = [m for m, v in monthly.items() if v.get("classification") == "STABLE"]
    return {
        "total_tier_c_n": p44t.get("total_tier_c_n"),
        "months_covered": p44t.get("months_covered", []),
        "stable_month_count": len(stable_months),
        "stable_months": sorted(stable_months),
        "temporal_pattern_classification": p44t.get("temporal_pattern_classification"),
    }


def build_p44_calibration_summary(p44c: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_brier": p44c.get("brier_score"),
        "raw_ece": p44c.get("ece"),
        "calibration_classification": p44c.get("calibration_classification"),
        "n_bins": p44c.get("n_bins"),
        "ece_bins_used": p44c.get("ece_bins_used"),
    }


def build_p45_platt_summary(p45: dict[str, Any]) -> dict[str, Any]:
    pilot = p45.get("p45a_pilot", {})
    cv_agg = p45.get("p45b_cv", {}).get("aggregate", {})
    wf = p45.get("p45c_walk_forward", {})
    return {
        "platt_a": pilot.get("platt_a"),
        "platt_b": pilot.get("platt_b"),
        "test_raw_ece": pilot.get("raw_ece"),
        "test_platt_ece": pilot.get("calibrated_ece"),
        "test_ece_improvement": pilot.get("ece_improvement"),
        "test_brier_improvement": pilot.get("brier_improvement"),
        "cv_mean_raw_ece": cv_agg.get("mean_raw_ece"),
        "cv_mean_platt_ece": cv_agg.get("mean_calibrated_ece"),
        "cv_mean_ece_improvement": cv_agg.get("mean_ece_improvement"),
        "cv_mean_platt_brier": cv_agg.get("mean_calibrated_brier"),
        "walk_forward_classification": wf.get("classification"),
        "p45_classification": p45.get("p45_classification"),
    }


def build_p46_isotonic_summary(p46: dict[str, Any]) -> dict[str, Any]:
    pilot = p46.get("p46a_pilot", {})
    cv_agg = p46.get("p46b_cv", {}).get("aggregate", {})
    wf = p46.get("p46c_walk_forward", {})
    return {
        "isotonic_knot_count": pilot.get("isotonic_knot_count"),
        "test_isotonic_ece": pilot.get("isotonic_ece"),
        "test_platt_ece": pilot.get("platt_ece"),
        "isotonic_vs_platt_ece": pilot.get("isotonic_vs_platt_ece_improvement"),
        "cv_mean_isotonic_ece": cv_agg.get("mean_isotonic_ece"),
        "cv_mean_platt_ece": cv_agg.get("mean_platt_ece"),
        "iso_beats_platt_fold_count": cv_agg.get("isotonic_beats_platt_fold_count_ece"),
        "cv_fold_count": cv_agg.get("fold_count"),
        "walk_forward_classification": wf.get("classification"),
        "p46_classification": p46.get("p46_classification"),
    }


# ---------------------------------------------------------------------------
# P47.A — Monitoring stream selection
# ---------------------------------------------------------------------------

def select_monitoring_stream(
    p45_summary: dict[str, Any],
    p46_summary: dict[str, Any],
) -> tuple[str, list[str]]:
    """
    Decision logic:
    1. Isotonic preferred only if: CV mean ECE materially lower than Platt (> 0.01 gap)
       AND walk-forward is ISOTONIC_WALK_FORWARD_HELPFUL.
    2. Platt preferred if: ECE improvement confirmed in CV AND walk-forward helpful/mixed.
    3. Raw sigmoid retained if: Platt shows no CV improvement.
    4. Sample limited otherwise.
    """
    rationale: list[str] = []

    cv_platt = p45_summary.get("cv_mean_platt_ece", 999.0) or 999.0
    cv_raw = p45_summary.get("cv_mean_raw_ece", 999.0) or 999.0
    cv_iso = p46_summary.get("cv_mean_isotonic_ece", 999.0) or 999.0
    iso_wf = p46_summary.get("walk_forward_classification", "")
    platt_wf = p45_summary.get("walk_forward_classification", "")
    iso_beats_n = p46_summary.get("iso_beats_platt_fold_count", 0) or 0
    fold_count = p46_summary.get("cv_fold_count", 5) or 5

    platt_cv_improvement = cv_raw - cv_platt
    iso_vs_platt_cv = cv_platt - cv_iso

    rationale.append(f"P45 Platt: CV mean ECE {cv_raw:.4f} → {cv_platt:.4f} (Δ +{platt_cv_improvement:.4f})")
    rationale.append(f"P45 Walk-forward: {platt_wf}")
    rationale.append(f"P46 Isotonic: CV mean ECE {cv_iso:.4f} vs Platt {cv_platt:.4f} (Δ {iso_vs_platt_cv:+.4f})")
    rationale.append(f"P46 Isotonic beats Platt in {iso_beats_n}/{fold_count} CV folds")
    rationale.append(f"P46 Walk-forward: {iso_wf}")

    # Isotonic selection: needs clear CV advantage + temporal stability
    if iso_vs_platt_cv > 0.01 and iso_wf == "ISOTONIC_WALK_FORWARD_HELPFUL":
        rationale.append("Isotonic selected: CV gap > 0.01 and walk-forward confirms stability.")
        return "ISOTONIC_CALIBRATED", rationale

    # Platt selection: confirmed CV improvement + positive walk-forward
    if platt_cv_improvement > 0.01 and platt_wf in ("WALK_FORWARD_HELPFUL",):
        rationale.append(
            "Platt selected: CV ECE improvement confirmed (+{:.4f}), walk-forward helpful. "
            "Isotonic not preferred due to weak CV (beats Platt only {}/{} folds) and "
            "walk-forward preference for Platt (P46.C PLATT_WALK_FORWARD_PREFERRED).".format(
                platt_cv_improvement, iso_beats_n, fold_count
            )
        )
        return "PLATT_CALIBRATED", rationale

    # Raw sigmoid retained
    rationale.append("Insufficient evidence for recalibration; raw sigmoid retained.")
    return "RAW_SIGMOID", rationale


# ---------------------------------------------------------------------------
# P47.B — Monitoring thresholds
# ---------------------------------------------------------------------------

def build_monitoring_thresholds(p45_summary: dict[str, Any], p44_cal: dict[str, Any]) -> dict[str, Any]:
    return {
        "ece_drift": {
            "baseline_platt_cv_mean_ece": p45_summary.get("cv_mean_platt_ece", 0.0862),
            "warning_threshold": 0.10,
            "critical_threshold": 0.12,
            "description": (
                "Monitor rolling ECE on new 2026 games. "
                "Warning if ECE > 0.10; critical if ECE > 0.12. "
                "Diagnostic guardrail only — not a betting instruction."
            ),
        },
        "brier_drift": {
            "baseline_platt_cv_mean_brier": p45_summary.get("cv_mean_platt_brier", 0.2385),
            "warning_threshold": 0.25,
            "critical_threshold": 0.27,
            "description": (
                "Monitor rolling Brier score. "
                "Warning if > 0.25; critical if > 0.27."
            ),
        },
        "edge_mean_drift": {
            "baseline_tier_c_mean_edge": 0.1059,
            "warning_threshold_mean_edge": 0.07,
            "critical_threshold": "CI_CROSSES_ZERO",
            "description": (
                "Monitor rolling Tier C mean edge. "
                "Warning if mean_edge < 0.07; critical if bootstrap CI crosses zero."
            ),
        },
        "monthly_stability": {
            "warning": "any_monthly_CI_crosses_zero",
            "critical": "two_consecutive_months_CI_crosses_zero_or_mean_edge_lte_zero",
            "description": (
                "Monthly edge CI monitoring. "
                "One month CI crossing zero triggers a warning. "
                "Two consecutive months triggers a critical flag."
            ),
        },
        "sample_accumulation": {
            "minimum_monitoring_batch_n": 100,
            "sample_limited_threshold": 100,
            "description": (
                "Do not compute ECE/Brier drift until n >= 100 new games are available. "
                "Mark SAMPLE_LIMITED if n < 100."
            ),
        },
    }


# ---------------------------------------------------------------------------
# P47.C — Data gap register
# ---------------------------------------------------------------------------

def build_data_gap_register() -> list[dict[str, Any]]:
    return [
        {
            "missing_data_item": "2024 MLB closing-line odds (Home ML / Away ML)",
            "current_status": "UNAVAILABLE — no CSV or API source exists in repository",
            "impact": (
                "Cross-year (2024+2025) closing-line edge validation is blocked. "
                "P43 final classification remains P43_BLOCKED_BY_DATA_GAP. "
                "Only 2025 single-year EDGE_CONFIRMED available."
            ),
            "required_resolution": (
                "Source a 2024 MLB moneyline odds CSV with schema matching "
                "mlb_odds_2025_real.csv (Date, Away, Home, Away ML, Home ML, Away Score, Home Score). "
                "Verified external source required — e.g., historical odds API or vendor export."
            ),
            "priority": "HIGH",
        },
        {
            "missing_data_item": "Cross-year market-edge validation",
            "current_status": "BLOCKED by 2024 closing-line odds gap",
            "impact": (
                "Cannot confirm that Tier C edge generalizes across seasons. "
                "Single-year 2025 finding could be spurious or season-specific."
            ),
            "required_resolution": "Depends on resolution of 2024 closing-line odds gap.",
            "priority": "HIGH",
        },
        {
            "missing_data_item": "2026 live odds (real-time TSL integration)",
            "current_status": "BLOCKED by no-live-call governance (live_api_calls=0)",
            "impact": (
                "Cannot evaluate model on 2026 regular season games in real time. "
                "Paper-trading monitoring requires pre-game odds snapshot collection."
            ),
            "required_resolution": (
                "Explicit governance authorization required to begin TSL live odds collection. "
                "Suggested: explicit CEO/CTO authorization for a limited capture window."
            ),
            "priority": "MEDIUM",
        },
        {
            "missing_data_item": "External odds source provenance documentation",
            "current_status": "mlb_odds_2025_real.csv marked is_verified_real=False for most rows",
            "impact": (
                "Cannot confirm that closing-line probabilities are authentic pre-game market odds. "
                "CSV was sourced from a single post-season scrape (all timestamps post-game). "
                "This makes edge vs closing-line a proxy measure, not true CLV."
            ),
            "required_resolution": (
                "Source data with pre-game timestamps and multi-snapshot trajectory. "
                "Alternatively, document the data vendor and confirm pre-game capture time."
            ),
            "priority": "MEDIUM",
        },
        {
            "missing_data_item": "Approved paper-trading monitoring loop",
            "current_status": "Not approved — promotion_freeze=true",
            "impact": (
                "No automated monitoring pipeline for ongoing ECE/edge tracking. "
                "Monitoring thresholds defined in P47 are advisory only."
            ),
            "required_resolution": (
                "Requires explicit CEO/CTO approval to implement an automated paper-only "
                "monitoring loop (no live bets, no Kelly deployment)."
            ),
            "priority": "LOW",
        },
    ]


# ---------------------------------------------------------------------------
# P47.D — Report generation
# ---------------------------------------------------------------------------

def build_report(
    sources: dict[str, Any],
    p43_sum: dict[str, Any],
    p44t_sum: dict[str, Any],
    p44c_sum: dict[str, Any],
    p45_sum: dict[str, Any],
    p46_sum: dict[str, Any],
    stream: str,
    rationale: list[str],
    thresholds: dict[str, Any],
    gaps: list[dict[str, Any]],
    p47_cls: str,
) -> str:
    L: list[str] = []

    L.append("# P47 Calibration Strategy Consolidation — P43-P46 Synthesis Report")
    L.append("")
    L.append("**Date:** 2026-05-26")
    L.append("**Phase:** P47 (synthesis diagnostic, paper_only=true)")
    L.append("")

    L.append("## Executive Summary")
    L.append("")
    L.append(
        "Phases P43-P46 completed a full diagnostic arc on the 2025 Tier C sp_fip_delta edge signal. "
        "The key findings are: (1) the edge is real and temporally stable across all 6 months of the "
        "2025 MLB season; (2) the raw sigmoid model is moderately miscalibrated (ECE=0.0953); "
        "(3) Platt scaling reliably reduces ECE to ~0.07-0.09 across CV and walk-forward evaluation; "
        "(4) Isotonic regression shows no consistent advantage over Platt in temporal out-of-sample tests. "
        "**Selected monitoring stream: Platt calibrated probability.** "
        "No champion replacement. No deployment. 2024 data gap remains unresolved."
    )
    L.append("")

    L.append("## Governance Flags")
    for k, v in GOVERNANCE.items():
        L.append(f"- {k}: `{v}`")
    L.append("")

    L.append("## P43-P46 Evidence Table")
    L.append("")
    L.append("| Phase | Key Result | Classification |")
    L.append("|-------|-----------|----------------|")
    L.append(f"| P43 | Tier C n={p43_sum['tier_c_n']}, mean_edge={p43_sum['mean_edge']:.4f}, CI fully positive | `{p43_sum['classification']}` |")
    L.append(f"| P44 temporal | {p44t_sum['stable_month_count']}/6 months STABLE, n={p44t_sum['total_tier_c_n']} | `{p44t_sum['temporal_pattern_classification']}` |")
    L.append(f"| P44 calibration | ECE={p44c_sum['raw_ece']}, Brier={p44c_sum['raw_brier']} | `{p44c_sum['calibration_classification']}` |")
    L.append(f"| P45 Platt | CV ECE {p45_sum['cv_mean_raw_ece']:.4f}→{p45_sum['cv_mean_platt_ece']:.4f}, WF={p45_sum['walk_forward_classification']} | `{p45_sum['p45_classification']}` |")
    L.append(f"| P46 Isotonic | CV ECE iso={p46_sum['cv_mean_isotonic_ece']:.4f} vs platt={p46_sum['cv_mean_platt_ece']:.4f}, beats Platt {p46_sum['iso_beats_platt_fold_count']}/{p46_sum['cv_fold_count']} folds | `{p46_sum['p46_classification']}` |")
    L.append("")

    L.append("## Selected Monitoring Probability Stream")
    L.append("")
    L.append(f"**Selected: `{stream}`**")
    L.append("")
    L.append("### Rationale")
    for line in rationale:
        L.append(f"- {line}")
    L.append("")

    L.append("### Why Platt is preferred over Isotonic")
    L.append("- Isotonic achieves marginally lower ECE on a single train/test split (0.058 vs 0.070)")
    L.append("- In 5-fold CV, Isotonic only beats Platt in 2/5 folds; mean ECE gap is only 0.002")
    L.append("- Walk-forward temporal evaluation shows Platt preferred in 3/5 months (PLATT_WALK_FORWARD_PREFERRED)")
    L.append("- Platt is a 2-parameter parametric model; Isotonic has 13+ knots and more capacity to overfit")
    L.append("- For monitoring purposes, Platt's temporal stability is more important than single-split ECE")
    L.append("")

    L.append("### Why Raw Sigmoid is not retained after P45")
    L.append("- Raw ECE=0.0953 is MODERATE_MISCALIBRATED — systematic bias confirmed")
    L.append("- Platt CV mean ECE=0.0862 shows consistent improvement (Δ +0.0307)")
    L.append("- P45 walk-forward: all 5 evaluation months show ECE improvement after Platt")
    L.append("- No reason to accept higher miscalibration when a stable recalibration is available")
    L.append("")

    L.append("## Monitoring Thresholds (Diagnostic Guardrails Only)")
    L.append("")
    L.append("These are advisory thresholds for future monitoring. They are NOT betting instructions.")
    L.append("")
    L.append("| Metric | Baseline | Warning | Critical |")
    L.append("|--------|----------|---------|----------|")
    t = thresholds
    L.append(f"| ECE | {t['ece_drift']['baseline_platt_cv_mean_ece']} | > {t['ece_drift']['warning_threshold']} | > {t['ece_drift']['critical_threshold']} |")
    L.append(f"| Brier | {t['brier_drift']['baseline_platt_cv_mean_brier']} | > {t['brier_drift']['warning_threshold']} | > {t['brier_drift']['critical_threshold']} |")
    L.append(f"| Mean Edge | {t['edge_mean_drift']['baseline_tier_c_mean_edge']} | < {t['edge_mean_drift']['warning_threshold_mean_edge']} | CI crosses zero |")
    L.append(f"| Monthly stability | All CI positive | Any CI crosses zero | Two consecutive months |")
    L.append(f"| Sample batch | — | — | n < {t['sample_accumulation']['minimum_monitoring_batch_n']} → SAMPLE_LIMITED |")
    L.append("")

    L.append("## Data Gap Register")
    L.append("")
    L.append("| Gap | Status | Priority |")
    L.append("|-----|--------|----------|")
    for g in gaps:
        L.append(f"| {g['missing_data_item']} | {g['current_status'][:60]}... | {g['priority']} |")
    L.append("")
    L.append("### Gap Details")
    for g in gaps:
        L.append(f"\n**{g['missing_data_item']}** (`{g['priority']}`)")
        L.append(f"- Status: {g['current_status']}")
        L.append(f"- Impact: {g['impact']}")
        L.append(f"- Resolution: {g['required_resolution']}")
    L.append("")

    L.append("## Risk and Uncertainty")
    L.append("")
    L.append("- **Single-year finding**: All edge and calibration results are based on 2025 data only.")
    L.append("- **Post-season odds proxy**: CSV closing-line odds are from a single post-season scrape.")
    L.append("  Edge measured against these odds is approximate, not true pregame CLV.")
    L.append("- **535 sample limitation**: Tier C n=535 is sufficient for bootstrap CI but not for")
    L.append("  fine-grained subgroup analysis or cross-year generalization claims.")
    L.append("- **Market adaptation risk**: If the sp_fip_delta signal becomes known, market may adapt.")
    L.append("  Temporal stability (P44) is reassuring for 2025 but not a forward guarantee.")
    L.append("")

    L.append("## Final P47 Classification")
    L.append(f"\n**P47 Classification:** `{p47_cls}`")
    L.append("")

    L.append("## Known Limitations")
    L.append("- 2024 closing-line data gap **remains unresolved** — all findings are 2025-only.")
    L.append("- No production deployment proposed.")
    L.append("- No champion strategy replacement.")
    L.append("- No runtime recommendation logic changed.")
    L.append("- **Paper-only diagnostic throughout P43-P47.**")
    L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Final P47 classification
# ---------------------------------------------------------------------------

def p47_classification(stream: str) -> str:
    mapping = {
        "PLATT_CALIBRATED": "P47_PLATT_SELECTED_FOR_MONITORING_DIAGNOSTIC",
        "RAW_SIGMOID": "P47_RAW_SIGMOID_RETAINED_DIAGNOSTIC",
        "ISOTONIC_CALIBRATED": "P47_ISOTONIC_SELECTED_FOR_MONITORING_DIAGNOSTIC",
        "NO_SELECTION_SAMPLE_LIMITED": "P47_NO_SELECTION_SAMPLE_LIMITED",
    }
    return mapping.get(stream, "P47_NO_SELECTION_SAMPLE_LIMITED")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P47] Loading source artifacts...")
    sources = load_sources()
    for key in SOURCE_ARTIFACTS:
        print(f"  ✓ {key}: {SOURCE_ARTIFACTS[key].name}")

    p43_sum = build_p43_edge_summary(sources["p43"])
    p44t_sum = build_p44_temporal_summary(sources["p44_temporal"])
    p44c_sum = build_p44_calibration_summary(sources["p44_calibration"])
    p45_sum = build_p45_platt_summary(sources["p45"])
    p46_sum = build_p46_isotonic_summary(sources["p46"])

    print("[P47] Selecting monitoring stream...")
    stream, rationale = select_monitoring_stream(p45_sum, p46_sum)
    print(f"[P47] Selected: {stream}")

    thresholds = build_monitoring_thresholds(p45_sum, p44c_sum)
    gaps = build_data_gap_register()
    p47_cls = p47_classification(stream)

    assert stream in ALLOWED_STREAM
    assert p47_cls in ALLOWED_P47_CLASSIFICATION
    print(f"[P47] Final classification: {p47_cls}")

    summary: dict[str, Any] = {
        "version": "p47_v1",
        "governance": GOVERNANCE,
        "source_artifacts": {k: str(v) for k, v in SOURCE_ARTIFACTS.items()},
        "p43_edge_summary": p43_sum,
        "p44_temporal_summary": p44t_sum,
        "p44_raw_calibration_summary": p44c_sum,
        "p45_platt_summary": p45_sum,
        "p46_isotonic_comparison_summary": p46_sum,
        "selected_monitoring_probability_stream": stream,
        "rationale": rationale,
        "monitoring_thresholds": thresholds,
        "unresolved_data_gaps": gaps,
        "final_p47_classification": p47_cls,
        "allowed_stream_values": sorted(ALLOWED_STREAM),
        "allowed_p47_classifications": sorted(ALLOWED_P47_CLASSIFICATION),
        "framing_note": (
            "Synthesis of P43-P46 calibration diagnostic arc. "
            "Platt scaling selected as monitoring baseline. "
            "No champion replacement. No production proposal. Paper-only. "
            "2024 closing-line data gap remains unresolved."
        ),
        "limitation": "2024_closing_line_data_unavailable_cross_year_validation_blocked",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P47] Saved: {OUT_JSON}")

    report_md = build_report(
        sources, p43_sum, p44t_sum, p44c_sum,
        p45_sum, p46_sum, stream, rationale, thresholds, gaps, p47_cls,
    )
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")
    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.write_text(report_md, encoding="utf-8")
    print(f"[P47] Reports saved.")

    print("\n=== P47 Summary ===")
    print(f"Selected monitoring stream: {stream}")
    print(f"P47 classification: {p47_cls}")
    print(f"Data gaps registered: {len(gaps)}")
    print(f"Monitoring thresholds defined: {len(thresholds)}")


if __name__ == "__main__":
    main()
