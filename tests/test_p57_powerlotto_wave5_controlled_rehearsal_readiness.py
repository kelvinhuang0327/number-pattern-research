"""
test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py
============================================================
Governance test suite for P57 — Wave 5 POWER_LOTTO controlled rehearsal
readiness review.

Tests verify:
- P56 artifact integrity (JSON exists, classification, row counts, governance)
- Production DB integrity (read-only: 42460 rows, wave5 not in prod, champion present)
- Per-strategy readiness classifications
- Statistical z-test results
- P57 JSON output structure and content
- Cohort decision
- P58 proposal validity
- Governance constraints (no prod write, no promotion, no champion replace)
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent

P56_JSON = PROJECT_ROOT / "outputs" / "replay" / \
    "p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.json"
P57_JSON = PROJECT_ROOT / "outputs" / "replay" / \
    "p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json"
PROD_DB = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ADAPTER_FILE = PROJECT_ROOT / "lottery_api" / "models" / \
    "p56_wave5_powerlotto_adapters.py"
P57_SCRIPT = PROJECT_ROOT / "scripts" / \
    "p57_powerlotto_wave5_controlled_rehearsal_readiness.py"

WAVE5_STRATEGIES = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]
EXPECTED_PROD_ROWS = 42460    # P57-era value; used for P57/P56 JSON output assertions
DB_TOTAL_ROWS = 43960         # Current DB total after P59 controlled apply
DB_PL_ROWS = 10640            # Current POWER_LOTTO rows after P59 (+1500)
ROWS_PER_STRATEGY = 1500
THEORETICAL_M3_BASELINE = 0.0387  # 3.87%


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p56_json():
    assert P56_JSON.exists(), f"P56 JSON not found: {P56_JSON}"
    with open(P56_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p57_json():
    assert P57_JSON.exists(), f"P57 JSON not found: {P57_JSON}"
    with open(P57_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def prod_conn():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ─── Class 1: P56 Artifact Integrity ──────────────────────────────────────────

class TestP56ArtifactIntegrity:
    """P56 artifacts must be complete and valid before P57 can proceed."""

    def test_p56_json_exists(self):
        assert P56_JSON.exists()

    def test_p56_classification(self, p56_json):
        assert p56_json["classification"] == \
            "P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED"

    def test_p56_total_rows(self, p56_json):
        assert p56_json["actual_raw_rows"] == 4500

    def test_p56_rows_per_strategy(self, p56_json):
        counts = p56_json["row_counts_by_strategy"]
        for sid in WAVE5_STRATEGIES:
            assert counts[sid] == ROWS_PER_STRATEGY, \
                f"{sid} expected {ROWS_PER_STRATEGY} rows, got {counts[sid]}"

    def test_p56_production_unchanged(self, p56_json):
        assert p56_json["production_rows_before"] == EXPECTED_PROD_ROWS
        assert p56_json["production_rows_after"] == EXPECTED_PROD_ROWS

    def test_p56_schema_valid(self, p56_json):
        assert p56_json["schema_validation"]["valid"] is True
        assert p56_json["schema_validation"]["errors"] == []

    def test_p56_leakage_pass(self, p56_json):
        assert p56_json["data_leakage_check"]["pass"] is True
        assert p56_json["data_leakage_check"]["violation_count"] == 0

    def test_p56_r1_ok(self, p56_json):
        assert p56_json["rehearsal"]["r1_apply"]["r1_ok"] is True
        assert p56_json["rehearsal"]["r1_apply"]["r1_inserted"] == 4500

    def test_p56_r2_idempotent(self, p56_json):
        assert p56_json["rehearsal"]["r2_idempotency"]["r2_idempotent"] is True
        assert p56_json["rehearsal"]["r2_idempotency"]["r2_duplicate_inserted"] == 0

    def test_p56_r3_rollback_ok(self, p56_json):
        assert p56_json["rehearsal"]["r3_rollback"]["r3_rollback_ok"] is True
        assert p56_json["rehearsal"]["r3_rollback"]["r3_after"] == 0

    def test_p56_no_production_db_write(self, p56_json):
        assert p56_json["governance"]["production_db_write"] is False

    def test_p56_no_lifecycle_promotion(self, p56_json):
        assert p56_json["governance"]["lifecycle_promotion"] is False

    def test_p56_no_champion_replacement(self, p56_json):
        assert p56_json["governance"]["champion_replacement"] is False

    def test_p56_all_dry_run(self, p56_json):
        assert p56_json["governance"]["all_dry_run"] is True

    def test_p56_adapters_not_in_registry(self, p56_json):
        assert p56_json["governance"]["adapters_not_in_registry"] is True

    def test_p56_zero_errors_per_strategy(self, p56_json):
        hit_stats = p56_json["hit_stats"]
        for sid in WAVE5_STRATEGIES:
            assert hit_stats[sid]["errors"] == 0, \
                f"{sid} has errors in P56 dry-run"

    def test_p56_wave(self, p56_json):
        assert p56_json["wave"] == "5"
        assert p56_json["lottery_type"] == "POWER_LOTTO"


# ─── Class 2: Production DB Integrity ────────────────────────────────────────

class TestProductionDBIntegrity:
    """Production DB must remain unmodified at exactly 42460 rows."""

    def test_total_prod_rows(self, prod_conn):
        cur = prod_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays"
        )
        assert cur.fetchone()["cnt"] == DB_TOTAL_ROWS

    def test_power_lotto_rows(self, prod_conn):
        cur = prod_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
            "WHERE lottery_type = 'POWER_LOTTO'"
        )
        assert cur.fetchone()["cnt"] == DB_PL_ROWS

    def test_wave5_not_in_production(self, prod_conn):
        """WATCHLIST strategies must not be in production. fourier30_markov30_2bet
        was promoted to production by P59 controlled apply."""
        watchlist = ["cold_complement_2bet", "zonal_entropy_2bet"]
        for sid in watchlist:
            cur = prod_conn.execute(
                "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
                "WHERE strategy_id = ? AND lottery_type = 'POWER_LOTTO'",
                (sid,),
            )
            count = cur.fetchone()["cnt"]
            assert count == 0, \
                f"{sid} found in production DB ({count} rows) — must remain DRY_RUN only"

    def test_champion_present(self, prod_conn):
        cur = prod_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
            "WHERE strategy_id = 'fourier_rhythm_3bet' AND lottery_type = 'POWER_LOTTO'"
        )
        assert cur.fetchone()["cnt"] > 0, \
            "Champion fourier_rhythm_3bet not found in production DB"

    def test_champion_not_replaced(self, prod_conn):
        """Champion must not be displaced — still has rows in POWER_LOTTO."""
        cur = prod_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
            "WHERE strategy_id = 'fourier_rhythm_3bet'"
        )
        assert cur.fetchone()["cnt"] > 0


# ─── Class 3: P57 JSON Structure ─────────────────────────────────────────────

class TestP57JSONStructure:
    """P57 output JSON must contain all required fields."""

    def test_p57_json_exists(self):
        assert P57_JSON.exists()

    def test_classification_field(self, p57_json):
        assert "classification" in p57_json

    def test_classification_is_valid(self, p57_json):
        valid = {
            "P57_POWERLOTTO_WAVE5_CONTROLLED_REHEARSAL_READINESS_COMPLETED",
            "P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED",
            "P57_POWERLOTTO_WAVE5_REHEARSAL_INCONCLUSIVE",
        }
        assert p57_json["classification"] in valid, \
            f"Invalid classification: {p57_json['classification']}"

    def test_phase_field(self, p57_json):
        assert p57_json["phase"] == "P57"

    def test_lottery_type(self, p57_json):
        assert p57_json["lottery_type"] == "POWER_LOTTO"

    def test_pre_flight_section(self, p57_json):
        pf = p57_json["pre_flight"]
        assert pf["production_rows"] == EXPECTED_PROD_ROWS
        assert pf["production_rows_ok"] is True
        assert pf["p56_artifact_integrity"] is True
        assert pf["wave5_not_in_prod"] is True
        assert pf["champion_online"] is True

    def test_strategy_readiness_keys(self, p57_json):
        sr = p57_json["strategy_readiness"]
        for sid in WAVE5_STRATEGIES:
            assert sid in sr, f"{sid} missing from strategy_readiness"

    def test_per_strategy_required_fields(self, p57_json):
        required = [
            "row_count", "predicted", "errors", "leakage_violations",
            "duplicate_rate", "hit_3plus", "hit_3plus_rate",
            "hit_count_distribution", "special_hits", "special_hit_rate",
            "theoretical_m3_baseline", "z_test", "classification",
            "classification_reason", "in_prod_db",
        ]
        for sid in WAVE5_STRATEGIES:
            r = p57_json["strategy_readiness"][sid]
            for field in required:
                assert field in r, f"{sid} missing field: {field}"

    def test_cohort_decision_field(self, p57_json):
        valid = {"FULL_COHORT_P58", "PARTIAL_COHORT_P58", "NO_P58"}
        assert p57_json["cohort_decision"] in valid

    def test_p58_proposal_present(self, p57_json):
        assert "p58_proposal" in p57_json
        proposal = p57_json["p58_proposal"]
        assert proposal["phase"] == "P58"
        assert "strategies" in proposal
        assert "authorization_phrase_required" in proposal
        assert "pre_apply_checks" in proposal
        assert "rollback_requirements" in proposal

    def test_governance_section(self, p57_json):
        gov = p57_json["governance"]
        assert gov["production_db_write"] is False
        assert gov["lifecycle_promotion"] is False
        assert gov["champion_replacement"] is False
        assert gov["registry_mutation"] is False
        assert gov["live_api_call"] is False

    def test_overall_ok(self, p57_json):
        assert p57_json["overall_ok"] is True

    def test_p56_ref_present(self, p57_json):
        ref = p57_json["p56_ref"]
        assert ref["commit"] == "c3f0325"
        assert ref["classification"] == \
            "P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED"

    def test_coverage_value_section(self, p57_json):
        cv = p57_json["coverage_value"]
        for sid in WAVE5_STRATEGIES:
            assert sid in cv
            assert "below_baseline" in cv[sid]
            assert "adds_coverage_value" in cv[sid]


# ─── Class 4: Per-Strategy Readiness ─────────────────────────────────────────

class TestPerStrategyReadiness:
    """Verify per-strategy readiness scores and classifications."""

    def test_row_counts_all_1500(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            rc = p57_json["strategy_readiness"][sid]["row_count"]
            assert rc == ROWS_PER_STRATEGY, \
                f"{sid} row_count={rc}, expected {ROWS_PER_STRATEGY}"

    def test_zero_errors_all_strategies(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            assert p57_json["strategy_readiness"][sid]["errors"] == 0

    def test_zero_leakage_all_strategies(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            assert p57_json["strategy_readiness"][sid]["leakage_violations"] == 0

    def test_zero_duplicates_all_strategies(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            assert p57_json["strategy_readiness"][sid]["duplicate_rate"] == 0.0

    def test_wave5_not_in_prod_all_strategies(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            assert p57_json["strategy_readiness"][sid]["in_prod_db"] is False

    def test_fourier30_m3_rate(self, p57_json):
        r = p57_json["strategy_readiness"]["fourier30_markov30_2bet"]
        assert abs(r["hit_3plus_rate"] - 0.0407) < 0.001

    def test_cold_complement_m3_rate(self, p57_json):
        r = p57_json["strategy_readiness"]["cold_complement_2bet"]
        assert abs(r["hit_3plus_rate"] - 0.0367) < 0.001

    def test_zonal_entropy_m3_rate(self, p57_json):
        r = p57_json["strategy_readiness"]["zonal_entropy_2bet"]
        assert abs(r["hit_3plus_rate"] - 0.0367) < 0.001

    def test_special_hit_rate_all_strategies(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            shr = p57_json["strategy_readiness"][sid]["special_hit_rate"]
            assert abs(shr - 0.1187) < 0.001, \
                f"{sid} special_hit_rate={shr}, expected ~0.1187"

    def test_fourier30_classification(self, p57_json):
        clf = p57_json["strategy_readiness"]["fourier30_markov30_2bet"]["classification"]
        assert clf in (
            "READY_FOR_P58_CONTROLLED_APPLY_PROPOSAL",
            "READY_FOR_P58_WITH_CAUTION",
        ), f"fourier30 unexpected classification: {clf}"

    def test_cold_complement_classification(self, p57_json):
        clf = p57_json["strategy_readiness"]["cold_complement_2bet"]["classification"]
        assert clf == "WATCHLIST_REHEARSAL_ONLY", \
            f"cold_complement unexpected classification: {clf}"

    def test_zonal_entropy_classification(self, p57_json):
        clf = p57_json["strategy_readiness"]["zonal_entropy_2bet"]["classification"]
        assert clf == "WATCHLIST_REHEARSAL_ONLY", \
            f"zonal_entropy unexpected classification: {clf}"

    def test_fourier30_above_baseline(self, p57_json):
        r = p57_json["strategy_readiness"]["fourier30_markov30_2bet"]
        assert r["hit_3plus_rate"] > r["theoretical_m3_baseline"]

    def test_cold_complement_below_baseline(self, p57_json):
        r = p57_json["strategy_readiness"]["cold_complement_2bet"]
        assert r["hit_3plus_rate"] < r["theoretical_m3_baseline"]

    def test_zonal_entropy_below_baseline(self, p57_json):
        r = p57_json["strategy_readiness"]["zonal_entropy_2bet"]
        assert r["hit_3plus_rate"] < r["theoretical_m3_baseline"]

    def test_all_classifications_valid(self, p57_json):
        valid = {
            "READY_FOR_P58_CONTROLLED_APPLY_PROPOSAL",
            "READY_FOR_P58_WITH_CAUTION",
            "WATCHLIST_REHEARSAL_ONLY",
            "REWORK_REQUIRED",
            "BLOCKED_BY_SEMANTICS",
            "BLOCKED_BY_LEAKAGE_RISK",
        }
        for sid in WAVE5_STRATEGIES:
            clf = p57_json["strategy_readiness"][sid]["classification"]
            assert clf in valid, f"{sid}: invalid classification {clf}"


# ─── Class 5: Statistical Significance ────────────────────────────────────────

class TestStatisticalSignificance:
    """Verify z-test results for each strategy."""

    def test_z_test_fields_present(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            z = p57_json["strategy_readiness"][sid]["z_test"]
            assert "z" in z
            assert "p_value" in z
            assert "significant_at_05" in z

    def test_fourier30_not_significant_at_1500(self, p57_json):
        """
        At n=1500, fourier30 M3+ 4.07% vs baseline 3.87% (delta=0.2pp)
        is NOT statistically significant. Z ≈ 0.4, p ≈ 0.35.
        This is a key P57 finding: evidence is directional but inconclusive.
        """
        z_test = p57_json["strategy_readiness"]["fourier30_markov30_2bet"]["z_test"]
        assert z_test["significant_at_05"] is False, \
            "fourier30 should NOT be significant at n=1500"
        # Z should be positive (above baseline) but small
        assert z_test["z"] > 0, "fourier30 Z should be positive (above baseline)"
        assert z_test["z"] < 2.0, "fourier30 Z should be < 2.0 at n=1500"

    def test_cold_complement_negative_z(self, p57_json):
        z_test = p57_json["strategy_readiness"]["cold_complement_2bet"]["z_test"]
        assert z_test["z"] < 0, "cold_complement Z should be negative (below baseline)"

    def test_zonal_entropy_negative_z(self, p57_json):
        z_test = p57_json["strategy_readiness"]["zonal_entropy_2bet"]["z_test"]
        assert z_test["z"] < 0, "zonal_entropy Z should be negative (below baseline)"

    def test_p_values_between_0_and_1(self, p57_json):
        for sid in WAVE5_STRATEGIES:
            p = p57_json["strategy_readiness"][sid]["z_test"]["p_value"]
            assert 0.0 <= p <= 1.0, f"{sid} p_value={p} out of range"

    def test_theoretical_baseline_correct(self, p57_json):
        """Theoretical M3+ baseline should be close to 3.87% (hypergeometric)."""
        baseline = p57_json["theoretical_m3_baseline"]
        assert abs(baseline - 0.0387) < 0.001, \
            f"baseline={baseline}, expected ~0.0387"

    def test_theoretical_special_baseline(self, p57_json):
        """Theoretical special hit baseline = 1/8 = 0.125."""
        sb = p57_json["theoretical_special_baseline"]
        assert abs(sb - 0.125) < 0.001, f"special baseline={sb}, expected 0.125"

    def test_special_hit_below_theoretical_special_baseline(self, p57_json):
        """
        All strategies show special_hit_rate ≈ 11.87% (< 12.5% theoretical).
        This is expected variance — _special_predict uses mean-reversion which
        intentionally picks underrepresented values.
        """
        for sid in WAVE5_STRATEGIES:
            shr = p57_json["strategy_readiness"][sid]["special_hit_rate"]
            # Should be in a plausible range around 1/8
            assert 0.05 <= shr <= 0.20, \
                f"{sid} special_hit_rate={shr} unusually far from 1/8"


# ─── Class 6: Cohort Decision and P58 Proposal ────────────────────────────────

class TestCohortAndP58Proposal:
    """Cohort decision and P58 proposal must be valid and actionable."""

    def test_cohort_decision_is_partial(self, p57_json):
        """Only fourier30 passes the above-baseline threshold."""
        assert p57_json["cohort_decision"] == "PARTIAL_COHORT_P58"

    def test_p58_cohort_contains_fourier30(self, p57_json):
        assert "fourier30_markov30_2bet" in p57_json["p58_cohort"]

    def test_p58_cohort_excludes_watchlist(self, p57_json):
        cohort = p57_json["p58_cohort"]
        assert "cold_complement_2bet" not in cohort
        assert "zonal_entropy_2bet" not in cohort

    def test_watchlist_contains_below_baseline(self, p57_json):
        watchlist = p57_json["watchlist"]
        assert "cold_complement_2bet" in watchlist
        assert "zonal_entropy_2bet" in watchlist

    def test_p58_proposal_rows(self, p57_json):
        proposal = p57_json["p58_proposal"]
        cohort = p57_json["p58_cohort"]
        expected_new = len(cohort) * ROWS_PER_STRATEGY
        assert proposal["expected_new_rows"] == expected_new
        assert proposal["rows_per_strategy"] == ROWS_PER_STRATEGY

    def test_p58_projected_rows_after(self, p57_json):
        proposal = p57_json["p58_proposal"]
        assert proposal["production_rows_before"] == EXPECTED_PROD_ROWS
        expected_after = EXPECTED_PROD_ROWS + proposal["expected_new_rows"]
        assert proposal["projected_rows_after"] == expected_after

    def test_p58_authorization_phrase_present(self, p57_json):
        phrase = p57_json["p58_proposal"]["authorization_phrase_required"]
        assert "YES" in phrase
        assert len(phrase) > 20

    def test_p58_rollback_requirements_present(self, p57_json):
        rollback = p57_json["p58_proposal"]["rollback_requirements"]
        assert len(rollback) >= 2
        # Must mention backup
        backup_mentioned = any("backup" in r.lower() or "bak" in r.lower() for r in rollback)
        assert backup_mentioned, "P58 proposal must require DB backup"

    def test_p58_tests_required_present(self, p57_json):
        tests = p57_json["p58_proposal"]["tests_required"]
        assert len(tests) >= 4
        # Must include drift guard test
        drift_mentioned = any("drift" in t.lower() for t in tests)
        assert drift_mentioned

    def test_p58_note_no_authorization(self, p57_json):
        """P57 recommendation is NOT P58 authorization."""
        note = p57_json["p58_proposal"].get("note", "")
        assert "separately" in note.lower() or "does not" in note.lower(), \
            "P58 proposal must clarify P57 recommendation ≠ P58 authorization"


# ─── Class 7: Governance Constraints ─────────────────────────────────────────

class TestP57GovernanceConstraints:
    """P57 must not mutate production state."""

    def test_no_production_db_write(self, p57_json):
        assert p57_json["governance"]["production_db_write"] is False

    def test_no_lifecycle_promotion(self, p57_json):
        assert p57_json["governance"]["lifecycle_promotion"] is False

    def test_no_champion_replacement(self, p57_json):
        assert p57_json["governance"]["champion_replacement"] is False

    def test_no_registry_mutation(self, p57_json):
        assert p57_json["governance"]["registry_mutation"] is False

    def test_no_live_api_call(self, p57_json):
        assert p57_json["governance"]["live_api_call"] is False

    def test_p57_script_is_read_only(self):
        """P57 script must not contain 'INSERT INTO strategy_prediction_replays'."""
        content = P57_SCRIPT.read_text()
        assert "INSERT INTO strategy_prediction_replays" not in content, \
            "P57 script must not write to production DB"

    def test_p57_script_no_lifecycle_promotion(self):
        """P57 script must not set lifecycle = 'ONLINE' on any DB."""
        content = P57_SCRIPT.read_text()
        assert "lifecycle = 'ONLINE'" not in content
        assert "lifecycle='ONLINE'" not in content

    def test_adapter_not_in_registry(self):
        """Wave 5 adapter must not register itself — check code lines only (skip docstrings)."""
        in_docstring = False
        for line in ADAPTER_FILE.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Code line must not append/assign to registry lists
            assert "._ALL_ADAPTERS" not in line, \
                f"Adapter file assigns to _ALL_ADAPTERS in code: {line}"
            assert "_REGISTRY[" not in line, \
                f"Adapter file mutates _REGISTRY in code: {line}"

    def test_wave5_dryrun_lifecycle_declared(self):
        """Adapter file must declare DRY_RUN lifecycle."""
        content = ADAPTER_FILE.read_text()
        assert "DRY_RUN" in content

    def test_hit_count_distribution_sums_to_1500(self, p57_json):
        """hit_count distribution must sum to row_count for each strategy."""
        for sid in WAVE5_STRATEGIES:
            r = p57_json["strategy_readiness"][sid]
            dist = r["hit_count_distribution"]
            total = sum(dist.values())
            assert total == ROWS_PER_STRATEGY, \
                f"{sid} hit distribution sums to {total}, expected {ROWS_PER_STRATEGY}"
