#!/usr/bin/env python3
"""依官方來源暫存指定大樂透期別，並提供 SQLite 原子匯入函式。

暫存流程對 SQLite 僅使用唯讀連線；匯入函式與暫存流程分開，這次只用合成資料庫驗證。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


TASK_ID = "NPR_BIGLOTTO_16_DRAW_STAGED_IMPORT_R1"
API_BASE_URL = "https://api.taiwanlottery.com/TLCAPIWeB"
RESULT_ENDPOINT = API_BASE_URL + "/Lottery/Lotto649Result"
OFFICIAL_RESULT_PAGE = "https://www.taiwanlottery.com/lotto/result/lotto649/"
LOTTERY_TYPE = "BIG_LOTTO"
CANONICAL_VIEW = "draws_big_lotto_canonical_main"
TARGET_DRAW_IDS: Tuple[str, ...] = tuple(
    "115000{:03d}".format(number) for number in range(80, 96)
)
_PERIOD_RE = re.compile(r"^[0-9]{9}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VIEW_FILTER_RE = re.compile(
    r"MAX\s*\(\s*CAST\s*\(\s*j\.value\s+AS\s+INTEGER\s*\)\s*\)"
    r"[\s\S]{0,300}?>\s*25\b",
    re.IGNORECASE,
)


class StagingError(RuntimeError):
    """官方回應、暫存 manifest 或資料庫狀態不符合安全條件時的錯誤。"""


class DuplicateJSONKeyError(StagingError):
    """JSON 物件出現重複 key 時拒絕解析。"""


class DrawConflictError(StagingError):
    """資料庫既有期別內容與官方暫存資料不同時拒絕匯入。"""


@dataclass(frozen=True)
class DrawRecord:
    """已驗證並標準化的一期開獎資料及官方回應摘要。"""

    draw: str
    date: str
    numbers: Tuple[int, ...]
    special: int
    source_sha256: str


def _object_from_unique_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError("duplicate JSON key: {!r}".format(key))
        result[key] = value
    return result


def strict_json_loads(raw: Union[bytes, str], source: str = "JSON") -> Any:
    """解碼 JSON，並拒絕任何巢狀層級的重複 key。"""
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text, object_pairs_hook=_object_from_unique_pairs)
    except DuplicateJSONKeyError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StagingError("{} is not valid UTF-8 JSON: {}".format(source, exc)) from exc


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StagingError("{} must be an integer".format(field))
    return value


def _validate_requested_period(period: str) -> None:
    if not isinstance(period, str) or not _PERIOD_RE.fullmatch(period):
        raise StagingError("period must be a nine-digit string")
    if period not in TARGET_DRAW_IDS:
        raise StagingError("period is outside the authorized 115000080-115000095 range")


def _validate_record(record: DrawRecord) -> None:
    _validate_requested_period(record.draw)
    if not isinstance(record.date, str):
        raise StagingError("draw date must be text")
    try:
        parsed_date = date.fromisoformat(record.date)
    except ValueError as exc:
        raise StagingError("draw date must use YYYY-MM-DD") from exc
    if parsed_date.isoformat() != record.date:
        raise StagingError("draw date must use canonical YYYY-MM-DD form")
    if not isinstance(record.numbers, tuple) or len(record.numbers) != 6:
        raise StagingError("a Big Lotto draw must contain six main numbers")
    values = tuple(_require_int(value, "main number") for value in record.numbers)
    if any(value < 1 or value > 49 for value in values):
        raise StagingError("main numbers must be between 1 and 49")
    if len(set(values)) != 6:
        raise StagingError("main numbers must be unique")
    if values != tuple(sorted(values)):
        raise StagingError("main numbers must be sorted in ascending order")
    special = _require_int(record.special, "special number")
    if special < 1 or special > 49:
        raise StagingError("special number must be between 1 and 49")
    if special in values:
        raise StagingError("special number must differ from all main numbers")
    if not isinstance(record.source_sha256, str) or not _SHA256_RE.fullmatch(
        record.source_sha256
    ):
        raise StagingError("source digest must be a lowercase SHA-256 hex digest")


def validate_records(records: Sequence[DrawRecord]) -> Tuple[DrawRecord, ...]:
    """驗證完整 16 期批次，拒絕重複期號及授權範圍外的期別。"""
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise StagingError("draw batch must be a sequence")
    normalized = tuple(records)
    seen = set()
    for record in normalized:
        if not isinstance(record, DrawRecord):
            raise StagingError("draw batch contains a non-DrawRecord value")
        _validate_record(record)
        if record.draw in seen:
            raise StagingError("duplicate draw period: {}".format(record.draw))
        seen.add(record.draw)
    expected = set(TARGET_DRAW_IDS)
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing or unexpected:
        raise StagingError(
            "batch must contain exactly the target periods; missing={}, unexpected={}".format(
                missing, unexpected
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.draw))


def parse_official_response(expected_period: str, raw_body: bytes) -> DrawRecord:
    """驗證台灣彩券官方 API 對指定期號回傳的單筆資料。"""
    _validate_requested_period(expected_period)
    payload = strict_json_loads(raw_body, source="official API response")
    if not isinstance(payload, dict):
        raise StagingError("official API response must be a JSON object")
    if type(payload.get("rtCode")) is not int or payload["rtCode"] != 0:
        raise StagingError("official API returned a non-success result code")
    content = payload.get("content")
    if not isinstance(content, dict):
        raise StagingError("official API response is missing content")
    total_size = _require_int(content.get("totalSize"), "content.totalSize")
    rows = content.get("lotto649Res")
    if total_size != 1 or not isinstance(rows, list) or len(rows) != 1:
        raise StagingError(
            "exact-period API lookup must return exactly one result, got totalSize={}".format(
                total_size
            )
        )
    source = rows[0]
    if not isinstance(source, dict):
        raise StagingError("official API result row must be a JSON object")
    returned_period = source.get("period")
    if isinstance(returned_period, bool) or not isinstance(returned_period, (int, str)):
        raise StagingError("official API result period must be an integer or digit string")
    if str(returned_period) != expected_period:
        raise StagingError(
            "official API period mismatch: requested {}, received {}".format(
                expected_period, returned_period
            )
        )

    lottery_date = source.get("lotteryDate")
    if not isinstance(lottery_date, str):
        raise StagingError("official API result is missing lotteryDate")
    try:
        draw_date = date.fromisoformat(lottery_date[:10])
    except ValueError as exc:
        raise StagingError("official API lotteryDate is not ISO formatted") from exc
    if len(lottery_date) > 10:
        try:
            datetime.fromisoformat(lottery_date.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StagingError("official API lotteryDate is not ISO formatted") from exc

    draw_size = source.get("drawNumberSize")
    draw_order = source.get("drawNumberAppear")
    if not isinstance(draw_size, list) or len(draw_size) != 7:
        raise StagingError("official API drawNumberSize must contain seven numbers")
    if not isinstance(draw_order, list) or len(draw_order) != 7:
        raise StagingError("official API drawNumberAppear must contain seven numbers")
    size_values = tuple(
        _require_int(value, "drawNumberSize") for value in draw_size
    )
    order_values = tuple(
        _require_int(value, "drawNumberAppear") for value in draw_order
    )
    if any(value < 1 or value > 49 for value in size_values + order_values):
        raise StagingError("official API numbers must be between 1 and 49")
    if len(set(size_values)) != 7 or len(set(order_values)) != 7:
        raise StagingError("official API result contains repeated numbers")
    if sorted(size_values[:6]) != sorted(order_values[:6]):
        raise StagingError("official API sorted and draw-order main numbers disagree")
    if size_values[6] != order_values[6]:
        raise StagingError("official API special number fields disagree")

    return DrawRecord(
        draw=expected_period,
        date=draw_date.isoformat(),
        numbers=tuple(sorted(size_values[:6])),
        special=size_values[6],
        source_sha256=hashlib.sha256(raw_body).hexdigest(),
    )


def fetch_official_draw(period: str, timeout_seconds: float = 20.0) -> DrawRecord:
    """從台灣彩券官方 API 單獨取得指定期號。"""
    _validate_requested_period(period)
    query = urlencode({"period": period, "pageNum": 1, "pageSize": 200})
    request = Request(
        RESULT_ENDPOINT + "?" + query,
        headers={
            "Accept": "application/json",
            "User-Agent": "NPRBiglottoStagedImport/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is not None and status != 200:
                raise StagingError(
                    "official API returned HTTP status {}".format(status)
                )
            body = response.read()
    except StagingError:
        raise
    except Exception as exc:
        raise StagingError(
            "official API request failed for {}: {}".format(period, exc)
        ) from exc
    return parse_official_response(period, body)


def fetch_target_batch(request_delay_seconds: float = 0.15) -> Tuple[DrawRecord, ...]:
    """逐筆取得 16 個授權期號，並要求每一期都有精確匹配。"""
    if not math.isfinite(request_delay_seconds) or request_delay_seconds < 0:
        raise StagingError("request delay must be a finite non-negative number")
    records: List[DrawRecord] = []
    for index, period in enumerate(TARGET_DRAW_IDS):
        if index and request_delay_seconds:
            time.sleep(request_delay_seconds)
        records.append(fetch_official_draw(period))
    return validate_records(records)


def view_risk_report(
    records: Sequence[DrawRecord],
) -> Dict[str, Any]:
    """逐期回報現行 canonical view 的 MAX(main number) > 25 排除風險。"""
    verified = validate_records(records)
    per_draw = []
    at_risk = []
    for record in verified:
        maximum = max(record.numbers)
        included = maximum > 25
        if not included:
            at_risk.append(record.draw)
        per_draw.append(
            {
                "draw": record.draw,
                "max_main_number": maximum,
                "included_by_max_gt_25": included,
            }
        )
    return {
        "target_range": "{}-{}".format(TARGET_DRAW_IDS[0], TARGET_DRAW_IDS[-1]),
        "condition": "MAX(main numbers) > 25",
        "at_risk_draw_ids": at_risk,
        "per_draw": per_draw,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_identity(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _database_identity(path: Path) -> Dict[str, Any]:
    sidecars: Dict[str, Any] = {}
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        sidecars[suffix] = _stat_identity(sidecar) if sidecar.exists() else None
    return {
        "path": str(path),
        "file": _stat_identity(path),
        "sha256": _sha256_file(path),
        "sidecars": sidecars,
    }


def _stored_row_matches(
    row: Tuple[Any, Any, Any, Any], record: DrawRecord
) -> bool:
    _draw, stored_date, numbers_json, stored_special = row
    try:
        stored_numbers = strict_json_loads(
            numbers_json, source="existing draws.numbers"
        )
    except (StagingError, TypeError):
        return False
    if not isinstance(stored_numbers, list) or len(stored_numbers) != 6:
        return False
    try:
        parsed_numbers = tuple(
            _require_int(value, "existing main number") for value in stored_numbers
        )
        parsed_special = _require_int(stored_special, "existing special number")
    except StagingError:
        return False
    return (
        stored_date == record.date
        and len(set(parsed_numbers)) == 6
        and tuple(sorted(parsed_numbers)) == record.numbers
        and parsed_special == record.special
    )


def inspect_database_read_only(
    database_path: Union[str, Path],
    records: Sequence[DrawRecord],
    expected_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """使用唯讀、immutable、private cache 與 query_only 比對指定期別。"""
    verified = validate_records(records)
    source_path = Path(database_path)
    resolved = source_path.resolve(strict=True)
    if not resolved.is_file():
        raise StagingError("database path is not a regular file")
    if expected_sha256 is not None and not _SHA256_RE.fullmatch(expected_sha256):
        raise StagingError("expected database SHA-256 is malformed")
    before = _database_identity(resolved)
    if expected_sha256 and before["sha256"] != expected_sha256:
        raise StagingError(
            "database SHA-256 mismatch: expected {}, received {}".format(
                expected_sha256, before["sha256"]
            )
        )

    uri = "file:{}?mode=ro&immutable=1&cache=private".format(
        quote(str(resolved), safe="/")
    )
    connection = sqlite3.connect(uri, uri=True, isolation_level=None)
    try:
        connection.execute("PRAGMA query_only=ON")
        query_only = connection.execute("PRAGMA query_only").fetchone()[0]
        if query_only != 1:
            raise StagingError("SQLite query_only could not be enabled")
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(draws)")
        }
        if not {"draw", "date", "lottery_type", "numbers", "special"}.issubset(
            columns
        ):
            raise StagingError("database draws table has an incompatible schema")
        view_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
            (CANONICAL_VIEW,),
        ).fetchone()
        if not view_row or not isinstance(view_row[0], str):
            raise StagingError("canonical Big Lotto view is missing")
        if not _VIEW_FILTER_RE.search(view_row[0]):
            raise StagingError(
                "canonical view no longer contains the expected MAX(number) > 25 rule"
            )

        placeholders = ",".join("?" for _ in verified)
        query = (
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type=? AND draw IN ({}) ORDER BY draw".format(
                placeholders
            )
        )
        rows = connection.execute(
            query, (LOTTERY_TYPE,) + tuple(item.draw for item in verified)
        ).fetchall()
    finally:
        connection.close()

    rows_by_draw: Dict[str, List[Tuple[Any, Any, Any, Any]]] = {}
    for row in rows:
        rows_by_draw.setdefault(str(row[0]), []).append(row)
    presence = []
    for record in verified:
        existing = rows_by_draw.get(record.draw, [])
        if not existing:
            status = "MISSING"
        elif len(existing) != 1:
            raise DrawConflictError(
                "database contains duplicate BIG_LOTTO rows for {}".format(record.draw)
            )
        elif not _stored_row_matches(existing[0], record):
            raise DrawConflictError(
                "database content conflicts with official period {}".format(record.draw)
            )
        else:
            status = "PRESENT_IDENTICAL"
        presence.append({"draw": record.draw, "status": status})

    after = _database_identity(resolved)
    if before != after:
        raise StagingError("database or SQLite sidecar identity changed during read")
    return {
        "path": str(resolved),
        "read_only": True,
        "sqlite_uri_options": ["mode=ro", "immutable=1", "cache=private"],
        "query_only": query_only,
        "sha256_before": before["sha256"],
        "sha256_after": after["sha256"],
        "identity_before": before,
        "identity_after": after,
        "target_presence": presence,
        "db_copy": "NONE",
        "db_writes": "NONE",
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def build_manifest(
    records: Sequence[DrawRecord],
    official_fetch_utc: str,
    database_check: Mapping[str, Any],
) -> Dict[str, Any]:
    """建立包含官方回應摘要、DB 身分與 view 風險的暫存 manifest。"""
    verified = validate_records(records)
    try:
        timestamp = datetime.fromisoformat(
            official_fetch_utc.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise StagingError("official fetch time must be an ISO timestamp") from exc
    if timestamp.tzinfo is None:
        raise StagingError("official fetch time must include a timezone")
    manifest: Dict[str, Any] = {
        "task_id": TASK_ID,
        "status": "STAGED_ONLY_NOT_APPLIED",
        "source": {
            "official_result_page": OFFICIAL_RESULT_PAGE,
            "api_endpoint": RESULT_ENDPOINT,
            "lookup": "one GET per exact period with pageNum=1&pageSize=200",
        },
        "official_fetch_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "expected_draw_ids": list(TARGET_DRAW_IDS),
        "verified_draw_ids": [record.draw for record in verified],
        "missing_or_rejected_ids": [],
        "records": [
            {
                "draw": record.draw,
                "date": record.date,
                "numbers": list(record.numbers),
                "special": record.special,
                "source_sha256": record.source_sha256,
            }
            for record in verified
        ],
        "database_check": dict(database_check),
        "current_view_risk_check": view_risk_report(verified),
    }
    manifest["content_sha256"] = hashlib.sha256(
        _canonical_json_bytes(manifest)
    ).hexdigest()
    return manifest


def write_manifest_exclusive(path: Union[str, Path], manifest: Mapping[str, Any]) -> str:
    """以 exclusive create 建立未追蹤 manifest，拒絕覆寫既有檔案。"""
    target = Path(path)
    if not target.parent.exists():
        raise StagingError("manifest parent directory must already exist")
    content = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(target), flags, 0o644)
    with os.fdopen(descriptor, "wb") as file_obj:
        file_obj.write(content)
        file_obj.flush()
        os.fsync(file_obj.fileno())
    return hashlib.sha256(content).hexdigest()


def records_from_manifest(manifest_path: Union[str, Path]) -> Tuple[DrawRecord, ...]:
    """只在 manifest 摘要與期別範圍正確時載入資料。"""
    manifest = strict_json_loads(
        Path(manifest_path).read_bytes(), source="staged manifest"
    )
    if not isinstance(manifest, dict):
        raise StagingError("staged manifest must be a JSON object")
    recorded_digest = manifest.get("content_sha256")
    unsigned = dict(manifest)
    unsigned.pop("content_sha256", None)
    actual_digest = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if recorded_digest != actual_digest:
        raise StagingError("staged manifest content digest mismatch")
    if manifest.get("task_id") != TASK_ID:
        raise StagingError("staged manifest belongs to a different task")
    if manifest.get("expected_draw_ids") != list(TARGET_DRAW_IDS):
        raise StagingError("staged manifest target range does not match this task")
    if manifest.get("missing_or_rejected_ids") != []:
        raise StagingError("staged manifest has missing or rejected periods")
    items = manifest.get("records")
    if not isinstance(items, list):
        raise StagingError("staged manifest records must be a list")
    records: List[DrawRecord] = []
    for item in items:
        if not isinstance(item, dict):
            raise StagingError("staged manifest contains a non-object draw")
        numbers = item.get("numbers")
        if not isinstance(numbers, list):
            raise StagingError("staged manifest numbers must be a list")
        records.append(
            DrawRecord(
                draw=item.get("draw"),
                date=item.get("date"),
                numbers=tuple(numbers),
                special=item.get("special"),
                source_sha256=item.get("source_sha256"),
            )
        )
    verified = validate_records(records)
    if manifest.get("verified_draw_ids") != [record.draw for record in verified]:
        raise StagingError("staged manifest verified-period list is inconsistent")
    return verified


def _existing_rows(
    connection: sqlite3.Connection, records: Sequence[DrawRecord]
) -> Dict[str, List[Tuple[Any, Any, Any, Any]]]:
    placeholders = ",".join("?" for _ in records)
    query = (
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? AND draw IN ({}) ORDER BY draw".format(placeholders)
    )
    rows = connection.execute(
        query, (LOTTERY_TYPE,) + tuple(record.draw for record in records)
    ).fetchall()
    by_draw: Dict[str, List[Tuple[Any, Any, Any, Any]]] = {}
    for row in rows:
        by_draw.setdefault(str(row[0]), []).append(row)
    return by_draw


def apply_batch(
    connection: sqlite3.Connection, records: Sequence[DrawRecord]
) -> Dict[str, Any]:
    """以單一 transaction 匯入完整 16 期批次，確保全成或全數 rollback。

    完全相同的既有資料可安全重跑；內容衝突或 SQL 錯誤都拒絕整批，
    不使用忽略衝突的 INSERT，也不逐筆 commit。
    """
    verified = validate_records(records)
    if connection.in_transaction:
        raise StagingError("apply_batch requires a connection with no open transaction")
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    if query_only:
        raise StagingError("apply_batch refuses a query_only connection")
    connection.execute("BEGIN IMMEDIATE")
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(draws)")
        }
        if not {"draw", "date", "lottery_type", "numbers", "special"}.issubset(
            columns
        ):
            raise StagingError("database draws table has an incompatible schema")
        by_draw = _existing_rows(connection, verified)
        to_insert: List[DrawRecord] = []
        identical = 0
        for record in verified:
            existing = by_draw.get(record.draw, [])
            if not existing:
                to_insert.append(record)
            elif len(existing) != 1:
                raise DrawConflictError(
                    "database contains duplicate BIG_LOTTO rows for {}".format(
                        record.draw
                    )
                )
            elif not _stored_row_matches(existing[0], record):
                raise DrawConflictError(
                    "database content conflicts with official period {}".format(
                        record.draw
                    )
                )
            else:
                identical += 1

        for record in to_insert:
            connection.execute(
                "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    record.draw,
                    record.date,
                    LOTTERY_TYPE,
                    json.dumps(list(record.numbers), separators=(",", ":")),
                    record.special,
                ),
            )
        connection.commit()
        return {
            "inserted_count": len(to_insert),
            "inserted_draw_ids": [record.draw for record in to_insert],
            "identical_existing_count": identical,
        }
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise


def _stage(args: argparse.Namespace) -> Dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    records = fetch_target_batch(request_delay_seconds=args.request_delay)
    database_check = inspect_database_read_only(
        args.database, records, expected_sha256=args.expected_db_sha256
    )
    manifest = build_manifest(records, fetched_at, database_check)
    manifest_sha256 = write_manifest_exclusive(args.manifest, manifest)
    risk = manifest["current_view_risk_check"]
    return {
        "task_id": TASK_ID,
        "status": manifest["status"],
        "manifest_path": str(Path(args.manifest).resolve()),
        "manifest_sha256": manifest_sha256,
        "staged_record_count": len(records),
        "expected_draw_ids": list(TARGET_DRAW_IDS),
        "verified_draw_ids": [record.draw for record in records],
        "missing_or_rejected_ids": [],
        "period_exact_match": "PASS",
        "date_and_number_validation": "PASS",
        "db_read_only": "PASS",
        "db_sha256_before": database_check["sha256_before"],
        "db_sha256_after": database_check["sha256_after"],
        "db_copy": "NONE",
        "db_writes": "NONE",
        "target_presence": database_check["target_presence"],
        "at_risk_draw_ids": risk["at_risk_draw_ids"],
        "per_draw_view_risk": risk["per_draw"],
        "records": [
            {
                "draw": record.draw,
                "date": record.date,
                "numbers": list(record.numbers),
                "special": record.special,
                "source_sha256": record.source_sha256,
            }
            for record in records
        ],
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """建立唯讀 staging CLI 的參數解析器。"""
    parser = argparse.ArgumentParser(
        description="Fetch and stage the exact official Big Lotto periods 115000080-115000095."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser(
        "stage",
        help="fetch each official period and compare the authorized DB read-only",
    )
    stage.add_argument("--database", required=True, help="SQLite DB to inspect read-only")
    stage.add_argument(
        "--expected-db-sha256",
        required=True,
        help="expected database identity SHA-256",
    )
    stage.add_argument(
        "--manifest",
        required=True,
        help="new manifest path; existing files are never overwritten",
    )
    stage.add_argument(
        "--request-delay",
        type=float,
        default=0.15,
        help="seconds between exact-period API requests (default: 0.15)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """執行唯讀暫存命令並輸出可機器解析的驗證摘要。"""
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        result = _stage(args)
    except (StagingError, sqlite3.Error, OSError) as exc:
        print("暫存失敗：{}".format(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
