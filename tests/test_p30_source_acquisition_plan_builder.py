"""
tests/test_p30_source_acquisition_plan_builder.py

Unit tests for P30 source acquisition plan builder.
"""
from __future__ import annotations

import pytest
from typing import Dict, Any, List

from wbc_backend.recommendation.p30_source_acquisition_plan_builder import (
    ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT,
    build_gate_result,
    build_source_acquisition_plan,
    determine_p30_gate,
    estimate_active_entry_gain,
    rank_source_acquisition_options,
    validate_provenance_and_license,
)
from wbc_backend.recommendation.p30_required_artifact_spec_generator import (
    build_required_artifact_specs,
    identify_schema_gaps,
    map_existing_sources_to_specs,
)
from wbc_backend.recommendation.p30_source_acquisition_contract import (
    P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
    P30_BLOCKED_NO_VERIFIABLE_SOURCE,
    P30_SOURCE_ACQUISITION_PLAN_READY,
    SOURCE_PLAN_PARTIAL,
    SOURCE_PLAN_READY,
    SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    path: str = "data/test.csv",
    season: str = "2024",
    rows: int = 2430,
    provenance: str = "KNOWN_HISTORICAL",
    license_risk: str = "LOW",
    schema_coverage: str = "PARTIAL",
    source_status: str = SOURCE_PLAN_PARTIAL,
) -> Dict[str, Any]:
    return {
        "path": path,
        "source_type": "csv",
        "target_season": season,
        "estimated_rows": rows,
        "estimated_games": rows,
        "provenance_status": provenance,
        "license_risk": license_risk,
        "schema_coverage": schema_coverage,
        "source_status": source_status,
        "has_game_id": False,
        "has_game_date": True,
        "has_y_true": False,
        "has_home_away_teams": True,
        "has_p_model": False,
        "has_p_market": False,
        "has_odds_decimal": True,
        "paper_only": True,
        "production_ready": False,
    }


# ---------------------------------------------------------------------------
# rank_source_acquisition_options
# ---------------------------------------------------------------------------


def test_rank_puts_verifiable_first():
    unknown = _make_candidate(path="data/unk.csv", provenance="UNKNOWN", rows=5000)
    known = _make_candidate(path="data/known.csv", provenance="KNOWN_HISTORICAL", rows=1000)
    ranked = rank_source_acquisition_options([unknown, known])
    assert ranked[0]["provenance_status"] == "KNOWN_HISTORICAL"


def test_rank_puts_full_schema_before_minimal():
    minimal = _make_candidate(
        path="data/min.csv",
        provenance="KNOWN_HISTORICAL",
        schema_coverage="MINIMAL",
        rows=5000,
    )
    full = _make_candidate(
        path="data/full.csv",
        provenance="KNOWN_HISTORICAL",
        schema_coverage="FULL",
        source_status=SOURCE_PLAN_READY,
        rows=1000,
    )
    ranked = rank_source_acquisition_options([minimal, full])
    assert ranked[0]["schema_coverage"] == "FULL"


def test_rank_same_schema_higher_rows_first():
    small = _make_candidate(path="data/small.csv", provenance="KNOWN_HISTORICAL", rows=100)
    large = _make_candidate(path="data/large.csv", provenance="KNOWN_HISTORICAL", rows=5000)
    ranked = rank_source_acquisition_options([small, large])
    assert ranked[0]["estimated_rows"] == 5000


def test_rank_empty_list():
    ranked = rank_source_acquisition_options([])
    assert ranked == []


# ---------------------------------------------------------------------------
# validate_provenance_and_license
# ---------------------------------------------------------------------------


def test_validate_unknown_provenance_is_unsafe():
    c = _make_candidate(provenance="UNKNOWN", license_risk="UNKNOWN")
    result = validate_provenance_and_license(c)
    assert result["safe"] is False
    assert result["risk_level"] == "HIGH"


def test_validate_known_low_risk_is_safe():
    c = _make_candidate(provenance="KNOWN_HISTORICAL", license_risk="LOW")
    result = validate_provenance_and_license(c)
    assert result["safe"] is True


def test_validate_high_license_risk_is_unsafe():
    c = _make_candidate(provenance="KNOWN_HISTORICAL", license_risk="HIGH")
    result = validate_provenance_and_license(c)
    assert result["safe"] is False


def test_validate_returns_dict_with_required_keys():
    c = _make_candidate()
    result = validate_provenance_and_license(c)
    assert "safe" in result
    assert "risk_level" in result
    assert "notes" in result


# ---------------------------------------------------------------------------
# estimate_active_entry_gain
# ---------------------------------------------------------------------------


