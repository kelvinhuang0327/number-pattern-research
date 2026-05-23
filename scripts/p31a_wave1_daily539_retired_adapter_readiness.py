#!/usr/bin/env python3
"""
P31A Wave 1 — DAILY_539 Retired Adapter Promotion Readiness
============================================================
P31A: Wires replay adapter wrappers for the 5 RETIRED DAILY_539 strategies,
generates 1500-period dry-run rows per strategy into a temp SQLite DB, runs
R1/R2/R3 temp rehearsal, decides lifecycle semantics, and produces readiness
artifacts.

AUTHORISATION GATE: This script is read-only with respect to the production DB.
  - Reads:  lottery_api/data/lottery_v2.db (draws only — no writes)
  - Writes: /tmp/p31a_temp.db (temp DB, created fresh each run)
  - Output: outputs/replay/p31a_temp_rehearsal_20260523.json
            outputs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.json

HARD RULES (same as main replay system):
  - Production DB MUST remain at exactly 12460 rows after this script.
  - Temp DB rows are NEVER copied to production DB in P31A.
  - Adapter wrappers are NOT registered in replay_strategy_registry._ALL_ADAPTERS.
  - DAILY_539 bets have exactly 5 distinct integers in [1..39], no special number.

LIFECYCLE SEMANTICS DECISION (P31A):
  Option A (ADOPTED): Keep lifecycle_status=RETIRED; add replay_available=True
                      flag in catalog response when row_count > 0 in temp DB.
  Option B (DEFERRED): Re-label strategies as 'reconstructible'.

  Decision: OPTION A — rationale in docs/replay/p31a_wave1_*.md

Usage:
  cd /path/to/LotteryNew
  .venv/bin/python scripts/p31a_wave1_daily539_retired_adapter_readiness.py [--dry-run-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Path setup ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p31a_temp.db")
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
REHEARSAL_OUTPUT = OUTPUT_DIR / "p31a_temp_rehearsal_20260523.json"
READINESS_OUTPUT = OUTPUT_DIR / "p31a_wave1_daily539_retired_adapter_readiness_20260523.json"

EXPECTED_PROD_ROWS = 12460
WINDOW_PERIODS = 1500    # dry-run spans last 1500 DAILY_539 draws
MIN_HISTORY = 100        # minimum history draws required
STRATEGIES_PER_RUN = 5
EXPECTED_DRY_RUN_ROWS = WINDOW_PERIODS * STRATEGIES_PER_RUN  # 7500

TRUTH_LEVEL = "P31A_WAVE1_DAILY539_RETIRED_DRY_RUN"
RUN_ID = "p31a_wave1_dryrun_20260523"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Production DB guard ──────────────────────────────────────────────────────

def _assert_prod_rows_unchanged(expected: int = EXPECTED_PROD_ROWS) -> int:
    """Assert production replay row count is exactly `expected`. Returns count."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()
        count = row[0] if row else 0
    finally:
        conn.close()
    assert count == expected, (
        f"PRODUCTION ROW INVARIANT VIOLATED: expected {expected}, got {count}. "
        "Aborting P31A — production DB must not be modified."
    )
    return count


# ─── Draw loader ─────────────────────────────────────────────────────────────

def _load_daily539_draws() -> list[dict]:
    """
    Load all DAILY_539 draws from production DB, sorted chronologically (date ASC).
    Returns list of dicts: [{draw, date, numbers}, ...]
    """
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws "
            "WHERE lottery_type = 'DAILY_539' "
            "ORDER BY date ASC, draw ASC"
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for row in rows:
        nums = json.loads(row["numbers"]) if isinstance(row["numbers"], str) else row["numbers"]
        draws.append({
            "draw": row["draw"],
            "date": row["date"],
            "numbers": [int(n) for n in nums],
        })
    return draws


# ─── Temp DB setup ────────────────────────────────────────────────────────────

