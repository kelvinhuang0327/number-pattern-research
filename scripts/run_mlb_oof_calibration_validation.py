"""
scripts/run_mlb_oof_calibration_validation.py

P7: CLI for walk-forward OOF calibration validation.

Usage:
    python scripts/run_mlb_oof_calibration_validation.py \
        --input-csv outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv \
        --n-bins 10 \
        --min-train-size 300 \
        --min-bin-size 30 \
        --initial-train-months 2

Security:
  - Input CSV must exist.
  - Output dir must be under outputs/predictions/PAPER/.
  - Market-proxy-only inputs are refused unless --allow-market-proxy-input.
  - Refuses if no chronological date column can be resolved.
  - No production writes.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PAPER_PREDICTIONS_ZONE = "outputs/predictions/PAPER"


def _assert_paper_output_dir(path: Path) -> None:
    resolved = path.resolve()
    if _PAPER_PREDICTIONS_ZONE not in resolved.as_posix():
        print(
            f"[REFUSED] Output dir must be under {_PAPER_PREDICTIONS_ZONE!r}. "
            f"Got: {resolved}",
            file=sys.stderr,
        )
        sys.exit(2)


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    # Flatten calibration_source_trace dict to JSON string if present
    flat: list[dict] = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("calibration_source_trace"), dict):
            r["calibration_source_trace"] = json.dumps(r["calibration_source_trace"])
        flat.append(r)
    fieldnames = list(flat[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat)


def _detect_date_col(rows: list[dict], candidate: str) -> str | None:
    """Return the actual date column name used in rows, or None."""
    for col in [candidate, "Date", "date", "game_date", "GameDate"]:
        if any(r.get(col) for r in rows[:20]):
            return col
    return None


def _detect_proxy_rows(rows: list[dict]) -> tuple[int, int]:
    """Return (proxy_count, total_enriched)."""
    proxy = 0
    enriched = 0
    for r in rows:
        src = str(r.get("probability_source") or "").lower()
        if r.get("model_prob_home"):
            enriched += 1
            if "proxy" in src or "market" in src:
                proxy += 1
    return proxy, enriched


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P7: Walk-forward OOF calibration validation CLI"
    )
    parser.add_argument(
        "--input-csv",
        default=str(
            _REPO_ROOT / "outputs" / "predictions" / "PAPER" / "2026-05-11"
            / "mlb_odds_with_model_probabilities.csv"
        ),
        help="Path to enriched CSV with model_prob_home.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (must be under outputs/predictions/PAPER/). "
             "Defaults to same dir as input CSV.",
    )
    parser.add_argument("--date-col", default="Date", help="Date column name.")
    parser.add_argument("--n-bins", type=int, default=10)
    parser.add_argument("--min-train-size", type=int, default=300)
    parser.add_argument("--min-bin-size", type=int, default=30)
    parser.add_argument("--initial-train-months", type=int, default=2)
    parser.add_argument(
        "--allow-market-proxy-input",
        action="store_true",
        help="Allow input where all enriched rows use market proxy (otherwise refused).",
    )
    args = parser.parse_args()

    # ── 1. Validate input ────────────────────────────────────────────────────
    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(
            f"[REFUSED] Input CSV not found: {input_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = _load_csv(input_path)
    if not rows:
        print("[REFUSED] Input CSV is empty.", file=sys.stderr)
        sys.exit(1)

    # ── 2. Validate output dir ───────────────────────────────────────────────
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent
    _assert_paper_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 3. Validate date column ──────────────────────────────────────────────
    actual_date_col = _detect_date_col(rows, args.date_col)
    if actual_date_col is None:
        print(
            f"[REFUSED] Cannot find a parseable date column. "
            f"Tried: {args.date_col!r}, 'Date', 'date'. "
            "Pass --date-col with the correct column name.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── 4. Market proxy check ────────────────────────────────────────────────
    proxy_count, enriched_count = _detect_proxy_rows(rows)
    if enriched_count > 0 and proxy_count == enriched_count and not args.allow_market_proxy_input:
        print(
            f"[REFUSED] All {proxy_count} enriched rows use market proxy as model probability. "
            "OOF calibration on market proxy produces meaningless BSS (~0 by construction). "
            "Pass --allow-market-proxy-input to override.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── 5. Load module ───────────────────────────────────────────────────────
    sys.path.insert(0, str(_REPO_ROOT))
    from wbc_backend.prediction.mlb_oof_calibration import (
        build_walk_forward_calibrated_rows,
        evaluate_oof_calibration,
    )

    # ── 6. Run OOF calibration ───────────────────────────────────────────────
    oof_rows, meta = build_walk_forward_calibrated_rows(
        rows,
        date_col=actual_date_col,
        n_bins=args.n_bins,
        min_train_size=args.min_train_size,
        min_bin_size=args.min_bin_size,
        initial_train_months=args.initial_train_months,
    )

    if not oof_rows and meta.get("error"):
        print(
            f"[REFUSED] OOF calibration failed: {meta['error']}. "
            f"Details: {meta}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── 7. Evaluate ──────────────────────────────────────────────────────────
    eval_result = evaluate_oof_calibration(rows, oof_rows)

    # ── 8. Write outputs ─────────────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).isoformat()

    # 8a. OOF calibrated CSV
    oof_csv_path = output_dir / "mlb_odds_with_oof_calibrated_probabilities.csv"
    _write_csv(oof_rows, oof_csv_path)

    # 8b. Evaluation JSON
    eval_json_path = output_dir / "oof_calibration_evaluation.json"
    eval_json_path.write_text(
        json.dumps({**eval_result, "generated_at": generated_at}, indent=2)
    )

    # 8c. Folds JSON
    folds_json_path = output_dir / "oof_calibration_folds.json"
    folds_json_path.write_text(
        json.dumps({"meta": meta, "generated_at": generated_at}, indent=2)
    )

    # 8d. Markdown summary report
    rec = eval_result["recommendation"]
    deploy = eval_result["deployability_status"]
    oof_bss = eval_result["oof_bss"]
    orig_bss = eval_result["original_bss"]
    oof_ece = eval_result["oof_ece"]
    orig_ece = eval_result["original_ece"]
    delta_bss = eval_result["delta_bss"]
    oof_row_count = eval_result["oof_row_count"]
    skipped = eval_result["skipped_row_count"]

    md_lines = [
        "# P7 OOF Calibration Validation Summary",
        "",
        f"**Generated**: {generated_at}",
        f"**Input**: {input_path}",
        "",
        "## Results",
        "",
        f"| Metric | Original | OOF Calibrated | Delta |",
        f"|--------|----------|----------------|-------|",
        f"| BSS | {orig_bss} | {oof_bss} | {delta_bss} |",
        f"| ECE | {orig_ece} | {oof_ece} | {eval_result['delta_ece']} |",
        "",
        f"**OOF Row Count**: {oof_row_count}",
        f"**Skipped (warm-up)**: {skipped}",
        f"**Total Folds**: {meta.get('total_folds', 'N/A')}",
        f"**First Validation Month**: {meta.get('first_val_month', 'N/A')}",
        "",
        "## Recommendation",
        "",
        f"**{rec}**",
        f"**Deployability**: {deploy}",
        "",
        "## Gate Reasons",
        "",
    ]
    for reason in eval_result["gate_reasons"]:
        md_lines.append(f"- {reason}")
    md_lines += [
        "",
        "## Leakage Safety",
        "",
        "- Calibration maps are fit on **past data only** (train_end < validation_start).",
        "- Validation outcomes are **never used** in calibration fitting.",
        "- `leakage_safe = True` in all OOF row traces.",
        "",
        "> ⚠️ walk-forward OOF calibration candidate; production still requires human approval",
    ]

    md_report_path = output_dir / "p7_oof_calibration_summary.md"
    md_report_path.write_text("\n".join(md_lines))

    # ── 9. Print one-line summary ────────────────────────────────────────────
    print(
        f"original_bss={orig_bss} | oof_bss={oof_bss} | "
        f"original_ece={orig_ece} | oof_ece={oof_ece} | "
        f"oof_row_count={oof_row_count} | skipped={skipped} | "
        f"recommendation={rec} | deployability={deploy} | "
        f"oof_csv={oof_csv_path} | eval_json={eval_json_path} | "
        f"folds_json={folds_json_path} | md_report={md_report_path}"
    )


if __name__ == "__main__":
    main()
