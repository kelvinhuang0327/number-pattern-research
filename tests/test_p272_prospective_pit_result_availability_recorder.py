"""Focused offline tests for the P272 prospective availability recorder."""
from __future__ import annotations

import copy
import io
import inspect
import json
import os
import urllib.error
import urllib.request
import urllib.response
from email.message import Message
from pathlib import Path

import pytest

from scripts import _p272_prospective_pit_result_availability_recorder as p272


OBSERVED_AT = "2026-07-13T03:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[1]
P271_RAW_ROOT = (
    REPO_ROOT / "data/mlb_2026/pit_replay/p271_official_result_status_v1/raw"
)
FINAL_FIXTURE = P271_RAW_ROOT / "mlb_2026_822834.feed.live.json"
ALIAS_FIXTURE = P271_RAW_ROOT / "mlb_2026_825108.feed.live.json"
REAL_BUILD_OFFICIAL_OPENER = getattr(p272, "_build_official_opener", None)


class InMemoryHTTPSHandler(urllib.request.HTTPSHandler):
    """Return one synthetic HTTPS response without opening a socket."""

    def __init__(
        self,
        *,
        status: int,
        body: bytes = b"",
        location: str | None = None,
        effective_url: str | None = None,
        content_type: str = "application/json;charset=UTF-8",
    ) -> None:
        super().__init__()
        self.status = status
        self.body = body
        self.location = location
        self.effective_url = effective_url
        self.content_type = content_type
        self.requests: list[urllib.request.Request] = []

    def https_open(self, request: urllib.request.Request):
        self.requests.append(request)
        headers = Message()
        headers["Content-Type"] = self.content_type
        if self.location is not None:
            headers["Location"] = self.location
        response = urllib.response.addinfourl(
            io.BytesIO(self.body),
            headers,
            self.effective_url or request.full_url,
            code=self.status,
        )
        response.msg = "synthetic offline response"
        return response


def install_in_memory_opener(
    monkeypatch: pytest.MonkeyPatch, handler: InMemoryHTTPSHandler
) -> None:
    reject_handler = getattr(p272, "_RejectRedirectHandler", None)
    assert reject_handler is not None, "redirect rejection handler is missing"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), reject_handler(), handler
    )
    monkeypatch.setattr(p272, "_build_official_opener", lambda: opener, raising=False)


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_urlopen(*args, **kwargs):
        raise AssertionError("P272 tests must never call the network")

    monkeypatch.setattr(p272.urllib.request, "urlopen", forbidden_urlopen)

    def forbidden_opener():
        raise AssertionError("P272 tests must install an offline opener explicitly")

    monkeypatch.setattr(
        p272, "_build_official_opener", forbidden_opener, raising=False
    )


def fixture_payload(path: Path = FINAL_FIXTURE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_bytes(payload: dict) -> bytes:
    return p272.canonical_json_bytes(payload)


def bundle_bytes(output_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(output_root).as_posix(): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }


def fixture_artifacts() -> dict[str, bytes]:
    raw = FINAL_FIXTURE.read_bytes()
    record = p272.build_observation_record(raw, 822834, OBSERVED_AT)
    return p272.build_bundle_bytes(raw, record)


def materialize_test_bundle(output_root: Path, artifacts: dict[str, bytes]) -> None:
    """Test-only helper used to model an already visible concurrent winner."""
    for relative_path, data in artifacts.items():
        path = output_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_canonical_json_is_sorted_compact_nfc_and_sha256_stable() -> None:
    decomposed = {"z": 1, "label": "Cafe\u0301"}
    composed = {"label": "Caf\u00e9", "z": 1}
    expected = b'{"label":"Caf\xc3\xa9","z":1}'

    assert p272.canonical_json_bytes(decomposed) == expected
    assert p272.canonical_json_bytes(composed) == expected
    assert p272.sha256_bytes(expected) == p272.sha256_bytes(expected)
    assert len(p272.sha256_bytes(expected)) == 64


def test_canonical_json_rejects_nfc_duplicate_keys_and_non_finite_values() -> None:
    with pytest.raises(p272.P272Error, match="duplicate key"):
        p272.canonical_json_bytes({"Cafe\u0301": 1, "Caf\u00e9": 2})
    with pytest.raises(ValueError):
        p272.canonical_json_bytes({"bad": float("nan")})


def test_final_availability_equals_observation_time_and_preserves_raw_hash() -> None:
    raw = FINAL_FIXTURE.read_bytes()
    record = p272.build_observation_record(raw, 822834, OBSERVED_AT)

    assert record["official_status"] == "FINAL"
    assert record["source_observed_at_utc"] == OBSERVED_AT
    assert record["result_available_at_utc"] == OBSERVED_AT
    assert record["raw_sha256"] == p272.sha256_bytes(raw)
    assert record["away_score"] == 14
    assert record["home_score"] == 5
    assert record["provenance_status"] == "COMPLETE"


@pytest.mark.parametrize(
    ("detail", "code", "abstract", "abstract_code", "expected"),
    [
        ("Scheduled", "S", "Preview", "P", "SCHEDULED"),
        ("In Progress", "I", "Live", "L", "IN_PROGRESS"),
        ("Suspended", "U", "Live", "L", "SUSPENDED"),
        ("Postponed", "D", "Final", "F", "POSTPONED"),
        ("Cancelled", "C", "Final", "F", "CANCELLED"),
    ],
)
def test_non_final_statuses_leave_result_availability_and_scores_null(
    detail: str,
    code: str,
    abstract: str,
    abstract_code: str,
    expected: str,
) -> None:
    payload = fixture_payload()
    payload["gameData"]["status"].update(
        {
            "detailedState": detail,
            "statusCode": code,
            "codedGameState": code,
            "abstractGameState": abstract,
            "abstractGameCode": abstract_code,
        }
    )
    record = p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)

    assert record["official_status"] == expected
    assert record["result_available_at_utc"] is None
    assert record["away_score"] is None
    assert record["home_score"] is None


