"""
tests/test_p3_replay_catalog_ui_state_contract.py
==================================================
P3: Tests for replay catalog UI state machine contract.
Validates state transition rules, display labels, forbidden transitions,
and the public-vs-admin visibility gate (replay_catalog_visibility_gate).
"""
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_strategy_catalog_contract import (
    CatalogEntry,
    CatalogVisibilityState,
    ArtifactSourceType,
    classify_visibility,
)
from lottery_api.models.replay_catalog_visibility_gate import (
    is_public_visible,
    is_internal_only,
    requires_admin_or_debug,
    get_visibility_meta,
    filter_for_public,
    annotate_with_visibility,
    PUBLIC_VISIBLE_STATES,
    INTERNAL_ONLY_STATES,
)


_DISPLAY_LABEL_MAP = {
    CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS: "Registered (has rows)",
    CatalogVisibilityState.RECONSTRUCTIBLE: "Reconstructible",
    CatalogVisibilityState.REGISTERED_NO_DATA: "Registered (no data)",
    CatalogVisibilityState.ARTIFACT_CANDIDATE: "Artifact Candidate",
    CatalogVisibilityState.UNSUPPORTED: "Unsupported",
}


class TestP3UIStateMachineTransitions:
    """P3: Forbidden state transitions in the replay catalog UI."""

    def _make_entry(self, **kwargs) -> CatalogEntry:
        defaults = dict(
            strategy_id="ui_test_strat",
            display_name="UI Test",
            lottery_type="DAILY_539",
            lifecycle_state="RETIRED",
            catalog_visibility_state=CatalogVisibilityState.RECONSTRUCTIBLE,
        )
        defaults.update(kwargs)
        return CatalogEntry(**defaults)

    def test_reconstructible_cannot_become_registered_without_apply(self):
        """RECONSTRUCTIBLE cannot transition to REGISTERED_WITH_REPLAY_ROWS
        without an explicit P7 apply step.  The entry must remain RECONSTRUCTIBLE
        if no rows have been applied."""
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.RECONSTRUCTIBLE,
            lifecycle_state="RETIRED",
        )
        # The entry hasn't had rows applied, so it must stay RECONSTRUCTIBLE
        assert entry.catalog_visibility_state == CatalogVisibilityState.RECONSTRUCTIBLE
        # And it cannot generate rows via the P1 contract
        assert entry.can_generate_replay_rows() is False

    def test_artifact_candidate_cannot_transition_to_online(self):
        """ARTIFACT_CANDIDATE is never a valid ONLINE entry."""
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.ARTIFACT_CANDIDATE,
            lifecycle_state="ARTIFACT_CANDIDATE",
        )
        assert entry.can_mark_online() is False

    def test_unsupported_cannot_generate_rows(self):
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.UNSUPPORTED,
        )
        assert entry.can_generate_replay_rows() is False

    def test_registered_no_data_cannot_generate_rows(self):
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.REGISTERED_NO_DATA,
        )
        assert entry.can_generate_replay_rows() is False

    def test_registered_with_replay_rows_cannot_generate_more_rows(self):
        """Even REGISTERED_WITH_REPLAY_ROWS must pass through P7 apply contract."""
        entry = self._make_entry(
            catalog_visibility_state=CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS,
            lifecycle_state="ONLINE",
        )
        assert entry.can_generate_replay_rows() is False


class TestP3UIDisplayStates:
    """P3: All 5 states should have a valid display label."""

    def test_all_states_have_display_labels(self):
        """Every catalog_visibility_state maps to a non-empty display label."""
        for state in CatalogVisibilityState._ALL:
            label = _DISPLAY_LABEL_MAP.get(state)
            assert label is not None, f"No display label for state={state}"
            assert label.strip() != "", f"Empty display label for state={state}"

    def test_reconstructible_label(self):
        assert _DISPLAY_LABEL_MAP[CatalogVisibilityState.RECONSTRUCTIBLE] == "Reconstructible"

    def test_artifact_candidate_label(self):
        assert _DISPLAY_LABEL_MAP[CatalogVisibilityState.ARTIFACT_CANDIDATE] == "Artifact Candidate"


