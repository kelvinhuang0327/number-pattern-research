"""
tests/test_replay_strategy_lifecycle_exposure.py
=================================================
P3 tests for the lifecycle exposure API and CLI report script.

Rules:
  - No DB write (sqlite3.connect must never be called)
  - No replay execution
  - Non-ONLINE stubs must NOT be executable
  - Ordering must be deterministic
"""
from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Optional

import pytest

# ─── Imports under test ──────────────────────────────────────────────────────
import lottery_api.models.replay_strategy_registry as _reg

from lottery_api.models.replay_strategy_registry import (
    LifecycleNotExecutable,
    list_strategy_lifecycle_metadata,
    get_strategy_lifecycle_metadata,
    summarize_strategy_lifecycle_counts,
    list_executable_strategy_ids,
    list_non_executable_strategy_ids,
    _REGISTRY,
    _ALL_ADAPTERS,
    LIFECYCLE_STATUSES,
)

# ─── Required canonical identities; aggregate counts remain dynamic ──────────
_REQUIRED_ONLINE_IDS = frozenset({
    "power_precision_3bet",
    "power_orthogonal_5bet",
    "fourier_rhythm_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "ts3_regime_3bet",
    "daily539_f4cold",
    "daily539_markov_cold",
})
_REQUIRED_NON_EXEC_IDS = frozenset({
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq",
    "p1_deviation_2bet_539",
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
})


# ═══════════════════════════════════════════════════════════════════════════════
# TestListStrategyLifecycleMetadata
# ═══════════════════════════════════════════════════════════════════════════════

class TestListStrategyLifecycleMetadata:
    def test_returns_the_live_unique_adapter_universe(self):
        result = list_strategy_lifecycle_metadata()
        result_ids = [entry["strategy_id"] for entry in result]
        adapter_ids = [adapter.meta.strategy_id for adapter in _ALL_ADAPTERS]
        assert result_ids == adapter_ids
        assert len(result_ids) == len(set(result_ids))

    def test_each_entry_has_required_keys(self):
        required = {
            "strategy_id", "strategy_name", "strategy_version",
            "supported_lottery_types", "min_history", "lifecycle_status",
        }
        for entry in list_strategy_lifecycle_metadata():
            assert required.issubset(entry.keys()), (
                f"Entry missing keys: {required - entry.keys()}"
            )

    def test_filter_by_online(self):
        result = list_strategy_lifecycle_metadata(lifecycle_status="ONLINE")
        assert all(e["lifecycle_status"] == "ONLINE" for e in result)
        assert {entry["strategy_id"] for entry in result} == set(_REGISTRY)

    def test_filter_by_rejected(self):
        result = list_strategy_lifecycle_metadata(lifecycle_status="REJECTED")
        assert all(e["lifecycle_status"] == "REJECTED" for e in result)
        assert {entry["strategy_id"] for entry in result} == {
            adapter.meta.strategy_id
            for adapter in _ALL_ADAPTERS
            if adapter.meta.lifecycle_status == "REJECTED"
        }

    def test_filter_by_retired(self):
        result = list_strategy_lifecycle_metadata(lifecycle_status="RETIRED")
        assert all(e["lifecycle_status"] == "RETIRED" for e in result)

    def test_filter_by_observation(self):
        result = list_strategy_lifecycle_metadata(lifecycle_status="OBSERVATION")
        assert all(e["lifecycle_status"] == "OBSERVATION" for e in result)

    def test_ids_in_all_strategies(self):
        all_ids = {e["strategy_id"] for e in list_strategy_lifecycle_metadata()}
        assert _REQUIRED_ONLINE_IDS.issubset(all_ids)
        assert _REQUIRED_NON_EXEC_IDS.issubset(all_ids)

    def test_no_adapter_instances_returned(self):
        """Entries must be plain dicts, not adapter objects."""
        from lottery_api.models.replay_strategy_registry import ReplayStrategyAdapter
        for entry in list_strategy_lifecycle_metadata():
            assert isinstance(entry, dict), f"Expected dict, got {type(entry)}"
            assert not isinstance(entry, ReplayStrategyAdapter)

    def test_deterministic_ordering(self):
        """Repeated calls must return same order."""
        first = [e["strategy_id"] for e in list_strategy_lifecycle_metadata()]
        second = [e["strategy_id"] for e in list_strategy_lifecycle_metadata()]
        assert first == second


