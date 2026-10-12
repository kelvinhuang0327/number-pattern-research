"""P258J — D3 read-only synthetic integration skeleton tests.

All fixtures are synthetic literals.  No real candidate files, no strategy
output artifacts, no DB access, no executable gate evaluation, no null
generation, no p-values, no paired tests, no backtests.

D3 is not a prediction model.
Contract validation is not strategy evaluation.
NOT_YET_REJECTED is not approval.
"""

import json
import pathlib
import sys
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_PATH = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p258j_d3_readonly_synthetic_integration_skeleton_tests_20260609.json"
)
D3_GATE_DIR = REPO_ROOT / "lottery_api" / "research" / "d3_gate"
SKELETON_PATH = D3_GATE_DIR / "integration_skeleton.py"


# ---------------------------------------------------------------------------
# Helpers — synthetic dry-contract fixtures (all literals, no real data)
# ---------------------------------------------------------------------------

def _make_candidate():
    """Synthetic CandidateInput with all required fields."""
    from lottery_api.research.d3_gate.schemas import CandidateInput
    return CandidateInput(
        candidate_id="SYNTH-CAND-P258J-001",
        lottery_type="DAILY_539",
        target_draw_id="115000200",
        target_draw_date="2026-06-10",
        n_bet_count=2,
        numbers_per_bet=5,
        feature_dimensionality=3,
        regime_count_or_parameter_count=2,
        window_schedule="short100_mid500",
        generated_at="2026-06-09T12:00:00",
        available_information_cutoff="2026-06-09T00:00:00",
        random_seed=42,
        source_artifact_path="outputs/research/synth_candidate_p258j.json",
        provenance_digest="abc123def456synth",
    )


def _make_baseline(candidate=None):
    """Synthetic P257ABaselineInput aligned to the candidate fixture."""
    from lottery_api.research.d3_gate.schemas import P257ABaselineInput
    if candidate is None:
        candidate = _make_candidate()
    return P257ABaselineInput(
        baseline_id="SYNTH-BASE-P258J-001",
        lottery_type=candidate.lottery_type,
        target_draw_id=candidate.target_draw_id,
        n_bet_count=candidate.n_bet_count,
        source_artifact_path="outputs/research/synth_baseline_p258j.json",
        baseline_digest="baseline_digest_synth_p258j",
    )


def _make_null_family(candidate=None):
    """Synthetic MatchedNullFamily aligned to the candidate fixture."""
    from lottery_api.research.d3_gate.schemas import MatchedNullFamily
    if candidate is None:
        candidate = _make_candidate()
    return MatchedNullFamily(
        null_family_id="SYNTH-NULL-P258J-001",
        matched_lottery_type=candidate.lottery_type,
        matched_n_bet_count=candidate.n_bet_count,
        matched_numbers_per_bet=candidate.numbers_per_bet,
        matched_window_schedule=candidate.window_schedule,
        matched_feature_dimensionality=candidate.feature_dimensionality,
        matched_regime_or_parameter_count=candidate.regime_count_or_parameter_count,
        null_generation_seed=99,
        null_count=1000,
        source_artifact_path="outputs/research/synth_null_family_p258j.json",
    )


def _make_correction_family():
    """Synthetic correction-family declaration dict with 6 required collections."""
    return {
        "candidate_methods": ["synth_method_a", "synth_method_b"],
        "null_variants": ["binomial_null_v1"],
        "lottery_types": ["DAILY_539"],
        "n_bet_counts": [2],
        "metrics": ["hit_rate_m2plus"],
        "windows": ["short100", "mid500"],
    }


def _make_gate_output_not_yet_rejected():
    """Synthetic GateOutput with NOT_YET_REJECTED status."""
    from lottery_api.research.d3_gate.schemas import GateOutput, GateStatus
    return GateOutput(gate_decision=GateStatus.NOT_YET_REJECTED)


