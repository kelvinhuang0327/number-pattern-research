"""P541D_R2 deterministic, static-only adapter design for five BIG_LOTTO methods.

The selected legacy modules are read exclusively as blobs from the pinned Git
commit.  They are never imported or executed.  This module opens no DB, CSV,
runtime state, network resource, or environment-derived path.  ``main()`` writes
only the two authorized P541D_R2 research artifacts.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Optional, Union


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "9572d994e94fae44cf7730297e7537c0901d5a78"
TASK_ID = "P541D_R2_BIG_LOTTO_SELECTED_METHOD_ADAPTER_DESIGN_NO_DB_WRITE"
SCHEMA_VERSION = "p541d-r2-adapter-design-v1"
DESIGNER_VERSION = "p541d-r2-designer-v1"
GENERATED_AT = "2026-07-13T00:00:00+00:00"

UPSTREAM_PATH = (
    "outputs/research/"
    "p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.json"
)
UPSTREAM_IDENTITY = {
    "path": UPSTREAM_PATH,
    "byte_size": 1_401_576,
    "sha256": "f470b3c9da81fcb66ed5b0d60bc88c97bd8e51467a5e6e02dfd03cfb5ada013d",
    "schema_version": "p541c-r2-selection-v3",
    "selector_version": "p541c-r2-selector-v4",
    "record_count": 580,
}

SELECTED_PATHS = [
    "tools/advanced_prediction_engine.py",
    "lottery_api/models/social_wisdom_predictor.py",
    "tools/quick_ml_predict.py",
    "tools/big_lotto_exhaustive_audit.py",
    "lottery_api/models/zone_split.py",
]

ADAPTER_REFERENCE_PATHS = [
    "lottery_api/models/replay_strategy_registry.py",
    "lottery_api/models/p42_wave3_biglotto_adapters.py",
    "lottery_api/models/p93_tierb_replay_adapters.py",
]

JSON_OUTPUT = (
    REPO_ROOT
    / "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.json"
)
MARKDOWN_OUTPUT = (
    REPO_ROOT
    / "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.md"
)

DISCLAIMER = (
    "Static adapter-design research only; not a runtime adapter, replay result, "
    "production-readiness claim, prediction, betting edge, or betting advice. "
    "Lottery outcomes remain random; this material is for research and entertainment only."
)

ALLOWED_STATUSES = {
    "LAZY_DIRECT_WRAPPER_READY",
    "ADAPTER_OWNED_PURE_EXTRACTION_READY",
    "DETERMINISTIC_REIMPLEMENTATION_READY",
    "CTO_REVIEW_REQUIRED",
    "NOT_AN_ADAPTER_CANDIDATE",
}
READY_STATUSES = {
    "LAZY_DIRECT_WRAPPER_READY",
    "ADAPTER_OWNED_PURE_EXTRACTION_READY",
    "DETERMINISTIC_REIMPLEMENTATION_READY",
}
ALLOWED_EQUIVALENT_RESULTS = {
    "NO_EXISTING_EQUIVALENT",
    "EXISTING_EQUIVALENT_REUSE",
    "EXISTING_PARTIAL_EQUIVALENT",
    "POSSIBLE_DUPLICATE_CTO_REVIEW",
    "UNKNOWN",
}


class P541DR2ValidationError(ValueError):
    """Raised when a pinned identity or design contract fails closed."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise P541DR2ValidationError("packet is not finite JSON") from exc


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P541DR2ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_load_bytes(raw: bytes, source: str = "<git-blob>") -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P541DR2ValidationError(f"invalid UTF-8 JSON: {source}") from exc

    def reject_constant(value: str) -> None:
        raise P541DR2ValidationError(f"non-finite JSON constant: {value}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise P541DR2ValidationError(f"invalid strict JSON: {source}") from exc
    if not isinstance(value, dict):
        raise P541DR2ValidationError(f"top-level object required: {source}")
    return value


def _git(repo_root: Path, *args: str) -> bytes:
    command = ["git", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P541DR2ValidationError(f"read-only Git command failed: {args!r}") from exc
    return completed.stdout


def git_blob_bytes(repo_root: Path, path: str) -> bytes:
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise P541DR2ValidationError(f"unsafe Git path: {path}")
    return _git(repo_root, "show", f"{BASE_COMMIT}:{path}")


def git_blob_sha(repo_root: Path, path: str) -> str:
    return _git(repo_root, "rev-parse", f"{BASE_COMMIT}:{path}").decode("ascii").strip()


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _signature(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
    args: list[str] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f" = {ast.unparse(default)}"
        args.append(text)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        args.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f" = {ast.unparse(default)}"
        args.append(text)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"{node.name}({', '.join(args)}){returns}"


def _imports(tree: ast.Module) -> tuple[list[str], list[str]]:
    all_imports: set[str] = set()
    optional: set[str] = set()
    optional_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            handler.type is None
            or (isinstance(handler.type, ast.Name) and handler.type.id == "ImportError")
            for handler in node.handlers
        ):
            for child in node.body:
                for nested in ast.walk(child):
                    if isinstance(nested, (ast.Import, ast.ImportFrom)):
                        optional_nodes.add(id(nested))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if name:
                all_imports.add(name)
                if id(node) in optional_nodes:
                    optional.add(name)
    return sorted(all_imports), sorted(optional)


def _call_names(tree: ast.Module) -> list[str]:
    return sorted(
        {
            _dotted_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _dotted_name(node.func)
        }
    )


def _top_level_executable(tree: ast.Module) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, "value", None)
            if value is None or isinstance(value, (ast.Constant, ast.Dict, ast.List, ast.Tuple, ast.Set)):
                continue
        result.append({"node": type(node).__name__, "line": getattr(node, "lineno", None)})
    return result


SOURCE_SEMANTICS = {
    "tools/advanced_prediction_engine.py": {
        "input_shape": "AdvancedLotteryPredictor.data DataFrame with chronological numbers_list rows",
        "output_shape": "dict containing numbers, probabilities, method and confidence",
        "causal_history_requirements": "tail windows imply oldest-to-newest history; mode identity is unresolved",
    },
    "lottery_api/models/social_wisdom_predictor.py": {
        "input_shape": "list[dict] with numbers; source consumes history[:50] as most-recent-first",
        "output_shape": "sorted list[int] of pick_count numbers for predict()",
        "causal_history_requirements": "adapter must reverse canonical oldest-to-newest tail(50) before predict()",
    },
    "tools/quick_ml_predict.py": {
        "input_shape": "constructor CSV DataFrame with numbers column, newest rows first",
        "output_shape": "dict containing numbers, method, confidence, top_probabilities and details",
        "causal_history_requirements": "future extraction must accept in-memory tail(50), normalized newest-first",
    },
    "tools/big_lotto_exhaustive_audit.py": {
        "input_shape": "CSV-backed full draw history plus window and num_bets",
        "output_shape": "aggregate (hit_rate, roi, periods), not a one-draw bet",
        "causal_history_requirements": "run_audit observes each target outcome after randomized bet construction",
    },
    "lottery_api/models/zone_split.py": {
        "input_shape": "lottery_type and num_bets; no historical signal in legacy callable",
        "output_shape": "dict with multiple bets and coverage metadata",
        "causal_history_requirements": "future local RNG seed must bind strategy identity to strictly prior history",
    },
}


def source_manifest_record(repo_root: Path, path: str) -> dict[str, Any]:
    raw = git_blob_bytes(repo_root, path)
    try:
        text = raw.decode("utf-8", errors="strict")
        utf8 = "PASS"
    except UnicodeDecodeError as exc:
        raise P541DR2ValidationError(f"selected source is not UTF-8: {path}") from exc
    try:
        tree = ast.parse(text, filename=path)
        ast_result = "PASS"
    except SyntaxError as exc:
        raise P541DR2ValidationError(f"selected source does not parse: {path}") from exc
    imports, optional = _imports(tree)
    calls = _call_names(tree)
    classes: list[dict[str, Any]] = []
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_signature(node))
        elif isinstance(node, ast.ClassDef):
            classes.append(
                {
                    "name": node.name,
                    "methods": [
                        _signature(child)
                        for child in node.body
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                }
            )
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    file_refs = sorted(
        value
        for value in string_literals
        if any(token in value.lower() for token in (".csv", ".db", "data/", "../data"))
    )
    broad_handlers = [
        {
            "line": node.lineno,
            "type": "bare" if node.type is None else ast.unparse(node.type),
        }
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"})
        )
    ]
    main_guard = any(
        isinstance(node, ast.If)
        and "__name__" in ast.unparse(node.test)
        and "__main__" in ast.unparse(node.test)
        for node in tree.body
    )
    return {
        "source_path": path,
        "git_blob_sha": git_blob_sha(repo_root, path),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "utf8_parse": utf8,
        "ast_parse": ast_result,
        "imports": imports,
        "optional_dependencies": optional,
        "top_level_executable_statements": _top_level_executable(tree),
        "classes": classes,
        "functions": functions,
        "input_shape": SOURCE_SEMANTICS[path]["input_shape"],
        "output_shape": SOURCE_SEMANTICS[path]["output_shape"],
        "external_references": {
            "file_literals": file_refs,
            "db_calls": [name for name in calls if "sqlite" in name.lower() or "database" in name.lower()],
            "network_calls": [name for name in calls if any(x in name.lower() for x in ("request", "urlopen", "http"))],
            "environment_calls": [name for name in calls if "getenv" in name.lower() or "environ" in name.lower()],
        },
        "randomness_calls": [name for name in calls if "random" in name.lower()],
        "print_log_side_effect_calls": [
            name for name in calls if name == "print" or name.startswith("logging.") or name.startswith("logger.")
        ],
        "broad_exception_handlers": broad_handlers,
        "main_guard": main_guard,
        "causal_history_requirements": SOURCE_SEMANTICS[path]["causal_history_requirements"],
    }


