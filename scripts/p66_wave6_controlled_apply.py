#!/usr/bin/env python3
"""
P66 — POWER_LOTTO Wave 6 Controlled Production Apply.

Executes the authorized production apply for two Wave 6 strategies:
  1. cold_complement_2bet  — CAIDs: P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525
  2. zonal_entropy_2bet   — CAIDs: P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525

Pre-requisites:
  - P65 commit b2ae277 on main (classification: P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION)
  - Branch: p66-wave6-controlled-production-apply
  - Both authorization phrases confirmed by operator:
      "YES apply cold_complement_2bet 1500 rows to production for P66"
      "YES apply zonal_entropy_2bet 1500 rows to production for P66"
  - Production rows: 43960 before apply

Expected outcome:
  - 3000 rows inserted (1500 per strategy, POWER_LOTTO)
  - Production rows: 43960 → 46960
  - No lifecycle promotion
  - No champion replacement
  - No ONLINE promotion
  - Coverage-expansion rationale — not performance superiority

MUST NOT apply:
  - lag_reversion_2bet (P64b GATE_FAIL — permanently excluded from P66)
  - Any other strategy
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# ─── Constants ────────────────────────────────────────────────────────────────

LOTTERY_TYPE = "POWER_LOTTO"

STRATEGY_COLD   = "cold_complement_2bet"
STRATEGY_ZONAL  = "zonal_entropy_2bet"
EXCLUDED_STRATEGY = "lag_reversion_2bet"  # MUST NOT apply

CAID_COLD   = "P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525"
CAID_ZONAL  = "P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525"

ROWS_PER_STRATEGY  = 1500
TOTAL_ROWS         = ROWS_PER_STRATEGY * 2          # 3000
EXPECTED_ROWS_BEFORE = 43960
EXPECTED_ROWS_AFTER  = 46960                        # 43960 + 3000

PICK         = 6
POOL         = 38
SPECIAL_POOL = 8

# Prediction windows
_COLD_WINDOW      = 100
_ZONE_WINDOW      = 30
_ZONE_COLD_WINDOW = 100
_ENTROPY_CHAOS_THRESHOLD = 2.2

TRUTH_LEVEL = "POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED"
SOURCE      = "p66_wave6_controlled_apply.py"
P65_COMMIT  = "b2ae277"

REPO_ROOT   = Path(__file__).resolve().parent.parent
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_DIR  = REPO_ROOT / "backups"
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p66_wave6_controlled_apply_20260525.json"

RUN_ID = f"P66_POWERLOTTO_WAVE6_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

# ─── DB helpers ───────────────────────────────────────────────────────────────

def _prod_conn_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(PROD_DB))
    conn.row_factory = sqlite3.Row
    return conn

def _prod_conn_ro() -> sqlite3.Connection:
    uri = f"file:{PROD_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Backup ───────────────────────────────────────────────────────────────────

def _create_backup() -> dict:
    """Create a timestamped DB backup before any production write."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"lottery_v2_pre_p66_wave6_{ts}.db"
    try:
        shutil.copy2(str(PROD_DB), str(backup_path))
    except Exception as e:
        return {"ok": False, "error": str(e), "backup_path": None}

    # Verify backup row count
    try:
        with sqlite3.connect(str(backup_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
    except Exception as e:
        return {"ok": False, "error": f"Backup verify failed: {e}", "backup_path": str(backup_path)}

    ok = count == EXPECTED_ROWS_BEFORE
    return {
        "ok": ok,
        "backup_path": str(backup_path),
        "backup_rows": count,
        "expected_rows": EXPECTED_ROWS_BEFORE,
        "rollback_cmd": f"cp {backup_path} {PROD_DB}",
    }

# ─── Pre-flight ───────────────────────────────────────────────────────────────

def _pre_flight() -> dict:
    with _prod_conn_ro() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        cold_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_COLD),
        ).fetchone()[0]
        zonal_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ZONAL),
        ).fetchone()[0]
        lag_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, EXCLUDED_STRATEGY),
        ).fetchone()[0]
        caid_cold = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CAID_COLD,),
        ).fetchone()[0]
        caid_zonal = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CAID_ZONAL,),
        ).fetchone()[0]
        wave6_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id LIKE '%WAVE6%'",
        ).fetchone()[0]
        p59_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525'",
        ).fetchone()[0]

    return {
        "production_rows": total,
        "production_rows_ok": total == EXPECTED_ROWS_BEFORE,
        "cold_complement_existing": cold_rows,
        "cold_complement_clean": cold_rows == 0,
        "zonal_entropy_existing": zonal_rows,
        "zonal_entropy_clean": zonal_rows == 0,
        "lag_reversion_rows": lag_rows,
        "lag_reversion_absent": lag_rows == 0,
        "caid_cold_existing": caid_cold,
        "caid_cold_clean": caid_cold == 0,
        "caid_zonal_existing": caid_zonal,
        "caid_zonal_clean": caid_zonal == 0,
        "wave6_rows_existing": wave6_rows,
        "wave6_clean": wave6_rows == 0,
        "p59_rows": p59_rows,
        "p59_rows_ok": p59_rows == 1500,
        "duplicate_check_pass": cold_rows == 0 and zonal_rows == 0 and caid_cold == 0 and caid_zonal == 0,
    }

