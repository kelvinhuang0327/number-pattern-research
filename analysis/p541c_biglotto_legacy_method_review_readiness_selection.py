"""P541C: BIG_LOTTO legacy method review and replay-readiness selection.

Read-only review/selection artifact over the P541B classification output.
Does not touch the DB, does not generate replay rows, does not run OOS,
does not recompute any P536-P541B artifact.
"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

P541B_JSON = REPO_ROOT / "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json"
P541B_MD = REPO_ROOT / "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md"
P541A_JSON = REPO_ROOT / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json"
P541A_MD = REPO_ROOT / "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md"

IMPLEMENTATION_BASE_COMMIT = "0e895497f7a309c1b9f9e8801480fb498a63eef2"
GENERATED_AT = "2026-07-10T02:12:56.834011+00:00"
SOURCE_MANIFEST_COUNT = 580
SOURCE_MANIFEST_TOTAL_BYTES = 7_149_566
SOURCE_MANIFEST_SHA256 = "d863872664166bfdc06f79fcef51ca5c5ef1c6b39f60e35426abff5fb89fd69e"

INPUT_ARTIFACTS = {
    "p541b_json": {
        "path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json",
        "byte_size": 1_120_976,
        "sha256": "4828e67b06fe43e8db661c4a96fdaf37e25cef500759f7825ad96eeea1971f35",
        "git_blob_id": "12f1595c96e3f9deddc7a7d2d9549c03144635f0",
        "source_commit": "49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        "schema_version": "1.0",
        "task_id": "P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT",
    },
    "p541b_markdown": {
        "path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md",
        "byte_size": 14_737,
        "sha256": "a39131ba7d4536e39a07f36314870ba210e280d6d4c71e3046f82994733ed0a9",
        "git_blob_id": "3b28e39bfe747c5f196b9aec6610284709466cf8",
        "source_commit": "49a25effa62fc24f40789c16be6f11bdfb41a4a9",
    },
    "p541a_json": {
        "path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
        "byte_size": 52_406,
        "sha256": "52a90c714b495dde43db25f5d29aa6c4f3f2442e9225cd347b6ff4cde2cb3a47",
        "git_blob_id": "7557f364160dc09c91a19c07b370cb4b231c0194",
        "source_commit": "a0d6d925dbc70cceda98a10a4e0404ed35bf138c",
        "schema_version": "1.0",
        "task_id": "P541A",
    },
    "p541a_markdown": {
        "path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
        "byte_size": 5_224,
        "sha256": "d05e2e78e0378ffcb81d8e8e416aeed714d834f9ae82b43f84af4fbcda2cd34e",
        "git_blob_id": "7c2574dd80e8fbef147da0d4477a0c8eda56afe0",
        "source_commit": "a0d6d925dbc70cceda98a10a4e0404ed35bf138c",
    },
}

DISCLAIMER = (
    "Historical legacy method review and replay-readiness selection only; "
    "not a prediction, betting edge, future-winning, or production-readiness claim."
)

DECISION_READY = "ready_for_replay_readiness_now"
DECISION_ADAPTER = "needs_adapter_before_readiness"
DECISION_REFACTOR = "needs_refactor_before_readiness"
DECISION_CTO = "needs_cto_review"
DECISION_EXCLUDE = "exclude_from_replay"

ALL_DECISIONS = (DECISION_READY, DECISION_ADAPTER, DECISION_REFACTOR, DECISION_CTO, DECISION_EXCLUDE)

NEXT_TASK_OPTIONS = (
    "P541D_BIG_LOTTO_REPLAY_READINESS_FOR_SELECTED_LEGACY_METHODS_NO_DB_WRITE",
    "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE",
    "P541D_BIG_LOTTO_CTO_REVIEW_PACKET_FOR_AMBIGUOUS_METHODS",
    "P541C_COMPLETE_NO_SAFE_REPLAY_READINESS_CANDIDATES",
    "P541C_BLOCKED_SELECTION_TOO_AMBIGUOUS_NEEDS_OWNER_OR_CTO",
)

_EVIDENCE_BOOL_RE = re.compile(r"^([a-zA-Z_]+)=(True|False)$")
REQUIRED_EVIDENCE_FLAGS = {
    "module_level_db_call", "module_level_write_or_sideeffect",
    "uses_db_anywhere", "writes_files_anywhere", "hardcoded_abs_path",
    "hardcoded_draw_or_date", "has_main_guard",
}
ALLOWED_RECOMMENDED_ACTIONS = {
    "exclude_from_replay", "include_in_replay_readiness", "mark_deprecated",
    "mark_duplicate", "mark_not_strategy", "needs_cto_review",
}
ALLOWED_RUNNABLE_STATUSES = {
    "ambiguous_needs_cto_review", "broken_or_import_error",
    "hardcoded_paths_or_dates", "imports_db_or_runs_work_at_module_load",
    "needs_adapter_wrapper", "needs_db_safety_refactor",
    "needs_refactor_to_pure_function", "not_a_strategy",
    "obsolete_or_deprecated", "runnable_with_existing_adapter",
    "unsafe_side_effects",
}


class P541CValidationError(ValueError):
    """Raised when committed provenance or a fail-closed contract is violated."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise P541CValidationError("value is not finite canonical JSON") from exc


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P541CValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_load(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise P541CValidationError(f"non-finite JSON constant: {value}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(
                handle,
                object_pairs_hook=_reject_duplicate_object_pairs,
                parse_constant=reject_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P541CValidationError(f"cannot load strict JSON: {path}") from exc
    if not isinstance(value, dict):
        raise P541CValidationError(f"top-level JSON object required: {path}")
    return value


def verify_file_identity(repo_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    relative = Path(identity["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise P541CValidationError(f"unsafe input path: {identity['path']!r}")
    unresolved = repo_root / relative
    if unresolved.is_symlink():
        raise P541CValidationError(f"symlink input rejected: {identity['path']!r}")
    try:
        path = unresolved.resolve(strict=True)
        if repo_root not in path.parents or not path.is_file():
            raise P541CValidationError(f"input escapes repository: {identity['path']!r}")
        size = path.stat().st_size
    except OSError as exc:
        raise P541CValidationError(f"required input missing: {identity['path']}") from exc
    actual_sha256 = file_sha256(path)
    if size != identity["byte_size"] or actual_sha256 != identity["sha256"]:
        raise P541CValidationError(
            f"committed input identity mismatch: {identity['path']} "
            f"({size}/{actual_sha256})"
        )
    return {**identity, "verification": "PASS"}


def load_json(path: Path) -> dict[str, Any]:
    """Compatibility name for the strict, duplicate/non-finite rejecting loader."""
    return strict_json_load(path)


def validate_upstream_contracts(p541b: dict[str, Any], p541a: dict[str, Any]) -> None:
    if (p541b.get("schema_version"), p541b.get("task_id")) != (
        INPUT_ARTIFACTS["p541b_json"]["schema_version"],
        INPUT_ARTIFACTS["p541b_json"]["task_id"],
    ):
        raise P541CValidationError("P541B schema/task identity mismatch")
    if (p541a.get("schema_version"), p541a.get("task_id")) != (
        INPUT_ARTIFACTS["p541a_json"]["schema_version"],
        INPUT_ARTIFACTS["p541a_json"]["task_id"],
    ):
        raise P541CValidationError("P541A schema/task identity mismatch")
    records = p541b.get("method_classification_records")
    if not isinstance(records, list) or len(records) != SOURCE_MANIFEST_COUNT:
        raise P541CValidationError("P541B must contain exactly 580 method records")
    required = {
        "method_id", "source_path", "method_family", "recommended_action",
        "runnable_status", "is_actual_prediction_method", "confidence",
        "evidence", "why_not_runnable",
    }
    method_ids: set[str] = set()
    source_paths: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not required <= set(record):
            raise P541CValidationError(f"P541B record contract mismatch at index {index}")
        method_id = record["method_id"]
        source_path = record["source_path"]
        if not isinstance(method_id, str) or not method_id or method_id in method_ids:
            raise P541CValidationError(f"invalid or duplicate method_id at index {index}")
        if not isinstance(source_path, str) or not source_path or source_path in source_paths:
            raise P541CValidationError(f"invalid or duplicate source_path at index {index}")
        method_ids.add(method_id)
        source_paths.add(source_path)
        if record["recommended_action"] not in ALLOWED_RECOMMENDED_ACTIONS:
            raise P541CValidationError(f"unknown recommended_action: {record['recommended_action']}")
        if record["runnable_status"] not in ALLOWED_RUNNABLE_STATUSES:
            raise P541CValidationError(f"unknown runnable_status: {record['runnable_status']}")
        identity = record["is_actual_prediction_method"]
        if identity is not True and identity is not False and identity != "unknown":
            raise P541CValidationError(f"unknown method identity: {method_id}")
        if record["confidence"] not in ("high", "medium", "low"):
            raise P541CValidationError(f"unknown confidence: {method_id}")
        if not isinstance(record["evidence"], list):
            raise P541CValidationError(f"evidence list required: {method_id}")
        flags = parse_evidence_flags(record["evidence"])
        if set(flags) != REQUIRED_EVIDENCE_FLAGS:
            raise P541CValidationError(f"evidence flag contract mismatch: {method_id}")


def load_verified_inputs(
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo_root = repo_root.resolve()
    provenance = {
        name: verify_file_identity(repo_root, identity)
        for name, identity in INPUT_ARTIFACTS.items()
    }
    p541b = strict_json_load(repo_root / INPUT_ARTIFACTS["p541b_json"]["path"])
    p541a = strict_json_load(repo_root / INPUT_ARTIFACTS["p541a_json"]["path"])
    validate_upstream_contracts(p541b, p541a)
    return p541b, p541a, provenance


def parse_evidence_flags(evidence: list) -> dict:
    """Extract the `key=True/False` static-scan flags already recorded by P541B."""
    flags: dict = {}
    for line in evidence:
        m = _EVIDENCE_BOOL_RE.match(line)
        if m:
            if m.group(1) in flags:
                raise P541CValidationError(f"duplicate evidence flag: {m.group(1)}")
            flags[m.group(1)] = m.group(2) == "True"
    return flags


def compute_risk_level(flags: dict) -> str:
    if flags.get("uses_db_anywhere"):
        return "high"
    if flags.get("writes_files_anywhere") or flags.get("hardcoded_abs_path"):
        return "medium"
    return "low"


def _priority_for_adapter(confidence: str, risk: str) -> str:
    if risk == "high":
        return "low"
    if confidence == "high" and risk == "low":
        return "high"
    if confidence in ("high", "medium"):
        return "medium"
    return "low"


def _priority_for_refactor(confidence: str, risk: str) -> str:
    if risk == "high":
        return "low"
    if confidence == "high":
        return "medium"
    return "low"


def source_file_identity(source_path: str, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not isinstance(source_path, str) or not source_path:
        raise P541CValidationError(f"unsafe source_path: {source_path!r}")
    relative = Path(source_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py":
        raise P541CValidationError(f"unsafe source_path: {source_path!r}")
    unresolved = repo_root / relative
    if unresolved.is_symlink():
        raise P541CValidationError(f"symlink source_path rejected: {source_path!r}")
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as exc:
        raise P541CValidationError(f"source_path missing: {source_path!r}") from exc
    if repo_root not in resolved.parents or not resolved.is_file():
        raise P541CValidationError(f"source_path escapes repository: {source_path!r}")
    byte_size = resolved.stat().st_size
    return {
        "source_path": source_path,
        "byte_size": byte_size,
        "sha256": file_sha256(resolved),
    }


def source_exists(source_path: str, repo_root: Path = REPO_ROOT) -> bool:
    try:
        source_file_identity(source_path, repo_root)
    except P541CValidationError:
        return False
    return True


def classify_record(rec: dict, repo_root: Path = REPO_ROOT) -> dict:
    """Map one P541B method_classification_record to a P541C decision record."""
    ra = rec["recommended_action"]
    rs = rec["runnable_status"]
    iapm = rec["is_actual_prediction_method"]
    confidence = rec["confidence"]
    flags = parse_evidence_flags(rec["evidence"])
    if set(flags) != REQUIRED_EVIDENCE_FLAGS:
        raise P541CValidationError(f"evidence flag contract mismatch: {rec['method_id']}")
    risk = compute_risk_level(flags)
    if rs in ("unsafe_side_effects", "imports_db_or_runs_work_at_module_load"):
        # Safety-blocking is a fact about the code regardless of which P541B
        # bucket (duplicate/not-strategy/exclude) ultimately routes it.
        risk = "high"
    source_identity = source_file_identity(rec["source_path"], repo_root)

    if ra == "mark_duplicate":
        dup = rec.get("duplicate_of_existing_strategy")
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="deprecate",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                f"P541B: duplicate of existing replayed strategy '{dup}'; superseded, "
                "not a new replay-readiness candidate."
            ),
            confidence=confidence,
        )
    elif ra == "mark_not_strategy":
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="none",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                "P541B: classified as non-strategy utility/report/tool script; "
                "not a prediction-method candidate."
            ),
            confidence=confidence,
        )
    elif ra == "mark_deprecated":
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay="deprecate",
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason="P541B: classified obsolete/deprecated.",
            confidence=confidence,
        )
    elif ra == "include_in_replay_readiness":
        # P541B already confirmed is_actual_prediction_method == True for this bucket
        # (100% of 142 records); all carry runnable_status=needs_adapter_wrapper.
        priority = _priority_for_adapter(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_ADAPTER,
            required_change_before_replay="adapter_wrapper",
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                "P541B: confirmed actual prediction method needing a small adapter "
                f"wrapper. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "needs_cto_review":
        if rs == "broken_or_import_error":
            decision = dict(
                p541c_decision=DECISION_CTO,
                required_change_before_replay="dependency_fix",
                replay_readiness_priority="unknown",
                risk_level=risk,
                decision_reason=(
                    f"P541B: {rec['why_not_runnable']} Mechanically broken (fails "
                    "static parse); method identity is still undetermined, needs a "
                    "CTO read plus a dependency/syntax fix before further evaluation."
                ),
                confidence=confidence,
            )
        else:
            decision = dict(
                p541c_decision=DECISION_CTO,
                required_change_before_replay="unknown",
                replay_readiness_priority="unknown",
                risk_level=risk,
                decision_reason=(
                    f"P541B: {rec['why_not_runnable']} P541C limited static re-check "
                    "(file existence + reuse of recorded evidence flags) found no "
                    "additional signal beyond what P541B already captured; identity "
                    "remains unresolved."
                ),
                confidence=confidence,
            )
    elif ra == "exclude_from_replay" and rs in (
        "unsafe_side_effects",
        "imports_db_or_runs_work_at_module_load",
    ):
        if flags.get("uses_db_anywhere"):
            required_change = "db_safety_refactor"
        elif flags.get("writes_files_anywhere"):
            required_change = "pure_function_refactor"
        else:
            required_change = "unknown"
        decision = dict(
            p541c_decision=DECISION_EXCLUDE,
            required_change_before_replay=required_change,
            replay_readiness_priority="exclude",
            risk_level=risk,
            decision_reason=(
                f"P541B: {rec['why_not_runnable']} Safety-blocking; excluded "
                "regardless of method-identity confidence."
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay" and iapm is True and rs == "hardcoded_paths_or_dates":
        priority = _priority_for_adapter(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_ADAPTER,
            required_change_before_replay="parameterization",
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                f"P541B: confirmed actual prediction method. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay" and iapm is True and rs in (
        "needs_refactor_to_pure_function",
        "needs_db_safety_refactor",
    ):
        required_change = (
            "pure_function_refactor" if rs == "needs_refactor_to_pure_function" else "db_safety_refactor"
        )
        priority = _priority_for_refactor(confidence, risk)
        decision = dict(
            p541c_decision=DECISION_REFACTOR,
            required_change_before_replay=required_change,
            replay_readiness_priority=priority,
            risk_level=risk,
            decision_reason=(
                f"P541B: confirmed actual prediction method. {rec['why_not_runnable']}"
            ),
            confidence=confidence,
        )
    elif ra == "exclude_from_replay":
        # is_actual_prediction_method == "unknown" (identity itself unresolved) with a
        # mechanically-fixable blocker: defer to CTO review rather than silently
        # excluding or silently promoting a method whose identity is unconfirmed.
        decision = dict(
            p541c_decision=DECISION_CTO,
            required_change_before_replay="unknown",
            replay_readiness_priority="unknown",
            risk_level=risk,
            decision_reason=(
                f"P541B: identity unresolved (is_actual_prediction_method=unknown) "
                f"and {rec['why_not_runnable']} P541C found no additional evidence to "
                "resolve method identity; needs CTO read before any refactor "
                "investment."
            ),
            confidence=confidence,
        )
    else:
        raise P541CValidationError(
            f"unrecognized classification tuple for {rec['method_id']}: {ra}/{rs}/{iapm!r}"
        )

    return {
        "method_id": rec["method_id"],
        "source_path": rec["source_path"],
        "method_family": rec["method_family"],
        "p541b_status": {
            "recommended_action": ra,
            "runnable_status": rs,
            "is_actual_prediction_method": iapm,
            "duplicate_of_existing_strategy": rec.get("duplicate_of_existing_strategy"),
            "confidence": confidence,
        },
        "p541c_decision": decision["p541c_decision"],
        "decision_reason": decision["decision_reason"],
        "required_change_before_replay": decision["required_change_before_replay"],
        "replay_readiness_priority": decision["replay_readiness_priority"],
        "risk_level": decision["risk_level"],
        "evidence": {
            "source_path_exists": True,
            "source_file_identity": source_identity,
            "static_flags": flags,
            "p541b_evidence": rec["evidence"],
        },
        "confidence": decision["confidence"],
    }


def classify_all(p541b: dict, repo_root: Path = REPO_ROOT) -> list:
    return [classify_record(rec, repo_root) for rec in p541b["method_classification_records"]]


def build_shortlist(decisions: list, limit: int = 20) -> list:
    """Deterministic, family-diversified pick of the safest, highest-priority
    adapter-ready candidates. Bucket B only (needs_adapter_before_readiness),
    high priority, low risk -> no DB import/write risk, no unsafe side effects.
    """
    pool = [
        d
        for d in decisions
        if d["p541c_decision"] == DECISION_ADAPTER
        and d["replay_readiness_priority"] == "high"
        and d["risk_level"] == "low"
    ]
    by_family: dict = {}
    for d in sorted(pool, key=lambda d: d["method_id"]):
        by_family.setdefault(d["method_family"], []).append(d)

    shortlist = []
    families = sorted(by_family.keys())
    idx = 0
    while len(shortlist) < limit and any(by_family.values()):
        family = families[idx % len(families)]
        bucket = by_family[family]
        if bucket:
            shortlist.append(bucket.pop(0))
        idx += 1
        if idx > limit * len(families) + len(families):
            break
    return shortlist[:limit]


def determine_next_task(decisions: list, shortlist: list) -> str:
    adapter_ready = [d for d in decisions if d["p541c_decision"] == DECISION_ADAPTER]
    if shortlist:
        return "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE"
    if adapter_ready:
        return "P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE"
    cto = [d for d in decisions if d["p541c_decision"] == DECISION_CTO]
    if cto:
        return "P541D_BIG_LOTTO_CTO_REVIEW_PACKET_FOR_AMBIGUOUS_METHODS"
    return "P541C_COMPLETE_NO_SAFE_REPLAY_READINESS_CANDIDATES"


def summarize(decisions: list) -> dict:
    counts = {k: 0 for k in ALL_DECISIONS}
    for d in decisions:
        counts[d["p541c_decision"]] += 1
    priority_counts = {"high": 0, "medium": 0, "low": 0, "exclude": 0, "unknown": 0}
    for d in decisions:
        priority_counts[d["replay_readiness_priority"]] += 1
    return {
        "total_reviewed_from_p541b": len(decisions),
        "ready_for_replay_readiness_now": counts[DECISION_READY],
        "needs_adapter_before_readiness": counts[DECISION_ADAPTER],
        "needs_refactor_before_readiness": counts[DECISION_REFACTOR],
        "needs_cto_review": counts[DECISION_CTO],
        "exclude_from_replay": counts[DECISION_EXCLUDE],
        "high_priority_candidates": priority_counts["high"],
        "medium_priority_candidates": priority_counts["medium"],
        "low_priority_candidates": priority_counts["low"],
    }


def validate_artifact(artifact: dict[str, Any]) -> None:
    expected_summary = {
        "total_reviewed_from_p541b": 580,
        "ready_for_replay_readiness_now": 0,
        "needs_adapter_before_readiness": 173,
        "needs_refactor_before_readiness": 35,
        "needs_cto_review": 290,
        "exclude_from_replay": 82,
        "high_priority_candidates": 140,
        "medium_priority_candidates": 36,
        "low_priority_candidates": 32,
    }
    if artifact.get("summary") != expected_summary:
        raise P541CValidationError("numerical classification invariant mismatch")
    decisions = artifact.get("reviewed_method_decisions")
    if not isinstance(decisions, list) or len(decisions) != SOURCE_MANIFEST_COUNT:
        raise P541CValidationError("reviewed decision count mismatch")
    method_ids = [decision.get("method_id") for decision in decisions]
    if len(set(method_ids)) != SOURCE_MANIFEST_COUNT:
        raise P541CValidationError("reviewed method IDs are not unique")
    categorized = sum(
        (
            artifact[key]
            for key in (
                "ready_for_replay_readiness_now", "needs_adapter_before_readiness",
                "needs_refactor_before_readiness", "needs_cto_review", "excluded_methods",
            )
        ),
        [],
    )
    if sorted(item["method_id"] for item in categorized) != sorted(method_ids):
        raise P541CValidationError("decision bucket partition mismatch")
    manifest = artifact.get("input_provenance", {}).get("source_manifest", {})
    if manifest.get("sha256") != SOURCE_MANIFEST_SHA256 or manifest.get("verification") != "PASS":
        raise P541CValidationError("source manifest provenance missing or changed")
    if artifact.get("implementation_base_commit") != IMPLEMENTATION_BASE_COMMIT:
        raise P541CValidationError("implementation provenance mismatch")
    canonical_bytes(artifact)


def build_artifact(
    p541b: dict,
    p541a: dict,
    input_provenance: dict[str, Any],
    repo_root: Path = REPO_ROOT,
    generated_at: str | None = None,
) -> dict:
    validate_upstream_contracts(p541b, p541a)
    if set(input_provenance) != set(INPUT_ARTIFACTS):
        raise P541CValidationError("complete four-artifact input provenance required")
    expected_provenance = {
        name: {**identity, "verification": "PASS"}
        for name, identity in INPUT_ARTIFACTS.items()
    }
    if input_provenance != expected_provenance:
        raise P541CValidationError("input provenance identity contract mismatch")
    decisions = classify_all(p541b, repo_root)
    source_manifest = sorted(
        (decision["evidence"]["source_file_identity"] for decision in decisions),
        key=lambda item: item["source_path"],
    )
    source_manifest_digest = hashlib.sha256(canonical_bytes(source_manifest)).hexdigest()
    source_manifest_total_bytes = sum(item["byte_size"] for item in source_manifest)
    if (
        len(source_manifest) != SOURCE_MANIFEST_COUNT
        or source_manifest_total_bytes != SOURCE_MANIFEST_TOTAL_BYTES
        or source_manifest_digest != SOURCE_MANIFEST_SHA256
    ):
        raise P541CValidationError(
            "source manifest identity mismatch: "
            f"{len(source_manifest)}/{source_manifest_total_bytes}/{source_manifest_digest}"
        )
    shortlist = build_shortlist(decisions)
    next_task = determine_next_task(decisions, shortlist)
    if next_task not in NEXT_TASK_OPTIONS:
        raise P541CValidationError(f"unknown next-task classification: {next_task}")

    by_decision = {k: [] for k in ALL_DECISIONS}
    for d in decisions:
        by_decision[d["p541c_decision"]].append(d)

    generated_at = generated_at or GENERATED_AT

    artifact = {
        "schema_version": "1.1",
        "task_id": "P541C_BIG_LOTTO_LEGACY_METHOD_REVIEW_AND_REPLAY_READINESS_SELECTION",
        "generated_at": generated_at,
        "implementation_base_commit": IMPLEMENTATION_BASE_COMMIT,
        "input_provenance": {
            "artifacts": input_provenance,
            "source_manifest": {
                "record_count": len(source_manifest),
                "total_bytes": source_manifest_total_bytes,
                "sha256": source_manifest_digest,
                "canonicalization": "UTF-8 compact sorted-key JSON ordered by source_path",
                "entry_fields": ["source_path", "byte_size", "sha256"],
                "entries_embedded_at": "reviewed_method_decisions[*].evidence.source_file_identity",
                "verification": "PASS",
            },
            "fail_closed": True,
        },
        "summary": summarize(decisions),
        "p541b_context": {
            "p541b_json_path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json",
            "p541b_md_path": "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md",
            "p541b_summary": p541b.get("summary", {}),
            "p541b_recommended_next_task": p541b.get("recommended_next_single_worker_task"),
            "p541a_json_path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
            "p541a_md_path": "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
            "p541a_summary_answer": p541a.get("summary_answer"),
            "p541a_replay_coverage_totals": p541a.get("replay_coverage_totals"),
        },
        "selection_policy": {
            "method": (
                "Deterministic re-bucketing of P541B's 580 method_classification_records "
                "using only fields P541B already computed (recommended_action, "
                "runnable_status, is_actual_prediction_method, confidence, evidence "
                "flags), after exact size/SHA-256 verification of all four consumed "
                "P541A/P541B artifacts. Each repository-relative Python source is "
                "then existence-, boundary-, type-, size-, and SHA-256-verified into "
                "one pinned 580-entry manifest; no source is imported or executed."
            ),
            "bucket_A_ready_for_replay_readiness_now": (
                "P541B's own 'runnable_as_is'/'runnable_with_existing_adapter' records "
                "(5 total) are all mark_duplicate of an already-replayed strategy id, "
                "so bucket A is legitimately empty: P541B did not surface any candidate "
                "that needs zero further work."
            ),
            "bucket_B_needs_adapter_before_readiness": (
                "P541B recommended_action=include_in_replay_readiness (142, all "
                "is_actual_prediction_method=True, all needs_adapter_wrapper/small "
                "effort) PLUS the exclude_from_replay/hardcoded_paths_or_dates records "
                "with is_actual_prediction_method=True (31): both are confirmed real "
                "prediction methods where the only blocker is a wrapper or "
                "parameterization, matching bucket B's definition verbatim."
            ),
            "bucket_C_needs_refactor_before_readiness": (
                "exclude_from_replay/needs_refactor_to_pure_function and "
                "exclude_from_replay/needs_db_safety_refactor records with "
                "is_actual_prediction_method=True: confirmed real methods that need "
                "pure-function extraction or DB-safety refactor before they can be "
                "safely wrapped."
            ),
            "bucket_D_needs_cto_review": (
                "P541B's own needs_cto_review bucket (167) is carried through "
                "unchanged (P541C found no additional resolving evidence), PLUS any "
                "exclude_from_replay record whose is_actual_prediction_method is "
                "'unknown' (identity itself, not just readiness, is unresolved): "
                "deferring these to CTO review instead of silently excluding them or "
                "silently promoting them without confirmed identity."
            ),
            "bucket_E_exclude_from_replay": (
                "mark_not_strategy, mark_duplicate, mark_deprecated (57 total), plus "
                "exclude_from_replay/unsafe_side_effects and "
                "exclude_from_replay/imports_db_or_runs_work_at_module_load (25, "
                "excluded regardless of identity confidence because the blocker is a "
                "code-safety fact, not an identity judgment). Missing, unsafe, or "
                "identity-mismatched source files fail the entire build closed."
            ),
            "risk_level_rule": (
                "high if evidence flag uses_db_anywhere=True; medium if "
                "writes_files_anywhere=True or hardcoded_abs_path=True (and not "
                "already high); else low."
            ),
            "priority_rule": (
                "Bucket B: high if confidence=high and risk=low; medium if "
                "confidence in (high, medium) and risk<=medium; low otherwise; risk=high "
                "always caps at low. Bucket C: medium if confidence=high and risk!=high, "
                "else low. Bucket D/A: unknown/n-a. Bucket E: exclude."
            ),
            "shortlist_rule": (
                "Bucket B members with priority=high and risk=low only (guarantees no "
                "DB import/write risk and no unsafe side effects by construction), "
                "deduplicated by method_id, round-robin diversified across "
                "method_family, capped at 20, sorted deterministically by method_id "
                "within each family."
            ),
        },
        "reviewed_method_decisions": decisions,
        "ready_for_replay_readiness_now": by_decision[DECISION_READY],
        "needs_adapter_before_readiness": by_decision[DECISION_ADAPTER],
        "needs_refactor_before_readiness": by_decision[DECISION_REFACTOR],
        "needs_cto_review": by_decision[DECISION_CTO],
        "excluded_methods": by_decision[DECISION_EXCLUDE],
        "high_priority_candidate_shortlist": shortlist,
        "next_task_recommendation": next_task,
        "provenance_and_limits": {
            "method": (
                "Static, read-only re-bucketing of exactly pinned P541A/P541B "
                "artifacts. Strict JSON rejects duplicate keys and non-finite values. "
                "Every source is a repository-contained, non-symlink Python file "
                "whose size/SHA-256 participates in the pinned source-manifest digest. "
                "No source is imported or executed; no DB access, replay generation, "
                "OOS evaluation, or scoring/promotion gate."
            ),
            "p541b_artifacts_consumed": [
                "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json",
                "outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md",
            ],
            "p541a_artifacts_consumed": [
                "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json",
                "outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md",
            ],
            "not_performed_by_this_task": [
                "No DB write, migration, backfill, or replay row generation.",
                "No OOS evaluator or strategy scoring/promotion gate.",
                "No recomputation of P536-P541B artifacts.",
                "No route/API/UI changes.",
                "No adapter code was written; only the decision to route a method to "
                "needs_adapter_before_readiness / needs_refactor_before_readiness.",
            ],
            "known_limits": [
                "The 167 needs_cto_review records inherited from P541B were not "
                "further resolved: P541B's own static evidence already shows "
                "'no strong static signal either way' for all of them (or a syntax "
                "error for the one broken_or_import_error record), so no additional "
                "P541C-level static heuristic was applied on top of evidence P541B "
                "already weighed and found inconclusive.",
                "Source identity verification reads raw bytes only to compute size and "
                "SHA-256; all 580 sources matched the pinned manifest. This does not "
                "constitute new semantic or runtime analysis.",
                "Risk/priority scoring is a deterministic function of P541B's own "
                "evidence flags; it is a triage aid for the next task, not a safety "
                "guarantee, and does not itself verify runtime behavior.",
            ],
            "disclaimer": DISCLAIMER,
        },
        "disclaimer": DISCLAIMER,
    }
    validate_artifact(artifact)
    return artifact


def render_markdown(artifact: dict) -> str:
    s = artifact["summary"]
    lines = []
    lines.append("# P541C — BIG_LOTTO Legacy Method Review & Replay-Readiness Selection")
    lines.append("")
    lines.append(f"> generated_at: {artifact['generated_at']}")
    lines.append(f"> task_id: {artifact['task_id']}")
    lines.append("")
    lines.append(f"**Disclaimer:** {artifact['disclaimer']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Verified Input Provenance")
    lines.append("")
    lines.append(f"- Implementation base commit: `{artifact['implementation_base_commit']}`")
    lines.append("- Strict JSON policy: duplicate keys and non-finite constants are rejected.")
    lines.append("- Consumed artifacts (exact committed byte identities):")
    for name, identity in artifact["input_provenance"]["artifacts"].items():
        lines.append(
            f"  - `{name}`: `{identity['path']}` — {identity['byte_size']:,} bytes, "
            f"SHA-256 `{identity['sha256']}`, verification **{identity['verification']}**"
        )
    manifest = artifact["input_provenance"]["source_manifest"]
    lines.append(
        f"- Source manifest: **{manifest['record_count']}** repository-contained Python "
        f"files / **{manifest['total_bytes']:,}** bytes / SHA-256 `{manifest['sha256']}` / "
        f"verification **{manifest['verification']}**."
    )
    lines.append("- Fail-closed behavior: any input hash, schema, record, evidence flag, source path, or source-manifest mismatch aborts generation.")
    lines.append("")
    lines.append("## Selection Policy")
    lines.append("")
    for k, v in artifact["selection_policy"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Bucket Sizes")
    lines.append("")
    lines.append(f"- A. ready_for_replay_readiness_now: {len(artifact['ready_for_replay_readiness_now'])}")
    lines.append(f"- B. needs_adapter_before_readiness: {len(artifact['needs_adapter_before_readiness'])}")
    lines.append(f"- C. needs_refactor_before_readiness: {len(artifact['needs_refactor_before_readiness'])}")
    lines.append(f"- D. needs_cto_review: {len(artifact['needs_cto_review'])}")
    lines.append(f"- E. excluded_methods: {len(artifact['excluded_methods'])}")
    lines.append("")
    lines.append(f"## High-Priority Candidate Shortlist (max 20, n={len(artifact['high_priority_candidate_shortlist'])})")
    lines.append("")
    lines.append("| method_id | method_family | source_path | reason |")
    lines.append("|---|---|---|---|")
    for d in artifact["high_priority_candidate_shortlist"]:
        reason = d["decision_reason"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {d['method_id']} | {d['method_family']} | {d['source_path']} | {reason} |")
    lines.append("")
    lines.append(f"## Recommended Next Task")
    lines.append("")
    lines.append(f"`{artifact['next_task_recommendation']}`")
    lines.append("")
    lines.append("## Provenance and Limits")
    lines.append("")
    for k, v in artifact["provenance_and_limits"].items():
        if isinstance(v, list):
            lines.append(f"- **{k}**:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- **{k}**: {v}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p541b, p541a, input_provenance = load_verified_inputs(REPO_ROOT)
    artifact = build_artifact(p541b, p541a, input_provenance)

    date_tag = "20260710"
    out_json = REPO_ROOT / f"outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_{date_tag}.json"
    out_md = REPO_ROOT / f"outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_{date_tag}.md"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(render_markdown(artifact))

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=2))
    print("next_task_recommendation:", artifact["next_task_recommendation"])


if __name__ == "__main__":
    main()
