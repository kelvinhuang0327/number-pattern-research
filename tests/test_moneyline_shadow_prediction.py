"""Focused offline tests for the P278-A corrected Moneyline shadow handoff."""
from __future__ import annotations

import csv
import json
import socket
from pathlib import Path

import pytest

from scripts import _p275_prospective_availability_consumer_gate as p275
from wbc_backend.recommendation import moneyline_shadow_prediction as shadow


GAME_ID = "mlb_2026_825108"
OBSERVED_AT = "2026-07-13T07:17:10.769880Z"
BEFORE = "2026-07-13T07:17:10.769879Z"
AFTER = "2026-07-13T07:17:10.769881Z"


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_network(*args, **kwargs):
        raise AssertionError("P278-A tests must make zero network calls")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def _write_training(path: Path, *, reverse_same_date: bool = False) -> None:
    same_date = [
        ["2025-04-01", "Away A", 2, "Home A", 5, "Final"],
        ["2025-04-01", "Away B", 6, "Home B", 3, "Final"],
    ]
    if reverse_same_date:
        same_date.reverse()
    rows = [
        *same_date,
        ["2025-04-02", "Home A", 2, "Away B", 4, "Final"],
        ["2025-04-03", "Home B", 1, "Away A", 3, "Final"],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["Date", "Away", "Away Score", "Home", "Home Score", "Status"]
        )
        writer.writerows(rows)


def _prediction_row(
    game_id: str,
    game_date: str,
    away_team: str,
    home_team: str,
    *,
    feature_as_of_utc: str | None = None,
) -> dict:
    row = {
        "game_id": game_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "source_prediction_version": shadow.BASELINE_SOURCE_VERSION,
        "actual_winner": None,
        "is_correct": None,
        "result_home_score": None,
        "result_away_score": None,
    }
    if feature_as_of_utc is not None:
        row["feature_as_of_utc"] = feature_as_of_utc
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _generate_fixture(
    tmp_path: Path,
    *,
    predictions: list[dict],
    outcomes: list[dict] | None = None,
    out_name: str = "out",
    generated_at: str = "2026-07-14T00:00:00Z",
):
    training = tmp_path / "training.csv"
    prediction_path = tmp_path / "predictions.jsonl"
    outcome_path = tmp_path / "outcomes.jsonl"
    _write_training(training)
    _write_jsonl(prediction_path, predictions)
    _write_jsonl(outcome_path, outcomes or [])
    return shadow.generate_shadow_handoff(
        training_path=training,
        prediction_input_path=prediction_path,
        outcome_path=outcome_path,
        out_dir=tmp_path / out_name,
        source_git_commit="test-source-commit",
        generated_at_utc=generated_at,
        execution_command="test-generation-command",
    )


def _normalized_manifest(payload: dict) -> dict:
    copied = json.loads(json.dumps(payload))
    copied["generation"]["runtime_metadata"] = "NORMALIZED"
    return copied


def _normalized_summary(text: str) -> str:
    prefixes = ("- Generated at:", "- Execution command:", "- Execution output root:")
    return "\n".join(
        line for line in text.splitlines() if not line.startswith(prefixes)
    )


def test_real_committed_inputs_use_selected_model_and_safe_frozen_state(
    tmp_path: Path,
) -> None:
    baseline_before = shadow._sha256_file(shadow.DEFAULT_PREDICTION_INPUT_PATH)

    result = shadow.generate_shadow_handoff(
        out_dir=tmp_path,
        source_git_commit="77bca9d939cc361b6a1b3ef586d1417071f46a28",
        generated_at_utc="2026-07-14T00:00:00Z",
        execution_command="test-real-committed-inputs",
    )

    manifest = result["manifest"]
    assert manifest["model"]["algorithm"] == shadow.ALGORITHM_NAME
    assert manifest["training"]["eligible_row_count"] == 2430
    assert manifest["training"]["eligible_date_count"] == 184
    assert manifest["training"]["last_training_date"] == "2025-09-28"
    assert manifest["prediction_input"]["row_count"] == 828
    assert manifest["prediction_input"]["explicit_canonical_as_of_rows"] == 0
    assert manifest["availability_evidence"]["record_count"] == 1
    assert manifest["p275_state_updates"] == {
        "attempted": 0,
        "allowed": 0,
        "denied": 0,
        "denial_counts_by_reason": {},
        "applied": 0,
        "raw_outcome_available_candidate_rows": 808,
        "candidate_rows_not_attempted": 808,
        "raw_outcome_flag_alone_can_update_state": False,
        "missing_as_of_policy": "FREEZE_AND_DO_NOT_INVOKE_OUTCOME_UPDATE",
    }
    assert manifest["state_mode"] == shadow.FROZEN_STATE_MODE
    assert manifest["outcome_evaluation"]["outcome_evaluation_denominator"] == 0
    assert manifest["outcome_evaluation"]["accuracy"] is None
    assert manifest["outcome_evaluation"]["brier_score"] is None
    assert len(result["predictions"]) == 828
    assert all(row["feature_as_of_utc"] == "" for row in result["predictions"])
    assert all(
        row["prior_outcome_update_applied"] is False
        for row in result["predictions"]
    )
    assert shadow._sha256_file(shadow.DEFAULT_PREDICTION_INPUT_PATH) == baseline_before
    assert manifest["baseline_separation"]["baseline_byte_unchanged"] is True


