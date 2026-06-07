"""P252F — Rolling Window Statistics SSOT.

Pure-Python module for rolling / sliding window operations used in lottery
prediction research. Consolidates M3 gap from P252B. Standardises window
definitions, slice generation, and summary output previously scattered across
RSM, P211R, P221F, P222, P224, P230, P231, and research scripts.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy — pure stdlib only (math, statistics, typing)
- Deterministic output for identical inputs
- No claim of predictive edge
- No betting advice

Window vocabulary (from P221F governance, frozen 2026-05):
- SHORT  windows: 100 / 125 / 150 draws — recent-performance signal
- MID    windows: 500 / 750 / 1000 draws — medium-term signal
- ALL_HISTORY: full dataset — reference context only, never a gate

RSM production windows (from rolling_strategy_monitor.py):
- {'short': 30, 'medium': 100, 'long': 300}
Both sets are exposed as named constants in P221F_WINDOWS and RSM_WINDOWS.

Usage::

    from lottery_api.utils.rolling_window import (
        P221F_WINDOWS,
        validate_window_config,
        rolling_slices,
        rolling_window_labels,
        summarize_window,
        rolling_summary,
    )

    slices = rolling_slices(list(range(200)), window_size=150)
    # → one slice: items[-150:]

    report = rolling_summary(
        items=list(range(1000)),
        window_sizes=P221F_WINDOWS["short"],
        family_label="DAILY_539_midfreq_p252f_test",
    )
    assert report["no_edge_claim"] is True
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Callable, Optional, Sequence

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Canonical window constants
# ---------------------------------------------------------------------------

# P221F frozen research windows (governance: 2026-05, frozen by P221F/P225).
# Use these for any research-layer rolling analysis.
P221F_WINDOWS: dict[str, tuple[int, ...]] = {
    "short":  (100, 125, 150),
    "mid":    (500, 750, 1000),
    "all_history": (),       # empty = use full dataset; reference-context only
}

# RSM production windows (from rolling_strategy_monitor.py WINDOWS dict).
# These drive live strategy monitoring, not research scanning.
RSM_WINDOWS: dict[str, int] = {
    "short":  30,
    "medium": 100,
    "long":   300,
}

# Representative single windows used in most P211R / P222 / P224 research tasks
RESEARCH_SHORT = 150
RESEARCH_MID_1 = 500
RESEARCH_MID_2 = 1000

# Minimum sample threshold below which a window is flagged UNDERPOWERED
DEFAULT_MIN_COUNT = 30


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_window_config(
    total_count: int,
    window_size: int,
    step_size: int = 1,
    min_count: Optional[int] = None,
) -> dict:
    """Validate rolling window configuration parameters.

    Args:
        total_count: Total number of items in the dataset.
        window_size: Number of items per window.
        step_size: Stride between successive window start positions (≥ 1).
        min_count: Minimum acceptable window size (default: DEFAULT_MIN_COUNT).

    Returns:
        dict with:
            valid (bool): True if all checks pass.
            errors (list[str]): Error messages (empty if valid).
            warnings (list[str]): Non-fatal concerns.
            window_count (int): Estimated full window count (0 if invalid).
            underpowered (bool): True if total_count < window_size.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(total_count, int) or total_count < 0:
        errors.append(f"total_count must be a non-negative integer, got {total_count!r}")
    if not isinstance(window_size, int) or window_size < 1:
        errors.append(f"window_size must be a positive integer, got {window_size!r}")
    if not isinstance(step_size, int) or step_size < 1:
        errors.append(f"step_size must be a positive integer, got {step_size!r}")

    eff_min = min_count if (min_count is not None) else DEFAULT_MIN_COUNT
    if min_count is not None and (not isinstance(min_count, int) or min_count < 1):
        errors.append(f"min_count must be a positive integer, got {min_count!r}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings,
                "window_count": 0, "underpowered": True}

    window_count = max(0, math.ceil((total_count - window_size + 1) / step_size))
    underpowered = total_count < window_size

    if underpowered:
        warnings.append(
            f"total_count ({total_count}) < window_size ({window_size}); "
            "only a partial window is available — results may be UNDERPOWERED."
        )
    if window_size < eff_min:
        warnings.append(
            f"window_size ({window_size}) < min_count ({eff_min}); "
            "window may be UNDERPOWERED for statistical tests."
        )

    return {
        "valid": True,
        "errors": errors,
        "warnings": warnings,
        "window_count": window_count,
        "underpowered": underpowered,
    }


