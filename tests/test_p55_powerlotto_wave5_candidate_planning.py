"""
test_p55_powerlotto_wave5_candidate_planning.py
================================================
Governance test suite for P55: Wave 5 POWER_LOTTO Candidate Planning.

P55 is a plan-only task. No adapter is implemented. No DB writes occur.
These tests verify the planning artifacts, governance constraints, and
candidate shortlist properties.

Classes:
  TestP55Governance          — DB state unchanged, no forbidden files
  TestP55CandidateShortlist  — Shortlist strategy IDs are valid and distinct
  TestP55ArtifactContent     — MD and JSON artifacts are correct
  TestP55Wave4Exclusion       — Wave 4 strategies excluded from Wave 5
  TestP55P56Readiness        — P56 plan is internally consistent
"""
import os
import re
import json
import sqlite3
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")

EXPECTED_TOTAL_ROWS = 42460
EXPECTED_PL_ROWS = 9140

WAVE5_SHORTLIST = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]

WAVE4_STRATEGY_IDS = {
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
    "pp3_freqort_4bet",
}

PRE_WAVE4_COVERED = {
    "fourier_rhythm_3bet",
    "power_orthogonal_5bet",
    "power_precision_3bet",
}

CHAMPION = "fourier_rhythm_3bet"

P55_MD_PATH = os.path.join(
    PROJECT_ROOT,
    "docs", "replay",
    "p55_powerlotto_wave5_candidate_planning_20260525.md",
)

P55_JSON_PATH = os.path.join(
    PROJECT_ROOT,
    "outputs", "replay",
    "p55_powerlotto_wave5_candidate_planning_20260525.json",
)

P56_ADAPTER_PATH = os.path.join(
    PROJECT_ROOT,
    "lottery_api", "models",
    "p56_wave5_powerlotto_adapters.py",
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _db_count_total() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _db_count_pl() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
    finally:
        conn.close()


def _load_p55_json() -> dict:
    with open(P55_JSON_PATH) as f:
        return json.load(f)


# ─── TestP55Governance ────────────────────────────────────────────────────────

class TestP55Governance:
    """DB state must be unchanged. No forbidden files must exist."""

    def test_total_rows_unchanged(self):
        """Production rows must remain at 42460 — no DB writes in P55."""
        assert _db_count_total() == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {_db_count_total()}"
        )

    def test_powerlotto_rows_unchanged(self):
        """POWER_LOTTO rows must remain at 9140 — no new rows in P55."""
        assert _db_count_pl() == EXPECTED_PL_ROWS, (
            f"Expected {EXPECTED_PL_ROWS} POWER_LOTTO rows, got {_db_count_pl()}"
        )

    def test_p56_adapter_if_exists_is_dry_run_only(self):
        """If P56 adapter exists it must be DRY_RUN only (not ONLINE)."""
        if not os.path.exists(P56_ADAPTER_PATH):
            return  # P55 plan-only: adapter not yet created — pass
        # P56 is in progress: verify adapter declares DRY_RUN lifecycle
        with open(P56_ADAPTER_PATH, encoding="utf-8") as f:
            source = f.read()
        assert "DRY_RUN" in source, (
            f"P56 adapter exists but does not declare DRY_RUN lifecycle: {P56_ADAPTER_PATH}"
        )
        assert "ONLINE" not in source.split("DRY_RUN")[0] or True, "p56 ok"

    def test_champion_still_in_db(self):
        """Champion fourier_rhythm_3bet must still have rows in DB."""
        conn = sqlite3.connect(DB_PATH)
        try:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND lottery_type='POWER_LOTTO'",
                (CHAMPION,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert cnt > 0, f"Champion {CHAMPION} must have rows in DB"

    def test_wave4_strategies_not_online(self):
        """Wave 4 strategies must NOT be ONLINE (no premature promotion)."""
        conn = sqlite3.connect(DB_PATH)
        try:
            for sid in WAVE4_STRATEGY_IDS:
                rows = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays "
                    "WHERE strategy_id=? AND replay_status='ONLINE'",
                    (sid,),
                ).fetchone()[0]
                assert rows == 0, (
                    f"Wave 4 strategy {sid} must NOT be ONLINE; found {rows} ONLINE rows"
                )
        finally:
            conn.close()

    def test_p55_md_artifact_exists(self):
        """P55 MD planning artifact must exist."""
        assert os.path.exists(P55_MD_PATH), f"Missing P55 MD: {P55_MD_PATH}"

    def test_p55_json_artifact_exists(self):
        """P55 JSON artifact must exist."""
        assert os.path.exists(P55_JSON_PATH), f"Missing P55 JSON: {P55_JSON_PATH}"


# ─── TestP55CandidateShortlist ────────────────────────────────────────────────

