"""P520B source checks for stale archived ingest hook references.

These tests parse source files only. They do not import app modules, do not
open or write a database, do not run migrations/backfills, do not deploy, and
make no betting or future prediction claims.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_SMOKE_PATH = REPO_ROOT / "analysis" / "p255d_ingest_write_guard_runtime_smoke_governance_closure.py"
INGEST_ROUTE_PATH = REPO_ROOT / "lottery_api" / "routes" / "ingest.py"
THIS_TEST_PATH = Path(__file__).resolve()


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> ast.AST:
    return ast.parse(_source(path), filename=str(path))


def _referenced_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _string_literals(tree: ast.AST) -> set[str]:
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def test_archived_smoke_script_no_longer_references_removed_after_insert_hook():
    src = _source(ARCHIVED_SMOKE_PATH)
    tree = ast.parse(src, filename=str(ARCHIVED_SMOKE_PATH))

    assert "_schedule_after_insert" not in src
    assert "_schedule_after_insert" not in _referenced_names(tree)


def test_ingest_route_has_no_removed_after_insert_hook_or_dead_scheduler_modules():
    src = _source(INGEST_ROUTE_PATH)
    tree = ast.parse(src, filename=str(INGEST_ROUTE_PATH))
    names = _referenced_names(tree)

    for removed_name in ("_schedule_after_insert", "snapshot_scheduler", "prediction_tracker"):
        assert removed_name not in src
        assert removed_name not in names


def test_this_regression_check_imports_no_app_modules_and_names_no_db_path():
    tree = _parse(THIS_TEST_PATH)
    imported_modules = _imported_modules(tree)
    string_literals = _string_literals(tree)

    forbidden_import_prefixes = ("lottery_api", "routes", "engine", "database", "db")
    forbidden_db_name = "lottery_v2" + ".db"
    for module in imported_modules:
        assert not module.startswith(forbidden_import_prefixes)
    assert "sqlite3" not in imported_modules
    assert all(forbidden_db_name not in literal for literal in string_literals)
