"""Focused offline tests for the P275 result-availability consumer gate."""
from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import pytest

from scripts import _p274_prospective_result_availability_index as p274
from scripts import _p275_prospective_availability_consumer_gate as p275


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = REPO_ROOT / "data/mlb_2026/derived/p274_prospective_result_availability_index_v1"
INDEX_PATH = INDEX_ROOT / p274.INDEX_FILENAME
MANIFEST_PATH = INDEX_ROOT / p274.CHECKSUM_FILENAME
GAME_ID = "mlb_2026_825108"
OBSERVED_AT = "2026-07-13T07:17:10.769880Z"
BEFORE = "2026-07-13T07:17:10.769879Z"
AFTER = "2026-07-13T07:17:10.769881Z"


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_network(*args, **kwargs):
        raise AssertionError("P275 tests must make zero network calls")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def _evaluate(
    *,
    game_id: str = GAME_ID,
    feature_as_of_utc: str | None = AFTER,
    index_path: Path = INDEX_PATH,
    manifest_path: Path = MANIFEST_PATH,
) -> p275.AvailabilityGateDecision:
    return p275.evaluate_result_availability(
        game_id=game_id,
        feature_as_of_utc=feature_as_of_utc,
        index_path=index_path,
        manifest_path=manifest_path,
    )


def _copy_publication(tmp_path: Path) -> Path:
    copied_root = tmp_path / "p274-index"
    shutil.copytree(INDEX_ROOT, copied_root)
    return copied_root


def _republish(copied_root: Path, payload: dict) -> None:
    index_bytes = p274.canonical_json_bytes(payload, trailing_newline=True)
    (copied_root / p274.INDEX_FILENAME).write_bytes(index_bytes)
    (copied_root / p274.CHECKSUM_FILENAME).write_text(
        f"{p274.sha256_bytes(index_bytes)}  {p274.INDEX_FILENAME}\n",
        encoding="utf-8",
    )


def test_before_observation_is_rejected() -> None:
    decision = _evaluate(feature_as_of_utc=BEFORE)

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.RESULT_NOT_YET_AVAILABLE
    assert decision.result_available_at_utc == OBSERVED_AT
    assert decision.availability_semantics == "LOCAL_OBSERVATION_LOWER_BOUND"
    assert decision.retroactive_certification is False


@pytest.mark.parametrize("feature_as_of_utc", [OBSERVED_AT, AFTER])
def test_exact_and_after_observation_are_accepted(feature_as_of_utc: str) -> None:
    decision = _evaluate(feature_as_of_utc=feature_as_of_utc)

    assert decision.result_usage_allowed is True
    assert decision.block_reason is None
    assert decision.feature_as_of_utc == feature_as_of_utc
    assert decision.result_available_at_utc == OBSERVED_AT


@pytest.mark.parametrize(
    "feature_as_of_utc",
    [
        "2026-07-13 07:17:10.769880",
        "2026-07-13T07:17:10.769880",
        "2026-07-13T07:17:10.769880+00:00",
        "2026-07-13T07:17:10.7698800Z",
    ],
)
def test_naive_or_noncanonical_feature_timestamp_is_rejected(
    feature_as_of_utc: str,
) -> None:
    decision = _evaluate(feature_as_of_utc=feature_as_of_utc)

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_FEATURE_AS_OF_UTC
    assert decision.feature_as_of_utc is None


def test_missing_feature_as_of_fails_closed() -> None:
    decision = _evaluate(feature_as_of_utc=None)

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_FEATURE_AS_OF_UTC


def test_unknown_game_fails_closed_without_inference() -> None:
    decision = _evaluate(game_id="mlb_2026_999999")

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.MISSING_AVAILABILITY_EVIDENCE
    assert decision.result_available_at_utc is None
    assert decision.retroactive_certification is False


def test_missing_index_publication_is_rejected(tmp_path: Path) -> None:
    decision = _evaluate(index_path=tmp_path / p274.INDEX_FILENAME)

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.MISSING_AVAILABILITY_EVIDENCE


def test_missing_manifest_publication_is_rejected(tmp_path: Path) -> None:
    decision = _evaluate(manifest_path=tmp_path / p274.CHECKSUM_FILENAME)

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.MISSING_AVAILABILITY_EVIDENCE


def test_tampered_index_is_rejected(tmp_path: Path) -> None:
    copied_root = _copy_publication(tmp_path)
    copied_index = copied_root / p274.INDEX_FILENAME
    payload = json.loads(copied_index.read_text(encoding="utf-8"))
    payload["records"][0]["result_available_at_utc"] = AFTER
    copied_index.write_bytes(p274.canonical_json_bytes(payload, trailing_newline=True))

    decision = _evaluate(
        index_path=copied_index,
        manifest_path=copied_root / p274.CHECKSUM_FILENAME,
    )

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_AVAILABILITY_EVIDENCE


def test_tampered_or_inconsistent_manifest_is_rejected(tmp_path: Path) -> None:
    copied_root = _copy_publication(tmp_path)
    manifest = copied_root / p274.CHECKSUM_FILENAME
    manifest.write_text(f"{'0' * 64}  {p274.INDEX_FILENAME}\n", encoding="utf-8")

    decision = _evaluate(
        index_path=copied_root / p274.INDEX_FILENAME,
        manifest_path=manifest,
    )

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_AVAILABILITY_EVIDENCE


@pytest.mark.parametrize(
    ("mutation", "label"),
    [
        (lambda payload: payload.update(availability_semantics="GLOBAL_EARLIEST"), "semantics"),
        (lambda payload: payload.update(retroactive_certification=True), "retroactive"),
    ],
)
def test_unsupported_semantics_and_retroactive_certification_fail_closed(
    tmp_path: Path,
    mutation,
    label: str,
) -> None:
    copied_root = _copy_publication(tmp_path)
    payload = json.loads((copied_root / p274.INDEX_FILENAME).read_text(encoding="utf-8"))
    mutation(payload)
    _republish(copied_root, payload)

    decision = _evaluate(
        index_path=copied_root / p274.INDEX_FILENAME,
        manifest_path=copied_root / p274.CHECKSUM_FILENAME,
    )

    assert label in {"semantics", "retroactive"}
    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_AVAILABILITY_EVIDENCE


def test_conflicting_duplicate_records_fail_closed(tmp_path: Path) -> None:
    copied_root = _copy_publication(tmp_path)
    payload = json.loads((copied_root / p274.INDEX_FILENAME).read_text(encoding="utf-8"))
    duplicate = dict(payload["records"][0])
    duplicate["result_available_at_utc"] = AFTER
    payload["records"].append(duplicate)
    payload["record_count"] = 2
    _republish(copied_root, payload)

    decision = _evaluate(
        index_path=copied_root / p274.INDEX_FILENAME,
        manifest_path=copied_root / p274.CHECKSUM_FILENAME,
    )

    assert decision.result_usage_allowed is False
    assert decision.block_reason == p275.INVALID_AVAILABILITY_EVIDENCE


def test_repeated_runs_are_deterministic() -> None:
    first = _evaluate().to_dict()
    second = _evaluate().to_dict()

    assert first == second


def test_gate_evaluation_performs_no_repository_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_write(*args, **kwargs):
        raise AssertionError("P275 gate evaluation must be read-only")

    monkeypatch.setattr(Path, "write_bytes", forbidden_write)
    monkeypatch.setattr(Path, "write_text", forbidden_write)

    assert _evaluate().result_usage_allowed is True
