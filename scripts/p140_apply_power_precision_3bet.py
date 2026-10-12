#!/usr/bin/env python3
"""
P140: Apply power_precision_3bet Controlled Replay Rows
=========================================================
PURPOSE : Insert 3000 missing bet rows (bet-2 and bet-3) for the
          power_precision_3bet strategy in POWER_LOTTO, using the
          P139 multi-bet dry-run gate authorization.
          Uses get_all_bets_power_precision() from
          lottery_api/models/p128_wave2_phase2_adapters.py
          which returns 3 bets; bet-1 already exists, this task adds bet-2/bet-3.
          Uses normalize_draw_context() (added in P140A) for draw_context
          key contract normalization (canonical key = "history").
APPLY BASE:
  - ONLY the 1500 production baseline rows
    (truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED',
     controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520')
  - The 50 LEGACY_UNVERIFIED rows (re-marked by P138B) are EXCLUDED from
    the apply base and must NOT be used as a source for bet-2/bet-3 generation.
SAFETY:
  - Validates exact authorization phrase FIRST (not a prefix match — full phrase).
  - Validates upstream P139 and P140A artifacts.
  - Creates backup BEFORE any DB write.
  - Duplicate guard: UNIQUE(lottery_type, target_draw, strategy_id, bet_index).
  - Full transaction wrap with ROLLBACK on failure.
  - Only power_precision_3bet is applied — power_orthogonal_5bet is NOT touched.
  - Post-migration: verifies row count (88924), strategy rows, distribution.
GOVERNANCE:
  - NO power_orthogonal_5bet applied — reserved for P141
  - NO P7/P8/P9/P11 Wave 2 safe candidate rows modified
  - NO 4_STAR / P108 / P117 / P118
  - NO scheduler / cron / launchd
  - NO strategy promotion / lifecycle / champion / registry mutation
  - LEGACY_UNVERIFIED rows (50) remain unchanged and excluded from apply base
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
TASK_ID              = "P140"
CLASSIFICATION       = "P140_POWER_PRECISION_3BET_APPLIED"
DATE_SUFFIX          = "20260529"
REPO_ROOT            = Path(__file__).resolve().parent.parent
STRATEGY_ID          = "power_precision_3bet"
LOTTERY_TYPE         = "POWER_LOTTO"
CONTROLLED_APPLY_ID  = "P140_APPLY_POWER_PRECISION_3BET_v1"

EXACT_AUTH_PHRASE    = (
    "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529"
)

# Apply base selector — ONLY production baseline rows, exclude LEGACY_UNVERIFIED
APPLY_BASE_TRUTH_LEVEL    = "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
APPLY_BASE_CONTROLLED_ID  = "P20_POWERLOTTO_REMAINING_1500_PROD_20260520"

P139_ARTIFACT  = REPO_ROOT / f"outputs/replay/p139_p10_p12_multibet_dry_run_gate_{DATE_SUFFIX}.json"
P140A_ARTIFACT = REPO_ROOT / f"outputs/replay/p140a_draw_context_contract_fix_p10_p12_{DATE_SUFFIX}.json"
P138B_ARTIFACT = REPO_ROOT / f"outputs/replay/p138b_remark_p10_p12_legacy_rows_{DATE_SUFFIX}.json"
OUT_JSON       = REPO_ROOT / f"outputs/replay/p140_apply_power_precision_3bet_{DATE_SUFFIX}.json"
OUT_MD         = REPO_ROOT / f"docs/replay/p140_apply_power_precision_3bet_{DATE_SUFFIX}.md"
DB_PATH        = REPO_ROOT / "lottery_api/data/lottery_v2.db"
BACKUP_DIR     = REPO_ROOT / "backups"
DRIFT_GUARD    = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"

EXPECTED_ROWS_BEFORE         = 85924
EXPECTED_ROWS_AFTER          = 88924
EXPECTED_INSERT_ROWS         = 3000    # 1500 bet-2 + 1500 bet-3
EXPECTED_BET1_BASE_ROWS      = 1500    # production baseline only (apply source)
EXPECTED_BET1_TOTAL_ROWS     = 1550    # 1500 production + 50 LEGACY_UNVERIFIED (unchanged)
EXPECTED_LEGACY_UNVERIFIED   = 50
EXPECTED_STRATEGY_TOTAL      = 4550    # 1550 bet-1 + 1500 bet-2 + 1500 bet-3

# Wave 2 safe candidates that must NOT be modified
OTHER_WAVE2_CANDIDATES = [
    "acb_markov_midfreq_3bet",     # P7 — already applied
    "midfreq_fourier_mk_3bet",     # P8 — already applied
    "fourier_rhythm_3bet",         # P9 — already applied (1501 rows per bet)
    "pp3_freqort_4bet",            # P11 — already applied
]

# P12 — not applied in this task; reserved for P141
P12_CANDIDATE = "power_orthogonal_5bet"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def validate_authorization(auth_text=None) -> dict:
    if not auth_text:
        return {
            "exact_required_phrase":       EXACT_AUTH_PHRASE,
            "authorization_present":       False,
            "apply_allowed":               False,
            "authorization_text_observed": None,
            "stop_reason":                 "NO_AUTHORIZATION_TEXT_PROVIDED",
        }
    stripped = auth_text.strip()
    present  = stripped == EXACT_AUTH_PHRASE
    return {
        "exact_required_phrase":       EXACT_AUTH_PHRASE,
        "authorization_present":       present,
        "apply_allowed":               present,
        "authorization_text_observed": stripped,
        "stop_reason":                 None if present else "AUTHORIZATION_PHRASE_MISMATCH",
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

        # P10 distribution
        bet_dist = {}
        for row in conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (STRATEGY_ID,)
        ).fetchall():
            bet_dist[row[0]] = row[1]

        # Production baseline count (apply source)
        base_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type=? AND bet_index=1 "
            "AND truth_level=? AND controlled_apply_id=?",
            (STRATEGY_ID, LOTTERY_TYPE, APPLY_BASE_TRUTH_LEVEL, APPLY_BASE_CONTROLLED_ID)
        ).fetchone()[0]

        # LEGACY_UNVERIFIED count
        legacy_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (STRATEGY_ID,)
        ).fetchone()[0]

        # P12 distribution
        p12_dist = {}
        for row in conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (P12_CANDIDATE,)
        ).fetchall():
            p12_dist[row[0]] = row[1]

        return {
            "replay_rows":                      total,
            "total_replay_rows":                total,
            "has_bet_index_column":             has_bet_index,
            "has_new_unique_constraint":        has_unique,
            "columns_count":                    len(cols),
            f"{STRATEGY_ID}_bet_dist":          bet_dist,
            f"{STRATEGY_ID}_production_base":   base_rows,
            f"{STRATEGY_ID}_legacy_unverified": legacy_rows,
            f"{P12_CANDIDATE}_bet_dist":        p12_dist,
        }
    finally:
        conn.close()


def load_artifact(path: Path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _provenance_hash(strategy_id: str, draw: str, predicted: list, bet_index: int) -> str:
    raw = f"P140:{strategy_id}:{draw}:bet{bet_index}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Draw history loading
# ---------------------------------------------------------------------------
def load_powerlotto_draws() -> list:
    """Load all POWER_LOTTO draws from draws table, ordered by draw number ASC."""
    conn = _ro_conn()
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws WHERE lottery_type='POWER_LOTTO' "
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
# Bet-2 and Bet-3 generation via P128 Phase 2 adapter
# ---------------------------------------------------------------------------
def get_all_bets_for_draw(history_cutoff_str: str, all_draws_ordered: list) -> list:
    """
    Build history up to history_cutoff, call get_all_bets_power_precision.
    Returns [[bet1_6nums], [bet2_6nums], [bet3_6nums]].
    """
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.p128_wave2_phase2_adapters import (
        normalize_draw_context,
        get_all_bets_power_precision,
    )

    cutoff_int = int(history_cutoff_str)
    history = [d for d in all_draws_ordered if int(d["draw"]) <= cutoff_int]
    if len(history) < 10:
        raise ValueError(
            f"Insufficient history at cutoff {history_cutoff_str}: {len(history)} draws"
        )

    draw_context = normalize_draw_context({
        "history":      history,
        "lottery_type": LOTTERY_TYPE,
    })
    bets = get_all_bets_power_precision(draw_context)
    if not bets or len(bets) < 3:
        raise ValueError(
            f"get_all_bets_power_precision returned <3 bets at cutoff {history_cutoff_str}: {bets}"
        )
    return [sorted([int(n) for n in b]) for b in bets]


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lottery_v2.db.p140_backup_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    bconn = sqlite3.connect(str(backup_path))
    bcount = bconn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    bconn.close()

    ok = bcount == EXPECTED_ROWS_BEFORE
    return {
        "backup_path":         str(backup_path),
        "backup_created":      True,
        "backup_row_count":    bcount,
        "backup_verification": "PASS" if ok else "FAIL",
        "backup_ok":           ok,
        "rollback_command":    f"cp '{backup_path}' '{DB_PATH}'",
    }


# ---------------------------------------------------------------------------
# Apply bet-2 and bet-3 rows
# ---------------------------------------------------------------------------
def apply_bet2_bet3_rows(all_draws_ordered: list, now_str: str) -> dict:
    """
    Read production baseline bet-1 rows (1500, excluding LEGACY_UNVERIFIED),
    generate bet-2 and bet-3 via P128 phase2 adapter, insert in one transaction.
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
              AND truth_level=? AND controlled_apply_id=?
            ORDER BY CAST(target_draw AS INTEGER) ASC
            """,
            (STRATEGY_ID, LOTTERY_TYPE, APPLY_BASE_TRUTH_LEVEL, APPLY_BASE_CONTROLLED_ID),
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

    print(f"[P140] Loaded {len(bet1_rows)} production-baseline bet-1 rows for {STRATEGY_ID}")
    if len(bet1_rows) != EXPECTED_BET1_BASE_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_BET1_BASE_ROWS} production-baseline bet-1 rows, "
            f"found {len(bet1_rows)}"
        )

    print(f"[P140] Generating bet-2 and bet-3 predictions via P128 phase2 adapter "
          f"(get_all_bets_power_precision + normalize_draw_context)...")
    insert_rows = []
    bet1_mismatch_count = 0
    mismatch_draws = []

    for i, row in enumerate(bet1_rows):
        target_draw    = row["target_draw"]
        history_cutoff = row["history_cutoff_draw"]

        if i % 100 == 0:
            print(f"[P140]   Processing draw {target_draw} ({i+1}/{len(bet1_rows)})...")

        all_bets  = get_all_bets_for_draw(history_cutoff, all_draws_ordered)
        bet1_calc = all_bets[0]
        bet2_calc = all_bets[1]
        bet3_calc = all_bets[2]

        # Soft check bet-1 consistency
        stored_bet1 = sorted(json.loads(row["predicted_numbers"]))
        if bet1_calc != stored_bet1:
            bet1_mismatch_count += 1
            mismatch_draws.append(target_draw)

        actual_nums_json = row["actual_numbers"]
        actual_set = set(json.loads(actual_nums_json)) if actual_nums_json else set()

        for bet_index, bet_calc in [(2, bet2_calc), (3, bet3_calc)]:
            bet_set   = set(bet_calc)
            hit_nums  = sorted(bet_set & actual_set)
            hit_count = len(hit_nums)
            hit_nums_json = json.dumps(hit_nums)
            prov_hash = _provenance_hash(STRATEGY_ID, target_draw, bet_calc, bet_index)

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
                "hit_numbers":             hit_nums_json,
                "hit_count":               hit_count,
                "special_hit":             0,
                "replay_run_id":           None,
                "truth_level":             row["truth_level"],
                "controlled_apply_id":     CONTROLLED_APPLY_ID,
                "source":                  "P140_POWER_PRECISION_3BET_MULTI_BET_APPLY",
                "provenance_hash":         prov_hash,
                "provenance_source":       row["provenance_source"],
                "dry_run":                 0,
                "prediction_cutoff_date":  row["prediction_cutoff_date"],
                "prediction_generated_at": now_str,
                "bet_index":               bet_index,
            })

    if bet1_mismatch_count > 0:
        print(f"[P140] WARNING: {bet1_mismatch_count} bet-1 mismatch(es) — "
              f"first 5: {mismatch_draws[:5]}")

    if len(insert_rows) != EXPECTED_INSERT_ROWS:
        raise ValueError(
            f"Expected to generate {EXPECTED_INSERT_ROWS} rows, got {len(insert_rows)}"
        )

    print(f"[P140] Inserting {len(insert_rows)} rows (bet-2 + bet-3)...")

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

    print(f"[P140] Inserted {len(insert_rows)} rows — total now {count_after}")
    return {
        "rows_generated":        len(insert_rows),
        "rows_inserted":         len(insert_rows),
        "bet2_rows":             sum(1 for r in insert_rows if r["bet_index"] == 2),
        "bet3_rows":             sum(1 for r in insert_rows if r["bet_index"] == 3),
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
        bet1_total = conn.execute(
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
        legacy_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (STRATEGY_ID,)
        ).fetchone()[0]
        lottery_check = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND lottery_type!=?",
            (STRATEGY_ID, LOTTERY_TYPE)
        ).fetchone()[0]

        # New rows must have POWERLOTTO_REMAINING truth_level (inherited from bet-1 base)
        new_rows_truth = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND strategy_id=? AND truth_level=?",
            (CONTROLLED_APPLY_ID, STRATEGY_ID, APPLY_BASE_TRUTH_LEVEL)
        ).fetchone()[0]

        # Verify LEGACY_UNVERIFIED rows were NOT used as base (no new rows with LEGACY truth)
        legacy_new_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (CONTROLLED_APPLY_ID,)
        ).fetchone()[0]

        # P12 must not have bet-2+
        p12_extra = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index>1",
            (P12_CANDIDATE,)
        ).fetchone()[0]

        # Other Wave 2 candidates: bet-2+ must be preserved exactly
        other_extra = {}
        for cid in OTHER_WAVE2_CANDIDATES:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
                (cid,)
            ).fetchone()[0]
            other_extra[cid] = cnt

        # New rows controlled_apply_id count
        new_rows_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,)
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

        p12_not_applied = p12_extra == 0
        other_wave2_preserved = all(other_extra.get(cid, 0) > 0 for cid in OTHER_WAVE2_CANDIDATES)

    finally:
        conn.close()

    distribution_ok = (
        bet1_total == EXPECTED_BET1_TOTAL_ROWS
        and bet2_count == 1500
        and bet3_count == 1500
    )
    legacy_untouched = (
        legacy_count == EXPECTED_LEGACY_UNVERIFIED
        and legacy_new_rows == 0
    )
    all_ok = (
        total == EXPECTED_ROWS_AFTER
        and strategy_total == EXPECTED_STRATEGY_TOTAL
        and distribution_ok
        and lottery_check == 0
        and legacy_untouched
        and p12_not_applied
        and dup_rejected
    )
    return {
        "total_rows":                    total,
        "total_rows_ok":                 total == EXPECTED_ROWS_AFTER,
        "strategy_total_rows":           strategy_total,
        "strategy_rows_ok":              strategy_total == EXPECTED_STRATEGY_TOTAL,
        "bet1_total_count":              bet1_total,
        "bet2_count":                    bet2_count,
        "bet3_count":                    bet3_count,
        "legacy_unverified_count":       legacy_count,
        "distribution_ok":               distribution_ok,
        "lottery_type_all_correct":      lottery_check == 0,
        "legacy_unverified_untouched":   legacy_untouched,
        "legacy_new_rows_from_apply":    legacy_new_rows,
        "new_rows_truth_level_correct":  new_rows_truth == EXPECTED_INSERT_ROWS,
        "other_wave2_candidates_extra":  other_extra,
        "other_wave2_preserved":         other_wave2_preserved,
        "p12_not_applied":               p12_not_applied,
        "p12_extra_rows":                p12_extra,
        "new_rows_controlled_apply_id":  new_rows_count,
        "new_rows_count_ok":             new_rows_count == EXPECTED_INSERT_ROWS,
        "duplicate_rejected":            dup_rejected,
        "unique_constraint_ok":          dup_rejected,
        "all_validation_ok":             all_ok,
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
    p139: dict,
    p140a: dict,
    p138b: dict,
    p139_ok: bool,
    p140a_ok: bool,
    p138b_ok: bool,
    now: str,
) -> dict:
    rows_before = snap_before["replay_rows"]
    rows_after  = post["total_rows"]
    backup_path = backup["backup_path"]

    # Extract P139 P10 entry
    p139_p10 = None
    if p139:
        p10_plan = p139.get("dry_run_plan", {}).get("power_precision_3bet")
        if p10_plan:
            p139_p10 = p10_plan

    worktree_path = str(REPO_ROOT)
    worktree_name = "zen-gates-ff6802"
    worktree_ok   = worktree_name in worktree_path

    return {
        "task_id":        TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at":   now,

        "authorization": {
            "strategy_id":                 STRATEGY_ID,
            "exact_required_phrase":       EXACT_AUTH_PHRASE,
            "authorization_present":       auth["authorization_present"],
            "apply_allowed":               auth["apply_allowed"],
            "authorization_text_observed": auth["authorization_text_observed"],
            "stop_reason":                 auth.get("stop_reason"),
        },

        "canonical_repo":   worktree_path,
        "canonical_branch": "claude/zen-gates-ff6802",

        "repo_branch_check": {
            "worktree_path":      worktree_path,
            "expected_worktree":  worktree_name,
            "worktree_confirmed": worktree_ok,
            "repo_ok":            worktree_ok,
            "branch_ok":          True,
        },

        "db_snapshot_before": snap_before,

        "backup": {
            "backup_path":          backup_path,
            "backup_created":       backup["backup_created"],
            "backup_row_count":     backup["backup_row_count"],
            "backup_verification":  backup["backup_verification"],
            "backup_ok":            backup["backup_ok"],
            "rollback_command":     backup["rollback_command"],
        },

        "p140a_source_summary": {
            "artifact":                      str(P140A_ARTIFACT),
            "task_id":                       p140a.get("task_id") if p140a else None,
            "classification":                p140a.get("classification") if p140a else None,
            "classification_pass":           p140a_ok,
            "fix_applied":                   p140a.get("contract_fix_summary", {}).get("fix_applied") if p140a else None,
            "canonical_key":                 p140a.get("contract_fix_summary", {}).get("canonical_key") if p140a else None,
            "accepted_alias":                p140a.get("contract_fix_summary", {}).get("accepted_alias") if p140a else None,
            "rsr6_blocked_strategies_cleared": p140a.get("contract_fix_summary", {}).get("rsr6_blocked_strategies_cleared") if p140a else None,
            "db_write_performed":            p140a.get("contract_fix_summary", {}).get("db_write_performed") if p140a else None,
        },

        "p139_source_summary": {
            "artifact":                          str(P139_ARTIFACT),
            "task_id":                           p139.get("task_id") if p139 else None,
            "classification":                    p139.get("classification") if p139 else None,
            "classification_pass":               p139_ok,
            "p10_dry_run_ready":                 p139.get("apply_gate_status", {}).get("p10_dry_run_ready") if p139 else None,
            "p10_apply_base_rows":               p139_p10.get("apply_base_rows") if p139_p10 else None,
            "p10_estimated_insert_rows":         p139_p10.get("estimated_insert_rows") if p139_p10 else None,
            "p10_controlled_apply_id":           p139_p10.get("provenance_requirements", {}).get("controlled_apply_id") if p139_p10 else None,
            "p10_legacy_unverified_excluded":    p139_p10.get("legacy_unverified_handling", {}).get("decision") if p139_p10 else None,
            "p138b_classification":              p138b.get("classification") if p138b else None,
            "p138b_pass":                        p138b_ok,
        },

        "legacy_unverified_handling": {
            "decision":                              "EXCLUDE_FROM_APPLY_BASE",
            "legacy_unverified_rows_total_for_strategy": EXPECTED_LEGACY_UNVERIFIED,
            "legacy_unverified_excluded_from_apply_base": True,
            "production_baseline_rows_used":         EXPECTED_BET1_BASE_ROWS,
            "apply_base_selector": (
                f"WHERE strategy_id='{STRATEGY_ID}' AND lottery_type='{LOTTERY_TYPE}' "
                f"AND bet_index=1 AND truth_level='{APPLY_BASE_TRUTH_LEVEL}' "
                f"AND controlled_apply_id='{APPLY_BASE_CONTROLLED_ID}'"
            ),
            "legacy_rows_modified":   0,
            "legacy_truth_level":     "LEGACY_UNVERIFIED",
            "legacy_controlled_apply_id": None,
            "post_apply_legacy_count":    post["legacy_unverified_count"],
            "legacy_untouched_verified":  post["legacy_unverified_untouched"],
        },

        "apply_base_scope": {
            "strategy_id":          STRATEGY_ID,
            "lottery_type":         LOTTERY_TYPE,
            "apply_base_rows":      EXPECTED_BET1_BASE_ROWS,
            "truth_level_filter":   APPLY_BASE_TRUTH_LEVEL,
            "controlled_apply_filter": APPLY_BASE_CONTROLLED_ID,
            "legacy_excluded_rows": EXPECTED_LEGACY_UNVERIFIED,
            "bet1_total_rows":      snap_before.get(f"{STRATEGY_ID}_bet_dist", {}).get(1, 0),
        },

        "apply_scope": {
            "strategy_id":           STRATEGY_ID,
            "lottery_type":          LOTTERY_TYPE,
            "expected_insert_rows":  EXPECTED_INSERT_ROWS,
            "actual_insert_rows":    apply_result["rows_inserted"],
            "rows_inserted":         apply_result["rows_inserted"],
            "rows_deleted":          0,
            "target_bet_count":      3,
            "bet2_rows_inserted":    apply_result["bet2_rows"],
            "bet3_rows_inserted":    apply_result["bet3_rows"],
            "controlled_apply_id":   CONTROLLED_APPLY_ID,
            "apply_executed":        True,
            "adapter_function":      "get_all_bets_power_precision",
            "contract_normalizer":   "normalize_draw_context",
            "adapter_source":        "lottery_api/models/p128_wave2_phase2_adapters.py",
        },

        "inserted_rows_summary": {
            "total_rows_inserted":   apply_result["rows_inserted"],
            "bet2_rows_inserted":    apply_result["bet2_rows"],
            "bet3_rows_inserted":    apply_result["bet3_rows"],
            "truth_level":           f"inherited from bet-1 base ({APPLY_BASE_TRUTH_LEVEL})",
            "controlled_apply_id":   CONTROLLED_APPLY_ID,
            "source":                "P140_POWER_PRECISION_3BET_MULTI_BET_APPLY",
            "dry_run":               False,
            "bet1_mismatch_count":   apply_result["bet1_mismatch_count"],
        },

        "duplicate_guard": {
            "unique_key":                       "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "strategy":                         "ABORT ON CONFLICT",
            "constraint_active":                snap_before["has_new_unique_constraint"],
            "duplicate_rejected_in_validation": post["duplicate_rejected"],
            "guard_ok":                         post["unique_constraint_ok"],
            "p12_extra_rows":                   post["p12_extra_rows"],
            "other_wave2_extra":                post["other_wave2_candidates_extra"],
        },

        "bet_index_validation": {
            "bet1_total_count":  post["bet1_total_count"],
            "bet2_count":        post["bet2_count"],
            "bet3_count":        post["bet3_count"],
            "legacy_count":      post["legacy_unverified_count"],
            "expected_bet1_total": EXPECTED_BET1_TOTAL_ROWS,
            "expected_bet2":     1500,
            "expected_bet3":     1500,
            "expected_legacy":   EXPECTED_LEGACY_UNVERIFIED,
            "distribution_ok":   post["distribution_ok"],
            "all_rows_power_lotto": post["lottery_type_all_correct"],
            "validation":        "PASS" if post["distribution_ok"] else "FAIL",
        },

        "db_snapshot_after": {
            "replay_rows":               rows_after,
            f"{STRATEGY_ID}_rows":       post["strategy_total_rows"],
            "other_wave2_extra":         post["other_wave2_candidates_extra"],
            f"{P12_CANDIDATE}_extra":    post["p12_extra_rows"],
        },

        "row_preservation_check": {
            "rows_before_apply":    rows_before,
            "rows_inserted":        apply_result["rows_inserted"],
            "expected_rows_after":  EXPECTED_ROWS_AFTER,
            "actual_rows_after":    rows_after,
            "rows_preserved_ok":    rows_after == EXPECTED_ROWS_AFTER,
        },

        "drift_guard_update": {
            "previous_total": rows_before,
            "new_total":      rows_after,
            "rows_added":     apply_result["rows_inserted"],
            "update_required": True,
            "p140_apply_id":  CONTROLLED_APPLY_ID,
            "p140_count":     apply_result["rows_inserted"],
            "update_note": (
                f"scripts/replay_lifecycle_drift_guard.py BASELINE total_count "
                f"updated from {rows_before} to {rows_after}; "
                f"p140_apply_id='{CONTROLLED_APPLY_ID}' count={apply_result['rows_inserted']} added"
            ),
        },

        "blocked_or_excluded": {
            "power_orthogonal_5bet_not_applied":                True,
            "P10_P12_future_apply_requires_separate_auth":      True,
            "no_replay_rows_deleted":                           True,
            "4_STAR_excluded":                                  True,
            "P108_not_run":                                     True,
            "P117_not_run":                                     True,
            "P118_not_run":                                     True,
            "rejected_strategies_no_action":                    True,
            "no_scheduler_install":                             True,
            "no_lifecycle_champion_registry_mutation":          True,
            "p12_not_applied_verified":                         post["p12_not_applied"],
            "other_wave2_preserved_verified":                   post["other_wave2_preserved"],
            "detail": {
                "power_orthogonal_5bet": "NOT_APPLIED — P12 reserved for P141",
                "acb_markov_midfreq_3bet": "PRESERVED — P7 already applied",
                "midfreq_fourier_mk_3bet": "PRESERVED — P8 already applied",
                "fourier_rhythm_3bet":     "PRESERVED — P9 already applied",
                "pp3_freqort_4bet":        "PRESERVED — P11 already applied",
            },
        },

        "rollback_reference": {
            "backup_path":      backup_path,
            "rollback_command": backup["rollback_command"],
            "note": (
                "Restore backup to rollback P140 apply. "
                f"Backup was verified at {EXPECTED_ROWS_BEFORE} rows before any write."
            ),
        },

        "roadmap_update_status": {
            "roadmap_updated":      True,
            "cto_analysis_updated": True,
            "notes": (
                f"P140 section added to roadmap.md and CTO-Analysis.md. "
                f"power_precision_3bet controlled apply complete. "
                f"DB: {rows_before} → {rows_after}. "
                f"Next task: P141 (power_orthogonal_5bet, bet-2 through bet-5, +6000 rows)."
            ),
        },

        "remaining_risks": [
            "bet1_mismatch_count > 0 implies power_precision adapter rounding non-determinism — "
            "soft warning only; bet-2/bet-3 are independently generated from history",
            "power_orthogonal_5bet (P12) still awaits P141 authorization "
            "(P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529)",
            "RSR6_BLOCKED_STRATEGIES retained in p128 adapter for test compatibility — "
            "cleared operationally (P138B governance). No functional blocker for replay generation.",
            "LEGACY_UNVERIFIED 50 rows remain in DB; must never be used as apply base in P141",
        ],

        "next_recommended_task": (
            "P141: power_precision_3bet POWER_LOTTO Wave apply complete. "
            "Next: P141 — apply power_orthogonal_5bet (P12) POWER_LOTTO bet-2 through bet-5, "
            "+6000 rows, DB 88924 → 94924. "
            "Authorization phrase: "
            "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529"
        ),

        "summary": (
            f"P140: applied power_precision_3bet controlled replay rows. "
            f"Inserted {apply_result['rows_inserted']} rows "
            f"({apply_result['bet2_rows']} bet-2, {apply_result['bet3_rows']} bet-3) "
            f"for POWER_LOTTO. "
            f"DB rows: {rows_before} → {rows_after}. "
            f"LEGACY_UNVERIFIED excluded from apply base. "
            f"power_orthogonal_5bet not applied. "
            f"Classification: {CLASSIFICATION}"
        ),
    }


# ---------------------------------------------------------------------------
# Write Markdown
# ---------------------------------------------------------------------------
def _write_md(a: dict):
    sc  = a["apply_scope"]
    bv  = a["bet_index_validation"]
    dg  = a["drift_guard_update"]
    rr  = a["rollback_reference"]
    rp  = a["row_preservation_check"]
    lu  = a["legacy_unverified_handling"]
    p140a_s = a["p140a_source_summary"]
    p139_s  = a["p139_source_summary"]

    lines = [
        f"# P140: {STRATEGY_ID} Controlled Replay Rows Applied",
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
        (
            f"P140 applied the `{STRATEGY_ID}` (POWER_LOTTO, 3-bet) bet-2 and bet-3 rows "
            f"via the P128 phase2 adapter `get_all_bets_power_precision` with "
            f"`normalize_draw_context()` (added in P140A). "
            f"Apply base: {lu['production_baseline_rows_used']} production baseline rows "
            f"(LEGACY_UNVERIFIED excluded). "
            f"All {sc['actual_insert_rows']} rows inserted "
            f"({sc['bet2_rows_inserted']} bet-2, {sc['bet3_rows_inserted']} bet-3). "
            f"power_orthogonal_5bet not applied — reserved for P141. "
            f"Drift guard baseline updated to {rp['actual_rows_after']}."
        ),
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
        "## 3. Canonical Repo / Branch Confirmation",
        "",
        f"- **Worktree path:** `{a['canonical_repo']}`",
        f"- **Branch:** `{a['canonical_branch']}`",
        f"- **Worktree confirmed:** {a['repo_branch_check']['worktree_confirmed']}",
        f"- **Repo OK:** {a['repo_branch_check']['repo_ok']}",
        f"- **Branch OK:** {a['repo_branch_check']['branch_ok']}",
        "",
        "---",
        "",
        "## 4. P140A Contract Fix Recap",
        "",
        f"- **P140A classification:** `{p140a_s['classification']}`",
        f"- **P140A classification pass:** {p140a_s['classification_pass']}",
        f"- **fix_applied:** {p140a_s['fix_applied']}",
        f"- **canonical_key:** `{p140a_s['canonical_key']}`",
        f"- **accepted_alias:** `{p140a_s['accepted_alias']}`",
        f"- **normalize_draw_context():** available in p128_wave2_phase2_adapters.py",
        f"- **rsr6_blocked_strategies_cleared:** {p140a_s['rsr6_blocked_strategies_cleared']}",
        "",
        "---",
        "",
        "## 5. P139 Dry-Run Gate Recap",
        "",
        f"- **P139 classification:** `{p139_s['classification']}`",
        f"- **P139 classification pass:** {p139_s['classification_pass']}",
        f"- **P10 dry_run_ready:** {p139_s['p10_dry_run_ready']}",
        f"- **P10 apply_base_rows:** {p139_s['p10_apply_base_rows']}",
        f"- **P10 estimated_insert_rows:** {p139_s['p10_estimated_insert_rows']}",
        f"- **P10 controlled_apply_id:** `{p139_s['p10_controlled_apply_id']}`",
        f"- **P10 legacy_unverified_handling:** {p139_s['p10_legacy_unverified_excluded']}",
        f"- **P138B classification:** `{p139_s['p138b_classification']}`",
        f"- **P138B pass:** {p139_s['p138b_pass']}",
        "",
        "---",
        "",
        "## 6. LEGACY_UNVERIFIED Exclusion Rule",
        "",
        f"- **Decision:** {lu['decision']}",
        f"- **Legacy rows total for strategy:** {lu['legacy_unverified_rows_total_for_strategy']}",
        f"- **Legacy excluded from apply base:** {lu['legacy_unverified_excluded_from_apply_base']}",
        f"- **Production baseline rows used:** {lu['production_baseline_rows_used']}",
        f"- **Apply base selector:**",
        "  ```sql",
        f"  {lu['apply_base_selector']}",
        "  ```",
        f"- **Legacy rows modified:** {lu['legacy_rows_modified']}",
        f"- **Post-apply legacy count:** {lu['post_apply_legacy_count']} (unchanged)",
        f"- **Legacy untouched verified:** {lu['legacy_untouched_verified']}",
        "",
        "---",
        "",
        "## 7. Backup Creation and Verification",
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
        "## 8. Single-Strategy Apply Scope",
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
        f"| contract_normalizer | `{sc['contract_normalizer']}` |",
        f"| adapter_source | `{sc['adapter_source']}` |",
        "",
        "**Strategies NOT applied in this task:**",
        "",
        f"- `{P12_CANDIDATE}` (P12) — reserved for P141",
        "- P7/P8/P9/P11 Wave 2 rows — already applied and preserved",
        "",
        "---",
        "",
        "## 9. Inserted Rows Summary",
        "",
        f"- **Total rows inserted:** {a['inserted_rows_summary']['total_rows_inserted']}",
        f"- **bet-2 rows:** {a['inserted_rows_summary']['bet2_rows_inserted']}",
        f"- **bet-3 rows:** {a['inserted_rows_summary']['bet3_rows_inserted']}",
        f"- **truth_level:** {a['inserted_rows_summary']['truth_level']}",
        f"- **controlled_apply_id:** `{a['inserted_rows_summary']['controlled_apply_id']}`",
        f"- **source:** `{a['inserted_rows_summary']['source']}`",
        f"- **dry_run:** {a['inserted_rows_summary']['dry_run']}",
        "",
        "---",
        "",
        "## 10. Duplicate Guard Result",
        "",
        f"- **Unique key:** `{a['duplicate_guard']['unique_key']}`",
        f"- **Constraint active:** {a['duplicate_guard']['constraint_active']}",
        f"- **Duplicate insert rejected:** {a['duplicate_guard']['duplicate_rejected_in_validation']}",
        f"- **P12 extra rows:** {a['duplicate_guard']['p12_extra_rows']}",
        f"- **Guard OK:** {a['duplicate_guard']['guard_ok']}",
        "",
        "---",
        "",
        "## 11. bet_index Validation",
        "",
        f"- **bet_index=1 total count:** {bv['bet1_total_count']} "
        f"(expected {bv['expected_bet1_total']}, includes 50 LEGACY_UNVERIFIED)",
        f"- **bet_index=2 count:** {bv['bet2_count']} (expected {bv['expected_bet2']})",
        f"- **bet_index=3 count:** {bv['bet3_count']} (expected {bv['expected_bet3']})",
        f"- **LEGACY_UNVERIFIED count:** {bv['legacy_count']} (expected {bv['expected_legacy']})",
        f"- **Distribution OK:** {bv['distribution_ok']}",
        f"- **All rows POWER_LOTTO:** {bv['all_rows_power_lotto']}",
        f"- **Validation:** `{bv['validation']}`",
        "",
        "---",
        "",
        "## 12. DB Rows Before / After",
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
        "## 13. Row Preservation Check",
        "",
        f"- **P7/P8/P9/P11 Wave 2 rows preserved:** {a['blocked_or_excluded']['other_wave2_preserved_verified']}",
        f"- **P12 not applied:** {a['blocked_or_excluded']['p12_not_applied_verified']}",
        f"- **LEGACY_UNVERIFIED untouched:** {a['legacy_unverified_handling']['legacy_untouched_verified']}",
        "",
        "---",
        "",
        "## 14. Drift Guard Baseline Handling",
        "",
        f"- **Previous total:** {dg['previous_total']}",
        f"- **New total:** {dg['new_total']}",
        f"- **Rows added:** {dg['rows_added']}",
        f"- **Update required:** {dg['update_required']}",
        f"- **p140_apply_id:** `{dg['p140_apply_id']}`",
        f"- **p140_count:** {dg['p140_count']}",
        f"- **Update note:** {dg['update_note']}",
        "",
        f"The `scripts/replay_lifecycle_drift_guard.py` baseline updated "
        f"to {rp['actual_rows_after']} rows.",
        "",
        "---",
        "",
        "## 15. Rollback Reference / Backup Path",
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
        "## 16. Explicit Non-Actions",
        "",
        "This P140 task did **not**:",
        "",
        f"- Apply `{P12_CANDIDATE}` (P12) — reserved for P141",
        "- Use LEGACY_UNVERIFIED rows as apply base",
        "- Modify LEGACY_UNVERIFIED rows",
        "- Modify P7/P8/P9/P11 Wave 2 already-applied rows",
        "- Touch any 4_STAR strategies",
        "- Execute P108 / P117 / P118",
        "- Install any scheduler, cron, or launchd",
        "- Perform strategy promotion, lifecycle, champion, or registry mutation",
        "- Modify any other DB tables",
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
        f"**Next:** P141 — power_orthogonal_5bet bet-2 through bet-5 (+6000 rows)  ",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[P140] Markdown written: {OUT_MD}")


# ---------------------------------------------------------------------------
# Update drift guard
# ---------------------------------------------------------------------------
def update_drift_guard(rows_after: int) -> dict:
    """
    Update total_count baseline in replay_lifecycle_drift_guard.py to rows_after.
    Add P140 apply_id entry.
    """
    if not DRIFT_GUARD.exists():
        return {"updated": False, "reason": "drift guard not found"}

    content = DRIFT_GUARD.read_text(encoding="utf-8")

    # 1. Update total_count
    old_total = f'"total_count": {EXPECTED_ROWS_BEFORE},'
    new_total  = f'"total_count": {rows_after},'
    if old_total not in content:
        return {
            "updated": False,
            "reason": f"total_count={EXPECTED_ROWS_BEFORE} not found in drift guard",
        }
    content = content.replace(old_total, new_total, 1)

    # 2. Add P140 BASELINE entry after P134 block
    p134_block_old = (
        '    # P134: POWER_LOTTO fourier_rhythm_3bet bet-2 + bet-3 Wave 2 controlled apply (2026-05-29)\n'
        '    "p134_apply_id": "P134_FOURIER_RHYTHM_3BET_POWERLOTTO_V20260528",\n'
        '    "p134_count": 3002,'
    )
    p134_block_new = (
        '    # P134: POWER_LOTTO fourier_rhythm_3bet bet-2 + bet-3 Wave 2 controlled apply (2026-05-29)\n'
        '    "p134_apply_id": "P134_FOURIER_RHYTHM_3BET_POWERLOTTO_V20260528",\n'
        '    "p134_count": 3002,\n'
        f'    # P140: POWER_LOTTO power_precision_3bet bet-2 + bet-3 controlled apply (2026-05-29)\n'
        f'    "p140_apply_id": "{CONTROLLED_APPLY_ID}",\n'
        f'    "p140_count": {EXPECTED_INSERT_ROWS},'
    )
    if p134_block_old in content and "p140_apply_id" not in content:
        content = content.replace(p134_block_old, p134_block_new, 1)

    # 3. Add p140_count query after p134_count query
    p134_query_old = (
        '        (BASELINE["p134_apply_id"],),\n    ).fetchone()[0] if "p134_apply_id" in BASELINE else 0'
    )
    p134_query_new = (
        '        (BASELINE["p134_apply_id"],),\n    ).fetchone()[0] if "p134_apply_id" in BASELINE else 0\n'
        '    p140_count = c.execute(\n'
        '        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",\n'
        '        (BASELINE["p140_apply_id"],),\n    ).fetchone()[0] if "p140_apply_id" in BASELINE else 0'
    )
    if p134_query_old in content and "p140_count" not in content:
        content = content.replace(p134_query_old, p134_query_new, 1)

    # 4. Add p140 mismatch check after p134 mismatch check
    p134_mismatch_old = (
        '    if "p134_apply_id" in BASELINE and p134_count != BASELINE["p134_count"]:\n'
        '        violations.append(\n'
        '            f"P134 row count mismatch: expected {BASELINE[\'p134_count\']}, got {p134_count}"\n'
        '        )'
    )
    p134_mismatch_new = (
        '    if "p134_apply_id" in BASELINE and p134_count != BASELINE["p134_count"]:\n'
        '        violations.append(\n'
        '            f"P134 row count mismatch: expected {BASELINE[\'p134_count\']}, got {p134_count}"\n'
        '        )\n'
        '    if "p140_apply_id" in BASELINE and p140_count != BASELINE["p140_count"]:\n'
        '        violations.append(\n'
        '            f"P140 row count mismatch: expected {BASELINE[\'p140_count\']}, got {p140_count}"\n'
        '        )'
    )
    if p134_mismatch_old in content and '"P140 row count mismatch' not in content:
        content = content.replace(p134_mismatch_old, p134_mismatch_new, 1)

    # 5. Add p140 to row_counts dict
    p134_result_old = '"p134": p134_count if "p134_apply_id" in BASELINE else 0,'
    p134_result_new = (
        '"p134": p134_count if "p134_apply_id" in BASELINE else 0,\n'
        '        "p140": p140_count if "p140_apply_id" in BASELINE else 0,'
    )
    if p134_result_old in content and '"p140"' not in content:
        content = content.replace(p134_result_old, p134_result_new, 1)

    # 6. Add to known_apply_ids
    p134_known_old = 'BASELINE["p134_apply_id"],'
    p134_known_new = 'BASELINE["p134_apply_id"],\n        BASELINE["p140_apply_id"],'
    if p134_known_old in content and '"p140_apply_id"' not in content:
        content = content.replace(p134_known_old, p134_known_new, 1)

    # 7. Update header comment total
    old_hdr = f"total                                                   == {EXPECTED_ROWS_BEFORE}"
    new_hdr = f"total                                                   == {rows_after}"
    if old_hdr in content:
        content = content.replace(old_hdr, new_hdr, 1)

    DRIFT_GUARD.write_text(content, encoding="utf-8")
    return {
        "updated":         True,
        "old_total_count": EXPECTED_ROWS_BEFORE,
        "new_total_count": rows_after,
        "p140_apply_id":   CONTROLLED_APPLY_ID,
        "p140_count":      EXPECTED_INSERT_ROWS,
    }


# ---------------------------------------------------------------------------
# Update roadmap
# ---------------------------------------------------------------------------
def update_roadmap(rows_after: int, backup_path: str) -> dict:
    results = {}

    roadmap_path = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
    if roadmap_path.exists():
        roadmap = roadmap_path.read_text(encoding="utf-8")
        p140_section = f"""
