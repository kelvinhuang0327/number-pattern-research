"""
test_replay_api_contract.py
===========================
P0-5-A  G1 — Replay API Contract Tests

Validates response shape and mandatory fields for:
  GET /api/replay/freshness
  GET /api/replay/summary
  GET /api/replay/history

Source-level: calls FastAPI route functions directly via asyncio.
No live server, no external HTTP calls, no replay generation.
Read-only DB access.

Deliberate-failure probes:
  - test_freshness_contract_fails_without_has_legacy_errors
  - test_summary_contract_fails_without_data_scope
  - test_history_contract_fails_without_records
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"

sys.path.insert(0, str(LOTTERY_API))

from routes.replay import (
    get_replay_freshness,
    get_replay_history,
    get_replay_summary,
)

DB_PATH = LOTTERY_API / "data" / "lottery_v2.db"


def _run(coro):
    """Run an async route function synchronously (new event loop each call)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Wrappers that explicitly supply None for all optional FastAPI Query params
# (direct calls do not go through FastAPI's dependency injection)

def _freshness():
    return _run(get_replay_freshness())


def _summary(lottery_type: str):
    return _run(get_replay_summary(
        lottery_type=lottery_type,
        strategy_id=None,
        date_from=None,
        date_to=None,
    ))


def _history(lottery_type: str, page: int = 1, page_size: int = 50):
    return _run(get_replay_history(
        lottery_type=lottery_type,
        strategy_id=None,
        replay_status=None,
        date_from=None,
        date_to=None,
        page=page,
        page_size=page_size,
    ))


# ── Constants ─────────────────────────────────────────────────────────────────

_COVERAGE_MODES = {"FULL", "LIMITED", "UNKNOWN"}

_FORBIDDEN_IN_SUMMARIES = (
    "SIGNAL",
    "NO_SIGNAL",
    "NO_VALIDATED_EDGE",
    "edge ranking",
    "推薦投注",
)


# ── Contract validators ───────────────────────────────────────────────────────

def _check_freshness_contract(data: Dict[str, Any]) -> None:
    required_fields = [
        "generated_at",
        "coverage_mode",
        "total_rows",
        "total_predicted",
        "total_replay_error",
        "legacy_error_count",
        "has_legacy_errors",
        "lottery_types",
        "latest_run_id",
        "latest_run_status",
        "per_lottery_latest_run",
        "disclaimer",
    ]
    for field in required_fields:
        assert field in data, f"freshness: required field missing: {field!r}"

    assert data["coverage_mode"] in _COVERAGE_MODES, (
        f"freshness: coverage_mode {data['coverage_mode']!r} not in {_COVERAGE_MODES}"
    )
    assert isinstance(data["legacy_error_count"], int), (
        "freshness: legacy_error_count must be int"
    )
    assert data["legacy_error_count"] >= 0, (
        "freshness: legacy_error_count must be >= 0"
    )
    assert isinstance(data["has_legacy_errors"], bool), (
        "freshness: has_legacy_errors must be bool"
    )
    assert isinstance(data["per_lottery_latest_run"], list), (
        "freshness: per_lottery_latest_run must be a list"
    )
    for entry in data["per_lottery_latest_run"]:
        for sub in ("lottery_type", "replay_run_id", "status", "coverage_mode"):
            assert sub in entry, (
                f"freshness: per_lottery_latest_run entry missing {sub!r}"
            )
        assert entry["coverage_mode"] in _COVERAGE_MODES, (
            f"freshness: per_lottery coverage_mode {entry['coverage_mode']!r} invalid"
        )


def _check_summary_contract(data: Dict[str, Any]) -> None:
    required_fields = [
        "lottery_type",
        "summaries",
        "disclaimer",
        "data_scope",
        "legacy_error_count",
        "has_legacy_errors",
    ]
    for field in required_fields:
        assert field in data, f"summary: required field missing: {field!r}"

    assert data["data_scope"] == "ALL_REPLAY_ROWS", (
        f"summary: data_scope must be 'ALL_REPLAY_ROWS', got {data['data_scope']!r}"
    )
    assert isinstance(data["summaries"], list), "summary: summaries must be a list"

    for entry in data["summaries"]:
        for sub in ("strategy_id", "strategy_name", "error_count"):
            assert sub in entry, (
                f"summary: summaries entry missing field {sub!r} "
                f"(strategy_id={entry.get('strategy_id')})"
            )
        entry_str = str(entry)
        for term in _FORBIDDEN_IN_SUMMARIES:
            assert term not in entry_str, (
                f"summary: strategy entry contains forbidden term {term!r}"
            )


def _check_history_contract(data: Dict[str, Any]) -> None:
    required_fields = ["total", "page", "page_size", "pages", "records"]
    for field in required_fields:
        assert field in data, f"history: required field missing: {field!r}"

    assert isinstance(data["records"], list), "history: records must be a list"

    for rec in data["records"]:
        for sub in ("target_draw", "history_cutoff"):
            assert sub in rec, (
                f"history: record id={rec.get('id')} missing required field {sub!r}"
            )