# ─── Draw loading ─────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> list[dict]:
    uri = f"file:{PROD_DB}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
            (LOTTERY_TYPE,),
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

# ─── Prediction functions (mirrored from p56_wave5_powerlotto_adapters.py) ────

def _special_predict(history: list[dict]) -> int:
    """Frequency mean-reversion for special number in [1..8]."""
    recent = history[-30:] if len(history) >= 30 else history
    freq: Counter = Counter()
    for d in recent:
        sp = d.get("special")
        if sp is not None:
            freq[int(sp)] += 1
    w = len(recent)
    expected = w / SPECIAL_POOL
    return min(range(1, SPECIAL_POOL + 1), key=lambda n: abs(freq.get(n, 0) - expected))


def _predict_cold_complement(history: list[dict]) -> list[int]:
    """Cold-reversion: 6 numbers with lowest frequency over last 100 draws."""
    recent = history[-_COLD_WINDOW:] if len(history) >= _COLD_WINDOW else history
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= POOL:
                freq[num] += 1
    sorted_cold = sorted(range(1, POOL + 1), key=lambda n: (freq.get(n, 0), n))
    return sorted(sorted_cold[:PICK])


def _zone_entropy(history: list[dict], window: int = 30) -> float:
    """Shannon entropy of zone distribution over last `window` draws."""
    import math
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return 0.0
    zones = [0, 0, 0]  # [1-13], [14-26], [27-38]
    total = 0
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= 13:
                zones[0] += 1
            elif 14 <= num <= 26:
                zones[1] += 1
            else:
                zones[2] += 1
            total += 1
    if total == 0:
        return 0.0
    ent = 0.0
    for z in zones:
        if z > 0:
            p = z / total
            ent -= p * math.log2(p)
    return ent


def _predict_zonal_entropy(history: list[dict]) -> list[int]:
    """Entropy-adaptive zone selection: cold if chaotic, hot if stable."""
    entropy = _zone_entropy(history, window=_ZONE_WINDOW)
    is_chaotic = entropy > _ENTROPY_CHAOS_THRESHOLD

    if is_chaotic:
        recent = history[-_ZONE_COLD_WINDOW:] if len(history) >= _ZONE_COLD_WINDOW else history
        freq: Counter = Counter()
        for d in recent:
            for num in d["numbers"]:
                if 1 <= num <= POOL:
                    freq[num] += 1
        ranked = sorted(range(1, POOL + 1), key=lambda n: (freq.get(n, 0), n))
    else:
        recent = history[-_ZONE_WINDOW:] if len(history) >= _ZONE_WINDOW else history
        freq = Counter()
        for d in recent:
            for num in d["numbers"]:
                if 1 <= num <= POOL:
                    freq[num] += 1
        ranked = sorted(range(1, POOL + 1), key=lambda n: (-freq.get(n, 0), n))

    return sorted(ranked[:PICK])

