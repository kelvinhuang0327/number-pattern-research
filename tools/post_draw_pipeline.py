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


def _risk_color(split):
    if split == 'LOW':
        return GREEN
    if split == 'MED':
        return YELLOW
    return RED


# ── Step 1: 入庫 ─────────────────────────────────────
def step_insert(lottery_type, draw, date, numbers, special, jackpot_amount=None):
    hdr(f'[Step 1] 入庫: {lottery_type} {draw}')
    from lottery_api.database import DatabaseManager

    db = DatabaseManager(DB_PATH)
    existing = db.get_draw(lottery_type, draw)
    if existing:
        warn(f'已存在 {lottery_type} {draw}，跳過入庫')
        return False

    draw_payload = {
        'draw': draw,
        'date': date,
        'lotteryType': lottery_type,
        'numbers': numbers,
        'special': special,
    }
    if jackpot_amount is not None:
        draw_payload['jackpot_amount'] = jackpot_amount

    inserted, duplicates = db.insert_draws([draw_payload])
    if inserted > 0:
        jackpot_text = f' jackpot={jackpot_amount}' if jackpot_amount is not None else ''
        ok(f'已入庫 {draw} {numbers} SP={special}{jackpot_text}')
        return True

    warn(f'入庫被忽略（duplicates={duplicates}）')
    return False


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


