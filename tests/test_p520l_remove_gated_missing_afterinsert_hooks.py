"""P520L source-only checks for removed gated missing after-insert hooks.

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
ARTIFACT_PREFIX = "P520L_remove_gated_missing_afterinsert_hooks"
ARTIFACT_DIR = REPO_ROOT / "artifacts"

MISSING_HOOK_RESIDUE = {
    "_MISSING_AFTERINSERT_HOOKS_ENABLED",
    "refresh_hedge_fund_outputs",
    "analysis.payout.sync",
    "weight_adjuster",
    "engine.weight_adjuster",
    "adjust_all_types",
    "learning_integrator",
    "engine.learning_integrator",
    "apply_all_types",
    "apply_learning",
}
REMOVED_DEAD_SYMBOLS = {
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
}


def _source_and_tree() -> tuple[str, ast.Module]:
    source = INGEST_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(INGEST_PATH))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _refresh_function(tree: ast.AST) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_refresh_after_insert":
            return node
    raise AssertionError("_refresh_after_insert missing")


def test_gated_missing_hook_residue_is_removed_from_ingest_source():
    source, _ = _source_and_tree()

    for residue in sorted(MISSING_HOOK_RESIDUE | REMOVED_DEAD_SYMBOLS):
        assert residue not in source, residue


def test_scheduler_load_data_remains_active_in_refresh_after_insert():
    source, tree = _source_and_tree()
    refresh_function = _refresh_function(tree)
    calls = [
        node
        for node in ast.walk(refresh_function)
        if isinstance(node, ast.Call) and _call_name(node.func) == "scheduler.load_data"
    ]
    scheduler_imports = [
        node
        for node in ast.walk(refresh_function)
        if isinstance(node, ast.ImportFrom)
        and node.module == "utils.scheduler"
        and any(alias.name == "scheduler" for alias in node.names)
    ]

    assert len(calls) == 1
    assert len(scheduler_imports) == 1
    assert "scheduler.load_data()" in source


def test_p520l_artifacts_are_parseable_and_match_source_state():
    result = json.loads((ARTIFACT_DIR / f"{ARTIFACT_PREFIX}_result.json").read_text(encoding="utf-8"))
    delta = json.loads(
        (ARTIFACT_DIR / f"{ARTIFACT_PREFIX}_acceptance_delta.json").read_text(encoding="utf-8")
    )
    removed_rows = list(
        csv.DictReader(
            (ARTIFACT_DIR / f"{ARTIFACT_PREFIX}_removed_matrix.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    retained_rows = list(
        csv.DictReader(
            (ARTIFACT_DIR / f"{ARTIFACT_PREFIX}_retained_active_surface.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    manifest_rows = list(
        csv.DictReader(
            (ARTIFACT_DIR / f"{ARTIFACT_PREFIX}_manifest.csv").read_text(encoding="utf-8").splitlines()
        )
    )

    assert result["final_status"] == "PASS"
    assert result["missing_hook_residue_present"] == []
    assert result["scheduler_load_data_retained"] is True
    assert delta["p520k_final_status_before"] == "WARN"
    assert delta["p520k_final_status_after"] == "PASS"
    assert {row["hook_name"] for row in removed_rows} == {
        "refresh_hedge_fund_outputs",
        "weight_adjuster",
        "learning_integrator",
    }
    assert [row["surface_name"] for row in retained_rows] == ["scheduler.load_data"]
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
    assert "utils.scheduler" not in imported_modules
    assert "sqlite3" not in imported_modules
