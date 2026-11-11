"""
Tests for P33 Joined Input Skeleton Writer
"""

import csv
import json
import os

import pytest

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    REQUIRED_JOINED_INPUT_FIELDS,
    P33SourceGapSummary,
)
from wbc_backend.recommendation.p33_joined_input_skeleton_writer import (
    OUT_GAP_ROWS_CSV,
    OUT_MANIFEST,
    OUT_REQUIRED_SPEC,
    OUT_SCHEMA_CSV,
    OUT_SCHEMA_GAP,
    validate_skeleton_outputs,
    write_all_skeleton_artifacts,
    write_empty_joined_input_schema_csv,
    write_gap_rows_csv,
    write_required_spec_json,
    write_schema_gap_json,
    write_schema_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_gap_summary(pred_missing: bool = True, odds_missing: bool = True) -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=pred_missing,
        odds_missing=odds_missing,
        prediction_gap_reason="No 2024 prediction files found." if pred_missing else "",
        odds_gap_reason="No 2024 odds files found." if odds_missing else "",
    )


def _make_p32_csv(tmp_path) -> str:
    """Write a minimal P32-style identity/outcomes CSV."""
    path = tmp_path / "p32_identity_outcomes.csv"
    rows = [
        "game_id,game_date,season,away_team,home_team,away_score,home_score,y_true_home_win",
        "ANA202403280,2024-03-28,2024,HOU,LAA,3,2,0",
        "ARI202403280,2024-03-28,2024,COL,ARI,5,8,1",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# write_required_spec_json
# ---------------------------------------------------------------------------


class TestWriteRequiredSpecJson:
    def test_file_created(self, tmp_path):
        path = write_required_spec_json(str(tmp_path))
        assert os.path.isfile(path)

    def test_file_is_valid_json(self, tmp_path):
        path = write_required_spec_json(str(tmp_path))
        with open(path) as fh:
            data = json.load(fh)
        assert isinstance(data, dict)

    def test_required_fields_present(self, tmp_path):
        path = write_required_spec_json(str(tmp_path))
        with open(path) as fh:
            data = json.load(fh)
        assert data["season"] == 2024
        assert data["paper_only"] is True
        assert data["production_ready"] is False
        assert "required_fields" in data
        assert set(data["required_fields"]) == set(REQUIRED_JOINED_INPUT_FIELDS)
        assert data["field_count"] == len(REQUIRED_JOINED_INPUT_FIELDS)

    def test_file_name_correct(self, tmp_path):
        path = write_required_spec_json(str(tmp_path))
        assert os.path.basename(path) == OUT_REQUIRED_SPEC


# ---------------------------------------------------------------------------
# write_schema_gap_json
# ---------------------------------------------------------------------------


class TestWriteSchemaGapJson:
    def test_file_created_no_df(self, tmp_path):
        path = write_schema_gap_json(str(tmp_path), df=None)
        assert os.path.isfile(path)

    def test_all_missing_when_no_df(self, tmp_path):
        path = write_schema_gap_json(str(tmp_path), df=None)
        with open(path) as fh:
            data = json.load(fh)
        assert data["missing_count"] == len(REQUIRED_JOINED_INPUT_FIELDS)
        for field_val in data["field_availability"].values():
            assert field_val == "MISSING"

    def test_file_name_correct(self, tmp_path):
        path = write_schema_gap_json(str(tmp_path))
        assert os.path.basename(path) == OUT_SCHEMA_GAP

    def test_json_has_season(self, tmp_path):
        path = write_schema_gap_json(str(tmp_path))
        with open(path) as fh:
            data = json.load(fh)
        assert data["season"] == 2024


# ---------------------------------------------------------------------------
# write_empty_joined_input_schema_csv
# ---------------------------------------------------------------------------


class TestWriteEmptyJoinedInputSchemaCsv:
    def test_file_created(self, tmp_path):
        path = write_empty_joined_input_schema_csv(str(tmp_path))
        assert os.path.isfile(path)

    def test_has_correct_header(self, tmp_path):
        path = write_empty_joined_input_schema_csv(str(tmp_path))
        with open(path, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert header == REQUIRED_JOINED_INPUT_FIELDS

    def test_has_no_data_rows(self, tmp_path):
        path = write_empty_joined_input_schema_csv(str(tmp_path))
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        # Only the header line
        assert len(lines) == 1

    def test_file_name_correct(self, tmp_path):
        path = write_empty_joined_input_schema_csv(str(tmp_path))
        assert os.path.basename(path) == OUT_SCHEMA_CSV


# ---------------------------------------------------------------------------
# write_gap_rows_csv
# ---------------------------------------------------------------------------


class TestWriteGapRowsCsv:
    def test_file_created_no_identity(self, tmp_path):
        path = write_gap_rows_csv(str(tmp_path), game_identity_csv=None)
        assert os.path.isfile(path)

    def test_header_contains_required_fields(self, tmp_path):
        path = write_gap_rows_csv(str(tmp_path))
        with open(path, encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)
        assert set(header) == set(REQUIRED_JOINED_INPUT_FIELDS)

    def test_with_p32_identity_csv(self, tmp_path):
        p32_csv = _make_p32_csv(tmp_path)
        path = write_gap_rows_csv(str(tmp_path), game_identity_csv=p32_csv)
        with open(path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        # Should have 2 rows from P32 CSV
        assert len(rows) == 2

    def test_game_id_populated_from_identity(self, tmp_path):
        p32_csv = _make_p32_csv(tmp_path)
        path = write_gap_rows_csv(str(tmp_path), game_identity_csv=p32_csv)
        with open(path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        game_ids = {r["game_id"] for r in rows}
        assert "ANA202403280" in game_ids
        assert "ARI202403280" in game_ids

    def test_prediction_fields_are_null(self, tmp_path):
        p32_csv = _make_p32_csv(tmp_path)
        path = write_gap_rows_csv(str(tmp_path), game_identity_csv=p32_csv)
        with open(path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        for row in rows:
            assert row["p_model"] in ("", "None", None)
            assert row["p_oof"] in ("", "None", None)
            assert row["odds_decimal"] in ("", "None", None)

    def test_paper_only_flag_set(self, tmp_path):
        p32_csv = _make_p32_csv(tmp_path)
        path = write_gap_rows_csv(str(tmp_path), game_identity_csv=p32_csv)
        with open(path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        for row in rows:
            assert row["paper_only"] == "True"
            assert row["production_ready"] == "False"

    def test_file_name_correct(self, tmp_path):
        path = write_gap_rows_csv(str(tmp_path))
        assert os.path.basename(path) == OUT_GAP_ROWS_CSV


# ---------------------------------------------------------------------------
# write_schema_manifest
# ---------------------------------------------------------------------------


class TestWriteSchemaManifest:
    def test_file_created(self, tmp_path):
        gap = _make_gap_summary()
        path = write_schema_manifest(str(tmp_path), written_files=["a.csv", "b.json"], gap_summary=gap)
        assert os.path.isfile(path)

    def test_manifest_content(self, tmp_path):
        gap = _make_gap_summary()
        written = ["x.csv", "y.json"]
        path = write_schema_manifest(str(tmp_path), written_files=written, gap_summary=gap)
        with open(path) as fh:
            data = json.load(fh)
        assert data["season"] == 2024
        assert data["paper_only"] is True
        assert data["artifacts"] == written
        assert data["artifact_count"] == 2

    def test_gap_status_in_manifest(self, tmp_path):
        gap = _make_gap_summary(pred_missing=True, odds_missing=True)
        path = write_schema_manifest(str(tmp_path), written_files=[], gap_summary=gap)
        with open(path) as fh:
            data = json.load(fh)
        assert data["gap_status"]["prediction_missing"] is True
        assert data["gap_status"]["odds_missing"] is True

    def test_file_name_correct(self, tmp_path):
        gap = _make_gap_summary()
        path = write_schema_manifest(str(tmp_path), written_files=[], gap_summary=gap)
        assert os.path.basename(path) == OUT_MANIFEST


# ---------------------------------------------------------------------------
# write_all_skeleton_artifacts
# ---------------------------------------------------------------------------


class TestWriteAllSkeletonArtifacts:
    def test_creates_all_expected_files(self, tmp_path):
        gap = _make_gap_summary()
        out = str(tmp_path / "p33_output")
        written = write_all_skeleton_artifacts(out, gap)
        assert len(written) >= 5
        for f in written:
            assert os.path.isfile(f), f"File not created: {f}"

    def test_output_dir_created(self, tmp_path):
        gap = _make_gap_summary()
        out = str(tmp_path / "nested" / "output")
        assert not os.path.isdir(out)
        write_all_skeleton_artifacts(out, gap)
        assert os.path.isdir(out)

    def test_validate_skeleton_outputs_passes(self, tmp_path):
        gap = _make_gap_summary()
        out = str(tmp_path / "p33_output")
        write_all_skeleton_artifacts(out, gap)
        assert validate_skeleton_outputs(out) is True


# ---------------------------------------------------------------------------
# validate_skeleton_outputs
# ---------------------------------------------------------------------------


class TestValidateSkeletonOutputs:
    def test_returns_false_for_empty_dir(self, tmp_path):
        assert validate_skeleton_outputs(str(tmp_path)) is False

    def test_returns_true_after_write(self, tmp_path):
        gap = _make_gap_summary()
        out = str(tmp_path / "out")
        write_all_skeleton_artifacts(out, gap)
        assert validate_skeleton_outputs(out) is True

    def test_returns_false_if_one_file_missing(self, tmp_path):
        gap = _make_gap_summary()
        out = str(tmp_path / "out")
        write_all_skeleton_artifacts(out, gap)
        # Remove one expected file
        os.remove(os.path.join(out, OUT_SCHEMA_GAP))
        assert validate_skeleton_outputs(out) is False
