"""P254B — Fetcher repair governance closure tests.

Verifies the closure artifact documents the incident chain correctly.
Read-only: no DB writes, no API calls, no registry mutations.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p254b_fetcher_repair_governance_closure_20260608.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p254b_fetcher_repair_governance_closure_20260608.md"


@pytest.fixture(scope="module")
def artifact():
    assert JSON_PATH.exists(), f"P254B JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists(), f"P254B MD not found: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


class TestP254BArtifactStructure:
    def test_parses(self, artifact):
        assert isinstance(artifact, dict)

    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P254B"

    def test_schema_version(self, artifact):
        assert artifact["schema_version"] == "1.0"

    def test_classification(self, artifact):
        assert artifact["classification"] == "FETCHER_REPAIR_GOVERNANCE_CLOSURE_COMPLETE"


class TestP254BPRStatus:
    def test_pr360_merged(self, artifact):
        assert artifact["pr360_status"]["state"] == "MERGED"

    def test_pr360_merge_commit(self, artifact):
        assert artifact["pr360_status"]["merge_commit"] == "234cc02aee1c5d7a4e7990d3195ad4d987315a70"

    def test_pr361_merged(self, artifact):
        assert artifact["pr361_status"]["state"] == "MERGED"

    def test_pr361_merge_commit(self, artifact):
        assert artifact["pr361_status"]["merge_commit"] == "36f6862dc912af31115183cf6072dec939ed4dda"

    def test_pr360_no_db_write(self, artifact):
        assert artifact["pr360_status"]["db_write_in_pr360"] is False

    def test_pr361_no_db_write(self, artifact):
        assert artifact["pr361_status"]["db_write_in_pr361"] is False


class TestP254BAcceptedBaseline:
    def test_big_lotto_raw_22239(self, artifact):
        assert artifact["accepted_db_baseline"]["BIG_LOTTO_raw"] == 22_239

    def test_big_lotto_canonical_2114(self, artifact):
        assert artifact["accepted_db_baseline"]["BIG_LOTTO_canonical"] == 2_114

    def test_add_on_19100(self, artifact):
        assert artifact["accepted_db_baseline"]["BIG_LOTTO_add_on"] == 19_100

    def test_power_lotto_1917(self, artifact):
        assert artifact["accepted_db_baseline"]["POWER_LOTTO_raw"] == 1_917

    def test_daily539_5882(self, artifact):
        assert artifact["accepted_db_baseline"]["DAILY_539_raw"] == 5_882

    def test_replays_94924(self, artifact):
        assert artifact["accepted_db_baseline"]["strategy_prediction_replays"] == 94_924

    def test_stale_raw_22238_documented(self, artifact):
        stale = artifact["accepted_db_baseline"]["stale_values_must_not_reuse"]
        assert stale["BIG_LOTTO_raw_stale"] == 22_238

    def test_stale_canonical_2113_documented(self, artifact):
        stale = artifact["accepted_db_baseline"]["stale_values_must_not_reuse"]
        assert stale["BIG_LOTTO_canonical_stale"] == 2_113


class TestP254BEndpointSmoke:
    def test_log_endpoint_pass(self, artifact):
        assert artifact["endpoint_smoke_summary"]["GET_ingest_log"]["result"] == "PASS"

    def test_backfill_dry_run_pass(self, artifact):
        assert artifact["endpoint_smoke_summary"]["POST_ingest_backfill_dry_run"]["result"] == "PASS"

    def test_preflight_pass(self, artifact):
        assert artifact["endpoint_smoke_summary"]["OPTIONS_preflight"]["result"] == "PASS"

    def test_add_on_crash_pass(self, artifact):
        assert artifact["endpoint_smoke_summary"]["ADD_ON_crash_103000009_01"]["result"] == "PASS"


class TestP254BSkippedTestExplanation:
    def test_skipped_count(self, artifact):
        assert artifact["skipped_test_explanation"]["count"] == 7

    def test_mentions_numpy(self, artifact):
        reason = artifact["skipped_test_explanation"]["reason"].lower()
        assert "numpy" in reason

    def test_mentions_venv_smoke(self, artifact):
        comp = artifact["skipped_test_explanation"]["compensating_verification"]
        assert ".venv" in comp

    def test_mentions_endpoint_pass(self, artifact):
        comp = artifact["skipped_test_explanation"]["compensating_verification"].upper()
        assert "PASS" in comp


class TestP254BGovernanceLessons:
    def test_has_lessons(self, artifact):
        lessons = artifact["governance_lessons"]
        assert isinstance(lessons, list) and len(lessons) >= 2

    def test_separation_lesson_present(self, artifact):
        titles = " ".join(l["title"].lower() for l in artifact["governance_lessons"])
        assert "separate" in titles

    def test_stale_baseline_lesson_present(self, artifact):
        content = json.dumps(artifact["governance_lessons"]).lower()
        assert "22238" in content or "stale" in content

    def test_add_on_lesson_present(self, artifact):
        content = json.dumps(artifact["governance_lessons"]).lower()
        assert "add_on" in content or "isdigit" in content or "int()" in content


class TestP254BNoClaimFlags:
    def test_no_db_write(self, artifact):
        assert artifact["no_db_write_confirmed"] is True

    def test_no_registry_mutation(self, artifact):
        assert artifact["no_registry_mutation_confirmed"] is True

    def test_no_strategy_promotion(self, artifact):
        assert artifact["no_strategy_promotion_confirmed"] is True

    def test_no_betting_advice(self, artifact):
        assert artifact["no_betting_advice_confirmed"] is True

    def test_no_fetcher_code_changed(self, artifact):
        assert artifact["no_fetcher_code_changed_in_p254b"] is True

    def test_no_p247g_changed(self, artifact):
        assert artifact["no_p247g_constants_changed_in_p254b"] is True


class TestP254BFinalDecision:
    def test_final_decision_hold(self, artifact):
        decision = artifact["final_decision"].upper()
        assert "HOLD" in decision or "WAITING_FOR_USER_AUTHORIZATION" in decision

    def test_final_decision_no_db_write(self, artifact):
        text = artifact["final_decision"].lower()
        assert "db write" in text or "no db" in text or "non-dry-run" in text or "backfill" in text


class TestP254BMarkdown:
    def test_md_has_executive_summary(self, md):
        assert "Executive Summary" in md

    def test_md_incident_chain(self, md):
        assert "Incident Chain" in md

    def test_md_pr360_section(self, md):
        assert "PR #360" in md and "MERGED" in md

    def test_md_pr361_section(self, md):
        assert "PR #361" in md and "MERGED" in md

    def test_md_baseline_table(self, md):
        assert "22,239" in md and "2,114" in md

    def test_md_stale_warning(self, md):
        assert "22,238" in md or "stale" in md.lower()

    def test_md_endpoint_section(self, md):
        assert "Endpoint" in md

    def test_md_skipped_explanation(self, md):
        assert "numpy" in md.lower() or "skipped" in md.lower()

    def test_md_governance_lesson(self, md):
        assert "Governance Lesson" in md or "L_P254" in md

    def test_md_non_actions(self, md):
        assert "Non-Action" in md or "non-action" in md.lower() or "NOT" in md

    def test_md_recommended_hold(self, md):
        assert "HOLD" in md or "WAITING_FOR_USER_AUTHORIZATION" in md

    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower() or "No DB write" in md
