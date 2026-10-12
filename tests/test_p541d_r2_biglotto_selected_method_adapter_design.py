"""Focused static/no-DB contract tests for the P541D_R2 design packet."""
import ast
import builtins
import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _module():
    from analysis import p541d_r2_biglotto_selected_method_adapter_design as mod

    return mod


@pytest.fixture(scope="module")
def packet():
    return _module().build_packet(REPO_ROOT)


@pytest.fixture(scope="module")
def artifact():
    mod = _module()
    return mod.strict_json_load_bytes(mod.JSON_OUTPUT.read_bytes(), str(mod.JSON_OUTPUT))


def test_exact_p541c_upstream_identity_and_shortlist(packet):
    mod = _module()
    identity = packet["upstream_identity"]
    assert identity == {
        **mod.UPSTREAM_IDENTITY,
        "verification": "PASS",
        "read_mechanism": "pinned Git blob",
    }
    assert [item["source_path"] for item in packet["method_designs"]] == mod.SELECTED_PATHS
    for design in packet["method_designs"]:
        provenance = design["p541c_provenance"]
        assert provenance["p541c_r2_bucket"] == "needs_adapter_before_readiness"
        assert provenance["risk_level"] == "low"
        assert provenance["low_risk_eligible"] is True
        assert provenance["identity_confirmed"] is True
        assert provenance["confidence"] == "high"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b'{"x":1,"x":2}', "duplicate JSON key"),
        (b'{"x":NaN}', "non-finite JSON constant"),
        (b'[]', "top-level object required"),
        (b'\xff', "invalid UTF-8 JSON"),
    ],
)
def test_strict_json_rejects_invalid_inputs(raw, message):
    mod = _module()
    with pytest.raises(mod.P541DR2ValidationError, match=message):
        mod.strict_json_load_bytes(raw)


@pytest.mark.parametrize("field", ["method_id", "source_path"])
def test_duplicate_design_id_or_path_rejected(packet, field):
    mod = _module()
    changed = copy.deepcopy(packet)
    changed["method_designs"][1][field] = changed["method_designs"][0][field]
    with pytest.raises(mod.P541DR2ValidationError, match="selected path/order|duplicate"):
        mod.validate_packet(changed)


def test_duplicate_manifest_path_rejected(packet):
    mod = _module()
    changed = copy.deepcopy(packet)
    changed["selected_source_manifest"][1]["source_path"] = changed["selected_source_manifest"][0]["source_path"]
    with pytest.raises(mod.P541DR2ValidationError, match="selected path/order|duplicate"):
        mod.validate_packet(changed)


def test_duplicate_strategy_id_rejected(packet):
    mod = _module()
    changed = copy.deepcopy(packet)
    changed["method_designs"][2]["proposed_strategy"]["strategy_id"] = (
        changed["method_designs"][1]["proposed_strategy"]["strategy_id"]
    )
    with pytest.raises(mod.P541DR2ValidationError, match="duplicate proposed strategy_id"):
        mod.validate_packet(changed)


def test_five_source_identities_and_ast_parsing(packet):
    expected = {
        "tools/advanced_prediction_engine.py": (
            "5c72f7e87de6d2f7721d7fc9eb7eb57f4e848744",
            24006,
            "f92be0a25fc2da83eb9d999081a80d59c4c9af089edcefcdf44f6f3cfc16a8ce",
        ),
        "lottery_api/models/social_wisdom_predictor.py": (
            "1a1f4119f4ade1b5605a988f595c7ed8300e6a40",
            12772,
            "a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b",
        ),
        "tools/quick_ml_predict.py": (
            "36cf12dcef80d7f0bada22e024336eb22f8bfee5",
            11213,
            "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80",
        ),
        "tools/big_lotto_exhaustive_audit.py": (
            "ff9efe54d3519c47798c9f6b47a5e3dc44f0b730",
            3292,
            "694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c",
        ),
        "lottery_api/models/zone_split.py": (
            "5ce1ce023cab846791550bd7240106600ee9b95e",
            3916,
            "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211",
        ),
    }
    assert len(packet["selected_source_manifest"]) == 5
    for record in packet["selected_source_manifest"]:
        blob, size, sha256 = expected[record["source_path"]]
        assert (record["git_blob_sha"], record["byte_size"], record["sha256"]) == (
            blob,
            size,
            sha256,
        )
        assert record["utf8_parse"] == "PASS"
        assert record["ast_parse"] == "PASS"
        assert isinstance(record["imports"], list)
        assert isinstance(record["classes"], list)
        assert isinstance(record["functions"], list)


