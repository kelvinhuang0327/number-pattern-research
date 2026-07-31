"""Result-only local simulator for existing historical run-line predictions.

This module only turns already-generated historical prediction rows into a
paper decision ledger.  It intentionally does not price bets, compute P/L, or
derive an edge.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.run_line_backtest_explorer import (
    DEFAULT_LEDGER,
    DEFAULT_PACKAGE,
    ROOT,
    ExplorerError,
    LIMITATION_LABELS as EXPLORER_LIMITATION_LABELS,
    filter_rows,
    load_explorer_dataset,
)


DEFAULT_OUTPUT_JSON = ROOT / "report" / "p237a_paper_strategy_simulator_summary.json"
DEFAULT_OUTPUT_CSV = ROOT / "report" / "p237a_paper_strategy_decisions.csv"

DECISION_FIELDNAMES = [
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "market",
    "line_value",
    "model_name",
    "predicted_side",
    "predicted_side_probability",
    "actual_side",
    "correct",
    "stake_units",
    "pnl_units",
    "settlement_status",
]

LIMITATION_LABELS = [
    "2025-only",
    "historical paper-only",
    "odds provenance unverified",
    "not true-PIT",
    "not betting edge",
    "not future prediction",
    "not live",
    "not production",
    "not real betting",
    "not multi-season validation",
]

ROI_UNAVAILABLE_REASON = (
    "NO_PER_BET_PRICE_IN_INPUT_LEDGER; "
    "ONLY_LOCAL_PRICE_SOURCE_IS_POST_GAME_UNVERIFIED_SNAPSHOT(is_verified_real=False); "
    "FLAT_PRICE_ASSUMPTION_REJECTED_AS_SYSTEMATICALLY_WRONG_FOR_RUN_LINE"
)
SETTLEMENT_STATUS = "RESULT_ONLY_NO_PRICE"
THRESHOLD_SWEEP = (0.5, 0.6, 0.7, 0.8)


@dataclass(frozen=True)
class PaperStrategyDataset:
    rows: tuple[dict[str, Any], ...]
    source_csv: str
    source_package: str


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _require_columns(fieldnames: Iterable[str] | None, required: set[str], path: Path) -> None:
    available = set(fieldnames or ())
    missing = sorted(required - available)
    if missing:
        raise ExplorerError(
            f"UNSUPPORTED_SCHEMA: {path} is missing required columns: {', '.join(missing)}; "
            f"available columns: {', '.join(sorted(available))}"
        )


def _parse_probability(value: str, column: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is not a probability: {value!r}"
        ) from exc
    if not 0.0 <= parsed <= 1.0:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is outside [0, 1]: {value!r}"
        )
    return parsed


def _parse_correct(value: str, row_number: int) -> int:
    text = str(value).strip()
    if text not in {"0", "1"}:
        raise ExplorerError(f"INVALID_VALUE: row {row_number} correct must be 0 or 1")
    return int(text)


def _parse_2025_date(value: str, row_number: int) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} game_date is not YYYY-MM-DD: {value!r}"
        ) from exc
    if parsed.year != 2025:
        raise ExplorerError(
            f"OUT_OF_SCOPE_YEAR: row {row_number} has {value!r}; this simulator is 2025-only"
        )
    return parsed.isoformat()


def _validate_source_package(package_path: Path) -> str:
    package_path = Path(package_path)
    if not package_path.is_file():
        raise ExplorerError(f"MISSING_INPUT: P235-A package not found: {package_path}")
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExplorerError(f"INVALID_INPUT: cannot read P235-A package: {package_path}: {exc}") from exc
    missing_labels = sorted(set(EXPLORER_LIMITATION_LABELS) - set(package.get("limitation_labels", ())))
    if missing_labels:
        raise ExplorerError(
            "INVALID_P235_PACKAGE: missing limitation labels: " + ", ".join(missing_labels)
        )
    return _display_path(package_path)


def _normalized_rows_from_csv(source_csv: Path) -> tuple[dict[str, Any], ...]:
    required = {
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "line_value",
        "model_name",
        "predicted_home_probability",
        "predicted_side",
        "predicted_side_probability",
        "actual_side",
        "correct",
    }
    rows: list[dict[str, Any]] = []
    with source_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, required, source_csv)
        for row_number, raw in enumerate(reader, start=2):
            predicted_side = raw["predicted_side"].strip().upper()
            actual_side = raw["actual_side"].strip().upper()
            if predicted_side not in {"HOME", "AWAY"} or actual_side not in {"HOME", "AWAY"}:
                raise ExplorerError(
                    f"INVALID_VALUE: row {row_number} side columns must be HOME or AWAY"
                )
            rows.append(
                {
                    "game_id": raw["game_id"],
                    "game_date": _parse_2025_date(raw["game_date"], row_number),
                    "home_team": raw["home_team"],
                    "away_team": raw["away_team"],
                    "market": "run_line",
                    "line_value": raw["line_value"],
                    "model_name": raw["model_name"],
                    "predicted_home_probability": _parse_probability(
                        raw["predicted_home_probability"],
                        "predicted_home_probability",
                        row_number,
                    ),
                    "predicted_side": predicted_side,
                    "predicted_side_probability": _parse_probability(
                        raw["predicted_side_probability"],
                        "predicted_side_probability",
                        row_number,
                    ),
                    "actual_side": actual_side,
                    "correct": _parse_correct(raw["correct"], row_number),
                }
            )
    rows.sort(key=lambda row: (row["game_date"], row["game_id"]))
    return tuple(rows)


def load_paper_strategy_dataset(
    source_csv: Path = DEFAULT_LEDGER,
    package_path: Path = DEFAULT_PACKAGE,
) -> PaperStrategyDataset:
    source_csv = Path(source_csv)
    if not source_csv.is_file():
        raise ExplorerError(f"MISSING_INPUT: source CSV not found: {source_csv}")

    with source_csv.open(newline="", encoding="utf-8") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []

    if "predicted_primary_probability" in fieldnames:
        explorer_dataset = load_explorer_dataset(source_csv, package_path)
        rows = tuple({**row, "market": "run_line"} for row in explorer_dataset.rows)
        source_package = explorer_dataset.package_path
    else:
        source_package = _validate_source_package(package_path)
        rows = _normalized_rows_from_csv(source_csv)

    return PaperStrategyDataset(
        rows=rows,
        source_csv=_display_path(source_csv),
        source_package=source_package,
    )


def _summary_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    selected = list(rows)
    count = len(selected)
    if not count:
        return {
            "hit_rate": None,
            "brier_score": None,
            "average_confidence": None,
            "side_distribution": {"HOME": 0, "AWAY": 0},
        }
    side_distribution = {
        "HOME": sum(row["predicted_side"] == "HOME" for row in selected),
        "AWAY": sum(row["predicted_side"] == "AWAY" for row in selected),
    }
    return {
        "hit_rate": sum(row["correct"] for row in selected) / count,
        "brier_score": sum(
            (
                row["predicted_home_probability"]
                - (1.0 if row["actual_side"] == "HOME" else 0.0)
            )
            ** 2
            for row in selected
        )
        / count,
        "average_confidence": sum(row["predicted_side_probability"] for row in selected) / count,
        "side_distribution": side_distribution,
    }


def _decision_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for row in rows:
        decisions.append(
            {
                "game_id": row["game_id"],
                "game_date": row["game_date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "market": row.get("market", "run_line"),
                "line_value": row["line_value"],
                "model_name": row["model_name"],
                "predicted_side": row["predicted_side"],
                "predicted_side_probability": row["predicted_side_probability"],
                "actual_side": row["actual_side"],
                "correct": row["correct"],
                "stake_units": 1.0,
                "pnl_units": None,
                "settlement_status": SETTLEMENT_STATUS,
            }
        )
    return decisions


def make_decisions(rows: Iterable[dict[str, Any]], min_confidence: float) -> list[dict[str, Any]]:
    selected = filter_rows(rows, min_confidence=min_confidence, top_n=None)
    return _decision_rows(selected)


def _threshold_sweep(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_rows = list(rows)
    sweep = []
    for threshold in THRESHOLD_SWEEP:
        threshold_rows = filter_rows(selected_rows, min_confidence=threshold, top_n=None)
        metrics = _summary_metrics(threshold_rows)
        sweep.append(
            {
                "min_confidence": threshold,
                "status": "IN_SAMPLE_DESCRIPTIVE_ONLY",
                "decisions_count": len(threshold_rows),
                **metrics,
            }
        )
    return sweep


def build_output_payload(
    dataset: PaperStrategyDataset,
    *,
    min_confidence: float,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not 0.5 <= min_confidence <= 1.0:
        raise ExplorerError("INVALID_FILTER: --min-confidence must be between 0.5 and 1.0")

    base_rows = filter_rows(dataset.rows, date_from=date_from, date_to=date_to, top_n=None)
    selected_rows = filter_rows(base_rows, min_confidence=min_confidence, top_n=None)
    decisions = _decision_rows(selected_rows)
    metrics = _summary_metrics(selected_rows)
    payload = {
        "simulator": "P237-A Result-Only Historical Paper Strategy Simulator",
        "metadata": {
            "source_csv": dataset.source_csv,
            "source_package": dataset.source_package,
            "source_rows_loaded": len(dataset.rows),
            "generates_new_predictions": False,
            "limitation_labels": LIMITATION_LABELS,
        },
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "min_confidence": min_confidence,
        },
        "decisions_count": len(decisions),
        **metrics,
        "stake_units_total": float(len(decisions)),
        "roi": None,
        "roi_status": "ROI_UNAVAILABLE",
        "roi_unavailable_reason": ROI_UNAVAILABLE_REASON,
        "threshold_sweep": _threshold_sweep(base_rows),
    }
    return payload, decisions


def write_outputs(payload: dict[str, Any], decisions: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    json_path, csv_path = Path(json_path), Path(csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for decision in decisions:
            row = dict(decision)
            row["pnl_units"] = ""
            writer.writerow(row)
