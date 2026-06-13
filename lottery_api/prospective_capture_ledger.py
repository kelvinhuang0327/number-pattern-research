"""Isolated prospective-capture ledger (P271J).

This module implements the *frozen* P271I prospective-capture ledger contract
(``outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.json``)
as a standalone, fail-closed library that operates **only** on a caller-supplied
``sqlite3.Connection``.

Isolation guarantees (P271J task boundary):
  * No import-time database access.
  * No canonical/production database path appears anywhere in this module.
  * No route / API / server registration, scheduler, or network call.
  * No import of ``lottery_api.database`` or of any replay / scorer / strategy /
    registry / controlled_apply / recommendation / production module.
  * The module never opens a database path itself; the caller supplies the
    connection (synthetic ``:memory:`` or pytest ``tmp_path`` databases only in
    P271J).
  * Deterministic except for explicitly supplied timestamps / identifiers.
  * Fails closed: anything that is not provably eligible is rejected.

Nothing in this module fetches an official draw-close schedule, claims official
verification, computes hits / prizes / M3+ / success rates, queries any outcome
or result table, activates prospective collection, or writes a real activation
record. ``SOURCE_VERIFICATION_STATUS`` remains ``MANUAL_VERIFICATION_REQUIRED``.

Clock-skew tolerance is intentionally **not** a hard-coded constant. P271I freezes
the *rule* (``prediction_created_at_utc < draw_close_at_utc`` minus a conservative
margin) and states the margin "is configured per draw-close source version and
never silently widened". This module therefore requires the caller to supply an
explicit, non-negative ``clock_skew_margin_seconds`` on every draw-close source;
a missing margin fails closed (``SOURCE_PROVENANCE_FAILURE``). No default margin
is invented.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Frozen constants (re-derived natively; the scorer is intentionally not imported)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "p271j_prospective_capture_ledger.v1"

SOURCE_VERIFICATION_STATUS = "MANUAL_VERIFICATION_REQUIRED"

SUPPORTED_LOTTERY_TYPES = ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")

# P271C-compatible capture validation ranges (no scoring of outcomes).
_MAIN_PICK_COUNT = {
    "POWER_LOTTO": 6,
    "BIG_LOTTO": 6,
    "DAILY_539": 5,
}
_MAIN_NUMBER_RANGE = {
    "POWER_LOTTO": (1, 38),
    "BIG_LOTTO": (1, 49),
    "DAILY_539": (1, 39),
}
_SECOND_ZONE_RANGE = (1, 8)  # POWER_LOTTO second zone (特別號)
_REQUIRES_SECOND_ZONE = {"POWER_LOTTO"}

# Capture modes — only LIVE_PRE_CLOSE is ever eligible for the prospective population.
CAPTURE_MODE_LIVE_PRE_CLOSE = "LIVE_PRE_CLOSE"
_NON_LIVE_CAPTURE_MODES = ("MANUAL", "RECONSTRUCTED", "BACKFILL", "IMPORT")
_ALL_CAPTURE_MODES = (CAPTURE_MODE_LIVE_PRE_CLOSE,) + _NON_LIVE_CAPTURE_MODES

# Draw-close source classes and their confirmatory eligibility (P271I).
SOURCE_OFFICIAL_MACHINE_READABLE = "official_machine_readable"
SOURCE_OFFICIAL_PUBLISHED_SCHEDULE = "official_published_schedule"
SOURCE_REPOSITORY_DETERMINISTIC = "repository_configured_deterministic_schedule"
SOURCE_MANUAL = "manual"
_SOURCE_TYPES = (
    SOURCE_OFFICIAL_MACHINE_READABLE,
    SOURCE_OFFICIAL_PUBLISHED_SCHEDULE,
    SOURCE_REPOSITORY_DETERMINISTIC,
    SOURCE_MANUAL,
)
# Manual sources can never be confirmatory; official/deterministic sources are
# confirmatory only after explicit manual verification (PENDING / ONLY_AFTER).
_MANUAL_VERIFICATION_GATED_SOURCES = (
    SOURCE_OFFICIAL_MACHINE_READABLE,
    SOURCE_OFFICIAL_PUBLISHED_SCHEDULE,
    SOURCE_REPOSITORY_DETERMINISTIC,
)

# Eligibility statuses recorded on a persisted ledger / batch row.
ELIGIBILITY_ELIGIBLE = "ELIGIBLE"
ELIGIBILITY_REJECTED = "REJECTED"

# Rejection reasons. F01-F14 mirror the P271I failure matrix one-for-one; the
# remaining structured reasons cover designed ineligibilities the matrix folds
# into its broader cases.
REASON_CLOSE_TIME_MISSING = "CLOSE_TIME_MISSING"                       # F01
REASON_STALE_SCHEDULE = "STALE_SCHEDULE"                               # F02
REASON_UNSUPPORTED_LOTTERY = "UNSUPPORTED_LOTTERY"                     # F03
REASON_INVALID_PREDICTED_NUMBERS = "INVALID_PREDICTED_NUMBERS"        # F04
REASON_MISSING_OR_INVALID_SECOND_ZONE = "MISSING_OR_INVALID_PREDICTED_SECOND_ZONE"  # F05
REASON_DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"                       # F06
REASON_AMBIGUOUS_TIMESTAMP = "AMBIGUOUS_TIMESTAMP"                     # F07
REASON_POST_CLOSE_SUBMISSION = "POST_CLOSE_SUBMISSION"                 # F08
REASON_INACTIVE_ACTIVATION = "INACTIVE_ACTIVATION"                     # F09
REASON_UNKNOWN_STRATEGY_VERSION = "UNKNOWN_STRATEGY_VERSION"           # F10
REASON_TRANSACTION_FAILURE = "TRANSACTION_FAILURE"                     # F11
REASON_PARTIAL_BATCH_REJECTED = "PARTIAL_BATCH_REJECTED"              # F12
REASON_BACKFILL_EXCLUDED = "BACKFILL_EXCLUDED"                         # F13
REASON_SOURCE_PROVENANCE_FAILURE = "SOURCE_PROVENANCE_FAILURE"        # F14
# Designed ineligibilities / structural rejections.
REASON_SECOND_ZONE_NOT_PERMITTED = "SECOND_ZONE_NOT_PERMITTED"
REASON_MANUAL_SOURCE_NOT_CONFIRMATORY = "MANUAL_SOURCE_NOT_CONFIRMATORY"
REASON_SOURCE_PENDING_MANUAL_VERIFICATION = "SOURCE_PENDING_MANUAL_VERIFICATION"
REASON_EMPTY_BATCH = "EMPTY_BATCH"
REASON_POST_CLOSE_AMENDMENT = "POST_CLOSE_AMENDMENT"
REASON_AMENDMENT_ALTERS_IDENTITY = "AMENDMENT_ALTERS_IDENTITY"
REASON_UNKNOWN_LEDGER_ROW = "UNKNOWN_LEDGER_ROW"

FAILURE_MATRIX_REASONS = (
    REASON_CLOSE_TIME_MISSING,
    REASON_STALE_SCHEDULE,
    REASON_UNSUPPORTED_LOTTERY,
    REASON_INVALID_PREDICTED_NUMBERS,
    REASON_MISSING_OR_INVALID_SECOND_ZONE,
    REASON_DUPLICATE_IDENTITY,
    REASON_AMBIGUOUS_TIMESTAMP,
    REASON_POST_CLOSE_SUBMISSION,
    REASON_INACTIVE_ACTIVATION,
    REASON_UNKNOWN_STRATEGY_VERSION,
    REASON_TRANSACTION_FAILURE,
    REASON_PARTIAL_BATCH_REJECTED,
    REASON_BACKFILL_EXCLUDED,
    REASON_SOURCE_PROVENANCE_FAILURE,
)

# Event types recorded in the append-only event stream.
EVENT_ACTIVATION = "ACTIVATION"
EVENT_DEACTIVATION = "DEACTIVATION"
EVENT_CAPTURE = "CAPTURE"
EVENT_CAPTURE_REJECTED = "CAPTURE_REJECTED"
EVENT_AMENDMENT = "AMENDMENT"
EVENT_INVALIDATION = "INVALIDATION"

_LEDGER_TABLE = "prospective_prediction_ledger"
_BATCH_TABLE = "prospective_capture_batches"
_EVENT_TABLE = "prospective_capture_events"
_REGISTRY_TABLE = "prospective_activation_registry"
_OUTCOME_TABLE = "prospective_outcome_links"
_META_TABLE = "prospective_schema_meta"

# Tables protected by append-only BEFORE UPDATE / BEFORE DELETE triggers.
_APPEND_ONLY_TABLES = (
    _REGISTRY_TABLE,
    _BATCH_TABLE,
    _LEDGER_TABLE,
    _EVENT_TABLE,
    _OUTCOME_TABLE,
)


# ---------------------------------------------------------------------------
# Typed exceptions
# ---------------------------------------------------------------------------


class ProspectiveCaptureError(Exception):
    """Base class for prospective-capture-ledger errors (programmer misuse)."""


class SchemaVersionError(ProspectiveCaptureError):
    """Raised when a pre-existing connection carries an incompatible schema."""


class LedgerUsageError(ProspectiveCaptureError):
    """Raised for invalid use of the public API (wrong types, missing args)."""


class _BatchRejected(Exception):
    """Internal: a batch failed a fail-closed check inside the transaction."""

    def __init__(self, reason: str, bet_index: Optional[int] = None):
        super().__init__(reason)
        self.reason = reason
        self.bet_index = bet_index


# ---------------------------------------------------------------------------
# Input / output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DrawCloseSource:
    """A versioned draw-close evidence descriptor.

    ``clock_skew_margin_seconds`` is the per-source-version margin required by
    the P271I causality rule. It must be supplied explicitly; there is no
    invented default.
    """

    source_type: str
    source_id: str
    source_version: str
    clock_skew_margin_seconds: object  # validated; intentionally untyped to catch bad input
    provenance: Mapping[str, object] = field(default_factory=dict)
    snapshot_at_utc: Optional[str] = None
    freshness_window_seconds: Optional[int] = None
    manually_verified: bool = False


@dataclass(frozen=True)
class TicketInput:
    strategy_id: str
    strategy_version: str
    bet_index: object  # validated
    predicted_main_numbers: Sequence[object]
    prediction_created_at_utc: str
    created_by: str
    source_provenance: str
    predicted_second_zone: Optional[object] = None


@dataclass(frozen=True)
class BatchInput:
    activation_id: str
    preregistration_version: str
    prospective_protocol_version: str
    lottery_type: str
    target_draw: str
    draw_close_at_utc: Optional[str]
    draw_close_source: DrawCloseSource
    capture_mode: str
    created_by: str
    recorded_at_utc: str
    tickets: Sequence[TicketInput]


@dataclass(frozen=True)
class BatchCaptureResult:
    accepted: bool
    eligibility_status: str
    batch_id: Optional[str] = None
    ledger_ids: tuple = ()
    event_ids: tuple = ()
    rejection_reason: Optional[str] = None
    rejected_bet_index: Optional[int] = None


@dataclass(frozen=True)
class AmendmentResult:
    accepted: bool
    event_id: Optional[str] = None
    rejection_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Connection / pragma helpers
# ---------------------------------------------------------------------------


def _require_connection(conn: object) -> sqlite3.Connection:
    if not isinstance(conn, sqlite3.Connection):
        raise LedgerUsageError(
            "A sqlite3.Connection supplied by the caller is required; "
            "this module never opens a database path itself."
        )
    return conn


def _ensure_pragmas(conn: sqlite3.Connection) -> None:
    """Enable fail-closed pragmas and explicit transaction control.

    ``isolation_level = None`` puts the connection in autocommit mode so this
    module can issue ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` explicitly.
    ``PRAGMA foreign_keys`` and ``busy_timeout`` are per-connection and must be
    set outside any open transaction.
    """

    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_SCHEMA_STATEMENTS = (
    f"""
    CREATE TABLE IF NOT EXISTS {_META_TABLE} (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {_REGISTRY_TABLE} (
        activation_id               TEXT PRIMARY KEY,
        activation_artifact_commit  TEXT NOT NULL,
        deployed_implementation_commit TEXT NOT NULL,
        migration_verification_ref  TEXT NOT NULL,
        activation_merged_at_utc    TEXT NOT NULL,
        prospective_start_at_utc    TEXT NOT NULL,
        status                      TEXT NOT NULL DEFAULT 'INACTIVE',
        created_by                  TEXT NOT NULL,
        recorded_at_utc             TEXT NOT NULL
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {_BATCH_TABLE} (
        batch_id                     TEXT PRIMARY KEY,
        activation_id                TEXT NOT NULL,
        preregistration_version      TEXT NOT NULL,
        prospective_protocol_version TEXT NOT NULL,
        lottery_type                 TEXT NOT NULL,
        target_draw                  TEXT NOT NULL,
        draw_close_at_utc            TEXT NOT NULL,
        draw_close_source_id         TEXT NOT NULL,
        draw_close_source_version    TEXT NOT NULL,
        capture_mode                 TEXT NOT NULL,
        eligibility_status           TEXT NOT NULL,
        rejection_reason             TEXT,
        created_by                   TEXT NOT NULL,
        recorded_at_utc              TEXT NOT NULL,
        UNIQUE (activation_id, lottery_type, target_draw),
        FOREIGN KEY (activation_id)
            REFERENCES {_REGISTRY_TABLE} (activation_id)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {_LEDGER_TABLE} (
        ledger_id                    TEXT PRIMARY KEY,
        batch_id                     TEXT NOT NULL,
        activation_id                TEXT NOT NULL,
        preregistration_version      TEXT NOT NULL,
        prospective_protocol_version TEXT NOT NULL,
        lottery_type                 TEXT NOT NULL,
        target_draw                  TEXT NOT NULL,
        strategy_id                  TEXT NOT NULL,
        strategy_version             TEXT NOT NULL,
        bet_index                    INTEGER NOT NULL,
        predicted_main_numbers       TEXT NOT NULL,
        predicted_second_zone        INTEGER,
        prediction_created_at_utc    TEXT NOT NULL,
        draw_close_at_utc            TEXT NOT NULL,
        eligibility_status           TEXT NOT NULL,
        rejection_reason             TEXT,
        source_provenance            TEXT NOT NULL,
        payload_hash                 TEXT NOT NULL,
        created_by                   TEXT NOT NULL,
        recorded_at_utc              TEXT NOT NULL,
        UNIQUE (activation_id, lottery_type, target_draw,
                strategy_id, strategy_version, bet_index),
        FOREIGN KEY (batch_id) REFERENCES {_BATCH_TABLE} (batch_id),
        FOREIGN KEY (activation_id)
            REFERENCES {_REGISTRY_TABLE} (activation_id)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {_EVENT_TABLE} (
        event_id            TEXT PRIMARY KEY,
        event_type          TEXT NOT NULL,
        ledger_id           TEXT,
        batch_id            TEXT,
        actor               TEXT NOT NULL,
        service_identity    TEXT NOT NULL,
        code_commit         TEXT NOT NULL,
        source_artifact_hash TEXT,
        transaction_id      TEXT NOT NULL,
        event_payload       TEXT,
        recorded_at_utc     TEXT NOT NULL
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {_OUTCOME_TABLE} (
        outcome_link_id      TEXT PRIMARY KEY,
        ledger_id            TEXT NOT NULL,
        resolved_target_draw TEXT NOT NULL,
        outcome_ingested_at_utc TEXT NOT NULL,
        outcome_source_ref   TEXT NOT NULL,
        UNIQUE (ledger_id),
        FOREIGN KEY (ledger_id) REFERENCES {_LEDGER_TABLE} (ledger_id)
    )
    """,
)

# Deterministic unique indexes (in addition to inline UNIQUE constraints).
_INDEX_STATEMENTS = (
    f"""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_identity
        ON {_LEDGER_TABLE} (activation_id, lottery_type, target_draw,
                            strategy_id, strategy_version, bet_index)
    """,
    f"""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_batch_cluster
        ON {_BATCH_TABLE} (activation_id, lottery_type, target_draw)
    """,
)


def _trigger_statements() -> tuple:
    statements = []
    for table in _APPEND_ONLY_TABLES:
        statements.append(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT,
                    'append_only: UPDATE forbidden on {table}');
            END
            """
        )
        statements.append(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT,
                    'append_only: DELETE forbidden on {table}');
            END
            """
        )
    return tuple(statements)


REQUIRED_TABLES = (
    _META_TABLE,
    _REGISTRY_TABLE,
    _BATCH_TABLE,
    _LEDGER_TABLE,
    _EVENT_TABLE,
    _OUTCOME_TABLE,
)


def get_schema_version(conn: sqlite3.Connection) -> Optional[str]:
    """Return the installed schema version, or ``None`` if absent."""

    conn = _require_connection(conn)
    row = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (_META_TABLE,),
    ).fetchone()
    if row is None:
        return None
    rec = conn.execute(
        f"SELECT value FROM {_META_TABLE} WHERE key='schema_version'"
    ).fetchone()
    return None if rec is None else rec[0]


def _existing_prospective_tables(conn: sqlite3.Connection) -> set:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'prospective_%'"
    ).fetchall()
    return {r[0] for r in rows}


def install_schema(conn: sqlite3.Connection) -> str:
    """Install the P271J schema on a caller-supplied SQLite connection.

    Idempotent on an empty or same-version database. Fails closed
    (``SchemaVersionError``) on any incompatible pre-existing schema. Never
    touches a production database — the caller owns the connection.
    """

    conn = _require_connection(conn)
    _ensure_pragmas(conn)

    existing_version = get_schema_version(conn)
    if existing_version is not None and existing_version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Incompatible prospective schema version {existing_version!r}; "
            f"this module installs {SCHEMA_VERSION!r}."
        )
    if existing_version is None:
        # A foreign/legacy schema that already defines prospective tables
        # without our version marker is rejected rather than silently merged.
        stray = _existing_prospective_tables(conn)
        if stray:
            raise SchemaVersionError(
                "Pre-existing prospective_* tables without a recognized "
                f"schema version marker: {sorted(stray)}"
            )

    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in _SCHEMA_STATEMENTS:
            conn.execute(statement)
        for statement in _INDEX_STATEMENTS:
            conn.execute(statement)
        for statement in _trigger_statements():
            conn.execute(statement)
        conn.execute(
            f"INSERT OR IGNORE INTO {_META_TABLE} (key, value) VALUES "
            "('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return SCHEMA_VERSION


def schema_objects(conn: sqlite3.Connection) -> dict:
    """Return present tables / indexes / triggers (read-only inspection)."""

    conn = _require_connection(conn)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL"
        ).fetchall()
    }
    triggers = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    return {"tables": tables, "indexes": indexes, "triggers": triggers}


# ---------------------------------------------------------------------------
# Timestamp normalization
# ---------------------------------------------------------------------------


def _parse_utc(value: object) -> Optional[datetime]:
    """Parse a timezone-aware ISO-8601 string to a UTC datetime.

    Returns ``None`` for naive / ambiguous / unparseable input (the caller
    decides the fail-closed reason). Per the P271I timezone contract, any
    tz-aware offset (e.g. Asia/Taipei +08:00) is accepted and normalized to UTC;
    naive timestamps are rejected.
    """

    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # Accept a trailing 'Z' as UTC.
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return None
    return dt.astimezone(timezone.utc)


def _to_canonical_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Identity & payload hash (pure, deterministic)
# ---------------------------------------------------------------------------


def derive_ledger_id(
    activation_id: str,
    lottery_type: str,
    target_draw: str,
    strategy_id: str,
    strategy_version: str,
    bet_index: int,
) -> str:
    """Deterministic ledger id from the identity tuple.

    The same prospective ticket can never receive two distinct ledger ids, and
    a ledger id can never be supplied / overridden by a caller.
    """

    canonical = json.dumps(
        [
            activation_id,
            lottery_type,
            target_draw,
            strategy_id,
            strategy_version,
            int(bet_index),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"pl_{digest}"


def compute_payload_hash(
    activation_id: str,
    lottery_type: str,
    target_draw: str,
    strategy_id: str,
    strategy_version: str,
    bet_index: int,
    predicted_main_numbers: Sequence[int],
    predicted_second_zone: Optional[int],
    prediction_created_at_utc: str,
) -> str:
    """Deterministic SHA-256 over canonical prediction content (P271I)."""

    canonical = json.dumps(
        {
            "activation_id": activation_id,
            "lottery_type": lottery_type,
            "target_draw": target_draw,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "bet_index": int(bet_index),
            "predicted_main_numbers": sorted(int(n) for n in predicted_main_numbers),
            "predicted_second_zone": (
                None if predicted_second_zone is None else int(predicted_second_zone)
            ),
            "prediction_created_at_utc": prediction_created_at_utc,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation helpers (P271C-compatible; capture only, never scoring)
# ---------------------------------------------------------------------------


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_main_numbers(lottery_type: str, numbers: object) -> Optional[list]:
    """Return a sorted copy, or ``None`` if invalid. Never mutates the input."""

    if numbers is None or isinstance(numbers, (str, bytes)):
        return None
    try:
        values = list(numbers)
    except TypeError:
        return None
    expected = _MAIN_PICK_COUNT[lottery_type]
    if len(values) != expected:
        return None
    lo, hi = _MAIN_NUMBER_RANGE[lottery_type]
    for v in values:
        if not _is_int(v) or v < lo or v > hi:
            return None
    if len(set(values)) != len(values):
        return None
    return sorted(values)


def _validate_second_zone(lottery_type: str, value: object) -> tuple:
    """Validate the predicted second zone for a ticket.

    Returns ``(ok, normalized_value, reason)``. ``normalized_value`` is ``None``
    for lotteries without a second zone.
    """

    if lottery_type in _REQUIRES_SECOND_ZONE:
        if value is None:
            return (False, None, REASON_MISSING_OR_INVALID_SECOND_ZONE)
        if not _is_int(value):
            return (False, None, REASON_MISSING_OR_INVALID_SECOND_ZONE)
        lo, hi = _SECOND_ZONE_RANGE
        if value < lo or value > hi:
            return (False, None, REASON_MISSING_OR_INVALID_SECOND_ZONE)
        return (True, int(value), None)
    # Non-POWER lotteries must not carry a predicted second zone.
    if value is not None:
        return (False, None, REASON_SECOND_ZONE_NOT_PERMITTED)
    return (True, None, None)


def _evaluate_draw_close_source(source: object) -> tuple:
    """Validate a draw-close source descriptor.

    Returns ``(ok, reason)`` where ``ok`` means the source is structurally valid
    *and* confirmatory-eligible. ``reason`` is the fail-closed rejection reason
    otherwise.
    """

    if not isinstance(source, DrawCloseSource):
        return (False, REASON_SOURCE_PROVENANCE_FAILURE)
    if source.source_type not in _SOURCE_TYPES:
        return (False, REASON_SOURCE_PROVENANCE_FAILURE)
    if not source.source_id or not source.source_version:
        return (False, REASON_SOURCE_PROVENANCE_FAILURE)
    if not isinstance(source.provenance, Mapping) or not source.provenance:
        return (False, REASON_SOURCE_PROVENANCE_FAILURE)
    # Clock-skew margin must be an explicit, non-negative number (no default).
    margin = source.clock_skew_margin_seconds
    if not _is_int(margin) or margin < 0:
        return (False, REASON_SOURCE_PROVENANCE_FAILURE)
    # Manual sources can never be confirmatory.
    if source.source_type == SOURCE_MANUAL:
        return (False, REASON_MANUAL_SOURCE_NOT_CONFIRMATORY)
    # Official / deterministic sources are confirmatory only after manual
    # verification (PENDING_MANUAL_VERIFICATION / ONLY_AFTER_MANUAL_VERIFICATION).
    if source.source_type in _MANUAL_VERIFICATION_GATED_SOURCES:
        if not source.manually_verified:
            return (False, REASON_SOURCE_PENDING_MANUAL_VERIFICATION)
    return (True, None)


def _source_is_stale(source: DrawCloseSource, reference_utc: datetime) -> bool:
    """Fail-closed freshness check when the source declares a window."""

    if source.snapshot_at_utc is None and source.freshness_window_seconds is None:
        return False  # No declared freshness window for this source.
    snapshot = _parse_utc(source.snapshot_at_utc)
    if snapshot is None or not _is_int(source.freshness_window_seconds):
        return True  # Declared-but-broken freshness fails closed.
    if source.freshness_window_seconds < 0:
        return True
    age = (reference_utc - snapshot).total_seconds()
    return age > source.freshness_window_seconds or age < 0


# ---------------------------------------------------------------------------
# Activation registration & lifecycle (append-only)
# ---------------------------------------------------------------------------


def register_activation(
    conn: sqlite3.Connection,
    *,
    activation_id: str,
    activation_artifact_commit: str,
    deployed_implementation_commit: str,
    migration_verification_ref: str,
    activation_merged_at_utc: str,
    prospective_start_at_utc: str,
    recorded_at_utc: str,
    created_by: str,
    actor: str,
    service_identity: str,
    code_commit: str,
    initial_status: str = "ACTIVE",
) -> str:
    """Append one immutable activation registry row plus an ACTIVATION event.

    This is a synthetic activation definition. It does not activate production
    collection and inserts no real activation timestamp into any production
    database — it writes only to the caller-supplied (synthetic) connection.
    """

    conn = _require_connection(conn)
    _ensure_pragmas(conn)
    start = _parse_utc(prospective_start_at_utc)
    merged = _parse_utc(activation_merged_at_utc)
    recorded = _parse_utc(recorded_at_utc)
    if start is None or merged is None or recorded is None:
        raise LedgerUsageError("activation timestamps must be tz-aware UTC ISO-8601")
    if initial_status not in ("ACTIVE", "INACTIVE"):
        raise LedgerUsageError("initial_status must be ACTIVE or INACTIVE")

    txn_id = f"txn_register_{activation_id}"
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            f"""
            INSERT INTO {_REGISTRY_TABLE}
                (activation_id, activation_artifact_commit,
                 deployed_implementation_commit, migration_verification_ref,
                 activation_merged_at_utc, prospective_start_at_utc,
                 status, created_by, recorded_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activation_id,
                activation_artifact_commit,
                deployed_implementation_commit,
                migration_verification_ref,
                _to_canonical_utc(merged),
                _to_canonical_utc(start),
                initial_status,
                created_by,
                _to_canonical_utc(recorded),
            ),
        )
        event_id = _insert_event(
            conn,
            event_type=EVENT_ACTIVATION,
            ledger_id=None,
            batch_id=None,
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
            transaction_id=txn_id,
            payload={
                "activation_id": activation_id,
                "effective_at_utc": _to_canonical_utc(start),
                "lifecycle": EVENT_ACTIVATION,
                "initial_status": initial_status,
            },
            recorded_at_utc=_to_canonical_utc(recorded),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return event_id


def append_activation_lifecycle_event(
    conn: sqlite3.Connection,
    *,
    activation_id: str,
    lifecycle: str,
    effective_at_utc: str,
    recorded_at_utc: str,
    actor: str,
    service_identity: str,
    code_commit: str,
    justification: Optional[str] = None,
) -> str:
    """Append an ACTIVATION / DEACTIVATION event without rewriting history."""

    conn = _require_connection(conn)
    _ensure_pragmas(conn)
    if lifecycle not in (EVENT_ACTIVATION, EVENT_DEACTIVATION):
        raise LedgerUsageError("lifecycle must be ACTIVATION or DEACTIVATION")
    effective = _parse_utc(effective_at_utc)
    recorded = _parse_utc(recorded_at_utc)
    if effective is None or recorded is None:
        raise LedgerUsageError("lifecycle timestamps must be tz-aware UTC ISO-8601")

    conn.execute("BEGIN IMMEDIATE")
    try:
        event_id = _insert_event(
            conn,
            event_type=lifecycle,
            ledger_id=None,
            batch_id=None,
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
            transaction_id=f"txn_lifecycle_{activation_id}_{lifecycle}",
            payload={
                "activation_id": activation_id,
                "effective_at_utc": _to_canonical_utc(effective),
                "lifecycle": lifecycle,
                "justification": justification,
            },
            recorded_at_utc=_to_canonical_utc(recorded),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return event_id


def deactivate_activation(
    conn: sqlite3.Connection,
    *,
    activation_id: str,
    effective_at_utc: str,
    recorded_at_utc: str,
    actor: str,
    service_identity: str,
    code_commit: str,
    justification: str,
) -> str:
    """Deactivate by appending a DEACTIVATION event (never a row rewrite)."""

    return append_activation_lifecycle_event(
        conn,
        activation_id=activation_id,
        lifecycle=EVENT_DEACTIVATION,
        effective_at_utc=effective_at_utc,
        recorded_at_utc=recorded_at_utc,
        actor=actor,
        service_identity=service_identity,
        code_commit=code_commit,
        justification=justification,
    )


def _activation_row(conn: sqlite3.Connection, activation_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        f"SELECT * FROM {_REGISTRY_TABLE} WHERE activation_id=?",
        (activation_id,),
    ).fetchone()


def _lifecycle_events(conn: sqlite3.Connection, activation_id: str) -> list:
    rows = conn.execute(
        f"""
        SELECT event_payload FROM {_EVENT_TABLE}
        WHERE event_type IN (?, ?)
        ORDER BY recorded_at_utc ASC, event_id ASC
        """,
        (EVENT_ACTIVATION, EVENT_DEACTIVATION),
    ).fetchall()
    out = []
    for (payload_text,) in rows:
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except (ValueError, TypeError):
            continue
        if payload.get("activation_id") != activation_id:
            continue
        eff = _parse_utc(payload.get("effective_at_utc"))
        if eff is None:
            continue
        out.append((eff, payload.get("lifecycle")))
    return out


def is_activation_active(
    conn: sqlite3.Connection, activation_id: str, at_utc: str
) -> bool:
    """Return whether an activation is active at the supplied UTC instant.

    Active-state is derived from the append-only event stream (latest lifecycle
    event effective at or before ``at_utc``), gated by the registry row and its
    ``prospective_start_at_utc``. Deactivation never rewrites history.
    """

    conn = _require_connection(conn)
    conn.row_factory = sqlite3.Row
    row = _activation_row(conn, activation_id)
    if row is None:
        return False
    at = _parse_utc(at_utc)
    start = _parse_utc(row["prospective_start_at_utc"])
    if at is None or start is None:
        return False
    if at < start:
        return False
    latest_state = None
    for eff, lifecycle in _lifecycle_events(conn, activation_id):
        if eff <= at:
            latest_state = lifecycle
    if latest_state is None:
        # No lifecycle event applies yet; fall back to the registry's recorded
        # initial status.
        return row["status"] == "ACTIVE"
    return latest_state == EVENT_ACTIVATION


# ---------------------------------------------------------------------------
# Event insertion
# ---------------------------------------------------------------------------


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    ledger_id: Optional[str],
    batch_id: Optional[str],
    actor: str,
    service_identity: str,
    code_commit: str,
    transaction_id: str,
    payload: Optional[dict],
    recorded_at_utc: str,
    source_artifact_hash: Optional[str] = None,
) -> str:
    seed = json.dumps(
        [event_type, ledger_id, batch_id, transaction_id, payload, recorded_at_utc],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    event_id = "ev_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    conn.execute(
        f"""
        INSERT INTO {_EVENT_TABLE}
            (event_id, event_type, ledger_id, batch_id, actor,
             service_identity, code_commit, source_artifact_hash,
             transaction_id, event_payload, recorded_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            ledger_id,
            batch_id,
            actor,
            service_identity,
            code_commit,
            source_artifact_hash,
            transaction_id,
            None if payload is None else json.dumps(payload, ensure_ascii=False, sort_keys=True),
            recorded_at_utc,
        ),
    )
    return event_id


def _record_rejection_event(
    conn: sqlite3.Connection,
    *,
    batch: BatchInput,
    reason: str,
    bet_index: Optional[int],
    actor: str,
    service_identity: str,
    code_commit: str,
) -> str:
    """Append an immutable rejection event in its own transaction.

    Called only after the capture transaction has been rolled back, so it can
    reference an attempted (non-persisted) batch identity without violating any
    foreign key (the event table carries no FK by design).
    """

    txn_id = f"txn_reject_{batch.activation_id}_{batch.lottery_type}_{batch.target_draw}"
    conn.execute("BEGIN IMMEDIATE")
    try:
        event_id = _insert_event(
            conn,
            event_type=EVENT_CAPTURE_REJECTED,
            ledger_id=None,
            batch_id=None,
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
            transaction_id=txn_id,
            payload={
                "rejection_reason": reason,
                "rejected_bet_index": bet_index,
                "activation_id": batch.activation_id,
                "lottery_type": batch.lottery_type,
                "target_draw": batch.target_draw,
                "capture_mode": batch.capture_mode,
            },
            recorded_at_utc=batch.recorded_at_utc
            if _parse_utc(batch.recorded_at_utc)
            else _fallback_event_time(batch),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return event_id


def _fallback_event_time(batch: BatchInput) -> str:
    """A deterministic non-empty recorded-at for rejection events when the
    caller-supplied recorded_at is itself invalid. Uses the draw close if
    parseable, else a fixed sentinel — never invents 'now'."""

    close = _parse_utc(batch.draw_close_at_utc)
    if close is not None:
        return _to_canonical_utc(close)
    return "1970-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Atomic batch capture
# ---------------------------------------------------------------------------


def capture_batch(
    conn: sqlite3.Connection,
    batch: BatchInput,
    *,
    known_strategy_versions: Iterable[tuple],
    actor: str = "p271j-synthetic-capture",
    service_identity: str = "prospective_capture_ledger",
    code_commit: str = "synthetic",
) -> BatchCaptureResult:
    """Atomically capture one (activation, lottery_type, target_draw) cluster.

    All tickets are validated and inserted inside a single ``BEGIN IMMEDIATE``
    transaction. Any failure rolls back the entire batch (all-or-nothing); no
    partial ledger / batch / event rows persist, and an immutable rejection
    event is appended afterward. Only ``LIVE_PRE_CLOSE`` captures backed by a
    confirmatory, fresh draw-close source and an active activation can become
    eligible prospective rows.
    """

    conn = _require_connection(conn)
    _ensure_pragmas(conn)

    if not isinstance(batch, BatchInput):
        raise LedgerUsageError("batch must be a BatchInput")
    known = {
        (str(s), str(v))
        for (s, v) in (known_strategy_versions or ())
    }

    try:
        plan = _plan_batch(conn, batch, known)
    except _BatchRejected as rej:
        event_id = _record_rejection_event(
            conn,
            batch=batch,
            reason=rej.reason,
            bet_index=rej.bet_index,
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
        )
        return BatchCaptureResult(
            accepted=False,
            eligibility_status=ELIGIBILITY_REJECTED,
            rejection_reason=rej.reason,
            rejected_bet_index=rej.bet_index,
            event_ids=(event_id,),
        )

    # Everything validated outside the write transaction; now write atomically.
    txn_id = f"txn_capture_{batch.activation_id}_{batch.lottery_type}_{batch.target_draw}"
    reason: Optional[str] = None
    bet_index: Optional[int] = None
    ledger_ids = []
    event_ids = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"""
            INSERT INTO {_BATCH_TABLE}
                (batch_id, activation_id, preregistration_version,
                 prospective_protocol_version, lottery_type, target_draw,
                 draw_close_at_utc, draw_close_source_id, draw_close_source_version,
                 capture_mode, eligibility_status, rejection_reason,
                 created_by, recorded_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["batch_id"],
                batch.activation_id,
                batch.preregistration_version,
                batch.prospective_protocol_version,
                batch.lottery_type,
                batch.target_draw,
                plan["draw_close_at_utc"],
                batch.draw_close_source.source_id,
                batch.draw_close_source.source_version,
                batch.capture_mode,
                ELIGIBILITY_ELIGIBLE,
                None,
                batch.created_by,
                plan["recorded_at_utc"],
            ),
        )
        for ticket_plan in plan["tickets"]:
            conn.execute(
                f"""
                INSERT INTO {_LEDGER_TABLE}
                    (ledger_id, batch_id, activation_id, preregistration_version,
                     prospective_protocol_version, lottery_type, target_draw,
                     strategy_id, strategy_version, bet_index,
                     predicted_main_numbers, predicted_second_zone,
                     prediction_created_at_utc, draw_close_at_utc,
                     eligibility_status, rejection_reason, source_provenance,
                     payload_hash, created_by, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_plan["ledger_id"],
                    plan["batch_id"],
                    batch.activation_id,
                    batch.preregistration_version,
                    batch.prospective_protocol_version,
                    batch.lottery_type,
                    batch.target_draw,
                    ticket_plan["strategy_id"],
                    ticket_plan["strategy_version"],
                    ticket_plan["bet_index"],
                    json.dumps(ticket_plan["predicted_main_numbers"]),
                    ticket_plan["predicted_second_zone"],
                    ticket_plan["prediction_created_at_utc"],
                    plan["draw_close_at_utc"],
                    ELIGIBILITY_ELIGIBLE,
                    None,
                    ticket_plan["source_provenance"],
                    ticket_plan["payload_hash"],
                    ticket_plan["created_by"],
                    plan["recorded_at_utc"],
                ),
            )
            ledger_ids.append(ticket_plan["ledger_id"])
            ev = _insert_event(
                conn,
                event_type=EVENT_CAPTURE,
                ledger_id=ticket_plan["ledger_id"],
                batch_id=plan["batch_id"],
                actor=actor,
                service_identity=service_identity,
                code_commit=code_commit,
                transaction_id=txn_id,
                payload={"payload_hash": ticket_plan["payload_hash"]},
                recorded_at_utc=plan["recorded_at_utc"],
            )
            event_ids.append(ev)
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        reason = REASON_DUPLICATE_IDENTITY
    except _BatchRejected as rej:  # pragma: no cover - validation is pre-transaction
        conn.execute("ROLLBACK")
        reason = rej.reason
        bet_index = rej.bet_index
    except Exception:
        conn.execute("ROLLBACK")
        reason = REASON_TRANSACTION_FAILURE

    if reason is not None:
        event_id = _record_rejection_event(
            conn,
            batch=batch,
            reason=reason,
            bet_index=bet_index,
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
        )
        return BatchCaptureResult(
            accepted=False,
            eligibility_status=ELIGIBILITY_REJECTED,
            rejection_reason=reason,
            rejected_bet_index=bet_index,
            event_ids=(event_id,),
        )

    return BatchCaptureResult(
        accepted=True,
        eligibility_status=ELIGIBILITY_ELIGIBLE,
        batch_id=plan["batch_id"],
        ledger_ids=tuple(ledger_ids),
        event_ids=tuple(event_ids),
    )


def _plan_batch(conn: sqlite3.Connection, batch: BatchInput, known: set) -> dict:
    """Validate the whole batch fail-closed. Raises ``_BatchRejected``.

    Performed before opening the write transaction so a rejection never leaves
    partial rows. The semantic unique key (not this planning step) remains the
    authority on duplicates; the in-transaction insert still fails closed on any
    conflict.
    """

    # --- batch-level: lottery, capture mode, source, close time, causality, activation
    if batch.lottery_type not in SUPPORTED_LOTTERY_TYPES:
        raise _BatchRejected(REASON_UNSUPPORTED_LOTTERY)

    if batch.capture_mode not in _ALL_CAPTURE_MODES:
        raise _BatchRejected(REASON_BACKFILL_EXCLUDED)
    if batch.capture_mode != CAPTURE_MODE_LIVE_PRE_CLOSE:
        raise _BatchRejected(REASON_BACKFILL_EXCLUDED)  # F13: non-live excluded

    source_ok, source_reason = _evaluate_draw_close_source(batch.draw_close_source)
    if not source_ok:
        raise _BatchRejected(source_reason)

    close_dt = _parse_utc(batch.draw_close_at_utc)
    if batch.draw_close_at_utc is None or (
        isinstance(batch.draw_close_at_utc, str) and not batch.draw_close_at_utc.strip()
    ):
        raise _BatchRejected(REASON_CLOSE_TIME_MISSING)
    if close_dt is None:
        raise _BatchRejected(REASON_AMBIGUOUS_TIMESTAMP)

    recorded_dt = _parse_utc(batch.recorded_at_utc)
    if recorded_dt is None:
        raise _BatchRejected(REASON_AMBIGUOUS_TIMESTAMP)

    if _source_is_stale(batch.draw_close_source, recorded_dt):
        raise _BatchRejected(REASON_STALE_SCHEDULE)

    if not is_activation_active(conn, batch.activation_id, batch.recorded_at_utc):
        raise _BatchRejected(REASON_INACTIVE_ACTIVATION)

    margin = int(batch.draw_close_source.clock_skew_margin_seconds)

    tickets = list(batch.tickets or [])
    if not tickets:
        raise _BatchRejected(REASON_EMPTY_BATCH)

    seen_identity = set()
    planned = []
    for ticket in tickets:
        if not isinstance(ticket, TicketInput):
            raise _BatchRejected(REASON_INVALID_PREDICTED_NUMBERS)

        if not _is_int(ticket.bet_index) or ticket.bet_index < 0:
            raise _BatchRejected(REASON_INVALID_PREDICTED_NUMBERS, None)
        bet_index = int(ticket.bet_index)

        # strategy version must be resolvable to an immutable known version
        if (str(ticket.strategy_id), str(ticket.strategy_version)) not in known:
            raise _BatchRejected(REASON_UNKNOWN_STRATEGY_VERSION, bet_index)

        main = _validate_main_numbers(batch.lottery_type, ticket.predicted_main_numbers)
        if main is None:
            raise _BatchRejected(REASON_INVALID_PREDICTED_NUMBERS, bet_index)

        zone_ok, zone_value, zone_reason = _validate_second_zone(
            batch.lottery_type, ticket.predicted_second_zone
        )
        if not zone_ok:
            raise _BatchRejected(zone_reason, bet_index)

        created_dt = _parse_utc(ticket.prediction_created_at_utc)
        if created_dt is None:
            raise _BatchRejected(REASON_AMBIGUOUS_TIMESTAMP, bet_index)

        # Causality: prediction must precede draw close minus the per-source margin.
        if not (created_dt.timestamp() < close_dt.timestamp() - margin):
            raise _BatchRejected(REASON_POST_CLOSE_SUBMISSION, bet_index)

        if not ticket.source_provenance or not isinstance(ticket.source_provenance, str):
            raise _BatchRejected(REASON_SOURCE_PROVENANCE_FAILURE, bet_index)

        identity = (
            batch.activation_id,
            batch.lottery_type,
            batch.target_draw,
            str(ticket.strategy_id),
            str(ticket.strategy_version),
            bet_index,
        )
        if identity in seen_identity:
            raise _BatchRejected(REASON_DUPLICATE_IDENTITY, bet_index)
        seen_identity.add(identity)

        ledger_id = derive_ledger_id(*identity)
        payload_hash = compute_payload_hash(
            batch.activation_id,
            batch.lottery_type,
            batch.target_draw,
            str(ticket.strategy_id),
            str(ticket.strategy_version),
            bet_index,
            main,
            zone_value,
            _to_canonical_utc(created_dt),
        )
        planned.append(
            {
                "ledger_id": ledger_id,
                "strategy_id": str(ticket.strategy_id),
                "strategy_version": str(ticket.strategy_version),
                "bet_index": bet_index,
                "predicted_main_numbers": main,
                "predicted_second_zone": zone_value,
                "prediction_created_at_utc": _to_canonical_utc(created_dt),
                "source_provenance": ticket.source_provenance,
                "payload_hash": payload_hash,
                "created_by": ticket.created_by,
            }
        )

    batch_seed = json.dumps(
        [batch.activation_id, batch.lottery_type, batch.target_draw],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    batch_id = "pb_" + hashlib.sha256(batch_seed.encode("utf-8")).hexdigest()[:32]

    return {
        "batch_id": batch_id,
        "draw_close_at_utc": _to_canonical_utc(close_dt),
        "recorded_at_utc": _to_canonical_utc(recorded_dt),
        "tickets": planned,
    }


# ---------------------------------------------------------------------------
# Amendment (append-only; never rewrites the original)
# ---------------------------------------------------------------------------


def append_amendment(
    conn: sqlite3.Connection,
    *,
    original_ledger_id: str,
    reason: str,
    amended_payload: Mapping[str, object],
    effective_at_utc: str,
    recorded_at_utc: str,
    actor: str,
    service_identity: str,
    code_commit: str,
) -> AmendmentResult:
    """Append a correction as a new AMENDMENT event referencing the original.

    The original ledger row is never updated or deleted. A post-close amendment
    is ineligible. An amendment that attempts to alter any identity-tuple field
    (which would silently change prospective membership) is rejected.
    """

    conn = _require_connection(conn)
    _ensure_pragmas(conn)

    original = get_ledger_row(conn, original_ledger_id)
    if original is None:
        return AmendmentResult(accepted=False, rejection_reason=REASON_UNKNOWN_LEDGER_ROW)

    effective = _parse_utc(effective_at_utc)
    recorded = _parse_utc(recorded_at_utc)
    close = _parse_utc(original["draw_close_at_utc"])
    if effective is None or recorded is None:
        raise LedgerUsageError("amendment timestamps must be tz-aware UTC ISO-8601")
    if close is not None and effective.timestamp() >= close.timestamp():
        return AmendmentResult(accepted=False, rejection_reason=REASON_POST_CLOSE_AMENDMENT)

    # Reject any attempt to change identity-tuple fields via amendment.
    identity_fields = (
        "activation_id",
        "lottery_type",
        "target_draw",
        "strategy_id",
        "strategy_version",
        "bet_index",
    )
    for field_name in identity_fields:
        if field_name in amended_payload and str(amended_payload[field_name]) != str(
            original[field_name]
        ):
            return AmendmentResult(
                accepted=False, rejection_reason=REASON_AMENDMENT_ALTERS_IDENTITY
            )

    conn.execute("BEGIN IMMEDIATE")
    try:
        event_id = _insert_event(
            conn,
            event_type=EVENT_AMENDMENT,
            ledger_id=original_ledger_id,
            batch_id=original["batch_id"],
            actor=actor,
            service_identity=service_identity,
            code_commit=code_commit,
            transaction_id=f"txn_amend_{original_ledger_id}",
            payload={
                "reason": reason,
                "amended_payload": dict(amended_payload),
                "effective_at_utc": _to_canonical_utc(effective),
                "original_payload_hash": original["payload_hash"],
            },
            recorded_at_utc=_to_canonical_utc(recorded),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return AmendmentResult(accepted=True, event_id=event_id)


# ---------------------------------------------------------------------------
# Read-only inspection helpers (never join outcome tables; never score)
# ---------------------------------------------------------------------------


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def get_ledger_row(conn: sqlite3.Connection, ledger_id: str) -> Optional[dict]:
    conn = _require_connection(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT * FROM {_LEDGER_TABLE} WHERE ledger_id=?", (ledger_id,)
    ).fetchone()
    return _row_to_dict(row)


def get_batch(conn: sqlite3.Connection, batch_id: str) -> Optional[dict]:
    conn = _require_connection(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        f"SELECT * FROM {_BATCH_TABLE} WHERE batch_id=?", (batch_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_ledger_rows(
    conn: sqlite3.Connection,
    *,
    activation_id: Optional[str] = None,
    lottery_type: Optional[str] = None,
    target_draw: Optional[str] = None,
    eligibility_status: Optional[str] = None,
) -> list:
    conn = _require_connection(conn)
    conn.row_factory = sqlite3.Row
    clauses = []
    params = []
    if activation_id is not None:
        clauses.append("activation_id=?")
        params.append(activation_id)
    if lottery_type is not None:
        clauses.append("lottery_type=?")
        params.append(lottery_type)
    if target_draw is not None:
        clauses.append("target_draw=?")
        params.append(target_draw)
    if eligibility_status is not None:
        clauses.append("eligibility_status=?")
        params.append(eligibility_status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {_LEDGER_TABLE}{where} ORDER BY ledger_id ASC", params
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_events(
    conn: sqlite3.Connection, *, event_type: Optional[str] = None
) -> list:
    conn = _require_connection(conn)
    conn.row_factory = sqlite3.Row
    if event_type is None:
        rows = conn.execute(
            f"SELECT * FROM {_EVENT_TABLE} ORDER BY recorded_at_utc ASC, event_id ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM {_EVENT_TABLE} WHERE event_type=? "
            "ORDER BY recorded_at_utc ASC, event_id ASC",
            (event_type,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_eligible_rows(conn: sqlite3.Connection) -> int:
    conn = _require_connection(conn)
    row = conn.execute(
        f"SELECT COUNT(*) FROM {_LEDGER_TABLE} WHERE eligibility_status=?",
        (ELIGIBILITY_ELIGIBLE,),
    ).fetchone()
    return int(row[0])


def verify_payload_hash(conn: sqlite3.Connection, ledger_id: str) -> bool:
    """Recompute and compare the stored payload hash for a ledger row."""

    row = get_ledger_row(conn, ledger_id)
    if row is None:
        return False
    main = json.loads(row["predicted_main_numbers"])
    recomputed = compute_payload_hash(
        row["activation_id"],
        row["lottery_type"],
        row["target_draw"],
        row["strategy_id"],
        row["strategy_version"],
        row["bet_index"],
        main,
        row["predicted_second_zone"],
        row["prediction_created_at_utc"],
    )
    return recomputed == row["payload_hash"]
