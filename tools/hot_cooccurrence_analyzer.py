#!/usr/bin/env python3
"""
熱號與共現分析模組 (Hot Number & Co-occurrence Analyzer)

Phase 1 核心模組：
1. 動態窗口熱號分析
2. 號碼共現矩陣建立
3. 高共現組合識別
4. 共現規則選號應用
"""
import sys
import os
import io
import argparse
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class HotCooccurrenceAnalyzer:
    """
    熱號與共現分析器
    
    支援：
    - 動態窗口熱號分析
    - 號碼共現矩陣計算
    - 高共現組合識別
    """
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.rules = get_lottery_rules(lottery_type)
        self.min_num = self.rules['minNumber']
        self.max_num = self.rules['maxNumber']
        self.pick_count = self.rules['pickCount']
        
    def get_data(self) -> List[Dict]:
        """獲取歷史數據 (ASC: 最舊 -> 最新)"""
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
    
    def get_hot_numbers(
        self, 
        history: List[Dict], 
        window_size: int = 50,
        top_n: Optional[int] = None
    ) -> List[Tuple[int, int]]:
        """
        動態窗口熱號分析
        
        Args:
            history: 歷史開獎數據 (ASC)
            window_size: 分析窗口大小
            top_n: 返回前 N 個熱號（預設返回全部）
            
        Returns:
            熱號列表 [(號碼, 出現次數), ...]，按出現次數降序
        """
        # 取最近 window_size 期
        recent_history = history[-window_size:] if len(history) > window_size else history
        
        # 統計各號碼出現次數
        all_numbers = [num for draw in recent_history for num in draw['numbers']]
        freq_counter = Counter(all_numbers)
        
        # 按頻率降序排列
        sorted_freq = freq_counter.most_common(top_n)
        
        return sorted_freq
    
    def build_cooccurrence_matrix(
        self, 
        history: List[Dict], 
        window_size: int = 100,
        normalize: bool = True
    ) -> pd.DataFrame:
        """
        建立號碼共現矩陣
        
        Args:
            history: 歷史開獎數據 (ASC)
            window_size: 分析窗口大小
            normalize: 是否正規化為共現率 (0-1)
            
        Returns:
            共現矩陣 DataFrame (N x N)
        """
        # 取最近 window_size 期
        recent_history = history[-window_size:] if len(history) > window_size else history
        
        # 初始化共現計數矩陣
        num_range = self.max_num - self.min_num + 1
        co_matrix = np.zeros((num_range, num_range), dtype=np.int32)
        
        # 統計共現次數
        for draw in recent_history:
            numbers = draw['numbers']
            for i, num1 in enumerate(numbers):
                for num2 in numbers[i+1:]:
                    idx1 = num1 - self.min_num
                    idx2 = num2 - self.min_num
                    co_matrix[idx1, idx2] += 1
                    co_matrix[idx2, idx1] += 1  # 對稱
        
        # 轉換為 DataFrame
        index_labels = list(range(self.min_num, self.max_num + 1))
        df = pd.DataFrame(co_matrix, index=index_labels, columns=index_labels)
        
        # 正規化
        if normalize and len(recent_history) > 0:
            max_co = len(recent_history)  # 理論最大共現次數
            df = df / max_co
        
        return df
    
    def get_high_cooccurrence_pairs(
        self, 
        co_matrix: pd.DataFrame, 
        threshold: float = 0.3,
        top_n: int = 20
    ) -> List[Tuple[Tuple[int, int], float]]:
        """
        識別高共現號碼組合
        
        Args:
            co_matrix: 共現矩陣 DataFrame
            threshold: 共現率閾值
            top_n: 返回前 N 個高共現組合
            
        Returns:
            高共現組合列表 [((num1, num2), 共現率), ...]
        """
        pairs = []
        
        for i in co_matrix.index:
            for j in co_matrix.columns:
                if i < j:  # 避免重複（只取上三角）
                    rate = co_matrix.loc[i, j]
                    if rate >= threshold:
                        pairs.append(((i, j), rate))
        
        # 按共現率降序排列
        pairs.sort(key=lambda x: x[1], reverse=True)
        
        return pairs[:top_n]
    
    def get_hot_cold_numbers(
        self, 
        history: List[Dict], 
        window_size: int = 50
    ) -> Tuple[List[int], List[int]]:
        """
        獲取熱號與冷號
        
        Args:
            history: 歷史數據
            window_size: 分析窗口
            
        Returns:
            (熱號列表, 冷號列表)
        """
        hot_freq = self.get_hot_numbers(history, window_size)
        
        # 所有號碼
        all_nums = set(range(self.min_num, self.max_num + 1))
        
        # 熱號：頻率前 1/3
        hot_count = len(hot_freq) // 3
        hot_nums = [num for num, freq in hot_freq[:hot_count]]
        
        # 計算冷號（頻率最低 1/3 或未出現）
        appeared_nums = {num for num, freq in hot_freq}
        cold_from_data = [num for num, freq in hot_freq[-hot_count:]]
        cold_from_zero = list(all_nums - appeared_nums)
        
        cold_nums = cold_from_zero + cold_from_data
        
        return hot_nums, cold_nums
    
    def apply_cooccurrence_rules(
        self, 
        hot_numbers: List[int], 
        co_matrix: pd.DataFrame,
        pick_count: int = 6,
        cooccurrence_weight: float = 0.3
    ) -> List[int]:
        """
        應用共現規則選號
        
        策略：
        1. 從熱號中選擇基礎號碼
        2. 根據共現關係加分
        3. 優先選擇與其他候選號共現率高的號碼
        
        Args:
            hot_numbers: 熱號列表
            co_matrix: 共現矩陣
            pick_count: 選號數量
            cooccurrence_weight: 共現權重
            
        Returns:
            優化後的選號列表
        """
        if len(hot_numbers) <= pick_count:
            return sorted(hot_numbers)
        
        # 計算每個熱號的綜合得分
        scores = {}
        
        for i, num in enumerate(hot_numbers):
            # 基礎分：排名分（越熱越高）
            rank_score = (len(hot_numbers) - i) / len(hot_numbers)
            
            # 共現分：與其他熱號的平均共現率
            co_scores = []
            for other_num in hot_numbers:
                if other_num != num:
                    try:
                        co_rate = co_matrix.loc[num, other_num]
                        co_scores.append(co_rate)
                    except:
                        co_scores.append(0)
            
            co_score = np.mean(co_scores) if co_scores else 0
            
            # 綜合分
            total_score = (1 - cooccurrence_weight) * rank_score + cooccurrence_weight * co_score
            scores[num] = total_score
        
        # 按綜合分排序
        sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # 選擇得分最高的號碼
        selected = sorted_nums[:pick_count]
        
        return sorted(selected)
    
    def analyze_and_recommend(
        self, 
        hot_window: int = 50, 
        co_window: int = 100,
        co_threshold: float = 0.3,
        verbose: bool = True
    ) -> Dict:
        """
        完整分析並給出推薦
        
        Args:
            hot_window: 熱號分析窗口
            co_window: 共現分析窗口
            co_threshold: 共現率閾值
            verbose: 是否輸出詳細信息
            
        Returns:
            分析結果與推薦號碼
        """
        history = self.get_data()
        
        if verbose:
            print("=" * 80)
            print(f"🔥 熱號與共現分析 ({self.lottery_type})")
            print(f"📊 數據範圍: {history[0]['date']} -> {history[-1]['date']} ({len(history)} 期)")
            print("=" * 80)
        
        # 1. 熱號分析
        hot_freq = self.get_hot_numbers(history, hot_window)
        hot_nums = [num for num, freq in hot_freq[:20]]
        
        if verbose:
            print(f"\n[1] 熱號分析 (近 {hot_window} 期)")
            print("-" * 40)
            print(f"Top 10 熱號: {[f'{num}({freq}次)' for num, freq in hot_freq[:10]]}")
        
        # 2. 共現分析
        co_matrix = self.build_cooccurrence_matrix(history, co_window)
        high_pairs = self.get_high_cooccurrence_pairs(co_matrix, co_threshold)
        
        if verbose:
            print(f"\n[2] 共現分析 (近 {co_window} 期, 閾值 {co_threshold})")
            print("-" * 40)
            print(f"高共現組合 ({len(high_pairs)} 組):")
            for pair, rate in high_pairs[:10]:
                print(f"  {pair[0]:2d} & {pair[1]:2d} = {rate:.2%}")
        
        # 3. 熱冷號
        hot, cold = self.get_hot_cold_numbers(history, hot_window)
        
        if verbose:
            print(f"\n[3] 熱冷分類")
            print("-" * 40)
            print(f"熱號 ({len(hot)}): {hot[:10]}...")
            print(f"冷號 ({len(cold)}): {cold[:10]}...")
        
        # 4. 推薦號碼
        recommended = self.apply_cooccurrence_rules(
            hot_nums, co_matrix, self.pick_count
        )
        
        if verbose:
            print(f"\n[4] 推薦號碼 (熱號 + 共現優化)")
            print("-" * 40)
            print(f"🎯 推薦: {recommended}")
        
        return {
            'hot_numbers': hot_freq,
            'cooccurrence_matrix': co_matrix,
            'high_cooccurrence_pairs': high_pairs,
            'hot_cold': (hot, cold),
            'recommended': recommended,
            'config': {
                'hot_window': hot_window,
                'co_window': co_window,
                'co_threshold': co_threshold
            }
        }


