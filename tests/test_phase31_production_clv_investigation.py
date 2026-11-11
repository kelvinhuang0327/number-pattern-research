"""
Phase 31 Tests — Production CLV Investigation (PAPER_ONLY)
===========================================================
10 tests covering:
  1. loads only COMPUTED CLV
  2. excludes PENDING / BLOCKED
  3. segment stats are computed correctly
  4. weak segment detection works
  5. promising segment detection works
  6. small sample segments are flagged TOO_SMALL
  7. investigation result is recorded to training memory
  8. report is generated
  9. no production CLV file is mutated
 10. no external LLM usage occurs
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.run_phase31_production_clv_investigation import (
    EXECUTION_MODE,
    INVESTIGATION_TYPE,
    LIVE_BET_SUBMITTED,
    MIN_RELIABLE_SEGMENT,
    PRODUCTION_MUTATION,
    RELIABILITY_MIXED,
    RELIABILITY_NEGATIVE,
    RELIABILITY_POSITIVE,
    RELIABILITY_TOO_SMALL,
    RESULT_COLLECT_MORE,
    RESULT_INVESTIGATE_WEAK,
    SOURCE_MARKER,
    _classify_reliability,
    compute_segment_stats,
    determine_investigation_result,
    identify_promising_segments,
    identify_weak_segments,
    load_computed_clv_records,
    record_clv_investigation,
    run_investigation,
    write_investigation_report,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _computed(clv: float, idx: int = 0, **extra) -> dict:
    base = {
        "prediction_id": f"pred_{idx:04d}",
        "clv_status": "COMPUTED",
        "clv_value": clv,
        "canonical_match_id": f"baseball:mlb:2026:A{idx}:B{idx}",
        "selection": "home" if idx % 2 == 0 else "away",
        "closing_odds_source": "tsl_closing",
        "closing_lookup_method": "odds_snapshot_ref_game_id",
        "expected_value": 0.05 if idx % 2 == 0 else -0.05,
        "implied_probability_at_prediction": 0.55,
        "market_odds_at_prediction": -122,
        "market_type": "ML",
        "source_model": "mlb_ml_elo_stub_v1.1.0",
        "execution_mode": "RESEARCH_ONLY",
    }
    base.update(extra)
    return base


def _pending(idx: int = 99) -> dict:
    return {
        "prediction_id": f"pend_{idx:04d}",
        "clv_status": "PENDING_CLOSING",
        "clv_value": None,
        "canonical_match_id": f"baseball:mlb:2026:P{idx}:Q{idx}",
        "selection": "home",
    }


def _blocked(idx: int = 98) -> dict:
    return {
        "prediction_id": f"blok_{idx:04d}",
        "clv_status": "BLOCKED",
        "clv_value": 0.05,
        "canonical_match_id": f"baseball:mlb:2026:B{idx}:C{idx}",
        "selection": "home",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — Loads only COMPUTED CLV
# ═══════════════════════════════════════════════════════════════════════════

def test_loads_only_computed_clv():
    """load_computed_clv_records() returns only COMPUTED rows with valid clv_value."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "clv_validation_records_6u_2026-04-30.jsonl"
        _write_jsonl(path, [
            _computed(0.04, 0),
            _computed(-0.03, 1),
        ])

        rows = load_computed_clv_records(path)

    assert len(rows) == 2
    assert all(r["clv_status"] == "COMPUTED" for r in rows)
    assert all(isinstance(r["clv_value"], float) for r in rows)


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — Excludes PENDING / BLOCKED
# ═══════════════════════════════════════════════════════════════════════════

def test_excludes_pending_and_blocked():
    """
    PENDING_CLOSING and BLOCKED rows must be dropped.
    A COMPUTED row with clv_value=None must also be dropped.
    """
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "clv_validation_records_6u_2026-04-30.jsonl"
        _write_jsonl(path, [
            _computed(0.04, 0),
            _pending(idx=10),
            _blocked(idx=11),
            # COMPUTED but None value
            {
                "prediction_id": "bad_null",
                "clv_status": "COMPUTED",
                "clv_value": None,
            },
        ])

        rows = load_computed_clv_records(path)

    assert len(rows) == 1
    assert rows[0]["clv_value"] == pytest.approx(0.04)


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — Segment stats are computed correctly
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_segment_stats_correct():
    """compute_segment_stats() must produce correct descriptive statistics."""
    values = [0.10, -0.05, 0.0, 0.08, -0.02]
    stats = compute_segment_stats(values)

    assert stats["count"] == 5
    assert stats["positive_count"] == 2       # 0.10, 0.08
    assert stats["negative_count"] == 2       # -0.05, -0.02
    assert stats["flat_count"] == 1           # 0.0
    assert stats["positive_rate"] == pytest.approx(2 / 5)
    assert stats["negative_rate"] == pytest.approx(2 / 5)
    assert stats["mean_clv"] == pytest.approx(0.022, abs=1e-5)
    assert stats["min_clv"] == pytest.approx(-0.05)
    assert stats["max_clv"] == pytest.approx(0.10)


