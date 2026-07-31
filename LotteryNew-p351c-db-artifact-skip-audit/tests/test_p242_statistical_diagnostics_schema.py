"""
Targeted tests for P242 statistical diagnostics schema module.
Validates module purity, safety defaults, schema completeness, and NIST semantics.
No DB access. No production side effects.
"""
import importlib
import inspect
import json
import os
import pytest

import lottery_api.diagnostics.statistical_diagnostics_schema as schema_mod
from lottery_api.diagnostics.statistical_diagnostics_schema import (
    REQUIRED_SCHEMA_FIELDS,
    LotteryType,
    LifecycleStatus,
    CorrectionMethod,
    PsiStatus,
    NistAlertLevel,
    DriftGuardResult,
    TaskType,
    build_diagnostic_report,
    validate_diagnostic_report,
    default_safety_fields,
    classify_nist_alert,
)

JSON_PATH = "outputs/research/p242_statistical_diagnostics_schema_implementation_20260605.json"
MD_PATH = "outputs/research/p242_statistical_diagnostics_schema_implementation_20260605.md"

P241B_CORE_FIELDS = [
    "task_id", "report_date", "lottery_type", "strategy_id", "diagnostic_subject",
    "lifecycle_status", "sample_size", "window_definition", "is_oos", "split_boundary",
    "family_size_k", "baseline_method", "baseline_value", "observed_metric",
    "delta_vs_baseline", "n_blocks", "blocks_above_baseline", "p_value_raw",
    "correction_method", "corrected_threshold", "is_corrected_significant",
    "mc_null_99th_pct", "is_above_mc_noise_floor", "robustness_check_description",
    "robustness_metric", "robustness_sign_stable", "drift_guard_result",
    "psi_value", "psi_status", "feature_bottleneck", "min_detectable_effect",
    "power_at_observed_effect", "overfit_ratio", "classification",
    "blocker_classification", "allowed_next_action", "forbidden_next_action",
    "confidence_language", "human_review_required", "db_write_authorized",
    "registry_write_authorized", "production_authorized", "betting_advice",
    "nist_alert_level",
]

_MINIMAL_VALID_REPORT = {
    "task_id": "TEST",
    "report_date": "2026-06-05",
    "lottery_type": LotteryType.DAILY_539,
    "strategy_id": "test_strategy",
    "diagnostic_subject": "unit test",
    "lifecycle_status": LifecycleStatus.OBSERVATION,
    "sample_size": 1500,
    "window_definition": "full_1500",
    "is_oos": True,
    "split_boundary": "99000001",
    "family_size_k": 1,
    "baseline_method": "theoretical",
    "baseline_value": 0.641,
    "observed_metric": 0.650,
    "delta_vs_baseline": 0.009,
    "n_blocks": 5,
    "blocks_above_baseline": 3,
    "p_value_raw": 0.12,
    "correction_method": CorrectionMethod.BONFERRONI,
    "corrected_threshold": 0.05,
    "is_corrected_significant": False,
    "mc_null_99th_pct": 0.008,
    "is_above_mc_noise_floor": False,
    "robustness_check_description": "exclude hit>=3",
    "robustness_metric": 0.638,
    "robustness_sign_stable": False,
    "drift_guard_result": DriftGuardResult.PASS,
    "psi_value": 0.09,
    "psi_status": PsiStatus.STABLE,
    "feature_bottleneck": "sample_too_small",
    "min_detectable_effect": 0.008,
    "power_at_observed_effect": 0.35,
    "overfit_ratio": 1.1,
    "classification": "WAIT_FOR_OOS",
    "blocker_classification": "P221F_GATE_NOT_PASSED",
    "allowed_next_action": ["passive_monitoring"],
    "forbidden_next_action": ["strategy_promotion", "db_write"],
    "confidence_language": "Historical evidence only; not a betting recommendation.",
    "human_review_required": False,
    "db_write_authorized": False,
    "registry_write_authorized": False,
    "production_authorized": False,
    "betting_advice": False,
    "nist_alert_level": NistAlertLevel.NOT_RUN,
}


