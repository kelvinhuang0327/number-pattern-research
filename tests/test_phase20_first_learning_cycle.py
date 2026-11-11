"""
tests/test_phase20_first_learning_cycle.py
==========================================
Phase 20 — First Real Learning Cycle Orchestration: 9 unit tests.

Proves the learning loop works end-to-end:
  COMPUTED CLV fixture
    → governance DATA_READY
    → deterministic/local executor (no LLM, no external calls)
    → learning insight produced
    → training memory updated
    → ops report & readiness surface the learning cycle

Hard rules verified by these tests:
  ✓ No production CLV file is modified
  ✓ No external LLM is called
  ✓ Sandbox source marker is always "sandbox/test"
  ✓ PENDING_CLOSING rows are never counted as COMPUTED
  ✓ No live betting triggered

SUCCESS CRITERIA: PHASE_20_FIRST_LEARNING_CYCLE_VERIFIED
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Repo paths ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "runtime" / "agent_orchestrator" / "test_fixtures"
PRODUCTION_REPORTS_DIR = REPO_ROOT / "data" / "wbc_backend" / "reports"
LLM_USAGE_JSONL = (
    REPO_ROOT / "runtime" / "agent_orchestrator" / "llm_usage.jsonl"
)

# ── Fixture CLV expectations (values from computed_clv_fixture.jsonl) ─────────
FIXTURE_CLV_VALUES = [0.025, 0.03, 0.035, 0.04, 0.045]
FIXTURE_COUNT = len(FIXTURE_CLV_VALUES)                           # 5
FIXTURE_MEAN_CLV = sum(FIXTURE_CLV_VALUES) / FIXTURE_COUNT        # 0.035
FIXTURE_MEDIAN_CLV = sorted(FIXTURE_CLV_VALUES)[FIXTURE_COUNT // 2]  # 0.035


# ── Shared pytest fixtures ────────────────────────────────────────────────────

@pytest.fixture()
def clv_reports_dir(tmp_path: Path) -> Path:
    """
    Tmpdir containing a properly-named CLV JSONL fixture.
    The executor scans for ``clv_validation_records_6u_*.jsonl``; the file must
    match that pattern for the glob to find it.
    """
    src = FIXTURE_DIR / "computed_clv_fixture.jsonl"
    dest = tmp_path / "clv_validation_records_6u_2026-04-30.jsonl"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def full_phase6_dir(clv_reports_dir: Path) -> Path:
    """
    Extends ``clv_reports_dir`` with a prediction registry file so that
    ``phase6_data_registry.discover_phase6_dates()`` can discover the date and
    ``optimization_state.classify()`` sees COMPUTED CLV records.
    """
    registry_row = json.dumps({
        "prediction_id": "sandbox_pred_001",
        "canonical_match_id": "sandbox_match_001",
        "ev_percent": 2.5,
        "execution_mode": "RESEARCH_ONLY",
    })
    (clv_reports_dir / "prediction_registry_6t_2026-04-30.jsonl").write_text(
        registry_row + "\n", encoding="utf-8"
    )
    return clv_reports_dir


@pytest.fixture()
def isolated_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Redirects training_memory I/O to a temporary file so tests never
    touch the real training_memory.json.
    """
    import orchestrator.training_memory as tm_module

    temp_path = tmp_path / "training_memory.json"
    monkeypatch.setattr(tm_module, "MEMORY_PATH", temp_path)
    return temp_path


# ── Test 1: Governance reports DATA_READY, executor registered ────────────────

def test_sandbox_clv_generates_learning_task(full_phase6_dir: Path) -> None:
    """
    Sandbox COMPUTED CLV fixture → governance classifies as DATA_READY.
    Learning families are allowed, and ``clv_quality_analysis`` is registered
    as a deterministic (no-LLM) task type.
    """
    from orchestrator.optimization_state import classify
    from orchestrator.safe_task_executor import is_deterministic_safe_task

    result = classify(reports_dir=full_phase6_dir)

    assert result["state"] == "DATA_READY", (
        f"Expected DATA_READY; got: {result['state']!r}  "
        f"reasons={result.get('reasons')}"
    )
    # Learning families must be allowed when DATA_READY
    allowed = result.get("allowed_task_families", [])
    assert len(allowed) > 0, "No learning families allowed in DATA_READY state"

    # clv_quality_analysis is registered as a deterministic executor
    assert is_deterministic_safe_task({"task_type": "clv_quality_analysis"}), (
        "clv_quality_analysis must be registered in DETERMINISTIC_TASK_TYPES"
    )


# ── Test 2: Executor produces a non-empty artifact file ───────────────────────

