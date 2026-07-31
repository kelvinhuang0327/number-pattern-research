"""
P10-D: PATH B Forward-Only Activation Manifest
Converts the P9 daily forward schedule into an executable paper-only manifest.
No network calls. No crawler modification. No live write.
paper_only=true enforced.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────────────
MIN_PAIRS_FOR_CLV = 200
MIN_PAIR_COVERAGE_PCT = 90.0
MIN_TIMESTAMP_COVERAGE_PCT = 95.0
CLOSING_WINDOW_SEC = 3600
PREGAME_MIN_SEC = 60

TARGET_MARKETS = [
    {"code": "ML", "name": "Moneyline", "priority": 1, "minimum_viable": True},
    {"code": "RL", "name": "Run Line", "priority": 2, "minimum_viable": False},
    {"code": "OU", "name": "Over/Under", "priority": 3, "minimum_viable": False},
]

PREGAME_WINDOWS = [
    {
        "label": "early",
        "hours_before_game": [24, 72],
        "priority": "NICE_TO_HAVE",
        "snapshot_type": "pregame",
        "critical": False,
    },
    {
        "label": "pregame_d1",
        "hours_before_game": [6, 24],
        "priority": "HIGH",
        "snapshot_type": "pregame",
        "critical": False,
    },
    {
        "label": "pregame_d2",
        "hours_before_game": [2, 6],
        "priority": "CRITICAL",
        "snapshot_type": "pregame",
        "critical": True,
    },
    {
        "label": "decision",
        "hours_before_game": [0.5, 2],
        "priority": "CRITICAL",
        "snapshot_type": "decision",
        "critical": True,
    },
]

CLOSING_WINDOWS = [
    {
        "label": "closing_final",
        "hours_before_game": [0, 1],
        "priority": "CRITICAL",
        "snapshot_type": "closing",
        "critical": True,
    },
]

FAILURE_REASON_TAXONOMY = {
    "CRAWLER_FETCH_FAILED": (
        "TSL crawler fetch returned error or timeout; "
        "skip window, retry next cron cycle"
    ),
    "MISSING_SNAPSHOT_TYPE": (
        "snapshot_type absent; "
        "infer from captured_at_utc vs game_start_utc delta"
    ),
    "API_TIMEOUT": (
        "HTTP timeout; 3 retries with exponential backoff (1s, 4s, 16s); "
        "mark FAILED_SNAPSHOT after retry limit"
    ),
    "PAPER_ONLY_VIOLATION": (
        "paper_only=False detected; "
        "raise PaperOnlyViolationError; halt batch"
    ),
    "POST_GAME_PROXY_MISCLASSIFY": (
        "captured_at_utc > game_start_utc but typed as PREGAME/CLOSING; "
        "reject snapshot"
    ),
    "DUPLICATE_SNAPSHOT": (
        "same match_id + market_code + window_label + same minute bucket; "
        "skip"
    ),
    "CLOSING_WINDOW_OUTSIDE_RANGE": (
        "captured_at_utc not within CLOSING_WINDOW_SEC of game_start_utc; "
        "reject as closing"
    ),
    "PREGAME_BEFORE_MIN_SEC": (
        "captured_at_utc delta < PREGAME_MIN_SEC before game_start; "
        "reject as pregame"
    ),
}

EXPECTED_TAXONOMY_KEYS = frozenset(FAILURE_REASON_TAXONOMY.keys())


class ForwardManifestError(Exception):
    pass


class PaperOnlyViolationError(ForwardManifestError):
    """Raised when paper_only=False is passed to manifest generation."""


def build_snapshot_filename(
    match_id: str,
    market_code: str,
    window_label: str,
    captured_at_utc: datetime,
) -> str:
    """Return a deterministic snapshot filename.

    Determinism: same (match_id, market_code, window_label, minute) → same name.
    Minute-bucketed so sub-minute re-fetches map to the same file (duplicate
    detection without a database).
    """
    minute_ts = captured_at_utc.strftime("%Y%m%dT%H%M00Z")
    return f"tsl_{match_id}_{market_code}_{window_label}_{minute_ts}.json"


def build_forward_collection_manifest(
    *,
    paper_only: bool = True,
    run_date: Optional[datetime] = None,
    base_output_dir: str = "data/paper_recommendations/forward_snapshots",
    target_games_source: str = "TSL_LIVE_CRAWLER",
) -> dict:
    """Build the P10-D forward-only activation manifest.

    Raises PaperOnlyViolationError if paper_only=False.
    Makes no network calls. Does not import or modify tsl_crawler.
    """
    if not paper_only:
        raise PaperOnlyViolationError(
            "paper_only=False is not permitted for P10-D manifest generation."
        )

    if run_date is None:
        run_date = datetime.now(timezone.utc)

    manifest: dict = {
        "task": "P10-D",
        "title": "Forward-Only Activation Manifest",
        "run_date": run_date.isoformat(),
        "paper_only": True,
        "network_call": False,
        "crawler_modified": False,
        "production_write": False,
        "target_games_source": target_games_source,
        "pregame_windows": PREGAME_WINDOWS,
        "closing_windows": CLOSING_WINDOWS,
        "market_priority": TARGET_MARKETS,
        "output_path_plan": {
            "base_dir": base_output_dir,
            "naming_convention": (
                "tsl_{match_id}_{market_code}_{window_label}_{yyyymmddThhmmssZ}.json"
            ),
            "example": "tsl_G2026031501_ML_closing_final_20260315T203000Z.json",
            "paper_only_path": True,
        },
        "duplicate_snapshot_policy": {
            "rule": "SKIP_IF_EXISTS",
            "dedup_key": ["match_id", "market_code", "window_label", "minute_bucket"],
            "deterministic": True,
            "description": (
                "Same match_id + market_code + window_label + same-minute timestamp "
                "→ SKIP. Implemented via deterministic filename collision."
            ),
        },
        "replay_safe_append_policy": {
            "mode": "APPEND_ONLY",
            "overwrite": False,
            "description": (
                "New snapshots appended to existing JSONL; never overwrite existing records. "
                "Idempotent on replay."
            ),
        },
        "failure_reason_taxonomy": FAILURE_REASON_TAXONOMY,
        "clv_gate_thresholds": {
            "min_pairs": MIN_PAIRS_FOR_CLV,
            "min_pair_coverage_pct": MIN_PAIR_COVERAGE_PCT,
            "min_timestamp_coverage_pct": MIN_TIMESTAMP_COVERAGE_PCT,
            "closing_window_sec": CLOSING_WINDOW_SEC,
            "pregame_min_sec": PREGAME_MIN_SEC,
        },
        "ceo_decision_dependency": (
            "PATH B activation does not require CEO approval for forward collection. "
            "However, CLV validation requires 200+ pregame/closing pairs at 90%+ coverage."
        ),
        "annotation": (
            "paper_only=true。此為 P10-D 前向收集啟動 manifest。"
            "TSL crawler 未修改。不做任何網路呼叫。"
            "不代表任何實盤獲利能力。"
        ),
    }
    return manifest


def run_forward_collection_manifest(
    output_path: Optional[str] = None,
) -> dict:
    """Generate and optionally persist the P10-D manifest. No network calls."""
    manifest = build_forward_collection_manifest(paper_only=True)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


if __name__ == "__main__":
    out = Path(
        "data/paper_recommendations"
        "/p10_forward_collection_activation_manifest_20260526.json"
    )
    result = run_forward_collection_manifest(output_path=str(out))
    print(f"Written: {out}")
    print(f"  paper_only:        {result['paper_only']}")
    print(f"  network_call:      {result['network_call']}")
    print(f"  crawler_modified:  {result['crawler_modified']}")
    print(f"  pregame_windows:   {len(result['pregame_windows'])}")
    print(f"  closing_windows:   {len(result['closing_windows'])}")
    print(f"  failure_taxonomy:  {len(result['failure_reason_taxonomy'])} entries")
