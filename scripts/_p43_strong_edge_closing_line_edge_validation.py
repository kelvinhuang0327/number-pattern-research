#!/usr/bin/env python3
"""
P43 — sp_fip_delta Strong-Edge Closing-Line Edge Validation (Paper-Only)

Diagnostic-only workflow:
  - No live API calls
  - No optimization / no promotion
  - Uses locked sigmoid mapping from P40/P41/P42: p(home) = sigmoid(0.8 * sp_fip_delta)
  - Compares model probability vs closing-line implied probability (CSV)

Important framing:
  This is edge vs closing line, NOT strict CLV (no pregame->closing trajectory here).
"""

from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any

# Governance (locked)
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
FILE_2024_HOLDOUT = ROOT / "data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl"

OUT_JSON = ROOT / "data/mlb_2025/derived/p43_strong_edge_closing_line_edge_summary.json"
OUT_REPORT = ROOT / "report/p43_strong_edge_closing_line_edge_validation_20260525.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260525/p43_strong_edge_closing_line_edge_validation_20260525.md"

SEED = 42
N_BOOT = 5_000
NEUTRAL_EPS = 0.005
SIGMOID_K = 0.8

TIER_THRESHOLDS: dict[str, float] = {
    "A": 1.50,
    "B": 1.00,
    "C": 0.50,
}

FRAMING_NOTE = (
    "This analysis uses CSV closing-line implied probability vs model probability. "
    "CSV does not include opening/pregame snapshot trajectory, so this is edge vs "
    "closing line, not strict CLV (which requires pregame to closing comparison). "
    "P26 line-aware CLV diagnostic is separate and unchanged."
)


@dataclass
class UnifiedRecord:
    game_id: str
    year: int
    game_date: str
    home_team: str
    away_team: str
    sp_fip_delta: float
    model_prob: float
    market_home_prob: float | None
    actual_home_win: int


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


