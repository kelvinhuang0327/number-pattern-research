"""
AI Prediction Rationalizer.
Explains WHY the AI recommends specific bets based on model outputs and features.
"""
from typing import Dict, List, Tuple
from data.wbc_data import MatchData
from strategy.value_detector import ValueBet
from models.advanced_features import aggregate_lineup_strength, calculate_bullpen_fatigue_penalty

def rationalize_recommendation(
    match: MatchData,
    away_wp: float,
    home_wp: float,
    ensemble_details: Dict,
    value_bets: List[ValueBet]
) -> List[str]:
    """
    Generate a human-readable list of reasons for the current prediction and recommendations.
    """
    reasons = []
    
    # 1. Logic behind the Win Probability
    fav_team = match.home.code if home_wp > away_wp else match.away.code
    wp_val = max(home_wp, away_wp)
    
    reasons.append(f"🤖 **模型核心邏輯**: 預測 {fav_team} 為優勢方 ({wp_val:.1%})。")
    
    # WBC Specifics: Pitch Count & Piggyback
    pc_rule = match.pitch_count_rule
    reasons.append(f"⚾ **WBC 賽制特點**: 本場為 {pc_rule.round_name}，先發限投 {pc_rule.max_pitches} 球，預測先發僅能負擔約 {pc_rule.expected_sp_innings} 局。")
    
    if match.home_piggyback or match.away_piggyback:
        pb_teams = []
        if match.home_piggyback: pb_teams.append(match.home.code)
        if match.away_piggyback: pb_teams.append(match.away.code)
        reasons.append(f"🔄 **第二先發 (Piggyback)**: {'、'.join(pb_teams)} 已配置第二先發以銜接中繼局數，顯著降低了早期換投帶來的崩盤風險。")
    
    # Roster Volatility impact
    rv_away = match.away.roster_vol.roster_strength_index if match.away.roster_vol else 100
    rv_home = match.home.roster_vol.roster_strength_index if match.home.roster_vol else 100
    
    if rv_away < 70 or rv_home < 70:
        vol_team = match.away.code if rv_away < rv_home else match.home.code
        reasons.append(f"⚠️ **陣容異動警告**: {vol_team} 陣容完整度僅 {min(rv_away, rv_home)}%，Meta-Learner 已自動調高 Simulation 模型權重以應對不確定性。")

    # 2. PA-level Matchup Strength (X-Factor)
    # Check SP quality vs Lineup
    away_vs_sp = aggregate_lineup_strength(match.away_lineup, match.home_sp)
    home_vs_sp = aggregate_lineup_strength(match.home_lineup, match.away_sp)
    
    if home_vs_sp > 0.350:
        reasons.append(f"🔥 **打線壓制力**: {match.home.code} 打線對戰 {match.away_sp.name} 的預期 wOBA 高達 {home_vs_sp:.3f}，存在早期爆發可能。")
    if match.home_sp.stuff_plus > 120:
        reasons.append(f"⚡ **投手壓制力**: {match.home_sp.name} 具備 Stuff+ {match.home_sp.stuff_plus} 的頂級球威，顯著降低了對手打線的長打機率。")

    # 3. Bullpen Fatigue
    a_bp_fatigue = calculate_bullpen_fatigue_penalty(match.away_bullpen)
    h_bp_fatigue = calculate_bullpen_fatigue_penalty(match.home_bullpen)
    
    if a_bp_fatigue > 1.1:
        reasons.append(f"📉 **牛棚疲勞**: {match.away.code} 牛棚近三日用球量過高，模型已加入 {a_bp_fatigue-1:.1%} 的失分懲罰係數。")

    # 4. Run Line (Spread) Advice
    # Use MC score differential to advise on Run Lines
    mc_data = ensemble_details.get("sub_models", {}).get("monte_carlo", {})
    a_runs = mc_data.get("away_avg_runs", 0)
    h_runs = mc_data.get("home_avg_runs", 0)
    score_diff = abs(h_runs - a_runs)
    
    if score_diff > 0:
        if score_diff < 1.3:
            reasons.append(f"⚖️ **盤口建議 (讓分)**: 模擬顯示兩隊分差僅 {score_diff:.1f} 分，強隊穿盤 (-1.5) 風險較高，建議優先考慮 **受讓方 (+1.5)**。")
        elif score_diff > 2.0:
            strong_team = match.home.code if h_runs > a_runs else match.away.code
            reasons.append(f"💪 **盤口建議 (讓分)**: {strong_team} 具備強大分差優勢 (預計贏 {score_diff:.1f} 分)，**讓分盤 (-1.5)** 具備高度穿盤潛力。")
        else:
            reasons.append(f"📊 **盤口建議 (讓分)**: 預計分差落在 {score_diff:.1f} 分，讓分盤價值與精準度持平，需注意牛棚最後一局的穩定性。")

    # 5. Over/Under Advice
    total_runs = mc_data.get("total_runs_avg", 0)
    
    # Analyze 'Duel' potential via Pitcher stats
    high_lev_risk = (match.away_sp.high_leverage_era + match.home_sp.high_leverage_era) / 2.0
    clutch_power = sum(b.clutch_woba for b in match.away_lineup + match.home_lineup) / max(1, len(match.away_lineup + match.home_lineup))
    
    if total_runs < 7.5:
        reasons.append(f"🔒 **盤口建議 (大小分)**: 預計總分為 {total_runs:.1f}，且雙方先發具備強大的「高壓解危能力」(Avg High-Lev ERA {high_lev_risk:.2f})，高機率出現 **投手戰 (Under)**。")
    elif total_runs > 9.5:
        reasons.append(f"🧨 **盤口建議 (大小分)**: 預計總分高達 {total_runs:.1f}，且打線擁有卓越的「关键打擊率」(Clutch wOBA {clutch_power:.3f})，強烈建議觀察 **大分 (Over)**。")
    else:
        reasons.append(f"☁️ **盤口建議 (大小分)**: 總分預計在 {total_runs:.1f} 附近，處於關鍵盤口中性區，需視當天球場風向與濕度決定。")

    # 6. Value Detection Logic
    best_bets = [b for b in value_bets if b.edge_tier == "STRONG"]
    for b in best_bets:
        reason = f"💰 **價值交易點**: {b.market} {b.side} 賠率為 {b.decimal_odds}，隱含勝率僅 {b.implied_prob:.1%}，"
        reason += f"但 AI 計算結果為 {b.true_prob:.1%}，存在 {b.ev:.1%} 的期望值邊際 (Edge)。"
        reasons.append(reason)

    return reasons
