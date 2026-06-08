"""
P258E — D3 gate read-only skeleton + contract tests.

Verifies the skeleton boundary and prevents accidental execution:
- GateStatus enum has exactly REJECTED + NOT_YET_REJECTED (no approval values)
- validation stubs raise NotImplementedError (non-executing)
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
# Validation stubs are non-executing
# ---------------------------------------------------------------------------


def test_validation_stubs_raise_not_implemented():
    from lottery_api.research.d3_gate import gate_validation

    stub_names = [
        "validate_candidate_provenance_contract",
        "validate_timestamp_cutoff_contract",
        "validate_p257a_baseline_contract",
        "validate_matched_null_family_contract",
        "validate_correction_family_contract",
        "validate_no_approval_status_contract",
    ]
    for name in stub_names:
        assert hasattr(gate_validation, name), f"Missing validation stub: {name}"
        stub = getattr(gate_validation, name)
        with pytest.raises(NotImplementedError):
            # call with Nones — stub must raise before using args
            import inspect

            argcount = len(inspect.signature(stub).parameters)
            stub(*([None] * argcount))


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
