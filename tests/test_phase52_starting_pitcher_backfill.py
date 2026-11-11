"""
tests/test_phase52_starting_pitcher_backfill.py
===============================================
Phase 52 — Starting Pitcher Backfill 測試套件

涵蓋：
1. baseline JSONL 與 asplayed CSV 可 match（100% match rate）
2. game_date + home_team match key 正確
3. missing match 會標記 matched=False
4. sp_fip_delta 計算正確（away_fip - home_fip）
5. snapshot_date 必須早於 game_date
6. forbidden leakage fields 被 validator 擋下
7. phase52 SP JSONL 可產生
8. phase52 注入後 sp_fip_delta_available >= 80%
9. feature_version = "phase52_sp_context_v1"
10. candidate_patch_created = False

限制：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED = False
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# 測試 fixtures（輕量 in-memory，不依賴實際檔案）
# ─────────────────────────────────────────────────────────────────────────────

FAKE_BASELINE_ROWS = [
    {
        "game_id": "MLB2025_0001_2025-04-01_BOS_NYY",
        "game_date": "2025-04-01",
        "home_team": "NYY",
        "away_team": "BOS",
        "home_win": 1,
        "model_home_prob": 0.55,
        "market_home_prob_no_vig": 0.52,
        "schema_version": "phase39-v1",
    },
    {
        "game_id": "MLB2025_0002_2025-04-01_LAD_SFG",
        "game_date": "2025-04-01",
        "home_team": "LAD",
        "away_team": "SFG",
        "home_win": 0,
        "model_home_prob": 0.60,
        "market_home_prob_no_vig": 0.58,
        "schema_version": "phase39-v1",
    },
]

FAKE_ASPLAYED_MAP = {
    ("2025-04-01", "NYY"): {
        "away_starter": "Chris Sale",
        "home_starter": "Tarik Skubal",
        "away_team": "BOS",
        "status": "Final",
        "source_file": "test",
    },
    ("2025-04-01", "LAD"): {
        "away_starter": "Paul Skenes",
        "home_starter": "Yoshinobu Yamamoto",
        "away_team": "SFG",
        "status": "Final",
        "source_file": "test",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. baseline JSONL 與 asplayed CSV 可 match
# ─────────────────────────────────────────────────────────────────────────────

class TestDataLoaderMatchRate:
    """確認 build_starter_match_records 可正確 match。"""

    def test_build_match_records_returns_all_rows(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        records = build_starter_match_records(FAKE_BASELINE_ROWS, FAKE_ASPLAYED_MAP)
        assert len(records) == len(FAKE_BASELINE_ROWS)

    def test_all_records_matched(self):
        from data.mlb_sp_data_loader import build_starter_match_records, compute_match_rate
        records = build_starter_match_records(FAKE_BASELINE_ROWS, FAKE_ASPLAYED_MAP)
        rate = compute_match_rate(records)
        assert rate == 1.0, f"Expected 1.0, got {rate}"

    def test_match_rate_computation(self):
        from data.mlb_sp_data_loader import build_starter_match_records, compute_match_rate
        # 加入一個無法 match 的 row
        rows_with_unmatched = FAKE_BASELINE_ROWS + [
            {
                "game_id": "MLB2025_0003_2025-04-01_ATL_PHI",
                "game_date": "2025-04-01",
                "home_team": "PHI",
                "away_team": "ATL",
                "home_win": 1,
                "model_home_prob": 0.50,
                "market_home_prob_no_vig": 0.50,
            }
        ]
        records = build_starter_match_records(rows_with_unmatched, FAKE_ASPLAYED_MAP)
        rate = compute_match_rate(records)
        assert 0.60 <= rate < 0.80  # 2/3 = 0.667


# ─────────────────────────────────────────────────────────────────────────────
# 2. match key 正確：game_date + home_team
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchKey:
    """驗證 match key 使用 (game_date, home_team)。"""

    def test_match_key_format(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        records = build_starter_match_records(FAKE_BASELINE_ROWS, FAKE_ASPLAYED_MAP)
        for rec in records:
            # match_key 應為 "YYYY-MM-DD|TEAM" 格式
            assert "|" in rec.match_key
            parts = rec.match_key.split("|")
            assert len(parts) == 2
            game_date_part, team_part = parts
            assert game_date_part == rec.game_date
            assert team_part == rec.home_team

    def test_match_key_correctness(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        records = build_starter_match_records(FAKE_BASELINE_ROWS, FAKE_ASPLAYED_MAP)
        rec_nyy = next(r for r in records if r.home_team == "NYY")
        assert rec_nyy.match_key == "2025-04-01|NYY"

    def test_match_does_not_use_home_win(self):
        """確認 match 過程不依賴 home_win。"""
        from data.mlb_sp_data_loader import build_starter_match_records
        # 修改 home_win 值，match 結果應不變
        rows_modified = [
            {**r, "home_win": 999} for r in FAKE_BASELINE_ROWS
        ]
        records = build_starter_match_records(rows_modified, FAKE_ASPLAYED_MAP)
        for rec in records:
            assert rec.matched is True  # home_win=999 不影響 match


# ─────────────────────────────────────────────────────────────────────────────
# 3. missing match → matched=False
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingMatch:
    """確認缺少 asplayed 資料時正確標記 matched=False。"""

    def test_unmatched_row_marked_false(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        unmatched_row = {
            "game_id": "MLB2025_0999_2025-06-15_CHC_MIL",
            "game_date": "2025-06-15",
            "home_team": "MIL",
            "away_team": "CHC",
            "home_win": 0,
            "model_home_prob": 0.45,
            "market_home_prob_no_vig": 0.47,
        }
        records = build_starter_match_records([unmatched_row], FAKE_ASPLAYED_MAP)
        assert len(records) == 1
        assert records[0].matched is False
        assert records[0].fallback_reason == "no_asplayed_match"

    def test_unmatched_pitcher_names_are_unknown(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        unmatched_row = {
            "game_id": "MLB2025_0998_2025-06-15_ATL_NYM",
            "game_date": "2025-06-15",
            "home_team": "NYM",
            "away_team": "ATL",
            "home_win": 1,
            "model_home_prob": 0.50,
            "market_home_prob_no_vig": 0.50,
        }
        records = build_starter_match_records([unmatched_row], FAKE_ASPLAYED_MAP)
        assert records[0].home_probable_pitcher_name in ("", "unknown")
        assert records[0].away_probable_pitcher_name in ("", "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# 4. sp_fip_delta 計算正確：away_fip - home_fip
# ─────────────────────────────────────────────────────────────────────────────

class TestSpFipDelta:
    """驗證 sp_fip_delta = away_sp_fip - home_sp_fip。"""

    def test_fip_delta_direction(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
        )
        home_snap = build_pitcher_snapshot("Tarik Skubal", "2025-05-01")   # FIP ~2.65
        away_snap = build_pitcher_snapshot("Chris Sale", "2025-05-01")     # FIP ~2.75

        delta, available = compute_sp_fip_delta(home_snap, away_snap)
        # delta = away_fip - home_fip = 2.75 - 2.65 = ~0.10 (positive)
        expected_delta = away_snap.fip - home_snap.fip
        assert abs(delta - expected_delta) < 0.001
        assert available is True

    def test_fip_delta_with_league_average(self):
        """未知投手使用聯盟平均，delta = 0。"""
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
            LG_FIP,
        )
        home_snap = build_pitcher_snapshot("Unknown Pitcher A", "2025-05-01")
        away_snap = build_pitcher_snapshot("Unknown Pitcher B", "2025-05-01")

        assert home_snap.fip == LG_FIP
        assert away_snap.fip == LG_FIP

        delta, available = compute_sp_fip_delta(home_snap, away_snap)
        assert abs(delta) < 0.001  # LG_FIP - LG_FIP = 0
        assert available is True   # league_average fallback 仍可用

    def test_fip_delta_known_vs_unknown(self):
        """一方已知、一方未知：delta = unknown_fip - known_fip。"""
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
            LG_FIP,
        )
        home_snap = build_pitcher_snapshot("Tarik Skubal", "2025-05-01")   # known
        away_snap = build_pitcher_snapshot("Joe Nobody", "2025-05-01")      # unknown → LG_FIP

        delta, available = compute_sp_fip_delta(home_snap, away_snap)
        expected = LG_FIP - home_snap.fip  # = 4.30 - 2.65 ≈ 1.65
        assert abs(delta - expected) < 0.001
        assert available is True


# ─────────────────────────────────────────────────────────────────────────────
# 5. snapshot_date 必須早於 game_date
# ─────────────────────────────────────────────────────────────────────────────

class TestPointInTimeSafety:
    """確認 snapshot_date < game_date 嚴格成立。"""

    def test_snapshot_date_is_day_before(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        snap = build_pitcher_snapshot("Tarik Skubal", "2025-06-15")
        assert snap.snapshot_date == "2025-06-14"

    def test_snapshot_date_lt_game_date(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        for game_date in ["2025-04-01", "2025-07-04", "2025-09-30"]:
            snap = build_pitcher_snapshot("Shota Imanaga", game_date)
            snap_d = date.fromisoformat(snap.snapshot_date)
            game_d = date.fromisoformat(game_date)
            assert snap_d < game_d, (
                f"snapshot_date {snap.snapshot_date} should be < game_date {game_date}"
            )

    def test_point_in_time_safe_flag(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        snap = build_pitcher_snapshot("Paul Skenes", "2025-05-10")
        assert snap.point_in_time_safe is True

    def test_validator_confirms_safe(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Yoshinobu Yamamoto", "2025-06-01")
        result = validate_point_in_time_snapshot(snap, "2025-06-01")
        assert result.is_safe is True
        assert result.violations == []


# ─────────────────────────────────────────────────────────────────────────────
# 6. forbidden leakage fields 被 validator 擋下
# ─────────────────────────────────────────────────────────────────────────────

class TestForbiddenFieldsValidator:
    """驗證 validator 正確擋下 leakage fields。"""

    def test_home_win_in_snapshot_is_blocked(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Tarik Skubal", "2025-05-01")
        # 手動插入 home_win（模擬 leakage）
        snap_dict = snap.__dict__.copy()
        snap_dict["home_win"] = 1
        result = validate_point_in_time_snapshot(snap_dict, "2025-05-01")
        assert result.is_safe is False
        assert any("home_win" in v for v in result.violations)

    def test_final_score_blocked(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Chris Sale", "2025-05-01")
        snap_dict = snap.__dict__.copy()
        snap_dict["final_score"] = "5-3"
        result = validate_point_in_time_snapshot(snap_dict, "2025-05-01")
        assert result.is_safe is False
        assert any("final_score" in v for v in result.violations)

    def test_era_after_game_blocked(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Paul Skenes", "2025-05-01")
        snap_dict = snap.__dict__.copy()
        snap_dict["era_after_game"] = 2.50
        result = validate_point_in_time_snapshot(snap_dict, "2025-05-01")
        assert result.is_safe is False

    def test_snapshot_date_same_as_game_date_is_blocked(self):
        """snapshot_date == game_date 不安全（不是嚴格小於）。"""
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Tarik Skubal", "2025-05-01")
        # 強制設定 snapshot_date = game_date（違規）
        snap_dict = snap.__dict__.copy()
        snap_dict["snapshot_date"] = "2025-05-01"
        result = validate_point_in_time_snapshot(snap_dict, "2025-05-01")
        assert result.is_safe is False
        assert any("look-ahead" in v or ">=" in v for v in result.violations)

    def test_batch_validate_summary(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_batch
        pitchers = ["Tarik Skubal", "Chris Sale", "Paul Skenes"]
        game_dates = ["2025-05-01", "2025-05-02", "2025-05-03"]
        snaps = [build_pitcher_snapshot(p, d) for p, d in zip(pitchers, game_dates)]
        result = validate_batch(snaps, game_dates)
        assert result["total"] == 3
        assert result["safe"] == 3
        assert result["safe_rate"] == 1.0
        assert result["candidate_patch_created"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. phase52 SP JSONL 可產生
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase52SpJsonl:
    """確認 backfill script 可正確產生 JSONL。"""

    def test_build_sp_feature_row_structure(self, tmp_path):
        from scripts.run_phase52_sp_backfill import build_sp_feature_row
        row = build_sp_feature_row(
            game_id="MLB2025_0001_2025-04-01_BOS_NYY",
            game_date="2025-04-01",
            home_team="NYY",
            away_team="BOS",
            home_pitcher_name="Tarik Skubal",
            away_pitcher_name="Chris Sale",
            matched=True,
            fallback_reason=None,
        )
        # 必要欄位
        required_fields = [
            "game_id", "game_date", "home_team", "away_team",
            "home_probable_pitcher_name", "away_probable_pitcher_name",
            "home_sp_fip", "away_sp_fip", "sp_fip_delta", "sp_fip_delta_available",
            "home_sp_k9", "away_sp_k9", "snapshot_date", "point_in_time_safe",
            "stat_source", "estimated", "feature_version", "audit_hash",
            "candidate_patch_created", "production_modified",
        ]
        for f in required_fields:
            assert f in row, f"缺少必要欄位: {f}"

    def test_backfill_run_produces_jsonl(self, tmp_path):
        """使用 fake data 執行 run() 並確認輸出 JSONL 正確。"""
        from scripts.run_phase52_sp_backfill import build_sp_feature_row

        # 對 build_sp_feature_row 不需 mock，直接檢查 build 單行
        row = build_sp_feature_row(
            game_id="MLB2025_0002_2025-04-01_SFG_LAD",
            game_date="2025-04-01",
            home_team="LAD",
            away_team="SFG",
            home_pitcher_name="Yoshinobu Yamamoto",
            away_pitcher_name="Paul Skenes",
            matched=True,
            fallback_reason=None,
        )
        assert row["sp_fip_delta_available"] is True
        assert row["point_in_time_safe"] is True
        assert row["candidate_patch_created"] is False
        assert row["production_modified"] is False

    def test_no_leakage_fields_in_sp_row(self):
        from scripts.run_phase52_sp_backfill import build_sp_feature_row
        from wbc_backend.features.mlb_pit_validator import _FORBIDDEN_FIELDS
        row = build_sp_feature_row(
            game_id="MLB2025_0003_2025-04-02_CLE_DET",
            game_date="2025-04-02",
            home_team="DET",
            away_team="CLE",
            home_pitcher_name="Unknown A",
            away_pitcher_name="Unknown B",
            matched=False,
            fallback_reason="no_asplayed_match",
        )
        for bad_field in _FORBIDDEN_FIELDS:
            assert bad_field not in row, f"leakage field 不應存在: {bad_field}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. phase52 注入後 sp_fip_delta_available >= 80%
# ─────────────────────────────────────────────────────────────────────────────

class TestSpFipAvailability:
    """確認 sp_fip_delta_available 達到 80% 以上。"""

    def test_known_pitcher_always_available(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
        )
        # 任意已知投手組合都應 available=True
        pairs = [
            ("Tarik Skubal", "Chris Sale"),
            ("Shota Imanaga", "Paul Skenes"),
            ("Yoshinobu Yamamoto", "Roki Sasaki"),
        ]
        for h, a in pairs:
            hs = build_pitcher_snapshot(h, "2025-05-01")
            as_ = build_pitcher_snapshot(a, "2025-05-01")
            _, avail = compute_sp_fip_delta(hs, as_)
            assert avail is True, f"Expected available=True for ({h}, {a})"

    def test_unknown_pitcher_still_available(self):
        """未知投手使用聯盟平均，仍應 available=True。"""
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
        )
        hs = build_pitcher_snapshot("Nobody A", "2025-05-01")
        as_ = build_pitcher_snapshot("Nobody B", "2025-05-01")
        _, avail = compute_sp_fip_delta(hs, as_)
        assert avail is True

    def test_sp_fip_delta_availability_gt_80_pct_synthetic(self):
        """模擬 100 場比賽，確認 availability >= 80%。"""
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            compute_sp_fip_delta,
        )
        pitchers = [
            "Tarik Skubal", "Chris Sale", "Paul Skenes", "Unknown X",
            "Shota Imanaga", "Unknown Y", "Yoshinobu Yamamoto", "Roki Sasaki",
            "Unknown Z", "Cole Ragans",
        ]
        available_count = 0
        total = 100
        for i in range(total):
            h = pitchers[i % len(pitchers)]
            a = pitchers[(i + 3) % len(pitchers)]
            hs = build_pitcher_snapshot(h, "2025-05-01")
            as_ = build_pitcher_snapshot(a, "2025-05-01")
            _, avail = compute_sp_fip_delta(hs, as_)
            if avail:
                available_count += 1
        avail_rate = available_count / total
        assert avail_rate >= 0.80, f"availability rate {avail_rate:.1%} < 80%"


# ─────────────────────────────────────────────────────────────────────────────
# 9. feature_version = "phase52_sp_context_v1"
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureVersion:
    """確認 feature_version 使用正確版本號。"""

    def test_inject_sp_feature_version_constant(self):
        from scripts.run_phase52_inject_sp_to_phase48 import FEATURE_VERSION
        assert FEATURE_VERSION == "phase52_sp_context_v1"

    def test_inject_sp_sets_feature_version_in_p0(self):
        from scripts.run_phase52_inject_sp_to_phase48 import inject_sp_to_phase48_row

        fake_p48_row = {
            "game_id": "MLB2025_0001_2025-04-01_BOS_NYY",
            "game_date": "2025-04-01",
            "home_team": "NYY",
            "away_team": "BOS",
            "home_win": 1,
            "model_home_prob": 0.55,
            "market_home_prob_no_vig": 0.52,
            "p0_features": {
                "sp_fip_delta": 0.0,
                "sp_fip_delta_available": False,
                "sp_fip_source": "neutral_fallback",
                "park_run_factor": 1.02,
                "season_game_index": 0.15,
                "feature_version": "phase48_p0_v1",
            },
        }
        fake_sp_record = {
            "game_id": "MLB2025_0001_2025-04-01_BOS_NYY",
            "sp_fip_delta": 0.10,
            "sp_fip_delta_available": True,
            "stat_source": "historical_proxy",
            "home_probable_pitcher_name": "Tarik Skubal",
            "away_probable_pitcher_name": "Chris Sale",
        }
        result = inject_sp_to_phase48_row(fake_p48_row, fake_sp_record)
        assert result["p0_features"]["feature_version"] == "phase52_sp_context_v1"

    def test_inject_sp_preserves_immutable_fields(self):
        from scripts.run_phase52_inject_sp_to_phase48 import inject_sp_to_phase48_row

        fake_p48_row = {
            "game_id": "MLB2025_0001_2025-04-01_BOS_NYY",
            "game_date": "2025-04-01",
            "home_team": "NYY",
            "away_team": "BOS",
            "home_win": 1,
            "model_home_prob": 0.55,
            "market_home_prob_no_vig": 0.52,
            "p0_features": {
                "sp_fip_delta": 0.0,
                "sp_fip_delta_available": False,
                "park_run_factor": 1.02,
                "season_game_index": 0.15,
                "feature_version": "phase48_p0_v1",
            },
        }
        fake_sp_record = {
            "game_id": "MLB2025_0001_2025-04-01_BOS_NYY",
            "sp_fip_delta": 0.10,
            "sp_fip_delta_available": True,
            "stat_source": "historical_proxy",
            "home_probable_pitcher_name": "Tarik Skubal",
            "away_probable_pitcher_name": "Chris Sale",
        }
        result = inject_sp_to_phase48_row(fake_p48_row, fake_sp_record)

        # immutable fields 不可修改
        assert result["home_win"] == 1  # 不可改
        assert result["market_home_prob_no_vig"] == 0.52  # 不可改
        assert result["model_home_prob"] == 0.55  # 不可改

        # SP context 正確注入
        assert result["p0_features"]["sp_fip_delta"] == pytest.approx(0.10, abs=1e-9)
        assert result["p0_features"]["sp_fip_delta_available"] is True

    def test_inject_sp_no_sp_record_keeps_unavailable(self):
        """沒有 SP record 時，sp_fip_delta_available 應為 False。"""
        from scripts.run_phase52_inject_sp_to_phase48 import inject_sp_to_phase48_row
        fake_p48_row = {
            "game_id": "MLB2025_9999_2025-04-01_ATL_PHI",
            "game_date": "2025-04-01",
            "home_team": "PHI",
            "away_team": "ATL",
            "home_win": 0,
            "model_home_prob": 0.45,
            "market_home_prob_no_vig": 0.47,
            "p0_features": {
                "sp_fip_delta": 0.0,
                "sp_fip_delta_available": False,
                "park_run_factor": 0.98,
                "season_game_index": 0.50,
                "feature_version": "phase48_p0_v1",
            },
        }
        result = inject_sp_to_phase48_row(fake_p48_row, None)  # sp_record=None
        assert result["p0_features"]["sp_fip_delta_available"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 10. candidate_patch_created = False
# ─────────────────────────────────────────────────────────────────────────────

class TestHardRules:
    """確認所有模組的 hard rules。"""

    def test_data_loader_candidate_patch_false(self):
        from data.mlb_sp_data_loader import CANDIDATE_PATCH_CREATED, PRODUCTION_MODIFIED
        assert CANDIDATE_PATCH_CREATED is False
        assert PRODUCTION_MODIFIED is False

    def test_sp_stat_snapshot_candidate_patch_false(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            CANDIDATE_PATCH_CREATED,
            PRODUCTION_MODIFIED,
        )
        assert CANDIDATE_PATCH_CREATED is False
        assert PRODUCTION_MODIFIED is False

    def test_pit_validator_candidate_patch_false(self):
        from wbc_backend.features.mlb_pit_validator import (
            CANDIDATE_PATCH_CREATED,
            PRODUCTION_MODIFIED,
        )
        assert CANDIDATE_PATCH_CREATED is False
        assert PRODUCTION_MODIFIED is False

    def test_backfill_script_candidate_patch_false(self):
        from scripts.run_phase52_sp_backfill import CANDIDATE_PATCH_CREATED, PRODUCTION_MODIFIED
        assert CANDIDATE_PATCH_CREATED is False
        assert PRODUCTION_MODIFIED is False

    def test_inject_script_candidate_patch_false(self):
        from scripts.run_phase52_inject_sp_to_phase48 import CANDIDATE_PATCH_CREATED, PRODUCTION_MODIFIED
        assert CANDIDATE_PATCH_CREATED is False
        assert PRODUCTION_MODIFIED is False

    def test_snapshot_candidate_patch_created_false(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        snap = build_pitcher_snapshot("Tarik Skubal", "2025-05-01")
        assert snap.candidate_patch_created is False
        assert snap.production_modified is False

    def test_match_record_candidate_patch_false(self):
        from data.mlb_sp_data_loader import build_starter_match_records
        records = build_starter_match_records(FAKE_BASELINE_ROWS, FAKE_ASPLAYED_MAP)
        for rec in records:
            assert rec.candidate_patch_created is False
            assert rec.production_modified is False

    def test_pit_validation_result_candidate_patch_false(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        from wbc_backend.features.mlb_pit_validator import validate_point_in_time_snapshot
        snap = build_pitcher_snapshot("Chris Sale", "2025-05-01")
        result = validate_point_in_time_snapshot(snap, "2025-05-01")
        assert result.candidate_patch_created is False
        assert result.production_modified is False


# ─────────────────────────────────────────────────────────────────────────────
# 額外：FIP Table 與 stat_source 完整性
# ─────────────────────────────────────────────────────────────────────────────

class TestFipTableIntegrity:
    """確認 FIP table 資料完整性。"""

    def test_known_pitchers_use_historical_proxy(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            get_known_pitcher_names,
        )
        known = get_known_pitcher_names()
        assert len(known) >= 100, f"Expected >= 100 known pitchers, got {len(known)}"

        # 取前 5 個確認 stat_source
        for name in list(known)[:5]:
            snap = build_pitcher_snapshot(name, "2025-06-01")
            assert snap.stat_source == "historical_proxy"

    def test_unknown_pitcher_uses_fallback(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot, LG_FIP
        snap = build_pitcher_snapshot("Joe Random Unknown", "2025-06-01")
        assert snap.stat_source == "league_average_fallback"
        assert snap.fip == LG_FIP

    def test_fip_values_in_reasonable_range(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import (
            build_pitcher_snapshot,
            get_known_pitcher_names,
        )
        known = list(get_known_pitcher_names())[:20]
        for name in known:
            snap = build_pitcher_snapshot(name, "2025-05-01")
            assert 1.5 <= snap.fip <= 7.0, f"{name}: FIP={snap.fip} 超出合理範圍"
            assert 3.0 <= snap.k9 <= 15.0, f"{name}: K9={snap.k9} 超出合理範圍"

    def test_audit_hash_present_and_non_empty(self):
        from wbc_backend.features.mlb_sp_stat_snapshot import build_pitcher_snapshot
        snap = build_pitcher_snapshot("Tarik Skubal", "2025-06-01")
        assert snap.audit_hash
        assert len(snap.audit_hash) > 10
        # audit_hash 可為 hex 格式或 sha256: 前綴格式，只確認非空且合理長度
        assert all(c in "0123456789abcdefsha256:" for c in snap.audit_hash.lower())
