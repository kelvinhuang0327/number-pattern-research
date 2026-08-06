<<<<<<< HEAD
"""Focused contract tests for scripts/randomness_audit.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "randomness_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("randomness_audit_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_db(path: Path, *, repeated_daily: bool = False) -> Path:
    rng = random.Random(9917)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, draw TEXT NOT NULL, date TEXT NOT NULL, "
        "lottery_type TEXT NOT NULL, numbers TEXT NOT NULL, special INTEGER)"
    )
    start = datetime(2020, 1, 1)
    configs = (
        ("POWER_LOTTO", 38, 6, 8, 80),
        ("BIG_LOTTO", 49, 6, 49, 80),
        ("DAILY_539", 39, 5, None, 90),
    )
    daily_first = None
    for lottery_type, pool, pick, special_pool, count in configs:
        for index in range(count):
            numbers = sorted(rng.sample(range(1, pool + 1), pick))
            if lottery_type == "BIG_LOTTO" and max(numbers) <= 25:
                numbers = sorted([*numbers[:-1], 49])
            if lottery_type == "DAILY_539" and repeated_daily and index == count - 1:
                numbers = daily_first
            if lottery_type == "DAILY_539" and index == 0:
                daily_first = numbers
            if lottery_type == "BIG_LOTTO":
                special_candidates = [
                    value for value in range(1, 50) if value not in numbers
                ]
                special = special_candidates[index % len(special_candidates)]
            elif lottery_type == "POWER_LOTTO":
                special = index % special_pool + 1
            else:
                special = 0
            connection.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES(?,?,?,?,?)",
                (
                    f"{110000000 + index + 1}",
                    (start + timedelta(days=index)).strftime("%Y/%m/%d"),
                    lottery_type,
                    json.dumps(numbers),
                    special,
                ),
            )
    for index in range(3):
        numbers = [1, 2, 3, 4, 5, 6]
        connection.execute(
            "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES(?,?,?,?,?)",
            (f"20{index:06d}", "2020/01/01", "BIG_LOTTO", json.dumps(numbers), 7),
        )
    connection.execute(
        "CREATE VIEW draws_big_lotto_canonical_main AS SELECT * FROM draws "
        "WHERE lottery_type='BIG_LOTTO' AND draw NOT LIKE '%-%' "
        "AND NOT (LENGTH(draw)=8 AND draw LIKE '20%') "
        "AND (SELECT MAX(CAST(value AS INTEGER)) FROM json_each(numbers)) > 25"
    )
    connection.commit()
    connection.close()
    return path


def _legacy() -> dict:
    return {
        "run_timestamp": "2026-06-02T06:57:02.982982",
        "re_attestation_timestamp": "2026-06-30T13:42:02.321987",
        "re_attestation_type": "HUMAN_REVIEW_OF_UNCHANGED_COMMITTED_EVIDENCE",
        "reanalysis_performed": False,
        "new_draws_analyzed": False,
        "final_verdict": "WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION",
        "tests": [{"confirmatory": True}] * 44,
    }


def _compute(db: Path, *, seed: int = 42, simulations: int = 24):
    return audit.compute_audit(
        db_path=db,
        seed=seed,
        simulations=simulations,
        alpha=0.05,
        existing_results=_legacy(),
        run_timestamp=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )


def test_strict_json_rejects_duplicate_top_level_key_with_source(tmp_path):
    source = tmp_path / "duplicate-top-level.json"
    source.write_text('{"seed":42,"seed":43}', encoding="utf-8")

    with pytest.raises(audit.AuditContractError) as raised:
        audit._load_json(source)

    assert str(source) in str(raised.value)
    assert "duplicate JSON object key 'seed'" in str(raised.value)


@pytest.mark.parametrize(
    ("case", "payload", "duplicate_key"),
    (
        (
            "provenance",
            '{"provenance":{"implementation":{},"implementation":{}}}',
            "implementation",
        ),
        (
            "historical-evidence",
            '{"provenance":{"historical_evidence":{"actual_run_provenance":"a",'
            '"actual_run_provenance":"b"}}}',
            "actual_run_provenance",
        ),
        (
            "dataset-binding",
            '{"validation_results":{"dataset_binding":{"status":"PASS"},'
            '"dataset_binding":{"status":"FAIL"}}}',
            "dataset_binding",
        ),
    ),
)
def test_strict_json_rejects_duplicate_nested_governing_keys(
    tmp_path, case, payload, duplicate_key
):
    source = tmp_path / f"duplicate-{case}.json"
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(audit.AuditContractError) as raised:
        audit._load_json(source)

    assert str(source) in str(raised.value)
    assert f"duplicate JSON object key {duplicate_key!r}" in str(raised.value)


def test_strict_json_preserves_clean_values_types_and_order(tmp_path):
    source = tmp_path / "clean.json"
    text = '{"z":0,"nested":{"b":true,"a":null},"items":[1,2.5,"three"]}'
    source.write_text(text, encoding="utf-8")

    strict = audit._load_json(source)
    standard = json.loads(text)

    assert strict == standard
    assert list(strict) == list(standard)
    assert list(strict["nested"]) == list(standard["nested"])
    assert [type(value) for value in strict["items"]] == [
        type(value) for value in standard["items"]
    ]


def test_committed_artifact_strict_load_and_normalized_result_are_identical():
    source = REPO / "outputs" / "randomness_audit" / "randomness_audit_results.json"
    strict = audit._load_json(source)
    standard = json.loads(source.read_text(encoding="utf-8"))

    assert strict == standard
    assert audit.normalized_result_digest(strict) == audit.normalized_result_digest(standard)
    assert (
        audit.normalized_result_digest(strict)
        == "ca097c324970ce06acb1fee29efccb48576b48cb9c34317fc24d341042338616"
    )


def test_ambiguous_run_input_fails_before_compute_db_open_and_publication_callbacks(
    tmp_path, monkeypatch
):
    source = tmp_path / "ambiguous-results.json"
    source.write_text('{"provenance":{},"provenance":{}}', encoding="utf-8")
    callbacks = []

    def forbidden(name):
        def callback(*args, **kwargs):
            callbacks.append(name)
            raise AssertionError(f"{name} callback must not run")

        return callback

    monkeypatch.setattr(audit, "compute_audit", forbidden("compute"))
    monkeypatch.setattr(audit, "load_canonical_data", forbidden("DB load"))
    monkeypatch.setattr(audit, "_connect_read_only", forbidden("DB open"))
    monkeypatch.setattr(audit, "_write_pair", forbidden("publication"))
    args = SimpleNamespace(
        results_out=source,
        summary_out=tmp_path / "summary.md",
        db=tmp_path / "forbidden.db",
        seed=42,
        simulations=2000,
        alpha=0.05,
    )

    with pytest.raises(audit.AuditContractError, match="duplicate JSON object key 'provenance'"):
        audit.run_and_publish(args)

    assert callbacks == []


def test_ambiguous_verify_input_fails_before_artifact_verification_callbacks(
    tmp_path, monkeypatch
):
    source = tmp_path / "ambiguous-results.json"
    source.write_text('{"dataset_identity":{},"dataset_identity":{}}', encoding="utf-8")
    callbacks = []

    def forbidden(name):
        def callback(*args, **kwargs):
            callbacks.append(name)
            raise AssertionError(f"{name} callback must not run")

        return callback

    monkeypatch.setattr(audit, "_parse_utc", forbidden("timestamp verification"))
    monkeypatch.setattr(audit, "compute_audit", forbidden("artifact recomputation"))
    monkeypatch.setattr(audit, "render_summary", forbidden("artifact summary verification"))
    args = SimpleNamespace(
        results=source,
        summary=tmp_path / "summary.md",
        db=tmp_path / "forbidden.db",
        seed=42,
        simulations=2000,
        alpha=0.05,
    )

    with pytest.raises(audit.AuditContractError, match="duplicate JSON object key 'dataset_identity'"):
        audit.verify_artifacts(args)

    assert callbacks == []


def test_confirmatory_registry_is_frozen_and_complete():
    assert len(audit.CONFIRMATORY_REGISTRY) == 44
    ids = [entry["test_id"] for entry in audit.CONFIRMATORY_REGISTRY]
    assert len(ids) == len(set(ids))
    assert ids[0] == "power_lotto_overall_frequency"
    assert ids[-1] == "daily_539_drift_halves"
    assert audit.registry_sha256() == "29e89b798a1937628d7856a45e444669066a2141062db1159e91786a1d10a61c"


def test_big_lotto_special_domain_and_null_model_are_one_through_49():
    entry = next(
        value for value in audit.CONFIRMATORY_REGISTRY
        if value["test_id"] == "big_lotto_special_uniformity"
    )
    assert "[1..49]" in entry["hypothesis"]
    config = next(config for config in audit.GAME_CONFIGS if config.game == "big_lotto")
    assert (config.special_min, config.special_max) == (1, 49)


def test_duplicate_records_are_distinct_from_repeated_combinations():
    first = audit.Draw("1", "2026-01-01", (1, 2, 3, 4, 5), None)
    repeat = audit.Draw("2", "2026-02-01", (1, 2, 3, 4, 5), None)
    classification = audit.classify_record_identity([first, repeat])
    assert classification["duplicate_draw_id_groups"] == 0
    assert classification["duplicate_full_record_groups"] == 0
    assert classification["repeated_main_combination_groups"] == 1
    assert classification["repeated_full_outcome_groups"] == 1


def test_duplicate_draw_id_and_full_record_are_defects():
    row = audit.Draw("1", "2026-01-01", (1, 2, 3, 4, 5), None)
    classification = audit.classify_record_identity([row, row])
    assert classification["duplicate_draw_id_groups"] == 1
    assert classification["duplicate_full_record_groups"] == 1


def test_sorted_position_tests_are_exploratory_only():
    assert len(audit.EXPLORATORY_REGISTRY) == 17
    assert all(entry["correction_family"] is None for entry in audit.EXPLORATORY_REGISTRY)
    assert all("sorted-order artifact" in entry["hypothesis"] for entry in audit.EXPLORATORY_REGISTRY)


def test_mature_multiple_testing_fixture():
    from lottery_api.utils.correction_gate import correction_gate_summary

    result = correction_gate_summary([0.001, 0.02, 0.5], alpha=0.05)
    assert result["bonferroni"]["adjusted_p_values"] == [0.003, 0.06, 1.0]
    assert result["bonferroni"]["rejected"] == [True, False, False]
    assert result["bh_fdr"]["adjusted_p_values"] == [0.003, 0.03, 0.5]


def test_read_only_connection_blocks_write_and_preserves_db(tmp_path):
    db = _build_db(tmp_path / "fixture.db")
    before = _sha(db)
    connection = audit._connect_read_only(db)
    try:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden_write(x INTEGER)")
    finally:
        connection.close()
    assert _sha(db) == before


def test_load_fails_closed_when_canonical_view_missing(tmp_path):
    db = tmp_path / "missing-view.db"
    connection = sqlite3.connect(db)
    connection.execute(
        "CREATE TABLE draws(draw TEXT,date TEXT,lottery_type TEXT,numbers TEXT,special INTEGER)"
    )
    connection.commit()
    connection.close()
    with pytest.raises(audit.AuditContractError, match="view"):
        audit.load_canonical_data(db)


def test_load_uses_view_and_classifies_repeated_daily_outcome(tmp_path):
    db = _build_db(tmp_path / "fixture.db", repeated_daily=True)
    loaded = audit.load_canonical_data(db)
    sources = {source["game"]: source for source in loaded["sources"]}
    assert sources["big_lotto"]["excluded_row_count"] == 3
    assert sources["daily_539"]["repeated_main_combinations"] == 1
    assert sources["daily_539"]["duplicate_draw_ids"] == 0


def test_same_seed_same_process_is_deterministic(tmp_path):
    db = _build_db(tmp_path / "fixture.db")
    first = _compute(db)
    second = _compute(db)
    assert first == second
    assert audit.render_summary(first) == audit.render_summary(second)


def test_different_seed_changes_monte_carlo_evidence(tmp_path):
    db = _build_db(tmp_path / "fixture.db")
    first = _compute(db, seed=42)
    second = _compute(db, seed=43)
    first_p = [test["p_raw"] for test in first["tests"] if "monte_carlo" in test["method"]]
    second_p = [test["p_raw"] for test in second["tests"] if "monte_carlo" in test["method"]]
    assert first_p != second_p


def test_required_evidence_fields_and_corrections(tmp_path):
    db = _build_db(tmp_path / "fixture.db", repeated_daily=True)
    result = _compute(db)
    assert result["run_timestamp"].endswith("Z")
    assert result["reanalysis_performed"] is True
    assert result["new_draws_analyzed"] is False
    assert result["confirmatory_test_count"] == 44
    assert result["exploratory_test_count"] == 17
    assert result["multiple_testing_methods"] == ["bonferroni", "bh_fdr"]
    assert all(value["status"] == "PASS" for value in result["validation_results"].values())
    assert all(
        test["p_bonferroni"] is None and test["q_bh_fdr"] is None
        for test in result["tests"] if not test["confirmatory"]
    )


def test_artifacts_verify_in_two_independent_processes(tmp_path):
    db = _build_db(tmp_path / "fixture.db")
    result = _compute(db)
    results = tmp_path / "results.json"
    summary = tmp_path / "summary.md"
    results.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary.write_text(audit.render_summary(result), encoding="utf-8")
    command = [
        sys.executable,
        str(SCRIPT),
        "verify",
        "--db",
        str(db),
        "--seed",
        "42",
        "--simulations",
        "24",
        "--alpha",
        "0.05",
        "--results",
        str(results),
        "--summary",
        str(summary),
    ]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    first = subprocess.run(command, cwd=REPO, env=environment, text=True, capture_output=True)
    second = subprocess.run(command, cwd=REPO, env=environment, text=True, capture_output=True)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout


def test_future_or_naive_run_timestamp_fails():
    with pytest.raises(audit.AuditContractError):
        audit._format_utc(datetime(2026, 1, 1))
    with pytest.raises(audit.AuditContractError):
        audit._parse_utc("2026-01-01T00:00:00")


def test_output_has_no_machine_specific_db_path(tmp_path):
    db = _build_db(tmp_path / "fixture.db")
    text = json.dumps(_compute(db), sort_keys=True)
    assert str(tmp_path) not in text
    assert "fixture.db" not in text
=======
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Optional
from unittest.mock import patch

import pytest

from scripts import randomness_audit as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_PATH = REPO_ROOT / "wiki" / "system" / "randomness_final_verdict.md"

EXPECTED_P238B_SOURCE_SHA256 = "6eee50f61101b016737863eb426da6a0e893bc2d3f38387aa232ac1b4b86dcd8"
EXPECTED_P246K_SOURCE_SHA256 = "3ddd1453ae562c0ac6bec1ada0bc6c2ca3339012ec8a2a26dc233bc1fac83157"
EXPECTED_CURRENT_INPUT_SHA256 = "7d48306f31746ec3ea8976b4d0b88f2577decd52191391ee5c059f2fd4588a09"
EXPECTED_CURRENT_P246K_SEMANTIC_SHA256 = "48f72f61764e09de20702a853d124930eb3275ce49eb7e9b4b9e26e84f5d9dd1"
EXPECTED_RESULTS_SHA256 = "c1436cf5804f457c0f53f37278fb57351150f793137355a4d55656c3ebe4e4fb"
EXPECTED_SUMMARY_SHA256 = "a2766ecb0d6ce0d8747c96cd0da40c6f3d1c8371e14f3c547cec7d1b52f8cbc0"
EXPECTED_WIKI_SHA256 = "8e221783f6fc82c9fb5bfd0381d5b712672a170ddd298b81855946067a6f27a4"
R5_DUPLICATE_CLASSIFICATION_FIXTURE = (
    '{"classification":"FIRST_VALUE","classification":"LAST_VALUE",'
    '"test_results":[],"is_corrected_significant":false}'
)


@pytest.mark.parametrize(
    ("location", "payload"),
    [
        (
            "top level",
            '{"artifact_schema_version":"2.0","artifact_schema_version":"2.0"}',
        ),
        (
            "nested current audit",
            '{"current_executable_audit":{"task_id":"P691","task_id":"P691"}}',
        ),
        (
            "nested P246K payload",
            '{"current_executable_audit":{"p246k_existing_logic_result":'
            '{"task_id":"P246K","task_id":"P246K"}}}',
        ),
        (
            "cadence anchor",
            '{"current_executable_audit":{"cadence_anchor":'
            '{"canonical_draw_count":1,"canonical_draw_count":1}}}',
        ),
        (
            "provenance",
            '{"current_executable_audit":{"input_provenance":'
            '{"db_identity":"canonical","db_identity":"canonical"}}}',
        ),
        (
            "historical legacy payload",
            '{"run_timestamp":"2026-06-02","run_timestamp":"2026-06-02"}',
        ),
    ],
)
def test_strict_json_loader_rejects_duplicate_keys_at_every_trust_boundary(
    tmp_path: Path,
    location: str,
    payload: str,
):
    path = tmp_path / f"{location.replace(' ', '_')}.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(audit.AuditProvenanceError, match="duplicate JSON object key"):
        audit._load_results(path)


def test_render_validation_rejects_duplicate_keys_before_document_validation():
    duplicate = '{"artifact_schema_version":"2.0","artifact_schema_version":"2.0"}'
    with patch.object(
        audit,
        "_validate_executable_audit_document",
        side_effect=AssertionError("document validation must not run"),
    ):
        with pytest.raises(audit.AuditProvenanceError, match="duplicate JSON object key"):
            audit._validate_rendered_pair(duplicate, "unused")


def test_generation_rejects_duplicate_legacy_json_before_db_or_hash_evaluation(
    tmp_path: Path,
):
    duplicate_legacy = tmp_path / "legacy.json"
    duplicate_legacy.write_text(
        '{"run_timestamp":"2026-06-02","run_timestamp":"2026-06-02"}',
        encoding="utf-8",
    )
    with patch.object(
        audit,
        "load_canonical_big_lotto_population",
        side_effect=AssertionError("DB evaluation must not run"),
    ):
        with pytest.raises(audit.AuditProvenanceError, match="duplicate JSON object key"):
            audit.generate(
                db_path=tmp_path / "unused.db",
                executed_at_utc=datetime(2026, 7, 18, tzinfo=timezone.utc),
                legacy_results_path=duplicate_legacy,
                legacy_summary_path=SUMMARY_PATH,
                wiki_source_path=WIKI_PATH,
                results_out=tmp_path / "results.json",
                summary_out=tmp_path / "summary.md",
                wiki_out=tmp_path / "wiki.md",
            )


def test_p238b_duplicate_classification_rejected_before_donor_and_publication(
    monkeypatch, tmp_path: Path
):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    duplicate_path = tmp_path / "p238b-duplicate-classification.json"
    duplicate_path.write_text(R5_DUPLICATE_CLASSIFICATION_FIXTURE, encoding="utf-8")

    outputs = {
        tmp_path / "results.json": b"unchanged results",
        tmp_path / "summary.md": b"unchanged summary",
        tmp_path / "wiki.md": b"unchanged wiki",
    }
    for path, payload in outputs.items():
        path.write_bytes(payload)

    module = audit._load_p246k_module()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("downstream execution must not run")

    module.load_p238b_comparison = forbidden
    module.run_canonical_nist_reaudit = forbidden
    monkeypatch.setattr(audit, "_load_p246k_module", lambda: module)
    monkeypatch.setattr(audit, "P238B_COMPARISON_ARTIFACT", duplicate_path)
    for name in (
        "_p246k_semantic_payload",
        "build_results_document",
        "render_summary",
        "render_wiki",
        "evaluate_cadence",
        "_publish_artifact_triplet",
    ):
        monkeypatch.setattr(audit, name, forbidden)

    original_read_bytes = Path.read_bytes
    comparison_reads = 0

    def tracking_read_bytes(path: Path) -> bytes:
        nonlocal comparison_reads
        if path == duplicate_path:
            comparison_reads += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", tracking_read_bytes)
    before_db = (
        original_read_bytes(db_path),
        db_path.stat().st_size,
        db_path.stat().st_mtime_ns,
        db_path.stat().st_ino,
    )

    with pytest.raises(audit.AuditProvenanceError, match="duplicate JSON object key.*classification"):
        audit.generate(
            db_path=db_path.resolve(),
            executed_at_utc=datetime(2026, 7, 18, 13, 37, 50, tzinfo=timezone.utc),
            legacy_results_path=RESULTS_PATH,
            legacy_summary_path=SUMMARY_PATH,
            wiki_source_path=WIKI_PATH,
            results_out=tmp_path / "results.json",
            summary_out=tmp_path / "summary.md",
            wiki_out=tmp_path / "wiki.md",
        )

    assert comparison_reads == 1
    assert module.load_p238b_comparison is forbidden
    assert module.run_canonical_nist_reaudit is forbidden
    assert original_read_bytes(duplicate_path).decode("utf-8") == R5_DUPLICATE_CLASSIFICATION_FIXTURE
    assert (
        original_read_bytes(db_path),
        db_path.stat().st_size,
        db_path.stat().st_mtime_ns,
        db_path.stat().st_ino,
    ) == before_db
    for path, payload in outputs.items():
        assert original_read_bytes(path) == payload


def _create_canonical_db(path: Path, *, count: int = 80) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE draws ("
            "id INTEGER PRIMARY KEY, draw TEXT NOT NULL, date TEXT NOT NULL, "
            "lottery_type TEXT NOT NULL, numbers TEXT NOT NULL, special INTEGER DEFAULT 0, "
            "jackpot_amount REAL DEFAULT NULL, UNIQUE(draw, lottery_type))"
        )
        for index in range(count):
            numbers = sorted(((index + 7 * offset) % 49) + 1 for offset in range(6))
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES (?,?,?,?,?)",
                (
                    f"115{index + 1:06d}",
                    f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
                    "BIG_LOTTO",
                    json.dumps(numbers),
                    ((index * 3) % 49) + 1,
                ),
            )
        conn.execute(
            "CREATE VIEW draws_big_lotto_canonical_main AS "
            "SELECT * FROM draws WHERE lottery_type='BIG_LOTTO'"
        )
        conn.commit()
    finally:
        conn.close()


def _fake_p246k_result(
    population_count: int,
    raw_count: int,
    *,
    yellow_check: Optional[str] = None,
    db_path: str = "/Users/tester/private/canonical.db",
) -> dict:
    statuses = {
        "draw_sum_distribution": "GREEN",
        "number_frequency_uniformity": "GREEN",
        "runs_test": "GREEN",
        "ljung_box_lag10": "GREEN",
        "entropy": "GREEN",
    }
    if yellow_check is not None:
        statuses[yellow_check] = "YELLOW"
    yellow = list(statuses.values()).count("YELLOW")
    green = len(statuses) - yellow
    overall = "GREEN" if yellow == 0 else "YELLOW"
    return {
        "schema_version": "1.0",
        "task_id": "P246K",
        "classification": (
            "P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE"
            if overall == "GREEN"
            else "P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY"
        ),
        "db_path": db_path,
        "db_read": True,
        "db_read_only": True,
        "db_write_performed": False,
        "input_population": "CANONICAL_MAIN_DRAW",
        "raw_population_count": raw_count,
        "canonical_population_count": population_count,
        "excluded_add_on_count": raw_count - population_count,
        "exclusion_rules_verified": {
            "canonical_count": population_count,
            "raw_count": raw_count,
            "excluded_count": raw_count - population_count,
            "hyphen_in_canonical": 0,
            "date_format_in_canonical": 0,
            "small_pool_in_canonical": 0,
            "all_exclusions_verified": True,
            "max_num_all_above_25": True,
            "num_range_valid": True,
        },
        "audit_methods": dict(audit.P246K_REQUIRED_AUDIT_METHODS),
        "audit_results": {
            "draw_sum_distribution": {
                "n": population_count,
                "ks_stat": 0.01,
                "ks_p": 0.5,
                "status": statuses["draw_sum_distribution"],
            },
            "number_frequency_uniformity": {
                "n_draws": population_count,
                "n_numbers": population_count * 6,
                "max_frequency": max(1, population_count),
                "min_frequency": max(1, population_count - 1),
                "chi2_stat": 1.0,
                "chi2_p": 0.5,
                "status": statuses["number_frequency_uniformity"]
            },
            "serial_randomness": {
                "runs_test": {
                    "z_stat": 0.0,
                    "p_value": 0.5,
                    "status": statuses["runs_test"],
                },
                "ljung_box_lag10": {
                    "stat": 1.0,
                    "p_value": 0.5,
                    "status": statuses["ljung_box_lag10"],
                },
            },
            "entropy": {
                "normalized_entropy": 0.999,
                "status": statuses["entropy"],
            },
            "per_position": {"pos_1": {"mean": 1.0}},
            "era_stability": {"2026": {"n": population_count, "mean": 100.0}},
            "summary": {
                "total_tests": 5,
                "green": green,
                "yellow": yellow,
                "overall_status": overall,
            },
        },
    }


def test_source_implementation_hashes_and_transfer_boundary():
    sources = {item["implementation_id"]: item for item in audit._source_implementations()}
    assert sources["P246K"]["source_sha256"] == EXPECTED_P246K_SOURCE_SHA256
    assert sources["P246K"]["entry_symbol"] == "run_canonical_nist_reaudit"
    assert sources["P246K"]["reuse_mode"] == "unchanged_through_read_only_population_adapter"
    assert sources["P238B"]["source_sha256"] == EXPECTED_P238B_SOURCE_SHA256
    assert sources["P238B"]["entry_symbol"] == "_connect_ro"
    excluded = " ".join(sources["P238B"]["excluded"])
    assert "raw BIG_LOTTO" in excluded
    assert "statistical helpers" in excluded


def test_orchestration_runtime_donor_symbols_are_exactly_allowlisted():
    tree = ast.parse(inspect.getsource(audit))
    p238b_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "p238b"
    }
    assert p238b_attributes == {"_connect_ro"}
    assert "DatabaseManager" not in inspect.getsource(audit)


def test_p238b_statistical_and_rendering_runtime_helpers_are_never_called(
    monkeypatch, tmp_path: Path
):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("excluded P238B runtime helper was called")

    for name in (
        "_frequency_test",
        "_special_test",
        "_lag_overlap_test",
        "_gap_test",
        "_apply_corrections",
        "_alert_level",
        "_overall_level",
        "_classification",
        "_build_results",
        "build_artifact",
        "render_markdown",
        "write_artifacts",
        "run",
    ):
        monkeypatch.setattr(audit.p238b, name, forbidden)

    population = audit.load_canonical_big_lotto_population(db_path)
    module = ModuleType("fake_p246k_donor_guard")
    module.load_canonical_draws = forbidden
    module.run_canonical_nist_reaudit = lambda _path: _fake_p246k_result(3, 3)
    assert audit.run_p246k_existing_logic(population, db_path, module=module) == (
        _fake_p246k_result(3, 3)
    )


def test_read_only_open_failure_has_no_writable_fallback(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path)

    def fail_read_only(_path):
        raise sqlite3.OperationalError("forced read-only open failure")

    def forbidden_writable_connect(*_args, **_kwargs):
        raise AssertionError("writable sqlite fallback must never run")

    monkeypatch.setattr(audit.p238b, "_connect_ro", fail_read_only)
    monkeypatch.setattr(audit.sqlite3, "connect", forbidden_writable_connect)
    with pytest.raises(sqlite3.OperationalError, match="forced read-only"):
        audit._read_only_connection(db_path)


def test_read_only_connection_enables_query_only_and_blocks_write(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path)
    conn = audit._read_only_connection(db_path)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 80
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO draws(draw,date,lottery_type,numbers) VALUES ('x','x','x','[]')"
            )
    finally:
        conn.close()


def test_read_only_connection_adds_immutable_private_uri_without_changing_donor(
    monkeypatch, tmp_path: Path
):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path)
    native_connect = audit.sqlite3.connect
    observed = []

    def tracking_connect(database, *args, **kwargs):
        observed.append((str(database), dict(kwargs)))
        return native_connect(database, *args, **kwargs)

    monkeypatch.setattr(audit.sqlite3, "connect", tracking_connect)
    conn = audit._read_only_connection(db_path)
    conn.close()
    assert len(observed) == 1
    uri, kwargs = observed[0]
    assert "mode=ro" in uri
    assert "immutable=1" in uri
    assert "cache=private" in uri
    assert kwargs["uri"] is True


def test_immutable_read_fails_closed_with_nonempty_wal(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path)
    Path(f"{db_path}-wal").write_bytes(b"not-checkpointed")
    with pytest.raises(audit.AuditProvenanceError, match="WAL"):
        audit._read_only_connection(db_path)


def test_population_loader_records_exact_sql_boundaries_and_hash(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    loaded = audit.load_canonical_big_lotto_population(db_path)
    assert len(loaded.draws) == 3
    assert loaded.raw_count == 3
    assert loaded.draws[0]["draw"] == "115000003"
    assert loaded.draws[-1]["draw"] == "115000001"
    provenance = loaded.provenance
    assert provenance["db_identity"] == audit.LOGICAL_DB_IDENTITY
    assert "db_path" not in provenance
    assert provenance["sqlite_immutable"] is True
    assert provenance["sqlite_cache"] == "private"
    assert provenance["wal_precondition"] == "empty_or_absent"
    assert provenance["db_open_mode"] == "sqlite_uri_mode_ro"
    assert provenance["pragma_query_only"] is True
    assert provenance["sql"]["canonical_population"] == audit.CANONICAL_POPULATION_SQL
    assert provenance["sql"]["raw_population_count"] == audit.RAW_POPULATION_COUNT_SQL
    assert len(provenance["selected_row_stream_sha256"]) == 64


def test_population_loader_fails_closed_without_canonical_view(tmp_path: Path):
    db_path = tmp_path / "missing-view.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE draws (draw TEXT, date TEXT, lottery_type TEXT, numbers TEXT, special INTEGER)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(audit.AuditProvenanceError, match="canonical view"):
        audit.load_canonical_big_lotto_population(db_path)


def test_run_p246k_patches_only_loader_seam(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    population = audit.load_canonical_big_lotto_population(db_path)
    module = ModuleType("fake_p246k")

    def legacy_loader(_db_path):
        raise AssertionError("write-capable legacy loader must not run")

    def legacy_runner(_db_path):
        draws, raw_count = module.load_canonical_draws(_db_path)
        return _fake_p246k_result(len(draws), raw_count)

    module.load_canonical_draws = legacy_loader
    module.run_canonical_nist_reaudit = legacy_runner
    result = audit.run_p246k_existing_logic(population, db_path, module=module)
    assert result == _fake_p246k_result(3, 3)
    assert module.load_canonical_draws is legacy_loader


def test_run_p246k_preserves_dependency_free_non_green_result(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    population = audit.load_canonical_big_lotto_population(db_path)
    module = ModuleType("fake_p246k_yellow")
    expected = _fake_p246k_result(3, 3, yellow_check="entropy")

    def legacy_loader(_db_path):
        raise AssertionError("write-capable legacy loader must not run")

    def legacy_runner(_db_path):
        draws, raw_count = module.load_canonical_draws(_db_path)
        assert len(draws) == 3
        assert raw_count == 3
        return expected

    module.load_canonical_draws = legacy_loader
    module.run_canonical_nist_reaudit = legacy_runner
    result = audit.run_p246k_existing_logic(population, db_path, module=module)
    assert result == expected
    assert result["audit_results"]["summary"] == {
        "total_tests": 5,
        "green": 4,
        "yellow": 1,
        "overall_status": "YELLOW",
    }
    assert result["classification"].endswith("YELLOW_OBSERVATION_ONLY")


@pytest.mark.skipif(
    importlib.util.find_spec("scipy") is None or importlib.util.find_spec("statsmodels") is None,
    reason="P246K optional scientific runtime is absent; committed artifact checks remain active",
)
def test_migrated_p246k_path_has_exact_semantic_equivalence(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path)
    population = audit.load_canonical_big_lotto_population(db_path)
    module = audit._load_p246k_module()
    with patch.object(
        module,
        "load_canonical_draws",
        return_value=(population.draws, population.raw_count),
    ):
        expected = module.run_canonical_nist_reaudit(db_path)
    actual = audit.run_p246k_existing_logic(population, db_path, module=module)
    assert audit._p246k_semantic_payload(actual) == audit._p246k_semantic_payload(expected)


def test_strict_p238b_clean_input_preserves_semantics_hash_and_artifact_bytes(
    monkeypatch, tmp_path: Path
):
    committed = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    current = committed["current_executable_audit"]
    expected_result = deepcopy(current["p246k_existing_logic_result"])
    expected_comparison = deepcopy(expected_result["p238b_comparison"])
    population_count = expected_result["canonical_population_count"]
    population = audit.PopulationLoad(
        draws=[{}] * population_count,
        raw_count=expected_result["raw_population_count"],
        provenance=deepcopy(current["input_provenance"]),
    )

    db_path = tmp_path / "canonical.db"
    db_path.write_bytes(b"not opened because the canonical population is injected")
    module = audit._load_p246k_module()
    original_population_loader = module.load_canonical_draws
    original_comparison_loader = module.load_p238b_comparison
    ordinary_loader_calls = 0

    def tracking_ordinary_loader():
        nonlocal ordinary_loader_calls
        ordinary_loader_calls += 1
        return original_comparison_loader()

    def clean_runner(path: Path):
        draws, raw_count = module.load_canonical_draws(path)
        assert len(draws) == population_count
        assert raw_count == population.raw_count
        result = deepcopy(expected_result)
        result["p238b_comparison"] = module.load_p238b_comparison()
        return result

    module.load_p238b_comparison = tracking_ordinary_loader
    module.run_canonical_nist_reaudit = clean_runner
    monkeypatch.setattr(audit, "_load_p246k_module", lambda: module)
    monkeypatch.setattr(audit, "load_canonical_big_lotto_population", lambda _path: population)

    original_read_bytes = Path.read_bytes
    comparison_reads = 0

    def tracking_read_bytes(path: Path) -> bytes:
        nonlocal comparison_reads
        if path == audit.P238B_COMPARISON_ARTIFACT:
            comparison_reads += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", tracking_read_bytes)
    results_out = tmp_path / "generated-results.json"
    summary_out = tmp_path / "generated-summary.md"
    wiki_out = tmp_path / "generated-wiki.md"
    generated = audit.generate(
        db_path=db_path.resolve(),
        executed_at_utc=datetime(2026, 7, 18, 13, 37, 50, tzinfo=timezone.utc),
        legacy_results_path=RESULTS_PATH,
        legacy_summary_path=SUMMARY_PATH,
        wiki_source_path=WIKI_PATH,
        results_out=results_out,
        summary_out=summary_out,
        wiki_out=wiki_out,
    )

    generated_result = generated["current_executable_audit"]["p246k_existing_logic_result"]
    semantic_sha256 = audit._sha256_bytes(
        audit._canonical_json_bytes(audit._p246k_semantic_payload(generated_result))
    )
    assert generated_result["p238b_comparison"] == expected_comparison
    assert semantic_sha256 == EXPECTED_CURRENT_P246K_SEMANTIC_SHA256
    assert comparison_reads == 1
    assert ordinary_loader_calls == 0
    assert module.load_p238b_comparison is tracking_ordinary_loader
    assert module.load_canonical_draws is original_population_loader
    assert original_read_bytes(results_out) == original_read_bytes(RESULTS_PATH)
    assert original_read_bytes(summary_out) == original_read_bytes(SUMMARY_PATH)
    assert original_read_bytes(wiki_out) == original_read_bytes(WIKI_PATH)
    assert audit._sha256_bytes(original_read_bytes(results_out)) == EXPECTED_RESULTS_SHA256
    assert audit._sha256_bytes(original_read_bytes(summary_out)) == EXPECTED_SUMMARY_SHA256
    assert audit._sha256_bytes(original_read_bytes(wiki_out)) == EXPECTED_WIKI_SHA256


def test_legacy_json_payload_is_immutable_and_unreproducible():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    legacy = audit._extract_legacy_payload(document)
    assert audit._sha256_bytes(audit._canonical_json_bytes(legacy)) == audit.LEGACY_CANONICAL_SHA256
    metadata = document["legacy_44_test_evidence"]
    assert metadata["status"] == "IMMUTABLE_LEGACY_EVIDENCE"
    assert metadata["reproducible_from_committed_source"] is False
    assert metadata["historical_confirmatory_test_count"] == 44
    assert metadata["statistical_values_mutated"] is False
    assert document["run_timestamp"] == "2026-06-02T06:57:02.982982"
    assert document["final_verdict"] == "WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION"


def test_legacy_summary_bytes_are_preserved_by_hash():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    legacy_summary = audit.extract_legacy_summary(summary)
    assert audit._sha256_bytes(legacy_summary.encode("utf-8")) == document[
        "legacy_44_test_evidence"
    ]["original_summary_file_sha256"]
    assert "**Total confirmatory tests:** 44" in legacy_summary
    assert "**Run timestamp:** 2026-06-02T06:57:02.982982" in legacy_summary


def test_current_committed_audit_is_existing_p246k_logic_only():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    current = document["current_executable_audit"]
    assert current["task_id"] == audit.TASK_ID
    assert current["historical_44_test_reproduction"] is False
    assert current["scope"] == {
        "lottery_type": "BIG_LOTTO",
        "population": "CANONICAL_MAIN_DRAW",
        "statistical_controller": "P246K",
    }
    assert current["new_statistical_procedure_introduced"] is False
    assert current["combined_p238b_p246k_verdict"] is False
    assert current["db_write_performed"] is False
    assert current["p246k_result_retained_unchanged"] is True
    assert current["p246k_nonsemantic_location_sanitized"] is True
    assert "not current row-family provenance" in current["p246k_static_narrative_caveat"]
    assert current["input_provenance"]["db_identity"] == audit.LOGICAL_DB_IDENTITY
    assert "db_path" not in current["input_provenance"]
    assert current["input_provenance"]["selected_row_stream_sha256"] == EXPECTED_CURRENT_INPUT_SHA256
    assert current["p246k_semantic_output_sha256"] == EXPECTED_CURRENT_P246K_SEMANTIC_SHA256
    p246k = current["p246k_existing_logic_result"]
    assert p246k["db_identity"] == audit.LOGICAL_DB_IDENTITY
    assert "db_path" not in p246k
    assert p246k["canonical_population_count"] == 2125
    assert p246k["audit_results"]["summary"] == {
        "total_tests": 5,
        "green": 5,
        "yellow": 0,
        "overall_status": "GREEN",
    }
    containment = current["p246k_existing_logic_payload_metadata"]
    assert containment["status"] == "UNCHANGED_SOURCE_DIAGNOSTIC_PAYLOAD"
    assert containment["authoritative_for_proving_randomness"] is False
    assert containment["equivalent_to_historical_44_test_audit"] is False
    assert containment["evidence_of_no_exploitable_edge"] is False
    assert containment["validates_another_lottery"] is False
    assert containment["authorizes_prediction"] is False
    assert containment["authorizes_betting"] is False
    assert len(containment["scientific_limitations"]) == 6
    assert current["current_authoritative_conclusion"]["status"] == "DIAGNOSTIC_ONLY"
    assert "does not prove randomness" in current["current_authoritative_conclusion"][
        "statement"
    ]
    assert current["historical_date_conflict"] == audit.HISTORICAL_DATE_CONFLICT


def test_results_build_and_summary_render_are_deterministic(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    population = audit.load_canonical_big_lotto_population(db_path)
    existing_bytes = RESULTS_PATH.read_bytes()
    existing = audit.strict_json_loads(existing_bytes, source=str(RESULTS_PATH))
    legacy_summary = audit.extract_legacy_summary(SUMMARY_PATH.read_text(encoding="utf-8"))
    executed = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
    fake = _fake_p246k_result(3, 3)
    first = audit.build_results_document(
        existing_results=existing,
        existing_results_bytes=existing_bytes,
        legacy_summary=legacy_summary,
        executed_at_utc=executed,
        population=population,
        p246k_result=fake,
    )
    second = audit.build_results_document(
        existing_results=existing,
        existing_results_bytes=existing_bytes,
        legacy_summary=legacy_summary,
        executed_at_utc=executed,
        population=population,
        p246k_result=fake,
    )
    assert audit._canonical_json_bytes(first) == audit._canonical_json_bytes(second)
    assert audit.render_summary(first, legacy_summary) == audit.render_summary(second, legacy_summary)
    wiki_source = WIKI_PATH.read_text(encoding="utf-8")
    assert audit.render_wiki(first, wiki_source) == audit.render_wiki(second, wiki_source)


def _run_fake_generation(
    db_path: Path,
    results_out: Path,
    summary_out: Path,
    wiki_out: Path,
    *,
    executed: datetime,
) -> dict:
    def fake_runner(population, runtime_db_path):
        return _fake_p246k_result(
            len(population.draws),
            population.raw_count,
            db_path=str(runtime_db_path),
        )

    with patch.object(audit, "run_p246k_existing_logic", side_effect=fake_runner):
        return audit.generate(
            db_path=db_path,
            executed_at_utc=executed,
            legacy_results_path=RESULTS_PATH,
            legacy_summary_path=SUMMARY_PATH,
            wiki_source_path=WIKI_PATH,
            results_out=results_out,
            summary_out=summary_out,
            wiki_out=wiki_out,
        )


def _prepare_publication_case(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    results_out = tmp_path / "results.json"
    summary_out = tmp_path / "summary.md"
    wiki_out = tmp_path / "wiki.md"
    results_out.write_bytes(RESULTS_PATH.read_bytes())
    summary_out.write_bytes(SUMMARY_PATH.read_bytes())
    wiki_out.write_bytes(WIKI_PATH.read_bytes())
    return db_path, results_out, summary_out, wiki_out


def _assert_no_publication_residue(root: Path) -> None:
    residue = [
        path
        for path in root.iterdir()
        if path.name.endswith(".stage") or path.name.endswith(".rollback")
    ]
    assert residue == []


def test_complete_generation_is_location_independent_and_byte_deterministic(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_db = left / "canonical.db"
    right_db = right / "canonical.db"
    _create_canonical_db(left_db, count=3)
    _create_canonical_db(right_db, count=3)
    assert left_db.read_bytes() == right_db.read_bytes()

    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
    left_results = left / "results.json"
    left_summary = left / "summary.md"
    left_wiki = left / "wiki.md"
    right_results = right / "results.json"
    right_summary = right / "summary.md"
    right_wiki = right / "wiki.md"
    _run_fake_generation(left_db, left_results, left_summary, left_wiki, executed=executed)
    _run_fake_generation(right_db, right_results, right_summary, right_wiki, executed=executed)

    assert left_results.read_bytes() == right_results.read_bytes()
    assert left_summary.read_bytes() == right_summary.read_bytes()
    assert left_wiki.read_bytes() == right_wiki.read_bytes()
    audit._validate_rendered_artifacts(
        left_results.read_text(encoding="utf-8"),
        left_summary.read_text(encoding="utf-8"),
        left_wiki.read_text(encoding="utf-8"),
    )


def test_generation_serialization_failure_preserves_original_pair(tmp_path: Path):
    db_path, results_out, summary_out, wiki_out = _prepare_publication_case(tmp_path)
    original_results = results_out.read_bytes()
    original_summary = summary_out.read_bytes()
    original_wiki = wiki_out.read_bytes()
    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)

    with patch.object(audit, "render_summary", side_effect=ValueError("forced serialization")):
        with pytest.raises(ValueError, match="forced serialization"):
            _run_fake_generation(db_path, results_out, summary_out, wiki_out, executed=executed)
    assert results_out.read_bytes() == original_results
    assert summary_out.read_bytes() == original_summary
    assert wiki_out.read_bytes() == original_wiki
    _assert_no_publication_residue(tmp_path)


def test_first_final_replacement_failure_preserves_original_pair(tmp_path: Path):
    db_path, results_out, summary_out, wiki_out = _prepare_publication_case(tmp_path)
    original_results = results_out.read_bytes()
    original_summary = summary_out.read_bytes()
    original_wiki = wiki_out.read_bytes()
    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)

    with patch.object(audit, "_replace_file", side_effect=OSError("forced first replace")):
        with pytest.raises(audit.AuditProvenanceError, match="before any final"):
            _run_fake_generation(db_path, results_out, summary_out, wiki_out, executed=executed)
    assert results_out.read_bytes() == original_results
    assert summary_out.read_bytes() == original_summary
    assert wiki_out.read_bytes() == original_wiki
    _assert_no_publication_residue(tmp_path)


def test_second_final_replacement_failure_restores_pair_and_anchor(tmp_path: Path):
    db_path, results_out, summary_out, wiki_out = _prepare_publication_case(tmp_path)
    original_results = results_out.read_bytes()
    original_summary = summary_out.read_bytes()
    original_wiki = wiki_out.read_bytes()
    original_anchor = audit.strict_json_loads(
        original_results,
        source="publication rollback baseline",
    )["current_executable_audit"]["cadence_anchor"]
    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
    real_replace = audit._replace_file
    calls = 0

    def fail_second(source: Path, target: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("forced second replace")
        real_replace(source, target)

    with patch.object(audit, "_replace_file", side_effect=fail_second):
        with pytest.raises(audit.AuditProvenanceError, match="artifact set was restored"):
            _run_fake_generation(db_path, results_out, summary_out, wiki_out, executed=executed)
    assert results_out.read_bytes() == original_results
    assert summary_out.read_bytes() == original_summary
    assert wiki_out.read_bytes() == original_wiki
    assert audit.strict_json_loads(
        results_out.read_bytes(),
        source=str(results_out),
    )["current_executable_audit"][
        "cadence_anchor"
    ] == original_anchor
    _assert_no_publication_residue(tmp_path)


def test_final_cadence_json_replacement_failure_restores_all_three_surfaces(
    tmp_path: Path,
):
    db_path, results_out, summary_out, wiki_out = _prepare_publication_case(tmp_path)
    originals = {
        results_out: results_out.read_bytes(),
        summary_out: summary_out.read_bytes(),
        wiki_out: wiki_out.read_bytes(),
    }
    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
    real_replace = audit._replace_file
    calls = 0

    def fail_third(source: Path, target: Path):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("forced cadence JSON replace failure")
        real_replace(source, target)

    with patch.object(audit, "_replace_file", side_effect=fail_third):
        with pytest.raises(audit.AuditProvenanceError, match="artifact set was restored"):
            _run_fake_generation(
                db_path,
                results_out,
                summary_out,
                wiki_out,
                executed=executed,
            )
    for target, original in originals.items():
        assert target.read_bytes() == original
    _assert_no_publication_residue(tmp_path)


def test_rollback_failure_is_explicit_and_cleans_task_residue(tmp_path: Path):
    db_path, results_out, summary_out, wiki_out = _prepare_publication_case(tmp_path)
    executed = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)
    real_replace = audit._replace_file
    calls = 0

    def fail_publish_and_first_rollback(source: Path, target: Path):
        nonlocal calls
        calls += 1
        if calls in {2, 3}:
            raise OSError(f"forced replace failure {calls}")
        real_replace(source, target)

    with patch.object(audit, "_replace_file", side_effect=fail_publish_and_first_rollback):
        with pytest.raises(audit.AuditProvenanceError, match="rollback was incomplete"):
            _run_fake_generation(db_path, results_out, summary_out, wiki_out, executed=executed)
    _assert_no_publication_residue(tmp_path)


def test_committed_outputs_have_full_current_field_agreement_and_no_machine_paths():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    markdown = SUMMARY_PATH.read_text(encoding="utf-8")
    wiki = WIKI_PATH.read_text(encoding="utf-8")
    current = document["current_executable_audit"]
    provenance = current["input_provenance"]
    result = current["p246k_existing_logic_result"]
    anchor = current["cadence_anchor"]
    policy = current["cadence_policy"]
    checks = result["audit_results"]

    assert f"**Current executable audit timestamp (UTC):** {current['executed_at_utc']}" in markdown
    assert f"**Latest real executable audit:** {current['executed_at_utc']}" in wiki
    assert "Unchanged nested P246K diagnostic status (non-authoritative)" in markdown
    assert f"Logical DB identity: `{provenance['db_identity']}`" in markdown
    assert f"Canonical rows: `{provenance['selected_row_count']}`" in markdown
    assert f"Raw BIG_LOTTO rows observed: `{provenance['raw_population_count']}`" in markdown
    assert provenance["newest_selected_row"]["draw"] in markdown
    assert provenance["selected_row_stream_sha256"] in markdown
    assert current["p246k_semantic_output_sha256"] in markdown
    assert anchor["real_executable_audit_timestamp_utc"] in markdown
    assert str(anchor["canonical_draw_count"]) in markdown
    assert policy["trigger"] in markdown
    for limitation in current["p246k_existing_logic_payload_metadata"][
        "scientific_limitations"
    ]:
        assert limitation["statement"] in markdown
        assert limitation["statement"] in wiki
    disclosure = current["historical_date_conflict"]["disclosure"]
    assert disclosure in markdown
    assert disclosure in wiki
    assert "This GREEN result confirms randomness" not in markdown
    assert "This GREEN result confirms randomness" not in wiki
    assert "fair random 6/49 process" not in markdown
    assert "fair random 6/49 process" not in wiki
    for check in (
        checks["draw_sum_distribution"],
        checks["number_frequency_uniformity"],
        checks["serial_randomness"]["runs_test"],
        checks["serial_randomness"]["ljung_box_lag10"],
        checks["entropy"],
    ):
        assert check["status"] in markdown
    assert document["legacy_44_test_evidence"]["status"] in json.dumps(document)
    assert "immutable legacy evidence" in markdown.lower()
    audit._validate_rendered_artifacts(
        RESULTS_PATH.read_text(encoding="utf-8"),
        markdown,
        wiki,
    )


def test_inherited_nested_prose_cannot_become_the_authoritative_verdict():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    changed = deepcopy(document)
    nested = changed["current_executable_audit"]["p246k_existing_logic_result"]
    nested["gate_implication"] = "This GREEN result confirms randomness."
    nested["final_decision"] = "Canonical draws are a fair random 6/49 process."
    audit._validate_executable_audit_document(changed)
    legacy_summary = audit.extract_legacy_summary(SUMMARY_PATH.read_text(encoding="utf-8"))
    markdown = audit.render_summary(changed, legacy_summary)
    wiki = audit.render_wiki(changed, WIKI_PATH.read_text(encoding="utf-8"))
    assert "This GREEN result confirms randomness" not in markdown
    assert "This GREEN result confirms randomness" not in wiki
    assert "fair random 6/49 process" not in markdown
    assert "fair random 6/49 process" not in wiki
    assert "does not prove randomness" in markdown
    assert "does not prove randomness" in wiki


@pytest.mark.parametrize("surface", ["json", "markdown", "wiki"])
def test_execution_timestamp_disagreement_fails_publication_validation(surface: str):
    results_text = RESULTS_PATH.read_text(encoding="utf-8")
    summary_text = SUMMARY_PATH.read_text(encoding="utf-8")
    wiki_text = WIKI_PATH.read_text(encoding="utf-8")
    document = audit.strict_json_loads(results_text, source=str(RESULTS_PATH))
    current_timestamp = document["current_executable_audit"]["executed_at_utc"]
    disagreement = "2099-01-01T00:00:00Z"
    if surface == "json":
        changed = deepcopy(document)
        current = changed["current_executable_audit"]
        current["executed_at_utc"] = disagreement
        current["cadence_anchor"]["real_executable_audit_timestamp_utc"] = disagreement
        results_text = json.dumps(changed, ensure_ascii=False, indent=2)
    elif surface == "markdown":
        summary_text = summary_text.replace(current_timestamp, disagreement, 1)
    else:
        wiki_text = wiki_text.replace(current_timestamp, disagreement, 1)
    with pytest.raises(audit.AuditProvenanceError):
        audit._validate_rendered_artifacts(results_text, summary_text, wiki_text)


def test_summary_and_wiki_state_non_gating_reattestation_contract():
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    wiki = (REPO_ROOT / "wiki" / "system" / "randomness_final_verdict.md").read_text(
        encoding="utf-8"
    )
    assert "Current executable audit timestamp (UTC)" in summary
    assert "not historical 44-test reproduction" in summary
    assert "Timestamp-only re-attestation is non-gating" in summary
    assert "P246K controls" in summary
    assert "timestamp-only re-attestation" in wiki.lower()
    assert "unreproducible from committed source" in wiki.lower()
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
