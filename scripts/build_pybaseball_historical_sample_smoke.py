#!/usr/bin/env python3
"""Build the P214-A pybaseball historical sample smoke artifacts."""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
OUT_MD = REPORT_DIR / "p214a_pybaseball_historical_sample_smoke.md"
OUT_JSON = REPORT_DIR / "p214a_pybaseball_historical_sample_smoke.json"
OUT_CSV = REPORT_DIR / "p214a_pybaseball_historical_sample_smoke.csv"
REEXEC_GUARD = "P214A_PYBASEBALL_VENV_REEXEC"
SUCCESS_BANNER = "P214-A PYBASEBALL HISTORICAL SAMPLE SMOKE PASS"
FAILURE_BANNER = "P214-A PYBASEBALL HISTORICAL SAMPLE SMOKE FAIL"


def _maybe_reexec_into_venv() -> None:
    if importlib.util.find_spec("pybaseball") is not None:
        return
    if os.environ.get(REEXEC_GUARD) == "1":
        return

    venv_python = ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return

    env = os.environ.copy()
    env[REEXEC_GUARD] = "1"
    env.setdefault("PYTHONPATH", str(ROOT))
    completed = subprocess.run(
        [str(venv_python), str(Path(__file__).resolve())],
        cwd=ROOT,
        env=env,
        text=False,
        check=False,
    )
    raise SystemExit(completed.returncode)


_maybe_reexec_into_venv()

from wbc_backend.recommendation.pybaseball_historical_sample_adapter import (  # noqa: E402
    DISCLAIMER,
    build_historical_sample_payload as build_payload,
)


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_md_cell(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(payload: dict[str, Any]) -> str:
    request = payload["request"]
    summary = payload["result_summary"]
    lines = [
        "# P214-A pybaseball Historical Sample Smoke",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Source library: {payload['source_library']} {payload['source_version'] or '(version unavailable)'}",
        f"- Source function: {payload['source_function']}",
        f"- Fixed request: {request['start_date']}..{request['end_date']} team={request['team']}",
        f"- Fetched row count: {summary['fetched_row_count']}",
        f"- Snapshot row count: {summary['snapshot_row_count']}",
        f"- Snapshot columns: {', '.join(summary['snapshot_columns'])}",
        "",
        "## Observed Date Range",
        "",
        f"- Start: {summary['observed_date_range']['start']}",
        f"- End: {summary['observed_date_range']['end']}",
        "",
        "## Guardrails",
        "",
    ]
    for guardrail in payload["guardrails"]:
        lines.append(f"- {guardrail}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for limitation in payload["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "",
            "## Snapshot",
            "",
            "| " + " | ".join(summary["snapshot_columns"]) + " |",
            "| " + " | ".join("---" for _ in summary["snapshot_columns"]) + " |",
        ]
    )
    for record in payload["records"]:
        lines.append(
            "| " + " | ".join(_md_cell(record[column]) for column in summary["snapshot_columns"]) + " |"
        )
    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    summary = payload["result_summary"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=summary["snapshot_columns"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(payload["records"])


def main() -> int:
    try:
        payload = build_payload()
        write_outputs(payload)
    except Exception as exc:
        print(f"{FAILURE_BANNER}: {exc}")
        return 1

    print(SUCCESS_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
