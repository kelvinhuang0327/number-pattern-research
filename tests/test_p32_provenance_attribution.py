"""
Tests for P32 Retrosheet Provenance Attribution.

Coverage:
- build_retrosheet_provenance_record returns valid record for missing file
- record has attribution_required=True
- record has no_odds_included=True, no_predictions_included=True
- RetroSheetProvenanceRecord rejects attribution_required=False
- RetroSheetProvenanceRecord rejects no_odds_included=False
- validate_retrosheet_attribution passes valid record
- provenance record production_ready=False
- write_provenance_record writes JSON with correct fields
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wbc_backend.recommendation.p32_provenance_attribution import (
    PROVENANCE_FILENAME,
    RETROSHEET_ATTRIBUTION_TEXT,
    RETROSHEET_LICENSE,
    RETROSHEET_SEASON,
    RETROSHEET_SOURCE_NAME,
    RETROSHEET_SOURCE_URL,
    RetroSheetProvenanceRecord,
    build_retrosheet_provenance_record,
    summarize_provenance,
    validate_retrosheet_attribution,
    write_provenance_record,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestProvenanceConstants:
    def test_source_name_is_retrosheet(self) -> None:
        assert RETROSHEET_SOURCE_NAME == "Retrosheet"

    def test_season_is_2024(self) -> None:
        assert RETROSHEET_SEASON == 2024

    def test_license_is_attribution_required(self) -> None:
        assert RETROSHEET_LICENSE == "ATTRIBUTION_REQUIRED"

    def test_source_url_contains_retrosheet(self) -> None:
        assert "retrosheet.org" in RETROSHEET_SOURCE_URL

    def test_attribution_text_not_empty(self) -> None:
        assert len(RETROSHEET_ATTRIBUTION_TEXT) > 0
        assert "Retrosheet" in RETROSHEET_ATTRIBUTION_TEXT


# ---------------------------------------------------------------------------
# RetroSheetProvenanceRecord dataclass
# ---------------------------------------------------------------------------


class TestRetroSheetProvenanceRecord:
    def _valid(self, **kwargs) -> RetroSheetProvenanceRecord:
        defaults = dict(
            source_name="Retrosheet",
            season=2024,
            source_url_or_reference="https://www.retrosheet.org/gamelogs/index.html",
            license_status="ATTRIBUTION_REQUIRED",
            attribution_required=True,
            attribution_text="The information used here was obtained free of charge from Retrosheet.",
            source_file_exists=False,
            source_file_mtime=None,
            downloaded_at="2024-01-01T00:00:00Z",
            source_path="/data/gl2024.txt",
            no_odds_included=True,
            no_predictions_included=True,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return RetroSheetProvenanceRecord(**defaults)

    def test_valid_record(self) -> None:
        r = self._valid()
        assert r.attribution_required is True
        assert r.no_odds_included is True
        assert r.no_predictions_included is True
        assert r.production_ready is False

    def test_rejects_attribution_required_false(self) -> None:
        with pytest.raises(ValueError, match="attribution_required"):
            self._valid(attribution_required=False)

    def test_rejects_no_odds_included_false(self) -> None:
        with pytest.raises(ValueError, match="no_odds_included"):
            self._valid(no_odds_included=False)

    def test_rejects_no_predictions_included_false(self) -> None:
        with pytest.raises(ValueError, match="no_predictions_included"):
            self._valid(no_predictions_included=False)

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_rejects_paper_only_false(self) -> None:
        with pytest.raises(ValueError, match="paper_only"):
            self._valid(paper_only=False)

    def test_to_dict_is_serializable(self) -> None:
        r = self._valid()
        d = r.to_dict()
        serialized = json.dumps(d)
        loaded = json.loads(serialized)
        assert loaded["source_name"] == "Retrosheet"
        assert loaded["attribution_required"] is True
        assert loaded["production_ready"] is False
        # Field name in dict matches dataclass
        assert "source_url_or_reference" in loaded
        assert "source_file_exists" in loaded


# ---------------------------------------------------------------------------
# build_retrosheet_provenance_record (file missing)
# ---------------------------------------------------------------------------


class TestBuildRetroSheetProvenanceRecord:
    def test_returns_record_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"  # does not exist
        record = build_retrosheet_provenance_record(path)
        assert isinstance(record, RetroSheetProvenanceRecord)
        assert record.source_file_exists is False

    def test_attribution_required_true_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"
        record = build_retrosheet_provenance_record(path)
        assert record.attribution_required is True

    def test_no_odds_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"
        record = build_retrosheet_provenance_record(path)
        assert record.no_odds_included is True

    def test_no_predictions_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"
        record = build_retrosheet_provenance_record(path)
        assert record.no_predictions_included is True

    def test_production_ready_false_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"
        record = build_retrosheet_provenance_record(path)
        assert record.production_ready is False

    def test_paper_only_true_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "gl2024.txt"
        record = build_retrosheet_provenance_record(path)
        assert record.paper_only is True

    def test_returns_record_for_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "gl2024.txt"
        f.write_text("20240401,0,Mon,BOS,AL,1,NYY,AL,1,3,5\n", encoding="latin-1")
        record = build_retrosheet_provenance_record(f)
        assert record.source_file_exists is True


# ---------------------------------------------------------------------------
# validate_retrosheet_attribution
# ---------------------------------------------------------------------------


class TestValidateRetroSheetAttribution:
    def _make_record(self, **kwargs) -> RetroSheetProvenanceRecord:
        defaults = dict(
            source_name="Retrosheet",
            season=2024,
            source_url_or_reference="https://www.retrosheet.org/gamelogs/index.html",
            license_status="ATTRIBUTION_REQUIRED",
            attribution_required=True,
            attribution_text="The information used here was obtained free of charge from Retrosheet.",
            source_file_exists=False,
            source_file_mtime=None,
            downloaded_at="2024-01-01T00:00:00Z",
            source_path="/data/gl2024.txt",
            no_odds_included=True,
            no_predictions_included=True,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return RetroSheetProvenanceRecord(**defaults)

    def test_valid_record_passes(self) -> None:
        record = self._make_record()
        ok, reason = validate_retrosheet_attribution(record)
        assert ok, reason

    def test_empty_attribution_text_fails(self) -> None:
        record = self._make_record(attribution_text="")
        ok, reason = validate_retrosheet_attribution(record)
        assert not ok
        assert "attribution_text" in reason.lower()

    def test_wrong_source_url_fails(self) -> None:
        record = self._make_record(source_url_or_reference="https://evil.com")
        ok, reason = validate_retrosheet_attribution(record)
        assert not ok


# ---------------------------------------------------------------------------
# summarize_provenance
# ---------------------------------------------------------------------------


class TestSummarizeProvenance:
    def test_returns_string(self, tmp_path: Path) -> None:
        record = build_retrosheet_provenance_record(tmp_path / "missing.txt")
        result = summarize_provenance(record)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_retrosheet(self, tmp_path: Path) -> None:
        record = build_retrosheet_provenance_record(tmp_path / "missing.txt")
        result = summarize_provenance(record)
        assert "Retrosheet" in result

    def test_contains_paper_only_marker(self, tmp_path: Path) -> None:
        record = build_retrosheet_provenance_record(tmp_path / "missing.txt")
        result = summarize_provenance(record)
        assert "PAPER" in result.upper() or "paper" in result.lower()


# ---------------------------------------------------------------------------
# write_provenance_record
# ---------------------------------------------------------------------------


class TestWriteProvenanceRecord:
    def _make_record(self, source_path: Path) -> RetroSheetProvenanceRecord:
        return build_retrosheet_provenance_record(source_path)

    def test_file_is_written(self, tmp_path: Path) -> None:
        record = self._make_record(tmp_path / "gl2024.txt")
        path = write_provenance_record(record, tmp_path)
        assert path.exists()
        assert path.name == PROVENANCE_FILENAME

    def test_written_json_is_valid(self, tmp_path: Path) -> None:
        record = self._make_record(tmp_path / "gl2024.txt")
        path = write_provenance_record(record, tmp_path)
        data = json.loads(path.read_text())
        assert data["source_name"] == "Retrosheet"
        assert data["attribution_required"] is True
        assert data["no_odds_included"] is True
        assert data["no_predictions_included"] is True
        assert data["production_ready"] is False
        assert data["paper_only"] is True
        # Verify actual field names used in to_dict()
        assert "source_url_or_reference" in data
        assert "source_file_exists" in data

    def test_written_json_has_license_status(self, tmp_path: Path) -> None:
        record = self._make_record(tmp_path / "gl2024.txt")
        path = write_provenance_record(record, tmp_path)
        data = json.loads(path.read_text())
        assert data["license_status"] == "ATTRIBUTION_REQUIRED"
