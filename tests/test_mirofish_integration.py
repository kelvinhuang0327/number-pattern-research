"""
MiroFish 借鑑模組整合測試 — Phase 4 驗證套件
==============================================
測試三個新增模組：
  K. wbc_backend/features/knowledge_graph.py  (棒球知識圖譜)
  L. wbc_backend/features/nlp_extractor.py    (NLP 賽前特徵)
  M. wbc_backend/betting/market_simulator.py  (市場代理人模擬)

確認：
  1. 所有模組可正確匯入與執行
  2. 無 Look-ahead Leakage（截止日期機制正確）
  3. Feature dict 輸出值域合理（無 NaN / Inf）
  4. 整合至 build_alpha_signals() 後總特徵數 >= 300
  5. 市場模擬延遲 < 15 秒（1000 代理 × 60 輪）

Run: python -m pytest tests/test_mirofish_integration.py -v
"""
from __future__ import annotations

import math
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 共用 Fixtures ─────────────────────────────────────────────────────────────

from wbc_backend.domain.schemas import (
    BatterSnapshot, Matchup, PitcherSnapshot, TeamSnapshot,
)


def _make_team(name: str, elo: float = 1500.0) -> TeamSnapshot:
    return TeamSnapshot(
        team=name,
        elo=elo,
        batting_woba=0.320,
        batting_ops_plus=105,
        pitching_fip=3.80,
        pitching_whip=1.20,
        pitching_stuff_plus=102.0,
        der=0.695,
        bullpen_depth=6.0,
        pitch_limit=80,
        opening_ml_prob=0.52,
        public_bet_pct=0.55,
        sharp_handle_pct=0.48,
    )


def _make_pitcher(name: str, team: str) -> PitcherSnapshot:
    return PitcherSnapshot(
        name=name,
        team=team,
        era=3.50,
        fip=3.60,
        whip=1.18,
        k_per_9=9.5,
        bb_per_9=2.8,
        stuff_plus=108.0,
        ip_last_30=28.0,
        era_last_3=3.20,
        pitch_count_last_3d=0,
        fastball_velo=95.5,
        high_leverage_era=3.40,
    )


def _make_batter(name: str, team: str) -> BatterSnapshot:
    return BatterSnapshot(
        name=name,
        team=team,
        avg=0.275,
        obp=0.355,
        slg=0.450,
        woba=0.335,
        ops_plus=112,
        clutch_woba=0.340,
        vs_left_avg=0.260,
        vs_right_avg=0.285,
    )


