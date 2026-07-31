#!/usr/bin/env python3
"""
P13 CLI: build walk-forward ML candidate probabilities under PAPER outputs.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.prediction.mlb_ml_feature_matrix import build_ml_feature_matrix
from wbc_backend.prediction.mlb_walk_forward_model import run_walk_forward_ml_candidate


def _assert_paper_dir(path: Path) -> None:
    if "outputs/predictions/PAPER" not in path.resolve().as_posix():
        print(f"[REFUSED] output dir must be under outputs/predictions/PAPER: {path}", file=sys.stderr)
        sys.exit(2)


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="P13 walk-forward ML candidate export")
    parser.add_argument(
        "--input-csv",
        default="outputs/predictions/PAPER/2026-05-11/mlb_odds_with_feature_candidate_probabilities.csv",
    )
    parser.add_argument(
        "--output-dir",
        default=f"outputs/predictions/PAPER/{datetime.now(timezone.utc).date()}/p13_ml",
    )
    parser.add_argument("--model-type", default="logistic_regression")
    parser.add_argument("--feature-policy", default="p13_v1")
    parser.add_argument("--min-train-size", type=int, default=300)
    parser.add_argument("--initial-train-months", type=int, default=2)
    parser.add_argument("--allow-market-prob-feature", action="store_true", default=False)
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"[REFUSED] input csv not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    _assert_paper_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_csv(input_path)
    matrix_rows, matrix_meta = build_ml_feature_matrix(
        rows,
        feature_policy=args.feature_policy,
        allow_market_prob_feature=args.allow_market_prob_feature,
    )
    if not matrix_rows:
        print("[REFUSED] feature matrix empty (all features missing or dropped).", file=sys.stderr)
        sys.exit(1)
    if matrix_meta.get("leakage_safe") is not True:
        print("[REFUSED] leakage_safe=false in matrix meta.", file=sys.stderr)
        sys.exit(1)

    feature_cols = list(matrix_meta.get("features_used") or [])
    preds, model_meta = run_walk_forward_ml_candidate(
        matrix_rows,
        feature_columns=feature_cols,
        model_type=args.model_type,
        min_train_size=args.min_train_size,
        initial_train_months=args.initial_train_months,
    )
    if not preds:
        print(f"[REFUSED] no predictions generated: {model_meta}", file=sys.stderr)
        sys.exit(1)

    matrix_csv = out_dir / "ml_feature_matrix.csv"
    preds_jsonl = out_dir / "ml_walk_forward_predictions.jsonl"
    merged_csv = out_dir / "ml_odds_with_walk_forward_predictions.csv"
    meta_json = out_dir / "ml_model_metadata.json"
    summary_md = out_dir / "ml_candidate_summary.md"

    _write_csv(matrix_rows, matrix_csv)
    with preds_jsonl.open("w", encoding="utf-8") as fh:
        for r in preds:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    _write_csv(preds, merged_csv)

    all_meta = {
        "input_count": len(rows),
        "matrix_meta": matrix_meta,
        "model_meta": model_meta,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_json.write_text(json.dumps(all_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    probs = [float(r["model_prob_home"]) for r in preds]
    summary_lines = [
        "# P13 Walk-Forward ML Candidate Summary",
        "",
        f"- input_count: {len(rows)}",
        f"- matrix_count: {len(matrix_rows)}",
        f"- prediction_count: {len(preds)}",
        f"- fold_count: {model_meta.get('fold_count', 0)}",
        f"- features_used: {', '.join(feature_cols)}",
        f"- probability_range: [{min(probs):.4f}, {max(probs):.4f}]",
        f"- model_type: {args.model_type}",
        f"- feature_policy: {args.feature_policy}",
        "",
        "## Outputs",
        f"- {matrix_csv}",
        f"- {preds_jsonl}",
        f"- {merged_csv}",
        f"- {meta_json}",
    ]
    summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(
        " | ".join(
            [
                f"input_count={len(rows)}",
                f"matrix_count={len(matrix_rows)}",
                f"prediction_count={len(preds)}",
                f"fold_count={model_meta.get('fold_count', 0)}",
                f"features_used={','.join(feature_cols)}",
                f"prob_range=[{min(probs):.4f},{max(probs):.4f}]",
                f"out={out_dir}",
            ]
        )
    )


if __name__ == "__main__":
    main()

