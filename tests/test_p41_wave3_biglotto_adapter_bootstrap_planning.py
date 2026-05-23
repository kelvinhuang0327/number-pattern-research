"""
test_p41_wave3_biglotto_adapter_bootstrap_planning.py
======================================================
Contract tests for P41 Wave 3 BIG_LOTTO Adapter Bootstrap Planning.

These tests verify that:
1. P41 output JSON exists at the expected path
2. P41 identifies exactly 6 BIG_LOTTO Wave 3 candidates
3. All 6 candidates have lottery_type = BIG_LOTTO
4. No DAILY_539 strategies appear in Wave 3 candidates
5. No manual_review or blocked strategies appear in Wave 3 candidates
6. Production rows are unchanged at 28960 (no dry-run rows generated)
7. P41 output documents special number handling
8. P41 output includes P42 recommended scope
9. P41 output includes future row estimate (clearly marked as estimate)
10. Bootstrap design documentation exists
"""
import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
P41_JSON = PROJECT_ROOT / "outputs" / "replay" / "p41_wave3_biglotto_adapter_bootstrap_planning_20260524.json"
P41_MD = PROJECT_ROOT / "docs" / "replay" / "p41_wave3_biglotto_adapter_bootstrap_planning_20260524.md"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_PRODUCTION_ROWS = 28960
EXPECTED_WAVE3_COUNT = 6
EXPECTED_WAVE3_LOTTERY_TYPE = "BIG_LOTTO"
EXPECTED_WAVE3_STRATEGY_IDS = {
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "bet2_fourier_expansion_biglotto",
    "fourier30_markov30_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p41_data() -> dict:
    """Load P41 output JSON."""
    assert P41_JSON.exists(), f"P41 JSON not found: {P41_JSON}"
    with open(P41_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def wave3_candidates(p41_data) -> list:
    """Extract wave3_candidates list from P41 output."""
    assert "wave3_candidates" in p41_data, "wave3_candidates key missing from P41 JSON"
    return p41_data["wave3_candidates"]


# ─── Test 1: P41 output JSON exists ──────────────────────────────────────────

def test_p41_json_exists():
    """P41 output JSON must exist at the expected path."""
    assert P41_JSON.exists(), f"P41 JSON not found at {P41_JSON}"


def test_p41_md_exists():
    """P41 planning document must exist at the expected path."""
    assert P41_MD.exists(), f"P41 MD not found at {P41_MD}"


def test_p41_json_valid(p41_data):
    """P41 JSON must be valid and have the expected classification."""
    assert "classification" in p41_data
    assert "P41" in p41_data["classification"]
    assert "BIGLOTTO" in p41_data["classification"].upper() or "BIG_LOTTO" in p41_data["classification"]


# ─── Test 2: Exactly 6 BIG_LOTTO Wave 3 candidates ──────────────────────────

def test_wave3_candidate_count(wave3_candidates):
    """P41 must identify exactly 6 Wave 3 candidates."""
    assert len(wave3_candidates) == EXPECTED_WAVE3_COUNT, (
        f"Expected {EXPECTED_WAVE3_COUNT} Wave 3 candidates, got {len(wave3_candidates)}"
    )


def test_wave3_strategy_ids_complete(wave3_candidates):
    """Wave 3 candidates must include exactly the 6 expected strategy IDs."""
    found_ids = {c["strategy_id"] for c in wave3_candidates}
    assert found_ids == EXPECTED_WAVE3_STRATEGY_IDS, (
        f"Wave 3 strategy IDs mismatch.\n"
        f"Expected: {sorted(EXPECTED_WAVE3_STRATEGY_IDS)}\n"
        f"Found:    {sorted(found_ids)}"
    )


# ─── Test 3: All candidates have lottery_type = BIG_LOTTO ───────────────────

def test_all_candidates_are_biglotto(wave3_candidates):
    """All 6 Wave 3 candidates must have lottery_type = BIG_LOTTO."""
    for candidate in wave3_candidates:
        assert candidate["lottery_type"] == EXPECTED_WAVE3_LOTTERY_TYPE, (
            f"Candidate {candidate['strategy_id']} has lottery_type={candidate['lottery_type']}, "
            f"expected {EXPECTED_WAVE3_LOTTERY_TYPE}"
        )


# ─── Test 4: No DAILY_539 strategies in Wave 3 candidates ───────────────────

def test_no_daily539_in_wave3(wave3_candidates):
    """No DAILY_539 strategies must appear in Wave 3 candidates."""
    daily_539_candidates = [
        c for c in wave3_candidates if c.get("lottery_type") == "DAILY_539"
    ]
    assert len(daily_539_candidates) == 0, (
        f"Found DAILY_539 strategies in Wave 3: {[c['strategy_id'] for c in daily_539_candidates]}"
    )


def test_no_daily539_ids_in_wave3(wave3_candidates):
    """No '539' in strategy_id for Wave 3 candidates."""
    for candidate in wave3_candidates:
        assert "539" not in candidate["strategy_id"], (
            f"Candidate {candidate['strategy_id']} appears to be a DAILY_539 strategy"
        )


# ─── Test 5: No manual_review or blocked strategies ─────────────────────────

def test_no_manual_review_in_wave3(p41_data, wave3_candidates):
    """No manual_review strategies in Wave 3 candidates."""
    # cluster_pivot_biglotto should be in manual_review or excluded, not wave3_candidates
    manual_review_ids = set()
    if "excluded_strategies" in p41_data:
        for strat_id, info in p41_data["excluded_strategies"].items():
            if "manual_review" in info.get("p35_recommendation", ""):
                manual_review_ids.add(strat_id)

    wave3_ids = {c["strategy_id"] for c in wave3_candidates}
    overlap = manual_review_ids & wave3_ids
    assert not overlap, f"Manual review strategies found in Wave 3: {overlap}"


def test_no_blocked_strategies_in_wave3(p41_data, wave3_candidates):
    """No blocked strategies in Wave 3 candidates."""
    blocked_ids = set()
    if "excluded_strategies" in p41_data:
        for strat_id, info in p41_data["excluded_strategies"].items():
            if info.get("p35_recommendation") == "block":
                blocked_ids.add(strat_id)

    wave3_ids = {c["strategy_id"] for c in wave3_candidates}
    overlap = blocked_ids & wave3_ids
    assert not overlap, f"Blocked strategies found in Wave 3: {overlap}"


def test_cluster_pivot_not_in_wave3(wave3_candidates):
    """cluster_pivot_biglotto (negative edge, SHORT_MOMENTUM) must not be in Wave 3."""
    wave3_ids = {c["strategy_id"] for c in wave3_candidates}
    assert "cluster_pivot_biglotto" not in wave3_ids, (
        "cluster_pivot_biglotto has negative edge (-0.45%) and must not be in Wave 3"
    )


def test_ts3_markov_not_in_wave3(wave3_candidates):
    """ts3_markov_freq_5bet_biglotto (SUPERSEDED) must not be in Wave 3."""
    wave3_ids = {c["strategy_id"] for c in wave3_candidates}
    assert "ts3_markov_freq_5bet_biglotto" not in wave3_ids, (
        "ts3_markov_freq_5bet_biglotto is SUPERSEDED and must not be in Wave 3"
    )


# ─── Test 6: Production rows unchanged at 28960 ─────────────────────────────

def test_production_rows_unchanged():
    """Production DB must still have 28960 rows — no dry-run rows generated."""
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
        count = cursor.fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_PRODUCTION_ROWS, (
        f"Production rows changed! Expected {EXPECTED_PRODUCTION_ROWS}, got {count}. "
        f"P41 must not generate any dry-run rows."
    )


def test_p41_declares_rows_unchanged(p41_data):
    """P41 JSON must declare production_rows_unchanged = 28960."""
    assert p41_data.get("production_rows_unchanged") == EXPECTED_PRODUCTION_ROWS, (
        f"P41 JSON declares production_rows_unchanged={p41_data.get('production_rows_unchanged')}, "
        f"expected {EXPECTED_PRODUCTION_ROWS}"
    )


# ─── Test 7: Special number handling documented ──────────────────────────────

def test_special_number_handling_documented(p41_data):
    """P41 must document special number handling for BIG_LOTTO."""
    assert "bootstrap_design" in p41_data, "bootstrap_design missing from P41 JSON"
    bootstrap = p41_data["bootstrap_design"]
    assert "special_number_scoring" in bootstrap or "key_differences_from_daily539" in bootstrap, (
        "Special number handling must be documented in bootstrap_design"
    )


def test_special_number_requirement_per_candidate(wave3_candidates):
    """Each Wave 3 candidate must document special_number_required or special_number_strategy."""
    for candidate in wave3_candidates:
        has_special_doc = (
            "special_number_required" in candidate or
            "special_number_strategy" in candidate
        )
        assert has_special_doc, (
            f"Candidate {candidate['strategy_id']} missing special number documentation"
        )


def test_wave3_special_prediction_is_null(wave3_candidates):
    """Wave 3 strategies do not predict the special number — should be documented as null/None/false."""
    for candidate in wave3_candidates:
        # special_number_required should be False, or special_number_strategy should indicate no prediction
        special_required = candidate.get("special_number_required", None)
        special_strategy = candidate.get("special_number_strategy", "")
        # Either explicitly false, or strategy indicates no prediction
        no_prediction = (
            special_required is False or
            "RANDOM_FROM_REMAINING" in str(special_strategy) or
            "no special" in str(special_strategy).lower() or
            "null" in str(special_strategy).lower() or
            "none" in str(special_strategy).lower()
        )
        assert no_prediction, (
            f"Candidate {candidate['strategy_id']} appears to claim special number prediction: "
            f"special_number_required={special_required}, special_number_strategy={special_strategy}"
        )


# ─── Test 8: P42 recommended scope included ─────────────────────────────────

def test_p42_recommended_scope_present(p41_data):
    """P41 must include P42 recommended scope."""
    assert "p42_recommended_scope" in p41_data, "p42_recommended_scope missing from P41 JSON"


def test_p42_scope_has_candidates(p41_data):
    """P42 recommended scope must list candidates."""
    scope = p41_data["p42_recommended_scope"]
    assert "candidates_recommended" in scope, "p42_recommended_scope missing candidates_recommended"
    assert len(scope["candidates_recommended"]) > 0, "p42_recommended_scope has empty candidates"


def test_p42_scope_matches_wave3(p41_data, wave3_candidates):
    """P42 recommended candidates should match the Wave 3 candidate IDs."""
    scope = p41_data["p42_recommended_scope"]
    p42_candidates = set(scope.get("candidates_recommended", []))
    wave3_ids = {c["strategy_id"] for c in wave3_candidates}
    # P42 candidates should be a subset of Wave 3 candidates
    assert p42_candidates.issubset(wave3_ids), (
        f"P42 candidates not subset of Wave 3: extra={p42_candidates - wave3_ids}"
    )


def test_p42_has_stop_condition(p41_data):
    """P42 scope must include STOP condition (no production apply)."""
    scope = p41_data["p42_recommended_scope"]
    stop_condition = scope.get("stop_condition", "")
    assert "STOP" in stop_condition.upper() or "production apply" in stop_condition.lower(), (
        "P42 scope missing STOP condition before production apply"
    )


# ─── Test 9: Future row estimate clearly marked as ESTIMATE ─────────────────

def test_row_estimate_present(p41_data):
    """P41 must include a future row estimate."""
    scope = p41_data["p42_recommended_scope"]
    has_estimate = (
        "total_estimated_rows" in scope or
        "expected_dry_run_rows" in scope or
        "rows_per_strategy" in scope
    )
    assert has_estimate, "P41 P42 scope missing row estimate"


def test_row_estimate_marked_as_estimate(p41_data):
    """Row estimate must be clearly marked as ESTIMATE ONLY."""
    scope = p41_data["p42_recommended_scope"]
    note = scope.get("note", "")
    assert "ESTIMATE" in note.upper() or "not applied" in note.lower(), (
        f"Row estimate note must say ESTIMATE ONLY / not applied. Got: '{note}'"
    )


def test_row_estimate_value(p41_data):
    """Row estimate should be 9000 (6 strategies × 1500 rows)."""
    scope = p41_data["p42_recommended_scope"]
    total = scope.get("total_estimated_rows")
    rows_per = scope.get("rows_per_strategy", 1500)
    count = scope.get("candidate_count", EXPECTED_WAVE3_COUNT)
    if total is not None:
        assert total == rows_per * count, (
            f"total_estimated_rows={total} does not match {rows_per} × {count} = {rows_per * count}"
        )


# ─── Test 10: Bootstrap design documentation exists ─────────────────────────

def test_bootstrap_design_exists(p41_data):
    """P41 must include bootstrap_design section."""
    assert "bootstrap_design" in p41_data, "bootstrap_design missing from P41 JSON"


def test_bootstrap_design_has_main_numbers(p41_data):
    """Bootstrap design must document main number format (6 ints in [1,49])."""
    bootstrap = p41_data["bootstrap_design"]
    # Check for any reference to 6-number or [1,49] range
    bootstrap_str = json.dumps(bootstrap)
    assert (
        "6" in bootstrap_str and "49" in bootstrap_str
    ), "Bootstrap design must reference 6 main numbers in [1,49]"


def test_bootstrap_design_has_cutoff_semantics(p41_data):
    """Bootstrap design must document cutoff semantics."""
    bootstrap = p41_data["bootstrap_design"]
    assert "cutoff_semantics" in bootstrap or "cutoff" in json.dumps(bootstrap).lower(), (
        "Bootstrap design must document cutoff semantics"
    )


def test_bootstrap_design_has_lifecycle(p41_data):
    """Bootstrap design must document DRY_RUN lifecycle."""
    bootstrap = p41_data["bootstrap_design"]
    bootstrap_str = json.dumps(bootstrap)
    assert "DRY_RUN" in bootstrap_str, "Bootstrap design must document DRY_RUN lifecycle"


def test_bootstrap_design_no_registry_mutation(p41_data):
    """Bootstrap design must document that adapters are NOT registered in _ALL_ADAPTERS."""
    bootstrap = p41_data["bootstrap_design"]
    bootstrap_str = json.dumps(bootstrap).lower()
    # Should mention not registering / forbidden
    lifecycle_info = bootstrap.get("lifecycle_flow", {})
    lifecycle_str = json.dumps(lifecycle_info).lower()
    forbidden = (
        "not registered" in lifecycle_str or
        "forbidden" in lifecycle_str or
        "_all_adapters" in lifecycle_str or
        "registry" in lifecycle_str
    )
    assert forbidden, (
        "Bootstrap design must state that adapters are NOT registered in _ALL_ADAPTERS"
    )


# ─── Additional contract tests ───────────────────────────────────────────────

def test_all_candidates_have_source_artifact(wave3_candidates):
    """Each Wave 3 candidate must document its source artifact."""
    for candidate in wave3_candidates:
        assert "source_artifact" in candidate and candidate["source_artifact"], (
            f"Candidate {candidate['strategy_id']} missing source_artifact"
        )


def test_all_candidates_have_min_history(wave3_candidates):
    """Each Wave 3 candidate must document min_history_requirement."""
    for candidate in wave3_candidates:
        assert "min_history_requirement" in candidate, (
            f"Candidate {candidate['strategy_id']} missing min_history_requirement"
        )
        assert candidate["min_history_requirement"] >= 1500, (
            f"Candidate {candidate['strategy_id']} min_history_requirement < 1500"
        )


def test_all_candidates_have_expected_dry_run_rows(wave3_candidates):
    """Each Wave 3 candidate must document expected_dry_run_rows."""
    for candidate in wave3_candidates:
        assert "expected_dry_run_rows" in candidate, (
            f"Candidate {candidate['strategy_id']} missing expected_dry_run_rows"
        )
        assert candidate["expected_dry_run_rows"] == 1500, (
            f"Candidate {candidate['strategy_id']} expected_dry_run_rows != 1500"
        )


def test_no_adapter_implementation_committed():
    """P41 must NOT have added p42_wave3_biglotto_adapters.py (forbidden)."""
    forbidden_file = PROJECT_ROOT / "lottery_api" / "models" / "p42_wave3_biglotto_adapters.py"
    assert not forbidden_file.exists(), (
        "p42_wave3_biglotto_adapters.py was created during P41 — this is forbidden. "
        "P41 is read-only planning. Adapter implementation belongs in P42."
    )


def test_no_biglotto_wave3_dryrun_rows():
    """No Wave 3 BIG_LOTTO dry-run rows must exist in production DB."""
    wave3_ids = list(EXPECTED_WAVE3_STRATEGY_IDS)
    placeholders = ",".join(f"'{sid}'" for sid in wave3_ids)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM strategy_prediction_replays "
            f"WHERE lottery_type='BIG_LOTTO' AND strategy_id IN ({placeholders});"
        )
        count = cursor.fetchone()[0]
    finally:
        conn.close()
    assert count == 0, (
        f"Found {count} Wave 3 BIG_LOTTO rows in production DB. "
        "P41 is read-only — no rows should have been generated."
    )


def test_p41_classification_string(p41_data):
    """P41 JSON classification must match expected format."""
    classification = p41_data.get("classification", "")
    assert "P41" in classification
    assert "BIGLOTTO" in classification.upper() or "BIG_LOTTO" in classification
    assert "PLANNING" in classification.upper()


def test_p41_note_is_read_only(p41_data):
    """P41 JSON note must state read-only / no DB write."""
    note = p41_data.get("note", "").lower()
    assert "read-only" in note or "no db write" in note or "no adapter" in note, (
        f"P41 note must state READ-ONLY. Got: '{note}'"
    )
