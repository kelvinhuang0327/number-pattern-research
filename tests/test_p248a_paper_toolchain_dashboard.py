"""P248-A result-only paper toolchain static dashboard tests."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_toolchain_dashboard as dashboard


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_dashboard.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "dashboard_summary.json",
    "dashboard_sections.csv",
    "dashboard.html",
)
SOURCE_ARTIFACTS = (
    dashboard.DEFAULT_TOOLCHAIN_STATUS_JSON,
    dashboard.DEFAULT_TOOLCHAIN_STEPS_CSV,
    dashboard.DEFAULT_TOOLCHAIN_REPORT_MD,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_dashboard(output_dir: Path) -> dashboard.PaperToolchainDashboardResult:
    return dashboard.build_paper_toolchain_dashboard(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )


def test_default_dashboard_reads_committed_p247_artifacts_and_writes_outputs(tmp_path):
    output_dir = tmp_path / "dashboard"

    result = _run_dashboard(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "dashboard_summary.json")
    rows = _csv(output_dir / "dashboard_sections.csv")
    assert len(rows) == 10
    assert list(rows[0]) == dashboard.SECTION_CSV_FIELDNAMES
    html = (output_dir / "dashboard.html").read_text(encoding="utf-8")
    for section in (
        "Summary",
        "Latest Gate",
        "Toolchain Steps",
        "Artifact Roots",
        "Scripts",
        "Hashes",
        "Warnings / Failures",
        "Safety Boundaries",
        "Limitations",
        "Not Claims",
    ):
        assert section in html


def test_default_dashboard_returns_pass_over_current_committed_p247_status(tmp_path):
    payload = _run_dashboard(tmp_path / "dashboard").summary

    assert payload["dashboard_status"] == "PASS"
    assert payload["toolchain_status"] == "PASS"
    assert payload["artifact_roots_present"] == 12
    assert payload["artifact_roots_total"] == 12
    assert payload["scripts_present"] == 10
    assert payload["scripts_total"] == 10
    assert payload["latest_gate_status"] == "PASS"
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []


def test_dashboard_html_is_self_contained_without_network_assets(tmp_path):
    html = (tmp_path / "dashboard" / "dashboard.html")
    _run_dashboard(tmp_path / "dashboard")
    text = html.read_text(encoding="utf-8")

    assert "<script" not in text.lower()
    assert not re.search(r"<link\b", text, flags=re.IGNORECASE)
    assert not re.search(r"<img\b", text, flags=re.IGNORECASE)
    assert not re.search(r"@import\b", text, flags=re.IGNORECASE)
    assert not re.search(r"https?://|//[^\\s'\"]+", text)


def test_latest_p246_gate_and_counts_are_rendered(tmp_path):
    output_dir = tmp_path / "dashboard"
    payload = _run_dashboard(output_dir).summary
    html = (output_dir / "dashboard.html").read_text(encoding="utf-8")

    assert payload["latest_gate_status"] == "PASS"
    assert "P246 gate status" in html
    assert ">PASS<" in html
    assert "&quot;passed&quot;:9" in html


def test_artifact_root_and_script_counts_are_rendered(tmp_path):
    output_dir = tmp_path / "dashboard"
    _run_dashboard(output_dir)
    html = (output_dir / "dashboard.html").read_text(encoding="utf-8")
    sections = _csv(output_dir / "dashboard_sections.csv")

    assert "12 / 12" in html
    assert "10 / 10" in html
    assert any(row["section_id"] == "artifact_roots" and row["item_count"] == "12" for row in sections)
    assert any(row["section_id"] == "scripts" and row["item_count"] == "10" for row in sections)


def test_missing_or_corrupt_p247_input_fails_clearly(tmp_path):
    with pytest.raises(dashboard.PaperToolchainDashboardError, match="MISSING_INPUT"):
        dashboard.build_paper_toolchain_dashboard(
            toolchain_status_json=tmp_path / "missing.json",
            output_dir=tmp_path / "dashboard",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(dashboard.PaperToolchainDashboardError, match="CORRUPT_INPUT"):
        dashboard.build_paper_toolchain_dashboard(
            toolchain_status_json=corrupt_json,
            output_dir=tmp_path / "dashboard",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("step_id,status\nP246,PASS\n", encoding="utf-8")
    with pytest.raises(dashboard.PaperToolchainDashboardError, match="missing required columns"):
        dashboard.build_paper_toolchain_dashboard(
            toolchain_steps_csv=corrupt_csv,
            output_dir=tmp_path / "dashboard",
            generated_at_utc=FIXED_TIME,
        )


def test_output_json_csv_and_html_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "dashboard"

    first = _run_dashboard(output_dir)
    assert first.summary["dashboard_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_dashboard(output_dir)
    assert second.summary["dashboard_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_dashboard_does_not_mutate_p237_to_p247_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in SOURCE_ARTIFACTS}

    result = _run_dashboard(tmp_path / "dashboard")

    assert result.summary["dashboard_status"] == "PASS"
    assert before == {path: _digest(path) for path in before}


def test_cli_builds_dashboard_outputs_and_reports_bad_input(tmp_path):
    output_dir = tmp_path / "dashboard"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert _json(output_dir / "dashboard_summary.json")["dashboard_status"] == "PASS"

    missing = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--toolchain-status-json",
            str(tmp_path / "missing.json"),
            "--output-dir",
            str(tmp_path / "failed"),
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert missing.returncode == 2
    assert "MISSING_INPUT" in missing.stderr