# ── Step 4: Winning Quality + EXTREME_SUM 偵測 ───────
def _compute_sum_percentile(lottery_type, draw_sum, window=300, long_window=1500):
    """
    動態計算和值百分位，並做閾值校準檢查。
    校準條件：若 P5_window 與 P5_long_window 差 > 3 → 輸出校準警告，不停用。
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 長窗口（依時間排序取最新 long_window 期）
    cur.execute(
        "SELECT numbers FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT ?",
        (lottery_type, long_window)
    )
    long_sums = sorted([sum(json.loads(r[0])) for r in cur.fetchall()])
    # 短窗口（依時間排序取最新 window 期）
    cur.execute(
        "SELECT numbers FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT ?",
        (lottery_type, window)
    )
    recent_sums = sorted([sum(json.loads(r[0])) for r in cur.fetchall()])
    conn.close()

    all_sums = long_sums
    n_long = len(all_sums)
    n_win  = len(recent_sums)

    pct_long  = sum(1 for s in all_sums   if s <= draw_sum) / n_long  * 100
    pct_win   = sum(1 for s in recent_sums if s <= draw_sum) / n_win   * 100

    p5_long  = all_sums[int(n_long * 0.05)]
    p95_long = all_sums[int(n_long * 0.95)]
    p5_win   = recent_sums[int(n_win * 0.05)]
    p95_win  = recent_sums[int(n_win * 0.95)]

    extreme = draw_sum <= p5_win or draw_sum >= p95_win
    # 閾值飄移校準：若 300p P5 與 1500p P5 差 > 3 → 提示重新校準
    calibration_ok = abs(p5_win - p5_long) <= 3 and abs(p95_win - p95_long) <= 3
    calibration_note = None
    if not calibration_ok:
        calibration_note = (
            f'閾值飄移：P5 {p5_win}(300p) vs {p5_long}(1500p)，'
            f'P95 {p95_win}(300p) vs {p95_long}(1500p) → 建議重新校準'
        )

    return {
        'draw_sum': draw_sum,
        'pct_300p': round(pct_win, 1),
        'pct_1500p': round(pct_long, 1),
        'p5_300p': p5_win, 'p95_300p': p95_win,
        'p5_1500p': p5_long, 'p95_1500p': p95_long,
        'extreme': extreme,
        'label': 'EXTREME_SUM' if extreme else 'NORMAL_SUM',
        'calibration_ok': calibration_ok,
        'calibration_note': calibration_note,
    }


def step_winning_quality(lottery_type, numbers):
    if not numbers:
        return None
    hdr('[Step 4] Winning Quality + EXTREME_SUM 分析')
    result = {}
    try:
        from lottery_api.engine.winning_quality import analyze
        wq = analyze(numbers, lottery_type)
        result.update(wq)
        print(f'  號碼: {wq["numbers"]}')
        print(f'  Popularity: {wq["pop_score"]} (mean={wq["baseline_mean"]}, z={wq["z_score"]})')
        print(f'  百分位: P{wq["percentile"]:.0f}')
        split = wq['split_risk']
        payout = wq['payout_quality']
        color = _risk_color(split)
        print(f'  分獎風險: {color}{split}{RESET}  中獎價值: {color}{payout}{RESET}')
        print(f'  {wq["interpretation"]}')
    except Exception as ex:
        err(f'Winning Quality 失敗: {ex}')

    # EXTREME_SUM 偵測（獨立，不依賴 winning_quality 模組）
    try:
        draw_sum = sum(numbers)
        sp = _compute_sum_percentile(lottery_type, draw_sum)
        result['extreme_sum'] = sp
        label_color = RED if sp['extreme'] else GREEN
        print(f'  和值 {draw_sum}：P{sp["pct_300p"]}(300p) / P{sp["pct_1500p"]}(1500p)  '
              f'→ {label_color}{sp["label"]}{RESET}')
        if sp['extreme']:
            warn(f'EXTREME_SUM 觸發：和值 {draw_sum} 超出 [{sp["p5_300p"]}, {sp["p95_300p"]}] (300p P5~P95)')
        if sp['calibration_note']:
            warn(f'閾值校準提示：{sp["calibration_note"]}')
    except Exception as ex:
        err(f'EXTREME_SUM 偵測失敗: {ex}')

    return result if result else None


# ── Step 4b: WQ 結果寫入最新 run 的 review_json ──────
def step_wq_to_db(lottery_type, draw, wq_result):
    """
    將 WQ + EXTREME_SUM 分析結果合併寫入該期最新 prediction_run 的 review_json。
    若 run 已有 review_json（人工評審），則只補充 winning_quality 欄位，不覆蓋其他欄位。
    """
    if not wq_result:
        return
    hdr('[Step 4b] WQ 結果寫入 review_json')
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # 找最新 resolved run（latest_known_draw = draw 前一期）
        cur.execute("""
            SELECT id, review_json FROM prediction_runs
            WHERE lottery_type=? AND latest_known_draw=(
                SELECT draw FROM draws WHERE lottery_type=?
                AND CAST(draw AS INTEGER) < CAST(? AS INTEGER)
                ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1
            )
            ORDER BY id DESC LIMIT 1
        """, (lottery_type, lottery_type, draw))
        row = cur.fetchone()
        if not row:
            warn(f'找不到對應 run（lottery={lottery_type}, draw={draw}）')
            conn.close()
            return

        run_id = row['id']
        existing = {}
        if row['review_json']:
            try:
                existing = json.loads(row['review_json'])
            except Exception:
                pass

        # 補充 winning_quality 欄位（不覆蓋已有的其他評審欄位）
        wq_payload = {
            'popularity_score': wq_result.get('pop_score'),
            'split_risk':       wq_result.get('split_risk'),
            'payout_quality':   wq_result.get('payout_quality'),
            'z_score':          wq_result.get('z_score'),
            'interpretation':   wq_result.get('interpretation'),
        }
        sp = wq_result.get('extreme_sum', {})
        if sp:
            wq_payload['extreme_sum'] = {
                'label':       sp.get('label'),
                'draw_sum':    sp.get('draw_sum'),
                'pct_300p':    sp.get('pct_300p'),
                'pct_1500p':   sp.get('pct_1500p'),
                'p5_300p':     sp.get('p5_300p'),
                'p95_300p':    sp.get('p95_300p'),
                'calibration_ok': sp.get('calibration_ok'),
            }
        existing['winning_quality'] = wq_payload
        existing.setdefault('auto_analyzed_at', datetime.now().isoformat())

        cur.execute('UPDATE prediction_runs SET review_json=? WHERE id=?',
                    (json.dumps(existing, ensure_ascii=False), run_id))
        conn.commit()
        conn.close()
        ok(f'run_id={run_id} review_json.winning_quality 已更新 ({sp.get("label","N/A")})')
    except Exception as ex:
        err(f'Step 4b 失敗: {ex}')


# ── Step 6: 自動解析 PENDING 預測 ────────────────────
def step_resolve_pending(lottery_type, draw, date, numbers, special):
    hdr('[Step 6] 自動解析 PENDING 預測')
    total_resolved = 0

    # 6a: 更新 DB prediction_items
    try:
        import requests
        payload = {
            'lottery_type': lottery_type,
            'draw': draw,
            'date': date,
            'numbers': numbers,
            'special': special,
        }
        resp = requests.post(
            'http://localhost:8002/api/tracking/resolve',
            json=payload, timeout=15
        )
        if resp.ok:
            data = resp.json()
            resolved = data.get('resolved', 0)
            ok(f'DB: 已解析 {resolved} 筆 PENDING 預測')
            total_resolved += resolved
        else:
            warn(f'tracking/resolve 回應異常: HTTP {resp.status_code}')
    except Exception as ex:
        warn(f'Step 6a DB resolve 失敗（API 不可用）: {ex}')

    # 6b: 更新 JSONL prediction logger（backfill actual results）
    try:
        sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))
        from engine.prediction_logger import get_logger
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        logger = get_logger()
        # 掃描所有彩種的 pending JSONL 記錄
        lottery_types = [lottery_type] if lottery_type else ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']
        jsonl_resolved = 0
        for lt in lottery_types:
            pending = logger.get_pending(lt)
            for rec in pending:
                period = rec.get('period')
                if not period:
                    continue
                # 找到 period 之後的第一期開獎
                cur.execute("""
                    SELECT draw, date, numbers, special FROM draws
                    WHERE lottery_type=? AND CAST(draw AS INTEGER) > CAST(? AS INTEGER)
                    ORDER BY CAST(draw AS INTEGER) ASC LIMIT 1
                """, (lt, period))
                row = cur.fetchone()
                if row:
                    actual_nums = json.loads(row['numbers'])
                    actual_sp = row['special']
                    updated = logger.update_result(lt, period, actual_nums, actual_sp)
                    jsonl_resolved += updated
        conn.close()
        ok(f'JSONL: 已回填 {jsonl_resolved} 筆預測結果')
        total_resolved += jsonl_resolved
    except Exception as ex:
        warn(f'Step 6b JSONL backfill 失敗: {ex}')

    return {'resolved': total_resolved}


# ── Step 7: 自動快照（為下期預測存檔）────────────────
def step_snapshot(lottery_type):
    hdr('[Step 7] 自動快照（下期預測）')
    try:
        import requests
        resp = requests.post(
            'http://localhost:8002/api/tracking/snapshot',
            json={'lottery_type': lottery_type},
            timeout=30
        )
        if resp.ok:
            data = resp.json()
            run_id = data.get('run_id') or data.get('id')
            if data.get('warning'):
                warn(data['warning'])
            else:
                ok(f'快照已儲存 (run_id={run_id})')
            return data
        else:
            warn(f'snapshot API 回應異常: HTTP {resp.status_code} — {resp.text[:200]}')
    except Exception as ex:
        warn(f'Step 7 snapshot 失敗（API 不可用）: {ex}')
    return {}


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


# ── Step 8: Shadow C Regime 並行追蹤 ──────────────────
def step_shadow_tracking(lottery_type, draw, date):
    """追蹤 shadow_C_regime 預測，寫入 data/shadow_tracking_BIG_LOTTO.jsonl"""
    hdr('[Step 8] Shadow C Regime 並行追蹤')
    if lottery_type != 'BIG_LOTTO':
        warn(f'shadow_C_regime 只追蹤 BIG_LOTTO，跳過 {lottery_type}')
        return

    try:
        from lottery_api.database import DatabaseManager
        db = DatabaseManager(DB_PATH)
        history = sorted(
            db.get_all_draws(lottery_type='BIG_LOTTO'),
            key=lambda x: (x['date'], x['draw'])
        )
        if len(history) < 50:
            warn('歷史資料不足 50 期，跳過 shadow tracking')
            return

        from tools.rsm_bootstrap import get_big_lotto_strategies_inline
        fns = {c['name']: c['predict_func'] for c in get_big_lotto_strategies_inline()}
        shadow_fn = fns.get('shadow_C_regime')
        if not shadow_fn:
            warn('shadow_C_regime 函數未找到')
            return

        bets_raw = shadow_fn(history)
        skipped = (len(bets_raw) == 0)
        skip_reason = 'selective_gate: M3+ hit_rate < 4.48%' if skipped else ''

        record = {
            'draw': draw or str(history[-1]['draw']),
            'date': date or datetime.now().strftime('%Y/%m/%d'),
            'shadow_C_bets': bets_raw,
            'skipped': skipped,
            'skip_reason': skip_reason,
        }

        tracking_path = os.path.join(ROOT, 'data', 'shadow_tracking_BIG_LOTTO.jsonl')
        with open(tracking_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        if skipped:
            warn(f'Shadow C: 選擇性過濾觸發，本期跳過 → {tracking_path}')
        else:
            ok(f'Shadow C: 已記錄 {len(bets_raw)} 注預測 → {tracking_path}')

    except Exception as ex:
        err(f'Step 8 shadow tracking 失敗: {ex}')


def _combo_b_paths():
    return (
        os.path.join(ROOT, 'data', 'combo_b_milestone.json'),
        os.path.join(ROOT, 'data', 'combo_b_tracking_POWER_LOTTO.jsonl'),
    )


def _combo_b_is_m3plus(bets, actual_nums):
    actual_set = set(actual_nums)
    for bet in bets:
        nums = bet.get('numbers', bet) if isinstance(bet, dict) else bet
        if sum(1 for n in nums if n in actual_set) >= 3:
            return True
    return False


def _combo_b_prepare_target(history, draw, date):
    target_draw = str(draw) if draw else str(history[-1]['draw'])
    idx_map = {str(d['draw']): i for i, d in enumerate(history)}
    if target_draw not in idx_map:
        raise ValueError(f'找不到 draw={target_draw}')

    idx = idx_map[target_draw]
    if idx <= 0:
        raise ValueError(f'draw={target_draw} 前無歷史')

    hist = history[:idx]
    actual = history[idx]['numbers'][:6]
    target_date = date or history[idx]['date']
    return target_draw, hist, actual, target_date


def _combo_b_predict(hist):
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_midfreq_fourier import midfreq_fourier_markov_3bet

    fourier_bets = fourier_rhythm_predict(hist, n_bets=3, window=500)
    markov_bets = midfreq_fourier_markov_3bet(hist)
    combo_b = fourier_bets[:2] + markov_bets[:3]
    return fourier_bets, markov_bets, combo_b


def _combo_b_existing_draws(tracking_path):
    existing_draws = set()
    if not os.path.exists(tracking_path):
        return existing_draws

    with open(tracking_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                existing_draws.add(str(rec.get('draw')))
            except Exception:
                continue
    return existing_draws


def _combo_b_update_milestone(milestone, milestone_path, target_draw):
    if int(target_draw) < int(milestone.get('evaluate_at_draw', 10 ** 18)):
        return

    milestone['status'] = 'NEEDS_EVALUATION'
    milestone['status_updated_at'] = datetime.now().isoformat()
    with open(milestone_path, 'w', encoding='utf-8') as f:
        json.dump(milestone, f, ensure_ascii=False, indent=2)
    warn('combo_B milestone 已達成，status -> NEEDS_EVALUATION')


# ── Step 9: combo_B Shadow Tracking (POWER_LOTTO) ───────
def step_combo_b_tracking(lottery_type, draw, date):
    """追蹤 combo_B（fourier×2 + mk×3）預測，寫入 data/combo_b_tracking_POWER_LOTTO.jsonl。"""
    hdr('[Step 9] combo_B Shadow Tracking')
    if lottery_type != 'POWER_LOTTO':
        warn(f'combo_B 只追蹤 POWER_LOTTO，跳過 {lottery_type}')
        return

    milestone_path, tracking_path = _combo_b_paths()
    if not os.path.exists(milestone_path):
        warn('找不到 combo_b_milestone.json，跳過追蹤')
        return

    try:
        with open(milestone_path, 'r', encoding='utf-8') as f:
            milestone = json.load(f)

        status = milestone.get('status', 'SHADOW_TRACKING')
        if status != 'SHADOW_TRACKING':
            warn(f'combo_B status={status}，不進行新追蹤')
            return

        from lottery_api.database import DatabaseManager

        db = DatabaseManager(DB_PATH)
        history = sorted(
            db.get_all_draws(lottery_type='POWER_LOTTO'),
            key=lambda x: (x['date'], x['draw'])
        )
        if len(history) < 120:
            warn('歷史資料不足 120 期，跳過 combo_B tracking')
            return

        target_draw, hist, actual, target_date = _combo_b_prepare_target(history, draw, date)
        fourier_bets, markov_bets, combo_b = _combo_b_predict(hist)

        fourier_hit = _combo_b_is_m3plus(fourier_bets[:2], actual)
        markov_hit = _combo_b_is_m3plus(markov_bets[:3], actual)
        combo_hit = _combo_b_is_m3plus(combo_b, actual)

        notes = 'post-draw pipeline tracking'
        if str(target_draw) >= str(milestone.get('evaluate_at_draw', '0')):
            notes = 'milestone_reached'

        rec = {
            'draw': str(target_draw),
            'date': target_date,
            'combo_b_bets': combo_b,
            'actual_numbers': actual,
            'is_m3plus': combo_hit,
            'fourier_hit': fourier_hit,
            'mk_hit': markov_hit,
            'notes': notes,
        }

        existing_draws = _combo_b_existing_draws(tracking_path)
        if str(target_draw) in existing_draws:
            warn(f'combo_B draw={target_draw} 已存在，跳過重複寫入')
        else:
            with open(tracking_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            ok(f'combo_B: 已記錄 draw={target_draw} → {tracking_path}')

        try:
            _combo_b_update_milestone(milestone, milestone_path, target_draw)
        except Exception as ex:
            warn(f'combo_B milestone 更新失敗: {ex}')

    except Exception as ex:
        err(f'Step 9 combo_B tracking 失敗: {ex}')


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
    parser.add_argument('--jackpot', type=float, default=None, help='當期頭獎金額（選填）')
    parser.add_argument('--dry-run', action='store_true', help='模擬執行，不寫入資料庫')
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
            if args.dry_run:
                hdr('[Step 1] 入庫 (DRY-RUN)')
                jackpot_text = f', jackpot={args.jackpot}' if args.jackpot is not None else ''
                ok(f'將入庫 {args.lottery} {args.draw} {numbers} SP={args.special}{jackpot_text}')
            else:
                step_insert(args.lottery, args.draw, args.date, numbers, args.special, args.jackpot)
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

    # Step 4: Winning Quality + EXTREME_SUM（對新入庫號碼）
    wq_result = None
    if args.lottery and numbers:
        wq_result = step_winning_quality(args.lottery, numbers)
        if args.draw:
            step_wq_to_db(args.lottery, args.draw, wq_result)

    # Step 5: Alerts（含 EXTREME_SUM）
    extreme_alerts = []
    if wq_result:
        sp = wq_result.get('extreme_sum', {})
        if sp.get('extreme'):
            extreme_alerts.append(
                f'{args.lottery} 和值 {sp["draw_sum"]} EXTREME_SUM '
                f'(P{sp["pct_300p"]} 超出 300p [{sp["p5_300p"]},{sp["p95_300p"]}])'
            )
        if sp.get('calibration_note'):
            extreme_alerts.append(f'THRESHOLD_DRIFT: {sp["calibration_note"]}')
    all_alerts = step_alerts(drift_alerts + extreme_alerts, rsm_results)

    # Step 6: 自動解析 PENDING 預測（需有新入庫資料）
    if not args.rsm_only and args.lottery and args.draw and args.date and numbers:
        step_resolve_pending(args.lottery, args.draw, args.date, numbers, args.special)

    # Step 7: 自動快照下期預測
    if not args.rsm_only and args.lottery:
        step_snapshot(args.lottery)

    # Step 8: Shadow C Regime 並行追蹤
    if not args.rsm_only and args.lottery:
        step_shadow_tracking(args.lottery, args.draw, args.date)

    # Step 9: combo_B Shadow Tracking
    if not args.rsm_only and args.lottery:
        step_combo_b_tracking(args.lottery, args.draw, args.date)

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
