"""P271D — read-only schema/data-flow/causality feasibility audit.

Determines whether existing replay (`strategy_prediction_replays`) and draw
(`draws`) data in the canonical DB contain the inputs required by
`lottery_api.prize_aware_scorer.score_prize_aware_ticket` for each of
POWER_LOTTO, BIG_LOTTO, and DAILY_539.

This script is read-only:
  * Opens the canonical DB with sqlite3 URI mode=ro (no writes possible).
  * Issues only SELECT statements.
  * Does NOT import or call lottery_api.prize_aware_scorer.
  * Does NOT compute hit counts, special hits, tier classes, endpoint flags,
    success rates, or any prize-aware/strategy-level metric.
  * Does NOT compare predicted values against actual values.

Running this script regenerates the structural metrics embedded in
outputs/research/p271d_prize_aware_replay_input_feasibility_audit_20260612.json.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

LOTTERY_TYPES = ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")

_MAIN_PICK_COUNT = {"POWER_LOTTO": 6, "BIG_LOTTO": 6, "DAILY_539": 5}
_MAIN_NUMBER_RANGE = {
    "POWER_LOTTO": (1, 38),
    "BIG_LOTTO": (1, 49),
    "DAILY_539": (1, 39),
}


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the canonical DB strictly read-only (sqlite3 URI mode=ro)."""
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _is_valid_number_list(raw: str | None, expected_len: int, lo: int, hi: int) -> bool:
    if raw is None:
        return False
    try:
        values = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(values, list) or len(values) != expected_len:
        return False
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in values):
        return False
    if len(set(values)) != len(values):
        return False
    return all(lo <= x <= hi for x in values)


def compute_structural_metrics(conn: sqlite3.Connection) -> dict:
    """Compute data-availability structural metrics for each lottery type.

    No comparisons between predicted and actual numbers are made.
    """
    cur = conn.cursor()
    metrics: dict[str, dict] = {}

    for lt in LOTTERY_TYPES:
        expected_len = _MAIN_PICK_COUNT[lt]
        lo, hi = _MAIN_NUMBER_RANGE[lt]

        cur.execute(
            "SELECT predicted_numbers, actual_numbers, predicted_special, "
            "actual_special, history_cutoff_draw, target_draw "
            "FROM strategy_prediction_replays WHERE lottery_type = ?",
            (lt,),
        )
        rows = cur.fetchall()
        total = len(rows)

        cur.execute(
            "SELECT COUNT(DISTINCT target_draw) FROM strategy_prediction_replays "
            "WHERE lottery_type = ?",
            (lt,),
        )
        target_draws_represented = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM strategy_prediction_replays r
            WHERE r.lottery_type = ? AND EXISTS (
                SELECT 1 FROM draws d
                WHERE d.lottery_type = r.lottery_type AND d.draw = r.target_draw
            )
            """,
            (lt,),
        )
        joinable_to_one_draw = cur.fetchone()[0]

        parseable_pred_main = 0
        missing_actual_main = 0
        missing_actual_aux = 0
        cardinality_range_dup_failures = 0
        causality_verifiable = 0
        predicted_aux_present = 0
        structurally_eligible = 0

        for pred, act, pred_special, act_special, cutoff, target in rows:
            pred_ok = _is_valid_number_list(pred, expected_len, lo, hi)
            act_ok = _is_valid_number_list(act, expected_len, lo, hi)

            if pred_ok:
                parseable_pred_main += 1
            if not act_ok:
                missing_actual_main += 1
            if not pred_ok or not act_ok:
                cardinality_range_dup_failures += 1

            if lt == "POWER_LOTTO":
                if act_special is None:
                    missing_actual_aux += 1
                if pred_special is not None and 1 <= pred_special <= 8:
                    predicted_aux_present += 1
            elif lt == "BIG_LOTTO":
                if act_special is None:
                    missing_actual_aux += 1
                # No predicted auxiliary field required for BIG_LOTTO.
            else:  # DAILY_539
                # No auxiliary field allowed/required for DAILY_539.
                pass

            cutoff_ok = False
            try:
                if cutoff is not None and target is not None:
                    cutoff_ok = int(cutoff) < int(target)
            except (TypeError, ValueError):
                cutoff_ok = False
            if cutoff_ok:
                causality_verifiable += 1

            if lt == "POWER_LOTTO":
                eligible = (
                    pred_ok
                    and act_ok
                    and act_special is not None
                    and (pred_special is not None and 1 <= pred_special <= 8)
                    and cutoff_ok
                )
            elif lt == "BIG_LOTTO":
                eligible = pred_ok and act_ok and act_special is not None and cutoff_ok
            else:  # DAILY_539
                eligible = pred_ok and act_ok and cutoff_ok

            if eligible:
                structurally_eligible += 1

        metrics[lt] = {
            "total_replay_rows": total,
            "parseable_predicted_main_rows": parseable_pred_main,
            "rows_with_required_predicted_aux_field": (
                predicted_aux_present if lt == "POWER_LOTTO" else total
            ),
            "target_draws_represented": target_draws_represented,
            "rows_joinable_to_one_actual_draw": joinable_to_one_draw,
            "rows_missing_actual_main_result": missing_actual_main,
            "rows_missing_actual_aux_result": missing_actual_aux,
            "rows_failing_cardinality_range_or_duplicate_validation": (
                cardinality_range_dup_failures
            ),
            "causality_verifiable_rows": causality_verifiable,
            "structurally_eligible_rows": structurally_eligible,
            "structurally_eligible_percentage": (
                round(100.0 * structurally_eligible / total, 4) if total else 0.0
            ),
        }

    return metrics


def main() -> None:
    conn = _open_readonly(CANONICAL_DB_PATH)
    try:
        metrics = compute_structural_metrics(conn)
    finally:
        conn.close()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
