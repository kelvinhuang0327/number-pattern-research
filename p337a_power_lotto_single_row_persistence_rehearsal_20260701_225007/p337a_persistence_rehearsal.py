#!/usr/bin/env python3
"""
P337A — POWER_LOTTO single-row persistence rehearsal (TEMP/REHEARSAL DB ONLY).

Proves ONE POWER_LOTTO row can flow through:
    generate  ->  second-zone guard  ->  persist
into a temp/rehearsal DB created under the P337A evidence root.

HARD BOUNDARIES (enforced by construction):
  - NO canonical DB write. This script never opens
    lottery_api/data/lottery_v2.db. It only touches a fresh temp DB under the
    evidence root.
  - NO historical backfill. The row is a NEW forward row for a fictional target;
    no existing replay row is read or mutated.
  - NOT a prediction / betting / recommendation. All inputs are synthetic and
    fixed, labeled TEST_DATA_ONLY / NOT_RECOMMENDED. Prior POWER second-zone
    findings remain negative and unchanged.

Reuse (no new algorithm invented):
  - P336A  build_power_lotto_forward_replay_row(...)   (generate the row)
  - P335A  second_zone_predict(history)                (invoked inside builder)
  - P335A  assert_power_lotto_predicted_special(row)   (guard, run again pre-insert)

Determinism: synthetic history + first zone are fixed (no RNG), so re-running
yields the same predicted_special and the same persisted row.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

# --- Paths -----------------------------------------------------------------
WORKTREE = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a"
EVIDENCE_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMP_DB = os.path.join(EVIDENCE_ROOT, "p337a_rehearsal_temp.db")
SUMMARY_JSON = os.path.join(EVIDENCE_ROOT, "rehearsal_output.json")

# Import the P336A builder + P335A helpers from the worktree WITHOUT changing CWD
# into the repo (CWD stays the evidence root so any stray relative-path file would
# land here in isolation, never near the canonical DB).
sys.path.insert(0, WORKTREE)

from lottery_api.models.power_lotto_forward_replay_row import (  # noqa: E402
    build_power_lotto_forward_replay_row,
)
from lottery_api.models.power_lotto_second_zone import (  # noqa: E402
    InsufficientHistoryError,
    assert_power_lotto_predicted_special,
    second_zone_predict,
)

# --- Exact schema copied from lottery_api/database.py (origin/main ce2c042) --
# Both the parent (strategy_replay_runs) and child (strategy_prediction_replays)
# tables + indexes are reproduced verbatim so the temp DB is an authentic copy
# of the production shape, including the FOREIGN KEY and UNIQUE constraints.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS strategy_replay_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_type TEXT NOT NULL,
    strategy_scope TEXT NOT NULL DEFAULT 'ALL',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    generator_version TEXT NOT NULL DEFAULT 'v0.1',
    data_hash TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_srr_lottery ON strategy_replay_runs(lottery_type);
CREATE INDEX IF NOT EXISTS idx_srr_status ON strategy_replay_runs(status);

CREATE TABLE IF NOT EXISTS strategy_prediction_replays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_type TEXT NOT NULL,
    target_draw TEXT NOT NULL,
    target_date TEXT,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL DEFAULT 'v0.1',
    history_cutoff_draw TEXT,
    replay_status TEXT NOT NULL,
    reject_reason TEXT,
    predicted_numbers TEXT,
    predicted_special INTEGER,
    actual_numbers TEXT,
    actual_special INTEGER,
    hit_numbers TEXT,
    hit_count INTEGER DEFAULT 0,
    special_hit INTEGER DEFAULT 0,
    replay_run_id INTEGER,
    generated_at TEXT,
    FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id),
    UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
);
CREATE INDEX IF NOT EXISTS idx_spr_lottery ON strategy_prediction_replays(lottery_type);
CREATE INDEX IF NOT EXISTS idx_spr_strategy ON strategy_prediction_replays(strategy_id);
CREATE INDEX IF NOT EXISTS idx_spr_draw ON strategy_prediction_replays(target_draw);
CREATE INDEX IF NOT EXISTS idx_spr_status ON strategy_prediction_replays(replay_status);
CREATE INDEX IF NOT EXISTS idx_spr_run ON strategy_prediction_replays(replay_run_id);
CREATE INDEX IF NOT EXISTS idx_spr_hit ON strategy_prediction_replays(hit_count);
"""


