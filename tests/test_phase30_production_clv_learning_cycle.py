"""
Phase 30 Tests — Production CLV Learning Cycle (PAPER_ONLY)
============================================================
8 tests verifying the paper-only production learning cycle:

  1. COMPUTED records are loaded; PENDING/BLOCKED excluded
  2. CLV analysis excludes PENDING/BLOCKED even when mixed in fixture
  3. Learning cycle records source="production/paper"
  4. No production model file is modified
  5. No external LLM usage is created
  6. Patch gate uses production threshold (≥50)
  7. 14 records cannot create a production patch
  8. Task artifact is generated with expected content
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ── Unit under test ────────────────────────────────────────────────────────
from scripts.run_phase30_production_clv_learning_cycle import (
    EXECUTION_MODE,
    LIVE_BET_SUBMITTED,
    PRODUCTION_MUTATION,
    PRODUCTION_PATCH_THRESHOLD,
    SOURCE_MARKER,
    analyze_clv_quality,
    evaluate_production_patch_gate,
    get_recommendation,
    load_computed_clv_records,
    record_production_cycle,
    run_cycle,
    write_task_artifact,
)
from orchestrator.learning_patch_gate import (
    GATE_ALLOW_PATCH,
    GATE_HOLD,
    GATE_INVESTIGATE_ONLY,
    GATE_REJECT,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _write_clv_jsonl(path: Path, rows: list[dict]) -> None:
    """Write a list of CLV record dicts as JSONL."""
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


def _make_computed_row(clv_value: float, idx: int = 0) -> dict:
    return {
        "prediction_id": f"pred_{idx:04d}",
        "clv_status": "COMPUTED",
        "clv_value": clv_value,
        "canonical_match_id": f"baseball:mlb:2026:team_a:team_b_{idx}",
        "selection": "home",
        "closing_lookup_method": "odds_snapshot_ref_game_id",
    }


def _make_pending_row(idx: int = 99) -> dict:
    return {
        "prediction_id": f"pend_{idx:04d}",
        "clv_status": "PENDING_CLOSING",
        "clv_value": None,
        "canonical_match_id": f"baseball:mlb:2026:pend_a:pend_b_{idx}",
        "selection": "home",
    }


def _make_blocked_row(idx: int = 98) -> dict:
    return {
        "prediction_id": f"blok_{idx:04d}",
        "clv_status": "BLOCKED",
        "clv_value": 0.05,
        "canonical_match_id": f"baseball:mlb:2026:blok_a:blok_b_{idx}",
        "selection": "home",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — COMPUTED records are loaded; PENDING/BLOCKED excluded
# ═══════════════════════════════════════════════════════════════════════════

def test_load_computed_clv_records_excludes_non_computed():
    """
    load_computed_clv_records() must return only COMPUTED records with
    non-None clv_value. PENDING_CLOSING and BLOCKED rows must be dropped.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "clv_validation_records_6u_2026-04-30.jsonl"
        rows = [
            _make_computed_row(0.05, idx=0),
            _make_computed_row(-0.03, idx=1),
            _make_pending_row(idx=2),
            _make_blocked_row(idx=3),
            # COMPUTED with None clv_value — also excluded
            {
                "prediction_id": "bad_000",
                "clv_status": "COMPUTED",
                "clv_value": None,
            },
        ]
        _write_clv_jsonl(path, rows)

        loaded = load_computed_clv_records(path)

    assert len(loaded) == 2
    assert all(r["clv_status"] == "COMPUTED" for r in loaded)
    clv_vals = {r["clv_value"] for r in loaded}
    assert 0.05 in clv_vals
    assert -0.03 in clv_vals


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — CLV analysis excludes PENDING/BLOCKED (integration via run_cycle)
# ═══════════════════════════════════════════════════════════════════════════

