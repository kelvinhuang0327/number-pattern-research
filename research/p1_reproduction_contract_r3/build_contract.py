#!/usr/bin/env python3
"""Build the deterministic, offline P1 reproduction contract authority R3.

The builder reads only exact immutable Git objects.  It does not import or run
the pinned strategy modules, open a database, access a network, or reproduce a
backtest.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable


SCHEMA_NAME = "LotteryNewP1ReproductionContract"
SCHEMA_VERSION = "3.0.0"
TASK_ID = "LOTTERYNEW_P1_REPRODUCTION_CONTRACT_REPAIR_R3"
TARGET_REPOSITORY = "kelvinhuang0327/number-pattern-research"
PACKAGE_ROOT = "research/p1_reproduction_contract_r3"
TEST_PATH = "tests/test_p1_reproduction_contract_r3.py"
CONTENT_PATHS = (
    f"{PACKAGE_ROOT}/build_contract.py",
    f"{PACKAGE_ROOT}/contract.json",
    f"{PACKAGE_ROOT}/orthogonal_authority.json",
    f"{PACKAGE_ROOT}/REPORT.md",
    TEST_PATH,
)
PACKAGE_PATHS = (
    *CONTENT_PATHS[:4],
    f"{PACKAGE_ROOT}/MANIFEST.json",
    f"{PACKAGE_ROOT}/SHA256SUMS",
    TEST_PATH,
)
DIRECT_IMPORT_CLOSURE = (
    "fourier_rhythm_bet",
    "cold_numbers_bet",
    "tail_balance_bet",
    "markov_orthogonal_bet",
)
CALLABLE_CLOSURE = (
    "biglotto_5bet_orthogonal",
    "fourier_rhythm_bet",
    "cold_numbers_bet",
    "_sum_target",
    "tail_balance_bet",
    "markov_orthogonal_bet",
)
BLOCKED_DEPENDENCY_NAMES = frozenset(
    {
        "DatabaseManager",
        "aiohttp",
        "httpx",
        "random",
        "requests",
        "secrets",
        "socket",
        "sqlite3",
        "urllib",
    }
)
BLOCKED_IO_CALLS = frozenset({"open", "urlopen"})


@dataclasses.dataclass(frozen=True)
class Pins:
    minimum_origin_main: str = "e6037b06c3030bc1efc6538fc1a936bd763958b6"
    minimum_origin_main_tree: str = "3179953ef8112cb1b40670e9fe6826c73869fc28"
    environment_merge_commit: str = "e6037b06c3030bc1efc6538fc1a936bd763958b6"
    environment_fixed_head: str = "17874e95a83713f7629e74c7963562581f6c6022"
    environment_fixed_tree: str = "cc0e99e5931fdc6918c92b67e45060ec921e6b55"
    environment_root: str = "research/p1_reproduction_environment_authority_r3"
    installation_receipt_sha256: str = (
        "4f3d94933a42d98d48448ed188855f3d296795bbb73b9e84dd6c55229cce87aa"
    )
    runtime_fingerprint_v3: str = (
        "372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e"
    )
    historical_commit: str = "28940a2572c051c6ba8b2ab6a077f706e800477d"
    historical_path: str = "tools/quick_predict.py"
    historical_blob: str = "bb2826b84a782aa6f68d472b30221fa2d1781a4b"
    historical_function: str = "biglotto_p1_deviation_5bet"
    adopted_commit: str = "e56ce9f196342e9d50edc9fd19c42f72c1fa2047"
    adopted_path: str = "tools/quick_predict.py"
    adopted_blob: str = "7ee44fa584442419410d675b3ec3598c161ad2ec"
    adopted_symbol: str = "biglotto_5bet_orthogonal"
    helper_commit: str = "e56ce9f196342e9d50edc9fd19c42f72c1fa2047"
    helper_comparison_commit: str = "d9c27f51ed42335e467047c1f2bcb00528be68e0"
    helper_path: str = "tools/backtest_biglotto_markov_4bet.py"
    helper_blob: str = "cd5b6f780cdf0d2363a631dc5faba0a013a52566"
    lottery_type: str = "BIG_LOTTO"
    main_number_min: int = 1
    main_number_max: int = 49
    ticket_count: int = 5
    evidence_status: str = "HISTORICAL_RESEARCH_ONLY"
    current_significance: str = "NOT_ESTABLISHED"
    diagnostic_only: bool = True


PINS = Pins()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_slug(repo: Path) -> str:
    remote = _run_git(repo, "config", "--get", "remote.origin.url").decode().strip()
    normalized = remote.removesuffix(".git")
    if normalized.startswith("git@github.com:"):
        normalized = normalized.removeprefix("git@github.com:")
    elif "github.com/" in normalized:
        normalized = normalized.split("github.com/", 1)[1]
    if normalized != TARGET_REPOSITORY:
        raise RuntimeError(
            f"target repository mismatch: expected={TARGET_REPOSITORY} actual={normalized}"
        )
    return normalized


def tree_oid(repo: Path, commit: str) -> str:
    return _run_git(repo, "rev-parse", f"{commit}^{{tree}}").decode().strip()


def blob_oid(repo: Path, commit: str, path: str) -> str:
    output = _run_git(repo, "ls-tree", commit, "--", path).decode().strip()
    parts = output.split(maxsplit=3)
    if len(parts) != 4 or parts[1] != "blob" or parts[3] != path:
        raise RuntimeError(f"missing pinned Git blob: {commit}:{path}")
    return parts[2]


def blob_bytes(repo: Path, commit: str, path: str) -> bytes:
    expected = blob_oid(repo, commit, path)
    payload = _run_git(repo, "show", f"{commit}:{path}")
    actual = _run_git(repo, "hash-object", "--stdin", input_bytes=payload)
    actual_oid = actual.decode().strip()
    if actual_oid != expected:
        raise RuntimeError(
            f"immutable blob read mismatch: {commit}:{path} "
            f"expected={expected} actual={actual_oid}"
        )
    return payload


def _run_git(
    repo: Path,
    *args: str,
    input_bytes: bytes | None = None,
) -> bytes:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        check=False,
        capture_output=True,
        env=env,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"immutable Git read failed: {' '.join(args)}: {message}")
    return completed.stdout


def require_blob(repo: Path, commit: str, path: str, expected: str) -> bytes:
    actual = blob_oid(repo, commit, path)
    if actual != expected:
        raise RuntimeError(
            f"pinned blob mismatch: {commit}:{path} expected={expected} actual={actual}"
        )
    return blob_bytes(repo, commit, path)


def parse_module(payload: bytes, identity: str) -> ast.Module:
    try:
        return ast.parse(payload.decode("utf-8"), filename=identity)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError(f"pinned source is not valid UTF-8 Python: {identity}") from exc


def function_definition(module: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) != 1 or not isinstance(matches[0], ast.FunctionDef):
        raise RuntimeError(f"expected exactly one synchronous function: {name}")
    return matches[0]


def assigned_integer(function: ast.FunctionDef, name: str) -> int:
    values: list[int] = []
    for node in function.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int)
        ):
            values.append(node.value.value)
    if len(values) != 1:
        raise RuntimeError(f"expected one integer assignment for {name}")
    return values[0]


def returned_ticket_names(function: ast.FunctionDef) -> tuple[str, ...]:
    returns = [node for node in function.body if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.List):
        raise RuntimeError(f"{function.name} must have one literal-list return")
    result: list[str] = []
    for element in returns[0].value.elts:
        if not isinstance(element, ast.Dict) or len(element.keys) != 1:
            raise RuntimeError(f"{function.name} return entries must be one-key mappings")
        key = element.keys[0]
        value = element.values[0]
        if not (
            isinstance(key, ast.Constant)
            and key.value == "numbers"
            and isinstance(value, ast.Name)
        ):
            raise RuntimeError(f"{function.name} ticket entries must bind numbers names")
        result.append(value.id)
    return tuple(result)


def direct_helper_imports(function: ast.FunctionDef) -> tuple[str, ...]:
    imports = [
        node
        for node in function.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "tools.backtest_biglotto_markov_4bet"
    ]
    if len(imports) != 1:
        raise RuntimeError("orthogonal function must have one exact helper import")
    return tuple(alias.name for alias in imports[0].names)


def attribute_root(node: ast.Attribute) -> str | None:
    value: ast.expr = node
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def verify_callable_isolation(functions: Iterable[ast.FunctionDef]) -> dict[str, Any]:
    blocked_names: set[str] = set()
    blocked_calls: set[str] = set()
    for function in functions:
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and node.id in BLOCKED_DEPENDENCY_NAMES:
                blocked_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                root = attribute_root(node)
                if root in BLOCKED_DEPENDENCY_NAMES:
                    blocked_names.add(root)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_IO_CALLS:
                    blocked_calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute) and node.func.attr in BLOCKED_IO_CALLS:
                    blocked_calls.add(node.func.attr)
    if blocked_names or blocked_calls:
        raise RuntimeError(
            "blocked dependency in approved callable closure: "
            f"names={sorted(blocked_names)} calls={sorted(blocked_calls)}"
        )
    return {
        "db_dependency": "ABSENT_IN_APPROVED_CALLABLE_CLOSURE",
        "network_dependency": "ABSENT_IN_APPROVED_CALLABLE_CLOSURE",
        "random_dependency": "ABSENT_IN_APPROVED_CALLABLE_CLOSURE",
        "filesystem_dependency": "ABSENT_IN_APPROVED_CALLABLE_CLOSURE",
        "inspection_method": "PYTHON_AST_NAMED_FUNCTION_CLOSURE",
    }


def validate_policy_pins(pins: Pins) -> None:
    required = {
        "lottery_type": "BIG_LOTTO",
        "main_number_min": 1,
        "main_number_max": 49,
        "ticket_count": 5,
        "evidence_status": "HISTORICAL_RESEARCH_ONLY",
        "current_significance": "NOT_ESTABLISHED",
        "diagnostic_only": True,
    }
    for field, expected in required.items():
        actual = getattr(pins, field)
        if actual != expected:
            raise RuntimeError(
                f"closed policy mismatch for {field}: expected={expected!r} actual={actual!r}"
            )


def validate_control_policy(
    *,
    lottery_type: str,
    maximum_number: int,
    source_role: str,
) -> None:
    if lottery_type != "BIG_LOTTO" or maximum_number != 49:
        raise RuntimeError("POWER_LOTTO 1-38 control substitution is forbidden")
    if source_role == "ALGORITHM_SOURCE_AUTHORITY":
        raise RuntimeError("the P1 strategy may not serve as its own control")
    if source_role != "DIAGNOSTIC_CONTROL_AUTHORITY":
        raise RuntimeError(f"unsupported control source role: {source_role}")


def source_evidence(repo: Path, pins: Pins) -> dict[str, Any]:
    historical_payload = require_blob(
        repo, pins.historical_commit, pins.historical_path, pins.historical_blob
    )
    historical_module = parse_module(
        historical_payload, f"{pins.historical_commit}:{pins.historical_path}"
    )
    historical_symbols = {
        node.name
        for node in historical_module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if pins.adopted_symbol in historical_symbols:
        raise RuntimeError("historical orthogonal symbol must be absent")
    historical_function = function_definition(
        historical_module, pins.historical_function
    )
    historical_tickets = returned_ticket_names(historical_function)
    if len(historical_tickets) != 5:
        raise RuntimeError("historical P1 source must expose five ordered tickets")

    adopted_payload = require_blob(
        repo, pins.adopted_commit, pins.adopted_path, pins.adopted_blob
    )
    adopted_module = parse_module(
        adopted_payload, f"{pins.adopted_commit}:{pins.adopted_path}"
    )
    adopted_function = function_definition(adopted_module, pins.adopted_symbol)
    imports = direct_helper_imports(adopted_function)
    if imports != DIRECT_IMPORT_CLOSURE:
        raise RuntimeError(
            f"direct helper import closure mismatch: expected={DIRECT_IMPORT_CLOSURE} "
            f"actual={imports}"
        )
    max_number = assigned_integer(adopted_function, "MAX_NUM")
    if max_number != pins.main_number_max:
        raise RuntimeError(
            f"BIG_LOTTO maximum mismatch: expected={pins.main_number_max} actual={max_number}"
        )
    adopted_tickets = returned_ticket_names(adopted_function)
    if adopted_tickets != ("bet1", "bet2", "bet3", "bet4", "bet5"):
        raise RuntimeError(
            f"ordered orthogonal tickets mismatch: actual={adopted_tickets}"
        )
    if len(adopted_tickets) != pins.ticket_count:
        raise RuntimeError(
            f"ticket count mismatch: expected={pins.ticket_count} "
            f"actual={len(adopted_tickets)}"
        )

    helper_payload = require_blob(
        repo, pins.helper_commit, pins.helper_path, pins.helper_blob
    )
    comparison_blob = blob_oid(
        repo, pins.helper_comparison_commit, pins.helper_path
    )
    if comparison_blob != pins.helper_blob:
        raise RuntimeError(
            "helper comparison identity mismatch: "
            f"expected={pins.helper_blob} actual={comparison_blob}"
        )
    helper_module = parse_module(
        helper_payload, f"{pins.helper_commit}:{pins.helper_path}"
    )
    helper_functions = {
        name: function_definition(helper_module, name)
        for name in (*DIRECT_IMPORT_CLOSURE, "_sum_target")
    }
    isolation = verify_callable_isolation(
        [adopted_function, *helper_functions.values()]
    )
    helper_max = next(
        (
            node.value.value
            for node in helper_module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "MAX_NUM"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int)
        ),
        None,
    )
    if helper_max != pins.main_number_max:
        raise RuntimeError(
            f"helper BIG_LOTTO maximum mismatch: expected={pins.main_number_max} "
            f"actual={helper_max}"
        )

    return {
        "historical_symbol_status": "ABSENT",
        "historical_ordered_tickets": list(historical_tickets),
        "adopted_symbol_status": "PRESENT",
        "direct_import_closure": list(imports),
        "callable_closure": list(CALLABLE_CLOSURE),
        "ordered_tickets": list(adopted_tickets),
        "main_number_range": [pins.main_number_min, max_number],
        "ticket_count": len(adopted_tickets),
        "helper_blob_at_adopted_commit": pins.helper_blob,
        "helper_blob_at_comparison_commit": comparison_blob,
        "helper_blob_equality": True,
        "isolation": isolation,
        "module_level_nonclosure_findings": [
            {
                "finding": "helper module imports DatabaseManager outside the named callable closure",
                "disposition": "EXCLUDED_NOT_APPROVED_NOT_EXECUTED",
            },
            {
                "finding": "helper module contains unrelated backtest and seeded simulation code outside the named callable closure",
                "disposition": "EXCLUDED_NOT_APPROVED_NOT_EXECUTED",
            },
        ],
    }


def environment_evidence(repo: Path, pins: Pins) -> dict[str, Any]:
    actual_tree = tree_oid(repo, pins.environment_merge_commit)
    if actual_tree != pins.minimum_origin_main_tree:
        raise RuntimeError(
            "Environment R3 merge tree mismatch: "
            f"expected={pins.minimum_origin_main_tree} actual={actual_tree}"
        )
    receipt_path = f"{pins.environment_root}/installation_receipt.json"
    receipt = blob_bytes(repo, pins.environment_merge_commit, receipt_path)
    receipt_sha256 = sha256_bytes(receipt)
    if receipt_sha256 != pins.installation_receipt_sha256:
        raise RuntimeError(
            "Environment R3 receipt mismatch: "
            f"expected={pins.installation_receipt_sha256} actual={receipt_sha256}"
        )
    fingerprint_path = f"{pins.environment_root}/runtime_fingerprint.json"
    fingerprint_payload = blob_bytes(
        repo, pins.environment_merge_commit, fingerprint_path
    )
    fingerprint = json.loads(fingerprint_payload)
    actual_fingerprint = fingerprint.get("environment_fingerprint_sha256")
    if actual_fingerprint != pins.runtime_fingerprint_v3:
        raise RuntimeError(
            "Environment R3 fingerprint mismatch: "
            f"expected={pins.runtime_fingerprint_v3} actual={actual_fingerprint}"
        )
    return {
        "merge_commit": pins.environment_merge_commit,
        "fixed_head": pins.environment_fixed_head,
        "fixed_tree": pins.environment_fixed_tree,
        "root": pins.environment_root,
        "installation_receipt_sha256": receipt_sha256,
        "runtime_fingerprint_v3": actual_fingerprint,
        "reference_only": True,
        "modified_by_this_contract": False,
    }


def contract_document(
    pins: Pins,
    source: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": {"name": SCHEMA_NAME, "version": SCHEMA_VERSION},
        "contract_task_id": TASK_ID,
        "target_repository": TARGET_REPOSITORY,
        "current_main_minimum_merge": {
            "commit": pins.minimum_origin_main,
            "tree": pins.minimum_origin_main_tree,
        },
        "authority_roles": {
            "algorithm_source_authority": (
                "historical P1 implementation under evaluation"
            ),
            "diagnostic_control_authority": (
                "later pinned orthogonal generator adopted only as a mechanical "
                "equal-ticket comparator"
            ),
            "environment_authority": (
                "merged sealed Environment R3 package referenced without modification"
            ),
            "result_artifact": (
                "future P1 reproduction output; no result artifact is created here"
            ),
        },
        "environment_authority": environment,
        "historical_algorithm_source_authorities": {
            "four_bet": {
                "commit": pins.historical_commit,
                "path": pins.historical_path,
                "blob": pins.historical_blob,
                "function": pins.historical_function,
                "ticket_slice": {"start": 0, "stop": 4},
            },
            "five_bet": {
                "commit": pins.historical_commit,
                "path": pins.historical_path,
                "blob": pins.historical_blob,
                "function": pins.historical_function,
                "ticket_slice": {"start": 0, "stop": 5},
            },
        },
        "historical_orthogonal_absence": {
            "commit": pins.historical_commit,
            "path": pins.historical_path,
            "blob": pins.historical_blob,
            "symbol": pins.adopted_symbol,
            "status": source["historical_symbol_status"],
        },
        "diagnostic_control_authority": {
            "control_role": "DIAGNOSTIC_EQUAL_TICKET_COMPARATOR",
            "source_role": "DIAGNOSTIC_CONTROL_AUTHORITY",
            "commit": pins.adopted_commit,
            "path": pins.adopted_path,
            "blob": pins.adopted_blob,
            "symbol": pins.adopted_symbol,
            "helper_commit": pins.helper_commit,
            "helper_comparison_commit": pins.helper_comparison_commit,
            "helper_path": pins.helper_path,
            "helper_blob": pins.helper_blob,
            "direct_import_closure": source["direct_import_closure"],
            "callable_closure": source["callable_closure"],
            "lottery_type": pins.lottery_type,
            "main_number_range": source["main_number_range"],
            "ticket_count": source["ticket_count"],
            "ordered_tickets": source["ordered_tickets"],
            "input_boundary": "SUPPLIED_HISTORICAL_DRAW_PREFIX_ONLY",
            "determinism": "REQUIRED",
            "dependency_prohibitions": source["isolation"],
            "four_bet_comparator_ticket_slice": {
                "start": 0,
                "stop": 4,
                "meaning": "FIRST_FOUR_ORDERED_ORTHOGONAL_TICKETS",
            },
            "five_bet_comparator_ticket_slice": {
                "start": 0,
                "stop": 5,
                "meaning": "ALL_FIVE_ORDERED_ORTHOGONAL_TICKETS",
            },
        },
        "classification": {
            "evidence_status": pins.evidence_status,
            "current_significance": pins.current_significance,
            "diagnostic_only": pins.diagnostic_only,
            "production_eligible": False,
            "ranking_eligible": False,
            "promotion_eligible": False,
            "rejection_authority": False,
            "live_db_execution_allowed": False,
            "production_wiring_allowed": False,
        },
        "exclusions": {
            "power_lotto_control": (
                "FORBIDDEN: POWER_LOTTO MAX_NUM=38 is incompatible with BIG_LOTTO 1-49"
            ),
            "p1_self_control": (
                "FORBIDDEN: the P1 strategy under evaluation cannot serve as its own control"
            ),
            "validated_alternative_claim": False,
            "statistical_advantage_claim": False,
            "strategy_promotion_signal": False,
            "strategy_rejection_signal": False,
        },
        "future_p1_reproduction_consumer_requirements": [
            "resolve every source from the exact pinned commit/path/blob identity",
            "extract only the named diagnostic callable closure without executing unrelated module-level code",
            "supply only the historical draw prefix preceding each evaluated draw",
            "use the first four ordered diagnostic tickets for four-bet evaluation",
            "use all five ordered diagnostic tickets for five-bet evaluation",
            "use the referenced sealed Environment R3 authority",
            "produce result artifacts outside this contract-authoring task",
            "retain HISTORICAL_RESEARCH_ONLY / NOT_ESTABLISHED / DIAGNOSTIC_ONLY labels",
        ],
        "task_effects": {
            "db_opened": False,
            "backtest_run": False,
            "reproduction_run": False,
            "strategy_executed": False,
            "production_changed": False,
            "rejection_state_changed": False,
            "environment_authority_changed": False,
        },
    }


def orthogonal_authority_document(
    pins: Pins,
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": {
            "name": "LotteryNewP1OrthogonalDiagnosticAuthority",
            "version": SCHEMA_VERSION,
        },
        "contract_task_id": TASK_ID,
        "authority_role": "DIAGNOSTIC_CONTROL_AUTHORITY",
        "control_role": "DIAGNOSTIC_EQUAL_TICKET_COMPARATOR",
        "source": {
            "commit": pins.adopted_commit,
            "path": pins.adopted_path,
            "blob": pins.adopted_blob,
            "symbol": pins.adopted_symbol,
        },
        "historical_absence": {
            "commit": pins.historical_commit,
            "path": pins.historical_path,
            "blob": pins.historical_blob,
            "symbol_status": source["historical_symbol_status"],
        },
        "helper": {
            "commit": pins.helper_commit,
            "comparison_commit": pins.helper_comparison_commit,
            "path": pins.helper_path,
            "blob": pins.helper_blob,
            "blob_equality": source["helper_blob_equality"],
        },
        "source_closure": {
            "direct_imports": source["direct_import_closure"],
            "named_callable_closure": source["callable_closure"],
            "module_level_nonclosure_findings": source[
                "module_level_nonclosure_findings"
            ],
            "module_import_execution_approved": False,
            "strategy_or_backtest_execution_performed": False,
        },
        "semantic_verification": {
            "lottery_type": pins.lottery_type,
            "main_number_range": source["main_number_range"],
            "ticket_count": source["ticket_count"],
            "ordered_tickets": source["ordered_tickets"],
            "prefix_only_input": True,
            "deterministic": True,
            "db_dependency": source["isolation"]["db_dependency"],
            "network_dependency": source["isolation"]["network_dependency"],
            "random_dependency": source["isolation"]["random_dependency"],
            "four_bet_slice": [0, 4],
            "five_bet_slice": [0, 5],
        },
        "classification": {
            "evidence_status": pins.evidence_status,
            "current_significance": pins.current_significance,
            "diagnostic_only": pins.diagnostic_only,
            "production_eligible": False,
            "ranking_eligible": False,
            "promotion_eligible": False,
            "rejection_authority": False,
            "live_db_execution_allowed": False,
            "production_wiring_allowed": False,
        },
        "prohibited_interpretations": [
            "validated alternative",
            "statistically superior strategy",
            "production candidate",
            "ranking or promotion signal",
            "rejection authority",
            "POWER_LOTTO 1-38 substitute",
            "P1 self-control",
        ],
    }


def report_bytes(pins: Pins) -> bytes:
    report = f"""# P1 Reproduction Contract Authority R3

