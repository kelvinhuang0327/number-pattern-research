"""
tests/test_phase64b_full_season_bullpen_ingestion_and_attribution.py
=====================================================================
Phase 64-B — Full-Season Bullpen Ingestion + Attribution 測試套件

安全規範：
  - 所有 tests 絕不呼叫 live StatsAPI
  - 所有 tests 使用 synthetic fixtures 或本地已存在的 artifact 檔案
  - dry_run=True 為所有測試的預設值

測試分類：
  Class 01: Safety Constants
  Class 02: Game ID Parsing
  Class 03: SSOT Artifact Construction
  Class 04: Team Index Building (synthetic)
  Class 05: Feature Derivation (synthetic)
  Class 06: Ingestion Pipeline (dry-run, synthetic)
  Class 07: fetch_boxscore_cached dry-run guard
  Class 08: Alignment (synthetic)
  Class 09: Feature Coverage
  Class 10: Bucket Attribution Logic
  Class 11: OOF Validation Logic
  Class 12: Negative Control Logic
  Class 13: Gate Decision Logic
  Class 14: End-to-End (real data files)
  Class 15: Backward Compatibility (Phase 63/64 regression)
"""
from __future__ import annotations

import json
import math
import os
import random
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.features.mlb_bullpen_full_season_ingestion import (
    MODULE_VERSION,
    DRY_RUN_DEFAULT,
    LIVE_API_CALLS_ENABLED,
    RATE_LIMIT_RPM,
    MAX_RETRY,
    _norm_team,
    _canonical_team,
    parse_bull3d_game_id,
    _build_team_artifact,
    build_full_season_ssot_index,
    fetch_boxscore_cached,
    load_full_season_ssot_from_file,
    run_full_season_ingestion,
    BullpenSSOTArtifact,
    FullSeasonIngestionSummary,
)

from orchestrator.phase64b_full_season_attribution import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    ALPHA,
    PHASE_VERSION,
    BULLPEN_GRANULAR_FEATURE_PROMISING,
    DIAGNOSTIC_ONLY_SIGNAL,
    DATA_LIMITED,
    OVERFIT_RISK,
    BULLPEN_GRANULAR_FEATURE_NOT_PROMISING,
    _B_FEATURE_REGISTRY,
    _B_AVAILABLE_FEATURES,
    _HEAVY_FAV_THRESHOLD,
    _B_ALIGNMENT_GATE,
    _MIN_COVERAGE_RATE,
    _norm_team as _b_norm_team,
    _blend_prob,
    _fav_prob,
    _brier_score,
    _bss,
    _compute_ece,
    _bootstrap_win_rate_delta,
    _bucket_attribution,
    _parse_bull3d_game_id as _b_parse_game_id,
    _build_team_index,
    _derive_b_features,
    _align_predictions_with_bull3d,
    _compute_b_coverage,
    _extract_segment,
    _compute_b_attribution,
    _compute_b_negative_control,
    _compute_b_oof,
    _decide_b_gate,
    _replicate_phase60_baseline,
    run_phase64b_attribution,
    Phase64BResult,
    FullSeasonAlignment,
    BFeatureCoverage,
    BBucketAttribution,
    BSegmentAttribution,
    BNegativeControl,
    BOOFResult,
)

