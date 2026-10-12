"""
tests/test_replay_strategy_lifecycle_endpoint.py
=================================================
P7 tests for GET /api/replay/strategy-lifecycle endpoint.

Rules:
  - No DB write (sqlite3.connect must never be called)
  - No replay execution
  - Endpoint is read-only
  - All assertions are deterministic (sourced from in-memory registry)
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_strategy_lifecycle


def _run(coro):
    """Run an async route function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def response():
    return _run(get_strategy_lifecycle())


# ─── Basic response shape ────────────────────────────────────────────────────

class TestResponseShape:
    def test_total_is_16(self, response):
        assert response["total"] == 16

    def test_lifecycle_counts_present(self, response):
        assert "lifecycle_counts" in response

    def test_executable_strategy_ids_present(self, response):
        assert "executable_strategy_ids" in response

    def test_non_executable_strategy_ids_present(self, response):
        assert "non_executable_strategy_ids" in response

    def test_strategies_list_present(self, response):
        assert "strategies" in response

    def test_no_db_write_field_present(self, response):
        assert "no_db_write" in response

    def test_marker_present(self, response):
        assert "marker" in response

    def test_disclaimer_present(self, response):
        assert "disclaimer" in response


# ─── Lifecycle count assertions ───────────────────────────────────────────────

class TestLifecycleCounts:
    def test_online_count_is_6(self, response):
        assert response["lifecycle_counts"]["ONLINE"] == 6

    def test_rejected_count_is_4(self, response):
        assert response["lifecycle_counts"]["REJECTED"] == 4

    def test_retired_count_is_5(self, response):
        assert response["lifecycle_counts"]["RETIRED"] == 5

    def test_observation_count_is_1(self, response):
        assert response["lifecycle_counts"]["OBSERVATION"] == 1


# ─── Executable / non-executable ────────────────────────────────────────────

class TestExecutability:
    def test_executable_count_is_6(self, response):
        assert len(response["executable_strategy_ids"]) == 6

    def test_non_executable_count_is_10(self, response):
        assert len(response["non_executable_strategy_ids"]) == 10

    def test_executable_and_non_executable_disjoint(self, response):
        exec_set = set(response["executable_strategy_ids"])
        non_exec_set = set(response["non_executable_strategy_ids"])
        assert exec_set.isdisjoint(non_exec_set)

    def test_all_strategy_ids_covered(self, response):
        exec_set = set(response["executable_strategy_ids"])
        non_exec_set = set(response["non_executable_strategy_ids"])
        strat_ids = {s["strategy_id"] for s in response["strategies"]}
        assert exec_set | non_exec_set == strat_ids


# ─── Strategies list ──────────────────────────────────────────────────────────

class TestStrategiesList:
    def test_strategies_length_is_16(self, response):
        assert len(response["strategies"]) == 16

    def test_each_strategy_has_strategy_id(self, response):
        for s in response["strategies"]:
            assert "strategy_id" in s
            assert isinstance(s["strategy_id"], str)
            assert s["strategy_id"]

    def test_each_strategy_has_lifecycle_status(self, response):
        for s in response["strategies"]:
            assert "lifecycle_status" in s
            assert s["lifecycle_status"] in {"ONLINE", "REJECTED", "RETIRED", "OBSERVATION"}

    def test_each_strategy_has_is_executable(self, response):
        for s in response["strategies"]:
            assert "is_executable" in s
            assert isinstance(s["is_executable"], bool)

    def test_online_strategies_are_executable(self, response):
        for s in response["strategies"]:
            if s["lifecycle_status"] == "ONLINE":
                assert s["is_executable"] is True

    def test_non_online_strategies_are_not_executable(self, response):
        for s in response["strategies"]:
            if s["lifecycle_status"] != "ONLINE":
                assert s["is_executable"] is False

    def test_no_callable_in_strategies(self, response):
        """Strategies must not leak adapter objects or callables."""
        for s in response["strategies"]:
            for v in s.values():
                assert not callable(v), f"callable leaked in strategy entry: {s}"


# ─── No DB write ─────────────────────────────────────────────────────────────

class TestNoDbWrite:
    def test_no_db_write_field_is_true(self, response):
        assert response["no_db_write"] is True

    def test_sqlite3_connect_not_called_by_endpoint(self):
        """Endpoint must not open any sqlite3 connection."""
        connect_calls = []
        real_connect = sqlite3.connect

        def _spy(*args, **kwargs):
            connect_calls.append(args)
            return real_connect(*args, **kwargs)

        with patch("sqlite3.connect", side_effect=_spy):
            _run(get_strategy_lifecycle())

        assert connect_calls == [], (
            f"sqlite3.connect was called {len(connect_calls)} time(s): {connect_calls}"
        )


# ─── Marker ───────────────────────────────────────────────────────────────────

class TestMarker:
    def test_marker_value(self, response):
        assert response["marker"] == "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY"
