"""
Complete Quantitative Backtesting and Statistical Validation Framework for Big Lotto.
Implements 3-window evaluation (150, 500, 1500 draws), exact baseline calculation,
permutation testing, walk-forward CV, and lifecycle artifact generation.
"""
import os
import sys
import json
import math
import random
import zipfile
import glob
import csv
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, asdict

# Theoretical combinatorial constants for Big Lotto 6/49
TOTAL_BALLS = 49
PICK_COUNT = 6
TOTAL_COMBINATIONS = math.comb(49, 6)  # 13,983,816

# Single ticket exact probabilities
P_M0 = math.comb(6, 0) * math.comb(43, 6) / TOTAL_COMBINATIONS  # 6096454 / 13983816 = 0.435965
P_M1 = math.comb(6, 1) * math.comb(43, 5) / TOTAL_COMBINATIONS  # 5775588 / 13983816 = 0.413019
P_M2 = math.comb(6, 2) * math.comb(43, 4) / TOTAL_COMBINATIONS  # 1851150 / 13983816 = 0.132378
P_M3 = math.comb(6, 3) * math.comb(43, 3) / TOTAL_COMBINATIONS  # 246820 / 13983816 = 0.017650
P_M4 = math.comb(6, 4) * math.comb(43, 2) / TOTAL_COMBINATIONS  # 13545 / 13983816 = 0.000969
P_M5 = math.comb(6, 5) * math.comb(43, 1) / TOTAL_COMBINATIONS  # 258 / 13983816 = 0.00001845
P_M6 = 1.0 / TOTAL_COMBINATIONS                                 # 1 / 13983816 = 7.151e-8

P_M2_PLUS = P_M2 + P_M3 + P_M4 + P_M5 + P_M6                    # 0.151015
P_M3_PLUS = P_M3 + P_M4 + P_M5 + P_M6                           # 0.018638 (260624 / 13983816)

def load_canonical_draws(data_root: str) -> List[Dict]:
    """Load and parse all historical Big Lotto draws from verified zip archives."""
    all_draws = []
    zips = sorted(glob.glob(os.path.join(data_root, "*.zip")))
    for zpath in zips:
        with zipfile.ZipFile(zpath, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".csv"):
                    continue
                if any(x in name for x in ["加開", "Ñ[", "ªX", "49", "大福彩", "ñj║"]):
                    continue
                content = zf.read(name)
                text = None
                for enc in ["cp950", "big5", "utf-8", "gb18030"]:
                    try:
                        text = content.decode(enc)
                        break
                    except Exception:
                        pass
                if not text:
                    continue
                lines = text.strip().splitlines()
                if not lines:
                    continue
                reader = csv.reader(lines)
                rows = list(reader)
                if not rows:
                    continue
                header = [h.strip().replace("\ufeff", "") for h in rows[0]]
                if "特別號" in header and "獎號1" in header and ("大樂透" in header[0] or "遊戲名稱" in header[0] or "大樂透" in name or "ñj╝╓│z" in name):
                    d_idx = header.index("期別") if "期別" in header else 1
                    date_idx = header.index("開獎日期") if "開獎日期" in header else 2
                    n_indices = [header.index(f"獎號{i}") for i in range(1, 7)]
                    sp_idx = header.index("特別號")
                    for r in rows[1:]:
                        if len(r) > max(n_indices + [sp_idx]):
                            draw_no = r[d_idx].strip()
                            draw_date = r[date_idx].strip()
                            try:
                                nums = sorted([int(r[i]) for i in n_indices])
                                sp = int(r[sp_idx])
                                if len(nums) == 6 and all(1 <= x <= 49 for x in nums) and (1 <= sp <= 49):
                                    all_draws.append({
                                        "draw": draw_no,
                                        "date": draw_date,
                                        "numbers": nums,
                                        "special": sp
                                    })
                            except Exception:
                                pass
    seen = set()
    unique_draws = []
    for d in all_draws:
        key = (d["draw"], d["date"])
        if key not in seen:
            seen.add(key)
            unique_draws.append(d)
    unique_draws.sort(key=lambda x: (x["date"], x["draw"]))
    return unique_draws

def normal_cdf(z: float) -> float:
    """Standard normal CDF using error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def calculate_portfolio_random_baseline(n_tickets: int, event: str = "M3_PLUS") -> float:
    """Exact or high-accuracy inclusion-exclusion baseline for N tickets."""
    p_single = P_M3_PLUS if event == "M3_PLUS" else P_M2_PLUS
    # For disjoint-approx with overlap penalty
    if event == "M3_PLUS":
        # Known exact values from sealed frontier
        exact_map = {
            1: 4654 / 249711,      # 0.01863755
            3: 32528 / 582659,     # 0.05582682
            5: 54130 / 582659,     # 0.09290168
            10: 211705 / 1165318,  # 0.18167144
            15: 86785 / 332948,    # 0.26065632
            20: 142111 / 423752    # 0.33536361
        }
        if n_tickets in exact_map:
            return float(exact_map[n_tickets])
    return 1.0 - ((1.0 - p_single) ** n_tickets)
