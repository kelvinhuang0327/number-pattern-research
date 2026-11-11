"""Focused offline tests for the P274 prospective availability index and gate."""
from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path

import pytest

from scripts import _p274_prospective_result_availability_index as p274


REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_RELATIVE = Path(
    "data/mlb_2026/pit_observations/p273_game_825108_first_observation_v1"
)
REAL_BUNDLE = REPO_ROOT / BUNDLE_RELATIVE
GAME_ID = "mlb_2026_825108"
OBSERVED_AT = "2026-07-13T07:17:10.769880Z"
BEFORE = "2026-07-13T07:17:10.769879Z"
LATER = "2026-07-13T07:17:10.769881Z"
RAW_SHA256 = "21ca8b41c4c52d8d05198b32da2931a0343d8e364f04ee71f1a68cb256e1432f"


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_network(*args, **kwargs):
        raise AssertionError("P274 tests must make zero network calls")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def copy_bundle(tmp_path: Path, name: str = "bundle") -> Path:
    destination = tmp_path / name
    shutil.copytree(REAL_BUNDLE, destination)
    return destination


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_bytes(p274.canonical_json_bytes(value, trailing_newline=True))


def rebuild_manifest(bundle: Path) -> None:
    source_index = read_json(bundle / p274.SOURCE_INDEX_FILENAME)
    relative_raw_path = source_index["relative_raw_path"]
    paths = [
        p274.OBSERVATION_FILENAME,
        relative_raw_path,
        p274.SOURCE_INDEX_FILENAME,
    ]
    lines = [
        f"{p274.sha256_bytes((bundle / path).read_bytes())}  {path}"
        for path in sorted(paths)
    ]
    (bundle / p274.CHECKSUM_FILENAME).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def set_observation_time(bundle: Path, timestamp: str) -> None:
    observation_path = bundle / p274.OBSERVATION_FILENAME
    source_index_path = bundle / p274.SOURCE_INDEX_FILENAME
    observation = read_json(observation_path)
    observation["source_observed_at_utc"] = timestamp
    observation["result_available_at_utc"] = timestamp
    observation["source_fingerprint"] = p274._source_fingerprint(observation)
    observation["record_fingerprint"] = p274._record_fingerprint(observation)
    source_index = read_json(source_index_path)
    source_index["source_observed_at_utc"] = timestamp
    source_index["source_fingerprint"] = observation["source_fingerprint"]
    source_index["record_fingerprint"] = observation["record_fingerprint"]
    write_json(observation_path, observation)
    write_json(source_index_path, source_index)
    rebuild_manifest(bundle)


def build_real_index() -> dict:
    return p274.build_index([BUNDLE_RELATIVE])


def test_real_merged_p273_bundle_verifies_with_exact_evidence() -> None:
    record = p274.verify_bundle(BUNDLE_RELATIVE)

    assert record["game_id"] == GAME_ID
    assert record["official_game_pk"] == 825108
    assert record["official_status"] == "FINAL"
    assert (record["away_team"], record["away_score"]) == ("DET", 6)
    assert (record["home_team"], record["home_score"]) == ("AZ", 9)
    assert record["source_observed_at_utc"] == OBSERVED_AT
    assert record["result_available_at_utc"] == OBSERVED_AT
    assert record["raw_sha256"] == RAW_SHA256
    assert record["observation_sha256"] == (
        "a42911fd3838aa8310b313d949a00f23f3af1d79288f5d4638d69925747dc835"
    )
    assert record["source_index_sha256"] == (
        "c201e77c8644a6c203f4d87625c7e24e9ee461c116eab35e25ecff4f0b18ca5f"
    )
    assert record["manifest_fingerprint"] == (
        "ce4efb0e2e9d553aa9ebd791b235ed7b34897af34b40e9c957ee73ded5799725"
    )


def test_index_schema_is_exact_with_one_stably_ordered_record() -> None:
    index = build_real_index()

    assert set(index) == p274.INDEX_FIELDS
    assert index["index_schema_version"] == p274.INDEX_SCHEMA_VERSION
    assert index["record_count"] == 1
    assert len(index["records"]) == 1
    assert set(index["records"][0]) == p274.RECORD_FIELDS
    assert index["availability_semantics"] == "LOCAL_OBSERVATION_LOWER_BOUND"
    assert index["retroactive_certification"] is False
    assert index["records"][0]["retroactive_certification"] is False


