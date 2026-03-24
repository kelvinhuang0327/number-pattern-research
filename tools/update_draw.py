#!/usr/bin/env python3
"""
快速開獎入庫工具
用法:
  python3 tools/update_draw.py                          # 互動模式
  python3 tools/update_draw.py 539 115000073 03 11 15 33 39
  python3 tools/update_draw.py 大樂透 115000038 5 12 20 33 41 49 --special 7
  python3 tools/update_draw.py 威力彩 115000025 3 8 15 22 27 35 --special 4
  python3 tools/update_draw.py --rsm-only               # 只跑RSM更新
"""

import sys
import json
import sqlite3
import subprocess
import argparse
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"

LOTTERY_MAP = {
    "539": "DAILY_539", "今彩539": "DAILY_539", "DAILY_539": "DAILY_539",
    "大樂透": "BIG_LOTTO", "BIG_LOTTO": "BIG_LOTTO", "lotto": "BIG_LOTTO",
    "威力彩": "POWER_LOTTO", "POWER_LOTTO": "POWER_LOTTO", "power": "POWER_LOTTO",
}

RSM_TYPE_MAP = {
    "DAILY_539": "DAILY_539",
    "BIG_LOTTO": "BIG_LOTTO",
    "POWER_LOTTO": "POWER_LOTTO",
}

NUMBER_RANGE = {
    "DAILY_539": (1, 39, 5),    # min, max, count
    "BIG_LOTTO": (1, 49, 6),
    "POWER_LOTTO": (1, 38, 6),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_existing(lottery_type, draw):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT draw, date, numbers FROM draws WHERE lottery_type=? AND draw=?",
                (lottery_type, draw))
    row = cur.fetchone()
    conn.close()
    return row


def get_latest_draw(lottery_type):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1",
        (lottery_type,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def insert_draw(lottery_type, draw, draw_date, numbers, special=0):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?,?,?,?,?)",
            (draw, draw_date, lottery_type, json.dumps(sorted(numbers)), special)
        )
        conn.commit()
        print(f"  ✅ 已插入: {lottery_type} {draw} → {sorted(numbers)}" +
              (f" SP={special}" if special else ""))
        return True
    except sqlite3.IntegrityError:
        print(f"  ⚠️  已存在: {lottery_type} {draw}")
        return False
    finally:
        conn.close()


def run_rsm(lottery_type):
    rsm_arg = RSM_TYPE_MAP.get(lottery_type, lottery_type)
    print(f"\n  🔄 執行 RSM bootstrap ({rsm_arg})...")
    script = Path(__file__).parent / "rsm_bootstrap.py"
    result = subprocess.run(
        [sys.executable, str(script), "--lottery", rsm_arg],
        capture_output=True, text=True,
        cwd=Path(__file__).parent.parent
    )
    if result.returncode == 0:
        # 只顯示關鍵行
        for line in result.stdout.split("\n"):
            if any(k in line for k in ["★", "Edge", "策略狀態", "STABLE", "ACCEL", "REGIME", "DECEL"]):
                print(" ", line)
        print("  ✅ RSM 更新完成")
    else:
        print("  ❌ RSM 失敗:", result.stderr[:200])


