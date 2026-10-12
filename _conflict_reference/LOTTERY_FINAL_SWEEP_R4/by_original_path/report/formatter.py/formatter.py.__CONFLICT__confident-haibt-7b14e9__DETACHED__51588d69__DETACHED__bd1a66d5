"""
Report Formatter.

Generates the fixed-format analysis report including:
  • Match overview & radar chart data
  • WBC pitch-count rules & pitcher timeline
  • Win probability from ensemble + WBC adjustments
  • Score prediction & distribution
  • Taiwan Sports Lottery (TSL) betting recommendations
    — 不讓分(ML), 讓分(RL), 大小分(OU), 單雙(OE), 前五局(F5), 隊伍總分(TT)
  • Value bet details with Kelly sizing
  • Roster Strength Index comparison
  • Market signals & risk status
  • X-Factors: pitch limits, bullpen fatigue, starters, star players
  • Portfolio summary
"""
from __future__ import annotations
from typing import Dict, List, Optional
from strategy.value_detector import ValueBet
from strategy.kelly_criterion import BetSizing, BankrollState
from strategy.sharp_detector import MarketSignal
from strategy.risk_control import RiskStatus
from data.wbc_data import MatchData
from strategy.rationalizer import rationalize_recommendation


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _stars(confidence: float) -> str:
    """Map a 0-1 confidence to 1-5 star rating."""
    n = max(1, min(5, round(confidence * 5)))
    return "★" * n + "☆" * (5 - n)


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _signed_pct(v: float) -> str:
    return f"{v * 100:+.1f}%"


def _fmt_odds(v: float) -> str:
    return f"{v:.2f}"


def _bar(label: str, value: float, width: int = 20) -> str:
    filled = round(value / 100 * width)
    return f"{label:>8s} |{'█' * filled}{'░' * (width - filled)}| {value:.0f}"


# ──────────────────────────────────────────────────────────
# Main report builder
# ──────────────────────────────────────────────────────────