This package repairs only the authority contract for a future P1 reproduction.
It does not run a reproduction, a backtest, a strategy, or a database query.

## Authority split

- **Algorithm source authority:** `{pins.historical_commit}:{pins.historical_path}`
  at blob `{pins.historical_blob}` remains the historical P1 implementation under
  evaluation for both four-bet and five-bet use.
- **Diagnostic control authority:** `{pins.adopted_commit}:{pins.adopted_path}`
  at blob `{pins.adopted_blob}` supplies `{pins.adopted_symbol}` only as a
  mechanical equal-ticket comparator.
- **Environment authority:** merged Environment R3 at
  `{pins.environment_merge_commit}:{pins.environment_root}` is referenced without
  modification.
- **Result artifact:** future reproduction output is outside this task and is not
  present in this package.

## Closed interpretation

The historical source blob does not contain `{pins.adopted_symbol}`. The later
symbol is therefore an explicit diagnostic-control exception and never enters
the historical P1 algorithm-source closure. Four-bet comparison uses the first
four ordered diagnostic tickets; five-bet comparison uses all five.

The diagnostic callable closure is BIG_LOTTO 1–49, deterministic, and accepts
only a supplied historical draw prefix. Static AST verification finds no DB,
network, random, or filesystem dependency in the named callable closure. The
helper module contains unrelated module-level DB and backtest code; that code is
excluded, unapproved, and must not be executed by a future consumer.

