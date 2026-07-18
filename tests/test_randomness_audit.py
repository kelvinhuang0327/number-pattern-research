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
