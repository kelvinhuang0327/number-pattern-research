"""
test_p26_non_online_strategy_state_labels.py
=============================================
P26: Non-ONLINE Strategy State Labels — verification suite

Scope:
  - Label definitions (all 9 defined, correct fields)
  - assign_label() pure function coverage for all 9 labels
  - is_row_backed() correctness
  - P24 inventory integration (all 59 strategies, correct distribution)
  - get_label_for_strategy() / get_full_label_catalog() / get_label_summary()
  - Anti-contamination: no DB access, no writes, no execution

HARD RULES (verified):
  - No production DB write.
  - No new migrations.
  - No new tables.
  - No strategy execution.
  - Production rows stay at 12460.
"""
from __future__ import annotations

import importlib
import inspect
import json
import sqlite3
from pathlib import Path
from typing import Optional

import pytest

# ─── Module under test ────────────────────────────────────────────────────────

from lottery_api.models.replay_strategy_state_labels import (
    ALL_LABEL_KEYS,
    LABEL_DEFINITIONS,
    assign_label,
    build_label_entry,
    get_full_label_catalog,
    get_label_definition,
    get_label_for_strategy,
    get_label_summary,
    is_row_backed,
)

# ─── Paths ────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent
_P24_PATH  = _REPO_ROOT / "outputs" / "replay" / "p24_full_strategy_universe_inventory_20260521.json"
_DB_PATH   = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# ─── Expected P24 constants ───────────────────────────────────────────────────

_EXPECTED_TOTAL        = 59
_EXPECTED_ROW_BACKED   = 8
_EXPECTED_ARTIFACT     = 41
_EXPECTED_RETIRED      = 5
_EXPECTED_REJECTED_REG = 4
_EXPECTED_OBSERVATION  = 1
_EXPECTED_DB_ROWS      = 12460

# ─── Section 1: Label definition tests ───────────────────────────────────────

class TestLabelDefinitions:

    def test_all_9_labels_defined(self):
        """All 9 canonical label keys must be present in LABEL_DEFINITIONS."""
        required = {
            "row-backed", "artifact-only", "no-data", "reconstructible",
            "manual-review", "unsupported", "retired",
            "rejected-registered", "observation",
        }
        assert required == set(LABEL_DEFINITIONS.keys()), (
            f"Missing labels: {required - set(LABEL_DEFINITIONS.keys())}"
        )

    def test_all_9_in_all_label_keys_frozenset(self):
        """ALL_LABEL_KEYS frozenset mirrors LABEL_DEFINITIONS keys."""
        assert ALL_LABEL_KEYS == frozenset(LABEL_DEFINITIONS.keys())

    def test_every_label_has_display_field(self):
        for key, defn in LABEL_DEFINITIONS.items():
            assert "display" in defn, f"Label '{key}' missing 'display'"
            assert isinstance(defn["display"], str)
            assert len(defn["display"]) > 0

    def test_every_label_has_description_field(self):
        for key, defn in LABEL_DEFINITIONS.items():
            assert "description" in defn, f"Label '{key}' missing 'description'"
            assert isinstance(defn["description"], str)
            assert len(defn["description"]) > 0

    def test_every_label_has_queryable_field(self):
        for key, defn in LABEL_DEFINITIONS.items():
            assert "queryable" in defn, f"Label '{key}' missing 'queryable'"
            assert isinstance(defn["queryable"], bool)

    def test_row_backed_is_queryable(self):
        """Only row-backed strategies are queryable."""
        assert LABEL_DEFINITIONS["row-backed"]["queryable"] is True

    def test_all_non_row_backed_not_queryable(self):
        """All non-row-backed labels must have queryable=False."""
        non_row_backed = set(LABEL_DEFINITIONS.keys()) - {"row-backed"}
        for key in non_row_backed:
            assert LABEL_DEFINITIONS[key]["queryable"] is False, (
                f"Label '{key}' must not be queryable"
            )

    def test_get_label_definition_returns_copy(self):
        """get_label_definition should return a copy, not the original dict."""
        defn = get_label_definition("row-backed")
        assert defn is not None
        defn["queryable"] = False  # mutate the copy
        # Original must be unchanged
        assert LABEL_DEFINITIONS["row-backed"]["queryable"] is True

    def test_get_label_definition_unknown_returns_none(self):
        assert get_label_definition("nonexistent-label-xyz") is None

    def test_get_label_definition_all_9_return_dicts(self):
        for key in LABEL_DEFINITIONS:
            defn = get_label_definition(key)
            assert defn is not None
            assert isinstance(defn, dict)


# ─── Section 2: assign_label() pure function tests ───────────────────────────

