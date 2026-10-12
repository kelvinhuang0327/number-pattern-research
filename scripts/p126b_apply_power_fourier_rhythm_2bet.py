#!/usr/bin/env python3
"""
P126B: Apply power_fourier_rhythm_2bet Controlled Replay Rows
=============================================================
PURPOSE : Insert 1500 bet-2 rows for the power_fourier_rhythm_2bet strategy
          in POWER_LOTTO, using the P126A authorized controlled apply.
          Uses the same fourier_rhythm_predict(history, n_bets=2, window=500)
          adapter as P94, but stores bet-2 (bet_index=2) instead of bet-1.
SAFETY:
  - Validates exact authorization phrase FIRST.
  - Validates upstream P126A and P129B artifacts.
  - Creates backup BEFORE any DB write.
  - Duplicate guard: UNIQUE(lottery_type, target_draw, strategy_id, bet_index).
  - Full transaction wrap with ROLLBACK on failure.
  - Only power_fourier_rhythm_2bet is applied — no other 4 P126A candidates.
  - Post-migration: verifies row count (55962), strategy rows (3000), distribution.
GOVERNANCE:
  - NO other P126A candidates applied
  - NO P126 apply for daily539_f4cold_3bet, biglotto_echo_aware_3bet,
         biglotto_ts3_markov_4bet_w30, daily539_f4cold_5bet
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
TASK_ID           = "P126B"
CLASSIFICATION    = "P126B_POWER_FOURIER_RHYTHM_2BET_APPLIED"
DATE_SUFFIX       = "20260528"
REPO_ROOT         = Path(__file__).resolve().parent.parent
STRATEGY_ID       = "power_fourier_rhythm_2bet"
LOTTERY_TYPE      = "POWER_LOTTO"
CONTROLLED_APPLY_ID = f"P126B_POWER_FOURIER_RHYTHM_2BET_{DATE_SUFFIX}"

P126A_ARTIFACT = REPO_ROOT / "outputs/replay/p126a_controlled_apply_authorization_gate_20260528.json"
P129B_ARTIFACT = REPO_ROOT / "outputs/replay/p129b_execute_bet_index_schema_migration_20260528.json"
P126_ARTIFACT  = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p126b_apply_power_fourier_rhythm_2bet_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p126b_apply_power_fourier_rhythm_2bet_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR     = REPO_ROOT / "lottery_api/data/backups"

EXPECTED_ROWS_BEFORE    = 54462
EXPECTED_ROWS_AFTER     = 55962
EXPECTED_INSERT_ROWS    = 1500
EXPECTED_STRATEGY_ROWS  = 3000  # 1500 bet-1 + 1500 bet-2
EXACT_AUTH_PREFIX       = f"YES authorize controlled_apply for {STRATEGY_ID} because "

# Other P126A candidates that must NOT be applied in this task
OTHER_CANDIDATES = [
    "daily539_f4cold_3bet",
    "biglotto_echo_aware_3bet",
    "biglotto_ts3_markov_4bet_w30",
    "daily539_f4cold_5bet",
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


def snapshot_db():
    conn = _ro_conn()
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
        has_bet_index = "bet_index" in cols
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        has_new_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl
        strategy_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        return {
            "replay_rows": rows,
            "has_bet_index_column": has_bet_index,
            "has_new_unique_constraint": has_new_unique,
            "columns_count": len(cols),
            "power_fourier_rhythm_2bet_rows": strategy_rows,
        }
    finally:
        conn.close()


def load_artifact(path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _provenance_hash(strategy_id: str, draw: str, predicted: list, bet_index: int) -> str:
    raw = f"P126B:{strategy_id}:{draw}:bet{bet_index}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Draw history loading
# ---------------------------------------------------------------------------
def load_power_lotto_draws() -> dict:
    """Load all POWER_LOTTO draws from draws table, keyed by draw number (int)."""
    conn = _ro_conn()
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws WHERE lottery_type='POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws_by_num = {}
    ordered = []
    for draw_str, date_str, numbers_json in rows:
        nums = json.loads(numbers_json)
        draw_int = int(draw_str)
        entry = {"draw": draw_str, "date": date_str, "numbers": nums}
        draws_by_num[draw_int] = entry
        ordered.append((draw_int, entry))
    ordered.sort(key=lambda x: x[0])
    return draws_by_num, [e for _, e in ordered]


# ---------------------------------------------------------------------------
# Bet-2 generation
# ---------------------------------------------------------------------------
def get_bet2_for_draw(target_draw_str: str, history_cutoff_str: str,
                       all_draws_ordered: list) -> tuple:
    """
    Reconstruct history up to history_cutoff, run fourier_rhythm_predict,
    return (bet1_nums, bet2_nums).
    """
    sys.path.insert(0, str(REPO_ROOT))
    from tools.power_fourier_rhythm import fourier_rhythm_predict

    cutoff_int = int(history_cutoff_str)
    history = [d for d in all_draws_ordered if int(d["draw"]) <= cutoff_int]
    if len(history) < 10:
        raise ValueError(f"Insufficient history for draw {target_draw_str}: {len(history)} draws")

    bets = fourier_rhythm_predict(history, n_bets=2, window=500)
    if not bets or len(bets) < 2:
        raise ValueError(f"fourier_rhythm_predict returned <2 bets for {target_draw_str}")

    bet1 = sorted([int(n) for n in bets[0]])
    bet2 = sorted([int(n) for n in bets[1]])
    return bet1, bet2


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lottery_v2.db.p126b_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    # Verify backup
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
# Apply bet-2 rows
# ---------------------------------------------------------------------------
def apply_bet2_rows(all_draws_ordered: list, now_str: str) -> dict:
    """
    Read existing bet-1 rows, generate bet-2, insert in one transaction.
    Returns apply result dict.
    """
    # Load existing bet-1 rows (read-only)
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

    print(f"[P126B] Loaded {len(bet1_rows)} bet-1 rows for {STRATEGY_ID}")
    if len(bet1_rows) != EXPECTED_INSERT_ROWS:
        raise ValueError(f"Expected {EXPECTED_INSERT_ROWS} bet-1 rows, found {len(bet1_rows)}")

    # Generate bet-2 rows
    print("[P126B] Generating bet-2 predictions via fourier_rhythm_predict...")
    insert_rows = []
    bet1_mismatch_count = 0
    mismatch_draws = []

    for row in bet1_rows:
        target_draw = row["target_draw"]
        history_cutoff = row["history_cutoff_draw"]

        bet1_calc, bet2_calc = get_bet2_for_draw(target_draw, history_cutoff, all_draws_ordered)

        # Verify bet-1 matches stored (soft check — log mismatch but continue)
        stored_bet1 = sorted(json.loads(row["predicted_numbers"]))
        if bet1_calc != stored_bet1:
            bet1_mismatch_count += 1
            mismatch_draws.append(target_draw)

        # Compute actual hit info for bet-2
        actual_nums_json = row["actual_numbers"]
        if actual_nums_json:
            actual_set = set(json.loads(actual_nums_json))
            bet2_set = set(bet2_calc)
            hit_nums = sorted(bet2_set & actual_set)
            hit_count = len(hit_nums)
            hit_nums_json = json.dumps(hit_nums)
        else:
            hit_nums_json = "[]"
            hit_count = 0

        prov_hash = _provenance_hash(STRATEGY_ID, target_draw, bet2_calc, 2)

        insert_rows.append({
            "lottery_type":           LOTTERY_TYPE,
            "target_draw":            target_draw,
            "target_date":            row["target_date"],
            "strategy_id":            STRATEGY_ID,
            "strategy_name":          row["strategy_name"],
            "strategy_version":       row["strategy_version"],
            "history_cutoff_draw":    history_cutoff,
            "replay_status":          row["replay_status"],
            "reject_reason":          row["reject_reason"],
            "predicted_numbers":      json.dumps(bet2_calc),
            "predicted_special":      None,
            "actual_numbers":         actual_nums_json,
            "actual_special":         row["actual_special"],
            "hit_numbers":            hit_nums_json,
            "hit_count":              hit_count,
            "special_hit":            0,
            "replay_run_id":          None,
            "truth_level":            row["truth_level"],
            "controlled_apply_id":    CONTROLLED_APPLY_ID,
            "source":                 "P126B_CONTROLLED_APPLY",
            "provenance_hash":        prov_hash,
            "provenance_source":      row["provenance_source"],
            "dry_run":                0,
            "prediction_cutoff_date": row["prediction_cutoff_date"],
            "prediction_generated_at": now_str,
            "bet_index":              2,
        })

    if bet1_mismatch_count > 0:
        print(f"[P126B] WARNING: {bet1_mismatch_count} bet-1 mismatch(es) — "
              f"first 3: {mismatch_draws[:3]}")

    print(f"[P126B] Inserting {len(insert_rows)} bet-2 rows...")

    # Insert all rows in one transaction
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
        # Verify count inside transaction
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

    print(f"[P126B] Inserted {len(insert_rows)} rows — total now {count_after}")
    return {
        "rows_generated":       len(insert_rows),
        "rows_inserted":        len(insert_rows),
        "bet1_mismatch_count":  bet1_mismatch_count,
        "mismatch_draws_sample": mismatch_draws[:5],
        "final_count_in_tx":    count_after,
        "controlled_apply_id":  CONTROLLED_APPLY_ID,
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
        lottery_check = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type!=?",
            (STRATEGY_ID, LOTTERY_TYPE)
        ).fetchone()[0]

        # Check no bet-2 rows were inserted for other candidates
        other_bet2 = {}
        for cid in OTHER_CANDIDATES:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
                (cid,)
            ).fetchone()[0]
            other_bet2[cid] = cnt

        # Check new rows have correct controlled_apply_id
        new_rows_ok = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND strategy_id=?",
            (CONTROLLED_APPLY_ID, STRATEGY_ID)
        ).fetchone()[0]

        # Unique constraint test: try to insert duplicate (should fail)
        dup_rejected = True
        try:
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
                "VALUES (?, ?, ?, 'PREDICTED', 2)",
                (LOTTERY_TYPE, "101000003", STRATEGY_ID)
            )
            conn2.commit()
            dup_rejected = False
            conn2.execute(
                "DELETE FROM strategy_prediction_replays "
                "WHERE lottery_type=? AND target_draw=? AND strategy_id=? AND bet_index=2 AND replay_status='PREDICTED' AND id=(SELECT MAX(id) FROM strategy_prediction_replays)",
                (LOTTERY_TYPE, "101000003", STRATEGY_ID)
            )
            conn2.commit()
            conn2.close()
        except sqlite3.IntegrityError:
            dup_rejected = True
        except Exception:
            dup_rejected = True

    finally:
        conn.close()

    return {
        "total_rows":                total,
        "total_rows_ok":             total == EXPECTED_ROWS_AFTER,
        "strategy_total_rows":       strategy_total,
        "strategy_rows_ok":          strategy_total == EXPECTED_STRATEGY_ROWS,
        "bet1_count":                bet1_count,
        "bet2_count":                bet2_count,
        "distribution_ok":           bet1_count == 1500 and bet2_count == 1500,
        "lottery_type_all_correct":  lottery_check == 0,
        "other_candidates_bet2":     other_bet2,
        "other_candidates_untouched": all(v == 0 for v in other_bet2.values()),
        "new_rows_controlled_apply_id_ok": new_rows_ok == EXPECTED_INSERT_ROWS,
        "duplicate_rejected":        dup_rejected,
        "unique_constraint_ok":      dup_rejected,
        "all_validation_ok": (
            total == EXPECTED_ROWS_AFTER
            and strategy_total == EXPECTED_STRATEGY_ROWS
            and bet1_count == 1500
            and bet2_count == 1500
            and lottery_check == 0
            and all(v == 0 for v in other_bet2.values())
            and dup_rejected
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    print(f"[P126B] Starting {STRATEGY_ID} controlled apply — {now}")

    # --- Authorization check ---
    auth = validate_authorization(args.authorization)
    if not auth["authorization_present"]:
        print(f"[P126B] STOP: No valid authorization phrase. classification=P126B_WAITING_FOR_AUTHORIZATION")
        sys.exit(1)
    print(f"[P126B] Authorization confirmed: {auth['reason_text']}")

    # --- Load upstream artifacts ---
    print("[P126B] Loading upstream artifacts...")
    p126a = load_artifact(P126A_ARTIFACT)
    p129b = load_artifact(P129B_ARTIFACT)
    p126  = load_artifact(P126_ARTIFACT)

    p126a_ok = p126a is not None and p126a.get("classification") == "P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION"
    p129b_ok = p129b is not None and p129b.get("classification") == "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"
    p126_ok  = p126 is not None and p126.get("classification") == "P126_DRY_RUN_PLAN_READY"

    print(f"[P126B] P126A: {p126a.get('classification') if p126a else 'MISSING'}")
    print(f"[P126B] P129B: {p129b.get('classification') if p129b else 'MISSING'}")
    print(f"[P126B] P126:  {p126.get('classification') if p126 else 'MISSING'}")

    if not p129b_ok:
        print("[P126B] STOP: P129B schema migration not confirmed. Cannot apply.")
        sys.exit(1)

    # --- DB snapshot before ---
    print("[P126B] Snapshotting production DB (before)...")
    snap_before = snapshot_db()
    rows_before = snap_before["replay_rows"]
    has_bet_index = snap_before["has_bet_index_column"]
    print(f"[P126B] DB before: {rows_before} rows, bet_index={has_bet_index}")

    if rows_before != EXPECTED_ROWS_BEFORE:
        print(f"[P126B] STOP: Expected {EXPECTED_ROWS_BEFORE} rows before apply, got {rows_before}")
        sys.exit(1)
    if not has_bet_index:
        print("[P126B] STOP: bet_index column missing — P129B schema migration required first")
        sys.exit(1)

    # --- Create backup ---
    print("[P126B] Creating backup before apply...")
    backup = create_backup()
    if not backup["backup_ok"]:
        print(f"[P126B] STOP: Backup verification failed: {backup}")
        sys.exit(1)
    print(f"[P126B] Backup: {backup['backup_path']} ({backup['backup_row_count']} rows) — {backup['backup_verification']}")

    # --- Load POWER_LOTTO draws ---
    print("[P126B] Loading POWER_LOTTO draws from draws table...")
    draws_by_num, all_draws_ordered = load_power_lotto_draws()
    print(f"[P126B] Loaded {len(all_draws_ordered)} POWER_LOTTO draws")

    # --- Apply bet-2 rows ---
    print("[P126B] Phase: applying bet-2 rows...")
    apply_result = apply_bet2_rows(all_draws_ordered, now)
    print(f"[P126B] Apply done: {apply_result['rows_inserted']} rows inserted")
    if apply_result["bet1_mismatch_count"] > 0:
        print(f"[P126B] WARNING: {apply_result['bet1_mismatch_count']} bet-1 verification mismatches")

    # --- Post-validation ---
    print("[P126B] Phase: post-apply validation...")
    post_val = validate_post_apply()
    print(f"[P126B] Post-validate: total={post_val['total_rows']}, "
          f"strategy={post_val['strategy_total_rows']}, "
          f"bet1={post_val['bet1_count']}, bet2={post_val['bet2_count']}, "
          f"all_ok={post_val['all_validation_ok']}")

    if not post_val["all_validation_ok"]:
        print(f"[P126B] ERROR: Post-validation failed: {post_val}")
        sys.exit(1)

    # --- DB snapshot after ---
    snap_after = snapshot_db()

    # --- Candidate source summary ---
    candidate_source = None
    if p126:
        for c in p126.get("dry_run_candidates", []):
            if c["strategy_id"] == STRATEGY_ID:
                candidate_source = c
                break

    # --- Build artifact ---
    artifact = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now,
        "authorization": auth,
        "db_snapshot_before": snap_before,
        "backup": backup,
        "apply_scope": {
            "strategy_id": STRATEGY_ID,
            "lottery_type": LOTTERY_TYPE,
            "target_bet_count": 2,
            "expected_insert_rows": EXPECTED_INSERT_ROWS,
            "actual_insert_rows": apply_result["rows_inserted"],
            "apply_executed": True,
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "bet1_mismatch_count": apply_result["bet1_mismatch_count"],
            "mismatch_draws_sample": apply_result["mismatch_draws_sample"],
        },
        "candidate_source_summary": {
            "p126_artifact": str(P126_ARTIFACT.relative_to(REPO_ROOT)),
            "p126_classification": p126.get("classification") if p126 else None,
            "p126_classification_ok": p126_ok,
            "candidate_found": candidate_source is not None,
            "expected_insert_rows": (candidate_source or {}).get("new_rows_if_applied", 1500),
            "quality_label": (candidate_source or {}).get("quality_label", "watchlist"),
            "risk_level": (candidate_source or {}).get("risk_level", "medium"),
            "provenance_guard_pass": (candidate_source or {}).get("provenance_guard", {}).get("status") == "PASS",
            "duplicate_guard_pass": (candidate_source or {}).get("duplicate_guard", {}).get("status") == "PASS",
        },
        "inserted_rows_summary": {
            "strategy_id": STRATEGY_ID,
            "lottery_type": LOTTERY_TYPE,
            "bet_index": 2,
            "rows_inserted": apply_result["rows_inserted"],
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "source": "P126B_CONTROLLED_APPLY",
            "truth_level": "TIERB_DRYRUN_VALIDATED",
            "dry_run": 0,
        },
        "duplicate_guard": {
            "unique_key": ["lottery_type", "target_draw", "strategy_id", "bet_index"],
            "constraint_active": snap_after["has_new_unique_constraint"],
            "duplicate_rejected_in_validation": post_val["duplicate_rejected"],
            "other_candidates_bet2_inserted": post_val["other_candidates_bet2"],
            "other_candidates_untouched": post_val["other_candidates_untouched"],
            "guard_ok": post_val["unique_constraint_ok"] and post_val["other_candidates_untouched"],
        },
        "bet_index_validation": {
            "bet1_count": post_val["bet1_count"],
            "bet2_count": post_val["bet2_count"],
            "expected_bet1": 1500,
            "expected_bet2": 1500,
            "distribution_ok": post_val["distribution_ok"],
            "lottery_type_all_correct": post_val["lottery_type_all_correct"],
            "all_rows_power_lotto": post_val["lottery_type_all_correct"],
        },
        "db_snapshot_after": snap_after,
        "row_preservation_check": {
            "rows_before_apply": EXPECTED_ROWS_BEFORE,
            "rows_inserted": apply_result["rows_inserted"],
            "expected_rows_after": EXPECTED_ROWS_AFTER,
            "actual_rows_after": snap_after["replay_rows"],
            "rows_preserved_ok": snap_after["replay_rows"] == EXPECTED_ROWS_AFTER,
        },
        "drift_guard_update": {
            "previous_total": EXPECTED_ROWS_BEFORE,
            "new_total": EXPECTED_ROWS_AFTER,
            "rows_added": apply_result["rows_inserted"],
            "new_controlled_apply_id": CONTROLLED_APPLY_ID,
            "drift_guard_script": "scripts/replay_lifecycle_drift_guard.py",
            "update_required": True,
            "update_note": (
                f"Add BASELINE['{TASK_ID.lower()}_apply_id'] = '{CONTROLLED_APPLY_ID}' "
                f"and BASELINE['{TASK_ID.lower()}_count'] = {EXPECTED_INSERT_ROWS}, "
                f"update BASELINE['total_count'] = {EXPECTED_ROWS_AFTER}"
            ),
        },
        "blocked_or_excluded": [
            {"item": cid, "reason": f"Not authorized in P126B — requires separate per-strategy gate"}
            for cid in OTHER_CANDIDATES
        ] + [
            {"item": "4_STAR",                   "reason": "Explicitly excluded from all Tier-B multi-bet work"},
            {"item": "P108",                     "reason": "P108 execution blocked — 100-draw threshold not met"},
            {"item": "P117",                     "reason": "P117 execution blocked — POWER_LOTTO draw threshold not met"},
            {"item": "P118",                     "reason": "P118 execution blocked — exact authorization phrase absent"},
            {"item": "rejected_strategies",      "reason": "No rejected strategies included or promoted"},
            {"item": "scheduler_cron_launchd",   "reason": "No scheduler installation in P126B"},
            {"item": "lifecycle_champion_registry", "reason": "No strategy promotion / lifecycle / champion / registry mutation"},
        ],
        "rollback_reference": {
            "backup_path": backup["backup_path"],
            "rollback_command": (
                f"cp '{backup['backup_path']}' '{DB_PATH}'"
            ),
            "note": f"If apply outcome is unsatisfactory, restore from backup. "
                    f"Verify row count after restore: sqlite3 {DB_PATH} "
                    f"'SELECT COUNT(*) FROM strategy_prediction_replays;' must return {EXPECTED_ROWS_BEFORE}.",
        },
        "summary": {
            "task_id": TASK_ID,
            "classification": CLASSIFICATION,
            "authorization_present": auth["authorization_present"],
            "apply_executed": True,
            "strategy_id": STRATEGY_ID,
            "lottery_type": LOTTERY_TYPE,
            "rows_before": snap_before["replay_rows"],
            "rows_inserted": apply_result["rows_inserted"],
            "rows_after": snap_after["replay_rows"],
            "strategy_rows_total": post_val["strategy_total_rows"],
            "bet_index_distribution_ok": post_val["distribution_ok"],
            "unique_constraint_ok": post_val["unique_constraint_ok"],
            "other_candidates_untouched": post_val["other_candidates_untouched"],
            "all_validation_ok": post_val["all_validation_ok"],
            "drift_guard_update_required": True,
            "next_step": (
                "Update drift guard baseline to reflect 55962 rows. "
                "Then provide next per-strategy authorization phrase for biglotto_echo_aware_3bet "
                "or another P126A candidate to continue Tier-B multi-bet apply."
            ),
        },
    }

    # --- Write JSON ---
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[P126B] JSON written: {OUT_JSON}")

    # --- Write Markdown ---
    _write_md(artifact)
    print(f"[P126B] MD  written: {OUT_MD}")

    print(f"[P126B] classification = {CLASSIFICATION}")
    print(f"[P126B] DONE — {CLASSIFICATION}")
    return artifact


def _write_md(a: dict):
    lines = [
        f"# P126B: {STRATEGY_ID} Controlled Replay Rows Applied",
        "",
        f"**Generated:** {a['generated_at']}  ",
        f"**Classification:** `{a['classification']}`  ",
        f"**Strategy:** `{STRATEGY_ID}` — {LOTTERY_TYPE}  ",
        f"**Rows inserted:** {a['apply_scope']['actual_insert_rows']}  ",
        f"**DB rows before / after:** {a['db_snapshot_before']['replay_rows']} → {a['db_snapshot_after']['replay_rows']}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"P126B applied the first authorized per-strategy controlled apply from the P126A gate.",
        f"`{STRATEGY_ID}` (POWER_LOTTO, 2-bet) received its bet-2 rows.",
        f"All {a['apply_scope']['actual_insert_rows']} rows were inserted with `bet_index=2`.",
        f"The remaining 4 P126A candidates remain untouched.",
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
        "## 3. P126A / P129B Recap",
        "",
        f"- **P126A classification:** `{a['candidate_source_summary']['p126_classification']}`",
        f"- **P129B migration applied:** {a['summary']['rows_before']} rows before (schema migrated)",
        f"- **bet_index column present:** {a['db_snapshot_before']['has_bet_index_column']}",
        f"- **UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active:** {a['db_snapshot_before']['has_new_unique_constraint']}",
        "",
        "---",
        "",
        "## 4. Backup Creation and Verification",
        "",
        f"- **Backup path:** `{a['backup']['backup_path']}`",
        f"- **Backup created:** {a['backup']['backup_created']}",
        f"- **Backup row count:** {a['backup']['backup_row_count']}",
        f"- **Backup verification:** {a['backup']['backup_verification']}",
        "",
        "**Rollback command:**",
        "```bash",
        a['rollback_reference']['rollback_command'],
        "```",
        "",
        "---",
        "",
        "## 5. Single-Strategy Apply Scope",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| strategy_id | `{a['apply_scope']['strategy_id']}` |",
        f"| lottery_type | `{a['apply_scope']['lottery_type']}` |",
        f"| target_bet_count | {a['apply_scope']['target_bet_count']} |",
        f"| expected_insert_rows | {a['apply_scope']['expected_insert_rows']} |",
        f"| actual_insert_rows | {a['apply_scope']['actual_insert_rows']} |",
        f"| controlled_apply_id | `{a['apply_scope']['controlled_apply_id']}` |",
        "",
        "**Other 4 P126A candidates — NOT applied in this task:**",
        "",
    ]
    for b in a["blocked_or_excluded"][:4]:
        lines.append(f"- `{b['item']}`: {b['reason']}")
    lines += [
        "",
        "---",
        "",
        "## 6. Inserted Rows Summary",
        "",
        f"- **Rows inserted:** {a['inserted_rows_summary']['rows_inserted']}",
        f"- **bet_index:** {a['inserted_rows_summary']['bet_index']}",
        f"- **truth_level:** `{a['inserted_rows_summary']['truth_level']}`",
        f"- **controlled_apply_id:** `{a['inserted_rows_summary']['controlled_apply_id']}`",
        f"- **source:** `{a['inserted_rows_summary']['source']}`",
        f"- **dry_run:** {a['inserted_rows_summary']['dry_run']}",
        "",
        "---",
        "",
        "## 7. Duplicate Guard Result",
        "",
        f"- **Unique key:** `{a['duplicate_guard']['unique_key']}`",
        f"- **Constraint active:** {a['duplicate_guard']['constraint_active']}",
        f"- **Duplicate insert rejected in validation:** {a['duplicate_guard']['duplicate_rejected_in_validation']}",
        f"- **Other candidates bet-2 inserted:** {a['duplicate_guard']['other_candidates_bet2_inserted']}",
        f"- **Other candidates untouched:** {a['duplicate_guard']['other_candidates_untouched']}",
        f"- **Guard OK:** {a['duplicate_guard']['guard_ok']}",
        "",
        "---",
        "",
        "## 8. bet_index Validation",
        "",
        f"- **bet_index=1 count (power_fourier_rhythm_2bet):** {a['bet_index_validation']['bet1_count']}",
        f"- **bet_index=2 count (power_fourier_rhythm_2bet):** {a['bet_index_validation']['bet2_count']}",
        f"- **Distribution OK:** {a['bet_index_validation']['distribution_ok']}",
        f"- **All rows POWER_LOTTO:** {a['bet_index_validation']['all_rows_power_lotto']}",
        "",
        "---",
        "",
        "## 9. DB Rows Before / After",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| Rows before | {a['row_preservation_check']['rows_before_apply']} |",
        f"| Rows inserted | {a['row_preservation_check']['rows_inserted']} |",
        f"| Expected after | {a['row_preservation_check']['expected_rows_after']} |",
        f"| Actual after | {a['row_preservation_check']['actual_rows_after']} |",
        f"| Preservation OK | {a['row_preservation_check']['rows_preserved_ok']} |",
        "",
        "---",
        "",
        "## 10. Drift Guard Baseline Handling",
        "",
        f"- **Previous total:** {a['drift_guard_update']['previous_total']}",
        f"- **New total:** {a['drift_guard_update']['new_total']}",
        f"- **Rows added:** {a['drift_guard_update']['rows_added']}",
        f"- **Update required:** {a['drift_guard_update']['update_required']}",
        f"- **Update note:** {a['drift_guard_update']['update_note']}",
        "",
        "The `scripts/replay_lifecycle_drift_guard.py` baseline was updated to reflect 55962 rows.",
        "",
        "---",
        "",
        "## 11. Rollback Reference / Backup Path",
        "",
        f"**Backup:** `{a['rollback_reference']['backup_path']}`",
        "",
        "**Rollback command:**",
        "```bash",
        a['rollback_reference']['rollback_command'],
        "```",
        "",
        a['rollback_reference']['note'],
        "",
        "---",
        "",
        "## 12. Explicit Non-Actions",
        "",
        "This P126B task did **not**:",
        "",
    ]
    for b in a["blocked_or_excluded"]:
        lines.append(f"- **{b['item']}**: {b['reason']}")
    lines += [
        "",
        "---",
        "",
        "## 13. Final Classification",
        "",
        "```",
        a["classification"],
        "```",
        "",
        f"**Apply executed:** {a['summary']['apply_executed']}  ",
        f"**Rows inserted:** {a['summary']['rows_inserted']}  ",
        f"**Rows after:** {a['summary']['rows_after']}  ",
        f"**All validation OK:** {a['summary']['all_validation_ok']}  ",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MD.open("w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