# ---------------------------------------------------------------------------
# Slice generation — TAIL windows (most common in this codebase)
# ---------------------------------------------------------------------------


def rolling_slices(
    items: Sequence,
    window_size: int,
    step_size: int = 1,
    include_partial: bool = False,
) -> list[list]:
    """Generate rolling (sliding) window slices of a sequence.

    Slices are ordered from oldest to newest. Each slice contains
    window_size consecutive items (or fewer if include_partial=True
    and the last window is shorter).

    This is the FORWARD sliding window (start-to-end), complementing the
    RSM TAIL window pattern (items[-window_size:]). For RSM-style tail
    analysis use tail_window() instead.

    Args:
        items: Input sequence (list, tuple, etc.).
        window_size: Number of items per window.
        step_size: Stride between window start positions (default 1).
        include_partial: If True, include the last window even if shorter
                         than window_size (default False).

    Returns:
        list[list]: List of window slices.

    Raises:
        ValueError: If window_size < 1 or step_size < 1.
    """
    if window_size < 1:
        raise ValueError(f"window_size must be ≥ 1, got {window_size}")
    if step_size < 1:
        raise ValueError(f"step_size must be ≥ 1, got {step_size}")

    items_list = list(items)
    n = len(items_list)
    slices: list[list] = []

    start = 0
    while start < n:
        end = start + window_size
        chunk = items_list[start:end]
        if len(chunk) == window_size:
            slices.append(chunk)
        elif include_partial and len(chunk) > 0:
            slices.append(chunk)
        elif len(chunk) < window_size:
            break  # no more full windows
        start += step_size

    return slices


def tail_window(items: Sequence, window_size: int) -> list:
    """Return the last window_size items — the RSM pattern.

    If len(items) < window_size, returns all available items
    (partial window, flagged in the returned dict metadata).

    Args:
        items: Input sequence.
        window_size: Number of items to include from the end.

    Returns:
        list: Last window_size items (or all if fewer available).
    """
    lst = list(items)
    return lst[-window_size:] if len(lst) >= window_size else lst


# ---------------------------------------------------------------------------
# Window labels
# ---------------------------------------------------------------------------


def rolling_window_labels(
    total_count: int,
    window_size: int,
    step_size: int = 1,
) -> list[str]:
    """Generate ordered labels for each rolling window.

    Label format: "w{window_size}[{start}:{end}]"
    Example: "w150[0:150]", "w150[1:151]", ...

    Args:
        total_count: Total number of items.
        window_size: Items per window.
        step_size: Stride between windows.

    Returns:
        list[str]: One label per full window.

    Raises:
        ValueError: If window_size < 1 or step_size < 1.
    """
    if window_size < 1:
        raise ValueError(f"window_size must be ≥ 1, got {window_size}")
    if step_size < 1:
        raise ValueError(f"step_size must be ≥ 1, got {step_size}")

    labels: list[str] = []
    start = 0
    while start + window_size <= total_count:
        end = start + window_size
        labels.append(f"w{window_size}[{start}:{end}]")
        start += step_size
    return labels


def tail_window_label(total_count: int, window_size: int) -> str:
    """Label for a tail window — the RSM/research pattern.

    Format: "tail_{window_size}" when full, "partial_{actual}" when short.
    """
    actual = min(total_count, window_size)
    if actual == window_size:
        return f"tail_{window_size}"
    return f"partial_{actual}_of_{window_size}"


# ---------------------------------------------------------------------------
# Window summarisation
# ---------------------------------------------------------------------------