class TestAssignLabel:

    # row-backed
    def test_online_row_backed_with_rows_returns_row_backed(self):
        assert assign_label("ONLINE_ROW_BACKED", row_count=1570) == "row-backed"

    def test_online_row_backed_with_one_row_returns_row_backed(self):
        assert assign_label("ONLINE_ROW_BACKED", row_count=1) == "row-backed"

    def test_online_row_backed_no_rows_returns_no_data(self):
        """Edge: registered as row-backed but has 0 rows → no-data."""
        assert assign_label("ONLINE_ROW_BACKED", row_count=0) == "no-data"

    # artifact-only
    def test_artifact_only_basic_returns_artifact_only(self):
        assert assign_label("ARTIFACT_ONLY") == "artifact-only"

    def test_artifact_only_with_reconstructible_returns_reconstructible(self):
        assert assign_label("ARTIFACT_ONLY", reconstructible_candidate=True) == "reconstructible"

    def test_artifact_only_manual_review_returns_manual_review(self):
        assert assign_label("ARTIFACT_ONLY", needs_manual_review=True) == "manual-review"

    def test_artifact_only_unsupported_returns_unsupported(self):
        assert assign_label("ARTIFACT_ONLY", unsupported_reason="no source code") == "unsupported"

    def test_manual_review_overrides_reconstructible(self):
        """manual-review has priority over reconstructible_candidate."""
        result = assign_label(
            "ARTIFACT_ONLY",
            reconstructible_candidate=True,
            needs_manual_review=True,
        )
        assert result == "manual-review"

    def test_unsupported_overrides_reconstructible(self):
        """unsupported_reason has priority over reconstructible_candidate."""
        result = assign_label(
            "ARTIFACT_ONLY",
            reconstructible_candidate=True,
            unsupported_reason="missing training data",
        )
        assert result == "unsupported"

    def test_manual_review_overrides_unsupported(self):
        """manual-review has priority over unsupported_reason."""
        result = assign_label(
            "ARTIFACT_ONLY",
            needs_manual_review=True,
            unsupported_reason="no source code",
        )
        assert result == "manual-review"

    # retired
    def test_retired_returns_retired(self):
        assert assign_label("RETIRED") == "retired"

    def test_retired_with_reconstructible_still_retired(self):
        """RETIRED keeps its label even when reconstructible_candidate=True."""
        assert assign_label("RETIRED", reconstructible_candidate=True) == "retired"

    # rejected-registered
    def test_rejected_registered_returns_rejected_registered(self):
        assert assign_label("REJECTED_REGISTERED") == "rejected-registered"

    def test_rejected_registered_with_reconstructible_still_rejected_registered(self):
        assert assign_label("REJECTED_REGISTERED", reconstructible_candidate=True) == "rejected-registered"

    # observation
    def test_observation_returns_observation(self):
        assert assign_label("OBSERVATION") == "observation"

    def test_observation_with_reconstructible_still_observation(self):
        assert assign_label("OBSERVATION", reconstructible_candidate=True) == "observation"

    # no-data
    def test_unknown_state_returns_no_data(self):
        assert assign_label("UNKNOWN_STATE_XYZ") == "no-data"

    def test_empty_state_returns_no_data(self):
        assert assign_label("") == "no-data"

    # Purity: same inputs → same output
    def test_assign_label_is_deterministic(self):
        for _ in range(10):
            assert assign_label("ARTIFACT_ONLY") == "artifact-only"
            assert assign_label("ONLINE_ROW_BACKED", row_count=100) == "row-backed"

    def test_all_returned_labels_are_in_definitions(self):
        """Every label returned by assign_label must be a known label key."""
        inputs = [
            ("ONLINE_ROW_BACKED", 100, False, False, None),
            ("ONLINE_ROW_BACKED", 0,   False, False, None),
            ("ARTIFACT_ONLY",     0,   False, False, None),
            ("ARTIFACT_ONLY",     0,   True,  False, None),
            ("ARTIFACT_ONLY",     0,   False, True,  None),
            ("ARTIFACT_ONLY",     0,   False, False, "reason"),
            ("RETIRED",           0,   True,  False, None),
            ("REJECTED_REGISTERED", 0, True,  False, None),
            ("OBSERVATION",       0,   True,  False, None),
            ("TOTALLY_UNKNOWN",   0,   False, False, None),
        ]
        for rvs, rc, recon, manual, unsup in inputs:
            label = assign_label(rvs, rc, recon, manual, unsup)
            assert label in LABEL_DEFINITIONS, (
                f"assign_label({rvs!r}, ...) returned unknown label {label!r}"
            )


