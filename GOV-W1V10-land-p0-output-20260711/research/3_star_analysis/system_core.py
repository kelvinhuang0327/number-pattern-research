import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import sqlite3
import os

class ThreeStarAnalyzer:
    """
    3星彩研究級分析系統
    整合隨機性檢定、回測系統與統計建模
    """
    def __init__(self, data_path=None):
        self.data_path = data_path
        self.history = None
        self.draw_count = 0
        
    def generate_synthetic_data(self, n_draws=1000, bias_type=None):
        """
        生成測試用合成數據
        bias_type: 
            None - 完全隨機
            'freq' - 某些號碼頻率偏高
            'seq' - 存在序列關聯 (馬可夫)
        """
        print(f"Generating {n_draws} synthetic draws (bias: {bias_type})...")
        if bias_type is None:
            # 完美的均勻分布
            data = np.random.randint(0, 10, size=(n_draws, 3))
        elif bias_type == 'freq':
            # 號碼 7 出現機率較高 (0.2 而非 0.1)
            p = [0.08, 0.08, 0.08, 0.08, 0.08, 0.1, 0.1, 0.2, 0.1, 0.1]
            data = np.array([np.random.choice(10, size=3, p=p) for _ in range(n_draws)])
        elif bias_type == 'seq':
            # 存在一階滯後相關
            data = np.zeros((n_draws, 3), dtype=int)
            for i in range(n_draws):
                if i == 0:
                    data[i] = np.random.randint(0, 10, size=3)
                else:
                    # 有30%機率跟前一期某位數相同
                    for pos in range(3):
                        if np.random.random() < 0.3:
                            data[i, pos] = data[i-1, pos]
                        else:
                            data[i, pos] = np.random.randint(0, 10)
        
        df = pd.DataFrame(data, columns=['Num1', 'Num2', 'Num3'])
        df['DrawID'] = range(1, n_draws + 1)
        self.history = df
        self.draw_count = n_draws
        return df

    def run_randomness_tests(self):
        """
        執行多種隨機性檢定 (Step 5)
        """
        print("\n--- [STEP 5] 隨機性檢定報告 ---")
        results = {}
        
        # 1. 卡方檢定 (Chi-Square) - 頻率均勻性
        all_nums = self.history[['Num1', 'Num2', 'Num3']].values.flatten()
        observed_freq = np.bincount(all_nums, minlength=10)
        expected_freq = [len(all_nums) / 10] * 10
        chi2, p_val = stats.chisquare(observed_freq, f_exp=expected_freq)
        results['chi_square'] = {'stat': chi2, 'p_value': p_val, 'sig': p_val < 0.05}
        
        # 2. Runs Test (單變量符號檢定) - 序列平穩性
        # 取第一位數舉例
        n1 = self.history['Num1'].values
        median = np.median(n1)
        runs = (n1 > median).astype(int)
        
        # 計算 Runs
        run_count = 1
        for i in range(1, len(runs)):
            if runs[i] != runs[i-1]:
                run_count += 1
        
        n1_pos = np.sum(runs == 1)
        n2_neg = np.sum(runs == 0)
        exp_runs = ((2 * n1_pos * n2_neg) / (n1_pos + n2_neg)) + 1
        std_runs = np.sqrt((2 * n1_pos * n2_neg * (2 * n1_pos * n2_neg - n1_pos - n2_neg)) / 
                          (((n1_pos + n2_neg)**2) * (n1_pos + n2_neg - 1)))
        z_stat = (run_count - exp_runs) / std_runs
        p_runs = 2 * (1 - stats.norm.cdf(abs(z_stat)))
        results['runs_test'] = {'stat': z_stat, 'p_value': p_runs, 'sig': p_runs < 0.05}
        
        # 3. 自相關檢定 (Autocorrelation)
        acf = pd.Series(n1).autocorr(lag=1)
        results['autocorr_lag1'] = {'value': acf}

        # 輸出
        print(f"1. 卡方檢定 P值: {p_val:.4f} " + ("[顯著非隨機]" if p_val < 0.05 else "[符合隨機分布]"))
        print(f"2. Runs Test P值: {p_runs:.4f} " + ("[序列存在模式]" if p_runs < 0.05 else "[序列符合隨機]"))
        print(f"3. 一階自相關系數: {acf:.4f}")
        
        return results

    def backtest_strategy(self, strategy_func, train_size=500):
        """
        執行回測系統 (Step 4)
        """
        print("\n--- [STEP 4] 策略回測報告 ---")
        if self.history is None or len(self.history) <= train_size:
            print("數據不足以執行回測")
            return
            
        predictions = []
        actuals = []
        
        for i in range(train_size, len(self.history)):
            train_set = self.history.iloc[i-train_size : i]
            actual = self.history.iloc[i][['Num1', 'Num2', 'Num3']].values
            
            # 得到預測號碼 (預設回傳 3 個數字)
            pred = strategy_func(train_set)
            predictions.append(pred)
            actuals.append(actual)
            
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        # 計算指標
        exact_hits = np.all(predictions == actuals, axis=1)
        any_pos_hits = np.any(predictions == actuals, axis=1)
        each_pos_hits = np.sum(predictions == actuals, axis=0) / len(actuals)
        
        hit_rate = np.mean(exact_hits)
        expected_hit_rate = 0.001
        
        print(f"回測期數: {len(actuals)}")
        print(f"完全命中次數: {np.sum(exact_hits)}")
        print(f"完全命中率: {hit_rate:.5f} (理論值: {expected_hit_rate:.5f})")
        print(f"任一位命中率: {each_pos_hits}")
        print(f"相對理論提升: {((hit_rate / expected_hit_rate) - 1) * 100:.2f}%")
        
        return {
            'hit_rate': hit_rate,
            'pos_hit_rates': each_pos_hits,
            'total_hits': np.sum(exact_hits)
        }