def run_window_comparison(
    lottery_type: str = 'BIG_LOTTO',
    windows: List[int] = [10, 20, 30, 40, 50, 60],
    verbose: bool = True
):
    """
    比較不同窗口大小的熱號分佈
    
    Args:
        lottery_type: 彩票類型
        windows: 要比較的窗口大小列表
        verbose: 是否輸出詳細信息
    """
    analyzer = HotCooccurrenceAnalyzer(lottery_type)
    history = analyzer.get_data()
    
    if verbose:
        print("=" * 80)
        print("🔍 窗口大小比較分析")
        print("=" * 80)
    
    results = {}
    
    for window in windows:
        hot_freq = analyzer.get_hot_numbers(history, window)
        top_6 = [num for num, freq in hot_freq[:6]]
        
        results[window] = {
            'top_6': top_6,
            'top_10': [num for num, freq in hot_freq[:10]],
            'frequencies': hot_freq[:10]
        }
        
        if verbose:
            freq_str = ', '.join([f"{num}({freq})" for num, freq in hot_freq[:6]])
            print(f"Window {window:3d}: Top 6 = {top_6} | Freq: {freq_str}")
    
    # 找出各窗口共同的穩定熱號
    common_hot = set(results[windows[0]]['top_6'])
    for window in windows[1:]:
        common_hot &= set(results[window]['top_10'])
    
    if verbose:
        print("-" * 80)
        print(f"🌟 穩定熱號 (所有窗口共同的 Top 10): {sorted(common_hot)}")
    
    return results, common_hot