# ─── Section 3: is_row_backed() tests ────────────────────────────────────────

class TestIsRowBacked:

    def test_online_row_backed_with_rows_is_true(self):
        assert is_row_backed("ONLINE_ROW_BACKED", row_count=1570) is True

    def test_online_row_backed_no_rows_is_false(self):
        assert is_row_backed("ONLINE_ROW_BACKED", row_count=0) is False

    def test_artifact_only_is_false(self):
        assert is_row_backed("ARTIFACT_ONLY") is False

    def test_retired_is_false(self):
        assert is_row_backed("RETIRED") is False

    def test_rejected_registered_is_false(self):
        assert is_row_backed("REJECTED_REGISTERED") is False

    def test_observation_is_false(self):
        assert is_row_backed("OBSERVATION") is False

    def test_unknown_state_is_false(self):
        assert is_row_backed("UNKNOWN_STATE") is False


# ─── Section 4: P24 inventory integration tests ──────────────────────────────

@pytest.fixture(scope="module")
def p24_strategies() -> list[dict]:
    """Load all P24 strategies once per test module."""
    assert _P24_PATH.exists(), f"P24 inventory not found: {_P24_PATH}"
    with _P24_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["strategies"]


@pytest.fixture(scope="module")
def full_catalog() -> list[dict]:
    """Full P26 label catalog from get_full_label_catalog()."""
    return get_full_label_catalog()


class TestP24Integration:

    def test_p24_inventory_file_exists(self):
        assert _P24_PATH.exists()

    def test_p24_has_59_strategies(self, p24_strategies):
        assert len(p24_strategies) == _EXPECTED_TOTAL

    def test_full_catalog_has_59_entries(self, full_catalog):
        assert len(full_catalog) == _EXPECTED_TOTAL

    def test_8_online_strategies_are_row_backed(self, full_catalog):
        row_backed = [e for e in full_catalog if e["primary_label"] == "row-backed"]
        assert len(row_backed) == _EXPECTED_ROW_BACKED, (
            f"Expected {_EXPECTED_ROW_BACKED} row-backed, got {len(row_backed)}"
        )

    def test_41_artifact_only_strategies(self, full_catalog):
        artifact = [e for e in full_catalog if e["primary_label"] == "artifact-only"]
        assert len(artifact) == _EXPECTED_ARTIFACT

    def test_5_retired_strategies(self, full_catalog):
        retired = [e for e in full_catalog if e["primary_label"] == "retired"]
        assert len(retired) == _EXPECTED_RETIRED

    def test_4_rejected_registered_strategies(self, full_catalog):
        rejected = [e for e in full_catalog if e["primary_label"] == "rejected-registered"]
        assert len(rejected) == _EXPECTED_REJECTED_REG

    def test_1_observation_strategy(self, full_catalog):
        obs = [e for e in full_catalog if e["primary_label"] == "observation"]
        assert len(obs) == _EXPECTED_OBSERVATION

    def test_no_artifact_only_is_row_backed(self, full_catalog):
        artifact = [
            e for e in full_catalog
            if e["primary_label"] == "artifact-only" and e["is_row_backed"]
        ]
        assert artifact == [], f"Artifact-only strategies must not be row-backed: {artifact}"

    def test_no_retired_is_row_backed(self, full_catalog):
        bad = [
            e for e in full_catalog
            if e["primary_label"] == "retired" and e["is_row_backed"]
        ]
        assert bad == []

    def test_no_rejected_registered_is_row_backed(self, full_catalog):
        bad = [
            e for e in full_catalog
            if e["primary_label"] == "rejected-registered" and e["is_row_backed"]
        ]
        assert bad == []

    def test_no_observation_is_row_backed(self, full_catalog):
        bad = [
            e for e in full_catalog
            if e["primary_label"] == "observation" and e["is_row_backed"]
        ]
        assert bad == []

    def test_all_row_backed_strategies_have_positive_row_count(self, full_catalog):
        for e in full_catalog:
            if e["primary_label"] == "row-backed":
                assert e["row_count"] > 0, (
                    f"row-backed strategy {e['strategy_id']} has row_count=0"
                )

    def test_all_non_row_backed_have_zero_rows(self, full_catalog):
        for e in full_catalog:
            if e["primary_label"] != "row-backed":
                assert e["row_count"] == 0, (
                    f"Non-row-backed strategy {e['strategy_id']} has row_count={e['row_count']}"
                )

    def test_catalog_entries_have_required_fields(self, full_catalog):
        required = {
            "strategy_id", "lottery_type", "lifecycle_state",
            "replay_visibility_state", "row_count", "reconstructible_candidate",
            "primary_label", "label_display", "label_description",
            "is_row_backed", "queryable", "reason_text",
        }
        for entry in full_catalog:
            missing = required - set(entry.keys())
            assert not missing, (
                f"Entry {entry.get('strategy_id')} missing fields: {missing}"
            )

    def test_all_labels_in_catalog_are_known(self, full_catalog):
        for entry in full_catalog:
            lbl = entry["primary_label"]
            assert lbl in LABEL_DEFINITIONS, (
                f"{entry['strategy_id']} has unknown label {lbl!r}"
            )

    def test_queryable_matches_label_definition(self, full_catalog):
        for entry in full_catalog:
            lbl = entry["primary_label"]
            expected_queryable = LABEL_DEFINITIONS[lbl]["queryable"]
            assert entry["queryable"] == expected_queryable, (
                f"{entry['strategy_id']}: queryable={entry['queryable']} "
                f"but {lbl} definition says queryable={expected_queryable}"
            )

    def test_is_row_backed_matches_primary_label(self, full_catalog):
        for entry in full_catalog:
            if entry["primary_label"] == "row-backed":
                assert entry["is_row_backed"] is True
            else:
                assert entry["is_row_backed"] is False

    def test_catalog_preserves_strategy_id(self, full_catalog, p24_strategies):
        catalog_ids = {e["strategy_id"] for e in full_catalog}
        p24_ids     = {s["strategy_id"] for s in p24_strategies}
        assert catalog_ids == p24_ids

    def test_catalog_preserves_lottery_type(self, full_catalog, p24_strategies):
        p24_map = {s["strategy_id"]: s for s in p24_strategies}
        for entry in full_catalog:
            sid = entry["strategy_id"]
            assert entry["lottery_type"] == p24_map[sid]["lottery_type"]

    def test_catalog_preserves_reconstructible_candidate(self, full_catalog, p24_strategies):
        p24_map = {s["strategy_id"]: s for s in p24_strategies}
        for entry in full_catalog:
            sid = entry["strategy_id"]
            expected = bool(p24_map[sid].get("reconstructible_candidate"))
            assert entry["reconstructible_candidate"] == expected

    def test_reason_text_non_empty_for_all_entries(self, full_catalog):
        for entry in full_catalog:
            assert entry["reason_text"], (
                f"{entry['strategy_id']} has empty reason_text"
            )

    def test_label_display_matches_definition(self, full_catalog):
        for entry in full_catalog:
            lbl = entry["primary_label"]
            assert entry["label_display"] == LABEL_DEFINITIONS[lbl]["display"]

    def test_label_description_matches_definition(self, full_catalog):
        for entry in full_catalog:
            lbl = entry["primary_label"]
            assert entry["label_description"] == LABEL_DEFINITIONS[lbl]["description"]


