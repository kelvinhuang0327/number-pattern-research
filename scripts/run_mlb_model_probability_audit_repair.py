"""
scripts/run_mlb_model_probability_audit_repair.py

P6: CLI for MLB model probability audit and calibration repair.

Usage:
    python scripts/run_mlb_model_probability_audit_repair.py \
        --input-csv outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv \
        --n-bins 10 \
        --min-bin-size 30

Security:
  - Input CSV must exist.
  - Output dir must be under outputs/predictions/PAPER/.
  - Market-proxy-only inputs are refused unless --allow-market-proxy-audit is passed.
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
    """Raise SystemExit if path is not under outputs/predictions/PAPER/."""
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
        reader = csv.DictReader(f)
        return list(reader)


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P6 MLB model probability audit and calibration repair CLI."
    )
    parser.add_argument(
        "--input-csv",
        default=str(
            _REPO_ROOT / "outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv"
        ),
        help="Path to enriched odds CSV with model_prob_home.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Output directory for audit artifacts. "
            "Must be under outputs/predictions/PAPER/. "
            "Default: outputs/predictions/PAPER/YYYY-MM-DD/"
        ),
    )
    parser.add_argument(
        "--date-start",
        default=None,
        help="Filter rows to this start date (YYYY-MM-DD), inclusive.",
    )
    parser.add_argument(
        "--date-end",
        default=None,
        help="Filter rows to this end date (YYYY-MM-DD), inclusive.",
    )
    parser.add_argument(
        "--n-bins",
        type=int,
        default=10,
        help="Number of calibration bins (default 10).",
    )
    parser.add_argument(
        "--min-bin-size",
        type=int,
        default=30,
        help="Minimum samples per bin before fallback to global rate (default 30).",
    )
    parser.add_argument(
        "--write-calibrated",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Write calibrated CSV (default True).",
    )
    parser.add_argument(
        "--allow-market-proxy-audit",
        action="store_true",
        default=False,
        help="Allow audit even if all rows are market_proxy (usually refused).",
    )

    args = parser.parse_args()

    # ── Input validation ──────────────────────────────────────────────────────
    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"[REFUSED] Input CSV does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    # ── Output dir ────────────────────────────────────────────────────────────
    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = _REPO_ROOT / "outputs" / "predictions" / "PAPER" / today_str

    _assert_paper_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load rows ─────────────────────────────────────────────────────────────
    rows = _load_csv(input_path)

    # Date filter
    if args.date_start or args.date_end:
        filtered = []
        for row in rows:
            d = str(row.get("Date") or "")
            if args.date_start and d < args.date_start:
                continue
            if args.date_end and d > args.date_end:
                continue
            filtered.append(row)
        rows = filtered

    # ── Market-proxy guard ────────────────────────────────────────────────────
    enriched_rows = [r for r in rows if r.get("model_prob_home", "").strip()]
    if enriched_rows:
        all_proxy = all(
            str(r.get("probability_source", "")).lower() in ("market_proxy", "")
            for r in enriched_rows
        )
        if all_proxy and not args.allow_market_proxy_audit:
            print(
                "[REFUSED] All enriched rows use market_proxy probability source. "
                "Pass --allow-market-proxy-audit to proceed.",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── Import audit and repair modules ──────────────────────────────────────
    sys.path.insert(0, str(_REPO_ROOT))
    from wbc_backend.prediction.mlb_model_probability_audit import (
        audit_model_probability_rows,
        segment_model_probability_audit,
    )
    from wbc_backend.prediction.mlb_probability_calibration_repair import (
        calibrate_probabilities_by_bins,
        evaluate_calibration_candidate,
    )

    # ── Step 1: Full audit ────────────────────────────────────────────────────
    audit_result = audit_model_probability_rows(rows)

    audit_path = output_dir / "model_probability_audit.json"
    audit_path.write_text(json.dumps(audit_result, indent=2))

    # ── Step 2: Segment audits ────────────────────────────────────────────────
    segment_results: dict[str, list[dict]] = {}
    for seg in ("month", "confidence_bucket", "market_prob_bucket", "favorite_side", "probability_source"):
        try:
            segment_results[seg] = segment_model_probability_audit(rows, seg)
        except Exception as exc:
            segment_results[seg] = [{"error": str(exc)}]

    segment_path = output_dir / "model_probability_segment_audit.json"
    segment_path.write_text(json.dumps(segment_results, indent=2))

    # ── Step 3: Calibration repair ────────────────────────────────────────────
    calibrated_path: Path | None = None
    eval_path: Path | None = None
    eval_result: dict = {}

    if args.write_calibrated:
        calibrated_rows = calibrate_probabilities_by_bins(
            rows,
            n_bins=args.n_bins,
            min_bin_size=args.min_bin_size,
        )
        calibrated_path = output_dir / "mlb_odds_with_calibrated_probabilities.csv"
        _write_csv(calibrated_rows, calibrated_path)

        # ── Step 4: Evaluate ──────────────────────────────────────────────────
        eval_result = evaluate_calibration_candidate(rows, calibrated_rows)
        eval_path = output_dir / "calibration_candidate_evaluation.json"
        eval_path.write_text(json.dumps(eval_result, indent=2))

    # ── Step 5: Markdown summary ──────────────────────────────────────────────
    md_path = output_dir / "p6_audit_repair_summary.md"
    _write_markdown_summary(
        audit_result,
        segment_results,
        eval_result,
        md_path,
        args,
    )

    # ── Print one-line summary ────────────────────────────────────────────────
    print(
        f"original_bss={audit_result.get('brier_skill_score')} | "
        f"calibrated_bss={eval_result.get('calibrated_bss')} | "
        f"original_ece={audit_result.get('ece')} | "
        f"calibrated_ece={eval_result.get('calibrated_ece')} | "
        f"recommendation={eval_result.get('recommendation', 'N/A')} | "
        f"audit_json={audit_path} | "
        f"segment_json={segment_path} | "
        f"calibrated_csv={calibrated_path} | "
        f"eval_json={eval_path} | "
        f"md_report={md_path}"
    )


def _write_markdown_summary(
    audit: dict,
    segments: dict,
    evaluation: dict,
    path: Path,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# P6 MLB Model Probability Audit & Calibration Repair",
        "",
        f"**Generated**: {datetime.now(tz=timezone.utc).isoformat()}",
        f"**Input**: `{args.input_csv}`",
        f"**Bins**: {args.n_bins} | **Min bin size**: {args.min_bin_size}",
        "",
        "## Audit Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Row count | {audit.get('row_count')} |",
        f"| Usable count | {audit.get('usable_count')} |",
        f"| Missing model prob | {audit.get('missing_model_prob_count')} |",
        f"| Missing market prob | {audit.get('missing_market_prob_count')} |",
        f"| Missing outcome | {audit.get('missing_outcome_count')} |",
        f"| Model Brier | {audit.get('model_brier')} |",
        f"| Market Brier | {audit.get('market_brier')} |",
        f"| **BSS** | **{audit.get('brier_skill_score')}** |",
        f"| ECE | {audit.get('ece')} |",
        f"| Avg model prob | {audit.get('avg_model_prob')} |",
        f"| Avg market prob | {audit.get('avg_market_prob')} |",
        f"| Avg outcome (home win rate) | {audit.get('avg_outcome')} |",
        "",
    ]

    oc = audit.get("orientation_checks", {})
    lines += [
        "## Orientation Checks",
        "",
        "| Check | Value |",
        "|---|---|",
        f"| Home win rate when model > 0.5 | {oc.get('home_win_rate_when_model_gt_0_5')} |",
        f"| Home win rate when model < 0.5 | {oc.get('home_win_rate_when_model_lt_0_5')} |",
        f"| Avg model prob when home wins | {oc.get('avg_model_prob_when_home_wins')} |",
        f"| Avg model prob when home loses | {oc.get('avg_model_prob_when_home_loses')} |",
        "",
    ]

    lines += [
        "## Segment Audits — Monthly BSS",
        "",
        "| Month | Count | Model Brier | Market Brier | BSS | ECE |",
        "|---|---|---|---|---|---|",
    ]
    for seg in segments.get("month", []):
        if "error" not in seg:
            lines.append(
                f"| {seg['segment']} | {seg['row_count']} | "
                f"{seg['model_brier']} | {seg['market_brier']} | "
                f"{seg['bss']} | {seg['ece']} |"
            )

    lines += [
        "",
        "## Segment Audits — Market Prob Bucket",
        "",
        "| Bucket | Count | BSS | ECE |",
        "|---|---|---|---|",
    ]
    for seg in segments.get("market_prob_bucket", []):
        if "error" not in seg:
            lines.append(
                f"| {seg['segment']} | {seg['row_count']} | {seg['bss']} | {seg['ece']} |"
            )

    lines += [
        "",
        "## Segment Audits — Favorite Side",
        "",
        "| Side | Count | BSS | ECE |",
        "|---|---|---|---|",
    ]
    for seg in segments.get("favorite_side", []):
        if "error" not in seg:
            lines.append(
                f"| {seg['segment']} | {seg['row_count']} | {seg['bss']} | {seg['ece']} |"
            )

    if evaluation:
        lines += [
            "",
            "## Calibration Candidate Evaluation",
            "",
            f"| Metric | Original | Calibrated | Delta |",
            f"|---|---|---|---|",
            f"| BSS | {evaluation.get('original_bss')} | {evaluation.get('calibrated_bss')} | {evaluation.get('delta_bss')} |",
            f"| ECE | {evaluation.get('original_ece')} | {evaluation.get('calibrated_ece')} | {evaluation.get('delta_ece')} |",
            f"",
            f"**Recommendation**: `{evaluation.get('recommendation')}`",
            f"",
            f"> ⚠️ {evaluation.get('in_sample_warning')}",
        ]

    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
