"""
scripts/run_mlb_independent_feature_candidate_export.py

P10: Independent Feature Candidate Probability Export

Loads P9 repaired features CSV, builds P10 independent features,
and produces feature_candidate probabilities in two modes:
  - feature_only:     base = 0.5, adjust using independent features only
  - feature_augmented: base = repaired model probability, adjust using features

All outputs are paper_only=True, leakage_safe=True.

Usage:
    python scripts/run_mlb_independent_feature_candidate_export.py \
      --input-csv outputs/predictions/PAPER/2026-05-11/mlb_odds_with_repaired_features.csv \
      --output-dir outputs/predictions/PAPER/2026-05-11 \
      --candidate-mode feature_augmented \
      --lookback-games 15
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

# Repo root on sys.path when run as: python scripts/...
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.prediction.mlb_independent_feature_builder import (
    build_independent_features,
    merge_independent_features_into_rows,
)
from wbc_backend.prediction.mlb_game_key import build_mlb_game_id, normalize_mlb_team

_PAPER_ZONE = "outputs/predictions/PAPER"
_DEFAULT_INPUT = (
    "outputs/predictions/PAPER/2026-05-11/mlb_odds_with_repaired_features.csv"
)

# ---------------------------------------------------------------------------
# Probability scoring helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def _clamp(p: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return max(lo, min(hi, p))


def _build_feature_score(row: dict, merged: dict) -> float:
    """
    Compute a logit-space feature adjustment from independent features.

    Features used:
    1. recent_win_rate_delta       (+0.15 per unit)
    2. rest_days_delta             (+0.03 per 7 days)
    3. bullpen_proxy_delta         (-0.05 per unit: higher usage = worse bullpen)
    4. starter_era_delta           (-0.10 per run: home starter more runs = worse)
    5. wind_kmh                    (ignored — affects both teams symmetrically)

    All deltas: positive = advantage for home team.
    """
    adj = 0.0

    # 1. Recent win rate delta (home - away) → range [-1, +1]
    wr_delta = merged.get("indep_recent_win_rate_delta")
    if wr_delta is not None:
        try:
            adj += 0.15 * float(wr_delta)
        except (ValueError, TypeError):
            pass

    # 2. Rest days delta → range roughly [-7, +7]
    rest_delta = merged.get("indep_rest_days_delta")
    if rest_delta is not None:
        try:
            adj += 0.03 * float(rest_delta) / 7.0
        except (ValueError, TypeError):
            pass

    # 3. Bullpen proxy delta (home - away usage: positive = home more fatigued)
    bullpen_delta = merged.get("indep_bullpen_proxy_delta")
    if bullpen_delta is not None:
        try:
            adj -= 0.05 * float(bullpen_delta)
        except (ValueError, TypeError):
            pass

    # 4. Starter ERA proxy delta (home - away runs-allowed: positive = home worse)
    era_delta = merged.get("indep_starter_era_delta")
    if era_delta is not None:
        try:
            adj -= 0.10 * float(era_delta)
        except (ValueError, TypeError):
            pass

    return adj


def _compute_feature_only_prob(merged: dict) -> float:
    """Feature-only candidate: start from logit(0.5) = 0, add feature score."""
    adj = _build_feature_score({}, merged)
    return _clamp(_sigmoid(adj))


def _compute_feature_augmented_prob(merged: dict) -> float:
    """Feature-augmented: start from repaired model probability, add feature score."""
    base_prob = 0.5
    # Try repaired model prob first, then raw model prob
    for col in ("model_prob_home", "raw_model_prob_home"):
        v = merged.get(col)
        if v is not None:
            try:
                base_prob = float(v)
                break
            except (ValueError, TypeError):
                continue
    adj = _build_feature_score({}, merged)
    logit_adj = _logit(base_prob) + adj
    return _clamp(_sigmoid(logit_adj))


# ---------------------------------------------------------------------------
# Paper zone gate
# ---------------------------------------------------------------------------

def _assert_paper_output_path(output_dir: str) -> None:
    abs_out = pathlib.Path(output_dir).resolve()
    abs_paper = (_REPO_ROOT / _PAPER_ZONE).resolve()
    try:
        abs_out.relative_to(abs_paper)
    except ValueError:
        print(
            f"FATAL: Output path must be under '{_PAPER_ZONE}'. Got: {abs_out}",
            file=sys.stderr,
        )
        sys.exit(2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P10/P11 independent feature candidate probability export"
    )
    parser.add_argument(
        "--input-csv", default=_DEFAULT_INPUT, help="P9 repaired features CSV"
    )
    parser.add_argument(
        "--output-dir",
        default=f"outputs/predictions/PAPER/{datetime.now(timezone.utc).date()}",
        help="Output directory (must be under outputs/predictions/PAPER/)",
    )
    parser.add_argument(
        "--lookback-games", type=int, default=15, help="Rolling win rate window"
    )
    parser.add_argument(
        "--candidate-mode",
        choices=["feature_only", "feature_augmented"],
        default="feature_augmented",
        help="Probability candidate construction mode",
    )
    parser.add_argument(
        "--use-market-probability",
        action="store_true",
        default=False,
        help="If set, use market probability as base (NOT recommended; breaks independence)",
    )
    parser.add_argument(
        "--bullpen-context",
        default="data/mlb_context/bullpen_usage_3d.jsonl",
    )
    parser.add_argument(
        "--rest-context",
        default="data/mlb_context/injury_rest.jsonl",
    )
    parser.add_argument(
        "--weather-context",
        default="data/mlb_context/weather_wind.jsonl",
    )
    parser.add_argument(
        "--asplayed",
        default="data/mlb_2025/mlb-2025-asplayed.csv",
    )
    parser.add_argument(
        "--context-file",
        dest="context_files",
        action="append",
        default=[],
        metavar="PATH",
        help="Additional context file (JSONL/CSV/JSON). Repeatable.",
    )
    parser.add_argument(
        "--auto-discover-context",
        action="store_true",
        default=False,
        help="Auto-discover likely context files under data/, outputs/, reports/",
    )
    parser.add_argument(
        "--disable-context-discovery",
        action="store_true",
        default=False,
        help="Disable all context file discovery (only use explicitly named files)",
    )
    args = parser.parse_args()

    # Safety gate
    _assert_paper_output_path(args.output_dir)

    input_path = pathlib.Path(args.input_csv)
    if not input_path.exists():
        print(f"FATAL: Input CSV not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load input rows
    # ------------------------------------------------------------------
    print(f"Loading input CSV: {input_path}")
    rows = list(csv.DictReader(input_path.open(encoding="utf-8")))
    print(f"Loaded {len(rows)} rows.")

    # ------------------------------------------------------------------
    # 1b. Collect extra context files
    # ------------------------------------------------------------------
    extra_context_paths: list[str] = list(args.context_files)

    if args.auto_discover_context and not args.disable_context_discovery:
        try:
            from wbc_backend.prediction.mlb_feature_context_loader import discover_context_files
            discovered = discover_context_files(["data", "outputs", "reports"], base_dir=_REPO_ROOT)
            # Only include files that look like context files and exist
            for item in discovered:
                if item["likely_context"] and item["path"] not in extra_context_paths:
                    extra_context_paths.append(item["path"])
            print(f"Auto-discovered {len(extra_context_paths)} context file(s).")
        except Exception as exc:
            print(f"WARNING: context auto-discovery failed: {exc}")
    elif args.context_files:
        print(f"Using {len(extra_context_paths)} explicitly provided context file(s).")

    # ------------------------------------------------------------------
    # 2. Build independent features
    # ------------------------------------------------------------------
    print(f"Building independent features (mode={args.candidate_mode}, lookback={args.lookback_games}) ...")
    feature_rows, feat_meta = build_independent_features(
        rows,
        lookback_games=args.lookback_games,
        bullpen_context_path=args.bullpen_context,
        rest_context_path=args.rest_context,
        weather_context_path=args.weather_context,
        asplayed_path=args.asplayed,
        extra_context_paths=extra_context_paths if extra_context_paths else None,
    )
    print(f"Built {len(feature_rows)} feature rows.")

    # Report context hit rate
    ctx_hit = feat_meta.get("context_hit_count", 0)
    ctx_miss = feat_meta.get("context_miss_count", 0)
    ctx_total = ctx_hit + ctx_miss
    if ctx_total > 0:
        ctx_rate = round(ctx_hit / ctx_total, 3)
        print(f"Context lookup: {ctx_hit}/{ctx_total} hits ({ctx_rate:.1%})")
    print(f"  date_col resolved: {feat_meta.get('date_col_resolved')}")
    print(f"  home_col resolved: {feat_meta.get('home_col_resolved')}")
    print(f"  away_col resolved: {feat_meta.get('away_col_resolved')}")
    print(f"  home_starter_col resolved: {feat_meta.get('home_starter_col_resolved')}")
    print(f"  away_starter_col resolved: {feat_meta.get('away_starter_col_resolved')}")
    print(f"  feature_version: {feat_meta.get('feature_version')}")

    # ------------------------------------------------------------------
    # 3. Merge features into rows
    # ------------------------------------------------------------------
    merged_rows = merge_independent_features_into_rows(rows, feature_rows)

    # ------------------------------------------------------------------
    # 4. Compute candidate probabilities
    # ------------------------------------------------------------------
    prob_before: list[float] = []
    prob_after: list[float] = []

    final_rows: list[dict] = []
    for merged in merged_rows:
        # Collect before-prob (repaired model_prob_home)
        orig_prob = None
        for col in ("model_prob_home", "raw_model_prob_home"):
            v = merged.get(col)
            if v is not None:
                try:
                    orig_prob = float(v)
                    break
                except (ValueError, TypeError):
                    continue
        if orig_prob is not None:
            prob_before.append(orig_prob)

        if args.candidate_mode == "feature_only":
            cand_prob = _compute_feature_only_prob(merged)
        else:
            cand_prob = _compute_feature_augmented_prob(merged)

        prob_after.append(cand_prob)

        row_out = dict(merged)
        # Preserve raw model prob
        if "model_prob_home" in row_out:
            row_out["raw_model_prob_before_p10"] = row_out["model_prob_home"]
        # Overwrite model_prob_home with candidate
        row_out["model_prob_home"] = round(cand_prob, 6)
        row_out["model_prob_away"] = round(1.0 - cand_prob, 6)
        row_out["probability_source"] = "feature_candidate"
        row_out["feature_candidate_mode"] = args.candidate_mode
        row_out["independent_feature_version"] = (
            feature_rows[0].feature_version if feature_rows else "p10_independent_features_v1"
        )
        row_out["paper_only"] = True
        row_out["leakage_safe"] = True
        final_rows.append(row_out)

    # ------------------------------------------------------------------
    # 5. Write outputs
    # ------------------------------------------------------------------
    # 5a. Independent features JSONL
    indep_jsonl_path = output_dir / "mlb_independent_features.jsonl"
    with indep_jsonl_path.open("w", encoding="utf-8") as fh:
        for fr in feature_rows:
            fh.write(fr.to_jsonl_line() + "\n")

    # 5b. Merged features CSV (pre-candidate-probability overlay)
    merged_csv_path = output_dir / "mlb_odds_with_independent_features.csv"
    if merged_rows:
        fieldnames = list(merged_rows[0].keys())
        with merged_csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged_rows)

    # 5c. Candidate probability JSONL
    cand_prob_jsonl_path = output_dir / "mlb_feature_candidate_probabilities.jsonl"
    run_ts = datetime.now(timezone.utc).isoformat()
    with cand_prob_jsonl_path.open("w", encoding="utf-8") as fh:
        for r in final_rows:
            line = {
                "game_id": r.get("game_id"),
                "date": r.get("date") or r.get("Date"),
                "home_team": r.get("home_team") or r.get("Home"),
                "away_team": r.get("away_team") or r.get("Away"),
                "model_prob_home": r.get("model_prob_home"),
                "model_prob_away": r.get("model_prob_away"),
                "raw_model_prob_before_p10": r.get("raw_model_prob_before_p10"),
                "probability_source": r.get("probability_source"),
                "feature_candidate_mode": r.get("feature_candidate_mode"),
                "independent_feature_version": r.get("independent_feature_version"),
                "paper_only": True,
                "leakage_safe": True,
                "run_at_utc": run_ts,
            }
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    # 5d. Full candidate CSV (for OOF calibration downstream)
    cand_csv_path = output_dir / "mlb_odds_with_feature_candidate_probabilities.csv"
    if final_rows:
        fieldnames_out = list(final_rows[0].keys())
        with cand_csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames_out)
            writer.writeheader()
            writer.writerows(final_rows)

    # 5e. Feature coverage JSON
    coverage_json_path = output_dir / "independent_feature_coverage.json"
    coverage_data = {
        **feat_meta,
        "candidate_mode": args.candidate_mode,
        "paper_only": True,
        "leakage_safe": True,
        "run_at_utc": run_ts,
        "input_csv": str(input_path),
        "output_dir": str(output_dir),
    }
    coverage_json_path.write_text(
        json.dumps(coverage_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 5f. Summary Markdown
    avg_before = sum(prob_before) / len(prob_before) if prob_before else float("nan")
    avg_after = sum(prob_after) / len(prob_after) if prob_after else float("nan")
    min_before = min(prob_before) if prob_before else float("nan")
    max_before = max(prob_before) if prob_before else float("nan")
    min_after = min(prob_after) if prob_after else float("nan")
    max_after = max(prob_after) if prob_after else float("nan")

    cov_report = ""
    for feat_name, cv in feat_meta.get("coverage_by_feature", {}).items():
        cov_report += f"- `{feat_name}`: {cv['hit']}/{cv['total']} ({cv['pct']*100:.1f}%)\n"

    summary_md = f"""# P10 Independent Feature Candidate Export Summary

