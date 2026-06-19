"""Fail-closed no-DB adapter for the frozen BIG 6/49 strategy family.

The adapter invokes only the exact source identities frozen by P280D and the
P280AJ-authorized deterministic candidate callables added to those same frozen
source files. Callers must provide historical draws, a cutoff, and target
metadata. This module does not read a database, use the network, select a
target, look up a deadline, write publication artifacts, or invent replacement
tickets.

P280AJ remediation: the frozen ``bet_index=1`` outputs structurally duplicate
sibling strategies, so a single primary ticket per strategy cannot yield eleven
unique complete tickets. Each strategy now exposes an ordered list of
deterministic source candidates derived only from its own scoring/ranking
family. The adapter selects, in canonical frozen order, the first candidate whose
complete ticket is not already claimed by an earlier strategy, records full
provenance, and fails closed if any strategy has no non-duplicate candidate. No
fabricated fallback, outcome-aware selection, or historical-best selection is
performed.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.big649_real_publication_runner import (
    BET_INDEX,
    BIG649_FROZEN_STRATEGY_IDS,
    ENDPOINT,
    N,
    PublicationGuardError,
    SAFE_VALIDATE_ONLY,
    SYNTHETIC_TARGET,
    build_publication_manifest_candidate,
)

__all__ = [
    "AdapterContractError",
    "DETERMINISTIC_MISMATCH_STOP",
    "DUPLICATE_COMPLETE_TICKET_STOP",
    "MISSING_OR_EXTRA_STRATEGY_STOP",
    "STOCHASTIC_POLICY_MISSING_STOP",
    "UNRESOLVED_DUPLICATE_STOP",
    "SELECTION_RULE",
    "build_adapter_report",
    "classify_strategy_randomness",
    "compute_strategy_output_digest",
    "discover_strategy_adapters",
    "enumerate_strategy_candidates",
    "frozen_primary_outputs",
    "frozen_primary_duplicate_groups",
    "generate_strategy_outputs_no_db",
    "list_frozen_big649_strategy_ids",
    "resolve_unique_strategy_outputs",
    "validate_strategy_adapter_contract",
    "validate_strategy_outputs",
]


class AdapterContractError(ValueError):
    """Raised when a no-DB strategy-output contract fails closed."""


REPO_ROOT = Path(__file__).resolve().parent.parent
TICKET_SIZE = 6
NUMBER_MIN = 1
NUMBER_MAX = 49
MIN_HISTORY = 500

MISSING_OR_EXTRA_STRATEGY_STOP = "MISSING_OR_EXTRA_STRATEGY_STOP"
DUPLICATE_COMPLETE_TICKET_STOP = "DUPLICATE_COMPLETE_TICKET_STOP"
UNRESOLVED_DUPLICATE_STOP = "UNRESOLVED_DUPLICATE_STOP"
DETERMINISTIC_MISMATCH_STOP = "DETERMINISTIC_MISMATCH_STOP"
STOCHASTIC_POLICY_MISSING_STOP = "STOCHASTIC_POLICY_MISSING_STOP"
DETERMINISTIC_NO_RANDOMNESS = "DETERMINISTIC_NO_RANDOMNESS"
STOCHASTIC_READY_WITH_SEED_AND_POLICY = "STOCHASTIC_READY_WITH_SEED_AND_POLICY"
TARGET_METADATA_MIXING_STOP = "TARGET_METADATA_MIXING_STOP"
SOURCE_IDENTITY_MISMATCH_STOP = "SOURCE_IDENTITY_MISMATCH_STOP"

SELECTION_RULE = (
    "first deterministic source candidate whose complete ticket is not already "
    "claimed by an earlier frozen strategy in canonical order; fail closed if "
    "none remain"
)

_FORBIDDEN_TARGET_KEY_PARTS = (
    "actual",
    "deadline",
    "hit",
    "outcome",
    "publication",
    "result",
    "ticket",
    "winning",
)

# Each spec binds:
#   frozen_function   - the original P280D bet_index=1 callable (reproduces the
#                       pre-remediation duplicate root cause)
#   candidate_function- the ordered deterministic candidate callable used for
#                       publication selection (== frozen_function for strategies
#                       that were never duplicate-blocked at source level)
#   *_multi           - True when the callable returns a list of bets (the bet-1
#                       primary is element 0); False for a single ticket
# The P280AJ-added candidate callables live in the same frozen source files, so
# every spec keeps exactly one (source_path, sha256, git_blob_sha1) identity.
_SPECS = (
    {
        "strategy_id": "bet2_fourier_expansion_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_fourier_expansion_bet1",
        "frozen_multi": False,
        "candidate_function": "predict_fourier_expansion_bet1",
        "candidate_multi": False,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "biglotto_deviation_2bet",
        "source_path": "tools/predict_biglotto_deviation_2bet.py",
        "module": "tools.predict_biglotto_deviation_2bet",
        "frozen_function": "deviation_complement_2bet",
        "frozen_multi": True,
        "candidate_function": "deviation_complement_2bet",
        "candidate_multi": True,
        "kwargs": {"window": 50},
        "git_blob_sha1": "1ea8ad13aa2d26a8f7e64845b21d104542fcab4f",
        "sha256": "bb97c0bf044c5f9f37de7c6f27629e479bda650ca33dfeb7d0fbff840537bfba",
    },
    {
        "strategy_id": "biglotto_echo_aware_3bet",
        "source_path": "tools/predict_biglotto_echo_3bet.py",
        "module": "tools.predict_biglotto_echo_3bet",
        "frozen_function": "echo_aware_mixed_3bet",
        "frozen_multi": True,
        "candidate_function": "echo_aware_mixed_3bet",
        "candidate_multi": True,
        "kwargs": {"window": 50, "echo_weight": 0.25},
        "git_blob_sha1": "a1852cb7d63b995c3e05935425a31160cc434faa",
        "sha256": "ed4878fb59e22c44f26313646a762e034c7f92355e5df56a6f72eed887d11320",
    },
    {
        "strategy_id": "biglotto_triple_strike",
        "source_path": "tools/predict_biglotto_triple_strike.py",
        "module": "tools.predict_biglotto_triple_strike",
        "frozen_function": "generate_triple_strike",
        "frozen_multi": True,
        "candidate_function": "generate_triple_strike",
        "candidate_multi": True,
        "kwargs": {},
        "git_blob_sha1": "dd6c2cd5bc7e4957b42761309593d4874e58a5db",
        "sha256": "236fe529c01f1c39f4297258db6dc591e4612365720245fc8051540ed69954b7",
    },
    {
        "strategy_id": "biglotto_ts3_markov_4bet_w30",
        "source_path": "tools/backtest_biglotto_5bet_ts3markov.py",
        "module": "tools.backtest_biglotto_5bet_ts3markov",
        "frozen_function": "generate_ts3_markov_4bet",
        "frozen_multi": True,
        "candidate_function": "generate_ts3_markov_4bet",
        "candidate_multi": True,
        "kwargs": {"markov_window": 30},
        "git_blob_sha1": "817a43b92d21e5f74fc18b980994aa4e99cc494e",
        "sha256": "25760472baa09835b560f146ff4a0ce23fa2f2373a75d60c64ed557286dfbc2a",
    },
    {
        "strategy_id": "cold_complement_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_cold_complement_bet1",
        "frozen_multi": False,
        "candidate_function": "predict_cold_complement_bet1",
        "candidate_multi": False,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "coldpool15_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_coldpool15",
        "frozen_multi": False,
        "candidate_function": "predict_coldpool15_candidates",
        "candidate_multi": True,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "fourier30_markov30_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_fourier30_markov30_bet1",
        "frozen_multi": False,
        "candidate_function": "predict_fourier30_markov30_bet1",
        "candidate_multi": False,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "markov_2bet_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_markov_2bet_bet1",
        "frozen_multi": False,
        "candidate_function": "predict_markov_2bet_candidates",
        "candidate_multi": True,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "markov_single_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "frozen_function": "predict_markov_single",
        "frozen_multi": False,
        "candidate_function": "predict_markov_single",
        "candidate_multi": False,
        "kwargs": {},
        "git_blob_sha1": "37aaf7eb94625a16887412f8fd96c864eb6cdab8",
        "sha256": "f53dd87d98ba5ae6d3434b656e1e025b16b1bbc318696039e8c9b0887d1313da",
    },
    {
        "strategy_id": "ts3_regime_3bet",
        "source_path": "tools/backtest_biglotto_enhancements.py",
        "module": "tools.backtest_biglotto_enhancements",
        "frozen_function": "fourier_rhythm_bet",
        "frozen_multi": False,
        "candidate_function": "ts3_regime_candidates",
        "candidate_multi": True,
        "kwargs": {"window": 500},
        "git_blob_sha1": "9f293c05a9e50a21bdbf8cafeb372931ee789f21",
        "sha256": "b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e",
    },
)


def list_frozen_big649_strategy_ids() -> tuple[str, ...]:
    """Return the exact ordered frozen strategy identity."""
    return tuple(BIG649_FROZEN_STRATEGY_IDS)


def _git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _source_import_roots(tree: ast.AST) -> set[str]:
    roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    roots.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    return roots


def discover_strategy_adapters() -> list[dict[str, Any]]:
    """Statically discover and pin every frozen callable without importing it."""
    discovered: list[dict[str, Any]] = []
    for spec in _SPECS:
        path = REPO_ROOT / spec["source_path"]
        data = path.read_bytes()
        tree = ast.parse(data.decode("utf-8"), filename=str(path))
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        import_roots = _source_import_roots(tree)
        actual_sha256 = hashlib.sha256(data).hexdigest()
        actual_blob = _git_blob_sha1(data)
        identity_ok = (
            actual_sha256 == spec["sha256"]
            and actual_blob == spec["git_blob_sha1"]
            and spec["frozen_function"] in function_names
            and spec["candidate_function"] in function_names
        )
        discovered.append(
            {
                "strategy_id": spec["strategy_id"],
                "source_path": spec["source_path"],
                "module": spec["module"],
                "frozen_function": spec["frozen_function"],
                "candidate_function": spec["candidate_function"],
                "kwargs": copy.deepcopy(spec["kwargs"]),
                "expected_git_blob_sha1": spec["git_blob_sha1"],
                "actual_git_blob_sha1": actual_blob,
                "expected_sha256": spec["sha256"],
                "actual_sha256": actual_sha256,
                "source_imports_db_library": "sqlite3" in import_roots,
                "source_imports_network_library": bool(
                    import_roots
                    & {"httpx", "requests", "socket", "urllib", "urllib3"}
                ),
                "caller_history_supported": True,
                "bet_index": BET_INDEX,
                "randomness": "DETERMINISTIC",
                "status": "SAFE_CALLABLE_FOUND" if identity_ok else SOURCE_IDENTITY_MISMATCH_STOP,
            }
        )
    return discovered


def validate_strategy_adapter_contract(
    discovered: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Validate exact identities, pinned source bytes, and callable declarations."""
    records = list(discovered if discovered is not None else discover_strategy_adapters())
    ids = [record.get("strategy_id") for record in records]
    expected = list(list_frozen_big649_strategy_ids())
    if ids != expected:
        raise AdapterContractError(
            f"{MISSING_OR_EXTRA_STRATEGY_STOP}: expected={expected}, actual={ids}"
        )
    failed = [record["strategy_id"] for record in records if record.get("status") != "SAFE_CALLABLE_FOUND"]
    if failed:
        raise AdapterContractError(f"{SOURCE_IDENTITY_MISMATCH_STOP}: {failed}")
    if any(record.get("source_imports_network_library") for record in records):
        raise AdapterContractError("NETWORK_IMPORT_STOP")
    return copy.deepcopy(records)


