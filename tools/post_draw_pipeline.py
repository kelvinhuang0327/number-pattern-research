#!/usr/bin/env python3
"""
Post-Draw Pipeline
==================
每期開獎後自動執行的完整流程：

  1. 入庫（若提供新開獎資料）
  2. RSM 更新（三彩種）
  3. DriftDetector PSI 重跑
  4. Winning Quality 計算
  5. Alert 判定（PSI WARNING/CRITICAL / RSM 邊際崩跌）

使用方式:
  # 完整流程（含新資料入庫）
  python3 tools/post_draw_pipeline.py \
    --lottery BIG_LOTTO \
    --draw 115000037 \
    --date 2026/03/20 \
    --numbers 11,15,33,38,41,43 \
    --special 21

  # 不入庫，只跑 RSM + PSI
  python3 tools/post_draw_pipeline.py --no-insert

  # 只跑 RSM
  python3 tools/post_draw_pipeline.py --rsm-only

2026-03-22 Created
"""
import argparse
import json
import os
import sys
import sqlite3
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')

# ── 顏色輸出 ─────────────────────────────────────────
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

def ok(msg):   print(f'{GREEN}  ✓{RESET} {msg}')
def warn(msg): print(f'{YELLOW}  ⚠{RESET} {msg}')
def err(msg):  print(f'{RED}  ✗{RESET} {msg}')
def hdr(msg):  print(f'\n{BOLD}{msg}{RESET}')


# ── Step 1: 入庫 ─────────────────────────────────────
def step_insert(lottery_type, draw, date, numbers, special):
    hdr(f'[Step 1] 入庫: {lottery_type} {draw}')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('SELECT id FROM draws WHERE lottery_type=? AND draw=?', (lottery_type, draw))
    existing = c.fetchone()
    if existing:
        warn(f'已存在 {lottery_type} {draw}，跳過入庫')
        conn.close()
        return True

    c.execute(
        'INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?,?,?,?,?)',
        (draw, date, lottery_type, json.dumps(numbers), special)
    )
    conn.commit()
    conn.close()
    ok(f'已入庫 {draw} {numbers} SP={special}')
    return True


# ── Step 2: RSM 更新 ─────────────────────────────────
def step_rsm(lotteries=('BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539')):
    hdr('[Step 2] RSM 更新')
    import subprocess

    results = {}
    for lt in lotteries:
        try:
            cmd = [sys.executable, os.path.join(ROOT, 'tools', 'rsm_bootstrap.py'),
                   '--lottery', lt, '--periods', '300']
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=120)
            if proc.returncode != 0:
                err(f'{lt} RSM 失敗:\n{proc.stderr[:300]}')
                continue
            # 解析總結行
            lines = proc.stdout.splitlines()
            strategy_lines = [l for l in lines if ':' in l and ('Edge' in l or '+' in l or '-' in l)
                              and ('期,' in l or 'Edge' in l)]
            ok(f'{lt}: RSM 更新完成')

            # 讀取 strategy_states JSON
            import json as _json
            state_file = os.path.join(ROOT, 'lottery_api', 'data',
                                      f'strategy_states_{lt}.json')
            if os.path.exists(state_file):
                with open(state_file) as f:
                    states = _json.load(f)
                results[lt] = {}
                for name, data in states.items():
                    e = data.get('edge_300p', 0)
                    status = data.get('status', '?')
                    trend = data.get('trend', '?')
                    results[lt][name] = data
                    marker = ''
                    if e < 0:
                        marker = f' {RED}⚠ NEGATIVE EDGE{RESET}'
                    elif status in ('WARNING', 'REGIME_SHIFT'):
                        marker = f' {YELLOW}⚠ {status}{RESET}'
                    print(f'    {name}: edge300={e:+.4f} [{status}] {trend}{marker}')
            else:
                results[lt] = {}
        except subprocess.TimeoutExpired:
            err(f'{lt} RSM 超時')
        except Exception as ex:
            err(f'{lt} RSM 失敗: {ex}')
    return results


# ── Step 3: DriftDetector PSI ────────────────────────
def step_drift(lotteries=('BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539')):
    hdr('[Step 3] DriftDetector PSI')
    from lottery_api.engine.drift_detector import check_drift

    alerts = []
    for lt in lotteries:
        try:
            report = check_drift(lt)
            overall = report.overall_status
            psi = report.metrics.get('number_freq_PSI', {})
            psi_val = psi.get('value', 0)

            if overall == 'STABLE':
                ok(f'{lt}: PSI={psi_val:.4f} [{overall}]')
            elif overall == 'WARNING':
                warn(f'{lt}: PSI={psi_val:.4f} [{overall}] — 持續監控')
                alerts.append(f'{lt} PSI WARNING ({psi_val:.4f})')
            else:
                err(f'{lt}: PSI={psi_val:.4f} [{overall}] — 緊急假設生成觸發！')
                alerts.append(f'{lt} PSI CRITICAL ({psi_val:.4f})')
        except Exception as ex:
            err(f'{lt} DriftDetector 失敗: {ex}')

    return alerts


