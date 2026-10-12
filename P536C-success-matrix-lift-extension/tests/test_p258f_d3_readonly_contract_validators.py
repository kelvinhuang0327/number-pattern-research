"""
P258F — D3 read-only contract validator tests.

Validates contract-only behavior:
- synthetic complete contracts pass
- missing fields, timestamp violations, forbidden statuses, matched-null
  mismatches, and missing correction-family declarations fail deterministically
- validators remain pure/read-only and import no forbidden DB / recommendation /
  production / registry / controlled_apply / deployment paths
- no executable gate evaluation, null generation, p-value computation, paired
  statistical test, or backtest surface is introduced
"""

import ast
import json
import os

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
VALIDATION_PY = os.path.join(
    REPO_ROOT, "lottery_api", "research", "d3_gate", "gate_validation.py"
)
SCHEMAS_PY = os.path.join(
    REPO_ROOT, "lottery_api", "research", "d3_gate", "schemas.py"
)
ARTIFACT_JSON = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258f_d3_readonly_contract_validators_20260608.json",
)
ARTIFACT_MD = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258f_d3_readonly_contract_validators_20260608.md",
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
        candidate_id="synthetic_candidate",
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
        source_artifact_path="outputs/research/synthetic_candidate.json",
        provenance_digest="sha256:synthetic",
    )


@pytest.fixture()
def baseline(candidate):
    from lottery_api.research.d3_gate.schemas import P257ABaselineInput

    return P257ABaselineInput(
        baseline_id="p257a_best_n_bet",
        lottery_type=candidate.lottery_type,
        target_draw_id=candidate.target_draw_id,
        n_bet_count=candidate.n_bet_count,
        source_artifact_path="outputs/research/p257a_baseline.json",
        baseline_digest="sha256:baseline",
    )


@pytest.fixture()
def null_family(candidate):
    from lottery_api.research.d3_gate.schemas import MatchedNullFamily

    return MatchedNullFamily(
        null_family_id="synthetic_matched_null",
        matched_lottery_type=candidate.lottery_type,
        matched_n_bet_count=candidate.n_bet_count,
        matched_numbers_per_bet=candidate.numbers_per_bet,
        matched_window_schedule=candidate.window_schedule,
        matched_feature_dimensionality=candidate.feature_dimensionality,
        matched_regime_or_parameter_count=candidate.regime_count_or_parameter_count,
        null_generation_seed=259,
        null_count=1000,
        source_artifact_path="outputs/research/synthetic_null.json",
    )


@pytest.fixture()
def correction_family():
    return {
        "candidate_methods": ["synthetic_candidate"],
        "null_variants": ["matched_binomial"],
        "lottery_types": ["POWER_LOTTO"],
        "n_bet_counts": [3],
        "metrics": ["paired_win_rate", "null_percentile"],
        "windows": ["short", "mid", "long"],
    }


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258F_D3_READ_ONLY_CONTRACT_VALIDATORS_READY"


def test_validators_accept_complete_synthetic_contracts(
    candidate, baseline, null_family, correction_family
):
    from lottery_api.research.d3_gate.gate_validation import (
        validate_candidate_provenance_contract,
        validate_correction_family_contract,
        validate_matched_null_family_contract,
        validate_no_approval_status_contract,
        validate_p257a_baseline_contract,
        validate_timestamp_cutoff_contract,
    )
    from lottery_api.research.d3_gate.schemas import GateOutput, GateStatus

    results = [
        validate_candidate_provenance_contract(candidate),
        validate_timestamp_cutoff_contract(candidate),
        validate_p257a_baseline_contract(candidate, baseline),
        validate_matched_null_family_contract(candidate, null_family),
        validate_correction_family_contract(correction_family),
        validate_no_approval_status_contract(
            GateOutput(gate_decision=GateStatus.NOT_YET_REJECTED)
        ),
    ]
    assert {result.validator for result in results} == {
        "candidate_provenance",
        "timestamp_cutoff",
        "p257a_baseline",
        "matched_null_family",
        "correction_family",
        "no_approval_status",
    }


