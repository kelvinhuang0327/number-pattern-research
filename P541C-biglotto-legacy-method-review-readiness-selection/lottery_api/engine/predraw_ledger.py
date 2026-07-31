"""
predraw_ledger.py
==================
P360A pre-draw metadata instrumentation.

Scope (per P359_TRUE_OOS_NOT_SUPPORTED_BY_CURRENT_METADATA and the Fable5
P360A design review, DESIGN_ACCEPTABLE_WITH_REQUIRED_ADDITIONS):
  - An append-only JSONL sidecar ledger, entirely separate from the canonical
    `lottery_v2.db`. This module NEVER opens the canonical DB for write.
  - Writing a LIVE_PREDRAW record here is NOT a predictive claim, a bet
    recommendation, or evidence that any strategy has edge. It only enables a
    FUTURE honest OOS audit once enough genuinely pre-registered live records
    accumulate. See docs/p360a_predraw_metadata_preregistration.md.
  - The existing retrospective replay corpus in `strategy_prediction_replays`
    remains permanently non-OOS; this module does not read, write, or relabel
    that table.

Core design decisions (why, not just what):
  - generation_mode is a VERIFIED condition, not a caller-supplied label.
    `write_live_prediction()` is the ONLY function that can produce
    generation_mode=LIVE_PREDRAW, and it independently re-checks the
    mechanical witness conditions (max_source_draw_at_generation < target_draw,
    predicted_at < scheduled_draw_close_at, predicted_at < outcome_ingested_at
    if known) before writing. `write_retrospective_record()` structurally
    cannot emit LIVE_PREDRAW -- it is not part of its accepted mode set.
  - predicted_at for LIVE_PREDRAW is always writer-assigned (`now`, tz-aware
    UTC); it is not an accepted parameter, so a caller cannot backdate it.
  - Every record is chained via record_hash = sha256(canonical_json(payload)
    + "|" + prev_record_hash), so a later whole-ledger regeneration changes
    every hash from the tamper point forward. This is tamper-EVIDENT, not
    tamper-PROOF: without an external anchor (e.g. committing the ledger, or
    its head hash, to git before each draw) a full-file rewrite is still
    undetectable. That anchoring step is intentionally left to the calling
    workflow/task, not this module.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.9+ ships zoneinfo
    ZoneInfo = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SCHEMA_VERSION = "p360a-v1"

# Fixed, non-canonical sidecar path. NEVER the canonical lottery_v2.db.
DEFAULT_LEDGER_PATH = PROJECT_ROOT / "lottery_api" / "data" / "predraw_prediction_ledger.jsonl"
DEFAULT_SCHEDULE_CONFIG_PATH = PROJECT_ROOT / "lottery_api" / "data" / "predraw_schedule_config.json"

# Any path resolving to one of these basenames is refused as a ledger path.
_CANONICAL_DB_BASENAMES = frozenset({"lottery_v2.db"})

# generation_mode values a WRITER may produce. LEGACY_UNLABELED is a
# reader-only classification for pre-P360A / unrecognized records -- it is
# never accepted as a write-time argument.
GENERATION_MODES: Tuple[str, ...] = (
    "LIVE_PREDRAW",
    "RETROSPECTIVE_REPLAY",
    "BACKFILL",
    "REGENERATED",
)
_RETROSPECTIVE_MODES = ("RETROSPECTIVE_REPLAY", "BACKFILL", "REGENERATED")
LEGACY_UNLABELED = "LEGACY_UNLABELED"

LOTTERY_TYPES: Tuple[str, ...] = ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")
_SPECIAL_MANDATORY_TYPES = frozenset({"POWER_LOTTO"})
_SPECIAL_FORBIDDEN_TYPES = frozenset({"DAILY_539"})


# ─── Errors ────────────────────────────────────────────────────────────────

class LedgerPathError(ValueError):
    """Raised when a ledger path resolves to (or under) the canonical DB file."""


class LiveEligibilityError(ValueError):
    """
    Raised when a caller requests LIVE_PREDRAW but the mechanical witness
    conditions do not hold. Fails closed: this is always a hard refusal,
    never a silent downgrade to another mode.
    """


class NaiveDatetimeError(ValueError):
    """Raised when a datetime lacks tzinfo (UTC-aware required everywhere)."""


class LedgerTruncationError(ValueError):
    """Raised by strict readers when a ledger line is not valid JSON."""


# ─── Time / serialization helpers ───────────────────────────────────────────

def _require_aware(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise NaiveDatetimeError(
            f"{field_name} must be timezone-aware (UTC); got naive datetime {dt!r}"
        )
    return dt


def _iso(dt: datetime) -> str:
    _require_aware(dt, "datetime")
    return dt.astimezone(timezone.utc).isoformat()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_record_hash(payload: Dict[str, Any], prev_record_hash: Optional[str]) -> str:
    """
    sha256 over canonical_json(payload) + "|" + prev_record_hash.
    `payload` must NOT already contain 'record_hash' or 'prev_record_hash'.
    """
    if "record_hash" in payload or "prev_record_hash" in payload:
        raise ValueError(
            "payload must not include 'record_hash'/'prev_record_hash' when computing the hash"
        )
    body = _canonical_json(payload) + "|" + (prev_record_hash or "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def compute_params_hash(params: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(params).encode("utf-8")).hexdigest()


def _guard_noncanonical_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    if resolved.name in _CANONICAL_DB_BASENAMES:
        raise LedgerPathError(
            f"Refusing to use canonical DB basename as a ledger path: {resolved}"
        )
    return resolved


# ─── Source DB fingerprint (read-only helpers) ──────────────────────────────

@dataclass(frozen=True)
class SourceDbFingerprint:
    path: str
    per_lottery_max_draw: Dict[str, Optional[int]]
    row_count: int
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "per_lottery_max_draw": dict(self.per_lottery_max_draw),
            "row_count": self.row_count,
            "content_hash": self.content_hash,
        }


def compute_source_db_fingerprint(
    db_path: str,
    lottery_types: Sequence[str] = LOTTERY_TYPES,
) -> SourceDbFingerprint:
    """
    Opens `db_path` STRICTLY read-only (mode=ro + PRAGMA query_only=ON) and
    computes, per lottery_type, the max ingested draw number (as INTEGER, per
    the project's `draw` TEXT-ordering rule) and total row count. Does not
    compute a full-file content hash by default (99MB canonical DB makes that
    expensive on every call) -- callers needing that can hash `db_path`
    themselves and pass it through `SourceDbFingerprint(content_hash=...)`.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON;")
        per_lottery_max: Dict[str, Optional[int]] = {}
        total_rows = 0
        for lt in lottery_types:
            cur = conn.execute(
                "SELECT MAX(CAST(draw AS INTEGER)), COUNT(*) FROM draws WHERE lottery_type = ?",
                (lt,),
            )
            max_draw, cnt = cur.fetchone()
            per_lottery_max[lt] = int(max_draw) if max_draw is not None else None
            total_rows += cnt or 0
        return SourceDbFingerprint(
            path=str(db_path), per_lottery_max_draw=per_lottery_max, row_count=total_rows
        )
    finally:
        conn.close()


def compute_max_source_draw(db_path: str, lottery_type: str) -> Optional[int]:
    """Read-only max ingested draw (as int) for one lottery_type, or None."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON;")
        cur = conn.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = ?",
            (lottery_type,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()


# ─── Code identity ───────────────────────────────────────────────────────────

def get_code_git_sha(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Returns {"code_git_sha": sha_or_None, "code_dirty_flag": bool_or_None}.
    Never raises -- git absence/failure yields None values (still recorded).
    """
    root = str(repo_root or PROJECT_ROOT)
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) != 0
        return {"code_git_sha": sha, "code_dirty_flag": bool(dirty)}
    except Exception:
        return {"code_git_sha": None, "code_dirty_flag": None}