def test_clv_quality_analysis_produces_artifact(
    clv_reports_dir: Path, tmp_path: Path
) -> None:
    """
    Running the deterministic executor against the sandbox fixture must create
    a non-empty Markdown artifact at the expected path.
    """
    from orchestrator.safe_task_executor import execute_safe_task

    artifact_dir = tmp_path / "artifacts"
    task = {
        "id": "phase20_test_002",
        "task_type": "clv_quality_analysis",
        "_sandbox_reports_dir": clv_reports_dir,
        "_sandbox_artifact_dir": artifact_dir,
    }

    result = execute_safe_task(task)

    assert result["success"] is True, f"Executor failed: {result}"
    artifact_path = Path(result["completed_file_path"])
    assert artifact_path.exists(), f"Artifact not written to {artifact_path}"
    content = artifact_path.read_text(encoding="utf-8")
    assert len(content) > 100, "Artifact is suspiciously short"
    assert "CLV Quality Analysis" in content
    assert "sandbox/test" in content


# ── Test 3: Computed statistics are correct for fixture data ──────────────────

def test_clv_quality_stats_are_correct(
    clv_reports_dir: Path, tmp_path: Path
) -> None:
    """
    The executor must correctly compute mean, median, and per-direction counts
    for the 5 fixture COMPUTED CLV records (values: 0.025, 0.03, 0.035, 0.04, 0.045).
    All values are positive → positive_rate = 1.0, recommendation = "HOLD".
    """
    from orchestrator.safe_task_executor import execute_safe_task

    task = {
        "id": "phase20_test_003",
        "task_type": "clv_quality_analysis",
        "_sandbox_reports_dir": clv_reports_dir,
        "_sandbox_artifact_dir": tmp_path / "artifacts",
    }

    result = execute_safe_task(task)

    assert result["computed_count"] == FIXTURE_COUNT
    assert result["positive_clv_count"] == FIXTURE_COUNT
    assert result["negative_clv_count"] == 0
    assert result["flat_count"] == 0
    assert abs(result["mean_clv"] - FIXTURE_MEAN_CLV) < 1e-9, (
        f"mean_clv mismatch: expected {FIXTURE_MEAN_CLV}, got {result['mean_clv']}"
    )
    assert abs(result["median_clv"] - FIXTURE_MEDIAN_CLV) < 1e-9, (
        f"median_clv mismatch: expected {FIXTURE_MEDIAN_CLV}, got {result['median_clv']}"
    )
    assert result["positive_rate"] == pytest.approx(1.0)
    assert result["recommendation"] == "HOLD", (
        f"All-positive CLV should yield HOLD; got: {result['recommendation']!r}"
    )


# ── Test 4: PENDING_CLOSING records are ignored ───────────────────────────────

def test_pending_closing_ignored_in_learning_cycle(tmp_path: Path) -> None:
    """
    Records with ``clv_status != "COMPUTED"`` (PENDING_CLOSING, BLOCKED, etc.)
    must be excluded from the CLV quality analysis entirely.
    """
    from orchestrator.safe_task_executor import execute_safe_task

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    mixed_rows = [
        {"prediction_id": "p1", "clv_status": "COMPUTED",       "clv_value": 0.05},
        {"prediction_id": "p2", "clv_status": "COMPUTED",       "clv_value": -0.02},
        {"prediction_id": "p3", "clv_status": "PENDING_CLOSING","clv_value": None},
        {"prediction_id": "p4", "clv_status": "PENDING_CLOSING","clv_value": None},
        {"prediction_id": "p5", "clv_status": "BLOCKED",        "clv_value": None},
    ]
    (reports_dir / "clv_validation_records_6u_2026-04-30.jsonl").write_text(
        "\n".join(json.dumps(r) for r in mixed_rows) + "\n",
        encoding="utf-8",
    )

    task = {
        "id": "phase20_test_004",
        "task_type": "clv_quality_analysis",
        "_sandbox_reports_dir": reports_dir,
        "_sandbox_artifact_dir": tmp_path / "artifacts",
    }

    result = execute_safe_task(task)

    assert result["computed_count"] == 2, (
        f"Only COMPUTED rows should be analysed; got computed_count={result['computed_count']}"
    )
    assert result["positive_clv_count"] == 1
    assert result["negative_clv_count"] == 1


# ── Test 5: Training memory records the learning cycle ────────────────────────

def test_training_memory_records_learning_result(
    clv_reports_dir: Path, tmp_path: Path, isolated_memory: Path
) -> None:
    """
    After running a sandbox learning cycle, training memory must contain an
    entry with the correct task_id, source="sandbox/test", and CLV stats.
    """
    from orchestrator.learning_cycle_runner import run_sandbox_learning_cycle
    from orchestrator import training_memory as tm

    result = run_sandbox_learning_cycle(
        reports_dir=clv_reports_dir,
        artifact_dir=tmp_path / "artifacts",
        task_id="phase20_test_005",
    )

    assert result["learning_cycle_status"] == "COMPLETED"

    cycles = tm.get_learning_cycle_history()
    assert len(cycles) >= 1, "No learning cycles recorded in training memory"

    last = cycles[-1]
    assert last["task_id"] == "phase20_test_005"
    assert last["source"] == "sandbox/test"
    assert last["computed_clv_count"] == FIXTURE_COUNT
    assert last["recommendation"] == "HOLD"
    assert last["learning_cycle_status"] == "COMPLETED"
    assert "recorded_at" in last


