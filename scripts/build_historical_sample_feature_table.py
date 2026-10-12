#!/usr/bin/env python3
"""Build the P218-A historical sample feature table prototype from P216/P217 artifacts only."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_CSV = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.csv"
SOURCE_JSON = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.json"
SOURCE_MD = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.md"
SOURCE_DASHBOARD_JSON = REPORT_DIR / "p217a_pybaseball_multidate_quality_dashboard.json"
OUT_CSV = REPORT_DIR / "p218a_historical_sample_feature_table.csv"
OUT_JSON = REPORT_DIR / "p218a_historical_sample_feature_table.json"
OUT_MD = REPORT_DIR / "p218a_historical_sample_feature_table.md"
TASK_NAME = "P218-A Historical Sample Feature Table Prototype"
STATUS = "PASS_P216A_P217A_ARTIFACT_ONLY_HISTORICAL_SAMPLE_FEATURE_TABLE_PROTOTYPE"
DISCLAIMER = "Historical sample feature table prototype only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P218-A HISTORICAL SAMPLE FEATURE TABLE PROTOTYPE PASS"
FAILURE_BANNER = "P218-A HISTORICAL SAMPLE FEATURE TABLE PROTOTYPE FAIL"
PREVIEW_ROW_LIMIT = 5
FEATURE_COLUMNS = [
    "source_row_id",
    "game_date",
    "game_pk",
    "home_team",
    "away_team",
    "inning",
    "inning_topbot",
    "pitcher",
    "batter",
    "pitch_type",
    "event_category",
    "is_in_play",
    "is_strike_like",
    "is_ball_like",
    "release_speed",
    "release_speed_bucket",
    "zone",
    "zone_bucket",
]
IN_PLAY_HIT_EVENTS = {"single", "double", "triple", "home_run"}
IN_PLAY_OUT_EVENTS = {
    "field_out",
    "force_out",
    "double_play",
    "fielders_choice_out",
    "grounded_into_double_play",
    "lineout",
    "flyout",
    "popup",
    "sac_fly",
    "sac_bunt",
    "triple_play",
}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKE_LIKE_DESCRIPTIONS = {
    "called_strike",
    "foul",
    "foul_tip",
    "missed_bunt",
    "swinging_strike",
    "swinging_strike_blocked",
}
BALL_LIKE_DESCRIPTIONS = {
    "ball",
    "blocked_ball",
    "pitchout",
    "automatic_ball",
}
PROHIBITED_CLAIMS = [
    "No future prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No ROI, EV, Kelly, CLV, or edge claim.",
]
DERIVED_FEATURE_DEFINITIONS = {
    "source_row_id": "1-based lineage back to the original P216 CSV row before deterministic resorting.",
    "game_date": "Historical game date copied from the fixed P216 sample pack.",
    "game_pk": "Historical game identifier copied from the fixed P216 sample pack.",
    "home_team": "Home team code copied from the fixed P216 sample pack.",
    "away_team": "Away team code copied from the fixed P216 sample pack.",
    "inning": "Inning number copied from the fixed P216 sample pack.",
    "inning_topbot": "Half-inning label copied from the fixed P216 sample pack.",
    "pitcher": "Pitcher display name derived from the P216 player_name field.",
    "batter": "Batter identifier copied from the fixed P216 batter field because batter name is not present in the source artifact.",
    "pitch_type": "Pitch type code copied from the fixed P216 sample pack.",
    "event_category": "Heuristic categorical label derived only from the P216 events and description fields.",
    "is_in_play": "Boolean flag derived from event/description values that indicate contacted balls in play or resolved in-play outcomes.",
    "is_strike_like": "Boolean flag derived from strike-like descriptions or strikeout events.",
    "is_ball_like": "Boolean flag derived from ball-like descriptions or walk events.",
    "release_speed": "Numeric release_speed value parsed from the P216 CSV text snapshot.",
    "release_speed_bucket": "Velocity bucket derived from release_speed using fixed cutoffs: <85, 85-89.9, 90-94.9, 95+.",
    "zone": "Numeric zone value parsed from the P216 CSV text snapshot.",
    "zone_bucket": "Zone bucket derived from Statcast-style zone numbering: 1-9 in_zone, 11+ out_of_zone, else other_zone.",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_label(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _normalize_cell(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str | None]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {column: _normalize_cell(value) for column, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def _source_sort_key(item: tuple[int, dict[str, str | None]]) -> tuple[Any, ...]:
    source_row_id, row = item
    return (
        row.get("game_date") or "",
        _parse_int(row.get("game_pk")) or 0,
        _parse_int(row.get("inning")) or 0,
        row.get("inning_topbot") or "",
        _parse_int(row.get("at_bat_number")) or 0,
        _parse_int(row.get("pitch_number")) or 0,
        row.get("player_name") or "",
        row.get("pitch_type") or "",
        source_row_id,
    )


def _derive_event_category(events: str | None, description: str | None) -> str:
    if events == "hit_by_pitch" or description == "hit_by_pitch":
        return "hit_by_pitch"
    if events in IN_PLAY_HIT_EVENTS:
        return "in_play_hit"
    if events in IN_PLAY_OUT_EVENTS:
        return "in_play_out"
    if events in STRIKEOUT_EVENTS:
        return "strikeout"
    if description == "hit_into_play":
        return "in_play_unknown"
    if description in STRIKE_LIKE_DESCRIPTIONS:
        return "strike_like"
    if events in WALK_EVENTS or description in BALL_LIKE_DESCRIPTIONS:
        return "ball_like"
    return "other"


def _is_in_play(events: str | None, description: str | None) -> bool:
    return (
        events in IN_PLAY_HIT_EVENTS
        or events in IN_PLAY_OUT_EVENTS
        or description == "hit_into_play"
    )


def _is_strike_like(events: str | None, description: str | None) -> bool:
    return events in STRIKEOUT_EVENTS or description in STRIKE_LIKE_DESCRIPTIONS


def _is_ball_like(events: str | None, description: str | None) -> bool:
    return events in WALK_EVENTS or description in BALL_LIKE_DESCRIPTIONS


def _bucket_release_speed(release_speed: float | None) -> str:
    if release_speed is None:
        return "missing"
    if release_speed < 85.0:
        return "lt_85"
    if release_speed < 90.0:
        return "85_to_89_9"
    if release_speed < 95.0:
        return "90_to_94_9"
    return "95_plus"


def _bucket_zone(zone: int | None) -> str:
    if zone is None:
        return "missing"
    if 1 <= zone <= 9:
        return "in_zone"
    if zone >= 11:
        return "out_of_zone"
    return "other_zone"


def _build_feature_record(source_row_id: int, row: dict[str, str | None]) -> dict[str, Any]:
    events = row.get("events")
    description = row.get("description")
    release_speed = _parse_float(row.get("release_speed"))
    zone = _parse_int(row.get("zone"))
    return {
        "source_row_id": source_row_id,
        "game_date": row.get("game_date"),
        "game_pk": _parse_int(row.get("game_pk")),
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "inning": _parse_int(row.get("inning")),
        "inning_topbot": row.get("inning_topbot"),
        "pitcher": row.get("player_name"),
        "batter": row.get("batter"),
        "pitch_type": row.get("pitch_type"),
        "event_category": _derive_event_category(events, description),
        "is_in_play": _is_in_play(events, description),
        "is_strike_like": _is_strike_like(events, description),
        "is_ball_like": _is_ball_like(events, description),
        "release_speed": release_speed,
        "release_speed_bucket": _bucket_release_speed(release_speed),
        "zone": zone,
        "zone_bucket": _bucket_zone(zone),
    }


def build_payload() -> dict[str, Any]:
    source_md_text = SOURCE_MD.read_text(encoding="utf-8")
    source_json_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    dashboard_payload = json.loads(SOURCE_DASHBOARD_JSON.read_text(encoding="utf-8"))
    source_columns, source_rows = _load_csv_rows(SOURCE_CSV)
    sorted_source_rows = sorted(
        list(enumerate(source_rows, start=1)),
        key=_source_sort_key,
    )
    records = [_build_feature_record(source_row_id, row) for source_row_id, row in sorted_source_rows]
    source_artifacts = [
        _artifact_label(SOURCE_MD),
        _artifact_label(SOURCE_JSON),
        _artifact_label(SOURCE_CSV),
        _artifact_label(SOURCE_DASHBOARD_JSON),
    ]
    source_hashes = {artifact: _sha256(ROOT / artifact) for artifact in source_artifacts}

    limitations = [
        "Feature rows are derived only from the fixed P216/P217 artifact snapshots and do not refresh upstream data.",
        "This prototype is a bounded preprocessing example for one small historical sample and is not a production feature contract.",
        "Several fields remain heuristic because the source artifacts do not include full context such as batter names, count state, or full plate appearance outcomes.",
    ]
    for item in source_json_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)
    for item in dashboard_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_summary": {
            "p216_task": source_json_payload.get("task"),
            "p216_status": source_json_payload.get("status"),
            "p216_disclaimer": source_json_payload.get("disclaimer"),
            "p216_markdown_mentions_disclaimer": source_json_payload.get("disclaimer") in source_md_text,
            "p217_task": dashboard_payload.get("task"),
            "p217_status": dashboard_payload.get("status"),
            "p217_disclaimer": dashboard_payload.get("disclaimer"),
        },
        "source_row_count": len(source_rows),
        "source_column_count": len(source_columns),
        "row_count": len(records),
        "column_count": len(FEATURE_COLUMNS),
        "feature_columns": list(FEATURE_COLUMNS),
        "derived_feature_definitions": DERIVED_FEATURE_DEFINITIONS,
        "sample_preview": records[:PREVIEW_ROW_LIMIT],
        "records": records,
        "feature_distributions": {
            "event_category": _value_distribution(records, "event_category"),
            "release_speed_bucket": _value_distribution(records, "release_speed_bucket"),
            "zone_bucket": _value_distribution(records, "zone_bucket"),
        },
        "limitations": limitations,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
    }


def _value_distribution(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for record in records:
        label = record.get(key)
        counts[str(label)] = counts.get(str(label), 0) + 1
    return [
        {
            "value": value,
            "count": count,
            "fraction": _fraction(count, len(records)),
        }
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P218-A Historical Sample Feature Table Prototype",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Source row count: {payload['source_row_count']}",
        f"- Source column count: {payload['source_column_count']}",
        f"- Feature row count: {payload['row_count']}",
        f"- Feature column count: {payload['column_count']}",
        "",
        "## Source Artifacts",
        "",
        "| Artifact | SHA256 |",
        "| --- | --- |",
    ]
    for artifact in payload["source_artifacts"]:
        lines.append(f"| `{artifact}` | `{payload['source_hashes'][artifact]}` |")

    lines.extend(
        [
            "",
            "## Feature Columns",
            "",
        ]
    )
    for column in payload["feature_columns"]:
        lines.append(f"- `{column}`")

    lines.extend(
        [
            "",
            "## Derived Feature Definitions",
            "",
            "| Feature | Definition |",
            "| --- | --- |",
        ]
    )
    for column in payload["feature_columns"]:
        lines.append(
            f"| `{column}` | {payload['derived_feature_definitions'][column]} |"
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for item in payload["limitations"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Prohibited Claims",
            "",
        ]
    )
    for item in payload["prohibited_claims"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Feature Table",
            "",
            "| " + " | ".join(payload["feature_columns"]) + " |",
            "| " + " | ".join("---" for _ in payload["feature_columns"]) + " |",
        ]
    )
    for record in payload["records"]:
        lines.append(
            "| "
            + " | ".join(_md_cell(record[column]) for column in payload["feature_columns"])
            + " |"
        )

    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def _write_csv(payload: dict[str, Any]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEATURE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(payload["records"])


def _write_json(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(payload)
    OUT_MD.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    _write_json(payload)


def main() -> int:
    try:
        payload = build_payload()
        write_outputs(payload)
    except Exception as exc:
        print(f"{FAILURE_BANNER}: {exc}")
        return 1

    print(SUCCESS_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