def _make_gate_output_rejected():
    """Synthetic GateOutput with REJECTED status."""
    from lottery_api.research.d3_gate.schemas import GateOutput, GateStatus
    return GateOutput(
        gate_decision=GateStatus.REJECTED,
        rejection_reasons=["synth_rejection_reason_p258j"],
    )


def _import_skeleton():
    """Import the integration skeleton as a package module."""
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    import importlib
    return importlib.import_module(
        "lottery_api.research.d3_gate.integration_skeleton"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact():
    with ARTIFACT_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def skeleton():
    return _import_skeleton()


# ---------------------------------------------------------------------------
# Artifact: basic structure
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_classification"] == (
        "P258J_D3_READ_ONLY_SYNTHETIC_INTEGRATION_SKELETON_TESTS_READY"
    )


def test_artifact_is_synthetic_tests_only(artifact):
    assert artifact["synthetic_tests_only_declaration"]["is_synthetic_tests_only"] is True


def test_artifact_uses_synthetic_dry_contract_fixtures_only(artifact):
    assert (
        artifact["synthetic_tests_only_declaration"][
            "uses_synthetic_dry_contract_fixtures_only"
        ]
        is True
    )


def test_no_real_candidate_methods_in_artifact(artifact):
    assert (
        artifact["synthetic_tests_only_declaration"]["no_real_candidate_methods_used"]
        is True
    )


def test_no_strategy_output_artifacts_as_fixtures(artifact):
    assert (
        artifact["synthetic_tests_only_declaration"][
            "no_strategy_output_artifacts_as_fixtures"
        ]
        is True
    )


# ---------------------------------------------------------------------------
# Artifact: safety semantics
# ---------------------------------------------------------------------------

def test_d3_is_not_a_prediction_model(artifact):
    assert artifact["mandatory_safety_semantics"]["d3_is_not_a_prediction_model"] is True


def test_contract_validation_is_not_strategy_evaluation(artifact):
    assert (
        artifact["mandatory_safety_semantics"][
            "contract_validation_is_not_strategy_evaluation"
        ]
        is True
    )


def test_not_yet_rejected_is_not_approval_in_artifact(artifact):
    assert (
        artifact["mandatory_safety_semantics"]["not_yet_rejected_is_not_approval"] is True
    )


def test_no_improved_accuracy_claimed(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert (
        sem["passing_contract_validation_does_not_imply_improved_prediction_accuracy"]
        is True
    )


def test_no_production_use_authorized(artifact):
    assert (
        artifact["mandatory_safety_semantics"][
            "passing_validators_does_not_allow_production_use"
        ]
        is True
    )


def test_no_recommendation_use_authorized(artifact):
    assert (
        artifact["mandatory_safety_semantics"][
            "passing_validators_does_not_allow_recommendation_use"
        ]
        is True
    )


def test_no_lottery_edge_claimed(artifact):
    assert artifact["mandatory_safety_semantics"]["no_lottery_edge_claimed"] is True


# ---------------------------------------------------------------------------
# Artifact: next task
# ---------------------------------------------------------------------------

def test_next_allowed_task_is_p258k(artifact):
    assert "P258K" in artifact["next_allowed_task"]


def test_executable_gate_is_forbidden_next_task(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("executable gate" in t.lower() for t in forbidden)


def test_not_yet_rejected_as_approved_is_forbidden_next_task(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("NOT_YET_REJECTED" in t for t in forbidden)


# ---------------------------------------------------------------------------
# Synthetic dry-contract complete fixture round-trip
# These tests prove the validators can be called with synthetic fixtures
# and produce ValidationResult objects — no real candidate data used.
# ---------------------------------------------------------------------------

def test_synthetic_candidate_passes_provenance_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_candidate_provenance_contract,
    )
    result = validate_candidate_provenance_contract(_make_candidate())
    assert result.validator == "candidate_provenance"


def test_synthetic_candidate_passes_timestamp_cutoff_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_timestamp_cutoff_contract,
    )
    result = validate_timestamp_cutoff_contract(_make_candidate())
    assert result.validator == "timestamp_cutoff"


def test_synthetic_baseline_passes_p257a_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_p257a_baseline_contract,
    )
    candidate = _make_candidate()
    baseline = _make_baseline(candidate)
    result = validate_p257a_baseline_contract(candidate, baseline)
    assert result.validator == "p257a_baseline"


