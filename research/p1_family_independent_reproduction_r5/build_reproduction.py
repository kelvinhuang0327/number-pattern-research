#!/usr/bin/env python3
"""Deterministic, historical-only Big Lotto P1 family reproduction R5."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import random
import re
import sqlite3
import stat
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
from numpy.fft import fft, fftfreq
from scipy.stats import binomtest


TASK_NAME = "LOTTERYNEW_P1_FAMILY_INDEPENDENT_REPRODUCTION_R5"
PACKAGE_ROOT = "research/p1_family_independent_reproduction_r5"
PACKAGE_PATHS = (
    f"{PACKAGE_ROOT}/build_reproduction.py",
    f"{PACKAGE_ROOT}/result.schema.json",
    f"{PACKAGE_ROOT}/result.json",
    f"{PACKAGE_ROOT}/run_comparison.json",
    f"{PACKAGE_ROOT}/REPORT.md",
    f"{PACKAGE_ROOT}/MANIFEST.json",
    f"{PACKAGE_ROOT}/SHA256SUMS",
    "tests/test_p1_family_independent_reproduction_r5.py",
)
CONTENT_PATHS = (
    PACKAGE_PATHS[0],
    PACKAGE_PATHS[1],
    PACKAGE_PATHS[2],
    PACKAGE_PATHS[3],
    PACKAGE_PATHS[4],
    PACKAGE_PATHS[7],
)
SCHEMA_VERSION = "LotteryNewP1FamilyIndependentReproductionResultV1"
COMPARISON_SCHEMA_VERSION = "LotteryNewP1FamilyIndependentRunComparisonV1"
DISCLAIMER = (
    "HISTORICAL_RESEARCH_ONLY; NOT_ESTABLISHED; DIAGNOSTIC_ONLY; "
    "not betting advice; no production, ranking, promotion, or rejection authority."
)
SNAPSHOT_PATH = Path(
    "/Users/kelvin/Kelvin-WorkSpace/.artifacts/LotteryNew/"
    "p1-family-independent-reproduction-r2/snapshot/lottery_v2.db"
)
SNAPSHOT_SHA256 = "5d712edb64fc490bf4e081a4256a29be89351902fbfadad3f27873f14201488e"
SNAPSHOT_SIZE = 63_594_496
SNAPSHOT_VIEW = "draws_big_lotto_canonical_main"
DRAW_COUNT = 2_127
DRAW_MIN = 96_000_001
DRAW_MAX = 115_000_072
MAIN_COMMIT = "24617fe3bb7ec087acf121f302bffd638ccfa179"
MAIN_TREE = "b9f3f38ca5a5f62ccea533d8a8ba814149554a17"
ALGORITHM_COMMIT = "28940a2572c051c6ba8b2ab6a077f706e800477d"
ALGORITHM_PATH = "tools/quick_predict.py"
ALGORITHM_BLOB = "bb2826b84a782aa6f68d472b30221fa2d1781a4b"
ALGORITHM_CALLABLE = "biglotto_p1_deviation_5bet"
ALGORITHM_CLOSURE = (
    "biglotto_p1_deviation_5bet",
    "_bl_fourier_scores",
    "_bl_markov_scores",
    "_bl_cold_sum_fixed",
    "_bl_dev_complement_2bet",
    "_bl_bet5_sum_conditional",
)
CONTROL_COMMIT = "e56ce9f196342e9d50edc9fd19c42f72c1fa2047"
CONTROL_PATH = "tools/quick_predict.py"
CONTROL_BLOB = "7ee44fa584442419410d675b3ec3598c161ad2ec"
CONTROL_SYMBOL = "biglotto_5bet_orthogonal"
CONTROL_HELPER_PATH = "tools/backtest_biglotto_markov_4bet.py"
CONTROL_HELPER_BLOB = "cd5b6f780cdf0d2363a631dc5faba0a013a52566"
CONTROL_CLOSURE = (
    "biglotto_5bet_orthogonal",
    "fourier_rhythm_bet",
    "cold_numbers_bet",
    "_sum_target",
    "tail_balance_bet",
    "markov_orthogonal_bet",
)
BASELINE_PATH = "lottery_api/utils/baseline_calculator.py"
BASELINE_BLOB = "be203a05e01cb211c7101137ab2ff7968e5d5bd1"
P_VALUE_PATH = "lottery_api/utils/permutation_test.py"
P_VALUE_BLOB = "ebf5b7eb13edb79f456320f4626c88cce9a330f7"
ENVIRONMENT_MERGE = "e6037b06c3030bc1efc6538fc1a936bd763958b6"
ENVIRONMENT_ROOT = "research/p1_reproduction_environment_authority_r3"
EXPECTED_RUNTIME_ROOT = Path(
    "/Users/kelvin/Kelvin-WorkSpace/.runtime/LotteryNew/"
    "p1-family-independent-reproduction-r5"
)
APPROVED_INTERPRETER_BASENAMES = frozenset({"python", "python3", "python3.12"})
MAX_INTERPRETER_SYMLINK_HOPS = 32
PYTHON_IMPLEMENTATION = "CPython"
PYTHON_VERSION = "3.12.12"
INSTALLATION_RECEIPT_SHA256 = (
    "4f3d94933a42d98d48448ed188855f3d296795bbb73b9e84dd6c55229cce87aa"
)
RUNTIME_FINGERPRINT_V3 = (
    "372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e"
)
RUNTIME_FINGERPRINT_DOCUMENT_SHA256 = (
    "cb879f93616a30d21d5a1d1e3f179eb3a8381d40485a3a4620c98be3b173b757"
)
ENVIRONMENT_AUTHORITY_DOCUMENT_SHA256 = (
    "7eb8717d10b4a4cb71cefb0f4a5899e49d298ba53cece931973754df1e9cf73a"
)
CONTRACT_ROOT = "research/p1_reproduction_contract_r3"
MASTER_SEED = 20_260_724
MONTE_CARLO_B = 9_999
MONTE_CARLO_WINDOW = 1_500
EPSILON = 1e-12
PER_STRATEGY_ALPHA = 0.025
CUTOFF_DRAW = 115_000_027
CUTOFF_DATE = "2026-02-26"
OOS_MATURITY = 150
STRATEGIES = (
    ("BIG_LOTTO_P1_DEVIATION_4BET", 4),
    ("BIG_LOTTO_P1_DEVIATION_5BET", 5),
)
SUBSEED_PREFIX = b"LOTTERYNEW_BIG_LOTTO_P1_MC_SUBSEED_V1"
OUTCOME_PRECEDENCE = "INVALID_REPRODUCTION>FAIL>INSUFFICIENT_EVIDENCE>PASS"
REASON_CODES = frozenset(
    {
        "SOURCE_IDENTITY_MISMATCH",
        "SOURCE_CLOSURE_INVALID",
        "SNAPSHOT_IDENTITY_MISMATCH",
        "RUNTIME_FINGERPRINT_MISMATCH",
        "TICKET_COUNT_INVALID",
        "TICKET_INVALID",
        "PREFIX_ISOLATION_FAILED",
        "MONTE_CARLO_COUNT_INVALID",
        "MANDATORY_VALUE_MISSING",
        "MANDATORY_VALUE_NONFINITE",
        "RESULT_SCHEMA_INVALID",
        "RUN_OUTPUT_MISMATCH",
    }
)


class ReproductionInvalid(RuntimeError):
    """A closed reason-code failure in a reproduction invariant."""

    def __init__(self, reason: str, detail: str) -> None:
        if reason not in REASON_CODES:
            raise ValueError(f"unknown reason code: {reason}")
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Draw:
    draw: int
    date: str
    numbers: tuple[int, ...]
    special: int

    def history_row(self) -> dict[str, Any]:
        return {"draw": self.draw, "date": self.date, "numbers": list(self.numbers)}


def normalize_canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_canonical(child) for key, child in value.items()}
    if isinstance(value, list):
        return [normalize_canonical(child) for child in value]
    if isinstance(value, tuple):
        return [normalize_canonical(child) for child in value]
    if isinstance(value, float) and value == 0.0:
        return 0.0
    return value


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            normalize_canonical(value),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def schema_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            normalize_canonical(value),
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


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReproductionInvalid(
            "SOURCE_IDENTITY_MISMATCH", f"git {' '.join(args)}: {message}"
        )
    return completed.stdout


def require_blob(repo: Path, commit: str, path: str, expected: str) -> bytes:
    row = _git(repo, "ls-tree", commit, "--", path).decode().strip().split(maxsplit=3)
    if len(row) != 4 or row[1] != "blob" or row[2] != expected or row[3] != path:
        raise ReproductionInvalid(
            "SOURCE_IDENTITY_MISMATCH",
            f"{commit}:{path} expected blob {expected}, got {row!r}",
        )
    payload = _git(repo, "show", f"{commit}:{path}")
    actual = _git(repo, "hash-object", "--stdin", input_bytes=payload).decode().strip()
    if actual != expected:
        raise ReproductionInvalid(
            "SOURCE_IDENTITY_MISMATCH",
            f"{commit}:{path} content blob {actual}, expected {expected}",
        )
    return payload


def _functions(payload: bytes, identity: str) -> dict[str, ast.FunctionDef]:
    try:
        module = ast.parse(payload.decode("utf-8"), filename=identity)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", identity) from exc
    result: dict[str, ast.FunctionDef] = {}
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            result[node.name] = node
    return result


def _compile_functions(
    functions: Sequence[ast.FunctionDef], namespace: dict[str, Any], identity: str
) -> dict[str, Any]:
    module = ast.Module(body=list(functions), type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, identity, "exec"), namespace)
    return namespace


def source_closures(repo: Path) -> tuple[Callable[..., Any], Callable[..., Any]]:
    historical = require_blob(repo, ALGORITHM_COMMIT, ALGORITHM_PATH, ALGORITHM_BLOB)
    historical_functions = _functions(
        historical, f"{ALGORITHM_COMMIT}:{ALGORITHM_PATH}"
    )
    if (
        ALGORITHM_CALLABLE not in ALGORITHM_CLOSURE
        or tuple(name for name in ALGORITHM_CLOSURE if name not in historical_functions)
    ):
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "historical closure missing")
    algorithm_namespace = {
        "np": np,
        "fft": fft,
        "fftfreq": fftfreq,
        "Counter": Counter,
        "combinations": combinations,
    }
    _compile_functions(
        [historical_functions[name] for name in reversed(ALGORITHM_CLOSURE)],
        algorithm_namespace,
        "historical_p1_closure",
    )

    control_payload = require_blob(repo, CONTROL_COMMIT, CONTROL_PATH, CONTROL_BLOB)
    helper_payload = require_blob(
        repo, CONTROL_COMMIT, CONTROL_HELPER_PATH, CONTROL_HELPER_BLOB
    )
    control_functions = _functions(control_payload, f"{CONTROL_COMMIT}:{CONTROL_PATH}")
    helper_functions = _functions(
        helper_payload, f"{CONTROL_COMMIT}:{CONTROL_HELPER_PATH}"
    )
    if CONTROL_SYMBOL not in control_functions or any(
        name not in {*control_functions, *helper_functions}
        for name in CONTROL_CLOSURE
    ):
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "control closure missing")
    control_function = ast.fix_missing_locations(
        ast.FunctionDef(
            name=control_functions[CONTROL_SYMBOL].name,
            args=control_functions[CONTROL_SYMBOL].args,
            body=[
                node
                for node in control_functions[CONTROL_SYMBOL].body
                if not isinstance(node, ast.ImportFrom)
            ],
            decorator_list=[],
            returns=control_functions[CONTROL_SYMBOL].returns,
            type_comment=control_functions[CONTROL_SYMBOL].type_comment,
        )
    )
    control_namespace = {
        "np": np,
        "fft": fft,
        "fftfreq": fftfreq,
        "Counter": Counter,
        "_icombs": combinations,
        "MAX_NUM": 49,
        "PICK": 6,
        "_SUM_WIN": 300,
    }
    ordered_helpers = (
        "_sum_target",
        "fourier_rhythm_bet",
        "cold_numbers_bet",
        "tail_balance_bet",
        "markov_orthogonal_bet",
    )
    _compile_functions(
        [helper_functions[name] for name in ordered_helpers] + [control_function],
        control_namespace,
        "diagnostic_control_closure",
    )
    validate_control_policy(
        lottery_type="BIG_LOTTO",
        maximum_number=49,
        four_slice=(0, 4),
        five_slice=(0, 5),
        control_symbol=CONTROL_SYMBOL,
    )
    return (
        algorithm_namespace[ALGORITHM_CALLABLE],
        control_namespace[CONTROL_SYMBOL],
    )


def _lexical_absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError(f"path is not absolute: {path}")
    return Path(os.path.normpath(os.fspath(path)))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _runtime_identity_failure(
    message: str,
    *,
    lexical_interpreter: Path,
    resolved_terminal: Path | None,
    symlink_hops: Sequence[Mapping[str, str]],
) -> None:
    diagnostics = {
        "lexical_interpreter_path": lexical_interpreter.as_posix(),
        "resolved_terminal_path": (
            resolved_terminal.as_posix() if resolved_terminal is not None else None
        ),
        "symlink_hops": list(symlink_hops),
    }
    raise ReproductionInvalid(
        "RUNTIME_FINGERPRINT_MISMATCH",
        f"{message}; diagnostics={json.dumps(diagnostics, sort_keys=True)}",
    )


def _resolve_interpreter_topology(
    runtime_root: Path, lexical_interpreter: Path
) -> tuple[Path, list[dict[str, str]]]:
    symlink_hops: list[dict[str, str]] = []
    try:
        runtime_root = _lexical_absolute(runtime_root)
        lexical_interpreter = _lexical_absolute(lexical_interpreter)
    except ValueError as exc:
        _runtime_identity_failure(
            str(exc),
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=None,
            symlink_hops=symlink_hops,
        )
        raise AssertionError("unreachable") from exc

    venv_bin = runtime_root / "venv" / "bin"
    if (
        lexical_interpreter.parent != venv_bin
        or lexical_interpreter.name not in APPROVED_INTERPRETER_BASENAMES
    ):
        _runtime_identity_failure(
            "reported interpreter is not an approved lexical venv/bin entry",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=lexical_interpreter,
            symlink_hops=symlink_hops,
        )

    try:
        root_mode = runtime_root.lstat().st_mode
    except OSError as exc:
        _runtime_identity_failure(
            f"runtime root unavailable: {exc}",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=runtime_root,
            symlink_hops=symlink_hops,
        )
        raise AssertionError("unreachable") from exc
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        _runtime_identity_failure(
            "runtime root is not a regular directory",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=runtime_root,
            symlink_hops=symlink_hops,
        )

    remaining = list(lexical_interpreter.relative_to(runtime_root).parts)
    current = runtime_root
    seen_symlinks: set[Path] = set()
    inspected_components = 0
    while remaining:
        inspected_components += 1
        if inspected_components > 256:
            _runtime_identity_failure(
                "interpreter resolution exceeded the component bound",
                lexical_interpreter=lexical_interpreter,
                resolved_terminal=current,
                symlink_hops=symlink_hops,
            )
        candidate = current / remaining.pop(0)
        if not _is_within(candidate, runtime_root):
            _runtime_identity_failure(
                "interpreter component escaped the runtime root",
                lexical_interpreter=lexical_interpreter,
                resolved_terminal=candidate,
                symlink_hops=symlink_hops,
            )
        try:
            mode = candidate.lstat().st_mode
        except OSError as exc:
            _runtime_identity_failure(
                f"broken interpreter topology: {exc}",
                lexical_interpreter=lexical_interpreter,
                resolved_terminal=candidate,
                symlink_hops=symlink_hops,
            )
            raise AssertionError("unreachable") from exc
        if stat.S_ISLNK(mode):
            if (
                candidate in seen_symlinks
                or len(symlink_hops) >= MAX_INTERPRETER_SYMLINK_HOPS
            ):
                _runtime_identity_failure(
                    "interpreter symlink loop or hop bound exceeded",
                    lexical_interpreter=lexical_interpreter,
                    resolved_terminal=candidate,
                    symlink_hops=symlink_hops,
                )
            seen_symlinks.add(candidate)
            try:
                target_text = os.readlink(candidate)
            except OSError as exc:
                _runtime_identity_failure(
                    f"interpreter symlink unreadable: {exc}",
                    lexical_interpreter=lexical_interpreter,
                    resolved_terminal=candidate,
                    symlink_hops=symlink_hops,
                )
                raise AssertionError("unreachable") from exc
            target = Path(target_text)
            if not target.is_absolute():
                target = candidate.parent / target
            target = Path(os.path.normpath(os.fspath(target)))
            symlink_hops.append(
                {
                    "path": candidate.as_posix(),
                    "target": target_text,
                    "next_path": target.as_posix(),
                }
            )
            if not _is_within(target, runtime_root):
                _runtime_identity_failure(
                    "interpreter symlink escaped the runtime root",
                    lexical_interpreter=lexical_interpreter,
                    resolved_terminal=target,
                    symlink_hops=symlink_hops,
                )
            remaining = list(target.relative_to(runtime_root).parts) + remaining
            current = runtime_root
            continue
        if remaining and not stat.S_ISDIR(mode):
            _runtime_identity_failure(
                "interpreter topology contains a non-directory component",
                lexical_interpreter=lexical_interpreter,
                resolved_terminal=candidate,
                symlink_hops=symlink_hops,
            )
        current = candidate

    terminal = current
    try:
        terminal_mode = terminal.lstat().st_mode
    except OSError as exc:
        _runtime_identity_failure(
            f"interpreter terminal unavailable: {exc}",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=terminal,
            symlink_hops=symlink_hops,
        )
        raise AssertionError("unreachable") from exc
    allowed_terminal = (
        _is_within(terminal, venv_bin) and terminal != venv_bin
    ) or (
        _is_within(terminal, runtime_root / "python")
        and terminal != runtime_root / "python"
    )
    if (
        not allowed_terminal
        or not stat.S_ISREG(terminal_mode)
        or not os.access(terminal, os.X_OK)
    ):
        _runtime_identity_failure(
            "interpreter terminal is not an approved regular executable",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=terminal,
            symlink_hops=symlink_hops,
        )
    return terminal, symlink_hops


def _require_environment_r3_identity(repo: Path) -> dict[str, str]:
    authority_root = repo / ENVIRONMENT_ROOT
    receipt_path = authority_root / "installation_receipt.json"
    fingerprint_path = authority_root / "runtime_fingerprint.json"
    authority_path = authority_root / "environment_authority.json"
    expected_file_hashes = {
        receipt_path: INSTALLATION_RECEIPT_SHA256,
        fingerprint_path: RUNTIME_FINGERPRINT_DOCUMENT_SHA256,
        authority_path: ENVIRONMENT_AUTHORITY_DOCUMENT_SHA256,
    }
    for path, expected in expected_file_hashes.items():
        if path.is_symlink() or not path.is_file() or sha256_path(path) != expected:
            raise ReproductionInvalid(
                "RUNTIME_FINGERPRINT_MISMATCH",
                f"Environment R3 evidence mismatch: {path}",
            )
    try:
        fingerprint = json.loads(fingerprint_path.read_text(encoding="utf-8"))
        authority = json.loads(authority_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReproductionInvalid(
            "RUNTIME_FINGERPRINT_MISMATCH",
            f"Environment R3 evidence unreadable: {exc}",
        ) from exc
    expected_fields = {
        "installation_receipt_sha256": INSTALLATION_RECEIPT_SHA256,
        "environment_fingerprint_sha256": RUNTIME_FINGERPRINT_V3,
    }
    if any(
        fingerprint.get(key) != value or authority.get(key) != value
        for key, value in expected_fields.items()
    ):
        raise ReproductionInvalid(
            "RUNTIME_FINGERPRINT_MISMATCH",
            "Environment R3 receipt or fingerprint field mismatch",
        )
    python_identity = fingerprint.get("python_identity", {})
    if (
        python_identity.get("implementation") != PYTHON_IMPLEMENTATION
        or python_identity.get("version") != PYTHON_VERSION
        or python_identity.get("uv_identity")
        != "cpython-3.12.12-macos-aarch64-none"
    ):
        raise ReproductionInvalid(
            "RUNTIME_FINGERPRINT_MISMATCH",
            "Environment R3 Python identity mismatch",
        )
    return expected_fields


def require_runtime_identity(repo: Path, runtime_root: Path) -> dict[str, Any]:
    lexical_runtime_root = _lexical_absolute(runtime_root)
    expected_runtime_root = _lexical_absolute(EXPECTED_RUNTIME_ROOT)
    lexical_interpreter = Path(sys.executable)
    if lexical_runtime_root != expected_runtime_root:
        _runtime_identity_failure(
            "wrong task runtime root",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=None,
            symlink_hops=[],
        )
    terminal, symlink_hops = _resolve_interpreter_topology(
        lexical_runtime_root, lexical_interpreter
    )
    expected_prefix = lexical_runtime_root / "venv"
    try:
        reported_prefix = _lexical_absolute(Path(sys.prefix))
    except ValueError as exc:
        _runtime_identity_failure(
            f"invalid sys.prefix: {exc}",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=terminal,
            symlink_hops=symlink_hops,
        )
        raise AssertionError("unreachable") from exc
    if reported_prefix != expected_prefix:
        _runtime_identity_failure(
            "sys.prefix does not identify the exact R5 venv",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=terminal,
            symlink_hops=symlink_hops,
        )
    implementation = platform.python_implementation()
    version = platform.python_version()
    if implementation != PYTHON_IMPLEMENTATION or version != PYTHON_VERSION:
        _runtime_identity_failure(
            "Python implementation or version mismatch",
            lexical_interpreter=lexical_interpreter,
            resolved_terminal=terminal,
            symlink_hops=symlink_hops,
        )
    environment_identity = _require_environment_r3_identity(repo)
    return {
        "lexical_interpreter_path": lexical_interpreter.as_posix(),
        "symlink_hops": symlink_hops,
        "resolved_terminal_path": terminal.as_posix(),
        "python_implementation": implementation,
        "python_version": version,
        "sys_prefix": reported_prefix.as_posix(),
        **environment_identity,
    }


def load_draws(snapshot: Path = SNAPSHOT_PATH) -> list[Draw]:
    if snapshot.is_symlink() or not snapshot.is_file():
        raise ReproductionInvalid("SNAPSHOT_IDENTITY_MISMATCH", "not a regular file")
    if snapshot.stat().st_size != SNAPSHOT_SIZE or sha256_path(snapshot) != SNAPSHOT_SHA256:
        raise ReproductionInvalid("SNAPSHOT_IDENTITY_MISMATCH", "size or digest drift")
    for suffix in ("-wal", "-shm"):
        if Path(f"{snapshot}{suffix}").exists():
            raise ReproductionInvalid(
                "SNAPSHOT_IDENTITY_MISMATCH", f"forbidden sidecar {suffix}"
            )
    uri = f"file:{snapshot}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only=1")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise ReproductionInvalid(
                "SNAPSHOT_IDENTITY_MISMATCH", "query_only not active"
            )
        rows = connection.execute(
            "SELECT CAST(draw AS INTEGER), date, numbers, special "
            f"FROM {SNAPSHOT_VIEW} ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        connection.close()
    draws = [
        Draw(int(draw), str(date), tuple(json.loads(numbers)), int(special))
        for draw, date, numbers, special in rows
    ]
    if (
        len(draws) != DRAW_COUNT
        or draws[0].draw != DRAW_MIN
        or draws[-1].draw != DRAW_MAX
        or any(a.draw >= b.draw for a, b in zip(draws, draws[1:]))
    ):
        raise ReproductionInvalid(
            "SNAPSHOT_IDENTITY_MISMATCH", "canonical draw order or bounds drift"
        )
    return draws


def validate_tickets(raw: Any, count: int) -> list[list[int]]:
    if not isinstance(raw, list) or len(raw) < count:
        raise ReproductionInvalid("TICKET_COUNT_INVALID", f"expected slice {count}")
    tickets: list[list[int]] = []
    for item in raw[:count]:
        numbers = item.get("numbers") if isinstance(item, dict) else None
        if (
            not isinstance(numbers, list)
            or len(numbers) != 6
            or numbers != sorted(numbers)
            or len(set(numbers)) != 6
            or any(not isinstance(n, int) or n < 1 or n > 49 for n in numbers)
        ):
            raise ReproductionInvalid("TICKET_INVALID", repr(item))
        tickets.append(numbers)
    if len(tickets) != count:
        raise ReproductionInvalid("TICKET_COUNT_INVALID", str(len(tickets)))
    return tickets


def validate_control_policy(
    *,
    lottery_type: str,
    maximum_number: int,
    four_slice: tuple[int, int],
    five_slice: tuple[int, int],
    control_symbol: str,
) -> None:
    if lottery_type != "BIG_LOTTO" or maximum_number != 49:
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "CONTROL_LOTTERY_INVALID")
    if four_slice != (0, 4) or five_slice != (0, 5):
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "CONTROL_SLICE_INVALID")
    if control_symbol == ALGORITHM_CALLABLE:
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "CONTROL_SELF_REFERENCE")


def require_prefix(
    history: Sequence[Mapping[str, Any]], target: Draw, index: int
) -> None:
    if len(history) != index:
        raise ReproductionInvalid("PREFIX_ISOLATION_FAILED", "prefix length")
    if any(int(row["draw"]) >= target.draw for row in history):
        raise ReproductionInvalid("PREFIX_ISOLATION_FAILED", "future draw in history")


def hit(tickets: Sequence[Sequence[int]], main_numbers: Sequence[int]) -> bool:
    main = set(main_numbers)
    return any(len(main.intersection(ticket)) >= 4 for ticket in tickets)


def equal_ticket_probability(ticket_count: int) -> float:
    total = math.comb(49, 6)
    single = sum(
        math.comb(6, matches) * math.comb(43, 6 - matches) / total
        for matches in range(4, 7)
    )
    return 1.0 - (1.0 - single) ** ticket_count


def require_finite(value: Any, field: str) -> float:
    if value is None:
        raise ReproductionInvalid("MANDATORY_VALUE_MISSING", field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReproductionInvalid("MANDATORY_VALUE_NONFINITE", field)
    result = float(value)
    if not math.isfinite(result):
        raise ReproductionInvalid("MANDATORY_VALUE_NONFINITE", field)
    return result


def subseed_preimage(
    strategy: str, ticket_count: int, *, separator: bytes = b"\x00"
) -> bytes:
    if separator != b"\x00":
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "SUBSEED_VECTOR_INVALID")
    return (
        SUBSEED_PREFIX
        + separator
        + str(MASTER_SEED).encode("ascii")
        + separator
        + strategy.encode("utf-8")
        + separator
        + str(ticket_count).encode("ascii")
    )


def subseed(strategy: str, ticket_count: int) -> tuple[str, int]:
    preimage = subseed_preimage(strategy, ticket_count)
    digest = hashlib.sha256(preimage).digest()
    vectors = {
        ("BIG_LOTTO_P1_DEVIATION_4BET", 4): (
            "b13bf2d7fc3ce6299fffa57a4c42d110e9724c87d9070857b4995fe4773691f3"
        ),
        ("BIG_LOTTO_P1_DEVIATION_5BET", 5): (
            "06063d4ee2e642c42f9c792971553d50ed04954e832452a72d129941db4b147a"
        ),
    }
    expected = vectors.get((strategy, ticket_count))
    if expected is not None and digest.hex() != expected:
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "SUBSEED_VECTOR_INVALID")
    return digest.hex(), int.from_bytes(digest, "big", signed=False)


def independent_rng(strategy: str, ticket_count: int) -> random.Random:
    _, seed = subseed(strategy, ticket_count)
    rng = random.Random()
    rng.seed(seed, version=2)
    return rng


def validate_rng_independence(first: random.Random, second: random.Random) -> None:
    if first is second:
        raise ReproductionInvalid("SOURCE_CLOSURE_INVALID", "RNG_INDEPENDENCE_INVALID")


def is_oos(draw: int) -> bool:
    return CUTOFF_DRAW < draw <= DRAW_MAX


def validate_oos_selection(rows: Sequence[Mapping[str, Any]]) -> None:
    if any(not is_oos(int(row["draw"])) for row in rows):
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "OOS_BOUNDARY_INVALID")


def p_value_pass(value: float) -> bool:
    return require_finite(value, "monte_carlo_p1500") < PER_STRATEGY_ALPHA


def normalize_reason_array(reasons: Sequence[str]) -> list[str]:
    normalized = sorted(set(reasons))
    if list(reasons) != normalized:
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "unsorted or duplicate reasons")
    return normalized


def validate_strategy_order(rows: Sequence[Mapping[str, Any]]) -> None:
    actual = [row.get("strategy_identity") for row in rows]
    expected = [row[0] for row in STRATEGIES]
    if actual != expected:
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "strategy order")


def window_metric(
    strategy_hits: Sequence[bool],
    control_hits: Sequence[bool],
    random_probability: float,
) -> dict[str, Any]:
    n = len(strategy_hits)
    if n == 0 or len(control_hits) != n:
        raise ValueError("window requires equally sized nonempty hit vectors")
    observed = sum(strategy_hits) / n
    orthogonal = sum(control_hits) / n
    edge = observed - random_probability
    return {
        "eligible_draws": n,
        "strategy_hits": sum(strategy_hits),
        "observed_hit_rate": observed,
        "random_probability": random_probability,
        "edge_decimal": edge,
        "edge_percentage_points": edge * 100.0,
        "orthogonal_hits": sum(control_hits),
        "orthogonal_hit_rate": orthogonal,
        "p1_minus_orthogonal_decimal": observed - orthogonal,
    }


def monte_carlo(
    strategy: str,
    ticket_count: int,
    observed_statistic: float,
    *,
    rng: random.Random,
    b: int = MONTE_CARLO_B,
) -> dict[str, Any]:
    if b != MONTE_CARLO_B:
        raise ReproductionInvalid("MONTE_CARLO_COUNT_INVALID", f"B={b}")
    digest, seed = subseed(strategy, ticket_count)
    probability = equal_ticket_probability(ticket_count)
    upper = 0
    for _ in range(b):
        simulated = (
            sum(rng.random() < probability for _ in range(MONTE_CARLO_WINDOW))
            / MONTE_CARLO_WINDOW
        )
        if simulated >= observed_statistic - EPSILON:
            upper += 1
    p_value = (1 + upper) / (b + 1)
    return {
        "B": b,
        "null_statistics_count": b,
        "subseed_sha256": digest,
        "subseed_integer": seed,
        "observed_statistic": observed_statistic,
        "upper_tail_count": upper,
        "p_value": p_value,
        "alternative": "greater",
        "epsilon": EPSILON,
    }


def production_monte_carlo_pair(
    observed_statistics: Mapping[int, float],
    *,
    rng_factory: Callable[[str, int], random.Random] = independent_rng,
    b: int = MONTE_CARLO_B,
) -> dict[int, dict[str, Any]]:
    expected_counts = tuple(ticket_count for _, ticket_count in STRATEGIES)
    if tuple(observed_statistics) != expected_counts:
        raise ReproductionInvalid(
            "RESULT_SCHEMA_INVALID", "Monte Carlo strategy order"
        )
    rngs = [
        rng_factory(strategy, ticket_count)
        for strategy, ticket_count in STRATEGIES
    ]
    validate_rng_independence(rngs[0], rngs[1])
    return {
        ticket_count: monte_carlo(
            strategy,
            ticket_count,
            observed_statistics[ticket_count],
            rng=rng,
            b=b,
        )
        for (strategy, ticket_count), rng in zip(STRATEGIES, rngs)
    }


def mcnemar(strategy_hits: Sequence[bool], control_hits: Sequence[bool]) -> dict[str, Any]:
    b = sum(a and not c for a, c in zip(strategy_hits, control_hits))
    c = sum((not a) and control for a, control in zip(strategy_hits, control_hits))
    discordant = b + c
    p_value = (
        1.0
        if discordant == 0
        else float(
            binomtest(
                min(b, c), n=discordant, p=0.5, alternative="two-sided"
            ).pvalue
        )
    )
    return {"b": b, "c": c, "discordant_count": discordant, "p_value": p_value}


def sharpe_diagnostic(
    hits: Sequence[bool], random_probability: float
) -> dict[str, Any]:
    selected = list(hits[-1500:])
    if len(selected) != 1500:
        raise ValueError("Sharpe requires 1500 eligible draws")
    edges = [
        sum(selected[end - 300 : end]) / 300 - random_probability
        for end in range(300, 1501, 150)
    ]
    sigma = statistics.pstdev(edges)
    return {
        "rolling_window": 300,
        "step": 150,
        "window_edges": edges,
        "value": None if sigma == 0 else statistics.fmean(edges) / sigma,
        "status": "UNDEFINED_ZERO_VARIANCE" if sigma == 0 else "DEFINED",
    }


def outcome_for(
    reproduction_valid: bool,
    invalid_reasons: Sequence[str],
    hard: Mapping[str, Any],
) -> tuple[str, list[str]]:
    if not reproduction_valid:
        if not invalid_reasons:
            raise ValueError("invalid reproduction requires reasons")
        return "INVALID_REPRODUCTION", []
    in_sample = (
        hard["edge500_pass"],
        hard["edge1500_pass"],
        hard["monte_carlo_p1500_pass"],
    )
    if any(value is False for value in in_sample):
        return "FAIL", []
    if not hard["oos_mature"]:
        return "INSUFFICIENT_EVIDENCE", ["OOS_ELIGIBLE_DRAWS_LT_150"]
    if hard["edge_oos_pass"] is False:
        return "FAIL", []
    return "PASS", []


def _require_equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise ReproductionInvalid(
            "RESULT_SCHEMA_INVALID", f"{field}: {actual!r} != {expected!r}"
        )


def validate_window_metric(metric: Mapping[str, Any], field: str) -> None:
    eligible = metric["eligible_draws"]
    strategy_hits = metric["strategy_hits"]
    control_hits = metric["orthogonal_hits"]
    if (
        not isinstance(eligible, int)
        or eligible <= 0
        or not 0 <= strategy_hits <= eligible
        or not 0 <= control_hits <= eligible
    ):
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", f"{field}: count bounds")
    observed = strategy_hits / eligible
    control_rate = control_hits / eligible
    probability = require_finite(metric["random_probability"], f"{field}.random")
    edge = observed - probability
    _require_equal(metric["observed_hit_rate"], observed, f"{field}.observed")
    _require_equal(metric["orthogonal_hit_rate"], control_rate, f"{field}.control")
    _require_equal(metric["edge_decimal"], edge, f"{field}.edge")
    _require_equal(
        metric["edge_percentage_points"], edge * 100.0, f"{field}.edge_pp"
    )
    _require_equal(
        metric["p1_minus_orthogonal_decimal"],
        observed - control_rate,
        f"{field}.p1_minus_control",
    )


def validate_result_semantics(result: Mapping[str, Any]) -> None:
    rows = result["strategy_results"]
    validate_strategy_order(rows)
    for position, row in enumerate(rows):
        identity, ticket_count = STRATEGIES[position]
        _require_equal(row["strategy_identity"], identity, "strategy_identity")
        diagnostic = row["diagnostic_results"]
        hard = row["hard_gate_results"]
        _require_equal(diagnostic["ticket_count"], ticket_count, "ticket_count")
        control = diagnostic["orthogonal_control"]
        _require_equal(control["ticket_count"], ticket_count, "control.ticket_count")
        _require_equal(control["slice"], [0, ticket_count], "control.slice")
        _require_equal(control["diagnostic_only"], True, "control.diagnostic_only")
        if position == 0:
            _require_equal(diagnostic["incremental_5_vs_4"], None, "4bet.incremental")
        elif diagnostic["incremental_5_vs_4"] is None:
            raise ReproductionInvalid(
                "RESULT_SCHEMA_INVALID", "5bet incremental is required"
            )

        invalid_reasons = normalize_reason_array(row["invalid_reasons"])
        insufficient = normalize_reason_array(row["insufficient_evidence_reasons"])
        reproduction_valid = row["reproduction_valid"]
        if reproduction_valid and invalid_reasons:
            raise ReproductionInvalid(
                "RESULT_SCHEMA_INVALID", "valid reproduction has invalid reasons"
            )
        if not reproduction_valid and (
            not invalid_reasons or row["outcome"] != "INVALID_REPRODUCTION"
        ):
            raise ReproductionInvalid(
                "RESULT_SCHEMA_INVALID", "invalid reproduction conditional"
            )

        for name in ("window150", "window500", "window1500", "oos"):
            validate_window_metric(diagnostic[name], f"{identity}.{name}")
        _require_equal(
            hard["edge500_decimal"],
            diagnostic["window500"]["edge_decimal"],
            "edge500",
        )
        _require_equal(
            hard["edge500_percentage_points"],
            hard["edge500_decimal"] * 100.0,
            "edge500_pp",
        )
        _require_equal(
            hard["edge500_pass"], hard["edge500_decimal"] > 0, "edge500_pass"
        )
        _require_equal(
            hard["edge1500_decimal"],
            diagnostic["window1500"]["edge_decimal"],
            "edge1500",
        )
        _require_equal(
            hard["edge1500_percentage_points"],
            hard["edge1500_decimal"] * 100.0,
            "edge1500_pp",
        )
        _require_equal(
            hard["edge1500_pass"], hard["edge1500_decimal"] > 0, "edge1500_pass"
        )

        mc = diagnostic["monte_carlo"]
        _require_equal(mc["B"], MONTE_CARLO_B, "mc.B")
        _require_equal(mc["null_statistics_count"], MONTE_CARLO_B, "mc.count")
        mc_count_invalid = (
            not reproduction_valid
            and "MONTE_CARLO_COUNT_INVALID" in invalid_reasons
        )
        mc_null_fields = (
            mc["upper_tail_count"],
            mc["p_value"],
            hard["monte_carlo_p1500"],
            hard["monte_carlo_p1500_pass"],
        )
        if mc_count_invalid:
            if any(value is not None for value in mc_null_fields):
                raise ReproductionInvalid(
                    "RESULT_SCHEMA_INVALID",
                    "Monte Carlo count invalid requires calculation nulls",
                )
        else:
            if any(value is None for value in mc_null_fields):
                raise ReproductionInvalid(
                    "RESULT_SCHEMA_INVALID",
                    "Monte Carlo nulls require MONTE_CARLO_COUNT_INVALID",
                )
            if (
                not isinstance(mc["upper_tail_count"], int)
                or isinstance(mc["upper_tail_count"], bool)
                or not 0 <= mc["upper_tail_count"] <= MONTE_CARLO_B
            ):
                raise ReproductionInvalid(
                    "RESULT_SCHEMA_INVALID", "mc upper-tail bounds"
                )
            _require_equal(
                mc["observed_statistic"],
                diagnostic["window1500"]["observed_hit_rate"],
                "mc.observed",
            )
            _require_equal(
                mc["p_value"],
                (1 + mc["upper_tail_count"]) / (MONTE_CARLO_B + 1),
                "mc.p_value",
            )
            _require_equal(hard["monte_carlo_p1500"], mc["p_value"], "hard.mc")
            _require_equal(
                hard["monte_carlo_p1500_pass"],
                p_value_pass(mc["p_value"]),
                "hard.mc_pass",
            )

        oos_count = diagnostic["oos"]["eligible_draws"]
        _require_equal(hard["oos_eligible_draws"], oos_count, "oos.count")
        mature = oos_count >= OOS_MATURITY
        _require_equal(hard["oos_mature"], mature, "oos.mature")
        if mature:
            edge = diagnostic["oos"]["edge_decimal"]
            _require_equal(hard["edge_oos_decimal"], edge, "oos.edge")
            _require_equal(hard["edge_oos_percentage_points"], edge * 100.0, "oos.pp")
            _require_equal(hard["edge_oos_pass"], edge > 0, "oos.pass")
        else:
            _require_equal(hard["edge_oos_decimal"], None, "oos.edge")
            _require_equal(hard["edge_oos_percentage_points"], None, "oos.pp")
            _require_equal(hard["edge_oos_pass"], None, "oos.pass")

        expected_outcome, expected_insufficient = outcome_for(
            reproduction_valid, invalid_reasons, hard
        )
        _require_equal(row["outcome"], expected_outcome, "outcome")
        _require_equal(insufficient, expected_insufficient, "insufficient_reasons")

        mcnemar_result = diagnostic["mcnemar"]
        _require_equal(
            mcnemar_result["discordant_count"],
            mcnemar_result["b"] + mcnemar_result["c"],
            "mcnemar.discordant",
        )
        if not 0 <= mcnemar_result["p_value"] <= 1:
            raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "mcnemar p")

        total_eligible = diagnostic["eligible_draw_count"]
        total_hits = control["hits"]
        if not 0 <= total_hits <= total_eligible:
            raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "control count bounds")
        _require_equal(control["eligible_draws"], total_eligible, "control.eligible")
        _require_equal(control["hit_rate"], total_hits / total_eligible, "control.rate")

        sharpe = diagnostic["sharpe"]
        _require_equal(len(sharpe["window_edges"]), 9, "sharpe.window_count")
        sigma = statistics.pstdev(sharpe["window_edges"])
        if sigma == 0:
            _require_equal(sharpe["status"], "UNDEFINED_ZERO_VARIANCE", "sharpe.status")
            _require_equal(sharpe["value"], None, "sharpe.value")
        else:
            _require_equal(sharpe["status"], "DEFINED", "sharpe.status")
            _require_equal(
                sharpe["value"],
                statistics.fmean(sharpe["window_edges"]) / sigma,
                "sharpe.value",
            )

        incremental = diagnostic["incremental_5_vs_4"]
        if incremental is not None:
            eligible = incremental["eligible_draws"]
            four_hits = incremental["four_bet_hits"]
            five_hits = incremental["five_bet_hits"]
            if not 0 <= four_hits <= eligible or not 0 <= five_hits <= eligible:
                raise ReproductionInvalid(
                    "RESULT_SCHEMA_INVALID", "incremental count bounds"
                )
            _require_equal(
                incremental["four_bet_hit_rate"],
                four_hits / eligible,
                "incremental.four_rate",
            )
            _require_equal(
                incremental["five_bet_hit_rate"],
                five_hits / eligible,
                "incremental.five_rate",
            )
            _require_equal(
                incremental["five_minus_four_hit_rate"],
                (five_hits - four_hits) / eligible,
                "incremental.delta",
            )


def _strategy_document(
    identity: str,
    ticket_count: int,
    records: Sequence[dict[str, Any]],
    skipped: Sequence[dict[str, Any]],
    incremental: dict[str, Any] | None,
    monte_carlo_result: Mapping[str, Any],
) -> dict[str, Any]:
    probability = equal_ticket_probability(ticket_count)
    hits = [bool(row["strategy_hit"]) for row in records]
    controls = [bool(row["orthogonal_hit"]) for row in records]
    w150 = window_metric(hits[-150:], controls[-150:], probability)
    w500 = window_metric(hits[-500:], controls[-500:], probability)
    w1500 = window_metric(hits[-1500:], controls[-1500:], probability)
    oos_rows = [row for row in records if is_oos(row["draw"])]
    validate_oos_selection(oos_rows)
    oos_hits = [bool(row["strategy_hit"]) for row in oos_rows]
    oos_controls = [bool(row["orthogonal_hit"]) for row in oos_rows]
    oos = window_metric(oos_hits, oos_controls, probability)
    mc = dict(monte_carlo_result)
    mature = len(oos_rows) >= OOS_MATURITY
    hard = {
        "edge500_decimal": w500["edge_decimal"],
        "edge500_percentage_points": w500["edge_percentage_points"],
        "edge500_pass": w500["edge_decimal"] > 0,
        "edge1500_decimal": w1500["edge_decimal"],
        "edge1500_percentage_points": w1500["edge_percentage_points"],
        "edge1500_pass": w1500["edge_decimal"] > 0,
        "monte_carlo_p1500": mc["p_value"],
        "monte_carlo_p1500_pass": p_value_pass(mc["p_value"]),
        "oos_eligible_draws": len(oos_rows),
        "oos_mature": mature,
        "edge_oos_decimal": oos["edge_decimal"] if mature else None,
        "edge_oos_percentage_points": oos["edge_percentage_points"] if mature else None,
        "edge_oos_pass": oos["edge_decimal"] > 0 if mature else None,
    }
    outcome, insufficient = outcome_for(True, [], hard)
    return {
        "strategy_identity": identity,
        "reproduction_valid": True,
        "invalid_reasons": [],
        "hard_gate_results": hard,
        "insufficient_evidence_reasons": insufficient,
        "diagnostic_results": {
            "ticket_count": ticket_count,
            "complete_draw_count": DRAW_COUNT,
            "eligible_draw_count": len(records),
            "first_eligible_draw": records[0]["draw"] if records else None,
            "last_eligible_draw": records[-1]["draw"] if records else None,
            "skipped_draws": list(skipped),
            "random_probability": probability,
            "window150": w150,
            "window500": w500,
            "window1500": w1500,
            "oos": oos,
            "orthogonal_control": {
                "ticket_count": ticket_count,
                "slice": [0, ticket_count],
                "eligible_draws": len(records),
                "hits": sum(controls),
                "hit_rate": sum(controls) / len(controls),
                "p1_minus_control_hit_rate": (
                    sum(hits) / len(hits) - sum(controls) / len(controls)
                ),
                "diagnostic_only": True,
            },
            "monte_carlo": mc,
            "mcnemar": mcnemar(hits[-1500:], controls[-1500:]),
            "sharpe": sharpe_diagnostic(hits, probability),
            "incremental_5_vs_4": incremental,
        },
        "outcome": outcome,
        "outcome_precedence_rule": OUTCOME_PRECEDENCE,
    }


def _authorities() -> dict[str, Any]:
    return {
        "main": {"commit": MAIN_COMMIT, "tree": MAIN_TREE},
        "algorithm_source": {
            "commit": ALGORITHM_COMMIT,
            "path": ALGORITHM_PATH,
            "blob": ALGORITHM_BLOB,
            "callable": ALGORITHM_CALLABLE,
            "callable_closure": list(ALGORITHM_CLOSURE),
            "four_bet_slice": [0, 4],
            "five_bet_slice": [0, 5],
        },
        "environment_r3": {
            "merge_commit": ENVIRONMENT_MERGE,
            "root": ENVIRONMENT_ROOT,
            "installation_receipt_sha256": INSTALLATION_RECEIPT_SHA256,
            "runtime_fingerprint_v3": RUNTIME_FINGERPRINT_V3,
        },
        "contract_r3": {"merge_commit": MAIN_COMMIT, "root": CONTRACT_ROOT},
        "diagnostic_control": {
            "commit": CONTROL_COMMIT,
            "path": CONTROL_PATH,
            "blob": CONTROL_BLOB,
            "symbol": CONTROL_SYMBOL,
            "helper_path": CONTROL_HELPER_PATH,
            "helper_blob": CONTROL_HELPER_BLOB,
            "four_bet_slice": [0, 4],
            "five_bet_slice": [0, 5],
            "lottery_type": "BIG_LOTTO",
            "main_number_min": 1,
            "main_number_max": 49,
            "diagnostic_only": True,
        },
        "random_baseline": {
            "commit": MAIN_COMMIT,
            "path": BASELINE_PATH,
            "blob": BASELINE_BLOB,
            "callable": "n_ticket_probability",
            "pool_size": 49,
            "pick_count": 6,
            "match_threshold": 4,
        },
        "p_value": {
            "commit": MAIN_COMMIT,
            "path": P_VALUE_PATH,
            "blob": P_VALUE_BLOB,
            "callable": "empirical_p_value",
            "epsilon": EPSILON,
            "plus_one": True,
        },
    }


def build_reproduction(
    repo: Path, runtime_root: Path, snapshot: Path = SNAPSHOT_PATH
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    require_runtime_identity(repo, runtime_root)
    if _git(repo, "rev-parse", f"{MAIN_COMMIT}^{{tree}}").decode().strip() != MAIN_TREE:
        raise ReproductionInvalid("SOURCE_IDENTITY_MISMATCH", "main tree")
    require_blob(repo, MAIN_COMMIT, BASELINE_PATH, BASELINE_BLOB)
    require_blob(repo, MAIN_COMMIT, P_VALUE_PATH, P_VALUE_BLOB)
    algorithm, control = source_closures(repo)
    draws = load_draws(snapshot)
    histories = [draw.history_row() for draw in draws]
    per_strategy: dict[int, list[dict[str, Any]]] = {4: [], 5: []}
    skipped = [
        {"draw": draw.draw, "reason": "INSUFFICIENT_HISTORICAL_PREFIX"}
        for draw in draws[:3]
    ]
    for index in range(3, len(draws)):
        prefix = histories[:index]
        target = draws[index]
        require_prefix(prefix, target, index)
        raw_algorithm = algorithm(prefix)
        raw_control = control(prefix)
        for _, ticket_count in STRATEGIES:
            strategy_tickets = validate_tickets(raw_algorithm, ticket_count)
            control_tickets = validate_tickets(raw_control, ticket_count)
            per_strategy[ticket_count].append(
                {
                    "draw": target.draw,
                    "date": target.date,
                    "history_length": index,
                    "strategy_identity": STRATEGIES[ticket_count - 4][0],
                    "ticket_count": ticket_count,
                    "strategy_tickets": strategy_tickets,
                    "orthogonal_tickets": control_tickets,
                    "main_numbers": list(target.numbers),
                    "strategy_hit": hit(strategy_tickets, target.numbers),
                    "orthogonal_hit": hit(control_tickets, target.numbers),
                    "diagnostic_only": True,
                }
            )
    four_hits = [row["strategy_hit"] for row in per_strategy[4]][-1500:]
    five_hits = [row["strategy_hit"] for row in per_strategy[5]][-1500:]
    incremental = {
        "eligible_draws": 1500,
        "four_bet_hits": sum(four_hits),
        "five_bet_hits": sum(five_hits),
        "four_bet_hit_rate": sum(four_hits) / 1500,
        "five_bet_hit_rate": sum(five_hits) / 1500,
        "five_minus_four_hit_rate": (sum(five_hits) - sum(four_hits)) / 1500,
        "diagnostic_only": True,
    }
    monte_carlo_results = production_monte_carlo_pair(
        {
            4: sum(four_hits) / len(four_hits),
            5: sum(five_hits) / len(five_hits),
        }
    )
    strategy_results = [
        _strategy_document(
            STRATEGIES[0][0],
            4,
            per_strategy[4],
            skipped,
            None,
            monte_carlo_results[4],
        ),
        _strategy_document(
            STRATEGIES[1][0],
            5,
            per_strategy[5],
            skipped,
            incremental,
            monte_carlo_results[5],
        ),
    ]
    validate_strategy_order(strategy_results)
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_name": TASK_NAME,
        "classification": {
            "evidence_status": "HISTORICAL_RESEARCH_ONLY",
            "current_significance": "NOT_ESTABLISHED",
            "diagnostic_only": True,
            "production_eligible": False,
            "ranking_eligible": False,
            "promotion_eligible": False,
            "rejection_authority": False,
        },
        "authorities": _authorities(),
        "snapshot": {
            "path": str(snapshot),
            "sha256": SNAPSHOT_SHA256,
            "size_bytes": SNAPSHOT_SIZE,
            "schema_version": "SnapshotManifestV1",
            "canonical_view": SNAPSHOT_VIEW,
            "draw_count": DRAW_COUNT,
            "min_draw": DRAW_MIN,
            "max_draw": DRAW_MAX,
            "access_mode": "ro_immutable",
            "query_only": True,
            "sidecars_allowed": False,
        },
        "method": {
            "target_event": "ANY_TICKET_MATCHES_AT_LEAST_4_OF_6_MAIN_NUMBERS",
            "draw_order": "ASCENDING_CANONICAL_DRAW",
            "prefix_rule": "draws[:i]",
            "window_warning": 150,
            "window_gate": 500,
            "window_formal": 1500,
            "cutoff_draw": CUTOFF_DRAW,
            "cutoff_date": CUTOFF_DATE,
            "oos_rule": "STRICTLY_AFTER_CUTOFF_THROUGH_115000072",
            "oos_maturity": OOS_MATURITY,
            "B": MONTE_CARLO_B,
            "null_statistics_count": MONTE_CARLO_B,
            "master_seed": MASTER_SEED,
            "strategy_order": [row[0] for row in STRATEGIES],
            "random_engine": "CPython random.Random",
            "seed_version": 2,
            "subseed_scheme": "SHA256_INT_BIG_UNSIGNED_V1",
            "subseed_prefix": SUBSEED_PREFIX.decode("ascii"),
            "alternative": "greater",
            "familywise_alpha": 0.05,
            "per_strategy_alpha": PER_STRATEGY_ALPHA,
            "epsilon": EPSILON,
        },
        "strategy_results": strategy_results,
        "disclaimer": DISCLAIMER,
    }
    validate_result_semantics(result)
    return result, per_strategy[4], per_strategy[5]


def write_run(
    repo: Path, runtime_root: Path, output_dir: Path, snapshot: Path = SNAPSHOT_PATH
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=False)
    result, four_rows, five_rows = build_reproduction(repo, runtime_root, snapshot)
    payloads = {
        "result.json": canonical_bytes(result),
        "p1_4bet_per_draw.jsonl": b"".join(canonical_bytes(row) for row in four_rows),
        "p1_5bet_per_draw.jsonl": b"".join(canonical_bytes(row) for row in five_rows),
    }
    for name, payload in payloads.items():
        (output_dir / name).write_bytes(payload)
    return {name: sha256_bytes(payload) for name, payload in payloads.items()}


def comparison_document(run1: Path, run2: Path) -> dict[str, Any]:
    result1 = (run1 / "result.json").read_bytes()
    result2 = (run2 / "result.json").read_bytes()
    per1 = (run1 / "p1_4bet_per_draw.jsonl").read_bytes() + (
        run1 / "p1_5bet_per_draw.jsonl"
    ).read_bytes()
    per2 = (run2 / "p1_4bet_per_draw.jsonl").read_bytes() + (
        run2 / "p1_5bet_per_draw.jsonl"
    ).read_bytes()
    if result1 != result2 or per1 != per2:
        raise ReproductionInvalid("RUN_OUTPUT_MISMATCH", "two runs differ")
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "task_name": TASK_NAME,
        "run1_result_sha256": sha256_bytes(result1),
        "run2_result_sha256": sha256_bytes(result2),
        "result_byte_identical": True,
        "run1_per_draw_bundle_sha256": sha256_bytes(per1),
        "run2_per_draw_bundle_sha256": sha256_bytes(per2),
        "per_draw_bundle_byte_identical": True,
        "canonical_result_sha256": sha256_bytes(result1),
        "decision": "ACCEPT_BYTE_IDENTICAL_RUNS",
    }


def report_text(result: Mapping[str, Any], comparison: Mapping[str, Any]) -> str:
    rows = result["strategy_results"]
    lines = [
        "# P1 Family Independent Reproduction R5",
        "",
        "This is historical research evidence only. It is not betting advice and "
        "has no production, ranking, promotion, or rejection authority.",
        "",
        "| Strategy | Outcome | Edge500 (pp) | Edge1500 (pp) | MC p | OOS draws |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        hard = row["hard_gate_results"]
        lines.append(
            f"| {row['strategy_identity']} | {row['outcome']} | "
            f"{hard['edge500_percentage_points']:.6f} | "
            f"{hard['edge1500_percentage_points']:.6f} | "
            f"{hard['monte_carlo_p1500']:.6f} | "
            f"{hard['oos_eligible_draws']} |"
        )
    lines.extend(
        [
            "",
            f"Two-run result byte identity: {comparison['result_byte_identical']}.",
            "Both strategies remain NOT_ESTABLISHED and DIAGNOSTIC_ONLY.",
            "",
        ]
    )
    return "\n".join(lines)


def finalize_package(repo: Path, run1: Path, run2: Path) -> None:
    package = repo / PACKAGE_ROOT
    comparison = comparison_document(run1, run2)
    result_payload = (run1 / "result.json").read_bytes()
    result = json.loads(result_payload)
    (package / "result.json").write_bytes(result_payload)
    (package / "run_comparison.json").write_bytes(canonical_bytes(comparison))
    (package / "REPORT.md").write_text(
        report_text(result, comparison), encoding="utf-8", newline="\n"
    )


def build_manifest(
    repo: Path,
    *,
    judge_input_head: str,
    judge_input_tree: str,
    judge_verdict: str,
) -> dict[str, Any]:
    records = []
    for relative in CONTENT_PATHS:
        path = repo / relative
        records.append(
            {
                "path": relative,
                "sha256": sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "schema_version": "LotteryNewP1FamilyIndependentReproductionManifestV1",
        "task_name": TASK_NAME,
        "package_paths": list(PACKAGE_PATHS),
        "content_records": records,
        "sha256sums_coverage": list(PACKAGE_PATHS[:-2]) + [PACKAGE_PATHS[-1]],
        "full_judge": {
            "input_head": judge_input_head,
            "input_tree": judge_input_tree,
            "verdict": judge_verdict,
        },
        "seal_design": "NON_RECURSIVE_MANIFEST_HASHED_BY_SHA256SUMS",
    }


def validate_manifest_coverage(manifest: Mapping[str, Any]) -> None:
    expected = sorted(list(CONTENT_PATHS) + [f"{PACKAGE_ROOT}/MANIFEST.json"])
    actual = sorted(manifest.get("sha256sums_coverage", []))
    if actual != expected:
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "SEAL_COVERAGE_INVALID")


def validate_sha256sum_lines(payload: str, expected_paths: Sequence[str]) -> None:
    lines = payload.splitlines(keepends=True)
    paths: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)\n", line)
        if match is None:
            raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "SEAL_FORMAT_INVALID")
        paths.append(match.group(2))
    if paths != sorted(expected_paths) or paths != sorted(paths):
        raise ReproductionInvalid("RESULT_SCHEMA_INVALID", "SEAL_FORMAT_INVALID")


def write_seals(
    repo: Path,
    *,
    judge_input_head: str,
    judge_input_tree: str,
    judge_verdict: str,
) -> None:
    package = repo / PACKAGE_ROOT
    manifest = build_manifest(
        repo,
        judge_input_head=judge_input_head,
        judge_input_tree=judge_input_tree,
        judge_verdict=judge_verdict,
    )
    validate_manifest_coverage(manifest)
    (package / "MANIFEST.json").write_bytes(schema_bytes(manifest))
    covered = sorted(list(CONTENT_PATHS) + [f"{PACKAGE_ROOT}/MANIFEST.json"])
    lines = [f"{sha256_path(repo / path)}  {path}\n" for path in covered]
    sums = "".join(lines)
    validate_sha256sum_lines(sums, covered)
    (package / "SHA256SUMS").write_text(sums, encoding="ascii", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--run1", type=Path)
    parser.add_argument("--run2", type=Path)
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--judge-input-head")
    parser.add_argument("--judge-input-tree")
    parser.add_argument("--judge-verdict")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    if args.seal:
        if not all(
            (args.judge_input_head, args.judge_input_tree, args.judge_verdict)
        ):
            raise SystemExit("--seal requires Judge identity and verdict")
        write_seals(
            repo,
            judge_input_head=args.judge_input_head,
            judge_input_tree=args.judge_input_tree,
            judge_verdict=args.judge_verdict,
        )
        print('{"result":"SEALED"}')
        return 0
    if args.finalize:
        if not args.run1 or not args.run2:
            raise SystemExit("--finalize requires --run1 and --run2")
        finalize_package(repo, args.run1.resolve(), args.run2.resolve())
        print('{"result":"FINALIZED"}')
        return 0
    if not args.runtime_root or not args.output_dir:
        raise SystemExit("run mode requires --runtime-root and --output-dir")
    digests = write_run(
        repo, args.runtime_root.resolve(), args.output_dir.resolve(), args.snapshot.resolve()
    )
    print(json.dumps({"result": "PASS", "digests": digests}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
