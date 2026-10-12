"""P333 — Strategy Pick/Combination Prize-Aware Scoreboard.

Read-only analysis over existing replay rows.  It answers three product
questions without changing prediction generation, training, registry state, or
the replay DB:

* For each strategy, if we take the first K emitted numbers, how often did at
  least one number hit?
* Under the real prize-aware endpoints, how do BIG_LOTTO special numbers and
  POWER_LOTTO second-zone numbers change the historical success signal?
* Which equal-budget strategy combinations worked best in the historical
  replay data for the primary 50 / 300 / 750 windows?

This is retrospective evidence only.  It is not a betting recommendation and it
does not claim future predictability.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
OUTPUT_JSON = OUTPUT_DIR / "p333_strategy_pick_combination_scoreboard_20260702.json"
OUTPUT_MD = OUTPUT_DIR / "p333_strategy_pick_combination_scoreboard_20260702.md"

LOTTERIES = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")
WINDOWS = (50, 300, 750)
MIN_SUPPORT_DRAWS = 30
MAX_COMBO_STRATEGIES = 3
MAX_QUOTA_PER_STRATEGY_IN_COMBO = 2
TOP_COMBOS_PER_BUCKET = 10

GAME_RULES: dict[str, dict[str, Any]] = {
    "BIG_LOTTO": {
        "main_pool": 49,
        "main_drawn": 6,
        "pick_count": 6,
        "endpoint": "main_hits >= 3 OR (main_hits >= 2 AND actual_special IN selected_numbers)",
    },
    "DAILY_539": {
        "main_pool": 39,
        "main_drawn": 5,
        "pick_count": 5,
        "endpoint": "main_hits >= 2",
    },
    "POWER_LOTTO": {
        "main_pool": 38,
        "main_drawn": 6,
        "pick_count": 6,
        "second_zone_size": 8,
        "endpoint": "main_hits >= 3 OR (main_hits >= 1 AND predicted_second_zone == actual_second_zone)",
    },
}

DISCLAIMER_ZH = (
    "歷史回放統計只描述既有 replay 的過去表現；不代表未來中獎率，"
    "不提供投注建議，也不代表策略可直接上線。"
)


def _open_ro(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _safe_comb(n: int, k: int) -> int:
    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)


def _parse_numbers(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, list):
        values = raw
    else:
        try:
            values = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
    result: list[int] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            result.append(value)
    return result


def _draw_sort_key(draw: str) -> int:
    try:
        return int(draw)
    except (TypeError, ValueError):
        return -1


def _unique_preserve(values: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _load_replay_draws(conn: sqlite3.Connection) -> dict[str, dict[str, dict[str, dict]]]:
    """Return nested replay data: lottery -> strategy -> target_draw -> record."""
    rows = conn.execute(
        """
        SELECT lottery_type, strategy_id, target_draw, bet_index,
               predicted_numbers, predicted_special,
               actual_numbers, actual_special, history_cutoff_draw
        FROM strategy_prediction_replays
        WHERE lottery_type IN ('BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO')
          AND replay_status = 'PREDICTED'
          AND dry_run = 0
          AND predicted_numbers IS NOT NULL
          AND actual_numbers IS NOT NULL
        ORDER BY lottery_type, strategy_id, CAST(target_draw AS INTEGER) DESC, bet_index
        """
    ).fetchall()

    data: dict[str, dict[str, dict[str, dict]]] = {
        lt: defaultdict(dict) for lt in LOTTERIES
    }
    seen_bet_rows: set[tuple[str, str, str, int]] = set()

    for row in rows:
        lt = row["lottery_type"]
        sid = row["strategy_id"]
        draw = str(row["target_draw"])
        bet_index = int(row["bet_index"] or 1)
        dedupe = (lt, sid, draw, bet_index)
        if dedupe in seen_bet_rows:
            continue
        seen_bet_rows.add(dedupe)

        actual_numbers = _parse_numbers(row["actual_numbers"])
        predicted_numbers = _parse_numbers(row["predicted_numbers"])
        if not actual_numbers or not predicted_numbers:
            continue

        draw_record = data[lt][sid].setdefault(
            draw,
            {
                "target_draw": draw,
                "actual_numbers": actual_numbers,
                "actual_special": row["actual_special"],
                "history_cutoff_draw": row["history_cutoff_draw"],
                "rows": [],
            },
        )
        draw_record["rows"].append(
            {
                "bet_index": bet_index,
                "predicted_numbers": predicted_numbers,
                "predicted_special": row["predicted_special"],
            }
        )

    # Convert defaultdicts to plain dicts and enforce stable row order.
    plain: dict[str, dict[str, dict[str, dict]]] = {}
    for lt, by_strategy in data.items():
        plain[lt] = {}
        for sid, by_draw in by_strategy.items():
            plain[lt][sid] = {}
            for draw, record in by_draw.items():
                record["rows"].sort(key=lambda r: int(r["bet_index"]))
                plain[lt][sid][draw] = record
    return plain


def select_strategy_numbers(draw_record: dict, quota: int) -> tuple[list[int], list[int]]:
    """Take the first `quota` distinct main numbers emitted by a strategy.

    Row order is bet_index ascending, then the order of numbers inside the
    stored prediction list.  POWER_LOTTO second-zone candidates are collected
    from visited bet rows only, so second-zone budget stays tied to the selected
    strategy rows.
    """
    selected: list[int] = []
    seconds: list[int] = []
    for row in draw_record.get("rows", []):
        special = row.get("predicted_special")
        if special is not None and not isinstance(special, bool):
            try:
                seconds.append(int(special))
            except (TypeError, ValueError):
                pass
        for number in row.get("predicted_numbers", []):
            if number not in selected:
                selected.append(number)
            if len(selected) >= quota:
                return selected, _unique_preserve(seconds)
    return selected, _unique_preserve(seconds)


def _baseline_any_main(lottery_type: str, selected_count: int) -> float:
    rule = GAME_RULES[lottery_type]
    pool = int(rule["main_pool"])
    drawn = int(rule["main_drawn"])
    denom = _safe_comb(pool, selected_count)
    if denom <= 0 or selected_count <= 0:
        return 0.0
    miss = _safe_comb(pool - drawn, selected_count)
    return 1.0 - (miss / denom)


def _hypergeom_at_least(lottery_type: str, selected_count: int, threshold: int) -> float:
    rule = GAME_RULES[lottery_type]
    pool = int(rule["main_pool"])
    drawn = int(rule["main_drawn"])
    denom = _safe_comb(pool, selected_count)
    if denom <= 0:
        return 0.0
    total = 0
    for hits in range(threshold, min(drawn, selected_count) + 1):
        total += _safe_comb(drawn, hits) * _safe_comb(pool - drawn, selected_count - hits)
    return total / denom


def _baseline_big_prize_signal(selected_count: int) -> float:
    denom = _safe_comb(49, selected_count)
    if denom <= 0:
        return 0.0
    main3_plus = 0
    for hits in range(3, min(6, selected_count) + 1):
        main3_plus += _safe_comb(6, hits) * _safe_comb(43, selected_count - hits)
    m2_special = _safe_comb(6, 2) * _safe_comb(42, selected_count - 3)
    return (main3_plus + m2_special) / denom


def _baseline_power_prize_signal(selected_count: int, second_zone_count: int) -> float:
    p_m3 = _hypergeom_at_least("POWER_LOTTO", selected_count, 3)
    p_m1 = _baseline_any_main("POWER_LOTTO", selected_count)
    p_second = max(0.0, min(1.0, second_zone_count / 8.0))
    return p_m3 + (p_m1 - p_m3) * p_second


def _baseline_prize_signal(
    lottery_type: str, selected_count: int, second_zone_count: int
) -> float:
    if lottery_type == "DAILY_539":
        return _hypergeom_at_least(lottery_type, selected_count, 2)
    if lottery_type == "BIG_LOTTO":
        return _baseline_big_prize_signal(selected_count)
    return _baseline_power_prize_signal(selected_count, second_zone_count)


def score_selection(
    lottery_type: str,
    selected_numbers: list[int],
    second_zone_candidates: list[int],
    actual_numbers: list[int],
    actual_special: Any,
) -> dict[str, Any]:
    selected = set(selected_numbers)
    actual = set(actual_numbers)
    main_hits = len(selected & actual)
    second_candidates = set(
        n for n in second_zone_candidates if isinstance(n, int) and 1 <= n <= 8
    )

    special_hit = False
    second_zone_hit = False
    if lottery_type == "BIG_LOTTO" and actual_special is not None:
        try:
            special_hit = int(actual_special) in selected
        except (TypeError, ValueError):
            special_hit = False
    if lottery_type == "POWER_LOTTO" and actual_special is not None:
        try:
            second_zone_hit = int(actual_special) in second_candidates
        except (TypeError, ValueError):
            second_zone_hit = False

    if lottery_type == "DAILY_539":
        prize_signal = main_hits >= 2
    elif lottery_type == "BIG_LOTTO":
        prize_signal = main_hits >= 3 or (main_hits >= 2 and special_hit)
    else:
        prize_signal = main_hits >= 3 or (main_hits >= 1 and second_zone_hit)

    selected_count = len(selected)
    second_count = len(second_candidates)
    return {
        "selected_count": selected_count,
        "second_zone_candidate_count": second_count,
        "main_hits": main_hits,
        "any_main_hit": main_hits >= 1,
        "m2_plus": main_hits >= 2,
        "special_hit": special_hit if lottery_type == "BIG_LOTTO" else None,
        "second_zone_hit": second_zone_hit if lottery_type == "POWER_LOTTO" else None,
        "prize_signal": prize_signal,
        "baseline_any_main": _baseline_any_main(lottery_type, selected_count),
        "baseline_prize_signal": _baseline_prize_signal(
            lottery_type, selected_count, second_count
        ),
    }


def _empty_aggregate(
    lottery_type: str,
    window: int,
    *,
    strategy_id: str | None = None,
    pick_k: int | None = None,
    combo: list[dict] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "lottery_type": lottery_type,
        "window": window,
        "support_draws": 0,
        "any_main_hit_count": 0,
        "any_main_hit_rate": None,
        "m2_plus_count": 0,
        "m2_plus_rate": None,
        "prize_signal_count": 0,
        "prize_signal_rate": None,
        "baseline_any_main_rate": None,
        "baseline_prize_signal_rate": None,
        "any_main_hit_edge_pp": None,
        "prize_signal_edge_pp": None,
        "avg_main_hits": None,
        "avg_selected_count": None,
        "avg_second_zone_candidates": None,
        "special_hit_count": None if lottery_type != "BIG_LOTTO" else 0,
        "special_hit_rate": None,
        "second_zone_hit_count": None if lottery_type != "POWER_LOTTO" else 0,
        "second_zone_hit_rate": None,
        "latest_target_draw": None,
        "earliest_target_draw": None,
    }
    if strategy_id is not None:
        rec["strategy_id"] = strategy_id
    if pick_k is not None:
        rec["pick_k"] = pick_k
    if combo is not None:
        rec["combo"] = combo
        rec["combo_id"] = " + ".join(
            f"{part['strategy_id']}:{part['quota']}" for part in combo
        )
        rec["requested_budget"] = sum(int(part["quota"]) for part in combo)
    return rec


def _finalize_aggregate(rec: dict[str, Any], scores: list[dict], draws: list[str]) -> dict[str, Any]:
    support = len(scores)
    rec["support_draws"] = support
    rec["latest_target_draw"] = draws[0] if draws else None
    rec["earliest_target_draw"] = draws[-1] if draws else None
    if support == 0:
        return rec

    any_count = sum(1 for s in scores if s["any_main_hit"])
    m2_count = sum(1 for s in scores if s["m2_plus"])
    prize_count = sum(1 for s in scores if s["prize_signal"])
    base_any = sum(float(s["baseline_any_main"]) for s in scores) / support
    base_prize = sum(float(s["baseline_prize_signal"]) for s in scores) / support
    any_rate = any_count / support
    prize_rate = prize_count / support

    rec.update(
        {
            "any_main_hit_count": any_count,
            "any_main_hit_rate": any_rate,
            "m2_plus_count": m2_count,
            "m2_plus_rate": m2_count / support,
            "prize_signal_count": prize_count,
            "prize_signal_rate": prize_rate,
            "baseline_any_main_rate": base_any,
            "baseline_prize_signal_rate": base_prize,
            "any_main_hit_edge_pp": (any_rate - base_any) * 100,
            "prize_signal_edge_pp": (prize_rate - base_prize) * 100,
            "avg_main_hits": sum(int(s["main_hits"]) for s in scores) / support,
            "avg_selected_count": sum(int(s["selected_count"]) for s in scores) / support,
            "avg_second_zone_candidates": sum(
                int(s["second_zone_candidate_count"]) for s in scores
            )
            / support,
        }
    )

    if rec["lottery_type"] == "BIG_LOTTO":
        sp_count = sum(1 for s in scores if s["special_hit"])
        rec["special_hit_count"] = sp_count
        rec["special_hit_rate"] = sp_count / support
    if rec["lottery_type"] == "POWER_LOTTO":
        sz_count = sum(1 for s in scores if s["second_zone_hit"])
        rec["second_zone_hit_count"] = sz_count
        rec["second_zone_hit_rate"] = sz_count / support
    return rec


def evaluate_strategy_pick(
    by_draw: dict[str, dict], lottery_type: str, strategy_id: str, pick_k: int, window: int
) -> dict[str, Any]:
    draws = sorted(by_draw, key=_draw_sort_key, reverse=True)[:window]
    scores: list[dict] = []
    score_draws: list[str] = []
    for draw in draws:
        record = by_draw[draw]
        selected, seconds = select_strategy_numbers(record, pick_k)
        if not selected:
            continue
        scores.append(
            score_selection(
                lottery_type,
                selected,
                seconds,
                record["actual_numbers"],
                record["actual_special"],
            )
        )
        score_draws.append(draw)
    rec = _empty_aggregate(
        lottery_type, window, strategy_id=strategy_id, pick_k=pick_k
    )
    return _finalize_aggregate(rec, scores, score_draws)


def evaluate_combo(
    by_strategy: dict[str, dict[str, dict]],
    lottery_type: str,
    combo: list[dict],
    window: int,
) -> dict[str, Any]:
    draw_sets = [set(by_strategy[part["strategy_id"]]) for part in combo]
    common_draws = set.intersection(*draw_sets) if draw_sets else set()
    draws = sorted(common_draws, key=_draw_sort_key, reverse=True)[:window]

    scores: list[dict] = []
    score_draws: list[str] = []
    for draw in draws:
        selected: list[int] = []
        seconds: list[int] = []
        base_record = None
        for part in combo:
            record = by_strategy[part["strategy_id"]][draw]
            base_record = base_record or record
            nums, sz = select_strategy_numbers(record, int(part["quota"]))
            selected.extend(nums)
            seconds.extend(sz)
        if base_record is None:
            continue
        selected = _unique_preserve(selected)
        if not selected:
            continue
        scores.append(
            score_selection(
                lottery_type,
                selected,
                _unique_preserve(seconds),
                base_record["actual_numbers"],
                base_record["actual_special"],
            )
        )
        score_draws.append(draw)

    rec = _empty_aggregate(lottery_type, window, combo=combo)
    return _finalize_aggregate(rec, scores, score_draws)


def _family_for_strategy(strategy_id: str) -> str:
    sid = strategy_id.lower()
    rules = [
        ("fourier", "fourier"),
        ("cold", "cold"),
        ("deviation", "deviation"),
        ("markov", "markov"),
        ("orthogonal", "orthogonal"),
        ("entropy", "entropy"),
        ("zone", "zone"),
        ("zonal", "zone"),
        ("acb", "acb"),
        ("echo", "echo"),
        ("ts3", "ts3"),
        ("precision", "precision"),
        ("freq", "frequency"),
    ]
    for token, family in rules:
        if token in sid:
            return family
    return "other"


def build_strategy_pick_matrix(data: dict[str, dict[str, dict]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for lottery_type in LOTTERIES:
        pick_count = int(GAME_RULES[lottery_type]["pick_count"])
        for strategy_id in sorted(data.get(lottery_type, {})):
            by_draw = data[lottery_type][strategy_id]
            for window in WINDOWS:
                for pick_k in range(1, pick_count + 1):
                    rec = evaluate_strategy_pick(
                        by_draw, lottery_type, strategy_id, pick_k, window
                    )
                    rec["feature_family"] = _family_for_strategy(strategy_id)
                    matrix.append(rec)
    return matrix


def build_strategy_window_decisions(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[int, dict]] = defaultdict(dict)
    for rec in matrix:
        full_pick = int(GAME_RULES[rec["lottery_type"]]["pick_count"])
        if rec.get("pick_k") == full_pick:
            grouped[(rec["lottery_type"], rec["strategy_id"])][rec["window"]] = rec

    decisions: list[dict[str, Any]] = []
    for (lottery_type, strategy_id), by_window in sorted(grouped.items()):
        short = by_window.get(50)
        mid = by_window.get(300)
        long = by_window.get(750)
        support_ok = all(
            r is not None and int(r["support_draws"]) >= MIN_SUPPORT_DRAWS
            for r in (short, mid, long)
        )
        if not support_ok:
            label = "INSUFFICIENT_WINDOW_SUPPORT"
        elif (
            float(mid["prize_signal_edge_pp"]) > 0
            and float(long["prize_signal_edge_pp"]) > 0
            and float(short["prize_signal_edge_pp"]) > -5
        ):
            label = "HISTORICAL_WINDOW_PASS"
        else:
            label = "HISTORICAL_WINDOW_FAIL"
        decisions.append(
            {
                "lottery_type": lottery_type,
                "strategy_id": strategy_id,
                "feature_family": _family_for_strategy(strategy_id),
                "decision_label": label,
                "decision_windows": [50, 300, 750],
                "long_history_reference_used_for_decision": False,
                "support_draws": {
                    str(w): by_window.get(w, {}).get("support_draws") for w in WINDOWS
                },
                "prize_signal_rate": {
                    str(w): by_window.get(w, {}).get("prize_signal_rate") for w in WINDOWS
                },
                "prize_signal_edge_pp": {
                    str(w): by_window.get(w, {}).get("prize_signal_edge_pp") for w in WINDOWS
                },
            }
        )
    return decisions


def _combo_candidates(strategy_ids: list[str], pick_count: int) -> list[list[dict[str, Any]]]:
    candidates: list[list[dict[str, Any]]] = []
    for sid in strategy_ids:
        for quota in range(1, min(MAX_QUOTA_PER_STRATEGY_IN_COMBO, pick_count) + 1):
            candidates.append([{"strategy_id": sid, "quota": quota}])

    for size in range(2, MAX_COMBO_STRATEGIES + 1):
        for sid_tuple in itertools.combinations(strategy_ids, size):
            for quotas in itertools.product(
                range(1, MAX_QUOTA_PER_STRATEGY_IN_COMBO + 1), repeat=size
            ):
                if sum(quotas) > pick_count:
                    continue
                candidates.append(
                    [
                        {"strategy_id": sid, "quota": quota}
                        for sid, quota in zip(sid_tuple, quotas)
                    ]
                )
    return candidates


def build_combination_leaderboard(
    data: dict[str, dict[str, dict]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    leaderboard: list[dict[str, Any]] = []
    best_by_bucket: dict[str, dict[str, Any]] = {}

    for lottery_type in LOTTERIES:
        by_strategy = data.get(lottery_type, {})
        strategy_ids = sorted(by_strategy)
        pick_count = int(GAME_RULES[lottery_type]["pick_count"])
        candidates = _combo_candidates(strategy_ids, pick_count)

        for window in WINDOWS:
            buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for combo in candidates:
                rec = evaluate_combo(by_strategy, lottery_type, combo, window)
                if int(rec["support_draws"]) < MIN_SUPPORT_DRAWS:
                    continue
                buckets[int(rec["requested_budget"])].append(rec)

            for budget, records in buckets.items():
                records.sort(
                    key=lambda r: (
                        r["any_main_hit_rate"] or 0,
                        r["prize_signal_rate"] or 0,
                        r["any_main_hit_edge_pp"] or -999,
                        r["prize_signal_edge_pp"] or -999,
                        r["support_draws"],
                        r["combo_id"],
                    ),
                    reverse=True,
                )
                bucket_key = f"{lottery_type}|{window}|{budget}"
                if records:
                    best_by_bucket[bucket_key] = records[0]
                for rank, rec in enumerate(records[:TOP_COMBOS_PER_BUCKET], start=1):
                    out = dict(rec)
                    out["rank_in_bucket"] = rank
                    out["bucket_key"] = bucket_key
                    leaderboard.append(out)

    return leaderboard, best_by_bucket


def build_top_strategy_pick_index(matrix: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    grouped: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for rec in matrix:
        if int(rec["support_draws"]) >= MIN_SUPPORT_DRAWS:
            grouped[(rec["lottery_type"], rec["window"], rec["pick_k"])].append(rec)
    for key, records in grouped.items():
        records.sort(
            key=lambda r: (
                r["any_main_hit_rate"] or 0,
                r["prize_signal_rate"] or 0,
                r["any_main_hit_edge_pp"] or -999,
                r["strategy_id"],
            ),
            reverse=True,
        )
        best[f"{key[0]}|{key[1]}|{key[2]}"] = records[0]
    return best


def build_feature_family_summary(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rec in matrix:
        if rec["window"] == 750 and rec["pick_k"] == min(2, int(GAME_RULES[rec["lottery_type"]]["pick_count"])):
            buckets[(rec["lottery_type"], rec["feature_family"])].append(rec)

    summary: list[dict[str, Any]] = []
    for (lottery_type, family), records in sorted(buckets.items()):
        if not records:
            continue
        summary.append(
            {
                "lottery_type": lottery_type,
                "feature_family": family,
                "strategy_count": len({r["strategy_id"] for r in records}),
                "avg_any_main_hit_rate": sum(r["any_main_hit_rate"] or 0 for r in records)
                / len(records),
                "avg_prize_signal_rate": sum(r["prize_signal_rate"] or 0 for r in records)
                / len(records),
                "avg_any_main_hit_edge_pp": sum(r["any_main_hit_edge_pp"] or 0 for r in records)
                / len(records),
                "avg_prize_signal_edge_pp": sum(r["prize_signal_edge_pp"] or 0 for r in records)
                / len(records),
                "decision_basis": "window=750, pick_k=2; cross-lottery reference only",
            }
        )
    summary.sort(
        key=lambda r: (r["avg_any_main_hit_rate"], r["avg_prize_signal_rate"]),
        reverse=True,
    )
    return summary


def build_requested_example(data: dict[str, dict[str, dict]]) -> dict[str, Any]:
    combo = [
        {"strategy_id": "bet2_fourier_expansion_biglotto", "quota": 2},
        {"strategy_id": "cold_complement_biglotto", "quota": 2},
        {"strategy_id": "biglotto_deviation_2bet", "quota": 2},
    ]
    by_strategy = data.get("BIG_LOTTO", {})
    available = [part["strategy_id"] in by_strategy for part in combo]
    if not all(available):
        return {
            "lottery_type": "BIG_LOTTO",
            "combo": combo,
            "status": "NOT_EVALUATED_MISSING_STRATEGY",
        }
    return {
        "lottery_type": "BIG_LOTTO",
        "combo": combo,
        "status": "EVALUATED",
        "windows": {
            str(window): evaluate_combo(by_strategy, "BIG_LOTTO", combo, window)
            for window in WINDOWS
        },
    }


def _db_baseline(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    by_lottery = {
        row["lottery_type"]: row["n"]
        for row in conn.execute(
            """
            SELECT lottery_type, COUNT(*) AS n
            FROM strategy_prediction_replays
            GROUP BY lottery_type
            """
        )
    }
    strategy_counts = {
        row["lottery_type"]: row["n"]
        for row in conn.execute(
            """
            SELECT lottery_type, COUNT(DISTINCT strategy_id) AS n
            FROM strategy_prediction_replays
            WHERE lottery_type IN ('BIG_LOTTO','DAILY_539','POWER_LOTTO')
              AND replay_status = 'PREDICTED'
              AND dry_run = 0
            GROUP BY lottery_type
            """
        )
    }
    return {
        "strategy_prediction_replays_total": total,
        "rows_by_lottery": by_lottery,
        "strategy_counts_by_lottery": strategy_counts,
        "db_open_mode": "sqlite3 URI mode=ro + PRAGMA query_only=ON",
    }


def run_analysis(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    conn = _open_ro(db_path)
    try:
        baseline = _db_baseline(conn)
        data = _load_replay_draws(conn)
    finally:
        conn.close()

    matrix = build_strategy_pick_matrix(data)
    decisions = build_strategy_window_decisions(matrix)
    combo_leaderboard, best_combo = build_combination_leaderboard(data)
    top_strategy_pick = build_top_strategy_pick_index(matrix)
    family_summary = build_feature_family_summary(matrix)
    requested_example = build_requested_example(data)

    pass_counts = Counter(d["decision_label"] for d in decisions)
    artifact = {
        "schema_version": "1.0",
        "task_id": "P333",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P333_STRATEGY_PICK_COMBINATION_SCOREBOARD_READY",
        "source": {
            "db_path": str(db_path),
            "tables": ["strategy_prediction_replays"],
            "filters": {
                "lottery_type": list(LOTTERIES),
                "replay_status": "PREDICTED",
                "dry_run": 0,
            },
            "baseline": baseline,
        },
        "window_policy": {
            "primary_windows": list(WINDOWS),
            "long_history_reference_role": "reference_only_not_decision_gate",
            "minimum_support_draws": MIN_SUPPORT_DRAWS,
        },
        "score_definitions": {
            "strategy_pick_k": "take first K distinct emitted main numbers by bet_index then prediction order",
            "combination_budget": "equal requested main-number budget; each strategy contributes quota 1 or 2",
            "any_main_hit": "selected main-number set intersects actual main numbers",
            "prize_signal_by_lottery": {
                lt: GAME_RULES[lt]["endpoint"] for lt in LOTTERIES
            },
            "baseline": "analytic random baseline for same selected main-number count and second-zone candidate count",
        },
        "summary": {
            "strategy_pick_records": len(matrix),
            "combination_leaderboard_records": len(combo_leaderboard),
            "strategy_window_decision_counts": dict(pass_counts),
            "best_750_budget6_by_lottery": {
                lt: best_combo.get(f"{lt}|750|{GAME_RULES[lt]['pick_count']}")
                for lt in LOTTERIES
            },
        },
        "strategy_pick_matrix": matrix,
        "top_strategy_pick_by_lottery_window_pick": top_strategy_pick,
        "strategy_window_decisions": decisions,
        "combination_leaderboard": combo_leaderboard,
        "best_combination_by_lottery_window_budget": best_combo,
        "feature_family_summary": family_summary,
        "requested_example_fourier2_cold2_deviation2": requested_example,
        "safety_flags": {
            "db_read_only": True,
            "db_write": False,
            "replay_generation": False,
            "model_training": False,
            "registry_mutation": False,
            "strategy_promotion": False,
            "betting_advice": False,
        },
        "disclaimer_zh": DISCLAIMER_ZH,
    }
    return artifact


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def _pp(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.2f}pp"


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P333 — Strategy Pick / Combination Scoreboard")
    add("")
    add(f"> {DISCLAIMER_ZH}")
    add("")
    add("## Summary")
    add("")
    summary = result["summary"]
    add(f"- strategy_pick_records: **{summary['strategy_pick_records']}**")
    add(f"- combination_leaderboard_records: **{summary['combination_leaderboard_records']}**")
    add(f"- primary_windows: {', '.join(str(w) for w in result['window_policy']['primary_windows'])}")
    add(f"- strategy_window_decision_counts: `{summary['strategy_window_decision_counts']}`")
    add("")

    add("## Best 750-Window Equal-Budget Combinations")
    add("")
    add("| lottery | budget | combo | support | any-hit | prize-signal | any-hit edge | prize edge |")
    add("|---|---:|---|---:|---:|---:|---:|---:|")
    for lt in LOTTERIES:
        for budget in range(1, int(GAME_RULES[lt]["pick_count"]) + 1):
            rec = result["best_combination_by_lottery_window_budget"].get(f"{lt}|750|{budget}")
            if not rec:
                continue
            add(
                f"| {lt} | {budget} | `{rec['combo_id']}` | {rec['support_draws']} | "
                f"{_pct(rec['any_main_hit_rate'])} | {_pct(rec['prize_signal_rate'])} | "
                f"{_pp(rec['any_main_hit_edge_pp'])} | {_pp(rec['prize_signal_edge_pp'])} |"
            )
    add("")

    add("## Top Strategy Pick-K at 750 Window")
    add("")
    add("| lottery | K | strategy | support | any-hit | prize-signal | any-hit edge | prize edge |")
    add("|---|---:|---|---:|---:|---:|---:|---:|")
    top = result["top_strategy_pick_by_lottery_window_pick"]
    for lt in LOTTERIES:
        for k in range(1, int(GAME_RULES[lt]["pick_count"]) + 1):
            rec = top.get(f"{lt}|750|{k}")
            if not rec:
                continue
            add(
                f"| {lt} | {k} | `{rec['strategy_id']}` | {rec['support_draws']} | "
                f"{_pct(rec['any_main_hit_rate'])} | {_pct(rec['prize_signal_rate'])} | "
                f"{_pp(rec['any_main_hit_edge_pp'])} | {_pp(rec['prize_signal_edge_pp'])} |"
            )
    add("")

    add("## Requested Example")
    add("")
    example = result["requested_example_fourier2_cold2_deviation2"]
    add("BIG_LOTTO: `bet2_fourier_expansion_biglotto:2 + cold_complement_biglotto:2 + biglotto_deviation_2bet:2`")
    if example.get("status") == "EVALUATED":
        add("")
        add("| window | support | any-hit | prize-signal | any-hit edge | prize edge |")
        add("|---:|---:|---:|---:|---:|---:|")
        for window in WINDOWS:
            rec = example["windows"][str(window)]
            add(
                f"| {window} | {rec['support_draws']} | {_pct(rec['any_main_hit_rate'])} | "
                f"{_pct(rec['prize_signal_rate'])} | {_pp(rec['any_main_hit_edge_pp'])} | "
                f"{_pp(rec['prize_signal_edge_pp'])} |"
            )
    else:
        add(f"- status: `{example.get('status')}`")
    add("")

    add("## Cross-Lottery Feature Family Reference")
    add("")
    add("| lottery | family | strategies | avg any-hit | avg prize-signal | avg any-hit edge |")
    add("|---|---|---:|---:|---:|---:|")
    for rec in result["feature_family_summary"][:30]:
        add(
            f"| {rec['lottery_type']} | {rec['feature_family']} | {rec['strategy_count']} | "
            f"{_pct(rec['avg_any_main_hit_rate'])} | {_pct(rec['avg_prize_signal_rate'])} | "
            f"{_pp(rec['avg_any_main_hit_edge_pp'])} |"
        )
    add("")

    add("## Safety")
    add("")
    for key, value in result["safety_flags"].items():
        add(f"- {key}: `{str(value).lower()}`")
    add("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build P333 strategy pick scoreboard")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out-json", default=str(OUTPUT_JSON))
    parser.add_argument("--out-md", default=str(OUTPUT_MD))
    args = parser.parse_args(argv)

    result = run_analysis(args.db)
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "strategy_pick_records": result["summary"]["strategy_pick_records"],
                "combination_leaderboard_records": result["summary"]["combination_leaderboard_records"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
