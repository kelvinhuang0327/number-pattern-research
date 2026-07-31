"""
P258E — D3 gate read-only skeleton + contract tests.

Verifies the skeleton boundary and prevents accidental execution:
- GateStatus enum has exactly REJECTED + NOT_YET_REJECTED (no approval values)
- validators remain non-executing contract checks
- skeleton modules import no DB / recommendation / production / registry /
  controlled_apply / deployment paths
- no backtest loop or strategy-execution function exists
- the P258E artifact states the non-predictor / not-approval / no-DB / no-accuracy
  boundaries and points to P258F as next
"""

import ast
import json
import os
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

SKELETON_DIR = os.path.join(REPO_ROOT, "lottery_api", "research", "d3_gate")
SCHEMAS_PY = os.path.join(SKELETON_DIR, "schemas.py")
VALIDATION_PY = os.path.join(SKELETON_DIR, "gate_validation.py")

ARTIFACT_JSON = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258e_d3_gate_readonly_skeleton_contract_tests_20260608.json",
)
ARTIFACT_MD = os.path.join(
    REPO_ROOT,
    "outputs",
    "research",
    "p258e_d3_gate_readonly_skeleton_contract_tests_20260608.md",
)

# Forbidden import-module substrings that must never appear in any import
# statement of the skeleton source (checked against actual import targets via
# AST, NOT raw text — docstrings legitimately mention these words to forbid them).
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
]


def _imported_modules(path):
    """Return the set of module targets imported by a Python file (via AST)."""
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


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Skeleton files exist
# ---------------------------------------------------------------------------


def test_skeleton_files_exist():
    assert os.path.isfile(os.path.join(SKELETON_DIR, "__init__.py"))
    assert os.path.isfile(SCHEMAS_PY)
    assert os.path.isfile(VALIDATION_PY)
    assert os.path.isfile(
        os.path.join(REPO_ROOT, "lottery_api", "research", "__init__.py")
    )


# ---------------------------------------------------------------------------
# Gate status enum
# ---------------------------------------------------------------------------


def test_gate_status_enum_only_two_values():
    from lottery_api.research.d3_gate.schemas import GateStatus

    names = {m.name for m in GateStatus}
    assert names == {"REJECTED", "NOT_YET_REJECTED"}


def test_gate_status_enum_no_approval_values():
    from lottery_api.research.d3_gate.schemas import GateStatus

    names = {m.name for m in GateStatus}
    for forbidden in ["APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED"]:
        assert forbidden not in names


# ---------------------------------------------------------------------------
# Schemas present
# ---------------------------------------------------------------------------


def test_schemas_dataclasses_present():
    from lottery_api.research.d3_gate import schemas

    for name in ["CandidateInput", "P257ABaselineInput", "MatchedNullFamily", "GateOutput"]:
        assert hasattr(schemas, name), f"Missing schema dataclass: {name}"


def test_candidate_input_has_required_fields():
    from dataclasses import fields
    from lottery_api.research.d3_gate.schemas import CandidateInput

    field_names = {f.name for f in fields(CandidateInput)}
    for required in [
        "candidate_id",
        "lottery_type",
        "target_draw_id",
        "n_bet_count",
        "numbers_per_bet",
        "available_information_cutoff",
        "random_seed",
        "provenance_digest",
    ]:
        assert required in field_names, f"Missing CandidateInput field: {required}"


# ---------------------------------------------------------------------------
# Validators remain non-executing
# ---------------------------------------------------------------------------


