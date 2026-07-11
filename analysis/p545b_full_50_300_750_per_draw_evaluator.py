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
GENERATED_AT_UTC = "2026-07-11T07:58:26+00:00"
GENERATED_AT_POLICY = "implementation base commit committer timestamp normalized to UTC seconds"
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
INFERENTIAL_FIELDS = (
    "expected_successes", "observed_rate", "mean_baseline_rate", "absolute_excess",
    "absolute_excess_pp", "relative_lift", "wilson_ci_95", "clopper_pearson_ci_95",
    "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower",
    "bonferroni_p_value", "bonferroni_p_value_lower", "bh_fdr_descriptive_reject",
    "p_value_method_upper", "p_value_method_lower", "statistical_status", "window_decision",
    "significant_positive", "significant_negative", "exact_distinct_ticket_null_used",
    "independent_approximation_rejected_for_final_inference",
)


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
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
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
    return [{**spec, "commit": IMPLEMENTATION_BASE_COMMIT, "verification": "PASS"} for spec in CONTRACT_SOURCES]


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
            "canonical_ticket_content": identity["canonical_ticket_content"],
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
            "window_membership": {
                "SHORT": bool(source["window_mask"] & 1),
                "MID": bool(source["window_mask"] & 2),
                "LONG": bool(source["window_mask"] & 4),
            },
            "gross_attempts": legacy["gross_attempts"],
            "eligible_attempts": legacy["eligible_attempts"],
            "excluded_attempts": legacy["excluded_attempts"],
            "exclusion_by_reason": legacy["exclusion_by_reason"],
            "supported": legacy["supported"],
            "eligible_ticket_identities": identities,
            "distinct_ticket_count": legacy["distinct_ticket_count"],
            "duplicate_ticket_count": legacy["duplicate_ticket_count"],
            "attempt_result_references": attempt_refs,
            "tier_counts": dict(sorted(tier_counts.items())),
            "endpoint_counts": dict(sorted(endpoint_counts.items())),
            "winning_eligible_attempt_count": endpoint_counts["ANY_PRIZE_AWARE_WIN"],
            "observed_success_count": int(legacy["observed_success"]),
            "any_prize_aware_success": legacy["observed_success"],
            "best_observed_tier": _best_tier(lottery, tier_counts),
        }
        if len(identities) != record["distinct_ticket_count"]:
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
    membership_fields = ["latest_target_draw", "earliest_target_draw", "draw_set_sha256", "opportunity_ids"]
    primary_fields = ["gross_attempts", "eligible_attempts", "excluded_attempts", "support_draws", "supported_opportunities", "unsupported_opportunities", "observed_successes", "empirical_success_rate", "exclusion_by_reason"]
    identity_fields = ["distinct_eligible_ticket_identities", "distinct_ticket_count_distribution", "duplicate_content_draw_count"]
    inferential_fields = ["expected_successes", "wilson_ci_95", "clopper_pearson_ci_95", "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower", "bonferroni_p_value", "bonferroni_p_value_lower", "statistical_status", "window_decision"]
    mismatches: list[str] = []
    for field in membership_fields[:3]:
        _compare(f"membership.{field}", actual[field], committed[field], mismatches)
    for field in ("gross_attempts", "eligible_attempts", "excluded_attempts", "support_draws", "observed_successes", "exclusion_by_reason"):
        _compare(f"primary.{field}", actual[field], committed[field], mismatches)
    _compare("primary.supported_opportunities", actual["supported_opportunities"], committed["support_draws"], mismatches)
    _compare("primary.unsupported_opportunities", actual["unsupported_opportunities"], actual["window"] - committed["support_draws"], mismatches)
    expected_rate = committed["observed_successes"] / committed["support_draws"] if committed["support_draws"] else None
    _compare("primary.empirical_success_rate", actual["empirical_success_rate"], expected_rate, mismatches)
    for field in identity_fields[1:]:
        _compare(f"identity.{field}", actual[field], committed[field], mismatches)
    expected_distinct = sum(int(value) * int(count) for value, count in committed["distinct_ticket_count_distribution"].items())
    _compare("identity.distinct_eligible_ticket_identities", actual["distinct_eligible_ticket_identities"], expected_distinct, mismatches)
    expected_inference = committed["inference"]
    _compare("inference.evaluable", actual["evaluable"], expected_inference["evaluable"], mismatches)
    _compare("inference.support_status", actual["support_status"], expected_inference["support_status"], mismatches)
    for field in inferential_fields:
        _compare(f"inference.{field}", actual[field], expected_inference["values"].get(field), mismatches)
    for field in INFERENTIAL_FIELDS:
        _compare(f"legacy_inference.{field}", actual[field], legacy_window.get(field), mismatches)
    if not actual["evaluable"]:
        _compare("inference.omission_reason", actual["inferential_omission_reason"], expected_inference["omission_reason"], mismatches)
    _compare("legacy_window_evaluation_digest", digest(legacy_window), actual["legacy_window_evaluation_digest"], mismatches)
    _compare("stability", actual["stability"], legacy_group["stability"], mismatches)
    _compare("group_decision", actual["group_decision"], legacy_group["overall_group_decision"], mismatches)
    if mismatches:
        raise CanonicalEvaluationError(f"window reconciliation drift {actual['window_evaluation_id']}: {mismatches}")
    return {
        "frozen_membership": {"status": "PASS", "fields": membership_fields},
        "primary": {"status": "PASS", "fields": primary_fields},
        "identity": {"status": "PASS", "fields": identity_fields},
        "scoring_aggregation": {"status": "PASS", "fields": ["tier_counts", "endpoint_counts", "observed_successes"]},
        "inferential": {"status": "PASS", "fields": ["evaluable", "support_status", *INFERENTIAL_FIELDS, "nullable_omission_semantics"]},
        "stability_and_decision": {"status": "PASS", "fields": ["stability", "window_decision", "group_decision"]},
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
            selected = sorted(
                (item for item in by_cell[cell_id] if item["window_membership"][label]),
                key=lambda item: -int(item["target_draw"]),
            )
            anchor = next(item for item in cell["window_anchors"] if item["window"] == window)
            legacy_window = legacy_windows[(lottery, strategy, window)]
            committed = committed_windows[(lottery, strategy, window)]
            if len(selected) != window:
                raise CanonicalEvaluationError(f"frozen membership count mismatch: {cell_id}/w{window}")
            inference_values = {field: legacy_window.get(field) for field in INFERENTIAL_FIELDS}
            evaluable = bool(legacy_window["evaluable"])
            omission = None if evaluable else f"UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:{legacy_window['support_status']}"
            field_presence = {field: ("present-value" if value is not None else "present-null") for field, value in inference_values.items()}
            record = {
                "window_evaluation_id": f"{cell_id}:w{window}",
                "cell_id": cell_id,
                "lottery_type": lottery,
                "strategy_id": strategy,
                "window": window,
                "window_label": label,
                "latest_target_draw": anchor["latest_target_draw"],
                "earliest_target_draw": anchor["earliest_target_draw"],
                "opportunity_ids": [item["opportunity_id"] for item in selected],
                "draw_set_sha256": digest([item["target_draw"] for item in selected]),
                "gross_attempts": sum(item["gross_attempts"] for item in selected),
                "eligible_attempts": sum(item["eligible_attempts"] for item in selected),
                "excluded_attempts": sum(item["excluded_attempts"] for item in selected),
                "exclusion_by_reason": _sum_counters(selected, "exclusion_by_reason"),
                "supported_opportunities": sum(item["supported"] for item in selected),
                "unsupported_opportunities": sum(not item["supported"] for item in selected),
                "support_draws": legacy_window["support_draws"],
                "distinct_eligible_ticket_identities": sum(item["distinct_ticket_count"] for item in selected),
                "distinct_ticket_count_distribution": legacy_window["distinct_ticket_count_distribution"],
                "duplicate_content_draw_count": 0,
                "observed_successes": legacy_window["observed_successes"],
                "tier_counts": _sum_counters(selected, "tier_counts"),
                "endpoint_counts": _sum_counters(selected, "endpoint_counts"),
                "empirical_success_rate": (legacy_window["observed_successes"] / legacy_window["support_draws"] if legacy_window["support_draws"] else None),
                "evaluable": evaluable,
                "support_status": legacy_window["support_status"],
                **inference_values,
                "inferential_field_presence": field_presence,
                "inferential_omission_reason": omission,
                "stability": group["stability"],
                "group_decision": group["overall_group_decision"],
                "legacy_window_evaluation_digest": digest(legacy_window),
            }
            record["reconciliation"] = _window_reconciliation(record, legacy_window, group, committed)
            record["source_and_derivation_digest"] = digest(record)
            windows.append(record)
            cell_window_ids.append(record["window_evaluation_id"])
        cell_opportunities = by_cell[cell_id]
        cell_summary = {
            "cell_id": cell_id,
            "lottery_type": lottery,
            "strategy_id": strategy,
            "declared_bet_count": cell["declared_bet_count"],
            "opportunities": len(cell_opportunities),
            "supported_opportunities": sum(item["supported"] for item in cell_opportunities),
            "unsupported_opportunities": sum(not item["supported"] for item in cell_opportunities),
            "observed_successes_long": sum(item["observed_success_count"] for item in cell_opportunities),
            "window_evaluation_ids": cell_window_ids,
            "stability": group["stability"],
            "overall_group_decision": group["overall_group_decision"],
            "legacy_group_evaluation_digest": digest(group),
        }
        cell_summary["cell_summary_digest"] = digest(cell_summary)
        cells_out.append(cell_summary)
    return sorted(windows, key=lambda item: (item["lottery_type"], item["strategy_id"], item["window"])), sorted(cells_out, key=lambda item: item["cell_id"])


def _numerical_projection(payload: Mapping[str, Any], *, canonical: bool) -> dict[str, Any]:
    if canonical:
        opportunities = [{key: item[key] for key in ("opportunity_id", "gross_attempts", "eligible_attempts", "excluded_attempts", "supported", "distinct_ticket_count", "duplicate_ticket_count", "exclusion_by_reason")} | {"observed_success": item["any_prize_aware_success"]} for item in payload["opportunity_evaluations"]]
        windows = [{"legacy_window_evaluation_digest": item["legacy_window_evaluation_digest"]} for item in payload["window_evaluations"]]
        groups = [{"legacy_group_evaluation_digest": item["legacy_group_evaluation_digest"]} for item in payload["cell_summaries"]]
    else:
        opportunities = [{key: item[key] for key in ("opportunity_id", "gross_attempts", "eligible_attempts", "excluded_attempts", "supported", "distinct_ticket_count", "duplicate_ticket_count", "exclusion_by_reason", "observed_success")} for item in payload["per_opportunity_evaluations"]]
        windows = [{"legacy_window_evaluation_digest": digest(item)} for item in payload["per_window_evaluations"]]
        groups = [{"legacy_group_evaluation_digest": digest(item)} for item in payload["group_evaluations"]]
    return {
        "opportunities": sorted(opportunities, key=lambda item: item["opportunity_id"]),
        "windows": sorted(windows, key=lambda item: item["legacy_window_evaluation_digest"]),
        "groups": sorted(groups, key=lambda item: item["legacy_group_evaluation_digest"]),
    }


def _global_summary(registry: Mapping[str, Any], opportunities: Sequence[Mapping[str, Any]], windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    zero_ids = {"POWER_LOTTO:fourier_rhythm_3bet", "POWER_LOTTO:power_fourier_rhythm_2bet", "POWER_LOTTO:power_orthogonal_5bet", "POWER_LOTTO:power_precision_3bet"}
    zero = [item for item in opportunities if item["cell_id"] in zero_ids]
    daily_long = next(item for item in windows if item["cell_id"] == "DAILY_539:acb_markov_midfreq_3bet" and item["window"] == 750)
    return {
        "cells": 36,
        "official_outcomes": len(registry["official_outcomes"]),
        "opportunity_evaluations": len(opportunities),
        "attempts_represented": sum(item["gross_attempts"] for item in opportunities),
        "eligible_attempts": sum(item["eligible_attempts"] for item in opportunities),
        "excluded_attempts": sum(item["excluded_attempts"] for item in opportunities),
        "supported_opportunities": sum(item["supported"] for item in opportunities),
        "identity_missing_opportunities": sum(not item["supported"] for item in opportunities),
        "window_evaluations": len(windows),
        "evaluable_windows": sum(item["evaluable"] for item in windows),
        "unevaluable_windows": sum(not item["evaluable"] for item in windows),
        "reconciled_windows": sum(not item["reconciliation"]["unexplained_mismatches"] for item in windows),
        "all_exclusion_reasons": sorted({reason for item in opportunities for reason in item["exclusion_by_reason"]}),
        "four_zero_identity_power_lotto_cells": {
            "cell_ids": sorted(zero_ids),
            "opportunities": len(zero),
            "gross_attempts": sum(item["gross_attempts"] for item in zero),
            "eligible_attempts": sum(item["eligible_attempts"] for item in zero),
            "excluded_attempts": sum(item["excluded_attempts"] for item in zero),
            "exclusion_by_reason": _sum_counters(zero, "exclusion_by_reason"),
        },
        "known_daily_539_correction": {
            "cell_id": daily_long["cell_id"],
            "window": 750,
            "frozen_long_gross_attempts": daily_long["gross_attempts"],
            "post_freeze_rows_included": False,
            "minus_88_deficit_present": False,
        },
        "duplicate_and_index_invariants": {
            "same_key_duplicates": registry["global_summary"]["same_key_duplicate_rows"],
            "cross_index_duplicate_tickets": registry["global_summary"]["cross_index_duplicate_tickets"],
            "same_index_conflicts": registry["global_summary"]["same_index_conflicts"],
            "missing_expected_bet_indices": sum(len(item["missing_expected_bet_indices"]) for item in registry["opportunities"]),
            "unexpected_bet_indices": sum(len(item["unexpected_bet_indices"]) for item in registry["opportunities"]),
        },
    }


def _assert_global_invariants(summary: Mapping[str, Any]) -> None:
    expected = {
        "cells": 36, "official_outcomes": 2_253, "opportunity_evaluations": 27_000,
        "attempts_represented": 47_250, "eligible_attempts": 33_749,
        "excluded_attempts": 13_501, "supported_opportunities": 23_999,
        "identity_missing_opportunities": 3_001, "window_evaluations": 108,
        "evaluable_windows": 86, "unevaluable_windows": 22, "reconciled_windows": 108,
        "all_exclusion_reasons": ["MISSING_PREDICTED_SECOND_ZONE"],
    }
    for field, value in expected.items():
        if summary[field] != value:
            raise CanonicalEvaluationError(f"global invariant mismatch {field}: {summary[field]} != {value}")
    zero = summary["four_zero_identity_power_lotto_cells"]
    if (zero["opportunities"], zero["gross_attempts"], zero["eligible_attempts"], zero["excluded_attempts"]) != (3_000, 9_750, 0, 9_750):
        raise CanonicalEvaluationError("four POWER-cell invariant mismatch")
    if summary["known_daily_539_correction"]["frozen_long_gross_attempts"] != 2_250:
        raise CanonicalEvaluationError("known DAILY correction mismatch")
    if any(summary["duplicate_and_index_invariants"].values()):
        raise CanonicalEvaluationError("duplicate or frozen-index invariant mismatch")


def build_evaluation(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = verify_contract_sources(repo_root)
    legacy = load_verified_legacy_module(repo_root)
    legacy_payload = load_verified_legacy_evidence(repo_root, legacy)
    registry, input_identity = legacy.load_registry(repo_root)
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
            "legacy_numerical_projection_digest": legacy_projection_digest,
            "canonical_numerical_projection_digest": None,
            "legacy_numerical_equivalence": None,
            "primary_windows": "108/108 PASS",
            "identity_windows": "108/108 PASS",
            "inferential_windows": "108/108 PASS",
            "unexplained_mismatches": 0,
        },
        "determinism": {
            "generated_at_policy": GENERATED_AT_POLICY,
            "implementation_base_commit_timestamp": IMPLEMENTATION_BASE_COMMIT_TIMESTAMP,
            "collection_ordering": "explicit stable keys for opportunities, windows, cells, identities, attempts, tiers, and exclusions",
            "canonical_serialization": "UTF-8 sorted-key compact JSON; canonical digest excludes only canonical_payload_digest",
            "non_finite_json_rejected": True,
            "required_build_count": 2,
            "two_build_json_byte_identity_verified": True,
            "two_build_markdown_byte_identity_verified": True,
            "json_size_limit_bytes": MAX_JSON_BYTES,
            "markdown_size_limit_bytes": MAX_MARKDOWN_BYTES,
        },
        "safety": {
            "sqlite_imported_or_invoked": False,
            "database_or_snapshot_opened": False,
            "network_used": False,
            "strategy_combination_or_parameter_search": False,
            "upstream_or_legacy_artifacts_modified": False,
            "predictive_validity_claim": False,
            "betting_recommendation": False,
        },
        "limitations": [
            "Retrospective research reconciliation only.",
            "The committed P545C R4 registry is the sole row-level evidence input.",
            "Legacy P545B R2 is preserved as numerical evidence and is not replaced or modified.",
            "No predictive-validity, betting-edge, ROI, EV, staking, deployment, or production-readiness claim.",
        ],
    }
    canonical_projection_digest = digest(_numerical_projection(payload, canonical=True))
    payload["reconciliation"]["canonical_numerical_projection_digest"] = canonical_projection_digest
    payload["reconciliation"]["legacy_numerical_equivalence"] = canonical_projection_digest == legacy_projection_digest
    if not payload["reconciliation"]["legacy_numerical_equivalence"]:
        raise CanonicalEvaluationError("canonical numerical projection differs from legacy evidence")
    payload["canonical_payload_digest"] = canonical_payload_digest(payload)
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["global_summary"]
    zero = summary["four_zero_identity_power_lotto_cells"]
    source = payload["input_registry"]
    lines = [
        "# P545B — Canonical Full 50/300/750 Per-Draw Evaluation", "",
        "> Retrospective research reconciliation only. No predictive-validity or betting recommendation claim.", "",
        "## Published contract", "",
        f"- Schema: `{payload['schema']}`",
        f"- Implementation base: `{payload['implementation_base_commit']}`",
        f"- Deterministic timestamp: `{payload['generated_at_utc']}`",
        f"- Timestamp policy: `{payload['generated_at_policy']}`",
        f"- Canonical payload digest: `{payload['canonical_payload_digest']}`", "",
        "## Evidence lineage", "",
        f"- Sole row-level input: `{source['path']}`",
        f"- Input bytes / SHA-256: **{source['byte_size']:,}** / `{source['sha256']}`",
        f"- Semantic projection digest: `{source['semantic_projection_digest']}`",
        f"- Input canonical digest: `{source['canonical_payload_digest']}`",
        f"- Verified contract sources: **{len(payload['contract_manifest'])}**", "",
        "## Global accounting", "",
        f"- Cells / opportunities / attempts: **{summary['cells']} / {summary['opportunity_evaluations']:,} / {summary['attempts_represented']:,}**",
        f"- Eligible / excluded attempts: **{summary['eligible_attempts']:,} / {summary['excluded_attempts']:,}**",
        f"- Supported / identity-missing opportunities: **{summary['supported_opportunities']:,} / {summary['identity_missing_opportunities']:,}**",
        f"- Evaluable / unevaluable windows: **{summary['evaluable_windows']} / {summary['unevaluable_windows']}**", "",
        "## Reconciliation", "",
        "- Primary: **108/108 PASS**",
        "- Identity: **108/108 PASS**",
        "- Inferential: **108/108 PASS**",
        "- Unexplained mismatches: **0**",
        f"- Legacy numerical equivalence: **{'PASS' if payload['reconciliation']['legacy_numerical_equivalence'] else 'FAIL'}**",
        f"- Numerical projection digest: `{payload['reconciliation']['canonical_numerical_projection_digest']}`", "",
        "## Four unsupported POWER_LOTTO cells", "",
        f"- Opportunities / gross attempts: **{zero['opportunities']:,} / {zero['gross_attempts']:,}**",
        f"- Eligible / excluded: **{zero['eligible_attempts']:,} / {zero['excluded_attempts']:,}**",
        "- Exclusion: `MISSING_PREDICTED_SECOND_ZONE`", "",
        "## Determinism and safety", "",
        "- Two independent JSON builds byte-identical: **PASS**",
        "- Two independent Markdown builds byte-identical: **PASS**",
        "- Non-finite JSON rejected: **YES**",
        "- SQLite/database/snapshot opened: **NO**",
        "- Strategy search or parameter tuning: **NO**",
        "- Predictive-validity, ROI, EV, staking, deployment, or betting claim: **NO**", "",
        "## Limitations", "",
        "- Frozen retrospective evidence only.",
        "- Legacy P545B R2 evidence remains immutable and is not superseded numerically.",
        "- This publication contract does not authorize any operational or wagering action.", "",
    ]
    return "\n".join(lines)


def generate(repo_root: Path, output_json: Path = OUTPUT_JSON, output_markdown: Path = OUTPUT_MARKDOWN) -> tuple[Path, Path]:
    first = build_evaluation(repo_root)
    second = build_evaluation(repo_root)
    first_json = canonical_bytes(first) + b"\n"
    second_json = canonical_bytes(second) + b"\n"
    if first_json != second_json:
        raise CanonicalEvaluationError("two-build JSON determinism failure")
    first_markdown = render_markdown(first).encode("utf-8")
    second_markdown = render_markdown(second).encode("utf-8")
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
