"""Tests for the MLB paper evaluation runner (P143).

Covers:
  - CLI single-date evaluation against fixture data
  - CLI all-dates batch evaluation over multiple fixture date folders
  - Empty / missing paper row handling
  - Missing outcome handling
  - JSON-serializable output artifact
  - No provider / live odds / EV / CLV / Kelly fields required
  - Batch output schema: per_date + aggregate
  - discover_paper_dates helper
  - execute_batch_evaluation helper
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure repo root is on path for script imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.mlb_paper_evaluator import (
    discover_paper_dates,
    evaluate_paper_recommendations,
    execute_batch_evaluation,
    execute_evaluation,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_recommendations() -> list[dict]:
    return [
        {
            "game_id": "2026-05-11-LAA-CLE-824441",
            "model_prob_home": 0.62,
            "model_prob_away": 0.38,
            "tsl_market": "moneyline",
            "tsl_side": "home",
            "tsl_decimal_odds": 1.90,
            "stake_units_paper": 2.0,
            "gate_status": "PASS",
            "paper_only": True,
        },
        {
            "game_id": "2026-05-11-NYY-BOS-824442",
            "model_prob_home": 0.48,
            "model_prob_away": 0.52,
            "tsl_market": "moneyline",
            "tsl_side": "away",
            "tsl_decimal_odds": 1.80,
            "stake_units_paper": 0.0,
            "gate_status": "BLOCKED_SIMULATION_GATE",
            "paper_only": True,
        },
    ]


@pytest.fixture
def sample_outcomes() -> list[dict]:
    return [
        {
            "game_id": "mlb_2026_824441",
            "outcome_available": True,
            "actual_winner": "home",
        },
        {
            "game_id": "mlb_2026_824442",
            "outcome_available": True,
            "actual_winner": "away",
        },
    ]


@pytest.fixture
def paper_dir_fixture(tmp_path, sample_recommendations) -> Path:
    """Create a fixture PAPER date folder with two recommendation rows."""
    date_dir = tmp_path / "PAPER" / "2026-05-11"
    date_dir.mkdir(parents=True)
    for i, rec in enumerate(sample_recommendations):
        rec_file = date_dir / f"game_{i}.jsonl"
        rec_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    return tmp_path / "PAPER"


@pytest.fixture
def outcome_file_fixture(tmp_path, sample_outcomes) -> Path:
    """Create a fixture outcome JSONL file."""
    out_file = tmp_path / "outcomes.jsonl"
    lines = [json.dumps(o) for o in sample_outcomes]
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_file


# ─── Tests: discover_paper_dates ──────────────────────────────────────────────


def test_discover_paper_dates_returns_sorted_dates(tmp_path):
    """discover_paper_dates should return YYYY-MM-DD dirs in sorted order."""
    root = tmp_path / "PAPER"
    for d in ["2026-05-13", "2026-05-11", "2026-05-12"]:
        (root / d).mkdir(parents=True)
    # A non-date dir should be ignored
    (root / "not-a-date-dir").mkdir()

    dates = discover_paper_dates(root)
    assert dates == ["2026-05-11", "2026-05-12", "2026-05-13"]


def test_discover_paper_dates_missing_root_returns_empty(tmp_path):
    """discover_paper_dates returns empty list when root does not exist."""
    result = discover_paper_dates(tmp_path / "nonexistent")
    assert result == []


def test_discover_paper_dates_empty_root_returns_empty(tmp_path):
    """discover_paper_dates returns empty list when root is empty."""
    empty_root = tmp_path / "PAPER"
    empty_root.mkdir()
    assert discover_paper_dates(empty_root) == []


# ─── Tests: single-date evaluation ────────────────────────────────────────────


def test_single_date_evaluate_returns_correct_hit_rate(paper_dir_fixture, outcome_file_fixture):
    """execute_evaluation: both rows matched, both correct → hit_rate=1.0."""
    date_dir = paper_dir_fixture / "2026-05-11"
    result = execute_evaluation(
        paper_dir=date_dir,
        outcome_path=outcome_file_fixture,
    )
    assert result["metrics"]["evaluated_count"] == 2
    assert result["metrics"]["matched_outcome_count"] == 2
    assert result["metrics"]["hit_rate"] == 1.0


def test_single_date_evaluate_has_timestamp_utc(paper_dir_fixture, outcome_file_fixture):
    """execute_evaluation: timestamp_utc must be a non-empty UTC ISO string."""
    date_dir = paper_dir_fixture / "2026-05-11"
    result = execute_evaluation(
        paper_dir=date_dir,
        outcome_path=outcome_file_fixture,
    )
    ts = result.get("timestamp_utc", "")
    assert isinstance(ts, str)
    assert len(ts) > 0
    assert "T" in ts


def test_single_date_evaluate_zero_rows_safe(tmp_path, outcome_file_fixture):
    """execute_evaluation with no paper rows returns safe empty metrics without crashing."""
    empty_dir = tmp_path / "PAPER" / "2026-06-01"
    empty_dir.mkdir(parents=True)
    result = execute_evaluation(
        paper_dir=empty_dir,
        outcome_path=outcome_file_fixture,
    )
    assert result["metrics"]["evaluated_count"] == 0
    assert result["metrics"]["matched_outcome_count"] == 0
    assert result["metrics"]["hit_rate"] == 0.0
    assert result["metrics"]["brier_score"] is None


def test_single_date_evaluate_missing_dir_safe(tmp_path, outcome_file_fixture):
    """execute_evaluation with a nonexistent paper dir returns empty metrics safely."""
    result = execute_evaluation(
        paper_dir=tmp_path / "nonexistent",
        outcome_path=outcome_file_fixture,
    )
    assert result["metrics"]["evaluated_count"] == 0


def test_single_date_evaluate_missing_outcomes_counted(paper_dir_fixture, tmp_path):
    """execute_evaluation: rows with no matching outcome are counted as missing."""
    empty_outcomes = tmp_path / "empty_outcomes.jsonl"
    empty_outcomes.write_text("", encoding="utf-8")
    date_dir = paper_dir_fixture / "2026-05-11"
    result = execute_evaluation(
        paper_dir=date_dir,
        outcome_path=empty_outcomes,
    )
    assert result["metrics"]["evaluated_count"] == 2
    assert result["metrics"]["matched_outcome_count"] == 0
    assert result["metrics"]["missing_outcome_count"] == 2


def test_single_date_output_is_json_serializable(paper_dir_fixture, outcome_file_fixture, tmp_path):
    """execute_evaluation output dict must be fully JSON-serializable."""
    date_dir = paper_dir_fixture / "2026-05-11"
    summary_path = tmp_path / "summary.json"
    result = execute_evaluation(
        paper_dir=date_dir,
        outcome_path=outcome_file_fixture,
        summary_output_path=summary_path,
    )
    # Should not raise
    serialized = json.dumps(result)
    assert len(serialized) > 0
    # Written file should be parseable
    assert summary_path.exists()
    loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    assert loaded["metrics"]["evaluated_count"] == result["metrics"]["evaluated_count"]


# ─── Tests: no provider / live / Kelly / EV / CLV fields required ─────────────


def test_evaluation_does_not_require_provider_fields(paper_dir_fixture, outcome_file_fixture):
    """Evaluation must succeed with paper rows that have no provider/live/EV/CLV/Kelly fields."""
    minimal_recs = [
        {
            "game_id": "2026-05-11-MIN-KC-900001",
            "model_prob_home": 0.55,
            "model_prob_away": 0.45,
            "tsl_market": "moneyline",
            "tsl_side": "home",
            "tsl_decimal_odds": 1.85,
            "stake_units_paper": 0.0,
            "gate_status": "BLOCKED_TSL_SOURCE",
            "paper_only": True,
        }
    ]
    outcomes_with_match = [
        {
            "game_id": "mlb_2026_900001",
            "outcome_available": True,
            "actual_winner": "home",
        }
    ]
    metrics = evaluate_paper_recommendations(minimal_recs, outcomes_with_match)
    assert metrics.evaluated_count == 1
    assert metrics.matched_outcome_count == 1


def test_evaluation_does_not_require_ev_clv_kelly_fields(tmp_path):
    """Rows without ev / clv / kelly fields must be evaluated without crash."""
    recs = [
        {
            "game_id": "2026-05-11-LAD-SF-910001",
            "model_prob_home": 0.60,
            "model_prob_away": 0.40,
            "tsl_side": "home",
            "tsl_decimal_odds": 1.90,
            "stake_units_paper": 0.0,
            "gate_status": "BLOCKED_SIMULATION_GATE",
            "paper_only": True,
            # Explicitly no ev, clv, kelly_fraction fields
        }
    ]
    outcomes = [
        {"game_id": "mlb_2026_910001", "outcome_available": True, "actual_winner": "home"}
    ]
    metrics = evaluate_paper_recommendations(recs, outcomes)
    assert metrics.evaluated_count == 1
    assert metrics.hit_rate == 1.0


# ─── Tests: batch evaluation ──────────────────────────────────────────────────


def test_batch_evaluate_multiple_dates(tmp_path, sample_outcomes):
    """execute_batch_evaluation: evaluates each date folder and aggregates."""
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text(
        "\n".join(json.dumps(o) for o in sample_outcomes) + "\n",
        encoding="utf-8",
    )

    # Build two date folders
    paper_root = tmp_path / "PAPER"
    for date_str, game_id, side in [
        ("2026-05-11", "2026-05-11-LAA-CLE-824441", "home"),
        ("2026-05-12", "2026-05-12-NYY-BOS-824442", "away"),
    ]:
        d = paper_root / date_str
        d.mkdir(parents=True)
        rec = {
            "game_id": game_id,
            "model_prob_home": 0.55,
            "model_prob_away": 0.45,
            "tsl_side": side,
            "tsl_decimal_odds": 1.90,
            "stake_units_paper": 0.0,
            "gate_status": "BLOCKED_TSL_SOURCE",
            "paper_only": True,
        }
        (d / "rec.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")

    result = execute_batch_evaluation(
        paper_root=paper_root,
        outcome_path=outcome_file,
    )

    assert result["mode"] == "batch"
    assert set(result["dates_found"]) == {"2026-05-11", "2026-05-12"}
    assert result["dates_evaluated"] == 2
    assert result["total_rows"] == 2
    assert "per_date" in result
    assert "2026-05-11" in result["per_date"]
    assert "2026-05-12" in result["per_date"]
    assert "aggregate" in result


def test_batch_evaluate_empty_root_safe(tmp_path):
    """execute_batch_evaluation with no date folders returns zero-row aggregate safely."""
    paper_root = tmp_path / "PAPER"
    paper_root.mkdir()
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text("", encoding="utf-8")

    result = execute_batch_evaluation(paper_root=paper_root, outcome_path=outcome_file)
    assert result["dates_evaluated"] == 0
    assert result["total_rows"] == 0
    assert result["aggregate"]["evaluated_count"] == 0


def test_batch_output_is_json_serializable(tmp_path, sample_outcomes):
    """execute_batch_evaluation output must be fully JSON-serializable."""
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text(
        "\n".join(json.dumps(o) for o in sample_outcomes) + "\n", encoding="utf-8"
    )
    paper_root = tmp_path / "PAPER"
    paper_root.mkdir()
    summary_out = tmp_path / "batch_summary.json"

    result = execute_batch_evaluation(
        paper_root=paper_root,
        outcome_path=outcome_file,
        summary_output_path=summary_out,
    )
    serialized = json.dumps(result)
    assert len(serialized) > 0


def test_batch_per_date_schema(tmp_path, sample_recommendations, sample_outcomes):
    """Each per_date entry must contain the expected schema keys."""
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text(
        "\n".join(json.dumps(o) for o in sample_outcomes) + "\n", encoding="utf-8"
    )
    paper_root = tmp_path / "PAPER"
    date_dir = paper_root / "2026-05-11"
    date_dir.mkdir(parents=True)
    for i, rec in enumerate(sample_recommendations):
        (date_dir / f"rec_{i}.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")

    result = execute_batch_evaluation(paper_root=paper_root, outcome_path=outcome_file)

    per_date_entry = result["per_date"]["2026-05-11"]
    for key in (
        "evaluated_count",
        "matched_outcome_count",
        "missing_outcome_count",
        "coverage_rate",
        "hit_rate",
        "brier_score",
        "actual_paper_roi",
        "shadow_unit_roi",
        "binomial_p_value",
    ):
        assert key in per_date_entry, f"Missing key {key!r} in per_date entry"


# ─── Tests: CLI runner entrypoint ─────────────────────────────────────────────


def test_cli_single_date_exits_0(paper_dir_fixture, outcome_file_fixture, tmp_path):
    """CLI single-date mode returns exit code 0 for valid date with fixture data."""
    import importlib.util

    script_path = REPO_ROOT / "scripts" / "run_mlb_paper_evaluation.py"
    spec = importlib.util.spec_from_file_location("run_mlb_paper_evaluation", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out_path = str(tmp_path / "out.json")
    exit_code = mod.run_single_date(
        date_str="2026-05-11",
        paper_dir=str(paper_dir_fixture / "2026-05-11"),
        outcome_path=str(outcome_file_fixture),
        output=out_path,
    )
    assert exit_code == 0
    assert (tmp_path / "out.json").exists()


def test_cli_batch_exits_0_with_fixture_data(
    paper_dir_fixture, outcome_file_fixture, tmp_path
):
    """CLI batch mode returns exit code 0 even with fixture data."""
    import importlib.util

    script_path = REPO_ROOT / "scripts" / "run_mlb_paper_evaluation.py"
    spec = importlib.util.spec_from_file_location("run_mlb_paper_evaluation", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out_path = str(tmp_path / "batch_out.json")
    exit_code = mod.run_batch(
        paper_root=str(paper_dir_fixture),
        outcome_path=str(outcome_file_fixture),
        output=out_path,
    )
    assert exit_code == 0
    assert (tmp_path / "batch_out.json").exists()


def test_cli_no_mode_specified_returns_error_code():
    """CLI without --date or --all-dates must exit with code 2."""
    import importlib.util
    import io

    script_path = REPO_ROOT / "scripts" / "run_mlb_paper_evaluation.py"
    spec = importlib.util.spec_from_file_location("run_mlb_paper_evaluation", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with patch("sys.argv", ["run_mlb_paper_evaluation.py"]):
        try:
            exit_code = mod.main()
        except SystemExit as exc:
            exit_code = exc.code
    assert exit_code == 2


# ─── P144: runner DATA_LIMITED / idempotency contract ─────────────────────────

from orchestrator.mlb_daily_scheduler import (  # noqa: E402
    JOB_STATUS_DATA_LIMITED,
    JOB_STATUS_SUCCESS,
    PAPER_EVAL_STATUS_OUTCOMES_UNAVAILABLE,
    run_paper_evaluation_job,
)


def test_evaluator_metrics_are_deterministic(tmp_path, sample_recommendations, sample_outcomes):
    """execute_evaluation metrics are a pure function of inputs (idempotent)."""
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text(
        "\n".join(json.dumps(o) for o in sample_outcomes) + "\n", encoding="utf-8"
    )
    date_dir = tmp_path / "PAPER" / "2026-05-11"
    date_dir.mkdir(parents=True)
    for i, rec in enumerate(sample_recommendations):
        (date_dir / f"rec_{i}.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")

    r1 = execute_evaluation(paper_dir=date_dir, outcome_path=outcome_file)
    r2 = execute_evaluation(paper_dir=date_dir, outcome_path=outcome_file)
    assert r1["metrics"] == r2["metrics"]  # timestamp may differ; metrics may not


def test_runner_outcomes_unavailable_data_limited(tmp_path):
    """run_paper_evaluation_job: rows present, no matching outcomes → DATA_LIMITED."""
    date_dir = tmp_path / "PAPER" / "2026-05-11"
    date_dir.mkdir(parents=True)
    (date_dir / "rec.jsonl").write_text(
        json.dumps({
            "game_id": "2026-05-11-LAA-CLE-824441",
            "model_prob_home": 0.6, "model_prob_away": 0.4,
            "tsl_side": "home", "tsl_decimal_odds": 1.9,
            "stake_units_paper": 0.0, "gate_status": "BLOCKED_TSL_SOURCE",
            "paper_only": True,
        }) + "\n",
        encoding="utf-8",
    )
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text("", encoding="utf-8")  # no outcomes yet

    result = run_paper_evaluation_job(
        run_date="2026-05-11", paper_dir=str(date_dir),
        outcome_path=str(outcome_file), output_path=str(tmp_path / "out.json"),
    )
    assert result.status == JOB_STATUS_DATA_LIMITED
    assert result.details["data_status"] == PAPER_EVAL_STATUS_OUTCOMES_UNAVAILABLE


def test_runner_idempotent_artifact_metrics(tmp_path):
    """Re-running the runner before outcomes arrive yields identical artifact metrics."""
    date_dir = tmp_path / "PAPER" / "2026-05-11"
    date_dir.mkdir(parents=True)
    (date_dir / "rec.jsonl").write_text(
        json.dumps({
            "game_id": "2026-05-11-LAA-CLE-824441",
            "model_prob_home": 0.6, "model_prob_away": 0.4,
            "tsl_side": "home", "tsl_decimal_odds": 1.9,
            "stake_units_paper": 0.0, "gate_status": "BLOCKED_TSL_SOURCE",
            "paper_only": True,
        }) + "\n",
        encoding="utf-8",
    )
    outcome_file = tmp_path / "outcomes.jsonl"
    outcome_file.write_text("", encoding="utf-8")
    out_path = tmp_path / "out.json"

    run_paper_evaluation_job(
        run_date="2026-05-11", paper_dir=str(date_dir),
        outcome_path=str(outcome_file), output_path=str(out_path),
    )
    m1 = json.loads(out_path.read_text(encoding="utf-8"))["metrics"]
    run_paper_evaluation_job(
        run_date="2026-05-11", paper_dir=str(date_dir),
        outcome_path=str(outcome_file), output_path=str(out_path),
    )
    m2 = json.loads(out_path.read_text(encoding="utf-8"))["metrics"]
    assert m1 == m2
