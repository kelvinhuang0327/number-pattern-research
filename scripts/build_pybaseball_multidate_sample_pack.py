#!/usr/bin/env python3
"""Build the P216-A pybaseball multi-date historical sample pack artifacts."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
OUT_MD = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.md"
OUT_JSON = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.json"
OUT_CSV = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.csv"
REEXEC_GUARD = "P216A_PYBASEBALL_VENV_REEXEC"
SUCCESS_BANNER = "P216-A PYBASEBALL MULTI-DATE SAMPLE PACK PASS"
FAILURE_BANNER = "P216-A PYBASEBALL MULTI-DATE SAMPLE PACK FAIL"


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

from wbc_backend.recommendation.pybaseball_multidate_sample_adapter import (  # noqa: E402
    DISCLAIMER,
    build_multidate_sample_payload as build_payload,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_md_cell(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(payload: dict[str, Any], *, artifact_hashes: dict[str, str]) -> str:
    request = payload["source_request"]
    limits = payload["sample_size_limits"]
    lines = [
        "# P216-A pybaseball Multi-Date Historical Sample Pack",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Source library: {payload['source_library']} {payload['source_version'] or '(version unavailable)'}",
        f"- Source function: {payload['source_function']}",
        f"- Requested date range: {request['start_date']}..{request['end_date']}",
        f"- Team filter: {request['team']}",
        f"- Row count: {payload['row_count']}",
        f"- Column count: {payload['column_count']}",
        f"- Fetched row count: {payload['fetched_row_count']}",
        f"- Fetched column count: {payload['fetched_column_count']}",
        "",
        "## Sample Size Limits",
        "",
        f"- Per-date row limit: {limits['per_date_row_limit']}",
        f"- Total row limit: {limits['total_row_limit']}",
        f"- Preview row limit: {limits['preview_row_limit']}",
        f"- Requested date count: {limits['requested_date_count']}",
        "",
        "## Observed Dates",
        "",
        f"- Observed dates: {', '.join(payload['observed_dates'])}",
        "",
        "## Artifact Hashes",
        "",
        f"- CSV SHA256: {artifact_hashes[_artifact_label(OUT_CSV)]}",
        "",
        "## Guardrails",
        "",
    ]
    for guardrail in payload["guardrails"]:
        lines.append(f"- {guardrail}")
    lines.extend(["", "## Limitations", ""])
    for limitation in payload["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(["", "## Prohibited Claims", ""])
    for item in payload["prohibited_claims"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Sample Pack",
            "",
            "| " + " | ".join(payload["columns"]) + " |",
            "| " + " | ".join("---" for _ in payload["columns"]) + " |",
        ]
    )
    for record in payload["records"]:
        lines.append(
            "| " + " | ".join(_md_cell(record[column]) for column in payload["columns"]) + " |"
        )
    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def _write_csv(payload: dict[str, Any]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=payload["columns"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(payload["records"])


def _write_json(payload: dict[str, Any], *, artifact_hashes: dict[str, str]) -> None:
    output_payload = dict(payload)
    output_payload["artifact_hashes"] = artifact_hashes
    output_payload["artifact_hash_notes"] = (
        "Artifact hashes cover companion outputs only; the JSON self-hash is validated externally to avoid self-reference."
    )
    OUT_JSON.write_text(json.dumps(output_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(payload)
    csv_relpath = _artifact_label(OUT_CSV)
    md_relpath = _artifact_label(OUT_MD)
    json_relpath = _artifact_label(OUT_JSON)
    artifact_hashes_for_md = {
        csv_relpath: _sha256(OUT_CSV),
    }
    OUT_MD.write_text(
        render_markdown(payload, artifact_hashes=artifact_hashes_for_md) + "\n",
        encoding="utf-8",
    )
    artifact_hashes_for_json = {
        csv_relpath: artifact_hashes_for_md[csv_relpath],
        md_relpath: _sha256(OUT_MD),
    }
    _write_json(payload, artifact_hashes=artifact_hashes_for_json)


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
