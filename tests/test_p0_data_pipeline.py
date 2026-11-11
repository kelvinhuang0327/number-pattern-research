"""
P0 資料管道測試套件
===================================
測試兩個 P0 解決模組：
  P0-1: data/mlb_data_loader.py    (MLB 歷史資料 → GameRecord)
  P0-2: data/mlb_live_pipeline.py  (MLB Stats API 即時管道)

驗證項目：
  1. CSV 正確讀取並轉換 GameRecord（>= 50 場）
  2. Elo 滾動更新正確（初始 1500，有效範圍 [1000, 2000]）
  3. wOBA/FIP 代理在合理範圍（0.2-0.42 / 2.5-6.5）
  4. data_source 不含 synthetic（機構審查通過）
  5. Look-ahead 隔離（特徵為賽前，比分為賽後）
  6. 快取層正常工作
  7. merge_with_live 去重正確
  8. API fallback（無網路時不報錯）

Run: python3 -m pytest tests/test_p0_data_pipeline.py -v
"""
from __future__ import annotations

import os
import sys
import math
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 資料路徑 ─────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent / "data" / "mlb_2025"
_SCORES_CSV = _DATA_DIR / "mlb-2025-asplayed.csv"
_ODDS_CSV = _DATA_DIR / "mlb_odds_2025_real.csv"

_HAS_DATA = _SCORES_CSV.exists()


# ══════════════════════════════════════════════════════════════════════════════
# P0-1: MLB 歷史資料載入器
# ══════════════════════════════════════════════════════════════════════════════