def interactive_mode():
    print("=" * 50)
    print("  開獎入庫工具（互動模式）")
    print("=" * 50)

    # 選彩種
    print("\n彩種：")
    print("  1. 今彩539  2. 大樂透  3. 威力彩")
    choice = input("選擇 [1-3]: ").strip()
    lt_map = {"1": "DAILY_539", "2": "BIG_LOTTO", "3": "POWER_LOTTO"}
    lottery_type = lt_map.get(choice)
    if not lottery_type:
        print("❌ 無效選擇")
        return

    # 顯示最新期
    latest = get_latest_draw(lottery_type)
    if latest:
        print(f"\n  DB最新: {latest['draw']} ({latest['date']}) {json.loads(latest['numbers'])}")

    # 期號
    draw = input("\n期號: ").strip()
    if not draw:
        return

    # 日期
    today = date.today().strftime("%Y/%m/%d")
    draw_date = input(f"開獎日期 [{today}]: ").strip() or today

    # 號碼
    n_min, n_max, n_count = NUMBER_RANGE[lottery_type]
    print(f"\n號碼（{n_count}個，{n_min}-{n_max}）")
    nums_input = input("號碼（空格分隔）: ").strip()

    try:
        numbers = [int(x) for x in nums_input.split()]
        assert len(numbers) == n_count, f"需要 {n_count} 個號碼"
        assert all(n_min <= n <= n_max for n in numbers), f"號碼需在 {n_min}-{n_max}"
    except (ValueError, AssertionError) as e:
        print(f"❌ 號碼錯誤: {e}")
        return

    special = 0
    if lottery_type in ("BIG_LOTTO", "POWER_LOTTO"):
        sp = input("特別號: ").strip()
        if sp:
            special = int(sp)

    # 確認
    print(f"\n  即將插入: {lottery_type} {draw} ({draw_date})")
    print(f"  號碼: {sorted(numbers)}" + (f"  特別號: {special}" if special else ""))
    confirm = input("\n確認插入？[Y/n]: ").strip().lower()
    if confirm == 'n':
        print("已取消")
        return

    ok = insert_draw(lottery_type, draw, draw_date, numbers, special)
    if ok:
        run_rsm_q = input("\n執行 RSM 更新？[Y/n]: ").strip().lower()
        if run_rsm_q != 'n':
            run_rsm(lottery_type)


def parse_date_from_draw(draw, lottery_type):
    """從期號推算大略日期（民國→西元）"""
    try:
        draw_int = int(draw)
        # 民國年 = draw_int // 1000000
        roc_year = draw_int // 1000000
        ad_year = roc_year + 1911
        return f"{ad_year}/01/01"  # 近似日期，實際以手動輸入為準
    except:
        return date.today().strftime("%Y/%m/%d")


def cli_mode(args):
    lottery_type = LOTTERY_MAP.get(args.lottery)
    if not lottery_type:
        print(f"❌ 不認識彩種: {args.lottery}")
        print(f"   支援: {', '.join(LOTTERY_MAP.keys())}")
        sys.exit(1)

    draw = args.draw
    n_min, n_max, n_count = NUMBER_RANGE[lottery_type]

    try:
        numbers = [int(x) for x in args.numbers]
        assert len(numbers) == n_count, f"需要 {n_count} 個號碼，輸入了 {len(numbers)} 個"
        assert all(n_min <= n <= n_max for n in numbers), f"號碼需在 {n_min}-{n_max}"
    except (ValueError, AssertionError) as e:
        print(f"❌ 號碼錯誤: {e}")
        sys.exit(1)

    special = args.special or 0
    draw_date = args.date or date.today().strftime("%Y/%m/%d")

    # 確認現有最新
    latest = get_latest_draw(lottery_type)
    if latest:
        print(f"  DB最新: {latest['draw']} ({latest['date']})")

    ok = insert_draw(lottery_type, draw, draw_date, numbers, special)
    if ok and not args.no_rsm:
        run_rsm(lottery_type)


def main():
    parser = argparse.ArgumentParser(description="快速開獎入庫工具")
    parser.add_argument("lottery", nargs="?", help="彩種（539/大樂透/威力彩）")
    parser.add_argument("draw", nargs="?", help="期號")
    parser.add_argument("numbers", nargs="*", help="號碼")
    parser.add_argument("--special", "-s", type=int, default=0, help="特別號（大樂透/威力彩）")
    parser.add_argument("--date", "-d", help="開獎日期 YYYY/MM/DD（預設今天）")
    parser.add_argument("--no-rsm", action="store_true", help="不執行RSM更新")
    parser.add_argument("--rsm-only", action="store_true", help="只執行RSM ALL更新")
    parser.add_argument("--status", action="store_true", help="顯示各彩種最新期號")

    args = parser.parse_args()

    if args.rsm_only:
        print("執行 RSM ALL 更新...")
        for lt in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
            run_rsm(lt)
        return

    if args.status:
        for lt in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
            row = get_latest_draw(lt)
            if row:
                print(f"  {lt}: {row['draw']} ({row['date']}) {json.loads(row['numbers'])}")
        return

    if not args.lottery:
        interactive_mode()
    else:
        if not args.draw or not args.numbers:
            parser.print_help()
            sys.exit(1)
        cli_mode(args)


if __name__ == "__main__":
    main()
