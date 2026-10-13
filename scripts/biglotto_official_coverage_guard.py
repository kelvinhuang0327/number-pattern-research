#!/usr/bin/env python3
"""唯讀比對台灣彩券大樂透最新已完成期數與固定官方身分快照。

本工具不連接資料庫，只唯讀取得既有 audit artifact 的執行時間，且不會更新
官方身分投影或 audit artifact。只有明確傳入 ``--check-official`` 才會向
官方 API 發出一次唯讀 GET。
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

try:
    if __package__:
        from . import biglotto_official_membership_projection as membership
    else:  # 支援直接執行 scripts/ 內的唯讀工具。
        import biglotto_official_membership_projection as membership
except Exception as exc:  # 投影本身無法載入時仍要 fail closed 並回報狀態。
    membership = None  # type: ignore[assignment]
    _MEMBERSHIP_IMPORT_FAILURE = "{}: {}".format(type(exc).__name__, exc)
else:
    _MEMBERSHIP_IMPORT_FAILURE = None


COVERAGE_CURRENT_TO_CUTOFF = "COVERAGE_CURRENT_TO_CUTOFF"
COVERAGE_GAP_DETECTED = "COVERAGE_GAP_DETECTED"
OFFICIAL_SOURCE_UNVERIFIABLE = "OFFICIAL_SOURCE_UNVERIFIABLE"

_PERIOD_RE = re.compile(r"^[0-9]{9}$")
_PAGE_SIZE = 5000
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 20.0
_TAIPEI = ZoneInfo("Asia/Taipei")
_AUDIT_RESULTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "outputs"
    / "randomness_audit"
    / "randomness_audit_results.json"
)


class CoverageError(RuntimeError):
    """官方來源或固定快照無法可靠核實。"""


@dataclass(frozen=True)
class SnapshotIdentity:
    """從既有官方投影讀出的快照識別，不另存第二份開獎資料。"""

    cutoff_period: str
    record_count: int
    dataset_sha256: str
    computed_sha256: str
    cutoff_draw_date: date
    cutoff_numbers: Tuple[int, ...]
    cutoff_special: int


@dataclass(frozen=True)
class VerifiedDraw:
    period: str
    draw_date: date
    numbers: Tuple[int, ...]
    special: int


@dataclass(frozen=True)
class CoverageReport:
    classification: str
    query_utc: str
    snapshot_cutoff_period: Optional[str]
    snapshot_record_count: Optional[int]
    snapshot_dataset_sha256: Optional[str]
    snapshot_sha256_verified: bool
    official_latest_completed_period: Optional[str]
    official_latest_completed_draw_date: Optional[str]
    confirmed_new_periods: Tuple[str, ...]
    confirmed_new_period_count: int
    future_uncompleted_periods_excluded: Tuple[str, ...]
    query_month_start: Optional[str]
    query_month_end: Optional[str]
    source_page: Optional[str]
    source_endpoint: Optional[str]
    last_audit_execution_utc: Optional[str]
    last_audit_execution_status: str
    reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification,
            "coverage_query_utc": self.query_utc,
            "last_audit_execution_utc": self.last_audit_execution_utc,
            "last_audit_execution_status": self.last_audit_execution_status,
            "snapshot_cutoff_period": self.snapshot_cutoff_period,
            "snapshot_record_count": self.snapshot_record_count,
            "snapshot_dataset_sha256": self.snapshot_dataset_sha256,
            "snapshot_sha256_verified": self.snapshot_sha256_verified,
            "official_latest_completed_period": self.official_latest_completed_period,
            "official_latest_completed_draw_date": self.official_latest_completed_draw_date,
            "confirmed_new_periods": list(self.confirmed_new_periods),
            "confirmed_new_period_count": self.confirmed_new_period_count,
            "future_uncompleted_periods_excluded": list(
                self.future_uncompleted_periods_excluded
            ),
            "query_month_start": self.query_month_start,
            "query_month_end": self.query_month_end,
            "source_page": self.source_page,
            "source_endpoint": self.source_endpoint,
            "reason": self.reason,
        }


def _normalize_query_time(value: Optional[datetime]) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise CoverageError("query time must include a UTC offset")
    return result.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_snapshot_identity() -> SnapshotIdentity:
    """驗證並讀取已提交 projection 的 cutoff、筆數與 digest。"""
    if membership is None:
        raise CoverageError(
            "official identity projection could not be loaded: {}".format(
                _MEMBERSHIP_IMPORT_FAILURE
            )
        )
    try:
        identities = tuple(membership.OFFICIAL_IDENTITIES)
        if not identities:
            raise CoverageError("official identity projection is empty")
        declared_sha256 = membership.OFFICIAL_DATASET_SHA256
        computed_sha256 = membership.identity_dataset_sha256(identities)
        cutoff_period = membership.OFFICIAL_AS_OF_PERIOD
        if computed_sha256 != declared_sha256:
            raise CoverageError("official identity projection SHA-256 mismatch")
        if identities[-1].period != cutoff_period:
            raise CoverageError("official identity projection cutoff mismatch")
        if not _PERIOD_RE.fullmatch(str(cutoff_period)):
            raise CoverageError("official identity projection cutoff is malformed")
        cutoff_draw = identities[-1]
        cutoff_date = date.fromisoformat(cutoff_draw.draw_date)
        return SnapshotIdentity(
            cutoff_period=str(cutoff_period),
            record_count=len(identities),
            dataset_sha256=str(declared_sha256),
            computed_sha256=str(computed_sha256),
            cutoff_draw_date=cutoff_date,
            cutoff_numbers=tuple(cutoff_draw.numbers),
            cutoff_special=int(cutoff_draw.special),
        )
    except CoverageError:
        raise
    except Exception as exc:
        raise CoverageError(
            "official identity projection is unverifiable: {}: {}".format(
                type(exc).__name__, exc
            )
        ) from exc


def _query_window(snapshot: SnapshotIdentity, query_time: datetime) -> Tuple[str, str]:
    start_month = snapshot.cutoff_draw_date.strftime("%Y-%m")
    end_month = query_time.astimezone(_TAIPEI).date().strftime("%Y-%m")
    if end_month < start_month:
        raise CoverageError("query date precedes the fixed snapshot cutoff")
    return start_month, end_month


def _official_endpoint() -> str:
    if membership is None:
        raise CoverageError("official identity projection is unavailable")
    endpoint = membership.OFFICIAL_SOURCE_ENDPOINT
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.taiwanlottery.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/TLCAPIWeB/Lottery/Lotto649Result"
        or parsed.query
        or parsed.fragment
    ):
        raise CoverageError("official API endpoint is outside the approved source")
    return endpoint


class _RejectRedirectHandler(HTTPRedirectHandler):
    """拒絕轉址，避免把官方查詢導向未驗證來源。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _response_content_type(response: Any) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get_content_type", None)
    if callable(getter):
        return str(getter()).split(";", 1)[0].strip().lower()
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        value = get_header("Content-Type")
        if value is not None:
            return str(value).split(";", 1)[0].strip().lower()
    return None


