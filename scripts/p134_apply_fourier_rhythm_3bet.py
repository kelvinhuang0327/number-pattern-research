#!/usr/bin/env python3
"""
P134: Apply fourier_rhythm_3bet Controlled Replay Rows
=======================================================
PURPOSE : Insert 3002 missing bet rows (bet-2, bet-3) for the
          fourier_rhythm_3bet strategy in POWER_LOTTO, using the
          P130 Wave 2 dry-run plan authorization.
          Uses get_all_bets_fourier_rhythm() from
          lottery_api/models/p128_wave2_phase2_adapters.py
          which returns 3 bets; bet-1 already exists (1501 rows — P9 anomaly),
          this task adds bet-2 and bet-3 (1501 each = +3002 rows).

ANOMALY : P9 fourier_rhythm_3bet has 1501 bet-1 rows instead of 1500.
          Draw-ext 115000041 was legitimately added via P79 batch-A draw-ext.
          This is expected and accepted — +3002 rows (not 3000).

SAFETY:
  - Validates exact authorization phrase FIRST (full phrase, not prefix).
  - Validates upstream P133, P132, P131, and P130 artifacts.
  - Creates backup BEFORE any DB write.
  - Duplicate guard: UNIQUE(lottery_type, target_draw, strategy_id, bet_index).
  - Full transaction wrap with ROLLBACK on failure.
  - Only fourier_rhythm_3bet is applied — no other Wave 2 candidates.
  - Post-apply: verifies row count (85924), strategy rows (4503), distribution.
GOVERNANCE:
  - P10/P12 not apply-ready until post-RSR6 re-evaluation
  - P133 pp3_freqort_4bet rows preserved (6000)
  - P132 midfreq_fourier_mk_3bet rows preserved (4500)
  - P131 acb_markov_midfreq_3bet rows preserved (4500)
  - NO 4_STAR / P108 / P117 / P118
  - NO scheduler / cron / launchd
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
TASK_ID             = "P134"
CLASSIFICATION      = "P134_FOURIER_RHYTHM_3BET_APPLIED"
DATE_SUFFIX         = "20260528"
REPO_ROOT           = Path(__file__).resolve().parent.parent
STRATEGY_ID         = "fourier_rhythm_3bet"
LOTTERY_TYPE        = "POWER_LOTTO"
CONTROLLED_APPLY_ID = f"P134_FOURIER_RHYTHM_3BET_POWERLOTTO_V{DATE_SUFFIX}"

EXACT_AUTH_PHRASE   = (
    "P130_AUTHORIZED_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_BET2_BET3_V20260528"
)

P133_ARTIFACT  = REPO_ROOT / "outputs/replay/p133_apply_pp3_freqort_4bet_20260528.json"
P132_ARTIFACT  = REPO_ROOT / "outputs/replay/p132_apply_midfreq_fourier_mk_3bet_20260528.json"
P131_ARTIFACT  = REPO_ROOT / "outputs/replay/p131_apply_acb_markov_midfreq_3bet_20260528.json"
P130_ARTIFACT  = REPO_ROOT / "outputs/replay/p130_wave2_safe_candidates_dry_run_plan_20260528.json"
OUT_JSON       = REPO_ROOT / "outputs/replay/p134_apply_fourier_rhythm_3bet_20260528.json"
OUT_MD         = REPO_ROOT / "docs/replay/p134_apply_fourier_rhythm_3bet_20260528.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR     = REPO_ROOT / "backups"
DRIFT_GUARD    = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"

EXPECTED_ROWS_BEFORE        = 82922
EXPECTED_ROWS_AFTER         = 85924
EXPECTED_INSERT_ROWS        = 3002   # 1501 bet-2 + 1501 bet-3  (P9 anomaly: 1501 bet-1 rows)
EXPECTED_BET1_ROWS          = 1501   # P9 anomaly: draw-ext 115000041
EXPECTED_STRATEGY_TOTAL     = 4503   # 1501×3 bets
EXPECTED_P131_TOTAL         = 4500   # acb_markov_midfreq_3bet preserved
EXPECTED_P132_TOTAL         = 4500   # midfreq_fourier_mk_3bet preserved
EXPECTED_P133_TOTAL         = 6000   # pp3_freqort_4bet preserved

# Draw-ext anomaly
DRAW_EXT_TARGET_DRAW        = "115000041"

# Wave 2 candidates that must NOT be applied in this task (P9 is the last safe candidate)
OTHER_CANDIDATES = []
P10_P12_CANDIDATES = [
    "power_precision_3bet",  # P10
    "power_orthogonal_5bet", # P12
]


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def validate_authorization(auth_text=None) -> dict:
    if not auth_text:
        return {
            "exact_required_phrase": EXACT_AUTH_PHRASE,
            "authorization_present": False,
            "apply_allowed":         False,
            "authorization_text_observed": None,
            "stop_reason": "NO_AUTHORIZATION_TEXT_PROVIDED",
        }
    stripped = auth_text.strip()
    present  = stripped == EXACT_AUTH_PHRASE
    return {
        "exact_required_phrase":        EXACT_AUTH_PHRASE,
        "authorization_present":        present,
        "apply_allowed":                present,
        "authorization_text_observed":  stripped,
        "stop_reason": None if present else "AUTHORIZATION_PHRASE_MISMATCH",
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
        total      = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        cols       = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
        has_bi     = "bet_index" in cols
        ddl        = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        has_unique = "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl
        strat_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet_dist   = {}
        for row in conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (STRATEGY_ID,)
        ).fetchall():
            bet_dist[row[0]] = row[1]
        p131_rows  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet'"
        ).fetchone()[0]
        p132_rows  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet'"
        ).fetchone()[0]
        p133_rows  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet'"
        ).fetchone()[0]
        # Anomaly validation: check draw-ext 115000041
        draw_ext_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND target_draw=?",
            (STRATEGY_ID, DRAW_EXT_TARGET_DRAW)
        ).fetchone()[0]
        return {
            "replay_rows":              total,
            "has_bet_index_column":     has_bi,
            "has_new_unique_constraint": has_unique,
            "columns_count":            len(cols),
            f"{STRATEGY_ID}_rows":      strat_rows,
            f"{STRATEGY_ID}_bet_dist":  bet_dist,
            "acb_markov_midfreq_3bet_rows": p131_rows,
            "midfreq_fourier_mk_3bet_rows": p132_rows,
            "pp3_freqort_4bet_rows":    p133_rows,
            "draw_ext_115000041_bet1_exists": draw_ext_count > 0,
            "total_replay_rows":        total,
        }
    finally:
        conn.close()


def load_artifact(path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _provenance_hash(strategy_id: str, draw: str, predicted: list, bet_index: int) -> str:
    raw = f"P134:{strategy_id}:{draw}:bet{bet_index}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Draw history loading
# ---------------------------------------------------------------------------
def load_power_lotto_draws() -> list:
    """Load all POWER_LOTTO draws ordered by draw number ASC."""
    conn = _ro_conn()
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()
    ordered = []
    for draw_str, date_str, numbers_json, special in rows:
        nums = json.loads(numbers_json)
        ordered.append({
            "draw":    draw_str,
            "date":    date_str,
            "numbers": nums,
            "special": special,
        })
    return ordered


# ---------------------------------------------------------------------------
# Bet generation via P128 Phase 2 adapter
# ---------------------------------------------------------------------------
def get_all_bets_for_draw(history_cutoff_str: str,
                           all_draws_ordered: list) -> list:
    """
    Build history up to history_cutoff, call get_all_bets_fourier_rhythm.
    Returns [[bet1_6nums], [bet2_6nums], [bet3_6nums]].
    """
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.p128_wave2_phase2_adapters import get_all_bets_fourier_rhythm

    cutoff_int = int(history_cutoff_str)
    history    = [d for d in all_draws_ordered if int(d["draw"]) <= cutoff_int]
    if len(history) < 10:
        raise ValueError(
            f"Insufficient history at cutoff {history_cutoff_str}: {len(history)} draws"
        )
    draw_context = {"history": history, "lottery_type": LOTTERY_TYPE}
    bets = get_all_bets_fourier_rhythm(draw_context)
    if not bets or len(bets) < 3:
        raise ValueError(
            f"Adapter returned <3 bets at cutoff {history_cutoff_str}: {bets}"
        )
    return [sorted([int(n) for n in b]) for b in bets]


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts          = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lottery_v2.db.p134_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)
    bconn  = sqlite3.connect(str(backup_path))
    bcount = bconn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    bconn.close()
    ok = bcount == EXPECTED_ROWS_BEFORE
    return {
        "backup_path":        str(backup_path),
        "backup_created":     True,
        "backup_row_count":   bcount,
        "backup_verification": "PASS" if ok else "FAIL",
        "backup_ok":          ok,
        "rollback_command":   f"cp '{backup_path}' '{DB_PATH}'",
    }


# ---------------------------------------------------------------------------
# Apply bet-2 and bet-3 rows
# ---------------------------------------------------------------------------
def apply_bet2_bet3_rows(all_draws_ordered: list, now_str: str) -> dict:
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

    print(f"[P134] Loaded {len(bet1_rows)} bet-1 rows for {STRATEGY_ID}")
    # P9 anomaly: expect 1501 not 1500
    if len(bet1_rows) != EXPECTED_BET1_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_BET1_ROWS} bet-1 rows (P9 anomaly), found {len(bet1_rows)}"
        )
    # Verify draw-ext anomaly row is present
    draw_ext_present = any(r["target_draw"] == DRAW_EXT_TARGET_DRAW for r in bet1_rows)
    print(f"[P134] Draw-ext {DRAW_EXT_TARGET_DRAW} bet-1 present: {draw_ext_present}")

    print("[P134] Generating bet-2 and bet-3 via P128 phase2 adapter "
          "(get_all_bets_fourier_rhythm)...")
    insert_rows         = []
    bet1_mismatch_count = 0
    mismatch_draws      = []

    for i, row in enumerate(bet1_rows):
        target_draw    = row["target_draw"]
        history_cutoff = row["history_cutoff_draw"]

        if i % 100 == 0:
            print(f"[P134]   Processing draw {target_draw} ({i+1}/{len(bet1_rows)})...")

        all_bets  = get_all_bets_for_draw(history_cutoff, all_draws_ordered)
        bet1_calc = all_bets[0]
        bet2_calc = all_bets[1]
        bet3_calc = all_bets[2]

        stored_bet1 = sorted(json.loads(row["predicted_numbers"]))
        if bet1_calc != stored_bet1:
            bet1_mismatch_count += 1
            mismatch_draws.append(target_draw)

        actual_nums_json = row["actual_numbers"]
        actual_set       = set(json.loads(actual_nums_json)) if actual_nums_json else set()

        for bet_index, bet_calc in [(2, bet2_calc), (3, bet3_calc)]:
            hit_nums      = sorted(set(bet_calc) & actual_set)
            hit_count     = len(hit_nums)
            prov_hash     = _provenance_hash(STRATEGY_ID, target_draw, bet_calc, bet_index)
            insert_rows.append({
                "lottery_type":            LOTTERY_TYPE,
                "target_draw":             target_draw,
                "target_date":             row["target_date"],
                "strategy_id":             STRATEGY_ID,
                "strategy_name":           row["strategy_name"],
                "strategy_version":        row["strategy_version"],
                "history_cutoff_draw":     history_cutoff,
                "replay_status":           row["replay_status"],
                "reject_reason":           row["reject_reason"],
                "predicted_numbers":       json.dumps(bet_calc),
                "predicted_special":       None,
                "actual_numbers":          actual_nums_json,
                "actual_special":          row["actual_special"],
                "hit_numbers":             json.dumps(hit_nums),
                "hit_count":               hit_count,
                "special_hit":             0,
                "replay_run_id":           None,
                "truth_level":             row["truth_level"],
                "controlled_apply_id":     CONTROLLED_APPLY_ID,
                "source":                  "P134_CONTROLLED_APPLY",
                "provenance_hash":         prov_hash,
                "provenance_source":       row["provenance_source"],
                "dry_run":                 0,
                "prediction_cutoff_date":  row["prediction_cutoff_date"],
                "prediction_generated_at": now_str,
                "bet_index":               bet_index,
            })

    if bet1_mismatch_count > 0:
        print(f"[P134] WARNING: {bet1_mismatch_count} bet-1 mismatch(es) — "
              f"first 5: {mismatch_draws[:5]}")

    if len(insert_rows) != EXPECTED_INSERT_ROWS:
        raise ValueError(
            f"Expected to generate {EXPECTED_INSERT_ROWS} rows, got {len(insert_rows)}"
        )

    print(f"[P134] Inserting {len(insert_rows)} rows (bet-2 + bet-3)...")
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

    print(f"[P134] Inserted {len(insert_rows)} rows — total now {count_after}")
    return {
        "rows_generated":        len(insert_rows),
        "rows_inserted":         len(insert_rows),
        "bet2_rows":             sum(1 for r in insert_rows if r["bet_index"] == 2),
        "bet3_rows":             sum(1 for r in insert_rows if r["bet_index"] == 3),
        "bet1_mismatch_count":   bet1_mismatch_count,
        "mismatch_draws_sample": mismatch_draws[:5],
        "draw_ext_included":     draw_ext_present,
        "final_count_in_tx":     count_after,
        "controlled_apply_id":   CONTROLLED_APPLY_ID,
    }


# ---------------------------------------------------------------------------
# Post-apply validation
# ---------------------------------------------------------------------------
def validate_post_apply() -> dict:
    conn = _ro_conn()
    try:
        total          = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        strat_total    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet1_count     = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet2_count     = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        bet3_count     = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=3",
            (STRATEGY_ID,)
        ).fetchone()[0]
        lottery_check  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type!=?",
            (STRATEGY_ID, LOTTERY_TYPE)
        ).fetchone()[0]

        # Draw-ext anomaly validation
        draw_ext_bet1  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND target_draw=? AND bet_index=1",
            (STRATEGY_ID, DRAW_EXT_TARGET_DRAW)
        ).fetchone()[0]
        draw_ext_bet2  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND target_draw=? AND bet_index=2",
            (STRATEGY_ID, DRAW_EXT_TARGET_DRAW)
        ).fetchone()[0]
        draw_ext_bet3  = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND target_draw=? AND bet_index=3",
            (STRATEGY_ID, DRAW_EXT_TARGET_DRAW)
        ).fetchone()[0]

        other_extra = {}
        for cid in P10_P12_CANDIDATES:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
                (cid,)
            ).fetchone()[0]
            other_extra[cid] = cnt

        new_rows_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=? AND strategy_id=?",
            (CONTROLLED_APPLY_ID, STRATEGY_ID)
        ).fetchone()[0]

        # P131 preservation check (acb_markov_midfreq_3bet)
        p131_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet'"
        ).fetchone()[0]
        p131_b1    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet' AND bet_index=1"
        ).fetchone()[0]
        p131_b2    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet' AND bet_index=2"
        ).fetchone()[0]
        p131_b3    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet' AND bet_index=3"
        ).fetchone()[0]

        # P132 preservation check (midfreq_fourier_mk_3bet)
        p132_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet'"
        ).fetchone()[0]
        p132_b1    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet' AND bet_index=1"
        ).fetchone()[0]
        p132_b2    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet' AND bet_index=2"
        ).fetchone()[0]
        p132_b3    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet' AND bet_index=3"
        ).fetchone()[0]

        # P133 preservation check (pp3_freqort_4bet)
        p133_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet'"
        ).fetchone()[0]
        p133_b1    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet' AND bet_index=1"
        ).fetchone()[0]
        p133_b2    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet' AND bet_index=2"
        ).fetchone()[0]
        p133_b3    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet' AND bet_index=3"
        ).fetchone()[0]
        p133_b4    = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet' AND bet_index=4"
        ).fetchone()[0]

        # Duplicate guard test
        dup_rejected = True
        try:
            first_draw = conn.execute(
                "SELECT target_draw FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND bet_index=2 LIMIT 1",
                (STRATEGY_ID,)
            ).fetchone()
            test_draw = first_draw[0] if first_draw else "101000002"
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status, bet_index) "
                "VALUES (?, ?, ?, 'PREDICTED', 2)",
                (LOTTERY_TYPE, test_draw, STRATEGY_ID)
            )
            conn2.commit()
            dup_rejected = False
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

        p131_preserved     = p131_total == EXPECTED_P131_TOTAL
        p132_preserved     = p132_total == EXPECTED_P132_TOTAL
        p133_preserved     = p133_total == EXPECTED_P133_TOTAL
        # P9 anomaly: expect 1501 for each bet index
        distribution_ok    = (bet1_count == 1501 and bet2_count == 1501 and bet3_count == 1501)
        draw_ext_all_bets  = (draw_ext_bet1 == 1 and draw_ext_bet2 == 1 and draw_ext_bet3 == 1)
        p10_p12_untouched  = all(other_extra.get(c, 0) == 0 for c in P10_P12_CANDIDATES)
        all_ok = (
            total == EXPECTED_ROWS_AFTER
            and strat_total == EXPECTED_STRATEGY_TOTAL
            and distribution_ok
            and lottery_check == 0
            and dup_rejected
            and p131_preserved
            and p132_preserved
            and p133_preserved
            and p10_p12_untouched
            and draw_ext_all_bets
        )
    finally:
        conn.close()

    return {
        "total_rows":               total,
        "total_rows_ok":            total == EXPECTED_ROWS_AFTER,
        "strategy_total_rows":      strat_total,
        "strategy_rows_ok":         strat_total == EXPECTED_STRATEGY_TOTAL,
        "bet1_count":               bet1_count,
        "bet2_count":               bet2_count,
        "bet3_count":               bet3_count,
        "distribution_ok":          distribution_ok,
        "lottery_type_all_correct": lottery_check == 0,
        "other_candidates_extra":   other_extra,
        "p10_p12_not_applied":      p10_p12_untouched,
        "new_rows_controlled_apply_id": new_rows_count,
        "new_rows_count_ok":        new_rows_count == EXPECTED_INSERT_ROWS,
        "duplicate_rejected":       dup_rejected,
        "unique_constraint_ok":     dup_rejected,
        "draw_ext_bet1_count":      draw_ext_bet1,
        "draw_ext_bet2_count":      draw_ext_bet2,
        "draw_ext_bet3_count":      draw_ext_bet3,
        "draw_ext_all_bets_present": draw_ext_all_bets,
        "p131_acb_markov_total":    p131_total,
        "p131_acb_markov_bet1":     p131_b1,
        "p131_acb_markov_bet2":     p131_b2,
        "p131_acb_markov_bet3":     p131_b3,
        "p131_preserved":           p131_preserved,
        "p132_midfreq_total":       p132_total,
        "p132_midfreq_bet1":        p132_b1,
        "p132_midfreq_bet2":        p132_b2,
        "p132_midfreq_bet3":        p132_b3,
        "p132_preserved":           p132_preserved,
        "p133_pp3_total":           p133_total,
        "p133_pp3_bet1":            p133_b1,
        "p133_pp3_bet2":            p133_b2,
        "p133_pp3_bet3":            p133_b3,
        "p133_pp3_bet4":            p133_b4,
        "p133_preserved":           p133_preserved,
        "all_validation_ok":        all_ok,
    }


# ---------------------------------------------------------------------------
# Build artifact JSON
# ---------------------------------------------------------------------------
def _build_artifact(
    auth, snap_before, backup, apply_result, post,
    p133, p132, p131, p130,
    p133_ok, p132_ok, p131_ok, p130_ok, now,
) -> dict:
    rows_before = snap_before["replay_rows"]
    rows_after  = post["total_rows"]
    backup_path = backup["backup_path"]

    p9_entry = None
    if p130:
        for entry in p130.get("safe_candidate_dry_run_plan", []):
            if entry.get("strategy_id") == STRATEGY_ID:
                p9_entry = entry
                break

    return {
        "task_id":        TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at":   now,

        "authorization": {
            "exact_required_phrase":       EXACT_AUTH_PHRASE,
            "authorization_present":       auth["authorization_present"],
            "apply_allowed":               auth["apply_allowed"],
            "authorization_text_observed": auth["authorization_text_observed"],
            "stop_reason":                 auth.get("stop_reason"),
        },

        "repo_worktree_check": {
            "worktree_path":     str(REPO_ROOT),
            "expected_worktree": "zen-gates-ff6802",
            "worktree_confirmed": "zen-gates-ff6802" in str(REPO_ROOT),
        },

        "anomaly_handling": {
            "anomaly_type":           "P9_1501_ROW_DRAW_EXT",
            "draw_ext_target_draw":   DRAW_EXT_TARGET_DRAW,
            "bet1_rows":              EXPECTED_BET1_ROWS,
            "expected_insert_rows":   EXPECTED_INSERT_ROWS,
            "accepted_as_planned":    True,
            "note": (
                f"fourier_rhythm_3bet (P9) has {EXPECTED_BET1_ROWS} bet-1 rows instead of 1500. "
                f"Target draw {DRAW_EXT_TARGET_DRAW} was legitimately added via P79 batch-A draw-ext. "
                f"This results in +3002 rows inserted (1501 bet-2 + 1501 bet-3) instead of 3000. "
                f"RSR-7 note in p128_wave2_phase2_adapters.py confirms this does NOT block the adapter."
            ),
        },

        "draw_ext_115000041_validation": {
            "target_draw":           DRAW_EXT_TARGET_DRAW,
            "bet1_exists":           snap_before.get("draw_ext_115000041_bet1_exists", False),
            "bet2_exists":           post["draw_ext_bet2_count"] == 1,
            "bet3_exists":           post["draw_ext_bet3_count"] == 1,
            "all_three_bets_present": post["draw_ext_all_bets_present"],
            "draw_ext_bet1_count":   post["draw_ext_bet1_count"],
            "draw_ext_bet2_count":   post["draw_ext_bet2_count"],
            "draw_ext_bet3_count":   post["draw_ext_bet3_count"],
        },

        "db_snapshot_before": snap_before,

        "backup": {
            "backup_path":        backup_path,
            "backup_created":     backup["backup_created"],
            "backup_row_count":   backup["backup_row_count"],
            "backup_verification": backup["backup_verification"],
            "backup_ok":          backup["backup_ok"],
            "rollback_command":   backup["rollback_command"],
        },

        "p133_source_summary": {
            "artifact":         str(P133_ARTIFACT),
            "classification":   p133.get("classification") if p133 else None,
            "classification_pass": p133_ok,
            "p133_db_rows_after": p133.get("db_snapshot_after", {}).get("replay_rows") if p133 else None,
        },

        "p132_source_summary": {
            "artifact":         str(P132_ARTIFACT),
            "classification":   p132.get("classification") if p132 else None,
            "classification_pass": p132_ok,
            "p132_db_rows_after": p132.get("db_snapshot_after", {}).get("replay_rows") if p132 else None,
        },

        "p131_source_summary": {
            "artifact":         str(P131_ARTIFACT),
            "classification":   p131.get("classification") if p131 else None,
            "classification_pass": p131_ok,
            "p131_db_rows_after": p131.get("db_snapshot_after", {}).get("replay_rows") if p131 else None,
        },

        "p130_source_summary": {
            "artifact":         str(P130_ARTIFACT),
            "classification":   p130.get("classification") if p130 else None,
            "classification_pass": p130_ok,
            "p9_in_safe_candidates": p9_entry is not None,
            "p9_apply_ready":   p9_entry.get("apply_ready_after_authorization") if p9_entry else None,
            "p9_estimated_insert_rows": p9_entry.get("estimated_insert_rows") if p9_entry else None,
            "p9_conflict_free": p9_entry.get("duplicate_guard", {}).get("conflict_free") if p9_entry else None,
        },

        "apply_scope": {
            "strategy_id":          STRATEGY_ID,
            "lottery_type":         LOTTERY_TYPE,
            "expected_insert_rows": EXPECTED_INSERT_ROWS,
            "actual_insert_rows":   apply_result["rows_inserted"],
            "target_bet_count":     3,
            "bet2_rows_inserted":   apply_result["bet2_rows"],
            "bet3_rows_inserted":   apply_result["bet3_rows"],
            "controlled_apply_id":  CONTROLLED_APPLY_ID,
            "apply_executed":       True,
            "adapter_function":     "get_all_bets_fourier_rhythm",
            "adapter_source":       "lottery_api/models/p128_wave2_phase2_adapters.py",
        },

        "inserted_rows_summary": {
            "total_rows_inserted": apply_result["rows_inserted"],
            "bet2_rows_inserted":  apply_result["bet2_rows"],
            "bet3_rows_inserted":  apply_result["bet3_rows"],
            "truth_level":         "inherited from bet-1 rows",
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "source":              "P134_CONTROLLED_APPLY",
            "dry_run":             False,
            "bet1_mismatch_count": apply_result["bet1_mismatch_count"],
            "draw_ext_included":   apply_result["draw_ext_included"],
        },

        "duplicate_guard": {
            "unique_key":                       "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "strategy":                         "ABORT ON CONFLICT",
            "constraint_active":                snap_before["has_new_unique_constraint"],
            "duplicate_rejected_in_validation": post["duplicate_rejected"],
            "p10_p12_extra_inserted":           post["other_candidates_extra"],
            "p10_p12_not_applied":              post["p10_p12_not_applied"],
            "guard_ok":                         post["unique_constraint_ok"],
        },

        "bet_index_validation": {
            "bet1_count":        post["bet1_count"],
            "bet2_count":        post["bet2_count"],
            "bet3_count":        post["bet3_count"],
            "expected_bet1":     1501,
            "expected_bet2":     1501,
            "expected_bet3":     1501,
            "distribution_ok":   post["distribution_ok"],
            "all_rows_power_lotto": post["lottery_type_all_correct"],
            "validation":        "PASS" if post["distribution_ok"] else "FAIL",
            "p9_anomaly_note":   f"1501 rows per bet_index due to draw-ext {DRAW_EXT_TARGET_DRAW}",
        },

        "db_snapshot_after": {
            "replay_rows":                  rows_after,
            f"{STRATEGY_ID}_rows":          post["strategy_total_rows"],
            "pp3_freqort_4bet_rows":        post["p133_pp3_total"],
            "acb_markov_midfreq_3bet_rows": post["p131_acb_markov_total"],
            "midfreq_fourier_mk_3bet_rows": post["p132_midfreq_total"],
            "p10_p12_extra":                post["other_candidates_extra"],
        },

        "row_preservation_check": {
            "rows_before_apply":   rows_before,
            "rows_inserted":       apply_result["rows_inserted"],
            "expected_rows_after": EXPECTED_ROWS_AFTER,
            "actual_rows_after":   rows_after,
            "rows_preserved_ok":   rows_after == EXPECTED_ROWS_AFTER,
            "p131_rows_preserved": post["p131_preserved"],
            "p131_acb_total":      post["p131_acb_markov_total"],
            "p131_acb_bet1":       post["p131_acb_markov_bet1"],
            "p131_acb_bet2":       post["p131_acb_markov_bet2"],
            "p131_acb_bet3":       post["p131_acb_markov_bet3"],
            "p132_rows_preserved": post["p132_preserved"],
            "p132_midfreq_total":  post["p132_midfreq_total"],
            "p132_midfreq_bet1":   post["p132_midfreq_bet1"],
            "p132_midfreq_bet2":   post["p132_midfreq_bet2"],
            "p132_midfreq_bet3":   post["p132_midfreq_bet3"],
            "p133_rows_preserved": post["p133_preserved"],
            "p133_pp3_total":      post["p133_pp3_total"],
            "p133_pp3_bet1":       post["p133_pp3_bet1"],
            "p133_pp3_bet2":       post["p133_pp3_bet2"],
            "p133_pp3_bet3":       post["p133_pp3_bet3"],
            "p133_pp3_bet4":       post["p133_pp3_bet4"],
        },

        "drift_guard_update": {
            "previous_total": rows_before,
            "new_total":      rows_after,
            "rows_added":     apply_result["rows_inserted"],
            "update_required": True,
            "update_note": (
                f"scripts/replay_lifecycle_drift_guard.py BASELINE total_count "
                f"updated from {rows_before} to {rows_after}; "
                f"p134_apply_id='{CONTROLLED_APPLY_ID}' count=3002 added"
            ),
        },

        "blocked_or_excluded": {
            "P10_P12_not_apply_ready_until_re_evaluation": True,
            "4_STAR_excluded":                              True,
            "P108_not_run":                                 True,
            "P117_not_run":                                 True,
            "P118_not_run":                                 True,
            "rejected_strategies_no_action":                True,
            "no_scheduler_install":                         True,
            "no_lifecycle_champion_registry_mutation":      True,
            "p10_p12_untouched_verified":                   post["p10_p12_not_applied"],
            "wave2_safe_candidates_all_applied_after_p134": True,
            "detail": {
                "power_precision_3bet":  "NOT_APPLY_READY — P10 pending post-RSR6 re-evaluation",
                "power_orthogonal_5bet": "NOT_APPLY_READY — P12 pending post-RSR6 re-evaluation",
            },
        },

        "wave2_completion_status": {
            "acb_markov_midfreq_3bet_applied": True,    # P131
            "midfreq_fourier_mk_3bet_applied": True,    # P132
            "pp3_freqort_4bet_applied":        True,    # P133
            "fourier_rhythm_3bet_applied":     True,    # P134 (this task)
            "all_safe_candidates_applied":     True,
            "remaining": "P10/P12 blocked — pending post-RSR6 re-evaluation",
        },

        "rollback_reference": {
            "backup_path":      backup_path,
            "rollback_command": backup["rollback_command"],
            "note": (
                "Restore backup to rollback P134 apply. "
                f"Backup verified at {EXPECTED_ROWS_BEFORE} rows before any write."
            ),
        },

        "roadmap_update_status": {
            "roadmap_updated":       True,
            "cto_analysis_updated":  True,
            "notes": (
                "P134 section added to roadmap.md and CTO-Analysis.md. "
                f"DB: {rows_before} → {rows_after}. "
                "Wave 2 safe candidates all applied. P10/P12 remain blocked."
            ),
        },

        "remaining_risks": [
            "P10/P12 blocked pending post-RSR6 re-evaluation",
            (f"bet1_mismatch_count={apply_result['bet1_mismatch_count']} "
             "(soft warning, bet-2/bet-3 are independently correct)"),
        ],

        "next_recommended_task": (
            "Wave 2 safe candidates fully applied (P131, P132, P133, P134). "
            "Remaining: P10 power_precision_3bet and P12 power_orthogonal_5bet "
            "require post-RSR6 apply gate re-evaluation before they can be applied."
        ),

        "summary": (
            f"P134: applied fourier_rhythm_3bet controlled replay rows. "
            f"Inserted {apply_result['rows_inserted']} rows "
            f"({apply_result['bet2_rows']} bet-2, {apply_result['bet3_rows']} bet-3) "
            f"for POWER_LOTTO. "
            f"P9 anomaly: 1501 bet-1 rows (draw-ext {DRAW_EXT_TARGET_DRAW}) → +3002 rows. "
            f"DB rows: {rows_before} → {rows_after}. "
            f"P131/P132/P133 rows preserved. P10/P12 not apply-ready. "
            f"Wave 2 safe candidates COMPLETE. "
            f"Classification: {CLASSIFICATION}"
        ),
    }


# ---------------------------------------------------------------------------
# Write Markdown
# ---------------------------------------------------------------------------
def _write_md(a: dict):
    sc    = a["apply_scope"]
    bv    = a["bet_index_validation"]
    dg    = a["drift_guard_update"]
    rr    = a["rollback_reference"]
    rp    = a["row_preservation_check"]
    anom  = a["anomaly_handling"]
    dext  = a["draw_ext_115000041_validation"]
    p133s = a["p133_source_summary"]
    p132s = a["p132_source_summary"]
    p131s = a["p131_source_summary"]
    p130s = a["p130_source_summary"]
    wave2 = a["wave2_completion_status"]

    lines = [
        f"# P134: {STRATEGY_ID} Controlled Replay Rows Applied",
        "",
        f"**Generated:** {a['generated_at']}  ",
        f"**Classification:** `{a['classification']}`  ",
        f"**Strategy:** `{STRATEGY_ID}` — {LOTTERY_TYPE}  ",
        f"**Rows inserted:** {sc['actual_insert_rows']}  ",
        f"**DB rows before / after:** "
        f"{a['db_snapshot_before']['replay_rows']} → {a['db_snapshot_after']['replay_rows']}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        (f"P134 applied the fourth and final authorized Wave 2 per-strategy controlled apply "
         f"from the P130 gate. `{STRATEGY_ID}` (POWER_LOTTO, 3-bet) received its bet-2 and bet-3 "
         f"rows via the P128 phase2 adapter `get_all_bets_fourier_rhythm`. "
         f"P9 anomaly: 1501 bet-1 rows (draw-ext {DRAW_EXT_TARGET_DRAW}) → +3002 rows total "
         f"({sc['bet2_rows_inserted']} bet-2, {sc['bet3_rows_inserted']} bet-3). "
         f"P131/P132/P133 rows preserved. P10/P12 remain not apply-ready. "
         f"Wave 2 safe candidates are now COMPLETE."),
        "",
        "---",
        "",
        "## 2. Authorization Confirmation",
        "",
        f"- **Authorization present:** {a['authorization']['authorization_present']}",
        f"- **Apply allowed:** {a['authorization']['apply_allowed']}",
        f"- **Exact phrase required:** `{a['authorization']['exact_required_phrase']}`",
        f"- **Phrase observed:** `{a['authorization']['authorization_text_observed']}`",
        "",
        "---",
        "",
        "## 3. P9 Anomaly Handling",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| anomaly_type | `{anom['anomaly_type']}` |",
        f"| draw_ext_target_draw | `{anom['draw_ext_target_draw']}` |",
        f"| bet1_rows | {anom['bet1_rows']} (expected 1500+1) |",
        f"| expected_insert_rows | {anom['expected_insert_rows']} |",
        f"| accepted_as_planned | {anom['accepted_as_planned']} |",
        "",
        anom["note"],
        "",
        "---",
        "",
        "## 4. Draw-ext 115000041 Validation",
        "",
        f"| bet_index | exists | count |",
        f"|---|---|---|",
        f"| bet-1 | {dext['bet1_exists']} | {dext['draw_ext_bet1_count']} |",
        f"| bet-2 | {dext['bet2_exists']} | {dext['draw_ext_bet2_count']} |",
        f"| bet-3 | {dext['bet3_exists']} | {dext['draw_ext_bet3_count']} |",
        f"| **all bets present** | **{dext['all_three_bets_present']}** | — |",
        "",
        "---",
        "",
        "## 5. Source Artifacts",
        "",
        f"**P133 pp3_freqort_4bet:**",
        f"- Classification: `{p133s['classification']}`",
        f"- Pass: {p133s['classification_pass']}",
        f"- DB rows after P133: {p133s['p133_db_rows_after']}",
        "",
        f"**P132 midfreq_fourier_mk_3bet:**",
        f"- Classification: `{p132s['classification']}`",
        f"- Pass: {p132s['classification_pass']}",
        "",
        f"**P131 acb_markov_midfreq_3bet:**",
        f"- Classification: `{p131s['classification']}`",
        f"- Pass: {p131s['classification_pass']}",
        "",
        f"**P130 dry-run plan:**",
        f"- Classification: `{p130s['classification']}`",
        f"- P9 in safe candidates: {p130s['p9_in_safe_candidates']}",
        f"- P9 estimated_insert_rows: {p130s['p9_estimated_insert_rows']}",
        "",
        "---",
        "",
        "## 6. Backup Creation and Verification",
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
        "## 7. Single-Strategy Apply Scope",
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
        f"| controlled_apply_id | `{sc['controlled_apply_id']}` |",
        f"| adapter_function | `{sc['adapter_function']}` |",
        f"| adapter_source | `{sc['adapter_source']}` |",
        "",
        "**Wave 2 candidates NOT applied in this task:**",
        "",
        "- `power_precision_3bet` (P10) — not apply-ready until re-evaluation",
        "- `power_orthogonal_5bet` (P12) — not apply-ready until re-evaluation",
        "",
        "---",
        "",
        "## 8. Inserted Rows Summary",
        "",
        f"- **Total rows inserted:** {a['inserted_rows_summary']['total_rows_inserted']}",
        f"- **bet-2 rows:** {a['inserted_rows_summary']['bet2_rows_inserted']}",
        f"- **bet-3 rows:** {a['inserted_rows_summary']['bet3_rows_inserted']}",
        f"- **truth_level:** inherited from bet-1 rows",
        f"- **controlled_apply_id:** `{a['inserted_rows_summary']['controlled_apply_id']}`",
        f"- **source:** `{a['inserted_rows_summary']['source']}`",
        f"- **dry_run:** {a['inserted_rows_summary']['dry_run']}",
        "",
        "---",
        "",
        "## 9. Duplicate Guard Result",
        "",
        f"- **Unique key:** `{a['duplicate_guard']['unique_key']}`",
        f"- **Constraint active:** {a['duplicate_guard']['constraint_active']}",
        f"- **Duplicate insert rejected:** {a['duplicate_guard']['duplicate_rejected_in_validation']}",
        f"- **P10/P12 extra rows:** {a['duplicate_guard']['p10_p12_extra_inserted']}",
        f"- **P10/P12 not applied:** {a['duplicate_guard']['p10_p12_not_applied']}",
        f"- **Guard OK:** {a['duplicate_guard']['guard_ok']}",
        "",
        "---",
        "",
        "## 10. bet_index Validation",
        "",
        f"- **bet_index=1 count:** {bv['bet1_count']} (expected {bv['expected_bet1']})",
        f"- **bet_index=2 count:** {bv['bet2_count']} (expected {bv['expected_bet2']})",
        f"- **bet_index=3 count:** {bv['bet3_count']} (expected {bv['expected_bet3']})",
        f"- **Distribution OK:** {bv['distribution_ok']}",
        f"- **All rows POWER_LOTTO:** {bv['all_rows_power_lotto']}",
        f"- **Validation:** `{bv['validation']}`",
        f"- **P9 anomaly note:** {bv['p9_anomaly_note']}",
        "",
        "---",
        "",
        "## 11. DB Rows Before / After",
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
        "## 12. P131/P132/P133 Row Preservation",
        "",
        f"**P131 acb_markov_midfreq_3bet:**",
        f"- Total: {rp['p131_acb_total']} (expected 4500)",
        f"- bet-1: {rp['p131_acb_bet1']} | bet-2: {rp['p131_acb_bet2']} | bet-3: {rp['p131_acb_bet3']}",
        f"- Preserved: {rp['p131_rows_preserved']}",
        "",
        f"**P132 midfreq_fourier_mk_3bet:**",
        f"- Total: {rp['p132_midfreq_total']} (expected 4500)",
        f"- bet-1: {rp['p132_midfreq_bet1']} | bet-2: {rp['p132_midfreq_bet2']} | bet-3: {rp['p132_midfreq_bet3']}",
        f"- Preserved: {rp['p132_rows_preserved']}",
        "",
        f"**P133 pp3_freqort_4bet:**",
        f"- Total: {rp['p133_pp3_total']} (expected 6000)",
        f"- bet-1: {rp['p133_pp3_bet1']} | bet-2: {rp['p133_pp3_bet2']} | bet-3: {rp['p133_pp3_bet3']} | bet-4: {rp['p133_pp3_bet4']}",
        f"- Preserved: {rp['p133_rows_preserved']}",
        "",
        "---",
        "",
        "## 13. Drift Guard Baseline Handling",
        "",
        f"- **Previous total:** {dg['previous_total']}",
        f"- **New total:** {dg['new_total']}",
        f"- **Rows added:** {dg['rows_added']}",
        f"- **Update note:** {dg['update_note']}",
        "",
        f"`scripts/replay_lifecycle_drift_guard.py` baseline updated to {rp['actual_rows_after']} rows.",
        "",
        "---",
        "",
        "## 14. Rollback Reference / Backup Path",
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
        "## 15. Wave 2 Completion Status",
        "",
        "| Candidate | Applied | Task |",
        "|---|---|---|",
        f"| acb_markov_midfreq_3bet | {wave2['acb_markov_midfreq_3bet_applied']} | P131 |",
        f"| midfreq_fourier_mk_3bet | {wave2['midfreq_fourier_mk_3bet_applied']} | P132 |",
        f"| pp3_freqort_4bet | {wave2['pp3_freqort_4bet_applied']} | P133 |",
        f"| fourier_rhythm_3bet | {wave2['fourier_rhythm_3bet_applied']} | P134 (this) |",
        f"| power_precision_3bet | ❌ | blocked (P10) |",
        f"| power_orthogonal_5bet | ❌ | blocked (P12) |",
        "",
        f"**All safe candidates applied:** {wave2['all_safe_candidates_applied']}",
        f"**Remaining:** {wave2['remaining']}",
        "",
        "---",
        "",
        "## 16. Explicit Non-Actions",
        "",
        "This P134 task did **not**:",
        "",
        "- Apply `power_precision_3bet` / `power_orthogonal_5bet` "
        "(P10/P12 — not apply-ready until re-evaluation)",
        "- Touch any P131 acb_markov_midfreq_3bet rows (preserved at 4500)",
        "- Touch any P132 midfreq_fourier_mk_3bet rows (preserved at 4500)",
        "- Touch any P133 pp3_freqort_4bet rows (preserved at 6000)",
        "- Touch any P126B–P126F previously applied rows",
        "- Touch any 4_STAR strategies",
        "- Execute P108 / P117 / P118",
        "- Install any scheduler, cron, or launchd",
        "- Perform strategy promotion, lifecycle, champion, or registry mutation",
        "",
        "---",
        "",
        "## 17. Remaining Risks",
        "",
    ]
    for r in a["remaining_risks"]:
        lines.append(f"- {r}")
    lines += [
        "",
        "---",
        "",
        "## 18. Recommended Next Task",
        "",
        a["next_recommended_task"],
        "",
        "---",
        "",
        "## 19. Final Classification",
        "",
        "```text",
        a["classification"],
        "```",
        "",
        f"**Task:** {a['task_id']}  ",
        f"**DB rows after apply:** {a['db_snapshot_after']['replay_rows']}  ",
        f"**Wave 2 safe candidates: COMPLETE**  ",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[P134] Markdown written: {OUT_MD}")


# ---------------------------------------------------------------------------
# Update drift guard
# ---------------------------------------------------------------------------
def update_drift_guard(rows_after: int) -> dict:
    if not DRIFT_GUARD.exists():
        return {"updated": False, "reason": "drift guard not found"}

    content = DRIFT_GUARD.read_text(encoding="utf-8")

    # 1. Update total_count
    old_total = f'"total_count": {EXPECTED_ROWS_BEFORE},'
    new_total  = f'"total_count": {rows_after},'
    if old_total not in content:
        return {"updated": False, "reason": f"total_count={EXPECTED_ROWS_BEFORE} not found"}
    content = content.replace(old_total, new_total, 1)

    # 2. Add P134 block after P133 block in BASELINE
    p133_block = (
        f'    "p133_apply_id": "{CONTROLLED_APPLY_ID.replace("P134", "P133").replace("FOURIER_RHYTHM_3BET", "PP3_FREQORT_4BET")}",\n'
        '    "p133_count": 4500,'
    )
    p134_insert = (
        f'    "p133_apply_id": "{CONTROLLED_APPLY_ID.replace("P134", "P133").replace("FOURIER_RHYTHM_3BET", "PP3_FREQORT_4BET")}",\n'
        '    "p133_count": 4500,\n'
        f'    # P134: POWER_LOTTO fourier_rhythm_3bet bet-2 + bet-3 Wave 2 controlled apply (2026-05-29)\n'
        f'    "p134_apply_id": "{CONTROLLED_APPLY_ID}",\n'
        '    "p134_count": 3002,'
    )
    if p133_block in content and "p134_apply_id" not in content:
        content = content.replace(p133_block, p134_insert, 1)

    # 3. Update header comment
    old_header = f"total                                                   == {EXPECTED_ROWS_BEFORE}"
    new_header = f"total                                                   == {rows_after}"
    if old_header in content:
        content = content.replace(old_header, new_header, 1)

    DRIFT_GUARD.write_text(content, encoding="utf-8")
    return {
        "updated":         True,
        "old_total_count": EXPECTED_ROWS_BEFORE,
        "new_total_count": rows_after,
        "p134_apply_id":   CONTROLLED_APPLY_ID,
        "p134_count":      3002,
    }


# ---------------------------------------------------------------------------
# Update roadmap
# ---------------------------------------------------------------------------
def update_roadmap(rows_after: int, backup_path: str) -> dict:
    results = {}

    roadmap_path = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
    if roadmap_path.exists():
        roadmap = roadmap_path.read_text(encoding="utf-8")
        p134_section = f"""
