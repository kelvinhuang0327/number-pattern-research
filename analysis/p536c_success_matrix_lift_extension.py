"""P536C — Strategy Success-Rate Matrix Lift Extension (read-only, additive).

Extends the committed P333 strategy pick/combination scoreboard with the
metrics P333 does not compute: hit>=3 main numbers, exact hypergeometric
baselines for hit>=2/hit>=3, lift ratios (observed / baseline), log10 lift,
a cross-lottery normalized-lift comparison, and a stability-rank enrichment
of the existing equal-budget combination leaderboard.

All selection, scoring, hypergeometric-baseline, and combination-search logic
is imported unmodified from analysis/p333_strategy_pick_combination_scoreboard.py.
This module does not re-implement any of that logic; it only adds derived
metrics and a presentation layer on top of it.

This evaluates historical replay performance only, not guaranteed future winning.
Retrospective historical replay evidence only; no prediction, betting, edge,
future-winning, or production-readiness claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.p333_strategy_pick_combination_scoreboard import (  # noqa: E402
    DB_PATH,
    GAME_RULES,
    LOTTERIES,
    MIN_SUPPORT_DRAWS,
    TOP_COMBOS_PER_BUCKET,
    WINDOWS,
    _draw_sort_key,
    _family_for_strategy,
    _hypergeom_at_least,
    _load_replay_draws,
    _open_ro,
    build_combination_leaderboard,
    score_selection,
    select_strategy_numbers,
)

TASK_ID = "P536C"
EXTENDS_TASK_ID = "P333"

OUTPUT_DIR = REPO_ROOT / "outputs" / "research"

DISCLAIMER_EN_HISTORICAL = (
    "This evaluates historical replay performance only, not guaranteed future winning."
)
DISCLAIMER_EN_NO_CLAIM = (
    "Retrospective historical replay evidence only; no prediction, betting, edge, "
    "future-winning, or production-readiness claim."
)

_SOURCE_ROW_QUERY = """
    SELECT lottery_type, strategy_id, target_draw, bet_index,
           predicted_numbers, predicted_special,
           actual_numbers, actual_special
    FROM strategy_prediction_replays
    WHERE lottery_type IN ('BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO')
      AND replay_status = 'PREDICTED'
      AND dry_run = 0
      AND predicted_numbers IS NOT NULL
      AND actual_numbers IS NOT NULL
    ORDER BY lottery_type, strategy_id, CAST(target_draw AS INTEGER) DESC, bet_index