# --- 範例策略 ---

def frequentist_strategy(df):
    """
    熱門號碼策略：預測每個位置出現次數最多的號碼
    """
    res = []
    for col in ['Num1', 'Num2', 'Num3']:
        res.append(df[col].mode()[0])
    return np.array(res)

def bayesian_laplace_strategy(df):
    """
    貝氏平滑策略：計算每個號碼機率並取 Max
    """
    res = []
    for col in ['Num1', 'Num2', 'Num3']:
        counts = df[col].value_counts().reindex(range(10), fill_value=0)
        # Laplace Smoothing
        probs = (counts + 1) / (len(df) + 10)
        res.append(probs.idxmax())
    return np.array(res)

# --- 執行分析 ---

if __name__ == "__main__":
    analyzer = ThreeStarAnalyzer()
    
    # 場景 A: 完全隨機數據 (控制組)
    print("="*50)
    print("場景 A: 完全隨機模擬數據")
    analyzer.generate_synthetic_data(n_draws=2000, bias_type=None)
    analyzer.run_randomness_tests()
    analyzer.backtest_strategy(frequentist_strategy)
    
    # 場景 B: 頻率偏差數據 (實驗組 - 特定號碼 7 機率高)
    print("\n" + "="*50)
    print("場景 B: 頻率偏差模擬數據 (號碼7偏熱)")
    analyzer.generate_synthetic_data(n_draws=2000, bias_type='freq')
    analyzer.run_randomness_tests()
    analyzer.backtest_strategy(frequentist_strategy)

    # 場景 C: 序列相關數據 (實驗組 - 有記憶性)
    print("\n" + "="*50)
    print("場景 C: 序列相關模擬數據 (滯後1相關)")
    analyzer.generate_synthetic_data(n_draws=2000, bias_type='seq')
    analyzer.run_randomness_tests()
    # 這裡可以用前一期的號碼作為預測
    def last_draw_strategy(df):
        return df.iloc[-1][['Num1', 'Num2', 'Num3']].values
    analyzer.backtest_strategy(last_draw_strategy)