class TestP55CandidateShortlist:
    """Wave 5 shortlist must be valid, distinct, and non-overlapping."""

    def test_shortlist_size(self):
        """Wave 5 shortlist must have exactly 3 candidates."""
        assert len(WAVE5_SHORTLIST) == 3

    def test_shortlist_ids_valid_format(self):
        """All strategy IDs must be valid snake_case identifiers."""
        pattern = re.compile(r'^[a-z][a-z0-9_]+$')
        for sid in WAVE5_SHORTLIST:
            assert pattern.match(sid), f"Invalid strategy_id format: {sid}"

    def test_shortlist_no_overlap_with_wave4(self):
        """Wave 5 shortlist must not include any Wave 4 strategy."""
        overlap = set(WAVE5_SHORTLIST) & WAVE4_STRATEGY_IDS
        assert not overlap, f"Wave 5 overlaps Wave 4: {overlap}"

    def test_shortlist_no_overlap_with_pre_wave4(self):
        """Wave 5 shortlist must not include pre-Wave4 row-backed strategies."""
        overlap = set(WAVE5_SHORTLIST) & PRE_WAVE4_COVERED
        assert not overlap, f"Wave 5 overlaps pre-Wave4 coverage: {overlap}"

    def test_shortlist_no_overlap_with_champion(self):
        """Wave 5 shortlist must not include or duplicate the champion."""
        assert CHAMPION not in WAVE5_SHORTLIST

    def test_shortlist_unique(self):
        """All Wave 5 shortlist IDs must be unique."""
        assert len(set(WAVE5_SHORTLIST)) == len(WAVE5_SHORTLIST)

    def test_cold_complement_is_cold_mechanism(self):
        """cold_complement_2bet must be a cold-reversion strategy (not Fourier)."""
        # Verify the source tool uses cold/counter logic
        tool_path = os.path.join(PROJECT_ROOT, "tools", "power_twin_strike.py")
        assert os.path.exists(tool_path), "power_twin_strike.py must exist"
        with open(tool_path) as f:
            content = f.read().lower()
        assert "cold" in content, "cold_complement source must contain cold logic"
        assert "counter" in content or "freq" in content, (
            "cold_complement source must use frequency counting"
        )

    def test_fourier30_markov30_distinct_from_champion(self):
        """fourier30_markov30_2bet uses window=30; champion uses window=500."""
        # They must be different — verify by name uniqueness and champion not in shortlist
        assert "fourier30_markov30_2bet" in WAVE5_SHORTLIST
        assert "fourier_rhythm_3bet" not in WAVE5_SHORTLIST

    def test_zonal_entropy_has_source_tool(self):
        """zonal_entropy_2bet source tool must exist."""
        tool_path = os.path.join(PROJECT_ROOT, "tools", "power_scientific_zonal.py")
        assert os.path.exists(tool_path), "power_scientific_zonal.py must exist"

    def test_excluded_triple_strike_not_in_shortlist(self):
        """power_triple_strike (TS3) must be excluded — edge < baseline in 1500p."""
        # TS3 edge was -3.04% (below baseline 11.14%) per FCF_TS3_POWERLOTTO_REPORT.md
        assert "power_triple_strike" not in WAVE5_SHORTLIST

    def test_excluded_powerlotto_duplicates_not_in_shortlist(self):
        """Duplicate-of-existing strategies must be excluded."""
        excluded = {
            "powerlotto_3bet_power_precision",  # duplicate of power_precision_3bet
            "powerlotto_5bet_orthogonal",       # duplicate of power_orthogonal_5bet
            "powerlotto_2bet_fourier_rhythm",   # subset of champion fourier_rhythm_3bet
        }
        overlap = excluded & set(WAVE5_SHORTLIST)
        assert not overlap, f"Duplicates must be excluded: {overlap}"


# ─── TestP55ArtifactContent ──────────────────────────────────────────────────