# ─── Section 5: get_label_for_strategy() tests ───────────────────────────────

class TestGetLabelForStrategy:

    def test_known_online_strategy_returns_row_backed(self):
        entry = get_label_for_strategy("power_precision_3bet")
        assert entry is not None
        assert entry["primary_label"] == "row-backed"
        assert entry["is_row_backed"] is True

    def test_known_artifact_strategy_returns_artifact_only(self):
        entry = get_label_for_strategy("539_3bet_orthogonal")
        assert entry is not None
        assert entry["primary_label"] == "artifact-only"
        assert entry["is_row_backed"] is False

    def test_observation_strategy_h6_returns_observation(self):
        """h6_gate_mk20_ew85 is the known OBSERVATION strategy."""
        entry = get_label_for_strategy("h6_gate_mk20_ew85")
        assert entry is not None
        assert entry["primary_label"] == "observation"
        assert entry["is_row_backed"] is False

    def test_unknown_strategy_returns_none(self):
        result = get_label_for_strategy("strategy_that_does_not_exist_xyz")
        assert result is None

    def test_entry_has_required_fields(self):
        entry = get_label_for_strategy("power_precision_3bet")
        assert entry is not None
        assert "primary_label"   in entry
        assert "is_row_backed"   in entry
        assert "queryable"       in entry
        assert "reason_text"     in entry
        assert "label_display"   in entry


# ─── Section 6: get_label_summary() tests ────────────────────────────────────

