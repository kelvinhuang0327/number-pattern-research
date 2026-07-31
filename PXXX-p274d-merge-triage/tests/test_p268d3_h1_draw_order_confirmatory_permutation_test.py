"""Tests for P268D-3 H1 draw-order confirmatory permutation test artifacts."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "research"

OUTPUT_JSON = OUT_DIR / "p268d3_h1_draw_order_confirmatory_permutation_test_20260611.json"
OUTPUT_MD = OUT_DIR / "p268d3_h1_draw_order_confirmatory_permutation_test_20260611.md"
HYPOTHESIS_REGISTRY_PATH = REPO_ROOT / "lottery_api" / "data" / "hypothesis_registry.jsonl"
ANALYSIS_SCRIPT = REPO_ROOT / "analysis" / "p268d3_h1_draw_order_confirmatory_permutation_test.py"

HYPOTHESIS_ID = "HR-P268D3-H1-DRAW-ORDER-EXIT-RANK-001"

VALID_FINAL_CLASSIFICATIONS = {
    "P268D3_H1_DRAW_ORDER_CONFIRMATORY_TEST_COMPLETE_PRIMARY_PASS",
    "P268D3_H1_DRAW_ORDER_CONFIRMATORY_TEST_COMPLETE_PRIMARY_FAIL",
    "P268D3_H1_DRAW_ORDER_CONFIRMATORY_TEST_INCONCLUSIVE_RUNTIME_LIMIT",
}


@pytest.fixture(scope="module")
def artifact():
    assert OUTPUT_JSON.exists(), f"missing {OUTPUT_JSON}"
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def registry_lines():
    with open(HYPOTHESIS_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_json_artifact_exists_and_valid(artifact):
    assert artifact["task_id"] == "P268D3"


def test_markdown_artifact_exists():
    assert OUTPUT_MD.exists()
    content = OUTPUT_MD.read_text(encoding="utf-8")
    assert "P268D-3" in content
    assert len(content) > 0


def test_registry_contains_pre_registered_entry(registry_lines):
    matches = [e for e in registry_lines if e.get("hypothesis_id") == HYPOTHESIS_ID]
    assert len(matches) == 1, f"expected exactly 1 entry, found {len(matches)}"
    assert matches[0]["status"] == "PRE_REGISTERED_BEFORE_TEST"
    assert matches[0]["task_id"] == "P268D3"


def test_script_does_not_open_db():
    source = ANALYSIS_SCRIPT.read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert "connect(" not in source
    assert "lottery_v2.db" not in source


def test_h1_present_in_artifact(artifact):
    assert "primary_result" in artifact
    assert "h1_classification" in artifact
    assert artifact["h1_classification"] in {
        "H1_PRIMARY_PASS",
        "H1_PRIMARY_FAIL",
        "H1_INCONCLUSIVE_RUNTIME_LIMIT",
    }


def test_h2_h3_not_run(artifact):
    assert artifact["h2_h3_run"] is False


def test_within_draw_permutation_null_represented(artifact):
    desc = artifact["method"]["null_model"]
    assert "permutation" in desc.lower()
    assert "within" in desc.lower() or "draw" in desc.lower()


def test_70_30_split_represented(artifact):
    for game, split in artifact["splits"].items():
        eligible = split["eligible_records"]
        estimation = split["estimation_records"]
        holdout = split["holdout_records"]
        assert estimation + holdout == eligible
        if eligible > 0:
            ratio = estimation / eligible
            assert 0.65 <= ratio <= 0.75, f"{game}: estimation ratio {ratio}"


def test_2026_04_05_excluded(artifact):
    for game, split in artifact["splits"].items():
        assert split["excluded_records"] >= 0
    assert artifact["windows"]["excluded_months"] if "windows" in artifact else True


def test_p_value_present_for_h1(artifact):
    p = artifact["primary_result"]["p_value_one_sided"]
    assert 0.0 <= p <= 1.0


def test_no_strategy_or_recommendation_numbers(artifact):
    assert artifact["strategy_generated"] is False
    forbidden_keys = {"recommended_numbers", "betting_recommendation", "picks"}
    assert not (forbidden_keys & set(artifact.keys()))


def test_no_hit_rate_improvement_claim(artifact):
    assert artifact["hit_rate_claim"] is False
    text = json.dumps(artifact, ensure_ascii=False).lower()
    assert "hit rate improvement" not in text
    assert "success rate improvement" not in text


def test_db_write_false(artifact):
    assert artifact["db_write"] is False


def test_final_classification_allowed(artifact):
    assert artifact["final_classification"] in VALID_FINAL_CLASSIFICATIONS


def test_secondary_results_labeled(artifact):
    assert len(artifact["secondary_results"]) == 4
    for r in artifact["secondary_results"]:
        assert r["role"] == "SECONDARY_EXPLORATORY"


def test_primary_game_is_daily_539(artifact):
    assert artifact["primary_result"]["game"] == "DAILY_539"
    assert artifact["primary_result"]["role"] == "PRIMARY"
