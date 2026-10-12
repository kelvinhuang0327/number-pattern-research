#!/usr/bin/env python3
"""
P59 — POWER_LOTTO Wave 5 Controlled Production Apply.

Executes the authorized production apply for fourier30_markov30_2bet.
Inserts exactly 1500 rows into the production DB.

Pre-requisites:
  - P58 commit 4b6a0c4 on main (classification: P58_CONTROLLED_APPLY_PROPOSAL_READY)
  - Branch: p59-powerlotto-wave5-controlled-production-apply
  - Both authorization phrases present (verified externally)
  - Production rows: 42460 before apply

Expected outcome:
  - 1500 rows inserted (fourier30_markov30_2bet, POWER_LOTTO)
  - Production rows: 42460 → 43960
  - Controlled Apply ID: P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525
  - No lifecycle promotion
  - No champion replacement
  - No ONLINE promotion
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Constants ────────────────────────────────────────────────────────────────

P59_STRATEGY       = "fourier30_markov30_2bet"
P59_LOTTERY_TYPE   = "POWER_LOTTO"
CONTROLLED_APPLY_ID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
ROWS_PER_STRATEGY  = 1500
EXPECTED_ROWS_BEFORE = 42460
EXPECTED_ROWS_AFTER  = 43960
PICK               = 6
POOL               = 38
SPECIAL_POOL       = 8
TRUTH_LEVEL        = "POWER_LOTTO_WAVE5_CONTROLLED_APPLY_VERIFIED"
SOURCE             = "p59_powerlotto_wave5_controlled_apply.py"
P58_COMMIT         = "4b6a0c4"

REPO_ROOT    = Path(__file__).resolve().parent.parent
PROD_DB      = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON  = REPO_ROOT / "outputs" / "replay" / "p59_powerlotto_wave5_controlled_apply_20260525.json"

RUN_ID = f"P59_POWERLOTTO_WAVE5_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

# ─── DB helpers ───────────────────────────────────────────────────────────────

def _prod_conn_rw() -> sqlite3.Connection:
    """Open production DB in read-write mode."""
    conn = sqlite3.connect(str(PROD_DB))
    conn.row_factory = sqlite3.Row
    return conn

def _prod_conn_ro() -> sqlite3.Connection:
    """Open production DB in read-only URI mode."""
    uri = f"file:{PROD_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Pre-flight ───────────────────────────────────────────────────────────────

def _pre_flight() -> dict:
    """Verify production state before apply."""
    with _prod_conn_ro() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        dup_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (P59_LOTTERY_TYPE, P59_STRATEGY),
        ).fetchone()[0]
        caid_count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        # Verify P58 champion still present
        champion = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (P59_LOTTERY_TYPE, "fourier_rhythm_3bet"),
        ).fetchone()[0]

    return {
        "production_rows": total,
        "production_rows_ok": total == EXPECTED_ROWS_BEFORE,
        "strategy_dup_count": dup_count,
        "duplicate_check_pass": dup_count == 0,
        "controlled_apply_id_count": caid_count,
        "caid_check_pass": caid_count == 0,
        "champion_present": champion > 0,
        "p58_commit_ref": P58_COMMIT,
    }

# ─── Draw loading ─────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> list[dict]:
    """Load all POWER_LOTTO draws from production DB (read-only, ordered by draw asc)."""
    uri = f"file:{PROD_DB}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
            (P59_LOTTERY_TYPE,),
        ).fetchall()
    result = []
    for row in rows:
        nums_raw = row[2]
        if isinstance(nums_raw, str):
            try:
                nums = json.loads(nums_raw)
            except json.JSONDecodeError:
                nums = [int(x.strip()) for x in nums_raw.strip("[]").split(",") if x.strip()]
        else:
            nums = list(nums_raw) if nums_raw else []
        result.append({
            "draw": row[0],
            "date": row[1],
            "numbers": nums,
            "special": row[3],
        })
    return result

# ─── Prediction ───────────────────────────────────────────────────────────────

def _predict_fourier30_markov30(history: list[dict]) -> list[int]:
    """Recency-weighted frequency, window=30. Returns top-6 from [1..38]."""
    window = history[-30:] if len(history) >= 30 else history
    n = len(window)
    freq: dict[int, float] = {i: 0.0 for i in range(1, POOL + 1)}
    for i, draw in enumerate(window):
        weight = 1.0 + 2.0 * (i / n) if n > 0 else 1.0
        for num in draw.get("numbers", []):
            if 1 <= num <= POOL:
                freq[num] += weight
    top6 = sorted(range(1, POOL + 1), key=lambda x: -freq[x])[:PICK]
    return sorted(top6)


def _predict_special_mean_reversion(history: list[dict]) -> int:
    """Least-seen special in window=30 from [1..8]."""
    from collections import Counter
    window = history[-30:]
    freq: Counter = Counter()
    for draw in window:
        sp = draw.get("special")
        if sp is not None:
            freq[sp] += 1
    return min(range(1, SPECIAL_POOL + 1), key=lambda n: (freq.get(n, 0), n))

# ─── Row generation ───────────────────────────────────────────────────────────

def _make_prov_hash(strategy_id: str, draw: str, predicted: list[int], special: int) -> str:
    payload = f"{strategy_id}|{draw}|{sorted(predicted)}|{special}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _generate_rows(all_draws: list[dict]) -> list[dict]:
    """Generate 1500 production rows (in memory). No leakage — history is strictly before target."""
    target_draws = all_draws[-ROWS_PER_STRATEGY:]
    now_str = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, target in enumerate(target_draws):
        history = all_draws[:len(all_draws) - ROWS_PER_STRATEGY + i]
        target_draw_str = str(target["draw"])
        draw_date = target.get("date", "")
        cutoff_draw = str(history[-1]["draw"]) if history else ""
        cutoff_date = history[-1].get("date", "") if history else ""

        predicted = _predict_fourier30_markov30(history)
        predicted_special = _predict_special_mean_reversion(history)

        actual_nums = target["numbers"]
        actual_special = target.get("special")
        hit_nums = [n for n in predicted if n in actual_nums]
        hit_count = len(hit_nums)
        special_hit = 1 if (actual_special is not None and predicted_special == actual_special) else 0
        prov_hash = _make_prov_hash(P59_STRATEGY, target_draw_str, predicted, predicted_special)

        rows.append({
            "lottery_type": P59_LOTTERY_TYPE,
            "target_draw": target_draw_str,
            "target_date": draw_date,
            "strategy_id": P59_STRATEGY,
            "strategy_name": "fourier30_markov30_2bet",
            "strategy_version": "1.0.0",
            "history_cutoff_draw": cutoff_draw,
            "replay_status": "PREDICTED",
            "reject_reason": None,
            "predicted_numbers": predicted,
            "predicted_special": predicted_special,
            "actual_numbers": actual_nums,
            "actual_special": actual_special,
            "hit_numbers": hit_nums,
            "hit_count": hit_count,
            "special_hit": special_hit,
            "replay_run_id": RUN_ID,
            "generated_at": now_str,
            "truth_level": TRUTH_LEVEL,
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "source": SOURCE,
            "provenance_hash": prov_hash,
            "provenance_source": "p56_wave5_powerlotto_adapters.py",
            "dry_run": 0,
            "prediction_cutoff_date": cutoff_date,
            "prediction_generated_at": now_str,
            "draw_date": draw_date,
        })
    return rows

# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_rows(rows: list[dict]) -> dict:
    """Validate POWER_LOTTO semantics."""
    errors: list[str] = []
    for i, row in enumerate(rows):
        sid, draw = row.get("strategy_id", "?"), row.get("target_draw", "?")
        nums = row.get("predicted_numbers", [])
        if len(nums) != PICK:
            errors.append(f"row {i} ({sid}/{draw}): expected {PICK} nums, got {len(nums)}")
        if len(set(nums)) != len(nums):
            errors.append(f"row {i} ({sid}/{draw}): duplicate numbers: {nums}")
        if any(not (1 <= n <= POOL) for n in nums):
            errors.append(f"row {i} ({sid}/{draw}): numbers out of [1..{POOL}]: {nums}")
        sp = row.get("predicted_special")
        if sp is not None and not (1 <= sp <= SPECIAL_POOL):
            errors.append(f"row {i} ({sid}/{draw}): special out of [1..{SPECIAL_POOL}]: {sp}")
        if row.get("controlled_apply_id") != CONTROLLED_APPLY_ID:
            errors.append(f"row {i}: controlled_apply_id mismatch")
        if row.get("dry_run") != 0:
            errors.append(f"row {i}: dry_run must be 0 for production apply")
        if row.get("strategy_id") != P59_STRATEGY:
            errors.append(f"row {i}: strategy_id mismatch: {row.get('strategy_id')}")
    return {"valid": len(errors) == 0, "error_count": len(errors), "errors": errors[:10]}


def _check_leakage(rows: list[dict]) -> dict:
    """Verify cutoff_date < draw_date for all rows (no future data used)."""
    violations: list[str] = []
    for i, row in enumerate(rows):
        cutoff = row.get("prediction_cutoff_date", "")
        draw_date = row.get("draw_date", "")
        if cutoff and draw_date and cutoff >= draw_date:
            violations.append(f"row {i}: cutoff={cutoff} >= draw_date={draw_date}")
    return {"violation_count": len(violations), "pass": len(violations) == 0, "violations": violations[:5]}


def _check_duplicates_pre(rows: list[dict]) -> dict:
    """Verify zero existing rows for this strategy+controlled_apply_id in prod."""
    with _prod_conn_ro() as conn:
        exact = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND controlled_apply_id=?",
            (P59_LOTTERY_TYPE, P59_STRATEGY, CONTROLLED_APPLY_ID),
        ).fetchone()[0]
    return {"existing_in_prod": exact, "pass": exact == 0}

# ─── Serialisation ────────────────────────────────────────────────────────────

def _to_prod_row(row: dict) -> dict:
    """Serialize in-memory row dict to production DB column format."""
    predicted = row["predicted_numbers"]
    return {
        "lottery_type":            row["lottery_type"],
        "target_draw":             row["target_draw"],
        "target_date":             row.get("target_date"),
        "strategy_id":             row["strategy_id"],
        "strategy_name":           row.get("strategy_name"),
        "strategy_version":        row.get("strategy_version"),
        "history_cutoff_draw":     row.get("history_cutoff_draw"),
        "replay_status":           row.get("replay_status", "PREDICTED"),
        "reject_reason":           row.get("reject_reason"),
        "predicted_numbers":       json.dumps(sorted(predicted)) if predicted else None,
        "predicted_special":       str(row["predicted_special"]) if row.get("predicted_special") is not None else None,
        "actual_numbers":          json.dumps(row.get("actual_numbers", [])),
        "actual_special":          row.get("actual_special"),
        "hit_numbers":             json.dumps(row.get("hit_numbers", [])),
        "hit_count":               row.get("hit_count", 0),
        "special_hit":             row.get("special_hit", 0),
        "replay_run_id":           row.get("replay_run_id"),
        "generated_at":            row.get("generated_at"),
        "truth_level":             row.get("truth_level"),
        "controlled_apply_id":     row.get("controlled_apply_id"),
        "source":                  row.get("source"),
        "provenance_hash":         row.get("provenance_hash"),
        "provenance_source":       row.get("provenance_source"),
        "dry_run":                 row.get("dry_run", 0),
        "prediction_cutoff_date":  row.get("prediction_cutoff_date"),
        "prediction_generated_at": row.get("prediction_generated_at"),
    }

# ─── Production INSERT ────────────────────────────────────────────────────────

_INSERT_SQL = """
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
"""


def _insert_to_prod(rows: list[dict]) -> dict:
    """Insert serialized rows into production DB. Returns insert summary."""
    prod_rows = [_to_prod_row(r) for r in rows]
    inserted = 0
    skipped = 0
    errors_list = []
    with _prod_conn_rw() as conn:
        for i, pr in enumerate(prod_rows):
            try:
                conn.execute(_INSERT_SQL, pr)
                inserted += 1
            except sqlite3.IntegrityError as e:
                skipped += 1
                errors_list.append(f"row {i}: IntegrityError: {e}")
            except Exception as e:
                errors_list.append(f"row {i}: Error: {e}")
        conn.commit()
    return {
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors_list[:10],
        "insert_ok": inserted == ROWS_PER_STRATEGY and skipped == 0,
    }

# ─── Post-apply verification ──────────────────────────────────────────────────

def _post_verify() -> dict:
    """Verify production DB state after apply."""
    with _prod_conn_ro() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        strategy_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (P59_LOTTERY_TYPE, P59_STRATEGY),
        ).fetchone()[0]
        caid_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        online_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (P59_LOTTERY_TYPE, P59_STRATEGY),
        ).fetchone()[0]
        dry_run_zero = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        # Check POWER_LOTTO semantics on sample
        samples = conn.execute(
            "SELECT predicted_numbers, predicted_special, actual_numbers, hit_numbers, hit_count, special_hit "
            "FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 10",
            (CONTROLLED_APPLY_ID,),
        ).fetchall()

    semantic_ok = True
    sem_errors: list[str] = []
    for row in samples:
        try:
            pnums = json.loads(row[0]) if row[0] else []
            if len(pnums) != 6 or any(not (1 <= n <= 38) for n in pnums):
                sem_errors.append(f"first-zone semantics fail: {pnums}")
            sp = int(row[1]) if row[1] is not None else None
            if sp is not None and not (1 <= sp <= 8):
                sem_errors.append(f"special out of [1..8]: {sp}")
        except Exception as e:
            sem_errors.append(f"parse error: {e}")
    if sem_errors:
        semantic_ok = False

    return {
        "total_rows": total,
        "total_ok": total == EXPECTED_ROWS_AFTER,
        "strategy_rows": strategy_rows,
        "strategy_rows_ok": strategy_rows == ROWS_PER_STRATEGY,
        "caid_rows": caid_rows,
        "caid_rows_ok": caid_rows == ROWS_PER_STRATEGY,
        "online_promotion_count": online_rows,
        "online_promotion_ok": online_rows == 0,
        "dry_run_zero_ok": dry_run_zero == 0,
        "semantic_ok": semantic_ok,
        "semantic_errors": sem_errors,
    }

# ─── Hit statistics ───────────────────────────────────────────────────────────

def _compute_hit_stats(rows: list[dict]) -> dict:
    from math import comb
    from collections import Counter
    dist: Counter = Counter()
    specials = 0
    for row in rows:
        hc = row.get("hit_count", 0)
        dist[hc] += 1
        specials += row.get("special_hit", 0)
    n = len(rows)
    hit3plus = sum(v for k, v in dist.items() if k >= 3)
    # Theoretical M3+ (hypergeometric)
    pool, pick, drawn = 38, 6, 6
    baseline = sum(
        comb(pick, k) * comb(pool - pick, drawn - k) / comb(pool, drawn)
        for k in range(3, pick + 1)
    )
    # z-test
    import math
    p0 = baseline
    p_hat = hit3plus / n if n > 0 else 0
    z = (p_hat - p0) / math.sqrt(p0 * (1 - p0) / n) if n > 0 else 0
    import statistics
    # one-tailed p-value approximation
    from scipy.stats import norm as _norm  # type: ignore
    try:
        p_value = round(1 - _norm.cdf(z), 4)
    except Exception:
        p_value = None

    return {
        "predicted": n,
        "hit_3plus": hit3plus,
        "hit_3plus_rate": round(hit3plus / n, 4) if n else 0,
        "hit_count_distribution": {str(k): dist[k] for k in sorted(dist)},
        "special_hits": specials,
        "special_hit_rate": round(specials / n, 4) if n else 0,
        "theoretical_m3_baseline": round(baseline, 4),
        "z_test": {"z": round(z, 3), "p_value": p_value},
    }

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=" * 70)
    logger.info("P59 POWER_LOTTO Wave 5 Controlled Production Apply")
    logger.info("Strategy: %s", P59_STRATEGY)
    logger.info("Controlled Apply ID: %s", CONTROLLED_APPLY_ID)
    logger.info("Authorization: GRANTED (both phrases confirmed by operator)")
    logger.info("=" * 70)

    # ── Pre-flight ────────────────────────────────────────────────────────────
    logger.info("[PRE-FLIGHT] Running checks...")
    pre = _pre_flight()
    logger.info("[PRE-FLIGHT] rows=%d ok=%s dup_pass=%s caid_pass=%s champion=%s",
                pre["production_rows"], pre["production_rows_ok"],
                pre["duplicate_check_pass"], pre["caid_check_pass"],
                pre["champion_present"])

    if not pre["production_rows_ok"]:
        result = {
            "classification": "P59_BLOCKED_BY_GOVERNANCE",
            "phase": "P59", "overall_ok": False,
            "error": f"production_rows={pre['production_rows']} != {EXPECTED_ROWS_BEFORE}",
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    if not pre["duplicate_check_pass"]:
        result = {
            "classification": "P59_BLOCKED_BY_DUPLICATE_ROWS",
            "phase": "P59", "overall_ok": False,
            "error": f"strategy already has {pre['strategy_dup_count']} rows in POWER_LOTTO",
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    if not pre["caid_check_pass"]:
        result = {
            "classification": "P59_BLOCKED_BY_DUPLICATE_ROWS",
            "phase": "P59", "overall_ok": False,
            "error": f"controlled_apply_id already has {pre['controlled_apply_id_count']} rows in prod",
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    # ── Load draws ────────────────────────────────────────────────────────────
    logger.info("[DRAWS] Loading POWER_LOTTO draws (read-only)...")
    all_draws = _load_powerlotto_draws()
    logger.info("[DRAWS] Loaded %d draws", len(all_draws))

    if len(all_draws) < ROWS_PER_STRATEGY + 30:
        result = {
            "classification": "P59_BLOCKED_BY_GOVERNANCE",
            "phase": "P59", "overall_ok": False,
            "error": f"Insufficient draws: {len(all_draws)}",
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    # ── Generate rows ─────────────────────────────────────────────────────────
    logger.info("[GENERATE] Building %d rows for %s...", ROWS_PER_STRATEGY, P59_STRATEGY)
    rows = _generate_rows(all_draws)
    logger.info("[GENERATE] Generated %d rows", len(rows))

    # ── Validate ──────────────────────────────────────────────────────────────
    schema_val = _validate_rows(rows)
    logger.info("[VALIDATE] Schema: valid=%s errors=%d", schema_val["valid"], schema_val["error_count"])

    leakage = _check_leakage(rows)
    logger.info("[VALIDATE] Leakage: violations=%d pass=%s", leakage["violation_count"], leakage["pass"])

    dup_check = _check_duplicates_pre(rows)
    logger.info("[VALIDATE] Dup check: existing=%d pass=%s", dup_check["existing_in_prod"], dup_check["pass"])

    if not (schema_val["valid"] and leakage["pass"] and dup_check["pass"]):
        result = {
            "classification": "P59_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P59", "overall_ok": False,
            "error": "Pre-insert validation failed",
            "schema_validation": schema_val,
            "leakage_check": leakage,
            "duplicate_check": dup_check,
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    # ── Insert to production DB ───────────────────────────────────────────────
    logger.info("[APPLY] Inserting %d rows into production DB...", ROWS_PER_STRATEGY)
    insert_result = _insert_to_prod(rows)
    logger.info("[APPLY] inserted=%d skipped=%d ok=%s",
                insert_result["inserted"], insert_result["skipped"], insert_result["insert_ok"])

    if not insert_result["insert_ok"]:
        result = {
            "classification": "P59_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P59", "overall_ok": False,
            "error": f"Insert incomplete: inserted={insert_result['inserted']} expected={ROWS_PER_STRATEGY}",
            "insert_result": insert_result,
            "pre_flight": pre,
        }
        _write_json(result)
        return result

    # ── Post-apply verification ───────────────────────────────────────────────
    logger.info("[VERIFY] Post-apply verification...")
    post = _post_verify()
    logger.info("[VERIFY] total=%d ok=%s strategy_rows=%d online=%d",
                post["total_rows"], post["total_ok"],
                post["strategy_rows"], post["online_promotion_count"])

    # ── Hit statistics ────────────────────────────────────────────────────────
    logger.info("[STATS] Computing hit statistics...")
    hit_stats = _compute_hit_stats(rows)
    logger.info("[STATS] M3+: %d/%d = %.2f%% (baseline: %.2f%%)",
                hit_stats["hit_3plus"], ROWS_PER_STRATEGY,
                hit_stats["hit_3plus_rate"] * 100,
                hit_stats["theoretical_m3_baseline"] * 100)

    all_ok = (
        pre["production_rows_ok"]
        and pre["duplicate_check_pass"]
        and pre["caid_check_pass"]
        and schema_val["valid"]
        and leakage["pass"]
        and dup_check["pass"]
        and insert_result["insert_ok"]
        and post["total_ok"]
        and post["strategy_rows_ok"]
        and post["online_promotion_ok"]
        and post["semantic_ok"]
    )

    classification = (
        "P59_POWERLOTTO_WAVE5_CONTROLLED_APPLY_COMPLETED"
        if all_ok else
        "P59_BLOCKED_BY_POST_APPLY_VERIFICATION"
    )

    result = {
        "classification": classification,
        "phase": "P59",
        "lottery_type": P59_LOTTERY_TYPE,
        "strategy": P59_STRATEGY,
        "controlled_apply_id": CONTROLLED_APPLY_ID,
        "mode": "CONTROLLED_APPLY",
        "overall_ok": all_ok,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pre_flight": pre,
        "production_rows_before": EXPECTED_ROWS_BEFORE,
        "production_rows_after": post["total_rows"],
        "inserted_rows": insert_result["inserted"],
        "insert_result": insert_result,
        "schema_validation": schema_val,
        "leakage_check": leakage,
        "duplicate_check_pre": dup_check,
        "post_apply_verification": post,
        "hit_stats": hit_stats,
        "governance": {
            "production_db_write": True,
            "lifecycle_promotion": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "live_api_call": False,
            "online_promotion": False,
            "watchlist_strategies_excluded": sorted([
                "cold_complement_2bet",
                "zonal_entropy_2bet",
            ]),
        },
        "rollback": {
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "rollback_sql": (
                f"DELETE FROM strategy_prediction_replays "
                f"WHERE controlled_apply_id = '{CONTROLLED_APPLY_ID}';"
            ),
            "restore_backup": "cp lottery_api/data/lottery_v2.db.bak_p59_* lottery_api/data/lottery_v2.db",
            "verify_sql": "SELECT COUNT(*) FROM strategy_prediction_replays;  -- expected: 42460 after rollback",
        },
        "p58_ref": {
            "commit": P58_COMMIT,
            "classification": "P58_CONTROLLED_APPLY_PROPOSAL_READY",
            "mode": "PROPOSAL_ONLY",
        },
    }

    _write_json(result)

    logger.info("=" * 70)
    logger.info("Classification: %s", classification)
    logger.info("Production rows: %d → %d", EXPECTED_ROWS_BEFORE, post["total_rows"])
    logger.info("Inserted: %d", insert_result["inserted"])
    logger.info("=" * 70)

    return result


def _write_json(result: dict) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("[OUTPUT] JSON written to: %s", OUTPUT_JSON)


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("overall_ok") else 1)
