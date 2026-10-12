"""
tests/test_p64c_zonal_entropy_wave6_determinism_dryrun.py

Governance test suite for P64c: zonal_entropy_2bet Wave 6 Determinism + Dry-Run Rehearsal.
Covers artifact existence, schema, governance invariants, production DB integrity,
determinism evidence, backtest configuration, row counts, metrics, readiness, and
classification.

Run:
  .venv/bin/python3.9 -m pytest tests/test_p64c_zonal_entropy_wave6_determinism_dryrun.py -v
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
PROD_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_PATH = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p64c_zonal_entropy_wave6_determinism_dryrun_20260525.json"
)
DOC_PATH = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "p64c_zonal_entropy_wave6_determinism_dryrun_20260525.md"
)
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "p64c_zonal_entropy_wave6_determinism_dryrun.py"
)
TEMP_DB_PATH = Path("/tmp/p64c_zonal_entropy_temp.db")

EXPECTED_PROD_ROWS = 43960
TARGET_ROWS = 1500
EVIDENCE_GATE_M3PLUS_PCT = 3.87
STRATEGY_ID = "zonal_entropy_2bet"
MARKER = "P64C_ZONAL_ENTROPY_WAVE6_DETERMINISM_DRYRUN_20260525"

VALID_READINESS = {
    "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL",
    "READY_FOR_P65_WITH_CAUTION",
    "WATCHLIST_REHEARSAL_ONLY",
    "BLOCKED_BY_NON_DETERMINISM",
    "BLOCKED_BY_LEAKAGE_RISK",
    "REWORK_REQUIRED",
}

VALID_CLASSIFICATIONS = {
    "P64C_ZONAL_ENTROPY_WAVE6_READY_FOR_P65",
    "P64C_ZONAL_ENTROPY_WAVE6_READY_WITH_CAUTION",
    "P64C_ZONAL_ENTROPY_WAVE6_WATCHLIST_REHEARSAL_ONLY",
    "P64C_ZONAL_ENTROPY_BLOCKED_BY_NON_DETERMINISM",
    "P64C_ZONAL_ENTROPY_BLOCKED_BY_LEAKAGE_RISK",
    "P64C_ZONAL_ENTROPY_REWORK_REQUIRED",
}


@pytest.fixture(scope="module")
def output() -> dict:
    """Load output JSON once for the whole module."""
    with open(JSON_PATH) as f:
        return json.load(f)


# ─── 1. Artifact Existence ────────────────────────────────────────────────────

class TestArtifactExistence:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"Script not found: {SCRIPT_PATH}"

    def test_script_non_empty(self):
        assert SCRIPT_PATH.stat().st_size > 1000

    def test_json_exists(self):
        assert JSON_PATH.exists(), f"JSON artifact not found: {JSON_PATH}"

    def test_json_non_empty(self):
        assert JSON_PATH.stat().st_size > 500

    def test_doc_exists(self):
        assert DOC_PATH.exists(), f"Doc artifact not found: {DOC_PATH}"

    def test_doc_non_empty(self):
        assert DOC_PATH.stat().st_size > 500


# ─── 2. Output Schema ─────────────────────────────────────────────────────────

class TestOutputSchema:
    REQUIRED_KEYS = [
        "schema_version", "task_id", "strategy_id", "run_id", "marker",
        "generated_at", "temp_db_path", "governance", "adapter", "dry_run",
        "determinism_check", "metrics", "semantic_validations",
        "leakage_validation", "idempotency_check", "rollback_check",
        "readiness", "classification",
    ]

    def test_required_keys_present(self, output):
        for key in self.REQUIRED_KEYS:
            assert key in output, f"Missing key: {key}"

    def test_task_id_is_p64c(self, output):
        assert output["task_id"] == "P64c"

    def test_strategy_id_is_zonal_entropy(self, output):
        assert output["strategy_id"] == STRATEGY_ID

    def test_marker_correct(self, output):
        assert output["marker"] == MARKER

    def test_schema_version(self, output):
        assert output["schema_version"] == "1.0"

    def test_run_id_contains_p64c(self, output):
        assert "p64c" in output["run_id"].lower()

    def test_run_id_contains_zonal_entropy(self, output):
        assert "zonal_entropy" in output["run_id"].lower()


# ─── 3. Governance Invariants ─────────────────────────────────────────────────

class TestGovernanceInvariants:
    def test_db_writes_false(self, output):
        assert output["governance"]["db_writes"] is False

    def test_online_promotions_false(self, output):
        assert output["governance"]["online_promotions"] is False

    def test_champion_replacement_false(self, output):
        assert output["governance"]["champion_replacement"] is False

    def test_production_apply_false(self, output):
        assert output["governance"]["production_apply"] is False

    def test_registry_mutation_false(self, output):
        assert output["governance"]["registry_mutation"] is False

    def test_production_rows_before(self, output):
        assert output["governance"]["production_rows_before"] == EXPECTED_PROD_ROWS

    def test_production_rows_after(self, output):
        assert output["governance"]["production_rows_after"] == EXPECTED_PROD_ROWS

    def test_temp_db_path_in_output(self, output):
        assert "/tmp/p64c_zonal_entropy_temp.db" in output["temp_db_path"]

    def test_dry_run_in_memory_false(self, output):
        assert output["dry_run"]["in_memory"] is False

    def test_dry_run_temp_db_only(self, output):
        assert output["dry_run"]["temp_db_only"] is True


# ─── 4. Production DB Intact ──────────────────────────────────────────────────

class TestProductionDBIntact:
    def test_prod_rows_still_43960(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == EXPECTED_PROD_ROWS

    def test_no_zonal_entropy_in_prod(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ?",
                (STRATEGY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_rollback_check_prod_rows_ok(self, output):
        assert output["rollback_check"]["production_rows_ok"] is True

    def test_rollback_check_ze_rows_ok(self, output):
        assert output["rollback_check"]["zonal_entropy_production_rows_ok"] is True

    def test_rollback_check_ze_rows_zero(self, output):
        assert output["rollback_check"]["zonal_entropy_production_rows"] == 0


# ─── 5. Determinism Evidence ──────────────────────────────────────────────────

class TestDeterminismEvidence:
    def test_determinism_pass(self, output):
        assert output["determinism_check"]["determinism_pass"] is True

    def test_determinism_violations_zero(self, output):
        assert output["determinism_check"]["violations"] == 0

    def test_determinism_checks_run_at_least_3(self, output):
        assert output["determinism_check"]["checks_run"] >= 3

    def test_no_random_seed(self, output):
        assert output["adapter"]["no_random_seed"] is True

    def test_no_random_sample(self, output):
        assert output["adapter"]["no_random_sample"] is True

    def test_adapter_deterministic(self, output):
        assert output["adapter"]["deterministic"] is True

    def test_fix_applied_false(self, output):
        # P56 already fixed it — no code change was needed in P64c
        assert output["determinism_check"]["fix_applied"] is False

    def test_source_risk_resolved(self, output):
        assert output["determinism_check"]["source_risk_status"] == "RESOLVED_IN_P56"


# ─── 6. Backtest Configuration ────────────────────────────────────────────────

class TestBacktestConfig:
    def test_target_rows(self, output):
        assert output["dry_run"]["window_periods"] == TARGET_ROWS

    def test_in_memory_false(self, output):
        assert output["dry_run"]["in_memory"] is False

    def test_temp_db_only(self, output):
        assert output["dry_run"]["temp_db_only"] is True

    def test_lifecycle_dry_run(self, output):
        assert output["dry_run"]["lifecycle"] == "DRY_RUN"

    def test_strategy_id_correct(self, output):
        assert output["adapter"]["class"] == "ZonalEntropy2BetAdapter"

    def test_adapter_file_correct(self, output):
        assert "p56_wave5_powerlotto_adapters" in output["adapter"]["file"]

    def test_algorithm_entropy_adaptive(self, output):
        assert "entropy_adaptive" in output["adapter"]["algorithm"]


# ─── 7. Dry-Run Row Counts ────────────────────────────────────────────────────

class TestDryrunRowCounts:
    def test_total_rows_equals_target(self, output):
        assert output["metrics"]["total_rows"] == TARGET_ROWS

    def test_predicted_rows_equals_target(self, output):
        assert output["metrics"]["predicted_rows"] == TARGET_ROWS

    def test_no_error_rows(self, output):
        assert output["metrics"]["error_rows"] == 0

    def test_no_insufficient_history_rows(self, output):
        assert output["metrics"]["insufficient_history_rows"] == 0

    def test_no_duplicate_target_draws(self, output):
        assert output["metrics"]["duplicate_target_draws"] == 0

    def test_idempotency_pass(self, output):
        assert output["idempotency_check"]["idempotent"] is True


# ─── 8. Window Metrics ────────────────────────────────────────────────────────

class TestWindowMetrics:
    def test_m3plus_rate_in_range(self, output):
        rate = output["metrics"]["m3plus_rate_pct"]
        assert 0.0 <= rate <= 20.0

    def test_special_hit_rate_in_range(self, output):
        rate = output["metrics"]["special_hit_rate_pct"]
        assert 3.0 <= rate <= 30.0

    def test_avg_hit_in_range(self, output):
        avg = output["metrics"]["avg_hit_count"]
        assert 0.0 <= avg <= 6.0

    def test_hit_distribution_sums_to_predicted(self, output):
        total = sum(output["metrics"]["hit_distribution"].values())
        assert total == output["metrics"]["predicted_rows"]

    def test_m3plus_count_consistent(self, output):
        dist = output["metrics"]["hit_distribution"]
        m3plus = sum(v for k, v in dist.items() if int(k) >= 3)
        assert m3plus == output["metrics"]["m3plus_count"]

    def test_regime_distribution_present(self, output):
        regime = output["metrics"]["regime_distribution"]
        assert "chaotic" in regime
        assert "stable" in regime

    def test_regime_distribution_sums_to_predicted(self, output):
        regime = output["metrics"]["regime_distribution"]
        predicted = output["metrics"]["predicted_rows"]
        total = regime["chaotic"] + regime["stable"] + regime["unknown"]
        assert total == predicted

    def test_baseline_value_correct(self, output):
        assert output["metrics"]["theoretical_m3plus_baseline_pct"] == EVIDENCE_GATE_M3PLUS_PCT

    def test_prior_p57_m3plus_recorded(self, output):
        assert output["metrics"]["prior_p57_m3plus_pct"] == pytest.approx(3.67, abs=0.01)

    def test_vs_prior_p57_recorded(self, output):
        # vs_prior should be small (same data)
        assert abs(output["metrics"]["vs_prior_p57_pp"]) < 0.5


# ─── 9. Readiness Decision ────────────────────────────────────────────────────

class TestReadinessDecision:
    def test_readiness_in_valid_set(self, output):
        assert output["readiness"]["classification"] in VALID_READINESS

    def test_readiness_has_rationale(self, output):
        assert len(output["readiness"]["rationale"]) > 10

    def test_no_production_apply(self, output):
        assert output["governance"]["production_apply"] is False

    def test_prior_p57_recorded_in_readiness(self, output):
        assert output["readiness"]["prior_p57_m3plus_pct"] == pytest.approx(3.67, abs=0.01)

    def test_prior_p57_mcnemar_p_recorded(self, output):
        assert output["readiness"]["prior_p57_mcnemar_p"] == pytest.approx(0.656, abs=0.01)

    def test_readiness_not_blocked_by_determinism(self, output):
        # Given determinism pass, should not be BLOCKED
        assert output["readiness"]["classification"] != "BLOCKED_BY_NON_DETERMINISM"


# ─── 10. Classification Marker ────────────────────────────────────────────────

class TestClassificationMarker:
    def test_classification_in_valid_set(self, output):
        assert output["classification"] in VALID_CLASSIFICATIONS

    def test_classification_contains_p64c(self, output):
        assert "P64C" in output["classification"]

    def test_classification_contains_zonal_entropy(self, output):
        assert "ZONAL_ENTROPY" in output["classification"]

    def test_marker_in_output(self, output):
        assert output["marker"] == MARKER


# ─── 11. Doc Content ──────────────────────────────────────────────────────────

class TestDocContent:
    @pytest.fixture(scope="class")
    def doc_text(self):
        return DOC_PATH.read_text()

    def test_doc_contains_marker(self, doc_text):
        assert MARKER in doc_text

    def test_doc_contains_strategy_id(self, doc_text):
        assert STRATEGY_ID in doc_text

    def test_doc_contains_prod_rows(self, doc_text):
        assert str(EXPECTED_PROD_ROWS) in doc_text

    def test_doc_contains_p64c(self, doc_text):
        assert "P64c" in doc_text

    def test_doc_no_production_apply_action(self, doc_text):
        # Must not mention production_apply=True
        assert "production_apply: True" not in doc_text
        assert '"production_apply": true' not in doc_text.lower()

    def test_doc_contains_readiness(self, doc_text):
        any_readiness = any(r in doc_text for r in VALID_READINESS)
        assert any_readiness

    def test_doc_contains_determinism(self, doc_text):
        assert "Determinism" in doc_text or "determinism" in doc_text

    def test_doc_contains_classification(self, output, doc_text):
        assert output["classification"] in doc_text

    def test_doc_contains_baseline(self, doc_text):
        assert "3.87" in doc_text


# ─── 12. No Staging Leak ─────────────────────────────────────────────────────

class TestNoStagingLeak:
    def test_temp_db_not_in_git_index(self):
        """Verify temp DB is not staged in git."""
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        staged = result.stdout.strip().splitlines()
        for f in staged:
            assert "p64c_zonal_entropy_temp" not in f, (
                f"Temp DB accidentally staged: {f}"
            )

    def test_prod_db_not_staged(self):
        """Verify production DB is not in git index."""
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        staged = result.stdout.strip().splitlines()
        for f in staged:
            assert "lottery_v2.db" not in f, (
                f"Production DB accidentally staged: {f}"
            )

    def test_json_artifact_exists_at_expected_path(self):
        assert JSON_PATH.exists()
        assert str(JSON_PATH).startswith(str(REPO_ROOT))
