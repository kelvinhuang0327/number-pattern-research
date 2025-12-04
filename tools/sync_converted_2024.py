#!/usr/bin/env python3
"""Sync converted_2024.csv into backend /api/auto-learning/sync-data.

Reads the CSV file `data/converted_2024.csv` and converts each row into the
expected backend history format:
{
  "date": "YYYY-MM-DD",
  "draw": "<period id>",
  "numbers": [n1, n2, n3, n4, n5, n6],  # ignores special number
  "lotteryType": "BIG_LOTTO"
}

Lottery rules are inferred for Taiwan Big Lotto (6 picks from 1..49).

Usage:
  python tools/sync_converted_2024.py --host http://localhost:5001 \
      --file data/converted_2024.csv --lottery BIG_LOTTO

Requires `requests` library:
  pip install requests
"""
import csv
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

try:
    import requests  # type: ignore
except ImportError:
    print("[ERROR] Missing requests. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)

def parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw  # fallback unchanged

def load_history(csv_path: Path, lottery_type: str) -> list:
    history = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Expected headers: 期數,日期,號碼1..號碼6,特別號
        for row in reader:
            try:
                period = row.get('期數') or row.get('draw') or ''
                date = parse_date(row.get('日期', ''))
                # Extract first 6 numbers; ignore special number
                numbers = []
                for i in range(1, 7):
                    key = f'號碼{i}'
                    val = row.get(key)
                    if val is None or val.strip() == '':
                        raise ValueError(f'Missing {key} in row {period}')
                    numbers.append(int(val))
                history.append({
                    'date': date,
                    'draw': str(period),
                    'numbers': numbers,
                    'lotteryType': lottery_type
                })
            except Exception as e:
                print(f"[WARN] Skipping row due to error: {e}")
    return history

def build_rules(lottery_type: str) -> dict:
    return {
        'lotteryType': lottery_type,
        'minNumber': 1,
        'maxNumber': 49,
        'pickCount': 6,
        'name': 'Taiwan Big Lotto',
    }

def main():
    ap = argparse.ArgumentParser(description="Sync converted_2024.csv to backend")
    ap.add_argument('--host', default='http://localhost:5001', help='Backend host base URL')
    ap.add_argument('--file', default='data/converted_2024.csv', help='CSV file path')
    ap.add_argument('--lottery', default='BIG_LOTTO', help='Lottery type label to assign')
    ap.add_argument('--limit', type=int, default=0, help='Optional limit on number of rows (0 = all)')
    args = ap.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"[ERROR] File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    history = load_history(csv_path, args.lottery)
    if args.limit > 0:
        history = history[:args.limit]

    if len(history) < 10:
        print(f"[ERROR] Need at least 10 rows, got {len(history)}", file=sys.stderr)
        sys.exit(1)

    rules = build_rules(args.lottery)
    payload = {
        'history': history,
        'lotteryRules': rules,
        'generations': 0,  # not used in sync
        'population_size': 0
    }

    url = f"{args.host}/api/auto-learning/sync-data"
    print(f"[INFO] POST {url} rows={len(history)}")
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"[ERROR] Sync failed {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] Sync success: {resp.json()}")

    # Quick smoke predictions
    predict_models = ["prophet", "xgboost", "backend_optimized"]
    for m in predict_models:
        url2 = f"{args.host}/api/predict-from-backend"
        pld = {"lotteryType": args.lottery, "modelType": m}
        print(f"[INFO] Predict {m} -> {url2}")
        r2 = requests.post(url2, json=pld, timeout=30)
        if r2.status_code == 200:
            print(f"[PREDICT {m}] {r2.json()}")
        else:
            print(f"[PREDICT {m} ERROR] {r2.status_code}: {r2.text}")

if __name__ == '__main__':
    main()
