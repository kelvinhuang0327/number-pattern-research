"""
test_p1_catalog_visibility_contract.py
=======================================
Tests for the P1 Catalog Visibility contract module.

Covers:
  1. CatalogVisibilityState enum values
  2. CatalogEntry dataclass creation and validation
  3. Safety helpers: is_visible_in_catalog, is_no_data_entry
  4. P1 hard constraint: can_generate_replay_rows always False
  5. can_mark_online only for ONLINE lifecycle
  6. Artifact-only entries cannot be marked ONLINE
  7. validate_entry catches violations
  8. CatalogExpansionPlan.to_dict() includes correct safety flags
"""
import pytest
from lottery_api.models.replay_strategy_catalog_contract import (
    ArtifactSourceType,
    CatalogEntry,
    CatalogExpansionPlan,
    CatalogVisibilityState,
    LifecycleState,
    can_generate_replay_rows,
    can_mark_online,
    is_no_data_entry,
    is_visible_in_catalog,
    is_safe_artifact_lifecycle,
    requires_controlled_apply,
    validate_entry,
)


# ─── CatalogVisibilityState ───────────────────────────────────────────────────

class TestCatalogVisibilityState:
    def test_all_states_present(self):
        states = {s.value for s in CatalogVisibilityState}
        assert "REGISTERED_WITH_REPLAY_ROWS" in states
        assert "REGISTERED_NO_DATA" in states
        assert "ARTIFACT_CANDIDATE" in states
        assert "UNSUPPORTED" in states

    def test_str_enum(self):
        assert CatalogVisibilityState.ARTIFACT_CANDIDATE == "ARTIFACT_CANDIDATE"


# ─── CatalogEntry construction ────────────────────────────────────────────────

class TestCatalogEntry:
    def _make_entry(self, **kwargs):
        defaults = dict(
            strategy_id="test_strategy_001",
            display_name="Test Strategy",
            lottery_type="DAILY_539",
            lifecycle_state=LifecycleState.REJECTED,
            catalog_visibility_state=CatalogVisibilityState.ARTIFACT_CANDIDATE,
            has_replay_rows=False,
            no_data_reason="NO_REPLAY_ROWS: test",
        )
        defaults.update(kwargs)
        return CatalogEntry(**defaults)

    def test_basic_creation(self):
        entry = self._make_entry()
        assert entry.strategy_id == "test_strategy_001"
        assert entry.lottery_type == "DAILY_539"
        assert entry.dry_run_only is True

    def test_provenance_hash_auto_computed(self):
        entry = self._make_entry(source_paths=["rejected/test.json"])
        assert entry.provenance_hash is not None
        assert len(entry.provenance_hash) == 64  # SHA-256 hex

    def test_to_dict_serializable(self):
        import json
        entry = self._make_entry()
        d = entry.to_dict()
        # Must be JSON serializable
        json.dumps(d)
        assert "strategy_id" in d
        assert "catalog_visibility_state" in d
        assert "lifecycle_state" in d

    def test_to_dict_enum_values_are_strings(self):
        entry = self._make_entry()
        d = entry.to_dict()
        assert isinstance(d["lifecycle_state"], str)
        assert isinstance(d["catalog_visibility_state"], str)


# ─── Safety helpers ───────────────────────────────────────────────────────────

