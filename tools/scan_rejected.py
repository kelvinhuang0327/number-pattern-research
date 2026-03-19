"""
Rejected 策略重測條件掃描器
=============================
掃描 rejected/*.json 的 retest_conditions，
自動偵測數值門檻是否已觸發，輸出重測候選報告。

用法:
    python3 tools/scan_rejected.py              # 完整報告
    python3 tools/scan_rejected.py --triggered  # 只看已觸發項目
    python3 tools/scan_rejected.py --lottery 今彩539  # 過濾彩種
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REJECTED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rejected')
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data')

LOTTERY_KEYWORDS = {
    'BIG_LOTTO':   ['大樂透', 'biglotto', 'big_lotto'],
    'POWER_LOTTO': ['威力彩', 'powerlotto', 'power_lotto', 'power'],
    'DAILY_539':   ['539', 'daily_539'],
}

# 目前資料庫期數（從 DB 查詢真實總數）
def get_current_data_sizes() -> dict:
    sizes = {}
    try:
        db_path = os.path.join(DATA_DIR, 'lottery_v2.db')
        if os.path.exists(db_path):
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            for lt in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
                cur.execute("SELECT COUNT(*) FROM draws WHERE lottery_type=?", (lt,))
                row = cur.fetchone()
                if row:
                    sizes[lt] = row[0]
            conn.close()
    except Exception:
        pass
    # fallback: strategy_states total_records (RSM 記錄數，不代表 DB 全量)
    if not sizes:
        for lt in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
            path = os.path.join(DATA_DIR, f'strategy_states_{lt}.json')
            if not os.path.exists(path):
                continue
            try:
                d = json.load(open(path, encoding='utf-8'))
                records = [v.get('total_records', 0) for v in d.values()]
                if records:
                    sizes[lt] = max(records)
            except Exception:
                pass
    return sizes


def get_rsm_states() -> dict:
    """載入三彩種策略狀態: {lt: {strategy_name: state_dict}}"""
    result = {}
    for lt in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
        path = os.path.join(DATA_DIR, f'strategy_states_{lt}.json')
        if os.path.exists(path):
            try:
                result[lt] = json.load(open(path, encoding='utf-8'))
            except Exception:
                result[lt] = {}
    return result


# ─────────────────────────────────────────────
# 自動偵測邏輯
# ─────────────────────────────────────────────

def _infer_lottery_from_filename(fname: str):
    """從檔名推斷彩種。"""
    n = fname.lower()
    if 'biglotto' in n or 'big_lotto' in n:
        return 'BIG_LOTTO'
    if 'power' in n or 'powerlotto' in n:
        return 'POWER_LOTTO'
    if '539' in n or 'daily_539' in n:
        return 'DAILY_539'
    return None


def _detect_trigger(condition_text, data_sizes, rsm_states, fname=''):
    """
    嘗試自動偵測條件是否觸發。
    Returns: (triggered: bool, reason: str)
    若無法自動偵測，返回 (None, '需人工審核')
    """
    text = condition_text if isinstance(condition_text, str) else str(condition_text)

    # 1. 資料量門檻: "資料量達 5000期" / "dataset>5000" / "超過 3000期"
    m = re.search(r'(?:資料量|dataset)[^0-9]*?([0-9,]+)\s*期', text)
    if not m:
        m = re.search(r'dataset\s*[>≥]\s*([0-9,]+)', text)
    if m:
        threshold = int(m.group(1).replace(',', ''))
        # 優先從條件文字猜彩種，其次從檔名推斷
        lt_found = None
        for lt, keywords in LOTTERY_KEYWORDS.items():
            if any(kw in text.lower() for kw in keywords):
                lt_found = lt
                break
        if not lt_found:
            lt_found = _infer_lottery_from_filename(fname)
        if lt_found:
            current = data_sizes.get(lt_found, 0)
            lt_name = lt_found.replace('_', '')
            if current >= threshold:
                return True, f"資料量 {current} 期 ≥ 門檻 {threshold} 期 ({lt_name})"
            else:
                return False, f"資料量 {current} 期 < 門檻 {threshold} 期 ({lt_name})"
        # 仍無法判斷彩種 → 人工審核
        return None, f"需人工審核（無法判斷彩種，門檻={threshold}期）"

    # 2. RSM Edge 持續負: "若 X 在 60 期 RSM Edge 連續負超過 N 期"
    m = re.search(r'連續.{0,10}負.{0,10}(\d+)\s*期', text)
    if m:
        threshold = int(m.group(1))
        # 掃描所有策略的 consecutive_neg_30p
        for lt, states in rsm_states.items():
            for name, s in states.items():
                if name.lower() in text.lower() or any(kw in text.lower() for kw in LOTTERY_KEYWORDS.get(lt, [])):
                    neg = s.get('consecutive_neg_30p', 0)
                    if neg >= threshold:
                        return True, f"{name} 連續負 {neg} 期 ≥ 門檻 {threshold} 期"
                    else:
                        return False, f"{name} 連續負 {neg} 期 < 門檻 {threshold} 期"
        return None, '需人工審核（找不到對應策略）'

    # 3. RSM Edge 跌至負: "若 edge 在 500 期窗口跌至零以下"
    if '跌至零以下' in text or 'edge.*負' in text.lower() or '負.*edge' in text.lower():
        return None, '需人工審核（RSM Edge 條件，請查閱 strategy_states）'

    return None, '需人工審核（條件無法自動偵測）'


# ─────────────────────────────────────────────
# 主掃描邏輯
# ─────────────────────────────────────────────

def scan(filter_lottery: str = None, only_triggered: bool = False):
    data_sizes = get_current_data_sizes()
    rsm_states = get_rsm_states()

    print(f"\n{'='*70}")
    print(f"  Rejected 策略重測掃描報告")
    print(f"  目前資料量: " + "  ".join(f"{lt.replace('_', '')}={n}期" for lt, n in data_sizes.items()))
    print(f"{'='*70}")

    files = sorted(f for f in os.listdir(REJECTED_DIR) if f.endswith('.json'))

    triggered_list = []
    manual_list = []
    no_condition_list = []

    for fname in files:
        path = os.path.join(REJECTED_DIR, fname)
        try:
            d = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue

        # 彩種過濾
        if filter_lottery:
            lt_filter = {
                '大樂透': 'biglotto', '威力彩': 'power', '539': '539',
                '今彩539': '539',
            }.get(filter_lottery, filter_lottery.lower())
            if lt_filter not in fname.lower() and lt_filter not in d.get('strategy', '').lower():
                continue

        strategy_name = d.get('strategy', fname.replace('.json', ''))
        rejected_date = d.get('rejected_date', '?')
        conditions = d.get('retest_conditions', None)

        if not conditions:
            no_condition_list.append((strategy_name, rejected_date))
            continue

        if isinstance(conditions, str):
            conditions = [conditions]

        for cond in conditions:
            triggered, reason = _detect_trigger(cond, data_sizes, rsm_states, fname)
            item = {
                'strategy': strategy_name,
                'rejected_date': rejected_date,
                'condition': cond,
                'triggered': triggered,
                'reason': reason,
                'file': fname,
            }
            if triggered is True:
                triggered_list.append(item)
            else:
                manual_list.append(item)

    # 輸出已觸發
    print(f"\n🔴 已觸發重測條件 ({len(triggered_list)} 項)")
    print(f"{'─'*70}")
    if triggered_list:
        for item in triggered_list:
            print(f"  [{item['rejected_date']}] {item['strategy']}")
            print(f"    條件: {item['condition'][:80]}")
            print(f"    觸發: {item['reason']}")
            print()
    else:
        print("  （無）\n")

    if not only_triggered:
        # 按人工審核
        manual_auto_no = [x for x in manual_list if x['triggered'] is False]
        manual_review = [x for x in manual_list if x['triggered'] is None]

        print(f"\n🟡 條件尚未達到 ({len(manual_auto_no)} 項，自動偵測）")
        print(f"{'─'*70}")
        for item in manual_auto_no[:10]:  # 最多顯示10條
            print(f"  [{item['rejected_date']}] {item['strategy']}")
            print(f"    {item['reason']}")
        if len(manual_auto_no) > 10:
            print(f"  ... 還有 {len(manual_auto_no)-10} 項（使用 --triggered 只看觸發項）")

        print(f"\n⚪ 需人工審核 ({len(manual_review)} 項)")
        print(f"{'─'*70}")
        for item in manual_review[:8]:
            print(f"  [{item['rejected_date']}] {item['strategy']}")
            print(f"    條件: {item['condition'][:70]}...")
        if len(manual_review) > 8:
            print(f"  ... 還有 {len(manual_review)-8} 項")

        print(f"\n⚫ 無重測條件 ({len(no_condition_list)} 項，永久歸檔）")

    print(f"\n{'='*70}")
    print(f"  摘要: 觸發={len(triggered_list)}  未達={len(manual_auto_no) if not only_triggered else '?'}  人工審核={len(manual_review) if not only_triggered else '?'}  無條件={len(no_condition_list)}")
    print(f"{'='*70}\n")

    return triggered_list


def main():
    args = sys.argv[1:]
    only_triggered = '--triggered' in args
    lottery_filter = None
    if '--lottery' in args:
        idx = args.index('--lottery')
        if idx + 1 < len(args):
            lottery_filter = args[idx + 1]

    triggered = scan(filter_lottery=lottery_filter, only_triggered=only_triggered)

    if triggered:
        print("\n建議：以上策略已達重測條件，可安排回測驗證。")
    else:
        print("\n目前無策略觸發數值重測條件。")


if __name__ == '__main__':
    main()
