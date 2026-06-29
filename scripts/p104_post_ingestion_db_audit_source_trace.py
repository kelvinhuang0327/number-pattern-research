#!/usr/bin/env python3
"""
P104 Post-Ingestion DB Audit + Source Trace
Read-only forensic script — no DB writes.
"""

import sqlite3
import json
import os
import sys
from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')

STAR3_OLD_COUNT = 4115
STAR3_OLD_MAX = 115000024
STAR4_OLD_COUNT = 0


def get_db_snapshot():
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM strategy_prediction_replays')
    replay_rows = c.fetchone()[0]

    c.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
    pl_max = c.fetchone()[0]

    c.execute("SELECT COUNT(*), MIN(CAST(draw AS INTEGER)), MAX(CAST(draw AS INTEGER)), MIN(date), MAX(date) FROM draws WHERE lottery_type='3_STAR'")
    s3 = c.fetchone()

    c.execute("SELECT COUNT(*), MIN(CAST(draw AS INTEGER)), MAX(CAST(draw AS INTEGER)), MIN(date), MAX(date) FROM draws WHERE lottery_type='4_STAR'")
    s4 = c.fetchone()

    conn.close()

    return {
        'replay_rows': replay_rows,
        'power_lotto_max_draw': pl_max,
        'star3_count': s3[0],
        'star3_min_draw': s3[1],
        'star3_max_draw': s3[2],
        'star3_min_date': s3[3],
        'star3_max_date': s3[4],
        'star4_count': s4[0],
        'star4_min_draw': s4[1],
        'star4_max_draw': s4[2],
        'star4_min_date': s4[3],
        'star4_max_date': s4[4],
    }


def get_star3_new_rows():
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    c = conn.cursor()
    c.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type='3_STAR' AND CAST(draw AS INTEGER) > ? ORDER BY CAST(draw AS INTEGER) ASC",
        (STAR3_OLD_MAX,)
    )
    rows = [{'draw': r[0], 'date': r[1], 'numbers': r[2]} for r in c.fetchall()]
    conn.close()
    return rows


def validate_star3_integrity():
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    c = conn.cursor()

    c.execute("SELECT draw, COUNT(*) FROM draws WHERE lottery_type='3_STAR' GROUP BY draw HAVING COUNT(*) > 1")
    dups = c.fetchall()

    c.execute("SELECT draw, numbers FROM draws WHERE lottery_type='3_STAR'")
    invalid_numbers = []
    for draw, nums_raw in c.fetchall():
        try:
            nums = json.loads(nums_raw) if isinstance(nums_raw, str) else nums_raw
            if len(nums) != 3:
                invalid_numbers.append(draw)
            elif not all(0 <= int(n) <= 9 for n in nums):
                invalid_numbers.append(draw)
        except Exception:
            invalid_numbers.append(draw)

    c.execute(
        "SELECT CAST(draw AS INTEGER) FROM draws WHERE lottery_type='3_STAR' AND CAST(draw AS INTEGER) >= ? ORDER BY CAST(draw AS INTEGER) ASC",
        (STAR3_OLD_MAX,)
    )
    draw_nums = [r[0] for r in c.fetchall()]
    draw_set = set(draw_nums)
    gaps = [d for d in range(STAR3_OLD_MAX, max(draw_set) + 1) if d not in draw_set]

    conn.close()
    return {
        'duplicate_draws': len(dups),
        'invalid_numbers': len(invalid_numbers),
        'gaps_in_new_range': len(gaps),
        'gap_draws': gaps,
    }


def validate_star4_integrity():
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    c = conn.cursor()

    c.execute("SELECT draw, COUNT(*) FROM draws WHERE lottery_type='4_STAR' GROUP BY draw HAVING COUNT(*) > 1")
    dups = c.fetchall()

    c.execute("SELECT draw, numbers FROM draws WHERE lottery_type='4_STAR'")
    invalid_numbers = []
    for draw, nums_raw in c.fetchall():
        try:
            nums = json.loads(nums_raw) if isinstance(nums_raw, str) else nums_raw
            if len(nums) != 4:
                invalid_numbers.append(draw)
            elif not all(0 <= int(n) <= 9 for n in nums):
                invalid_numbers.append(draw)
        except Exception:
            invalid_numbers.append(draw)

    conn.close()
    return {
        'duplicate_draws': len(dups),
        'invalid_numbers': len(invalid_numbers),
    }


def check_ingest_log():
    log_path = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'ingest_log.jsonl')
    if not os.path.exists(log_path):
        return {'star3_entries': 0, 'star4_entries': 0}

    s3 = 0
    s4 = 0
    with open(log_path) as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                lt = d.get('lottery_type', '')
                if lt == '3_STAR':
                    s3 += 1
                elif lt == '4_STAR':
                    s4 += 1
            except Exception:
                pass

    return {'star3_entries': s3, 'star4_entries': s4}


def main():
    print("P104 Post-Ingestion DB Audit + Source Trace")
    print("=" * 50)

    snap = get_db_snapshot()
    print(f"replay_rows: {snap['replay_rows']}")
    print(f"POWER_LOTTO max_draw: {snap['power_lotto_max_draw']}")
    print(f"3_STAR: count={snap['star3_count']}, max={snap['star3_max_draw']}, date_range={snap['star3_min_date']}--{snap['star3_max_date']}")
    print(f"4_STAR: count={snap['star4_count']}, max={snap['star4_max_draw']}, date_range={snap['star4_min_date']}--{snap['star4_max_date']}")

    s3_delta = snap['star3_count'] - STAR3_OLD_COUNT
    s4_delta = snap['star4_count'] - STAR4_OLD_COUNT
    print(f"\n3_STAR delta: +{s3_delta} rows (old={STAR3_OLD_COUNT}, current={snap['star3_count']})")
    print(f"4_STAR delta: +{s4_delta} rows (old={STAR4_OLD_COUNT}, current={snap['star4_count']})")

    s3i = validate_star3_integrity()
    print(f"\n3_STAR integrity: dups={s3i['duplicate_draws']}, invalid={s3i['invalid_numbers']}, gaps={s3i['gaps_in_new_range']}")

    s4i = validate_star4_integrity()
    print(f"4_STAR integrity: dups={s4i['duplicate_draws']}, invalid={s4i['invalid_numbers']}")

    log = check_ingest_log()
    print(f"\ningest_log: 3_STAR entries={log['star3_entries']}, 4_STAR entries={log['star4_entries']}")

    print("\nDB writes: false")
    print("Replay row inserts: 0")
    print("Classification: P104_POST_INGESTION_DB_AUDIT_SOURCE_UNKNOWN_READY")

    return snap


if __name__ == '__main__':
    main()
