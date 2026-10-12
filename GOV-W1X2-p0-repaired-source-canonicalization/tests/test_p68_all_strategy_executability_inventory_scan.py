"""
test_p68_all_strategy_executability_inventory_scan.py

P68 All-Strategy Executability Inventory Scan — Evidence Tests

Verifies:
- P68 artifacts exist (MD + JSON)
- Governance invariants
- Baseline verification (46960 rows, 3 controlled apply IDs × 1500)
- Classification buckets present
- Strategy disclosures (prediction-helpful / sub-baseline / fallback-equivalent)

No DB writes. No lifecycle promotion. No champion replacement. No registry mutation.
"""
import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P68_JSON = REPO_ROOT / "outputs" / "replay" / "p68_all_strategy_executability_inventory_scan_20260526.json"
P68_MD = REPO_ROOT / "docs" / "replay" / "p68_all_strategy_executability_inventory_scan_20260526.md"

EXPECTED_PRODUCTION_ROWS = 46960
EXPECTED_CONTROLLED_APPLY_IDS = {
    "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525": 1500,
    "P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525": 1500,
    "P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525": 1500,
}
REQUIRED_BUCKETS = [
    "row_backed",
    "executable_no_row",
    "adapter_needed",
    "unsupported",
    "rejected",
    "dependency_blocked",
    "manual_review",
    "no_data",
    "artifact_only",
    "code_only",
    "reconstructible",
    "sub_baseline",
    "fallback_equivalent",
]
REQUIRED_PERFORMANCE_LABELS = {"prediction-helpful", "sub-baseline", "fallback-equivalent"}
REQUIRED_STRATEGY_DISCLOSURES = {
    "fourier30_markov30_2bet": "prediction-helpful",
    "cold_complement_2bet": "sub-baseline",
    "zonal_entropy_2bet": "fallback-equivalent",
}


@pytest.fixture(scope="module")
def p68():
    assert P68_JSON.exists(), f"P68 JSON missing: {P68_JSON}"
    return json.loads(P68_JSON.read_text())


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP68ArtifactExistence:
    def test_json_exists(self):
        assert P68_JSON.exists()

    def test_md_exists(self):
        assert P68_MD.exists()

    def test_json_task_is_p68(self, p68):
        assert p68["task"] == "P68"

    def test_json_status(self, p68):
        assert p68["status"] == "EVIDENCE_ONLY"


# ---------------------------------------------------------------------------
# 2. Governance invariants
# ---------------------------------------------------------------------------
class TestP68Governance:
    def test_project_context_lock(self, p68):
        assert p68["project_context_lock"] == "LotteryNew"

    def test_no_db_write(self, p68):
        assert p68["no_db_write"] is True

    def test_db_writes_false(self, p68):
        assert p68["db_writes"] is False

    def test_no_force_push(self, p68):
        assert p68["no_force_push"] is True

    def test_no_lifecycle_promotion(self, p68):
        assert p68["no_lifecycle_promotion"] is True

    def test_no_registry_mutation(self, p68):
        assert p68["no_registry_mutation"] is True

    def test_branch(self, p68):
        assert p68["branch"] == "p68-all-strategy-executability-inventory-scan"

    def test_final_classification(self, p68):
        assert "P68" in p68["final_classification"]


# ---------------------------------------------------------------------------
# 3. Production rows — JSON
# ---------------------------------------------------------------------------
class TestP68ProductionRowsJson:
    def test_production_rows_before(self, p68):
        assert p68["production_rows_before"] == EXPECTED_PRODUCTION_ROWS

    def test_production_rows_after(self, p68):
        assert p68["production_rows_after"] == EXPECTED_PRODUCTION_ROWS

    def test_rows_unchanged(self, p68):
        assert p68["production_rows_before"] == p68["production_rows_after"]


# ---------------------------------------------------------------------------
# 4. Production rows — live DB
# ---------------------------------------------------------------------------
class TestP68ProductionRowsDB:
    def test_total_rows(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == EXPECTED_PRODUCTION_ROWS

    def test_no_new_rows_inserted(self, db):
        """Confirm that the three controlled apply IDs have the expected counts."""
        cur = db.cursor()
        for apply_id, expected_count in EXPECTED_CONTROLLED_APPLY_IDS.items():
            cur.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
                (apply_id,),
            )
            actual = cur.fetchone()[0]
            assert actual == expected_count, (
                f"controlled_apply_id={apply_id}: expected {expected_count}, got {actual}"
            )


