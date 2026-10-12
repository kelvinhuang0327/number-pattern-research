"""
P255A — Ingest / Backfill Safety Boundary Audit — Tests

Verifies the JSON artifact is well-formed and contains the required fields,
classifications, and safety flags.  Read-only: no DB access, no live endpoints.
"""

import json
import os
import pytest

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JSON_PATH = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p255a_ingest_backfill_safety_audit_20260608.json"
)


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(_JSON_PATH), f"Artifact not found: {_JSON_PATH}"
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Basic parse + classification
# ---------------------------------------------------------------------------

class TestArtifactBasics:
    def test_json_parses(self, artifact):
        assert isinstance(artifact, dict)

    def test_schema_version(self, artifact):
        assert artifact.get("schema_version") == "1.0"

    def test_task_id(self, artifact):
        assert artifact.get("task_id") == "P255A"

    def test_classification(self, artifact):
        assert artifact.get("classification") == "INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE"

    def test_date(self, artifact):
        assert artifact.get("date") == "2026-06-08"


# ---------------------------------------------------------------------------
# PR statuses
# ---------------------------------------------------------------------------

class TestPRStatuses:
    def test_pr360_merged(self, artifact):
        assert artifact["pr360_status"]["state"] == "MERGED"
        assert artifact["pr360_status"]["pr"] == 360

    def test_pr361_merged(self, artifact):
        assert artifact["pr361_status"]["state"] == "MERGED"
        assert artifact["pr361_status"]["pr"] == 361

    def test_pr362_merged(self, artifact):
        assert artifact["pr362_status"]["state"] == "MERGED"
        assert artifact["pr362_status"]["pr"] == 362

    def test_pr360_merge_commit_present(self, artifact):
        commit = artifact["pr360_status"]["merge_commit"]
        assert isinstance(commit, str) and len(commit) >= 20

    def test_pr361_merge_commit_present(self, artifact):
        commit = artifact["pr361_status"]["merge_commit"]
        assert isinstance(commit, str) and len(commit) >= 20

    def test_pr362_merge_commit_present(self, artifact):
        commit = artifact["pr362_status"]["merge_commit"]
        assert isinstance(commit, str) and len(commit) >= 20


# ---------------------------------------------------------------------------
# Trigger path inventory
# ---------------------------------------------------------------------------

class TestTriggerPathInventory:
    def test_inventory_exists_and_nonempty(self, artifact):
        inv = artifact.get("trigger_path_inventory")
        assert isinstance(inv, list) and len(inv) > 0

    def test_inventory_count_matches(self, artifact):
        assert artifact["trigger_path_count"] == len(artifact["trigger_path_inventory"])

    def test_all_paths_have_id(self, artifact):
        for p in artifact["trigger_path_inventory"]:
            assert "id" in p and p["id"].startswith("T")

    def test_all_paths_have_classification(self, artifact):
        valid_classes = {
            "READ_ONLY_LOG", "DRY_RUN_SAFE", "WRITE_CAPABLE_REQUIRES_GUARD",
            "AUTO_TRIGGER_RISK", "TEST_ONLY", "UNKNOWN_NEEDS_SCOPE"
        }
        for p in artifact["trigger_path_inventory"]:
            assert p.get("classification") in valid_classes, (
                f"Path {p['id']} has unknown classification: {p.get('classification')}"
            )

    def test_write_capable_paths_flagged(self, artifact):
        write_paths = [p for p in artifact["trigger_path_inventory"]
                       if p.get("writes_db")]
        assert len(write_paths) >= 3, "Expected at least 3 DB-writing paths"

    def test_backfill_incident_path_present(self, artifact):
        incident = [p for p in artifact["trigger_path_inventory"]
                    if p.get("critical_finding")]
        assert len(incident) >= 1, "Expected at least one path marked critical_finding"

    def test_auto_load_only_reads(self, artifact):
        auto_paths = [p for p in artifact["trigger_path_inventory"]
                      if p.get("auto_trigger_on_load")]
        for p in auto_paths:
            assert not p.get("writes_db"), (
                f"Auto-triggered path {p['id']} should not write DB"
            )


