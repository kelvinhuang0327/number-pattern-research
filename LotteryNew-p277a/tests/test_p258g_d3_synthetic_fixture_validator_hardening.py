"""
P258G — D3 synthetic-fixture-only contract validator hardening.

Validates hardened synthetic fixtures only:
- complete synthetic contracts pass
- every required missing/invalid field case fails deterministically
- forbidden statuses stay forbidden and allowed statuses stay exactly two
- validators remain pure/read-only and import no forbidden execution paths
- no real candidate methods, null generation, p-values, paired tests, or
  backtests are introduced
"""

import ast
import json
import os
from dataclasses import replace

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
VALIDATION_PY = os.path.join(
    REPO_ROOT, "lottery_api", "research", "d3_gate", "gate_validation.py"
)
SCHEMAS_PY = os.path.join(REPO_ROOT, "lottery_api", "research", "d3_gate", "schemas.py")
ARTIFACT_JSON = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258g_d3_synthetic_fixture_validator_hardening_20260608.json",
)
ARTIFACT_MD = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258g_d3_synthetic_fixture_validator_hardening_20260608.md",
)

FORBIDDEN_IMPORT_SUBSTRINGS = [
    "sqlite3",
    "sqlalchemy",
    "database",
    "recommend",
    "registry",
    "controlled_apply",
    "controlled_application",
    "deployment",
    "production",
    "backtest",
    "fetcher",
    "engine",
    "requests",
    "urllib",
]


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _imported_modules(path):
    tree = ast.parse(_read(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def candidate():
    from lottery_api.research.d3_gate.schemas import CandidateInput

    return CandidateInput(
        candidate_id="synthetic_candidate_v2",
        lottery_type="POWER_LOTTO",
        target_draw_id="115000046",
        target_draw_date="2026-06-09",
        n_bet_count=3,
        numbers_per_bet=6,
        feature_dimensionality=12,
        regime_count_or_parameter_count=4,
        window_schedule="short_mid_long",
        generated_at="2026-06-08T18:00:00",
        available_information_cutoff="2026-06-08T12:00:00",
        random_seed=258,
        source_artifact_path="outputs/research/synthetic_candidate_v2.json",
        provenance_digest="sha256:synthetic-v2",
    )


@pytest.fixture()
def baseline(candidate):
    from lottery_api.research.d3_gate.schemas import P257ABaselineInput

    return P257ABaselineInput(
        baseline_id="p257a_best_n_bet_v2",
        lottery_type=candidate.lottery_type,
        target_draw_id=candidate.target_draw_id,
        n_bet_count=candidate.n_bet_count,
        source_artifact_path="outputs/research/p257a_baseline_v2.json",
        baseline_digest="sha256:baseline-v2",
    )


@pytest.fixture()
def null_family(candidate):
    from lottery_api.research.d3_gate.schemas import MatchedNullFamily

    return MatchedNullFamily(
        null_family_id="synthetic_matched_null_v2",
        matched_lottery_type=candidate.lottery_type,
        matched_n_bet_count=candidate.n_bet_count,
        matched_numbers_per_bet=candidate.numbers_per_bet,
        matched_window_schedule=candidate.window_schedule,
        matched_feature_dimensionality=candidate.feature_dimensionality,
        matched_regime_or_parameter_count=candidate.regime_count_or_parameter_count,
        null_generation_seed=259,
        null_count=1000,
        source_artifact_path="outputs/research/synthetic_null_v2.json",
    )


@pytest.fixture()
def correction_family():
    return {
        "candidate_methods": ["synthetic_candidate_v2"],
        "null_variants": ["matched_binomial"],
        "lottery_types": ["POWER_LOTTO"],
        "n_bet_counts": [3],
        "metrics": ["paired_win_rate", "null_percentile"],
        "windows": ["short", "mid", "long"],
    }


def _candidate_dict(candidate, **overrides):
    data = dict(candidate.__dict__)
    data.update(overrides)
    return data


def _baseline_dict(baseline, **overrides):
    data = dict(baseline.__dict__)
    data.update(overrides)
    return data


def _null_dict(null_family, **overrides):
    data = dict(null_family.__dict__)
    data.update(overrides)
    return data


def _correction_family_dict(correction_family, **overrides):
    data = dict(correction_family)
    data.update(overrides)
    return data


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258G_D3_SYNTHETIC_FIXTURE_VALIDATOR_HARDENING_READY"


def test_valid_synthetic_fixtures_pass(candidate, baseline, null_family, correction_family):
    from lottery_api.research.d3_gate.gate_validation import (
        validate_candidate_provenance_contract,
        validate_correction_family_contract,
        validate_matched_null_family_contract,
        validate_no_approval_status_contract,
        validate_p257a_baseline_contract,
        validate_timestamp_cutoff_contract,
    )
    from lottery_api.research.d3_gate.schemas import GateOutput, GateStatus

    assert validate_candidate_provenance_contract(candidate).validator == "candidate_provenance"
    assert validate_timestamp_cutoff_contract(candidate).validator == "timestamp_cutoff"
    assert validate_p257a_baseline_contract(candidate, baseline).validator == "p257a_baseline"
    assert validate_matched_null_family_contract(candidate, null_family).validator == "matched_null_family"
    assert validate_correction_family_contract(correction_family).validator == "correction_family"
    assert validate_no_approval_status_contract(
        GateOutput(gate_decision=GateStatus.NOT_YET_REJECTED)
    ).validator == "no_approval_status"


@pytest.mark.parametrize(
    "field_name",
    [
        "candidate_id",
        "lottery_type",
        "target_draw_id",
        "target_draw_date",
        "n_bet_count",
        "numbers_per_bet",
        "feature_dimensionality",
        "regime_count_or_parameter_count",
        "random_seed",
    ],
)
def test_candidate_provenance_required_fields_missing_fail(candidate, field_name):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_candidate_provenance_contract,
    )

    bad = _candidate_dict(candidate)
    bad.pop(field_name)
    with pytest.raises(ContractValidationError, match=field_name):
        validate_candidate_provenance_contract(bad)


@pytest.mark.parametrize(
    "field_name, value",
    [
        ("n_bet_count", 0),
        ("numbers_per_bet", 0),
        ("feature_dimensionality", 0),
        ("regime_count_or_parameter_count", 0),
        ("n_bet_count", -1),
        ("numbers_per_bet", -3),
        ("feature_dimensionality", -5),
        ("regime_count_or_parameter_count", -8),
        ("random_seed", "not-an-int"),
    ],
)
def test_candidate_provenance_invalid_numeric_fields_fail(candidate, field_name, value):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_candidate_provenance_contract,
    )

    bad = _candidate_dict(candidate, **{field_name: value})
    with pytest.raises(ContractValidationError, match=field_name):
        validate_candidate_provenance_contract(bad)

