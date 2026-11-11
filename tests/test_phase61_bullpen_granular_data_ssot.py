"""
tests/test_phase61_bullpen_granular_data_ssot.py
================================================
Phase 61 — Bullpen Granular Data SSOT Tests (gate = SOURCE_SELECTION_REQUIRED)

測試範圍：
  - TestSafetyConstants:         safety flags, schema version, ALPHA 不可修改
  - TestPITSafeDateWindow:       PIT 視窗定義正確性（game_date > snapshot_date）
  - TestSchemaCompleteness:      所有必要特徵已宣告；DATA_LIMITED 正確標記
  - TestMissingDataHandling:     缺資料 → DATA_LIMITED，不得 fallback neutral
  - TestNoNeutralFallbackMasquerade: DATA_LIMITED 特徵 value 必須為 None
  - TestSSOTSingleSourceGuard:   SSOT 所有權 guard 運作正確
  - TestSpecialGameHandlingPolicy: 雙重賽、延賽、Opener 政策有文字記錄
  - TestNoProductionPatch:       CANDIDATE_PATCH_CREATED=False / PRODUCTION_MODIFIED=False
  - TestEndToEnd:                build_granular_record end-to-end 整合

Gate: SOURCE_SELECTION_REQUIRED
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from wbc_backend.features.mlb_bullpen_granular_ssot import (
    # Safety constants
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    SSOT_SCHEMA_VERSION,
    # Enum
    FeatureAvailability,
    # Dataclasses
    BullpenGranularRecord,
    GranularFeatureSlot,
    SpecialGameHandlingPolicy,
    # PIT windows
    FEATURE_PIT_WINDOWS,
    # Guard functions
    assert_not_forbidden_field,
    assert_no_neutral_fallback,
    assert_ssot_ownership,
    get_ssot_owner,
    list_available_features,
    list_data_limited_features,
    # Builder
    build_granular_record,
    # SSOT registry
    _SSOT_REGISTERED_MODULES,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAME_DATE = "2025-05-06"
_GAME_ID = "MLB-20250506-LAA-LAD"
_HOME = "Los Angeles Dodgers"
_AWAY = "Los Angeles Angels"


def _build_default() -> BullpenGranularRecord:
    """Build a standard valid record for testing."""
    return build_granular_record(
        game_id=_GAME_ID,
        game_date=_GAME_DATE,
        team=_HOME,
        side="home",
        bullpen_3d_ip=5.667,
        fav_3d_ip=5.667,
        dog_3d_ip=3.333,
        home_3d_ip=5.667,
        away_3d_ip=3.333,
        source="mlb_stats_api_boxscore",
    )


def _build_no_3d() -> BullpenGranularRecord:
    """Build a record where 3d data is unavailable."""
    return build_granular_record(
        game_id=_GAME_ID,
        game_date=_GAME_DATE,
        team=_HOME,
        side="home",
        bullpen_3d_ip=None,
        fav_3d_ip=None,
        dog_3d_ip=None,
        home_3d_ip=None,
        away_3d_ip=None,
        source="mlb_stats_api_boxscore",
    )


# ---------------------------------------------------------------------------
# Class 1: TestSafetyConstants
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    """Safety flags must be frozen and not changeable."""

    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_ssot_schema_version_contains_phase61(self):
        assert "phase61" in SSOT_SCHEMA_VERSION

    def test_ssot_schema_version_is_string(self):
        assert isinstance(SSOT_SCHEMA_VERSION, str)

    def test_ssot_schema_version_nonempty(self):
        assert len(SSOT_SCHEMA_VERSION) > 0

    def test_alpha_modified_type_is_bool(self):
        assert isinstance(ALPHA_MODIFIED, bool)

    def test_candidate_patch_created_type_is_bool(self):
        assert isinstance(CANDIDATE_PATCH_CREATED, bool)

    def test_production_modified_type_is_bool(self):
        assert isinstance(PRODUCTION_MODIFIED, bool)

    def test_diagnostic_only_type_is_bool(self):
        assert isinstance(DIAGNOSTIC_ONLY, bool)

    def test_record_inherits_safety_flags(self):
        rec = _build_default()
        assert rec.candidate_patch_created is False
        assert rec.production_modified is False
        assert rec.diagnostic_only is True


# ---------------------------------------------------------------------------
# Class 2: TestPITSafeDateWindow
# ---------------------------------------------------------------------------

class TestPITSafeDateWindow:
    """All PIT windows must be defined and snapshot_date < game_date."""

    REQUIRED_FEATURES = [
        "bullpen_usage_last_1d",
        "bullpen_usage_last_3d",
        "bullpen_usage_last_5d",
        "reliever_back_to_back_count",
        "reliever_three_in_four_days_count",
        "closer_used_last_1d",
        "closer_used_last_2d",
        "high_leverage_reliever_used_last_1d",
        "high_leverage_reliever_workload_last_3d",
        "bullpen_fatigue_favorite_side",
        "bullpen_fatigue_underdog_side",
        "bullpen_rest_imbalance",
    ]

    def test_all_required_features_have_pit_window(self):
        for fname in self.REQUIRED_FEATURES:
            assert fname in FEATURE_PIT_WINDOWS, f"Missing PIT window: {fname}"

    def test_all_pit_windows_are_positive_integers(self):
        for fname, meta in FEATURE_PIT_WINDOWS.items():
            w = meta["window_days"]
            assert isinstance(w, int) and w > 0, (
                f"{fname}: window_days={w!r} must be positive int"
            )

    def test_3d_window_is_exactly_3(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_3d"]["window_days"] == 3

    def test_1d_window_is_exactly_1(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_1d"]["window_days"] == 1

    def test_5d_window_is_exactly_5(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_5d"]["window_days"] == 5

    def test_b2b_window_uses_2_days(self):
        assert FEATURE_PIT_WINDOWS["reliever_back_to_back_count"]["window_days"] == 2

    def test_available_slot_snapshot_date_before_game_date(self):
        rec = _build_default()
        slot = rec.bullpen_usage_last_3d
        if slot.availability == FeatureAvailability.AVAILABLE:
            assert slot.pit_snapshot_date is not None
            assert slot.pit_snapshot_date < _GAME_DATE

    def test_available_slot_snapshot_date_is_d_minus_1(self):
        rec = _build_default()
        slot = rec.bullpen_usage_last_3d
        if slot.availability == FeatureAvailability.AVAILABLE:
            expected = (date.fromisoformat(_GAME_DATE) - timedelta(days=1)).isoformat()
            assert slot.pit_snapshot_date == expected

    def test_all_available_slots_have_snapshot_before_game_date(self):
        rec = _build_default()
        slots = [
            rec.bullpen_usage_last_3d,
            rec.bullpen_fatigue_favorite_side,
            rec.bullpen_fatigue_underdog_side,
            rec.bullpen_rest_imbalance,
        ]
        for slot in slots:
            if slot.availability == FeatureAvailability.AVAILABLE:
                assert slot.pit_snapshot_date < _GAME_DATE, (
                    f"{slot.feature_name}: snapshot_date={slot.pit_snapshot_date} "
                    f"must be < game_date={_GAME_DATE}"
                )

    def test_data_limited_slot_pit_snapshot_is_none(self):
        rec = _build_default()
        assert rec.bullpen_usage_last_1d.pit_snapshot_date is None
        assert rec.reliever_back_to_back_count.pit_snapshot_date is None
        assert rec.closer_used_last_1d.pit_snapshot_date is None

    def test_future_game_date_is_still_pit_safe(self):
        """PIT rule should apply for any future game_date."""
        future = "2025-09-15"
        rec = build_granular_record(
            game_id="MLB-20250915-NYY-BOS",
            game_date=future,
            team="Boston Red Sox",
            side="home",
            bullpen_3d_ip=4.0,
            fav_3d_ip=4.0,
            dog_3d_ip=2.0,
            home_3d_ip=4.0,
            away_3d_ip=2.0,
        )
        slot = rec.bullpen_usage_last_3d
        if slot.availability == FeatureAvailability.AVAILABLE:
            assert slot.pit_snapshot_date < future

    def test_pit_window_description_exists(self):
        for fname, meta in FEATURE_PIT_WINDOWS.items():
            assert "description" in meta, f"{fname} missing 'description'"
            assert len(meta["description"]) > 5


# ---------------------------------------------------------------------------
# Class 3: TestSchemaCompleteness
# ---------------------------------------------------------------------------

class TestSchemaCompleteness:
    """All 12 required features must be declared; DATA_LIMITED flagged correctly."""

    REQUIRED_SLOTS = [
        "bullpen_usage_last_1d",
        "bullpen_usage_last_3d",
        "bullpen_usage_last_5d",
        "reliever_back_to_back_count",
        "reliever_three_in_four_days_count",
        "closer_used_last_1d",
        "closer_used_last_2d",
        "high_leverage_reliever_used_last_1d",
        "high_leverage_reliever_workload_last_3d",
        "bullpen_fatigue_favorite_side",
        "bullpen_fatigue_underdog_side",
        "bullpen_rest_imbalance",
    ]

    def test_all_required_slots_present_in_record(self):
        rec = _build_default()
        for slot_name in self.REQUIRED_SLOTS:
            assert hasattr(rec, slot_name), (
                f"BullpenGranularRecord missing slot: {slot_name}"
            )

    def test_all_required_features_in_pit_windows(self):
        for fname in self.REQUIRED_SLOTS:
            assert fname in FEATURE_PIT_WINDOWS, f"Missing in FEATURE_PIT_WINDOWS: {fname}"

    def test_1d_is_data_limited_in_current_data(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_1d"]["available_in_current_data"] is False

    def test_5d_is_data_limited_in_current_data(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_5d"]["available_in_current_data"] is False

    def test_b2b_is_data_limited_in_current_data(self):
        assert FEATURE_PIT_WINDOWS["reliever_back_to_back_count"]["available_in_current_data"] is False

    def test_3in4_is_data_limited_in_current_data(self):
        assert FEATURE_PIT_WINDOWS["reliever_three_in_four_days_count"]["available_in_current_data"] is False

    def test_closer_1d_is_data_limited(self):
        assert FEATURE_PIT_WINDOWS["closer_used_last_1d"]["available_in_current_data"] is False

    def test_closer_2d_is_data_limited(self):
        assert FEATURE_PIT_WINDOWS["closer_used_last_2d"]["available_in_current_data"] is False

    def test_high_leverage_1d_is_data_limited(self):
        assert FEATURE_PIT_WINDOWS["high_leverage_reliever_used_last_1d"]["available_in_current_data"] is False

    def test_high_leverage_3d_is_data_limited(self):
        assert FEATURE_PIT_WINDOWS["high_leverage_reliever_workload_last_3d"]["available_in_current_data"] is False

    def test_3d_is_available_in_current_data(self):
        assert FEATURE_PIT_WINDOWS["bullpen_usage_last_3d"]["available_in_current_data"] is True

    def test_list_available_features_contains_3d(self):
        avail = list_available_features()
        assert "bullpen_usage_last_3d" in avail

    def test_list_data_limited_features_contains_1d(self):
        dl = list_data_limited_features()
        assert "bullpen_usage_last_1d" in dl

    def test_list_data_limited_features_contains_closer(self):
        dl = list_data_limited_features()
        assert "closer_used_last_1d" in dl

    def test_data_limited_features_have_reason(self):
        for fname, meta in FEATURE_PIT_WINDOWS.items():
            if not meta.get("available_in_current_data", True):
                reason = meta.get("data_limited_reason")
                assert reason is not None and len(reason) > 5, (
                    f"{fname}: data_limited_reason missing or too short"
                )


# ---------------------------------------------------------------------------
# Class 4: TestMissingDataHandling
# ---------------------------------------------------------------------------

class TestMissingDataHandling:
    """Missing data → DATA_LIMITED, never silently fills with neutral value."""

    def test_null_3d_gives_missing_slot(self):
        rec = _build_no_3d()
        slot = rec.bullpen_usage_last_3d
        assert slot.availability == FeatureAvailability.MISSING
        assert slot.value is None

    def test_null_fav_gives_missing_fatigue_fav(self):
        rec = _build_no_3d()
        assert rec.bullpen_fatigue_favorite_side.value is None

    def test_null_dog_gives_missing_fatigue_dog(self):
        rec = _build_no_3d()
        assert rec.bullpen_fatigue_underdog_side.value is None

    def test_null_home_away_gives_missing_imbalance(self):
        rec = _build_no_3d()
        assert rec.bullpen_rest_imbalance.value is None

    def test_data_limited_slots_always_none(self):
        rec = _build_default()
        data_limited_slots = [
            rec.bullpen_usage_last_1d,
            rec.bullpen_usage_last_5d,
            rec.reliever_back_to_back_count,
            rec.reliever_three_in_four_days_count,
            rec.closer_used_last_1d,
            rec.closer_used_last_2d,
            rec.high_leverage_reliever_used_last_1d,
            rec.high_leverage_reliever_workload_last_3d,
        ]
        for slot in data_limited_slots:
            assert slot.value is None, (
                f"{slot.feature_name}: DATA_LIMITED but value={slot.value!r}"
            )

    def test_data_limited_slots_have_reason(self):
        rec = _build_default()
        data_limited_slots = [
            rec.bullpen_usage_last_1d,
            rec.reliever_back_to_back_count,
            rec.closer_used_last_1d,
        ]
        for slot in data_limited_slots:
            assert slot.data_limited_reason is not None
            assert len(slot.data_limited_reason) > 5

    def test_data_limited_availability_enum(self):
        rec = _build_default()
        assert rec.bullpen_usage_last_1d.availability == FeatureAvailability.DATA_LIMITED

    def test_available_slot_has_none_reason(self):
        rec = _build_default()
        slot = rec.bullpen_usage_last_3d
        if slot.availability == FeatureAvailability.AVAILABLE:
            assert slot.data_limited_reason is None


# ---------------------------------------------------------------------------
# Class 5: TestNoNeutralFallbackMasquerade
# ---------------------------------------------------------------------------

class TestNoNeutralFallbackMasquerade:
    """DATA_LIMITED/MISSING features MUST have value=None, never 0 or 0.5."""

    def test_assert_no_neutral_fallback_passes_for_none(self):
        assert_no_neutral_fallback(None, "test_feature", FeatureAvailability.DATA_LIMITED)

    def test_assert_no_neutral_fallback_raises_for_zero(self):
        with pytest.raises(ValueError, match="(?i)masquerade"):
            assert_no_neutral_fallback(0.0, "test_feature", FeatureAvailability.DATA_LIMITED)

    def test_assert_no_neutral_fallback_raises_for_half(self):
        with pytest.raises(ValueError, match="(?i)masquerade"):
            assert_no_neutral_fallback(0.5, "test_feature", FeatureAvailability.MISSING)

    def test_assert_no_neutral_fallback_raises_for_negative(self):
        with pytest.raises(ValueError, match="(?i)masquerade"):
            assert_no_neutral_fallback(-1.0, "test_feature", FeatureAvailability.DATA_LIMITED)

    def test_assert_no_neutral_fallback_ok_for_available_with_value(self):
        # AVAILABLE + real value is fine
        assert_no_neutral_fallback(4.5, "test_feature", FeatureAvailability.AVAILABLE)

    def test_assert_no_neutral_fallback_ok_for_available_with_zero(self):
        # AVAILABLE + 0 is ok (e.g., team genuinely used 0 bullpen IP)
        assert_no_neutral_fallback(0.0, "test_feature", FeatureAvailability.AVAILABLE)

    def test_record_validate_catches_masquerade(self):
        """BullpenGranularRecord.validate() catches masquerade violations."""
        rec = _build_default()
        # Manually corrupt a DATA_LIMITED slot to hold a non-None value
        rec.bullpen_usage_last_1d.value = 0.0
        violations = rec.validate()
        assert any("masquerade" in v for v in violations), (
            f"Expected masquerade violation, got: {violations}"
        )

    def test_data_limited_availability_with_nonzero_fails_validate(self):
        rec = _build_default()
        rec.reliever_back_to_back_count.value = 2
        violations = rec.validate()
        assert len(violations) > 0


# ---------------------------------------------------------------------------
# Class 6: TestSSOTSingleSourceGuard
# ---------------------------------------------------------------------------

class TestSSOTSingleSourceGuard:
    """All bullpen features must be owned by the SSOT module."""

    SSOT_MODULE = "wbc_backend.features.mlb_bullpen_granular_ssot"

    SSOT_FEATURES = [
        "bullpen_usage_last_3d",
        "bullpen_usage_last_1d",
        "bullpen_usage_last_5d",
        "reliever_back_to_back_count",
        "reliever_three_in_four_days_count",
        "closer_used_last_1d",
        "closer_used_last_2d",
        "high_leverage_reliever_used_last_1d",
        "high_leverage_reliever_workload_last_3d",
        "bullpen_fatigue_favorite_side",
        "bullpen_fatigue_underdog_side",
        "bullpen_rest_imbalance",
    ]

    def test_all_features_registered_in_ssot(self):
        for fname in self.SSOT_FEATURES:
            assert fname in _SSOT_REGISTERED_MODULES, (
                f"Feature '{fname}' not registered in SSOT"
            )

    def test_all_features_point_to_ssot_module(self):
        for fname in self.SSOT_FEATURES:
            owner = get_ssot_owner(fname)
            assert owner == self.SSOT_MODULE, (
                f"Feature '{fname}' owner={owner!r} != SSOT module"
            )

    def test_assert_ssot_ownership_passes_for_correct_module(self):
        for fname in self.SSOT_FEATURES:
            assert_ssot_ownership(fname, self.SSOT_MODULE)

    def test_assert_ssot_ownership_raises_for_wrong_module(self):
        for fname in self.SSOT_FEATURES:
            with pytest.raises(ValueError, match="SSOT"):
                assert_ssot_ownership(fname, "orchestrator.phase60_bullpen_feature_decomposition")

    def test_assert_ssot_ownership_raises_for_phase56_module(self):
        with pytest.raises(ValueError, match="SSOT"):
            assert_ssot_ownership(
                "bullpen_fatigue_3d",
                "wbc_backend.features.mlb_bullpen_feature_builder",
            )

    def test_unknown_feature_not_blocked(self):
        # Unregistered features are not blocked (not yet a bullpen feature)
        assert_ssot_ownership("sp_era_7d", "some.other.module")

    def test_get_ssot_owner_returns_none_for_unknown(self):
        assert get_ssot_owner("sp_era_7d") is None

    def test_ssot_module_is_present_in_registry(self):
        values = set(_SSOT_REGISTERED_MODULES.values())
        assert self.SSOT_MODULE in values

    def test_legacy_features_registered_in_ssot(self):
        """Phase56/58 legacy features must also be SSOT-registered for migration."""
        assert "bullpen_fatigue_3d" in _SSOT_REGISTERED_MODULES
        assert "bullpen_fatigue_7d" in _SSOT_REGISTERED_MODULES


# ---------------------------------------------------------------------------
# Class 7: TestSpecialGameHandlingPolicy
# ---------------------------------------------------------------------------

class TestSpecialGameHandlingPolicy:
    """Policy strings must be documented for all special game cases."""

    def test_doubleheader_policy_exists(self):
        policy = SpecialGameHandlingPolicy.DOUBLEHEADER
        assert isinstance(policy, str) and len(policy) > 20

    def test_doubleheader_policy_mentions_game2(self):
        assert "Game 2" in SpecialGameHandlingPolicy.DOUBLEHEADER

    def test_postponed_policy_exists(self):
        policy = SpecialGameHandlingPolicy.POSTPONED
        assert isinstance(policy, str) and len(policy) > 20

    def test_opener_policy_exists(self):
        policy = SpecialGameHandlingPolicy.OPENER
        assert isinstance(policy, str) and len(policy) > 20

    def test_opener_policy_mentions_ip(self):
        assert "IP" in SpecialGameHandlingPolicy.OPENER

    def test_missing_boxscore_policy_exists(self):
        policy = SpecialGameHandlingPolicy.MISSING_BOXSCORE
        assert isinstance(policy, str) and len(policy) > 20

    def test_suspension_policy_exists(self):
        policy = SpecialGameHandlingPolicy.SUSPENSION
        assert isinstance(policy, str) and len(policy) > 20

    def test_suspension_policy_mentions_resume(self):
        assert "resume" in SpecialGameHandlingPolicy.SUSPENSION.lower()


# ---------------------------------------------------------------------------
# Class 8: TestNoProductionPatch
# ---------------------------------------------------------------------------

class TestNoProductionPatch:
    """Production and alpha must not be modified."""

    def test_candidate_patch_created_module_constant_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_module_constant_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_module_constant_false(self):
        assert ALPHA_MODIFIED is False

    def test_record_candidate_patch_false(self):
        rec = _build_default()
        assert rec.candidate_patch_created is False

    def test_record_production_modified_false(self):
        rec = _build_default()
        assert rec.production_modified is False

    def test_record_diagnostic_only_true(self):
        rec = _build_default()
        assert rec.diagnostic_only is True

    def test_no_blend_probability_modification(self):
        """SSOT module must not define or modify blend probability."""
        import wbc_backend.features.mlb_bullpen_granular_ssot as ssot_mod
        # Should NOT have ALPHA or blend_prob constants
        assert not hasattr(ssot_mod, "ALPHA"), (
            "SSOT module must not define ALPHA (it is frozen in phase60)"
        )

    def test_pit_safe_flag_on_record(self):
        rec = _build_default()
        assert rec.pit_safe is True


# ---------------------------------------------------------------------------
# Class 9: TestEndToEnd
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """Integration tests for build_granular_record."""

    def test_build_default_returns_record(self):
        rec = _build_default()
        assert isinstance(rec, BullpenGranularRecord)

    def test_build_default_no_violations(self):
        rec = _build_default()
        violations = rec.validate()
        assert violations == [], f"Unexpected violations: {violations}"

    def test_build_no_3d_no_violations(self):
        rec = _build_no_3d()
        violations = rec.validate()
        assert violations == []

    def test_record_schema_version(self):
        rec = _build_default()
        assert rec.ssot_schema_version == SSOT_SCHEMA_VERSION

    def test_record_game_id(self):
        rec = _build_default()
        assert rec.game_id == _GAME_ID

    def test_record_game_date(self):
        rec = _build_default()
        assert rec.game_date == _GAME_DATE

    def test_3d_slot_value_matches_input(self):
        rec = _build_default()
        assert rec.bullpen_usage_last_3d.value == pytest.approx(5.667, rel=1e-4)

    def test_fav_fatigue_value_matches_input(self):
        rec = _build_default()
        assert rec.bullpen_fatigue_favorite_side.value == pytest.approx(5.667, rel=1e-4)

    def test_dog_fatigue_value_matches_input(self):
        rec = _build_default()
        assert rec.bullpen_fatigue_underdog_side.value == pytest.approx(3.333, rel=1e-4)

    def test_rest_imbalance_computed_correctly(self):
        rec = _build_default()
        expected = abs(5.667 - 3.333)
        assert rec.bullpen_rest_imbalance.value == pytest.approx(expected, rel=1e-3)

    def test_audit_hash_present_and_nonempty(self):
        rec = _build_default()
        assert isinstance(rec.audit_hash, str)
        assert len(rec.audit_hash) > 0

    def test_audit_hash_deterministic(self):
        rec1 = _build_default()
        rec2 = _build_default()
        assert rec1.audit_hash == rec2.audit_hash

    def test_all_data_limited_slots_have_none_value(self):
        rec = _build_default()
        slots = [
            rec.bullpen_usage_last_1d,
            rec.bullpen_usage_last_5d,
            rec.reliever_back_to_back_count,
            rec.reliever_three_in_four_days_count,
            rec.closer_used_last_1d,
            rec.closer_used_last_2d,
            rec.high_leverage_reliever_used_last_1d,
            rec.high_leverage_reliever_workload_last_3d,
        ]
        for slot in slots:
            assert slot.value is None

    def test_all_data_limited_slots_have_availability_data_limited(self):
        rec = _build_default()
        slots = [
            rec.bullpen_usage_last_1d,
            rec.bullpen_usage_last_5d,
            rec.reliever_back_to_back_count,
            rec.reliever_three_in_four_days_count,
            rec.closer_used_last_1d,
            rec.closer_used_last_2d,
            rec.high_leverage_reliever_used_last_1d,
            rec.high_leverage_reliever_workload_last_3d,
        ]
        for slot in slots:
            assert slot.availability == FeatureAvailability.DATA_LIMITED

    def test_forbidden_field_guard_raises_for_home_win(self):
        with pytest.raises(ValueError, match="forbidden"):
            assert_not_forbidden_field("home_win")

    def test_forbidden_field_guard_raises_for_final_score(self):
        with pytest.raises(ValueError, match="forbidden"):
            assert_not_forbidden_field("final_score")

    def test_forbidden_field_guard_passes_for_bullpen_feature(self):
        assert_not_forbidden_field("bullpen_usage_last_3d")

    def test_source_recorded_in_record(self):
        rec = _build_default()
        assert rec.source == "mlb_stats_api_boxscore"

    def test_side_recorded_in_record(self):
        rec = _build_default()
        assert rec.side == "home"

    def test_team_recorded_in_record(self):
        rec = _build_default()
        assert rec.team == _HOME

    def test_different_sides_produce_different_hashes(self):
        rec_home = _build_default()
        rec_away = build_granular_record(
            game_id=_GAME_ID,
            game_date=_GAME_DATE,
            team=_AWAY,
            side="away",
            bullpen_3d_ip=3.333,
            fav_3d_ip=5.667,
            dog_3d_ip=3.333,
            home_3d_ip=5.667,
            away_3d_ip=3.333,
        )
        assert rec_home.audit_hash != rec_away.audit_hash

    def test_symmetric_home_away_rest_imbalance(self):
        """Rest imbalance should be the same for both home and away records."""
        rec_home = _build_default()
        rec_away = build_granular_record(
            game_id=_GAME_ID,
            game_date=_GAME_DATE,
            team=_AWAY,
            side="away",
            bullpen_3d_ip=3.333,
            fav_3d_ip=5.667,
            dog_3d_ip=3.333,
            home_3d_ip=5.667,
            away_3d_ip=3.333,
        )
        assert rec_home.bullpen_rest_imbalance.value == pytest.approx(
            rec_away.bullpen_rest_imbalance.value, rel=1e-4
        )

    def test_zero_3d_ip_gives_available_zero(self):
        rec = build_granular_record(
            game_id=_GAME_ID,
            game_date=_GAME_DATE,
            team=_HOME,
            side="home",
            bullpen_3d_ip=0.0,
            fav_3d_ip=0.0,
            dog_3d_ip=0.0,
            home_3d_ip=0.0,
            away_3d_ip=0.0,
        )
        # 0.0 is a valid measurement (team genuinely used 0 IP in 3d)
        assert rec.bullpen_usage_last_3d.value == pytest.approx(0.0)
        assert rec.bullpen_usage_last_3d.availability == FeatureAvailability.AVAILABLE
        assert rec.bullpen_rest_imbalance.value == pytest.approx(0.0)
