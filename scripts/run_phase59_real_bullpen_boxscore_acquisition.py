#!/usr/bin/env python3
"""
scripts/run_phase59_real_bullpen_boxscore_acquisition.py
=========================================================
Phase 59 runner — Real Bullpen Boxscore Acquisition.

Usage:
    python scripts/run_phase59_real_bullpen_boxscore_acquisition.py \
        [--input PATH] [--bullpen PATH] \
        [--print] [--json] [--report]

Defaults:
    --input    data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl
    --bullpen  data/mlb_context/bullpen_usage_3d.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict
from datetime import date as DateObj
from pathlib import Path

# ── project root on sys.path ──────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from orchestrator.phase59_real_bullpen_boxscore_acquisition import (  # noqa: E402
    Phase59AcquisitionResult,
    run_phase59_acquisition,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Output paths ──────────────────────────────────────────────────────────────
REPORT_DATE: str = DateObj.today().isoformat().replace("-", "")[:8]
_REPORT_JSON_PATH: Path = (
    _ROOT / f"reports/phase59_real_bullpen_boxscore_acquisition_{REPORT_DATE}.json"
)
_REPORT_MD_PATH: Path = (
    _ROOT / f"00-BettingPlan/phase59_real_bullpen_boxscore_acquisition_report_{REPORT_DATE}.md"
)

# ── Defaults ──────────────────────────────────────────────────────────────────
_DEFAULT_INPUT: Path = _ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
_DEFAULT_BULLPEN: Path = _ROOT / "data/mlb_context/bullpen_usage_3d.jsonl"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe(v):
    """Convert NaN to None for JSON serialization."""
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _dict_safe(d: dict) -> dict:
    """Recursively convert nan to None in nested dict."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _dict_safe(v)
        elif isinstance(v, float) and math.isnan(v):
            out[k] = None
        else:
            out[k] = v
    return out


def _result_to_dict(result: Phase59AcquisitionResult) -> dict:
    """Serialize result to JSON-safe dict."""
    return _dict_safe(asdict(result))


# ─── Markdown Report ──────────────────────────────────────────────────────────