def _adapter_reference(repo_root: Path, path: str) -> dict[str, Any]:
    raw = git_blob_bytes(repo_root, path)
    symbols: list[str]
    if path.endswith("replay_strategy_registry.py"):
        symbols = [
            "ReplayStrategyAdapter",
            "_StrategyMeta",
            "_validate_numbers",
            "RejectPrediction",
            "InsufficientHistory",
            "InvalidOutput",
            "UnsupportedLotteryType",
        ]
    elif path.endswith("p42_wave3_biglotto_adapters.py"):
        symbols = ["strictly-prior history", "one recorded bet", "BIG_LOTTO 1..49 validation"]
    else:
        symbols = ["canonical primitive reuse", "lazy strategy imports", "first-bet normalization"]
    return {
        "path": path,
        "git_blob_sha": git_blob_sha(repo_root, path),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "reused_contract": symbols,
    }


def _p541c_provenance(shortlist: list[dict[str, Any]], path: str) -> dict[str, Any]:
    record = next(item for item in shortlist if item.get("source_path") == path)
    return {
        "method_id": record["method_id"],
        "source_path": record["source_path"],
        "method_family": record["method_family"],
        "p541c_r2_bucket": record["p541c_r2_bucket"],
        "risk_level": record["p541b_r2_status"]["risk_level"],
        "low_risk_eligible": record["p541b_r2_status"]["low_risk_eligible"],
        "identity_confirmed": record["historical_p541b_status"]["is_actual_prediction_method"],
        "confidence": record["historical_p541b_status"]["confidence"],
        "required_change_before_replay": record["required_change_before_replay"],
    }


