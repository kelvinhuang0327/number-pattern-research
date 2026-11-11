from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from wbc_backend.recommendation import moneyline_shadow_divergence as div


def _p84b_row(
    game_id: str,
    probability: float,
    *,
    game_date: str = "2026-04-01",
    away_team: str = "Away",
    home_team: str = "Home",
) -> dict:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "model_probability": probability,
        "predicted_side": "home" if probability >= 0.5 else "away",
        "source_prediction_version": div.EXPECTED_P84B_VERSION,
        "result_home_score": 99,
        "result_away_score": -1,
        "actual_winner": "ignored",
        "outcome_available": True,
        "odds": "+999",
    }


def _p278_row(
    game_id: str,
    probability: float,
    *,
    game_date: str = "2026-04-01",
    away_team: str = "Away",
    home_team: str = "Home",
) -> dict:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "away_team": away_team,
        "home_team": home_team,
        "shadow_home_win_probability": probability,
        "predicted_side": "HOME" if probability >= 0.5 else "AWAY",
        "model_id": "corrected_moneyline_shadow",
        "model_version": div.EXPECTED_P278_VERSION,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(path: Path, row_count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "artifact_version": div.EXPECTED_P278_VERSION,
                "artifacts": {"prediction_row_count": row_count},
                "baseline_separation": {
                    "baseline_source_version": div.EXPECTED_P84B_VERSION
                },
                "model": {
                    "model_id": "corrected_moneyline_shadow",
                    "model_version": div.EXPECTED_P278_VERSION,
                },
                "state_mode": "frozen_final_2025_state",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _fixture_inputs(root: Path) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    left = root / "p84b.jsonl"
    right = root / "p278.csv"
    manifest = root / "p278_manifest.json"
    left_rows = [
        _p84b_row("g-1", 0.48, game_date="2026-03-31", away_team="A1", home_team="H1"),
        _p84b_row("g-2", 0.60, away_team="A2", home_team="H2"),
        _p84b_row("g-3", 0.70, away_team="A3", home_team="H3"),
        _p84b_row("g-4", 0.40, game_date="2026-05-01", away_team="A4", home_team="H4"),
    ]
    right_rows = [
        _p278_row("g-1", 0.52, game_date="2026-03-31", away_team="A1", home_team="H1"),
        _p278_row("g-2", 0.65, away_team="A2", home_team="H2"),
        _p278_row("g-3", 0.59, away_team="A3", home_team="H3"),
        _p278_row("g-4", 0.42, game_date="2026-05-01", away_team="A4", home_team="H4"),
    ]
    _write_jsonl(left, left_rows)
    _write_csv(right, right_rows)
    _write_manifest(manifest, len(right_rows))
    return left, right, manifest


def _build(paths: tuple[Path, Path, Path], **kwargs):
    left, right, manifest = paths
    return div.build_divergence(
        p84b_path=left,
        p278_path=right,
        p278_manifest_path=manifest,
        **kwargs,
    )


def test_alignment_uses_exact_game_id_not_row_order(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path / "a")
    ledger_a, summary_a = _build(paths)

    left, right, manifest = _fixture_inputs(tmp_path / "b")
    left_rows = [json.loads(line) for line in left.read_text().splitlines()]
    with right.open(newline="", encoding="utf-8") as handle:
        right_rows = list(csv.DictReader(handle))
    _write_jsonl(left, list(reversed(left_rows)))
    _write_csv(right, [right_rows[2], right_rows[0], right_rows[3], right_rows[1]])
    ledger_b, summary_b = _build((left, right, manifest))

    assert ledger_a == ledger_b
    assert summary_a == summary_b
    assert [row["game_id"] for row in ledger_a] == ["g-1", "g-2", "g-3", "g-4"]


def test_committed_sources_have_independently_verified_828_shared_games() -> None:
    left_ids = {
        json.loads(line)["game_id"]
        for line in div.DEFAULT_P84B_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    with div.DEFAULT_P278_PATH.open(newline="", encoding="utf-8") as handle:
        right_rows = list(csv.DictReader(handle))
    right_ids = {row["game_id"] for row in right_rows}

    assert len(left_ids) == 828
    assert len(right_rows) == 828
    assert len(right_ids) == 828
    assert left_ids == right_ids
    ledger, summary = div.build_divergence(
        p84b_path=div.DEFAULT_P84B_PATH,
        p278_path=div.DEFAULT_P278_PATH,
        p278_manifest_path=div.DEFAULT_P278_MANIFEST_PATH,
    )
    assert len(ledger) == 828
    assert summary["alignment"]["shared_game_count"] == 828


def test_probability_orientation_side_delta_and_thresholds(tmp_path: Path) -> None:
    ledger, summary = _build(_fixture_inputs(tmp_path))
    rows = {row["game_id"]: row for row in ledger}

    assert rows["g-1"]["signed_probability_delta"] == pytest.approx(0.04)
    assert rows["g-1"]["p84b_predicted_side"] == "AWAY"
    assert rows["g-1"]["p278_predicted_side"] == "HOME"
    assert rows["g-1"]["side_disagreement"] is True
    assert rows["g-2"]["material_difference_bucket"] == "GE_0_05_LT_0_10"
    assert rows["g-2"]["abs_delta_ge_0_05"] is True
    assert rows["g-3"]["material_difference_bucket"] == "GE_0_10"
    assert rows["g-4"]["absolute_probability_delta"] == pytest.approx(0.02)
    assert rows["g-4"]["abs_delta_ge_0_02"] is True
    assert summary["divergence_metrics"]["side_disagreement_count"] == 1
    assert summary["divergence_metrics"]["thresholds"]["0.02"]["count"] == 4
    assert summary["divergence_metrics"]["thresholds"]["0.05"]["count"] == 2
    assert summary["divergence_metrics"]["thresholds"]["0.10"]["count"] == 1


def test_duplicate_ids_fail_clearly(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    left = paths[0]
    first = left.read_text(encoding="utf-8").splitlines()[0]
    left.write_text(left.read_text(encoding="utf-8") + first + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"duplicate game IDs in P84-B: count=1"):
        _build(paths)


def test_missing_ids_fail_or_are_reported_deterministically(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    right = paths[1]
    with right.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    _write_csv(right, rows[:-1])
    _write_manifest(paths[2], len(rows) - 1)

    with pytest.raises(ValueError, match=r"missing_p278=1 \['g-4'\]"):
        _build(paths)
    ledger, summary = _build(paths, require_full_alignment=False)
    assert len(ledger) == 3
    assert summary["alignment"]["missing_p278_game_ids"] == ["g-4"]
    assert summary["alignment"]["missing_p84b_game_ids"] == []


def test_percentiles_use_documented_r7_linear_interpolation() -> None:
    values = [0.0, 1.0, 2.0, 3.0]
    assert div.percentile_r7(values, 0.5) == pytest.approx(1.5)
    assert div.percentile_r7(values, 0.9) == pytest.approx(2.7)
    assert div.percentile_r7(values, 0.95) == pytest.approx(2.85)
    assert "R-7 linear interpolation" in div.PERCENTILE_METHOD


def test_summary_reconciles_exactly_with_ledger(tmp_path: Path) -> None:
    ledger, summary = _build(_fixture_inputs(tmp_path))
    metrics = summary["divergence_metrics"]
    assert metrics["row_count"] == len(ledger)
    assert metrics["side_agreement_count"] == sum(
        row["side_agreement"] for row in ledger
    )
    assert metrics["side_disagreement_count"] == sum(
        row["side_disagreement"] for row in ledger
    )
    for threshold, field in (
        ("0.02", "abs_delta_ge_0_02"),
        ("0.05", "abs_delta_ge_0_05"),
        ("0.10", "abs_delta_ge_0_10"),
    ):
        assert metrics["thresholds"][threshold]["count"] == sum(
            row[field] for row in ledger
        )
    assert sum(row["row_count"] for row in summary["monthly_breakdown"]) == len(ledger)
    assert sum(metrics["confidence_change_counts"].values()) == len(ledger)


def test_outcome_score_availability_odds_settlement_and_noise_are_isolated(
    tmp_path: Path,
) -> None:
    base_paths = _fixture_inputs(tmp_path / "base")
    mutation_paths = _fixture_inputs(tmp_path / "mutated")
    baseline = _build(base_paths)

    left, right, _ = mutation_paths
    left_rows = [json.loads(line) for line in left.read_text().splitlines()]
    for index, row in enumerate(left_rows):
        row.pop("actual_winner", None)
        row["result_home_score"] = -1000 - index
        row["result_away_score"] = 1000 + index
        row["outcome_available"] = not bool(row.get("outcome_available"))
        row["odds"] = None
        row["settlement_result"] = "MUTATED"
        row["postgame_noise"] = {"index": index, "winner": "noise"}
    _write_jsonl(left, left_rows)

    with right.open(newline="", encoding="utf-8") as handle:
        right_rows = list(csv.DictReader(handle))
    for index, row in enumerate(right_rows):
        row["final_home_score"] = str(200 + index)
        row["final_away_score"] = str(-200 - index)
        row["winner"] = "MUTATED"
        row["outcome_available"] = "False"
        row["closing_odds"] = "-999"
        row["settlement"] = "VOID"
        row["postgame_noise"] = f"noise-{index}"
    _write_csv(right, right_rows)

    mutated = _build(mutation_paths)
    assert mutated == baseline
    base_output = div.write_divergence_reports(
        ledger=baseline[0],
        summary=baseline[1],
        out_dir=tmp_path / "base-output" / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
    )
    mutated_output = div.write_divergence_reports(
        ledger=mutated[0],
        summary=mutated[1],
        out_dir=tmp_path / "mutated-output" / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
    )
    assert base_output["ledger_csv"].read_bytes() == mutated_output[
        "ledger_csv"
    ].read_bytes()
    assert base_output["summary_json"].read_bytes() == mutated_output[
        "summary_json"
    ].read_bytes()
    assert base_output["summary_markdown"].read_bytes() == mutated_output[
        "summary_markdown"
    ].read_bytes()


def _normalized_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("runtime_metadata", None)
    return payload


def _normalized_markdown(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "Summary JSON file SHA-256" in line:
            continue
        if "Generated at (runtime metadata only)" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def test_repeated_runs_are_deterministic_except_truthful_runtime_metadata(
    tmp_path: Path,
) -> None:
    paths = _fixture_inputs(tmp_path / "inputs")
    ledger, summary = _build(paths)
    first = div.write_divergence_reports(
        ledger=ledger,
        summary=summary,
        out_dir=tmp_path / "run-1" / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
        source_git_commit="abc",
    )
    second = div.write_divergence_reports(
        ledger=ledger,
        summary=summary,
        out_dir=tmp_path / "run-2" / "report",
        generated_at_utc="2026-07-14T10:01:00Z",
        source_git_commit="abc",
    )

    assert first["ledger_csv"].read_bytes() == second["ledger_csv"].read_bytes()
    assert first["ledger_csv_sha256"] == second["ledger_csv_sha256"]
    assert (
        first["summary_deterministic_payload_sha256"]
        == second["summary_deterministic_payload_sha256"]
    )
    assert _normalized_json(first["summary_json"]) == _normalized_json(
        second["summary_json"]
    )
    assert _normalized_markdown(first["summary_markdown"]) == _normalized_markdown(
        second["summary_markdown"]
    )


def test_protected_prediction_inputs_remain_byte_identical(tmp_path: Path) -> None:
    protected = [
        div.DEFAULT_P84B_PATH,
        div.DEFAULT_P278_PATH,
        div.DEFAULT_P278_MANIFEST_PATH,
        div.REPO_ROOT / "report/mlb_2026_corrected_moneyline_shadow_summary.md",
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    div.generate_divergence_reports(
        out_dir=tmp_path / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
        source_git_commit="test",
    )
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    assert before == after


def test_committed_sources_generate_twice_identically_in_pytest_roots(
    tmp_path: Path,
) -> None:
    first = div.generate_divergence_reports(
        out_dir=tmp_path / "first" / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
        source_git_commit="1716a2d",
    )
    second = div.generate_divergence_reports(
        out_dir=tmp_path / "second" / "report",
        generated_at_utc="2026-07-14T10:01:00Z",
        source_git_commit="1716a2d",
    )
    assert first["ledger_csv"].read_bytes() == second["ledger_csv"].read_bytes()
    assert _normalized_json(first["summary_json"]) == _normalized_json(
        second["summary_json"]
    )
    assert _normalized_markdown(first["summary_markdown"]) == _normalized_markdown(
        second["summary_markdown"]
    )
    payload = json.loads(first["summary_json"].read_text(encoding="utf-8"))
    assert payload["alignment"]["shared_game_count"] == 828
    assert payload["output_artifacts"]["ledger_row_count"] == 828


def test_report_contract_contains_no_evaluation_or_superiority_claim(tmp_path: Path) -> None:
    ledger, summary = _build(_fixture_inputs(tmp_path / "inputs"))
    result = div.write_divergence_reports(
        ledger=ledger,
        summary=summary,
        out_dir=tmp_path / "report",
        generated_at_utc="2026-07-14T10:00:00Z",
    )
    payload = json.loads(result["summary_json"].read_text(encoding="utf-8"))
    markdown = result["summary_markdown"].read_text(encoding="utf-8")
    assert payload["comparison_contract"]["outcome_fields_used"] == "NONE"
    assert payload["comparison_contract"]["odds_fields_used"] == "NONE"
    assert payload["comparison_contract"]["evaluation_denominator"] == 0
    assert payload["claims"]["model_winner_declared"] is False
    assert payload["claims"]["champion_activated"] is False
    assert "not accuracy, performance" in markdown
    assert "Neither model is activated, selected, deployed, or declared superior" in markdown


def test_generation_writes_only_requested_report_root_and_time_is_metadata_only(
    tmp_path: Path,
) -> None:
    paths = _fixture_inputs(tmp_path / "inputs")
    ledger, summary = _build(paths)
    original_summary = deepcopy(summary)
    out = tmp_path / "candidate" / "report"
    div.write_divergence_reports(
        ledger=ledger,
        summary=summary,
        out_dir=out,
        generated_at_utc="2099-12-31T23:59:59Z",
    )
    assert summary == original_summary
    assert sorted(path.name for path in out.iterdir()) == [
        "mlb_2026_moneyline_shadow_divergence.csv",
        "mlb_2026_moneyline_shadow_divergence_summary.json",
        "mlb_2026_moneyline_shadow_divergence_summary.md",
    ]
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "database.db").exists()
    source = Path(div.__file__).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "urllib" not in source
    assert "sqlite3" not in source
    assert "st_mtime" not in source
    assert "getmtime" not in source
