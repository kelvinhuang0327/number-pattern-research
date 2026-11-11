"""Focused offline tests for the P271 official result/status manifest."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import _p271_official_result_status_manifest_v1 as p271


RETRIEVED_AT = "2026-07-13T03:00:00Z"


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_urlopen(*args, **kwargs):
        raise AssertionError("P271 tests must never call the network")

    monkeypatch.setattr(p271.urllib.request, "urlopen", forbidden_urlopen)


def official_payload(
    spec: dict,
    *,
    detailed_state: str = "Final",
    status_code: str = "F",
    abstract_state: str = "Final",
    away_score: int = 3,
    home_score: int = 2,
    line_away_score: int | None = None,
    line_home_score: int | None = None,
    reason: str | None = None,
    result_available_at: str | None = None,
    doubleheader: str = "N",
    game_number: int = 1,
) -> dict:
    if line_away_score is None:
        line_away_score = away_score
    if line_home_score is None:
        line_home_score = home_score
    status = {
        "abstractGameState": abstract_state,
        "codedGameState": status_code,
        "detailedState": detailed_state,
        "statusCode": status_code,
    }
    if reason is not None:
        status["reason"] = reason
    if result_available_at is not None:
        status["resultAvailableAtUtc"] = result_available_at
    return {
        "gamePk": spec["game_pk"],
        "metaData": {"timeStamp": "20260713_030000"},
        "gameData": {
            "game": {
                "pk": spec["game_pk"],
                "doubleHeader": doubleheader,
                "gameNumber": game_number,
            },
            "datetime": {
                "dateTime": f"{spec['expected_date']}T23:07:00Z",
                "officialDate": spec["expected_date"],
                "originalDate": spec["expected_date"],
            },
            "status": status,
            "teams": {
                "away": {"abbreviation": spec["away_team"], "score": away_score},
                "home": {"abbreviation": spec["home_team"], "score": home_score},
            },
        },
        "liveData": {
            "linescore": {
                "teams": {
                    "away": {"runs": line_away_score},
                    "home": {"runs": line_home_score},
                }
            }
        },
    }


def source_entry(spec: dict, payload: dict) -> dict:
    raw = p271.canonical_json_bytes(payload)
    return {
        "game_id": spec["game_id"],
        "official_source_identifier": p271.OFFICIAL_SOURCE_IDENTIFIER,
        "official_endpoint_action_identifier": p271.ENDPOINT_ACTION_IDENTIFIER,
        "request_parameters": {"gamePk": spec["game_pk"]},
        "http_status": 200,
        "content_type": "application/json;charset=UTF-8",
        "source_retrieved_at_utc": RETRIEVED_AT,
        "relative_raw_path": f"raw/{spec['game_id']}.feed.live.json",
        "raw_sha256": p271.sha256_bytes(raw),
        "retrieval_outcome": "SUCCESS",
        "error_reason": None,
        "attempt_count": 1,
    }


def write_offline_fixture(output_root: Path) -> dict:
    raw_dir = output_root / "raw"
    raw_dir.mkdir(parents=True)
    entries = []
    for spec in p271.ALLOWLIST:
        payload = official_payload(spec)
        raw = p271.canonical_json_bytes(payload)
        entry = source_entry(spec, payload)
        (output_root / entry["relative_raw_path"]).write_bytes(raw)
        entries.append(entry)
    source_index = {
        "source_index_contract_version": p271.SOURCE_INDEX_CONTRACT_VERSION,
        "retrieval_started_at_utc": "2026-07-13T02:59:00Z",
        "retrieval_completed_at_utc": RETRIEVED_AT,
        "allowlisted_game_ids": list(p271.ALLOWLISTED_GAME_IDS),
        "sources": entries,
    }
    (output_root / "source_index.json").write_bytes(
        p271.canonical_json_bytes(source_index, trailing_newline=True)
    )
    return source_index


def test_canonical_serialization_is_nfc_sorted_compact_and_stable() -> None:
    decomposed = "Cafe\u0301"
    first = p271.canonical_json_bytes({"z": 1, "a": decomposed})
    second = p271.canonical_json_bytes({"a": "Caf\u00e9", "z": 1})
    assert first == second == b'{"a":"Caf\xc3\xa9","z":1}'
    assert p271.sha256_bytes(first) == p271.sha256_bytes(second)


def test_canonical_serialization_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        p271.canonical_json_bytes({"bad": float("nan")})


@pytest.mark.parametrize(
    ("detail", "code", "abstract", "expected"),
    [
        ("Scheduled", "S", "Preview", "SCHEDULED"),
        ("In Progress", "I", "Live", "IN_PROGRESS"),
        ("Suspended", "U", "Live", "SUSPENDED"),
        ("Final", "F", "Final", "FINAL"),
        ("Postponed", "D", "Final", "POSTPONED"),
        ("Cancelled", "C", "Final", "CANCELLED"),
        ("Forfeit", "F", "Final", "FORFEIT"),
    ],
)
def test_allowed_official_status_mapping(
    detail: str, code: str, abstract: str, expected: str
) -> None:
    status, conflicts = p271.resolve_official_status(
        {
            "detailedState": detail,
            "statusCode": code,
            "abstractGameState": abstract,
        }
    )
    assert status == expected
    assert conflicts == []


def test_unknown_official_status_fails_closed() -> None:
    with pytest.raises(p271.P271Error, match="Unrecognized official detailed status"):
        p271.resolve_official_status(
            {
                "detailedState": "Mystery",
                "statusCode": "F",
                "abstractGameState": "Final",
            }
        )


def test_official_arizona_az_abbreviation_matches_allowlisted_ari_identity() -> None:
    spec = p271.GAME_BY_ID["mlb_2026_825108"]
    payload = official_payload(spec)
    payload["gameData"]["teams"]["home"]["abbreviation"] = "AZ"
    p271.validate_official_payload(payload, spec)
    record, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["home_team"] == "AZ"


def test_required_and_nullable_manifest_fields() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec)
    record, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    record["actual_start_utc"] = None
    record["game_final_utc"] = None
    record["record_fingerprint"] = p271._record_fingerprint(record)
    p271.validate_manifest_record(record)

    missing = dict(record)
    del missing["status_reason"]
    with pytest.raises(p271.P271Error, match="Manifest schema mismatch"):
        p271.validate_manifest_record(missing)

    bad_status = dict(record)
    bad_status["status"] = "UNKNOWN"
    bad_status["record_fingerprint"] = p271._record_fingerprint(bad_status)
    with pytest.raises(p271.P271Error, match="not allowed"):
        p271.validate_manifest_record(bad_status)


def test_current_retrieval_and_feed_metadata_do_not_prove_historical_availability() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec)
    record, blockers = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["source_retrieved_at_utc"] == RETRIEVED_AT
    assert record["result_available_at_utc"] is None
    assert record["provenance_status"] == "INCOMPLETE"
    assert blockers == ["HISTORICAL_RESULT_AVAILABILITY_UNPROVEN"]


def test_final_record_requires_and_preserves_official_scores() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec, away_score=7, home_score=4)
    record, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["status"] == "FINAL"
    assert record["away_score"] == 7
    assert record["home_score"] == 4

    payload["gameData"]["teams"]["away"].pop("score")
    payload["gameData"]["teams"]["home"].pop("score")
    payload["liveData"]["linescore"]["teams"] = {}
    with pytest.raises(p271.P271Error, match="missing final scores"):
        p271.extract_manifest_record(payload, source_entry(spec, payload))


@pytest.mark.parametrize(
    ("detail", "code", "expected"),
    [("Postponed", "D", "POSTPONED"), ("Cancelled", "C", "CANCELLED")],
)
def test_postponed_and_cancelled_records_keep_scores_null(
    detail: str, code: str, expected: str
) -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(
        spec, detailed_state=detail, status_code=code, abstract_state="Final"
    )
    record, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["status"] == expected
    assert record["away_score"] is None
    assert record["home_score"] is None


def test_conflicting_official_scores_block_certification_without_choosing_a_score() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec, away_score=3, line_away_score=4)
    record, blockers = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["status"] == "FINAL"
    assert record["away_score"] is None
    assert record["home_score"] is None
    assert record["provenance_status"] == "CONFLICT"
    assert "OFFICIAL_FINAL_SCORE_CONFLICT" in blockers


def test_duplicate_game_ids_in_source_index_fail_closed(tmp_path: Path) -> None:
    source_index = write_offline_fixture(tmp_path)
    source_index["sources"][1]["game_id"] = source_index["sources"][0]["game_id"]
    with pytest.raises(p271.P271Error, match="duplicate game IDs"):
        p271.validate_source_index(source_index)


def test_record_fingerprint_is_stable_and_content_sensitive() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec, reason="Cafe\u0301")
    record_one, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    payload["gameData"]["status"]["reason"] = "Caf\u00e9"
    record_two, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record_one["record_fingerprint"] == record_two["record_fingerprint"]

    payload["gameData"]["teams"]["away"]["score"] = 9
    payload["liveData"]["linescore"]["teams"]["away"]["runs"] = 9
    record_three, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record_three["record_fingerprint"] != record_two["record_fingerprint"]


def test_doubleheader_requires_official_game_number() -> None:
    spec = p271.ALLOWLIST[0]
    payload = official_payload(spec, doubleheader="Y", game_number=2)
    record, _ = p271.extract_manifest_record(payload, source_entry(spec, payload))
    assert record["doubleheader_game_number"] == 2
    payload["gameData"]["game"].pop("gameNumber")
    with pytest.raises(p271.P271Error, match="requires a positive gameNumber"):
        p271.extract_manifest_record(payload, source_entry(spec, payload))


def test_raw_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    source_index = write_offline_fixture(tmp_path)
    first = source_index["sources"][0]
    (tmp_path / first["relative_raw_path"]).write_text("{}", encoding="utf-8")
    with pytest.raises(p271.P271Error, match="Raw SHA-256 mismatch"):
        p271.regenerate(tmp_path)


def test_two_run_offline_regeneration_is_byte_identical(tmp_path: Path) -> None:
    write_offline_fixture(tmp_path)
    first_summary = p271.regenerate(tmp_path)
    first_bytes = {
        name: (tmp_path / name).read_bytes()
        for name in (
            "pit-result-status.v1.jsonl",
            "manifest_summary.json",
            "SHA256SUMS",
        )
    }
    second_summary = p271.regenerate(tmp_path)
    second_bytes = {name: (tmp_path / name).read_bytes() for name in first_bytes}

    assert first_summary["manifest_root_hash"] == second_summary["manifest_root_hash"]
    assert first_summary["logical_summary_counts"] == second_summary["logical_summary_counts"]
    assert first_bytes == second_bytes
    assert first_summary["game_count"] == 12
    assert first_summary["logical_summary_counts"] == {
        "CERTIFIED": 0,
        "OFFICIAL_STATUS_RECOVERED_AVAILABILITY_BLOCKED": 12,
        "CONFLICT": 0,
        "UNRESOLVED": 0,
    }
    assert p271.verify(tmp_path)["manifest_root_hash"] == first_summary["manifest_root_hash"]

    manifest_rows = [
        json.loads(line)
        for line in (tmp_path / "pit-result-status.v1.jsonl").read_text().splitlines()
    ]
    assert len(manifest_rows) == 12
    assert [row["game_id"] for row in manifest_rows] == list(p271.ALLOWLISTED_GAME_IDS)


def test_network_mode_requires_exact_allowlist_and_rejects_duplicates() -> None:
    assert p271.validate_requested_game_ids(None) == p271.ALLOWLISTED_GAME_IDS
    with pytest.raises(p271.P271Error, match="Duplicate"):
        p271.validate_requested_game_ids([p271.ALLOWLISTED_GAME_IDS[0]] * 12)
    with pytest.raises(p271.P271Error, match="exact twelve"):
        p271.validate_requested_game_ids(list(p271.ALLOWLISTED_GAME_IDS[:-1]))