def test_compute_segment_stats_empty():
    """Empty list must return zero-filled stats with TOO_SMALL flag."""
    stats = compute_segment_stats([])
    assert stats["count"] == 0
    assert stats["mean_clv"] is None
    assert stats["reliability_flag"] == RELIABILITY_TOO_SMALL


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — Weak segment detection
# ═══════════════════════════════════════════════════════════════════════════

def test_weak_segment_detection():
    """
    identify_weak_segments() must return segments where count >= 3 and
    positive_rate < 0.40 OR mean_clv < -0.005.
    """
    # Craft a segment dict: one weak (low positive rate), one not-weak
    all_segs: dict = {
        "by_test_dim": {
            "weak_seg": compute_segment_stats([-0.05, -0.04, -0.03, 0.01]),    # pos_rate=0.25
            "ok_seg":   compute_segment_stats([0.05, 0.04, 0.03, -0.01]),     # pos_rate=0.75
        }
    }
    weak = identify_weak_segments(all_segs)
    assert len(weak) == 1
    assert weak[0]["segment"] == "weak_seg"
    assert weak[0]["observation_only"] is True
    assert weak[0]["patch_evidence"] is False


def test_weak_segment_by_mean_clv():
    """Segment with mean_clv < -0.005 must be detected as weak even if pos_rate is moderate."""
    all_segs: dict = {
        "by_test_dim": {
            # mean = (-0.02-0.01-0.02)/3 = -0.0167 < -0.005, pos_rate = 0/3 = 0.0
            "weak_mean_seg": compute_segment_stats([-0.02, -0.01, -0.02]),
        }
    }
    weak = identify_weak_segments(all_segs)
    assert any(w["segment"] == "weak_mean_seg" for w in weak)


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — Promising segment detection
# ═══════════════════════════════════════════════════════════════════════════