@pytest.mark.parametrize(
    "field_name, value, match",
    [
        ("generated_at", "2026-06-08T11:59:59", "after generated_at"),
        ("available_information_cutoff", "2026-06-09T00:00:00", "precede target_draw_date"),
        ("available_information_cutoff", "not-a-timestamp", "invalid temporal field"),
    ],
)
def test_timestamp_cutoff_edge_cases_fail(candidate, field_name, value, match):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_timestamp_cutoff_contract,
    )

    if field_name == "generated_at":
        bad = _candidate_dict(candidate, generated_at=value)
    elif value == "2026-06-09T00:00:00":
        bad = _candidate_dict(
            candidate,
            generated_at="2026-06-09T01:00:00",
            available_information_cutoff=value,
        )
    else:
        bad = _candidate_dict(candidate, available_information_cutoff=value)
    with pytest.raises(ContractValidationError, match=match):
        validate_timestamp_cutoff_contract(bad)


@pytest.mark.parametrize(
    "field_name",
    ["lottery_type", "target_draw_id", "n_bet_count"],
)
def test_baseline_alignment_mismatch_fails(candidate, baseline, field_name):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_p257a_baseline_contract,
    )

    overrides = {
        "lottery_type": "DAILY_539",
        "target_draw_id": "115000099",
        "n_bet_count": 1,
    }
    bad = _baseline_dict(baseline, **{field_name: overrides[field_name]})
    with pytest.raises(ContractValidationError, match=field_name):
        validate_p257a_baseline_contract(candidate, bad)