def test_refit_is_complete_date_and_source_order_invariant(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    _write_training(first)
    _write_training(second, reverse_same_date=True)

    first_result = shadow.refit_selected_model(first)
    second_result = shadow.refit_selected_model(second)

    assert first_result.metadata["eligible_row_count"] == 4
    assert first_result.metadata["eligible_date_count"] == 3
    assert first_result.metadata["first_training_date"] == "2025-04-01"
    assert first_result.metadata["last_training_date"] == "2025-04-03"
    assert (
        first_result.metadata["final_state_fingerprint"]
        == second_result.metadata["final_state_fingerprint"]
    )
    assert (
        first_result.metadata["eligible_training_rows_fingerprint"]
        == second_result.metadata["eligible_training_rows_fingerprint"]
    )


def test_prediction_order_and_fingerprints_are_deterministic(tmp_path: Path) -> None:
    rows = [
        _prediction_row("game-b", "2026-04-02", "Away B", "Home B"),
        _prediction_row("game-a", "2026-04-01", "Away A", "Home A"),
    ]
    first = _generate_fixture(tmp_path, predictions=rows, out_name="first")
    second = shadow.generate_shadow_handoff(
        training_path=tmp_path / "training.csv",
        prediction_input_path=tmp_path / "predictions.jsonl",
        outcome_path=tmp_path / "outcomes.jsonl",
        out_dir=tmp_path / "second",
        source_git_commit="test-source-commit",
        generated_at_utc="2026-07-14T00:00:01Z",
        execution_command="second-runtime-command",
    )

    assert [row["game_id"] for row in first["predictions"]] == ["game-a", "game-b"]
    assert (
        first["paths"]["predictions_csv"].read_bytes()
        == second["paths"]["predictions_csv"].read_bytes()
    )
    assert _normalized_manifest(first["manifest"]) == _normalized_manifest(
        second["manifest"]
    )
    assert _normalized_summary(
        first["paths"]["summary_markdown"].read_text(encoding="utf-8")
    ) == _normalized_summary(
        second["paths"]["summary_markdown"].read_text(encoding="utf-8")
    )
    assert (
        first["manifest"]["model"]["model_code_config_fingerprint"]
        == second["manifest"]["model"]["model_code_config_fingerprint"]
    )


def test_duplicate_game_ids_fail_clearly(tmp_path: Path) -> None:
    row = _prediction_row("duplicate", "2026-04-01", "Away", "Home")
    with pytest.raises(ValueError, match="duplicate game_id"):
        _generate_fixture(tmp_path, predictions=[row, dict(row)])


@pytest.mark.parametrize(
    "field_name",
    ["actual_winner", "is_correct", "result_home_score", "result_away_score"],
)
def test_prediction_input_outcome_fields_fail_closed(
    tmp_path: Path, field_name: str
) -> None:
    row = _prediction_row("game-a", "2026-04-01", "Away", "Home")
    row[field_name] = "poisoned-outcome"
    with pytest.raises(ValueError, match="contains outcome fields"):
        _generate_fixture(tmp_path, predictions=[row])


def test_raw_outcome_flag_without_as_of_never_invokes_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    predictions = [
        _prediction_row(GAME_ID, "2026-04-01", "Away", "Home"),
        _prediction_row("later", "2026-04-02", "Other", "Home"),
    ]
    outcomes = [
        {
            "game_id": GAME_ID,
            "outcome_available": True,
            "actual_winner": "home",
        }
    ]

    def forbidden_gate(**kwargs):
        raise AssertionError(f"missing as-of must not invoke P275: {kwargs}")

    monkeypatch.setattr(shadow.p275, "evaluate_result_availability", forbidden_gate)
    result = _generate_fixture(tmp_path, predictions=predictions, outcomes=outcomes)

    assert result["manifest"]["p275_state_updates"]["attempted"] == 0
    assert result["manifest"]["p275_state_updates"]["applied"] == 0
    assert result["manifest"]["state_mode"] == shadow.FROZEN_STATE_MODE


def test_p275_approved_prior_complete_date_is_the_only_applied_update(
    tmp_path: Path,
) -> None:
    predictions = [
        _prediction_row(
            GAME_ID,
            "2026-04-01",
            "Away A",
            "Home A",
            feature_as_of_utc=BEFORE,
        ),
        _prediction_row(
            "later",
            "2026-07-14",
            "Away B",
            "Home A",
            feature_as_of_utc=AFTER,
        ),
    ]
    outcomes = [
        {
            "game_id": GAME_ID,
            "outcome_available": True,
            "actual_winner": "home",
        }
    ]

    result = _generate_fixture(tmp_path, predictions=predictions, outcomes=outcomes)

    updates = result["manifest"]["p275_state_updates"]
    assert updates["attempted"] == 1
    assert updates["allowed"] == 1
    assert updates["denied"] == 0
    assert updates["applied"] == 1
    later = next(row for row in result["predictions"] if row["game_id"] == "later")
    assert later["prior_outcome_update_applied"] is True
    assert later["state_mode"] == shadow.GATED_STATE_MODE
    evaluation = result["manifest"]["outcome_evaluation"]
    assert evaluation["outcome_evaluation_denominator"] == 0
    assert result["manifest"]["outcome_evaluation_gate"]["denied"] == 1
    assert result["manifest"]["outcome_evaluation_gate"][
        "denial_counts_by_reason"
    ] == {p275.RESULT_NOT_YET_AVAILABLE: 1}


def test_p275_denial_blocks_raw_outcome_state_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    predictions = [
        _prediction_row(
            GAME_ID,
            "2026-04-01",
            "Away A",
            "Home A",
            feature_as_of_utc=BEFORE,
        ),
        _prediction_row(
            "later",
            "2026-04-02",
            "Away B",
            "Home A",
            feature_as_of_utc=AFTER,
        ),
    ]
    outcomes = [
        {"game_id": GAME_ID, "outcome_available": True, "actual_winner": "home"}
    ]

    def deny(**kwargs):
        return p275.AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=p275.MISSING_AVAILABILITY_EVIDENCE,
            game_id=kwargs["game_id"],
            feature_as_of_utc=kwargs["feature_as_of_utc"],
            result_available_at_utc=None,
        )

    monkeypatch.setattr(shadow.p275, "evaluate_result_availability", deny)
    result = _generate_fixture(tmp_path, predictions=predictions, outcomes=outcomes)

    updates = result["manifest"]["p275_state_updates"]
    assert updates["attempted"] == 1
    assert updates["allowed"] == 0
    assert updates["denied"] == 1
    assert updates["applied"] == 0
    assert updates["denial_counts_by_reason"] == {
        p275.MISSING_AVAILABILITY_EVIDENCE: 1
    }
    assert all(
        row["prior_outcome_update_applied"] is False
        for row in result["predictions"]
    )


def test_zero_denominator_reports_na_and_only_writes_allowed_artifacts(
    tmp_path: Path,
) -> None:
    result = _generate_fixture(
        tmp_path,
        predictions=[_prediction_row("game-a", "2026-04-01", "Away", "Home")],
    )
    output_names = {path.name for path in result["paths"].values()}
    assert output_names == {shadow.CSV_FILENAME, shadow.MANIFEST_FILENAME, shadow.SUMMARY_FILENAME}
    summary = result["paths"]["summary_markdown"].read_text(encoding="utf-8")
    assert "Accuracy: `N/A`" in summary
    assert "Brier: `N/A`" in summary
    assert "ROI / EV / Kelly: `N/A` / `N/A` / `N/A`" in summary
    assert "not a live or pregame publication" in summary
    assert "not production-ready" in summary
    assert "not betting readiness" in summary
    assert "no champion activation" in summary
    assert "production-ready: true" not in summary.lower()
    assert "verified betting edge" not in summary.lower()
