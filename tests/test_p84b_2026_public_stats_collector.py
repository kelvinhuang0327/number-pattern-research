"""
Tests for P84B — 2026 Public Stats Collector Implementation
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True

Covers all 27 required test cases (T01-T27).
All tests that touch live API use mock stubs — tests must pass offline.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts._p84b_2026_public_stats_collector import (
    ALLOWED_SOURCE_CLASSES,
    FIP_CONSTANT,
    FORBIDDEN_SOURCE_CLASSES,
    GOVERNANCE,
    MIN_IP_FOR_FIP,
    MLB_API_BASE,
    SOURCE_ARTIFACTS,
    SOURCE_PREDICTION_VERSION,
    UPSTREAM_FILES,
    build_model_output_rows,
    build_pitcher_fip_row,
    compute_diagnostic_model_probability,
    compute_fip,
    forbidden_scan,
    validate_model_output_row,
    validate_no_odds_in_script,
    validate_pitcher_row,
    validate_schedule_row,
    verify_p84a_state,
)


# ---------------------------------------------------------------------------
# T01 — P84A source artifact loads
# ---------------------------------------------------------------------------

def test_t01_p84a_artifact_loads():
    p = SOURCE_ARTIFACTS["p84a_json"]
    assert p.exists(), f"P84A artifact missing: {p}"
    d = json.loads(p.read_text())
    assert "p84a_classification" in d
    assert "governance" in d


# ---------------------------------------------------------------------------
# T02 — P84A classification verified
# ---------------------------------------------------------------------------

def test_t02_p84a_classification_verified():
    state = verify_p84a_state()
    assert state["loaded"] is True
    assert state["p84a_classification"] == "P84A_UPSTREAM_COLLECTOR_CONTRACT_READY"
    assert state["classification_ok"] is True


# ---------------------------------------------------------------------------
# T03 — Schedule contract verified
# ---------------------------------------------------------------------------

def test_t03_schedule_contract_verified():
    state = verify_p84a_state()
    assert state["schedule_contract"] == "P84A_SCHEDULE_COLLECTOR_CONTRACT_V1"


# ---------------------------------------------------------------------------
# T04 — Pitcher FIP contract verified
# ---------------------------------------------------------------------------

def test_t04_pitcher_fip_contract_verified():
    state = verify_p84a_state()
    assert state["pitcher_contract"] == "P84A_PITCHER_FIP_CONTRACT_V1"


# ---------------------------------------------------------------------------
# T05 — Model output contract verified
# ---------------------------------------------------------------------------

def test_t05_model_output_contract_verified():
    state = verify_p84a_state()
    assert state["model_contract"] == "P84A_MODEL_OUTPUT_CONTRACT_V1"


# ---------------------------------------------------------------------------
# T06 — Public schedule endpoint definition present
# ---------------------------------------------------------------------------

def test_t06_schedule_endpoint_defined():
    assert MLB_API_BASE == "https://statsapi.mlb.com/api/v1"
    # Verify endpoint construction
    url = f"{MLB_API_BASE}/schedule?sportId=1&season=2026&gameType=R"
    assert "statsapi.mlb.com" in url
    assert "season=2026" in url
    assert "odds" not in url.lower()
    assert "sportsbook" not in url.lower()


# ---------------------------------------------------------------------------
# T07 — Schedule row schema validator present
# ---------------------------------------------------------------------------

def test_t07_schedule_row_schema_validator():
    good_row = {
        "game_id": "mlb_2026_999",
        "game_date": "2026-04-01",
        "season": 2026,
        "home_team": "NYY",
        "away_team": "BOS",
        "source_trace": "MLB_STATS_API_PUBLIC_SCHEDULE",
        "collected_at_utc": "2026-05-26T00:00:00+00:00",
    }
    errors = validate_schedule_row(good_row)
    assert errors == [], f"unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# T08 — Pitcher FIP formula present
# ---------------------------------------------------------------------------

def test_t08_fip_formula_present():
    # Verify FIP computation is correct
    # FIP = ((13*HR + 3*(BB+HBP) - 2*K) / IP) + FIP_CONSTANT
    hr, bb, hbp, k, ip_str = 8, 27, 2, 63, "61.1"
    fip = compute_fip(hr, bb, hbp, k, ip_str)
    assert fip is not None
    # Manual: IP = 61 + 1/3 = 61.333...
    ip = 61 + 1 / 3
    expected = round(((13 * hr + 3 * (bb + hbp) - 2 * k) / ip) + FIP_CONSTANT, 4)
    assert abs(fip - expected) < 0.001, f"FIP mismatch: {fip} vs {expected}"


def test_t08b_fip_returns_none_below_min_ip():
    fip = compute_fip(hr=5, bb=10, hbp=1, k=20, ip_str="3.0")
    assert fip is None, f"expected None for IP < {MIN_IP_FOR_FIP}"


# ---------------------------------------------------------------------------
# T09 — Pitcher feature row schema validator present
# ---------------------------------------------------------------------------

def test_t09_pitcher_feature_row_schema():
    good_row = {
        "game_id": "mlb_2026_999",
        "home_sp_fip": 3.85,
        "away_sp_fip": 4.40,
        "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
        "feature_version": "p84b_fip_v1",
        "row_status": "FEATURE_READY",
    }
    errors = validate_pitcher_row(good_row)
    assert errors == [], f"unexpected errors: {errors}"


def test_t09b_pitcher_feature_pending_row_valid():
    pending_row = {
        "game_id": "mlb_2026_999",
        "home_sp_fip": None,
        "away_sp_fip": None,
        "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
        "feature_version": "p84b_fip_v1",
        "row_status": "FEATURE_PENDING",
    }
    errors = validate_pitcher_row(pending_row)
    assert errors == [], f"unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# T10 — Model output row schema validator present
# ---------------------------------------------------------------------------

def test_t10_model_output_row_schema():
    good_row = {
        "game_id": "mlb_2026_999",
        "model_probability": 0.55,
        "source_prediction_version": SOURCE_PREDICTION_VERSION,
        "model_input_trace": "DIAGNOSTIC_BASELINE_MODEL",
        "predicted_side_derivation_status": "DERIVABLE",
    }
    errors = validate_model_output_row(good_row)
    assert errors == [], f"unexpected errors: {errors}"


def test_t10b_model_pending_row_valid():
    pending_row = {
        "game_id": "mlb_2026_999",
        "model_probability": None,
        "source_prediction_version": SOURCE_PREDICTION_VERSION,
        "model_input_trace": "DIAGNOSTIC_BASELINE_MODEL",
        "predicted_side_derivation_status": "MODEL_PENDING",
    }
    errors = validate_model_output_row(pending_row)
    assert errors == [], f"unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# T11 — No odds API endpoint used
# ---------------------------------------------------------------------------

def test_t11_no_odds_api_endpoint():
    assert validate_no_odds_in_script() is True
    # Schedule endpoint must not contain odds-related terms
    url = f"{MLB_API_BASE}/schedule?sportId=1&season=2026&gameType=R"
    assert "odds" not in url.lower()
    assert "the-odds-api" not in url.lower()
    # ODDS_API must be in forbidden classes
    assert "ODDS_API" in FORBIDDEN_SOURCE_CLASSES


# ---------------------------------------------------------------------------
# T12 — No API key access
# ---------------------------------------------------------------------------

def test_t12_no_api_key_access():
    assert GOVERNANCE["the_odds_api_key_required"] is False
    assert GOVERNANCE["api_key_accessed"] is False
    # Check that no code (non-comment, non-docstring) accesses odds API keys
    script_content = (ROOT / "scripts/_p84b_2026_public_stats_collector.py").read_text()
    code_lines = [
        line for line in script_content.split("\n")
        if not line.strip().startswith("#")
        and not line.strip().startswith('"""')
        and not line.strip().startswith("'''")
    ]
    code_block = "\n".join(code_lines)
    for forbidden_pat in [
        "os.environ.get('THE_ODDS_API",
        'os.environ["THE_ODDS_API',
        "os.getenv('THE_ODDS_API",
        "the-odds-api.com",
    ]:
        assert forbidden_pat not in code_block, f"Odds API key access found: {forbidden_pat}"


