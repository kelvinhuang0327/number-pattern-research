"""
Authoritative WBC schedule / roster / starter verification gate.

This module enforces a simple rule:
  no verified schedule + no verified participants + no prediction.

The goal is not to guess better from seed data. The goal is to hard-stop when
the local authoritative snapshot is incomplete, stale, or disagrees with the
match object being analysed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable

from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import BatterSnapshot, Matchup, PitcherSnapshot


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _list_names(players: Iterable[dict[str, Any]] | None) -> list[str]:
    names: list[str] = []
    for player in players or []:
        if isinstance(player, dict) and player.get("name"):
            names.append(str(player["name"]))
    return names


def _lineup_names(lineup: Iterable[Any] | None) -> list[str]:
    names: list[str] = []
    for player in lineup or []:
        name = getattr(player, "name", None)
        if name:
            names.append(str(name))
    return names


def _compare_name_lists(expected: list[str], actual: list[str]) -> bool:
    return [_normalize_name(n) for n in expected] == [_normalize_name(n) for n in actual]


def _freshness_window_hours(game_time_utc: str | None, verification: dict[str, Any]) -> float:
    explicit = verification.get("max_age_hours")
    if explicit is not None:
        return float(explicit)

    now = _coerce_now()
    first_pitch = _parse_dt(game_time_utc)
    if first_pitch is None:
        return 24.0

    delta_hours = abs((first_pitch - now).total_seconds()) / 3600.0
    if delta_hours <= 6:
        return 2.0
    if delta_hours <= 24:
        return 6.0
    return 24.0


@dataclass
class VerificationIssue:
    code: str
    message: str
    severity: str = "ERROR"


@dataclass
class VerificationResult:
    requested_game_id: str
    canonical_game_id: str | None = None
    status: str = "REJECTED"
    issues: list[VerificationIssue] = field(default_factory=list)
    snapshot_game: dict[str, Any] | None = None
    used_fallback_lineup: bool = False

    @property
    def blocking(self) -> bool:
        return any(issue.severity == "ERROR" for issue in self.issues)

    def ensure_verified(self) -> VerificationResult:
        if self.blocking:
            raise WBCDataVerificationError(self)
        return self


class WBCDataVerificationError(RuntimeError):
    def __init__(self, result: VerificationResult):
        self.result = result
        summary = "; ".join(issue.message for issue in result.issues) or "unknown verification failure"
        super().__init__(f"WBC data verification failed for {result.requested_game_id}: {summary}")


class WBCAuthoritativeSnapshot:
    def __init__(self, snapshot_path: str):
        self.snapshot_path = Path(snapshot_path)
        self.payload = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.snapshot_path.exists():
            return {"games": []}
        with self.snapshot_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def find_game(self, game_id: str) -> dict[str, Any] | None:
        target = game_id.upper()
        for game in self.payload.get("games", []):
            keys = {
                str(game.get("canonical_game_id", "")).upper(),
                str(game.get("game_id", "")).upper(),
            }
            keys.update(str(alias).upper() for alias in game.get("aliases", []))
            if target in keys:
                return game
        return None

    def find_game_by_matchup(  # NOSONAR
        self,
        *,
        home: str | None,
        away: str | None,
        game_time: str | None,
    ) -> dict[str, Any] | None:
        expected_time = _parse_dt(game_time)
        for game in self.payload.get("games", []):
            if home and str(game.get("home", "")).upper() != home.upper():
                continue
            if away and str(game.get("away", "")).upper() != away.upper():
                continue
            if expected_time is not None:
                actual_time = _parse_dt(game.get("game_time_utc") or game.get("game_time_local"))
                if actual_time is None:
                    continue
                if abs((actual_time - expected_time).total_seconds()) > 60:
                    continue
            return game
        return None

    def to_schedule_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for game in self.payload.get("games", []):
            verification = game.get("verification", {})
            rows.append(
                {
                    "game_id": game.get("canonical_game_id") or game.get("game_id"),
                    "aliases": ",".join(game.get("aliases", [])),
                    "tournament": game.get("tournament", "WBC2026"),
                    "round_name": game.get("round_name", "Pool"),
                    "game_time_utc": game.get("game_time_utc", ""),
                    "game_time_local": game.get("game_time_local", ""),
                    "venue": game.get("venue", ""),
                    "home": game.get("home", ""),
                    "away": game.get("away", ""),
                    "neutral_site": bool(game.get("neutral_site", True)),
                    "weather": game.get("weather", "dome"),
                    "umpire_id": game.get("umpire_id", "generic_avg"),
                    "elevation_m": float(game.get("elevation_m", 0.0)),
                    "temp_f": float(game.get("temp_f", 72.0)),
                    "humidity_pct": float(game.get("humidity_pct", 0.50)),
                    "wind_speed_mph": float(game.get("wind_speed_mph", 0.0)),
                    "wind_direction": game.get("wind_direction", "none"),
                    "is_dome": bool(game.get("is_dome", False)),
                    "schedule_verified": bool(verification.get("schedule_verified", False)),
                    "rosters_verified": bool(verification.get("rosters_verified", False)),
                    "starters_verified": bool(verification.get("starters_verified", False)),
                    "lineups_verified": bool(verification.get("lineups_verified", False)),
                    "last_verified_at": verification.get("last_verified_at", ""),
                }
            )
        return rows


def _build_pitcher(record: dict[str, Any] | None, fallback_team: str) -> PitcherSnapshot | None:
    if not record or not record.get("name"):
        return None
    era = float(record.get("era", 3.80))
    return PitcherSnapshot(
        name=str(record["name"]),
        team=str(record.get("team", fallback_team)),
        era=era,
        fip=float(record.get("fip", era + 0.10)),
        whip=float(record.get("whip", 1.25)),
        k_per_9=float(record.get("k_per_9", 8.5)),
        bb_per_9=float(record.get("bb_per_9", 3.0)),
        stuff_plus=float(record.get("stuff_plus", 100.0)),
        ip_last_30=float(record.get("ip_last_30", 20.0)),
        era_last_3=float(record.get("era_last_3", era)),
        pitch_count_last_3d=int(record.get("pitch_count_last_3d", 0)),
        fastball_velo=float(record.get("fastball_velo", 93.0)),
        high_leverage_era=float(record.get("high_leverage_era", era)),
        role=str(record.get("role", "SP")),
        pitch_mix=dict(record.get("pitch_mix", {}) or {}),
        recent_fastball_velos=[
            float(value) for value in record.get("recent_fastball_velos", []) or []
        ],
        career_fastball_velo=float(record.get("career_fastball_velo", record.get("fastball_velo", 93.0))),
        woba_vs_left=float(record.get("woba_vs_left", 0.320)),
        woba_vs_right=float(record.get("woba_vs_right", 0.320)),
        innings_last_14d=float(record.get("innings_last_14d", 0.0)),
        season_avg_innings_per_14d=float(record.get("season_avg_innings_per_14d", 0.0)),
        recent_spin_rate=float(record.get("recent_spin_rate", 0.0)),
        career_spin_rate_mean=float(record.get("career_spin_rate_mean", 0.0)),
        career_spin_rate_std=float(record.get("career_spin_rate_std", 0.0)),
    )


def _build_batter(record: dict[str, Any], fallback_team: str) -> BatterSnapshot:
    avg = float(record.get("avg", 0.250))
    obp = float(record.get("obp", avg + 0.070))
    slg = float(record.get("slg", avg + 0.150))
    woba = float(record.get("woba", 0.320))
    return BatterSnapshot(
        name=str(record["name"]),
        team=str(record.get("team", fallback_team)),
        avg=avg,
        obp=obp,
        slg=slg,
        woba=woba,
        ops_plus=float(record.get("ops_plus", 100.0)),
        clutch_woba=float(record.get("clutch_woba", woba)),
        vs_left_avg=float(record.get("vs_left_avg", avg)),
        vs_right_avg=float(record.get("vs_right_avg", avg)),
        barrel_pct=float(record.get("barrel_pct", 0.0)),
    )


def _resolved_lineup(snapshot_game: dict[str, Any], side: str) -> tuple[list[dict[str, Any]], bool]:
    official = snapshot_game.get(f"{side}_lineup", [])
    if len(official) == 9:
        return official, False
    previous = snapshot_game.get(f"{side}_previous_lineup", [])
    if len(previous) == 9:
        return previous, True
    return official or previous or [], False


def hydrate_matchup_from_snapshot(matchup: Matchup, snapshot_game: dict[str, Any]) -> Matchup:
    matchup.game_id = str(snapshot_game.get("canonical_game_id") or matchup.game_id)
    matchup.tournament = str(snapshot_game.get("tournament", matchup.tournament))
    matchup.game_time_utc = str(snapshot_game.get("game_time_utc", matchup.game_time_utc))
    matchup.venue = str(snapshot_game.get("venue", matchup.venue))
    matchup.round_name = str(snapshot_game.get("round_name", matchup.round_name))
    matchup.weather = str(snapshot_game.get("weather", matchup.weather))
    matchup.umpire_id = str(snapshot_game.get("umpire_id", matchup.umpire_id))
    matchup.elevation_m = float(snapshot_game.get("elevation_m", matchup.elevation_m))
    matchup.temp_f = float(snapshot_game.get("temp_f", matchup.temp_f))
    matchup.humidity_pct = float(snapshot_game.get("humidity_pct", matchup.humidity_pct))
    matchup.wind_speed_mph = float(snapshot_game.get("wind_speed_mph", matchup.wind_speed_mph))
    matchup.wind_direction = str(snapshot_game.get("wind_direction", matchup.wind_direction))
    matchup.is_dome = bool(snapshot_game.get("is_dome", matchup.is_dome))
    matchup.neutral_site = bool(snapshot_game.get("neutral_site", matchup.neutral_site))
    matchup.home_sp = _build_pitcher(snapshot_game.get("home_sp"), matchup.home.team)
    matchup.away_sp = _build_pitcher(snapshot_game.get("away_sp"), matchup.away.team)
    home_lineup, _ = _resolved_lineup(snapshot_game, "home")
    away_lineup, _ = _resolved_lineup(snapshot_game, "away")
    matchup.home_lineup = [
        _build_batter(player, matchup.home.team)
        for player in home_lineup
        if player.get("name")
    ]
    matchup.away_lineup = [
        _build_batter(player, matchup.away.team)
        for player in away_lineup
        if player.get("name")
    ]
    return matchup


def verify_game_artifact(  # NOSONAR  # noqa: C901
    *,
    game_id: str,
    expected_home: str | None,
    expected_away: str | None,
    expected_game_time: str | None,
    expected_home_sp: str | None,
    expected_away_sp: str | None,
    expected_home_lineup: list[str] | None,
    expected_away_lineup: list[str] | None,
    data_source: str = "",
    snapshot_path: str | None = None,
    now: datetime | None = None,
) -> VerificationResult:
    config = AppConfig()
    repo = WBCAuthoritativeSnapshot(snapshot_path or config.sources.wbc_authoritative_snapshot_json)
    result = VerificationResult(requested_game_id=game_id)
    snapshot_game = repo.find_game(game_id)
    if snapshot_game is None and (expected_home or expected_away or expected_game_time):
        snapshot_game = repo.find_game_by_matchup(
            home=expected_home,
            away=expected_away,
            game_time=expected_game_time,
        )
    if snapshot_game is None:
        result.issues.append(
            VerificationIssue(
                code="game_not_in_authoritative_snapshot",
                message=(
                    f"Game {game_id} is not present in the authoritative WBC snapshot. "
                    "Prediction is blocked until schedule / roster / starters are verified."
                ),
            )
        )
        return result

    result.snapshot_game = snapshot_game
    result.canonical_game_id = str(snapshot_game.get("canonical_game_id") or game_id)
    verification = snapshot_game.get("verification", {})
    home_resolved_lineup, home_used_fallback = _resolved_lineup(snapshot_game, "home")
    away_resolved_lineup, away_used_fallback = _resolved_lineup(snapshot_game, "away")
    result.used_fallback_lineup = home_used_fallback or away_used_fallback

    required_flags = {
        "schedule_verified": "Schedule has not been officially verified.",
        "rosters_verified": "Roster snapshot has not been officially verified.",
        "starters_verified": "Starting pitchers have not been officially verified.",
    }
    for key, message in required_flags.items():
        if not verification.get(key, False):
            result.issues.append(VerificationIssue(code=key, message=message))
    if not verification.get("lineups_verified", False):
        if config.sources.allow_previous_lineup_fallback and result.used_fallback_lineup:
            result.issues.append(
                VerificationIssue(
                    code="lineups_fallback_previous_game",
                    message="Official starting lineup missing; using previous-game lineup fallback.",
                    severity="WARNING",
                )
            )
        else:
            result.issues.append(
                VerificationIssue(
                    code="lineups_verified",
                    message="Starting lineups have not been officially verified.",
                )
            )

    last_verified_at = _parse_dt(verification.get("last_verified_at"))
    if last_verified_at is None:
        result.issues.append(
            VerificationIssue(
                code="missing_last_verified_at",
                message="Authoritative snapshot is missing last_verified_at.",
            )
        )
    else:
        max_age_hours = _freshness_window_hours(snapshot_game.get("game_time_utc"), verification)
        age_hours = (_coerce_now(now) - last_verified_at).total_seconds() / 3600.0
        if age_hours > max_age_hours:
            result.issues.append(
                VerificationIssue(
                    code="stale_authoritative_snapshot",
                    message=(
                        f"Authoritative snapshot is stale ({age_hours:.1f}h old, "
                        f"limit {max_age_hours:.1f}h)."
                    ),
                )
            )

    if expected_home and str(snapshot_game.get("home", "")).upper() != expected_home.upper():
        result.issues.append(
            VerificationIssue(
                code="home_team_mismatch",
                message=f"Snapshot home team {snapshot_game.get('home')} != model home team {expected_home}.",
            )
        )
    if expected_away and str(snapshot_game.get("away", "")).upper() != expected_away.upper():
        result.issues.append(
            VerificationIssue(
                code="away_team_mismatch",
                message=f"Snapshot away team {snapshot_game.get('away')} != model away team {expected_away}.",
            )
        )

    snapshot_game_time = _parse_dt(snapshot_game.get("game_time_utc") or snapshot_game.get("game_time_local"))
    expected_time = _parse_dt(expected_game_time)
    if snapshot_game_time and expected_time:
        diff_seconds = abs((snapshot_game_time - expected_time).total_seconds())
        if diff_seconds > 60:
            result.issues.append(
                VerificationIssue(
                    code="game_time_mismatch",
                    message="Snapshot game time does not match the model game time.",
                )
            )

    home_roster = {_normalize_name(name) for name in snapshot_game.get("home_roster", [])}
    away_roster = {_normalize_name(name) for name in snapshot_game.get("away_roster", [])}

    snapshot_home_sp = str(snapshot_game.get("home_sp", {}).get("name", ""))
    snapshot_away_sp = str(snapshot_game.get("away_sp", {}).get("name", ""))
    if expected_home_sp and _normalize_name(snapshot_home_sp) != _normalize_name(expected_home_sp):
        result.issues.append(
            VerificationIssue(
                code="home_sp_mismatch",
                message=f"Snapshot home SP {snapshot_home_sp} != model home SP {expected_home_sp}.",
            )
        )
    if expected_away_sp and _normalize_name(snapshot_away_sp) != _normalize_name(expected_away_sp):
        result.issues.append(
            VerificationIssue(
                code="away_sp_mismatch",
                message=f"Snapshot away SP {snapshot_away_sp} != model away SP {expected_away_sp}.",
            )
        )

    if expected_home_sp and home_roster and _normalize_name(expected_home_sp) not in home_roster:
        result.issues.append(
            VerificationIssue(
                code="home_sp_not_on_roster",
                message=f"Home SP {expected_home_sp} is not present in the verified home roster.",
            )
        )
    if expected_away_sp and away_roster and _normalize_name(expected_away_sp) not in away_roster:
        result.issues.append(
            VerificationIssue(
                code="away_sp_not_on_roster",
                message=f"Away SP {expected_away_sp} is not present in the verified away roster.",
            )
        )

    snapshot_home_lineup = _list_names(home_resolved_lineup)
    snapshot_away_lineup = _list_names(away_resolved_lineup)
    if expected_home_lineup is not None and not _compare_name_lists(snapshot_home_lineup, expected_home_lineup):
        result.issues.append(
            VerificationIssue(
                code="home_lineup_mismatch",
                message="Home lineup does not match the verified starting lineup.",
            )
        )
    if expected_away_lineup is not None and not _compare_name_lists(snapshot_away_lineup, expected_away_lineup):
        result.issues.append(
            VerificationIssue(
                code="away_lineup_mismatch",
                message="Away lineup does not match the verified starting lineup.",
            )
        )

    for name in expected_home_lineup or []:
        if home_roster and _normalize_name(name) not in home_roster:
            result.issues.append(
                VerificationIssue(
                    code="home_lineup_player_not_on_roster",
                    message=f"Home lineup player {name} is not present in the verified home roster.",
                )
            )
    for name in expected_away_lineup or []:
        if away_roster and _normalize_name(name) not in away_roster:
            result.issues.append(
                VerificationIssue(
                    code="away_lineup_player_not_on_roster",
                    message=f"Away lineup player {name} is not present in the verified away roster.",
                )
            )

    if data_source and any(token in data_source.upper() for token in ("MOCK", "SEED")):
        result.issues.append(
            VerificationIssue(
                code="seed_source_detected",
                message=(
                    "Model input still declares MOCK/SEED source. "
                    "Treat this as unsafe until the authoritative snapshot fully replaces the seed path."
                ),
                severity="WARNING",
            )
        )

    if not result.blocking:
        result.status = "VERIFIED_WITH_FALLBACK" if result.used_fallback_lineup else "VERIFIED"
    else:
        result.status = "REJECTED"
    return result


def verify_matchup(matchup: Matchup, snapshot_path: str | None = None) -> VerificationResult:
    return verify_game_artifact(
        game_id=matchup.game_id,
        expected_home=matchup.home.team,
        expected_away=matchup.away.team,
        expected_game_time=matchup.game_time_utc,
        expected_home_sp=getattr(matchup.home_sp, "name", None),
        expected_away_sp=getattr(matchup.away_sp, "name", None),
        expected_home_lineup=_lineup_names(matchup.home_lineup),
        expected_away_lineup=_lineup_names(matchup.away_lineup),
        snapshot_path=snapshot_path,
    )