def build_report(
    match: MatchData,
    away_wp: float,
    home_wp: float,
    wbc_details: Dict,
    ensemble_details: Dict,
    poisson_details: Dict,
    mc_details: Dict,
    value_bets: List[ValueBet],
    portfolio: List[BetSizing],
    bankroll: BankrollState,
    market_signals: List[MarketSignal],
    market_headline: str,
    risk_status: RiskStatus,
) -> str:
    """Return the full Markdown analysis report."""

    away = match.away
    home = match.home
    lines: List[str] = []

    def ln(s: str = ""):
        lines.append(s)

    # ══════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════
    ln("=" * 70)
    ln(f"  ⚾  2026 WBC QUANTITATIVE BETTING REPORT")
    ln(f"  {match.round_name}  |  {match.venue}")
    ln(f"  {match.game_time}")
    ln()
    ln(f"  📡 資料來源 (Data Source): {getattr(match, 'data_source', 'MOCK/SEED (人工建模資料)')}")
    ln(f"  💧 盤口流動性 (Liquidity): {getattr(match, 'liquidity_level', 'LOW (初期/死盤)')}")
    ln("=" * 70)
    ln()

    # ══════════════════════════════════════════════════════
    # MATCH: AWAY vs HOME
    # ══════════════════════════════════════════════════════
    ln(f"## Match: {away.name} ({away.code}) vs {home.name} ({home.code})")
    ln()

    # ── 1. 核心指標對比 (Radar Chart Data) ─────────────
    ln("### 1. 核心指標對比")
    ln()
    ln("| 指標 (Category)    | " + f"{away.code:^10s}" + " | " + f"{home.code:^10s}" + " | 優勢 (Edge) |")
    ln("|" + "-" * 20 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 13 + "|")

    # Pitching (lower ERA is better)
    away_pitch = (match.away_sp.era + away.bullpen_era) / 2
    home_pitch = (match.home_sp.era + home.bullpen_era) / 2
    pitch_edge = away.code if away_pitch < home_pitch else home.code
    ln(f"| 投手 (Pitching)    | {away_pitch:^10.2f} | {home_pitch:^10.2f} | {pitch_edge:^11s} |")

    # Batting
    bat_edge = away.code if away.lineup_wrc_plus > home.lineup_wrc_plus else home.code
    ln(f"| 打擊 wRC+          | {away.lineup_wrc_plus:^10.0f} | {home.lineup_wrc_plus:^10.0f} | {bat_edge:^11s} |")

    # Team wOBA
    woba_edge = away.code if away.team_woba > home.team_woba else home.code
    ln(f"| 打線 wOBA          | {away.team_woba:^10.3f} | {home.team_woba:^10.3f} | {woba_edge:^11s} |")

    # Defense
    def_edge = away.code if away.defense_efficiency > home.defense_efficiency else home.code
    ln(f"| 守備 DER           | {away.defense_efficiency:^10.3f} | {home.defense_efficiency:^10.3f} | {def_edge:^11s} |")

    # Running
    run_edge = away.code if away.sb_success_rate > home.sb_success_rate else home.code
    ln(f"| 跑壘 SB%           | {away.sb_success_rate:^10.0%} | {home.sb_success_rate:^10.0%} | {run_edge:^11s} |")

    # Bullpen
    bp_edge = away.code if away.bullpen_era < home.bullpen_era else home.code
    ln(f"| 牛棚 ERA           | {away.bullpen_era:^10.2f} | {home.bullpen_era:^10.2f} | {bp_edge:^11s} |")

    # Clutch wOBA
    cwoba_edge = away.code if away.clutch_woba > home.clutch_woba else home.code
    ln(f"| 高壓 Clutch wOBA   | {away.clutch_woba:^10.3f} | {home.clutch_woba:^10.3f} | {cwoba_edge:^11s} |")

    # Elo
    elo_edge = away.code if away.elo > home.elo else home.code
    ln(f"| Elo Rating         | {away.elo:^10.0f} | {home.elo:^10.0f} | {elo_edge:^11s} |")
    ln()

    # ── Starting Pitcher Duel ─────────────────────────
    ln("#### 先發投手對決")
    ln()
    ln(f"| 指標           | {match.away_sp.name:^22s} | {match.home_sp.name:^22s} |")
    ln("|" + "-" * 16 + "|" + "-" * 24 + "|" + "-" * 24 + "|")
    ln(f"| ERA            | {match.away_sp.era:^22.2f} | {match.home_sp.era:^22.2f} |")
    ln(f"| FIP            | {match.away_sp.fip:^22.2f} | {match.home_sp.fip:^22.2f} |")
    ln(f"| WHIP           | {match.away_sp.whip:^22.2f} | {match.home_sp.whip:^22.2f} |")
    ln(f"| K/9            | {match.away_sp.k_per_9:^22.1f} | {match.home_sp.k_per_9:^22.1f} |")
    ln(f"| BB/9           | {match.away_sp.bb_per_9:^22.1f} | {match.home_sp.bb_per_9:^22.1f} |")
    ln(f"| Stuff+         | {match.away_sp.stuff_plus:^22.0f} | {match.home_sp.stuff_plus:^22.0f} |")
    ln(f"| 均速 (mph)     | {match.away_sp.fastball_velo:^22.1f} | {match.home_sp.fastball_velo:^22.1f} |")
    ln(f"| 春訓 ERA       | {match.away_sp.spring_era:^22.2f} | {match.home_sp.spring_era:^22.2f} |")
    ln(f"| 近3場 ERA      | {match.away_sp.era_last_3:^22.2f} | {match.home_sp.era_last_3:^22.2f} |")
    ln(f"| vs LHB BA      | {match.away_sp.vs_left_ba:^22.3f} | {match.home_sp.vs_left_ba:^22.3f} |")
    ln(f"| vs RHB BA      | {match.away_sp.vs_right_ba:^22.3f} | {match.home_sp.vs_right_ba:^22.3f} |")
    ln(f"| 高壓 ERA       | {match.away_sp.high_leverage_era:^22.2f} | {match.home_sp.high_leverage_era:^22.2f} |")
    ln()

    # ── Pitch Count Timeline ──────────────────────────
    pc = match.pitch_count_rule
    sp_inn = pc.expected_sp_innings
    ln("#### 投手用球數限制 & 投手時間軸")
    ln()
    ln(f"- **賽程階段**: {pc.round_name}")
    ln(f"- **單場上限**: {pc.max_pitches} 球")
    ln(f"- **休息規定**: ≥30球 → 休{pc.rest_after_30}天; ≥50球 → 休{pc.rest_after_50}天")
    ln(f"- **先發預計局數**: ~{sp_inn:.1f} 局")
    ln()
    ln("| 局數   | " + f"{away.code:^14s}" + " | " + f"{home.code:^14s}" + " |")
    ln("|--------|" + "-" * 16 + "|" + "-" * 16 + "|")
    away_sp_name = match.away_sp.name.split()[-1]  # last name
    home_sp_name = match.home_sp.name.split()[-1]
    away_pb_name = match.away_piggyback.name.split()[-1] if match.away_piggyback else "Bullpen"
    home_pb_name = match.home_piggyback.name.split()[-1] if match.home_piggyback else "Bullpen"
    sp_end = int(sp_inn)
    for inn in range(1, 10):
        if inn <= sp_end:
            a_who = f"SP {away_sp_name}"
            h_who = f"SP {home_sp_name}"
        elif inn <= sp_end + 2:
            a_who = f"PB {away_pb_name}"
            h_who = f"PB {home_pb_name}"
        else:
            a_who = "Bullpen"
            h_who = "Bullpen"
        ln(f"|  {inn}局   | {a_who:^14s} | {h_who:^14s} |")
    ln()

    # ── Piggyback (第二先發) detail ───────────────────
    if match.away_piggyback or match.home_piggyback:
        ln("#### 第二先發 (Piggyback Starter)")
        ln()
        pb_a = match.away_piggyback
        pb_h = match.home_piggyback
        a_name = pb_a.name if pb_a else "N/A"
        h_name = pb_h.name if pb_h else "N/A"
        ln(f"| 指標         | {a_name:^22s} | {h_name:^22s} |")
        ln("|" + "-" * 14 + "|" + "-" * 24 + "|" + "-" * 24 + "|")
        if pb_a and pb_h:
            ln(f"| ERA          | {pb_a.era:^22.2f} | {pb_h.era:^22.2f} |")
            ln(f"| FIP          | {pb_a.fip:^22.2f} | {pb_h.fip:^22.2f} |")
            ln(f"| Stuff+       | {pb_a.stuff_plus:^22.0f} | {pb_h.stuff_plus:^22.0f} |")
            ln(f"| 春訓 ERA     | {pb_a.spring_era:^22.2f} | {pb_h.spring_era:^22.2f} |")
        ln()

    # ══════════════════════════════════════════════════════
    # 2. WIN PROBABILITY
    # ══════════════════════════════════════════════════════
    ln("### 2. 勝率預測與比分分佈")
    ln()
    ln("#### Ensemble Model 各模型輸出")
    ln()
    subs = ensemble_details.get("sub_models", {})
    ln("| Model         | " + f"{away.code:>8s}" + " | " + f"{home.code:>8s}" + " |")
    ln("|" + "-" * 15 + "|" + "-" * 10 + "|" + "-" * 10 + "|")
    for mname in ["elo", "bayesian", "poisson", "gbm", "monte_carlo"]:
        sm = subs.get(mname, {})
        ln(f"| {mname:<13s} | {_pct(sm.get('away', 0)):>8s} | {_pct(sm.get('home', 0)):>8s} |")
    ln("|" + "-" * 15 + "|" + "-" * 10 + "|" + "-" * 10 + "|")
    ln(f"| **Ensemble**  | **{_pct(away_wp):>5s}** | **{_pct(home_wp):>5s}** |")
    ln()

    # WBC adjustments
    ln("#### WBC 修正係數")
    ln()
    for k, v in wbc_details.items():
        ln(f"- {k}: `{v}`")
    ln()

    # ── Score prediction ──────────────────────────────
    ln("#### 比分預測")
    ln()
    top5 = mc_details.get("top5_scores", [])
    if top5:
        ln(f"| 排名 | 比分 ({away.code}-{home.code}) | 機率     |")
        ln("|------|" + "-" * 22 + "|----------|")
        for i, (score, prob) in enumerate(top5, 1):
            ln(f"|  {i}   | {score:^20s} | {_pct(prob):>8s} |")
    ln()

    # Most likely score
    if top5:
        best_score = top5[0][0]
        ln(f"**最可能比分 (Most Likely Score):** `{best_score}` ({away.code}-{home.code})")
    ln()

    # Total runs
    total_mu = mc_details.get("total_runs_avg", 0)
    ln(f"**預測總分:** {total_mu:.1f} 分")
    ln()

    # ── Multi-Scenario Analysis ───────────────────────
    scenarios = mc_details.get("scenarios", {})
    if scenarios:
        ln("#### 多維度情境分析 (Multi-Scenario Analysis)")
        ln()
        ln("> [!NOTE]")
        ln("> 基於 WBC 2026 模擬引擎輸出的三種情境預案：")
        ln()
        ln("| 情境 (Scenario) | 預計總分 | 特徵描述 |")
        ln("|:---|:---:|:---|")
        ln(f"| **中性基準 (Baseline)** | {scenarios.get('baseline', 0):.0f} | 雙方發揮正常，符合實力常態分佈。 |")
        ln(f"| **投手戰 (Pitching Duel)** | {scenarios.get('pitching_duel', 0):.0f} | 先發投手壓制力極大化，且牛棚銜接完美。 |")
        ln(f"| **打線爆發 (Explosion)** | {scenarios.get('explosion', 0):.0f} | 觸發連續得分鏈，弱方防禦體系崩潰。 |")
        ln()
        ln(f"**模擬平均局數:** {scenarios.get('avg_innings', 9.0):.1f} 局 (含 Mercy Rule 影響)")
        ln()

    # O/U probabilities vs common lines
    total_dist = mc_details.get("total_runs_distribution", {})
    if total_dist:
        ln("#### 總分分佈 (O/U 機率)")
        ln()
        ln("| 盤口 (Line) | Over 機率 | Under 機率 |")
        ln("|-------------|-----------|------------|")
        for line_val in [6.5, 7.5, 8.5, 9.5]:
            over_p = sum(
                v for k, v in total_dist.items() if int(k) > line_val
            )
            under_p = 1.0 - over_p
            ln(f"| {line_val:>11.1f} | {_pct(over_p):>9s} | {_pct(under_p):>10s} |")
        ln()

    # Extra innings probability
    poi_dist_a = poisson_details.get("dist_away", [])
    poi_dist_h = poisson_details.get("dist_home", [])
    if poi_dist_a and poi_dist_h:
        tie_prob = sum(
            poi_dist_a[i] * poi_dist_h[i]
            for i in range(min(len(poi_dist_a), len(poi_dist_h)))
        )
        ln(f"**延長賽機率 (Extra Innings):** {_pct(tie_prob)}")
        ln()

    # Upset chance
    upset_team = home.code if away_wp > home_wp else away.code
    upset_prob = min(away_wp, home_wp)
    ln(f"**爆冷機率 ({upset_team} 獲勝):** {_pct(upset_prob)}")
    ln()

    # ══════════════════════════════════════════════════════
    # 3. TAIWAN SPORTS LOTTERY (TSL) BETTING RECOMMENDATIONS
    # ══════════════════════════════════════════════════════
    ln("### 3. 台灣運彩 (TSL) 下注建議")
    ln()

    # Find best bet
    actionable = [b for b in value_bets if b.edge_tier != "PASS"]

    # Helper to render bet lines
    def _render_bet(b: ValueBet, show_line: bool = False):
        symbol = "✅" if b.ev > 0.03 else "⚠️" if b.ev > 0 else "❌"
        line_str = f" ({b.line:+.1f})" if show_line and b.line is not None else ""
        ln(f"- {symbol} **{b.side}{line_str}** @ {_fmt_odds(b.decimal_odds)} ({b.book})")
        ln(f"  - 隱含機率: {_pct(b.implied_prob)} | 模型真實機率: {_pct(b.true_prob)}")
        ln(f"  - 期望值 (EV): {_signed_pct(b.ev)} → **{b.edge_tier}**")

    # ── 不讓分 (Money Line) ──
    ml_bets = [b for b in value_bets if b.market == "ML"]
    ln("#### 不讓分（獨贏）Money Line")
    if ml_bets:
        for b in ml_bets:
            _render_bet(b)
    else:
        ln("- 無盤口數據")
    ln()

    # ── 讓分 (Run Line) ──
    rl_bets = [b for b in value_bets if b.market == "RL"]
    ln("#### 讓分 Run Line / Spread")
    if rl_bets:
        for b in rl_bets:
            _render_bet(b, show_line=True)
    else:
        ln("- 無盤口數據")
    ln()

    # ── 大小分 (Over/Under) ──
    ou_bets = [b for b in value_bets if b.market == "OU"]
    ln("#### 大小分 Over/Under")
    if ou_bets:
        for b in ou_bets:
            line_str = f" {b.line}" if b.line else ""
            symbol = "✅" if b.ev > 0.03 else "⚠️" if b.ev > 0 else "❌"
            ln(f"- {symbol} **{b.side}{line_str}** @ {_fmt_odds(b.decimal_odds)} ({b.book})")
            ln(f"  - EV: {_signed_pct(b.ev)} → **{b.edge_tier}**")
    else:
        ln("- 無盤口數據")
    ln()

    # ── 單雙 (Odd/Even) ──
    oe_bets = [b for b in value_bets if b.market == "OE"]
    ln("#### 單雙 Odd/Even（總分奇偶）")
    if oe_bets:
        for b in oe_bets:
            side_zh = "單（奇數）" if b.side == "Odd" else "雙（偶數）"
            symbol = "✅" if b.ev > 0.03 else "⚠️" if b.ev > 0 else "❌"
            ln(f"- {symbol} **{side_zh}** @ {_fmt_odds(b.decimal_odds)} ({b.book})")
            ln(f"  - 隱含機率: {_pct(b.implied_prob)} | 模型機率: {_pct(b.true_prob)}")
            ln(f"  - EV: {_signed_pct(b.ev)} → **{b.edge_tier}**")
    else:
        ln("- 無盤口數據")
    ln()

    # ── 前五局 (First 5 Innings) ──
    f5_bets = [b for b in value_bets if b.market == "F5"]
    ln("#### 前五局獨贏 First 5 Innings")
    if f5_bets:
        for b in f5_bets:
            _render_bet(b)
    else:
        ln("- 無盤口數據")
    ln()

    # ── 隊伍總分 (Team Totals) ──
    tt_bets = [b for b in value_bets if b.market == "TT"]
    if tt_bets:
        ln("#### 隊伍總分 Team Totals")
        for b in tt_bets:
            line_str = f" {b.line}" if b.line else ""
            symbol = "✅" if b.ev > 0.03 else "⚠️" if b.ev > 0 else "❌"
            ln(f"- {symbol} **{b.market} {b.side}{line_str}** @ {_fmt_odds(b.decimal_odds)} ({b.book})")
            ln(f"  - EV: {_signed_pct(b.ev)} → **{b.edge_tier}**")
        ln()

    # ══════════════════════════════════════════════════════
    # BETTING DECISION (Best Bet)
    # ══════════════════════════════════════════════════════
    ln("-" * 50)
    ln("### BETTING DECISION")
    ln()

    if portfolio:
        best = portfolio[0]
        bb = best.bet
        confidence = min(1.0, bb.ev * 5 + 0.5)
        ln(f"**Best Bet:** {bb.market} {bb.side} "
           f"{'(' + str(bb.line) + ') ' if bb.line else ''}"
           f"@ {_fmt_odds(bb.decimal_odds)} ({bb.book})")
        ln(f"- True Probability: {_pct(bb.true_prob)}")
        ln(f"- Implied Probability: {_pct(bb.implied_prob)}")
        ln(f"- **EV: {_signed_pct(bb.ev)}**")
        if "Restricted" in bb.edge_tier:
            ln(f"- **Warning**: This market has been restricted due to historical negative ROI.")
        if "SECONDARY" in bb.edge_tier:
            ln(f"- **Warning**: Edge calculation is extremely high. Secondary validation required.")
        ln(f"- Stake: {best.stake_pct:.2%} of bankroll = **${best.stake_amount:,.0f}**")
        ln(f"  (Kelly Full: {best.kelly_full:.4f} → Used: {best.kelly_used:.4f})")
        ln()
        ln(f"**Confidence:** {_stars(confidence)}")
    else:
        ln("**No actionable bets found — all markets below EV threshold.**")
    ln()

    # ══════════════════════════════════════════════════════
    # AI RATIONALE (WHY RECOMMEND?)
    # ══════════════════════════════════════════════════════
    ln("-" * 50)
    ln("### AI 推薦原因 (AI Rationale)")
    ln()
    reasons = rationalize_recommendation(match, away_wp, home_wp, ensemble_details, value_bets)
    for r in reasons:
        ln(f"- {r}")
    ln()

    # ══════════════════════════════════════════════════════
    # 4. X-FACTORS
    # ══════════════════════════════════════════════════════
    ln("### 4. 關鍵變數 (X-Factors)")
    ln()
    factors = _identify_x_factors(match, away_wp, home_wp, wbc_details)
    for i, f in enumerate(factors, 1):
        ln(f"{i}. {f}")
    ln()

    # ══════════════════════════════════════════════════════
    # 5. ROSTER STRENGTH (陣容完整度)
    # ══════════════════════════════════════════════════════
    ln("### 5. 陣容完整度 (Roster Strength)")
    ln()
    rv_a = away.roster_vol
    rv_h = home.roster_vol
    if rv_a and rv_h:
        ln(f"| 指標              | {away.code:^14s} | {home.code:^14s} |")
        ln("|" + "-" * 19 + "|" + "-" * 16 + "|" + "-" * 16 + "|")
        ln(f"| RSI (0-100)       | {rv_a.roster_strength_index:^14.0f} | {rv_h.roster_strength_index:^14.0f} |")
        ln(f"| MLB 球員數        | {rv_a.mlb_player_count:^14d} | {rv_h.mlb_player_count:^14d} |")
        ln(f"| 磨合度 Chemistry  | {rv_a.team_chemistry:^14.2f} | {rv_h.team_chemistry:^14.2f} |")
        ln()
        if rv_a.confirmed_stars:
            ln(f"**{away.code} 確認出賽球星**: {', '.join(rv_a.confirmed_stars)}")
        if rv_a.uncertain_stars:
            ln(f"**{away.code} 待確認球星**:  {', '.join(rv_a.uncertain_stars)}")
        if rv_a.absent_stars:
            ln(f"**{away.code} 缺席球星**:    {', '.join(rv_a.absent_stars)}")
        ln()
        if rv_h.confirmed_stars:
            ln(f"**{home.code} 確認出賽球星**: {', '.join(rv_h.confirmed_stars)}")
        if rv_h.uncertain_stars:
            ln(f"**{home.code} 待確認球星**:  {', '.join(rv_h.uncertain_stars)}")
        if rv_h.absent_stars:
            ln(f"**{home.code} 缺席球星**:    {', '.join(rv_h.absent_stars)}")
        ln()

        rsi_gap = rv_a.roster_strength_index - rv_h.roster_strength_index
        if abs(rsi_gap) > 10:
            stronger = away.code if rsi_gap > 0 else home.code
            ln(f"> ⚠️ **陣容差距**: {stronger} RSI 高出 {abs(rsi_gap):.0f} 分，")
            ln(f">    MLB 球員數量與球星密度有明顯優勢。")
            ln()
    else:
        ln("- 尚無陣容完整度數據。")
        ln()

    # ══════════════════════════════════════════════════════
    # RISK STATUS
    # ══════════════════════════════════════════════════════
    ln("-" * 50)
    ln(f"### Risk Status: {risk_status.risk_level}")
    ln()
    if risk_status.allow_betting:
        ln("🟢 **Betting ALLOWED**")
    else:
        ln("🔴 **Betting SUSPENDED**")
    for r in risk_status.reasons:
        ln(f"- {r}")
    ln()

    # ══════════════════════════════════════════════════════
    # PORTFOLIO SUMMARY
    # ══════════════════════════════════════════════════════
    ln("-" * 50)
    ln("### PORTFOLIO SUMMARY")
    ln()
    total_stake = sum(p.stake_amount for p in portfolio)
    total_risk_pct = sum(p.stake_pct for p in portfolio)
    weighted_ev = (
        sum(p.bet.ev * p.stake_amount for p in portfolio) / total_stake
        if total_stake > 0 else 0
    )
    ln(f"- **Total Bets Today:** {len(portfolio)}")
    ln(f"- **Total Risk:** {total_risk_pct:.2%} of bankroll (${total_stake:,.0f})")
    ln(f"- **Bankroll:** ${bankroll.current:,.0f}")
    ln(f"- **Conservative Mode:** {'Yes' if bankroll.conservative_mode else 'No'}")
    ln(f"- **Expected ROI (weighted):** {_signed_pct(weighted_ev)}")
    ln()
    if portfolio:
        ln("| # | Market | Side | Odds | EV | Stake | Amount |")
        ln("|---|--------|------|------|----|-------|--------|")
        for i, p in enumerate(portfolio, 1):
            ln(f"| {i} | {p.bet.market} | {p.bet.side} | "
               f"{_fmt_odds(p.bet.decimal_odds)} | {_signed_pct(p.bet.ev)} | "
               f"{p.stake_pct:.2%} | ${p.stake_amount:,.0f} |")
    ln()
    ln("=" * 70)
    ln("  END OF REPORT — Generated by WBC Quantitative Betting AI Engine")
    ln("=" * 70)

    return "\n".join(lines)