def main():
    parser = argparse.ArgumentParser(description='熱號與共現分析')
    parser.add_argument('--lottery', '-l', type=str, default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'],
                        help='彩票類型')
    parser.add_argument('--hot-window', type=int, default=50,
                        help='熱號分析窗口大小')
    parser.add_argument('--co-window', type=int, default=100,
                        help='共現分析窗口大小')
    parser.add_argument('--threshold', type=float, default=0.3,
                        help='共現率閾值')
    parser.add_argument('--compare-windows', action='store_true',
                        help='比較不同窗口大小')
    parser.add_argument('--test', action='store_true',
                        help='執行測試模式')
    
    args = parser.parse_args()
    
    if args.compare_windows:
        run_window_comparison(args.lottery)
    elif args.test:
        print("🧪 測試模式")
        print("-" * 40)
        
        analyzer = HotCooccurrenceAnalyzer(args.lottery)
        history = analyzer.get_data()
        
        # 測試熱號分析
        hot_freq = analyzer.get_hot_numbers(history, 50)
        assert len(hot_freq) > 0, "熱號分析失敗"
        print("✅ 熱號分析通過")
        
        # 測試共現矩陣
        co_matrix = analyzer.build_cooccurrence_matrix(history, 100)
        assert co_matrix.shape[0] == co_matrix.shape[1], "共現矩陣格式錯誤"
        print("✅ 共現矩陣建立通過")
        
        # 測試高共現組合
        pairs = analyzer.get_high_cooccurrence_pairs(co_matrix, 0.2)
        print(f"✅ 高共現組合識別通過 ({len(pairs)} 組)")
        
        # 測試完整分析
        result = analyzer.analyze_and_recommend(verbose=False)
        assert 'recommended' in result, "完整分析失敗"
        print("✅ 完整分析流程通過")
        
        print("-" * 40)
        print("🎉 所有測試通過！")
    else:
        analyzer = HotCooccurrenceAnalyzer(args.lottery)
        analyzer.analyze_and_recommend(
            hot_window=args.hot_window,
            co_window=args.co_window,
            co_threshold=args.threshold
        )


if __name__ == '__main__':
    main()