def _common_design(
    path: str,
    provenance: dict[str, Any],
    equivalent_result: str,
    equivalent_evidence: list[dict[str, str]],
    status: str,
    rationale: str,
    strategy_id: Optional[str],
    strategy_name: Optional[str],
    selected_entrypoint: Optional[str],
    legacy_entrypoints: list[str],
    min_history: Optional[int],
    history_ordering: str,
    required_fields: list[str],
    randomness: dict[str, Any],
    external_state: dict[str, Any],
    import_plan: str,
    normalization: dict[str, Any],
    exception_mapping: dict[str, str],
    parity_oracle: dict[str, Any],
    synthetic_vectors: list[dict[str, Any]],
    future_files: list[str],
    blockers: list[str],
    readiness_gates: dict[str, bool],
) -> dict[str, Any]:
    ready = status in READY_STATUSES
    return {
        "method_id": path,
        "source_path": path,
        "p541c_provenance": provenance,
        "legacy_entrypoints": legacy_entrypoints,
        "selected_entrypoint": selected_entrypoint,
        "equivalent_audit": {
            "result": equivalent_result,
            "evidence": equivalent_evidence,
            "distinct_identity_proven": equivalent_result
            not in {"POSSIBLE_DUPLICATE_CTO_REVIEW", "UNKNOWN"},
        },
        "design_status": status,
        "design_rationale": rationale,
        "proposed_strategy": {
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "strategy_version": "v0.1-design" if strategy_id else None,
            "lifecycle": "DEFERRED_NOT_REGISTERED" if strategy_id else "NOT_PROPOSED",
            "supported_lottery_types": ["BIG_LOTTO"] if strategy_id else [],
        },
        "minimum_history": min_history,
        "history_ordering": history_ordering,
        "causal_cutoff": "Every input draw must be strictly before the target draw; reject equal/future rows.",
        "required_history_fields": required_fields,
        "special_number_behavior": "Return None; BIG_LOTTO special number is not predicted by replay v0.1.",
        "randomness_and_seed_contract": randomness,
        "external_state_and_dependencies": external_state,
        "import_safety_plan": import_plan,
        "input_output_normalization": normalization,
        "six_number_validation": (
            "Pass the flat result to repository-native _validate_numbers(numbers, "
            "'BIG_LOTTO', strategy_id): exactly six distinct integers in [1,49], sorted."
        ),
        "exception_mapping": exception_mapping,
        "rejection_and_insufficient_history": {
            "insufficient_history": "Raise InsufficientHistory before strategy logic.",
            "deliberate_no_bet": "Raise RejectPrediction with a stable reason.",
            "malformed_result": "Raise InvalidOutput; do not fabricate or repair a ticket.",
        },
        "parity_oracle": parity_oracle,
        "synthetic_vectors": synthetic_vectors,
        "no_db_proof_obligations": [
            "Prediction receives the complete causal history as an argument.",
            "No DB, file, CSV, environment, network or runtime-state read is reachable during prediction.",
            "No selected legacy module is imported unless the approved plan explicitly permits a lazy safe import.",
            "One and only one validated bet is returned for a strategy/draw pair.",
        ],
        "future_implementation_files": future_files,
        "deferred_registry_lifecycle_changes": [
            "No registry entry in this task or implied by this design.",
            "Lifecycle assignment, replay generation, promotion and ONLINE status require separate authorization.",
        ],
        "blockers_and_cto_decisions": blockers,
        "readiness_gates": readiness_gates,
        "ready_for_implementation": ready,
        "disclaimer": DISCLAIMER,
    }


