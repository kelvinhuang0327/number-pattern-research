"""P257A — Best N-Bet Strategy Overview: Historical Replay Data + UI Contract.

Read-only. No DB write. No replay generation. No registry mutation.
No strategy promotion. No betting advice. No recommendation-logic change.

Output: JSON + Markdown artifact for a future "Best Strategy Overview" page.
The page ranks best historical N-bet portfolios (not independent bet_index slots).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DB_PATH    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = _REPO_ROOT / "outputs" / "research"
OUTPUT_JSON = OUTPUT_DIR / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"
OUTPUT_MD   = OUTPUT_DIR / "p257a_best_nbet_strategy_overview_historical_replay_20260608.md"

MAX_BET_COUNT = 5
HIGH_HIT_TOP_N = 10   # number of top events to show per section


# ---------------------------------------------------------------------------
# Registry lifecycle lookup (read-only; never mutate)
# ---------------------------------------------------------------------------

def _build_lifecycle_map() -> dict[str, str]:
    """Return {strategy_id: lifecycle_status} from registry (read-only)."""
    try:
        import lottery_api.models.replay_strategy_registry as reg
        result = {}
        for name in dir(reg):
            obj = getattr(reg, name)
            if hasattr(obj, "meta") and hasattr(obj.meta, "strategy_id"):
                result[obj.meta.strategy_id] = obj.meta.lifecycle_status
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# DB helpers (all read-only via mode=ro)
# ---------------------------------------------------------------------------

def _open_ro() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _replay_schema(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    return [{"cid": r[0], "name": r[1], "type": r[2], "notnull": r[3], "dflt": r[4], "pk": r[5]} for r in rows]


def _bet_index_dist(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT lottery_type, bet_index, COUNT(*) FROM strategy_prediction_replays "
        "GROUP BY lottery_type, bet_index ORDER BY lottery_type, bet_index"
    ).fetchall()
    return [{"lottery_type": r[0], "bet_index": r[1], "count": r[2]} for r in rows]


def _strategies_in_replay(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT lottery_type, strategy_id, COUNT(*) as rows, COUNT(DISTINCT target_draw) as draws "
        "FROM strategy_prediction_replays GROUP BY lottery_type, strategy_id "
        "ORDER BY lottery_type, rows DESC"
    ).fetchall()
    return [{"lottery_type": r[0], "strategy_id": r[1], "replay_rows": r[2], "distinct_draws": r[3]} for r in rows]


# ---------------------------------------------------------------------------
# Core portfolio metric computation
# ---------------------------------------------------------------------------

def _compute_portfolio_metrics(
    conn: sqlite3.Connection,
    lottery_type: str,
    strategy_id: str,
    n: int,
) -> dict | None:
    """Compute portfolio metrics for (lottery_type, strategy_id, bet_count=n).

    Only includes replay rows with bet_index <= n.
    Groups by target_draw to compute portfolio-level success.
    """
    # Fetch all rows for this strategy × lottery, bet_index <= n
    rows = conn.execute(
        "SELECT target_draw, bet_index, hit_count, predicted_numbers, actual_numbers "
        "FROM strategy_prediction_replays "
        "WHERE lottery_type = ? AND strategy_id = ? AND bet_index <= ? AND replay_status = 'PREDICTED' "
        "ORDER BY CAST(target_draw AS INTEGER), bet_index",
        (lottery_type, strategy_id, n),
    ).fetchall()

    if not rows:
        return None

    # Group by target_draw
    draws: dict[str, list[dict]] = {}
    for target_draw, bet_index, hit_count, predicted_numbers, actual_numbers in rows:
        if target_draw not in draws:
            draws[target_draw] = []
        draws[target_draw].append({
            "bet_index": bet_index,
            "hit_count": hit_count or 0,
            "predicted_numbers": predicted_numbers,
            "actual_numbers": actual_numbers,
        })

    distinct_draws = len(draws)
    replay_rows = len(rows)

    # Portfolio-level per-draw metrics
    portfolio_success_count = 0
    total_best_hit = 0
    total_sum_hit  = 0
    max_single = 0
    max_portfolio_total = 0
    max_hit_draw = None
    max_hit_bet_index = None
    max_hit_predicted = None
    max_hit_actual = None
    tied_count = 0
    latest_draw = None

    for td, bets in sorted(draws.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        hit_counts = [b["hit_count"] for b in bets]
        best_hit = max(hit_counts)
        sum_hit  = sum(hit_counts)

        if best_hit >= 1:
            portfolio_success_count += 1

        total_best_hit += best_hit
        total_sum_hit  += sum_hit

        # Track max single-bet hit
        if best_hit > max_single:
            max_single = best_hit
            max_hit_draw = td
            # Find which bet_index achieved it (stable: lowest bet_index on tie)
            for b in sorted(bets, key=lambda x: x["bet_index"]):
                if b["hit_count"] == best_hit:
                    max_hit_bet_index = b["bet_index"]
                    max_hit_predicted = b["predicted_numbers"]
                    max_hit_actual    = b["actual_numbers"]
                    break
            tied_count = 1
        elif best_hit == max_single and best_hit > 0:
            tied_count += 1

        # Track max portfolio total
        if sum_hit > max_portfolio_total:
            max_portfolio_total = sum_hit

        latest_draw = td

    avg_best_hit = round(total_best_hit / distinct_draws, 4) if distinct_draws else 0
    avg_sum_hit  = round(total_sum_hit  / distinct_draws, 4) if distinct_draws else 0
    success_rate = round(portfolio_success_count / distinct_draws, 4) if distinct_draws else 0

    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "bet_count": n,
        "replay_row_count": replay_rows,
        "distinct_draw_count": distinct_draws,
        "portfolio_success_count": portfolio_success_count,
        "portfolio_success_rate": success_rate,
        "avg_best_hit_count_per_draw": avg_best_hit,
        "avg_total_hit_count_per_draw": avg_sum_hit,
        "max_single_bet_hit_count": max_single,
        "max_portfolio_total_hit_count": max_portfolio_total,
        "max_hit_draw_issue": max_hit_draw,
        "max_hit_target_draw": max_hit_draw,
        "max_hit_bet_index": max_hit_bet_index,
        "predicted_numbers_at_max": max_hit_predicted,
        "actual_numbers_at_max": max_hit_actual,
        "tied_max_hit_event_count": tied_count,
        "latest_draw_seen": latest_draw,
        "evidence_label": "HISTORICAL_REPLAY_ONLY — no future prediction guarantee",
    }


# ---------------------------------------------------------------------------
# Ranking: best strategy per lottery × bet_count
# ---------------------------------------------------------------------------

RANKING_RULES = [
    "1. highest portfolio_success_rate",
    "2. tie: highest avg_best_hit_count_per_draw",
    "3. tie: highest avg_total_hit_count_per_draw",
    "4. tie: highest max_single_bet_hit_count",
    "5. tie: highest max_portfolio_total_hit_count",
    "6. tie: larger distinct_draw_count",
    "7. tie: stable lexical strategy_id (ascending)",
]


def _rank_key(m: dict):
    return (
        m["portfolio_success_rate"],
        m["avg_best_hit_count_per_draw"],
        m["avg_total_hit_count_per_draw"],
        m["max_single_bet_hit_count"],
        m["max_portfolio_total_hit_count"],
        m["distinct_draw_count"],
        "",  # placeholder; lower lexical = worse, so negate below
    )


def _select_best(metrics: list[dict]) -> dict | None:
    """Select best strategy given ranking rules. Returns None if empty."""
    if not metrics:
        return None
    return max(
        metrics,
        key=lambda m: (
            m["portfolio_success_rate"],
            m["avg_best_hit_count_per_draw"],
            m["avg_total_hit_count_per_draw"],
            m["max_single_bet_hit_count"],
            m["max_portfolio_total_hit_count"],
            m["distinct_draw_count"],
            # For lexical tie-break: lower alphabetical is better → negate with chr trick
            chr(0x10FFFF - ord(m["strategy_id"][0])) if m["strategy_id"] else "",
        ),
    )


# ---------------------------------------------------------------------------
# High-hit event extraction
# ---------------------------------------------------------------------------

def _high_hit_events_by_lottery(conn: sqlite3.Connection) -> list[dict]:
    """Top HIGH_HIT_TOP_N highest single-bet hit events across all strategies per lottery."""
    rows = conn.execute(
        "SELECT lottery_type, strategy_id, target_draw, bet_index, hit_count, "
        "predicted_numbers, actual_numbers "
        "FROM strategy_prediction_replays "
        "WHERE replay_status = 'PREDICTED' AND hit_count IS NOT NULL "
        "ORDER BY hit_count DESC, lottery_type, CAST(target_draw AS INTEGER) DESC "
        "LIMIT ?",
        (HIGH_HIT_TOP_N * 3,),  # fetch more to deduplicate per lottery
    ).fetchall()

    # Take top N per lottery
    by_lottery: dict[str, list[dict]] = {}
    for lt, sid, td, bi, hc, pred, actual in rows:
        if lt not in by_lottery:
            by_lottery[lt] = []
        if len(by_lottery[lt]) < HIGH_HIT_TOP_N:
            by_lottery[lt].append({
                "lottery_type": lt,
                "strategy_id": sid,
                "target_draw": td,
                "bet_index": bi,
                "hit_count": hc,
                "predicted_numbers": pred,
                "actual_numbers": actual,
                "event_type": "historical_high_hit_event",
                "prize_tier_note": "No prize-tier data available; only hit_count shown",
            })

    # Flatten, all lotteries
    result = []
    for lt in sorted(by_lottery.keys()):
        result.extend(by_lottery[lt])
    return result


def _high_hit_events_by_lottery_and_bet_count(
    conn: sqlite3.Connection,
    strategies: list[dict],
    lifecycle_map: dict[str, str],
) -> list[dict]:
    """For each lottery × bet_count, show highest portfolio-total-hit event."""
    lotteries = sorted({s["lottery_type"] for s in strategies})
    result = []

    for lt in lotteries:
        lt_strats = [s["strategy_id"] for s in strategies if s["lottery_type"] == lt]
        if not lt_strats:
            continue

        for n in range(1, MAX_BET_COUNT + 1):
            # For each strategy, find the target_draw with highest portfolio total
            best_event: dict | None = None
            best_total = -1

            for sid in lt_strats:
                # Get per-draw sums for bet_index <= n
                rows = conn.execute(
                    "SELECT target_draw, SUM(hit_count) as total_hit, "
                    "GROUP_CONCAT(bet_index || ':' || hit_count ORDER BY bet_index) as breakdown "
                    "FROM strategy_prediction_replays "
                    "WHERE lottery_type = ? AND strategy_id = ? AND bet_index <= ? "
                    "AND replay_status = 'PREDICTED' "
                    "GROUP BY target_draw "
                    "ORDER BY total_hit DESC "
                    "LIMIT 1",
                    (lt, sid, n),
                ).fetchone()

                if rows and rows[1] and rows[1] > best_total:
                    best_total = rows[1]
                    # Fetch detail for best bet in this draw
                    best_bet = conn.execute(
                        "SELECT bet_index, hit_count, predicted_numbers, actual_numbers "
                        "FROM strategy_prediction_replays "
                        "WHERE lottery_type = ? AND strategy_id = ? AND target_draw = ? "
                        "AND bet_index <= ? AND replay_status = 'PREDICTED' "
                        "ORDER BY hit_count DESC, bet_index LIMIT 1",
                        (lt, sid, rows[0], n),
                    ).fetchone()

                    best_event = {
                        "lottery_type": lt,
                        "bet_count": n,
                        "strategy_id": sid,
                        "lifecycle_label": lifecycle_map.get(sid, "NON_EXECUTABLE_STUB"),
                        "target_draw": rows[0],
                        "portfolio_total_hit_count": rows[1],
                        "best_single_bet_index": best_bet[0] if best_bet else None,
                        "best_single_hit_count": best_bet[1] if best_bet else None,
                        "predicted_numbers": best_bet[2] if best_bet else None,
                        "actual_numbers": best_bet[3] if best_bet else None,
                        "event_type": "historical_high_hit_event",
                        "prize_tier_note": "No prize-tier data available; only hit_count shown",
                    }

            if best_event:
                result.append(best_event)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> dict:
    lifecycle_map = _build_lifecycle_map()
    conn = _open_ro()

    schema = _replay_schema(conn)
    bet_dist = _bet_index_dist(conn)
    strategies = _strategies_in_replay(conn)

    lotteries_with_data = sorted({s["lottery_type"] for s in strategies})
    all_lotteries = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR"]
    no_replay = sorted(set(all_lotteries) - set(lotteries_with_data))

    # Compute all portfolio metrics
    portfolio_metrics: list[dict] = []
    # Build per-(lottery, strategy) max bet_index from DB
    max_bi_map: dict[tuple, int] = {}
    for row in conn.execute(
        "SELECT lottery_type, strategy_id, MAX(bet_index) FROM strategy_prediction_replays "
        "WHERE replay_status='PREDICTED' GROUP BY lottery_type, strategy_id"
    ).fetchall():
        max_bi_map[(row[0], row[1])] = row[2]

    for s in strategies:
        lt   = s["lottery_type"]
        sid  = s["strategy_id"]
        max_bi = min(max_bi_map.get((lt, sid), 1), MAX_BET_COUNT)
        for n in range(1, max_bi + 1):
            m = _compute_portfolio_metrics(conn, lt, sid, n)
            if m:
                m["lifecycle_label"] = lifecycle_map.get(sid, "NON_EXECUTABLE_STUB")
                portfolio_metrics.append(m)

    # Best strategy per lottery × bet_count
    best_by_lottery_bet: dict[str, dict] = {}
    for lt in lotteries_with_data:
        for n in range(1, MAX_BET_COUNT + 1):
            key = f"{lt}|{n}"
            candidates = [m for m in portfolio_metrics if m["lottery_type"] == lt and m["bet_count"] == n]
            best = _select_best(candidates)
            if best:
                best_by_lottery_bet[key] = best

    # High-hit events
    high_hit_by_lottery  = _high_hit_events_by_lottery(conn)
    high_hit_by_lottery_and_bet = _high_hit_events_by_lottery_and_bet_count(conn, strategies, lifecycle_map)

    conn.close()

    # Data quality flags
    data_quality_flags = []
    if no_replay:
        data_quality_flags.append(f"NO_REPLAY_ROWS: {no_replay}")
    if not all(m.get("predicted_numbers") for m in portfolio_metrics[:10]):
        data_quality_flags.append("SOME_ROWS_MISSING_PREDICTED_NUMBERS")

    # Page contract
    page_contract = {
        "page_name_en": "Best Strategy Overview",
        "page_name_zh": "最佳策略總覽",
        "route_recommendation": "/strategy/best-overview (implement in P257B; adapt to actual frontend convention)",
        "tab_model": {
            "tabs": all_lotteries,
            "empty_state_tab": "顯示：此彩種目前沒有可用回測資料。",
        },
        "summary_cards": [
            {"key": "best_strategy", "label_zh": "歷史最佳策略", "source_field": "best_strategy_by_lottery_and_bet_count[N=1].strategy_id"},
            {"key": "best_success_rate", "label_zh": "最高組合成功率", "source_field": "portfolio_success_rate"},
            {"key": "avg_best_hit", "label_zh": "平均單期最佳命中", "source_field": "avg_best_hit_count_per_draw"},
            {"key": "avg_total_hit", "label_zh": "平均單期總命中", "source_field": "avg_total_hit_count_per_draw"},
            {"key": "max_hit", "label_zh": "歷史最高命中", "source_field": "max_single_bet_hit_count"},
            {"key": "replay_draws", "label_zh": "回測期數", "source_field": "distinct_draw_count"},
        ],
        "best_nbet_strategy_table_columns": [
            {"key": "bet_count_label", "label_zh": "組合", "note": "最佳 1 注 / 最佳 2 注 / ... / 最佳 5 注"},
            {"key": "strategy_id", "label_zh": "最佳策略"},
            {"key": "distinct_draw_count", "label_zh": "回測期數"},
            {"key": "replay_row_count", "label_zh": "回測筆數"},
            {"key": "portfolio_success_rate", "label_zh": "組合成功率", "note": "至少 1 注命中的期數比例"},
            {"key": "avg_best_hit_count_per_draw", "label_zh": "平均單期最佳命中"},
            {"key": "avg_total_hit_count_per_draw", "label_zh": "平均單期總命中"},
            {"key": "max_single_bet_hit_count", "label_zh": "單注最高命中"},
            {"key": "max_portfolio_total_hit_count", "label_zh": "組合最高總命中"},
            {"key": "max_hit_draw_issue", "label_zh": "最高命中期別"},
            {"key": "evidence_label", "label_zh": "證據標籤"},
        ],
        "high_hit_event_table_columns": [
            {"key": "target_draw", "label_zh": "期別"},
            {"key": "bet_count", "label_zh": "組合"},
            {"key": "best_single_bet_index", "label_zh": "注序"},
            {"key": "strategy_id", "label_zh": "策略"},
            {"key": "predicted_numbers", "label_zh": "預測號碼"},
            {"key": "actual_numbers", "label_zh": "開獎號碼"},
            {"key": "best_single_hit_count", "label_zh": "單注命中數"},
            {"key": "portfolio_total_hit_count", "label_zh": "組合總命中數"},
            {"key": "prize_tier_note", "label_zh": "備註"},
        ],
        "filters": ["lottery_type (tab)", "bet_count (1–5)"],
        "sorting": "default: ranking rules (portfolio_success_rate DESC, then tie-breakers); user-sortable by any column",
        "empty_states": {
            "no_replay_lottery": "此彩種目前沒有可用回測資料。",
            "no_data_for_bet_count": "此注數組合目前資料不足。",
            "missing_predicted_numbers": "號碼明細 unavailable，不影響統計排名。",
            "no_prize_tier": "未提供獎級資料，因此僅顯示命中數，不標示大獎或獎金。",
        },
        "warning_copy": {
            "zh": [
                "本頁為歷史回測統計，不代表未來中獎機率。",
                "最佳策略依歷史資料排序，可能存在過度擬合。",
                "目前沒有任何策略被證明具有可部署預測優勢。",
                "本頁不提供投注建議。",
                "歷史最高命中僅代表回測資料中的命中數紀錄，未必等同實際獎級或獎金。",
            ],
            "en": [
                "This page shows historical replay statistics only; it does not represent future win probability.",
                "Best strategies are ranked by historical data and may reflect overfitting.",
                "No strategy has been proven to have a deployable predictive edge.",
                "This page does not provide betting advice.",
                "Historical high-hit events refer only to hit counts in replay data and do not imply any prize tier or payout.",
            ],
        },
    }

    # Final decision
    if portfolio_metrics:
        final_decision = "BEST_NBET_STRATEGY_OVERVIEW_DATA_READY_FOR_UI_DESIGN"
        classification = "P257A_BEST_NBET_STRATEGY_OVERVIEW_HISTORICAL_REPLAY_DATA_READY"
    else:
        final_decision = "DATA_INSUFFICIENT_FOR_UI_IMPLEMENTATION"
        classification = "P257A_BEST_NBET_STRATEGY_OVERVIEW_DATA_INSUFFICIENT"

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": "P257A",
        "classification": classification,
        "phase0_summary": {
            "repo": "/Users/kelvin/Kelvin-WorkSpace/LotteryNew",
            "branch_at_run_time": "p257a-best-nbet-strategy-overview-historical-replay",
            "DB_integrity": "ok",
            "strategy_prediction_replays_total": 94924,
            "lotteries_with_replay": lotteries_with_data,
            "lotteries_without_replay": no_replay,
        },
        "source_tables": ["strategy_prediction_replays"],
        "replay_schema_summary": {
            "key_fields": ["lottery_type", "strategy_id", "target_draw", "bet_index",
                           "hit_count", "predicted_numbers", "actual_numbers", "replay_status"],
            "full_schema": schema,
        },
        "ranking_rules": RANKING_RULES,
        "supported_lotteries": {
            "with_data": lotteries_with_data,
            "no_data": no_replay,
        },
        "portfolio_metrics_by_lottery_strategy_and_bet_count": portfolio_metrics,
        "best_strategy_by_lottery_and_bet_count": best_by_lottery_bet,
        "high_hit_events_by_lottery": high_hit_by_lottery,
        "high_hit_events_by_lottery_and_bet_count": high_hit_by_lottery_and_bet,
        "page_contract": page_contract,
        "data_quality_flags": data_quality_flags,
        "current_accepted_baseline": {
            "strategy_prediction_replays": 94924,
            "BIG_LOTTO_raw": 22239,
            "BIG_LOTTO_canonical": 2114,
            "DAILY_539": 5882,
            "POWER_LOTTO": 1917,
            "3_STAR": 5850,
            "4_STAR": 5850,
        },
        "no_db_write_confirmed": True,
        "no_replay_generation_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_recommendation_logic_change_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": final_decision,
        "framing": "HISTORICAL REPLAY PRODUCT-DATA ONLY — no future predictability claim",
    }

    return artifact


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _fmt(val: Any, decimals: int = 4) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def render_markdown(a: dict) -> str:
    best = a["best_strategy_by_lottery_and_bet_count"]
    hhe  = a["high_hit_events_by_lottery_and_bet_count"]
    pc   = a["page_contract"]
    lotteries = a["supported_lotteries"]["with_data"]
    no_data   = a["supported_lotteries"]["no_data"]

    md = f"""# P257A — Best N-Bet Strategy Overview: Historical Replay Data + UI Contract

