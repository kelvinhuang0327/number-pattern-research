"""Tests for P246 BIG_LOTTO data-integrity audit artifact.

Verifies: JSON parses, required fields, read_only_confirmed, forbidden actions,
classification language, anomaly != predictor, quarantine authorization,
row-family count consistency, gate state.
"""
import json
import os
import sys

import pytest

ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__),
    "..", "outputs", "research",
    "p246_big_lotto_data_integrity_audit_20260605.json"
)
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__),
    "..", "outputs", "research",
    "p246_big_lotto_data_integrity_audit_20260605.md"
)

REQUIRED_FORBIDDEN = [
    "DB write",
    "registry mutation",
    "production recommendation change",
    "controlled_apply",
    "strategy promotion",
    "betting advice",
]


@pytest.fixture(scope="module")
def data():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report():
    with open(ARTIFACT_MD) as f:
        return f.read()


# --- JSON integrity -----------------------------------------------------------

def test_json_parses(data):
    assert isinstance(data, dict)


def test_required_fields_present(data):
    required = [
        "schema_version", "task_id", "classification", "db_path",
        "read_only_confirmed", "input_artifacts_verified", "total_big_lotto_rows",
        "canonical_plausible_estimate", "contaminated_rows", "contamination_pct",
        "row_family_counts", "row_family_percentages", "quarantine_plan",
        "allowed_actions", "forbidden_actions", "required_authorization_for_apply",
        "final_decision", "anomaly_is_not_predictor",
    ]
    for f in required:
        assert f in data, f"Missing required field: {f!r}"


def test_task_id(data):
    assert data["task_id"] == "P246"


def test_schema_version(data):
    assert data["schema_version"] == "1.0"


# --- Read-only confirmation ---------------------------------------------------

def test_read_only_confirmed(data):
    assert data["read_only_confirmed"] is True


def test_db_path_present(data):
    assert data["db_path"] and "lottery_v2.db" in data["db_path"]


# --- Forbidden actions --------------------------------------------------------

def test_forbidden_actions_present(data):
    fa = " ".join(data.get("forbidden_actions", [])).lower()
    for req in REQUIRED_FORBIDDEN:
        assert req.lower() in fa, f"Required forbidden action missing: {req!r}"


def test_forbidden_includes_gate_open(data):
    fa = " ".join(data.get("forbidden_actions", [])).lower()
    assert "gate_open" in fa or "gate open" in fa or "promotion" in fa


# --- Classification language --------------------------------------------------

def test_classification_is_integrity_not_edge(data):
    cls = data["classification"].lower()
    assert "integrity" in cls or "contamination" in cls or "audit" in cls, \
        "Classification must reference data-integrity / contamination"
    assert "predictive_edge" not in cls and "edge_found" not in cls, \
        "Classification must not claim a predictive edge"


def test_gate_red_confirmed(data):
    assert data.get("current_gate_state") == "GATE_RED_DATA_CONTAMINATION"


# --- Anomaly is not predictor -----------------------------------------------

def test_anomaly_not_predictor_json(data):
    assert data.get("anomaly_is_not_predictor") is True


def test_anomaly_not_predictor_report(report):
    assert "anomaly is not predictor" in report.lower() or \
           "anomaly is NOT predictor" in report, \
        "Report must contain 'anomaly is not predictor' language"


def test_no_p_win_claim(report):
    text = report.lower()
    assert "p(win)" not in text or "no exploitable edge" in text or \
           "not an edge" in text, \
        "Report must not claim P(win) improvement"


# --- Quarantine authorization ------------------------------------------------

def test_quarantine_requires_authorization(data):
    auth = data.get("required_authorization_for_apply", "").lower()
    assert "type d" in auth or "human gate" in auth or "explicit" in auth, \
        "required_authorization_for_apply must mention Type D / explicit authorization"


def test_quarantine_plan_has_phases(data):
    qp = data.get("quarantine_plan", {})
    assert "phase_1_backup" in qp
    assert "phase_2_quarantine_table" in qp
    assert "phase_3_verification" in qp


def test_quarantine_plan_auth_on_phases(data):
    qp = data["quarantine_plan"]
    for phase in ["phase_1_backup", "phase_2_quarantine_table", "phase_3_verification"]:
        auth = str(qp[phase].get("authorization", "")).lower()
        assert "type d" in auth or "human gate" in auth or "explicit" in auth, \
            f"{phase} must require explicit authorization"


def test_quarantine_plan_does_not_authorize_strategy(data):
    what_not = " ".join(data["quarantine_plan"].get("what_this_does_not_authorize", [])).lower()
    assert "strategy" in what_not or "prediction" in what_not


# --- Row-family counts -------------------------------------------------------

def test_row_family_counts_sum_to_total(data):
    total = data["total_big_lotto_rows"]
    counts_sum = sum(data["row_family_counts"].values())
    assert counts_sum == total, \
        f"row_family_counts sum {counts_sum} != total {total}"


def test_canonical_plausible_near_governance_expected(data):
    canonical = data["canonical_plausible_estimate"]
    expected = data["governance_expected_draws"]
    # Allow ±50 tolerance (small draws may differ due to recency)
    assert abs(canonical - expected) <= 50, \
        f"Canonical count {canonical} differs from governance expected {expected} by more than 50"


def test_contamination_families_present(data):
    fc = data["row_family_counts"]
    assert "SIM_HYPHEN" in fc, "SIM_HYPHEN family must be identified"
    assert "DATE_FORMAT_ALIEN" in fc, "DATE_FORMAT_ALIEN family must be identified"
    assert "SMALL_POOL_ALIEN" in fc, "SMALL_POOL_ALIEN family must be identified"
    assert "CANONICAL_PLAUSIBLE" in fc, "CANONICAL_PLAUSIBLE family must be present"


def test_contamination_is_majority(data):
    """BIG_LOTTO should be >80% contaminated per P219 finding."""
    assert data["contamination_pct"] >= 80.0, \
        f"Expected contamination >= 80%, got {data['contamination_pct']}%"


# --- P219 linkage -----------------------------------------------------------

def test_p219_signal_explanation_present(data):
    exp = data.get("p219_signal_explanation", {})
    assert "conclusion" in exp
    assert "not" in exp["conclusion"].lower() or "anomaly" in exp["conclusion"].lower()


def test_input_artifacts_cite_p219(data):
    verified = " ".join(data.get("input_artifacts_verified", []))
    assert "P219" in verified


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
