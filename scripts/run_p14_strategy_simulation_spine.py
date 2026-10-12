"""
scripts/run_p14_strategy_simulation_spine.py

P14: CLI entrypoint for strategy simulation spine activation.

Usage:
    .venv/bin/python scripts/run_p14_strategy_simulation_spine.py \\
        --p13-oof-dir outputs/predictions/PAPER/2026-05-12/p13_walk_forward_logistic \\
        --output-dir  outputs/predictions/PAPER/2026-05-12/p14_strategy_simulation \\
        --policies    flat,capped_kelly,confidence_rank,no_bet \\
        --paper-only

Outputs (all written to --output-dir):
    simulation_summary.json   – aggregated spine summary per policy
    simulation_summary.md     – human-readable report
    simulation_ledger.csv     – per-row per-policy bet decisions

Refusals:
- Refuses if paper_only gate is removed.
- Refuses if --p13-oof-dir does not contain oof_predictions.csv.
- Refuses if oof_report.json shows gate_decision != PASS.
- Refuses if output path is outside outputs/predictions/PAPER/.
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

from wbc_backend.simulation.p13_strategy_simulator import (
    P13StrategySimulationRunner,
    SimulationSummary,
)

# ── Hard gates ────────────────────────────────────────────────────────────────
_PAPER_ONLY: bool = True           # DO NOT change
_ALLOWED_OUTPUT_PREFIX = "outputs/predictions/PAPER"
_OOF_CSV_FILENAME = "oof_predictions.csv"
_OOF_REPORT_FILENAME = "oof_report.json"

_VALID_POLICIES = {"flat", "capped_kelly", "confidence_rank", "no_bet"}
_DEFAULT_POLICIES = "flat,capped_kelly,confidence_rank,no_bet"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _refuse(reason: str) -> None:
    print(f"[REFUSED] {reason}", file=sys.stderr)
    sys.exit(2)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P14 strategy simulation spine activation CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--p13-oof-dir",
        required=True,
        help="Directory containing P13 oof_predictions.csv and oof_report.json",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help=(
            "Output directory (must be under outputs/predictions/PAPER/). "
            "Created if absent."
        ),
    )
    parser.add_argument(
        "--policies",
        default=_DEFAULT_POLICIES,
        help=f"Comma-separated policy list (default: {_DEFAULT_POLICIES})",
    )
    parser.add_argument(
        "--paper-only",
        action="store_true",
        default=True,
        help="Enforce paper_only gate (default: True, cannot be disabled).",
    )
    return parser.parse_args(argv)


def _validate_output_dir(output_dir: str) -> Path:
    """Refuse if output is outside the PAPER prediction zone."""
    path = Path(output_dir)
    abs_path = path.resolve()
    # Relative check: look for prefix in resolved string
    rel_check = path.as_posix()
    if _ALLOWED_OUTPUT_PREFIX not in rel_check and _ALLOWED_OUTPUT_PREFIX not in abs_path.as_posix():
        _refuse(
            f"Output path must be under '{_ALLOWED_OUTPUT_PREFIX}'. "
            f"Got: {output_dir}"
        )
    return path


def _load_p13_oof(p13_dir: Path) -> tuple[Path, float]:
    """
    Validate P13 OOF directory and return (csv_path, source_bss_oof).
    Refuses if gate_decision != PASS.
    """
    csv_path = p13_dir / _OOF_CSV_FILENAME
    report_path = p13_dir / _OOF_REPORT_FILENAME

    if not csv_path.exists():
        _refuse(f"OOF predictions CSV not found: {csv_path}")
    if not report_path.exists():
        _refuse(f"OOF report JSON not found: {report_path}")

    with report_path.open(encoding="utf-8") as f:
        report = json.load(f)

    gate = report.get("gate_decision", "UNKNOWN")
    if gate != "PASS":
        _refuse(
            f"P13 gate_decision is '{gate}', expected 'PASS'. "
            "Refusing to activate simulation spine on non-passing model."
        )

    bss = float(report.get("bss_oof", 0.0))
    if bss <= 0:
        _refuse(
            f"P13 bss_oof = {bss:.6f} is not positive. Refusing spine activation."
        )

    print(f"[P14] P13 gate_decision : PASS", file=sys.stderr)
    print(f"[P14] P13 bss_oof       : {bss:.6f}", file=sys.stderr)
    return csv_path, bss


def _parse_policies(policies_str: str) -> list[str]:
    """Parse comma-separated policy names and validate."""
    parts = [p.strip() for p in policies_str.split(",") if p.strip()]
    invalid = [p for p in parts if p not in _VALID_POLICIES]
    if invalid:
        _refuse(
            f"Invalid policy names: {invalid}. "
            f"Valid policies: {sorted(_VALID_POLICIES)}"
        )
    return parts


def _write_summary_json(summary: SimulationSummary, output_dir: Path) -> Path:
    path = output_dir / "simulation_summary.json"
    data = summary.to_summary_dict()
    # Add generated_at only at write time (not in core deterministic metrics)
    data["generated_at_utc"] = summary.generated_at_utc.isoformat()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"[P14] Written: {path}", file=sys.stderr)
    return path


def _write_summary_md(summary: SimulationSummary, output_dir: Path) -> Path:
    data = summary.to_summary_dict()
    path = output_dir / "simulation_summary.md"

    lines: list[str] = [
        "# P14 Strategy Simulation Spine Activation Report\n",
        f"**Generated:** {summary.generated_at_utc.isoformat()}  \n",
        f"**Spine Gate:** `{data['spine_gate']}`  \n",
        f"**Source Model:** `{data['source_model']}`  \n",
        f"**Source BSS OOF:** `{data['source_bss_oof']:.6f}`  \n",
        f"**N Samples:** `{data['n_samples']}`  \n",
        f"**Market Odds Available:** `{data['market_odds_available']}`  \n",
        f"**paper_only:** `{data['paper_only']}`  \n",
        f"**production_ready:** `{data['production_ready']}`  \n",
        f"\n> {data['p14_note']}\n",
        "\n## Per-Policy Results\n",
        "| Policy | Gate | Bets | Skipped | Avg p_model | Brier | BSS | ECE | ROI% |",
        "|--------|------|------|---------|-------------|-------|-----|-----|------|",
    ]

    for pname in data["policies_run"]:
        p = data["per_policy"].get(pname, {})
        avg_p = f"{p['avg_model_prob']:.4f}" if p.get("avg_model_prob") is not None else "N/A"
        brier = f"{p['brier_model']:.5f}" if p.get("brier_model") is not None else "N/A"
        bss = f"{p['brier_skill_score']:.5f}" if p.get("brier_skill_score") is not None else "N/A"
        ece = f"{p['ece']:.5f}" if p.get("ece") is not None else "N/A"
        roi = f"{p['roi_pct']:.2f}%" if p.get("roi_pct") is not None else "N/A"
        lines.append(
            f"| {pname} | {p.get('gate_status', '?')} | {p.get('bet_count', 0)} "
            f"| {p.get('skipped_count', 0)} | {avg_p} | {brier} | {bss} | {ece} | {roi} |"
        )

    lines.append("\n## Gate Reasons\n")
    for pname in data["policies_run"]:
        p = data["per_policy"].get(pname, {})
        reasons = "; ".join(p.get("gate_reasons", []))
        lines.append(f"- **{pname}**: {reasons}")

    lines.append(
        "\n\n---\n"
        "> P14_STRATEGY_SIMULATION_SPINE_READY\n"
    )

    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    print(f"[P14] Written: {path}", file=sys.stderr)
    return path


def _write_ledger_csv(summary: SimulationSummary, output_dir: Path) -> Path:
    path = output_dir / "simulation_ledger.csv"
    rows = summary.ledger_rows()
    if not rows:
        path.write_text("", encoding="utf-8")
        print(f"[P14] Written (empty): {path}", file=sys.stderr)
        return path

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[P14] Written: {path} ({len(rows)} rows)", file=sys.stderr)
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Hard gate: paper_only cannot be disabled
    if not _PAPER_ONLY:
        _refuse("PAPER_ONLY gate has been tampered with. Refusing execution.")

    print(f"[P14] paper_only        : {_PAPER_ONLY}", file=sys.stderr)
    print(f"[P14] production_ready  : False", file=sys.stderr)

    # Validate output dir
    output_dir = _validate_output_dir(args.output_dir)

    # Load and validate P13 OOF
    p13_dir = Path(args.p13_oof_dir)
    if not p13_dir.exists():
        _refuse(f"P13 OOF directory not found: {p13_dir}")

    oof_csv_path, source_bss_oof = _load_p13_oof(p13_dir)

    # Parse policies
    policies = _parse_policies(args.policies)
    print(f"[P14] Policies          : {policies}", file=sys.stderr)
    print(f"[P14] OOF CSV           : {oof_csv_path}", file=sys.stderr)
    print(f"[P14] Output dir        : {output_dir}", file=sys.stderr)

    # Build runner
    runner = P13StrategySimulationRunner.from_oof_csv(
        oof_csv_path=oof_csv_path,
        source_bss_oof=source_bss_oof,
        source_model="p13_walk_forward_logistic",
        paper_only=True,
    )

    # Run simulation
    summary = runner.run(policies=policies)

    print(f"\n[P14] Spine gate        : {summary.spine_gate}", file=sys.stderr)
    print(f"[P14] Market odds       : {summary.market_odds_available}", file=sys.stderr)
    print(f"[P14] N samples         : {summary.n_samples}", file=sys.stderr)
    for p in policies:
        res = summary.policy_results.get(p)
        if res:
            print(
                f"[P14] policy={p:<20} bets={res.bet_count:<6} "
                f"skips={res.skipped_count:<6} gate={res.gate_status}",
                file=sys.stderr,
            )

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_summary_json(summary, output_dir)
    _write_summary_md(summary, output_dir)
    _write_ledger_csv(summary, output_dir)

    print("\n[P14] Done. production_ready=False, paper_only=True", file=sys.stderr)

    # Machine-readable summary line for CI parsing
    print(
        f"spine_gate={summary.spine_gate} "
        f"n_samples={summary.n_samples} "
        f"source_bss_oof={source_bss_oof:.6f} "
        f"paper_only=True"
    )


if __name__ == "__main__":
    main()
