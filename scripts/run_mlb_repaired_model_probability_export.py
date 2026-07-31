#!/usr/bin/env python3
"""
scripts/run_mlb_repaired_model_probability_export.py

P9: CLI to apply conservative feature repair to a P5 probability-enriched CSV
and produce a repaired-candidate artifact for downstream OOF calibration and
simulation.

Behavior:
  1. Load input CSV (default: P5 artifact).
  2. Run build_repaired_feature_rows():
       - Remove constant home_bias=1.0 artefact.
       - Add bullpen-usage delta, rest-day delta, rolling win-rate delta.
  3. Write outputs to outputs/predictions/PAPER/<date>/:
       - mlb_odds_with_repaired_features.csv
       - mlb_repaired_model_probabilities.jsonl
       - repaired_feature_metadata.json
       - repaired_probability_summary.md
  4. Print summary statistics on stdout.

Security:
  - All output restricted to outputs/predictions/PAPER/.
  - paper_only = True always.
  - leakage_safe = True always.
  - Never enables production mode.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

_PAPER_PREDICTIONS_ZONE = "outputs/predictions/PAPER"

_DEFAULT_INPUT_CSV = str(
    _REPO_ROOT
    / "outputs"
    / "predictions"
    / "PAPER"
    / "2026-05-11"
    / "mlb_odds_with_model_probabilities.csv"
)


def _assert_paper_output_path(path: Path) -> None:
    resolved = path.resolve()
    if _PAPER_PREDICTIONS_ZONE not in resolved.as_posix():
        print(
            f"FATAL: Output path must be under {_PAPER_PREDICTIONS_ZONE!r}. "
            f"Got: {resolved}",
            file=sys.stderr,
        )
        sys.exit(2)


def main() -> int:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    default_out_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / today

    parser = argparse.ArgumentParser(
        description="Apply P9 feature repair to MLB model probabilities."
    )
    parser.add_argument(
        "--input-csv",
        default=_DEFAULT_INPUT_CSV,
        help="Path to P5 probability-enriched odds CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_out_dir),
        help=f"Output directory. Must be under {_PAPER_PREDICTIONS_ZONE}.",
    )
    parser.add_argument(
        "--feature-version",
        default="p9_feature_repair_v1",
        help="Feature version label (informational).",
    )
    parser.add_argument(
        "--remove-constant-home-bias",
        action="store_true",
        default=True,
        help="Remove the constant home_bias=1.0 artefact from model logit.",
    )
    parser.add_argument(
        "--no-remove-constant-home-bias",
        dest="remove_constant_home_bias",
        action="store_false",
        help="Skip home-bias removal.",
    )
    parser.add_argument(
        "--bullpen-context",
        default=str(_REPO_ROOT / "data" / "mlb_context" / "bullpen_usage_3d.jsonl"),
        help="Path to bullpen_usage_3d.jsonl context file.",
    )
    parser.add_argument(
        "--rest-context",
        default=str(_REPO_ROOT / "data" / "mlb_context" / "injury_rest.jsonl"),
        help="Path to injury_rest.jsonl context file.",
    )
    args = parser.parse_args()

    # ── Validate paths ──────────────────────────────────────────────────────
    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"FATAL: Input CSV not found: {input_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir)
    _assert_paper_output_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load input CSV ──────────────────────────────────────────────────────
    print(f"Loading input CSV: {input_path}")
    rows: list[dict] = []
    with input_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} rows from CSV.")

    if not rows:
        print("FATAL: No rows found in input CSV.", file=sys.stderr)
        return 1

    # ── Apply feature repair ────────────────────────────────────────────────
    from wbc_backend.prediction.mlb_feature_repair import build_repaired_feature_rows

    print(
        f"Applying feature repair (remove_home_bias={args.remove_constant_home_bias}) ..."
    )
    repaired_rows, metadata = build_repaired_feature_rows(
        rows,
        remove_constant_home_bias=args.remove_constant_home_bias,
        bullpen_context_path=args.bullpen_context,
        rest_context_path=args.rest_context,
    )
    print(f"Repair complete: {metadata['output_count']} rows out.")

    # ── Write CSV ───────────────────────────────────────────────────────────
    csv_out = out_dir / "mlb_odds_with_repaired_features.csv"
    _assert_paper_output_path(csv_out)
    _write_csv(repaired_rows, csv_out)
    print(f"CSV written: {csv_out}")

    # ── Write JSONL ─────────────────────────────────────────────────────────
    jsonl_out = out_dir / "mlb_repaired_model_probabilities.jsonl"
    _assert_paper_output_path(jsonl_out)
    with jsonl_out.open("w", encoding="utf-8") as jf:
        for row in repaired_rows:
            jf.write(json.dumps(row) + "\n")
    print(f"JSONL written: {jsonl_out}")

    # ── Write metadata JSON ─────────────────────────────────────────────────
    meta_out = out_dir / "repaired_feature_metadata.json"
    _assert_paper_output_path(meta_out)
    meta_full: dict[str, Any] = {
        **metadata,
        "input_csv": str(input_path),
        "output_dir": str(out_dir),
        "feature_version_arg": args.feature_version,
        "remove_constant_home_bias": args.remove_constant_home_bias,
        "run_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "paper_only": True,
        "leakage_safe": True,
    }
    with meta_out.open("w", encoding="utf-8") as mf:
        json.dump(meta_full, mf, indent=2)
    print(f"Metadata JSON written: {meta_out}")

    # ── Write summary markdown ──────────────────────────────────────────────
    summary_out = out_dir / "repaired_probability_summary.md"
    _assert_paper_output_path(summary_out)
    summary_md = _build_summary_md(metadata, repaired_rows, meta_full)
    with summary_out.open("w", encoding="utf-8") as sf:
        sf.write(summary_md)
    print(f"Summary MD written: {summary_out}")

    # ── Print summary statistics ────────────────────────────────────────────
    print()
    print("=" * 60)
    print("P9 REPAIRED MODEL FEATURE EXPORT — SUMMARY")
    print("=" * 60)
    print(f"  input_count              : {metadata['input_count']}")
    print(f"  output_count             : {metadata['output_count']}")
    print(f"  duplicate_count          : {metadata['duplicate_count']}")
    print(f"  bullpen_join_hit         : {metadata['bullpen_join_hit_count']}")
    print(f"  bullpen_join_miss        : {metadata['bullpen_join_miss_count']}")
    print(f"  rest_join_hit            : {metadata['rest_join_hit_count']}")
    print(f"  rest_join_miss           : {metadata['rest_join_miss_count']}")
    print(f"  home_bias_logit_correct  : {metadata['home_bias_logit_correction']:.4f}")
    print(f"  avg_model_prob_before    : {metadata['avg_model_prob_before']:.4f}")
    print(f"  avg_model_prob_after     : {metadata['avg_model_prob_after']:.4f}")
    print(f"  repaired_feature_version : {metadata['repaired_feature_version']}")
    print(f"  paper_only               : {metadata['paper_only']}")
    print(f"  leakage_safe             : {metadata['leakage_safe']}")
    print()
    print(f"  CSV path   : {csv_out}")
    print(f"  JSONL path : {jsonl_out}")
    print(f"  Meta path  : {meta_out}")
    print(f"  MD path    : {summary_out}")
    print()

    return 0


def _write_csv(rows: list[dict], path: Path) -> None:
    """Write a list of dicts to CSV with all keys as headers."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Collect all field names preserving first-occurrence order
    seen_fields: list[str] = []
    field_set: set[str] = set()
    for row in rows:
        for k in row:
            if k not in field_set:
                seen_fields.append(k)
                field_set.add(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=seen_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _build_summary_md(
    metadata: dict,
    repaired_rows: list[dict],
    meta_full: dict,
) -> str:
    bias_corr = metadata.get("home_bias_logit_correction", 0.0)
    prob_before = metadata.get("avg_model_prob_before", 0.0)
    prob_after = metadata.get("avg_model_prob_after", 0.0)
    bp_hit = metadata.get("bullpen_join_hit_count", 0)
    rest_hit = metadata.get("rest_join_hit_count", 0)
    n_out = metadata.get("output_count", len(repaired_rows))
    feature_ver = metadata.get("repaired_feature_version", "unknown")

    # Collect prob ranges
    probs_before = [float(r["raw_model_prob_home"]) for r in repaired_rows if r.get("raw_model_prob_home") is not None]
    probs_after = [float(r["model_prob_home"]) for r in repaired_rows if r.get("model_prob_home") is not None]
    range_before = (
        f"[{min(probs_before):.4f}, {max(probs_before):.4f}]" if probs_before else "N/A"
    )
    range_after = (
        f"[{min(probs_after):.4f}, {max(probs_after):.4f}]" if probs_after else "N/A"
    )

    return f"""# P9 Repaired Model Probability Summary

**Feature Version**: `{feature_ver}`
**Run At (UTC)**: {meta_full.get("run_at_utc", "")}
**paper_only**: True | **leakage_safe**: True

## Input / Output Counts

| Metric | Value |
|--------|-------|
| Input rows | {metadata.get("input_count", 0)} |
| Output rows | {n_out} |
| Duplicates dropped | {metadata.get("duplicate_count", 0)} |
| Bullpen context joins | {bp_hit} / {n_out} |
| Rest context joins | {rest_hit} / {n_out} |

## Probability Shift (RC-1 + Independent Features)

| Metric | Before | After |
|--------|--------|-------|
| Average model_prob_home | {prob_before:.4f} | {prob_after:.4f} |
| Range model_prob_home | {range_before} | {range_after} |
| Home bias logit correction | — | {bias_corr:.4f} |

## Repair Components

1. **RC-1 fix**: Removed constant `home_bias=1.0` intercept artefact via logit correction = `{bias_corr:.4f}`.
2. **Bullpen-usage delta** (home − away last 3d): joined from `data/mlb_context/bullpen_usage_3d.jsonl`.
3. **Rest-day delta** (home − away): joined from `data/mlb_context/injury_rest.jsonl`.
4. **Rolling win-rate delta** (home − away, last {15} games): derived from historical score records in input CSV.

## Output Artifacts

| Artifact | Path |
|----------|------|
| Repaired CSV | `{meta_full.get("output_dir", "")}/mlb_odds_with_repaired_features.csv` |
| Repaired JSONL | `{meta_full.get("output_dir", "")}/mlb_repaired_model_probabilities.jsonl` |
| Metadata JSON | `{meta_full.get("output_dir", "")}/repaired_feature_metadata.json` |
| This summary | `{meta_full.get("output_dir", "")}/repaired_probability_summary.md` |

---
*Generated by P9 feature repair pipeline. Paper-only; no production bets.*
"""


if __name__ == "__main__":
    sys.exit(main())
