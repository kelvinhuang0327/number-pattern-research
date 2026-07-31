"""
scripts/run_mlb_strategy_simulation_spine.py

CLI entrypoint for running the MLB strategy simulation spine.

Usage:
    .venv/bin/python scripts/run_mlb_strategy_simulation_spine.py \\
        --date-start 2025-03-01 \\
        --date-end   2025-12-31 \\
        --strategy-name moneyline_edge_threshold_v0 \\
        --edge-threshold 0.01 \\
        --kelly-cap 0.05 \\
        --input-csv data/mlb_2025/mlb_odds_2025_real.csv

Refusals:
- Refuses if paper_only gate is removed.
- Refuses if input CSV does not exist.
- Refuses if output path is outside outputs/simulation/PAPER/.
- Refuses if attempting production mode.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Project root on sys.path ──────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wbc_backend.simulation.strategy_simulator import simulate_strategy
from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult

# ── Hard gates ────────────────────────────────────────────────────────────────
_PAPER_ONLY: bool = True                        # DO NOT change without P38 governance
_ALLOWED_OUTPUT_PREFIX = "outputs/simulation/PAPER"

_DEFAULT_INPUT_CSV = "data/mlb_2025/mlb_odds_2025_real.csv"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _refuse(reason: str) -> None:
    print(f"[REFUSED] {reason}", file=sys.stderr)
    sys.exit(2)


def _load_csv_rows(csv_path: Path) -> list[dict]:
    """Load CSV into a list of dicts."""
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    return rows


def _filter_rows_by_date(
    rows: list[dict],
    date_start: str,
    date_end: str,
) -> list[dict]:
    """Keep rows whose Date column falls in [date_start, date_end]."""
    filtered: list[dict] = []
    for row in rows:
        date_str = str(row.get("Date") or row.get("date") or "").strip()
        if not date_str:
            continue
        # Normalize: keep first 10 chars (YYYY-MM-DD)
        try:
            d = date_str[:10]
            if date_start <= d <= date_end:
                filtered.append(row)
        except Exception:
            continue
    return filtered


def _resolve_output_dir(output_dir: str | None, date_today: str) -> Path:
    """Resolve and validate output directory.

    The path must contain 'outputs/simulation/PAPER' as a component anywhere
    in its absolute path, to prevent writes to production or arbitrary zones.
    """
    if output_dir is None:
        output_dir = f"outputs/simulation/PAPER/{date_today}"
    resolved = Path(output_dir)
    resolved_abs = resolved.resolve()
    # Security: path must contain outputs/simulation/PAPER as a path segment
    # This works for both project-relative and absolute test temp paths.
    path_str = resolved_abs.as_posix()
    if "outputs/simulation/PAPER" not in path_str:
        _refuse(
            f"Output path '{output_dir}' is not under 'outputs/simulation/PAPER'. "
            "Writes outside the PAPER simulation zone are not permitted."
        )
    return resolved


def _write_jsonl(result: StrategySimulationResult, out_dir: Path) -> Path:
    """Write simulation result as a JSONL file."""
    slug = result.strategy_name.replace(" ", "_")[:48]
    fname = f"{result.date_start}_{result.date_end}_{slug}_{result.simulation_id[-8:]}.jsonl"
    out_path = out_dir / fname
    out_path.write_text(result.to_jsonl_line() + "\n", encoding="utf-8")
    return out_path


def _write_md_summary(result: StrategySimulationResult, out_dir: Path) -> Path:
    """Write a Markdown summary of the simulation result."""
    slug = result.strategy_name.replace(" ", "_")[:48]
    fname = f"{result.date_start}_{result.date_end}_{slug}_{result.simulation_id[-8:]}_report.md"
    out_path = out_dir / fname

    def _fmt(v: float | None, decimals: int = 4) -> str:
        return f"{v:.{decimals}f}" if v is not None else "null"

    lines = [
        f"# Strategy Simulation Report — {result.strategy_name}",
        f"",
        f"**Simulation ID:** `{result.simulation_id}`  ",
        f"**Date Range:** {result.date_start} → {result.date_end}  ",
        f"**Generated:** {result.generated_at_utc.isoformat()}  ",
        f"**Paper-Only:** {result.paper_only}  ",
        f"",
        f"## Gate Status",
        f"",
        f"**`{result.gate_status}`**",
        f"",
    ]
    for reason in result.gate_reasons:
        lines.append(f"- {reason}")
    lines += [
        f"",
        f"## Metrics Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Sample size | {result.sample_size} |",
        f"| Bet count | {result.bet_count} |",
        f"| Skipped count | {result.skipped_count} |",
        f"| Avg model prob | {_fmt(result.avg_model_prob)} |",
        f"| Avg market prob | {_fmt(result.avg_market_prob)} |",
        f"| Brier (model) | {_fmt(result.brier_model)} |",
        f"| Brier (market) | {_fmt(result.brier_market)} |",
        f"| Brier Skill Score | {_fmt(result.brier_skill_score)} |",
        f"| ECE | {_fmt(result.ece)} |",
        f"| ROI (%) | {_fmt(result.roi_pct, 2)} |",
        f"| Max Drawdown (%) | {_fmt(result.max_drawdown_pct, 2)} |",
        f"| Sharpe proxy | {_fmt(result.sharpe_proxy, 4)} |",
        f"| Avg edge (%) | {_fmt(result.avg_edge_pct, 4) if result.avg_edge_pct is not None else 'null'} |",
        f"| Avg Kelly fraction | {_fmt(result.avg_kelly_fraction, 4)} |",
        f"",
        f"## Source Trace",
        f"",
        f"```json",
        json.dumps(result.source_trace, indent=2, ensure_ascii=False),
        f"```",
        f"",
        f"---",
        f"*PAPER-ONLY simulation. No real bets placed. No production enablement.*",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MLB strategy simulation spine (PAPER-ONLY)"
    )
    parser.add_argument("--date-start", default="2025-03-01", help="YYYY-MM-DD")
    parser.add_argument("--date-end", default="2025-12-31", help="YYYY-MM-DD")
    parser.add_argument(
        "--strategy-name", default="moneyline_edge_threshold_v0", help="Strategy name"
    )
    parser.add_argument(
        "--edge-threshold", type=float, default=0.0, help="Min edge to place a bet"
    )
    parser.add_argument(
        "--kelly-cap", type=float, default=0.05, help="Max Kelly fraction"
    )
    parser.add_argument(
        "--input-csv",
        default=_DEFAULT_INPUT_CSV,
        help="Path to historical odds CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output dir (default: outputs/simulation/PAPER/YYYY-MM-DD/)",
    )
    args = parser.parse_args()

    # ── Hard-gate checks ─────────────────────────────────────────────────────
    if not _PAPER_ONLY:
        _refuse("_PAPER_ONLY gate is False. This script must run in paper-only mode.")

    # ── Resolve input CSV ─────────────────────────────────────────────────────
    csv_path = Path(args.input_csv)
    if not csv_path.is_absolute():
        csv_path = _ROOT / csv_path
    if not csv_path.exists():
        _refuse(f"Input CSV does not exist: {csv_path}")

    # ── Resolve output directory ──────────────────────────────────────────────
    date_today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    out_dir = _resolve_output_dir(args.output_dir, date_today)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load + filter data ────────────────────────────────────────────────────
    all_rows = _load_csv_rows(csv_path)
    rows = _filter_rows_by_date(all_rows, args.date_start, args.date_end)
    print(
        f"[PAPER-SIM] Loaded {len(all_rows)} rows from {csv_path.name}; "
        f"{len(rows)} in date range {args.date_start}→{args.date_end}"
    )

    # ── Run simulation ────────────────────────────────────────────────────────
    result = simulate_strategy(
        strategy_name=args.strategy_name,
        rows=rows,
        date_start=args.date_start,
        date_end=args.date_end,
        edge_threshold=args.edge_threshold,
        kelly_cap=args.kelly_cap,
    )

    # ── Write outputs ─────────────────────────────────────────────────────────
    jsonl_path = _write_jsonl(result, out_dir)
    md_path = _write_md_summary(result, out_dir)

    # ── Print one-line summary ────────────────────────────────────────────────
    bss_str = f"{result.brier_skill_score:.4f}" if result.brier_skill_score is not None else "null"
    ece_str = f"{result.ece:.4f}" if result.ece is not None else "null"
    roi_str = f"{result.roi_pct:.2f}%" if result.roi_pct is not None else "null"

    print(
        f"[PAPER-SIM] strategy={result.strategy_name} | "
        f"n={result.sample_size} | bets={result.bet_count} | "
        f"BSS={bss_str} | ECE={ece_str} | ROI={roi_str} | "
        f"gate={result.gate_status}"
    )
    print(f"[PAPER-SIM] JSONL → {jsonl_path}")
    print(f"[PAPER-SIM] Report → {md_path}")


if __name__ == "__main__":
    main()