def _identify_x_factors(
    match: MatchData,
    away_wp: float,
    home_wp: float,
    wbc_details: Dict,
) -> List[str]:
    """Auto-generate key game factors including WBC-specific rules."""
    factors = []
    
    # 0. Data warnings
    data_src = getattr(match, 'data_source', '')
    if "MOCK" in data_src.upper() or "SEED" in data_src.upper():
        factors.append("⚠️ **資料真實性警示**: 目前盤口/球員數據依賴預先設定之 SEED，尚未經真實市場深度校驗，存在嚴重高估 Edge 的風險。")

    # 1. Pitch-count limit impact
    pc = match.pitch_count_rule
    factors.append(
        f"🔑 **用球數限制 (Pitch Count)**: {pc.round_name} 階段上限 {pc.max_pitches} 球，"
        f"{match.away_sp.name} 與 {match.home_sp.name} 預計僅投 ~{pc.expected_sp_innings:.1f} 局 "
        f"(約 15~18 球/局)。第 {int(pc.expected_sp_innings)+1} 局起由第二先發接手，"
        f"比賽後半段完全由牛棚主導。"
    )

    # 2. Piggyback quality
    if match.away_piggyback and match.home_piggyback:
        pb_a = match.away_piggyback
        pb_h = match.home_piggyback
        better_pb = match.away.code if pb_a.era < pb_h.era else match.home.code
        factors.append(
            f"🔑 **第二先發 (Piggyback)**: {pb_a.name} (ERA {pb_a.era:.2f}) vs "
            f"{pb_h.name} (ERA {pb_h.era:.2f}) — "
            f"{better_pb} 的第二先發品質較佳，中段比賽有優勢。"
        )

    # 3. Bullpen fatigue
    bp_away_total = sum(p.pitch_count_last_3d for p in match.away_bullpen)
    bp_home_total = sum(p.pitch_count_last_3d for p in match.home_bullpen)
    if bp_away_total == 0 and bp_home_total == 0:
        factors.append(
            f"🔑 **牛棚疲勞度**: 兩隊牛棚近 3 日用球數均為 0 (Pool 首戰)，"
            f"牛棚狀態新鮮，可全力調度。"
        )
    else:
        tired = match.home.code if bp_home_total > bp_away_total else match.away.code
        factors.append(
            f"🔑 **牛棚疲勞度**: {tired} 近 3 日牛棚用球數較高 "
            f"({match.away.code}: {bp_away_total}, {match.home.code}: {bp_home_total})，"
            f"後段比賽可能出現失分風險。"
        )

    # 4. Key batter vs fastball speed
    if match.away_lineup and match.home_lineup:
        best_away = max(match.away_lineup, key=lambda b: b.ops)
        best_home = max(match.home_lineup, key=lambda b: b.ops)
        factors.append(
            f"🔑 **打線核心對決**: {best_away.name} (wOBA {best_away.woba:.3f}, "
            f"SwStr% vs 98mph+ {best_away.swstr_vs_98:.1f}%) vs "
            f"{best_home.name} (wOBA {best_home.woba:.3f}, "
            f"SwStr% vs 98mph+ {best_home.swstr_vs_98:.1f}%)"
        )

    # 5. Star player effect
    rv_a = match.away.roster_vol
    rv_h = match.home.roster_vol
    if rv_a and rv_h:
        all_stars = rv_a.confirmed_stars + rv_h.confirmed_stars
        if all_stars:
            factors.append(
                f"🔑 **球星效應**: 本場確認參賽球星 — "
                + ", ".join(all_stars[:6])
                + (f" 等 {len(all_stars)} 人" if len(all_stars) > 6 else "")
                + "，球星表現將直接影響勝負走勢。"
            )

    # 6. Elo gap
    elo_gap = abs(match.away.elo - match.home.elo)
    if elo_gap > 30:
        stronger = match.away.code if match.away.elo > match.home.elo else match.home.code
        factors.append(
            f"🔑 **Elo 差距**: {stronger} 高出 {elo_gap:.0f} 分，"
            f"歷史勝率優勢明顯，但 WBC 短期賽制與 {match.pitch_count_rule.max_pitches} 球限制增加爆冷機率。"
        )

    return factors
