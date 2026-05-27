"""
P112: Cross-Lottery Prediction-Helpfulness Audit
=================================================
Read-only script. Queries existing DB only.
Classifies each row-backed strategy as:
  PREDICTION_HELPFUL | WATCHLIST_CANDIDATE | OBSERVE_MORE |
  SUB_BASELINE | FALLBACK_EQUIVALENT | INCONCLUSIVE | INSUFFICIENT_DATA

No SQL write verbs (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, REPLACE,
VACUUM, PRAGMA writable_schema).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DB_PATH = Path("lottery_api/data/lottery_v2.db")

# Game rules (confirmed from DB inspection)
# POWER_LOTTO: 6 main from 1-38, 1 special from 1-8
POWER_POOL = 38
POWER_DRAW = 6
POWER_SPECIAL_POOL = 8

# DAILY_539: 5 from 1-39
D539_POOL = 39
D539_DRAW = 5

# BIG_LOTTO: 6 from 1-49, special = bonus ball (strategies do not predict it)
BIG_POOL = 49
BIG_DRAW = 6

# Baseline expected hit rates (hypergeometric E[hits] = k * k / N)
BASELINES = {
    "POWER_LOTTO": {
        "main": POWER_DRAW * POWER_DRAW / POWER_POOL,       # 6*6/38 ≈ 0.9474
        "special": 1.0 / POWER_SPECIAL_POOL,               # 1/8 = 0.1250
    },
    "DAILY_539": {
        "main": D539_DRAW * D539_DRAW / D539_POOL,          # 5*5/39 ≈ 0.6410
        "special": None,
    },
    "BIG_LOTTO": {
        "main": BIG_DRAW * BIG_DRAW / BIG_POOL,             # 6*6/49 ≈ 0.7347
        "special": None,
    },
}

# Classification edge thresholds (main-number edge vs baseline)
EDGE_PREDICTION_HELPFUL = 0.05
EDGE_WATCHLIST = 0.01
EDGE_FALLBACK_LOWER = -0.01   # -0.01 ≤ edge ≤ 0.01 → FALLBACK_EQUIVALENT
EDGE_SUB_BASELINE = -0.01     # edge < -0.01 → SUB_BASELINE
MIN_ROWS = 200                # below this → INSUFFICIENT_DATA

VALID_CLASSIFICATIONS = {
    "PREDICTION_HELPFUL",
    "WATCHLIST_CANDIDATE",
    "OBSERVE_MORE",
    "SUB_BASELINE",
    "FALLBACK_EQUIVALENT",
    "INCONCLUSIVE",
    "INSUFFICIENT_DATA",
}

AUDIT_SCOPE = ["POWER_LOTTO", "DAILY_539", "BIG_LOTTO"]


# ---------------------------------------------------------------------------
# DB helpers (read-only; no write SQL verbs)
# ---------------------------------------------------------------------------
def open_db(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.resolve()
    uri = resolved.as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def query_replay_total(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def query_draw_snapshot(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
        "FROM draws WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') "
        "GROUP BY lottery_type"
    ).fetchall()
    snap = {}
    for lt, cnt, mx in rows:
        snap[lt] = {"count": cnt, "max_draw": str(mx)}
    return snap


def query_per_lottery(conn: sqlite3.Connection, lottery_type: str) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*) as total_rows,
               SUM(CASE WHEN replay_status='PREDICTED' THEN 1 ELSE 0 END) as predicted,
               COUNT(DISTINCT strategy_id) as strategy_count,
               MIN(target_draw) as min_draw,
               MAX(target_draw) as max_draw
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        """,
        (lottery_type,),
    ).fetchone()
    strat_ids = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays "
            "WHERE lottery_type = ? ORDER BY strategy_id",
            (lottery_type,),
        ).fetchall()
    ]
    draw_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type = ?", (lottery_type,)
    ).fetchone()[0]
    return {
        "lottery_type": lottery_type,
        "draw_count": draw_count,
        "replay_row_count": row[0],
        "predicted_row_count": row[1],
        "strategy_count": row[2],
        "strategy_ids": strat_ids,
        "min_target_draw": row[3],
        "max_target_draw": row[4],
    }