def test_forfeit_is_resolved_at_observation_time() -> None:
    payload = fixture_payload()
    payload["gameData"]["status"].update(
        {
            "detailedState": "Forfeit",
            "statusCode": "F",
            "codedGameState": "F",
            "abstractGameState": "Final",
            "abstractGameCode": "F",
        }
    )
    record = p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)
    assert record["official_status"] == "FORFEIT"
    assert record["result_available_at_utc"] == OBSERVED_AT


def test_capture_has_no_backdating_parameter_or_cli_option(tmp_path: Path) -> None:
    assert "observed_at_utc" not in inspect.signature(p272.capture).parameters
    with pytest.raises(SystemExit):
        p272._parser().parse_args(
            [
                "capture",
                "--game-pk",
                "822834",
                "--output-root",
                str(tmp_path / "bundle"),
                "--observed-at-utc",
                "2000-01-01T00:00:00Z",
            ]
        )


def test_offline_verify_accepts_fixed_time_and_never_uses_feed_metadata(
    tmp_path: Path,
) -> None:
    record, state = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc="2026-07-13T11:00:00+08:00",
        output_root=tmp_path / "bundle",
    )
    payload = fixture_payload()

    assert state == "CREATED"
    assert record["source_observed_at_utc"] == OBSERVED_AT
    assert record["source_observed_at_utc"] != payload["metaData"]["timeStamp"]
    assert record["result_available_at_utc"] == OBSERVED_AT


def test_official_request_rejects_non_mlb_host_and_broad_paths() -> None:
    with pytest.raises(p272.P272Error, match="official statsapi"):
        p272.build_official_request(
            822834,
            url="https://example.com/api/v1.1/game/822834/feed/live",
        )
    with pytest.raises(p272.P272Error, match="exact one-game"):
        p272.build_official_request(
            822834,
            url="https://statsapi.mlb.com/api/v1/schedule?sportId=1",
        )


def test_official_request_rejects_url_userinfo_authentication_and_cookies() -> None:
    endpoint = p272.OFFICIAL_ENDPOINT_TEMPLATE.format(game_pk=822834)
    with pytest.raises(p272.P272Error, match="userinfo"):
        p272.build_official_request(
            822834,
            url="https://user:secret@statsapi.mlb.com/api/v1.1/game/822834/feed/live",
        )
    with pytest.raises(p272.P272Error, match="Authentication"):
        p272.build_official_request(
            822834,
            url=endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": p272.USER_AGENT,
                "Authorization": "Bearer forbidden",
            },
        )
    with pytest.raises(p272.P272Error, match="Authentication"):
        p272.build_official_request(
            822834,
            url=endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": p272.USER_AGENT,
                "Cookie": "forbidden=true",
            },
        )


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize(
    "location",
    [
        "https://example.com/escape",
        "https://statsapi.mlb.com/api/v1.1/game/822834/feed/live?redirected=1",
    ],
)
def test_hardening_redirects_fail_closed_without_second_request(
    monkeypatch: pytest.MonkeyPatch, status: int, location: str
) -> None:
    handler = InMemoryHTTPSHandler(status=status, location=location)
    install_in_memory_opener(monkeypatch, handler)

    with pytest.raises(p272.P272Error, match=rf"redirect.*{status}|{status}.*redirect"):
        p272.fetch_official_response_once(822834)

    assert [request.full_url for request in handler.requests] == [
        p272.OFFICIAL_ENDPOINT_TEMPLATE.format(game_pk=822834)
    ]


