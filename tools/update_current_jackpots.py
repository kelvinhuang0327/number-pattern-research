#!/usr/bin/env python3
"""Update current jackpot assumptions and refresh hedge-fund outputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from analysis.payout.sync import refresh_hedge_fund_outputs


JACKPOT_PATH = os.path.join(project_root, 'lottery_api', 'data', 'current_jackpots.json')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('lottery_type', choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'])
    parser.add_argument('jackpot', type=int)
    parser.add_argument('--source', default='manual_cli')
    args = parser.parse_args()

    payload = json.load(open(JACKPOT_PATH, 'r', encoding='utf-8'))
    payload[args.lottery_type] = {
        'jackpot': args.jackpot,
        'source': args.source,
        'updated_at': date.today().isoformat(),
    }

    with open(JACKPOT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    refreshed = refresh_hedge_fund_outputs(project_root)
    print(json.dumps({
        'lottery_type': args.lottery_type,
        'jackpot': args.jackpot,
        'source': args.source,
        'hedge_fund_refreshed': refreshed,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
