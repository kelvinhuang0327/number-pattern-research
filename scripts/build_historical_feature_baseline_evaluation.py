#!/usr/bin/env python3
"""Build the P219-A historical feature baseline evaluation prototype from P218 artifacts only."""
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
OUT_CSV = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.csv"
OUT_JSON = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.json"
OUT_MD = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.md"
TASK_NAME = "P219-A Historical Feature Baseline Evaluation Prototype"
STATUS = "PASS_P218A_ARTIFACT_ONLY_HISTORICAL_FEATURE_BASELINE_EVALUATION_PROTOTYPE"
DISCLAIMER = "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P219-A HISTORICAL FEATURE BASELINE EVALUATION PROTOTYPE PASS"
FAILURE_BANNER = "P219-A HISTORICAL FEATURE BASELINE EVALUATION PROTOTYPE FAIL"
PREVIEW_ROW_LIMIT = 5
TARGET_COLUMN = "event_category"
SOURCE_REQUIRED_HASHES = {
    "report/p218a_historical_sample_feature_table.csv": "d3d00176e3e40163c8d38a60019e204b0d37ef7efb745b638e797578f197b507",
    "report/p218a_historical_sample_feature_table.json": "60fde1062e935c7f5d37a693611e6433d765b905fb7e1a499c513bf728e39844",
    "report/p218a_historical_sample_feature_table.md": "28aa4b4d17bade86fe9c51990cf1798640967ea3a6e7388a81e54d485efbf016",
}
PROHIBITED_CLAIMS = [
    "No future prediction claim.",
    "No live prediction claim.",
    "No betting advice claim.",
    "No production readiness claim.",
    "No ROI, EV, Kelly, CLV, or edge claim.",
]
OUTPUT_COLUMNS = [
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


def _parse_int(value: str | None) -> int | None:
    if value is None:
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
                f"P219A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {artifact} expected {required_hash} got {observed_hash}"
            )
    return observed_hashes


def _majority_label_or_none(values: list[str]) -> str | None:
    ranked = _sorted_counts(values)
    if not ranked:
        return None
    if len(ranked) == 1:
        return ranked[0][0]
    top_count = ranked[0][1]
    top_labels = [label for label, count in ranked if count == top_count]
    if len(top_labels) != 1:
        return None
    return ranked[0][0]


def _resolved_majority_label(values: list[str]) -> str | None:
    ranked = _sorted_counts(values)
    if not ranked:
        return None
    return ranked[0][0]


def _pitch_type_baseline_table(rows: list[dict[str, str | None]], global_majority: str) -> list[dict[str, Any]]:
    grouped_targets: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped_targets[row.get("pitch_type") or "missing"].append(row[TARGET_COLUMN] or "missing")

    baseline_rows: list[dict[str, Any]] = []
    for pitch_type in sorted(grouped_targets):
        values = grouped_targets[pitch_type]
        ranked = _sorted_counts(values)
        unique_majority = _majority_label_or_none(values)
        uses_fallback = unique_majority is None
        baseline_rows.append(
            {
                "pitch_type": pitch_type,
                "support": len(values),
                "event_category_distribution": [
                    {"value": label, "count": count, "fraction": _fraction(count, len(values))}
                    for label, count in ranked
                ],
                "resolved_prediction": unique_majority or global_majority,
                "prediction_source": "global_fallback_due_to_tie" if uses_fallback else "pitch_type_majority",
                "fallback_to_global_majority": uses_fallback,
            }
        )
    return baseline_rows


def _class_support(rows: list[dict[str, str | None]]) -> list[dict[str, Any]]:
    labels = [row[TARGET_COLUMN] or "missing" for row in rows]
    return _distribution(labels)


