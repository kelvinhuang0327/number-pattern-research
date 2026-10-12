"""Create a deterministic descriptive pilot from a committed JSON contract only."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


DEFAULT_SEED = 543_010
DEFAULT_PERMUTATIONS = 1_000
STABILITY_DELTA_THRESHOLD = 0.10
ABOVE_BASELINE_PERCENTILE = 0.90
BELOW_BASELINE_PERCENTILE = 0.10
REQUIRED_ROW_FIELDS = (
    "actual_numbers",
    "candidate_id",
    "draw_date",
    "draw_id",
    "draw_order",
    "hit_count",
    "lottery",
    "selected_numbers",
    "strategy_ids",
)


class ContractSchemaError(ValueError):
    """Raised when the committed contract cannot be evaluated without guessing."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractSchemaError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractSchemaError(f"{label} must be a list")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractSchemaError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractSchemaError(f"{label} must be at least {minimum}")
    return value


def _numbers(value: Any, label: str) -> list[int]:
    values = _list(value, label)
    if not values or any(not isinstance(item, int) or isinstance(item, bool) for item in values):
        raise ContractSchemaError(f"{label} must be a non-empty list of integers")
    if len(set(values)) != len(values):
        raise ContractSchemaError(f"{label} must not contain duplicate numbers")
    return values


