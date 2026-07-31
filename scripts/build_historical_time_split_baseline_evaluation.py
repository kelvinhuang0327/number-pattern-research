#!/usr/bin/env python3
"""Build the P221-A historical time-split baseline evaluation from fixed artifacts only."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_CSV = REPORT_DIR / "p218a_historical_sample_feature_table.csv"
SOURCE_JSON = REPORT_DIR / "p218a_historical_sample_feature_table.json"
SOURCE_MD = REPORT_DIR / "p218a_historical_sample_feature_table.md"
SOURCE_P219_JSON = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.json"
SOURCE_P220_JSON = REPORT_DIR / "p220a_historical_baseline_error_dashboard.json"
OUT_CSV = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.csv"
OUT_JSON = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.json"
OUT_MD = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.md"
TASK_NAME = "P221-A Historical Time-Split Baseline Evaluation Prototype"
STATUS = "PASS_P218A_P219A_P220A_ARTIFACT_ONLY_HISTORICAL_TIME_SPLIT_BASELINE_EVALUATION_PROTOTYPE"
DISCLAIMER = "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P221-A HISTORICAL TIME-SPLIT BASELINE EVALUATION PROTOTYPE PASS"
FAILURE_BANNER = "P221-A HISTORICAL TIME-SPLIT BASELINE EVALUATION PROTOTYPE FAIL"
TARGET_COLUMN = "event_category"
SOURCE_REQUIRED_HASHES = {
    "report/p218a_historical_sample_feature_table.csv": "d3d00176e3e40163c8d38a60019e204b0d37ef7efb745b638e797578f197b507",
    "report/p218a_historical_sample_feature_table.json": "60fde1062e935c7f5d37a693611e6433d765b905fb7e1a499c513bf728e39844",
    "report/p218a_historical_sample_feature_table.md": "28aa4b4d17bade86fe9c51990cf1798640967ea3a6e7388a81e54d485efbf016",
    "report/p219a_historical_feature_baseline_evaluation.json": "dc4ac6fce1e0f8f92a87a3bd3ab74d6aa60d8ea4b8205b3c8e822a1cbb370298",
    "report/p220a_historical_baseline_error_dashboard.json": "abd4a2540ea2109ee77f30a4a836f1800e3218cc003ed92fda0e1043c8f695f3",
}
PROHIBITED_CLAIMS = [
    "No future prediction claim.",
    "No live prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No edge, ROI, EV, Kelly, or CLV claim.",
]
OUTPUT_COLUMNS = [
    "split_id",
    "train_date_range",
    "eval_date",
    "source_row_id",
    "pitch_type",
    "actual_event_category",
    "baseline_a_prediction",
    "baseline_a_correct",
    "baseline_b_prediction",
    "baseline_b_correct",
    "baseline_b_prediction_source",
]
BASELINE_A_KEY = "baseline_a_global_majority"
BASELINE_B_KEY = "baseline_b_pitch_type_majority_with_global_fallback"


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
    if value in (None, ""):
        return None
    return int(value)


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
        return f"{value:.6f}"
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sorted_counts(values: list[str]) -> list[tuple[str, int]]:
    return sorted(Counter(values).items(), key=lambda item: (-item[1], item[0]))


def _distribution(values: list[str]) -> list[dict[str, Any]]:
    ranked = _sorted_counts(values)
    total = len(values)
    return [
        {
            "value": label,
            "count": count,
            "fraction": _fraction(count, total),
        }
        for label, count in ranked
    ]


def _confusion_matrix(
    actual_values: list[str],
    predicted_values: list[str],
    labels: list[str],
) -> dict[str, dict[str, int]]:
    matrix = {
        actual_label: {predicted_label: 0 for predicted_label in labels}
        for actual_label in labels
    }
    for actual_value, predicted_value in zip(actual_values, predicted_values):
        matrix[actual_value][predicted_value] += 1
    return matrix


def _render_markdown_matrix(labels: list[str], matrix: dict[str, dict[str, int]]) -> list[str]:
    lines = [
        "| actual \\ predicted | " + " | ".join(labels) + " |",
        "| " + " | ".join(["---"] * (len(labels) + 1)) + " |",
    ]
    for actual_label in labels:
        row = [actual_label]
        row.extend(str(matrix[actual_label][predicted_label]) for predicted_label in labels)
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _validate_source_hashes(source_artifacts: list[str]) -> dict[str, str]:
    observed_hashes = {artifact: _sha256(ROOT / artifact) for artifact in source_artifacts}
    for artifact, required_hash in SOURCE_REQUIRED_HASHES.items():
        observed_hash = observed_hashes.get(artifact)
        if observed_hash != required_hash:
            raise ValueError(
                f"P221A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {artifact} expected {required_hash} got {observed_hash}"
            )
    return observed_hashes


def _majority_label(values: list[str]) -> str:
    ranked = _sorted_counts(values)
    if not ranked:
        raise ValueError("P221A_STOPPED_PRE_IMPLEMENTATION_WITH_ROOT_CAUSE: missing training values")
    return ranked[0][0]


def _date_range_label(dates: list[str]) -> str:
    if not dates:
        return ""
    return f"{dates[0]} to {dates[-1]}"


def _pitch_type_resolution_table(
    train_rows: list[dict[str, str | None]],
    global_majority: str,
) -> list[dict[str, Any]]:
    grouped_targets: dict[str, list[str]] = defaultdict(list)
    for row in train_rows:
        grouped_targets[row.get("pitch_type") or "missing"].append(row[TARGET_COLUMN] or "missing")

    table: list[dict[str, Any]] = []
    for pitch_type in sorted(grouped_targets):
        values = grouped_targets[pitch_type]
        ranked = _sorted_counts(values)
        top_count = ranked[0][1]
        top_labels = [label for label, count in ranked if count == top_count]
        uses_fallback = len(top_labels) != 1
        table.append(
            {
                "pitch_type": pitch_type,
                "support": len(values),
                "event_category_distribution": [
                    {"value": label, "count": count, "fraction": _fraction(count, len(values))}
                    for label, count in ranked
                ],
                "resolved_prediction": global_majority if uses_fallback else ranked[0][0],
                "prediction_source": "global_fallback_due_to_tie" if uses_fallback else "pitch_type_majority",
                "fallback_to_global_majority": uses_fallback,
            }
        )
    return table


def _resolve_baseline_b_prediction(
    pitch_type: str,
    pitch_type_table: dict[str, dict[str, Any]],
    global_majority: str,
) -> tuple[str, str]:
    resolution = pitch_type_table.get(pitch_type)
    if resolution is None:
        return global_majority, "global_fallback_missing_pitch_type"
    return resolution["resolved_prediction"], resolution["prediction_source"]


def _baseline_metrics(
    records: list[dict[str, Any]],
    labels: list[str],
    prediction_key: str,
    correct_key: str,
) -> dict[str, Any]:
    actual_values = [record["actual_event_category"] for record in records]
    predicted_values = [record[prediction_key] for record in records]
    row_count = len(records)
    correct_count = sum(1 for record in records if record[correct_key])
    return {
        "row_count": row_count,
        "correct_count": correct_count,
        "accuracy": _fraction(correct_count, row_count),
        "coverage_rows": row_count,
        "coverage_fraction": _fraction(row_count, row_count),
        "predicted_class_distribution": _distribution(predicted_values),
        "confusion_matrix": _confusion_matrix(actual_values, predicted_values, labels),
    }


def _baseline_b_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    direct_rows = [
        record for record in records if record["baseline_b_prediction_source"] == "pitch_type_majority"
    ]
    tie_fallback_rows = [
        record for record in records if record["baseline_b_prediction_source"] == "global_fallback_due_to_tie"
    ]
    missing_pitch_type_rows = [
        record
        for record in records
        if record["baseline_b_prediction_source"] == "global_fallback_missing_pitch_type"
    ]
    fallback_rows = tie_fallback_rows + missing_pitch_type_rows
    total_rows = len(records)
    return {
        "direct_pitch_type_majority": {
            "rows": len(direct_rows),
            "fraction": _fraction(len(direct_rows), total_rows),
            "correct_rows": sum(1 for record in direct_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in direct_rows if record["baseline_b_correct"]),
                len(direct_rows),
            ),
        },
        "global_fallback_due_to_tie": {
            "rows": len(tie_fallback_rows),
            "fraction": _fraction(len(tie_fallback_rows), total_rows),
            "correct_rows": sum(1 for record in tie_fallback_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in tie_fallback_rows if record["baseline_b_correct"]),
                len(tie_fallback_rows),
            ),
        },
        "global_fallback_missing_pitch_type": {
            "rows": len(missing_pitch_type_rows),
            "fraction": _fraction(len(missing_pitch_type_rows), total_rows),
            "correct_rows": sum(1 for record in missing_pitch_type_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in missing_pitch_type_rows if record["baseline_b_correct"]),
                len(missing_pitch_type_rows),
            ),
        },
        "all_global_fallback": {
            "rows": len(fallback_rows),
            "fraction": _fraction(len(fallback_rows), total_rows),
            "correct_rows": sum(1 for record in fallback_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in fallback_rows if record["baseline_b_correct"]),
                len(fallback_rows),
            ),
        },
    }


def build_payload() -> dict[str, Any]:
    source_artifacts = [
        _artifact_label(SOURCE_CSV),
        _artifact_label(SOURCE_JSON),
        _artifact_label(SOURCE_MD),
        _artifact_label(SOURCE_P219_JSON),
        _artifact_label(SOURCE_P220_JSON),
    ]
    source_hashes = _validate_source_hashes(source_artifacts)
    fieldnames, source_rows = _load_csv_rows(SOURCE_CSV)
    source_json = _load_json(SOURCE_JSON)
    p219_json = _load_json(SOURCE_P219_JSON)
    p220_json = _load_json(SOURCE_P220_JSON)
    source_markdown = SOURCE_MD.read_text(encoding="utf-8")

    date_order = sorted({row["game_date"] or "" for row in source_rows})
    if len(date_order) < 2:
        raise ValueError("P221A_STOPPED_PRE_IMPLEMENTATION_WITH_ROOT_CAUSE: insufficient historical dates")

    full_target_values = [row[TARGET_COLUMN] or "missing" for row in source_rows]
    label_order = [entry["value"] for entry in _distribution(full_target_values)]
    split_definitions: list[dict[str, Any]] = []
    per_split_metrics: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for split_index, eval_date in enumerate(date_order[1:], start=1):
        train_rows = [row for row in source_rows if (row["game_date"] or "") < eval_date]
        eval_rows = [row for row in source_rows if row["game_date"] == eval_date]
        train_dates = sorted({row["game_date"] or "" for row in train_rows})
        train_targets = [row[TARGET_COLUMN] or "missing" for row in train_rows]
        global_majority = _majority_label(train_targets)
        pitch_type_rows = _pitch_type_resolution_table(train_rows, global_majority)
        pitch_type_table = {row["pitch_type"]: row for row in pitch_type_rows}
        split_records: list[dict[str, Any]] = []

        for row in eval_rows:
            pitch_type = row.get("pitch_type") or "missing"
            actual = row.get(TARGET_COLUMN) or "missing"
            baseline_b_prediction, baseline_b_source = _resolve_baseline_b_prediction(
                pitch_type,
                pitch_type_table,
                global_majority,
            )
            split_record = {
                "split_id": split_index,
                "train_date_range": _date_range_label(train_dates),
                "eval_date": eval_date,
                "source_row_id": _parse_int(row.get("source_row_id")),
                "pitch_type": pitch_type,
                "actual_event_category": actual,
                "baseline_a_prediction": global_majority,
                "baseline_a_correct": global_majority == actual,
                "baseline_b_prediction": baseline_b_prediction,
                "baseline_b_correct": baseline_b_prediction == actual,
                "baseline_b_prediction_source": baseline_b_source,
            }
            split_records.append(split_record)

        split_baseline_a = _baseline_metrics(
            split_records,
            label_order,
            "baseline_a_prediction",
            "baseline_a_correct",
        )
        split_baseline_b = _baseline_metrics(
            split_records,
            label_order,
            "baseline_b_prediction",
            "baseline_b_correct",
        )
        split_coverage = _baseline_b_coverage(split_records)

        split_definitions.append(
            {
                "split_id": split_index,
                "train_dates": train_dates,
                "train_date_range": _date_range_label(train_dates),
                "eval_date": eval_date,
                "train_row_count": len(train_rows),
                "eval_row_count": len(eval_rows),
                "train_class_distribution": _distribution(train_targets),
                "baseline_a_global_majority_prediction": global_majority,
                "baseline_b_pitch_type_resolution_table": pitch_type_rows,
            }
        )
        per_split_metrics.append(
            {
                "split_id": split_index,
                "eval_date": eval_date,
                "baseline_a_global_majority": split_baseline_a,
                "baseline_b_pitch_type_majority_with_global_fallback": split_baseline_b,
                "baseline_b_coverage": split_coverage,
                "comparison": {
                    "accuracy_delta_b_minus_a": round(
                        split_baseline_b["accuracy"] - split_baseline_a["accuracy"],
                        6,
                    ),
                    "correct_row_delta_b_minus_a": split_baseline_b["correct_count"]
                    - split_baseline_a["correct_count"],
                },
            }
        )
        records.extend(split_records)

    overall_baseline_a = _baseline_metrics(
        records,
        label_order,
        "baseline_a_prediction",
        "baseline_a_correct",
    )
    overall_baseline_b = _baseline_metrics(
        records,
        label_order,
        "baseline_b_prediction",
        "baseline_b_correct",
    )
    overall_coverage = _baseline_b_coverage(records)

    limitations = [
        "Evaluation reads only the fixed committed P218, P219, and P220 artifacts and does not refresh any upstream source.",
        "Each holdout split trains only on earlier historical game_date rows and evaluates later historical rows from the same bounded P218 sample.",
        "Baseline A uses the prior-date global majority event_category with deterministic alphabetical tie-break on tied counts.",
        "Baseline B uses the prior-date pitch_type majority event_category and falls back to the prior-date global majority when the pitch_type majority is tied or missing from training history.",
        "This is a historical-only evaluation prototype for pipeline shape demonstration and does not train a production model.",
        "Results are bounded historical holdout metrics on a 24-row artifact snapshot and must not be interpreted as future predictive ability.",
        "No remote data fetch, no pybaseball call, no DB write, and no production activation occur in this task.",
    ]

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_summary": {
            "p218_feature_row_count": source_json.get("row_count"),
            "p218_feature_column_count": source_json.get("column_count"),
            "p218_markdown_mentions_disclaimer": "Not live predictions, not betting advice." in source_markdown,
            "p219_status": p219_json.get("status"),
            "p220_status": p220_json.get("status"),
        },
        "source_lineage": {
            "p218_task": source_json.get("task"),
            "p219_task": p219_json.get("task"),
            "p220_task": p220_json.get("task"),
        },
        "source_row_count": len(source_rows),
        "source_column_count": len(fieldnames),
        "row_count": len(records),
        "column_count": len(OUTPUT_COLUMNS),
        "output_columns": OUTPUT_COLUMNS,
        "target_definition": {
            "name": TARGET_COLUMN,
            "description": "Historical categorical label copied from the fixed P218 feature table event_category column.",
            "class_support": _distribution(full_target_values),
            "label_order": label_order,
        },
        "evaluation_method": [
            "Read only the fixed committed P218 CSV/JSON/Markdown artifacts plus the fixed P219/P220 JSON artifacts for lineage and compatibility context.",
            "Sort the P218 feature-table rows by game_date and evaluate each historical date after the first observed date as a holdout split.",
            "For each split, train Baseline A on earlier dates only and predict the prior-date global majority event_category using deterministic alphabetical tie-break on ties.",
            "For each split, train Baseline B on earlier dates only and predict the prior-date pitch_type majority event_category, falling back to the prior-date global majority when the pitch_type majority is tied or absent from training history.",
            "Report deterministic historical-only per-split and overall holdout accuracy, confusion matrices, and baseline-B fallback coverage.",
        ],
        "time_split_definitions": split_definitions,
        "per_split_metrics": per_split_metrics,
        "overall_holdout_metrics": {
            BASELINE_A_KEY: overall_baseline_a,
            BASELINE_B_KEY: overall_baseline_b,
            "baseline_b_coverage": overall_coverage,
            "comparison": {
                "accuracy_delta_b_minus_a": round(
                    overall_baseline_b["accuracy"] - overall_baseline_a["accuracy"],
                    6,
                ),
                "correct_row_delta_b_minus_a": overall_baseline_b["correct_count"]
                - overall_baseline_a["correct_count"],
            },
        },
        "confusion_matrices": {
            BASELINE_A_KEY: overall_baseline_a["confusion_matrix"],
            BASELINE_B_KEY: overall_baseline_b["confusion_matrix"],
        },
        "coverage": {
            "baseline_b_pitch_type_majority_with_global_fallback": overall_coverage,
        },
        "limitations": limitations,
        "prohibited_claims": PROHIBITED_CLAIMS,
        "records": records,
    }


def write_csv(payload: dict[str, Any]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for record in payload["records"]:
            writer.writerow({column: record[column] for column in OUTPUT_COLUMNS})


def write_json(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P221-A Historical Time-Split Baseline Evaluation Prototype",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Source row count: {payload['source_row_count']}",
        f"- Evaluation row count: {payload['row_count']}",
        f"- Source column count: {payload['source_column_count']}",
        f"- Evaluation column count: {payload['column_count']}",
        f"- Split count: {len(payload['time_split_definitions'])}",
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
            "## Evaluation Method",
            "",
        ]
    )
    for item in payload["evaluation_method"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Time Split Definitions",
            "",
            "| split_id | train_date_range | eval_date | train_row_count | eval_row_count | baseline_a_global_majority_prediction |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for split in payload["time_split_definitions"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(split["split_id"]),
                    _md_cell(split["train_date_range"]),
                    _md_cell(split["eval_date"]),
                    _md_cell(split["train_row_count"]),
                    _md_cell(split["eval_row_count"]),
                    _md_cell(split["baseline_a_global_majority_prediction"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Overall Holdout Metrics",
            "",
            "| baseline | accuracy | correct_count | row_count | coverage_rows | coverage_fraction |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for key in [BASELINE_A_KEY, BASELINE_B_KEY]:
        metric = payload["overall_holdout_metrics"][key]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(key),
                    _md_cell(metric["accuracy"]),
                    _md_cell(metric["correct_count"]),
                    _md_cell(metric["row_count"]),
                    _md_cell(metric["coverage_rows"]),
                    _md_cell(metric["coverage_fraction"]),
                ]
            )
            + " |"
        )

    coverage = payload["overall_holdout_metrics"]["baseline_b_coverage"]
    lines.extend(
        [
            "",
            "## Baseline B Coverage",
            "",
            "| coverage_type | rows | fraction | correct_rows | accuracy |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for key in [
        "direct_pitch_type_majority",
        "global_fallback_due_to_tie",
        "global_fallback_missing_pitch_type",
        "all_global_fallback",
    ]:
        summary = coverage[key]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(key),
                    _md_cell(summary["rows"]),
                    _md_cell(summary["fraction"]),
                    _md_cell(summary["correct_rows"]),
                    _md_cell(summary["accuracy"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Per-Split Metrics",
            "",
            "| split_id | eval_date | baseline_a_accuracy | baseline_b_accuracy | direct_pitch_type_rows | fallback_rows | accuracy_delta_b_minus_a |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for split_metric in payload["per_split_metrics"]:
        coverage_summary = split_metric["baseline_b_coverage"]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(split_metric["split_id"]),
                    _md_cell(split_metric["eval_date"]),
                    _md_cell(split_metric[BASELINE_A_KEY]["accuracy"]),
                    _md_cell(split_metric[BASELINE_B_KEY]["accuracy"]),
                    _md_cell(coverage_summary["direct_pitch_type_majority"]["rows"]),
                    _md_cell(coverage_summary["all_global_fallback"]["rows"]),
                    _md_cell(split_metric["comparison"]["accuracy_delta_b_minus_a"]),
                ]
            )
            + " |"
        )

    for split in payload["time_split_definitions"]:
        lines.extend(
            [
                "",
                f"## Split {split['split_id']} Pitch-Type Resolution",
                "",
                f"Eval date: `{split['eval_date']}`",
                "",
                "| pitch_type | support | resolved_prediction | prediction_source | fallback_to_global_majority |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in split["baseline_b_pitch_type_resolution_table"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(row["pitch_type"]),
                        _md_cell(row["support"]),
                        _md_cell(row["resolved_prediction"]),
                        _md_cell(row["prediction_source"]),
                        _md_cell(row["fallback_to_global_majority"]),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Overall Confusion Matrices",
            "",
            f"### {BASELINE_A_KEY}",
            "",
        ]
    )
    lines.extend(
        _render_markdown_matrix(
            payload["target_definition"]["label_order"],
            payload["confusion_matrices"][BASELINE_A_KEY],
        )
    )
    lines.extend(
        [
            "",
            f"### {BASELINE_B_KEY}",
            "",
        ]
    )
    lines.extend(
        _render_markdown_matrix(
            payload["target_definition"]["label_order"],
            payload["confusion_matrices"][BASELINE_B_KEY],
        )
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
            "## Evaluation Rows",
            "",
            "| split_id | train_date_range | eval_date | source_row_id | pitch_type | actual_event_category | baseline_a_prediction | baseline_a_correct | baseline_b_prediction | baseline_b_correct | baseline_b_prediction_source |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in payload["records"]:
        lines.append(
            "| " + " | ".join(_md_cell(record[column]) for column in OUTPUT_COLUMNS) + " |"
        )

    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def write_markdown(payload: dict[str, Any]) -> None:
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    try:
        payload = build_payload()
        write_csv(payload)
        write_json(payload)
        write_markdown(payload)
    except Exception as exc:
        print(FAILURE_BANNER)
        print(str(exc))
        return 1

    print(SUCCESS_BANNER)
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
