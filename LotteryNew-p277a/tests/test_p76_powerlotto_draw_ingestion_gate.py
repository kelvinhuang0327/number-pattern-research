"""
P76 POWER_LOTTO Draw Ingestion Gate — Governance Test Suite

Tests:
  - Required artifact existence
  - project_context_lock = LotteryNew
  - replay_rows_before = 46960
  - replay_rows_after = 46960
  - powerlotto_draw_max is recorded
  - powerlotto_draws_after_115000040_count is recorded (== 0 at gate time)
  - p75 blocker summary exists
  - ingestion_source_discovery is present
  - ingestion_readiness_status is present
  - required_ingestion_gates is a non-empty list
  - p75_plan_regeneration_requirements is present
  - safety booleans all true
  - final_classification = P76_POWERLOTTO_DRAW_INGESTION_GATE_MERGED_TO_MAIN

PROJECT_CONTEXT_LOCK = LotteryNew
"""

import json
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent
P76_JSON  = REPO_ROOT / "outputs" / "replay" / "p76_powerlotto_draw_ingestion_gate_20260526.json"
P76_DOC   = REPO_ROOT / "docs"    / "replay" / "p76_powerlotto_draw_ingestion_gate_20260526.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p76_data():
    with open(P76_JSON, encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p76_doc_text():
    return P76_DOC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Artifact Existence
# ---------------------------------------------------------------------------

class TestArtifactExistence:
    def test_p76_json_exists(self):
        assert P76_JSON.exists(), f"Missing: {P76_JSON}"

    def test_p76_doc_exists(self):
        assert P76_DOC.exists(), f"Missing: {P76_DOC}"


# ---------------------------------------------------------------------------
# Project Context Lock
# ---------------------------------------------------------------------------

class TestProjectContextLock:
    def test_json_project_context_lock(self, p76_data):
        assert p76_data["project_context_lock"] == "LotteryNew"

    def test_doc_project_context_lock(self, p76_doc_text):
        assert "PROJECT_CONTEXT_LOCK" in p76_doc_text
        assert "LotteryNew" in p76_doc_text

    def test_json_repo(self, p76_data):
        assert "LotteryNew" in p76_data["repo"]

    def test_json_branch(self, p76_data):
        assert "p76" in p76_data["branch"]


# ---------------------------------------------------------------------------
# Replay Row Invariant
# ---------------------------------------------------------------------------

class TestReplayRowInvariant:
    def test_replay_rows_before(self, p76_data):
        assert p76_data["replay_rows_before"] == 46960

    def test_replay_rows_after(self, p76_data):
        assert p76_data["replay_rows_after"] == 46960

    def test_replay_rows_unchanged(self, p76_data):
        assert p76_data["replay_rows_before"] == p76_data["replay_rows_after"]

    def test_no_replay_db_write(self, p76_data):
        assert p76_data["no_replay_db_write"] is True


# ---------------------------------------------------------------------------
# POWER_LOTTO Draw Coverage
# ---------------------------------------------------------------------------

class TestPowerlottoDrawCoverage:
    def test_powerlotto_draw_max_recorded(self, p76_data):
        assert "powerlotto_draw_max" in p76_data
        assert isinstance(p76_data["powerlotto_draw_max"], int)

    def test_powerlotto_draw_max_value(self, p76_data):
        assert p76_data["powerlotto_draw_max"] == 115000040

    def test_powerlotto_draw_min_recorded(self, p76_data):
        assert "powerlotto_draw_min" in p76_data
        assert isinstance(p76_data["powerlotto_draw_min"], int)

    def test_powerlotto_draw_count_recorded(self, p76_data):
        assert "powerlotto_draw_count" in p76_data
        assert p76_data["powerlotto_draw_count"] > 0

    def test_powerlotto_draws_after_115000040_count_recorded(self, p76_data):
        assert "powerlotto_draws_after_115000040_count" in p76_data

    def test_powerlotto_draws_after_115000040_count_is_zero_at_gate_time(self, p76_data):
        # At P76 gate time, no new draws exist in DB yet — this is the confirmed blocker
        assert p76_data["powerlotto_draws_after_115000040_count"] == 0

    def test_doc_draws_after_count(self, p76_doc_text):
        assert "115000040" in p76_doc_text
        # Doc must mention draw gap
        assert "0" in p76_doc_text


# ---------------------------------------------------------------------------
# P75 Blocker Summary
# ---------------------------------------------------------------------------

class TestP75BlockerSummary:
    def test_p75_blocker_summary_exists(self, p76_data):
        assert "p75_blocker_summary" in p76_data

    def test_p75_blocker_classification(self, p76_data):
        assert p76_data["p75_blocker_summary"]["classification"] == "P75_BLOCKED_BY_SOURCE_DATA_GAP"

    def test_p75_blocker_strategies(self, p76_data):
        strategies = p76_data["p75_blocker_summary"]["strategies_affected"]
        assert "fourier_rhythm_3bet" in strategies
        assert "fourier30_markov30_2bet" in strategies

    def test_p75_blocker_db_max_draw(self, p76_data):
        assert p76_data["p75_blocker_summary"]["db_max_draw_integer"] == 115000040

    def test_p75_blocker_draws_after_max(self, p76_data):
        assert p76_data["p75_blocker_summary"]["draws_after_max_in_db"] == 0

    def test_p75_blocker_coverage_fourier_rhythm(self, p76_data):
        cov = p76_data["p75_blocker_summary"]["current_coverage"]
        assert "fourier_rhythm_3bet" in cov
        assert cov["fourier_rhythm_3bet"]["row_count"] == 1500

    def test_p75_blocker_coverage_fourier30_markov30(self, p76_data):
        cov = p76_data["p75_blocker_summary"]["current_coverage"]
        assert "fourier30_markov30_2bet" in cov
        assert cov["fourier30_markov30_2bet"]["row_count"] == 1500

    def test_doc_p75_blocker_summary(self, p76_doc_text):
        assert "P75_BLOCKED_BY_SOURCE_DATA_GAP" in p76_doc_text
        assert "fourier_rhythm_3bet" in p76_doc_text
        assert "fourier30_markov30_2bet" in p76_doc_text


# ---------------------------------------------------------------------------
# Ingestion Source Discovery
# ---------------------------------------------------------------------------

class TestIngestionSourceDiscovery:
    def test_ingestion_source_discovery_exists(self, p76_data):
        assert "ingestion_source_discovery" in p76_data

    def test_official_api_available(self, p76_data):
        assert p76_data["ingestion_source_discovery"]["official_api_available"] is True

    def test_official_api_base_recorded(self, p76_data):
        base = p76_data["ingestion_source_discovery"]["official_api_base"]
        assert "taiwanlottery" in base

    def test_power_lotto_endpoint_recorded(self, p76_data):
        ep = p76_data["ingestion_source_discovery"]["power_lotto_endpoint"]
        assert "SuperLotto638" in ep or "super" in ep.lower()

    def test_fetcher_module_recorded(self, p76_data):
        assert "fetcher_module" in p76_data["ingestion_source_discovery"]

    def test_ingestion_pipeline_status_recorded(self, p76_data):
        status = p76_data["ingestion_source_discovery"]["ingestion_pipeline_status"]
        assert status  # non-empty

    def test_doc_official_api(self, p76_doc_text):
        assert "taiwanlottery.com" in p76_doc_text


# ---------------------------------------------------------------------------
# Ingestion Readiness Status
# ---------------------------------------------------------------------------

class TestIngestionReadinessStatus:
    def test_ingestion_readiness_status_exists(self, p76_data):
        assert "ingestion_readiness_status" in p76_data

    def test_ingestion_readiness_status_not_blocked(self, p76_data):
        # Source is available — not blocked by missing API
        status = p76_data["ingestion_readiness_status"]
        assert "INGESTION_POSSIBLE" in status or "INGESTION_READY" in status

    def test_ingestion_readiness_detail_exists(self, p76_data):
        assert "ingestion_readiness_detail" in p76_data
        assert len(p76_data["ingestion_readiness_detail"]) > 20


# ---------------------------------------------------------------------------
# Required Ingestion Gates
# ---------------------------------------------------------------------------

class TestRequiredIngestionGates:
    def test_required_ingestion_gates_exists(self, p76_data):
        assert "required_ingestion_gates" in p76_data

    def test_required_ingestion_gates_non_empty(self, p76_data):
        gates = p76_data["required_ingestion_gates"]
        assert isinstance(gates, list)
        assert len(gates) >= 5

    def test_gate_source_provenance_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "source_provenance" in gate_names

    def test_gate_backup_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "backup" in gate_names

    def test_gate_dry_run_fetch_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "dry_run_fetch" in gate_names

    def test_gate_duplicate_draw_check_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "duplicate_draw_check" in gate_names

    def test_gate_drift_guard_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "drift_guard" in gate_names

    def test_gate_branch_governance_guard_present(self, p76_data):
        gate_names = [g["gate"] for g in p76_data["required_ingestion_gates"]]
        assert "branch_governance_guard" in gate_names

    def test_doc_ingestion_gates(self, p76_doc_text):
        assert "backup" in p76_doc_text.lower()
        assert "dry" in p76_doc_text.lower()
        assert "duplicate" in p76_doc_text.lower()


# ---------------------------------------------------------------------------
# P75 Plan Regeneration Requirements
# ---------------------------------------------------------------------------

class TestP75PlanRegenerationRequirements:
    def test_p75_plan_regeneration_requirements_exists(self, p76_data):
        assert "p75_plan_regeneration_requirements" in p76_data

    def test_plan_regeneration_steps_non_empty(self, p76_data):
        req = p76_data["p75_plan_regeneration_requirements"]
        assert "steps" in req
        assert len(req["steps"]) >= 5

    def test_plan_regeneration_expected_rows(self, p76_data):
        req = p76_data["p75_plan_regeneration_requirements"]
        assert req["expected_rows_after_batch_a_apply"] == 49960

    def test_doc_plan_regeneration(self, p76_doc_text):
        assert "PLAN_READY_FOR_P76_APPLY" in p76_doc_text
        assert "49960" in p76_doc_text


# ---------------------------------------------------------------------------
# Safety Booleans
# ---------------------------------------------------------------------------

class TestSafetyBooleans:
    def test_no_replay_db_write(self, p76_data):
        assert p76_data["no_replay_db_write"] is True

    def test_no_fake_draws(self, p76_data):
        assert p76_data["no_fake_draws"] is True

    def test_no_fake_prediction_rows(self, p76_data):
        assert p76_data["no_fake_prediction_rows"] is True

    def test_no_force_push(self, p76_data):
        assert p76_data["no_force_push"] is True

    def test_no_reset_hard(self, p76_data):
        assert p76_data["no_reset_hard"] is True

    def test_no_git_clean(self, p76_data):
        assert p76_data["no_git_clean"] is True

    def test_no_lifecycle_promotion(self, p76_data):
        assert p76_data["no_lifecycle_promotion"] is True

    def test_no_champion_replacement(self, p76_data):
        assert p76_data["no_champion_replacement"] is True

    def test_no_registry_mutation(self, p76_data):
        assert p76_data["no_registry_mutation"] is True


# ---------------------------------------------------------------------------
# Final Classification
# ---------------------------------------------------------------------------

class TestFinalClassification:
    def test_final_classification_exists(self, p76_data):
        assert "final_classification" in p76_data

    def test_final_classification_value(self, p76_data):
        assert p76_data["final_classification"] == "P76_POWERLOTTO_DRAW_INGESTION_GATE_MERGED_TO_MAIN"

    def test_doc_final_classification(self, p76_doc_text):
        assert "P76_POWERLOTTO_DRAW_INGESTION_GATE_MERGED_TO_MAIN" in p76_doc_text