def test_synthetic_null_family_passes_matched_null_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_matched_null_family_contract,
    )
    candidate = _make_candidate()
    null_family = _make_null_family(candidate)
    result = validate_matched_null_family_contract(candidate, null_family)
    assert result.validator == "matched_null_family"


def test_synthetic_correction_family_passes_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_correction_family_contract,
    )
    result = validate_correction_family_contract(_make_correction_family())
    assert result.validator == "correction_family"


def test_synthetic_not_yet_rejected_gate_output_passes_no_approval_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_no_approval_status_contract,
    )
    result = validate_no_approval_status_contract(_make_gate_output_not_yet_rejected())
    assert result.validator == "no_approval_status"


def test_synthetic_rejected_gate_output_passes_no_approval_validator():
    from lottery_api.research.d3_gate.gate_validation import (
        validate_no_approval_status_contract,
    )
    result = validate_no_approval_status_contract(_make_gate_output_rejected())
    assert result.validator == "no_approval_status"


def test_complete_synthetic_integration_contract_all_validators_pass():
    """All 6 validators pass against a fully consistent synthetic fixture set."""
    from lottery_api.research.d3_gate.gate_validation import (
        validate_no_approval_status_contract,
        validate_candidate_provenance_contract,
        validate_timestamp_cutoff_contract,
        validate_p257a_baseline_contract,
        validate_matched_null_family_contract,
        validate_correction_family_contract,
    )
    candidate = _make_candidate()
    baseline = _make_baseline(candidate)
    null_family = _make_null_family(candidate)
    correction_family = _make_correction_family()
    gate_output = _make_gate_output_not_yet_rejected()

    results = [
        validate_no_approval_status_contract(gate_output),
        validate_candidate_provenance_contract(candidate),
        validate_timestamp_cutoff_contract(candidate),
        validate_p257a_baseline_contract(candidate, baseline),
        validate_matched_null_family_contract(candidate, null_family),
        validate_correction_family_contract(correction_family),
    ]
    assert len(results) == 6
    assert all(hasattr(r, "validator") for r in results)


# ---------------------------------------------------------------------------
# Synthetic dry-contract invalid fixture cases
# ---------------------------------------------------------------------------

def test_invalid_missing_candidate_id_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_candidate_provenance_contract,
    )
    bad = {
        "lottery_type": "DAILY_539",
        "target_draw_id": "115000200",
        "target_draw_date": "2026-06-10",
        "n_bet_count": 2,
        "numbers_per_bet": 5,
        "feature_dimensionality": 3,
        "regime_count_or_parameter_count": 2,
        "window_schedule": "short100",
        "generated_at": "2026-06-09T12:00:00",
        "available_information_cutoff": "2026-06-09T00:00:00",
        "random_seed": 42,
        "source_artifact_path": "synth.json",
        "provenance_digest": "abc",
        # candidate_id intentionally missing
    }
    with pytest.raises(ContractValidationError):
        validate_candidate_provenance_contract(bad)


def test_invalid_missing_baseline_id_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_p257a_baseline_contract,
    )
    candidate = _make_candidate()
    bad_baseline = {
        "lottery_type": candidate.lottery_type,
        "target_draw_id": candidate.target_draw_id,
        "n_bet_count": candidate.n_bet_count,
        "source_artifact_path": "synth.json",
        "baseline_digest": "abc",
        # baseline_id intentionally missing
    }
    with pytest.raises(ContractValidationError):
        validate_p257a_baseline_contract(candidate, bad_baseline)


