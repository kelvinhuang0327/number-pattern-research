"""
Baseline Heuristics Model inspired by JamesQuintero/Sports-Odds-Algorithms (Algo V2).
Calculates a win probability based on seasonal records, home/away performance, and recent trends.
"""
from typing import Dict, Tuple

class BaselineHeuristics:
    def __init__(self, league: str = "MLB"):
        self.league = league
        # Weights inspired by repo: Record, Home/Away, Home/Away Last 10, Last 10, Avg Pts, Avg Pts 10
        # For simplicity, we normalize these into a core heuristic score.
        self.weights = {
            "seasonal_record": 0.30,
            "home_away_record": 0.25,
            "last_10_games": 0.25,
            "avg_points_diff": 0.20
        }

    def calculate_score(self, team_stats: Dict, opponent_stats: Dict) -> float:
        """
        Calculate a raw favorability score for the team.
        Higher score means higher favorability relative to opponent.
        """
        score = 0.0
        
        # 1. Seasonal Record Difference (0 to 1 scale)
        rec_diff = team_stats.get("win_pct", 0.5) - opponent_stats.get("win_pct", 0.5)
        score += rec_diff * self.weights["seasonal_record"]
        
        # 2. Home/Away specific performance
        # (team_home_pct - opp_away_pct)
        ha_diff = team_stats.get("ha_win_pct", 0.5) - opponent_stats.get("opp_ha_win_pct", 0.5)
        score += ha_diff * self.weights["home_away_record"]
        
        # 3. Last 10 games trend
        trend_diff = team_stats.get("last_10_win_pct", 0.5) - opponent_stats.get("last_10_win_pct", 0.5)
        score += trend_diff * self.weights["last_10_games"]
        
        # 4. Average points/runs difference
        pts_diff = team_stats.get("avg_runs", 4.5) - opponent_stats.get("avg_runs", 4.5)
        # Normalize pts_diff: +/- 2 runs is significant
        norm_pts_diff = max(-1.0, min(1.0, pts_diff / 2.0))
        score += norm_pts_diff * self.weights["avg_points_diff"]
        
        return score

    def predict_probability(self, home_stats: Dict, away_stats: Dict) -> Tuple[float, float]:
        """
        Convert heuristic scores into win probabilities.
        Returns: (away_prob, home_prob)
        """
        # Note: repo uses polynomial fitting, we use a sigmoid calibration for stability
        home_score = self.calculate_score(home_stats, away_stats)
        away_score = self.calculate_score(away_stats, home_stats)
        
        # Simple Logistic mapping
        # 0.0 score diff -> 50/50
        # 0.2 score diff -> ~70/30
        k = 5.0 
        home_prob = 1.0 / (1.0 + pow(2.71828, -k * (home_score - away_score)))
        
        return 1.0 - home_prob, home_prob

def get_baseline_prediction(league: str, home_data: Dict, away_data: Dict) -> Tuple[float, float]:
    model = BaselineHeuristics(league)
    return model.predict_probability(home_data, away_data)
