"""P359 tiered no-DB replay-readiness harness for Big Lotto adapters.

This quarantined harness uses only deterministic in-memory Big Lotto fixture
history. It does not open a DB, import production registries, start services,
run production replay/backfill, or score betting outcomes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import historical_adapters as adapters

GAME = "BIG_LOTTO"
FIXTURE_SIZE = 520
WINDOW_SIZE = 520
PICK = 6
MAX_NUM = 49

MANIFEST_PATH = Path("artifacts/P359_biglotto_no_db_replay_readiness_manifest.csv")
RESULTS_PATH = Path("artifacts/P359_biglotto_no_db_replay_readiness_results.csv")
REPORT_PATH = Path("artifacts/P359_biglotto_no_db_replay_readiness_report.md")

REQUIRED_COLUMNS = [
    "tier",
    "strategy_id",
    "adapter_function",
    "execution_status",
    "readiness_status",
    "parity_status",
    "bet_count",
    "window_size",
    "fixture_size",
    "period_count",
    "output_shape",
    "all_outputs_valid",
    "deterministic",
    "db_opened",
    "production_registry_imported",
    "blocked_reason",
    "notes",
]

P356_BASELINE = (
    ("biglotto_deviation_2bet", 2),
    ("biglotto_echo_aware_3bet", 3),
    ("biglotto_triple_strike", 3),
    ("biglotto_ts3_markov_4bet_w30", 4),
    ("cold_complement_biglotto", 1),
    ("coldpool15_biglotto", 3),
    ("fourier30_markov30_biglotto", 2),
    ("markov_2bet_biglotto", 2),
    ("markov_single_biglotto", 1),
    ("ts3_regime_3bet", 3),
)

P358_PARITY_ACCEPTABLE = (
    "adapt_biglotto_p0_2bet",
    "adapt_predict_biglotto_echo_2bet",
    "adapt_predict_biglotto_echo_phase2_2bet",
    "adapt_predict_biglotto_echo_phase2_3bet",
    "adapt_predict_biglotto_echo_mixed_3bet",
)

P358_SHAPE_SAFETY_ONLY = (
    "adapt_biglotto_zonal_pruning",
    "adapt_biglotto_5bet_orthogonal",
    "adapt_predict_biglotto_regime_3bet",
    "adapt_biglotto_10bet_combined",
)

BLOCKED_EXCLUDED = (
    (
        "biglotto_ts3_markov_freq_5bet",
        "BLOCKED_LINEAGE_GAP",
        "partial evidence only; registered source identity not proven",
    ),
    (
        "biglotto_ts3_acb_4bet",
        "BLOCKED_MISSING_SOURCE",
        "missing runnable source",
    ),
    (
        "ts3_acb_4bet_biglotto",
        "BLOCKED_MISSING_SOURCE",
        "rejected/result artifact only; no callable source",
    ),
    (
        "bet2_fourier_expansion_biglotto",
        "BLOCKED_ID_REUSE",
        "confirmed ID reuse split; do not replay under shared strategy_id",
    ),
)


@dataclass(frozen=True)
class ReadinessRow:
    tier: str
    strategy_id: str
    adapter_function: str
    execution_status: str
    readiness_status: str
    parity_status: str
    bet_count: int | str
    window_size: int
    fixture_size: int
    period_count: int
    output_shape: str
    all_outputs_valid: bool
    deterministic: bool
    db_opened: bool
    production_registry_imported: bool
    blocked_reason: str
    notes: str
    outputs_json: str = ""

    def as_csv_row(self) -> dict[str, object]:
        row = {column: getattr(self, column) for column in REQUIRED_COLUMNS}
        row["outputs_json"] = self.outputs_json
        return row


def build_deterministic_biglotto_fixture(draw_count: int = FIXTURE_SIZE) -> list[dict[str, object]]:
    """Build deterministic synthetic Big Lotto draw history ordered old-to-new."""
    if draw_count < WINDOW_SIZE:
        raise ValueError(f"P359 fixture requires at least {WINDOW_SIZE} draws; got {draw_count}")

    history: list[dict[str, object]] = []
    for draw_index in range(draw_count):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < PICK:
            digest = hashlib.sha256(f"P359-BIGLOTTO:{draw_index}:{counter}".encode("ascii")).digest()
            for byte in digest:
                number = byte % MAX_NUM + 1
                if number not in numbers:
                    numbers.append(number)
                if len(numbers) == PICK:
                    break
            counter += 1
        special = next(number for number in range(1, MAX_NUM + 1) if number not in numbers)
        history.append(
            {
                "draw": f"P359-SYNBL-{draw_index:04d}",
                "date": f"SYNTHETIC-P359-{draw_index:04d}",
                "numbers": sorted(numbers),
                "special": special,
            }
        )
    return history


def _valid_biglotto_bets(bets: list[list[int]], expected_count: int) -> bool:
    if not isinstance(bets, list) or len(bets) != expected_count:
        return False
    for bet in bets:
        if not isinstance(bet, list):
            return False
        if bet != sorted(bet):
            return False
        if len(bet) != PICK or len(set(bet)) != PICK:
            return False
        if any(number < 1 or number > MAX_NUM for number in bet):
            return False
    return True


def _period_windows(history: list[dict[str, object]], window_size: int) -> list[list[dict[str, object]]]:
    if len(history) < window_size:
        raise ValueError(f"Fixture has {len(history)} draws, below window size {window_size}")
    return [history[start : start + window_size] for start in range(len(history) - window_size + 1)]


def _execute_adapter(
    tier: str,
    adapter_function: str,
    readiness_status: str,
    parity_status: str,
    fixture: list[dict[str, object]],
    window_size: int,
) -> ReadinessRow:
    metadata = adapters.ADAPTER_METADATA[adapter_function]
    expected_count = int(metadata["bet_count"])
    strategy_id = str(metadata["source_strategy_id"])
    func: Callable[[list[dict[str, object]]], list[list[int]]] = getattr(adapters, adapter_function)
    windows = _period_windows(fixture, window_size)

    first_outputs = [func(window) for window in windows]
    second_outputs = [func(window) for window in windows]
    output_valid = all(_valid_biglotto_bets(output, expected_count) for output in first_outputs)
    deterministic = first_outputs == second_outputs
    shape = f"{len(first_outputs)}x{expected_count}x{PICK}"
    notes = "Executed against deterministic in-memory fixture; output shape/readiness only; no outcome scoring."
    if tier == "p358_shape_safety_only":
        notes += " Shape/safety-only row; not parity replay evidence."

    return ReadinessRow(
        tier=tier,
        strategy_id=strategy_id,
        adapter_function=adapter_function,
        execution_status="EXECUTED_NO_DB" if output_valid and deterministic else "FAILED",
        readiness_status=readiness_status if output_valid and deterministic else "NOT_READY",
        parity_status=parity_status,
        bet_count=expected_count,
        window_size=window_size,
        fixture_size=len(fixture),
        period_count=len(windows),
        output_shape=shape,
        all_outputs_valid=output_valid,
        deterministic=deterministic,
        db_opened=False,
        production_registry_imported=False,
        blocked_reason="" if output_valid and deterministic else "ADAPTER_OUTPUT_VALIDATION_FAILED",
        notes=notes,
        outputs_json=json.dumps(first_outputs, separators=(",", ":")),
    )


def build_readiness_rows(
    fixture: list[dict[str, object]] | None = None,
    window_size: int = WINDOW_SIZE,
) -> list[ReadinessRow]:
    history = fixture if fixture is not None else build_deterministic_biglotto_fixture()
    rows: list[ReadinessRow] = []

    for strategy_id, bet_count in P356_BASELINE:
        rows.append(
            ReadinessRow(
                tier="p356_baseline",
                strategy_id=strategy_id,
                adapter_function="NOT_EXECUTED_BY_DESIGN",
                execution_status="PRIOR_REPLAY_EVIDENCE_ONLY",
                readiness_status="PRIOR_BASELINE_ONLY",
                parity_status="PRIOR_P356_REPLAY_EVIDENCE",
                bet_count=bet_count,
                window_size=0,
                fixture_size=0,
                period_count=0,
                output_shape="prior-p356-evidence",
                all_outputs_valid=False,
                deterministic=True,
                db_opened=False,
                production_registry_imported=False,
                blocked_reason="",
                notes="Prior P356 evidence only; no production registry import and no DB-backed replay rerun.",
            )
        )

    for adapter_function in P358_PARITY_ACCEPTABLE:
        rows.append(
            _execute_adapter(
                "p358_parity_acceptable",
                adapter_function,
                "READY_FOR_NO_DB_HARNESS",
                "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
                history,
                window_size,
            )
        )

    for adapter_function in P358_SHAPE_SAFETY_ONLY:
        rows.append(
            _execute_adapter(
                "p358_shape_safety_only",
                adapter_function,
                "READY_SHAPE_SAFETY_ONLY",
                "SHAPE_SAFETY_ONLY",
                history,
                window_size,
            )
        )

    for strategy_id, readiness_status, reason in BLOCKED_EXCLUDED:
        rows.append(
            ReadinessRow(
                tier="blocked_excluded",
                strategy_id=strategy_id,
                adapter_function="NOT_EXECUTED_BY_DESIGN",
                execution_status="EXCLUDED_BLOCKED",
                readiness_status=readiness_status,
                parity_status="BLOCKED_NOT_COMPARABLE",
                bet_count="UNKNOWN",
                window_size=0,
                fixture_size=0,
                period_count=0,
                output_shape="excluded",
                all_outputs_valid=False,
                deterministic=True,
                db_opened=False,
                production_registry_imported=False,
                blocked_reason=reason,
                notes="Explicitly excluded by P358 lineage/readiness evidence.",
            )
        )

    return rows


def run_harness() -> dict[str, Any]:
    rows = build_readiness_rows()
    return {
        "classification": "P359_COMPLETE_NO_DB_REPLAY_READINESS_HARNESS",
        "game": GAME,
        "fixture_size": FIXTURE_SIZE,
        "window_size": WINDOW_SIZE,
        "row_count": len(rows),
        "tier_counts": {
            tier: sum(1 for row in rows if row.tier == tier)
            for tier in ("p356_baseline", "p358_parity_acceptable", "p358_shape_safety_only", "blocked_excluded")
        },
        "all_executed_outputs_valid": all(
            row.all_outputs_valid for row in rows if row.execution_status == "EXECUTED_NO_DB"
        ),
        "all_executed_deterministic": all(
            row.deterministic for row in rows if row.execution_status == "EXECUTED_NO_DB"
        ),
        "no_db_open_write_status": "NO_DB_OPENED_OR_WRITTEN",
        "production_registry_status": "NOT_IMPORTED_OR_CONNECTED",
        "replay_backfill_status": "NOT_RUN",
        "strategy_status_change_status": "NOT_CHANGED",
        "deploy_service_status": "NOT_STARTED_OR_CHANGED",
        "rows": rows,
    }


def _write_csv(rows: list[ReadinessRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = REQUIRED_COLUMNS + ["outputs_json"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.as_csv_row() for row in rows)
    return path


def write_manifest_csv(result: dict[str, Any], path: Path = MANIFEST_PATH) -> Path:
    return _write_csv(result["rows"], path)


def write_results_csv(result: dict[str, Any], path: Path = RESULTS_PATH) -> Path:
    return _write_csv(result["rows"], path)


def render_report(result: dict[str, Any]) -> str:
    rows: list[ReadinessRow] = result["rows"]
    tier_lines = "\n".join(
        f"- `{tier}`: {count} rows" for tier, count in result["tier_counts"].items()
    )
    parity_adapters = ", ".join(P358_PARITY_ACCEPTABLE)
    shape_adapters = ", ".join(P358_SHAPE_SAFETY_ONLY)
    blocked = ", ".join(strategy_id for strategy_id, _, _ in BLOCKED_EXCLUDED)
    executed_lines = "\n".join(
        f"- `{row.adapter_function}` -> `{row.strategy_id}`: "
        f"{row.execution_status}, shape `{row.output_shape}`, valid `{row.all_outputs_valid}`, "
        f"deterministic `{row.deterministic}`"
        for row in rows
        if row.tier in {"p358_parity_acceptable", "p358_shape_safety_only"}
    )
    baseline_lines = "\n".join(f"- `{strategy_id}`" for strategy_id, _ in P356_BASELINE)

    return f"""# P359 Big Lotto No-DB Replay-Readiness Report

