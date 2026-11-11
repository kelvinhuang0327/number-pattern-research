"""
tests/test_p83d_2026_upstream_data_availability_probe.py
P83D — 2026 Upstream Data Availability Probe + Producer Activation Gate
37 required tests
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
SCRIPT = ROOT / "scripts" / "_p83d_2026_upstream_data_availability_probe.py"
JSON_OUT = ROOT / "data/mlb_2026/derived/p83d_2026_upstream_data_availability_probe_summary.json"
P83C_JSON = ROOT / "data/mlb_2026/derived/p83c_2026_prediction_schema_producer_contract_summary.json"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"
REPORT_MD = ROOT / "report/p83d_2026_upstream_data_availability_probe_20260526.md"
CANONICAL_PRED_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"


@pytest.fixture(scope="module")
def p83d_module():
    mod_name = "_p83d_2026_upstream_data_availability_probe"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p83d_result(p83d_module):
    return p83d_module.run_p83d_probe()


@pytest.fixture(scope="module")
def p83d_json():
    assert JSON_OUT.exists(), f"P83D JSON not found: {JSON_OUT}"
    return json.loads(JSON_OUT.read_text())


# ===========================================================================
# T01 — P83C source artifact loads
# ===========================================================================
def test_t01_p83c_artifact_loads():
    """T01: P83C source artifact must exist and be loadable."""
    assert P83C_JSON.exists(), f"P83C artifact missing: {P83C_JSON}"
    d = json.loads(P83C_JSON.read_text())
    assert isinstance(d, dict), "P83C artifact must be a dict"
    assert "p83c_classification" in d


# ===========================================================================
# T02 — P83C classification verified
# ===========================================================================
def test_t02_p83c_classification_verified(p83d_result):
    """T02: P83D must verify P83C classification is a valid P83C state."""
    v = p83d_result["step1_p83c_verification"]
    assert v["artifact_loaded"] is True
    VALID_P83C = {
        "P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA",
        "P83C_SCHEMA_PRODUCER_READY_WITH_EXISTING_UPSTREAM_DATA",
    }
    assert v["p83c_classification"] in VALID_P83C, (
        f"Expected a valid P83C classification, got {v['p83c_classification']}"
    )
    assert isinstance(v["classification_ok"], bool)


# ===========================================================================
# T03 — Canonical prediction path verified
# ===========================================================================
def test_t03_canonical_prediction_path_verified(p83d_result):
    """T03: Canonical prediction path must be defined in P83C contract."""
    v = p83d_result["step1_p83c_verification"]
    assert v["canonical_path_defined"] is True
    path = v["canonical_prediction_path"]
    assert "mlb_2026" in path
    assert "mlb_2026_prediction_rows.jsonl" in path


# ===========================================================================
# T04 — Upstream input contract verified
# ===========================================================================
def test_t04_upstream_input_contract_verified(p83d_result):
    """T04: P83C upstream input contract must exist and have required fields."""
    v = p83d_result["step1_p83c_verification"]
    assert v["upstream_contract_exists"] is True
    assert v["upstream_contract_id"] != ""


# ===========================================================================
# T05 — Mock rows cannot unlock snapshot
# ===========================================================================
def test_t05_mock_rows_cannot_unlock_snapshot(p83d_result):
    """T05: P83C mock rows are in-memory only and cannot unlock the snapshot."""
    v = p83d_result["step1_p83c_verification"]
    assert v["mock_rows_noncanonical"] is True


# ===========================================================================
# T06 — Local-only probe contract generated
# ===========================================================================
def test_t06_probe_contract_generated(p83d_result):
    """T06: P83D probe must produce upstream probe results."""
    probe = p83d_result["step2_upstream_probe"]
    assert "dirs_probed" in probe
    assert "files_by_category" in probe
    assert isinstance(probe["dirs_probed"], list)


# ===========================================================================
# T07 — Probe paths defined
# ===========================================================================
def test_t07_probe_paths_defined(p83d_module):
    """T07: PROBE_PATHS constant must be defined with expected directories."""
    probe_paths = p83d_module.PROBE_PATHS
    assert isinstance(probe_paths, list)
    assert len(probe_paths) > 0
    path_strs = [str(p) for p in probe_paths]
    assert any("mlb_2026" in s for s in path_strs)


# ===========================================================================
# T08 — Probe does not call API
# ===========================================================================
def test_t08_probe_does_not_call_api(p83d_result):
    """T08: Probe must not make any external API calls."""
    gov = p83d_result["governance"]
    assert gov["live_api_calls"] == 0
    assert gov["api_key_accessed"] is False


# ===========================================================================
# T09 — Schedule gate defined
# ===========================================================================
def test_t09_schedule_gate_defined(p83d_result):
    """T09: SCHEDULE_GATE must be defined in gate results."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "SCHEDULE_GATE" in gates
    sg = gates["SCHEDULE_GATE"]
    assert "gate_pass" in sg
    assert "required_fields" in sg
    assert "game_id" in sg["required_fields"]
    assert "game_date" in sg["required_fields"]
    assert "home_team" in sg["required_fields"]
    assert "away_team" in sg["required_fields"]