def test_hardening_effective_response_url_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = InMemoryHTTPSHandler(
        status=200,
        body=FINAL_FIXTURE.read_bytes(),
        effective_url="https://example.com/api/v1.1/game/822834/feed/live",
    )
    install_in_memory_opener(monkeypatch, handler)

    with pytest.raises(p272.P272Error, match="effective response URL"):
        p272.fetch_official_response_once(822834)
    assert len(handler.requests) == 1


def test_hardening_proxy_environment_is_disabled_and_boundary_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "example.com")
    assert REAL_BUILD_OFFICIAL_OPENER is not None, "official opener factory is missing"

    opener = REAL_BUILD_OFFICIAL_OPENER()
    proxy_handlers = [
        handler
        for handler in opener.handlers
        if isinstance(handler, urllib.request.ProxyHandler)
    ]
    redirect_handlers = [
        handler
        for handler in opener.handlers
        if isinstance(handler, urllib.request.HTTPRedirectHandler)
    ]
    # ProxyHandler({}) intentionally contributes no proxy_open methods, so urllib
    # omits it from the installed handler list instead of deriving proxies from env.
    assert proxy_handlers == []
    assert len(redirect_handlers) == 1
    assert type(redirect_handlers[0]).__name__ == "_RejectRedirectHandler"

    request = p272.build_official_request(822834)
    assert request.full_url == p272.OFFICIAL_ENDPOINT_TEMPLATE.format(game_pk=822834)
    assert request.host == p272.OFFICIAL_HOST


def test_hardening_mocked_200_is_accepted_with_one_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = FINAL_FIXTURE.read_bytes()
    handler = InMemoryHTTPSHandler(status=200, body=raw)
    install_in_memory_opener(monkeypatch, handler)
    monkeypatch.setattr(p272, "utc_now", lambda: OBSERVED_AT)

    observed_raw, observed_at = p272.fetch_official_response_once(822834)

    assert observed_raw == raw
    assert observed_at == OBSERVED_AT
    assert len(handler.requests) == 1


def test_exact_one_numeric_game_restriction() -> None:
    assert p272.validate_single_game_pk([822834]) == 822834
    with pytest.raises(p272.P272Error, match="Exactly one"):
        p272.validate_single_game_pk([])
    with pytest.raises(p272.P272Error, match="Exactly one"):
        p272.validate_single_game_pk([822834, 822835])
    with pytest.raises(SystemExit):
        p272._parser().parse_args(
            [
                "offline-verify",
                "--game-pk",
                "not-numeric",
                "--raw-response",
                str(FINAL_FIXTURE),
                "--observed-at-utc",
                OBSERVED_AT,
                "--output-root",
                "/tmp/unused",
            ]
        )


def test_capture_transport_failure_is_attempted_once_without_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("offline test")

    class FailingOpener:
        def open(self, *args, **kwargs):
            return fail_once(*args, **kwargs)

    monkeypatch.setattr(p272.urllib.request, "urlopen", fail_once)
    monkeypatch.setattr(p272, "_build_official_opener", lambda: FailingOpener(), raising=False)
    output_root = tmp_path / "bundle"
    with pytest.raises(p272.P272Error, match="retry is forbidden"):
        p272.capture(game_pk=822834, output_root=output_root)

    assert calls == 1
    assert not output_root.exists()


def test_capture_clock_runs_after_complete_response_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_completed = False
    raw = FINAL_FIXTURE.read_bytes()

    class FakeResponse:
        headers = {"Content-Type": "application/json;charset=UTF-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def getcode(self):
            return 200

        def geturl(self):
            return p272.OFFICIAL_ENDPOINT_TEMPLATE.format(game_pk=822834)

        def read(self):
            nonlocal read_completed
            read_completed = True
            return raw

    def fake_urlopen(*args, **kwargs):
        return FakeResponse()

    class FakeOpener:
        def open(self, *args, **kwargs):
            return fake_urlopen(*args, **kwargs)

    def fake_clock() -> str:
        assert read_completed
        return OBSERVED_AT

    monkeypatch.setattr(p272.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(p272, "_build_official_opener", lambda: FakeOpener(), raising=False)
    monkeypatch.setattr(p272, "utc_now", fake_clock)

    observed_raw, observed_at = p272.fetch_official_response_once(822834)
    assert observed_raw == raw
    assert observed_at == OBSERVED_AT


def test_game_identity_validation_fails_closed() -> None:
    payload = fixture_payload()
    payload["gameData"]["game"]["pk"] = 999999
    with pytest.raises(p272.P272Error, match="identity mismatch"):
        p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)

    payload = fixture_payload()
    payload["gamePk"] = 999999
    with pytest.raises(p272.P272Error, match="Conflicting top-level"):
        p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)