## Research and production boundary

The comparator is `HISTORICAL_RESEARCH_ONLY / NOT_ESTABLISHED /
DIAGNOSTIC_ONLY`. It is not a validated alternative, production candidate,
ranking signal, promotion signal, or rejection authority. POWER_LOTTO
`MAX_NUM=38` substitution and using P1 as its own control are forbidden.
"""
    return report.encode("utf-8")


def build_documents(
    repo: Path,
    pins: Pins = PINS,
) -> dict[str, bytes]:
    repo = repo.resolve()
    repository_slug(repo)
    validate_policy_pins(pins)
    validate_control_policy(
        lottery_type=pins.lottery_type,
        maximum_number=pins.main_number_max,
        source_role="DIAGNOSTIC_CONTROL_AUTHORITY",
    )
    if tree_oid(repo, pins.minimum_origin_main) != pins.minimum_origin_main_tree:
        raise RuntimeError("minimum origin/main commit tree mismatch")
    source = source_evidence(repo, pins)
    environment = environment_evidence(repo, pins)
    return {
        "contract.json": canonical_bytes(
            contract_document(pins, source, environment)
        ),
        "orthogonal_authority.json": canonical_bytes(
            orthogonal_authority_document(pins, source)
        ),
        "REPORT.md": report_bytes(pins),
    }


def write_or_check(path: Path, payload: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"required deterministic output is absent: {path}")
        if path.read_bytes() != payload:
            raise RuntimeError(f"deterministic output mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_content_outputs(
    repo: Path,
    output_dir: Path,
    *,
    check: bool,
    pins: Pins = PINS,
) -> None:
    documents = build_documents(repo, pins)
    for name, payload in documents.items():
        write_or_check(output_dir / name, payload, check=check)


def manifest_document(repo: Path) -> dict[str, Any]:
    records = []
    for path in CONTENT_PATHS:
        absolute = repo / path
        if not absolute.is_file() or absolute.is_symlink():
            raise RuntimeError(f"unsealed content path: {path}")
        records.append(
            {
                "path": path,
                "sha256": sha256_path(absolute),
                "size": absolute.stat().st_size,
            }
        )
    return {
        "schema": {
            "name": "LotteryNewP1ReproductionContractManifest",
            "version": SCHEMA_VERSION,
        },
        "contract_task_id": TASK_ID,
        "package_paths": list(PACKAGE_PATHS),
        "content_records": records,
        "sha256sums_coverage": [
            path
            for path in PACKAGE_PATHS
            if path != f"{PACKAGE_ROOT}/SHA256SUMS"
        ],
        "sha256sums_self_exclusion": (
            "SHA256SUMS cannot contain its own digest; final Git tree identity seals it"
        ),
    }


def seal_payloads(repo: Path) -> tuple[bytes, bytes]:
    manifest = canonical_bytes(manifest_document(repo))
    manifest_path = f"{PACKAGE_ROOT}/MANIFEST.json"
    rows: list[tuple[str, str]] = []
    for path in PACKAGE_PATHS:
        if path == f"{PACKAGE_ROOT}/SHA256SUMS":
            continue
        if path == manifest_path:
            digest = sha256_bytes(manifest)
        else:
            absolute = repo / path
            if not absolute.is_file() or absolute.is_symlink():
                raise RuntimeError(f"SHA256SUMS input is absent or unsafe: {path}")
            digest = sha256_path(absolute)
        rows.append((path, digest))
    sums = "".join(f"{digest}  {path}\n" for path, digest in rows).encode("utf-8")
    return manifest, sums


def write_seal(repo: Path, *, check: bool) -> None:
    manifest, sums = seal_payloads(repo)
    write_or_check(repo / PACKAGE_ROOT / "MANIFEST.json", manifest, check=check)
    write_or_check(repo / PACKAGE_ROOT / "SHA256SUMS", sums, check=check)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--check-seal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else repo / PACKAGE_ROOT
    )
    write_content_outputs(repo, output_dir, check=args.check)
    if args.seal and args.check_seal:
        raise RuntimeError("--seal and --check-seal are mutually exclusive")
    if args.seal:
        if output_dir != repo / PACKAGE_ROOT:
            raise RuntimeError("seal generation requires the canonical package output path")
        write_seal(repo, check=False)
    elif args.check_seal:
        if output_dir != repo / PACKAGE_ROOT:
            raise RuntimeError("seal verification requires the canonical package output path")
        write_seal(repo, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
