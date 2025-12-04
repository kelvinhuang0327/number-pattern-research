#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark all lottery types and generate a markdown report.

Usage:
    python3 run_benchmark_and_report.py

The script will:
1. Call the existing benchmark_prediction_speed.py for each lottery type.
2. Capture the average latency.
3. Write a markdown file `benchmark_report.md` in the project root.
"""
import subprocess
import sys
import os
import re
from datetime import datetime

# Configuration
LOTTERY_TYPES = ["BIG_LOTTO", "POWER_LOTTO", "LOTTO_539"]
MODEL_TYPE = "ensemble"
ITERATIONS = 20
BENCHMARK_SCRIPT = os.path.join(os.path.dirname(__file__), "benchmark_prediction_speed.py")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "benchmark_report.md")


def run_one(lottery_type: str) -> float:
    """Run benchmark for a single lottery type and return average ms."""
    try:
        result = subprocess.run(
            [sys.executable, BENCHMARK_SCRIPT, lottery_type, MODEL_TYPE, str(ITERATIONS)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Benchmark failed for {lottery_type}: {e}")
        return None
    # Parse the "平均耗時" line
    match = re.search(r"平均耗時：([0-9.]+) ms", result.stdout)
    if match:
        return float(match.group(1))
    else:
        # Fallback: try to extract the last numeric line
        numbers = re.findall(r"([0-9.]+) ms", result.stdout)
        if numbers:
            return float(numbers[-1])
    return None


def main():
    print("🚀 Running benchmark for all lottery types…")
    results = {}
    for lt in LOTTERY_TYPES:
        avg = run_one(lt)
        results[lt] = avg
        print(f"{lt}: {avg if avg is not None else 'Failed'} ms")

    # Generate markdown report
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 📊 預測速度基準報告\n\n")
        f.write(f"生成時間：{now}\n\n")
        f.write("| 彩券類型 | 平均耗時 (ms) | 判斷 (O(1) 快速) |\n")
        f.write("|----------|--------------|-------------------|\n")
        for lt, avg in results.items():
            status = "✅" if avg is not None and avg < 0.05 else "⚠️" if avg is not None else "❌"
            f.write(f"| {lt} | {avg if avg is not None else '失敗'} | {status} |\n")
        f.write("\n*若所有項目均顯示 ✅，即代表分類存儲已生效，預測時間接近毫秒級。*\n")
    print(f"✅ Report written to {REPORT_PATH}")

if __name__ == "__main__":
    main()