def _unique_json_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CoverageError("official API JSON contains a duplicate key")
        result[key] = value
    return result


def _read_last_audit_execution_utc() -> Tuple[Optional[str], str]:
    """唯讀取出既有 audit artifact 的實際執行時間，不執行或更新 audit。"""
    try:
        document = json.loads(
            _AUDIT_RESULTS_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
        if not isinstance(document, dict):
            raise CoverageError("audit artifact must be a JSON object")
        current = document.get("current_executable_audit")
        if not isinstance(current, dict):
            raise CoverageError("audit artifact is missing current execution metadata")
        value = current.get("executed_at_utc")
        if not isinstance(value, str) or not value.endswith("Z"):
            raise CoverageError("audit execution time must use UTC Z notation")
        executed_at = datetime.fromisoformat(value[:-1] + "+00:00")
        if executed_at.tzinfo is None or executed_at.utcoffset() != timezone.utc.utcoffset(executed_at):
            raise CoverageError("audit execution time is not UTC")
        return _format_utc(executed_at), "READ_ONLY_FROM_EXISTING_AUDIT_ARTIFACT"
    except Exception:
        return None, "UNAVAILABLE_OR_INVALID"


def _decode_json(raw: bytes) -> Any:
    if not isinstance(raw, bytes) or not raw:
        raise CoverageError("official API response body is empty or not bytes")
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise CoverageError("official API response exceeded the size limit")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object)
    except CoverageError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoverageError("official API response is not valid UTF-8 JSON") from exc


def _validate_official_response_url(response: Any, requested_url: str) -> None:
    geturl = getattr(response, "geturl", None)
    final_url = geturl() if callable(geturl) else None
    if final_url != requested_url:
        raise CoverageError("official API response URL changed or is unverifiable")