def _evaluation_records(
    rows: list[dict[str, str | None]],
    global_majority: str,
    pitch_type_table: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mapping = {row["pitch_type"]: row for row in pitch_type_table}
    records: list[dict[str, Any]] = []
    for row in rows:
        pitch_type = row.get("pitch_type") or "missing"
        actual = row.get(TARGET_COLUMN) or "missing"
        pitch_row = mapping[pitch_type]
        baseline_a_prediction = global_majority
        baseline_b_prediction = pitch_row["resolved_prediction"]
        records.append(
            {
                "source_row_id": _parse_int(row.get("source_row_id")),
                "game_date": row.get("game_date"),
                "game_pk": _parse_int(row.get("game_pk")),
                "pitcher": row.get("pitcher"),
                "pitch_type": pitch_type,
                "actual_event_category": actual,
                "baseline_a_global_prediction": baseline_a_prediction,
                "baseline_a_correct": baseline_a_prediction == actual,
                "baseline_b_pitch_type_prediction": baseline_b_prediction,
                "baseline_b_correct": baseline_b_prediction == actual,
                "baseline_b_prediction_source": pitch_row["prediction_source"],
            }
        )
    return records


def _baseline_metrics(
    records: list[dict[str, Any]],
    labels: list[str],
    predicted_key: str,
    correct_key: str,
    coverage_key: str | None = None,
) -> dict[str, Any]:
    actual_values = [record["actual_event_category"] for record in records]
    predicted_values = [record[predicted_key] for record in records]
    correct_count = sum(1 for record in records if record[correct_key])
    if coverage_key is None:
        coverage_rows = len(records)
    else:
        coverage_rows = sum(1 for record in records if record[coverage_key] == "pitch_type_majority")
    return {
        "row_count": len(records),
        "correct_count": correct_count,
        "accuracy": _fraction(correct_count, len(records)),
        "coverage_rows": coverage_rows,
        "coverage_fraction": _fraction(coverage_rows, len(records)),
        "predicted_class_distribution": _distribution(predicted_values),
        "confusion_matrix": _confusion_matrix(actual_values, predicted_values, labels),
    }


def build_payload() -> dict[str, Any]:
    source_md_text = SOURCE_MD.read_text(encoding="utf-8")
    source_json_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_columns, source_rows = _load_csv_rows(SOURCE_CSV)

    source_artifacts = [
        _artifact_label(SOURCE_CSV),
        _artifact_label(SOURCE_JSON),
        _artifact_label(SOURCE_MD),
    ]
    source_hashes = _validate_source_hashes(source_artifacts)

    if source_json_payload.get("disclaimer") != source_json_payload.get("historical_only_disclaimer"):
        raise ValueError("P218 source disclaimer mismatch between json disclaimer fields")

    target_values = [row.get(TARGET_COLUMN) or "missing" for row in source_rows]
    global_majority = _resolved_majority_label(target_values)
    if global_majority is None:
        raise ValueError("Global majority baseline could not be resolved deterministically")

    pitch_type_table = _pitch_type_baseline_table(source_rows, global_majority)
    records = _evaluation_records(source_rows, global_majority, pitch_type_table)
    label_order = sorted({record["actual_event_category"] for record in records})

    limitations = [
        "This evaluation reuses the fixed 24-row P218 historical feature table only and does not refresh any upstream source.",
        "Baselines are deterministic heuristics for pipeline demonstration only and do not train or score a production model.",
        "Pitch-type baseline falls back to the global majority class whenever a pitch type has no unique within-pitch majority class.",
        "Results are in-sample on a bounded historical snapshot and must not be interpreted as future predictive ability.",
    ]
    for item in source_json_payload.get("limitations", []):
        if item not in limitations:
            limitations.append(item)

    baseline_metrics = {
        "baseline_a_global_majority": _baseline_metrics(
            records=records,
            labels=label_order,
            predicted_key="baseline_a_global_prediction",
            correct_key="baseline_a_correct",
        ),
        "baseline_b_pitch_type_majority_with_global_fallback": _baseline_metrics(
            records=records,
            labels=label_order,
            predicted_key="baseline_b_pitch_type_prediction",
            correct_key="baseline_b_correct",
            coverage_key="baseline_b_prediction_source",
        ),
    }

    return {
        "task": TASK_NAME,
        "status": STATUS,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_artifacts": source_artifacts,
        "source_hashes": source_hashes,
        "source_hash_validation": {
            "required_hashes": dict(SOURCE_REQUIRED_HASHES),
            "match": True,
        },
        "source_summary": {
            "p218_task": source_json_payload.get("task"),
            "p218_status": source_json_payload.get("status"),
            "p218_disclaimer": source_json_payload.get("disclaimer"),
            "p218_markdown_mentions_disclaimer": source_json_payload.get("disclaimer") in source_md_text,
            "p218_row_count": source_json_payload.get("row_count"),
            "p218_column_count": source_json_payload.get("column_count"),
            "p218_feature_columns": source_json_payload.get("feature_columns"),
        },
        "row_count": len(records),
        "column_count": len(OUTPUT_COLUMNS),
        "output_columns": list(OUTPUT_COLUMNS),
        "source_column_count": len(source_columns),
        "target_definition": {
            "name": TARGET_COLUMN,
            "description": "Historical categorical label copied from the fixed P218 feature table event_category column.",
            "class_support": _class_support(source_rows),
            "label_order": label_order,
        },
        "evaluation_method": [
            "Read the fixed P218 CSV/JSON/Markdown artifacts only.",
            "Evaluate the same 24 historical rows already present in the P218 feature table.",
            "Baseline A predicts the global majority event_category for every row.",
            "Baseline B predicts the within-pitch_type majority event_category only when that majority is unique; otherwise it falls back to the global majority event_category.",
            "Report deterministic in-sample accuracy, per-class support, confusion matrices, and pitch-type baseline coverage.",
        ],
        "baseline_definitions": {
            "baseline_a_global_majority": {
                "prediction_rule": "Predict the most frequent event_category across all P218 rows for every row.",
                "resolved_prediction": global_majority,
            },
            "baseline_b_pitch_type_majority_with_global_fallback": {
                "prediction_rule": "Predict the most frequent event_category within each pitch_type when the pitch_type has a unique majority; otherwise predict the global majority event_category.",
                "global_fallback_prediction": global_majority,
                "pitch_type_resolution_table": pitch_type_table,
            },
        },
        "metric_summary": baseline_metrics,
        "sample_preview": records[:PREVIEW_ROW_LIMIT],
        "records": records,
        "limitations": limitations,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    baseline_a = payload["metric_summary"]["baseline_a_global_majority"]
    baseline_b = payload["metric_summary"]["baseline_b_pitch_type_majority_with_global_fallback"]
    labels = payload["target_definition"]["label_order"]
    lines = [
        "# P219-A Historical Feature Baseline Evaluation Prototype",
        "",
        DISCLAIMER,
        "",
        "## Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Evaluated historical rows: {payload['row_count']}",
        f"- Output column count: {payload['column_count']}",
        f"- Target: `{payload['target_definition']['name']}`",
        f"- Baseline A accuracy: {baseline_a['accuracy']}",
        f"- Baseline B accuracy: {baseline_b['accuracy']}",
        f"- Baseline B coverage: {baseline_b['coverage_rows']} / {baseline_b['row_count']} ({baseline_b['coverage_fraction']})",
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
            "## Target Definition",
            "",
            f"- Target column: `{payload['target_definition']['name']}`",
            f"- Description: {payload['target_definition']['description']}",
            "",
            "| Class | Support | Fraction |",
            "| --- | --- | --- |",
        ]
    )
    for item in payload["target_definition"]["class_support"]:
        lines.append(
            f"| `{item['value']}` | {item['count']} | {item['fraction']} |"
        )

    lines.extend(
        [
            "",
            "## Baseline Definitions",
            "",
            f"- Baseline A: {payload['baseline_definitions']['baseline_a_global_majority']['prediction_rule']}",
            f"- Baseline A resolved prediction: `{payload['baseline_definitions']['baseline_a_global_majority']['resolved_prediction']}`",
            f"- Baseline B: {payload['baseline_definitions']['baseline_b_pitch_type_majority_with_global_fallback']['prediction_rule']}",
            f"- Baseline B global fallback prediction: `{payload['baseline_definitions']['baseline_b_pitch_type_majority_with_global_fallback']['global_fallback_prediction']}`",
            "",
            "### Pitch-Type Resolution Table",
            "",
            "| Pitch Type | Support | Resolved Prediction | Prediction Source | Fallback |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in payload["baseline_definitions"]["baseline_b_pitch_type_majority_with_global_fallback"]["pitch_type_resolution_table"]:
        lines.append(
            f"| `{item['pitch_type']}` | {item['support']} | `{item['resolved_prediction']}` | `{item['prediction_source']}` | {_md_cell(item['fallback_to_global_majority'])} |"
        )

    lines.extend(
        [
            "",
            "## Metric Summary",
            "",
            "### Baseline A",
            "",
            f"- Accuracy: {baseline_a['accuracy']}",
            f"- Correct rows: {baseline_a['correct_count']} / {baseline_a['row_count']}",
            f"- Coverage: {baseline_a['coverage_rows']} / {baseline_a['row_count']} ({baseline_a['coverage_fraction']})",
            "",
            "| Predicted Class | Count | Fraction |",
            "| --- | --- | --- |",
        ]
    )
    for item in baseline_a["predicted_class_distribution"]:
        lines.append(f"| `{item['value']}` | {item['count']} | {item['fraction']} |")

    lines.extend(["", "#### Baseline A Confusion Matrix", ""])
    lines.extend(_render_markdown_matrix(labels, baseline_a["confusion_matrix"]))

    lines.extend(
        [
            "",
            "### Baseline B",
            "",
            f"- Accuracy: {baseline_b['accuracy']}",
            f"- Correct rows: {baseline_b['correct_count']} / {baseline_b['row_count']}",
            f"- Coverage: {baseline_b['coverage_rows']} / {baseline_b['row_count']} ({baseline_b['coverage_fraction']})",
            "",
            "| Predicted Class | Count | Fraction |",
            "| --- | --- | --- |",
        ]
    )
    for item in baseline_b["predicted_class_distribution"]:
        lines.append(f"| `{item['value']}` | {item['count']} | {item['fraction']} |")

    lines.extend(["", "#### Baseline B Confusion Matrix", ""])
    lines.extend(_render_markdown_matrix(labels, baseline_b["confusion_matrix"]))

    lines.extend(
        [
            "",
            "## Per-Row Historical Baseline Output",
            "",
            "| " + " | ".join(payload["output_columns"]) + " |",
            "| " + " | ".join("---" for _ in payload["output_columns"]) + " |",
        ]
    )
    for record in payload["records"]:
        lines.append(
            "| "
            + " | ".join(_md_cell(record[column]) for column in payload["output_columns"])
            + " |"
        )

    lines.extend(["", "## Limitations", ""])
    for item in payload["limitations"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Prohibited Claims", ""])
    for item in payload["prohibited_claims"]:
        lines.append(f"- {item}")

    lines.extend(["", DISCLAIMER, ""])
    return "\n".join(lines)


def _write_csv(payload: dict[str, Any]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
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
