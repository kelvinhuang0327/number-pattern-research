"""
wbc_backend/recommendation/p27_true_date_range_planner.py

P27 Full 2025 True-Date Backfill — segmented range planner.

Splits a full date range (e.g. 2025-05-08 → 2025-09-28) into manageable
14-day segments. Segments are contiguous, non-overlapping, and no dates
are skipped silently.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    P27ExpansionSegment,
)


# Default output dir templates
_P25_OUTPUT_BASE = (
    "outputs/predictions/PAPER/backfill/"
    "p25_true_date_source_separation_{start}_{end}"
)
_P26_OUTPUT_BASE = (
    "outputs/predictions/PAPER/backfill/"
    "p26_true_date_historical_backfill_{start}_{end}"
)


def build_true_date_segments(
    date_start: str,
    date_end: str,
    segment_days: int = 14,
    p25_base_dir: Optional[str] = None,
    p26_base_dir: Optional[str] = None,
) -> List[P27ExpansionSegment]:
    """
    Split [date_start, date_end] (inclusive ISO dates) into segments of
    up to `segment_days` days. The last segment may be shorter.

    Returns an empty list if date_start > date_end.
    Raises ValueError if segment_days < 1.
    """
    if segment_days < 1:
        raise ValueError(f"segment_days must be >= 1, got {segment_days}")

    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)

    if start > end:
        return []

    segments: List[P27ExpansionSegment] = []
    seg_idx = 0
    cur = start

    while cur <= end:
        seg_end = min(cur + timedelta(days=segment_days - 1), end)
        seg_start_str = cur.isoformat()
        seg_end_str = seg_end.isoformat()
        date_count = (seg_end - cur).days + 1

        p25_dir = (
            p25_base_dir
            if p25_base_dir is not None
            else _P25_OUTPUT_BASE.format(start=seg_start_str, end=seg_end_str)
        )
        p26_dir = (
            p26_base_dir
            if p26_base_dir is not None
            else _P26_OUTPUT_BASE.format(start=seg_start_str, end=seg_end_str)
        )

        segments.append(
            P27ExpansionSegment(
                segment_index=seg_idx,
                date_start=seg_start_str,
                date_end=seg_end_str,
                date_count=date_count,
                p25_output_dir=p25_dir,
                p26_output_dir=p26_dir,
            )
        )
        seg_idx += 1
        cur = seg_end + timedelta(days=1)

    return segments


def validate_segment_plan(segments: List[P27ExpansionSegment]) -> bool:
    """
    Validate that segments are:
    - Contiguous (each segment starts the day after the prior ends)
    - Non-overlapping
    - Correctly indexed (0-based sequential)

    Returns True if valid, raises ValueError with description if not.
    """
    if not segments:
        return True  # empty range is trivially valid

    for i, seg in enumerate(segments):
        if seg.segment_index != i:
            raise ValueError(
                f"Segment at position {i} has segment_index={seg.segment_index}, expected {i}"
            )
        if i > 0:
            prev = segments[i - 1]
            prev_end = date.fromisoformat(prev.date_end)
            cur_start = date.fromisoformat(seg.date_start)
            expected_start = prev_end + timedelta(days=1)
            if cur_start != expected_start:
                raise ValueError(
                    f"Gap detected between segment {i-1} (ends {prev.date_end}) "
                    f"and segment {i} (starts {seg.date_start}). "
                    f"Expected start: {expected_start.isoformat()}"
                )

    return True


def summarize_segment_plan(segments: List[P27ExpansionSegment]) -> Dict:
    """
    Return a JSON-serializable dict describing the segment plan.
    """
    if not segments:
        return {
            "n_segments": 0,
            "total_dates": 0,
            "date_start": None,
            "date_end": None,
            "segments": [],
        }

    total_dates = sum(s.date_count for s in segments)
    return {
        "n_segments": len(segments),
        "total_dates": total_dates,
        "date_start": segments[0].date_start,
        "date_end": segments[-1].date_end,
        "segments": [
            {
                "segment_index": s.segment_index,
                "date_start": s.date_start,
                "date_end": s.date_end,
                "date_count": s.date_count,
                "p25_output_dir": s.p25_output_dir,
                "p26_output_dir": s.p26_output_dir,
            }
            for s in segments
        ],
    }


def estimate_runtime_risk(
    segments: List[P27ExpansionSegment],
    expected_rows_per_day: Optional[float] = None,
) -> Dict:
    """
    Estimate runtime risk for executing all segments.

    expected_rows_per_day: if None, uses a conservative default of 12 rows/day.
    Returns a dict with estimated total_rows, segment_count, and risk_level
    (LOW / MEDIUM / HIGH).
    """
    rows_per_day = expected_rows_per_day if expected_rows_per_day is not None else 12.0
    total_dates = sum(s.date_count for s in segments)
    estimated_rows = total_dates * rows_per_day
    n_segments = len(segments)

    # Heuristic: each segment takes ~5s; total risk from segment count
    estimated_runtime_s = n_segments * 5.0

    if estimated_runtime_s < 60:
        risk_level = "LOW"
    elif estimated_runtime_s < 180:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "n_segments": n_segments,
        "total_dates": total_dates,
        "estimated_rows": int(estimated_rows),
        "estimated_runtime_seconds": estimated_runtime_s,
        "risk_level": risk_level,
    }