def test_invalid_missing_null_family_id_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_matched_null_family_contract,
    )
    candidate = _make_candidate()
    bad_null = {
        "matched_lottery_type": candidate.lottery_type,
        "matched_n_bet_count": candidate.n_bet_count,
        "matched_numbers_per_bet": candidate.numbers_per_bet,
        "matched_window_schedule": candidate.window_schedule,
        "matched_feature_dimensionality": candidate.feature_dimensionality,
        "matched_regime_or_parameter_count": candidate.regime_count_or_parameter_count,
        "null_generation_seed": 99,
        "null_count": 1000,
        "source_artifact_path": "synth.json",
        # null_family_id intentionally missing
    }
    with pytest.raises(ContractValidationError):
        validate_matched_null_family_contract(candidate, bad_null)


def test_invalid_missing_correction_family_field_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_correction_family_contract,
    )
    bad = {
        "candidate_methods": ["synth_a"],
        "null_variants": ["null_v1"],
        "lottery_types": ["DAILY_539"],
        "n_bet_counts": [2],
        "metrics": ["hit_rate"],
        # "windows" intentionally missing
    }
    with pytest.raises(ContractValidationError):
        validate_correction_family_contract(bad)


def test_invalid_empty_correction_family_field_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_correction_family_contract,
    )
    bad = {
        "candidate_methods": [],  # empty — forbidden
        "null_variants": ["null_v1"],
        "lottery_types": ["DAILY_539"],
        "n_bet_counts": [2],
        "metrics": ["hit_rate"],
        "windows": ["short100"],
    }
    with pytest.raises(ContractValidationError):
        validate_correction_family_contract(bad)


def test_invalid_forbidden_gate_status_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )
    # Simulate a dict with a forbidden token (APPROVED)
    class FakeOutput:
        gate_decision = "APPROVED"
    with pytest.raises(ContractValidationError):
        validate_no_approval_status_contract(FakeOutput())


def test_invalid_promoted_gate_status_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )
    class FakeOutput:
        gate_decision = "PROMOTED"
    with pytest.raises(ContractValidationError):
        validate_no_approval_status_contract(FakeOutput())


def test_invalid_production_ready_gate_status_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )
    class FakeOutput:
        gate_decision = "PRODUCTION_READY"
    with pytest.raises(ContractValidationError):
        validate_no_approval_status_contract(FakeOutput())


def test_invalid_recommended_gate_status_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_no_approval_status_contract,
    )
    class FakeOutput:
        gate_decision = "RECOMMENDED"
    with pytest.raises(ContractValidationError):
        validate_no_approval_status_contract(FakeOutput())


def test_invalid_timestamp_cutoff_after_target_draw_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_timestamp_cutoff_contract,
    )
    bad = {
        "target_draw_date": "2026-06-09",
        "generated_at": "2026-06-10T00:00:00",
        # cutoff is AFTER target_draw_date — forbidden
        "available_information_cutoff": "2026-06-09T12:00:00",
    }
    with pytest.raises(ContractValidationError):
        validate_timestamp_cutoff_contract(bad)


def test_invalid_baseline_lottery_type_mismatch_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_p257a_baseline_contract,
    )
    candidate = _make_candidate()
    bad_baseline = {
        "baseline_id": "SYNTH-BAD",
        "lottery_type": "BIG_LOTTO",  # mismatches candidate.lottery_type DAILY_539
        "target_draw_id": candidate.target_draw_id,
        "n_bet_count": candidate.n_bet_count,
        "source_artifact_path": "synth.json",
        "baseline_digest": "abc",
    }
    with pytest.raises(ContractValidationError):
        validate_p257a_baseline_contract(candidate, bad_baseline)


