"""
Targeted tests for P232A all-catalog strategy historical replay scoreboard.

Covers:
  - Zero DB write / no-write guarantee
  - Output JSON schema completeness
  - All catalog strategies included even with zero replay rows
  - DB-only strategies included as LIFECYCLE_UNRESOLVED
  - lifecycle is label only, not filter (no strategy hidden by lifecycle)
  - No-row strategies appear with row_count=0 and NO_REPLAY_ROWS
  - Per-lottery presence (BIG_LOTTO / DAILY_539 / POWER_LOTTO; 3_STAR/4_STAR note)
  - Row-level vs draw-level fields are separate and populated
  - bet_index distribution exists for replay-backed strategies
  - Second-zone is DISPLAY_ONLY and separate from classification
  - No forbidden (deployable/promote) classifications emitted
  - Deterministic output (rerun produces same result)
  - Classification vocabulary is only the allowed set
  - Baseline values are correctly computed for known lotteries
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("numpy")  # P47 adapters use numpy; skip cleanly if absent

from scripts import p232a_all_catalog_strategy_replay_scoreboard as sb

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

ALLOWED_CLASSIFICATIONS = frozenset({
    "HISTORICAL_REPLAY_ONLY",
    "NULL_OR_BASELINE_LIKE",
    "WEAK_OBSERVATION_ONLY",
    "INSUFFICIENT_ROWS",
    "NO_REPLAY_ROWS",
    "LIFECYCLE_UNRESOLVED",
})
FORBIDDEN_CLASSIFICATIONS = sb.FORBIDDEN_CLASSIFICATIONS


# ─── DB availability guard ────────────────────────────────────────────────────

def _db_available() -> bool:
    """Return True if the DB can be opened for reading right now."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("SELECT 1 FROM strategy_prediction_replays LIMIT 1").fetchone()
        conn.close()
        return True
    except sqlite3.OperationalError:
        return False


_db_skip = pytest.mark.skipif(
    not _db_available(),
    reason="production DB not accessible right now (WAL/live backend)",
)


# ─── Catalog-only (no DB) tests ───────────────────────────────────────────────

def test_registry_catalog_not_empty():
    """Main registry returns at least one entry per lifecycle class."""
    entries = sb.load_registry_catalog()
    assert len(entries) >= 8, "Expected at least 8 catalog entries"
    lifecycles = {e["lifecycle_status"] for e in entries}
    assert "ONLINE" in lifecycles
    assert "RETIRED" in lifecycles or "REJECTED" in lifecycles


def test_p47_catalog_all_power_lotto():
    """All P47 Wave4 adapters are for POWER_LOTTO and have DRY_RUN lifecycle."""
    entries = sb.load_p47_catalog()
    assert entries, "P47 catalog must not be empty"
    for e in entries:
        assert e["lottery_type"] == "POWER_LOTTO", (
            f"P47 entry {e['strategy_id']} has unexpected lottery_type {e['lottery_type']}"
        )
        assert e["lifecycle_status"] == sb._DRY_RUN_LIFECYCLE


def test_forbidden_classifications_never_emitted():
    """The FORBIDDEN_CLASSIFICATIONS set must not overlap with ALLOWED_CLASSIFICATIONS."""
    assert FORBIDDEN_CLASSIFICATIONS.isdisjoint(ALLOWED_CLASSIFICATIONS), (
        "A classification is in both allowed and forbidden sets — logic error."
    )


def test_classification_only_no_replay_for_empty_metrics():
    """_classify returns NO_REPLAY_ROWS when replay_presence is False."""
    entry = {"lifecycle_status": "ONLINE"}
    metrics = {"replay_presence": False}
    cls = sb._classify(entry, metrics, "BIG_LOTTO")
    assert cls == "NO_REPLAY_ROWS"


def test_classification_unresolved_for_db_only():
    """_classify returns LIFECYCLE_UNRESOLVED for DB-only strategies."""
    entry = {"lifecycle_status": sb._UNRESOLVED_LIFECYCLE}
    metrics = {
        "replay_presence": True,
        "distinct_target_draws": 200,
        "row_level": {"mean_hit_count": 1.0},
    }
    cls = sb._classify(entry, metrics, "BIG_LOTTO")
    assert cls == "LIFECYCLE_UNRESOLVED"


def test_baselines_known_lotteries():
    """Verify the mean_hit baselines match the published lottery rules."""
    assert abs(sb.MEAN_HIT_BASELINES["BIG_LOTTO"]["mean_hit"] - 36 / 49) < 1e-9
    assert abs(sb.MEAN_HIT_BASELINES["POWER_LOTTO"]["mean_hit"] - 36 / 38) < 1e-9
    assert abs(sb.MEAN_HIT_BASELINES["DAILY_539"]["mean_hit"] - 25 / 39) < 1e-9


