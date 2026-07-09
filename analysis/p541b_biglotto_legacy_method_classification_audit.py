"""P541B — BIG_LOTTO legacy / folklore / statistical method classification audit.

Read-only, static-inspection audit. Consumes the P541A strategy inventory /
replay coverage artifact and classifies every discovered BIG_LOTTO legacy
script (plus additional BIG_LOTTO-referencing files found outside P541A's
tools/*.py + analysis/*.py scan) into a runnable-status taxonomy, using
AST-based static inspection only (no import, no execution).

Historical legacy method classification audit only; not a prediction,
betting edge, future-winning, or production-readiness claim.

Run:
    python3 analysis/p541b_biglotto_legacy_method_classification_audit.py
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DISCLAIMER = (
    "Historical legacy method classification audit only; not a "
    "prediction, betting edge, future-winning, or production-readiness claim."
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATE_TAG = "20260709"

P541A_JSON = (
    REPO_ROOT
    / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json"
)
P541A_MD = (
    REPO_ROOT
    / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md"
)

REGISTRY_FILE = "lottery_api/models/replay_strategy_registry.py"
ADAPTER_FILES = [
    "lottery_api/models/p42_wave3_biglotto_adapters.py",
    "lottery_api/models/p93_tierb_replay_adapters.py",
]
D3_TEST_FILE = "tests/test_p263a_d3_strategy_status_coverage_audit.py"
QUICK_PREDICT_FILE = "tools/quick_predict.py"

BIG_LOTTO_NAME_PATTERN = r"big_lotto\|BIG_LOTTO\|biglotto\|大樂透"

# ── P541A-derived known-id context ───────────────────────────────────────────

REPLAYED_IDS = {
    "bet2_fourier_expansion_biglotto": 1500,
    "biglotto_deviation_2bet": 1570,
    "biglotto_echo_aware_3bet": 4500,
    "biglotto_triple_strike": 1570,
    "biglotto_ts3_markov_4bet_w30": 6000,
    "cold_complement_biglotto": 1500,
    "coldpool15_biglotto": 1500,
    "fourier30_markov30_biglotto": 1500,
    "markov_2bet_biglotto": 1500,
    "markov_single_biglotto": 1500,
    "ts3_regime_3bet": 1500,
}
ZERO_REPLAY_IDS = ["biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet"]
PHANTOM_IDS = [
    "p1_dev_sum5bet",
    "p1_deviation_4bet",
    "p1_neighbor_cold_2bet",
    "regime_2bet",
]
ALL_KNOWN_IDS = set(REPLAYED_IDS) | set(ZERO_REPLAY_IDS) | set(PHANTOM_IDS)

# ── Additional discovery globs (item 3 of task spec: re-scan beyond P541A's
#    tools/*.py + analysis/*.py-only scan). Each glob is intentionally scoped
#    to directories/files that plausibly contain individual candidate
#    prediction methods, not generic API/route/test/infra noise. ───────────

EXTRA_GLOB_GROUPS: list[tuple[str, list[str]]] = [
    ("root_level_scripts", ["*.py"]),
    ("ai_lab", ["ai_lab/*.py", "ai_lab/**/*.py"]),
    ("recovered_strategies_biglotto", ["recovered_strategies/biglotto/*.py"]),
    ("lottery_api_models", ["lottery_api/models/*.py"]),
    ("lottery_api_tools", ["lottery_api/tools/*.py"]),
    ("lottery_api_engine", ["lottery_api/engine/*.py"]),
]

# Files that are already fully accounted for elsewhere (registry, adapters,
# D3 test, quick_predict dispatcher) and must not be re-classified as
# "legacy" candidates -- they are the known-good wiring P541A already read.
EXCLUDE_FROM_LEGACY_SET = {
    REGISTRY_FILE,
    *ADAPTER_FILES,
    D3_TEST_FILE,
    QUICK_PREDICT_FILE,
}

# Generic framework/infra filenames inside lottery_api/models that are not
# themselves a numbers-selection method (they are shared scaffolding used by
# many strategies), even though they match the BIG_LOTTO keyword grep.
FRAMEWORK_FILE_BASENAMES = {
    "strategy_adapter.py",
    "strategy_evaluator.py",
    "backtest_framework.py",
    "replay_strategy_catalog_contract.py",
}

# ── method_family keyword table (weighted scoring; enum is fixed by spec) ──

FAMILY_KEYWORDS: dict[str, list[str]] = {
    "ML_like": [
        "lstm", "xgboost", "bayesian", "ensemble", "neural", "transformer",
        "gpt", "autogluon", "meta_learning", "graph_predictor", "mcts",
        "reinforcement", "rl_", "_rl", "attention", "q_learning", "critic",
        "actor_critic", "quantum_random", "finetune", "train_",
    ],
    "markov": ["markov"],
    "hot_cold": [
        "hot_cold", "hotcold", "熱號", "冷號", "hot_pool", "coldpool",
        "hot number", "cold number",
    ],
    "frequency": ["frequency", "freq_", "_freq", "頻率", "頻次"],
    "overdue": ["overdue", "遺漏", "gap_analysis"],
    "parity": ["parity", "奇偶", "odd_even", "oddeven"],
    "sum_range": ["sum_range", "sum5", "sum_value", "和值", "dev_sum", "sum_bet"],
    "tail": ["tail_number", "tail_balance", "尾數"],
    "zone": ["zone_split", "zone_balance", "區間", "second_zone", "zone"],
    "neighbor": ["neighbor", "鄰號"],
    "deviation": ["deviation", "偏差", "dev_"],
    "regime": ["regime"],
    "folklore": [
        "folklore", "生肖", "風水", "幸運", "lucky", "superstition", "算命",
        "dream_number", "auspicious",
    ],
    "statistical": [
        "fourier", "echo_aware", "acb", "ts3", "p_value", "z_score",
        "significance", "correlation", "regression", "mcnemar", "midfreq",
        "mid_freq", "orthogonal", "wavelet", "spectral", "monte_carlo",
        "portfolio_optim",
    ],
    "data_prep": [
        "ingest", "backfill", "fetcher", "fetch_", "parser", "csv_validator",
        "migration", "schema", "import_", "historical_draw_parser",
    ],
    "report": [
        "report", "export", "audit", "diagnostic", "benchmark",
        "verification", "summary", "dashboard", "evidence", "scoreboard",
        "regression_archive", "acceptance",
    ],
    "utility": [
        "scheduler", "helper", "_util", "util_", "config", "adapter",
        "registry", "contract", "logger", "debug_", "test_", "console",
        "operator_", "coverage_utility",
    ],
}

FAMILY_TIEBREAK_ORDER = [
    "ML_like", "markov", "hot_cold", "frequency", "overdue", "parity",
    "sum_range", "tail", "zone", "neighbor", "deviation", "regime",
    "statistical", "folklore", "data_prep", "report", "utility", "unknown",
]

PREDICTION_FUNCNAME_RE = re.compile(
    r"^(predict|select|choose|pick|generate|gen_|recommend|suggest|"
    r"produce_ticket|build_ticket)_?", re.IGNORECASE,
)
NUMBER_GEN_CONTENT_RE = re.compile(
    r"random\.sample\(|range\(\s*1\s*,\s*(43|44|49|50)\s*\)|"
    r"選[號号]|生成號碼|下注號碼",
)
REPORT_UTILITY_FILENAME_RE = re.compile(
    r"^(test_|debug_|verify_|validat|export_|audit_|diagnostic|backfill_|"
    r"ingest_|fetch_|scheduler|benchmark_|csv_|parser_|quick_test|"
    r"verification_)",
    re.IGNORECASE,
)
DEPRECATED_FILENAME_RE = re.compile(
    r"(deprecated|obsolete|_old\b|_bak\b|_backup\b|_v1\b)", re.IGNORECASE,
)

RISKY_CALL_LEAF_NAMES = {
    "system", "Popen", "call", "run", "check_call", "check_output",
    "urlopen", "urlretrieve", "get", "post", "put", "delete", "request",
    "unlink", "rmtree", "remove", "exit", "input",
}


def _call_leaf_name(call: ast.Call) -> Optional[str]:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_risky_call(call: ast.Call, local_func_names: frozenset[str] = frozenset()) -> bool:
    """Deny-by-default is too noisy for this codebase's common preamble
    (os.path.dirname/join, random.seed, logging.basicConfig, sys.path.insert,
    etc.). Only flag calls with a real reuse/import-safety implication:
    file writes, DB access, process/network calls, or calling one of the
    file's own top-level functions directly (i.e. the module runs its own
    pipeline on import, not just on `python file.py`)."""
    name = _call_leaf_name(call)
    if name in local_func_names:
        return True
    if name in RISKY_CALL_LEAF_NAMES:
        return True
    src = ast.dump(call)
    if "connect" in src or "sqlite3" in src:
        return True
    if re.search(r"'(open|to_csv|to_json|to_excel|dump)'", src):
        return True
    return False


def _stmt_is_risky(node: ast.stmt, local_func_names: frozenset[str] = frozenset()) -> bool:
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith,
                          ast.Assert, ast.Delete)):
        return True
    if isinstance(node, ast.Raise):
        return False  # e.g. bare re-raise inside an except handler
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        return _is_risky_call(node.value, local_func_names)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        value = getattr(node, "value", None)
        if isinstance(value, ast.Call):
            return _is_risky_call(value, local_func_names)
        return False
    if isinstance(node, ast.Try):
        body = list(node.body) + list(node.orelse) + list(node.finalbody)
        for handler in node.handlers:
            body.extend(handler.body)
        return any(
            not isinstance(s, (ast.Import, ast.ImportFrom, ast.Pass)) and _stmt_is_risky(s, local_func_names)
            for s in body
        )
    if isinstance(node, ast.If):
        return any(_stmt_is_risky(s, local_func_names) for s in node.body + node.orelse)
    return False


DB_CALL_RE = re.compile(r"sqlite3\.connect|\.execute\(\s*[\"']\s*(SELECT|INSERT|UPDATE|DELETE)")
WRITE_CALL_RE = re.compile(
    r"\.to_csv\(|\.to_json\(|\.to_excel\(|json\.dump\(|pickle\.dump\(|"
    r"os\.remove\(|shutil\.|open\([^)]*[\"'][wa]b?[\"']",
)
HARDCODED_PATH_RE = re.compile(r"[\"']\/Users\/[a-zA-Z0-9_\-\/\.]+[\"']")
HARDCODED_DRAW_RE = re.compile(r"\b11\d{7}\b")
ARGPARSE_ENV_RE = re.compile(r"argparse|sys\.argv|os\.environ|getenv\(")


def git_grep_files(pattern: str, path_globs: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "grep", "-il", pattern, "--", *path_globs],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if result.returncode not in (0, 1):
        return []
    return sorted(set(l for l in result.stdout.splitlines() if l.strip()))


def load_p541a() -> dict:
    with open(P541A_JSON, encoding="utf-8") as f:
        return json.load(f)


def discover_files(p541a: dict) -> dict[str, list[str]]:
    """Return {group_name: [relative file paths]} for every scanned source."""
    amb = p541a["ambiguous_or_unmapped_items"]
    groups: dict[str, list[str]] = {
        "p541a_tools": sorted(amb["legacy_tools_scripts_matched_not_individually_traced"]),
        "p541a_analysis": sorted(amb["legacy_analysis_scripts_matched_not_individually_traced"]),
    }
    for group_name, globs in EXTRA_GLOB_GROUPS:
        files = git_grep_files(BIG_LOTTO_NAME_PATTERN, globs)
        if group_name == "root_level_scripts":
            # root-level *.py only (no subdirectory) to avoid re-matching
            # every other group's files via the broad "*.py" pathspec.
            files = [f for f in files if "/" not in f]
        files = [f for f in files if f not in EXCLUDE_FROM_LEGACY_SET]
        if group_name == "lottery_api_models":
            files = [
                f for f in files
                if Path(f).name not in FRAMEWORK_FILE_BASENAMES
            ]
        groups[group_name] = files
    return groups


def discover_out_of_scope_summary() -> dict:
    """Directories intentionally NOT given individual per-file records."""
    scripts = git_grep_files(BIG_LOTTO_NAME_PATTERN, ["scripts/*.py", "scripts/**/*.py"])
    tests = git_grep_files(BIG_LOTTO_NAME_PATTERN, ["tests/*.py"])
    routes = git_grep_files(BIG_LOTTO_NAME_PATTERN, ["lottery_api/routes/*.py"])
    utils = git_grep_files(BIG_LOTTO_NAME_PATTERN, ["lottery_api/utils/*.py"])
    fetcher_diag = git_grep_files(
        BIG_LOTTO_NAME_PATTERN,
        ["lottery_api/fetcher/*.py", "lottery_api/diagnostics/*.py"],
    )
    src_js = git_grep_files(BIG_LOTTO_NAME_PATTERN, ["src/**/*.js", "src/*.js"])
    return {
        "scripts_dir": {
            "count": len(scripts),
            "reason": (
                "Operational/ingestion/backfill/audit/migration worker scripts "
                "(scripts/p*.py task-numbered lineage). Naming and prior "
                "artifact evidence (e.g. p356a_all_strategy_inventory.py, "
                "p1_replay_truth_executable_inventory.py) indicate these are "
                "one-off task-execution or inventory scripts, not standalone "
                "candidate prediction methods. Not given individual "
                "method_classification_records in this pass; grouped here."
            ),
            "sample": scripts[:15],
        },
        "tests_dir": {
            "count": len(tests),
            "reason": (
                "pytest test files (source_type=test). By definition these "
                "verify other code rather than implement a prediction method; "
                "grouped rather than individually classified."
            ),
            "sample": tests[:10],
        },
        "lottery_api_routes": {
            "count": len(routes),
            "reason": "FastAPI route handlers (source_type=ui_reference/API infra), not methods.",
            "files": routes,
        },
        "lottery_api_utils": {
            "count": len(utils),
            "reason": "Shared utility modules (scheduler, csv validation, baseline calc), not methods.",
            "files": utils,
        },
        "lottery_api_fetcher_diagnostics": {
            "count": len(fetcher_diag),
            "reason": "Data-fetch/diagnostics infra, not prediction methods.",
            "files": fetcher_diag,
        },
        "frontend_src_js": {
            "count": len(src_js),
            "reason": (
                "Already fully named and classified by P541A's "
                "folklore_and_statistical_method_inventory section (17 "
                "generic frontend advisory strategy classes in "
                "src/engine/strategies/*.js, e.g. FrequencyStrategy, "
                "HotColdMixStrategy, MarkovStrategy). They have no "
                "strategy_id in the replay system and no replay coverage "
                "is possible under the current schema; not re-enumerated "
                "here."
            ),
            "sample": src_js[:10],
        },
    }


# ── per-file static feature extraction (AST + regex; no import/execution) ──


def read_source(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def extract_features(rel_path: str) -> dict:
    abs_path = REPO_ROOT / rel_path
    content = read_source(abs_path)
    features: dict = {
        "rel_path": rel_path,
        "exists": content is not None,
        "syntax_error": None,
        "docstring": None,
        "function_names": [],
        "has_main_guard": False,
        "module_level_db_call": False,
        "module_level_write": False,
        "module_level_other_sideeffect": False,
        "uses_db_anywhere": False,
        "writes_files_anywhere": False,
        "hardcoded_abs_path": False,
        "hardcoded_draw_or_date": False,
        "uses_argparse_or_env": False,
        "has_functions": False,
        "content_len": len(content) if content else 0,
    }
    if content is None:
        features["syntax_error"] = "file_not_found_or_unreadable"
        return features

    features["uses_db_anywhere"] = bool(DB_CALL_RE.search(content))
    features["writes_files_anywhere"] = bool(WRITE_CALL_RE.search(content))
    features["hardcoded_abs_path"] = bool(HARDCODED_PATH_RE.search(content))
    features["hardcoded_draw_or_date"] = bool(HARDCODED_DRAW_RE.search(content))
    features["uses_argparse_or_env"] = bool(ARGPARSE_ENV_RE.search(content))

    try:
        tree = ast.parse(content, filename=rel_path)
    except SyntaxError as e:
        features["syntax_error"] = f"{e.__class__.__name__}: {e.msg} (line {e.lineno})"
        return features

    features["docstring"] = ast.get_docstring(tree)
    func_names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_names.append(node.name)
    features["function_names"] = func_names
    features["has_functions"] = len(func_names) > 0
    # Only top-level (module-scope) function names matter for the "does
    # module-load call its own pipeline" check -- nested/class methods are
    # not directly callable as `foo()` from module scope.
    local_func_names = frozenset(
        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                              ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(
            getattr(node, "value", None), (ast.Constant,)
        ):
            continue  # docstring / bare string literal
        if isinstance(node, ast.If):
            test = node.test
            is_main_guard = (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
            )
            if is_main_guard:
                features["has_main_guard"] = True
                continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, "value", None)
            if value is not None and isinstance(value, ast.Call):
                src = ast.dump(value)
                if "connect" in src or "sqlite3" in src:
                    features["module_level_db_call"] = True
                elif _is_risky_call(value, local_func_names):
                    features["module_level_other_sideeffect"] = True
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call_src = ast.dump(node.value)
            if "connect" in call_src or "sqlite3" in call_src:
                features["module_level_db_call"] = True
            elif re.search(r"'(open|to_csv|to_json|dump|remove)'", call_src):
                features["module_level_write"] = True
            elif _is_risky_call(node.value, local_func_names):
                features["module_level_other_sideeffect"] = True
            continue
        if isinstance(node, ast.Try):
            if _stmt_is_risky(node, local_func_names):
                features["module_level_other_sideeffect"] = True
            continue
        if isinstance(node, ast.Raise):
            continue  # rare at true module top-level; not a reuse blocker on its own
        # Any other top-level statement (for/while/with/assert/delete/...)
        # counts as a module-load side effect signal.
        features["module_level_other_sideeffect"] = True

    return features


def score_family(rel_path: str, features: dict, content: str) -> str:
    name = Path(rel_path).name.lower()
    docstring = (features.get("docstring") or "").lower()
    text = f"{name} {docstring} {content[:6000].lower()}"
    scores = {fam: 0 for fam in FAMILY_KEYWORDS}
    for fam, kws in FAMILY_KEYWORDS.items():
        for kw in kws:
            kwl = kw.lower()
            if kwl in name:
                scores[fam] += 3
            if kwl in docstring:
                scores[fam] += 2
            if kwl in text:
                scores[fam] += 1
    best = max(scores.items(), key=lambda kv: (kv[1], -FAMILY_TIEBREAK_ORDER.index(kv[0])))
    if best[1] == 0:
        return "unknown"
    return best[0]


def detect_prediction_signal(rel_path: str, features: dict, content: str) -> tuple[Optional[bool], str]:
    name = Path(rel_path).name
    func_hits = [fn for fn in features["function_names"] if PREDICTION_FUNCNAME_RE.match(fn)]
    number_gen = bool(NUMBER_GEN_CONTENT_RE.search(content))
    report_util_name = bool(REPORT_UTILITY_FILENAME_RE.match(name))

    evidence_bits = []
    if func_hits:
        evidence_bits.append(f"function name(s) matching prediction pattern: {func_hits[:3]}")
    if number_gen:
        evidence_bits.append("content matches lottery number-generation pattern (random.sample/range(1,N)/選號)")
    if report_util_name:
        evidence_bits.append(f"filename matches report/utility/test naming pattern: '{name}'")

    if report_util_name and not (func_hits or number_gen):
        return False, "; ".join(evidence_bits) or "filename matches report/utility naming convention"
    if func_hits or number_gen:
        return True, "; ".join(evidence_bits)
    return None, "no strong static signal either way"


def find_duplicate_id(content: str) -> Optional[str]:
    for sid in sorted(ALL_KNOWN_IDS, key=len, reverse=True):
        if re.search(rf'["\']{re.escape(sid)}["\']', content):
            return sid
    return None


def classify_runnable(
    features: dict,
    family: str,
    is_pred: Optional[bool],
    duplicate_of: Optional[str],
    rel_path: str,
) -> tuple[str, str, str, str]:
    """Returns (runnable_status, why_not_runnable, rewrite_needed, estimated_effort)."""
    name = Path(rel_path).name

    if features["syntax_error"] == "file_not_found_or_unreadable":
        return (
            "broken_or_import_error",
            "File listed by static grep but could not be read from disk in this worktree.",
            "unknown",
            "unknown",
        )
    if features["syntax_error"]:
        return (
            "broken_or_import_error",
            f"Static AST parse failed: {features['syntax_error']}.",
            "unknown",
            "unknown",
        )
    if DEPRECATED_FILENAME_RE.search(name):
        return (
            "obsolete_or_deprecated",
            "Filename contains a deprecated/obsolete/backup/old-version marker.",
            "deprecate",
            "none",
        )
    if features["module_level_db_call"]:
        return (
            "imports_db_or_runs_work_at_module_load",
            "Module-level code opens or queries a database connection outside "
            "any function or `if __name__` guard, so merely importing this "
            "file could touch a database.",
            "db_safety_refactor",
            "medium",
        )
    if features["module_level_write"] or features["module_level_other_sideeffect"]:
        return (
            "unsafe_side_effects",
            "Executable statements run at module import time outside a "
            "`__main__` guard (file writes, network/DB calls, loops, or "
            "other side effects), making it unsafe to import for reuse "
            "without refactoring.",
            "small_refactor",
            "small",
        )
    if duplicate_of:
        status = "runnable_with_existing_adapter" if duplicate_of in REPLAYED_IDS else "not_a_strategy"
        return (
            status,
            f"String literal strategy_id '{duplicate_of}' found in source; "
            "likely a duplicate, earlier draft, or reference copy of an "
            "already-registered strategy rather than a distinct method.",
            "none",
            "none",
        )
    if is_pred is False:
        return (
            "not_a_strategy",
            "Static signals (filename convention, function names, no "
            "number-generation pattern) indicate this is a utility, report, "
            "data-prep, or test script rather than a numbers-selection method.",
            "none",
            "none",
        )
    if (features["hardcoded_abs_path"] or features["hardcoded_draw_or_date"]) and not features["uses_argparse_or_env"]:
        return (
            "hardcoded_paths_or_dates",
            "Contains hardcoded absolute paths and/or specific draw numbers "
            "with no CLI argument or environment-variable parameterization, "
            "so it cannot be re-run generically against new draws without "
            "editing source.",
            "parameterization",
            "small",
        )
    if features["uses_db_anywhere"]:
        return (
            "needs_db_safety_refactor",
            "Database access exists inside function bodies (not at module "
            "load), but no read-only/dry-run guard was detected in static "
            "scan; needs an explicit read-only mode before reuse.",
            "db_safety_refactor",
            "small",
        )
    if features["writes_files_anywhere"]:
        return (
            "needs_refactor_to_pure_function",
            "Numbers-selection logic appears entangled with file I/O inside "
            "functions; would need separating pure selection logic from "
            "output writing before reuse as a replay adapter.",
            "small_refactor",
            "small",
        )
    if is_pred is True and features["has_functions"]:
        if features["has_main_guard"]:
            return (
                "needs_adapter_wrapper",
                "Appears to implement its own numbers-selection logic in "
                "well-scoped functions with no detected module-level side "
                "effects; likely only needs a thin adapter to plug into the "
                "replay strategy registry.",
                "small_adapter",
                "small",
            )
        return (
            "needs_adapter_wrapper",
            "Appears to implement numbers-selection logic in functions but "
            "has no `if __name__` guard; needs a small wrapper/entrypoint "
            "guard plus adapter before reuse.",
            "small_adapter",
            "small",
        )
    return (
        "ambiguous_needs_cto_review",
        "Static signals were inconclusive (mixed or weak signals for "
        "prediction-method vs. utility, or unclear scope); needs a "
        "human/CTO read before classification.",
        "unknown",
        "unknown",
    )


CATEGORY_MAP = {
    # runnable_status -> (legacy_script_group category per item 8 taxonomy)
    "runnable_as_is": "candidate prediction method",
    "runnable_with_existing_adapter": "duplicate / variant",
    "needs_adapter_wrapper": "candidate prediction method",
    "needs_parameterization": "strategy experiment",
    "needs_refactor_to_pure_function": "strategy experiment",
    "needs_db_safety_refactor": "strategy experiment",
    "needs_dependency_fix": "strategy experiment",
    "needs_input_data_contract": "strategy experiment",
    "unsafe_side_effects": "one-off notebook-like script",
    "imports_db_or_runs_work_at_module_load": "one-off notebook-like script",
    "writes_db_or_files": "data ingestion / cleaning",
    "hardcoded_paths_or_dates": "one-off notebook-like script",
    "obsolete_or_deprecated": "obsolete / unsafe",
    "not_a_strategy": "statistical report",
    "broken_or_import_error": "unknown",
    "ambiguous_needs_cto_review": "unknown",
}


def recommended_action(
    runnable_status: str, duplicate_of: Optional[str], estimated_effort: str
) -> str:
    if duplicate_of:
        return "mark_duplicate"
    if runnable_status == "not_a_strategy":
        return "mark_not_strategy"
    if runnable_status == "obsolete_or_deprecated":
        return "mark_deprecated"
    if runnable_status in ("broken_or_import_error", "ambiguous_needs_cto_review"):
        return "needs_cto_review"
    if runnable_status in ("runnable_as_is", "runnable_with_existing_adapter"):
        return "include_in_replay_readiness"
    if runnable_status == "needs_adapter_wrapper" and estimated_effort == "small":
        return "include_in_replay_readiness"
    return "exclude_from_replay"


def confidence_for(features: dict, family: str, is_pred: Optional[bool]) -> str:
    if features["syntax_error"]:
        return "high"  # confident about the parse failure itself
    if is_pred is None or family == "unknown":
        return "low"
    if features["has_functions"] and family != "unknown" and is_pred is not None:
        return "medium" if is_pred is None else "high" if features["has_main_guard"] else "medium"
    return "low"


def build_record(rel_path: str, group: str) -> dict:
    abs_path = REPO_ROOT / rel_path
    content = read_source(abs_path) or ""
    features = extract_features(rel_path)

    if group in ("p541a_tools", "lottery_api_tools"):
        source_type = "tool_script"
    elif group in ("p541a_analysis",):
        source_type = "analysis_script"
    elif group == "recovered_strategies_biglotto":
        source_type = "legacy_script"
    elif group == "ai_lab":
        source_type = "legacy_script"
    elif group == "lottery_api_models":
        source_type = "adapter"
    elif group == "lottery_api_engine":
        source_type = "legacy_script"
    elif group == "root_level_scripts":
        source_type = "legacy_script"
    else:
        source_type = "unknown"

    family = score_family(rel_path, features, content)
    is_pred, pred_evidence = detect_prediction_signal(rel_path, features, content)
    duplicate_of = find_duplicate_id(content)
    runnable_status, why_not_runnable, rewrite_needed, estimated_effort = classify_runnable(
        features, family, is_pred, duplicate_of, rel_path
    )
    action = recommended_action(runnable_status, duplicate_of, estimated_effort)
    conf = confidence_for(features, family, is_pred)

    has_replay_rows: object = "unknown"
    if duplicate_of:
        if duplicate_of in REPLAYED_IDS:
            has_replay_rows = True
        elif duplicate_of in ZERO_REPLAY_IDS:
            has_replay_rows = False
        else:
            has_replay_rows = "unknown"

    evidence = []
    if features["syntax_error"]:
        evidence.append(f"syntax_error={features['syntax_error']}")
    if features["docstring"]:
        evidence.append(f"docstring[:120]={features['docstring'][:120]!r}")
    if pred_evidence:
        evidence.append(f"prediction_signal: {pred_evidence}")
    if features["function_names"]:
        evidence.append(f"functions[:8]={features['function_names'][:8]}")
    evidence.append(f"module_level_db_call={features['module_level_db_call']}")
    evidence.append(f"module_level_write_or_sideeffect={features['module_level_write'] or features['module_level_other_sideeffect']}")
    evidence.append(f"uses_db_anywhere={features['uses_db_anywhere']}")
    evidence.append(f"writes_files_anywhere={features['writes_files_anywhere']}")
    evidence.append(f"hardcoded_abs_path={features['hardcoded_abs_path']}")
    evidence.append(f"hardcoded_draw_or_date={features['hardcoded_draw_or_date']}")
    evidence.append(f"has_main_guard={features['has_main_guard']}")
    if duplicate_of:
        evidence.append(f"duplicate_id_literal_found={duplicate_of!r}")

    return {
        "method_id": rel_path,
        "normalized_name": Path(rel_path).stem,
        "source_path": rel_path,
        "discovery_group": group,
        "source_type": source_type,
        "method_family": family,
        "is_actual_prediction_method": is_pred if is_pred is not None else "unknown",
        "has_registry_entry": False,
        "has_adapter": False,
        "has_replay_rows": has_replay_rows,
        "appears_in_artifacts": group in ("p541a_tools", "p541a_analysis"),
        "duplicate_of_existing_strategy": duplicate_of,
        "runnable_status": runnable_status,
        "why_not_runnable": why_not_runnable,
        "rewrite_needed": rewrite_needed,
        "estimated_effort": estimated_effort,
        "recommended_action": action,
        "evidence": evidence,
        "confidence": conf,
        "legacy_script_group_category": CATEGORY_MAP.get(runnable_status, "unknown"),
    }


def summarize(records: list[dict]) -> dict:
    total = len(records)

    def count_where(pred):
        return sum(1 for r in records if pred(r))

    return {
        "total_methods_scripts_scanned": total,
        "actual_candidate_prediction_methods": count_where(
            lambda r: r["is_actual_prediction_method"] is True
        ),
        "replay_covered_methods_via_duplicate_match": count_where(
            lambda r: r["duplicate_of_existing_strategy"] in REPLAYED_IDS
        ),
        "code_only_methods_needs_adapter_wrapper": count_where(
            lambda r: r["runnable_status"] == "needs_adapter_wrapper"
        ),
        "non_strategy_utilities": count_where(
            lambda r: r["runnable_status"] == "not_a_strategy"
        ),
        "duplicates": count_where(lambda r: r["duplicate_of_existing_strategy"] is not None),
        "unsafe_or_not_runnable": count_where(
            lambda r: r["runnable_status"] in (
                "unsafe_side_effects",
                "imports_db_or_runs_work_at_module_load",
                "writes_db_or_files",
                "hardcoded_paths_or_dates",
                "broken_or_import_error",
            )
        ),
        "candidate_methods_for_future_replay_readiness": count_where(
            lambda r: r["recommended_action"] == "include_in_replay_readiness"
        ),
        "methods_requiring_cto_review": count_where(
            lambda r: r["recommended_action"] == "needs_cto_review"
        ),
        "obsolete_or_deprecated": count_where(
            lambda r: r["runnable_status"] == "obsolete_or_deprecated"
        ),
        "by_runnable_status": _tally(records, "runnable_status"),
        "by_method_family": _tally(records, "method_family"),
        "by_source_type": _tally(records, "source_type"),
        "by_discovery_group": _tally(records, "discovery_group"),
        "by_recommended_action": _tally(records, "recommended_action"),
        "by_confidence": _tally(records, "confidence"),
        "by_legacy_script_group_category": _tally(records, "legacy_script_group_category"),
    }


def _tally(records: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for r in records:
        v = r[key]
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def registered_zero_replay_review() -> list[dict]:
    return [
        {
            "strategy_id": sid,
            "status_in_registry": "REJECTED",
            "why_no_rows": (
                "Formally registered in lottery_api/models/replay_strategy_registry.py "
                "with status REJECTED; REJECTED strategies are excluded from "
                "replay-row generation eligibility (in_registry_generation_eligible=false "
                "per P541A inventory), so zero replay rows is expected, not a gap."
            ),
            "disposition": "rejected",
            "recommendation": (
                "Remain excluded from replay readiness; no action needed unless "
                "a future task explicitly re-evaluates the REJECTED verdict."
            ),
        }
        for sid in ZERO_REPLAY_IDS
    ]


def phantom_id_review() -> list[dict]:
    registry_content = read_source(REPO_ROOT / REGISTRY_FILE) or ""
    m = re.search(
        r"# - memory/lessons\.md L90:.*?\n.*?# - No exact callable found in codebase.*?\n",
        registry_content,
        re.DOTALL,
    )
    registry_comment_evidence = (
        m.group(0).strip() if m else "see lottery_api/models/replay_strategy_registry.py comment block near L90 reference"
    )
    return [
        {
            "id": pid,
            "referenced_in": [D3_TEST_FILE, "memory/lessons.md (L90, cited by registry comment)"],
            "why_phantom": (
                "No registry entry and no replay rows; the registry file's own "
                "source comment documents this explicitly: it cites "
                "memory/lessons.md L90 naming this id among production "
                "strategies but states 'No exact callable found in codebase' "
                "and that related ids were handled via SAFE_RECONSTRUCTION "
                "thin wrappers rather than a real implementation being found."
            ),
            "registry_comment_evidence": registry_comment_evidence,
            "recommendation": (
                "Treat as a historical/naming-drift note, not a claim of a "
                "missing implementation to build. If `ts3_regime_3bet` "
                "(the confirmed ONLINE strategy referenced alongside it in "
                "the same memory citation) is the intended real strategy, "
                "map future references to that id instead of the phantom name."
                if pid == "regime_2bet" else
                "Treat as a historical/naming-drift note only; do not "
                "delete from historical memory citations, but do not claim "
                "it as a buildable/missing implementation without further "
                "explicit code archaeology."
            ),
        }
        for pid in PHANTOM_IDS
    ]


def choose_next_task(summary: dict) -> str:
    candidates = summary["candidate_methods_for_future_replay_readiness"]
    cto_review = summary["methods_requiring_cto_review"]
    total = summary["total_methods_scripts_scanned"]
    if candidates == 0:
        return "P541B_COMPLETE_NO_REPLAYABLE_LEGACY_METHODS_FOUND"
    if cto_review > 0 and cto_review >= candidates:
        return "P541B_BLOCKED_LEGACY_METHODS_TOO_AMBIGUOUS_NEED_CTO_REVIEW"
    if candidates > 0:
        return "P541C_BIG_LOTTO_REPLAY_READINESS_FOR_RUNNABLE_LEGACY_METHODS_NO_DB_WRITE"
    return "P541C_BIG_LOTTO_LEGACY_METHOD_ADAPTER_DESIGN_NO_DB_WRITE"


def main() -> None:
    p541a = load_p541a()
    groups = discover_files(p541a)
    out_of_scope = discover_out_of_scope_summary()

    records: list[dict] = []
    for group, files in groups.items():
        for rel_path in files:
            records.append(build_record(rel_path, group))

    summary = summarize(records)
    zero_replay_review = registered_zero_replay_review()
    phantom_review = phantom_id_review()
    next_task = choose_next_task(summary)

    generated_at = datetime.now(timezone.utc).isoformat()

    output = {
        "schema_version": "1.0",
        "task_id": "P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT",
        "generated_at": generated_at,
        "summary": summary,
        "p541a_context": {
            "owner_question_answer": "PARTIAL",
            "replayed_strategy_ids": sorted(REPLAYED_IDS),
            "registered_zero_replay_ids": ZERO_REPLAY_IDS,
            "phantom_ids": PHANTOM_IDS,
            "legacy_tools_matched_by_p541a": len(groups["p541a_tools"]),
            "legacy_analysis_matched_by_p541a": len(groups["p541a_analysis"]),
            "p541a_json_path": str(P541A_JSON.relative_to(REPO_ROOT)),
            "p541a_md_path": str(P541A_MD.relative_to(REPO_ROOT)),
        },
        "inventory_sources_scanned": {
            "p541a_derived_groups": {g: len(files) for g, files in groups.items() if g.startswith("p541a_")},
            "newly_discovered_groups": {
                g: len(files) for g, files in groups.items() if not g.startswith("p541a_")
            },
            "newly_discovered_group_definitions": {
                g: globs for g, globs in EXTRA_GLOB_GROUPS
            },
            "out_of_scope_directories_grouped_not_individually_classified": out_of_scope,
            "note": (
                "P541A's static scan only searched tools/*.py and analysis/*.py "
                "(451 files total). This audit additionally discovered BIG_LOTTO-"
                "referencing legacy/candidate-method code in ai_lab/ (separate "
                "AutoML/RL/transformer/GPT research track, first committed "
                "2026-02-24, predates the P357+ lineage), "
                "recovered_strategies/biglotto/ (P357-P360 lineage, already "
                "evaluated NO_GO per project memory), root-level standalone "
                "scripts, and lottery_api/models|tools|engine/ files that were "
                "never referenced by P541A at all. These are new findings, not "
                "part of the original 451-script count."
            ),
        },
        "classification_taxonomy": {
            "source_type": [
                "registry", "adapter", "legacy_script", "tool_script",
                "analysis_script", "test", "ui_reference", "artifact_reference",
                "memory_reference", "unknown",
            ],
            "method_family": list(FAMILY_KEYWORDS) + ["unknown"],
            "runnable_status": [
                "runnable_as_is", "runnable_with_existing_adapter",
                "needs_adapter_wrapper", "needs_parameterization",
                "needs_refactor_to_pure_function", "needs_db_safety_refactor",
                "needs_dependency_fix", "needs_input_data_contract",
                "unsafe_side_effects", "imports_db_or_runs_work_at_module_load",
                "writes_db_or_files", "hardcoded_paths_or_dates",
                "obsolete_or_deprecated", "not_a_strategy",
                "broken_or_import_error", "ambiguous_needs_cto_review",
            ],
            "rewrite_needed": [
                "none", "small_adapter", "small_refactor", "db_safety_refactor",
                "parameterization", "dependency_fix", "major_rewrite",
                "deprecate", "unknown",
            ],
            "estimated_effort": ["none", "small", "medium", "large", "unknown"],
            "recommended_action": [
                "include_in_replay_readiness", "map_to_existing_strategy",
                "mark_duplicate", "mark_not_strategy", "mark_deprecated",
                "needs_cto_review", "exclude_from_replay",
            ],
            "confidence": ["high", "medium", "low"],
            "legacy_script_group_summary_categories": [
                "candidate prediction method", "strategy experiment",
                "statistical report", "data ingestion / cleaning",
                "visualization / export", "one-off notebook-like script",
                "duplicate / variant", "obsolete / unsafe", "unknown",
            ],
        },
        "method_classification_records": records,
        "legacy_script_group_summary": _tally(records, "legacy_script_group_category"),
        "registered_zero_replay_strategy_review": zero_replay_review,
        "phantom_id_review": phantom_review,
        "runnable_candidate_set": [
            r["method_id"] for r in records
            if r["recommended_action"] == "include_in_replay_readiness"
        ],
        "non_runnable_methods_and_reasons": [
            {"method_id": r["method_id"], "runnable_status": r["runnable_status"], "why_not_runnable": r["why_not_runnable"]}
            for r in records
            if r["runnable_status"] not in ("runnable_as_is", "runnable_with_existing_adapter", "needs_adapter_wrapper")
        ],
        "rewrite_or_adapter_requirements": _tally(records, "rewrite_needed"),
        "recommended_next_single_worker_task": next_task,
        "provenance_and_limits": {
            "method": (
                "Static AST parsing (ast.parse, no import/exec), regex "
                "keyword/content scoring, and git grep file discovery only. "
                "No module was imported, no script was executed, no DB "
                "connection was opened by this audit script itself."
            ),
            "p541a_artifacts_consumed": [
                str(P541A_JSON.relative_to(REPO_ROOT)),
                str(P541A_MD.relative_to(REPO_ROOT)),
            ],
            "not_performed_by_this_task": [
                "DB writes of any kind",
                "DB reads of any kind (P541A's replay coverage numbers are reused as-is, not re-queried)",
                "import/execution of any classified script",
                "replay row generation",
                "OOS evaluator runs, strategy scoring, or promotion gating",
                "recomputation or overwrite of P536-P541A artifacts",
            ],
            "known_limits": [
                "Classification is heuristic (filename/docstring/content keyword "
                "scoring plus AST structural checks); it cannot substitute for "
                "actually importing and testing a script.",
                "is_actual_prediction_method, method_family, and runnable_status "
                "should be treated as a first-pass triage signal, not a final "
                "verdict — confidence field reflects this.",
                "duplicate_of_existing_strategy only catches literal strategy_id "
                "string matches; naming-convention-similar-but-not-identical "
                "files (e.g. biglotto_2bet_final.py vs biglotto_deviation_2bet) "
                "are NOT auto-flagged as duplicates to avoid false positives.",
            ],
            "disclaimer": DISCLAIMER,
        },
        "disclaimer": DISCLAIMER,
    }
    return output


def render_md(result: dict) -> str:
    s = result["summary"]
    lines = []
    lines.append("# P541B — BIG_LOTTO Legacy / Folklore / Statistical Method Classification Audit")
    lines.append("")
    lines.append(f"> generated_at: {result['generated_at']}")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append(f"## Recommended next task: {result['recommended_next_single_worker_task']}")
    lines.append("")
    lines.append(
        f"Classified {s['total_methods_scripts_scanned']} BIG_LOTTO-referencing legacy "
        f"scripts/methods across 8 discovery groups (P541A's original 451 tools/analysis "
        f"scripts plus 5 newly-discovered groups: root-level scripts, `ai_lab/`, "
        f"`recovered_strategies/biglotto/`, and `lottery_api/models|tools|engine/`). "
        f"{s['actual_candidate_prediction_methods']} show static signals of implementing "
        f"their own numbers-selection logic; {s['candidate_methods_for_future_replay_readiness']} "
        f"are classified `include_in_replay_readiness` (clean enough for a small adapter); "
        f"{s['methods_requiring_cto_review']} are too ambiguous for static classification "
        f"alone and need a human/CTO read; {s['duplicates']} contain a literal strategy_id "
        f"string matching an already-registered strategy."
    )
    lines.append("")
    lines.append("## Summary counts")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---|")
    for k in [
        "total_methods_scripts_scanned", "actual_candidate_prediction_methods",
        "replay_covered_methods_via_duplicate_match", "code_only_methods_needs_adapter_wrapper",
        "non_strategy_utilities", "duplicates", "unsafe_or_not_runnable",
        "candidate_methods_for_future_replay_readiness", "methods_requiring_cto_review",
        "obsolete_or_deprecated",
    ]:
        lines.append(f"| {k} | {s[k]} |")
    lines.append("")
    lines.append("## Discovery groups scanned")
    lines.append("")
    lines.append("| group | count | note |")
    lines.append("|---|---|---|")
    dg = result["inventory_sources_scanned"]
    for g, n in dg["p541a_derived_groups"].items():
        lines.append(f"| {g} | {n} | from P541A artifact (tools/*.py, analysis/*.py) |")
    for g, n in dg["newly_discovered_groups"].items():
        lines.append(f"| {g} | {n} | new discovery, not in P541A's original scan |")
    lines.append("")
    lines.append("## by_runnable_status")
    lines.append("")
    lines.append("| runnable_status | count |")
    lines.append("|---|---|")
    for k, v in s["by_runnable_status"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## by_method_family")
    lines.append("")
    lines.append("| method_family | count |")
    lines.append("|---|---|")
    for k, v in s["by_method_family"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## legacy_script_group_summary (item-8 taxonomy)")
    lines.append("")
    lines.append("| category | count |")
    lines.append("|---|---|")
    for k, v in result["legacy_script_group_summary"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Registered zero-replay strategy review")
    lines.append("")
    for item in result["registered_zero_replay_strategy_review"]:
        lines.append(f"- **{item['strategy_id']}** ({item['status_in_registry']}): {item['why_no_rows']}")
    lines.append("")
    lines.append("## Phantom id review")
    lines.append("")
    for item in result["phantom_id_review"]:
        lines.append(f"- **{item['id']}**: {item['why_phantom']}")
        lines.append(f"  - Recommendation: {item['recommendation']}")
    lines.append("")
    lines.append("## Runnable candidate set (future replay readiness)")
    lines.append("")
    cands = result["runnable_candidate_set"]
    lines.append(f"{len(cands)} method(s) classified `include_in_replay_readiness`:")
    lines.append("")
    for c in cands:
        lines.append(f"- `{c}`")
    lines.append("")
    lines.append("## Out-of-scope directories (grouped, not individually classified)")
    lines.append("")
    oos = dg["out_of_scope_directories_grouped_not_individually_classified"]
    lines.append("| directory | count | reason |")
    lines.append("|---|---|---|")
    for k, v in oos.items():
        reason = " ".join(v["reason"].split())
        lines.append(f"| {k} | {v['count']} | {reason} |")
    lines.append("")
    lines.append("## Provenance and limits")
    lines.append("")
    prov = result["provenance_and_limits"]
    lines.append(prov["method"])
    lines.append("")
    lines.append("Not performed by this task:")
    for item in prov["not_performed_by_this_task"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Known limits:")
    for item in prov["known_limits"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"*{DISCLAIMER}*")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    result = main()
    out_json = REPO_ROOT / f"outputs/research/p541b_biglotto_legacy_method_classification_audit_{DATE_TAG}.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_json} ({out_json.stat().st_size} bytes)")

    out_md = REPO_ROOT / f"outputs/research/p541b_biglotto_legacy_method_classification_audit_{DATE_TAG}.md"
    out_md.write_text(render_md(result), encoding="utf-8")
    print(f"Wrote {out_md} ({out_md.stat().st_size} bytes)")