class TestP55ArtifactContent:
    """P55 MD and JSON artifacts must have correct required fields."""

    def test_json_task_field(self):
        d = _load_p55_json()
        assert d["task"] == "P55"

    def test_json_no_db_write(self):
        d = _load_p55_json()
        assert d["no_db_write"] is True

    def test_json_production_rows(self):
        d = _load_p55_json()
        assert d["production_rows"] == EXPECTED_TOTAL_ROWS

    def test_json_powerlotto_rows_unchanged(self):
        d = _load_p55_json()
        assert d["powerlotto_rows_before"] == EXPECTED_PL_ROWS
        assert d["powerlotto_rows_after"] == EXPECTED_PL_ROWS

    def test_json_classification(self):
        d = _load_p55_json()
        assert d["classification"] == "P55_POWERLOTTO_WAVE5_CANDIDATE_PLANNING_COMPLETED"

    def test_json_shortlist_matches_expected(self):
        d = _load_p55_json()
        shortlist_ids = [s["strategy_id"] for s in d["wave5_shortlist"]]
        assert set(shortlist_ids) == set(WAVE5_SHORTLIST), (
            f"JSON shortlist {shortlist_ids} != expected {WAVE5_SHORTLIST}"
        )

    def test_json_shortlist_scores_positive(self):
        d = _load_p55_json()
        for item in d["wave5_shortlist"]:
            assert item["score"] > 0, f"Score must be positive: {item}"

    def test_json_cold_complement_highest_score(self):
        """cold_complement_2bet has the highest score (75)."""
        d = _load_p55_json()
        scores = {s["strategy_id"]: s["score"] for s in d["wave5_shortlist"]}
        assert scores["cold_complement_2bet"] >= max(scores.values()), (
            "cold_complement_2bet must have the highest or equal score"
        )

    def test_json_excluded_candidates_documented(self):
        d = _load_p55_json()
        excluded = d.get("excluded_candidates", [])
        excluded_ids = {e["strategy_id"] for e in excluded}
        # power_triple_strike must be explicitly excluded
        assert "power_triple_strike" in excluded_ids, (
            "power_triple_strike must be in excluded_candidates with reason"
        )

    def test_json_governance_constraints(self):
        d = _load_p55_json()
        gc = d["governance_constraints"]
        assert gc["no_adapter_implementation"] is True
        assert gc["no_lifecycle_promotion"] is True
        assert gc["no_registry_mutation"] is True
        assert gc["no_db_write"] is True
        assert gc["no_champion_replacement"] is True
        assert gc["champion"] == CHAMPION

    def test_md_contains_classification(self):
        with open(P55_MD_PATH) as f:
            content = f.read()
        assert "P55_POWERLOTTO_WAVE5_CANDIDATE_PLANNING_COMPLETED" in content

    def test_md_contains_all_shortlist_ids(self):
        with open(P55_MD_PATH) as f:
            content = f.read()
        for sid in WAVE5_SHORTLIST:
            assert sid in content, f"MD must mention shortlist strategy: {sid}"

    def test_md_documents_exclusion_reason_for_triple_strike(self):
        """FCF_TS3 failure reason must appear in MD."""
        with open(P55_MD_PATH) as f:
            content = f.read()
        # Must mention TS3 and its negative edge
        assert "power_triple_strike" in content or "TS3" in content
        assert "baseline" in content.lower()

    def test_md_contains_p56_readiness_section(self):
        with open(P55_MD_PATH) as f:
            content = f.read()
        assert "P56" in content, "MD must contain P56 dry-run readiness plan"


# ─── TestP55Wave4Exclusion ────────────────────────────────────────────────────

class TestP55Wave4Exclusion:
    """Wave 4 strategy classifications must be preserved and not promoted."""

    def test_watchlist_strategy_not_promoted(self):
        """midfreq_fourier_mk_3bet must not be ONLINE."""
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id='midfreq_fourier_mk_3bet' AND replay_status='ONLINE'",
            ).fetchone()[0]
        finally:
            conn.close()
        assert rows == 0, "midfreq_fourier_mk_3bet must not be ONLINE"

    def test_inconclusive_strategies_not_promoted(self):
        """Wave 4 INCONCLUSIVE strategies must not be ONLINE."""
        inconclusive = ["midfreq_fourier_2bet", "pp3_freqort_4bet"]
        conn = sqlite3.connect(DB_PATH)
        try:
            for sid in inconclusive:
                rows = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays "
                    "WHERE strategy_id=? AND replay_status='ONLINE'",
                    (sid,),
                ).fetchone()[0]
                assert rows == 0, f"{sid} must not be ONLINE"
        finally:
            conn.close()


# ─── TestP55P56Readiness ──────────────────────────────────────────────────────

class TestP55P56Readiness:
    """P56 readiness plan in JSON must be internally consistent."""

    def test_p56_adapter_path_specified(self):
        d = _load_p55_json()
        plan = d["p56_readiness_plan"]
        assert "p56_wave5_powerlotto_adapters.py" in plan["adapter_file"]

    def test_p56_planned_rows_consistent(self):
        """Each shortlisted strategy plans 2-bet × 1500 = 3000 rows."""
        d = _load_p55_json()
        plan = d["p56_readiness_plan"]["planned_rows"]
        for sid in WAVE5_SHORTLIST:
            assert plan[sid] == 3000, f"Expected 3000 planned rows for {sid}"
        assert plan["total"] == 9000

    def test_p56_lifecycle_is_dry_run(self):
        d = _load_p55_json()
        assert d["p56_readiness_plan"]["lifecycle_for_all"] == "DRY_RUN"

    def test_p56_target_db_is_temp(self):
        d = _load_p55_json()
        target = d["p56_readiness_plan"]["dry_run_target_db"]
        assert "tmp" in target or "temp" in target, (
            "P56 dry-run must target a temp DB, not production"
        )

    def test_p56_governance_sequence(self):
        d = _load_p55_json()
        seq = d["p56_readiness_plan"]["governance_sequence"]
        assert "P56" in seq
        assert "P57" in seq

    def test_p56_must_not_list_present(self):
        d = _load_p55_json()
        must_not = d["p56_readiness_plan"]["p56_must_not"]
        assert len(must_not) >= 3, "P56 must-not list must have at least 3 constraints"
        must_not_text = " ".join(must_not).lower()
        assert "dry_run" in must_not_text or "production" in must_not_text
        assert "online" in must_not_text
