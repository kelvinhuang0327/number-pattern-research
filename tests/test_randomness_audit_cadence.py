<<<<<<< HEAD
"""Fail-closed cadence contract for the executable randomness audit."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
=======
"""Cadence contract for the real existing-logic randomness audit.

The gate is anchored only to a real executable audit and to an independent
canonical DB population.  Human or timestamp-only re-attestation is legacy
metadata and resets neither the 14-day nor the 50-new-draw trigger.
"""
from __future__ import annotations

from copy import deepcopy
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

<<<<<<< HEAD
from scripts.randomness_audit import AuditContractError, _load_json


REPO = Path(__file__).resolve().parent.parent
RESULTS_FILE = REPO / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_FILE = REPO / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_FILE = REPO / "wiki" / "system" / "randomness_final_verdict.md"
CADENCE_MAX_CALENDAR_DAYS = 14
CADENCE_MAX_NEW_DRAWS = 50
EXPECTED_GAMES = {"power_lotto", "big_lotto", "daily_539"}
RUN_LINE = re.compile(r"^\*\*Run timestamp:\*\*\s+(.+)$", re.MULTILINE)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_results(path: Path = RESULTS_FILE) -> dict[str, Any]:
    return _load_json(path)


def test_ambiguous_results_fail_before_cadence_callback(tmp_path):
    source = tmp_path / "ambiguous-cadence-results.json"
    source.write_text('{"cadence":{"anchor":"run_timestamp","anchor":"other"}}', encoding="utf-8")
    callbacks = []

    def evaluate_cadence(data):
        callbacks.append(data)

    with pytest.raises(AuditContractError, match="duplicate JSON object key 'anchor'"):
        evaluate_cadence(_load_results(source))

    assert callbacks == []


def _parse_run_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("run_timestamp must use explicit UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("run_timestamp is malformed") from exc
    return parsed.astimezone(timezone.utc)


def _check_calendar(run_timestamp: datetime, now: datetime) -> tuple[bool, str]:
    if run_timestamp.tzinfo is None or now.tzinfo is None:
        raise ValueError("cadence timestamps must be timezone-aware")
    run_utc = run_timestamp.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    if run_utc > now_utc:
        return True, "run_timestamp is in the future"
    age = now_utc - run_utc
    stale = age > timedelta(days=CADENCE_MAX_CALENDAR_DAYS)
    return stale, f"audit age is {age.total_seconds() / 86400:.2f} days"


def _validate_artifact(data: Mapping[str, Any]) -> None:
    required = {
        "run_timestamp",
        "audit_version",
        "audit_commit",
        "data_sources",
        "simulations",
        "seed",
        "alpha",
        "confirmatory_test_count",
        "multiple_testing_methods",
        "reanalysis_performed",
        "new_draws_analyzed",
        "final_verdict",
        "strategy_implication",
        "validation_results",
        "dataset_identity",
    }
    assert not (required - set(data)), f"missing required audit fields: {sorted(required - set(data))}"
    _parse_run_timestamp(data["run_timestamp"])
    assert data["audit_execution"]["run_timestamp"] == data["run_timestamp"]
    assert data["audit_execution"]["timezone"] == "UTC"
    assert data["reanalysis_performed"] is True
    assert data["new_draws_analyzed"] is True
    assert "re_attestation_type" not in data
    assert data["confirmatory_test_count"] == 44
    assert set(data["multiple_testing_methods"]) == {"bonferroni", "bh_fdr"}
    sources = data["data_sources"]
    assert {source["game"] for source in sources} == EXPECTED_GAMES
    for source in sources:
        assert isinstance(source["row_count"], int) and source["row_count"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", source["digest"])
        assert source["date_min"] <= source["date_max"]
        assert source["duplicate_draw_ids"] == 0
        assert source["duplicate_full_records"] == 0
        assert source["invalid_repeated_numbers_inside_draw"] == 0
    projection = [
        {
            key: source[key]
            for key in ("game", "source", "row_count", "date_min", "date_max", "digest")
        }
        for source in sources
    ]
    assert data["dataset_identity"]["combined_selected_data_sha256"] == _sha256(
        _canonical_json_bytes(projection)
    )
    assert all(result["status"] == "PASS" for result in data["validation_results"].values())
    confirmatory = [test for test in data["tests"] if test["confirmatory"]]
    exploratory = [test for test in data["tests"] if not test["confirmatory"]]
    assert len(confirmatory) == 44
    assert len(exploratory) == 17
    assert all(test["correction_family"] is not None for test in confirmatory)
    assert all(test["correction_family"] is None for test in exploratory)
    assert all(test["p_bonferroni"] is None and test["q_bh_fdr"] is None for test in exploratory)


def _candidate_db() -> Path | None:
    explicit = os.environ.get("LOTTERY_CANONICAL_DB_PATH")
    if explicit:
        return Path(explicit)
    candidate = REPO / "lottery_api" / "data" / "lottery_v2.db"
    return candidate if candidate.is_file() else None


def _normalize_date(value: str) -> str:
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"bad DB date: {value!r}")


def _current_streams(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    wal = Path(f"{db_path}-wal")
    assert not wal.exists() or wal.stat().st_size == 0
    connection = sqlite3.connect(
        f"file:{db_path.resolve()}?mode=ro&immutable=1&cache=private", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    queries = {
        "power_lotto": (
            "SELECT draw,date,numbers,special FROM draws WHERE lottery_type='POWER_LOTTO' "
            "ORDER BY date(replace(date,'/','-')),CAST(draw AS INTEGER),draw"
        ),
        "big_lotto": (
            "SELECT draw,date,numbers,special FROM draws_big_lotto_canonical_main "
            "ORDER BY date(replace(date,'/','-')),CAST(draw AS INTEGER),draw"
        ),
        "daily_539": (
            "SELECT draw,date,numbers,special FROM draws WHERE lottery_type='DAILY_539' "
            "ORDER BY date(replace(date,'/','-')),CAST(draw AS INTEGER),draw"
        ),
    }
    try:
        result = {}
        for game, query in queries.items():
            rows = []
            for row in connection.execute(query):
                special = None if game == "daily_539" else int(row["special"])
                rows.append(
                    {
                        "date": _normalize_date(row["date"]),
                        "draw": str(row["draw"]),
                        "numbers": json.loads(row["numbers"]),
                        "special": special,
                    }
                )
            result[game] = rows
        return result
    finally:
        connection.close()


def _stream_digest(rows: list[dict[str, Any]]) -> str:
    return _sha256(b"".join(_canonical_json_bytes(row) + b"\n" for row in rows))


class TestTimestampSemantics:
    def test_valid_utc_timestamp(self):
        parsed = _parse_run_timestamp("2026-07-18T12:00:00.000000Z")
        assert parsed.tzinfo == timezone.utc

    @pytest.mark.parametrize("value", [None, "", "not-a-date", "2026-07-18T12:00:00"])
    def test_missing_malformed_or_naive_timestamp_fails(self, value):
        with pytest.raises(ValueError):
            _parse_run_timestamp(value)

    def test_future_timestamp_fails_closed(self):
        now = datetime(2026, 7, 18, tzinfo=timezone.utc)
        stale, reason = _check_calendar(now + timedelta(microseconds=1), now)
        assert stale and "future" in reason

    def test_exactly_fourteen_days_is_current(self):
        now = datetime(2026, 7, 18, tzinfo=timezone.utc)
        stale, _ = _check_calendar(now - timedelta(days=14), now)
        assert not stale

    def test_over_fourteen_days_is_stale(self):
        now = datetime(2026, 7, 18, tzinfo=timezone.utc)
        stale, _ = _check_calendar(now - timedelta(days=14, microseconds=1), now)
        assert stale


class TestStaticDatasetBinding:
    def test_results_and_summary_exist(self):
        assert RESULTS_FILE.is_file()
        assert SUMMARY_FILE.is_file()

    def test_machine_readable_contract(self):
        _validate_artifact(_load_results())

    def test_summary_timestamp_matches_json(self):
        data = _load_results()
        match = RUN_LINE.search(SUMMARY_FILE.read_text(encoding="utf-8"))
        assert match and match.group(1).strip() == data["run_timestamp"]

    def test_re_attestation_cannot_reset_cadence(self):
        data = _load_results()
        assert data["cadence"]["anchor"] == "run_timestamp"
        assert data["cadence"]["re_attestation_resets_cadence"] is False
        assert "re_attestation_type" not in data

    def test_policy_and_test_constants_agree(self):
        text = WIKI_FILE.read_text(encoding="utf-8")
        assert "14 days" in text
        assert "50 draws" in text
        assert "run_timestamp" in text

    def test_real_audit_is_not_stale_by_calendar(self):
        data = _load_results()
        stale, reason = _check_calendar(
            _parse_run_timestamp(data["run_timestamp"]), datetime.now(timezone.utc)
        )
        assert not stale, f"CADENCE GATE FAILURE: {reason}"

    def test_timestamp_without_dataset_evidence_fails_closed(self):
        data = _load_results()
        data["data_sources"] = []
        with pytest.raises(AssertionError):
            _validate_artifact(data)

    def test_human_only_identity_is_historical_provenance_only(self):
        data = _load_results()
        history = data["provenance"]["historical_evidence"]
        assert history["artifact_re_attestation_type"] == "HUMAN_REVIEW_OF_UNCHANGED_COMMITTED_EVIDENCE"
        assert data["reanalysis_performed"] is True


class TestLiveDatasetCadence:
    def test_current_dataset_preserves_audited_stream_and_draw_threshold(self):
        db_path = _candidate_db()
        if db_path is None:
            pytest.skip("canonical DB unavailable; embedded dataset-binding checks remain mandatory")
        data = _load_results()
        streams = _current_streams(db_path)
        sources = {source["game"]: source for source in data["data_sources"]}
        new_rows = 0
        for game, source in sources.items():
            rows = streams[game]
            baseline_count = source["row_count"]
            assert len(rows) >= baseline_count
            assert _stream_digest(rows[:baseline_count]) == source["digest"], (
                f"{game} audited history was changed or reordered"
            )
            new_rows += len(rows) - baseline_count
        assert new_rows < CADENCE_MAX_NEW_DRAWS, (
            f"CADENCE GATE FAILURE: {new_rows} new canonical draws since audit"
        )
=======
from scripts import randomness_audit as audit


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_results.json"
SUMMARY_PATH = REPO_ROOT / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_PATH = REPO_ROOT / "wiki" / "system" / "randomness_final_verdict.md"


def _draws(count: int) -> list[dict]:
    return [
        {
            "draw": f"115{index:06d}",
            "date": f"2026-01-{((index - 1) % 28) + 1:02d}",
            "numbers": [1, 8, 15, 22, 29, 36],
            "special": 7,
        }
        for index in range(count, 0, -1)
    ]


def _population(draws: list[dict], *, raw_count: int = None) -> audit.PopulationLoad:
    if raw_count is None:
        raw_count = len(draws)
    stream_hash = audit._sha256_bytes(audit._row_stream_bytes(draws))
    provenance = {
        "db_identity": audit.LOGICAL_DB_IDENTITY,
        "db_open_mode": "sqlite_uri_mode_ro",
        "sqlite_immutable": True,
        "sqlite_cache": "private",
        "wal_precondition": "empty_or_absent",
        "pragma_query_only": True,
        "selected_population": "BIG_LOTTO/CANONICAL_MAIN_DRAW",
        "canonical_view": audit.CANONICAL_VIEW_NAME,
        "sql": {
            "canonical_population": audit.CANONICAL_POPULATION_SQL,
            "raw_population_count": audit.RAW_POPULATION_COUNT_SQL,
            "raw_population_count_params": list(audit.RAW_POPULATION_COUNT_PARAMS),
        },
        "raw_population_count": raw_count,
        "selected_row_count": len(draws),
        "selected_row_stream_sha256": stream_hash,
        "selected_row_stream_serialization": audit.ROW_STREAM_SERIALIZATION,
        "oldest_selected_row": {
            "draw": draws[-1]["draw"],
            "date": draws[-1]["date"],
        },
        "newest_selected_row": {
            "draw": draws[0]["draw"],
            "date": draws[0]["date"],
        },
        "selected_date_min": draws[-1]["date"],
        "selected_date_max": draws[0]["date"],
    }
    return audit.PopulationLoad(draws=draws, raw_count=raw_count, provenance=provenance)


def _document(audit_time: datetime, baseline: audit.PopulationLoad) -> dict:
    p246k_result = {
        "schema_version": "1.0",
        "task_id": "P246K",
        "classification": (
            "P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE"
        ),
        "db_identity": audit.LOGICAL_DB_IDENTITY,
        "db_read": True,
        "db_read_only": True,
        "db_write_performed": False,
        "input_population": "CANONICAL_MAIN_DRAW",
        "raw_population_count": baseline.raw_count,
        "canonical_population_count": len(baseline.draws),
        "excluded_add_on_count": baseline.raw_count - len(baseline.draws),
        "exclusion_rules_verified": {
            "canonical_count": len(baseline.draws),
            "raw_count": baseline.raw_count,
            "excluded_count": baseline.raw_count - len(baseline.draws),
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
                "n": len(baseline.draws),
                "ks_stat": 0.01,
                "ks_p": 0.5,
                "status": "GREEN",
            },
            "number_frequency_uniformity": {
                "n_draws": len(baseline.draws),
                "n_numbers": len(baseline.draws) * 6,
                "max_frequency": len(baseline.draws),
                "min_frequency": max(1, len(baseline.draws) - 1),
                "chi2_stat": 1.0,
                "chi2_p": 0.5,
                "status": "GREEN",
            },
            "serial_randomness": {
                "runs_test": {"z_stat": 0.0, "p_value": 0.5, "status": "GREEN"},
                "ljung_box_lag10": {
                    "stat": 1.0,
                    "p_value": 0.5,
                    "status": "GREEN",
                },
            },
            "entropy": {"normalized_entropy": 0.999, "status": "GREEN"},
            "per_position": {"pos_1": {"mean": 1.0}},
            "era_stability": {"2026": {"n": len(baseline.draws), "mean": 100.0}},
            "summary": {
                "total_tests": 5,
                "green": 5,
                "yellow": 0,
                "overall_status": "GREEN",
            },
        },
    }
    semantic_hash = audit._sha256_bytes(
        audit._canonical_json_bytes(audit._p246k_semantic_payload(p246k_result))
    )
    executed = audit._format_utc(audit_time)
    return {
        "artifact_schema_version": audit.SCHEMA_VERSION,
        "re_attestation_timestamp": "2099-01-01T00:00:00Z",
        "current_executable_audit": {
            "task_id": audit.TASK_ID,
            "audit_type": audit.AUDIT_TYPE,
            "historical_44_test_reproduction": False,
            "executed_at_utc": executed,
            "scope": {
                "lottery_type": "BIG_LOTTO",
                "population": "CANONICAL_MAIN_DRAW",
                "statistical_controller": "P246K",
            },
            "implementation_sources": audit._source_implementations(),
            "input_provenance": baseline.provenance,
            "p246k_existing_logic_payload_metadata": audit._p246k_payload_metadata(
                p246k_result
            ),
            "p246k_existing_logic_result": p246k_result,
            "p246k_semantic_output_sha256": semantic_hash,
            "current_authoritative_conclusion": audit._bounded_current_conclusion(
                p246k_result
            ),
            "historical_date_conflict": dict(audit.HISTORICAL_DATE_CONFLICT),
            "p246k_result_retained_unchanged": True,
            "p246k_nonsemantic_location_sanitized": True,
            "p246k_static_narrative_caveat": "unchanged nested source prose is non-authoritative",
            "cadence_anchor": {
                "real_executable_audit_timestamp_utc": executed,
                "canonical_draw_count": len(baseline.draws),
                "selected_row_stream_sha256": baseline.provenance[
                    "selected_row_stream_sha256"
                ],
                "oldest_selected_row": baseline.provenance["oldest_selected_row"],
                "newest_selected_row": baseline.provenance["newest_selected_row"],
            },
            "cadence_policy": {
                "max_calendar_days": audit.CADENCE_MAX_CALENDAR_DAYS,
                "max_new_canonical_draws": audit.CADENCE_MAX_NEW_DRAWS,
                "trigger": "whichever_occurs_first",
                "timestamp_only_re_attestation_is_gating": False,
            },
            "orchestration_additions_only": [
                "provenance",
                "cadence",
                "publication_containment",
            ],
            "new_statistical_procedure_introduced": False,
            "combined_p238b_p246k_verdict": False,
            "db_write_performed": False,
        },
    }


def _rehash_p246k_semantic(document: dict) -> None:
    current = document["current_executable_audit"]
    current["p246k_semantic_output_sha256"] = audit._sha256_bytes(
        audit._canonical_json_bytes(
            audit._p246k_semantic_payload(current["p246k_existing_logic_result"])
        )
    )


@pytest.fixture
def baseline() -> audit.PopulationLoad:
    return _population(_draws(100))


def test_policy_constants_are_owner_approved_values():
    assert audit.CADENCE_MAX_CALENDAR_DAYS == 14
    assert audit.CADENCE_MAX_NEW_DRAWS == 50


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-18T08:00:00Z", datetime(2026, 7, 18, 8, tzinfo=timezone.utc)),
        ("2026-07-18T16:00:00+08:00", datetime(2026, 7, 18, 8, tzinfo=timezone.utc)),
    ],
)
def test_parse_utc_timestamp_normalizes_offsets(raw: str, expected: datetime):
    assert audit._parse_utc_timestamp(raw, field_name="test") == expected


@pytest.mark.parametrize("raw", ["", "not-a-date", "2026-07-18T08:00:00"])
def test_parse_utc_timestamp_fails_closed_on_malformed_or_naive(raw: str):
    with pytest.raises(audit.AuditProvenanceError):
        audit._parse_utc_timestamp(raw, field_name="test")


def test_calendar_trigger_not_due_one_second_before_14_days(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14) - timedelta(seconds=1),
    )
    assert result["status"] == "CURRENT"
    assert result["calendar_due"] is False


def test_calendar_trigger_due_exactly_at_14_days(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14),
    )
    assert result["status"] == "DUE"
    assert result["trigger"] == "CALENDAR"
    assert result["calendar_due"] is True


def test_draw_trigger_not_due_at_49_new_canonical_draws(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    current = _population(_draws(149))
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["status"] == "CURRENT"
    assert result["new_canonical_draws"] == 49
    assert result["draw_due"] is False


def test_raw_growth_alone_cannot_satisfy_draw_trigger():
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    baseline = _population(_draws(100), raw_count=1000)
    current = _population(_draws(100), raw_count=1050)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["new_canonical_draws"] == 0
    assert result["draw_due"] is False


def test_raw_count_cannot_replace_canonical_count_in_49_draw_boundary():
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    baseline = _population(_draws(100), raw_count=1000)
    current = _population(_draws(149), raw_count=9999)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["new_canonical_draws"] == 49
    assert result["draw_due"] is False


def test_draw_trigger_due_at_50_new_canonical_draws(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    current = _population(_draws(150))
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        current,
        audit_time + timedelta(days=1),
    )
    assert result["status"] == "DUE"
    assert result["trigger"] == "DRAW_COUNT"
    assert result["new_canonical_draws"] == 50


def test_whichever_trigger_occurs_first_is_enough(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    by_draw = audit.evaluate_cadence(
        _document(audit_time, baseline),
        _population(_draws(150)),
        audit_time + timedelta(days=2),
    )
    by_time = audit.evaluate_cadence(
        _document(audit_time, baseline),
        baseline,
        audit_time + timedelta(days=14),
    )
    assert by_draw["due"] is True and by_draw["trigger"] == "DRAW_COUNT"
    assert by_time["due"] is True and by_time["trigger"] == "CALENDAR"


def test_both_triggers_are_reported_when_both_due(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = audit.evaluate_cadence(
        _document(audit_time, baseline),
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    assert result["trigger"] == "CALENDAR_AND_DRAW_COUNT"


def test_timestamp_only_reattestation_resets_neither_trigger(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    first = audit.evaluate_cadence(
        document,
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    changed = deepcopy(document)
    changed["re_attestation_timestamp"] = "2200-12-31T23:59:59Z"
    second = audit.evaluate_cadence(
        changed,
        _population(_draws(150)),
        audit_time + timedelta(days=14),
    )
    assert first == second
    assert second["due"] is True


def test_generated_output_cannot_supply_current_draw_count(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    document["current_draw_count"] = 999999
    result = audit.evaluate_cadence(
        document,
        _population(_draws(149)),
        audit_time + timedelta(days=1),
    )
    assert result["new_canonical_draws"] == 49
    assert result["current_draw_source"] == "independent_read_only_canonical_DB_query"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document.pop("current_executable_audit"),
        lambda document: document["current_executable_audit"].pop("cadence_anchor"),
        lambda document: document["current_executable_audit"].pop("input_provenance"),
        lambda document: document["current_executable_audit"]["cadence_anchor"].update(
            {"canonical_draw_count": "100"}
        ),
        lambda document: document["current_executable_audit"]["cadence_anchor"].update(
            {"selected_row_stream_sha256": "bad"}
        ),
        lambda document: document["current_executable_audit"]["cadence_policy"].update(
            {"timestamp_only_re_attestation_is_gating": True}
        ),
    ],
)
def test_missing_or_malformed_provenance_fails_closed(baseline, mutation):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    mutation(document)
    with pytest.raises(audit.AuditProvenanceError):
        audit.evaluate_cadence(document, baseline, audit_time + timedelta(days=1))


@pytest.mark.parametrize(
    ("r3_mutant", "mutation"),
    [
        (
            "empty exclusion_rules_verified",
            lambda document: document["current_executable_audit"][
                "p246k_existing_logic_result"
            ].update({"exclusion_rules_verified": {}}),
        ),
        (
            "empty audit_methods",
            lambda document: document["current_executable_audit"][
                "p246k_existing_logic_result"
            ].update({"audit_methods": {}}),
        ),
        (
            "missing oldest_selected_row",
            lambda document: document["current_executable_audit"][
                "input_provenance"
            ].pop("oldest_selected_row"),
        ),
        (
            "missing raw_population_count_params",
            lambda document: document["current_executable_audit"]["input_provenance"][
                "sql"
            ].pop("raw_population_count_params"),
        ),
    ],
)
def test_exact_r3_incomplete_green_mutants_fail_closed(
    baseline,
    r3_mutant,
    mutation,
):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    mutation(document)
    _rehash_p246k_semantic(document)
    assert r3_mutant in {
        "empty exclusion_rules_verified",
        "empty audit_methods",
        "missing oldest_selected_row",
        "missing raw_population_count_params",
    }
    with pytest.raises(audit.AuditProvenanceError):
        audit.evaluate_cadence(document, baseline, audit_time + timedelta(days=1))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document["current_executable_audit"].update(
            {"executed_at_utc": ""}
        ),
        lambda document: document["current_executable_audit"].update(
            {"implementation_sources": []}
        ),
        lambda document: document["current_executable_audit"].update({"scope": {}}),
        lambda document: document["current_executable_audit"][
            "p246k_existing_logic_payload_metadata"
        ].update({"scientific_limitations": []}),
        lambda document: document["current_executable_audit"].update(
            {"current_authoritative_conclusion": {}}
        ),
        lambda document: document["current_executable_audit"].update(
            {"historical_date_conflict": {}}
        ),
        lambda document: document["current_executable_audit"]["input_provenance"][
            "sql"
        ].update({"raw_population_count_params": []}),
        lambda document: document["current_executable_audit"]["input_provenance"].update(
            {"oldest_selected_row": None}
        ),
    ],
)
def test_null_empty_or_contentless_required_provenance_fails_closed(
    baseline,
    mutation,
):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    mutation(document)
    with pytest.raises(audit.AuditProvenanceError):
        audit.evaluate_cadence(document, baseline, audit_time + timedelta(days=1))


@pytest.mark.parametrize(
    ("case", "mutation"),
    [
        ("wrong schema", lambda document: document.update({"artifact_schema_version": "1.0"})),
        (
            "wrong task",
            lambda document: document["current_executable_audit"].update(
                {"task_id": "P246K"}
            ),
        ),
        (
            "wrong type",
            lambda document: document["current_executable_audit"].update(
                {"audit_type": "HUMAN_RE_ATTESTATION"}
            ),
        ),
        (
            "wrong lottery",
            lambda document: document["current_executable_audit"]["scope"].update(
                {"lottery_type": "POWER_LOTTO"}
            ),
        ),
        (
            "noncanonical scope",
            lambda document: document["current_executable_audit"]["scope"].update(
                {"population": "RAW_MIXED"}
            ),
        ),
        (
            "incomplete result",
            lambda document: document["current_executable_audit"].pop(
                "p246k_existing_logic_result"
            ),
        ),
        (
            "missing check",
            lambda document: document["current_executable_audit"][
                "p246k_existing_logic_result"
            ]["audit_results"].pop("entropy"),
        ),
        (
            "non-success execution",
            lambda document: document["current_executable_audit"][
                "p246k_existing_logic_result"
            ].update({"db_read": False}),
        ),
        (
            "timestamp mismatch",
            lambda document: document["current_executable_audit"]["cadence_anchor"].update(
                {"real_executable_audit_timestamp_utc": "2026-07-01T00:00:01Z"}
            ),
        ),
        (
            "missing semantic hash",
            lambda document: document["current_executable_audit"].pop(
                "p246k_semantic_output_sha256"
            ),
        ),
        (
            "wrong implementation source hash",
            lambda document: document["current_executable_audit"][
                "implementation_sources"
            ][0].update({"source_sha256": "0" * 64}),
        ),
        (
            "missing row-stream hash",
            lambda document: document["current_executable_audit"]["input_provenance"].pop(
                "selected_row_stream_sha256"
            ),
        ),
        (
            "legacy substitution",
            lambda document: document.update(
                {"current_executable_audit": {"run_timestamp": document["re_attestation_timestamp"]}}
            ),
        ),
        (
            "reattestation substitution",
            lambda document: document["current_executable_audit"].update(
                {
                    "cadence_anchor": {
                        "real_executable_audit_timestamp_utc": document[
                            "re_attestation_timestamp"
                        ]
                    }
                }
            ),
        ),
    ],
)
def test_incompatible_executable_audit_anchor_fails_closed(baseline, case, mutation):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(audit_time, baseline)
    mutation(document)
    assert case
    with pytest.raises(audit.AuditProvenanceError):
        audit.evaluate_cadence(document, baseline, audit_time + timedelta(days=1))


def test_changed_historical_row_stream_fails_closed(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    changed_draws = deepcopy(baseline.draws)
    changed_draws[-1]["numbers"] = [2, 9, 16, 23, 30, 37]
    changed = _population(changed_draws)
    with pytest.raises(audit.AuditProvenanceError, match="does not preserve"):
        audit.evaluate_cadence(
            _document(audit_time, baseline),
            changed,
            audit_time + timedelta(days=1),
        )


def test_smaller_current_population_fails_closed(baseline):
    audit_time = datetime(2026, 7, 1, tzinfo=timezone.utc)
    with pytest.raises(audit.AuditProvenanceError, match="smaller"):
        audit.evaluate_cadence(
            _document(audit_time, baseline),
            _population(_draws(99)),
            audit_time + timedelta(days=1),
        )


@pytest.mark.parametrize(
    "future_delta",
    [timedelta(microseconds=1), timedelta(seconds=1), timedelta(hours=25)],
)
def test_every_future_real_audit_timestamp_fails_closed(baseline, future_delta):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(now + future_delta, baseline)
    with pytest.raises(audit.AuditProvenanceError, match="future"):
        audit.evaluate_cadence(document, baseline, now)


@pytest.mark.parametrize("historical_delta", [timedelta(0), timedelta(seconds=1)])
def test_equal_or_past_real_audit_timestamp_remains_valid(baseline, historical_delta):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    document = _document(now - historical_delta, baseline)
    result = audit.evaluate_cadence(document, baseline, now)
    assert result["status"] == "CURRENT"
    assert result["elapsed_seconds"] == historical_delta.total_seconds()


def test_committed_artifact_anchors_to_real_executable_audit():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    audit._validate_executable_audit_document(document)
    current = document["current_executable_audit"]
    anchor = current["cadence_anchor"]
    provenance = current["input_provenance"]
    assert anchor["real_executable_audit_timestamp_utc"] == current["executed_at_utc"]
    assert anchor["canonical_draw_count"] == provenance["selected_row_count"]
    assert anchor["selected_row_stream_sha256"] == provenance["selected_row_stream_sha256"]
    assert current["cadence_policy"] == {
        "max_calendar_days": 14,
        "max_new_canonical_draws": 50,
        "trigger": "whichever_occurs_first",
        "timestamp_only_re_attestation_is_gating": False,
    }


def test_committed_real_audit_calendar_gate_is_current():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    timestamp = document["current_executable_audit"]["cadence_anchor"][
        "real_executable_audit_timestamp_utc"
    ]
    audit_time = audit._parse_utc_timestamp(
        timestamp,
        field_name="real_executable_audit_timestamp_utc",
    )
    age = datetime.now(timezone.utc) - audit_time
    assert age < timedelta(days=14), (
        f"real executable randomness audit is due by calendar cadence: age={age}"
    )


def test_summary_timestamp_matches_committed_cadence_anchor():
    document = audit.strict_json_loads(RESULTS_PATH.read_bytes(), source=str(RESULTS_PATH))
    summary = SUMMARY_PATH.read_text(encoding="utf-8")
    expected = document["current_executable_audit"]["executed_at_utc"]
    assert f"**Current executable audit timestamp (UTC):** {expected}" in summary


def test_wiki_policy_routes_to_real_execution_and_both_triggers():
    wiki = WIKI_PATH.read_text(encoding="utf-8")
    lowered = wiki.lower()
    assert "14 calendar days" in lowered
    assert "50 new canonical" in lowered
    assert "whichever occurs first" in lowered
    assert "timestamp-only re-attestation" in lowered
    assert "every future timestamp fails closed" in lowered
    assert "incompatible schema" in lowered
    assert audit.LOGICAL_DB_IDENTITY in wiki
    assert "scripts/randomness_audit.py" in wiki
    assert "P246K" in wiki
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