class TestGetLabelSummary:

    def test_summary_returns_dict(self):
        summary = get_label_summary()
        assert isinstance(summary, dict)

    def test_summary_has_all_9_keys(self):
        summary = get_label_summary()
        for key in LABEL_DEFINITIONS:
            assert key in summary, f"Summary missing key '{key}'"

    def test_summary_row_backed_count(self):
        summary = get_label_summary()
        assert summary["row-backed"] == _EXPECTED_ROW_BACKED

    def test_summary_artifact_only_count(self):
        summary = get_label_summary()
        assert summary["artifact-only"] == _EXPECTED_ARTIFACT

    def test_summary_retired_count(self):
        summary = get_label_summary()
        assert summary["retired"] == _EXPECTED_RETIRED

    def test_summary_rejected_registered_count(self):
        summary = get_label_summary()
        assert summary["rejected-registered"] == _EXPECTED_REJECTED_REG

    def test_summary_observation_count(self):
        summary = get_label_summary()
        assert summary["observation"] == _EXPECTED_OBSERVATION

    def test_summary_total_equals_59(self):
        summary = get_label_summary()
        assert sum(summary.values()) == _EXPECTED_TOTAL


# ─── Section 7: build_label_entry() tests ────────────────────────────────────

class TestBuildLabelEntry:

    def test_online_strategy_entry(self):
        entry = build_label_entry({
            "strategy_id": "test_online",
            "replay_visibility_state": "ONLINE_ROW_BACKED",
            "row_count": 1500,
            "reconstructible_candidate": False,
            "needs_manual_review": False,
            "unsupported_reason": None,
            "lottery_type": "BIG_LOTTO",
            "lifecycle_state": "ONLINE",
        })
        assert entry["primary_label"] == "row-backed"
        assert entry["is_row_backed"] is True
        assert entry["queryable"] is True

    def test_artifact_only_entry(self):
        entry = build_label_entry({
            "strategy_id": "test_artifact",
            "replay_visibility_state": "ARTIFACT_ONLY",
            "row_count": 0,
            "reconstructible_candidate": False,
            "needs_manual_review": False,
            "unsupported_reason": None,
            "lottery_type": "DAILY_539",
            "lifecycle_state": "REJECTED",
        })
        assert entry["primary_label"] == "artifact-only"
        assert entry["is_row_backed"] is False
        assert entry["queryable"] is False

    def test_rejected_registered_entry_with_recon(self):
        entry = build_label_entry({
            "strategy_id": "test_rejected_reg",
            "replay_visibility_state": "REJECTED_REGISTERED",
            "row_count": 0,
            "reconstructible_candidate": True,
            "needs_manual_review": False,
            "unsupported_reason": None,
            "lottery_type": "BIG_LOTTO",
            "lifecycle_state": "REJECTED",
        })
        assert entry["primary_label"] == "rejected-registered"
        assert entry["reconstructible_candidate"] is True
        assert entry["is_row_backed"] is False


# ─── Section 8: Anti-contamination tests ─────────────────────────────────────

class TestAntiContamination:

    def test_label_module_has_no_sqlite3_import(self):
        """The label module must not import sqlite3 — no DB access."""
        import lottery_api.models.replay_strategy_state_labels as mod
        source = inspect.getsource(mod)
        # Must not contain sqlite3 import
        assert "import sqlite3" not in source
        assert "from sqlite3" not in source

    def test_label_module_has_no_database_manager_import(self):
        """The label module must not import DatabaseManager."""
        import lottery_api.models.replay_strategy_state_labels as mod
        source = inspect.getsource(mod)
        assert "DatabaseManager" not in source

    def test_label_module_has_no_db_write_calls(self):
        """No INSERT / UPDATE / DELETE / CREATE TABLE in the label module."""
        import lottery_api.models.replay_strategy_state_labels as mod
        source = inspect.getsource(mod).upper()
        forbidden = ["INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE"]
        for kw in forbidden:
            assert kw not in source, f"Forbidden SQL keyword '{kw}' in label module"

    def test_production_rows_unchanged(self):
        """Production DB must still have exactly 12460 rows."""
        assert _DB_PATH.exists(), f"DB not found: {_DB_PATH}"
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cur = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
            count = cur.fetchone()[0]
        finally:
            conn.close()
        assert count == _EXPECTED_DB_ROWS, (
            f"Production rows changed! Expected {_EXPECTED_DB_ROWS}, got {count}"
        )

    def test_assign_label_is_pure_same_output_repeated(self):
        """assign_label must be deterministic."""
        results = {assign_label("ARTIFACT_ONLY") for _ in range(5)}
        assert len(results) == 1

    def test_label_definitions_cannot_be_mutated_externally(self):
        """Modifying the get_label_definition() copy must not affect LABEL_DEFINITIONS."""
        copy = get_label_definition("retired")
        assert copy is not None
        original_queryable = LABEL_DEFINITIONS["retired"]["queryable"]
        copy["queryable"] = True  # attempt to mutate
        assert LABEL_DEFINITIONS["retired"]["queryable"] == original_queryable