def fetch_official_response(
    snapshot: SnapshotIdentity,
    query_time: datetime,
    *,
    opener_factory: Optional[Callable[..., Any]] = None,
) -> Any:
    """對官方 API 執行單次明確的唯讀查詢，回傳尚未信任的 JSON 物件。"""
    query_time = _normalize_query_time(query_time)
    start_month, end_month = _query_window(snapshot, query_time)
    endpoint = _official_endpoint()
    query = urlencode(
        {
            "period": "",
            "month": start_month,
            "endMonth": end_month,
            "pageNum": 1,
            "pageSize": _PAGE_SIZE,
        }
    )
    requested_url = endpoint + "?" + query
    request = Request(
        requested_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "NPRBiglottoCoverageGuard/1.0",
            "Referer": membership.OFFICIAL_SOURCE_PAGE,
        },
        method="GET",
    )
    factory = build_opener if opener_factory is None else opener_factory
    try:
        opener = factory(_RejectRedirectHandler())
        with opener.open(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            if getattr(response, "status", None) != 200:
                raise CoverageError("official API did not return HTTP 200")
            _validate_official_response_url(response, requested_url)
            if _response_content_type(response) != "application/json":
                raise CoverageError("official API response is not application/json")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except CoverageError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise CoverageError(
            "official API request failed: {}".format(type(exc).__name__)
        ) from exc
    except Exception as exc:
        raise CoverageError(
            "official API request failed: {}".format(type(exc).__name__)
        ) from exc
    return _decode_json(raw)


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoverageError("official API {} must be an integer".format(field))
    return value


def _parse_period(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise CoverageError("official API period is missing or malformed")
    period = str(value)
    if not _PERIOD_RE.fullmatch(period):
        raise CoverageError("official API period is not a nine-digit period")
    return period


def _parse_draw_date(value: Any) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise CoverageError("official API lotteryDate is missing or malformed")
    date_text = value[:10]
    try:
        parsed_date = date.fromisoformat(date_text)
    except ValueError as exc:
        raise CoverageError("official API lotteryDate is invalid") from exc
    if parsed_date.isoformat() != date_text:
        raise CoverageError("official API lotteryDate is not canonical ISO format")
    if len(value) > 10:
        if value[10] != "T":
            raise CoverageError("official API lotteryDate has an invalid suffix")
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CoverageError("official API lotteryDate timestamp is invalid") from exc
    return parsed_date


def _parse_draw_numbers(row: Dict[str, Any]) -> Optional[Tuple[Tuple[int, ...], int]]:
    raw_size = row.get("drawNumberSize")
    raw_order = row.get("drawNumberAppear")
    if raw_size in (None, []) and raw_order in (None, []):
        return None
    if not isinstance(raw_size, list) or len(raw_size) != 7:
        raise CoverageError("official API drawNumberSize must contain seven numbers")
    if not isinstance(raw_order, list) or len(raw_order) != 7:
        raise CoverageError("official API drawNumberAppear must contain seven numbers")
    size_values = tuple(
        _require_int(value, "drawNumberSize") for value in raw_size
    )
    order_values = tuple(
        _require_int(value, "drawNumberAppear") for value in raw_order
    )
    if any(value < 1 or value > 49 for value in size_values + order_values):
        raise CoverageError("official API draw numbers are outside 1-49")
    if len(set(size_values)) != 7 or len(set(order_values)) != 7:
        raise CoverageError("official API draw result contains repeated numbers")
    if sorted(size_values[:6]) != sorted(order_values[:6]):
        raise CoverageError("official API main-number fields disagree")
    if size_values[6] != order_values[6]:
        raise CoverageError("official API special-number fields disagree")
    return tuple(sorted(size_values[:6])), size_values[6]


def _parse_completed_draws(
    payload: Any,
    snapshot: SnapshotIdentity,
    query_time: datetime,
    start_month: str,
    end_month: str,
) -> Tuple[Tuple[VerifiedDraw, ...], Tuple[str, ...]]:
    if not isinstance(payload, dict):
        raise CoverageError("official API response must be a JSON object")
    if type(payload.get("rtCode")) is not int or payload["rtCode"] != 0:
        raise CoverageError("official API returned a non-success result code")
    content = payload.get("content")
    if not isinstance(content, dict):
        raise CoverageError("official API response is missing content")
    total_size = _require_int(content.get("totalSize"), "content.totalSize")
    rows = content.get("lotto649Res")
    if total_size < 0 or total_size > _PAGE_SIZE:
        raise CoverageError("official API response exceeds the complete-page limit")
    if not isinstance(rows, list) or len(rows) != total_size:
        raise CoverageError("official API result page is incomplete")
    for field, expected in (("pageNum", 1), ("pageSize", _PAGE_SIZE)):
        if field in content and _require_int(content[field], "content." + field) != expected:
            raise CoverageError("official API response pagination does not match request")

    today_taipei = query_time.astimezone(_TAIPEI).date()
    parsed: list[VerifiedDraw] = []
    future_uncompleted: list[str] = []
    seen_periods = set()
    for row in rows:
        if not isinstance(row, dict):
            raise CoverageError("official API result row must be an object")
        period = _parse_period(row.get("period"))
        if period in seen_periods:
            raise CoverageError("official API returned a duplicate period")
        seen_periods.add(period)
        draw_date = _parse_draw_date(row.get("lotteryDate"))
        month = draw_date.strftime("%Y-%m")
        if month < start_month or month > end_month:
            raise CoverageError("official API result date is outside the requested range")

        if period > snapshot.cutoff_period and draw_date <= snapshot.cutoff_draw_date:
            raise CoverageError("official API period/date order conflicts with the snapshot")
        if period < snapshot.cutoff_period and draw_date > snapshot.cutoff_draw_date:
            raise CoverageError("official API period/date order conflicts with the snapshot")

        numbers = _parse_draw_numbers(row)
        if draw_date > today_taipei:
            if numbers is not None:
                raise CoverageError("future-dated draw cannot be treated as completed")
            future_uncompleted.append(period)
            continue
        if numbers is None:
            raise CoverageError("official API row has no announced draw result")
        parsed.append(
            VerifiedDraw(
                period=period,
                draw_date=draw_date,
                numbers=numbers[0],
                special=numbers[1],
            )
        )

    parsed.sort(key=lambda draw: int(draw.period))
    for previous, current in zip(parsed, parsed[1:]):
        if current.draw_date < previous.draw_date:
            raise CoverageError("official API periods and dates are out of order")

    cutoff_rows = [draw for draw in parsed if draw.period == snapshot.cutoff_period]
    if len(cutoff_rows) != 1:
        raise CoverageError("official API did not verify the fixed snapshot cutoff")
    cutoff_row = cutoff_rows[0]
    if (
        cutoff_row.draw_date != snapshot.cutoff_draw_date
        or cutoff_row.numbers != snapshot.cutoff_numbers
        or cutoff_row.special != snapshot.cutoff_special
    ):
        raise CoverageError("official API cutoff result conflicts with fixed snapshot")
    if not parsed:
        raise CoverageError("official API returned no completed draws")
    if int(parsed[-1].period) < int(snapshot.cutoff_period):
        raise CoverageError("official API latest completed period precedes snapshot cutoff")
    return tuple(parsed), tuple(sorted(future_uncompleted, key=int))


def _make_report(
    classification: str,
    query_time: datetime,
    *,
    snapshot: Optional[SnapshotIdentity] = None,
    digest_verified: bool = False,
    latest: Optional[VerifiedDraw] = None,
    new_periods: Tuple[str, ...] = (),
    future_periods: Tuple[str, ...] = (),
    month_start: Optional[str] = None,
    month_end: Optional[str] = None,
    last_audit_execution_utc: Optional[str] = None,
    last_audit_execution_status: str = "NOT_INSPECTED_BY_THIS_TOOL",
    reason: Optional[str] = None,
) -> CoverageReport:
    source_page = (
        membership.OFFICIAL_SOURCE_PAGE
        if membership is not None
        else None
    )
    source_endpoint = (
        membership.OFFICIAL_SOURCE_ENDPOINT
        if membership is not None
        else None
    )
    return CoverageReport(
        classification=classification,
        query_utc=_format_utc(query_time),
        snapshot_cutoff_period=snapshot.cutoff_period if snapshot else None,
        snapshot_record_count=snapshot.record_count if snapshot else None,
        snapshot_dataset_sha256=snapshot.dataset_sha256 if snapshot else None,
        snapshot_sha256_verified=digest_verified,
        official_latest_completed_period=latest.period if latest else None,
        official_latest_completed_draw_date=(
            latest.draw_date.isoformat() if latest else None
        ),
        confirmed_new_periods=new_periods,
        confirmed_new_period_count=len(new_periods),
        future_uncompleted_periods_excluded=future_periods,
        query_month_start=month_start,
        query_month_end=month_end,
        source_page=source_page,
        source_endpoint=source_endpoint,
        last_audit_execution_utc=last_audit_execution_utc,
        last_audit_execution_status=last_audit_execution_status,
        reason=reason,
    )


def classify_official_response(
    payload: Any,
    *,
    snapshot: Optional[SnapshotIdentity] = None,
    query_utc: Optional[datetime] = None,
    computed_snapshot_sha256: Optional[str] = None,
    last_audit_execution_utc: Optional[str] = None,
    last_audit_execution_status: str = "NOT_INSPECTED_BY_THIS_TOOL",
) -> CoverageReport:
    """驗證 mocked 或官方回應並分類；任何不確定狀態都不會成為 CURRENT。"""
    try:
        query_time = _normalize_query_time(query_utc)
    except CoverageError as exc:
        fallback_time = datetime.now(timezone.utc)
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            fallback_time,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason=str(exc),
        )
    try:
        selected_snapshot = load_snapshot_identity() if snapshot is None else snapshot
    except CoverageError as exc:
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason=str(exc),
        )

    digest = (
        selected_snapshot.computed_sha256
        if computed_snapshot_sha256 is None
        else computed_snapshot_sha256
    )
    if digest != selected_snapshot.dataset_sha256:
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            snapshot=selected_snapshot,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason="official identity snapshot SHA-256 mismatch",
        )

    try:
        month_start, month_end = _query_window(selected_snapshot, query_time)
        completed, future_periods = _parse_completed_draws(
            payload,
            selected_snapshot,
            query_time,
            month_start,
            month_end,
        )
        latest = completed[-1]
        new_periods = tuple(
            draw.period
            for draw in completed
            if int(draw.period) > int(selected_snapshot.cutoff_period)
        )
        if latest.period == selected_snapshot.cutoff_period:
            classification = COVERAGE_CURRENT_TO_CUTOFF
        elif int(latest.period) > int(selected_snapshot.cutoff_period):
            classification = COVERAGE_GAP_DETECTED
        else:
            raise CoverageError("official latest period is below the fixed cutoff")
        return _make_report(
            classification,
            query_time,
            snapshot=selected_snapshot,
            digest_verified=True,
            latest=latest,
            new_periods=new_periods,
            future_periods=future_periods,
            month_start=month_start,
            month_end=month_end,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
        )
    except CoverageError as exc:
        try:
            month_start, month_end = _query_window(selected_snapshot, query_time)
        except CoverageError:
            month_start, month_end = None, None
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            snapshot=selected_snapshot,
            digest_verified=True,
            month_start=month_start,
            month_end=month_end,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason=str(exc),
        )