# ---------------------------------------------------------------------------
# Module purity tests
# ---------------------------------------------------------------------------

def test_module_imports():
    assert schema_mod is not None


def test_no_sqlite_import():
    source = inspect.getsource(schema_mod)
    assert "import sqlite" not in source
    assert "sqlite3" not in source


def test_no_db_path_string():
    source = inspect.getsource(schema_mod)
    assert "lottery_v2.db" not in source
    assert "lottery.db" not in source


def test_no_network_imports():
    source = inspect.getsource(schema_mod)
    for net_mod in ("requests", "urllib", "httpx", "aiohttp", "socket"):
        assert net_mod not in source, f"Found network import: {net_mod}"


def test_no_production_registry_import():
    source = inspect.getsource(schema_mod)
    assert "replay_strategy_registry" not in source
    # Check for import statement (not field name substrings)
    assert "import controlled_apply" not in source
    assert "from controlled_apply" not in source


# ---------------------------------------------------------------------------
# Schema fields
# ---------------------------------------------------------------------------

def test_required_fields_include_all_p241b_core():
    for field in P241B_CORE_FIELDS:
        assert field in REQUIRED_SCHEMA_FIELDS, f"Missing core P241B field: {field}"


def test_required_fields_is_non_empty():
    assert len(REQUIRED_SCHEMA_FIELDS) >= 43


# ---------------------------------------------------------------------------
# default_safety_fields
# ---------------------------------------------------------------------------

def test_default_safety_fields_all_false():
    safety = default_safety_fields()
    for field, val in safety.items():
        assert val is False, f"Safety field '{field}' should be False, got {val!r}"


def test_default_safety_fields_includes_critical():
    safety = default_safety_fields()
    for field in ("db_write_authorized", "registry_write_authorized",
                  "production_authorized", "betting_advice"):
        assert field in safety


# ---------------------------------------------------------------------------
# build_diagnostic_report
# ---------------------------------------------------------------------------

def test_build_report_from_valid_inputs():
    report = build_diagnostic_report(**_MINIMAL_VALID_REPORT)
    assert isinstance(report, dict)
    assert report["task_id"] == "TEST"


def test_build_report_safety_defaults_applied():
    report = build_diagnostic_report(task_id="X", report_date="2026-06-05")
    assert report["db_write_authorized"] is False
    assert report["production_authorized"] is False
    assert report["betting_advice"] is False


def test_build_report_raises_on_db_write_true():
    with pytest.raises(ValueError, match="db_write_authorized"):
        build_diagnostic_report(db_write_authorized=True)


def test_build_report_raises_on_registry_write_true():
    with pytest.raises(ValueError, match="registry_write_authorized"):
        build_diagnostic_report(registry_write_authorized=True)


def test_build_report_raises_on_production_true():
    with pytest.raises(ValueError, match="production_authorized"):
        build_diagnostic_report(production_authorized=True)


def test_build_report_raises_on_betting_advice_true():
    with pytest.raises(ValueError, match="betting_advice"):
        build_diagnostic_report(betting_advice=True)


def test_build_report_auto_delta():
    report = build_diagnostic_report(
        task_id="X", baseline_value=0.64, observed_metric=0.66
    )
    assert abs(report["delta_vs_baseline"] - 0.02) < 1e-9


# ---------------------------------------------------------------------------
# validate_diagnostic_report
# ---------------------------------------------------------------------------

def test_validate_valid_report():
    ok, errors = validate_diagnostic_report(_MINIMAL_VALID_REPORT)
    assert ok is True, f"Unexpected errors: {errors}"
    assert errors == []


def test_validate_fails_missing_field():
    bad = dict(_MINIMAL_VALID_REPORT)
    del bad["sample_size"]
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("sample_size" in e for e in errors)


def test_validate_fails_db_write_true():
    bad = dict(_MINIMAL_VALID_REPORT, db_write_authorized=True)
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("db_write_authorized" in e for e in errors)


