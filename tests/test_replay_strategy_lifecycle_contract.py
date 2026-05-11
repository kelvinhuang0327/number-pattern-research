"""
test_replay_strategy_lifecycle_contract.py
==========================================
P10 — Strategy Lifecycle Endpoint Contract / Snapshot Tests

Validates the stable response contract for:
  GET /api/replay/strategy-lifecycle

Source-level: calls FastAPI route function directly via asyncio.
No live server, no external HTTP calls, no DB write, no replay generation.

Covers 10 contract assertions:
  1.  Endpoint response has stable top-level keys
  2.  lifecycle_counts schema is stable
  3.  total = 16
  4.  marker = P7_STRATEGY_LIFECYCLE_ENDPOINT_READY
  5.  no_db_write = True
  6.  strategies entries only contain allowed metadata keys
  7.  strategies list has deterministic (stable) ordering
  8.  response contains no callable / adapter object representation
  9.  executable_strategy_ids and non_executable_strategy_ids do not overlap
  10. API contract doc mentions all top-level response fields
"""
from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
DOCS_CONTRACT = (
    REPO_ROOT / "docs" / "replay" / "strategy_lifecycle_endpoint_contract.md"
)

sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_strategy_lifecycle


def _run(coro):
    """Run an async route function in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Module-scoped fixture: call the endpoint once, reuse across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def lifecycle_response():
    return _run(get_strategy_lifecycle())


# ---------------------------------------------------------------------------
# Expected constants
# ---------------------------------------------------------------------------

_EXPECTED_TOP_LEVEL_KEYS = frozenset({
    "total",
    "lifecycle_counts",
    "executable_strategy_ids",
    "non_executable_strategy_ids",
    "strategies",
    "no_db_write",
    "no_db_write_note",
    "marker",
    "disclaimer",
})

_EXPECTED_LIFECYCLE_COUNT_KEYS = frozenset({"ONLINE", "REJECTED", "RETIRED", "OBSERVATION"})

_ALLOWED_STRATEGY_KEYS = frozenset({
    "strategy_id",
    "strategy_name",
    "strategy_version",
    "supported_lottery_types",
    "min_history",
    "lifecycle_status",
    "is_executable",
})


# ---------------------------------------------------------------------------
# 1. Stable top-level keys
# ---------------------------------------------------------------------------

class TestTopLevelKeys:
    def test_response_has_all_expected_keys(self, lifecycle_response):
        assert _EXPECTED_TOP_LEVEL_KEYS == set(lifecycle_response.keys()), (
            f"Top-level keys mismatch. "
            f"Missing: {_EXPECTED_TOP_LEVEL_KEYS - set(lifecycle_response.keys())}, "
            f"Extra: {set(lifecycle_response.keys()) - _EXPECTED_TOP_LEVEL_KEYS}"
        )

    def test_no_unexpected_top_level_keys(self, lifecycle_response):
        extra = set(lifecycle_response.keys()) - _EXPECTED_TOP_LEVEL_KEYS
        assert not extra, f"Unexpected top-level keys: {extra}"


# ---------------------------------------------------------------------------
# 2. lifecycle_counts schema
# ---------------------------------------------------------------------------

class TestLifecycleCountsSchema:
    def test_lifecycle_counts_is_dict(self, lifecycle_response):
        assert isinstance(lifecycle_response["lifecycle_counts"], dict)

    def test_lifecycle_counts_has_all_status_keys(self, lifecycle_response):
        assert _EXPECTED_LIFECYCLE_COUNT_KEYS == set(lifecycle_response["lifecycle_counts"].keys()), (
            f"lifecycle_counts keys mismatch: "
            f"{set(lifecycle_response['lifecycle_counts'].keys())}"
        )

    def test_lifecycle_counts_values_are_int(self, lifecycle_response):
        for k, v in lifecycle_response["lifecycle_counts"].items():
            assert isinstance(v, int), f"lifecycle_counts[{k!r}] is not int: {v!r}"

    def test_lifecycle_counts_sum_equals_total(self, lifecycle_response):
        counts_sum = sum(lifecycle_response["lifecycle_counts"].values())
        assert counts_sum == lifecycle_response["total"], (
            f"lifecycle_counts sum {counts_sum} != total {lifecycle_response['total']}"
        )


# ---------------------------------------------------------------------------
# 3. total = 16
# ---------------------------------------------------------------------------

class TestTotal:
    def test_total_is_16(self, lifecycle_response):
        assert lifecycle_response["total"] == 16

    def test_strategies_list_length_matches_total(self, lifecycle_response):
        assert len(lifecycle_response["strategies"]) == lifecycle_response["total"]


# ---------------------------------------------------------------------------
# 4. marker
# ---------------------------------------------------------------------------

class TestMarker:
    def test_marker_value(self, lifecycle_response):
        assert lifecycle_response["marker"] == "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY"

    def test_marker_is_string(self, lifecycle_response):
        assert isinstance(lifecycle_response["marker"], str)


# ---------------------------------------------------------------------------
# 5. no_db_write = True
# ---------------------------------------------------------------------------

class TestNoDbWrite:
    def test_no_db_write_is_true(self, lifecycle_response):
        assert lifecycle_response["no_db_write"] is True

    def test_no_db_write_note_is_string(self, lifecycle_response):
        assert isinstance(lifecycle_response["no_db_write_note"], str)
        assert len(lifecycle_response["no_db_write_note"]) > 0


# ---------------------------------------------------------------------------
# 6. strategies entries only contain allowed metadata keys
# ---------------------------------------------------------------------------

class TestStrategyEntryKeys:
    def test_all_strategy_entries_have_only_allowed_keys(self, lifecycle_response):
        for s in lifecycle_response["strategies"]:
            extra = set(s.keys()) - _ALLOWED_STRATEGY_KEYS
            assert not extra, f"strategy {s.get('strategy_id')!r} has unexpected keys: {extra}"

    def test_all_strategy_entries_have_required_keys(self, lifecycle_response):
        required = {"strategy_id", "lifecycle_status", "is_executable"}
        for s in lifecycle_response["strategies"]:
            missing = required - set(s.keys())
            assert not missing, (
                f"strategy {s.get('strategy_id')!r} missing required keys: {missing}"
            )

    def test_strategy_id_is_string(self, lifecycle_response):
        for s in lifecycle_response["strategies"]:
            assert isinstance(s["strategy_id"], str) and s["strategy_id"]

    def test_lifecycle_status_is_string(self, lifecycle_response):
        valid_statuses = {"ONLINE", "REJECTED", "RETIRED", "OBSERVATION"}
        for s in lifecycle_response["strategies"]:
            assert s["lifecycle_status"] in valid_statuses, (
                f"strategy {s['strategy_id']!r} has unexpected lifecycle_status: "
                f"{s['lifecycle_status']!r}"
            )

    def test_is_executable_is_bool(self, lifecycle_response):
        for s in lifecycle_response["strategies"]:
            assert isinstance(s["is_executable"], bool), (
                f"strategy {s['strategy_id']!r} is_executable is not bool: "
                f"{s['is_executable']!r}"
            )


# ---------------------------------------------------------------------------
# 7. strategies ordering is deterministic (stable across calls)
# ---------------------------------------------------------------------------

class TestStrategyOrdering:
    def test_strategies_ordering_is_stable(self):
        """Calling the endpoint twice should yield the same strategy order."""
        r1 = _run(get_strategy_lifecycle())
        r2 = _run(get_strategy_lifecycle())
        ids1 = [s["strategy_id"] for s in r1["strategies"]]
        ids2 = [s["strategy_id"] for s in r2["strategies"]]
        assert ids1 == ids2, "strategies ordering is not deterministic across calls"


# ---------------------------------------------------------------------------
# 8. No callable / adapter objects in response
# ---------------------------------------------------------------------------

class TestNoCallablesInResponse:
    def test_strategy_entries_contain_no_callables(self, lifecycle_response):
        for s in lifecycle_response["strategies"]:
            for k, v in s.items():
                assert not callable(v), (
                    f"strategy {s.get('strategy_id')!r} key {k!r} is callable: {v!r}"
                )

    def test_strategy_entries_contain_no_class_instances(self, lifecycle_response):
        """Entries must only contain JSON-serialisable primitives."""
        import json
        for s in lifecycle_response["strategies"]:
            try:
                json.dumps(s)
            except TypeError as exc:
                pytest.fail(
                    f"strategy {s.get('strategy_id')!r} is not JSON-serialisable: {exc}"
                )


# ---------------------------------------------------------------------------
# 9. executable_strategy_ids and non_executable_strategy_ids do not overlap
# ---------------------------------------------------------------------------

class TestIdSets:
    def test_exec_and_non_exec_ids_are_disjoint(self, lifecycle_response):
        exec_set = set(lifecycle_response["executable_strategy_ids"])
        non_exec_set = set(lifecycle_response["non_executable_strategy_ids"])
        overlap = exec_set & non_exec_set
        assert not overlap, f"IDs appear in both exec and non_exec lists: {overlap}"

    def test_exec_plus_non_exec_equals_total(self, lifecycle_response):
        total = (
            len(lifecycle_response["executable_strategy_ids"])
            + len(lifecycle_response["non_executable_strategy_ids"])
        )
        assert total == lifecycle_response["total"], (
            f"exec ({len(lifecycle_response['executable_strategy_ids'])}) + "
            f"non_exec ({len(lifecycle_response['non_executable_strategy_ids'])}) "
            f"!= total ({lifecycle_response['total']})"
        )

    def test_only_online_strategies_are_executable(self, lifecycle_response):
        exec_ids = set(lifecycle_response["executable_strategy_ids"])
        for s in lifecycle_response["strategies"]:
            if s["lifecycle_status"] == "ONLINE":
                assert s["strategy_id"] in exec_ids, (
                    f"ONLINE strategy {s['strategy_id']!r} not in executable_strategy_ids"
                )
            else:
                assert s["strategy_id"] not in exec_ids, (
                    f"non-ONLINE strategy {s['strategy_id']!r} (status={s['lifecycle_status']!r}) "
                    f"unexpectedly in executable_strategy_ids"
                )


# ---------------------------------------------------------------------------
# 10. API contract doc mentions all top-level response fields
# ---------------------------------------------------------------------------

class TestContractDocCompleteness:
    def test_contract_doc_exists(self):
        assert DOCS_CONTRACT.exists(), (
            f"Contract doc not found: {DOCS_CONTRACT}"
        )

    def test_contract_doc_mentions_all_top_level_fields(self, lifecycle_response):
        if not DOCS_CONTRACT.exists():
            pytest.skip("Contract doc not present — skipping doc completeness check")
        doc_text = DOCS_CONTRACT.read_text(encoding="utf-8")
        for key in _EXPECTED_TOP_LEVEL_KEYS:
            assert key in doc_text, (
                f"Contract doc does not mention top-level field: {key!r}"
            )
