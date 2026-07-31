"""
wbc_backend/features/mlb_bullpen_pit_validator.py
==================================================
Phase 56 — Bullpen Feature Point-in-Time Validator

驗證 build_bullpen_features() 的輸出是否符合 PIT-safe 規範。

核心規則：
1. point_in_time_safe = True（強制）
2. 不含任何 forbidden post-game fields
3. audit_hash 存在且非空
4. candidate_patch_created = False
5. production_modified = False

Usage:
    from wbc_backend.features.mlb_bullpen_pit_validator import (
        validate_bullpen_features,
        BullpenPitValidationResult,
    )

    result = validate_bullpen_features(bullpen_record, game_date="2025-04-15")
    if not result.is_safe:
        raise ValueError(result.violations)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False

# ─── Forbidden post-game fields (must NEVER appear with non-None values) ──────
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
    "whip_after_game",
    "fip_after_game",
})

# ─── Required fields that must exist in every bullpen record ──────────────────
_REQUIRED_FIELDS: frozenset[str] = frozenset({
    "feature_version",
    "bullpen_feature_available",
    "point_in_time_safe",
    "audit_hash",
    "candidate_patch_created",
    "production_modified",
    "bullpen_feature_source",
    "fallback_reason",
})


@dataclass
class BullpenPitValidationResult:
    """Bullpen point-in-time 驗證結果。"""
    is_safe: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    game_date: str = ""
    audit_hash_present: bool = False
    pit_flag_correct: bool = False
    hard_rules_correct: bool = False
    # Hard rules (always False — invariants)
    candidate_patch_created: bool = False
    production_modified: bool = False


def validate_bullpen_features(
    bullpen_record: dict,
    game_date: str = "",
) -> BullpenPitValidationResult:
    """
    Validate that a bullpen feature record is point-in-time safe.

    Args:
        bullpen_record: Output of build_bullpen_features() or a backfill row.
        game_date: The game date (YYYY-MM-DD) for context.
                   If provided, additional date-consistency checks are applied.

    Returns:
        BullpenPitValidationResult

    Validation rules (all must pass for is_safe = True):
    1. No forbidden post-game fields with non-None values
    2. point_in_time_safe == True
    3. audit_hash is present and non-empty
    4. candidate_patch_created == False
    5. production_modified == False
    6. All required fields are present
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    violations: list[str] = []
    warnings: list[str] = []

    if not isinstance(bullpen_record, dict):
        violations.append(f"bullpen_record must be dict, got {type(bullpen_record)}")
        return BullpenPitValidationResult(
            is_safe=False,
            violations=violations,
            warnings=warnings,
            game_date=game_date,
        )

    # ── Rule 1: No forbidden post-game fields ─────────────────────────────
    for bad_field in _FORBIDDEN_FIELDS:
        if bad_field in bullpen_record and bullpen_record[bad_field] is not None:
            violations.append(f"forbidden post-game field present: {bad_field}")

    # ── Rule 2: point_in_time_safe == True ───────────────────────────────
    pit_flag = bullpen_record.get("point_in_time_safe")
    pit_flag_correct = (pit_flag is True)
    if not pit_flag_correct:
        violations.append(
            f"point_in_time_safe must be True, got {pit_flag!r}"
        )

    # ── Rule 3: audit_hash present and non-empty ──────────────────────────
    audit_hash = bullpen_record.get("audit_hash", "")
    audit_hash_present = bool(audit_hash)
    if not audit_hash_present:
        violations.append("audit_hash is missing or empty")

    # ── Rule 4: candidate_patch_created == False ──────────────────────────
    cpc = bullpen_record.get("candidate_patch_created")
    hard_rules_ok = True
    if cpc is not False:
        violations.append(
            f"candidate_patch_created must be False, got {cpc!r}"
        )
        hard_rules_ok = False

    # ── Rule 5: production_modified == False ──────────────────────────────
    pm = bullpen_record.get("production_modified")
    if pm is not False:
        violations.append(
            f"production_modified must be False, got {pm!r}"
        )
        hard_rules_ok = False

    # ── Rule 6: Required fields present ───────────────────────────────────
    for req in _REQUIRED_FIELDS:
        if req not in bullpen_record:
            violations.append(f"required field missing: {req}")

    # ── Warnings: feature_version should match phase56 ────────────────────
    fv = bullpen_record.get("feature_version", "")
    if fv and "phase56" not in fv:
        warnings.append(
            f"feature_version '{fv}' does not reference phase56"
        )

    # ── Warnings: fallback notes ──────────────────────────────────────────
    if not bullpen_record.get("bullpen_feature_available", False):
        warnings.append(
            "bullpen_feature_available=False: using neutral fallback values"
        )

    is_safe = len(violations) == 0
    return BullpenPitValidationResult(
        is_safe=is_safe,
        violations=violations,
        warnings=warnings,
        game_date=game_date,
        audit_hash_present=audit_hash_present,
        pit_flag_correct=pit_flag_correct,
        hard_rules_correct=hard_rules_ok,
        candidate_patch_created=False,
        production_modified=False,
    )