def _generate_markdown(result: Phase59AcquisitionResult) -> str:
    """Generate markdown report for Phase 59."""
    al = result.alignment
    bsr = result.bullpen_source_report
    hf = result.heavy_fav_signal
    hc = result.high_conf_signal
    hf_ece = result.heavy_fav_ece_comparison
    hc_ece = result.high_conf_ece_comparison

    def fmt(v, fmt_str=".4f"):
        if isinstance(v, float) and math.isnan(v):
            return "N/A"
        return format(v, fmt_str)

    def pct(v):
        if isinstance(v, float) and math.isnan(v):
            return "N/A"
        return f"{v:.1%}"

    lines = [
        "# Phase 59 — Real Bullpen Boxscore Acquisition Report",
        "",
        f"> Generated: {result.run_timestamp}  ",
        f"> Phase version: `{result.phase_version}`  ",
        f"> Audit hash: `{result.audit_hash}`",
        "",
        "---",
        "",
        "## § 1. Safety Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
        f"| `CANDIDATE_PATCH_CREATED` | `{result.candidate_patch_created}` |",
        f"| `PRODUCTION_MODIFIED` | `{result.production_modified}` |",
        f"| `ALPHA_MODIFIED` | `{result.alpha_modified}` |",
        f"| `DIAGNOSTIC_ONLY` | `{result.diagnostic_only}` |",
        "",
        "---",
        "",
        "## § 2. Input Artifacts",
        "",
        "| Artifact | Path |",
        "|----------|------|",
        f"| Prediction JSONL | `{al.total_prediction_rows} rows` |",
        f"| Bullpen JSONL | `{bsr.source_file}` |",
        f"| Bullpen rows | `{bsr.total_rows}` |",
        f"| Bullpen date range | `{bsr.date_range_start}` → `{bsr.date_range_end}` |",
        f"| Prediction date range | `{result.date_range_start}` → `{result.date_range_end}` |",
        "",
        "---",
        "",
        "## § 3. Data Inventory & PIT-Safety Validation",
        "",
        f"**Bullpen data source**: `{bsr.pit_source}`  ",
        f"**PIT validated**: `{bsr.pit_validated}`  ",
        "",
        f"> {bsr.pit_explanation}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Missing home bullpen % | {pct(bsr.missing_home_pct)} |",
        f"| Missing away bullpen % | {pct(bsr.missing_away_pct)} |",
        "",
        "**PIT Contract** (hard rule): `bullpen_usage_last_3d = Σ(D-1, D-2, D-3) innings pitched`.",
        "The current game's boxscore is never included in its own lookback window.",
        "",
        "---",
        "",
        "## § 4. Acquisition Method",
        "",
        f"**Alignment method**: `{al.alignment_method}`",
        "",
        "Game ID format mismatch between prediction JSONL and bullpen JSONL was resolved by",
        "normalizing both team name columns with `re.sub(r'[_\\s]+', ' ', s).strip().lower()`,",
        "then joining on `(game_date, norm_away, norm_home)` — no dependency on game_id format.",
        "",
        "---",
        "",
        "## § 5. Bullpen Feature Schema",
        "",
        "| Field | Type | Description | PIT-safe? |",
        "|-------|------|-------------|-----------|",
        "| `bullpen_usage_last_3d_home` | float | Home bullpen IP sum (D-1+D-2+D-3) | ✅ |",
        "| `bullpen_usage_last_3d_away` | float | Away bullpen IP sum (D-1+D-2+D-3) | ✅ |",
        "| `bullpen_fatigue_delta_3d` | float | home - away (positive = home tired) | ✅ |",
        "| `fav_bull_fatigue` | float | Favorite team's fatigue relative to opponent | ✅ |",
        "| `bullpen_available` | bool | Whether real bullpen data exists for this game | ✅ |",
        "",
        "**Forbidden features** (never used): `home_win`, `final_score`, `game_result`,",
        "`innings_pitched_today`, `era_after_game`, and all other post-game fields.",
        "",
        "---",
        "",
        "## § 6. Sample Size & Coverage",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total prediction rows | {al.total_prediction_rows} |",
        f"| Matched with bullpen | {al.matched_rows} ({pct(al.match_rate)}) |",
        f"| Usable rows (non-null) | {al.usable_rows} ({pct(al.usable_rate)}) |",
        f"| Unmatched rows | {al.unmatched_rows} |",
        f"| Null bullpen values | {al.null_bull_rows} |",
        "",
        "---",
        "",
        "## § 7. Heavy-Fav & High-Conf Segment Coverage",
        "",
        f"| Segment | Total | With Bullpen | Coverage |",
        f"|---------|-------|--------------|----------|",
        f"| Heavy-fav (fav≥0.70) | {al.heavy_fav_total} | {al.heavy_fav_usable} | {pct(al.heavy_fav_coverage)} |",
        f"| High-conf (fav≥0.65) | — | {al.high_conf_usable} | {pct(al.high_conf_coverage)} |",
        "",
        f"**Prior heavy_fav ECE baseline** (Phase 59-Pre): `{fmt(result.prior_heavy_fav_ece_baseline)}`",
        "",
        "---",
        "",
        "## § 8. Baseline vs Bullpen Diagnostic",
        "",
        "### Heavy-Fav Signal Analysis",
        "",
        f"n={hf.n}, mean_bull_delta={fmt(hf.mean_bull_delta, '.2f')}, "
        f"stdev_bull_delta={fmt(hf.stdev_bull_delta, '.2f')}",
        "",
        "| Segment | n | Fav-win rate |",
        "|---------|---|-------------|",
        f"| Tired fav (Δ ≥ +2 IP) | {hf.tired_fav_n} | {fmt(hf.tired_fav_win_rate, '.3f')} |",
        f"| Rested fav (Δ ≤ -2 IP) | {hf.rested_fav_n} | {fmt(hf.rested_fav_win_rate, '.3f')} |",
        f"| Delta (rested - tired) | — | {fmt(hf.fatigue_win_rate_delta, '+.3f')} |",
        f"| Has signal? | — | `{hf.has_signal}` |",
        "",
        "### ECE Comparison (Heavy-Fav)",
        "",
        "| Metric | Baseline | Bullpen-adjusted | Δ |",
        "|--------|----------|-----------------|---|",
        f"| ECE | {fmt(hf_ece.baseline_ece)} | {fmt(hf_ece.bullpen_adjusted_ece)} | {fmt(hf_ece.ece_delta, '+.4f')} |",
        f"| BSS | {fmt(hf_ece.baseline_bss)} | {fmt(hf_ece.bullpen_adjusted_bss)} | — |",
        "",
        "### ECE Comparison (High-Conf)",
        "",
        "| Metric | Baseline | Bullpen-adjusted | Δ |",
        "|--------|----------|-----------------|---|",
        f"| ECE | {fmt(hc_ece.baseline_ece)} | {fmt(hc_ece.bullpen_adjusted_ece)} | {fmt(hc_ece.ece_delta, '+.4f')} |",
        f"| BSS | {fmt(hc_ece.baseline_bss)} | {fmt(hc_ece.bullpen_adjusted_bss)} | — |",
        "",
        "---",
        "",
        "## § 9. Historical Phase Context",
        "",
        "| Phase | Gate | Bullpen Coverage |",
        "|-------|------|-----------------|",
        f"| Phase 55 | `{result.phase55_gate}` | N/A (investigation) |",
        f"| Phase 56 | `{result.phase56_gate}` | {pct(result.phase56_bullpen_available_rate)} (neutral_fallback) |",
        f"| Phase 59-Pre | `BULLPEN_HYPOTHESIS_RETAINED` | N/A (heavy_fav ECE baseline) |",
        f"| **Phase 59** | **`{result.gate}`** | {pct(al.heavy_fav_coverage)} (real data) |",
        "",
        "---",
        "",
        "## § 10. Gate Conclusion",
        "",
        f"### Gate: `{result.gate}`",
        "",
        f"{result.gate_rationale}",
        "",
        "---",
        "",
        "## § 11. Next Steps",
        "",
        result.next_step,
        "",
        "---",
        "",
        "<!-- PHASE_59_REAL_BULLPEN_BOXSCORE_ACQUISITION_VERIFIED -->",
        "",
    ]
    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 59 — Real Bullpen Boxscore Acquisition Runner"
    )
    p.add_argument(
        "--input",
        type=Path,
        default=_DEFAULT_INPUT,
        help="Path to per-game predictions JSONL",
    )
    p.add_argument(
        "--bullpen",
        type=Path,
        default=_DEFAULT_BULLPEN,
        help="Path to bullpen_usage_3d JSONL",
    )
    p.add_argument("--print", action="store_true", dest="do_print",
                   help="Print summary to stdout")
    p.add_argument("--json", action="store_true", dest="do_json",
                   help=f"Write JSON report to {_REPORT_JSON_PATH}")
    p.add_argument("--report", action="store_true", dest="do_report",
                   help=f"Write Markdown report to {_REPORT_MD_PATH}")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Validate inputs
    if not args.input.exists():
        logger.error("Predictions file not found: %s", args.input)
        sys.exit(1)
    if not args.bullpen.exists():
        logger.error("Bullpen file not found: %s", args.bullpen)
        sys.exit(1)

    logger.info("Running Phase 59 acquisition...")
    result = run_phase59_acquisition(
        predictions_path=args.input,
        bullpen_path=args.bullpen,
    )

    # Print summary
    if args.do_print:
        al = result.alignment
        hf = result.heavy_fav_signal
        hf_ece = result.heavy_fav_ece_comparison

        def safe_fmt(v, fmt="f"):
            if isinstance(v, float) and math.isnan(v):
                return "N/A"
            return format(v, fmt)

        print()
        print("=" * 70)
        print("  PHASE 59 — REAL BULLPEN BOXSCORE ACQUISITION")
        print("=" * 70)
        print(f"  Phase version  : {result.phase_version}")
        print(f"  Audit hash     : {result.audit_hash}")
        print(f"  DIAGNOSTIC_ONLY: {result.diagnostic_only}")
        print()
        print("  [SAFETY]")
        print(f"    CANDIDATE_PATCH_CREATED = {result.candidate_patch_created}")
        print(f"    PRODUCTION_MODIFIED     = {result.production_modified}")
        print(f"    ALPHA_MODIFIED          = {result.alpha_modified}")
        print()
        print("  [DATA]")
        print(f"    Total prediction rows   : {al.total_prediction_rows}")
        print(f"    Matched w/ bullpen      : {al.matched_rows} ({al.match_rate:.1%})")
        print(f"    Usable (non-null)       : {al.usable_rows} ({al.usable_rate:.1%})")
        print(f"    Heavy_fav usable        : {al.heavy_fav_usable}/{al.heavy_fav_total} "
              f"({al.heavy_fav_coverage:.1%})")
        print()
        print("  [SIGNAL]")
        print(f"    Heavy_fav n             : {hf.n}")
        print(f"    Tired_fav (≥+2 IP) n    : {hf.tired_fav_n}")
        print(f"    Rested_fav (≤-2 IP) n   : {hf.rested_fav_n}")
        print(f"    Tired fav win rate      : {safe_fmt(hf.tired_fav_win_rate, '.3f')}")
        print(f"    Rested fav win rate     : {safe_fmt(hf.rested_fav_win_rate, '.3f')}")
        print(f"    Fatigue Δ win rate      : {safe_fmt(hf.fatigue_win_rate_delta, '+.3f')}")
        print(f"    has_signal              : {hf.has_signal}")
        print()
        print("  [ECE]")
        print(f"    Heavy_fav baseline ECE  : {safe_fmt(hf_ece.baseline_ece, '.4f')}")
        print(f"    Heavy_fav adjusted ECE  : {safe_fmt(hf_ece.bullpen_adjusted_ece, '.4f')}")
        print(f"    ECE delta (pos=better)  : {safe_fmt(hf_ece.ece_delta, '+.4f')}")
        print()
        print("  " + "─" * 66)
        print(f"  GATE: {result.gate}")
        print("  " + "─" * 66)
        print(f"  {result.gate_rationale[:200]}")
        print("=" * 70)
        print()

    # Write JSON report
    if args.do_json:
        _REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "phase59_acquisition_v1",
            "gate": result.gate,
            **_result_to_dict(result),
        }
        _REPORT_JSON_PATH.write_text(json.dumps(payload, indent=2))
        logger.info("JSON report: %s", _REPORT_JSON_PATH)

    # Write Markdown report
    if args.do_report:
        _REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        md = _generate_markdown(result)
        _REPORT_MD_PATH.write_text(md, encoding="utf-8")
        logger.info("Markdown report: %s", _REPORT_MD_PATH)

    print(f"\nGate: {result.gate}")
    sys.exit(0)


if __name__ == "__main__":
    main()