def test_invalid_null_family_lottery_type_mismatch_raises():
    from lottery_api.research.d3_gate.gate_validation import (
        ContractValidationError,
        validate_matched_null_family_contract,
    )
    candidate = _make_candidate()
    bad_null = {
        "null_family_id": "SYNTH-BAD-NULL",
        "matched_lottery_type": "POWER_LOTTO",  # mismatches
        "matched_n_bet_count": candidate.n_bet_count,
        "matched_numbers_per_bet": candidate.numbers_per_bet,
        "matched_window_schedule": candidate.window_schedule,
        "matched_feature_dimensionality": candidate.feature_dimensionality,
        "matched_regime_or_parameter_count": candidate.regime_count_or_parameter_count,
        "null_generation_seed": 99,
        "null_count": 1000,
        "source_artifact_path": "synth.json",
    }
    with pytest.raises(ContractValidationError):
        validate_matched_null_family_contract(candidate, bad_null)


def test_invalid_not_yet_rejected_is_not_equivalent_to_approved():
    """NOT_YET_REJECTED must not trigger ContractValidationError — it is the correct non-approval status."""
    from lottery_api.research.d3_gate.gate_validation import (
        validate_no_approval_status_contract,
    )
    from lottery_api.research.d3_gate.schemas import GateOutput, GateStatus
    output = GateOutput(gate_decision=GateStatus.NOT_YET_REJECTED)
    # Must pass (no exception) — NOT_YET_REJECTED is valid and NOT treated as APPROVED
    result = validate_no_approval_status_contract(output)
    assert result.validator == "no_approval_status"


# ---------------------------------------------------------------------------
# Validator invocation order
# ---------------------------------------------------------------------------

EXPECTED_VALIDATOR_ORDER = [
    "validate_no_approval_status_contract",
    "validate_candidate_provenance_contract",
    "validate_timestamp_cutoff_contract",
    "validate_p257a_baseline_contract",
    "validate_matched_null_family_contract",
    "validate_correction_family_contract",
]


def test_validator_invocation_order_length(skeleton):
    assert len(skeleton.VALIDATOR_INVOCATION_ORDER) == 6


@pytest.mark.parametrize("i, expected_name", enumerate(EXPECTED_VALIDATOR_ORDER))
def test_validator_invocation_order_step_name(skeleton, i, expected_name):
    order = skeleton.VALIDATOR_INVOCATION_ORDER
    assert order[i]["name"] == expected_name
    assert order[i]["step"] == i + 1


def test_no_approval_validator_is_first(skeleton):
    assert skeleton.VALIDATOR_INVOCATION_ORDER[0]["name"] == (
        "validate_no_approval_status_contract"
    )


def test_correction_family_validator_is_last(skeleton):
    assert skeleton.VALIDATOR_INVOCATION_ORDER[-1]["name"] == (
        "validate_correction_family_contract"
    )


def test_all_validators_have_callable(skeleton):
    for entry in skeleton.VALIDATOR_INVOCATION_ORDER:
        assert callable(entry["callable"]), (
            f"Step {entry['step']} missing callable"
        )


def test_validator_order_matches_artifact(artifact, skeleton):
    artifact_names = [v["name"] for v in artifact["validator_invocation_order_verified"]]
    skeleton_names = [v["name"] for v in skeleton.VALIDATOR_INVOCATION_ORDER]
    assert artifact_names == skeleton_names


# ---------------------------------------------------------------------------
# Fail-closed policy
# ---------------------------------------------------------------------------

def test_fail_closed_policy_present(skeleton):
    policy = skeleton.FAIL_CLOSED_POLICY
    assert policy["any_contract_validation_error_blocks_further_validation"] is True


def test_fail_closed_failure_cannot_be_downgraded(skeleton):
    assert skeleton.FAIL_CLOSED_POLICY["failure_cannot_be_converted_to_warning_only"] is True


def test_fail_closed_not_yet_rejected_not_approval(skeleton):
    assert skeleton.FAIL_CLOSED_POLICY["not_yet_rejected_remains_not_approval"] is True


