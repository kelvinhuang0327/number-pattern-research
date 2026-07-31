"""P521A no-DB mocked smoke for the active after-insert scheduler surface.

This test reads and executes only an extracted source-level helper from
lottery_api/routes/ingest.py. It does not import lottery_api.routes.ingest,
does not import the real scheduler, does not execute draw inserts, and does
not open or write a database.
"""
from __future__ import annotations

import ast
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_PATH = REPO_ROOT / "lottery_api" / "routes" / "ingest.py"

REMOVED_HOOK_RESIDUE = {
    "_MISSING_AFTERINSERT_HOOKS_ENABLED",
    "refresh_hedge_fund_outputs",
    "weight_adjuster",
    "learning_integrator",
    "_schedule_after_insert",
    "snapshot_scheduler",
    "prediction_tracker",
}


class FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def load_data(self) -> None:
        self.calls.append("load_data")


class FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _function_named(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} missing")


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and _call_name(child.func) == name
    ]


def _compile_refresh_function(refresh_function: ast.FunctionDef, fake_import):
    module = ast.Module(body=[refresh_function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {
        "__builtins__": {
            "__import__": fake_import,
            "Exception": Exception,
        },
        "logger": FakeLogger(),
    }
    exec(compile(module, filename=str(INGEST_PATH), mode="exec"), namespace)
    return namespace["_refresh_after_insert"]


def test_afterinsert_refresh_source_reaches_fake_scheduler_load_data_once():
    source = INGEST_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(INGEST_PATH))

    for residue in sorted(REMOVED_HOOK_RESIDUE):
        assert residue not in source, residue

    refresh_function = _function_named(tree, "_refresh_after_insert")
    assert "after new data inserted" in ast.get_docstring(refresh_function)

    scheduler_imports = [
        node
        for node in ast.walk(refresh_function)
        if isinstance(node, ast.ImportFrom)
        and node.module == "utils.scheduler"
        and [alias.name for alias in node.names] == ["scheduler"]
    ]
    scheduler_calls = _calls_named(refresh_function, "scheduler.load_data")
    refresh_call_sites = _calls_named(tree, "_refresh_after_insert")

    assert len(scheduler_imports) == 1
    assert len(scheduler_calls) == 1
    assert "scheduler.load_data()" in source
    assert len(refresh_call_sites) == 2

    fake_scheduler = FakeScheduler()
    imported_modules: list[tuple[str, tuple[str, ...]]] = []

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        imported_modules.append((name, tuple(fromlist)))
        if name == "utils.scheduler" and tuple(fromlist) == ("scheduler",):
            return types.SimpleNamespace(scheduler=fake_scheduler)
        raise AssertionError(f"unexpected import: {name!r} fromlist={fromlist!r}")

    refresh_after_insert = _compile_refresh_function(refresh_function, fake_import)

    refresh_after_insert()

    assert imported_modules == [("utils.scheduler", ("scheduler",))]
    assert fake_scheduler.calls == ["load_data"]
