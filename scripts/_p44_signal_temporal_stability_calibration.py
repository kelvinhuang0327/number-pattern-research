#!/usr/bin/env python3
"""
P44 — Signal Temporal Stability + Calibration Audit (Paper-Only)

Governance:
  - No live API calls
  - No optimization / no promotion
  - Uses locked sigmoid mapping: p(home) = sigmoid(0.8 * sp_fip_delta)
  - Tier C only: |sp_fip_delta| >= 0.50 with closing-line market prob

Two analyses:
  P44.A — Monthly temporal edge breakdown (Apr–Sep 2025)
  P44.B — 10-bin reliability calibration audit
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Governance (locked — must match P43)
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "T_LOCKED": 0.50,
    "live_api_calls": 0,
    "no_champion_modification": True,
}

assert GOVERNANCE["paper_only"] is True
assert GOVERNANCE["diagnostic_only"] is True
assert GOVERNANCE["promotion_freeze"] is True
assert GOVERNANCE["kelly_deploy_allowed"] is False
assert GOVERNANCE["live_api_calls"] == 0

ROOT = Path(__file__).resolve().parents[1]
FILE_2025_PHASE56 = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
FILE_2025_CLOSING = ROOT / "data/mlb_2025/mlb_odds_2025_real.csv"

OUT_TEMPORAL = ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"
OUT_CALIBRATION = ROOT / "data/mlb_2025/derived/p44_calibration_audit_summary.json"
OUT_REPORT = ROOT / "report/p44_signal_temporal_stability_calibration_20260525.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260525/p44_signal_temporal_stability_calibration_20260525.md"

SEED = 42
N_BOOT = 5_000
SIGMOID_K = 0.8
TIER_C_THRESHOLD = 0.50
NEUTRAL_EPS = 0.005
N_CALIB_BINS = 10
MIN_BIN_FOR_ECE = 5


@dataclass
class JoinedRecord:
    game_date: str          # "YYYY-MM-DD"
    month: str              # "YYYY-MM"
    sp_fip_delta: float
    model_prob: float       # sigmoid(0.8 * sp_fip_delta)
    market_home_prob: float
    actual_home_win: int    # 0 or 1
    edge: float             # model_side_prob - market_side_prob


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float, k: float = SIGMOID_K) -> float:
    return 1.0 / (1.0 + math.exp(-k * x))


def american_to_prob(odds_text: str | None) -> float | None:
    if odds_text is None:
        return None
    s = str(odds_text).strip()
    if not s:
        return None
    try:
        odds = int(s)
    except ValueError:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    if odds < 0:
        a = abs(odds)
        return a / (a + 100.0)
    return None


def closing_market_home_prob(home_ml: str | None, away_ml: str | None) -> float | None:
    hp = american_to_prob(home_ml)
    ap = american_to_prob(away_ml)
    if hp is None or ap is None:
        return None
    s = hp + ap
    if s <= 0:
        return None
    return hp / s


def edge_for_model_side(model_home_prob: float, market_home_prob: float) -> float:
    if model_home_prob >= 0.5:
        return model_home_prob - market_home_prob
    else:
        return (1.0 - model_home_prob) - (1.0 - market_home_prob)


def bootstrap_mean_ci(
    values: list[float],
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> dict[str, float]:
    n = len(values)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[int(0.975 * len(means))]
    return {
        "n_boot": n_boot,
        "mean_boot": sum(means) / len(means),
        "ci_95_low": lo,
        "ci_95_high": hi,
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tier_c_records() -> tuple[list[JoinedRecord], dict[str, int]]:
    """Load 2025 closing-line joined records filtered to Tier C (|delta| >= 0.50)."""
    # Build market lookup
    market: dict[tuple[str, str, str], dict[str, str]] = {}
    with FILE_2025_CLOSING.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (str(row.get("Date", "")), str(row.get("Away", "")), str(row.get("Home", "")))
            market[key] = dict(row)

    inv = {
        "phase56_rows": 0,
        "phase56_quality_rows": 0,
        "phase56_joined_rows": 0,
        "phase56_tier_c_rows": 0,
        "phase56_missing_market_rows": 0,
    }

    records: list[JoinedRecord] = []
    with FILE_2025_PHASE56.open("r", encoding="utf-8") as f:
        for line in f:
            inv["phase56_rows"] += 1
            r = json.loads(line)
            p0 = r.get("p0_features", {})

            # Quality filter (same as P43)
            if not p0.get("sp_fip_delta_available"):
                continue
            if p0.get("sp_context_source", "") == "league_average_fallback":
                continue
            delta = p0.get("sp_fip_delta")
            if delta is None or r.get("home_win") is None:
                continue
            inv["phase56_quality_rows"] += 1

            key = (str(r.get("game_date", "")), str(r.get("away_team", "")), str(r.get("home_team", "")))
            market_row = market.get(key)
            if market_row is None:
                inv["phase56_missing_market_rows"] += 1
                continue

            mkt_prob = closing_market_home_prob(market_row.get("Home ML"), market_row.get("Away ML"))
            if mkt_prob is None:
                inv["phase56_missing_market_rows"] += 1
                continue

            hs = market_row.get("Home Score")
            aw = market_row.get("Away Score")
            if hs is None or aw is None or str(hs).strip() == "" or str(aw).strip() == "":
                inv["phase56_missing_market_rows"] += 1
                continue

            inv["phase56_joined_rows"] += 1

            # Tier C filter
            if abs(float(delta)) < TIER_C_THRESHOLD:
                continue
            inv["phase56_tier_c_rows"] += 1

            game_date = str(r.get("game_date", ""))
            model_prob = _sigmoid(float(delta))
            actual = int(int(hs) > int(aw))
            edge = edge_for_model_side(model_prob, mkt_prob)

            records.append(JoinedRecord(
                game_date=game_date,
                month=game_date[:7] if len(game_date) >= 7 else "unknown",
                sp_fip_delta=float(delta),
                model_prob=model_prob,
                market_home_prob=mkt_prob,
                actual_home_win=actual,
                edge=edge,
            ))

    return records, inv


# ---------------------------------------------------------------------------
# P44.A — Temporal stability
# ---------------------------------------------------------------------------

def _classify_month(mean_edge: float, ci_low: float, ci_high: float, n: int) -> str:
    if n < 15:
        return "SAMPLE_LIMITED"
    if ci_low > 0:
        return "STABLE"
    if mean_edge > 0 and ci_high > 0:
        return "WEAK"
    return "NEGATIVE"


def _classify_temporal_pattern(monthly: dict[str, dict[str, Any]]) -> str:
    valid = [v for v in monthly.values() if v["classification"] != "SAMPLE_LIMITED"]
    if len(valid) < 3:
        return "SAMPLE_LIMITED"

    stable_count = sum(1 for v in valid if v["classification"] == "STABLE")
    weak_count = sum(1 for v in valid if v["classification"] == "WEAK")
    neg_count = sum(1 for v in valid if v["classification"] == "NEGATIVE")

    total = len(valid)
    if stable_count == total:
        return "TEMPORAL_STABLE"
    if neg_count > total * 0.5:
        return "DEGRADING"
    if stable_count > total * 0.5:
        return "TEMPORAL_STABLE"
    if stable_count >= 1 and neg_count >= 1:
        return "MIXED"
    if weak_count + stable_count == total:
        return "IMPROVING"
    return "MIXED"


def temporal_stability_analysis(records: list[JoinedRecord]) -> dict[str, Any]:
    # Group by month
    by_month: dict[str, list[float]] = defaultdict(list)
    for r in records:
        by_month[r.month].append(r.edge)

    monthly: dict[str, dict[str, Any]] = {}
    for month in sorted(by_month.keys()):
        edges = by_month[month]
        n = len(edges)
        m = sum(edges) / n
        if n == 1:
            std = 0.0
        else:
            std = math.sqrt(sum((x - m) ** 2 for x in edges) / (n - 1))
        pos_rate = sum(1 for e in edges if e > 0) / n

        if n >= 2:
            boot = bootstrap_mean_ci(edges, n_boot=N_BOOT, seed=SEED)
            ci_low = boot["ci_95_low"]
            ci_high = boot["ci_95_high"]
        else:
            boot = None
            ci_low = float("nan")
            ci_high = float("nan")

        cls = _classify_month(m, ci_low, ci_high, n)

        monthly[month] = {
            "month": month,
            "n": n,
            "mean_edge": round(m, 6),
            "std_edge": round(std, 6),
            "positive_rate": round(pos_rate, 4),
            "bootstrap_ci_low": round(ci_low, 6) if not math.isnan(ci_low) else None,
            "bootstrap_ci_high": round(ci_high, 6) if not math.isnan(ci_high) else None,
            "bootstrap_n_boot": N_BOOT,
            "classification": cls,
        }

    overall = _classify_temporal_pattern(monthly)

    return {
        "version": "p44_temporal_v1",
        "governance": GOVERNANCE,
        "tier_c_threshold": TIER_C_THRESHOLD,
        "total_tier_c_n": len(records),
        "months_covered": sorted(by_month.keys()),
        "monthly_breakdown": monthly,
        "temporal_pattern_classification": overall,
        "framing_note": (
            "Temporal edge stability of Tier C (|sp_fip_delta| >= 0.50) vs closing-line market. "
            "2024 closing-line data gap remains unresolved — this analysis covers 2025 only."
        ),
        "limitation": "2024_closing_line_data_unavailable",
    }


# ---------------------------------------------------------------------------
# P44.B — Calibration audit
# ---------------------------------------------------------------------------

def calibration_audit(records: list[JoinedRecord]) -> dict[str, Any]:
    n_total = len(records)

    # Build 10-bin reliability table on model_prob
    bin_edges = [i / N_CALIB_BINS for i in range(N_CALIB_BINS + 1)]
    bins: list[dict[str, Any]] = []

    for i in range(N_CALIB_BINS):
        lo = bin_edges[i]
        hi = bin_edges[i + 1]
        in_bin = [r for r in records if lo <= r.model_prob < hi]
        # Include the last point in the last bin
        if i == N_CALIB_BINS - 1:
            in_bin = [r for r in records if lo <= r.model_prob <= hi]
        n_bin = len(in_bin)
        if n_bin == 0:
            bins.append({
                "bin_low": round(lo, 2),
                "bin_high": round(hi, 2),
                "n": 0,
                "predicted_mean": None,
                "actual_win_rate": None,
                "calibration_gap": None,
            })
        else:
            pred_mean = sum(r.model_prob for r in in_bin) / n_bin
            actual_rate = sum(r.actual_home_win for r in in_bin) / n_bin
            bins.append({
                "bin_low": round(lo, 2),
                "bin_high": round(hi, 2),
                "n": n_bin,
                "predicted_mean": round(pred_mean, 4),
                "actual_win_rate": round(actual_rate, 4),
                "calibration_gap": round(pred_mean - actual_rate, 4),
            })

    # Brier score
    brier = sum((r.model_prob - r.actual_home_win) ** 2 for r in records) / n_total if n_total > 0 else float("nan")

    # ECE — only bins with n >= MIN_BIN_FOR_ECE
    ece_numerator = 0.0
    ece_bins_used = 0
    for b in bins:
        if b["n"] is not None and b["n"] >= MIN_BIN_FOR_ECE:
            ece_numerator += (b["n"] / n_total) * abs(b["calibration_gap"])
            ece_bins_used += 1
    ece = ece_numerator

    # Calibration classification
    if ece < 0.05:
        cal_cls = "WELL_CALIBRATED"
    elif ece < 0.10:
        cal_cls = "MODERATE_MISCALIBRATED"
    else:
        cal_cls = "OVERCONFIDENT_OR_MISCALIBRATED"

    return {
        "version": "p44_calibration_v1",
        "governance": GOVERNANCE,
        "tier_c_threshold": TIER_C_THRESHOLD,
        "total_tier_c_n": n_total,
        "n_bins": N_CALIB_BINS,
        "min_bin_for_ece": MIN_BIN_FOR_ECE,
        "reliability_table": bins,
        "brier_score": round(brier, 6) if not math.isnan(brier) else None,
        "ece": round(ece, 6),
        "ece_bins_used": ece_bins_used,
        "calibration_classification": cal_cls,
        "framing_note": (
            "Calibration of sigmoid model (p = sigmoid(0.8 * sp_fip_delta)) on 2025 Tier C games. "
            "Model probability is the locked mapping — not post-hoc recalibrated. "
            "2024 closing-line data gap remains unresolved."
        ),
        "limitation": "2024_closing_line_data_unavailable",
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _star(cls: str) -> str:
    icons = {"STABLE": "✅", "TEMPORAL_STABLE": "✅", "WEAK": "⚠️", "NEGATIVE": "❌",
             "SAMPLE_LIMITED": "⚠️", "MIXED": "⚠️", "DEGRADING": "❌", "IMPROVING": "📈"}
    return icons.get(cls, "")


def build_report(
    inv: dict[str, int],
    temporal: dict[str, Any],
    calib: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# P44 Signal Temporal Stability + Calibration Audit")
    lines.append("")
    lines.append("**Date:** 2026-05-25")
    lines.append("**Phase:** P44 (diagnostic-only, paper_only=true)")
    lines.append("")

    lines.append("## Governance Flags")
    g = GOVERNANCE
    lines.append(f"- paper_only: `{g['paper_only']}`")
    lines.append(f"- diagnostic_only: `{g['diagnostic_only']}`")
    lines.append(f"- promotion_freeze: `{g['promotion_freeze']}`")
    lines.append(f"- kelly_deploy_allowed: `{g['kelly_deploy_allowed']}`")
    lines.append(f"- live_api_calls: `{g['live_api_calls']}`")
    lines.append("")

    lines.append("## Data Inventory")
    lines.append(f"- Source: `mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl`")
    lines.append(f"- Closing odds: `mlb_odds_2025_real.csv`")
    lines.append(f"- Phase56 rows: {inv['phase56_rows']}")
    lines.append(f"- Quality rows (delta available, not fallback): {inv['phase56_quality_rows']}")
    lines.append(f"- Joined rows (with closing-line market): {inv['phase56_joined_rows']}")
    lines.append(f"- Tier C rows (|delta| >= 0.50): {inv['phase56_tier_c_rows']}")
    lines.append("")

    lines.append("## P44.A — Monthly Temporal Edge Breakdown (Tier C)")
    lines.append("")
    lines.append("| Month | n | Mean Edge | Std | Pos Rate | CI Low | CI High | Classification |")
    lines.append("|-------|---|-----------|-----|----------|--------|---------|----------------|")
    for month, d in temporal["monthly_breakdown"].items():
        ci_lo = f"{d['bootstrap_ci_low']:.4f}" if d["bootstrap_ci_low"] is not None else "N/A"
        ci_hi = f"{d['bootstrap_ci_high']:.4f}" if d["bootstrap_ci_high"] is not None else "N/A"
        icon = _star(d["classification"])
        lines.append(
            f"| {month} | {d['n']} | {d['mean_edge']:.4f} | {d['std_edge']:.4f} | "
            f"{d['positive_rate']:.3f} | {ci_lo} | {ci_hi} | {icon} {d['classification']} |"
        )
    lines.append("")
    lines.append(f"**Overall Temporal Pattern:** {_star(temporal['temporal_pattern_classification'])} "
                 f"`{temporal['temporal_pattern_classification']}`")
    lines.append("")

    lines.append("## P44.B — Calibration Audit (Tier C, 10-bin)")
    lines.append("")
    lines.append("| Bin | n | Predicted Mean | Actual Win Rate | Gap |")
    lines.append("|-----|---|----------------|-----------------|-----|")
    for b in calib["reliability_table"]:
        if b["n"] == 0:
            lines.append(f"| [{b['bin_low']:.1f}, {b['bin_high']:.1f}) | 0 | — | — | — |")
        else:
            lines.append(
                f"| [{b['bin_low']:.1f}, {b['bin_high']:.1f}) | {b['n']} | "
                f"{b['predicted_mean']:.4f} | {b['actual_win_rate']:.4f} | "
                f"{b['calibration_gap']:+.4f} |"
            )
    lines.append("")
    lines.append(f"**Brier Score:** `{calib['brier_score']}`")
    lines.append(f"**ECE:** `{calib['ece']}` (bins used: {calib['ece_bins_used']})")
    lines.append(f"**Calibration Classification:** {_star(calib['calibration_classification'])} "
                 f"`{calib['calibration_classification']}`")
    lines.append("")

    lines.append("## Final P44 Classification")
    lines.append("")
    temporal_cls = temporal["temporal_pattern_classification"]
    cal_cls = calib["calibration_classification"]

    if temporal_cls in ("TEMPORAL_STABLE",) and cal_cls == "WELL_CALIBRATED":
        p44_cls = "P44_STABLE_AND_CALIBRATED"
    elif temporal_cls == "DEGRADING" or cal_cls == "OVERCONFIDENT_OR_MISCALIBRATED":
        p44_cls = "P44_REQUIRES_FURTHER_DIAGNOSIS"
    else:
        p44_cls = "P44_MODERATE — further monitoring warranted"

    lines.append(f"**P44 Classification:** `{p44_cls}`")
    lines.append("")

    lines.append("## Known Limitations")
    lines.append("- 2024 closing-line data gap **remains unresolved** — temporal analysis covers 2025 only.")
    lines.append("- CSV closing-line odds are from a single post-season scrape; no pregame trajectory available.")
    lines.append("- This is edge vs closing-line, NOT strict CLV.")
    lines.append("- Sigmoid model is the locked P40/P41/P42 mapping; no post-hoc recalibration applied.")
    lines.append("- **No production deployment proposal. No champion replacement. Paper-only.**")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P44] Loading Tier C joined records...")
    records, inv = load_tier_c_records()
    print(f"[P44] Tier C records loaded: {len(records)}")

    print("[P44.A] Running temporal stability analysis...")
    temporal = temporal_stability_analysis(records)

    print("[P44.B] Running calibration audit...")
    calib = calibration_audit(records)

    # Save JSON outputs
    OUT_TEMPORAL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TEMPORAL.open("w", encoding="utf-8") as f:
        json.dump(temporal, f, indent=2, ensure_ascii=False)
    print(f"[P44] Saved: {OUT_TEMPORAL}")

    with OUT_CALIBRATION.open("w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2, ensure_ascii=False)
    print(f"[P44] Saved: {OUT_CALIBRATION}")

    # Generate reports
    report_md = build_report(inv, temporal, calib)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")
    print(f"[P44] Saved report: {OUT_REPORT}")

    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.write_text(report_md, encoding="utf-8")
    print(f"[P44] Saved betting plan: {OUT_BETTINGPLAN}")

    # Console summary
    print("\n=== P44 Summary ===")
    print(f"Tier C n: {inv['phase56_tier_c_rows']}")
    print(f"Months covered: {temporal['months_covered']}")
    print(f"Temporal pattern: {temporal['temporal_pattern_classification']}")
    print(f"Brier score: {calib['brier_score']}")
    print(f"ECE: {calib['ece']}")
    print(f"Calibration: {calib['calibration_classification']}")


if __name__ == "__main__":
    main()