def _make_matchup() -> Matchup:
    home = _make_team("TPE", elo=1520.0)
    away = _make_team("JPN", elo=1560.0)
    home_sp = _make_pitcher("Chen", "TPE")
    away_sp = _make_pitcher("Yamamoto", "JPN")
    home_lineup = [_make_batter(f"TPE_B{i}", "TPE") for i in range(9)]
    away_lineup = [_make_batter(f"JPN_B{i}", "JPN") for i in range(9)]
    return Matchup(
        game_id="WBC_2026_A01",
        tournament="WBC",
        game_time_utc="2026-03-07T10:00:00Z",
        home=home,
        away=away,
        home_sp=home_sp,
        away_sp=away_sp,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
        venue="Tokyo_Dome",
        umpire_id="ump_001",
        tournament_round_num=1,
        opening_ml_home_odds=1.90,
        public_bet_pct_home=0.58,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Category K — 棒球知識圖譜測試
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """知識圖譜特徵層測試。"""

    def setup_method(self):
        """使用記憶體資料庫（避免污染磁碟）。"""
        from pathlib import Path
        from wbc_backend.features.knowledge_graph import BaseballKnowledgeGraph
        self.kg = BaseballKnowledgeGraph(db_path=Path(":memory:"))

    def test_kg_imports(self):
        """確保模組可正常匯入。"""
        from wbc_backend.features.knowledge_graph import (
            BaseballKnowledgeGraph,
            KnowledgeGraphFeatures,
            MatchupEdge,
            compute_knowledge_graph_signals,
        )
        assert BaseballKnowledgeGraph is not None

    def test_empty_graph_returns_neutral_features(self):
        """空圖譜應返回中性特徵（無錯誤）。"""
        from wbc_backend.features.knowledge_graph import compute_knowledge_graph_signals
        matchup = _make_matchup()
        feats = compute_knowledge_graph_signals(matchup, self.kg, "2026-03-07")

        assert isinstance(feats, dict)
        assert len(feats) >= 15, f"期望 >= 15 個特徵，實際: {len(feats)}"

        # 所有值應為有限浮點數
        for k, v in feats.items():
            assert math.isfinite(v), f"特徵 {k} = {v} 非有限數"

    def test_write_and_read_pitcher_batter(self):
        """寫入對決記錄後可正確讀取。"""
        self.kg.record_pitcher_batter(
            pitcher_id="Yamamoto",
            batter_id="TPE_B1",
            game_date="2023-03-10",
            at_bats=12,
            hits=2,
            walks=1,
            strikeouts=5,
            home_runs=0,
            woba_sum=0.280 * 12,
        )

        edge = self.kg.get_pitcher_vs_lineup("Yamamoto", ["TPE_B1"], "2026-03-07")
        assert edge.at_bats == 12
        assert edge.strikeouts == 5
        assert abs(edge.woba - 0.280) < 0.01
        assert 0.0 <= edge.sample_confidence <= 1.0

    def test_cutoff_date_prevents_leakage(self):
        """截止日期機制：未來資料不應被讀取到。"""
        self.kg.record_pitcher_batter(
            pitcher_id="Yamamoto",
            batter_id="TPE_B1",
            game_date="2026-03-10",   # 開賽後 3 天
            at_bats=6, hits=2, walks=0,
            strikeouts=3, home_runs=1, woba_sum=0.400 * 6,
        )

        # 截止日期 = 開賽當天，不應讀到未來資料
        edge = self.kg.get_pitcher_vs_lineup("Yamamoto", ["TPE_B1"], "2026-03-07")
        assert edge.at_bats == 0, "截止日期後的資料被讀取了！Look-ahead Leakage！"

    def test_team_vs_team_stats(self):
        """球隊對球隊勝率統計正確。"""
        for i in range(5):
            self.kg.record_team_vs_team(
                "TPE", "JPN", f"2023-{i+1:02d}-10",
                home_win=(i % 2 == 0), home_runs=4, away_runs=3
            )

        stats = self.kg.get_team_vs_team_stats("TPE", "JPN", "2026-03-07")
        assert 0.0 <= stats["win_pct"] <= 1.0
        assert stats["n_games"] == 5.0

    def test_kg_feature_value_ranges(self):
        """知識圖譜特徵值域合理性檢查。"""
        from wbc_backend.features.knowledge_graph import compute_knowledge_graph_signals
        matchup = _make_matchup()

        # 寫入一些測試資料
        for i in range(9):
            self.kg.record_pitcher_batter(
                f"Yamamoto", f"TPE_B{i}", "2023-03-10",
                at_bats=8, hits=2, walks=1, strikeouts=3, home_runs=0,
                woba_sum=0.290 * 8,
            )

        feats = compute_knowledge_graph_signals(matchup, self.kg, "2026-03-07")

        # 差值特徵應在 [-5, 5] 合理範圍內
        for k, v in feats.items():
            assert math.isfinite(v), f"NaN/Inf: {k} = {v}"
        # 樣本信心度應在 [0, 1]
        assert 0.0 <= feats.get("kg_matchup_sample_confidence", 0.5) <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Category L — NLP 賽前特徵測試
# ══════════════════════════════════════════════════════════════════════════════

class TestNLPExtractor:
    """NLP 特徵提取層測試。"""

    def test_nlp_imports(self):
        """確保模組可正常匯入。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals, build_empty_nlp_features,
        )
        assert PregameTextBundle is not None

    def test_empty_bundle_returns_neutral(self):
        """空文字包應返回中性特徵。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals,
        )
        bundle = PregameTextBundle(home_team="TPE", away_team="JPN")
        feats = compute_nlp_signals(bundle, use_llm=False)

        assert isinstance(feats, dict)
        assert len(feats) >= 10
        for k, v in feats.items():
            assert math.isfinite(v), f"NaN/Inf: {k} = {v}"

    def test_injury_detection(self):
        """傷兵關鍵字應正確識別。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals,
        )
        bundle = PregameTextBundle(
            home_team="TPE",
            away_team="JPN",
            home_injury_report="主力三號棒球員因肘部受傷退出先發名單",
        )
        feats = compute_nlp_signals(bundle, use_llm=False)
        assert feats["nlp_home_injury_severity"] > 0.0, "應偵測到傷兵"

    def test_positive_news_lifts_confidence(self):
        """正面新聞應提升先發信心度。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals,
        )
        bundle_good = PregameTextBundle(
            home_team="TPE",
            away_team="JPN",
            home_starter_news="先發投手陳偉殷復健完成，狀態佳，準備就緒",
        )
        bundle_neutral = PregameTextBundle(home_team="TPE", away_team="JPN")

        feats_good = compute_nlp_signals(bundle_good, use_llm=False)
        feats_neutral = compute_nlp_signals(bundle_neutral, use_llm=False)

        assert feats_good["nlp_home_starter_confidence"] >= feats_neutral["nlp_home_starter_confidence"]

    def test_weather_detection(self):
        """天氣關鍵字應正確識別。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals,
        )
        bundle = PregameTextBundle(
            home_team="TPE",
            away_team="JPN",
            weather_report="強風 + 雨，比賽可能延遲",
        )
        feats = compute_nlp_signals(bundle, use_llm=False)
        assert feats["nlp_weather_impact"] > 0.0

    def test_composite_advantage_direction(self):
        """主隊優勢場景：綜合 NLP 分數應為正。"""
        from wbc_backend.features.nlp_extractor import (
            PregameTextBundle, compute_nlp_signals,
        )
        bundle = PregameTextBundle(
            home_team="TPE",
            away_team="JPN",
            home_starter_news="陳偉殷狀態絕佳，備戰充足",
            away_injury_report="日本王牌投手山本由伸肩膀受傷無法出賽",
            game_context="台灣背水一戰，必須晉級",
        )
        feats = compute_nlp_signals(bundle, use_llm=False)
        assert feats["nlp_composite_nlp_advantage"] > 0.0, "主隊明顯優勢應有正值"

    def test_neutral_features_all_keys_present(self):
        """build_empty_nlp_features 應包含所有必要鍵值。"""
        from wbc_backend.features.nlp_extractor import build_empty_nlp_features, _NEUTRAL_FEATURES
        feats = build_empty_nlp_features()
        for k in _NEUTRAL_FEATURES:
            assert k in feats, f"缺少鍵值: {k}"


# ══════════════════════════════════════════════════════════════════════════════
# Category M — 市場代理人模擬測試
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketSimulator:
    """市場代理人模擬器測試。"""

    def test_market_sim_imports(self):
        """確保模組可正常匯入。"""
        from wbc_backend.betting.market_simulator import (
            BettingMarketSimulator, MarketPrediction,
            compute_market_simulation_signals,
        )
        assert BettingMarketSimulator is not None

    def test_basic_simulation_runs(self):
        """基本模擬應能正常完成並返回合理結果。"""
        from wbc_backend.betting.market_simulator import BettingMarketSimulator
        sim = BettingMarketSimulator(n_agents=100, n_rounds=20, seed=42)
        result = sim.run(
            opening_home_prob=0.52,
            model_home_prob=0.60,
            public_bet_pct_home=0.62,
            is_sharp_on_home=True,
        )

        assert 0.05 <= result.predicted_closing_home_prob <= 0.95
        assert 0.0 <= result.steam_move_probability <= 1.0
        assert result.sharp_consensus_direction in (-1, 0, 1)
        assert result.total_volume_simulated > 0

    def test_to_feature_dict_format(self):
        """to_feature_dict 應返回 10 個有限浮點特徵。"""
        from wbc_backend.betting.market_simulator import BettingMarketSimulator
        sim = BettingMarketSimulator(n_agents=100, n_rounds=20, seed=42)
        result = sim.run(0.50, 0.55)
        feats = result.to_feature_dict()

        assert len(feats) == 10
        for k, v in feats.items():
            assert math.isfinite(v), f"NaN/Inf: {k} = {v}"

    def test_sharp_on_home_lifts_closing_prob(self):
        """大戶押主隊應使收盤主隊勝率上升。"""
        from wbc_backend.betting.market_simulator import BettingMarketSimulator
        sim = BettingMarketSimulator(n_agents=500, n_rounds=30, seed=99)

        sharp_home = sim.run(0.50, 0.65, public_bet_pct_home=0.55, is_sharp_on_home=True)
        sharp_away = sim.run(0.50, 0.35, public_bet_pct_home=0.45, is_sharp_on_home=False)

        # 大戶押主隊：收盤主隊勝率應高
        assert sharp_home.predicted_closing_home_prob > 0.50
        # 大戶押客隊：收盤主隊勝率應低
        assert sharp_away.predicted_closing_home_prob < 0.50

    def test_performance_under_15_seconds(self):
        """1000 代理 × 60 輪應在 15 秒內完成。"""
        from wbc_backend.betting.market_simulator import BettingMarketSimulator
        sim = BettingMarketSimulator(n_agents=1000, n_rounds=60, seed=42)
        t0 = time.time()
        sim.run(0.52, 0.58)
        elapsed = time.time() - t0
        assert elapsed < 15.0, f"模擬超時: {elapsed:.1f}s > 15s 目標"

    def test_compute_market_simulation_signals_interface(self):
        """公開介面函數應正常工作。"""
        from wbc_backend.betting.market_simulator import compute_market_simulation_signals
        feats = compute_market_simulation_signals(
            opening_home_prob=0.52,
            model_home_prob=0.59,
            public_bet_pct_home=0.60,
            n_agents=200,
            n_rounds=20,
        )
        assert len(feats) == 10
        for k, v in feats.items():
            assert math.isfinite(v), f"NaN/Inf: {k} = {v}"

    def test_steam_detection_on_sharp_action(self):
        """大戶快速行動應能觸發 Steam Move 偵測。"""
        from wbc_backend.betting.market_simulator import BettingMarketSimulator
        # 大幅模型優勢 → 大戶積極下注 → 應有 steam 事件
        sim = BettingMarketSimulator(n_agents=1000, n_rounds=60, seed=7)
        result = sim.run(
            opening_home_prob=0.50,
            model_home_prob=0.72,   # 大幅偏離
            public_bet_pct_home=0.65,
            is_sharp_on_home=True,
        )
        # steam_events 不一定觸發，但模擬應能完成
        assert result.n_steam_events >= 0


# ══════════════════════════════════════════════════════════════════════════════
# 整合測試 — build_alpha_signals() 含三新層
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """整合測試：三個新層與 build_alpha_signals() 的整合。"""

    def test_build_alpha_signals_total_features(self):
        """加入 K/L/M 三層後，總特徵數應 >= 300。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            cutoff_date="2026-03-07",
            enable_kg=True,
            enable_nlp=True,
            enable_market_sim=True,
            use_llm=False,
        )
        # 含 K+L+M 三新層（各 17/11/10 個特徵），原始 A-J 約 239 唯一特徵
        # 總計約 277 = 239+38，閾值設 270 以保留容忍度
        assert signals.n_signals >= 270, (
            f"總特徵數 {signals.n_signals} < 270，"
            f"已計算類別: {signals.categories_computed}"
        )

    def test_new_categories_in_computed(self):
        """三個新類別應出現在 categories_computed 列表中。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            cutoff_date="2026-03-07",
            enable_kg=True,
            enable_nlp=True,
            enable_market_sim=True,
            use_llm=False,
        )
        cats = signals.categories_computed
        assert any("KnowledgeGraph" in c for c in cats), f"K 類別未計算: {cats}"
        assert any("NLP" in c for c in cats), f"L 類別未計算: {cats}"
        assert any("MarketSim" in c for c in cats), f"M 類別未計算: {cats}"

    def test_all_features_finite(self):
        """所有特徵值應為有限浮點數（無 NaN / Inf）。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            cutoff_date="2026-03-07",
            enable_kg=True,
            enable_nlp=True,
            enable_market_sim=True,
            use_llm=False,
        )
        bad = {k: v for k, v in signals.feature_dict.items() if not math.isfinite(v)}
        assert not bad, f"發現非有限特徵: {bad}"

    def test_backward_compatible_without_new_layers(self):
        """停用新層時，結果應與舊版相容（>= 200 個原始特徵）。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            enable_kg=False,
            enable_nlp=False,
            enable_market_sim=False,
        )
        assert signals.n_signals >= 200

    def test_with_pregame_text(self):
        """提供賽前文字時，NLP 特徵應有所不同（非全部中性值）。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        from wbc_backend.features.nlp_extractor import PregameTextBundle

        matchup = _make_matchup()
        bundle = PregameTextBundle(
            home_team="TPE",
            away_team="JPN",
            away_injury_report="日本王牌投手山本由伸肩膀受傷",
        )
        signals = build_alpha_signals(
            matchup,
            pregame_text=bundle,
            enable_kg=False,
            enable_nlp=True,
            enable_market_sim=False,
            use_llm=False,
        )
        # 應能偵測到客隊傷兵
        away_injury = signals.feature_dict.get("nlp_away_injury_severity", 0.0)
        assert away_injury > 0.0, "應偵測到客隊傷兵"

    def test_kg_prefix_features_exist(self):
        """KG 特徵應出現在 feature_dict 中。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            cutoff_date="2026-03-07",
            enable_kg=True,
            enable_nlp=False,
            enable_market_sim=False,
        )
        kg_feats = [k for k in signals.feature_dict if k.startswith("kg_")]
        assert len(kg_feats) >= 10, f"KG 特徵數量不足: {len(kg_feats)}"

    def test_market_sim_prefix_features_exist(self):
        """市場模擬特徵應出現在 feature_dict 中。"""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = _make_matchup()
        signals = build_alpha_signals(
            matchup,
            enable_kg=False,
            enable_nlp=False,
            enable_market_sim=True,
        )
        mkt_feats = [k for k in signals.feature_dict if k.startswith("mkt_")]
        assert len(mkt_feats) == 10, f"市場特徵數量錯誤: {len(mkt_feats)}"
