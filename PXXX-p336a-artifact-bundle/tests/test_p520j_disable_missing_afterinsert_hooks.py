"""P520J source-only checks for removed missing after-insert hook targets.

These tests parse source and committed artifacts only. They do not import
lottery_api.routes.ingest, do not import live hook target modules, do not
execute hooks or draw inserts, do not open or write a database, do not run
migrations/backfills, and do not deploy.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_PATH = REPO_ROOT / "lottery_api" / "routes" / "ingest.py"
P520I_BINDING_PATH = REPO_ROOT / "artifacts" / "P520I_ingest_afterinsert_hook_static_binding_resolver_binding_chain.csv"
P520J_RESULT_PATH = REPO_ROOT / "artifacts" / "P520J_disable_missing_afterinsert_hooks_result.json"
P520J_DISABLED_MATRIX_PATH = (
    REPO_ROOT / "artifacts" / "P520J_disable_missing_afterinsert_hooks_disabled_matrix.csv"
)
P520J_RETAINED_HOOKS_PATH = REPO_ROOT / "artifacts" / "P520J_disable_missing_afterinsert_hooks_retained_hooks.csv"
P520J_WARNING_EVIDENCE_PATH = (
    REPO_ROOT / "artifacts" / "P520J_disable_missing_afterinsert_hooks_warning_only_evidence.json"
)
P520J_MANIFEST_PATH = REPO_ROOT / "artifacts" / "P520J_disable_missing_afterinsert_hooks_manifest.csv"

DISABLED_FLAG = "_MISSING_AFTERINSERT_HOOKS_ENABLED"
MISSING_HOOKS = {
    "refresh_hedge_fund_outputs": {
        "import_module": "analysis.payout.sync",
        "imported_symbol": "refresh_hedge_fund_outputs",
        "local_symbol": "refresh_hedge_fund_outputs",
        "call_name": "refresh_hedge_fund_outputs",
        "warning_fragment": "refresh_hedge_fund_outputs() failed",
    },
    "weight_adjuster": {
        "import_module": "engine.weight_adjuster",
        "imported_symbol": "adjust_all_types",
        "local_symbol": "adjust_all_types",
        "call_name": "adjust_all_types",
        "warning_fragment": "weight_adjuster after resolve failed",
    },
    "learning_integrator": {
        "import_module": "engine.learning_integrator",
        "imported_symbol": "apply_all_types",
        "local_symbol": "apply_learning",
        "call_name": "apply_learning",
        "warning_fragment": "learning_integrator after weight_adjuster failed",
    },
}


def _ingest_source_and_tree() -> tuple[str, ast.Module]:
    source = INGEST_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(INGEST_PATH))


def _refresh_function(tree: ast.AST) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_refresh_after_insert":
            return node
    raise AssertionError("_refresh_after_insert missing")


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _ancestors(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    chain = []
    while node in parents:
        node = parents[node]
        chain.append(node)
    return chain


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _disabled_guard_node(refresh_function: ast.FunctionDef) -> ast.If:
    for node in ast.walk(refresh_function):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == DISABLED_FLAG:
            return node
    raise AssertionError("disabled missing-hook guard not found")


def _missing_hook_nodes(refresh_function: ast.FunctionDef) -> dict[str, dict[str, ast.AST]]:
    found: dict[str, dict[str, ast.AST]] = {name: {} for name in MISSING_HOOKS}
    for node in ast.walk(refresh_function):
        if isinstance(node, ast.ImportFrom):
            for name, spec in MISSING_HOOKS.items():
                if node.module != spec["import_module"]:
                    continue
                if any(
                    alias.name == spec["imported_symbol"]
                    and (alias.asname or alias.name) == spec["local_symbol"]
                    for alias in node.names
                ):
                    found[name]["import"] = node
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            for name, spec in MISSING_HOOKS.items():
                if call_name == spec["call_name"]:
                    found[name]["call"] = node
    return found


def test_missing_target_guard_and_source_residue_are_removed():
    source, tree = _ingest_source_and_tree()

    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == DISABLED_FLAG for target in node.targets)
    ]

    assert assignments == []
    assert DISABLED_FLAG not in source
    assert "from utils.scheduler import scheduler" in source
    assert "scheduler.load_data()" in source
    for hook_name, spec in MISSING_HOOKS.items():
        assert hook_name not in source
        assert spec["import_module"] not in source
        assert spec["imported_symbol"] not in source
        assert spec["local_symbol"] not in source


def test_scheduler_is_the_only_after_insert_completion_surface():
    _, tree = _ingest_source_and_tree()
    refresh_function = _refresh_function(tree)
    nodes_by_hook = _missing_hook_nodes(refresh_function)

    assert set(nodes_by_hook) == set(MISSING_HOOKS)
    for hook_name, nodes in nodes_by_hook.items():
        assert nodes == {}, hook_name

    scheduler_calls = [
        node
        for node in ast.walk(refresh_function)
        if isinstance(node, ast.Call) and _call_name(node.func) == "scheduler.load_data"
    ]
    assert len(scheduler_calls) == 1


def test_removed_missing_target_warning_blocks_are_absent():
    source, tree = _ingest_source_and_tree()
    refresh_function = _refresh_function(tree)
    nodes_by_hook = _missing_hook_nodes(refresh_function)

    assert all(nodes == {} for nodes in nodes_by_hook.values())
    for spec in MISSING_HOOKS.values():
        assert spec["warning_fragment"] not in source


def test_p520i_artifacts_no_longer_feed_active_or_disabled_missing_surface():
    rows = {
        row["hook_name"]: row
        for row in csv.DictReader(P520I_BINDING_PATH.read_text(encoding="utf-8").splitlines())
    }

    assert rows == {}


def test_removed_dead_hook_symbols_remain_absent_from_ingest_source():
    source = INGEST_PATH.read_text(encoding="utf-8")

    assert "_schedule_after_insert" not in source
    assert "snapshot_scheduler" not in source
    assert "prediction_tracker" not in source


def test_p520j_artifacts_are_parseable_and_match_source_state():
    result = json.loads(P520J_RESULT_PATH.read_text(encoding="utf-8"))
    warning_evidence = json.loads(P520J_WARNING_EVIDENCE_PATH.read_text(encoding="utf-8"))
    disabled_rows = list(
        csv.DictReader(P520J_DISABLED_MATRIX_PATH.read_text(encoding="utf-8").splitlines())
    )
    retained_rows = list(
        csv.DictReader(P520J_RETAINED_HOOKS_PATH.read_text(encoding="utf-8").splitlines())
    )
    manifest_rows = list(csv.DictReader(P520J_MANIFEST_PATH.read_text(encoding="utf-8").splitlines()))

    assert result["final_status"] == "PASS"
    assert result["disabled_missing_hook_count"] == 0
    assert result["removed_missing_hook_count"] == 3
    assert result["retained_hook_count"] == 1
    assert result["scheduler_load_data_retained"] is True
    assert result["runtime_import_avoided"] is True
    assert {row["hook_name"] for row in disabled_rows} == set(MISSING_HOOKS)
    assert {row["status"] for row in disabled_rows} == {"REMOVED"}
    assert [row["hook_name"] for row in retained_rows] == ["scheduler.load_data"]
    assert set(warning_evidence["hooks"]) == set(MISSING_HOOKS)
    assert len(manifest_rows) == 6
    assert manifest_rows[-1]["sha256"] == ""


def test_this_test_module_does_not_import_runtime_targets():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert "lottery_api.routes.ingest" not in imported_modules
    assert "analysis.payout.sync" not in imported_modules
    assert "engine.weight_adjuster" not in imported_modules
    assert "engine.learning_integrator" not in imported_modules
    assert "sqlite3" not in imported_modules
