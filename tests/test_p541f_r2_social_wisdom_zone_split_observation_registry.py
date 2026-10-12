"""Focused no-DB lifecycle tests after the target-native Big Lotto migrations."""
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

from lottery_api.models import p541d_r2_biglotto_selected_adapters as donor_adapters
from lottery_api.models import replay_strategy_registry as registry


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_MODULE_NAME = "lottery_api.models.replay_strategy_registry"
DONOR_ADAPTER_MODULE_NAME = (
    "lottery_api.models.p541d_r2_biglotto_selected_adapters"
)
TARGET_SOCIAL_MODULE_NAME = "lottery_api.models.biglotto_social_wisdom_adapter"
TARGET_ZONE_MODULE_NAME = "lottery_api.models.biglotto_zone_split_adapter"
SOCIAL_PREDICTOR_MODULE_NAME = "lottery_api.models.social_wisdom_predictor"
LEGACY_ZONE_MODULE_NAME = "lottery_api.models.zone_split"

SOCIAL_ID = "biglotto_social_wisdom_anti_popularity"
ZONE_IDS = (
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet2",
    "biglotto_zone_split_3bet_bet3",
)
PROMOTED_IDS = (*ZONE_IDS, SOCIAL_ID)

SOCIAL_META = {
    "strategy_id": SOCIAL_ID,
    "strategy_name": "大樂透 Social Wisdom Anti-Popularity",
    "strategy_version": "v0.1",
    "supported_lottery_types": ["BIG_LOTTO"],
    "min_history": 1,
    "lifecycle_status": "ONLINE",
}
ZONE_META_BY_ID = {
    strategy_id: {
        "strategy_id": strategy_id,
        "strategy_name": f"大樂透 Zone Split 3注（Replay Bet {index}）",
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "ONLINE",
    }
    for index, strategy_id in enumerate(ZONE_IDS, start=1)
}
PROMOTED_META_BY_ID = {**ZONE_META_BY_ID, SOCIAL_ID: SOCIAL_META}

OBSERVATION_BASELINE_ID = "h6_gate_mk20_ew85"
OBSERVATION_BASELINE_META = {
    "strategy_id": OBSERVATION_BASELINE_ID,
    "strategy_name": "威力彩 H6 Gate mk20 ew85",
    "strategy_version": "v0.0",
    "supported_lottery_types": ["POWER_LOTTO"],
    "min_history": 0,
    "lifecycle_status": "OBSERVATION",
}

# Exact order is intentionally limited to the executable prefix that predates
# this migration.  Historical non-executable ordering remains outside this test.
UNAFFECTED_EXECUTABLE_PREFIX = (
    "power_precision_3bet",
    "power_orthogonal_5bet",
    "fourier_rhythm_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "ts3_regime_3bet",
    *ZONE_IDS,
    "daily539_f4cold",
    "daily539_markov_cold",
)

# Immutable historical donor evidence retained from the original P541F test.
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


def test_promoted_ids_have_exact_identity_membership_and_online_lifecycle():
    all_ids = [adapter.meta.strategy_id for adapter in registry._ALL_ADAPTERS]
    executable_ids = set(registry.list_executable_strategy_ids())
    non_executable_ids = set(registry.list_non_executable_strategy_ids())

    for strategy_id in PROMOTED_IDS:
        assert all_ids.count(strategy_id) == 1
        assert strategy_id in registry._REGISTRY
        assert strategy_id in executable_ids
        assert strategy_id not in non_executable_ids
        assert registry.get_strategy_lifecycle_status(strategy_id) == "ONLINE"


