#!/usr/bin/env python3
"""
Backfill 30 天歷史快照 — MULTI_STRATEGY 格式
===============================================
對每期開獎（過去 30 天）補建 MULTI_STRATEGY 快照，
使用每個注數對應的最佳驗證策略（與現行快照系統一致）。

用法：
  python3 tools/backfill_snapshots_30d.py
  python3 tools/backfill_snapshots_30d.py --days 60
  python3 tools/backfill_snapshots_30d.py --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

import sqlite3

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

def ok(msg):   print(f'{GREEN}  ✓{RESET} {msg}')
def warn(msg): print(f'{YELLOW}  ⚠{RESET} {msg}')
def skip(msg): print(f'  · {msg}')


def get_draws_in_window(lottery_type: str, days: int):
    """取得過去 N 天的開獎資料，按期號升序排列"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
    cur.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type=? AND date >= ?
        ORDER BY CAST(draw AS INTEGER) ASC
    """, (lottery_type, cutoff))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_draws_before(lottery_type: str, draw: str):
    """取得 draw 之前的所有歷史資料（預測引擎用）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type=? AND CAST(draw AS INTEGER) < CAST(? AS INTEGER)
        ORDER BY CAST(draw AS INTEGER) ASC
    """, (lottery_type, draw))
    rows = []
    for r in cur.fetchall():
        rows.append({
            'draw': r['draw'],
            'date': r['date'],
            'numbers': json.loads(r['numbers']),
            'special': r['special'],
        })
    conn.close()
    return rows


def has_multi_strategy_run(lottery_type: str, latest_known_draw: str) -> bool:
    """檢查是否已有該 latest_known_draw 的 MULTI_STRATEGY 快照"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM prediction_runs
        WHERE lottery_type=? AND latest_known_draw=? AND strategy_name='MULTI_STRATEGY'
    """, (lottery_type, latest_known_draw))
    count = cur.fetchone()[0]
    conn.close()
    return count > 0


def get_prev_draw(lottery_type: str, draw: str) -> tuple:
    """取得 draw 的前一期號與日期"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT draw, date FROM draws
        WHERE lottery_type=? AND CAST(draw AS INTEGER) < CAST(? AS INTEGER)
        ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1
    """, (lottery_type, draw))
    row = cur.fetchone()
    conn.close()
    if row:
        return row['draw'], row['date']
    return None, None


def build_snapshot_for_draw(lottery_type: str, draw: str, history: list, dry_run: bool) -> bool:
    """
    為 draw 期建立 MULTI_STRATEGY 快照。
    history = 開獎 draw 之前的所有資料（預測引擎輸入）。
    latest_known_draw = history 最後一期（即 draw 的前一期）。
    """
    if len(history) < 50:
        warn(f'{lottery_type} {draw}: 歷史資料不足 50 期，跳過')
        return False

    prev_draw = history[-1]['draw']
    prev_date = history[-1]['date']

    if has_multi_strategy_run(lottery_type, prev_draw):
        skip(f'{lottery_type} {draw}: latest={prev_draw} 已有 MULTI_STRATEGY，跳過')
        return False

    # 載入策略函數
    if lottery_type == 'POWER_LOTTO':
        from tools.rsm_bootstrap import get_power_lotto_strategies_inline
        strategy_cfgs = get_power_lotto_strategies_inline()
        tracking_strategies = [
            {'bet_count': 2, 'strategy_key': 'fourier_rhythm_2bet'},
            {'bet_count': 3, 'strategy_key': 'fourier_rhythm_3bet'},
            {'bet_count': 4, 'strategy_key': 'pp3_freqort_4bet'},
            {'bet_count': 5, 'strategy_key': 'orthogonal_5bet'},
        ]
    elif lottery_type == 'BIG_LOTTO':
        from tools.rsm_bootstrap import get_big_lotto_strategies_inline
        strategy_cfgs = get_big_lotto_strategies_inline()
        tracking_strategies = [
            {'bet_count': 2, 'strategy_key': 'regime_2bet'},
            {'bet_count': 3, 'strategy_key': 'ts3_regime_3bet'},
            {'bet_count': 4, 'strategy_key': 'p1_deviation_4bet'},
            {'bet_count': 5, 'strategy_key': 'p1_dev_sum5bet'},
        ]
    elif lottery_type == 'DAILY_539':
        from tools.rsm_bootstrap import get_daily_539_strategies_inline
        strategy_cfgs = get_daily_539_strategies_inline()
        tracking_strategies = [
            {'bet_count': 1, 'strategy_key': 'acb_1bet'},
            {'bet_count': 2, 'strategy_key': 'midfreq_acb_2bet'},
            {'bet_count': 3, 'strategy_key': 'acb_markov_midfreq_3bet'},
            {'bet_count': 5, 'strategy_key': 'f4cold_5bet'},
        ]
    else:
        warn(f'未知彩種 {lottery_type}')
        return False

    predict_fns = {c['name']: c['predict_func'] for c in strategy_cfgs}

    # 特別號（威力彩需要）
    special_val = None
    if lottery_type == 'POWER_LOTTO':
        try:
            from tools.quick_predict import power_special_v3
            special_val = power_special_v3(history)[0]
        except Exception:
            pass

    # 執行各策略預測
    strategy_bets = []
    for ts in tracking_strategies:
        sk = ts['strategy_key']
        fn = predict_fns.get(sk)
        if fn is None:
            warn(f'  找不到策略函數: {sk}')
            continue
        try:
            raw = fn(history)
            bets = [sorted(b) for b in raw] if raw else []
            if bets:
                strategy_bets.append({
                    'strategy_name': sk,
                    'num_bets': ts['bet_count'],
                    'bets': bets,
                    'special': special_val,
                })
        except Exception as e:
            warn(f'  策略 {sk} 預測失敗: {e}')

    if not strategy_bets:
        warn(f'{lottery_type} {draw}: 所有策略均失敗，跳過')
        return False

    total_bets = sum(len(sg['bets']) for sg in strategy_bets)

    if dry_run:
        ok(f'[DRY-RUN] {lottery_type} {draw}: latest={prev_draw}, {len(strategy_bets)} 策略, {total_bets} 注')
        return True

    # 直接寫入正確 DB（bypass db_manager 相對路徑問題）
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO prediction_runs
              (lottery_type, latest_known_draw, latest_known_date, strategy_name, snapshot_source, notes)
            VALUES (?, ?, ?, 'MULTI_STRATEGY', 'RECONSTRUCTED', 'backfill_30d')
        """, (lottery_type, prev_draw, prev_date))
        run_id = cur.lastrowid

        global_idx = 0
        for sg in strategy_bets:
            sg_name = sg['strategy_name']
            sg_nbets = sg['num_bets']
            sg_special = sg.get('special')
            for bet_nums in sg['bets']:
                sp = sg_special if (lottery_type == 'POWER_LOTTO' and global_idx == 0) else None
                cur.execute("""
                    INSERT INTO prediction_items
                      (run_id, bet_index, numbers, special, status, strategy_name, num_bets)
                    VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
                """, (run_id, global_idx, json.dumps(sorted(bet_nums)), sp, sg_name, sg_nbets))
                global_idx += 1
        conn.commit()
    finally:
        conn.close()

    ok(f'{lottery_type} {draw}: latest={prev_draw}, run_id={run_id}, {len(strategy_bets)} 策略, {total_bets} 注')
    return True


