#!/usr/bin/env python3
"""Build the P209-A static MLB scorecard dashboard.

The dashboard is a deterministic, self-contained HTML view over committed
historical replay artifacts. It does not train models, call providers, write a
database, publish tickets, or activate any production workflow.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"

SCORECARD_JSON = REPORT_DIR / "p207a_local_retrain_scorecard.json"
MODEL_COMPARISON_CSV = REPORT_DIR / "p207a_local_retrain_model_comparison.csv"
PREDICTIONS_CSV = REPORT_DIR / "p207a_local_retrain_predictions.csv"
P208_VIEWER_JSON = REPORT_DIR / "p208a_visible_scorecard_result_viewer.json"

OUT_HTML = REPORT_DIR / "p209a_static_scorecard_dashboard.html"
OUT_JSON = REPORT_DIR / "p209a_static_scorecard_dashboard.json"

TITLE = "MLB Local Retrain Historical Scorecard Dashboard"
SCOPE = "LOCAL_HISTORICAL_REPLAY_ONLY"
DISCLAIMER = (
    "Historical replay/backtest only. This dashboard summarizes completed MLB "
    "games from committed local artifacts and is not for live use."
)
SAMPLE_LABEL = "historical replay / backtest only"
TOP_SAMPLE_LIMIT = 14
BANDS = ("LOW", "MEDIUM", "HIGH")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escape_html(value: Any) -> str:
    """Escape data-derived values before inserting them into HTML."""
    return html.escape(str(value), quote=True)


def _round_metric(value: Any) -> float:
    return round(float(value), 6)


def _intish(value: Any) -> int:
    return int(value)


def _is_reference_metric(row: dict[str, str]) -> bool:
    name = row.get("model_name", "")
    return "REFERENCE_UNVERIFIED" in name or row.get("train_rows") == "0"


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
        "reference_only": _is_reference_metric(row),
        "notes": row["notes"],
    }


def _selected_probability(row: dict[str, str]) -> float:
    home_prob = float(row["predicted_home_win_probability"])
    return home_prob if row["selected_side"] == "HOME" else 1.0 - home_prob


def _sample_row(row: dict[str, str]) -> dict[str, Any]:
    selected_probability = _selected_probability(row)
    return {
        "label": SAMPLE_LABEL,
        "game_date": row["game_date"],
        "game_id": row["game_id"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "model_name": row["model_name"],
        "predicted_home_win_probability": _round_metric(row["predicted_home_win_probability"]),
        "selected_side": row["selected_side"],
        "selected_side_probability": _round_metric(selected_probability),
        "confidence_band": row["confidence_band"],
        "actual_home_win": _intish(row["actual_home_win"]),
        "correct": _intish(row["correct"]),
        "learning_guard_status": row["learning_guard_status"],
        "provenance_contract_version": row["provenance_contract_version"],
    }


def _sort_predictions(rows: list[dict[str, str]], model_name: str) -> list[dict[str, str]]:
    scoped = [row for row in rows if row["model_name"] == model_name]
    return sorted(
        scoped,
        key=lambda row: (
            -_selected_probability(row),
            row["game_date"],
            row["game_id"],
            row["selected_side"],
        ),
    )


def _best_accuracy(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        candidates,
        key=lambda row: (row["accuracy"], -row["brier_score"], row["model_name"]),
    )


def _best_brier(scorecard: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best_brier_name = scorecard.get("best_by_brier")
    from_scorecard = next(
        (row for row in candidates if row["model_name"] == best_brier_name),
        None,
    )
    if from_scorecard:
        return from_scorecard
    return min(
        candidates,
        key=lambda row: (row["brier_score"], -row["accuracy"], row["model_name"]),
    )


def _band_summary(scorecard: dict[str, Any]) -> dict[str, dict[str, int | float]]:
    summary = scorecard.get("best_confidence_band_breakdown", {})
    result: dict[str, dict[str, int | float]] = {}
    for band in BANDS:
        item = summary.get(band, {"n": 0, "correct": 0})
        n = int(item["n"])
        correct = int(item["correct"])
        result[band] = {
            "n": n,
            "correct": correct,
            "accuracy": _round_metric(correct / n) if n else 0.0,
        }
    return result


def _selected_side_counts(scorecard: dict[str, Any]) -> dict[str, int]:
    counts = scorecard.get("best_selected_side_distribution", {})
    return {
        "AWAY": int(counts.get("AWAY", 0)),
        "HOME": int(counts.get("HOME", 0)),
    }


def _p208_consistency(
    p208_payload: dict[str, Any],
    best_accuracy: dict[str, Any],
    best_brier: dict[str, Any],
) -> dict[str, bool]:
    return {
        "best_accuracy_model_matches_p208": (
            p208_payload.get("best_accuracy_model", {}).get("model_name")
            == best_accuracy["model_name"]
        ),
        "best_brier_model_matches_p208": (
            p208_payload.get("best_brier_model", {}).get("model_name")
            == best_brier["model_name"]
        ),
    }


def build_dashboard_payload(
    scorecard: dict[str, Any],
    model_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
    p208_payload: dict[str, Any],
) -> dict[str, Any]:
    leaderboard = [_metric_row(row) for row in model_rows]
    candidate_models = [row for row in leaderboard if not row["reference_only"]]
    if not candidate_models:
        raise ValueError("P209A_BLOCKED_NO_MODEL_METRICS")

    best_accuracy = _best_accuracy(candidate_models)
    best_brier = _best_brier(scorecard, candidate_models)
    examples = [
        _sample_row(row)
        for row in _sort_predictions(prediction_rows, best_brier["model_name"])[:TOP_SAMPLE_LIMIT]
    ]

    return {
        "task": "P209-A static scorecard dashboard",
        "title": TITLE,
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "source_artifacts": [
            "P207-A: report/p207a_local_retrain_scorecard.json",
            "P207-A: report/p207a_local_retrain_model_comparison.csv",
            "P207-A: report/p207a_local_retrain_predictions.csv",
            "P208-A: report/p208a_visible_scorecard_result_viewer.json",
        ],
        "split": scorecard["split"],
        "eval_rows": int(scorecard["eval_rows"]),
        "leaderboard": leaderboard,
        "best_accuracy_model": best_accuracy,
        "best_brier_model": best_brier,
        "confidence_band_summary": _band_summary(scorecard),
        "selected_side_counts": _selected_side_counts(scorecard),
        "top_historical_examples": examples,
        "p208_consistency": _p208_consistency(p208_payload, best_accuracy, best_brier),
        "claim_status": {
            "historical_only": True,
            "provider_called": False,
            "db_written": False,
            "production_enabled": False,
            "ticket_mutated": False,
        },
    }


def _format_pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _fmt_float(value: Any) -> str:
    return f"{float(value):.6f}"


def _metric_card(label: str, model: dict[str, Any], metric_label: str, metric_value: str) -> str:
    return (
        '<article class="summary-card">'
        f"<span>{escape_html(label)}</span>"
        f"<strong>{escape_html(model['model_name'])}</strong>"
        f"<p>{escape_html(metric_label)}: {escape_html(metric_value)}</p>"
        "</article>"
    )


def _source_list(payload: dict[str, Any]) -> str:
    items = "\n".join(
        f"<li><code>{escape_html(source)}</code></li>"
        for source in payload["source_artifacts"]
    )
    return f"<ul>{items}</ul>"


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
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr>"
        "<th>Model</th><th>Accuracy</th><th>Brier</th><th>Log Loss</th>"
        "<th>Calibration Error</th><th>Coverage</th><th>Reference Only</th><th>Notes</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def _confidence_band_section(summary: dict[str, dict[str, int | float]]) -> str:
    cards = []
    for band in BANDS:
        item = summary[band]
        cards.append(
            '<article class="mini-card">'
            f"<span>{escape_html(band)}</span>"
            f"<strong>{int(item['correct'])} / {int(item['n'])}</strong>"
            f"<p>{_format_pct(item['accuracy'])} correct</p>"
            "</article>"
        )
    return f'<div class="mini-grid">{"".join(cards)}</div>'


def _selected_side_section(counts: dict[str, int]) -> str:
    total = counts["AWAY"] + counts["HOME"]
    rows = []
    for side in ("HOME", "AWAY"):
        count = counts[side]
        pct = count / total if total else 0.0
        rows.append(
            '<article class="mini-card">'
            f"<span>{escape_html(side)}</span>"
            f"<strong>{count}</strong>"
            f"<p>{_format_pct(pct)} of selected sides</p>"
            "</article>"
        )
    return f'<div class="mini-grid">{"".join(rows)}</div>'


def _examples_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        game = f"{row['away_team']} @ {row['home_team']}"
        body.append(
            "<tr>"
            f"<td>{escape_html(row['label'])}</td>"
            f"<td>{escape_html(row['game_date'])}</td>"
            f"<td>{escape_html(game)}</td>"
            f"<td>{escape_html(row['selected_side'])}</td>"
            f"<td>{_format_pct(row['selected_side_probability'])}</td>"
            f"<td>{escape_html(row['confidence_band'])}</td>"
            f"<td>{'Yes' if row['correct'] else 'No'}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr>"
        "<th>Label</th><th>Date</th><th>Game</th><th>Selected Side</th>"
        "<th>Selected Probability</th><th>Band</th><th>Correct</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def render_html(payload: dict[str, Any]) -> str:
    best_accuracy = payload["best_accuracy_model"]
    best_brier = payload["best_brier_model"]
    split = payload["split"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(payload["title"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5b6776;
      --line: #d9dee8;
      --accent: #176b87;
      --accent-2: #8b5e34;
      --good: #1f7a4d;
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
      font-size: clamp(28px, 4vw, 46px);
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    p {{ margin: 0; }}
    .disclaimer {{
      max-width: 900px;
      color: var(--muted);
      font-weight: 650;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .pill {{
      border: 1px solid var(--line);
      background: #f2f5f8;
      border-radius: 999px;
      color: #243241;
      font-size: 13px;
      padding: 6px 10px;
    }}
    section {{
      margin-top: 24px;
      padding: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .summary-grid, .mini-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .summary-card, .mini-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 118px;
      background: #fbfcfe;
    }}
    .summary-card span, .mini-card span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .summary-card strong, .mini-card strong {{
      display: block;
      margin-top: 8px;
      font-size: 22px;
      overflow-wrap: anywhere;
    }}
    .summary-card p, .mini-card p {{
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
      min-width: 820px;
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
      background: #eef3f6;
      color: #253241;
      font-size: 13px;
    }}
    td:last-child {{ white-space: normal; min-width: 240px; }}
    code {{
      background: #eef3f6;
      border-radius: 4px;
      padding: 2px 5px;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    li + li {{ margin-top: 6px; }}
    .status {{
      border-left: 4px solid var(--good);
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape_html(payload["title"])}</h1>
    <p class="disclaimer">{escape_html(payload["disclaimer"])}</p>
    <div class="meta">
      <span class="pill">Scope: {escape_html(payload["scope"])}</span>
      <span class="pill">Train: {escape_html(split["train_period"][0])} to {escape_html(split["train_period"][1])}</span>
      <span class="pill">Test: {escape_html(split["test_period"][0])} to {escape_html(split["test_period"][1])}</span>
      <span class="pill">Evaluation rows: {int(payload["eval_rows"])}</span>
    </div>
  </header>
  <main>
    <section aria-labelledby="summary-title">
      <h2 id="summary-title">Summary Cards</h2>
      <div class="summary-grid">
        {_metric_card("Best Accuracy", best_accuracy, "Accuracy", _format_pct(best_accuracy["accuracy"]))}
        {_metric_card("Best Brier", best_brier, "Brier score", _fmt_float(best_brier["brier_score"]))}
      </div>
    </section>

    <section aria-labelledby="leaderboard-title">
      <h2 id="leaderboard-title">Model Leaderboard</h2>
      {_leaderboard_table(payload["leaderboard"])}
    </section>

    <section aria-labelledby="band-title">
      <h2 id="band-title">Confidence-Band Correctness</h2>
      {_confidence_band_section(payload["confidence_band_summary"])}
    </section>

    <section aria-labelledby="side-title">
      <h2 id="side-title">Selected-Side Counts</h2>
      {_selected_side_section(payload["selected_side_counts"])}
    </section>

    <section aria-labelledby="examples-title">
      <h2 id="examples-title">Top Historical Examples Sorted By Confidence</h2>
      {_examples_table(payload["top_historical_examples"])}
    </section>

    <section aria-labelledby="source-title">
      <h2 id="source-title">P207-A And P208-A Source Artifacts</h2>
      {_source_list(payload)}
    </section>

    <section aria-labelledby="status-title" class="status">
      <h2 id="status-title">Run Status</h2>
      <p>All displayed rows are labeled historical replay/backtest only. Provider calls, database writes, ticket mutation, and production activation are false for this dashboard build.</p>
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
    inputs = (SCORECARD_JSON, MODEL_COMPARISON_CSV, PREDICTIONS_CSV, P208_VIEWER_JSON)
    missing = [path for path in inputs if not path.exists()]
    if missing:
        print("P209A_BLOCKED_MISSING_SOURCE_ARTIFACTS", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 2

    payload = build_dashboard_payload(
        _read_json(SCORECARD_JSON),
        _read_csv(MODEL_COMPARISON_CSV),
        _read_csv(PREDICTIONS_CSV),
        _read_json(P208_VIEWER_JSON),
    )
    written = write_outputs(payload)

    print("P209-A STATIC MLB SCORECARD DASHBOARD")
    print(f"dashboard HTML: {written[0]}")
    print(f"dashboard JSON: {written[1]}")
    print(
        "best accuracy model: "
        f"{payload['best_accuracy_model']['model_name']} "
        f"({_format_pct(payload['best_accuracy_model']['accuracy'])})"
    )
    print(
        "best Brier model: "
        f"{payload['best_brier_model']['model_name']} "
        f"({_fmt_float(payload['best_brier_model']['brier_score'])})"
    )
    print("all examples are historical replay/backtest only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
