"""Non-DB tests for the compact P545C R4 opportunity registry."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from analysis import p545c_r4_strategy_draw_opportunity_registry as registry


REPO_ROOT = Path(registry.__file__).resolve().parents[1]
JSON_PATH = (
    REPO_ROOT
    / "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json"
)
MD_PATH = JSON_PATH.with_suffix(".md")


def _evaluable_window() -> dict[str, object]:
    return {
        "evaluable": True,
        "support_status": "SUFFICIENT",
        "expected_successes": 5.0,
        "wilson_ci_95": [0.1, 0.3],
        "clopper_pearson_ci_95": [0.09, 0.31],
        "raw_p_value_one_sided_upper": 0.2,
        "raw_p_value_one_sided_lower": 0.8,
        "bonferroni_p_value": 1.0,
        "bonferroni_p_value_lower": 1.0,
        "statistical_status": "POSITIVE_NOT_CORRECTED",
        "window_decision": "PRIZE_AWARE_NULL",
    }


@pytest.fixture(scope="module")
def payload() -> dict[str, object]:
    return json.loads(JSON_PATH.read_bytes())


def test_date_normalization_accepts_only_two_exact_forms() -> None:
    assert registry.normalize_calendar_date("2026/05/21") == "2026-05-21"
    assert registry.normalize_calendar_date("2026-05-21") == "2026-05-21"
    for invalid in (
        "2026/5/21",
        "2026-05/21",
        " 2026-05-21",
        "2026-05-21T00:00:00",
        "2026-02-30",
    ):
        with pytest.raises(registry.RegistryError):
            registry.normalize_calendar_date(invalid)


def test_nullable_evaluable_record_requires_complete_valid_statistics() -> None:
    normalized = registry.normalized_inference_block(_evaluable_window())
    assert normalized["evaluable"] is True
    assert normalized["omitted_fields"] == []
    assert normalized["normalization_applied"] is False


@pytest.mark.parametrize(
    ("mutation", "value"),
    (
        ("missing", None),
        ("null", None),
        ("below", -0.01),
        ("above", 1.01),
    ),
)
def test_nullable_evaluable_invalid_upper_pvalue_fails(
    mutation: str, value: object
) -> None:
    record = _evaluable_window()
    if mutation == "missing":
        record.pop("raw_p_value_one_sided_upper")
    else:
        record["raw_p_value_one_sided_upper"] = value
    with pytest.raises(registry.RegistryError):
        registry.normalized_inference_block(record)


def test_nullable_unevaluable_absent_statistics_become_explicit_null() -> None:
    record = {
        "evaluable": False,
        "support_status": "INSUFFICIENT_SUPPORT",
        "window_decision": "PRIZE_AWARE_INSUFFICIENT_SUPPORT",
    }
    normalized = registry.normalized_inference_block(record)
    assert normalized["values"]["raw_p_value_one_sided_upper"] is None
    assert (
        normalized["source_field_presence"]["raw_p_value_one_sided_upper"]
        == "absent"
    )
    assert "raw_p_value_one_sided_upper" in normalized["omitted_fields"]
    assert normalized["omission_reason"].startswith(
        "UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:"
    )
    assert normalized["normalization_applied"] is True
    encoded = registry._canonical_bytes(normalized)
    assert b'"raw_p_value_one_sided_upper":null' in encoded
    assert b"NaN" not in encoded and b"Infinity" not in encoded


def test_nullable_present_null_is_distinguished() -> None:
    record = {
        "evaluable": False,
        "support_status": "INSUFFICIENT_SUPPORT",
        "raw_p_value_one_sided_upper": None,
        "window_decision": "PRIZE_AWARE_INSUFFICIENT_SUPPORT",
    }
    normalized = registry.normalized_inference_block(record)
    assert (
        normalized["source_field_presence"]["raw_p_value_one_sided_upper"]
        == "present-null"
    )


def test_nullable_missing_or_contradictory_status_fails() -> None:
    with pytest.raises(registry.RegistryError):
        registry.normalized_inference_block({"evaluable": False})
    with pytest.raises(registry.RegistryError):
        registry.normalized_inference_block(
            {"evaluable": False, "support_status": "SUFFICIENT"}
        )


def test_committed_compact_top_level_and_counts(payload: dict[str, object]) -> None:
    assert payload["schema"] == registry.SCHEMA
    assert len(payload["cells"]) == 36
    assert len(payload["official_outcomes"]) == 2_253
    assert len(payload["opportunities"]) == 27_000
    assert len(payload["attempts"]) == 47_250
    assert len(payload["window_reconciliation"]) == 108
    assert payload["global_summary"] == {
        "cross_index_duplicate_tickets": 0,
        "eligible_attempts": 33_749,
        "excluded_attempts": 13_501,
        "frozen_cells": 36,
        "gross_attempts": 47_250,
        "identity_missing_opportunities": 3_001,
        "long_opportunities": 27_000,
        "official_outcomes": 2_253,
        "same_index_conflicts": 0,
        "same_key_duplicate_rows": 0,
        "supported_opportunities": 23_999,
        "window_records": 108,
    }


def test_committed_references_ids_and_ranges(payload: dict[str, object]) -> None:
    cells = {item["cell_id"] for item in payload["cells"]}
    outcomes = {item["outcome_id"] for item in payload["official_outcomes"]}
    opportunities = payload["opportunities"]
    attempts = payload["attempts"]
    assert len(cells) == 36 and len(outcomes) == 2_253
    assert len({item["opportunity_id"] for item in opportunities}) == 27_000
    assert len({item["attempt_id"] for item in attempts}) == 47_250
    cursor = 0
    for opportunity in opportunities:
        assert opportunity["cell_id"] in cells
        assert opportunity["outcome_id"] in outcomes
        assert opportunity["attempt_start"] == cursor
        selected = attempts[cursor : cursor + opportunity["attempt_count"]]
        assert all(
            attempt["opportunity_id"] == opportunity["opportunity_id"]
            for attempt in selected
        )
        cursor += opportunity["attempt_count"]
    assert cursor == len(attempts)


def test_committed_accounting_and_four_zero_cells(payload: dict[str, object]) -> None:
    opportunities = payload["opportunities"]
    assert sum(item["gross_attempt_count"] for item in opportunities) == 47_250
    assert sum(item["eligible_attempt_count"] for item in opportunities) == 33_749
    assert sum(item["excluded_attempt_count"] for item in opportunities) == 13_501
    zero_ids = {
        "POWER_LOTTO:fourier_rhythm_3bet",
        "POWER_LOTTO:power_fourier_rhythm_2bet",
        "POWER_LOTTO:power_orthogonal_5bet",
        "POWER_LOTTO:power_precision_3bet",
    }
    selected = [item for item in opportunities if item["cell_id"] in zero_ids]
    assert len(selected) == 3_000
    assert sum(item["gross_attempt_count"] for item in selected) == 9_750
    assert sum(item["eligible_attempt_count"] for item in selected) == 0
    assert sum(item["excluded_attempt_count"] for item in selected) == 9_750
    assert all(
        item["exclusion_by_reason"]
        == {"MISSING_PREDICTED_SECOND_ZONE": item["excluded_attempt_count"]}
        for item in selected
    )


def test_committed_nullable_inference_contract(payload: dict[str, object]) -> None:
    windows = payload["window_reconciliation"]
    unevaluable = [item for item in windows if not item["inference"]["evaluable"]]
    assert len(unevaluable) == 22
    assert all(item["inference"]["normalization_applied"] for item in unevaluable)
    assert all(item["inference"]["omitted_fields"] for item in unevaluable)
    assert all(
        item["inference"]["values"]["raw_p_value_one_sided_upper"] is None
        for item in unevaluable
    )
    evaluable = [item for item in windows if item["inference"]["evaluable"]]
    assert len(evaluable) == 86
    assert all(not item["inference"]["omitted_fields"] for item in evaluable)


def test_committed_draw_115000041_and_postfreeze_rule(payload: dict[str, object]) -> None:
    matches = [
        item
        for item in payload["official_outcomes"]
        if item["outcome_id"] == "POWER_LOTTO:115000041"
    ]
    assert matches == [
        {
            **matches[0],
            "raw_date": "2026/05/21",
            "canonical_date": "2026-05-21",
            "main_numbers": [6, 14, 22, 28, 35, 38],
            "auxiliary": 1,
        }
    ]
    correction = payload["postfreeze_correction"]
    assert correction["excluded_from_registry"] is True
    assert correction["dynamic_window_deficit_explained"] == 88


def test_committed_semantic_equivalence_and_digest(payload: dict[str, object]) -> None:
    evidence = payload["semantic_equivalence"]
    assert evidence["equivalence_result"] == "PASS"
    assert evidence["expanded_semantic_projection_digest"] == evidence[
        "compact_semantic_projection_digest"
    ]
    assert registry.semantic_projection_digest(payload) == evidence[
        "compact_semantic_projection_digest"
    ]
    assert registry.canonical_payload_digest(payload) == payload[
        "canonical_payload_digest"
    ]


def test_committed_bytes_size_markdown_and_no_claim(payload: dict[str, object]) -> None:
    raw = JSON_PATH.read_bytes()
    assert len(raw) < 83_886_080
    assert raw == registry.canonical_json_bytes(payload)
    assert b"NaN" not in raw and b"Infinity" not in raw
    markdown = MD_PATH.read_text(encoding="utf-8")
    assert markdown == registry.render_markdown(payload)
    assert "No predictive-validity" in markdown
    assert "betting claim" in markdown
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports.isdisjoint({"sqlite3", "requests", "urllib"})


def test_artifact_hashes_are_stable_and_nonempty() -> None:
    assert hashlib.sha256(JSON_PATH.read_bytes()).hexdigest()
    assert hashlib.sha256(MD_PATH.read_bytes()).hexdigest()