# ── Freshness tests ───────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestFreshnessContract:
    def test_freshness_returns_dict(self):
        assert isinstance(_freshness(), dict)

    def test_freshness_all_required_fields(self):
        _check_freshness_contract(_freshness())

    def test_freshness_coverage_mode_in_allowed_set(self):
        assert _freshness()["coverage_mode"] in _COVERAGE_MODES

    def test_freshness_legacy_error_count_is_nonneg_int(self):
        data = _freshness()
        assert isinstance(data["legacy_error_count"], int)
        assert data["legacy_error_count"] >= 0

    def test_freshness_has_legacy_errors_is_bool(self):
        assert isinstance(_freshness()["has_legacy_errors"], bool)

    def test_freshness_legacy_error_consistency(self):
        """has_legacy_errors must equal (legacy_error_count > 0)."""
        data = _freshness()
        expected = data["legacy_error_count"] > 0
        assert data["has_legacy_errors"] == expected, (
            f"has_legacy_errors={data['has_legacy_errors']} but "
            f"legacy_error_count={data['legacy_error_count']}"
        )

    def test_freshness_per_lottery_coverage_mode_valid(self):
        for entry in _freshness()["per_lottery_latest_run"]:
            assert entry["coverage_mode"] in _COVERAGE_MODES

    def test_freshness_disclaimer_present_and_nonempty(self):
        assert _freshness().get("disclaimer")

    def test_freshness_contract_fails_without_has_legacy_errors(self):
        """Deliberate-failure probe: removing has_legacy_errors must fail contract."""
        data = _freshness()
        stripped = {k: v for k, v in data.items() if k != "has_legacy_errors"}
        with pytest.raises(AssertionError, match="has_legacy_errors"):
            _check_freshness_contract(stripped)

    def test_freshness_contract_fails_without_legacy_error_count(self):
        """Deliberate-failure probe: removing legacy_error_count must fail contract."""
        data = _freshness()
        stripped = {k: v for k, v in data.items() if k != "legacy_error_count"}
        with pytest.raises(AssertionError, match="legacy_error_count"):
            _check_freshness_contract(stripped)


# ── Summary tests ─────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestSummaryContract:
    def test_summary_returns_dict_big_lotto(self):
        assert isinstance(_summary("BIG_LOTTO"), dict)

    def test_summary_all_required_fields(self):
        _check_summary_contract(_summary("BIG_LOTTO"))

    def test_summary_data_scope_all_lottery_types(self):
        for lt in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
            data = _summary(lt)
            assert data.get("data_scope") == "ALL_REPLAY_ROWS", (
                f"summary {lt}: data_scope={data.get('data_scope')!r}"
            )

    def test_summary_has_legacy_errors_field_present(self):
        assert "has_legacy_errors" in _summary("BIG_LOTTO")

    def test_summary_error_count_not_hidden_per_strategy(self):
        """Per-strategy error_count must be visible (not omitted)."""
        for entry in _summary("DAILY_539")["summaries"]:
            assert "error_count" in entry, (
                f"strategy {entry.get('strategy_id')!r} missing error_count"
            )

    def test_summary_disclaimer_present(self):
        assert _summary("BIG_LOTTO").get("disclaimer")

    def test_summary_contract_fails_without_data_scope(self):
        """Deliberate-failure probe: removing data_scope must fail contract."""
        data = _summary("BIG_LOTTO")
        stripped = {k: v for k, v in data.items() if k != "data_scope"}
        with pytest.raises(AssertionError, match="data_scope"):
            _check_summary_contract(stripped)


# ── History tests ─────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestHistoryContract:
    def test_history_returns_dict_big_lotto(self):
        assert isinstance(_history("BIG_LOTTO"), dict)

    def test_history_all_required_fields(self):
        _check_history_contract(_history("BIG_LOTTO"))

    def test_history_uses_records_not_rows(self):
        """Regression guard: key must be 'records', not 'rows'."""
        data = _history("BIG_LOTTO")
        assert "records" in data, "history: must use 'records' key"
        assert "rows" not in data, "history: must NOT use 'rows' key (regression)"

    def test_history_records_have_history_cutoff(self):
        for rec in _history("BIG_LOTTO")["records"]:
            assert "history_cutoff" in rec, f"record id={rec.get('id')} missing history_cutoff"

    def test_history_records_have_target_draw(self):
        for rec in _history("BIG_LOTTO")["records"]:
            assert "target_draw" in rec, f"record id={rec.get('id')} missing target_draw"

    def test_history_pagination_shape(self):
        data = _history("BIG_LOTTO", page=1, page_size=10)
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert "pages" in data

    def test_history_contract_fails_without_records(self):
        """Deliberate-failure probe: removing 'records' must fail contract."""
        data = _history("BIG_LOTTO")
        stripped = {k: v for k, v in data.items() if k != "records"}
        with pytest.raises(AssertionError, match="records"):
            _check_history_contract(stripped)

    def test_history_all_lottery_types_respond(self):
        for lt in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
            _check_history_contract(_history(lt))