# ---------------------------------------------------------------------------
# Write-capable paths
# ---------------------------------------------------------------------------

class TestWriteCapablePaths:
    def test_write_capable_paths_exists(self, artifact):
        wcp = artifact.get("write_capable_paths")
        assert isinstance(wcp, list) and len(wcp) > 0

    def test_write_capable_count_matches(self, artifact):
        assert artifact["write_capable_path_count"] == len(artifact["write_capable_paths"])

    def test_all_write_capable_are_correctly_classified(self, artifact):
        for p in artifact["write_capable_paths"]:
            assert p["classification"] == "WRITE_CAPABLE_REQUIRES_GUARD"

    def test_backfill_dry_run_false_present(self, artifact):
        paths = artifact["write_capable_paths"]
        backfill_write = [p for p in paths if "dry_run=False" in p.get("path", "")
                          and "backfill" in p.get("path", "").lower()]
        assert len(backfill_write) >= 1, "Expected at least one write-capable backfill path"


# ---------------------------------------------------------------------------
# Dry-run safety assessment
# ---------------------------------------------------------------------------

class TestDryRunSafetyAssessment:
    def test_assessment_exists(self, artifact):
        assert "dry_run_safety_assessment" in artifact

    def test_backfill_endpoint_has_high_risk(self, artifact):
        ep = artifact["dry_run_safety_assessment"].get("backfill_endpoint", {})
        assert ep.get("dry_run_supported") is True
        assert ep.get("dry_run_default") is False
        assert "HIGH" in ep.get("risk", "")

    def test_fetch_latest_default_no_insert(self, artifact):
        ep = artifact["dry_run_safety_assessment"].get("fetch_latest_endpoint", {})
        assert ep.get("insert_if_new_default") is False

    def test_scan_missing_is_safe(self, artifact):
        ep = artifact["dry_run_safety_assessment"].get("scan_missing_endpoint", {})
        assert "NONE" in ep.get("risk", "")

    def test_log_endpoint_is_safe(self, artifact):
        ep = artifact["dry_run_safety_assessment"].get("log_endpoint", {})
        assert "NONE" in ep.get("risk", "")


# ---------------------------------------------------------------------------
# Recommended guardrails
# ---------------------------------------------------------------------------

class TestRecommendedGuardrails:
    def test_guardrails_exist_and_nonempty(self, artifact):
        g = artifact.get("recommended_guardrails")
        assert isinstance(g, list) and len(g) > 0

    def test_guardrails_include_default_dry_run(self, artifact):
        types = [g.get("guardrail_type") for g in artifact["recommended_guardrails"]]
        assert "default_dry_run" in types

    def test_guardrails_include_explicit_confirm_token(self, artifact):
        types = [g.get("guardrail_type") for g in artifact["recommended_guardrails"]]
        assert "explicit_confirm_token" in types

    def test_guardrails_include_audit_log(self, artifact):
        types = [g.get("guardrail_type") for g in artifact["recommended_guardrails"]]
        assert "audit_log" in types

    def test_guardrails_include_controlled_apply_sha(self, artifact):
        types = [g.get("guardrail_type") for g in artifact["recommended_guardrails"]]
        assert "controlled_apply_backup_sha" in types

    def test_guardrail_count_matches(self, artifact):
        assert artifact["recommended_guardrail_count"] == len(artifact["recommended_guardrails"])

    def test_all_guardrails_have_priority(self, artifact):
        for g in artifact["recommended_guardrails"]:
            assert g.get("priority") in {"P0", "P1", "P2"}

    def test_at_least_one_p0_guardrail(self, artifact):
        p0 = [g for g in artifact["recommended_guardrails"] if g["priority"] == "P0"]
        assert len(p0) >= 1


