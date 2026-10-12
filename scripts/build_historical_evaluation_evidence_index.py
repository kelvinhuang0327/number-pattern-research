#!/usr/bin/env python3
"""Build the P223-A historical evaluation evidence index from fixed P216-P222 artifacts only."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SOURCE_P216_CSV = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.csv"
SOURCE_P216_JSON = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.json"
SOURCE_P216_MD = REPORT_DIR / "p216a_pybaseball_multidate_sample_pack.md"
SOURCE_P217_HTML = REPORT_DIR / "p217a_pybaseball_multidate_quality_dashboard.html"
SOURCE_P217_JSON = REPORT_DIR / "p217a_pybaseball_multidate_quality_dashboard.json"
SOURCE_P218_CSV = REPORT_DIR / "p218a_historical_sample_feature_table.csv"
SOURCE_P218_JSON = REPORT_DIR / "p218a_historical_sample_feature_table.json"
SOURCE_P218_MD = REPORT_DIR / "p218a_historical_sample_feature_table.md"
SOURCE_P219_CSV = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.csv"
SOURCE_P219_JSON = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.json"
SOURCE_P219_MD = REPORT_DIR / "p219a_historical_feature_baseline_evaluation.md"
SOURCE_P220_HTML = REPORT_DIR / "p220a_historical_baseline_error_dashboard.html"
SOURCE_P220_JSON = REPORT_DIR / "p220a_historical_baseline_error_dashboard.json"
SOURCE_P221_CSV = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.csv"
SOURCE_P221_JSON = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.json"
SOURCE_P221_MD = REPORT_DIR / "p221a_historical_time_split_baseline_evaluation.md"
SOURCE_P222_HTML = REPORT_DIR / "p222a_historical_time_split_error_dashboard.html"
SOURCE_P222_JSON = REPORT_DIR / "p222a_historical_time_split_error_dashboard.json"
OUT_HTML = REPORT_DIR / "p223a_historical_evaluation_evidence_index.html"
OUT_JSON = REPORT_DIR / "p223a_historical_evaluation_evidence_index.json"
TASK_NAME = "P223-A Historical Evaluation Evidence Index"
STATUS = "PASS_P216A_P222A_ARTIFACT_ONLY_HISTORICAL_EVALUATION_EVIDENCE_INDEX"
DISCLAIMER = "Historical evaluation evidence index only. Not live predictions, not betting advice."
SUCCESS_BANNER = "P223-A HISTORICAL EVALUATION EVIDENCE INDEX PASS"
FAILURE_BANNER = "P223-A HISTORICAL EVALUATION EVIDENCE INDEX FAIL"
BASELINE_A_KEY = "baseline_a_global_majority"
BASELINE_B_KEY = "baseline_b_pitch_type_majority_with_global_fallback"
SOURCE_REQUIRED_HASHES = {
    "report/p216a_pybaseball_multidate_sample_pack.csv": "e2d2eb233d4cb930ba7a886d7ca3350922aea671343ba23c6979f9dcedcac3c0",
    "report/p216a_pybaseball_multidate_sample_pack.json": "c4f048a072097378978dbb71b1ba60749f0014157b91affd9a3438f6531e72c8",
    "report/p216a_pybaseball_multidate_sample_pack.md": "f3ad49921b60df67449c6c846777318b5c4e81d79db393b47a14eac0c1e800b9",
    "report/p217a_pybaseball_multidate_quality_dashboard.html": "568ebfaca288a0c8dce56117d5f82673e89de074f46598a16067356556c657f0",
    "report/p217a_pybaseball_multidate_quality_dashboard.json": "850cfc282505df70f5472133d16ec1772df5411bdddb26bf30be6b5c414ac516",
    "report/p218a_historical_sample_feature_table.csv": "d3d00176e3e40163c8d38a60019e204b0d37ef7efb745b638e797578f197b507",
    "report/p218a_historical_sample_feature_table.json": "60fde1062e935c7f5d37a693611e6433d765b905fb7e1a499c513bf728e39844",
    "report/p218a_historical_sample_feature_table.md": "28aa4b4d17bade86fe9c51990cf1798640967ea3a6e7388a81e54d485efbf016",
    "report/p219a_historical_feature_baseline_evaluation.csv": "4c447f63e827d6fad4a4fdd6f2f36142cc601d6f622aceeca3a31f21a22075e7",
    "report/p219a_historical_feature_baseline_evaluation.json": "dc4ac6fce1e0f8f92a87a3bd3ab74d6aa60d8ea4b8205b3c8e822a1cbb370298",
    "report/p219a_historical_feature_baseline_evaluation.md": "2ba77c284d094a1e34770a1377cd47b25ef076f09c6b8187465ebcd0b970a1c9",
    "report/p220a_historical_baseline_error_dashboard.html": "b239b2249810b0b9c04551e625ac0c4f70c6298427756ab8e1cd5c2b80991f19",
    "report/p220a_historical_baseline_error_dashboard.json": "abd4a2540ea2109ee77f30a4a836f1800e3218cc003ed92fda0e1043c8f695f3",
    "report/p221a_historical_time_split_baseline_evaluation.csv": "2d17483e66a11069806f4b0f49bcd905f1d427ab56425edef9f24aba8844d3ae",
    "report/p221a_historical_time_split_baseline_evaluation.json": "0ccec8bc6b01c5bbdd8a3c082cbbc161d4a5fc0f39cc3cfe51948199e7528982",
    "report/p221a_historical_time_split_baseline_evaluation.md": "f31c00dbd65a86ae0224cbd147c1e2c39c45a58e13791f702266c54cb5b05617",
    "report/p222a_historical_time_split_error_dashboard.html": "620dea39de7464a7d1ae6f46dba9aab0d3687c2bb33b8d496b45a447ba783c94",
    "report/p222a_historical_time_split_error_dashboard.json": "97a9646e4892d7fcc49c48679760f8a86cff05f8c11565460c2c824d118b016f",
}


def _source_paths() -> list[Path]:
    return [
        SOURCE_P216_CSV,
        SOURCE_P216_JSON,
        SOURCE_P216_MD,
        SOURCE_P217_HTML,
        SOURCE_P217_JSON,
        SOURCE_P218_CSV,
        SOURCE_P218_JSON,
        SOURCE_P218_MD,
        SOURCE_P219_CSV,
        SOURCE_P219_JSON,
        SOURCE_P219_MD,
        SOURCE_P220_HTML,
        SOURCE_P220_JSON,
        SOURCE_P221_CSV,
        SOURCE_P221_JSON,
        SOURCE_P221_MD,
        SOURCE_P222_HTML,
        SOURCE_P222_JSON,
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_label(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_shape(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return {"row_count": 0, "column_count": 0}
    return {
        "row_count": max(len(rows) - 1, 0),
        "column_count": len(rows[0]),
    }


def _validate_source_hashes(source_artifacts: list[str]) -> dict[str, str]:
    observed_hashes = {artifact: _sha256(ROOT / artifact) for artifact in source_artifacts}
    for artifact, required_hash in SOURCE_REQUIRED_HASHES.items():
        observed_hash = observed_hashes.get(artifact)
        if observed_hash != required_hash:
            raise ValueError(
                f"P223A_STOPPED_SOURCE_ARTIFACT_MISMATCH: {artifact} expected {required_hash} got {observed_hash}"
            )
    return observed_hashes


def _validate_shape(
    stage_id: str,
    csv_shape: dict[str, int],
    payload: dict[str, Any],
) -> None:
    if payload.get("row_count") != csv_shape["row_count"]:
        raise ValueError(
            f"P223A_IMPLEMENTED_VALIDATION_FAILED: {stage_id} row_count does not match CSV"
        )
    if payload.get("column_count") != csv_shape["column_count"]:
        raise ValueError(
            f"P223A_IMPLEMENTED_VALIDATION_FAILED: {stage_id} column_count does not match CSV"
        )


def _baseline_metrics_snapshot(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_count": metric["row_count"],
        "correct_count": metric["correct_count"],
        "accuracy": metric["accuracy"],
        "coverage_rows": metric["coverage_rows"],
        "coverage_fraction": metric["coverage_fraction"],
    }


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _artifact_chain(
    p216_json: dict[str, Any],
    p217_json: dict[str, Any],
    p218_json: dict[str, Any],
    p219_json: dict[str, Any],
    p220_json: dict[str, Any],
    p221_json: dict[str, Any],
    p222_json: dict[str, Any],
) -> list[dict[str, Any]]:
    p219_a = p219_json["metric_summary"][BASELINE_A_KEY]["accuracy"]
    p219_b = p219_json["metric_summary"][BASELINE_B_KEY]["accuracy"]
    p221_a = p221_json["overall_holdout_metrics"][BASELINE_A_KEY]["accuracy"]
    p221_b = p221_json["overall_holdout_metrics"][BASELINE_B_KEY]["accuracy"]
    return [
        {
            "artifact_id": "P216-A",
            "task": p216_json["task"],
            "status": p216_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P216_CSV),
                _artifact_label(SOURCE_P216_JSON),
                _artifact_label(SOURCE_P216_MD),
            ],
            "summary": (
                f"Fixed {p216_json['row_count']}-row, {p216_json['column_count']}-column "
                f"historical sample covering {', '.join(p216_json['observed_dates'])}."
            ),
        },
        {
            "artifact_id": "P217-A",
            "task": p217_json["task"],
            "status": p217_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P217_HTML),
                _artifact_label(SOURCE_P217_JSON),
            ],
            "summary": (
                f"Deterministic quality dashboard over the same {p217_json['row_count']}-row snapshot "
                f"with per-date row counts {p217_json['per_date_row_counts']}."
            ),
        },
        {
            "artifact_id": "P218-A",
            "task": p218_json["task"],
            "status": p218_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P218_CSV),
                _artifact_label(SOURCE_P218_JSON),
                _artifact_label(SOURCE_P218_MD),
            ],
            "summary": (
                f"{p218_json['row_count']}-row, {p218_json['column_count']}-column feature table "
                "derived only from the fixed P216/P217 artifacts."
            ),
        },
        {
            "artifact_id": "P219-A",
            "task": p219_json["task"],
            "status": p219_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P219_CSV),
                _artifact_label(SOURCE_P219_JSON),
                _artifact_label(SOURCE_P219_MD),
            ],
            "summary": (
                f"In-sample deterministic baselines on {p219_json['row_count']} rows: "
                f"baseline A accuracy {p219_a}, baseline B accuracy {p219_b}."
            ),
        },
        {
            "artifact_id": "P220-A",
            "task": p220_json["task"],
            "status": p220_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P220_HTML),
                _artifact_label(SOURCE_P220_JSON),
            ],
            "summary": "Error dashboard for P219 in-sample baselines, including pitch-type fallback analysis.",
        },
        {
            "artifact_id": "P221-A",
            "task": p221_json["task"],
            "status": p221_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P221_CSV),
                _artifact_label(SOURCE_P221_JSON),
                _artifact_label(SOURCE_P221_MD),
            ],
            "summary": (
                f"Time-split holdout baseline evaluation on {p221_json['row_count']} rows across "
                f"{len(p221_json['time_split_definitions'])} splits: baseline A accuracy {p221_a}, "
                f"baseline B accuracy {p221_b}."
            ),
        },
        {
            "artifact_id": "P222-A",
            "task": p222_json["task"],
            "status": p222_json["status"],
            "artifacts": [
                _artifact_label(SOURCE_P222_HTML),
                _artifact_label(SOURCE_P222_JSON),
            ],
            "summary": "Time-split error dashboard comparing P221 holdout behavior against P220 in-sample behavior.",
        },
    ]


def build_payload() -> dict[str, Any]:
    source_artifacts = [_artifact_label(path) for path in _source_paths()]
    source_hashes = _validate_source_hashes(source_artifacts)

    p216_json = _load_json(SOURCE_P216_JSON)
    p217_json = _load_json(SOURCE_P217_JSON)
    p218_json = _load_json(SOURCE_P218_JSON)
    p219_json = _load_json(SOURCE_P219_JSON)
    p220_json = _load_json(SOURCE_P220_JSON)
    p221_json = _load_json(SOURCE_P221_JSON)
    p222_json = _load_json(SOURCE_P222_JSON)

    p216_csv_shape = _csv_shape(SOURCE_P216_CSV)
    p218_csv_shape = _csv_shape(SOURCE_P218_CSV)
    p219_csv_shape = _csv_shape(SOURCE_P219_CSV)
    p221_csv_shape = _csv_shape(SOURCE_P221_CSV)
    _validate_shape("P216-A", p216_csv_shape, p216_json)
    _validate_shape("P218-A", p218_csv_shape, p218_json)
    _validate_shape("P219-A", p219_csv_shape, p219_json)
    _validate_shape("P221-A", p221_csv_shape, p221_json)

    p219_a = p219_json["metric_summary"][BASELINE_A_KEY]
    p219_b = p219_json["metric_summary"][BASELINE_B_KEY]
    p221_a = p221_json["overall_holdout_metrics"][BASELINE_A_KEY]
    p221_b = p221_json["overall_holdout_metrics"][BASELINE_B_KEY]
    p221_coverage = p221_json["overall_holdout_metrics"]["baseline_b_coverage"]
    p222_overall = p222_json["overall_metrics"]
    p222_vs_p220 = p222_overall["vs_p220_in_sample"]

    limitations = [
        (
            f"Fixed bounded sample only: P216/P218/P219/P220 are based on {p216_json['row_count']} rows "
            f"across {len(p216_json['observed_dates'])} dates for the committed historical snapshot."
        ),
        (
            "Feature engineering remains heuristic and source-bounded; the artifacts do not establish full "
            "point-in-time pregame context, complete count state, or a production feature contract."
        ),
        (
            f"P219/P220 evidence is in-sample on the same {p219_json['row_count']} rows used to derive "
            "the baseline rules, so it does not establish out-of-sample predictive ability."
        ),
        (
            f"P221/P222 holdout evidence is still small: {p221_json['row_count']} evaluated rows across "
            f"{len(p221_json['time_split_definitions'])} time-split holdout dates."
        ),
        "Baseline A and baseline B are deterministic reference heuristics, not trained production models.",
        (
            f"P221 baseline B fallback coverage remains weak: {p221_coverage['all_global_fallback']['rows']} "
            f"of {p221_b['row_count']} rows used global fallback, with fallback accuracy "
            f"{p221_coverage['all_global_fallback']['accuracy']}."
        ),
        "Current evidence does not establish live data readiness, point-in-time integrity, or production activation readiness.",
        "This index reads committed artifacts only and does not independently refresh, extend, or relabel the historical sample.",
    ]

    prohibited_claims = [
        "Do not claim future prediction ability from this evidence index.",
        "Do not claim betting advice, wagering edge, or pick quality from this evidence index.",
        "Do not claim ROI, EV, Kelly, or CLV from this evidence index.",
        "Do not claim production readiness or live pipeline readiness from this evidence index.",
        "Do not claim season-wide or league-wide generalization from this bounded historical snapshot.",
        "Do not claim point-in-time feature integrity beyond what the fixed P216-P222 artifacts explicitly show.",
    ]

    current_capabilities = [
        f"Verify a fixed P216-P222 evidence chain by SHA256 across {len(source_artifacts)} committed artifacts.",
        "Trace deterministic lineage from bounded historical sample collection through quality review, feature construction, in-sample baseline evaluation, and time-split holdout evaluation.",
        (
            f"Quantify current baseline behavior on the fixed sample: P219 baseline A accuracy {p219_a['accuracy']}, "
            f"P219 baseline B accuracy {p219_b['accuracy']}, P221 baseline A accuracy {p221_a['accuracy']}, "
            f"and P221 baseline B accuracy {p221_b['accuracy']}."
        ),
        "Compare in-sample versus time-split degradation using the committed P220 and P222 dashboard evidence.",
    ]

    not_claimed = [
        "No future predictive ability is established.",
        "No betting advice or wagering edge is established.",
        "No ROI, EV, Kelly, or CLV is established.",
        "No production readiness or live pipeline readiness is established.",
        "No model training, remote data refresh, or pybaseball invocation occurred in this task.",
        "No database writes or live provider calls occurred in this task.",
    ]

    next_step_options = [
        {
            "option_id": "cto_option_1",
            "decision_point": "Authorize point-in-time feature and lineage contract design before any model design work.",
            "why_now": "The current evidence chain is historical and deterministic, but it does not prove point-in-time feature integrity.",
            "requires_new_artifacts": True,
        },
        {
            "option_id": "cto_option_2",
            "decision_point": "Expand the bounded historical sample and rerun the same artifact chain before interpreting baseline behavior more broadly.",
            "why_now": "The present evidence is limited to 24 in-sample rows and 16 holdout rows.",
            "requires_new_artifacts": True,
        },
        {
            "option_id": "cto_option_3",
            "decision_point": "Revisit target and feature design to reduce sparse classes and fallback-heavy baseline behavior before any model experimentation.",
            "why_now": "Baseline B still relies on global fallback for a material share of holdout rows and struggles on minority classes.",
            "requires_new_artifacts": True,
        },
        {
            "option_id": "cto_option_4",
            "decision_point": "Defer model design authorization until point-in-time integrity and broader historical coverage are explicitly demonstrated.",
            "why_now": "Nothing in the current evidence chain establishes live or production-readiness.",
            "requires_new_artifacts": False,
        },
    ]

    artifact_chain = _artifact_chain(
        p216_json=p216_json,
        p217_json=p217_json,
        p218_json=p218_json,
        p219_json=p219_json,
        p220_json=p220_json,
        p221_json=p221_json,
        p222_json=p222_json,
    )

    metrics = {
        "p216_sample": {
            "row_count": p216_json["row_count"],
            "column_count": p216_json["column_count"],
            "csv_row_count": p216_csv_shape["row_count"],
            "csv_column_count": p216_csv_shape["column_count"],
            "observed_dates": p216_json["observed_dates"],
            "sample_size_limits": p216_json["sample_size_limits"],
            "per_date_row_counts": p217_json["per_date_row_counts"],
        },
        "p218_feature_table": {
            "row_count": p218_json["row_count"],
            "column_count": p218_json["column_count"],
            "csv_row_count": p218_csv_shape["row_count"],
            "csv_column_count": p218_csv_shape["column_count"],
            "feature_columns": p218_json["feature_columns"],
        },
        "p219_in_sample": {
            "row_count": p219_json["row_count"],
            "column_count": p219_json["column_count"],
            BASELINE_A_KEY: _baseline_metrics_snapshot(p219_a),
            BASELINE_B_KEY: _baseline_metrics_snapshot(p219_b),
            "comparison": {
                "accuracy_delta_b_minus_a": round(p219_b["accuracy"] - p219_a["accuracy"], 6),
                "correct_row_delta_b_minus_a": p219_b["correct_count"] - p219_a["correct_count"],
            },
        },
        "p220_dashboard_hashes": {
            _artifact_label(SOURCE_P220_HTML): source_hashes[_artifact_label(SOURCE_P220_HTML)],
            _artifact_label(SOURCE_P220_JSON): source_hashes[_artifact_label(SOURCE_P220_JSON)],
        },
        "p221_time_split": {
            "row_count": p221_json["row_count"],
            "column_count": p221_json["column_count"],
            "split_count": len(p221_json["time_split_definitions"]),
            BASELINE_A_KEY: _baseline_metrics_snapshot(p221_a),
            BASELINE_B_KEY: _baseline_metrics_snapshot(p221_b),
            "baseline_b_coverage": p221_coverage,
            "comparison": p221_json["overall_holdout_metrics"]["comparison"],
        },
        "p222_dashboard_hashes": {
            _artifact_label(SOURCE_P222_HTML): source_hashes[_artifact_label(SOURCE_P222_HTML)],
            _artifact_label(SOURCE_P222_JSON): source_hashes[_artifact_label(SOURCE_P222_JSON)],
        },
        "p222_vs_p220_dashboard": p222_vs_p220,
    }

    return {
        "artifact_chain": artifact_chain,
        "current_capabilities": current_capabilities,
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "limitations": limitations,
        "metrics": metrics,
        "next_step_options": next_step_options,
        "not_claimed": not_claimed,
        "prohibited_claims": prohibited_claims,
        "source_artifacts": source_artifacts,
        "source_hash_validation": "PASS_ALL_FIXED_P216_P222_SOURCE_HASHES_MATCH",
        "source_hashes": source_hashes,
        "status": STATUS,
        "task": TASK_NAME,
    }


def _html_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _render_html_table(headers: list[str], rows: list[list[Any]]) -> str:
    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
        )
    return "<table><thead><tr>" + header_html + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table>"


def render_html(payload: dict[str, Any]) -> str:
    chain_rows = [
        [entry["artifact_id"], entry["status"], ", ".join(entry["artifacts"]), entry["summary"]]
        for entry in payload["artifact_chain"]
    ]
    source_rows = [
        [artifact, payload["source_hashes"][artifact]]
        for artifact in payload["source_artifacts"]
    ]
    p216 = payload["metrics"]["p216_sample"]
    p218 = payload["metrics"]["p218_feature_table"]
    p219 = payload["metrics"]["p219_in_sample"]
    p221 = payload["metrics"]["p221_time_split"]
    p222_vs_p220 = payload["metrics"]["p222_vs_p220_dashboard"]
    metric_rows = [
        ["P216 rows", p216["row_count"]],
        ["P216 columns", p216["column_count"]],
        ["P218 rows", p218["row_count"]],
        ["P218 columns", p218["column_count"]],
        ["P219 baseline A accuracy", p219[BASELINE_A_KEY]["accuracy"]],
        ["P219 baseline B accuracy", p219[BASELINE_B_KEY]["accuracy"]],
        ["P221 baseline A accuracy", p221[BASELINE_A_KEY]["accuracy"]],
        ["P221 baseline B accuracy", p221[BASELINE_B_KEY]["accuracy"]],
        [
            "P222 vs P220 baseline A delta",
            p222_vs_p220[BASELINE_A_KEY]["accuracy_delta_time_split_minus_p220"],
        ],
        [
            "P222 vs P220 baseline B delta",
            p222_vs_p220[BASELINE_B_KEY]["accuracy_delta_time_split_minus_p220"],
        ],
    ]
    next_step_rows = [
        [
            option["option_id"],
            option["decision_point"],
            option["why_now"],
            option["requires_new_artifacts"],
        ]
        for option in payload["next_step_options"]
    ]
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html.escape(TASK_NAME)}</title>",
            "  <style>",
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #14213d; background: #f7f7f2; }",
            "    main { max-width: 1200px; margin: 0 auto; }",
            "    h1, h2 { color: #0b3954; }",
            "    .notice { padding: 12px 14px; background: #fff3cd; border-left: 4px solid #b08900; }",
            "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }",
            "    section { background: white; padding: 16px; border: 1px solid #d9d9d9; border-radius: 8px; margin-bottom: 20px; }",
            "    table { width: 100%; border-collapse: collapse; }",
            "    th, td { border: 1px solid #d9d9d9; padding: 8px; text-align: left; vertical-align: top; }",
            "    th { background: #eef4ed; }",
            "    code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }",
            "  </style>",
            "</head>",
            "<body>",
            "<main>",
            f"  <h1>{html.escape(TASK_NAME)}</h1>",
            f"  <p class=\"notice\"><strong>Status:</strong> {html.escape(payload['status'])}<br><strong>Disclaimer:</strong> {html.escape(payload['disclaimer'])}</p>",
            "  <section>",
            "    <h2>Current Capability Statement</h2>",
            f"    {_html_list(payload['current_capabilities'])}",
            "  </section>",
            "  <section>",
            "    <h2>Artifact Chain</h2>",
            f"    {_render_html_table(['Artifact', 'Status', 'Artifacts', 'Summary'], chain_rows)}",
            "  </section>",
            "  <div class=\"grid\">",
            "    <section>",
            "      <h2>Source Hashes</h2>",
            f"      {_render_html_table(['Artifact Path', 'SHA256'], source_rows)}",
            "    </section>",
            "    <section>",
            "      <h2>Key Metrics</h2>",
            f"      {_render_html_table(['Metric', 'Value'], metric_rows)}",
            "    </section>",
            "  </div>",
            "  <section>",
            "    <h2>Current Limitations</h2>",
            f"    {_html_list(payload['limitations'])}",
            "  </section>",
            "  <section>",
            "    <h2>Prohibited Claims</h2>",
            f"    {_html_list(payload['prohibited_claims'])}",
            "  </section>",
            "  <section>",
            "    <h2>Not Claimed</h2>",
            f"    {_html_list(payload['not_claimed'])}",
            "  </section>",
            "  <section>",
            "    <h2>Next-Step Decision Points For CTO</h2>",
            f"    {_render_html_table(['Option', 'Decision Point', 'Why Now', 'Requires New Artifacts'], next_step_rows)}",
            "  </section>",
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
