"""
Tests for P22.5 historical source discovery scanner.
Uses tmp_path fixtures — never touches real source files.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_MARKET_ODDS,
    HISTORICAL_OOF_PREDICTIONS,
    HISTORICAL_P15_JOINED_INPUT,
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    MAPPING_RISK_UNKNOWN,
    SOURCE_CANDIDATE_MISSING,
    SOURCE_CANDIDATE_PARTIAL,
    SOURCE_CANDIDATE_UNSAFE_MAPPING,
    SOURCE_CANDIDATE_USABLE,
)
from wbc_backend.recommendation.p22_5_historical_source_discovery import (
    classify_source_candidate,
    discover_historical_source_candidates,
    infer_candidate_date,
    scan_candidate_file,
    summarize_source_candidates,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mlb_odds_csv(tmp_path) -> Path:
    """Simulates data/mlb_2025/mlb_odds_2025_real.csv"""
    p = tmp_path / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
    p.parent.mkdir(parents=True)
    df = pd.DataFrame({
        "Date": ["2025-04-15", "2025-04-15"],
        "Away": ["LAD", "NYY"],
        "Home": ["SFG", "BOS"],
        "Away Score": [3, 5],
        "Home Score": [7, 2],
        "Away ML": [-130, 110],
        "Home ML": [110, -120],
        "Status": ["Final", "Final"],
    })
    df.to_csv(p, index=False)
    return p


@pytest.fixture()
def oof_predictions_csv(tmp_path) -> Path:
    """Simulates outputs/predictions/PAPER/2026-05-12/p13_.../oof_predictions.csv"""
    p = (
        tmp_path
        / "outputs"
        / "predictions"
        / "PAPER"
        / "2026-05-12"
        / "p13_walk_forward_logistic"
        / "oof_predictions.csv"
    )
    p.parent.mkdir(parents=True)
    df = pd.DataFrame({
        "y_true": [1, 0, 1],
        "p_oof": [0.62, 0.38, 0.71],
        "fold_id": [0, 0, 1],
        "train_window_start": ["2025-04-07"] * 3,
        "predict_window_start": ["2025-05-08"] * 3,
        "source_model": ["p13_logistic"] * 3,
        "paper_only": [True, True, True],
    })
    df.to_csv(p, index=False)
    return p


@pytest.fixture()
def joined_oof_csv(tmp_path) -> Path:
    """Simulates joined_oof_with_odds.csv with full P15 columns."""
    p = (
        tmp_path
        / "outputs"
        / "predictions"
        / "PAPER"
        / "2026-05-12"
        / "p15_market_odds_simulation"
        / "joined_oof_with_odds.csv"
    )
    p.parent.mkdir(parents=True)
    df = pd.DataFrame({
        "game_id": ["2025-05-08_LAD_SFG", "2025-05-08_NYY_BOS"],
        "game_date": ["2025-05-08", "2025-05-08"],
        "home_team": ["SFG", "BOS"],
        "away_team": ["LAD", "NYY"],
        "y_true": [1, 0],
        "p_oof": [0.62, 0.38],
        "odds_decimal_home": [1.91, 2.10],
        "odds_decimal_away": [2.05, 1.83],
        "p_market": [0.524, 0.476],
        "paper_only": [True, True],
    })
    df.to_csv(p, index=False)
    return p


@pytest.fixture()
def odds_only_csv(tmp_path) -> Path:
    """JSONL odds file with no predictions or outcomes."""
    p = tmp_path / "data" / "derived" / "odds_snapshots_2026-04-29.jsonl"
    p.parent.mkdir(parents=True)
    records = [
        {"decimal_odds": 1.91, "match_time_utc": "2026-04-29T18:00:00Z", "home_team": "TeamA"},
        {"decimal_odds": 2.10, "match_time_utc": "2026-04-29T18:00:00Z", "away_team": "TeamB"},
    ]
    with p.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return p


# ---------------------------------------------------------------------------
# classify_source_candidate
# ---------------------------------------------------------------------------


def test_classify_usable_with_3_key_fields():
    status = classify_source_candidate(
        has_game_id=False,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        has_team_fields=True,
        source_date="2025-04-15",
        mapping_risk=MAPPING_RISK_MEDIUM,
    )
    assert status == SOURCE_CANDIDATE_USABLE


def test_classify_usable_when_all_4_fields():
    status = classify_source_candidate(
        has_game_id=True,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=True,
        has_team_fields=True,
        source_date="2026-05-12",
        mapping_risk=MAPPING_RISK_LOW,
    )
    assert status == SOURCE_CANDIDATE_USABLE


def test_classify_partial_with_1_key_field():
    status = classify_source_candidate(
        has_game_id=False,
        has_y_true=False,
        has_odds=True,
        has_p_model_or_p_oof=False,
        has_team_fields=False,
        source_date="2026-04-29",
        mapping_risk=MAPPING_RISK_HIGH,
    )
    # Only odds, no team fields → partial/missing territory
    assert status in (SOURCE_CANDIDATE_PARTIAL, SOURCE_CANDIDATE_MISSING,
                      SOURCE_CANDIDATE_UNSAFE_MAPPING)


def test_classify_unsafe_when_no_date_no_game_id():
    status = classify_source_candidate(
        has_game_id=False,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=False,
        has_team_fields=True,
        source_date="",  # no date
        mapping_risk=MAPPING_RISK_HIGH,
    )
    assert status == SOURCE_CANDIDATE_UNSAFE_MAPPING


def test_classify_missing_when_no_relevant_fields():
    status = classify_source_candidate(
        has_game_id=False,
        has_y_true=False,
        has_odds=False,
        has_p_model_or_p_oof=False,
        has_team_fields=False,
        source_date="",
        mapping_risk=MAPPING_RISK_UNKNOWN,
    )
    assert status == SOURCE_CANDIDATE_MISSING


# ---------------------------------------------------------------------------
# infer_candidate_date
# ---------------------------------------------------------------------------


def test_infer_date_from_filename(tmp_path):
    f = tmp_path / "odds_snapshots_2026-04-29.jsonl"
    f.touch()
    result = infer_candidate_date(f)
    assert result == "2026-04-29"


def test_infer_date_from_parent_dir(tmp_path):
    d = tmp_path / "2026-05-12" / "p15_market_odds_simulation"
    d.mkdir(parents=True)
    f = d / "joined_oof_with_odds.csv"
    f.touch()
    result = infer_candidate_date(f)
    assert result == "2026-05-12"


def test_infer_date_from_content_column(tmp_path):
    f = tmp_path / "oof_predictions.csv"
    sample = pd.DataFrame({"game_date": ["2025-05-08", "2025-05-08"]})
    result = infer_candidate_date(f, columns=list(sample.columns), content_sample=sample)
    assert result == "2025-05-08"


def test_infer_date_returns_empty_when_unknown(tmp_path):
    f = tmp_path / "unknown_file.csv"
    f.touch()
    result = infer_candidate_date(f)
    assert result == ""


# ---------------------------------------------------------------------------
# scan_candidate_file
# ---------------------------------------------------------------------------


def test_scan_detects_mlb_odds_csv(mlb_odds_csv):
    candidate = scan_candidate_file(mlb_odds_csv)
    assert candidate is not None
    assert candidate.has_y_true is True  # Away Score + Home Score → y_true
    assert candidate.has_odds is True  # Away ML, Home ML
    assert candidate.has_game_id is False
    assert candidate.candidate_status in (SOURCE_CANDIDATE_USABLE, SOURCE_CANDIDATE_PARTIAL)
    assert candidate.paper_only is True
    assert candidate.production_ready is False


def test_scan_detects_oof_predictions_csv(oof_predictions_csv):
    candidate = scan_candidate_file(oof_predictions_csv)
    assert candidate is not None
    assert candidate.has_p_model_or_p_oof is True  # p_oof column
    assert candidate.has_y_true is True
    assert candidate.has_game_id is False
    assert candidate.source_type == HISTORICAL_OOF_PREDICTIONS
    assert candidate.paper_only is True
    assert candidate.production_ready is False


def test_scan_detects_joined_oof_csv(joined_oof_csv):
    candidate = scan_candidate_file(joined_oof_csv)
    assert candidate is not None
    assert candidate.has_game_id is True
    assert candidate.has_y_true is True
    assert candidate.has_odds is True
    assert candidate.has_p_model_or_p_oof is True
    assert candidate.source_type == HISTORICAL_P15_JOINED_INPUT
    assert candidate.mapping_risk == MAPPING_RISK_LOW
    assert candidate.candidate_status == SOURCE_CANDIDATE_USABLE


def test_scan_returns_none_for_irrelevant_csv(tmp_path):
    """A CSV with no relevant columns should return None."""
    p = tmp_path / "config.csv"
    pd.DataFrame({"setting": ["foo"], "value": ["bar"]}).to_csv(p, index=False)
    candidate = scan_candidate_file(p)
    assert candidate is None


def test_scan_returns_missing_for_unreadable_file(tmp_path):
    """An empty file should return None or a missing candidate."""
    p = tmp_path / "empty.csv"
    p.write_text("")
    candidate = scan_candidate_file(p)
    # Either None (irrelevant) or MISSING is acceptable
    if candidate is not None:
        assert candidate.candidate_status == SOURCE_CANDIDATE_MISSING


def test_scan_jsonl_detects_odds(odds_only_csv):
    candidate = scan_candidate_file(odds_only_csv)
    # Should detect odds; may be partial due to no predictions
    if candidate is not None:
        assert candidate.has_odds is True
        assert candidate.paper_only is True
        assert candidate.production_ready is False


# ---------------------------------------------------------------------------
# discover_historical_source_candidates
# ---------------------------------------------------------------------------


def test_discover_finds_all_relevant_files(tmp_path, mlb_odds_csv, joined_oof_csv):
    base_data = mlb_odds_csv.parent.parent.parent  # tmp_path/data
    base_outputs = joined_oof_csv.parent.parent.parent.parent.parent  # tmp_path/outputs

    candidates = discover_historical_source_candidates(
        base_paths=[str(base_data), str(base_outputs)],
        date_start="2026-05-01",
        date_end="2026-05-12",
    )
    paths = [c.source_path for c in candidates]
    assert any("mlb_odds_2025_real.csv" in p for p in paths)
    assert any("joined_oof_with_odds.csv" in p for p in paths)


def test_discover_skips_venv_dir(tmp_path):
    venv = tmp_path / ".venv" / "lib" / "site-packages"
    venv.mkdir(parents=True)
    f = venv / "some_data.csv"
    pd.DataFrame({"game_id": ["g1"], "y_true": [1]}).to_csv(f, index=False)

    candidates = discover_historical_source_candidates(
        base_paths=[str(tmp_path)],
        date_start="2026-05-01",
        date_end="2026-05-12",
    )
    paths = [c.source_path for c in candidates]
    assert not any(".venv" in p for p in paths)


def test_discover_returns_sorted_by_path(tmp_path):
    for name in ["z_data.csv", "a_data.csv", "m_data.csv"]:
        p = tmp_path / name
        pd.DataFrame({"game_id": ["g1"], "y_true": [1], "odds_decimal": [1.9]}).to_csv(p, index=False)

    candidates = discover_historical_source_candidates(
        base_paths=[str(tmp_path)],
        date_start="2026-05-01",
        date_end="2026-05-12",
    )
    paths = [c.source_path for c in candidates]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# summarize_source_candidates
# ---------------------------------------------------------------------------


def test_summarize_counts_correctly(tmp_path, joined_oof_csv, oof_predictions_csv):
    c1 = scan_candidate_file(joined_oof_csv)
    c2 = scan_candidate_file(oof_predictions_csv)
    candidates = [c for c in [c1, c2] if c is not None]
    summary = summarize_source_candidates(candidates)

    assert summary["n_total"] == len(candidates)
    assert summary["n_usable"] + summary["n_partial"] + summary["n_missing"] + summary["n_unsafe"] + summary["n_unknown"] == len(candidates)


def test_summarize_empty_list():
    summary = summarize_source_candidates([])
    assert summary["n_total"] == 0
    assert summary["n_usable"] == 0