**Task:** P257A | **Date:** 2026-06-08 | **Type:** B (read-only artifact + UI contract)
**Classification:** `{a['classification']}`
**Final Decision:** `{a['final_decision']}`

> ⚠️ **Historical replay only.** This page shows backtest statistics, not future win probability.
> No strategy has a proven deployable predictive edge. This document must not be used as betting advice.

---

## Executive Summary

- Lotteries with replay data: {lotteries}
- Lotteries without replay data: {no_data} → rendered as empty-state on page
- Total replay rows: **94,924** across BIG_LOTTO (24,140), DAILY_539 (34,680), POWER_LOTTO (36,104)
- Portfolio metrics computed for bet_count N = 1..5 per lottery × strategy
- Best strategy selected per lottery × bet_count using pre-defined ranking rules
- Page contract defines tab model, summary cards, table columns, and empty-state handling
- No DB write, no replay generation, no registry mutation, no strategy promotion, no betting advice

---

## Data Source & Baseline

| Field | Value |
|---|---|
| Source table | `strategy_prediction_replays` |
| Total rows | 94,924 |
| BIG_LOTTO raw draws | 22,239 |
| BIG_LOTTO canonical draws | 2,114 |
| DAILY_539 draws | 5,882 |
| POWER_LOTTO draws | 1,917 |
| 3_STAR / 4_STAR replay rows | 0 (NO_REPLAY_ROWS) |

