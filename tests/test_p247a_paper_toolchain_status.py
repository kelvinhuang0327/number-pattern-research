"""P247-A result-only paper toolchain status exporter tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.recommendation import paper_toolchain_status as status


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_toolchain_status.py"
FIXED_TIME = "2026-07-09T00:00:00Z"
REQUIRED_OUTPUTS = (
    "toolchain_status.json",
    "toolchain_steps.csv",
    "toolchain_report.md",
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
    for spec in status.STEP_SPECS:
        for root in spec.artifact_roots:
            if root.is_file():
                files.append(root)
            elif root.is_dir():
                files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def _run_status(output_dir: Path) -> status.PaperToolchainStatusResult:
    return status.build_paper_toolchain_status(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )


def test_status_builds_json_csv_and_markdown_from_committed_artifacts(tmp_path):
    output_dir = tmp_path / "toolchain_status"

    result = _run_status(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.status == _json(output_dir / "toolchain_status.json")
    rows = _csv(output_dir / "toolchain_steps.csv")
    assert len(rows) == 10
    assert list(rows[0]) == status.STEP_CSV_FIELDNAMES
    markdown = (output_dir / "toolchain_report.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Toolchain Steps",
        "## Latest Gate",
        "## Missing / Warning Items",
        "## Safety Boundaries",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_current_committed_toolchain_status_is_pass(tmp_path):
    payload = _run_status(tmp_path / "toolchain_status").status

    assert payload["toolchain_status"] == "PASS"
    assert payload["step_count"] == 10
    assert payload["artifact_root_count"] == 12
    assert payload["present_artifact_root_count"] == 12
    assert payload["missing_artifact_root_count"] == 0
    assert payload["script_count"] == 10
    assert payload["present_script_count"] == 10
    assert payload["latest_gate_status"] == "PASS"
    assert payload["warnings"] == []
    assert payload["failures"] == []


def test_required_limitation_labels_and_no_side_effect_flags_are_present(tmp_path):
    payload = _run_status(tmp_path / "toolchain_status").status

    for label in status.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert payload["no_side_effects"]["read_existing_artifacts_only"] is True
    assert payload["no_side_effects"]["executed_existing_workflows"] is False
    assert payload["no_side_effects"]["computed_roi_pnl_ev_kelly"] is False
    assert payload["no_side_effects"]["created_betting_recommendations"] is False


def test_source_hashes_include_script_module_and_artifact_digest(tmp_path):
    payload = _run_status(tmp_path / "toolchain_status").status
    script = "scripts/check_mlb_paper_artifact_diff.py"
    module = "wbc_backend/recommendation/paper_artifact_diff_gate.py"
    artifact = "report/p246a_paper_artifact_diff_gate"

    assert payload["source_hashes"]["scripts"][script] == _digest(ROOT / script)
    assert payload["source_hashes"]["modules"][module] == _digest(ROOT / module)
    assert payload["source_hashes"]["artifact_roots"][artifact]["file_count"] == 3
    assert payload["source_hashes"]["artifact_roots"][artifact]["sha256_or_digest"]


def test_missing_required_artifact_root_fails_clearly(tmp_path):
    missing_step = status.ToolchainStepSpec(
        step_id="PX",
        step_name="missing fixture",
        script_candidates=(ROOT / "scripts" / "missing_fixture.py",),
        module_path=None,
        artifact_roots=(tmp_path / "missing_artifact",),
    )

    result = status.build_paper_toolchain_status(
        output_dir=tmp_path / "toolchain_status",
        generated_at_utc=FIXED_TIME,
        step_specs=(missing_step,),
    )

    assert result.status["toolchain_status"] == "FAIL"
    assert result.status["missing_artifact_root_count"] == 1
    assert "required artifact root missing" in result.status["failures"][0]


def test_optional_missing_p237_p238_style_script_warns_without_failing(tmp_path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text('{"ok": true}\n', encoding="utf-8")
    optional_step = status.ToolchainStepSpec(
        step_id="PX",
        step_name="optional script fixture",
        script_candidates=(tmp_path / "missing_optional_script.py",),
        module_path=None,
        artifact_roots=(artifact,),
        script_optional=True,
    )

    result = status.build_paper_toolchain_status(
        output_dir=tmp_path / "toolchain_status",
        generated_at_utc=FIXED_TIME,
        step_specs=(optional_step,),
    )

    assert result.status["toolchain_status"] == "WARN"
    assert result.status["warnings"]
    assert result.status["failures"] == []


def test_status_does_not_mutate_p237_to_p246_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in _source_files()}

    result = _run_status(tmp_path / "toolchain_status")

    assert result.status["toolchain_status"] == "PASS"
    assert before == {path: _digest(path) for path in before}


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "toolchain_status"

    first = _run_status(output_dir)
    assert first.status["toolchain_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_status(output_dir)
    assert second.status["toolchain_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_cli_builds_toolchain_status_outputs(tmp_path):
    output_dir = tmp_path / "toolchain_status"

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
    assert _json(output_dir / "toolchain_status.json")["toolchain_status"] == "PASS"
