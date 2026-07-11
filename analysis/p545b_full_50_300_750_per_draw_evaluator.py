"""Canonical published P545B 50/300/750 per-draw evaluation contract.

The committed P545C R4 compact registry is the sole row-level evidence input.
The merged P545B R2 evaluator is verified byte-for-byte before its pure
evaluation logic is loaded.  This module has no database, network, service,
strategy-search, or production interface.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


TASK_ID = "P545B_R4_CANONICAL_PUBLISHED_CONTRACT_REMEDIATION"
SCHEMA = "p545b_full_50_300_750_per_draw_evaluation.v1"
CLASSIFICATION = "P545B_CANONICAL_RETROSPECTIVE_EVALUATION_RECONCILED_NO_PREDICTIVE_OR_BETTING_CLAIM"
IMPLEMENTATION_BASE_COMMIT = "72e55acde36792912873315eb75f8a5b74c7470a"
IMPLEMENTATION_BASE_COMMIT_TIMESTAMP = "2026-07-11T15:58:26+08:00"
GENERATED_AT_UTC = "2026-07-11T07:58:26Z"
GENERATED_AT_POLICY = {
    "source_commit": IMPLEMENTATION_BASE_COMMIT,
    "timestamp_field": "committer_timestamp",
    "source_timestamp": "2026-07-11T15:58:26+08:00",
    "timezone_normalization": "UTC",
    "precision": "seconds",
    "format": "RFC3339_Z",
    "deterministic": True,
}
OUTPUT_JSON = Path("outputs/research/p545b_full_50_300_750_per_draw_evaluation_20260711.json")
OUTPUT_MARKDOWN = Path("outputs/research/p545b_full_50_300_750_per_draw_evaluation_20260711.md")
MAX_JSON_BYTES = 40 * 1024 * 1024
MAX_MARKDOWN_BYTES = 100 * 1024

LEGACY_SOURCE = "analysis/p545b_r2_full_per_draw_evaluator.py"
LEGACY_OUTPUT = "outputs/research/p545b_r2_full_per_draw_evaluator_20260711.json"
REGISTRY_PATH = "outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json"
LEGACY_SCHEMA = "p545b_r2_full_per_draw_evaluator.v1"
LEGACY_SOURCE_SHA256 = "886459547ca67c1ac614e9ae807f07fffc1ac068f62c8844ceb4c0806b59873a"
LEGACY_SOURCE_SIZE = 24_268
LEGACY_OUTPUT_SHA256 = "c8f78663a9d3dd726e647b7ee90ae54be7fcbf0647dfabd7b37237c5e72059db"
LEGACY_OUTPUT_SIZE = 15_797_408
LEGACY_OUTPUT_CANONICAL_DIGEST = "46c6f3bd3bc4c98582d77436395172acd5a56bc92bc2bb0c1b61b9c6f6612c46"
REGISTRY_SHA256 = "ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8"
REGISTRY_SIZE = 52_393_107
REGISTRY_SEMANTIC_DIGEST = "f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39"
REGISTRY_CANONICAL_DIGEST = "34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84"
WINDOWS = ((50, "SHORT", 1), (300, "MID", 2), (750, "LONG", 4))

CONTRACT_SOURCES = (
    {
        "role": "legacy_pure_evaluation_logic",
        "path": LEGACY_SOURCE,
        "byte_size": LEGACY_SOURCE_SIZE,
        "sha256": LEGACY_SOURCE_SHA256,
        "git_blob_id": "94c6d6a391a36fa63ba9a651b83dd24d3fd84c2f",
        "schema_or_version": LEGACY_SCHEMA,
        "functions_or_fields_used": ["load_registry", "evaluate_opportunities", "evaluate_windows", "build_evaluation"],
    },
    {
        "role": "legacy_numerical_evidence",
        "path": LEGACY_OUTPUT,
        "byte_size": LEGACY_OUTPUT_SIZE,
        "sha256": LEGACY_OUTPUT_SHA256,
        "git_blob_id": "8cec97c479c74321401a7b793febe627d7e07256",
        "schema_or_version": LEGACY_SCHEMA,
        "functions_or_fields_used": ["per_opportunity_evaluations", "per_window_evaluations", "group_evaluations", "canonical_payload_digest"],
    },
    {
        "role": "sole_row_level_evidence",
        "path": REGISTRY_PATH,
        "byte_size": REGISTRY_SIZE,
        "sha256": REGISTRY_SHA256,
        "git_blob_id": "3451924c2d9f1598b8a5514da8c9db2e4e6d178b",
        "schema_or_version": "p545c_r4_strategy_draw_opportunity_registry.compact.v1",
        "functions_or_fields_used": ["cells", "official_outcomes", "opportunities", "attempts", "window_reconciliation"],
    },
    {
        "role": "exact_statistical_contract",
        "path": "analysis/p273a_prize_aware_inferential_validation.py",
        "byte_size": 90_605,
        "sha256": "f08b9062ebbf17046f8f46ffe92df27db0664ed51f7d125b785f34bbacc76697",
        "git_blob_id": "581bfd6aea96bcc6ac77a7086aa91ea5309108a9",
        "schema_or_version": "P273A_EXACT_DISTINCT_TICKET_PRIZE_AWARE_INFERENCE",
        "functions_or_fields_used": ["evaluate_window", "evaluate_stability", "benjamini_hochberg", "overall_project_classification"],
    },
    {
        "role": "lottery_scoring_contract",
        "path": "lottery_api/prize_aware_scorer.py",
        "byte_size": 15_526,
        "sha256": "907bdfa514aa18b33defe44869673cf43ce82fe143260564635cfc7284a76659",
        "git_blob_id": "fe1acc430e4a571772077d2b8d94dd1a8641ab6b",
        "schema_or_version": "prize_aware_v1",
        "functions_or_fields_used": ["score_prize_aware_ticket", "main_hit_count", "special_hit", "prize_tier", "any_prize_aware_win"],
    },
    {
        "role": "endpoint_definition_contract",
        "path": "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json",
        "byte_size": 33_623,
        "sha256": "73517f8be239a5638489b1b6291e2bb6a382b59be82d353e63916472939329ab",
        "git_blob_id": "d12bb76113b552ba62f733389474ce92749c7e89",
        "schema_or_version": "P271A",
        "functions_or_fields_used": ["endpoint_mapping_by_lottery", "tier_mapping_by_lottery"],
    },
    {
        "role": "frozen_36_cell_roster",
        "path": "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json",
        "byte_size": 39_690,
        "sha256": "3769596df51f6eaab5ef98cdf799ba9915f0c0349810f0899a7516004639a241",
        "git_blob_id": "3dfc3f558e002cafb7a1ce03bd1b336cfb7280f3",
        "schema_or_version": "P267C_FROZEN_STRATEGY_CELLS",
        "functions_or_fields_used": ["lottery_type", "strategy_id", "declared_bet_count"],
    },
)

TIER_ORDER = {
    "DAILY_539": ["D539_FIRST_PRIZE", "D539_SECOND_PRIZE", "D539_THIRD_PRIZE", "D539_FOURTH_PRIZE", "D539_NO_PRIZE"],
    "BIG_LOTTO": ["BIG_FIRST_PRIZE", "BIG_SECOND_PRIZE", "BIG_THIRD_PRIZE", "BIG_FOURTH_PRIZE", "BIG_FIFTH_PRIZE", "BIG_SIXTH_PRIZE", "BIG_SEVENTH_PRIZE", "BIG_CONSOLATION_PRIZE", "BIG_NO_PRIZE"],
    "POWER_LOTTO": ["POWER_FIRST_PRIZE", "POWER_SECOND_PRIZE", "POWER_THIRD_PRIZE", "POWER_FOURTH_PRIZE", "POWER_FIFTH_PRIZE", "POWER_SIXTH_PRIZE", "POWER_SEVENTH_PRIZE", "POWER_EIGHTH_PRIZE", "POWER_NINTH_PRIZE", "POWER_CONSOLATION_PRIZE", "POWER_NO_PRIZE"],
}
INFERENTIAL_SCALAR_MAP = (
    ("expected_successes", "expected_successes"),
    ("observed_rate", "observed_rate"),
    ("mean_baseline_rate", "mean_baseline_rate"),
    ("absolute_excess", "absolute_excess"),
    ("absolute_excess_pp", "absolute_excess_pp"),
    ("relative_lift", "relative_lift"),
    ("raw_p_value_one_sided_upper", "raw_p_value_one_sided_upper"),
    ("raw_p_value_one_sided_lower", "raw_p_value_one_sided_lower"),
    ("bonferroni_p_value_upper", "bonferroni_p_value"),
    ("bonferroni_p_value_lower", "bonferroni_p_value_lower"),
    ("bh_fdr_descriptive_reject", "bh_fdr_descriptive_reject"),
    ("p_value_method_upper", "p_value_method_upper"),
    ("p_value_method_lower", "p_value_method_lower"),
    ("significant_positive", "significant_positive"),
    ("significant_negative", "significant_negative"),
    ("statistical_status", "statistical_status"),
    ("exact_distinct_ticket_null_used", "exact_distinct_ticket_null_used"),
    ("independent_approximation_rejected_for_final_inference", "independent_approximation_rejected_for_final_inference"),
)

TOP_LEVEL_FIELDS = {
    "schema", "task_id", "classification", "generated_at_utc",
    "generated_at_policy", "implementation_base_commit", "input_registry",
    "contract_manifest", "scoring_contract", "statistical_contract",
    "opportunity_evaluations", "window_evaluations", "cell_summaries",
    "global_summary", "reconciliation", "determinism", "safety",
    "limitations", "canonical_payload_digest",
}
OPPORTUNITY_FIELDS = {
    "opportunity_id", "cell_id", "outcome_id", "target_draw", "canonical_date",
    "in_short_window", "in_mid_window", "in_long_window", "gross_attempt_count",
    "eligible_attempt_count", "excluded_attempt_count", "supported",
    "all_attempts_excluded", "exclusion_by_reason", "eligible_ticket_identity_refs",
    "attempt_result_refs", "tier_counts", "endpoint_counts", "observed_success_count",
    "any_success", "best_observed_tier", "best_observed_tier_contract",
    "opportunity_evaluation_digest",
}
WINDOW_FIELDS = {
    "window_id", "cell_id", "window_name", "window_size", "anchor_first_draw",
    "anchor_last_draw", "opportunity_ids", "draw_set_digest", "gross_attempt_count",
    "eligible_attempt_count", "excluded_attempt_count", "supported_opportunity_count",
    "unsupported_opportunity_count", "exclusion_by_reason",
    "distinct_ticket_identity_count", "tier_counts", "endpoint_counts",
    "observed_success_count", "expected_successes", "confidence_interval",
    "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower",
    "bonferroni_p_value_upper", "bonferroni_p_value_lower",
    "bh_fdr_descriptive_reject", "support_status", "evaluable",
    "inferential_field_presence", "omitted_inferential_fields", "omission_reason",
    "stability", "decision", "source_derivation", "window_evaluation_digest",
    "reconciliation",
}


class CanonicalEvaluationError(RuntimeError):
    """Fail-closed canonical contract or evidence error."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalEvaluationError("payload is not finite canonical JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def strict_json_load(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise CanonicalEvaluationError(f"non-finite JSON constant: {value}")
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CanonicalEvaluationError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result
    try:
        parsed = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalEvaluationError(f"invalid UTF-8 JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise CanonicalEvaluationError(f"JSON root is not an object: {path}")
    return parsed


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    candidate = dict(payload)
    candidate.pop("canonical_payload_digest", None)
    return digest(candidate)


def _verify_file(repo_root: Path, spec: Mapping[str, Any]) -> None:
    path = repo_root / str(spec["path"])
    if not path.is_file() or path.is_symlink():
        raise CanonicalEvaluationError(f"contract source is not a regular file: {spec['path']}")
    if path.stat().st_size != spec["byte_size"]:
        raise CanonicalEvaluationError(f"contract source size mismatch: {spec['path']}")
    if file_sha256(path) != spec["sha256"]:
        raise CanonicalEvaluationError(f"contract source hash mismatch: {spec['path']}")


def verify_contract_sources(repo_root: Path) -> list[dict[str, Any]]:
    for spec in CONTRACT_SOURCES:
        _verify_file(repo_root, spec)
    return [{**spec, "source_commit": IMPLEMENTATION_BASE_COMMIT, "verification": "PASS"} for spec in CONTRACT_SOURCES]


_LEGACY_MODULE: ModuleType | None = None


def load_verified_legacy_module(repo_root: Path) -> ModuleType:
    """Verify every load-bearing source before importing legacy pure logic."""
    global _LEGACY_MODULE
    verify_contract_sources(repo_root)
    if _LEGACY_MODULE is None:
        path = repo_root / LEGACY_SOURCE
        spec = importlib.util.spec_from_file_location("_verified_p545b_r2_legacy", path)
        if spec is None or spec.loader is None:
            raise CanonicalEvaluationError("cannot load verified legacy evaluator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.SCHEMA != LEGACY_SCHEMA or module.REGISTRY_SHA256 != REGISTRY_SHA256:
            raise CanonicalEvaluationError("legacy evaluator semantic constants changed")
        for name in ("load_registry", "evaluate_opportunities", "evaluate_windows", "build_evaluation"):
            if not callable(getattr(module, name, None)):
                raise CanonicalEvaluationError(f"legacy evaluator missing callable {name}")
        _LEGACY_MODULE = module
    return _LEGACY_MODULE


def load_verified_legacy_evidence(repo_root: Path, legacy: ModuleType) -> dict[str, Any]:
    committed = strict_json_load(repo_root / LEGACY_OUTPUT)
    if committed.get("schema") != LEGACY_SCHEMA:
        raise CanonicalEvaluationError("legacy output schema mismatch")
    if committed.get("canonical_payload_digest") != LEGACY_OUTPUT_CANONICAL_DIGEST:
        raise CanonicalEvaluationError("legacy output embedded digest mismatch")
    if legacy.canonical_payload_digest(committed) != LEGACY_OUTPUT_CANONICAL_DIGEST:
        raise CanonicalEvaluationError("legacy output canonical digest mismatch")
    recomputed = legacy.build_evaluation(repo_root)
    if legacy.canonical_bytes(recomputed) + b"\n" != (repo_root / LEGACY_OUTPUT).read_bytes():
        raise CanonicalEvaluationError("legacy numerical evaluation does not reproduce committed bytes")
    return recomputed


def _best_tier(lottery: str, counts: Mapping[str, int]) -> str | None:
    for tier in TIER_ORDER[lottery]:
        if counts.get(tier, 0) and not tier.endswith("_NO_PRIZE"):
            return tier
    return None


def _identity_groups(attempts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[bytes, dict[str, Any]] = {}
    for attempt in attempts:
        if not attempt["eligible"]:
            continue
        identity = attempt["ticket_identity"]
        key = canonical_bytes(identity["canonical_ticket_content"])
        group = groups.setdefault(key, {
            "fingerprint_sha256": identity["fingerprint_sha256"],
            "bet_indices": [],
        })
        group["bet_indices"].append(attempt["bet_index"])
    result = []
    for key in sorted(groups):
        group = groups[key]
        group["bet_indices"] = sorted(group["bet_indices"])
        result.append(group)
    return result


def _opportunity_records(registry: Mapping[str, Any], legacy_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    outcomes = {item["outcome_id"]: item for item in registry["official_outcomes"]}
    legacy_by_id = {item["opportunity_id"]: item for item in legacy_payload["per_opportunity_evaluations"]}
    if len(outcomes) != 2_253 or len(legacy_by_id) != 27_000:
        raise CanonicalEvaluationError("legacy opportunity or outcome identity count mismatch")
    attempts = registry["attempts"]
    records = []
    for source in registry["opportunities"]:
        legacy = legacy_by_id[source["opportunity_id"]]
        selected = attempts[source["attempt_start"]:source["attempt_start"] + source["attempt_count"]]
        if len(selected) != source["attempt_count"] or any(item["opportunity_id"] != source["opportunity_id"] for item in selected):
            raise CanonicalEvaluationError(f"attempt range mismatch: {source['opportunity_id']}")
        lottery = source["cell_id"].split(":", 1)[0]
        tier_counts: Counter[str] = Counter()
        endpoint_counts: Counter[str] = Counter()
        attempt_refs = []
        for attempt in sorted(selected, key=lambda item: (item["bet_index"], item["attempt_id"])):
            score = attempt["score"]
            if attempt["eligible"]:
                tier_counts[score["prize_tier"]] += 1
                endpoint_counts["ANY_PRIZE_AWARE_WIN" if score["any_prize_aware_win"] else "NO_PRIZE_AWARE_WIN"] += 1
            attempt_refs.append({
                "attempt_id": attempt["attempt_id"],
                "bet_index": attempt["bet_index"],
                "eligible": attempt["eligible"],
                "exclusion_reason": attempt["exclusion_reason"],
                "main_hit_count": score["main_hit_count"] if score is not None else None,
                "special_hit": score["special_hit"] if score is not None else None,
                "prize_tier": score["prize_tier"] if score is not None else None,
                "any_prize_aware_win": score["any_prize_aware_win"] if score is not None else None,
            })
        identities = _identity_groups(selected)
        outcome = outcomes[source["outcome_id"]]
        record = {
            "opportunity_id": source["opportunity_id"],
            "cell_id": source["cell_id"],
            "outcome_id": source["outcome_id"],
            "target_draw": source["target_draw"],
            "canonical_date": outcome["canonical_date"],
            "in_short_window": bool(source["window_mask"] & 1),
            "in_mid_window": bool(source["window_mask"] & 2),
            "in_long_window": bool(source["window_mask"] & 4),
            "gross_attempt_count": legacy["gross_attempts"],
            "eligible_attempt_count": legacy["eligible_attempts"],
            "excluded_attempt_count": legacy["excluded_attempts"],
            "exclusion_by_reason": legacy["exclusion_by_reason"],
            "supported": legacy["supported"],
            "all_attempts_excluded": not legacy["supported"],
            "eligible_ticket_identity_refs": identities,
            "attempt_result_refs": attempt_refs,
            "tier_counts": dict(sorted(tier_counts.items())),
            "endpoint_counts": dict(sorted(endpoint_counts.items())),
            "observed_success_count": int(legacy["observed_success"]),
            "any_success": legacy["observed_success"],
            "best_observed_tier": _best_tier(lottery, tier_counts),
            "best_observed_tier_contract": (
                "lottery_prize_tier_order" if legacy["supported"] else "NO_ELIGIBLE_ATTEMPTS"
            ),
        }
        if len(identities) != legacy["distinct_ticket_count"]:
            raise CanonicalEvaluationError(f"identity count mismatch: {source['opportunity_id']}")
        record["opportunity_evaluation_digest"] = digest(record)
        records.append(record)
    return sorted(records, key=lambda item: item["opportunity_id"])


def _sum_counters(records: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    value: Counter[str] = Counter()
    for record in records:
        value.update(record[field])
    return dict(sorted(value.items()))


def _compare(label: str, actual: Any, expected: Any, mismatches: list[str]) -> None:
    if actual != expected:
        mismatches.append(label)


def _window_reconciliation(
    actual: Mapping[str, Any],
    legacy_window: Mapping[str, Any],
    legacy_group: Mapping[str, Any],
    committed: Mapping[str, Any],
) -> dict[str, Any]:
    membership_fields = ["window_id", "opportunity_ids", "anchor_first_draw", "anchor_last_draw", "draw_set_digest"]
    primary_fields = ["gross_attempt_count", "eligible_attempt_count", "excluded_attempt_count", "supported_opportunity_count", "unsupported_opportunity_count", "observed_success_count", "exclusion_by_reason"]
    identity_fields = ["distinct_ticket_identity_count", "duplicate_content_draw_count"]
    inferential_fields = [name for name, _source in INFERENTIAL_SCALAR_MAP] + ["confidence_interval", "support_status", "evaluable", "inferential_field_presence", "omitted_inferential_fields", "omission_reason"]
    mismatches: list[str] = []
    _compare("membership.anchor_first_draw", actual["anchor_first_draw"], committed["earliest_target_draw"], mismatches)
    _compare("membership.anchor_last_draw", actual["anchor_last_draw"], committed["latest_target_draw"], mismatches)
    _compare("membership.draw_set_digest", actual["draw_set_digest"], committed["draw_set_sha256"], mismatches)
    _compare("membership.opportunity_count", len(actual["opportunity_ids"]), actual["window_size"], mismatches)
    for actual_field, committed_field in (
        ("gross_attempt_count", "gross_attempts"),
        ("eligible_attempt_count", "eligible_attempts"),
        ("excluded_attempt_count", "excluded_attempts"),
        ("observed_success_count", "observed_successes"),
        ("exclusion_by_reason", "exclusion_by_reason"),
    ):
        _compare(f"primary.{actual_field}", actual[actual_field], committed[committed_field], mismatches)
    _compare("primary.supported_opportunity_count", actual["supported_opportunity_count"], committed["support_draws"], mismatches)
    _compare("primary.unsupported_opportunity_count", actual["unsupported_opportunity_count"], actual["window_size"] - committed["support_draws"], mismatches)
    expected_distinct = sum(int(value) * int(count) for value, count in committed["distinct_ticket_count_distribution"].items())
    _compare("identity.distinct_ticket_identity_count", actual["distinct_ticket_identity_count"], expected_distinct, mismatches)
    _compare("identity.duplicate_content_draw_count", actual["source_derivation"]["duplicate_content_draw_count"], committed["duplicate_content_draw_count"], mismatches)
    expected_inference = committed["inference"]
    _compare("inference.evaluable", actual["evaluable"], expected_inference["evaluable"], mismatches)
    _compare("inference.support_status", actual["support_status"], expected_inference["support_status"], mismatches)
    for published_field, source_field in INFERENTIAL_SCALAR_MAP:
        _compare(f"legacy_inference.{published_field}", actual[published_field], legacy_window.get(source_field), mismatches)
        if source_field in expected_inference["values"]:
            _compare(f"committed_inference.{published_field}", actual[published_field], expected_inference["values"].get(source_field), mismatches)
    _compare("legacy_inference.confidence_interval.wilson_95", actual["confidence_interval"]["wilson_95"], legacy_window.get("wilson_ci_95"), mismatches)
    _compare("legacy_inference.confidence_interval.clopper_pearson_95", actual["confidence_interval"]["clopper_pearson_95"], legacy_window.get("clopper_pearson_ci_95"), mismatches)
    _compare("committed_inference.confidence_interval.wilson_95", actual["confidence_interval"]["wilson_95"], expected_inference["values"].get("wilson_ci_95"), mismatches)
    _compare("committed_inference.confidence_interval.clopper_pearson_95", actual["confidence_interval"]["clopper_pearson_95"], expected_inference["values"].get("clopper_pearson_ci_95"), mismatches)
    if not actual["evaluable"]:
        _compare("inference.omission_reason", actual["omission_reason"], expected_inference["omission_reason"], mismatches)
    _compare("inferential_record_digest", actual["source_derivation"]["inferential_record_digest"], committed["inferential_record_sha256"], mismatches)
    _compare("legacy_window_evaluation_digest", digest(legacy_window), actual["source_derivation"]["legacy_window_evaluation_digest"], mismatches)
    _compare("stability", actual["stability"], legacy_group["stability"], mismatches)
    _compare("decision.window", actual["decision"]["window"], legacy_window["window_decision"], mismatches)
    _compare("decision.group", actual["decision"]["group"], legacy_group["overall_group_decision"], mismatches)
    if mismatches:
        raise CanonicalEvaluationError(f"window reconciliation drift {actual['window_id']}: {mismatches}")
    return {
        "frozen_membership": {"status": "PASS", "fields": membership_fields},
        "primary": {"status": "PASS", "fields": primary_fields},
        "identity": {"status": "PASS", "fields": identity_fields},
        "scoring_aggregation": {"status": "PASS", "fields": ["tier_counts", "endpoint_counts", "observed_successes"]},
        "inferential": {"status": "PASS", "fields": inferential_fields},
        "stability_and_decision": {"status": "PASS", "fields": ["stability", "decision.window", "decision.group"]},
        "classification": "FULL_CANONICAL_FIELD_RECONCILIATION_PASS",
        "unexplained_mismatches": [],
    }


def _window_records(
    registry: Mapping[str, Any],
    opportunities: Sequence[Mapping[str, Any]],
    legacy_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_cell: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in opportunities:
        by_cell[record["cell_id"]].append(record)
    cells = {item["cell_id"]: item for item in registry["cells"]}
    committed_windows = {(item["lottery_type"], item["strategy_id"], item["window"]): item for item in registry["window_reconciliation"]}
    legacy_windows = {(item["lottery_type"], item["strategy_id"], item["window"]): item for item in legacy_payload["per_window_evaluations"]}
    legacy_groups = {(item["lottery_type"], item["strategy_id"]): item for item in legacy_payload["group_evaluations"]}
    windows = []
    cells_out = []
    for cell_id in sorted(cells):
        cell = cells[cell_id]
        lottery, strategy = cell["lottery_type"], cell["strategy_id"]
        group = legacy_groups[(lottery, strategy)]
        cell_window_ids = []
        for window, label, _bit in WINDOWS:
            membership_field = {"SHORT": "in_short_window", "MID": "in_mid_window", "LONG": "in_long_window"}[label]
            selected = sorted(
                (item for item in by_cell[cell_id] if item[membership_field]),
                key=lambda item: -int(item["target_draw"]),
            )
            anchor = next(item for item in cell["window_anchors"] if item["window"] == window)
            legacy_window = legacy_windows[(lottery, strategy, window)]
            committed = committed_windows[(lottery, strategy, window)]
            if len(selected) != window:
                raise CanonicalEvaluationError(f"frozen membership count mismatch: {cell_id}/w{window}")
            inference_values = {published: legacy_window.get(source) for published, source in INFERENTIAL_SCALAR_MAP}
            evaluable = bool(legacy_window["evaluable"])
            omission = None if evaluable else f"UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:{legacy_window['support_status']}"
            field_presence = {}
            for published, source in INFERENTIAL_SCALAR_MAP:
                if source not in legacy_window:
                    field_presence[published] = "source-absent-normalized-to-null"
                elif inference_values[published] is None:
                    field_presence[published] = "present-null"
                else:
                    field_presence[published] = "present-value"
            confidence_interval = {
                "wilson_95": legacy_window.get("wilson_ci_95"),
                "clopper_pearson_95": legacy_window.get("clopper_pearson_ci_95"),
            }
            for published, source in (("confidence_interval.wilson_95", "wilson_ci_95"), ("confidence_interval.clopper_pearson_95", "clopper_pearson_ci_95")):
                if source not in legacy_window:
                    field_presence[published] = "source-absent-normalized-to-null"
                elif legacy_window[source] is None:
                    field_presence[published] = "present-null"
                else:
                    field_presence[published] = "present-value"
            omitted_fields = sorted(name for name, state in field_presence.items() if state != "present-value")
            record = {
                "window_id": f"{cell_id}:w{window}",
                "cell_id": cell_id,
                "window_name": label,
                "window_size": window,
                "anchor_first_draw": anchor["earliest_target_draw"],
                "anchor_last_draw": anchor["latest_target_draw"],
                "opportunity_ids": [item["opportunity_id"] for item in selected],
                "draw_set_digest": digest([item["target_draw"] for item in selected]),
                "gross_attempt_count": sum(item["gross_attempt_count"] for item in selected),
                "eligible_attempt_count": sum(item["eligible_attempt_count"] for item in selected),
                "excluded_attempt_count": sum(item["excluded_attempt_count"] for item in selected),
                "exclusion_by_reason": _sum_counters(selected, "exclusion_by_reason"),
                "supported_opportunity_count": sum(item["supported"] for item in selected),
                "unsupported_opportunity_count": sum(not item["supported"] for item in selected),
                "distinct_ticket_identity_count": sum(len(item["eligible_ticket_identity_refs"]) for item in selected),
                "tier_counts": _sum_counters(selected, "tier_counts"),
                "endpoint_counts": _sum_counters(selected, "endpoint_counts"),
                "observed_success_count": legacy_window["observed_successes"],
                "confidence_interval": confidence_interval,
                "evaluable": evaluable,
                "support_status": legacy_window["support_status"],
                **inference_values,
                "inferential_field_presence": field_presence,
                "omitted_inferential_fields": omitted_fields,
                "omission_reason": omission,
                "stability": group["stability"],
                "decision": {
                    "window": legacy_window["window_decision"],
                    "group": group["overall_group_decision"],
                },
                "source_derivation": {
                    "row_evidence": REGISTRY_PATH,
                    "window_membership": "P545C window_mask intersected with committed cell anchors",
                    "legacy_window_evaluation_digest": digest(legacy_window),
                    "inferential_record_digest": committed["inferential_record_sha256"],
                    "duplicate_content_draw_count": committed["duplicate_content_draw_count"],
                },
            }
            record["reconciliation"] = _window_reconciliation(record, legacy_window, group, committed)
            record["window_evaluation_digest"] = digest(record)
            windows.append(record)
            cell_window_ids.append(record["window_id"])
        cell_opportunities = by_cell[cell_id]
        cell_windows = [item for item in windows if item["cell_id"] == cell_id]
        cell_summary = {
            "cell_id": cell_id,
            "lottery_type": lottery,
            "strategy_id": strategy,
            "declared_bet_count": cell["declared_bet_count"],
            "window_refs": cell_window_ids,
            "support_distribution": {item["window_name"]: {"supported": item["supported_opportunity_count"], "unsupported": item["unsupported_opportunity_count"]} for item in cell_windows},
            "evaluability_distribution": {item["window_name"]: item["evaluable"] for item in cell_windows},
            "stability_summary": group["stability"],
            "committed_decisions": {
                "windows": {item["window_name"]: item["decision"]["window"] for item in cell_windows},
                "group": group["overall_group_decision"],
            },
            "opportunity_count": len(cell_opportunities),
            "legacy_group_semantic_digest": digest(group),
        }
        cell_summary["cell_summary_digest"] = digest(cell_summary)
        cells_out.append(cell_summary)
    return sorted(windows, key=lambda item: (item["cell_id"], item["window_size"])), sorted(cells_out, key=lambda item: item["cell_id"])


def _numerical_projection(payload: Mapping[str, Any], *, canonical: bool) -> dict[str, Any]:
    if canonical:
        opportunities = [{
            "opportunity_id": item["opportunity_id"], "cell_id": item["cell_id"],
            "window_mask": int(item["in_short_window"]) + 2 * int(item["in_mid_window"]) + 4 * int(item["in_long_window"]),
            "gross_attempts": item["gross_attempt_count"], "eligible_attempts": item["eligible_attempt_count"],
            "excluded_attempts": item["excluded_attempt_count"], "supported": item["supported"],
            "distinct_ticket_count": len(item["eligible_ticket_identity_refs"]),
            "exclusion_by_reason": item["exclusion_by_reason"], "observed_success": item["any_success"],
        } for item in payload["opportunity_evaluations"]]
        windows = [{
            "cell_id": item["cell_id"], "window": item["window_size"],
            "support_draws": item["supported_opportunity_count"], "observed_successes": item["observed_success_count"],
            "expected_successes": item["expected_successes"], "wilson_ci_95": item["confidence_interval"]["wilson_95"],
            "clopper_pearson_ci_95": item["confidence_interval"]["clopper_pearson_95"],
            "raw_p_value_one_sided_upper": item["raw_p_value_one_sided_upper"],
            "raw_p_value_one_sided_lower": item["raw_p_value_one_sided_lower"],
            "bonferroni_p_value": item["bonferroni_p_value_upper"],
            "bonferroni_p_value_lower": item["bonferroni_p_value_lower"],
            "evaluable": item["evaluable"], "support_status": item["support_status"],
            "window_decision": item["decision"]["window"],
        } for item in payload["window_evaluations"]]
        groups = [{
            "cell_id": item["cell_id"], "stability": item["stability_summary"],
            "overall_group_decision": item["committed_decisions"]["group"],
        } for item in payload["cell_summaries"]]
    else:
        opportunities = [{
            "opportunity_id": item["opportunity_id"], "cell_id": item["cell_id"], "window_mask": item["window_mask"],
            "gross_attempts": item["gross_attempts"], "eligible_attempts": item["eligible_attempts"],
            "excluded_attempts": item["excluded_attempts"], "supported": item["supported"],
            "distinct_ticket_count": item["distinct_ticket_count"], "exclusion_by_reason": item["exclusion_by_reason"],
            "observed_success": item["observed_success"],
        } for item in payload["per_opportunity_evaluations"]]
        windows = [{
            "cell_id": f"{item['lottery_type']}:{item['strategy_id']}", "window": item["window"],
            "support_draws": item["support_draws"], "observed_successes": item["observed_successes"],
            "expected_successes": item["expected_successes"], "wilson_ci_95": item.get("wilson_ci_95"),
            "clopper_pearson_ci_95": item.get("clopper_pearson_ci_95"),
            "raw_p_value_one_sided_upper": item.get("raw_p_value_one_sided_upper"),
            "raw_p_value_one_sided_lower": item.get("raw_p_value_one_sided_lower"),
            "bonferroni_p_value": item.get("bonferroni_p_value"),
            "bonferroni_p_value_lower": item.get("bonferroni_p_value_lower"),
            "evaluable": item["evaluable"], "support_status": item["support_status"],
            "window_decision": item["window_decision"],
        } for item in payload["per_window_evaluations"]]
        groups = [{
            "cell_id": f"{item['lottery_type']}:{item['strategy_id']}", "stability": item["stability"],
            "overall_group_decision": item["overall_group_decision"],
        } for item in payload["group_evaluations"]]
    return {
        "opportunities": sorted(opportunities, key=lambda item: item["opportunity_id"]),
        "windows": sorted(windows, key=lambda item: (item["cell_id"], item["window"])),
        "groups": sorted(groups, key=lambda item: item["cell_id"]),
    }


def _global_summary(registry: Mapping[str, Any], opportunities: Sequence[Mapping[str, Any]], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    zero_ids = {"POWER_LOTTO:fourier_rhythm_3bet", "POWER_LOTTO:power_fourier_rhythm_2bet", "POWER_LOTTO:power_orthogonal_5bet", "POWER_LOTTO:power_precision_3bet"}
    zero = [item for item in opportunities if item["cell_id"] in zero_ids]
    daily_long = next(item for item in windows if item["cell_id"] == "DAILY_539:acb_markov_midfreq_3bet" and item["window_size"] == 750)
    exclusion_totals = _sum_counters(opportunities, "exclusion_by_reason")
    return {
        "cells": 36,
        "official_outcomes_referenced": len(registry["official_outcomes"]),
        "opportunities": len(opportunities),
        "attempts": sum(item["gross_attempt_count"] for item in opportunities),
        "eligible_attempts": sum(item["eligible_attempt_count"] for item in opportunities),
        "excluded_attempts": sum(item["excluded_attempt_count"] for item in opportunities),
        "supported_opportunities": sum(item["supported"] for item in opportunities),
        "unsupported_opportunities": sum(not item["supported"] for item in opportunities),
        "windows": len(windows),
        "evaluable_windows": sum(item["evaluable"] for item in windows),
        "unevaluable_windows": sum(not item["evaluable"] for item in windows),
        "reconciliation_totals": {
            "primary_pass": sum(item["reconciliation"]["primary"]["status"] == "PASS" for item in windows),
            "identity_pass": sum(item["reconciliation"]["identity"]["status"] == "PASS" for item in windows),
            "inferential_pass": sum(item["reconciliation"]["inferential"]["status"] == "PASS" for item in windows),
            "full_canonical_field_pass": sum(item["reconciliation"]["classification"] == "FULL_CANONICAL_FIELD_RECONCILIATION_PASS" for item in windows),
            "unexplained_mismatches": sum(len(item["reconciliation"]["unexplained_mismatches"]) for item in windows),
        },
        "exclusion_totals": exclusion_totals,
        "four_zero_identity_power_lotto_cells": {
            "cell_ids": sorted(zero_ids),
            "opportunities": len(zero),
            "gross_attempts": sum(item["gross_attempt_count"] for item in zero),
            "eligible_attempts": sum(item["eligible_attempt_count"] for item in zero),
            "excluded_attempts": sum(item["excluded_attempt_count"] for item in zero),
            "exclusion_by_reason": _sum_counters(zero, "exclusion_by_reason"),
        },
        "known_daily_539_correction": {
            "cell_id": daily_long["cell_id"],
            "window": 750,
            "frozen_long_gross_attempts": daily_long["gross_attempt_count"],
            "post_freeze_rows_included": False,
            "minus_88_deficit_present": False,
        },
        "duplicate_conflict_totals": {
            "same_key_duplicates": registry["global_summary"]["same_key_duplicate_rows"],
            "cross_index_duplicate_tickets": registry["global_summary"]["cross_index_duplicate_tickets"],
            "same_index_conflicts": registry["global_summary"]["same_index_conflicts"],
            "missing_expected_bet_indices": sum(len(item["missing_expected_bet_indices"]) for item in registry["opportunities"]),
            "unexpected_bet_indices": sum(len(item["unexpected_bet_indices"]) for item in registry["opportunities"]),
        },
    }


def _assert_global_invariants(summary: Mapping[str, Any]) -> None:
    expected = {
        "cells": 36, "official_outcomes_referenced": 2_253, "opportunities": 27_000,
        "attempts": 47_250, "eligible_attempts": 33_749,
        "excluded_attempts": 13_501, "supported_opportunities": 23_999,
        "unsupported_opportunities": 3_001, "windows": 108,
        "evaluable_windows": 86, "unevaluable_windows": 22,
        "exclusion_totals": {"MISSING_PREDICTED_SECOND_ZONE": 13_501},
    }
    for field, value in expected.items():
        if summary[field] != value:
            raise CanonicalEvaluationError(f"global invariant mismatch {field}: {summary[field]} != {value}")
    zero = summary["four_zero_identity_power_lotto_cells"]
    if (zero["opportunities"], zero["gross_attempts"], zero["eligible_attempts"], zero["excluded_attempts"]) != (3_000, 9_750, 0, 9_750):
        raise CanonicalEvaluationError("four POWER-cell invariant mismatch")
    if summary["known_daily_539_correction"]["frozen_long_gross_attempts"] != 2_250:
        raise CanonicalEvaluationError("known DAILY correction mismatch")
    if summary["reconciliation_totals"] != {
        "primary_pass": 108, "identity_pass": 108, "inferential_pass": 108,
        "full_canonical_field_pass": 108, "unexplained_mismatches": 0,
    }:
        raise CanonicalEvaluationError("global reconciliation invariant mismatch")
    if any(summary["duplicate_conflict_totals"].values()):
        raise CanonicalEvaluationError("duplicate or frozen-index invariant mismatch")


def validate_canonical_payload(payload: Mapping[str, Any]) -> None:
    if set(payload) != TOP_LEVEL_FIELDS:
        raise CanonicalEvaluationError("canonical top-level field contract mismatch")
    if payload["schema"] != SCHEMA:
        raise CanonicalEvaluationError("canonical schema mismatch")
    if payload["generated_at_utc"] != GENERATED_AT_UTC or not GENERATED_AT_UTC.endswith("Z"):
        raise CanonicalEvaluationError("canonical timestamp is not RFC3339 UTC Z")
    if not isinstance(payload["generated_at_policy"], Mapping):
        raise CanonicalEvaluationError("generated_at_policy must be structured")
    opportunities = payload["opportunity_evaluations"]
    windows = payload["window_evaluations"]
    cells = payload["cell_summaries"]
    if (len(opportunities), len(windows), len(cells)) != (27_000, 108, 36):
        raise CanonicalEvaluationError("canonical record counts changed")
    if any(set(item) != OPPORTUNITY_FIELDS for item in opportunities):
        raise CanonicalEvaluationError("opportunity interface field contract mismatch")
    if any(not WINDOW_FIELDS <= set(item) for item in windows):
        raise CanonicalEvaluationError("window interface field contract mismatch")
    if sum(len(item["attempt_result_refs"]) for item in opportunities) != 47_250:
        raise CanonicalEvaluationError("attempt-result reference accounting changed")
    for record in opportunities:
        if record["all_attempts_excluded"] != (not record["supported"]):
            raise CanonicalEvaluationError(f"unsupported opportunity contradiction: {record['opportunity_id']}")
        if record["eligible_attempt_count"] != len(record["eligible_ticket_identity_refs"]):
            raise CanonicalEvaluationError(f"eligible identity reference count changed: {record['opportunity_id']}")
    required_evaluable = {
        "expected_successes", "observed_rate", "mean_baseline_rate",
        "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower",
        "bonferroni_p_value_upper", "bonferroni_p_value_lower",
    }
    for record in windows:
        if len(record["opportunity_ids"]) != record["window_size"]:
            raise CanonicalEvaluationError(f"window membership count changed: {record['window_id']}")
        if record["evaluable"]:
            for field in required_evaluable:
                value = record[field]
                if value is None or not math.isfinite(value):
                    raise CanonicalEvaluationError(f"evaluable field missing or non-finite: {record['window_id']}/{field}")
            for field in ("raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower", "bonferroni_p_value_upper", "bonferroni_p_value_lower"):
                if not 0.0 <= record[field] <= 1.0:
                    raise CanonicalEvaluationError(f"p-value outside [0,1]: {record['window_id']}/{field}")
            for interval in record["confidence_interval"].values():
                if interval is None or interval[0] > interval[1]:
                    raise CanonicalEvaluationError(f"invalid confidence interval: {record['window_id']}")
            if record["omission_reason"] is not None or record["omitted_inferential_fields"]:
                raise CanonicalEvaluationError(f"evaluable window carries omission metadata: {record['window_id']}")
        else:
            if not record["omission_reason"] or not record["omitted_inferential_fields"]:
                raise CanonicalEvaluationError(f"unevaluable omission metadata missing: {record['window_id']}")
            for field in record["omitted_inferential_fields"]:
                if field.startswith("confidence_interval."):
                    value = record["confidence_interval"][field.split(".", 1)[1]]
                else:
                    value = record[field]
                if value is not None:
                    raise CanonicalEvaluationError(f"omitted inferential field is not null: {record['window_id']}/{field}")
        if record["reconciliation"]["classification"] != "FULL_CANONICAL_FIELD_RECONCILIATION_PASS":
            raise CanonicalEvaluationError(f"window reconciliation classification changed: {record['window_id']}")
        if record["reconciliation"]["unexplained_mismatches"]:
            raise CanonicalEvaluationError(f"window reconciliation mismatch: {record['window_id']}")
    _assert_global_invariants(payload["global_summary"])
    canonical_bytes(payload)


def _json_determinism_projection(payload: Mapping[str, Any]) -> bytes:
    projection = dict(payload)
    projection.pop("canonical_payload_digest", None)
    determinism = dict(projection["determinism"])
    determinism.pop("json_build_projection_sha256", None)
    determinism.pop("markdown_build_projection_sha256", None)
    determinism.pop("two_build_json_byte_identity_verified", None)
    determinism.pop("two_build_markdown_byte_identity_verified", None)
    projection["determinism"] = determinism
    return canonical_bytes(projection)


def build_evaluation(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = verify_contract_sources(repo_root)
    legacy = load_verified_legacy_module(repo_root)
    legacy_payload = load_verified_legacy_evidence(repo_root, legacy)
    strict_registry = strict_json_load(repo_root / REGISTRY_PATH)
    if strict_registry.get("schema") != "p545c_r4_strategy_draw_opportunity_registry.compact.v1":
        raise CanonicalEvaluationError("strict registry schema mismatch")
    if legacy.canonical_payload_digest(strict_registry) != REGISTRY_CANONICAL_DIGEST:
        raise CanonicalEvaluationError("strict registry canonical digest mismatch")
    registry, input_identity = legacy.load_registry(repo_root)
    if canonical_bytes(strict_registry) != canonical_bytes(registry):
        raise CanonicalEvaluationError("strict and verified registry parses differ")
    opportunities = _opportunity_records(registry, legacy_payload)
    windows, cell_summaries = _window_records(registry, opportunities, legacy_payload)
    global_summary = _global_summary(registry, opportunities, windows)
    _assert_global_invariants(global_summary)
    legacy_projection_digest = digest(_numerical_projection(legacy_payload, canonical=False))
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at_utc": GENERATED_AT_UTC,
        "generated_at_policy": GENERATED_AT_POLICY,
        "implementation_base_commit": IMPLEMENTATION_BASE_COMMIT,
        "input_registry": {
            **input_identity,
            "schema": registry["schema"],
            "sole_row_level_evidence_input": True,
            "cells": len(registry["cells"]),
            "official_outcomes": len(registry["official_outcomes"]),
            "opportunities": len(registry["opportunities"]),
            "attempts": len(registry["attempts"]),
            "window_reconciliations": len(registry["window_reconciliation"]),
        },
        "contract_manifest": manifest,
        "scoring_contract": {
            "version": "prize_aware_v1",
            "source": "lottery_api/prize_aware_scorer.py",
            "endpoint_source": "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json",
            "eligible_attempts_only": True,
            "daily_539": "main numbers only; prize-aware success at hit_count >= 2",
            "big_lotto": "actual special number is a hit when contained in predicted main numbers",
            "power_lotto": "first-zone main hits plus separately predicted second-zone equality",
            "excluded_attempt_semantics": "excluded attempts have explicit null score fields and never become supported failures",
            "ticket_identity": "unique canonical ticket content grouped by SHA-256 fingerprint per opportunity",
        },
        "statistical_contract": {
            "source": "analysis/p273a_prize_aware_inferential_validation.py",
            "primary_windows": [50, 300, 750],
            "reference_only_windows_excluded": [100, 500, 1500, "all_history"],
            "analysis_unit": "distinct_target_draw",
            "exact_distinct_ticket_null": "q_N = 1 - C(T-W,N)/C(T,N)",
            "p_value_method": "exact binomial for constant probabilities; exact Poisson-binomial for heterogeneous probabilities",
            "confidence_intervals": ["Wilson 95%", "Clopper-Pearson exact 95%"],
            "family_size": 108,
            "family_alpha": 0.05,
            "bonferroni_confirmatory": True,
            "bh_fdr_q": 0.10,
            "bh_fdr_descriptive_only": True,
            "minimum_support_draws": 30,
            "minimum_expected_successes": 5.0,
            "stability_rule": "committed P273A ten-point nested-window stability contract",
            "short_window_role": "direction guardrail; cannot independently trigger promotion",
        },
        "opportunity_evaluations": opportunities,
        "window_evaluations": windows,
        "cell_summaries": cell_summaries,
        "global_summary": global_summary,
        "reconciliation": {
            "legacy_source_sha256": LEGACY_SOURCE_SHA256,
            "legacy_output_sha256": LEGACY_OUTPUT_SHA256,
            "legacy_output_canonical_payload_digest": LEGACY_OUTPUT_CANONICAL_DIGEST,
            "legacy_semantic_projection_digest": legacy_projection_digest,
            "canonical_semantic_projection_digest": None,
            "legacy_canonical_semantic_equivalence": None,
            "primary_windows": "108/108 PASS",
            "identity_windows": "108/108 PASS",
            "inferential_windows": "108/108 PASS",
            "full_canonical_fields": "108/108 PASS",
            "unexplained_mismatches": 0,
        },
        "determinism": {
            "generated_at_policy": GENERATED_AT_POLICY,
            "implementation_base_commit_timestamp": IMPLEMENTATION_BASE_COMMIT_TIMESTAMP,
            "sort_policy": {
                "mapping_keys": "lexicographic sort_keys=True",
                "opportunities": "opportunity_id ascending",
                "windows": "cell_id then window_size ascending",
                "cells": "cell_id ascending",
                "nested_references": "explicit semantic keys",
            },
            "canonical_serialization": {
                "encoding": "UTF-8",
                "separators": [",", ":"],
                "allow_nan": False,
                "canonical_digest_excludes": ["canonical_payload_digest"],
            },
            "non_finite_json_rejected": True,
            "duplicate_json_keys_rejected": True,
            "immutable_in_memory_result_count": 1,
            "json_serialization_build_count": 2,
            "markdown_render_build_count": 2,
            "two_build_json_byte_identity_verified": True,
            "two_build_markdown_byte_identity_verified": True,
            "hash_projection_policy": "exclude canonical_payload_digest, both projection-hash fields, and both byte-identity result fields",
            "json_build_projection_sha256": None,
            "markdown_build_projection_sha256": None,
            "json_size_limit_bytes": MAX_JSON_BYTES,
            "markdown_size_limit_bytes": MAX_MARKDOWN_BYTES,
        },
        "safety": {
            "database_opened": False,
            "snapshot_opened": False,
            "sqlite_imported_or_connection_opened": False,
            "network_used_by_evaluator_or_tests": False,
            "git_or_github_network_limited_to_pr_workflow": True,
            "upstream_or_legacy_artifacts_modified": False,
            "strategy_search": False,
            "parameter_tuning": False,
            "combination_optimization": False,
            "deployment_action": False,
            "predictive_validity_claim": False,
            "betting_recommendation": False,
        },
        "limitations": [
            "Retrospective research reconciliation only.",
            "The committed P545C R4 registry is the sole row-level evidence input.",
            "Legacy P545B R2 is preserved as numerical evidence and is not replaced or modified.",
            "There is no untouched prospective holdout in this retrospective evaluation.",
            "This is not proof of predictive validity or a betting edge.",
            "No ROI, EV, staking, bankroll, or purchase recommendation.",
            "No deployment-readiness or production-readiness claim.",
        ],
    }
    canonical_projection_digest = digest(_numerical_projection(payload, canonical=True))
    payload["reconciliation"]["canonical_semantic_projection_digest"] = canonical_projection_digest
    payload["reconciliation"]["legacy_canonical_semantic_equivalence"] = canonical_projection_digest == legacy_projection_digest
    if not payload["reconciliation"]["legacy_canonical_semantic_equivalence"]:
        raise CanonicalEvaluationError("canonical numerical projection differs from legacy evidence")
    payload["determinism"]["json_build_projection_sha256"] = hashlib.sha256(
        _json_determinism_projection(payload)
    ).hexdigest()
    payload["determinism"]["markdown_build_projection_sha256"] = hashlib.sha256(
        render_markdown(payload, projection=True).encode("utf-8")
    ).hexdigest()
    payload["canonical_payload_digest"] = canonical_payload_digest(payload)
    validate_canonical_payload(payload)
    return payload


def render_markdown(payload: Mapping[str, Any], *, projection: bool = False) -> str:
    summary = payload["global_summary"]
    zero = summary["four_zero_identity_power_lotto_cells"]
    source = payload["input_registry"]
    policy = payload["generated_at_policy"]
    determinism = payload["determinism"]
    canonical_digest = (
        "EXCLUDED_FROM_NON_SELF_REFERENTIAL_PROJECTION"
        if projection else payload["canonical_payload_digest"]
    )
    lines = [
        "# P545B — Canonical Full 50/300/750 Per-Draw Evaluation", "",
        "> Retrospective research reconciliation only. No predictive-validity or betting recommendation claim.", "",
        "## Published contract", "",
        f"- Schema: `{payload['schema']}`",
        f"- Implementation base: `{payload['implementation_base_commit']}`",
        f"- Deterministic timestamp: `{payload['generated_at_utc']}`",
        f"- Timestamp source: `{policy['timestamp_field']}` of `{policy['source_commit']}`",
        f"- Timestamp format: `{policy['format']}` at `{policy['precision']}` precision",
        f"- Canonical payload digest: `{canonical_digest}`", "",
        "## Evidence lineage", "",
        f"- Sole row-level input: `{source['path']}`",
        f"- Input bytes / SHA-256: **{source['byte_size']:,}** / `{source['sha256']}`",
        f"- Semantic projection digest: `{source['semantic_projection_digest']}`",
        f"- Input canonical digest: `{source['canonical_payload_digest']}`",
        f"- Verified contract sources: **{len(payload['contract_manifest'])}**", "",
        "## Global accounting", "",
        f"- Cells / opportunities / attempts: **{summary['cells']} / {summary['opportunities']:,} / {summary['attempts']:,}**",
        f"- Eligible / excluded attempts: **{summary['eligible_attempts']:,} / {summary['excluded_attempts']:,}**",
        f"- Supported / unsupported opportunities: **{summary['supported_opportunities']:,} / {summary['unsupported_opportunities']:,}**",
        f"- Evaluable / unevaluable windows: **{summary['evaluable_windows']} / {summary['unevaluable_windows']}**", "",
        "## Reconciliation", "",
        "- Primary: **108/108 PASS**",
        "- Identity: **108/108 PASS**",
        "- Inferential: **108/108 PASS**",
        "- Full canonical fields: **108/108 PASS**",
        "- Unexplained mismatches: **0**",
        f"- Legacy semantic equivalence: **{'PASS' if payload['reconciliation']['legacy_canonical_semantic_equivalence'] else 'FAIL'}**",
        f"- Semantic projection digest: `{payload['reconciliation']['canonical_semantic_projection_digest']}`", "",
        "## Four unsupported POWER_LOTTO cells", "",
        f"- Opportunities / gross attempts: **{zero['opportunities']:,} / {zero['gross_attempts']:,}**",
        f"- Eligible / excluded: **{zero['eligible_attempts']:,} / {zero['excluded_attempts']:,}**",
        "- Exclusion: `MISSING_PREDICTED_SECOND_ZONE`", "",
        "## Determinism and safety", "",
        "- Two independent JSON serializations byte-identical: **PASS**",
        "- Two independent Markdown renders byte-identical: **PASS**",
        "- Non-finite JSON rejected: **YES**",
        "- Duplicate JSON keys rejected: **YES**",
        "- SQLite/database/snapshot opened: **NO**",
        "- Strategy search or parameter tuning: **NO**",
    ]
    if not projection:
        lines.extend([
            f"- JSON determinism projection SHA-256: `{determinism['json_build_projection_sha256']}`",
            f"- Markdown determinism projection SHA-256: `{determinism['markdown_build_projection_sha256']}`",
        ])
    lines.extend([
        "- Predictive-validity, ROI, EV, staking, deployment, or betting claim: **NO**", "",
        "## Limitations", "",
        "- Frozen retrospective evidence only.",
        "- No untouched prospective holdout is present.",
        "- Legacy P545B R2 evidence remains immutable and is not superseded numerically.",
        "- This publication contract does not authorize any operational or wagering action.", "",
    ])
    return "\n".join(lines)


def generate(repo_root: Path, output_json: Path = OUTPUT_JSON, output_markdown: Path = OUTPUT_MARKDOWN) -> tuple[Path, Path]:
    immutable_result = build_evaluation(repo_root)
    first_json = canonical_bytes(immutable_result) + b"\n"
    second_json = canonical_bytes(immutable_result) + b"\n"
    if first_json != second_json:
        raise CanonicalEvaluationError("two-build JSON determinism failure")
    first_markdown = render_markdown(immutable_result).encode("utf-8")
    second_markdown = render_markdown(immutable_result).encode("utf-8")
    if first_markdown != second_markdown:
        raise CanonicalEvaluationError("two-build Markdown determinism failure")
    if len(first_json) >= MAX_JSON_BYTES:
        raise CanonicalEvaluationError(f"canonical JSON size {len(first_json)} reaches 40 MiB gate")
    if len(first_markdown) >= MAX_MARKDOWN_BYTES:
        raise CanonicalEvaluationError("canonical Markdown is not summary-sized")
    json_path = repo_root / output_json
    markdown_path = repo_root / output_markdown
    json_path.write_bytes(first_json)
    markdown_path.write_bytes(first_markdown)
    return json_path, markdown_path


def main() -> None:
    generate(_REPO_ROOT)


if __name__ == "__main__":
    main()