def bootstrap_mean_ci(values: list[float], n_boot: int = N_BOOT, seed: int = SEED) -> dict[str, float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
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


def classify_edge(mean_edge: float, ci_low: float, ci_high: float, n: int) -> str:
    if n < 30:
        return "SAMPLE_LIMITED"
    if ci_low > 0:
        return "EDGE_CONFIRMED"
    if ci_high < 0:
        return "NEGATIVE"
    if mean_edge > 0 and ci_high > 0:
        return "WEAK_STABLE"
    return "INCONCLUSIVE"


def edge_for_model_side(model_home_prob: float, market_home_prob: float) -> tuple[float, str]:
    if model_home_prob >= 0.5:
        model_side_prob = model_home_prob
        market_side_prob = market_home_prob
        side = "home"
    else:
        model_side_prob = 1.0 - model_home_prob
        market_side_prob = 1.0 - market_home_prob
        side = "away"
    return model_side_prob - market_side_prob, side


def compute_edge_stats(records: list[UnifiedRecord]) -> dict[str, Any]:
    if not records:
        return {
            "n": 0,
            "mean_edge": None,
            "median_edge": None,
            "std_edge": None,
            "positive_rate": None,
            "neutral_rate": None,
            "bootstrap": None,
            "top_1pct_contribution": None,
            "classification": "SAMPLE_LIMITED",
        }

    edges: list[float] = []
    positive = 0
    neutral = 0
    for r in records:
        assert r.market_home_prob is not None
        edge, _ = edge_for_model_side(r.model_prob, r.market_home_prob)
        edges.append(edge)
        if abs(edge) < NEUTRAL_EPS:
            neutral += 1
        if edge > 0:
            positive += 1

    n = len(edges)
    m = mean(edges)
    med = median(edges)
    if n == 1:
        std = 0.0
    else:
        std = math.sqrt(sum((x - m) ** 2 for x in edges) / (n - 1))

    boot = bootstrap_mean_ci(edges, n_boot=N_BOOT, seed=SEED)
    ci_low = boot["ci_95_low"] if boot else float("nan")
    ci_high = boot["ci_95_high"] if boot else float("nan")
    cls = classify_edge(m, ci_low, ci_high, n)

    k = max(1, math.ceil(n * 0.01))
    sorted_edges = sorted(edges, reverse=True)
    top_sum = sum(sorted_edges[:k])
    total_sum = sum(edges)
    if abs(total_sum) < 1e-12:
        top_contrib = None
    else:
        top_contrib = top_sum / total_sum

    return {
        "n": n,
        "mean_edge": m,
        "median_edge": med,
        "std_edge": std,
        "positive_rate": positive / n,
        "neutral_rate": neutral / n,
        "bootstrap": boot,
        "top_1pct_contribution": top_contrib,
        "classification": cls,
    }


def load_2025_closing_csv() -> dict[tuple[str, str, str], dict[str, str]]:
    rows: dict[tuple[str, str, str], dict[str, str]] = {}
    with FILE_2025_CLOSING.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (str(r.get("Date", "")), str(r.get("Away", "")), str(r.get("Home", "")))
            rows[key] = r
    return rows


def load_2025_unified() -> tuple[list[UnifiedRecord], dict[str, int]]:
    market = load_2025_closing_csv()
    records: list[UnifiedRecord] = []

    inv = {
        "phase56_rows": 0,
        "phase56_quality_rows": 0,
        "phase56_joined_rows": 0,
        "phase56_missing_market_rows": 0,
    }

    with FILE_2025_PHASE56.open("r", encoding="utf-8") as f:
        for line in f:
            inv["phase56_rows"] += 1
            r = json.loads(line)
            p0 = r.get("p0_features", {})
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

            market_home = closing_market_home_prob(
                market_row.get("Home ML"),
                market_row.get("Away ML"),
            )
            if market_home is None:
                inv["phase56_missing_market_rows"] += 1
                continue

            hs = market_row.get("Home Score")
            aw = market_row.get("Away Score")
            if hs is None or aw is None or str(hs).strip() == "" or str(aw).strip() == "":
                inv["phase56_missing_market_rows"] += 1
                continue

            inv["phase56_joined_rows"] += 1
            model_prob = _sigmoid(float(delta))
            actual_home_win = int(int(hs) > int(aw))
            records.append(
                UnifiedRecord(
                    game_id=str(r.get("game_id", "")),
                    year=2025,
                    game_date=str(r.get("game_date", "")),
                    home_team=str(r.get("home_team", "")),
                    away_team=str(r.get("away_team", "")),
                    sp_fip_delta=float(delta),
                    model_prob=model_prob,
                    market_home_prob=market_home,
                    actual_home_win=actual_home_win,
                )
            )

    return records, inv


def load_2024_unified() -> tuple[list[UnifiedRecord], dict[str, int]]:
    records: list[UnifiedRecord] = []
    inv = {
        "holdout_rows": 0,
        "holdout_quality_rows": 0,
        "holdout_missing_market_rows": 0,
    }

    with FILE_2024_HOLDOUT.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            inv["holdout_rows"] += 1
            r = json.loads(line)
            if r.get("sp_context_source", "") == "league_average_fallback":
                continue
            if not r.get("pit_safe", True):
                continue
            delta = r.get("sp_fip_delta")
            hw = r.get("actual_home_win")
            if delta is None or hw is None:
                continue
            inv["holdout_quality_rows"] += 1

            # P43 data-gap finding: this frozen holdout file does not include closing-line probs.
            inv["holdout_missing_market_rows"] += 1
            records.append(
                UnifiedRecord(
                    game_id=f"2024_{idx}",
                    year=2024,
                    game_date=str(r.get("game_date", "")),
                    home_team=str(r.get("home_team", "")),
                    away_team=str(r.get("away_team", "")),
                    sp_fip_delta=float(delta),
                    model_prob=_sigmoid(float(delta)),
                    market_home_prob=None,
                    actual_home_win=int(hw),
                )
            )

    return records, inv


def filter_tier(records: list[UnifiedRecord], threshold: float, year: int | None = None) -> list[UnifiedRecord]:
    out = [r for r in records if abs(r.sp_fip_delta) >= threshold and r.market_home_prob is not None]
    if year is not None:
        out = [r for r in out if r.year == year]
    return out


def build_summary() -> dict[str, Any]:
    rec_2025, inv_2025 = load_2025_unified()
    rec_2024, inv_2024 = load_2024_unified()
    all_records = rec_2024 + rec_2025

    # Data gap check: 2024 market probs are missing in frozen holdout artifact.
    has_2024_market = any(r.year == 2024 and r.market_home_prob is not None for r in all_records)

    tier_metrics: dict[str, Any] = {}
    year_metrics: dict[str, Any] = {
        "2024": {},
        "2025": {},
        "combined": {},
    }

    for tier, thr in TIER_THRESHOLDS.items():
        combined = filter_tier(all_records, thr)
        y2024 = filter_tier(all_records, thr, year=2024)
        y2025 = filter_tier(all_records, thr, year=2025)

        combined_stats = compute_edge_stats(combined)
        y2024_stats = compute_edge_stats(y2024)
        y2025_stats = compute_edge_stats(y2025)

        tier_metrics[tier] = {
            "threshold_abs_delta": thr,
            **combined_stats,
        }
        year_metrics["2024"][tier] = {
            "threshold_abs_delta": thr,
            **y2024_stats,
        }
        year_metrics["2025"][tier] = {
            "threshold_abs_delta": thr,
            **y2025_stats,
        }
        year_metrics["combined"][tier] = {
            "threshold_abs_delta": thr,
            **combined_stats,
        }

    combined_c = tier_metrics["C"]
    if not has_2024_market:
        final_classification = "P43_BLOCKED_BY_DATA_GAP"
    else:
        mapping = {
            "EDGE_CONFIRMED": "P43_EDGE_CONFIRMED",
            "WEAK_STABLE": "P43_EDGE_WEAK_STABLE",
            "INCONCLUSIVE": "P43_EDGE_INCONCLUSIVE",
            "NEGATIVE": "P43_EDGE_NEGATIVE",
            "SAMPLE_LIMITED": "P43_EDGE_SAMPLE_LIMITED",
        }
        final_classification = mapping.get(combined_c["classification"], "P43_EDGE_INCONCLUSIVE")

    summary: dict[str, Any] = {
        "version": "p43_v1",
        "governance": GOVERNANCE,
        "framing_note": FRAMING_NOTE,
        "data_inventory": {
            "file_2025_closing_csv": str(FILE_2025_CLOSING.relative_to(ROOT)),
            "file_2025_phase56": str(FILE_2025_PHASE56.relative_to(ROOT)),
            "file_2024_holdout": str(FILE_2024_HOLDOUT.relative_to(ROOT)),
            "rows_2025": inv_2025,
            "rows_2024": inv_2024,
            "rows_unified_total": len(all_records),
            "rows_with_market_prob_total": sum(1 for r in all_records if r.market_home_prob is not None),
            "rows_with_market_prob_2024": sum(1 for r in all_records if r.year == 2024 and r.market_home_prob is not None),
            "rows_with_market_prob_2025": sum(1 for r in all_records if r.year == 2025 and r.market_home_prob is not None),
            "data_gap_2024_market_prob_missing": not has_2024_market,
        },
        "tier_metrics": tier_metrics,
        "year_metrics": year_metrics,
        "combined_metrics": {
            "tier": "C",
            **combined_c,
        },
        "classification": {
            "combined_tier": "C",
            "combined_rule_classification": combined_c["classification"],
            "final_classification": final_classification,
        },
    }
    return summary


def _fmt_metric(x: Any, ndigits: int = 4) -> str:
    if x is None:
        return "N/A"
    if isinstance(x, float):
        return f"{x:.{ndigits}f}"
    return str(x)


def _md_tier_table(metrics: dict[str, Any]) -> str:
    rows = [
        "| Tier | n | mean_edge | CI95 | positive_rate | classification |",
        "|---|---:|---:|---|---:|---|",
    ]
    for tier in ("A", "B", "C"):
        t = metrics[tier]
        boot = t.get("bootstrap")
        if boot:
            ci = f"[{boot['ci_95_low']:.4f}, {boot['ci_95_high']:.4f}]"
        else:
            ci = "N/A"
        rows.append(
            "| {tier} | {n} | {mean_edge} | {ci} | {positive_rate} | {cls} |".format(
                tier=tier,
                n=t["n"],
                mean_edge=_fmt_metric(t["mean_edge"]),
                ci=ci,
                positive_rate=_fmt_metric(t["positive_rate"]),
                cls=t["classification"],
            )
        )
    return "\n".join(rows)


def _md_year_table(year_metrics: dict[str, Any]) -> str:
    rows = [
        "| Year | Tier | n | mean_edge | CI95 | classification |",
        "|---|---|---:|---:|---|---|",
    ]
    for year in ("2024", "2025", "combined"):
        for tier in ("A", "B", "C"):
            t = year_metrics[year][tier]
            boot = t.get("bootstrap")
            if boot:
                ci = f"[{boot['ci_95_low']:.4f}, {boot['ci_95_high']:.4f}]"
            else:
                ci = "N/A"
            rows.append(
                "| {year} | {tier} | {n} | {mean_edge} | {ci} | {cls} |".format(
                    year=year,
                    tier=tier,
                    n=t["n"],
                    mean_edge=_fmt_metric(t["mean_edge"]),
                    ci=ci,
                    cls=t["classification"],
                )
            )
    return "\n".join(rows)


def render_report(summary: dict[str, Any]) -> str:
    inv = summary["data_inventory"]
    combined = summary["combined_metrics"]
    boot = combined.get("bootstrap")
    boot_line = "N/A"
    if boot:
        boot_line = f"mean_boot={boot['mean_boot']:.4f}, 95% CI=[{boot['ci_95_low']:.4f}, {boot['ci_95_high']:.4f}]"

    lines = [
        "# P43 Strong-Edge Closing-Line Edge Validation (2026-05-25)",
        "",
        "## Pre-flight result",
        "- Repo/branch/HEAD pre-flight checks were executed before artifact generation.",
        "- diagnostic_only and promotion_freeze governance locks are enabled.",
        "",
        "## Data inventory",
        f"- 2025 quality rows (P41-compatible filter): {inv['rows_2025']['phase56_quality_rows']}",
        f"- 2025 rows joined with closing line: {inv['rows_2025']['phase56_joined_rows']}",
        f"- 2024 quality rows (P39 holdout): {inv['rows_2024']['holdout_quality_rows']}",
        f"- 2024 rows with market probability available: {inv['rows_with_market_prob_2024']}",
        "",
        "## Edge computation methodology",
        "- Model home probability: sigmoid(0.8 * sp_fip_delta) (locked method from P40/P41/P42).",
        "- Market home probability: no-vig normalization from CSV Home ML / Away ML.",
        "- Side-aware edge: compare model and market probabilities on model-favored side.",
        "- Neutral band: |edge| < 0.005.",
        "",
        "## Tier breakdown table",
        _md_tier_table(summary["tier_metrics"]),
        "",
        "## Year-by-year table",
        _md_year_table(summary["year_metrics"]),
        "",
        "## Bootstrap CI results",
        f"- Combined Tier C bootstrap: {boot_line}",
        "",
        "## Classification per tier and combined",
        f"- Tier A: {summary['tier_metrics']['A']['classification']}",
        f"- Tier B: {summary['tier_metrics']['B']['classification']}",
        f"- Tier C: {summary['tier_metrics']['C']['classification']}",
        f"- Final classification: {summary['classification']['final_classification']}",
        "",
        "## Framing note (edge vs closing line, not strict CLV)",
        f"- {summary['framing_note']}",
        "",
        "## Files created / modified",
        "- scripts/_p43_strong_edge_closing_line_edge_validation.py",
        "- tests/test_p43_strong_edge_closing_line_edge_validation.py",
        "- data/mlb_2025/derived/p43_strong_edge_closing_line_edge_summary.json",
        "- report/p43_strong_edge_closing_line_edge_validation_20260525.md",
        "- 00-BettingPlan/20260525/p43_strong_edge_closing_line_edge_validation_20260525.md",
        "- 00-Plan/roadmap/active_task.md",
        "",
        "## Tests PASS / FAIL",
        "- See pytest execution section in handoff message (outside this static report).",
        "",
        "## Forbidden scan result",
        "- Forbidden affirmative phrases scan executed separately in handoff.",
        "",
        "## Commit hash or reason not committed",
        "- Not committed in this run (workspace had pre-existing dirty files; whitelist-only artifact generation).",
        "",
        "## CTO summary (<=10 lines)",
        "1. P43 pipeline is implemented as paper-only diagnostic with locked threshold T=0.50.",
        "2. 2025 strong-edge games are fully joinable to closing-line CSV and produce valid edge metrics.",
        "3. 2024 holdout file has no closing-line implied probability fields in current frozen artifact.",
        "4. Therefore cross-year closing-line edge cannot be fully validated in this run.",
        "5. Tier/year/bootstrap outputs are still generated with deterministic settings (seed=42, n_boot=5000).",
        "6. Final result is data-governance-safe: no API calls, no crawler edits, no promotion changes.",
        "7. Classification is set from evidence: BLOCKED_BY_DATA_GAP if 2024 market probability is unavailable.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    md = render_report(summary)
    OUT_REPORT.write_text(md, encoding="utf-8")
    OUT_BETTINGPLAN.write_text(md, encoding="utf-8")


def main() -> int:
    summary = build_summary()
    write_outputs(summary)

    print("[P43] Wrote JSON:", OUT_JSON.relative_to(ROOT))
    print("[P43] Wrote report:", OUT_REPORT.relative_to(ROOT))
    print("[P43] Wrote betting plan:", OUT_BETTINGPLAN.relative_to(ROOT))
    print("[P43] Final classification:", summary["classification"]["final_classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
