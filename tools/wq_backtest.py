"""
P2-1: Winning Quality 回測驗證

目標：驗證 popularity_score 是否真正與「分獎人數少→獎金高」相關。
由於無真實分獎記錄，使用以下 proxy 策略：

1. 計算每期開獎號碼的 popularity_score
2. 分析 LOW/MED/HIGH split_risk 分布
3. 如有中獎紀錄，驗證 LOW risk 期的頭獎金額是否高於 HIGH risk 期
4. 輸出各彩種的 WQ 分布統計與趨勢

執行：
  python3 tools/wq_backtest.py
  python3 tools/wq_backtest.py --lottery BIG_LOTTO --periods 300
"""

import sys, json, argparse
import numpy as np
sys.path.insert(0, 'lottery_api')

from engine.winning_quality import analyze as wq_analyze
import sqlite3

def run_wq_backtest(lottery_type: str, periods: int = 300):
    conn = sqlite3.connect('lottery_api/data/lottery_v2.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT draw, date, numbers, special
        FROM draws WHERE lottery_type=?
        ORDER BY CAST(draw AS INTEGER) DESC
        LIMIT ?
    """, (lottery_type, periods))
    draws = list(reversed(cur.fetchall()))

    if not draws:
        print(f'[WQ Backtest] No data for {lottery_type}')
        conn.close()
        return

    print(f'\n{"="*60}')
    print(f'[WQ Backtest] {lottery_type}  ({len(draws)} 期)')
    print(f'{"="*60}')

    results = []
    for i, row in enumerate(draws):
        nums = json.loads(row['numbers'])
        # Use historical data up to this draw for baseline
        hist_draws = draws[:i] if i > 0 else draws[:1]
        try:
            wq = wq_analyze(nums, lottery_type, recent_n=min(len(hist_draws), 300))
            results.append({
                'draw': row['draw'],
                'date': row['date'],
                'numbers': nums,
                'pop_score': wq['pop_score'],
                'split_risk': wq['split_risk'],
                'payout_quality': wq['payout_quality'],
                'z_score': wq.get('z_score', 0),
            })
        except Exception as e:
            pass

    if not results:
        print('No results computed')
        conn.close()
        return

    # Distribution analysis
    scores = [r['pop_score'] for r in results]
    low_cnt = sum(1 for r in results if r['split_risk'] == 'LOW')
    med_cnt = sum(1 for r in results if r['split_risk'] == 'MED')
    high_cnt = sum(1 for r in results if r['split_risk'] == 'HIGH')
    n = len(results)

    print(f'\n📊 Popularity Score 分布:')
    print(f'  均值: {np.mean(scores):.1f}  Std: {np.std(scores):.1f}')
    print(f'  Min: {min(scores)}  Max: {max(scores)}')
    print(f'  P25: {np.percentile(scores,25):.0f}  P50: {np.percentile(scores,50):.0f}  P75: {np.percentile(scores,75):.0f}')
    print(f'\n🏷️  Split Risk 分布:')
    print(f'  LOW  (低分獎風險): {low_cnt}/{n} = {low_cnt/n*100:.1f}%')
    print(f'  MED  (中分獎風險): {med_cnt}/{n} = {med_cnt/n*100:.1f}%')
    print(f'  HIGH (高分獎風險): {high_cnt}/{n} = {high_cnt/n*100:.1f}%')

    # Trend: last 30 vs prior
    if len(results) >= 60:
        recent_30 = [r['pop_score'] for r in results[-30:]]
        prior_30 = [r['pop_score'] for r in results[-60:-30]]
        print(f'\n📈 趨勢 (最近30期 vs 前30期):')
        print(f'  最近30期均值: {np.mean(recent_30):.1f}')
        print(f'  前30期均值:   {np.mean(prior_30):.1f}')
        trend = '⬆ 上升 (近期號碼偏熱門)' if np.mean(recent_30) > np.mean(prior_30) else '⬇ 下降 (近期號碼偏冷門)'
        print(f'  趨勢: {trend}')

    # Recent 10 draws
    print(f'\n📋 最近10期 WQ 分析:')
    print(f'  {"期號":>12}  {"日期":>12}  {"PopScore":>8}  {"SplitRisk":>10}  {"PayoutQ":>8}')
    for r in results[-10:]:
        print(f'  {r["draw"]:>12}  {r["date"]:>12}  {r["pop_score"]:>8}  {r["split_risk"]:>10}  {r["payout_quality"]:>8}')

    # WQ vs Hit correlation (using resolved prediction_results if available)
    cur.execute("""
        SELECT pr.actual_draw, pr.hit_count, pr.split_risk, pr.wq_score
        FROM prediction_results pr
        JOIN prediction_items i ON i.id = pr.item_id
        JOIN prediction_runs r ON r.id = i.run_id
        WHERE r.lottery_type=? AND pr.wq_score IS NOT NULL
        ORDER BY pr.actual_draw
    """, (lottery_type,))
    pred_rows = cur.fetchall()

    if pred_rows:
        print(f'\n🔗 WQ vs 命中率相關性分析 ({len(pred_rows)} 筆預測結果):')
        low_hits = [r['hit_count'] for r in pred_rows if r['split_risk'] == 'LOW']
        med_hits = [r['hit_count'] for r in pred_rows if r['split_risk'] == 'MED']
        high_hits = [r['hit_count'] for r in pred_rows if r['split_risk'] == 'HIGH']

        if low_hits:
            print(f'  LOW  split_risk 期 avg_hit={np.mean(low_hits):.3f} (n={len(low_hits)})')
        if med_hits:
            print(f'  MED  split_risk 期 avg_hit={np.mean(med_hits):.3f} (n={len(med_hits)})')
        if high_hits:
            print(f'  HIGH split_risk 期 avg_hit={np.mean(high_hits):.3f} (n={len(high_hits)})')
        print(f'  [NOTE] WQ 與命中率不應高度相關（命中率=策略效果，WQ=分獎優化）')
        print(f'  [NOTE] WQ 的驗證需要真實頭獎金額資料（P2-1 待補）')

    conn.close()

    # Summary verdict
    print(f'\n🎯 P2-1 驗證狀態:')
    print(f'  Proxy 模型已建立: ✅')
    print(f'  分布統計可計算: ✅')
    print(f'  真實分獎資料: ❌ (待補 — 需爬取台灣彩券分獎資料)')
    print(f'  最終驗證結論: [UNSURE] — 需 300 期真實分獎記錄才能確認 proxy 有效性')

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default=None, help='BIG_LOTTO / POWER_LOTTO / DAILY_539')
    parser.add_argument('--periods', type=int, default=300)
    args = parser.parse_args()

    lotteries = [args.lottery] if args.lottery else ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']
    for lt in lotteries:
        run_wq_backtest(lt, args.periods)


if __name__ == '__main__':
    main()
