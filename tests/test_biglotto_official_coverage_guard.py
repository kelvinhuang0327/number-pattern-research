"""唯讀 BIG_LOTTO 官方期數覆蓋 guard 的 focused tests。"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import biglotto_official_membership_projection as membership
from scripts import biglotto_official_coverage_guard as guard


QUERY_UTC = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)


def _result_row(period, draw_date, numbers, special):
    result = list(numbers) + [special]
    return {
        "period": period,
        "lotteryDate": draw_date + "T00:00:00",
        "drawNumberSize": result,
        "drawNumberAppear": result,
    }


def _cutoff_row():
    draw = membership.OFFICIAL_IDENTITIES[-1]
    return _result_row(
        draw.period,
        draw.draw_date,
        draw.numbers,
        draw.special,
    )


def _payload(rows, *, total_size=None, rt_code=0):
    selected_rows = list(rows)
    return {
        "rtCode": rt_code,
        "content": {
            "totalSize": len(selected_rows) if total_size is None else total_size,
            "lotto649Res": selected_rows,
        },
    }


def test_snapshot_identity_comes_from_unchanged_official_projection():
    snapshot = guard.load_snapshot_identity()

    assert snapshot.cutoff_period == "115000095"
    assert snapshot.record_count == 2177
    assert snapshot.dataset_sha256 == (
        "3cf99e7cfabd3071da062d95175b769d5d287b0769570e947bf0a82d1cb9a6b3"
    )
    assert snapshot.computed_sha256 == snapshot.dataset_sha256
    assert snapshot.cutoff_draw_date.isoformat() == "2026-10-09"


def test_latest_completed_period_equal_to_cutoff_is_current():
    report = guard.classify_official_response(
        _payload([_cutoff_row()]), query_utc=QUERY_UTC
    )

    assert report.classification == guard.COVERAGE_CURRENT_TO_CUTOFF
    assert report.official_latest_completed_period == "115000095"
    assert report.confirmed_new_periods == ()
    assert report.snapshot_sha256_verified is True
    assert report.last_audit_execution_utc is None
    assert report.last_audit_execution_status == "NOT_INSPECTED_BY_THIS_TOOL"
    assert report.query_utc == "2026-10-13T06:00:00Z"


def test_new_completed_periods_are_reported_from_source_rows_only():
    rows = [
        _cutoff_row(),
        _result_row("115000096", "2026-10-10", (1, 8, 14, 22, 33, 46), 4),
        _result_row("115000098", "2026-10-12", (2, 9, 17, 24, 38, 47), 5),
        _result_row("115000100", "2026-10-13", (3, 10, 18, 26, 35, 49), 6),
    ]

    report = guard.classify_official_response(_payload(rows), query_utc=QUERY_UTC)

    assert report.classification == guard.COVERAGE_GAP_DETECTED
    assert report.official_latest_completed_period == "115000100"
    assert report.confirmed_new_periods == (
        "115000096",
        "115000098",
        "115000100",
    )
    assert report.confirmed_new_period_count == 3
    assert "115000097" not in report.confirmed_new_periods
    assert "115000099" not in report.confirmed_new_periods


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: row.update(period="11500009X"),
        lambda row: row.update(lotteryDate="2026-02-31T00:00:00"),
    ],
    ids=["malformed-period", "invalid-date"],
)
def test_malformed_period_or_date_is_unverifiable(mutate):
    row = _cutoff_row()
    mutate(row)

    report = guard.classify_official_response(
        _payload([row]), query_utc=QUERY_UTC
    )

    assert report.classification == guard.OFFICIAL_SOURCE_UNVERIFIABLE
    assert report.official_latest_completed_period is None


def test_snapshot_digest_mismatch_cannot_claim_current():
    snapshot = replace(guard.load_snapshot_identity(), computed_sha256="0" * 64)

    report = guard.classify_official_response(
        _payload([_cutoff_row()]), snapshot=snapshot, query_utc=QUERY_UTC
    )

    assert report.classification == guard.OFFICIAL_SOURCE_UNVERIFIABLE
    assert report.snapshot_sha256_verified is False
    assert report.official_latest_completed_period is None


def test_future_uncompleted_period_is_excluded_from_latest_completed_result():
    future_row = {
        "period": "115000096",
        "lotteryDate": "2026-10-14T00:00:00",
        "drawNumberSize": None,
        "drawNumberAppear": None,
    }

    report = guard.classify_official_response(
        _payload([_cutoff_row(), future_row]), query_utc=QUERY_UTC
    )

    assert report.classification == guard.COVERAGE_CURRENT_TO_CUTOFF
    assert report.official_latest_completed_period == "115000095"
    assert report.future_uncompleted_periods_excluded == ("115000096",)


def test_future_dated_result_is_not_claimed_as_completed():
    rows = [
        _cutoff_row(),
        _result_row("115000096", "2026-10-14", (1, 8, 14, 22, 33, 46), 4),
    ]

    report = guard.classify_official_response(_payload(rows), query_utc=QUERY_UTC)

    assert report.classification == guard.OFFICIAL_SOURCE_UNVERIFIABLE
    assert report.official_latest_completed_period is None


def test_missing_or_failed_official_api_response_is_unverifiable(monkeypatch):
    def failed_fetch(_snapshot, _query_time):
        raise OSError("mocked official endpoint failure")

    monkeypatch.setattr(
        guard,
        "_read_last_audit_execution_utc",
        lambda: ("2026-10-12T10:11:04.508684Z", "READ_ONLY_FROM_EXISTING_AUDIT_ARTIFACT"),
    )
    report = guard.run_coverage_check(
        now_utc=QUERY_UTC,
        fetcher=failed_fetch,
    )

    assert report.classification == guard.OFFICIAL_SOURCE_UNVERIFIABLE
    assert report.snapshot_cutoff_period == "115000095"
    assert report.official_latest_completed_period is None
    assert report.reason.startswith("official source request failed:")
    assert report.last_audit_execution_utc == "2026-10-12T10:11:04.508684Z"


def test_last_audit_time_is_read_only_and_separate_from_query_time(tmp_path, monkeypatch):
    audit_path = tmp_path / "randomness_audit_results.json"
    audit_path.write_text(
        json.dumps(
            {
                "current_executable_audit": {
                    "executed_at_utc": "2026-10-12T10:11:04.508684Z"
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "_AUDIT_RESULTS_PATH", audit_path)

    report = guard.run_coverage_check(
        now_utc=QUERY_UTC,
        fetcher=lambda _snapshot, _query_time: _payload([_cutoff_row()]),
    )

    assert report.classification == guard.COVERAGE_CURRENT_TO_CUTOFF
    assert report.last_audit_execution_utc == "2026-10-12T10:11:04.508684Z"
    assert report.last_audit_execution_status == "READ_ONLY_FROM_EXISTING_AUDIT_ARTIFACT"
    assert report.query_utc == "2026-10-13T06:00:00Z"
    assert report.last_audit_execution_utc != report.query_utc


def test_official_request_is_explicit_read_only_and_uses_mocked_response(monkeypatch):
    snapshot = guard.load_snapshot_identity()
    response_payload = _payload([_cutoff_row()])
    body = json.dumps(response_payload).encode("utf-8")
    captured = {}

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json; charset=utf-8"}

        def __init__(self, url):
            self._url = url

        def geturl(self):
            return self._url

        def read(self, _limit):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeOpener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(request.full_url)

    def fake_build_opener(handler):
        assert isinstance(handler, guard._RejectRedirectHandler)
        return FakeOpener()

    monkeypatch.setattr(guard, "build_opener", fake_build_opener)

    response = guard.fetch_official_response(snapshot, QUERY_UTC)

    request = captured["request"]
    parsed_url = urlsplit(request.full_url)
    params = parse_qs(parsed_url.query)
    assert response == response_payload
    assert request.get_method() == "GET"
    assert parsed_url.scheme == "https"
    assert parsed_url.hostname == "api.taiwanlottery.com"
    assert params["month"] == ["2026-10"]
    assert params["endMonth"] == ["2026-10"]
    assert params["pageNum"] == ["1"]
    assert params["pageSize"] == ["5000"]
    assert captured["timeout"] == guard._REQUEST_TIMEOUT_SECONDS


def test_cli_requires_explicit_flag_before_any_official_query(monkeypatch, capsys):
    monkeypatch.setattr(
        guard,
        "run_coverage_check",
        lambda **_kwargs: pytest.fail("network query must require --check-official"),
    )

    assert guard.main([]) == 2
    assert "--check-official" in capsys.readouterr().out


def test_incomplete_api_page_is_unverifiable():
    report = guard.classify_official_response(
        _payload([_cutoff_row()], total_size=2), query_utc=QUERY_UTC
    )

    assert report.classification == guard.OFFICIAL_SOURCE_UNVERIFIABLE
    assert report.official_latest_completed_period is None
