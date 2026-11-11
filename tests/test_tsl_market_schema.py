"""Tests for TSL Market Taxonomy + Schema Pack."""
from __future__ import annotations

import json

import pytest

from wbc_backend.markets.tsl_market_schema import (
    TSLMarketType,
    MarketContract,
    get_market_contract,
    list_implemented_markets,
    describe_market_for_audit,
)


def test_all_markets_have_contract():
    """Every TSLMarketType member must have a registered contract."""
    for market_type in TSLMarketType:
        contract = get_market_contract(market_type)
        assert isinstance(contract, MarketContract), f"No valid contract for {market_type}"


def test_only_moneyline_paper_implemented_v1():
    """In v1 exactly one market must be paper-implemented: MONEYLINE_HOME_AWAY."""
    implemented = list_implemented_markets()
    assert implemented == [TSLMarketType.MONEYLINE_HOME_AWAY], (
        f"Expected [MONEYLINE_HOME_AWAY], got {implemented}"
    )


def test_market_contract_is_frozen():
    """MarketContract instances must be frozen (immutable)."""
    contract = get_market_contract(TSLMarketType.MONEYLINE_HOME_AWAY)
    with pytest.raises((AttributeError, TypeError)):
        contract.paper_only = False  # type: ignore[misc]


def test_paper_only_true_always():
    """paper_only must be True for every market contract."""
    for market_type in TSLMarketType:
        contract = get_market_contract(market_type)
        assert contract.paper_only is True, f"paper_only=False for {market_type}"


def test_production_ready_false_always():
    """production_ready must be False for every market contract."""
    for market_type in TSLMarketType:
        contract = get_market_contract(market_type)
        assert contract.production_ready is False, f"production_ready=True for {market_type}"


def test_describe_market_returns_serializable_dict():
    """describe_market_for_audit must return a JSON-serializable dict."""
    for market_type in TSLMarketType:
        description = describe_market_for_audit(market_type)
        assert isinstance(description, dict)
        # Must be JSON-serializable without raising
        json.dumps(description)


def test_run_line_label_fields_include_handicap_value():
    """RUN_LINE_HANDICAP contract must reference handicap_value in label_fields."""
    contract = get_market_contract(TSLMarketType.RUN_LINE_HANDICAP)
    assert "handicap_value" in contract.label_fields, (
        f"handicap_value not in label_fields: {contract.label_fields}"
    )


def test_totals_label_fields_include_line_value():
    """TOTALS_OVER_UNDER contract must reference line_value in label_fields."""
    contract = get_market_contract(TSLMarketType.TOTALS_OVER_UNDER)
    assert "line_value" in contract.label_fields, (
        f"line_value not in label_fields: {contract.label_fields}"
    )


def test_all_eight_markets_defined():
    """All 8 expected market types must be in the enum."""
    expected = {
        "moneyline_home_away",
        "run_line_handicap",
        "totals_over_under",
        "first_five_innings_moneyline",
        "first_five_innings_totals",
        "odd_even_total_runs",
        "team_total_home",
        "team_total_away",
    }
    actual = {m.value for m in TSLMarketType}
    assert actual == expected


def test_moneyline_has_no_push():
    """Moneyline does not support push (extra innings count)."""
    contract = get_market_contract(TSLMarketType.MONEYLINE_HOME_AWAY)
    assert contract.supports_push_tie is False


def test_describe_includes_market_type_value():
    """describe_market_for_audit output must include market_type as string value."""
    desc = describe_market_for_audit(TSLMarketType.MONEYLINE_HOME_AWAY)
    assert desc["market_type"] == "moneyline_home_away"