def test_predeclared_alias_validates_identity_but_preserves_official_abbreviation() -> None:
    raw = ALIAS_FIXTURE.read_bytes()
    record = p272.build_observation_record(
        raw,
        825108,
        OBSERVED_AT,
        expected_away_team="DET",
        expected_home_team="ARI",
    )
    assert record["home_team"] == "AZ"

    with pytest.raises(p272.P272Error, match="identity mismatch"):
        p272.build_observation_record(
            raw,
            825108,
            OBSERVED_AT,
            expected_away_team="DET",
            expected_home_team="PHX",
        )


def test_unknown_optional_fields_remain_null() -> None:
    payload = fixture_payload()
    payload["gameData"]["status"].pop("reason", None)
    record = p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)
    assert record["status_reason"] is None

    payload["gameData"]["game"].pop("season")
    record = p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)
    assert record["season"] is None
    assert record["provenance_status"] == "INCOMPLETE"


def test_conflicting_status_team_and_score_evidence_fail_closed() -> None:
    payload = fixture_payload()
    payload["gameData"]["status"]["detailedState"] = "In Progress"
    with pytest.raises(p272.P272Error, match="detailed/coded"):
        p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)

    payload = fixture_payload()
    payload["liveData"]["boxscore"]["teams"]["away"]["team"]["id"] = 999
    with pytest.raises(p272.P272Error, match="team identity evidence"):
        p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)

    payload = fixture_payload()
    payload["gameData"]["teams"]["away"]["score"] = 99
    with pytest.raises(p272.P272Error, match="score evidence"):
        p272.build_observation_record(fixture_bytes(payload), 822834, OBSERVED_AT)


def test_hardening_successful_publish_exposes_all_four_files_together(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"
    real_publish = p272._atomic_publish_noreplace
    observations = 0

    def observing_publish(parent_fd: int, staging_name: str, final_name: str) -> bool:
        nonlocal observations
        observations += 1
        assert final_name not in os.listdir(parent_fd)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        try:
            assert set(os.listdir(staging_fd)) == {
                p272.CHECKSUM_FILENAME,
                p272.OBSERVATION_FILENAME,
                p272.SOURCE_INDEX_FILENAME,
                "raw",
            }
            raw_fd = os.open(
                "raw",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=staging_fd,
            )
            try:
                assert os.listdir(raw_fd) == ["mlb_2026_822834.feed.live.json"]
            finally:
                os.close(raw_fd)
        finally:
            os.close(staging_fd)
        return real_publish(parent_fd, staging_name, final_name)

    monkeypatch.setattr(p272, "_atomic_publish_noreplace", observing_publish)
    _, state = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=output_root,
    )

    assert state == "CREATED"
    assert observations == 1
    assert bundle_bytes(output_root) == fixture_artifacts()