def test_special_baseline_power_lotto():
    assert abs(sb.SPECIAL_BASELINE["POWER_LOTTO"] - 1.0 / 8.0) < 1e-9


# ─── Full scoreboard tests (require DB) ───────────────────────────────────────

@_db_skip
def test_zero_db_write():
    """Running the scoreboard must not change the DB row count."""
    before = sb.total_replay_rows(DB_PATH)
    result = sb.build_scoreboard(DB_PATH)
    after = sb.total_replay_rows(DB_PATH)
    assert before == after, f"Row count changed: {before} -> {after}"
    assert result["db_write_performed"] is False
    assert result["db_rows_before"] == result["db_rows_after"]


@_db_skip
def test_json_schema_completeness():
    """Output JSON must contain all required top-level fields."""
    result = sb.build_scoreboard(DB_PATH)
    required = {
        "execution_status", "db_read_only", "db_write_performed",
        "db_rows_before", "db_rows_after",
        "total_catalog_strategy_count", "total_replay_strategy_count",
        "total_no_replay_count", "total_strategy_count_after_union",
        "unresolved_lifecycle_count", "per_lottery_counts", "lifecycle_counts",
        "all_strategy_scoreboard", "caveats", "final_classification",
    }
    for key in required:
        assert key in result, f"Missing required JSON key: {key}"
    assert result["db_read_only"] is True
    assert isinstance(result["caveats"], list) and len(result["caveats"]) > 0
    assert isinstance(result["all_strategy_scoreboard"], list)
    assert len(result["all_strategy_scoreboard"]) > 0


@_db_skip
def test_catalog_strategies_included_with_zero_rows():
    """Every catalog-registered strategy must appear in the scoreboard, including no-row entries."""
    result = sb.build_scoreboard(DB_PATH)
    catalog_entries = sb.load_registry_catalog() + sb.load_p47_catalog()
    scoreboard_keys = {
        (s["strategy_id"], s["lottery_type"])
        for s in result["all_strategy_scoreboard"]
    }
    for ce in catalog_entries:
        key = (ce["strategy_id"], ce["lottery_type"])
        assert key in scoreboard_keys, (
            f"Catalog entry {key} not found in scoreboard. "
            "lifecycle must not exclude strategies."
        )


@_db_skip
def test_no_row_strategies_have_row_count_zero():
    """Strategies with no replay rows must appear with row_count=0 and NO_REPLAY_ROWS classification."""
    result = sb.build_scoreboard(DB_PATH)
    no_replay = [s for s in result["all_strategy_scoreboard"] if not s["replay_presence"]]
    assert len(no_replay) > 0, "Expected some no-replay strategies (REJECTED/OBSERVATION)"
    for s in no_replay:
        assert s["row_count"] == 0, f"{s['strategy_id']} has row_count != 0 but replay_presence=False"
        assert s["distinct_target_draws"] == 0
        assert s["historical_classification"] == "NO_REPLAY_ROWS", (
            f"{s['strategy_id']} classification is {s['historical_classification']}, expected NO_REPLAY_ROWS"
        )


@_db_skip
def test_db_only_strategies_lifecycle_unresolved():
    """Strategies in DB but not in catalog must have LIFECYCLE_UNRESOLVED."""
    result = sb.build_scoreboard(DB_PATH)
    db_pairs = set(sb.load_db_strategy_pairs(DB_PATH))
    catalog_entries = sb.load_registry_catalog() + sb.load_p47_catalog()
    catalog_keys = {(e["strategy_id"], e["lottery_type"]) for e in catalog_entries}
    db_only_keys = db_pairs - catalog_keys
    assert len(db_only_keys) > 0, "Expected some DB-only strategies"

    unresolved_keys = {
        (s["strategy_id"], s["lottery_type"])
        for s in result["all_strategy_scoreboard"]
        if s["lifecycle_status"] == sb._UNRESOLVED_LIFECYCLE
    }
    for key in db_only_keys:
        assert key in unresolved_keys, (
            f"DB-only strategy {key} is not marked LIFECYCLE_UNRESOLVED"
        )