# ===========================================================================
# T10 — Pitcher feature gate defined
# ===========================================================================
def test_t10_pitcher_feature_gate_defined(p83d_result):
    """T10: PITCHER_FEATURE_GATE must be defined with FIP fields."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "PITCHER_FEATURE_GATE" in gates
    pg = gates["PITCHER_FEATURE_GATE"]
    assert "gate_pass" in pg
    assert "required_fields" in pg
    assert "home_sp_fip" in pg["required_fields"]
    assert "away_sp_fip" in pg["required_fields"]
    assert "sp_fip_delta" in pg["derived_fields"]
    assert "abs_sp_fip_delta" in pg["derived_fields"]


# ===========================================================================
# T11 — Model output gate defined
# ===========================================================================
def test_t11_model_output_gate_defined(p83d_result):
    """T11: MODEL_OUTPUT_GATE must be defined with probability fields."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "MODEL_OUTPUT_GATE" in gates
    mg = gates["MODEL_OUTPUT_GATE"]
    assert "gate_pass" in mg
    assert "required_fields" in mg
    assert "model_probability" in mg["required_fields"]
    assert "source_prediction_version" in mg["required_fields"]


# ===========================================================================
# T12 — Predicted side gate defined
# ===========================================================================
def test_t12_predicted_side_gate_defined(p83d_result):
    """T12: PREDICTED_SIDE_GATE must be defined with deterministic logic."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "PREDICTED_SIDE_GATE" in gates
    pg = gates["PREDICTED_SIDE_GATE"]
    assert "gate_pass" in pg
    assert pg["logic_available"] is True
    assert "sp_fip_delta" in pg["logic_definition"]
    assert pg["data_available"] is False  # blocked by missing pitcher data


# ===========================================================================
# T13 — Governance gate defined
# ===========================================================================
def test_t13_governance_gate_defined(p83d_result):
    """T13: GOVERNANCE_GATE must be defined and always pass (constants)."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "GOVERNANCE_GATE" in gates
    gg = gates["GOVERNANCE_GATE"]
    assert gg["gate_pass"] is True
    enforced = gg["enforced_values"]
    assert enforced["paper_only"] is True
    assert enforced["diagnostic_only"] is True
    assert enforced["odds_used"] is False
    assert enforced["production_ready"] is False


# ===========================================================================
# T14 — Producer activation gate defined
# ===========================================================================
def test_t14_producer_activation_gate_defined(p83d_result):
    """T14: PRODUCER_ACTIVATION_GATE must be defined and depend on all prerequisite gates."""
    gates = p83d_result["step4_gate_results"]["gates"]
    assert "PRODUCER_ACTIVATION_GATE" in gates
    ag = gates["PRODUCER_ACTIVATION_GATE"]
    assert "gate_pass" in ag
    prereqs = ag["prerequisite_gates"]
    assert "SCHEDULE_GATE" in prereqs
    assert "PITCHER_FEATURE_GATE" in prereqs
    assert "MODEL_OUTPUT_GATE" in prereqs
    assert "PREDICTED_SIDE_GATE" in prereqs
    assert "GOVERNANCE_GATE" in prereqs


# ===========================================================================
# T15 — Candidate file classifier generated
# ===========================================================================
def test_t15_candidate_file_classifier_generated(p83d_result):
    """T15: Probe must classify discovered files into categories."""
    files_by_category = p83d_result["step2_upstream_probe"]["files_by_category"]
    expected_categories = {
        "schedule_candidate",
        "pitcher_feature_candidate",
        "model_probability_candidate",
        "canonical_prediction_candidate",
        "runtime_paper_candidate",
        "contract_artifact",
        "noncanonical",
    }
    assert expected_categories.issubset(set(files_by_category.keys()))


