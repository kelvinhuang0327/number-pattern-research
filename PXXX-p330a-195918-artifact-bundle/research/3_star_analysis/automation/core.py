import numpy as np
import pandas as pd
import sqlite3
import json
import os
import random
from typing import Dict, List, Any, Callable
from itertools import combinations
from datetime import datetime

class LotteryDataset:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.raw_df = self._load_data()
        self.conn.close()
        
    def _load_data(self):
        query = "SELECT draw, date, numbers FROM draws WHERE lottery_type = '3_STAR' ORDER BY date ASC"
        df = pd.read_sql_query(query, self.conn)
        df['nums'] = df['numbers'].apply(json.loads)
        # 展開為 Num1, Num2, Num3
        for i in range(3):
            df[f'N{i+1}'] = df['nums'].apply(lambda x: x[i])
        return df

    def get_split(self, train_ratio=0.7, val_ratio=0.15):
        n = len(self.raw_df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        return {
            'train': self.raw_df.iloc[:train_end],
            'val': self.raw_df.iloc[train_end:val_end],
            'test': self.raw_df.iloc[val_end:]
        }

class Evaluator:
    @staticmethod
    def calculate_metrics(preds: np.ndarray, actuals: np.ndarray):
        """
        preds: (N, 3)
        actuals: (N, 3)
        """
        n = len(preds)
        exact_match = np.all(preds == actuals, axis=1)
        hit_count = np.sum(exact_match)
        hit_rate = hit_count / n
        
        # 位數命中
        pos_hits = np.sum(preds == actuals, axis=0) / n
        
        # 穩定度 (Rolling Hit Rate 的標準差)
        rolling_hits = pd.Series(exact_match).rolling(100).mean().dropna()
        stability = 1.0 / (rolling_hits.std() + 1e-6) if len(rolling_hits) > 0 else 0
        
        # EV (假設賠率 500)
        ev = hit_rate * 500 - 1
        
        return {
            'hit_rate': hit_rate,
            'hits': int(hit_count),
            'pos_hits': pos_hits.tolist(),
            'stability': float(stability),
            'ev': float(ev),
            'sharpe_like': float(hit_rate / (rolling_hits.std() + 1e-6)) if len(rolling_hits) > 0 else 0
        }

class DiscoverySystem:
    def __init__(self, dataset: LotteryDataset):
        self.dataset = dataset
        self.splits = dataset.get_split()
        self.strategy_pool = {} # 存放所有生成的策略及其性能
        
    def audit_strategy(self, strategy_func: Callable, split_name='val'):
        """檢核策略防止過擬合"""
        df = self.splits[split_name]
        full_df = self.dataset.raw_df
        
        preds = []
        actuals = []
        
        # 正常回測
        start_idx = df.index[0]
        end_idx = df.index[-1]
        
        for i in range(start_idx, end_idx + 1):
            history = full_df.iloc[:i]
            target = full_df.iloc[i][['N1', 'N2', 'N3']].values
            pred = strategy_func(history)
            preds.append(pred)
            actuals.append(target)
            
        preds = np.array(preds)
        actuals = np.array(actuals)
        metrics = Evaluator.calculate_metrics(preds, actuals)
        
        # 1. Permutation Test (隨機擾動標籤)
        shuffled_actuals = actuals.copy()
        np.random.shuffle(shuffled_actuals)
        shuffled_metrics = Evaluator.calculate_metrics(preds, shuffled_actuals)
        
        # 如果真實性能沒能顯著超過隨機擾動後的性能，則標記為具有風險
        metrics['p_value_proxy'] = 1.0 if metrics['hit_rate'] <= shuffled_metrics['hit_rate'] else 0.05
        metrics['overfit_risk'] = metrics['p_value_proxy'] > 0.1
        
        return metrics

# --- 預定義特徵提取器 ---

class FeatureExtractor:
    @staticmethod
    def get_freq_score(df, window):
        recent = df.tail(window)
        scores = np.zeros((3, 10))
        for i in range(3):
            counts = recent[f'N{i+1}'].value_counts().reindex(range(10), fill_value=0)
            scores[i] = counts.values / (window + 1e-6)
        return scores

    @staticmethod
    def get_markov_score(df, lag=1):
        if len(df) < lag + 1: return np.ones((3, 10)) * 0.1
        last_vals = df.iloc[-lag][['N1', 'N2', 'N3']].values
        scores = np.zeros((3, 10))
        for i in range(3):
            col = f'N{i+1}'
            vals = df[col].values
            transitions = []
            for j in range(len(vals) - lag):
                if vals[j] == last_vals[i]:
                    transitions.append(vals[j+lag])
            if transitions:
                counts = np.bincount(transitions, minlength=10)
                scores[i] = counts / len(transitions)
            else:
                scores[i] = np.ones(10) * 0.1
        return scores

    @staticmethod
    def get_echo_score(df, lag=2):
        """重複上前幾期的號碼"""
        if len(df) < lag: return np.zeros((3, 10))
        target = df.iloc[-lag][['N1', 'N2', 'N3']].values
        scores = np.zeros((3, 10))
        for i in range(3):
            scores[i, int(target[i])] = 1.0
        return scores
