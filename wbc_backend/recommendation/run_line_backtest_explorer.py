"""Local-only explorer for existing 2025 historical run-line predictions.

This module never trains a model or creates predictions.  It reads the tracked
P226-A prediction ledger and P235-A package metadata, normalizes the known
schema, filters rows, and computes descriptive metrics.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "report" / "p226a_run_line_total_predictions.csv"
DEFAULT_PACKAGE = ROOT / "report" / "p235a_final_2025_runline_backtest_package.json"

LIMITATION_LABELS = (
    "2025-ONLY",
    "HISTORICAL_PAPER_ONLY",
    "ODDS_PROVENANCE_UNVERIFIED",
    "NOT_TRUE_PIT",
    "NOT_BETTING_EDGE",
    "NOT_FUTURE_PREDICTION",
    "NOT_LIVE",
    "NOT_PRODUCTION",
    "NOT_MULTI_SEASON_VALIDATION",
)


class ExplorerError(ValueError):
    """Raised when an input schema or requested filter is unsupported."""


@dataclass(frozen=True)
class ExplorerDataset:
    rows: tuple[dict[str, Any], ...]
    source_ledger: str
    package_path: str
    package_limitation_labels: tuple[str, ...]


def _display_path(path: Path) -> str:
    """Use stable repo-relative paths for tracked inputs when possible."""
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
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is not a probability: {value!r}"
        ) from exc
    if not 0.0 <= result <= 1.0:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is outside [0, 1]: {value!r}"
        )
    return result


def _parse_date(value: str, row_number: int) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} game_date is not YYYY-MM-DD: {value!r}"
        ) from exc
    if parsed.year != 2025:
        raise ExplorerError(
            f"OUT_OF_SCOPE_YEAR: row {row_number} has {value!r}; this explorer is 2025-only"
        )
    return parsed.isoformat()


def load_explorer_dataset(
    ledger_path: Path = DEFAULT_LEDGER,
    package_path: Path = DEFAULT_PACKAGE,
) -> ExplorerDataset:
    """Load and normalize the existing P226-A Poisson run-line rows.

    P235-A is read to verify the consolidated package limitations.  No source
    artifact is written or modified.
    """
    ledger_path = Path(ledger_path)
    package_path = Path(package_path)
    if not ledger_path.is_file():
        raise ExplorerError(f"MISSING_INPUT: prediction ledger not found: {ledger_path}")
    if not package_path.is_file():
        raise ExplorerError(f"MISSING_INPUT: P235-A package not found: {package_path}")

    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExplorerError(f"INVALID_INPUT: cannot read P235-A package: {package_path}: {exc}") from exc
    package_labels = tuple(package.get("limitation_labels", ()))
    missing_labels = sorted(set(LIMITATION_LABELS) - set(package_labels))
    if missing_labels:
        raise ExplorerError(
            "INVALID_P235_PACKAGE: missing limitation labels: " + ", ".join(missing_labels)
        )

    required = {
        "game_id", "game_date", "home_team", "away_team", "market", "model_name",
        "predicted_primary_probability", "predicted_side", "actual_side", "is_push", "correct",
    }
    normalized: list[dict[str, Any]] = []
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, required, ledger_path)
        for row_number, raw in enumerate(reader, start=2):
            if raw["market"] != "run_line" or raw["model_name"] != "poisson_team_rate_model":
                continue
            if raw["is_push"].strip().lower() not in {"false", "0"}:
                continue
            probability = _parse_probability(
                raw["predicted_primary_probability"], "predicted_primary_probability", row_number
            )
            predicted_side = raw["predicted_side"].strip().upper()
            actual_side = raw["actual_side"].strip().upper()
            if predicted_side not in {"HOME", "AWAY"} or actual_side not in {"HOME", "AWAY"}:
                raise ExplorerError(
                    f"INVALID_VALUE: row {row_number} side columns must be HOME or AWAY"
                )
            expected_side = "HOME" if probability >= 0.5 else "AWAY"
            if predicted_side != expected_side:
                raise ExplorerError(
                    f"INCONSISTENT_SCHEMA: row {row_number} predicted_side conflicts with probability"
                )
            correct = raw["correct"].strip()
            if correct not in {"0", "1"}:
                raise ExplorerError(f"INVALID_VALUE: row {row_number} correct must be 0 or 1")
            normalized.append(
                {
                    "game_id": raw["game_id"],
                    "game_date": _parse_date(raw["game_date"], row_number),
                    "home_team": raw["home_team"],
                    "away_team": raw["away_team"],
                    "line_value": raw.get("line_value", ""),
                    "model_name": raw["model_name"],
                    "predicted_home_probability": probability,
                    "predicted_side": predicted_side,
                    "predicted_side_probability": max(probability, 1.0 - probability),
                    "actual_side": actual_side,
                    "correct": int(correct),
                }
            )

    if not normalized:
        raise ExplorerError(
            "NO_SUPPORTED_ROWS: no decided run_line rows for poisson_team_rate_model were found"
        )
    normalized.sort(key=lambda row: (row["game_date"], row["game_id"]))
    return ExplorerDataset(
        rows=tuple(normalized),
        source_ledger=_display_path(ledger_path),
        package_path=_display_path(package_path),
        package_limitation_labels=package_labels,
    )


def parse_filter_date(value: str | None, option_name: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ExplorerError(f"INVALID_FILTER: {option_name} must be YYYY-MM-DD: {value!r}") from exc
    if parsed.year != 2025:
        raise ExplorerError(f"INVALID_FILTER: {option_name} must be within 2025")
    return parsed.isoformat()


def filter_rows(
    rows: Iterable[dict[str, Any]],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    team: str | None = None,
    min_confidence: float | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Apply inclusive filters and a deterministic highest-confidence top-N."""
    start = parse_filter_date(date_from, "--date-from")
    end = parse_filter_date(date_to, "--date-to")
    if start and end and start > end:
        raise ExplorerError("INVALID_FILTER: --date-from cannot be after --date-to")
    if min_confidence is not None and not 0.5 <= min_confidence <= 1.0:
        raise ExplorerError("INVALID_FILTER: --min-confidence must be between 0.5 and 1.0")
    if top_n is not None and top_n < 1:
        raise ExplorerError("INVALID_FILTER: --top-n must be a positive integer")

    needle = team.casefold().strip() if team else None
    selected = []
    for row in rows:
        if start and row["game_date"] < start:
            continue
        if end and row["game_date"] > end:
            continue
        if needle and needle not in row["home_team"].casefold() and needle not in row["away_team"].casefold():
            continue
        if min_confidence is not None and row["predicted_side_probability"] < min_confidence:
            continue
        selected.append(dict(row))

    selected.sort(
        key=lambda row: (-row["predicted_side_probability"], row["game_date"], row["game_id"])
    )
    if top_n is not None:
        selected = selected[:top_n]
    return selected


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    selected = list(rows)
    count = len(selected)
    if not count:
        return {
            "row_count": 0,
            "accuracy": None,
            "brier_score": None,
            "average_predicted_probability": None,
            "average_predicted_home_probability": None,
            "home_cover_rate": None,
            "away_cover_rate": None,
            "descriptive_base_rate_reference": "UNAVAILABLE_EMPTY_FILTERED_SET",
        }
    accuracy = sum(row["correct"] for row in selected) / count
    brier = sum(
        (row["predicted_home_probability"] - (1.0 if row["actual_side"] == "HOME" else 0.0)) ** 2
        for row in selected
    ) / count
    home_rate = sum(row["actual_side"] == "HOME" for row in selected) / count
    return {
        "row_count": count,
        "accuracy": accuracy,
        "brier_score": brier,
        "average_predicted_probability": sum(
            row["predicted_side_probability"] for row in selected
        ) / count,
        "average_predicted_home_probability": sum(
            row["predicted_home_probability"] for row in selected
        ) / count,
        "home_cover_rate": home_rate,
        "away_cover_rate": 1.0 - home_rate,
        "descriptive_base_rate_reference": "POST_HOC_ACTUAL_SIDE_RATE_REFERENCE_ONLY",
    }


def build_output_payload(
    dataset: ExplorerDataset,
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "explorer": "P236-A Historical Run Line Backtest Explorer",
        "metadata": {
            "source_ledger": dataset.source_ledger,
            "source_package": dataset.package_path,
            "source_rows_loaded": len(dataset.rows),
            "generates_new_predictions": False,
            "limitation_labels": list(LIMITATION_LABELS),
        },
        "filters": filters,
        "summary": summarize_rows(rows),
        "filtered_rows": rows,
    }


def write_outputs(payload: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    """Write deterministic JSON and normalized CSV outputs."""
    json_path, csv_path = Path(json_path), Path(csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = [
        "game_id", "game_date", "home_team", "away_team", "line_value", "model_name",
        "predicted_home_probability", "predicted_side", "predicted_side_probability",
        "actual_side", "correct",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(payload["filtered_rows"])