def _resolve_pending_direct():
    """直接對正確 DB 執行 resolve，不經 db_manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    resolved = 0
    cur.execute("""
        SELECT pi.id, pi.run_id, pr.lottery_type, pr.latest_known_draw
        FROM prediction_items pi
        JOIN prediction_runs pr ON pi.run_id = pr.id
        WHERE pi.status = 'PENDING'
    """)
    pending = cur.fetchall()
    for row in pending:
        item_id = row['id']
        lt = row['lottery_type']
        lkd = row['latest_known_draw']
        cur.execute("""
            SELECT draw, date, numbers, special FROM draws
            WHERE lottery_type=? AND CAST(draw AS INTEGER) > CAST(? AS INTEGER)
            ORDER BY CAST(draw AS INTEGER) ASC LIMIT 1
        """, (lt, lkd))
        actual = cur.fetchone()
        if actual:
            import json as _json
            actual_nums = _json.loads(actual['numbers'])
            cur2 = conn.cursor()
            cur2.execute("SELECT numbers FROM prediction_items WHERE id=?", (item_id,))
            item_row = cur2.fetchone()
            bet_nums = _json.loads(item_row['numbers'])
            matched = sorted(set(bet_nums) & set(actual_nums))
            hit_count = len(matched)
            special_hit = actual['special'] in bet_nums if actual['special'] else False
            cur2.execute("""
                INSERT OR REPLACE INTO prediction_results
                  (item_id, actual_draw, actual_date, actual_numbers, actual_special,
                   hit_count, matched_numbers, special_hit, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (item_id, actual['draw'], actual['date'],
                  _json.dumps(actual_nums), actual['special'],
                  hit_count, _json.dumps(matched), 1 if special_hit else 0))
            cur2.execute("UPDATE prediction_items SET status='RESOLVED' WHERE id=?", (item_id,))
            resolved += 1
    conn.commit()
    conn.close()
    ok(f'已解析 {resolved} 筆 PENDING 預測')


def main():
    parser = argparse.ArgumentParser(description='Backfill 30天歷史快照')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print(f'\n{BOLD}Backfill 歷史快照 — 過去 {args.days} 天{"（DRY RUN）" if args.dry_run else ""}{RESET}')
    print('=' * 60)

    lottery_types = ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']
    total_created = 0

    for lt in lottery_types:
        draws = get_draws_in_window(lt, args.days)
        print(f'\n{BOLD}[{lt}] {len(draws)} 期{RESET}')
        for row in draws:
            draw = row['draw']
            history = get_all_draws_before(lt, draw)
            created = build_snapshot_for_draw(lt, draw, history, args.dry_run)
            if created:
                total_created += 1

    print(f'\n{BOLD}完成：{"模擬" if args.dry_run else "新建"} {total_created} 個快照{RESET}')

    if not args.dry_run and total_created > 0:
        print(f'\n{BOLD}自動解析 PENDING 預測...{RESET}')
        _resolve_pending_direct()


if __name__ == '__main__':
    main()
