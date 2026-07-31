"""Tests for P268D-4 draw-order H1 NULL closeout artifact (governance closeout only)."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "research"

OUTPUT_JSON = OUT_DIR / "p268d4_draw_order_h1_null_closeout_20260611.json"
OUTPUT_MD = OUT_DIR / "p268d4_draw_order_h1_null_closeout_20260611.md"

VALID_FINAL_CLASSIFICATIONS = {
    "P268D4_DRAW_ORDER_H1_NULL_CLOSEOUT_COMPLETE",
    "P268D4_DRAW_ORDER_H1_NULL_CLOSEOUT_BLOCKED_STATE_MISMATCH",
    "P268D4_DRAW_ORDER_H1_NULL_CLOSEOUT_BLOCKED_ARTIFACT_MISSING",
    "P268D4_DRAW_ORDER_H1_NULL_CLOSEOUT_BLOCKED_SCOPE_CONFLICT",
}


@pytest.fixture(scope="module")
def artifact():
    assert OUTPUT_JSON.exists(), f"missing {OUTPUT_JSON}"
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    assert OUTPUT_MD.exists(), f"missing {OUTPUT_MD}"
    return OUTPUT_MD.read_text(encoding="utf-8")


def test_json_artifact_exists_and_valid(artifact):
    assert artifact["task_id"] == "P268D4"


def test_markdown_artifact_exists(md_text):
    assert "P268D-4" in md_text
    assert len(md_text) > 0


def test_h1_primary_fail_present(artifact, md_text):
    assert artifact["p268d3_result_summary"]["h1_classification"] == "H1_PRIMARY_FAIL"
    assert artifact["p268d3_result_summary"]["primary_result"]["classification"] == "H1_PRIMARY_FAIL"
    assert "H1_PRIMARY_FAIL" in md_text


def test_daily_539_p_value_present(artifact, md_text):
    p = artifact["p268d3_result_summary"]["primary_result"]["p_value_one_sided"]
    assert abs(p - 0.3050694930506949) < 1e-12
    alpha = artifact["p268d3_result_summary"]["primary_result"]["alpha"]
    assert alpha == 0.01
    assert "0.3051" in md_text
    assert "0.01" in md_text


def test_no_h2_h3_continuation_claim(artifact, md_text):
    assert artifact["p268d3_result_summary"]["h2_h3_run"] is False
    assert artifact["closeout_conclusion"]["h2_h3_authorization"]["authorized"] is False
    assert artifact["h2_h3_run"] is False
    text = md_text.lower()
    assert "h2/h3 are not authorized" in text or "not authorized" in text
    assert "must not be run" in text


def test_no_strategy_claim(artifact, md_text):
    assert artifact["p268d3_result_summary"]["strategy_generated"] is False
    assert artifact["closeout_conclusion"]["strategy_authorization"]["authorized"] is False
    assert artifact["strategy_generated"] is False
    assert artifact["closeout_conclusion"]["no_strategy"] is True


def test_no_hit_rate_improvement_claim(artifact, md_text):
    assert artifact["hit_rate_claim"] is False
    assert artifact["closeout_conclusion"]["no_hit_rate_improvement_claim"] is True
    text = md_text.lower()
    assert "hit rate improvement" not in text
    assert "success rate improvement" not in text


def test_no_registry_write(artifact):
    assert artifact["hypothesis_registry_write"] is False
    assert artifact["closeout_conclusion"]["no_registry_write"] is True
    assert artifact["boundary"]["hypothesis_registry_write_in_this_task"] is False


def test_no_db_write(artifact):
    assert artifact["db_write"] is False
    assert artifact["closeout_conclusion"]["no_db_write"] is True
    assert artifact["boundary"]["db_write_in_this_task"] is False


def test_p268d3_script_not_executed(artifact):
    assert artifact["boundary"]["p268d3_script_executed_in_this_task"] is False


def test_secondary_games_exploratory_only(artifact):
    secondary = artifact["p268d3_result_summary"]["secondary_results"]
    assert len(secondary) == 4
    for r in secondary:
        assert r["role"] == "SECONDARY_EXPLORATORY"


def test_draw_order_line_classified_as_null_closure(artifact, md_text):
    assert artifact["closeout_conclusion"]["draw_order_line_classification"] == "DIAGNOSTICS_ONLY_NULL_CLOSURE"
    assert "DIAGNOSTICS-ONLY NULL CLOSURE" in md_text or "DIAGNOSTICS_ONLY_NULL_CLOSURE" in md_text


def test_next_frontier_pointer_present(artifact):
    pointer = artifact["next_frontier_pointer"]
    assert "do_not_continue" in pointer
    assert any("H2" in item for item in pointer["do_not_continue"])
    assert any("H3" in item for item in pointer["do_not_continue"])
    assert "recommendation" in pointer
    assert "new" in pointer["recommendation"].lower()


def test_final_classification_allowed(artifact):
    assert artifact["final_classification"] in VALID_FINAL_CLASSIFICATIONS


def test_p268d3_pr_merged(artifact):
    assert artifact["p268d3_pr_status"]["pr_number"] == 411
    assert artifact["p268d3_pr_status"]["merged"] is True
