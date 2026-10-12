#!/usr/bin/env python3
"""P208-A visible local scorecard result viewer.

Reads committed P207-A historical replay artifacts and writes a compact
owner-facing report. This script does not train models, query providers,
write a DB, publish tickets, or create forward-looking recommendations.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "report"
SCORECARD_JSON = REPORT_DIR / "p207a_local_retrain_scorecard.json"
MODEL_COMPARISON_CSV = REPORT_DIR / "p207a_local_retrain_model_comparison.csv"
PREDICTIONS_CSV = REPORT_DIR / "p207a_local_retrain_predictions.csv"
OUT_MD = REPORT_DIR / "p208a_visible_scorecard_result_viewer.md"
OUT_JSON = REPORT_DIR / "p208a_visible_scorecard_result_viewer.json"

DISCLAIMER = (
    "Historical replay/backtest only; not for live use and not a future betting claim."
)
SAMPLE_LABEL = "historical replay / backtest only"
TOP_SAMPLE_LIMIT = 12


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _intish(value: Any) -> int:
    return int(value)


def _is_reference_metric(row: dict[str, str]) -> bool:
    name = row.get("model_name", "")
    return "REFERENCE_UNVERIFIED" in name or row.get("train_rows") == "0"


def _round_metric(value: Any) -> float:
    return round(float(value), 6)


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
    home_prob = float(row["predicted_home_win_probability"])
    selected_prob = _selected_probability(row)
    return {
        "label": SAMPLE_LABEL,
        "game_date": row["game_date"],
        "game_id": row["game_id"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "model_name": row["model_name"],
        "predicted_home_win_probability": _round_metric(home_prob),
        "selected_side": row["selected_side"],
        "selected_side_probability": _round_metric(selected_prob),
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


def build_viewer_payload(
    scorecard: dict[str, Any],
    model_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
) -> dict[str, Any]:
    leaderboard = [_metric_row(row) for row in model_rows]
    candidate_models = [row for row in leaderboard if not row["reference_only"]]
    if not candidate_models:
        raise ValueError("P208A_BLOCKED_NO_MODEL_METRICS")

    best_accuracy = max(candidate_models, key=lambda row: (row["accuracy"], -row["brier_score"], row["model_name"]))
    best_brier_name = scorecard.get("best_by_brier")
    best_brier = next(
        (row for row in candidate_models if row["model_name"] == best_brier_name),
        min(candidate_models, key=lambda row: (row["brier_score"], -row["accuracy"], row["model_name"])),
    )

    sample_predictions = [
        _sample_row(row)
        for row in _sort_predictions(prediction_rows, best_brier["model_name"])[:TOP_SAMPLE_LIMIT]
    ]

    return {
        "task": "P208-A visible scorecard result viewer",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "disclaimer": DISCLAIMER,
        "source_artifacts": [
            SCORECARD_JSON.name,
            MODEL_COMPARISON_CSV.name,
            PREDICTIONS_CSV.name,
        ],
        "split": scorecard["split"],
        "leaderboard": leaderboard,
        "best_accuracy_model": best_accuracy,
        "best_brier_model": best_brier,
        "confidence_band_summary": scorecard["best_confidence_band_breakdown"],
        "selected_side_distribution": scorecard["best_selected_side_distribution"],
        "sample_predictions": sample_predictions,
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


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# P208-A Visible MLB Scorecard Result Viewer",
        "",
        f"**Scope:** {payload['scope']}",
        "",
        f"**Disclaimer:** {payload['disclaimer']}",
        "",
        "## Source Artifacts",
        "",
    ]
    lines.extend(f"- `{name}`" for name in payload["source_artifacts"])
    lines.extend([
        "",
        "## Model Leaderboard",
        "",
        "| Model | Accuracy | Brier | Log Loss | Calibration Error | Coverage | Reference Only |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])
    for row in payload["leaderboard"]:
        lines.append(
            f"| `{row['model_name']}` | {_format_pct(row['accuracy'])} | "
            f"{row['brier_score']:.6f} | {row['log_loss']:.6f} | "
            f"{row['calibration_error']:.6f} | {_format_pct(row['coverage'])} | "
            f"{'YES' if row['reference_only'] else 'NO'} |"
        )

    best_acc = payload["best_accuracy_model"]
    best_brier = payload["best_brier_model"]
    lines.extend([
        "",
        "## Best Models",
        "",
        f"- Best accuracy model: `{best_acc['model_name']}` ({_format_pct(best_acc['accuracy'])}).",
        f"- Best Brier model: `{best_brier['model_name']}` ({best_brier['brier_score']:.6f}).",
        "",
        "## Confidence Band Summary",
        "",
        "| Band | Rows | Correct | Accuracy |",
        "|---|---:|---:|---:|",
    ])
    for band in ("LOW", "MEDIUM", "HIGH"):
        item = payload["confidence_band_summary"].get(band, {"n": 0, "correct": 0})
        n = int(item["n"])
        correct = int(item["correct"])
        acc = correct / n if n else 0.0
        lines.append(f"| {band} | {n} | {correct} | {_format_pct(acc)} |")

    side_dist = payload["selected_side_distribution"]
    lines.extend([
        "",
        "## Selected-Side Distribution",
        "",
        f"- HOME: {int(side_dist.get('HOME', 0))}",
        f"- AWAY: {int(side_dist.get('AWAY', 0))}",
        "",
        "## Top Historical Prediction Examples",
        "",
        "| Label | Date | Game | Selected Side | Selected Probability | Band | Correct |",
        "|---|---|---|---|---:|---|---:|",
    ])
    for row in payload["sample_predictions"]:
        game = f"{row['away_team']} @ {row['home_team']}"
        lines.append(
            f"| {row['label']} | {row['game_date']} | {game} | {row['selected_side']} | "
            f"{_format_pct(row['selected_side_probability'])} | {row['confidence_band']} | {row['correct']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> list[Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(payload, OUT_MD)
    return [OUT_MD, OUT_JSON]


def main() -> int:
    missing = [p for p in (SCORECARD_JSON, MODEL_COMPARISON_CSV, PREDICTIONS_CSV) if not p.exists()]
    if missing:
        print("P208A_BLOCKED_MISSING_P207A_ARTIFACTS", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    payload = build_viewer_payload(
        _read_json(SCORECARD_JSON),
        _read_csv(MODEL_COMPARISON_CSV),
        _read_csv(PREDICTIONS_CSV),
    )
    written = write_outputs(payload)

    best_acc = payload["best_accuracy_model"]
    best_brier = payload["best_brier_model"]
    print("P208-A VISIBLE SCORECARD RESULT VIEWER")
    print(DISCLAIMER)
    print(f"best accuracy: {best_acc['model_name']} ({_format_pct(best_acc['accuracy'])})")
    print(f"best Brier: {best_brier['model_name']} ({best_brier['brier_score']:.6f})")
    print(f"confidence bands: {payload['confidence_band_summary']}")
    print(f"selected sides: {payload['selected_side_distribution']}")
    print("top historical examples:")
    for row in payload["sample_predictions"][:5]:
        print(
            f"  {row['game_date']} {row['away_team']} @ {row['home_team']} "
            f"{row['selected_side']} {_format_pct(row['selected_side_probability'])} "
            f"{row['confidence_band']} correct={row['correct']} [{row['label']}]"
        )
    print("wrote:")
    for p in written:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
