"""Create a deterministic feasibility packet from committed scoreboard artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping


class SchemaError(ValueError):
    """Raised when the supplied artifact shape cannot be interpreted safely."""


CANDIDATE_CLASSES = (
    "multi_window_stable",
    "single_window_spike",
    "prize_or_zone2_signal",
    "unknown_or_incomplete",
    "not_comparable",
)
PER_DRAW_KEY = "per_draw_validation_rows"
PILOT_PERMUTATION_ROUNDS = 32


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{label} must be an object")
    return value


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sort_value(value: Any) -> tuple[int, Any]:
    if _finite(value):
        return (0, float(value))
    return (1, str(value))


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("lottery", "")),
        str(row.get("section", "")),
        _sort_value(row.get("bucket", row.get("scope", ""))),
        str(row.get("candidate_id", "")),
    )


def _source_metadata(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _decode(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError(f"{label} is not valid UTF-8 JSON") from exc
    return _mapping(value, label)


def _extract_candidate_rows(p543a: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    packet = _mapping(p543a.get("candidate_packet"), "p543a.candidate_packet")
    classes: dict[str, list[dict[str, Any]]] = {}
    issues: list[dict[str, Any]] = []
    for candidate_class in CANDIDATE_CLASSES:
        rows = packet.get(candidate_class)
        if not isinstance(rows, list):
            raise SchemaError(f"p543a.candidate_packet.{candidate_class} must be a list")
        parsed: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                issues.append(
                    {
                        "candidate_class": candidate_class,
                        "source_index": index,
                        "status": "blocked_schema_ambiguous",
                        "reason": "Candidate row is not an object.",
                    }
                )
                continue
            parsed.append(dict(row))
        classes[candidate_class] = sorted(parsed, key=_candidate_sort_key)
    return classes, sorted(issues, key=lambda row: (row["candidate_class"], row["source_index"]))


def _valid_number_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, (int, str)) and not isinstance(item, bool) for item in value
    )


def _per_draw_inventory(p542a: Mapping[str, Any]) -> dict[str, Any]:
    if PER_DRAW_KEY not in p542a:
        return {
            "status": "ABSENT",
            "row_count": 0,
            "valid_rows_by_candidate": {},
            "issues_by_candidate": {},
            "global_issues": [
                "blocked_missing_per_draw_predictions",
                "blocked_missing_actual_draw_outcomes",
            ],
            "reason": "The committed source has aggregate rows but no per_draw_validation_rows section.",
        }

    rows = p542a[PER_DRAW_KEY]
    if not isinstance(rows, list) or not rows:
        return {
            "status": "AMBIGUOUS",
            "row_count": 0 if not isinstance(rows, list) else len(rows),
            "valid_rows_by_candidate": {},
            "issues_by_candidate": {},
            "global_issues": ["blocked_schema_ambiguous"],
            "reason": "per_draw_validation_rows must be a non-empty list.",
        }

    valid_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    issues: dict[str, set[str]] = defaultdict(set)
    global_issues: set[str] = set()
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, Mapping):
            global_issues.add("blocked_schema_ambiguous")
            continue
        candidate_id = raw_row.get("candidate_id")
        if not _identifier(candidate_id):
            global_issues.add("blocked_schema_ambiguous")
            continue
        candidate_id = str(candidate_id)
        if not _valid_number_list(raw_row.get("predicted_numbers")):
            issues[candidate_id].add("blocked_missing_per_draw_predictions")
        if not _valid_number_list(raw_row.get("actual_numbers")):
            issues[candidate_id].add("blocked_missing_actual_draw_outcomes")
        if not (_finite(raw_row.get("window")) and raw_row.get("window") > 0 and raw_row.get("draw_id") is not None):
            issues[candidate_id].add("blocked_schema_ambiguous")
        if issues[candidate_id]:
            continue
        valid_rows[candidate_id].append(
            {
                "candidate_id": candidate_id,
                "draw_id": raw_row["draw_id"],
                "window": int(raw_row["window"]),
                "predicted_numbers": list(raw_row["predicted_numbers"]),
                "actual_numbers": list(raw_row["actual_numbers"]),
                "source_index": index,
            }
        )

    for candidate_id in valid_rows:
        valid_rows[candidate_id].sort(key=lambda row: (_sort_value(row["draw_id"]), row["source_index"]))
    return {
        "status": "AVAILABLE" if valid_rows else "AMBIGUOUS",
        "row_count": len(rows),
        "valid_rows_by_candidate": dict(sorted(valid_rows.items())),
        "issues_by_candidate": {key: sorted(value) for key, value in sorted(issues.items())},
        "global_issues": sorted(global_issues),
        "reason": "Explicit per-draw validation rows were inspected." if valid_rows else "No complete per-draw rows were available.",
    }


def _candidate_feasibility(
    candidate_class: str, row: Mapping[str, Any], per_draw: Mapping[str, Any]
) -> dict[str, Any]:
    base = {
        "candidate_class": candidate_class,
        "lottery": row.get("lottery", "UNKNOWN"),
        "section": row.get("section", "UNKNOWN"),
        "candidate_id": row.get("candidate_id", "UNKNOWN"),
    }
    if candidate_class in {"unknown_or_incomplete", "not_comparable"}:
        return {
            **base,
            "walk_forward_status": "unsupported",
            "permutation_status": "unsupported",
            "overall_status": "unsupported",
            "per_draw_row_count": 0,
            "blockers": [candidate_class],
        }
    if not _identifier(row.get("candidate_id")):
        return {
            **base,
            "walk_forward_status": "blocked_schema_ambiguous",
            "permutation_status": "blocked_schema_ambiguous",
            "overall_status": "blocked_schema_ambiguous",
            "per_draw_row_count": 0,
            "blockers": ["blocked_schema_ambiguous"],
        }

    candidate_id = str(row["candidate_id"])
    if per_draw["status"] == "ABSENT":
        blockers = list(per_draw["global_issues"])
        return {
            **base,
            "walk_forward_status": "blocked_missing_per_draw_predictions",
            "permutation_status": "blocked_missing_per_draw_predictions",
            "overall_status": "aggregate_only_not_validatable",
            "per_draw_row_count": 0,
            "blockers": blockers,
        }

    candidate_issues = list(per_draw["issues_by_candidate"].get(candidate_id, []))
    if candidate_issues:
        primary = candidate_issues[0]
        return {
            **base,
            "walk_forward_status": primary,
            "permutation_status": primary,
            "overall_status": "aggregate_only_not_validatable",
            "per_draw_row_count": 0,
            "blockers": candidate_issues,
        }
    if per_draw["global_issues"]:
        return {
            **base,
            "walk_forward_status": "blocked_schema_ambiguous",
            "permutation_status": "blocked_schema_ambiguous",
            "overall_status": "blocked_schema_ambiguous",
            "per_draw_row_count": 0,
            "blockers": list(per_draw["global_issues"]),
        }
    rows = per_draw["valid_rows_by_candidate"].get(candidate_id, [])
    if len(rows) < 2:
        return {
            **base,
            "walk_forward_status": "blocked_missing_per_draw_predictions",
            "permutation_status": "blocked_missing_per_draw_predictions",
            "overall_status": "aggregate_only_not_validatable",
            "per_draw_row_count": len(rows),
            "blockers": ["blocked_missing_per_draw_predictions", "blocked_missing_actual_draw_outcomes"],
        }
    return {
        **base,
        "walk_forward_status": "walk_forward_possible_from_committed_artifacts",
        "permutation_status": "permutation_possible_from_committed_artifacts",
        "overall_status": "walk_forward_possible_from_committed_artifacts",
        "per_draw_row_count": len(rows),
        "blockers": [],
    }


def _feasibility_summary(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "walk_forward_possible_from_committed_artifacts": sum(
            row["walk_forward_status"] == "walk_forward_possible_from_committed_artifacts" for row in rows
        ),
        "permutation_possible_from_committed_artifacts": sum(
            row["permutation_status"] == "permutation_possible_from_committed_artifacts" for row in rows
        ),
        "aggregate_only_not_validatable": sum(row["overall_status"] == "aggregate_only_not_validatable" for row in rows),
        "blocked_missing_per_draw_predictions": sum(
            "blocked_missing_per_draw_predictions" in row["blockers"] for row in rows
        ),
        "blocked_missing_actual_draw_outcomes": sum(
            "blocked_missing_actual_draw_outcomes" in row["blockers"] for row in rows
        ),
        "blocked_schema_ambiguous": sum("blocked_schema_ambiguous" in row["blockers"] for row in rows),
        "unsupported": sum(row["overall_status"] == "unsupported" for row in rows),
    }


def _pilot(
    candidate_rows: list[Mapping[str, Any]],
    per_draw: Mapping[str, Any],
    top_n: int,
    seed: int,
) -> dict[str, Any]:
    eligible = [
        row
        for row in candidate_rows
        if row["candidate_class"] == "multi_window_stable"
        and row["walk_forward_status"] == "walk_forward_possible_from_committed_artifacts"
        and row["permutation_status"] == "permutation_possible_from_committed_artifacts"
    ]
    selected: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(eligible, key=_candidate_sort_key):
        candidate_id = str(row["candidate_id"])
        if candidate_id not in seen:
            selected.append(row)
            seen.add(candidate_id)
        if len(selected) == top_n:
            break
    if not selected:
        return {
            "computed": False,
            "reason": "No high-stability candidate has complete committed per-draw predictions and actual outcomes.",
            "candidate_count": 0,
            "seed": seed,
            "results": [],
        }

    rng = random.Random(seed)
    results: list[dict[str, Any]] = []
    for candidate in selected:
        rows = per_draw["valid_rows_by_candidate"][str(candidate["candidate_id"])]
        observed_hits = [
            bool(set(row["predicted_numbers"]) & set(row["actual_numbers"]))
            for row in rows
        ]
        permutation_rates: list[float] = []
        actual_sets = [set(row["actual_numbers"]) for row in rows]
        for _ in range(PILOT_PERMUTATION_ROUNDS):
            shuffled = list(actual_sets)
            rng.shuffle(shuffled)
            permutation_rates.append(
                sum(bool(set(row["predicted_numbers"]) & actual) for row, actual in zip(rows, shuffled)) / len(rows)
            )
        observed_rate = sum(observed_hits) / len(rows)
        baseline_rate = sum(permutation_rates) / len(permutation_rates)
        results.append(
            {
                "candidate_id": candidate["candidate_id"],
                "lottery": candidate["lottery"],
                "section": candidate["section"],
                "draw_rows": len(rows),
                "observed_any_overlap_rate": round(observed_rate, 12),
                "permutation_mean_any_overlap_rate": round(baseline_rate, 12),
                "descriptive_difference": round(observed_rate - baseline_rate, 12),
            }
        )
    return {
        "computed": True,
        "reason": "Capped deterministic overlap pilot from an explicit committed per-draw schema; descriptive only.",
        "candidate_count": len(results),
        "seed": seed,
        "permutation_rounds": PILOT_PERMUTATION_ROUNDS,
        "results": sorted(results, key=lambda row: (row["lottery"], row["section"], row["candidate_id"])),
    }


def _matrix(classes: Mapping[str, list[Mapping[str, Any]]], per_draw: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_rows: list[dict[str, Any]] = []
    matrix: list[dict[str, Any]] = []
    for candidate_class in CANDIDATE_CLASSES:
        rows = [_candidate_feasibility(candidate_class, row, per_draw) for row in classes[candidate_class]]
        all_rows.extend(rows)
        matrix.append(
            {
                "candidate_class": candidate_class,
                "source_count": len(classes[candidate_class]),
                "summary": _feasibility_summary(rows),
            }
        )
    return matrix, sorted(all_rows, key=lambda row: (row["candidate_class"], _candidate_sort_key(row)))


def _markdown(packet: Mapping[str, Any]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# P543B — Scoreboard Validation Feasibility / Minimal Pilot",
        "",
        "> 本文件只評估已提交 artifacts 的驗證可行性；不預測未來，也不構成投注建議。",
        "> P543B 僅為 feasibility / pilot；不表示任何候選可正式使用、可上線或已具備正式環境準備。",
        "> 若有 pilot，數值只描述固定輸入與固定 seed 的小型重排比較，不代表未來表現。",
        "",
        "## Sources",
        "",
        "| artifact | SHA256 | bytes | purpose |",
        "|---|---|---:|---|",
    ]
    for item in packet["source_artifacts"]:
        lines.append(f"| `{cell(item['path'])}` | `{item['sha256']}` | {item['bytes']} | {cell(item['purpose'])} |")

    lines.extend(
        [
            "",
            "## Inspected Artifact Inventory",
            "",
            "| artifact | usable fields | finding |",
            "|---|---|---|",
        ]
    )
    for item in packet["inspected_artifacts"]:
        lines.append(
            f"| `{cell(item['path'])}` | {cell(', '.join(item['usable_fields']))} | {cell(item['finding'])} |"
        )

    lines.extend(
        [
            "",
            "## Feasibility Matrix",
            "",
            "| candidate class | source rows | walk-forward possible | permutation possible | aggregate only | missing predictions | missing actual outcomes | unsupported |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in packet["feasibility_matrix"]:
        summary = item["summary"]
        lines.append(
            "| {klass} | {source} | {walk} | {perm} | {aggregate} | {pred} | {actual} | {unsupported} |".format(
                klass=cell(item["candidate_class"]),
                source=item["source_count"],
                walk=summary["walk_forward_possible_from_committed_artifacts"],
                perm=summary["permutation_possible_from_committed_artifacts"],
                aggregate=summary["aggregate_only_not_validatable"],
                pred=summary["blocked_missing_per_draw_predictions"],
                actual=summary["blocked_missing_actual_draw_outcomes"],
                unsupported=summary["unsupported"],
            )
        )

    pilot = packet["pilot"]
    lines.extend(["", "## Pilot", ""])
    if pilot["computed"]:
        lines.extend(
            [
                f"Computed: YES; candidates: {pilot['candidate_count']}; fixed seed: {pilot['seed']}; rounds: {pilot['permutation_rounds']}.",
                "",
                "| candidate | draw rows | observed overlap | permutation mean | descriptive difference |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in pilot["results"]:
            lines.append(
                "| {candidate} | {draws} | {observed} | {baseline} | {difference} |".format(
                    candidate=cell(row["candidate_id"]),
                    draws=row["draw_rows"],
                    observed=row["observed_any_overlap_rate"],
                    baseline=row["permutation_mean_any_overlap_rate"],
                    difference=row["descriptive_difference"],
                )
            )
    else:
        lines.append(f"Computed: NO — {pilot['reason']}")
        lines.append("Required gap: chronological draw ID, candidate ID, selected numbers, and actual drawn numbers in one committed per-draw artifact.")

    lines.extend(
        [
            "",
            "## Recommended Next Task",
            "",
            "Create and audit a committed per-draw validation-input contract containing chronological draw IDs, candidate IDs, selected numbers, and actual outcomes. Only after that contract is available should a separate validation task implement walk-forward or permutation analysis.",
            "",
        ]
    )
    return "\n".join(lines)


def build_packet_from_bytes(
    p543a_raw: bytes,
    p543a_path: str,
    p542a_raw: bytes,
    p542a_path: str,
    generated_at: str,
    top_n: int = 10,
    seed: int = 543210,
    artifact_root: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Build JSON-ready data and Markdown without consulting any external state."""
    if not generated_at:
        raise ValueError("--generated-at is required")
    if top_n < 1:
        raise ValueError("--top-n must be at least 1")
    p543a = _decode(p543a_raw, "p543a")
    p542a = _decode(p542a_raw, "p542a")
    classes, schema_issues = _extract_candidate_rows(p543a)
    per_draw = _per_draw_inventory(p542a)
    matrix, candidate_rows = _matrix(classes, per_draw)
    pilot = _pilot(candidate_rows, per_draw, top_n, seed)

    source_artifacts = [
        {**_source_metadata(p543a_path, p543a_raw), "purpose": "P543A candidate classes and aggregate evidence."},
        {**_source_metadata(p542a_path, p542a_raw), "purpose": "P542A aggregate metric schema and per-draw availability."},
    ]
    inspected = [
        {
            "path": p543a_path,
            "reason": "Read candidate classes and their aggregate evidence.",
            "usable_fields": ["candidate_packet", "candidate_id", "observed_windows", "evidence"],
            "finding": "Provides candidate classes, but not per-draw selected numbers or actual outcomes.",
        },
        {
            "path": p542a_path,
            "reason": "Determine whether committed rows permit a pilot.",
            "usable_fields": ["strategy_pick_matrix", "combination_leaderboard", "power_lotto_zone2_metrics", "window_policy"],
            "finding": per_draw["reason"],
        },
    ]
    packet = {
        "classification": "descriptive_only_validation_feasibility_packet",
        "generated_at": generated_at,
        "seed": seed,
        "top_n": top_n,
        "source_artifacts": source_artifacts,
        "artifact_root": artifact_root,
        "additional_artifact_scan_performed": False,
        "inspected_artifacts": inspected,
        "p542a_top_level_keys": sorted(p542a),
        "p543a_top_level_keys": sorted(p543a),
        "per_draw_inventory": {
            "status": per_draw["status"],
            "row_count": per_draw["row_count"],
            "reason": per_draw["reason"],
            "global_issues": per_draw["global_issues"],
        },
        "feasibility_matrix": matrix,
        "candidate_feasibility": candidate_rows,
        "schema_issues": schema_issues,
        "pilot": pilot,
        "summary": _feasibility_summary(candidate_rows),
        "safety": {
            "descriptive_only": True,
            "no_prediction_claim": True,
            "no_betting_advice": True,
            "no_read_or_write_of_local_data_store": True,
        },
        "next_step_recommendation": "Create and audit a committed per-draw validation-input contract before any validation implementation.",
    }
    return packet, _markdown(packet)


def generate(
    p543a_json: Path,
    p542a_json: Path,
    output_json: Path,
    output_md: Path,
    generated_at: str,
    top_n: int = 10,
    seed: int = 543210,
    artifact_root: str | None = None,
) -> None:
    packet, markdown = build_packet_from_bytes(
        p543a_json.read_bytes(),
        str(p543a_json),
        p542a_json.read_bytes(),
        str(p542a_json),
        generated_at,
        top_n,
        seed,
        artifact_root,
    )
    output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a deterministic scoreboard validation feasibility packet.")
    parser.add_argument("--p543a-json", required=True)
    parser.add_argument("--p542a-json", required=True)
    parser.add_argument("--artifact-root")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=543210)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate(
        Path(args.p543a_json),
        Path(args.p542a_json),
        Path(args.output_json),
        Path(args.output_md),
        args.generated_at,
        args.top_n,
        args.seed,
        args.artifact_root,
    )


if __name__ == "__main__":
    main()
