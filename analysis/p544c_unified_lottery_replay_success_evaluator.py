#!/usr/bin/env python3
"""Deterministic P544C unified replay-success evaluator.

The evaluator reads eight JSON inputs exclusively as committed git blobs at a
fixed source commit.  It never opens a database, uses a wall clock, or mutates
an upstream artifact.  P543C's stored BIG_LOTTO ``special_hit`` is retained for
provenance but, under the owner-approved R1 amendment, official endpoint
scoring recomputes the value from the primary fields as
``special_actual in selected_numbers``.

All findings are retrospective research diagnostics.  They do not establish
future performance, increased winning odds, betting usefulness, or production
readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Optional, Sequence


SCHEMA_ID = "p544c_unified_lottery_replay_success_evaluation.v1"
TASK_ID = "P544C_R1_RESUME_UNIFIED_EVALUATOR_WITH_SPECIAL_HIT_CONTRACT_AMENDMENT"
PINNED_SOURCE_COMMIT = "0279409fbfeba94c2b1be667c0b99f9a39e45069"
OUTPUT_DATE = "20260710"
DEFAULT_PERMUTATIONS = 1_000
SEED_REGISTRY = {"p543d_within_lottery_outcome_repairing": 543_010}
P543C_FAMILY_SIZE = 10
FAMILY_ALPHA = 0.05
MIN_SUPPORT_DRAWS = 30
MIN_EXPECTED_SUCCESSES = 5.0
PRIMARY_WINDOWS = (50, 300, 750)
WINDOW_LABELS = {50: "SHORT", 300: "MID", 750: "LONG"}
CLASSIFICATION_VOCABULARY = (
    "insufficient_data",
    "descriptive_only",
    "below_baseline",
    "near_baseline",
    "chronologically_unstable",
    "diagnostic_candidate",
    "research_candidate",
    "holdout_supported_candidate",
    "rejected",
)

BIG_LOTTO_UNIVERSE = 13_983_816
BIG_LOTTO_MAIN_HIT_NUMERATORS = {
    0: 6_096_454,
    1: 5_775_588,
    2: 1_851_150,
    3: 246_820,
    4: 13_545,
    5: 258,
    6: 1,
}
BIG_LOTTO_M3_PLUS_NUMERATOR = 260_624
BIG_LOTTO_ANY_PRIZE_NUMERATOR = 432_824

SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "role": "p543c_per_draw_contract",
        "path": "outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json",
        "sha256": "71be8549daddbc0e810e17e3e6afbd49eedc02eee402c017e562a834ef1448a5",
        "bytes": 515_478,
        "uses": {"per_draw_evaluation": True, "aggregate_verification": False, "summary_normalization": False},
    },
    {
        "role": "p273a_distinct_ticket_identity",
        "path": "outputs/research/p273a_distinct_ticket_identity_20260615.json",
        "sha256": "b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0",
        "bytes": 26_707_364,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": True, "summary_normalization": False},
    },
    {
        "role": "p273a_primary_window_observed_counts",
        "path": "outputs/research/p273a_primary_window_observed_counts_20260615.json",
        "sha256": "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73",
        "bytes": 116_807,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": True, "summary_normalization": False},
    },
    {
        "role": "p273a_prize_aware_inference",
        "path": "outputs/research/p273a_prize_aware_inferential_validation_20260615.json",
        "sha256": "ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe",
        "bytes": 4_658_516,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": True, "summary_normalization": False},
    },
    {
        "role": "p281a_cross_lottery_verification",
        "path": "outputs/research/p281a_cross_lottery_prize_aware_validation_20260619.json",
        "sha256": "584d4e0de7f02d5b649d10f75a541731b07a221c4d26c83ab1f5ded5c218b68d",
        "bytes": 695_172,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": True, "summary_normalization": False},
    },
    {
        "role": "p542a_scoreboard",
        "path": "outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json",
        "sha256": "c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b",
        "bytes": 1_999_750,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": False, "summary_normalization": True},
    },
    {
        "role": "p536c_lift_extension",
        "path": "outputs/research/p536c_success_matrix_lift_extension_20260708.json",
        "sha256": "e98443bbe549ec23d46187689bd810423bfa07d2626fa2b98d919c96b54ac316",
        "bytes": 1_761_713,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": False, "summary_normalization": True},
    },
    {
        "role": "p543a_stability_packet",
        "path": "outputs/research/p543a_scoreboard_stability_packet_20260710.json",
        "sha256": "190fc9f9a8f2d4817a955204b5af1f5d9cf1fb186fa0695713202235f306e0e5",
        "bytes": 987_573,
        "uses": {"per_draw_evaluation": False, "aggregate_verification": False, "summary_normalization": True},
    },
)

FROZEN_SPEC = {
    "schema_id": SCHEMA_ID,
    "pinned_source_commit": PINNED_SOURCE_COMMIT,
    "windows": {"SHORT": 50, "MID": 300, "LONG": 750, "reference_only": [1500, "all_history"]},
    "draw_is_independent_unit": True,
    "p543c_family_size": P543C_FAMILY_SIZE,
    "family_alpha": FAMILY_ALPHA,
    "permutations": DEFAULT_PERMUTATIONS,
    "seed_registry": SEED_REGISTRY,
    "big_lotto_main_hit_numerators": BIG_LOTTO_MAIN_HIT_NUMERATORS,
    "big_lotto_m3_plus_numerator": BIG_LOTTO_M3_PLUS_NUMERATOR,
    "big_lotto_any_prize_numerator": BIG_LOTTO_ANY_PRIZE_NUMERATOR,
    "big_lotto_universe": BIG_LOTTO_UNIVERSE,
    "special_hit_amendment": {
        "authoritative_primary_fields": ["selected_numbers", "special_actual"],
        "recomputation_rule": "special_actual in selected_numbers",
        "source_field_authority": "non_authoritative_derived_field",
        "resolution": "semantic_drift_explained_recomputed_from_primary_fields",
    },
}


class EvaluationError(RuntimeError):
    """Base class for fail-closed evaluation errors."""


class InputIntegrityError(EvaluationError):
    """Raised when a pinned source blob differs from its manifest."""


class ContractSemanticError(EvaluationError):
    """Raised when primary fields are malformed or committed contracts drift."""


class CrossLotteryPoolingError(EvaluationError):
    """Raised when raw rates from different lotteries would be pooled."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FROZEN_SPEC_DIGEST = _sha256(_canonical_json_bytes(FROZEN_SPEC))


def _round(value: float, places: int = 12) -> float:
    return round(float(value), places)


def _rate_string(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.12f}"


def validate_repo_relative_json_path(path: str) -> str:
    """Reject absolute, parent-traversing, and database paths before any read."""
    pure = PurePosixPath(path)
    if not path or pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise InputIntegrityError(f"source path must be a normalized repo-relative path: {path!r}")
    if pure.suffix.lower() != ".json":
        raise InputIntegrityError(f"source path must identify a JSON artifact: {path!r}")
    return path