def build_synthetic_history(n: int = 60):
    """Deterministic TEST_DATA_ONLY causal history (>= MIN_HISTORY=30 draws).

    Each draw carries the three keys the builder / helper actually read:
      - "draw"    (id string)   -> builder history_cutoff_draw
      - "date"    (date string) -> builder prediction_cutoff_date
      - "special" (int 1..8)    -> second_zone_predict input
    No RNG: fully reproducible.
    """
    hist = []
    for i in range(n):
        special = ((i * 7 + 3) % 8) + 1  # deterministic sweep over 1..8
        hist.append(
            {
                "draw": str(114000000 + i),
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "special": special,
            }
        )
    return hist


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    out = {"label": "TEST_DATA_ONLY / NOT_RECOMMENDED", "steps": {}}

    # --- STEP 1: synthetic inputs (TEST_DATA_ONLY) -------------------------
    history = build_synthetic_history(60)
    # Fixed, obviously-synthetic first zone supplied as INPUT (the builder does
    # not generate the first zone; the caller supplies it). [1..6] makes it
    # unmistakably a placeholder, NOT a recommended bet.
    first_zone_test = [1, 2, 3, 4, 5, 6]
    out["steps"]["1_inputs"] = {
        "history_len": len(history),
        "min_history_required": 30,
        "first_zone_TEST_DATA_ONLY": first_zone_test,
        "history_last_draw": history[-1]["draw"],
    }

    # --- STEP 2: GENERATE the forward row (builder calls second_zone_predict +
    #             the guard internally). dry_run=False => guard ENFORCES. -----
    row = build_power_lotto_forward_replay_row(
        strategy_id="p337a_rehearsal_powerlotto",
        strategy_name="P337A Persistence Rehearsal (TEST_DATA_ONLY)",
        strategy_version="rehearsal-p337a",
        target_draw_id="114000060",
        target_draw_date="2026-07-04",
        history=history,
        predicted_numbers=first_zone_test,
        dry_run=False,
    )
    out["steps"]["2_generate"] = {
        "builder": "build_power_lotto_forward_replay_row",
        "predicted_special_TEST_DATA_ONLY": row["predicted_special"],
        "replay_status": row["replay_status"],
        "dry_run_field": row["dry_run"],
        "actual_numbers": row["actual_numbers"],
        "hit_count": row["hit_count"],
    }

    # --- STEP 3: GUARD executed explicitly BEFORE insert -------------------
    # (independent of the builder's own internal guard call at line 195)
    assert_power_lotto_predicted_special(row)  # passes: non-null in [1,8]
    guard_ran_and_passed = True

    # Negative control (does NOT insert anything): a NULL predicted_special on a
    # production (dry_run=0) POWER_LOTTO row MUST be rejected by the guard.
    guard_blocks_null = False
    try:
        bad = dict(row)
        bad["predicted_special"] = None
        bad["dry_run"] = 0
        assert_power_lotto_predicted_special(bad)
    except ValueError:
        guard_blocks_null = True

    # Negative control: insufficient history MUST raise (no silent default).
    guard_blocks_short_history = False
    try:
        second_zone_predict(history[:5])
    except InsufficientHistoryError:
        guard_blocks_short_history = True

    out["steps"]["3_guard"] = {
        "guard": "assert_power_lotto_predicted_special",
        "guard_ran_and_passed_before_insert": guard_ran_and_passed,
        "negative_control_null_special_blocked": guard_blocks_null,
        "negative_control_short_history_blocked": guard_blocks_short_history,
    }

    # --- STEP 4: create TEMP/REHEARSAL DB + copy real schema ---------------
    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)
    conn = sqlite3.connect(TEMP_DB)
    try:
        conn.execute("PRAGMA foreign_keys=ON")  # enforce the real FK/UNIQUE
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # --- STEP 5: INSERT exactly ONE row --------------------------------
        # Map builder dict -> table columns (note: draw_date->target_date,
        # prediction_generated_at->generated_at; predicted_numbers JSON-encoded;
        # replay_run_id left NULL for a forward row not yet tied to a run).
        cur = conn.execute(
            """
            INSERT INTO strategy_prediction_replays (
                lottery_type, target_draw, target_date, strategy_id, strategy_name,
                strategy_version, history_cutoff_draw, replay_status, reject_reason,
                predicted_numbers, predicted_special, actual_numbers, actual_special,
                hit_numbers, hit_count, special_hit, replay_run_id, generated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["lottery_type"],
                row["target_draw"],
                row["draw_date"],
                row["strategy_id"],
                row["strategy_name"],
                row["strategy_version"],
                row["history_cutoff_draw"],
                row["replay_status"],
                row["reject_reason"],
                json.dumps(row["predicted_numbers"]),
                row["predicted_special"],
                row["actual_numbers"],
                row["actual_special"],
                row["hit_numbers"],
                row["hit_count"],
                row["special_hit"],
                None,  # replay_run_id (FK nullable; forward row)
                row["prediction_generated_at"],
            ),
        )
        conn.commit()
        inserted_rowid = cur.lastrowid

        # --- STEP 6: QUERY BACK to prove persistence -----------------------
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        non_null_special = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE predicted_special IS NOT NULL"
        ).fetchone()[0]
        fetched = conn.execute(
            "SELECT id, lottery_type, target_draw, strategy_id, strategy_name, "
            "replay_status, predicted_numbers, predicted_special, actual_numbers, "
            "hit_count, replay_run_id, generated_at "
            "FROM strategy_prediction_replays"
        ).fetchall()
    finally:
        conn.close()

    persisted = fetched[0] if fetched else None
    out["steps"]["5_insert"] = {
        "temp_db": TEMP_DB,
        "inserted_rowid": inserted_rowid,
        "rows_after_insert": total,
    }
    out["steps"]["6_query_back"] = {
        "row_count": total,
        "rows_with_non_null_predicted_special": non_null_special,
        "persisted_row_TEST_DATA_ONLY": {
            "id": persisted[0],
            "lottery_type": persisted[1],
            "target_draw": persisted[2],
            "strategy_id": persisted[3],
            "strategy_name": persisted[4],
            "replay_status": persisted[5],
            "predicted_numbers": persisted[6],
            "predicted_special": persisted[7],
            "actual_numbers": persisted[8],
            "hit_count": persisted[9],
            "replay_run_id": persisted[10],
            "generated_at": persisted[11],
        }
        if persisted
        else None,
    }

    # --- Validation booleans ----------------------------------------------
    validations = {
        "exactly_one_row_inserted": total == 1,
        "inserted_row_non_null_predicted_special": non_null_special == 1
        and persisted is not None
        and persisted[7] is not None,
        "guard_ran_before_insert": guard_ran_and_passed,
        "guard_blocks_null_special": guard_blocks_null,
        "guard_blocks_short_history": guard_blocks_short_history,
        "forward_row_actual_is_null": persisted is not None and persisted[8] is None,
        "predicted_special_in_range_1_8": persisted is not None
        and isinstance(persisted[7], int)
        and 1 <= persisted[7] <= 8,
    }
    out["validations"] = validations
    out["all_validations_pass"] = all(validations.values())
    out["temp_db_sha256"] = sha256_file(TEMP_DB)
    out["temp_db_size_bytes"] = os.path.getsize(TEMP_DB)
    out["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    with open(SUMMARY_JSON, "w") as fh:
        json.dump(out, fh, indent=2)

    print(json.dumps(out, indent=2))
    print("\n=== P337A REHEARSAL:", "PASS" if out["all_validations_pass"] else "FAIL", "===")
    return 0 if out["all_validations_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
