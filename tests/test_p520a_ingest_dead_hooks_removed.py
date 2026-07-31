"""P520A — dead after-insert hooks removed from lottery_api/routes/ingest.py.

The ingest route previously imported engine.prediction_tracker and
engine.snapshot_scheduler inside try/except blocks, but both modules are
absent from the tree (see P271H/P271I audits), so the hooks could only emit
warnings. These tests pin the removal at source/AST level — no app import,
no database access.
"""
import ast
from pathlib import Path

INGEST_PATH = Path(__file__).resolve().parents[1] / "lottery_api" / "routes" / "ingest.py"


def _source() -> str:
    return INGEST_PATH.read_text(encoding="utf-8")


def test_no_dead_module_references():
    src = _source()
    assert "snapshot_scheduler" not in src
    assert "prediction_tracker" not in src


def test_schedule_after_insert_function_and_call_sites_removed():
    src = _source()
    assert "_schedule_after_insert" not in src
    fn_names = {
        node.name
        for node in ast.walk(ast.parse(src))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_schedule_after_insert" not in fn_names


def test_live_after_insert_hooks_preserved():
    src = _source()
    fn_names = {
        node.name
        for node in ast.walk(ast.parse(src))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_refresh_after_insert" in fn_names
    assert "scheduler.load_data" in src
    for removed_hook in ("refresh_hedge_fund_outputs",
                         "weight_adjuster", "learning_integrator"):
        assert removed_hook not in src
