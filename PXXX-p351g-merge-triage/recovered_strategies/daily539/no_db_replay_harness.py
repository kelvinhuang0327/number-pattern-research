"""P357E controlled no-DB replay harness for Daily 539 recovered adapters.

This quarantine harness accepts only in-memory Daily 539 draw histories. It
does not import sqlite3, DatabaseManager, production replay registries, or
strategy status modules. It produces deterministic prediction rows only; it
does not score future outcomes or claim predictive ability.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .historical_adapters import generate_no_db_adapter_output

INCLUDED_STRATEGY_IDS = (
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
)

EXCLUDED_SHAPE_ONLY_STRATEGY_IDS = ("539_3bet_orthogonal",)

GAME = "DAILY_539"
FIXTURE_SIZE = 520
REPLAY_WINDOW = 500
RESULTS_PATH = Path("artifacts/P357E_daily539_no_db_replay_harness_results.csv")
REPORT_PATH = Path("artifacts/P357E_daily539_no_db_replay_harness_report.md")


@dataclass(frozen=True)
class ReplayRow:
    strategy_id: str
    game: str
    fixture_size: int
    replay_window: int
    replay_period_index: int
    total_periods: int
    history_start_draw: str
    history_end_draw: str
    prediction_rows: int
    predictions_json: str
    output_valid: bool
    no_db_access_proof: str
    notes: str

    def as_csv_row(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "game": self.game,
            "fixture_size": self.fixture_size,
            "replay_window": self.replay_window,
            "replay_period_index": self.replay_period_index,
            "total_periods": self.total_periods,
            "history_start_draw": self.history_start_draw,
            "history_end_draw": self.history_end_draw,
            "prediction_rows": self.prediction_rows,
            "predictions_json": self.predictions_json,
            "output_valid": self.output_valid,
            "no_db_access_proof": self.no_db_access_proof,
            "notes": self.notes,
        }


def build_deterministic_daily539_fixture(
    draw_count: int = FIXTURE_SIZE,
) -> list[dict[str, object]]:
    """Build a deterministic in-memory Daily 539 fixture."""
    if draw_count < REPLAY_WINDOW:
        raise ValueError(
            f"P357E fixture must contain at least {REPLAY_WINDOW} draws; "
            f"got {draw_count}"
        )

    history: list[dict[str, object]] = []
    for draw_index in range(draw_count):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < 5:
            digest = hashlib.sha256(
                f"P357E-DAILY539:{draw_index}:{counter}".encode("ascii")
            ).digest()
            for byte in digest:
                number = byte % 39 + 1
                if number not in numbers:
                    numbers.append(number)
                if len(numbers) == 5:
                    break
            counter += 1
        history.append(
            {
                "draw": f"P357E-SYN539-{draw_index:04d}",
                "date": f"SYNTHETIC-P357E-{draw_index:04d}",
                "numbers": sorted(numbers),
            }
        )
    return history


def _validate_prediction_rows(predictions: list[list[int]]) -> bool:
    if len(predictions) != 3:
        return False
    flattened: list[int] = []
    for row in predictions:
        if len(row) != 5:
            return False
        if row != sorted(row):
            return False
        if len(set(row)) != 5:
            return False
        if any(number < 1 or number > 39 for number in row):
            return False
        flattened.extend(row)
    return len(set(flattened)) == 15


def run_controlled_no_db_replay(
    fixture: list[dict[str, object]] | None = None,
    replay_window: int = REPLAY_WINDOW,
) -> dict[str, Any]:
    """Run the controlled rolling-window replay for parity-acceptable adapters."""
    history = fixture if fixture is not None else build_deterministic_daily539_fixture()
    if len(history) < replay_window:
        raise ValueError(
            f"Fixture must contain at least {replay_window} draws; got {len(history)}"
        )

    total_periods = len(history) - replay_window + 1
    rows: list[ReplayRow] = []
    for period_index, start_index in enumerate(range(total_periods), start=1):
        window_history = history[start_index : start_index + replay_window]
        history_start_draw = str(window_history[0]["draw"])
        history_end_draw = str(window_history[-1]["draw"])

        for strategy_id in INCLUDED_STRATEGY_IDS:
            adapter_output = generate_no_db_adapter_output(strategy_id, window_history)
            predictions = adapter_output["predictions"]
            output_valid = _validate_prediction_rows(predictions)
            rows.append(
                ReplayRow(
                    strategy_id=strategy_id,
                    game=GAME,
                    fixture_size=len(history),
                    replay_window=replay_window,
                    replay_period_index=period_index,
                    total_periods=total_periods,
                    history_start_draw=history_start_draw,
                    history_end_draw=history_end_draw,
                    prediction_rows=len(predictions),
                    predictions_json=json.dumps(predictions, separators=(",", ":")),
                    output_valid=output_valid,
                    no_db_access_proof=(
                        "in-memory fixture only; harness imports no sqlite3, "
                        "DatabaseManager, registry, or status module"
                    ),
                    notes=(
                        "prediction rows only; no future outcome scoring; "
                        "no production registry connection"
                    ),
                )
            )

    return {
        "classification": "P357E_COMPLETE_NO_DB_REPLAY_HARNESS",
        "game": GAME,
        "included_adapters": list(INCLUDED_STRATEGY_IDS),
        "excluded_shape_only_adapters": list(EXCLUDED_SHAPE_ONLY_STRATEGY_IDS),
        "fixture_size": len(history),
        "fixture_design": "deterministic synthetic in-memory Daily 539 fixture",
        "replay_window": replay_window,
        "total_periods": total_periods,
        "prediction_row_count": len(rows),
        "all_outputs_valid": all(row.output_valid for row in rows),
        "no_db_write_open_status": "NO_DB_OPENED_OR_WRITTEN",
        "production_registry_status": "NOT_CONNECTED",
        "strategy_status_change_status": "NOT_CHANGED",
        "full_replay_status": "NOT_RUN",
        "next_readiness": "READY_FOR_CONTROLLED_REPLAY_EXPANSION",
        "rows": [row.as_csv_row() for row in rows],
    }


def write_results_csv(
    replay_result: dict[str, Any],
    path: Path = RESULTS_PATH,
) -> Path:
    rows = replay_result["rows"]
    if not rows:
        raise ValueError("No P357E replay rows to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def render_report(replay_result: dict[str, Any]) -> str:
    rows = replay_result["rows"]
    sample_rows = rows[:2]
    sample_lines = "\n".join(
        "- `{strategy_id}` period {replay_period_index}/{total_periods}: "
        "`{predictions_json}`; valid={output_valid}".format(**row)
        for row in sample_rows
    )

    return f"""# P357E Daily 539 No-DB Replay Harness Report

