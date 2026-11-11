"""
P11-D: Forward Collection Readiness Monitor — Tests
tests/test_forward_collection_readiness_monitor_p11.py

paper_only=true。不做任何外部呼叫。不修改 TSL crawler。
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.monitor_forward_collection_readiness_p11 import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_TIMELINE_PATH,
    MIN_PAIR_COVERAGE_PCT,
    MIN_PAIRS_FOR_CLV,
    ForwardReadinessResult,
    ForwardReadinessStatus,
    PaperOnlyViolationError,
    compute_forward_readiness,
    run_forward_collection_monitor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAME_START = datetime(2026, 5, 15, 18, 0, 0, tzinfo=timezone.utc)


def _pregame_entry(match_id: str, hours_before: float = 3.0, market: str = "ML") -> dict:
    captured = _GAME_START - timedelta(hours=hours_before)
    return {
        "match_id": match_id,
        "snapshot_type": "PREGAME",
        "captured_at_utc": captured.isoformat(),
        "game_start_utc": _GAME_START.isoformat(),
        "market_code": market,
    }


def _closing_entry(match_id: str, minutes_before: float = 30.0, market: str = "ML") -> dict:
    captured = _GAME_START - timedelta(minutes=minutes_before)
    return {
        "match_id": match_id,
        "snapshot_type": "CLOSING",
        "captured_at_utc": captured.isoformat(),
        "game_start_utc": _GAME_START.isoformat(),
        "market_code": market,
    }


def _post_game_entry(match_id: str, market: str = "ML") -> dict:
    captured = _GAME_START + timedelta(hours=4)
    return {
        "match_id": match_id,
        "snapshot_type": "POST_GAME_PROXY",
        "captured_at_utc": captured.isoformat(),
        "game_start_utc": _GAME_START.isoformat(),
        "market_code": market,
    }


def _write_timeline(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


# ---------------------------------------------------------------------------
# 1. Empty timeline → ACCUMULATION_INSUFFICIENT
# ---------------------------------------------------------------------------

class TestEmptyTimeline:
    def test_missing_file_gives_insufficient(self, tmp_path):
        result = compute_forward_readiness(
            timeline_path=tmp_path / "nonexistent.jsonl",
            manifest_path=tmp_path / "no_manifest.json",
        )
        assert result.status == ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT

    def test_empty_file_gives_insufficient(self, tmp_path):
        tl = tmp_path / "timeline.jsonl"
        tl.write_text("")
        result = compute_forward_readiness(
            timeline_path=tl,
            manifest_path=tmp_path / "no_manifest.json",
        )
        assert result.status == ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT
        assert result.total_snapshots == 0

    def test_zero_counts_on_empty(self, tmp_path):
        tl = tmp_path / "timeline.jsonl"
        tl.write_text("")
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.pregame_candidate_count == 0
        assert result.closing_candidate_count == 0
        assert result.pair_count == 0
        assert result.pair_coverage_pct == 0.0


# ---------------------------------------------------------------------------
# 2. Only pregame, no closing → BLOCKED_NO_CLOSING_LINE
# ---------------------------------------------------------------------------

class TestOnlyPregame:
    def test_only_pregame_no_closing(self, tmp_path):
        entries = [_pregame_entry(f"GAME_{i:03d}") for i in range(10)]
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.status == ForwardReadinessStatus.BLOCKED_NO_CLOSING_LINE

    def test_only_pregame_closing_count_zero(self, tmp_path):
        entries = [_pregame_entry(f"GAME_{i:03d}") for i in range(5)]
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.closing_candidate_count == 0
        assert result.pregame_candidate_count == 5

    def test_post_game_only_gives_insufficient(self, tmp_path):
        """POST_GAME_PROXY entries alone → no pregame → ACCUMULATION_INSUFFICIENT."""
        entries = [_post_game_entry(f"GAME_{i:03d}") for i in range(5)]
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.status == ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT
        assert result.pregame_candidate_count == 0


# ---------------------------------------------------------------------------
# 3. Valid pregame+closing pairs counted correctly
# ---------------------------------------------------------------------------

class TestPairCounting:
    def test_pair_count_equals_games_with_both(self, tmp_path):
        entries = []
        for i in range(50):
            gid = f"GAME_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.pair_count == 50

    def test_partial_pairs_not_counted(self, tmp_path):
        """Some games have only pregame, not counted as pairs."""
        entries = []
        # 30 games with both
        for i in range(30):
            gid = f"PAIRED_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        # 10 games with only pregame
        for i in range(10):
            gid = f"PREGAME_ONLY_{i:03d}"
            entries.append(_pregame_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.pair_count == 30
        assert result.missing_closing_count == 10

    def test_post_game_excluded_from_pairs(self, tmp_path):
        """POST_GAME_PROXY does not count as CLOSING for pairing."""
        entries = []
        for i in range(20):
            gid = f"GAME_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_post_game_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.closing_candidate_count == 0
        assert result.pair_count == 0
        assert result.status == ForwardReadinessStatus.BLOCKED_NO_CLOSING_LINE


# ---------------------------------------------------------------------------
# 4. Duplicate snapshots deterministically deduplicated
# ---------------------------------------------------------------------------

class TestDuplicateSnapshots:
    def test_duplicate_by_filename_deduplicated(self, tmp_path):
        entry = _pregame_entry("GAME_001")
        entry["filename"] = "tsl_GAME_001_ML_pregame_20260515T150000Z.json"
        entries = [entry, dict(entry), dict(entry)]  # 3 identical (same filename)
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.duplicate_snapshot_count == 2
        assert result.total_snapshots == 3

    def test_duplicate_by_key_deduplicated(self, tmp_path):
        """Same match_id + market + snapshot_type + minute → deduplicated."""
        e1 = _pregame_entry("GAME_002", hours_before=3.0)  # same minute
        e2 = _pregame_entry("GAME_002", hours_before=3.0)  # same minute → duplicate
        tl = tmp_path / "timeline.jsonl"
        _write_timeline([e1, e2], tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.duplicate_snapshot_count == 1

    def test_different_minutes_not_duplicates(self, tmp_path):
        """Same game + type but different minutes → not duplicates."""
        e1 = _pregame_entry("GAME_003", hours_before=3.0)
        e2 = _pregame_entry("GAME_003", hours_before=2.0)  # different minute
        tl = tmp_path / "timeline.jsonl"
        _write_timeline([e1, e2], tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.duplicate_snapshot_count == 0


# ---------------------------------------------------------------------------
# 5. No network call
# ---------------------------------------------------------------------------

class TestNoNetworkCall:
    def test_result_network_call_false(self, tmp_path):
        result = compute_forward_readiness(
            timeline_path=tmp_path / "no.jsonl",
            manifest_path=tmp_path / "no.json",
        )
        assert result.network_call is False

    def test_result_crawler_modified_false(self, tmp_path):
        result = compute_forward_readiness(
            timeline_path=tmp_path / "no.jsonl",
            manifest_path=tmp_path / "no.json",
        )
        assert result.crawler_modified is False

    def test_no_network_import_in_script(self):
        script = (
            Path(__file__).parent.parent
            / "scripts"
            / "monitor_forward_collection_readiness_p11.py"
        ).read_text()
        assert "import requests" not in script
        assert "import urllib" not in script
        assert "import socket" not in script
        assert "import tsl_crawler" not in script
        assert "from tsl_crawler" not in script


# ---------------------------------------------------------------------------
# 6. Manifest paper_only=true
# ---------------------------------------------------------------------------

class TestManifestPaperOnly:
    def test_paper_only_violation_raises(self, tmp_path):
        with pytest.raises(PaperOnlyViolationError):
            compute_forward_readiness(
                timeline_path=tmp_path / "no.jsonl",
                manifest_path=tmp_path / "no.json",
                paper_only=False,
            )

    def test_result_paper_only_true(self, tmp_path):
        result = compute_forward_readiness(
            timeline_path=tmp_path / "no.jsonl",
            manifest_path=tmp_path / "no.json",
            paper_only=True,
        )
        assert result.paper_only is True

    def test_manifest_paper_only_flag_read_ok(self, tmp_path):
        """Manifest with paper_only=true is loaded without error."""
        manifest = {"task": "P10-D", "paper_only": True, "network_call": False}
        mp = tmp_path / "manifest.json"
        mp.write_text(json.dumps(manifest))
        result = compute_forward_readiness(
            timeline_path=tmp_path / "no.jsonl",
            manifest_path=mp,
        )
        # Should still return ACCUMULATION_INSUFFICIENT since no timeline
        assert result.status == ForwardReadinessStatus.ACCUMULATION_INSUFFICIENT


# ---------------------------------------------------------------------------
# 7. Threshold < target → BLOCKED_LOW_COVERAGE
# ---------------------------------------------------------------------------

class TestThresholdBelowTarget:
    def test_pairs_below_200_blocked(self, tmp_path):
        entries = []
        for i in range(50):  # 50 pairs < 200
            gid = f"GAME_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.status == ForwardReadinessStatus.BLOCKED_LOW_COVERAGE
        assert result.pair_count == 50
        assert result.pair_count < MIN_PAIRS_FOR_CLV

    def test_coverage_below_90_blocked(self, tmp_path):
        """80% coverage → BLOCKED_LOW_COVERAGE even if pairs ≥ 200."""
        entries = []
        # 200 pairs
        for i in range(200):
            gid = f"PAIRED_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        # 50 games pregame-only (coverage = 200/250 = 80%)
        for i in range(50):
            gid = f"MISSING_{i:03d}"
            entries.append(_pregame_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.pair_count == 200
        assert result.pair_coverage_pct < MIN_PAIR_COVERAGE_PCT
        assert result.status == ForwardReadinessStatus.BLOCKED_LOW_COVERAGE

    def test_min_pairs_constant_matches_p8_p9(self):
        assert MIN_PAIRS_FOR_CLV == 200

    def test_min_coverage_constant_matches_p8_p9(self):
        assert MIN_PAIR_COVERAGE_PCT == 90.0


# ---------------------------------------------------------------------------
# 8. Threshold >= target → CLV_READY_CANDIDATE
# ---------------------------------------------------------------------------

class TestThresholdAtOrAboveTarget:
    def test_200_pairs_100_coverage_ready(self, tmp_path):
        entries = []
        for i in range(200):
            gid = f"GAME_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.status == ForwardReadinessStatus.CLV_READY_CANDIDATE
        assert result.pair_count == 200
        assert result.pair_coverage_pct == 100.0

    def test_300_pairs_91_coverage_ready(self, tmp_path):
        entries = []
        for i in range(300):  # 300 pairs
            gid = f"PAIRED_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        # 27 pregame-only (coverage = 300/327 ≈ 91.7%)
        for i in range(27):
            gid = f"MISSING_{i:03d}"
            entries.append(_pregame_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        result = compute_forward_readiness(timeline_path=tl, manifest_path=tmp_path / "m.json")
        assert result.status == ForwardReadinessStatus.CLV_READY_CANDIDATE
        assert result.pair_coverage_pct >= MIN_PAIR_COVERAGE_PCT

    def test_clv_gate_passed_true_when_ready(self, tmp_path):
        entries = []
        for i in range(200):
            gid = f"GAME_{i:03d}"
            entries.append(_pregame_entry(gid))
            entries.append(_closing_entry(gid))
        tl = tmp_path / "timeline.jsonl"
        _write_timeline(entries, tl)
        out = run_forward_collection_monitor(
            timeline_path=tl,
            manifest_path=tmp_path / "m.json",
            output_path=None,
        )
        assert out["clv_gate_passed"] is True
        assert out["network_call"] is False
        assert out["crawler_modified"] is False


# ---------------------------------------------------------------------------
# 9. Output file writes valid JSON
# ---------------------------------------------------------------------------

class TestOutputFile:
    def test_output_json_written(self, tmp_path):
        tl = tmp_path / "timeline.jsonl"
        out = tmp_path / "out.json"
        run_forward_collection_monitor(
            timeline_path=tl,
            manifest_path=tmp_path / "m.json",
            output_path=out,
        )
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["task"] == "P11-D"
        assert data["paper_only"] is True

    def test_output_has_all_required_keys(self, tmp_path):
        out = tmp_path / "out.json"
        run_forward_collection_monitor(
            timeline_path=tmp_path / "no.jsonl",
            manifest_path=tmp_path / "no.json",
            output_path=out,
        )
        data = json.loads(out.read_text())
        required = {
            "task", "paper_only", "network_call", "crawler_modified",
            "total_snapshots", "pair_count", "pair_coverage_pct",
            "clv_readiness_status", "clv_gate_passed",
        }
        for key in required:
            assert key in data, f"Missing key: {key}"
