#!/usr/bin/env python3
"""Build the P210-A historical MLB slice analysis dashboard.

This script reads only committed P207-A, P208-A, and P209-A report artifacts and
produces a deterministic static HTML dashboard plus JSON summary. It does not
train models, call providers, write a database, mutate tickets, or activate any
workflow.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"

SCORECARD_JSON = REPORT_DIR / "p207a_local_retrain_scorecard.json"
MODEL_COMPARISON_CSV = REPORT_DIR / "p207a_local_retrain_model_comparison.csv"
PREDICTIONS_CSV = REPORT_DIR / "p207a_local_retrain_predictions.csv"
P208_VIEWER_JSON = REPORT_DIR / "p208a_visible_scorecard_result_viewer.json"
P209_DASHBOARD_JSON = REPORT_DIR / "p209a_static_scorecard_dashboard.json"

OUT_HTML = REPORT_DIR / "p210a_historical_slice_analysis.html"
OUT_JSON = REPORT_DIR / "p210a_historical_slice_analysis.json"

TITLE = "MLB Historical Slice Analysis Dashboard"
SCOPE = "LOCAL_HISTORICAL_REPLAY_ONLY"
DISCLAIMER = "Historical replay/backtest only. Not live predictions, not betting advice."
EXAMPLE_LABEL = "historical replay/backtest only"
MODEL_MERGE_LINEAGE = {
    "P207-A": "dbdbe24053a07a7a9ae338395992849350072bdd",
    "P208-A": "a3ae86aa7c78361082b1e250e1ae740cd79c6f70",
    "P209-A": "48727abef6e3323fdbfe37b89d7e10cf7497f692",
}
REQUIRED_INPUTS = (
    SCORECARD_JSON,
    MODEL_COMPARISON_CSV,
    PREDICTIONS_CSV,
    P208_VIEWER_JSON,
    P209_DASHBOARD_JSON,
)
REQUIRED_PREDICTION_COLUMNS = (
    "model_name",
    "predicted_home_win_probability",
    "selected_side",
    "confidence_band",
    "actual_home_win",
    "correct",
)
OPTIONAL_COLUMN_GROUPS = {
    "month_by_model": ("game_date",),
    "team_exposure": ("home_team", "away_team"),
    "historical_examples": (
        "game_date",
        "game_id",
        "home_team",
        "away_team",
        "learning_guard_status",
        "provenance_contract_version",
    ),
}
CONFIDENCE_BANDS = ("HIGH", "MEDIUM", "LOW")
SIDES = ("HOME", "AWAY")
TOP_TEAM_LIMIT = 12
TOP_EXAMPLE_LIMIT = 12


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escape_html(value: Any) -> str:
    """Escape any value before it is interpolated into the HTML dashboard."""
    return html.escape(str(value), quote=True)


def _round_metric(value: Any) -> float:
    return round(float(value), 6)


def _intish(value: Any) -> int:
    return int(float(value))


def _format_pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _fmt_float(value: Any) -> str:
    return f"{float(value):.6f}"


def _column_set(rows: list[dict[str, str]]) -> set[str]:
    columns: set[str] = set()
    for row in rows:
        columns.update(row.keys())
    return columns


def _missing_columns(rows: list[dict[str, str]], columns: tuple[str, ...]) -> list[str]:
    present = _column_set(rows)
    return [column for column in columns if column not in present]


def _add_missing_column_limitations(
    rows: list[dict[str, str]],
    limitations: list[str],
) -> dict[str, bool]:
    availability: dict[str, bool] = {}
    for slice_name, columns in OPTIONAL_COLUMN_GROUPS.items():
        missing = _missing_columns(rows, columns)
        availability[slice_name] = not missing
        if missing:
            limitations.append(
                f"Skipped {slice_name} slice because optional column(s) were absent: "
                f"{', '.join(missing)}."
            )
    return availability


def _selected_probability(row: dict[str, str]) -> float:
    home_probability = float(row["predicted_home_win_probability"])
    if row["selected_side"] == "HOME":
        return home_probability
    return 1.0 - home_probability


def _slice_stats(rows: list[dict[str, str]]) -> dict[str, int | float]:
    count = len(rows)
    correct = sum(_intish(row["correct"]) for row in rows)
    return {
        "count": count,
        "correct": correct,
        "accuracy": _round_metric(correct / count) if count else 0.0,
    }


def _metric_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "model_name": row["model_name"],
        "train_rows": _intish(row["train_rows"]),
        "test_rows": _intish(row["test_rows"]),
        "accuracy": _round_metric(row["accuracy"]),
        "log_loss": _round_metric(row["log_loss"]),
        "brier_score": _round_metric(row["brier_score"]),
        "calibration_error": _round_metric(row["calibration_error"]),
        "coverage": _round_metric(row["coverage"]),
        "reference_only": "REFERENCE_UNVERIFIED" in row["model_name"] or row["train_rows"] == "0",
        "notes": row["notes"],
    }


def _models_from_rows(rows: list[dict[str, str]]) -> list[str]:
    return sorted({row["model_name"] for row in rows})


def _month_by_model(rows: list[dict[str, str]], available: bool) -> list[dict[str, Any]]:
    if not available:
        return []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        date = row.get("game_date", "")
        if len(date) >= 7:
            groups[(row["model_name"], date[:7])].append(row)
    result = []
    for model_name, month in sorted(groups):
        stats = _slice_stats(groups[(model_name, month)])
        result.append({"model_name": model_name, "month": month, **stats})
    return result


def _confidence_band_by_model(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["model_name"], row["confidence_band"])].append(row)
    models = _models_from_rows(rows)
    extra_bands = sorted(
        {row["confidence_band"] for row in rows if row["confidence_band"] not in CONFIDENCE_BANDS}
    )
    result = []
    for model_name in models:
        for band in (*CONFIDENCE_BANDS, *extra_bands):
            stats = _slice_stats(groups[(model_name, band)])
            result.append({"model_name": model_name, "confidence_band": band, **stats})
    return result


def _selected_side_by_model(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["model_name"], row["selected_side"])].append(row)
    models = _models_from_rows(rows)
    extra_sides = sorted({row["selected_side"] for row in rows if row["selected_side"] not in SIDES})
    result = []
    for model_name in models:
        for side in (*SIDES, *extra_sides):
            stats = _slice_stats(groups[(model_name, side)])
            result.append({"model_name": model_name, "selected_side": side, **stats})
    return result


def _team_exposure(rows: list[dict[str, str]], available: bool) -> list[dict[str, Any]]:
    if not available:
        return []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        selected_side = row["selected_side"]
        team = row["home_team"] if selected_side == "HOME" else row["away_team"]
        groups[(row["model_name"], team)].append(row)
    result = []
    for model_name, team in sorted(
        groups,
        key=lambda item: (-len(groups[item]), item[0], item[1]),
    )[:TOP_TEAM_LIMIT]:
        stats = _slice_stats(groups[(model_name, team)])
        result.append({"model_name": model_name, "team": team, **stats})
    return result


def _example_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "label": EXAMPLE_LABEL,
        "game_date": row.get("game_date", ""),
        "game_id": row.get("game_id", ""),
        "home_team": row.get("home_team", ""),
        "away_team": row.get("away_team", ""),
        "model_name": row["model_name"],
        "selected_side": row["selected_side"],
        "selected_side_probability": _round_metric(_selected_probability(row)),
        "predicted_home_win_probability": _round_metric(row["predicted_home_win_probability"]),
        "confidence_band": row["confidence_band"],
        "actual_home_win": _intish(row["actual_home_win"]),
        "correct": _intish(row["correct"]),
        "learning_guard_status": row.get("learning_guard_status", "LOCAL_HISTORICAL_BACKTEST_ONLY"),
        "provenance_contract_version": row.get("provenance_contract_version", ""),
    }


def _top_examples(
    rows: list[dict[str, str]],
    available: bool,
    correct_value: int,
) -> list[dict[str, Any]]:
    if not available:
        return []
    scoped = [
        row
        for row in rows
        if row["confidence_band"] == "HIGH" and _intish(row["correct"]) == correct_value
    ]
    scoped.sort(
        key=lambda row: (
            -_selected_probability(row),
            row.get("game_date", ""),
            row.get("game_id", ""),
            row["model_name"],
            row["selected_side"],
        )
    )
    return [_example_row(row) for row in scoped[:TOP_EXAMPLE_LIMIT]]


def _source_artifacts() -> list[dict[str, str]]:
    return [
        {"task": "P207-A", "path": "report/p207a_local_retrain_scorecard.json"},
        {"task": "P207-A", "path": "report/p207a_local_retrain_model_comparison.csv"},
        {"task": "P207-A", "path": "report/p207a_local_retrain_predictions.csv"},
        {"task": "P208-A", "path": "report/p208a_visible_scorecard_result_viewer.json"},
        {"task": "P209-A", "path": "report/p209a_static_scorecard_dashboard.json"},
    ]


def build_dashboard_payload(
    scorecard: dict[str, Any],
    model_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
    p208_payload: dict[str, Any],
    p209_payload: dict[str, Any],
) -> dict[str, Any]:
    missing_required = _missing_columns(prediction_rows, REQUIRED_PREDICTION_COLUMNS)
    if missing_required:
        raise ValueError(
            "P210A_BLOCKED_MISSING_REQUIRED_COLUMNS: " + ", ".join(missing_required)
        )

    limitations = [
        "Uses only committed historical replay artifacts from P207-A, P208-A, and P209-A.",
        "Slice accuracy is descriptive over completed rows and should not be extrapolated.",
        "Small slice counts can be noisy; inspect count before comparing accuracy.",
    ]
    availability = _add_missing_column_limitations(prediction_rows, limitations)
    leaderboard = [_metric_row(row) for row in model_rows]

    return {
        "task": "P210-A historical slice analysis",
        "title": TITLE,
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "source_artifacts": _source_artifacts(),
        "merge_lineage": MODEL_MERGE_LINEAGE,
        "input_artifact_consistency": {
            "p208_scope": p208_payload.get("scope"),
            "p209_scope": p209_payload.get("scope"),
            "p207_task": scorecard.get("task"),
            "p209_title": p209_payload.get("title"),
        },
        "split": scorecard.get("split", {}),
        "prediction_rows_read": len(prediction_rows),
        "models_analyzed": _models_from_rows(prediction_rows),
        "leaderboard": leaderboard,
        "slices": {
            "month_by_model": _month_by_model(prediction_rows, availability["month_by_model"]),
            "confidence_band_by_model": _confidence_band_by_model(prediction_rows),
            "selected_side_by_model": _selected_side_by_model(prediction_rows),
            "top_team_exposure": _team_exposure(prediction_rows, availability["team_exposure"]),
        },
        "examples": {
            "top_correct_high_confidence": _top_examples(
                prediction_rows,
                availability["historical_examples"],
                1,
            ),
            "top_incorrect_high_confidence": _top_examples(
                prediction_rows,
                availability["historical_examples"],
                0,
            ),
        },
        "limitations": limitations,
        "claim_status": {
            "historical_only": True,
            "provider_called": False,
            "db_written": False,
            "production_enabled": False,
            "ticket_mutated": False,
        },
    }


def _source_list(payload: dict[str, Any]) -> str:
    rows = []
    for source in payload["source_artifacts"]:
        rows.append(
            "<tr>"
            f"<td>{escape_html(source['task'])}</td>"
            f"<td><code>{escape_html(source['path'])}</code></td>"
            "</tr>"
        )
    return _table(["Task", "Artifact"], "".join(rows))


def _lineage_table(payload: dict[str, Any]) -> str:
    rows = []
    for task, sha in payload["merge_lineage"].items():
        rows.append(
            "<tr>"
            f"<td>{escape_html(task)}</td>"
            f"<td><code>{escape_html(sha)}</code></td>"
            "</tr>"
        )
    return _table(["Task", "Merge commit"], "".join(rows))


def _table(headers: list[str], body: str) -> str:
    head = "".join(f"<th>{escape_html(header)}</th>" for header in headers)
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table></div>"
    )


def _slice_table(
    rows: list[dict[str, Any]],
    label_key: str,
    label_header: str,
    empty_text: str,
) -> str:
    if not rows:
        return f"<p>{escape_html(empty_text)}</p>"
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{escape_html(row['model_name'])}</td>"
            f"<td>{escape_html(row[label_key])}</td>"
            f"<td>{int(row['count'])}</td>"
            f"<td>{int(row['correct'])}</td>"
            f"<td>{_format_pct(row['accuracy'])}</td>"
            "</tr>"
        )
    return _table(["Model", label_header, "Count", "Correct", "Accuracy"], "".join(body))


def _leaderboard_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{escape_html(row['model_name'])}</td>"
            f"<td>{_format_pct(row['accuracy'])}</td>"
            f"<td>{_fmt_float(row['brier_score'])}</td>"
            f"<td>{_fmt_float(row['log_loss'])}</td>"
            f"<td>{_fmt_float(row['calibration_error'])}</td>"
            f"<td>{_format_pct(row['coverage'])}</td>"
            f"<td>{'Yes' if row['reference_only'] else 'No'}</td>"
            f"<td>{escape_html(row['notes'])}</td>"
            "</tr>"
        )
    return _table(
        [
            "Model",
            "Accuracy",
            "Brier",
            "Log Loss",
            "Calibration Error",
            "Coverage",
            "Reference Only",
            "Notes",
        ],
        "".join(body),
    )


def _team_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>Team exposure slice skipped because team columns were unavailable.</p>"
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{escape_html(row['model_name'])}</td>"
            f"<td>{escape_html(row['team'])}</td>"
            f"<td>{int(row['count'])}</td>"
            f"<td>{int(row['correct'])}</td>"
            f"<td>{_format_pct(row['accuracy'])}</td>"
            "</tr>"
        )
    return _table(["Model", "Selected Team", "Exposure", "Correct", "Accuracy"], "".join(body))


def _examples_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>Examples skipped because optional example columns were unavailable.</p>"
    body = []
    for row in rows:
        matchup = f"{row['away_team']} @ {row['home_team']}"
        body.append(
            "<tr>"
            f"<td>{escape_html(row['label'])}</td>"
            f"<td>{escape_html(row['game_date'])}</td>"
            f"<td>{escape_html(matchup)}</td>"
            f"<td>{escape_html(row['model_name'])}</td>"
            f"<td>{escape_html(row['selected_side'])}</td>"
            f"<td>{_format_pct(row['selected_side_probability'])}</td>"
            f"<td>{escape_html(row['confidence_band'])}</td>"
            f"<td>{'Yes' if row['correct'] else 'No'}</td>"
            "</tr>"
        )
    return _table(
        [
            "Label",
            "Date",
            "Game",
            "Model",
            "Selected Side",
            "Selected Probability",
            "Band",
            "Correct",
        ],
        "".join(body),
    )


def _limitations_list(limitations: list[str]) -> str:
    items = "\n".join(f"<li>{escape_html(item)}</li>" for item in limitations)
    return f"<ul>{items}</ul>"


def render_html(payload: dict[str, Any]) -> str:
    split = payload.get("split", {})
    train_period = split.get("train_period", ["unknown", "unknown"])
    test_period = split.get("test_period", ["unknown", "unknown"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(payload["title"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #56616f;
      --line: #d8dee7;
      --head: #eef2f5;
      --accent: #22577a;
      --alert: #8a4b14;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 28px max(24px, calc((100vw - 1180px) / 2)) 22px;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(28px, 4vw, 44px);
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    p {{ margin: 0; }}
    section {{
      margin-top: 24px;
      padding: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .disclaimer {{
      max-width: 900px;
      color: var(--alert);
      font-weight: 750;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .pill {{
      border: 1px solid var(--line);
      background: #f1f4f7;
      border-radius: 999px;
      color: #243241;
      font-size: 13px;
      padding: 6px 10px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .summary-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 112px;
      background: #fbfcfe;
    }}
    .summary-card span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .summary-card strong {{
      display: block;
      margin-top: 8px;
      font-size: 24px;
      overflow-wrap: anywhere;
    }}
    .summary-card p {{
      margin-top: 8px;
      color: var(--muted);
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 840px;
      background: #fff;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      background: var(--head);
      color: #253241;
      font-size: 13px;
    }}
    td:last-child {{ white-space: normal; min-width: 180px; }}
    code {{
      background: #eef2f5;
      border-radius: 4px;
      padding: 2px 5px;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    li + li {{ margin-top: 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape_html(payload["title"])}</h1>
    <p class="disclaimer">{escape_html(payload["disclaimer"])}</p>
    <div class="meta">
      <span class="pill">Scope: {escape_html(payload["scope"])}</span>
      <span class="pill">Prediction rows: {int(payload["prediction_rows_read"])}</span>
      <span class="pill">Models analyzed: {len(payload["models_analyzed"])}</span>
      <span class="pill">Train: {escape_html(train_period[0])} to {escape_html(train_period[1])}</span>
      <span class="pill">Test: {escape_html(test_period[0])} to {escape_html(test_period[1])}</span>
    </div>
  </header>
  <main>
    <section aria-labelledby="summary-title">
      <h2 id="summary-title">Historical Slice Summary</h2>
      <div class="summary-grid">
        <article class="summary-card">
          <span>Rows Read</span>
          <strong>{int(payload["prediction_rows_read"])}</strong>
          <p>Completed historical replay rows only.</p>
        </article>
        <article class="summary-card">
          <span>Models</span>
          <strong>{len(payload["models_analyzed"])}</strong>
          <p>{escape_html(", ".join(payload["models_analyzed"]))}</p>
        </article>
        <article class="summary-card">
          <span>Claim Status</span>
          <strong>Historical Only</strong>
          <p>No provider call, database write, ticket mutation, or workflow activation.</p>
        </article>
      </div>
    </section>

    <section aria-labelledby="sources-title">
      <h2 id="sources-title">Source Artifacts And Merge Lineage</h2>
      {_source_list(payload)}
      <br>
      {_lineage_table(payload)}
    </section>

    <section aria-labelledby="leaderboard-title">
      <h2 id="leaderboard-title">Model Leaderboard</h2>
      {_leaderboard_table(payload["leaderboard"])}
    </section>

    <section aria-labelledby="month-title">
      <h2 id="month-title">Month-By-Month Accuracy And Count Slices</h2>
      {_slice_table(payload["slices"]["month_by_model"], "month", "Month", "Month slice skipped because date data was unavailable.")}
    </section>

    <section aria-labelledby="band-title">
      <h2 id="band-title">Confidence-Band Correctness Slices</h2>
      {_slice_table(payload["slices"]["confidence_band_by_model"], "confidence_band", "Confidence Band", "No confidence-band rows were available.")}
    </section>

    <section aria-labelledby="side-title">
      <h2 id="side-title">Selected-Side HOME/AWAY Counts And Correctness</h2>
      {_slice_table(payload["slices"]["selected_side_by_model"], "selected_side", "Selected Side", "No selected-side rows were available.")}
    </section>

    <section aria-labelledby="team-title">
      <h2 id="team-title">Top Teams By Exposure</h2>
      {_team_table(payload["slices"]["top_team_exposure"])}
    </section>

    <section aria-labelledby="correct-title">
      <h2 id="correct-title">Top Correct High-Confidence Historical Examples</h2>
      {_examples_table(payload["examples"]["top_correct_high_confidence"])}
    </section>

    <section aria-labelledby="incorrect-title">
      <h2 id="incorrect-title">Top Incorrect High-Confidence Historical Examples</h2>
      {_examples_table(payload["examples"]["top_incorrect_high_confidence"])}
    </section>

    <section aria-labelledby="limitations-title">
      <h2 id="limitations-title">Limitations</h2>
      {_limitations_list(payload["limitations"])}
    </section>
  </main>
</body>
</html>
"""


def write_outputs(payload: dict[str, Any]) -> list[Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_HTML.write_text(render_html(payload), encoding="utf-8")
    return [OUT_HTML, OUT_JSON]


def main() -> int:
    missing = [path for path in REQUIRED_INPUTS if not path.exists()]
    if missing:
        print("P210A_BLOCKED_MISSING_SOURCE_ARTIFACTS", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 2

    payload = build_dashboard_payload(
        _read_json(SCORECARD_JSON),
        _read_csv(MODEL_COMPARISON_CSV),
        _read_csv(PREDICTIONS_CSV),
        _read_json(P208_VIEWER_JSON),
        _read_json(P209_DASHBOARD_JSON),
    )
    written = write_outputs(payload)

    print("P210-A HISTORICAL MLB SLICE ANALYSIS")
    print(f"dashboard HTML: {written[0]}")
    print(f"dashboard JSON: {written[1]}")
    print(f"prediction rows read: {payload['prediction_rows_read']}")
    print(f"models analyzed: {len(payload['models_analyzed'])}")
    print("all examples are historical replay/backtest only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
