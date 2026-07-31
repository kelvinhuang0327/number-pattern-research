"""
P11-D: Forward Collection Readiness Monitor

讀取既有 TSL odds timeline，計算 pregame+closing pair count 與 CLV gate 距離。
不做任何外部呼叫。不修改 TSL crawler。paper_only=true 強制執行。

Timeline 格式（tsl_odds_history.jsonl，每行一個 JSON 物件）：
  {
    "match_id":       str,          # 比賽 ID
    "snapshot_type":  str,          # PREGAME | CLOSING | POST_GAME_PROXY | UNKNOWN
    "captured_at_utc": str,         # ISO 8601 UTC
    "game_start_utc":  str,         # ISO 8601 UTC
    "market_code":     str,         # ML | RL | OU
    "filename":        str | null   # 決定性檔名（可選，供去重使用）
  }
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants (must align with P8/P9/P10 thresholds)
# ---------------------------------------------------------------------------
MIN_PAIRS_FOR_CLV: int = 200
MIN_PAIR_COVERAGE_PCT: float = 90.0
MIN_TIMESTAMP_COVERAGE_PCT: float = 95.0

DEFAULT_TIMELINE_PATH = Path("data/tsl_odds_history.jsonl")
DEFAULT_MANIFEST_PATH = Path(
    "data/paper_recommendations/p10_forward_collection_activation_manifest_20260526.json"
)
DEFAULT_OUTPUT_PATH = Path(
    "data/paper_recommendations/p11_forward_collection_readiness_20260527.json"
)

# ---------------------------------------------------------------------------
# Status Enum
# ---------------------------------------------------------------------------


class ForwardReadinessStatus(str, Enum):
    """Readiness status for forward collection CLV gate."""

    ACCUMULATION_INSUFFICIENT = "ACCUMULATION_INSUFFICIENT"
    """Timeline absent or has 0 valid snapshots; cannot compute pairs."""

    BLOCKED_NO_CLOSING_LINE = "BLOCKED_NO_CLOSING_LINE"
    """Pregame snapshots exist but 0 confirmed closing snapshots."""

    BLOCKED_LOW_COVERAGE = "BLOCKED_LOW_COVERAGE"
    """Pairs exist but below MIN_PAIRS_FOR_CLV or MIN_PAIR_COVERAGE_PCT."""

    CLV_READY_CANDIDATE = "CLV_READY_CANDIDATE"
    """pair_count >= 200 and pair_coverage_pct >= 90.0 — CLV gate can proceed."""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ForwardReadinessError(RuntimeError):
    """Unrecoverable error in readiness monitor."""


class PaperOnlyViolationError(RuntimeError):
    """Raised when paper_only=False is passed."""


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ForwardReadinessResult:
    """Output of compute_forward_readiness."""

    status: ForwardReadinessStatus
    total_snapshots: int
    unique_games: int
    pregame_candidate_count: int
    closing_candidate_count: int
    pair_count: int
    pair_coverage_pct: float
    missing_closing_count: int
    duplicate_snapshot_count: int
    clv_readiness_status: str
    min_pairs_target: int = MIN_PAIRS_FOR_CLV
    min_coverage_target: float = MIN_PAIR_COVERAGE_PCT
    paper_only: bool = True
    network_call: bool = False
    crawler_modified: bool = False
    annotation: str = (
        "paper_only=true。此為 P11-D Forward Accumulation Monitor 唯讀分析。"
        "不代表任何實盤獲利能力。"
    )


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------


def _parse_snapshot_type(raw: str) -> str:
    """Normalise snapshot_type string to uppercase."""
    return (raw or "UNKNOWN").strip().upper()


def _dedup_key(entry: dict[str, Any], index: int) -> str:
    """
    Produce a deterministic deduplication key for a snapshot entry.

    Uses filename if present; otherwise falls back to
    (match_id, market_code, snapshot_type, minute_bucket_of_captured_at_utc).
    """
    if entry.get("filename"):
        return str(entry["filename"])
    match_id = entry.get("match_id", f"UNKNOWN_MATCH_{index}")
    market_code = entry.get("market_code", "UNKNOWN_MARKET")
    snapshot_type = _parse_snapshot_type(entry.get("snapshot_type", "UNKNOWN"))
    captured_raw = entry.get("captured_at_utc", "")
    try:
        dt = datetime.fromisoformat(captured_raw.replace("Z", "+00:00"))
        minute_ts = dt.strftime("%Y%m%dT%H%M")
    except (ValueError, AttributeError):
        minute_ts = captured_raw[:16].replace(":", "").replace("-", "").replace("T", "T")
    return f"{match_id}_{market_code}_{snapshot_type}_{minute_ts}"


def compute_forward_readiness(
    timeline_path: Path = DEFAULT_TIMELINE_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    min_pairs: int = MIN_PAIRS_FOR_CLV,
    min_coverage_pct: float = MIN_PAIR_COVERAGE_PCT,
    paper_only: bool = True,
) -> ForwardReadinessResult:
    """
    Read timeline and compute forward collection readiness.

    Does NOT make any network calls.
    Does NOT modify TSL crawler.
    Raises PaperOnlyViolationError if paper_only=False.
    """
    if not paper_only:
        raise PaperOnlyViolationError(
            "compute_forward_readiness: paper_only must be True. "
            "Production collection not permitted."
        )

    # --- Load manifest for context (optional; don't fail if absent) ---
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    # --- Load timeline ---
    if not timeline_path.exists():
        return ForwardReadinessResult(
            status=ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT,
            total_snapshots=0,
            unique_games=0,
            pregame_candidate_count=0,
            closing_candidate_count=0,
            pair_count=0,
            pair_coverage_pct=0.0,
            missing_closing_count=0,
            duplicate_snapshot_count=0,
            clv_readiness_status=ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT.value,
        )

    # --- Parse entries ---
    raw_entries: list[dict[str, Any]] = []
    parse_errors = 0
    try:
        with timeline_path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    parse_errors += 1
    except OSError as exc:
        raise ForwardReadinessError(
            f"Cannot read timeline {timeline_path}: {exc}"
        ) from exc

    total_snapshots = len(raw_entries)

    if total_snapshots == 0:
        return ForwardReadinessResult(
            status=ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT,
            total_snapshots=0,
            unique_games=0,
            pregame_candidate_count=0,
            closing_candidate_count=0,
            pair_count=0,
            pair_coverage_pct=0.0,
            missing_closing_count=0,
            duplicate_snapshot_count=0,
            clv_readiness_status=ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT.value,
        )

    # --- Deduplication ---
    seen_keys: set[str] = set()
    unique_entries: list[dict[str, Any]] = []
    duplicate_count = 0
    for i, entry in enumerate(raw_entries):
        key = _dedup_key(entry, i)
        if key in seen_keys:
            duplicate_count += 1
        else:
            seen_keys.add(key)
            unique_entries.append(entry)

    # --- Per-game + per-type accounting ---
    game_ids: set[str] = set()
    games_with_pregame: set[str] = set()
    games_with_closing: set[str] = set()
    pregame_count = 0
    closing_count = 0

    for i, entry in enumerate(unique_entries):
        match_id = entry.get("match_id", f"UNKNOWN_MATCH_{i}")
        snap_type = _parse_snapshot_type(entry.get("snapshot_type", "UNKNOWN"))
        game_ids.add(match_id)

        if snap_type == "PREGAME":
            pregame_count += 1
            games_with_pregame.add(match_id)
        elif snap_type == "CLOSING":
            closing_count += 1
            games_with_closing.add(match_id)
        # POST_GAME_PROXY / UNKNOWN → excluded from CLV pairing

    unique_games = len(game_ids)

    # --- Pair calculation ---
    paired_games = games_with_pregame & games_with_closing
    pair_count = len(paired_games)
    missing_closing_count = len(games_with_pregame - games_with_closing)

    if unique_games > 0:
        pair_coverage_pct = round(pair_count / unique_games * 100, 2)
    else:
        pair_coverage_pct = 0.0

    # --- Status determination ---
    if pregame_count == 0:
        status = ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT
    elif closing_count == 0:
        status = ForwardReadinessStatus.BLOCKED_NO_CLOSING_LINE
    elif pair_count < min_pairs or pair_coverage_pct < min_coverage_pct:
        status = ForwardReadinessStatus.BLOCKED_LOW_COVERAGE
    else:
        status = ForwardReadinessStatus.CLV_READY_CANDIDATE

    return ForwardReadinessResult(
        status=status,
        total_snapshots=total_snapshots,
        unique_games=unique_games,
        pregame_candidate_count=pregame_count,
        closing_candidate_count=closing_count,
        pair_count=pair_count,
        pair_coverage_pct=pair_coverage_pct,
        missing_closing_count=missing_closing_count,
        duplicate_snapshot_count=duplicate_count,
        clv_readiness_status=status.value,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_forward_collection_monitor(
    timeline_path: Path = DEFAULT_TIMELINE_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_path: Optional[Path] = DEFAULT_OUTPUT_PATH,
    paper_only: bool = True,
) -> dict[str, Any]:
    """Run the readiness monitor and write JSON artifact."""
    result = compute_forward_readiness(
        timeline_path=timeline_path,
        manifest_path=manifest_path,
        paper_only=paper_only,
    )

    output: dict[str, Any] = {
        "task": "P11-D",
        "title": "Forward Collection Readiness Monitor",
        "run_date": datetime.now(timezone.utc).isoformat(),
        "paper_only": result.paper_only,
        "network_call": result.network_call,
        "crawler_modified": result.crawler_modified,
        "timeline_path": str(timeline_path),
        "manifest_path": str(manifest_path),
        "total_snapshots": result.total_snapshots,
        "unique_games": result.unique_games,
        "pregame_candidate_count": result.pregame_candidate_count,
        "closing_candidate_count": result.closing_candidate_count,
        "pair_count": result.pair_count,
        "pair_coverage_pct": result.pair_coverage_pct,
        "missing_closing_count": result.missing_closing_count,
        "duplicate_snapshot_count": result.duplicate_snapshot_count,
        "clv_readiness_status": result.clv_readiness_status,
        "min_pairs_target": result.min_pairs_target,
        "min_coverage_target": result.min_coverage_target,
        "clv_gate_passed": result.status == ForwardReadinessStatus.CLV_READY_CANDIDATE,
        "annotation": result.annotation,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base = Path(__file__).parent.parent
    result = run_forward_collection_monitor(
        timeline_path=base / DEFAULT_TIMELINE_PATH,
        manifest_path=base / DEFAULT_MANIFEST_PATH,
        output_path=base / DEFAULT_OUTPUT_PATH,
    )
    print(f"Written: {DEFAULT_OUTPUT_PATH}")
    print(f"  status:            {result['clv_readiness_status']}")
    print(f"  total_snapshots:   {result['total_snapshots']}")
    print(f"  pair_count:        {result['pair_count']} / {result['min_pairs_target']}")
    print(f"  pair_coverage_pct: {result['pair_coverage_pct']}% / {result['min_coverage_target']}%")
    print(f"  clv_gate_passed:   {result['clv_gate_passed']}")
