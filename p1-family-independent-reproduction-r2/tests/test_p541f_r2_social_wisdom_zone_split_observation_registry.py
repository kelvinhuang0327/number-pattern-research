"""Focused no-DB tests for the P541F_R2 OBSERVATION registry metadata entries.

Scope: metadata-only lifecycle registration of two P541E-implemented strategies
as non-executable OBSERVATION stubs. Does not test adapter execution, replay
generation, or promotion — those remain out of scope for this task.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from lottery_api.models import replay_strategy_registry as registry
from lottery_api.models import p541d_r2_biglotto_selected_adapters as adapters


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_MODULE_NAME = "lottery_api.models.replay_strategy_registry"
ADAPTER_MODULE_NAME = "lottery_api.models.p541d_r2_biglotto_selected_adapters"
SOCIAL_MODULE_NAME = "lottery_api.models.social_wisdom_predictor"
ZONE_MODULE_NAME = "lottery_api.models.zone_split"

SOCIAL_ID = "biglotto_social_wisdom_anti_popularity"
ZONE_ID = "biglotto_zone_split_3bet_bet1"
NEW_IDS = (SOCIAL_ID, ZONE_ID)

SOCIAL_META = {
    "strategy_id": SOCIAL_ID,
    "strategy_name": "大樂透 Social Wisdom Anti-Popularity",
    "strategy_version": "v0.1",
    "supported_lottery_types": ["BIG_LOTTO"],
    "min_history": 1,
    "lifecycle_status": "OBSERVATION",
}
ZONE_META = {
    "strategy_id": ZONE_ID,
    "strategy_name": "大樂透 Zone Split 3注（Replay Bet 1）",
    "strategy_version": "v0.1",
    "supported_lottery_types": ["BIG_LOTTO"],
    "min_history": 1,
    "lifecycle_status": "OBSERVATION",
}
NEW_META_BY_ID = {SOCIAL_ID: SOCIAL_META, ZONE_ID: ZONE_META}

PRE_EXISTING_OBSERVATION_ID = "h6_gate_mk20_ew85"
PRE_EXISTING_OBSERVATION_META = {
    "strategy_id": PRE_EXISTING_OBSERVATION_ID,
    "strategy_name": "威力彩 H6 Gate mk20 ew85",
    "strategy_version": "v0.0",
    "supported_lottery_types": ["POWER_LOTTO"],
    "min_history": 0,
    "lifecycle_status": "OBSERVATION",
}

# Captured live from the exact base commit 08e0d6b2c6456e242c5507435a3dacc59e1eb577
# (PR #689 merge, immediately pre-P541F-edit) via direct module introspection in
# an isolated worktree. Used to prove the edit ONLY appends the two new
# OBSERVATION stubs at the tail, in the OBSERVATION section, and changes
# nothing else about ordering, executability, or existing metadata.
PRE_EDIT_ALL_ADAPTERS_SEQUENCE = (
    "power_precision_3bet",
    "power_orthogonal_5bet",
    "fourier_rhythm_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "ts3_regime_3bet",
    "daily539_f4cold",
    "daily539_markov_cold",
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq",
    "p1_deviation_2bet_539",
    "bet2_fourier_expansion_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "539_3bet_orthogonal",
    "acb_single_539",
    "markov_1bet_539",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
    "zone_gap_3bet_539",
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_ts3_markov_4bet_w30",
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "power_fourier_rhythm_2bet",
    "zonal_entropy_2bet",
    "h6_gate_mk20_ew85",
)
PRE_EDIT_REGISTRY_KEYS_SORTED = (
    "biglotto_deviation_2bet",
    "biglotto_triple_strike",
    "daily539_f4cold",
    "daily539_markov_cold",
    "fourier_rhythm_3bet",
    "power_orthogonal_5bet",
    "power_precision_3bet",
    "ts3_regime_3bet",
)
PRE_EDIT_NON_EXECUTABLE_IDS_SORTED = (
    "539_3bet_orthogonal",
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "acb_single_539",
    "bet2_fourier_expansion_biglotto",
    "biglotto_echo_aware_3bet",
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_4bet_w30",
    "biglotto_ts3_markov_freq_5bet",
    "cold_complement_2bet",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "fourier30_markov30_2bet",
    "fourier30_markov30_biglotto",
    "h6_gate_mk20_ew85",
    "markov_1bet_539",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
    "p1_deviation_2bet_539",
    "power_fourier_rhythm_2bet",
    "power_shlc_midfreq",
    "zonal_entropy_2bet",
    "zone_gap_3bet_539",
)

# Exact file identity pins (bytes, sha256) for the merged P541E implementation
# module (unmodified by this task) and its test file. The test file pin is the
# POST-amendment identity: owner-authorized scope expansion narrowed exactly
# two assertions that were mutually exclusive with this task's Phase 3/4
# requirements (see test_p541e_test_file_amendment_is_scoped_to_the_two_known_narrowings
# below for an explicit diff-shaped proof of what changed).
BASE_FILE_PINS = {
    "lottery_api/models/p541d_r2_biglotto_selected_adapters.py": (
        7673,
        "22e3a5bfc27272d2126e7daa256d2f1840d3b7fd760bce700c39e3f1f236c82a",
    ),
    "tests/test_p541d_r2_biglotto_selected_adapters.py": (
        32031,
        "f2bfff8ad90b6f644ed3a52e03a6f623fa80c094d8d895d237cdb5ddb7881324",
    ),
}


# ─── 1. Exact two new IDs occur exactly once in _ALL_ADAPTERS ────────────────

def test_new_ids_occur_exactly_once_in_all_adapters():
    ids = [a.meta.strategy_id for a in registry._ALL_ADAPTERS]
    for new_id in NEW_IDS:
        assert ids.count(new_id) == 1


# ─── 2. Both new entries are _LifecycleStub instances, not adapter classes ──

def test_new_entries_are_lifecycle_stubs_not_adapter_classes():
    by_id = {
        a.meta.strategy_id: a
        for a in registry._ALL_ADAPTERS
        if a.meta.strategy_id in NEW_IDS
    }
    assert set(by_id) == set(NEW_IDS)
    for strategy_id, instance in by_id.items():
        assert type(instance) is registry._LifecycleStub, strategy_id
        assert not isinstance(instance, adapters.BigLottoSocialWisdomAntiPopularityAdapter)
        assert not isinstance(instance, adapters.BigLottoZoneSplit3BetBet1Adapter)


# ─── 3. Exact metadata ───────────────────────────────────────────────────────

@pytest.mark.parametrize("strategy_id", NEW_IDS)
def test_new_stub_instance_meta_matches_expected(strategy_id):
    stub = next(a for a in registry._ALL_ADAPTERS if a.meta.strategy_id == strategy_id)
    expected = NEW_META_BY_ID[strategy_id]
    assert stub.meta.strategy_id == expected["strategy_id"]
    assert stub.meta.strategy_name == expected["strategy_name"]
    assert stub.meta.strategy_version == expected["strategy_version"]
    assert stub.meta.supported_lottery_types == expected["supported_lottery_types"]
    assert stub.meta.min_history == expected["min_history"]
    assert stub.meta.status == "OBSERVATION"
    assert stub.meta.lifecycle_status == "OBSERVATION"


@pytest.mark.parametrize("strategy_id", NEW_IDS)
def test_new_entry_exact_metadata_via_accessor(strategy_id):
    assert registry.get_strategy_lifecycle_metadata(strategy_id) == NEW_META_BY_ID[strategy_id]


# ─── 4. Lifecycle visibility across all exposure APIs ───────────────────────

@pytest.mark.parametrize("strategy_id", NEW_IDS)
def test_new_entry_lifecycle_status_and_membership(strategy_id):
    assert registry.get_strategy_lifecycle_status(strategy_id) == "OBSERVATION"
    assert strategy_id in registry.list_non_executable_strategy_ids()


def test_new_entries_appear_in_list_strategies_observation_filter():
    observation = {
        entry["strategy_id"]: entry
        for entry in registry.list_strategies(lifecycle_status="OBSERVATION")
    }
    assert set(NEW_IDS) <= set(observation)
    for strategy_id in NEW_IDS:
        entry = observation[strategy_id]
        expected = NEW_META_BY_ID[strategy_id]
        assert entry["strategy_id"] == expected["strategy_id"]
        assert entry["strategy_name"] == expected["strategy_name"]
        assert entry["strategy_version"] == expected["strategy_version"]
        assert entry["supported_lottery_types"] == expected["supported_lottery_types"]
        assert entry["min_history"] == expected["min_history"]
        assert entry["status"] == "OBSERVATION"
        assert entry["strategy_lifecycle_status"] == "OBSERVATION"


def test_new_entries_appear_in_list_strategy_lifecycle_metadata_observation_filter():
    observation = {
        entry["strategy_id"]: entry
        for entry in registry.list_strategy_lifecycle_metadata(lifecycle_status="OBSERVATION")
    }
    assert set(NEW_IDS) <= set(observation)
    for strategy_id in NEW_IDS:
        assert observation[strategy_id] == NEW_META_BY_ID[strategy_id]


# ─── 5. Non-executability ────────────────────────────────────────────────────

@pytest.mark.parametrize("strategy_id", NEW_IDS)
def test_new_entries_absent_from_registry_and_executable_ids(strategy_id):
    assert strategy_id not in registry._REGISTRY
    assert strategy_id not in registry.list_executable_strategy_ids()


def test_new_entries_absent_from_biglotto_generation_eligible_adapters():
    ids = {a.meta.strategy_id for a in registry.get_adapters_for_lottery("BIG_LOTTO")}
    assert ids.isdisjoint(NEW_IDS)


@pytest.mark.parametrize("strategy_id", NEW_IDS)
def test_get_adapter_raises_keyerror(strategy_id):
    with pytest.raises(KeyError):
        registry.get_adapter(strategy_id)


@pytest.mark.parametrize("strategy_id", NEW_IDS)
@pytest.mark.parametrize(
    "lottery_type", ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539", "NOT_A_LOTTERY_TYPE"]
)
def test_direct_stub_get_one_bet_always_raises_lifecycle_not_executable(
    strategy_id, lottery_type
):
    stub = next(a for a in registry._ALL_ADAPTERS if a.meta.strategy_id == strategy_id)
    assert type(stub) is registry._LifecycleStub
    with pytest.raises(registry.LifecycleNotExecutable):
        stub.get_one_bet([], lottery_type)


class _ExplodingHistory(list):
    """A history object that fails loudly if its contents are ever touched."""

    def __iter__(self):
        raise AssertionError("history contents must not be inspected")

    def __len__(self):
        raise AssertionError("history contents must not be inspected")

    def __getitem__(self, item):
        raise AssertionError("history contents must not be inspected")

    def __bool__(self):
        raise AssertionError("history contents must not be inspected")


@pytest.mark.parametrize("strategy_id", NEW_IDS)
@pytest.mark.parametrize("lottery_type", ["BIG_LOTTO", "POWER_LOTTO"])
def test_history_contents_never_inspected_before_lifecycle_rejection(
    strategy_id, lottery_type
):
    stub = next(a for a in registry._ALL_ADAPTERS if a.meta.strategy_id == strategy_id)
    with pytest.raises(registry.LifecycleNotExecutable):
        stub.get_one_bet(_ExplodingHistory(), lottery_type)


# ─── 6. Registry isolation from implementation modules ──────────────────────

def test_registry_source_has_no_import_of_implementation_modules():
    tree = ast.parse(inspect.getsource(registry))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
    forbidden_modules = {ADAPTER_MODULE_NAME, SOCIAL_MODULE_NAME, ZONE_MODULE_NAME}
    assert imported_modules.isdisjoint(forbidden_modules)


def test_registry_module_level_imports_unchanged_no_new_external_access_surface():
    """Only module-level (top-of-file) imports are checked — pre-existing
    per-strategy adapters intentionally use lazy imports scoped inside their
    own _call_strategy methods (see HARD RULES in the module docstring); this
    test must not walk into those nested scopes."""
    tree = ast.parse(inspect.getsource(registry))
    imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports == {"__future__", "sys", "json", "logging", "pathlib", "typing"}


def test_registry_source_has_no_file_env_network_or_db_calls():
    tree = ast.parse(inspect.getsource(registry))
    forbidden_calls = {
        "open", "exec", "eval", "__import__", "getenv", "urlopen", "connect",
        "read_text", "read_bytes", "write_text", "write_bytes", "system", "popen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls


def test_no_executable_implementation_object_in_registry_globals():
    forbidden_types = (
        adapters.BigLottoSocialWisdomAntiPopularityAdapter,
        adapters.BigLottoZoneSplit3BetBet1Adapter,
    )
    for name, value in vars(registry).items():
        assert not isinstance(value, forbidden_types), name
    for adapter in registry._ALL_ADAPTERS:
        assert not isinstance(adapter, forbidden_types)


def test_fresh_process_registry_import_never_loads_implementation_modules():
    code = (
        "import json, sys\n"
        "import lottery_api.models.replay_strategy_registry as registry\n"
        "registry.list_strategy_lifecycle_metadata()\n"
        "registry.list_strategies()\n"
        "print(json.dumps({\n"
        "    'adapter_loaded': 'lottery_api.models.p541d_r2_biglotto_selected_adapters' in sys.modules,\n"
        "    'social_loaded': 'lottery_api.models.social_wisdom_predictor' in sys.modules,\n"
        "    'zone_loaded': 'lottery_api.models.zone_split' in sys.modules,\n"
        "    'registry_loaded': 'lottery_api.models.replay_strategy_registry' in sys.modules,\n"
        "}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result == {
        "adapter_loaded": False,
        "social_loaded": False,
        "zone_loaded": False,
        "registry_loaded": True,
    }


# ─── 7. Existing behavior preserved ──────────────────────────────────────────

def test_preexisting_registry_keys_unchanged():
    assert sorted(registry._REGISTRY.keys()) == list(PRE_EDIT_REGISTRY_KEYS_SORTED)


def test_non_executable_ids_equal_preexisting_plus_two_new():
    expected = sorted(set(PRE_EDIT_NON_EXECUTABLE_IDS_SORTED) | set(NEW_IDS))
    assert registry.list_non_executable_strategy_ids() == expected


def test_preexisting_observation_entry_unchanged():
    assert (
        registry.get_strategy_lifecycle_metadata(PRE_EXISTING_OBSERVATION_ID)
        == PRE_EXISTING_OBSERVATION_META
    )


def test_all_adapters_sequence_is_preedit_sequence_plus_two_appended_at_tail():
    ids = tuple(a.meta.strategy_id for a in registry._ALL_ADAPTERS)
    assert ids == PRE_EDIT_ALL_ADAPTERS_SEQUENCE + NEW_IDS


def test_strategy_ids_remain_unique():
    ids = [a.meta.strategy_id for a in registry._ALL_ADAPTERS]
    assert len(ids) == len(set(ids))


def test_all_lifecycle_statuses_remain_valid():
    for a in registry._ALL_ADAPTERS:
        assert a.meta.lifecycle_status in registry.LIFECYCLE_STATUSES


def test_exactly_two_lifecycle_stub_calls_added_relative_to_preedit_snapshot():
    tree = ast.parse(inspect.getsource(registry))
    stub_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_LifecycleStub"
    ]
    assert len(stub_calls) == len(PRE_EDIT_NON_EXECUTABLE_IDS_SORTED) + len(NEW_IDS)


# ─── 8. No DB / external state ───────────────────────────────────────────────

def test_lifecycle_apis_never_call_sqlite_connect(monkeypatch):
    def _forbidden_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)

    registry.list_strategies()
    registry.list_strategies(lifecycle_status="OBSERVATION")
    for strategy_id in NEW_IDS:
        registry.get_strategy_lifecycle_status(strategy_id)
        registry.get_strategy_lifecycle_metadata(strategy_id)
    registry.list_strategy_lifecycle_metadata()
    registry.list_strategy_lifecycle_metadata(lifecycle_status="OBSERVATION")
    registry.list_executable_strategy_ids()
    registry.list_non_executable_strategy_ids()
    registry.summarize_strategy_lifecycle_counts()
    registry.get_adapters_for_lottery("BIG_LOTTO")


def test_registry_reload_in_fresh_process_makes_no_sqlite_connect_call():
    code = (
        "import sqlite3\n"
        "def _boom(*a, **k):\n"
        "    raise AssertionError('sqlite3.connect must not be called')\n"
        "sqlite3.connect = _boom\n"
        "import lottery_api.models.replay_strategy_registry as registry\n"
        "registry.list_strategy_lifecycle_metadata()\n"
        "registry.summarize_strategy_lifecycle_counts()\n"
        "print('OK')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "OK"


# ─── 9. P541E binding ─────────────────────────────────────────────────────────

def test_p541e_adapter_file_identity_matches_pin():
    path = REPO_ROOT / "lottery_api/models/p541d_r2_biglotto_selected_adapters.py"
    raw = path.read_bytes()
    expected_bytes, expected_sha256 = BASE_FILE_PINS[
        "lottery_api/models/p541d_r2_biglotto_selected_adapters.py"
    ]
    assert len(raw) == expected_bytes
    assert hashlib.sha256(raw).hexdigest() == expected_sha256


def test_p541e_test_file_identity_matches_amended_pin():
    path = REPO_ROOT / "tests/test_p541d_r2_biglotto_selected_adapters.py"
    raw = path.read_bytes()
    expected_bytes, expected_sha256 = BASE_FILE_PINS[
        "tests/test_p541d_r2_biglotto_selected_adapters.py"
    ]
    assert len(raw) == expected_bytes
    assert hashlib.sha256(raw).hexdigest() == expected_sha256


def test_p541e_test_file_amendment_is_scoped_to_the_two_known_narrowings():
    """Owner-authorized scope expansion beyond the original two-file plan:
    narrows exactly the two P541E-test assertions that were mutually
    exclusive with this task's own Phase 3/4 requirements (registering
    SOCIAL_ID/ZONE_ID as visible OBSERVATION stubs necessarily makes them
    appear in _ALL_ADAPTERS, and necessarily changes registry.py's hash).
    Everything else in that file is untouched (see the byte/hash pin above,
    which pins the file as a whole)."""
    source = (
        REPO_ROOT / "tests/test_p541d_r2_biglotto_selected_adapters.py"
    ).read_text(encoding="utf-8")
    # The registry.py pin was advanced to this task's post-edit identity.
    assert "380ac2942a7374bd7ccad940ec50b273757ae100" in source
    assert "c6c0352868f93c27e68c230e14b1b1c8f8c6a4f2feb021574d2f7cc49170976e" in source
    assert "45770dabaa46c80e6f564b61e5dae96b03bd856e" not in source
    # The over-broad "never appears in _ALL_ADAPTERS at all" clause was removed.
    assert "item.meta.strategy_id not in {SOCIAL_ID, ZONE_ID}" not in source
    # The narrower, still-true "non-executable" invariant is preserved.
    assert "assert SOCIAL_ID not in registry._REGISTRY" in source
    assert "assert ZONE_ID not in registry._REGISTRY" in source


def test_p541e_adapter_metadata_matches_registry_stubs():
    pairs = [
        (adapters.BigLottoSocialWisdomAntiPopularityAdapter, SOCIAL_META),
        (adapters.BigLottoZoneSplit3BetBet1Adapter, ZONE_META),
    ]
    for adapter_class, expected in pairs:
        meta = adapter_class.meta
        assert meta.strategy_id == expected["strategy_id"]
        assert meta.strategy_name == expected["strategy_name"]
        assert meta.strategy_version == expected["strategy_version"]
        assert meta.supported_lottery_types == expected["supported_lottery_types"]
        assert meta.min_history == expected["min_history"]
        assert meta.lifecycle_status == expected["lifecycle_status"]
        assert registry.get_strategy_lifecycle_metadata(meta.strategy_id) == expected


def test_implementation_module_is_independently_importable():
    module = importlib.import_module(ADAPTER_MODULE_NAME)
    assert hasattr(module, "BigLottoSocialWisdomAntiPopularityAdapter")
    assert hasattr(module, "BigLottoZoneSplit3BetBet1Adapter")
    assert module.BigLottoSocialWisdomAntiPopularityAdapter.meta.strategy_id == SOCIAL_ID
    assert module.BigLottoZoneSplit3BetBet1Adapter.meta.strategy_id == ZONE_ID
