import sqlite3
import pandas as pd
import numpy as np
import json
import sys
from scipy import stats

# Add research path
sys.path.append('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/research/3_star_analysis')

def load_real_data(db_path):
    conn = sqlite3.connect(db_path)
    query = "SELECT draw, date, numbers FROM draws WHERE lottery_type = '3_STAR' ORDER BY date ASC, draw ASC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['parsed_nums'] = df['numbers'].apply(lambda x: json.loads(x))
    df['Num1'] = df['parsed_nums'].apply(lambda x: x[0])
    df['Num2'] = df['parsed_nums'].apply(lambda x: x[1])
    df['Num3'] = df['parsed_nums'].apply(lambda x: x[2])
    return df

# --- 策略库 ---

def random_baseline(df):
    return np.random.randint(0, 10, size=3)

def frequency_strategy(df):
    """統計方法: 最熱門號碼"""
    return np.array([df['Num1'].mode()[0], df['Num2'].mode()[0], df['Num3'].mode()[0]])

def cold_strategy(df):
    """統計方法: 冷門補償 (最久未出現號碼)"""
    res = []
    for col in ['Num1', 'Num2', 'Num3']:
        last_seen = {}
        vals = df[col].values
        for n in range(10):
            indices = np.where(vals == n)[0]
            last_seen[n] = indices[-1] if len(indices) > 0 else -1
        # 找出 index 最小的 (最久遠)
        res.append(min(last_seen, key=last_seen.get))
    return np.array(res)

def markov_strategy(df):
    """機率模型: 一階馬可夫鏈"""
    last_draw = df.iloc[-1][['Num1', 'Num2', 'Num3']].values
    res = []
    for i, col in enumerate(['Num1', 'Num2', 'Num3']):
        vals = df[col].values
        transitions = []
        for j in range(len(vals)-1):
            if vals[j] == last_draw[i]:
                transitions.append(vals[j+1])
        if transitions:
            res.append(np.bincount(transitions).argmax())
        else:
            res.append(df[col].mode()[0])
    return np.array(res)

def bayesian_fusion_strategy(df):
    """機率模型: 貝氏融合 (結合頻率與近期波動)"""
    window_long = 500
    window_short = 50
    res = []
    for col in ['Num1', 'Num2', 'Num3']:
        long_freq = df[col].tail(window_long).value_counts(normalize=True).reindex(range(10), fill_value=0.1)
        short_freq = df[col].tail(window_short).value_counts(normalize=True).reindex(range(10), fill_value=0.1)
        # 簡單融合
        combined = (long_freq * 0.3 + short_freq * 0.7)
        res.append(combined.idxmax())
    return np.array(res)

def sum_reversion_strategy(df):
    """和值分析: 預測和值向均值(13.5)回歸"""
    # 這是一個過濾型策略，這裡簡化為選擇最接近中位數的組合
    # 實際上 3星彩各個位置獨立性強，這裡用每個位置趨向於 4.5 的模式
    last_draw = df.iloc[-1][['Num1', 'Num2', 'Num3']].values
    res = []
    for i, col in enumerate(['Num1', 'Num2', 'Num3']):
        # 如果上期 > 5 下期預測 < 5，反之亦然
        if last_draw[i] > 4.5:
            res.append(df[df[col] <= 4][col].mode()[0] if not df[df[col] <= 4].empty else 2)
        else:
            res.append(df[df[col] >= 5][col].mode()[0] if not df[df[col] >= 5].empty else 7)
    return np.array(res)

# --- 回測引擎 ---

def run_benchmark(df, strategies, train_size=2000):
    results = []
    test_df = df.iloc[train_size:]
    print(f"總樣本人數: {len(df)}, 訓練集: {train_size}, 測試集: {len(test_df)}")
    
    for name, func in strategies.items():
        print(f"正在回測策略: {name}...")
        hits = 0
        pos_hits = np.zeros(3)
        
        for i in range(train_size, len(df)):
            history = df.iloc[i-train_size:i]
            actual = df.iloc[i][['Num1', 'Num2', 'Num3']].values
            pred = func(history)
            
            if np.all(pred == actual):
                hits += 1
            pos_hits += (pred == actual)
            
        hit_rate = hits / len(test_df)
        pos_hit_rate = pos_hits / len(test_df)
        
        results.append({
            "方法": name,
            "完全命中率": f"{hit_rate*100:.3f}%",
            "命中次數": hits,
            "位數命中率": [f"{p*100:.1f}%" for p in pos_hit_rate],
            "相對提升": f"{(hit_rate/0.001 - 1)*100:.1f}%",
            "EV (估計)": hit_rate * 500 - 1  # 假設賠率 500
        })
    
    return pd.DataFrame(results)

if __name__ == "__main__":
    db_path = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
    df = load_real_data(db_path)
    
    strategies = {
        "隨機基準 (Random)": random_baseline,
        "熱門頻率 (Hot)": frequency_strategy,
        "冷門補償 (Cold)": cold_strategy,
        "一階馬可夫 (Markov)": markov_strategy,
        "貝氏融合 (Bayesian)": bayesian_fusion_strategy,
        "和值回歸 (Sum)": sum_reversion_strategy
    }
    
    report = run_benchmark(df, strategies)
    print("\n" + "="*80)
    print("3星彩全方法回測績效榜單 (真實數據: 4116期)")
    print("="*80)
    print(report.to_string(index=False))
    
    # 儲存結果
    report.to_json("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/research/3_star_analysis/benchmark_results.json", orient='records', force_ascii=False)