def test_run_cycle_dry_run_excludes_pending_blocked():
    """
    run_cycle(apply=False) must only count COMPUTED records — PENDING_CLOSING
    and BLOCKED rows must not inflate computed_count.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "clv_validation_records_6u_2026-05-01.jsonl"
        rows = [
            _make_computed_row(0.04, idx=0),
            _make_computed_row(0.03, idx=1),
            _make_pending_row(idx=10),
            _make_blocked_row(idx=11),
        ]
        _write_clv_jsonl(path, rows)

        result = run_cycle(clv_path=path, apply=False)

    assert result["computed_count"] == 2
    assert result["apply"] is False
    assert result["learning_cycle_status"] == "DRY_RUN"
    assert result["production_mutation"] is False
    assert result["live_bet_submitted"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — Learning cycle records source="production/paper"
# ═══════════════════════════════════════════════════════════════════════════

def test_record_production_cycle_uses_production_paper_source(
    tmp_path, monkeypatch
):
    """
    record_production_cycle() must call training_memory.record_learning_cycle
    with source="production/paper" and record_gate_decision with the same source.
    """
    recorded_calls: list[dict] = []

    # Monkeypatch training_memory functions to capture calls
    import orchestrator.training_memory as tm

    def _fake_record_learning_cycle(**kwargs):  # type: ignore[override]
        recorded_calls.append({"type": "learning_cycle", **kwargs})
        return {}

    def _fake_record_gate_decision(**kwargs):  # type: ignore[override]
        recorded_calls.append({"type": "gate_decision", **kwargs})
        return {}

    monkeypatch.setattr(tm, "record_learning_cycle", _fake_record_learning_cycle)
    monkeypatch.setattr(tm, "record_gate_decision", _fake_record_gate_decision)

    stats = analyze_clv_quality([_make_computed_row(0.02, i) for i in range(5)])
    recommendation = get_recommendation(stats)
    gate_result = evaluate_production_patch_gate(stats, recommendation)

    record_production_cycle(
        task_id="phase30_test_source",
        stats=stats,
        recommendation=recommendation,
        gate_result=gate_result,
        artifact_path="/fake/path/artifact.md",
    )

    lc_calls = [c for c in recorded_calls if c["type"] == "learning_cycle"]
    gd_calls = [c for c in recorded_calls if c["type"] == "gate_decision"]

    assert len(lc_calls) == 1
    assert lc_calls[0]["source"] == "production/paper"

    assert len(gd_calls) == 1
    assert gd_calls[0]["source"] == "production/paper"


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — No production model file is modified
# ═══════════════════════════════════════════════════════════════════════════

def test_run_cycle_apply_does_not_modify_clv_source_file(tmp_path, monkeypatch):
    """
    run_cycle(apply=True) must not mutate the source CLV JSONL file.
    The file contents before and after must be identical.
    """
    import orchestrator.training_memory as tm

    # Suppress actual disk writes to training_memory
    monkeypatch.setattr(tm, "record_learning_cycle", lambda **kw: {})
    monkeypatch.setattr(tm, "record_gate_decision", lambda **kw: {})

    clv_path = tmp_path / "clv_validation_records_6u_2026-04-30.jsonl"
    rows = [_make_computed_row(0.03, i) for i in range(6)]
    _write_clv_jsonl(clv_path, rows)

    original_text = clv_path.read_text(encoding="utf-8")

    task_dir = tmp_path / "tasks"
    run_cycle(clv_path=clv_path, task_dir=task_dir, apply=True, task_id="phase30_test_nomut")

    after_text = clv_path.read_text(encoding="utf-8")
    assert original_text == after_text, "CLV source file was mutated — production_mutation violation"


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — No external LLM usage is created
# ═══════════════════════════════════════════════════════════════════════════

def test_run_cycle_no_llm_flag():
    """
    run_cycle() must always return no_llm_used=True.
    The PAPER_ONLY cycle is fully deterministic — no AI provider is called.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "clv_validation_records_6u_2026-05-01.jsonl"
        rows = [_make_computed_row(0.02, i) for i in range(8)]
        _write_clv_jsonl(path, rows)

        result = run_cycle(clv_path=path, apply=False)

    assert result["no_llm_used"] is True
    assert result["execution_mode"] == EXECUTION_MODE
    assert result["source"] == SOURCE_MARKER


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — Patch gate uses production threshold (≥50)
# ═══════════════════════════════════════════════════════════════════════════

def test_patch_gate_production_threshold_is_50():
    """
    PRODUCTION_PATCH_THRESHOLD must equal 50, matching
    learning_patch_gate._ALLOW_COUNT_PRODUCTION.
    For a CANDIDATE_PATCH recommendation with <50 records, the gate must
    return REJECT_INSUFFICIENT_EVIDENCE (not ALLOW_PATCH_CANDIDATE).
    """
    assert PRODUCTION_PATCH_THRESHOLD == 50

    # Simulate 49 records with strong CANDIDATE_PATCH signal (clearly negative mean)
    stats = {
        "computed_count": 49,
        "mean_clv": -0.05,       # clearly negative → CANDIDATE_PATCH
        "median_clv": -0.04,
        "clv_variance": 0.001,
        "positive_rate": 0.10,   # very low → CANDIDATE_PATCH
        "positive_clv_count": 5,
        "negative_clv_count": 44,
        "flat_clv_count": 0,
    }
    gate = evaluate_production_patch_gate(stats, "CANDIDATE_PATCH")
    assert gate["gate_decision"] == GATE_REJECT, (
        f"Expected REJECT for 49 production records, got {gate['gate_decision']}"
    )


