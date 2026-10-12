"""
MLB Point-in-Time Validator — Phase 52
=======================================
驗證先發投手統計快照是否為 point-in-time safe。

核心規則：
1. snapshot_date < game_date（嚴格小於）
2. 不含任何 forbidden fields（leakage guard）
3. point_in_time_safe 旗標 = True
4. audit_hash 存在且非空
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 常數 ──────────────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False

# 絕對禁止出現在 SP snapshot 中的欄位
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "box_score",
    "post_game_stats",
    "closing_odds_after_game",
    "actual_starter_ip_today",
    "game_score",
    "innings_pitched_today",
    "era_after_game",
    "whip_after_game",
    "fip_after_game",
})


@dataclass
class PitValidationResult:
    """Point-in-time 驗證結果。"""
    is_safe: bool
    violations: list[str]       # 違規項目列表（空 = 通過）
    warnings: list[str]         # 警告（不影響 is_safe）
    snapshot_date: Optional[str]
    game_date: Optional[str]
    audit_hash_present: bool

    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False


def validate_point_in_time_snapshot(
    snapshot: Any,
    game_date: str,
) -> PitValidationResult:
    """
    驗證先發投手統計快照是否為 point-in-time safe。

    Args:
        snapshot: PitcherStatSnapshot dataclass 或 dict
        game_date: 比賽日期（YYYY-MM-DD）

    Returns:
        PitValidationResult

    規則（全部通過 → is_safe = True）：
    1. snapshot_date < game_date
    2. 不含任何 forbidden fields
    3. point_in_time_safe = True
    4. audit_hash 存在且非空
    """
    violations: list[str] = []
    warnings: list[str] = []

    # 支援 dataclass 或 dict
    if hasattr(snapshot, "__dict__"):
        snap_dict = snapshot.__dict__
        snap_date = getattr(snapshot, "snapshot_date", None)
        pit_safe = getattr(snapshot, "point_in_time_safe", None)
        audit_hash = getattr(snapshot, "audit_hash", None)
    elif isinstance(snapshot, dict):
        snap_dict = snapshot
        snap_date = snapshot.get("snapshot_date")
        pit_safe = snapshot.get("point_in_time_safe")
        audit_hash = snapshot.get("audit_hash")
    else:
        violations.append(f"unsupported snapshot type: {type(snapshot)}")
        return PitValidationResult(
            is_safe=False, violations=violations, warnings=warnings,
            snapshot_date=None, game_date=game_date,
            audit_hash_present=False,
        )

    # ── Rule 1: snapshot_date < game_date ──────────────────────────────────
    if snap_date is None:
        violations.append("snapshot_date is None")
    else:
        try:
            snap_d = date.fromisoformat(snap_date)
            game_d = date.fromisoformat(game_date)
            if snap_d >= game_d:
                violations.append(
                    f"snapshot_date {snap_date} >= game_date {game_date} "
                    f"(look-ahead leakage detected)"
                )
        except ValueError as e:
            violations.append(f"date parse error: {e}")

    # ── Rule 2: 不含 forbidden fields ──────────────────────────────────────
    for bad_field in _FORBIDDEN_FIELDS:
        if bad_field in snap_dict and snap_dict[bad_field] is not None:
            violations.append(f"forbidden field present: {bad_field}")

    # ── Rule 3: point_in_time_safe 旗標 ────────────────────────────────────
    if pit_safe is None:
        warnings.append("point_in_time_safe flag not set (treating as missing)")
    elif pit_safe is False:
        violations.append("point_in_time_safe = False")

    # ── Rule 4: audit_hash ──────────────────────────────────────────────────
    audit_hash_present = bool(audit_hash)
    if not audit_hash_present:
        violations.append("audit_hash is missing or empty")

    is_safe = len(violations) == 0

    if is_safe:
        logger.debug("PIT validation passed for game_date=%s", game_date)
    else:
        logger.warning(
            "PIT validation FAILED for game_date=%s violations=%s",
            game_date, violations,
        )

    return PitValidationResult(
        is_safe=is_safe,
        violations=violations,
        warnings=warnings,
        snapshot_date=snap_date,
        game_date=game_date,
        audit_hash_present=audit_hash_present,
    )


def validate_batch(
    snapshots: list[Any],
    game_dates: list[str],
) -> dict:
    """
    批次驗證多個快照。

    Returns:
        {
          "total": int,
          "safe": int,
          "unsafe": int,
          "safe_rate": float,
          "violations_summary": list[str],
        }
    """
    if len(snapshots) != len(game_dates):
        raise ValueError("snapshots 與 game_dates 長度不符")

    results = [
        validate_point_in_time_snapshot(snap, gd)
        for snap, gd in zip(snapshots, game_dates)
    ]

    safe_count = sum(1 for r in results if r.is_safe)
    all_violations: list[str] = []
    for r in results:
        all_violations.extend(r.violations)

    return {
        "total": len(results),
        "safe": safe_count,
        "unsafe": len(results) - safe_count,
        "safe_rate": safe_count / max(len(results), 1),
        "violations_summary": list(set(all_violations)),
        "candidate_patch_created": False,
        "production_modified": False,
    }