@_db_skip
def test_lifecycle_is_label_not_filter():
    """All lifecycle values present in catalog must appear in the scoreboard output."""
    result = sb.build_scoreboard(DB_PATH)
    catalog_lifecycles = {
        e["lifecycle_status"]
        for e in sb.load_registry_catalog() + sb.load_p47_catalog()
    }
    scoreboard_lifecycles = {
        s["lifecycle_status"]
        for s in result["all_strategy_scoreboard"]
        if s["registry_presence"]
    }
    for lc in catalog_lifecycles:
        assert lc in scoreboard_lifecycles, (
            f"Lifecycle {lc!r} present in catalog but absent from scoreboard. "
            "lifecycle must be a label, not a filter."
        )


@_db_skip
def test_per_lottery_presence():
    """BIG_LOTTO, DAILY_539, POWER_LOTTO must all appear in the scoreboard."""
    result = sb.build_scoreboard(DB_PATH)
    lt_present = {s["lottery_type"] for s in result["all_strategy_scoreboard"]}
    for required_lt in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO"):
        assert required_lt in lt_present, f"{required_lt} missing from scoreboard"


@_db_skip
def test_row_level_and_draw_level_are_separate():
    """Replay-backed strategies must have both row_level and draw_level fields."""
    result = sb.build_scoreboard(DB_PATH)
    replay_entries = [s for s in result["all_strategy_scoreboard"] if s["replay_presence"]]
    assert replay_entries, "Expected at least one replay-backed strategy"
    for s in replay_entries:
        assert "row_level" in s and s["row_level"] is not None, (
            f"{s['strategy_id']} missing row_level"
        )
        assert "draw_level" in s and s["draw_level"] is not None, (
            f"{s['strategy_id']} missing draw_level"
        )
        rl = s["row_level"]
        dl = s["draw_level"]
        # Row-level uses n_predicted; draw-level uses n_predicted_draws
        assert "n_predicted" in rl
        assert "n_predicted_draws" in dl
        # They should not be the same field name (they measure different things)
        assert "mean_hit_count" in rl
        assert "mean_best_hit_count" in dl


@_db_skip
def test_bet_index_distribution_for_replay_strategies():
    """Each replay-backed strategy must have a non-empty bet_index_values list."""
    result = sb.build_scoreboard(DB_PATH)
    for s in result["all_strategy_scoreboard"]:
        if s["replay_presence"]:
            bi = s.get("bet_index_values")
            assert bi is not None and len(bi) > 0, (
                f"{s['strategy_id']} / {s['lottery_type']} missing bet_index_values"
            )
            assert s.get("per_bet_index") is not None


@_db_skip
def test_second_zone_display_only():
    """Second-zone field must be present and never used in classification."""
    result = sb.build_scoreboard(DB_PATH)
    for s in result["all_strategy_scoreboard"]:
        if s["replay_presence"]:
            sz = s.get("second_zone_display_only")
            assert sz is not None, f"{s['strategy_id']} missing second_zone_display_only"
            note = sz.get("note", "")
            assert "DISPLAY ONLY" in note.upper() or "display only" in note.lower(), (
                f"second_zone note does not say DISPLAY ONLY: {note!r}"
            )
        # Verify second-zone is never used in the classification field
        cls = s.get("historical_classification", "")
        assert "SECOND_ZONE" not in cls.upper()
        assert "SPECIAL" not in cls.upper()


@_db_skip
def test_no_forbidden_classifications():
    """No scoreboard entry may have a forbidden classification."""
    result = sb.build_scoreboard(DB_PATH)
    bad = [
        (s["strategy_id"], s["lottery_type"], s["historical_classification"])
        for s in result["all_strategy_scoreboard"]
        if s.get("historical_classification") in FORBIDDEN_CLASSIFICATIONS
    ]
    assert not bad, f"Forbidden classifications found: {bad}"


@_db_skip
def test_all_classifications_in_allowed_set():
    """Every emitted classification must be in the ALLOWED_CLASSIFICATIONS set."""
    result = sb.build_scoreboard(DB_PATH)
    for s in result["all_strategy_scoreboard"]:
        cls = s.get("historical_classification")
        assert cls in ALLOWED_CLASSIFICATIONS, (
            f"Unknown classification {cls!r} for {s['strategy_id']} / {s['lottery_type']}"
        )


@_db_skip
def test_deterministic_rerun():
    """Running the scoreboard twice must produce identical strategy counts."""
    r1 = sb.build_scoreboard(DB_PATH)
    r2 = sb.build_scoreboard(DB_PATH)
    assert r1["total_strategy_count_after_union"] == r2["total_strategy_count_after_union"]
    assert r1["total_replay_strategy_count"] == r2["total_replay_strategy_count"]
    assert r1["total_no_replay_count"] == r2["total_no_replay_count"]
    assert r1["lifecycle_counts"] == r2["lifecycle_counts"]
    assert r1["per_lottery_counts"] == r2["per_lottery_counts"]
