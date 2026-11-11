"""P250-A result-only paper toolchain CLI help smoke exporter tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.recommendation import paper_toolchain_cli_help as cli_help


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_cli_help.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "cli_help_summary.json",
    "cli_help_entries.csv",
    "cli_help_report.md",
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
    for spec in cli_help.DEFAULT_SCRIPT_SPECS:
        if spec.script_path.is_file():
            files.append(spec.script_path)
    for root in SOURCE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(set(files))


def _run_cli_help(output_dir: Path, **kwargs) -> cli_help.PaperToolchainCliHelpResult:
    return cli_help.build_paper_toolchain_cli_help(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
        python_executable=sys.executable,
        **kwargs,
    )


def test_default_help_smoke_produces_json_csv_and_markdown_outputs(tmp_path):
    output_dir = tmp_path / "cli_help"

    result = _run_cli_help(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.summary == _json(output_dir / "cli_help_summary.json")
    rows = _csv(output_dir / "cli_help_entries.csv")
    assert len(rows) == len(cli_help.DEFAULT_SCRIPT_SPECS)
    assert list(rows[0]) == cli_help.ENTRY_CSV_FIELDNAMES
    markdown = (output_dir / "cli_help_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Help Smoke Results",
        "## Scripts",
        "## Hashes",
        "## Warnings / Failures",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_default_help_smoke_returns_pass_over_current_committed_scripts(tmp_path):
    payload = _run_cli_help(tmp_path / "cli_help").summary

    assert payload["smoke_status"] == "PASS"
    assert payload["script_count"] == len(cli_help.DEFAULT_SCRIPT_SPECS)
    assert payload["help_pass_count"] == len(cli_help.DEFAULT_SCRIPT_SPECS)
    assert payload["help_fail_count"] == 0
    assert payload["timeout_count"] == 0
    assert payload["missing_script_count"] == 0
    assert payload["warning_count"] == 0
    assert payload["failure_count"] == 0
    assert payload["warnings"] == []
    assert payload["failures"] == []
    for label in cli_help.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["executed_only_help_calls"] is True
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False
    assert payload["no_side_effects"]["created_betting_recommendations_or_rankings"] is False
    assert payload["no_side_effects"]["created_live_production_or_real_betting_output"] is False


def test_missing_configured_script_fails_in_synthetic_fixture(tmp_path):
    missing_spec = cli_help.ScriptSpec("missing_fixture", "PX", tmp_path / "does_not_exist.py")

    result = cli_help.build_paper_toolchain_cli_help(
        output_dir=tmp_path / "cli_help",
        generated_at_utc=FIXED_TIME,
        python_executable=sys.executable,
        script_specs=(missing_spec,),
    )

    assert result.summary["smoke_status"] == "FAIL"
    assert result.summary["missing_script_count"] == 1
    assert result.summary["failure_count"] == 1
    assert "script not found" in result.summary["failures"][0]
    row = result.entry_rows[0]
    assert row["script_present"] is False
    assert row["status"] == "FAIL"


def test_nonzero_help_exit_fails_in_synthetic_fixture(tmp_path):
    broken_script = tmp_path / "broken_help_script.py"
    broken_script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    broken_spec = cli_help.ScriptSpec("broken_fixture", "PX", broken_script)

    result = cli_help.build_paper_toolchain_cli_help(
        output_dir=tmp_path / "cli_help",
        generated_at_utc=FIXED_TIME,
        python_executable=sys.executable,
        script_specs=(broken_spec,),
    )

    assert result.summary["smoke_status"] == "FAIL"
    assert result.summary["help_fail_count"] == 1
    assert result.summary["missing_script_count"] == 0
    assert result.summary["timeout_count"] == 0
    assert "help exit code 3" in result.summary["failures"][0]


def test_timeout_fails_in_synthetic_fixture(tmp_path):
    slow_script = tmp_path / "slow_help_script.py"
    slow_script.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    slow_spec = cli_help.ScriptSpec("slow_fixture", "PX", slow_script)

    result = cli_help.build_paper_toolchain_cli_help(
        output_dir=tmp_path / "cli_help",
        generated_at_utc=FIXED_TIME,
        python_executable=sys.executable,
        timeout_seconds=1,
        script_specs=(slow_spec,),
    )

    assert result.summary["smoke_status"] == "FAIL"
    assert result.summary["timeout_count"] == 1
    assert result.summary["missing_script_count"] == 0
    assert result.summary["help_fail_count"] == 0
    assert "timed out" in result.summary["failures"][0]
    row = result.entry_rows[0]
    assert row["timed_out"] is True


def test_help_output_hashes_are_deterministic(tmp_path):
    first = _run_cli_help(tmp_path / "first").summary
    second = _run_cli_help(tmp_path / "second").summary

    assert first["help_output_hashes"] == second["help_output_hashes"]
    assert first["input_script_hashes"] == second["input_script_hashes"]
    for digest in first["help_output_hashes"].values():
        assert digest


def test_output_json_csv_and_markdown_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "cli_help"

    first = _run_cli_help(output_dir)
    assert first.summary["smoke_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_cli_help(output_dir)
    assert second.summary["smoke_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_help_smoke_does_not_mutate_p237_to_p249_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in _source_files()}

    result = _run_cli_help(tmp_path / "cli_help")

    assert result.summary["smoke_status"] == "PASS"
    after = {path: _digest(path) for path in _source_files()}
    assert before == after


def test_cli_builds_help_smoke_outputs_and_exit_code(tmp_path):
    output_dir = tmp_path / "cli_help"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--python",
            sys.executable,
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
    assert _json(output_dir / "cli_help_summary.json")["smoke_status"] == "PASS"


def test_cli_rejects_non_positive_timeout(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(tmp_path / "cli_help"),
            "--generated-at-utc",
            FIXED_TIME,
            "--timeout-seconds",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "timeout_seconds must be positive" in result.stderr
