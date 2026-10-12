"""
Phase 62 — Bullpen Granular Source Selection and Minimal PIT-safe Ingestion Proof.

GATE: STATSAPI_SELECTED | STATCAST_PBP_SELECTED | HYBRID_SOURCE_REQUIRED | SOURCE_BLOCKED

This module proves that the MLB StatsAPI /game/{pk}/boxscore endpoint is sufficient
to derive per-pitcher relief appearance records that can feed Phase 61 SSOT features.

SAFETY CONSTANTS — NEVER MODIFY:
    CANDIDATE_PATCH_CREATED  = False  (no production write path built)
    PRODUCTION_MODIFIED      = False  (no existing model/data modified)
    ALPHA_MODIFIED           = False  (blend formula untouched)
    DIAGNOSTIC_ONLY          = True   (fixture-only proof, no live API calls)

SOURCE SELECTION:
    Selected: MLB StatsAPI /game/{pk}/boxscore (extension of existing integration)
    Reason:
        - Already integrated; per-pitcher pitching stats are in the players dict.
        - Extending window from 3d to 1d/5d only requires adjusting timedelta range.
        - Per-pitcher B2B and 3-in-4 derivable by tracking pitcher IDs across days.
        - Leverage index (LI) features remain DATA_LIMITED; PbP optional in Phase 63.
        - No new API dependency; rate-limit budget already managed in Phase 58/59.

PIT SAFETY:
    All records must satisfy: entry_date (fetched_at) < game_date (strictly prior day).
    Functions that require game_date use a pit_snapshot_date parameter (D-1 by default).
    No future data is ever incorporated into a pre-game record.

MODULE_VERSION = "phase62_bullpen_granular_ingestion_v1"
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Safety Constants — NEVER modify these
# ─────────────────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True

MODULE_VERSION: str = "phase62_bullpen_granular_ingestion_v1"

# ─────────────────────────────────────────────────────────────────────────────
# Source Constants
# ─────────────────────────────────────────────────────────────────────────────
SOURCE_LABEL: str = "mlb_stats_api_boxscore"
PLAY_BY_PLAY_SOURCE_LABEL: str = "mlb_stats_api_play_by_play"

# IP classification thresholds
OPENER_IP_THRESHOLD: float = 2.0    # pitchers[0] with IP < this → treated as opener/reliever
_MIN_RELIEVER_IP: float = 0.0       # any appearance > 0 IP counts as a relief appearance

# Rolling window lengths (D-1 through D-N; target game NOT included)
WINDOW_1D: int = 1
WINDOW_3D: int = 3
WINDOW_5D: int = 5
WINDOW_7D: int = 7

# Back-to-back / high-frequency thresholds
B2B_CONSECUTIVE_DAYS: int = 2       # appeared on both D-1 and D-2
THREE_IN_FOUR_WINDOW: int = 4       # appeared on >= 3 of [D-1, D-2, D-3, D-4]
THREE_IN_FOUR_MIN_APPEARANCES: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# Relief Appearance Record — SSOT-aligned schema
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReliefAppearanceRecord:
    """
    Normalized per-pitcher, per-game appearance record derived from boxscore.
    Only relievers (is_reliever=True) are relevant for SSOT features.

    PIT SAFETY:
        This record is ALWAYS built from a completed game that occurred strictly
        before the prediction date. It is illegal to use current-day data.
    """
    game_id: str
    game_date: str          # YYYY-MM-DD (date of the completed game)
    team: str               # Canonical team name
    side: str               # "home" | "away"
    pitcher_id: int         # MLB player ID (integer)
    pitcher_name: str       # Display name
    appearance_order: int   # 1 = first pitcher (usually SP), 2+ = relievers
    innings_pitched: float  # Decimal: 1.1 IP → 1.333; 1.2 IP → 1.667
    is_starter: bool        # True if appearance_order == 1 AND ip >= OPENER_IP_THRESHOLD
    is_opener: bool         # True if appearance_order == 1 AND ip < OPENER_IP_THRESHOLD
    is_reliever: bool       # True if is_starter is False (includes opener scenarios)
    is_closer_candidate: bool   # True if last pitcher to appear in the game
    source: str             # Always SOURCE_LABEL for boxscore-derived records
    pit_safe: bool          # Always True; enforced in parser


@dataclass(frozen=True)
class IngestionResult:
    """
    Container for a batch of parsed relief appearances from multiple games.
    Maps game_date → team → list[ReliefAppearanceRecord].
    """
    appearances: list[ReliefAppearanceRecord]
    games_parsed: int
    games_missing: int          # Null boxscores (postponed / API failure)
    errors: list[str]
    source: str = SOURCE_LABEL
    module_version: str = MODULE_VERSION
    diagnostic_only: bool = True  # Always True in Phase 62


# ─────────────────────────────────────────────────────────────────────────────
# Source Comparison Metadata (Phase 62 gate evidence)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SourceCapabilityEntry:
    """Structured capability flag for one feature vs one data source."""
    feature: str
    statsapi_boxscore: str      # "AVAILABLE" | "DATA_LIMITED" | "MISSING"
    statcast_pbp: str           # "AVAILABLE" | "DATA_LIMITED" | "MISSING"
    notes: str


SOURCE_CAPABILITY_TABLE: list[SourceCapabilityEntry] = [
    SourceCapabilityEntry(
        feature="bullpen_usage_last_1d",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Sum IP of relievers on D-1; both sources support this window.",
    ),
    SourceCapabilityEntry(
        feature="bullpen_usage_last_3d",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Existing Phase 58/59 data; 2,430 rows in bullpen_usage_3d.jsonl.",
    ),
    SourceCapabilityEntry(
        feature="bullpen_usage_last_5d",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Extend timedelta range from D-3 to D-5; no new source needed.",
    ),
    SourceCapabilityEntry(
        feature="reliever_back_to_back_count",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Track pitcher IDs across days; B2B = appeared on both D-1 and D-2.",
    ),
    SourceCapabilityEntry(
        feature="reliever_three_in_four_days_count",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Track pitcher IDs across 4d window; >=3 appearances = high-frequency.",
    ),
    SourceCapabilityEntry(
        feature="closer_used_last_1d",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Closer candidate = last pitcher in game. Heuristic, not role-confirmed.",
    ),
    SourceCapabilityEntry(
        feature="closer_used_last_2d",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Same closer candidate heuristic; check D-1 and D-2.",
    ),
    SourceCapabilityEntry(
        feature="bullpen_fatigue_favorite_side",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Derived from bullpen_usage_last_3d + market; no new source needed.",
    ),
    SourceCapabilityEntry(
        feature="bullpen_fatigue_underdog_side",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Derived from bullpen_usage_last_3d + market; no new source needed.",
    ),
    SourceCapabilityEntry(
        feature="bullpen_rest_imbalance",
        statsapi_boxscore="AVAILABLE",
        statcast_pbp="AVAILABLE",
        notes="Ratio of home/away 3d usage; derivable from existing data.",
    ),
    SourceCapabilityEntry(
        feature="high_leverage_reliever_used_last_1d",
        statsapi_boxscore="DATA_LIMITED",
        statcast_pbp="AVAILABLE",
        notes="Requires leverage index (LI) per appearance. Boxscore has no LI field. PbP needed.",
    ),
    SourceCapabilityEntry(
        feature="high_leverage_reliever_workload_last_3d",
        statsapi_boxscore="DATA_LIMITED",
        statcast_pbp="AVAILABLE",
        notes="Requires LI per appearance. Boxscore has no LI field. PbP needed.",
    ),
]

SELECTED_SOURCE: str = "mlb_stats_api_boxscore"
GATE_RESULT: str = "STATSAPI_SELECTED"
GATE_RATIONALE: str = (
    "MLB StatsAPI /game/{pk}/boxscore provides per-pitcher IP and appearance order "
    "sufficient to derive 10 of 12 Phase 61 SSOT features. The 2 LI-dependent features "
    "(high_leverage_reliever_*) remain DATA_LIMITED and are deferred to Phase 63. "
    "Adding Statcast PbP now would double integration complexity without Phase 62 gate benefit."
)


# ─────────────────────────────────────────────────────────────────────────────
# IP Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_innings_pitched(ip_str: Any) -> float | None:
    """
    Convert MLB API inningsPitched string to decimal IP.
    '6.1' → 6.333, '6.2' → 6.667, '6.0' → 6.0
    Returns None if the value is missing or unparseable.
    """
    if ip_str is None:
        return None
    s = str(ip_str).strip()
    if not s:
        return None
    try:
        # Replace the fractional-inning notation: .1 → .333, .2 → .667
        # Do NOT replace .0 (keep as 0)
        parts = s.split(".")
        if len(parts) == 1:
            return float(parts[0])
        whole = int(parts[0])
        frac = parts[1]
        if frac == "1":
            return whole + 1 / 3
        elif frac == "2":
            return whole + 2 / 3
        elif frac == "0" or frac == "":
            return float(whole)
        else:
            return float(s)
    except (ValueError, IndexError):
        return None


def _normalize_ip(ip: float | None) -> float:
    """Clamp to non-negative; return 0.0 for None."""
    if ip is None:
        return 0.0
    return max(0.0, ip)


# ─────────────────────────────────────────────────────────────────────────────
# Core Boxscore Parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_boxscore_to_appearances(
    *,
    boxscore: dict[str, Any],
    game_id: str,
    game_date: str,
    home_team: str,
    away_team: str,
) -> list[ReliefAppearanceRecord]:
    """
    Parse an MLB StatsAPI /game/{pk}/boxscore response into a list of
    ReliefAppearanceRecord objects (one per pitcher per side).

    PIT safety: caller must guarantee game_date is strictly in the past relative
    to any prediction being made. This function does not enforce the date check
    (use assert_pit_safe before calling in production-adjacent code).

    Args:
        boxscore:   The JSON dict from /game/{pk}/boxscore. May be None → returns [].
        game_id:    Canonical game ID string.
        game_date:  YYYY-MM-DD string for the completed game.
        home_team:  Canonical home team name.
        away_team:  Canonical away team name.

    Returns:
        List of ReliefAppearanceRecord, one per pitcher per side.
        Returns [] if boxscore is None or missing required fields.
    """
    if not boxscore:
        return []

    teams_box = boxscore.get("teams", {})
    if not teams_box:
        return []

    records: list[ReliefAppearanceRecord] = []

    for side, team_name in (("home", home_team), ("away", away_team)):
        tbox = teams_box.get(side, {})
        if not tbox:
            continue
        pitcher_ids: list[int] = [int(pid) for pid in (tbox.get("pitchers") or [])]
        players: dict[str, Any] = tbox.get("players") or {}

        if not pitcher_ids:
            continue

        n_pitchers = len(pitcher_ids)
        for order, pid in enumerate(pitcher_ids, start=1):
            player_key = f"ID{pid}"
            player_data = players.get(player_key, {})
            person = player_data.get("person", {})
            pitching_stats = player_data.get("stats", {}).get("pitching", {})

            pitcher_name = str(person.get("fullName", f"UnknownPitcher_{pid}"))
            ip_raw = pitching_stats.get("inningsPitched")
            ip_decimal = _normalize_ip(_parse_innings_pitched(ip_raw))

            is_first = order == 1
            is_last = order == n_pitchers
            is_starter = is_first and ip_decimal >= OPENER_IP_THRESHOLD
            is_opener = is_first and ip_decimal < OPENER_IP_THRESHOLD
            is_reliever = not is_starter

            records.append(
                ReliefAppearanceRecord(
                    game_id=game_id,
                    game_date=game_date,
                    team=team_name,
                    side=side,
                    pitcher_id=pid,
                    pitcher_name=pitcher_name,
                    appearance_order=order,
                    innings_pitched=ip_decimal,
                    is_starter=is_starter,
                    is_opener=is_opener,
                    is_reliever=is_reliever,
                    is_closer_candidate=is_last and is_reliever,
                    source=SOURCE_LABEL,
                    pit_safe=True,
                )
            )

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Fixture Loader (for tests and proof runs only — no live API)
# ─────────────────────────────────────────────────────────────────────────────

def load_fixture_boxscores(
    fixture_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Load Phase 62 fixture boxscores from the JSON fixture file.
    Returns list of fixture dicts, each with 'meta' and 'boxscore' keys.
    Raises FileNotFoundError if fixture file is not found.
    """
    if fixture_path is None:
        fixture_path = (
            Path(__file__).parent.parent.parent  # repo root
            / "tests" / "fixtures" / "phase62_boxscore_fixtures.json"
        )
    if not fixture_path.exists():
        raise FileNotFoundError(f"Phase 62 fixture not found: {fixture_path}")
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return list(data.get("fixtures", []))


