"""
Tests for Phase 48: P0 Feature Builder
=======================================
Covers:
  - Known park mapping returns correct factor + available=True
  - Unknown park returns neutral fallback 1.00 + available=False
  - season_game_index range [0.0, 1.0]
  - April index < July index
  - sp_fip_delta neutral fallback when context missing
  - sp_fip_delta correct when safe context provided
  - Forbidden leakage fields don't influence output
  - feature_audit_hash stability
  - Script produces valid JSONL
  - candidate_patch_created = False invariant
  - production_modified = False invariant
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.features.mlb_p0_feature_builder import (
    CANDIDATE_PATCH_CREATED,
    FEATURE_VERSION,
    PRODUCTION_MODIFIED,
    _FORBIDDEN_FIELDS,
    _PARK_RUN_FACTOR,
    _compute_park_run_factor,
    _compute_season_game_index,
    _compute_sp_fip_delta,
    _compute_feature_audit_hash,
    build_mlb_p0_features,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _record(
    home_team: str = "New York Yankees",
    game_date: str = "2025-06-15",
    game_id: str = "TEST_001",
) -> dict:
    return {"home_team": home_team, "game_date": game_date, "game_id": game_id}


# ═══════════════════════════════════════════════════════════════════════════════
# § A  Hard-Rule Invariants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleInvariants:
    def test_candidate_patch_created_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_result_candidate_patch_false(self):
        r = build_mlb_p0_features(_record())
        assert r["candidate_patch_created"] is False

    def test_result_production_modified_false(self):
        r = build_mlb_p0_features(_record())
        assert r["production_modified"] is False

    def test_feature_version_constant(self):
        r = build_mlb_p0_features(_record())
        assert r["feature_version"] == "phase48_p0_v1"

    def test_feature_version_matches_module_constant(self):
        r = build_mlb_p0_features(_record())
        assert r["feature_version"] == FEATURE_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# § B  Park Run Factor (F-002)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParkRunFactor:
    def test_coors_field_factor(self):
        factor, available = _compute_park_run_factor("Colorado Rockies")
        assert factor == 1.15
        assert available is True

    def test_fenway_factor(self):
        factor, available = _compute_park_run_factor("Boston Red Sox")
        assert factor == 1.08
        assert available is True

    def test_dodger_stadium_factor(self):
        factor, available = _compute_park_run_factor("Los Angeles Dodgers")
        assert factor == 0.96
        assert available is True

    def test_petco_park_factor(self):
        factor, available = _compute_park_run_factor("San Diego Padres")
        assert factor == 0.94
        assert available is True

    def test_tmobile_factor(self):
        factor, available = _compute_park_run_factor("Seattle Mariners")
        assert factor == 0.95
        assert available is True

    def test_yankee_stadium_factor(self):
        factor, available = _compute_park_run_factor("New York Yankees")
        assert factor == 1.04
        assert available is True

    def test_unknown_park_neutral_fallback(self):
        factor, available = _compute_park_run_factor("UNKNOWN TEAM XYZ")
        assert factor == 1.00
        assert available is False

    def test_empty_string_neutral_fallback(self):
        factor, available = _compute_park_run_factor("")
        assert factor == 1.00
        assert available is False

    def test_all_known_teams_in_range(self):
        for team, factor in _PARK_RUN_FACTOR.items():
            assert 0.80 <= factor <= 1.20, f"{team}: {factor} out of [0.80, 1.20]"

    def test_build_returns_park_factor_in_result(self):
        r = build_mlb_p0_features(_record(home_team="Colorado Rockies"))
        assert r["park_run_factor"] == 1.15
        assert r["park_factor_available"] is True

    def test_build_unknown_team_fallback(self):
        r = build_mlb_p0_features(_record(home_team="No Such Team"))
        assert r["park_run_factor"] == 1.00
        assert r["park_factor_available"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § C  Season Game Index (F-004)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeasonGameIndex:
    def test_early_april_low_index(self):
        idx, available = _compute_season_game_index("2025-04-01")
        assert 0.0 <= idx < 0.25
        assert available is True

    def test_mid_july_above_half(self):
        idx, available = _compute_season_game_index("2025-07-01")
        assert idx > 0.5
        assert available is True

    def test_april_less_than_july(self):
        idx_apr, _ = _compute_season_game_index("2025-04-01")
        idx_jul, _ = _compute_season_game_index("2025-07-01")
        assert idx_apr < idx_jul

    def test_before_season_start_returns_zero(self):
        idx, available = _compute_season_game_index("2025-02-15")
        assert idx == 0.0
        assert available is True

    def test_at_season_start_returns_zero(self):
        idx, available = _compute_season_game_index("2025-03-01")
        assert idx == 0.0
        assert available is True

    def test_after_season_end_returns_one(self):
        idx, available = _compute_season_game_index("2025-10-15")
        assert idx == 1.0
        assert available is True

    def test_at_season_end_returns_one(self):
        idx, available = _compute_season_game_index("2025-10-01")
        assert idx == 1.0
        assert available is True

    def test_always_in_zero_to_one(self):
        dates = ["2025-01-01", "2025-04-01", "2025-07-04", "2025-09-30", "2025-12-01"]
        for d in dates:
            idx, _ = _compute_season_game_index(d)
            assert 0.0 <= idx <= 1.0, f"{d}: {idx}"

    def test_invalid_date_fallback(self):
        idx, available = _compute_season_game_index("NOT-A-DATE")
        assert idx == 0.0
        assert available is False

    def test_empty_date_fallback(self):
        idx, available = _compute_season_game_index("")
        assert idx == 0.0
        assert available is False

    def test_build_season_index_in_result(self):
        r = build_mlb_p0_features(_record(game_date="2025-04-01"))
        assert 0.0 <= r["season_game_index"] <= 1.0
        assert r["season_game_index_available"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § D  SP FIP Delta (F-001)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSPFipDelta:
    def test_no_context_neutral_fallback(self):
        delta, available = _compute_sp_fip_delta({})
        assert delta == 0.0
        assert available is False

    def test_missing_home_fip_fallback(self):
        delta, available = _compute_sp_fip_delta({"away_sp_fip": 3.50})
        assert delta == 0.0
        assert available is False

    def test_missing_away_fip_fallback(self):
        delta, available = _compute_sp_fip_delta({"home_sp_fip": 3.20})
        assert delta == 0.0
        assert available is False

    def test_correct_delta_home_better(self):
        # away_fip - home_fip = 4.50 - 2.80 = +1.70 (home better)
        delta, available = _compute_sp_fip_delta({"home_sp_fip": 2.80, "away_sp_fip": 4.50})
        assert abs(delta - 1.70) < 1e-5
        assert available is True

    def test_correct_delta_away_better(self):
        # away_fip - home_fip = 2.50 - 4.00 = -1.50 (away better)
        delta, available = _compute_sp_fip_delta({"home_sp_fip": 4.00, "away_sp_fip": 2.50})
        assert abs(delta - (-1.50)) < 1e-5
        assert available is True

    def test_equal_fip_zero_delta(self):
        delta, available = _compute_sp_fip_delta({"home_sp_fip": 3.50, "away_sp_fip": 3.50})
        assert delta == 0.0
        assert available is True

    def test_out_of_range_fip_fallback(self):
        # FIP > 15.0 is implausible
        delta, available = _compute_sp_fip_delta({"home_sp_fip": 99.0, "away_sp_fip": 3.50})
        assert delta == 0.0
        assert available is False

    def test_build_with_context_sp_fip(self):
        r = build_mlb_p0_features(
            _record(),
            context={"home_sp_fip": 3.00, "away_sp_fip": 4.50},
        )
        assert abs(r["sp_fip_delta"] - 1.50) < 1e-5
        assert r["sp_fip_delta_available"] is True

    def test_build_no_context_neutral(self):
        r = build_mlb_p0_features(_record(), context=None)
        assert r["sp_fip_delta"] == 0.0
        assert r["sp_fip_delta_available"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § E  Leakage Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeakageGuard:
    def test_forbidden_fields_defined(self):
        for f in ("home_win", "final_score", "home_score", "away_score",
                  "result", "closing_odds_after_game", "post_game_stats"):
            assert f in _FORBIDDEN_FIELDS

    def test_home_win_in_record_does_not_affect_output(self):
        # With forbidden field
        r_with = build_mlb_p0_features(
            {**_record(), "home_win": 1},
        )
        # Without forbidden field
        r_without = build_mlb_p0_features(_record())
        # Feature values must be identical
        assert r_with["sp_fip_delta"]        == r_without["sp_fip_delta"]
        assert r_with["park_run_factor"]     == r_without["park_run_factor"]
        assert r_with["season_game_index"]   == r_without["season_game_index"]
        assert r_with["feature_audit_hash"]  == r_without["feature_audit_hash"]

    def test_final_score_in_record_does_not_affect_output(self):
        r_with    = build_mlb_p0_features({**_record(), "final_score": "5-3"})
        r_without = build_mlb_p0_features(_record())
        assert r_with["feature_audit_hash"] == r_without["feature_audit_hash"]

    def test_forbidden_fields_logged_in_audit_notes(self):
        r = build_mlb_p0_features({**_record(), "home_win": 0, "home_score": 3})
        ignored = r["audit_notes"]["ignored_forbidden_fields"]
        assert "home_win" in ignored
        assert "home_score" in ignored

    def test_context_forbidden_fields_also_stripped(self):
        r_with = build_mlb_p0_features(
            _record(),
            context={"home_sp_fip": 3.0, "away_sp_fip": 4.0, "result": "WIN"},
        )
        # result is forbidden → stripped; FIP context should still work
        assert r_with["sp_fip_delta_available"] is True
        assert "result" in r_with["audit_notes"]["ignored_forbidden_fields"]

    def test_no_forbidden_fields_empty_ignored_list(self):
        r = build_mlb_p0_features(_record())
        assert r["audit_notes"]["ignored_forbidden_fields"] == []

    def test_post_game_stats_in_context_stripped(self):
        r = build_mlb_p0_features(
            _record(),
            context={"post_game_stats": {"home_era": 2.5}},
        )
        assert "post_game_stats" in r["audit_notes"]["ignored_forbidden_fields"]


# ═══════════════════════════════════════════════════════════════════════════════
# § F  Audit Hash Stability
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditHash:
    def test_hash_is_64_hex_chars(self):
        r = build_mlb_p0_features(_record())
        assert len(r["feature_audit_hash"]) == 64
        int(r["feature_audit_hash"], 16)  # raises if not valid hex

    def test_hash_stable_across_calls(self):
        rec = _record()
        h1 = build_mlb_p0_features(rec)["feature_audit_hash"]
        h2 = build_mlb_p0_features(rec)["feature_audit_hash"]
        assert h1 == h2

    def test_hash_differs_for_different_park(self):
        r_coors   = build_mlb_p0_features(_record(home_team="Colorado Rockies",   game_id="X"))
        r_dodgers = build_mlb_p0_features(_record(home_team="Los Angeles Dodgers", game_id="X"))
        assert r_coors["feature_audit_hash"] != r_dodgers["feature_audit_hash"]

    def test_hash_differs_for_different_date(self):
        r_apr = build_mlb_p0_features(_record(game_date="2025-04-01", game_id="Y"))
        r_sep = build_mlb_p0_features(_record(game_date="2025-09-01", game_id="Y"))
        assert r_apr["feature_audit_hash"] != r_sep["feature_audit_hash"]

    def test_hash_differs_with_sp_fip_context(self):
        r_no_ctx = build_mlb_p0_features(_record(game_id="Z"), context=None)
        r_ctx    = build_mlb_p0_features(
            _record(game_id="Z"),
            context={"home_sp_fip": 3.0, "away_sp_fip": 4.5},
        )
        assert r_no_ctx["feature_audit_hash"] != r_ctx["feature_audit_hash"]

    def test_compute_feature_audit_hash_direct(self):
        h = _compute_feature_audit_hash(
            game_id="T001",
            sp_fip_delta=1.5,
            park_run_factor=1.15,
            season_game_index=0.25,
            feature_version="phase48_p0_v1",
        )
        assert len(h) == 64


# ═══════════════════════════════════════════════════════════════════════════════
# § G  Full build_mlb_p0_features API
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildMlbP0Features:
    def test_returns_dict(self):
        r = build_mlb_p0_features(_record())
        assert isinstance(r, dict)

    def test_required_keys_present(self):
        r = build_mlb_p0_features(_record())
        for key in (
            "feature_version", "candidate_patch_created", "production_modified",
            "sp_fip_delta", "sp_fip_delta_available",
            "park_run_factor", "park_factor_available",
            "season_game_index", "season_game_index_available",
            "feature_audit_hash", "audit_notes",
        ):
            assert key in r, f"Missing key: {key}"

    def test_audit_notes_structure(self):
        r = build_mlb_p0_features(_record())
        an = r["audit_notes"]
        assert "ignored_forbidden_fields" in an
        assert "sp_fip_source" in an
        assert "park_factor_source" in an
        assert "season_index_source" in an

    def test_sp_fip_source_neutral_fallback_label(self):
        r = build_mlb_p0_features(_record())
        assert r["audit_notes"]["sp_fip_source"] == "neutral_fallback"

    def test_sp_fip_source_context_label(self):
        r = build_mlb_p0_features(
            _record(),
            context={"home_sp_fip": 3.0, "away_sp_fip": 4.0},
        )
        assert r["audit_notes"]["sp_fip_source"] == "context"

    def test_park_factor_source_lookup_label(self):
        r = build_mlb_p0_features(_record(home_team="Colorado Rockies"))
        assert r["audit_notes"]["park_factor_source"] == "lookup_table"

    def test_park_factor_source_fallback_label(self):
        r = build_mlb_p0_features(_record(home_team="UNKNOWN"))
        assert r["audit_notes"]["park_factor_source"] == "neutral_fallback"

    def test_empty_record_does_not_raise(self):
        # Should not raise; should return neutral values
        r = build_mlb_p0_features({})
        assert r["park_run_factor"] == 1.00
        assert r["sp_fip_delta"]   == 0.0

    def test_none_context_is_safe(self):
        r = build_mlb_p0_features(_record(), context=None)
        assert r["sp_fip_delta"] == 0.0

    def test_empty_context_is_safe(self):
        r = build_mlb_p0_features(_record(), context={})
        assert r["sp_fip_delta"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § H  Script Integration (run_phase48_p0_feature_builder)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScriptIntegration:
    def _write_minimal_jsonl(self, path: Path, rows: list[dict]) -> None:
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def _make_row(self, idx: int = 0) -> dict:
        return {
            "schema_version": "phase39-v1",
            "season": 2025,
            "game_date": f"2025-06-{15 + idx:02d}",
            "game_id": f"TEST_{idx:04d}",
            "home_team": "Colorado Rockies",
            "away_team": "Los Angeles Dodgers",
            "home_win": 1,
            "model_home_prob": 0.60,
            "market_home_prob_no_vig": 0.55,
            "market_away_prob_no_vig": 0.45,
        }

    def test_script_produces_jsonl(self):
        from scripts.run_phase48_p0_feature_builder import run

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row(i) for i in range(5)])
            summary = run(inp, out)

            assert out.exists()
            lines = out.read_text().splitlines()
            assert len(lines) == 5

    def test_script_output_contains_p0_features(self):
        from scripts.run_phase48_p0_feature_builder import run

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row()])
            run(inp, out)

            row = json.loads(out.read_text().splitlines()[0])
            assert "p0_features" in row
            assert "feature_version" in row
            assert "feature_audit_hash" in row

    def test_script_row_count_matches(self):
        from scripts.run_phase48_p0_feature_builder import run

        n = 12
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row(i) for i in range(n)])
            summary = run(inp, out)
            assert summary["rows_written"] == n

    def test_script_park_availability_rate_correct(self):
        from scripts.run_phase48_p0_feature_builder import run

        # Colorado Rockies → known park
        rows = [self._make_row(i) for i in range(4)]
        # Add one unknown team
        unknown = {**self._make_row(99), "home_team": "UNKNOWN TEAM"}
        rows.append(unknown)

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, rows)
            summary = run(inp, out)
            # 4 known / 5 total = 0.8
            assert abs(summary["park_availability_rate"] - 0.80) < 1e-3

    def test_script_candidate_patch_false_in_summary(self):
        from scripts.run_phase48_p0_feature_builder import run

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row()])
            summary = run(inp, out)
            assert summary["candidate_patch_created"] is False

    def test_script_production_modified_false_in_summary(self):
        from scripts.run_phase48_p0_feature_builder import run

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row()])
            summary = run(inp, out)
            assert summary["production_modified"] is False

    def test_script_preserves_original_fields(self):
        from scripts.run_phase48_p0_feature_builder import run

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.jsonl"
            out = Path(tmp) / "output.jsonl"
            self._write_minimal_jsonl(inp, [self._make_row()])
            run(inp, out)

            row = json.loads(out.read_text().splitlines()[0])
            assert row["game_id"] == "TEST_0000"
            assert row["model_home_prob"] == 0.60
            assert row["market_home_prob_no_vig"] == 0.55