# ─── Schedule config ─────────────────────────────────────────────────────────

def load_schedule_config(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path or DEFAULT_SCHEDULE_CONFIG_PATH)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_scheduled_draw_close_at(
    target_draw_date: str,
    lottery_type: str,
    schedule_config: Dict[str, Any],
) -> datetime:
    """
    Returns a tz-aware UTC datetime: the conservative draw-close cutoff for
    `target_draw_date` (a "YYYY-MM-DD" or "YYYY/MM/DD" local date string).
    """
    if ZoneInfo is None:  # pragma: no cover
        raise RuntimeError("zoneinfo is required (Python 3.9+)")
    rules = schedule_config.get("rules", {})
    rule = rules.get(lottery_type)
    if not rule:
        raise KeyError(f"No schedule rule for lottery_type={lottery_type!r}")
    tz_name = schedule_config.get("timezone", "Asia/Taipei")
    tz = ZoneInfo(tz_name)
    date_str = target_draw_date.replace("/", "-")
    year, month, day = (int(x) for x in date_str.split("-"))
    close_time_str = rule["conservative_close_time_local"]
    hour, minute, second = (int(x) for x in close_time_str.split(":"))
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


# ─── Writer ──────────────────────────────────────────────────────────────────

class PredrawLedgerWriter:
    """
    Append-only writer for one JSONL ledger file. No update/delete API exists
    on this class by design -- corrections must be REGENERATED records that
    reference the record they supersede, never in-place edits.
    """

    def __init__(self, ledger_path: Optional[Path] = None):
        self.ledger_path = _guard_noncanonical_path(Path(ledger_path or DEFAULT_LEDGER_PATH))
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    # -- internal --

    def _last_record_hash(self) -> Optional[str]:
        if not self.ledger_path.exists():
            return None
        last_line = None
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        return json.loads(last_line).get("record_hash")

    def _append(self, record: Dict[str, Any]) -> None:
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(_canonical_json(record) + "\n")

    def _validate_payload_shape(
        self, lottery_type: str, predicted_special: Optional[int]
    ) -> None:
        if lottery_type not in LOTTERY_TYPES:
            raise ValueError(f"Unknown lottery_type: {lottery_type!r}")
        if lottery_type in _SPECIAL_MANDATORY_TYPES and predicted_special is None:
            raise ValueError(f"predicted_special is mandatory for {lottery_type}")
        if lottery_type in _SPECIAL_FORBIDDEN_TYPES and predicted_special is not None:
            raise ValueError(f"{lottery_type} has no special number; predicted_special must be None")

    def _write_record(
        self,
        *,
        generation_mode: str,
        lottery_type: str,
        target_draw: int,
        target_draw_date: Optional[str],
        scheduled_draw_close_at: Optional[str],
        schedule_rule_version: Optional[str],
        history_cutoff_draw: Optional[int],
        history_cutoff_date: Optional[str],
        max_source_draw_at_generation: Optional[int],
        max_source_draw_date_at_generation: Optional[str],
        source_db_fingerprint: Optional[Dict[str, Any]],
        strategy_id: str,
        strategy_version: str,
        params: Optional[Dict[str, Any]],
        random_seed: Optional[int],
        strategy_artifact_hash: Optional[str],
        predicted_numbers: Sequence[int],
        predicted_special: Optional[int],
        bet_index: int,
        n_bets_total: int,
        run_id: str,
        generation_source: str,
        supersedes_record_id: Optional[str],
        predicted_at: datetime,
    ) -> Dict[str, Any]:
        created_at = utcnow()
        git_info = get_code_git_sha()
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "record_id": str(uuid.uuid4()),
            "record_kind": "PREDICTION",
            "lottery_type": lottery_type,
            "generation_mode": generation_mode,
            "predicted_at": _iso(predicted_at),
            "created_at": _iso(created_at),
            "target_draw": int(target_draw),
            "target_draw_date": target_draw_date,
            "scheduled_draw_close_at": scheduled_draw_close_at,
            "schedule_rule_version": schedule_rule_version,
            "history_cutoff_draw": history_cutoff_draw,
            "history_cutoff_date": history_cutoff_date,
            "max_source_draw_at_generation": max_source_draw_at_generation,
            "max_source_draw_date_at_generation": max_source_draw_date_at_generation,
            "source_db_fingerprint": source_db_fingerprint,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "code_git_sha": git_info["code_git_sha"],
            "code_dirty_flag": git_info["code_dirty_flag"],
            "params_hash": compute_params_hash(params) if params is not None else None,
            "random_seed": random_seed,
            "strategy_artifact_hash": strategy_artifact_hash,
            "predicted_numbers": [int(n) for n in predicted_numbers],
            "predicted_special": predicted_special,
            "bet_index": bet_index,
            "n_bets_total": n_bets_total,
            "run_id": run_id,
            "generation_source": generation_source,
            "supersedes_record_id": supersedes_record_id,
        }
        prev_hash = self._last_record_hash()
        record_hash = compute_record_hash(payload, prev_hash)
        full_record = dict(payload)
        full_record["prev_record_hash"] = prev_hash
        full_record["record_hash"] = record_hash
        self._append(full_record)
        return full_record

    # -- public: the ONLY entry point that can produce LIVE_PREDRAW --

    def write_live_prediction(
        self,
        *,
        lottery_type: str,
        target_draw: int,
        target_draw_date: str,
        strategy_id: str,
        strategy_version: str,
        predicted_numbers: Sequence[int],
        predicted_special: Optional[int],
        bet_index: int,
        n_bets_total: int,
        run_id: str,
        generation_source: str,
        max_source_draw_at_generation: int,
        max_source_draw_date_at_generation: Optional[str] = None,
        source_db_fingerprint: Optional[SourceDbFingerprint] = None,
        history_cutoff_draw: Optional[int] = None,
        history_cutoff_date: Optional[str] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        random_seed: Optional[int] = None,
        strategy_artifact_hash: Optional[str] = None,
        outcome_ingested_at: Optional[datetime] = None,
        now_fn=utcnow,
    ) -> Dict[str, Any]:
        """
        Writes a LIVE_PREDRAW record. `predicted_at` is NOT a parameter --
        it is always assigned by this function as `now_fn()` so a caller
        cannot backdate liveness. Raises LiveEligibilityError (fails CLOSED,
        never silently downgrades) if any witness condition fails:
          1. max_source_draw_at_generation < target_draw  (no-look-ahead)
          2. predicted_at < scheduled_draw_close_at(target_draw_date)
          3. predicted_at < outcome_ingested_at, if the caller supplies it
        """
        self._validate_payload_shape(lottery_type, predicted_special)
        if max_source_draw_at_generation is None:
            raise LiveEligibilityError(
                "max_source_draw_at_generation is required (missing witness) for LIVE_PREDRAW"
            )
        target_draw = int(target_draw)
        max_source_draw_at_generation = int(max_source_draw_at_generation)

        predicted_at = now_fn()
        _require_aware(predicted_at, "predicted_at")

        if not (max_source_draw_at_generation < target_draw):
            raise LiveEligibilityError(
                f"max_source_draw_at_generation ({max_source_draw_at_generation}) "
                f"must be < target_draw ({target_draw}) for LIVE_PREDRAW"
            )

        if not target_draw_date:
            raise LiveEligibilityError(
                "target_draw_date is required to compute scheduled_draw_close_at for LIVE_PREDRAW"
            )
        cfg = schedule_config or load_schedule_config()
        scheduled_close_at = compute_scheduled_draw_close_at(target_draw_date, lottery_type, cfg)
        schedule_rule_version = cfg.get("schedule_rule_version")
        if not (predicted_at < scheduled_close_at):
            raise LiveEligibilityError(
                f"predicted_at ({_iso(predicted_at)}) is not before "
                f"scheduled_draw_close_at ({_iso(scheduled_close_at)}) for LIVE_PREDRAW"
            )

        if outcome_ingested_at is not None:
            _require_aware(outcome_ingested_at, "outcome_ingested_at")
            if not (predicted_at < outcome_ingested_at):
                raise LiveEligibilityError(
                    f"predicted_at ({_iso(predicted_at)}) is not before "
                    f"outcome_ingested_at ({_iso(outcome_ingested_at)}) for LIVE_PREDRAW"
                )

        return self._write_record(
            generation_mode="LIVE_PREDRAW",
            lottery_type=lottery_type,
            target_draw=target_draw,
            target_draw_date=target_draw_date,
            scheduled_draw_close_at=_iso(scheduled_close_at),
            schedule_rule_version=schedule_rule_version,
            history_cutoff_draw=history_cutoff_draw,
            history_cutoff_date=history_cutoff_date,
            max_source_draw_at_generation=max_source_draw_at_generation,
            max_source_draw_date_at_generation=max_source_draw_date_at_generation,
            source_db_fingerprint=source_db_fingerprint.to_dict() if source_db_fingerprint else None,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            params=params,
            random_seed=random_seed,
            strategy_artifact_hash=strategy_artifact_hash,
            predicted_numbers=predicted_numbers,
            predicted_special=predicted_special,
            bet_index=bet_index,
            n_bets_total=n_bets_total,
            run_id=run_id,
            generation_source=generation_source,
            supersedes_record_id=None,
            predicted_at=predicted_at,
        )

    # -- public: BACKFILL / RETROSPECTIVE_REPLAY / REGENERATED only --

    def write_retrospective_record(
        self,
        *,
        generation_mode: str,
        lottery_type: str,
        target_draw: int,
        strategy_id: str,
        strategy_version: str,
        predicted_numbers: Sequence[int],
        predicted_special: Optional[int],
        bet_index: int,
        n_bets_total: int,
        run_id: str,
        generation_source: str,
        target_draw_date: Optional[str] = None,
        max_source_draw_at_generation: Optional[int] = None,
        max_source_draw_date_at_generation: Optional[str] = None,
        source_db_fingerprint: Optional[SourceDbFingerprint] = None,
        history_cutoff_draw: Optional[int] = None,
        history_cutoff_date: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        random_seed: Optional[int] = None,
        strategy_artifact_hash: Optional[str] = None,
        supersedes_record_id: Optional[str] = None,
        predicted_at: Optional[datetime] = None,
        now_fn=utcnow,
    ) -> Dict[str, Any]:
        """
        Writes a BACKFILL / RETROSPECTIVE_REPLAY / REGENERATED record.
        generation_mode=LIVE_PREDRAW is structurally rejected here -- callers
        needing a live record MUST use write_live_prediction() instead, which
        enforces the witness conditions this function does not check.
        """
        if generation_mode == "LIVE_PREDRAW":
            raise ValueError(
                "write_retrospective_record() cannot emit LIVE_PREDRAW; "
                "use write_live_prediction() for that."
            )
        if generation_mode not in _RETROSPECTIVE_MODES:
            raise ValueError(
                f"generation_mode must be one of {_RETROSPECTIVE_MODES}, got {generation_mode!r}"
            )
        if generation_mode == "REGENERATED" and not supersedes_record_id:
            raise ValueError("REGENERATED records require supersedes_record_id")
        if generation_mode != "REGENERATED" and supersedes_record_id:
            raise ValueError("supersedes_record_id is only valid when generation_mode=REGENERATED")

        self._validate_payload_shape(lottery_type, predicted_special)
        target_draw = int(target_draw)
        predicted_at = predicted_at or now_fn()
        _require_aware(predicted_at, "predicted_at")

        scheduled_close_at = None
        schedule_rule_version = None
        # Retrospective records MAY still carry a scheduled_draw_close_at for
        # descriptive/audit purposes, but it plays no eligibility role here.

        return self._write_record(
            generation_mode=generation_mode,
            lottery_type=lottery_type,
            target_draw=target_draw,
            target_draw_date=target_draw_date,
            scheduled_draw_close_at=scheduled_close_at,
            schedule_rule_version=schedule_rule_version,
            history_cutoff_draw=history_cutoff_draw,
            history_cutoff_date=history_cutoff_date,
            max_source_draw_at_generation=max_source_draw_at_generation,
            max_source_draw_date_at_generation=max_source_draw_date_at_generation,
            source_db_fingerprint=source_db_fingerprint.to_dict() if source_db_fingerprint else None,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            params=params,
            random_seed=random_seed,
            strategy_artifact_hash=strategy_artifact_hash,
            predicted_numbers=predicted_numbers,
            predicted_special=predicted_special,
            bet_index=bet_index,
            n_bets_total=n_bets_total,
            run_id=run_id,
            generation_source=generation_source,
            supersedes_record_id=supersedes_record_id,
            predicted_at=predicted_at,
        )

    # -- public: settlement (never mutates a prediction record) --

    def write_settlement(
        self,
        *,
        references_record_id: str,
        actual_numbers: Sequence[int],
        actual_special: Optional[int],
        hit_count: int,
        special_hit: bool,
        now_fn=utcnow,
    ) -> Dict[str, Any]:
        """
        Appends a SEPARATE settlement record referencing a prediction record
        by record_id. Never rewrites, updates, or touches the prediction
        record's own bytes or record_hash.
        """
        settled_at = now_fn()
        _require_aware(settled_at, "settled_at")
        payload: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "record_id": str(uuid.uuid4()),
            "record_kind": "SETTLEMENT",
            "references_record_id": references_record_id,
            "settled_at": _iso(settled_at),
            "actual_numbers": [int(n) for n in actual_numbers],
            "actual_special": actual_special,
            "hit_count": int(hit_count),
            "special_hit": bool(special_hit),
        }
        prev_hash = self._last_record_hash()
        record_hash = compute_record_hash(payload, prev_hash)
        full_record = dict(payload)
        full_record["prev_record_hash"] = prev_hash
        full_record["record_hash"] = record_hash
        self._append(full_record)
        return full_record