Final classification: `{result["classification"]}`

## Executive Summary

P359 created a controlled, tiered Big Lotto no-DB replay-readiness harness. It is a readiness/smoke harness only: no production replay, no backfill, no betting interpretation, and no blended leaderboard across tiers.

Fable5 planning input was accepted as conversation-provided planning input: `RECOMMEND_NO_DB_HARNESS_TIERED_WITH_SHAPE_ONLY_FLAGGED`.

## Tier Definitions

{tier_lines}

- `p356_baseline`: prior P356 replay evidence only; not rerun here.
- `p358_parity_acceptable`: P358 recovered adapters executed under deterministic in-memory fixture history and acceptable for this bounded no-DB harness.
- `p358_shape_safety_only`: P358 adapters executed only for shape/safety readiness; these rows are not parity replay evidence.
- `blocked_excluded`: lineage/source/id-reuse blocked targets explicitly excluded from execution.

## Included And Excluded Targets

- P356 prior-evidence baseline rows:
{baseline_lines}
- P358 parity-acceptable adapters: `{parity_adapters}`
- P358 shape/safety-only adapters: `{shape_adapters}`
- Blocked excluded strategies: `{blocked}`

## Execution Results

- Fixture design: deterministic synthetic in-memory Big Lotto draw history.
- Fixture size: `{result["fixture_size"]}` draws.
- Window size: `{result["window_size"]}` draws.
- All executed outputs valid: `{result["all_executed_outputs_valid"]}`
- All executed outputs deterministic: `{result["all_executed_deterministic"]}`

