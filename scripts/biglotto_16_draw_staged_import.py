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

if __package__:
    from . import biglotto_official_membership_projection as membership
else:  # 支援既有直接執行 staging 腳本的入口。
    import biglotto_official_membership_projection as membership


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
_LEGACY_CANONICAL_VIEW_SQL = """CREATE VIEW draws_big_lotto_canonical_main AS
SELECT d.*
FROM draws AS d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND CAST(d.draw AS INTEGER) < 115000080
  AND (
      SELECT MAX(CAST(j.value AS INTEGER))
      FROM json_each(d.numbers) AS j
  ) > 25
"""


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


def _sql_fingerprint(sql: str) -> str:
    """Return a whitespace-normalized digest for a trusted view definition."""
    normalized = " ".join(sql.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_official_identity_tables_read_only(
    connection: sqlite3.Connection,
) -> None:
    """Verify that a new canonical view is bound to the complete pinned dataset."""
    expected_schemas = {
        membership.IDENTITY_TABLE: (
            "period",
            "draw_date",
            "numbers_json",
            "numbers_csv",
            "special",
            "dataset_sha256",
        ),
        membership.MANIFEST_TABLE: (
            "singleton",
            "source_page",
            "source_endpoint",
            "query_scope",
            "as_of_period",
            "official_record_count",
            "normalized_sha256",
        ),
    }
    for table_name, expected_columns in expected_schemas.items():
        object_row = connection.execute(
            "SELECT type FROM sqlite_master WHERE name=?", (table_name,)
        ).fetchone()
        if object_row != ("table",):
            raise StagingError(
                "official identity object {} is missing or is not a table".format(
                    table_name
                )
            )
        actual_columns = tuple(
            row[1]
            for row in connection.execute(
                "PRAGMA table_info({})".format(table_name)
            ).fetchall()
        )
        if actual_columns != expected_columns:
            raise StagingError(
                "official identity table {} has an incompatible schema".format(
                    table_name
                )
            )

    expected_manifest = (
        1,
        membership.OFFICIAL_SOURCE_PAGE,
        membership.OFFICIAL_SOURCE_ENDPOINT,
        membership.OFFICIAL_SOURCE_QUERY,
        membership.OFFICIAL_AS_OF_PERIOD,
        len(membership.OFFICIAL_IDENTITIES),
        membership.OFFICIAL_DATASET_SHA256,
    )
    manifest_rows = connection.execute(
        "SELECT singleton, source_page, source_endpoint, query_scope, as_of_period, "
        "official_record_count, normalized_sha256 FROM {} ORDER BY singleton".format(
            membership.MANIFEST_TABLE
        )
    ).fetchall()
    if manifest_rows != [expected_manifest]:
        raise StagingError("official identity manifest does not match its pinned digest")

    expected_identity_rows = tuple(
        (
            draw.period,
            draw.draw_date,
            json.dumps(list(draw.numbers), separators=(",", ":")),
            ",".join(str(number) for number in draw.numbers),
            draw.special,
            membership.OFFICIAL_DATASET_SHA256,
        )
        for draw in membership.OFFICIAL_IDENTITIES
    )
    identity_rows = tuple(
        connection.execute(
            "SELECT period, draw_date, numbers_json, numbers_csv, special, dataset_sha256 "
            "FROM {} ORDER BY period".format(membership.IDENTITY_TABLE)
        ).fetchall()
    )
    if identity_rows != expected_identity_rows:
        raise StagingError("official identity rows do not match the pinned dataset")


def _validate_canonical_view_read_only(connection: sqlite3.Connection) -> str:
    """Accept only the exact known legacy view or digest-bound official view."""
    view_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
        (CANONICAL_VIEW,),
    ).fetchone()
    if not view_row or not isinstance(view_row[0], str):
        raise StagingError("canonical Big Lotto view is missing")

    actual_fingerprint = _sql_fingerprint(view_row[0])
    if actual_fingerprint == _sql_fingerprint(_LEGACY_CANONICAL_VIEW_SQL):
        return "LEGACY_MAX_MAIN_GT_25"
    if actual_fingerprint == _sql_fingerprint(membership.CREATE_VIEW_SQL):
        _validate_official_identity_tables_read_only(connection)
        return "OFFICIAL_IDENTITY_SHA256"
    raise StagingError("canonical Big Lotto view definition is not recognized")


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
        canonical_view_kind = _validate_canonical_view_read_only(connection)

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
        "canonical_view_kind": canonical_view_kind,
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


