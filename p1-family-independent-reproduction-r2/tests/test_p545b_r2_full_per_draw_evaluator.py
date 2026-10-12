"""Focused no-database tests for the P545B R2 evaluator."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from analysis import p545b_r2_full_per_draw_evaluator as evaluator


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry_and_identity():
    return evaluator.load_registry(REPO_ROOT)


@pytest.fixture(scope="module")
def committed_output():
    return json.loads((REPO_ROOT / evaluator.OUTPUT_JSON).read_text(encoding="utf-8"))


def test_registry_four_integrity_contracts(registry_and_identity):
    registry, identity = registry_and_identity
    assert registry["schema"] == evaluator.REGISTRY_SCHEMA
    assert identity == {
        "path": evaluator.REGISTRY_PATH,
        "byte_size": 52_393_107,
        "sha256": evaluator.REGISTRY_SHA256,
        "semantic_projection_digest": evaluator.REGISTRY_SEMANTIC_DIGEST,
        "canonical_payload_digest": evaluator.REGISTRY_CANONICAL_DIGEST,
    }


def test_full_scope_and_reconciliation(committed_output):
    assert committed_output["scope"] == {
        "betting_recommendation_produced": False,
        "frozen_cells": 36,
        "opportunities": 27_000,
        "sqlite_opened": False,
        "strategy_search_performed": False,
        "windows": 108,
    }
    assert len(committed_output["per_opportunity_evaluations"]) == 27_000
    assert len(committed_output["per_window_evaluations"]) == 108
    assert len(committed_output["group_evaluations"]) == 36
    assert {item["reconciliation"] for item in committed_output["per_window_evaluations"]} == {"PASS"}


def test_all_three_windows_for_every_frozen_cell(committed_output):
    observed = {}
    for item in committed_output["per_window_evaluations"]:
        observed.setdefault((item["lottery_type"], item["strategy_id"]), set()).add(item["window"])
    assert len(observed) == 36
    assert all(windows == {50, 300, 750} for windows in observed.values())


def test_committed_inference_summary_is_exact(committed_output):
    summary = committed_output["reconciliation"]["inference_summary"]
    assert summary["window_decision_counts"] == {
        "PRIZE_AWARE_DESCRIPTIVE_ONLY": 17,
        "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING": 4,
        "PRIZE_AWARE_INSUFFICIENT_SUPPORT": 22,
        "PRIZE_AWARE_NULL": 65,
    }
    assert summary["stability_counts"] == {"STABILITY_FAIL": 33, "STABILITY_PASS": 3}
    assert summary["group_decision_counts"] == {
        "DESCRIPTIVE_ONLY": 16, "GO_CANDIDATE_RESEARCH_ONLY": 3,
        "INSUFFICIENT_SUPPORT": 14, "NULL": 3,
    }


def test_output_canonical_payload_digest(committed_output):
    assert evaluator.canonical_payload_digest(committed_output) == committed_output["canonical_payload_digest"]


def test_deterministic_regeneration_matches_committed_bytes(tmp_path):
    json_path = tmp_path / "evaluation.json"
    md_path = tmp_path / "evaluation.md"
    evaluator.generate(REPO_ROOT, json_path.relative_to(REPO_ROOT) if json_path.is_relative_to(REPO_ROOT) else json_path,
                       md_path.relative_to(REPO_ROOT) if md_path.is_relative_to(REPO_ROOT) else md_path)
    assert json_path.read_bytes() == (REPO_ROOT / evaluator.OUTPUT_JSON).read_bytes()
    assert md_path.read_bytes() == (REPO_ROOT / evaluator.OUTPUT_MD).read_bytes()


def test_big_lotto_special_hit_is_recomputed_from_actual_special():
    attempt = {"predicted_main_numbers": [1, 2, 7, 8, 9, 10], "predicted_auxiliary": None}
    outcome = {"main_numbers": [1, 2, 3, 4, 5, 6], "auxiliary": 7}
    assert evaluator._score("BIG_LOTTO", attempt, outcome) == {
        "main_hit_count": 2, "special_hit": 1,
        "prize_tier": "BIG_CONSOLATION_PRIZE", "any_prize_aware_win": True,
    }


def test_score_tampering_fails_closed(registry_and_identity):
    source = registry_and_identity[0]
    registry = dict(source)
    registry["attempts"] = list(source["attempts"])
    registry["attempts"][0] = dict(source["attempts"][0])
    registry["attempts"][0]["score"] = dict(source["attempts"][0]["score"])
    registry["attempts"][0]["score"]["any_prize_aware_win"] = True
    with pytest.raises(evaluator.EvaluationError, match="score mismatch"):
        evaluator.evaluate_opportunities(registry)


def test_window_reconciliation_tampering_fails_closed(registry_and_identity):
    source = registry_and_identity[0]
    registry = dict(source)
    registry["window_reconciliation"] = list(source["window_reconciliation"])
    registry["window_reconciliation"][0] = dict(source["window_reconciliation"][0])
    opportunities = evaluator.evaluate_opportunities(registry)
    registry["window_reconciliation"][0]["observed_successes"] += 1
    with pytest.raises(evaluator.EvaluationError, match="window reconciliation mismatch"):
        evaluator.evaluate_windows(registry, opportunities)


def test_source_has_no_database_network_or_process_imports():
    source = (REPO_ROOT / "analysis/p545b_r2_full_per_draw_evaluator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint({"sqlite3", "socket", "subprocess", "requests", "urllib", "httpx"})


def test_markdown_states_no_claim_and_no_database(committed_output):
    markdown = (REPO_ROOT / evaluator.OUTPUT_MD).read_text(encoding="utf-8")
    assert "This is not a betting recommendation" in markdown
    assert "SQLite opened: **NO**" in markdown
    assert committed_output["canonical_payload_digest"] in markdown


def test_authorized_changed_file_set_is_exact():
    expected = {
        "analysis/p545b_r2_full_per_draw_evaluator.py",
        "tests/test_p545b_r2_full_per_draw_evaluator.py",
        "outputs/research/p545b_r2_full_per_draw_evaluator_20260711.json",
        "outputs/research/p545b_r2_full_per_draw_evaluator_20260711.md",
    }
    assert all((REPO_ROOT / path).is_file() for path in expected)