def test_fail_closed_forbidden_patterns_include_swallow(skeleton):
    patterns = skeleton.FAIL_CLOSED_POLICY["forbidden_patterns"]
    assert any("ContractValidationError: pass" in p for p in patterns)


def test_fail_closed_forbidden_patterns_include_warning_downgrade(skeleton):
    patterns = skeleton.FAIL_CLOSED_POLICY["forbidden_patterns"]
    assert any("warnings.warn" in p for p in patterns)


# ---------------------------------------------------------------------------
# Allowed input contract boundaries
# ---------------------------------------------------------------------------

def test_five_allowed_input_contract_boundaries(skeleton):
    assert len(skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES) == 5


def test_candidate_boundary_present(skeleton):
    names = [b["name"] for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES]
    assert "candidate_provenance_contract" in names


def test_baseline_boundary_present(skeleton):
    names = [b["name"] for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES]
    assert "p257a_baseline_contract" in names


def test_null_family_boundary_present(skeleton):
    names = [b["name"] for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES]
    assert "matched_null_metadata_contract" in names


def test_correction_family_boundary_present(skeleton):
    names = [b["name"] for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES]
    assert "correction_family_declaration_contract" in names


def test_status_result_boundary_present(skeleton):
    names = [b["name"] for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES]
    assert "status_result_contract" in names


def test_status_result_boundary_has_forbidden_values(skeleton):
    status = next(
        b for b in skeleton.ALLOWED_INPUT_CONTRACT_BOUNDARIES
        if b["name"] == "status_result_contract"
    )
    forbidden = status["forbidden_gate_status_values"]
    assert "APPROVED" in forbidden
    assert "PROMOTED" in forbidden


# ---------------------------------------------------------------------------
# Safety semantic constants
# ---------------------------------------------------------------------------

def test_safety_d3_not_prediction_model(skeleton):
    assert skeleton.D3_IS_NOT_A_PREDICTION_MODEL is True


def test_safety_not_strategy_evaluation(skeleton):
    assert skeleton.CONTRACT_VALIDATION_IS_NOT_STRATEGY_EVALUATION is True


def test_safety_not_yet_rejected_not_approval(skeleton):
    assert skeleton.NOT_YET_REJECTED_IS_NOT_APPROVAL is True


def test_safety_no_production_use(skeleton):
    assert skeleton.PASSING_VALIDATORS_DOES_NOT_ALLOW_PRODUCTION_USE is True


def test_safety_no_accuracy_implication(skeleton):
    assert skeleton.PASSING_VALIDATORS_DOES_NOT_IMPLY_IMPROVED_PREDICTION_ACCURACY is True


def test_safety_no_lottery_edge(skeleton):
    assert skeleton.NO_LOTTERY_EDGE_CLAIMED is True


# ---------------------------------------------------------------------------
# NotImplementedError stub safety
# ---------------------------------------------------------------------------

def test_run_flow_raises_not_implemented(skeleton):
    with pytest.raises(NotImplementedError):
        skeleton.run_contract_validation_flow()


def test_run_flow_error_message_mentions_p258i(skeleton):
    with pytest.raises(NotImplementedError) as exc_info:
        skeleton.run_contract_validation_flow()
    assert "P258I" in str(exc_info.value)


def test_run_flow_rejects_any_args(skeleton):
    with pytest.raises(NotImplementedError):
        skeleton.run_contract_validation_flow("some_arg", key="val")


def test_build_plan_returns_dict(skeleton):
    result = skeleton.build_contract_validation_plan()
    assert isinstance(result, dict)


def test_build_plan_includes_not_implemented_status(skeleton):
    result = skeleton.build_contract_validation_plan()
    assert "NOT_IMPLEMENTED" in result["executable_flow_status"]


def test_build_plan_includes_p258j_next_task(skeleton):
    result = skeleton.build_contract_validation_plan()
    assert "P258J" in result["next_authorized_task"] or "P258" in result["next_authorized_task"]