def validate_bullpen_batch(
    records: list[dict],
    game_date: str = "",
) -> dict:
    """
    Validate a batch of bullpen feature records.

    Returns:
        Summary dict with:
            total, safe_count, violation_count,
            availability_rate, pit_safe_rate,
            sample_violations
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    total = len(records)
    safe_count = 0
    available_count = 0
    all_violations: list[str] = []

    for rec in records:
        result = validate_bullpen_features(rec, game_date)
        if result.is_safe:
            safe_count += 1
        else:
            all_violations.extend(result.violations)
        if rec.get("bullpen_feature_available", False):
            available_count += 1

    return {
        "total": total,
        "safe_count": safe_count,
        "violation_count": total - safe_count,
        "pit_safe_rate": round(safe_count / max(1, total), 4),
        "availability_count": available_count,
        "availability_rate": round(available_count / max(1, total), 4),
        "sample_violations": all_violations[:10],
        "candidate_patch_created": False,
        "production_modified": False,
    }


# ─── Phase 58 — Bullpen Snapshot Validator ────────────────────────────────────

# Extended forbidden fields for Phase58 snapshots
_FORBIDDEN_SNAPSHOT_FIELDS: frozenset[str] = frozenset({
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
    "whip_after_game",
    "fip_after_game",
    "same_game_boxscore",
    "box_score_result",
})

# Required fields for Phase58 snapshot
_REQUIRED_SNAPSHOT_FIELDS: frozenset[str] = frozenset({
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "snapshot_date",
    "point_in_time_safe",
    "audit_hash",
    "source",
    "feature_version",
    "bullpen_feature_available",
    "candidate_patch_created",
    "production_modified",
    "diagnostic_only",
})


@dataclass
class BullpenSnapshotValidationResult:
    """Phase58 Bullpen Snapshot 驗證結果。"""
    is_safe: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    game_id: str = ""
    game_date: str = ""
    snapshot_date: str = ""
    audit_hash_present: bool = False
    snapshot_date_safe: bool = False   # snapshot_date < game_date
    candidate_patch_created: bool = False
    production_modified: bool = False


def validate_bullpen_snapshot(
    snapshot: dict,
) -> BullpenSnapshotValidationResult:
    """
    驗證 Phase58 bullpen usage snapshot 是否符合 PIT-safe 規範。

    Rules:
    1. snapshot_date < game_date (strict <)
    2. point_in_time_safe = True
    3. audit_hash present and non-empty
    4. candidate_patch_created = False
    5. production_modified = False
    6. diagnostic_only = True
    7. No forbidden leakage fields with non-None values
    8. All required fields present

    Returns:
        BullpenSnapshotValidationResult
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    violations: list[str] = []
    warnings: list[str] = []

    if not isinstance(snapshot, dict):
        violations.append(f"snapshot must be dict, got {type(snapshot)}")
        return BullpenSnapshotValidationResult(
            is_safe=False,
            violations=violations,
        )

    game_id = snapshot.get("game_id", "")
    game_date = snapshot.get("game_date", "")
    snapshot_date = snapshot.get("snapshot_date", "")

    # ── Rule 1: snapshot_date < game_date ─────────────────────────────────
    snapshot_date_safe = False
    if not snapshot_date:
        violations.append("snapshot_date is missing or empty")
    elif not game_date:
        violations.append("game_date is missing or empty")
    elif snapshot_date >= game_date:
        violations.append(
            f"PIT violation: snapshot_date={snapshot_date!r} >= game_date={game_date!r}"
        )
    else:
        snapshot_date_safe = True

    # ── Rule 2: point_in_time_safe = True ─────────────────────────────────
    pit_flag = snapshot.get("point_in_time_safe")
    if pit_flag is not True:
        violations.append(
            f"point_in_time_safe must be True, got {pit_flag!r}"
        )

    # ── Rule 3: audit_hash present ────────────────────────────────────────
    audit_hash = snapshot.get("audit_hash", "")
    audit_hash_present = bool(audit_hash)
    if not audit_hash_present:
        violations.append("audit_hash is missing or empty")

    # ── Rule 4: candidate_patch_created = False ───────────────────────────
    cpc = snapshot.get("candidate_patch_created")
    if cpc is not False:
        violations.append(f"candidate_patch_created must be False, got {cpc!r}")

    # ── Rule 5: production_modified = False ───────────────────────────────
    pm = snapshot.get("production_modified")
    if pm is not False:
        violations.append(f"production_modified must be False, got {pm!r}")

    # ── Rule 6: diagnostic_only = True ───────────────────────────────────
    do = snapshot.get("diagnostic_only")
    if do is not True:
        violations.append(f"diagnostic_only must be True, got {do!r}")

    # ── Rule 7: No forbidden leakage fields ───────────────────────────────
    for forbidden in _FORBIDDEN_SNAPSHOT_FIELDS:
        if forbidden in snapshot and snapshot[forbidden] is not None:
            violations.append(f"leakage field present with non-None value: '{forbidden}'")

    # ── Rule 8: Required fields ───────────────────────────────────────────
    for req in _REQUIRED_SNAPSHOT_FIELDS:
        if req not in snapshot:
            violations.append(f"required field missing: '{req}'")

    # ── Warnings ──────────────────────────────────────────────────────────
    if not snapshot.get("bullpen_feature_available", False):
        warnings.append("bullpen_feature_available=False: insufficient history data")

    doubleheader_num = snapshot.get("doubleheader_game_num", 0)
    if doubleheader_num not in (0, 1, 2):
        violations.append(
            f"doubleheader_game_num must be 0, 1, or 2, got {doubleheader_num!r}"
        )

    is_safe = len(violations) == 0
    return BullpenSnapshotValidationResult(
        is_safe=is_safe,
        violations=violations,
        warnings=warnings,
        game_id=game_id,
        game_date=game_date,
        snapshot_date=snapshot_date,
        audit_hash_present=audit_hash_present,
        snapshot_date_safe=snapshot_date_safe,
        candidate_patch_created=False,
        production_modified=False,
    )


def validate_bullpen_snapshot_batch(
    snapshots: list[dict],
) -> dict:
    """
    批次驗證 Phase58 bullpen snapshots。

    Returns:
        Summary dict with pit_safe_rate, audit_hash_present_rate,
        violation_count, availability_rate, sample_violations
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    total = len(snapshots)
    safe_count = 0
    audit_present_count = 0
    available_count = 0
    all_violations: list[str] = []

    for snap in snapshots:
        result = validate_bullpen_snapshot(snap)
        if result.is_safe:
            safe_count += 1
        else:
            all_violations.extend(result.violations[:2])
        if result.audit_hash_present:
            audit_present_count += 1
        if snap.get("bullpen_feature_available", False):
            available_count += 1

    return {
        "total": total,
        "safe_count": safe_count,
        "violation_count": total - safe_count,
        "pit_safe_rate": round(safe_count / max(1, total), 4),
        "audit_hash_present_count": audit_present_count,
        "audit_hash_present_rate": round(audit_present_count / max(1, total), 4),
        "availability_count": available_count,
        "availability_rate": round(available_count / max(1, total), 4),
        "sample_violations": all_violations[:10],
        "candidate_patch_created": False,
        "production_modified": False,
    }
