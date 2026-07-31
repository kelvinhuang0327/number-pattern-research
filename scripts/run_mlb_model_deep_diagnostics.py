"""
scripts/run_mlb_model_deep_diagnostics.py

P8: CLI for running deep model diagnostics on raw and OOF-calibrated CSVs.

Usage:
    .venv/bin/python scripts/run_mlb_model_deep_diagnostics.py \\
        --raw-input-csv outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv \\
        --input-csv     outputs/predictions/PAPER/2026-05-11/mlb_odds_with_oof_calibrated_probabilities.csv \\
        --top-n 10

Refusals:
  - Input CSV paths must exist.
  - Output dir must be inside outputs/predictions/PAPER/.
  - No production artifacts.
  - At least one real_model or calibrated_model probability source required.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wbc_backend.prediction.mlb_model_deep_diagnostics import (
    find_worst_model_segments,
    run_model_deep_diagnostics,
)
from wbc_backend.prediction.mlb_prediction_join_audit import (
    audit_prediction_join_integrity,
)

# ── Hard gates ────────────────────────────────────────────────────────────────
_PAPER_ONLY: bool = True
_ALLOWED_OUTPUT_PREFIX = "outputs/predictions/PAPER"


def _refuse(reason: str, code: int = 1) -> None:
    print(f"[REFUSED] {reason}", file=sys.stderr)
    sys.exit(code)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _assert_paper_output_dir(output_dir: Path) -> None:
    """Refuse if output_dir is outside outputs/predictions/PAPER/."""
    try:
        rel = output_dir.resolve().relative_to(_ROOT.resolve())
        rel_str = str(rel).replace("\\", "/")
    except ValueError:
        _refuse(f"Output dir '{output_dir}' is outside the repo root.", code=2)
        return
    if not rel_str.startswith(_ALLOWED_OUTPUT_PREFIX):
        _refuse(
            f"Output dir '{rel_str}' is outside allowed zone "
            f"'{_ALLOWED_OUTPUT_PREFIX}'. "
            "Do not write production artifacts.",
            code=2,
        )


def _load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    return rows


def _check_prob_source(rows: list[dict], label: str) -> None:
    """Refuse if no real_model or calibrated_model probability source found."""
    sources = set()
    for row in rows:
        src = str(row.get("probability_source") or "").strip().lower()
        if src:
            sources.add(src)
    valid_sources = {"real_model", "calibrated_model"}
    if not sources.intersection(valid_sources):
        _refuse(
            f"{label}: no real_model or calibrated_model probability source found in CSV. "
            f"Found sources: {sorted(sources) or ['none']}. "
            "Cannot run deep diagnostics without model probabilities."
        )


def _detect_date_col(rows: list[dict]) -> str:
    """Return the date column name present in the rows."""
    if rows and "Date" in rows[0]:
        return "Date"
    return "date"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Markdown summary builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary_md(
    raw_diag: dict,
    oof_diag: dict,
    join_audit: dict,
    worst_segs: list[dict],
    run_date: str,
) -> str:
    def _fmt(v: object) -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:.6f}"
        return str(v)

    raw_orient = raw_diag.get("orientation_diagnostics", {})
    oof_orient = oof_diag.get("orientation_diagnostics", {})

    lines = [
        "# P8 Model Deep Diagnostics Summary",
        f"**Generated:** {run_date}",
        "",
        "## Core Metrics: Raw vs OOF",
        "",
        "| Metric | Raw Model | OOF Calibrated | Delta |",
        "|---|---|---|---|",
    ]

    def _delta(a: object, b: object) -> str:
        if isinstance(a, float) and isinstance(b, float):
            return f"{b - a:+.6f}"
        return "—"

    for metric, raw_key, oof_key in [
        ("BSS", "brier_skill_score", "brier_skill_score"),
        ("ECE", "ece", "ece"),
        ("Model Brier", "model_brier", "model_brier"),
        ("Market Brier", "market_brier", "market_brier"),
        ("Avg Model Prob", "avg_model_prob", "avg_model_prob"),
        ("Avg Market Prob", "avg_market_prob", "avg_market_prob"),
        ("Avg Home Win Rate", "avg_home_win_rate", "avg_home_win_rate"),
        ("Avg Model−Market", "avg_model_minus_market", "avg_model_minus_market"),
        ("Usable Rows", "usable_count", "usable_count"),
    ]:
        rv = raw_diag.get(raw_key)
        ov = oof_diag.get(oof_key)
        lines.append(f"| {metric} | {_fmt(rv)} | {_fmt(ov)} | {_delta(rv, ov)} |")

    lines += [
        "",
        "## Orientation Diagnostics",
        "",
        "| Orientation | Raw BSS | OOF BSS |",
        "|---|---|---|",
        f"| normal | {_fmt(raw_orient.get('bss_normal'))} | {_fmt(oof_orient.get('bss_normal'))} |",
        f"| inverted_model | {_fmt(raw_orient.get('bss_inverted_model'))} | {_fmt(oof_orient.get('bss_inverted_model'))} |",
        f"| swapped_home_away | {_fmt(raw_orient.get('bss_swapped_home_away'))} | {_fmt(oof_orient.get('bss_swapped_home_away'))} |",
        f"| **best_orientation** | **{raw_orient.get('best_orientation', 'unknown')}** | **{oof_orient.get('best_orientation', 'unknown')}** |",
        "",
    ]

    raw_warn = raw_orient.get("orientation_warning")
    oof_warn = oof_orient.get("orientation_warning")
    if raw_warn:
        lines.append(f"> **Raw orientation warning:** {raw_warn}")
    if oof_warn:
        lines.append(f"> **OOF orientation warning:** {oof_warn}")

    lines += [
        "",
        "## Join Integrity Audit",
        "",
        f"- **risk_level:** {join_audit.get('risk_level', 'unknown')}",
        f"- missing_game_id: {join_audit.get('missing_game_id_count')}",
        f"- duplicate_game_id: {join_audit.get('duplicate_game_id_count')}",
        f"- duplicate_date_team_key: {join_audit.get('duplicate_date_team_key_count')}",
        f"- missing_home_team: {join_audit.get('missing_home_team_count')}",
        f"- missing_away_team: {join_audit.get('missing_away_team_count')}",
        f"- same_home_away: {join_audit.get('same_home_away_count')}",
    ]
    if join_audit.get("risk_reasons"):
        for r in join_audit["risk_reasons"]:
            lines.append(f"- ⚠️ {r}")

    lines += ["", "## Worst Segments (by composite score)", ""]
    if worst_segs:
        lines.append("| # | Segment | By | Rows | BSS | ECE | Avg Edge | Reason |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, seg in enumerate(worst_segs[:10], 1):
            lines.append(
                f"| {i} | {seg['segment']} | {seg['segment_by']} | "
                f"{seg['row_count']} | {_fmt(seg['bss'])} | "
                f"{_fmt(seg['ece'])} | {_fmt(seg['avg_edge'])} | {seg['rank_reason']} |"
            )
    else:
        lines.append("No segments with sufficient data found.")

    lines += [
        "",
        "## Probability Diagnostics (OOF)",
        "",
    ]
    prob_diag = oof_diag.get("probability_diagnostics", {})
    for k in (
        "model_prob_min", "model_prob_max", "model_prob_std",
        "market_prob_min", "market_prob_max", "market_prob_std",
        "overconfident_count", "underconfident_count",
    ):
        lines.append(f"- {k}: {_fmt(prob_diag.get(k))}")

    lines += [
        "",
        "## Outcome Diagnostics (OOF rows)",
        "",
    ]
    out_diag = oof_diag.get("outcome_diagnostics", {})
    for k in ("outcome_one_count", "outcome_zero_count", "outcome_null_count", "outcome_balance"):
        lines.append(f"- {k}: {_fmt(out_diag.get(k))}")

    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P8: Run deep model diagnostics on raw and OOF-calibrated CSV."
    )
    parser.add_argument(
        "--input-csv",
        default="outputs/predictions/PAPER/2026-05-11/mlb_odds_with_oof_calibrated_probabilities.csv",
        help="OOF-calibrated CSV (default: 2026-05-11 OOF output).",
    )
    parser.add_argument(
        "--raw-input-csv",
        default="outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv",
        help="Raw real-model CSV (P5 artifact).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: same dir as --input-csv).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of worst segments to surface (default: 10).",
    )
    args = parser.parse_args()

    raw_path = _ROOT / args.raw_input_csv
    oof_path = _ROOT / args.input_csv

    # ── Refusal: inputs must exist ───────────────────────────────────────────
    if not raw_path.exists():
        _refuse(f"Raw input CSV not found: {raw_path}")
    if not oof_path.exists():
        _refuse(f"OOF input CSV not found: {oof_path}")

    # ── Output dir ────────────────────────────────────────────────────────────
    if args.output_dir:
        output_dir = _ROOT / args.output_dir
    else:
        output_dir = oof_path.parent

    _assert_paper_output_dir(output_dir)

    # ── Load CSVs ─────────────────────────────────────────────────────────────
    raw_rows = _load_csv(raw_path)
    oof_rows = _load_csv(oof_path)

    # ── Refusal: probability source check ────────────────────────────────────
    _check_prob_source(raw_rows, "raw-input-csv")
    _check_prob_source(oof_rows, "input-csv (OOF)")

    # ── Date col detection ────────────────────────────────────────────────────
    raw_date_col = _detect_date_col(raw_rows)
    oof_date_col = _detect_date_col(oof_rows)

    # ── Run diagnostics ───────────────────────────────────────────────────────
    raw_diag = run_model_deep_diagnostics(
        raw_rows,
        model_prob_col="model_prob_home",
        outcome_col="home_win",
        date_col=raw_date_col,
    )
    oof_diag = run_model_deep_diagnostics(
        oof_rows,
        model_prob_col="model_prob_home",
        outcome_col="home_win",
        date_col=oof_date_col,
    )

    # ── Join audit ────────────────────────────────────────────────────────────
    join_audit = audit_prediction_join_integrity(
        oof_rows,
        date_col=oof_date_col,
    )

    # ── Worst segments (from OOF diagnostics) ────────────────────────────────
    worst_segs = find_worst_model_segments(oof_diag, top_n=args.top_n)

    # ── BSS / ECE comparison ──────────────────────────────────────────────────
    raw_bss = raw_diag.get("brier_skill_score")
    oof_bss = oof_diag.get("brier_skill_score")
    raw_ece = raw_diag.get("ece")
    oof_ece = oof_diag.get("ece")
    best_orient = (oof_diag.get("orientation_diagnostics") or {}).get("best_orientation", "unknown")
    join_risk = join_audit.get("risk_level", "unknown")
    worst_seg_label = worst_segs[0]["segment"] if worst_segs else "none"

    # ── Write outputs ─────────────────────────────────────────────────────────
    run_date = datetime.now(timezone.utc).isoformat()

    raw_diag["generated_at"] = run_date
    oof_diag["generated_at"] = run_date
    join_audit["generated_at"] = run_date

    raw_json_path = output_dir / "model_deep_diagnostics_raw.json"
    oof_json_path = output_dir / "model_deep_diagnostics_oof.json"
    join_json_path = output_dir / "model_join_integrity_audit.json"
    worst_json_path = output_dir / "model_worst_segments.json"
    summary_md_path = output_dir / "model_deep_diagnostics_summary.md"

    _write_json(raw_json_path, raw_diag)
    _write_json(oof_json_path, oof_diag)
    _write_json(join_json_path, join_audit)
    _write_json(worst_json_path, {"worst_segments": worst_segs, "generated_at": run_date})
    _write_md(summary_md_path, _build_summary_md(raw_diag, oof_diag, join_audit, worst_segs, run_date))

    # ── One-line stdout summary ───────────────────────────────────────────────
    print(
        f"raw_bss={raw_bss} | oof_bss={oof_bss} | "
        f"raw_ece={raw_ece} | oof_ece={oof_ece} | "
        f"best_orientation={best_orient} | join_risk_level={join_risk} | "
        f"worst_segment={worst_seg_label} | "
        f"raw_diag={raw_json_path.relative_to(_ROOT)} | "
        f"oof_diag={oof_json_path.relative_to(_ROOT)} | "
        f"join_audit={join_json_path.relative_to(_ROOT)} | "
        f"worst_segs={worst_json_path.relative_to(_ROOT)} | "
        f"summary_md={summary_md_path.relative_to(_ROOT)}"
    )


if __name__ == "__main__":
    main()