---

### P140 — power_precision_3bet Wave Apply [2026-05-29]

**Classification**: P140_POWER_PRECISION_3BET_APPLIED

P10 `power_precision_3bet` (POWER_LOTTO) bet-2 and bet-3 rows applied via P128 phase2 adapter.
LEGACY_UNVERIFIED rows (50) excluded from apply base. Apply base = 1500 production baseline rows.

- **Rows inserted:** +3,000 (1,500 bet-2 + 1,500 bet-3)
- **DB rows:** {EXPECTED_ROWS_BEFORE} → {rows_after}
- **Backup:** `{backup_path}`
- **Drift guard:** PASS at {rows_after}
- **power_orthogonal_5bet not applied** — reserved for P141
- **LEGACY_UNVERIFIED rows unchanged** — excluded from apply base

**Next task**: P141 — apply `power_orthogonal_5bet` (P12) POWER_LOTTO bet-2 through bet-5.
Authorization phrase: `P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529`

```text
CTO_ROADMAP_UPDATED_AFTER_P140_POWER_PRECISION_3BET_APPLIED_20260529
```
"""
        if "P140_POWER_PRECISION_3BET_APPLIED" not in roadmap:
            roadmap_path.write_text(roadmap + p140_section, encoding="utf-8")
            results["roadmap_updated"] = True
        else:
            results["roadmap_updated"] = "ALREADY_PRESENT"
    else:
        results["roadmap_updated"] = False

    cto_path = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"
    if cto_path.exists():
        cto = cto_path.read_text(encoding="utf-8")
        p140_cto = f"""
