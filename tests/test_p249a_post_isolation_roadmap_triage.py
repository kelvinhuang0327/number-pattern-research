"""Tests for P249A — Post-isolation roadmap triage."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p249a_post_isolation_roadmap_triage_20260606.json"
MD_PATH = OUTPUTS / "p249a_post_isolation_roadmap_triage_20260606.md"

REQUIRED_CANDIDATE_FIELDS = {"candidate_id", "title", "type", "value", "risk",
                              "urgency", "recommended_now", "reason"}


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P249A JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


class TestP249AJSONStructure:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_task_id(self, report):
        assert report["task_id"] == "P249A"

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_classification(self, report):
        assert "TRIAGE" in report["classification"].upper()


class TestP249AClosure:
    def test_closure_verified_present(self, report):
        assert "p246_p248_closure_verified" in report

    def test_p248a_artifact_exists(self, report):
        assert report["p246_p248_closure_verified"]["p248a_artifact_exists"] is True

    def test_p247g_artifact_exists(self, report):
        assert report["p246_p248_closure_verified"]["p247g_artifact_exists"] is True

    def test_active_task_waiting(self, report):
        assert report["p246_p248_closure_verified"]["active_task_waiting"] is True

    def test_closure_all_ok(self, report):
        assert report["p246_p248_closure_verified"]["all_ok"] is True

    def test_phase0_expected_state_present(self, report):
        es = report["phase0_expected_state"]
        assert es["big_lotto_canonical_isolation"] == "COMPLETE"
        assert es["canonical_main_draw_rows"] == 2_113
        assert es["raw_big_lotto_rows"] == 22_238


class TestP249ACandidateTasks:
    def test_at_least_5_candidates(self, report):
        assert len(report["candidate_tasks"]) >= 5

    def test_at_least_8_candidates(self, report):
        assert len(report["candidate_tasks"]) >= 8

    def test_each_candidate_has_required_fields(self, report):
        for t in report["candidate_tasks"]:
            for field in REQUIRED_CANDIDATE_FIELDS:
                assert field in t, f"Candidate {t.get('candidate_id')} missing field: {field}"

    def test_each_candidate_has_value_field(self, report):
        for t in report["candidate_tasks"]:
            assert "value" in t and len(t["value"]) > 0

    def test_each_candidate_has_risk_field(self, report):
        for t in report["candidate_tasks"]:
            assert "risk" in t and len(t["risk"]) > 0

    def test_each_candidate_has_urgency_field(self, report):
        for t in report["candidate_tasks"]:
            assert "urgency" in t and len(t["urgency"]) > 0

    def test_each_candidate_has_recommended_now(self, report):
        for t in report["candidate_tasks"]:
            assert "recommended_now" in t

    def test_candidate_ids_unique(self, report):
        ids = [t["candidate_id"] for t in report["candidate_tasks"]]
        assert len(ids) == len(set(ids))


class TestP249ATypeD:
    def test_type_d_candidates_require_authorization(self, report):
        """Type D candidates must document authorization requirement."""
        for t in report["candidate_tasks"]:
            if "Type D" in t["type"] or "type d" in t["type"].lower():
                auth = t.get("authorization_required", "")
                assert len(auth) > 0, (
                    f"Type D candidate {t['candidate_id']} missing authorization_required"
                )
                assert "Type D" in auth or "authorization" in auth.lower() or "Explicit" in auth


class TestP249ARecommendedNext:
    def test_recommended_next_task_present(self, report):
        assert "recommended_next_task" in report
        rnt = report["recommended_next_task"]
        assert isinstance(rnt, dict)

    def test_recommended_next_has_title(self, report):
        assert len(report["recommended_next_task"]["title"]) > 0

    def test_recommended_next_has_rationale(self, report):
        assert len(report["recommended_next_task"]["rationale"]) > 0

    def test_recommended_next_no_prediction_edge(self, report):
        rnt = report["recommended_next_task"]
        assert rnt.get("no_prediction_edge_claim") is True

    def test_recommended_next_no_betting_advice(self, report):
        rnt = report["recommended_next_task"]
        assert rnt.get("no_betting_advice") is True

    def test_recommended_is_low_risk(self, report):
        rnt = report["recommended_next_task"]
        title = rnt["title"].lower()
        rationale = rnt["rationale"].lower()
        # Recommended task should be type B or doc-only or read-only
        assert (
            "type b" in rationale
            or "doc-only" in rationale
            or "doc only" in rationale
            or "read-only" in rationale
        ), "Recommended task should be low-risk (Type B, doc-only, or read-only)"


class TestP249ACompliance:
    def test_no_db_write_confirmed(self, report):
        assert report["no_db_write_confirmed"] is True

    def test_no_prediction_betting(self, report):
        assert report["no_prediction_betting_recommendation"] is True

    def test_no_production_recommendation(self, report):
        assert report["no_production_recommendation_change"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_final_decision_no_db_write(self, report):
        assert "no db write" in report["final_decision"].lower()

    def test_final_decision_no_prediction(self, report):
        fd = report["final_decision"].lower()
        assert "prediction" in fd or "betting" in fd


class TestP249ARanking:
    def test_ranking_summary_present(self, report):
        rs = report["ranking_summary"]
        assert isinstance(rs, list) and len(rs) >= 5

    def test_ranking_has_sequential_ranks(self, report):
        ranks = sorted(r["rank"] for r in report["ranking_summary"])
        assert ranks == list(range(1, len(ranks) + 1))

    def test_closed_research_lines_present(self, report):
        closed = report.get("closed_research_lines", [])
        assert len(closed) >= 4

    def test_daily_539_rejected_recorded(self, report):
        lines = [r["line"] for r in report.get("closed_research_lines", [])]
        assert any("DAILY_539" in l or "539" in l for l in lines)

    def test_power_lotto_null_recorded(self, report):
        lines = [r["line"] for r in report.get("closed_research_lines", [])]
        assert any("POWER" in l or "power" in l.lower() for l in lines)


class TestP249AMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_no_betting_advice(self, md):
        assert "betting" in md.lower()

    def test_md_no_prediction_overclaim(self, md):
        assert "does not imply" in md.lower() or "no prediction" in md.lower()

    def test_md_mentions_recommended_next(self, md):
        assert "recommended next task" in md.lower()

    def test_md_mentions_type_b(self, md):
        assert "type b" in md.lower()

    def test_md_mentions_annotation_table_deferred(self, md):
        assert "annotation" in md.lower()

    def test_md_canonical_counts_present(self, md):
        assert "2,113" in md or "2113" in md
        assert "22,238" in md or "22238" in md