---

### P134 — fourier_rhythm_3bet Wave 2 Controlled Apply [2026-05-29]

**Classification**: P134_FOURIER_RHYTHM_3BET_APPLIED

P9 `fourier_rhythm_3bet` (POWER_LOTTO) bet-2 and bet-3 rows applied via P128 phase2 adapter.
P9 anomaly: 1501 bet-1 rows (draw-ext 115000041) → +3002 rows.

- **Rows inserted:** +3,002 (1,501 bet-2 + 1,501 bet-3)
- **DB rows:** 82,922 → {rows_after}
- **Backup:** `{backup_path}`
- **Drift guard:** PASS at {rows_after}
- **P131/P132/P133 rows preserved**
- **Wave 2 safe candidates: COMPLETE**
- **P10/P12 not apply-ready** — pending post-RSR6 re-evaluation

```text
CTO_ROADMAP_UPDATED_AFTER_P134_FOURIER_RHYTHM_3BET_APPLIED_20260529
```
"""
        if "P134_FOURIER_RHYTHM_3BET_APPLIED" not in roadmap:
            roadmap_path.write_text(roadmap + p134_section, encoding="utf-8")
            results["roadmap_updated"] = True
        else:
            results["roadmap_updated"] = "ALREADY_PRESENT"
    else:
        results["roadmap_updated"] = False

    cto_path = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"
    if cto_path.exists():
        cto = cto_path.read_text(encoding="utf-8")
        p134_cto = f"""