def test_selected_targets_are_never_imported_or_executed(packet):
    mod = _module()
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for path in mod.SELECTED_PATHS:
        module_name = path[:-3].replace("/", ".")
        assert module_name not in imported
        assert module_name not in sys.modules
    evidence = packet["no_db_no_execution_evidence"]
    assert evidence["selected_modules_imported"] is False
    assert evidence["selected_modules_executed"] is False
    assert evidence["source_read_mechanism"] == "git show <base>:<relative-path>"


def test_build_opens_no_db_csv_runtime_or_network_file(monkeypatch):
    mod = _module()
    original_path_open = Path.open
    original_builtin_open = builtins.open

    def forbidden_path_open(self, *_args, **_kwargs):
        raise AssertionError(f"unexpected Path.open during static build: {self}")

    def forbidden_builtin_open(file, *_args, **_kwargs):
        raise AssertionError(f"unexpected open during static build: {file}")

    monkeypatch.setattr(Path, "open", forbidden_path_open)
    monkeypatch.setattr(builtins, "open", forbidden_builtin_open)
    built = mod.build_packet(REPO_ROOT)
    assert built["no_db_no_execution_evidence"]["db_access"] == "NONE"
    assert original_path_open is not None and original_builtin_open is not None


def test_generator_has_no_sqlite_network_environment_or_dynamic_import_api():
    mod = _module()
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    forbidden_imports = {"sqlite3", "requests", "urllib", "socket", "importlib", "pandas", "numpy"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert forbidden_imports.isdisjoint(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_imports
    assert "__import__(" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source


def test_allowed_status_enum_only_and_ready_consistency(packet):
    mod = _module()
    for design in packet["method_designs"]:
        assert design["design_status"] in mod.ALLOWED_STATUSES
        assert design["ready_for_implementation"] == (
            design["design_status"] in mod.READY_STATUSES
        )


@pytest.mark.parametrize(
    "gate",
    ["causality_resolved", "randomness_resolved", "external_state_resolved", "identity_distinct"],
)
def test_unresolved_gate_cannot_be_marked_ready(packet, gate):
    mod = _module()
    changed = copy.deepcopy(packet)
    ready = next(item for item in changed["method_designs"] if item["ready_for_implementation"])
    ready["readiness_gates"][gate] = False
    with pytest.raises(mod.P541DR2ValidationError, match="unresolved design marked ready"):
        mod.validate_packet(changed)


def test_existing_equivalent_findings_are_represented(packet):
    allowed = _module().ALLOWED_EQUIVALENT_RESULTS
    results = []
    for design in packet["method_designs"]:
        audit = design["equivalent_audit"]
        assert audit["result"] in allowed
        assert audit["evidence"]
        assert all(item["path"] and item["finding"] for item in audit["evidence"])
        results.append(audit["result"])
    assert "EXISTING_EQUIVALENT_REUSE" in results
    assert "EXISTING_PARTIAL_EQUIVALENT" in results
    assert "NO_EXISTING_EQUIVALENT" in results


def test_big_lotto_auditor_is_fail_closed(packet):
    design = packet["method_designs"][3]
    assert design["source_path"] == "tools/big_lotto_exhaustive_audit.py"
    assert design["design_status"] == "NOT_AN_ADAPTER_CANDIDATE"
    assert design["ready_for_implementation"] is False
    assert design["selected_entrypoint"] is None
    assert design["proposed_strategy"]["strategy_id"] is None
    assert "outcome" in design["design_rationale"].lower()
    assert design["randomness_and_seed_contract"]["deterministic"] is False


def test_zone_split_has_local_deterministic_rng_design(packet):
    design = packet["method_designs"][4]
    seed = design["randomness_and_seed_contract"]
    assert design["design_status"] == "DETERMINISTIC_REIMPLEMENTATION_READY"
    assert seed["present"] is True
    assert seed["deterministic"] is True
    assert "SHA-256" in seed["contract"]
    assert "local random.Random" in seed["contract"]
    assert "global RNG" in seed["contract"]
    assert design["input_output_normalization"]["output"].startswith("first of three")


def test_quickml_is_fail_closed_and_has_no_implementation_identity(packet):
    design = packet["method_designs"][2]
    assert design["design_status"] == "CTO_REVIEW_REQUIRED"
    assert design["ready_for_implementation"] is False
    assert design["equivalent_audit"]["result"] == "EXISTING_PARTIAL_EQUIVALENT"
    assert design["candidate_legacy_entrypoint"] == "QuickMLPredictor.predict_advanced_ensemble"
    assert design["selected_entrypoint"] is None
    assert design["minimum_history"] == 50
    assert design["proposed_strategy"] == {
        "strategy_id": None,
        "strategy_name": None,
        "strategy_version": None,
        "lifecycle": None,
        "supported_lottery_types": [],
    }
    assert design["future_implementation_files"] == []


def test_quickml_has_no_temporary_csv_workaround(packet):
    design = packet["method_designs"][2]
    assert "temporary CSV" in design["external_state_and_dependencies"]["forbidden_legacy_reads"]
    assert "constructor CSV access" in design["external_state_and_dependencies"]["forbidden_legacy_reads"]
    assert "Do not import or construct" in design["import_safety_plan"]
    assert "do not create a temporary CSV" in design["import_safety_plan"]
    assert design["external_state_and_dependencies"]["prediction_reads"] == []


def test_quickml_parity_is_blocked_and_old_success_claim_is_absent(packet):
    design = packet["method_designs"][2]
    assert design["parity_oracle"]["type"] == "blocked"
    assert design["parity_oracle"]["status"] == "BLOCKED"
    assert "No successful legacy parity oracle exists" in design["parity_oracle"]["requirement"]
    encoded = json.dumps(design, ensure_ascii=False, sort_keys=True)
    assert "expected_numbers" not in encoded
    assert "quickml-repeated-low" not in encoded
    assert "can be extracted unchanged" not in encoded
    assert "correcting the loop boundary changes executable semantics" in design["design_rationale"]


def test_quickml_cto_decisions_and_order_asymmetric_vector_are_explicit(packet):
    design = packet["method_designs"][2]
    assert design["blockers_and_cto_decisions"] == [
        "Reject the historical QuickML identity entirely; or",
        "Authorize a separately identified bounds-repaired QuickML strategy; and",
        "Specify the corrected loop boundary and parity contract.",
    ]
    vectors = {item["id"]: item for item in design["synthetic_vectors"]}
    assert set(vectors) == {
        "quickml-method9-minimum-history-crash",
        "quickml-order-asymmetric-source-observation",
    }
    order_input = vectors["quickml-order-asymmetric-source-observation"]["input"]
    assert order_input["newest_row"] != order_input["middle_row"]
    assert order_input["middle_row"] != order_input["older_row"]
    assert "successful legacy output" in vectors["quickml-order-asymmetric-source-observation"]["expected_observation"]


def test_quickml_method9_defect_from_pinned_source_without_import(packet):
    mod = _module()
    path = "tools/quick_ml_predict.py"
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{mod.BASE_COMMIT}:{path}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    source_bytes = completed.stdout
    assert len(source_bytes) == 11213
    assert hashlib.sha256(source_bytes).hexdigest() == (
        "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80"
    )
    tree = ast.parse(source_bytes.decode("utf-8"), filename=path)
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "predict_advanced_ensemble"
    )
    outer = next(
        node
        for node in ast.walk(method)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "i"
        and ast.unparse(node.iter) == "range(3, len(self.df) - 1)"
    )
    pattern_assignment = next(
        node
        for node in outer.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "pattern" for target in node.targets)
    )
    assert ast.unparse(pattern_assignment.value) == "list(self.df.iloc[i:i + 3]['numbers_list'])"
    inner = next(
        node
        for node in ast.walk(outer)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "j"
    )
    assert ast.unparse(inner.iter) == "range(3)"
    assert any(
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "pattern"
        and isinstance(node.slice, ast.Name)
        and node.slice.id == "j"
        for node in ast.walk(inner)
    )

    for history_length in range(5, 101):
        iterations = list(range(3, history_length - 1))
        terminal_i = iterations[-1]
        order_asymmetric_rows = [[row] for row in range(history_length)]
        terminal_pattern = order_asymmetric_rows[terminal_i:terminal_i + 3]
        assert terminal_i == history_length - 2
        assert len(terminal_pattern) == 2
        with pytest.raises(IndexError):
            terminal_pattern[2]

    evidence = packet["method_designs"][2]["semantic_defect_evidence"]
    assert evidence["normalized_outer_loop"] == "range(3, len(df) - 1)"
    assert evidence["terminal_iteration"] == "i = len(df) - 2"
    assert evidence["normalized_pattern_slice"] == "df.iloc[i:i+3]"
    assert evidence["accessed_pattern_indices"] == [0, 1, 2]
    assert evidence["failure"] == "pattern[2] raises IndexError for every history length >= 5"
    assert evidence["candidate_minimum_history_result"] == "cannot produce a successful legacy ticket"
    assert "semantic repair" in evidence["semantic_identity_consequence"]
    assert path[:-3].replace("/", ".") not in sys.modules