def summarize_window(
    values: Sequence,
    label: Optional[str] = None,
    start_index: int = 0,
) -> dict:
    """Compute summary statistics for a single window of values.

    Args:
        values: Sequence of values (numeric or arbitrary).
        label: Optional label string.
        start_index: Index of the first element in the parent sequence.

    Returns:
        dict: Window summary with count, and numeric stats if applicable.
    """
    lst = list(values)
    n = len(lst)
    end_index = start_index + n

    summary: dict = {
        "label": label or f"w{n}[{start_index}:{end_index}]",
        "start_index": start_index,
        "end_index": end_index,
        "count": n,
        "value_count": n,
    }

    # Numeric stats only if values are all numeric
    numeric = [v for v in lst if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v)]
    if len(numeric) == n and n > 0:
        summary["mean"] = sum(numeric) / n
        summary["min"]  = min(numeric)
        summary["max"]  = max(numeric)
        if n >= 2:
            summary["std"] = statistics.pstdev(numeric)
        else:
            summary["std"] = 0.0
    else:
        summary["mean"] = None
        summary["min"]  = None
        summary["max"]  = None
        summary["std"]  = None

    return summary


# ---------------------------------------------------------------------------
# Full rolling summary — canonical SSOT output
# ---------------------------------------------------------------------------


def rolling_summary(
    items: Sequence,
    window_sizes: int | tuple[int, ...],
    step_size: int = 1,
    value_getter: Optional[Callable[[Any], float]] = None,
    family_label: Optional[str] = None,
    include_partial: bool = False,
    min_count: Optional[int] = None,
) -> dict:
    """Produce a structured rolling window summary.

    This is the canonical SSOT output for rolling window analysis.
    Always includes no_edge_claim=True and no_betting_advice=True.

    Args:
        items: Input sequence (list, tuple, etc.).
        window_sizes: Single int or tuple of ints; each generates a
                      separate window series in the output.
        step_size: Stride between windows (default 1).
        value_getter: Optional callable(item) → float for extracting a
                      numeric value from each item. If None, items are
                      used directly as values.
        family_label: Optional label for the analysis family.
        include_partial: Whether to include terminal partial windows.
        min_count: Minimum window size below which UNDERPOWERED is flagged.

    Returns:
        dict: Structured rolling summary with schema_version and all fields.

    Raises:
        ValueError: If window_sizes is empty or step_size < 1.
    """
    if step_size < 1:
        raise ValueError(f"step_size must be ≥ 1, got {step_size}")

    items_list = list(items)
    n = len(items_list)

    if value_getter is not None:
        values = [float(value_getter(item)) for item in items_list]
    else:
        values = items_list

    # Normalise window_sizes to tuple
    if isinstance(window_sizes, int):
        ws_tuple: tuple[int, ...] = (window_sizes,)
    else:
        ws_tuple = tuple(window_sizes)
    if len(ws_tuple) == 0:
        raise ValueError("window_sizes must not be empty")

    series: list[dict] = []
    for ws in ws_tuple:
        if ws < 1:
            raise ValueError(f"window_size must be ≥ 1, got {ws}")

        validation = validate_window_config(n, ws, step_size, min_count)
        labels = rolling_window_labels(n, ws, step_size)
        slices = rolling_slices(items_list, ws, step_size, include_partial)
        val_slices = rolling_slices(values, ws, step_size, include_partial)

        windows: list[dict] = []
        start = 0
        for i, (sl, vl) in enumerate(zip(slices, val_slices)):
            wlabel = labels[i] if i < len(labels) else f"w{ws}[{start}:{start+len(sl)}]"
            wsumm = summarize_window(vl, label=wlabel, start_index=start)
            windows.append(wsumm)
            start += step_size

        series.append({
            "window_size": ws,
            "window_count": len(windows),
            "underpowered": validation["underpowered"],
            "warnings": validation["warnings"],
            "windows": windows,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "summary_type": "rolling_window_statistics",
        "family_label": family_label or "UNLABELED",
        "total_count": n,
        "step_size": step_size,
        "include_partial": include_partial,
        "min_count": min_count if min_count is not None else DEFAULT_MIN_COUNT,
        "window_series": series,
        "window_sizes_requested": list(ws_tuple),
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Items are in chronological order (oldest first)",
            "Windows are independent; forward-leakage prevention is caller's responsibility",
            "P221F windows (short: 100/125/150, mid: 500/750/1000) are frozen research constants",
        ],
        "limitations": [
            "Small window counts may produce UNDERPOWERED statistics",
            "Rolling window correlations require multiple-testing correction (use correction_gate)",
            "A rolling window edge does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }
