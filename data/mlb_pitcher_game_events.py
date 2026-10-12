"""Strict, auditable MLB pitcher-game event primitives.

This module is intentionally isolated from production feature and settlement
paths. It accepts caller-supplied or decoded finalized-boxscore payloads only;
it does not perform network collection or infer missing pitcher statistics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONTRACT_VERSION = "p202g-b.v1"
PARSER_VERSION = "p202g-b.statsapi-decoded.v1"

EVENT_FIELDS = (
    "contract_version",
    "source_provider",
    "source_endpoint_or_feed_id",
    "source_record_id",
    "payload_fingerprint",
    "collected_at_utc",
    "game_pk",
    "game_start_utc",
    "game_finalized_at_utc",
    "official_game_date",
    "pitcher_id",
    "pitcher_name",
    "team_id",
    "opponent_team_id",
    "home_away",
    "appearance_sequence",
    "starter_flag",
    "record_status",
    "innings_outs",
    "innings_pitched_display",
    "batters_faced",
    "strikeouts",
    "walks",
    "intentional_walks",
    "hit_by_pitch",
    "home_runs_allowed",
    "hits_allowed",
    "earned_runs",
    "runs_allowed",
    "pitches_thrown",
    "strikes",
    "parser_version",
    "diagnostic_only",
    "production_ready",
)

ALLOWED_RECORD_STATUSES = {
    "final",
    "corrected",
    "superseded",
    "malformed",
    "source_unavailable",
}
NORMALIZABLE_RECORD_STATUSES = {"final", "corrected", "superseded"}
FORBIDDEN_KEY_TOKENS = {
    "odds",
    "recommendation",
    "recommendedbet",
    "winner",
    "homescore",
    "awayscore",
    "finalscore",
    "settlement",
    "settled",
    "modeloutput",
    "modelprobability",
    "learningeligible",
}
PROXY_KEY_TOKENS = {
    "estimated",
    "estimate",
    "proxy",
    "averaged",
    "averageallocated",
    "distributed",
    "syntheticallocation",
}
PROXY_VALUE_TOKENS = (
    "schedule_proxy",
    "proxy_fallback",
    "estimated",
    "averaged",
    "distributed",
)


class PitcherGameEventError(ValueError):
    """Raised when an event violates the P202G-B contract."""


class PitcherEventStoreError(RuntimeError):
    """Raised when JSONL storage cannot be validated safely."""


@dataclass(frozen=True)
class PitcherGameEvent:
    contract_version: str
    source_provider: str
    source_endpoint_or_feed_id: str
    source_record_id: str
    payload_fingerprint: str
    collected_at_utc: str
    game_pk: int
    game_start_utc: str
    game_finalized_at_utc: str
    official_game_date: str
    pitcher_id: int
    pitcher_name: str
    team_id: int
    opponent_team_id: int
    home_away: str
    appearance_sequence: int
    starter_flag: bool
    record_status: str
    innings_outs: int
    innings_pitched_display: str
    batters_faced: int
    strikeouts: int
    walks: int
    intentional_walks: int | None
    hit_by_pitch: int
    home_runs_allowed: int
    hits_allowed: int
    earned_runs: int
    runs_allowed: int
    pitches_thrown: int | None
    strikes: int | None
    parser_version: str
    diagnostic_only: bool
    production_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def dedup_key(self) -> tuple[Any, ...]:
        return (
            self.source_provider,
            self.source_record_id,
            self.game_pk,
            self.pitcher_id,
            self.appearance_sequence,
            self.collected_at_utc,
            self.payload_fingerprint,
        )

    @property
    def logical_event_key(self) -> tuple[int, int]:
        """Stable revision identity for one pitcher in one game.

        Contract v1 stores exactly one logical pitching line per
        ``(game_pk, pitcher_id)``. ``appearance_sequence`` is observed source
        ordering metadata only and must never partition revision history.
        """
        return (self.game_pk, self.pitcher_id)

    @property
    def source_lineage_key(self) -> tuple[str, str]:
        """Source provenance lineage for one observation stream.

        Revision resolution happens only within a single lineage. Different
        ``source_provider`` values or different ``source_endpoint_or_feed_id``
        values are never automatic revisions of one another, so a later row
        from another lineage must never silently overwrite an earlier one.
        The logical event identity stays ``(game_pk, pitcher_id)``; the complete
        source identity is this lineage plus ``source_record_id``.
        """
        return (self.source_provider, self.source_endpoint_or_feed_id)


@dataclass(frozen=True)
class AdapterDiagnostic:
    code: str
    message: str
    game_pk: int | None = None
    pitcher_id: int | None = None


@dataclass(frozen=True)
class AdapterResult:
    events: tuple[PitcherGameEvent, ...]
    diagnostics: tuple[AdapterDiagnostic, ...]
    accepted_records: int
    rejected_records: int


@dataclass(frozen=True)
class AppendResult:
    appended: int
    duplicates_skipped: int
    total_records: int


@dataclass(frozen=True)
class PriorSelectionResult:
    status: str
    events: tuple[PitcherGameEvent, ...]
    diagnostics: tuple[str, ...]
    information_cutoff_utc: str
    max_included_game_start_utc: str | None


def _key_token(value: Any) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _walk_payload(value: Any, path: str = "$") -> Iterable[tuple[str, Any, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield str(key), child, child_path
            yield from _walk_payload(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_payload(child, f"{path}[{index}]")


def reject_proxy_or_outcome_leakage(payload: Mapping[str, Any]) -> None:
    """Reject estimated allocation and downstream outcome/decision fields."""

    for key, value, path in _walk_payload(payload):
        token = _key_token(key)
        if token in FORBIDDEN_KEY_TOKENS:
            raise PitcherGameEventError(f"forbidden outcome/decision field at {path}")
        if token in PROXY_KEY_TOKENS and value not in (False, None, 0, "", []):
            raise PitcherGameEventError(f"estimated/proxy field is not allowed at {path}")
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in PROXY_VALUE_TOKENS):
                raise PitcherGameEventError(f"estimated/proxy source marker at {path}")


def parse_utc_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PitcherGameEventError(f"{field_name} must be a non-empty UTC timestamp")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PitcherGameEventError(f"{field_name} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PitcherGameEventError(f"{field_name} must be explicitly UTC")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def innings_display_to_outs(value: Any) -> int:
    """Convert baseball innings notation, where the suffix counts outs."""

    if not isinstance(value, str) or value.count(".") != 1:
        raise PitcherGameEventError("innings_pitched_display must use baseball notation")
    whole, remainder = value.split(".", 1)
    if not whole.isdigit() or remainder not in {"0", "1", "2"}:
        raise PitcherGameEventError("innings suffix must be exactly .0, .1, or .2")
    return int(whole) * 3 + int(remainder)


def outs_to_innings_display(outs: int) -> str:
    if isinstance(outs, bool) or not isinstance(outs, int) or outs < 0:
        raise PitcherGameEventError("innings_outs must be a non-negative integer")
    return f"{outs // 3}.{outs % 3}"


def _required_text(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise PitcherGameEventError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_int(raw: Mapping[str, Any], field_name: str, *, positive: bool = False) -> int:
    value = raw.get(field_name)
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "positive" if positive else "non-negative"
        raise PitcherGameEventError(f"{field_name} must be a {qualifier} integer")
    return value


def _optional_int(raw: Mapping[str, Any], field_name: str) -> int | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PitcherGameEventError(f"{field_name} must be null or a non-negative integer")
    return value


def _canonical_fingerprint(fields: Mapping[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_pitcher_game_event(raw: Mapping[str, Any]) -> PitcherGameEvent:
    """Validate and normalize one complete pitcher appearance."""

    if not isinstance(raw, Mapping):
        raise PitcherGameEventError("event must be an object")
    unknown_fields = set(raw) - set(EVENT_FIELDS)
    if unknown_fields:
        raise PitcherGameEventError(
            f"unknown event fields: {', '.join(sorted(map(str, unknown_fields)))}"
        )
    reject_proxy_or_outcome_leakage(raw)

    contract_version = raw.get("contract_version", CONTRACT_VERSION)
    parser_version = raw.get("parser_version", PARSER_VERSION)
    if contract_version != CONTRACT_VERSION:
        raise PitcherGameEventError(f"unsupported contract_version: {contract_version}")
    if parser_version != PARSER_VERSION:
        raise PitcherGameEventError(f"unsupported parser_version: {parser_version}")

    source_provider = _required_text(raw, "source_provider")
    source_feed = _required_text(raw, "source_endpoint_or_feed_id")
    source_record_id = _required_text(raw, "source_record_id")

    collected = parse_utc_timestamp(raw.get("collected_at_utc"), "collected_at_utc")
    game_start = parse_utc_timestamp(raw.get("game_start_utc"), "game_start_utc")
    finalized = parse_utc_timestamp(
        raw.get("game_finalized_at_utc"), "game_finalized_at_utc"
    )
    if finalized < game_start:
        raise PitcherGameEventError("game_finalized_at_utc cannot precede game_start_utc")
    if collected < finalized:
        raise PitcherGameEventError("collected_at_utc cannot precede game_finalized_at_utc")

    official_text = _required_text(raw, "official_game_date")
    try:
        official_date = date.fromisoformat(official_text)
    except ValueError as exc:
        raise PitcherGameEventError("official_game_date must be YYYY-MM-DD") from exc
    if abs((official_date - game_start.date()).days) > 1:
        raise PitcherGameEventError(
            "official_game_date must be compatible with the UTC game start date"
        )

    game_pk = _required_int(raw, "game_pk", positive=True)
    pitcher_id = _required_int(raw, "pitcher_id", positive=True)
    pitcher_name = _required_text(raw, "pitcher_name")
    team_id = _required_int(raw, "team_id", positive=True)
    opponent_team_id = _required_int(raw, "opponent_team_id", positive=True)
    if team_id == opponent_team_id:
        raise PitcherGameEventError("team_id and opponent_team_id must differ")

    home_away = raw.get("home_away")
    if home_away not in {"home", "away"}:
        raise PitcherGameEventError("home_away must be 'home' or 'away'")
    appearance_sequence = _required_int(raw, "appearance_sequence", positive=True)
    starter_flag = raw.get("starter_flag")
    if not isinstance(starter_flag, bool):
        raise PitcherGameEventError("starter_flag must be an explicit boolean")

    record_status = raw.get("record_status")
    if record_status not in ALLOWED_RECORD_STATUSES:
        raise PitcherGameEventError(f"unsupported record_status: {record_status}")
    if record_status not in NORMALIZABLE_RECORD_STATUSES:
        raise PitcherGameEventError(
            f"{record_status} is diagnostic state, not a normalized pitcher event"
        )

    innings_outs = _required_int(raw, "innings_outs")
    innings_display = _required_text(raw, "innings_pitched_display")
    if innings_display_to_outs(innings_display) != innings_outs:
        raise PitcherGameEventError("innings display and innings_outs disagree")

    batters_faced = _required_int(raw, "batters_faced")
    strikeouts = _required_int(raw, "strikeouts")
    walks = _required_int(raw, "walks")
    intentional_walks = _optional_int(raw, "intentional_walks")
    hit_by_pitch = _required_int(raw, "hit_by_pitch")
    home_runs_allowed = _required_int(raw, "home_runs_allowed")
    hits_allowed = _required_int(raw, "hits_allowed")
    earned_runs = _required_int(raw, "earned_runs")
    runs_allowed = _required_int(raw, "runs_allowed")
    pitches_thrown = _optional_int(raw, "pitches_thrown")
    strikes = _optional_int(raw, "strikes")

    if earned_runs > runs_allowed:
        raise PitcherGameEventError("earned_runs cannot exceed runs_allowed")
    if strikes is not None and pitches_thrown is None:
        raise PitcherGameEventError("strikes require pitches_thrown")
    if pitches_thrown is not None and strikes is None:
        raise PitcherGameEventError("pitches_thrown require strikes")
    if (
        strikes is not None
        and pitches_thrown is not None
        and strikes > pitches_thrown
    ):
        raise PitcherGameEventError("strikes cannot exceed pitches_thrown")

    diagnostic_only = raw.get("diagnostic_only", True)
    production_ready = raw.get("production_ready", False)
    if diagnostic_only is not True or production_ready is not False:
        raise PitcherGameEventError(
            "P202G-B records must remain diagnostic_only=true and production_ready=false"
        )

    fingerprint_fields = {
        "contract_version": contract_version,
        "source_provider": source_provider,
        "source_endpoint_or_feed_id": source_feed,
        "source_record_id": source_record_id,
        "collected_at_utc": _format_utc(collected),
        "game_pk": game_pk,
        "game_start_utc": _format_utc(game_start),
        "game_finalized_at_utc": _format_utc(finalized),
        "official_game_date": official_text,
        "pitcher_id": pitcher_id,
        "pitcher_name": pitcher_name,
        "team_id": team_id,
        "opponent_team_id": opponent_team_id,
        "home_away": home_away,
        "appearance_sequence": appearance_sequence,
        "starter_flag": starter_flag,
        "record_status": record_status,
        "innings_outs": innings_outs,
        "innings_pitched_display": innings_display,
        "batters_faced": batters_faced,
        "strikeouts": strikeouts,
        "walks": walks,
        "intentional_walks": intentional_walks,
        "hit_by_pitch": hit_by_pitch,
        "home_runs_allowed": home_runs_allowed,
        "hits_allowed": hits_allowed,
        "earned_runs": earned_runs,
        "runs_allowed": runs_allowed,
        "pitches_thrown": pitches_thrown,
        "strikes": strikes,
        "parser_version": parser_version,
        "diagnostic_only": True,
        "production_ready": False,
    }
    fingerprint = _canonical_fingerprint(fingerprint_fields)
    supplied_fingerprint = raw.get("payload_fingerprint")
    if supplied_fingerprint is not None and supplied_fingerprint != fingerprint:
        raise PitcherGameEventError("payload_fingerprint does not match normalized content")

    return PitcherGameEvent(
        payload_fingerprint=fingerprint,
        **fingerprint_fields,
    )


def _adapter_diagnostic(
    diagnostics: list[AdapterDiagnostic],
    code: str,
    message: str,
    *,
    game_pk: int | None = None,
    pitcher_id: int | None = None,
) -> None:
    diagnostics.append(
        AdapterDiagnostic(
            code=code,
            message=message,
            game_pk=game_pk,
            pitcher_id=pitcher_id,
        )
    )


def _game_status_is_final(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {
        "final",
        "completed",
        "game over",
    }


def adapt_finalized_boxscore_payload(
    payload: Mapping[str, Any],
    *,
    collected_at_utc: str,
    source_provider: str,
    source_endpoint_or_feed_id: str,
    parser_version: str,
) -> AdapterResult:
    """Decode StatsAPI-shaped finalized boxscores without network access."""

    diagnostics: list[AdapterDiagnostic] = []
    events: list[PitcherGameEvent] = []
    rejected = 0

    if not isinstance(payload, Mapping):
        _adapter_diagnostic(diagnostics, "malformed_payload", "payload must be an object")
        return AdapterResult((), tuple(diagnostics), 0, 1)

    try:
        reject_proxy_or_outcome_leakage(payload)
    except PitcherGameEventError as exc:
        _adapter_diagnostic(diagnostics, "proxy_or_leakage_rejected", str(exc))
        return AdapterResult((), tuple(diagnostics), 0, 1)

    if payload.get("sourceUnavailable") is True:
        _adapter_diagnostic(
            diagnostics,
            "source_unavailable",
            "caller marked the finalized-boxscore source unavailable",
        )
        return AdapterResult((), tuple(diagnostics), 0, 1)

    games = payload.get("games")
    if not isinstance(games, list):
        code = (
            "team_aggregate_without_pitcher_games"
            if "teams" in payload or "teamAggregates" in payload
            else "malformed_payload"
        )
        _adapter_diagnostic(
            diagnostics,
            code,
            "payload must contain a games list of per-pitcher boxscores",
        )
        return AdapterResult((), tuple(diagnostics), 0, 1)

    for game in games:
        if not isinstance(game, Mapping):
            rejected += 1
            _adapter_diagnostic(diagnostics, "malformed_game", "game must be an object")
            continue

        raw_game_pk = game.get("gamePk")
        game_pk = raw_game_pk if isinstance(raw_game_pk, int) else None
        if not _game_status_is_final(game.get("gameStatus")):
            rejected += 1
            _adapter_diagnostic(
                diagnostics,
                "game_not_final",
                f"game status is not finalized: {game.get('gameStatus')!r}",
                game_pk=game_pk,
            )
            continue

        record_status = game.get("recordStatus", "final")
        if record_status not in NORMALIZABLE_RECORD_STATUSES:
            rejected += 1
            _adapter_diagnostic(
                diagnostics,
                "invalid_record_status",
                f"recordStatus is not final/corrected/superseded: {record_status!r}",
                game_pk=game_pk,
            )
            continue

        teams = game.get("teams")
        if not isinstance(teams, Mapping):
            rejected += 1
            _adapter_diagnostic(
                diagnostics,
                "missing_pitcher_lines",
                "final game has no home/away pitcher structures",
                game_pk=game_pk,
            )
            continue

        # Contract v1 stores one row per (game_pk, pitcher_id). A pitcher listed
        # on both sides of one game is ambiguous; fail the whole game closed
        # before any side emits a row.
        side_pitcher_ids: dict[str, list[int]] = {}
        for scan_side in ("home", "away"):
            scan_block = teams.get(scan_side)
            scan_pitchers = (
                scan_block.get("pitchers") if isinstance(scan_block, Mapping) else None
            )
            if isinstance(scan_pitchers, list) and all(
                isinstance(entry, int) and not isinstance(entry, bool)
                for entry in scan_pitchers
            ):
                side_pitcher_ids[scan_side] = scan_pitchers
        both_side_pitcher_ids = set(side_pitcher_ids.get("home", ())) & set(
            side_pitcher_ids.get("away", ())
        )
        if both_side_pitcher_ids:
            rejected += len(both_side_pitcher_ids)
            _adapter_diagnostic(
                diagnostics,
                "ambiguous_pitcher_both_sides",
                "same pitcher_id appears on both sides; contract v1 is one row "
                "per pitcher-game",
                game_pk=game_pk,
            )
            continue

        for side, opponent_side in (("home", "away"), ("away", "home")):
            team_block = teams.get(side)
            opponent_block = teams.get(opponent_side)
            if not isinstance(team_block, Mapping) or not isinstance(
                opponent_block, Mapping
            ):
                rejected += 1
                _adapter_diagnostic(
                    diagnostics,
                    "missing_team_side",
                    f"missing {side}/{opponent_side} team block",
                    game_pk=game_pk,
                )
                continue

            pitchers = team_block.get("pitchers")
            players = team_block.get("players")
            if not isinstance(pitchers, list) or not isinstance(players, Mapping):
                rejected += 1
                _adapter_diagnostic(
                    diagnostics,
                    "team_aggregate_without_pitcher_games",
                    f"{side} side lacks per-pitcher list/player lines",
                    game_pk=game_pk,
                )
                continue

            if not pitchers:
                rejected += 1
                _adapter_diagnostic(
                    diagnostics,
                    "empty_pitcher_list",
                    f"{side} side has no pitcher appearances",
                    game_pk=game_pk,
                )
                continue

            if any(
                isinstance(pitcher, bool) or not isinstance(pitcher, int)
                for pitcher in pitchers
            ):
                rejected += 1
                _adapter_diagnostic(
                    diagnostics,
                    "malformed_pitcher_list",
                    "pitcher list entries must be integer identifiers",
                    game_pk=game_pk,
                )
                continue

            seen_pitcher_ids: set[int] = set()
            duplicate_pitcher_ids: set[int] = set()
            for pitcher in pitchers:
                if pitcher in seen_pitcher_ids:
                    duplicate_pitcher_ids.add(pitcher)
                seen_pitcher_ids.add(pitcher)
            if duplicate_pitcher_ids:
                rejected += len(duplicate_pitcher_ids)
                _adapter_diagnostic(
                    diagnostics,
                    "ambiguous_duplicate_pitcher",
                    "aggregate player blocks cannot represent repeated appearances",
                    game_pk=game_pk,
                )
                continue

            team_identity = team_block.get("team")
            opponent_identity = opponent_block.get("team")
            team_id = team_identity.get("id") if isinstance(team_identity, Mapping) else None
            opponent_team_id = (
                opponent_identity.get("id")
                if isinstance(opponent_identity, Mapping)
                else None
            )

            for appearance_sequence, raw_pitcher_id in enumerate(pitchers, start=1):
                pitcher_id = raw_pitcher_id if isinstance(raw_pitcher_id, int) else None
                player = players.get(f"ID{raw_pitcher_id}")
                if not isinstance(player, Mapping):
                    rejected += 1
                    _adapter_diagnostic(
                        diagnostics,
                        "missing_pitcher_line",
                        f"no player block for pitcher list entry {raw_pitcher_id!r}",
                        game_pk=game_pk,
                        pitcher_id=pitcher_id,
                    )
                    continue

                person = player.get("person")
                stats = player.get("stats")
                pitching = stats.get("pitching") if isinstance(stats, Mapping) else None
                if not isinstance(person, Mapping) or not isinstance(pitching, Mapping):
                    rejected += 1
                    _adapter_diagnostic(
                        diagnostics,
                        "incomplete_pitcher_line",
                        "pitcher line lacks person or stats.pitching data",
                        game_pk=game_pk,
                        pitcher_id=pitcher_id,
                    )
                    continue

                innings_display = pitching.get("inningsPitched")
                try:
                    innings_outs = innings_display_to_outs(innings_display)
                except PitcherGameEventError as exc:
                    rejected += 1
                    _adapter_diagnostic(
                        diagnostics,
                        "invalid_innings_notation",
                        str(exc),
                        game_pk=game_pk,
                        pitcher_id=pitcher_id,
                    )
                    continue

                event_raw = {
                    "contract_version": CONTRACT_VERSION,
                    "source_provider": source_provider,
                    "source_endpoint_or_feed_id": source_endpoint_or_feed_id,
                    # Stable across pitcher-list reorder: identity is the source
                    # game record plus pitcher, never the mutable list position.
                    "source_record_id": f"{raw_game_pk}:pitcher:{raw_pitcher_id}",
                    "collected_at_utc": collected_at_utc,
                    "game_pk": raw_game_pk,
                    "game_start_utc": game.get("gameDate"),
                    "game_finalized_at_utc": game.get("gameFinalizedAtUtc"),
                    "official_game_date": game.get("officialDate"),
                    "pitcher_id": person.get("id"),
                    "pitcher_name": person.get("fullName"),
                    "team_id": team_id,
                    "opponent_team_id": opponent_team_id,
                    "home_away": side,
                    "appearance_sequence": appearance_sequence,
                    "starter_flag": player.get("starterFlag"),
                    "record_status": record_status,
                    "innings_outs": innings_outs,
                    "innings_pitched_display": innings_display,
                    "batters_faced": pitching.get("battersFaced"),
                    "strikeouts": pitching.get("strikeOuts"),
                    "walks": pitching.get("baseOnBalls"),
                    "intentional_walks": pitching.get("intentionalWalks"),
                    "hit_by_pitch": pitching.get("hitBatsmen"),
                    "home_runs_allowed": pitching.get("homeRuns"),
                    "hits_allowed": pitching.get("hits"),
                    "earned_runs": pitching.get("earnedRuns"),
                    "runs_allowed": pitching.get("runs"),
                    "pitches_thrown": pitching.get("numberOfPitches"),
                    "strikes": pitching.get("strikes"),
                    "parser_version": parser_version,
                    "diagnostic_only": True,
                    "production_ready": False,
                }
                try:
                    event = normalize_pitcher_game_event(event_raw)
                except PitcherGameEventError as exc:
                    rejected += 1
                    _adapter_diagnostic(
                        diagnostics,
                        "malformed_pitcher_event",
                        str(exc),
                        game_pk=game_pk,
                        pitcher_id=pitcher_id,
                    )
                    continue
                events.append(event)

    return AdapterResult(
        events=tuple(events),
        diagnostics=tuple(diagnostics),
        accepted_records=len(events),
        rejected_records=rejected,
    )


class PitcherGameEventStore:
    """Append-only JSONL store with exact duplicate suppression."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> tuple[PitcherGameEvent, ...]:
        if not self.path.exists():
            return ()
        records: list[PitcherGameEvent] = []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        decoded = json.loads(line)
                        if set(decoded) != set(EVENT_FIELDS):
                            raise PitcherGameEventError(
                                "stored record fields do not match the contract"
                            )
                        records.append(normalize_pitcher_game_event(decoded))
                    except (json.JSONDecodeError, PitcherGameEventError) as exc:
                        raise PitcherEventStoreError(
                            f"invalid JSONL record at line {line_number}: {exc}"
                        ) from exc
        except OSError as exc:
            raise PitcherEventStoreError(f"cannot read {self.path}: {exc}") from exc
        return tuple(records)

    def append(self, records: Sequence[PitcherGameEvent]) -> AppendResult:
        existing = self.load()
        known_keys = {record.dedup_key for record in existing}
        to_append: list[PitcherGameEvent] = []
        duplicates = 0
        for record in records:
            if not isinstance(record, PitcherGameEvent):
                raise PitcherEventStoreError("append accepts PitcherGameEvent records only")
            if record.dedup_key in known_keys:
                duplicates += 1
                continue
            known_keys.add(record.dedup_key)
            to_append.append(record)

        if to_append:
            if not self.path.parent.exists():
                raise PitcherEventStoreError(
                    f"parent directory does not exist: {self.path.parent}"
                )
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    for record in to_append:
                        handle.write(
                            json.dumps(
                                record.to_dict(),
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=True,
                            )
                            + "\n"
                        )
            except OSError as exc:
                raise PitcherEventStoreError(f"cannot append to {self.path}: {exc}") from exc

        return AppendResult(
            appended=len(to_append),
            duplicates_skipped=duplicates,
            total_records=len(existing) + len(to_append),
        )


def _coerce_event(record: PitcherGameEvent | Mapping[str, Any]) -> PitcherGameEvent:
    if isinstance(record, PitcherGameEvent):
        return record
    return normalize_pitcher_game_event(record)


def select_prior_pitcher_events(
    records: Iterable[PitcherGameEvent | Mapping[str, Any]],
    *,
    pitcher_id: int,
    target_information_cutoff_utc: str,
    target_game_pk: int | None = None,
) -> PriorSelectionResult:
    """Select the latest known non-superseded revision before a target cutoff."""

    if isinstance(pitcher_id, bool) or not isinstance(pitcher_id, int) or pitcher_id <= 0:
        raise PitcherGameEventError("pitcher_id must be a positive integer")
    cutoff = parse_utc_timestamp(
        target_information_cutoff_utc, "target_information_cutoff_utc"
    )
    cutoff_text = _format_utc(cutoff)

    try:
        normalized = tuple(_coerce_event(record) for record in records)
    except PitcherGameEventError as exc:
        return PriorSelectionResult(
            status="invalid_record",
            events=(),
            diagnostics=(f"selection failed closed: {exc}",),
            information_cutoff_utc=cutoff_text,
            max_included_game_start_utc=None,
        )

    eligible: list[PitcherGameEvent] = []
    for event in normalized:
        if event.pitcher_id != pitcher_id:
            continue
        if target_game_pk is not None and event.game_pk == target_game_pk:
            continue
        game_start = parse_utc_timestamp(event.game_start_utc, "game_start_utc")
        finalized = parse_utc_timestamp(
            event.game_finalized_at_utc, "game_finalized_at_utc"
        )
        collected = parse_utc_timestamp(event.collected_at_utc, "collected_at_utc")
        if game_start >= cutoff or finalized > cutoff or collected > cutoff:
            continue
        eligible.append(event)

    groups: dict[tuple[int, int], list[PitcherGameEvent]] = {}
    for event in eligible:
        groups.setdefault(event.logical_event_key, []).append(event)

    # Cross-source lineage takes precedence over within-lineage revision
    # resolution. A logical pitcher-game with more than one eligible source
    # lineage fails closed: different providers or feed IDs are not automatic
    # revisions of one another, so there is no latest-wins, no provider
    # precedence, no voting/consensus, no averaging, and no silent cross-source
    # dedup -- even identical content from two lineages stays ambiguous. Only
    # rows already known by the cutoff are grouped here, so a future cross-source
    # row cannot create historical ambiguity.
    for logical_key in sorted(groups):
        lineages = sorted(
            {revision.source_lineage_key for revision in groups[logical_key]}
        )
        if len(lineages) > 1:
            game_pk, pitcher = logical_key
            return PriorSelectionResult(
                status="ambiguous_cross_source_lineage",
                events=(),
                diagnostics=(
                    "selection failed closed: multiple source lineages "
                    f"{lineages} for pitcher-game (game_pk={game_pk}, "
                    f"pitcher_id={pitcher}); different providers/feeds are not "
                    "automatic revisions of one another",
                ),
                information_cutoff_utc=cutoff_text,
                max_included_game_start_utc=None,
            )

    selected: list[PitcherGameEvent] = []
    for logical_key in sorted(groups):
        revisions = groups[logical_key]
        latest_collected = max(
            parse_utc_timestamp(revision.collected_at_utc, "collected_at_utc")
            for revision in revisions
        )
        latest = [
            revision
            for revision in revisions
            if parse_utc_timestamp(revision.collected_at_utc, "collected_at_utc")
            == latest_collected
        ]
        distinct_latest = {
            revision.payload_fingerprint: revision for revision in latest
        }
        if len(distinct_latest) > 1:
            return PriorSelectionResult(
                status="ambiguous_revision",
                events=(),
                diagnostics=(
                    "selection failed closed: multiple differing revisions share "
                    f"the latest collected_at_utc for pitcher-game {logical_key}",
                ),
                information_cutoff_utc=cutoff_text,
                max_included_game_start_utc=None,
            )
        revision = next(iter(distinct_latest.values()))
        if revision.record_status == "superseded":
            continue
        selected.append(revision)

    selected.sort(
        key=lambda event: (
            parse_utc_timestamp(event.game_start_utc, "game_start_utc"),
            event.game_pk,
            event.appearance_sequence,
        )
    )
    max_start = selected[-1].game_start_utc if selected else None
    return PriorSelectionResult(
        status="ok" if selected else "no_records",
        events=tuple(selected),
        diagnostics=(),
        information_cutoff_utc=cutoff_text,
        max_included_game_start_utc=max_start,
    )