class TestP3UIAllStatesReachable:
    """P3: All 5 catalog visibility states must be reachable via classify_visibility."""

    def _classify(self, **kwargs) -> str:
        return classify_visibility(**kwargs)

    def test_registered_with_replay_rows_reachable(self):
        result = self._classify(
            is_registered=True,
            replay_row_count=10,
            artifact_source_type=ArtifactSourceType.REPLAY_RUN,
            lifecycle_state="ONLINE",
            has_historical_predictions=True,
        )
        assert result == CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS

    def test_reconstructible_reachable(self):
        result = self._classify(
            is_registered=True,
            replay_row_count=0,
            artifact_source_type=ArtifactSourceType.PREDICTION_LOG,
            lifecycle_state="RETIRED",
            has_historical_predictions=True,
        )
        assert result == CatalogVisibilityState.RECONSTRUCTIBLE

    def test_artifact_candidate_reachable(self):
        result = self._classify(
            is_registered=False,
            replay_row_count=0,
            artifact_source_type=ArtifactSourceType.CODE_SCAN,
            lifecycle_state="ARTIFACT_CANDIDATE",
            has_historical_predictions=False,
        )
        assert result == CatalogVisibilityState.ARTIFACT_CANDIDATE

    def test_registered_no_data_reachable(self):
        result = self._classify(
            is_registered=True,
            replay_row_count=0,
            artifact_source_type=ArtifactSourceType.NONE,
            lifecycle_state="ONLINE",
            has_historical_predictions=False,
        )
        assert result == CatalogVisibilityState.REGISTERED_NO_DATA

    def test_unsupported_reachable(self):
        result = self._classify(
            is_registered=True,
            replay_row_count=0,
            artifact_source_type=ArtifactSourceType.NONE,
            lifecycle_state="UNSUPPORTED",
            has_historical_predictions=False,
        )
        assert result == CatalogVisibilityState.UNSUPPORTED


# ---------------------------------------------------------------------------
# Public Visibility Gate tests (replay_catalog_visibility_gate)
# ---------------------------------------------------------------------------