# ─── Reader / chain verification ────────────────────────────────────────────

def read_all_records(ledger_path: Path) -> List[Dict[str, Any]]:
    ledger_path = _guard_noncanonical_path(Path(ledger_path))
    if not ledger_path.exists():
        return []
    out = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


@dataclass
class ChainVerificationResult:
    ok: bool
    total_records: int
    first_broken_index: Optional[int]
    reason: Optional[str]


def verify_chain(ledger_path: Path) -> ChainVerificationResult:
    """
    Walks the ledger from the top, recomputing each record_hash from its
    payload + the previous record's stored hash. Detects:
      - single-byte tampering of any record's content (hash mismatch)
      - deletion/reordering of a record (prev_record_hash mismatch)
      - truncation (an unparsable/partial trailing line)
    """
    ledger_path = _guard_noncanonical_path(Path(ledger_path))
    if not ledger_path.exists():
        return ChainVerificationResult(True, 0, None, None)

    raw_lines = [ln for ln in ledger_path.read_text(encoding="utf-8").split("\n") if ln.strip()]
    records: List[Dict[str, Any]] = []
    for i, line in enumerate(raw_lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            return ChainVerificationResult(False, len(raw_lines), i, f"unparseable/truncated line at index {i}")

    prev_hash: Optional[str] = None
    for i, rec in enumerate(records):
        rec = dict(rec)
        stored_hash = rec.pop("record_hash", None)
        stored_prev = rec.pop("prev_record_hash", None)
        if stored_prev != prev_hash:
            return ChainVerificationResult(False, len(records), i, f"prev_record_hash mismatch at index {i}")
        recomputed = compute_record_hash(rec, prev_hash)
        if recomputed != stored_hash:
            return ChainVerificationResult(
                False, len(records), i, f"record_hash mismatch at index {i} (tampered content)"
            )
        prev_hash = stored_hash
    return ChainVerificationResult(True, len(records), None, None)


# ─── Eligibility / audit ────────────────────────────────────────────────────

@dataclass
class EligibilityResult:
    eligible: bool
    reason: str


def classify_generation_mode(record: Dict[str, Any]) -> str:
    """Any record missing/mis-declaring generation_mode maps to LEGACY_UNLABELED."""
    mode = record.get("generation_mode")
    return mode if mode in GENERATION_MODES else LEGACY_UNLABELED


def evaluate_oos_eligibility(record: Dict[str, Any]) -> EligibilityResult:
    """
    Re-derives eligibility from the record's OWN witness fields -- it does
    NOT trust generation_mode as a label alone beyond requiring it to equal
    LIVE_PREDRAW; every mechanical witness is independently re-checked here
    too, so a corrupted/hand-edited record cannot claim eligibility merely by
    setting generation_mode="LIVE_PREDRAW" without the supporting fields.
    """
    mode = classify_generation_mode(record)
    if mode != "LIVE_PREDRAW":
        return EligibilityResult(False, f"generation_mode={mode} is never OOS-eligible")

    if record.get("supersedes_record_id"):
        return EligibilityResult(False, "LIVE_PREDRAW must not carry supersedes_record_id")

    predicted_at_raw = record.get("predicted_at")
    if not predicted_at_raw:
        return EligibilityResult(False, "missing predicted_at")
    try:
        predicted_at = datetime.fromisoformat(predicted_at_raw)
    except ValueError:
        return EligibilityResult(False, "unparseable predicted_at")
    if predicted_at.tzinfo is None:
        return EligibilityResult(False, "predicted_at is not timezone-aware")

    scheduled_close_raw = record.get("scheduled_draw_close_at")
    if not scheduled_close_raw:
        return EligibilityResult(False, "missing scheduled_draw_close_at")
    try:
        scheduled_close_at = datetime.fromisoformat(scheduled_close_raw)
    except ValueError:
        return EligibilityResult(False, "unparseable scheduled_draw_close_at")
    if not (predicted_at < scheduled_close_at):
        return EligibilityResult(False, "predicted_at is not before scheduled_draw_close_at")

    target_draw = record.get("target_draw")
    max_source = record.get("max_source_draw_at_generation")
    if target_draw is None or max_source is None:
        return EligibilityResult(False, "missing target_draw or max_source_draw_at_generation")
    if not (int(max_source) < int(target_draw)):
        return EligibilityResult(False, "max_source_draw_at_generation is not < target_draw")

    return EligibilityResult(True, "eligible")


def select_eligible_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Per-record eligibility, then earliest-eligible-record-wins for duplicate
    (strategy_id, lottery_type, target_draw, bet_index) keys.
    """
    candidates = []
    for rec in records:
        if rec.get("record_kind", "PREDICTION") != "PREDICTION":
            continue
        if evaluate_oos_eligibility(rec).eligible:
            candidates.append(rec)

    best: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for rec in candidates:
        key = (rec["strategy_id"], rec["lottery_type"], rec["target_draw"], rec.get("bet_index"))
        existing = best.get(key)
        if existing is None or rec["predicted_at"] < existing["predicted_at"]:
            best[key] = rec
    return list(best.values())


@dataclass
class AuditReport:
    status: str
    per_strategy_eligible_counts: Dict[str, int]
    total_eligible: int
    minimum_n_required: Dict[str, int]
    below_minimum: bool
    note: str


def p361_dry_run_audit(
    records: List[Dict[str, Any]],
    minimum_n_by_lottery: Dict[str, int],
) -> AuditReport:
    """
    Pre-registered-N-aware dry-run: reports ELIGIBLE COUNTS ONLY. This
    function never computes a hit rate, edge, ROI, or significance value --
    that is deliberate. See docs/p360a_predraw_metadata_preregistration.md
    for why performance analysis must wait for the pre-registered minimum N
    of genuinely LIVE_PREDRAW-eligible records per lottery_type.
    """
    eligible = select_eligible_records(records)
    per_strategy: Dict[str, int] = {}
    per_lottery_counts: Dict[str, int] = {}
    for rec in eligible:
        per_strategy[rec["strategy_id"]] = per_strategy.get(rec["strategy_id"], 0) + 1
        per_lottery_counts[rec["lottery_type"]] = per_lottery_counts.get(rec["lottery_type"], 0) + 1

    below_minimum = any(
        per_lottery_counts.get(lt, 0) < min_n for lt, min_n in minimum_n_by_lottery.items()
    )

    return AuditReport(
        status="ACCUMULATING",
        per_strategy_eligible_counts=per_strategy,
        total_eligible=len(eligible),
        minimum_n_required=dict(minimum_n_by_lottery),
        below_minimum=below_minimum,
        note=(
            "Eligible-record counts only. No performance/edge/ROI/significance "
            "is computed by this function, regardless of N."
        ),
    )
