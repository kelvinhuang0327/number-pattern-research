"""Compact real-data-first report formatter."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional
from strategy.value_detector import ValueBet
from strategy.kelly_criterion import BetSizing, BankrollState
from strategy.sharp_detector import MarketSignal
from strategy.risk_control import RiskStatus
from data.wbc_data import MatchData
from data.tsl_snapshot import get_tsl_summary
from wbc_backend.data.wbc_verification import VerificationResult
from wbc_backend.ux.report_style import build_report_header, render_report_banner


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

NA = "無資料"


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _safe_getattr(obj: object, field: str) -> object | None:
    return getattr(obj, field, None) if obj is not None else None


def _contains_untrusted_source(data_source: str) -> bool:
    source = (data_source or "").upper()
    return any(token in source for token in ("MOCK", "SEED", "MIXED"))


def _format_game_type(match: MatchData) -> str:
    if "POOL" in (match.round_name or "").upper() or "WBC" in (match.venue or "").upper():
        return "WBC"
    return "MLB"


def _format_game_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value or NA


def _pick_market(odds: List, book: str, market: str) -> List:
    return [line for line in odds if line.book == book and line.market == market]


def _first_line_text(lines: List[object], *, team_a: str, team_b: str) -> str:
    if not lines:
        return NA
    parts: List[str] = []
    for line in lines[:2]:
        side = getattr(line, "side", "")
        price = _safe_getattr(line, "price") or _safe_getattr(line, "decimal_odds")
        handicap = _safe_getattr(line, "line")
        if side == "Over":
            label = f"Over {handicap}" if handicap is not None else "Over"
        elif side == "Under":
            label = f"Under {handicap}" if handicap is not None else "Under"
        elif side == "Odd":
            label = "單"
        elif side == "Even":
            label = "雙"
        elif side == team_a:
            label = team_a
        elif side == team_b:
            label = team_b
        else:
            label = str(side)
        if handicap is not None and market_needs_line(getattr(line, "market", "")) and side not in ("Over", "Under"):
            label = f"{label} {handicap:+.1f}"
        parts.append(f"{label} {_fmt_float(float(price), 2)}")
    return " / ".join(parts) if parts else NA


def market_needs_line(market: str) -> bool:
    return market in {"RL", "TT"}


def _trusted_analysis_allowed(
    match: MatchData,
    verification_result: VerificationResult | None,
) -> bool:
    return (
        verification_result is not None
        and not verification_result.blocking
        and not _contains_untrusted_source(getattr(match, "data_source", ""))
    )


def _trusted_odds_allowed(
    match: MatchData,
    verification_result: VerificationResult | None,
    tsl_status: dict | None,
) -> bool:
    if tsl_status and tsl_status.get("success") is False:
        return False
    return True


def _translate_issue(code: str, message: str) -> str:
    mapping = {
        "starters_verified": "先發投手尚未完成官方驗證。",
        "lineups_fallback_previous_game": "官方先發打線尚未公布，目前沒有可用正式名單。",
        "lineups_verified": "先發打線尚未完成官方驗證。",
        "stale_authoritative_snapshot": "權威快照已過期，需先更新資料。",
        "home_sp_mismatch": "主隊先發資料與權威快照不一致。",
        "away_sp_mismatch": "客隊先發資料與權威快照不一致。",
        "seed_source_detected": "資料來源仍含 seed，不能作為正式投注依據。",
    }
    return mapping.get(code, message or NA)


# ──────────────────────────────────────────────────────────
# Main report builder
# ──────────────────────────────────────────────────────────

def build_report(
    match: MatchData,
    away_wp: Optional[float],
    home_wp: Optional[float],
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
    verification_result: VerificationResult | None = None,
    tsl_status: dict | None = None,
) -> str:
    """Return the user-requested concise report."""

    away = match.away
    home = match.home
    lines: List[str] = []

    def ln(s: str = ""):
        lines.append(s)

    trusted_analysis = _trusted_analysis_allowed(match, verification_result)
    trusted_odds = _trusted_odds_allowed(match, verification_result, tsl_status)
    snapshot = verification_result.snapshot_game if verification_result else {}
    starter_verified = bool(snapshot.get("verification", {}).get("starters_verified")) if snapshot else False

    away_starter_name = NA
    home_starter_name = NA
    if starter_verified:
        away_starter_name = snapshot.get("away_sp", {}).get("name") or NA
        home_starter_name = snapshot.get("home_sp", {}).get("name") or NA

    intl_ml = _first_line_text(_pick_market(match.odds, "Pinnacle", "ML"), team_a=away.code, team_b=home.code) if trusted_odds else NA
    intl_rl = _first_line_text(_pick_market(match.odds, "Pinnacle", "RL"), team_a=away.code, team_b=home.code) if trusted_odds else NA
    intl_ou = _first_line_text(_pick_market(match.odds, "Pinnacle", "OU"), team_a=away.code, team_b=home.code) if trusted_odds else NA

    tsl_snapshot = get_tsl_summary(away.code, home.code) if tsl_status and tsl_status.get("success") else {}
    tsl_ml = tsl_snapshot.get("ML", NA)
    tsl_rl = tsl_snapshot.get("RL", NA)
    tsl_ou = tsl_snapshot.get("OU", NA)

    actionable = [
        sizing.bet for sizing in portfolio
        if sizing.bet.edge_tier != "PASS"
    ]

    report_header = build_report_header(
        title="WBC MATCH REPORT",
        mode="WBC",
        safety="PRODUCTION",
        purpose="official WBC analysis and betting decision support",
        scope=_format_game_type(match),
        source="report/formatter.py",
        status="production / verified" if trusted_analysis else "blocked / incomplete",
    )
    lines.append(render_report_banner(report_header).rstrip())
    lines.append("")

    summary_lines: List[str]
    if trusted_analysis and away_wp is not None and home_wp is not None:
        stronger = away.name if away_wp > home_wp else home.name
        weaker = home.name if away_wp > home_wp else away.name
        pitcher_edge = NA
        if starter_verified:
            pitcher_edge = away.name if away_wp > home_wp else home.name
        summary_lines = [
            f"- 戰力差距：{stronger} 較優，{weaker} 相對劣勢。",
            f"- 投手優勢：{pitcher_edge if pitcher_edge != NA else NA}",
            f"- 打線優勢：{NA}",
            f"- 可能比賽節奏：{market_headline if market_headline else NA}",
        ]
    else:
        summary_lines = ["- 無資料"]

    risks = []
    if verification_result and verification_result.issues:
        for issue in verification_result.issues[:2]:
            risks.append(_translate_issue(issue.code, issue.message))
    if tsl_status and tsl_status.get("success") is False:
        risks.append(f"台灣運彩抓取失敗：{tsl_status.get('error') or NA}")
    if _contains_untrusted_source(getattr(match, "data_source", "")):
        risks.append("資料來源含 seed 或混合資料，模型輸出已停用。")
    if not risks:
        risks = ["無資料"]

    def _bet_block(index: int) -> tuple[str, str]:
        if len(actionable) > index:
            bet = actionable[index]
            line_text = f" {bet.line:+.1f}" if bet.line is not None and bet.market in {"RL", "TT", "OU"} else ""
            bet_name = f"{bet.market} {bet.side}{line_text} @ {_fmt_float(bet.decimal_odds, 2)}"
            reason = f"EV {_pct(bet.ev)}，且通過目前資料驗證。"
            return bet_name, reason
        return NA, NA

    best_bet, best_reason = _bet_block(0)
    second_bet, second_reason = _bet_block(1)
    third_bet, third_reason = _bet_block(2)

    ln("# ⚾ 賽事對戰")
    ln()
    ln("對戰組合：")
    ln(f"{away.name} vs {home.name}")
    ln()
    ln("比賽類型：")
    ln(_format_game_type(match))
    ln()
    ln("比賽時間：")
    ln(_format_game_time(match.game_time))
    ln()
    ln("---")
    ln()
    ln("# 📊 戰力指數對比")
    ln()
    ln(f"| 指標 | {away.name} | {home.name} |")
    ln("|-----|-----|-----|")
    if trusted_analysis:
        ln(f"| 綜合戰力指數 | {_fmt_float(float(away.elo), 0)} | {_fmt_float(float(home.elo), 0)} |")
        ln(f"| 打擊戰力 | {_fmt_float(float(away.lineup_wrc_plus), 0)} | {_fmt_float(float(home.lineup_wrc_plus), 0)} |")
        ln(f"| 投手戰力 | {_fmt_float(float(match.away_sp.era), 2)} | {_fmt_float(float(match.home_sp.era), 2)} |")
        ln(f"| 牛棚深度 | {_fmt_float(float(away.bullpen_era), 2)} | {_fmt_float(float(home.bullpen_era), 2)} |")
        ln(f"| 防守能力 | {_fmt_float(float(away.defense_efficiency), 3)} | {_fmt_float(float(home.defense_efficiency), 3)} |")
    else:
        for label in ["綜合戰力指數", "打擊戰力", "投手戰力", "牛棚深度", "防守能力"]:
            ln(f"| {label} | {NA} | {NA} |")
    ln()
    ln("---")
    ln()
    ln("# 🧢 先發投手")
    ln()
    ln(f"| 項目 | {away.name} | {home.name} |")
    ln("|-----|-----|-----|")
    ln(f"| 先發投手 | {away_starter_name} | {home_starter_name} |")
    if trusted_analysis and starter_verified and not _contains_untrusted_source(getattr(match, 'data_source', '')):
        ln(f"| ERA | {_fmt_float(float(match.away_sp.era), 2)} | {_fmt_float(float(match.home_sp.era), 2)} |")
        ln(f"| WHIP | {_fmt_float(float(match.away_sp.whip), 2)} | {_fmt_float(float(match.home_sp.whip), 2)} |")
        ln(f"| K/9 | {_fmt_float(float(match.away_sp.k_per_9), 1)} | {_fmt_float(float(match.home_sp.k_per_9), 1)} |")
    else:
        ln(f"| ERA | {NA} | {NA} |")
        ln(f"| WHIP | {NA} | {NA} |")
        ln(f"| K/9 | {NA} | {NA} |")
    ln()
    ln("---")
    ln()
    ln("# 🌎 國外盤口（International Odds）")
    ln()
    ln("來源：")
    ln("Pinnacle / major sportsbooks")
    ln()
    ln("| 項目 | 數值 |")
    ln("|-----|-----|")
    ln(f"| Moneyline | {intl_ml} |")
    ln(f"| Run Line | {intl_rl} |")
    ln(f"| Total | {intl_ou} |")
    ln()
    ln("---")
    ln()
    ln("# 🇹🇼 台灣運彩盤口（TSL）")
    ln()
    ln("| 項目 | 數值 |")
    ln("|-----|-----|")
    ln(f"| 不讓分 | {tsl_ml} |")
    ln(f"| 讓分 | {tsl_rl} |")
    ln(f"| 大小分 | {tsl_ou} |")
    ln()
    ln("---")
    ln()
    ln("# 🧠 模型分析摘要")
    ln()
    for item in summary_lines[:4]:
        ln(item)
    ln()
    ln("---")
    ln()
    ln("# 💰 投注建議")
    ln()
    ln("依照模型優勢排序。")
    ln()
    ln("### 🥇 最佳投注")
    ln(best_bet)
    ln()
    ln("原因：")
    ln(best_reason)
    ln()
    ln("---")
    ln()
    ln("### 🥈 次佳投注")
    ln(second_bet)
    ln()
    ln("原因：")
    ln(second_reason)
    ln()
    ln("---")
    ln()
    ln("### 🥉 第三投注")
    ln(third_bet)
    ln()
    ln("原因：")
    ln(third_reason)
    ln()
    ln("---")
    ln()
    ln("# ⚠️ 風險提醒")
    ln()
    for risk in risks[:3]:
        ln(f"- {risk}")
    return "\n".join(lines)
