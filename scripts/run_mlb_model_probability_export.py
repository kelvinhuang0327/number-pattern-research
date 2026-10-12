#!/usr/bin/env python3
"""
scripts/run_mlb_model_probability_export.py

CLI to generate probability-enriched simulation input from historical odds CSV.

Behavior:
1. Load existing model probability artifact (data/derived/model_outputs_2026-04-29.jsonl).
2. Merge real model probabilities into odds rows.
3. If no real model probabilities found and --allow-market-proxy is not set: fail clearly.
4. Write JSONL probabilities under outputs/predictions/PAPER/YYYY-MM-DD/.
5. Write merged CSV under outputs/predictions/PAPER/YYYY-MM-DD/.
6. Print summary statistics.

Security:
- All output restricted to outputs/predictions/PAPER/.
- market_proxy is never labelled as real_model.
- Production mode never enabled.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

_PAPER_PREDICTIONS_ZONE = "outputs/predictions/PAPER"


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
        description="Export MLB model probabilities enriched into historical odds CSV."
    )
    parser.add_argument(
        "--input-csv",
        default=str(_REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"),
        help="Path to historical odds CSV.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(default_out_dir / "mlb_model_probabilities.jsonl"),
        help="Output JSONL path for probability records.",
    )
    parser.add_argument(
        "--merged-output-csv",
        default=str(default_out_dir / "mlb_odds_with_model_probabilities.csv"),
        help="Output CSV path for odds rows enriched with model probabilities.",
    )
    parser.add_argument(
        "--model-version",
        default="v1-mlb-moneyline-trained",
        help="Model version label.",
    )
    parser.add_argument(
        "--allow-market-proxy",
        action="store_true",
        default=False,
        help=(
            "If set, rows without real model probabilities fall back to "
            "market-implied probability. Clearly labelled as market_proxy."
        ),
    )
    args = parser.parse_args()

    # ── Validate output paths ──────────────────────────────────────────────────
    output_jsonl = Path(args.output_jsonl)
    merged_csv = Path(args.merged_output_csv)
    _assert_paper_output_path(output_jsonl)
    _assert_paper_output_path(merged_csv)

    # ── Load and build model probabilities ────────────────────────────────────
    try:
        from wbc_backend.prediction.mlb_model_probability_adapter import (
            build_model_probabilities_from_existing_artifacts,
            merge_model_probabilities_into_rows,
        )
    except ImportError as exc:
        print(f"FATAL: Cannot import adapter: {exc}", file=sys.stderr)
        return 2

    print(f"[PROB-EXPORT] Loading probabilities from model artifact...")
    try:
        probabilities = build_model_probabilities_from_existing_artifacts(
            odds_csv_path=args.input_csv,
            output_jsonl_path=output_jsonl,
            model_version=args.model_version,
            allow_market_proxy=args.allow_market_proxy,
        )
    except ValueError as exc:
        print(f"[PROB-EXPORT] REFUSED: {exc}", file=sys.stderr)
        return 1

    # ── Statistics ────────────────────────────────────────────────────────────
    real_model_count = sum(
        1 for p in probabilities
        if p.probability_source in ("real_model", "calibrated_model")
    )
    market_proxy_count = sum(
        1 for p in probabilities
        if p.probability_source == "market_proxy"
    )

    print(f"[PROB-EXPORT] probability_count={len(probabilities)}")
    print(f"[PROB-EXPORT] real_model_count (calibrated + real_model)={real_model_count}")
    print(f"[PROB-EXPORT] market_proxy_count={market_proxy_count}")
    print(f"[PROB-EXPORT] output_jsonl={output_jsonl}")

    # ── Merge into odds rows ──────────────────────────────────────────────────
    try:
        import pandas as pd
    except ImportError:
        print("FATAL: pandas not available.", file=sys.stderr)
        return 2

    df_odds = pd.read_csv(args.input_csv)
    odds_rows = df_odds.to_dict(orient="records")

    enriched_rows = merge_model_probabilities_into_rows(odds_rows, probabilities)

    enriched_df = pd.DataFrame(enriched_rows)
    merged_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.to_csv(merged_csv, index=False)

    enriched_with_model = sum(
        1 for r in enriched_rows if r.get("model_prob_home") is not None
    )
    print(f"[PROB-EXPORT] row_count={len(enriched_rows)}")
    print(f"[PROB-EXPORT] enriched_with_model_prob={enriched_with_model}")
    print(f"[PROB-EXPORT] merged_output_csv={merged_csv}")

    if not args.allow_market_proxy and market_proxy_count > 0:
        print(
            "[PROB-EXPORT] WARNING: market_proxy rows detected but --allow-market-proxy "
            "was not set. This should not happen — check adapter logic.",
            file=sys.stderr,
        )
        return 1

    print("[PROB-EXPORT] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