# ─── Provenance ───────────────────────────────────────────────────────────────

def _make_prov_hash(strategy_id: str, draw: str, predicted: list[int], special: int) -> str:
    payload = f"{strategy_id}|{draw}|{sorted(predicted)}|{special}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

# ─── Row generation ───────────────────────────────────────────────────────────

def _generate_rows(
    all_draws: list[dict],
    strategy_id: str,
    predict_fn,
    controlled_apply_id: str,
    strategy_name: str,
) -> list[dict]:
    """Generate ROWS_PER_STRATEGY rows. Strictly no leakage: history is before target."""
    target_draws = all_draws[-ROWS_PER_STRATEGY:]
    now_str = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, target in enumerate(target_draws):
        history = all_draws[:len(all_draws) - ROWS_PER_STRATEGY + i]
        target_draw_str = str(target["draw"])
        draw_date = target.get("date", "")
        cutoff_draw = str(history[-1]["draw"]) if history else ""
        cutoff_date = history[-1].get("date", "") if history else ""

        predicted = predict_fn(history)
        predicted_special = _special_predict(history)

        actual_nums = target["numbers"]
        actual_special = target.get("special")
        hit_nums = [n for n in predicted if n in actual_nums]
        hit_count = len(hit_nums)
        special_hit = 1 if (actual_special is not None and int(predicted_special) == int(actual_special)) else 0
        prov_hash = _make_prov_hash(strategy_id, target_draw_str, predicted, predicted_special)

        rows.append({
            "lottery_type":             LOTTERY_TYPE,
            "target_draw":              target_draw_str,
            "target_date":              draw_date,
            "strategy_id":              strategy_id,
            "strategy_name":            strategy_name,
            "strategy_version":         "v0.1-p56",
            "history_cutoff_draw":      cutoff_draw,
            "replay_status":            "PREDICTED",
            "reject_reason":            None,
            "predicted_numbers":        predicted,
            "predicted_special":        predicted_special,
            "actual_numbers":           actual_nums,
            "actual_special":           actual_special,
            "hit_numbers":              hit_nums,
            "hit_count":                hit_count,
            "special_hit":              special_hit,
            "replay_run_id":            RUN_ID,
            "generated_at":             now_str,
            "truth_level":              TRUTH_LEVEL,
            "controlled_apply_id":      controlled_apply_id,
            "source":                   SOURCE,
            "provenance_hash":          prov_hash,
            "provenance_source":        "lottery_api/models/p56_wave5_powerlotto_adapters.py",
            "dry_run":                  0,
            "prediction_cutoff_date":   cutoff_date,
            "prediction_generated_at":  now_str,
            "draw_date":                draw_date,
        })
    return rows

# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_rows(rows: list[dict], strategy_id: str, caid: str) -> dict:
    errors: list[str] = []
    for i, row in enumerate(rows):
        draw = row.get("target_draw", "?")
        nums = row.get("predicted_numbers", [])
        if len(nums) != PICK:
            errors.append(f"row {i} ({draw}): expected {PICK} nums, got {len(nums)}")
        if len(set(nums)) != len(nums):
            errors.append(f"row {i} ({draw}): duplicate nums: {nums}")
        if any(not (1 <= n <= POOL) for n in nums):
            errors.append(f"row {i} ({draw}): nums out of [1..{POOL}]: {nums}")
        sp = row.get("predicted_special")
        if sp is not None and not (1 <= sp <= SPECIAL_POOL):
            errors.append(f"row {i} ({draw}): special out of [1..{SPECIAL_POOL}]: {sp}")
        if row.get("controlled_apply_id") != caid:
            errors.append(f"row {i}: caid mismatch")
        if row.get("dry_run") != 0:
            errors.append(f"row {i}: dry_run must be 0")
        if row.get("strategy_id") != strategy_id:
            errors.append(f"row {i}: strategy_id mismatch")
        if row.get("replay_status") == "ONLINE":
            errors.append(f"row {i}: replay_status must not be ONLINE")
    return {"valid": len(errors) == 0, "error_count": len(errors), "errors": errors[:10]}