@pytest.mark.parametrize("strategy_id", PROMOTED_IDS)
def test_promoted_ids_publish_exact_metadata(strategy_id):
    expected = PROMOTED_META_BY_ID[strategy_id]
    adapter = registry.get_adapter(strategy_id)
    assert adapter.meta.strategy_id == expected["strategy_id"]
    assert adapter.meta.strategy_name == expected["strategy_name"]
    assert adapter.meta.strategy_version == expected["strategy_version"]
    assert adapter.meta.supported_lottery_types == expected[
        "supported_lottery_types"
    ]
    assert adapter.meta.min_history == expected["min_history"]
    assert adapter.meta.status == "ONLINE"
    assert adapter.meta.lifecycle_status == "ONLINE"
    assert registry.get_strategy_lifecycle_metadata(strategy_id) == expected


def test_promoted_ids_appear_in_online_filters_and_biglotto_generation():
    strategy_rows = {
        row["strategy_id"]: row
        for row in registry.list_strategies(lifecycle_status="ONLINE")
    }
    lifecycle_rows = {
        row["strategy_id"]: row
        for row in registry.list_strategy_lifecycle_metadata(
            lifecycle_status="ONLINE"
        )
    }
    biglotto_ids = {
        adapter.meta.strategy_id
        for adapter in registry.get_adapters_for_lottery("BIG_LOTTO")
    }
    for strategy_id in PROMOTED_IDS:
        assert strategy_rows[strategy_id]["strategy_lifecycle_status"] == "ONLINE"
        assert lifecycle_rows[strategy_id] == PROMOTED_META_BY_ID[strategy_id]
        assert strategy_id in biglotto_ids


def test_promoted_entries_are_target_native_not_lifecycle_stubs_or_donor_objects():
    social = registry.get_adapter(SOCIAL_ID)
    assert type(social) is not registry._LifecycleStub
    assert type(social).__module__ == TARGET_SOCIAL_MODULE_NAME
    assert not isinstance(
        social,
        donor_adapters.BigLottoSocialWisdomAntiPopularityAdapter,
    )

    for strategy_id in ZONE_IDS:
        zone = registry.get_adapter(strategy_id)
        assert type(zone) is not registry._LifecycleStub
        assert type(zone).__module__ == TARGET_ZONE_MODULE_NAME
        assert not isinstance(
            zone,
            donor_adapters.BigLottoZoneSplit3BetBet1Adapter,
        )


def test_h6_gate_remains_the_exact_observation_baseline():
    assert (
        registry.get_strategy_lifecycle_metadata(OBSERVATION_BASELINE_ID)
        == OBSERVATION_BASELINE_META
    )
    assert OBSERVATION_BASELINE_ID in registry.list_non_executable_strategy_ids()
    assert OBSERVATION_BASELINE_ID not in registry.list_executable_strategy_ids()
    with pytest.raises(KeyError):
        registry.get_adapter(OBSERVATION_BASELINE_ID)


def test_unaffected_executable_prefix_and_promotion_relative_order():
    ids = tuple(adapter.meta.strategy_id for adapter in registry._ALL_ADAPTERS)
    expected_prefix = UNAFFECTED_EXECUTABLE_PREFIX + (SOCIAL_ID,)
    assert ids[: len(expected_prefix)] == expected_prefix
    assert ids.index(SOCIAL_ID) < ids.index(OBSERVATION_BASELINE_ID)


def test_strategy_ids_remain_unique_and_lifecycle_values_remain_valid():
    ids = [adapter.meta.strategy_id for adapter in registry._ALL_ADAPTERS]
    assert len(ids) == len(set(ids))
    assert all(
        adapter.meta.lifecycle_status in registry.LIFECYCLE_STATUSES
        for adapter in registry._ALL_ADAPTERS
    )


def test_registry_imports_only_target_native_adapter_modules():
    tree = ast.parse(inspect.getsource(registry))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "biglotto_social_wisdom_adapter" in imported_modules
    assert "biglotto_zone_split_adapter" in imported_modules
    assert "p541d_r2_biglotto_selected_adapters" not in imported_modules
    assert "social_wisdom_predictor" not in imported_modules
    assert "zone_split" not in imported_modules