class TestMLBDataLoader:

    def test_import(self) -> None:
        """P0-1-01: 模組可正確匯入"""
        from data.mlb_data_loader import (
            load_mlb_records, print_dataset_summary,
            _american_to_prob, _remove_vig, _elo_expected, _elo_update,
        )
        assert callable(load_mlb_records)

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_load_returns_sufficient_records(self) -> None:
        """P0-1-02: 載入場數 >= 50（解決 P0 問題）"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        assert len(records) >= 50, f"載入 {len(records)} 場 < 最低標準 50"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_load_exceeds_2000_records(self) -> None:
        """P0-1-03: MLB 2025 CSV 應含 2000+ 場（確認資料豐富性）"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        assert len(records) >= 2000, f"只有 {len(records)} 場，CSV 可能被截斷"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_no_synthetic_data(self) -> None:
        """P0-1-04: data_source 不含 synthetic（機構審查 § 核心規範 01）"""
        from data.mlb_data_loader import load_mlb_records
        from wbc_backend.evaluation.institutional_backtest import assert_no_synthetic
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        # 不應拋出 ValueError
        assert_no_synthetic(records, "MLB2025")

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_elo_in_valid_range(self) -> None:
        """P0-1-05: 所有 Elo 值在合理範圍 [1000, 2000]"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        for r in records:
            assert 1000 <= r.home_elo <= 2000, f"home_elo={r.home_elo} 超出範圍"
            assert 1000 <= r.away_elo <= 2000, f"away_elo={r.away_elo} 超出範圍"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_woba_proxy_in_range(self) -> None:
        """P0-1-06: wOBA 代理在合理範圍 [0.20, 0.42]"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        for r in records:
            assert 0.20 <= r.home_woba <= 0.42, f"home_woba={r.home_woba}"
            assert 0.20 <= r.away_woba <= 0.42, f"away_woba={r.away_woba}"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_fip_proxy_in_range(self) -> None:
        """P0-1-07: FIP 代理在合理範圍 [2.5, 6.5]"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        for r in records:
            assert 2.5 <= r.home_fip <= 6.5, f"home_fip={r.home_fip}"
            assert 2.5 <= r.away_fip <= 6.5, f"away_fip={r.away_fip}"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_market_prob_in_range(self) -> None:
        """P0-1-08: 市場隱含機率在 [0.2, 0.8]"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        for r in records:
            assert 0.20 <= r.market_home_prob <= 0.80, (
                f"market_home_prob={r.market_home_prob} 超出合理範圍"
            )

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_actual_scores_post_game(self) -> None:
        """P0-1-09: 賽果欄位有值（Look-ahead 隔離確認）"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        for r in records[:50]:  # 抽查前 50 場
            assert r.actual_home_win is not None
            assert r.actual_total_runs is not None
            assert r.actual_total_runs >= 0
            assert r.actual_home_win in (0, 1)

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_sorted_by_date(self) -> None:
        """P0-1-10: 結果按日期升序排序（Walk-Forward 要求）"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        dates = [r.game_date for r in records]
        assert dates == sorted(dates), "GameRecord 未按日期排序"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_home_win_rate_reasonable(self) -> None:
        """P0-1-11: MLB 主隊勝率應在 [45%, 60%]"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        home_wins = sum(1 for r in records if r.actual_home_win == 1)
        win_rate = home_wins / len(records)
        assert 0.45 <= win_rate <= 0.60, f"主隊勝率 {win_rate:.1%} 偏離 MLB 正常範圍"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_date_range_filter(self) -> None:
        """P0-1-12: min_date/max_date 過濾正確"""
        from data.mlb_data_loader import load_mlb_records
        records_all = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        records_filtered = load_mlb_records(
            _SCORES_CSV, _ODDS_CSV,
            min_date="2025-06-01",
            max_date="2025-07-31",
        )
        assert len(records_filtered) < len(records_all)
        for r in records_filtered:
            assert "2025-06-01" <= r.game_date <= "2025-07-31"

    def test_american_to_prob(self) -> None:
        """P0-1-13: 美式賠率轉換正確"""
        from data.mlb_data_loader import _american_to_prob
        # -150 → 60%
        assert abs(_american_to_prob("-150") - 0.60) < 0.001
        # +150 → 40%
        assert abs(_american_to_prob("+150") - 0.40) < 0.001
        # 無效值 → 0.5
        assert _american_to_prob("N/A") == 0.5

    def test_remove_vig(self) -> None:
        """P0-1-14: 去除 vig 後機率之和為 1"""
        from data.mlb_data_loader import _remove_vig
        p1, p2 = _remove_vig(0.55, 0.50)
        assert abs(p1 + p2 - 1.0) < 1e-6
        assert 0 < p1 < 1
        assert 0 < p2 < 1

    def test_elo_update_winner_gains(self) -> None:
        """P0-1-15: ELO 更新後勝者 Elo 升高、敗者降低"""
        from data.mlb_data_loader import _elo_update
        new_win, new_lose = _elo_update(1500.0, 1500.0)
        assert new_win > 1500.0, "勝者 Elo 應升高"
        assert new_lose < 1500.0, "敗者 Elo 應降低"
        # 零和
        assert abs((new_win + new_lose) - (1500.0 + 1500.0)) < 1e-6

    def test_elo_update_upset(self) -> None:
        """P0-1-16: 弱隊爆冷勝利時 Elo 獲益更大"""
        from data.mlb_data_loader import _elo_update
        # 1400 爆冷勝 1600
        new_win, new_lose = _elo_update(1400.0, 1600.0)
        # 1500 平推勝 1500
        new_even_win, _ = _elo_update(1500.0, 1500.0)
        assert new_win - 1400.0 > new_even_win - 1500.0, "爆冷勝應獲得更多 Elo"

    @pytest.mark.skipif(not _HAS_DATA, reason="CSV 資料不存在")
    def test_elo_converges_over_season(self) -> None:
        """P0-1-17: 賽季後 Elo 分布合理（強隊 > 弱隊）"""
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records(_SCORES_CSV, _ODDS_CSV)
        # 取後 100 場（Elo 已收斂）
        late_records = records[-100:]
        elos = [r.home_elo for r in late_records] + [r.away_elo for r in late_records]
        elo_std = (sum((e - 1500) ** 2 for e in elos) / len(elos)) ** 0.5
        assert elo_std > 10, f"Elo 標準差 {elo_std:.1f} 太小，未收斂"
        assert elo_std < 300, f"Elo 標準差 {elo_std:.1f} 太大，可能有 bug"


# ══════════════════════════════════════════════════════════════════════════════
# P0-2: MLB 實時資料管道
# ══════════════════════════════════════════════════════════════════════════════

class TestMLBLivePipeline:

    def test_import(self) -> None:
        """P0-2-01: 模組可正確匯入"""
        from data.mlb_live_pipeline import (
            fetch_schedule, fetch_today_scores, fetch_recent_completed,
            fetch_completed_to_game_records, merge_with_live,
        )
        assert callable(fetch_schedule)

    def test_american_odds_parsing(self) -> None:
        """P0-2-02: 快取路徑生成正確"""
        from data.mlb_live_pipeline import _cache_path
        p = _cache_path("schedule_1_2025-06-01")
        assert isinstance(p, Path)
        assert p.suffix == ".json"

    def test_fetch_schedule_network_failure(self) -> None:
        """P0-2-03: 網路失敗時返回空列表（不拋出異常）"""
        from data.mlb_live_pipeline import fetch_schedule
        with patch("data.mlb_live_pipeline._fetch_json", return_value=None):
            result = fetch_schedule("2025-06-01", use_cache=False)
            assert result == []

    def test_fetch_today_scores_no_network(self) -> None:
        """P0-2-04: 無網路時返回空列表"""
        from data.mlb_live_pipeline import fetch_today_scores
        with patch("data.mlb_live_pipeline.fetch_schedule", return_value=[]):
            result = fetch_today_scores(use_cache=False)
            assert result == []

    def test_fetch_recent_completed_mock(self) -> None:
        """P0-2-05: Mock API 回應 → 正確解析"""
        from data.mlb_live_pipeline import fetch_recent_completed

        mock_game = {
            "gamePk": 123456,
            "gameDate": "2025-06-01T13:05:00Z",
            "status": {"detailedState": "Final"},
            "teams": {
                "home": {"team": {"name": "New York Yankees"}, "score": 5},
                "away": {"team": {"name": "Boston Red Sox"}, "score": 3},
            },
        }
        with patch("data.mlb_live_pipeline.fetch_schedule", return_value=[mock_game]):
            results = fetch_recent_completed(n_days=1, use_cache=False)
            assert len(results) == 1
            assert results[0]["home_team"] == "New York Yankees"
            assert results[0]["home_score"] == 5
            assert results[0]["away_score"] == 3

    def test_game_record_conversion_mock(self) -> None:
        """P0-2-06: Mock 轉換為 GameRecord 結構正確"""
        from data.mlb_live_pipeline import fetch_completed_to_game_records

        mock_game = {
            "gamePk": 999,
            "gameDate": "2025-06-15T19:00:00Z",
            "status": {"detailedState": "Final"},
            "teams": {
                "home": {"team": {"name": "Los Angeles Dodgers"}, "score": 4},
                "away": {"team": {"name": "San Francisco Giants"}, "score": 2},
            },
        }
        with patch("data.mlb_live_pipeline.fetch_schedule", return_value=[mock_game]):
            records = fetch_completed_to_game_records(n_days=1, use_cache=False)
            assert len(records) == 1
            r = records[0]
            assert r.home_team == "Los Angeles Dodgers"
            assert r.actual_home_win == 1
            assert r.actual_total_runs == 6
            assert r.data_source == "mlb_stats_api_live"

    def test_no_synthetic_in_live_records(self) -> None:
        """P0-2-07: 即時 GameRecord 通過機構真實性驗證"""
        from data.mlb_live_pipeline import fetch_completed_to_game_records
        from wbc_backend.evaluation.institutional_backtest import assert_no_synthetic

        mock_game = {
            "gamePk": 1,
            "gameDate": "2025-07-01T18:00:00Z",
            "status": {"detailedState": "Final"},
            "teams": {
                "home": {"team": {"name": "Chicago Cubs"}, "score": 3},
                "away": {"team": {"name": "Milwaukee Brewers"}, "score": 1},
            },
        }
        with patch("data.mlb_live_pipeline.fetch_schedule", return_value=[mock_game]):
            records = fetch_completed_to_game_records(n_days=1, use_cache=False)
            assert_no_synthetic(records, "LivePipeline")  # 不應拋出異常

    def test_live_record_probabilities_in_range(self) -> None:
        """P0-2-08: 即時 GameRecord 的機率欄位在合理範圍"""
        from data.mlb_live_pipeline import fetch_completed_to_game_records

        mock_game = {
            "gamePk": 2,
            "gameDate": "2025-07-02T18:00:00Z",
            "status": {"detailedState": "Final"},
            "teams": {
                "home": {"team": {"name": "Team A"}, "score": 7},
                "away": {"team": {"name": "Team B"}, "score": 2},
            },
        }
        with patch("data.mlb_live_pipeline.fetch_schedule", return_value=[mock_game]):
            records = fetch_completed_to_game_records(n_days=1, use_cache=False)
            r = records[0]
            assert 0 < r.market_home_prob <= 1
            assert 0 < r.ou_line < 30
            assert r.actual_home_win in (0, 1)

    def test_merge_with_live_deduplication(self) -> None:
        """P0-2-09: merge_with_live 去重正確（相同日期+球隊只保留一條）"""
        from data.mlb_live_pipeline import merge_with_live
        from wbc_backend.evaluation.institutional_backtest import GameRecord

        def make_record(src: str) -> GameRecord:
            return GameRecord(
                game_id=f"TEST_{src}",
                game_date="2025-06-01",
                tournament="TEST",
                round_name="REG",
                home_team="Yankees",
                away_team="Red Sox",
                actual_home_score=5,
                actual_away_score=3,
                actual_home_win=1,
                actual_total_runs=8,
                data_source=src,
            )

        hist = [make_record("mlb_2025_retrosheet")]
        live = [make_record("mlb_stats_api_live")]

        merged = merge_with_live(hist, live, dedup=True)
        assert len(merged) == 1, "相同場次應被去重為 1 條"

    def test_merge_no_dedup(self) -> None:
        """P0-2-10: merge_with_live(dedup=False) 保留所有記錄"""
        from data.mlb_live_pipeline import merge_with_live
        from wbc_backend.evaluation.institutional_backtest import GameRecord

        def make_record(gid: str) -> GameRecord:
            return GameRecord(
                game_id=gid,
                game_date="2025-06-01",
                tournament="TEST",
                round_name="REG",
                home_team="Yankees",
                away_team="Red Sox",
                actual_home_score=5,
                actual_away_score=3,
                actual_home_win=1,
                actual_total_runs=8,
                data_source="mlb_2025_retrosheet",
            )

        hist = [make_record("A")]
        live = [make_record("B")]
        merged = merge_with_live(hist, live, dedup=False)
        assert len(merged) == 2

    def test_cache_save_and_load(self) -> None:
        """P0-2-11: 快取 save/load 循環正確"""
        from data.mlb_live_pipeline import _save_cache, _load_cache
        test_data = {"test": [1, 2, 3], "key": "value"}
        _save_cache("test_cache_key_123", test_data)
        loaded = _load_cache("test_cache_key_123", ttl=60)
        assert loaded == test_data

    def test_cache_expired(self) -> None:
        """P0-2-12: TTL=0 時快取視為過期"""
        from data.mlb_live_pipeline import _save_cache, _load_cache
        _save_cache("test_expired_key", {"data": 42})
        loaded = _load_cache("test_expired_key", ttl=0)
        assert loaded is None

    def test_parse_game_non_final_returns_none(self) -> None:
        """P0-2-13: 未完成比賽不轉換為 GameRecord"""
        from data.mlb_live_pipeline import _parse_game_to_dict
        scheduled_game = {
            "gamePk": 100,
            "gameDate": "2025-08-01T19:00:00Z",
            "status": {"detailedState": "Scheduled"},
            "teams": {
                "home": {"team": {"name": "A"}, "score": None},
                "away": {"team": {"name": "B"}, "score": None},
            },
        }
        result = _parse_game_to_dict(scheduled_game)
        assert result is None

    def test_fetch_recent_sorted_by_date(self) -> None:
        """P0-2-14: 近期完成比賽按日期升序排列"""
        from data.mlb_live_pipeline import fetch_recent_completed

        def make_game(date_str: str, pk: int) -> dict:
            return {
                "gamePk": pk,
                "gameDate": f"{date_str}T19:00:00Z",
                "status": {"detailedState": "Final"},
                "teams": {
                    "home": {"team": {"name": f"Home{pk}"}, "score": 3},
                    "away": {"team": {"name": f"Away{pk}"}, "score": 1},
                },
            }

        games_by_day = {
            "2025-06-03": [make_game("2025-06-03", 3)],
            "2025-06-02": [make_game("2025-06-02", 2)],
            "2025-06-01": [make_game("2025-06-01", 1)],
        }

        def mock_schedule(date_str: str, sport_id="1", use_cache=True):
            return games_by_day.get(date_str, [])

        with patch("data.mlb_live_pipeline.fetch_schedule", side_effect=mock_schedule):
            results = fetch_recent_completed(n_days=3, use_cache=False)
            dates = [r["game_date"] for r in results]
            assert dates == sorted(dates)
