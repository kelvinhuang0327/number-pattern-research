"""
tests/test_p16_recommendation_input_adapter.py

Unit tests for wbc_backend/recommendation/p16_recommendation_input_adapter.py

Test cases:
- JOINED rows are eligible
- non-JOINED rows (MISSING/INVALID) preserved but marked ineligible
- invalid probability blocked
- invalid odds blocked
- paper_only always True
- production_ready always False
- source_model and source_bss_oof injected
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p16_recommendation_input_adapter import (
    P16InputRow,
    SOURCE_MODEL,
    SOURCE_BSS_OOF,
    input_rows_to_dataframe,
    load_p16_input_rows,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_csv_file(rows: list[dict]) -> str:
    df = pd.DataFrame(rows)
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    df.to_csv(tmp.name, index=False)
    tmp.close()
    return tmp.name


def _base_row(
    game_id: str = "2025-05-08_KC_CWS",
    p_oof: float = 0.62,
    p_market: float = 0.55,
    odds_decimal_home: float = 1.82,
    odds_decimal_away: float = 2.10,
    odds_join_status: str = "JOINED",
    y_true: int = 1,
    game_date: str = "2025-05-08",
) -> dict:
    edge = p_oof - p_market
    return {
        "game_id": game_id,
        "game_date": game_date,
        "y_true": y_true,
        "p_oof": p_oof,
        "p_market": p_market,
        "edge": edge,
        "odds_decimal_home": odds_decimal_home,
        "odds_decimal_away": odds_decimal_away,
        "odds_join_status": odds_join_status,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_joined_row_is_eligible():
    path = _make_csv_file([_base_row(odds_join_status="JOINED")])
    rows = load_p16_input_rows(path)
    assert len(rows) == 1
    assert rows[0].eligible is True
    assert rows[0].ineligibility_reason is None


def test_missing_join_status_blocked():
    path = _make_csv_file([_base_row(odds_join_status="MISSING")])
    rows = load_p16_input_rows(path)
    assert rows[0].eligible is False
    assert rows[0].ineligibility_reason is not None
    assert "MISSING" in rows[0].ineligibility_reason or "JOINED" in rows[0].ineligibility_reason


def test_invalid_join_status_blocked():
    path = _make_csv_file([_base_row(odds_join_status="INVALID_ODDS")])
    rows = load_p16_input_rows(path)
    assert rows[0].eligible is False


def test_invalid_probability_blocked():
    r = _base_row()
    r["p_oof"] = 1.5  # invalid
    path = _make_csv_file([r])
    rows = load_p16_input_rows(path)
    assert rows[0].eligible is False
    assert "p_model" in (rows[0].ineligibility_reason or "")


def test_zero_probability_blocked():
    r = _base_row()
    r["p_oof"] = 0.0
    path = _make_csv_file([r])
    rows = load_p16_input_rows(path)
    assert rows[0].eligible is False


def test_invalid_odds_blocked():
    r = _base_row()
    r["odds_decimal_home"] = 0.5  # odds < 1.0 are invalid
    r["odds_decimal_away"] = 0.5
    path = _make_csv_file([r])
    rows = load_p16_input_rows(path)
    assert rows[0].eligible is False
    assert "odds_decimal" in (rows[0].ineligibility_reason or "")


def test_paper_only_always_true():
    path = _make_csv_file([_base_row()])
    rows = load_p16_input_rows(path)
    assert all(r.paper_only is True for r in rows)


def test_production_ready_always_false():
    path = _make_csv_file([_base_row()])
    rows = load_p16_input_rows(path)
    assert all(r.production_ready is False for r in rows)


def test_source_model_injected():
    path = _make_csv_file([_base_row()])
    rows = load_p16_input_rows(path)
    assert rows[0].source_model == SOURCE_MODEL


def test_source_bss_oof_injected():
    path = _make_csv_file([_base_row()])
    rows = load_p16_input_rows(path, source_bss_oof=0.012)
    assert abs(rows[0].source_bss_oof - 0.012) < 1e-9


def test_multiple_rows_mixed_eligibility():
    rows_data = [
        _base_row(game_id="g1", odds_join_status="JOINED"),
        _base_row(game_id="g2", odds_join_status="MISSING"),
        _base_row(game_id="g3", odds_join_status="JOINED"),
    ]
    path = _make_csv_file(rows_data)
    rows = load_p16_input_rows(path)
    assert len(rows) == 3
    assert rows[0].eligible is True
    assert rows[1].eligible is False
    assert rows[2].eligible is True


def test_input_rows_to_dataframe_columns():
    path = _make_csv_file([_base_row()])
    rows = load_p16_input_rows(path)
    df = input_rows_to_dataframe(rows)
    assert "game_id" in df.columns
    assert "p_model" in df.columns
    assert "paper_only" in df.columns
    assert "production_ready" in df.columns
    assert "eligible" in df.columns
    assert df["paper_only"].all()
    assert not df["production_ready"].any()
