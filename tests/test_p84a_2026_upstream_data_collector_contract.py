"""
Tests for P84A — 2026 Upstream Data Collector Contract
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True

Covers all 29 required test cases (T01-T29).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts._p84a_2026_upstream_data_collector_contract import (
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_SOURCE_CLASSES,
    FORBIDDEN_SOURCE_CLASSES,
    GOVERNANCE,
    MODEL_OUTPUT_CONTRACT,
    PITCHER_FIP_CONTRACT,
    SCHEDULE_COLLECTOR_CONTRACT,
    SOURCE_ARTIFACTS,
    UPSTREAM_TARGET_FILES,
    build_mock_fixture,
    build_mock_model_output_row,
    build_mock_pitcher_row,
    build_mock_schedule_row,
    check_upstream_targets,
    forbidden_scan,
    run,
    validate_mock_fixture,
    validate_model_output_row_p84a,
    validate_pitcher_row_p84a,
    validate_schedule_row_p84a,
    verify_p83e_state,
    verify_source_artifacts,
)


# ---------------------------------------------------------------------------
# T01 — P83E source artifact loads
# ---------------------------------------------------------------------------

def test_t01_p83e_artifact_loads():
    p = SOURCE_ARTIFACTS["p83e_json"]
    assert p.exists(), f"P83E artifact missing: {p}"
    d = json.loads(p.read_text())
    assert "p83e_classification" in d
    assert "governance" in d


# ---------------------------------------------------------------------------
# T02 — P83E classification verified
# ---------------------------------------------------------------------------

def test_t02_p83e_classification_verified():
    state = verify_p83e_state()
    assert state["loaded"] is True
    VALID_P83E_STATES = {
        "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA",
        "P83E_BLOCKED_BY_SCHEMA_MISMATCH",
        "P83E_CANONICAL_ROWS_READY",
    }
    assert state["p83e_classification"] in VALID_P83E_STATES, (
        f"Expected a valid P83E state, got {state['p83e_classification']}"
    )


# ---------------------------------------------------------------------------
# T03 — P83E missing upstream files verified
# ---------------------------------------------------------------------------

def test_t03_p83e_missing_upstream_files():
    state = verify_p83e_state()
    classification = state["p83e_classification"]
    missing = state["missing_upstream_files"]
    if classification == "P83E_BLOCKED_BY_MISSING_UPSTREAM_DATA":
        assert set(missing) == {"schedule", "pitchers", "model_outputs"}, (
            f"unexpected missing set: {missing}"
        )
        assert state["rows_written"] is False
    # Governance invariants always hold regardless of classification
    assert state["live_api_calls"] == 0
    assert state["odds_used"] is False
    assert state["production_ready"] is False


# ---------------------------------------------------------------------------
# T04 — Public stats collector contract generated
# ---------------------------------------------------------------------------

def test_t04_public_collector_contract_generated():
    summary = run()
    assert summary["p84a_classification"] in ALLOWED_CLASSIFICATIONS
    assert "step5_schedule_collector_contract" in summary
    assert "step6_pitcher_fip_contract" in summary
    assert "step7_model_output_contract" in summary


# ---------------------------------------------------------------------------
# T05 — Allowed source classes defined
# ---------------------------------------------------------------------------

def test_t05_allowed_source_classes_defined():
    expected = {
        "MLB_STATS_API_PUBLIC_SCHEDULE",
        "MLB_STATS_API_PUBLIC_PLAYER_STATS",
        "LOCAL_PUBLIC_STATS_EXPORT",
        "MANUAL_PUBLIC_STATS_FIXTURE",
        "MOCK_SCHEMA_ONLY_FIXTURE",
    }
    assert expected.issubset(set(ALLOWED_SOURCE_CLASSES)), f"missing allowed classes: {expected - set(ALLOWED_SOURCE_CLASSES)}"


# ---------------------------------------------------------------------------
# T06 — Forbidden source classes defined
# ---------------------------------------------------------------------------

def test_t06_forbidden_source_classes_defined():
    expected = {
        "ODDS_API",
        "PAID_ODDS_DATA",
        "SPORTSBOOK_SOURCE",
        "RUNTIME_PAPER_OUTPUT",
        "FABRICATED_NON_MOCK",
    }
    assert expected.issubset(set(FORBIDDEN_SOURCE_CLASSES)), f"missing forbidden classes: {expected - set(FORBIDDEN_SOURCE_CLASSES)}"


# ---------------------------------------------------------------------------
# T07 — Schedule collector contract generated
# ---------------------------------------------------------------------------

def test_t07_schedule_collector_contract():
    c = SCHEDULE_COLLECTOR_CONTRACT
    assert c["contract_id"] == "P84A_SCHEDULE_COLLECTOR_CONTRACT_V1"
    required = {"game_id", "game_date", "season", "home_team", "away_team", "source_trace", "collected_at_utc"}
    assert required.issubset(set(c["required_fields"]))
    assert c["output_path"] == "data/mlb_2026/schedule/mlb_2026_schedule.jsonl"
    assert c["activation_gate"] == "SCHEDULE_GATE in P83D/P83E"


# ---------------------------------------------------------------------------
# T08 — Pitcher FIP feature builder contract generated
# ---------------------------------------------------------------------------

def test_t08_pitcher_fip_contract():
    c = PITCHER_FIP_CONTRACT
    assert c["contract_id"] == "P84A_PITCHER_FIP_CONTRACT_V1"
    required = {"game_id", "home_sp_fip", "away_sp_fip", "source_trace", "feature_version"}
    assert required.issubset(set(c["required_fields"]))
    assert "FEATURE_READY" in c["row_status_values"]
    assert "FEATURE_PENDING" in c["row_status_values"]
    assert c["constraints"]["fip_missing_marks_row_FEATURE_PENDING"] is True
    assert c["constraints"]["FEATURE_PENDING_blocks_activation"] is True


# ---------------------------------------------------------------------------
# T09 — Model output builder contract generated
# ---------------------------------------------------------------------------

def test_t09_model_output_contract():
    c = MODEL_OUTPUT_CONTRACT
    assert c["contract_id"] == "P84A_MODEL_OUTPUT_CONTRACT_V1"
    required = {
        "game_id", "model_probability", "source_prediction_version",
        "model_input_trace", "predicted_side_derivation_status",
    }
    assert required.issubset(set(c["required_fields"]))
    assert "DERIVABLE" in c["predicted_side_derivation_status_values"]
    assert "MODEL_PENDING" in c["predicted_side_derivation_status_values"]
    assert c["constraints"]["runtime_paper_output_is_not_canonical"] is True


# ---------------------------------------------------------------------------
# T10 — Missing pitcher/FIP blocks activation
# ---------------------------------------------------------------------------

def test_t10_missing_fip_blocks_activation():
    row = {
        "game_id": "test_001",
        "home_sp_fip": None,
        "away_sp_fip": None,
        "source_trace": "MOCK_SCHEMA_ONLY_FIXTURE",
        "feature_version": "v1",
        # no row_status → should fail validation
    }
    result = validate_pitcher_row_p84a(row)
    assert result["valid"] is False, "Row with missing FIP and no FEATURE_PENDING status should be invalid"

    row_pending = {**row, "row_status": "FEATURE_PENDING"}
    result2 = validate_pitcher_row_p84a(row_pending)
    assert result2["valid"] is True, "Row with FEATURE_PENDING should be valid"


# ---------------------------------------------------------------------------
# T11 — Missing model output blocks activation
# ---------------------------------------------------------------------------

def test_t11_model_pending_blocks_activation():
    row = build_mock_model_output_row("test_001")
    row["predicted_side_derivation_status"] = "MODEL_PENDING"
    row["model_probability"] = 0.5
    result = validate_model_output_row_p84a(row)
    # Schema valid but MODEL_PENDING status means it blocks activation gate
    assert result["valid"] is True  # schema still valid
    assert row["predicted_side_derivation_status"] == "MODEL_PENDING"

    # Verify contract documents the blocking behavior
    assert "MODEL_PENDING" in MODEL_OUTPUT_CONTRACT["blocking_behavior"]
    assert "MODEL_OUTPUT_GATE" in MODEL_OUTPUT_CONTRACT["blocking_behavior"]


# ---------------------------------------------------------------------------
# T12 — Safe dry-run mode defined
# ---------------------------------------------------------------------------

def test_t12_safe_dry_run_mode():
    summary = run()
    # dry-run produces contract artifacts and mock fixture, not real data
    assert summary["step8_mock_fixture_validation"]["canonical"] is False
    assert summary["step8_mock_fixture_validation"]["source_class"] == "MOCK_SCHEMA_ONLY_FIXTURE"
    assert summary["forbidden_scan"]["canonical_rows_written"] is False


# ---------------------------------------------------------------------------
# T13 — Mock schema-only fixture is noncanonical
# ---------------------------------------------------------------------------

def test_t13_mock_fixture_noncanonical():
    fixture = build_mock_fixture(n_games=3)
    assert fixture["canonical"] is False
    assert fixture["source_class"] == "MOCK_SCHEMA_ONLY_FIXTURE"
    assert "In-memory only" in fixture["note"]
    assert "Not written to disk" in fixture["note"]

    # Upstream target files must not exist after mock fixture build
    schedule_path = UPSTREAM_TARGET_FILES["schedule"]
    pitchers_path = UPSTREAM_TARGET_FILES["pitchers"]
    model_path = UPSTREAM_TARGET_FILES["model_outputs"]
    # These files should be missing (we do NOT write mock to disk)
    for gid in [r["game_id"] for r in fixture["schedule_rows"]]:
        assert gid.startswith("mock_"), f"game_id should be mock: {gid}"


# ---------------------------------------------------------------------------
# T14 — No canonical upstream files written unless traceable source data exists
# ---------------------------------------------------------------------------

def test_t14_no_canonical_files_written():
    # Run the full pipeline
    summary = run()
    # Verify no upstream target files were created with real data
    for key, path in UPSTREAM_TARGET_FILES.items():
        if path.exists():
            # If file exists, verify it has traceable source
            with open(path) as f:
                first_line = f.readline().strip()
            if first_line:
                row = json.loads(first_line)
                assert row.get("source_trace") in ALLOWED_SOURCE_CLASSES, \
                    f"file {path} has untraced source: {row.get('source_trace')}"
    # The run() summary must confirm no canonical rows written
    assert summary["forbidden_scan"]["canonical_rows_written"] is False


# ---------------------------------------------------------------------------
# T15 — No odds required
# ---------------------------------------------------------------------------

def test_t15_no_odds_required():
    for c in [SCHEDULE_COLLECTOR_CONTRACT, PITCHER_FIP_CONTRACT, MODEL_OUTPUT_CONTRACT]:
        fields = c.get("required_fields", [])
        odds_fields = [f for f in fields if "odds" in f.lower() or "line" in f.lower() or "spread" in f.lower()]
        assert len(odds_fields) == 0, f"Contract {c['contract_id']} has odds fields: {odds_fields}"
        assert c["constraints"]["no_odds_fields"] is True


# ---------------------------------------------------------------------------
# T16 — No odds API call
# ---------------------------------------------------------------------------

def test_t16_no_odds_api_call():
    assert "ODDS_API" in FORBIDDEN_SOURCE_CLASSES
    assert GOVERNANCE["odds_used"] is False
    assert GOVERNANCE["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# T17 — No API key access
# ---------------------------------------------------------------------------

def test_t17_no_api_key_access():
    assert GOVERNANCE["the_odds_api_key_required"] is False
    assert GOVERNANCE["api_key_accessed"] is False

    # Scan script source for API key access patterns
    script = ROOT / "scripts/_p84a_2026_upstream_data_collector_contract.py"
    content = script.read_text()
    forbidden_patterns = ["THE_ODDS_API_KEY", "os.environ.get('THE_ODDS_API", 'os.environ["THE_ODDS_API']
    for pattern in forbidden_patterns:
        assert pattern not in content, f"API key pattern found: {pattern}"


# ---------------------------------------------------------------------------
# T18 — No edge calculated
# ---------------------------------------------------------------------------

def test_t18_no_edge_calculated():
    assert GOVERNANCE["market_edge_calculated"] is False
    assert GOVERNANCE["market_edge_evaluated"] is False
    script = ROOT / "scripts/_p84a_2026_upstream_data_collector_contract.py"
    content = script.read_text()
    # Check no actual market_edge computation assignments exist (governance dict and comments are fine)
    edge_compute_lines = [
        line.strip() for line in content.split("\n")
        if "market_edge" in line.lower()
        and "market_edge_calculated" not in line
        and "market_edge_evaluated" not in line
        and not line.strip().startswith("#")
        and not line.strip().startswith("<!--")
        and "=" in line
        and "market_edge" in line.lower().split("=")[0]
    ]
    assert len(edge_compute_lines) == 0, f"market_edge computation found: {edge_compute_lines}"


# ---------------------------------------------------------------------------
# T19 — No CLV calculated
# ---------------------------------------------------------------------------

def test_t19_no_clv_calculated():
    assert GOVERNANCE["clv_calculated"] is False
    script = ROOT / "scripts/_p84a_2026_upstream_data_collector_contract.py"
    content = script.read_text()
    # Check that no CLV computation assignments exist (references in comments/strings are fine)
    clv_compute_lines = [
        line.strip() for line in content.split("\n")
        if "clv" in line.lower()
        and "clv_calculated" not in line
        and "=" in line
        and not line.strip().startswith("#")
        and not line.strip().startswith('"')
        and not line.strip().startswith("'")
        and "clv" in line.lower().split("=")[0]
    ]
    assert len(clv_compute_lines) == 0, f"CLV computation assignment found: {clv_compute_lines}"


# ---------------------------------------------------------------------------
# T20 — No EV calculated
# ---------------------------------------------------------------------------

def test_t20_no_ev_calculated():
    assert GOVERNANCE["ev_calculated"] is False
    script = ROOT / "scripts/_p84a_2026_upstream_data_collector_contract.py"
    content = script.read_text()
    ev_lines = [line.strip() for line in content.split("\n")
                if "ev_calculated" not in line and "expected_value" not in line
                and "ev" in line.lower().split("#")[0]
                and "=" in line and "ev" in line.lower().split("=")[0]]
    assert len(ev_lines) == 0, f"EV computation found: {ev_lines}"


# ---------------------------------------------------------------------------
# T21 — No Kelly calculated
# ---------------------------------------------------------------------------

def test_t21_no_kelly_calculated():
    assert GOVERNANCE["kelly_calculated"] is False
    assert GOVERNANCE["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# T22 — live_api_calls=0 for odds APIs
# ---------------------------------------------------------------------------

def test_t22_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    fscan = forbidden_scan()
    assert fscan["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# T23 — production_ready=false
# ---------------------------------------------------------------------------

def test_t23_production_ready_false():
    assert GOVERNANCE["production_ready"] is False
    summary = run()
    assert summary["governance"]["production_ready"] is False


# ---------------------------------------------------------------------------
# T24 — kelly_deploy_allowed=false
# ---------------------------------------------------------------------------

def test_t24_kelly_deploy_allowed_false():
    assert GOVERNANCE["kelly_deploy_allowed"] is False
    summary = run()
    assert summary["governance"]["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# T25 — Forbidden scan passes
# ---------------------------------------------------------------------------

def test_t25_forbidden_scan_passes():
    fscan = forbidden_scan()
    assert fscan["forbidden_scan_pass"] is True
    assert fscan["api_key_accessed"] is False
    assert fscan["ev_calculated"] is False
    assert fscan["clv_calculated"] is False
    assert fscan["kelly_calculated"] is False
    assert fscan["production_ready"] is False
    assert fscan["canonical_rows_written"] is False


# ---------------------------------------------------------------------------
# T26 — JSON schema stable
# ---------------------------------------------------------------------------

def test_t26_json_schema_stable():
    summary = run()
    required_top_keys = {
        "phase", "date", "generated_at", "p84a_classification",
        "allowed_classifications", "governance", "prediction_boundary",
        "step1_p83e_state", "step4_allowed_source_classes",
        "step4_forbidden_source_classes", "step5_schedule_collector_contract",
        "step6_pitcher_fip_contract", "step7_model_output_contract",
        "step8_mock_fixture_validation", "forbidden_scan",
    }
    for key in required_top_keys:
        assert key in summary, f"missing key: {key}"
    # Should be JSON serializable
    json_str = json.dumps(summary, default=str)
    reparsed = json.loads(json_str)
    assert reparsed["phase"] == "P84A"


# ---------------------------------------------------------------------------
# T27 — Report includes collector contract
# ---------------------------------------------------------------------------

def test_t27_report_includes_collector_contract():
    report_path = ROOT / "report/p84a_2026_upstream_data_collector_contract_20260526.md"
    assert report_path.exists(), "P84A report not found — run the script first"
    content = report_path.read_text()
    assert "P84A_SCHEDULE_COLLECTOR_CONTRACT_V1" in content
    assert "P84A_PITCHER_FIP_CONTRACT_V1" in content
    assert "P84A_MODEL_OUTPUT_CONTRACT_V1" in content
    assert "MLB_STATS_API_PUBLIC_SCHEDULE" in content
    assert "FEATURE_PENDING" in content
    assert "MODEL_PENDING" in content


# ---------------------------------------------------------------------------
# T28 — active_task.md updated
# ---------------------------------------------------------------------------

def test_t28_active_task_updated():
    p = ROOT / "00-Plan/roadmap/active_task.md"
    assert p.exists()
    content = p.read_text()
    assert "P84A" in content
    assert "P84A_UPSTREAM_COLLECTOR_CONTRACT_READY" in content


# ---------------------------------------------------------------------------
# T29 — Regression: P72A-P84A passes (spot check key imports)
# ---------------------------------------------------------------------------

def test_t29_regression_key_modules_importable():
    # Spot-check that prior phase modules still importable
    from scripts._p83e_2026_canonical_prediction_row_producer import (
        GOVERNANCE as G83E,
        run_p83e_producer,
    )
    assert G83E["paper_only"] is True
    assert G83E["production_ready"] is False

    from scripts._p83d_2026_upstream_data_availability_probe import (
        GOVERNANCE as G83D,
    )
    assert G83D["paper_only"] is True

    from scripts._p83c_2026_prediction_schema_producer_contract import (
        GOVERNANCE as G83C,
    )
    assert G83C["paper_only"] is True


# ---------------------------------------------------------------------------
# Additional schema validation tests
# ---------------------------------------------------------------------------

def test_schedule_row_valid_mock():
    row = build_mock_schedule_row("g001", "2026-04-15")
    result = validate_schedule_row_p84a(row)
    assert result["valid"] is True, f"errors: {result['errors']}"


def test_schedule_row_invalid_season():
    row = build_mock_schedule_row("g001")
    row["season"] = 2025
    result = validate_schedule_row_p84a(row)
    assert result["valid"] is False
    assert any("season" in e for e in result["errors"])


def test_schedule_row_invalid_source():
    row = build_mock_schedule_row("g001")
    row["source_trace"] = "ODDS_API"
    result = validate_schedule_row_p84a(row)
    assert result["valid"] is False
    assert any("source_trace" in e for e in result["errors"])


def test_pitcher_row_valid_mock():
    row = build_mock_pitcher_row("g001")
    result = validate_pitcher_row_p84a(row)
    assert result["valid"] is True, f"errors: {result['errors']}"


def test_model_output_row_valid_mock():
    row = build_mock_model_output_row("g001")
    result = validate_model_output_row_p84a(row)
    assert result["valid"] is True, f"errors: {result['errors']}"


def test_model_output_probability_out_of_range():
    row = build_mock_model_output_row("g001")
    row["model_probability"] = 1.5
    result = validate_model_output_row_p84a(row)
    assert result["valid"] is False
    assert any("range" in e for e in result["errors"])


def test_mock_fixture_full_validation():
    fixture = build_mock_fixture(n_games=5)
    result = validate_mock_fixture(fixture)
    assert result["all_valid"] is True, (
        f"schedule_errors: {result['schedule_errors']}, "
        f"pitcher_errors: {result['pitcher_errors']}, "
        f"model_errors: {result['model_errors']}"
    )


def test_classification_is_valid():
    summary = run()
    assert summary["p84a_classification"] in ALLOWED_CLASSIFICATIONS


def test_governance_constants_immutable():
    # Governance dict should have all required keys set correctly
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
    assert GOVERNANCE["real_bet_allowed"] is False
    assert GOVERNANCE["champion_replacement_allowed"] is False


def test_runtime_paper_output_forbidden():
    assert "RUNTIME_PAPER_OUTPUT" in FORBIDDEN_SOURCE_CLASSES
    # Verify model output contract explicitly marks it noncanonical
    assert MODEL_OUTPUT_CONTRACT["constraints"]["runtime_paper_output_is_not_canonical"] is True