Generated: {run_ts}

## Input
- Input CSV: `{input_path}`
- Rows loaded: {len(rows)}
- Lookback games: {args.lookback_games}
- Candidate mode: `{args.candidate_mode}`

## Feature Coverage
{cov_report or "No coverage data."}

## Probability Shift
| Metric | Before (P9 repaired) | After (P10 candidate) |
|--------|---------------------|----------------------|
| avg | {avg_before:.4f} | {avg_after:.4f} |
| min | {min_before:.4f} | {min_after:.4f} |
| max | {max_before:.4f} | {max_after:.4f} |

## Gate Status
- paper_only: `True`
- leakage_safe: `True`
- production_enabled: `False`
- probability_source: `feature_candidate`

## Output Artifacts
- `{indep_jsonl_path}`
- `{merged_csv_path}`
- `{cand_prob_jsonl_path}`
- `{cand_csv_path}`
- `{coverage_json_path}`
"""
    summary_md_path = output_dir / "feature_candidate_summary.md"
    summary_md_path.write_text(summary_md, encoding="utf-8")

    # ------------------------------------------------------------------
    # 6. Print summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("P10 FEATURE CANDIDATE EXPORT — SUMMARY")
    print("=" * 60)
    print(f"  candidate_mode           : {args.candidate_mode}")
    print(f"  input_count              : {len(rows)}")
    print(f"  feature_count            : {len(feature_rows)}")
    for feat_name, cv in feat_meta.get("coverage_by_feature", {}).items():
        print(f"  coverage/{feat_name:<25}: {cv['hit']}/{cv['total']} ({cv['pct']*100:.1f}%)")
    print(f"  avg_prob_before          : {avg_before:.4f}")
    print(f"  avg_prob_after           : {avg_after:.4f}")
    print(f"  prob_range_before        : [{min_before:.4f}, {max_before:.4f}]")
    print(f"  prob_range_after         : [{min_after:.4f}, {max_after:.4f}]")
    print(f"  paper_only               : True")
    print(f"  leakage_safe             : True")
    print()
    print(f"  indep JSONL   : {indep_jsonl_path}")
    print(f"  merged CSV    : {merged_csv_path}")
    print(f"  cand JSONL    : {cand_prob_jsonl_path}")
    print(f"  cand CSV      : {cand_csv_path}")
    print(f"  coverage JSON : {coverage_json_path}")
    print(f"  summary MD    : {summary_md_path}")


if __name__ == "__main__":
    main()
