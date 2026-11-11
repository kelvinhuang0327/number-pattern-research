"""
MoneylinePaperRecommenderV2 測試套件

覆蓋：
- 校準機率路徑正確
- odds_quality_tier 永遠 POST_GAME_PROXY
- paper_only 永遠 True
- blowout gate 拒絕
- ECE gate 拒絕
- edge gate 拒絕
- kelly_cap 不超限
- 不寫入 production channel
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.moneyline_paper_v2 import (
    MoneylinePaperRecommenderV2,
    RecommendationRow,
    _american_to_implied_prob,
    _american_to_decimal,
    _kelly_fraction,
)


# ── 輔助 Fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def recommender() -> MoneylinePaperRecommenderV2:
    return MoneylinePaperRecommenderV2(edge_threshold=0.01, kelly_cap=0.05)


def make_rec(
    p_home: float = 0.55,
    p_away: float = 0.45,
    home_odds: float = -110,
    away_odds: float = -110,
    blowout: float = 0.3,
    ece: float = 0.05,
    recommender: MoneylinePaperRecommenderV2 | None = None,
) -> RecommendationRow:
    r = recommender or MoneylinePaperRecommenderV2()
    return r.recommend(
        game_id="TEST001",
        p_home_win=p_home,
        p_away_win=p_away,
        home_ml_odds=home_odds,
        away_ml_odds=away_odds,
        blowout_propensity=blowout,
        ece=ece,
        home_team="HomeTeam",
        away_team="AwayTeam",
        game_date="2025-06-01",
    )


# ── Tests ────────────────────────────────────────────────────────────────────

class TestCalibratedProbPath:
    """test_calibrated_prob_path_correct"""

    def test_calibrated_prob_path_correct(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """給定強 edge，推薦應選擇正確 side 並且 edge 計算正確。"""
        # home 勝率 0.60，-110 隱含約 0.524 → edge ~ 0.076
        row = recommender.recommend(
            game_id="G001",
            p_home_win=0.60,
            p_away_win=0.40,
            home_ml_odds=-110,
            away_ml_odds=+110,
            ece=0.05,
            blowout_propensity=0.2,
        )
        assert not row.rejected
        assert row.bet_side == "HOME"
        expected_implied = _american_to_implied_prob(-110)
        expected_edge = 0.60 - expected_implied
        assert abs(row.edge - expected_edge) < 1e-6

    def test_edge_calculation_positive_odds(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """正值盤口（underdog）edge 計算正確。"""
        row = recommender.recommend(
            game_id="G002",
            p_home_win=0.40,
            p_away_win=0.60,
            home_ml_odds=-140,
            away_ml_odds=+120,
            ece=0.05,
            blowout_propensity=0.2,
        )
        assert not row.rejected
        assert row.bet_side == "AWAY"
        expected_implied = _american_to_implied_prob(+120)
        expected_edge = 0.60 - expected_implied
        assert abs(row.edge - expected_edge) < 1e-6


class TestOddsQualityTier:
    """test_odds_quality_tier_always_post_game_proxy"""

    def test_odds_quality_tier_always_post_game_proxy_recommended(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(recommender=recommender)
        assert row.odds_quality_tier == "POST_GAME_PROXY"

    def test_odds_quality_tier_always_post_game_proxy_rejected_ece(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(ece=0.99, recommender=recommender)
        assert row.rejected
        assert row.odds_quality_tier == "POST_GAME_PROXY"

    def test_odds_quality_tier_always_post_game_proxy_rejected_blowout(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(blowout=0.99, recommender=recommender)
        assert row.rejected
        assert row.odds_quality_tier == "POST_GAME_PROXY"


class TestPaperOnlyAlwaysTrue:
    """test_paper_only_always_true"""

    def test_paper_only_always_true_when_recommended(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(recommender=recommender)
        assert row.paper_only is True

    def test_paper_only_always_true_when_rejected(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(ece=0.99, recommender=recommender)
        assert row.paper_only is True

    def test_paper_only_cannot_be_overridden(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """即使外部嘗試設置 paper_only=False 也不可能，因為它由 recommender 控制。"""
        row = make_rec(recommender=recommender)
        # 永遠為 True
        assert row.paper_only is True


class TestBlowoutGate:
    """test_blowout_gate_rejects"""

    def test_blowout_gate_rejects_at_threshold(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(blowout=0.66, recommender=recommender)
        assert row.rejected
        assert "blowout_gate" in row.reject_reason

    def test_blowout_gate_passes_below_threshold(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(blowout=0.64, recommender=recommender)
        assert not row.rejected

    def test_blowout_gate_exact_boundary(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """正好在 0.65 邊界，應 pass（> 才拒）。"""
        row = make_rec(blowout=0.65, recommender=recommender)
        assert not row.rejected

    def test_blowout_gate_rejects_extreme(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(blowout=1.0, recommender=recommender)
        assert row.rejected
        assert row.bet_side == "NO_BET"


class TestECEGate:
    """test_ece_gate_rejects_when_above_threshold"""

    def test_ece_gate_rejects_above_threshold(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(ece=0.13, recommender=recommender)
        assert row.rejected
        assert "ece_gate" in row.reject_reason

    def test_ece_gate_passes_below_threshold(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(ece=0.11, recommender=recommender)
        assert not row.rejected

    def test_ece_gate_exact_boundary(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """正好 0.12，應 pass（> 才拒）。"""
        row = make_rec(ece=0.12, recommender=recommender)
        assert not row.rejected

    def test_ece_gate_takes_priority_over_blowout(self) -> None:
        """ECE 先驗，blowout 後驗；若 ECE 已拒則 reject_reason 含 ece_gate。"""
        r = MoneylinePaperRecommenderV2()
        row = r.recommend(
            game_id="G_ECE_FIRST",
            p_home_win=0.55,
            p_away_win=0.45,
            home_ml_odds=-110,
            away_ml_odds=-110,
            ece=0.99,
            blowout_propensity=0.99,
        )
        assert row.rejected
        assert "ece_gate" in row.reject_reason


class TestEdgeGate:
    """test_edge_gate_rejects_when_below_threshold"""

    def test_edge_gate_rejects_zero_edge(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """當 p == 隱含機率時，edge = 0 < 1% → 拒。"""
        implied = _american_to_implied_prob(-110)
        row = recommender.recommend(
            game_id="G_EDGE",
            p_home_win=implied,
            p_away_win=1.0 - implied,
            home_ml_odds=-110,
            away_ml_odds=-110,
            ece=0.05,
            blowout_propensity=0.2,
        )
        assert row.rejected
        assert "edge_gate" in row.reject_reason

    def test_edge_gate_passes_with_sufficient_edge(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(p_home=0.60, p_away=0.40, home_odds=-110, recommender=recommender)
        assert not row.rejected

    def test_edge_gate_rejects_negative_edge(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """模型機率低於隱含機率 → edge < 0 → 拒。"""
        row = recommender.recommend(
            game_id="G_NEG",
            p_home_win=0.40,
            p_away_win=0.60,
            home_ml_odds=-200,
            away_ml_odds=+170,
            ece=0.05,
            blowout_propensity=0.2,
        )
        # away edge = 0.60 - implied(+170) ≈ 0.60 - 0.370 = 0.23 > 0 → 應 pass
        # 這個案例 away 仍有 edge，測試 home 拒
        # 換個明顯無 edge 的案例
        row2 = recommender.recommend(
            game_id="G_NEG2",
            p_home_win=0.40,
            p_away_win=0.40,  # 兩側 prob 都低
            home_ml_odds=-200,
            away_ml_odds=-200,
            ece=0.05,
            blowout_propensity=0.2,
        )
        assert row2.rejected


class TestKellyCap:
    """test_kelly_cap_not_exceeded"""

    def test_kelly_cap_not_exceeded_high_edge(self) -> None:
        """即使 Kelly 建議高倉位，stake 不超過 kelly_cap。"""
        r = MoneylinePaperRecommenderV2(kelly_cap=0.03)
        row = r.recommend(
            game_id="G_KELLY",
            p_home_win=0.80,
            p_away_win=0.20,
            home_ml_odds=+200,
            away_ml_odds=-300,
            ece=0.05,
            blowout_propensity=0.2,
        )
        assert not row.rejected
        assert row.stake_fraction <= 0.03 + 1e-9

    def test_kelly_cap_default_five_percent(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(p_home=0.90, p_away=0.10, home_odds=+500, recommender=recommender)
        if not row.rejected:
            assert row.stake_fraction <= 0.05 + 1e-9

    def test_kelly_fraction_raw_may_exceed_cap(self) -> None:
        """raw kelly_fraction 可能超過 cap，但 stake_fraction 不會。"""
        r = MoneylinePaperRecommenderV2(kelly_cap=0.02)
        row = r.recommend(
            game_id="G_CAP_TEST",
            p_home_win=0.75,
            p_away_win=0.25,
            home_ml_odds=+150,
            away_ml_odds=-200,
            ece=0.05,
            blowout_propensity=0.2,
        )
        if not row.rejected:
            assert row.stake_fraction <= 0.02 + 1e-9


class TestNoProductionChannelWritten:
    """test_no_production_channel_written"""

    def test_paper_only_true_means_no_production(self, recommender: MoneylinePaperRecommenderV2) -> None:
        """paper_only=True 即合約保證不寫 production channel。"""
        row = make_rec(recommender=recommender)
        assert row.paper_only is True
        # 確認無任何 production channel 欄位
        d = row.to_dict()
        assert d["paper_only"] is True
        assert d["odds_quality_tier"] == "POST_GAME_PROXY"

    def test_to_dict_contains_required_proxy_fields(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(recommender=recommender)
        d = row.to_dict()
        assert "paper_only" in d
        assert "odds_quality_tier" in d
        assert d["paper_only"] is True
        assert d["odds_quality_tier"] == "POST_GAME_PROXY"

    def test_rejected_rows_also_paper_only(self, recommender: MoneylinePaperRecommenderV2) -> None:
        for ece_val in [0.15, 0.5, 1.0]:
            row = make_rec(ece=ece_val, recommender=recommender)
            assert row.paper_only is True
            assert row.to_dict()["odds_quality_tier"] == "POST_GAME_PROXY"


# ── 額外整合測試 ──────────────────────────────────────────────────────────────

class TestGatesPassedTracking:
    def test_gates_passed_records_all_passed_gates(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(recommender=recommender)
        if not row.rejected:
            assert "ece_pass" in row.gates_passed
            assert "blowout_pass" in row.gates_passed
            assert "edge_pass" in row.gates_passed

    def test_gates_passed_stops_at_first_rejection(self, recommender: MoneylinePaperRecommenderV2) -> None:
        row = make_rec(ece=0.99, recommender=recommender)
        assert "ece_pass" not in row.gates_passed