# ═══════════════════════════════════════════════════════════════════════════════
# TestGetStrategyLifecycleMetadata
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetStrategyLifecycleMetadata:
    def test_known_online_strategy(self):
        meta = get_strategy_lifecycle_metadata("power_precision_3bet")
        assert meta["strategy_id"] == "power_precision_3bet"
        assert meta["lifecycle_status"] == "ONLINE"

    def test_known_rejected_strategy(self):
        meta = get_strategy_lifecycle_metadata("p1_deviation_2bet_539")
        assert meta["lifecycle_status"] == "REJECTED"

    def test_known_observation_strategy(self):
        meta = get_strategy_lifecycle_metadata("h6_gate_mk20_ew85")
        assert meta["lifecycle_status"] == "OBSERVATION"

    def test_known_retired_strategy(self):
        meta = get_strategy_lifecycle_metadata("acb_1bet")
        assert meta["lifecycle_status"] == "RETIRED"

    def test_unknown_strategy_raises_key_error(self):
        with pytest.raises(KeyError, match="not registered"):
            get_strategy_lifecycle_metadata("__not_a_real_strategy__")

    def test_returns_plain_dict(self):
        meta = get_strategy_lifecycle_metadata("biglotto_triple_strike")
        assert isinstance(meta, dict)

    def test_has_all_required_keys(self):
        meta = get_strategy_lifecycle_metadata("daily539_f4cold")
        assert "strategy_id" in meta
        assert "lifecycle_status" in meta
        assert "supported_lottery_types" in meta
        assert "min_history" in meta


# ═══════════════════════════════════════════════════════════════════════════════
# TestSummarizeStrategyLifecycleCounts
# ═══════════════════════════════════════════════════════════════════════════════

class TestSummarizeStrategyLifecycleCounts:
    def test_counts_match_live_metadata_partitions(self):
        counts = summarize_strategy_lifecycle_counts()
        for status, count in counts.items():
            expected = sum(
                entry["lifecycle_status"] == status
                for entry in list_strategy_lifecycle_metadata()
            )
            assert count == expected

    def test_total_equals_all_adapters(self):
        counts = summarize_strategy_lifecycle_counts()
        assert sum(counts.values()) == len(_ALL_ADAPTERS)

    def test_no_unknown_statuses(self):
        counts = summarize_strategy_lifecycle_counts()
        for status in counts:
            assert status in LIFECYCLE_STATUSES, f"Unexpected status: {status!r}"

    def test_canonical_order(self):
        """Keys must appear in LIFECYCLE_STATUSES declaration order."""
        counts = summarize_strategy_lifecycle_counts()
        returned_keys = list(counts.keys())
        expected_order = [s for s in LIFECYCLE_STATUSES if s in counts]
        assert returned_keys == expected_order


# ═══════════════════════════════════════════════════════════════════════════════
# TestListExecutableNonExecutableIds
# ═══════════════════════════════════════════════════════════════════════════════

class TestListExecutableNonExecutableIds:
    def test_executable_ids_count(self):
        assert len(list_executable_strategy_ids()) == len(_REGISTRY)

    def test_executable_ids_match_registry(self):
        assert set(list_executable_strategy_ids()) == set(_REGISTRY.keys())

    def test_non_executable_ids_count(self):
        assert len(list_non_executable_strategy_ids()) == len(_ALL_ADAPTERS) - len(_REGISTRY)

    def test_non_executable_ids_correct(self):
        non_exec = set(list_non_executable_strategy_ids())
        expected = {
            adapter.meta.strategy_id
            for adapter in _ALL_ADAPTERS
            if adapter.meta.strategy_id not in _REGISTRY
        }
        assert non_exec == expected
        assert _REQUIRED_NON_EXEC_IDS.issubset(non_exec)

    def test_executable_and_non_executable_are_disjoint(self):
        exec_ids = set(list_executable_strategy_ids())
        non_exec_ids = set(list_non_executable_strategy_ids())
        assert exec_ids.isdisjoint(non_exec_ids), (
            f"Overlap: {exec_ids & non_exec_ids}"
        )

    def test_union_equals_all(self):
        exec_ids = set(list_executable_strategy_ids())
        non_exec_ids = set(list_non_executable_strategy_ids())
        all_ids = {e["strategy_id"] for e in list_strategy_lifecycle_metadata()}
        assert exec_ids | non_exec_ids == all_ids

    def test_executable_ids_are_sorted(self):
        ids = list_executable_strategy_ids()
        assert ids == sorted(ids)

    def test_non_executable_ids_are_sorted(self):
        ids = list_non_executable_strategy_ids()
        assert ids == sorted(ids)