# ── Step 4: Winning Quality ──────────────────────────
def step_winning_quality(lottery_type, numbers):
    if not numbers:
        return
    hdr('[Step 4] Winning Quality 分析')
    try:
        from lottery_api.engine.winning_quality import analyze
        result = analyze(numbers, lottery_type)
        print(f'  號碼: {result["numbers"]}')
        print(f'  Popularity: {result["pop_score"]} (mean={result["baseline_mean"]}, z={result["z_score"]})')
        print(f'  百分位: P{result["percentile"]:.0f}')
        split = result['split_risk']
        payout = result['payout_quality']
        color = GREEN if split == 'LOW' else (YELLOW if split == 'MED' else RED)
        print(f'  分獎風險: {color}{split}{RESET}  中獎價值: {color}{payout}{RESET}')
        print(f'  {result["interpretation"]}')
        return result
    except Exception as ex:
        err(f'Winning Quality 失敗: {ex}')


# ── Step 5: Alert 彙總 ───────────────────────────────
def step_alerts(drift_alerts, rsm_results):
    hdr('[Step 5] Alert 彙總')
    all_alerts = list(drift_alerts)

    # RSM 邊際崩跌偵測
    EDGE_FLOOR = {
        'BIG_LOTTO':   0.02,   # +2%
        'POWER_LOTTO': 0.025,  # +2.5%
        'DAILY_539':   0.04,   # +4%
    }
    for lt, strategies in rsm_results.items():
        floor = EDGE_FLOOR.get(lt, 0.01)
        for name, data in strategies.items():
            e = data.get('edge_300p', 0)
            status = data.get('status', '')
            if e < 0:
                all_alerts.append(f'{lt}/{name} EDGE NEGATIVE ({e:+.2%})')
            elif e < floor and '★' in name:  # 僅監控推薦策略
                all_alerts.append(f'{lt}/{name} EDGE BELOW FLOOR ({e:+.2%} < {floor:.0%})')

    if not all_alerts:
        ok('無需處理的 Alert')
    else:
        for a in all_alerts:
            warn(f'ALERT: {a}')

    return all_alerts


# ── 主流程 ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Post-Draw Pipeline')
    parser.add_argument('--lottery', default=None,
                        choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'],
                        help='新入庫彩種（不指定則跳過入庫）')
    parser.add_argument('--draw', default=None, help='期號，如 115000037')
    parser.add_argument('--date', default=None, help='開獎日期，如 2026/03/20')
    parser.add_argument('--numbers', default=None, help='主號，逗號分隔，如 11,15,33,38,41,43')
    parser.add_argument('--special', type=int, default=None, help='特別號')
    parser.add_argument('--no-insert', action='store_true', help='跳過入庫步驟')
    parser.add_argument('--rsm-only', action='store_true', help='只跑 RSM')
    parser.add_argument('--lotteries', default='BIG_LOTTO,POWER_LOTTO,DAILY_539',
                        help='RSM/PSI 更新的彩種列表（逗號分隔）')
    args = parser.parse_args()

    print(f'\n{"="*60}')
    print(f'  Post-Draw Pipeline — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*60}')

    lotteries = [x.strip() for x in args.lotteries.split(',')]
    numbers = [int(x) for x in args.numbers.split(',')] if args.numbers else None

    # Step 1: 入庫
    if not args.no_insert and not args.rsm_only:
        if args.lottery and args.draw and args.date and numbers:
            step_insert(args.lottery, args.draw, args.date, numbers, args.special)
        else:
            warn('未提供完整入庫參數，跳過入庫')

    # Step 2: RSM
    rsm_results = step_rsm(lotteries)

    if args.rsm_only:
        print(f'\n{"="*60}')
        print('  RSM-only 模式完成')
        print(f'{"="*60}\n')
        return

    # Step 3: Drift
    drift_alerts = step_drift(lotteries)

    # Step 4: Winning Quality（對新入庫號碼）
    wq_result = None
    if args.lottery and numbers:
        wq_result = step_winning_quality(args.lottery, numbers)

    # Step 5: Alerts
    all_alerts = step_alerts(drift_alerts, rsm_results)

    # 最終摘要
    print(f'\n{"="*60}')
    print(f'  Pipeline 完成 — {datetime.now().strftime("%H:%M:%S")}')
    print(f'  Alerts: {len(all_alerts)} 項')
    if all_alerts:
        for a in all_alerts:
            print(f'    ⚠ {a}')
    else:
        print(f'  {GREEN}系統狀態正常{RESET}')
    print(f'{"="*60}\n')


if __name__ == '__main__':
    main()