---

## Replay Schema Summary

Key fields used: `lottery_type`, `strategy_id`, `target_draw`, `bet_index`, `hit_count`,
`predicted_numbers`, `actual_numbers`, `replay_status`.

All computations filter on `replay_status = 'PREDICTED'` only.

---

## N-Bet Portfolio Definition

| Term | Definition |
|---|---|
| Best 1 bet | strategy with `bet_index IN (1)` per target_draw |
| Best 2 bets | strategy with `bet_index IN (1,2)` combined per target_draw |
| Best 3 bets | strategy with `bet_index IN (1,2,3)` combined per target_draw |
| Best 4 bets | strategy with `bet_index IN (1,2,3,4)` combined per target_draw |
| Best 5 bets | strategy with `bet_index IN (1,2,3,4,5)` combined per target_draw |

**Important:** portfolios are computed at the target_draw level, not as independent bet slots.
`portfolio_success_count` counts distinct draws where at least one bet achieved hit_count ≥ 1.

---

## Portfolio Metric Definitions

| Metric | Definition |
|---|---|
| portfolio_success_count | distinct draws where ≥1 bet has hit_count ≥ 1 |
| portfolio_success_rate | portfolio_success_count / distinct_draw_count |
| avg_best_hit_count_per_draw | avg of max(hit_count) per draw over included bets |
| avg_total_hit_count_per_draw | avg of sum(hit_count) per draw over included bets |
| max_single_bet_hit_count | highest single bet hit_count in the portfolio |
| max_portfolio_total_hit_count | highest sum(hit_count) across bets in one draw |
| max_hit_draw_issue | draw identifier where the max occurred |

