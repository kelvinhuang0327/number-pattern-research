from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from scripts import randomness_audit as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"

EXPECTED_P238B_SOURCE_SHA256 = "6eee50f61101b016737863eb426da6a0e893bc2d3f38387aa232ac1b4b86dcd8"
EXPECTED_P246K_SOURCE_SHA256 = "3ddd1453ae562c0ac6bec1ada0bc6c2ca3339012ec8a2a26dc233bc1fac83157"
EXPECTED_CURRENT_INPUT_SHA256 = "7d48306f31746ec3ea8976b4d0b88f2577decd52191391ee5c059f2fd4588a09"
EXPECTED_CURRENT_P246K_SEMANTIC_SHA256 = "48f72f61764e09de20702a853d124930eb3275ce49eb7e9b4b9e26e84f5d9dd1"


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


def _fake_p246k_result(population_count: int, raw_count: int) -> dict:
    return {
        "classification": "P246K_FAKE_TEST_RESULT",
        "raw_population_count": raw_count,
        "canonical_population_count": population_count,
        "excluded_add_on_count": raw_count - population_count,
        "exclusion_rules_verified": {"all_exclusions_verified": True},
        "audit_methods": {"existing": "unchanged"},
        "audit_results": {
            "draw_sum_distribution": {"status": "GREEN"},
            "number_frequency_uniformity": {"status": "GREEN"},
            "serial_randomness": {
                "runs_test": {"status": "GREEN"},
                "ljung_box_lag10": {"status": "GREEN"},
            },
            "entropy": {"status": "GREEN"},
            "summary": {"total_tests": 5, "green": 5, "yellow": 0},
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


def test_population_loader_records_exact_sql_boundaries_and_hash(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    loaded = audit.load_canonical_big_lotto_population(db_path)
    assert len(loaded.draws) == 3
    assert loaded.raw_count == 3
    assert loaded.draws[0]["draw"] == "115000003"
    assert loaded.draws[-1]["draw"] == "115000001"
    provenance = loaded.provenance
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


def test_legacy_json_payload_is_immutable_and_unreproducible():
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
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
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    legacy_summary = audit.extract_legacy_summary(summary)
    assert audit._sha256_bytes(legacy_summary.encode("utf-8")) == document[
        "legacy_44_test_evidence"
    ]["original_summary_file_sha256"]
    assert "**Total confirmatory tests:** 44" in legacy_summary
    assert "**Run timestamp:** 2026-06-02T06:57:02.982982" in legacy_summary


def test_current_committed_audit_is_existing_p246k_logic_only():
    document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
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
    assert "not current row-family provenance" in current["p246k_static_narrative_caveat"]
    assert current["input_provenance"]["selected_row_stream_sha256"] == EXPECTED_CURRENT_INPUT_SHA256
    assert current["p246k_semantic_output_sha256"] == EXPECTED_CURRENT_P246K_SEMANTIC_SHA256
    p246k = current["p246k_existing_logic_result"]
    assert p246k["canonical_population_count"] == 2125
    assert p246k["audit_results"]["summary"] == {
        "total_tests": 5,
        "green": 5,
        "yellow": 0,
        "overall_status": "GREEN",
    }


def test_results_build_and_summary_render_are_deterministic(tmp_path: Path):
    db_path = tmp_path / "canonical.db"
    _create_canonical_db(db_path, count=3)
    population = audit.load_canonical_big_lotto_population(db_path)
    existing_bytes = RESULTS_PATH.read_bytes()
    existing = json.loads(existing_bytes)
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
