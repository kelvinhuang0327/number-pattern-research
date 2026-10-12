"""
P255B — Ingest Write Guard Design — Tests

Verifies the JSON design artifact is well-formed and contains all required
guardrail specifications, contract designs, and safety flags.
Read-only: no DB access, no live endpoints.
"""

import json
import os
import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JSON_PATH = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p255b_ingest_write_guard_design_20260608.json"
)


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(_JSON_PATH), f"Artifact not found: {_JSON_PATH}"
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Basic parse + classification
# ---------------------------------------------------------------------------

class TestArtifactBasics:
    def test_json_parses(self, artifact):
        assert isinstance(artifact, dict)

    def test_schema_version(self, artifact):
        assert artifact.get("schema_version") == "1.0"

    def test_task_id(self, artifact):
        assert artifact.get("task_id") == "P255B"

    def test_classification(self, artifact):
        assert artifact.get("classification") == "INGEST_WRITE_GUARD_DESIGN_COMPLETE"

    def test_date(self, artifact):
        assert artifact.get("date") == "2026-06-08"

    def test_explicit_authorization_present(self, artifact):
        auth = artifact.get("explicit_authorization", "")
        assert "P255B" in auth


# ---------------------------------------------------------------------------
# P255A dependency
# ---------------------------------------------------------------------------

class TestP255ADependency:
    def test_p255a_dependency_verified(self, artifact):
        assert artifact.get("p255a_dependency_verified") is True

    def test_p255a_pr_363(self, artifact):
        dep = artifact.get("p255a_dependency", {})
        assert dep.get("pr") == 363

    def test_p255a_classification_correct(self, artifact):
        dep = artifact.get("p255a_dependency", {})
        assert dep.get("classification") == "INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE"


# ---------------------------------------------------------------------------
# Guardrail designs — presence
# ---------------------------------------------------------------------------

class TestGuardrailDesignsPresence:
    EXPECTED_KEYS = [
        "G01_default_dry_run_true",
        "G02_server_side_confirm_token",
        "G03_ui_confirmation",
        "G04_audit_log",
        "G05_backup_sha_integrity",
        "G06_idempotency",
        "G07_cors_hardening",
        "G08_env_write_gate",
    ]

    def test_guardrail_designs_exist(self, artifact):
        assert "guardrail_designs" in artifact

    def test_all_eight_guardrails_present(self, artifact):
        gd = artifact["guardrail_designs"]
        for key in self.EXPECTED_KEYS:
            assert key in gd, f"Missing guardrail key: {key}"

    def test_guardrail_ids_sequential(self, artifact):
        gd = artifact["guardrail_designs"]
        for expected_id, key in zip(["G01","G02","G03","G04","G05","G06","G07","G08"],
                                     self.EXPECTED_KEYS):
            assert gd[key]["id"] == expected_id


# ---------------------------------------------------------------------------
# G01 — default dry_run=True
# ---------------------------------------------------------------------------

class TestG01DefaultDryRun:
    def test_g01_proposed_default_is_true(self, artifact):
        g01 = artifact["guardrail_designs"]["G01_default_dry_run_true"]
        assert g01["proposed_default"] is True

    def test_g01_proposed_code_contains_true(self, artifact):
        g01 = artifact["guardrail_designs"]["G01_default_dry_run_true"]
        assert "True" in g01["proposed_code"]

    def test_g01_current_code_contains_false(self, artifact):
        g01 = artifact["guardrail_designs"]["G01_default_dry_run_true"]
        assert "False" in g01["current_state"]["current_code"]

    def test_g01_error_response_defined(self, artifact):
        g01 = artifact["guardrail_designs"]["G01_default_dry_run_true"]
        err = g01["error_semantics"]["dry_run_false_without_confirm"]
        assert err["http_status"] == 422
        assert "error" in err["body"]

    def test_g01_implementation_done_is_false(self, artifact):
        g01 = artifact["guardrail_designs"]["G01_default_dry_run_true"]
        assert g01["implementation_done"] is False

    def test_g01_priority_p0(self, artifact):
        assert artifact["guardrail_designs"]["G01_default_dry_run_true"]["priority"] == "P0"


# ---------------------------------------------------------------------------
# G02 — server-side confirm token
# ---------------------------------------------------------------------------

