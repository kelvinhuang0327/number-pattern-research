"""Focused static tests for the smart-betting wheel generation API contract.

No DB, no service startup, no runtime artifacts: these assertions verify the
static frontend call matches the existing FastAPI route declaration.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT = REPO_ROOT / "src/ui/components/SmartBettingComponent.js"
PREDICTION_ROUTE = REPO_ROOT / "lottery_api/routes/prediction.py"


def _component() -> str:
    return COMPONENT.read_text(encoding="utf-8")


def _generate_combinations_block() -> str:
    script = _component()
    return script.split("async generateCombinations()", 1)[1].split(
        "    hasConsecutive(numbers, count)", 1
    )[0]


def _wheel_route_block() -> str:
    route = PREDICTION_ROUTE.read_text(encoding="utf-8")
    return route.split('@router.post("/api/wheel/generate")', 1)[1].split(
        '@router.get("/api/wheel/available-guarantees")', 1
    )[0]


def test_frontend_uses_post_for_backend_wheel_generate_route() -> None:
    block = _generate_combinations_block()
    assert '@router.post("/api/wheel/generate")' in PREDICTION_ROUTE.read_text(
        encoding="utf-8"
    )
    assert "fetch(`/api/wheel/generate?${wheelParams.toString()}`" in block
    assert "method: 'POST'" in block
    assert "fetch(`/api/wheel/generate?pool=${JSON.stringify(nums)}" not in block


def test_frontend_url_encodes_wheel_query_parameters() -> None:
    block = _generate_combinations_block()
    assert "new URLSearchParams({" in block
    assert "pool: JSON.stringify(nums)" in block
    assert "guarantee_t: String(guarantee_t || 3)" in block
    assert "condition_m: String(condition_m || 4)" in block
    assert "wheelParams.toString()" in block


def test_backend_route_still_expects_query_params_not_body() -> None:
    block = _wheel_route_block()
    assert "pool: List[int] = Query(" in block
    assert "guarantee_t: int = Query(" in block
    assert "condition_m: int = Query(" in block


def test_no_db_service_or_mutation_behavior_added() -> None:
    block = _generate_combinations_block()
    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "method: 'DELETE'",
        "method: 'PUT'",
        "method: 'PATCH'",
    ):
        assert forbidden not in block