# ---------------------------------------------------------------------------
# Current accepted baseline
# ---------------------------------------------------------------------------

class TestCurrentAcceptedBaseline:
    def test_baseline_exists(self, artifact):
        assert "current_accepted_baseline" in artifact

    def test_big_lotto_raw(self, artifact):
        assert artifact["current_accepted_baseline"]["BIG_LOTTO_raw"] == 22239

    def test_big_lotto_canonical(self, artifact):
        assert artifact["current_accepted_baseline"]["BIG_LOTTO_canonical"] == 2114

    def test_big_lotto_add_on(self, artifact):
        assert artifact["current_accepted_baseline"]["BIG_LOTTO_add_on"] == 19100

    def test_power_lotto_raw(self, artifact):
        assert artifact["current_accepted_baseline"]["POWER_LOTTO_raw"] == 1917

    def test_daily_539_raw(self, artifact):
        assert artifact["current_accepted_baseline"]["DAILY_539_raw"] == 5882

    def test_replays(self, artifact):
        assert artifact["current_accepted_baseline"]["strategy_prediction_replays"] == 94924

    def test_stale_values_documented(self, artifact):
        stale = artifact["current_accepted_baseline"].get("stale_must_not_reuse", {})
        assert stale.get("BIG_LOTTO_raw_stale") == 22238
        assert stale.get("BIG_LOTTO_canonical_stale") == 2113


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------

class TestSafetyFlags:
    def test_no_db_write_confirmed(self, artifact):
        assert artifact.get("no_db_write_confirmed") is True

    def test_no_registry_mutation_confirmed(self, artifact):
        assert artifact.get("no_registry_mutation_confirmed") is True

    def test_no_strategy_promotion_confirmed(self, artifact):
        assert artifact.get("no_strategy_promotion_confirmed") is True

    def test_no_betting_advice_confirmed(self, artifact):
        assert artifact.get("no_betting_advice_confirmed") is True


# ---------------------------------------------------------------------------
# Final decision
# ---------------------------------------------------------------------------

class TestFinalDecision:
    def test_final_decision_exists(self, artifact):
        assert "final_decision" in artifact

    def test_final_decision_is_hold(self, artifact):
        fd = artifact.get("final_decision", "")
        assert "HOLD" in fd, f"Expected HOLD in final_decision, got: {fd[:80]}"

    def test_recommended_next_task_is_hold(self, artifact):
        rnt = artifact.get("recommended_next_task", "")
        assert "HOLD" in rnt or "WAITING_FOR_USER_AUTHORIZATION" in rnt

    def test_phase0_head_equals_origin_main(self, artifact):
        assert artifact["phase0_summary"]["HEAD_equals_origin_main"] is True


# ---------------------------------------------------------------------------
# Auto-trigger risks
# ---------------------------------------------------------------------------

class TestAutoTriggerRisks:
    def test_risks_exist(self, artifact):
        risks = artifact.get("auto_trigger_risks")
        assert isinstance(risks, list) and len(risks) > 0

    def test_risk_count_matches(self, artifact):
        assert artifact["auto_trigger_risk_count"] == len(artifact["auto_trigger_risks"])

    def test_all_risks_have_severity(self, artifact):
        valid = {"HIGH", "MEDIUM", "LOW", "CRITICAL"}
        for r in artifact["auto_trigger_risks"]:
            assert r.get("severity") in valid

    def test_high_risk_for_dry_run_default(self, artifact):
        high_risks = [r for r in artifact["auto_trigger_risks"]
                      if r.get("severity") == "HIGH"]
        assert len(high_risks) >= 1

    def test_r01_dry_run_default_present(self, artifact):
        ids = [r["risk_id"] for r in artifact["auto_trigger_risks"]]
        assert "R01" in ids

    def test_r02_frontend_gate_present(self, artifact):
        ids = [r["risk_id"] for r in artifact["auto_trigger_risks"]]
        assert "R02" in ids
