"""
Tests for P33 2024 Source Gap Auditor
"""

import json
import os
import tempfile

import pytest

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    SOURCE_BLOCKED_SCHEMA,
    SOURCE_MISSING,
    SOURCE_PARTIAL,
    SOURCE_READY,
)
from wbc_backend.recommendation.p33_2024_source_gap_auditor import (
    DEFAULT_SCAN_PATHS,
    _columns_intersect,
    _count_rows,
    _detect_season_from_path,
    _get_file_columns,
    _has_game_id,
    _is_dry_run,
    _path_contains_non_2024_year,
    _read_csv_columns,
    _read_json_keys,
    _read_jsonl_keys,
    classify_odds_candidate,
    classify_prediction_candidate,
    scan_all_source_candidates,
)


# ---------------------------------------------------------------------------
# Helper: temporary file factories
# ---------------------------------------------------------------------------


def _tmp_csv(tmp_path, name: str, header: str, rows: list = None) -> str:
    p = tmp_path / name
    lines = [header]
    if rows:
        lines.extend(rows)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _tmp_jsonl(tmp_path, name: str, records: list) -> str:
    p = tmp_path / name
    lines = [json.dumps(r) for r in records]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


def _tmp_json(tmp_path, name: str, obj) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Internal utility tests
# ---------------------------------------------------------------------------


class TestReadCsvColumns:
    def test_reads_header(self, tmp_path):
        f = _tmp_csv(tmp_path, "t.csv", "col_a,col_b,col_c", ["1,2,3"])
        cols = _read_csv_columns(f)
        assert cols == ("col_a", "col_b", "col_c")

    def test_missing_file_returns_empty(self):
        cols = _read_csv_columns("/nonexistent/path/file.csv")
        assert cols == ()

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("", encoding="utf-8")
        cols = _read_csv_columns(str(f))
        assert cols == ()


class TestReadJsonlKeys:
    def test_reads_first_line_keys(self, tmp_path):
        f = _tmp_jsonl(tmp_path, "t.jsonl", [{"game_id": "A", "p_model": 0.6}])
        keys = _read_jsonl_keys(str(f))
        assert "game_id" in keys
        assert "p_model" in keys

    def test_missing_file_returns_empty(self):
        assert _read_jsonl_keys("/no/such/file.jsonl") == ()


class TestReadJsonKeys:
    def test_reads_dict_keys(self, tmp_path):
        f = _tmp_json(tmp_path, "t.json", {"gate": "OK", "season": 2024})
        keys = _read_json_keys(str(f))
        assert "gate" in keys
        assert "season" in keys

    def test_reads_list_first_element_keys(self, tmp_path):
        f = _tmp_json(tmp_path, "t.json", [{"game_id": "A"}])
        keys = _read_json_keys(str(f))
        assert "game_id" in keys

    def test_missing_file_returns_empty(self):
        assert _read_json_keys("/no/such.json") == ()