def test_estimate_gain_uses_default_conversion_rate():
    c = _make_candidate(rows=2430)
    gain = estimate_active_entry_gain(c)
    expected = int(2430 * ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT)
    assert gain == expected


def test_estimate_gain_with_zero_rows():
    c = _make_candidate(rows=0)
    gain = estimate_active_entry_gain(c)
    assert gain == 0


def test_estimate_gain_custom_rate():
    c = _make_candidate(rows=1000)
    gain = estimate_active_entry_gain(c, conversion_rate=0.5)
    assert gain == 500


def test_estimate_gain_is_integer():
    c = _make_candidate(rows=3333)
    gain = estimate_active_entry_gain(c)
    assert isinstance(gain, int)


# ---------------------------------------------------------------------------
# determine_p30_gate
# ---------------------------------------------------------------------------


def _specs_for_empty():
    return build_required_artifact_specs("2024")


def test_gate_ready_when_verifiable_partial_source():
    inventory = [_make_candidate(provenance="KNOWN_HISTORICAL", source_status=SOURCE_PLAN_PARTIAL)]
    specs = _specs_for_empty()
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    gate = determine_p30_gate(inventory, specs, gaps)
    assert gate == P30_SOURCE_ACQUISITION_PLAN_READY


def test_gate_ready_when_verifiable_ready_source():
    inventory = [_make_candidate(provenance="KNOWN_HISTORICAL", source_status=SOURCE_PLAN_READY, schema_coverage="FULL")]
    specs = _specs_for_empty()
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    gate = determine_p30_gate(inventory, specs, gaps)
    assert gate == P30_SOURCE_ACQUISITION_PLAN_READY


def test_gate_blocked_no_verifiable_source_when_empty():
    gate = determine_p30_gate([], _specs_for_empty(), {})
    assert gate == P30_BLOCKED_NO_VERIFIABLE_SOURCE


def test_gate_blocked_provenance_when_only_unknown():
    unknown = _make_candidate(provenance="UNKNOWN", source_status=SOURCE_PLAN_PARTIAL)
    specs = _specs_for_empty()
    gaps = identify_schema_gaps(map_existing_sources_to_specs([unknown], specs))
    gate = determine_p30_gate([unknown], specs, gaps)
    assert gate == P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE


def test_gate_blocked_missing_specs_when_no_specs():
    gate = determine_p30_gate([], [], {})
    from wbc_backend.recommendation.p30_source_acquisition_contract import (
        P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
    )
    assert gate == P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC


# ---------------------------------------------------------------------------
# build_source_acquisition_plan
# ---------------------------------------------------------------------------


def test_plan_paper_only_enforced():
    inventory = [_make_candidate()]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    assert plan.paper_only is True
    assert plan.production_ready is False


def test_plan_target_season():
    inventory = [_make_candidate()]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    assert plan.target_season == "2024"


def test_plan_has_recommended_action():
    inventory = [_make_candidate()]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    assert len(plan.recommended_next_action) > 0


def test_plan_estimated_gain_non_negative():
    inventory = [_make_candidate(rows=2430)]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    assert plan.estimated_sample_gain >= 0


def test_plan_empty_inventory_blocked():
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs([], specs))
    plan = build_source_acquisition_plan([], specs, gaps, "2024")
    assert plan.p30_gate == P30_BLOCKED_NO_VERIFIABLE_SOURCE


# ---------------------------------------------------------------------------
# build_gate_result
# ---------------------------------------------------------------------------


def test_gate_result_from_plan():
    inventory = [_make_candidate(provenance="KNOWN_HISTORICAL", source_status=SOURCE_PLAN_PARTIAL)]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    result = build_gate_result(plan)
    assert result.p30_gate == plan.p30_gate
    assert result.paper_only is True
    assert result.production_ready is False


def test_gate_result_blocker_empty_when_ready():
    inventory = [_make_candidate(provenance="KNOWN_HISTORICAL", source_status=SOURCE_PLAN_READY, schema_coverage="FULL")]
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs(inventory, specs))
    plan = build_source_acquisition_plan(inventory, specs, gaps, "2024")
    result = build_gate_result(plan)
    if result.p30_gate == P30_SOURCE_ACQUISITION_PLAN_READY:
        assert result.blocker_reason == ""


def test_gate_result_blocker_populated_when_blocked():
    specs = build_required_artifact_specs("2024")
    gaps = identify_schema_gaps(map_existing_sources_to_specs([], specs))
    plan = build_source_acquisition_plan([], specs, gaps, "2024")
    result = build_gate_result(plan)
    assert result.blocker_reason == P30_BLOCKED_NO_VERIFIABLE_SOURCE