def test_validation_functions_accept_synthetic_contracts_without_execution():
    from lottery_api.research.d3_gate import gate_validation
    from lottery_api.research.d3_gate.schemas import (
        CandidateInput,
        GateOutput,
        GateStatus,
        MatchedNullFamily,
        P257ABaselineInput,
    )

    candidate = CandidateInput(
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
    baseline = P257ABaselineInput(
        baseline_id="p257a_best_n_bet",
        lottery_type=candidate.lottery_type,
        target_draw_id=candidate.target_draw_id,
        n_bet_count=candidate.n_bet_count,
        source_artifact_path="outputs/research/p257a_baseline.json",
        baseline_digest="sha256:baseline",
    )
    null_family = MatchedNullFamily(
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
    correction_family = {
        "candidate_methods": ["synthetic_candidate"],
        "null_variants": ["matched_binomial"],
        "lottery_types": ["POWER_LOTTO"],
        "n_bet_counts": [3],
        "metrics": ["paired_win_rate", "null_percentile"],
        "windows": ["short", "mid", "long"],
    }

    results = [
        gate_validation.validate_candidate_provenance_contract(candidate),
        gate_validation.validate_timestamp_cutoff_contract(candidate),
        gate_validation.validate_p257a_baseline_contract(candidate, baseline),
        gate_validation.validate_matched_null_family_contract(candidate, null_family),
        gate_validation.validate_correction_family_contract(correction_family),
        gate_validation.validate_no_approval_status_contract(
            GateOutput(gate_decision=GateStatus.NOT_YET_REJECTED)
        ),
    ]
    assert all(result.checked_fields for result in results)


# ---------------------------------------------------------------------------
# Import bans / no execution
# ---------------------------------------------------------------------------


def test_skeleton_has_no_forbidden_imports():
    init_py = os.path.join(SKELETON_DIR, "__init__.py")
    research_init = os.path.join(REPO_ROOT, "lottery_api", "research", "__init__.py")
    for path in [SCHEMAS_PY, VALIDATION_PY, init_py, research_init]:
        modules = " ".join(_imported_modules(path)).lower()
        for forbidden in FORBIDDEN_IMPORT_SUBSTRINGS:
            assert forbidden.lower() not in modules, (
                f"Forbidden import target '{forbidden}' in {os.path.basename(path)} "
                f"(imports: {modules})"
            )


def test_no_backtest_or_execution_function():
    for path in [SCHEMAS_PY, VALIDATION_PY]:
        src = _read(path).lower()
        for banned in ["def run_gate", "def evaluate", "def run_backtest", "def score", "def generate_null", "for draw in"]:
            assert banned not in src, f"Banned execution construct '{banned}' in {os.path.basename(path)}"


# ---------------------------------------------------------------------------
# Artifact assertions
# ---------------------------------------------------------------------------


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258E_D3_READ_ONLY_SKELETON_CONTRACT_TESTS_READY"


def test_artifact_states_d3_not_prediction_model(artifact):
    assert artifact["d3_is_not_a_prediction_model_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["is_validation_gate_not_predictor"] is True


def test_artifact_states_passing_is_not_approval(artifact):
    assert artifact["passing_gate_is_not_approval_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["passing_means_only_not_yet_rejected_never_approved"] is True


def test_artifact_bans_accuracy_claim(artifact):
    assert artifact["no_improved_accuracy_claim_confirmed"] is True


def test_artifact_bans_db_write(artifact):
    assert artifact["no_db_write_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["cannot_write_db"] is True


def test_artifact_bans_recommendation_mutation(artifact):
    assert artifact["no_recommendation_logic_change_confirmed"] is True


def test_artifact_enum_records_absent_approval_values(artifact):
    absent = artifact["gate_status_enum"]["explicitly_absent_values"]
    for v in ["APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED"]:
        assert v in absent


def test_artifact_next_task_is_p258f_contract_validator(artifact):
    nxt = artifact["next_allowed_task"]
    assert nxt["task_id"] == "P258F"
    typ = nxt["type"].lower()
    assert "contract validator" in typ
    assert "no scoring" in typ or "still no" in typ


def test_artifact_forbidden_next_tasks(artifact):
    forb = " ".join(artifact["forbidden_next_tasks"]).lower()
    assert "executable gate evaluation" in forb
    assert "db write" in forb
    assert "not_yet_rejected as approved" in forb


def test_md_artifact_exists_and_states_skeleton_only():
    content = _read(ARTIFACT_MD)
    assert "skeleton + contract tests only" in content.lower()
    # MD states: ... never "approved."
    assert 'never "approved' in content or "never approved" in content.lower()