# ---------------------------------------------------------------------------
# 5. Controlled apply IDs — JSON
# ---------------------------------------------------------------------------
class TestP68ControlledApplyIds:
    def test_controlled_apply_ids_present(self, p68):
        assert "controlled_apply_ids" in p68

    def test_p58_apply_id(self, p68):
        ids = p68["controlled_apply_ids"]
        assert ids["P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"] == 1500

    def test_p66_cold_complement_apply_id(self, p68):
        ids = p68["controlled_apply_ids"]
        assert ids["P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525"] == 1500

    def test_p66_zonal_entropy_apply_id(self, p68):
        ids = p68["controlled_apply_ids"]
        assert ids["P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525"] == 1500


# ---------------------------------------------------------------------------
# 6. Classification buckets
# ---------------------------------------------------------------------------
class TestP68ClassificationBuckets:
    def test_inventory_summary_present(self, p68):
        assert "inventory_summary" in p68

    def test_all_required_buckets_present(self, p68):
        summary = p68["inventory_summary"]
        for bucket in REQUIRED_BUCKETS:
            assert bucket in summary, f"Missing bucket: {bucket}"

    def test_row_backed_count(self, p68):
        assert p68["inventory_summary"]["row_backed"] == 31

    def test_row_backed_count_top_level(self, p68):
        assert p68["row_backed_count"] == 31

    def test_strategy_universe_count(self, p68):
        assert p68["strategy_universe_count"] == 512

    def test_sub_baseline_count(self, p68):
        assert p68["inventory_summary"]["sub_baseline"] == 2

    def test_fallback_equivalent_count(self, p68):
        assert p68["inventory_summary"]["fallback_equivalent"] == 1


# ---------------------------------------------------------------------------
# 7. Strategy disclosures — prediction-helpful / sub-baseline / fallback-equivalent
# ---------------------------------------------------------------------------
class TestP68StrategyDisclosures:
    def test_disclosures_present(self, p68):
        assert "strategy_disclosures" in p68

    def test_fourier30_markov30_prediction_helpful(self, p68):
        assert p68["strategy_disclosures"]["fourier30_markov30_2bet"] == "prediction-helpful"

    def test_cold_complement_sub_baseline(self, p68):
        assert p68["strategy_disclosures"]["cold_complement_2bet"] == "sub-baseline"

    def test_zonal_entropy_fallback_equivalent(self, p68):
        assert p68["strategy_disclosures"]["zonal_entropy_2bet"] == "fallback-equivalent"

    def test_performance_disclosures_labels(self, p68):
        disclosures = p68["performance_disclosures"]
        labels = {v["label"] for v in disclosures.values()}
        assert "prediction-helpful" in labels
        assert "sub-baseline" in labels
        assert "fallback-equivalent" in labels

    def test_sub_baseline_below_baseline(self, p68):
        cold = p68["performance_disclosures"]["cold_complement_2bet"]
        assert cold["m3_hit_rate"] < cold["baseline"]

    def test_prediction_helpful_above_baseline(self, p68):
        fourier = p68["performance_disclosures"]["fourier30_markov30_2bet"]
        assert fourier["m3_hit_rate"] > fourier["baseline"]


# ---------------------------------------------------------------------------
# 8. Guard results
# ---------------------------------------------------------------------------
class TestP68GuardResults:
    def test_guard_results_present(self, p68):
        assert "guard_results" in p68

    def test_drift_guard_pass(self, p68):
        gr = p68["guard_results"]
        assert "PASS" in gr["drift_guard"]

    def test_branch_governance_pass(self, p68):
        gr = p68["guard_results"]
        assert "PASS" in gr["branch_governance_guard"]


# ---------------------------------------------------------------------------
# 9. Forbidden staging confirmation
# ---------------------------------------------------------------------------
class TestP68ForbiddenStagingConfirmation:
    def test_forbidden_staging_results_present(self, p68):
        assert "forbidden_staging_scan_results" in p68

    def test_all_scans_clean(self, p68):
        scans = p68["forbidden_staging_scan_results"]
        assert scans["overall"] == "ALL_SCANS_CLEAN"

    def test_db_files_clean(self, p68):
        scans = p68["forbidden_staging_scan_results"]
        assert scans["scan2_db_files"] == "DB_STAGE_CLEAN"


# ---------------------------------------------------------------------------
# 10. Files created list
# ---------------------------------------------------------------------------
class TestP68FilesCreated:
    def test_files_created_present(self, p68):
        assert "files_created" in p68

    def test_md_in_files_created(self, p68):
        assert any("p68" in f and f.endswith(".md") for f in p68["files_created"])

    def test_json_in_files_created(self, p68):
        assert any("p68" in f and f.endswith(".json") for f in p68["files_created"])

    def test_test_in_files_created(self, p68):
        assert any("p68" in f and f.endswith(".py") for f in p68["files_created"])
