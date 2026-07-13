"""Focused static/no-DB contract tests for the P541D_R2 design packet."""
import ast
import builtins
import copy
import inspect
import json
import os
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


def test_quickml_has_no_temporary_csv_plan(packet):
    design = packet["method_designs"][2]
    assert design["design_status"] == "ADAPTER_OWNED_PURE_EXTRACTION_READY"
    assert "temporary CSV" in design["external_state_and_dependencies"]["forbidden_legacy_reads"]
    assert "Never import or construct" in design["import_safety_plan"]
    assert "without pandas or CSV" in design["input_output_normalization"]["input"]


def test_advanced_optional_dependency_boundary_requires_cto(packet):
    design = packet["method_designs"][0]
    assert design["design_status"] == "CTO_REVIEW_REQUIRED"
    assert design["ready_for_implementation"] is False
    assert design["selected_entrypoint"] is None
    assert "sklearn" in design["design_rationale"]
    assert "XGBoost" in design["design_rationale"]


def test_exact_summary_and_projections(packet):
    mod = _module()
    assert packet["summary"] == {
        "selected_methods": 5,
        "counts_by_status": {
            "ADAPTER_OWNED_PURE_EXTRACTION_READY": 1,
            "CTO_REVIEW_REQUIRED": 1,
            "DETERMINISTIC_REIMPLEMENTATION_READY": 1,
            "LAZY_DIRECT_WRAPPER_READY": 1,
            "NOT_AN_ADAPTER_CANDIDATE": 1,
        },
        "implementation_ready_count": 3,
        "cto_review_count": 1,
        "rejected_count": 1,
    }
    assert packet["projections"] == {
        "implementation_ready": mod.SELECTED_PATHS[1:3] + [mod.SELECTED_PATHS[4]],
        "cto_review": [mod.SELECTED_PATHS[0]],
        "rejected": [mod.SELECTED_PATHS[3]],
    }


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
    assert "Three designs are implementation-ready" in markdown
    assert "one requires a CTO identity decision" in markdown
    assert "one is rejected" in markdown
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