@pytest.mark.parametrize("completed_files", [0, 1, 2, 3])
def test_hardening_staging_failure_never_exposes_partial_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, completed_files: int
) -> None:
    output_root = tmp_path / f"bundle-{completed_files}"
    real_write = p272._write_bundle_artifact
    completed = 0

    def fail_after_count(
        staging_fd: int,
        raw_fd: int,
        relative_path: str,
        data: bytes,
    ):
        nonlocal completed
        if completed == completed_files:
            raise OSError(f"injected failure after {completed_files} files")
        written = real_write(staging_fd, raw_fd, relative_path, data)
        completed += 1
        return written

    monkeypatch.setattr(p272, "_write_bundle_artifact", fail_after_count)
    with pytest.raises(p272.P272Error, match="staging write failed"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert completed == completed_files
    assert not output_root.exists()


def test_hardening_failure_before_final_rename_leaves_bundle_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"

    def fail_publish(*args, **kwargs):
        raise p272.P272Error("injected failure before final rename")

    monkeypatch.setattr(p272, "_atomic_publish_noreplace", fail_publish)
    with pytest.raises(
        p272.P272Error,
        match="before final rename.*cleanup=CLEANUP_RETAINED_IDENTITY_UNCERTAIN",
    ):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert not output_root.exists()
    assert len(list(tmp_path.glob(".bundle.p272-stage-*"))) == 1


def test_hardening_concurrent_identical_winner_is_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"
    artifacts = fixture_artifacts()
    collisions = 0

    def install_winner(parent_fd: int, staging_name: str, final_name: str) -> bool:
        nonlocal collisions
        collisions += 1
        assert not output_root.exists()
        materialize_test_bundle(output_root, artifacts)
        return False

    monkeypatch.setattr(p272, "_atomic_publish_noreplace", install_winner)
    with pytest.raises(
        p272.P272Error,
        match="cleanup=CLEANUP_RETAINED_IDENTITY_UNCERTAIN",
    ):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert collisions == 1
    assert bundle_bytes(output_root) == artifacts
    assert len(list(tmp_path.glob(".bundle.p272-stage-*"))) == 1


def test_hardening_existing_partial_bundle_is_rejected(tmp_path: Path) -> None:
    output_root = tmp_path / "bundle"
    output_root.mkdir()
    (output_root / p272.OBSERVATION_FILENAME).write_bytes(
        fixture_artifacts()[p272.OBSERVATION_FILENAME]
    )

    with pytest.raises(p272.P272Error, match="partial|inventory"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )


def test_hardening_output_root_and_parent_symlinks_are_rejected(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    output_symlink = tmp_path / "bundle-link"
    output_symlink.symlink_to(external, target_is_directory=True)

    with pytest.raises(p272.P272Error, match="symlink"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_symlink,
        )

    parent_symlink = tmp_path / "parent-link"
    parent_symlink.symlink_to(external, target_is_directory=True)
    with pytest.raises(p272.P272Error, match="symlink|securely open"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=parent_symlink / "bundle",
        )
    assert list(external.iterdir()) == []


def test_hardening_offline_raw_response_symlink_is_rejected(tmp_path: Path) -> None:
    source_link = tmp_path / "source-link.json"
    source_link.symlink_to(FINAL_FIXTURE)
    output_root = tmp_path / "bundle"

    with pytest.raises(p272.P272Error, match="raw-response.*symlink"):
        p272.offline_verify(
            raw_response=source_link,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert not output_root.exists()


def test_hardening_existing_raw_symlink_is_rejected(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    output_root = tmp_path / "bundle"
    output_root.mkdir()
    (output_root / "raw").symlink_to(external, target_is_directory=True)

    with pytest.raises(p272.P272Error, match="raw.*symlink|symlink.*raw"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )
    assert list(external.iterdir()) == []


def test_hardening_raw_replacement_race_cannot_write_outside_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    external = tmp_path / "external"
    external.mkdir()
    output_root = tmp_path / "bundle"
    real_write = p272._write_bundle_artifact
    raced = False

    def replace_raw_before_write(
        staging_fd: int,
        raw_fd: int,
        relative_path: str,
        data: bytes,
    ):
        nonlocal raced
        if relative_path.startswith("raw/") and not raced:
            raced = True
            os.rename(
                "raw",
                "raw-original",
                src_dir_fd=staging_fd,
                dst_dir_fd=staging_fd,
            )
            os.symlink(str(external), "raw", dir_fd=staging_fd)
        return real_write(staging_fd, raw_fd, relative_path, data)

    monkeypatch.setattr(p272, "_write_bundle_artifact", replace_raw_before_write)
    with pytest.raises(p272.P272Error, match="staging|raw|inventory"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert raced
    assert not output_root.exists()
    assert list(external.iterdir()) == []


def test_hardening_final_bundle_replacement_after_inventory_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"
    p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=output_root,
    )
    displaced = tmp_path / "displaced-bundle"
    external = tmp_path / "external"
    external.mkdir()
    real_read = p272._read_regular_file_at
    raced = False

    def replace_final_then_read(directory_fd: int, name: str) -> bytes:
        nonlocal raced
        if not raced:
            raced = True
            output_root.rename(displaced)
            output_root.symlink_to(external, target_is_directory=True)
        return real_read(directory_fd, name)

    monkeypatch.setattr(p272, "_read_regular_file_at", replace_final_then_read)
    with pytest.raises(p272.P272Error, match="identity|replaced|symlink"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert raced
    assert list(external.iterdir()) == []


@pytest.mark.parametrize("bad_relative", ["../escape", "/absolute/escape"])
def test_hardening_bundle_relative_path_traversal_is_rejected(
    tmp_path: Path, bad_relative: str
) -> None:
    artifacts = fixture_artifacts()
    artifacts[bad_relative] = artifacts.pop(p272.OBSERVATION_FILENAME)

    with pytest.raises(p272.P272Error, match="relative path"):
        p272.write_bundle(tmp_path / "bundle", artifacts)

    assert not (tmp_path / "escape").exists()
    assert not (tmp_path / "bundle").exists()


def test_hardening_output_root_traversal_is_rejected(tmp_path: Path) -> None:
    safe = tmp_path / "safe"
    safe.mkdir()
    traversing_root = safe / ".." / "traversed-bundle"

    with pytest.raises(p272.P272Error, match="traversal"):
        p272.write_bundle(traversing_root, fixture_artifacts())

    assert not (tmp_path / "traversed-bundle").exists()


def test_hardening_staging_name_replacement_before_publish_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"
    real_verify = p272._verify_staging_before_publish
    replaced = False

    def replace_staging_name(
        parent_fd: int,
        staging_name: str,
        staging_fd: int,
        staging_identity,
        raw_fd: int,
        raw_identity,
        artifacts,
    ) -> None:
        nonlocal replaced
        if not replaced:
            replaced = True
            os.rename(
                staging_name,
                f"{staging_name}.original",
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.mkdir(staging_name, mode=0o700, dir_fd=parent_fd)
        real_verify(
            parent_fd,
            staging_name,
            staging_fd,
            staging_identity,
            raw_fd,
            raw_identity,
            artifacts,
        )

    monkeypatch.setattr(p272, "_verify_staging_before_publish", replace_staging_name)
    with pytest.raises(
        p272.P272Error, match="(?i)staging.*identity|identity.*staging"
    ):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    assert replaced
    assert not output_root.exists()


def test_hardening_untrusted_writable_publication_parent_fails_closed(
    tmp_path: Path,
) -> None:
    publication_parent = tmp_path / "writable-parent"
    publication_parent.mkdir(mode=0o770)
    publication_parent.chmod(0o770)

    with pytest.raises(p272.P272Error, match="group/world writable"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=publication_parent / "bundle",
        )

    assert not (publication_parent / "bundle").exists()


def test_differing_existing_bundle_is_rejected_without_overwrite(tmp_path: Path) -> None:
    output_root = tmp_path / "bundle"
    p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=output_root,
    )
    observation_path = output_root / p272.OBSERVATION_FILENAME
    observation_path.write_bytes(b'{"different":true}\n')

    with pytest.raises(p272.P272Error, match="write-once overwrite refused"):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )
    assert observation_path.read_bytes() == b'{"different":true}\n'


def test_identical_existing_bundle_is_accepted_idempotently(tmp_path: Path) -> None:
    output_root = tmp_path / "bundle"
    first_record, first_state = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=output_root,
    )
    first = bundle_bytes(output_root)
    second_record, second_state = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=output_root,
    )

    assert first_state == "CREATED"
    assert second_state == "VERIFIED_IDENTICAL"
    assert first_record == second_record
    assert first == bundle_bytes(output_root)


def test_two_run_offline_bundles_are_byte_identical_and_lossless(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_record, _ = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=first_root,
    )
    second_record, _ = p272.offline_verify(
        raw_response=FINAL_FIXTURE,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=second_root,
    )

    first = bundle_bytes(first_root)
    second = bundle_bytes(second_root)
    assert first_record == second_record
    assert first == second
    assert set(first) == {
        p272.CHECKSUM_FILENAME,
        p272.OBSERVATION_FILENAME,
        p272.SOURCE_INDEX_FILENAME,
        "raw/mlb_2026_822834.feed.live.json",
    }
    assert first["raw/mlb_2026_822834.feed.live.json"] == FINAL_FIXTURE.read_bytes()

    checksum_lines = first[p272.CHECKSUM_FILENAME].decode("utf-8").splitlines()
    assert checksum_lines == sorted(checksum_lines, key=lambda line: line.split("  ", 1)[1])
    for line in checksum_lines:
        digest, relative_path = line.split("  ", 1)
        assert digest == p272.sha256_bytes(first[relative_path])


def test_file_mtime_is_excluded_from_all_logical_fingerprints(tmp_path: Path) -> None:
    first_raw = tmp_path / "first.raw.json"
    second_raw = tmp_path / "second.raw.json"
    raw = FINAL_FIXTURE.read_bytes()
    first_raw.write_bytes(raw)
    second_raw.write_bytes(raw)
    os.utime(first_raw, (1, 1))
    os.utime(second_raw, (2_000_000_000, 2_000_000_000))

    first, _ = p272.offline_verify(
        raw_response=first_raw,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=tmp_path / "first-bundle",
    )
    second, _ = p272.offline_verify(
        raw_response=second_raw,
        game_pk=822834,
        observed_at_utc=OBSERVED_AT,
        output_root=tmp_path / "second-bundle",
    )
    assert first["source_fingerprint"] == second["source_fingerprint"]
    assert first["record_fingerprint"] == second["record_fingerprint"]


def test_offline_cli_has_exact_two_modes_and_is_deterministic(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    parser = p272._parser()
    subparser_action = next(
        action for action in parser._actions if isinstance(action, p272.argparse._SubParsersAction)
    )
    assert set(subparser_action.choices) == {"capture", "offline-verify"}

    output_root = tmp_path / "cli-bundle"
    exit_code = p272.main(
        [
            "offline-verify",
            "--game-pk",
            "822834",
            "--raw-response",
            str(FINAL_FIXTURE),
            "--observed-at-utc",
            OBSERVED_AT,
            "--output-root",
            str(output_root),
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert set(result) == {
        "bundle_state",
        "game_id",
        "mode",
        "official_game_pk",
        "record_fingerprint",
        "source_observed_at_utc",
    }
    assert result["mode"] == "offline-verify"
    assert result["bundle_state"] == "CREATED"
    assert result["source_observed_at_utc"] == OBSERVED_AT


def test_observation_schema_is_exact_and_fingerprints_are_content_sensitive() -> None:
    raw = FINAL_FIXTURE.read_bytes()
    first = p272.build_observation_record(raw, 822834, OBSERVED_AT)
    second = p272.build_observation_record(raw, 822834, "2026-07-13T03:00:01Z")
    assert set(first) == p272.OBSERVATION_FIELDS
    assert first["source_fingerprint"] != second["source_fingerprint"]
    assert first["record_fingerprint"] != second["record_fingerprint"]

    tampered = copy.deepcopy(first)
    tampered["away_score"] += 1
    with pytest.raises(p272.P272Error, match="record_fingerprint"):
        p272.validate_observation_record(tampered)


def test_failed_exclusive_stage_write_retains_a_replacement_after_identity_inspection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    staging_parent = tmp_path / "staging-parent"
    staging_parent.mkdir()
    parent_fd = os.open(
        staging_parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        raced = False

        def replace_after_identity_then_fail(_fd: int) -> None:
            nonlocal raced
            assert not raced
            raced = True
            os.rename(
                "artifact.json",
                "artifact-original.json",
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            replacement_fd = os.open(
                "artifact.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=parent_fd,
            )
            try:
                os.write(replacement_fd, b"replacement")
            finally:
                os.close(replacement_fd)
            raise OSError("injected write failure after identity inspection")

        monkeypatch.setattr(p272.os, "fsync", replace_after_identity_then_fail)
        with pytest.raises(OSError, match="after identity inspection"):
            p272._write_regular_file_exclusive_at(
                parent_fd, "artifact.json", b"original"
            )

        assert raced
        assert (staging_parent / "artifact.json").read_bytes() == b"replacement"
        assert (staging_parent / "artifact-original.json").read_bytes() == b"original"
    finally:
        os.close(parent_fd)


@pytest.mark.parametrize(
    "replacement_kind",
    [
        "regular-file",
        "symlink-external-file",
        "symlink-external-directory",
        "unrelated-directory",
        "same-type-empty-directory",
    ],
)
def test_retained_staging_cleanup_never_deletes_a_replaced_pathname(
    tmp_path: Path, replacement_kind: str
) -> None:
    output_parent = tmp_path / "output-parent"
    output_parent.mkdir()
    external_file = tmp_path / "external-file"
    external_file.write_bytes(b"external-file-content")
    external_directory = tmp_path / "external-directory"
    external_directory.mkdir()
    (external_directory / "untouched.txt").write_bytes(b"external-directory-content")
    parent_fd = os.open(output_parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging_fd: int | None = None
    try:
        staging_name = ".bundle.p272-stage-test"
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        staging_identity = p272._filesystem_identity(os.fstat(staging_fd))
        os.rename(
            staging_name,
            f"{staging_name}.original",
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )

        replacement_path = output_parent / staging_name
        if replacement_kind == "regular-file":
            replacement_path.write_bytes(b"replacement-file")
        elif replacement_kind == "symlink-external-file":
            replacement_path.symlink_to(external_file)
        elif replacement_kind == "symlink-external-directory":
            replacement_path.symlink_to(external_directory, target_is_directory=True)
        elif replacement_kind == "unrelated-directory":
            replacement_path.mkdir()
            (replacement_path / "unrelated.txt").write_bytes(b"unrelated-content")
        else:
            replacement_path.mkdir()

        replacement_identity = p272._filesystem_identity(os.lstat(replacement_path))
        replacement_mode = os.lstat(replacement_path).st_mode
        external_file_before = external_file.read_bytes()
        external_directory_before = (external_directory / "untouched.txt").read_bytes()

        first_outcome = p272._cleanup_owned_staging(
            parent_fd,
            staging_name,
            staging_fd,
            staging_identity,
            None,
            None,
            [],
        )
        second_outcome = p272._cleanup_owned_staging(
            parent_fd,
            staging_name,
            staging_fd,
            staging_identity,
            None,
            None,
            [],
        )

        assert first_outcome == p272.CLEANUP_RETAINED_REPLACED
        assert second_outcome == p272.CLEANUP_RETAINED_REPLACED
        assert p272._filesystem_identity(os.lstat(replacement_path)) == replacement_identity
        assert os.lstat(replacement_path).st_mode == replacement_mode
        assert external_file.read_bytes() == external_file_before
        assert (external_directory / "untouched.txt").read_bytes() == external_directory_before
        if replacement_kind == "regular-file":
            assert replacement_path.read_bytes() == b"replacement-file"
        elif replacement_kind == "unrelated-directory":
            assert (replacement_path / "unrelated.txt").read_bytes() == b"unrelated-content"
        elif replacement_kind == "same-type-empty-directory":
            assert list(replacement_path.iterdir()) == []
        else:
            assert replacement_path.is_symlink()
    finally:
        if staging_fd is not None:
            os.close(staging_fd)
        os.close(parent_fd)


def test_staging_failure_reports_retention_without_deleting_a_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "bundle"
    real_write = p272._write_bundle_artifact
    raced = False

    def replace_then_fail(
        staging_fd: int,
        raw_fd: int,
        relative_path: str,
        data: bytes,
    ):
        nonlocal raced
        written = real_write(staging_fd, raw_fd, relative_path, data)
        if not raced:
            raced = True
            os.rename(
                written[1],
                f"{written[1]}.original",
                src_dir_fd=written[0],
                dst_dir_fd=written[0],
            )
            replacement_fd = os.open(
                written[1],
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=written[0],
            )
            try:
                os.write(replacement_fd, b"replacement")
            finally:
                os.close(replacement_fd)
            raise OSError("injected failure after staging replacement")
        return written

    monkeypatch.setattr(p272, "_write_bundle_artifact", replace_then_fail)
    with pytest.raises(
        p272.P272Error,
        match="cleanup=CLEANUP_RETAINED_IDENTITY_UNCERTAIN.*retained_staging=\\.bundle",
    ):
        p272.offline_verify(
            raw_response=FINAL_FIXTURE,
            game_pk=822834,
            observed_at_utc=OBSERVED_AT,
            output_root=output_root,
        )

    staging_paths = list(tmp_path.glob(".bundle.p272-stage-*"))
    assert raced
    assert not output_root.exists()
    assert len(staging_paths) == 1
    assert (staging_paths[0] / "observation.json").read_bytes() == b"replacement"
    assert (staging_paths[0] / "observation.json.original").exists()


def test_cleanup_helpers_contain_no_identity_check_then_pathname_deletion() -> None:
    exclusive_write_source = inspect.getsource(p272._write_regular_file_exclusive_at)
    retention_cleanup_source = inspect.getsource(p272._cleanup_owned_staging)
    for source in (exclusive_write_source, retention_cleanup_source):
        assert "os.unlink" not in source
        assert "os.rmdir" not in source
        assert "os.rename" not in source


@pytest.mark.parametrize(
    "cleanup_outcome",
    [
        p272.CLEANUP_RETAINED_IDENTITY_UNCERTAIN,
        p272.CLEANUP_FAILED,
    ],
)
def test_cli_failure_distinguishes_publication_and_cleanup_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    cleanup_outcome: str,
) -> None:
    def fail_publish(*args, **kwargs):
        raise p272.P272Error("injected publication failure")

    monkeypatch.setattr(p272, "_atomic_publish_noreplace", fail_publish)
    monkeypatch.setattr(
        p272,
        "_cleanup_owned_staging",
        lambda *args, **kwargs: cleanup_outcome,
    )

    exit_code = p272.main(
        [
            "offline-verify",
            "--game-pk",
            "822834",
            "--raw-response",
            str(FINAL_FIXTURE),
            "--observed-at-utc",
            OBSERVED_AT,
            "--output-root",
            str(tmp_path / "bundle"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "Publication failure: injected publication failure" in captured.err
    assert f"cleanup={cleanup_outcome}" in captured.err
    assert "retained_staging=.bundle.p272-stage-" in captured.err
