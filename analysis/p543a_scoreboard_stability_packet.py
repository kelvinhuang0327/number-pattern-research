"""Build a deterministic descriptive stability packet from a scoreboard artifact.

This module only reads the JSON path supplied at the command line.  It does not
start services or import project runtime modules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


class SchemaError(ValueError):
    """Raised when an input artifact cannot support this packet safely."""


STRATEGY_SECTION = "top_strategy_pick_by_lottery_window_pick"
COMBINATION_SECTION = "best_combination_by_lottery_window_budget"

RANKING_METRICS = (
    "support_draws",
    "any_main_hit_rate",
    "baseline_any_main_rate",
    "any_main_hit_edge_pp",
    "prize_signal_rate",
    "baseline_prize_signal_rate",
    "prize_signal_edge_pp",
)
ZONE2_METRICS = (
    "support_draws",
    "zone2_hit_rate",
    "random_zone2_hit_rate",
    "zone2_hit_edge_pp",
    "prize_aware_hit_rate",
    "random_prize_aware_hit_rate",
    "prize_aware_edge_pp",
)
NUMERIC_FIELDS = frozenset((*RANKING_METRICS, *ZONE2_METRICS, "window", "pick_k", "requested_budget", "rank_in_bucket"))


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{label} must be an object")
    return value


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _missing_fields(row: Mapping[str, Any], fields: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        value = row.get(field)
        if value is None or value == "UNKNOWN":
            missing.append(field)
        elif field in NUMERIC_FIELDS:
            if not _finite_number(value):
                missing.append(field)
        elif not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def _sort_value(value: Any) -> tuple[int, Any]:
    if _finite_number(value):
        return (0, float(value))
    return (1, str(value))


def _metric_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in RANKING_METRICS}


def _zone2_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in ZONE2_METRICS}


def _record_unknown(
    unknown_rows: list[dict[str, Any]],
    section: str,
    source_key: str,
    missing_fields: list[str],
) -> None:
    unknown_rows.append(
        {
            "classification": "unknown_or_incomplete",
            "section": section,
            "source_key": source_key,
            "missing_fields": sorted(missing_fields),
            "status": "UNKNOWN",
        }
    )


def _ranking_observation(
    row: Any,
    *,
    section: str,
    source_key: str,
    candidate_field: str,
    bucket_field: str,
    rank: int,
    unknown_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        _record_unknown(unknown_rows, section, source_key, ["row"])
        return None

    required = ("lottery_type", "window", candidate_field, bucket_field, *RANKING_METRICS)
    missing = _missing_fields(row, required)
    if missing:
        _record_unknown(unknown_rows, section, source_key, missing)
        return None

    return {
        "section": section,
        "lottery": row["lottery_type"],
        "window": int(row["window"]),
        "bucket": row[bucket_field],
        "bucket_field": bucket_field,
        "candidate_id": row[candidate_field],
        "source_key": source_key,
        "source_rank": rank,
        "evidence": _metric_evidence(row),
    }


def _strategy_observations(
    rankings: Mapping[str, Any], unknown_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = _require_mapping(rankings.get(STRATEGY_SECTION), STRATEGY_SECTION)
    observations: list[dict[str, Any]] = []
    for source_key in sorted(rows):
        observation = _ranking_observation(
            rows[source_key],
            section="strategy_pick",
            source_key=str(source_key),
            candidate_field="strategy_id",
            bucket_field="pick_k",
            rank=1,
            unknown_rows=unknown_rows,
        )
        if observation is not None:
            observations.append(observation)
    return observations


def _combination_observations(
    artifact: Mapping[str, Any], rankings: Mapping[str, Any], top_n: int, unknown_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    raw_rows = artifact.get("combination_leaderboard")
    observations: list[dict[str, Any]] = []
    if isinstance(raw_rows, list) and raw_rows:
        for index, row in enumerate(raw_rows):
            source_key = f"combination_leaderboard[{index}]"
            if not isinstance(row, Mapping):
                _record_unknown(unknown_rows, "combination", source_key, ["row"])
                continue
            raw_rank = row.get("rank_in_bucket")
            if not _finite_number(raw_rank) or int(raw_rank) < 1:
                _record_unknown(unknown_rows, "combination", source_key, ["rank_in_bucket"])
                continue
            if int(raw_rank) > top_n:
                continue
            observation = _ranking_observation(
                row,
                section="combination",
                source_key=source_key,
                candidate_field="combo_id",
                bucket_field="requested_budget",
                rank=int(raw_rank),
                unknown_rows=unknown_rows,
            )
            if observation is not None:
                observations.append(observation)
        if observations:
            return observations

    rows = _require_mapping(rankings.get(COMBINATION_SECTION), COMBINATION_SECTION)
    for source_key in sorted(rows):
        observation = _ranking_observation(
            rows[source_key],
            section="combination",
            source_key=str(source_key),
            candidate_field="combo_id",
            bucket_field="requested_budget",
            rank=1,
            unknown_rows=unknown_rows,
        )
        if observation is not None:
            observations.append(observation)
    return observations


def _zone2_candidates(artifact: Mapping[str, Any], top_n: int, unknown_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_rows = artifact.get("power_lotto_zone2_metrics")
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, list):
        _record_unknown(unknown_rows, "power_lotto_zone2_metrics", "power_lotto_zone2_metrics", ["list"])
        return []

    grouped: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for index, row in enumerate(raw_rows):
        source_key = f"power_lotto_zone2_metrics[{index}]"
        if not isinstance(row, Mapping):
            _record_unknown(unknown_rows, "power_lotto_zone2_metrics", source_key, ["row"])
            continue
        missing = _missing_fields(row, ("scope", "identifier", "window", *ZONE2_METRICS))
        if missing:
            _record_unknown(unknown_rows, "power_lotto_zone2_metrics", source_key, missing)
            continue
        grouped[(str(row["scope"]), int(row["window"]))].append(row)

    candidates: list[dict[str, Any]] = []
    for (scope, window), rows in sorted(grouped.items()):
        ranked = sorted(
            rows,
            key=lambda row: (
                -float(row["prize_aware_edge_pp"]),
                -float(row["zone2_hit_edge_pp"]),
                str(row["identifier"]),
            ),
        )[:top_n]
        for rank, row in enumerate(ranked, start=1):
            candidates.append(
                {
                    "lottery": "POWER_LOTTO",
                    "section": "power_lotto_zone2_metrics",
                    "scope": scope,
                    "candidate_id": row["identifier"],
                    "source_rank": rank,
                    "window": window,
                    "evidence": _zone2_evidence(row),
                }
            )
    return candidates


def _group_ranking_candidates(observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        key = (
            observation["lottery"],
            observation["section"],
            observation["bucket_field"],
            observation["bucket"],
            observation["candidate_id"],
        )
        grouped[key].append(observation)

    stable: list[dict[str, Any]] = []
    spikes: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: tuple(_sort_value(part) for part in item)):
        rows = sorted(grouped[key], key=lambda row: (row["window"], row["source_rank"], row["source_key"]))
        windows = sorted({row["window"] for row in rows})
        candidate = {
            "classification": "multi_window_stable" if len(windows) >= 2 else "single_window_spike",
            "lottery": key[0],
            "section": key[1],
            "bucket_field": key[2],
            "bucket": key[3],
            "candidate_id": key[4],
            "observed_windows": windows,
            "window_count": len(windows),
            "evidence": rows,
        }
        if len(windows) >= 2:
            stable.append(candidate)
        else:
            spikes.append(candidate)
    return stable, spikes


def _group_zone2_candidates(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[(observation["lottery"], observation["scope"], observation["candidate_id"])].append(observation)

    candidates: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda row: (row["window"], row["source_rank"]))
        candidates.append(
            {
                "classification": "prize_or_zone2_signal",
                "lottery": key[0],
                "section": "power_lotto_zone2_metrics",
                "scope": key[1],
                "candidate_id": key[2],
                "observed_windows": sorted({row["window"] for row in rows}),
                "window_count": len({row["window"] for row in rows}),
                "evidence": rows,
            }
        )
    return candidates


def _not_comparable_rows(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], set[Any]] = defaultdict(set)
    for observation in observations:
        buckets[(observation["lottery"], observation["section"], observation["bucket_field"])].add(observation["bucket"])

    rows: list[dict[str, Any]] = []
    for (lottery, section, bucket_field), values in sorted(buckets.items()):
        if len(values) > 1:
            rows.append(
                {
                    "classification": "not_comparable",
                    "lottery": lottery,
                    "section": section,
                    "bucket_field": bucket_field,
                    "bucket_values": sorted(values, key=_sort_value),
                    "reason": "Rows with different selection-count buckets are retained separately and are not numerically ranked against each other.",
                }
            )
    return rows


def _per_lottery_summary(candidates: Mapping[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    lotteries = sorted({row["lottery"] for rows in candidates.values() for row in rows if "lottery" in row})
    summary: dict[str, dict[str, int]] = {}
    for lottery in lotteries:
        summary[lottery] = {
            classification: sum(1 for row in rows if row.get("lottery") == lottery)
            for classification, rows in sorted(candidates.items())
        }
    return summary


def _top_rows(observations: list[dict[str, Any]], zone2_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "lottery": row["lottery"],
            "window": row["window"],
            "section": row["section"],
            "bucket": row["bucket"],
            "source_rank": row["source_rank"],
            "candidate_id": row["candidate_id"],
            "evidence": row["evidence"],
        }
        for row in observations
    ]
    rows.extend(zone2_rows)
    return sorted(
        rows,
        key=lambda row: (
            row["lottery"],
            row["window"],
            row["section"],
            _sort_value(row.get("bucket", row.get("scope", ""))),
            row["source_rank"],
            row["candidate_id"],
        ),
    )


def _schema_summary(artifact: Mapping[str, Any], rankings: Mapping[str, Any], zone2_available: bool) -> dict[str, Any]:
    unsupported = [
        {
            "section": "walk_forward_or_permutation_validation",
            "status": "UNSUPPORTED",
            "reason": "The source artifact has no separate walk-forward or permutation result section.",
        }
    ]
    if not zone2_available:
        unsupported.append(
            {
                "section": "power_lotto_zone2_metrics",
                "status": "UNKNOWN",
                "reason": "No usable second-zone list is present in the source artifact.",
            }
        )
    return {
        "top_level_keys": sorted(artifact),
        "usable_ranking_sections": [
            {
                "name": STRATEGY_SECTION,
                "record_count": len(rankings[STRATEGY_SECTION]),
                "identity_field": "strategy_id",
                "bucket_field": "pick_k",
                "source_rank_available": True,
            },
            {
                "name": COMBINATION_SECTION,
                "record_count": len(rankings[COMBINATION_SECTION]),
                "identity_field": "combo_id",
                "bucket_field": "requested_budget",
                "source_rank_available": True,
            },
        ],
        "available_metric_fields": list(RANKING_METRICS),
        "zone2_metric_fields": list(ZONE2_METRICS) if zone2_available else [],
        "unsupported_or_unknown_sections": unsupported,
    }


def _markdown(packet: Mapping[str, Any]) -> str:
    def cell(value: Any) -> str:
        if value is None:
            return "UNKNOWN"
        return str(value).replace("|", "\\|").replace("\n", " ")

    def edge_from(row: Mapping[str, Any]) -> Any:
        evidence = row["evidence"]
        return evidence.get("prize_signal_edge_pp", evidence.get("prize_aware_edge_pp", "UNKNOWN"))

    lines = [
        "# P543A — Scoreboard Stability Packet",
        "",
        "> 本文件僅整理已提交 artifact 的歷史描述資料；不預測未來，也不構成投注建議。",
        "> 選擇偏差注意：來源中的 top rows 是從多個候選中挑出的歷史極值，edge 僅為描述性比較，可能偏樂觀。",
        "> 本 packet 不宣告任何候選可上線、可獲利或會在未來維持相同結果。",
        "",
        "## Source",
        "",
        f"- source artifact: `{packet['source_artifact']['path']}`",
        f"- SHA256: `{packet['source_artifact']['sha256']}`",
        f"- bytes: {packet['source_artifact']['bytes']}",
        f"- generated_at: `{packet['generated_at']}`",
        "",
        "## Schema Summary",
        "",
        f"- top-level keys: {', '.join(packet['schema_summary']['top_level_keys'])}",
        f"- ranking sections: {', '.join(item['name'] for item in packet['schema_summary']['usable_ranking_sections'])}",
        f"- supported windows: {', '.join(str(value) for value in packet['source_windows'])}",
        "- direct numeric comparison is restricted to matching lottery, section, and selection-count bucket.",
        "",
        "## Per-lottery Candidate Summary",
        "",
        "| lottery | multi-window stable | single-window spike | prize/zone2 signal | UNKNOWN/incomplete |",
        "|---|---:|---:|---:|---:|",
    ]
    for lottery, counts in packet["per_lottery_summary"].items():
        lines.append(
            "| {lottery} | {stable} | {spike} | {zone2} | {unknown} |".format(
                lottery=cell(lottery),
                stable=counts.get("multi_window_stable", 0),
                spike=counts.get("single_window_spike", 0),
                zone2=counts.get("prize_or_zone2_signal", 0),
                unknown=counts.get("unknown_or_incomplete", 0),
            )
        )

    lines.extend(
        [
            "",
            "## Top Historical Candidates by Matching Bucket",
            "",
            "| lottery | window | section | bucket/scope | source rank | candidate | descriptive edge (pp) |",
            "|---|---:|---|---|---:|---|---:|",
        ]
    )
    for row in packet["top_historical_candidates"]:
        bucket = row.get("bucket", row.get("scope", "UNKNOWN"))
        lines.append(
            "| {lottery} | {window} | {section} | {bucket} | {rank} | {candidate} | {edge} |".format(
                lottery=cell(row["lottery"]),
                window=cell(row["window"]),
                section=cell(row["section"]),
                bucket=cell(bucket),
                rank=cell(row["source_rank"]),
                candidate=cell(row["candidate_id"]),
                edge=cell(edge_from(row)),
            )
        )

    lines.extend(["", "## UNKNOWN / Missing-data Rows", "", "| section | source key | missing fields |", "|---|---|---|"])
    unknown_rows = packet["candidate_packet"]["unknown_or_incomplete"]
    if unknown_rows:
        for row in unknown_rows:
            lines.append(
                f"| {cell(row['section'])} | {cell(row['source_key'])} | {cell(', '.join(row['missing_fields']))} |"
            )
    else:
        lines.append("| NONE | No incomplete selected ranking rows | — |")

    lines.extend(["", "## Excluded / Not-comparable Rows", "", "| lottery | section | differing bucket values | reason |", "|---|---|---|---|"])
    not_comparable = packet["candidate_packet"]["not_comparable"]
    if not_comparable:
        for row in not_comparable:
            lines.append(
                "| {lottery} | {section} | {buckets} | {reason} |".format(
                    lottery=cell(row["lottery"]),
                    section=cell(row["section"]),
                    buckets=cell(", ".join(str(value) for value in row["bucket_values"])),
                    reason=cell(row["reason"]),
                )
            )
    else:
        lines.append("| NONE | — | — | No multi-bucket exclusion rows were found. |")

    lines.extend(
        [
            "",
            "## Next-step Recommendation",
            "",
            "P543B 可先評估 walk-forward / permutation 驗證的可行性，並以本 packet 的 evidence、bucket 與 UNKNOWN 狀態作為輸入；本任務不實作該驗證。",
            "",
        ]
    )
    return "\n".join(lines)


def build_packet_from_bytes(raw: bytes, source_path: str, generated_at: str, top_n: int = 10) -> tuple[dict[str, Any], str]:
    """Return deterministic JSON-ready content and Markdown for one artifact payload."""
    if not generated_at:
        raise ValueError("--generated-at is required")
    if top_n < 1:
        raise ValueError("--top-n must be at least 1")
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError("input is not valid UTF-8 JSON") from exc

    artifact = _require_mapping(artifact, "root")
    rankings = _require_mapping(artifact.get("descriptive_rankings"), "descriptive_rankings")
    for name in (STRATEGY_SECTION, COMBINATION_SECTION):
        rows = rankings.get(name)
        if not isinstance(rows, Mapping) or not rows:
            raise SchemaError(f"{name} is required and must not be empty")

    window_policy = _require_mapping(artifact.get("window_policy"), "window_policy")
    source_windows = window_policy.get("draw_windows")
    if not isinstance(source_windows, list) or not source_windows or not all(_finite_number(value) for value in source_windows):
        raise SchemaError("window_policy.draw_windows must be a non-empty numeric list")

    unknown_rows: list[dict[str, Any]] = []
    strategy_rows = _strategy_observations(rankings, unknown_rows)
    combination_rows = _combination_observations(artifact, rankings, top_n, unknown_rows)
    ranking_rows = strategy_rows + combination_rows
    if not ranking_rows:
        raise SchemaError("no complete ranking rows are available")

    zone2_rows = _zone2_candidates(artifact, top_n, unknown_rows)
    stable, spikes = _group_ranking_candidates(ranking_rows)
    zone2_candidates = _group_zone2_candidates(zone2_rows)
    unknown_rows = sorted(unknown_rows, key=lambda row: (row["section"], row["source_key"], row["missing_fields"]))
    not_comparable = _not_comparable_rows(ranking_rows)

    candidates = {
        "multi_window_stable": stable,
        "single_window_spike": spikes,
        "prize_or_zone2_signal": zone2_candidates,
        "unknown_or_incomplete": unknown_rows,
        "not_comparable": not_comparable,
    }
    packet = {
        "classification": "descriptive_only_stability_packet",
        "generated_at": generated_at,
        "source_artifact": {
            "path": source_path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        "source_windows": sorted({int(value) for value in source_windows}),
        "top_n": top_n,
        "schema_summary": _schema_summary(artifact, rankings, isinstance(artifact.get("power_lotto_zone2_metrics"), list)),
        "top_historical_candidates": _top_rows(ranking_rows, zone2_rows),
        "candidate_packet": candidates,
        "per_lottery_summary": _per_lottery_summary(candidates),
        "selection_bias_risk": {
            "status": "PRESENT",
            "reason": "Top rows are historical maxima selected from many candidates; descriptive edges may be optimistic.",
        },
        "next_step_recommendation": {
            "task": "P543B walk-forward/permutation feasibility or validation",
            "scope": "Assess validation feasibility using only the packet evidence; implementation is outside P543A.",
        },
        "safety": {
            "descriptive_only": True,
            "no_prediction_claim": True,
            "no_betting_advice": True,
        },
    }
    return packet, _markdown(packet)


def generate(input_json: Path, output_json: Path, output_md: Path, generated_at: str, top_n: int = 10) -> None:
    raw = input_json.read_bytes()
    packet, markdown = build_packet_from_bytes(raw, str(input_json), generated_at, top_n)
    output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a deterministic descriptive scoreboard stability packet.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate(Path(args.input_json), Path(args.output_json), Path(args.output_md), args.generated_at, args.top_n)


if __name__ == "__main__":
    main()