def _canonical_ticket(numbers: Any, label: str) -> list[int]:
    if not isinstance(numbers, (list, tuple)) or len(numbers) != TICKET_SIZE:
        raise AdapterContractError(f"{label} must contain exactly six numbers")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in numbers):
        raise AdapterContractError(f"{label} must contain integers only")
    if len(set(numbers)) != TICKET_SIZE:
        raise AdapterContractError(f"{label} contains duplicate numbers")
    if any(number < NUMBER_MIN or number > NUMBER_MAX for number in numbers):
        raise AdapterContractError(f"{label} number outside 1..49")
    return sorted(numbers)


def _minimal_history(history: Sequence[Mapping[str, Any]]) -> list[dict[str, list[int]]]:
    if isinstance(history, (str, bytes)) or not isinstance(history, Sequence):
        raise AdapterContractError("history must be a caller-supplied sequence")
    if len(history) < MIN_HISTORY:
        raise AdapterContractError(f"history must contain at least {MIN_HISTORY} draws")
    minimal: list[dict[str, list[int]]] = []
    for index, draw in enumerate(history):
        if not isinstance(draw, Mapping) or "numbers" not in draw:
            raise AdapterContractError(f"history[{index}] must contain numbers")
        minimal.append({"numbers": _canonical_ticket(draw["numbers"], f"history[{index}]")})
    return minimal


