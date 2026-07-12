"""P541C_R2: BIG_LOTTO legacy method review and replay-readiness selection,
re-based on the P541B_R2 fail-closed safety audit.

Read-only review/selection artifact over a single pinned P541B_R2 input.
Does not touch the DB, does not import or execute any reviewed script, does
not recompute any P536-P541B_R2 artifact. Supersedes the pre-R2 P541C
artifact (PR #663 / outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_20260710.*),
which consumed the retired boolean-only P541B v1 evidence schema and has no
representation for unknown/unresolved transitive risk.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

P541B_R2_JSON = REPO_ROOT / "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"

INPUT_IDENTITY = {
    "path": "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json",
    "byte_size": 10_478_598,
    "sha256": "9c9a28d871113c63f3de024f056d7a4e2d6949e934e76da161a9c891e662103f",
    "schema_version": "p541b-r2-evidence-v1",
    "detector_version": "p541b-r2-detector-v4",
}
SOURCE_MANIFEST_SHA256 = "ca0f84b23f1a3f6613c5f78d6020ec954a3e28fb702152fbf1fa1fb53dbf4e40"
SOURCE_MANIFEST_COUNT = 580
IMPLEMENTATION_BASE_COMMIT = "137dbff5938a74117bb33a4a3db5ccc5de2e8454"
GENERATED_AT = "2026-07-12T00:00:00+00:00"

DISCLAIMER = (
    "Historical legacy method review and replay-readiness selection only; "
    "not a prediction, betting edge, future-winning, or production-readiness claim."
)

BUCKET_READY = "ready_for_replay_readiness_now"
BUCKET_NEEDS_ADAPTER = "needs_adapter_before_readiness"
BUCKET_NEEDS_REFACTOR = "needs_refactor_before_readiness"
BUCKET_NEEDS_CTO_REVIEW = "needs_cto_review"
BUCKET_EXCLUDED = "exclude_from_replay"

ALL_BUCKETS = (
    BUCKET_READY,
    BUCKET_NEEDS_ADAPTER,
    BUCKET_NEEDS_REFACTOR,
    BUCKET_NEEDS_CTO_REVIEW,
    BUCKET_EXCLUDED,
)

EXCLUDE_RECOMMENDED_ACTIONS = {"mark_duplicate", "mark_not_strategy", "mark_deprecated"}
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

SHORTLIST_MAX = 20


class P541CR2ValidationError(ValueError):
    """Raised when committed provenance or a fail-closed contract is violated."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise P541CR2ValidationError("value is not finite canonical JSON") from exc


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
            raise P541CR2ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_load(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise P541CR2ValidationError(f"non-finite JSON constant: {value}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(
                handle,
                object_pairs_hook=_reject_duplicate_object_pairs,
                parse_constant=reject_constant,
            )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P541CR2ValidationError(f"cannot load strict JSON: {path}") from exc
    if not isinstance(value, dict):
        raise P541CR2ValidationError(f"top-level JSON object required: {path}")
    return value


def verify_input_identity(repo_root: Path, identity: dict[str, Any] = INPUT_IDENTITY) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    relative = Path(identity["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise P541CR2ValidationError(f"unsafe input path: {identity['path']!r}")
    unresolved = repo_root / relative
    if unresolved.is_symlink():
        raise P541CR2ValidationError(f"symlink input rejected: {identity['path']!r}")
    try:
        path = unresolved.resolve(strict=True)
        if repo_root not in path.parents or not path.is_file():
            raise P541CR2ValidationError(f"input escapes repository: {identity['path']!r}")
        size = path.stat().st_size
    except OSError as exc:
        raise P541CR2ValidationError(f"required input missing: {identity['path']}") from exc
    actual_sha256 = file_sha256(path)
    if size != identity["byte_size"] or actual_sha256 != identity["sha256"]:
        raise P541CR2ValidationError(
            f"committed input identity mismatch: {identity['path']} "
            f"({size}/{actual_sha256})"
        )
    return {**identity, "verification": "PASS"}


def load_verified_input(repo_root: Path = REPO_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_root = repo_root.resolve()
    provenance = verify_input_identity(repo_root, INPUT_IDENTITY)
    p541b_r2 = strict_json_load(repo_root / INPUT_IDENTITY["path"])
    validate_upstream_contract(p541b_r2)
    return p541b_r2, provenance


def validate_upstream_contract(p541b_r2: dict[str, Any]) -> None:
    if p541b_r2.get("schema_version") != INPUT_IDENTITY["schema_version"]:
        raise P541CR2ValidationError("P541B_R2 schema_version mismatch")
    if p541b_r2.get("detector_version") != INPUT_IDENTITY["detector_version"]:
        raise P541CR2ValidationError("P541B_R2 detector_version mismatch")
    manifest = p541b_r2.get("provenance", {}).get("source_manifest", {})
    if manifest.get("canonical_sha256") != SOURCE_MANIFEST_SHA256:
        raise P541CR2ValidationError("P541B_R2 source manifest sha256 mismatch")
    if manifest.get("record_count") != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("P541B_R2 source manifest record_count mismatch")
    if manifest.get("verification") != "PASS":
        raise P541CR2ValidationError("P541B_R2 source manifest not verified PASS")
    records = p541b_r2.get("method_classification_records")
    if not isinstance(records, list) or len(records) != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("P541B_R2 must contain exactly 580 method records")
    required_top = {"method_id", "source_path", "safety_classification", "historical_p541b_classification"}
    required_safety = {"risk_level", "low_risk_eligible", "disposition", "reasons"}
    required_historical = {
        "method_family", "is_actual_prediction_method", "recommended_action",
        "runnable_status", "confidence", "duplicate_of_existing_strategy", "why_not_runnable",
    }
    method_ids: set[str] = set()
    source_paths: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not required_top <= set(record):
            raise P541CR2ValidationError(f"P541B_R2 record contract mismatch at index {index}")
        method_id = record["method_id"]
        source_path = record["source_path"]
        if not isinstance(method_id, str) or not method_id or method_id in method_ids:
            raise P541CR2ValidationError(f"invalid or duplicate method_id at index {index}")
        if not isinstance(source_path, str) or not source_path or source_path in source_paths:
            raise P541CR2ValidationError(f"invalid or duplicate source_path at index {index}")
        method_ids.add(method_id)
        source_paths.add(source_path)
        safety = record["safety_classification"]
        if not isinstance(safety, dict) or not required_safety <= set(safety):
            raise P541CR2ValidationError(f"safety_classification contract mismatch: {method_id}")
        if safety["risk_level"] not in ("low", "medium", "high", "unknown"):
            raise P541CR2ValidationError(f"unknown risk_level: {method_id}")
        if (safety["risk_level"] == "low") != (safety["low_risk_eligible"] is True):
            raise P541CR2ValidationError(f"low_risk_eligible/risk_level invariant violated: {method_id}")
        historical = record["historical_p541b_classification"]
        if not isinstance(historical, dict) or not required_historical <= set(historical):
            raise P541CR2ValidationError(f"historical_p541b_classification contract mismatch: {method_id}")
        identity = historical["is_actual_prediction_method"]
        if identity is not True and identity is not False and identity != "unknown":
            raise P541CR2ValidationError(f"unknown historical method identity: {method_id}")
        if historical["recommended_action"] not in ALLOWED_RECOMMENDED_ACTIONS:
            raise P541CR2ValidationError(f"unknown recommended_action: {method_id}")
        if historical["runnable_status"] not in ALLOWED_RUNNABLE_STATUSES:
            raise P541CR2ValidationError(f"unknown runnable_status: {method_id}")
        if historical["confidence"] not in ("high", "medium", "low"):
            raise P541CR2ValidationError(f"unknown confidence: {method_id}")


def source_file_identity(source_path: str, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not isinstance(source_path, str) or not source_path:
        raise P541CR2ValidationError(f"unsafe source_path: {source_path!r}")
    relative = Path(source_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py":
        raise P541CR2ValidationError(f"unsafe source_path: {source_path!r}")
    unresolved = repo_root / relative
    if unresolved.is_symlink():
        raise P541CR2ValidationError(f"symlink source_path rejected: {source_path!r}")
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as exc:
        raise P541CR2ValidationError(f"source_path missing: {source_path!r}") from exc
    if repo_root not in resolved.parents or not resolved.is_file():
        raise P541CR2ValidationError(f"source_path escapes repository: {source_path!r}")
    return {
        "source_path": source_path,
        "byte_size": resolved.stat().st_size,
        "sha256": file_sha256(resolved),
    }


def classify_record(rec: dict[str, Any], repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Map one P541B_R2 method_classification_record to a P541C_R2 decision.

    Safety (risk_level) is always the primary, fail-closed gate: unknown never
    resolves to eligible. Replay readiness is then derived from P541B's
    historical runnable_status; low safety risk never means that an adapter or
    refactor requirement has disappeared.
    """
    method_id = rec["method_id"]
    safety = rec["safety_classification"]
    historical = rec["historical_p541b_classification"]
    risk = safety["risk_level"]
    identity = historical["is_actual_prediction_method"]
    recommended_action = historical["recommended_action"]
    source_identity = source_file_identity(rec["source_path"], repo_root)

    # Safety (risk_level) is checked before any identity-based exclusion: an
    # unknown or high risk record must never be routed to EXCLUDED on the
    # strength of a historical duplicate/not-strategy label alone, since that
    # would silently drop an unresolved-risk record from all further review.
    if risk == "unknown":
        bucket = BUCKET_NEEDS_CTO_REVIEW
        priority = "unknown"
        required_change = "unknown"
        reason = (
            f"P541B_R2: risk_level=unknown, disposition={safety['disposition']}; "
            "unresolved transitive/one-hop risk carried through verbatim, never "
            "resolved to safe, regardless of historical recommended_action "
            f"({recommended_action!r})."
        )
    elif risk == "high":
        bucket = BUCKET_EXCLUDED
        priority = "exclude"
        required_change = "unknown"
        reason = (
            f"P541B_R2: risk_level=high, disposition={safety['disposition']}; "
            "safety-blocking, excluded regardless of method-identity confidence."
        )
    elif recommended_action in EXCLUDE_RECOMMENDED_ACTIONS:
        bucket = BUCKET_EXCLUDED
        priority = "exclude"
        required_change = "deprecate"
        reason = (
            f"P541B historical: {recommended_action}; superseded/non-strategy, "
            "excluded regardless of P541B_R2 risk_level."
        )
    elif identity == "unknown":
        bucket = BUCKET_NEEDS_CTO_REVIEW
        priority = "unknown"
        required_change = "identity_confirmation"
        reason = (
            f"P541B_R2: risk_level={risk} ({safety['disposition']}), but P541B historical "
            "method identity is unresolved (is_actual_prediction_method=unknown). "
            "Safety and identity remain separate; needs CTO identity review before any "
            "readiness investment."
        )
    elif identity is False:
        bucket = BUCKET_EXCLUDED
        priority = "exclude"
        required_change = "none"
        reason = (
            f"P541B_R2: risk_level={risk} ({safety['disposition']}), but P541B historical "
            "confirms this is not an actual prediction method; not a replay-readiness "
            "candidate regardless of safety."
        )
    else:
        runnable_status = historical["runnable_status"]
        confidence = historical["confidence"]
        if runnable_status == "runnable_with_existing_adapter":
            bucket = BUCKET_READY
            required_change = "none"
        elif runnable_status == "needs_adapter_wrapper":
            bucket = BUCKET_NEEDS_ADAPTER
            required_change = "adapter_wrapper"
        elif runnable_status == "hardcoded_paths_or_dates":
            bucket = BUCKET_NEEDS_ADAPTER
            required_change = "parameterization"
        elif runnable_status in ("needs_refactor_to_pure_function", "needs_db_safety_refactor"):
            bucket = BUCKET_NEEDS_REFACTOR
            required_change = (
                "pure_function_refactor"
                if runnable_status == "needs_refactor_to_pure_function"
                else "db_safety_refactor"
            )
        else:
            bucket = BUCKET_NEEDS_CTO_REVIEW
            priority = "unknown"
            required_change = "unknown"
            reason = (
                f"P541B_R2: risk_level={risk} ({safety['disposition']}); confirmed method "
                f"has non-actionable runnable_status={runnable_status!r}; fail-closed CTO "
                "review required."
            )
        if bucket != BUCKET_NEEDS_CTO_REVIEW:
            if bucket == BUCKET_READY:
                priority = "n-a"
            elif bucket == BUCKET_NEEDS_REFACTOR:
                priority = "medium" if confidence == "high" else "low"
            elif confidence == "high" and risk == "low":
                priority = "high"
            elif confidence in ("high", "medium"):
                priority = "medium"
            else:
                priority = "low"
            reason = (
                f"P541B_R2: risk_level={risk} ({safety['disposition']}); P541B historical: "
                f"confirmed actual prediction method with runnable_status={runnable_status}. "
                f"Readiness requirement preserved as {required_change}."
            )

    return {
        "method_id": method_id,
        "source_path": rec["source_path"],
        "method_family": historical["method_family"],
        "p541b_r2_status": {
            "risk_level": risk,
            "low_risk_eligible": safety["low_risk_eligible"],
            "disposition": safety["disposition"],
            "reasons": safety["reasons"],
        },
        "historical_p541b_status": {
            "recommended_action": recommended_action,
            "runnable_status": historical["runnable_status"],
            "is_actual_prediction_method": identity,
            "duplicate_of_existing_strategy": historical["duplicate_of_existing_strategy"],
            "confidence": historical["confidence"],
        },
        "p541c_r2_bucket": bucket,
        "p541c_decision": bucket,
        "decision_reason": reason,
        "required_change_before_replay": required_change,
        "replay_readiness_priority": priority,
        "evidence": {
            "source_path_exists": True,
            "source_file_identity": source_identity,
        },
    }


def classify_all(p541b_r2: dict[str, Any], repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    return [classify_record(rec, repo_root) for rec in p541b_r2["method_classification_records"]]


def build_shortlist(decisions: list[dict[str, Any]], limit: int = SHORTLIST_MAX) -> list[dict[str, Any]]:
    """Deterministic, family-diversified pick of safest high-priority adapters.

    Never pads: if fewer than `limit` records qualify, the shortlist is
    exactly that (possibly smaller) set, not artificially inflated.
    """
    pool = [
        d for d in decisions
        if d["p541c_r2_bucket"] == BUCKET_NEEDS_ADAPTER
        and d["p541b_r2_status"]["risk_level"] == "low"
        and d["replay_readiness_priority"] == "high"
        and d["historical_p541b_status"]["is_actual_prediction_method"] is True
    ]
    by_family: dict[str, list[dict[str, Any]]] = {}
    for d in sorted(pool, key=lambda d: d["method_id"]):
        by_family.setdefault(d["method_family"], []).append(d)

    shortlist: list[dict[str, Any]] = []
    families = sorted(by_family.keys())
    if not families:
        return shortlist
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


def summarize(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {k: 0 for k in ALL_BUCKETS}
    for d in decisions:
        counts[d["p541c_r2_bucket"]] += 1
    return {
        "total_reviewed_from_p541b_r2": len(decisions),
        BUCKET_READY: counts[BUCKET_READY],
        BUCKET_NEEDS_ADAPTER: counts[BUCKET_NEEDS_ADAPTER],
        BUCKET_NEEDS_REFACTOR: counts[BUCKET_NEEDS_REFACTOR],
        BUCKET_NEEDS_CTO_REVIEW: counts[BUCKET_NEEDS_CTO_REVIEW],
        BUCKET_EXCLUDED: counts[BUCKET_EXCLUDED],
    }


def validate_artifact(artifact: dict[str, Any]) -> None:
    decisions = artifact.get("reviewed_method_decisions")
    if not isinstance(decisions, list) or len(decisions) != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("reviewed decision count mismatch")
    method_ids = [d["method_id"] for d in decisions]
    if len(set(method_ids)) != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("reviewed method IDs are not unique")
    for d in decisions:
        if d["p541b_r2_status"]["risk_level"] == "unknown" and d["p541c_r2_bucket"] != BUCKET_NEEDS_CTO_REVIEW:
            raise P541CR2ValidationError(
                f"fail-closed invariant violated: unknown risk routed to {d['p541c_r2_bucket']}: {d['method_id']}"
            )
    shortlist_ids = {d["method_id"] for d in artifact["high_priority_candidate_shortlist"]}
    for d in decisions:
        if d["method_id"] in shortlist_ids:
            if d["p541c_r2_bucket"] != BUCKET_NEEDS_ADAPTER:
                raise P541CR2ValidationError(f"shortlist contains non-adapter record: {d['method_id']}")
            if d["historical_p541b_status"]["is_actual_prediction_method"] is not True:
                raise P541CR2ValidationError(f"shortlist contains identity-unresolved record: {d['method_id']}")
            if d["required_change_before_replay"] == "none":
                raise P541CR2ValidationError(f"shortlist loses readiness requirement: {d['method_id']}")
            if d["replay_readiness_priority"] != "high":
                raise P541CR2ValidationError(f"shortlist contains non-high-priority record: {d['method_id']}")
    by_bucket_total = (
        len(artifact[BUCKET_READY])
        + len(artifact[BUCKET_NEEDS_ADAPTER])
        + len(artifact[BUCKET_NEEDS_REFACTOR])
        + len(artifact[BUCKET_NEEDS_CTO_REVIEW])
        + len(artifact["excluded_methods"])
    )
    if by_bucket_total != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("bucket partition does not sum to 580")
    canonical_bytes(artifact)


def build_artifact(
    p541b_r2: dict[str, Any],
    input_provenance: dict[str, Any],
    repo_root: Path = REPO_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    validate_upstream_contract(p541b_r2)
    if input_provenance.get("verification") != "PASS":
        raise P541CR2ValidationError("input provenance not verified PASS")
    decisions = classify_all(p541b_r2, repo_root)
    shortlist = build_shortlist(decisions)

    by_bucket: dict[str, list[dict[str, Any]]] = {k: [] for k in ALL_BUCKETS}
    for d in decisions:
        by_bucket[d["p541c_r2_bucket"]].append(d)

    if by_bucket[BUCKET_NEEDS_ADAPTER] or by_bucket[BUCKET_NEEDS_REFACTOR] or by_bucket[BUCKET_NEEDS_CTO_REVIEW]:
        next_task = "P541D_R2_BIG_LOTTO_ADAPTER_DESIGN_OR_CTO_REVIEW_NO_DB_WRITE"
    elif shortlist:
        next_task = "P541D_R2_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE"
    else:
        next_task = "P541C_R2_COMPLETE_NO_SAFE_REPLAY_READINESS_CANDIDATES"

    generated_at = generated_at or GENERATED_AT

    artifact = {
        "schema_version": "p541c-r2-selection-v2",
        "task_id": "P541C_R2_BIG_LOTTO_LEGACY_METHOD_REVIEW_READINESS_SELECTION_REPLACEMENT",
        "generated_at": generated_at,
        "implementation_base_commit": IMPLEMENTATION_BASE_COMMIT,
        "supersedes": {
            "task_id": "P541C_BIG_LOTTO_LEGACY_METHOD_REVIEW_AND_REPLAY_READINESS_SELECTION",
            "artifacts": [
                "outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_20260710.json",
                "outputs/research/p541c_biglotto_legacy_method_review_readiness_selection_20260710.md",
            ],
            "overwrite_policy": "HISTORICAL_ARTIFACTS_PRESERVED",
            "reason": (
                "Pre-R2 P541C consumed the retired boolean-only P541B v1 evidence schema, "
                "which has no unknown state and coerces missing/absent evidence flags to "
                "low risk. Cross-checked against P541B_R2: 135/140 (96%) of its shortlist- "
                "eligible pool and 19/20 of its published shortlist are no longer "
                "confirmed low-risk under the fail-closed P541B_R2 audit."
            ),
        },
        "input_provenance": {
            "artifact": input_provenance,
            "fail_closed": True,
        },
        "contract_reconciliation": {
            "task_id": "P541C_R2_PR686_CONTRACT_RECONCILIATION_R1",
            "status": "PASS",
            "reconciled_invariant": (
                "P541B_R2 safety risk and historical replay readiness are orthogonal: "
                "risk_level=low does not erase runnable_status or required change."
            ),
            "prior_drift": (
                "PR #686 v1 labeled 12 low-risk confirmed methods safe_confirmed_method "
                "with required_change_before_replay=none even though all 12 upstream "
                "records say runnable_status=needs_adapter_wrapper."
            ),
        },
        "summary": summarize(decisions),
        "bucket_definitions": {
            BUCKET_READY: (
                "P541B_R2 risk_level=low, historical identity confirmed, and historical "
                "runnable_status=runnable_with_existing_adapter. No readiness change remains."
            ),
            BUCKET_NEEDS_ADAPTER: (
                "Confirmed method whose historical runnable_status requires an adapter "
                "wrapper or parameterization. Low-risk/high-confidence members alone may "
                "enter the shortlist."
            ),
            BUCKET_NEEDS_REFACTOR: (
                "Confirmed method whose historical runnable_status requires pure-function "
                "or DB-safety refactoring. High safety risk remains excluded."
            ),
            BUCKET_NEEDS_CTO_REVIEW: (
                "P541B_R2 risk_level=unknown (any identity), unresolved historical identity "
                "at low/medium risk, or a confirmed method with a non-actionable readiness "
                "status. Unresolved risk is never resolved to safe."
            ),
            BUCKET_EXCLUDED: (
                "P541B_R2 risk_level=high (any identity, safety-blocking regardless of "
                "confidence), OR P541B historical recommended_action is mark_duplicate/"
                "mark_not_strategy/mark_deprecated, OR risk_level=low with "
                "is_actual_prediction_method=False (safe but not a prediction method)."
            ),
        },
        "selection_policy": {
            "safety_first_rule": (
                "P541B_R2 risk_level is evaluated first: unknown routes to CTO review and "
                "high routes to exclusion before historical identity/readiness can refine a bucket."
            ),
            "readiness_rule": (
                "For low/medium-risk confirmed methods, historical runnable_status maps to "
                "ready, adapter, or refactor without being erased by the safety tier."
            ),
            "priority_rule": (
                "Adapter: high only when confidence=high and risk=low; medium when confidence "
                "is high/medium and risk is not high; low otherwise. Refactor: medium only "
                "when confidence=high and risk is not high; low otherwise."
            ),
            "shortlist_rule": (
                "needs_adapter_before_readiness members only with P541B_R2 risk_level=low, "
                "confirmed method identity, and historical confidence=high; deduplicated by "
                "method_id, round-robin diversified across method_family, capped at "
                f"{SHORTLIST_MAX}, sorted deterministically by method_id within each family. "
                "Never padded: if fewer candidates qualify, the shortlist is exactly that "
                "smaller set."
            ),
        },
        "reviewed_method_decisions": decisions,
        BUCKET_READY: by_bucket[BUCKET_READY],
        BUCKET_NEEDS_ADAPTER: by_bucket[BUCKET_NEEDS_ADAPTER],
        BUCKET_NEEDS_REFACTOR: by_bucket[BUCKET_NEEDS_REFACTOR],
        BUCKET_NEEDS_CTO_REVIEW: by_bucket[BUCKET_NEEDS_CTO_REVIEW],
        "excluded_methods": by_bucket[BUCKET_EXCLUDED],
        "high_priority_candidate_shortlist": shortlist,
        "next_task_recommendation": next_task,
        "provenance_and_limits": {
            "method": (
                "Static, read-only re-bucketing of exactly one pinned P541B_R2 artifact "
                "(which already embeds historical P541B v1 identity fields per record). "
                "Strict JSON rejects duplicate keys and non-finite values. Every source "
                "is a repository-contained, non-symlink Python file whose size/SHA-256 is "
                "recorded per decision. No source is imported or executed; no DB access, "
                "replay generation, or scoring/promotion gate."
            ),
            "p541b_r2_artifact_consumed": [INPUT_IDENTITY["path"]],
            "not_performed_by_this_task": [
                "No DB write, migration, backfill, or replay row generation.",
                "No OOS evaluator or strategy scoring/promotion gate.",
                "No recomputation of P536-P541B_R2 artifacts.",
                "No route/API/UI changes.",
                "No adapter code was written; only the decision to route a method to "
                "needs_adapter_or_refactor_before_readiness / needs_cto_review.",
            ],
            "known_limits": [
                "needs_cto_review records (from unknown risk or unresolved/negative "
                "identity at medium risk) were not further resolved; P541B_R2's own "
                "evidence already represents the limit of static analysis.",
                "Source identity verification reads raw bytes only to compute size and "
                "SHA-256; this does not constitute new semantic or runtime analysis.",
                "Bucket/priority assignment is a deterministic function of P541B_R2's "
                "risk evidence plus P541B's historical identity, runnable_status, and "
                "confidence fields; it is a "
                "triage aid for the next task, not a safety guarantee.",
            ],
            "disclaimer": DISCLAIMER,
        },
        "disclaimer": DISCLAIMER,
    }
    validate_artifact(artifact)
    return artifact


def render_markdown(artifact: dict[str, Any]) -> str:
    s = artifact["summary"]
    lines = []
    lines.append("# P541C_R2 — BIG_LOTTO Legacy Method Review & Replay-Readiness Selection")
    lines.append("")
    lines.append(f"> generated_at: {artifact['generated_at']}")
    lines.append(f"> task_id: {artifact['task_id']}")
    lines.append("")
    lines.append(f"**Disclaimer:** {artifact['disclaimer']}")
    lines.append("")
    lines.append("## Supersedes")
    lines.append("")
    lines.append(f"- task_id: `{artifact['supersedes']['task_id']}`")
    lines.append(f"- overwrite_policy: {artifact['supersedes']['overwrite_policy']}")
    lines.append(f"- reason: {artifact['supersedes']['reason']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    for k, v in s.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Contract Reconciliation")
    lines.append("")
    reconciliation = artifact["contract_reconciliation"]
    lines.append(f"- task_id: `{reconciliation['task_id']}`")
    lines.append(f"- status: **{reconciliation['status']}**")
    lines.append(f"- reconciled_invariant: {reconciliation['reconciled_invariant']}")
    lines.append(f"- prior_drift: {reconciliation['prior_drift']}")
    lines.append("")
    lines.append("## Verified Input Provenance")
    lines.append("")
    lines.append(f"- Implementation base commit: `{artifact['implementation_base_commit']}`")
    identity = artifact["input_provenance"]["artifact"]
    lines.append(
        f"- Input: `{identity['path']}` — {identity['byte_size']:,} bytes, SHA-256 "
        f"`{identity['sha256']}`, verification **{identity['verification']}**"
    )
    lines.append("- Fail-closed behavior: any input hash, schema, record, or contract mismatch aborts generation.")
    lines.append("")
    lines.append("## Bucket Definitions")
    lines.append("")
    for k, v in artifact["bucket_definitions"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append(f"## Shortlist Rule")
    lines.append("")
    lines.append(artifact["selection_policy"]["shortlist_rule"])
    lines.append("")
    lines.append(f"## Shortlist (n={len(artifact['high_priority_candidate_shortlist'])})")
    lines.append("")
    lines.append("| method_id | method_family | source_path | reason |")
    lines.append("|---|---|---|---|")
    for d in artifact["high_priority_candidate_shortlist"]:
        reason = d["decision_reason"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {d['method_id']} | {d['method_family']} | {d['source_path']} | {reason} |")
    lines.append("")
    lines.append("## Recommended Next Task")
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
    p541b_r2, input_provenance = load_verified_input(REPO_ROOT)
    artifact = build_artifact(p541b_r2, input_provenance)

    date_tag = "20260712"
    out_json = REPO_ROOT / f"outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_{date_tag}.json"
    out_md = REPO_ROOT / f"outputs/research/p541c_r2_biglotto_legacy_method_review_readiness_selection_{date_tag}.md"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(render_markdown(artifact))

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=2))
    print("shortlist size:", len(artifact["high_priority_candidate_shortlist"]))
    print("next_task_recommendation:", artifact["next_task_recommendation"])


if __name__ == "__main__":
    main()