# ═══════════════════════════════════════════════════════════════════════════════
# TestNoDbWrite
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoDbWrite:
    def test_no_db_write_on_exposure_api_calls(self, monkeypatch):
        """All exposure API calls must not touch sqlite3."""
        call_log = []

        def mock_connect(*args, **kwargs):
            call_log.append(("connect", args, kwargs))
            raise RuntimeError("sqlite3 MUST NOT be called from exposure API")

        monkeypatch.setattr(sqlite3, "connect", mock_connect)

        # Call all 5 exposure functions
        list_strategy_lifecycle_metadata()
        get_strategy_lifecycle_metadata("power_precision_3bet")
        summarize_strategy_lifecycle_counts()
        list_executable_strategy_ids()
        list_non_executable_strategy_ids()

        assert call_log == [], (
            f"sqlite3.connect was called unexpectedly: {call_log}"
        )

    def test_no_db_write_on_cli_text_mode(self, monkeypatch):
        """CLI text mode must not touch sqlite3."""
        call_log = []

        def mock_connect(*args, **kwargs):
            call_log.append(("connect", args))
            raise RuntimeError("sqlite3 must not be called from CLI")

        monkeypatch.setattr(sqlite3, "connect", mock_connect)

        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main([])
        assert rc == 0
        assert call_log == [], f"sqlite3.connect called: {call_log}"

    def test_no_db_write_on_cli_json_mode(self, monkeypatch):
        """CLI JSON mode must not touch sqlite3."""
        call_log = []

        def mock_connect(*args, **kwargs):
            call_log.append(("connect", args))
            raise RuntimeError("sqlite3 must not be called from CLI")

        monkeypatch.setattr(sqlite3, "connect", mock_connect)

        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        assert call_log == [], f"sqlite3.connect called: {call_log}"


# ═══════════════════════════════════════════════════════════════════════════════
# TestCLIReport
# ═══════════════════════════════════════════════════════════════════════════════

class TestCLIReport:
    def test_cli_text_mode_contains_marker(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "P3_LIFECYCLE_REPORT_CLI_READY" in captured.out

    def test_cli_text_mode_contains_totals(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "ONLINE" in captured.out
        assert "REJECTED" in captured.out
        assert "RETIRED" in captured.out
        assert "OBSERVATION" in captured.out

    def test_cli_json_mode_valid_json(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)

    def test_cli_json_mode_schema(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        required_keys = {
            "generated_at", "lifecycle_counts", "total",
            "executable_strategy_ids", "non_executable_strategy_ids_by_status",
            "no_db_write", "marker",
        }
        assert required_keys.issubset(data.keys())

    def test_cli_json_mode_counts(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total"] == len(_ALL_ADAPTERS)
        assert data["lifecycle_counts"] == summarize_strategy_lifecycle_counts()

    def test_cli_json_mode_no_db_write_flag(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["no_db_write"] is True

    def test_cli_json_mode_marker(self, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        rc = cli_module.main(["--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["marker"] == "P3_LIFECYCLE_REPORT_CLI_READY"

    def test_cli_output_file_writes_json(self, tmp_path, capsys):
        import scripts.report_strategy_lifecycle_registry as cli_module
        out_file = tmp_path / "output.json"
        rc = cli_module.main(["--json", "--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["total"] == len(_ALL_ADAPTERS)
