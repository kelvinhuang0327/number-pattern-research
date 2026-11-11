"""
tests/test_phase58_bullpen_usage_pipeline.py
============================================
Phase 58 — Bullpen Usage Pipeline Tests

覆蓋（18+ tests）：
  T-01  BullpenUsageInputBundle loader 可讀取 baseline rows
  T-02  Team history can be built from asplayed schedule
  T-03  Relief appearance parser fallback does not use forbidden leakage fields
  T-04  Snapshot date < game_date (PIT rule)
  T-05  PIT validator rejects forbidden leakage fields
  T-06  PIT validator rejects snapshot_date >= game_date
  T-07  Bullpen usage snapshot can be built for multiple rows
  T-08  Snapshot audit_hash is present and non-empty
  T-09  bullpen_feature_available = False when team has no prior history
  T-10  bullpen_feature_available = True when team has >= 7d history
  T-11  Context injection preserves SP / p0 features
  T-12  Context injection adds phase58_feature_version
  T-13  feature_version = "phase58_bullpen_context_v1" after injection
  T-14  Injection max adjustment <= 0.015
  T-15  unavailable → adjustment = 0
  T-16  candidate_patch_created = False in all modules
  T-17  production_modified = False in all modules
  T-18  diagnostic_only = True in all modules
  T-19  Gate cannot output PATCH_GATE_RECHECK (invalid gate)
  T-20  Gate = DATA_GAP_REMAINS when availability < 80%
  T-21  Valid gates are exactly 4
  T-22  Batch PIT validator returns audit_hash_present_rate
  T-23  Phase58 evaluation result hard rules invariants
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Module under test ─────────────────────────────────────────────────────────
from data.mlb_bullpen_usage_loader import (
    CANDIDATE_PATCH_CREATED as LOADER_CPC,
    PRODUCTION_MODIFIED as LOADER_PM,
    DIAGNOSTIC_ONLY as LOADER_DO,
    ScheduleGameRecord,
    BullpenUsageInputBundle,
    _build_team_game_history,
)

from wbc_backend.features.mlb_relief_appearance_parser import (
    CANDIDATE_PATCH_CREATED as PARSER_CPC,
    PRODUCTION_MODIFIED as PARSER_PM,
    ReliefAppearance,
    parse_relief_appearances,
    _FORBIDDEN_INPUT_FIELDS as _LEAKAGE_FIELDS,
    _PROXY_PITCHER_ID_OFFSET,
)

from wbc_backend.features.mlb_bullpen_usage_snapshot import (
    CANDIDATE_PATCH_CREATED as SNAP_CPC,
    PRODUCTION_MODIFIED as SNAP_PM,
    DIAGNOSTIC_ONLY as SNAP_DO,
    FEATURE_VERSION,
    build_bullpen_snapshot_for_game,
    build_bullpen_snapshots_batch,
    _pit_safe_history,
    _games_in_window,
    _compute_snapshot_audit_hash,
    _PROXY_BULLPEN_OUTS_PER_GAME as PROXY_BULLPEN_OUTS_PER_GAME,
    _LEAGUE_AVG_ERA as LEAGUE_AVG_ERA,
    _LEAGUE_AVG_FIP as LEAGUE_AVG_FIP,
)

from wbc_backend.features.mlb_bullpen_pit_validator import (
    CANDIDATE_PATCH_CREATED as PIT_CPC,
    PRODUCTION_MODIFIED as PIT_PM,
    validate_bullpen_snapshot,
    validate_bullpen_snapshot_batch,
    BullpenSnapshotValidationResult,
    _FORBIDDEN_SNAPSHOT_FIELDS,
)

from wbc_backend.features.mlb_bullpen_feature_injection import (
    CANDIDATE_PATCH_CREATED as ADJ_CPC,
    PRODUCTION_MODIFIED as ADJ_PM,
    DIAGNOSTIC_ONLY as ADJ_DO,
    apply_bullpen_adjustment,
    _MAX_TOTAL_ADJUSTMENT as MAX_TOTAL_ADJUSTMENT,
)

from orchestrator.phase58_bullpen_usage_evaluation import (
    CANDIDATE_PATCH_CREATED as EVAL_CPC,
    PRODUCTION_MODIFIED as EVAL_PM,
    DIAGNOSTIC_ONLY as EVAL_DO,
    DATA_GAP_REMAINS,
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
    BULLPEN_FEATURE_NOT_EFFECTIVE,
    COLLECT_MORE_DATA,
    _VALID_GATES,
    Phase58EvaluationResult,
    BullpenAvailabilitySummary58,
    MetricsSnapshot58,
    _determine_gate,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_schedule_record(
    game_id: str = "G001",
    game_date: str = "2025-04-10",
    home_team: str = "NYY",
    away_team: str = "BOS",
    status: str = "Final",
    entry_date: str = "2025-04-10",
) -> ScheduleGameRecord:
    return ScheduleGameRecord(
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        status=status,
    )


def _make_team_history(team: str, game_dates: list[str]) -> list[ScheduleGameRecord]:
    """Build a fake team game history as ScheduleGameRecord objects."""
    history = []
    for gd in game_dates:
        history.append(ScheduleGameRecord(
            game_date=gd,
            home_team=team,
            away_team="OPP",
            status="Final",
        ))
    return history


def _make_baseline_row(
    game_id: str = "G001",
    game_date: str = "2025-04-15",
    home_team: str = "NYY",
    away_team: str = "BOS",
    model_home_prob: float = 0.55,
    market_home_prob_no_vig: float = 0.52,
    home_win: int = 1,
) -> dict:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "home_win": home_win,
        "season": 2025,
    }


def _make_valid_snapshot(
    game_id: str = "G001",
    game_date: str = "2025-04-15",
    snapshot_date: str = "2025-04-14",
    available: bool = True,
) -> dict:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "home_team": "NYY",
        "away_team": "BOS",
        "snapshot_date": snapshot_date,
        "point_in_time_safe": True,
        "audit_hash": "abc123def456",
        "source": "schedule_proxy_fallback",
        "feature_version": FEATURE_VERSION,
        "bullpen_feature_available": available,
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
        "doubleheader_game_num": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# T-01: Loader — BullpenUsageInputBundle 基本結構
# ═══════════════════════════════════════════════════════════════════════════════

class TestBullpenUsageLoader:

    def test_t01_schedule_record_has_required_fields(self):
        """T-01: ScheduleGameRecord 有所有必要欄位"""
        rec = _make_schedule_record()
        assert rec.game_date == "2025-04-10"
        assert rec.home_team == "NYY"
        assert rec.away_team == "BOS"
        assert rec.status == "Final"
        assert rec.is_completed is True

    def test_t02_team_history_built_from_schedule(self):
        """T-02: Team game history 可從 asplayed records 建立"""
        records = [
            _make_schedule_record("G001", "2025-04-01", "NYY", "BOS", "Final", "2025-04-01"),
            _make_schedule_record("G002", "2025-04-03", "NYY", "LAD", "Final", "2025-04-03"),
            _make_schedule_record("G003", "2025-04-05", "BOS", "NYY", "Final", "2025-04-05"),
        ]
        history = _build_team_game_history(records)
        assert "NYY" in history
        assert "BOS" in history
        # NYY appears in G001 (home), G002 (home), G003 (away) → 3 entries
        assert len(history["NYY"]) == 3
    def test_loader_constants(self):
        """Loader module 的 hard constants 正確"""
        assert LOADER_CPC is False
        assert LOADER_PM is False
        assert LOADER_DO is True


# ═══════════════════════════════════════════════════════════════════════════════
# T-03: Relief Appearance Parser — 不使用 leakage fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestReliefAppearanceParser:

    def test_t03_parser_forbidden_fields_defined(self):
        """T-03: Parser 定義了 leakage fields 列表"""
        assert "home_win" in _LEAKAGE_FIELDS
        assert "final_score" in _LEAKAGE_FIELDS
        assert "box_score" in _LEAKAGE_FIELDS

    def test_parser_proxy_appearances_no_leakage(self):
        """Parser proxy 輸出不包含 leakage fields"""
        game_data = {}
        appearances = parse_relief_appearances(
            game_data=game_data,
            game_id="G001",
            game_date="2025-04-10",
            home_team="NYY",
            away_team="BOS",
        )
        for app in appearances:
            app_dict = vars(app) if hasattr(app, "__dict__") else {}
            for forbidden in _LEAKAGE_FIELDS:
                assert forbidden not in app_dict, f"Leakage field {forbidden!r} in appearance"

    def test_parser_proxy_appearances_point_in_time_safe(self):
        """Parser proxy 的每個 ReliefAppearance 都標記 point_in_time_safe=True"""
        appearances = parse_relief_appearances(
            game_data={},
            game_id="G001",
            game_date="2025-04-10",
            home_team="NYY",
            away_team="BOS",
        )
        for app in appearances:
            assert app.point_in_time_safe is True
            assert app.estimated is True

    def test_parser_constants(self):
        assert PARSER_CPC is False
        assert PARSER_PM is False


# ═══════════════════════════════════════════════════════════════════════════════
# T-04 ~ T-10: Snapshot Builder
# ═══════════════════════════════════════════════════════════════════════════════

class TestBullpenUsageSnapshot:

    def _make_history_for_team(self, team: str, n_days: int = 10) -> list[ScheduleGameRecord]:
        """建立過去 n_days 天的 team history"""
        base_date = date(2025, 4, 14)
        history = []
        for i in range(n_days):
            gd = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
            history.append(ScheduleGameRecord(
                game_date=gd,
                home_team=team,
                away_team="OPP",
                status="Final",
            ))
        return history

    def test_t04_snapshot_date_before_game_date(self):
        """T-04: snapshot_date < game_date (strict PIT rule)"""
        row = _make_baseline_row(game_date="2025-04-15")
        home_history = self._make_history_for_team("NYY")
        away_history = self._make_history_for_team("BOS")
        team_history = {"NYY": home_history, "BOS": away_history}

        snapshot = build_bullpen_snapshot_for_game(row, team_history)
        assert snapshot["snapshot_date"] < snapshot["game_date"], (
            f"PIT violation: snapshot_date={snapshot['snapshot_date']} >= game_date={snapshot['game_date']}"
        )

    def test_t08_snapshot_audit_hash_present(self):
        """T-08: audit_hash 存在且非空"""
        row = _make_baseline_row(game_date="2025-04-15")
        team_history = {"NYY": self._make_history_for_team("NYY"), "BOS": self._make_history_for_team("BOS")}
        snapshot = build_bullpen_snapshot_for_game(row, team_history)
        assert snapshot.get("audit_hash", "") != "", "audit_hash 不應為空"

    def test_t09_no_prior_history_bullpen_feature_unavailable(self):
        """T-09: 沒有歷史資料時 bullpen_feature_available = False"""
        row = _make_baseline_row(game_date="2025-04-01")
        team_history: dict = {}
        snapshot = build_bullpen_snapshot_for_game(row, team_history)
        assert snapshot["bullpen_feature_available"] is False
        assert snapshot["workload_available"] is False

    def test_t10_sufficient_history_bullpen_feature_available(self):
        """T-10: 有 7+ 天歷史資料時 bullpen_feature_available = True"""
        row = _make_baseline_row(game_date="2025-04-15")
        team_history = {
            "NYY": self._make_history_for_team("NYY", n_days=8),
            "BOS": self._make_history_for_team("BOS", n_days=8),
        }
        snapshot = build_bullpen_snapshot_for_game(row, team_history)
        assert snapshot["bullpen_feature_available"] is True
        assert snapshot["workload_available"] is True

    def test_snapshot_point_in_time_safe(self):
        """Snapshot 的 point_in_time_safe = True"""
        row = _make_baseline_row(game_date="2025-04-15")
        team_history = {"NYY": self._make_history_for_team("NYY"), "BOS": self._make_history_for_team("BOS")}
        snapshot = build_bullpen_snapshot_for_game(row, team_history)
        assert snapshot["point_in_time_safe"] is True

    def test_snapshot_batch_row_count(self):
        """T-07: build_bullpen_snapshots_batch 產生正確數量的 snapshots"""
        rows = [
            _make_baseline_row("G001", "2025-04-15", "NYY", "BOS"),
            _make_baseline_row("G002", "2025-04-16", "LAD", "SFG"),
            _make_baseline_row("G003", "2025-04-17", "NYY", "LAD"),
        ]
        team_history = {
            "NYY": _make_team_history("NYY", ["2025-04-01", "2025-04-03", "2025-04-05", "2025-04-07", "2025-04-09", "2025-04-11", "2025-04-13", "2025-04-14"]),
            "BOS": _make_team_history("BOS", ["2025-04-01", "2025-04-03", "2025-04-05", "2025-04-07", "2025-04-09", "2025-04-11", "2025-04-13", "2025-04-14"]),
            "LAD": _make_team_history("LAD", ["2025-04-01", "2025-04-03", "2025-04-05", "2025-04-07", "2025-04-09", "2025-04-11", "2025-04-13", "2025-04-14"]),
            "SFG": _make_team_history("SFG", ["2025-04-01"]),
        }
        snapshots = build_bullpen_snapshots_batch(rows, team_history)
        assert len(snapshots) == 3

    def test_snapshot_hard_constants(self):
        assert SNAP_CPC is False
        assert SNAP_PM is False
        assert SNAP_DO is True


# ═══════════════════════════════════════════════════════════════════════════════
# T-05 ~ T-06: PIT Validator v2
# ═══════════════════════════════════════════════════════════════════════════════

class TestBullpenSnapshotValidator:

    def test_t05_validator_rejects_forbidden_field(self):
        """T-05: PIT validator 拒絕含 forbidden leakage fields 的 snapshot"""
        snap = _make_valid_snapshot()
        snap["same_game_boxscore"] = {"innings": 9}
        result = validate_bullpen_snapshot(snap)
        assert not result.is_safe
        assert any("same_game_boxscore" in v for v in result.violations)

    def test_t06_validator_rejects_snapshot_date_not_before_game_date(self):
        """T-06: snapshot_date >= game_date 應觸發違規"""
        snap = _make_valid_snapshot(
            game_date="2025-04-15",
            snapshot_date="2025-04-15",  # 同一天 — 違規
        )
        result = validate_bullpen_snapshot(snap)
        assert not result.is_safe
        assert any("PIT violation" in v for v in result.violations)

    def test_validator_passes_clean_snapshot(self):
        """有效的 snapshot 通過 PIT validation"""
        snap = _make_valid_snapshot()
        result = validate_bullpen_snapshot(snap)
        assert result.is_safe, f"Violations: {result.violations}"
        assert result.audit_hash_present is True
        assert result.snapshot_date_safe is True

    def test_validator_rejects_missing_audit_hash(self):
        """audit_hash 缺失時應拒絕"""
        snap = _make_valid_snapshot()
        snap["audit_hash"] = ""
        result = validate_bullpen_snapshot(snap)
        assert not result.is_safe

    def test_validator_rejects_candidate_patch_true(self):
        """candidate_patch_created=True 應被拒絕"""
        snap = _make_valid_snapshot()
        snap["candidate_patch_created"] = True
        result = validate_bullpen_snapshot(snap)
        assert not result.is_safe
        assert any("candidate_patch_created" in v for v in result.violations)

    def test_validator_rejects_production_modified_true(self):
        """production_modified=True 應被拒絕"""
        snap = _make_valid_snapshot()
        snap["production_modified"] = True
        result = validate_bullpen_snapshot(snap)
        assert not result.is_safe
        assert any("production_modified" in v for v in result.violations)

    def test_t22_batch_validator_returns_audit_hash_rate(self):
        """T-22: 批次 validator 回傳 audit_hash_present_rate"""
        snaps = [_make_valid_snapshot(f"G{i:03d}", f"2025-04-{15+i:02d}", f"2025-04-{14+i:02d}") for i in range(5)]
        result = validate_bullpen_snapshot_batch(snaps)
        assert "audit_hash_present_rate" in result
        assert result["audit_hash_present_rate"] == 1.0
        assert result["pit_safe_rate"] == 1.0
        assert result["candidate_patch_created"] is False
        assert result["production_modified"] is False

    def test_validator_pit_constants(self):
        assert PIT_CPC is False
        assert PIT_PM is False


# ═══════════════════════════════════════════════════════════════════════════════
# T-11 ~ T-13: Context Injection
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextInjection:

    def _make_context_row_with_sp(
        self,
        game_id: str = "G001",
        game_date: str = "2025-04-15",
    ) -> dict:
        return {
            "game_id": game_id,
            "game_date": game_date,
            "home_team": "NYY",
            "away_team": "BOS",
            "model_home_prob": 0.55,
            "market_home_prob_no_vig": 0.52,
            "home_win": 1,
            # SP features — 不應被改動
            "home_sp_era": 3.20,
            "away_sp_era": 4.10,
            "home_sp_whip": 1.15,
            # p0 features — 不應被改動
            "home_win_pct": 0.580,
            "away_win_pct": 0.490,
        }

    def _make_usage_row(self, game_id: str = "G001") -> dict:
        return {
            "game_id": game_id,
            "game_date": "2025-04-15",
            "home_team": "NYY",
            "away_team": "BOS",
            "home_bullpen_outs_7d": 63.0,
            "away_bullpen_outs_7d": 54.0,
            "bullpen_feature_available": True,
            "workload_available": True,
            "leverage_available": False,
            "performance_proxy_available": False,
            "source": "schedule_proxy_fallback",
            "audit_hash": "abc123",
            "feature_version": FEATURE_VERSION,
            "snapshot_date": "2025-04-14",
            "point_in_time_safe": True,
        }

    def test_t11_injection_preserves_sp_features(self):
        """T-11: Context injection 保留 SP / p0 features"""
        from scripts.run_phase58_inject_bullpen_usage_to_phase56 import (
            _inject_bullpen_to_row,
        )
        context_row = self._make_context_row_with_sp()
        usage_row = self._make_usage_row()

        injected = _inject_bullpen_to_row(context_row, usage_row)

        assert injected["home_sp_era"] == 3.20, "SP ERA should be preserved"
        assert injected["away_sp_era"] == 4.10, "SP ERA should be preserved"
        assert injected["home_sp_whip"] == 1.15, "SP WHIP should be preserved"
        assert injected["home_win_pct"] == 0.580, "p0 win_pct should be preserved"

    def test_t12_injection_adds_phase58_version(self):
        """T-12: Context injection adds phase58_feature_version"""
        from scripts.run_phase58_inject_bullpen_usage_to_phase56 import (
            _inject_bullpen_to_row,
        )
        context_row = self._make_context_row_with_sp()
        usage_row = self._make_usage_row()

        injected = _inject_bullpen_to_row(context_row, usage_row)
        assert "phase58_feature_version" in injected

    def test_t13_injection_feature_version_correct(self):
        """T-13: phase58_feature_version = 'phase58_bullpen_context_v1'"""
        from scripts.run_phase58_inject_bullpen_usage_to_phase56 import (
            _inject_bullpen_to_row,
            FEATURE_VERSION as CTX_FEATURE_VERSION,
        )
        context_row = self._make_context_row_with_sp()
        usage_row = self._make_usage_row()

        injected = _inject_bullpen_to_row(context_row, usage_row)
        assert injected["phase58_feature_version"] == CTX_FEATURE_VERSION

    def test_injection_preserves_home_win(self):
        """home_win 不可被 injection 改變"""
        from scripts.run_phase58_inject_bullpen_usage_to_phase56 import (
            _inject_bullpen_to_row,
        )
        context_row = self._make_context_row_with_sp()
        usage_row = self._make_usage_row()
        usage_row["home_win"] = 0  # 應被忽略

        injected = _inject_bullpen_to_row(context_row, usage_row)
        assert injected["home_win"] == 1, "home_win must not be overwritten"


# ═══════════════════════════════════════════════════════════════════════════════
# T-14 ~ T-15: Feature Injection
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureInjection:

    def _make_bullpen_features_available(self) -> dict:
        return {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 0.3,   # away more fatigued
            "bullpen_recent_era_delta": 0.5,
            "leverage_usage_delta": 0.0,
            "home_bullpen_fatigue_3d": 0.2,
            "home_bullpen_fatigue_7d": 0.15,
            "home_reliever_b2b_count": 1,
            "home_bullpen_recent_era_proxy": 4.10,
            "home_late_game_leverage_usage_proxy": 0.0,
            "away_bullpen_fatigue_3d": 0.5,
            "away_bullpen_fatigue_7d": 0.4,
            "away_reliever_b2b_count": 2,
            "away_bullpen_recent_era_proxy": 4.10,
            "away_late_game_leverage_usage_proxy": 0.0,
            "bullpen_fatigue_delta_7d": 0.25,
            "bullpen_feature_source": "schedule_proxy_fallback",
            "point_in_time_safe": True,
            "fallback_reason": "",
            "feature_version": FEATURE_VERSION,
            "audit_hash": "abc123",
            "candidate_patch_created": False,
            "production_modified": False,
            "diagnostic_only": True,
        }

    def _make_bullpen_features_unavailable(self) -> dict:
        return {
            "bullpen_feature_available": False,
            "bullpen_fatigue_delta_3d": 0.0,
            "bullpen_recent_era_delta": 0.0,
            "leverage_usage_delta": 0.0,
            "home_bullpen_fatigue_3d": 0.0,
            "home_bullpen_fatigue_7d": 0.0,
            "home_reliever_b2b_count": 0,
            "home_bullpen_recent_era_proxy": 4.10,
            "home_late_game_leverage_usage_proxy": 0.0,
            "away_bullpen_fatigue_3d": 0.0,
            "away_bullpen_fatigue_7d": 0.0,
            "away_reliever_b2b_count": 0,
            "away_bullpen_recent_era_proxy": 4.10,
            "away_late_game_leverage_usage_proxy": 0.0,
            "bullpen_fatigue_delta_7d": 0.0,
            "bullpen_feature_source": "schedule_proxy_fallback",
            "point_in_time_safe": True,
            "fallback_reason": "insufficient_history",
            "feature_version": FEATURE_VERSION,
            "audit_hash": "abc123",
            "candidate_patch_created": False,
            "production_modified": False,
            "diagnostic_only": True,
        }

    def test_t14_max_adjustment_within_limit(self):
        """T-14: 注入調整量 <= 0.015"""
        features = self._make_bullpen_features_available()
        result = apply_bullpen_adjustment(0.55, features)
        assert abs(result.bullpen_adjustment) <= MAX_TOTAL_ADJUSTMENT, (
            f"Adjustment {result.bullpen_adjustment:.6f} exceeds limit {MAX_TOTAL_ADJUSTMENT}"
        )

    def test_t15_unavailable_gives_zero_adjustment(self):
        """T-15: bullpen_feature_available=False → adjustment = 0"""
        features = self._make_bullpen_features_unavailable()
        result = apply_bullpen_adjustment(0.55, features)
        assert abs(result.bullpen_adjustment) < 1e-9, (
            f"Expected zero adjustment, got {result.bullpen_adjustment}"
        )

    def test_adjustment_preserves_probability_bounds(self):
        """調整後機率在 [0.01, 0.99] 之間"""
        features = self._make_bullpen_features_available()
        for base_prob in [0.01, 0.10, 0.50, 0.90, 0.99]:
            result = apply_bullpen_adjustment(base_prob, features)
            assert 0.01 <= result.adjusted_model_home_prob <= 0.99


# ═══════════════════════════════════════════════════════════════════════════════
# T-16 ~ T-18: Hard Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardConstants:

    def test_t16_candidate_patch_created_false(self):
        """T-16: candidate_patch_created = False 在所有模組中"""
        assert LOADER_CPC is False
        assert PARSER_CPC is False
        assert SNAP_CPC is False
        assert PIT_CPC is False
        assert ADJ_CPC is False
        assert EVAL_CPC is False

    def test_t17_production_modified_false(self):
        """T-17: production_modified = False 在所有模組中"""
        assert LOADER_PM is False
        assert PARSER_PM is False
        assert SNAP_PM is False
        assert PIT_PM is False
        assert ADJ_PM is False
        assert EVAL_PM is False

    def test_t18_diagnostic_only_true(self):
        """T-18: diagnostic_only = True 在所有支援的模組中"""
        assert LOADER_DO is True
        assert SNAP_DO is True
        assert ADJ_DO is True
        assert EVAL_DO is True


# ═══════════════════════════════════════════════════════════════════════════════
# T-19 ~ T-21: Gate Logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateLogic:

    def test_t19_gate_cannot_be_patch_gate_recheck(self):
        """T-19: 'PATCH_GATE_RECHECK' 不是合法的 gate"""
        assert "PATCH_GATE_RECHECK" not in _VALID_GATES

    def test_t20_gate_data_gap_remains_when_availability_low(self):
        """T-20: availability < 80% → DATA_GAP_REMAINS"""
        avail = BullpenAvailabilitySummary58(
            total_rows=100,
            available_count=70,
            availability_rate=0.70,  # below 80% threshold
        )
        baseline_m = MetricsSnapshot58("baseline", n=100, brier=0.24, bss_vs_market=0.01, ece=0.03)
        phase58_m = MetricsSnapshot58("phase58", n=100, brier=0.23, bss_vs_market=0.02, ece=0.02)

        gate, rationale = _determine_gate(avail, baseline_m, phase58_m, [], 5, 4)
        assert gate == DATA_GAP_REMAINS

    def test_t21_valid_gates_exactly_four(self):
        """T-21: _VALID_GATES 恰好包含 4 個合法 gate"""
        assert len(_VALID_GATES) == 4
        assert DATA_GAP_REMAINS in _VALID_GATES
        assert BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY in _VALID_GATES
        assert BULLPEN_FEATURE_NOT_EFFECTIVE in _VALID_GATES
        assert COLLECT_MORE_DATA in _VALID_GATES

    def test_gate_not_effective_when_no_improvement(self):
        """availability >= 80% 但無顯著改善 → NOT_EFFECTIVE"""
        avail = BullpenAvailabilitySummary58(
            total_rows=100,
            available_count=90,
            availability_rate=0.90,  # passes 80% threshold
        )
        baseline_m = MetricsSnapshot58("baseline", n=200, brier=0.24, bss_vs_market=0.01, ece=0.03)
        phase58_m = MetricsSnapshot58("phase58", n=200, brier=0.24, bss_vs_market=0.01, ece=0.03)

        gate, rationale = _determine_gate(avail, baseline_m, phase58_m, [], 5, 5)
        assert gate in {BULLPEN_FEATURE_NOT_EFFECTIVE, COLLECT_MORE_DATA}


# ═══════════════════════════════════════════════════════════════════════════════
# T-23: Evaluation Result Invariants
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvaluationResultInvariants:

    def test_t23_evaluation_result_hard_rules(self):
        """T-23: Phase58EvaluationResult 的 hard rules 不可違反"""
        result = Phase58EvaluationResult(
            gate_recommendation=DATA_GAP_REMAINS,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True
        assert result.gate_recommendation in _VALID_GATES

    def test_evaluation_result_rejects_invalid_gate(self):
        """無效 gate 應觸發 AssertionError"""
        with pytest.raises(AssertionError):
            Phase58EvaluationResult(
                gate_recommendation="INVALID_GATE",
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=True,
            )

    def test_evaluation_result_rejects_candidate_patch_true(self):
        """candidate_patch_created=True 應觸發 AssertionError"""
        with pytest.raises(AssertionError):
            Phase58EvaluationResult(
                gate_recommendation=DATA_GAP_REMAINS,
                candidate_patch_created=True,
                production_modified=False,
                diagnostic_only=True,
            )

    def test_evaluation_result_to_dict(self):
        """to_dict() 可序列化"""
        result = Phase58EvaluationResult(
            gate_recommendation=DATA_GAP_REMAINS,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )
        d = result.to_dict()
        assert "gate_recommendation" in d
        assert d["candidate_patch_created"] is False
        assert d["production_modified"] is False
        # Should be JSON serializable
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 0
