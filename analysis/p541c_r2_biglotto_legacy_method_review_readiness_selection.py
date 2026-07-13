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

import hashlib
import json
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
    "source_manifest_sha256": "ca0f84b23f1a3f6613c5f78d6020ec954a3e28fb702152fbf1fa1fb53dbf4e40",
    "record_count": 580,
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
SELECTOR_VERSION = "p541c-r2-selector-v4"
FINALIZATION_TASK_ID = "P541C_R2_PR686_ATOMIC_PINNED_INPUT_BINDING_REPAIR_R4"
ATOMIC_INPUT_BINDING_STATEMENT = (
    "The pinned upstream input is read once into bytes; byte size, SHA-256, strict "
    "UTF-8 decoding, and strict JSON parsing are all applied to the same immutable "
    "byte buffer."
)


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


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P541CR2ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_load_bytes(raw: bytes, source: str = "<bytes>") -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise P541CR2ValidationError(f"non-finite JSON constant: {value}")

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P541CR2ValidationError(f"invalid UTF-8 JSON: {source}") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise P541CR2ValidationError(f"cannot parse strict JSON: {source}") from exc
    if not isinstance(value, dict):
        raise P541CR2ValidationError(f"top-level JSON object required: {source}")
    return value


def strict_json_load(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise P541CR2ValidationError(f"cannot load strict JSON: {path}") from exc
    return strict_json_load_bytes(raw, str(path))


def read_verified_input_bytes(
    repo_root: Path,
    identity: dict[str, Any] = INPUT_IDENTITY,
) -> tuple[bytes, dict[str, Any]]:
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
        with path.open("rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise P541CR2ValidationError(f"required input missing: {identity['path']}") from exc
    size = len(raw)
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if size != identity["byte_size"] or actual_sha256 != identity["sha256"]:
        raise P541CR2ValidationError(
            f"committed input identity mismatch: {identity['path']} "
            f"({size}/{actual_sha256})"
        )
    provenance = {
        **identity,
        "byte_size": size,
        "sha256": actual_sha256,
        "verification": "PASS",
        "atomic_same_byte_binding": ATOMIC_INPUT_BINDING_STATEMENT,
    }
    return raw, provenance


def verify_input_identity(
    repo_root: Path,
    identity: dict[str, Any] = INPUT_IDENTITY,
) -> dict[str, Any]:
    _, provenance = read_verified_input_bytes(repo_root, identity)
    return provenance


def load_verified_input(repo_root: Path = REPO_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, provenance = read_verified_input_bytes(repo_root, INPUT_IDENTITY)
    p541b_r2 = strict_json_load_bytes(raw, INPUT_IDENTITY["path"])
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
        if not isinstance(safety["low_risk_eligible"], bool):
            raise P541CR2ValidationError(f"low_risk_eligible must be boolean: {method_id}")
        if not isinstance(safety["disposition"], str) or not safety["disposition"]:
            raise P541CR2ValidationError(f"invalid safety disposition: {method_id}")
        if not isinstance(safety["reasons"], list) or not all(
            isinstance(reason, str) for reason in safety["reasons"]
        ):
            raise P541CR2ValidationError(f"invalid safety reasons: {method_id}")
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
        if not isinstance(historical["method_family"], str) or not historical["method_family"]:
            raise P541CR2ValidationError(f"invalid method_family: {method_id}")
        if not isinstance(historical["why_not_runnable"], str):
            raise P541CR2ValidationError(f"invalid why_not_runnable: {method_id}")


def classify_record(rec: dict[str, Any]) -> dict[str, Any]:
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
        if runnable_status == "runnable_with_existing_adapter" and risk == "low":
            bucket = BUCKET_READY
            required_change = "none"
        elif runnable_status == "runnable_with_existing_adapter":
            bucket = BUCKET_NEEDS_CTO_REVIEW
            priority = "unknown"
            required_change = "safety_review"
            reason = (
                f"P541B_R2: risk_level={risk} ({safety['disposition']}); historical "
                "adapter readiness does not satisfy the low-risk safety prerequisite. "
                "Fail-closed CTO safety review required."
            )
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
            "source_path_contract": "identifier_only_from_pinned_p541b_r2",
        },
    }


def classify_all(p541b_r2: dict[str, Any]) -> list[dict[str, Any]]:
    return [classify_record(rec) for rec in p541b_r2["method_classification_records"]]


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
    if artifact.get("schema_version") != "p541c-r2-selection-v3":
        raise P541CR2ValidationError("artifact schema_version mismatch")
    if artifact.get("selector_version") != SELECTOR_VERSION:
        raise P541CR2ValidationError("artifact selector_version mismatch")
    reconciliation = artifact.get("contract_reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("task_id") != FINALIZATION_TASK_ID:
        raise P541CR2ValidationError("contract finalization task mismatch")
    if reconciliation.get("status") != "PASS":
        raise P541CR2ValidationError("contract reconciliation not PASS")
    decisions = artifact.get("reviewed_method_decisions")
    if not isinstance(decisions, list) or len(decisions) != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("reviewed decision count mismatch")
    method_ids = [d["method_id"] for d in decisions]
    if len(set(method_ids)) != SOURCE_MANIFEST_COUNT:
        raise P541CR2ValidationError("reviewed method IDs are not unique")
    for d in decisions:
        bucket = d["p541c_r2_bucket"]
        if bucket not in ALL_BUCKETS or d.get("p541c_decision") != bucket:
            raise P541CR2ValidationError(f"decision bucket mismatch: {d['method_id']}")
        risk = d["p541b_r2_status"]["risk_level"]
        if risk == "unknown" and bucket != BUCKET_NEEDS_CTO_REVIEW:
            raise P541CR2ValidationError(
                f"fail-closed invariant violated: unknown risk routed to {bucket}: {d['method_id']}"
            )
        if risk == "high" and bucket != BUCKET_EXCLUDED:
            raise P541CR2ValidationError(
                f"fail-closed invariant violated: high risk routed to {bucket}: {d['method_id']}"
            )
        if bucket == BUCKET_READY and (
            risk != "low"
            or d["historical_p541b_status"]["is_actual_prediction_method"] is not True
            or d["historical_p541b_status"]["runnable_status"] != "runnable_with_existing_adapter"
            or d["required_change_before_replay"] != "none"
        ):
            raise P541CR2ValidationError(f"ready contract mismatch: {d['method_id']}")

    expected_summary = summarize(decisions)
    if artifact.get("summary") != expected_summary:
        raise P541CR2ValidationError("summary does not match reviewed decisions")

    bucket_keys = {
        BUCKET_READY: BUCKET_READY,
        BUCKET_NEEDS_ADAPTER: BUCKET_NEEDS_ADAPTER,
        BUCKET_NEEDS_REFACTOR: BUCKET_NEEDS_REFACTOR,
        BUCKET_NEEDS_CTO_REVIEW: BUCKET_NEEDS_CTO_REVIEW,
        BUCKET_EXCLUDED: "excluded_methods",
    }
    for bucket, artifact_key in bucket_keys.items():
        expected = [d for d in decisions if d["p541c_r2_bucket"] == bucket]
        if artifact.get(artifact_key) != expected:
            raise P541CR2ValidationError(f"bucket partition mismatch: {bucket}")

    expected_shortlist = build_shortlist(decisions)
    if artifact.get("high_priority_candidate_shortlist") != expected_shortlist:
        raise P541CR2ValidationError("shortlist does not match canonical selection")
    canonical_bytes(artifact)


def build_artifact(
    p541b_r2: dict[str, Any],
    input_provenance: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    validate_upstream_contract(p541b_r2)
    if input_provenance.get("verification") != "PASS":
        raise P541CR2ValidationError("input provenance not verified PASS")
    decisions = classify_all(p541b_r2)
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
        "schema_version": "p541c-r2-selection-v3",
        "selector_version": SELECTOR_VERSION,
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
            "task_id": FINALIZATION_TASK_ID,
            "status": "PASS",
            "reconciled_invariant": (
                "Ready requires both low safety risk and explicit historical adapter "
                "readiness; summary, bucket partitions, and shortlist must be exact "
                "canonical projections of the reviewed decisions. source_path is an "
                "identifier inherited from the pinned P541B_R2 input, not a checkout probe. "
                + ATOMIC_INPUT_BINDING_STATEMENT
            ),
            "prior_drift": (
                "Earlier revisions coupled selection to mutable checkout source files and "
                "then verified and parsed the pinned input through separate path reads. The "
                "selector now consumes one verified immutable input buffer only."
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
                "at low/medium risk, a medium-risk method otherwise adapter-ready, or a "
                "confirmed method with a non-actionable readiness status. Unresolved or "
                "non-low risk is never resolved to ready."
            ),
            BUCKET_EXCLUDED: (
                "P541B_R2 risk_level=high (any identity, safety-blocking regardless of "
                "confidence), OR P541B historical recommended_action is mark_duplicate/"
                "mark_not_strategy/mark_deprecated, OR risk_level=low/medium with "
                "is_actual_prediction_method=False (not a prediction method)."
            ),
        },
        "selection_policy": {
            "safety_first_rule": (
                "P541B_R2 risk_level is evaluated first: unknown routes to CTO review and "
                "high routes to exclusion before historical identity/readiness can refine a bucket."
            ),
            "readiness_rule": (
                "For confirmed methods, ready additionally requires low risk; adapter and "
                "refactor requirements remain explicit at low/medium risk, while an otherwise "
                "adapter-ready medium-risk method routes to CTO safety review."
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
                + ATOMIC_INPUT_BINDING_STATEMENT + " Strict JSON rejects duplicate keys and "
                "non-finite values. source_path is "
                "retained only as an identifier from that pinned input; no reviewed source "
                "is resolved, opened, statted, hashed, imported or executed. No DB access, "
                "replay generation, or scoring/promotion gate."
            ),
            "p541b_r2_artifact_consumed": [INPUT_IDENTITY["path"]],
            "not_performed_by_this_task": [
                "No DB write, migration, backfill, or replay row generation.",
                "No OOS evaluator or strategy scoring/promotion gate.",
                "No recomputation of P536-P541B_R2 artifacts.",
                "No route/API/UI changes.",
                "No adapter code was written; only the decision to route a method to "
                "needs_adapter_before_readiness / needs_refactor_before_readiness / "
                "needs_cto_review.",
            ],
            "known_limits": [
                "needs_cto_review records (from unknown risk, unresolved identity, or a "
                "non-actionable safety/readiness combination) were not further resolved; "
                "P541B_R2's own evidence already represents the limit of static analysis.",
                "No current-checkout source existence or identity claim is made; source_path "
                "stability is inherited from the pinned P541B_R2 artifact contract.",
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
    lines.append(f"> selector_version: {artifact['selector_version']}")
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
    lines.append(
        f"- Upstream contract: schema `{identity['schema_version']}`, detector "
        f"`{identity['detector_version']}`, manifest "
        f"`{identity['source_manifest_sha256']}`, records {identity['record_count']}"
    )
    lines.append(f"- Atomic input binding: {identity['atomic_same_byte_binding']}")
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
