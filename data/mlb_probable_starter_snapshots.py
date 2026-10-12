"""
data/mlb_probable_starter_snapshots.py
======================================
P202D — Pregame Probable-Starter Snapshot Intake Skeleton (FIXTURE-ONLY)

實作 P202C 賽前 probable-starter 快照資料契約（見
``report/p202c_point_in_time_pitcher_data_gap_evidence_contract_20260612.md`` §4/§8/§9）
之 append-only intake skeleton。

本模組為 plan/skeleton 階段資產：
  - 純標準函式庫，零網路、零外部相依（無 requests/httpx/socket/urllib）。
  - 不呼叫任何 live API（含 statsapi.mlb.com）。
  - 不連接 scheduler / recommendation producer / evaluator。
  - 不寫入任何真實 runtime 資料集；所有寫入路徑由呼叫端「顯式」提供（測試一律用 tmp_path）。
  - import 時零副作用（不寫檔、不連網）。
  - 所有快照 diagnostic_only=True、production_ready=False；永不標 learning_eligible。
  - 嚴禁以賽後實際先發（as-played / actual starter）冒充賽前 probable —— 偵測到即 fail-closed。

公開 API：
  - normalize_snapshot(raw, *, parser_version=PARSER_VERSION) -> ProbableStarterSnapshot
  - compute_payload_fingerprint(canonical_fields) -> str
  - snapshot_dedup_key(record) -> tuple
  - load_snapshots(path) -> list[dict]              (fail-closed on malformed JSONL)
  - append_snapshot(snapshot, path) -> AppendResult (append-only / idempotent)
  - select_canonical_snapshot(...) -> SelectionResult (純函式；diagnostic-only)

Hard Rules (NEVER violate):
  - DIAGNOSTIC_ONLY = True
  - PRODUCTION_READY = False
  - 無網路、無 DB、無 import 副作用、無 default 寫入路徑
  - 不替換／不接受賽後實際先發
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CONTRACT_VERSION: str = "p202c_probable_starter_snapshot_v1"
PARSER_VERSION: str = "p202d_probable_snapshot_parser_v1"
DIAGNOSTIC_ONLY: bool = True
PRODUCTION_READY: bool = False

# 非綁定提示：未來經「獨立授權」之 live collector（P202E）慣用的輸出路徑。
# 本模組與其測試「絕不」寫入此路徑；``append_snapshot`` 無 default path，
# 呼叫端必須顯式提供。此常數僅供文件用途，不得作為任何寫入預設值。
CANONICAL_RUNTIME_OUTPUT_PATH_HINT: str = (
    "data/mlb_probable_starters/probable_starter_snapshots.jsonl"
)

# ─── Controlled vocabularies（P202C §4）────────────────────────────────────────
PITCHER_STATUS_VALUES: frozenset[str] = frozenset({
    "announced", "probable", "confirmed", "changed", "scratched",
    "opener", "bullpen_game", "tbd", "unavailable",
})
# 「已定」狀態——雙邊皆此類且雙邊 pitcher_id 齊備時，方視為可信先發身份。
TRUSTED_PITCHER_STATUSES: frozenset[str] = frozenset({
    "announced", "probable", "confirmed",
})
GAME_STATUS_VALUES: frozenset[str] = frozenset({
    "scheduled", "postponed", "cancelled", "delayed", "suspended",
})
SNAPSHOT_STATUS_VALUES: frozenset[str] = frozenset({
    "valid", "partial", "stale", "superseded", "postponed",
    "cancelled", "malformed", "source_unavailable",
})

# ─── Leakage guards（P202C §9）─────────────────────────────────────────────────
# 任一禁用欄位出現（非 None）即 fail-closed：杜絕賽後結果與實際先發冒充賽前 probable。
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    # postgame outcome
    "home_win", "away_win", "final_score", "home_score", "away_score",
    "result", "box_score", "boxscore", "post_game_stats", "postgame_stats",
    "actual_winner", "winning_team", "game_outcome", "is_final", "final",
    "linescore",
    # as-played / actual starter substitution
    "home_actual_starter", "away_actual_starter",
    "home_actual_starter_id", "away_actual_starter_id",
    "actual_home_starter_id", "actual_away_starter_id",
    "actual_starter", "actual_starters", "as_played", "asplayed",
    "is_as_played", "starter_origin_actual",
})
# source_provider / endpoint 不得自稱 as-played / actual / postgame。
_FORBIDDEN_PROVIDER_MARKERS: tuple[str, ...] = (
    "asplayed", "as_played", "as-played", "actual", "postgame", "post_game",
)


# ─── Exceptions ────────────────────────────────────────────────────────────────
class SnapshotValidationError(ValueError):
    """Raised when a raw snapshot payload fails the P202C contract (fail-closed)."""


class SnapshotStoreError(RuntimeError):
    """Raised when the append-only store is malformed or its parent path is invalid."""


# ─── Normalized record（P202C §4，恰好 25 欄）────────────────────────────────────
@dataclass(frozen=True)
class ProbableStarterSnapshot:
    contract_version: str
    source_provider: str
    source_endpoint_or_feed_id: str
    source_record_id: str
    payload_fingerprint: str
    collected_at_utc: str
    information_cutoff_utc: str
    game_pk: int
    scheduled_start_utc: str
    official_game_date: str
    doubleheader_game_number: int
    home_team_id: int
    away_team_id: int
    home_probable_pitcher_id: Optional[int]
    home_probable_pitcher_name: Optional[str]
    away_probable_pitcher_id: Optional[int]
    away_probable_pitcher_name: Optional[str]
    home_pitcher_status: str
    away_pitcher_status: str
    game_status: str
    snapshot_status: str
    source_freshness_seconds: int
    parser_version: str
    diagnostic_only: bool
    production_ready: bool


@dataclass(frozen=True)
class AppendResult:
    appended: bool
    status: str        # appended_new | appended_revision | idempotent_duplicate
    reason: str
    dedup_key: tuple
    total_records: int
    path: str


@dataclass(frozen=True)
class SelectionResult:
    trusted: bool
    status: str        # trusted | no_matching_game | no_pre_cutoff_snapshot | stale |
                       # one_side_missing | both_sides_tbd | scratched | changed |
                       # opener_bullpen | tbd | unavailable | cancelled | postponed |
                       # source_unavailable | insufficient_lead_time | no_selectable_snapshot
    reason: str
    snapshot: Optional[dict]
    candidate_count: int


# ─── Low-level validators ───────────────────────────────────────────────────────
def _require_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError(f"required string field missing/empty: {key!r}")
    return value


def _require_int(raw: dict, key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotValidationError(f"required int field missing/invalid: {key!r}={value!r}")
    return value


def _opt_int(value: Any, key: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotValidationError(f"optional int field invalid: {key!r}={value!r}")
    return value


def _opt_str(value: Any, key: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SnapshotValidationError(f"optional string field invalid: {key!r}={value!r}")
    return value


def _validate_enum(value: Any, allowed: frozenset[str], key: str) -> str:
    if value not in allowed:
        raise SnapshotValidationError(
            f"{key!r}={value!r} not in allowed values {sorted(allowed)}"
        )
    return value


def _parse_utc(value: Any, key: str) -> datetime:
    """Parse a timezone-aware UTC datetime; reject naive or non-UTC values (fail-closed)."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            raise SnapshotValidationError(f"{key!r} timestamp is empty")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError as exc:
            raise SnapshotValidationError(f"{key!r} is not ISO-8601: {value!r}") from exc
    else:
        raise SnapshotValidationError(
            f"{key!r} must be an ISO-8601 string or datetime, got {type(value).__name__}"
        )
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise SnapshotValidationError(
            f"{key!r} must be timezone-aware UTC (naive datetime rejected): {value!r}"
        )
    if dt.utcoffset() != timedelta(0):
        raise SnapshotValidationError(
            f"{key!r} must be UTC (zero offset), got offset {dt.utcoffset()}: {value!r}"
        )
    return dt.astimezone(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _validate_official_date(date_str: str, scheduled_start: datetime) -> None:
    try:
        d = date.fromisoformat(date_str)
    except ValueError as exc:
        raise SnapshotValidationError(
            f"official_game_date is not YYYY-MM-DD: {date_str!r}"
        ) from exc
    # 聯盟官方日期（league-local）與 UTC 排定日可差至多一日。
    if abs((d - scheduled_start.date()).days) > 1:
        raise SnapshotValidationError(
            f"official_game_date {date_str!r} incompatible with "
            f"scheduled_start_utc date {scheduled_start.date().isoformat()!r}"
        )


def _reject_forbidden(raw: dict) -> None:
    """Fail closed on postgame-outcome / actual-starter / production / learning claims."""
    present = [k for k in _FORBIDDEN_FIELDS if raw.get(k) is not None]
    if present:
        raise SnapshotValidationError(
            f"forbidden postgame/actual-starter field(s) present (leakage): {sorted(present)}"
        )
    if raw.get("production_ready") is True:
        raise SnapshotValidationError("a fixture/intake snapshot may not claim production_ready=True")
    if raw.get("diagnostic_only") is False:
        raise SnapshotValidationError("a fixture/intake snapshot may not claim diagnostic_only=False")
    if "learning_eligible" in raw:
        raise SnapshotValidationError("a probable-starter snapshot may not set learning_eligible")


def _reject_provider_markers(*values: str) -> None:
    for value in values:
        low = value.lower()
        for marker in _FORBIDDEN_PROVIDER_MARKERS:
            if marker in low:
                raise SnapshotValidationError(
                    f"source provider/endpoint may not claim as-played/actual/postgame origin: {value!r}"
                )


def _derive_snapshot_status(
    game_status: str,
    home_pid: Optional[int],
    away_pid: Optional[int],
) -> str:
    if game_status == "cancelled":
        return "cancelled"
    if game_status == "postponed":
        return "postponed"
    if home_pid is not None and away_pid is not None:
        return "valid"
    return "partial"


# ─── Fingerprint / idempotency ──────────────────────────────────────────────────
def compute_payload_fingerprint(canonical_fields: dict) -> str:
    """Deterministic ``sha256:`` fingerprint over canonical (sorted) JSON.

    Stable across input dictionary key order because keys are sorted; changes when
    any substantive field (starter, status, scheduled time, source record, collection
    time, cutoff, identity) changes.
    """
    blob = json.dumps(canonical_fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def snapshot_dedup_key(record: Any) -> tuple:
    """Exact-duplicate idempotency key (P202C §8).

    Includes enough provenance to distinguish legitimate revisions: source provider,
    source record, game_pk, doubleheader game number, collection timestamp, and the
    payload fingerprint. An exact duplicate yields an identical tuple (idempotent);
    a changed starter/status/time/collection-time yields a different tuple (revision).
    """
    d = asdict(record) if isinstance(record, ProbableStarterSnapshot) else record
    try:
        return (
            d["source_provider"],
            d["source_record_id"],
            int(d["game_pk"]),
            int(d["doubleheader_game_number"]),
            d["collected_at_utc"],
            d["payload_fingerprint"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotStoreError(f"record missing/invalid dedup-key fields: {exc}") from exc


# ─── Normalization（Phase 2/3/4）─────────────────────────────────────────────────
def normalize_snapshot(raw: dict, *, parser_version: str = PARSER_VERSION) -> ProbableStarterSnapshot:
    """Validate + normalize a raw probable-starter payload into a contract record.

    Fail-closed: any contract violation raises ``SnapshotValidationError`` and yields
    no record. ``diagnostic_only`` and ``production_ready`` are forced True/False.
    """
    if not isinstance(raw, dict):
        raise SnapshotValidationError(f"raw snapshot must be a dict, got {type(raw).__name__}")

    _reject_forbidden(raw)

    source_provider = _require_str(raw, "source_provider")
    source_endpoint = _require_str(raw, "source_endpoint_or_feed_id")
    source_record_id = _require_str(raw, "source_record_id")
    _reject_provider_markers(source_provider, source_endpoint)

    collected_at = _parse_utc(raw.get("collected_at_utc"), "collected_at_utc")
    cutoff = _parse_utc(raw.get("information_cutoff_utc"), "information_cutoff_utc")
    scheduled = _parse_utc(raw.get("scheduled_start_utc"), "scheduled_start_utc")

    # Timestamp ordering (P202C §8): cutoff strictly before start; collected ≤ cutoff.
    if not (cutoff < scheduled):
        raise SnapshotValidationError(
            "information_cutoff_utc must be strictly before scheduled_start_utc"
        )
    if collected_at > cutoff:
        raise SnapshotValidationError(
            "collected_at_utc must not be after information_cutoff_utc"
        )

    game_pk = _require_int(raw, "game_pk")
    home_team_id = _require_int(raw, "home_team_id")
    away_team_id = _require_int(raw, "away_team_id")
    if home_team_id == away_team_id:
        raise SnapshotValidationError("home_team_id and away_team_id must differ")

    dh = raw.get("doubleheader_game_number")
    if isinstance(dh, bool) or not isinstance(dh, int) or dh < 0 or dh > 2:
        raise SnapshotValidationError(
            f"doubleheader_game_number must be an int in 0..2, got {dh!r}"
        )

    official_game_date = _require_str(raw, "official_game_date")
    _validate_official_date(official_game_date, scheduled)

    home_status = _validate_enum(raw.get("home_pitcher_status"), PITCHER_STATUS_VALUES, "home_pitcher_status")
    away_status = _validate_enum(raw.get("away_pitcher_status"), PITCHER_STATUS_VALUES, "away_pitcher_status")
    game_status = _validate_enum(raw.get("game_status"), GAME_STATUS_VALUES, "game_status")

    home_pid = _opt_int(raw.get("home_probable_pitcher_id"), "home_probable_pitcher_id")
    away_pid = _opt_int(raw.get("away_probable_pitcher_id"), "away_probable_pitcher_id")
    home_pname = _opt_str(raw.get("home_probable_pitcher_name"), "home_probable_pitcher_name")
    away_pname = _opt_str(raw.get("away_probable_pitcher_name"), "away_probable_pitcher_name")

    freshness = raw.get("source_freshness_seconds")
    if isinstance(freshness, bool) or not isinstance(freshness, int) or freshness < 0:
        raise SnapshotValidationError(
            f"source_freshness_seconds must be a non-negative int, got {freshness!r}"
        )

    explicit_status = raw.get("snapshot_status")
    if explicit_status == "source_unavailable":
        snapshot_status = "source_unavailable"
    elif explicit_status is not None and explicit_status not in SNAPSHOT_STATUS_VALUES:
        raise SnapshotValidationError(
            f"snapshot_status={explicit_status!r} not in {sorted(SNAPSHOT_STATUS_VALUES)}"
        )
    else:
        snapshot_status = _derive_snapshot_status(game_status, home_pid, away_pid)

    collected_iso = _to_iso(collected_at)
    cutoff_iso = _to_iso(cutoff)
    scheduled_iso = _to_iso(scheduled)

    # Fingerprint over normalized substantive fields (order-independent, format-stable).
    canonical_fields = {
        "source_provider": source_provider,
        "source_endpoint_or_feed_id": source_endpoint,
        "source_record_id": source_record_id,
        "collected_at_utc": collected_iso,
        "information_cutoff_utc": cutoff_iso,
        "game_pk": game_pk,
        "scheduled_start_utc": scheduled_iso,
        "official_game_date": official_game_date,
        "doubleheader_game_number": dh,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_probable_pitcher_id": home_pid,
        "home_probable_pitcher_name": home_pname,
        "away_probable_pitcher_id": away_pid,
        "away_probable_pitcher_name": away_pname,
        "home_pitcher_status": home_status,
        "away_pitcher_status": away_status,
        "game_status": game_status,
    }
    fingerprint = compute_payload_fingerprint(canonical_fields)

    return ProbableStarterSnapshot(
        contract_version=CONTRACT_VERSION,
        source_provider=source_provider,
        source_endpoint_or_feed_id=source_endpoint,
        source_record_id=source_record_id,
        payload_fingerprint=fingerprint,
        collected_at_utc=collected_iso,
        information_cutoff_utc=cutoff_iso,
        game_pk=game_pk,
        scheduled_start_utc=scheduled_iso,
        official_game_date=official_game_date,
        doubleheader_game_number=dh,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_probable_pitcher_id=home_pid,
        home_probable_pitcher_name=home_pname,
        away_probable_pitcher_id=away_pid,
        away_probable_pitcher_name=away_pname,
        home_pitcher_status=home_status,
        away_pitcher_status=away_status,
        game_status=game_status,
        snapshot_status=snapshot_status,
        source_freshness_seconds=freshness,
        parser_version=parser_version,
        diagnostic_only=True,
        production_ready=False,
    )


# ─── Append-only persistence（Phase 5）───────────────────────────────────────────
def load_snapshots(path: Any) -> list[dict]:
    """Read the JSONL store; fail-closed (raise) on malformed content without altering it."""
    p = os.fspath(path)
    if not os.path.exists(p):
        return []
    records: list[dict] = []
    with open(p, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SnapshotStoreError(
                    f"malformed JSONL at line {line_no} in {p!r}: {exc}"
                ) from exc
            if not isinstance(rec, dict):
                raise SnapshotStoreError(
                    f"non-object JSONL record at line {line_no} in {p!r}"
                )
            records.append(rec)
    return records


def append_snapshot(snapshot: ProbableStarterSnapshot, path: Any) -> AppendResult:
    """Append a normalized snapshot to an explicit JSONL path (append-only / idempotent).

    - ``path`` is required; there is no default runtime path.
    - Exact-duplicate dedup keys are a no-op (idempotent).
    - A legitimate revision (same game, changed payload/collection time) appends a new line.
    - Existing lines are never rewritten (pure append); malformed stores fail closed.
    - The parent directory must already exist (no silent auto-create).
    """
    if not isinstance(snapshot, ProbableStarterSnapshot):
        raise SnapshotValidationError(
            "append_snapshot requires a normalized ProbableStarterSnapshot"
        )
    p = os.fspath(path)
    parent = os.path.dirname(p)
    if parent and not os.path.isdir(parent):
        raise SnapshotStoreError(
            f"parent directory does not exist (explicit path required, no auto-create): {parent!r}"
        )

    existing = load_snapshots(p)  # fail-closed on malformed
    key = snapshot_dedup_key(snapshot)

    is_revision = False
    for rec in existing:
        if snapshot_dedup_key(rec) == key:
            return AppendResult(
                appended=False,
                status="idempotent_duplicate",
                reason="exact-duplicate dedup key already present",
                dedup_key=key,
                total_records=len(existing),
                path=p,
            )
        if (
            str(rec.get("game_pk")) == str(snapshot.game_pk)
            and rec.get("doubleheader_game_number") == snapshot.doubleheader_game_number
        ):
            is_revision = True

    line = json.dumps(asdict(snapshot), sort_keys=True, ensure_ascii=False)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    return AppendResult(
        appended=True,
        status="appended_revision" if is_revision else "appended_new",
        reason="revision appended" if is_revision else "first snapshot for this game appended",
        dedup_key=key,
        total_records=len(existing) + 1,
        path=p,
    )


# ─── Canonical selection（Phase 6）───────────────────────────────────────────────
_NON_SELECTABLE_STATUSES: frozenset[str] = frozenset({
    "cancelled", "postponed", "source_unavailable", "malformed", "superseded",
})
_SURFACED_PITCHER_STATES: frozenset[str] = frozenset({
    "scratched", "changed", "opener", "bullpen_game", "tbd", "unavailable",
})


def _as_dict(record: Any) -> dict:
    return asdict(record) if isinstance(record, ProbableStarterSnapshot) else record


def _sort_key(rec: dict) -> tuple:
    # Deterministic ordering: latest collection time, fingerprint tiebreak.
    return (rec.get("collected_at_utc", ""), rec.get("payload_fingerprint", ""))


def select_canonical_snapshot(
    snapshots: Any,
    *,
    game_pk: int,
    doubleheader_game_number: int,
    target_information_cutoff_utc: Any,
    stale_max_seconds: float,
    min_lead_seconds: float,
) -> SelectionResult:
    """Pure, diagnostic-only selection of a canonical pregame snapshot.

    Never substitutes an actual starter (only stored snapshots are considered, and
    those can never contain actual starters by construction). Fails closed and
    returns an explicit reason whenever no trusted snapshot is available. Caller must
    supply staleness / minimum-lead thresholds (no unapproved production default).
    """
    target = _parse_utc(target_information_cutoff_utc, "target_information_cutoff_utc")
    if isinstance(stale_max_seconds, bool) or not isinstance(stale_max_seconds, (int, float)) or stale_max_seconds < 0:
        raise SnapshotValidationError("stale_max_seconds must be a non-negative number")
    if isinstance(min_lead_seconds, bool) or not isinstance(min_lead_seconds, (int, float)) or min_lead_seconds < 0:
        raise SnapshotValidationError("min_lead_seconds must be a non-negative number")

    recs = [_as_dict(s) for s in snapshots]
    matched = [
        r for r in recs
        if str(r.get("game_pk")) == str(game_pk)
        and r.get("doubleheader_game_number") == doubleheader_game_number
    ]
    if not matched:
        return SelectionResult(False, "no_matching_game",
                               f"no snapshot for game_pk={game_pk} dh={doubleheader_game_number}",
                               None, 0)

    # Exclude records collected after the target information cutoff (post-cutoff updates).
    pre_cutoff = [r for r in matched if _parse_utc(r["collected_at_utc"], "collected_at_utc") <= target]
    if not pre_cutoff:
        return SelectionResult(False, "no_pre_cutoff_snapshot",
                               "all snapshots were collected after the target cutoff",
                               None, len(matched))

    latest_overall = max(pre_cutoff, key=_sort_key)

    # Surface terminal states on the latest snapshot rather than silently returning an
    # older scheduled_start version.
    overall_status = latest_overall.get("snapshot_status")
    if overall_status in {"cancelled", "postponed", "source_unavailable"}:
        return SelectionResult(False, overall_status,
                               f"latest pre-cutoff snapshot is {overall_status}",
                               latest_overall, len(pre_cutoff))

    # Minimum lead time: scheduled_start minus the decision cutoff (also rejects cutoff
    # at/after game start).
    scheduled = _parse_utc(latest_overall["scheduled_start_utc"], "scheduled_start_utc")
    lead = (scheduled - target).total_seconds()
    if lead < min_lead_seconds:
        return SelectionResult(False, "insufficient_lead_time",
                               f"lead {lead:.0f}s < min_lead {min_lead_seconds:.0f}s",
                               latest_overall, len(pre_cutoff))

    selectable = [r for r in pre_cutoff if r.get("snapshot_status") not in _NON_SELECTABLE_STATUSES]
    if not selectable:
        return SelectionResult(False, "no_selectable_snapshot",
                               "no non-terminal snapshot available before cutoff",
                               latest_overall, len(pre_cutoff))

    latest = max(selectable, key=_sort_key)

    age = (target - _parse_utc(latest["collected_at_utc"], "collected_at_utc")).total_seconds()
    if age > stale_max_seconds:
        return SelectionResult(False, "stale",
                               f"latest snapshot age {age:.0f}s > stale_max {stale_max_seconds:.0f}s",
                               latest, len(pre_cutoff))

    if latest.get("snapshot_status") == "partial":
        hp = latest.get("home_probable_pitcher_id")
        ap = latest.get("away_probable_pitcher_id")
        if hp is None and ap is None:
            return SelectionResult(False, "both_sides_tbd",
                                   "both probable starters are unannounced",
                                   latest, len(pre_cutoff))
        return SelectionResult(False, "one_side_missing",
                               "only one side has an announced probable starter",
                               latest, len(pre_cutoff))

    home_status = latest["home_pitcher_status"]
    away_status = latest["away_pitcher_status"]
    flagged = [s for s in (home_status, away_status) if s in _SURFACED_PITCHER_STATES]
    if flagged:
        if "scratched" in flagged:
            rep = "scratched"
        elif "changed" in flagged:
            rep = "changed"
        elif "opener" in flagged or "bullpen_game" in flagged:
            rep = "opener_bullpen"
        elif "tbd" in flagged:
            rep = "tbd"
        else:
            rep = "unavailable"
        return SelectionResult(False, rep,
                               f"pitcher status surfaced: home={home_status}, away={away_status}",
                               latest, len(pre_cutoff))

    if (
        home_status in TRUSTED_PITCHER_STATUSES
        and away_status in TRUSTED_PITCHER_STATUSES
        and latest.get("home_probable_pitcher_id") is not None
        and latest.get("away_probable_pitcher_id") is not None
    ):
        return SelectionResult(True, "trusted",
                               "both-side settled probable starters before cutoff (diagnostic-only)",
                               latest, len(pre_cutoff))

    return SelectionResult(False, "not_trusted",
                           "did not meet both-side trusted criteria",
                           latest, len(pre_cutoff))
