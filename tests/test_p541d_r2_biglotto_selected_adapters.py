"""Focused no-DB tests for the P541D_R2-selected BIG_LOTTO adapters."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import inspect
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from lottery_api.models import replay_strategy_registry as registry
from lottery_api.models import p541d_r2_biglotto_selected_adapters as adapters


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "lottery_api.models.p541d_r2_biglotto_selected_adapters"
SOCIAL_MODULE_NAME = "lottery_api.models.social_wisdom_predictor"
ZONE_MODULE_NAME = "lottery_api.models.zone_split"
DESIGN_PATH = (
    REPO_ROOT
    / "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.json"
)
SOCIAL_ID = "biglotto_social_wisdom_anti_popularity"
ZONE_ID = "biglotto_zone_split_3bet_bet1"
ADAPTER_CLASSES = (
    adapters.BigLottoSocialWisdomAntiPopularityAdapter,
    adapters.BigLottoZoneSplit3BetBet1Adapter,
)
ZONE_HISTORY = [
    {
        "draw": "1",
        "date": "2026-01-01",
        "numbers": [1, 2, 3, 4, 5, 6],
    }
]
ZONE_PREIMAGE = (
    b'{"causal_history":[{"date":"2026-01-01","draw":"1",'
    b'"numbers":[1,2,3,4,5,6]}],"lottery_type":"BIG_LOTTO",'
    b'"strategy_id":"biglotto_zone_split_3bet_bet1"}'
)
ZONE_DIGEST = "8d1984bfcf997abb35fd4eaf53115c0afcbcfd7bb763dc9a1fd66dbe869872f3"
ZONE_BETS = [
    [4, 6, 11, 14, 15, 18],
    [15, 16, 17, 21, 26, 31],
    [38, 41, 42, 44, 48, 49],
]


def _source_tree() -> ast.Module:
    return ast.parse(inspect.getsource(adapters))


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _valid_ticket(numbers: list[int]) -> None:
    assert numbers == sorted(numbers)
    assert len(numbers) == 6
    assert len(set(numbers)) == 6
    assert all(type(number) is int and 1 <= number <= 49 for number in numbers)


def test_exact_two_adapter_classes_strategy_ids_and_exports():
    defined_adapters = {
        name: cls
        for name, cls in inspect.getmembers(adapters, inspect.isclass)
        if cls.__module__ == MODULE_NAME
        and issubclass(cls, registry.ReplayStrategyAdapter)
    }
    assert defined_adapters == {
        "BigLottoSocialWisdomAntiPopularityAdapter": ADAPTER_CLASSES[0],
        "BigLottoZoneSplit3BetBet1Adapter": ADAPTER_CLASSES[1],
    }
    assert [cls.meta.strategy_id for cls in ADAPTER_CLASSES] == [SOCIAL_ID, ZONE_ID]
    assert adapters.__all__ == list(defined_adapters)


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_shared_metadata_is_biglotto_observation_only(adapter_class):
    meta = adapter_class.meta
    assert meta.supported_lottery_types == ["BIG_LOTTO"]
    assert meta.min_history == 1
    assert meta.status == "OBSERVATION"
    assert meta.lifecycle_status == "OBSERVATION"
    assert meta.strategy_version == "v0.1"


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_unsupported_lottery_fails_closed(adapter_class):
    with pytest.raises(registry.UnsupportedLotteryType):
        adapter_class().get_one_bet(ZONE_HISTORY, "POWER_LOTTO")


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_empty_history_fails_closed(adapter_class):
    with pytest.raises(registry.InsufficientHistory):
        adapter_class().get_one_bet([], "BIG_LOTTO")


def test_both_final_outputs_are_valid_and_special_is_none():
    social_history = [
        {"draw": str(index), "date": f"2026-01-{index + 1:02d}",
         "numbers": [32, 33, 34, 35, 41, 49]}
        for index in range(20)
    ]
    outputs = [
        adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
            social_history, "BIG_LOTTO"
        ),
        adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
            ZONE_HISTORY, "BIG_LOTTO"
        ),
    ]
    for numbers, special in outputs:
        _valid_ticket(numbers)
        assert special is None


def test_module_import_does_not_mutate_canonical_registry():
    before_registry = dict(registry._REGISTRY)
    before_all = tuple(registry._ALL_ADAPTERS)
    sys.modules.pop(MODULE_NAME, None)
    imported = importlib.import_module(MODULE_NAME)
    assert imported is not None
    assert registry._REGISTRY == before_registry
    assert tuple(registry._ALL_ADAPTERS) == before_all
    assert SOCIAL_ID not in registry._REGISTRY
    assert ZONE_ID not in registry._REGISTRY
    assert all(
        item.meta.strategy_id not in {SOCIAL_ID, ZONE_ID}
        for item in registry._ALL_ADAPTERS
    )


def test_adapter_ast_has_no_external_state_or_registry_mutation_api():
    tree = _source_tree()
    forbidden_import_roots = {
        "os", "pathlib", "sqlite3", "requests", "urllib", "socket",
        "subprocess", "pandas", "numpy",
    }
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint(forbidden_import_roots)

    forbidden_calls = {
        "open", "exec", "eval", "__import__", "getenv", "urlopen", "connect",
        "read_text", "read_bytes", "write_text", "write_bytes",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
    source = inspect.getsource(adapters)
    assert "sys.path" not in source
    assert "_REGISTRY" not in source
    assert "_ALL_ADAPTERS" not in source


def test_social_import_is_lazy_and_scoped_to_call_strategy():
    tree = _source_tree()
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == SOCIAL_MODULE_NAME
    ]
    assert len(imports) == 1
    social_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "BigLottoSocialWisdomAntiPopularityAdapter"
    )
    call_strategy = next(
        node
        for node in social_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_call_strategy"
    )
    assert imports[0] in list(ast.walk(call_strategy))

    sys.modules.pop(SOCIAL_MODULE_NAME, None)
    adapter = adapters.BigLottoSocialWisdomAntiPopularityAdapter()
    assert SOCIAL_MODULE_NAME not in sys.modules
    adapter._call_strategy(
        [{"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]}],
        "BIG_LOTTO",
    )
    assert SOCIAL_MODULE_NAME in sys.modules


def test_social_direct_call_parity_and_input_equivalence():
    from lottery_api.models.social_wisdom_predictor import SocialWisdomPredictor

    history = [
        {
            "draw": str(index),
            "date": f"2025-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
            "numbers": sorted({
                index % 49 + 1,
                (index + 7) % 49 + 1,
                (index + 14) % 49 + 1,
                (index + 21) % 49 + 1,
                (index + 28) % 49 + 1,
                (index + 35) % 49 + 1,
            }),
        }
        for index in range(60)
    ]
    before = copy.deepcopy(history)
    before_bytes = _json_bytes(history)
    direct_history = copy.deepcopy(history[-50:])
    direct_history.reverse()
    expected = SocialWisdomPredictor(max_num=49).predict(direct_history, pick_count=6)
    actual, special = adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        history, "BIG_LOTTO"
    )
    assert actual == expected
    assert special is None
    assert history == before
    assert _json_bytes(history) == before_bytes


def test_social_last_50_newest_first_copy_and_excluded_methods(monkeypatch):
    social_module = importlib.import_module(SOCIAL_MODULE_NAME)
    received = []

    class SpyPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            assert pick_count == 6
            received.extend(copy.deepcopy(history))
            history[0]["numbers"][0] = 49
            return [1, 2, 3, 4, 5, 6]

        def predict_with_balance(self, *_args, **_kwargs):
            raise AssertionError("predict_with_balance must not be called")

        def generate_8_bets(self, *_args, **_kwargs):
            raise AssertionError("generate_8_bets must not be called")

    monkeypatch.setattr(social_module, "SocialWisdomPredictor", SpyPredictor)
    history = [
        {"draw": f"d{index}", "date": f"date-{index}",
         "numbers": [1, 2, 3, 4, 5, 6], "extra": index}
        for index in range(55)
    ]
    before = copy.deepcopy(history)
    numbers, special = adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        history, "BIG_LOTTO"
    )
    assert [row["draw"] for row in received] == [f"d{index}" for index in range(54, 4, -1)]
    assert numbers == [1, 2, 3, 4, 5, 6]
    assert special is None
    assert history == before


def test_social_repeated_high_synthetic_vector():
    newest_first = [
        {"draw": str(index), "date": str(index),
         "numbers": [32, 33, 34, 35, 41, 49]}
        for index in range(50)
    ]
    numbers, special = adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
        list(reversed(newest_first)), "BIG_LOTTO"
    )
    assert numbers == [32, 33, 34, 35, 41, 49]
    assert special is None


@pytest.mark.parametrize("malformed", [None, [], [1, 2, 3, 4, 5], [1, 1, 2, 3, 4, 5]])
def test_social_malformed_legacy_output_fails_closed(monkeypatch, malformed):
    social_module = importlib.import_module(SOCIAL_MODULE_NAME)

    class MalformedPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            return malformed

    monkeypatch.setattr(social_module, "SocialWisdomPredictor", MalformedPredictor)
    with pytest.raises(registry.InvalidOutput):
        adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
            ZONE_HISTORY, "BIG_LOTTO"
        )


def test_social_unexpected_runtime_failure_propagates(monkeypatch):
    social_module = importlib.import_module(SOCIAL_MODULE_NAME)

    class BrokenPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            raise RuntimeError("pinned callable failure")

    monkeypatch.setattr(social_module, "SocialWisdomPredictor", BrokenPredictor)
    with pytest.raises(RuntimeError, match="pinned callable failure"):
        adapters.BigLottoSocialWisdomAntiPopularityAdapter().get_one_bet(
            ZONE_HISTORY, "BIG_LOTTO"
        )


def test_social_call_strategy_has_no_random_api_use():
    source = inspect.getsource(adapters.BigLottoSocialWisdomAntiPopularityAdapter)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id in {"np", "numpy", "random"}
            )


def test_zone_source_is_never_imported_or_executed():
    tree = _source_tree()
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert ZONE_MODULE_NAME not in imported_modules

    code = """
