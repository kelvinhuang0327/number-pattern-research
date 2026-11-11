"""P252-A result-only paper toolchain operator pack manifest exporter tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_toolchain_operator_pack as operator_pack


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_operator_pack.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "operator_pack_summary.json",
    "operator_pack_files.csv",
    "operator_pack.md",
)
REQUIRED_MINIMUM_PACK_PATHS = (
    "report/p248a_paper_toolchain_dashboard/dashboard.html",
    "report/p248a_paper_toolchain_dashboard/dashboard_summary.json",
    "report/p249a_paper_toolchain_index/index.html",
    "report/p249a_paper_toolchain_index/index_summary.json",
    "report/p250a_paper_toolchain_cli_help/cli_help_report.md",
    "report/p250a_paper_toolchain_cli_help/cli_help_summary.json",
    "report/p251a_paper_toolchain_quickstart/quickstart.md",
    "report/p251a_paper_toolchain_quickstart/quickstart_summary.json",
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
    ROOT / "report" / "p251a_paper_toolchain_quickstart",
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
    return sorted(set(files))


def _run_operator_pack(output_dir: Path, **kwargs) -> operator_pack.PaperToolchainOperatorPackResult:
    return operator_pack.build_paper_toolchain_operator_pack(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
        **kwargs,
    )


def _write_synthetic_fixture(base: Path) -> dict[str, Path]:
    dashboard_summary_path = base / "dashboard_summary.json"
    index_summary_path = base / "index_summary.json"
    index_links_path = base / "index_links.csv"
    cli_help_summary_path = base / "cli_help_summary.json"
    quickstart_summary_path = base / "quickstart_summary.json"
    quickstart_commands_path = base / "quickstart_commands.csv"
    quickstart_md_path = base / "quickstart.md"

    dashboard_summary_path.write_text(
        json.dumps({"dashboard_status": "PASS", "output_files": {}}),
        encoding="utf-8",
    )
    index_summary_path.write_text(
        json.dumps({"index_status": "PASS", "output_files": {}}),
        encoding="utf-8",
    )
    with index_links_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["link_id", "title", "category", "relative_path", "target_exists", "target_type", "sha256", "notes"]
        )
        writer.writerow(["sample_link", "Sample Link", "viewing", "sample.json", "False", "file", "", ""])

    cli_help_summary_path.write_text(json.dumps({"smoke_status": "PASS"}), encoding="utf-8")

    quickstart_summary_path.write_text(json.dumps({"quickstart_status": "PASS"}), encoding="utf-8")
    with quickstart_commands_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "command_id",
                "category",
                "title",
                "command_text",
                "references_path",
                "safety_level",
                "executes_workflow",
                "writes_outputs",
                "notes",
            ]
        )
        writer.writerow(
            [
                "sample_help",
                "help",
                "Sample --help",
                "python3 sample.py --help",
                "sample.py",
                "help_only",
                "False",
                "False",
                "",
            ]
        )
    quickstart_md_path.write_text("# Sample Quickstart\n", encoding="utf-8")

    return {
        "dashboard_summary_json": dashboard_summary_path,
        "index_summary_json": index_summary_path,
        "index_links_csv": index_links_path,
        "cli_help_summary_json": cli_help_summary_path,
        "quickstart_summary_json": quickstart_summary_path,
        "quickstart_commands_csv": quickstart_commands_path,
        "quickstart_md": quickstart_md_path,
    }


def test_default_operator_pack_produces_json_csv_and_markdown_outputs(tmp_path):
    output_dir = tmp_path / "operator_pack"

    result = _run_operator_pack(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "operator_pack_summary.json")
    rows = _csv(output_dir / "operator_pack_files.csv")
    assert len(rows) == len(result.file_rows)
    assert list(rows[0]) == operator_pack.FILE_CSV_FIELDNAMES
    markdown = (output_dir / "operator_pack.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Pack Contents",
        "## Status Snapshot",
        "## Safe Viewing Files",
        "## Safe Help / Quickstart References",
        "## Hashes",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_operator_pack_returns_pass_over_current_committed_artifacts(tmp_path):
    payload = _run_operator_pack(tmp_path / "operator_pack").summary

    assert payload["operator_pack_status"] == "PASS"
    assert payload["dashboard_status"] == "PASS"
    assert payload["index_status"] == "PASS"
    assert payload["cli_help_smoke_status"] == "PASS"
    assert payload["quickstart_status"] == "PASS"
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []
    assert payload["file_count"] > 0
    assert payload["local_link_count"] > 0
    assert payload["command_count"] > 0
    for label in operator_pack.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["read_existing_p248_p249_p250_p251_artifacts_only"] is True
    assert payload["no_side_effects"]["executed_p239_to_p251_scripts"] is False
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False
    assert payload["no_side_effects"]["created_betting_recommendations_or_rankings"] is False
    assert payload["no_side_effects"]["created_live_production_or_real_betting_output"] is False


def test_all_configured_pack_targets_exist_with_sha256_hashes(tmp_path):
    result = _run_operator_pack(tmp_path / "operator_pack")

    covered = {row["relative_path"] for row in result.file_rows}
    for required in REQUIRED_MINIMUM_PACK_PATHS:
        assert required in covered, f"missing minimum required pack path: {required}"

    for row in result.file_rows:
        assert row["target_exists"] is True
        assert isinstance(row["sha256"], str) and len(row["sha256"]) == 64


def test_operator_pack_files_csv_contains_only_repo_local_relative_paths(tmp_path):
    output_dir = tmp_path / "operator_pack"
    _run_operator_pack(output_dir)

    rows = _csv(output_dir / "operator_pack_files.csv")
    for row in rows:
        path = row["relative_path"]
        assert not path.startswith("/")
        assert "http://" not in path
        assert "https://" not in path
        assert ".." not in Path(path).parts


def test_operator_pack_markdown_contains_limitations_and_not_claims(tmp_path):
    output_dir = tmp_path / "operator_pack"
    _run_operator_pack(output_dir)

    markdown = (output_dir / "operator_pack.md").read_text(encoding="utf-8")
    for label in operator_pack.LIMITATION_LABELS:
        assert label in markdown
    for claim in operator_pack.NOT_CLAIMS:
        assert claim in markdown


def test_missing_dashboard_summary_json_fails_clearly(tmp_path):
    with pytest.raises(operator_pack.PaperToolchainOperatorPackError, match="not found"):
        operator_pack.build_paper_toolchain_operator_pack(
            dashboard_summary_json=tmp_path / "does_not_exist.json",
            index_summary_json=operator_pack.DEFAULT_INDEX_SUMMARY_JSON,
            index_links_csv=operator_pack.DEFAULT_INDEX_LINKS_CSV,
            cli_help_summary_json=operator_pack.DEFAULT_CLI_HELP_SUMMARY_JSON,
            quickstart_summary_json=operator_pack.DEFAULT_QUICKSTART_SUMMARY_JSON,
            quickstart_commands_csv=operator_pack.DEFAULT_QUICKSTART_COMMANDS_CSV,
            quickstart_md=operator_pack.DEFAULT_QUICKSTART_MD,
            output_dir=tmp_path / "operator_pack",
            generated_at_utc=FIXED_TIME,
        )


def test_corrupt_index_summary_json_fails_clearly(tmp_path):
    corrupt_path = tmp_path / "index_summary.json"
    corrupt_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(operator_pack.PaperToolchainOperatorPackError, match="not valid JSON"):
        operator_pack.build_paper_toolchain_operator_pack(
            dashboard_summary_json=operator_pack.DEFAULT_DASHBOARD_SUMMARY_JSON,
            index_summary_json=corrupt_path,
            index_links_csv=operator_pack.DEFAULT_INDEX_LINKS_CSV,
            cli_help_summary_json=operator_pack.DEFAULT_CLI_HELP_SUMMARY_JSON,
            quickstart_summary_json=operator_pack.DEFAULT_QUICKSTART_SUMMARY_JSON,
            quickstart_commands_csv=operator_pack.DEFAULT_QUICKSTART_COMMANDS_CSV,
            quickstart_md=operator_pack.DEFAULT_QUICKSTART_MD,
            output_dir=tmp_path / "operator_pack",
            generated_at_utc=FIXED_TIME,
        )


def test_missing_configured_pack_target_fails_in_synthetic_fixture(tmp_path):
    paths = _write_synthetic_fixture(tmp_path)

    result = operator_pack.build_paper_toolchain_operator_pack(
        output_dir=tmp_path / "operator_pack",
        generated_at_utc=FIXED_TIME,
        **paths,
    )

    assert result.summary["operator_pack_status"] == "FAIL"
    assert result.summary["failure_count"] > 0
    joined_failures = " | ".join(result.summary["failures"])
    assert "missing configured pack file" in joined_failures


def test_output_json_csv_and_markdown_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "operator_pack"

    first = _run_operator_pack(output_dir)
    assert first.summary["operator_pack_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_operator_pack(output_dir)
    assert second.summary["operator_pack_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_operator_pack_does_not_mutate_p237_to_p251_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in _source_files()}

    result = _run_operator_pack(tmp_path / "operator_pack")

    assert result.summary["operator_pack_status"] == "PASS"
    after = {path: _digest(path) for path in _source_files()}
    assert before == after


def test_cli_builds_operator_pack_outputs_and_exit_code(tmp_path):
    output_dir = tmp_path / "operator_pack"

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
    assert _json(output_dir / "operator_pack_summary.json")["operator_pack_status"] == "PASS"


def test_cli_rejects_missing_input_with_nonzero_exit(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dashboard-summary-json",
            str(tmp_path / "does_not_exist.json"),
            "--output-dir",
            str(tmp_path / "operator_pack"),
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