def test_canonical_json_is_utf8_sorted_compact_and_nfc_normalized() -> None:
    decomposed = {"z": 1, "label": "Cafe\u0301"}
    composed = {"label": "Caf\u00e9", "z": 1}
    expected = b'{"label":"Caf\xc3\xa9","z":1}'

    assert p274.canonical_json_bytes(decomposed) == expected
    assert p274.canonical_json_bytes(composed) == expected


@pytest.mark.parametrize(
    ("as_of_utc", "expected_available"),
    [(BEFORE, False), (OBSERVED_AT, True), (LATER, True)],
)
def test_before_at_and_after_observation_gate(
    as_of_utc: str, expected_available: bool
) -> None:
    result, found = p274.query_index(build_real_index(), GAME_ID, as_of_utc)

    assert found is True
    assert result == {
        "game_id": GAME_ID,
        "as_of_utc": as_of_utc,
        "found": True,
        "available": expected_available,
        "available_from_utc": OBSERVED_AT,
        "semantics": "LOCAL_OBSERVATION_LOWER_BOUND",
        "retroactive_certification": False,
    }


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-07-13T07:17:10.769880",
        "2026-07-13T08:17:10.769880+01:00",
        "2026-07-13T07:17:10.769880+00:00",
        "not-a-timestamp",
    ],
)
def test_query_rejects_naive_non_utc_noncanonical_and_malformed_timestamps(
    timestamp: str,
) -> None:
    with pytest.raises(p274.P274Error, match="canonical timezone-aware UTC"):
        p274.query_index(build_real_index(), GAME_ID, timestamp)


def test_unknown_game_id_is_explicit_and_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    index_path = tmp_path / "output" / p274.INDEX_FILENAME
    p274.write_index(index_path.parent, build_real_index())

    exit_code = p274.main(
        [
            "query",
            "--index",
            str(index_path),
            "--game-id",
            "mlb_2026_999999",
            "--as-of-utc",
            OBSERVED_AT,
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert output["found"] is False
    assert output["available"] is False
    assert output["available_from_utc"] is None


def test_backdated_result_availability_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = copy_bundle(tmp_path)
    observation_path = bundle / p274.OBSERVATION_FILENAME
    observation = read_json(observation_path)
    observation["result_available_at_utc"] = BEFORE
    observation["record_fingerprint"] = p274._record_fingerprint(observation)
    source_index_path = bundle / p274.SOURCE_INDEX_FILENAME
    source_index = read_json(source_index_path)
    source_index["record_fingerprint"] = observation["record_fingerprint"]
    write_json(observation_path, observation)
    write_json(source_index_path, source_index)
    rebuild_manifest(bundle)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="Backdated"):
        p274.verify_bundle(Path("bundle"))


@pytest.mark.parametrize(
    "relative_path",
    [
        "raw/mlb_2026_825108.feed.live.json",
        p274.OBSERVATION_FILENAME,
        p274.SOURCE_INDEX_FILENAME,
    ],
)
def test_tampered_raw_observation_and_source_index_reject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    bundle = copy_bundle(tmp_path)
    target = bundle / relative_path
    target.write_bytes(target.read_bytes() + b" ")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="Checksum mismatch"):
        p274.verify_bundle(Path("bundle"))


def test_invalid_sha256sums_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = copy_bundle(tmp_path)
    manifest_path = bundle / p274.CHECKSUM_FILENAME
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text("0" + manifest[1:], encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="Checksum mismatch"):
        p274.verify_bundle(Path("bundle"))


@pytest.mark.parametrize(
    "relative_path",
    [
        p274.CHECKSUM_FILENAME,
        p274.OBSERVATION_FILENAME,
        p274.SOURCE_INDEX_FILENAME,
        "raw/mlb_2026_825108.feed.live.json",
    ],
)
def test_partial_bundle_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    bundle = copy_bundle(tmp_path)
    (bundle / relative_path).unlink()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="Partial|exactly one"):
        p274.verify_bundle(Path("bundle"))


