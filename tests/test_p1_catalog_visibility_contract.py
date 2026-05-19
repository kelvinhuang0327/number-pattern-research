"""
tests/test_p1_catalog_visibility_contract.py
=============================================
Tests for the P1 catalog visibility contract model.
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_strategy_catalog_contract import (
    ArtifactSourceType,
    CatalogEntry,
    CatalogVisibilityState,
    classify_visibility,
)


class TestCatalogVisibilityState:
    def test_validate_valid_state(self):
        for s in CatalogVisibilityState._ALL:
            assert CatalogVisibilityState.validate(s) == s

    def test_validate_invalid_state(self):
        import pytest
        with pytest.raises(ValueError):
            CatalogVisibilityState.validate("NO_DATA")  # old enum value not valid

    def test_all_constants_in_all(self):
        expected = {
            "REGISTERED_WITH_REPLAY_ROWS",
            "RECONSTRUCTIBLE",
            "REGISTERED_NO_DATA",
            "ARTIFACT_CANDIDATE",
            "UNSUPPORTED",
        }
        actual = set(CatalogVisibilityState._ALL)
        assert actual == expected


class TestCatalogEntry:
    def _make_entry(self, **kwargs) -> CatalogEntry:
        defaults = dict(
            strategy_id="test_strat",
            display_name="Test",
            lottery_type="DAILY_539",
            lifecycle_state="ONLINE",
            catalog_visibility_state=CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS,
        )
        defaults.update(kwargs)
        return CatalogEntry(**defaults)

    def test_can_generate_replay_rows_always_false(self):
        """P1 hard constraint: can_generate_replay_rows() must always return False."""
        for state in CatalogVisibilityState._ALL:
            entry = self._make_entry(catalog_visibility_state=state)
            assert entry.can_generate_replay_rows() is False, (
                f"can_generate_replay_rows() returned True for state={state}"
            )

    def test_can_mark_online_only_for_online(self):
        """can_mark_online() returns True only when lifecycle_state=ONLINE."""
        online = self._make_entry(lifecycle_state="ONLINE")
        assert online.can_mark_online() is True

        for state in ("OFFLINE", "REJECTED", "RETIRED", "OBSERVATION", "NOT_REGISTERED"):
            entry = self._make_entry(lifecycle_state=state)
            assert entry.can_mark_online() is False, (
                f"can_mark_online() returned True for lifecycle_state={state}"
            )

    def test_artifact_only_not_online(self):
        """ARTIFACT_CANDIDATE entries must not be markable ONLINE."""
        entry = self._make_entry(
            lifecycle_state="NOT_REGISTERED",
            catalog_visibility_state=CatalogVisibilityState.ARTIFACT_CANDIDATE,
        )
        assert entry.can_mark_online() is False

    def test_dry_run_only_default_true(self):
        """dry_run_only must default to True."""
        entry = self._make_entry()
        assert entry.dry_run_only is True

    def test_to_dict_has_required_fields(self):
        entry = self._make_entry()
        d = entry.to_dict()
        required = {
            "strategy_id", "display_name", "lottery_type", "lifecycle_state",
            "catalog_visibility_state", "source_paths", "artifact_source_type",
            "has_replay_rows", "has_historical_predictions", "replay_row_count",
            "reconstructible_reason", "no_data_reason", "provenance_hash",
            "created_by_phase", "dry_run_only",
        }
        missing = required - set(d.keys())
        assert not missing, f"Missing fields in to_dict(): {missing}"


class TestClassifyVisibility:
    def test_with_replay_rows(self):
        state = classify_visibility(
            lifecycle_state="ONLINE",
            replay_row_count=10,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.NONE,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS

    def test_artifact_candidate_not_registered(self):
        state = classify_visibility(
            lifecycle_state="ONLINE",
            replay_row_count=0,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.CODE_SCAN,
            is_registered=False,
        )
        assert state == CatalogVisibilityState.ARTIFACT_CANDIDATE

    def test_reconstructible_with_prediction_log(self):
        state = classify_visibility(
            lifecycle_state="RETIRED",
            replay_row_count=0,
            has_historical_predictions=True,
            artifact_source_type=ArtifactSourceType.PREDICTION_LOG,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.RECONSTRUCTIBLE

    def test_reconstructible_with_code_scan(self):
        state = classify_visibility(
            lifecycle_state="ONLINE",
            replay_row_count=0,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.CODE_SCAN,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.RECONSTRUCTIBLE

    def test_registered_no_data_for_active(self):
        state = classify_visibility(
            lifecycle_state="ONLINE",
            replay_row_count=0,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.NONE,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.REGISTERED_NO_DATA

    def test_unsupported_for_rejected_no_artifact(self):
        state = classify_visibility(
            lifecycle_state="REJECTED",
            replay_row_count=0,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.NONE,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.UNSUPPORTED

    def test_reconstructible_beats_unsupported(self):
        """REJECTED + code artifact → RECONSTRUCTIBLE, not UNSUPPORTED."""
        state = classify_visibility(
            lifecycle_state="REJECTED",
            replay_row_count=0,
            has_historical_predictions=False,
            artifact_source_type=ArtifactSourceType.REJECTED_JSON,
            is_registered=True,
        )
        assert state == CatalogVisibilityState.RECONSTRUCTIBLE
