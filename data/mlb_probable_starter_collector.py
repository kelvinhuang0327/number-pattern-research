"""
data/mlb_probable_starter_collector.py
======================================
P202E — Pregame Probable-Starter Collector Adapter Skeleton (FIXTURE-ONLY)

在 P202D 的可信本地快照契約（``data/mlb_probable_starter_snapshots.py``）之上，
只補上「來源邊界」這一塊，且**完全不含真實傳輸/網路**：

  synthetic source payload
    -> source-shape validation
    -> deterministic game extraction
    -> probable-starter mapping
    -> P202D normalized snapshot records
    -> (optional) append via an explicit caller-supplied path

設計鐵則（NEVER violate）：
  - 純標準函式庫；零網路（無 requests/httpx/urllib/socket）。
  - 不呼叫任何 live API（含 statsapi.mlb.com）；不呼叫 fetch_probable_starters()。
  - 傳輸（transport）與時鐘（clock）皆為**注入式 callable**，**無 default 實作**。
  - 不接 scheduler / recommendation / evaluator / model。
  - 不寫真實 runtime 資料；唯有 caller 顯式提供 output_path 時才透過 P202D append。
  - 重用 P202D ``normalize_snapshot`` / ``append_snapshot``，**不修改** P202D。
  - 賽後/完賽（final/live）局不得作為賽前快照；actual/as-played 欄位 → 拒絕（非靜默忽略）。
  - 一律 diagnostic_only=True、production_ready=False；永不 learning_eligible。

來源形狀（依 ``data/mlb_player_stats.py`` fetch_probable_starters 之 schedule?hydrate=probablePitcher
回應結構；本模組僅以**合成** payload 演練，永不實際抓取）：
  {"dates": [{"games": [{
      "gamePk": int, "gameDate": ISO-UTC, "officialDate": "YYYY-MM-DD",
      "doubleHeader": "N"|"S"|"Y", "gameNumber": 1|2,
      "status": {"abstractGameState": ..., "detailedState": ...},
      "teams": {"home"/"away": {"team": {"id": int},
                                "probablePitcher": {"id": int, "fullName": str}}}
  }]}]}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from data.mlb_probable_starter_snapshots import (
    ProbableStarterSnapshot,
    SnapshotStoreError,
    SnapshotValidationError,
    append_snapshot,
    normalize_snapshot,
)

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
COLLECTOR_VERSION: str = "p202e_probable_starter_collector_v1"
COLLECTOR_PARSER_VERSION: str = "p202e_collector_parser_v1"

# 賽前可接受之 game-status（小寫 detailedState / abstractGameState）。
_SCHEDULED_STATES: frozenset[str] = frozenset({
    "scheduled", "pre-game", "pregame", "preview", "warmup",
})
_POSTPONED_STATES: frozenset[str] = frozenset({"postponed"})
_CANCELLED_STATES: frozenset[str] = frozenset({"cancelled", "canceled"})
_SUSPENDED_STATES: frozenset[str] = frozenset({"suspended"})
# 完賽/進行中 → 非賽前候選，一律拒絕（杜絕賽後 outcome 滲透）。
_FINAL_LIVE_STATES: frozenset[str] = frozenset({
    "final", "game over", "completed early", "in progress", "live",
    "manager challenge",
})

# 來源端 leakage 詞彙（鏡射 P202D §9：賽後 outcome + as-played/actual starter）。
# 出現任一即拒絕該局（非靜默忽略）。遞迴掃描鍵名。
_SOURCE_LEAKAGE_KEYS: frozenset[str] = frozenset({
    "home_win", "away_win", "final_score", "home_score", "away_score",
    "result", "box_score", "boxscore", "post_game_stats", "postgame_stats",
    "actual_winner", "winning_team", "game_outcome", "is_final", "linescore",
    "decisions",
    "home_actual_starter", "away_actual_starter",
    "home_actual_starter_id", "away_actual_starter_id",
    "actual_home_starter_id", "actual_away_starter_id",
    "actual_starter", "actual_starters", "as_played", "asplayed",
    "is_as_played", "starter_origin_actual", "is_actual_starter",
})
_LEAKAGE_SCAN_MAX_DEPTH: int = 5


# ─── Result types ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RejectedRecord:
    source_ref: str
    reason: str


@dataclass(frozen=True)
class CollectorResult:
    status: str                                   # ok | source_unavailable | malformed_payload
    accepted: tuple[ProbableStarterSnapshot, ...]
    rejected: tuple[RejectedRecord, ...]
    accepted_count: int
    rejected_count: int
    partial_count: int
    appended_count: int
    duplicate_count: int


# ─── Internal control-flow exception ─────────────────────────────────────────────
class _GameRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ─── Helpers ─────────────────────────────────────────────────────────────────────
def _scan_for_leakage(obj: Any, depth: int = 0) -> Optional[str]:
    """Return the first leakage key name found (recursively), else None."""
    if depth > _LEAKAGE_SCAN_MAX_DEPTH:
        return None
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key in _SOURCE_LEAKAGE_KEYS:
                return key
            found = _scan_for_leakage(value, depth + 1)
            if found:
                return found
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found = _scan_for_leakage(item, depth + 1)
            if found:
                return found
    return None


def _map_game_status(game: dict) -> str:
    status = game.get("status")
    if not isinstance(status, dict):
        raise _GameRejected("missing_or_malformed_status")
    abstract = str(status.get("abstractGameState", "")).strip().lower()
    detailed = str(status.get("detailedState", "")).strip().lower()
    if abstract in ("final", "live") or detailed in _FINAL_LIVE_STATES:
        raise _GameRejected("final_or_live_not_pregame")
    if detailed in _POSTPONED_STATES or abstract == "postponed":
        return "postponed"
    if detailed in _CANCELLED_STATES:
        return "cancelled"
    if detailed in _SUSPENDED_STATES:
        return "suspended"
    if "delayed" in detailed:
        return "delayed"
    if detailed in _SCHEDULED_STATES or abstract == "preview":
        return "scheduled"
    raise _GameRejected(f"unknown_game_status: detailed={detailed!r} abstract={abstract!r}")


def _side_fields(teams: dict, side: str) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
    block = teams.get(side)
    if not isinstance(block, dict):
        raise _GameRejected(f"missing_{side}_team_block")
    team = block.get("team")
    if not isinstance(team, dict) or team.get("id") is None:
        raise _GameRejected(f"missing_{side}_team_id")
    team_id = team.get("id")
    pp = block.get("probablePitcher")
    if pp is None:
        pp = {}
    if not isinstance(pp, dict):
        raise _GameRejected(f"malformed_{side}_probable_pitcher")
    pid = pp.get("id")
    pname = pp.get("fullName")
    status_hint = block.get("probableStatus")  # synthetic optional override
    return team_id, pid, pname, status_hint


def _derive_pitcher_status(pid: Any, status_hint: Any) -> str:
    if status_hint is not None:
        # validated downstream by P202D enum check
        return str(status_hint)
    if pid is not None:
        return "probable"
    return "tbd"


def _map_game_to_raw(
    game: Any,
    *,
    collected_at_utc: Any,
    information_cutoff_utc: Any,
    source_provider: str,
    source_endpoint_or_feed_id: str,
) -> dict:
    if not isinstance(game, dict):
        raise _GameRejected("malformed_game_record")

    leak = _scan_for_leakage(game)
    if leak is not None:
        raise _GameRejected(f"leakage_field_present: {leak}")

    game_pk = game.get("gamePk")
    if isinstance(game_pk, bool) or not isinstance(game_pk, int):
        raise _GameRejected("missing_game_pk")

    scheduled = game.get("gameDate")
    if not isinstance(scheduled, str) or not scheduled.strip():
        raise _GameRejected("missing_scheduled_start")

    teams = game.get("teams")
    if not isinstance(teams, dict):
        raise _GameRejected("missing_teams")
    home_team_id, home_pid, home_pname, home_hint = _side_fields(teams, "home")
    away_team_id, away_pid, away_pname, away_hint = _side_fields(teams, "away")

    game_status = _map_game_status(game)

    dh = str(game.get("doubleHeader", "N")).strip().upper()
    game_number = game.get("gameNumber", 1)
    if isinstance(game_number, bool) or not isinstance(game_number, int):
        raise _GameRejected("malformed_game_number")
    dh_no = game_number if dh in ("S", "Y") else 0

    official = game.get("officialDate")
    if not isinstance(official, str) or not official.strip():
        # Deterministic fallback: UTC date prefix of the scheduled start.
        official = scheduled[:10]

    freshness = game.get("sourceFreshnessSeconds", 0)
    if isinstance(freshness, bool) or not isinstance(freshness, int) or freshness < 0:
        freshness = 0

    raw: dict = {
        "source_provider": source_provider,
        "source_endpoint_or_feed_id": source_endpoint_or_feed_id,
        "source_record_id": f"{game_pk}:{dh_no}",
        "collected_at_utc": collected_at_utc,
        "information_cutoff_utc": information_cutoff_utc,
        "game_pk": game_pk,
        "scheduled_start_utc": scheduled,
        "official_game_date": official,
        "doubleheader_game_number": dh_no,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "home_probable_pitcher_id": home_pid,
        "home_probable_pitcher_name": home_pname,
        "away_probable_pitcher_id": away_pid,
        "away_probable_pitcher_name": away_pname,
        "home_pitcher_status": _derive_pitcher_status(home_pid, home_hint),
        "away_pitcher_status": _derive_pitcher_status(away_pid, away_hint),
        "game_status": game_status,
        "source_freshness_seconds": freshness,
    }
    return raw


def _game_ref(game: Any, date_idx: int, game_idx: int) -> str:
    if isinstance(game, dict) and isinstance(game.get("gamePk"), int) and not isinstance(game.get("gamePk"), bool):
        return f"gamePk={game['gamePk']}"
    return f"dates[{date_idx}].games[{game_idx}]"


# ─── Public adapter（pure；no I/O）──────────────────────────────────────────────
def adapt_schedule_payload(
    payload: Any,
    *,
    collected_at_utc: Any,
    information_cutoff_utc: Any,
    source_provider: str,
    source_endpoint_or_feed_id: str,
    parser_version: str = COLLECTOR_PARSER_VERSION,
) -> CollectorResult:
    """Map a synthetic schedule payload into P202D normalized snapshots (no I/O).

    Returns a :class:`CollectorResult` with accepted snapshots and explicit
    rejected-record diagnostics. Never raises for per-game problems (they become
    rejections); only programmer errors propagate. Performs no network or file I/O.
    """
    if not isinstance(source_provider, str) or not source_provider.strip():
        raise ValueError("source_provider must be a non-empty string")
    if not isinstance(source_endpoint_or_feed_id, str) or not source_endpoint_or_feed_id.strip():
        raise ValueError("source_endpoint_or_feed_id must be a non-empty string")

    if not isinstance(payload, dict):
        return CollectorResult("malformed_payload", (), (RejectedRecord("payload", "payload_not_object"),), 0, 1, 0, 0, 0)
    if payload.get("source_unavailable") is True:
        return CollectorResult("source_unavailable", (), (RejectedRecord("payload", "source_unavailable"),), 0, 1, 0, 0, 0)
    dates = payload.get("dates")
    if not isinstance(dates, list):
        return CollectorResult("malformed_payload", (), (RejectedRecord("payload", "missing_dates_list"),), 0, 1, 0, 0, 0)

    accepted: list[ProbableStarterSnapshot] = []
    rejected: list[RejectedRecord] = []

    for i, date_entry in enumerate(dates):
        if not isinstance(date_entry, dict) or not isinstance(date_entry.get("games"), list):
            rejected.append(RejectedRecord(f"dates[{i}]", "malformed_date_entry"))
            continue
        for j, game in enumerate(date_entry["games"]):
            ref = _game_ref(game, i, j)
            try:
                raw = _map_game_to_raw(
                    game,
                    collected_at_utc=collected_at_utc,
                    information_cutoff_utc=information_cutoff_utc,
                    source_provider=source_provider,
                    source_endpoint_or_feed_id=source_endpoint_or_feed_id,
                )
                snap = normalize_snapshot(raw, parser_version=parser_version)
                accepted.append(snap)
            except _GameRejected as exc:
                rejected.append(RejectedRecord(ref, exc.reason))
            except SnapshotValidationError as exc:
                rejected.append(RejectedRecord(ref, f"normalize_rejected: {exc}"))

    partial = sum(1 for s in accepted if s.snapshot_status == "partial")
    return CollectorResult(
        status="ok",
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        partial_count=partial,
        appended_count=0,
        duplicate_count=0,
    )


# ─── Orchestration with injected transport/clock ─────────────────────────────────
def collect_probable_starters(
    *,
    transport: Callable[[Any], Any],
    request: Any,
    source_provider: str,
    source_endpoint_or_feed_id: str,
    information_cutoff_utc: Any,
    collected_at_utc: Any = None,
    clock: Optional[Callable[[], Any]] = None,
    parser_version: str = COLLECTOR_PARSER_VERSION,
    output_path: Any = None,
) -> CollectorResult:
    """Drive an injected transport callable, adapt the payload, optionally persist.

    - ``transport`` is REQUIRED (no default; no network library). It receives only
      ``request`` and returns a payload (or ``None`` for source-unavailable).
    - ``collected_at_utc`` may be given explicitly, or via an injected ``clock``
      callable. There is no default clock (no implicit wall-clock read).
    - A transport exception or ``None`` payload becomes an explicit
      ``source_unavailable`` diagnostic (never a silent failure).
    - Persists only when ``output_path`` is explicitly provided (P202D append-only;
      exact duplicates are no-ops, revisions append). No default output path; no
      runtime directory is created. No retry/sleep/scheduling/daemon behavior.
    """
    if transport is None or not callable(transport):
        raise ValueError("an explicit transport callable is required (no default transport)")
    if collected_at_utc is None:
        if clock is None or not callable(clock):
            raise ValueError("either collected_at_utc or an injected clock callable is required")
        collected_at_utc = clock()

    try:
        payload = transport(request)
    except Exception as exc:  # noqa: BLE001 - any transport failure is source-unavailable
        return CollectorResult(
            "source_unavailable", (), (RejectedRecord("transport", f"transport_exception: {exc}"),),
            0, 1, 0, 0, 0,
        )

    if payload is None:
        return CollectorResult(
            "source_unavailable", (), (RejectedRecord("transport", "transport_returned_none"),),
            0, 1, 0, 0, 0,
        )

    result = adapt_schedule_payload(
        payload,
        collected_at_utc=collected_at_utc,
        information_cutoff_utc=information_cutoff_utc,
        source_provider=source_provider,
        source_endpoint_or_feed_id=source_endpoint_or_feed_id,
        parser_version=parser_version,
    )

    if output_path is None or not result.accepted:
        return result

    # Optional persistence (P202D append-only). Malformed store raises explicitly.
    appended = 0
    duplicates = 0
    for snap in result.accepted:
        append_result = append_snapshot(snap, output_path)
        if append_result.appended:
            appended += 1
        else:
            duplicates += 1

    return CollectorResult(
        status=result.status,
        accepted=result.accepted,
        rejected=result.rejected,
        accepted_count=result.accepted_count,
        rejected_count=result.rejected_count,
        partial_count=result.partial_count,
        appended_count=appended,
        duplicate_count=duplicates,
    )