def test_conflicting_duplicate_game_id_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_bundle(tmp_path, "first")
    second = copy_bundle(tmp_path, "second")
    set_observation_time(second, "2026-07-13T07:18:10.769880Z")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="Conflicting duplicate game ID"):
        p274.build_index([Path("first"), Path("second")])


def test_global_earliest_or_historical_certification_claim_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = copy_bundle(tmp_path)
    observation_path = bundle / p274.OBSERVATION_FILENAME
    observation = read_json(observation_path)
    observation["globally_earliest_result_available_at_utc"] = OBSERVED_AT
    write_json(observation_path, observation)
    rebuild_manifest(bundle)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(p274.P274Error, match="historical/globally-earliest"):
        p274.verify_bundle(Path("bundle"))


def test_file_mtime_changes_do_not_affect_index_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = copy_bundle(tmp_path)
    monkeypatch.chdir(tmp_path)
    before = p274.canonical_json_bytes(p274.build_index([Path("bundle")]), trailing_newline=True)
    for path in bundle.rglob("*"):
        os.utime(path, (1_000_000_000, 1_000_000_000), follow_symlinks=False)
    after = p274.canonical_json_bytes(p274.build_index([Path("bundle")]), trailing_newline=True)

    assert after == before


def test_two_independent_builds_are_byte_identical_and_manifest_valid(
    tmp_path: Path,
) -> None:
    index = build_real_index()
    first_index, first_manifest = p274.write_index(tmp_path / "first", index)
    second_index, second_manifest = p274.write_index(tmp_path / "second", index)

    assert first_index == second_index
    assert first_manifest == second_manifest
    expected_manifest = f"{p274.sha256_bytes(first_index)}  index.json\n".encode()
    assert first_manifest == expected_manifest
    assert (tmp_path / "first" / "index.json").read_bytes() == first_index
    assert (tmp_path / "second" / "SHA256SUMS").read_bytes() == second_manifest


def test_output_has_no_wall_clock_temp_or_absolute_path_metadata(tmp_path: Path) -> None:
    index_bytes, manifest_bytes = p274.write_index(tmp_path / "physical-output", build_real_index())
    index = json.loads(index_bytes)

    assert "generated_at" not in index
    assert "mtime" not in index
    assert str(tmp_path).encode() not in index_bytes
    assert b"physical-output" not in index_bytes
    assert index["records"][0]["source_bundle_root"] == BUNDLE_RELATIVE.as_posix()
    assert manifest_bytes.endswith(b"  index.json\n")


def test_query_cli_performs_no_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_root = tmp_path / "output"
    p274.write_index(output_root, build_real_index())
    before = {
        path.relative_to(tmp_path).as_posix(): (
            path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    exit_code = p274.main(
        [
            "query",
            "--index",
            str(output_root / p274.INDEX_FILENAME),
            "--game-id",
            GAME_ID,
            "--as-of-utc",
            OBSERVED_AT,
        ]
    )
    result = json.loads(capsys.readouterr().out)
    after = {
        path.relative_to(tmp_path).as_posix(): (
            path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert exit_code == 0
    assert result["available"] is True
    assert after == before


def test_cli_has_exact_build_and_query_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = p274._parser()
    action = next(
        item
        for item in parser._actions
        if isinstance(item, p274.argparse._SubParsersAction)
    )
    assert set(action.choices) == {"build", "query"}

    output_root = tmp_path / "built"
    build_exit = p274.main(
        [
            "build",
            "--bundle-root",
            BUNDLE_RELATIVE.as_posix(),
            "--output-root",
            str(output_root),
        ]
    )
    build_result = json.loads(capsys.readouterr().out)
    query_exit = p274.main(
        [
            "query",
            "--index",
            str(output_root / p274.INDEX_FILENAME),
            "--game-id",
            GAME_ID,
            "--as-of-utc",
            BEFORE,
        ]
    )
    query_result = json.loads(capsys.readouterr().out)

    assert build_exit == 0
    assert build_result["record_count"] == 1
    assert query_exit == 0
    assert query_result["available"] is False