def _records_from_manifest_object(manifest: Any) -> Tuple[DrawRecord, ...]:
    if not isinstance(manifest, dict):
        raise StagingError("staged manifest must be a JSON object")
    recorded_digest = manifest.get("content_sha256")
    unsigned = dict(manifest)
    unsigned.pop("content_sha256", None)
    actual_digest = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    if recorded_digest != actual_digest:
        raise StagingError("staged manifest self-calculated content digest mismatch")
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


def records_from_manifest(manifest_path: Union[str, Path]) -> Tuple[DrawRecord, ...]:
    """檢查 manifest 自算的內容摘要與固定期別範圍後載入開獎資料。

    內容摘要可發現意外的不一致，但不是數位簽章或外部核准。套用資料
    時，呼叫端還必須提供完整 manifest 檔案的獨立 SHA-256 pin。

    範例::

        records = records_from_manifest("/tmp/approved-stage.json")
    """
    manifest = strict_json_loads(
        Path(manifest_path).read_bytes(), source="staged manifest"
    )
    return _records_from_manifest_object(manifest)


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


def _plan_batch_import(
    connection: sqlite3.Connection, records: Sequence[DrawRecord]
) -> Tuple[Tuple[DrawRecord, ...], int]:
    """Read existing staged rows and return inserts plus identical-row count."""
    by_draw = _existing_rows(connection, records)
    to_insert: List[DrawRecord] = []
    identical = 0
    for record in records:
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
    return tuple(to_insert), identical


def apply_batch(
    connection: sqlite3.Connection,
    records: Sequence[DrawRecord],
    *,
    manage_transaction: bool = True,
) -> Dict[str, Any]:
    """以單一 transaction 匯入完整 16 期批次，確保全成或全數 rollback。

    完全相同的既有資料可安全重跑；內容衝突或 SQL 錯誤都拒絕整批，
    不使用忽略衝突的 INSERT，也不逐筆 commit。預設由本函式管理交易；
    外層整合交易可先 BEGIN 再傳入 ``manage_transaction=False``，由外層
    負責提交或回滾。

    範例::

        result = apply_batch(connection, records)
    """
    verified = validate_records(records)
    if manage_transaction and connection.in_transaction:
        raise StagingError("apply_batch requires a connection with no open transaction")
    if not manage_transaction and not connection.in_transaction:
        raise StagingError("manage_transaction=False requires an open transaction")
    query_only = connection.execute("PRAGMA query_only").fetchone()[0]
    if query_only:
        raise StagingError("apply_batch refuses a query_only connection")
    if manage_transaction:
        connection.execute("BEGIN IMMEDIATE")
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(draws)")
        }
        if not {"draw", "date", "lottery_type", "numbers", "special"}.issubset(
            columns
        ):
            raise StagingError("database draws table has an incompatible schema")
        to_insert, identical = _plan_batch_import(connection, verified)

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
        if manage_transaction:
            connection.commit()
        return {
            "inserted_count": len(to_insert),
            "inserted_draw_ids": [record.draw for record in to_insert],
            "identical_existing_count": identical,
        }
    except BaseException:
        if manage_transaction and connection.in_transaction:
            connection.rollback()
        raise


def _main_database_path(connection: sqlite3.Connection) -> Path:
    databases = connection.execute("PRAGMA database_list").fetchall()
    if len(databases) != 1 or databases[0][1] != "main" or not databases[0][2]:
        raise StagingError(
            "atomic apply requires one file-backed main database and no attached databases"
        )
    path = Path(str(databases[0][2])).resolve(strict=True)
    if not path.is_file():
        raise StagingError("atomic apply database is not a regular file")
    return path