class TestCountRows:
    def test_csv_excludes_header(self, tmp_path):
        f = _tmp_csv(tmp_path, "r.csv", "a,b", ["1,2", "3,4", "5,6"])
        assert _count_rows(str(f)) == 3

    def test_empty_csv(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("a,b\n", encoding="utf-8")
        assert _count_rows(str(f)) == 0


class TestPathHelpers:
    def test_detects_2025_token(self):
        assert _path_contains_non_2024_year("data/mlb_2025/odds.csv") == "2025"

    def test_detects_2026_token(self):
        assert _path_contains_non_2024_year("data/derived/dry_run_2026-04-29.jsonl") is not None

    def test_no_non_2024_token(self):
        assert _path_contains_non_2024_year("data/mlb_2024/processed/game.csv") is None

    def test_detect_season_2024(self):
        assert _detect_season_from_path("data/mlb_2024/processed/x.csv") == 2024

    def test_detect_season_2025(self):
        assert _detect_season_from_path("data/mlb_2025/mlb_odds.csv") == 2025

    def test_detect_season_none(self):
        assert _detect_season_from_path("data/misc/file.csv") is None


class TestColumnsIntersect:
    def test_found(self):
        assert _columns_intersect(("game_id", "p_model", "foo"), ["p_model", "p_oof"])

    def test_not_found(self):
        assert not _columns_intersect(("date", "team"), ["p_model", "p_oof"])

    def test_case_insensitive(self):
        assert _columns_intersect(("Game_ID", "P_Model"), ["game_id", "p_model"])


class TestHasGameId:
    def test_game_id_present(self):
        assert _has_game_id(("game_id", "p_model"))

    def test_match_id_alias(self):
        assert _has_game_id(("match_id", "odds_decimal"))

    def test_absent(self):
        assert not _has_game_id(("date", "team", "score"))


class TestIsDryRun:
    def test_path_dry_run(self):
        assert _is_dry_run("data/derived/future_model_predictions_dry_run_2026-04-29.jsonl", ())

    def test_column_dry_run(self):
        assert _is_dry_run("/some/path/file.csv", ("dry_run", "p_model"))

    def test_not_dry_run(self):
        assert not _is_dry_run("data/mlb_2024/processed/game.csv", ("game_id", "p_model"))


# ---------------------------------------------------------------------------
# Prediction candidate classification
# ---------------------------------------------------------------------------


class TestClassifyPredictionCandidate:
    def test_2025_file_blocked(self, tmp_path):
        f = _tmp_csv(tmp_path, "mlb_odds_2025.csv", "game_id,p_model,p_oof", ["g1,0.6,0.58"])
        # Move to a 2025-named path
        path_2025 = str(tmp_path / "mlb_2025" / "preds.csv")
        os.makedirs(os.path.dirname(path_2025), exist_ok=True)
        with open(path_2025, "w") as fh:
            fh.write("game_id,p_model,p_oof\ng1,0.6,0.58\n")
        cand = classify_prediction_candidate("pred_001", path_2025)
        assert cand.status == SOURCE_BLOCKED_SCHEMA
        assert "2025" in cand.blocker_reason

    def test_dry_run_file_blocked(self, tmp_path):
        path = str(tmp_path / "dry_run_preds.jsonl")
        _tmp_jsonl(tmp_path, "dry_run_preds.jsonl", [{"game_id": "g1", "p_model": 0.6, "p_oof": 0.58}])
        cand = classify_prediction_candidate("pred_002", path)
        assert cand.status == SOURCE_BLOCKED_SCHEMA
        assert "dry-run" in cand.blocker_reason.lower() or "dry_run" in cand.blocker_reason.lower()

    def test_no_game_id_blocked(self, tmp_path):
        f = _tmp_csv(tmp_path, "pred_2024.csv", "date,p_model,p_oof", ["2024-04-01,0.6,0.58"])
        cand = classify_prediction_candidate("pred_003", f)
        assert cand.status == SOURCE_BLOCKED_SCHEMA
        assert "game_id" in cand.blocker_reason

    def test_no_prediction_col_blocked(self, tmp_path):
        f = _tmp_csv(tmp_path, "game_2024.csv", "game_id,date,home,away", ["g1,2024-04-01,NYY,BOS"])
        cand = classify_prediction_candidate("pred_004", f)
        assert cand.status == SOURCE_BLOCKED_SCHEMA

    def test_partial_prediction(self, tmp_path):
        f = _tmp_csv(tmp_path, "pred_2024.csv", "game_id,p_model", ["g1,0.6"])
        cand = classify_prediction_candidate("pred_005", f)
        # Has game_id and p_model but not p_oof → SOURCE_PARTIAL
        assert cand.status == SOURCE_PARTIAL
        assert cand.has_game_id_column is True
        assert cand.has_p_model_column is True
        assert cand.has_p_oof_column is False
        # "2024" is in the filename so year is detected
        assert cand.detected_season == 2024

    def test_year_not_verified_without_2024_token(self, tmp_path):
        f = _tmp_csv(tmp_path, "predictions.csv", "game_id,p_model,p_oof", ["g1,0.6,0.58"])
        cand = classify_prediction_candidate("pred_006", f)
        assert cand.year_verified is False  # no year token in path


# ---------------------------------------------------------------------------
# Odds candidate classification
# ---------------------------------------------------------------------------


class TestClassifyOddsCandidate:
    def test_2025_file_blocked(self, tmp_path):
        path = str(tmp_path / "mlb_2025" / "odds.csv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("game_id,home_ml,away_ml\ng1,-150,+130\n")
        cand = classify_odds_candidate("odds_001", path)
        assert cand.status == SOURCE_BLOCKED_SCHEMA
        assert "2025" in cand.blocker_reason

    def test_no_game_id_blocked(self, tmp_path):
        f = _tmp_csv(tmp_path, "odds_2024.csv", "date,home_ml,away_ml", ["2024-04-01,-150,+130"])
        cand = classify_odds_candidate("odds_002", f)
        assert cand.status == SOURCE_BLOCKED_SCHEMA
        assert "game_id" in cand.blocker_reason

    def test_no_odds_col_blocked(self, tmp_path):
        f = _tmp_csv(tmp_path, "games_2024.csv", "game_id,date,home,away", ["g1,2024-04-01,NYY,BOS"])
        cand = classify_odds_candidate("odds_003", f)
        assert cand.status == SOURCE_BLOCKED_SCHEMA

    def test_partial_odds(self, tmp_path):
        f = _tmp_csv(tmp_path, "odds_2024.csv", "game_id,home_ml", ["g1,-150"])
        cand = classify_odds_candidate("odds_004", f)
        # Has game_id and moneyline but not closing_odds → SOURCE_PARTIAL
        assert cand.status == SOURCE_PARTIAL
        assert cand.has_moneyline_column is True
        assert cand.has_closing_odds_column is False

    def test_tsl_sportsbook_detection(self, tmp_path):
        f = _tmp_csv(tmp_path, "tsl_odds_2024.csv", "game_id,home_ml,away_ml", ["g1,-150,+130"])
        cand = classify_odds_candidate("odds_005", f)
        assert "TSL" in cand.sportsbook_reference or "台灣運彩" in cand.sportsbook_reference

    def test_unknown_sportsbook(self, tmp_path):
        f = _tmp_csv(tmp_path, "betting_odds_2024.csv", "game_id,home_ml", ["g1,-150"])
        cand = classify_odds_candidate("odds_006", f)
        assert cand.sportsbook_reference == "UNKNOWN"


# ---------------------------------------------------------------------------
# Full scan
# ---------------------------------------------------------------------------


class TestScanAllSourceCandidates:
    def test_empty_repo_no_candidates(self, tmp_path):
        """An empty repo root with no data dirs returns all-missing summary."""
        summary = scan_all_source_candidates(str(tmp_path), scan_paths=[])
        assert summary.prediction_missing is True
        assert summary.odds_missing is True
        assert summary.prediction_candidates_found == 0
        assert summary.odds_candidates_found == 0
        assert summary.paper_only is True
        assert summary.production_ready is False

    def test_scan_non_existent_paths(self, tmp_path):
        """Scanning paths that do not exist returns empty summary without error."""
        summary = scan_all_source_candidates(
            str(tmp_path), scan_paths=["nonexistent/path"]
        )
        assert summary.prediction_missing is True
        assert summary.odds_missing is True

    def test_2025_odds_file_classified_blocked(self, tmp_path):
        """A 2025 odds file should be found but classified as blocked."""
        d = tmp_path / "data" / "mlb_2025"
        d.mkdir(parents=True)
        (d / "mlb_odds_2025_real.csv").write_text(
            "game_id,home_ml,away_ml\ng1,-150,+130\n", encoding="utf-8"
        )
        summary = scan_all_source_candidates(
            str(tmp_path),
            scan_paths=["data/mlb_2025"],
        )
        # Should find the file as an odds candidate but it must be blocked
        assert summary.odds_candidates_found >= 1
        assert summary.odds_ready_count == 0
        assert summary.odds_missing is True

    def test_dry_run_prediction_file_classified_blocked(self, tmp_path):
        """A 2026 dry-run prediction file should be blocked."""
        d = tmp_path / "data" / "derived"
        d.mkdir(parents=True)
        records = [{"game_id": "g1", "predicted_probability": 0.6, "dry_run": True}]
        path = d / "future_model_predictions_dry_run_2026-04-29.jsonl"
        path.write_text(
            "\n".join(json.dumps(r) for r in records), encoding="utf-8"
        )
        summary = scan_all_source_candidates(
            str(tmp_path),
            scan_paths=["data/derived"],
        )
        # Dry-run files must not become ready
        assert summary.prediction_ready_count == 0
        assert summary.prediction_missing is True

    def test_summary_paper_only_flag(self, tmp_path):
        summary = scan_all_source_candidates(str(tmp_path), scan_paths=[])
        assert summary.paper_only is True

    def test_gap_reason_populated_when_missing(self, tmp_path):
        summary = scan_all_source_candidates(str(tmp_path), scan_paths=[])
        assert len(summary.prediction_gap_reason) > 0
        assert len(summary.odds_gap_reason) > 0

    def test_default_scan_paths_defined(self):
        assert len(DEFAULT_SCAN_PATHS) > 0
        assert "data/mlb_2024" in DEFAULT_SCAN_PATHS