def test_build_plan_has_no_real_candidate_paths():
    """The plan dict must not reference any real strategy output files."""
    skeleton = _import_skeleton()
    plan = skeleton.build_contract_validation_plan()
    plan_str = json.dumps(plan)
    forbidden_path_patterns = [
        "lottery_v2.db",
        "strategy_prediction_replays",
        "quick_predict",
        "acb_",
        "midfreq_",
        "fourier_rhythm",
    ]
    for pattern in forbidden_path_patterns:
        assert pattern not in plan_str, (
            f"build_contract_validation_plan output references real artifact: {pattern!r}"
        )


# ---------------------------------------------------------------------------
# No executable D3 modules created
# ---------------------------------------------------------------------------

FORBIDDEN_MODULES = [
    "candidate_ingest.py",
    "baseline_ingest.py",
    "null_factory.py",
    "gate_statistics.py",
    "gate_orchestrator.py",
    "gate_audit.py",
    "integration_runner.py",
]


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_executable_module_not_created(module_name):
    path = D3_GATE_DIR / module_name
    assert not path.exists(), f"Forbidden module {module_name} exists in d3_gate/"


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_module_confirmed_absent_in_artifact(artifact, module_name):
    confirmed = artifact["forbidden_executable_modules_confirmed_absent"]
    assert module_name in confirmed


# ---------------------------------------------------------------------------
# No forbidden imports in integration_skeleton.py
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORT_LINES = [
    "import numpy",
    "import scipy",
    "from numpy",
    "from scipy",
    "import random",
    "import sqlalchemy",
    "import sqlite3",
    "import null_factory",
    "import gate_statistics",
    "import gate_orchestrator",
    "from null_factory",
    "from gate_statistics",
    "from gate_orchestrator",
]


@pytest.mark.parametrize("import_line", FORBIDDEN_IMPORT_LINES)
def test_skeleton_has_no_forbidden_import(import_line):
    source = SKELETON_PATH.read_text()
    assert import_line not in source, (
        f"integration_skeleton.py contains forbidden import: {import_line!r}"
    )


# ---------------------------------------------------------------------------
# No forbidden function definitions
# ---------------------------------------------------------------------------

FORBIDDEN_FUNCTION_PATTERNS = [
    "def compute_p_value",
    "def generate_null",
    "def run_backtest",
    "def evaluate_gate",
    "def run_gate",
    "def compute_statistic",
    "def paired_test",
    "def load_db",
    "def write_db",
    "def query_db",
]


@pytest.mark.parametrize("pattern", FORBIDDEN_FUNCTION_PATTERNS)
def test_skeleton_has_no_forbidden_function_definition(pattern):
    source = SKELETON_PATH.read_text()
    assert pattern not in source, (
        f"integration_skeleton.py defines forbidden function: {pattern!r}"
    )


# ---------------------------------------------------------------------------
# No real candidate paths or strategy artifacts in fixtures
# ---------------------------------------------------------------------------

def test_synthetic_candidate_fixture_has_no_real_db_path():
    c = _make_candidate()
    assert "lottery_v2.db" not in c.source_artifact_path


def test_synthetic_candidate_fixture_has_no_real_strategy_path():
    c = _make_candidate()
    real_strategy_patterns = ["acb_", "midfreq_", "fourier_", "regime_", "quick_predict"]
    for pattern in real_strategy_patterns:
        assert pattern not in c.source_artifact_path


def test_synthetic_null_family_fixture_has_no_real_paths():
    n = _make_null_family()
    assert "lottery_v2.db" not in n.source_artifact_path
    assert "strategy_prediction_replays" not in n.source_artifact_path


def test_synthetic_baseline_fixture_has_no_real_paths():
    b = _make_baseline()
    assert "lottery_v2.db" not in b.source_artifact_path
