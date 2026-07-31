"""
wbc_backend/simulation/simulation_result_loader.py

Loads StrategySimulationResult from PAPER simulation JSONL output files.

Public API:
    load_latest_simulation_result(simulation_dir, strategy_name) -> StrategySimulationResult | None
    load_simulation_result_from_jsonl(path) -> StrategySimulationResult

Safety invariants:
- Only loads from paths that contain 'outputs/simulation/PAPER'.
- Rejects any result where paper_only is False.
- Rejects malformed JSONL.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wbc_backend.simulation.strategy_simulation_result import (
    StrategySimulationResult,
    VALID_GATE_STATUSES,
)

# Must appear anywhere in the absolute path string
_PAPER_PATH_MARKER = "outputs/simulation/PAPER"


def _assert_paper_path(path: Path) -> None:
    """Raise ValueError if path is not under a PAPER simulation zone."""
    path_str = path.resolve().as_posix()
    if _PAPER_PATH_MARKER not in path_str:
        raise ValueError(
            f"Refusing to load simulation result from non-PAPER path: {path!r}. "
            f"Path must contain '{_PAPER_PATH_MARKER}'."
        )


def load_simulation_result_from_jsonl(path: str | Path) -> StrategySimulationResult:
    """Load a single StrategySimulationResult from a JSONL file.

    Parameters
    ----------
    path : str | Path
        Absolute or relative path to the JSONL simulation file.

    Returns
    -------
    StrategySimulationResult

    Raises
    ------
    ValueError
        If the path is not under a PAPER simulation zone,
        if the file contains invalid JSON,
        if paper_only is False,
        or if required fields are missing.
    """
    path = Path(path)
    _assert_paper_path(path)

    if not path.exists():
        raise FileNotFoundError(f"Simulation JSONL not found: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Simulation JSONL is empty: {path}")

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {path}: {exc}") from exc

    # Security: reject paper_only=False before constructing result
    if data.get("paper_only") is False:
        raise ValueError(
            f"Refusing to load simulation result with paper_only=False from {path}. "
            "This invariant must never be violated."
        )

    # Parse generated_at_utc
    generated_at_raw = data.get("generated_at_utc")
    if generated_at_raw is None:
        raise ValueError(f"Missing 'generated_at_utc' in {path}")
    try:
        generated_at_utc = datetime.fromisoformat(generated_at_raw)
        if generated_at_utc.tzinfo is None:
            generated_at_utc = generated_at_utc.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Cannot parse generated_at_utc={generated_at_raw!r} in {path}: {exc}"
        ) from exc

    # Validate gate_status
    gate_status = data.get("gate_status")
    if gate_status not in VALID_GATE_STATUSES:
        raise ValueError(
            f"gate_status={gate_status!r} is not in VALID_GATE_STATUSES. "
            f"File: {path}"
        )

    required_int_fields = ("sample_size", "bet_count", "skipped_count")
    for field_name in required_int_fields:
        if field_name not in data:
            raise ValueError(f"Missing required field '{field_name}' in {path}")

    return StrategySimulationResult(
        simulation_id=data.get("simulation_id", ""),
        strategy_name=data.get("strategy_name", ""),
        date_start=data.get("date_start", ""),
        date_end=data.get("date_end", ""),
        sample_size=int(data["sample_size"]),
        bet_count=int(data["bet_count"]),
        skipped_count=int(data["skipped_count"]),
        gate_status=gate_status,
        generated_at_utc=generated_at_utc,
        avg_model_prob=_float_or_none(data.get("avg_model_prob")),
        avg_market_prob=_float_or_none(data.get("avg_market_prob")),
        brier_model=_float_or_none(data.get("brier_model")),
        brier_market=_float_or_none(data.get("brier_market")),
        brier_skill_score=_float_or_none(data.get("brier_skill_score")),
        ece=_float_or_none(data.get("ece")),
        roi_pct=_float_or_none(data.get("roi_pct")),
        max_drawdown_pct=_float_or_none(data.get("max_drawdown_pct")),
        sharpe_proxy=_float_or_none(data.get("sharpe_proxy")),
        avg_edge_pct=_float_or_none(data.get("avg_edge_pct")),
        avg_kelly_fraction=_float_or_none(data.get("avg_kelly_fraction")),
        gate_reasons=list(data.get("gate_reasons") or []),
        paper_only=True,  # always True — enforced above
        source_trace=dict(data.get("source_trace") or {}),
    )


def load_latest_simulation_result(
    simulation_dir: str | Path = "outputs/simulation/PAPER",
    strategy_name: str | None = None,
) -> StrategySimulationResult | None:
    """Load the most recently generated simulation result from PAPER zone.

    Searches recursively under *simulation_dir* for JSONL files that match
    the optional *strategy_name* filter. Returns the result with the latest
    ``generated_at_utc`` timestamp.

    Parameters
    ----------
    simulation_dir : str | Path
        Root directory to search (default: ``outputs/simulation/PAPER``).
        Must contain ``outputs/simulation/PAPER`` in its resolved path.
    strategy_name : str | None
        If provided, only files whose filename contains the strategy name
        (after slug normalisation) are considered.

    Returns
    -------
    StrategySimulationResult | None
        The latest simulation result, or None if none is found.
    """
    sim_dir = Path(simulation_dir)
    # Security: reject non-PAPER paths
    try:
        _assert_paper_path(sim_dir)
    except ValueError:
        return None

    if not sim_dir.exists():
        return None

    # Collect all candidate JSONL files (exclude *_report.md and similar)
    candidates: list[Path] = []
    for f in sim_dir.rglob("*.jsonl"):
        if f.name.endswith("_report.jsonl"):
            continue
        # If strategy_name filter is set, check filename
        if strategy_name is not None:
            slug = strategy_name.lower().replace(" ", "_").replace("-", "_")
            if slug not in f.name.lower():
                continue
        candidates.append(f)

    if not candidates:
        return None

    # Load all valid results, pick the latest by generated_at_utc
    best: StrategySimulationResult | None = None
    for candidate in candidates:
        try:
            result = load_simulation_result_from_jsonl(candidate)
        except (ValueError, FileNotFoundError, OSError):
            # Skip malformed or rejected files silently
            continue
        if best is None or result.generated_at_utc > best.generated_at_utc:
            best = result

    return best


def _float_or_none(value: Any) -> float | None:
    """Convert value to float, returning None if value is None or not numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