class GitBlobSource:
    """Read only explicitly named blobs from one immutable commit."""

    def __init__(self, repo_root: Path, commit: str = PINNED_SOURCE_COMMIT):
        self.repo_root = repo_root.resolve()
        resolved = self._git_text("rev-parse", f"{commit}^{{commit}}").strip()
        if resolved != PINNED_SOURCE_COMMIT:
            raise InputIntegrityError(
                f"source commit changed: expected {PINNED_SOURCE_COMMIT}, got {resolved}"
            )
        self.commit = resolved

    def _git_bytes(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(self.repo_root), *args],
            check=True,
            capture_output=True,
        ).stdout

    def _git_text(self, *args: str) -> str:
        return self._git_bytes(*args).decode("utf-8")

    def read(self, path: str) -> bytes:
        safe_path = validate_repo_relative_json_path(path)
        return self._git_bytes("show", f"{self.commit}:{safe_path}")

    def commit_timestamp_utc(self) -> str:
        raw = self._git_text("show", "-s", "--format=%cI", self.commit).strip()
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise InputIntegrityError("pinned commit timestamp lacks a timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def verify_source_bytes(spec: Mapping[str, Any], raw: bytes) -> None:
    if len(raw) != spec["bytes"]:
        raise InputIntegrityError(
            f"input byte-size mismatch for {spec['path']}: expected {spec['bytes']}, got {len(raw)}"
        )
    actual = _sha256(raw)
    if actual != spec["sha256"]:
        raise InputIntegrityError(
            f"input SHA-256 mismatch for {spec['path']}: expected {spec['sha256']}, got {actual}"
        )


def _absolute_reference_count(node: Any) -> int:
    if isinstance(node, Mapping):
        return sum(_absolute_reference_count(value) for value in node.values())
    if isinstance(node, list):
        return sum(_absolute_reference_count(value) for value in node)
    if isinstance(node, str) and (node.startswith("/") or node.startswith("file:/")):
        return 1
    return 0


def load_pinned_inputs(repo_root: Path) -> tuple[dict[str, Mapping[str, Any]], list[dict[str, Any]], str]:
    source = GitBlobSource(repo_root)
    documents: dict[str, Mapping[str, Any]] = {}
    manifest: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        raw = source.read(spec["path"])
        verify_source_bytes(spec, raw)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InputIntegrityError(f"invalid UTF-8 JSON: {spec['path']}") from exc
        if not isinstance(parsed, Mapping):
            raise InputIntegrityError(f"top-level JSON must be an object: {spec['path']}")
        documents[spec["role"]] = parsed
        absolute_count = _absolute_reference_count(parsed)
        portability = "portable_repo_relative_blob"
        if absolute_count:
            portability = "portable_blob_with_absolute_provenance_warning_not_opened"
        declared_link_status = "verified_or_not_applicable"
        if spec["role"] == "p273a_prize_aware_inference":
            declared_link_status = "stale_reference_explained"
        manifest.append(
            {
                "role": spec["role"],
                "path": spec["path"],
                "pinned_source_commit": source.commit,
                "sha256": spec["sha256"],
                "bytes": spec["bytes"],
                "json_parse_status": "valid",
                "raw_integrity_status": "verified_raw_bytes",
                "portability_status": portability,
                "absolute_provenance_reference_count": absolute_count,
                "declared_link_status": declared_link_status,
                "used_for": dict(spec["uses"]),
            }
        )
    manifest.sort(key=lambda item: (item["role"], item["path"]))
    return documents, manifest, source.commit_timestamp_utc()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractSemanticError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractSemanticError(f"{label} must be a list")
    return value


def _integer(value: Any, label: str, minimum: Optional[int] = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractSemanticError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractSemanticError(f"{label} must be at least {minimum}")
    return value


def _numbers(value: Any, label: str, *, count: int, maximum: int) -> list[int]:
    items = _list(value, label)
    if len(items) != count:
        raise ContractSemanticError(f"{label} must contain exactly {count} numbers")
    if any(not isinstance(item, int) or isinstance(item, bool) for item in items):
        raise ContractSemanticError(f"{label} must contain integers")
    if len(set(items)) != count:
        raise ContractSemanticError(f"{label} contains duplicates")
    if any(item < 1 or item > maximum for item in items):
        raise ContractSemanticError(f"{label} contains an out-of-range number")
    return list(items)


def _row_identifier(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "draw_order": row["draw_order"],
        "draw_id": row["draw_id"],
        "draw_date": row["draw_date"],
    }


def recompute_big_lotto_special_hit(selected_numbers: Sequence[int], special_actual: Any) -> bool:
    """Apply the R1 authoritative BIG_LOTTO special-hit rule."""
    if not isinstance(special_actual, int) or isinstance(special_actual, bool) or not 1 <= special_actual <= 49:
        raise ContractSemanticError("special_actual is missing or malformed")
    return special_actual in set(selected_numbers)


def score_big_lotto_any_prize(main_hit_count: int, recomputed_special_hit: bool) -> bool:
    """Return the amended official any-prize endpoint for one BIG_LOTTO ticket."""
    return main_hit_count >= 3 or (main_hit_count == 2 and recomputed_special_hit)


def audit_p543c(packet: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _list(packet.get("candidate_subset"), "p543c.candidate_subset")
    contract = _mapping(packet.get("contract"), "p543c.contract")
    rows = _list(contract.get("rows"), "p543c.contract.rows")
    if contract.get("contract_status") != "generated":
        raise ContractSemanticError("P543C contract status is not generated")
    if len(candidates) != 10 or len(rows) != 500:
        raise ContractSemanticError("P543C must contain 10 candidates and 500 rows")

    candidate_meta: dict[str, dict[str, Any]] = {}
    for position, raw_candidate in enumerate(candidates):
        candidate = _mapping(raw_candidate, f"candidate_subset[{position}]")
        candidate_id = candidate.get("candidate_id")
        strategy_id = candidate.get("strategy_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ContractSemanticError("candidate_id must be a non-empty string")
        if not isinstance(strategy_id, str) or candidate_id != f"{strategy_id}:{candidate.get('bet_index')}":
            raise ContractSemanticError(f"candidate linkage is malformed: {candidate_id!r}")
        if candidate.get("lottery") != "BIG_LOTTO":
            raise ContractSemanticError("P543C candidate is not BIG_LOTTO")
        if candidate_id in candidate_meta:
            raise ContractSemanticError(f"duplicate candidate: {candidate_id}")
        candidate_meta[candidate_id] = {
            "candidate_id": candidate_id,
            "strategy_id": strategy_id,
            "bet_index": candidate["bet_index"],
            "lottery_type": "BIG_LOTTO",
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_draw_cells: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    main_mismatch_count = 0
    special_actual_present = 0
    special_selected_null = 0
    source_special_hit_count = 0
    recomputed_special_hit_count = 0
    m2_special_count = 0
    seen_keys: set[tuple[Any, ...]] = set()
    seen_candidate_draw_ids: set[tuple[str, str]] = set()
    official_outcomes_by_draw: dict[str, tuple[str, tuple[int, ...], int]] = {}

    for position, raw_row in enumerate(rows):
        row = _mapping(raw_row, f"contract.rows[{position}]")
        candidate_id = row.get("candidate_id")
        if candidate_id not in candidate_meta:
            raise ContractSemanticError(f"row {position} references an unknown candidate")
        if row.get("lottery") != "BIG_LOTTO":
            raise ContractSemanticError(f"row {position} is not BIG_LOTTO")
        selected = _numbers(row.get("selected_numbers"), f"row {position}.selected_numbers", count=6, maximum=49)
        actual = _numbers(row.get("actual_numbers"), f"row {position}.actual_numbers", count=6, maximum=49)
        stored_main = _integer(row.get("hit_count"), f"row {position}.hit_count", minimum=0)
        recomputed_main = len(set(selected) & set(actual))
        if stored_main != recomputed_main:
            main_mismatch_count += 1
        special_actual = row.get("special_actual")
        if not isinstance(special_actual, int) or isinstance(special_actual, bool) or not 1 <= special_actual <= 49:
            raise ContractSemanticError(f"row {position}.special_actual is missing or malformed")
        if special_actual in actual:
            raise ContractSemanticError(f"row {position}.special_actual duplicates a main outcome")
        special_actual_present += 1
        if row.get("special_selected") is None:
            special_selected_null += 1
        source_special_hit = row.get("special_hit")
        if source_special_hit not in (0, 1, False, True):
            raise ContractSemanticError(f"row {position}.special_hit is malformed")
        source_special_hit_bool = bool(source_special_hit)
        recomputed_special_hit = recompute_big_lotto_special_hit(selected, special_actual)
        source_special_hit_count += int(source_special_hit_bool)
        recomputed_special_hit_count += int(recomputed_special_hit)
        if stored_main == 2 and recomputed_special_hit:
            m2_special_count += 1

        draw_order = _integer(row.get("draw_order"), f"row {position}.draw_order", minimum=1)
        draw_id = row.get("draw_id")
        draw_date = row.get("draw_date")
        if not isinstance(draw_id, str) or not draw_id or not isinstance(draw_date, str) or not draw_date:
            raise ContractSemanticError(f"row {position} has malformed draw identifiers")
        stable_key = (candidate_id, draw_order, draw_id, draw_date)
        if stable_key in seen_keys:
            raise ContractSemanticError(f"duplicate P543C row key: {stable_key}")
        seen_keys.add(stable_key)
        candidate_draw_key = (candidate_id, draw_id)
        if candidate_draw_key in seen_candidate_draw_ids:
            raise ContractSemanticError(f"duplicate candidate/draw identity: {candidate_draw_key}")
        seen_candidate_draw_ids.add(candidate_draw_key)
        official_outcome = (draw_date, tuple(sorted(actual)), special_actual)
        previous_outcome = official_outcomes_by_draw.get(draw_id)
        if previous_outcome is not None and previous_outcome != official_outcome:
            raise ContractSemanticError(f"conflicting official primary fields for draw_id {draw_id}")
        official_outcomes_by_draw[draw_id] = official_outcome

        normalized = {
            "candidate_id": candidate_id,
            "candidate_label": row.get("candidate_label") or candidate_id,
            "strategy_id": candidate_meta[candidate_id]["strategy_id"],
            "bet_index": candidate_meta[candidate_id]["bet_index"],
            "lottery_type": "BIG_LOTTO",
            "draw_order": draw_order,
            "draw_id": draw_id,
            "draw_date": draw_date,
            "selected_numbers": selected,
            "actual_numbers": actual,
            "special_actual": special_actual,
            "special_selected": row.get("special_selected"),
            "source_hit_count": stored_main,
            "recomputed_hit_count": recomputed_main,
            "source_special_hit": int(source_special_hit_bool),
            "recomputed_special_hit": recomputed_special_hit,
            "main_hit_consistent": stored_main == recomputed_main,
            "special_hit_consistent": source_special_hit_bool == recomputed_special_hit,
            "official_any_prize_success": score_big_lotto_any_prize(recomputed_main, recomputed_special_hit),
        }
        grouped[candidate_id].append(normalized)
        per_draw_cells.append(normalized)
        if source_special_hit_bool != recomputed_special_hit:
            mismatches.append(
                {
                    **_row_identifier(normalized),
                    "source_special_hit": int(source_special_hit_bool),
                    "recomputed_special_hit": recomputed_special_hit,
                    "main_hit_count": recomputed_main,
                }
            )

    if main_mismatch_count:
        raise ContractSemanticError(f"P543C main hit-count drift: {main_mismatch_count} rows")
    for candidate_id, candidate_rows in grouped.items():
        candidate_rows.sort(key=lambda row: (row["draw_order"], row["draw_id"], row["draw_date"]))
        if len(candidate_rows) != 50:
            raise ContractSemanticError(f"candidate {candidate_id} does not have 50 rows")
        if [row["draw_order"] for row in candidate_rows] != list(range(1, 51)):
            raise ContractSemanticError(f"candidate {candidate_id} draw_order is not contiguous 1..50")

    per_draw_cells.sort(
        key=lambda row: (row["candidate_id"], row["draw_order"], row["draw_id"], row["draw_date"])
    )
    mismatches.sort(key=lambda row: (row["candidate_id"], row["draw_order"], row["draw_id"], row["draw_date"]))
    if (
        special_actual_present != 500
        or source_special_hit_count != 0
        or recomputed_special_hit_count != 63
        or len(mismatches) != 63
        or m2_special_count != 7
    ):
        raise ContractSemanticError("owner-approved special-hit amendment fixtures did not reproduce")

    return {
        "candidate_meta": dict(sorted(candidate_meta.items())),
        "grouped_rows": dict(sorted(grouped.items())),
        "per_draw_cells": per_draw_cells,
        "contract_shape": {
            "candidate_count": len(candidate_meta),
            "row_count": len(per_draw_cells),
            "rows_per_candidate": {candidate_id: len(candidate_rows) for candidate_id, candidate_rows in sorted(grouped.items())},
            "main_hit_count_mismatch_count": main_mismatch_count,
            "chronological_sort_key": ["draw_order", "draw_id", "draw_date"],
        },
        "special_hit_contract_amendment": {
            "source_artifact_path": SOURCE_SPECS[0]["path"],
            "source_artifact_sha256": SOURCE_SPECS[0]["sha256"],
            "source_field": "special_hit",
            "authoritative_primary_fields": ["selected_numbers", "special_actual"],
            "recomputation_rule": "special_actual in selected_numbers",
            "source_special_hit_count": source_special_hit_count,
            "recomputed_special_hit_count": recomputed_special_hit_count,
            "mismatch_count": len(mismatches),
            "special_actual_present_rows": special_actual_present,
            "special_selected_null_rows": special_selected_null,
            "affected_row_ids": mismatches,
            "m2_plus_special_prize_case_count": m2_special_count,
            "source_field_authority": "non_authoritative_derived_field",
            "resolution": "semantic_drift_explained_recomputed_from_primary_fields",
            "reason": "selected_numbers and special_actual are primary committed facts; special_hit is an inconsistent derived convenience field",
            "upstream_artifact_modified": False,
        },
    }


def _log_binomial_pmf(k: int, n: int, probability: float) -> float:
    if probability <= 0.0:
        return 0.0 if k == 0 else float("-inf")
    if probability >= 1.0:
        return 0.0 if k == n else float("-inf")
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(probability)
        + (n - k) * math.log1p(-probability)
    )


def binomial_upper_pvalue(k: int, n: int, probability: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return min(
        1.0,
        math.fsum(
            math.exp(value)
            for value in (_log_binomial_pmf(index, n, probability) for index in range(k, n + 1))
            if value != float("-inf")
        ),
    )


def binomial_lower_pvalue(k: int, n: int, probability: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return 1.0 - binomial_upper_pvalue(k + 1, n, probability)


def wilson_interval(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    proportion = k / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = (proportion + z2 / (2 * n)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / n + z2 / (4 * n * n)) / denominator
    return (max(0.0, center - half), min(1.0, center + half))


def _bisect(function: Any, low: float, high: float, *, tolerance: float = 1e-10) -> float:
    low_value = function(low)
    high_value = function(high)
    if low_value == 0.0:
        return low
    if high_value == 0.0:
        return high
    for _ in range(200):
        middle = (low + high) / 2.0
        middle_value = function(middle)
        if abs(middle_value) < tolerance or high - low < tolerance:
            return middle
        if (middle_value > 0) == (low_value > 0):
            low, low_value = middle, middle_value
        else:
            high = middle
    return (low + high) / 2.0


def clopper_pearson_interval(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    alpha = 0.05
    low = 0.0 if k == 0 else _bisect(lambda p: binomial_upper_pvalue(k, n, p) - alpha / 2, 0.0, 1.0)
    high = 1.0 if k == n else _bisect(lambda p: binomial_lower_pvalue(k, n, p) - alpha / 2, 0.0, 1.0)
    return (low, high)


def infer_binomial(observed: int, total: int, baseline: float, family_size: int) -> dict[str, Any]:
    observed_rate = observed / total if total else 0.0
    upper = binomial_upper_pvalue(observed, total, baseline)
    lower = binomial_lower_pvalue(observed, total, baseline)
    wilson = wilson_interval(observed, total)
    clopper = clopper_pearson_interval(observed, total)
    relative_lift = observed_rate / baseline if baseline else None
    return {
        "observed_successes": observed,
        "total_draws": total,
        "observed_rate": _round(observed_rate),
        "baseline_rate": _round(baseline),
        "expected_successes": _round(total * baseline),
        "absolute_excess": _round(observed_rate - baseline),
        "absolute_excess_percentage_points": _round((observed_rate - baseline) * 100, 8),
        "relative_lift": _round(relative_lift) if relative_lift is not None else None,
        "log10_lift": _round(math.log10(relative_lift)) if relative_lift and relative_lift > 0 else None,
        "wilson_ci_95": [_round(wilson[0]), _round(wilson[1])],
        "clopper_pearson_ci_95": [_round(clopper[0]), _round(clopper[1])],
        "raw_p_value_one_sided_upper": _round(upper),
        "raw_p_value_one_sided_lower": _round(lower),
        "bonferroni_family_size": family_size,
        "bonferroni_p_value_upper": _round(min(1.0, upper * family_size)),
        "bonferroni_p_value_lower": _round(min(1.0, lower * family_size)),
    }


def chronological_stability(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row["draw_order"], row["draw_id"], row["draw_date"]))
    midpoint = len(ordered) // 2
    early = ordered[:midpoint]
    late = ordered[midpoint:]
    early_success = sum(bool(row["official_any_prize_success"]) for row in early)
    late_success = sum(bool(row["official_any_prize_success"]) for row in late)
    early_rate = early_success / len(early)
    late_rate = late_success / len(late)
    delta = late_rate - early_rate
    pooled = (early_success + late_success) / len(ordered)
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / len(early) + 1 / len(late)))
    if standard_error == 0:
        z_score = 0.0
        two_sided = 1.0
        status = "no_detected_instability_zero_variance"
    else:
        z_score = delta / standard_error
        two_sided = math.erfc(abs(z_score) / math.sqrt(2))
        status = "chronologically_unstable" if two_sided <= 0.05 else "no_detected_instability"
    return {
        "sort_key": ["draw_order", "draw_id", "draw_date"],
        "early": {"draws": len(early), "successes": early_success, "rate": _round(early_rate)},
        "late": {"draws": len(late), "successes": late_success, "rate": _round(late_rate)},
        "late_minus_early_rate_delta": _round(delta),
        "pooled_standard_error": _round(standard_error),
        "z_score": _round(z_score),
        "two_sided_p_value": _round(two_sided),
        "status": status,
        "absolute_delta_alone_is_decision_gate": False,
    }


def pairing_permutation_diagnostics(
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    seed: int = SEED_REGISTRY["p543d_within_lottery_outcome_repairing"],
    permutations: int = DEFAULT_PERMUTATIONS,
) -> dict[str, dict[str, Any]]:
    if permutations < 1:
        raise ValueError("permutations must be positive")
    entries: list[tuple[str, int, Mapping[str, Any]]] = []
    for candidate_id in sorted(grouped):
        for index, row in enumerate(grouped[candidate_id]):
            entries.append((candidate_id, index, row))
    outcomes = [(row["actual_numbers"], row["special_actual"]) for _, _, row in entries]
    selected = {(candidate_id, index): set(row["selected_numbers"]) for candidate_id, index, row in entries}
    rng = random.Random(seed)
    distributions: dict[str, list[int]] = {candidate_id: [] for candidate_id in sorted(grouped)}
    for _ in range(permutations):
        shuffled = list(outcomes)
        rng.shuffle(shuffled)
        successes = {candidate_id: 0 for candidate_id in sorted(grouped)}
        for (candidate_id, index, _), (actual_numbers, special_actual) in zip(entries, shuffled):
            chosen = selected[(candidate_id, index)]
            main_hits = len(chosen & set(actual_numbers))
            special_hit = recompute_big_lotto_special_hit(tuple(chosen), special_actual)
            if score_big_lotto_any_prize(main_hits, special_hit):
                successes[candidate_id] += 1
        for candidate_id in sorted(successes):
            distributions[candidate_id].append(successes[candidate_id])

    result: dict[str, dict[str, Any]] = {}
    for candidate_id in sorted(grouped):
        observed = sum(bool(row["official_any_prize_success"]) for row in grouped[candidate_id])
        values = distributions[candidate_id]
        at_or_below = sum(value <= observed for value in values)
        at_or_above = sum(value >= observed for value in values)
        result[candidate_id] = {
            "null_hypothesis": "within-lottery outcome re-pairing alignment/timing null; not an absolute-skill null",
            "p543d_pairing_semantics": "all 500 outcome tuples shuffled within lottery using one stateful RNG",
            "seed": seed,
            "permutations": permutations,
            "observed_success_count": observed,
            "permutation_success_count_distribution": {
                "mean": _round(math.fsum(values) / permutations),
                "minimum": min(values),
                "maximum": max(values),
            },
            "null_at_or_below_observed_count": at_or_below,
            "null_at_or_above_observed_count": at_or_above,
            "inclusive_empirical_percentile": _round(at_or_below / permutations),
            "add_one_empirical_upper_p_value": _round((1 + at_or_above) / (permutations + 1)),
        }
    return result


def _candidate_classification(inference: Mapping[str, Any], stability: Mapping[str, Any]) -> str:
    if stability["status"] == "chronologically_unstable":
        return "chronologically_unstable"
    if inference["absolute_excess"] > 0 and inference["bonferroni_p_value_upper"] <= FAMILY_ALPHA:
        return "diagnostic_candidate"
    if inference["absolute_excess"] < 0 and inference["bonferroni_p_value_lower"] <= FAMILY_ALPHA:
        return "below_baseline"
    low, high = inference["wilson_ci_95"]
    if low <= inference["baseline_rate"] <= high:
        return "near_baseline"
    return "descriptive_only"


def build_track1(audit: Mapping[str, Any], permutations: int) -> dict[str, Any]:
    grouped = audit["grouped_rows"]
    baseline = BIG_LOTTO_ANY_PRIZE_NUMERATOR / BIG_LOTTO_UNIVERSE
    permutation = pairing_permutation_diagnostics(grouped, permutations=permutations)
    candidates: list[dict[str, Any]] = []
    for candidate_id in sorted(grouped):
        rows = grouped[candidate_id]
        spectrum = Counter(row["recomputed_hit_count"] for row in rows)
        exact = {f"M{k}": spectrum.get(k, 0) for k in range(7)}
        cumulative = {f"M{k}plus": sum(value for hit, value in spectrum.items() if hit >= k) for k in range(1, 7)}
        source_special = sum(row["source_special_hit"] for row in rows)
        recomputed_special = sum(bool(row["recomputed_special_hit"]) for row in rows)
        special_mismatches = sum(not row["special_hit_consistent"] for row in rows)
        m1_special = sum(row["recomputed_hit_count"] == 1 and row["recomputed_special_hit"] for row in rows)
        m2_special = sum(row["recomputed_hit_count"] == 2 and row["recomputed_special_hit"] for row in rows)
        m3_special = sum(row["recomputed_hit_count"] == 3 and row["recomputed_special_hit"] for row in rows)
        m3_plus_special = sum(row["recomputed_hit_count"] >= 3 and row["recomputed_special_hit"] for row in rows)
        successes = sum(bool(row["official_any_prize_success"]) for row in rows)
        inference = infer_binomial(successes, len(rows), baseline, P543C_FAMILY_SIZE)
        stability = chronological_stability(rows)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_label": rows[0]["candidate_label"],
                "strategy_id": rows[0]["strategy_id"],
                "bet_index": rows[0]["bet_index"],
                "lottery_type": "BIG_LOTTO",
                "window": 50,
                "window_label": "SHORT",
                "total_draws": len(rows),
                "valid_prediction_rows": len(rows),
                "no_prediction_rows": 0,
                "excluded_invalid_draws": 0,
                "coverage": 1.0,
                "denominator_partition": {
                    "supported_draws": len(rows),
                    "no_prediction_draws": 0,
                    "excluded_invalid_draws": 0,
                    "window_draw_count": len(rows),
                    "partition_valid": True,
                },
                "exact_main_hit_counts": exact,
                "cumulative_main_hit_counts": cumulative,
                "full_hit_count": exact["M6"],
                "full_hit_rate": _round(exact["M6"] / len(rows)),
                "m3_plus_count": cumulative["M3plus"],
                "m3_plus_rate": _round(cumulative["M3plus"] / len(rows)),
                "source_special_hit_count": source_special,
                "recomputed_special_hit_count": recomputed_special,
                "special_hit_mismatch_count": special_mismatches,
                "m1_and_special_count": m1_special,
                "m2_and_special_count": m2_special,
                "m3_and_special_count": m3_special,
                "m3_plus_and_special_count": m3_plus_special,
                "official_any_prize_count": successes,
                "official_any_prize_rate": _round(successes / len(rows)),
                "official_any_prize_rate_12dp": f"{successes / len(rows):.12f}",
                "analytic_random_baseline": {
                    "numerator": BIG_LOTTO_ANY_PRIZE_NUMERATOR,
                    "denominator": BIG_LOTTO_UNIVERSE,
                    "rate": _round(baseline),
                    "rate_12dp": _rate_string(BIG_LOTTO_ANY_PRIZE_NUMERATOR, BIG_LOTTO_UNIVERSE),
                },
                "inference": inference,
                "chronological_stability": stability,
                "pairing_permutation": permutation[candidate_id],
                "classification": _candidate_classification(inference, stability),
                "classification_ceiling": "diagnostic_candidate_short_window_only",
            }
        )
    summary = Counter(item["classification"] for item in candidates)
    return {
        "scope": "BIG_LOTTO_SHORT_50",
        "endpoint": "main_hit_count >= 3 OR (main_hit_count == 2 AND recomputed_special_hit)",
        "candidate_count": len(candidates),
        "candidate_evaluations": candidates,
        "classification_counts": {label: summary.get(label, 0) for label in CLASSIFICATION_VOCABULARY},
        "unavailable_windows": [
            {"window": 300, "window_label": "MID", "status": "insufficient_data_missing_per_draw_outcomes"},
            {"window": 750, "window_label": "LONG", "status": "insufficient_data_missing_per_draw_outcomes"},
            {"window": 1500, "window_label": "REFERENCE_ONLY", "status": "descriptive_reference_not_executed"},
            {"window": "all_history", "window_label": "REFERENCE_ONLY", "status": "descriptive_reference_not_executed"},
        ],
    }


def exact_distinct_ticket_probability(total: int, winning: int, ticket_count: int) -> float:
    if not 0 < winning < total or not 1 <= ticket_count <= total:
        raise ValueError("invalid ticket-universe parameters")
    if ticket_count == 1:
        return winning / total
    if ticket_count > total - winning:
        return 1.0
    log_no_win = math.fsum(math.log1p(-winning / (total - index)) for index in range(ticket_count))
    return -math.expm1(log_no_win)


def derive_analytic_constants() -> dict[str, dict[str, Any]]:
    daily_total = math.comb(39, 5)
    daily_parts = [math.comb(5, k) * math.comb(34, 5 - k) for k in range(2, 6)]
    daily_winning = sum(daily_parts)
    big_m3 = [math.comb(6, k) * math.comb(43, 6 - k) for k in range(3, 7)]
    big_low = math.comb(6, 2) * math.comb(42, 3)
    power_m3_parts = [8 * math.comb(6, k) * math.comb(32, 6 - k) for k in range(3, 7)]
    power_low_parts = [math.comb(6, 1) * math.comb(32, 5), math.comb(6, 2) * math.comb(32, 4)]
    power_total = 8 * math.comb(38, 6)
    power_winning = sum(power_m3_parts) + sum(power_low_parts)
    return {
        "DAILY_539": {
            "universe": daily_total,
            "any_prize_numerator": daily_winning,
            "component_numerators": daily_parts,
            "rate": _round(daily_winning / daily_total),
            "rate_12dp": _rate_string(daily_winning, daily_total),
        },
        "BIG_LOTTO": {
            "universe": BIG_LOTTO_UNIVERSE,
            "any_prize_numerator": sum(big_m3) + big_low,
            "m3_plus_numerator": sum(big_m3),
            "m2_plus_special_numerator": big_low,
            "rate": _round((sum(big_m3) + big_low) / BIG_LOTTO_UNIVERSE),
            "rate_12dp": _rate_string(sum(big_m3) + big_low, BIG_LOTTO_UNIVERSE),
        },
        "POWER_LOTTO": {
            "universe": power_total,
            "any_prize_numerator": power_winning,
            "m3_plus_numerator": sum(power_m3_parts),
            "low_hit_plus_second_zone_numerator": sum(power_low_parts),
            "rate": _round(power_winning / power_total),
            "rate_12dp": _rate_string(power_winning, power_total),
        },
    }


def _equivalent(expected: Any, recomputed: Any) -> bool:
    if isinstance(expected, float) or isinstance(recomputed, float):
        try:
            return abs(float(expected) - float(recomputed)) <= 5e-12
        except (TypeError, ValueError):
            return False
    return expected == recomputed


def _record_check(
    mismatches: list[dict[str, Any]],
    counter: list[int],
    key: str,
    field: str,
    expected: Any,
    recomputed: Any,
) -> None:
    counter[0] += 1
    if not _equivalent(expected, recomputed):
        mismatches.append(
            {
                "cell": key,
                "field": field,
                "expected_value": expected,
                "recomputed_value": recomputed,
                "classification": "blocking_load_bearing_mismatch",
            }
        )


def _statistical_status(excess: float, upper_adjusted: float, lower_adjusted: float) -> str:
    if excess > 0 and upper_adjusted <= FAMILY_ALPHA:
        return "SIGNIFICANT_POSITIVE_CORRECTED"
    if excess < 0 and lower_adjusted <= FAMILY_ALPHA:
        return "SIGNIFICANT_NEGATIVE_CORRECTED"
    if excess > 0:
        return "POSITIVE_NOT_CORRECTED"
    if excess < 0:
        return "NEGATIVE_NOT_CORRECTED"
    return "FLAT"


def _recomputed_stability(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    short, mid, long = windows["SHORT"], windows["MID"], windows["LONG"]
    all_evaluable = bool(short["evaluable"] and mid["evaluable"] and long["evaluable"])
    criteria = {
        "c1_all_three_evaluable": all_evaluable,
        "c2_mid_excess_strictly_positive": bool(all_evaluable and mid.get("absolute_excess", 0) > 0),
        "c3_long_excess_strictly_positive": bool(all_evaluable and long.get("absolute_excess", 0) > 0),
        "c4_short_excess_nonnegative": bool(all_evaluable and short.get("absolute_excess", -1) >= 0),
        "c5_mid_or_long_bonferroni_sig": bool(
            all_evaluable and (mid.get("significant_positive") or long.get("significant_positive"))
        ),
        "c6_short_cannot_trigger_promotion": True,
        "c7_no_negative_or_insufficient_window": bool(
            all_evaluable and not any(window.get("significant_negative") for window in windows.values())
        ),
        "c8_no_post_outcome_family_or_threshold_change": True,
        "c9_nested_not_independent_replications": True,
        "c10_passing_is_research_go_candidate_only": True,
    }
    operational = all(
        criteria[name]
        for name in (
            "c1_all_three_evaluable",
            "c2_mid_excess_strictly_positive",
            "c3_long_excess_strictly_positive",
            "c4_short_excess_nonnegative",
            "c5_mid_or_long_bonferroni_sig",
            "c7_no_negative_or_insufficient_window",
        )
    )
    operational_names = {
        "c1_all_three_evaluable",
        "c2_mid_excess_strictly_positive",
        "c3_long_excess_strictly_positive",
        "c4_short_excess_nonnegative",
        "c5_mid_or_long_bonferroni_sig",
        "c7_no_negative_or_insufficient_window",
    }
    return {
        "status": "STABILITY_PASS" if operational else "STABILITY_FAIL",
        "criteria": criteria,
        "fail_reasons": [name for name, passed in criteria.items() if name in operational_names and not passed],
    }


def _window_decision(label: str, window: Mapping[str, Any], stability: Mapping[str, Any]) -> str:
    if not window["evaluable"]:
        return "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
    if window["absolute_excess"] <= 0 or window["raw_p_value_one_sided_upper"] > FAMILY_ALPHA:
        return "PRIZE_AWARE_NULL"
    if label in ("MID", "LONG") and window["significant_positive"] and stability["status"] == "STABILITY_PASS":
        return "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    return "PRIZE_AWARE_DESCRIPTIVE_ONLY"


def verify_p273a(
    identity: Mapping[str, Any], observed: Mapping[str, Any], inference: Mapping[str, Any]
) -> dict[str, Any]:
    constants = derive_analytic_constants()
    identity_cells = {(cell["lottery_type"], cell["strategy_id"]): cell for cell in identity["cells"]}
    observed_cells = {(cell["lottery_type"], cell["strategy_id"]): cell for cell in observed["cells"]}
    inference_groups = {(group["lottery_type"], group["strategy_id"]): group for group in inference["inference"]["groups"]}
    if set(identity_cells) != set(observed_cells) or set(identity_cells) != set(inference_groups) or len(identity_cells) != 36:
        raise ContractSemanticError("P273A strategy-cell sets differ")

    mismatches: list[dict[str, Any]] = []
    checks = [0]
    verification_rows: list[dict[str, Any]] = []
    for lottery, strategy in sorted(identity_cells):
        identity_windows = {window["window"]: window for window in identity_cells[(lottery, strategy)]["windows"]}
        observed_windows = {window["window"]: window for window in observed_cells[(lottery, strategy)]["windows"]}
        source_group = inference_groups[(lottery, strategy)]
        source_windows = {window["window"]: window for window in source_group["windows"]}
        recomputed_by_label: dict[str, dict[str, Any]] = {}
        for window_value in PRIMARY_WINDOWS:
            key = f"{lottery}|{strategy}|{window_value}"
            identity_window = identity_windows[window_value]
            observed_window = observed_windows[window_value]
            source_window = source_windows[window_value]
            label = WINDOW_LABELS[window_value]
            support = int(identity_window["support_draws"])
            observed_successes = int(observed_window["observed_successes"])
            trace = source_window["per_draw_distinct_ticket_trace"]
            counts = [int(item["distinct_ticket_count"]) for item in trace]
            if len(counts) != support or (counts and len(set(counts)) != 1):
                raise ContractSemanticError(f"P273A null vector is not the committed constant form: {key}")
            universe = constants[lottery]["universe"]
            winning = constants[lottery]["any_prize_numerator"]
            probability = (
                exact_distinct_ticket_probability(universe, winning, counts[0])
                if counts
                else winning / universe
            )
            expected_successes = support * probability
            evaluable = support >= MIN_SUPPORT_DRAWS and expected_successes >= MIN_EXPECTED_SUCCESSES
            _record_check(mismatches, checks, key, "window_label", source_window["window_label"], label)
            _record_check(mismatches, checks, key, "support_identity_vs_observed", observed_window["support_draws"], support)
            _record_check(mismatches, checks, key, "support_identity_vs_inference", source_window["support_draws"], support)
            _record_check(mismatches, checks, key, "observed_successes", source_window["observed_successes"], observed_successes)
            trace_distribution = {
                str(ticket_count): count
                for ticket_count, count in sorted(Counter(counts).items())
            }
            _record_check(
                mismatches,
                checks,
                key,
                "identity_distinct_ticket_count_distribution",
                identity_window["distinct_ticket_count_distribution"],
                trace_distribution,
            )
            _record_check(
                mismatches,
                checks,
                key,
                "inference_distinct_ticket_count_distribution",
                source_window["distinct_ticket_count_distribution"],
                trace_distribution,
            )
            _record_check(mismatches, checks, key, "ticket_universe_total", source_window["ticket_universe_total"], universe)
            _record_check(mismatches, checks, key, "ticket_universe_winning", source_window["ticket_universe_winning"], winning)
            _record_check(mismatches, checks, key, "expected_successes", source_window["expected_successes"], _round(expected_successes))
            _record_check(
                mismatches,
                checks,
                key,
                "mean_baseline_rate",
                source_window.get("mean_baseline_rate"),
                _round(probability) if evaluable else None,
            )
            recomputed: dict[str, Any] = {
                "evaluable": evaluable,
                "support_draws": support,
                "observed_successes": observed_successes,
                "expected_successes": expected_successes,
            }
            if evaluable:
                observed_rate = observed_successes / support
                excess = observed_rate - probability
                upper = binomial_upper_pvalue(observed_successes, support, probability)
                lower = binomial_lower_pvalue(observed_successes, support, probability)
                upper_adjusted = min(1.0, upper * 108)
                lower_adjusted = min(1.0, lower * 108)
                wilson = wilson_interval(observed_successes, support)
                clopper = clopper_pearson_interval(observed_successes, support)
                significant_positive = excess > 0 and upper_adjusted <= FAMILY_ALPHA
                significant_negative = excess < 0 and lower_adjusted <= FAMILY_ALPHA
                recomputed.update(
                    {
                        "absolute_excess": excess,
                        "raw_p_value_one_sided_upper": upper,
                        "raw_p_value_one_sided_lower": lower,
                        "bonferroni_p_value": upper_adjusted,
                        "bonferroni_p_value_lower": lower_adjusted,
                        "significant_positive": significant_positive,
                        "significant_negative": significant_negative,
                    }
                )
                for field, value in (
                    ("observed_rate", _round(observed_rate)),
                    ("raw_p_value_one_sided_upper", _round(upper)),
                    ("raw_p_value_one_sided_lower", _round(lower)),
                    ("bonferroni_p_value", _round(upper_adjusted)),
                    ("bonferroni_p_value_lower", _round(lower_adjusted)),
                    ("wilson_ci_95", [_round(wilson[0]), _round(wilson[1])]),
                    ("clopper_pearson_ci_95", [_round(clopper[0]), _round(clopper[1])]),
                    ("statistical_status", _statistical_status(excess, upper_adjusted, lower_adjusted)),
                ):
                    _record_check(mismatches, checks, key, field, source_window[field], value)
            else:
                recomputed.update(
                    {
                        "absolute_excess": None,
                        "significant_positive": False,
                        "significant_negative": False,
                    }
                )
                _record_check(mismatches, checks, key, "support_status", source_window["support_status"], "INSUFFICIENT_SUPPORT")
            recomputed_by_label[label] = recomputed
            verification_rows.append(
                {
                    "lottery_type": lottery,
                    "strategy_id": strategy,
                    "window": window_value,
                    "window_label": label,
                    "support_draws": support,
                    "observed_successes": observed_successes,
                    "expected_successes_recomputed": _round(expected_successes),
                    "baseline_rate_recomputed": _round(probability) if support else None,
                    "evaluable": evaluable,
                }
            )
        stability = _recomputed_stability(recomputed_by_label)
        group_key = f"{lottery}|{strategy}"
        _record_check(mismatches, checks, group_key, "stability.status", source_group["stability"]["status"], stability["status"])
        _record_check(mismatches, checks, group_key, "stability.criteria", source_group["stability"]["criteria"], stability["criteria"])
        _record_check(mismatches, checks, group_key, "stability.fail_reasons", source_group["stability"]["fail_reasons"], stability["fail_reasons"])
        decisions: dict[str, str] = {}
        for label, recomputed in recomputed_by_label.items():
            decision = _window_decision(label, recomputed, stability)
            decisions[label] = decision
            source_window = next(window for window in source_group["windows"] if window["window_label"] == label)
            _record_check(mismatches, checks, group_key, f"{label}.window_decision", source_window["window_decision"], decision)
        if any(not item["evaluable"] for item in recomputed_by_label.values()):
            group_decision = "INSUFFICIENT_SUPPORT"
        elif stability["status"] == "STABILITY_PASS" and any(
            decisions[label] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING" for label in ("MID", "LONG")
        ):
            group_decision = "GO_CANDIDATE_RESEARCH_ONLY"
        elif any(item["absolute_excess"] > 0 for item in recomputed_by_label.values()):
            group_decision = "DESCRIPTIVE_ONLY"
        else:
            group_decision = "NULL"
        _record_check(mismatches, checks, group_key, "overall_group_decision", source_group["overall_group_decision"], group_decision)

    verification_rows.sort(key=lambda row: (row["lottery_type"], row["strategy_id"], row["window"]))
    if mismatches:
        raise ContractSemanticError(f"P273A committed semantic drift: {len(mismatches)} mismatches")
    return {
        "consistency_with_committed": True,
        "strategy_lottery_cells": 36,
        "verified_window_count": len(verification_rows),
        "family_size": inference["inference"]["family_size"],
        "checks_performed": checks[0],
        "mismatched_fields": mismatches,
        "verification_rows": verification_rows,
        "committed_classification": inference["final_classification"],
        "committed_prediction_success_claim": inference["prediction_success_claim"],
        "committed_summary_counts": {
            "window_decision_counts": inference["summary"]["window_decision_counts"],
            "group_decision_counts": inference["summary"]["group_decision_counts"],
            "stability_counts": inference["summary"]["stability_counts"],
        },
        "classification_context": (
            "verification of a committed retrospective research classification only; "
            "not a P544C future-performance or betting claim"
        ),
        "prior_independent_audit": {
            "applicable_checks": 143_806,
            "mismatches": 0,
            "status": "preserved_prior_read_only_audit_result",
        },
    }


def verify_p281a_constants(
    p273a: Mapping[str, Any], p281a: Mapping[str, Any]
) -> dict[str, Any]:
    constants = derive_analytic_constants()
    p273_constants = p273a["analytic_random_baselines"]
    p281_config = p281a["random_baseline_config"]
    mismatches: list[dict[str, Any]] = []
    checks = [0]
    for lottery in sorted(constants):
        derived = constants[lottery]
        key = lottery
        _record_check(mismatches, checks, key, "p273_universe", p273_constants[lottery]["total_ticket_identities"], derived["universe"])
        _record_check(mismatches, checks, key, "p273_winning", p273_constants[lottery]["winning_ticket_identities"], derived["any_prize_numerator"])
        _record_check(mismatches, checks, key, "p273_rate", p273_constants[lottery]["ticket_baseline"], derived["rate"])
        _record_check(mismatches, checks, key, "p281_universe", p281_config["ticket_universes"][lottery]["total"], derived["universe"])
        _record_check(mismatches, checks, key, "p281_winning", p281_config["ticket_universes"][lottery]["winning"], derived["any_prize_numerator"])
        _record_check(mismatches, checks, key, "p281_rate", p281_config["analytic_baselines"][lottery]["ticket_baseline"], derived["rate"])
    if mismatches:
        raise ContractSemanticError(f"P281A analytic constant drift: {len(mismatches)} mismatches")
    return {
        "consistency_with_committed": True,
        "checks_performed": checks[0],
        "mismatched_fields": mismatches,
        "analytic_constants": constants,
        "legacy_window_policy_isolated": {
            "p281a_windows": p281a["meta"]["inferential_windows"],
            "current_primary_windows": list(PRIMARY_WINDOWS),
            "status": "P281A used only for analytic constants and rule cross-check",
        },
    }


def reject_cross_lottery_raw_rate_pooling(lottery_types: Iterable[str]) -> None:
    lotteries = sorted(set(lottery_types))
    if len(lotteries) > 1:
        raise CrossLotteryPoolingError(f"raw-rate pooling across lotteries is forbidden: {lotteries}")


def _window_label(window: Any) -> str:
    return WINDOW_LABELS.get(window, "REFERENCE_ONLY_OR_UNKNOWN")


def _portability_for_role(manifest: Sequence[Mapping[str, Any]], role: str) -> str:
    return next(item["portability_status"] for item in manifest if item["role"] == role)


def _stability_map(p543a: Mapping[str, Any]) -> dict[tuple[Any, ...], str]:
    result: dict[tuple[Any, ...], str] = {}
    for bucket in ("multi_window_stable", "single_window_spike", "prize_or_zone2_signal", "unknown_or_incomplete"):
        for group in p543a["candidate_packet"].get(bucket, []):
            key = (group.get("lottery"), group.get("section"), group.get("candidate_id"), group.get("bucket"))
            previous = result.get(key)
            if previous is not None and previous != bucket:
                result[key] = "multiple_source_buckets"
            else:
                result[key] = bucket
    return result


def normalize_summaries(
    p542a: Mapping[str, Any],
    p536c: Mapping[str, Any],
    p543a: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    specs = {spec["role"]: spec for spec in SOURCE_SPECS}
    p542_rows = p542a["strategy_pick_matrix"]
    p536_rows = p536c["strategy_pick_matrix_lift_extension"]
    projections = p536c["cross_lottery_normalized_lift"]
    p543_rows = p543a["top_historical_candidates"]
    if (len(p542_rows), len(p536_rows), len(projections), len(p543_rows)) != (603, 603, 195, 621):
        raise ContractSemanticError("summary artifact record counts changed")

    p542_normalized: list[dict[str, Any]] = []
    for index, row in enumerate(p542_rows):
        p542_normalized.append(
            {
                "source_artifact": specs["p542a_scoreboard"]["path"],
                "source_hash": specs["p542a_scoreboard"]["sha256"],
                "source_index": index,
                "source_record_type": "strategy_pick_matrix",
                "source_metric": "lottery_specific_prize_aware_endpoint",
                "lottery_type": row["lottery_type"],
                "strategy_or_candidate_id": row["strategy_id"],
                "candidate_kind": "strategy_pick",
                "pick_count": row["pick_k"],
                "window": row["window"],
                "window_label": _window_label(row["window"]),
                "denominators": {
                    "support_draws": row["support_draws"],
                    "observed_successes": row["prize_signal_count"],
                },
                "observed_rate": row["prize_signal_rate"],
                "baseline_rate": row["baseline_prize_signal_rate"],
                "excess_percentage_points": row["prize_signal_edge_pp"],
                "relative_lift": None,
                "log10_lift": None,
                "stability_bucket": "not_provided_by_source_row",
                "portability_status": _portability_for_role(manifest, "p542a_scoreboard"),
                "source_limitations": [
                    "summary row only; no per-draw values reconstructed",
                    "lift is unavailable in P542A and remains null",
                    "nested latest-draw windows are not independent folds",
                ],
            }
        )
    p542_normalized.sort(
        key=lambda row: (row["lottery_type"], row["strategy_or_candidate_id"], row["pick_count"], row["window"], row["source_index"])
    )

    p536_normalized: list[dict[str, Any]] = []
    for index, row in enumerate(p536_rows):
        p536_normalized.append(
            {
                "source_artifact": specs["p536c_lift_extension"]["path"],
                "source_hash": specs["p536c_lift_extension"]["sha256"],
                "source_index": index,
                "source_record_type": "strategy_pick_matrix_lift_extension",
                "source_metric": "lottery_specific_prize_aware_endpoint",
                "lottery_type": row["lottery_type"],
                "strategy_or_candidate_id": row["strategy_id"],
                "candidate_kind": "strategy_pick",
                "pick_count": row["pick_k"],
                "window": row["window"],
                "window_label": _window_label(row["window"]),
                "denominators": {
                    "support_draws": row["support_draws"],
                    "observed_successes": row["prize_signal_count"],
                },
                "observed_rate": row["prize_signal_rate"],
                "baseline_rate": row["baseline_prize_signal_rate"],
                "excess_percentage_points": row["prize_signal_edge_pp"],
                "relative_lift": row["prize_signal_lift"],
                "log10_lift": row["prize_signal_log10_lift"],
                "stability_bucket": "not_provided_by_source_row",
                "portability_status": _portability_for_role(manifest, "p536c_lift_extension"),
                "source_limitations": [
                    "same underlying replay observations as P542A; not independent evidence",
                    "summary row only; no per-draw values reconstructed",
                    "nested latest-draw windows are not independent folds",
                ],
            }
        )
    p536_normalized.sort(
        key=lambda row: (row["lottery_type"], row["strategy_or_candidate_id"], row["pick_count"], row["window"], row["source_index"])
    )

    stability = _stability_map(p543a)
    p543_normalized: list[dict[str, Any]] = []
    for index, row in enumerate(p543_rows):
        evidence = _mapping(row.get("evidence"), f"p543a.top_historical_candidates[{index}].evidence")
        section = row.get("section")
        if "prize_signal_rate" in evidence:
            observed_rate = evidence.get("prize_signal_rate")
            baseline_rate = evidence.get("baseline_prize_signal_rate")
            excess = evidence.get("prize_signal_edge_pp")
            metric = "lottery_specific_prize_aware_endpoint"
        elif "prize_aware_hit_rate" in evidence:
            observed_rate = evidence.get("prize_aware_hit_rate")
            baseline_rate = evidence.get("random_prize_aware_hit_rate")
            excess = evidence.get("prize_aware_edge_pp")
            metric = "power_lotto_prize_aware_endpoint"
        else:
            observed_rate = None
            baseline_rate = None
            excess = None
            metric = "source_metric_unavailable"
        key = (row.get("lottery"), section, row.get("candidate_id"), row.get("bucket"))
        pick_count = row.get("bucket") if section == "strategy_pick" else None
        p543_normalized.append(
            {
                "source_artifact": specs["p543a_stability_packet"]["path"],
                "source_hash": specs["p543a_stability_packet"]["sha256"],
                "source_index": index,
                "source_record_type": "top_historical_candidate",
                "source_metric": metric,
                "lottery_type": row.get("lottery"),
                "strategy_or_candidate_id": row.get("candidate_id"),
                "candidate_kind": section,
                "pick_count": pick_count,
                "requested_pick_budget": row.get("bucket") if section == "combination" else None,
                "window": row.get("window"),
                "window_label": _window_label(row.get("window")),
                "denominators": {"support_draws": evidence.get("support_draws")},
                "observed_rate": observed_rate,
                "baseline_rate": baseline_rate,
                "excess_percentage_points": excess,
                "relative_lift": None,
                "log10_lift": None,
                "stability_bucket": stability.get(key, "not_classified_or_lossy_source_identity"),
                "portability_status": _portability_for_role(manifest, "p543a_stability_packet"),
                "source_limitations": [
                    "historical-max selection; selection bias remains",
                    "derived from P542A and not independent evidence",
                    "counts, confidence intervals, and per-draw values are unavailable and not inferred",
                ],
            }
        )
    p543_normalized.sort(
        key=lambda row: (
            str(row["lottery_type"]),
            str(row["candidate_kind"]),
            str(row["strategy_or_candidate_id"]),
            -1 if row["pick_count"] is None else row["pick_count"],
            -1 if row["window"] is None else row["window"],
            row["source_index"],
        )
    )

    normalized_projections: list[dict[str, Any]] = []
    for index, row in enumerate(projections):
        lotteries = sorted(row["lotteries"])
        normalized_projections.append(
            {
                "source_artifact": specs["p536c_lift_extension"]["path"],
                "source_hash": specs["p536c_lift_extension"]["sha256"],
                "source_index": index,
                "source_record_type": "cross_lottery_normalized_lift_projection",
                "lottery_type": "MULTI_LOTTERY_PROJECTION",
                "lottery_types_present": lotteries,
                "strategy_or_candidate_id": f"feature_family:{row['feature_family']}",
                "candidate_kind": "feature_family_projection",
                "pick_count": row["pick_k"],
                "window": row["window"],
                "window_label": _window_label(row["window"]),
                "denominators": {
                    "strategy_count_by_lottery": {
                        lottery: row["lotteries"][lottery]["strategy_count"] for lottery in lotteries
                    }
                },
                "observed_rate": None,
                "baseline_rate": None,
                "excess_percentage_points": None,
                "relative_lift": None,
                "per_lottery_normalized_lifts": {
                    lottery: {
                        "average_any_main_hit_lift": row["lotteries"][lottery].get("avg_any_main_hit_lift"),
                        "average_m3_plus_lift": row["lotteries"][lottery].get("avg_m3_plus_lift"),
                        "average_prize_signal_lift": row["lotteries"][lottery].get("avg_prize_signal_lift"),
                    }
                    for lottery in lotteries
                },
                "stability_bucket": "aggregate_projection_not_stability_evidence",
                "portability_status": _portability_for_role(manifest, "p536c_lift_extension"),
                "source_limitations": [
                    "per-lottery normalized lifts retained separately; raw rates are not pooled",
                    "many projections do not contain all three lotteries",
                    "no candidate identity, observed rate, baseline rate, or support-draw total exists at aggregate level",
                ],
            }
        )
    normalized_projections.sort(
        key=lambda row: (row["strategy_or_candidate_id"], row["pick_count"], row["window"], row["source_index"])
    )
    return {
        "raw_cross_lottery_rate_pooling_performed": False,
        "overlap_warning": "P536C and P542A reuse the same observations; P543A derives from P542A. Rows are projections, not independent evidence.",
        "p542a_strategy_rows": p542_normalized,
        "p536c_lift_rows": p536_normalized,
        "p536c_cross_lottery_projections": normalized_projections,
        "p543a_historical_evidence_rows": p543_normalized,
        "counts": {
            "p542a_strategy_rows": len(p542_normalized),
            "p536c_lift_rows": len(p536_normalized),
            "p536c_cross_lottery_projections": len(normalized_projections),
            "p543a_historical_evidence_rows": len(p543_normalized),
        },
    }


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    stripped = {key: value for key, value in payload.items() if key != "canonical_payload_digest"}
    return _sha256(_canonical_json_bytes(stripped))


def serialize_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def build_evaluation(repo_root: Path) -> dict[str, Any]:
    documents, manifest, generated_at = load_pinned_inputs(repo_root)
    audit = audit_p543c(documents["p543c_per_draw_contract"])
    for source_item in manifest:
        if source_item["role"] == "p543c_per_draw_contract":
            source_item["source_semantic_status"] = (
                "semantic_drift_explained_recomputed_from_primary_fields"
            )
    track1 = build_track1(audit, DEFAULT_PERMUTATIONS)
    p273 = verify_p273a(
        documents["p273a_distinct_ticket_identity"],
        documents["p273a_primary_window_observed_counts"],
        documents["p273a_prize_aware_inference"],
    )
    p281 = verify_p281a_constants(
        documents["p273a_prize_aware_inference"],
        documents["p281a_cross_lottery_verification"],
    )
    normalized = normalize_summaries(
        documents["p542a_scoreboard"],
        documents["p536c_lift_extension"],
        documents["p543a_stability_packet"],
        manifest,
    )
    main_baseline = {
        f"M{k}": {
            "numerator": BIG_LOTTO_MAIN_HIT_NUMERATORS[k],
            "denominator": BIG_LOTTO_UNIVERSE,
            "rate": _round(BIG_LOTTO_MAIN_HIT_NUMERATORS[k] / BIG_LOTTO_UNIVERSE),
            "rate_12dp": _rate_string(BIG_LOTTO_MAIN_HIT_NUMERATORS[k], BIG_LOTTO_UNIVERSE),
        }
        for k in range(7)
    }
    main_baseline["M3plus"] = {
        "numerator": BIG_LOTTO_M3_PLUS_NUMERATOR,
        "denominator": BIG_LOTTO_UNIVERSE,
        "rate": _round(BIG_LOTTO_M3_PLUS_NUMERATOR / BIG_LOTTO_UNIVERSE),
        "rate_12dp": _rate_string(BIG_LOTTO_M3_PLUS_NUMERATOR, BIG_LOTTO_UNIVERSE),
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "metadata": {
            "task_id": TASK_ID,
            "pinned_source_commit": PINNED_SOURCE_COMMIT,
            "generated_at_utc": generated_at,
            "timestamp_policy": "pinned source commit committer timestamp normalized to UTC seconds",
            "frozen_spec_digest": FROZEN_SPEC_DIGEST,
            "deterministic_inputs": ["pinned commit", "eight committed JSON blobs", "frozen spec", "seed registry"],
        },
        "frozen_spec": FROZEN_SPEC,
        "seed_registry": SEED_REGISTRY,
        "window_policy": {
            "primary_windows": list(PRIMARY_WINDOWS),
            "labels": {str(key): value for key, value in WINDOW_LABELS.items()},
            "confirmatory_window": 750,
            "mid_role": "direction_and_stability_support",
            "short_role": "diagnostic_only",
            "reference_only": [1500, "all_history"],
            "draw_is_independent_inferential_unit": True,
        },
        "classification_vocabulary": list(CLASSIFICATION_VOCABULARY),
        "source_artifact_manifest": manifest,
        "special_hit_contract_amendment": audit["special_hit_contract_amendment"],
        "p543c_contract_verification": audit["contract_shape"],
        "analytic_constants": {
            "big_lotto_main_hit_spectrum": main_baseline,
            "cross_lottery_any_prize": p281["analytic_constants"],
        },
        "per_draw_cells": audit["per_draw_cells"],
        "track1_big_lotto_short": track1,
        "aggregate_verification": {"p273a": p273, "p281a": p281},
        "normalized_summaries": normalized,
        "unresolved_data_dependencies": [
            {
                "dependency": "committed official outcomes registry covering P273A identity sets",
                "impact": "full per-draw SHORT/MID/LONG recomputation remains unavailable",
                "created_by_p544c": False,
            },
            {
                "dependency": "DAILY_539 and POWER_LOTTO committed per-draw outcome joins",
                "impact": "cross-lottery per-draw evaluation remains unavailable",
                "created_by_p544c": False,
            },
            {
                "dependency": "committed official prize-amount constants",
                "impact": "currency and return calculations are out of scope",
                "created_by_p544c": False,
            },
        ],
        "safety": {
            "retrospective_research_only": True,
            "historical_replay_is_future_prediction_evidence": False,
            "increased_winning_odds_claim": False,
            "betting_advice": False,
            "production_or_go_live_readiness": False,
            "database_opened": False,
            "database_written": False,
            "api_or_ui_changed": False,
            "strategy_combination_search_performed": False,
            "upstream_artifact_modified": False,
        },
        "limitations": [
            "P543C remains immutable; P544C corrects interpretation, not historical source bytes.",
            "P543C's stored special_hit derived field is inconsistent and is disclosed alongside the recomputed primary-field value.",
            "The P543C rows are complete contract rows and cannot measure registry-level no-prediction coverage.",
            "Historical fit does not imply a future advantage or increased winning probability.",
            "SHORT-50 is diagnostic only and cannot establish research, holdout, deployment, or production status.",
            "Full 750/300/50 per-draw analysis remains blocked by the committed outcomes-registry dependency.",
            "P542A, P536C, and P543A share lineage and are normalized projections, not independent evidence.",
            "P281A's legacy 100/500/1500 labels are isolated and do not override the current 50/300/750 policy.",
        ],
        "final_classification": "P544C_R1_RETROSPECTIVE_EVALUATION_COMPLETE_NO_FUTURE_OR_BETTING_CLAIM",
    }
    payload["canonical_payload_digest"] = canonical_payload_digest(payload)
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    amendment = payload["special_hit_contract_amendment"]
    p273 = payload["aggregate_verification"]["p273a"]
    p281 = payload["aggregate_verification"]["p281a"]
    counts = payload["normalized_summaries"]["counts"]
    lines = [
        "# P544C R1 — Unified Lottery Replay Success Evaluation",
        "",
        "> Retrospective research only. Historical replay is not evidence of future performance or increased winning odds.",
        "> This is not betting advice and does not establish production or go-live readiness.",
        "",
        "## Deterministic Provenance",
        "",
        f"- schema: `{payload['schema_id']}`",
        f"- pinned commit: `{payload['metadata']['pinned_source_commit']}`",
        f"- generated_at_utc: `{payload['metadata']['generated_at_utc']}`",
        f"- frozen spec digest: `{payload['metadata']['frozen_spec_digest']}`",
        f"- canonical payload digest: `{payload['canonical_payload_digest']}`",
        "",
        "| role | committed artifact | SHA-256 | bytes | portability |",
        "|---|---|---|---:|---|",
    ]
    for source in payload["source_artifact_manifest"]:
        lines.append(
            f"| `{source['role']}` | `{source['path']}` | `{source['sha256']}` | {source['bytes']:,} | `{source['portability_status']}` |"
        )
    lines += [
        "",
        "## Owner-Approved BIG_LOTTO Special-Hit Amendment",
        "",
        f"- authoritative fields: `{', '.join(amendment['authoritative_primary_fields'])}`",
        f"- rule: `{amendment['recomputation_rule']}`",
        f"- source special hits: **{amendment['source_special_hit_count']}**",
        f"- recomputed special hits: **{amendment['recomputed_special_hit_count']}**",
        f"- source/recomputed mismatches: **{amendment['mismatch_count']}**",
        f"- M2 + special prize rows: **{amendment['m2_plus_special_prize_case_count']}**",
        f"- resolution: `{amendment['resolution']}`",
        "- P543C source bytes were not modified.",
        "",
        "### Affected Rows",
        "",
        "| candidate | order | draw | date | main hits | source | recomputed |",
        "|---|---:|---|---|---:|---:|---|",
    ]
    for row in amendment["affected_row_ids"]:
        lines.append(
            f"| `{row['candidate_id']}` | {row['draw_order']} | `{row['draw_id']}` | {row['draw_date']} | {row['main_hit_count']} | {row['source_special_hit']} | {str(row['recomputed_special_hit']).lower()} |"
        )
    lines += [
        "",
        "## Track 1 — BIG_LOTTO SHORT-50",
        "",
        "| candidate | M0 | M1 | M2 | M3+ | special hits | M2+special | any prize | rate | classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for candidate in payload["track1_big_lotto_short"]["candidate_evaluations"]:
        lines.append(
            f"| `{candidate['candidate_id']}` | {candidate['exact_main_hit_counts']['M0']} | {candidate['exact_main_hit_counts']['M1']} | {candidate['exact_main_hit_counts']['M2']} | {candidate['cumulative_main_hit_counts']['M3plus']} | {candidate['recomputed_special_hit_count']} | {candidate['m2_and_special_count']} | {candidate['official_any_prize_count']} | {candidate['official_any_prize_rate']:.3f} | `{candidate['classification']}` |"
        )
    lines += [
        "",
        "The pairing permutation is an alignment/timing null using P543D's within-lottery re-pairing semantics. It is not an absolute-skill null.",
        "SHORT-only results cannot exceed a diagnostic classification.",
        "",
        "## Track 2 — Aggregate and Constant Verification",
        "",
        f"- P273A windows verified: **{p273['verified_window_count']}**; mismatches: **{len(p273['mismatched_fields'])}**; family size: **{p273['family_size']}**.",
        f"- P281A analytic checks: **{p281['checks_performed']}**; mismatches: **{len(p281['mismatched_fields'])}**.",
        "- P281A legacy 100/500/1500 labels are isolated from the current window policy.",
        "",
        "## Track 3 — Normalized Summary Projections",
        "",
        f"- P542A strategy rows: **{counts['p542a_strategy_rows']}**",
        f"- P536C lift rows: **{counts['p536c_lift_rows']}**",
        f"- P536C cross-lottery projections: **{counts['p536c_cross_lottery_projections']}**",
        f"- P543A historical evidence rows: **{counts['p543a_historical_evidence_rows']}**",
        "- Raw rates were not pooled across lotteries, and overlapping lineage is not treated as independent evidence.",
        "",
        "## Unresolved Data Dependencies",
        "",
    ]
    lines.extend(
        f"- {item['dependency']}: {item['impact']}." for item in payload["unresolved_data_dependencies"]
    )
    lines += ["", "## Limitations and Safety", ""]
    lines.extend(f"- {item}" for item in payload["limitations"])
    lines += [
        "- No database was opened or written.",
        "- No API, UI, service, deployment, upstream artifact, or strategy-combination search was changed or performed.",
        "",
    ]
    return "\n".join(lines)


def generate(repo_root: Path, output_dir: Path, *, date: str = OUTPUT_DATE) -> tuple[Path, Path]:
    payload = build_evaluation(repo_root)
    json_text = serialize_json(payload)
    markdown_text = render_markdown(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"p544c_unified_lottery_replay_success_evaluator_{date}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")
    return json_path, markdown_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--date", default=OUTPUT_DATE)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = args.output_dir or args.repo_root / "outputs" / "research"
    json_path, markdown_path = generate(
        args.repo_root,
        output_dir,
        date=args.date,
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    print(f"canonical_payload_digest={payload['canonical_payload_digest']}")


if __name__ == "__main__":
    main()