def build_method_designs(shortlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance = {path: _p541c_provenance(shortlist, path) for path in SELECTED_PATHS}
    common_exceptions = {
        "unsupported lottery": "UnsupportedLotteryType",
        "history shorter than minimum": "InsufficientHistory",
        "intentional no-bet": "RejectPrediction",
        "shape/range/duplicate/type failure": "InvalidOutput",
        "unexpected failure": "propagate for caller mapping to REPLAY_ERROR",
    }
    return [
        _common_design(
            SELECTED_PATHS[0], provenance[SELECTED_PATHS[0]],
            "EXISTING_PARTIAL_EQUIVALENT",
            [
                {"path": "tools/quick_ml_predict.py", "finding": "overlapping frequency/hot-cold/statistical features, not exact engine identity"},
                {"path": "lottery_api/models/p42_wave3_biglotto_adapters.py", "finding": "native deterministic scoring precedent, not an equivalent adapter"},
            ],
            "CTO_REVIEW_REQUIRED",
            "The file exposes five predict_next_draw modes. Default ensemble behavior changes with optional sklearn/XGBoost availability, imports print warnings, and an untrained ensemble silently falls back to statistical mode. P541C selected only the file identity, so choosing one mode would invent the selected identity.",
            None, None, None,
            [
                "AdvancedLotteryPredictor.predict_next_draw(method='ensemble')",
                "AdvancedLotteryPredictor._predict_frequency",
                "AdvancedLotteryPredictor._predict_hot_cold_hybrid",
                "AdvancedLotteryPredictor._predict_pattern_matching",
                "AdvancedLotteryPredictor._predict_statistical",
            ],
            None,
            "Unresolved: statistical paths use oldest-to-newest DataFrame tail windows; P541C does not select a mode.",
            ["draw", "date", "numbers"],
            {"present": True, "deterministic": False, "contract": "ML model seeds are fixed at 42, but dependency-conditional mode selection remains unresolved."},
            {"prediction_reads": ["in-memory history"], "forbidden_legacy_reads": ["CSV load_data"], "dependencies": ["pandas", "numpy", "optional sklearn", "optional xgboost"]},
            "Do not import the source. CTO must select a single identity; then prefer adapter-owned pure extraction or explicitly approve a dependency-pinned implementation.",
            {"input": "unresolved until mode selection", "output": "one flat six-number list after selection"},
            common_exceptions,
            {"type": "blocked", "requirement": "CTO must pin the exact mode and optional-dependency semantics before parity can be defined."},
            [{"id": "advanced-mode-boundary", "input": "same 50 causal draws under ML-present and ML-absent environments", "expected": "mode-independent output is required before READY; currently unresolved"}],
            [],
            ["Select exactly one legacy prediction identity.", "Decide whether sklearn/XGBoost availability is part of identity or prohibited."],
            {"causality_resolved": False, "randomness_resolved": False, "external_state_resolved": False, "identity_distinct": True},
        ),
        _common_design(
            SELECTED_PATHS[1], provenance[SELECTED_PATHS[1]],
            "EXISTING_EQUIVALENT_REUSE",
            [{"path": "lottery_api/models/unified_predictor.py", "finding": "social_wisdom_predict delegates to SocialWisdomPredictor.predict; reuse the selected pure callable, not the facade's logging/special-number work"}],
            "LAZY_DIRECT_WRAPPER_READY",
            "SocialWisdomPredictor.predict is import-safe, deterministic and already accepts in-memory history. The random generate_8_bets and empty-history random branch of predict_with_balance are explicitly excluded.",
            "biglotto_social_wisdom_anti_popularity",
            "大樂透 Social Wisdom Anti-Popularity",
            "SocialWisdomPredictor.predict(history, pick_count=6)",
            ["SocialWisdomPredictor.predict", "UnifiedPredictor.social_wisdom_predict"],
            1,
            "Canonical replay supplies oldest-to-newest; wrapper passes reversed(history[-50:]) because the legacy callable treats history[:50] as newest-first.",
            ["draw", "date", "numbers"],
            {"present": False, "deterministic": True, "contract": "Use predict() only; never call predict_with_balance(empty history) or generate_8_bets()."},
            {"prediction_reads": ["in-memory history"], "forbidden_legacy_reads": [], "dependencies": ["numpy"]},
            "Lazy-import only SocialWisdomPredictor inside _call_strategy; module has no import-time executable output or I/O.",
            {"input": "copy strictly-prior history, keep last 50, reverse to newest-first", "output": "the returned sorted list[int]; ignore facade confidence/meta/special"},
            common_exceptions,
            {"type": "direct-call parity", "callable": "SocialWisdomPredictor(max_num=49).predict(newest_first_history, pick_count=6)", "comparison": "exact six-number equality"},
            [{"id": "social-repeated-high", "input": "50 newest-first draws each [32,33,34,35,41,49]", "expected_numbers": [32, 33, 34, 35, 41, 49]}],
            ["lottery_api/models/p541d_r2_biglotto_selected_adapters.py", "tests/test_p541d_r2_biglotto_selected_adapters.py"],
            [],
            {"causality_resolved": True, "randomness_resolved": True, "external_state_resolved": True, "identity_distinct": True},
        ),
        _common_design(
            SELECTED_PATHS[2], provenance[SELECTED_PATHS[2]],
            "EXISTING_PARTIAL_EQUIVALENT",
            [{"path": "tools/advanced_prediction_engine.py", "finding": "overlapping statistical features but not the same ten-weight QuickML formula"}],
            "ADAPTER_OWNED_PURE_EXTRACTION_READY",
            "The constructor's CSV read and printing cannot enter replay. The selected deterministic predict_advanced_ensemble formula can be extracted unchanged to a pure in-memory helper, including newest-first ordering and stable numeric tie order.",
            "biglotto_quickml_advanced_ensemble",
            "大樂透 QuickML Advanced Ensemble",
            "adapter-owned pure extraction of QuickMLPredictor.predict_advanced_ensemble(top_n=10)",
            ["QuickMLPredictor.__init__", "QuickMLPredictor.predict_advanced_ensemble", "QuickMLPredictor.predict_smart_hybrid"],
            50,
            "Canonical oldest-to-newest history is truncated to the last 50 then reversed; this preserves legacy DataFrame.head() newest-first semantics.",
            ["draw", "date", "numbers"],
            {"present": False, "deterministic": True, "contract": "predict_advanced_ensemble contains no random call; preserve ascending number tie-breaks."},
            {"prediction_reads": ["in-memory history"], "forbidden_legacy_reads": ["pd.read_csv in constructor", "temporary CSV"], "dependencies": ["stdlib-only extraction preferred"]},
            "Never import or construct QuickMLPredictor in replay. Extract the selected scoring formula into the future adapter module with source/blob provenance comments.",
            {"input": "list[dict] -> newest-first list[list[int]] without pandas or CSV", "output": "take ranked top six, sorted; discard confidence/top_n metadata"},
            common_exceptions,
            {"type": "controlled legacy oracle", "callable": "QuickMLPredictor.predict_advanced_ensemble", "comparison": "future isolated parity test only, with in-memory-vs-legacy fixture conversion outside prediction; never a runtime temp CSV"},
            [{"id": "quickml-repeated-low", "input": "50 newest-first draws each [1,2,3,4,5,6]", "expected_numbers": [1, 2, 3, 4, 5, 6]}],
            ["lottery_api/models/p541d_r2_biglotto_selected_adapters.py", "tests/test_p541d_r2_biglotto_selected_adapters.py"],
            [],
            {"causality_resolved": True, "randomness_resolved": True, "external_state_resolved": True, "identity_distinct": True},
        ),
        _common_design(
            SELECTED_PATHS[3], provenance[SELECTED_PATHS[3]],
            "NO_EXISTING_EQUIVALENT",
            [{"path": "tools/big_lotto_exhaustive_audit.py", "finding": "only the batch auditor identity was found; no genuine one-draw callable or adapter exists"}],
            "NOT_AN_ADAPTER_CANDIDATE",
            "BigLottoAuditor.run_audit is an outcome-aware multi-period evaluator. It reads CSV in the constructor, silently substitutes synthetic random history on every exception, samples multiple random bets, observes the actual draw, and returns aggregate hit-rate/ROI rather than a ticket.",
            None, None, None,
            ["BigLottoAuditor.__init__", "BigLottoAuditor.run_audit", "get_hits", "calculate_payout"],
            None,
            "run_audit internally slices prior rows, then consumes the current outcome; it is not a target-time predictor contract.",
            ["historical outcomes including target draw"],
            {"present": True, "deterministic": False, "contract": "global random.sample and synthetic fallback are prohibited; no seed can convert an evaluator into a predictor identity."},
            {"prediction_reads": ["CSV", "actual draw"], "forbidden_legacy_reads": ["CSV", "synthetic fallback", "outcome"], "dependencies": ["pandas", "numpy", "random"]},
            "Never import or wrap. A future task may separately design a new hot/cold predictor, but it must not claim BigLottoAuditor identity.",
            {"input": "not normalizable to a one-draw predictor without invention", "output": "aggregate metrics; no valid one-bet extraction"},
            common_exceptions,
            {"type": "not applicable", "requirement": "No parity oracle exists for a one-bet adapter because the source has no one-bet output."},
            [{"id": "auditor-fail-closed", "input": "missing CSV or any 50-draw window", "expected": "reject adapter candidacy; never invoke synthetic fallback or random audit"}],
            [],
            ["Rejected as adapter candidate. Any new predictor requires a separately named strategy and CTO approval."],
            {"causality_resolved": False, "randomness_resolved": False, "external_state_resolved": False, "identity_distinct": True},
        ),
        _common_design(
            SELECTED_PATHS[4], provenance[SELECTED_PATHS[4]],
            "EXISTING_PARTIAL_EQUIVALENT",
            [
                {"path": "tools/zone_split_optimizer.py", "finding": "multiple zone variants exist, but their pools/weighting differ from ZoneSplitStrategy.generate_bets"},
                {"path": "src/engine/strategies/ZoneSplitStrategy.js", "finding": "front-end zone strategy is a separate implementation surface, not a ReplayStrategyAdapter"},
                {"path": "lottery_api/routes/prediction.py", "finding": "runtime route calls the exact selected factory; no replay adapter exists"},
            ],
            "DETERMINISTIC_REIMPLEMENTATION_READY",
            "Preserve the exact three-zone boundaries, overlap=2 and first-bet selection, but replace global random.sample with a local random.Random instance seeded from canonical strategy identity plus strictly-prior causal history. No historical signal or equivalent strategy is borrowed.",
            "biglotto_zone_split_3bet_bet1",
            "大樂透 Zone Split 3注（Replay Bet 1）",
            "deterministic reimplementation of get_zone_split_predictor('BIG_LOTTO', 3), first bet only",
            ["ZoneSplitStrategy.generate_bets", "ZoneSplitStrategy.get_coverage_meta", "get_zone_split_predictor"],
            1,
            "Canonical oldest-to-newest history is retained only for seed material; all rows must be strictly prior and canonicalized by draw/date/numbers.",
            ["draw", "date", "numbers"],
            {
                "present": True,
                "deterministic": True,
                "contract": "Build UTF-8 canonical JSON of {strategy_id, lottery_type, causal_history:[{draw,date,numbers}]}; SHA-256 it; seed local random.Random with the full digest integer; sample each legacy zone sequentially; record bet 1 only. Never seed or call global RNG.",
            },
            {"prediction_reads": ["in-memory causal history for seed only"], "forbidden_legacy_reads": [], "dependencies": ["stdlib hashlib", "stdlib json", "stdlib random.Random"]},
            "Do not import the selected module because it uses global random. Reimplement only its 1..49, three-zone, overlap=2 candidate-pool construction in the future adapter.",
            {"input": "canonical history used only in deterministic seed preimage", "output": "first of three sequential local-RNG bets; validate and discard other bets/coverage metadata"},
            common_exceptions,
            {"type": "algorithm parity", "callable": "legacy zone boundary/pool construction", "comparison": "same pools and sample count; deterministic seed intentionally replaces nondeterministic global RNG"},
            [{"id": "zone-single-draw", "input": "one prior draw {draw:'1',date:'2026-01-01',numbers:[1,2,3,4,5,6]}", "expected": "identical output across processes; six distinct values from first zone pool [1,18]"}],
            ["lottery_api/models/p541d_r2_biglotto_selected_adapters.py", "tests/test_p541d_r2_biglotto_selected_adapters.py"],
            [],
            {"causality_resolved": True, "randomness_resolved": True, "external_state_resolved": True, "identity_distinct": True},
        ),
    ]


def validate_upstream(upstream: dict[str, Any]) -> list[dict[str, Any]]:
    if upstream.get("schema_version") != UPSTREAM_IDENTITY["schema_version"]:
        raise P541DR2ValidationError("P541C_R2 schema mismatch")
    if upstream.get("selector_version") != UPSTREAM_IDENTITY["selector_version"]:
        raise P541DR2ValidationError("P541C_R2 selector mismatch")
    records = upstream.get("reviewed_method_decisions")
    if not isinstance(records, list) or len(records) != UPSTREAM_IDENTITY["record_count"]:
        raise P541DR2ValidationError("P541C_R2 must contain exactly 580 reviewed records")
    shortlist = upstream.get("high_priority_candidate_shortlist")
    if not isinstance(shortlist, list) or [x.get("source_path") for x in shortlist] != SELECTED_PATHS:
        raise P541DR2ValidationError("P541C_R2 exact shortlist/order mismatch")
    for record in shortlist:
        if record.get("p541c_r2_bucket") != "needs_adapter_before_readiness":
            raise P541DR2ValidationError("shortlist bucket mismatch")
        safety = record.get("p541b_r2_status", {})
        history = record.get("historical_p541b_status", {})
        if safety.get("risk_level") != "low" or safety.get("low_risk_eligible") is not True:
            raise P541DR2ValidationError("shortlist low-risk gate failed")
        if history.get("is_actual_prediction_method") is not True or history.get("confidence") != "high":
            raise P541DR2ValidationError("shortlist identity/confidence gate failed")
    return shortlist


def _load_upstream(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = git_blob_bytes(repo_root, UPSTREAM_PATH)
    actual = {"byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if actual["byte_size"] != UPSTREAM_IDENTITY["byte_size"] or actual["sha256"] != UPSTREAM_IDENTITY["sha256"]:
        raise P541DR2ValidationError("pinned P541C_R2 byte identity mismatch")
    upstream = strict_json_load_bytes(raw, UPSTREAM_PATH)
    validate_upstream(upstream)
    return upstream, {**UPSTREAM_IDENTITY, **actual, "verification": "PASS", "read_mechanism": "pinned Git blob"}


def build_packet(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    upstream, upstream_identity = _load_upstream(repo_root)
    shortlist = validate_upstream(upstream)
    manifests = [source_manifest_record(repo_root, path) for path in SELECTED_PATHS]
    adapter_refs = [_adapter_reference(repo_root, path) for path in ADAPTER_REFERENCE_PATHS]
    designs = build_method_designs(shortlist)
    ready = [d["method_id"] for d in designs if d["ready_for_implementation"]]
    cto = [d["method_id"] for d in designs if d["design_status"] == "CTO_REVIEW_REQUIRED"]
    rejected = [d["method_id"] for d in designs if d["design_status"] == "NOT_AN_ADAPTER_CANDIDATE"]
    counts = {status: sum(d["design_status"] == status for d in designs) for status in sorted(ALLOWED_STATUSES)}
    packet = {
        "schema_version": SCHEMA_VERSION,
        "designer_version": DESIGNER_VERSION,
        "task": {
            "task_id": TASK_ID,
            "generated_at": GENERATED_AT,
            "scope": "static no-DB adapter design for exactly five selected BIG_LOTTO methods",
            "design_only": True,
        },
        "base": {"commit": BASE_COMMIT, "branch": "main"},
        "upstream_identity": upstream_identity,
        "canonical_adapter_references": adapter_refs,
        "selected_source_manifest": manifests,
        "method_designs": designs,
        "summary": {
            "selected_methods": len(designs),
            "counts_by_status": counts,
            "implementation_ready_count": len(ready),
            "cto_review_count": len(cto),
            "rejected_count": len(rejected),
        },
        "projections": {
            "implementation_ready": ready,
            "cto_review": cto,
            "rejected": rejected,
        },
        "shared_future_adapter_primitives": {
            "base": "ReplayStrategyAdapter",
            "metadata": "_StrategyMeta",
            "validation": "_validate_numbers",
            "exceptions": ["RejectPrediction", "InsufficientHistory", "InvalidOutput", "UnsupportedLotteryType"],
            "contract": [
                "strictly-prior causal history",
                "no DB/file/env/network reads during prediction",
                "six distinct integers in [1,49]",
                "one recorded bet per strategy/draw",
                "explicit rejection/insufficient-history/invalid-output/error mapping",
                "no ONLINE or production lifecycle implication",
            ],
        },
        "implementation_sequencing": [
            {"wave": 1, "methods": [SELECTED_PATHS[1]], "reason": "safe lazy direct reuse"},
            {"wave": 2, "methods": [SELECTED_PATHS[2]], "reason": "pure in-memory extraction and parity vectors"},
            {"wave": 3, "methods": [SELECTED_PATHS[4]], "reason": "local deterministic RNG reimplementation"},
            {"wave": "CTO", "methods": [SELECTED_PATHS[0]], "reason": "select exact mode/dependency identity"},
            {"wave": "REJECTED", "methods": [SELECTED_PATHS[3]], "reason": "outcome-aware audit is not a predictor"},
        ],
        "no_db_no_execution_evidence": {
            "source_read_mechanism": "git show <base>:<relative-path>",
            "selected_modules_imported": False,
            "selected_modules_executed": False,
            "db_access": "NONE",
            "data_runtime_access": "NONE",
            "network_access": "NONE",
            "environment_access": "NONE",
            "writes": [
                "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.json",
                "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.md",
            ],
        },
        "limits": [
            "Static design does not prove future implementation parity.",
            "No adapter, registry, lifecycle, replay row, DB state or target runtime was created or observed.",
            "Equivalent audit is pinned to Git objects at the authoritative base.",
        ],
        "disclaimer": DISCLAIMER,
    }
    validate_packet(packet)
    return packet


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return duplicate


def validate_packet(packet: dict[str, Any]) -> None:
    if packet.get("schema_version") != SCHEMA_VERSION or packet.get("designer_version") != DESIGNER_VERSION:
        raise P541DR2ValidationError("schema/designer mismatch")
    designs = packet.get("method_designs")
    manifests = packet.get("selected_source_manifest")
    if not isinstance(designs, list) or not isinstance(manifests, list):
        raise P541DR2ValidationError("design and manifest lists required")
    paths = [item.get("source_path") for item in designs]
    method_ids = [item.get("method_id") for item in designs]
    manifest_paths = [item.get("source_path") for item in manifests]
    if paths != SELECTED_PATHS or method_ids != SELECTED_PATHS or manifest_paths != SELECTED_PATHS:
        raise P541DR2ValidationError("exact selected path/order contract failed")
    if _duplicates(paths) or _duplicates(method_ids) or _duplicates(manifest_paths):
        raise P541DR2ValidationError("duplicate method id/path")
    strategy_ids = [
        item.get("proposed_strategy", {}).get("strategy_id")
        for item in designs
        if item.get("proposed_strategy", {}).get("strategy_id") is not None
    ]
    if _duplicates(strategy_ids):
        raise P541DR2ValidationError("duplicate proposed strategy_id")
    for item in designs:
        status = item.get("design_status")
        if status not in ALLOWED_STATUSES:
            raise P541DR2ValidationError(f"unknown status: {status}")
        if item.get("equivalent_audit", {}).get("result") not in ALLOWED_EQUIVALENT_RESULTS:
            raise P541DR2ValidationError("unknown equivalent classification")
        expected_ready = status in READY_STATUSES
        if item.get("ready_for_implementation") is not expected_ready:
            raise P541DR2ValidationError("ready/status inconsistency")
        gates = item.get("readiness_gates", {})
        if expected_ready and not all(gates.get(key) is True for key in (
            "causality_resolved", "randomness_resolved", "external_state_resolved", "identity_distinct"
        )):
            raise P541DR2ValidationError("unresolved design marked ready")
    by_path = {item["source_path"]: item for item in designs}
    if by_path[SELECTED_PATHS[3]]["design_status"] != "NOT_AN_ADAPTER_CANDIDATE":
        raise P541DR2ValidationError("BigLottoAuditor fail-closed gate failed")
    zone = by_path[SELECTED_PATHS[4]]
    if zone["design_status"] != "DETERMINISTIC_REIMPLEMENTATION_READY" or "local random.Random" not in zone["randomness_and_seed_contract"]["contract"]:
        raise P541DR2ValidationError("ZoneSplit deterministic-design gate failed")
    quick = by_path[SELECTED_PATHS[2]]
    if "temporary CSV" not in quick["external_state_and_dependencies"]["forbidden_legacy_reads"]:
        raise P541DR2ValidationError("QuickML no-temp-CSV gate failed")
    ready = [item["method_id"] for item in designs if item["ready_for_implementation"]]
    cto = [item["method_id"] for item in designs if item["design_status"] == "CTO_REVIEW_REQUIRED"]
    rejected = [item["method_id"] for item in designs if item["design_status"] == "NOT_AN_ADAPTER_CANDIDATE"]
    if packet.get("projections") != {"implementation_ready": ready, "cto_review": cto, "rejected": rejected}:
        raise P541DR2ValidationError("projection mismatch")
    if packet.get("summary", {}).get("implementation_ready_count") != 3:
        raise P541DR2ValidationError("implementation-ready projection must be 3")
    if packet["summary"].get("cto_review_count") != 1 or packet["summary"].get("rejected_count") != 1:
        raise P541DR2ValidationError("CTO/rejected projection mismatch")
    if packet.get("disclaimer") != DISCLAIMER or any(item.get("disclaimer") != DISCLAIMER for item in designs):
        raise P541DR2ValidationError("disclaimer mismatch")


def render_markdown(packet: dict[str, Any]) -> str:
    validate_packet(packet)
    designs = packet["method_designs"]
    manifest_by_path = {item["source_path"]: item for item in packet["selected_source_manifest"]}
    lines = [
        "# P541D_R2 BIG_LOTTO Selected-Method Adapter Design (No DB)",
        "",
        "## Executive summary",
        "",
        f"Pinned static design at `{packet['base']['commit']}` for exactly five P541C_R2-selected methods. "
        "Three designs are implementation-ready, one requires a CTO identity decision, and one is rejected as not an adapter candidate. "
        "No selected module was imported or executed; no DB, data, runtime, network, environment, registry or lifecycle state was accessed or changed.",
        "",
        "## Five-method decision table",
        "",
        "| Method | Equivalent audit | Design status | Ready | Proposed strategy |",
        "|---|---|---|---:|---|",
    ]
    for design in designs:
        strategy_id = design["proposed_strategy"]["strategy_id"] or "—"
        lines.append(
            f"| `{design['source_path']}` | {design['equivalent_audit']['result']} | "
            f"{design['design_status']} | {'yes' if design['ready_for_implementation'] else 'no'} | `{strategy_id}` |"
        )
    lines.extend(["", "## Detailed method sections", ""])
    for design in designs:
        manifest = manifest_by_path[design["source_path"]]
        lines.extend(
            [
                f"### `{design['source_path']}`",
                "",
                f"- Source identity: blob `{manifest['git_blob_sha']}`, {manifest['byte_size']} bytes, SHA-256 `{manifest['sha256']}`; UTF-8/AST `{manifest['utf8_parse']}/{manifest['ast_parse']}`.",
                f"- Decision: **{design['design_status']}** — {design['design_rationale']}",
                f"- Entry point: `{design['selected_entrypoint'] or 'UNRESOLVED / NONE'}`.",
                f"- Equivalent audit: {design['equivalent_audit']['result']}; " + "; ".join(item["finding"] for item in design["equivalent_audit"]["evidence"]),
                f"- History/cutoff: {design['history_ordering']} {design['causal_cutoff']}",
                f"- Randomness: {design['randomness_and_seed_contract']['contract']}",
                f"- External state/import plan: {design['import_safety_plan']}",
                f"- Normalization/validation: {design['input_output_normalization']['input']} → {design['input_output_normalization']['output']}; {design['six_number_validation']}",
                f"- Parity oracle: {design['parity_oracle']['type']} — {design['parity_oracle'].get('comparison', design['parity_oracle'].get('requirement', 'n/a'))}.",
                f"- Blockers/CTO decisions: {'; '.join(design['blockers_and_cto_decisions']) if design['blockers_and_cto_decisions'] else 'none'}.",
                "",
            ]
        )
    lines.extend(["## Duplicate/equivalent findings", ""])
    for design in designs:
        lines.append(f"- `{design['source_path']}` — {design['equivalent_audit']['result']}: " + "; ".join(f"`{item['path']}` ({item['finding']})" for item in design["equivalent_audit"]["evidence"]))
    lines.extend(
        [
            "",
            "## Shared architecture",
            "",
            "Future implementations must reuse `ReplayStrategyAdapter`, `_StrategyMeta`, `_validate_numbers`, `RejectPrediction`, `InsufficientHistory`, `InvalidOutput`, and `UnsupportedLotteryType`. History is strictly before target; prediction reads no DB/file/env/network state; the result is one validated six-number BIG_LOTTO bet with special `None`. This design assigns no lifecycle and does not imply ONLINE status.",
            "",
            "## Implementation waves",
            "",
        ]
    )
    for wave in packet["implementation_sequencing"]:
        lines.append(f"- Wave {wave['wave']}: {', '.join(f'`{x}`' for x in wave['methods'])} — {wave['reason']}.")
    lines.extend(
        [
            "",
            "## CTO decisions",
            "",
            "- Select one AdvancedPredictionEngine mode and decide whether optional sklearn/XGBoost availability is identity-defining or prohibited.",
            "- BigLottoAuditor remains rejected; any new hot/cold predictor must have a new identity and separate authorization.",
            "",
            "## Future test plan",
            "",
            "- Assert strictly-prior cutoff, canonical ordering, minimum history, unsupported lottery mapping and one-bet storage.",
            "- Run exact synthetic vectors and parity oracles for Social Wisdom and QuickML.",
            "- Run ZoneSplit in separate processes and assert identical tickets, local-RNG isolation and first-zone membership.",
            "- Monkeypatch DB/file/env/network APIs to fail and prove prediction reaches none of them.",
            "- Exercise malformed, duplicate, out-of-range and deliberate no-bet outputs through canonical exceptions.",
            "",
            "## Non-claims",
            "",
            "- No runtime adapter, registry entry, replay row, DB access, target execution, promotion, production lifecycle or ONLINE status exists from this task.",
            "- Static design does not establish future parity or production readiness.",
            f"- {packet['disclaimer']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    packet = build_packet(REPO_ROOT)
    json_bytes = canonical_json_bytes(packet)
    markdown_bytes = render_markdown(packet).encode("utf-8")
    JSON_OUTPUT.write_bytes(json_bytes)
    MARKDOWN_OUTPUT.write_bytes(markdown_bytes)


if __name__ == "__main__":
    main()
