"""
tests/test_p16_p18_policy_loader.py

Unit tests for the P18 selected policy loader and validator (P16.6).
"""
from __future__ import annotations

import json
import math
import os
import tempfile

import pytest

from wbc_backend.recommendation.p16_p18_policy_loader import (
    P18SelectedPolicy,
    ValidationResult,
    load_p18_selected_policy,
    validate_p18_selected_policy,
    P18_GATE_REPAIRED,
    VALIDATION_ERROR_CODE,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _valid_policy_dict() -> dict:
    return {
        "selected_policy_id": "e0p0500_s0p0025_k0p10_o2p50",
        "edge_threshold": 0.05,
        "max_stake_cap": 0.0025,
        "kelly_fraction": 0.10,
        "odds_decimal_max": 2.50,
        "n_bets": 324,
        "max_drawdown_pct": 1.847,
        "sharpe_ratio": 0.1016,
        "gate_decision": "P18_STRATEGY_POLICY_RISK_REPAIRED",
        "paper_only": True,
        "production_ready": False,
        "roi_mean": 10.78,
        "roi_ci_low_95": -0.988,
        "roi_ci_high_95": 20.78,
        "hit_rate": 0.5278,
    }


def _write_policy_json(tmp_dir: str, data: dict) -> str:
    path = os.path.join(tmp_dir, "selected_strategy_policy.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _valid_policy() -> P18SelectedPolicy:
    d = _valid_policy_dict()
    return P18SelectedPolicy(
        selected_policy_id=d["selected_policy_id"],
        edge_threshold=d["edge_threshold"],
        max_stake_cap=d["max_stake_cap"],
        kelly_fraction=d["kelly_fraction"],
        odds_decimal_max=d["odds_decimal_max"],
        n_bets=d["n_bets"],
        max_drawdown_pct=d["max_drawdown_pct"],
        sharpe_ratio=d["sharpe_ratio"],
        gate_decision=d["gate_decision"],
        paper_only=True,
        production_ready=False,
        roi_mean=d["roi_mean"],
        roi_ci_low_95=d["roi_ci_low_95"],
        roi_ci_high_95=d["roi_ci_high_95"],
        hit_rate=d["hit_rate"],
    )


# ── Loader tests ──────────────────────────────────────────────────────────────


def test_load_valid_policy():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, _valid_policy_dict())
        policy = load_p18_selected_policy(path)
    assert policy.selected_policy_id == "e0p0500_s0p0025_k0p10_o2p50"
    assert policy.edge_threshold == pytest.approx(0.05)
    assert policy.max_stake_cap == pytest.approx(0.0025)
    assert policy.kelly_fraction == pytest.approx(0.10)
    assert policy.odds_decimal_max == pytest.approx(2.50)
    assert policy.n_bets == 324
    assert policy.paper_only is True
    assert policy.production_ready is False


def test_load_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_p18_selected_policy("/nonexistent/path/policy.json")


def test_load_missing_required_field():
    data = _valid_policy_dict()
    del data["edge_threshold"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        with pytest.raises(ValueError, match="edge_threshold"):
            load_p18_selected_policy(path)


def test_load_missing_gate_decision():
    data = _valid_policy_dict()
    del data["gate_decision"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        with pytest.raises(ValueError, match="gate_decision"):
            load_p18_selected_policy(path)


def test_load_non_finite_field():
    data = _valid_policy_dict()
    data["edge_threshold"] = float("inf")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        with pytest.raises(ValueError, match="finite"):
            load_p18_selected_policy(path)


def test_load_optional_fields_default_to_zero():
    """If optional roi fields are absent, they default to 0.0."""
    data = _valid_policy_dict()
    del data["roi_mean"]
    del data["roi_ci_low_95"]
    del data["roi_ci_high_95"]
    del data["hit_rate"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        policy = load_p18_selected_policy(path)
    assert policy.roi_mean == 0.0
    assert policy.roi_ci_low_95 == 0.0
    assert policy.roi_ci_high_95 == 0.0
    assert policy.hit_rate == 0.0


def test_load_paper_only_defaults_to_true():
    """If paper_only absent from JSON, defaults to True."""
    data = _valid_policy_dict()
    del data["paper_only"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        policy = load_p18_selected_policy(path)
    assert policy.paper_only is True


def test_load_production_ready_defaults_to_false():
    """If production_ready absent from JSON, defaults to False."""
    data = _valid_policy_dict()
    del data["production_ready"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_policy_json(tmp, data)
        policy = load_p18_selected_policy(path)
    assert policy.production_ready is False


# ── Validator tests ───────────────────────────────────────────────────────────


def test_validate_valid_policy():
    result = validate_p18_selected_policy(_valid_policy())
    assert result.valid is True
    assert result.error_code is None
    assert result.error_message is None


def test_validate_wrong_gate_decision():
    p = _valid_policy()
    from dataclasses import replace
    p_bad = P18SelectedPolicy(
        **{**p.__dict__, "gate_decision": "WRONG_GATE"}
    )
    result = validate_p18_selected_policy(p_bad)
    assert result.valid is False
    assert result.error_code == VALIDATION_ERROR_CODE
    assert "gate_decision" in result.error_message


def test_validate_drawdown_too_high():
    d = _valid_policy_dict()
    d["max_drawdown_pct"] = 25.01
    p = P18SelectedPolicy(**{k: v for k, v in {
        "selected_policy_id": d["selected_policy_id"],
        "edge_threshold": d["edge_threshold"],
        "max_stake_cap": d["max_stake_cap"],
        "kelly_fraction": d["kelly_fraction"],
        "odds_decimal_max": d["odds_decimal_max"],
        "n_bets": d["n_bets"],
        "max_drawdown_pct": 25.01,
        "sharpe_ratio": d["sharpe_ratio"],
        "gate_decision": d["gate_decision"],
        "paper_only": True,
        "production_ready": False,
        "roi_mean": 0.0, "roi_ci_low_95": 0.0, "roi_ci_high_95": 0.0,
        "hit_rate": 0.0,
    }.items()})
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "max_drawdown_pct" in result.error_message


def test_validate_drawdown_exactly_at_limit():
    """max_drawdown_pct == 25.0 should pass."""
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=100,
        max_drawdown_pct=25.0,
        sharpe_ratio=0.0,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is True


def test_validate_sharpe_below_floor():
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=100,
        max_drawdown_pct=1.85,
        sharpe_ratio=-0.01,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "sharpe" in result.error_message.lower()


def test_validate_n_bets_below_floor():
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=49,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "n_bets" in result.error_message


def test_validate_production_ready_true_fails():
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=100,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=True,   # must be False
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "production_ready" in result.error_message


def test_validate_paper_only_false_fails():
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=100,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=False,   # must be True
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "paper_only" in result.error_message


def test_validate_zero_max_stake_cap_fails():
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0,   # must be > 0
        kelly_fraction=0.10,
        odds_decimal_max=2.50,
        n_bets=100,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "max_stake_cap" in result.error_message


def test_validate_odds_decimal_max_at_one_fails():
    """odds_decimal_max must be > 1.0."""
    p = P18SelectedPolicy(
        selected_policy_id="x",
        edge_threshold=0.05,
        max_stake_cap=0.0025,
        kelly_fraction=0.10,
        odds_decimal_max=1.0,
        n_bets=100,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        gate_decision=P18_GATE_REPAIRED,
        paper_only=True,
        production_ready=False,
        roi_mean=0.0, roi_ci_low_95=0.0, roi_ci_high_95=0.0, hit_rate=0.0,
    )
    result = validate_p18_selected_policy(p)
    assert result.valid is False
    assert "odds_decimal_max" in result.error_message
