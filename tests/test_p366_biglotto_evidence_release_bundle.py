import csv
import json
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_release_bundle as bundle


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P366 release bundle")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = bundle.run_bundle()
        second = bundle.run_bundle()
    finally:
        patcher.undo()
    return first, second


def test_required_p363_p364_p365_artifacts_exist():
    paths = bundle.verify_required_artifacts()
    assert len(paths) == len(bundle.SOURCE_ARTIFACTS)
    assert all(path.is_file() for path in paths)


def test_source_artifact_sha256_inventory_generation(double_run):
    first, _ = double_run
    source_rows = [row for row in first.inventory_rows if row["source_stage"] in {"P363", "P364", "P365"}]
    assert len(source_rows) == len(bundle.SOURCE_ARTIFACTS)
    by_path = {row["artifact_path"]: row for row in source_rows}
    assert by_path["artifacts/P363_biglotto_evidence_pack_adapter_cards.csv"]["row_count"] == "5"
    assert by_path["artifacts/P364_biglotto_evidence_dashboard_subset_table.csv"]["row_count"] == "31"
    assert by_path["artifacts/P365_biglotto_evidence_explorer_query_snapshots.json"]["object_count"] == "1"
    for row in source_rows:
        assert len(row["sha256"]) == 64
        assert row["artifact_type"]
        assert row["role"]


def test_manifest_json_schema(double_run):
    first, _ = double_run
    manifest = first.manifest
    assert manifest["task"] == bundle.TASK
    assert manifest["generated_at"] == bundle.GENERATED_AT
    assert len(manifest["source_artifacts"]) == len(bundle.SOURCE_ARTIFACTS)
    assert len(manifest["output_artifacts"]) == len(bundle.P366_ARTIFACT_BASENAMES)
    assert manifest["statements"]["db_opened"] is False
    assert manifest["statements"]["adapter_calls"] is False
    assert manifest["statements"]["new_scoring_cohort"] is False
    assert "No DB was opened or written." == manifest["no_db_open_write_statement"]
    assert "No adapters were called" in manifest["no_adapter_calls_statement"]
    assert manifest["smoke_summary"]["fail"] == 0


def test_inventory_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.inventory_rows[0]) == bundle.INVENTORY_COLUMNS
    p366_rows = [row for row in first.inventory_rows if row["source_stage"] == "P366"]
    assert len(p366_rows) == len(bundle.P366_ARTIFACT_BASENAMES)
    by_role = {row["role"]: row for row in p366_rows}
    assert by_role["release_bundle:smoke_results"]["row_count"] == str(len(first.smoke_rows))
    assert by_role["release_bundle:cli_examples"]["object_count"] == "1"
    for row in p366_rows:
        assert row["artifact_path"].startswith("artifacts/P366_biglotto_evidence_release_bundle_")
        assert len(row["sha256"]) == 64 or row["sha256"] == "SELF_SHA256_OMITTED_RECURSIVE_ARTIFACT"


def test_smoke_results_csv_schema(double_run):
    first, _ = double_run
    assert tuple(first.smoke_rows[0]) == bundle.SMOKE_COLUMNS
    assert all(row["status"] == "PASS" for row in first.smoke_rows)
    names = {row["check_name"] for row in first.smoke_rows}
    assert "cli_help_works:p366" in names
    assert "cli_help_works:p365_explorer" in names
    assert "example_commands_deterministic" in names
    assert "forbidden_promotional_phrases_absent" in names
    assert any(name.startswith("validate_entry_file:") for name in names)


def test_cli_examples_json_schema(double_run):
    first, _ = double_run
    examples = first.cli_examples
    assert examples["task"] == bundle.TASK
    assert examples["generated_at"] == bundle.GENERATED_AT
    assert set(examples["examples"]) == {
        "explorer_help",
        "list_adapters",
        "list_compact_shortlist",
        "show_one_adapter_detail",
        "show_one_subset_detail",
    }
    assert examples["examples"]["explorer_help"]["exit_code"] == 0
    assert "usage:" in examples["examples"]["explorer_help"]["stdout"]
    assert len(examples["examples"]["list_adapters"]["stdout"].splitlines()) == 5
    assert "display_rank" in examples["examples"]["list_compact_shortlist"]["stdout"].splitlines()[0]
    assert json.loads(examples["examples"]["show_one_adapter_detail"]["stdout"])["adapter_function"]
    assert json.loads(examples["examples"]["show_one_subset_detail"]["stdout"])["adapter_subset"]