def test_validate_fails_registry_write_true():
    bad = dict(_MINIMAL_VALID_REPORT, registry_write_authorized=True)
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("registry_write_authorized" in e for e in errors)


def test_validate_fails_production_true():
    bad = dict(_MINIMAL_VALID_REPORT, production_authorized=True)
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("production_authorized" in e for e in errors)


def test_validate_fails_betting_advice_true():
    bad = dict(_MINIMAL_VALID_REPORT, betting_advice=True)
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("betting_advice" in e for e in errors)


def test_validate_yellow_prediction_edge_language_fails():
    bad = dict(
        _MINIMAL_VALID_REPORT,
        nist_alert_level=NistAlertLevel.YELLOW,
        confidence_language="This prediction edge is now confirmed.",
    )
    ok, errors = validate_diagnostic_report(bad)
    assert ok is False
    assert any("prediction edge" in e for e in errors)


# ---------------------------------------------------------------------------
# classify_nist_alert
# ---------------------------------------------------------------------------

def test_classify_yellow_observation_only():
    result = classify_nist_alert(NistAlertLevel.YELLOW)
    assert result["strategy_authorized"] is False
    assert result["production_authorized"] is False
    assert result["betting_advice"] is False
    assert result["db_write_authorized"] is False
    assert "observation" in result["interpretation"].lower()


def test_classify_red_human_review_only():
    result = classify_nist_alert(NistAlertLevel.RED)
    assert result["strategy_authorized"] is False
    assert result["production_authorized"] is False
    assert result["betting_advice"] is False
    assert result["human_review_required"] is True
    assert "human" in result["interpretation"].lower()


def test_classify_green_no_review_required():
    result = classify_nist_alert(NistAlertLevel.GREEN)
    assert result["human_review_required"] is False
    assert result["strategy_authorized"] is False


def test_classify_invalid_level_raises():
    with pytest.raises(ValueError):
        classify_nist_alert("PURPLE")


def test_all_nist_levels_no_strategy_auth():
    for level in NistAlertLevel.ALL:
        result = classify_nist_alert(level)
        assert result["strategy_authorized"] is False, f"Level {level} must not authorize strategy"
        assert result["production_authorized"] is False
        assert result["betting_advice"] is False


# ---------------------------------------------------------------------------
# Artifact validation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def json_artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


def test_json_artifact_exists():
    assert os.path.exists(JSON_PATH), f"JSON artifact missing: {JSON_PATH}"


def test_markdown_artifact_exists():
    assert os.path.exists(MD_PATH), f"Markdown artifact missing: {MD_PATH}"


def test_json_artifact_classification(json_artifact):
    assert json_artifact["classification"] == "P242_READ_ONLY_STATISTICAL_DIAGNOSTICS_SCHEMA_IMPLEMENTATION_COMPLETE"


def test_json_artifact_task_type(json_artifact):
    assert json_artifact["task_type"] == "Type C"


def test_json_artifact_no_db_import(json_artifact):
    assert json_artifact["no_db_import"] is True


def test_json_artifact_no_db_write(json_artifact):
    assert json_artifact["no_db_write"] is True


def test_json_artifact_no_registry_mutation(json_artifact):
    assert json_artifact["no_registry_mutation"] is True


def test_json_artifact_no_production_change(json_artifact):
    assert json_artifact["no_production_change"] is True


def test_json_artifact_no_betting_advice(json_artifact):
    assert json_artifact["no_betting_advice"] is True


def test_json_artifact_p211_not_restarted(json_artifact):
    assert json_artifact["p211_restarted"] is False


def test_json_artifact_p238b_interpretation(json_artifact):
    assert "YELLOW" in json_artifact["p238b_interpretation"]


def test_markdown_no_db_write(json_artifact):
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "no db write" in content or "no database write" in content or "db_write_authorized" in content


def test_markdown_no_betting_advice(json_artifact):
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "betting advice" in content


def test_markdown_type_c_classification():
    with open(MD_PATH) as f:
        content = f.read().lower()
    assert "type c" in content
