"""Result-only descriptive learning summaries for P237-A paper decisions.

This module summarizes already-settled paper decision rows. It does not price
decisions, compute P/L, infer betting edge, or generate future predictions.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from wbc_backend.recommendation.paper_strategy_simulator import ExplorerError, ROOT


DEFAULT_DECISIONS_CSV = ROOT / "report" / "p237a_paper_strategy_decisions.csv"
DEFAULT_OUTPUT_JSON = ROOT / "report" / "p238a_paper_strategy_learning_summary.json"
DEFAULT_OUTPUT_CSV = ROOT / "report" / "p238a_paper_strategy_learning_segments.csv"

DEFAULT_THRESHOLDS = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8)
ROI_UNAVAILABLE_REASON = (
    "RESULT_ONLY_PAPER_DECISIONS_HAVE_NO_PER_BET_PRICE; "
    "P237A_CONTRACT_FORBIDS_PNL_AND_ROI; "
    "ODDS_PROVENANCE_UNVERIFIED"
)
ROI_STATUS = "ROI_UNAVAILABLE"
INTERPRETATION = "IN_SAMPLE_DESCRIPTIVE_ONLY"
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

SEGMENT_FIELDNAMES = [
    "segment_type",
    "segment_key",
    "min_confidence",
    "decisions_count",
    "hit_rate",
    "average_confidence",
    "calibration_gap",
    "home_count",
    "away_count",
    "stake_units_total",
    "roi",
    "roi_status",
    "interpretation_label",
]

CONFIDENCE_BUCKETS = (
    ("0.50_0.60", 0.5, 0.6, False),
    ("0.60_0.70", 0.6, 0.7, False),
    ("0.70_0.80", 0.7, 0.8, False),
    ("0.80_0.90", 0.8, 0.9, False),
    ("0.90_1.00", 0.9, 1.0, True),
)


@dataclass(frozen=True)
class PaperDecision:
    game_id: str
    game_date: str
    predicted_side: str
    confidence: float
    correct: int
    stake_units: float

    @property
    def game_month(self) -> str:
        return self.game_date[:7]


@dataclass(frozen=True)
class PaperLearningDataset:
    decisions: tuple[PaperDecision, ...]
    source_csv: str
    source_sha256: str


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_columns(fieldnames: Iterable[str] | None, required: set[str], path: Path) -> None:
    available = set(fieldnames or ())
    missing = sorted(required - available)
    if missing:
        raise ExplorerError(
            f"UNSUPPORTED_SCHEMA: {path} is missing required columns: {', '.join(missing)}"
        )


def _parse_probability(value: str, column: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is not a probability"
        ) from exc
    if not 0.0 <= parsed <= 1.0:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} column {column} is outside [0, 1]"
        )
    return parsed


def _parse_correct(value: str, row_number: int) -> int:
    text = str(value).strip()
    if text not in {"0", "1"}:
        raise ExplorerError(f"INVALID_VALUE: row {row_number} correct must be 0 or 1")
    return int(text)


def _parse_stake_units(value: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ExplorerError(f"INVALID_VALUE: row {row_number} stake_units is not numeric") from exc
    if parsed < 0:
        raise ExplorerError(f"INVALID_VALUE: row {row_number} stake_units is negative")
    return parsed


def _parse_game_date(value: str, row_number: int) -> str:
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ExplorerError(
            f"INVALID_VALUE: row {row_number} game_date is not YYYY-MM-DD"
        ) from exc
    return text


def _parse_decision(raw: dict[str, str], row_number: int) -> PaperDecision:
    predicted_side = raw["predicted_side"].strip().upper()
    if predicted_side not in {"HOME", "AWAY"}:
        raise ExplorerError(f"INVALID_VALUE: row {row_number} predicted_side must be HOME or AWAY")
    return PaperDecision(
        game_id=raw["game_id"].strip(),
        game_date=_parse_game_date(raw["game_date"], row_number),
        predicted_side=predicted_side,
        confidence=_parse_probability(
            raw["predicted_side_probability"], "predicted_side_probability", row_number
        ),
        correct=_parse_correct(raw["correct"], row_number),
        stake_units=_parse_stake_units(raw["stake_units"], row_number),
    )


def load_paper_decisions(decisions_csv: Path = DEFAULT_DECISIONS_CSV) -> PaperLearningDataset:
    decisions_csv = Path(decisions_csv)
    if not decisions_csv.is_file():
        raise ExplorerError(f"MISSING_INPUT: decisions CSV not found: {decisions_csv}")
    required = {
        "game_id",
        "game_date",
        "predicted_side",
        "predicted_side_probability",
        "correct",
        "stake_units",
    }
    decisions: list[PaperDecision] = []
    with decisions_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, required, decisions_csv)
        for row_number, raw in enumerate(reader, start=2):
            decisions.append(_parse_decision(raw, row_number))
    decisions.sort(key=lambda row: (row.game_date, row.game_id))
    return PaperLearningDataset(
        decisions=tuple(decisions),
        source_csv=_display_path(decisions_csv),
        source_sha256=_sha256(decisions_csv),
    )


def parse_thresholds(raw: str) -> tuple[float, ...]:
    thresholds: list[float] = []
    for item in raw.split(","):
        text = item.strip()
        if not text:
            continue
        try:
            threshold = float(text)
        except ValueError as exc:
            raise ExplorerError(f"INVALID_FILTER: threshold is not numeric: {text!r}") from exc
        if not 0.5 <= threshold <= 1.0:
            raise ExplorerError("INVALID_FILTER: thresholds must be between 0.5 and 1.0")
        thresholds.append(threshold)
    if not thresholds:
        raise ExplorerError("INVALID_FILTER: at least one threshold is required")
    return tuple(sorted(dict.fromkeys(thresholds)))


def _metrics(decisions: Iterable[PaperDecision]) -> dict[str, Any]:
    selected = list(decisions)
    count = len(selected)
    home_count = sum(row.predicted_side == "HOME" for row in selected)
    away_count = sum(row.predicted_side == "AWAY" for row in selected)
    stake_units_total = sum(row.stake_units for row in selected)
    if not count:
        return {
            "decisions_count": 0,
            "hit_rate": None,
            "average_confidence": None,
            "calibration_gap": None,
            "home_count": 0,
            "away_count": 0,
            "stake_units_total": 0.0,
        }
    hit_rate = sum(row.correct for row in selected) / count
    average_confidence = sum(row.confidence for row in selected) / count
    return {
        "decisions_count": count,
        "hit_rate": hit_rate,
        "average_confidence": average_confidence,
        "calibration_gap": average_confidence - hit_rate,
        "home_count": home_count,
        "away_count": away_count,
        "stake_units_total": stake_units_total,
    }


def _segment(
    segment_type: str,
    segment_key: str,
    min_confidence: float | None,
    decisions: Iterable[PaperDecision],
) -> dict[str, Any]:
    return {
        "segment_type": segment_type,
        "segment_key": segment_key,
        "min_confidence": min_confidence,
        **_metrics(decisions),
        "roi": None,
        "roi_status": ROI_STATUS,
        "interpretation_label": INTERPRETATION,
    }


def _bucket_rows(
    decisions: Iterable[PaperDecision], lower: float, upper: float, include_upper: bool
) -> list[PaperDecision]:
    if include_upper:
        return [row for row in decisions if lower <= row.confidence <= upper]
    return [row for row in decisions if lower <= row.confidence < upper]


def build_segments(
    decisions: Iterable[PaperDecision],
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
) -> list[dict[str, Any]]:
    rows = list(decisions)
    parsed_thresholds = tuple(sorted(dict.fromkeys(float(value) for value in thresholds)))
    if any(not 0.5 <= threshold <= 1.0 for threshold in parsed_thresholds):
        raise ExplorerError("INVALID_FILTER: thresholds must be between 0.5 and 1.0")
    segments: list[dict[str, Any]] = [_segment("GLOBAL", "ALL", None, rows)]
    for threshold in parsed_thresholds:
        segments.append(
            _segment(
                "THRESHOLD",
                f">={threshold:.2f}",
                threshold,
                [row for row in rows if row.confidence >= threshold],
            )
        )
    for key, lower, upper, include_upper in CONFIDENCE_BUCKETS:
        segments.append(
            _segment(
                "CONFIDENCE_BUCKET",
                key,
                lower,
                _bucket_rows(rows, lower, upper, include_upper),
            )
        )
    for side in ("HOME", "AWAY"):
        segments.append(
            _segment(
                "PREDICTED_SIDE",
                side,
                None,
                [row for row in rows if row.predicted_side == side],
            )
        )
    for month in sorted({row.game_month for row in rows}):
        segments.append(
            _segment("GAME_MONTH", month, None, [row for row in rows if row.game_month == month])
        )
    return segments


def resolve_generated_at_utc(value: str | None = None) -> str:
    """Return an explicit timestamp or the current UTC generation time."""
    if value is not None:
        return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_output_payload(
    dataset: PaperLearningDataset,
    *,
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    generated_at_utc: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parsed_thresholds = tuple(sorted(dict.fromkeys(float(value) for value in thresholds)))
    segments = build_segments(dataset.decisions, parsed_thresholds)
    global_metrics = dict(segments[0])
    global_metrics.pop("segment_type")
    global_metrics.pop("segment_key")
    global_metrics.pop("min_confidence")
    segment_types = []
    for segment in segments:
        segment_type = segment["segment_type"]
        if segment_type not in segment_types:
            segment_types.append(segment_type)
    payload = {
        "source_decisions_csv": dataset.source_csv,
        "source_sha256": dataset.source_sha256,
        "generated_at_utc": resolve_generated_at_utc(generated_at_utc),
        "segments_count": len(segments),
        "thresholds": list(parsed_thresholds),
        "global_metrics": global_metrics,
        "segment_types": segment_types,
        "roi": None,
        "roi_status": ROI_STATUS,
        "roi_unavailable_reason": ROI_UNAVAILABLE_REASON,
        "generates_new_predictions": False,
        "interpretation": INTERPRETATION,
        "limitation_labels": LIMITATION_LABELS,
    }
    return payload, segments


def write_outputs(
    payload: dict[str, Any],
    segments: list[dict[str, Any]],
    json_path: Path,
    csv_path: Path,
) -> None:
    json_path, csv_path = Path(json_path), Path(csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEGMENT_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for segment in segments:
            writer.writerow({name: segment[name] for name in SEGMENT_FIELDNAMES})