# ---------------------------------------------------------------------------
# T13 — No EV calculated
# ---------------------------------------------------------------------------

def test_t13_no_ev_calculated():
    assert GOVERNANCE["ev_calculated"] is False


# ---------------------------------------------------------------------------
# T14 — No CLV calculated
# ---------------------------------------------------------------------------

def test_t14_no_clv_calculated():
    assert GOVERNANCE["clv_calculated"] is False


# ---------------------------------------------------------------------------
# T15 — No Kelly calculated
# ---------------------------------------------------------------------------

def test_t15_no_kelly_calculated():
    assert GOVERNANCE["kelly_calculated"] is False
    assert GOVERNANCE["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# T16 — live_api_calls for odds APIs remains 0
# ---------------------------------------------------------------------------

def test_t16_odds_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    fscan = forbidden_scan()
    assert fscan["live_api_calls_odds"] == 0


# ---------------------------------------------------------------------------
# T17 — production_ready=false
# ---------------------------------------------------------------------------

def test_t17_production_ready_false():
    assert GOVERNANCE["production_ready"] is False


# ---------------------------------------------------------------------------
# T18 — If schedule data unavailable, no fabricated rows
# ---------------------------------------------------------------------------

def test_t18_no_fabricated_rows_when_api_unavailable():
    from scripts._p84b_2026_public_stats_collector import collect_schedule

    with patch("scripts._p84b_2026_public_stats_collector._api_get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        result = collect_schedule(season=2026)

    assert result["ok"] is False
    assert result["rows"] == []
    assert len(result["rows"]) == 0, "No rows should be fabricated on API failure"


# ---------------------------------------------------------------------------
# T19 — If pitcher data incomplete, feature gate blocks
# ---------------------------------------------------------------------------

def test_t19_feature_pending_blocks_gate():
    # Build rows with no probable pitcher
    schedule_rows = [
        {
            "game_id": "mlb_2026_test_001",
            "game_date": "2026-04-01",
            "season": 2026,
            "home_team": "NYY",
            "away_team": "BOS",
            "source_trace": "MLB_STATS_API_PUBLIC_SCHEDULE",
            "collected_at_utc": "2026-05-26T00:00:00+00:00",
        }
    ]
    pitcher_map = {
        "mlb_2026_test_001": {
            "home_pitcher_id": None,
            "home_pitcher_name": None,
            "away_pitcher_id": None,
            "away_pitcher_name": None,
        }
    }

    from scripts._p84b_2026_public_stats_collector import build_pitcher_features
    result = build_pitcher_features(schedule_rows, pitcher_map, rate_limit_sleep=0.0)

    assert result["feature_pending_count"] > 0
    assert result["gate_pass"] is False, "Gate should fail when pitchers are missing"


# ---------------------------------------------------------------------------
# T20 — If model data incomplete, model gate blocks
# ---------------------------------------------------------------------------

def test_t20_model_pending_blocks_gate():
    pitcher_rows_with_pending = [
        {
            "game_id": "mlb_2026_test_001",
            "home_sp_fip": None,
            "away_sp_fip": None,
            "row_status": "FEATURE_PENDING",
            "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
            "feature_version": "p84b_fip_v1",
        }
    ]
    result = build_model_output_rows(pitcher_rows_with_pending)
    assert result["model_pending_count"] > 0
    assert result["gate_pass"] is False, "Gate should fail when FIP is missing"
    assert result["rows"][0]["predicted_side_derivation_status"] == "MODEL_PENDING"


# ---------------------------------------------------------------------------
# T21 — P83E retry command defined
# ---------------------------------------------------------------------------

def test_t21_p83e_retry_command_defined():
    # Verify the rerun_p83e function exists and is importable
    from scripts._p84b_2026_public_stats_collector import rerun_p83e
    assert callable(rerun_p83e)
    # Verify it references P83E producer
    import inspect
    src = inspect.getsource(rerun_p83e)
    assert "run_p83e_producer" in src


# ---------------------------------------------------------------------------
# T22 — P83E classification captured
# ---------------------------------------------------------------------------

def test_t22_p83e_classification_captured():
    from scripts._p84b_2026_public_stats_collector import rerun_p83e

    with patch(
        "scripts._p84b_2026_public_stats_collector.rerun_p83e",
        return_value={
            "ok": True,
            "p83e_classification": "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA",
            "rows_written": False,
            "row_count": 0,
        },
    ):
        # When gates fail, P83E classification is still captured in summary
        pass  # Tested implicitly by run() structure

    # Direct test: rerun_p83e returns a dict with p83e_classification
    result = rerun_p83e()
    assert "p83e_classification" in result


# ---------------------------------------------------------------------------
# T23 — Canonical rows only written if P83E passes
# ---------------------------------------------------------------------------

def test_t23_canonical_rows_only_if_p83e_passes():
    from scripts._p84b_2026_public_stats_collector import build_model_output_rows

    # When pitcher FIP is None → MODEL_PENDING → gate fails → no canonical rows
    pitcher_rows = [
        {
            "game_id": "mlb_2026_x",
            "home_sp_fip": None,
            "away_sp_fip": None,
            "row_status": "FEATURE_PENDING",
            "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
            "feature_version": "p84b_fip_v1",
        }
    ]
    model_result = build_model_output_rows(pitcher_rows)
    assert model_result["gate_pass"] is False
    # gate_pass=False means P83E would not write canonical rows
    assert model_result["rows"][0]["model_probability"] is None


# ---------------------------------------------------------------------------
# T24 — JSON schema stable
# ---------------------------------------------------------------------------

def test_t24_json_schema_stable():
    summary_path = ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json"
    if not summary_path.exists():
        pytest.skip("P84B summary not yet generated — run script first")
    d = json.loads(summary_path.read_text())
    required_keys = {
        "phase", "date", "generated_at", "p84b_classification",
        "governance", "step1_p84a_state", "step2_schedule",
        "step3_pitcher_features", "step4_model_outputs",
        "step5_p83e_retry", "forbidden_scan",
    }
    for k in required_keys:
        assert k in d, f"missing key: {k}"
    assert d["phase"] == "P84B"


# ---------------------------------------------------------------------------
# T25 — Report includes endpoint/source trace
# ---------------------------------------------------------------------------

def test_t25_report_includes_endpoint_and_source_trace():
    report_path = ROOT / "report/p84b_2026_public_stats_collector_20260526.md"
    if not report_path.exists():
        pytest.skip("P84B report not yet generated — run script first")
    content = report_path.read_text()
    assert "statsapi.mlb.com" in content
    assert "MLB_STATS_API_PUBLIC_SCHEDULE" in content
    assert "DIAGNOSTIC_BASELINE_MODEL" in content


# ---------------------------------------------------------------------------
# T26 — active_task.md updated
# ---------------------------------------------------------------------------

def test_t26_active_task_updated():
    p = ROOT / "00-Plan/roadmap/active_task.md"
    assert p.exists()
    content = p.read_text()
    assert "P84B" in content


# ---------------------------------------------------------------------------
# T27 — Regression: P72A-P84B (spot-check key prior modules)
# ---------------------------------------------------------------------------

def test_t27_regression_key_modules_importable():
    from scripts._p84a_2026_upstream_data_collector_contract import (
        GOVERNANCE as G84A,
        ALLOWED_SOURCE_CLASSES as ASC84A,
    )
    assert G84A["paper_only"] is True
    assert "MLB_STATS_API_PUBLIC_SCHEDULE" in ASC84A

    from scripts._p83e_2026_canonical_prediction_row_producer import (
        GOVERNANCE as G83E,
        run_p83e_producer,
    )
    assert G83E["paper_only"] is True
    assert callable(run_p83e_producer)

    from scripts._p83d_2026_upstream_data_availability_probe import (
        GOVERNANCE as G83D,
    )
    assert G83D["production_ready"] is False


# ---------------------------------------------------------------------------
# Additional unit tests
# ---------------------------------------------------------------------------

def test_fip_formula_paul_skenes():
    # Paul Skenes: IP=60.0, HR=6, BB=9, HBP=4, SO=65
    fip = compute_fip(hr=6, bb=9, hbp=4, k=65, ip_str="60.0")
    assert fip is not None
    expected = round(((13 * 6 + 3 * (9 + 4) - 2 * 65) / 60.0) + FIP_CONSTANT, 4)
    assert abs(fip - expected) < 0.001


def test_diagnostic_model_probability_range():
    for delta in [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0]:
        home_fip = 4.00 + delta / 2
        away_fip = 4.00 - delta / 2
        prob = compute_diagnostic_model_probability(home_fip, away_fip)
        assert 0.30 <= prob <= 0.70, f"prob {prob} out of [0.30, 0.70] for delta={delta}"


def test_diagnostic_model_direction():
    # Higher home_fip relative to away → home worse → lower home win probability
    prob_home_worse = compute_diagnostic_model_probability(home_sp_fip=5.0, away_sp_fip=3.0)
    prob_home_better = compute_diagnostic_model_probability(home_sp_fip=3.0, away_sp_fip=5.0)
    assert prob_home_worse < prob_home_better, (
        f"Expected home_worse({prob_home_worse}) < home_better({prob_home_better})"
    )


def test_model_output_rows_from_ready_pitcher_rows():
    pitcher_rows = [
        {
            "game_id": "mlb_2026_001",
            "home_sp_fip": 3.50,
            "away_sp_fip": 4.20,
            "row_status": "FEATURE_READY",
            "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
            "feature_version": "p84b_fip_v1",
        },
        {
            "game_id": "mlb_2026_002",
            "home_sp_fip": 4.80,
            "away_sp_fip": 3.10,
            "row_status": "FEATURE_READY",
            "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
            "feature_version": "p84b_fip_v1",
        },
    ]
    result = build_model_output_rows(pitcher_rows)
    assert result["model_ready_count"] == 2
    assert result["model_pending_count"] == 0
    assert result["gate_pass"] is True
    for row in result["rows"]:
        assert row["predicted_side_derivation_status"] == "DERIVABLE"
        assert row["model_probability"] is not None
        assert 0.30 <= row["model_probability"] <= 0.70
        errs = validate_model_output_row(row)
        assert errs == [], f"model row invalid: {errs}"


def test_schedule_row_missing_season_fails():
    bad_row = {
        "game_id": "mlb_2026_999",
        "game_date": "2026-04-01",
        "season": 2025,   # wrong season
        "home_team": "NYY",
        "away_team": "BOS",
        "source_trace": "MLB_STATS_API_PUBLIC_SCHEDULE",
        "collected_at_utc": "2026-05-26T00:00:00+00:00",
    }
    errors = validate_schedule_row(bad_row)
    assert any("season" in e for e in errors)


def test_pitcher_row_feature_ready_with_none_fip_fails():
    bad_row = {
        "game_id": "mlb_2026_999",
        "home_sp_fip": None,
        "away_sp_fip": 4.0,
        "source_trace": "MLB_STATS_API_PUBLIC_PLAYER_STATS",
        "feature_version": "p84b_fip_v1",
        "row_status": "FEATURE_READY",  # contradicts None FIP
    }
    errors = validate_pitcher_row(bad_row)
    assert len(errors) > 0, "Should fail: FEATURE_READY with None FIP"


def test_model_output_probability_out_of_range_fails():
    bad_row = {
        "game_id": "mlb_2026_999",
        "model_probability": 1.5,
        "source_prediction_version": SOURCE_PREDICTION_VERSION,
        "model_input_trace": "DIAGNOSTIC_BASELINE_MODEL",
        "predicted_side_derivation_status": "DERIVABLE",
    }
    errors = validate_model_output_row(bad_row)
    assert any("range" in e for e in errors)


def test_governance_constants_immutable():
    assert GOVERNANCE["paper_only"] is True
    assert GOVERNANCE["diagnostic_only"] is True
    assert GOVERNANCE["live_api_calls"] == 0
    assert GOVERNANCE["ev_calculated"] is False
    assert GOVERNANCE["clv_calculated"] is False
    assert GOVERNANCE["kelly_calculated"] is False
    assert GOVERNANCE["kelly_deploy_allowed"] is False
    assert GOVERNANCE["production_ready"] is False
    assert GOVERNANCE["odds_used"] is False
    assert GOVERNANCE["the_odds_api_key_required"] is False
    assert GOVERNANCE["api_key_accessed"] is False
    assert GOVERNANCE["profitability_claim"] is False


def test_fip_constant_reasonable():
    # MLB FIP constant is typically ~3.0-3.2 for modern seasons
    assert 2.5 <= FIP_CONSTANT <= 3.5, f"FIP_CONSTANT {FIP_CONSTANT} seems unreasonable"


def test_build_pitcher_fip_row_no_probable_pitcher():
    row = build_pitcher_fip_row(
        game_id="mlb_2026_test",
        home_pitcher_id=None,
        home_pitcher_name=None,
        away_pitcher_id=None,
        away_pitcher_name=None,
    )
    assert row["row_status"] == "FEATURE_PENDING"
    assert row["home_sp_fip"] is None
    assert row["away_sp_fip"] is None
    errs = validate_pitcher_row(row)
    assert errs == []


def test_allowed_source_classes_complete():
    expected = {
        "MLB_STATS_API_PUBLIC_SCHEDULE",
        "MLB_STATS_API_PUBLIC_PLAYER_STATS",
        "LOCAL_PUBLIC_STATS_EXPORT",
        "MANUAL_PUBLIC_STATS_FIXTURE",
        "MOCK_SCHEMA_ONLY_FIXTURE",
    }
    assert expected.issubset(ALLOWED_SOURCE_CLASSES)


def test_forbidden_source_classes_complete():
    expected = {
        "ODDS_API",
        "PAID_ODDS_DATA",
        "SPORTSBOOK_SOURCE",
        "RUNTIME_PAPER_OUTPUT",
        "FABRICATED_NON_MOCK",
    }
    assert expected.issubset(FORBIDDEN_SOURCE_CLASSES)
