"""P251-A result-only paper toolchain operator quickstart exporter tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_toolchain_quickstart as quickstart


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_quickstart.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "quickstart_summary.json",
    "quickstart_commands.csv",
    "quickstart.md",
)
SOURCE_ROOTS = (
    ROOT / "report" / "p237a_paper_strategy_simulator_summary.json",
    ROOT / "report" / "p237a_paper_strategy_decisions.csv",
    ROOT / "report" / "p238a_paper_strategy_learning_summary.json",
    ROOT / "report" / "p238a_paper_strategy_learning_segments.csv",
    ROOT / "report" / "p239a_paper_strategy_workflow",
    ROOT / "report" / "p240a_paper_strategy_workflow_inspector",
    ROOT / "report" / "p241a_paper_strategy_workflow_review_pack",
    ROOT / "report" / "p242a_paper_strategy_workflow_bundle",
    ROOT / "report" / "p243a_paper_artifact_catalog",
    ROOT / "report" / "p244a_paper_artifact_catalog_query",
    ROOT / "report" / "p245a_paper_artifact_catalog_diff",
    ROOT / "report" / "p246a_paper_artifact_diff_gate",
    ROOT / "report" / "p247a_paper_toolchain_status",
    ROOT / "report" / "p248a_paper_toolchain_dashboard",
    ROOT / "report" / "p249a_paper_toolchain_index",
    ROOT / "report" / "p250a_paper_toolchain_cli_help",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    for spec_path in (
        quickstart.DEFAULT_INDEX_SUMMARY_JSON,
        quickstart.DEFAULT_INDEX_LINKS_CSV,
        quickstart.DEFAULT_CLI_HELP_SUMMARY_JSON,
        quickstart.DEFAULT_CLI_HELP_ENTRIES_CSV,
    ):
        if spec_path.is_file():
            files.append(spec_path)
    return sorted(set(files))


def _run_quickstart(output_dir: Path, **kwargs) -> quickstart.PaperToolchainQuickstartResult:
    return quickstart.build_paper_toolchain_quickstart(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def _write_synthetic_fixture(base: Path) -> dict[str, Path]:
    index_summary_path = base / "index_summary.json"
    index_links_path = base / "index_links.csv"
    cli_help_summary_path = base / "cli_help_summary.json"
    cli_help_entries_path = base / "cli_help_entries.csv"

    index_summary_path.write_text(
        json.dumps(
            {
                "index_status": "PASS",
                "dashboard_status": "PASS",
                "toolchain_status": "PASS",
                "latest_gate_status": "PASS",
                "output_files": {},
            }
        ),
        encoding="utf-8",
    )
    with index_links_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["link_id", "title", "category", "relative_path", "target_exists", "target_type", "sha256", "notes"]
        )
        writer.writerow(
            ["missing_link", "Missing Link", "viewing", "missing_file.json", "False", "file", "", ""]
        )

    cli_help_summary_path.write_text(
        json.dumps({"smoke_status": "PASS", "python_executable": sys.executable}),
        encoding="utf-8",
    )
    with cli_help_entries_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "script_id",
                "step_id",
                "script_path",
                "script_present",
                "help_exit_code",
                "timed_out",
                "help_sha256",
                "help_line_count",
                "has_usage",
                "has_quiet",
                "has_output_dir",
                "status",
                "notes",
            ]
        )
        writer.writerow(
            [
                "missing_script",
                "PX",
                "scripts/does_not_exist.py",
                "False",
                "",
                "False",
                "",
                "0",
                "False",
                "False",
                "False",
                "FAIL",
                "script not found",
            ]
        )

    return {
        "index_summary_json": index_summary_path,
        "index_links_csv": index_links_path,
        "cli_help_summary_json": cli_help_summary_path,
        "cli_help_entries_csv": cli_help_entries_path,
    }


def test_default_quickstart_produces_json_csv_and_markdown_outputs(tmp_path):
    output_dir = tmp_path / "quickstart"

    result = _run_quickstart(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "quickstart_summary.json")
    rows = _csv(output_dir / "quickstart_commands.csv")
    assert len(rows) == len(result.command_rows)
    assert list(rows[0]) == quickstart.COMMAND_CSV_FIELDNAMES
    markdown = (output_dir / "quickstart.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Start Here",
        "## Safe Viewing Links",
        "## Safe Help Commands",
        "## What Not To Run",
        "## Current Status Snapshot",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_quickstart_returns_pass_over_current_committed_artifacts(tmp_path):
    payload = _run_quickstart(tmp_path / "quickstart").summary

    assert payload["quickstart_status"] == "PASS"
    assert payload["index_status"] == "PASS"
    assert payload["dashboard_status"] == "PASS"
    assert payload["toolchain_status"] == "PASS"
    assert payload["latest_gate_status"] == "PASS"
    assert payload["cli_help_smoke_status"] == "PASS"
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []
    assert payload["local_link_count"] > 0
    assert payload["help_command_count"] > 0
    assert payload["command_count"] == payload["local_link_count"] + payload["help_command_count"]
    for label in quickstart.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["read_existing_p249_and_p250_artifacts_only"] is True
    assert payload["no_side_effects"]["executed_help_calls"] is False
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False
    assert payload["no_side_effects"]["created_betting_recommendations_or_rankings"] is False
    assert payload["no_side_effects"]["created_live_production_or_real_betting_output"] is False


def test_generated_commands_are_only_safe_help_or_viewing_references(tmp_path):
    result = _run_quickstart(tmp_path / "quickstart")

    assert result.command_rows
    for row in result.command_rows:
        text = row["command_text"]
        if row["category"] == "help":
            assert text.rstrip().endswith("--help")
            assert row["references_path"] in text
        else:
            assert text.startswith("view: ")


def test_no_generated_command_executes_workflows_or_writes_outputs(tmp_path):
    result = _run_quickstart(tmp_path / "quickstart")

    assert result.command_rows
    for row in result.command_rows:
        assert row["executes_workflow"] is False
        assert row["writes_outputs"] is False


def test_no_generated_command_contains_forbidden_tokens(tmp_path):
    result = _run_quickstart(tmp_path / "quickstart")

    forbidden = (
        "provider",
        "API",
        "pybaseball",
        "DB",
        "ROI",
        "EV",
        "Kelly",
        "live",
        "production",
        "real betting",
        "recommended_bet",
    )
    for row in result.command_rows:
        text = row["command_text"]
        for token in forbidden:
            assert token not in text, f"forbidden token {token!r} found in {text!r}"


def test_missing_index_summary_json_fails_clearly(tmp_path):
    with pytest.raises(quickstart.PaperToolchainQuickstartError, match="not found"):
        quickstart.build_paper_toolchain_quickstart(
            index_summary_json=tmp_path / "does_not_exist.json",
            index_links_csv=quickstart.DEFAULT_INDEX_LINKS_CSV,
            cli_help_summary_json=quickstart.DEFAULT_CLI_HELP_SUMMARY_JSON,
            cli_help_entries_csv=quickstart.DEFAULT_CLI_HELP_ENTRIES_CSV,
            output_dir=tmp_path / "quickstart",
            generated_at_utc=FIXED_TIME,
        )


def test_corrupt_cli_help_summary_json_fails_clearly(tmp_path):
    corrupt_path = tmp_path / "cli_help_summary.json"
    corrupt_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(quickstart.PaperToolchainQuickstartError, match="not valid JSON"):
        quickstart.build_paper_toolchain_quickstart(
            index_summary_json=quickstart.DEFAULT_INDEX_SUMMARY_JSON,
            index_links_csv=quickstart.DEFAULT_INDEX_LINKS_CSV,
            cli_help_summary_json=corrupt_path,
            cli_help_entries_csv=quickstart.DEFAULT_CLI_HELP_ENTRIES_CSV,
            output_dir=tmp_path / "quickstart",
            generated_at_utc=FIXED_TIME,
        )


def test_missing_configured_link_or_help_entry_fails_in_synthetic_fixture(tmp_path):
    paths = _write_synthetic_fixture(tmp_path)

    result = quickstart.build_paper_toolchain_quickstart(
        index_summary_json=paths["index_summary_json"],
        index_links_csv=paths["index_links_csv"],
        cli_help_summary_json=paths["cli_help_summary_json"],
        cli_help_entries_csv=paths["cli_help_entries_csv"],
        output_dir=tmp_path / "quickstart",
        generated_at_utc=FIXED_TIME,
    )

    assert result.summary["quickstart_status"] == "FAIL"
    assert result.summary["failure_count"] >= 2
    joined_failures = " | ".join(result.summary["failures"])
    assert "missing_link" in joined_failures
    assert "missing_script" in joined_failures


def test_output_json_csv_and_markdown_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "quickstart"

    first = _run_quickstart(output_dir)
    assert first.summary["quickstart_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_quickstart(output_dir)
    assert second.summary["quickstart_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_quickstart_does_not_mutate_p237_to_p250_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in _source_files()}

    result = _run_quickstart(tmp_path / "quickstart")

    assert result.summary["quickstart_status"] == "PASS"
    after = {path: _digest(path) for path in _source_files()}
    assert before == after


def test_cli_builds_quickstart_outputs_and_exit_code(tmp_path):
    output_dir = tmp_path / "quickstart"

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
    assert _json(output_dir / "quickstart_summary.json")["quickstart_status"] == "PASS"


def test_cli_rejects_missing_input_with_nonzero_exit(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--index-summary-json",
            str(tmp_path / "does_not_exist.json"),
            "--output-dir",
            str(tmp_path / "quickstart"),
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "not found" in result.stderr