def _check_leakage(rows: list[dict]) -> dict:
    violations: list[str] = []
    for i, row in enumerate(rows):
        cutoff = row.get("prediction_cutoff_date", "")
        draw_date = row.get("draw_date", "")
        if cutoff and draw_date and cutoff >= draw_date:
            violations.append(f"row {i}: cutoff={cutoff} >= draw_date={draw_date}")
    return {"violation_count": len(violations), "pass": len(violations) == 0, "violations": violations[:5]}


def _check_dup_pre(strategy_id: str, caid: str) -> dict:
    with _prod_conn_ro() as conn:
        by_sid = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, strategy_id),
        ).fetchone()[0]
        by_caid = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (caid,),
        ).fetchone()[0]
    return {"by_strategy": by_sid, "by_caid": by_caid, "pass": by_sid == 0 and by_caid == 0}

# ─── Serialisation ────────────────────────────────────────────────────────────

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


def _to_prod_row(row: dict) -> dict:
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


def _insert_rows(rows: list[dict]) -> dict:
    prod_rows = [_to_prod_row(r) for r in rows]
    inserted = skipped = 0
    errors_list: list[str] = []
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

def _post_verify(cold_caid: str, zonal_caid: str) -> dict:
    with _prod_conn_ro() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        cold_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_COLD),
        ).fetchone()[0]
        zonal_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ZONAL),
        ).fetchone()[0]
        lag_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, EXCLUDED_STRATEGY),
        ).fetchone()[0]
        cold_caid_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (cold_caid,),
        ).fetchone()[0]
        zonal_caid_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (zonal_caid,),
        ).fetchone()[0]
        p59_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id='P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525'",
        ).fetchone()[0]
        online_cold = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (LOTTERY_TYPE, STRATEGY_COLD),
        ).fetchone()[0]
        online_zonal = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (LOTTERY_TYPE, STRATEGY_ZONAL),
        ).fetchone()[0]
        dry_run_nonzero = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id IN (?,?) AND dry_run != 0",
            (cold_caid, zonal_caid),
        ).fetchone()[0]

        # POWER_LOTTO semantics check on 20 samples from each strategy
        cold_samples = conn.execute(
            "SELECT predicted_numbers, predicted_special FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 20",
            (cold_caid,),
        ).fetchall()
        zonal_samples = conn.execute(
            "SELECT predicted_numbers, predicted_special FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 20",
            (zonal_caid,),
        ).fetchall()

    sem_errors: list[str] = []
    for strategy_name, samples in [(STRATEGY_COLD, cold_samples), (STRATEGY_ZONAL, zonal_samples)]:
        for row in samples:
            try:
                pnums = json.loads(row[0]) if row[0] else []
                if len(pnums) != 6:
                    sem_errors.append(f"{strategy_name}: expected 6 first-zone nums, got {len(pnums)}: {pnums}")
                if any(not (1 <= n <= 38) for n in pnums):
                    sem_errors.append(f"{strategy_name}: nums out of [1..38]: {pnums}")
                sp = int(row[1]) if row[1] is not None else None
                if sp is not None and not (1 <= sp <= 8):
                    sem_errors.append(f"{strategy_name}: special out of [1..8]: {sp}")
            except Exception as e:
                sem_errors.append(f"{strategy_name}: parse error: {e}")

    return {
        "total_rows": total,
        "total_ok": total == EXPECTED_ROWS_AFTER,
        "cold_rows": cold_rows,
        "cold_rows_ok": cold_rows == ROWS_PER_STRATEGY,
        "zonal_rows": zonal_rows,
        "zonal_rows_ok": zonal_rows == ROWS_PER_STRATEGY,
        "lag_reversion_rows": lag_rows,
        "lag_reversion_absent": lag_rows == 0,
        "cold_caid_rows": cold_caid_rows,
        "cold_caid_ok": cold_caid_rows == ROWS_PER_STRATEGY,
        "zonal_caid_rows": zonal_caid_rows,
        "zonal_caid_ok": zonal_caid_rows == ROWS_PER_STRATEGY,
        "p59_rows": p59_rows,
        "p59_rows_preserved": p59_rows == 1500,
        "online_cold": online_cold,
        "online_zonal": online_zonal,
        "online_promotion_ok": online_cold == 0 and online_zonal == 0,
        "dry_run_zero_ok": dry_run_nonzero == 0,
        "semantic_errors": sem_errors,
        "semantic_ok": len(sem_errors) == 0,
        "p66_total_rows": cold_rows + zonal_rows,
        "p66_total_ok": (cold_rows + zonal_rows) == TOTAL_ROWS,
    }