import json
import sys
from lottery_api.models.p541d_r2_biglotto_selected_adapters import BigLottoZoneSplit3BetBet1Adapter
history = [{"draw":"1","date":"2026-01-01","numbers":[1,2,3,4,5,6]}]
result = BigLottoZoneSplit3BetBet1Adapter().get_one_bet(history, "BIG_LOTTO")
print(json.dumps({"loaded": "lottery_api.models.zone_split" in sys.modules, "result": result}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result == {"loaded": False, "result": [ZONE_BETS[0], None]}


def test_zone_exact_pools():
    assert adapters._zone_split_pools() == [
        list(range(1, 19)),
        list(range(15, 35)),
        list(range(31, 50)),
    ]


def test_zone_canonical_preimage_digest_and_sequential_bets():
    assert adapters._zone_seed_preimage(ZONE_HISTORY) == ZONE_PREIMAGE
    assert adapters._zone_seed_digest(ZONE_HISTORY) == ZONE_DIGEST
    assert adapters._zone_split_bets(ZONE_HISTORY) == ZONE_BETS


def test_zone_adapter_returns_first_bet_only_without_input_mutation():
    history = copy.deepcopy(ZONE_HISTORY)
    before = copy.deepcopy(history)
    before_bytes = _json_bytes(history)
    numbers, special = adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        history, "BIG_LOTTO"
    )
    assert numbers == ZONE_BETS[0]
    assert special is None
    assert history == before
    assert _json_bytes(history) == before_bytes


def test_zone_same_history_is_stable_across_instances_and_processes():
    first = adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        ZONE_HISTORY, "BIG_LOTTO"
    )
    second = adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        copy.deepcopy(ZONE_HISTORY), "BIG_LOTTO"
    )
    assert first == second

    code = """
import json
from lottery_api.models.p541d_r2_biglotto_selected_adapters import BigLottoZoneSplit3BetBet1Adapter
history = [{"draw":"1","date":"2026-01-01","numbers":[1,2,3,4,5,6]}]
print(json.dumps(BigLottoZoneSplit3BetBet1Adapter().get_one_bet(history, "BIG_LOTTO")))
"""
    outputs = [
        subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for _ in range(2)
    ]
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0]) == [ZONE_BETS[0], None]


def test_zone_causal_row_order_changes_seed_and_output():
    history = [
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "2", "date": "2026-01-02", "numbers": [7, 8, 9, 10, 11, 12]},
        {"draw": "3", "date": "2026-01-03", "numbers": [13, 14, 15, 16, 17, 18]},
    ]
    reversed_history = list(reversed(copy.deepcopy(history)))
    assert adapters._zone_seed_digest(history) != adapters._zone_seed_digest(reversed_history)
    assert adapters._zone_split_bets(history) != adapters._zone_split_bets(reversed_history)


def test_zone_number_order_and_extra_fields_do_not_change_seed_or_output():
    reordered = copy.deepcopy(ZONE_HISTORY)
    reordered[0]["numbers"] = [6, 4, 2, 5, 3, 1]
    with_extra = copy.deepcopy(ZONE_HISTORY)
    with_extra[0].update({"special": 49, "runtime_note": {"ignored": True}})
    baseline = (
        adapters._zone_seed_digest(ZONE_HISTORY),
        adapters._zone_split_bets(ZONE_HISTORY),
    )
    assert (
        adapters._zone_seed_digest(reordered),
        adapters._zone_split_bets(reordered),
    ) == baseline
    assert (
        adapters._zone_seed_digest(with_extra),
        adapters._zone_split_bets(with_extra),
    ) == baseline


def test_zone_leaves_global_random_state_unchanged():
    before = random.getstate()
    adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
        ZONE_HISTORY, "BIG_LOTTO"
    )
    assert random.getstate() == before


def test_zone_never_calls_module_level_seed_or_sample(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("global random API must not be called")

    monkeypatch.setattr(adapters.random, "seed", forbidden)
    monkeypatch.setattr(adapters.random, "sample", forbidden)
    assert adapters._zone_split_bets(ZONE_HISTORY) == ZONE_BETS


@pytest.mark.parametrize(
    "history",
    [
        [None],
        [{}],
        [{"draw": "1", "date": "2026-01-01"}],
        [{"draw": "1", "numbers": [1, 2, 3, 4, 5, 6]}],
        [{"date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]}],
        [{"draw": "1", "date": "2026-01-01", "numbers": None}],
        [{"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3]}],
        [{"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 50]}],
        [{"draw": "1", "date": "2026-01-01", "numbers": [1, 1, 2, 3, 4, 5]}],
    ],
)
def test_zone_malformed_or_missing_history_fields_fail_closed(history):
    with pytest.raises(registry.InvalidOutput):
        adapters.BigLottoZoneSplit3BetBet1Adapter().get_one_bet(
            history, "BIG_LOTTO"
        )


def test_design_artifact_identity_and_exact_two_approved_records():
    raw = DESIGN_PATH.read_bytes()
    assert len(raw) == 47683
    assert hashlib.sha256(raw).hexdigest() == (
        "32dddcca4e70ab2e27aeb2aa082f38d365dad3a1523207d48c4d2c0758db8ce7"
    )
    design = json.loads(raw)
    assert design["schema_version"] == "p541d-r2-adapter-design-v1"
    assert design["designer_version"] == "p541d-r2-designer-v2"
    approved = [item for item in design["method_designs"] if item["ready_for_implementation"]]
    assert [item["source_path"] for item in approved] == [
        "lottery_api/models/social_wisdom_predictor.py",
        "lottery_api/models/zone_split.py",
    ]
    assert [item["proposed_strategy"]["strategy_id"] for item in approved] == [
        SOCIAL_ID,
        ZONE_ID,
    ]
    assert [item["design_status"] for item in approved] == [
        "LAZY_DIRECT_WRAPPER_READY",
        "DETERMINISTIC_REIMPLEMENTATION_READY",
    ]


def test_source_and_canonical_reference_identities_match_pins():
    expected = {
        "lottery_api/models/social_wisdom_predictor.py": (
            "1a1f4119f4ade1b5605a988f595c7ed8300e6a40",
            "a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b",
        ),
        "lottery_api/models/zone_split.py": (
            "5ce1ce023cab846791550bd7240106600ee9b95e",
            "b6144f9d479feded3746d81e0d5682e7cfb28ba8d8aa03ff65f3706649996211",
        ),
        "lottery_api/models/replay_strategy_registry.py": (
            "45770dabaa46c80e6f564b61e5dae96b03bd856e",
            "bdc035b2f49a0368001ffd1af07d90f4d382cba79671abdea904e8b91de9a54f",
        ),
        "lottery_api/models/p42_wave3_biglotto_adapters.py": (
            "213193465f205faac47a23b4e6b07d6701626571",
            "d07b1c90f6971c01729d94919d7070ee23d45bf5357d3faf1f2f5b047dd2bb79",
        ),
        "lottery_api/models/p93_tierb_replay_adapters.py": (
            "297681147267d937383d7f898e59b26f811c6722",
            "569f85988cec49e55c0b429f093fabaad93ff9036506cac29ebf052bb1d10995",
        ),
    }
    for path, (blob_sha, sha256) in expected.items():
        raw = (REPO_ROOT / path).read_bytes()
        assert _git_blob_sha(raw) == blob_sha
        assert hashlib.sha256(raw).hexdigest() == sha256


def test_quickml_advanced_and_third_strategy_are_not_implemented():
    source = inspect.getsource(adapters)
    for forbidden in (
        "QuickMLPredictor",
        "quick_ml_predict",
        "AdvancedLotteryPredictor",
        "advanced_prediction_engine",
    ):
        assert forbidden not in source
    meta_calls = [
        node
        for node in ast.walk(_source_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_StrategyMeta"
    ]
    assert len(meta_calls) == 2
