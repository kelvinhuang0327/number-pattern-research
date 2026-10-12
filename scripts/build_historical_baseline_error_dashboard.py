#!/usr/bin/env python3
"""Build the P220-A historical baseline error analysis dashboard from P219-A artifacts only."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_CSV = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.csv"
SOURCE_JSON = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.json"
SOURCE_MD = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.md"
OUT_HTML = REPORT_DIR / "p220a_historical_baseline_error_dashboard.html"
OUT_JSON = REPORT_DIR / "p220a_historical_baseline_error_dashboard.json"
TASK_NAME = "P220-A Historical Baseline Error Analysis Dashboard"
STATUS = "PASS_P219A_ARTIFACT_ONLY_HISTORICAL_BASELINE_ERROR_ANALYSIS_DASHBOARD"
DISCLAIMER = "Historical baseline error analysis dashboard only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P220-A HISTORICAL BASELINE ERROR ANALYSIS DASHBOARD PASS"
FAILURE_BANNER = "P220-A HISTORICAL BASELINE ERROR ANALYSIS DASHBOARD FAIL"
SOURCE_REQUIRED_HASHES = {
    "report/p219a_historical_feature_baseline_evaluation.csv": "4c447f63e827d6fad4a4fdd6f2f36142cc601d6f622aceeca3a31f21a22075e7",
    "report/p219a_historical_feature_baseline_evaluation.json": "dc4ac6fce1e0f8f92a87a3bd3ab74d6aa60d8ea4b8205b3c8e822a1cbb370298",
    "report/p219a_historical_feature_baseline_evaluation.md": "2ba77c284d094a1e34770a1377cd47b25ef076f09c6b8187465ebcd0b970a1c9",
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
    "source_row_id",
    "game_date",
    "game_pk",
    "pitcher",
    "pitch_type",
    "actual_event_category",
    "baseline_a_global_prediction",
    "baseline_a_correct",
    "baseline_b_pitch_type_prediction",
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
                f"P220A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {artifact} expected {required_hash} got {observed_hash}"
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
        record = {
            "source_row_id": _parse_int(row.get("source_row_id")),
            "game_date": row.get("game_date"),
            "game_pk": _parse_int(row.get("game_pk")),
            "pitcher": row.get("pitcher"),
            "pitch_type": row.get("pitch_type"),
            "actual_event_category": row.get("actual_event_category"),
            "baseline_a_global_prediction": row.get("baseline_a_global_prediction"),
            "baseline_a_correct": _parse_bool(row.get("baseline_a_correct")),
            "baseline_b_pitch_type_prediction": row.get("baseline_b_pitch_type_prediction"),
            "baseline_b_correct": _parse_bool(row.get("baseline_b_correct")),
            "baseline_b_prediction_source": row.get("baseline_b_prediction_source"),
        }
        records.append(record)
    return records


def _per_class_errors(
    labels: list[str],
    records: list[dict[str, Any]],
    predicted_key: str,
) -> list[dict[str, Any]]:
    actual_values = [record["actual_event_category"] for record in records]
    predicted_values = [record[predicted_key] for record in records]
    confusion = _confusion_matrix(actual_values, predicted_values, labels)
    predicted_counts = Counter(predicted_values)

    rows: list[dict[str, Any]] = []
    for label in labels:
        support = sum(1 for value in actual_values if value == label)
        correct_count = confusion[label][label]
        predicted_count = predicted_counts.get(label, 0)
        false_negative_count = support - correct_count
        false_positive_count = predicted_count - correct_count
        rows.append(
            {
                "class_label": label,
                "support": support,
                "correct_count": correct_count,
                "misclassified_count": false_negative_count,
                "predicted_count": predicted_count,
                "false_positive_count": false_positive_count,
                "recall": _fraction(correct_count, support),
                "precision": _fraction(correct_count, predicted_count),
            }
        )
    return rows


def _baseline_metrics(
    labels: list[str],
    records: list[dict[str, Any]],
    predicted_key: str,
    correct_key: str,
    coverage_selector: str | None = None,
) -> dict[str, Any]:
    actual_values = [record["actual_event_category"] for record in records]
    predicted_values = [record[predicted_key] for record in records]
    row_count = len(records)
    correct_count = sum(1 for record in records if record[correct_key])
    coverage_rows = row_count
    if coverage_selector is not None:
        coverage_rows = sum(
            1 for record in records if record["baseline_b_prediction_source"] == coverage_selector
        )

    return {
        "row_count": row_count,
        "correct_count": correct_count,
        "accuracy": _fraction(correct_count, row_count),
        "coverage_rows": coverage_rows,
        "coverage_fraction": _fraction(coverage_rows, row_count),
        "predicted_class_distribution": _distribution(predicted_values),
        "confusion_matrix": _confusion_matrix(actual_values, predicted_values, labels),
        "per_class_errors": _per_class_errors(labels, records, predicted_key),
    }


def _pitch_type_resolution_summary(
    pitch_type_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    global_fallback_prediction: str | None,
) -> dict[str, Any]:
    direct_rows = [record for record in records if record["baseline_b_prediction_source"] == "pitch_type_majority"]
    fallback_rows = [
        record for record in records if record["baseline_b_prediction_source"] == "global_fallback_due_to_tie"
    ]
    direct_pitch_types = [row["pitch_type"] for row in pitch_type_rows if not row["fallback_to_global_majority"]]
    fallback_pitch_types = [row["pitch_type"] for row in pitch_type_rows if row["fallback_to_global_majority"]]
    return {
        "global_fallback_prediction": global_fallback_prediction,
        "pitch_type_table": pitch_type_rows,
        "direct_pitch_type_count": len(direct_pitch_types),
        "fallback_pitch_type_count": len(fallback_pitch_types),
        "direct_pitch_types": direct_pitch_types,
        "fallback_pitch_types": fallback_pitch_types,
        "direct_coverage_rows": len(direct_rows),
        "direct_coverage_fraction": _fraction(len(direct_rows), len(records)),
        "direct_correct_rows": sum(1 for record in direct_rows if record["baseline_b_correct"]),
        "direct_accuracy": _fraction(
            sum(1 for record in direct_rows if record["baseline_b_correct"]),
            len(direct_rows),
        ),
        "fallback_rows": len(fallback_rows),
        "fallback_fraction": _fraction(len(fallback_rows), len(records)),
        "fallback_correct_rows": sum(1 for record in fallback_rows if record["baseline_b_correct"]),
        "fallback_accuracy": _fraction(
            sum(1 for record in fallback_rows if record["baseline_b_correct"]),
            len(fallback_rows),
        ),
    }


def _error_row_view(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_row_id": record["source_row_id"],
        "game_date": record["game_date"],
        "game_pk": record["game_pk"],
        "pitcher": record["pitcher"],
        "pitch_type": record["pitch_type"],
        "actual_event_category": record["actual_event_category"],
        "baseline_a_global_prediction": record["baseline_a_global_prediction"],
        "baseline_a_correct": record["baseline_a_correct"],
        "baseline_b_pitch_type_prediction": record["baseline_b_pitch_type_prediction"],
        "baseline_b_correct": record["baseline_b_correct"],
        "baseline_b_prediction_source": record["baseline_b_prediction_source"],
    }


def _source_summary(
    source_json_payload: dict[str, Any],
    source_md_text: str,
    source_columns: list[str],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "p219_task": source_json_payload.get("task"),
        "p219_status": source_json_payload.get("status"),
        "p219_row_count": source_json_payload.get("row_count"),
        "p219_column_count": source_json_payload.get("column_count"),
        "p219_output_columns": source_json_payload.get("output_columns"),
        "p219_markdown_mentions_disclaimer": source_json_payload.get("disclaimer") in source_md_text,
        "observed_csv_column_count": len(source_columns),
        "observed_csv_row_count": len(records),
    }


def _validate_source_consistency(
    source_json_payload: dict[str, Any],
    records: list[dict[str, Any]],
    class_support: list[dict[str, Any]],
    metrics_a: dict[str, Any],
    metrics_b: dict[str, Any],
) -> None:
    if source_json_payload.get("disclaimer") != source_json_payload.get("historical_only_disclaimer"):
        raise ValueError("P220A_IMPLEMENTED_VALIDATION_FAILED: P219 disclaimer fields differ")
    if source_json_payload.get("row_count") != len(records):
        raise ValueError("P220A_IMPLEMENTED_VALIDATION_FAILED: P219 row count does not match CSV")
    if source_json_payload.get("target_definition", {}).get("class_support") != class_support:
        raise ValueError("P220A_IMPLEMENTED_VALIDATION_FAILED: P219 class support does not match CSV")
    if source_json_payload.get("metric_summary", {}).get(BASELINE_A_KEY) != {
        key: metrics_a[key]
        for key in (
            "accuracy",
            "confusion_matrix",
            "correct_count",
            "coverage_fraction",
            "coverage_rows",
            "predicted_class_distribution",
            "row_count",
        )
    }:
        raise ValueError("P220A_IMPLEMENTED_VALIDATION_FAILED: P219 baseline A metrics do not match CSV")
    if source_json_payload.get("metric_summary", {}).get(BASELINE_B_KEY) != {
        key: metrics_b[key]
        for key in (
            "accuracy",
            "confusion_matrix",
            "correct_count",
            "coverage_fraction",
            "coverage_rows",
            "predicted_class_distribution",
            "row_count",
        )
    }:
        raise ValueError("P220A_IMPLEMENTED_VALIDATION_FAILED: P219 baseline B metrics do not match CSV")


def build_payload() -> dict[str, Any]:
    source_artifacts = [
        _artifact_label(SOURCE_CSV),
        _artifact_label(SOURCE_JSON),
        _artifact_label(SOURCE_MD),
    ]
    source_hashes = _validate_source_hashes(source_artifacts)
    source_columns, source_rows = _load_csv_rows(SOURCE_CSV)
    source_json_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_md_text = SOURCE_MD.read_text(encoding="utf-8")
    records = _typed_records(source_rows)
    labels = list(source_json_payload.get("target_definition", {}).get("label_order", []))
    if not labels:
        labels = sorted({record["actual_event_category"] for record in records})

    class_support = _distribution([record["actual_event_category"] for record in records])
    metrics_a = _baseline_metrics(
        labels=labels,
        records=records,
        predicted_key="baseline_a_global_prediction",
        correct_key="baseline_a_correct",
    )
    metrics_b = _baseline_metrics(
        labels=labels,
        records=records,
        predicted_key="baseline_b_pitch_type_prediction",
        correct_key="baseline_b_correct",
        coverage_selector="pitch_type_majority",
    )
    _validate_source_consistency(source_json_payload, records, class_support, metrics_a, metrics_b)

    baseline_b_definition = source_json_payload["baseline_definitions"][BASELINE_B_KEY]
    pitch_type_rows = baseline_b_definition["pitch_type_resolution_table"]
    pitch_type_resolution = _pitch_type_resolution_summary(
        pitch_type_rows,
        records,
        baseline_b_definition.get("global_fallback_prediction"),
    )

    baseline_a_incorrect = [_error_row_view(record) for record in records if not record["baseline_a_correct"]]
    baseline_b_incorrect = [_error_row_view(record) for record in records if not record["baseline_b_correct"]]
    any_incorrect = [
        _error_row_view(record)
        for record in records
        if not record["baseline_a_correct"] or not record["baseline_b_correct"]
    ]

    limitations = [
        "This dashboard reads only the fixed P219-A CSV, JSON, and Markdown artifacts and does not refresh upstream data.",
        "All metrics are historical and in-sample on the bounded 24-row P219 evaluation snapshot.",
        "The dashboard analyzes deterministic baseline mistakes only and does not train or score a production model.",
    ]
    for item in source_json_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)

    confusion_matrices = {
        BASELINE_A_KEY: metrics_a["confusion_matrix"],
        BASELINE_B_KEY: metrics_b["confusion_matrix"],
    }

    metrics = {
        BASELINE_A_KEY: metrics_a,
        BASELINE_B_KEY: {
            **metrics_b,
            "direct_coverage": {
                "rows": pitch_type_resolution["direct_coverage_rows"],
                "fraction": pitch_type_resolution["direct_coverage_fraction"],
                "correct_rows": pitch_type_resolution["direct_correct_rows"],
                "accuracy": pitch_type_resolution["direct_accuracy"],
            },
            "fallback_coverage": {
                "rows": pitch_type_resolution["fallback_rows"],
                "fraction": pitch_type_resolution["fallback_fraction"],
                "correct_rows": pitch_type_resolution["fallback_correct_rows"],
                "accuracy": pitch_type_resolution["fallback_accuracy"],
            },
        },
        "comparison": {
            "accuracy_delta_b_minus_a": round(metrics_b["accuracy"] - metrics_a["accuracy"], 6),
            "correct_row_delta_b_minus_a": metrics_b["correct_count"] - metrics_a["correct_count"],
        },
    }

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_summary": _source_summary(source_json_payload, source_md_text, source_columns, records),
        "metrics": metrics,
        "class_support": class_support,
        "confusion_matrices": confusion_matrices,
        "pitch_type_resolution": pitch_type_resolution,
        "error_rows": {
            "baseline_a_incorrect": baseline_a_incorrect,
            "baseline_b_incorrect": baseline_b_incorrect,
            "any_incorrect": any_incorrect,
        },
        "limitations": limitations,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "label_order": labels,
        "row_count": len(records),
        "baseline_definitions": source_json_payload.get("baseline_definitions"),
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
    baseline_a = payload["metrics"][BASELINE_A_KEY]
    baseline_b = payload["metrics"][BASELINE_B_KEY]
    comparison = payload["metrics"]["comparison"]
    rows = [
        [
            "Baseline A",
            baseline_a["accuracy"],
            baseline_a["correct_count"],
            baseline_a["row_count"],
            baseline_a["coverage_rows"],
            baseline_a["coverage_fraction"],
        ],
        [
            "Baseline B",
            baseline_b["accuracy"],
            baseline_b["correct_count"],
            baseline_b["row_count"],
            baseline_b["coverage_rows"],
            baseline_b["coverage_fraction"],
        ],
        [
            "B minus A",
            comparison["accuracy_delta_b_minus_a"],
            comparison["correct_row_delta_b_minus_a"],
            "",
            "",
            "",
        ],
    ]
    return _render_html_table(
        ["Baseline", "Accuracy", "Correct Rows", "Row Count", "Coverage Rows", "Coverage Fraction"],
        rows,
    )


def _render_distribution_table(items: list[dict[str, Any]], value_key: str = "value") -> str:
    rows = [[item[value_key], item["count"], item["fraction"]] for item in items]
    return _render_html_table(["Class", "Count", "Fraction"], rows)


def _render_matrix_table(labels: list[str], matrix: dict[str, dict[str, int]]) -> str:
    headers = ["Actual \\ Predicted"] + labels
    rows = []
    for actual_label in labels:
        rows.append([actual_label] + [matrix[actual_label][predicted_label] for predicted_label in labels])
    return _render_html_table(headers, rows)


def _render_per_class_error_table(items: list[dict[str, Any]]) -> str:
    rows = [
        [
            item["class_label"],
            item["support"],
            item["correct_count"],
            item["misclassified_count"],
            item["predicted_count"],
            item["false_positive_count"],
            item["recall"],
            item["precision"],
        ]
        for item in items
    ]
    return _render_html_table(
        [
            "Class",
            "Support",
            "Correct",
            "Misclassified",
            "Predicted",
            "False Positive",
            "Recall",
            "Precision",
        ],
        rows,
    )


def _render_pitch_type_resolution_table(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        distribution = ", ".join(
            f"{part['value']} ({part['count']}, {part['fraction']:.6f})"
            for part in item["event_category_distribution"]
        )
        rows.append(
            [
                item["pitch_type"],
                item["support"],
                item["resolved_prediction"],
                item["prediction_source"],
                item["fallback_to_global_majority"],
                distribution,
            ]
        )
    return _render_html_table(
        [
            "Pitch Type",
            "Support",
            "Resolved Prediction",
            "Prediction Source",
            "Fallback",
            "Event Distribution",
        ],
        rows,
    )


def _render_error_rows_table(rows: list[dict[str, Any]]) -> str:
    rendered_rows = [
        [row[column] for column in ROW_COLUMNS]
        for row in rows
    ]
    return _render_html_table(ROW_COLUMNS, rendered_rows)


def render_html(payload: dict[str, Any]) -> str:
    baseline_a = payload["metrics"][BASELINE_A_KEY]
    baseline_b = payload["metrics"][BASELINE_B_KEY]
    pitch_type_resolution = payload["pitch_type_resolution"]
    source_rows = [
        [artifact, payload["source_hashes"][artifact]]
        for artifact in payload["source_artifacts"]
    ]
    direct_rows = [
        ["Direct coverage rows", pitch_type_resolution["direct_coverage_rows"]],
        ["Direct coverage fraction", pitch_type_resolution["direct_coverage_fraction"]],
        ["Direct correct rows", pitch_type_resolution["direct_correct_rows"]],
        ["Direct accuracy", pitch_type_resolution["direct_accuracy"]],
        ["Fallback rows", pitch_type_resolution["fallback_rows"]],
        ["Fallback fraction", pitch_type_resolution["fallback_fraction"]],
        ["Fallback correct rows", pitch_type_resolution["fallback_correct_rows"]],
        ["Fallback accuracy", pitch_type_resolution["fallback_accuracy"]],
        ["Direct pitch types", ", ".join(pitch_type_resolution["direct_pitch_types"])],
        ["Fallback pitch types", ", ".join(pitch_type_resolution["fallback_pitch_types"])],
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
            "    :root { color-scheme: light; --bg: #f4f1ea; --panel: #fffdfa; --ink: #1f2933; --muted: #5b6470; --line: #d7d0c4; --accent: #8b3a3a; --accent-soft: #efe0dd; }",
            "    * { box-sizing: border-box; }",
            "    body { margin: 0; padding: 24px; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #f4f1ea 0%, #ece6da 100%); color: var(--ink); }",
            "    main { max-width: 1400px; margin: 0 auto; }",
            "    h1, h2, h3 { margin: 0 0 12px; line-height: 1.15; }",
            "    p, li { line-height: 1.5; }",
            "    section { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; margin: 0 0 18px; box-shadow: 0 8px 30px rgba(59, 45, 25, 0.05); }",
            "    .eyebrow { color: var(--accent); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }",
            "    .banner { background: var(--accent-soft); border-left: 6px solid var(--accent); padding: 14px 16px; border-radius: 12px; margin: 0 0 18px; }",
            "    .grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }",
            "    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }",
            "    th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }",
            "    th { background: #f6eee3; }",
            "    code { background: #f6eee3; padding: 1px 4px; border-radius: 4px; }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            '<section class="banner">',
            '  <div class="eyebrow">Historical Only</div>',
            f"  <h1>{html.escape(TASK_NAME)}</h1>",
            f"  <p><strong>Status:</strong> {html.escape(payload['status'])}</p>",
            f"  <p>{html.escape(payload['disclaimer'])}</p>",
            "</section>",
            "<section>",
            "  <h2>Source Artifacts and Hashes</h2>",
            f"  {_render_html_table(['Artifact', 'SHA256'], source_rows)}",
            "</section>",
            "<section>",
            "  <h2>Baseline Summary</h2>",
            f"  {_render_metric_summary(payload)}",
            "</section>",
            '<div class="grid">',
            "<section>",
            "  <h2>Class Support</h2>",
            f"  {_render_distribution_table(payload['class_support'])}",
            "</section>",
            "<section>",
            "  <h2>Baseline B Direct Coverage</h2>",
            f"  {_render_html_table(['Metric', 'Value'], direct_rows)}",
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
            '<div class="grid">',
            "<section>",
            "  <h2>Baseline A Per-Class Errors</h2>",
            f"  {_render_per_class_error_table(baseline_a['per_class_errors'])}",
            "</section>",
            "<section>",
            "  <h2>Baseline B Per-Class Errors</h2>",
            f"  {_render_per_class_error_table(baseline_b['per_class_errors'])}",
            "</section>",
            "</div>",
            "<section>",
            "  <h2>Pitch-Type Resolution and Fallback</h2>",
            f"  {_render_pitch_type_resolution_table(pitch_type_resolution['pitch_type_table'])}",
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