def test_quickml_cannot_be_mutated_back_to_ready(packet):
    mod = _module()
    changed = copy.deepcopy(packet)
    quick = changed["method_designs"][2]
    quick["design_status"] = "ADAPTER_OWNED_PURE_EXTRACTION_READY"
    quick["ready_for_implementation"] = True
    quick["readiness_gates"] = {
        "causality_resolved": True,
        "randomness_resolved": True,
        "external_state_resolved": True,
        "identity_distinct": True,
    }
    with pytest.raises(mod.P541DR2ValidationError, match="QuickML fail-closed identity gate"):
        mod.validate_packet(changed)


def test_quickml_defect_evidence_cannot_disappear(packet):
    mod = _module()
    changed = copy.deepcopy(packet)
    changed["method_designs"][2]["semantic_defect_evidence"] = {}
    with pytest.raises(mod.P541DR2ValidationError, match="semantic-defect evidence missing"):
        mod.validate_packet(changed)


@pytest.mark.parametrize("false_claim", ["expected_numbers", "can be extracted unchanged"])
def test_quickml_false_success_or_identity_claim_is_rejected(packet, false_claim):
    mod = _module()
    changed = copy.deepcopy(packet)
    changed["method_designs"][2]["false_claim"] = false_claim
    with pytest.raises(mod.P541DR2ValidationError, match="false success/identity claim"):
        mod.validate_packet(changed)


