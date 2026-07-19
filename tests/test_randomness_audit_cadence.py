"""Fail-closed cadence contract for the executable randomness audit."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest


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
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


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
