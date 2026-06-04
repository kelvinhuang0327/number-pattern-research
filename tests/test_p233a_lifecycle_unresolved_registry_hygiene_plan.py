"""
Targeted tests for P233A lifecycle-unresolved registry hygiene plan.

Covers:
  - Exactly 20 unresolved entries
  - No ONLINE/DEPLOYABLE/PROMOTE suggestion emitted
  - db_write_performed == false
  - registry_modified == false
  - Artifact JSON schema completeness
  - rejected/ archive cross-check: entries with archive file → REJECTED suggestion
  - Production-applied entries → RETIRED suggestion (not ONLINE/DEPLOYABLE)
  - Evidence-based: all entries have non-empty evidence_summary
  - All actions are ADD_NON_EXECUTABLE_STUB (no EXECUTABLE suggestion)
  - Deterministic output
  - Registry file NOT modified by this script
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from scripts import p233a_lifecycle_unresolved_registry_hygiene_plan as plan

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"
P232A_JSON = REPO_ROOT / "outputs" / "research" / (
    "p232a_all_catalog_strategy_replay_scoreboard_20260604.json"
)

FORBIDDEN_SUGGESTIONS = plan.FORBIDDEN_SUGGESTIONS

# ─── Static / schema tests ─────────────────────────────────────────────────────

def test_evidence_map_covers_all_20_entries():
    """_EVIDENCE_MAP must have exactly 20 entries — one per unresolved strategy."""
    assert len(plan._EVIDENCE_MAP) == 20, (
        f"Expected 20 evidence map entries, got {len(plan._EVIDENCE_MAP)}"
    )


def test_no_forbidden_suggestion_in_evidence_map():
    """No entry in _EVIDENCE_MAP may suggest a forbidden lifecycle."""
    for sid, ev in plan._EVIDENCE_MAP.items():
        sug = ev.get("suggested_lifecycle", "")
        assert sug not in FORBIDDEN_SUGGESTIONS, (
            f"Forbidden suggestion {sug!r} for {sid}"
        )


def test_all_actions_are_non_executable_stub():
    """Every evidence map entry must propose ADD_NON_EXECUTABLE_STUB."""
    for sid, ev in plan._EVIDENCE_MAP.items():
        action = ev.get("registry_action", "")
        assert action == "ADD_NON_EXECUTABLE_STUB", (
            f"{sid}: unexpected action {action!r} — must be ADD_NON_EXECUTABLE_STUB"
        )


def test_forbidden_suggestions_not_in_allowed():
    """FORBIDDEN and allowed suggestion sets must be disjoint."""
    allowed = {"RETIRED", "REJECTED", "OBSERVATION", "UNKNOWN_REQUIRES_REVIEW"}
    assert FORBIDDEN_SUGGESTIONS.isdisjoint(allowed)


def test_p232a_json_exists():
    assert P232A_JSON.exists(), "P232A scoreboard JSON must exist on main"


def test_p232a_has_20_unresolved():
    with open(P232A_JSON) as f:
        d = json.load(f)
    unres = [s for s in d["all_strategy_scoreboard"]
             if s["lifecycle_status"] == "LIFECYCLE_UNRESOLVED"]
    assert len(unres) == 20, f"Expected 20 LIFECYCLE_UNRESOLVED, got {len(unres)}"


# ─── Plan output tests ─────────────────────────────────────────────────────────

def test_plan_has_exactly_20_entries():
    result = plan.build_plan()
    assert result["unresolved_count"] == 20
    assert len(result["unresolved_entries"]) == 20


def test_plan_zero_db_write():
    result = plan.build_plan()
    assert result["db_write_performed"] is False
    assert result["db_rows_before"] == result["db_rows_after"]


def test_plan_registry_not_modified():
    """build_plan() must not modify the registry file."""
    before_mtime = REGISTRY_PATH.stat().st_mtime
    before_hash = hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    plan.build_plan()
    after_mtime = REGISTRY_PATH.stat().st_mtime
    after_hash = hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    assert before_hash == after_hash, "Registry file was modified!"
    # mtime check is supplementary (hash is authoritative)
    assert before_mtime == after_mtime or before_hash == after_hash


def test_no_forbidden_classification_in_output():
    result = plan.build_plan()
    for e in result["unresolved_entries"]:
        sug = e["suggested_lifecycle"]
        assert sug not in FORBIDDEN_SUGGESTIONS, (
            f"Forbidden suggestion {sug!r} for {e['strategy_id']}"
        )


def test_json_schema_completeness():
    result = plan.build_plan()
    required_top = {
        "execution_status", "db_read_only", "db_write_performed",
        "db_rows_before", "db_rows_after", "registry_modified",
        "unresolved_count", "lifecycle_suggestion_summary",
        "per_lottery_counts", "unresolved_entries",
        "p233b_allowlist_if_authorized", "caveats", "final_classification",
    }
    for key in required_top:
        assert key in result, f"Missing required key: {key}"
    assert result["db_read_only"] is True
    assert result["registry_modified"] is False
    assert len(result["caveats"]) >= 4


def test_each_entry_has_required_fields():
    result = plan.build_plan()
    required_entry = {
        "strategy_id", "lottery_type", "row_count", "distinct_target_draws",
        "bet_index_values", "mean_hit_count_row_level",
        "suggested_lifecycle", "evidence_summary",
        "registry_action", "has_rejected_archive",
    }
    for e in result["unresolved_entries"]:
        for field in required_entry:
            assert field in e, (
                f"Entry {e.get('strategy_id')} missing field: {field}"
            )
        assert e["evidence_summary"] not in (None, "", "No specific evidence found"), (
            f"{e['strategy_id']} has missing or default evidence_summary"
        )


def test_rejected_entries_have_archive_file():
    """Entries suggested as REJECTED must have a corresponding rejected/ JSON file."""
    result = plan.build_plan()
    for e in result["unresolved_entries"]:
        if e["suggested_lifecycle"] == "REJECTED":
            assert e["has_rejected_archive"] is True, (
                f"{e['strategy_id']} suggested REJECTED but has_rejected_archive=False"
            )


def test_retired_entries_do_not_require_archive():
    """RETIRED entries are production-applied (not rejected); archive may or may not exist."""
    result = plan.build_plan()
    retired = [e for e in result["unresolved_entries"] if e["suggested_lifecycle"] == "RETIRED"]
    assert len(retired) > 0, "Expected at least one RETIRED suggestion"
    for e in retired:
        # RETIRED = production applied, not formally rejected → archive typically absent
        assert e["suggested_lifecycle"] == "RETIRED"


def test_lifecycle_count_totals_to_20():
    result = plan.build_plan()
    s = result["lifecycle_suggestion_summary"]
    total = s.get("REJECTED", 0) + s.get("RETIRED", 0) + s.get("UNKNOWN_REQUIRES_REVIEW", 0)
    assert total == 20, f"Lifecycle suggestion counts {s} do not sum to 20"


def test_per_lottery_counts_sum_to_20():
    result = plan.build_plan()
    c = result["per_lottery_counts"]
    assert sum(c.values()) == 20


def test_expected_lifecycle_split():
    """12 REJECTED (have archive), 8 RETIRED (production-applied)."""
    result = plan.build_plan()
    s = result["lifecycle_suggestion_summary"]
    assert s["REJECTED"] == 12, f"Expected 12 REJECTED, got {s['REJECTED']}"
    assert s["RETIRED"] == 8, f"Expected 8 RETIRED, got {s['RETIRED']}"


def test_deterministic_rerun():
    r1 = plan.build_plan()
    r2 = plan.build_plan()
    assert r1["unresolved_count"] == r2["unresolved_count"]
    assert r1["lifecycle_suggestion_summary"] == r2["lifecycle_suggestion_summary"]
    ids_1 = [e["strategy_id"] for e in r1["unresolved_entries"]]
    ids_2 = [e["strategy_id"] for e in r2["unresolved_entries"]]
    assert ids_1 == ids_2
    sugs_1 = {e["strategy_id"]: e["suggested_lifecycle"] for e in r1["unresolved_entries"]}
    sugs_2 = {e["strategy_id"]: e["suggested_lifecycle"] for e in r2["unresolved_entries"]}
    assert sugs_1 == sugs_2