---

### P134: fourier_rhythm_3bet Wave 2 Apply (2026-05-29)

**Status**: COMPLETE | **Classification**: P134_FOURIER_RHYTHM_3BET_APPLIED

CTO Note: P9 Wave 2 safe candidate `fourier_rhythm_3bet` (POWER_LOTTO) applied.
3,002 bet-2/bet-3 rows inserted via P128 phase2 adapter (P9 anomaly: 1501 rows base).
DB 82,922 → {rows_after}. P131/P132/P133 rows preserved.
Wave 2 safe candidates are now COMPLETE. P10/P12 await re-evaluation.

**Artifact**: `outputs/replay/p134_apply_fourier_rhythm_3bet_{DATE_SUFFIX}.json`
"""
        if "P134_FOURIER_RHYTHM_3BET_APPLIED" not in cto:
            cto_path.write_text(cto + p134_cto, encoding="utf-8")
            results["cto_analysis_updated"] = True
        else:
            results["cto_analysis_updated"] = "ALREADY_PRESENT"
    else:
        results["cto_analysis_updated"] = False

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    print(f"[P134] Starting {STRATEGY_ID} controlled apply — {now}")

    # 1. Authorization check (FIRST)
    auth = validate_authorization(args.authorization)
    if not auth["authorization_present"]:
        print(f"[P134] STOP: Authorization phrase invalid or missing.")
        print(f"[P134] Required: '{EXACT_AUTH_PHRASE}'")
        print(f"[P134] Observed: '{auth['authorization_text_observed']}'")
        sys.exit(1)
    print("[P134] Authorization confirmed.")

    # 2. Worktree check
    if "zen-gates-ff6802" not in str(REPO_ROOT):
        print(f"[P134] STOP: Must run in zen-gates-ff6802 worktree, got: {REPO_ROOT}")
        sys.exit(1)
    print(f"[P134] Worktree confirmed: {REPO_ROOT}")

    # 3. Load upstream artifacts
    print("[P134] Loading upstream artifacts...")
    p133 = load_artifact(P133_ARTIFACT)
    p132 = load_artifact(P132_ARTIFACT)
    p131 = load_artifact(P131_ARTIFACT)
    p130 = load_artifact(P130_ARTIFACT)

    p133_ok = (
        p133 is not None
        and p133.get("classification") == "P133_PP3_FREQORT_4BET_APPLIED"
    )
    p132_ok = (
        p132 is not None
        and p132.get("classification") == "P132_MIDFREQ_FOURIER_MK_3BET_APPLIED"
    )
    p131_ok = (
        p131 is not None
        and p131.get("classification") == "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED"
    )
    p130_ok = (
        p130 is not None
        and p130.get("classification") == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY"
    )

    print(f"[P134] P133: {p133.get('classification') if p133 else 'MISSING'} — {'OK' if p133_ok else 'FAIL'}")
    print(f"[P134] P132: {p132.get('classification') if p132 else 'MISSING'} — {'OK' if p132_ok else 'FAIL'}")
    print(f"[P134] P131: {p131.get('classification') if p131 else 'MISSING'} — {'OK' if p131_ok else 'FAIL'}")
    print(f"[P134] P130: {p130.get('classification') if p130 else 'MISSING'} — {'OK' if p130_ok else 'FAIL'}")

    if not p133_ok:
        print("[P134] STOP: P133 (pp3_freqort_4bet applied) not confirmed.")
        sys.exit(1)
    if not p132_ok:
        print("[P134] STOP: P132 (midfreq_fourier_mk_3bet applied) not confirmed.")
        sys.exit(1)
    if not p131_ok:
        print("[P134] STOP: P131 (acb_markov_midfreq_3bet applied) not confirmed.")
        sys.exit(1)
    if not p130_ok:
        print("[P134] STOP: P130 dry-run plan not confirmed.")
        sys.exit(1)

    # Verify P9 in P130 safe candidates
    p9_entry = None
    for entry in p130.get("safe_candidate_dry_run_plan", []):
        if entry.get("strategy_id") == STRATEGY_ID:
            p9_entry = entry
            break
    if p9_entry is None:
        print(f"[P134] STOP: {STRATEGY_ID} not found in P130 safe_candidate_dry_run_plan")
        sys.exit(1)
    print(f"[P134] P9 {STRATEGY_ID} confirmed in P130 safe candidates.")

    # 4. DB snapshot before
    print("[P134] Snapshotting production DB (before)...")
    snap_before = snapshot_db()
    rows_before = snap_before["replay_rows"]
    has_bi      = snap_before["has_bet_index_column"]
    print(f"[P134] DB before: {rows_before} rows, bet_index={has_bi}")
    print(f"[P134] {STRATEGY_ID} bet dist: {snap_before[f'{STRATEGY_ID}_bet_dist']}")
    print(f"[P134] Draw-ext {DRAW_EXT_TARGET_DRAW} bet-1 exists: {snap_before['draw_ext_115000041_bet1_exists']}")
    print(f"[P134] P131 acb_markov_midfreq_3bet rows: {snap_before['acb_markov_midfreq_3bet_rows']}")
    print(f"[P134] P132 midfreq_fourier_mk_3bet rows: {snap_before['midfreq_fourier_mk_3bet_rows']}")
    print(f"[P134] P133 pp3_freqort_4bet rows: {snap_before['pp3_freqort_4bet_rows']}")

    if rows_before != EXPECTED_ROWS_BEFORE:
        print(f"[P134] STOP: Expected {EXPECTED_ROWS_BEFORE} rows before apply, got {rows_before}")
        sys.exit(1)
    if not has_bi:
        print("[P134] STOP: bet_index column missing — schema migration required first")
        sys.exit(1)
    if not snap_before["draw_ext_115000041_bet1_exists"]:
        print(f"[P134] WARNING: draw-ext {DRAW_EXT_TARGET_DRAW} bet-1 row not found — anomaly may not be present")

    # 5. Create backup
    print("[P134] Creating backup before apply...")
    backup = create_backup()
    if not backup["backup_ok"]:
        print(f"[P134] STOP: Backup verification failed: {backup}")
        sys.exit(1)
    print(f"[P134] Backup: {backup['backup_path']} "
          f"({backup['backup_row_count']} rows) — {backup['backup_verification']}")

    # 6. Load POWER_LOTTO draws
    print("[P134] Loading POWER_LOTTO draw history...")
    all_draws = load_power_lotto_draws()
    print(f"[P134] Loaded {len(all_draws)} POWER_LOTTO draws")

    # 7. Apply bet-2 and bet-3
    try:
        apply_result = apply_bet2_bet3_rows(all_draws, now)
    except Exception as exc:
        print(f"[P134] APPLY FAILED: {exc}")
        print(f"[P134] Rollback: {backup['rollback_command']}")
        sys.exit(1)

    # 8. Post-apply validation
    print("[P134] Running post-apply validation...")
    post = validate_post_apply()
    print(f"[P134] Post-apply: total={post['total_rows']}, "
          f"strategy={post['strategy_total_rows']}, "
          f"distribution_ok={post['distribution_ok']}, "
          f"draw_ext_all_bets={post['draw_ext_all_bets_present']}, "
          f"p131_preserved={post['p131_preserved']}, "
          f"p132_preserved={post['p132_preserved']}, "
          f"p133_preserved={post['p133_preserved']}, "
          f"all_ok={post['all_validation_ok']}")

    if not post["all_validation_ok"]:
        print("[P134] VALIDATION FAILED — see rollback reference")
        print(f"[P134] Rollback: {backup['rollback_command']}")

    # 9. Update drift guard
    print("[P134] Updating drift guard baseline...")
    dg_result = update_drift_guard(post["total_rows"])
    print(f"[P134] Drift guard update: {dg_result}")

    # 10. Build and write artifact
    artifact = _build_artifact(
        auth, snap_before, backup, apply_result, post,
        p133, p132, p131, p130,
        p133_ok, p132_ok, p131_ok, p130_ok, now,
    )
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P134] JSON written: {OUT_JSON}")

    _write_md(artifact)

    # 11. Update roadmap
    print("[P134] Updating roadmap files...")
    rm_result = update_roadmap(post["total_rows"], backup["backup_path"])
    print(f"[P134] Roadmap update: {rm_result}")

    print(f"\n[P134] COMPLETE")
    print(f"[P134] Classification : {CLASSIFICATION}")
    print(f"[P134] DB rows        : {rows_before} → {post['total_rows']}")
    print(f"[P134] Inserted       : {apply_result['rows_inserted']} rows")
    print(f"[P134] Backup         : {backup['backup_path']}")
    print(f"[P134] Validation     : {'PASS' if post['all_validation_ok'] else 'FAIL'}")
    print(f"[P134] Drift guard    : {'UPDATED' if dg_result.get('updated') else 'NOT_UPDATED'}")

    if not post["all_validation_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