# ─── Hit statistics ───────────────────────────────────────────────────────────

def _compute_hit_stats(rows: list[dict], strategy_id: str) -> dict:
    import math
    from collections import Counter as Ctr
    dist: Ctr = Ctr()
    specials = 0
    for row in rows:
        hc = row.get("hit_count", 0)
        dist[hc] += 1
        specials += row.get("special_hit", 0)
    n = len(rows)
    hit3plus = sum(v for k, v in dist.items() if k >= 3)
    from math import comb
    pool, pick, drawn = POOL, PICK, PICK
    baseline = sum(
        comb(pick, k) * comb(pool - pick, drawn - k) / comb(pool, drawn)
        for k in range(3, pick + 1)
    )
    p0 = baseline
    p_hat = hit3plus / n if n > 0 else 0
    z = (p_hat - p0) / math.sqrt(p0 * (1 - p0) / n) if n > 0 else 0
    try:
        from scipy.stats import norm as _norm  # type: ignore
        p_value = round(float(1 - _norm.cdf(z)), 4)
    except Exception:
        p_value = None

    return {
        "strategy_id": strategy_id,
        "predicted": n,
        "hit_3plus": hit3plus,
        "hit_3plus_rate_pct": round(hit3plus / n * 100, 4) if n else 0,
        "hit_count_distribution": {str(k): dist[k] for k in sorted(dist)},
        "special_hits": specials,
        "special_hit_rate": round(specials / n, 4) if n else 0,
        "theoretical_m3_baseline_pct": round(baseline * 100, 4),
        "z_test": {"z": round(z, 3), "p_value": p_value},
    }

# ─── JSON output ──────────────────────────────────────────────────────────────