def run_coverage_check(
    *,
    now_utc: Optional[datetime] = None,
    snapshot: Optional[SnapshotIdentity] = None,
    fetcher: Optional[Callable[[SnapshotIdentity, datetime], Any]] = None,
    opener_factory: Optional[Callable[..., Any]] = None,
) -> CoverageReport:
    """執行官方覆蓋查詢；呼叫者須明確選擇此函式或 CLI 旗標。"""
    try:
        query_time = _normalize_query_time(now_utc)
    except CoverageError as exc:
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            datetime.now(timezone.utc),
            reason=str(exc),
        )
    last_audit_execution_utc, last_audit_execution_status = (
        _read_last_audit_execution_utc()
    )
    try:
        selected_snapshot = load_snapshot_identity() if snapshot is None else snapshot
    except CoverageError as exc:
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason=str(exc),
        )
    if selected_snapshot.computed_sha256 != selected_snapshot.dataset_sha256:
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            snapshot=selected_snapshot,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason="official identity snapshot SHA-256 mismatch",
        )
    try:
        if fetcher is None:
            payload = fetch_official_response(
                selected_snapshot,
                query_time,
                opener_factory=opener_factory,
            )
        else:
            payload = fetcher(selected_snapshot, query_time)
    except Exception as exc:
        try:
            month_start, month_end = _query_window(selected_snapshot, query_time)
        except CoverageError:
            month_start, month_end = None, None
        return _make_report(
            OFFICIAL_SOURCE_UNVERIFIABLE,
            query_time,
            snapshot=selected_snapshot,
            digest_verified=True,
            month_start=month_start,
            month_end=month_end,
            last_audit_execution_utc=last_audit_execution_utc,
            last_audit_execution_status=last_audit_execution_status,
            reason="official source request failed: {}".format(type(exc).__name__),
        )
    return classify_official_response(
        payload,
        snapshot=selected_snapshot,
        query_utc=query_time,
        last_audit_execution_utc=last_audit_execution_utc,
        last_audit_execution_status=last_audit_execution_status,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="唯讀檢查大樂透固定官方身分快照是否涵蓋最新已完成期數。"
    )
    parser.add_argument(
        "--check-official",
        action="store_true",
        help="明確向台灣彩券官方 API 發出唯讀查詢；不連接資料庫。",
    )
    args = parser.parse_args(argv)
    if not args.check_official:
        parser.print_help()
        return 2

    report = run_coverage_check()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if report.classification == COVERAGE_CURRENT_TO_CUTOFF:
        return 0
    if report.classification == COVERAGE_GAP_DETECTED:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