class TestP3UIPublicVisibilityGate:
    """P3: Public vs admin/debug visibility rules for catalog states."""

    # ── PUBLIC_VISIBLE_STATES coverage ────────────────────────────────────

    def test_registered_with_replay_rows_is_public_visible(self):
        assert is_public_visible(CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS) is True

    def test_artifact_candidate_not_public_visible(self):
        """ARTIFACT_CANDIDATE must NEVER appear on the public replay page."""
        assert is_public_visible(CatalogVisibilityState.ARTIFACT_CANDIDATE) is False

    def test_reconstructible_not_public_visible(self):
        """RECONSTRUCTIBLE rows not yet applied (P7 gate); hidden from users."""
        assert is_public_visible(CatalogVisibilityState.RECONSTRUCTIBLE) is False

    def test_registered_no_data_not_public_visible(self):
        assert is_public_visible(CatalogVisibilityState.REGISTERED_NO_DATA) is False

    def test_unsupported_not_public_visible(self):
        assert is_public_visible(CatalogVisibilityState.UNSUPPORTED) is False

    # ── INTERNAL_ONLY_STATES coverage ─────────────────────────────────────

    def test_artifact_candidate_is_internal_only(self):
        assert is_internal_only(CatalogVisibilityState.ARTIFACT_CANDIDATE) is True

    def test_reconstructible_is_internal_only(self):
        assert is_internal_only(CatalogVisibilityState.RECONSTRUCTIBLE) is True

    def test_registered_no_data_is_internal_only(self):
        assert is_internal_only(CatalogVisibilityState.REGISTERED_NO_DATA) is True

    def test_unsupported_is_internal_only(self):
        assert is_internal_only(CatalogVisibilityState.UNSUPPORTED) is True

    def test_registered_with_replay_rows_is_not_internal_only(self):
        assert is_internal_only(CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS) is False

    # ── requires_admin_or_debug alias ─────────────────────────────────────

    def test_requires_admin_or_debug_matches_internal_only(self):
        for state in CatalogVisibilityState._ALL:
            assert requires_admin_or_debug(state) == is_internal_only(state), (
                f"requires_admin_or_debug / is_internal_only mismatch for {state}"
            )

    # ── All states covered — no orphaned state ────────────────────────────

    def test_every_state_in_exactly_one_bucket(self):
        """Each state must be in either PUBLIC_VISIBLE or INTERNAL_ONLY, not both."""
        for state in CatalogVisibilityState._ALL:
            in_public   = state in PUBLIC_VISIBLE_STATES
            in_internal = state in INTERNAL_ONLY_STATES
            assert in_public != in_internal, (
                f"State {state!r} must be in exactly one bucket "
                f"(public={in_public}, internal={in_internal})"
            )

    def test_all_states_covered_by_gate(self):
        """No state in _ALL should be missing from both buckets."""
        all_covered = PUBLIC_VISIBLE_STATES | INTERNAL_ONLY_STATES
        for state in CatalogVisibilityState._ALL:
            assert state in all_covered, f"State {state!r} not covered by visibility gate"

    # ── get_visibility_meta ───────────────────────────────────────────────

    def test_visibility_meta_registered_with_rows(self):
        meta = get_visibility_meta(CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS)
        assert meta["is_public_visible"] is True
        assert meta["is_internal_only"] is False
        assert meta["requires_admin_or_debug"] is False

    def test_visibility_meta_artifact_candidate(self):
        meta = get_visibility_meta(CatalogVisibilityState.ARTIFACT_CANDIDATE)
        assert meta["is_public_visible"] is False
        assert meta["is_internal_only"] is True
        assert meta["requires_admin_or_debug"] is True

    def test_visibility_meta_unknown_state_defaults_to_internal(self):
        meta = get_visibility_meta("UNKNOWN_FUTURE_STATE")
        assert meta["is_public_visible"] is False
        assert meta["is_internal_only"] is True

    # ── filter_for_public ─────────────────────────────────────────────────

    def test_filter_for_public_removes_internal_states(self):
        entries = [
            {"strategy_id": "s1", "catalog_visibility_state": CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS},
            {"strategy_id": "s2", "catalog_visibility_state": CatalogVisibilityState.ARTIFACT_CANDIDATE},
            {"strategy_id": "s3", "catalog_visibility_state": CatalogVisibilityState.RECONSTRUCTIBLE},
            {"strategy_id": "s4", "catalog_visibility_state": CatalogVisibilityState.REGISTERED_NO_DATA},
            {"strategy_id": "s5", "catalog_visibility_state": CatalogVisibilityState.UNSUPPORTED},
        ]
        public = filter_for_public(entries)
        assert len(public) == 1
        assert public[0]["strategy_id"] == "s1"

    def test_filter_for_public_keeps_only_registered_with_rows(self):
        entries = [
            {"strategy_id": "a", "catalog_visibility_state": CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS},
            {"strategy_id": "b", "catalog_visibility_state": CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS},
        ]
        public = filter_for_public(entries)
        assert len(public) == 2

    def test_filter_for_public_empty_list(self):
        assert filter_for_public([]) == []

    def test_filter_for_public_all_internal_returns_empty(self):
        entries = [
            {"catalog_visibility_state": CatalogVisibilityState.ARTIFACT_CANDIDATE},
            {"catalog_visibility_state": CatalogVisibilityState.RECONSTRUCTIBLE},
        ]
        assert filter_for_public(entries) == []

    # ── annotate_with_visibility ──────────────────────────────────────────

    def test_annotate_with_visibility_adds_fields(self):
        entries = [
            {"strategy_id": "s1", "catalog_visibility_state": CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS},
            {"strategy_id": "s2", "catalog_visibility_state": CatalogVisibilityState.ARTIFACT_CANDIDATE},
        ]
        annotated = annotate_with_visibility(entries)
        assert len(annotated) == 2

        pub = annotated[0]
        assert pub["is_public_visible"] is True
        assert pub["is_internal_only"] is False
        assert pub["requires_admin_or_debug"] is False

        internal = annotated[1]
        assert internal["is_public_visible"] is False
        assert internal["is_internal_only"] is True
        assert internal["requires_admin_or_debug"] is True

    def test_annotate_does_not_mutate_originals(self):
        original = {"strategy_id": "s1", "catalog_visibility_state": CatalogVisibilityState.RECONSTRUCTIBLE}
        annotate_with_visibility([original])
        assert "is_public_visible" not in original  # original dict unchanged