class TestG02ConfirmToken:
    def test_g02_priority_p0(self, artifact):
        assert artifact["guardrail_designs"]["G02_server_side_confirm_token"]["priority"] == "P0"

    def test_g02_has_apply_confirmed_field(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        fields = g02["new_request_fields"]
        assert "apply_confirmed" in fields
        assert fields["apply_confirmed"]["required_for_write"] is True

    def test_g02_has_confirm_token_field(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        fields = g02["new_request_fields"]
        assert "confirm_token" in fields
        assert fields["confirm_token"]["required_for_write"] is True

    def test_g02_token_ttl_defined(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        ttl = g02["new_request_fields"]["confirm_token"]["token_ttl_seconds"]
        assert isinstance(ttl, int) and ttl > 0

    def test_g02_missing_token_response_422(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        assert g02["missing_token_response"]["http_status"] == 422

    def test_g02_invalid_token_response_422(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        assert g02["invalid_token_response"]["http_status"] == 422

    def test_g02_count_mismatch_response_409(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        assert g02["count_mismatch_response"]["http_status"] == 409

    def test_g02_validation_logic_present(self, artifact):
        g02 = artifact["guardrail_designs"]["G02_server_side_confirm_token"]
        logic = g02["server_validation_logic"]
        assert isinstance(logic, list) and len(logic) >= 5

    def test_g02_implementation_done_is_false(self, artifact):
        assert artifact["guardrail_designs"]["G02_server_side_confirm_token"]["implementation_done"] is False


# ---------------------------------------------------------------------------
# Request contract design
# ---------------------------------------------------------------------------

class TestRequestContractDesign:
    def test_request_contract_exists(self, artifact):
        assert "request_contract_design" in artifact

    def test_proposed_schema_has_dry_run_false(self, artifact):
        schema = artifact["request_contract_design"]["proposed_schema"]
        dry_run = schema.get("dry_run", "")
        assert "True" in dry_run, f"dry_run default should be True in proposed schema, got: {dry_run}"

    def test_proposed_schema_has_apply_confirmed(self, artifact):
        schema = artifact["request_contract_design"]["proposed_schema"]
        assert "apply_confirmed" in schema

    def test_proposed_schema_has_confirm_token(self, artifact):
        schema = artifact["request_contract_design"]["proposed_schema"]
        assert "confirm_token" in schema

    def test_proposed_schema_has_idempotency_key(self, artifact):
        schema = artifact["request_contract_design"]["proposed_schema"]
        assert "idempotency_key" in schema

    def test_validation_order_starts_with_write_enabled_check(self, artifact):
        order = artifact["request_contract_design"]["validation_order"]
        assert any("INGEST_WRITE_ENABLED" in step or "G08" in step for step in order)


# ---------------------------------------------------------------------------
# Response contract design
# ---------------------------------------------------------------------------

class TestResponseContractDesign:
    def test_response_contract_exists(self, artifact):
        assert "response_contract_design" in artifact

    def test_dry_run_response_has_confirm_token(self, artifact):
        wg = artifact["response_contract_design"]["dry_run_response"]["write_guard"]
        assert "confirm_token" in wg

    def test_apply_response_has_sha_fields(self, artifact):
        wg = artifact["response_contract_design"]["apply_response"]["write_guard"]
        assert "db_sha256_before" in wg
        assert "db_sha256_after" in wg

    def test_error_responses_include_missing_token(self, artifact):
        errs = artifact["response_contract_design"]["error_responses"]
        assert any("missing_confirm_token" in k or "missing_confirm_token" in v
                   for k, v in errs.items())

    def test_error_responses_include_invalid_token(self, artifact):
        errs = artifact["response_contract_design"]["error_responses"]
        assert any("invalid_confirm_token" in k or "invalid_confirm_token" in v
                   for k, v in errs.items())

    def test_error_responses_include_write_disabled(self, artifact):
        errs = artifact["response_contract_design"]["error_responses"]
        assert any("write_disabled" in k or "disabled" in v
                   for k, v in errs.items())


# ---------------------------------------------------------------------------
# Failure mode design
# ---------------------------------------------------------------------------

class TestFailureModeDesign:
    def test_failure_modes_exist(self, artifact):
        fm = artifact.get("failure_mode_design")
        assert isinstance(fm, list) and len(fm) >= 5

    def test_missing_token_failure_mode(self, artifact):
        ids = [f["id"] for f in artifact["failure_mode_design"]]
        assert "F08" in ids or "F02" in ids  # missing token scenario

    def test_omitted_dry_run_failure_mode(self, artifact):
        fms = artifact["failure_mode_design"]
        omit_modes = [f for f in fms if "omit" in f["scenario"].lower()
                      or "no dry_run" in f["scenario"].lower()
                      or "dry_run field" in f["scenario"].lower()]
        assert len(omit_modes) >= 1, "Expected a failure mode for omitted dry_run"

    def test_all_failure_modes_have_proposed_behavior(self, artifact):
        for f in artifact["failure_mode_design"]:
            assert f.get("proposed_behavior"), f"Failure mode {f['id']} missing proposed_behavior"

    def test_all_failure_modes_reference_a_guard(self, artifact):
        for f in artifact["failure_mode_design"]:
            assert f.get("guard"), f"Failure mode {f['id']} missing guard reference"


# ---------------------------------------------------------------------------
# Future P255C scope
# ---------------------------------------------------------------------------

class TestP255CScope:
    def test_p255c_scope_exists(self, artifact):
        assert "future_p255c_implementation_scope" in artifact

    def test_p255c_implementation_done_is_false(self, artifact):
        scope = artifact["future_p255c_implementation_scope"]
        assert scope.get("implementation_done") is False

    def test_p255c_requires_authorization(self, artifact):
        scope = artifact["future_p255c_implementation_scope"]
        assert "authorization_required" in scope
        assert "P255C" in scope.get("authorization_required", "")

    def test_p255c_files_to_modify_nonempty(self, artifact):
        files = artifact["future_p255c_implementation_scope"]["scope"]["files_to_modify"]
        assert isinstance(files, list) and len(files) >= 3

    def test_p255c_files_to_create_nonempty(self, artifact):
        files = artifact["future_p255c_implementation_scope"]["scope"]["files_to_create"]
        assert isinstance(files, list) and len(files) >= 1

    def test_p255c_pre_conditions_nonempty(self, artifact):
        pre = artifact["future_p255c_implementation_scope"]["pre_conditions"]
        assert isinstance(pre, list) and len(pre) >= 2


# ---------------------------------------------------------------------------
# Current accepted baseline
# ---------------------------------------------------------------------------

class TestCurrentAcceptedBaseline:
    def test_baseline_exists(self, artifact):
        assert "current_accepted_baseline" in artifact

    def test_big_lotto_raw(self, artifact):
        assert artifact["current_accepted_baseline"]["BIG_LOTTO_raw"] == 22239

    def test_big_lotto_canonical(self, artifact):
        assert artifact["current_accepted_baseline"]["BIG_LOTTO_canonical"] == 2114

    def test_stale_values_documented(self, artifact):
        stale = artifact["current_accepted_baseline"]["stale_must_not_reuse"]
        assert stale["BIG_LOTTO_raw_stale"] == 22238
        assert stale["BIG_LOTTO_canonical_stale"] == 2113


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------

class TestSafetyFlags:
    def test_no_db_write_confirmed(self, artifact):
        assert artifact.get("no_db_write_confirmed") is True

    def test_no_registry_mutation_confirmed(self, artifact):
        assert artifact.get("no_registry_mutation_confirmed") is True

    def test_no_strategy_promotion_confirmed(self, artifact):
        assert artifact.get("no_strategy_promotion_confirmed") is True

    def test_no_betting_advice_confirmed(self, artifact):
        assert artifact.get("no_betting_advice_confirmed") is True

    def test_non_actions_nonempty(self, artifact):
        na = artifact.get("non_actions", [])
        assert isinstance(na, list) and len(na) >= 5


# ---------------------------------------------------------------------------
# Final decision
# ---------------------------------------------------------------------------

class TestFinalDecision:
    def test_final_decision_is_hold(self, artifact):
        fd = artifact.get("final_decision", "")
        assert "HOLD" in fd

    def test_recommended_next_task_is_hold(self, artifact):
        rnt = artifact.get("recommended_next_task", "")
        assert "HOLD" in rnt or "WAITING_FOR_USER_AUTHORIZATION" in rnt

    def test_phase0_head_equals_origin_main(self, artifact):
        assert artifact["phase0_summary"]["HEAD_equals_origin_main"] is True

    def test_p255c_authorization_required(self, artifact):
        rnt = artifact.get("recommended_next_task", "")
        fd  = artifact.get("final_decision", "")
        assert "P255C" in rnt or "P255C" in fd or \
               artifact["future_p255c_implementation_scope"]["authorization_required"]
