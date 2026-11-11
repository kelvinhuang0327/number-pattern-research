"""
P8-D Tests — 2026 TSL Forward Collection Plan

驗收條件：
- 現有 timeline 可被 summarize
- 無網路呼叫
- 未修改 crawler
- 排程包含 pregame + closing
- threshold >= P7 requirement
- paper_only=true
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from scripts.plan_2026_tsl_forward_collection_p8 import (
    JSONL_PATH,
    MIN_PAIR_COVERAGE_PCT,
    MIN_PAIRS_FOR_CLV,
    MIN_TIMESTAMP_COVERAGE_PCT,
    SCHEDULE_WINDOWS,
    TARGET_MARKETS,
    ForwardCollectionError,
    build_collection_manifest,
    run_forward_collection_plan,
    summarize_existing_timeline,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_jsonl_content() -> str:
    """Minimal JSONL content with pregame + closing records."""
    records = []
    # Two games: each with pregame + closing
    for i in range(1, 6):
        match_id = f"game_{i:04d}.1"
        game_time_utc = f"2026-05-{15 + i:02d}T03:30:00+00:00"
        pregame_at = f"2026-05-{15 + i - 1:02d}T18:00:00+00:00"  # ~9.5h before
        closing_at = f"2026-05-{15 + i:02d}T03:00:00+00:00"  # 30min before

        records.append(json.dumps({
            "match_id": match_id,
            "game_time": game_time_utc,
            "fetched_at": pregame_at,
            "snapshot_type": "pregame",
            "markets": [{"marketCode": "ML", "outcomes": []}],
        }))
        records.append(json.dumps({
            "match_id": match_id,
            "game_time": game_time_utc,
            "fetched_at": closing_at,
            "snapshot_type": "closing",
            "markets": [{"marketCode": "ML", "outcomes": []}],
        }))
    return "\n".join(records)


@pytest.fixture()
def sample_jsonl_file(sample_jsonl_content, tmp_path) -> Path:
    f = tmp_path / "tsl_odds_history.jsonl"
    f.write_text(sample_jsonl_content, encoding="utf-8")
    return f


# ── P8-D-1: existing timeline can be summarized ───────────────────────────────

class TestTimelineSummarized:
    def test_summary_file_not_found_returns_empty_structure(self, tmp_path):
        missing = tmp_path / "nonexistent.jsonl"
        result = summarize_existing_timeline(missing)
        assert result["file_found"] is False
        assert result["total_records"] == 0

    def test_summary_with_records_found(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        assert result["file_found"] is True
        assert result["total_records"] > 0

    def test_summary_match_ids_counted(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        assert result["match_ids_seen"] >= 1

    def test_summary_pregame_closing_pairs_counted(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        # 5 games each with pregame + closing
        assert result["pregame_closing_pairs"] >= 5

    def test_summary_date_range_populated(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        assert result["date_range_start"] is not None
        assert result["date_range_end"] is not None

    def test_summary_ignores_malformed_lines(self, tmp_path):
        f = tmp_path / "tsl.jsonl"
        f.write_text('{"valid": true, "match_id": "g1", "fetched_at": "2026-05-01T00:00:00Z", "game_time": "2026-05-01T04:00:00Z", "markets": []}\nNOT JSON\n{"valid": true, "match_id": "g1", "fetched_at": "2026-05-01T03:50:00Z", "game_time": "2026-05-01T04:00:00Z", "markets": []}\n')
        result = summarize_existing_timeline(f)
        # Should not crash; 2 valid records processed
        assert result["total_records"] == 2

    def test_summary_market_counts_populated(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        assert "ML" in result["market_counts"]

    def test_summary_snapshot_type_counts_populated(self, sample_jsonl_file):
        result = summarize_existing_timeline(sample_jsonl_file)
        # Should have PREGAME and CLOSING counts
        type_counts = result["snapshot_type_counts"]
        assert len(type_counts) >= 1


# ── P8-D-2: no network call ───────────────────────────────────────────────────

class TestNoNetworkCall:
    def test_summarize_uses_only_local_file(self, sample_jsonl_file, monkeypatch):
        """Ensure no socket usage — monkeypatch socket to block all connections."""
        import socket as _socket

        def _block(*a, **kw):
            raise RuntimeError("[TestNoNetworkCall] Network access is forbidden in dry-run tests.")

        monkeypatch.setattr(_socket, "socket", _block)
        # Should succeed even with socket blocked
        result = summarize_existing_timeline(sample_jsonl_file)
        assert result["total_records"] > 0

    def test_build_manifest_uses_no_network(self, sample_jsonl_file, monkeypatch):
        import socket as _socket

        def _block(*a, **kw):
            raise RuntimeError("[TestNoNetworkCall] Network access is forbidden in dry-run tests.")

        monkeypatch.setattr(_socket, "socket", _block)
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["paper_only"] is True


# ── P8-D-3: no crawler modification ──────────────────────────────────────────

class TestNoCrawlerModification:
    def test_manifest_crawler_modified_false(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["crawler_modified"] is False

    def test_manifest_is_not_live_crawler(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["is_live_crawler"] is False

    def test_manifest_is_dry_run_plan(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["is_dry_run_plan"] is True


# ── P8-D-4: schedule includes pregame + closing ───────────────────────────────

class TestScheduleWindows:
    def test_schedule_has_pregame_window(self):
        types = [w["snapshot_type"] for w in SCHEDULE_WINDOWS]
        assert "pregame" in types

    def test_schedule_has_closing_window(self):
        types = [w["snapshot_type"] for w in SCHEDULE_WINDOWS]
        assert "closing" in types

    def test_schedule_closing_has_closing_window_note(self):
        closing_windows = [w for w in SCHEDULE_WINDOWS if w["snapshot_type"] == "closing"]
        assert len(closing_windows) >= 1

    def test_manifest_contains_schedule(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        schedule = manifest["snapshot_schedule"]
        assert any(w["snapshot_type"] == "pregame" for w in schedule)
        assert any(w["snapshot_type"] == "closing" for w in schedule)

    def test_pairing_rule_includes_closing_window_sec(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        pairing = manifest["pairing_rule"]
        assert pairing["closing_window_sec"] == 3600

    def test_ml_market_is_minimum_viable(self):
        ml = [m for m in TARGET_MARKETS if m["market_code"] == "ML"]
        assert len(ml) >= 1
        assert ml[0]["minimum_viable"] is True


# ── P8-D-5: thresholds >= P7 requirement ─────────────────────────────────────

class TestThresholds:
    def test_min_timestamp_coverage_at_least_95(self):
        assert MIN_TIMESTAMP_COVERAGE_PCT >= 95.0

    def test_min_pair_coverage_at_least_90(self):
        assert MIN_PAIR_COVERAGE_PCT >= 90.0

    def test_min_pairs_for_clv_at_least_200(self):
        assert MIN_PAIRS_FOR_CLV >= 200

    def test_manifest_thresholds_correct(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        thresholds = manifest["minimum_coverage_thresholds"]
        assert thresholds["timestamp_coverage_pct"] >= 95.0
        assert thresholds["pair_coverage_pct"] >= 90.0
        assert thresholds["minimum_pairs_for_clv"] >= 200


# ── P8-D-6: paper_only=true ───────────────────────────────────────────────────

class TestPaperOnly:
    def test_manifest_paper_only_true(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["paper_only"] is True

    def test_manifest_production_write_false(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert manifest["is_production_write"] is False

    def test_build_manifest_paper_only_false_raises(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        with pytest.raises(ForwardCollectionError, match="paper_only must be True"):
            build_collection_manifest(summary, paper_only=False)  # type: ignore

    def test_annotation_contains_paper_only(self, sample_jsonl_file):
        summary = summarize_existing_timeline(sample_jsonl_file)
        manifest = build_collection_manifest(summary, paper_only=True)
        assert "paper_only=true" in manifest["annotation"]
