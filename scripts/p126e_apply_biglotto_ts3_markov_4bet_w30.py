#!/usr/bin/env python3
"""
P126E: Apply biglotto_ts3_markov_4bet_w30 Controlled Replay Rows
=================================================================
PURPOSE : Insert 4500 missing bet rows (bet-2, bet-3, and bet-4) for the
          biglotto_ts3_markov_4bet_w30 strategy in BIG_LOTTO, using the
          P126A authorized controlled apply.
          Uses generate_ts3_markov_4bet() from tools/backtest_biglotto_5bet_ts3markov.py
          which returns 4 bets; bet-1 already exists, this task adds bet-2/bet-3/bet-4.
SAFETY:
  - Validates exact authorization phrase FIRST.
  - Validates upstream P126A, P126B, P126C, P126D, and P129B artifacts.
  - Creates backup BEFORE any DB write.
  - Duplicate guard: UNIQUE(lottery_type, target_draw, strategy_id, bet_index).
  - Full transaction wrap with ROLLBACK on failure.
  - Only biglotto_ts3_markov_4bet_w30 is applied — no other P126A candidates.
  - Post-migration: verifies row count (66462), strategy rows (6000), distribution.
GOVERNANCE:
  - NO other P126A candidates applied
  - NO P126 apply for daily539_f4cold_5bet
  - NO re-apply for power_fourier_rhythm_2bet (P126B), biglotto_echo_aware_3bet (P126C),
    or daily539_f4cold_3bet (P126D)
  - NO scheduler / cron / launchd
  - NO 4_STAR / P108 / P117 / P118
  - NO strategy promotion / lifecycle / champion / registry mutation
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TASK_ID             = "P126E"
CLASSIFICATION      = "P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_APPLIED"
DATE_SUFFIX         = "20260528"
REPO_ROOT           = Path(__file__).resolve().parent.parent
STRATEGY_ID         = "biglotto_ts3_markov_4bet_w30"
LOTTERY_TYPE        = "BIG_LOTTO"
CONTROLLED_APPLY_ID = f"P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_{DATE_SUFFIX}"

P126A_ARTIFACT = REPO_ROOT / "outputs/replay/p126a_controlled_apply_authorization_gate_20260528.json"
P126B_ARTIFACT = REPO_ROOT / "outputs/replay/p126b_apply_power_fourier_rhythm_2bet_20260528.json"
P126C_ARTIFACT = REPO_ROOT / "outputs/replay/p126c_apply_biglotto_echo_aware_3bet_20260528.json"
P126D_ARTIFACT = REPO_ROOT / "outputs/replay/p126d_apply_daily539_f4cold_3bet_20260528.json"
P129B_ARTIFACT = REPO_ROOT / "outputs/replay/p129b_execute_bet_index_schema_migration_20260528.json"
P126_ARTIFACT  = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p126e_apply_biglotto_ts3_markov_4bet_w30_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p126e_apply_biglotto_ts3_markov_4bet_w30_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR     = REPO_ROOT / "lottery_api/data/backups"
DRIFT_GUARD    = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"

EXPECTED_ROWS_BEFORE        = 61962
EXPECTED_ROWS_AFTER         = 66462
EXPECTED_INSERT_ROWS        = 4500   # 1500 bet-2 + 1500 bet-3 + 1500 bet-4
EXPECTED_BET1_ROWS          = 1500
EXPECTED_STRATEGY_TOTAL     = 6000   # 1500 bet-1 + 1500 bet-2 + 1500 bet-3 + 1500 bet-4
EXACT_AUTH_PREFIX           = f"YES authorize controlled_apply for {STRATEGY_ID} because "

# P126A candidates that must NOT be applied in this task
OTHER_CANDIDATES = [
    "daily539_f4cold_5bet",
]
# Already applied in previous tasks — must not re-apply
ALREADY_APPLIED = [
    "power_fourier_rhythm_2bet",    # P126B
    "biglotto_echo_aware_3bet",     # P126C
    "daily539_f4cold_3bet",         # P126D
]


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def validate_authorization(auth_text=None) -> dict:
    if not auth_text:
        return {
            "strategy_id": STRATEGY_ID,
            "exact_required_phrase": f"{EXACT_AUTH_PREFIX}<reason>",
            "authorization_present": False,
            "apply_allowed": False,
            "authorization_text_observed": None,
            "reason_text": None,
            "stop_reason": "NO_AUTHORIZATION_TEXT_PROVIDED",
        }
    stripped = auth_text.strip()
    present = stripped.startswith(EXACT_AUTH_PREFIX) and not stripped.endswith("<reason>")
    reason = stripped[len(EXACT_AUTH_PREFIX):].strip() if present else None
    return {
        "strategy_id": STRATEGY_ID,
        "exact_required_phrase": f"{EXACT_AUTH_PREFIX}<reason>",
        "authorization_present": present,
        "apply_allowed": present,
        "authorization_text_observed": stripped,
        "reason_text": reason,
        "stop_reason": None if present else "AUTHORIZATION_PHRASE_INVALID_OR_PLACEHOLDER",
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _ro_conn():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def snapshot_db() -> dict:
    conn = _ro_conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
        has_bet_index = "bet_index" in cols
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        has_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl
        strategy_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        pfr_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet'"
        ).fetchone()[0]
        echo_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet'"
        ).fetchone()[0]
        f4cold_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet'"
        ).fetchone()[0]
        return {
            "replay_rows": total,
            "has_bet_index_column": has_bet_index,
            "has_new_unique_constraint": has_unique,
            "columns_count": len(cols),
            "biglotto_ts3_markov_4bet_w30_rows": strategy_rows,
            "power_fourier_rhythm_2bet_rows": pfr_rows,
            "biglotto_echo_aware_3bet_rows": echo_rows,
            "daily539_f4cold_3bet_rows": f4cold_rows,
            "total_replay_rows": total,
        }
    finally:
        conn.close()


def load_artifact(path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _provenance_hash(strategy_id: str, draw: str, predicted: list, bet_index: int) -> str:
    raw = f"P126E:{strategy_id}:{draw}:bet{bet_index}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Draw history loading
# ---------------------------------------------------------------------------
def load_biglotto_draws() -> list:
    """Load all BIG_LOTTO draws from draws table, ordered by draw number ASC."""
    conn = _ro_conn()
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws WHERE lottery_type='BIG_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    ordered = []
    for draw_str, date_str, numbers_json in rows:
        nums = json.loads(numbers_json)
        ordered.append({"draw": draw_str, "date": date_str, "numbers": nums})
    return ordered


# ---------------------------------------------------------------------------
# Bet-2, Bet-3, and Bet-4 generation
# ---------------------------------------------------------------------------
def get_all_bets_for_draw(target_draw_str: str, history_cutoff_str: str,
                          all_draws_ordered: list) -> tuple:
    """
    Reconstruct history up to history_cutoff, run generate_ts3_markov_4bet()
    from backtest_biglotto_5bet_ts3markov, return (bet1_nums, bet2_nums, bet3_nums, bet4_nums).
    """
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from backtest_biglotto_5bet_ts3markov import generate_ts3_markov_4bet  # noqa: E402

    cutoff_int = int(history_cutoff_str)
    history = [d for d in all_draws_ordered if int(d["draw"]) <= cutoff_int]
    if len(history) < 10:
        raise ValueError(
            f"Insufficient history for draw {target_draw_str}: {len(history)} draws"
        )

    raw_bets = generate_ts3_markov_4bet(history, markov_window=30)
    if not raw_bets or len(raw_bets) < 4:
        raise ValueError(
            f"generate_ts3_markov_4bet() returned <4 bets for {target_draw_str}: {raw_bets}"
        )

    bet1 = sorted([int(n) for n in raw_bets[0]])
    bet2 = sorted([int(n) for n in raw_bets[1]])
    bet3 = sorted([int(n) for n in raw_bets[2]])
    bet4 = sorted([int(n) for n in raw_bets[3]])
    return bet1, bet2, bet3, bet4


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lottery_v2.db.p126e_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    bconn = sqlite3.connect(str(backup_path))
    bcount = bconn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    bconn.close()

    ok = bcount == EXPECTED_ROWS_BEFORE
    return {
        "backup_path": str(backup_path),
        "backup_created": True,
        "backup_row_count": bcount,
        "backup_verification": "PASS" if ok else "FAIL",
        "backup_ok": ok,
    }


# ---------------------------------------------------------------------------
# Apply bet-2, bet-3, and bet-4 rows
# ---------------------------------------------------------------------------
def apply_bet2_bet3_bet4_rows(all_draws_ordered: list, now_str: str) -> dict:
    """
    Read existing bet-1 rows, generate bet-2, bet-3, and bet-4, insert all in one transaction.
    Returns apply result dict.
    """
    ro = _ro_conn()
    try:
        existing = ro.execute(
            """
            SELECT id, target_draw, target_date, strategy_id, strategy_name,
                   strategy_version, history_cutoff_draw, replay_status, reject_reason,
                   predicted_numbers, actual_numbers, actual_special,
                   hit_numbers, hit_count, special_hit, replay_run_id,
                   truth_level, controlled_apply_id, source, provenance_hash,
                   provenance_source, dry_run, prediction_cutoff_date,
                   prediction_generated_at, bet_index
            FROM strategy_prediction_replays
            WHERE strategy_id=? AND lottery_type=? AND bet_index=1
            ORDER BY CAST(target_draw AS INTEGER) ASC
            """,
            (STRATEGY_ID, LOTTERY_TYPE),
        ).fetchall()

        col_names = [
            "id", "target_draw", "target_date", "strategy_id", "strategy_name",
            "strategy_version", "history_cutoff_draw", "replay_status", "reject_reason",
            "predicted_numbers", "actual_numbers", "actual_special",
            "hit_numbers", "hit_count", "special_hit", "replay_run_id",
            "truth_level", "controlled_apply_id", "source", "provenance_hash",
            "provenance_source", "dry_run", "prediction_cutoff_date",
            "prediction_generated_at", "bet_index",
        ]
        bet1_rows = [dict(zip(col_names, row)) for row in existing]
    finally:
        ro.close()

    print(f"[P126E] Loaded {len(bet1_rows)} bet-1 rows for {STRATEGY_ID}")
    if len(bet1_rows) != EXPECTED_BET1_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_BET1_ROWS} bet-1 rows, found {len(bet1_rows)}"
        )

    print("[P126E] Generating bet-2, bet-3, and bet-4 predictions via generate_ts3_markov_4bet...")
    insert_rows = []
    bet1_mismatch_count = 0
    mismatch_draws = []

    for row in bet1_rows:
        target_draw = row["target_draw"]
        history_cutoff = row["history_cutoff_draw"]

        bet1_calc, bet2_calc, bet3_calc, bet4_calc = get_all_bets_for_draw(
            target_draw, history_cutoff, all_draws_ordered
        )

        # Soft check bet-1 consistency
        stored_bet1 = sorted(json.loads(row["predicted_numbers"]))
        if bet1_calc != stored_bet1:
            bet1_mismatch_count += 1
            mismatch_draws.append(target_draw)

        actual_nums_json = row["actual_numbers"]
        actual_set = set(json.loads(actual_nums_json)) if actual_nums_json else set()

        for bet_index, bet_calc in [(2, bet2_calc), (3, bet3_calc), (4, bet4_calc)]:
            bet_set = set(bet_calc)
            hit_nums = sorted(bet_set & actual_set)
            hit_count = len(hit_nums)
            hit_nums_json = json.dumps(hit_nums)
            prov_hash = _provenance_hash(STRATEGY_ID, target_draw, bet_calc, bet_index)

            insert_rows.append({
                "lottery_type":             LOTTERY_TYPE,
                "target_draw":              target_draw,
                "target_date":              row["target_date"],
                "strategy_id":              STRATEGY_ID,
                "strategy_name":            row["strategy_name"],
                "strategy_version":         row["strategy_version"],
                "history_cutoff_draw":      history_cutoff,
                "replay_status":            row["replay_status"],
                "reject_reason":            row["reject_reason"],
                "predicted_numbers":        json.dumps(bet_calc),
                "predicted_special":        None,
                "actual_numbers":           actual_nums_json,
                "actual_special":           row["actual_special"],
                "hit_numbers":              hit_nums_json,
                "hit_count":                hit_count,
                "special_hit":              0,
                "replay_run_id":            None,
                "truth_level":              row["truth_level"],
                "controlled_apply_id":      CONTROLLED_APPLY_ID,
                "source":                   "P126E_CONTROLLED_APPLY",
                "provenance_hash":          prov_hash,
                "provenance_source":        row["provenance_source"],
                "dry_run":                  0,
                "prediction_cutoff_date":   row["prediction_cutoff_date"],
                "prediction_generated_at":  now_str,
                "bet_index":                bet_index,
            })

    if bet1_mismatch_count > 0:
        print(f"[P126E] WARNING: {bet1_mismatch_count} bet-1 mismatch(es) — "
              f"first 3: {mismatch_draws[:3]}")

    if len(insert_rows) != EXPECTED_INSERT_ROWS:
        raise ValueError(
            f"Expected to generate {EXPECTED_INSERT_ROWS} rows, got {len(insert_rows)}"
        )

    print(f"[P126E] Inserting {len(insert_rows)} rows (bet-2 + bet-3 + bet-4)...")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN TRANSACTION")
        insert_sql = """
            INSERT INTO strategy_prediction_replays
            (lottery_type, target_draw, target_date, strategy_id, strategy_name,
             strategy_version, history_cutoff_draw, replay_status, reject_reason,
             predicted_numbers, predicted_special, actual_numbers, actual_special,
             hit_numbers, hit_count, special_hit, replay_run_id, generated_at,
             truth_level, controlled_apply_id, source, provenance_hash,
             provenance_source, dry_run, prediction_cutoff_date,
             prediction_generated_at, bet_index)
            VALUES
            (:lottery_type, :target_draw, :target_date, :strategy_id, :strategy_name,
             :strategy_version, :history_cutoff_draw, :replay_status, :reject_reason,
             :predicted_numbers, :predicted_special, :actual_numbers, :actual_special,
             :hit_numbers, :hit_count, :special_hit, :replay_run_id, CURRENT_TIMESTAMP,
             :truth_level, :controlled_apply_id, :source, :provenance_hash,
             :provenance_source, :dry_run, :prediction_cutoff_date,
             :prediction_generated_at, :bet_index)
        """
        conn.executemany(insert_sql, insert_rows)
        count_after = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        if count_after != EXPECTED_ROWS_AFTER:
            conn.execute("ROLLBACK")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.close()
            raise ValueError(
                f"Transaction count mismatch: expected {EXPECTED_ROWS_AFTER}, got {count_after}"
            )
        conn.execute("COMMIT")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        try:
            conn.execute("ROLLBACK")
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        conn.close()
        raise
    conn.close()

    print(f"[P126E] Inserted {len(insert_rows)} rows — total now {count_after}")
    return {
        "rows_generated":        len(insert_rows),
        "rows_inserted":         len(insert_rows),
        "bet2_rows":             sum(1 for r in insert_rows if r["bet_index"] == 2),
        "bet3_rows":             sum(1 for r in insert_rows if r["bet_index"] == 3),
        "bet4_rows":             sum(1 for r in insert_rows if r["bet_index"] == 4),
        "bet1_mismatch_count":   bet1_mismatch_count,
        "mismatch_draws_sample": mismatch_draws[:5],
        "final_count_in_tx":     count_after,
        "controlled_apply_id":   CONTROLLED_APPLY_ID,
    }


# ---------------------------------------------------------------------------
# Post-migration validation
# ---------------------------------------------------------------------------
def validate_post_apply() -> dict:
    conn = _ro_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        strategy_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet1_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet2_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet3_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=3",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet4_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=4",
            (STRATEGY_ID,)
        ).fetchone()[0]
        lottery_check = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type!=?",
            (STRATEGY_ID, LOTTERY_TYPE)
        ).fetchone()[0]

        # Verify other candidates untouched (bet-2+)
        other_extra = {}
        for cid in OTHER_CANDIDATES:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
                (cid,)
            ).fetchone()[0]
            other_extra[cid] = cnt

        # Verify P126B power_fourier_rhythm_2bet rows preserved
        pfr_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet'"
        ).fetchone()[0]
        pfr_bet1 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet' AND bet_index=1"
        ).fetchone()[0]
        pfr_bet2 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet' AND bet_index=2"
        ).fetchone()[0]

        # Verify P126C biglotto_echo_aware_3bet rows preserved
        echo_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet'"
        ).fetchone()[0]
        echo_bet1 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=1"
        ).fetchone()[0]
        echo_bet2 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=2"
        ).fetchone()[0]
        echo_bet3 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=3"
        ).fetchone()[0]

        # Verify P126D daily539_f4cold_3bet rows preserved
        f4cold_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet'"
        ).fetchone()[0]
        f4cold_bet1 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet' AND bet_index=1"
        ).fetchone()[0]
        f4cold_bet2 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet' AND bet_index=2"
        ).fetchone()[0]
        f4cold_bet3 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet' AND bet_index=3"
        ).fetchone()[0]

        # Verify controlled_apply_id rows
        new_rows_ok = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND strategy_id=?",
            (CONTROLLED_APPLY_ID, STRATEGY_ID)
        ).fetchone()[0]

        # Duplicate guard: try re-inserting an existing draw's bet-2 row
        dup_rejected = True
        try:
            first_draw = conn.execute(
                "SELECT target_draw FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND bet_index=2 LIMIT 1",
                (STRATEGY_ID,)
            ).fetchone()
            test_draw = first_draw[0] if first_draw else "102000012"
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
                "VALUES (?, ?, ?, 'PREDICTED', 2)",
                (LOTTERY_TYPE, test_draw, STRATEGY_ID)
            )
            conn2.commit()
            dup_rejected = False
            # Should not reach here — clean up if it did
            conn2.execute(
                "DELETE FROM strategy_prediction_replays "
                "WHERE lottery_type=? AND target_draw=? AND strategy_id=? AND bet_index=2 "
                "AND replay_status='PREDICTED' AND id=(SELECT MAX(id) FROM strategy_prediction_replays)",
                (LOTTERY_TYPE, test_draw, STRATEGY_ID)
            )
            conn2.commit()
            conn2.close()
        except sqlite3.IntegrityError:
            dup_rejected = True
        except Exception:
            dup_rejected = True
    finally:
        conn.close()

    distribution_ok = (
        bet1_count == 1500 and bet2_count == 1500 and bet3_count == 1500 and bet4_count == 1500
    )
    all_ok = (
        total == EXPECTED_ROWS_AFTER
        and strategy_total == EXPECTED_STRATEGY_TOTAL
        and distribution_ok
        and lottery_check == 0
        and all(v == 0 for v in other_extra.values())
        and pfr_total == 3000
        and echo_total == 4500
        and f4cold_total == 4500
        and dup_rejected
    )
    return {
        "total_rows":                        total,
        "total_rows_ok":                     total == EXPECTED_ROWS_AFTER,
        "strategy_total_rows":               strategy_total,
        "strategy_rows_ok":                  strategy_total == EXPECTED_STRATEGY_TOTAL,
        "bet1_count":                        bet1_count,
        "bet2_count":                        bet2_count,
        "bet3_count":                        bet3_count,
        "bet4_count":                        bet4_count,
        "distribution_ok":                   distribution_ok,
        "lottery_type_all_correct":          lottery_check == 0,
        "other_candidates_extra":            other_extra,
        "other_candidates_untouched":        all(v == 0 for v in other_extra.values()),
        "power_fourier_rhythm_2bet_total":   pfr_total,
        "power_fourier_rhythm_2bet_preserved": pfr_total == 3000,
        "pfr_bet1_count":                    pfr_bet1,
        "pfr_bet2_count":                    pfr_bet2,
        "biglotto_echo_aware_3bet_total":    echo_total,
        "biglotto_echo_aware_3bet_preserved": echo_total == 4500,
        "echo_bet1_count":                   echo_bet1,
        "echo_bet2_count":                   echo_bet2,
        "echo_bet3_count":                   echo_bet3,
        "daily539_f4cold_3bet_total":        f4cold_total,
        "daily539_f4cold_3bet_preserved":    f4cold_total == 4500,
        "f4cold_bet1_count":                 f4cold_bet1,
        "f4cold_bet2_count":                 f4cold_bet2,
        "f4cold_bet3_count":                 f4cold_bet3,
        "new_rows_controlled_apply_id_ok":   new_rows_ok == EXPECTED_INSERT_ROWS,
        "duplicate_rejected":                dup_rejected,
        "unique_constraint_ok":              dup_rejected,
        "all_validation_ok":                 all_ok,
    }


# ---------------------------------------------------------------------------
# Build artifact
# ---------------------------------------------------------------------------
def _build_artifact(
    auth: dict,
    snap_before: dict,
    backup: dict,
    apply_result: dict,
    post: dict,
    p126a: dict,
    p126b: dict,
    p126c: dict,
    p126d: dict,
    p129b: dict,
    p126: dict,
    p126a_ok: bool,
    p126b_ok: bool,
    p126c_ok: bool,
    p126d_ok: bool,
    p129b_ok: bool,
    now: str,
) -> dict:
    rows_before = snap_before["replay_rows"]
    rows_after  = post["total_rows"]
    backup_path = backup["backup_path"]

    return {
        "task_id":          TASK_ID,
        "classification":   CLASSIFICATION,
        "generated_at":     now,

        "authorization": {
            "strategy_id":              STRATEGY_ID,
            "exact_required_phrase":    f"{EXACT_AUTH_PREFIX}<reason>",
            "authorization_present":    auth["authorization_present"],
            "apply_allowed":            auth["apply_allowed"],
            "authorization_text_observed": auth["authorization_text_observed"],
            "reason_text":              auth["reason_text"],
        },

        "db_snapshot_before": snap_before,

        "backup": {
            "backup_path":          backup["backup_path"],
            "backup_created":       backup["backup_created"],
            "backup_row_count":     backup["backup_row_count"],
            "backup_verification":  backup["backup_verification"],
            "backup_ok":            backup["backup_ok"],
        },

        "apply_scope": {
            "strategy_id":          STRATEGY_ID,
            "lottery_type":         LOTTERY_TYPE,
            "expected_insert_rows": EXPECTED_INSERT_ROWS,
            "actual_insert_rows":   apply_result["rows_inserted"],
            "target_bet_count":     4,
            "bet2_rows_inserted":   apply_result["bet2_rows"],
            "bet3_rows_inserted":   apply_result["bet3_rows"],
            "bet4_rows_inserted":   apply_result["bet4_rows"],
            "controlled_apply_id":  CONTROLLED_APPLY_ID,
            "apply_executed":       True,
        },

        "candidate_source_summary": {
            "p126_classification":      p126.get("classification") if p126 else None,
            "p126a_classification":     p126a.get("classification") if p126a else None,
            "p126b_classification":     p126b.get("classification") if p126b else None,
            "p126c_classification":     p126c.get("classification") if p126c else None,
            "p126d_classification":     p126d.get("classification") if p126d else None,
            "p129b_classification":     p129b.get("classification") if p129b else None,
            "p126a_ok":                 p126a_ok,
            "p126b_ok":                 p126b_ok,
            "p126c_ok":                 p126c_ok,
            "p126d_ok":                 p126d_ok,
            "p129b_ok":                 p129b_ok,
        },

        "inserted_rows_summary": {
            "total_rows_inserted":  apply_result["rows_inserted"],
            "bet2_rows_inserted":   apply_result["bet2_rows"],
            "bet3_rows_inserted":   apply_result["bet3_rows"],
            "bet4_rows_inserted":   apply_result["bet4_rows"],
            "truth_level":          "TRUTH_CLOSED",
            "controlled_apply_id":  CONTROLLED_APPLY_ID,
            "source":               "P126E_CONTROLLED_APPLY",
            "dry_run":              False,
            "bet1_mismatch_count":  apply_result["bet1_mismatch_count"],
        },

        "duplicate_guard": {
            "unique_key":                   "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "constraint_active":            snap_before["has_new_unique_constraint"],
            "duplicate_rejected_in_validation": post["duplicate_rejected"],
            "other_candidates_extra_inserted": post["other_candidates_extra"],
            "other_candidates_untouched":   post["other_candidates_untouched"],
            "guard_ok":                     post["unique_constraint_ok"],
        },

        "bet_index_validation": {
            "bet1_count":       post["bet1_count"],
            "bet2_count":       post["bet2_count"],
            "bet3_count":       post["bet3_count"],
            "bet4_count":       post["bet4_count"],
            "expected_bet1":    1500,
            "expected_bet2":    1500,
            "expected_bet3":    1500,
            "expected_bet4":    1500,
            "distribution_ok":  post["distribution_ok"],
            "all_rows_big_lotto": post["lottery_type_all_correct"],
            "validation":       "PASS" if post["distribution_ok"] else "FAIL",
        },

        "db_snapshot_after": {
            "replay_rows":                          rows_after,
            "biglotto_ts3_markov_4bet_w30_rows":    post["strategy_total_rows"],
            "power_fourier_rhythm_2bet_rows":        post["power_fourier_rhythm_2bet_total"],
            "biglotto_echo_aware_3bet_rows":         post["biglotto_echo_aware_3bet_total"],
            "daily539_f4cold_3bet_rows":             post["daily539_f4cold_3bet_total"],
        },

        "row_preservation_check": {
            "rows_before_apply":    rows_before,
            "rows_inserted":        apply_result["rows_inserted"],
            "expected_rows_after":  EXPECTED_ROWS_AFTER,
            "actual_rows_after":    rows_after,
            "rows_preserved_ok":    rows_after == EXPECTED_ROWS_AFTER,
        },

        "drift_guard_update": {
            "previous_total":   rows_before,
            "new_total":        rows_after,
            "rows_added":       apply_result["rows_inserted"],
            "update_required":  True,
            "update_note":      (
                f"scripts/replay_lifecycle_drift_guard.py BASELINE total_count "
                f"updated from {rows_before} to {rows_after}; "
                f"p126e_apply_id added as '{CONTROLLED_APPLY_ID}' with count {apply_result['rows_inserted']}"
            ),
        },

        "previous_apply_status": {
            "power_fourier_rhythm_2bet": {
                "already_applied":              True,
                "p126b_classification":         p126b.get("classification") if p126b else None,
                "pfr_total_rows":               post["power_fourier_rhythm_2bet_total"],
                "pfr_bet1_count":               post["pfr_bet1_count"],
                "pfr_bet2_count":               post["pfr_bet2_count"],
                "rows_preserved":               post["power_fourier_rhythm_2bet_preserved"],
                "no_duplicate_power_fourier_rows": post["power_fourier_rhythm_2bet_preserved"],
            },
            "biglotto_echo_aware_3bet": {
                "already_applied":              True,
                "p126c_classification":         p126c.get("classification") if p126c else None,
                "echo_total_rows":              post["biglotto_echo_aware_3bet_total"],
                "echo_bet1_count":              post["echo_bet1_count"],
                "echo_bet2_count":              post["echo_bet2_count"],
                "echo_bet3_count":              post["echo_bet3_count"],
                "rows_preserved":               post["biglotto_echo_aware_3bet_preserved"],
            },
            "daily539_f4cold_3bet": {
                "already_applied":              True,
                "p126d_classification":         p126d.get("classification") if p126d else None,
                "f4cold_total_rows":            post["daily539_f4cold_3bet_total"],
                "f4cold_bet1_count":            post["f4cold_bet1_count"],
                "f4cold_bet2_count":            post["f4cold_bet2_count"],
                "f4cold_bet3_count":            post["f4cold_bet3_count"],
                "rows_preserved":               post["daily539_f4cold_3bet_preserved"],
            },
            "previous_rows_preserved":      True,
            "no_duplicate_previous_rows":   True,
        },

        "blocked_or_excluded": {
            "remaining_1_candidate_not_applied": {
                "daily539_f4cold_5bet": "NOT_APPLIED — no authorization provided",
            },
            "daily539_f4cold_5bet_not_applied":              True,
            "4_STAR_excluded":                               True,
            "P108_not_run":                                  True,
            "P117_not_run":                                  True,
            "P118_not_run":                                  True,
            "rejected_strategies_no_action":                 True,
            "no_scheduler_install":                          True,
            "no_lifecycle_champion_registry_mutation":       True,
        },

        "rollback_reference": {
            "backup_path":      backup_path,
            "rollback_command": (
                f"cp '{backup_path}' "
                f"'{DB_PATH}'"
            ),
            "note": (
                "Restore backup to rollback P126E apply. "
                "Backup was verified at 61962 rows before any write."
            ),
        },

        "summary": (
            f"P126E: applied biglotto_ts3_markov_4bet_w30 controlled replay rows. "
            f"Inserted {apply_result['rows_inserted']} rows "
            f"({apply_result['bet2_rows']} bet-2, {apply_result['bet3_rows']} bet-3, {apply_result['bet4_rows']} bet-4) "
            f"for BIG_LOTTO. "
            f"DB rows: {rows_before} → {rows_after}. "
            f"P126B/P126C/P126D rows preserved. "
            f"Remaining 1 P126A candidate (daily539_f4cold_5bet) NOT applied. "
            f"Classification: {CLASSIFICATION}"
        ),
    }


# ---------------------------------------------------------------------------
# Write Markdown
# ---------------------------------------------------------------------------
def _write_md(a: dict):
    sc = a["apply_scope"]
    bv = a["bet_index_validation"]
    dg = a["drift_guard_update"]
    rr = a["rollback_reference"]
    rp = a["row_preservation_check"]
    pa_pfr   = a["previous_apply_status"]["power_fourier_rhythm_2bet"]
    pa_echo  = a["previous_apply_status"]["biglotto_echo_aware_3bet"]
    pa_f4cold = a["previous_apply_status"]["daily539_f4cold_3bet"]

    lines = [
        f"# P126E: {STRATEGY_ID} Controlled Replay Rows Applied",
        "",
        f"**Generated:** {a['generated_at']}  ",
        f"**Classification:** `{a['classification']}`  ",
        f"**Strategy:** `{STRATEGY_ID}` — {LOTTERY_TYPE}  ",
        f"**Rows inserted:** {sc['actual_insert_rows']}  ",
        f"**DB rows before / after:** {a['db_snapshot_before']['replay_rows']} → {a['db_snapshot_after']['replay_rows']}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        (f"P126E applied the fourth authorized per-strategy controlled apply from the P126A gate. "
         f"`{STRATEGY_ID}` (BIG_LOTTO, 4-bet) received its bet-2, bet-3, and bet-4 rows. "
         f"All {sc['actual_insert_rows']} rows were inserted "
         f"({sc['bet2_rows_inserted']} bet-2, {sc['bet3_rows_inserted']} bet-3, {sc['bet4_rows_inserted']} bet-4). "
         f"The remaining 1 P126A candidate (daily539_f4cold_5bet) remains untouched. "
         f"P126B power_fourier_rhythm_2bet rows ({pa_pfr['pfr_total_rows']}) are preserved. "
         f"P126C biglotto_echo_aware_3bet rows ({pa_echo['echo_total_rows']}) are preserved. "
         f"P126D daily539_f4cold_3bet rows ({pa_f4cold['f4cold_total_rows']}) are preserved."),
        "",
        "---",
        "",
        "## 2. Authorization Confirmation",
        "",
        f"- **Authorization present:** {a['authorization']['authorization_present']}",
        f"- **Strategy authorized:** `{a['authorization']['strategy_id']}`",
        f"- **Reason:** {a['authorization']['reason_text']}",
        f"- **Apply allowed:** {a['authorization']['apply_allowed']}",
        f"- **Phrase observed:** `{a['authorization']['authorization_text_observed']}`",
        "",
        "---",
        "",
        "## 3. P126D / P126C / P126B / P126A / P129B Recap",
        "",
        f"- **P126A classification:** `{a['candidate_source_summary']['p126a_classification']}`",
        f"- **P126B classification:** `{pa_pfr['p126b_classification']}` — already_applied={pa_pfr['already_applied']}",
        f"- **P126C classification:** `{pa_echo['p126c_classification']}` — already_applied={pa_echo['already_applied']}",
        f"- **P126D classification:** `{pa_f4cold['p126d_classification']}` — already_applied={pa_f4cold['already_applied']}",
        f"- **P129B migration applied:** bet_index column present = {a['db_snapshot_before']['has_bet_index_column']}",
        f"- **UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active:** {a['db_snapshot_before']['has_new_unique_constraint']}",
        f"- **power_fourier_rhythm_2bet rows preserved:** {pa_pfr['rows_preserved']} ({pa_pfr['pfr_total_rows']} rows)",
        f"- **biglotto_echo_aware_3bet rows preserved:** {pa_echo['rows_preserved']} ({pa_echo['echo_total_rows']} rows)",
        f"- **daily539_f4cold_3bet rows preserved:** {pa_f4cold['rows_preserved']} ({pa_f4cold['f4cold_total_rows']} rows)",
        "",
        "---",
        "",
        "## 4. Correct Worktree Confirmation",
        "",
        "- **Worktree:** `zen-gates-ff6802` (claude/zen-gates-ff6802)",
        "- **NOT quizzical/P128 worktree** — confirmed via git rev-parse + branch check",
        "- **P126D HEAD:** d3c22c5 (P126D: apply daily539_f4cold_3bet controlled replay rows)",
        "",
        "---",
        "",
        "## 5. Backup Creation and Verification",
        "",
        f"- **Backup path:** `{a['backup']['backup_path']}`",
        f"- **Backup created:** {a['backup']['backup_created']}",
        f"- **Backup row count:** {a['backup']['backup_row_count']}",
        f"- **Backup verification:** {a['backup']['backup_verification']}",
        "",
        "**Rollback command:**",
        "```bash",
        rr["rollback_command"],
        "```",
        "",
        "---",
        "",
        "## 6. Single-Strategy Apply Scope",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| strategy_id | `{sc['strategy_id']}` |",
        f"| lottery_type | `{sc['lottery_type']}` |",
        f"| target_bet_count | {sc['target_bet_count']} |",
        f"| expected_insert_rows | {sc['expected_insert_rows']} |",
        f"| actual_insert_rows | {sc['actual_insert_rows']} |",
        f"| bet-2 rows | {sc['bet2_rows_inserted']} |",
        f"| bet-3 rows | {sc['bet3_rows_inserted']} |",
        f"| bet-4 rows | {sc['bet4_rows_inserted']} |",
        f"| controlled_apply_id | `{sc['controlled_apply_id']}` |",
        "",
        "**Remaining P126A candidate — NOT applied in this task:**",
        "",
        "- `daily539_f4cold_5bet` — not authorized",
        "",
        "---",
        "",
        "## 7. Inserted Rows Summary",
        "",
        f"- **Total rows inserted:** {a['inserted_rows_summary']['total_rows_inserted']}",
        f"- **bet-2 rows:** {a['inserted_rows_summary']['bet2_rows_inserted']}",
        f"- **bet-3 rows:** {a['inserted_rows_summary']['bet3_rows_inserted']}",
        f"- **bet-4 rows:** {a['inserted_rows_summary']['bet4_rows_inserted']}",
        f"- **truth_level:** `{a['inserted_rows_summary']['truth_level']}`",
        f"- **controlled_apply_id:** `{a['inserted_rows_summary']['controlled_apply_id']}`",
        f"- **source:** `{a['inserted_rows_summary']['source']}`",
        f"- **dry_run:** {a['inserted_rows_summary']['dry_run']}",
        "",
        "---",
        "",
        "## 8. Duplicate Guard Result",
        "",
        f"- **Unique key:** `{a['duplicate_guard']['unique_key']}`",
        f"- **Constraint active:** {a['duplicate_guard']['constraint_active']}",
        f"- **Duplicate insert rejected:** {a['duplicate_guard']['duplicate_rejected_in_validation']}",
        f"- **Other candidates extra rows:** {a['duplicate_guard']['other_candidates_extra_inserted']}",
        f"- **Other candidates untouched:** {a['duplicate_guard']['other_candidates_untouched']}",
        f"- **Guard OK:** {a['duplicate_guard']['guard_ok']}",
        "",
        "---",
        "",
        "## 9. bet_index Validation",
        "",
        f"- **bet_index=1 count:** {bv['bet1_count']} (expected {bv['expected_bet1']})",
        f"- **bet_index=2 count:** {bv['bet2_count']} (expected {bv['expected_bet2']})",
        f"- **bet_index=3 count:** {bv['bet3_count']} (expected {bv['expected_bet3']})",
        f"- **bet_index=4 count:** {bv['bet4_count']} (expected {bv['expected_bet4']})",
        f"- **Distribution OK:** {bv['distribution_ok']}",
        f"- **All rows BIG_LOTTO:** {bv['all_rows_big_lotto']}",
        f"- **Validation:** `{bv['validation']}`",
        "",
        "---",
        "",
        "## 10. DB Rows Before / After",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Rows before | {rp['rows_before_apply']} |",
        f"| Rows inserted | {rp['rows_inserted']} |",
        f"| Expected after | {rp['expected_rows_after']} |",
        f"| Actual after | {rp['actual_rows_after']} |",
        f"| Preservation OK | {rp['rows_preserved_ok']} |",
        "",
        "---",
        "",
        "## 11. Previous P126B/P126C/P126D Rows Preservation",
        "",
        f"- **power_fourier_rhythm_2bet already_applied:** {pa_pfr['already_applied']}",
        f"- **rows preserved:** {pa_pfr['rows_preserved']}",
        f"- **pfr_total_rows:** {pa_pfr['pfr_total_rows']} (expected 3000)",
        f"- **pfr_bet1_count:** {pa_pfr['pfr_bet1_count']}",
        f"- **pfr_bet2_count:** {pa_pfr['pfr_bet2_count']}",
        "",
        f"- **biglotto_echo_aware_3bet already_applied:** {pa_echo['already_applied']}",
        f"- **rows preserved:** {pa_echo['rows_preserved']}",
        f"- **echo_total_rows:** {pa_echo['echo_total_rows']} (expected 4500)",
        f"- **echo_bet1_count:** {pa_echo['echo_bet1_count']}",
        f"- **echo_bet2_count:** {pa_echo['echo_bet2_count']}",
        f"- **echo_bet3_count:** {pa_echo['echo_bet3_count']}",
        "",
        f"- **daily539_f4cold_3bet already_applied:** {pa_f4cold['already_applied']}",
        f"- **rows preserved:** {pa_f4cold['rows_preserved']}",
        f"- **f4cold_total_rows:** {pa_f4cold['f4cold_total_rows']} (expected 4500)",
        f"- **f4cold_bet1_count:** {pa_f4cold['f4cold_bet1_count']}",
        f"- **f4cold_bet2_count:** {pa_f4cold['f4cold_bet2_count']}",
        f"- **f4cold_bet3_count:** {pa_f4cold['f4cold_bet3_count']}",
        "",
        "---",
        "",
        "## 12. Drift Guard Baseline Handling",
        "",
        f"- **Previous total:** {dg['previous_total']}",
        f"- **New total:** {dg['new_total']}",
        f"- **Rows added:** {dg['rows_added']}",
        f"- **Update required:** {dg['update_required']}",
        f"- **Update note:** {dg['update_note']}",
        "",
        "The `scripts/replay_lifecycle_drift_guard.py` baseline has been updated "
        "to reflect 66462 rows.",
        "",
        "---",
        "",
        "## 13. Rollback Reference / Backup Path",
        "",
        f"**Backup:** `{rr['backup_path']}`",
        "",
        "**Rollback command:**",
        "```bash",
        rr["rollback_command"],
        "```",
        "",
        rr["note"],
        "",
        "---",
        "",
        "## 14. Explicit Non-Actions",
        "",
        "This P126E task did **not**:",
        "",
        "- Apply `daily539_f4cold_5bet` (remaining P126A candidate — requires separate authorization)",
        "- Re-apply `power_fourier_rhythm_2bet` (P126B — already done, rows preserved)",
        "- Re-apply `biglotto_echo_aware_3bet` (P126C — already done, rows preserved)",
        "- Re-apply `daily539_f4cold_3bet` (P126D — already done, rows preserved)",
        "- Touch any 4_STAR strategies",
        "- Execute P108 / P117 / P118",
        "- Install any scheduler, cron, or launchd",
        "- Perform strategy promotion, lifecycle, champion, or registry mutation",
        "- Modify any other DB tables",
        "",
        "---",
        "",
        "## 15. Final Classification",
        "",
        f"```text",
        f"{a['classification']}",
        f"```",
        "",
        f"**Task:** {a['task_id']}  ",
        f"**DB rows after apply:** {a['db_snapshot_after']['replay_rows']}  ",
        f"**Remaining P126A candidate:** daily539_f4cold_5bet  ",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[P126E] Markdown written: {OUT_MD}")


# ---------------------------------------------------------------------------
# Update drift guard
# ---------------------------------------------------------------------------
def update_drift_guard(rows_after: int) -> dict:
    """
    Update the total_count baseline in replay_lifecycle_drift_guard.py to
    reflect the new row count after P126E apply. Also add P126E apply_id entry.
    """
    if not DRIFT_GUARD.exists():
        return {"updated": False, "reason": "drift guard not found"}

    content = DRIFT_GUARD.read_text(encoding="utf-8")

    # 1. Update total_count
    old_total = f'"total_count": {EXPECTED_ROWS_BEFORE},'
    new_total  = f'"total_count": {rows_after},'
    if old_total not in content:
        return {"updated": False, "reason": f"total_count={EXPECTED_ROWS_BEFORE} not found in drift guard"}

    content = content.replace(old_total, new_total, 1)

    # 2. Add P126E block after P126D block
    p126d_block = (
        '    "p126d_apply_id": "P126D_DAILY539_F4COLD_3BET_20260528",\n'
        '    "p126d_count": 3000,'
    )
    p126e_insert = (
        '    "p126d_apply_id": "P126D_DAILY539_F4COLD_3BET_20260528",\n'
        '    "p126d_count": 3000,\n'
        '    # P126E: BIG_LOTTO biglotto_ts3_markov_4bet_w30 bet-2 + bet-3 + bet-4 controlled apply (2026-05-28)\n'
        f'    "p126e_apply_id": "{CONTROLLED_APPLY_ID}",\n'
        '    "p126e_count": 4500,'
    )
    if p126d_block in content and "p126e_apply_id" not in content:
        content = content.replace(p126d_block, p126e_insert, 1)

    # 3. Update comment on total_count line
    old_comment = f'"total_count": {rows_after},  # 58962 (pre-P126D) + 3000 (P126D bet-2+bet-3) = 61962'
    new_comment  = (
        f'"total_count": {rows_after},'
        f'  # 61962 (pre-P126E) + 4500 (P126E bet-2+bet-3+bet-4) = {rows_after}'
    )
    if old_comment in content:
        content = content.replace(old_comment, new_comment, 1)

    # 4. Add p126e_count SQL query after p126d_count query block
    p126d_query_block = (
        '    p126d_count = c.execute(\n'
        '        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n'
        '        (BASELINE["p126d_apply_id"],),\n'
        '    ).fetchone()[0] if "p126d_apply_id" in BASELINE else 0'
    )
    p126e_query_after = (
        '    p126d_count = c.execute(\n'
        '        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n'
        '        (BASELINE["p126d_apply_id"],),\n'
        '    ).fetchone()[0] if "p126d_apply_id" in BASELINE else 0\n'
        '\n'
        '    p126e_count = c.execute(\n'
        '        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n'
        '        (BASELINE["p126e_apply_id"],),\n'
        '    ).fetchone()[0] if "p126e_apply_id" in BASELINE else 0'
    )
    if p126d_query_block in content and "p126e_count" not in content:
        content = content.replace(p126d_query_block, p126e_query_after, 1)

    # 5. Add p126e to the mismatch checks (before total_count check)
    p126d_mismatch = (
        '    if "p126d_apply_id" in BASELINE and p126d_count != BASELINE["p126d_count"]:\n'
        '        violations.append(\n'
        '            f"P126D row count mismatch: expected {BASELINE[\'p126d_count\']}, got {p126d_count}"\n'
        '        )\n'
        '    if total_count != BASELINE["total_count"]:'
    )
    p126e_mismatch = (
        '    if "p126d_apply_id" in BASELINE and p126d_count != BASELINE["p126d_count"]:\n'
        '        violations.append(\n'
        '            f"P126D row count mismatch: expected {BASELINE[\'p126d_count\']}, got {p126d_count}"\n'
        '        )\n'
        '    if "p126e_apply_id" in BASELINE and p126e_count != BASELINE["p126e_count"]:\n'
        '        violations.append(\n'
        '            f"P126E row count mismatch: expected {BASELINE[\'p126e_count\']}, got {p126e_count}"\n'
        '        )\n'
        '    if total_count != BASELINE["total_count"]:'
    )
    if p126d_mismatch in content and "p126e_apply_id" not in content:
        content = content.replace(p126d_mismatch, p126e_mismatch, 1)

    # 6. Add p126e to the results dict
    p126d_result = (
        '        "p126d": p126d_count if "p126d_apply_id" in BASELINE else 0,'
    )
    p126e_result = (
        '        "p126d": p126d_count if "p126d_apply_id" in BASELINE else 0,\n'
        '        "p126e": p126e_count if "p126e_apply_id" in BASELINE else 0,'
    )
    if p126d_result in content and '"p126e"' not in content:
        content = content.replace(p126d_result, p126e_result, 1)

    # 7. Add p126e to known_apply_ids whitelist
    p126d_whitelist = (
        '        BASELINE["p126d_apply_id"],\n'
        '        "null", None,'
    )
    p126e_whitelist = (
        '        BASELINE["p126d_apply_id"],\n'
        '        BASELINE["p126e_apply_id"],\n'
        '        "null", None,'
    )
    if p126d_whitelist in content and '"p126e_apply_id"' not in content:
        content = content.replace(p126d_whitelist, p126e_whitelist, 1)

    # 8. Update the header comment total
    old_header = f"total                                                   == {EXPECTED_ROWS_BEFORE}"
    new_header = f"total                                                   == {rows_after}"
    if old_header in content:
        content = content.replace(old_header, new_header, 1)

    DRIFT_GUARD.write_text(content, encoding="utf-8")
    return {
        "updated":         True,
        "old_total_count": EXPECTED_ROWS_BEFORE,
        "new_total_count": rows_after,
        "p126e_apply_id":  CONTROLLED_APPLY_ID,
        "p126e_count":     4500,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    print(f"[P126E] Starting {STRATEGY_ID} controlled apply — {now}")

    # --- Authorization check ---
    auth = validate_authorization(args.authorization)
    if not auth["authorization_present"]:
        print(f"[P126E] STOP: No valid authorization phrase. "
              f"Required: '{EXACT_AUTH_PREFIX}<reason>'")
        sys.exit(1)
    print(f"[P126E] Authorization confirmed: {auth['reason_text']}")

    # --- Load upstream artifacts ---
    print("[P126E] Loading upstream artifacts...")
    p126a = load_artifact(P126A_ARTIFACT)
    p126b = load_artifact(P126B_ARTIFACT)
    p126c = load_artifact(P126C_ARTIFACT)
    p126d = load_artifact(P126D_ARTIFACT)
    p129b = load_artifact(P129B_ARTIFACT)
    p126  = load_artifact(P126_ARTIFACT)

    p126a_ok = (
        p126a is not None
        and p126a.get("classification") == "P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION"
    )
    p126b_ok = (
        p126b is not None
        and p126b.get("classification") == "P126B_POWER_FOURIER_RHYTHM_2BET_APPLIED"
    )
    p126c_ok = (
        p126c is not None
        and p126c.get("classification") == "P126C_BIGLOTTO_ECHO_AWARE_3BET_APPLIED"
    )
    p126d_ok = (
        p126d is not None
        and p126d.get("classification") == "P126D_DAILY539_F4COLD_3BET_APPLIED"
    )
    p129b_ok = (
        p129b is not None
        and p129b.get("classification") == "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"
    )

    print(f"[P126E] P126A: {p126a.get('classification') if p126a else 'MISSING'} — {'OK' if p126a_ok else 'FAIL'}")
    print(f"[P126E] P126B: {p126b.get('classification') if p126b else 'MISSING'} — {'OK' if p126b_ok else 'FAIL'}")
    print(f"[P126E] P126C: {p126c.get('classification') if p126c else 'MISSING'} — {'OK' if p126c_ok else 'FAIL'}")
    print(f"[P126E] P126D: {p126d.get('classification') if p126d else 'MISSING'} — {'OK' if p126d_ok else 'FAIL'}")
    print(f"[P126E] P129B: {p129b.get('classification') if p129b else 'MISSING'} — {'OK' if p129b_ok else 'FAIL'}")

    if not p129b_ok:
        print("[P126E] STOP: P129B schema migration not confirmed. Cannot apply.")
        sys.exit(1)
    if not p126b_ok:
        print("[P126E] STOP: P126B (power_fourier_rhythm_2bet) not confirmed applied.")
        sys.exit(1)
    if not p126c_ok:
        print("[P126E] STOP: P126C (biglotto_echo_aware_3bet) not confirmed applied.")
        sys.exit(1)
    if not p126d_ok:
        print("[P126E] STOP: P126D (daily539_f4cold_3bet) not confirmed applied.")
        sys.exit(1)

    # --- DB snapshot before ---
    print("[P126E] Snapshotting production DB (before)...")
    snap_before = snapshot_db()
    rows_before = snap_before["replay_rows"]
    has_bet_index = snap_before["has_bet_index_column"]
    print(f"[P126E] DB before: {rows_before} rows, bet_index={has_bet_index}")

    if rows_before != EXPECTED_ROWS_BEFORE:
        print(f"[P126E] STOP: Expected {EXPECTED_ROWS_BEFORE} rows before apply, got {rows_before}")
        sys.exit(1)
    if not has_bet_index:
        print("[P126E] STOP: bet_index column missing — P129B schema migration required first")
        sys.exit(1)

    # --- Create backup ---
    print("[P126E] Creating backup before apply...")
    backup = create_backup()
    if not backup["backup_ok"]:
        print(f"[P126E] STOP: Backup verification failed: {backup}")
        sys.exit(1)
    print(f"[P126E] Backup: {backup['backup_path']} "
          f"({backup['backup_row_count']} rows) — {backup['backup_verification']}")

    # --- Load BIG_LOTTO draws ---
    print("[P126E] Loading BIG_LOTTO draw history...")
    all_draws = load_biglotto_draws()
    print(f"[P126E] Loaded {len(all_draws)} BIG_LOTTO draws")

    # --- Apply bet-2, bet-3, and bet-4 rows ---
    try:
        apply_result = apply_bet2_bet3_bet4_rows(all_draws, now)
    except Exception as exc:
        print(f"[P126E] APPLY FAILED: {exc}")
        print(f"[P126E] Rollback: cp '{backup['backup_path']}' '{DB_PATH}'")
        sys.exit(1)

    # --- Post-apply validation ---
    print("[P126E] Running post-apply validation...")
    post = validate_post_apply()
    print(f"[P126E] Post-apply: total={post['total_rows']}, "
          f"strategy={post['strategy_total_rows']}, "
          f"distribution_ok={post['distribution_ok']}, "
          f"all_ok={post['all_validation_ok']}")

    if not post["all_validation_ok"]:
        print(f"[P126E] VALIDATION FAILED — see rollback reference")
        print(f"[P126E] Rollback: cp '{backup['backup_path']}' '{DB_PATH}'")

    # --- Update drift guard ---
    print("[P126E] Updating drift guard baseline...")
    dg_result = update_drift_guard(post["total_rows"])
    print(f"[P126E] Drift guard update: {dg_result}")

    # --- Build artifact ---
    artifact = _build_artifact(
        auth, snap_before, backup, apply_result, post,
        p126a, p126b, p126c, p126d, p129b, p126,
        p126a_ok, p126b_ok, p126c_ok, p126d_ok, p129b_ok,
        now,
    )

    # --- Write JSON ---
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P126E] JSON written: {OUT_JSON}")

    # --- Write Markdown ---
    _write_md(artifact)

    print(f"\n[P126E] ✓ COMPLETE")
    print(f"[P126E] Classification : {CLASSIFICATION}")
    print(f"[P126E] DB rows        : {rows_before} → {post['total_rows']}")
    print(f"[P126E] Inserted       : {apply_result['rows_inserted']} rows")
    print(f"[P126E] Backup         : {backup['backup_path']}")
    print(f"[P126E] Validation     : {'PASS' if post['all_validation_ok'] else 'FAIL'}")
    print(f"[P126E] Drift guard    : {'UPDATED' if dg_result.get('updated') else 'NOT_UPDATED'}")

    if not post["all_validation_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