@pytest.mark.parametrize(
    "field_name",
    [
        "matched_lottery_type",
        "matched_n_bet_count",
        "matched_numbers_per_bet",
        "matched_window_schedule",
        "matched_feature_dimensionality",
        "matched_regime_or_parameter_count",
        "null_generation_seed",
        "null_count",
    ],
)
def test_matched_null_required_fields_missing_fail(candidate, null_family, field_name):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_matched_null_family_contract,
    )

    bad = _null_dict(null_family)
    bad.pop(field_name)
    with pytest.raises(ContractValidationError, match=field_name):
        validate_matched_null_family_contract(candidate, bad)


@pytest.mark.parametrize(
    "field_name, value, match",
    [
        ("matched_lottery_type", "DAILY_539", "matched_lottery_type"),
        ("matched_n_bet_count", 2, "matched_n_bet_count"),
        ("matched_numbers_per_bet", 5, "matched_numbers_per_bet"),
        ("matched_window_schedule", "mid_only", "matched_window_schedule"),
        ("matched_feature_dimensionality", 99, "matched_feature_dimensionality"),
        ("matched_regime_or_parameter_count", 99, "matched_regime_or_parameter_count"),
        ("null_count", 0, "positive"),
        ("null_count", -1, "positive"),
        ("null_generation_seed", "seed", "integer"),
    ],
)
def test_matched_null_alignment_and_metadata_fail(
    candidate, null_family, field_name, value, match
):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_matched_null_family_contract,
    )

    bad = _null_dict(null_family, **{field_name: value})
    with pytest.raises(ContractValidationError, match=match):
        validate_matched_null_family_contract(candidate, bad)


@pytest.mark.parametrize(
    "field_name",
    ["candidate_methods", "null_variants", "lottery_types", "n_bet_counts", "metrics", "windows"],
)
def test_correction_family_missing_declarations_fail(correction_family, field_name):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_correction_family_contract,
    )

    bad = _correction_family_dict(correction_family)
    bad.pop(field_name)
    with pytest.raises(ContractValidationError, match=field_name):
        validate_correction_family_contract(bad)


@pytest.mark.parametrize("forbidden", ["APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED"])
def test_forbidden_statuses_fail(forbidden):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )

    with pytest.raises(ContractValidationError, match=forbidden):
        validate_no_approval_status_contract({"gate_decision": forbidden})


def test_allowed_statuses_remain_exactly_two():
    from lottery_api.research.d3_gate.schemas import GateStatus

    assert {member.name for member in GateStatus} == {"REJECTED", "NOT_YET_REJECTED"}


def test_validators_remain_pure_and_forbidden_import_free():
    modules = " ".join(_imported_modules(VALIDATION_PY)).lower()
    for forbidden in FORBIDDEN_IMPORT_SUBSTRINGS:
        assert forbidden.lower() not in modules


def test_no_executable_gate_null_generation_or_statistical_surface():
    src = f"{_read(VALIDATION_PY)}\n{_read(SCHEMAS_PY)}".lower()
    banned_fragments = [
        "def run_gate",
        "def evaluate",
        "def run_backtest",
        "def score",
        "def generate_null",
        "def compute_p",
        "def paired",
        "for draw in",
        "scipy",
        "numpy",
        "random.",
    ]
    for banned in banned_fragments:
        assert banned not in src, f"banned execution surface found: {banned}"


def test_artifact_states_and_boundaries(artifact):
    assert artifact["no_real_candidate_methods_used"] is True
    assert artifact["no_real_candidate_methods_used_confirmed"] is True
    assert artifact["d3_is_not_a_prediction_model_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["not_yet_rejected_is_not_approval"] is True
    assert artifact["no_improved_accuracy_claim_confirmed"] is True
    assert artifact["next_allowed_task"]["task_id"] == "P258H"


def test_md_artifact_boundary_language():
    content = _read(ARTIFACT_MD).lower()
    assert "synthetic-fixture-only" in content
    assert "not approval" in content
    assert "no real candidate methods" in content
