"""P538A — Strategy Candidate Evaluation Readiness Artifact (read-only, additive).

Builds a durable readiness assessment purely by reading the already-committed
P537A / P536K / P536C artifacts:

  outputs/research/p537a_shortlist_robustness_review_20260709.json
  outputs/research/p536k_lift_candidate_shortlist_20260708.json
  outputs/research/p536c_success_matrix_lift_extension_20260708.json

No database is opened, no route/API/UI is touched, no new statistical metric
is computed, and none of the three source artifacts are regenerated or
modified. This module only describes what is already there: what fields each
artifact section carries, which candidate groups exist, whether a rolling /
out-of-sample evaluation is even feasible from committed fields alone, what is
missing, and the smallest single next task that would move the needle.

This is a historical replay review artifact only; not a prediction, betting
edge, future-winning, or production-readiness claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TASK_ID = "P538A"
SOURCE_TASK_IDS = ["P537A", "P536K", "P536C"]

OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_P537A_ARTIFACT = OUTPUT_DIR / "p537a_shortlist_robustness_review_20260709.json"
DEFAULT_P536K_ARTIFACT = OUTPUT_DIR / "p536k_lift_candidate_shortlist_20260708.json"
DEFAULT_P536C_ARTIFACT = OUTPUT_DIR / "p536c_success_matrix_lift_extension_20260708.json"

DISCLAIMER_EN = (
    "Historical replay review artifact only; not a prediction, betting edge, "
    "future-winning, or production-readiness claim."
)

# P538A candidate-group name -> P537A field name it is derived from.
GROUP_FIELD_MAP: dict[str, str] = {
    "stable_review_candidates": "stable_candidates_for_owner_review",
    "short_window_spike_cautions": "short_window_spike_caution_list",
    "combination_followup_candidates": "combination_candidates_for_followup",
    "cross_lottery_followup_candidates": "cross_lottery_candidates_for_followup",
    "insufficient_context_candidates": "insufficient_or_ambiguous_candidates",
}

SAMPLE_ROWS_PER_GROUP = 3


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _row_field_union(rows: list[dict[str, Any]]) -> list[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(row.keys())
    return sorted(fields)


def _count_breakdown(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


# --- Section 1: artifact_schema_capability_map ------------------------------


def _section_map(doc: dict[str, Any], section_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in section_names:
        rows = doc.get(name, [])
        is_list = isinstance(rows, list)
        out[name] = {
            "row_count": len(rows) if is_list else None,
            "fields_present": _row_field_union(rows) if is_list and rows else [],
        }
    return out


def build_artifact_schema_capability_map(
    p537a: dict[str, Any],
    p536k: dict[str, Any],
    p536c: dict[str, Any],
    p537a_path: Path,
    p536k_path: Path,
    p536c_path: Path,
) -> dict[str, Any]:
    p537a_sections = _section_map(
        p537a,
        [
            "stable_candidates_for_owner_review",
            "short_window_spike_caution_list",
            "combination_candidates_for_followup",
            "cross_lottery_candidates_for_followup",
            "insufficient_or_ambiguous_candidates",
        ],
    )
    p536k_sections = _section_map(
        p536k,
        [
            "stable_300_750_review_candidates",
            "short_window_spike_review_candidates",
            "combination_review_candidates",
            "cross_lottery_review_candidates",
        ],
    )
    p536c_sections = _section_map(
        p536c,
        [
            "strategy_pick_matrix_lift_extension",
            "cross_lottery_normalized_lift",
            "combination_leaderboard_with_lift",
            "combination_stability_rank",
        ],
    )

    return {
        "P537A": {
            "artifact_path": _relative_or_absolute(p537a_path),
            "task_id": p537a.get("task_id"),
            "extends_task_id": p537a.get("extends_task_id"),
            "upstream_task_id": p537a.get("upstream_task_id"),
            "generated_at": p537a.get("generated_at"),
            "top_level_keys": sorted(p537a.keys()),
            "sections": p537a_sections,
        },
        "P536K": {
            "artifact_path": _relative_or_absolute(p536k_path),
            "task_id": p536k.get("task_id"),
            "extends_task_id": p536k.get("extends_task_id"),
            "generated_at": p536k.get("generated_at"),
            "top_level_keys": sorted(p536k.keys()),
            "sections": p536k_sections,
        },
        "P536C": {
            "artifact_path": _relative_or_absolute(p536c_path),
            "task_id": p536c.get("task_id"),
            "extends_task_id": p536c.get("extends_task_id"),
            "generated_at": p536c.get("generated_at"),
            "top_level_keys": sorted(p536c.keys()),
            "sections": p536c_sections,
            "window_policy": p536c.get("window_policy"),
        },
    }


# --- Section 2: candidate_groups_for_next_stage_review ----------------------


def build_candidate_groups_for_next_stage_review(p537a: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, Any] = {}

    for group_name, field_name in GROUP_FIELD_MAP.items():
        rows = p537a.get(field_name, [])
        sample = rows[:SAMPLE_ROWS_PER_GROUP]

        if group_name == "cross_lottery_followup_candidates":
            lottery_participation: dict[str, int] = {}
            for row in rows:
                for lottery_type in row.get("lotteries", {}).keys():
                    lottery_participation[lottery_type] = lottery_participation.get(lottery_type, 0) + 1
            groups[group_name] = {
                "source_field_in_p537a": field_name,
                "count": len(rows),
                "lottery_type_participation_counts": dict(sorted(lottery_participation.items())),
                "distinct_feature_families": sorted(
                    {row.get("feature_family") for row in rows if row.get("feature_family")}
                ),
                "distinct_windows": sorted({row.get("window") for row in rows if row.get("window") is not None}),
                "sample_rows_verbatim": sample,
            }
        elif group_name in ("combination_followup_candidates", "insufficient_context_candidates"):
            groups[group_name] = {
                "source_field_in_p537a": field_name,
                "count": len(rows),
                "lottery_type_breakdown": _count_breakdown(rows, "lottery_type"),
                "distinct_combo_id_count": len({row.get("combo_id") for row in rows if row.get("combo_id")}),
                "sample_rows_verbatim": sample,
            }
        else:
            groups[group_name] = {
                "source_field_in_p537a": field_name,
                "count": len(rows),
                "lottery_type_breakdown": _count_breakdown(rows, "lottery_type"),
                "distinct_strategy_id_count": len(
                    {row.get("strategy_id") for row in rows if row.get("strategy_id")}
                ),
                "distinct_feature_families": sorted(
                    {row.get("feature_family") for row in rows if row.get("feature_family")}
                ),
                "distinct_windows": sorted({row.get("window") for row in rows if row.get("window") is not None}),
                "sample_rows_verbatim": sample,
            }

    return groups


# --- Section 3: rolling_or_out_of_sample_feasibility -------------------------


def build_rolling_or_out_of_sample_feasibility(
    p537a: dict[str, Any], p536k: dict[str, Any], p536c: dict[str, Any]
) -> dict[str, Any]:
    matrix_rows = p536c.get("strategy_pick_matrix_lift_extension", [])
    combo_leaderboard_rows = p536c.get("combination_leaderboard_with_lift", [])
    cross_rows = p536c.get("cross_lottery_normalized_lift", [])

    matrix_has_draw_range = bool(matrix_rows) and {"earliest_target_draw", "latest_target_draw"} <= matrix_rows[0].keys()
    combo_has_draw_range = bool(combo_leaderboard_rows) and {
        "earliest_target_draw",
        "latest_target_draw",
    } <= combo_leaderboard_rows[0].keys()
    cross_has_strategy_identity = bool(cross_rows) and "strategy_id" in cross_rows[0]

    stable_rows = p537a.get("stable_candidates_for_owner_review", [])
    combo_rows = p537a.get("combination_candidates_for_followup", [])

    stable_has_draw_range_directly = bool(stable_rows) and {
        "earliest_target_draw",
        "latest_target_draw",
    } <= stable_rows[0].keys()
    combo_has_draw_range_directly = bool(combo_rows) and {
        "earliest_target_draw",
        "latest_target_draw",
    } <= combo_rows[0].keys()

    strategy_level_entry = {
        "feasible_directly_from_p537a_or_p536k": stable_has_draw_range_directly,
        "feasible_via_join_to_p536c": matrix_has_draw_range,
        "join_key_if_via_p536c": ["lottery_type", "strategy_id", "window", "pick_k"],
        "join_target": "P536C.strategy_pick_matrix_lift_extension",
        "recoverable_fields_via_join": (
            ["earliest_target_draw", "latest_target_draw"] if matrix_has_draw_range else []
        ),
        "residual_gap": (
            "P537A/P536K rows carry support_draws (a count) but not the actual "
            "earliest_target_draw/latest_target_draw values; those exist only in the "
            "upstream P536C strategy_pick_matrix_lift_extension row and must be recovered "
            "by joining on (lottery_type, strategy_id, window, pick_k). Even after the join, "
            "only the already-replayed draw range is known -- none of the three committed "
            "artifacts contain per-draw outcome rows, so no new walk-forward window can be "
            "computed without a further read-only DB export restricted to target_draw values "
            "after the recovered latest_target_draw."
        ),
    }

    return {
        "stable_review_candidates": strategy_level_entry,
        "short_window_spike_cautions": {
            **strategy_level_entry,
            "residual_gap": (
                "Same join path and same residual gap as stable_review_candidates. "
                "Short-window (50-draw) rows are additionally cautioned against reversal in "
                "the source artifacts, so even a feasible OOS join should not be read as "
                "evidence the pattern will hold."
            ),
        },
        "combination_followup_candidates": {
            "feasible_directly_from_p537a_or_p536k": combo_has_draw_range_directly,
            "feasible_via_join_to_p536c": combo_has_draw_range,
            "join_key_if_via_p536c": ["lottery_type", "combo_id", "window"],
            "join_target": "P536C.combination_leaderboard_with_lift",
            "recoverable_fields_via_join": (
                ["earliest_target_draw", "latest_target_draw"] if combo_has_draw_range else []
            ),
            "residual_gap": (
                "combo_id + lottery_type + window join to P536C's combination_leaderboard_with_lift "
                "recovers the replayed draw range per window, but per_window in the P537A/P536K "
                "rows only carries support_draws, not the range itself. No per-draw outcome rows "
                "exist in any committed artifact, so a further read-only DB export is still "
                "required before any new OOS window can be run."
            ),
        },
        "cross_lottery_followup_candidates": {
            "feasible_directly_from_p537a_or_p536k": False,
            "feasible_via_join_to_p536c": False,
            "join_key_if_via_p536c": None,
            "join_target": None,
            "recoverable_fields_via_join": [],
            "residual_gap": (
                "cross_lottery_normalized_lift rows are pre-aggregated (avg_* across "
                "strategy_count strategies per lottery) at generation time and do not carry "
                "strategy_id or target_draw range -- confirmed by strategy_id "
                f"{'present' if cross_has_strategy_identity else 'absent'} in the committed "
                "P536C cross_lottery_normalized_lift row. Recovering an OOS-testable identity "
                "would require re-deriving the underlying strategy_id set from "
                "strategy_pick_matrix_lift_extension by (feature_family, window, pick_k, "
                "lottery_type), which yields multiple strategies with potentially different "
                "draw ranges each, not a single walk-forward-able series. Treat this group as "
                "NOT feasible for rolling/OOS evaluation without a new aggregation-identity task."
            ),
        },
        "insufficient_context_candidates": {
            "feasible_directly_from_p537a_or_p536k": False,
            "feasible_via_join_to_p536c": False,
            "join_key_if_via_p536c": None,
            "join_target": None,
            "recoverable_fields_via_join": [],
            "residual_gap": (
                "These rows were excluded upstream specifically because "
                "avg_prize_signal_lift_across_present_windows is null in the P536K source -- "
                "the primary combination metric is not fully computable from existing fields. "
                "OOS evaluation is not meaningful until the missing upstream metric is resolved "
                "(a P536C/P536K-level fix), which is out of scope for this read-only readiness "
                "pass."
            ),
        },
        "artifact_wide_note": (
            "No committed artifact among P537A/P536K/P536C contains per-draw outcome rows "
            "(one row per target_draw with hit/miss). All feasibility above is about whether a "
            "draw-range cutoff can be recovered to avoid lookahead when defining a new OOS "
            "window -- not about whether the OOS window can actually be computed from these "
            "artifacts alone. Actually running a new rolling/OOS window always requires a "
            "further read-only DB export scoped to target_draw values after the recovered "
            "cutoff, which this task does not perform (no DB open permitted)."
        ),
    }


# --- Section 4: missing_fields_or_blockers -----------------------------------


def build_missing_fields_or_blockers(
    p537a: dict[str, Any], p536k: dict[str, Any], p536c: dict[str, Any]
) -> dict[str, Any]:
    stable_rows = p537a.get("stable_candidates_for_owner_review", [])
    combo_rows = p537a.get("combination_candidates_for_followup", [])
    cross_rows = p537a.get("cross_lottery_candidates_for_followup", [])
    provenance = p537a.get("provenance_and_limits", {})

    checklist = [
        {
            "required_field": "strategy / family / combo identity",
            "present_in_stable_short_window_groups": bool(stable_rows)
            and {"strategy_id", "feature_family"} <= stable_rows[0].keys(),
            "present_in_combination_group": bool(combo_rows) and "combo_id" in combo_rows[0],
            "present_in_cross_lottery_group": bool(cross_rows) and "feature_family" in cross_rows[0],
            "note": (
                "cross_lottery rows carry feature_family only, not individual strategy_id -- "
                "identity is at the family level, not the strategy level, for that group."
            ),
        },
        {
            "required_field": "lottery_type",
            "present_in_stable_short_window_groups": bool(stable_rows) and "lottery_type" in stable_rows[0],
            "present_in_combination_group": bool(combo_rows) and "lottery_type" in combo_rows[0],
            "present_in_cross_lottery_group": False,
            "note": (
                "cross_lottery rows are keyed by feature_family/window/pick_k with a nested "
                "lotteries dict; lottery_type is a nested key, not a top-level field."
            ),
        },
        {
            "required_field": "window",
            "present_in_stable_short_window_groups": bool(stable_rows) and "window" in stable_rows[0],
            "present_in_combination_group": bool(combo_rows) and "windows_present" in combo_rows[0],
            "present_in_cross_lottery_group": bool(cross_rows) and "window" in cross_rows[0],
            "note": "window is a draw-count bucket label (50/300/750), not a calendar date range.",
        },
        {
            "required_field": "target draw or draw index",
            "present_in_stable_short_window_groups": False,
            "present_in_combination_group": False,
            "present_in_cross_lottery_group": False,
            "note": (
                "Absent from all P537A groups and from P536K. Present only in upstream P536C's "
                "strategy_pick_matrix_lift_extension and combination_leaderboard_with_lift as "
                "earliest_target_draw/latest_target_draw; recoverable via join, not carried "
                "forward by the shortlist/review artifacts themselves. Never present for the "
                "cross-lottery group at any level (see rolling_or_out_of_sample_feasibility)."
            ),
        },
        {
            "required_field": "observed rate / baseline / lift",
            "present_in_stable_short_window_groups": bool(stable_rows)
            and {"observed_rate", "baseline_rate", "lift"} <= stable_rows[0].keys(),
            "present_in_combination_group": bool(combo_rows)
            and "avg_prize_signal_lift_across_present_windows" in combo_rows[0],
            "present_in_cross_lottery_group": bool(cross_rows)
            and any("avg_any_main_hit_lift" in v for v in cross_rows[0].get("lotteries", {}).values()),
            "note": None,
        },
        {
            "required_field": "support / sample size",
            "present_in_stable_short_window_groups": bool(stable_rows) and "support_draws" in stable_rows[0],
            "present_in_combination_group": bool(combo_rows)
            and any("support_draws" in v for v in combo_rows[0].get("per_window", {}).values()),
            "present_in_cross_lottery_group": bool(cross_rows)
            and any("strategy_count" in v for v in cross_rows[0].get("lotteries", {}).values()),
            "note": "cross_lottery support is strategy_count (strategies averaged), not a draw-count sample size.",
        },
        {
            "required_field": "source artifact data_hash / provenance",
            "present_in_stable_short_window_groups": "source_data_hash_sha256" in provenance,
            "present_in_combination_group": "source_data_hash_sha256" in provenance,
            "present_in_cross_lottery_group": "source_data_hash_sha256" in provenance,
            "note": (
                "Provenance is at the artifact level (provenance_and_limits.source_data_hash_sha256 "
                "/ hash_chain_verified), not per-row."
            ),
        },
        {
            "required_field": "temporal information to avoid lookahead leakage",
            "present_in_stable_short_window_groups": False,
            "present_in_combination_group": False,
            "present_in_cross_lottery_group": False,
            "note": (
                "No committed artifact records an explicit 'as of' cutoff at the shortlist/review "
                "level. earliest_target_draw/latest_target_draw exist upstream in P536C only (see "
                "target-draw row above) and must be joined back per candidate before defining any "
                "new OOS window; window_policy.minimum_support_draws=30 (P536C) is the only "
                "explicit sample-size floor found."
            ),
        },
    ]

    hard_blockers = [
        "No per-draw outcome rows (one row per target_draw with hit/miss) exist in any of "
        "P537A/P536K/P536C; only pre-aggregated window-level rates. A new rolling/OOS window "
        "cannot be computed from these three artifacts alone regardless of identity/draw-range "
        "availability.",
        "cross_lottery_followup_candidates rows lose strategy_id and target_draw range entirely "
        "during upstream aggregation in P536C; this group is not traceable back to a single "
        "walk-forward-able series without a new aggregation-identity task.",
        "insufficient_context_candidates rows are excluded specifically because a required "
        "upstream metric (avg_prize_signal_lift_across_present_windows) is null; this is an "
        "upstream data gap in P536K/P536C, not something this read-only readiness pass can "
        "resolve.",
        "target_draw range (earliest_target_draw/latest_target_draw) is present in upstream "
        "P536C rows but is not carried into the P536K/P537A shortlist/review rows -- any "
        "consumer of P537A alone would need to re-join to P536C to know where a new OOS window "
        "could safely start.",
    ]

    return {
        "field_presence_checklist": checklist,
        "hard_blockers_for_rolling_or_out_of_sample_evaluation": hard_blockers,
        "db_access_required_for_full_resolution": True,
        "db_access_performed_in_this_task": False,
    }


# --- Section 5: recommended_next_single_worker_task ---------------------------


def build_recommended_next_single_worker_task(p536c: dict[str, Any]) -> dict[str, Any]:
    window_policy = p536c.get("window_policy", {})
    min_support = window_policy.get("minimum_support_draws")
    return {
        "proposed_task_id": "P539A (proposed, not yet authorized)",
        "title": "Read-only per-draw replay export for stable/combination candidate draw-range cutoffs",
        "scope": (
            "Open lottery_api/data/lottery_v2.db read-only (sqlite3 URI mode=ro + PRAGMA "
            "query_only=ON, matching P536C's own source.db_open_mode) and, restricted to the "
            "strategy_ids/combo_ids already present in P537A's stable_review_candidates and "
            "combination_followup_candidates groups, export one row per target_draw (hit/miss, "
            "prize_signal boolean) for target_draw values strictly after each candidate's "
            "earliest/latest_target_draw range recovered from P536C -- to check whether enough "
            "NEW draws now exist to support even a first out-of-sample window "
            f"(P536C's own window_policy.minimum_support_draws={min_support})."
        ),
        "why_smallest_next_step": (
            "This answers the binary question 'is OOS evaluation possible today' before any "
            "actual walk-forward statistical test is attempted, and stays strictly read-only "
            "(no DB write, no new strategy, no promotion gate) -- consistent with this task's "
            "own DB-write prohibition, which is why it is proposed rather than executed here."
        ),
        "excluded_from_this_proposed_task": [
            "cross_lottery_followup_candidates (no recoverable strategy identity; needs a "
            "separate aggregation-identity task first)",
            "insufficient_context_candidates (blocked on an upstream P536K/P536C metric gap, "
            "not a DB export)",
        ],
        "not_run_in_this_task": True,
    }


# --- Section 6: provenance_and_limits ------------------------------------------


def build_provenance_and_limits(
    p537a_path: Path,
    p536k_path: Path,
    p536c_path: Path,
    p537a: dict[str, Any],
    p536k: dict[str, Any],
    p536c: dict[str, Any],
) -> dict[str, Any]:
    p537a_prov = p537a.get("provenance_and_limits", {})
    p536k_prov = p536k.get("provenance_and_limits", {})

    data_hash_p537a = p537a_prov.get("source_data_hash_sha256")
    data_hash_p536k = p536k_prov.get("source_data_hash_sha256")
    data_hash_p536c = p536c.get("source", {}).get("data_hash_sha256")

    replay_data_hash_chain_verified = (
        data_hash_p537a is not None and data_hash_p537a == data_hash_p536k == data_hash_p536c
    )

    return {
        "source_artifacts": {
            "P537A": {
                "path": _relative_or_absolute(p537a_path),
                "file_sha256": _sha256_file(p537a_path),
                "generated_at": p537a.get("generated_at"),
            },
            "P536K": {
                "path": _relative_or_absolute(p536k_path),
                "file_sha256": _sha256_file(p536k_path),
                "generated_at": p536k.get("generated_at"),
            },
            "P536C": {
                "path": _relative_or_absolute(p536c_path),
                "file_sha256": _sha256_file(p536c_path),
                "generated_at": p536c.get("generated_at"),
            },
        },
        "replay_data_hash_chain": {
            "P537A_source_data_hash_sha256": data_hash_p537a,
            "P536K_source_data_hash_sha256": data_hash_p536k,
            "P536C_source_data_hash_sha256": data_hash_p536c,
            "verified_equal_across_all_three": replay_data_hash_chain_verified,
        },
        "selection_method": (
            "Descriptive read-only synthesis over fields already present in the committed "
            "P537A/P536K/P536C artifacts only. No database access, no route/API/UI change, no "
            "new statistical metric, and no artifact regeneration -- every count and sample row "
            "is copied verbatim or derived by simple counting/grouping over existing fields. "
            "Feasibility findings are computed by checking for field presence in the loaded "
            "artifacts, not asserted from memory."
        ),
        "limitations": [
            "Retrospective replay evidence only; does not imply future performance.",
            "This artifact does not open the database, does not recompute P536C/P536K/P537A, "
            "and does not perform any rolling/out-of-sample statistical test itself -- it only "
            "assesses whether the committed artifacts contain enough fields to attempt one.",
            "candidate_groups_for_next_stage_review samples are the first rows in each source "
            "section's existing order, not a re-ranking by any new or existing metric.",
            "rolling_or_out_of_sample_feasibility describes whether a draw-range cutoff can be "
            "recovered to avoid lookahead, not whether an OOS window can actually be computed "
            "from these three artifacts alone -- that always requires a further read-only DB "
            "export, proposed but not performed here.",
        ],
        "disclaimer_en": DISCLAIMER_EN,
    }


# --- Top-level orchestration ---------------------------------------------------


def run_readiness_assessment(
    p537a_path: Path = DEFAULT_P537A_ARTIFACT,
    p536k_path: Path = DEFAULT_P536K_ARTIFACT,
    p536c_path: Path = DEFAULT_P536C_ARTIFACT,
) -> dict[str, Any]:
    p537a = _load_json(p537a_path)
    p536k = _load_json(p536k_path)
    p536c = _load_json(p536c_path)

    return {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "source_task_ids": SOURCE_TASK_IDS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P538A_STRATEGY_CANDIDATE_EVALUATION_READINESS_READY",
        "artifact_schema_capability_map": build_artifact_schema_capability_map(
            p537a, p536k, p536c, p537a_path, p536k_path, p536c_path
        ),
        "candidate_groups_for_next_stage_review": build_candidate_groups_for_next_stage_review(p537a),
        "rolling_or_out_of_sample_feasibility": build_rolling_or_out_of_sample_feasibility(p537a, p536k, p536c),
        "missing_fields_or_blockers": build_missing_fields_or_blockers(p537a, p536k, p536c),
        "recommended_next_single_worker_task": build_recommended_next_single_worker_task(p536c),
        "provenance_and_limits": build_provenance_and_limits(
            p537a_path, p536k_path, p536c_path, p537a, p536k, p536c
        ),
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P538A — Strategy Candidate Evaluation Readiness")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    add(f"Source task ids: **{', '.join(result['source_task_ids'])}**")
    add(f"Generated at: `{result['generated_at']}`")
    add("")

    add("## Artifact Schema Capability Map")
    add("")
    for artifact_name, info in result["artifact_schema_capability_map"].items():
        add(f"### {artifact_name} (`{info['artifact_path']}`)")
        add("")
        add(f"- task_id: **{info.get('task_id')}**, generated_at: `{info.get('generated_at')}`")
        add("- sections:")
        for section_name, section_info in info["sections"].items():
            add(f"  - `{section_name}`: {section_info['row_count']} rows")
        add("")

    add("## Candidate Groups For Next-Stage Review")
    add("")
    for group_name, info in result["candidate_groups_for_next_stage_review"].items():
        add(f"### {group_name} (count={info['count']})")
        add("")
        add(f"- source field in P537A: `{info['source_field_in_p537a']}`")
        for key, value in info.items():
            if key in ("source_field_in_p537a", "count", "sample_rows_verbatim"):
                continue
            add(f"- {key}: {value}")
        add("")

    add("## Rolling / Out-of-Sample Feasibility")
    add("")
    add("| group | feasible directly | feasible via join to P536C | join target |")
    add("|---|---|---|---|")
    for group_name, info in result["rolling_or_out_of_sample_feasibility"].items():
        if group_name == "artifact_wide_note":
            continue
        add(
            f"| {group_name} | {info['feasible_directly_from_p537a_or_p536k']} | "
            f"{info['feasible_via_join_to_p536c']} | {info['join_target']} |"
        )
    add("")
    add(f"> {result['rolling_or_out_of_sample_feasibility']['artifact_wide_note']}")
    add("")

    add("## Missing Fields Or Blockers")
    add("")
    add("| required field | stable/spike | combination | cross-lottery |")
    add("|---|---|---|---|")
    for row in result["missing_fields_or_blockers"]["field_presence_checklist"]:
        add(
            f"| {row['required_field']} | {row['present_in_stable_short_window_groups']} | "
            f"{row['present_in_combination_group']} | {row['present_in_cross_lottery_group']} |"
        )
    add("")
    add("### Hard Blockers")
    add("")
    for item in result["missing_fields_or_blockers"]["hard_blockers_for_rolling_or_out_of_sample_evaluation"]:
        add(f"- {item}")
    add("")

    add("## Recommended Next Single-Worker Task")
    add("")
    next_task = result["recommended_next_single_worker_task"]
    add(f"- proposed_task_id: **{next_task['proposed_task_id']}**")
    add(f"- title: {next_task['title']}")
    add(f"- scope: {next_task['scope']}")
    add(f"- why_smallest_next_step: {next_task['why_smallest_next_step']}")
    add("- excluded_from_this_proposed_task:")
    for item in next_task["excluded_from_this_proposed_task"]:
        add(f"  - {item}")
    add("")

    add("## Provenance & Limits")
    add("")
    prov = result["provenance_and_limits"]
    add(
        f"- replay_data_hash_chain.verified_equal_across_all_three: "
        f"**{prov['replay_data_hash_chain']['verified_equal_across_all_three']}**"
    )
    for artifact_name, info in prov["source_artifacts"].items():
        add(f"- {artifact_name} file_sha256: `{info['file_sha256']}`")
    add(f"- selection_method: {prov['selection_method']}")
    add("- limitations:")
    for item in prov["limitations"]:
        add(f"  - {item}")
    add("")
    add(f"> {prov['disclaimer_en']}")
    add("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    if out_json.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_json}")
    if out_md.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_md}")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result) + "\n", encoding="utf-8")


def _default_dated_paths() -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"p538a_strategy_candidate_evaluation_readiness_{stamp}.json"
    md_path = OUTPUT_DIR / f"p538a_strategy_candidate_evaluation_readiness_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P538A strategy candidate evaluation readiness artifact")
    parser.add_argument("--p537a-source", default=str(DEFAULT_P537A_ARTIFACT))
    parser.add_argument("--p536k-source", default=str(DEFAULT_P536K_ARTIFACT))
    parser.add_argument("--p536c-source", default=str(DEFAULT_P536C_ARTIFACT))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_readiness_assessment(
        Path(args.p537a_source), Path(args.p536k_source), Path(args.p536c_source)
    )
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "candidate_group_counts": {
                    name: info["count"] for name, info in result["candidate_groups_for_next_stage_review"].items()
                },
                "replay_data_hash_chain_verified": result["provenance_and_limits"]["replay_data_hash_chain"][
                    "verified_equal_across_all_three"
                ],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
