#!/usr/bin/env python3
"""Build the P222-A historical time-split error dashboard from fixed artifacts only."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_CSV = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.csv"
SOURCE_JSON = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.json"
SOURCE_MD = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.md"
SOURCE_P220_JSON = REPORT_DIR / "p220a_historical_baseline_error_dashboard.json"
OUT_HTML = REPORT_DIR / "p222a_historical_time_split_error_dashboard.html"
OUT_JSON = REPORT_DIR / "p222a_historical_time_split_error_dashboard.json"
TASK_NAME = "P222-A Historical Time-Split Error Analysis Dashboard"
STATUS = "PASS_P221A_P220A_ARTIFACT_ONLY_HISTORICAL_TIME_SPLIT_ERROR_ANALYSIS_DASHBOARD"
DISCLAIMER = "Historical time-split error analysis dashboard only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P222-A HISTORICAL TIME-SPLIT ERROR ANALYSIS DASHBOARD PASS"
FAILURE_BANNER = "P222-A HISTORICAL TIME-SPLIT ERROR ANALYSIS DASHBOARD FAIL"
SOURCE_REQUIRED_HASHES = {
    "report/p221a_historical_time_split_baseline_evaluation.csv": "2d17483e66a11069806f4b0f49bcd905f1d427ab56425edef9f24aba8844d3ae",
    "report/p221a_historical_time_split_baseline_evaluation.json": "0ccec8bc6b01c5bbdd8a3c082cbbc161d4a5fc0f39cc3cfe51948199e7528982",
    "report/p221a_historical_time_split_baseline_evaluation.md": "f31c00dbd65a86ae0224cbd147c1e2c39c45a58e13791f702266c54cb5b05617",
    "report/p220a_historical_baseline_error_dashboard.json": "abd4a2540ea2109ee77f30a4a836f1800e3218cc003ed92fda0e1043c8f695f3",
}
PROHIBITED_CLAIMS = [
    "No future prediction claim.",
    "No live prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No edge, ROI, EV, Kelly, or CLV claim.",
]
BASELINE_A_KEY = "baseline_a_global_majority"
BASELINE_B_KEY = "baseline_b_pitch_type_majority_with_global_fallback"
ROW_COLUMNS = [
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_label(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _normalize_cell(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _parse_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _fraction(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str | None]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {column: _normalize_cell(value) for column, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def _validate_source_hashes(source_artifacts: list[str]) -> dict[str, str]:
    observed_hashes = {artifact: _sha256(ROOT / artifact) for artifact in source_artifacts}
    for artifact, required_hash in SOURCE_REQUIRED_HASHES.items():
        observed_hash = observed_hashes.get(artifact)
        if observed_hash != required_hash:
            raise ValueError(
                f"P222A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {artifact} expected {required_hash} got {observed_hash}"
            )
    return observed_hashes


def _distribution(values: list[str]) -> list[dict[str, Any]]:
    counts = Counter(values)
    total = len(values)
    return [
        {"value": label, "count": count, "fraction": _fraction(count, total)}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
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


def _typed_records(source_rows: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in source_rows:
        records.append(
            {
                "split_id": _parse_int(row.get("split_id")),
                "train_date_range": row.get("train_date_range"),
                "eval_date": row.get("eval_date"),
                "source_row_id": _parse_int(row.get("source_row_id")),
                "pitch_type": row.get("pitch_type"),
                "actual_event_category": row.get("actual_event_category"),
                "baseline_a_prediction": row.get("baseline_a_prediction"),
                "baseline_a_correct": _parse_bool(row.get("baseline_a_correct")),
                "baseline_b_prediction": row.get("baseline_b_prediction"),
                "baseline_b_correct": _parse_bool(row.get("baseline_b_correct")),
                "baseline_b_prediction_source": row.get("baseline_b_prediction_source"),
            }
        )
    return records


def _baseline_metrics(
    labels: list[str],
    records: list[dict[str, Any]],
    predicted_key: str,
    correct_key: str,
) -> dict[str, Any]:
    actual_values = [record["actual_event_category"] for record in records]
    predicted_values = [record[predicted_key] for record in records]
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
    tie_rows = [
        record
        for record in records
        if record["baseline_b_prediction_source"] == "global_fallback_due_to_tie"
    ]
    missing_rows = [
        record
        for record in records
        if record["baseline_b_prediction_source"] == "global_fallback_missing_pitch_type"
    ]
    fallback_rows = tie_rows + missing_rows
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
            "rows": len(tie_rows),
            "fraction": _fraction(len(tie_rows), total_rows),
            "correct_rows": sum(1 for record in tie_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in tie_rows if record["baseline_b_correct"]),
                len(tie_rows),
            ),
        },
        "global_fallback_missing_pitch_type": {
            "rows": len(missing_rows),
            "fraction": _fraction(len(missing_rows), total_rows),
            "correct_rows": sum(1 for record in missing_rows if record["baseline_b_correct"]),
            "accuracy": _fraction(
                sum(1 for record in missing_rows if record["baseline_b_correct"]),
                len(missing_rows),
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


def _comparison(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> dict[str, Any]:
    return {
        "accuracy_delta_b_minus_a": round(metrics_b["accuracy"] - metrics_a["accuracy"], 6),
        "correct_row_delta_b_minus_a": metrics_b["correct_count"] - metrics_a["correct_count"],
    }


def _error_row_view(record: dict[str, Any]) -> dict[str, Any]:
    return {column: record[column] for column in ROW_COLUMNS}


def _prediction_source_breakdown(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["baseline_b_prediction_source"]].append(record)

    breakdown: dict[str, Any] = {}
    for source in sorted(grouped):
        group = sorted(grouped[source], key=lambda item: (item["split_id"], item["source_row_id"]))
        breakdown[source] = {
            "rows": len(group),
            "fraction": _fraction(len(group), len(records)),
            "correct_rows": sum(1 for item in group if item["baseline_b_correct"]),
            "accuracy": _fraction(sum(1 for item in group if item["baseline_b_correct"]), len(group)),
            "split_ids": sorted({item["split_id"] for item in group}),
            "eval_dates": sorted({item["eval_date"] for item in group}),
            "predicted_event_category_distribution": _distribution(
                [item["baseline_b_prediction"] for item in group]
            ),
            "actual_event_category_distribution": _distribution(
                [item["actual_event_category"] for item in group]
            ),
        }

    fallback_rows = [
        record
        for record in records
        if record["baseline_b_prediction_source"] != "pitch_type_majority"
    ]
    breakdown["all_global_fallback"] = {
        "rows": len(fallback_rows),
        "fraction": _fraction(len(fallback_rows), len(records)),
        "correct_rows": sum(1 for item in fallback_rows if item["baseline_b_correct"]),
        "accuracy": _fraction(
            sum(1 for item in fallback_rows if item["baseline_b_correct"]),
            len(fallback_rows),
        ),
        "split_ids": sorted({item["split_id"] for item in fallback_rows}),
        "eval_dates": sorted({item["eval_date"] for item in fallback_rows}),
        "predicted_event_category_distribution": _distribution(
            [item["baseline_b_prediction"] for item in fallback_rows]
        ),
        "actual_event_category_distribution": _distribution(
            [item["actual_event_category"] for item in fallback_rows]
        ),
    }
    return breakdown


def _split_metrics(
    labels: list[str],
    records: list[dict[str, Any]],
    split_definitions: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["split_id"]].append(record)

    items: list[dict[str, Any]] = []
    for split_id in sorted(grouped):
        group = sorted(grouped[split_id], key=lambda item: item["source_row_id"])
        metrics_a = _baseline_metrics(labels, group, "baseline_a_prediction", "baseline_a_correct")
        metrics_b = _baseline_metrics(labels, group, "baseline_b_prediction", "baseline_b_correct")
        coverage = _baseline_b_coverage(group)
        split_definition = split_definitions[split_id]
        items.append(
            {
                "split_id": split_id,
                "eval_date": split_definition["eval_date"],
                "train_date_range": split_definition["train_date_range"],
                "train_row_count": split_definition["train_row_count"],
                "eval_row_count": split_definition["eval_row_count"],
                BASELINE_A_KEY: metrics_a,
                BASELINE_B_KEY: metrics_b,
                "coverage": coverage,
                "comparison": _comparison(metrics_a, metrics_b),
            }
        )
    return items


def _date_metrics(labels: list[str], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["eval_date"]].append(record)

    items: list[dict[str, Any]] = []
    for eval_date in sorted(grouped):
        group = sorted(grouped[eval_date], key=lambda item: (item["split_id"], item["source_row_id"]))
        metrics_a = _baseline_metrics(labels, group, "baseline_a_prediction", "baseline_a_correct")
        metrics_b = _baseline_metrics(labels, group, "baseline_b_prediction", "baseline_b_correct")
        coverage = _baseline_b_coverage(group)
        items.append(
            {
                "eval_date": eval_date,
                "split_ids": sorted({item["split_id"] for item in group}),
                "row_count": len(group),
                BASELINE_A_KEY: metrics_a,
                BASELINE_B_KEY: metrics_b,
                "coverage": coverage,
                "comparison": _comparison(metrics_a, metrics_b),
            }
        )
    return items


def _source_summary(
    source_json_payload: dict[str, Any],
    source_md_text: str,
    source_columns: list[str],
    records: list[dict[str, Any]],
    p220_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "p221_task": source_json_payload.get("task"),
        "p221_status": source_json_payload.get("status"),
        "p221_row_count": source_json_payload.get("row_count"),
        "p221_column_count": source_json_payload.get("column_count"),
        "p221_markdown_mentions_disclaimer": source_json_payload.get("disclaimer") in source_md_text,
        "observed_csv_row_count": len(records),
        "observed_csv_column_count": len(source_columns),
        "p220_task": p220_payload.get("task"),
        "p220_status": p220_payload.get("status"),
    }


def _validate_source_consistency(
    source_json_payload: dict[str, Any],
    source_columns: list[str],
    records: list[dict[str, Any]],
    confusion_matrices: dict[str, Any],
    overall_a: dict[str, Any],
    overall_b: dict[str, Any],
    coverage: dict[str, Any],
    per_split_metrics: list[dict[str, Any]],
) -> None:
    if source_json_payload.get("disclaimer") != source_json_payload.get("historical_only_disclaimer"):
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 disclaimer fields differ")
    if source_json_payload.get("row_count") != len(records):
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 row count does not match CSV")
    if source_json_payload.get("column_count") != len(source_columns):
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 column count does not match CSV")
    if source_json_payload.get("output_columns") != source_columns:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 output columns do not match CSV")
    if source_json_payload.get("confusion_matrices") != confusion_matrices:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 confusion matrices do not match CSV")

    overall_holdout = source_json_payload.get("overall_holdout_metrics", {})
    if overall_holdout.get(BASELINE_A_KEY) != overall_a:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 baseline A metrics do not match CSV")
    if overall_holdout.get(BASELINE_B_KEY) != overall_b:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 baseline B metrics do not match CSV")
    if overall_holdout.get("baseline_b_coverage") != coverage:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 baseline B coverage does not match CSV")
    if source_json_payload.get("coverage", {}).get(BASELINE_B_KEY) != coverage:
        raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 coverage section does not match CSV")

    expected_per_split = source_json_payload.get("per_split_metrics")
    if expected_per_split is not None:
        normalized = []
        for item in per_split_metrics:
            normalized.append(
                {
                    "split_id": item["split_id"],
                    "eval_date": item["eval_date"],
                    BASELINE_A_KEY: item[BASELINE_A_KEY],
                    BASELINE_B_KEY: item[BASELINE_B_KEY],
                    "baseline_b_coverage": item["coverage"],
                    "comparison": item["comparison"],
                }
            )
        if expected_per_split != normalized:
            raise ValueError("P222A_IMPLEMENTED_VALIDATION_FAILED: P221 per-split metrics do not match CSV")


def build_payload() -> dict[str, Any]:
    source_artifacts = [
        _artifact_label(SOURCE_CSV),
        _artifact_label(SOURCE_JSON),
        _artifact_label(SOURCE_MD),
        _artifact_label(SOURCE_P220_JSON),
    ]
    source_hashes = _validate_source_hashes(source_artifacts)
    source_columns, source_rows = _load_csv_rows(SOURCE_CSV)
    source_json_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_md_text = SOURCE_MD.read_text(encoding="utf-8")
    p220_payload = json.loads(SOURCE_P220_JSON.read_text(encoding="utf-8"))
    records = _typed_records(source_rows)
    labels = list(source_json_payload.get("target_definition", {}).get("label_order", []))
    if not labels:
        labels = sorted({record["actual_event_category"] for record in records})

    overall_a = _baseline_metrics(labels, records, "baseline_a_prediction", "baseline_a_correct")
    overall_b = _baseline_metrics(labels, records, "baseline_b_prediction", "baseline_b_correct")
    coverage = _baseline_b_coverage(records)
    confusion_matrices = {
        BASELINE_A_KEY: overall_a["confusion_matrix"],
        BASELINE_B_KEY: overall_b["confusion_matrix"],
    }

    split_definitions = {
        item["split_id"]: item
        for item in source_json_payload.get("time_split_definitions", [])
    }
    per_split_metrics = _split_metrics(labels, records, split_definitions)
    per_date_metrics = _date_metrics(labels, records)

    _validate_source_consistency(
        source_json_payload=source_json_payload,
        source_columns=source_columns,
        records=records,
        confusion_matrices=confusion_matrices,
        overall_a=overall_a,
        overall_b=overall_b,
        coverage=coverage,
        per_split_metrics=per_split_metrics,
    )

    baseline_a_incorrect = [_error_row_view(record) for record in records if not record["baseline_a_correct"]]
    baseline_b_incorrect = [_error_row_view(record) for record in records if not record["baseline_b_correct"]]
    any_incorrect = [
        _error_row_view(record)
        for record in records
        if not record["baseline_a_correct"] or not record["baseline_b_correct"]
    ]
    baseline_b_only_improvements = [
        _error_row_view(record)
        for record in records
        if not record["baseline_a_correct"] and record["baseline_b_correct"]
    ]

    overall_metrics = {
        "split_count": len(per_split_metrics),
        "evaluated_rows": len(records),
        BASELINE_A_KEY: overall_a,
        BASELINE_B_KEY: overall_b,
        "comparison": _comparison(overall_a, overall_b),
        "vs_p220_in_sample": {
            BASELINE_A_KEY: {
                "p220_accuracy": p220_payload["metrics"][BASELINE_A_KEY]["accuracy"],
                "p222_time_split_accuracy": overall_a["accuracy"],
                "accuracy_delta_time_split_minus_p220": round(
                    overall_a["accuracy"] - p220_payload["metrics"][BASELINE_A_KEY]["accuracy"],
                    6,
                ),
            },
            BASELINE_B_KEY: {
                "p220_accuracy": p220_payload["metrics"][BASELINE_B_KEY]["accuracy"],
                "p222_time_split_accuracy": overall_b["accuracy"],
                "accuracy_delta_time_split_minus_p220": round(
                    overall_b["accuracy"] - p220_payload["metrics"][BASELINE_B_KEY]["accuracy"],
                    6,
                ),
            },
        },
    }

    limitations = [
        "This dashboard reads only the fixed P221-A CSV/JSON/Markdown artifacts plus the fixed P220-A JSON artifact.",
        "All metrics are historical holdout metrics on the bounded 16-row P221 evaluation snapshot.",
        "The dashboard analyzes deterministic baseline errors only and does not train or score a production model.",
        "No remote data fetch, no pybaseball call, no DB write, and no production activation occur in this task.",
    ]
    for item in source_json_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)
    for item in p220_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_summary": _source_summary(
            source_json_payload=source_json_payload,
            source_md_text=source_md_text,
            source_columns=source_columns,
            records=records,
            p220_payload=p220_payload,
        ),
        "overall_metrics": overall_metrics,
        "per_split_metrics": per_split_metrics,
        "per_date_metrics": per_date_metrics,
        "confusion_matrices": confusion_matrices,
        "coverage": {
            BASELINE_A_KEY: {"rows": len(records), "fraction": 1.0},
            BASELINE_B_KEY: {"rows": len(records), "fraction": 1.0},
            BASELINE_B_KEY + "_prediction_source_coverage": coverage,
        },
        "prediction_source_breakdown": _prediction_source_breakdown(records),
        "error_rows": {
            "baseline_a_incorrect": baseline_a_incorrect,
            "baseline_b_incorrect": baseline_b_incorrect,
            "any_incorrect": any_incorrect,
            "baseline_b_only_improvements": baseline_b_only_improvements,
        },
        "limitations": limitations,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "label_order": labels,
        "split_definitions": source_json_payload.get("time_split_definitions", []),
    }


def _html_cell(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    if value is None:
        return ""
    return html.escape(str(value))


def _render_html_table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_html_cell(cell)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _render_metric_summary(payload: dict[str, Any]) -> str:
    metrics = payload["overall_metrics"]
    baseline_a = metrics[BASELINE_A_KEY]
    baseline_b = metrics[BASELINE_B_KEY]
    comparison = metrics["comparison"]
    rows = [
        ["Baseline A", baseline_a["accuracy"], baseline_a["correct_count"], baseline_a["row_count"]],
        ["Baseline B", baseline_b["accuracy"], baseline_b["correct_count"], baseline_b["row_count"]],
        ["B minus A", comparison["accuracy_delta_b_minus_a"], comparison["correct_row_delta_b_minus_a"], ""],
    ]
    return _render_html_table(["Metric", "Accuracy", "Correct Rows", "Evaluated Rows"], rows)


def _render_split_table(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        coverage = item["coverage"]
        rows.append(
            [
                item["split_id"],
                item["train_date_range"],
                item["eval_date"],
                item["train_row_count"],
                item["eval_row_count"],
                item[BASELINE_A_KEY]["accuracy"],
                item[BASELINE_B_KEY]["accuracy"],
                coverage["direct_pitch_type_majority"]["rows"],
                coverage["all_global_fallback"]["rows"],
                item["comparison"]["accuracy_delta_b_minus_a"],
            ]
        )
    return _render_html_table(
        [
            "Split",
            "Train Date Range",
            "Eval Date",
            "Train Rows",
            "Eval Rows",
            "Baseline A Accuracy",
            "Baseline B Accuracy",
            "Direct Rows",
            "Fallback Rows",
            "B minus A",
        ],
        rows,
    )


def _render_date_table(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        coverage = item["coverage"]
        rows.append(
            [
                item["eval_date"],
                ", ".join(str(value) for value in item["split_ids"]),
                item["row_count"],
                item[BASELINE_A_KEY]["accuracy"],
                item[BASELINE_B_KEY]["accuracy"],
                coverage["direct_pitch_type_majority"]["rows"],
                coverage["all_global_fallback"]["rows"],
            ]
        )
    return _render_html_table(
        [
            "Eval Date",
            "Split IDs",
            "Rows",
            "Baseline A Accuracy",
            "Baseline B Accuracy",
            "Direct Rows",
            "Fallback Rows",
        ],
        rows,
    )


def _render_coverage_table(coverage: dict[str, Any]) -> str:
    rows = []
    for key, value in coverage.items():
        rows.append([key, value["rows"], value["fraction"], value["correct_rows"], value["accuracy"]])
    return _render_html_table(["Coverage Type", "Rows", "Fraction", "Correct Rows", "Accuracy"], rows)


def _render_prediction_source_breakdown(items: dict[str, Any]) -> str:
    rows = []
    for key in sorted(items):
        value = items[key]
        rows.append(
            [
                key,
                value["rows"],
                value["fraction"],
                value["correct_rows"],
                value["accuracy"],
                ", ".join(str(part) for part in value["split_ids"]),
                ", ".join(value["eval_dates"]),
            ]
        )
    return _render_html_table(
        ["Prediction Source", "Rows", "Fraction", "Correct Rows", "Accuracy", "Split IDs", "Eval Dates"],
        rows,
    )


def _render_matrix_table(labels: list[str], matrix: dict[str, dict[str, int]]) -> str:
    headers = ["Actual \\ Predicted"] + labels
    rows = []
    for actual_label in labels:
        rows.append([actual_label] + [matrix[actual_label][predicted_label] for predicted_label in labels])
    return _render_html_table(headers, rows)


def _render_error_rows_table(rows: list[dict[str, Any]]) -> str:
    return _render_html_table(ROW_COLUMNS, [[row[column] for column in ROW_COLUMNS] for row in rows])


def _render_split_resolution_tables(split_definitions: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for item in split_definitions:
        rows = []
        for resolution in item.get("baseline_b_pitch_type_resolution_table", []):
            rows.append(
                [
                    resolution["pitch_type"],
                    resolution["support"],
                    resolution["resolved_prediction"],
                    resolution["prediction_source"],
                    resolution["fallback_to_global_majority"],
                ]
            )
        sections.append(
            "\n".join(
                [
                    "<section>",
                    f"  <h3>Split {item['split_id']} Pitch-Type Resolution</h3>",
                    f"  <p><strong>Eval date:</strong> {_html_cell(item['eval_date'])}</p>",
                    f"  {_render_html_table(['Pitch Type', 'Support', 'Resolved Prediction', 'Prediction Source', 'Fallback'], rows)}",
                    "</section>",
                ]
            )
        )
    return "\n".join(sections)


def render_html(payload: dict[str, Any]) -> str:
    source_rows = [[artifact, payload["source_hashes"][artifact]] for artifact in payload["source_artifacts"]]
    vs_p220 = payload["overall_metrics"]["vs_p220_in_sample"]
    vs_p220_rows = [
        [
            "Baseline A",
            vs_p220[BASELINE_A_KEY]["p220_accuracy"],
            vs_p220[BASELINE_A_KEY]["p222_time_split_accuracy"],
            vs_p220[BASELINE_A_KEY]["accuracy_delta_time_split_minus_p220"],
        ],
        [
            "Baseline B",
            vs_p220[BASELINE_B_KEY]["p220_accuracy"],
            vs_p220[BASELINE_B_KEY]["p222_time_split_accuracy"],
            vs_p220[BASELINE_B_KEY]["accuracy_delta_time_split_minus_p220"],
        ],
    ]
    limitations_list = "".join(f"<li>{html.escape(item)}</li>" for item in payload["limitations"])
    prohibited_list = "".join(f"<li>{html.escape(item)}</li>" for item in payload["prohibited_claims"])

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html.escape(TASK_NAME)}</title>",
            "  <style>",
            "    :root { color-scheme: light; --bg: #f3efe7; --panel: #fffdf8; --ink: #1e2931; --line: #d6cab9; --accent: #7a2f2f; --accent-soft: #f2dfd6; --muted: #59636f; }",
            "    * { box-sizing: border-box; }",
            "    body { margin: 0; padding: 24px; font-family: Georgia, 'Times New Roman', serif; background: radial-gradient(circle at top, #fbf8f1 0%, #efe8dc 48%, #e6ddcf 100%); color: var(--ink); }",
            "    main { max-width: 1480px; margin: 0 auto; }",
            "    section { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px; margin-bottom: 18px; box-shadow: 0 10px 28px rgba(79, 61, 41, 0.06); }",
            "    .hero { background: linear-gradient(135deg, #f7e5db 0%, #fffaf4 100%); border-left: 6px solid var(--accent); }",
            "    .eyebrow { color: var(--accent); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }",
            "    .grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }",
            "    h1, h2, h3 { margin: 0 0 12px; line-height: 1.15; }",
            "    p, li { line-height: 1.5; }",
            "    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }",
            "    th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }",
            "    th { background: #f6efe4; }",
            "    .muted { color: var(--muted); }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            '<section class="hero">',
            '  <div class="eyebrow">Historical Only</div>',
            f"  <h1>{html.escape(TASK_NAME)}</h1>",
            f"  <p><strong>Status:</strong> {html.escape(payload['status'])}</p>",
            f"  <p>{html.escape(payload['disclaimer'])}</p>",
            "  <p class=\"muted\">Historical-only holdout error analysis. No live predictions, no betting advice, no production claims.</p>",
            "</section>",
            "<section>",
            "  <h2>Source Artifacts and Hashes</h2>",
            f"  {_render_html_table(['Artifact', 'SHA256'], source_rows)}",
            "</section>",
            '<div class="grid">',
            "<section>",
            "  <h2>Overall Metrics</h2>",
            f"  {_render_metric_summary(payload)}",
            "</section>",
            "<section>",
            "  <h2>P220 In-Sample vs P222 Time-Split</h2>",
            f"  {_render_html_table(['Baseline', 'P220 Accuracy', 'P222 Accuracy', 'Delta'], vs_p220_rows)}",
            "</section>",
            "</div>",
            "<section>",
            "  <h2>Per-Split Metrics</h2>",
            f"  {_render_split_table(payload['per_split_metrics'])}",
            "</section>",
            "<section>",
            "  <h2>Per-Date Metrics</h2>",
            f"  {_render_date_table(payload['per_date_metrics'])}",
            "</section>",
            '<div class="grid">',
            "<section>",
            "  <h2>Coverage Summary</h2>",
            f"  {_render_coverage_table(payload['coverage'][BASELINE_B_KEY + '_prediction_source_coverage'])}",
            "</section>",
            "<section>",
            "  <h2>Prediction Source Breakdown</h2>",
            f"  {_render_prediction_source_breakdown(payload['prediction_source_breakdown'])}",
            "</section>",
            "</div>",
            '<div class="grid">',
            "<section>",
            "  <h2>Baseline A Confusion Matrix</h2>",
            f"  {_render_matrix_table(payload['label_order'], payload['confusion_matrices'][BASELINE_A_KEY])}",
            "</section>",
            "<section>",
            "  <h2>Baseline B Confusion Matrix</h2>",
            f"  {_render_matrix_table(payload['label_order'], payload['confusion_matrices'][BASELINE_B_KEY])}",
            "</section>",
            "</div>",
            _render_split_resolution_tables(payload["split_definitions"]),
            "<section>",
            "  <h2>Baseline B Improvement Rows</h2>",
            f"  {_render_error_rows_table(payload['error_rows']['baseline_b_only_improvements'])}",
            "</section>",
            "<section>",
            "  <h2>Baseline B Incorrect Rows</h2>",
            f"  {_render_error_rows_table(payload['error_rows']['baseline_b_incorrect'])}",
            "</section>",
            "<section>",
            "  <h2>All Historical Mistake Rows</h2>",
            f"  {_render_error_rows_table(payload['error_rows']['any_incorrect'])}",
            "</section>",
            "<section>",
            "  <h2>Limitations</h2>",
            f"  <ul>{limitations_list}</ul>",
            "</section>",
            "<section>",
            "  <h2>Prohibited Claims</h2>",
            f"  <ul>{prohibited_list}</ul>",
            f"  <p><strong>Disclaimer:</strong> {html.escape(payload['disclaimer'])}</p>",
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def write_outputs(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(payload) + "\n", encoding="utf-8")


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