def _validate_expected_database_identity(
    connection: sqlite3.Connection,
    expected_db_identity: Mapping[str, Any],
) -> Tuple[Path, Dict[str, Any]]:
    if not isinstance(expected_db_identity, Mapping):
        raise StagingError("caller must provide the expected database identity")
    expected = dict(expected_db_identity)
    expected_path = expected.get("path")
    if not isinstance(expected_path, str) or not expected_path:
        raise StagingError("expected database identity must include its absolute path")
    try:
        resolved_expected_path = Path(expected_path).resolve(strict=True)
        database_path = _main_database_path(connection)
        actual = _database_identity(database_path)
    except OSError as exc:
        raise StagingError("could not resolve the expected database identity") from exc
    if str(resolved_expected_path) != str(database_path):
        raise StagingError("SQLite connection does not match the expected database path")
    if actual != expected:
        raise StagingError("database identity does not match the caller's expected identity")
    return database_path, actual


def _expected_periods(periods: Sequence[str]) -> Tuple[str, ...]:
    if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes)):
        raise StagingError("expected canonical periods must be a sequence")
    normalized = tuple(periods)
    if any(
        not isinstance(period, str) or not _PERIOD_RE.fullmatch(period)
        for period in normalized
    ):
        raise StagingError("expected canonical periods must be nine-digit strings")
    if len(set(normalized)) != len(normalized):
        raise StagingError("expected canonical periods must not contain duplicates")
    return tuple(sorted(normalized, key=int))


def _canonical_periods_in_view(connection: sqlite3.Connection) -> Tuple[str, ...]:
    rows = connection.execute(
        "SELECT draw FROM {}".format(membership.CANONICAL_VIEW)
    ).fetchall()
    periods: List[str] = []
    for row in rows:
        value = row[0]
        text = str(value)
        if not text.isdigit() or len(text) > 9:
            raise StagingError("canonical view contains a non-period draw value")
        periods.append(text.zfill(9))
    return tuple(sorted(periods, key=int))


def _validate_staged_import_prewrite(
    connection: sqlite3.Connection,
    manifest_path: Union[str, Path],
    *,
    approved_manifest_sha256: str,
    approved_official_dataset_sha256: str,
    expected_db_identity: Mapping[str, Any],
    expected_canonical_periods: Sequence[str],
    allow_query_only: bool,
) -> Dict[str, Any]:
    """Run the shared, non-mutating checks before either probe or Apply."""
    if not isinstance(approved_manifest_sha256, str) or not _SHA256_RE.fullmatch(
        approved_manifest_sha256
    ):
        raise StagingError("approved manifest file SHA-256 is malformed")
    if not isinstance(approved_official_dataset_sha256, str) or not _SHA256_RE.fullmatch(
        approved_official_dataset_sha256
    ):
        raise StagingError("approved official dataset SHA-256 is malformed")
    if connection.in_transaction:
        raise StagingError("atomic apply requires a connection with no open transaction")
    query_only = int(connection.execute("PRAGMA query_only").fetchone()[0]) == 1
    if query_only and not allow_query_only:
        raise StagingError("atomic apply refuses a query_only connection")

    try:
        manifest_bytes = Path(manifest_path).read_bytes()
    except OSError as exc:
        raise StagingError("could not read the staged manifest") from exc
    actual_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if actual_manifest_sha256 != approved_manifest_sha256:
        raise StagingError("external manifest file SHA-256 does not match its approved pin")
    manifest = strict_json_loads(manifest_bytes, source="staged manifest")
    records = _records_from_manifest_object(manifest)

    actual_dataset_sha256 = membership.identity_dataset_sha256(
        membership.OFFICIAL_IDENTITIES
    )
    if (
        len(membership.OFFICIAL_IDENTITIES) != 2177
        or membership.OFFICIAL_AS_OF_PERIOD != "115000095"
        or approved_official_dataset_sha256 != membership.OFFICIAL_DATASET_SHA256
        or actual_dataset_sha256 != approved_official_dataset_sha256
    ):
        raise StagingError("official identity dataset does not match its approved SHA-256")
    official_target = tuple(
        draw
        for draw in membership.OFFICIAL_IDENTITIES
        if draw.period in TARGET_DRAW_IDS
    )
    if tuple(draw.period for draw in official_target) != TARGET_DRAW_IDS:
        raise StagingError("official identity snapshot does not contain the exact 16-period range")
    official_by_period = {draw.period: draw for draw in official_target}
    for record in records:
        official = official_by_period[record.draw]
        if (
            record.date != official.draw_date
            or record.numbers != official.numbers
            or record.special != official.special
        ):
            raise StagingError(
                "staged period {} does not match the fixed official identity snapshot".format(
                    record.draw
                )
            )

    database_check = manifest.get("database_check")
    if not isinstance(database_check, dict):
        raise StagingError("staged manifest is missing its database check")
    if (
        database_check.get("read_only") is not True
        or database_check.get("db_copy") != "NONE"
        or database_check.get("db_writes") != "NONE"
        or not isinstance(database_check.get("path"), str)
    ):
        raise StagingError("staged manifest does not record a read-only database inspection")
    try:
        staged_database_path = Path(database_check["path"]).resolve(strict=True)
        database_path, actual_db_identity = _validate_expected_database_identity(
            connection, expected_db_identity
        )
    except OSError as exc:
        raise StagingError("could not resolve the staged database path") from exc
    if staged_database_path != database_path:
        raise StagingError("staged manifest and expected database identify different paths")

    expected_periods = _expected_periods(expected_canonical_periods)
    if not expected_periods:
        raise StagingError("expected canonical period set must not be empty")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(draws)")}
    if not {"draw", "date", "lottery_type", "numbers", "special"}.issubset(columns):
        raise StagingError("database draws table has an incompatible schema")
    canonical_view_kind = _validate_canonical_view_read_only(connection)

    return {
        "records": records,
        "manifest_file_sha256": actual_manifest_sha256,
        "database_path": database_path,
        "database_identity": actual_db_identity,
        "expected_periods": expected_periods,
        "canonical_view_kind": canonical_view_kind,
        "query_only": query_only,
    }


