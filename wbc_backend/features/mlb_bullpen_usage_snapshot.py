"""
wbc_backend/features/mlb_bullpen_usage_snapshot.py
===================================================
Phase 58 — Team Rolling Bullpen Snapshot Builder

功能：
  build_bullpen_snapshot_for_game(game_row, team_history, relief_appearances) -> dict

對每一場 game_date = D，建立 D-1 Point-in-Time Snapshot：
  - 只使用 entry_date < game_date 的歷史記錄（strict <）
  - 同日資料全部排除（含 doubleheader）

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - PIT: entry_date < game_date (strict <)
  - 不可使用 home_win / final_score / result 計算 feature
  - snapshot_date MUST < game_date
  - audit_hash MUST be present
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import date, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase58_bullpen_usage_v1"

# ─── League average defaults ─────────────────────────────────────────────────
_LEAGUE_AVG_ERA: float = 4.10
_LEAGUE_AVG_FIP: float = 4.05
_NEUTRAL_LEVERAGE: float = 0.0

# ─── Proxy estimation ────────────────────────────────────────────────────────
_PROXY_BULLPEN_OUTS_PER_GAME: float = 9.0   # ~3 innings of bullpen per game

# ─── Rolling window definitions ──────────────────────────────────────────────
_WINDOW_1D: int = 1
_WINDOW_3D: int = 3
_WINDOW_7D: int = 7
_WINDOW_14D: int = 14

# ─── B2B / high-frequency thresholds ────────────────────────────────────────
# A reliever is "B2B" if they appeared in the preceding 2 calendar days.
# We proxy this as: team played >= 1 game in the prior 1 day
_B2B_WINDOW_DAYS: int = 2
_HIGH_FREQ_WINDOW_DAYS: int = 4   # 3-in-4 = team played >= 3 games in prior 4 days

# ─── Minimum data requirements ───────────────────────────────────────────────
# A snapshot is considered "available" if the team has played at least
# 1 prior game in the 7-day window (enough to estimate workload).
_MIN_GAMES_FOR_AVAILABLE: int = 1

# ─── Forbidden leakage fields ────────────────────────────────────────────────
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "box_score",
    "post_game_stats",
    "closing_odds_after_game",
    "innings_pitched_today",
    "era_after_game",
    "game_score",
    "actual_starter_ip_today",
    "same_game_boxscore",
    "box_score_result",
})


def _pit_safe_history(
    team_history: list,  # list[ScheduleGameRecord]
    game_date: str,
) -> list:
    """
    從球隊歷史記錄中篩選出 game_date < 目標日期 的記錄（strict <）。
    同日資料全部排除。
    """
    return [
        rec for rec in team_history
        if rec.game_date < game_date and rec.is_completed
    ]


def _games_in_window(
    history: list,
    game_date: str,
    window_days: int,
) -> list:
    """
    找出過去 window_days 天內的比賽記錄（PIT 安全）。
    """
    target = date.fromisoformat(game_date)
    cutoff = target - timedelta(days=window_days)
    return [
        rec for rec in history
        if cutoff <= date.fromisoformat(rec.game_date) < target
    ]


def _compute_bullpen_outs_window(
    history: list,
    game_date: str,
    window_days: int,
    proxy_outs_per_game: float = _PROXY_BULLPEN_OUTS_PER_GAME,
) -> tuple[float, bool]:
    """
    計算過去 window_days 天的牛棚出局數估計值。

    Returns:
        (outs_estimate, is_available)
    """
    games_in_window = _games_in_window(history, game_date, window_days)
    if not games_in_window:
        return 0.0, False
    total_outs = len(games_in_window) * proxy_outs_per_game
    return round(total_outs, 2), True


def _compute_b2b_count_proxy(
    history: list,
    game_date: str,
) -> tuple[int, bool]:
    """
    估計 B2B（連續 2 天出賽）的中繼投手數量。

    Proxy 邏輯：
    - 若球隊在前 1 天有比賽 → 估計有 1 名 reliever B2B
    - 若球隊在前 1 天有 2+ 場比賽（少見）→ 估計有 2 名 reliever B2B
    """
    games_prev_1d = _games_in_window(history, game_date, _B2B_WINDOW_DAYS - 1)
    if not games_prev_1d:
        return 0, True  # No games yesterday → no B2B
    # Proxy: 1 reliever B2B per consecutive-day game
    b2b_count = min(len(games_prev_1d), 3)  # cap at 3
    return b2b_count, True


def _compute_3in4_count_proxy(
    history: list,
    game_date: str,
) -> tuple[int, bool]:
    """
    估計「4 天內出賽 3 次以上」的中繼投手數量。

    Proxy 邏輯：
    - 若球隊在前 3 天有 3+ 場比賽 → 估計有 1 名 reliever 3-in-4
    """
    games_prev_3d = _games_in_window(history, game_date, _HIGH_FREQ_WINDOW_DAYS - 1)
    if len(games_prev_3d) < 3:
        return 0, True
    # Proxy: 1 high-frequency reliever per 3 games in 4 days
    three_in_four_count = max(0, len(games_prev_3d) - 2)
    return min(three_in_four_count, 4), True  # cap at 4


def _compute_era_proxy(
    history: list,
    game_date: str,
    window_days: int = _WINDOW_14D,
) -> tuple[float, bool]:
    """
    計算近期牛棚 ERA proxy。

    由於無真實 ER/IP 資料，本 Phase 使用聯盟平均 ERA 作為 proxy。
    若球隊在 window 內有比賽記錄，返回聯盟平均；否則返回 fallback。

    Returns:
        (era_proxy, is_available)
    """
    games_in_window = _games_in_window(history, game_date, window_days)
    if not games_in_window:
        return _LEAGUE_AVG_ERA, False
    # Use league average as the best available proxy
    return _LEAGUE_AVG_ERA, True


def _compute_fip_proxy(
    history: list,
    game_date: str,
    window_days: int = _WINDOW_14D,
) -> tuple[float, bool]:
    """
    計算近期牛棚 FIP proxy。
    由於無 K/BB/HR 資料，使用聯盟平均 FIP。

    Returns:
        (fip_proxy, is_available)
    """
    games_in_window = _games_in_window(history, game_date, window_days)
    if not games_in_window:
        return _LEAGUE_AVG_FIP, False
    return _LEAGUE_AVG_FIP, True


def _compute_leverage_proxy(
    history: list,
    game_date: str,
    window_days: int = _WINDOW_7D,
) -> tuple[float, float, bool]:
    """
    計算高槓桿使用 proxy。
    由於無 play-by-play 資料，leverage proxy = 0.0（未知）。

    Returns:
        (late_game_leverage_usage_proxy, high_leverage_usage_3d, is_available)
    """
    # Phase 58: No leverage data available
    # Phase 59 will add Statcast leverage_index
    return _NEUTRAL_LEVERAGE, 0.0, False


def _compute_snapshot_audit_hash(
    game_id: str,
    snapshot_date: str,
    source: str,
    home_outs_3d: float,
    away_outs_3d: float,
    home_b2b: int,
    away_b2b: int,
) -> str:
    payload = (
        f"{game_id}|{snapshot_date}|{source}|"
        f"{home_outs_3d:.2f}|{away_outs_3d:.2f}|"
        f"{home_b2b}|{away_b2b}|{FEATURE_VERSION}"
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def _compute_snapshot_date(game_date: str) -> str:
    """
    Compute snapshot_date = game_date - 1 day.
    snapshot_date MUST be < game_date.
    """
    d = date.fromisoformat(game_date)
    return (d - timedelta(days=1)).isoformat()


def build_bullpen_snapshot_for_game(
    game_row: dict,
    team_history: dict[str, list],  # team_name -> list[ScheduleGameRecord]
    relief_appearances: Optional[list] = None,  # unused in proxy mode
) -> dict:
    """
    為單場比賽建立 PIT-safe 牛棚使用快照。

    Args:
        game_row: baseline prediction row (含 game_id, game_date, home_team, away_team)
        team_history: dict[team_name, list[ScheduleGameRecord]] — 全賽季歷史記錄
        relief_appearances: 若有真實出賽記錄可傳入（Phase 59 使用）；
                            Phase 58 不使用，由 schedule proxy 計算

    Returns:
        dict — Phase 58 schema 完整快照

    Hard Rules:
        - snapshot_date = game_date - 1 (MUST be < game_date)
        - 只使用 entry_date < game_date 的記錄
        - 不含 forbidden leakage fields
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    game_id = game_row.get("game_id", "")
    game_date = game_row.get("game_date", "")
    home_team = game_row.get("home_team", "")
    away_team = game_row.get("away_team", "")

    # ── PIT: 取得歷史記錄（entry_date < game_date） ──────────────────────────
    home_history = _pit_safe_history(
        team_history.get(home_team, []), game_date
    )
    away_history = _pit_safe_history(
        team_history.get(away_team, []), game_date
    )

    # ── snapshot_date ─────────────────────────────────────────────────────────
    snapshot_date = _compute_snapshot_date(game_date)
    assert snapshot_date < game_date, f"PIT violation: snapshot={snapshot_date} >= game={game_date}"

    # ── Workload: Bullpen Outs ────────────────────────────────────────────────
    home_outs_1d, home_1d_avail = _compute_bullpen_outs_window(home_history, game_date, _WINDOW_1D)
    away_outs_1d, away_1d_avail = _compute_bullpen_outs_window(away_history, game_date, _WINDOW_1D)
    home_outs_3d, home_3d_avail = _compute_bullpen_outs_window(home_history, game_date, _WINDOW_3D)
    away_outs_3d, away_3d_avail = _compute_bullpen_outs_window(away_history, game_date, _WINDOW_3D)
    home_outs_7d, home_7d_avail = _compute_bullpen_outs_window(home_history, game_date, _WINDOW_7D)
    away_outs_7d, away_7d_avail = _compute_bullpen_outs_window(away_history, game_date, _WINDOW_7D)

    # ── B2B & High-Frequency Usage ───────────────────────────────────────────
    home_b2b, home_b2b_avail = _compute_b2b_count_proxy(home_history, game_date)
    away_b2b, away_b2b_avail = _compute_b2b_count_proxy(away_history, game_date)
    home_3in4, home_3in4_avail = _compute_3in4_count_proxy(home_history, game_date)
    away_3in4, away_3in4_avail = _compute_3in4_count_proxy(away_history, game_date)

    # ── Performance Proxy ────────────────────────────────────────────────────
    home_era, home_era_avail = _compute_era_proxy(home_history, game_date)
    away_era, away_era_avail = _compute_era_proxy(away_history, game_date)
    home_fip, home_fip_avail = _compute_fip_proxy(home_history, game_date)
    away_fip, away_fip_avail = _compute_fip_proxy(away_history, game_date)

    # ── Leverage Proxy ───────────────────────────────────────────────────────
    home_leverage, home_lev_3d, home_lev_avail = _compute_leverage_proxy(home_history, game_date)
    away_leverage, away_lev_3d, away_lev_avail = _compute_leverage_proxy(away_history, game_date)

    # ── Derived Deltas (away - home) ─────────────────────────────────────────
    # Positive delta = away more fatigued / worse → home advantage
    fatigue_delta_3d = round(away_outs_3d - home_outs_3d, 2)
    fatigue_delta_7d = round(away_outs_7d - home_outs_7d, 2)
    b2b_delta = away_b2b - home_b2b
    era_delta = round(away_era - home_era, 4)
    fip_delta = round(away_fip - home_fip, 4)
    leverage_delta_3d = round(away_lev_3d - home_lev_3d, 2)

    # ── Availability Summary ─────────────────────────────────────────────────
    # bullpen_feature_available = True if BOTH teams have ≥ 1 prior game in 7d
    workload_available = home_7d_avail and away_7d_avail
    b2b_available = home_b2b_avail and away_b2b_avail
    performance_proxy_available = home_era_avail and away_era_avail
    leverage_available = home_lev_avail and away_lev_avail
    # Core availability: workload data is the minimum requirement
    bullpen_feature_available = workload_available

    # ── Fallback reason ──────────────────────────────────────────────────────
    fallback_parts: list[str] = []
    if not workload_available:
        if not home_7d_avail:
            fallback_parts.append(f"no_home_history:{home_team}")
        if not away_7d_avail:
            fallback_parts.append(f"no_away_history:{away_team}")
    if not leverage_available:
        fallback_parts.append("no_leverage_data:schedule_proxy_only")
    if not performance_proxy_available:
        fallback_parts.append("no_era_data:schedule_proxy_only")

    fallback_reason = "; ".join(fallback_parts) if fallback_parts else ""
    source = "schedule_proxy_fallback"
    estimated = True

    # ── Audit Hash ───────────────────────────────────────────────────────────
    audit_hash = _compute_snapshot_audit_hash(
        game_id=game_id,
        snapshot_date=snapshot_date,
        source=source,
        home_outs_3d=home_outs_3d,
        away_outs_3d=away_outs_3d,
        home_b2b=home_b2b,
        away_b2b=away_b2b,
    )

    snapshot = {
        # === Game Identity ===
        "game_id": game_id,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "season": game_row.get("season", 2025),
        "doubleheader_game_num": 0,   # Phase 58: all games treated as non-DH
        "is_bullpen_game": False,      # Phase 58: not detected from proxy

        # === Bullpen Workload — Home ===
        "home_bullpen_outs_1d": home_outs_1d,
        "home_bullpen_outs_3d": home_outs_3d,
        "home_bullpen_outs_7d": home_outs_7d,
        "home_bullpen_outs_1d_available": home_1d_avail,
        "home_bullpen_outs_3d_available": home_3d_avail,
        "home_bullpen_outs_7d_available": home_7d_avail,

        # === Bullpen Workload — Away ===
        "away_bullpen_outs_1d": away_outs_1d,
        "away_bullpen_outs_3d": away_outs_3d,
        "away_bullpen_outs_7d": away_outs_7d,
        "away_bullpen_outs_1d_available": away_1d_avail,
        "away_bullpen_outs_3d_available": away_3d_avail,
        "away_bullpen_outs_7d_available": away_7d_avail,

        # === B2B & High-Frequency ===
        "home_reliever_b2b_count": home_b2b,
        "away_reliever_b2b_count": away_b2b,
        "home_reliever_3in4_count": home_3in4,
        "away_reliever_3in4_count": away_3in4,
        "home_b2b_available": home_b2b_avail,
        "away_b2b_available": away_b2b_avail,
        "home_3in4_available": home_3in4_avail,
        "away_3in4_available": away_3in4_avail,

        # === Performance Proxy ===
        "home_bullpen_recent_era_proxy": home_era,
        "away_bullpen_recent_era_proxy": away_era,
        "home_bullpen_recent_fip_proxy": home_fip,
        "away_bullpen_recent_fip_proxy": away_fip,
        "home_era_available": home_era_avail,
        "away_era_available": away_era_avail,
        "home_fip_available": home_fip_avail,
        "away_fip_available": away_fip_avail,

        # === Leverage Proxy ===
        "home_late_game_leverage_usage_proxy": home_leverage,
        "away_late_game_leverage_usage_proxy": away_leverage,
        "home_high_leverage_reliever_usage_3d": home_lev_3d,
        "away_high_leverage_reliever_usage_3d": away_lev_3d,
        "home_leverage_available": home_lev_avail,
        "away_leverage_available": away_lev_avail,

        # === Derived Deltas ===
        "bullpen_fatigue_delta_3d": fatigue_delta_3d,
        "bullpen_fatigue_delta_7d": fatigue_delta_7d,
        "reliever_b2b_delta": b2b_delta,
        "bullpen_recent_era_delta": era_delta,
        "bullpen_recent_fip_delta": fip_delta,
        "leverage_usage_delta": leverage_delta_3d,

        # === Availability Summary ===
        "bullpen_feature_available": bullpen_feature_available,
        "workload_available": workload_available,
        "leverage_available": leverage_available,
        "performance_proxy_available": performance_proxy_available,
        "estimated": estimated,
        "availability_components": {
            "home_3d": home_3d_avail,
            "away_3d": away_3d_avail,
            "home_b2b": home_b2b_avail,
            "away_b2b": away_b2b_avail,
            "home_era": home_era_avail,
            "away_era": away_era_avail,
            "home_leverage": home_lev_avail,
            "away_leverage": away_lev_avail,
        },
        "fallback_reason": fallback_reason,

        # === Audit ===
        "snapshot_date": snapshot_date,
        "data_timestamp": "",   # filled by backfill script
        "source": source,
        "source_detail": "asplayed_schedule_proxy",
        "point_in_time_safe": True,
        "feature_version": FEATURE_VERSION,
        "audit_hash": audit_hash,

        # Hard rules
        "candidate_patch_created": CANDIDATE_PATCH_CREATED,
        "production_modified": PRODUCTION_MODIFIED,
        "diagnostic_only": DIAGNOSTIC_ONLY,
    }

    return snapshot


def build_bullpen_snapshots_batch(
    game_rows: list[dict],
    team_history: dict[str, list],
) -> list[dict]:
    """
    批次建立所有比賽的牛棚快照。

    Args:
        game_rows: baseline prediction rows
        team_history: dict[team_name, list[ScheduleGameRecord]]

    Returns:
        list of snapshot dicts (order matches game_rows)
    """
    snapshots: list[dict] = []
    for row in game_rows:
        snap = build_bullpen_snapshot_for_game(row, team_history)
        snapshots.append(snap)
    return snapshots
