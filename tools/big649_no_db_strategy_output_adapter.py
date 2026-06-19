"""Fail-closed no-DB adapter for the frozen BIG 6/49 strategy family.

The adapter invokes only the exact source identities frozen by P280D. Callers
must provide historical draws, a cutoff, and target metadata. This module does
not read a database, use the network, select a target, look up a deadline,
write publication artifacts, or invent replacement tickets.
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
    "build_adapter_report",
    "classify_strategy_randomness",
    "compute_strategy_output_digest",
    "discover_strategy_adapters",
    "generate_strategy_outputs_no_db",
    "list_frozen_big649_strategy_ids",
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
DETERMINISTIC_MISMATCH_STOP = "DETERMINISTIC_MISMATCH_STOP"
STOCHASTIC_POLICY_MISSING_STOP = "STOCHASTIC_POLICY_MISSING_STOP"
DETERMINISTIC_NO_RANDOMNESS = "DETERMINISTIC_NO_RANDOMNESS"
STOCHASTIC_READY_WITH_SEED_AND_POLICY = "STOCHASTIC_READY_WITH_SEED_AND_POLICY"
TARGET_METADATA_MIXING_STOP = "TARGET_METADATA_MIXING_STOP"
SOURCE_IDENTITY_MISMATCH_STOP = "SOURCE_IDENTITY_MISMATCH_STOP"

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

_SPECS = (
    {
        "strategy_id": "bet2_fourier_expansion_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_fourier_expansion_bet1",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "biglotto_deviation_2bet",
        "source_path": "tools/predict_biglotto_deviation_2bet.py",
        "module": "tools.predict_biglotto_deviation_2bet",
        "function": "deviation_complement_2bet",
        "kwargs": {"window": 50},
        "result_index": 0,
        "git_blob_sha1": "1ea8ad13aa2d26a8f7e64845b21d104542fcab4f",
        "sha256": "bb97c0bf044c5f9f37de7c6f27629e479bda650ca33dfeb7d0fbff840537bfba",
    },
    {
        "strategy_id": "biglotto_echo_aware_3bet",
        "source_path": "tools/predict_biglotto_echo_3bet.py",
        "module": "tools.predict_biglotto_echo_3bet",
        "function": "echo_aware_mixed_3bet",
        "kwargs": {"window": 50, "echo_weight": 0.25},
        "result_index": 0,
        "git_blob_sha1": "a1852cb7d63b995c3e05935425a31160cc434faa",
        "sha256": "ed4878fb59e22c44f26313646a762e034c7f92355e5df56a6f72eed887d11320",
    },
    {
        "strategy_id": "biglotto_triple_strike",
        "source_path": "tools/predict_biglotto_triple_strike.py",
        "module": "tools.predict_biglotto_triple_strike",
        "function": "generate_triple_strike",
        "kwargs": {},
        "result_index": 0,
        "git_blob_sha1": "dd6c2cd5bc7e4957b42761309593d4874e58a5db",
        "sha256": "236fe529c01f1c39f4297258db6dc591e4612365720245fc8051540ed69954b7",
    },
    {
        "strategy_id": "biglotto_ts3_markov_4bet_w30",
        "source_path": "tools/backtest_biglotto_5bet_ts3markov.py",
        "module": "tools.backtest_biglotto_5bet_ts3markov",
        "function": "generate_ts3_markov_4bet",
        "kwargs": {"markov_window": 30},
        "result_index": 0,
        "git_blob_sha1": "817a43b92d21e5f74fc18b980994aa4e99cc494e",
        "sha256": "25760472baa09835b560f146ff4a0ce23fa2f2373a75d60c64ed557286dfbc2a",
    },
    {
        "strategy_id": "cold_complement_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_cold_complement_bet1",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "coldpool15_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_coldpool15",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "fourier30_markov30_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_fourier30_markov30_bet1",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "markov_2bet_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_markov_2bet_bet1",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "markov_single_biglotto",
        "source_path": "lottery_api/models/p42_wave3_biglotto_adapters.py",
        "module": "lottery_api.models.p42_wave3_biglotto_adapters",
        "function": "predict_markov_single",
        "kwargs": {},
        "result_index": None,
        "git_blob_sha1": "ce6911405c15656fbfe35733edbe4e51938afdbd",
        "sha256": "19c8458421112f61137f96a7de92a7734b525d8cbd0673c65d4c09f94b3b664b",
    },
    {
        "strategy_id": "ts3_regime_3bet",
        "source_path": "tools/backtest_biglotto_enhancements.py",
        "module": "tools.backtest_biglotto_enhancements",
        "function": "fourier_rhythm_bet",
        "kwargs": {"window": 500},
        "result_index": None,
        "git_blob_sha1": "18a48fd216b4cc213cb505d069a6be98ce09fe68",
        "sha256": "088e0815a0f1afb2aa884b0215882090efa72afeea0cc020d6ec8145cb143260",
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
            and spec["function"] in function_names
        )
        discovered.append(
            {
                "strategy_id": spec["strategy_id"],
                "source_path": spec["source_path"],
                "module": spec["module"],
                "function": spec["function"],
                "kwargs": copy.deepcopy(spec["kwargs"]),
                "result_index": spec["result_index"],
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


def _call_frozen_source(spec: Mapping[str, Any], history: list[dict[str, list[int]]]) -> list[int]:
    module = importlib.import_module(spec["module"])
    function = getattr(module, spec["function"], None)
    if not callable(function):
        raise AdapterContractError(f"missing callable: {spec['module']}:{spec['function']}")
    result = function(history, **dict(spec["kwargs"]))
    if spec["result_index"] is not None:
        if not isinstance(result, (list, tuple)) or len(result) <= spec["result_index"]:
            raise AdapterContractError(f"missing bet_index=1 output: {spec['strategy_id']}")
        result = result[spec["result_index"]]
    return _canonical_ticket(result, spec["strategy_id"])


def _generate_source_outputs(
    history: Sequence[Mapping[str, Any]],
    history_cutoff: str,
    target_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    validate_strategy_adapter_contract()
    _validate_generation_context(history, history_cutoff, target_metadata)
    minimal = _minimal_history(history)
    return [
        {
            "strategy_id": spec["strategy_id"],
            "bet_index": BET_INDEX,
            "predicted_main_numbers": _call_frozen_source(spec, minimal),
        }
        for spec in _SPECS
    ]


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
    """Digest exact source outputs, including blocked duplicate evidence."""
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
    """Generate exact source outputs and fail closed before returning invalid output."""
    outputs = _generate_source_outputs(history, history_cutoff, target_metadata)
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
    """Build a side-effect-free capability and integration report."""
    discovery = validate_strategy_adapter_contract()
    first = _generate_source_outputs(history, history_cutoff, target_metadata)
    second = _generate_source_outputs(history, history_cutoff, target_metadata)
    first_digest = compute_strategy_output_digest(first)
    second_digest = compute_strategy_output_digest(second)
    if first_digest != second_digest:
        raise AdapterContractError(DETERMINISTIC_MISMATCH_STOP)
    _, duplicate_groups = _canonical_outputs(first, enforce_unique=False)

    validation_status = "PASS"
    validation_error = None
    try:
        validate_strategy_outputs(first)
    except AdapterContractError as exc:
        validation_status = DUPLICATE_COMPLETE_TICKET_STOP
        validation_error = str(exc)

    compatibility_status = "PASS_SAFE_VALIDATE_ONLY"
    compatibility_error = None
    try:
        build_publication_manifest_candidate(
            target_draw=SYNTHETIC_TARGET,
            target_draw_date="2099-01-02",
            official_source_url="https://example.invalid/p280ag-synthetic-source",
            official_source_accessed_at="2099-01-01T01:00:00+08:00",
            official_deadline="2099-01-01T20:00:00+08:00",
            generation_timestamp_utc="2099-01-01T02:00:00Z",
            cutoff_policy="SYNTHETIC_HISTORY_STRICTLY_BEFORE_TARGET",
            history_cutoff=history_cutoff,
            tickets=first,
            source_digests={"p280d_frozen_sources": first_digest},
            tool_digests={"p280ag_adapter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
            mode=SAFE_VALIDATE_ONLY,
        )
    except PublicationGuardError as exc:
        compatibility_status = "BLOCKED_DUPLICATE_COMPLETE_TICKETS"
        compatibility_error = str(exc)

    blocked = bool(duplicate_groups) or compatibility_status != "PASS_SAFE_VALIDATE_ONLY"
    return {
        "schema_version": "p280ag_big649_no_db_strategy_output_adapter_v1",
        "final_classification": (
            "P280AG_NO_DB_ADAPTER_BLOCKED_BY_STRATEGY_INTERFACE_GAP_NO_ACTIVATION"
            if blocked
            else "P280AG_BIG649_NO_DB_STRATEGY_OUTPUT_ADAPTER_PR_OPEN_NOT_ACTIVATED"
        ),
        "adapter_implemented": True,
        "publication_compatible": not blocked,
        "strategy_ids": list(list_frozen_big649_strategy_ids()),
        "strategy_count": len(first),
        "N": N,
        "bet_index": BET_INDEX,
        "endpoint": ENDPOINT,
        "capabilities": discovery,
        "generation_status": "EXACT_FROZEN_SOURCE_OUTPUTS_GENERATED_FROM_CALLER_HISTORY",
        "ticket_shape_status": "PASS_11_OF_11",
        "strategy_output_digest": first_digest,
        "deterministic_rerun_status": "PASS_BYTE_STABLE_DIGEST",
        "randomness_policy": classify_strategy_randomness(),
        "output_validation_status": validation_status,
        "output_validation_error": validation_error,
        "duplicate_complete_ticket_groups": duplicate_groups,
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
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation_authorized": False,
        "production_ready_claim": False,
        "remaining_blocker": (
            "Exact frozen bet_index=1 source identities produce duplicate complete "
            "tickets, while the P280AD manifest contract requires 11 unique complete "
            "tickets. No fallback, alternate bet, or algorithm rewrite is authorized."
        ),
        "next_recommended_step": (
            "Request Owner authorization for the minimum strategy-interface remediation "
            "needed to define distinct frozen N=1 outputs, then independently re-audit."
        ),
    }