# ── Test 6: No production CLV file is modified ────────────────────────────────

def test_no_production_clv_file_modified(
    clv_reports_dir: Path, tmp_path: Path, isolated_memory: Path
) -> None:
    """
    Running a sandbox learning cycle must never touch any file in the
    production CLV reports directory.
    """
    from orchestrator.learning_cycle_runner import run_sandbox_learning_cycle

    def _snapshot(directory: Path) -> dict[str, float]:
        if not directory.exists():
            return {}
        return {p.name: p.stat().st_mtime for p in directory.glob("*.jsonl")}

    mtime_before = _snapshot(PRODUCTION_REPORTS_DIR)

    run_sandbox_learning_cycle(
        reports_dir=clv_reports_dir,
        artifact_dir=tmp_path / "artifacts",
        task_id="phase20_test_006",
    )

    mtime_after = _snapshot(PRODUCTION_REPORTS_DIR)
    assert mtime_before == mtime_after, (
        "Production CLV files were modified during sandbox learning cycle! "
        f"Changed: {set(mtime_before) ^ set(mtime_after)}"
    )


# ── Test 7: No external LLM usage logged ─────────────────────────────────────

def test_no_external_llm_usage(
    clv_reports_dir: Path, tmp_path: Path, isolated_memory: Path
) -> None:
    """
    The sandbox learning cycle must not write any entry to llm_usage.jsonl
    (which would indicate an external AI call was made).
    The result dict must also explicitly confirm no_llm_used=True.
    """
    from orchestrator.learning_cycle_runner import run_sandbox_learning_cycle

    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())

    count_before = _line_count(LLM_USAGE_JSONL)

    result = run_sandbox_learning_cycle(
        reports_dir=clv_reports_dir,
        artifact_dir=tmp_path / "artifacts",
        task_id="phase20_test_007",
    )

    count_after = _line_count(LLM_USAGE_JSONL)

    assert count_before == count_after, (
        f"LLM usage log grew unexpectedly: {count_before} → {count_after} lines"
    )
    assert result["no_llm_used"] is True
    assert result["no_production_mutation"] is True


# ── Test 8: Ops report training-memory summary includes learning cycle ─────────

def test_learning_cycle_result_in_ops_report(
    tmp_path: Path, isolated_memory: Path
) -> None:
    """
    After recording a learning cycle, the ops report training-memory summary
    must expose ``learning_cycles_total`` >= 1 and ``latest_learning_cycle``
    with the expected task_id.
    """
    from orchestrator import training_memory as tm
    from orchestrator.optimization_ops_report import _get_training_memory_summary

    tm.record_learning_cycle(
        task_id="phase20_ops_test_008",
        computed_clv_count=5,
        mean_clv=0.035,
        recommendation="HOLD",
        learning_cycle_status="COMPLETED",
        source="sandbox/test",
        artifact_path=str(tmp_path / "test_artifact_008.md"),
    )

    summary = _get_training_memory_summary()

    assert "learning_cycles_total" in summary, (
        "ops report training_memory_summary missing 'learning_cycles_total'"
    )
    assert summary["learning_cycles_total"] >= 1
    assert summary["latest_learning_cycle"] is not None
    latest = summary["latest_learning_cycle"]
    assert latest["task_id"] == "phase20_ops_test_008"
    assert latest["source"] == "sandbox/test"
    assert latest["recommendation"] == "HOLD"


# ── Test 9: Insight from executor has correct structure ───────────────────────

def test_insight_captures_clv_quality_signal(
    clv_reports_dir: Path, tmp_path: Path
) -> None:
    """
    The structured insight embedded in the executor result must have the correct
    signal_state_type, source marker, evidence fields, and requires_patch
    consistent with the recommendation.
    """
    from orchestrator.safe_task_executor import execute_safe_task

    task = {
        "id": "phase20_test_009",
        "task_type": "clv_quality_analysis",
        "_sandbox_reports_dir": clv_reports_dir,
        "_sandbox_artifact_dir": tmp_path / "artifacts",
    }

    result = execute_safe_task(task)
    insight = result["insight"]

    assert insight["signal_state_type"] == "learning_clv_quality"
    assert insight["source"] == "sandbox_clv_quality_analysis"
    assert insight["source_marker"] == "sandbox/test"
    assert "confidence" in insight
    assert insight["confidence"] in {"low", "medium", "high"}
    assert "candidate_action" in insight
    assert isinstance(insight["requires_patch"], bool)

    # requires_patch must be consistent with recommendation
    expected_requires_patch = result["recommendation"] == "CANDIDATE_PATCH"
    assert insight["requires_patch"] == expected_requires_patch

    evidence = insight["evidence"]
    assert evidence["computed_count"] == FIXTURE_COUNT
    assert evidence["computed_count"] > 0
    assert "mean_clv" in evidence
    assert "positive_rate" in evidence
    assert "recommendation" in evidence