def test_advanced_optional_dependency_boundary_requires_cto(packet):
    design = packet["method_designs"][0]
    assert design["design_status"] == "CTO_REVIEW_REQUIRED"
    assert design["ready_for_implementation"] is False
    assert design["selected_entrypoint"] is None
    assert "sklearn" in design["design_rationale"]
    assert "XGBoost" in design["design_rationale"]


def test_exact_summary_and_projections(packet):
    mod = _module()
    assert packet["schema_version"] == "p541d-r2-adapter-design-v1"
    assert packet["designer_version"] == "p541d-r2-designer-v2"
    assert packet["summary"] == {
        "selected_methods": 5,
        "counts_by_status": {
            "ADAPTER_OWNED_PURE_EXTRACTION_READY": 0,
            "CTO_REVIEW_REQUIRED": 2,
            "DETERMINISTIC_REIMPLEMENTATION_READY": 1,
            "LAZY_DIRECT_WRAPPER_READY": 1,
            "NOT_AN_ADAPTER_CANDIDATE": 1,
        },
        "implementation_ready_count": 2,
        "cto_review_count": 2,
        "rejected_count": 1,
    }
    assert packet["projections"] == {
        "implementation_ready": [mod.SELECTED_PATHS[1], mod.SELECTED_PATHS[4]],
        "cto_review": [mod.SELECTED_PATHS[0], mod.SELECTED_PATHS[2]],
        "rejected": [mod.SELECTED_PATHS[3]],
    }
    assert [item["design_status"] for item in packet["method_designs"]] == [
        "CTO_REVIEW_REQUIRED",
        "LAZY_DIRECT_WRAPPER_READY",
        "CTO_REVIEW_REQUIRED",
        "NOT_AN_ADAPTER_CANDIDATE",
        "DETERMINISTIC_REIMPLEMENTATION_READY",
    ]
    quick_waves = [
        wave["wave"]
        for wave in packet["implementation_sequencing"]
        if mod.SELECTED_PATHS[2] in wave["methods"]
    ]
    assert quick_waves == ["CTO"]


