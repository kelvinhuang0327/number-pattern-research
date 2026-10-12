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
P541D_GENERATION_BASE_COMMIT = "8db53f9cb829d658ea47f01476ec52a61c5c583c"
P541D_GENERATION_BASE_TREE = "f0d26bd7235e3af02ba12790e18964b947e79d6f"
SELECTED_METHOD_SOURCE_COMMIT = "9572d994e94fae44cf7730297e7537c0901d5a78"
SELECTED_METHOD_SOURCE_TREE = "2cd6113c8450102d434044b7641a9d89f74cd682"
HISTORICAL_P541C_ARTIFACT_COMMIT = SELECTED_METHOD_SOURCE_COMMIT
P541C_ARTIFACT_COMMIT = "a68b5ca8663e82b7dad5da7c66d53eec10e517c0"
P541C_SOURCE_REFERENCE_COMMIT = "1777e15556d41f1ff829f9ac18aa3f58d7f8f54f"
P541C_SOURCE_REFERENCE_TREE = "5582783e56a930d7c9e637485b3c9749e66f470a"
ADAPTER_REFERENCE_COMMIT = P541D_GENERATION_BASE_COMMIT
PIN_ADOPTION_TASK_ID = "P541D_R2_R9_PIN_ADOPTION_IMPLEMENTATION_R1"
TASK_ID = "P541D_R2_BIG_LOTTO_SELECTED_METHOD_ADAPTER_DESIGN_NO_DB_WRITE"
SCHEMA_VERSION = "p541d-r2-adapter-design-v1"
DESIGNER_VERSION = "p541d-r2-designer-v2"
GENERATED_AT = "2026-10-12T00:00:00+00:00"

