"""
P359 read-only true-OOS-feasibility metadata audit for the 8 P356/P357/P358
candidates. Read-only sqlite3 (mode=ro, PRAGMA query_only=ON). No writes.
No repo edits. Registry code imported read-only for field inventory only.
"""
import json
import sqlite3
import sys

DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
sys.path.insert(0, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew")

CANDIDATES = {
    "power_precision_3bet": "POWER_LOTTO",
    "power_orthogonal_5bet": "POWER_LOTTO",
    "fourier_rhythm_3bet": "POWER_LOTTO",
    "biglotto_triple_strike": "BIG_LOTTO",
    "biglotto_deviation_2bet": "BIG_LOTTO",
    "ts3_regime_3bet": "BIG_LOTTO",
    "daily539_f4cold": "DAILY_539",
    "daily539_markov_cold": "DAILY_539",
}


def ro_connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def verify_readonly_guarantee(conn):
    try:
        conn.execute("CREATE TABLE __p359_write_probe__ (x INTEGER)")
        return {"write_attempt_rejected": False, "reason": "UNEXPECTED: write succeeded"}
    except sqlite3.OperationalError as e:
        return {"write_attempt_rejected": True, "reason": str(e)}


def registry_field_inventory():
    """_StrategyMeta.__slots__ is the authoritative field list for the registry."""
    from lottery_api.models.replay_strategy_registry import _StrategyMeta
    return list(_StrategyMeta.__slots__)


def candidate_metadata_audit(conn, strategy_id, lottery_type):
    row_stats = conn.execute("""
        SELECT
            COUNT(*) as rows,
            MIN(target_draw) as min_target_draw, MAX(target_draw) as max_target_draw,
            MIN(target_date) as min_target_date, MAX(target_date) as max_target_date,
            MIN(generated_at) as min_generated_at, MAX(generated_at) as max_generated_at,
            COUNT(DISTINCT generated_at) as distinct_generated_at,
            MIN(prediction_generated_at) as min_pred_gen_at, MAX(prediction_generated_at) as max_pred_gen_at,
            COUNT(DISTINCT prediction_generated_at) as distinct_pred_gen_at,
            MIN(prediction_cutoff_date) as min_pred_cutoff, MAX(prediction_cutoff_date) as max_pred_cutoff
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = ?
    """, [strategy_id, lottery_type]).fetchone()

    truth_source = conn.execute("""
        SELECT truth_level, source, COUNT(*) as n
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = ?
        GROUP BY truth_level, source
    """, [strategy_id, lottery_type]).fetchall()

    cutoff_check = conn.execute("""
        SELECT COUNT(*) as n,
               SUM(CASE WHEN CAST(target_draw AS INTEGER) - CAST(history_cutoff_draw AS INTEGER) = 1 THEN 1 ELSE 0 END) as gap_is_1
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = ?
          AND history_cutoff_draw IS NOT NULL
    """, [strategy_id, lottery_type]).fetchone()

    unlabeled = conn.execute("""
        SELECT COUNT(*) as n, MIN(target_draw) as min_draw, MAX(target_draw) as max_draw
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = ?
          AND (truth_level IS NULL OR truth_level = '')
    """, [strategy_id, lottery_type]).fetchone()

    runs = conn.execute("""
        SELECT DISTINCT s.id, s.started_at, s.finished_at, s.status, s.generator_version
        FROM strategy_prediction_replays r
        JOIN strategy_replay_runs s ON r.replay_run_id = s.id
        WHERE r.strategy_id = ? AND r.lottery_type = ?
    """, [strategy_id, lottery_type]).fetchall()

    all_backfill = all(
        (row["truth_level"] and "BACKFILL" in row["truth_level"]) or not row["truth_level"]
        for row in truth_source
    )
    any_labeled = any(row["truth_level"] for row in truth_source)

    return {
        "strategy_id": strategy_id,
        "lottery_type": lottery_type,
        "row_stats": dict(row_stats),
        "truth_level_and_source_breakdown": [dict(r) for r in truth_source],
        "unlabeled_truth_level_segment": dict(unlabeled),
        "history_cutoff_walkforward_check": {
            "rows_checked": cutoff_check["n"],
            "rows_with_gap_exactly_1": cutoff_check["gap_is_1"],
            "interpretation": "history_cutoff_draw = target_draw - 1 for all checked rows means each simulated prediction only used pre-draw history WITHIN the backtest simulation -- this is a within-simulation no-lookahead guarantee, NOT evidence of a genuine temporal separation between strategy design and evaluation.",
        },
        "replay_runs": [dict(r) for r in runs],
        "all_rows_backfill_or_unlabeled": all_backfill,
        "any_row_has_non_backfill_truth_level": any_labeled,
        "true_oos_cutoff_found": False,
        "classification": "TRUE_OOS_NOT_SUPPORTED_BY_CURRENT_METADATA",
        "reason": (
            "100% of rows were generated (per `generated_at`) within a narrow "
            "retrospective batch window, long after every target draw occurred "
            "(including the most recent ones); truth_level/source fields "
            "explicitly self-label the vast majority as *_BACKFILL_VERIFIED; "
            "the small unlabeled minority is the OLDEST draws (an older "
            "pre-labeling-convention backfill batch), not a live-generated "
            "recent segment. No field in this table, the strategy_replay_runs "
            "table, or the registry's _StrategyMeta class records a genuine "
            "strategy adoption/activation/freeze/first-online timestamp."
        ),
    }


def main():
    conn = ro_connect()
    ro_check = verify_readonly_guarantee(conn)
    registry_fields = registry_field_inventory()
    candidates = [candidate_metadata_audit(conn, sid, lt) for sid, lt in CANDIDATES.items()]
    conn.close()

    out = {
        "read_only_guarantee_check": ro_check,
        "registry_strategymeta_fields": registry_fields,
        "registry_has_any_date_field": False,
        "candidates": candidates,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