def test_patch_gate_production_threshold_50_allows_with_strong_signal():
    """
    With exactly 50 records and a strong negative CANDIDATE_PATCH signal,
    the production gate must return ALLOW_PATCH_CANDIDATE.
    """
    stats = {
        "computed_count": 50,
        "mean_clv": -0.05,
        "median_clv": -0.04,
        "clv_variance": 0.001,
        "positive_rate": 0.10,
        "positive_clv_count": 5,
        "negative_clv_count": 45,
        "flat_clv_count": 0,
    }
    gate = evaluate_production_patch_gate(stats, "CANDIDATE_PATCH")
    assert gate["gate_decision"] == GATE_ALLOW_PATCH, (
        f"Expected ALLOW_PATCH_CANDIDATE for 50 production records, got {gate['gate_decision']}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — 14 records cannot create a production patch
# ═══════════════════════════════════════════════════════════════════════════

def test_14_production_records_cannot_create_patch():
    """
    With exactly 14 COMPUTED CLV records matching the 2026-04-30 production
    data distribution, the patch gate must NOT return ALLOW_PATCH_CANDIDATE.

    The real production distribution:
      mean ≈ +0.0009  (slightly positive — INVESTIGATE recommendation)
    This yields INVESTIGATE_ONLY, never ALLOW_PATCH_CANDIDATE.

    Additionally verify: even if we force CANDIDATE_PATCH recommendation
    (negative mean scenario), 14 < 50 → REJECT.
    """
    # Real production statistics (from Phase 29 data)
    real_stats = {
        "computed_count": 14,
        "mean_clv": 0.000862,
        "median_clv": 0.0,
        "clv_variance": 0.00126075,
        "positive_rate": 0.4286,
        "positive_clv_count": 6,
        "negative_clv_count": 6,
        "flat_clv_count": 2,
    }
    real_recommendation = get_recommendation(real_stats)
    # With mean≈+0.0009, positive_rate≈0.43 → INVESTIGATE
    assert real_recommendation == "INVESTIGATE"

    gate = evaluate_production_patch_gate(real_stats, real_recommendation)
    assert gate["gate_decision"] != GATE_ALLOW_PATCH, (
        f"Production patch must NOT be allowed with only 14 records — got {gate['gate_decision']}"
    )
    assert gate["gate_decision"] == GATE_INVESTIGATE_ONLY

    # Even if we force CANDIDATE_PATCH (14 < 50 production threshold)
    gate_forced = evaluate_production_patch_gate(real_stats, "CANDIDATE_PATCH")
    assert gate_forced["gate_decision"] == GATE_REJECT


# ═══════════════════════════════════════════════════════════════════════════
# Test 8 — Task artifact is generated with expected content
# ═══════════════════════════════════════════════════════════════════════════

def test_write_task_artifact_content(tmp_path):
    """
    write_task_artifact() must produce a Markdown file that:
      - is non-empty
      - contains "PAPER_ONLY" execution mode
      - contains "production/paper" source marker
      - contains the task ID
      - contains the gate decision
      - references the production_mutation=False hard rule
    """
    stats = {
        "computed_count": 14,
        "positive_clv_count": 6,
        "negative_clv_count": 6,
        "flat_clv_count": 2,
        "mean_clv": 0.000862,
        "median_clv": 0.0,
        "clv_variance": 0.00126075,
        "positive_rate": 0.4286,
    }
    recommendation = "INVESTIGATE"
    gate_result = evaluate_production_patch_gate(stats, recommendation)

    task_id = "phase30_test_artifact_001"
    artifact_path = write_task_artifact(
        task_id=task_id,
        stats=stats,
        recommendation=recommendation,
        gate_result=gate_result,
        task_dir=tmp_path,
    )

    assert artifact_path.exists(), "Artifact file was not created"
    text = artifact_path.read_text(encoding="utf-8")

    assert len(text) > 200, "Artifact is suspiciously short"
    assert "PAPER_ONLY" in text
    assert "production/paper" in text
    assert task_id in text
    assert gate_result["gate_decision"] in text
    assert "production_mutation=False" in text
    assert "live_bet_submitted=False" in text
    assert "14" in text           # computed count
    assert "INVESTIGATE" in text  # recommendation