UPSTREAM_PATH = (
    "outputs/research/"
    "p541c_r2_biglotto_legacy_method_review_readiness_selection_20260712.json"
)
UPSTREAM_IDENTITY = {
    "path": UPSTREAM_PATH,
    "artifact_commit": P541C_ARTIFACT_COMMIT,
    "git_blob_sha": "0406f78c4d42b5551b12843f2d0d1443a55a9971",
    "byte_size": 1_407_881,
    "sha256": "ce0fa64f9b3b04dec4b42fddadce119c8f44ff5d36f10bf85a2dc0d3c2f3ac6c",
    "schema_version": "p541c-r2-selection-v3",
    "selector_version": "p541c-r2-selector-v5",
    "record_count": 580,
    "source_reference_commit": P541C_SOURCE_REFERENCE_COMMIT,
}
HISTORICAL_UPSTREAM_PIN = {
    "path": UPSTREAM_PATH,
    "artifact_commit": HISTORICAL_P541C_ARTIFACT_COMMIT,
    "git_blob_sha": "2fb216be14b95b84107417f67b67fe430403742a",
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
ADAPTER_REFERENCE_BLOBS = {
    "lottery_api/models/replay_strategy_registry.py": {
        "historical": "45770dabaa46c80e6f564b61e5dae96b03bd856e",
        "current": "21be32d9f0db2a600683dc1788a57f28b87f2529",
    },
    "lottery_api/models/p42_wave3_biglotto_adapters.py": {
        "historical": "213193465f205faac47a23b4e6b07d6701626571",
        "current": "213193465f205faac47a23b4e6b07d6701626571",
    },
    "lottery_api/models/p93_tierb_replay_adapters.py": {
        "historical": "297681147267d937383d7f898e59b26f811c6722",
        "current": "297681147267d937383d7f898e59b26f811c6722",
    },
}
REGISTRY_CONTRACT_DELTA = [
    "ReplayStrategyAdapter.get_one_bet now predicts a POWER_LOTTO special number with power_lotto_second_zone.second_zone_predict(history); BIG_LOTTO still returns special=None, so this change does not alter the five BIG_LOTTO designs.",
    "The current registry adds P0 2-bet, BIG_LOTTO ZoneSplit, and Social Wisdom adapter factories. The ZoneSplit Bet1 and Social Wisdom IDs match two P541D proposed IDs, and their factory source declares status=ONLINE.",
    "The two matching current registry declarations affect implementation follow-up: inspect and reconcile the existing source before any future implementation, and do not add duplicate strategy IDs. This static source finding is not runtime-state evidence and does not change P541C replay readiness.",
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


def git_blob_bytes(repo_root: Path, path: str, commit: str) -> bytes:
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise P541DR2ValidationError(f"unsafe Git path: {path}")
    return _git(repo_root, "show", f"{commit}:{path}")


def git_blob_sha(repo_root: Path, path: str, commit: str) -> str:
    return _git(repo_root, "rev-parse", f"{commit}:{path}").decode("ascii").strip()


def git_tree_sha(repo_root: Path, commit: str) -> str:
    return _git(repo_root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()


def _blob_identity(repo_root: Path, path: str, commit: str) -> dict[str, Any]:
    raw = git_blob_bytes(repo_root, path, commit)
    return {
        "commit": commit,
        "git_blob_sha": git_blob_sha(repo_root, path, commit),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


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
        "causal_history_requirements": "source head/slice operations show newest-first ordering, but the Method 9 bounds defect blocks runtime readiness",
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
    raw = git_blob_bytes(repo_root, path, SELECTED_METHOD_SOURCE_COMMIT)
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
        "source_commit": SELECTED_METHOD_SOURCE_COMMIT,
        "source_tree": SELECTED_METHOD_SOURCE_TREE,
        "git_blob_sha": git_blob_sha(repo_root, path, SELECTED_METHOD_SOURCE_COMMIT),
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


def _registry_factory_evidence(repo_root: Path, registry_raw: bytes) -> list[dict[str, Any]]:
    registry_text = registry_raw.decode("utf-8", errors="strict")
    required_registry_markers = (
        "power_lotto_second_zone.second_zone_predict(history)",
        "build_zone_split_adapters(",
        "build_social_wisdom_adapter(",
        "*_BIGLOTTO_ZONE_SPLIT_ADAPTERS",
        "_BIGLOTTO_SOCIAL_WISDOM_ADAPTER",
    )
    if any(marker not in registry_text for marker in required_registry_markers):
        raise P541DR2ValidationError("current replay registry contract evidence mismatch")
    registry_source_blob_sha = git_blob_sha(
        repo_root,
        "lottery_api/models/replay_strategy_registry.py",
        ADAPTER_REFERENCE_COMMIT,
    )

    declarations = [
        {
            "strategy_id": "biglotto_social_wisdom_anti_popularity",
            "source_path": "lottery_api/models/biglotto_social_wisdom_adapter.py",
            "required_markers": (
                'STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"',
                'strategy_id=STRATEGY_ID',
                'status="ONLINE"',
            ),
        },
        {
            "strategy_id": "biglotto_zone_split_3bet_bet1",
            "source_path": "lottery_api/models/biglotto_zone_split_adapter.py",
            "required_markers": (
                'BET1_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"',
                'strategy_id=BET1_STRATEGY_ID',
                'status="ONLINE"',
            ),
        },
    ]
    evidence: list[dict[str, Any]] = []
    for declaration in declarations:
        source_path = declaration["source_path"]
        raw = git_blob_bytes(repo_root, source_path, ADAPTER_REFERENCE_COMMIT)
        text = raw.decode("utf-8", errors="strict")
        if any(marker not in text for marker in declaration["required_markers"]):
            raise P541DR2ValidationError(
                f"current replay registry strategy declaration mismatch: {source_path}"
            )
        evidence.append(
            {
                "strategy_id": declaration["strategy_id"],
                "source_path": source_path,
                "source_commit": ADAPTER_REFERENCE_COMMIT,
                "registry_source_blob_sha": registry_source_blob_sha,
                "git_blob_sha": git_blob_sha(repo_root, source_path, ADAPTER_REFERENCE_COMMIT),
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "source_declared_status": "ONLINE",
                "runtime_state_observed": False,
            }
        )
    return evidence


def _adapter_reference(repo_root: Path, path: str) -> dict[str, Any]:
    historical = _blob_identity(repo_root, path, SELECTED_METHOD_SOURCE_COMMIT)
    current = _blob_identity(repo_root, path, ADAPTER_REFERENCE_COMMIT)
    expected = ADAPTER_REFERENCE_BLOBS[path]
    if (
        historical["git_blob_sha"] != expected["historical"]
        or current["git_blob_sha"] != expected["current"]
    ):
        raise P541DR2ValidationError(f"canonical adapter reference pin mismatch: {path}")
    raw = git_blob_bytes(repo_root, path, ADAPTER_REFERENCE_COMMIT)
    symbols: list[str]
    change_class = "UNCHANGED"
    contract_delta: list[str] = []
    registration_evidence: list[dict[str, Any]] = []
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
        change_class = "DESIGN_CONTRACT_DELTA"
        contract_delta = REGISTRY_CONTRACT_DELTA.copy()
        registration_evidence = _registry_factory_evidence(repo_root, raw)
    elif path.endswith("p42_wave3_biglotto_adapters.py"):
        symbols = ["strictly-prior history", "one recorded bet", "BIG_LOTTO 1..49 validation"]
    else:
        symbols = ["canonical primitive reuse", "lazy strategy imports", "first-bet normalization"]
    return {
        "path": path,
        "historical_source_commit": SELECTED_METHOD_SOURCE_COMMIT,
        "historical_git_blob_sha": historical["git_blob_sha"],
        "historical_byte_size": historical["byte_size"],
        "historical_sha256": historical["sha256"],
        "reference_commit": ADAPTER_REFERENCE_COMMIT,
        "git_blob_sha": current["git_blob_sha"],
        "byte_size": current["byte_size"],
        "sha256": current["sha256"],
        "change_class": change_class,
        "contract_delta": contract_delta,
        "registered_factory_evidence": registration_evidence,
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
            "lifecycle": "NOT_ASSIGNED_BY_THIS_STATIC_DESIGN" if strategy_id else "NOT_PROPOSED",
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
            "This static design makes no registry entry, lifecycle, replay-generation, promotion or ONLINE-status change.",
            "Current registry source observations are reported separately; future work must reconcile matching existing IDs before any implementation or registry change.",
        ],
        "blockers_and_cto_decisions": blockers,
        "readiness_gates": readiness_gates,
        "ready_for_implementation": ready,
        "disclaimer": DISCLAIMER,
    }


def build_method_designs(
    shortlist: list[dict[str, Any]],
    registered_factory_evidence: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    provenance = {path: _p541c_provenance(shortlist, path) for path in SELECTED_PATHS}
    common_exceptions = {
        "unsupported lottery": "UnsupportedLotteryType",
        "history shorter than minimum": "InsufficientHistory",
        "intentional no-bet": "RejectPrediction",
        "shape/range/duplicate/type failure": "InvalidOutput",
        "unexpected failure": "propagate for caller mapping to REPLAY_ERROR",
    }
    designs = [
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
            "CTO_REVIEW_REQUIRED",
            "QuickMLPredictor.predict_advanced_ensemble is only a candidate legacy entrypoint; no canonical runtime entrypoint is approved. Its Method 9 terminal iteration always forms a two-row pattern and then reads pattern[2], so the pinned callable raises IndexError for every usable history length (at least five), including the proposed 50-row minimum. A direct crash-faithful wrapper is not a useful replay strategy, while correcting the loop boundary changes executable semantics and requires a separately identified strategy or explicit CTO approval.",
            None,
            None,
            None,
            ["QuickMLPredictor.__init__", "QuickMLPredictor.predict_advanced_ensemble", "QuickMLPredictor.predict_smart_hybrid"],
            50,
            "Source-proven observation only: DataFrame.head() treats the CSV as newest-first. This ordering observation does not establish runtime readiness or approve a canonical adapter contract.",
            ["draw", "date", "numbers"],
            {"present": False, "deterministic": True, "contract": "The observed failure is deterministic; absence of random calls does not make the crashing callable implementation-ready."},
            {"prediction_reads": [], "forbidden_legacy_reads": ["pd.read_csv in constructor", "constructor CSV access", "temporary CSV"], "dependencies": ["pandas and numpy in the prohibited legacy execution path"]},
            "Do not import or construct QuickMLPredictor, do not create a temporary CSV, and do not implement an adapter. A corrected in-memory variant is a future, separately authorized strategy identity rather than a faithful wrapper of the pinned callable.",
            {"input": "No canonical runtime input contract is approved; newest-first behavior remains a source observation only", "output": "No successful legacy ticket exists for parity; pattern[2] raises IndexError before ranking completes"},
            common_exceptions,
            {"type": "blocked", "status": "BLOCKED", "callable": "QuickMLPredictor.predict_advanced_ensemble", "requirement": "No successful legacy parity oracle exists. CTO must first decide whether to reject the historical identity or authorize a separately named bounds-repaired strategy and its corrected parity contract."},
            [
                {
                    "id": "quickml-method9-minimum-history-crash",
                    "input": "50 order-asymmetric newest-first rows, with distinct row contents so ordering cannot be hidden",
                    "expected_failure": "The pinned callable reaches terminal i=48, obtains a two-row pattern slice, and raises IndexError at pattern[2]",
                    "purpose": "defect witness only; not a successful parity vector",
                },
                {
                    "id": "quickml-order-asymmetric-source-observation",
                    "input": {
                        "newest_row": [1, 7, 13, 19, 25, 31],
                        "middle_row": [2, 8, 14, 20, 26, 32],
                        "older_row": [3, 9, 15, 21, 27, 33],
                    },
                    "expected_observation": "head(3) preserves this newest-to-older order; it does not supply a successful legacy output",
                },
            ],
            [],
            [
                "Reject the historical QuickML identity entirely; or",
                "Authorize a separately identified bounds-repaired QuickML strategy; and",
                "Specify the corrected loop boundary and parity contract.",
            ],
            {"causality_resolved": False, "randomness_resolved": False, "external_state_resolved": False, "identity_distinct": False},
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
    quick = designs[2]
    quick["candidate_legacy_entrypoint"] = "QuickMLPredictor.predict_advanced_ensemble"
    quick["proposed_strategy"]["lifecycle"] = None
    quick["semantic_defect_evidence"] = {
        "analysis_method": "independent AST inspection plus a pandas-free list-slice bounds witness",
        "source_outer_loop": "range(3, len(self.df) - 1)",
        "normalized_outer_loop": "range(3, len(df) - 1)",
        "terminal_iteration": "i = len(df) - 2",
        "source_pattern_slice": "self.df.iloc[i:i+3]",
        "normalized_pattern_slice": "df.iloc[i:i+3]",
        "terminal_slice_row_count": 2,
        "inner_loop": "range(3)",
        "accessed_pattern_indices": [0, 1, 2],
        "failure": "pattern[2] raises IndexError for every history length >= 5",
        "candidate_minimum_history": 50,
        "candidate_minimum_history_result": "cannot produce a successful legacy ticket",
        "semantic_identity_consequence": "Clamping the loop boundary is a semantic repair, not identity-preserving extraction.",
    }
    registry_by_id = {
        item["strategy_id"]: item for item in (registered_factory_evidence or [])
    }
    for design in designs:
        strategy_id = design["proposed_strategy"]["strategy_id"]
        existing = registry_by_id.get(strategy_id)
        if existing is None:
            continue
        design["current_registry_observation"] = {
            "state": "MATCHING_STRATEGY_ID_DECLARED_IN_CURRENT_REGISTRY_SOURCE",
            "strategy_id": strategy_id,
            "registry_path": "lottery_api/models/replay_strategy_registry.py",
            "registry_source_commit": ADAPTER_REFERENCE_COMMIT,
            "registry_source_blob_sha": existing["registry_source_blob_sha"],
            "factory_source_path": existing["source_path"],
            "factory_source_blob_sha": existing["git_blob_sha"],
            "source_declared_status": existing["source_declared_status"],
            "runtime_state_observed": False,
            "follow_up": "Review the existing source implementation against this design; do not create a duplicate strategy ID.",
        }
        design["future_implementation_files"] = []
    return designs


def validate_upstream(upstream: dict[str, Any]) -> list[dict[str, Any]]:
    if upstream.get("schema_version") != UPSTREAM_IDENTITY["schema_version"]:
        raise P541DR2ValidationError("P541C_R2 schema mismatch")
    if upstream.get("selector_version") != UPSTREAM_IDENTITY["selector_version"]:
        raise P541DR2ValidationError("P541C_R2 selector mismatch")
    if upstream.get("implementation_base_commit") != P541C_SOURCE_REFERENCE_COMMIT:
        raise P541DR2ValidationError("P541C_R2 source-reference commit mismatch")
    records = upstream.get("reviewed_method_decisions")
    if not isinstance(records, list) or len(records) != UPSTREAM_IDENTITY["record_count"]:
        raise P541DR2ValidationError("P541C_R2 must contain exactly 580 reviewed records")
    record_ids = [item.get("method_id") for item in records if isinstance(item, dict)]
    source_paths = [item.get("source_path") for item in records if isinstance(item, dict)]
    if (
        len(record_ids) != UPSTREAM_IDENTITY["record_count"]
        or any(not isinstance(value, str) or not value for value in record_ids + source_paths)
        or len(set(record_ids)) != UPSTREAM_IDENTITY["record_count"]
        or len(set(source_paths)) != UPSTREAM_IDENTITY["record_count"]
    ):
        raise P541DR2ValidationError("P541C_R2 record identity duplicate or invalid")
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


def _historical_input_comparison(
    repo_root: Path,
    current_upstream: dict[str, Any],
) -> dict[str, Any]:
    raw = git_blob_bytes(
        repo_root,
        UPSTREAM_PATH,
        HISTORICAL_P541C_ARTIFACT_COMMIT,
    )
    historical_blob_sha = git_blob_sha(
        repo_root,
        UPSTREAM_PATH,
        HISTORICAL_P541C_ARTIFACT_COMMIT,
    )
    historical, actual = _verify_upstream_bytes(
        raw,
        HISTORICAL_UPSTREAM_PIN,
        historical_blob_sha,
        validate_current=False,
    )
    if (
        historical.get("schema_version") != HISTORICAL_UPSTREAM_PIN["schema_version"]
        or historical.get("selector_version") != HISTORICAL_UPSTREAM_PIN["selector_version"]
    ):
        raise P541DR2ValidationError("historical P541C_R2 selector identity mismatch")
    old_records = historical["reviewed_method_decisions"]
    new_records = current_upstream["reviewed_method_decisions"]
    old_method_ids = [item["method_id"] for item in old_records]
    new_method_ids = [item["method_id"] for item in new_records]
    old_source_paths = [item["source_path"] for item in old_records]
    new_source_paths = [item["source_path"] for item in new_records]
    old_shortlist = [item.get("source_path") for item in historical["high_priority_candidate_shortlist"]]
    new_shortlist = [item.get("source_path") for item in current_upstream["high_priority_candidate_shortlist"]]
    if (
        old_method_ids != new_method_ids
        or old_source_paths != new_source_paths
        or old_shortlist != new_shortlist
        or old_shortlist != SELECTED_PATHS
    ):
        raise P541DR2ValidationError("P541C_R2 record or shortlist order changed")
    return {
        "historical_artifact_commit": HISTORICAL_P541C_ARTIFACT_COMMIT,
        "historical_git_blob_sha": historical_blob_sha,
        "historical_byte_size": actual["byte_size"],
        "historical_sha256": actual["sha256"],
        "historical_selector_version": historical["selector_version"],
        "current_artifact_commit": P541C_ARTIFACT_COMMIT,
        "current_git_blob_sha": UPSTREAM_IDENTITY["git_blob_sha"],
        "record_count": len(new_records),
        "unique_method_id_count": len(set(new_method_ids)),
        "unique_source_path_count": len(set(new_source_paths)),
        "record_method_id_order_sha256": hashlib.sha256(
            canonical_json_bytes(new_method_ids)
        ).hexdigest(),
        "record_source_path_order_sha256": hashlib.sha256(
            canonical_json_bytes(new_source_paths)
        ).hexdigest(),
        "record_method_id_order_matches_historical": True,
        "record_source_path_order_matches_historical": True,
        "shortlist_count": len(new_shortlist),
        "shortlist_order_matches_historical": True,
        "shortlist_order": new_shortlist,
    }


def _verify_upstream_bytes(
    raw: bytes,
    expected_identity: dict[str, Any],
    actual_blob_sha: Optional[str] = None,
    validate_current: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    actual = {"byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if (
        actual["byte_size"] != expected_identity["byte_size"]
        or actual["sha256"] != expected_identity["sha256"]
        or (
            expected_identity.get("git_blob_sha") is not None
            and actual_blob_sha != expected_identity["git_blob_sha"]
        )
    ):
        raise P541DR2ValidationError("pinned P541C_R2 byte identity mismatch")
    upstream = strict_json_load_bytes(raw, UPSTREAM_PATH)
    if validate_current:
        validate_upstream(upstream)
    return upstream, actual


def _load_upstream(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    raw = git_blob_bytes(repo_root, UPSTREAM_PATH, P541C_ARTIFACT_COMMIT)
    blob_sha = git_blob_sha(repo_root, UPSTREAM_PATH, P541C_ARTIFACT_COMMIT)
    upstream, actual = _verify_upstream_bytes(raw, UPSTREAM_IDENTITY, blob_sha)
    source_reference_commit = upstream["implementation_base_commit"]
    source_reference_tree = git_tree_sha(repo_root, source_reference_commit)
    if source_reference_tree != P541C_SOURCE_REFERENCE_TREE:
        raise P541DR2ValidationError("P541C_R2 source-reference tree mismatch")
    identity = {
        **UPSTREAM_IDENTITY,
        **actual,
        "verification": "PASS",
        "read_mechanism": "git show <artifact commit>:<relative-path>",
    }
    source_reference = {
        "commit": source_reference_commit,
        "tree": source_reference_tree,
        "declared_by_artifact_commit": P541C_ARTIFACT_COMMIT,
    }
    return upstream, identity, source_reference


def build_packet(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    upstream, upstream_identity, source_reference = _load_upstream(repo_root)
    shortlist = validate_upstream(upstream)
    input_comparison = _historical_input_comparison(repo_root, upstream)
    manifests = [source_manifest_record(repo_root, path) for path in SELECTED_PATHS]
    adapter_refs = [_adapter_reference(repo_root, path) for path in ADAPTER_REFERENCE_PATHS]
    registry_ref = next(
        item for item in adapter_refs if item["path"] == "lottery_api/models/replay_strategy_registry.py"
    )
    designs = build_method_designs(shortlist, registry_ref["registered_factory_evidence"])
    ready = [d["method_id"] for d in designs if d["ready_for_implementation"]]
    cto = [d["method_id"] for d in designs if d["design_status"] == "CTO_REVIEW_REQUIRED"]
    rejected = [d["method_id"] for d in designs if d["design_status"] == "NOT_AN_ADAPTER_CANDIDATE"]
    counts = {status: sum(d["design_status"] == status for d in designs) for status in sorted(ALLOWED_STATUSES)}
    packet = {
        "schema_version": SCHEMA_VERSION,
        "designer_version": DESIGNER_VERSION,
        "task": {
            "task_id": TASK_ID,
            "pin_adoption_task_id": PIN_ADOPTION_TASK_ID,
            "generated_at": GENERATED_AT,
            "scope": "static no-DB adapter design for exactly five selected BIG_LOTTO methods",
            "design_only": True,
        },
        "base": {
            "commit": P541D_GENERATION_BASE_COMMIT,
            "tree": P541D_GENERATION_BASE_TREE,
            "branch": "main",
        },
        "source_bases": {
            "p541c_artifact": {
                "commit": P541C_ARTIFACT_COMMIT,
                "git_blob_sha": UPSTREAM_IDENTITY["git_blob_sha"],
                "path": UPSTREAM_PATH,
            },
            "p541c_declared_source_reference": source_reference,
            "p541d_generation_source": {
                "commit": P541D_GENERATION_BASE_COMMIT,
                "tree": P541D_GENERATION_BASE_TREE,
            },
            "selected_method_sources": {
                "commit": SELECTED_METHOD_SOURCE_COMMIT,
                "tree": SELECTED_METHOD_SOURCE_TREE,
            },
            "canonical_adapter_references": {
                "commit": ADAPTER_REFERENCE_COMMIT,
                "tree": P541D_GENERATION_BASE_TREE,
                "historical_comparison_commit": SELECTED_METHOD_SOURCE_COMMIT,
            },
        },
        "upstream_identity": upstream_identity,
        "p541c_readiness_context": {
            "ready_for_replay_readiness_now": upstream["summary"]["ready_for_replay_readiness_now"],
            "static_design_readiness_is_separate": True,
            "interpretation": "P541D ready_for_implementation is a static design grade and does not promote P541C replay readiness or production status.",
        },
        "historical_input_comparison": input_comparison,
        "canonical_adapter_references": adapter_refs,
        "selected_source_manifest": manifests,
        "method_designs": designs,
        "historical_design_comparison": {
            "historical_generator_source_commit": P541D_GENERATION_BASE_COMMIT,
            "historical_input_and_method_source_base_commit": SELECTED_METHOD_SOURCE_COMMIT,
            "historical_p541c_selector": "p541c-r2-selector-v4",
            "normalized_design_delta": "EXACT_EXPLAINED_DIFF",
            "normalization": [
                "Compare each method design after removing P541C provenance, current-registry observations, and the per-design lifecycle placeholder.",
                "Compare current method source manifests at the same historical source commit; verify status, gates, selected identity, and design contract independently.",
            ],
            "unchanged": [
                "Five selected method paths and order.",
                "All 580 method IDs and source paths are unique and retain the exact historical order; the five-member shortlist order is unchanged.",
                "Five selected source blob identities at the historical method-source commit.",
                "Two implementation-ready static designs, two CTO-review designs, and one rejected design.",
                "All design statuses, readiness gates, selected identities, and synthetic evidence after normalization.",
            ],
            "explained_deltas": [
                "P541C provenance now uses the v5 artifact at its exact Git commit/blob and separately records its declared implementation/source-reference commit.",
                "P541D generation provenance uses current main while the five reviewed legacy method sources remain pinned to their historical source base.",
                "The current replay registry has a contract delta: POWER_LOTTO special-number behavior changed, and the matching Social Wisdom and ZoneSplit strategy IDs are already declared by current registry source. Those existing IDs are surfaced so future work avoids duplicate registration; static design counts and P541C readiness do not change.",
            ],
        },
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
            {"wave": 2, "methods": [SELECTED_PATHS[4]], "reason": "local deterministic RNG reimplementation"},
            {"wave": "CTO", "methods": [SELECTED_PATHS[0], SELECTED_PATHS[2]], "reason": "select Advanced mode/dependency identity and decide QuickML bounds-repair identity"},
            {"wave": "REJECTED", "methods": [SELECTED_PATHS[3]], "reason": "outcome-aware audit is not a predictor"},
        ],
        "no_db_no_execution_evidence": {
            "source_read_mechanism": "git show <pinned commit>:<relative-path>",
            "p541c_artifact_commit": P541C_ARTIFACT_COMMIT,
            "p541c_source_reference_commit": P541C_SOURCE_REFERENCE_COMMIT,
            "selected_method_source_commit": SELECTED_METHOD_SOURCE_COMMIT,
            "adapter_reference_commit": ADAPTER_REFERENCE_COMMIT,
            "p541d_generation_source_commit": P541D_GENERATION_BASE_COMMIT,
            "selected_modules_imported": False,
            "selected_modules_executed": False,
            "db_access": "NONE",
            "data_runtime_access": "NONE",
            "runtime_state_access": "NONE",
            "environment_access": "NONE",
            "registry_runtime_state_access": "NONE",
            "writes": [
                "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.json",
                "outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.md",
            ],
        },
        "limits": [
            "Static design does not prove future implementation parity.",
            "No adapter, registry, lifecycle, replay row, DB state, production behavior or target runtime was created, executed or queried.",
            "Current registry declarations are static Git-source observations only; they do not prove that runtime adapters are active.",
            "P541D ready_for_implementation is static design readiness and is not P541C ready_for_replay_readiness_now or production readiness.",
            "Selected method sources are pinned to their historical Git object base; adapter references and generator provenance use current main.",
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
    if packet.get("base") != {
        "commit": P541D_GENERATION_BASE_COMMIT,
        "tree": P541D_GENERATION_BASE_TREE,
        "branch": "main",
    }:
        raise P541DR2ValidationError("P541D generation base pin mismatch")
    expected_source_bases = {
        "p541c_artifact": {
            "commit": P541C_ARTIFACT_COMMIT,
            "git_blob_sha": UPSTREAM_IDENTITY["git_blob_sha"],
            "path": UPSTREAM_PATH,
        },
        "p541c_declared_source_reference": {
            "commit": P541C_SOURCE_REFERENCE_COMMIT,
            "tree": P541C_SOURCE_REFERENCE_TREE,
            "declared_by_artifact_commit": P541C_ARTIFACT_COMMIT,
        },
        "p541d_generation_source": {
            "commit": P541D_GENERATION_BASE_COMMIT,
            "tree": P541D_GENERATION_BASE_TREE,
        },
        "selected_method_sources": {
            "commit": SELECTED_METHOD_SOURCE_COMMIT,
            "tree": SELECTED_METHOD_SOURCE_TREE,
        },
        "canonical_adapter_references": {
            "commit": ADAPTER_REFERENCE_COMMIT,
            "tree": P541D_GENERATION_BASE_TREE,
            "historical_comparison_commit": SELECTED_METHOD_SOURCE_COMMIT,
        },
    }
    if packet.get("source_bases") != expected_source_bases:
        raise P541DR2ValidationError("separated source-base identities mismatch")
    expected_upstream_identity = {
        **UPSTREAM_IDENTITY,
        "verification": "PASS",
        "read_mechanism": "git show <artifact commit>:<relative-path>",
    }
    if packet.get("upstream_identity") != expected_upstream_identity:
        raise P541DR2ValidationError("P541C artifact identity mismatch")
    if packet.get("p541c_readiness_context") != {
        "ready_for_replay_readiness_now": 0,
        "static_design_readiness_is_separate": True,
        "interpretation": "P541D ready_for_implementation is a static design grade and does not promote P541C replay readiness or production status.",
    }:
        raise P541DR2ValidationError("P541C/P541D readiness boundary mismatch")
    input_comparison = packet.get("historical_input_comparison", {})
    if (
        input_comparison.get("historical_artifact_commit") != HISTORICAL_P541C_ARTIFACT_COMMIT
        or input_comparison.get("historical_git_blob_sha") != HISTORICAL_UPSTREAM_PIN["git_blob_sha"]
        or input_comparison.get("current_artifact_commit") != P541C_ARTIFACT_COMMIT
        or input_comparison.get("current_git_blob_sha") != UPSTREAM_IDENTITY["git_blob_sha"]
        or input_comparison.get("record_count") != UPSTREAM_IDENTITY["record_count"]
        or input_comparison.get("unique_method_id_count") != UPSTREAM_IDENTITY["record_count"]
        or input_comparison.get("unique_source_path_count") != UPSTREAM_IDENTITY["record_count"]
        or input_comparison.get("record_method_id_order_matches_historical") is not True
        or input_comparison.get("record_source_path_order_matches_historical") is not True
        or input_comparison.get("shortlist_count") != len(SELECTED_PATHS)
        or input_comparison.get("shortlist_order_matches_historical") is not True
        or input_comparison.get("shortlist_order") != SELECTED_PATHS
    ):
        raise P541DR2ValidationError("P541C record uniqueness/order comparison mismatch")
    designs = packet.get("method_designs")
    manifests = packet.get("selected_source_manifest")
    if not isinstance(designs, list) or not isinstance(manifests, list):
        raise P541DR2ValidationError("design and manifest lists required")
    paths = [item.get("source_path") for item in designs]
    method_ids = [item.get("method_id") for item in designs]
    manifest_paths = [item.get("source_path") for item in manifests]
    if paths != SELECTED_PATHS or method_ids != SELECTED_PATHS or manifest_paths != SELECTED_PATHS:
        raise P541DR2ValidationError("exact selected path/order contract failed")
    if any(
        item.get("source_commit") != SELECTED_METHOD_SOURCE_COMMIT
        or item.get("source_tree") != SELECTED_METHOD_SOURCE_TREE
        for item in manifests
    ):
        raise P541DR2ValidationError("selected source base identity mismatch")
    if _duplicates(paths) or _duplicates(method_ids) or _duplicates(manifest_paths):
        raise P541DR2ValidationError("duplicate method id/path")
    strategy_ids = [
        item.get("proposed_strategy", {}).get("strategy_id")
        for item in designs
        if item.get("proposed_strategy", {}).get("strategy_id") is not None
    ]
    if _duplicates(strategy_ids):
        raise P541DR2ValidationError("duplicate proposed strategy_id")
    references = packet.get("canonical_adapter_references")
    if not isinstance(references, list) or [item.get("path") for item in references] != ADAPTER_REFERENCE_PATHS:
        raise P541DR2ValidationError("canonical adapter reference list/order mismatch")
    for reference in references:
        expected_blobs = ADAPTER_REFERENCE_BLOBS[reference["path"]]
        if (
            reference.get("historical_source_commit") != SELECTED_METHOD_SOURCE_COMMIT
            or reference.get("historical_git_blob_sha") != expected_blobs["historical"]
            or reference.get("reference_commit") != ADAPTER_REFERENCE_COMMIT
            or reference.get("git_blob_sha") != expected_blobs["current"]
        ):
            raise P541DR2ValidationError("canonical adapter reference blob pin mismatch")
    registry_reference = references[0]
    if (
        registry_reference.get("change_class") != "DESIGN_CONTRACT_DELTA"
        or registry_reference.get("contract_delta") != REGISTRY_CONTRACT_DELTA
    ):
        raise P541DR2ValidationError("replay registry contract delta missing or changed")
    registry_factories = registry_reference.get("registered_factory_evidence", [])
    if [item.get("strategy_id") for item in registry_factories] != [
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
    ] or any(
        item.get("source_declared_status") != "ONLINE"
        or item.get("runtime_state_observed") is not False
        or item.get("source_commit") != ADAPTER_REFERENCE_COMMIT
        for item in registry_factories
    ):
        raise P541DR2ValidationError("current registry factory evidence mismatch")
    if any(
        reference.get("change_class") != "UNCHANGED" or reference.get("contract_delta")
        for reference in references[1:]
    ):
        raise P541DR2ValidationError("unchanged adapter reference contract mismatch")
    comparison = packet.get("historical_design_comparison", {})
    if (
        comparison.get("normalized_design_delta") != "EXACT_EXPLAINED_DIFF"
        or comparison.get("historical_generator_source_commit") != P541D_GENERATION_BASE_COMMIT
        or comparison.get("historical_input_and_method_source_base_commit") != SELECTED_METHOD_SOURCE_COMMIT
    ):
        raise P541DR2ValidationError("historical normalized design comparison missing")
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
    quick_strategy = quick.get("proposed_strategy", {})
    quick_evidence = quick.get("semantic_defect_evidence", {})
    quick_parity = quick.get("parity_oracle", {})
    if (
        quick.get("design_status") != "CTO_REVIEW_REQUIRED"
        or quick.get("ready_for_implementation") is not False
        or quick.get("equivalent_audit", {}).get("result") != "EXISTING_PARTIAL_EQUIVALENT"
        or quick.get("candidate_legacy_entrypoint") != "QuickMLPredictor.predict_advanced_ensemble"
        or quick.get("selected_entrypoint") is not None
    ):
        raise P541DR2ValidationError("QuickML fail-closed identity gate failed")
    if (
        quick_strategy.get("strategy_id") is not None
        or quick_strategy.get("strategy_name") is not None
        or quick_strategy.get("strategy_version") is not None
        or quick_strategy.get("lifecycle") is not None
        or quick.get("future_implementation_files")
    ):
        raise P541DR2ValidationError("QuickML implementation authorization gate failed")
    if quick_parity.get("type") != "blocked" or quick_parity.get("status") != "BLOCKED":
        raise P541DR2ValidationError("QuickML parity must remain blocked")
    if not quick.get("blockers_and_cto_decisions"):
        raise P541DR2ValidationError("QuickML CTO decisions required")
    expected_evidence = {
        "source_outer_loop": "range(3, len(self.df) - 1)",
        "normalized_outer_loop": "range(3, len(df) - 1)",
        "terminal_iteration": "i = len(df) - 2",
        "source_pattern_slice": "self.df.iloc[i:i+3]",
        "normalized_pattern_slice": "df.iloc[i:i+3]",
        "terminal_slice_row_count": 2,
        "inner_loop": "range(3)",
        "accessed_pattern_indices": [0, 1, 2],
        "failure": "pattern[2] raises IndexError for every history length >= 5",
        "candidate_minimum_history": 50,
        "candidate_minimum_history_result": "cannot produce a successful legacy ticket",
    }
    if any(quick_evidence.get(key) != value for key, value in expected_evidence.items()):
        raise P541DR2ValidationError("QuickML semantic-defect evidence missing")
    quick_text = json.dumps(quick, ensure_ascii=False, sort_keys=True)
    if "expected_numbers" in quick_text or "can be extracted unchanged" in quick_text:
        raise P541DR2ValidationError("QuickML false success/identity claim")
    ready = [item["method_id"] for item in designs if item["ready_for_implementation"]]
    cto = [item["method_id"] for item in designs if item["design_status"] == "CTO_REVIEW_REQUIRED"]
    rejected = [item["method_id"] for item in designs if item["design_status"] == "NOT_AN_ADAPTER_CANDIDATE"]
    if packet.get("projections") != {"implementation_ready": ready, "cto_review": cto, "rejected": rejected}:
        raise P541DR2ValidationError("projection mismatch")
    if ready != [SELECTED_PATHS[1], SELECTED_PATHS[4]]:
        raise P541DR2ValidationError("implementation-ready projection must contain exactly Social Wisdom and ZoneSplit")
    if cto != [SELECTED_PATHS[0], SELECTED_PATHS[2]]:
        raise P541DR2ValidationError("CTO projection must contain exactly Advanced and QuickML")
    if packet.get("summary", {}).get("implementation_ready_count") != 2:
        raise P541DR2ValidationError("implementation-ready projection must be 2")
    if packet["summary"].get("cto_review_count") != 2 or packet["summary"].get("rejected_count") != 1:
        raise P541DR2ValidationError("CTO/rejected projection mismatch")
    quick_waves = [
        wave.get("wave")
        for wave in packet.get("implementation_sequencing", [])
        if SELECTED_PATHS[2] in wave.get("methods", [])
    ]
    if quick_waves != ["CTO"]:
        raise P541DR2ValidationError("QuickML must appear only in the CTO decision wave")
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
        f"Pinned static design at generation base `{packet['base']['commit']}` for exactly five P541C_R2-selected methods. "
        "Two designs are implementation-ready, two require CTO identity decisions, and one is rejected as not an adapter candidate. "
        "No selected module was imported or executed; no DB, data, runtime, network, environment, or registry runtime state was accessed or changed. "
        "Canonical registry Git source was inspected at the pinned reference commit.",
        "",
        "## Pinned source identities",
        "",
        f"- P541C artifact: commit `{packet['source_bases']['p541c_artifact']['commit']}`, blob `{packet['source_bases']['p541c_artifact']['git_blob_sha']}`, {packet['upstream_identity']['byte_size']} bytes, SHA-256 `{packet['upstream_identity']['sha256']}`, selector `{packet['upstream_identity']['selector_version']}`.",
        f"- P541C-declared source/reference: commit `{packet['source_bases']['p541c_declared_source_reference']['commit']}`, tree `{packet['source_bases']['p541c_declared_source_reference']['tree']}`.",
        f"- P541D generation source: commit `{packet['source_bases']['p541d_generation_source']['commit']}`, tree `{packet['source_bases']['p541d_generation_source']['tree']}`.",
        f"- Five selected method source blobs: historical source commit `{packet['source_bases']['selected_method_sources']['commit']}`, tree `{packet['source_bases']['selected_method_sources']['tree']}`.",
        f"- Canonical adapter references: current commit `{packet['source_bases']['canonical_adapter_references']['commit']}`; compared with historical commit `{packet['source_bases']['canonical_adapter_references']['historical_comparison_commit']}`.",
        "",
        "## P541C readiness boundary",
        "",
        f"P541C `ready_for_replay_readiness_now`: **{packet['p541c_readiness_context']['ready_for_replay_readiness_now']}**. P541D `ready_for_implementation` grades only static design readiness; it does not promote P541C replay readiness or production status.",
        "",
        "## Record and shortlist stability",
        "",
        f"P541C v5 contains {packet['historical_input_comparison']['record_count']} records, with {packet['historical_input_comparison']['unique_method_id_count']} unique method IDs and {packet['historical_input_comparison']['unique_source_path_count']} unique source paths. Method-ID and source-path order both match the historical v4 artifact. The five-member shortlist order is unchanged: "
        + ", ".join(f"`{path}`" for path in packet["historical_input_comparison"]["shortlist_order"])
        + ".",
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
                f"- Source identity: commit `{manifest['source_commit']}`, blob `{manifest['git_blob_sha']}`, {manifest['byte_size']} bytes, SHA-256 `{manifest['sha256']}`; UTF-8/AST `{manifest['utf8_parse']}/{manifest['ast_parse']}`.",
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
        defect = design.get("semantic_defect_evidence")
        if defect:
            lines[-1:] = [
                f"- Semantic defect evidence: Method 9 uses `{defect['normalized_outer_loop']}`; at `{defect['terminal_iteration']}`, `{defect['normalized_pattern_slice']}` has {defect['terminal_slice_row_count']} rows while `{defect['inner_loop']}` accesses indices {defect['accessed_pattern_indices']}. {defect['failure']}.",
                f"- Semantic identity consequence: {defect['semantic_identity_consequence']} The proposed minimum history of {defect['candidate_minimum_history']} {defect['candidate_minimum_history_result']}.",
                "",
            ]
        registry_observation = design.get("current_registry_observation")
        if registry_observation:
            lines.extend(
                [
                    f"- Current registry source: `{registry_observation['strategy_id']}` appears in `{registry_observation['registry_path']}` at `{registry_observation['registry_source_commit']}` (blob `{registry_observation['registry_source_blob_sha']}`); factory source declares `{registry_observation['source_declared_status']}`. Runtime state was not observed. {registry_observation['follow_up']}",
                    "",
                ]
            )
    lines.extend(["## Canonical adapter reference comparison", ""])
    lines.append("| Reference | Historical blob | Current blob | Classification |")
    lines.append("|---|---|---|---|")
    for reference in packet["canonical_adapter_references"]:
        lines.append(
            f"| `{reference['path']}` | `{reference['historical_git_blob_sha']}` | `{reference['git_blob_sha']}` | {reference['change_class']} |"
        )
        for delta in reference["contract_delta"]:
            lines.append(f"  - {delta}")
    lines.extend(
        [
            "",
            "P42 and P93 blobs are unchanged, so their recorded identities are provenance-only. The replay registry blob changed and its source-level contract delta is recorded above; Social Wisdom and ZoneSplit IDs already appear in the current source. This is not evidence that a runtime was queried or that those candidates are P541C replay-ready.",
            "",
            "## Historical normalized design comparison",
            "",
            f"Normalized result: **{packet['historical_design_comparison']['normalized_design_delta']}**. The five methods, order, source identities, readiness gates, and 2 implementation-ready / 2 CTO-review / 1 rejected status counts are preserved. Explained differences are limited to P541C v5 provenance, separated generation/source bases, and the current registry contract/reference evidence.",
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
            "The design references `ReplayStrategyAdapter`, `_StrategyMeta`, `_validate_numbers`, `RejectPrediction`, `InsufficientHistory`, `InvalidOutput`, and `UnsupportedLotteryType`. History is strictly before target; prediction reads no DB/file/env/network state; the result is one validated six-number BIG_LOTTO bet with special `None`. This static design assigns no lifecycle. The current registry source declares matching Social Wisdom and ZoneSplit IDs; reconcile those existing sources before any future implementation and do not create duplicate IDs.",
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
            "- QuickML decision 1: reject the historical QuickML identity entirely; or",
            "- QuickML decision 2: authorize a separately identified bounds-repaired QuickML strategy; and",
            "- QuickML decision 3: specify the corrected loop boundary and parity contract.",
            "- BigLottoAuditor remains rejected; any new hot/cold predictor must have a new identity and separate authorization.",
            "",
            "## Future test plan",
            "",
            "- Assert strictly-prior cutoff, canonical ordering, minimum history, unsupported lottery mapping and one-bet storage.",
            "- Reconcile the existing Social Wisdom and ZoneSplit source implementations with these designs before any further adapter work; do not create duplicate strategy IDs. QuickML parity remains BLOCKED because the pinned callable has no successful legacy output.",
            "- Preserve an order-asymmetric QuickML defect vector so newest/oldest history drift cannot be hidden by repeated draws.",
            "- Run ZoneSplit in separate processes and assert identical tickets, local-RNG isolation and first-zone membership.",
            "- Monkeypatch DB/file/env/network APIs to fail and prove prediction reaches none of them.",
            "- Exercise malformed, duplicate, out-of-range and deliberate no-bet outputs through canonical exceptions.",
            "",
            "## Non-claims",
            "",
            "- This task creates or changes no runtime adapter, registry entry, replay row, DB state, target execution, promotion, production lifecycle or ONLINE status.",
            "- Current source code declares matching Social Wisdom and ZoneSplit strategy IDs and status metadata; runtime state was not queried, so this is not a claim of active deployment or P541C replay readiness.",
            "- Static design does not establish future parity or production readiness.",
            f"- {packet['disclaimer']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    first_packet = build_packet(REPO_ROOT)
    first_json = canonical_json_bytes(first_packet)
    first_markdown = render_markdown(first_packet).encode("utf-8")
    second_packet = build_packet(REPO_ROOT)
    json_bytes = canonical_json_bytes(second_packet)
    markdown_bytes = render_markdown(second_packet).encode("utf-8")
    if first_json != json_bytes or first_markdown != markdown_bytes:
        raise P541DR2ValidationError("restricted P541D generation is not deterministic")
    JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_bytes(json_bytes)
    MARKDOWN_OUTPUT.write_bytes(markdown_bytes)


if __name__ == "__main__":
    main()
