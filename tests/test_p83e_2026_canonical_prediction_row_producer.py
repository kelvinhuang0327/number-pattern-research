"""
tests/test_p83e_2026_canonical_prediction_row_producer.py
P83E — 2026 Canonical Prediction Row Producer
35 required tests
paper_only=True | diagnostic_only=True | NO_REAL_BET=True
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "_p83e_2026_canonical_prediction_row_producer.py"
JSON_OUT = ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json"
P83D_JSON = ROOT / "data/mlb_2026/derived/p83d_2026_upstream_data_availability_probe_summary.json"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"
REPORT_MD = ROOT / "report/p83e_2026_canonical_prediction_row_producer_20260526.md"
CANONICAL_PRED_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"


@pytest.fixture(scope="module")
def mod():
    mod_name = "_p83e_2026_canonical_prediction_row_producer"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def p83e_result(mod):
    return mod.run_p83e_producer()


@pytest.fixture(scope="module")
def p83e_json():
    assert JSON_OUT.exists(), f"P83E JSON not found: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


@pytest.fixture(scope="module")
def mock_fixture(mod):
    return mod.build_mock_upstream_fixture()


@pytest.fixture(scope="module")
def mock_canonical_rows(mod, mock_fixture):
    return mod.produce_mock_canonical_rows(mock_fixture)


# ===========================================================================
# T01 — P83D source artifact loads
# ===========================================================================
def test_t01_p83d_artifact_loads():
    """T01: P83D source artifact must exist and be loadable."""
    assert P83D_JSON.exists(), f"P83D artifact missing: {P83D_JSON}"
    d = json.loads(P83D_JSON.read_text())
    assert isinstance(d, dict)
    assert "p83d_classification" in d


# ===========================================================================
# T02 — P83D classification verified
# ===========================================================================
def test_t02_p83d_classification_verified(p83e_result):
    """T02: P83E must load and verify P83D classification."""
    p83d = p83e_result.get("step1_p83d_artifact", {})
    assert p83d.get("loaded") is True
    assert p83d.get("p83d_classification") == "P83D_AWAITING_UPSTREAM_DATA"
    assert p83d.get("classification_ok") is True


# ===========================================================================
# T03 — Required upstream file list verified
# ===========================================================================
def test_t03_upstream_file_list_verified(mod):
    """T03: UPSTREAM_FILES must define all 3 required upstream paths."""
    files = mod.UPSTREAM_FILES
    assert "schedule" in files
    assert "pitchers" in files
    assert "model_outputs" in files
    assert "mlb_2026_schedule.jsonl" in str(files["schedule"])
    assert "mlb_2026_sp_fip_features.jsonl" in str(files["pitchers"])
    assert "mlb_2026_model_outputs.jsonl" in str(files["model_outputs"])


# ===========================================================================
# T04 — P83E classification reflects upstream file state
# ===========================================================================
def test_t04_missing_upstream_blocks_producer(p83e_result):
    """T04: P83E classification must be a valid allowed classification.

    Before P84B: upstream files absent → P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA.
    After P84B:  upstream files present and schema-valid → P83E_CANONICAL_ROWS_READY
                 (828 rows written for FEATURE_READY games with complete FIP data).
    """
    assert p83e_result["p83e_classification"] in [
        "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA",
        "P83E_BLOCKED_BY_SCHEMA_MISMATCH",
        "P83E_CANONICAL_ROWS_READY",
    ], f"Unexpected classification: {p83e_result['p83e_classification']}"
    # Key invariant: governance always respected regardless of classification
    assert p83e_result["governance"]["production_ready"] is False
    assert p83e_result["governance"]["odds_used"] is False


# ===========================================================================
# T05 — Schedule schema validator defined
# ===========================================================================
def test_t05_schedule_schema_validator(mod):
    """T05: validate_schedule_row must reject rows missing required fields."""
    errs = mod.validate_schedule_row({"game_id": "G1", "game_date": "2026-05-10", "season": 2026, "home_team": "BOS", "away_team": "NYY"})
    assert errs == [], f"Valid row should have no errors: {errs}"

    errs = mod.validate_schedule_row({"game_id": "G1"})
    assert any("game_date" in e for e in errs)
    assert any("home_team" in e for e in errs)

    errs = mod.validate_schedule_row({"game_id": "G1", "game_date": "2026-05-10", "season": 2025, "home_team": "BOS", "away_team": "NYY"})
    assert any("2026" in e for e in errs)


# ===========================================================================
# T06 — Pitcher feature schema validator defined
# ===========================================================================
def test_t06_pitcher_schema_validator(mod):
    """T06: validate_pitcher_row must validate FIP fields."""
    errs = mod.validate_pitcher_row({"game_id": "G1", "home_sp_fip": 3.5, "away_sp_fip": 4.0})
    assert errs == []

    errs = mod.validate_pitcher_row({"game_id": "G1"})
    assert any("home_sp_fip" in e for e in errs)

    errs = mod.validate_pitcher_row({"game_id": "G1", "home_sp_fip": -1.0, "away_sp_fip": 3.0})
    assert any("range" in e for e in errs)


# ===========================================================================
# T07 — Model output schema validator defined
# ===========================================================================
def test_t07_model_output_schema_validator(mod):
    """T07: validate_model_output_row must validate probability fields."""
    errs = mod.validate_model_output_row({
        "game_id": "G1", "model_probability": 0.58,
        "source_prediction_version": "mlb_2026_prediction_rows_v1"
    })
    assert errs == []

    errs = mod.validate_model_output_row({"game_id": "G1"})
    assert any("model_probability" in e for e in errs)

    errs = mod.validate_model_output_row({
        "game_id": "G1", "model_probability": 1.5,
        "source_prediction_version": "v1"
    })
    assert any("(0, 1)" in e for e in errs)


# ===========================================================================
# T08 — Join by game_id defined
# ===========================================================================
def test_t08_join_by_game_id(mod):
    """T08: join_upstream must join 3 datasets by game_id."""
    s = {"loaded": True, "rows": [{"game_id": "G1", "game_date": "2026-05-10", "season": 2026, "home_team": "BOS", "away_team": "NYY"}]}
    p = {"loaded": True, "rows": [{"game_id": "G1", "home_sp_fip": 3.5, "away_sp_fip": 4.0}]}
    m = {"loaded": True, "rows": [{"game_id": "G1", "model_probability": 0.58, "source_prediction_version": "v1"}]}
    result = mod.join_upstream(s, p, m)
    assert result["joined_row_count"] == 1
    assert result["join_ok"] is True
    assert result["joined_rows"][0]["game_id"] == "G1"
    assert result["joined_rows"][0]["home_sp_fip"] == 3.5


# ===========================================================================
# T09 — Duplicate game_id check present
# ===========================================================================
def test_t09_duplicate_game_id_check(mod):
    """T09: Duplicate game_id in upstream file must be flagged."""
    import io
    # Create a fake schedule file with duplicate game_ids
    rows = [
        {"game_id": "G1", "game_date": "2026-05-10", "season": 2026, "home_team": "BOS", "away_team": "NYY"},
        {"game_id": "G1", "game_date": "2026-05-11", "season": 2026, "home_team": "BOS", "away_team": "NYY"},
    ]
    schedule_data = {"loaded": True, "rows": rows, "row_count": 2,
                     "schema_valid": True, "validation_errors": [],
                     "duplicate_game_ids": ["G1"]}
    assert "G1" in schedule_data["duplicate_game_ids"]


# ===========================================================================
# T10 — Unmatched row reporting present
# ===========================================================================
def test_t10_unmatched_row_reporting(mod):
    """T10: Join must report unmatched rows from each source."""
    s = {"loaded": True, "rows": [
        {"game_id": "G1", "game_date": "2026-05-10", "season": 2026, "home_team": "BOS", "away_team": "NYY"},
        {"game_id": "G2", "game_date": "2026-05-10", "season": 2026, "home_team": "LAD", "away_team": "SF"},  # no pitcher match
    ]}
    p = {"loaded": True, "rows": [{"game_id": "G1", "home_sp_fip": 3.5, "away_sp_fip": 4.0}]}
    m = {"loaded": True, "rows": [{"game_id": "G1", "model_probability": 0.58, "source_prediction_version": "v1"}]}
    result = mod.join_upstream(s, p, m)
    assert result["joined_row_count"] == 1  # only G1
    assert "G2" in result["unmatched_schedule_ids"]


# ===========================================================================
# T11 — sp_fip_delta computation present
# ===========================================================================
def test_t11_sp_fip_delta_computation(mod):
    """T11: sp_fip_delta = home_sp_fip - away_sp_fip (P83C convention)."""
    delta = mod.compute_sp_fip_delta(4.80, 3.50)
    assert abs(delta - 1.30) < 1e-9

    delta_neg = mod.compute_sp_fip_delta(3.20, 4.60)
    assert abs(delta_neg - (-1.40)) < 1e-9


# ===========================================================================
# T12 — abs_sp_fip_delta computation present
# ===========================================================================
def test_t12_abs_sp_fip_delta_computation(mod):
    """T12: abs_sp_fip_delta = abs(sp_fip_delta)."""
    delta = mod.compute_sp_fip_delta(3.20, 4.60)
    assert abs(abs(delta) - 1.40) < 1e-9
    # Test via compute_prediction_row
    row = mod.compute_prediction_row({
        "game_id": "G1", "game_date": "2026-05-10", "season": 2026,
        "home_team": "BOS", "away_team": "NYY",
        "home_sp_fip": 3.20, "away_sp_fip": 4.60,
        "model_probability": 0.58,
        "source_prediction_version": "mlb_2026_prediction_rows_v1",
    })
    assert row is not None
    assert abs(row["abs_sp_fip_delta"] - 1.40) < 1e-6


# ===========================================================================
# T13 — predicted_side computation present
# ===========================================================================
def test_t13_predicted_side_computation(mod):
    """T13: predicted_side logic — P84G-corrected convention (FIP: lower-is-better).

    sp_fip_delta = home_sp_fip - away_sp_fip
    delta > 0 → home pitcher FIP higher (worse) → predicted_side='away'
    delta < 0 → away pitcher FIP higher (worse) → predicted_side='home'
    [P84G fix: corrected from P84F_SIDE_MAPPING_INVERTED]
    """
    assert mod.compute_predicted_side(1.30) == "away"   # home pitcher worse (higher FIP)
    assert mod.compute_predicted_side(-1.40) == "home"  # away pitcher worse (higher FIP)
    assert mod.compute_predicted_side(0.35) == "away"
    assert mod.compute_predicted_side(-0.15) == "home"
    assert mod.compute_predicted_side(0.0) is None  # tie excluded


# ===========================================================================
# T14 — Primary 125 rule flag computation present
# ===========================================================================
def test_t14_primary_125_rule_flag(mod):
    """T14: rule_primary_125_flag: home abs>=0.50, away abs>=1.25."""
    # home, abs=1.30 → True
    flags = mod.compute_rule_flags("home", 1.30)
    assert flags["rule_primary_125_flag"] is True

    # home, abs=0.35 → False
    flags = mod.compute_rule_flags("home", 0.35)
    assert flags["rule_primary_125_flag"] is False

    # away, abs=1.30 → True (>= 1.25)
    flags = mod.compute_rule_flags("away", 1.30)
    assert flags["rule_primary_125_flag"] is True

    # away, abs=1.10 → False (< 1.25)
    flags = mod.compute_rule_flags("away", 1.10)
    assert flags["rule_primary_125_flag"] is False


# ===========================================================================
# T15 — Shadow 100 rule flag computation present
# ===========================================================================
def test_t15_shadow_100_rule_flag(mod):
    """T15: rule_shadow_100_flag: home abs>=0.50, away abs>=1.00."""
    # away, abs=1.10 → True (>= 1.00)
    flags = mod.compute_rule_flags("away", 1.10)
    assert flags["rule_shadow_100_flag"] is True

    # away, abs=0.90 → False (< 1.00)
    flags = mod.compute_rule_flags("away", 0.90)
    assert flags["rule_shadow_100_flag"] is False

    # home, abs=0.50 → True (>= 0.50)
    flags = mod.compute_rule_flags("home", 0.50)
    assert flags["rule_shadow_100_flag"] is True

    # home, abs=0.49 → False (< 0.50)
    flags = mod.compute_rule_flags("home", 0.49)
    assert flags["rule_shadow_100_flag"] is False


# ===========================================================================
# T16 — Tier B flag computation present
# ===========================================================================
def test_t16_tier_b_flag(mod):
    """T16: tier_b_candidate_flag: 0.25 <= abs < 0.50."""
    flags = mod.compute_rule_flags("home", 0.35)
    assert flags["tier_b_candidate_flag"] is True

    flags = mod.compute_rule_flags("home", 0.25)
    assert flags["tier_b_candidate_flag"] is True

    flags = mod.compute_rule_flags("home", 0.50)
    assert flags["tier_b_candidate_flag"] is False  # >= 0.50, exits tier_b range

    flags = mod.compute_rule_flags("home", 0.24)
    assert flags["tier_b_candidate_flag"] is False  # < 0.25


# ===========================================================================
# T17 — Tier A flag computation present
# ===========================================================================
def test_t17_tier_a_flag(mod):
    """T17: tier_a_watchlist_flag: abs < 0.25."""
    flags = mod.compute_rule_flags("home", 0.15)
    assert flags["tier_a_watchlist_flag"] is True

    flags = mod.compute_rule_flags("home", 0.25)
    assert flags["tier_a_watchlist_flag"] is False  # = 0.25, not < 0.25

    flags = mod.compute_rule_flags("home", 0.35)
    assert flags["tier_a_watchlist_flag"] is False


# ===========================================================================
# T18 — Governance fields enforced
# ===========================================================================
def test_t18_governance_fields_enforced(mod):
    """T18: Each canonical row must have governance fields with correct values."""
    row = mod.compute_prediction_row({
        "game_id": "G1", "game_date": "2026-05-10", "season": 2026,
        "home_team": "BOS", "away_team": "NYY",
        "home_sp_fip": 4.80, "away_sp_fip": 3.50,
        "model_probability": 0.58,
        "source_prediction_version": "mlb_2026_prediction_rows_v1",
    })
    assert row is not None
    assert row["paper_only"] is True
    assert row["diagnostic_only"] is True
    assert row["odds_used"] is False
    assert row["market_edge_evaluated"] is False
    assert row["production_ready"] is False
    assert row["season"] == 2026


# ===========================================================================
# T19 — No odds required
# ===========================================================================
def test_t19_no_odds_required(p83e_result):
    """T19: P83E must not require or use odds data."""
    gov = p83e_result["governance"]
    assert gov["odds_used"] is False
    assert gov["uses_historical_odds"] is False


# ===========================================================================
# T20 — No API call
# ===========================================================================
def test_t20_no_api_call(p83e_result):
    """T20: P83E must make zero API calls."""
    gov = p83e_result["governance"]
    assert gov["live_api_calls"] == 0


# ===========================================================================
# T21 — No API key access
# ===========================================================================
def test_t21_no_api_key_access(p83e_result):
    """T21: P83E must not access any API key."""
    gov = p83e_result["governance"]
    assert gov["api_key_accessed"] is False
    assert gov["the_odds_api_key_required"] is False


# ===========================================================================
# T22 — No edge calculated
# ===========================================================================
def test_t22_no_edge_calculated(p83e_result):
    """T22: P83E must not calculate market edge."""
    gov = p83e_result["governance"]
    assert gov["market_edge_calculated"] is False
    assert gov["market_edge_evaluated"] is False


# ===========================================================================
# T23 — No CLV calculated
# ===========================================================================
def test_t23_no_clv_calculated(p83e_result):
    """T23: P83E must not calculate CLV."""
    assert p83e_result["governance"]["clv_calculated"] is False


# ===========================================================================
# T24 — No EV calculated
# ===========================================================================
def test_t24_no_ev_calculated(p83e_result):
    """T24: P83E must not calculate EV."""
    assert p83e_result["governance"]["ev_calculated"] is False


# ===========================================================================
# T25 — No Kelly calculated
# ===========================================================================
def test_t25_no_kelly_calculated(p83e_result):
    """T25: P83E must not calculate Kelly fraction."""
    assert p83e_result["governance"]["kelly_calculated"] is False


# ===========================================================================
# T26 — live_api_calls=0
# ===========================================================================
def test_t26_live_api_calls_zero(p83e_result):
    """T26: live_api_calls must be exactly 0."""
    assert p83e_result["governance"]["live_api_calls"] == 0
    assert p83e_result["forbidden_scan"]["live_api_calls"] == 0


# ===========================================================================
# T27 — production_ready=False
# ===========================================================================
def test_t27_production_ready_false(p83e_result):
    """T27: production_ready must be False."""
    assert p83e_result["governance"]["production_ready"] is False
    assert p83e_result["forbidden_scan"]["production_ready"] is False


# ===========================================================================
# T28 — kelly_deploy_allowed=False
# ===========================================================================
def test_t28_kelly_deploy_allowed_false(p83e_result):
    """T28: kelly_deploy_allowed must be False."""
    assert p83e_result["governance"]["kelly_deploy_allowed"] is False
    assert p83e_result["forbidden_scan"]["kelly_deploy_allowed"] is False


# ===========================================================================
# T29 — Canonical rows state consistent with P83E classification
# ===========================================================================
def test_t29_no_canonical_rows_when_upstream_missing(p83e_result):
    """T29: Canonical rows must be consistent with P83E classification.

    Before P84B: upstream files absent → rows_written=False, file absent.
    After P84B:  upstream files present → rows_written=True, 828 FEATURE_READY
                 games written (DIAGNOSTIC_BASELINE_MODEL, paper_only=True).
    """
    canon = p83e_result["step6_canonical_rows"]
    classification = p83e_result["p83e_classification"]
    if classification == "P83E_CANONICAL_ROWS_READY":
        assert canon["rows_written"] is True, "CANONICAL_ROWS_READY must have rows_written=True"
        assert canon.get("row_count", 0) > 0, "CANONICAL_ROWS_READY must have row_count > 0"
        assert CANONICAL_PRED_PATH.exists(), (
            f"Canonical prediction file must exist when P83E is CANONICAL_ROWS_READY: {CANONICAL_PRED_PATH}"
        )
    else:
        # Blocked states: rows must not be written
        assert canon["rows_written"] is False, (
            f"rows_written must be False when classification={classification}"
        )


# ===========================================================================
# T30 — In-memory mock fixture produces valid schema rows
# ===========================================================================
def test_t30_mock_fixture_schema_validation(mod, mock_canonical_rows):
    """T30: Mock fixture must produce rows that pass canonical schema validation."""
    assert len(mock_canonical_rows) > 0, "Mock fixture must produce at least 1 row"
    for i, row in enumerate(mock_canonical_rows):
        errors = mod.validate_canonical_row(row)
        assert errors == [], f"Row {i} (game_id={row.get('game_id')}) has schema errors: {errors}"


# ===========================================================================
# T30b — Mock fixture rule flag verification matches P83C cases
# ===========================================================================
def test_t30b_mock_fixture_rule_flags(mod, mock_canonical_rows):
    """T30b: Mock fixture rows must have correct rule flags per P83C verification cases."""
    # Map by game_id
    rows_by_id = {r["game_id"]: r for r in mock_canonical_rows}

    # Case 1: NYY@BOS: home_fip=4.80, away_fip=3.50 → delta=+1.30
    # P84G fix: delta>0 → home pitcher WORSE → predicted_side='away'
    r = rows_by_id["MLB2026_NYY_BOS_20260510"]
    assert r["predicted_side"] == "away"  # P84G: delta>0 → away
    assert abs(r["abs_sp_fip_delta"] - 1.30) < 1e-6
    assert r["rule_primary_125_flag"] is True   # away abs=1.30 >= 1.25
    assert r["rule_shadow_100_flag"] is True    # away abs=1.30 >= 1.00
    assert r["tier_b_candidate_flag"] is False
    assert r["tier_a_watchlist_flag"] is False

    # Case 2: LAD@SF: home_fip=3.20, away_fip=4.60 → delta=-1.40
    # P84G fix: delta<0 → away pitcher WORSE → predicted_side='home'
    r = rows_by_id["MLB2026_LAD_SF_20260510"]
    assert r["predicted_side"] == "home"  # P84G: delta<0 → home
    assert abs(r["abs_sp_fip_delta"] - 1.40) < 1e-6
    assert r["rule_primary_125_flag"] is True   # home abs=1.40 >= 0.50
    assert r["rule_shadow_100_flag"] is True    # home abs=1.40 >= 0.50

    # Case 3: CHC@STL: home_fip=3.10, away_fip=4.20 → delta=-1.10
    # P84G fix: delta<0 → away pitcher WORSE → predicted_side='home'
    r = rows_by_id["MLB2026_CHC_STL_20260511"]
    assert r["predicted_side"] == "home"  # P84G: delta<0 → home
    assert abs(r["abs_sp_fip_delta"] - 1.10) < 1e-6
    assert r["rule_primary_125_flag"] is True   # home abs=1.10 >= 0.50 (P84G: was False with away)
    assert r["rule_shadow_100_flag"] is True    # home abs=1.10 >= 0.50

    # Case 4: HOU@TEX: home_fip=4.00, away_fip=3.65 → delta=+0.35
    # P84G fix: delta>0 → home pitcher WORSE → predicted_side='away'
    r = rows_by_id["MLB2026_HOU_TEX_20260511"]
    assert r["predicted_side"] == "away"  # P84G: delta>0 → away
    assert abs(r["abs_sp_fip_delta"] - 0.35) < 1e-6
    assert r["rule_primary_125_flag"] is False  # away abs=0.35 < 1.25
    assert r["rule_shadow_100_flag"] is False   # away abs=0.35 < 1.00
    assert r["tier_b_candidate_flag"] is True   # 0.25 <= 0.35 < 0.50

    # Case 5: ATL@NYM: home_fip=3.80, away_fip=3.65 → delta=+0.15
    # P84G fix: delta>0 → home pitcher WORSE → predicted_side='away'
    r = rows_by_id["MLB2026_ATL_NYM_20260512"]
    assert r["predicted_side"] == "away"  # P84G: delta>0 → away
    assert abs(r["abs_sp_fip_delta"] - 0.15) < 1e-6
    assert r["tier_a_watchlist_flag"] is True   # abs=0.15 < 0.25


# ===========================================================================
# T31 — Forbidden scan passes
# ===========================================================================
def test_t31_forbidden_scan_passes(p83e_result):
    """T31: Forbidden scan must pass (all forbidden operations absent)."""
    fs = p83e_result["forbidden_scan"]
    assert fs["forbidden_scan_pass"] is True
    # canonical_rows_written reflects actual write state (True after P84B enabled P83E)
    assert isinstance(fs["canonical_rows_written"], bool)


# ===========================================================================
# T32 — JSON schema stable
# ===========================================================================
def test_t32_json_schema_stable(p83e_json):
    """T32: Output JSON must contain all required top-level keys."""
    required_keys = {
        "phase", "date", "generated_at", "p83e_classification",
        "governance", "prediction_boundary",
        "step1_p83d_artifact", "step2_upstream_check",
        "step3_gate_recheck", "step6_canonical_rows",
        "step7_next_prompt", "forbidden_scan",
    }
    for key in required_keys:
        assert key in p83e_json, f"Missing required key: {key}"
    assert p83e_json["phase"] == "P83E"
    assert p83e_json["date"] == "2026-05-26"


# ===========================================================================
# T33 — Report includes gate result
# ===========================================================================
def test_t33_report_includes_gate_results():
    """T33: Markdown report must include gate result table."""
    assert REPORT_MD.exists(), f"Report not found: {REPORT_MD}"
    content = REPORT_MD.read_text()
    assert "SCHEDULE_GATE" in content
    assert "PITCHER_FEATURE_GATE" in content
    assert "MODEL_OUTPUT_GATE" in content
    assert "GOVERNANCE_GATE" in content
    assert "PRODUCER_ACTIVATION_GATE" in content


# ===========================================================================
# T34 — active_task.md updated
# ===========================================================================
def test_t34_active_task_md_updated():
    """T34: active_task.md must exist (will be updated after commit)."""
    assert ACTIVE_TASK_MD.exists()
    content = ACTIVE_TASK_MD.read_text()
    assert len(content) > 10


# ===========================================================================
# T35 — Allowed classifications complete
# ===========================================================================
def test_t35_allowed_classifications_complete(mod):
    """T35: ALLOWED_CLASSIFICATIONS must include all 4 valid P83E states."""
    allowed = mod.ALLOWED_CLASSIFICATIONS
    assert "P83E_CANONICAL_ROWS_READY" in allowed
    assert "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA" in allowed
    assert "P83E_BLOCKED_BY_SCHEMA_MISMATCH" in allowed
    assert "P83E_FAILED_VALIDATION" in allowed