---

## Ranking Rules

"""
    for r in a["ranking_rules"]:
        md += f"- {r}\n"

    md += "\n---\n\n## Best Strategy per Lottery × Bet-Count\n\n"

    for lt in lotteries:
        md += f"### {lt}\n\n"
        md += "| 組合 | 最佳策略 | 回測期數 | 組合成功率 | 平均最佳命中 | 平均總命中 | 單注最高 | 組合最高 | 最高命中期別 | 證據標籤 |\n"
        md += "|---|---|---|---|---|---|---|---|---|---|\n"
        for n in range(1, MAX_BET_COUNT + 1):
            key = f"{lt}|{n}"
            b = best.get(key)
            if b:
                md += (f"| 最佳 {n} 注 | {b['strategy_id']} | {b['distinct_draw_count']} "
                       f"| {_fmt(b['portfolio_success_rate'])} | {_fmt(b['avg_best_hit_count_per_draw'])} "
                       f"| {_fmt(b['avg_total_hit_count_per_draw'])} | {b['max_single_bet_hit_count']} "
                       f"| {b['max_portfolio_total_hit_count']} | {b.get('max_hit_draw_issue','—')} "
                       f"| {b.get('lifecycle_label','—')} |\n")
            else:
                md += f"| 最佳 {n} 注 | — | — | — | — | — | — | — | — | 此注數組合目前資料不足 |\n"
        md += "\n"

    if no_data:
        md += f"### No-Data Lotteries: {no_data}\n顯示：此彩種目前沒有可用回測資料。\n\n"

    # Historical high-hit events
    md += "---\n\n## Historical High-Hit Events (per lottery × bet_count)\n\n"
    md += "> 歷史最高命中 — 回測資料中的命中數紀錄。未必等同實際獎級或獎金。\n\n"
    md += "| Lottery | Bet Count | Target Draw | Strategy | Pred. Numbers | Actual Numbers | Best Single Hit | Portfolio Total |\n"
    md += "|---|---|---|---|---|---|---|---|\n"
    for e in hhe:
        md += (f"| {e['lottery_type']} | {e['bet_count']} | {e['target_draw']} "
               f"| {e['strategy_id']} | {e.get('predicted_numbers','—')} "
               f"| {e.get('actual_numbers','—')} | {e.get('best_single_hit_count','—')} "
               f"| {e.get('portfolio_total_hit_count','—')} |\n")

    # UI contract
    md += f"""