class TestSafetyHelpers:
    def _make_entry(self, **kwargs):
        defaults = dict(
            strategy_id="test_001",
            display_name="Test",
            lottery_type="DAILY_539",
            lifecycle_state=LifecycleState.REJECTED,
            catalog_visibility_state=CatalogVisibilityState.ARTIFACT_CANDIDATE,
            has_replay_rows=False,
            no_data_reason="NO_REPLAY_ROWS: test",
        )
        defaults.update(kwargs)
        return CatalogEntry(**defaults)

    def test_is_visible_unsupported_is_false(self):
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.UNSUPPORTED
        )
        assert is_visible_in_catalog(entry) is False

    def test_is_visible_artifact_candidate_is_true(self):
        entry = self._make_entry()
        assert is_visible_in_catalog(entry) is True

    def test_is_no_data_entry_without_rows(self):
        entry = self._make_entry(has_replay_rows=False)
        assert is_no_data_entry(entry) is True

    def test_is_no_data_entry_with_rows(self):
        entry = self._make_entry(
            has_replay_rows=True,
            catalog_visibility_state=CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS,
            no_data_reason=None,
        )
        assert is_no_data_entry(entry) is False

    def test_can_generate_replay_rows_always_false(self):
        """P1 HARD CONSTRAINT: replay row generation is always False."""
        for vis in CatalogVisibilityState:
            for lc in LifecycleState:
                entry = self._make_entry(
                    catalog_visibility_state=vis,
                    lifecycle_state=lc,
                    no_data_reason="NO_REPLAY_ROWS: test" if vis != CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS else None,
                )
                assert can_generate_replay_rows(entry) is False, \
                    f"can_generate_replay_rows must always be False, failed for {vis}/{lc}"

    def test_can_mark_online_only_for_online_lifecycle(self):
        online_entry = self._make_entry(
            lifecycle_state=LifecycleState.ONLINE,
            catalog_visibility_state=CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS,
            has_replay_rows=True,
            no_data_reason=None,
        )
        assert can_mark_online(online_entry) is True

        for lc in (LifecycleState.REJECTED, LifecycleState.RETIRED,
                   LifecycleState.OBSERVATION, LifecycleState.ARTIFACT_ONLY):
            entry = self._make_entry(lifecycle_state=lc)
            assert can_mark_online(entry) is False, \
                f"can_mark_online must be False for lifecycle={lc}"

    def test_requires_controlled_apply_for_visible_entries(self):
        entry = self._make_entry()
        assert requires_controlled_apply(entry) is True

    def test_requires_controlled_apply_false_for_unsupported(self):
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.UNSUPPORTED
        )
        assert requires_controlled_apply(entry) is False

    def test_is_safe_artifact_lifecycle(self):
        safe = [LifecycleState.REJECTED, LifecycleState.RETIRED,
                LifecycleState.OBSERVATION, LifecycleState.ARTIFACT_ONLY,
                LifecycleState.OFFLINE]
        for lc in safe:
            assert is_safe_artifact_lifecycle(lc) is True

        assert is_safe_artifact_lifecycle(LifecycleState.ONLINE) is False


# ─── validate_entry ───────────────────────────────────────────────────────────

class TestValidateEntry:
    def _make_entry(self, **kwargs):
        defaults = dict(
            strategy_id="valid_strategy_001",
            display_name="Valid Strategy",
            lottery_type="DAILY_539",
            lifecycle_state=LifecycleState.REJECTED,
            catalog_visibility_state=CatalogVisibilityState.ARTIFACT_CANDIDATE,
            has_replay_rows=False,
            no_data_reason="NO_REPLAY_ROWS: rejected",
        )
        defaults.update(kwargs)
        return CatalogEntry(**defaults)

    def test_valid_entry_no_violations(self):
        entry = self._make_entry()
        violations = validate_entry(entry)
        assert violations == []

    def test_empty_strategy_id_violation(self):
        entry = self._make_entry(strategy_id="")
        violations = validate_entry(entry)
        assert any("strategy_id" in v for v in violations)

    def test_invalid_lottery_type_violation(self):
        entry = self._make_entry(lottery_type="INVALID_GAME")
        violations = validate_entry(entry)
        assert any("lottery_type" in v for v in violations)

    def test_artifact_candidate_online_violation(self):
        entry = self._make_entry(lifecycle_state=LifecycleState.ONLINE)
        violations = validate_entry(entry)
        assert any("ONLINE" in v for v in violations)

    def test_no_data_without_reason_violation(self):
        entry = self._make_entry(no_data_reason=None)
        violations = validate_entry(entry)
        assert any("no_data_reason" in v for v in violations)


# ─── CatalogExpansionPlan ─────────────────────────────────────────────────────

class TestCatalogExpansionPlan:
    def test_to_dict_safety_flags_all_false(self):
        plan = CatalogExpansionPlan(
            generated_at="2026-05-18T00:00:00Z",
            runtime_canonical_before=18,
        )
        d = plan.to_dict()
        safety = d["safety"]
        assert safety["db_write"] is False
        assert safety["draw_import"] is False
        assert safety["replay_row_generation"] is False
        assert safety["prediction_update"] is False
        assert safety["strategy_execution"] is False

    def test_to_dict_contains_required_keys(self):
        plan = CatalogExpansionPlan(generated_at="2026-05-18T00:00:00Z")
        d = plan.to_dict()
        required = [
            "generated_at", "runtime_canonical_before", "artifact_candidate_count",
            "planned_new_registry_entries", "planned_existing_registry_updates",
            "planned_no_data_entries", "by_lottery", "by_lifecycle", "entries",
            "safety",
        ]
        for key in required:
            assert key in d, f"Missing required key: {key}"

    def test_default_runtime_canonical_is_18(self):
        plan = CatalogExpansionPlan(generated_at="2026-05-18T00:00:00Z")
        assert plan.runtime_canonical_before == 18