def test_registry_source_has_no_file_env_network_or_db_calls():
    tree = ast.parse(inspect.getsource(registry))
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "__import__",
        "getenv",
        "urlopen",
        "connect",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "system",
        "popen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls


def test_fresh_registry_import_loads_targets_but_not_historical_implementations():
    code = (
        "import json, sys\n"
        "import lottery_api.models.replay_strategy_registry as registry\n"
        "registry.list_strategy_lifecycle_metadata()\n"
        "registry.list_strategies()\n"
        "print(json.dumps({\n"
        f"    'donor_loaded': {DONOR_ADAPTER_MODULE_NAME!r} in sys.modules,\n"
        f"    'predictor_loaded': {SOCIAL_PREDICTOR_MODULE_NAME!r} in sys.modules,\n"
        f"    'legacy_zone_loaded': {LEGACY_ZONE_MODULE_NAME!r} in sys.modules,\n"
        f"    'target_social_loaded': {TARGET_SOCIAL_MODULE_NAME!r} in sys.modules,\n"
        f"    'target_zone_loaded': {TARGET_ZONE_MODULE_NAME!r} in sys.modules,\n"
        f"    'registry_loaded': {REGISTRY_MODULE_NAME!r} in sys.modules,\n"
        "}))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "donor_loaded": False,
        "predictor_loaded": False,
        "legacy_zone_loaded": False,
        "target_social_loaded": True,
        "target_zone_loaded": True,
        "registry_loaded": True,
    }


def test_lifecycle_apis_never_call_sqlite_connect(monkeypatch):
    def forbidden_connect(*_args, **_kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    registry.list_strategies()
    registry.list_strategies(lifecycle_status="ONLINE")
    registry.list_strategies(lifecycle_status="OBSERVATION")
    for strategy_id in (*PROMOTED_IDS, OBSERVATION_BASELINE_ID):
        registry.get_strategy_lifecycle_status(strategy_id)
        registry.get_strategy_lifecycle_metadata(strategy_id)
    registry.list_strategy_lifecycle_metadata()
    registry.list_strategy_lifecycle_metadata(lifecycle_status="ONLINE")
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


def test_donor_adapter_file_identity_matches_pin():
    path = REPO_ROOT / "lottery_api/models/p541d_r2_biglotto_selected_adapters.py"
    raw = path.read_bytes()
    expected_bytes, expected_sha256 = BASE_FILE_PINS[
        "lottery_api/models/p541d_r2_biglotto_selected_adapters.py"
    ]
    assert len(raw) == expected_bytes
    assert hashlib.sha256(raw).hexdigest() == expected_sha256


def test_donor_test_file_identity_matches_pin():
    path = REPO_ROOT / "tests/test_p541d_r2_biglotto_selected_adapters.py"
    raw = path.read_bytes()
    expected_bytes, expected_sha256 = BASE_FILE_PINS[
        "tests/test_p541d_r2_biglotto_selected_adapters.py"
    ]
    assert len(raw) == expected_bytes
    assert hashlib.sha256(raw).hexdigest() == expected_sha256


def test_historical_donor_metadata_remains_observation_only():
    donor_meta = donor_adapters.BigLottoSocialWisdomAntiPopularityAdapter.meta
    assert donor_meta.strategy_id == SOCIAL_ID
    assert donor_meta.lifecycle_status == "OBSERVATION"
    assert registry.get_strategy_lifecycle_metadata(SOCIAL_ID) == SOCIAL_META


def test_historical_donor_import_does_not_replace_runtime_authority():
    before = registry.get_adapter(SOCIAL_ID)
    module = importlib.import_module(DONOR_ADAPTER_MODULE_NAME)
    after = registry.get_adapter(SOCIAL_ID)
    assert before is after
    assert type(after).__module__ == TARGET_SOCIAL_MODULE_NAME
    assert module.BigLottoSocialWisdomAntiPopularityAdapter.meta.strategy_id == SOCIAL_ID
