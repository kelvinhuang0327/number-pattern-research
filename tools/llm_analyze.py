"""
LLM 策略分析 CLI — 手動觸發工具
=================================
用法:
    python3 tools/llm_analyze.py              # 分析三彩種
    python3 tools/llm_analyze.py 威力彩       # 只分析威力彩
    python3 tools/llm_analyze.py 大樂透       # 只分析大樂透
    python3 tools/llm_analyze.py 今彩539      # 只分析今彩539
    python3 tools/llm_analyze.py --show-log   # 印出最近 5 筆分析紀錄
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottery_api.engine.llm_analyzer import LLMAnalyzer, _load_strategy_states, load_recent_log, LOTTERY_NAMES

LOTTERY_MAP = {
    '大樂透':  'BIG_LOTTO',
    '威力彩':  'POWER_LOTTO',
    '今彩539': 'DAILY_539',
    '539':     'DAILY_539',
}

LOTTERY_ALL = ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']


def show_log(n: int = 5):
    records = load_recent_log(n)
    if not records:
        print("尚無分析紀錄。")
        return
    for r in records:
        lt_name = LOTTERY_NAMES.get(r.get('lottery_type', ''), r.get('lottery_type', ''))
        print(f"\n{'─'*60}")
        print(f"  {r.get('date', '?')}  {lt_name}  provider={r.get('provider', '?')}  trigger={r.get('trigger', '?')}")
        print(f"{'─'*60}")
        print(r.get('analysis', ''))


def run_analysis(lottery_types: list[str]):
    analyzer = LLMAnalyzer()
    provider = analyzer.get_provider()
    print(f"\n[LLM Analyzer] provider = {provider}")

    for lt in lottery_types:
        lt_name = LOTTERY_NAMES.get(lt, lt)
        states = _load_strategy_states(lt)
        if not states:
            print(f"\n[{lt_name}] 無策略狀態資料（尚未執行 RSM）")
            continue

        print(f"\n{'='*60}")
        print(f"  {lt_name}（{len(states)} 個策略）")
        print(f"{'='*60}")
        analysis = analyzer.analyze_rsm(lt, states, trigger='manual')
        print(analysis)

    print(f"\n[完成] 結果已寫入 lottery_api/data/llm_analysis_log.jsonl")


def main():
    args = sys.argv[1:]

    if '--show-log' in args:
        show_log()
        return

    if not args:
        run_analysis(LOTTERY_ALL)
        return

    lt = LOTTERY_MAP.get(args[0])
    if lt:
        run_analysis([lt])
    else:
        print(f"未知彩種: {args[0]}。可選: 大樂透 / 威力彩 / 今彩539")
        sys.exit(1)


if __name__ == '__main__':
    main()