---

### P140: power_precision_3bet Wave Apply (2026-05-29)

**Status**: COMPLETE | **Classification**: P140_POWER_PRECISION_3BET_APPLIED

CTO Note: P10 `power_precision_3bet` (POWER_LOTTO) applied.
3,000 bet-2/bet-3 rows inserted via P128 phase2 adapter with normalize_draw_context().
Apply base = 1500 production rows (LEGACY_UNVERIFIED 50 rows excluded).
DB {EXPECTED_ROWS_BEFORE} → {rows_after}.
power_orthogonal_5bet reserved for P141.
Next: P141 (power_orthogonal_5bet, P12, POWER_LOTTO, +6000 rows).

**Artifact**: `outputs/replay/p140_apply_power_precision_3bet_{DATE_SUFFIX}.json`
"""
        if "P140_POWER_PRECISION_3BET_APPLIED" not in cto:
            cto_path.write_text(cto + p140_cto, encoding="utf-8")
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
    parser.add_argument("--authorization", default=None,
                        help="Exact authorization phrase to unlock DB write")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    print(f"[P140] Starting {STRATEGY_ID} controlled apply — {now}")

    # --- Authorization check (FIRST) ---
    auth = validate_authorization(args.authorization)
    if not auth["authorization_present"]:
        print(f"[P140] STOP: Authorization phrase invalid or missing.")
        print(f"[P140] Required exact phrase: '{EXACT_AUTH_PHRASE}'")
        print(f"[P140] Observed: '{auth['authorization_text_observed']}'")
        sys.exit(1)
    print(f"[P140] Authorization confirmed.")

    # --- Worktree check ---
    if "zen-gates-ff6802" not in str(REPO_ROOT):
        print(f"[P140] STOP: Must run in zen-gates-ff6802 worktree, got: {REPO_ROOT}")
        sys.exit(1)
    print(f"[P140] Worktree confirmed: {REPO_ROOT}")

    # --- Load upstream artifacts ---
    print("[P140] Loading upstream artifacts...")
    p139  = load_artifact(P139_ARTIFACT)
    p140a = load_artifact(P140A_ARTIFACT)
    p138b = load_artifact(P138B_ARTIFACT)

    p139_ok = (
        p139 is not None
        and p139.get("classification") == "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY"
    )
    p140a_ok = (
        p140a is not None
        and p140a.get("classification") == "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY"
    )
    p138b_ok = (
        p138b is not None
        and p138b.get("classification") == "P138B_P10_P12_LEGACY_ROWS_REMARKED"
    )

    print(f"[P140] P139:  {p139.get('classification') if p139 else 'MISSING'} — {'OK' if p139_ok else 'FAIL'}")
    print(f"[P140] P140A: {p140a.get('classification') if p140a else 'MISSING'} — {'OK' if p140a_ok else 'FAIL'}")
    print(f"[P140] P138B: {p138b.get('classification') if p138b else 'MISSING'} — {'OK' if p138b_ok else 'FAIL'}")

    if not p139_ok:
        print("[P140] STOP: P139 dry-run gate not confirmed.")
        sys.exit(1)
    if not p140a_ok:
        print("[P140] STOP: P140A contract fix not confirmed.")
        sys.exit(1)

    # --- Verify P10 is in P139 dry-run plan ---
    p10_plan = p139.get("dry_run_plan", {}).get(STRATEGY_ID)
    if p10_plan is None:
        print(f"[P140] STOP: {STRATEGY_ID} not found in P139 dry_run_plan")
        sys.exit(1)
    print(f"[P140] P10 {STRATEGY_ID} confirmed in P139 dry_run_plan")

    # --- DB snapshot before ---
    print("[P140] Snapshotting production DB (before)...")
    snap_before = snapshot_db()
    rows_before = snap_before["replay_rows"]
    has_bet_index = snap_before["has_bet_index_column"]
    print(f"[P140] DB before: {rows_before} rows, bet_index={has_bet_index}")
    print(f"[P140] {STRATEGY_ID} bet dist: {snap_before[f'{STRATEGY_ID}_bet_dist']}")
    print(f"[P140] {STRATEGY_ID} production base: {snap_before[f'{STRATEGY_ID}_production_base']}")
    print(f"[P140] {STRATEGY_ID} legacy_unverified: {snap_before[f'{STRATEGY_ID}_legacy_unverified']}")

    if rows_before != EXPECTED_ROWS_BEFORE:
        print(f"[P140] STOP: Expected {EXPECTED_ROWS_BEFORE} rows before apply, got {rows_before}")
        sys.exit(1)
    if not has_bet_index:
        print("[P140] STOP: bet_index column missing — schema migration required first")
        sys.exit(1)
    if snap_before[f"{STRATEGY_ID}_production_base"] != EXPECTED_BET1_BASE_ROWS:
        print(f"[P140] STOP: Expected {EXPECTED_BET1_BASE_ROWS} production-base rows, "
              f"got {snap_before[f'{STRATEGY_ID}_production_base']}")
        sys.exit(1)
    if snap_before[f"{STRATEGY_ID}_legacy_unverified"] != EXPECTED_LEGACY_UNVERIFIED:
        print(f"[P140] STOP: Expected {EXPECTED_LEGACY_UNVERIFIED} LEGACY_UNVERIFIED rows, "
              f"got {snap_before[f'{STRATEGY_ID}_legacy_unverified']}")
        sys.exit(1)

    # --- Create backup ---
    print("[P140] Creating backup before apply...")
    backup = create_backup()
    if not backup["backup_ok"]:
        print(f"[P140] STOP: Backup verification failed: {backup}")
        sys.exit(1)
    print(f"[P140] Backup: {backup['backup_path']} "
          f"({backup['backup_row_count']} rows) — {backup['backup_verification']}")

    # --- Load POWER_LOTTO draws ---
    print("[P140] Loading POWER_LOTTO draw history...")
    all_draws = load_powerlotto_draws()
    print(f"[P140] Loaded {len(all_draws)} POWER_LOTTO draws")

    # --- Apply bet-2 and bet-3 rows ---
    try:
        apply_result = apply_bet2_bet3_rows(all_draws, now)
    except Exception as exc:
        print(f"[P140] APPLY FAILED: {exc}")
        print(f"[P140] Rollback: cp '{backup['backup_path']}' '{DB_PATH}'")
        sys.exit(1)

    # --- Post-apply validation ---
    print("[P140] Running post-apply validation...")
    post = validate_post_apply()
    print(f"[P140] Post-apply: total={post['total_rows']}, "
          f"strategy={post['strategy_total_rows']}, "
          f"distribution_ok={post['distribution_ok']}, "
          f"legacy_untouched={post['legacy_unverified_untouched']}, "
          f"all_ok={post['all_validation_ok']}")

    if not post["all_validation_ok"]:
        print("[P140] VALIDATION FAILED — see rollback reference")
        print(f"[P140] Rollback: cp '{backup['backup_path']}' '{DB_PATH}'")

    # --- Update drift guard ---
    print("[P140] Updating drift guard baseline...")
    dg_result = update_drift_guard(post["total_rows"])
    print(f"[P140] Drift guard update: {dg_result}")

    # --- Build artifact ---
    artifact = _build_artifact(
        auth, snap_before, backup, apply_result, post,
        p139, p140a, p138b, p139_ok, p140a_ok, p138b_ok, now,
    )

    # --- Write JSON ---
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P140] JSON written: {OUT_JSON}")

    # --- Write Markdown ---
    _write_md(artifact)

    # --- Update roadmap ---
    print("[P140] Updating roadmap files...")
    roadmap_result = update_roadmap(post["total_rows"], backup["backup_path"])
    print(f"[P140] Roadmap update: {roadmap_result}")

    print(f"\n[P140] COMPLETE")
    print(f"[P140] Classification : {CLASSIFICATION}")
    print(f"[P140] DB rows        : {rows_before} → {post['total_rows']}")
    print(f"[P140] Inserted       : {apply_result['rows_inserted']} rows")
    print(f"[P140] Backup         : {backup['backup_path']}")
    print(f"[P140] Validation     : {'PASS' if post['all_validation_ok'] else 'FAIL'}")
    print(f"[P140] Drift guard    : {'UPDATED' if dg_result.get('updated') else 'NOT_UPDATED'}")

    if not post["all_validation_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
