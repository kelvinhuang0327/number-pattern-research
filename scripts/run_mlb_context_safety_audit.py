"""
scripts/run_mlb_context_safety_audit.py

P12: Context safety audit CLI.

Discovers context files under specified roots, audits each for postgame
leakage risk vs pregame safety, and writes a report.

Usage:
    .venv/bin/python scripts/run_mlb_context_safety_audit.py \\
        --root data \\
        --root outputs \\
        --root reports \\
        --output-dir outputs/predictions/PAPER/2026-05-11/context_safety

Outputs:
  - context_safety_audit.json     (per-file detail)
  - context_safety_summary.md     (human-readable summary)

Security:
  - Output dir must be under outputs/predictions/PAPER/.
  - No production writes.
  - No live data access.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wbc_backend.prediction.mlb_context_safety_audit import (
    audit_context_safety,
    summarize_context_safety,
)

_PAPER_ZONE = "outputs/predictions/PAPER"
_TODAY = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _refuse(reason: str) -> None:
    print(f"[REFUSED] {reason}", file=sys.stderr)
    sys.exit(2)


def _assert_paper_output_dir(path: Path) -> None:
    resolved = path.resolve()
    if _PAPER_ZONE not in resolved.as_posix():
        _refuse(f"Output dir must be under '{_PAPER_ZONE}'. Got: {resolved}")


def _write_json(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_summary_md(summary: dict, audit: dict, output_dir: Path) -> Path:
    path = output_dir / "context_safety_summary.md"
    files = audit.get("files", [])
    lines = [
        "# P12 Context Safety Audit Summary",
        "",
        f"Generated: {datetime.now(tz=timezone.utc).isoformat()}",
        "",
        "## Overall Statistics",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total files audited | {summary['total_files']} |",
        f"| PREGAME_SAFE | {summary['pregame_safe_count']} |",
        f"| POSTGAME_RISK | {summary['postgame_risk_count']} |",
        f"| UNKNOWN | {summary['unknown_count']} |",
        f"| Usable (safe) | {summary['usable_file_count']} |",
        f"| Unsafe | {summary['unsafe_file_count']} |",
        "",
        "## Safety Recommendation",
        "",
        summary["safety_recommendation"],
        "",
        "## Per-File Audit",
        "",
        "| File | Type | Rows | Status | Reasons |",
        "|------|------|------|--------|---------|",
    ]
    for fa in sorted(files, key=lambda x: x.get("safety_status", ""), reverse=True):
        fname = Path(fa["file_path"]).name
        ftype = fa.get("detected_context_type", "?")
        rows = fa.get("row_count", "?")
        status = fa.get("safety_status", "?")
        reasons = "; ".join(fa.get("safety_reasons", []))[:120]
        lines.append(f"| {fname} | {ftype} | {rows} | {status} | {reasons} |")

    lines += [
        "",
        "## Risk Files (detail)",
        "",
    ]
    risk_files = [f for f in files if f.get("safety_status") == "POSTGAME_RISK"]
    if risk_files:
        for fa in risk_files:
            lines += [
                f"### {Path(fa['file_path']).name}",
                "",
                f"- Path: `{fa['file_path']}`",
                f"- Rows: {fa.get('row_count')}",
                f"- Outcome columns: {fa.get('outcome_columns', [])}",
                f"- Postgame keyword hits: {fa.get('postgame_keyword_hits', [])}",
                f"- Reasons: {fa.get('safety_reasons', [])}",
                "",
            ]
    else:
        lines.append("No POSTGAME_RISK files found.")

    lines += [
        "",
        "---",
        "paper_only: true",
        "production_enablement_attempted: false",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="P12 context safety audit")
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=[],
        help="Root directory to scan (repeatable)",
    )
    parser.add_argument(
        "--output-dir",
        default=f"outputs/predictions/PAPER/{_TODAY}/context_safety",
    )
    parser.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args()

    roots = args.roots if args.roots else ["data"]
    output_dir = Path(args.output_dir)

    _assert_paper_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[P12] Context safety audit")
    print(f"[P12] Scanning roots: {roots}")
    print(f"[P12] Output dir: {output_dir}")

    audit = audit_context_safety(
        roots=[Path(r) for r in roots],
        sample_size=args.sample_size,
    )
    summary = summarize_context_safety(audit)

    # Write audit JSON
    audit_path = output_dir / "context_safety_audit.json"
    _write_json(audit, audit_path)
    print(f"[P12] Wrote {audit_path.name} ({audit['total_files']} files)")

    # Write summary markdown
    summary_path = _write_summary_md(summary, audit, output_dir)
    print(f"[P12] Wrote {summary_path.name}")

    # Print summary
    print("\n" + "=" * 60)
    print("P12 CONTEXT SAFETY SUMMARY")
    print("=" * 60)
    print(f"Total files audited : {summary['total_files']}")
    print(f"PREGAME_SAFE        : {summary['pregame_safe_count']}")
    print(f"POSTGAME_RISK       : {summary['postgame_risk_count']}")
    print(f"UNKNOWN             : {summary['unknown_count']}")
    print(f"Usable files        : {summary['usable_file_count']}")
    print(f"\nRecommendation: {summary['safety_recommendation'][:200]}")

    if summary.get("risk_files"):
        print(f"\nRisk files:")
        for f in summary["risk_files"]:
            print(f"  ⚠ {f}")

    print(f"\n[P12] Artifacts: {output_dir}")
    print("[P12] paper_only=True | production_enabled=False")


if __name__ == "__main__":
    main()