"""

_COMMON_PICK_MAX = min(int(GAME_RULES[lt]["pick_count"]) for lt in LOTTERIES)


def _lift(rate: float | None, baseline: float | None, support: int) -> tuple[float | None, float | None]:
    """observed_rate / baseline_rate; null when baseline<=0 or support<minimum."""
    if rate is None or baseline is None or support < MIN_SUPPORT_DRAWS or baseline <= 0:
        return None, None
    lift = rate / baseline
    log_lift = math.log10(lift) if lift > 0 else None
    return lift, log_lift


def _row_hash(conn: sqlite3.Connection) -> tuple[str, dict[str, int]]:
    """sha256 over the same ordered source rows P333 loads; also returns row counts."""
    rows = conn.execute(_SOURCE_ROW_QUERY).fetchall()
    hasher = hashlib.sha256()
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["lottery_type"]] += 1
        parts = [
            str(row["lottery_type"]),
            str(row["strategy_id"]),
            str(row["target_draw"]),
            str(row["bet_index"]),
            str(row["predicted_numbers"]),
            str(row["predicted_special"]),
            str(row["actual_numbers"]),
            str(row["actual_special"]),
        ]
        hasher.update("|".join(parts).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest(), dict(counts)


def evaluate_strategy_pick_extended(
    by_draw: dict[str, dict], lottery_type: str, strategy_id: str, pick_k: int, window: int
) -> dict[str, Any]:
    """Reuses select_strategy_numbers/score_selection/_hypergeom_at_least from P333;
    adds m3_plus and m2/m3 baselines, then aggregates rate/edge/lift/log10_lift."""
    draws = sorted(by_draw, key=_draw_sort_key, reverse=True)[:window]
    scores: list[dict] = []
    score_draws: list[str] = []
    for draw in draws:
        record = by_draw[draw]
        selected, seconds = select_strategy_numbers(record, pick_k)
        if not selected:
            continue
        s = score_selection(
            lottery_type, selected, seconds, record["actual_numbers"], record["actual_special"]
        )
        s["m3_plus"] = s["main_hits"] >= 3
        s["baseline_m2_plus"] = _hypergeom_at_least(lottery_type, s["selected_count"], 2)
        s["baseline_m3_plus"] = _hypergeom_at_least(lottery_type, s["selected_count"], 3)
        scores.append(s)
        score_draws.append(draw)

    support = len(scores)
    rec: dict[str, Any] = {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "pick_k": pick_k,
        "window": window,
        "support_draws": support,
        "latest_target_draw": score_draws[0] if score_draws else None,
        "earliest_target_draw": score_draws[-1] if score_draws else None,
    }

    metric_defs = (
        ("any_main_hit", "baseline_any_main"),
        ("m2_plus", "baseline_m2_plus"),
        ("m3_plus", "baseline_m3_plus"),
        ("prize_signal", "baseline_prize_signal"),
    )

    if support == 0:
        for metric, _ in metric_defs:
            rec[f"{metric}_count"] = 0
            rec[f"{metric}_rate"] = None
            rec[f"baseline_{metric}_rate"] = None
            rec[f"{metric}_edge_pp"] = None
            rec[f"{metric}_lift"] = None
            rec[f"{metric}_log10_lift"] = None
        return rec

    for metric, baseline_key in metric_defs:
        count = sum(1 for s in scores if s[metric])
        rate = count / support
        baseline_rate = sum(float(s[baseline_key]) for s in scores) / support
        lift, log_lift = _lift(rate, baseline_rate, support)
        rec[f"{metric}_count"] = count
        rec[f"{metric}_rate"] = rate
        rec[f"baseline_{metric}_rate"] = baseline_rate
        rec[f"{metric}_edge_pp"] = (rate - baseline_rate) * 100
        rec[f"{metric}_lift"] = lift
        rec[f"{metric}_log10_lift"] = log_lift
    return rec


def build_matrix(data: dict[str, dict[str, dict]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for lottery_type in LOTTERIES:
        pick_count = int(GAME_RULES[lottery_type]["pick_count"])
        for strategy_id in sorted(data.get(lottery_type, {})):
            by_draw = data[lottery_type][strategy_id]
            for window in WINDOWS:
                for pick_k in range(1, pick_count + 1):
                    rec = evaluate_strategy_pick_extended(
                        by_draw, lottery_type, strategy_id, pick_k, window
                    )
                    rec["feature_family"] = _family_for_strategy(strategy_id)
                    matrix.append(rec)
    return matrix


def build_cross_lottery_normalized_lift(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per feature_family x window x pick_k (pick_k<=common pick count across all
    three lotteries), show each lottery's own lift side-by-side. Raw rates are
    never pooled across lotteries; each lift is computed against that lottery's
    own hypergeometric baseline only."""
    buckets: dict[tuple[str, int, int], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for rec in matrix:
        if rec["pick_k"] > _COMMON_PICK_MAX:
            continue
        if rec["support_draws"] < MIN_SUPPORT_DRAWS:
            continue
        key = (rec["feature_family"], rec["window"], rec["pick_k"])
        buckets[key][rec["lottery_type"]].append(rec)

    def _avg(records: list[dict], field: str) -> float | None:
        vals = [r[field] for r in records if r.get(field) is not None]
        return sum(vals) / len(vals) if vals else None

    out: list[dict[str, Any]] = []
    for (family, window, pick_k), by_lottery in sorted(buckets.items()):
        entry: dict[str, Any] = {
            "feature_family": family,
            "window": window,
            "pick_k": pick_k,
            "lotteries": {},
        }
        for lottery_type, records in sorted(by_lottery.items()):
            entry["lotteries"][lottery_type] = {
                "strategy_count": len({r["strategy_id"] for r in records}),
                "avg_any_main_hit_lift": _avg(records, "any_main_hit_lift"),
                "avg_any_main_hit_log10_lift": _avg(records, "any_main_hit_log10_lift"),
                "avg_m2_plus_lift": _avg(records, "m2_plus_lift"),
                "avg_m3_plus_lift": _avg(records, "m3_plus_lift"),
                "avg_prize_signal_lift": _avg(records, "prize_signal_lift"),
                "avg_prize_signal_log10_lift": _avg(records, "prize_signal_log10_lift"),
            }
        out.append(entry)
    return out


def enrich_combo_leaderboard_with_lift(combo_leaderboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass-through of P333's own (unmodified) build_combination_leaderboard output,
    with lift/log10_lift columns added from the rate/baseline fields already present
    on each record. No new combination search is performed."""
    enriched: list[dict[str, Any]] = []
    for rec in combo_leaderboard:
        out = dict(rec)
        support = int(rec.get("support_draws") or 0)
        any_lift, any_log = _lift(
            rec.get("any_main_hit_rate"), rec.get("baseline_any_main_rate"), support
        )
        prize_lift, prize_log = _lift(
            rec.get("prize_signal_rate"), rec.get("baseline_prize_signal_rate"), support
        )
        out["any_main_hit_lift"] = any_lift
        out["any_main_hit_log10_lift"] = any_log
        out["prize_signal_lift"] = prize_lift
        out["prize_signal_log10_lift"] = prize_log
        enriched.append(out)
    return enriched


def build_combo_stability_rank(enriched_leaderboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stability rank computed only over combo_ids that already appear in P333's
    own top-N-per-bucket leaderboard for at least one of the three windows. This
    is an enrichment pass over existing search results, not an independent
    re-search across all combo candidates in all windows (no search-space
    expansion)."""
    grouped: dict[tuple[str, int, str], dict[int, dict]] = defaultdict(dict)
    for rec in enriched_leaderboard:
        key = (rec["lottery_type"], int(rec["requested_budget"]), rec["combo_id"])
        grouped[key][int(rec["window"])] = rec

    by_bucket: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for (lottery_type, budget, combo_id), by_window in grouped.items():
        windows_present = sorted(by_window)
        prize_lifts = [
            by_window[w]["prize_signal_lift"]
            for w in windows_present
            if by_window[w].get("prize_signal_lift") is not None
        ]
        avg_prize_lift = sum(prize_lifts) / len(prize_lifts) if prize_lifts else None
        entry = {
            "lottery_type": lottery_type,
            "requested_budget": budget,
            "combo_id": combo_id,
            "windows_present": windows_present,
            "windows_present_count": len(windows_present),
            "avg_prize_signal_lift_across_present_windows": avg_prize_lift,
            "per_window": {
                str(w): {
                    "prize_signal_rate": by_window[w].get("prize_signal_rate"),
                    "prize_signal_lift": by_window[w].get("prize_signal_lift"),
                    "any_main_hit_lift": by_window[w].get("any_main_hit_lift"),
                    "support_draws": by_window[w].get("support_draws"),
                }
                for w in windows_present
            },
        }
        by_bucket[(lottery_type, budget)].append(entry)

    stability_records: list[dict[str, Any]] = []
    for key in sorted(by_bucket):
        entries = by_bucket[key]
        entries.sort(
            key=lambda e: (
                e["windows_present_count"],
                e["avg_prize_signal_lift_across_present_windows"]
                if e["avg_prize_signal_lift_across_present_windows"] is not None
                else -999.0,
            ),
            reverse=True,
        )
        for rank, entry in enumerate(entries, start=1):
            entry["stability_rank"] = rank
        stability_records.extend(entries[:TOP_COMBOS_PER_BUCKET])
    return stability_records


def run_analysis(db_path: Path | str = DB_PATH) -> dict[str, Any]:
    conn = _open_ro(db_path)
    try:
        data_hash, row_counts = _row_hash(conn)
        data = _load_replay_draws(conn)
        combo_leaderboard, _best_combo = build_combination_leaderboard(data)
    finally:
        conn.close()

    matrix = build_matrix(data)
    cross_lift = build_cross_lottery_normalized_lift(matrix)
    enriched_combo = enrich_combo_leaderboard_with_lift(combo_leaderboard)
    stability = build_combo_stability_rank(enriched_combo)

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "extends_task_id": EXTENDS_TASK_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P536C_SUCCESS_MATRIX_LIFT_EXTENSION_READY",
        "source": {
            "db_path": str(db_path),
            "tables": ["strategy_prediction_replays"],
            "filters": {
                "lottery_type": list(LOTTERIES),
                "replay_status": "PREDICTED",
                "dry_run": 0,
            },
            "row_counts_by_lottery": row_counts,
            "data_hash_sha256": data_hash,
            "data_hash_fields": [
                "lottery_type", "strategy_id", "target_draw", "bet_index",
                "predicted_numbers", "predicted_special", "actual_numbers", "actual_special",
            ],
            "db_open_mode": "sqlite3 URI mode=ro + PRAGMA query_only=ON",
        },
        "window_policy": {
            "primary_windows": list(WINDOWS),
            "long_history_reference_role": "reference_only_not_decision_gate",
            "minimum_support_draws": MIN_SUPPORT_DRAWS,
            "cross_lottery_common_pick_max": _COMMON_PICK_MAX,
        },
        "metric_definitions": {
            "m3_plus": "main_hits >= 3, independent of the compound BIG_LOTTO/POWER_LOTTO prize_signal rule",
            "baseline_m2_plus": "_hypergeom_at_least(lottery_type, selected_count, 2), reused verbatim from P333",
            "baseline_m3_plus": "_hypergeom_at_least(lottery_type, selected_count, 3), reused verbatim from P333",
            "lift": "observed_rate / baseline_rate; null when baseline<=0 or support_draws < minimum_support_draws",
            "log10_lift": "log10(lift); null when lift is null or lift<=0",
        },
        "methodology_notes": {
            "reuse": (
                "All selection (select_strategy_numbers), scoring (score_selection), "
                "hypergeometric-baseline (_hypergeom_at_least), replay loading "
                "(_load_replay_draws), and combination-search "
                "(build_combination_leaderboard/_combo_candidates/evaluate_combo) logic is "
                "imported unmodified from analysis/p333_strategy_pick_combination_scoreboard.py. "
                "This module adds only m3+, baseline/lift derivations, and a presentation layer."
            ),
            "combination_stability_rank_scope": (
                "Computed only over combo_ids that already appear in P333's own "
                f"top-{TOP_COMBOS_PER_BUCKET}-per-bucket leaderboard for at least one of the "
                "three windows. This is an enrichment pass over existing search results, not "
                "an independent re-search across all combo candidates in all windows -- no "
                "combination search-space expansion was performed."
            ),
            "cross_lottery_normalization": (
                "Never pools raw hit rates across lotteries. Each lottery's lift is "
                "rate/baseline computed against its own lottery-specific hypergeometric "
                "baseline; lotteries are shown side-by-side only at pick_k values common to "
                f"all three games (pick_k <= {_COMMON_PICK_MAX})."
            ),
        },
        "strategy_pick_matrix_lift_extension": matrix,
        "cross_lottery_normalized_lift": cross_lift,
        "combination_leaderboard_with_lift": enriched_combo,
        "combination_stability_rank": stability,
        "summary": {
            "matrix_records": len(matrix),
            "cross_lottery_normalized_lift_records": len(cross_lift),
            "combination_leaderboard_with_lift_records": len(enriched_combo),
            "combination_stability_rank_records": len(stability),
        },
        "safety_flags": {
            "db_read_only": True,
            "db_write": False,
            "replay_generation": False,
            "model_training": False,
            "registry_mutation": False,
            "strategy_promotion": False,
            "betting_advice": False,
        },
        "disclaimer_en": [DISCLAIMER_EN_HISTORICAL, DISCLAIMER_EN_NO_CLAIM],
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


def _fmt_lift(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}x"


def _fmt_log_lift(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def _top_lift_cells(matrix: list[dict[str, Any]], window: int, n: int = 5) -> list[dict[str, Any]]:
    candidates = [
        r for r in matrix
        if r["window"] == window and r.get("prize_signal_lift") is not None
    ]
    candidates.sort(key=lambda r: r["prize_signal_lift"], reverse=True)
    return candidates[:n]


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P536C — Strategy Success-Rate Matrix Lift Extension")
    add("")
    add(f"> {DISCLAIMER_EN_HISTORICAL}")
    add(f"> {DISCLAIMER_EN_NO_CLAIM}")
    add("")
    add(f"Extends: **{result['extends_task_id']}** (analysis/p333_strategy_pick_combination_scoreboard.py)")
    add("")
    add("## Summary")
    add("")
    summary = result["summary"]
    for key, value in summary.items():
        add(f"- {key}: **{value}**")
    add(f"- data_hash_sha256: `{result['source']['data_hash_sha256']}`")
    add(f"- row_counts_by_lottery: `{result['source']['row_counts_by_lottery']}`")
    add("")

    add("## Top Prize-Signal Lift Cells Per Window")
    add("")
    add("| window | lottery | strategy | pick_k | support | prize-signal rate | baseline | lift | log10(lift) |")
    add("|---:|---|---|---:|---:|---:|---:|---:|---:|")
    matrix = result["strategy_pick_matrix_lift_extension"]
    for window in WINDOWS:
        for rec in _top_lift_cells(matrix, window):
            add(
                f"| {window} | {rec['lottery_type']} | `{rec['strategy_id']}` | {rec['pick_k']} | "
                f"{rec['support_draws']} | {_pct(rec['prize_signal_rate'])} | "
                f"{_pct(rec['baseline_prize_signal_rate'])} | {_fmt_lift(rec['prize_signal_lift'])} | "
                f"{_fmt_log_lift(rec.get('prize_signal_log10_lift'))} |"
            )
    add("")

    add("## Methodology Notes")
    add("")
    for key, value in result["methodology_notes"].items():
        add(f"- **{key}**: {value}")
    add("")

    add("## Safety")
    add("")
    for key, value in result["safety_flags"].items():
        add(f"- {key}: `{str(value).lower()}`")
    add("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    if out_json.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_json}")
    if out_md.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_md}")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result) + "\n", encoding="utf-8")


def _default_dated_paths() -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"p536c_success_matrix_lift_extension_{stamp}.json"
    md_path = OUTPUT_DIR / f"p536c_success_matrix_lift_extension_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P536C success-rate matrix lift extension")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_analysis(args.db)
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "summary": result["summary"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
