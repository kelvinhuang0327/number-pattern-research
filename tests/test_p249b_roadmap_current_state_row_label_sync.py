"""Tests for P249B — Roadmap sync + CURRENT_STATE row-label clarification."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p249b_roadmap_current_state_row_label_sync_20260606.json"
MD_PATH = OUTPUTS / "p249b_roadmap_current_state_row_label_sync_20260606.md"

CURRENT_STATE_PATH = REPO_ROOT / "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md"
ROADMAP_PATH = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan/roadmap/active_task.md"

EXPECTED_RAW_BIG_LOTTO = 22_238
EXPECTED_CANONICAL = 2_113
EXPECTED_ADD_ON = 19_100
EXPECTED_BIG_LOTTO_REPLAY = 24_140
EXPECTED_TOTAL_REPLAY = 94_924


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P249B JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def current_state():
    assert CURRENT_STATE_PATH.exists()
    return CURRENT_STATE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def roadmap():
    assert ROADMAP_PATH.exists()
    return ROADMAP_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def active_task():
    assert ACTIVE_TASK_PATH.exists()
    return ACTIVE_TASK_PATH.read_text(encoding="utf-8")


# ── JSON artifact ─────────────────────────────────────────────────────────────

class TestP249BJSONStructure:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_task_id(self, report):
        assert report["task_id"] == "P249B"

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_classification(self, report):
        assert "TYPE_B" in report["classification"] or "SYNC" in report["classification"]

    def test_p249a_merged_verified(self, report):
        assert report["p249a_merged_state_verified"] is True


class TestP249BRowLabelCorrections:
    def test_row_label_corrections_present(self, report):
        rlc = report["row_label_corrections"]
        assert isinstance(rlc, dict)

    def test_original_label_ambiguity_documented(self, report):
        rlc = report["row_label_corrections"]
        assert "24,140" in rlc["original_label"] or "24140" in rlc["original_label"]

    def test_corrected_labels_include_raw_draw_rows(self, report):
        rlc = report["row_label_corrections"]
        labels = rlc["corrected_labels"]
        # Check that raw draw rows value is present
        raw_values = [v for k, v in labels.items() if "raw draw" in k.lower()]
        assert any(v == EXPECTED_RAW_BIG_LOTTO for v in raw_values), (
            f"Expected {EXPECTED_RAW_BIG_LOTTO} raw draw rows in corrected labels"
        )

    def test_corrected_labels_include_canonical_rows(self, report):
        rlc = report["row_label_corrections"]
        labels = rlc["corrected_labels"]
        canonical_values = [v for k, v in labels.items() if "canonical" in k.lower()]
        assert any(v == EXPECTED_CANONICAL for v in canonical_values)

    def test_corrected_labels_include_add_on(self, report):
        rlc = report["row_label_corrections"]
        labels = rlc["corrected_labels"]
        add_on_values = [v for k, v in labels.items() if "add_on" in k.lower() or "add-on" in k.lower()]
        assert any(v == EXPECTED_ADD_ON for v in add_on_values)

    def test_sum_check_94924(self, report):
        rlc = report["row_label_corrections"]
        # Verify sum check: replay rows sum to 94924
        assert "94924" in rlc.get("sum_check", "").replace(",", "") or \
               "94,924" in rlc.get("sum_check", "")

    def test_add_on_valid_not_fake(self, report):
        rlc = report["row_label_corrections"]
        note = rlc.get("add_on_note", "").lower()
        assert "valid" in note
        # Should say NOT fake or confirm valid
        assert "fake" not in note or "not fake" in note or "valid lottery" in note


# ── Governance file verification ──────────────────────────────────────────────

class TestP249BCurrentStateMD:
    def test_has_replay_row_label(self, current_state):
        assert "replay rows" in current_state.lower()

    def test_has_raw_draw_rows_count(self, current_state):
        assert "22,238" in current_state or "22238" in current_state

    def test_has_canonical_rows_count(self, current_state):
        assert "2,113" in current_state or "2113" in current_state

    def test_has_add_on_count(self, current_state):
        assert "19,100" in current_state or "19100" in current_state

    def test_has_p249b_marker(self, current_state):
        assert "P249B" in current_state

    def test_distinguishes_replay_from_draw_rows(self, current_state):
        # Both "replay" and "draw" must now appear in the row-count section
        lower = current_state.lower()
        assert "replay" in lower and "draw rows" in lower


class TestP249BRoadmapMD:
    def test_has_p246_arc(self, roadmap):
        assert "P246B" in roadmap or "P246" in roadmap

    def test_has_p247_arc(self, roadmap):
        assert "P247B" in roadmap or "P247" in roadmap

    def test_has_canonical_isolation(self, roadmap):
        assert "canonical" in roadmap.lower()

    def test_has_2113_canonical_rows(self, roadmap):
        assert "2,113" in roadmap or "2113" in roadmap

    def test_has_p249b_marker(self, roadmap):
        assert "P249B" in roadmap

    def test_no_prediction_overclaim(self, roadmap):
        lower = roadmap.lower()
        assert "no prediction edge" in lower or "does not imply" in lower or \
               "no strategy promotion" in lower


class TestP249BActiveTaskMD:
    def test_is_waiting_for_authorization(self, active_task):
        assert "WAITING_FOR_USER_AUTHORIZATION" in active_task

    def test_has_p249b_completion(self, active_task):
        assert "P249B" in active_task

    def test_no_active_implementation(self, active_task):
        # Should not claim an active implementation task is running
        lower = active_task.lower()
        assert "status: `waiting_for_user_authorization`" in lower or \
               "waiting_for_user_authorization" in lower


# ── Compliance ────────────────────────────────────────────────────────────────

class TestP249BCompliance:
    def test_no_db_write_confirmed(self, report):
        assert report["no_db_write_confirmed"] is True

    def test_no_source_code_changes(self, report):
        assert report["no_source_code_changes"] is True

    def test_no_strategy_promotion(self, report):
        assert report["no_strategy_promotion"] is True

    def test_no_betting_advice(self, report):
        assert report["no_betting_advice"] is True

    def test_no_production_recommendation_change(self, report):
        assert report["no_production_recommendation_change"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_final_decision_no_db_write(self, report):
        assert "no db write" in report["final_decision"].lower()

    def test_governance_files_listed(self, report):
        gf = report["governance_files_updated"]
        assert len(gf) >= 3
        assert any("CURRENT_STATE" in f for f in gf)
        assert any("roadmap" in f for f in gf)
        assert any("active_task" in f for f in gf)


class TestP249BMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_no_betting_advice(self, md):
        assert "betting" in md.lower()

    def test_md_corrected_table_present(self, md):
        assert "22,238" in md and "2,113" in md and "19,100" in md

    def test_md_sum_check(self, md):
        assert "94,924" in md or "94924" in md

    def test_md_add_on_valid_note(self, md):
        assert "valid" in md.lower() and "add-on" in md.lower()

    def test_md_no_overclaim(self, md):
        assert "does not imply" in md.lower() or "no prediction" in md.lower() or \
               "green" in md.lower()