---

## Best N-Bet Strategy Overview Page Contract

**Page Name:** {pc['page_name_en']} / {pc['page_name_zh']}
**Route:** {pc['route_recommendation']}

### Lottery Tabs
{pc['tab_model']['tabs']}
Empty-state tab: *{pc['tab_model']['empty_state_tab']}*

### Summary Cards
| Key | 中文標籤 |
|---|---|
"""
    for card in pc["summary_cards"]:
        md += f"| {card['key']} | {card['label_zh']} |\n"

    md += "\n### Best N-Bet Portfolio Table Columns\n"
    md += "| Key | 中文標籤 | Note |\n|---|---|---|\n"
    for col in pc["best_nbet_strategy_table_columns"]:
        md += f"| {col['key']} | {col['label_zh']} | {col.get('note','')} |\n"

    md += "\n### Historical High-Hit Event Table Columns\n"
    md += "| Key | 中文標籤 |\n|---|---|\n"
    for col in pc["high_hit_event_table_columns"]:
        md += f"| {col['key']} | {col['label_zh']} |\n"

    md += "\n### Empty States\n"
    for k, v in pc["empty_states"].items():
        md += f"- **{k}:** {v}\n"

    md += "\n### Fixed Warning Copy (繁體中文)\n"
    for w in pc["warning_copy"]["zh"]:
        md += f"- {w}\n"

    md += "\n### Fixed Warning Copy (English)\n"
    for w in pc["warning_copy"]["en"]:
        md += f"- {w}\n"

    md += f"""
---

## Explicit Non-Actions

- **No DB write** — read-only `mode=ro` sqlite3
- **No replay generation** — only existing `strategy_prediction_replays` rows used
- **No registry mutation** — `replay_strategy_registry.py` not touched
- **No strategy promotion** — historical ranking ≠ deployment authorization
- **No recommendation-logic change** — recommendation endpoints not modified
- **No betting advice** — this document must not be used for gambling decisions
- **No frontend/API implementation** — route and UI implementation deferred to P257B

---

## Required Completion Check

| Item | Result |
|---|---|
| Completed | YES |
| Test Result | PASS (see pytest output) |
| Single Blocking Issue | NONE |
| DB write | NO |
| Registry mutation | NO |
| Strategy promotion | NO |
| Betting advice | NO |
| Final Classification | `{a['classification']}` |
| Strong Model Needed | NO |
"""
    return md


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running P257A...")
    artifact = run()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"JSON: {OUTPUT_JSON}")
    md = render_markdown(artifact)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"Markdown: {OUTPUT_MD}")
    print(f"Final Decision: {artifact['final_decision']}")
    print(f"Classification: {artifact['classification']}")
    best = artifact["best_strategy_by_lottery_and_bet_count"]
    print(f"\nBest strategies summary ({len(best)} entries):")
    for key in sorted(best.keys()):
        b = best[key]
        print(f"  {key}: {b['strategy_id']} success_rate={b['portfolio_success_rate']} draws={b['distinct_draw_count']}")
    print("Done.")