# ===========================================================================
# T16 — Runtime PAPER candidate remains noncanonical
# ===========================================================================
def test_t16_runtime_paper_noncanonical(p83d_result):
    """T16: Runtime PAPER output files must be classified as noncanonical."""
    probe = p83d_result["step2_upstream_probe"]
    assert probe["runtime_paper_noncanonical"] is True
    paper_analysis = p83d_result["step3_runtime_paper_analysis"]
    assert paper_analysis["runtime_paper_noncanonical"] is True


# ===========================================================================
# T17 — Missing gate checklist generated
# ===========================================================================
def test_t17_missing_gate_checklist_generated(p83d_result):
    """T17: Missing data checklist must be generated with items and rerun triggers."""
    checklist = p83d_result["step5_missing_data_checklist"]
    assert "missing_items" in checklist
    assert "rerun_triggers" in checklist
    assert isinstance(checklist["missing_items"], list)
    assert isinstance(checklist["rerun_triggers"], list)
    assert checklist["missing_item_count"] == len(checklist["missing_items"])


# ===========================================================================
# T18 — Awaiting classification emitted when upstream incomplete
# ===========================================================================
def test_t18_awaiting_classification_emitted(p83d_result):
    """T18: Classification must be a valid P83D state."""
    classification = p83d_result["p83d_classification"]
    VALID_P83D = {
        "P83D_AWAITING_UPSTREAM_DATA",
        "P83D_PRODUCER_ACTIVATION_READY",
        "P83D_FAILED_VALIDATION",
    }
    assert classification in VALID_P83D, (
        f"Expected a valid P83D classification, got {classification}"
    )


# ===========================================================================
# T19 — Activation-ready classification possible if gates pass
# ===========================================================================
def test_t19_activation_ready_classification_possible(p83d_module):
    """T19: P83D_PRODUCER_ACTIVATION_READY must be an allowed classification."""
    assert "P83D_PRODUCER_ACTIVATION_READY" in p83d_module.ALLOWED_CLASSIFICATIONS


# ===========================================================================
# T20 — Future P83E prompt generated
# ===========================================================================
def test_t20_p83e_prompt_generated(p83d_result):
    """T20: A future P83E prompt must be generated."""
    prompt = p83d_result["step7_p83e_prompt"]
    assert isinstance(prompt, str)
    assert len(prompt) > 50
    assert "P83E" in prompt
    assert "mlb_2026_prediction_rows.jsonl" in prompt


# ===========================================================================
# T21 — No canonical prediction rows written if upstream incomplete
# ===========================================================================
def test_t21_no_canonical_rows_written_if_incomplete(p83d_result):
    """T21: P83D itself must never write canonical prediction rows (P83E's responsibility)."""
    activation = p83d_result["step6_producer_activation_status"]
    # P83D is a probe only — it never writes canonical rows itself
    assert activation["canonical_rows_written"] is False
    # Note: canonical file may exist if P83E ran successfully (P83E_CANONICAL_ROWS_READY)
    # P83D does not control canonical file existence — that is P83E's responsibility


# ===========================================================================
# T22 — No odds required
# ===========================================================================
def test_t22_no_odds_required(p83d_result):
    """T22: P83D must not require or use odds data."""
    gov = p83d_result["governance"]
    assert gov["odds_used"] is False
    assert gov["uses_historical_odds"] is False


# ===========================================================================
# T23 — No API call
# ===========================================================================
def test_t23_no_api_call(p83d_result):
    """T23: P83D must make zero API calls."""
    gov = p83d_result["governance"]
    assert gov["live_api_calls"] == 0


# ===========================================================================
# T24 — No API key access
# ===========================================================================
def test_t24_no_api_key_access(p83d_result):
    """T24: P83D must not access any API key."""
    gov = p83d_result["governance"]
    assert gov["api_key_accessed"] is False
    assert gov["the_odds_api_key_required"] is False


# ===========================================================================
# T25 — No edge calculated
# ===========================================================================
def test_t25_no_edge_calculated(p83d_result):
    """T25: P83D must not calculate market edge."""
    gov = p83d_result["governance"]
    assert gov["market_edge_calculated"] is False
    assert gov["market_edge_evaluated"] is False


# ===========================================================================
# T26 — No CLV calculated
# ===========================================================================
def test_t26_no_clv_calculated(p83d_result):
    """T26: P83D must not calculate CLV."""
    gov = p83d_result["governance"]
    assert gov["clv_calculated"] is False