def query_per_strategy(
    conn: sqlite3.Connection, lottery_type: str, strategy_id: str
) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*) as n,
               AVG(CASE WHEN replay_status='PREDICTED' THEN hit_count ELSE NULL END) as avg_hit,
               AVG(CASE WHEN replay_status='PREDICTED' THEN special_hit ELSE NULL END) as avg_sp,
               SUM(CASE WHEN replay_status='PREDICTED' THEN 1 ELSE 0 END) as predicted_n,
               SUM(CASE WHEN replay_status='REPLAY_ERROR' THEN 1 ELSE 0 END) as error_n
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND strategy_id = ?
        """,
        (lottery_type, strategy_id),
    ).fetchone()
    return {
        "total_rows": row[0],
        "predicted_n": row[3] or 0,
        "error_n": row[4] or 0,
        "avg_hit": row[1],
        "avg_sp": row[2],
    }


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------
def classify_strategy(
    strategy_id: str,
    lottery_type: str,
    avg_hit: float | None,
    avg_sp: float | None,
    predicted_n: int,
) -> tuple[str, str, dict]:
    """
    Returns (classification, edge_label, metrics_dict).
    """
    if predicted_n < MIN_ROWS or avg_hit is None:
        return (
            "INSUFFICIENT_DATA",
            "n/a",
            {"note": f"predicted_n={predicted_n} < MIN_ROWS={MIN_ROWS}"},
        )

    bl = BASELINES.get(lottery_type)
    if bl is None:
        return "INCONCLUSIVE", "n/a", {"note": "lottery_type not in audit scope"}

    baseline_main = bl["main"]
    baseline_special = bl["special"]

    edge_main = avg_hit - baseline_main
    edge_main_rounded = round(edge_main, 6)

    sp_edge = None
    sp_summary = "not_applicable"
    strategy_predicts_special = avg_sp is not None and avg_sp > 0.0

    if baseline_special is not None and avg_sp is not None:
        if not strategy_predicts_special:
            sp_summary = "strategy_does_not_predict_special"
        else:
            sp_edge = avg_sp - baseline_special
            if sp_edge > 0.01:
                sp_summary = "above_baseline"
            elif sp_edge < -0.01:
                sp_summary = "below_baseline"
            else:
                sp_summary = "near_baseline"

    # Classify by main-number edge
    if edge_main >= EDGE_PREDICTION_HELPFUL:
        classification = "PREDICTION_HELPFUL"
    elif edge_main >= EDGE_WATCHLIST:
        classification = "WATCHLIST_CANDIDATE"
    elif edge_main >= EDGE_FALLBACK_LOWER:
        classification = "FALLBACK_EQUIVALENT"
    else:
        classification = "SUB_BASELINE"

    # Downgrade WATCHLIST to OBSERVE_MORE only if the strategy actively predicts
    # a special number (avg_sp > 0) but still shows below-baseline special performance.
    # Strategies that do not predict a special (avg_sp == 0) are not penalised.
    if (
        classification == "WATCHLIST_CANDIDATE"
        and sp_summary == "below_baseline"
        and sp_edge is not None
        and sp_edge < -0.015
        and strategy_predicts_special
    ):
        classification = "OBSERVE_MORE"

    sample_status = "adequate" if predicted_n >= MIN_ROWS else "insufficient"

    metrics = {
        "avg_hit": round(avg_hit, 6),
        "baseline_main": round(baseline_main, 6),
        "edge_main": edge_main_rounded,
        "avg_special_hit": round(avg_sp, 6) if avg_sp is not None else None,
        "baseline_special": round(baseline_special, 6) if baseline_special is not None else None,
        "special_edge": round(sp_edge, 6) if sp_edge is not None else None,
        "special_summary": sp_summary,
        "sample_size_status": sample_status,
    }
    return classification, f"{edge_main_rounded:+.4f}", metrics


def recommend(classification: str, lottery_type: str, strategy_id: str) -> str:
    recs = {
        "PREDICTION_HELPFUL": (
            "Keep monitoring. Candidate for promotion to watchlist with next "
            "governance review if edge is stable across temporal windows."
        ),
        "WATCHLIST_CANDIDATE": (
            "Continue observation. Queue for Wave-N targeted optimization. "
            "Review temporal stability before promotion decision."
        ),
        "OBSERVE_MORE": (
            "Mixed signal. Maintain replay coverage. Re-evaluate after 100+ "
            "additional draws are logged."
        ),
        "FALLBACK_EQUIVALENT": (
            "Materially indistinguishable from random/historical-frequency baseline. "
            "Consider demoting or replacing with a more differentiated strategy."
        ),
        "SUB_BASELINE": (
            "Consistently below baseline. Recommend quarantine review. "
            "Do not promote. Consider removal from active replay pool after "
            "governance sign-off."
        ),
        "INCONCLUSIVE": "Insufficient schema support to evaluate. Mark for manual review.",
        "INSUFFICIENT_DATA": "Too few evaluated draws. Maintain replay coverage and re-evaluate.",
    }
    return recs.get(classification, "No recommendation available.")


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------
def run_audit(db_path: Path) -> dict:
    conn = open_db(db_path)

    replay_rows = query_replay_total(conn)
    draw_snapshot = query_draw_snapshot(conn)

    per_lottery_summary = {}
    per_strategy_results = []

    for lt in AUDIT_SCOPE:
        lt_summary = query_per_lottery(conn, lt)
        strat_results = []

        for sid in lt_summary["strategy_ids"]:
            st = query_per_strategy(conn, lt, sid)
            classification, edge_label, metrics = classify_strategy(
                sid, lt, st["avg_hit"], st["avg_sp"], st["predicted_n"]
            )
            rec = recommend(classification, lt, sid)

            result = {
                "strategy_id": sid,
                "lottery_type": lt,
                "replay_rows": st["total_rows"],
                "predicted_rows": st["predicted_n"],
                "error_rows": st["error_n"],
                "primary_metric_name": "avg_hit_count_per_draw",
                "primary_metric_value": metrics.get("avg_hit"),
                "baseline_metric_name": "hypergeometric_expected_hits",
                "baseline_metric_value": metrics.get("baseline_main"),
                "edge_vs_baseline": metrics.get("edge_main"),
                "edge_label": edge_label,
                "special_hit_avg": metrics.get("avg_special_hit"),
                "special_baseline": metrics.get("baseline_special"),
                "special_edge": metrics.get("special_edge"),
                "special_summary": metrics.get("special_summary"),
                "stability_summary": "single_window_only__temporal_split_not_computed",
                "sample_size_status": metrics.get("sample_size_status"),
                "classification": classification,
                "recommendation": rec,
                "caveats": [
                    "hit_count measures number overlap only; prize-tier weighting not applied",
                    "temporal stability across sub-windows not computed (single pooled window)",
                    "4_STAR backtest unauthorized; 4_STAR excluded from this audit",
                    "Special3/P106 evaluation excluded; P108 blocked until 100 prospective draws",
                ],
            }
            strat_results.append(result)
            per_strategy_results.append(result)

        # per-lottery classification summary
        classifications = [r["classification"] for r in strat_results]
        class_counts = {}
        for c in classifications:
            class_counts[c] = class_counts.get(c, 0) + 1

        per_lottery_summary[lt] = {
            **lt_summary,
            "strategy_classification_counts": class_counts,
        }

    # Action recommendations per lottery
    action_recommendations = _build_recommendations(per_strategy_results)

    # Governance confirmations
    snap = draw_snapshot
    three_star = snap.get("3_STAR", {})
    four_star = snap.get("4_STAR", {})
    power_lotto = snap.get("POWER_LOTTO", {})

    artifact = {
        "classification": _overall_classification(per_strategy_results),
        "task_id": "P112_CROSS_LOTTERY_PREDICTION_HELPFULNESS_AUDIT",
        "audit_date": "2026-05-27",
        "audit_scope": AUDIT_SCOPE,
        "excluded_scope": [
            "3_STAR P108 not run because only 63/100 prospective draws are available",
            "4_STAR backtest not authorized because source_unknown",
        ],
        "db_writes": False,
        "replay_rows_before": 54462,
        "replay_rows_after": replay_rows,
        "no_strategy_promotion": True,
        "no_lifecycle_mutation": True,
        "no_registry_mutation": True,
        "no_4star_backtest": True,
        "no_special3_p108_rerun": True,
        "source_unknown_caveat_preserved": True,
        "current_db_snapshot": {
            "replay_rows": replay_rows,
            "three_star_count": three_star.get("count"),
            "three_star_max_draw": three_star.get("max_draw"),
            "four_star_count": four_star.get("count"),
            "four_star_max_draw": four_star.get("max_draw"),
            "power_lotto_count": power_lotto.get("count"),
            "power_lotto_max_draw": power_lotto.get("max_draw"),
        },
        "game_rules_used": {
            "POWER_LOTTO": {"pool": POWER_POOL, "draw_size": POWER_DRAW, "special_pool": POWER_SPECIAL_POOL,
                            "baseline_main": round(BASELINES["POWER_LOTTO"]["main"], 6),
                            "baseline_special": BASELINES["POWER_LOTTO"]["special"]},
            "DAILY_539": {"pool": D539_POOL, "draw_size": D539_DRAW, "special_pool": None,
                          "baseline_main": round(BASELINES["DAILY_539"]["main"], 6),
                          "baseline_special": None},
            "BIG_LOTTO": {"pool": BIG_POOL, "draw_size": BIG_DRAW, "special_pool": None,
                          "baseline_main": round(BASELINES["BIG_LOTTO"]["main"], 6),
                          "baseline_special": None},
        },
        "classification_thresholds": {
            "PREDICTION_HELPFUL": f"edge_main >= {EDGE_PREDICTION_HELPFUL}",
            "WATCHLIST_CANDIDATE": f"{EDGE_WATCHLIST} <= edge_main < {EDGE_PREDICTION_HELPFUL}",
            "FALLBACK_EQUIVALENT": f"{EDGE_FALLBACK_LOWER} <= edge_main < {EDGE_WATCHLIST}",
            "SUB_BASELINE": f"edge_main < {EDGE_SUB_BASELINE}",
        },
        "per_lottery_summary": per_lottery_summary,
        "per_strategy_results": per_strategy_results,
        "action_recommendations": action_recommendations,
        "limitations": [
            "hit_count measures number overlap only; prize-tier weighting not applied",
            "temporal stability across sub-windows not computed (single pooled window)",
            "baseline is hypergeometric expected value E[hits]=k^2/N (simple random)",
            "hit_count==0 rows included in average; REPLAY_ERROR rows excluded from hit avg",
            "4_STAR excluded: backtest remains unauthorized (source_unknown)",
            "3_STAR excluded: Special3 P108 blocked until 37 more prospective draws",
            "BIG_LOTTO special (bonus ball) not predicted by any audited strategy",
            "DAILY_539 special not applicable (game has no separate special ball)",
        ],
        "references": {
            "p105": "DB state acceptance decision (Option A, Special3 evaluation only)",
            "p106": "Special3 Prospective Evaluation Rerun -- PARTIAL, 63/100 draws",
            "p107a": "Special3 100-draw monitoring gate -- 63 draws, 37 remaining",
            "p107b": "Stale baseline guard repair -- P107B_STALE_BASELINE_GUARD_REPAIR_READY",
            "merge_commit_p107b": "e79b5e9",
        },
    }

    conn.close()
    return artifact


def _overall_classification(results: list[dict]) -> str:
    classifications = {r["classification"] for r in results}
    # If we have any actionable classifications, audit is READY
    actionable = classifications & {"PREDICTION_HELPFUL", "WATCHLIST_CANDIDATE", "SUB_BASELINE", "FALLBACK_EQUIVALENT"}
    if not results:
        return "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_INCONCLUSIVE"
    if "INCONCLUSIVE" in classifications and len(actionable) == 0:
        return "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_INCONCLUSIVE"
    if len(classifications - {"INCONCLUSIVE", "INSUFFICIENT_DATA"}) > 0:
        return "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY"
    return "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_PARTIAL"


def _build_recommendations(results: list[dict]) -> list[dict]:
    recs = []
    for lt in AUDIT_SCOPE:
        lt_results = [r for r in results if r["lottery_type"] == lt]
        helpful = [r for r in lt_results if r["classification"] == "PREDICTION_HELPFUL"]
        watchlist = [r for r in lt_results if r["classification"] == "WATCHLIST_CANDIDATE"]
        sub = [r for r in lt_results if r["classification"] == "SUB_BASELINE"]
        fallback = [r for r in lt_results if r["classification"] == "FALLBACK_EQUIVALENT"]
        observe = [r for r in lt_results if r["classification"] == "OBSERVE_MORE"]

        if helpful:
            top = sorted(helpful, key=lambda r: r["edge_vs_baseline"] or 0, reverse=True)
            recs.append({
                "lottery_type": lt,
                "recommendation": "PROMOTE_TO_WATCHLIST_CANDIDATES",
                "top_strategies": [r["strategy_id"] for r in top[:3]],
                "rationale": (
                    f"{len(helpful)} strategy(ies) show edge >= {EDGE_PREDICTION_HELPFUL} vs hypergeometric baseline. "
                    "Queue for governance watchlist review."
                ),
                "next_task_candidate": "P113_WATCHLIST_PROMOTION_GOVERNANCE_REVIEW",
            })

        if watchlist:
            top = sorted(watchlist, key=lambda r: r["edge_vs_baseline"] or 0, reverse=True)
            recs.append({
                "lottery_type": lt,
                "recommendation": "CONTINUE_OBSERVATION_WATCHLIST_CANDIDATES",
                "top_strategies": [r["strategy_id"] for r in top[:5]],
                "rationale": (
                    f"{len(watchlist)} strategy(ies) show positive edge vs baseline. "
                    "Monitor across additional draws before promotion decision."
                ),
                "next_task_candidate": "P114_TEMPORAL_STABILITY_AUDIT",
            })

        if sub:
            recs.append({
                "lottery_type": lt,
                "recommendation": "QUARANTINE_REVIEW",
                "strategies": [r["strategy_id"] for r in sub],
                "rationale": (
                    f"{len(sub)} strategy(ies) consistently below baseline. "
                    "Do not promote. Consider removal from active replay pool after governance sign-off."
                ),
                "next_task_candidate": "P115_STRATEGY_QUARANTINE_GOVERNANCE",
            })

        if fallback:
            recs.append({
                "lottery_type": lt,
                "recommendation": "MARK_FALLBACK_EQUIVALENT",
                "strategies": [r["strategy_id"] for r in fallback],
                "rationale": (
                    f"{len(fallback)} strategy(ies) indistinguishable from random/historical-frequency baseline. "
                    "Consider replacing with more differentiated strategies."
                ),
                "next_task_candidate": "P116_STRATEGY_REPLACEMENT_PLANNING",
            })

        if observe:
            recs.append({
                "lottery_type": lt,
                "recommendation": "MAINTAIN_OBSERVATION",
                "strategies": [r["strategy_id"] for r in observe],
                "rationale": (
                    f"{len(observe)} strategy(ies) show mixed signal. "
                    "Re-evaluate after 100+ additional draws."
                ),
                "next_task_candidate": "P114_TEMPORAL_STABILITY_AUDIT",
            })

    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_summary(artifact: dict) -> None:
    print(f"\n{'='*60}")
    print(f"P112 Cross-Lottery Prediction-Helpfulness Audit")
    print(f"{'='*60}")
    print(f"Classification: {artifact['classification']}")
    print(f"replay_rows_before={artifact['replay_rows_before']}  replay_rows_after={artifact['replay_rows_after']}")
    print(f"\nDB snapshot:")
    snap = artifact["current_db_snapshot"]
    print(f"  3_STAR:      count={snap['three_star_count']}, max_draw={snap['three_star_max_draw']}")
    print(f"  4_STAR:      count={snap['four_star_count']}, max_draw={snap['four_star_max_draw']}")
    print(f"  POWER_LOTTO: count={snap['power_lotto_count']}, max_draw={snap['power_lotto_max_draw']}")
    print()

    for lt in ["POWER_LOTTO", "DAILY_539", "BIG_LOTTO"]:
        lt_s = artifact["per_lottery_summary"].get(lt, {})
        print(f"\n--- {lt} (draws={lt_s.get('draw_count')}, replay_rows={lt_s.get('replay_row_count')}) ---")
        cc = lt_s.get("strategy_classification_counts", {})
        print(f"  Classifications: {cc}")
        lt_results = [r for r in artifact["per_strategy_results"] if r["lottery_type"] == lt]
        for r in sorted(lt_results, key=lambda x: x.get("edge_vs_baseline") or 0, reverse=True):
            mark = "✓" if r["classification"] in ("PREDICTION_HELPFUL", "WATCHLIST_CANDIDATE") else "✗"
            edge = r.get("edge_vs_baseline")
            edge_str = f"{edge:+.4f}" if edge is not None else "N/A"
            print(f"  {mark} {r['strategy_id']:45s} {r['classification']:25s} edge={edge_str}")

    print(f"\nGovernance flags:")
    print(f"  db_writes={artifact['db_writes']}  no_promotion={artifact['no_strategy_promotion']}")
    print(f"  no_4star_backtest={artifact['no_4star_backtest']}  no_p108_rerun={artifact['no_special3_p108_rerun']}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="P112 Cross-Lottery Prediction-Helpfulness Audit")
    parser.add_argument("--json-out", type=Path, default=None, help="Path to write JSON artifact")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to lottery_v2.db")
    args = parser.parse_args()

    artifact = run_audit(args.db)
    print_summary(artifact)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        print(f"JSON artifact written to: {args.json_out}")


if __name__ == "__main__":
    main()