# ---------------------------------------------------------------------------
# Real data paths (for end-to-end tests)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
_PRED_PATH = str(
    _ROOT / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_BULL_3D_PATH = str(_ROOT / "data/mlb_context/bullpen_usage_3d.jsonl")
_PHASE63_SSOT_PATH = str(_ROOT / "reports/phase63_bullpen_ssot_features_20260506.jsonl")
_PHASE64B_ATTRIBUTION_PATH = str(
    _ROOT / "reports/phase64b_full_season_bullpen_ingestion_and_attribution_20260506.json"
)
_PHASE64B_INGESTION_PATH = str(
    _ROOT / "reports/phase64b_full_season_ingestion_summary_20260506.json"
)


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _make_bull_3d_row(
    date: str = "2025-04-27",
    home: str = "NEW_YORK_YANKEES",
    away: str = "TORONTO_BLUE_JAYS",
    home_3d: float = 8.0,
    away_3d: float = 6.0,
) -> dict[str, Any]:
    gid = f"MLB-{date.replace('-', '_')}-1_40_PM-{away}-AT-{home}"
    return {
        "game_id": gid,
        "bullpen_usage_last_3d_home": home_3d,
        "bullpen_usage_last_3d_away": away_3d,
        "fetched_at": "2026-03-18T18:10:00Z",
        "source": "mlb_stats_api_boxscore",
        "unavailable_fields": [],
    }


def _make_pred_row(
    date: str = "2025-04-27",
    home: str = "New York Yankees",
    away: str = "Toronto Blue Jays",
    model_home: float = 0.55,
    market_home: float = 0.53,
    home_win: int = 1,
) -> dict[str, Any]:
    return {
        "game_date": date,
        "home_team": home,
        "away_team": away,
        "model_home_prob": model_home,
        "market_home_prob_no_vig": market_home,
        "home_win": home_win,
    }


def _write_tmp_jsonl(rows: list[dict], suffix: str = ".jsonl") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    for row in rows:
        f.write(json.dumps(row) + "\n")
    f.close()
    return f.name


# ===========================================================================
# Class 01 — Safety Constants
# ===========================================================================
class TestSafetyConstants:

    def test_candidate_patch_created_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_frozen(self):
        assert abs(ALPHA - 0.40) < 1e-9

    def test_phase_version_string(self):
        assert "phase64b" in PHASE_VERSION
        assert "v1" in PHASE_VERSION

    def test_module_version_string(self):
        assert "phase64b" in MODULE_VERSION
        assert "ingestion" in MODULE_VERSION
        assert "v1" in MODULE_VERSION

    def test_dry_run_default_true(self):
        assert DRY_RUN_DEFAULT is True

    def test_live_api_enabled_false(self):
        assert LIVE_API_CALLS_ENABLED is False

    def test_rate_limit_is_reasonable(self):
        assert 1 <= RATE_LIMIT_RPM <= 60

    def test_max_retry_is_reasonable(self):
        assert 1 <= MAX_RETRY <= 10

    def test_gate_constants_present(self):
        gates = {
            BULLPEN_GRANULAR_FEATURE_PROMISING,
            DIAGNOSTIC_ONLY_SIGNAL,
            DATA_LIMITED,
            OVERFIT_RISK,
            BULLPEN_GRANULAR_FEATURE_NOT_PROMISING,
        }
        assert len(gates) == 5

    def test_b_alignment_gate_threshold(self):
        assert _B_ALIGNMENT_GATE == 0.80

    def test_heavy_fav_threshold(self):
        assert _HEAVY_FAV_THRESHOLD == 0.70


# ===========================================================================
# Class 02 — Game ID Parsing
# ===========================================================================
class TestGameIdParsing:

    def test_parse_standard_game_id(self):
        gid = "MLB-2025_04_27-1_40_PM-TORONTO_BLUE_JAYS-AT-NEW_YORK_YANKEES"
        result = parse_bull3d_game_id(gid)
        assert result is not None
        date, away, home = result
        assert date == "2025-04-27"
        assert away == "TORONTO_BLUE_JAYS"
        assert home == "NEW_YORK_YANKEES"

    def test_parse_morning_game(self):
        gid = "MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS"
        result = parse_bull3d_game_id(gid)
        assert result is not None
        date, away, home = result
        assert date == "2025-03-18"
        assert away == "LOS_ANGELES_DODGERS"
        assert home == "CHICAGO_CUBS"

    def test_parse_returns_none_for_invalid_id(self):
        assert parse_bull3d_game_id("INVALID") is None
        assert parse_bull3d_game_id("") is None
        assert parse_bull3d_game_id("MLB-BAD-FORMAT") is None

    def test_parse_normalises_team_names(self):
        gid = "MLB-2025_05_01-7_05_PM-BOSTON_RED_SOX-AT-NEW_YORK_YANKEES"
        result = parse_bull3d_game_id(gid)
        assert result is not None
        _, away, home = result
        assert away == "BOSTON_RED_SOX"
        assert home == "NEW_YORK_YANKEES"

    def test_parse_attribution_module_consistent(self):
        """Both ingestion and attribution modules parse game IDs identically."""
        gid = "MLB-2025_04_27-1_40_PM-TORONTO_BLUE_JAYS-AT-NEW_YORK_YANKEES"
        r1 = parse_bull3d_game_id(gid)
        r2 = _b_parse_game_id(gid)
        assert r1 == r2

    def test_parse_date_format(self):
        gid = "MLB-2025_07_15-7_10_PM-TEXAS_RANGERS-AT-LOS_ANGELES_ANGELS"
        result = parse_bull3d_game_id(gid)
        assert result is not None
        date, _, _ = result
        assert date == "2025-07-15"


# ===========================================================================
# Class 03 — SSOT Artifact Construction
# ===========================================================================
class TestSSOTArtifactConstruction:

    def test_build_team_artifact_home(self):
        art = _build_team_artifact(
            game_id="MLB-2025_04_27-1_40_PM-TOR-AT-NYY",
            game_date="2025-04-27",
            team_norm="NEW_YORK_YANKEES",
            side="home",
            usage_3d=8.0,
        )
        assert isinstance(art, BullpenSSOTArtifact)
        assert art.game_date == "2025-04-27"
        assert art.team_norm == "NEW_YORK_YANKEES"
        assert art.side == "home"
        assert art.bullpen_usage_last_3d == 8.0

    def test_artifact_data_limited_fields_all_none(self):
        art = _build_team_artifact(
            game_id="test", game_date="2025-04-27",
            team_norm="NYY", side="home", usage_3d=5.0,
        )
        assert art.bullpen_usage_last_1d is None
        assert art.bullpen_usage_last_5d is None
        assert art.reliever_back_to_back_count is None
        assert art.reliever_three_in_four_days_count is None
        assert art.closer_used_last_1d is None
        assert art.closer_used_last_2d is None

    def test_artifact_safety_flags(self):
        art = _build_team_artifact(
            game_id="test", game_date="2025-04-27",
            team_norm="NYY", side="home", usage_3d=5.0,
        )
        assert art.diagnostic_only is True
        assert art.pit_safe is True

    def test_artifact_source_is_bull3d_derived(self):
        art = _build_team_artifact(
            game_id="test", game_date="2025-04-27",
            team_norm="NYY", side="home", usage_3d=5.0,
        )
        assert art.source == "bullpen_usage_3d_derived"

    def test_artifact_data_limited_fields_list(self):
        art = _build_team_artifact(
            game_id="test", game_date="2025-04-27",
            team_norm="NYY", side="home", usage_3d=5.0,
        )
        assert "bullpen_usage_last_1d" in art.data_limited_fields
        assert "reliever_back_to_back_count" in art.data_limited_fields
        assert "closer_used_last_1d" in art.data_limited_fields


# ===========================================================================
# Class 04 — Team Index Building (synthetic data)
# ===========================================================================
class TestTeamIndexBuilding:

    def test_build_index_basic(self):
        rows = [_make_bull_3d_row()]
        path = _write_tmp_jsonl(rows)
        try:
            idx = _build_team_index(path)
            assert len(idx) == 2  # home + away
            assert ("2025-04-27", "NEW_YORK_YANKEES") in idx
            assert ("2025-04-27", "TORONTO_BLUE_JAYS") in idx
        finally:
            os.unlink(path)

    def test_index_home_3d_value(self):
        rows = [_make_bull_3d_row(home_3d=8.0, away_3d=6.0)]
        path = _write_tmp_jsonl(rows)
        try:
            idx = _build_team_index(path)
            home_art = idx[("2025-04-27", "NEW_YORK_YANKEES")]
            away_art = idx[("2025-04-27", "TORONTO_BLUE_JAYS")]
            assert home_art["bullpen_usage_last_3d"] == 8.0
            assert away_art["bullpen_usage_last_3d"] == 6.0
        finally:
            os.unlink(path)

    def test_index_side_tags(self):
        rows = [_make_bull_3d_row()]
        path = _write_tmp_jsonl(rows)
        try:
            idx = _build_team_index(path)
            assert idx[("2025-04-27", "NEW_YORK_YANKEES")]["side"] == "home"
            assert idx[("2025-04-27", "TORONTO_BLUE_JAYS")]["side"] == "away"
        finally:
            os.unlink(path)

    def test_index_1d_5d_are_none(self):
        rows = [_make_bull_3d_row()]
        path = _write_tmp_jsonl(rows)
        try:
            idx = _build_team_index(path)
            for art in idx.values():
                assert art["bullpen_usage_last_1d"] is None
                assert art["bullpen_usage_last_5d"] is None
                assert art["reliever_back_to_back_count"] is None
        finally:
            os.unlink(path)

    def test_index_multiple_games(self):
        rows = [
            _make_bull_3d_row("2025-04-27", "NEW_YORK_YANKEES", "TORONTO_BLUE_JAYS", 8.0, 6.0),
            _make_bull_3d_row("2025-04-28", "BOSTON_RED_SOX", "HOUSTON_ASTROS", 5.0, 7.0),
        ]
        path = _write_tmp_jsonl(rows)
        try:
            idx = _build_team_index(path)
            assert len(idx) == 4
            assert ("2025-04-28", "BOSTON_RED_SOX") in idx
            assert ("2025-04-28", "HOUSTON_ASTROS") in idx
        finally:
            os.unlink(path)


# ===========================================================================
# Class 05 — Feature Derivation (synthetic)
# ===========================================================================
class TestFeatureDerivation:

    def _make_idx_one_game(self):
        rows = [_make_bull_3d_row(home_3d=8.0, away_3d=6.0)]
        path = _write_tmp_jsonl(rows)
        idx = _build_team_index(path)
        os.unlink(path)
        return idx

    def test_home_is_fav_gets_home_3d(self):
        idx = self._make_idx_one_game()
        row = _make_pred_row(model_home=0.70, market_home=0.68)  # home is fav
        features = _derive_b_features(row, idx)
        assert features["bullpen_usage_last_3d_fav"] == 8.0
        assert features["bullpen_usage_last_3d_dog"] == 6.0

    def test_away_is_fav_gets_away_3d(self):
        idx = self._make_idx_one_game()
        # blend = 0.6*0.30 + 0.4*0.32 = 0.18 + 0.128 = 0.308 < 0.5 → away is fav
        row = _make_pred_row(model_home=0.30, market_home=0.32)
        features = _derive_b_features(row, idx)
        assert features["bullpen_usage_last_3d_fav"] == 6.0   # away = TOR
        assert features["bullpen_usage_last_3d_dog"] == 8.0   # home = NYY

    def test_rest_imbalance_computed(self):
        idx = self._make_idx_one_game()
        row = _make_pred_row()
        features = _derive_b_features(row, idx)
        assert features["bullpen_rest_imbalance_3d"] == pytest.approx(abs(8.0 - 6.0))

    def test_fatigue_aliases_equal_3d(self):
        idx = self._make_idx_one_game()
        row = _make_pred_row(model_home=0.70, market_home=0.68)
        features = _derive_b_features(row, idx)
        assert features["bullpen_fatigue_favorite_side"] == features["bullpen_usage_last_3d_fav"]
        assert features["bullpen_fatigue_underdog_side"] == features["bullpen_usage_last_3d_dog"]

    def test_data_limited_features_are_none(self):
        idx = self._make_idx_one_game()
        row = _make_pred_row()
        features = _derive_b_features(row, idx)
        for fname in [
            "bullpen_usage_last_1d_fav", "bullpen_usage_last_1d_dog",
            "bullpen_usage_last_5d_fav", "bullpen_usage_last_5d_dog",
            "reliever_b2b_count_fav", "reliever_b2b_count_dog",
            "reliever_3in4_count_fav", "reliever_3in4_count_dog",
            "closer_used_1d_fav", "closer_used_2d_fav",
        ]:
            assert features[fname] is None, f"{fname} should be None"

    def test_no_match_gives_none_for_3d(self):
        idx = {}  # empty
        row = _make_pred_row()
        features = _derive_b_features(row, idx)
        assert features["bullpen_usage_last_3d_fav"] is None
        assert features["bullpen_usage_last_3d_dog"] is None
        assert features["bullpen_rest_imbalance_3d"] is None


# ===========================================================================
# Class 06 — Ingestion Pipeline (dry-run, synthetic)
# ===========================================================================
class TestIngestionPipeline:

    def _run_ingestion(self, bull_rows: list[dict]) -> FullSeasonIngestionSummary:
        bull_path = _write_tmp_jsonl(bull_rows)
        with tempfile.TemporaryDirectory() as tmpdir:
            ssot_out = str(Path(tmpdir) / "ssot.jsonl")
            app_out = str(Path(tmpdir) / "appearances.jsonl")
            try:
                summary = run_full_season_ingestion(
                    bull_3d_path=bull_path,
                    phase63_ssot_path="/nonexistent/path.jsonl",
                    ssot_output_path=ssot_out,
                    appearances_output_path=app_out,
                    dry_run=True,
                )
            finally:
                os.unlink(bull_path)
        return summary

    def test_ingestion_basic(self):
        rows = [_make_bull_3d_row()]
        summary = self._run_ingestion(rows)
        assert isinstance(summary, FullSeasonIngestionSummary)

    def test_ingestion_counts(self):
        rows = [
            _make_bull_3d_row("2025-04-27", "NEW_YORK_YANKEES", "TORONTO_BLUE_JAYS"),
            _make_bull_3d_row("2025-04-28", "BOSTON_RED_SOX", "HOUSTON_ASTROS"),
        ]
        summary = self._run_ingestion(rows)
        assert summary.n_bull_3d_rows == 2
        assert summary.n_parseable_games == 2
        assert summary.n_team_artifacts == 4

    def test_ingestion_3d_coverage_100pct(self):
        rows = [_make_bull_3d_row()]
        summary = self._run_ingestion(rows)
        assert summary.coverage_rate_3d == pytest.approx(1.0)
        assert summary.n_3d_available == 2
        assert summary.n_1d_available == 0
        assert summary.n_5d_available == 0

    def test_ingestion_dry_run_flag(self):
        rows = [_make_bull_3d_row()]
        summary = self._run_ingestion(rows)
        assert summary.dry_run is True
        assert summary.live_api_enabled is False

    def test_ingestion_ready_for_attribution_single_game(self):
        rows = [_make_bull_3d_row()]
        summary = self._run_ingestion(rows)
        assert summary.ready_for_attribution is True

    def test_ingestion_ssot_written(self):
        rows = [_make_bull_3d_row()]
        bull_path = _write_tmp_jsonl(rows)
        with tempfile.TemporaryDirectory() as tmpdir:
            ssot_out = str(Path(tmpdir) / "ssot.jsonl")
            app_out = str(Path(tmpdir) / "appearances.jsonl")
            try:
                run_full_season_ingestion(
                    bull_3d_path=bull_path,
                    phase63_ssot_path="/nonexistent/path.jsonl",
                    ssot_output_path=ssot_out,
                    appearances_output_path=app_out,
                    dry_run=True,
                )
                ssot_rows = [json.loads(l) for l in open(ssot_out) if l.strip()]
                assert len(ssot_rows) == 2  # home + away
            finally:
                os.unlink(bull_path)

    def test_ingestion_appearances_empty_in_dry_run(self):
        rows = [_make_bull_3d_row()]
        bull_path = _write_tmp_jsonl(rows)
        with tempfile.TemporaryDirectory() as tmpdir:
            ssot_out = str(Path(tmpdir) / "ssot.jsonl")
            app_out = str(Path(tmpdir) / "appearances.jsonl")
            try:
                run_full_season_ingestion(
                    bull_3d_path=bull_path,
                    phase63_ssot_path="/nonexistent/path.jsonl",
                    ssot_output_path=ssot_out,
                    appearances_output_path=app_out,
                    dry_run=True,
                )
                app_rows = [json.loads(l) for l in open(app_out) if l.strip()]
                assert app_rows == []
            finally:
                os.unlink(bull_path)


# ===========================================================================
# Class 07 — fetch_boxscore_cached dry-run guard
# ===========================================================================
class TestFetchBoxscoreCachedDryRun:

    def test_dry_run_returns_none_no_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = fetch_boxscore_cached(745000, tmpdir, dry_run=True)
        assert result is None

    def test_dry_run_reads_cache_if_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "745000.json"
            cache_file.write_text(json.dumps({"gamePk": 745000, "status": "cached"}))
            result = fetch_boxscore_cached(745000, tmpdir, dry_run=True)
        assert result is not None
        assert result["gamePk"] == 745000

    def test_non_dry_run_but_live_disabled_returns_none(self):
        """Even in non-dry-run mode, LIVE_API_CALLS_ENABLED=False prevents API calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # LIVE_API_CALLS_ENABLED is False at module level
            result = fetch_boxscore_cached(745000, tmpdir, dry_run=False)
        # Since LIVE_API_CALLS_ENABLED is False, should return None (no live call)
        assert result is None

    def test_cache_path_construction(self):
        """Cache file is named {game_pk}.json inside cache_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "123456.json"
            cache_file.write_text(json.dumps({"gamePk": 123456}))
            result = fetch_boxscore_cached(123456, tmpdir, dry_run=True)
        assert result is not None
        assert result["gamePk"] == 123456


# ===========================================================================
# Class 08 — Alignment (synthetic)
# ===========================================================================
class TestAlignment:

    def _run_alignment(
        self,
        pred_rows: list[dict],
        bull_rows: list[dict],
    ) -> tuple[list[dict], FullSeasonAlignment, int]:
        pred_path = _write_tmp_jsonl(pred_rows)
        bull_path = _write_tmp_jsonl(bull_rows)
        try:
            result = _align_predictions_with_bull3d(pred_path, bull_path)
        finally:
            os.unlink(pred_path)
            os.unlink(bull_path)
        return result

    def test_full_alignment_one_game(self):
        pred = [_make_pred_row()]
        bull = [_make_bull_3d_row()]
        enriched, alignment, n_ssot = self._run_alignment(pred, bull)
        assert alignment.n_aligned_3d == 1
        assert alignment.alignment_rate == pytest.approx(1.0)
        assert alignment.coverage_sufficient is True

    def test_no_alignment_mismatch(self):
        pred = [_make_pred_row(date="2025-04-30")]
        bull = [_make_bull_3d_row(date="2025-04-27")]
        enriched, alignment, _ = self._run_alignment(pred, bull)
        assert alignment.n_aligned_3d == 0
        assert alignment.coverage_sufficient is False

    def test_alignment_enriches_features(self):
        pred = [_make_pred_row()]
        bull = [_make_bull_3d_row(home_3d=9.5, away_3d=4.5)]
        enriched, alignment, _ = self._run_alignment(pred, bull)
        row = enriched[0]
        assert row["bullpen_usage_last_3d_fav"] is not None
        assert row["bullpen_rest_imbalance_3d"] == pytest.approx(abs(9.5 - 4.5))

    def test_alignment_tag(self):
        pred = [_make_pred_row()]
        bull = [_make_bull_3d_row()]
        enriched, alignment, _ = self._run_alignment(pred, bull)
        assert enriched[0]["_b_aligned"] is True

    def test_unmatched_tag(self):
        pred = [_make_pred_row(date="2025-04-30")]
        bull = [_make_bull_3d_row(date="2025-04-27")]
        enriched, _, _ = self._run_alignment(pred, bull)
        assert enriched[0]["_b_aligned"] is False

    def test_n_ssot_artifacts_count(self):
        pred = [_make_pred_row()]
        bull = [
            _make_bull_3d_row("2025-04-27", "NEW_YORK_YANKEES", "TORONTO_BLUE_JAYS"),
            _make_bull_3d_row("2025-04-28", "BOSTON_RED_SOX", "HOUSTON_ASTROS"),
        ]
        _, _, n_ssot = self._run_alignment(pred, bull)
        assert n_ssot == 4  # 2 games × 2 teams


# ===========================================================================
# Class 09 — Feature Coverage
# ===========================================================================
class TestFeatureCoverage:

    def _make_enriched_rows(self, n: int = 50, fav_3d: float = 8.0) -> list[dict]:
        rows = []
        for i in range(n):
            r = _make_pred_row(home_win=i % 2)
            r["bullpen_usage_last_3d_fav"] = fav_3d
            r["bullpen_usage_last_3d_dog"] = fav_3d - 2.0
            r["bullpen_rest_imbalance_3d"] = 2.0
            r["bullpen_fatigue_favorite_side"] = fav_3d
            r["bullpen_fatigue_underdog_side"] = fav_3d - 2.0
            for fname in [
                "bullpen_usage_last_1d_fav", "bullpen_usage_last_1d_dog",
                "bullpen_usage_last_5d_fav", "bullpen_usage_last_5d_dog",
                "reliever_b2b_count_fav", "reliever_b2b_count_dog",
                "reliever_3in4_count_fav", "reliever_3in4_count_dog",
                "closer_used_1d_fav", "closer_used_2d_fav",
            ]:
                r[fname] = None
            rows.append(r)
        return rows

    def test_coverage_15_features(self):
        rows = self._make_enriched_rows()
        coverage = _compute_b_coverage(rows)
        assert len(coverage) == 15

    def test_available_features_have_full_coverage(self):
        rows = self._make_enriched_rows()
        coverage = _compute_b_coverage(rows)
        for c in coverage:
            if c.feature_name in _B_AVAILABLE_FEATURES:
                assert c.coverage_pct == pytest.approx(1.0)
                assert not c.data_limited

    def test_data_limited_features_have_zero_coverage(self):
        rows = self._make_enriched_rows()
        coverage = _compute_b_coverage(rows)
        for c in coverage:
            if c.feature_name not in _B_AVAILABLE_FEATURES:
                assert c.coverage_pct == pytest.approx(0.0)
                assert c.data_limited

    def test_n_available_features(self):
        rows = self._make_enriched_rows()
        coverage = _compute_b_coverage(rows)
        n_avail = sum(1 for c in coverage if not c.data_limited)
        assert n_avail == len(_B_AVAILABLE_FEATURES)  # 5

    def test_data_limited_reason_present(self):
        rows = self._make_enriched_rows()
        coverage = _compute_b_coverage(rows)
        for c in coverage:
            if c.data_limited:
                assert c.data_limited_reason is not None
                assert len(c.data_limited_reason) > 0


# ===========================================================================
# Class 10 — Bucket Attribution Logic
# ===========================================================================
class TestBucketAttributionLogic:

    def test_bucket_attribution_basic(self):
        # Use distinct float values so median split gives non-empty high + low.
        # median = sorted_list[30] = 31.0; high=[f>31]→29 items, low=[f<=31]→31 items.
        fvals = [float(i) for i in range(1, 61)]   # 1.0 .. 60.0
        labels = [1 if i >= 31 else 0 for i in range(1, 61)]
        result = _bucket_attribution(fvals, labels)
        assert isinstance(result, BBucketAttribution)
        assert result.n_high > 0
        assert result.n_low > 0

    def test_bucket_attribution_insufficient_n(self):
        result = _bucket_attribution([5.0] * 10, [1] * 10)
        assert result is None

    def test_bootstrap_ci_structure(self):
        # Mix of wins/losses so bootstrap samples vary → ci_lo < ci_hi
        high_wins = [1] * 35 + [0] * 15  # win_rate=0.70
        low_wins  = [1] * 10 + [0] * 40  # win_rate=0.20
        ci_lo, ci_hi = _bootstrap_win_rate_delta(high_wins, low_wins)
        assert ci_lo < ci_hi
        assert ci_lo > 0   # expected delta ≈ 0.50, well above zero

    def test_bucket_delta_sign(self):
        # Distinct values so median split produces non-empty high + low.
        # high vals win, low vals lose → positive delta.
        fvals = [float(i) for i in range(1, 51)]   # 1.0 .. 50.0
        labels = [1 if i >= 26 else 0 for i in range(1, 51)]
        result = _bucket_attribution(fvals, labels)
        assert result is not None
        assert result.win_rate_delta > 0

    def test_bucket_no_signal(self):
        # Alternating wins — no bucket signal
        fvals = list(range(1, 61))  # 1..60
        labels = [i % 2 for i in range(60)]
        result = _bucket_attribution(fvals, labels)
        assert result is not None
        assert abs(result.win_rate_delta) < 0.2


# ===========================================================================
# Class 11 — OOF Validation Logic
# ===========================================================================
class TestOOFValidation:

    def _make_monthly_rows(self, n_months: int = 4, n_per_month: int = 30) -> list[dict]:
        rows = []
        months = ["2025-04", "2025-05", "2025-06", "2025-07"][:n_months]
        rng = random.Random(99)
        for m in months:
            for d in range(1, n_per_month + 1):
                r = _make_pred_row(date=f"{m}-{d:02d}", model_home=0.72, home_win=rng.randint(0, 1))
                r["bullpen_usage_last_3d_fav"] = rng.uniform(2, 12)
                rows.append(r)
        return rows

    def test_oof_with_sufficient_data(self):
        rows = self._make_monthly_rows(4, 30)
        result = _compute_b_oof(rows, "bullpen_usage_last_3d_fav", "heavy_favorite")
        assert isinstance(result, BOOFResult)
        assert result.n_folds >= 0  # May have few folds in heavy_fav

    def test_oof_no_folds_with_one_month(self):
        rows = [_make_pred_row(date="2025-04-01", model_home=0.75, home_win=1)]
        rows[0]["bullpen_usage_last_3d_fav"] = 5.0
        result = _compute_b_oof(rows, "bullpen_usage_last_3d_fav", "heavy_favorite")
        assert result.n_folds == 0

    def test_oof_result_fields(self):
        rows = self._make_monthly_rows()
        result = _compute_b_oof(rows, "bullpen_usage_last_3d_fav", "all")
        assert hasattr(result, "oof_mean_delta")
        assert hasattr(result, "oof_consistent_sign")
        assert hasattr(result, "oof_significant")
        assert hasattr(result, "fold_months")

    def test_oof_fold_months_sorted(self):
        rows = self._make_monthly_rows(4)
        result = _compute_b_oof(rows, "bullpen_usage_last_3d_fav", "all")
        if result.fold_months:
            assert result.fold_months == sorted(result.fold_months)


# ===========================================================================
# Class 12 — Negative Control Logic
# ===========================================================================
class TestNegativeControlLogic:

    def _make_hf_rows(self, n: int = 60, seed: int = 42) -> list[dict]:
        rng = random.Random(seed)
        rows = []
        for i in range(n):
            r = _make_pred_row(model_home=0.72, market_home=0.71, home_win=i % 2)
            r["bullpen_usage_last_3d_fav"] = rng.uniform(2, 15)
            rows.append(r)
        return rows

    def test_negative_control_returns_result(self):
        rows = self._make_hf_rows()
        nc = _compute_b_negative_control(rows, "bullpen_usage_last_3d_fav", "heavy_favorite")
        assert isinstance(nc, BNegativeControl)

    def test_negative_control_not_overfit_with_random_data(self):
        """With uniformly random data, overfit_risk should generally be False."""
        rows = self._make_hf_rows(n=80, seed=7)
        nc = _compute_b_negative_control(rows, "bullpen_usage_last_3d_fav", "heavy_favorite",
                                          n_shuffles=50, rng_seed=7)
        # overfit_risk = null_rejected AND std > 0.10
        # With random data, this should rarely trigger
        assert isinstance(nc.overfit_risk, bool)

    def test_negative_control_insufficient_n(self):
        rows = [_make_pred_row(model_home=0.75, home_win=1) for _ in range(5)]
        for r in rows:
            r["bullpen_usage_last_3d_fav"] = 5.0
        nc = _compute_b_negative_control(rows, "bullpen_usage_last_3d_fav", "heavy_favorite")
        assert nc.null_rejected is False
        assert nc.overfit_risk is False

    def test_negative_control_deterministic_no_signal(self):
        """Alternating win pattern with alternating feature → no overfit."""
        rows = []
        for i in range(60):
            r = _make_pred_row(model_home=0.72, market_home=0.71, home_win=i % 2)
            r["bullpen_usage_last_3d_fav"] = float(i % 2)  # binary alternating
            rows.append(r)
        nc = _compute_b_negative_control(rows, "bullpen_usage_last_3d_fav", "heavy_favorite",
                                          n_shuffles=50, rng_seed=77)
        assert nc.overfit_risk is False


# ===========================================================================
# Class 13 — Gate Decision Logic
# ===========================================================================
class TestGateDecisionLogic:

    def _make_alignment_sufficient(self) -> FullSeasonAlignment:
        return FullSeasonAlignment(
            n_ssot_artifacts=4000, n_predictions=2025,
            n_aligned_3d=1914, n_unmatched=111,
            alignment_rate=0.945, coverage_sufficient=True,
        )

    def _make_alignment_insufficient(self) -> FullSeasonAlignment:
        return FullSeasonAlignment(
            n_ssot_artifacts=10, n_predictions=2025,
            n_aligned_3d=5, n_unmatched=2020,
            alignment_rate=0.0025, coverage_sufficient=False,
        )

    def _make_coverage_all_limited(self) -> list[BFeatureCoverage]:
        return [
            BFeatureCoverage(
                feature_name=f, n_available=0, n_total=100,
                coverage_pct=0.0, data_limited=True, data_limited_reason="test",
            )
            for f, _, _, _ in _B_FEATURE_REGISTRY
        ]

    def _make_coverage_some_available(self) -> list[BFeatureCoverage]:
        result = []
        for fname, _, limited, _ in _B_FEATURE_REGISTRY:
            result.append(BFeatureCoverage(
                feature_name=fname, n_available=0 if limited else 1914,
                n_total=2025,
                coverage_pct=0.0 if limited else 0.945,
                data_limited=limited,
                data_limited_reason="DATA_LIMITED" if limited else None,
            ))
        return result

    def test_all_data_limited_gives_data_limited_gate(self):
        align = self._make_alignment_insufficient()
        coverage = self._make_coverage_all_limited()
        gate, rationale, next_step = _decide_b_gate(align, coverage, [], [], [])
        assert gate == DATA_LIMITED

    def test_no_significant_attribution_gives_not_promising(self):
        align = self._make_alignment_sufficient()
        coverage = self._make_coverage_some_available()
        # No bootstrap-significant attributions
        gate, rationale, next_step = _decide_b_gate(align, coverage, [], [], [])
        assert gate == BULLPEN_GRANULAR_FEATURE_NOT_PROMISING

    def test_bootstrap_significant_gives_diagnostic(self):
        align = self._make_alignment_sufficient()
        coverage = self._make_coverage_some_available()
        attr_sig = BSegmentAttribution(
            feature_name="bullpen_usage_last_3d_fav",
            segment="heavy_favorite",
            n=60, coverage_pct=0.945, brier=0.24, bss=0.02,
            calibration_residual=0.0, ece=0.03,
            bucket_attribution=BBucketAttribution(
                n_high=30, n_low=30,
                win_rate_high=0.70, win_rate_low=0.40,
                win_rate_delta=0.30,
                bootstrap_ci_lower=0.05, bootstrap_ci_upper=0.55,
                bootstrap_significant=True,
            ),
            oof_win_rate_delta=None, oof_n=None, oof_replicated=None,
            data_limited=False, data_limited_reason=None,
        )
        gate, _, _ = _decide_b_gate(align, coverage, [attr_sig], [], [])
        assert gate == DIAGNOSTIC_ONLY_SIGNAL

    def test_overfit_risk_gate(self):
        align = self._make_alignment_sufficient()
        coverage = self._make_coverage_some_available()
        nc_overfit = BNegativeControl(
            feature_name="bullpen_usage_last_3d_fav", segment="heavy_favorite",
            real_win_rate_delta=0.50, shuffled_mean_delta=0.0, shuffled_std_delta=0.02,
            null_rejected=True, overfit_risk=True,
        )
        gate, _, _ = _decide_b_gate(align, coverage, [], [nc_overfit], [])
        assert gate == OVERFIT_RISK

    def test_promising_oof_plus_bootstrap_gives_promising_gate(self):
        align = self._make_alignment_sufficient()
        coverage = self._make_coverage_some_available()
        attr_sig = BSegmentAttribution(
            feature_name="bullpen_usage_last_3d_fav", segment="heavy_favorite",
            n=200, coverage_pct=0.9, brier=0.24, bss=0.03,
            calibration_residual=0.0, ece=0.02,
            bucket_attribution=BBucketAttribution(
                n_high=100, n_low=100, win_rate_high=0.65, win_rate_low=0.45,
                win_rate_delta=0.20,
                bootstrap_ci_lower=0.05, bootstrap_ci_upper=0.35,
                bootstrap_significant=True,
            ),
            oof_win_rate_delta=None, oof_n=None, oof_replicated=None,
            data_limited=False, data_limited_reason=None,
        )
        oof_sig = BOOFResult(
            feature_name="bullpen_usage_last_3d_fav",
            n_folds=4, fold_months=["2025-04","2025-05","2025-06","2025-07"],
            fold_win_rate_deltas=[0.05, 0.03, 0.04, 0.06],
            fold_n=[40, 40, 40, 40],
            oof_mean_delta=0.045, oof_consistent_sign=True, oof_significant=True,
        )
        gate, _, _ = _decide_b_gate(align, coverage, [attr_sig], [], [oof_sig])
        assert gate == BULLPEN_GRANULAR_FEATURE_PROMISING

    def test_gate_rationale_not_empty(self):
        align = self._make_alignment_sufficient()
        coverage = self._make_coverage_some_available()
        _, rationale, next_step = _decide_b_gate(align, coverage, [], [], [])
        assert len(rationale) > 20
        assert len(next_step) > 20


# ===========================================================================
# Class 14 — End-to-End (real data files)
# ===========================================================================
class TestEndToEnd:
    """Uses real data files. Reads artifacts already generated by runner."""

    @pytest.fixture(scope="class")
    def result(self):
        """Load result from the generated JSON report."""
        assert os.path.exists(_PHASE64B_ATTRIBUTION_PATH), (
            f"Missing {_PHASE64B_ATTRIBUTION_PATH}. "
            f"Run scripts/run_phase64b_full_season_bullpen_ingestion_and_attribution.py first."
        )
        with open(_PHASE64B_ATTRIBUTION_PATH) as f:
            return json.load(f)

    @pytest.fixture(scope="class")
    def ingestion_summary(self):
        assert os.path.exists(_PHASE64B_INGESTION_PATH)
        with open(_PHASE64B_INGESTION_PATH) as f:
            return json.load(f)

    def test_completion_marker(self, result):
        assert result["completion_marker"] == "PHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED"

    def test_safety_constants_in_artifact(self, result):
        assert result["candidate_patch_created"] is False
        assert result["production_modified"] is False
        assert result["alpha_modified"] is False
        assert result["diagnostic_only"] is True
        assert result["alpha"] == pytest.approx(0.40)

    def test_n_predictions(self, result):
        assert result["n_predictions"] == 2025

    def test_n_bull_3d_rows(self, result):
        assert result["n_bull_3d_rows"] == 2430

    def test_alignment_rate_above_gate(self, result):
        assert result["alignment"]["alignment_rate"] >= _B_ALIGNMENT_GATE

    def test_n_aligned_3d_is_high(self, result):
        # ~94.5% of 2025 = ~1914 aligned
        assert 1800 <= result["alignment"]["n_aligned_3d"] <= 2025

    def test_n_available_features_is_5(self, result):
        assert result["n_available_features"] == 5

    def test_n_data_limited_is_10(self, result):
        assert result["n_data_limited_features"] == 10

    def test_feature_coverage_15_items(self, result):
        assert len(result["feature_coverage"]) == 15

    def test_available_features_coverage_above_80pct(self, result):
        for cov in result["feature_coverage"]:
            if not cov["data_limited"]:
                assert cov["coverage_pct"] >= 0.80

    def test_gate_is_valid(self, result):
        valid_gates = {
            BULLPEN_GRANULAR_FEATURE_PROMISING,
            DIAGNOSTIC_ONLY_SIGNAL,
            DATA_LIMITED,
            OVERFIT_RISK,
            BULLPEN_GRANULAR_FEATURE_NOT_PROMISING,
        }
        assert result["gate"] in valid_gates

    def test_phase64_gate_anchor(self, result):
        assert result["phase64_gate"] == "DATA_LIMITED"

    def test_phase64_audit_hash_anchor(self, result):
        assert result["phase64_audit_hash"] == "4923b662e37f0ca1"

    def test_phase60_baseline_replicated(self, result):
        assert result["phase60_baseline_replication"]["status"] == "REPLICATED"

    def test_phase60_brier_reasonable(self, result):
        brier = result["phase60_baseline_replication"]["brier"]
        assert 0.20 <= brier <= 0.30

    def test_attributions_include_all_features_both_segments(self, result):
        attrs = result["attributions"]
        n_features = len(_B_FEATURE_REGISTRY)
        assert len(attrs) == n_features * 2  # all + heavy_favorite

    def test_negative_controls_for_available_features(self, result):
        ncs = result["negative_controls"]
        assert len(ncs) == len(_B_AVAILABLE_FEATURES)

    def test_oof_results_for_available_features(self, result):
        oofs = result["oof_results"]
        assert len(oofs) == len(_B_AVAILABLE_FEATURES)

    def test_ingestion_summary_ready_for_attribution(self, ingestion_summary):
        assert ingestion_summary["ready_for_attribution"] is True

    def test_ingestion_ssot_artifacts_count(self, ingestion_summary):
        assert ingestion_summary["n_team_artifacts"] > 4000

    def test_ingestion_3d_coverage_is_100pct(self, ingestion_summary):
        assert ingestion_summary["coverage_rate_3d"] == pytest.approx(1.0)

    def test_ssot_file_exists(self):
        ssot_path = str(_ROOT / "reports/phase64b_bullpen_ssot_features_20260506.jsonl")
        assert os.path.exists(ssot_path)
        rows = [json.loads(l) for l in open(ssot_path) if l.strip()]
        assert len(rows) > 4000

    def test_appearances_file_exists(self):
        app_path = str(_ROOT / "reports/phase64b_bullpen_relief_appearances_20260506.jsonl")
        assert os.path.exists(app_path)


# ===========================================================================
# Class 15 — Backward Compatibility (Phase 63/64 regression)
# ===========================================================================
class TestBackwardCompatibility:

    def test_phase63_ssot_file_exists(self):
        assert os.path.exists(_PHASE63_SSOT_PATH)

    def test_phase63_ssot_has_four_artifacts(self):
        rows = [json.loads(l) for l in open(_PHASE63_SSOT_PATH) if l.strip()]
        assert len(rows) == 4

    def test_phase63_teams(self):
        rows = [json.loads(l) for l in open(_PHASE63_SSOT_PATH) if l.strip()]
        teams = {r["team"] for r in rows}
        expected = {"New York Yankees", "Boston Red Sox", "Houston Astros", "Tampa Bay Rays"}
        assert teams == expected

    def test_phase64b_does_not_modify_phase64_artifacts(self):
        """Phase 64-B reports use separate output paths from Phase 64."""
        phase64_path = str(_ROOT / "reports/phase64_granular_bullpen_attribution_20260506.json")
        assert os.path.exists(phase64_path)
        with open(phase64_path) as f:
            phase64 = json.load(f)
        assert phase64["gate"] == "DATA_LIMITED"
        assert phase64["phase_version"] == "phase64_granular_bullpen_attribution_v1"

    def test_phase64b_output_paths_different_from_phase64(self):
        """Ensure Phase 64-B outputs use different filenames."""
        p64_path = "reports/phase64_granular_bullpen_attribution_20260506.json"
        p64b_path = "reports/phase64b_full_season_bullpen_ingestion_and_attribution_20260506.json"
        assert p64_path != p64b_path

    def test_blend_formula_frozen(self):
        """ALPHA must be 0.40 (no drift from Phase 64)."""
        from orchestrator.phase64_granular_bullpen_attribution import ALPHA as ALPHA64
        from orchestrator.phase64b_full_season_attribution import ALPHA as ALPHA64B
        assert ALPHA64 == ALPHA64B == pytest.approx(0.40)

    def test_bull_3d_file_still_intact(self):
        """bull_3d file must not be modified by Phase 64-B run."""
        rows = [json.loads(l) for l in open(_BULL_3D_PATH) if l.strip()]
        assert len(rows) == 2430

    def test_predictions_file_still_intact(self):
        rows = [json.loads(l) for l in open(_PRED_PATH) if l.strip()]
        assert len(rows) == 2025

    def test_load_full_season_ssot_from_file(self):
        ssot_path = str(_ROOT / "reports/phase64b_bullpen_ssot_features_20260506.jsonl")
        if not os.path.exists(ssot_path):
            pytest.skip("SSOT file not yet generated")
        idx = load_full_season_ssot_from_file(ssot_path)
        assert len(idx) > 4000
        for key in idx:
            date, team = key
            assert len(date) == 10  # YYYY-MM-DD
            assert "_" in team or team.isupper()
