"""
wbc_backend/recommendation/p27_p26_segmented_replay_runner.py

P27 — P26 segmented replay runner.

For each P27ExpansionSegment, invokes the existing P26 CLI
(scripts/run_p26_true_date_historical_backfill.py) and collects results.
Blocked segments are reported, not hidden.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    P27ExpansionSegment,
)


_P26_SCRIPT = "scripts/run_p26_true_date_historical_backfill.py"
_P26_GATE_READY = "P26_TRUE_DATE_HISTORICAL_BACKFILL_READY"


# ---------------------------------------------------------------------------
# Per-segment runner
# ---------------------------------------------------------------------------


def run_p26_replay_for_segment(
    segment: P27ExpansionSegment,
    p25_dir: Path,
    output_base_dir: Path,
    cwd: Optional[str] = None,
) -> Dict:
    """
    Run P26 CLI for a single segment.

    p25_dir: the P25 output dir specific to this segment's date range.
    output_base_dir: base dir; the actual segment output will be placed under
        p26_true_date_historical_backfill_{start}_{end}/ inside it.

    Returns a dict with keys:
      segment_index, date_start, date_end, returncode, p26_gate,
      stdout, stderr, output_dir, gate_data (dict), blocked
    """
    repo_root = Path(cwd) if cwd else Path.cwd()
    script_path = repo_root / _P26_SCRIPT
    if not script_path.exists():
        return _blocked_segment_result(
            segment,
            reason=f"P26 script not found: {script_path}",
        )

    seg_out_dir = (
        output_base_dir
        / f"p26_true_date_historical_backfill_{segment.date_start}_{segment.date_end}"
    )

    cmd = [
        sys.executable,
        str(script_path),
        "--date-start", segment.date_start,
        "--date-end", segment.date_end,
        "--p25-dir", str(p25_dir),
        "--output-dir", str(seg_out_dir),
        "--paper-only", "true",
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=_make_env(),
    )

    gate_data = _read_gate_result(seg_out_dir)
    blocked = gate_data.get("p26_gate", "") != _P26_GATE_READY

    return {
        "segment_index": segment.segment_index,
        "date_start": segment.date_start,
        "date_end": segment.date_end,
        "returncode": proc.returncode,
        "p26_gate": gate_data.get("p26_gate", "UNKNOWN"),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "output_dir": str(seg_out_dir),
        "gate_data": gate_data,
        "blocked": blocked,
    }


def run_p26_replay_for_all_segments(
    segments: List[P27ExpansionSegment],
    p25_base_dir: Path,
    output_base_dir: Path,
    cwd: Optional[str] = None,
) -> List[Dict]:
    """
    Run P26 replay for every segment sequentially.

    p25_base_dir: the root of the full-range P25 output
      (expected to contain true_date_slices/<date>/p15_true_date_input.csv).

    Blocked segments are included in the results — execution continues.
    Returns list of per-segment result dicts (same schema as run_p26_replay_for_segment).
    """
    results: List[Dict] = []
    for seg in segments:
        res = run_p26_replay_for_segment(
            segment=seg,
            p25_dir=p25_base_dir,
            output_base_dir=output_base_dir,
            cwd=cwd,
        )
        results.append(res)
    return results


def summarize_segment_replay_results(segment_results: List[Dict]) -> Dict:
    """
    Aggregate per-segment results into a summary dict.

    ROI = total_pnl / total_stake (weighted, not averaged).
    Hit rate = total_wins / (total_wins + total_losses).
    """
    n_total = len(segment_results)
    n_ready = sum(1 for r in segment_results if not r.get("blocked", True))
    n_blocked = n_total - n_ready

    total_active = 0
    total_win = 0
    total_loss = 0
    total_unsettled = 0
    total_stake = 0.0
    total_pnl = 0.0

    for r in segment_results:
        gd = r.get("gate_data", {})
        total_active += gd.get("total_active_entries", 0)
        total_win += gd.get("total_settled_win", 0)
        total_loss += gd.get("total_settled_loss", 0)
        total_unsettled += gd.get("total_unsettled", 0)
        total_stake += gd.get("total_stake_units", 0.0)
        total_pnl += gd.get("total_pnl_units", 0.0)

    roi = total_pnl / total_stake if total_stake > 0 else 0.0
    settled = total_win + total_loss
    hit_rate = total_win / settled if settled > 0 else 0.0

    blocked_labels = [
        f"{r['date_start']}_{r['date_end']}"
        for r in segment_results
        if r.get("blocked", True)
    ]

    return {
        "n_segments": n_total,
        "n_segments_ready": n_ready,
        "n_segments_blocked": n_blocked,
        "total_active_entries": total_active,
        "total_settled_win": total_win,
        "total_settled_loss": total_loss,
        "total_unsettled": total_unsettled,
        "total_stake_units": total_stake,
        "total_pnl_units": total_pnl,
        "aggregate_roi_units": roi,
        "aggregate_hit_rate": hit_rate,
        "blocked_segment_labels": blocked_labels,
        "paper_only": True,
        "production_ready": False,
    }


def validate_segment_replay_outputs(segment_results: List[Dict]) -> Tuple[bool, str]:
    """
    Validate all segment results are structurally sound.

    Returns (is_valid, reason). is_valid=True even if some segments are blocked
    (blocked is expected and must be reported, not treated as invalid structure).
    """
    for r in segment_results:
        required_keys = {"segment_index", "date_start", "date_end", "p26_gate", "blocked"}
        missing = required_keys - r.keys()
        if missing:
            return False, f"Segment {r.get('segment_index', '?')} missing keys: {missing}"
        gd = r.get("gate_data", None)
        if gd is None:
            return False, f"Segment {r.get('segment_index')} has no gate_data"
    return True, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_gate_result(output_dir: Path) -> Dict:
    """Read p26_gate_result.json from segment output dir. Returns {} on failure."""
    gate_path = output_dir / "p26_gate_result.json"
    if not gate_path.exists():
        return {}
    try:
        return json.loads(gate_path.read_text())
    except Exception:
        return {}


def _blocked_segment_result(segment: P27ExpansionSegment, reason: str) -> Dict:
    return {
        "segment_index": segment.segment_index,
        "date_start": segment.date_start,
        "date_end": segment.date_end,
        "returncode": 2,
        "p26_gate": "P27_BLOCKED_P26_REPLAY_FAILED",
        "stdout": "",
        "stderr": reason,
        "output_dir": "",
        "gate_data": {},
        "blocked": True,
    }


def _make_env() -> Dict[str, str]:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    return env