def _validate_generation_context(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> None:
    if not isinstance(history_cutoff, str) or not history_cutoff.strip():
        raise AdapterContractError("history_cutoff is required")
    if not isinstance(target_metadata, Mapping):
        raise AdapterContractError("target_metadata must be caller supplied")
    if not isinstance(target_metadata.get("target_draw"), str) or not target_metadata["target_draw"]:
        raise AdapterContractError("target_metadata.target_draw is required")
    if target_metadata.get("synthetic") not in (True, False):
        raise AdapterContractError("target_metadata.synthetic must be boolean")
    forbidden = sorted(
        key
        for key in target_metadata
        if key != "target_draw"
        and any(part in key.lower() for part in _FORBIDDEN_TARGET_KEY_PARTS)
    )
    if forbidden:
        raise AdapterContractError(f"{TARGET_METADATA_MIXING_STOP}: {forbidden}")
    target = target_metadata["target_draw"]
    if target.isdigit() and history_cutoff.isdigit() and int(history_cutoff) >= int(target):
        raise AdapterContractError("history_cutoff must be strictly before target_draw")
    for draw in history:
        draw_id = draw.get("draw", draw.get("period")) if isinstance(draw, Mapping) else None
        if draw_id is not None and str(draw_id) == target:
            raise AdapterContractError("target draw must not appear in historical input")


def classify_strategy_randomness(
    *,
    strategy_kind: str = "deterministic",
    seed: str | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify randomness and fail closed on ungoverned stochastic output."""
    kind = strategy_kind.strip().lower() if isinstance(strategy_kind, str) else ""
    if kind == "deterministic":
        return {"status": DETERMINISTIC_NO_RANDOMNESS, "seed": None, "policy": None}
    if kind != "stochastic":
        raise AdapterContractError("strategy_kind must be deterministic or stochastic")
    if not isinstance(seed, str) or not seed.strip() or not isinstance(policy, Mapping) or not policy:
        raise AdapterContractError(STOCHASTIC_POLICY_MISSING_STOP)
    return {
        "status": STOCHASTIC_READY_WITH_SEED_AND_POLICY,
        "seed": seed,
        "policy": copy.deepcopy(dict(policy)),
    }


def _import_callable(spec: Mapping[str, Any], function_name: str):
    module = importlib.import_module(spec["module"])
    function = getattr(module, function_name, None)
    if not callable(function):
        raise AdapterContractError(f"missing callable: {spec['module']}:{function_name}")
    return function


def _normalize_bets(result: Any, *, multi: bool, label: str) -> list[list[int]]:
    """Normalize a source return into an ordered list of canonical tickets."""
    if multi:
        if isinstance(result, (str, bytes)) or not isinstance(result, (list, tuple)) or not result:
            raise AdapterContractError(f"{label} must return a non-empty list of bets")
        if not all(isinstance(bet, (list, tuple)) for bet in result):
            raise AdapterContractError(f"{label} must return a list of bets")
        return [_canonical_ticket(bet, label) for bet in result]
    return [_canonical_ticket(result, label)]


def _frozen_primary_ticket(
    spec: Mapping[str, Any], history: list[dict[str, list[int]]]
) -> list[int]:
    function = _import_callable(spec, spec["frozen_function"])
    result = function(history, **dict(spec["kwargs"]))
    bets = _normalize_bets(result, multi=spec["frozen_multi"], label=spec["strategy_id"])
    return bets[0]


def _candidate_tickets(
    spec: Mapping[str, Any], history: list[dict[str, list[int]]]
) -> list[list[int]]:
    function = _import_callable(spec, spec["candidate_function"])
    result = function(history, **dict(spec["kwargs"]))
    bets = _normalize_bets(result, multi=spec["candidate_multi"], label=spec["strategy_id"])
    # Preserve order while removing exact duplicate candidates within one strategy.
    seen: set[tuple[int, ...]] = set()
    unique: list[list[int]] = []
    for bet in bets:
        key = tuple(bet)
        if key not in seen:
            seen.add(key)
            unique.append(bet)
    return unique


def enumerate_strategy_candidates(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Enumerate the ordered deterministic candidate tickets for every strategy."""
    validate_strategy_adapter_contract()
    _validate_generation_context(history, history_cutoff, target_metadata)
    minimal = _minimal_history(history)
    return [
        {
            "strategy_id": spec["strategy_id"],
            "module": spec["module"],
            "source_callable": f"{spec['module']}:{spec['candidate_function']}",
            "source_sha256": spec["sha256"],
            "frozen_primary_ticket": _frozen_primary_ticket(spec, minimal),
            "candidates": _candidate_tickets(spec, minimal),
        }
        for spec in _SPECS
    ]


def frozen_primary_outputs(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return the original P280D bet_index=1 outputs (pre-remediation primaries)."""
    enumerated = enumerate_strategy_candidates(history, history_cutoff, target_metadata)
    return [
        {
            "strategy_id": record["strategy_id"],
            "bet_index": BET_INDEX,
            "predicted_main_numbers": record["frozen_primary_ticket"],
        }
        for record in enumerated
    ]


def frozen_primary_duplicate_groups(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> list[list[str]]:
    """Reproduce the pre-remediation duplicate complete-ticket groups (P280AH root)."""
    primaries = frozen_primary_outputs(history, history_cutoff, target_metadata)
    ticket_to_ids: dict[tuple[int, ...], list[str]] = {}
    for record in primaries:
        ticket_to_ids.setdefault(
            tuple(record["predicted_main_numbers"]), []
        ).append(record["strategy_id"])
    return [sorted(ids) for ids in ticket_to_ids.values() if len(ids) > 1]


def resolve_unique_strategy_outputs(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministically select one non-duplicate complete ticket per strategy.

    Fails closed (``UNRESOLVED_DUPLICATE_STOP``) if any strategy exhausts its
    deterministic candidates without yielding a complete ticket distinct from the
    tickets already claimed by earlier frozen strategies.
    """
    enumerated = enumerate_strategy_candidates(history, history_cutoff, target_metadata)
    claimed: set[tuple[int, ...]] = set()
    outputs: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for record in enumerated:
        chosen_index = None
        chosen_ticket = None
        for index, candidate in enumerate(record["candidates"]):
            key = tuple(candidate)
            if key not in claimed:
                chosen_index = index
                chosen_ticket = candidate
                claimed.add(key)
                break
        if chosen_ticket is None:
            raise AdapterContractError(
                f"{UNRESOLVED_DUPLICATE_STOP}: {record['strategy_id']} has no "
                f"non-duplicate candidate among {len(record['candidates'])} options"
            )
        outputs.append(
            {
                "strategy_id": record["strategy_id"],
                "bet_index": BET_INDEX,
                "predicted_main_numbers": chosen_ticket,
            }
        )
        provenance.append(
            {
                "strategy_id": record["strategy_id"],
                "source_callable": record["source_callable"],
                "source_sha256": record["source_sha256"],
                "candidate_count": len(record["candidates"]),
                "selected_candidate_index": chosen_index,
                "rebound_off_frozen_primary": chosen_ticket != record["frozen_primary_ticket"],
                "selection_rule": SELECTION_RULE,
            }
        )
    return {"outputs": outputs, "provenance": provenance}


def _canonical_outputs(
    outputs: Sequence[Mapping[str, Any]], *, enforce_unique: bool
) -> tuple[list[dict[str, Any]], list[list[str]]]:
    if isinstance(outputs, (str, bytes)) or not isinstance(outputs, Sequence):
        raise AdapterContractError("strategy outputs must be a sequence")
    records: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(outputs):
        if not isinstance(record, Mapping) or set(record) != {
            "strategy_id", "bet_index", "predicted_main_numbers"
        }:
            raise AdapterContractError(f"output[{index}] fields mismatch")
        strategy_id = record["strategy_id"]
        if not isinstance(strategy_id, str) or strategy_id in records:
            raise AdapterContractError(f"duplicate or invalid strategy_id: {strategy_id}")
        if record["bet_index"] != BET_INDEX or isinstance(record["bet_index"], bool):
            raise AdapterContractError(f"{strategy_id} must use bet_index=1")
        records[strategy_id] = {
            "strategy_id": strategy_id,
            "bet_index": BET_INDEX,
            "predicted_main_numbers": _canonical_ticket(
                record["predicted_main_numbers"], strategy_id
            ),
        }
    expected = set(list_frozen_big649_strategy_ids())
    actual = set(records)
    if actual != expected:
        raise AdapterContractError(
            f"{MISSING_OR_EXTRA_STRATEGY_STOP}: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    canonical = [records[strategy_id] for strategy_id in list_frozen_big649_strategy_ids()]
    ticket_to_ids: dict[tuple[int, ...], list[str]] = {}
    for record in canonical:
        ticket_to_ids.setdefault(tuple(record["predicted_main_numbers"]), []).append(
            record["strategy_id"]
        )
    duplicates = [ids for ids in ticket_to_ids.values() if len(ids) > 1]
    if enforce_unique and duplicates:
        raise AdapterContractError(
            f"{DUPLICATE_COMPLETE_TICKET_STOP}: "
            f"{json.dumps(duplicates, separators=(',', ':'))}"
        )
    return canonical, duplicates


def validate_strategy_outputs(outputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate exact identities and tickets; duplicate complete tickets always STOP."""
    canonical, _ = _canonical_outputs(outputs, enforce_unique=True)
    return canonical


def compute_strategy_output_digest(outputs: Sequence[Mapping[str, Any]]) -> str:
    """Digest exact resolved source outputs (sorted, canonical JSON)."""
    canonical, _ = _canonical_outputs(outputs, enforce_unique=False)
    rendered = json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def generate_strategy_outputs_no_db(
    *,
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
    previous_output_digest: str | None = None,
) -> list[dict[str, Any]]:
    """Resolve the eleven unique source outputs and fail closed on invalid output."""
    resolved = resolve_unique_strategy_outputs(history, history_cutoff, target_metadata)
    outputs = resolved["outputs"]
    digest = compute_strategy_output_digest(outputs)
    if previous_output_digest is not None and previous_output_digest != digest:
        raise AdapterContractError(DETERMINISTIC_MISMATCH_STOP)
    return validate_strategy_outputs(outputs)


def build_adapter_report(
    *,
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a side-effect-free capability, resolution, and integration report."""
    discovery = validate_strategy_adapter_contract()
    frozen_groups = frozen_primary_duplicate_groups(history, history_cutoff, target_metadata)

    first = resolve_unique_strategy_outputs(history, history_cutoff, target_metadata)
    second = resolve_unique_strategy_outputs(history, history_cutoff, target_metadata)
    first_outputs = first["outputs"]
    first_digest = compute_strategy_output_digest(first_outputs)
    second_digest = compute_strategy_output_digest(second["outputs"])
    if first_digest != second_digest:
        raise AdapterContractError(DETERMINISTIC_MISMATCH_STOP)

    validation_status = "PASS"
    validation_error = None
    try:
        validate_strategy_outputs(first_outputs)
    except AdapterContractError as exc:
        validation_status = DUPLICATE_COMPLETE_TICKET_STOP
        validation_error = str(exc)

    compatibility_status = "PASS_SAFE_VALIDATE_ONLY"
    compatibility_error = None
    try:
        build_publication_manifest_candidate(
            target_draw=SYNTHETIC_TARGET,
            target_draw_date="2099-01-02",
            official_source_url="https://example.invalid/p280aj-synthetic-source",
            official_source_accessed_at="2099-01-01T01:00:00+08:00",
            official_deadline="2099-01-01T20:00:00+08:00",
            generation_timestamp_utc="2099-01-01T02:00:00Z",
            cutoff_policy="SYNTHETIC_HISTORY_STRICTLY_BEFORE_TARGET",
            history_cutoff=history_cutoff,
            tickets=first_outputs,
            source_digests={"p280d_frozen_sources": first_digest},
            tool_digests={"p280aj_adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            mode=SAFE_VALIDATE_ONLY,
        )
    except PublicationGuardError as exc:
        compatibility_status = "BLOCKED"
        compatibility_error = str(exc)

    resolved_unique = validation_status == "PASS" and compatibility_status == "PASS_SAFE_VALIDATE_ONLY"
    return {
        "schema_version": "p280aj_big649_no_db_strategy_output_adapter_v2",
        "final_classification": (
            "P280AJ_NO_DB_ADAPTER_RESOLVES_11_UNIQUE_TICKETS_NOT_ACTIVATED"
            if resolved_unique
            else "P280AJ_NO_DB_ADAPTER_RESOLUTION_BLOCKED_NOT_ACTIVATED"
        ),
        "adapter_implemented": True,
        "publication_compatible": resolved_unique,
        "strategy_ids": list(list_frozen_big649_strategy_ids()),
        "strategy_count": len(first_outputs),
        "N": N,
        "bet_index": BET_INDEX,
        "endpoint": ENDPOINT,
        "capabilities": discovery,
        "generation_status": "EXACT_FROZEN_SOURCE_CANDIDATES_RESOLVED_FROM_CALLER_HISTORY",
        "ticket_shape_status": "PASS_11_OF_11",
        "strategy_output_digest": first_digest,
        "deterministic_rerun_status": "PASS_BYTE_STABLE_DIGEST",
        "randomness_policy": classify_strategy_randomness(),
        "output_validation_status": validation_status,
        "output_validation_error": validation_error,
        "frozen_primary_duplicate_groups": frozen_groups,
        "resolved_unique_ticket_count": len({
            tuple(record["predicted_main_numbers"]) for record in first_outputs
        }),
        "selection_rule": SELECTION_RULE,
        "selection_provenance": first["provenance"],
        "p280ad_runner_compatibility": {
            "status": compatibility_status,
            "mode": SAFE_VALIDATE_ONLY,
            "synthetic_target": SYNTHETIC_TARGET,
            "error": compatibility_error,
        },
        "database_access": {
            "opened": False,
            "queried": False,
            "copied": False,
            "written": False,
        },
        "network_used": False,
        "github_side_effect": False,
        "real_target_selected": False,
        "official_deadline_lookup": False,
        "real_ticket_published": False,
        "publication_pr_created": False,
        "future_evaluation_started": False,
        "outcome_used": False,
        "fabricated_fallback_output": False,
        "outcome_aware_selection": False,
        "historical_best_past_selection": False,
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "registry_mutated": False,
        "activation_authorized": False,
        "production_ready_claim": False,
        "remaining_blocker": (
            None
            if resolved_unique
            else "Deterministic source candidates could not yield 11 unique complete tickets."
        ),
        "next_recommended_step": (
            "Independent audit of the P280AJ strategy-interface and freeze "
            "reconciliation, then separate Owner authorization for the first real "
            "publication. No activation is performed by this adapter."
        ),
    }
