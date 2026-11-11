"""P243-A local paper artifact catalog tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from wbc_backend.recommendation import paper_artifact_catalog as catalog


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mlb_paper_artifact_catalog.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
REQUIRED_OUTPUTS = (
    "artifact_catalog.json",
    "artifact_catalog.csv",
    "artifact_catalog.md",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_catalog(output_dir: Path) -> catalog.PaperArtifactCatalogResult:
    return catalog.build_paper_artifact_catalog(
        output_dir=output_dir,
        generated_at_utc=FIXED_TIME,
    )


def _source_files() -> list[Path]:
    files: list[Path] = []
    for root in catalog.DEFAULT_SOURCE_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def test_catalog_builds_json_csv_and_markdown_from_committed_artifacts(tmp_path):
    output_dir = tmp_path / "catalog"

    result = _run_catalog(output_dir)

    for name in REQUIRED_OUTPUTS:
        assert (output_dir / name).is_file()
    assert result.catalog == _json(output_dir / "artifact_catalog.json")
    with (output_dir / "artifact_catalog.csv").open(encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows
    assert list(csv_rows[0]) == catalog.CSV_FIELDNAMES
    markdown = (output_dir / "artifact_catalog.md").read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Artifact Groups",
        "## Detected Manifests",
        "## Safety Scan",
        "## Limitations",
        "## Not Claims",
    ):
        assert section in markdown


def test_catalog_status_is_pass_for_current_committed_artifacts(tmp_path):
    summary = _run_catalog(tmp_path / "catalog").catalog

    assert summary["catalog_status"] == "PASS"
    assert summary["forbidden_field_scan_status"] == "PASS"
    assert summary["mutation_guard_status"] == "PASS"
    assert summary["failures"] == []


def test_source_file_sha256_and_size_values_are_recorded(tmp_path):
    output_dir = tmp_path / "catalog"
    _run_catalog(output_dir)

    payload = _json(output_dir / "artifact_catalog.json")
    files = {item["relative_path"]: item for item in payload["source_files"]}
    expected = ROOT / "report" / "p242a_paper_strategy_workflow_bundle" / "bundle_manifest.json"
    relative = str(expected.relative_to(ROOT))

    assert relative in files
    assert files[relative]["sha256"] == _digest(expected)
    assert files[relative]["size_bytes"] == expected.stat().st_size


def test_missing_required_artifact_root_fails_clearly(tmp_path):
    missing = tmp_path / "missing_required_root"

    result = catalog.build_paper_artifact_catalog(
        output_dir=tmp_path / "catalog",
        generated_at_utc=FIXED_TIME,
        source_roots=(missing,),
    )

    assert result.catalog["catalog_status"] == "FAIL"
    assert result.catalog["failures"]
    assert "required source artifact root is missing" in result.catalog["failures"][0]["message"]


def test_forbidden_field_scan_catches_actual_forbidden_data_fields(tmp_path):
    source_root = tmp_path / "synthetic"
    source_root.mkdir()
    (source_root / "actual_fields.csv").write_text(
        "game_id,recommended_bet,pnl_units\n1,HOME,1.25\n",
        encoding="utf-8",
    )
    (source_root / "actual_fields.json").write_text(
        json.dumps({"nested": {"ev": 0.05, "kelly": 0.1}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = catalog.build_paper_artifact_catalog(
        output_dir=tmp_path / "catalog",
        generated_at_utc=FIXED_TIME,
        source_roots=(source_root,),
    )

    observed = "\n".join(item["observed"] for item in result.catalog["failures"])
    assert result.catalog["catalog_status"] == "FAIL"
    assert result.catalog["forbidden_field_scan_status"] == "FAIL"
    assert "recommended_bet" in observed
    assert "pnl_units" in observed
    assert "$.nested.ev" in observed
    assert "$.nested.kelly" in observed


def test_required_limitation_labels_are_present(tmp_path):
    labels = _run_catalog(tmp_path / "catalog").catalog["limitation_labels"]

    for label in catalog.REQUIRED_LIMITATION_LABELS:
        assert label in labels


def test_catalog_does_not_mutate_p237_to_p242_source_artifacts(tmp_path):
    before = {path: _digest(path) for path in _source_files()}

    result = _run_catalog(tmp_path / "catalog")

    assert result.catalog["catalog_status"] == "PASS"
    assert before == {path: _digest(path) for path in before}


def test_output_json_csv_and_markdown_are_deterministic_with_fixed_generated_at(tmp_path):
    output_dir = tmp_path / "catalog"

    first = _run_catalog(output_dir)
    assert first.catalog["catalog_status"] == "PASS"
    first_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}
    second = _run_catalog(output_dir)
    assert second.catalog["catalog_status"] == "PASS"
    second_hashes = {name: _digest(output_dir / name) for name in REQUIRED_OUTPUTS}

    assert first_hashes == second_hashes


def test_cli_builds_catalog_outputs(tmp_path):
    output_dir = tmp_path / "catalog"

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
    assert _json(output_dir / "artifact_catalog.json")["catalog_status"] == "PASS"
