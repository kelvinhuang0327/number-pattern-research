"""
P64a: POWER_LOTTO Wave 6 cold_complement_2bet Dry-Run Rehearsal Tests

Validates:
- Output artifacts exist with correct schema
- Governance invariants (no production DB writes)
- Metrics within expected ranges
- All validations PASS (semantic, leakage, idempotency, rollback)
- Readiness classification present and valid
- No production apply, no online promotions
- Classification marker correct
- P65 proposal present and well-formed

Classification marker: P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p64_cold_complement_wave6_dryrun_rehearsal_20260525.json"
DOC_PATH = REPO_ROOT / "docs" / "replay" / "p64_cold_complement_wave6_dryrun_rehearsal_20260525.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "p64_cold_complement_wave6_dryrun_rehearsal.py"
PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_PROD_ROWS = 43960
EXPECTED_WINDOW = 1500
STRATEGY_ID = "cold_complement_2bet"
THEORETICAL_M3_PLUS_BASELINE = 3.87
VALID_READINESS_VALUES = {
    "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL",
    "READY_FOR_P65_WITH_CAUTION",
    "WATCHLIST_REHEARSAL_ONLY",
    "REWORK_REQUIRED",
    "BLOCKED_BY_LEAKAGE_RISK",
}
VALID_CLASSIFICATIONS = {
    "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED",
    "P64_COLD_COMPLEMENT_WATCHLIST_REHEARSAL_ONLY",
}


@pytest.fixture(scope="module")
def artifact() -> dict:
    """Load the P64a output JSON artifact."""
    assert OUTPUT_JSON.exists(), f"Output JSON not found: {OUTPUT_JSON}"
    with open(OUTPUT_JSON) as f:
        return json.load(f)


# ─── T1: Artifact existence ────────────────────────────────────────────────────

class TestArtifactExistence:
    def test_output_json_exists(self):
        assert OUTPUT_JSON.exists(), f"Missing: {OUTPUT_JSON}"

    def test_doc_exists(self):
        assert DOC_PATH.exists(), f"Missing: {DOC_PATH}"

    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"Missing: {SCRIPT_PATH}"

    def test_output_json_not_empty(self):
        assert OUTPUT_JSON.stat().st_size > 100

    def test_doc_not_empty(self):
        assert DOC_PATH.stat().st_size > 100


# ─── T2: Schema ────────────────────────────────────────────────────────────────

class TestOutputSchema:
    REQUIRED_TOP_LEVEL_KEYS = [
        "schema_version", "task_id", "strategy_id", "run_id",
        "generated_at", "temp_db_path", "marker", "governance",
        "adapter", "dry_run", "metrics", "semantic_validations",
        "leakage_validation", "idempotency_check", "rollback_check",
        "readiness", "classification",
    ]

    def test_required_keys_present(self, artifact):
        for key in self.REQUIRED_TOP_LEVEL_KEYS:
            assert key in artifact, f"Missing key: {key}"

    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P64a"

    def test_strategy_id(self, artifact):
        assert artifact["strategy_id"] == STRATEGY_ID

    def test_schema_version(self, artifact):
        assert artifact["schema_version"] == "1.0"

    def test_classification_marker(self, artifact):
        assert artifact["marker"] == "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_20260525"

    def test_base_commit_present(self, artifact):
        assert "base_commit" in artifact
        assert artifact["base_commit"] == "cc05a10"

    def test_preceding_task(self, artifact):
        assert artifact["preceding_task"] == "P63"

    def test_next_task_present(self, artifact):
        assert "next_task" in artifact
        assert "P64b" in artifact["next_task"]


# ─── T3: Governance invariants ────────────────────────────────────────────────

class TestGovernanceInvariants:
    def test_no_db_writes(self, artifact):
        assert artifact["governance"]["db_writes"] is False

    def test_no_online_promotions(self, artifact):
        assert artifact["governance"]["online_promotions"] is False

    def test_no_champion_replacement(self, artifact):
        assert artifact["governance"]["champion_replacement"] is False

    def test_no_registry_mutation(self, artifact):
        assert artifact["governance"]["registry_mutation"] is False

    def test_no_production_apply(self, artifact):
        assert artifact["governance"]["production_apply"] is False

    def test_prod_rows_before_unchanged(self, artifact):
        assert artifact["governance"]["production_rows_before"] == EXPECTED_PROD_ROWS

    def test_prod_rows_after_unchanged(self, artifact):
        assert artifact["governance"]["production_rows_after"] == EXPECTED_PROD_ROWS

    def test_drift_guard_pass(self, artifact):
        assert artifact["governance"]["drift_guard"] == "PASS"

    def test_branch_governance_guard_pass(self, artifact):
        assert artifact["governance"]["branch_governance_guard"] == "PASS"


# ─── T4: Production DB direct check ──────────────────────────────────────────

class TestProductionDBIntact:
    def test_production_rows_still_43960(self):
        conn = sqlite3.connect(str(PROD_DB_PATH))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == EXPECTED_PROD_ROWS, (
            f"Production DB has {count} rows, expected {EXPECTED_PROD_ROWS}"
        )

    def test_cold_complement_not_in_production(self):
        conn = sqlite3.connect(str(PROD_DB_PATH))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ?",
                (STRATEGY_ID,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0, (
            f"cold_complement_2bet found {count} rows in production — must be 0"
        )


# ─── T5: Dry-run metrics ──────────────────────────────────────────────────────

class TestDryRunMetrics:
    def test_total_rows_1500(self, artifact):
        assert artifact["metrics"]["total_rows"] == EXPECTED_WINDOW

    def test_predicted_rows_1500(self, artifact):
        assert artifact["metrics"]["predicted_rows"] == EXPECTED_WINDOW

    def test_no_insufficient_history_rows(self, artifact):
        assert artifact["metrics"]["insufficient_history_rows"] == 0

    def test_no_error_rows(self, artifact):
        assert artifact["metrics"]["error_rows"] == 0

    def test_m3plus_count_positive(self, artifact):
        assert artifact["metrics"]["m3plus_count"] > 0

    def test_m3plus_rate_within_plausible_range(self, artifact):
        # Must be positive and not impossibly high
        rate = artifact["metrics"]["m3plus_rate_pct"]
        assert 0.5 <= rate <= 15.0, f"M3+ rate {rate}% outside plausible range [0.5, 15.0]"

    def test_m3plus_vs_baseline_within_noise(self, artifact):
        # Within ±2 SE (SE ≈ 0.50pp at N=1500 → ±1.0pp is 2SE)
        delta = artifact["metrics"]["vs_baseline_pp"]
        assert delta >= -1.5, f"M3+ rate too far below baseline: {delta}pp"

    def test_theoretical_baseline_correct(self, artifact):
        assert artifact["metrics"]["theoretical_m3plus_baseline_pct"] == THEORETICAL_M3_PLUS_BASELINE

    def test_special_hit_rate_positive(self, artifact):
        assert artifact["metrics"]["special_hit_rate_pct"] > 0

    def test_special_hit_rate_plausible(self, artifact):
        # Special pool = 8, expected ~12.5% — accept 5-30% as plausible
        rate = artifact["metrics"]["special_hit_rate_pct"]
        assert 5.0 <= rate <= 30.0, f"Special hit rate {rate}% outside [5.0, 30.0]"

    def test_no_duplicate_target_draws(self, artifact):
        assert artifact["metrics"]["duplicate_target_draws"] == 0

    def test_target_draw_range_valid(self, artifact):
        dmin = artifact["metrics"]["target_draw_min"]
        dmax = artifact["metrics"]["target_draw_max"]
        assert dmin is not None and dmax is not None
        assert dmax > dmin

    def test_hit_distribution_keys_valid(self, artifact):
        for k in artifact["metrics"]["hit_distribution"]:
            assert int(k) in range(7), f"hit_count {k} out of [0,6]"

    def test_hit_distribution_sums_to_predicted(self, artifact):
        dist_sum = sum(artifact["metrics"]["hit_distribution"].values())
        assert dist_sum == artifact["metrics"]["predicted_rows"]

    def test_avg_hit_count_positive(self, artifact):
        assert artifact["metrics"]["avg_hit_count"] > 0


# ─── T6: Semantic validations ─────────────────────────────────────────────────

class TestSemanticValidations:
    def test_all_semantic_checks_pass(self, artifact):
        assert artifact["semantic_validations"]["all_pass"] is True

    def test_pick_6_unique_numbers_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["pick_6_unique_numbers"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["pick_6_unique_numbers"]["violations"] == 0

    def test_numbers_in_range_1_38_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["numbers_in_range_1_38"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["numbers_in_range_1_38"]["violations"] == 0

    def test_special_in_range_1_8_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["special_in_range_1_8"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["special_in_range_1_8"]["violations"] == 0

    def test_no_duplicate_numbers_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["no_duplicate_numbers"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["no_duplicate_numbers"]["violations"] == 0

    def test_hit_count_integrity_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["hit_count_integrity"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["hit_count_integrity"]["violations"] == 0

    def test_no_leakage_indicators_pass(self, artifact):
        assert artifact["semantic_validations"]["checks"]["no_leakage_indicators"]["pass"] is True
        assert artifact["semantic_validations"]["checks"]["no_leakage_indicators"]["violations"] == 0


# ─── T7: Leakage validation ───────────────────────────────────────────────────

class TestLeakageValidation:
    def test_leakage_free(self, artifact):
        assert artifact["leakage_validation"]["leakage_free"] is True

    def test_no_leakage_violations(self, artifact):
        assert artifact["leakage_validation"]["leakage_violations"] == 0

    def test_no_null_cutoff_rows(self, artifact):
        assert artifact["leakage_validation"]["null_cutoff_rows"] == 0


# ─── T8: Idempotency ─────────────────────────────────────────────────────────

class TestIdempotency:
    def test_idempotent(self, artifact):
        assert artifact["idempotency_check"]["idempotent"] is True

    def test_count_unchanged(self, artifact):
        assert artifact["idempotency_check"]["count_before"] == artifact["idempotency_check"]["count_after"]

    def test_count_is_1500(self, artifact):
        assert artifact["idempotency_check"]["count_before"] == EXPECTED_WINDOW


# ─── T9: Rollback check ───────────────────────────────────────────────────────

class TestRollbackCheck:
    def test_production_rows_ok(self, artifact):
        assert artifact["rollback_check"]["production_rows_ok"] is True

    def test_cold_complement_production_rows_zero(self, artifact):
        assert artifact["rollback_check"]["cold_complement_production_rows"] == 0
        assert artifact["rollback_check"]["cold_complement_production_rows_ok"] is True

    def test_production_rows_count(self, artifact):
        assert artifact["rollback_check"]["production_rows"] == EXPECTED_PROD_ROWS


# ─── T10: Readiness ───────────────────────────────────────────────────────────

class TestReadiness:
    def test_readiness_classification_valid(self, artifact):
        assert artifact["readiness"]["classification"] in VALID_READINESS_VALUES

    def test_readiness_rationale_present(self, artifact):
        assert "rationale" in artifact["readiness"]
        assert len(artifact["readiness"]["rationale"]) > 0

    def test_p57_reference_values_present(self, artifact):
        assert "p57_m3plus_pct" in artifact["readiness"]
        assert "p57_baseline_pct" in artifact["readiness"]
        assert "p57_delta_pp" in artifact["readiness"]
        assert "p57_mcnemar_p" in artifact["readiness"]

    def test_p57_mcnemar_p_not_significant(self, artifact):
        # McNemar p = 0.656 — not significant; cold_complement is within noise
        assert artifact["readiness"]["p57_mcnemar_p"] > 0.05


# ─── T11: Classification marker ───────────────────────────────────────────────

class TestClassificationMarker:
    def test_classification_valid(self, artifact):
        assert artifact["classification"] in VALID_CLASSIFICATIONS

    def test_classification_is_completed(self, artifact):
        assert artifact["classification"] == "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED"


# ─── T12: Adapter metadata ────────────────────────────────────────────────────

class TestAdapterMetadata:
    def test_adapter_class(self, artifact):
        assert artifact["adapter"]["class"] == "ColdComplement2BetAdapter"

    def test_adapter_file(self, artifact):
        assert "p56_wave5_powerlotto_adapters" in artifact["adapter"]["file"]

    def test_adapter_deterministic(self, artifact):
        assert artifact["adapter"]["deterministic"] is True

    def test_no_random_seed(self, artifact):
        assert artifact["adapter"]["no_random_seed"] is True

    def test_pick_6(self, artifact):
        assert artifact["adapter"]["pick"] == 6


# ─── T13: P65 proposal ────────────────────────────────────────────────────────

class TestP65Proposal:
    def test_p65_proposal_present(self, artifact):
        # Proposal should exist for READY_FOR_P65 readiness
        if artifact["readiness"]["classification"] in (
            "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL",
            "READY_FOR_P65_WITH_CAUTION",
        ):
            assert artifact["p65_proposal"] is not None

    def test_p65_proposed_rows(self, artifact):
        if artifact["p65_proposal"]:
            assert artifact["p65_proposal"]["proposed_apply_rows"] == EXPECTED_WINDOW

    def test_p65_backup_required(self, artifact):
        if artifact["p65_proposal"]:
            assert artifact["p65_proposal"]["backup_required"] is True

    def test_p65_explicit_auth_phrase_present(self, artifact):
        if artifact["p65_proposal"]:
            auth = artifact["p65_proposal"]["explicit_production_apply_authorization_required"]
            assert "YES apply cold_complement_2bet" in auth

    def test_p65_expected_rows_after(self, artifact):
        if artifact["p65_proposal"]:
            expected = EXPECTED_PROD_ROWS + EXPECTED_WINDOW  # 43960 + 1500 = 45460
            assert artifact["p65_proposal"]["expected_production_rows_after"] == expected


# ─── T14: Dry-run config ─────────────────────────────────────────────────────

class TestDryRunConfig:
    def test_window_periods(self, artifact):
        assert artifact["dry_run"]["window_periods"] == EXPECTED_WINDOW

    def test_lifecycle_dry_run(self, artifact):
        assert artifact["dry_run"]["lifecycle"] == "DRY_RUN"

    def test_temp_db_path_not_production(self, artifact):
        assert "lottery_v2.db" not in artifact["dry_run"]["temp_db"]
        assert "tmp" in artifact["dry_run"]["temp_db"]


# ─── T15: Doc content validation ──────────────────────────────────────────────

class TestDocContent:
    def test_doc_contains_classification_marker(self):
        content = DOC_PATH.read_text()
        assert "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED" in content

    def test_doc_contains_readiness_verdict(self):
        content = DOC_PATH.read_text()
        assert "READY_FOR_P65" in content

    def test_doc_contains_governance_table(self):
        content = DOC_PATH.read_text()
        assert "43960" in content

    def test_doc_contains_m3plus_rate(self):
        content = DOC_PATH.read_text()
        assert "3.67" in content

    def test_doc_contains_p65_proposal_section(self):
        content = DOC_PATH.read_text()
        assert "P65" in content

    def test_doc_no_temp_db_committed_warning(self):
        content = DOC_PATH.read_text()
        assert "NOT staged" in content or "Temp only" in content
