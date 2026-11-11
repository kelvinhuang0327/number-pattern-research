"""
P39 Tests — 2024 Holdout Dataset Build Validation
===================================================
Tests for:
  - gl2024.txt existence and parseability
  - 2023 FIP table validity and coverage
  - mlb-2024-asplayed.csv schema and content
  - sp_fip_delta feature JSONL integrity
  - PIT safety compliance
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).parent.parent
_GL2024_PATH   = _REPO / "data" / "mlb_2025" / "gl2024.txt"
_CSV_PATH      = _REPO / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
_JSONL_PATH    = _REPO / "data" / "mlb_2025" / "derived" / "mlb_2024_sp_fip_delta_features.jsonl"
_SUMMARY_PATH  = _REPO / "data" / "mlb_2025" / "derived" / "p39_2024_holdout_summary.json"


# ── Fixtures ───────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def features() -> list[dict]:
    if not _JSONL_PATH.exists():
        pytest.skip(f"{_JSONL_PATH} not found — run _p39_build_2024_holdout.py first")
    records = []
    with _JSONL_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@pytest.fixture(scope="module")
def summary() -> dict:
    if not _SUMMARY_PATH.exists():
        pytest.skip(f"{_SUMMARY_PATH} not found — run _p39_build_2024_holdout.py first")
    return json.loads(_SUMMARY_PATH.read_text(encoding="utf-8"))


# ── Test 1: gl2024.txt exists and is parseable ────────────────────────────────
class TestGl2024Exists:
    def test_file_exists(self) -> None:
        assert _GL2024_PATH.exists(), f"gl2024.txt not found at {_GL2024_PATH}"

    def test_file_is_nonempty(self) -> None:
        size = _GL2024_PATH.stat().st_size
        assert size > 100_000, f"gl2024.txt too small: {size} bytes (expect >100KB)"

    def test_row_count(self) -> None:
        """Expect 2429 rows (full 2024 MLB regular season + playoffs)."""
        with _GL2024_PATH.open("r", encoding="latin1") as fh:
            rows = [line for line in fh if line.strip()]
        assert len(rows) >= 2400, f"Too few rows: {len(rows)} (expect ~2429)"

    def test_column_count(self) -> None:
        """Verify 161-column Retrosheet format."""
        import csv
        with _GL2024_PATH.open("r", encoding="latin1", newline="") as fh:
            reader = csv.reader(fh)
            first_row = next(reader)
        assert len(first_row) >= 161, f"Expected ≥161 cols, got {len(first_row)}"

    def test_key_columns_nonempty(self) -> None:
        """Verify date, team codes, scores, starter names are non-empty in first row."""
        import csv
        with _GL2024_PATH.open("r", encoding="latin1", newline="") as fh:
            reader = csv.reader(fh)
            row = next(reader)
        assert len(row[0]) == 8,   f"Date col not 8 chars: {row[0]!r}"
        assert row[0][:4] == "2024", f"First row not 2024 season: {row[0][:4]}"
        assert len(row[3]) == 3,   f"Away team code unexpected: {row[3]!r}"
        assert len(row[6]) == 3,   f"Home team code unexpected: {row[6]!r}"
        assert row[102].strip(),   "Away starter (col 102) is empty"
        assert row[104].strip(),   "Home starter (col 104) is empty"


# ── Test 2: 2023 FIP table validity ───────────────────────────────────────────
class TestFip2023Table:
    def test_module_importable(self) -> None:
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import PITCHER_FIP_2023_CLEAN, LG_FIP_2023
        assert LG_FIP_2023 == 4.14
        assert isinstance(PITCHER_FIP_2023_CLEAN, dict)

    def test_min_pitcher_count(self) -> None:
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import PITCHER_FIP_2023_CLEAN
        n = len(PITCHER_FIP_2023_CLEAN)
        assert n >= 100, f"Too few pitchers in 2023 table: {n} (expect ≥100)"

    def test_fip_values_in_valid_range(self) -> None:
        """All FIP proxy values should be in plausible range [1.5, 6.5]."""
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import PITCHER_FIP_2023_CLEAN
        out_of_range = {
            name: stats["fip"]
            for name, stats in PITCHER_FIP_2023_CLEAN.items()
            if not (1.5 <= stats["fip"] <= 6.5)
        }
        assert not out_of_range, f"FIP values out of range: {out_of_range}"

    def test_spot_check_elite_pitchers(self) -> None:
        """Verify known elite 2023 pitchers have FIP < 3.5."""
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import get_fip_2023
        elite = ["Gerrit Cole", "Blake Snell", "Sonny Gray", "Framber Valdez",
                 "George Kirby", "Bailey Ober"]
        for name in elite:
            rec = get_fip_2023(name)
            assert rec is not None, f"Elite pitcher not in table: {name}"
            assert rec["fip"] < 3.5, (
                f"{name} FIP={rec['fip']} — expected elite pitcher to have FIP < 3.5"
            )

    def test_retrosheet_name_format(self) -> None:
        """Names should use ASCII (no diacritics) to match Retrosheet format."""
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import PITCHER_FIP_2023_CLEAN
        for name in PITCHER_FIP_2023_CLEAN:
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                pytest.fail(
                    f"Non-ASCII character in pitcher name: {name!r} "
                    "(Retrosheet uses plain ASCII)"
                )

    def test_specific_retrosheet_names(self) -> None:
        """Spot-check Retrosheet-format names (no accents)."""
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import get_fip_2023
        retrosheet_names = [
            "Jesus Luzardo",      # not "Jesús Luzardo"
            "Ranger Suarez",      # not "Ranger Suárez"
            "Cristopher Sanchez", # not "Cristópher Sánchez"
            "German Marquez",     # not "Germán Márquez"
            "Carlos Rodon",       # not "Carlos Rodón"
            "Yu Darvish",         # unchanged
            "Framber Valdez",     # unchanged
        ]
        for name in retrosheet_names:
            rec = get_fip_2023(name)
            assert rec is not None, f"Expected Retrosheet name not in table: {name!r}"

    def test_2024_rookies_not_in_table(self) -> None:
        """2024 MLB debuts should NOT be in the 2023 FIP table (correct behavior)."""
        import sys
        sys.path.insert(0, str(_REPO))
        from data.mlb_2023_pitchers import get_fip_2023
        rookies_2024 = ["Paul Skenes", "Jared Jones", "Cade Povich"]
        for name in rookies_2024:
            rec = get_fip_2023(name)
            assert rec is None, (
                f"2024 rookie {name!r} should NOT be in 2023 FIP table "
                f"(got: {rec})"
            )


# ── Test 3: mlb-2024-asplayed.csv schema ──────────────────────────────────────
class TestAsplayedCsv:
    def test_file_exists(self) -> None:
        assert _CSV_PATH.exists(), f"asplayed CSV not found: {_CSV_PATH}"

    def test_required_columns(self) -> None:
        import csv
        with _CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
        required = [
            "date", "away_team", "home_team", "away_score", "home_score",
            "away_starter", "home_starter", "home_win",
            "source_file", "source_type", "is_verified_real",
        ]
        missing = [c for c in required if c not in header]
        assert not missing, f"Missing columns in asplayed CSV: {missing}"

    def test_row_count(self) -> None:
        import csv
        with _CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) >= 2400, f"Too few rows: {len(rows)}"

    def test_date_format(self) -> None:
        """All dates should be YYYY-MM-DD and within 2024 season."""
        import csv
        with _CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        for row in rows[:100]:  # spot-check first 100
            d = row["date"]
            assert len(d) == 10 and d[4] == "-" and d[7] == "-", (
                f"Bad date format: {d!r}"
            )
            year = int(d[:4])
            assert year == 2024, f"Unexpected year {year} in 2024 asplayed CSV"

    def test_home_win_binary(self) -> None:
        """home_win should be 0.0 or 1.0."""
        import csv
        with _CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        for row in rows[:200]:
            hw = float(row["home_win"])
            assert hw in (0.0, 1.0), f"home_win not binary: {hw}"

    def test_source_type_retrosheet(self) -> None:
        import csv
        with _CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        for row in rows[:10]:
            assert row["source_type"] == "retrosheet_gamelog"
            assert row["source_file"] == "gl2024.txt"


# ── Test 4: sp_fip_delta feature JSONL ────────────────────────────────────────
class TestFeatureJsonl:
    def test_file_exists(self) -> None:
        assert _JSONL_PATH.exists(), f"Feature JSONL not found: {_JSONL_PATH}"

    def test_row_count(self, features: list[dict]) -> None:
        assert len(features) >= 2400, f"Too few feature records: {len(features)}"

    def test_required_fields(self, features: list[dict]) -> None:
        required = [
            "game_date", "home_team", "away_team",
            "home_starter", "away_starter",
            "home_fip_2023", "away_fip_2023",
            "sp_fip_delta", "sp_context_source",
            "is_strong_edge", "actual_home_win",
            "fip_data_year", "pit_safe",
        ]
        for feat in features[:50]:
            missing = [f for f in required if f not in feat]
            assert not missing, f"Missing fields in feature record: {missing}"

    def test_sp_fip_delta_arithmetic(self, features: list[dict]) -> None:
        """sp_fip_delta should equal away_fip_2023 - home_fip_2023."""
        for feat in features[:200]:
            expected = round(feat["away_fip_2023"] - feat["home_fip_2023"], 3)
            actual   = feat["sp_fip_delta"]
            assert abs(expected - actual) < 0.005, (
                f"Delta mismatch for {feat['game_date']} "
                f"{feat['away_starter']} vs {feat['home_starter']}: "
                f"expected {expected}, got {actual}"
            )

    def test_strong_edge_flag_correct(self, features: list[dict]) -> None:
        """is_strong_edge should be True iff |sp_fip_delta| >= 0.50."""
        for feat in features[:200]:
            expected = abs(feat["sp_fip_delta"]) >= 0.50
            assert feat["is_strong_edge"] == expected, (
                f"is_strong_edge mismatch: delta={feat['sp_fip_delta']}, "
                f"expected={expected}, got={feat['is_strong_edge']}"
            )

    def test_strong_edge_min_count(self, features: list[dict]) -> None:
        """At least 150 strong-edge records required for WFV analysis."""
        quality = [f for f in features if f["sp_context_source"] != "league_average_fallback"]
        strong = [f for f in quality if f["is_strong_edge"]]
        assert len(strong) >= 150, (
            f"Insufficient strong-edge records: {len(strong)} (need ≥150 for WFV)"
        )

    def test_fip_values_plausible(self, features: list[dict]) -> None:
        """FIP values should be in [1.5, 6.5] range."""
        for feat in features[:200]:
            for key in ("home_fip_2023", "away_fip_2023"):
                fip = feat[key]
                assert 1.5 <= fip <= 6.5, (
                    f"FIP out of range: {key}={fip} in {feat['game_date']}"
                )

    def test_home_win_binary(self, features: list[dict]) -> None:
        for feat in features[:200]:
            assert feat["actual_home_win"] in (0, 1)


# ── Test 5: PIT safety ─────────────────────────────────────────────────────────
class TestPitSafety:
    def test_all_records_pit_safe(self, features: list[dict]) -> None:
        violations = [f for f in features if not f.get("pit_safe")]
        assert not violations, (
            f"PIT violations detected: {len(violations)} records — "
            f"first: {violations[0] if violations else None}"
        )

    def test_fip_data_year_is_2023(self, features: list[dict]) -> None:
        for feat in features:
            assert feat.get("fip_data_year") == 2023, (
                f"fip_data_year should be 2023, got {feat.get('fip_data_year')}"
            )

    def test_game_dates_all_2024(self, features: list[dict]) -> None:
        for feat in features:
            year = int(feat["game_date"][:4])
            assert year == 2024, f"Unexpected game year: {year}"

    def test_fip_year_predates_game_year(self, features: list[dict]) -> None:
        """FIP data year (2023) must be strictly less than game year (2024)."""
        for feat in features:
            fip_year  = feat.get("fip_data_year", 9999)
            game_year = int(feat["game_date"][:4])
            assert fip_year < game_year, (
                f"PIT violation: fip_year={fip_year} >= game_year={game_year}"
            )

    def test_summary_pit_violations_zero(self, summary: dict) -> None:
        pit = summary.get("pit_audit", {})
        assert pit.get("pit_violations", 1) == 0, (
            f"PIT violations in summary: {pit.get('pit_violations')}"
        )


# ── Test 6: Summary JSON ───────────────────────────────────────────────────────
class TestSummaryJson:
    def test_summary_exists(self) -> None:
        assert _SUMMARY_PATH.exists()

    def test_classification_is_holdout_ready(self, summary: dict) -> None:
        cls = summary.get("classification", {})
        status = cls.get("classification", "")
        wfv = cls.get("wfv_viable", False)
        assert wfv, f"WFV not viable in summary: {cls}"
        assert "HOLDOUT" in status or "PARTIAL_VIABLE" in status, (
            f"Unexpected classification: {status}"
        )

    def test_governance_fields(self, summary: dict) -> None:
        gov = summary.get("governance", {})
        assert gov.get("diagnostic_only") is True
        assert gov.get("promotion_freeze") is True
        assert gov.get("t_locked") == 0.50
        assert gov.get("live_api_calls") == 0