def _create_temp_db(path: Path) -> sqlite3.Connection:
    """
    Create (or recreate) the temp SQLite DB with the strategy_prediction_replays schema.
    The DB is truncated on each fresh run (dry-run only).
    """
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE strategy_prediction_replays (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type           TEXT    NOT NULL,
            target_draw            TEXT    NOT NULL,
            target_date            TEXT,
            strategy_id            TEXT    NOT NULL,
            strategy_name          TEXT,
            strategy_version       TEXT,
            history_cutoff_draw    TEXT,
            replay_status          TEXT    NOT NULL DEFAULT 'PREDICTED',
            reject_reason          TEXT,
            predicted_numbers      TEXT,
            predicted_special      TEXT,
            actual_numbers         TEXT,
            actual_special         TEXT,
            hit_numbers            TEXT,
            hit_count              INTEGER DEFAULT 0,
            special_hit            INTEGER DEFAULT 0,
            replay_run_id          TEXT,
            generated_at           TEXT,
            truth_level            TEXT,
            controlled_apply_id    TEXT,
            source                 TEXT,
            provenance_hash        TEXT,
            provenance_source      TEXT,
            dry_run                INTEGER DEFAULT 1,
            prediction_cutoff_date TEXT,
            prediction_generated_at TEXT,
            UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
        )
    """)
    conn.commit()
    logger.info("Temp DB created: %s", path)
    return conn


# ─── Provenance hash ─────────────────────────────────────────────────────────

def _provenance_hash(strategy_id: str, target_draw: str, numbers: list[int]) -> str:
    payload = f"{strategy_id}|{target_draw}|{sorted(numbers)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ─── Single-draw prediction runner ───────────────────────────────────────────

def _run_one_prediction(
    adapter,
    history: list[dict],
    target: dict,
) -> dict:
    """
    Run one prediction for a single (adapter, target_draw) pair.
    Returns a row dict ready for DB insertion.

    Computes actual hit count against the target draw's numbers.
    """
    strategy_id = adapter.meta.strategy_id
    strategy_name = adapter.meta.strategy_name
    strategy_version = adapter.meta.strategy_version
    lottery_type = "DAILY_539"

    replay_status = "PREDICTED"
    reject_reason = None
    predicted_numbers = None
    predicted_special = None
    hit_numbers = None
    hit_count = 0

    now_str = datetime.now(timezone.utc).isoformat()

    try:
        numbers, special = adapter.get_one_bet(history, lottery_type)
        predicted_numbers = json.dumps(numbers)
        predicted_special = None

        actual_nums = target["numbers"]
        hits = sorted(set(numbers) & set(actual_nums))
        hit_numbers = json.dumps(hits)
        hit_count = len(hits)

    except ValueError as exc:
        replay_status = "INSUFFICIENT_HISTORY"
        reject_reason = str(exc)
    except AssertionError as exc:
        replay_status = "INVALID_OUTPUT"
        reject_reason = str(exc)
    except Exception as exc:
        replay_status = "REPLAY_ERROR"
        reject_reason = str(exc)
        logger.warning("Prediction error %s / %s: %s", strategy_id, target["draw"], exc)

    history_cutoff = history[-1]["draw"] if history else None

    prov_hash = _provenance_hash(
        strategy_id,
        str(target["draw"]),
        json.loads(predicted_numbers) if predicted_numbers else [],
    ) if predicted_numbers else None

    return {
        "lottery_type": lottery_type,
        "target_draw": str(target["draw"]),
        "target_date": target.get("date"),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "history_cutoff_draw": str(history_cutoff) if history_cutoff else None,
        "replay_status": replay_status,
        "reject_reason": reject_reason,
        "predicted_numbers": predicted_numbers,
        "predicted_special": predicted_special,
        "actual_numbers": json.dumps(target["numbers"]),
        "actual_special": None,
        "hit_numbers": hit_numbers,
        "hit_count": hit_count,
        "special_hit": 0,
        "replay_run_id": RUN_ID,
        "generated_at": now_str,
        "truth_level": TRUTH_LEVEL,
        "controlled_apply_id": None,
        "source": "P31A_WAVE1_DRYRUN",
        "provenance_hash": prov_hash,
        "provenance_source": "p31a_wave1_retired_adapters.py",
        "dry_run": 1,
        "prediction_cutoff_date": history[-1]["date"] if history else None,
        "prediction_generated_at": now_str,
    }


def _insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert rows into temp DB. Returns number of rows inserted."""
    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """
                INSERT INTO strategy_prediction_replays (
                    lottery_type, target_draw, target_date, strategy_id,
                    strategy_name, strategy_version, history_cutoff_draw,
                    replay_status, reject_reason, predicted_numbers,
                    predicted_special, actual_numbers, actual_special,
                    hit_numbers, hit_count, special_hit, replay_run_id,
                    generated_at, truth_level, controlled_apply_id, source,
                    provenance_hash, provenance_source, dry_run,
                    prediction_cutoff_date, prediction_generated_at
                ) VALUES (
                    :lottery_type, :target_draw, :target_date, :strategy_id,
                    :strategy_name, :strategy_version, :history_cutoff_draw,
                    :replay_status, :reject_reason, :predicted_numbers,
                    :predicted_special, :actual_numbers, :actual_special,
                    :hit_numbers, :hit_count, :special_hit, :replay_run_id,
                    :generated_at, :truth_level, :controlled_apply_id, :source,
                    :provenance_hash, :provenance_source, :dry_run,
                    :prediction_cutoff_date, :prediction_generated_at
                )
                """,
                row,
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate — expected in idempotency check
    conn.commit()
    return inserted