def test_validators_reject_missing_required_fields(candidate):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_candidate_provenance_contract,
    )

    bad = dict(candidate.__dict__)
    bad.pop("provenance_digest")
    with pytest.raises(ContractValidationError, match="provenance_digest"):
        validate_candidate_provenance_contract(bad)


def test_validators_reject_forbidden_gate_statuses():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )

    for forbidden in ["APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED"]:
        with pytest.raises(ContractValidationError, match=forbidden):
            validate_no_approval_status_contract({"gate_decision": forbidden})


def test_gate_status_enum_only_allows_rejected_and_not_yet_rejected():
    from lottery_api.research.d3_gate.schemas import GateStatus

    assert {member.value for member in GateStatus} == {"REJECTED", "NOT_YET_REJECTED"}


def test_validators_reject_timestamp_cutoff_violations(candidate):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_timestamp_cutoff_contract,
    )

    bad = dict(candidate.__dict__)
    bad["available_information_cutoff"] = "2026-06-10T00:00:00"
    with pytest.raises(ContractValidationError, match="cutoff"):
        validate_timestamp_cutoff_contract(bad)


def test_validators_reject_missing_matched_null_dimensions(candidate, null_family):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_matched_null_family_contract,
    )

    bad = dict(null_family.__dict__)
    bad.pop("matched_feature_dimensionality")
    with pytest.raises(ContractValidationError, match="matched_feature_dimensionality"):
        validate_matched_null_family_contract(candidate, bad)


def test_validators_reject_missing_correction_family_declarations(correction_family):
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_correction_family_contract,
    )

    bad = dict(correction_family)
    bad["metrics"] = []
    with pytest.raises(ContractValidationError, match="metrics"):
        validate_correction_family_contract(bad)


def test_validators_remain_pure_readonly_by_import_scan():
    modules = " ".join(_imported_modules(VALIDATION_PY)).lower()
    for forbidden in FORBIDDEN_IMPORT_SUBSTRINGS:
        assert forbidden.lower() not in modules


def test_no_backtest_strategy_null_or_statistical_execution_surface():
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
        assert banned not in src, f"Banned execution surface found: {banned}"


def test_artifact_states_d3_not_prediction_model(artifact):
    assert artifact["d3_is_not_a_prediction_model_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["is_validation_gate_not_predictor"] is True


def test_artifact_states_not_yet_rejected_is_not_approval(artifact):
    assert artifact["passing_validators_is_not_approval_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"][
        "not_yet_rejected_is_not_approval"
    ] is True


def test_artifact_bans_improved_accuracy_claims(artifact):
    assert artifact["no_improved_accuracy_claim_confirmed"] is True


def test_artifact_records_no_executable_gate_or_forbidden_paths(artifact):
    for key in [
        "no_executable_gate_evaluation_confirmed",
        "no_null_generation_confirmed",
        "no_pvalue_or_statistical_test_confirmed",
        "no_backtest_confirmed",
        "no_db_write_confirmed",
        "no_recommendation_logic_change_confirmed",
        "no_registry_mutation_confirmed",
        "no_production_write_confirmed",
        "no_controlled_apply_confirmed",
        "no_deployment_confirmed",
    ]:
        assert artifact[key] is True


def test_artifact_next_task_is_p258g_synthetic_fixture_hardening(artifact):
    nxt = artifact["next_allowed_task"]
    assert nxt["task_id"] == "P258G"
    typ = nxt["type"].lower()
    assert "synthetic" in typ
    assert "fixture" in typ
    assert "no real candidate" in typ or "real candidate" in " ".join(
        artifact["forbidden_next_tasks"]
    ).lower()


def test_md_artifact_exists_and_states_contract_validation_only():
    content = _read(ARTIFACT_MD).lower()
    assert "contract validation only" in content
    assert "not a prediction model" in content
    assert "not approval" in content