def apply_staged_import_atomically(
    connection: sqlite3.Connection,
    manifest_path: Union[str, Path],
    *,
    approved_manifest_sha256: str,
    approved_official_dataset_sha256: str,
    expected_db_identity: Mapping[str, Any],
    expected_canonical_periods: Sequence[str],
    preflight_only: bool = False,
) -> Dict[str, Any]:
    """以一筆 SQLite 交易套用官方身分及 manifest，再匯入 16 筆暫存開獎資料。

    在第一次資料庫寫入前，先驗證 manifest 完整檔案 SHA-256、固定的官方
    身分資料集、呼叫端預期的資料庫身分，以及預期 canonical 期號集合。
    `preflight_only=True` 會走同一個 prewrite 驗證，但在任何寫入交易前
    回傳明確的唯讀結果；它不測試 writer lock 或真實 COMMIT。manifest
    內自算的 content digest 只檢查內容一致性，不是數位簽章；
    呼叫端另提供完整檔案 SHA-256，作為核准檔案 pin。既有 CLI 維持唯讀
    staging，沒有正式資料庫 apply 子命令；此入口僅由程式呼叫。

    範例（僅限核准來源與合成資料庫驗證）::

        result = apply_staged_import_atomically(
            connection,
            manifest_path,
            approved_manifest_sha256=manifest_file_sha256,
            approved_official_dataset_sha256=OFFICIAL_DATASET_SHA256,
            expected_db_identity=expected_db_identity,
            expected_canonical_periods=expected_periods,
            preflight_only=True,
        )
    """
    if not isinstance(preflight_only, bool):
        raise StagingError("preflight_only must be a boolean")
    prepared = _validate_staged_import_prewrite(
        connection,
        manifest_path,
        approved_manifest_sha256=approved_manifest_sha256,
        approved_official_dataset_sha256=approved_official_dataset_sha256,
        expected_db_identity=expected_db_identity,
        expected_canonical_periods=expected_canonical_periods,
        allow_query_only=preflight_only,
    )
    records = prepared["records"]
    actual_manifest_sha256 = prepared["manifest_file_sha256"]
    database_path = prepared["database_path"]
    actual_db_identity = prepared["database_identity"]
    expected_periods = prepared["expected_periods"]

    if preflight_only:
        official_periods = tuple(draw.period for draw in membership.OFFICIAL_IDENTITIES)
        if expected_periods != official_periods:
            raise StagingError(
                "expected canonical period set does not match the pinned official dataset"
            )
        current_periods = _canonical_periods_in_view(connection)
        if len(current_periods) != len(set(current_periods)):
            raise StagingError("canonical view contains duplicate official periods")
        if set(current_periods).difference(official_periods):
            raise StagingError("canonical view contains periods outside the pinned dataset")

        inserted_records, identical_count = _plan_batch_import(connection, records)
        if prepared["canonical_view_kind"] == "OFFICIAL_IDENTITY_SHA256":
            predicted_periods = tuple(
                sorted(
                    set(current_periods).union(record.draw for record in inserted_records),
                    key=int,
                )
            )
            if predicted_periods != expected_periods:
                raise StagingError(
                    "canonical view cannot reach the expected period set from this batch"
                )
        else:
            expected_legacy_periods = tuple(
                draw.period
                for draw in membership.OFFICIAL_IDENTITIES
                if draw.period not in TARGET_DRAW_IDS
                and draw.period < TARGET_DRAW_IDS[0]
                and max(draw.numbers) > 25
            )
            if current_periods != expected_legacy_periods:
                raise StagingError(
                    "legacy canonical view periods do not match the known legacy subset"
                )

        identity_after = _database_identity(database_path)
        if identity_after != actual_db_identity:
            raise StagingError("database or SQLite sidecar identity changed during preflight")
        return {
            "PREFLIGHT_VALIDATION": "PASS",
            "MUTATION_PERFORMED": "NO",
            "WRITER_LOCK_TESTED": "NO",
            "REAL_TRANSACTION_COMMIT_TESTED": "NO",
            "DATABASE_IDENTITY_UNCHANGED": "PASS",
            "SIDECARS": "OBSERVED"
            if any(identity_after["sidecars"].values())
            else "NONE",
            "CONNECTION_QUERY_ONLY": "YES" if prepared["query_only"] else "NO",
            "SAME_CHAIN_VALIDATION": "PASS",
            "MANIFEST_FILE_SHA256": actual_manifest_sha256,
            "OFFICIAL_DATASET_SHA256": membership.OFFICIAL_DATASET_SHA256,
            "DATABASE_SHA256": actual_db_identity["sha256"],
            "CANONICAL_VIEW_KIND": prepared["canonical_view_kind"],
            "CANONICAL_PERIODS_BEFORE": list(current_periods),
            "EXPECTED_CANONICAL_PERIODS": list(expected_periods),
            "EXPECTED_CANONICAL_PERIOD_COUNT": len(expected_periods),
            "STAGED_PERIOD_COUNT": len(records),
            "INSERTED_PERIOD_COUNT": len(inserted_records),
            "IDENTICAL_PERIOD_COUNT": identical_count,
        }

    connection.execute("BEGIN IMMEDIATE")
    try:
        locked_db_identity = _database_identity(database_path)
        if locked_db_identity != actual_db_identity:
            raise StagingError("database identity changed before the transaction acquired its lock")
        projection_result = membership.apply_official_membership_projection(
            connection, manage_transaction=False
        )
        batch_result = apply_batch(connection, records, manage_transaction=False)
        canonical_periods = _canonical_periods_in_view(connection)
        if canonical_periods != expected_periods:
            raise StagingError(
                "canonical view period set differs from the caller's expected result"
            )
        if len(canonical_periods) != projection_result.view_row_count + batch_result[
            "inserted_count"
        ]:
            raise StagingError("canonical view row count is inconsistent with the atomic apply")
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise

    return {
        "official_record_count": projection_result.official_record_count,
        "identity_rows_written": projection_result.identity_rows_written,
        "official_dataset_sha256": projection_result.dataset_sha256,
        "canonical_count_before_staged_rows": projection_result.view_row_count,
        "inserted_count": batch_result["inserted_count"],
        "inserted_draw_ids": batch_result["inserted_draw_ids"],
        "identical_existing_count": batch_result["identical_existing_count"],
        "canonical_period_count": len(canonical_periods),
        "canonical_periods": list(canonical_periods),
        "manifest_file_sha256": actual_manifest_sha256,
    }


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