{executed_lines}

## Caveats

- P356 baseline rows are marked `PRIOR_REPLAY_EVIDENCE_ONLY`; this harness did not import the production registry or rerun DB-backed production replay for them.
- Shape/safety-only results are flagged `SHAPE_SAFETY_ONLY` and are not exact historical parity replay evidence.
- Blocked targets remain excluded: lineage gaps, missing runnable source, and confirmed ID reuse were not bypassed.
- No single blended leaderboard artifact was created and tiers must not be ranked together.
- This is not betting evidence and does not claim future predictive ability.

## Safety

- No DB open/write: `{result["no_db_open_write_status"]}`
- Production registry import/connection: `{result["production_registry_status"]}`
- Replay/backfill status: `{result["replay_backfill_status"]}`
- Strategy status change status: `{result["strategy_status_change_status"]}`
- Deploy/service status: `{result["deploy_service_status"]}`

## Artifacts

- `artifacts/P359_biglotto_no_db_replay_readiness_manifest.csv`
- `artifacts/P359_biglotto_no_db_replay_readiness_results.csv`
- `artifacts/P359_biglotto_no_db_replay_readiness_report.md`

## Recommendation

Proceed only with controlled no-DB harness expansion for parity-acceptable adapters, and run lineage reconstruction before any blocked target is reconsidered. Keep shape/safety-only rows separate unless exact source parity is later proven.
"""


def write_report(result: dict[str, Any], path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(result), encoding="utf-8")
    return path


def write_artifacts() -> dict[str, Path]:
    result = run_harness()
    return {
        "manifest": write_manifest_csv(result),
        "results": write_results_csv(result),
        "report": write_report(result),
    }


if __name__ == "__main__":
    for artifact_path in write_artifacts().values():
        print(artifact_path)