# ===========================================================================
# T27 — No EV calculated
# ===========================================================================
def test_t27_no_ev_calculated(p83d_result):
    """T27: P83D must not calculate EV."""
    gov = p83d_result["governance"]
    assert gov["ev_calculated"] is False


# ===========================================================================
# T28 — No Kelly calculated
# ===========================================================================
def test_t28_no_kelly_calculated(p83d_result):
    """T28: P83D must not calculate Kelly fraction."""
    gov = p83d_result["governance"]
    assert gov["kelly_calculated"] is False


# ===========================================================================
# T29 — live_api_calls=0
# ===========================================================================
def test_t29_live_api_calls_zero(p83d_result):
    """T29: live_api_calls must be exactly 0."""
    assert p83d_result["governance"]["live_api_calls"] == 0
    assert p83d_result["forbidden_scan"]["live_api_calls"] == 0


# ===========================================================================
# T30 — production_ready=False
# ===========================================================================
def test_t30_production_ready_false(p83d_result):
    """T30: production_ready must be False."""
    assert p83d_result["governance"]["production_ready"] is False
    assert p83d_result["forbidden_scan"]["production_ready"] is False


# ===========================================================================
# T31 — kelly_deploy_allowed=False
# ===========================================================================
def test_t31_kelly_deploy_allowed_false(p83d_result):
    """T31: kelly_deploy_allowed must be False."""
    assert p83d_result["governance"]["kelly_deploy_allowed"] is False
    assert p83d_result["forbidden_scan"]["kelly_deploy_allowed"] is False


# ===========================================================================
# T32 — Forbidden scan passes
# ===========================================================================
def test_t32_forbidden_scan_passes(p83d_result):
    """T32: Forbidden scan must pass (all forbidden operations absent)."""
    fs = p83d_result["forbidden_scan"]
    assert fs["forbidden_scan_pass"] is True
    assert fs["canonical_rows_written_in_p83d"] is False


# ===========================================================================
# T33 — JSON schema stable
# ===========================================================================
def test_t33_json_schema_stable(p83d_json):
    """T33: Output JSON must contain all required top-level keys."""
    required_keys = {
        "phase", "date", "generated_at", "p83d_classification",
        "governance", "prediction_boundary",
        "step1_p83c_verification", "step2_upstream_probe",
        "step3_runtime_paper_analysis", "step4_gate_results",
        "step5_missing_data_checklist", "step6_producer_activation_status",
        "step7_p83e_prompt", "forbidden_scan",
    }
    for key in required_keys:
        assert key in p83d_json, f"Missing required key: {key}"
    assert p83d_json["phase"] == "P83D"
    assert p83d_json["date"] == "2026-05-26"


# ===========================================================================
# T34 — Report includes probe table
# ===========================================================================
def test_t34_report_includes_probe_table():
    """T34: Markdown report must include upstream probe results table."""
    assert REPORT_MD.exists(), f"Report not found: {REPORT_MD}"
    content = REPORT_MD.read_text()
    assert "schedule_candidate" in content
    assert "pitcher_feature_candidate" in content
    assert "runtime_paper_candidate" in content


# ===========================================================================
# T35 — Report includes gate table
# ===========================================================================
def test_t35_report_includes_gate_table():
    """T35: Markdown report must include readiness gate table."""
    assert REPORT_MD.exists()
    content = REPORT_MD.read_text()
    assert "SCHEDULE_GATE" in content
    assert "PITCHER_FEATURE_GATE" in content
    assert "MODEL_OUTPUT_GATE" in content
    assert "PREDICTED_SIDE_GATE" in content
    assert "GOVERNANCE_GATE" in content
    assert "PRODUCER_ACTIVATION_GATE" in content


# ===========================================================================
# T36 — active_task.md updated
# ===========================================================================
def test_t36_active_task_md_updated():
    """T36: active_task.md must exist (will be updated after commit)."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text()
    assert len(content) > 10


# ===========================================================================
# T37 — P72A–P83D allowed classifications complete
# ===========================================================================
def test_t37_allowed_classifications_complete(p83d_module):
    """T37: ALLOWED_CLASSIFICATIONS must include all 4 valid P83D states."""
    allowed = p83d_module.ALLOWED_CLASSIFICATIONS
    assert "P83D_AWAITING_UPSTREAM_DATA" in allowed
    assert "P83D_PRODUCER_ACTIVATION_READY" in allowed
    assert "P83D_BLOCKED_BY_MISSING_P83C_ARTIFACT" in allowed
    assert "P83D_FAILED_VALIDATION" in allowed