def _decode(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractSchemaError(f"{label} is not valid UTF-8 JSON") from exc
    return _mapping(value, label)


def _metadata(path: str, raw: bytes, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _mean(values: list[int] | list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _quantile_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "min": None, "max": None}
    return {"mean": _mean(values), "min": round(min(values), 6), "max": round(max(values), 6)}


def _candidate_linkage(candidate: Mapping[str, Any], label: str) -> tuple[str, int]:
    candidate_id = candidate.get("candidate_id")
    strategy_id = candidate.get("strategy_id")
    bet_index = candidate.get("bet_index")
    if not isinstance(candidate_id, str) or not candidate_id or not isinstance(strategy_id, str) or not strategy_id:
        raise ContractSchemaError(f"{label} must contain candidate_id and strategy_id strings")
    bet = _integer(bet_index, f"{label}.bet_index", minimum=1)
    if candidate_id != f"{strategy_id}:{bet}":
        raise ContractSchemaError(f"{label} candidate_id must equal strategy_id:bet_index")
    return strategy_id, bet


def _normalise_contract(packet: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    contract = _mapping(packet.get("contract"), "p543c.contract")
    if contract.get("contract_status") != "generated":
        raise ContractSchemaError("p543c.contract.contract_status must be generated")
    candidates = _list(packet.get("candidate_subset"), "p543c.candidate_subset")
    rows = _list(contract.get("rows"), "p543c.contract.rows")
    candidate_data: dict[str, dict[str, Any]] = {}
    for position, raw_candidate in enumerate(candidates):
        candidate = dict(_mapping(raw_candidate, f"p543c.candidate_subset[{position}]"))
        strategy_id, bet_index = _candidate_linkage(candidate, f"p543c.candidate_subset[{position}]")
        candidate_id = candidate["candidate_id"]
        lottery = candidate.get("lottery")
        if not isinstance(lottery, str) or not lottery:
            raise ContractSchemaError(f"candidate {candidate_id} must have a lottery")
        if candidate_id in candidate_data:
            raise ContractSchemaError(f"duplicate candidate_id: {candidate_id}")
        candidate_data[candidate_id] = {
            "candidate_id": candidate_id,
            "strategy_id": strategy_id,
            "bet_index": bet_index,
            "lottery": lottery,
        }
    if not candidate_data:
        raise ContractSchemaError("p543c.candidate_subset must not be empty")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalised_rows: list[dict[str, Any]] = []
    for position, raw_row in enumerate(rows):
        row = dict(_mapping(raw_row, f"p543c.contract.rows[{position}]"))
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            raise ContractSchemaError(f"row {position} is missing required fields: {', '.join(missing)}")
        candidate_id = row["candidate_id"]
        if candidate_id not in candidate_data:
            raise ContractSchemaError(f"row {position} references an unknown candidate_id")
        candidate = candidate_data[candidate_id]
        if row["lottery"] != candidate["lottery"]:
            raise ContractSchemaError(f"row {position} lottery does not match its candidate")
        strategy_ids = _list(row["strategy_ids"], f"row {position}.strategy_ids")
        if strategy_ids != [candidate["strategy_id"]]:
            raise ContractSchemaError(f"row {position} strategy_ids do not match its candidate")
        selected = _numbers(row["selected_numbers"], f"row {position}.selected_numbers")
        actual = _numbers(row["actual_numbers"], f"row {position}.actual_numbers")
        supplied_hits = _integer(row["hit_count"], f"row {position}.hit_count", minimum=0)
        calculated_hits = len(set(selected) & set(actual))
        if supplied_hits != calculated_hits:
            raise ContractSchemaError(f"row {position} hit_count does not match selected and actual numbers")
        draw_order = _integer(row["draw_order"], f"row {position}.draw_order", minimum=1)
        if not isinstance(row["draw_id"], str) or not row["draw_id"] or not isinstance(row["draw_date"], str) or not row["draw_date"]:
            raise ContractSchemaError(f"row {position} needs draw_id and draw_date strings")
        label = row.get("candidate_label") if isinstance(row.get("candidate_label"), str) else candidate_id
        normalised = {
            "candidate_id": candidate_id,
            "candidate_label": label or candidate_id,
            "lottery": row["lottery"],
            "strategy_id": candidate["strategy_id"],
            "bet_index": candidate["bet_index"],
            "draw_order": draw_order,
            "draw_id": row["draw_id"],
            "draw_date": row["draw_date"],
            "selected_numbers": selected,
            "actual_numbers": actual,
            "hit_count": supplied_hits,
            "special_selected": row.get("special_selected"),
            "special_actual": row.get("special_actual"),
            "zone2_selected": row.get("zone2_selected"),
            "zone2_actual": row.get("zone2_actual"),
        }
        grouped[candidate_id].append(normalised)
        normalised_rows.append(normalised)
    if set(grouped) != set(candidate_data):
        missing = sorted(set(candidate_data) - set(grouped))
        raise ContractSchemaError(f"candidates without contract rows: {', '.join(missing)}")
    for candidate_id, candidate_rows in grouped.items():
        candidate_rows.sort(key=lambda row: (row["draw_order"], row["draw_id"], row["draw_date"]))
        orders = [row["draw_order"] for row in candidate_rows]
        if len(orders) != len(set(orders)):
            raise ContractSchemaError(f"candidate {candidate_id} has duplicate draw_order values")
    return sorted(normalised_rows, key=lambda row: (row["lottery"], row["candidate_id"], row["draw_order"], row["draw_id"], row["draw_date"])), dict(sorted(grouped.items())), candidate_data


def _optional_source(path: str | None, role: str) -> tuple[dict[str, Any] | None, bytes | None]:
    if path is None:
        return None, None
    raw = Path(path).read_bytes()
    _decode(raw, role)
    return _metadata(path, raw, role), raw


def _outcome_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hit_counts = [row["hit_count"] for row in rows]
    special_pairs = [row for row in rows if row["special_selected"] is not None and row["special_actual"] is not None]
    zone_pairs = [row for row in rows if row["zone2_selected"] is not None and row["zone2_actual"] is not None]
    return {
        "row_count": len(rows),
        "draw_range": {"first": rows[0]["draw_id"], "last": rows[-1]["draw_id"], "first_date": rows[0]["draw_date"], "last_date": rows[-1]["draw_date"]},
        "hit_count_distribution": {str(key): value for key, value in sorted(Counter(hit_counts).items())},
        "at_least_one_hit_count": sum(hit > 0 for hit in hit_counts),
        "at_least_one_hit_rate": _rate(sum(hit > 0 for hit in hit_counts), len(rows)),
        "average_hit_count": _mean(hit_counts),
        "special_hit": {
            "available": bool(special_pairs),
            "eligible_rows": len(special_pairs),
            "hit_count": sum(row["special_selected"] == row["special_actual"] for row in special_pairs) if special_pairs else None,
            "hit_rate": _rate(sum(row["special_selected"] == row["special_actual"] for row in special_pairs), len(special_pairs)) if special_pairs else None,
        },
        "zone2_hit": {
            "available": bool(zone_pairs),
            "eligible_rows": len(zone_pairs),
            "hit_count": sum(row["zone2_selected"] == row["zone2_actual"] for row in zone_pairs) if zone_pairs else None,
            "hit_rate": _rate(sum(row["zone2_selected"] == row["zone2_actual"] for row in zone_pairs), len(zone_pairs)) if zone_pairs else None,
        },
    }


def chronological_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row["draw_order"], row["draw_id"], row["draw_date"]))
    midpoint = len(ordered) // 2
    if midpoint == 0 or len(ordered) - midpoint == 0:
        return {"first_half_rows": midpoint, "second_half_rows": len(ordered) - midpoint, "first_half_at_least_one_hit_rate": None, "second_half_at_least_one_hit_rate": None, "absolute_delta": None, "stability_label": "insufficient_rows"}
    first = _outcome_metric(ordered[:midpoint])["at_least_one_hit_rate"]
    second = _outcome_metric(ordered[midpoint:])["at_least_one_hit_rate"]
    assert first is not None and second is not None
    delta = round(abs(second - first), 6)
    if len(ordered) < 4:
        label = "insufficient_rows"
    elif delta <= STABILITY_DELTA_THRESHOLD:
        label = "stable_descriptive"
    elif second < first:
        label = "late_drop"
    else:
        label = "late_improvement"
    return {"first_half_rows": midpoint, "second_half_rows": len(ordered) - midpoint, "first_half_at_least_one_hit_rate": first, "second_half_at_least_one_hit_rate": second, "absolute_delta": delta, "stability_label": label}


def _permuted_metrics(rows: list[dict[str, Any]], outcomes: dict[int, tuple[list[int], Any, Any]]) -> tuple[float, float, float | None, float | None]:
    hits: list[int] = []
    special_hits: list[int] = []
    zone_hits: list[int] = []
    for index, row in enumerate(rows):
        actual_numbers, special_actual, zone2_actual = outcomes[index]
        hit_count = len(set(row["selected_numbers"]) & set(actual_numbers))
        hits.append(hit_count)
        if row["special_selected"] is not None and special_actual is not None:
            special_hits.append(int(row["special_selected"] == special_actual))
        if row["zone2_selected"] is not None and zone2_actual is not None:
            zone_hits.append(int(row["zone2_selected"] == zone2_actual))
    return _rate(sum(hit > 0 for hit in hits), len(hits)) or 0.0, _mean(hits) or 0.0, _rate(sum(special_hits), len(special_hits)) if special_hits else None, _rate(sum(zone_hits), len(zone_hits)) if zone_hits else None


def permutation_baselines(grouped: Mapping[str, list[dict[str, Any]]], seed: int, permutations: int) -> dict[str, dict[str, Any]]:
    if permutations < 1:
        raise ValueError("permutations must be at least 1")
    rng = random.Random(seed)
    lottery_rows: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    for candidate_id, rows in grouped.items():
        for index, row in enumerate(rows):
            lottery_rows[row["lottery"]].append((candidate_id, index, row))
    distributions: dict[str, dict[str, list[float]]] = {candidate_id: {"rate": [], "average": [], "special": [], "zone2": []} for candidate_id in grouped}
    for _ in range(permutations):
        permuted: dict[str, dict[int, tuple[list[int], Any, Any]]] = {candidate_id: {} for candidate_id in grouped}
        for lottery in sorted(lottery_rows):
            entries = lottery_rows[lottery]
            outcomes = [(row["actual_numbers"], row["special_actual"], row["zone2_actual"]) for _, _, row in entries]
            rng.shuffle(outcomes)
            for (candidate_id, index, _), outcome in zip(entries, outcomes):
                permuted[candidate_id][index] = outcome
        for candidate_id, rows in grouped.items():
            rate, average, special, zone2 = _permuted_metrics(rows, permuted[candidate_id])
            distributions[candidate_id]["rate"].append(rate)
            distributions[candidate_id]["average"].append(average)
            if special is not None:
                distributions[candidate_id]["special"].append(special)
            if zone2 is not None:
                distributions[candidate_id]["zone2"].append(zone2)
    result: dict[str, dict[str, Any]] = {}
    for candidate_id in sorted(grouped):
        observed = _outcome_metric(grouped[candidate_id])
        rate_values = distributions[candidate_id]["rate"]
        avg_values = distributions[candidate_id]["average"]
        observed_rate = observed["at_least_one_hit_rate"]
        observed_avg = observed["average_hit_count"]
        assert observed_rate is not None and observed_avg is not None
        rate_at_or_below = sum(value <= observed_rate for value in rate_values)
        avg_at_or_below = sum(value <= observed_avg for value in avg_values)
        result[candidate_id] = {
            "permutations": permutations,
            "seed": seed,
            "at_least_one_hit_rate": {"observed": observed_rate, "distribution": _quantile_summary(rate_values), "observed_at_or_above_permutation_count": rate_at_or_below, "permutation_at_or_above_observed_count": sum(value >= observed_rate for value in rate_values), "empirical_percentile": _rate(rate_at_or_below, permutations)},
            "average_hit_count": {"observed": observed_avg, "distribution": _quantile_summary(avg_values), "observed_at_or_above_permutation_count": avg_at_or_below, "permutation_at_or_above_observed_count": sum(value >= observed_avg for value in avg_values), "empirical_percentile": _rate(avg_at_or_below, permutations)},
            "special_hit_rate": {"available": bool(distributions[candidate_id]["special"]), "distribution": _quantile_summary(distributions[candidate_id]["special"]), "observed": observed["special_hit"]["hit_rate"]},
            "zone2_hit_rate": {"available": bool(distributions[candidate_id]["zone2"]), "distribution": _quantile_summary(distributions[candidate_id]["zone2"]), "observed": observed["zone2_hit"]["hit_rate"]},
        }
    return result


def classify_candidate(metric: Mapping[str, Any], split: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    row_count = _integer(metric["row_count"], "metric.row_count", minimum=0)
    stability = split["stability_label"]
    percentile = baseline["at_least_one_hit_rate"]["empirical_percentile"]
    if row_count < 4 or stability == "insufficient_rows":
        label = "insufficient_or_unsupported"
    elif stability != "stable_descriptive":
        label = "chronologically_unstable"
    elif percentile is not None and percentile >= ABOVE_BASELINE_PERCENTILE:
        label = "pilot_above_permutation_baseline"
    elif percentile is not None and percentile <= BELOW_BASELINE_PERCENTILE:
        label = "pilot_below_permutation_baseline"
    else:
        label = "pilot_near_permutation_baseline"
    return {"label": label, "evidence": {"row_count": row_count, "stability_label": stability, "absolute_split_delta": split["absolute_delta"], "observed_at_least_one_hit_rate": metric["at_least_one_hit_rate"], "permutation_mean_at_least_one_hit_rate": baseline["at_least_one_hit_rate"]["distribution"]["mean"], "empirical_percentile": percentile, "above_baseline_threshold": ABOVE_BASELINE_PERCENTILE, "below_baseline_threshold": BELOW_BASELINE_PERCENTILE}}


def build_pilot_from_bytes(p543c_raw: bytes, p543c_path: str, generated_at: str, *, optional_sources: list[tuple[str, str, bytes]] | None = None, seed: int = DEFAULT_SEED, permutations: int = DEFAULT_PERMUTATIONS) -> tuple[dict[str, Any], str]:
    if not generated_at:
        raise ValueError("generated_at is required")
    if permutations < 1:
        raise ValueError("permutations must be at least 1")
    contract = _decode(p543c_raw, "p543c")
    _, grouped, candidate_data = _normalise_contract(contract)
    source_artifacts = [_metadata(p543c_path, p543c_raw, "primary_p543c_contract")]
    for path, role, raw in optional_sources or []:
        _decode(raw, role)
        source_artifacts.append(_metadata(path, raw, role))
    baselines = permutation_baselines(grouped, seed, permutations)
    candidate_results: list[dict[str, Any]] = []
    for candidate_id in sorted(grouped):
        rows = grouped[candidate_id]
        metric = _outcome_metric(rows)
        split = chronological_split(rows)
        classification = classify_candidate(metric, split, baselines[candidate_id])
        candidate = candidate_data[candidate_id]
        candidate_results.append({"candidate_id": candidate_id, "candidate_label": rows[0]["candidate_label"], "lottery": candidate["lottery"], "strategy_id": candidate["strategy_id"], "bet_index": candidate["bet_index"], "metrics": metric, "chronological_split": split, "permutation_baseline": baselines[candidate_id], "classification": classification})
    summary = Counter(item["classification"]["label"] for item in candidate_results)
    packet = {
        "classification": "descriptive_contract_validation_pilot_only",
        "generated_at": generated_at,
        "source_artifacts": source_artifacts,
        "contract_shape": {"candidate_count": len(candidate_data), "row_count": sum(len(rows) for rows in grouped.values()), "rows_per_candidate": {candidate_id: len(rows) for candidate_id, rows in sorted(grouped.items())}, "chronological_fields_used": ["draw_order", "draw_id", "draw_date"], "candidate_linkage": "candidate_id = strategy_id:bet_index"},
        "pilot_config": {"seed": seed, "permutations": permutations, "stability_delta_threshold": STABILITY_DELTA_THRESHOLD, "above_baseline_percentile_threshold": ABOVE_BASELINE_PERCENTILE, "below_baseline_percentile_threshold": BELOW_BASELINE_PERCENTILE},
        "safety": {"descriptive_only": True, "pilot_only": True, "true_oos_performed": False, "future_prediction_claim": False, "betting_advice": False, "production_or_go_live_readiness": False, "selection_bias_remains": True, "database_opened": False, "database_written": False},
        "candidate_results": candidate_results,
        "classification_summary": {label: summary.get(label, 0) for label in ("pilot_above_permutation_baseline", "pilot_near_permutation_baseline", "pilot_below_permutation_baseline", "chronologically_unstable", "insufficient_or_unsupported")},
        "blockers": [],
        "limitations": ["Candidate selection was pre-filtered before this pilot, so selection bias remains.", "The rows are committed historical contract rows, not a prospectively held-out protocol.", "Chronological half splits are descriptive and are not true out-of-sample evaluation.", "Outcome shuffling is a fixed-seed descriptive baseline, not proof or a statistical significance claim.", "No result establishes usefulness for betting, future performance, production readiness, or go-live readiness."],
        "recommended_next_task": "Define and authorize a prospective, leakage-controlled evaluation protocol before any true out-of-sample claim.",
    }
    return packet, markdown_report(packet)


def markdown_report(packet: Mapping[str, Any]) -> str:
    lines = [
        "# P543D — Contract Validation Pilot",
        "",
        "> Descriptive-only and pilot-only: this report is not betting advice and makes no future prediction.",
        "> No true OOS evaluation was performed; chronological splits are descriptive only.",
        "> This does not establish production or go-live readiness. The selected candidates were pre-filtered, so selection bias remains.",
        "",
        "## Sources",
        "",
        "| role | artifact | SHA256 | bytes |",
        "|---|---|---|---:|",
    ]
    for source in packet["source_artifacts"]:
        lines.append(f"| {source['role']} | `{source['path']}` | `{source['sha256']}` | {source['bytes']} |")
    shape = packet["contract_shape"]
    lines.extend(["", "## Contract Schema", "", f"- candidates: {shape['candidate_count']}", f"- rows: {shape['row_count']}", f"- linkage: {shape['candidate_linkage']}", f"- chronological fields: {', '.join(shape['chronological_fields_used'])}", "", "## Per-candidate Metrics", "", "| candidate | rows | draw range | ≥1 hit rate | average hits | hit distribution |", "|---|---:|---|---:|---:|---|"])
    for item in packet["candidate_results"]:
        metric = item["metrics"]
        draw_range = metric["draw_range"]
        distribution = ", ".join(f"{key}:{value}" for key, value in metric["hit_count_distribution"].items())
        lines.append(f"| `{item['candidate_id']}` | {metric['row_count']} | {draw_range['first']}–{draw_range['last']} | {metric['at_least_one_hit_rate']:.3f} | {metric['average_hit_count']:.3f} | {distribution} |")
    lines.extend(["", "## Chronological Split (not true OOS)", "", "| candidate | first half | second half | absolute delta | label |", "|---|---:|---:|---:|---|"])
    for item in packet["candidate_results"]:
        split = item["chronological_split"]
        lines.append(f"| `{item['candidate_id']}` | {split['first_half_at_least_one_hit_rate']:.3f} | {split['second_half_at_least_one_hit_rate']:.3f} | {split['absolute_delta']:.3f} | `{split['stability_label']}` |")
    lines.extend(["", "## Fixed-seed Permutation Baseline", "", "| candidate | observed ≥1 rate | baseline mean | empirical percentile | at/above count |", "|---|---:|---:|---:|---:|"])
    for item in packet["candidate_results"]:
        rate = item["permutation_baseline"]["at_least_one_hit_rate"]
        lines.append(f"| `{item['candidate_id']}` | {rate['observed']:.3f} | {rate['distribution']['mean']:.3f} | {rate['empirical_percentile']:.3f} | {rate['observed_at_or_above_permutation_count']} |")
    lines.extend(["", "## Pilot Classification", "", "| candidate | classification | evidence |", "|---|---|---|"])
    for item in packet["candidate_results"]:
        evidence = item["classification"]["evidence"]
        lines.append(f"| `{item['candidate_id']}` | `{item['classification']['label']}` | split={evidence['stability_label']}; percentile={evidence['empirical_percentile']}; rows={evidence['row_count']} |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in packet["limitations"])
    lines.extend(["", "## Recommended Next Task", "", packet["recommended_next_task"], ""])
    return "\n".join(lines)


def generate(p543c_json: Path, output_json: Path, output_md: Path, generated_at: str, *, p543b_json: Path | None = None, p543a_json: Path | None = None, p542a_json: Path | None = None, seed: int = DEFAULT_SEED, permutations: int = DEFAULT_PERMUTATIONS) -> tuple[dict[str, Any], str]:
    optional: list[tuple[str, str, bytes]] = []
    for path, role in ((p543b_json, "optional_p543b"), (p543a_json, "optional_p543a"), (p542a_json, "optional_p542a")):
        if path is not None:
            optional.append((str(path), role, path.read_bytes()))
    packet, markdown = build_pilot_from_bytes(p543c_json.read_bytes(), str(p543c_json), generated_at, optional_sources=optional, seed=seed, permutations=permutations)
    output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")
    return packet, markdown


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p543c-json", required=True)
    parser.add_argument("--p543b-json")
    parser.add_argument("--p543a-json")
    parser.add_argument("--p542a-json")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    generate(Path(args.p543c_json), Path(args.output_json), Path(args.output_md), args.generated_at, p543b_json=Path(args.p543b_json) if args.p543b_json else None, p543a_json=Path(args.p543a_json) if args.p543a_json else None, p542a_json=Path(args.p542a_json) if args.p542a_json else None, seed=args.seed, permutations=args.permutations)


if __name__ == "__main__":
    main()
