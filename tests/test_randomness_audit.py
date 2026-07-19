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
