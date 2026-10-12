"""Tests for P248A — BIG_LOTTO canonical isolation governance closure."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p248a_big_lotto_canonical_isolation_governance_closure_20260606.json"
MD_PATH = OUTPUTS / "p248a_big_lotto_canonical_isolation_governance_closure_20260606.md"

EXPECTED_CANONICAL = 2_113
EXPECTED_RAW = 22_238
EXPECTED_ADD_ON = 19_100

EXPECTED_DEPENDENCY_TASKS = [
    "P246B", "P246C", "P246D", "P246E", "P246F",
    "P246G", "P246H", "P246I", "P246J", "P246K",
    "P247A", "P247B", "P247C", "P247D", "P247E", "P247F", "P247G",
]

ACTIVE_PATH_KEYWORDS = [
    "quick_predict",
    "rsm_bootstrap",
    "core_satellite",
    "drift_detector",
    "backtest_framework",
    "scheduler",
]


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P248A JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


class TestP248AJSONStructure:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_task_id(self, report):
        assert report["task_id"] == "P248A"

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_classification(self, report):
        assert report["classification"] == "GOVERNANCE_CLOSURE"

    def test_p247g_merged_verified(self, report):
        assert report["p247g_merged_state_verified"] is True


class TestP248ADependencyArtifacts:
    def test_dependency_artifacts_verified_present(self, report):
        assert "dependency_artifacts_verified" in report

    def test_all_dependency_tasks_present(self, report):
        dep = report["dependency_artifacts_verified"]
        tasks = [r["task"] for r in dep["results"]]
        for expected in EXPECTED_DEPENDENCY_TASKS:
            assert expected in tasks, f"Missing dependency task: {expected}"

    def test_all_dependencies_ok(self, report):
        dep = report["dependency_artifacts_verified"]
        failed = [r for r in dep["results"] if r["status"] != "OK"]
        assert failed == [], f"Failed dependencies: {[r['task'] for r in failed]}"

    def test_dependency_count_is_17(self, report):
        dep = report["dependency_artifacts_verified"]
        assert len(dep["results"]) == 17

    def test_p246b_through_p247g_included(self, report):
        dep = report["dependency_artifacts_verified"]
        tasks = [r["task"] for r in dep["results"]]
        assert "P246B" in tasks and "P247G" in tasks


class TestP248ACanonicalState:
    def test_canonical_state_present(self, report):
        cs = report["canonical_state"]
        assert isinstance(cs, dict)

    def test_canonical_main_draw_count(self, report):
        assert report["canonical_state"]["canonical_main_draw"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_total(self, report):
        assert report["canonical_state"]["raw_big_lotto_total"] == EXPECTED_RAW

    def test_add_on_count(self, report):
        assert report["canonical_state"]["add_on_prize_excluded"] == EXPECTED_ADD_ON

    def test_sum_check_consistent(self, report):
        cs = report["canonical_state"]
        total = (
            cs["add_on_prize_excluded"]
            + cs["date_format_alien"]
            + cs["small_pool_alien"]
            + cs["canonical_main_draw"]
        )
        assert total == cs["raw_big_lotto_total"]

    def test_db_view_name(self, report):
        assert report["canonical_state"]["db_view"] == "draws_big_lotto_canonical_main"

    def test_helper_backed_by_view(self, report):
        assert report["canonical_state"]["helper_backed_by_view"] is True

    def test_raw_access_preserved(self, report):
        assert report["canonical_state"]["raw_access_preserved"] is True

    def test_add_on_raw_accessible(self, report):
        assert report["canonical_state"]["add_on_records_raw_accessible"] is True


class TestP248AActivePaths:
    def test_active_paths_protected_present(self, report):
        ap = report["active_paths_protected"]
        assert isinstance(ap, list) and len(ap) >= 15

    def test_active_path_count_15(self, report):
        assert report["active_path_count"] == 15

    def test_active_paths_include_key_callers(self, report):
        all_paths = " ".join(p["path"] for p in report["active_paths_protected"])
        for kw in ACTIVE_PATH_KEYWORDS:
            assert kw in all_paths, f"Missing keyword in active paths: {kw}"

    def test_canonical_state_has_view_name(self, report):
        assert report["canonical_state"]["db_view"] == "draws_big_lotto_canonical_main"

    def test_canonical_state_has_helper_method(self, report):
        assert "get_canonical_draws" in report["canonical_state"]["helper_method"]

    def test_p247f_tools_in_active_paths(self, report):
        paths = [p["path"] for p in report["active_paths_protected"]]
        p247f_tools = [p for p in paths if "analyze_" in p or "audit_big_lotto" in p]
        assert len(p247f_tools) == 9


class TestP248ACompliance:
    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_no_prediction_betting_recommendation(self, report):
        assert report["no_prediction_betting_recommendation"] is True

    def test_no_production_recommendation_change(self, report):
        assert report["no_production_recommendation_change"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_raw_access_preserved(self, report):
        assert report["raw_access_preserved"] is True

    def test_raw_display_paths_unchanged(self, report):
        assert report["raw_display_history_paths_unchanged"] is True


class TestP248AGateStatus:
    def test_gate_status_present(self, report):
        gs = report["gate_status"]
        assert isinstance(gs, dict)

    def test_p246k_green(self, report):
        gs = report["gate_status"]
        assert "GREEN" in gs["P246K_canonical_randomness_audit"]

    def test_green_does_not_imply_prediction_edge(self, report):
        assert report["gate_status"]["green_implies_prediction_edge"] is False

    def test_green_does_not_imply_betting_advice(self, report):
        assert report["gate_status"]["green_implies_betting_advice"] is False

    def test_green_does_not_imply_strategy_promotion(self, report):
        assert report["gate_status"]["green_implies_strategy_promotion"] is False

    def test_no_overclaim_statement_present(self, report):
        no_claim = report["gate_status"]["no_overclaim_statement"]
        assert len(no_claim) > 50
        assert "prediction" in no_claim.lower() or "signal" in no_claim.lower()


class TestP248ADeferredItems:
    def test_remaining_deferred_items_present(self, report):
        ri = report["remaining_deferred_items"]
        assert isinstance(ri, list) and len(ri) >= 4

    def test_deferred_includes_archived_scripts(self, report):
        ri_str = " ".join(report["remaining_deferred_items"]).lower()
        assert "archived" in ri_str or "deferred" in ri_str

    def test_deferred_includes_annotation_table(self, report):
        ri_str = " ".join(report["remaining_deferred_items"]).lower()
        assert "annotation" in ri_str

    def test_deferred_includes_no_new_prediction(self, report):
        ri_str = " ".join(report["remaining_deferred_items"]).lower()
        assert "gate" in ri_str or "pre-registration" in ri_str or "hit-rate" in ri_str


class TestP248AGovernanceFiles:
    def test_governance_files_listed(self, report):
        gf = report["governance_files_updated"]
        assert isinstance(gf, list) and len(gf) >= 2

    def test_current_state_md_updated(self, report):
        gf = report["governance_files_updated"]
        assert any("CURRENT_STATE" in f for f in gf)

    def test_active_task_md_updated(self, report):
        gf = report["governance_files_updated"]
        assert any("active_task" in f for f in gf)

    def test_current_state_md_has_p248a_marker(self):
        cs_path = REPO_ROOT / "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md"
        assert cs_path.exists()
        content = cs_path.read_text()
        assert "P248A" in content
        assert "BIG_LOTTO_CANONICAL_ISOLATION_GOVERNANCE_CLOSURE" in content

    def test_active_task_md_has_p248a_completion(self):
        at_path = REPO_ROOT / "00-Plan/roadmap/active_task.md"
        assert at_path.exists()
        content = at_path.read_text()
        assert "P248A" in content
        assert "WAITING_FOR_USER_AUTHORIZATION" in content


class TestP248AMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower() or "raw accessible" in md.lower()

    def test_md_no_prediction_recommendation(self, md):
        text = md.lower()
        assert "no prediction" in text or "does not imply" in text

    def test_md_mentions_p246_arc(self, md):
        assert "P246" in md and "P247" in md

    def test_md_canonical_count(self, md):
        assert "2,113" in md or "2113" in md

    def test_md_no_betting_advice(self, md):
        assert "betting advice" in md.lower()