def test_canonical_adapter_contract_is_reused(packet):
    shared = packet["shared_future_adapter_primitives"]
    assert shared["base"] == "ReplayStrategyAdapter"
    assert shared["metadata"] == "_StrategyMeta"
    assert shared["validation"] == "_validate_numbers"
    assert shared["exceptions"] == [
        "RejectPrediction",
        "InsufficientHistory",
        "InvalidOutput",
        "UnsupportedLotteryType",
    ]
    paths = [item["path"] for item in packet["canonical_adapter_references"]]
    assert paths == _module().ADAPTER_REFERENCE_PATHS


def test_json_markdown_agree(packet):
    mod = _module()
    markdown = mod.render_markdown(packet)
    for design in packet["method_designs"]:
        assert f"`{design['source_path']}`" in markdown
        assert design["design_status"] in markdown
        strategy_id = design["proposed_strategy"]["strategy_id"]
        if strategy_id:
            assert strategy_id in markdown
    assert "Two designs are implementation-ready" in markdown
    assert "two require CTO identity decisions" in markdown
    assert "one is rejected" in markdown
    assert "pattern[2] raises IndexError for every history length >= 5" in markdown
    assert "QuickML parity remains BLOCKED" in markdown
    assert packet["disclaimer"] in markdown


def test_committed_artifact_byte_equality(packet, artifact):
    mod = _module()
    assert artifact == packet
    assert mod.JSON_OUTPUT.read_bytes() == mod.canonical_json_bytes(packet)
    assert mod.MARKDOWN_OUTPUT.read_bytes() == mod.render_markdown(packet).encode("utf-8")


def test_no_absolute_host_paths(packet, artifact):
    mod = _module()
    for encoded in (
        mod.canonical_json_bytes(packet).decode("utf-8"),
        mod.canonical_json_bytes(artifact).decode("utf-8"),
        mod.render_markdown(packet),
    ):
        assert "/Users/" not in encoded
        assert "LotteryNew.worktrees" not in encoded


def test_disclaimer_and_non_claims(packet):
    mod = _module()
    assert packet["disclaimer"] == mod.DISCLAIMER
    assert all(item["disclaimer"] == mod.DISCLAIMER for item in packet["method_designs"])
    assert packet["task"]["design_only"] is True
    assert packet["no_db_no_execution_evidence"]["db_access"] == "NONE"
    assert packet["no_db_no_execution_evidence"]["data_runtime_access"] == "NONE"
    assert all(
        item["proposed_strategy"]["lifecycle"] != "ONLINE"
        for item in packet["method_designs"]
    )