def test_landing_html_contains_required_sections_and_disclaimers(double_run):
    first, _ = double_run
    html = first.landing_html
    assert "<!doctype html>" in html
    assert "Scope / disclaimer banner" in html
    assert "P363/P364/P365/P366 Artifact Paths" in html
    assert "Available CLI Commands" in html
    assert "Smoke Check Summary" in html
    assert "No DB open/write." in html
    assert "No adapter calls." in html
    for text in bundle.DISCLAIMER_LINES:
        assert text in html


def test_readme_contains_local_only_usage_and_disclaimers(double_run):
    first, _ = double_run
    readme = first.readme_md
    assert "local-only bundle" in readme
    assert "python3 -m recovered_strategies.biglotto.no_db_evidence_release_bundle smoke" in readme
    assert "artifacts/P366_biglotto_evidence_release_bundle_landing.html" in readme
    assert "No betting advice." in readme
    assert "No production registry import." in readme
    assert "Shape-only and blocked targets remain excluded." in readme


def test_cli_generate_help_inventory_smoke_examples_manifest_validate_work(tmp_path):
    generate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_release_bundle",
            "--artifacts-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "determinism double-run PASS" in generate_result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created." in generate_result.stdout
    for basename in bundle.P366_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()

    help_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "usage:" in help_result.stdout

    inventory_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "inventory"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert len(list(csv.DictReader(inventory_result.stdout.splitlines()))) == len(
        bundle.SOURCE_ARTIFACTS
    ) + len(bundle.P366_ARTIFACT_BASENAMES)

    smoke_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "smoke"],
        check=True,
        text=True,
        capture_output=True,
    )
    smoke_rows = list(csv.DictReader(smoke_result.stdout.splitlines()))
    assert smoke_rows
    assert {row["status"] for row in smoke_rows} == {"PASS"}

    examples_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "examples"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(examples_result.stdout)["examples"]["explorer_help"]["exit_code"] == 0

    validate_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "validate"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert all(row["status"] == "PASS" for row in csv.DictReader(validate_result.stdout.splitlines()))

    manifest_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_release_bundle", "manifest"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(manifest_result.stdout)["task"] == bundle.TASK


def test_deterministic_double_run_equality(double_run, tmp_path):
    first, second = double_run
    assert first.manifest == second.manifest
    assert first.inventory_rows == second.inventory_rows
    assert first.smoke_rows == second.smoke_rows
    assert first.cli_examples == second.cli_examples
    assert first.landing_html == second.landing_html
    assert first.readme_md == second.readme_md
    first_paths = bundle.write_artifacts(first, tmp_path / "first")
    second_paths = bundle.write_artifacts(second, tmp_path / "second")
    for key in first_paths:
        assert first_paths[key].read_bytes() == second_paths[key].read_bytes()


def test_generated_artifacts_parse_readback(tmp_path, double_run):
    first, _ = double_run
    paths = bundle.write_artifacts(first, tmp_path)
    with open(paths["manifest"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == bundle.TASK
    with open(paths["inventory"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.inventory_rows)
    with open(paths["smoke_results"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(first.smoke_rows)
    with open(paths["cli_examples"], encoding="utf-8") as handle:
        assert json.load(handle)["task"] == bundle.TASK
    assert paths["landing"].read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "# P366 Big Lotto no-DB evidence release bundle" in paths["readme"].read_text(
        encoding="utf-8"
    )


def test_no_db_import_open_guard_if_practical(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", _blocked_connect)
    output = bundle.run_bundle()
    assert output.manifest["statements"]["db_opened"] is False
    assert output.manifest["statements"]["db_written"] is False


def test_no_adapter_execution_guard_if_practical(double_run):
    first, _ = double_run
    assert first.manifest["statements"]["adapter_calls"] is False
    assert "No adapters were called" in first.manifest["no_adapter_calls_statement"]
    for row in first.smoke_rows:
        assert "adapter execution" not in row["details"].lower()