def _write_json(result: dict) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("[OUTPUT] JSON written to: %s", OUTPUT_JSON)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=" * 70)
    logger.info("P66 POWER_LOTTO Wave 6 Controlled Production Apply")
    logger.info("Strategies: %s, %s", STRATEGY_COLD, STRATEGY_ZONAL)
    logger.info("CAIDs: %s | %s", CAID_COLD, CAID_ZONAL)
    logger.info("Authorization: GRANTED (both phrases confirmed by operator)")
    logger.info("Excluded: %s (P64b GATE_FAIL)", EXCLUDED_STRATEGY)
    logger.info("=" * 70)

    # ── Step 1: Backup ────────────────────────────────────────────────────────
    logger.info("[BACKUP] Creating production DB backup...")
    backup = _create_backup()
    logger.info("[BACKUP] ok=%s path=%s rows=%s",
                backup["ok"], backup.get("backup_path"), backup.get("backup_rows"))

    if not backup["ok"]:
        result = {
            "classification": "P66_BLOCKED_BY_BACKUP_FAILURE",
            "phase": "P66", "overall_ok": False,
            "error": backup.get("error", "backup failed"),
            "backup": backup,
        }
        _write_json(result)
        return result

    # ── Step 2: Pre-flight ────────────────────────────────────────────────────
    logger.info("[PRE-FLIGHT] Running checks...")
    pre = _pre_flight()
    logger.info("[PRE-FLIGHT] rows=%d ok=%s cold_clean=%s zonal_clean=%s dup_pass=%s p59_ok=%s",
                pre["production_rows"], pre["production_rows_ok"],
                pre["cold_complement_clean"], pre["zonal_entropy_clean"],
                pre["duplicate_check_pass"], pre["p59_rows_ok"])

    if not pre["production_rows_ok"]:
        result = {
            "classification": "P66_BLOCKED_BY_GOVERNANCE",
            "phase": "P66", "overall_ok": False,
            "error": f"production_rows={pre['production_rows']} != {EXPECTED_ROWS_BEFORE}",
            "pre_flight": pre, "backup": backup,
        }
        _write_json(result)
        return result

    if not pre["duplicate_check_pass"]:
        result = {
            "classification": "P66_BLOCKED_BY_DUPLICATE_ROWS",
            "phase": "P66", "overall_ok": False,
            "error": "Duplicate rows detected before apply",
            "pre_flight": pre, "backup": backup,
        }
        _write_json(result)
        return result

    # ── Step 3: Load draws ────────────────────────────────────────────────────
    logger.info("[DRAWS] Loading POWER_LOTTO draws (read-only)...")
    all_draws = _load_powerlotto_draws()
    logger.info("[DRAWS] Loaded %d draws", len(all_draws))

    if len(all_draws) < ROWS_PER_STRATEGY + 30:
        result = {
            "classification": "P66_BLOCKED_BY_GOVERNANCE",
            "phase": "P66", "overall_ok": False,
            "error": f"Insufficient draws: {len(all_draws)}",
            "backup": backup,
        }
        _write_json(result)
        return result

    # ── Step 4a: Generate + validate cold_complement rows ────────────────────
    logger.info("[GENERATE] Building %d rows for %s...", ROWS_PER_STRATEGY, STRATEGY_COLD)
    cold_rows = _generate_rows(
        all_draws, STRATEGY_COLD, _predict_cold_complement, CAID_COLD,
        "威力彩 冷號互補 2注",
    )
    logger.info("[GENERATE] Generated %d cold rows", len(cold_rows))

    cold_schema = _validate_rows(cold_rows, STRATEGY_COLD, CAID_COLD)
    logger.info("[VALIDATE] cold schema: valid=%s errors=%d", cold_schema["valid"], cold_schema["error_count"])

    cold_leakage = _check_leakage(cold_rows)
    logger.info("[VALIDATE] cold leakage: violations=%d pass=%s", cold_leakage["violation_count"], cold_leakage["pass"])

    cold_dup_pre = _check_dup_pre(STRATEGY_COLD, CAID_COLD)
    logger.info("[VALIDATE] cold dup_pre: pass=%s", cold_dup_pre["pass"])

    if not (cold_schema["valid"] and cold_leakage["pass"] and cold_dup_pre["pass"]):
        result = {
            "classification": "P66_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P66", "overall_ok": False,
            "error": "cold_complement_2bet pre-insert validation failed",
            "cold_schema": cold_schema, "cold_leakage": cold_leakage,
            "cold_dup_pre": cold_dup_pre, "backup": backup,
        }
        _write_json(result)
        return result

    # ── Step 4b: Generate + validate zonal_entropy rows ──────────────────────
    logger.info("[GENERATE] Building %d rows for %s...", ROWS_PER_STRATEGY, STRATEGY_ZONAL)
    zonal_rows = _generate_rows(
        all_draws, STRATEGY_ZONAL, _predict_zonal_entropy, CAID_ZONAL,
        "威力彩 Zonal Entropy 2注",
    )
    logger.info("[GENERATE] Generated %d zonal rows", len(zonal_rows))

    zonal_schema = _validate_rows(zonal_rows, STRATEGY_ZONAL, CAID_ZONAL)
    logger.info("[VALIDATE] zonal schema: valid=%s errors=%d", zonal_schema["valid"], zonal_schema["error_count"])

    zonal_leakage = _check_leakage(zonal_rows)
    logger.info("[VALIDATE] zonal leakage: violations=%d pass=%s", zonal_leakage["violation_count"], zonal_leakage["pass"])

    zonal_dup_pre = _check_dup_pre(STRATEGY_ZONAL, CAID_ZONAL)
    logger.info("[VALIDATE] zonal dup_pre: pass=%s", zonal_dup_pre["pass"])

    if not (zonal_schema["valid"] and zonal_leakage["pass"] and zonal_dup_pre["pass"]):
        result = {
            "classification": "P66_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P66", "overall_ok": False,
            "error": "zonal_entropy_2bet pre-insert validation failed",
            "zonal_schema": zonal_schema, "zonal_leakage": zonal_leakage,
            "zonal_dup_pre": zonal_dup_pre, "backup": backup,
        }
        _write_json(result)
        return result

    # ── Step 5a: Insert cold_complement ──────────────────────────────────────
    logger.info("[APPLY] Inserting %d rows for %s...", ROWS_PER_STRATEGY, STRATEGY_COLD)
    cold_insert = _insert_rows(cold_rows)
    logger.info("[APPLY] cold inserted=%d skipped=%d ok=%s",
                cold_insert["inserted"], cold_insert["skipped"], cold_insert["insert_ok"])

    if not cold_insert["insert_ok"]:
        result = {
            "classification": "P66_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P66", "overall_ok": False,
            "error": f"cold_complement insert incomplete: {cold_insert['inserted']}/{ROWS_PER_STRATEGY}",
            "cold_insert": cold_insert, "backup": backup,
            "rollback_note": f"Run: DELETE FROM strategy_prediction_replays WHERE controlled_apply_id='{CAID_COLD}';",
        }
        _write_json(result)
        return result

    # ── Step 5b: Insert zonal_entropy ─────────────────────────────────────────
    logger.info("[APPLY] Inserting %d rows for %s...", ROWS_PER_STRATEGY, STRATEGY_ZONAL)
    zonal_insert = _insert_rows(zonal_rows)
    logger.info("[APPLY] zonal inserted=%d skipped=%d ok=%s",
                zonal_insert["inserted"], zonal_insert["skipped"], zonal_insert["insert_ok"])

    if not zonal_insert["insert_ok"]:
        result = {
            "classification": "P66_BLOCKED_BY_POST_APPLY_VERIFICATION",
            "phase": "P66", "overall_ok": False,
            "error": f"zonal_entropy insert incomplete: {zonal_insert['inserted']}/{ROWS_PER_STRATEGY}",
            "cold_insert": cold_insert, "zonal_insert": zonal_insert,
            "backup": backup,
            "rollback_note": (
                f"Run: DELETE FROM strategy_prediction_replays WHERE controlled_apply_id IN ('{CAID_COLD}','{CAID_ZONAL}');"
            ),
        }
        _write_json(result)
        return result

    # ── Step 6: Post-apply verification ──────────────────────────────────────
    logger.info("[VERIFY] Post-apply verification...")
    post = _post_verify(CAID_COLD, CAID_ZONAL)
    logger.info("[VERIFY] total=%d ok=%s cold=%d zonal=%d lag=%d online_ok=%s sem_ok=%s p59=%d",
                post["total_rows"], post["total_ok"],
                post["cold_rows"], post["zonal_rows"],
                post["lag_reversion_rows"],
                post["online_promotion_ok"],
                post["semantic_ok"],
                post["p59_rows"])

    # ── Hit statistics ────────────────────────────────────────────────────────
    cold_stats  = _compute_hit_stats(cold_rows, STRATEGY_COLD)
    zonal_stats = _compute_hit_stats(zonal_rows, STRATEGY_ZONAL)
    logger.info("[STATS] cold  M3+: %d/%d = %.2f%%",
                cold_stats["hit_3plus"], ROWS_PER_STRATEGY, cold_stats["hit_3plus_rate_pct"])
    logger.info("[STATS] zonal M3+: %d/%d = %.2f%%",
                zonal_stats["hit_3plus"], ROWS_PER_STRATEGY, zonal_stats["hit_3plus_rate_pct"])

    all_ok = (
        pre["production_rows_ok"]
        and pre["duplicate_check_pass"]
        and cold_schema["valid"]
        and cold_leakage["pass"]
        and cold_dup_pre["pass"]
        and cold_insert["insert_ok"]
        and zonal_schema["valid"]
        and zonal_leakage["pass"]
        and zonal_dup_pre["pass"]
        and zonal_insert["insert_ok"]
        and post["total_ok"]
        and post["cold_rows_ok"]
        and post["zonal_rows_ok"]
        and post["lag_reversion_absent"]
        and post["online_promotion_ok"]
        and post["semantic_ok"]
        and post["p59_rows_preserved"]
    )

    classification = (
        "P66_WAVE6_CONTROLLED_APPLY_COMPLETED"
        if all_ok else
        "P66_BLOCKED_BY_POST_APPLY_VERIFICATION"
    )

    result = {
        "schema_version": "1.0",
        "task_id": "P66",
        "run_id": RUN_ID,
        "classification": classification,
        "phase": "P66",
        "lottery_type": LOTTERY_TYPE,
        "overall_ok": all_ok,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "p65_ref": {
            "commit": P65_COMMIT,
            "classification": "P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION",
        },
        "backup": backup,
        "pre_flight": pre,
        "production_rows_before": EXPECTED_ROWS_BEFORE,
        "production_rows_after": post["total_rows"],
        "strategies_applied": {
            "cold_complement_2bet": {
                "controlled_apply_id": CAID_COLD,
                "rows_inserted": cold_insert["inserted"],
                "schema_validation": cold_schema,
                "leakage_check": cold_leakage,
                "dup_check_pre": cold_dup_pre,
                "insert_result": cold_insert,
                "hit_stats": cold_stats,
            },
            "zonal_entropy_2bet": {
                "controlled_apply_id": CAID_ZONAL,
                "rows_inserted": zonal_insert["inserted"],
                "schema_validation": zonal_schema,
                "leakage_check": zonal_leakage,
                "dup_check_pre": zonal_dup_pre,
                "insert_result": zonal_insert,
                "hit_stats": zonal_stats,
            },
        },
        "excluded_strategy": {
            "strategy_id": EXCLUDED_STRATEGY,
            "reason": "P64b GATE_FAIL — w150=0.67%, w500=2.00%, w1500=3.73%",
            "applied": False,
        },
        "post_apply_verification": post,
        "governance": {
            "production_db_write": True,
            "lifecycle_promotion": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "online_promotion": False,
            "wave5_champion_unchanged": "fourier30_markov30_2bet",
            "coverage_expansion_only": True,
            "performance_improvement_claim": False,
        },
        "rollback": {
            "rollback_sql": (
                f"DELETE FROM strategy_prediction_replays "
                f"WHERE controlled_apply_id IN "
                f"('{CAID_COLD}', '{CAID_ZONAL}');"
            ),
            "restore_backup_cmd": backup.get("rollback_cmd", ""),
            "verify_sql": f"SELECT COUNT(*) FROM strategy_prediction_replays;  -- expected {EXPECTED_ROWS_BEFORE} after rollback",
        },
    }

    _write_json(result)

    logger.info("=" * 70)
    logger.info("FINAL CLASSIFICATION: %s", classification)
    logger.info("Production rows: %d → %d", EXPECTED_ROWS_BEFORE, post["total_rows"])
    logger.info("cold_complement_2bet: %d rows inserted", cold_insert["inserted"])
    logger.info("zonal_entropy_2bet:   %d rows inserted", zonal_insert["inserted"])
    logger.info("P66 total inserted:   %d rows", cold_insert["inserted"] + zonal_insert["inserted"])
    logger.info("=" * 70)

    return result


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("overall_ok") else 1)