def test_promising_segment_detection():
    """
    identify_promising_segments() must return segments where count >= 3 and
    positive_rate >= 0.60 OR mean_clv > +0.005.
    """
    all_segs: dict = {
        "by_test_dim": {
            "promising_seg": compute_segment_stats([0.05, 0.04, 0.03, -0.01]),  # pos_rate=0.75
            "flat_seg":      compute_segment_stats([0.01, -0.01, 0.0, 0.0]),    # pos_rate=0.25
        }
    }
    promising = identify_promising_segments(all_segs)
    assert len(promising) == 1
    assert promising[0]["segment"] == "promising_seg"
    assert promising[0]["observation_only"] is True
    assert promising[0]["patch_evidence"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — Small-sample segments flagged TOO_SMALL
# ═══════════════════════════════════════════════════════════════════════════

def test_small_sample_flagged_too_small():
    """
    Segments with count < MIN_RELIABLE_SEGMENT (3) must receive
    RELIABILITY_TOO_SMALL flag and must NOT appear in weak/promising lists.
    """
    # count=2 → TOO_SMALL
    stats = compute_segment_stats([0.05, -0.05])
    assert stats["reliability_flag"] == RELIABILITY_TOO_SMALL

    # TOO_SMALL segments should be skipped by identify_weak/promising
    all_segs: dict = {
        "by_test_dim": {
            "tiny_seg": stats,
        }
    }
    assert identify_weak_segments(all_segs) == []
    assert identify_promising_segments(all_segs) == []


def test_classify_reliability_all_cases():
    """Verify all four reliability classification paths."""
    assert _classify_reliability(2, 0.10, -0.10) == RELIABILITY_TOO_SMALL   # n < 3
    assert _classify_reliability(5, 0.25, -0.02) == RELIABILITY_NEGATIVE    # pos_rate < 0.40
    assert _classify_reliability(5, 0.70, 0.02)  == RELIABILITY_POSITIVE    # pos_rate >= 0.60
    assert _classify_reliability(5, 0.50, 0.0)   == RELIABILITY_MIXED       # neither extreme


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — Investigation result is recorded to training memory
# ═══════════════════════════════════════════════════════════════════════════

def test_investigation_recorded_to_training_memory(tmp_path):
    """
    record_clv_investigation() must write an entry to the ``clv_investigations``
    list in training_memory.json with source="production/paper".
    """
    memory_path = tmp_path / "training_memory.json"

    record_clv_investigation(
        task_id="phase31_test_tm",
        total_computed=14,
        weak_segments=[{"dimension": "by_test", "segment": "weak_seg", "observation_only": True}],
        promising_segments=[],
        recommended_next_action=RESULT_COLLECT_MORE,
        memory_path=memory_path,
    )

    assert memory_path.exists()
    mem = json.loads(memory_path.read_text(encoding="utf-8"))
    invs = mem.get("clv_investigations", [])
    assert len(invs) == 1

    entry = invs[0]
    assert entry["task_id"] == "phase31_test_tm"
    assert entry["source"] == "production/paper"
    assert entry["investigation_type"] == INVESTIGATION_TYPE
    assert entry["computed_clv_count"] == 14
    assert entry["production_mutation"] is False
    assert entry["live_bet_submitted"] is False
    assert entry["recommended_next_action"] == RESULT_COLLECT_MORE


def test_record_appends_multiple_entries(tmp_path):
    """Multiple calls must append entries without overwriting previous ones."""
    memory_path = tmp_path / "training_memory.json"

    for i in range(3):
        record_clv_investigation(
            task_id=f"phase31_multi_{i}",
            total_computed=14 + i,
            weak_segments=[],
            promising_segments=[],
            recommended_next_action=RESULT_COLLECT_MORE,
            memory_path=memory_path,
        )

    mem = json.loads(memory_path.read_text(encoding="utf-8"))
    assert len(mem["clv_investigations"]) == 3
    assert mem["clv_investigations"][-1]["task_id"] == "phase31_multi_2"


# ═══════════════════════════════════════════════════════════════════════════
# Test 8 — Report is generated
# ═══════════════════════════════════════════════════════════════════════════

def test_write_investigation_report_content(tmp_path):
    """
    write_investigation_report() must create a non-empty Markdown file containing
    expected safety markers and key result fields.
    """
    records = [_computed(float(v) / 100, i) for i, v in
               enumerate([5, -4, 3, -2, 1, -1, 2, -3, 0, 4, -5, 2, -1, 3])]
    from scripts.run_phase31_production_clv_investigation import compute_all_segments
    all_vals = [r["clv_value"] for r in records]
    overall = compute_segment_stats(all_vals)
    segs = compute_all_segments(records)
    weak = identify_weak_segments(segs)
    promising = identify_promising_segments(segs)
    result = determine_investigation_result(weak, promising, len(records))

    report_path = write_investigation_report(
        task_id="phase31_test_report",
        total_computed=len(records),
        overall_stats=overall,
        all_segments=segs,
        weak_segments=weak,
        promising_segments=promising,
        investigation_result=result,
        docs_dir=tmp_path,
    )

    assert report_path.exists(), "Report file was not created"
    text = report_path.read_text(encoding="utf-8")

    assert len(text) > 500
    assert "PAPER_ONLY" in text
    assert "production/paper" in text
    assert "production_mutation=False" in text
    assert "live_bet_submitted=False" in text
    assert "phase31_test_report" in text
    assert result in text                  # investigation result present
    assert "observation-only" in text.lower() or "observation only" in text.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test 9 — No production CLV file is mutated
# ═══════════════════════════════════════════════════════════════════════════

def test_no_production_clv_file_mutated(tmp_path):
    """
    run_investigation(apply=True) must NOT modify the source CLV JSONL file.
    """
    clv_path = tmp_path / "clv_validation_records_6u_2026-04-30.jsonl"
    rows = [_computed(float(i) / 20 - 0.3, i) for i in range(8)]
    _write_jsonl(clv_path, rows)

    original = clv_path.read_text(encoding="utf-8")

    memory_path = tmp_path / "training_memory.json"
    docs_dir = tmp_path / "docs"
    run_investigation(
        clv_path=clv_path,
        docs_dir=docs_dir,
        memory_path=memory_path,
        apply=True,
        task_id="phase31_nomut_test",
    )

    after = clv_path.read_text(encoding="utf-8")
    assert original == after, "CLV source file was mutated — production_mutation violation"


# ═══════════════════════════════════════════════════════════════════════════
# Test 10 — No external LLM usage occurs
# ═══════════════════════════════════════════════════════════════════════════

def test_no_external_llm_usage():
    """
    run_investigation() must always return no_llm_used=True.
    The Phase 31 investigation is fully deterministic — no AI provider called.
    """
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "clv_validation_records_6u_2026-04-30.jsonl"
        rows = [_computed(float(i) / 10 - 0.5, i) for i in range(8)]
        _write_jsonl(path, rows)

        result = run_investigation(clv_path=path, apply=False)

    assert result["no_llm_used"] is True
    assert result["execution_mode"] == EXECUTION_MODE
    assert result["source"] == SOURCE_MARKER
    assert result["production_mutation"] is PRODUCTION_MUTATION
    assert result["live_bet_submitted"] is LIVE_BET_SUBMITTED