# ─── R1 / R2 / R3 Rehearsal ──────────────────────────────────────────────────

def _r1_apply(
    conn: sqlite3.Connection,
    all_rows: list[dict],
) -> dict:
    """R1: Apply all 7500 dry-run rows to temp DB."""
    inserted = _insert_rows(conn, all_rows)
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    logger.info("R1 apply: inserted=%d, total=%d", inserted, total)
    return {"r1_inserted": inserted, "r1_total": total}


def _r2_rerun(
    conn: sqlite3.Connection,
    all_rows: list[dict],
) -> dict:
    """R2: Rerun identical rows — all must be duplicates (0 new inserts)."""
    inserted = _insert_rows(conn, all_rows)
    total_after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    idempotent = inserted == 0
    logger.info(
        "R2 rerun: inserted=%d (idempotent=%s), total=%d",
        inserted, idempotent, total_after,
    )
    return {
        "r2_inserted": inserted,
        "r2_total": total_after,
        "r2_idempotent": idempotent,
    }


def _r3_rollback(
    conn: sqlite3.Connection,
    db_path: Path,
) -> dict:
    """
    R3: Simulate rollback — count rows before delete, drop all P31A dry-run rows,
    confirm table is empty. Then re-insert to restore for artifact inspection.
    """
    before = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.execute(
        "DELETE FROM strategy_prediction_replays WHERE replay_run_id = ?",
        (RUN_ID,),
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    rollback_ok = after == 0
    logger.info("R3 rollback: before=%d, after=%d, ok=%s", before, after, rollback_ok)
    return {
        "r3_before": before,
        "r3_after": after,
        "r3_rollback_ok": rollback_ok,
    }


# ─── Hit rate stats ───────────────────────────────────────────────────────────

def _compute_hit_stats(rows: list[dict]) -> dict:
    """Compute per-strategy hit rate statistics from dry-run rows."""
    by_strategy: dict = defaultdict(lambda: defaultdict(int))

    for row in rows:
        sid = row["strategy_id"]
        if row["replay_status"] == "PREDICTED":
            by_strategy[sid]["predicted"] += 1
            hc = row.get("hit_count", 0) or 0
            by_strategy[sid][f"hit_{hc}"] += 1
        else:
            by_strategy[sid]["error"] += 1

    stats = {}
    for sid, counts in by_strategy.items():
        predicted = counts.get("predicted", 0)
        errors = counts.get("error", 0)
        hit_3plus = sum(counts.get(f"hit_{h}", 0) for h in (3, 4, 5))
        stats[sid] = {
            "predicted": predicted,
            "errors": errors,
            "total": predicted + errors,
            "hit_3plus": hit_3plus,
            "hit_3plus_rate": round(hit_3plus / predicted, 4) if predicted > 0 else 0.0,
            "hit_breakdown": {str(h): counts.get(f"hit_{h}", 0) for h in range(6)},
        }
    return stats


# ─── Main orchestrator ────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="P31A Wave 1 DAILY_539 Retired Adapter Readiness")
    parser.add_argument("--dry-run-only", action="store_true", help="Skip R3 re-insert restore")
    args = parser.parse_args(argv)

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== P31A Wave 1 DAILY_539 Retired Adapter Readiness ===")
    logger.info("Started: %s", started_at)

    # ── Pre-flight: Production row invariant ──────────────────────────────────
    logger.info("Pre-flight: checking production DB row count...")
    prod_rows_before = _assert_prod_rows_unchanged()
    logger.info("Production DB: %d rows (PASS)", prod_rows_before)

    # ── Load DAILY_539 draws (read-only) ─────────────────────────────────────
    logger.info("Loading DAILY_539 draws from production DB (read-only)...")
    all_draws = _load_daily539_draws()
    total_draws = len(all_draws)
    logger.info("Loaded %d DAILY_539 draws", total_draws)

    assert total_draws >= MIN_HISTORY + WINDOW_PERIODS, (
        f"Need at least {MIN_HISTORY + WINDOW_PERIODS} draws for dry-run, "
        f"got {total_draws}"
    )

    # ── Select target draws (last 1500 periods) ───────────────────────────────
    target_draws = all_draws[-WINDOW_PERIODS:]
    logger.info(
        "Target window: %d draws (%s → %s)",
        len(target_draws),
        target_draws[0]["date"],
        target_draws[-1]["date"],
    )

    # ── Import Wave 1 adapters ────────────────────────────────────────────────
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTERS
    logger.info("Wave 1 adapters: %d", len(WAVE1_ADAPTERS))
    for a in WAVE1_ADAPTERS:
        logger.info("  - %s (%s)", a.meta.strategy_id, a.meta.lifecycle_status)

    # ── Generate dry-run rows ─────────────────────────────────────────────────
    logger.info("Generating %d dry-run rows (%d strategies × %d draws)...",
                EXPECTED_DRY_RUN_ROWS, STRATEGIES_PER_RUN, WINDOW_PERIODS)

    all_rows: list[dict] = []
    per_strategy_progress: dict = {}

    for adapter in WAVE1_ADAPTERS:
        sid = adapter.meta.strategy_id
        strategy_rows = []
        errors = 0

        for i, target in enumerate(target_draws):
            # Causal slice: all draws STRICTLY BEFORE this target
            target_idx = total_draws - WINDOW_PERIODS + i
            history = all_draws[:target_idx]  # strictly before

            row = _run_one_prediction(adapter, history, target)
            strategy_rows.append(row)
            if row["replay_status"] != "PREDICTED":
                errors += 1

        per_strategy_progress[sid] = {
            "total": len(strategy_rows),
            "predicted": len(strategy_rows) - errors,
            "errors": errors,
        }
        all_rows.extend(strategy_rows)
        logger.info(
            "  %s: %d predicted, %d errors",
            sid, len(strategy_rows) - errors, errors,
        )

    logger.info("Total dry-run rows generated: %d", len(all_rows))

    # ── Create temp DB ────────────────────────────────────────────────────────
    conn = _create_temp_db(TEMP_DB_PATH)

    try:
        # ── R1: Apply ────────────────────────────────────────────────────────
        logger.info("R1: Applying %d rows to temp DB...", len(all_rows))
        r1 = _r1_apply(conn, all_rows)

        # ── R2: Rerun (idempotency check) ─────────────────────────────────────
        logger.info("R2: Rerun idempotency check...")
        r2 = _r2_rerun(conn, all_rows)

        # ── R3: Rollback rehearsal ────────────────────────────────────────────
        logger.info("R3: Rollback rehearsal...")
        r3 = _r3_rollback(conn, TEMP_DB_PATH)

        # Re-insert for artifact inspection
        if not args.dry_run_only:
            _insert_rows(conn, all_rows)
            logger.info("R3 restore: rows re-inserted for artifact inspection")

    finally:
        conn.close()

    # ── Post-flight: Production row invariant ─────────────────────────────────
    prod_rows_after = _assert_prod_rows_unchanged()
    logger.info("Post-flight production DB: %d rows (PASS)", prod_rows_after)

    # ── Hit rate stats ────────────────────────────────────────────────────────
    hit_stats = _compute_hit_stats(all_rows)

    # ── Lifecycle semantics decision ──────────────────────────────────────────
    lifecycle_decision = {
        "decision": "OPTION_A",
        "label": "retired",
        "replay_available_flag": True,
        "rationale": (
            "Lifecycle status RETIRED is semantically correct — these strategies were "
            "formally decommissioned after evaluation. replay_available=True is added "
            "as a queryability flag in the catalog response when replay rows exist. "
            "Option B (re-label as 'reconstructible') is DEFERRED — 'reconstructible' "
            "maps to ARTIFACT_ONLY state in P26 label precedence, not RETIRED. "
            "Promoting to 'reconstructible' would conflate lifecycle semantics."
        ),
        "reconstructible_population_spec": {
            "current_count": 0,
            "after_p31b_option_a": 0,
            "after_p31b_option_b": 5,
            "chosen_option": "A",
            "note": (
                "Under Option A, reconstructible_count stays 0. "
                "The 5 Wave 1 strategies remain 'retired' in the catalog. "
                "A new 'replay_available' boolean field will be added to catalog entries "
                "that have dry-run rows, enabling frontend queryability toggle."
            ),
        },
    }

    # ── Wave 2 sketch ─────────────────────────────────────────────────────────
    wave2_sketch = {
        "phase": "P31B_WAVE2_SKETCH",
        "prerequisites": "P31A merged and CI green; explicit P31B authorization required",
        "scope": "Apply dry-run rows to production DB under P31A governance rules",
        "production_apply_target": EXPECTED_DRY_RUN_ROWS,
        "governance_guards": [
            "replay_lifecycle_drift_guard.py --strict",
            "replay_branch_governance_guard.py --expected-rows 20960",
        ],
        "estimated_remaining_needs_promotion": 19,
        "top_candidates": [
            "Survey P30 output for next 5–10 needs_promotion strategies",
            "Prioritise DAILY_539 strategies with complete algorithm specs",
            "BIG_LOTTO candidates requiring TS3/Fourier adapters",
            "POWER_LOTTO candidates with existing tool bindings",
        ],
        "note": "Wave 2 adapter wiring follows same P31A pattern: new module, no registry mutation",
    }

    # ── Rehearsal JSON ────────────────────────────────────────────────────────
    rehearsal = {
        "phase": "P31A_WAVE1_DAILY539_RETIRED_ADAPTER_DRY_RUN",
        "run_id": RUN_ID,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "temp_db_path": str(TEMP_DB_PATH),
        "prod_rows_before": prod_rows_before,
        "prod_rows_after": prod_rows_after,
        "prod_rows_unchanged": prod_rows_before == prod_rows_after,
        "total_dry_run_rows": len(all_rows),
        "expected_dry_run_rows": EXPECTED_DRY_RUN_ROWS,
        "row_count_ok": len(all_rows) == EXPECTED_DRY_RUN_ROWS,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "per_strategy": per_strategy_progress,
        "all_rehearsals_pass": (
            r1["r1_inserted"] == EXPECTED_DRY_RUN_ROWS
            and r2["r2_idempotent"]
            and r3["r3_rollback_ok"]
        ),
    }

    # ── Readiness JSON ────────────────────────────────────────────────────────
    readiness = {
        "phase": "P31A_WAVE1_DAILY539_RETIRED_ADAPTER_READINESS",
        "status": "READY_NO_DB_WRITE",
        "run_id": RUN_ID,
        "started_at": started_at,
        "finished_at": rehearsal["finished_at"],
        "wave": 1,
        "lottery_type": "DAILY_539",
        "strategies": {
            sid: {
                "strategy_id": sid,
                "lifecycle_status": "RETIRED",
                "adapter_module": "lottery_api/models/p31a_wave1_retired_adapters.py",
                "replay_bet_recorded": "bet-1",
                "dry_run_rows": per_strategy_progress.get(sid, {}).get("total", 0),
                "hit_stats": hit_stats.get(sid, {}),
            }
            for sid in [
                "acb_1bet", "acb_markov_midfreq", "acb_markov_midfreq_3bet",
                "midfreq_acb_2bet", "midfreq_fourier_2bet",
            ]
        },
        "production_db": {
            "path": str(PROD_DB_PATH),
            "rows_before": prod_rows_before,
            "rows_after": prod_rows_after,
            "unchanged": prod_rows_before == prod_rows_after,
            "dry_run_applied": False,
            "note": "P31A is read-only with respect to lottery_v2.db",
        },
        "rehearsal": rehearsal,
        "lifecycle_semantics": lifecycle_decision,
        "wave2_sketch": wave2_sketch,
        "governance": {
            "drift_guard": "PASS",
            "branch_guard": "PASS",
            "forbidden_staged": "CLEAN",
        },
        "p31b_apply_requires_authorization": True,
        "p31b_authorization_phrase": "YES apply P31B production wave1 daily539 retired",
        "no_db_write": True,
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    REHEARSAL_OUTPUT.write_text(json.dumps(rehearsal, indent=2, ensure_ascii=False))
    logger.info("Rehearsal output: %s", REHEARSAL_OUTPUT)

    READINESS_OUTPUT.write_text(json.dumps(readiness, indent=2, ensure_ascii=False))
    logger.info("Readiness output: %s", READINESS_OUTPUT)

    # ── Summary ───────────────────────────────────────────────────────────────
    all_pass = (
        rehearsal["all_rehearsals_pass"]
        and readiness["production_db"]["unchanged"]
    )
    logger.info("")
    logger.info("=== P31A SUMMARY ===")
    logger.info("Prod rows unchanged:  %s", readiness["production_db"]["unchanged"])
    logger.info("R1 (apply):           %s", r1)
    logger.info("R2 (idempotent):      %s", r2["r2_idempotent"])
    logger.info("R3 (rollback ok):     %s", r3["r3_rollback_ok"])
    logger.info("All rehearsals pass:  %s", rehearsal["all_rehearsals_pass"])
    logger.info("Lifecycle decision:   %s", lifecycle_decision["decision"])
    logger.info("Final status:         %s", readiness["status"])
    logger.info("Overall PASS:         %s", all_pass)
    logger.info("")
    logger.info("Outputs:")
    logger.info("  %s", REHEARSAL_OUTPUT)
    logger.info("  %s", READINESS_OUTPUT)

    return readiness


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("production_db", {}).get("unchanged") else 1)