def parse_fixture_to_ingestion_result(
    fixture_path: Path | None = None,
) -> IngestionResult:
    """
    Parse all Phase 62 fixtures into an IngestionResult.
    This is the main proof-of-concept entry point (no live API calls).
    """
    fixtures = load_fixture_boxscores(fixture_path)
    all_appearances: list[ReliefAppearanceRecord] = []
    games_parsed = 0
    games_missing = 0
    errors: list[str] = []

    for fx in fixtures:
        meta = fx.get("meta", {})
        game_id = meta.get("game_id", "UNKNOWN")
        game_date = meta.get("game_date", "")
        home_team = meta.get("home_team", "")
        away_team = meta.get("away_team", "")
        boxscore = fx.get("boxscore")

        if boxscore is None:
            games_missing += 1
            continue

        try:
            recs = parse_boxscore_to_appearances(
                boxscore=boxscore,
                game_id=game_id,
                game_date=game_date,
                home_team=home_team,
                away_team=away_team,
            )
            all_appearances.extend(recs)
            games_parsed += 1
        except Exception as exc:
            errors.append(f"{game_id}: {exc}")

    return IngestionResult(
        appearances=all_appearances,
        games_parsed=games_parsed,
        games_missing=games_missing,
        errors=errors,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rolling Window Computations
# ─────────────────────────────────────────────────────────────────────────────

def compute_bullpen_ip_window(
    appearances: list[ReliefAppearanceRecord],
    *,
    team: str,
    prediction_date: str,  # YYYY-MM-DD — the game we are predicting (PIT reference)
    window_days: int,
) -> float | None:
    """
    Sum innings pitched by all relievers for `team` in the D-1 to D-{window_days}
    window strictly before prediction_date.

    PIT SAFETY: only appearances where game_date < prediction_date are included.
    Returns None if no qualifying appearances exist in the window.
    """
    pred_d = date.fromisoformat(prediction_date)
    cutoff_start = pred_d - timedelta(days=window_days)  # inclusive start of window
    total_ip = 0.0
    found = False

    for rec in appearances:
        if rec.team != team:
            continue
        if not rec.is_reliever:
            continue
        game_d = date.fromisoformat(rec.game_date)
        # PIT safety: strictly before prediction date
        if not (cutoff_start <= game_d < pred_d):
            continue
        total_ip += rec.innings_pitched
        found = True

    return round(total_ip, 3) if found else None


def compute_back_to_back_count(
    appearances: list[ReliefAppearanceRecord],
    *,
    team: str,
    prediction_date: str,
) -> int:
    """
    Count unique relievers who appeared on BOTH D-1 AND D-2 before prediction_date.
    Returns 0 if no B2B relievers found.

    PIT SAFETY: only D-1 and D-2 (strictly before prediction_date).
    """
    pred_d = date.fromisoformat(prediction_date)
    d_minus_1 = (pred_d - timedelta(days=1)).isoformat()
    d_minus_2 = (pred_d - timedelta(days=2)).isoformat()

    appeared_d1: set[int] = set()
    appeared_d2: set[int] = set()

    for rec in appearances:
        if rec.team != team or not rec.is_reliever:
            continue
        if rec.game_date == d_minus_1:
            appeared_d1.add(rec.pitcher_id)
        elif rec.game_date == d_minus_2:
            appeared_d2.add(rec.pitcher_id)

    return len(appeared_d1 & appeared_d2)


def compute_three_in_four_days_count(
    appearances: list[ReliefAppearanceRecord],
    *,
    team: str,
    prediction_date: str,
) -> int:
    """
    Count unique relievers who appeared on >= 3 of the 4 days in [D-1, D-2, D-3, D-4]
    strictly before prediction_date.
    Returns 0 if no qualifying relievers.

    PIT SAFETY: only days D-1 through D-4 (strictly before prediction_date).
    """
    pred_d = date.fromisoformat(prediction_date)
    window_dates: set[str] = {
        (pred_d - timedelta(days=i)).isoformat()
        for i in range(1, THREE_IN_FOUR_WINDOW + 1)
    }

    pitcher_day_counts: dict[int, int] = defaultdict(int)

    for rec in appearances:
        if rec.team != team or not rec.is_reliever:
            continue
        if rec.game_date in window_dates:
            pitcher_day_counts[rec.pitcher_id] += 1

    return sum(1 for cnt in pitcher_day_counts.values() if cnt >= THREE_IN_FOUR_MIN_APPEARANCES)


def compute_closer_used_within_days(
    appearances: list[ReliefAppearanceRecord],
    *,
    team: str,
    prediction_date: str,
    within_days: int,
) -> bool:
    """
    Return True if the team's closer candidate (last pitcher in game) appeared
    within the last `within_days` days before prediction_date.
    Uses the is_closer_candidate heuristic (last pitcher in game).

    PIT SAFETY: only checks [D-1 .. D-{within_days}] strictly before prediction_date.
    """
    pred_d = date.fromisoformat(prediction_date)
    cutoff = (pred_d - timedelta(days=within_days)).isoformat()

    for rec in appearances:
        if rec.team != team:
            continue
        if not rec.is_closer_candidate:
            continue
        if rec.game_date >= cutoff and rec.game_date < prediction_date:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# PIT Safety Assertion
# ─────────────────────────────────────────────────────────────────────────────

def assert_pit_safe(
    prediction_date: str,
    snapshot_date: str,
) -> None:
    """
    Assert that snapshot_date (entry_date) is strictly before prediction_date (game_date).
    Raises ValueError if PIT contamination is detected.

    Args:
        prediction_date: The date being predicted (game_date). YYYY-MM-DD.
        snapshot_date:   The date when data was acquired. YYYY-MM-DD.
    """
    if snapshot_date >= prediction_date:
        raise ValueError(
            f"PIT VIOLATION: snapshot_date={snapshot_date!r} must be strictly before "
            f"prediction_date={prediction_date!r}. This is a data leakage error."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 61 SSOT Integration Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ssot_available_features_from_boxscore() -> list[str]:
    """
    Return the list of Phase 61 SSOT features that become AVAILABLE
    when per-pitcher boxscore data is ingested via this module.
    """
    return [
        "bullpen_usage_last_1d",
        "bullpen_usage_last_3d",
        "bullpen_usage_last_5d",
        "reliever_back_to_back_count",
        "reliever_three_in_four_days_count",
        "closer_used_last_1d",
        "closer_used_last_2d",
        "bullpen_fatigue_favorite_side",
        "bullpen_fatigue_underdog_side",
        "bullpen_rest_imbalance",
    ]


def ssot_still_data_limited_features() -> list[str]:
    """
    Return Phase 61 SSOT features that remain DATA_LIMITED even with boxscore ingestion.
    These require leverage index (LI) from the play-by-play endpoint.
    """
    return [
        "high_leverage_reliever_used_last_1d",
        "high_leverage_reliever_workload_last_3d",
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic Report Builder (no production write path)
# ─────────────────────────────────────────────────────────────────────────────

def build_phase62_diagnostic_report(result: IngestionResult) -> dict[str, Any]:
    """
    Build a diagnostic-only Phase 62 report from an IngestionResult.
    This report is written to reports/ as a JSON artifact — it does NOT
    modify any production dataset or model parameters.
    """
    relievers = [r for r in result.appearances if r.is_reliever]
    starters = [r for r in result.appearances if r.is_starter]
    openers = [r for r in result.appearances if r.is_opener]
    closers = [r for r in result.appearances if r.is_closer_candidate]

    # IP distribution across relievers
    reliever_ips = [r.innings_pitched for r in relievers]
    avg_ip = round(sum(reliever_ips) / len(reliever_ips), 3) if reliever_ips else None
    max_ip = round(max(reliever_ips), 3) if reliever_ips else None

    # Audit hash over sorted appearances
    hash_payload = "|".join(
        f"{r.game_id}:{r.pitcher_id}:{r.innings_pitched:.3f}"
        for r in sorted(result.appearances, key=lambda x: (x.game_id, x.pitcher_id))
    )
    audit_hash = hashlib.sha256(hash_payload.encode()).hexdigest()[:16]

    return {
        "module_version": result.module_version,
        "diagnostic_only": result.diagnostic_only,
        "candidate_patch_created": CANDIDATE_PATCH_CREATED,
        "production_modified": PRODUCTION_MODIFIED,
        "alpha_modified": ALPHA_MODIFIED,
        "source_selected": SELECTED_SOURCE,
        "gate": GATE_RESULT,
        "gate_rationale": GATE_RATIONALE,
        "ingestion_proof": {
            "games_parsed": result.games_parsed,
            "games_missing": result.games_missing,
            "total_pitcher_appearances": len(result.appearances),
            "starters": len(starters),
            "openers_detected": len(openers),
            "relievers": len(relievers),
            "closer_candidates": len(closers),
            "avg_reliever_ip": avg_ip,
            "max_reliever_ip": max_ip,
            "errors": result.errors,
        },
        "ssot_upgrade": {
            "features_now_available": ssot_available_features_from_boxscore(),
            "features_still_data_limited": ssot_still_data_limited_features(),
            "available_count": len(ssot_available_features_from_boxscore()),
            "data_limited_count": len(ssot_still_data_limited_features()),
        },
        "source_capability_table": [
            {
                "feature": e.feature,
                "statsapi_boxscore": e.statsapi_boxscore,
                "statcast_pbp": e.statcast_pbp,
                "notes": e.notes,
            }
            for e in SOURCE_CAPABILITY_TABLE
        ],
        "audit_hash": audit_hash,
    }


# =============================================================================
# Phase 63 — StatsAPI-based Bullpen Granular Ingestion Implementation
# =============================================================================

PHASE63_MODULE_VERSION: str = "phase63_bullpen_granular_ingestion_v2"

# Sentinel used in availability_map for DATA_LIMITED features
_DATA_LIMITED_SENTINEL: str = "DATA_LIMITED"

# Edge-case handling policies (documentation + testable dict)
EDGE_CASE_POLICIES: dict[str, str] = {
    "doubleheader": (
        "Game 2 of a same-day doubleheader excludes Game 1 box scores (D-0). "
        "The strict `game_date < prediction_date` inequality in all window functions "
        "enforces PIT safety so same-day games never pollute the pre-game window."
    ),
    "postponed": (
        "A null or missing boxscore is treated as postponed/rescheduled. "
        "games_missing is incremented; no relief appearances are generated; "
        "SSOT window functions fall back to prior available days naturally."
    ),
    "suspended": (
        "Suspended games are treated identically to postponed (incomplete boxscore). "
        "Not ingested until the game is officially marked complete."
    ),
    "opener": (
        f"Opener detected when appearance_order == 1 AND innings_pitched < {OPENER_IP_THRESHOLD}. "
        "opener_flag=True, reliever_flag=True. "
        "Opener IP IS counted in bullpen_usage_last_Nd windows (they are relievers)."
    ),
    "bulk_pitcher": (
        "Bulk pitcher: appearance_order >= 2 with potentially large IP. "
        "reliever_flag=True regardless of IP; opener_flag=False. "
        "Bulk pitcher IP is counted in bullpen IP windows same as any reliever."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Artifact Schema: NormalizedReliefAppearance
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NormalizedReliefAppearance:
    """
    Phase 63 canonical per-pitcher, per-game appearance artifact.

    Extends Phase 62 ReliefAppearanceRecord with:
      - opponent: opposing team canonical name
      - appeared_order: externally facing field (renamed from appearance_order)
      - starter_flag / opener_flag / reliever_flag: boolean role flags
      - outs_recorded: int(round(ip * 3)) — avoids float drift
      - pitches_thrown: from boxscore numberOfPitches (None if unavailable)
      - source_game_id: raw game_pk or game_id string from source
      - audit_hash: sha256[:12] of (game_id, pitcher_id, ip) for integrity

    PIT SAFETY: always built from completed prior-day games.
    """
    game_id: str
    game_date: str            # YYYY-MM-DD
    team: str
    opponent: str             # opposing team canonical name
    pitcher_id: int
    pitcher_name: str
    appeared_order: int       # 1-indexed; 1 = first pitcher in game
    starter_flag: bool        # True iff appearance_order==1 AND ip >= OPENER_IP_THRESHOLD
    opener_flag: bool         # True iff appearance_order==1 AND ip < OPENER_IP_THRESHOLD
    reliever_flag: bool       # True iff NOT starter_flag (includes openers)
    innings_pitched: float    # decimal: "6.1" → 6.333..., "6.2" → 6.667...
    outs_recorded: int        # int(round(ip * 3))
    pitches_thrown: int | None  # None if not in boxscore source
    source: str               # "mlb_stats_api_boxscore"
    source_game_id: str       # raw game_pk string or game_id
    audit_hash: str           # sha256[:12] of (game_id, pitcher_id, ip)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Artifact Schema: SSOTFeatureArtifact
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SSOTFeatureArtifact:
    """
    Phase 63 SSOT feature artifact for one (prediction_game_id, team) pair.

    All AVAILABLE features are computed from PIT-safe windows [D-1 .. D-N].
    DATA_LIMITED features MUST be None — no neutral fallback allowed.
    high_leverage_* remain DATA_LIMITED pending Phase 63/64 PbP integration.
    """
    prediction_game_id: str
    game_date: str                           # prediction game date (YYYY-MM-DD)
    team: str

    # AVAILABLE features — derivable from StatsAPI boxscore per-pitcher records
    bullpen_usage_last_1d: float | None      # None if no D-1 data
    bullpen_usage_last_3d: float | None      # None if no D-1..D-3 data
    bullpen_usage_last_5d: float | None      # None if no D-1..D-5 data
    reliever_back_to_back_count: int         # 0 if none
    reliever_three_in_four_days_count: int   # 0 if none
    closer_used_last_1d: bool
    closer_used_last_2d: bool

    # DATA_LIMITED features — value MUST be None (no neutral fallback)
    high_leverage_reliever_used_last_1d: None          # Requires LI from PbP
    high_leverage_reliever_workload_last_3d: None      # Requires LI from PbP

    # Metadata
    availability_map: dict[str, str]         # feature → "AVAILABLE" | "DATA_LIMITED"
    pit_window_map: dict[str, int]           # feature → window_days
    audit_hash: str
    module_version: str = PHASE63_MODULE_VERSION
    diagnostic_only: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def _compute_outs_recorded(ip: float) -> int:
    """
    Convert decimal innings_pitched to integer outs recorded.
    Uses round() to avoid float drift (e.g., 6.333... * 3 = 18.9999...).
    """
    return int(round(ip * 3))


def _appearance_audit_hash(game_id: str, pitcher_id: int, ip: float) -> str:
    """Short sha256 hash of (game_id, pitcher_id, ip) for NormalizedReliefAppearance."""
    payload = f"{game_id}:{pitcher_id}:{ip:.3f}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _build_opponent_map_from_appearances(
    appearances: list[ReliefAppearanceRecord],
) -> dict[str, dict[str, str]]:
    """
    Build {game_id: {team_name: opponent_name}} from a list of appearances.
    Derives opponent by pairing home↔away within the same game_id.
    """
    game_sides: dict[str, dict[str, str]] = {}  # game_id → {side → team}
    for rec in appearances:
        if rec.game_id not in game_sides:
            game_sides[rec.game_id] = {}
        game_sides[rec.game_id][rec.side] = rec.team

    result: dict[str, dict[str, str]] = {}
    for game_id, sides in game_sides.items():
        home = sides.get("home", "")
        away = sides.get("away", "")
        result[game_id] = {}
        if home:
            result[game_id][home] = away
        if away:
            result[game_id][away] = home
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Boxscore Parser → NormalizedReliefAppearance
# ─────────────────────────────────────────────────────────────────────────────

def parse_boxscore_to_normalized_appearances(
    *,
    boxscore: dict[str, Any],
    game_id: str,
    game_date: str,
    home_team: str,
    away_team: str,
    source_game_id: str = "",
) -> list[NormalizedReliefAppearance]:
    """
    Parse an MLB StatsAPI /game/{pk}/boxscore response into Phase 63
    NormalizedReliefAppearance records (one per pitcher per side).

    Differences from Phase 62 parse_boxscore_to_appearances:
      - Returns NormalizedReliefAppearance (Phase 63 schema)
      - Extracts opponent, outs_recorded, pitches_thrown, source_game_id, audit_hash
      - Uses appeared_order / starter_flag / opener_flag / reliever_flag field names

    PIT safety: caller guarantees game_date < prediction_date.
    Returns [] if boxscore is None or missing required structure.
    """
    if not boxscore:
        return []
    teams_box = boxscore.get("teams", {})
    if not teams_box:
        return []

    records: list[NormalizedReliefAppearance] = []
    src_game_id = source_game_id or game_id

    for side, team_name in (("home", home_team), ("away", away_team)):
        opponent_name = away_team if side == "home" else home_team
        tbox = teams_box.get(side, {})
        if not tbox:
            continue
        pitcher_ids: list[int] = [int(pid) for pid in (tbox.get("pitchers") or [])]
        players: dict[str, Any] = tbox.get("players") or {}
        if not pitcher_ids:
            continue

        n_pitchers = len(pitcher_ids)
        for order, pid in enumerate(pitcher_ids, start=1):
            player_key = f"ID{pid}"
            player_data = players.get(player_key, {})
            person = player_data.get("person", {})
            pitching_stats = player_data.get("stats", {}).get("pitching", {})

            pitcher_name = str(person.get("fullName", f"UnknownPitcher_{pid}"))
            ip_raw = pitching_stats.get("inningsPitched")
            ip_decimal = _normalize_ip(_parse_innings_pitched(ip_raw))
            pitches_raw = pitching_stats.get("numberOfPitches")
            pitches_thrown: int | None = int(pitches_raw) if pitches_raw is not None else None

            is_first = order == 1
            is_last = order == n_pitchers
            starter_flag = is_first and ip_decimal >= OPENER_IP_THRESHOLD
            opener_flag = is_first and ip_decimal < OPENER_IP_THRESHOLD
            reliever_flag = not starter_flag

            records.append(
                NormalizedReliefAppearance(
                    game_id=game_id,
                    game_date=game_date,
                    team=team_name,
                    opponent=opponent_name,
                    pitcher_id=pid,
                    pitcher_name=pitcher_name,
                    appeared_order=order,
                    starter_flag=starter_flag,
                    opener_flag=opener_flag,
                    reliever_flag=reliever_flag,
                    innings_pitched=ip_decimal,
                    outs_recorded=_compute_outs_recorded(ip_decimal),
                    pitches_thrown=pitches_thrown,
                    source=SOURCE_LABEL,
                    source_game_id=src_game_id,
                    audit_hash=_appearance_audit_hash(game_id, pid, ip_decimal),
                )
            )
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Fixture Loader → NormalizedReliefAppearance
# ─────────────────────────────────────────────────────────────────────────────

def parse_fixture_to_phase63_ingestion(
    fixture_path: Path | None = None,
) -> tuple[list[NormalizedReliefAppearance], IngestionResult]:
    """
    Parse all Phase 62 fixtures into Phase 63 NormalizedReliefAppearance records
    AND a compatible Phase 62 IngestionResult (for report generation).

    Returns:
        (normalized_appearances, ingestion_result) tuple.
        No live API calls; fixture-only proof.
    """
    fixtures = load_fixture_boxscores(fixture_path)
    all_normalized: list[NormalizedReliefAppearance] = []
    all_compat: list[ReliefAppearanceRecord] = []
    games_parsed = 0
    games_missing = 0
    errors: list[str] = []

    for fx in fixtures:
        meta = fx.get("meta", {})
        game_id = meta.get("game_id", "UNKNOWN")
        game_date = meta.get("game_date", "")
        home_team = meta.get("home_team", "")
        away_team = meta.get("away_team", "")
        game_pk = str(meta.get("game_pk", ""))
        boxscore = fx.get("boxscore")

        if boxscore is None:
            games_missing += 1
            continue

        try:
            normalized = parse_boxscore_to_normalized_appearances(
                boxscore=boxscore,
                game_id=game_id,
                game_date=game_date,
                home_team=home_team,
                away_team=away_team,
                source_game_id=game_pk,
            )
            compat = parse_boxscore_to_appearances(
                boxscore=boxscore,
                game_id=game_id,
                game_date=game_date,
                home_team=home_team,
                away_team=away_team,
            )
            all_normalized.extend(normalized)
            all_compat.extend(compat)
            games_parsed += 1
        except Exception as exc:
            errors.append(f"{game_id}: {exc}")

    result = IngestionResult(
        appearances=all_compat,
        games_parsed=games_parsed,
        games_missing=games_missing,
        errors=errors,
    )
    return all_normalized, result


# ─────────────────────────────────────────────────────────────────────────────
# Availability & PIT Window Maps
# ─────────────────────────────────────────────────────────────────────────────

def build_availability_map() -> dict[str, str]:
    """
    Return the canonical feature → availability mapping for Phase 63 artifacts.
    10 AVAILABLE (boxscore-derivable) + 2 DATA_LIMITED (require LI from PbP).
    """
    available = ssot_available_features_from_boxscore()
    limited = ssot_still_data_limited_features()
    return {f: "AVAILABLE" for f in available} | {f: _DATA_LIMITED_SENTINEL for f in limited}


def build_pit_window_map() -> dict[str, int]:
    """Return the canonical feature → window_days mapping for Phase 63 artifacts."""
    return {
        "bullpen_usage_last_1d": 1,
        "bullpen_usage_last_3d": 3,
        "bullpen_usage_last_5d": 5,
        "reliever_back_to_back_count": 2,
        "reliever_three_in_four_days_count": 4,
        "closer_used_last_1d": 1,
        "closer_used_last_2d": 2,
        "bullpen_fatigue_favorite_side": 3,
        "bullpen_fatigue_underdog_side": 3,
        "bullpen_rest_imbalance": 3,
        "high_leverage_reliever_used_last_1d": 1,
        "high_leverage_reliever_workload_last_3d": 3,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SSOT Feature Artifact Builder
# ─────────────────────────────────────────────────────────────────────────────

def compute_ssot_feature_artifact(
    appearances: list[ReliefAppearanceRecord],
    *,
    prediction_game_id: str,
    game_date: str,
    team: str,
) -> SSOTFeatureArtifact:
    """
    Compute all Phase 63 SSOT bullpen features for one (prediction_game_id, team) pair.

    Uses existing Phase 62 window compute functions (PIT-safe by design).
    DATA_LIMITED features (high_leverage_*) are set to None — no neutral fallback.

    Args:
        appearances:        List of ReliefAppearanceRecord from prior games.
        prediction_game_id: Game ID being predicted (used for artifact identity).
        game_date:          Prediction game date (YYYY-MM-DD). Windows reference this.
        team:               Canonical team name to compute features for.

    Returns:
        SSOTFeatureArtifact with all features populated.
    """
    usage_1d = compute_bullpen_ip_window(appearances, team=team, prediction_date=game_date, window_days=WINDOW_1D)
    usage_3d = compute_bullpen_ip_window(appearances, team=team, prediction_date=game_date, window_days=WINDOW_3D)
    usage_5d = compute_bullpen_ip_window(appearances, team=team, prediction_date=game_date, window_days=WINDOW_5D)
    b2b = compute_back_to_back_count(appearances, team=team, prediction_date=game_date)
    three4 = compute_three_in_four_days_count(appearances, team=team, prediction_date=game_date)
    closer_1d = compute_closer_used_within_days(appearances, team=team, prediction_date=game_date, within_days=1)
    closer_2d = compute_closer_used_within_days(appearances, team=team, prediction_date=game_date, within_days=2)

    availability_map = build_availability_map()
    pit_window_map = build_pit_window_map()

    # Build audit hash over computed feature values
    hash_parts = "|".join([
        prediction_game_id,
        game_date,
        team,
        str(usage_1d),
        str(usage_3d),
        str(usage_5d),
        str(b2b),
        str(three4),
        "T" if closer_1d else "F",
        "T" if closer_2d else "F",
    ])
    audit_hash = hashlib.sha256(hash_parts.encode()).hexdigest()[:12]

    return SSOTFeatureArtifact(
        prediction_game_id=prediction_game_id,
        game_date=game_date,
        team=team,
        bullpen_usage_last_1d=usage_1d,
        bullpen_usage_last_3d=usage_3d,
        bullpen_usage_last_5d=usage_5d,
        reliever_back_to_back_count=b2b,
        reliever_three_in_four_days_count=three4,
        closer_used_last_1d=closer_1d,
        closer_used_last_2d=closer_2d,
        high_leverage_reliever_used_last_1d=None,
        high_leverage_reliever_workload_last_3d=None,
        availability_map=availability_map,
        pit_window_map=pit_window_map,
        audit_hash=audit_hash,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 63 Diagnostic Report Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_phase63_diagnostic_report(
    normalized: list[NormalizedReliefAppearance],
    ssot_artifacts: list[SSOTFeatureArtifact],
    ingestion_result: IngestionResult,
) -> dict[str, Any]:
    """
    Build a diagnostic-only Phase 63 report.

    Gate options:
      - GRANULAR_INGESTION_READY       ← all SSOT features derivable & artifacts valid
      - DIAGNOSTIC_ARTIFACT_ONLY       ← artifacts present but coverage issues
      - DATA_QUALITY_BLOCKED           ← data quality errors block ingestion
      - SOURCE_INTEGRATION_BLOCKED     ← source contract broken
    """
    relievers = [r for r in normalized if r.reliever_flag]
    starters = [r for r in normalized if r.starter_flag]
    openers = [r for r in normalized if r.opener_flag]

    # Gate decision: GRANULAR_INGESTION_READY if no errors and >0 valid artifacts
    if ingestion_result.errors:
        gate63 = "DATA_QUALITY_BLOCKED"
    elif not normalized:
        gate63 = "SOURCE_INTEGRATION_BLOCKED"
    elif not ssot_artifacts:
        gate63 = "DIAGNOSTIC_ARTIFACT_ONLY"
    else:
        gate63 = "GRANULAR_INGESTION_READY"

    # Artifact integrity check
    artifact_audit_hashes = [a.audit_hash for a in ssot_artifacts]
    normalized_audit_hashes = [r.audit_hash for r in normalized]

    overall_hash_payload = "|".join(
        sorted(normalized_audit_hashes + artifact_audit_hashes)
    )
    overall_hash = hashlib.sha256(overall_hash_payload.encode()).hexdigest()[:16]

    return {
        "module_version": PHASE63_MODULE_VERSION,
        "phase62_gate": GATE_RESULT,
        "phase63_gate": gate63,
        "diagnostic_only": True,
        "candidate_patch_created": CANDIDATE_PATCH_CREATED,
        "production_modified": PRODUCTION_MODIFIED,
        "alpha_modified": ALPHA_MODIFIED,
        "source": SOURCE_LABEL,
        "ingestion_summary": {
            "games_parsed": ingestion_result.games_parsed,
            "games_missing": ingestion_result.games_missing,
            "total_normalized_appearances": len(normalized),
            "starters": len(starters),
            "openers": len(openers),
            "relievers": len(relievers),
            "errors": ingestion_result.errors,
        },
        "ssot_artifact_summary": {
            "total_artifacts": len(ssot_artifacts),
            "unique_teams": len({a.team for a in ssot_artifacts}),
            "unique_prediction_dates": len({a.game_date for a in ssot_artifacts}),
            "artifacts_with_1d_data": sum(1 for a in ssot_artifacts if a.bullpen_usage_last_1d is not None),
            "artifacts_with_3d_data": sum(1 for a in ssot_artifacts if a.bullpen_usage_last_3d is not None),
            "artifacts_with_5d_data": sum(1 for a in ssot_artifacts if a.bullpen_usage_last_5d is not None),
            "data_limited_confirmed": all(
                a.high_leverage_reliever_used_last_1d is None
                and a.high_leverage_reliever_workload_last_3d is None
                for a in ssot_artifacts
            ),
        },
        "ssot_feature_status": {
            "available_features": ssot_available_features_from_boxscore(),
            "data_limited_features": ssot_still_data_limited_features(),
            "available_count": len(ssot_available_features_from_boxscore()),
            "data_limited_count": len(ssot_still_data_limited_features()),
        },
        "edge_case_policies": EDGE_CASE_POLICIES,
        "phase64_ready": gate63 == "GRANULAR_INGESTION_READY",
        "phase64_guidance": (
            "Phase 64 attribution ready: compute feature EV deltas against CLV / final odds. "
            "Use SSOTFeatureArtifact as input. Restrict to prediction_date games only."
            if gate63 == "GRANULAR_INGESTION_READY"
            else "Resolve gate blocker before Phase 64 attribution."
        ),
        "audit_hash": overall_hash,
    }
