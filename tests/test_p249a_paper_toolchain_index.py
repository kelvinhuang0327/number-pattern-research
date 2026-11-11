"""P249-A result-only paper toolchain launch/index tests."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_toolchain_index as index


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_index.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "index_summary.json",
    "index_links.csv",
    "index.html",
)
SOURCE_ARTIFACTS = (
    index.DEFAULT_DASHBOARD_SUMMARY_JSON,
    index.DEFAULT_DASHBOARD_SECTIONS_CSV,
    index.DEFAULT_DASHBOARD_HTML,
    index.DEFAULT_TOOLCHAIN_STATUS_JSON,
    index.DEFAULT_GATE_SUMMARY_JSON,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _run_index(output_dir: Path) -> index.PaperToolchainIndexResult:
    return index.build_paper_toolchain_index(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )


def test_default_index_reads_committed_p246_to_p248_artifacts_and_writes_outputs(tmp_path):
    output_dir = tmp_path / "index"

    result = _run_index(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "index_summary.json")
    rows = _csv(output_dir / "index_links.csv")
    assert len(rows) == len(index.DEFAULT_LINK_SPECS)
    assert list(rows[0]) == index.LINK_CSV_FIELDNAMES
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    for section in (
        "Summary",
        "Launch Links",
        "Dashboard",
        "Latest Gate",
        "Toolchain Status",
        "Catalog / Query / Diff",
        "Scripts",
        "Safety Boundaries",
        "Limitations",
        "Not Claims",
    ):
        assert section in html


def test_default_index_returns_pass_over_current_committed_chain(tmp_path):
    payload = _run_index(tmp_path / "index").summary

    assert payload["index_status"] == "PASS"
    assert payload["dashboard_status"] == "PASS"
    assert payload["toolchain_status"] == "PASS"
    assert payload["latest_gate_status"] == "PASS"
    assert payload["local_link_count"] == payload["link_count"]
    assert payload["missing_link_count"] == 0
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []


def test_index_summary_has_required_contract_fields(tmp_path):
    payload = _run_index(tmp_path / "index").summary

    for key in (
        "generated_at_utc",
        "index_status",
        "input_paths",
        "input_hashes",
        "dashboard_status",
        "toolchain_status",
        "latest_gate_status",
        "link_count",
        "local_link_count",
        "missing_link_count",
        "warning_count",
        "failure_count",
        "output_files",
        "limitation_labels",
        "no_side_effects",
        "warnings",
        "failures",
    ):
        assert key in payload
    for label in index.REQUIRED_LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["executed_existing_workflows"] is False
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False
    assert payload["no_side_effects"]["created_betting_recommendations"] is False


def test_index_links_include_dashboard_catalog_query_diff_and_p239_to_p248_references(tmp_path):
    rows = _csv((_run_index(tmp_path / "index"), tmp_path / "index" / "index_links.csv")[1])
    link_ids = {row["link_id"] for row in rows}

    assert "p248_dashboard_html" in link_ids
    assert {"p243_catalog_json", "p244_query_results", "p245_diff_entries"} <= link_ids
    for step in range(239, 249):
        assert f"p{step}_script" in link_ids
    assert all(row["target_exists"] == "True" for row in rows)
    assert all(not re.search(r"https?://|//[^\\s'\"]+", row["relative_path"]) for row in rows)


def test_index_html_is_self_contained_without_network_assets(tmp_path):
    output_dir = tmp_path / "index"
    _run_index(output_dir)
    text = (output_dir / "index.html").read_text(encoding="utf-8")

    assert "<script" not in text.lower()
    assert not re.search(r"<link\b", text, flags=re.IGNORECASE)
    assert not re.search(r"<img\b", text, flags=re.IGNORECASE)
    assert not re.search(r"@import\b", text, flags=re.IGNORECASE)
    assert not re.search(r"https?://|//[^\\s'\"]+", text)


def test_missing_or_corrupt_inputs_fail_clearly(tmp_path):
    with pytest.raises(index.PaperToolchainIndexError, match="MISSING_INPUT"):
        index.build_paper_toolchain_index(
            dashboard_summary_json=tmp_path / "missing.json",
            output_dir=tmp_path / "index",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(index.PaperToolchainIndexError, match="CORRUPT_INPUT"):
        index.build_paper_toolchain_index(
            dashboard_summary_json=corrupt_json,
            output_dir=tmp_path / "index",
            generated_at_utc=FIXED_TIME,
        )

    corrupt_csv = tmp_path / "corrupt.csv"
    corrupt_csv.write_text("section_id,status\nsummary,PASS\n", encoding="utf-8")
    with pytest.raises(index.PaperToolchainIndexError, match="missing required columns"):
        index.build_paper_toolchain_index(
            dashboard_sections_csv=corrupt_csv,
            output_dir=tmp_path / "index",
            generated_at_utc=FIXED_TIME,
        )


def test_missing_configured_link_fails_unless_optional(tmp_path):
    required_link = (
        index.LinkSpec("missing_required", "Missing required", "launch", "report/nope/missing.json"),
    )
    required = index.build_paper_toolchain_index(
        output_dir=tmp_path / "required",
        generated_at_utc=FIXED_TIME,
        link_specs=required_link,
    )
    assert required.summary["index_status"] == "FAIL"
    assert required.summary["missing_link_count"] == 1
    assert any("MISSING_LINK" in failure for failure in required.summary["failures"])

    optional_link = (
        index.LinkSpec(
            "missing_optional",
            "Missing optional",
            "launch",
            "report/nope/missing.json",
            optional=True,
        ),
    )
    optional = index.build_paper_toolchain_index(
        output_dir=tmp_path / "optional",
        generated_at_utc=FIXED_TIME,
        link_specs=optional_link,
    )
    assert optional.summary["index_status"] == "PASS"
    assert optional.summary["missing_link_count"] == 0


def test_output_json_csv_and_html_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "index"

    first = _run_index(output_dir)
    assert first.summary["index_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_index(output_dir)
    assert second.summary["index_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_index_does_not_mutate_p246_to_p248_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in SOURCE_ARTIFACTS}

    result = _run_index(tmp_path / "index")

    assert result.summary["index_status"] == "PASS"
    assert before == {path: _digest(path) for path in before}


def test_cli_builds_index_outputs_and_reports_bad_input(tmp_path):
    output_dir = tmp_path / "index"

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
    assert _json(output_dir / "index_summary.json")["index_status"] == "PASS"

    missing = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dashboard-summary-json",
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