Final classification: `{replay_result["classification"]}`

## Scope

- Included adapters: `{", ".join(replay_result["included_adapters"])}`
- Excluded / partial adapters: `{", ".join(replay_result["excluded_shape_only_adapters"])}` remains shape/safety-only and was not included in performance replay rows.
- Fixture design: {replay_result["fixture_design"]}.
- Fixture size: {replay_result["fixture_size"]} draws.
- Replay window / history length: {replay_result["replay_window"]} draws per rolling window.
- Total periods: {replay_result["total_periods"]}.
- Prediction rows: {replay_result["prediction_row_count"]}.

## Output Validity

- All outputs valid: `{replay_result["all_outputs_valid"]}`
- Each row contains 3 Daily 539 bets, 5 sorted unique numbers per bet, values in `1..39`, and 15 unique numbers across the 3-bet set.
- Sample rows:
{sample_lines}

## Safety

- No DB write/open status: `{replay_result["no_db_write_open_status"]}`
- No production registry status: `{replay_result["production_registry_status"]}`
- Strategy status change status: `{replay_result["strategy_status_change_status"]}`
- Full replay status: `{replay_result["full_replay_status"]}`
- Harness namespace: `recovered_strategies/daily539/no_db_replay_harness.py`
- Results artifact: `artifacts/P357E_daily539_no_db_replay_harness_results.csv`

## Caveats

- This is a controlled no-DB replay harness over deterministic synthetic fixture history.
- The output is prediction-row generation only; it does not score future draws or claim predictive ability.
- P357D classified `539_3bet_orthogonal` as `PARITY_PARTIAL_NEEDS_NOTES`, so it is excluded from performance replay rows here.
- The two included adapters rely on the P357D parity-acceptable Fourier/cold reconstruction evidence for >=500-draw histories.

## Next Readiness

`{replay_result["next_readiness"]}`
"""


def write_report(
    replay_result: dict[str, Any],
    path: Path = REPORT_PATH,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(replay_result), encoding="utf-8")
    return path


def write_artifacts() -> dict[str, Path]:
    replay_result = run_controlled_no_db_replay()
    return {
        "results": write_results_csv(replay_result),
        "report": write_report(replay_result),
    }


if __name__ == "__main__":
    paths = write_artifacts()
    for artifact_path in paths.values():
        print(artifact_path)
