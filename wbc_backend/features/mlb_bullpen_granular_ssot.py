"""
wbc_backend/features/mlb_bullpen_granular_ssot.py
==================================================
Phase 61 — Bullpen Granular Feature SSOT (Single Source of Truth)

目的：
  建立所有 bullpen 粒度特徵的唯一權威來源 schema。
  禁止其他 phase / module 用自己的公式衍生 bullpen fatigue。
  每個 feature 均明確定義 PIT-safe 計算視窗。

SSOT 規則（絕不違反）：
  - 所有 bullpen feature 必須從本模組的 `BullpenGranularRecord` 輸出
  - 若資料不可用，必須輸出 DATA_LIMITED，不得 fallback 成中性值假裝可用
  - 所有特徵的 snapshot_date MUST 嚴格 < game_date
  - 禁止使用 post-game outcome 欄位（home_win、final_score 等）作為 feature

安全常數（絕不修改）：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True

Schema 版本：
  SSOT_SCHEMA_VERSION = "phase61_bullpen_granular_ssot_v1"
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Safety Constants — FROZEN
# ---------------------------------------------------------------------------
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True

SSOT_SCHEMA_VERSION: str = "phase61_bullpen_granular_ssot_v1"

# ---------------------------------------------------------------------------
# Availability Sentinel
# ---------------------------------------------------------------------------

class FeatureAvailability(str, Enum):
    """Availability status of each granular feature."""
    AVAILABLE = "AVAILABLE"               # Value is valid and PIT-safe
    DATA_LIMITED = "DATA_LIMITED"         # Source does not expose this field
    MISSING = "MISSING"                   # Source available but value absent
    PIT_VIOLATION = "PIT_VIOLATION"       # Would require post-game data


# ---------------------------------------------------------------------------
# Forbidden Fields Guard (SSOT-level)
# ---------------------------------------------------------------------------

_FORBIDDEN_POST_GAME_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "game_result",
    "winning_team",
    "losing_team",
    "box_score",
    "post_game_stats",
    "same_game_boxscore",
    "box_score_result",
    "closing_odds_after_game",
    "innings_pitched_today",
    "era_after_game",
    "fip_after_game",
    "whip_after_game",
    "game_score",
    "actual_starter_ip_today",
})

_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"home_win",
    r"final.*score",
    r"winning.*team",
    r"losing.*team",
    r"result",
    r"post.*game",
    r"after.*game",
    r"same.*game.*box",
)


def assert_not_forbidden_field(field_name: str) -> None:
    """
    Raise ValueError if a field name is a forbidden post-game / lookahead field.
    Called at SSOT boundary before any feature is computed.
    """
    lower = field_name.lower()
    if lower in _FORBIDDEN_POST_GAME_FIELDS:
        raise ValueError(
            f"[SSOT-PIT] Field '{field_name}' is a forbidden post-game field. "
            "Cannot be used as a bullpen feature."
        )
    for pat in _FORBIDDEN_PATTERNS:
        if re.search(pat, lower):
            raise ValueError(
                f"[SSOT-PIT] Field '{field_name}' matches forbidden pattern '{pat}'. "
                "Cannot be used as a bullpen feature."
            )


def assert_no_neutral_fallback(
    value: Any,
    field_name: str,
    availability: FeatureAvailability,
) -> None:
    """
    Guard against neutral-value masquerade: if availability is DATA_LIMITED or MISSING,
    the value MUST be None. A non-None value with DATA_LIMITED is a masquerade violation.
    """
    if availability in (FeatureAvailability.DATA_LIMITED, FeatureAvailability.MISSING):
        if value is not None:
            raise ValueError(
                f"[SSOT-MASQUERADE] Field '{field_name}' has availability={availability.value} "
                f"but value={value!r} is not None. "
                "Data-limited features must be None, not a neutral fallback."
            )


# ---------------------------------------------------------------------------
# PIT-safe date window definitions
# ---------------------------------------------------------------------------

# The canonical PIT window for each feature family
# game_date = D → feature uses data from [D - window_days, D - 1]  (inclusive, strict <)
FEATURE_PIT_WINDOWS: dict[str, dict[str, Any]] = {
    "bullpen_usage_last_1d": {
        "window_days": 1,
        "description": "D-1 only: previous day's total relief IP",
        "source": "mlb_stats_api_boxscore",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Current bullpen_usage_3d.jsonl only stores 3-day aggregates; "
            "per-day breakdown not stored"
        ),
    },
    "bullpen_usage_last_3d": {
        "window_days": 3,
        "description": "D-1 + D-2 + D-3: sum of relief IP over three prior days",
        "source": "mlb_stats_api_boxscore",
        "available_in_current_data": True,
        "data_limited_reason": None,
    },
    "bullpen_usage_last_5d": {
        "window_days": 5,
        "description": "D-1 through D-5: sum of relief IP over five prior days",
        "source": "mlb_stats_api_boxscore",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Requires 5-day historical boxscore window not currently fetched"
        ),
    },
    "reliever_back_to_back_count": {
        "window_days": 2,
        "description": (
            "Number of relievers who appeared in both D-1 and D-2 "
            "(pitched on consecutive days). Requires per-pitcher appearance records."
        ),
        "source": "mlb_stats_api_boxscore_per_pitcher",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Requires per-pitcher per-game appearance data; "
            "current source only exposes team-level IP sum"
        ),
    },
    "reliever_three_in_four_days_count": {
        "window_days": 4,
        "description": (
            "Number of relievers who appeared in ≥3 of the last 4 days "
            "(D-1, D-2, D-3, D-4). Requires per-pitcher appearance log."
        ),
        "source": "mlb_stats_api_boxscore_per_pitcher",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Requires per-pitcher per-game appearance data; "
            "current source only exposes team-level IP sum"
        ),
    },
    "closer_used_last_1d": {
        "window_days": 1,
        "description": (
            "Boolean flag: did the team's primary closer pitch on D-1? "
            "Requires pitcher role classification (closer designation)."
        ),
        "source": "mlb_stats_api_boxscore_per_pitcher + closer_role_table",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Closer role not exposed in current boxscore aggregate; "
            "requires pitcher-level data with role/leverage annotations"
        ),
    },
    "closer_used_last_2d": {
        "window_days": 2,
        "description": (
            "Boolean flag: did the team's primary closer pitch in D-1 or D-2?"
        ),
        "source": "mlb_stats_api_boxscore_per_pitcher + closer_role_table",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Same as closer_used_last_1d; requires pitcher-level role data"
        ),
    },
    "high_leverage_reliever_used_last_1d": {
        "window_days": 1,
        "description": (
            "Boolean: did a high-leverage reliever (LI > 1.5) appear on D-1?"
        ),
        "source": "mlb_stats_api_play_by_play + leverage_index",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Leverage index requires play-by-play data not available in boxscore summary"
        ),
    },
    "high_leverage_reliever_workload_last_3d": {
        "window_days": 3,
        "description": (
            "Total IP by relievers with LI > 1.5 over D-1, D-2, D-3"
        ),
        "source": "mlb_stats_api_play_by_play + leverage_index",
        "available_in_current_data": False,
        "data_limited_reason": (
            "Requires play-by-play LI data; not in current boxscore aggregate"
        ),
    },
    "bullpen_fatigue_favorite_side": {
        "window_days": 3,
        "description": (
            "bullpen_usage_last_3d for the team with higher pre-game win probability "
            "(determined from blend probability)"
        ),
        "source": "derived from bullpen_usage_last_3d + blend_prob",
        "available_in_current_data": True,
        "data_limited_reason": None,
    },
    "bullpen_fatigue_underdog_side": {
        "window_days": 3,
        "description": (
            "bullpen_usage_last_3d for the team with lower pre-game win probability"
        ),
        "source": "derived from bullpen_usage_last_3d + blend_prob",
        "available_in_current_data": True,
        "data_limited_reason": None,
    },
    "bullpen_rest_imbalance": {
        "window_days": 3,
        "description": (
            "|bullpen_usage_last_3d_home - bullpen_usage_last_3d_away|: "
            "absolute difference in 3-day bullpen workload"
        ),
        "source": "derived from bullpen_usage_last_3d_{home,away}",
        "available_in_current_data": True,
        "data_limited_reason": None,
    },
}


# ---------------------------------------------------------------------------
# SSOT Record
# ---------------------------------------------------------------------------

@dataclass
class GranularFeatureSlot:
    """Single granular bullpen feature slot with availability tracking."""
    feature_name: str
    value: float | None                  # None if not available
    availability: FeatureAvailability
    data_limited_reason: str | None      # If DATA_LIMITED, reason for it
    pit_window_days: int                 # How many days back from game_date
    pit_snapshot_date: str | None        # Latest date used (YYYY-MM-DD), must < game_date


@dataclass
class BullpenGranularRecord:
    """
    SSOT record for all bullpen granular features for a single game (one side).

    All features computed from data strictly BEFORE game_date (PIT-safe).
    DATA_LIMITED features MUST have value=None.
    """
    # Identity
    ssot_schema_version: str
    game_id: str
    game_date: str           # YYYY-MM-DD
    team: str                # canonical team name
    side: str                # "home" or "away"

    # Safety flags
    candidate_patch_created: bool
    production_modified: bool
    diagnostic_only: bool

    # Core 3d feature (AVAILABLE from current data)
    bullpen_usage_last_3d: GranularFeatureSlot

    # Extended features (DATA_LIMITED until granular acquisition)
    bullpen_usage_last_1d: GranularFeatureSlot
    bullpen_usage_last_5d: GranularFeatureSlot
    reliever_back_to_back_count: GranularFeatureSlot
    reliever_three_in_four_days_count: GranularFeatureSlot
    closer_used_last_1d: GranularFeatureSlot
    closer_used_last_2d: GranularFeatureSlot
    high_leverage_reliever_used_last_1d: GranularFeatureSlot
    high_leverage_reliever_workload_last_3d: GranularFeatureSlot

    # Derived features (AVAILABLE from current data if 3d available)
    bullpen_fatigue_favorite_side: GranularFeatureSlot
    bullpen_fatigue_underdog_side: GranularFeatureSlot
    bullpen_rest_imbalance: GranularFeatureSlot

    # Metadata
    source: str
    pit_safe: bool
    audit_hash: str

    def validate(self) -> list[str]:
        """
        Validate the record. Returns list of violation strings (empty = ok).
        Checks:
          1. All DATA_LIMITED features have value=None (no neutral fallback masquerade)
          2. pit_snapshot_date < game_date for all AVAILABLE slots
          3. Safety flags are frozen correctly
        """
        violations: list[str] = []
        # Safety flags
        if self.candidate_patch_created is not False:
            violations.append("candidate_patch_created must be False")
        if self.production_modified is not False:
            violations.append("production_modified must be False")
        if self.diagnostic_only is not True:
            violations.append("diagnostic_only must be True")

        # All feature slots
        slots: list[GranularFeatureSlot] = [
            self.bullpen_usage_last_3d,
            self.bullpen_usage_last_1d,
            self.bullpen_usage_last_5d,
            self.reliever_back_to_back_count,
            self.reliever_three_in_four_days_count,
            self.closer_used_last_1d,
            self.closer_used_last_2d,
            self.high_leverage_reliever_used_last_1d,
            self.high_leverage_reliever_workload_last_3d,
            self.bullpen_fatigue_favorite_side,
            self.bullpen_fatigue_underdog_side,
            self.bullpen_rest_imbalance,
        ]

        for slot in slots:
            # No neutral fallback masquerade
            if slot.availability in (FeatureAvailability.DATA_LIMITED, FeatureAvailability.MISSING):
                if slot.value is not None:
                    violations.append(
                        f"{slot.feature_name}: availability={slot.availability.value} "
                        f"but value={slot.value!r} is not None (masquerade violation)"
                    )
            # PIT-safe snapshot date
            if slot.availability == FeatureAvailability.AVAILABLE:
                if slot.pit_snapshot_date is not None:
                    if slot.pit_snapshot_date >= self.game_date:
                        violations.append(
                            f"{slot.feature_name}: pit_snapshot_date={slot.pit_snapshot_date} "
                            f">= game_date={self.game_date} (PIT violation)"
                        )

        return violations


# ---------------------------------------------------------------------------
# SSOT Record Builders
# ---------------------------------------------------------------------------

def _make_data_limited_slot(
    feature_name: str,
    game_date: str,
) -> GranularFeatureSlot:
    """Create a DATA_LIMITED slot with value=None."""
    meta = FEATURE_PIT_WINDOWS.get(feature_name, {})
    return GranularFeatureSlot(
        feature_name=feature_name,
        value=None,
        availability=FeatureAvailability.DATA_LIMITED,
        data_limited_reason=meta.get("data_limited_reason", "Source not available"),
        pit_window_days=meta.get("window_days", 0),
        pit_snapshot_date=None,
    )


def _make_available_slot(
    feature_name: str,
    value: float | None,
    game_date: str,
    snapshot_date: str | None = None,
) -> GranularFeatureSlot:
    """
    Create an AVAILABLE or MISSING slot.
    If value is None → MISSING.
    pit_snapshot_date defaults to game_date - 1d if not provided.
    """
    meta = FEATURE_PIT_WINDOWS.get(feature_name, {})
    if snapshot_date is None:
        d = date.fromisoformat(game_date)
        snapshot_date = (d - timedelta(days=1)).isoformat()
    availability = FeatureAvailability.AVAILABLE if value is not None else FeatureAvailability.MISSING
    return GranularFeatureSlot(
        feature_name=feature_name,
        value=value,
        availability=availability,
        data_limited_reason=None,
        pit_window_days=meta.get("window_days", 3),
        pit_snapshot_date=snapshot_date,
    )


def _compute_audit_hash(game_id: str, team: str, side: str) -> str:
    payload = f"{SSOT_SCHEMA_VERSION}:{game_id}:{team}:{side}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def build_granular_record(
    game_id: str,
    game_date: str,
    team: str,
    side: str,
    bullpen_3d_ip: float | None,
    fav_3d_ip: float | None,
    dog_3d_ip: float | None,
    home_3d_ip: float | None,
    away_3d_ip: float | None,
    source: str = "mlb_stats_api_boxscore",
) -> BullpenGranularRecord:
    """
    Build a BullpenGranularRecord from the current available 3d data.

    Parameters
    ----------
    game_id       : canonical game_id
    game_date     : YYYY-MM-DD, the game's date (PIT reference)
    team          : canonical team name
    side          : "home" or "away"
    bullpen_3d_ip : This team's bullpen IP over D-1+D-2+D-3. None if unavailable.
    fav_3d_ip     : Favored team's bullpen_3d IP (or None)
    dog_3d_ip     : Underdog team's bullpen_3d IP (or None)
    home_3d_ip    : Home team's bullpen_3d IP (or None)
    away_3d_ip    : Away team's bullpen_3d IP (or None)
    source        : Data source identifier
    """
    # Rest imbalance = |home - away|
    if home_3d_ip is not None and away_3d_ip is not None:
        rest_imbalance = round(abs(home_3d_ip - away_3d_ip), 4)
    else:
        rest_imbalance = None

    record = BullpenGranularRecord(
        ssot_schema_version=SSOT_SCHEMA_VERSION,
        game_id=game_id,
        game_date=game_date,
        team=team,
        side=side,
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,

        # AVAILABLE: 3d aggregate from current source
        bullpen_usage_last_3d=_make_available_slot(
            "bullpen_usage_last_3d", bullpen_3d_ip, game_date
        ),

        # DATA_LIMITED: not in current source
        bullpen_usage_last_1d=_make_data_limited_slot("bullpen_usage_last_1d", game_date),
        bullpen_usage_last_5d=_make_data_limited_slot("bullpen_usage_last_5d", game_date),
        reliever_back_to_back_count=_make_data_limited_slot(
            "reliever_back_to_back_count", game_date
        ),
        reliever_three_in_four_days_count=_make_data_limited_slot(
            "reliever_three_in_four_days_count", game_date
        ),
        closer_used_last_1d=_make_data_limited_slot("closer_used_last_1d", game_date),
        closer_used_last_2d=_make_data_limited_slot("closer_used_last_2d", game_date),
        high_leverage_reliever_used_last_1d=_make_data_limited_slot(
            "high_leverage_reliever_used_last_1d", game_date
        ),
        high_leverage_reliever_workload_last_3d=_make_data_limited_slot(
            "high_leverage_reliever_workload_last_3d", game_date
        ),

        # DERIVED (available if 3d available)
        bullpen_fatigue_favorite_side=_make_available_slot(
            "bullpen_fatigue_favorite_side", fav_3d_ip, game_date
        ),
        bullpen_fatigue_underdog_side=_make_available_slot(
            "bullpen_fatigue_underdog_side", dog_3d_ip, game_date
        ),
        bullpen_rest_imbalance=_make_available_slot(
            "bullpen_rest_imbalance", rest_imbalance, game_date
        ),

        source=source,
        pit_safe=True,
        audit_hash=_compute_audit_hash(game_id, team, side),
    )

    # Validate on construction
    violations = record.validate()
    if violations:
        raise ValueError(
            f"[SSOT] BullpenGranularRecord built with violations: {violations}"
        )
    return record


# ---------------------------------------------------------------------------
# SSOT Guard: Single-Source Enforcement
# ---------------------------------------------------------------------------

_SSOT_REGISTERED_MODULES: dict[str, str] = {
    # feature_family → authoritative module path
    "bullpen_usage_last_3d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_usage_last_1d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_usage_last_5d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "reliever_back_to_back_count": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "reliever_three_in_four_days_count": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "closer_used_last_1d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "closer_used_last_2d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "high_leverage_reliever_used_last_1d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "high_leverage_reliever_workload_last_3d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_fatigue_favorite_side": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_fatigue_underdog_side": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_rest_imbalance": "wbc_backend.features.mlb_bullpen_granular_ssot",
    # Legacy Phase56/58 features → must migrate to this SSOT
    "bullpen_fatigue_3d": "wbc_backend.features.mlb_bullpen_granular_ssot",
    "bullpen_fatigue_7d": "wbc_backend.features.mlb_bullpen_granular_ssot",
}


def assert_ssot_ownership(feature_name: str, caller_module: str) -> None:
    """
    Assert that the calling module is the SSOT owner for a bullpen feature.
    Raises ValueError if a non-SSOT module attempts to define a bullpen feature.

    Usage:
        # At the top of any module that computes bullpen features:
        assert_ssot_ownership("bullpen_usage_last_3d", __name__)
    """
    authoritative = _SSOT_REGISTERED_MODULES.get(feature_name)
    if authoritative is None:
        return  # Unknown feature, no SSOT registered yet → allow
    if caller_module != authoritative:
        raise ValueError(
            f"[SSOT-GUARD] Module '{caller_module}' attempted to define feature "
            f"'{feature_name}' but the SSOT owner is '{authoritative}'. "
            "All bullpen features must be sourced from mlb_bullpen_granular_ssot."
        )


def get_ssot_owner(feature_name: str) -> str | None:
    """Return the SSOT owner module for a feature, or None if unregistered."""
    return _SSOT_REGISTERED_MODULES.get(feature_name)


def list_available_features() -> list[str]:
    """List all features that are available in the current data (not DATA_LIMITED)."""
    return [
        fname for fname, meta in FEATURE_PIT_WINDOWS.items()
        if meta.get("available_in_current_data", False)
    ]


def list_data_limited_features() -> list[str]:
    """List all features that are DATA_LIMITED in the current data."""
    return [
        fname for fname, meta in FEATURE_PIT_WINDOWS.items()
        if not meta.get("available_in_current_data", True)
    ]


# ---------------------------------------------------------------------------
# Handling Policy: Special Cases
# ---------------------------------------------------------------------------

class SpecialGameHandlingPolicy:
    """
    Documents the SSOT policy for special game situations.
    All policies are read-only constants (no runtime behavior).
    """

    # Doubleheader games on the same calendar date
    DOUBLEHEADER: str = (
        "For doubleheader games on date D: "
        "Game 1 may use data from D-1 and earlier. "
        "Game 2 must also only use data from D-1 and earlier "
        "(Game 1 result on date D is POST-GAME and therefore forbidden). "
        "If bullpen_usage_last_1d is later implemented, doubleheader "
        "Game 2 MUST NOT include Game 1's bullpen usage as D-0 data."
    )

    # Postponed or suspended games
    POSTPONED: str = (
        "For postponed/suspended games: "
        "The PIT window is anchored to the actual played date, not the "
        "originally scheduled date. "
        "Rescheduled games inherit the postponement date as their game_date."
    )

    # Opener / bulk pitcher usage
    OPENER: str = (
        "Opener games: the 'opener' pitcher is treated as a reliever if "
        "IP < 2.0. Their IP contributes to bullpen_usage_last_Nd for that date. "
        "The 'bulk pitcher' who follows is also treated as a reliever if they "
        "entered before the 3rd out of inning 3. "
        "Source: mlb_stats_api_boxscore pitchers[0] exclusion logic must be "
        "disabled for opener-formatted games."
    )

    # Missing boxscore games
    MISSING_BOXSCORE: str = (
        "If no boxscore is available for a historical game, all features for that "
        "game_date must be output as MISSING (not DATA_LIMITED, not neutral fallback). "
        "Downstream consumers must handle MISSING explicitly."
    )

    # Rain delay / mid-game suspension
    SUSPENSION: str = (
        "Suspended games that resume on a later date: "
        "bullpen usage in the original day is credited to the original game_date. "
        "Usage in the resumed portion is credited to the resume date. "
        "Features for games after the resume date use the combined historical record."
    )
