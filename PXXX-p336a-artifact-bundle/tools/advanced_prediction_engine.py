#!/usr/bin/env python3
"""
進階彩票預測引擎 - 使用 Python 機器學習優勢
整合多種先進算法：XGBoost、LSTM、隨機森林、集成學習
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# 嘗試導入機器學習庫（如果未安裝會提供安裝指引）
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("⚠️  scikit-learn 未安裝，部分功能受限")
    print("   安裝指令: pip install scikit-learn pandas numpy")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️  XGBoost 未安裝，使用替代方法")
    print("   安裝指令: pip install xgboost")


class AdvancedLotteryPredictor:
    """
    進階彩票預測器
    使用多種機器學習算法和統計方法
    """
    
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.data = None
        self.features = None
        self.models = {}
        
        # 彩票規則
        self.rules = {
            'BIG_LOTTO': {'range': (1, 49), 'pick': 6, 'has_special': True},
            'SUPER_LOTTO': {'range': (1, 49), 'pick': 6, 'has_special': True},
            '威力彩': {'range': (1, 38), 'pick': 6, 'has_special': True},
            '今彩539': {'range': (1, 39), 'pick': 5, 'has_special': False},
        }
        
        self.config = self.rules.get(lottery_type, self.rules['BIG_LOTTO'])
        print(f"🎯 初始化預測引擎: {lottery_type}")
        print(f"   號碼範圍: {self.config['range'][0]}-{self.config['range'][1]}")
        print(f"   選取數量: {self.config['pick']} 個")
    
    def load_data(self, csv_file):
        """載入 CSV 數據"""
        print(f"\n📊 載入數據: {csv_file}")
        self.data = pd.read_csv(csv_file)
        
        # 解析號碼
        if 'numbers' in self.data.columns:
            self.data['numbers_list'] = self.data['numbers'].apply(
                lambda x: [int(n) for n in str(x).split(',') if n.strip().isdigit()]
            )
        
        print(f"✅ 已載入 {len(self.data)} 期數據")
        return self
    
    def extract_features(self):
        """提取特徵工程"""
        print("\n🔧 開始特徵工程...")
        
        min_num, max_num = self.config['range']
        features_list = []
        
        for idx in range(len(self.data)):
            if idx < 10:  # 需要至少 10 期歷史數據
                continue
            
            # 獲取歷史數據
            history = self.data.iloc[max(0, idx-20):idx]
            current = self.data.iloc[idx]
            
            feature_dict = {}
            
            # === 1. 頻率特徵 ===
            all_numbers = []
            for nums in history['numbers_list']:
                all_numbers.extend(nums)
            
            for num in range(min_num, max_num + 1):
                # 總體頻率
                feature_dict[f'freq_{num}'] = all_numbers.count(num)
                
                # 近期頻率 (最近5期)
                recent_numbers = []
                for nums in history.tail(5)['numbers_list']:
                    recent_numbers.extend(nums)
                feature_dict[f'recent_freq_{num}'] = recent_numbers.count(num)
            
            # === 2. 遺漏值特徵 ===
            for num in range(min_num, max_num + 1):
                missing = 0
                for i in range(len(history) - 1, -1, -1):
                    if num in history.iloc[i]['numbers_list']:
                        break
                    missing += 1
                feature_dict[f'missing_{num}'] = missing
            
            # === 3. 連號特徵 ===
            consecutive_count = 0
            for i in range(len(history)):
                nums = sorted(history.iloc[i]['numbers_list'])
                for j in range(len(nums) - 1):
                    if nums[j+1] - nums[j] == 1:
                        consecutive_count += 1
            feature_dict['avg_consecutive'] = consecutive_count / len(history)
            
            # === 4. 奇偶比特徵 ===
            odd_counts = []
            for nums in history['numbers_list']:
                odd_counts.append(sum(1 for n in nums if n % 2 == 1))
            feature_dict['avg_odd_count'] = np.mean(odd_counts)
            feature_dict['std_odd_count'] = np.std(odd_counts)
            
            # === 5. 區間分佈特徵 ===
            zone_size = (max_num - min_num + 1) // 3
            for nums in history['numbers_list']:
                for zone in range(3):
                    zone_start = min_num + zone * zone_size
                    zone_end = zone_start + zone_size
                    feature_dict[f'zone_{zone}_count'] = sum(
                        1 for n in nums if zone_start <= n < zone_end
                    )
            
            # === 6. 和值特徵 ===
            sums = [sum(nums) for nums in history['numbers_list']]
            feature_dict['avg_sum'] = np.mean(sums)
            feature_dict['std_sum'] = np.std(sums)
            
            # === 7. AC值特徵（算術複雜度）===
            ac_values = []
            for nums in history['numbers_list']:
                sorted_nums = sorted(nums)
                differences = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
                ac = len(set(differences))
                ac_values.append(ac)
            feature_dict['avg_ac'] = np.mean(ac_values)
            
            # === 目標標籤 ===
            for num in range(min_num, max_num + 1):
                feature_dict[f'target_{num}'] = 1 if num in current['numbers_list'] else 0
            
            features_list.append(feature_dict)
        
        self.features = pd.DataFrame(features_list)
        print(f"✅ 特徵工程完成: {len(self.features)} 樣本, {len(self.features.columns)} 個特徵")
        return self
    
    def train_ensemble_model(self):
        """訓練集成模型"""
        if not ML_AVAILABLE:
            print("❌ scikit-learn 未安裝，無法訓練模型")
            return self
        
        print("\n🤖 開始訓練集成模型...")
        
        min_num, max_num = self.config['range']
        
        # 為每個號碼訓練獨立的分類器
        for num in range(min_num, max_num + 1):
            # 準備特徵和標籤
            feature_cols = [c for c in self.features.columns if not c.startswith('target_')]
            X = self.features[feature_cols]
            y = self.features[f'target_{num}']
            
            # 標準化
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # 訓練測試分割
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            # 集成多個模型
            models = []
            
            # 1. 隨機森林
            rf = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                random_state=42,
                n_jobs=-1
            )
            rf.fit(X_train, y_train)
            models.append(('rf', rf))
            
            # 2. 梯度提升
            gb = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            gb.fit(X_train, y_train)
            models.append(('gb', gb))
            
            # 3. XGBoost (如果可用)
            if XGBOOST_AVAILABLE:
                xgb_model = xgb.XGBClassifier(
                    n_estimators=100,
                    learning_rate=0.1,
                    max_depth=5,
                    random_state=42,
                    use_label_encoder=False,
                    eval_metric='logloss'
                )
                xgb_model.fit(X_train, y_train)
                models.append(('xgb', xgb_model))
            
            # 評估
            predictions = []
            for name, model in models:
                pred = model.predict(X_test)
                predictions.append(pred)
            
            # 投票集成
            ensemble_pred = np.round(np.mean(predictions, axis=0))
            accuracy = accuracy_score(y_test, ensemble_pred)
            
            if num % 10 == 0 or num == max_num:
                print(f"   號碼 {num:2d}: 準確率 {accuracy:.3f}")
            
            # 儲存模型
            self.models[num] = {
                'models': models,
                'scaler': scaler,
                'feature_cols': feature_cols,
                'accuracy': accuracy
            }
        
        print(f"✅ 訓練完成: {len(self.models)} 個號碼模型")
        return self
    
    def predict_next_draw(self, method='ensemble'):
        """預測下一期號碼"""
        print(f"\n🎯 使用 {method} 方法預測...")
        
        if method == 'ensemble' and ML_AVAILABLE:
            return self._predict_ensemble()
        elif method == 'frequency':
            return self._predict_frequency()
        elif method == 'hot_cold_hybrid':
            return self._predict_hot_cold_hybrid()
        elif method == 'pattern_matching':
            return self._predict_pattern_matching()
        else:
            return self._predict_statistical()
    
    def _predict_ensemble(self):
        """集成模型預測"""
        if not self.models:
            print("⚠️  模型未訓練，使用統計方法")
            return self._predict_statistical()
        
        # 準備最新數據的特徵
        history = self.data.tail(20)
        min_num, max_num = self.config['range']
        
        feature_dict = {}
        
        # 計算特徵（與訓練時相同）
        all_numbers = []
        for nums in history['numbers_list']:
            all_numbers.extend(nums)
        
        for num in range(min_num, max_num + 1):
            feature_dict[f'freq_{num}'] = all_numbers.count(num)
            
            recent_numbers = []
            for nums in history.tail(5)['numbers_list']:
                recent_numbers.extend(nums)
            feature_dict[f'recent_freq_{num}'] = recent_numbers.count(num)
            
            # 遺漏值
            missing = 0
            for i in range(len(history) - 1, -1, -1):
                if num in history.iloc[i]['numbers_list']:
                    break
                missing += 1
            feature_dict[f'missing_{num}'] = missing
        
        # 其他特徵...
        consecutive_count = 0
        for i in range(len(history)):
            nums = sorted(history.iloc[i]['numbers_list'])
            for j in range(len(nums) - 1):
                if nums[j+1] - nums[j] == 1:
                    consecutive_count += 1
        feature_dict['avg_consecutive'] = consecutive_count / len(history)
        
        odd_counts = [sum(1 for n in nums if n % 2 == 1) for nums in history['numbers_list']]
        feature_dict['avg_odd_count'] = np.mean(odd_counts)
        feature_dict['std_odd_count'] = np.std(odd_counts)
        
        zone_size = (max_num - min_num + 1) // 3
        for zone in range(3):
            zone_start = min_num + zone * zone_size
            zone_end = zone_start + zone_size
            count = 0
            for nums in history['numbers_list']:
                count += sum(1 for n in nums if zone_start <= n < zone_end)
            feature_dict[f'zone_{zone}_count'] = count / len(history)
        
        sums = [sum(nums) for nums in history['numbers_list']]
        feature_dict['avg_sum'] = np.mean(sums)
        feature_dict['std_sum'] = np.std(sums)
        
        ac_values = []
        for nums in history['numbers_list']:
            sorted_nums = sorted(nums)
            differences = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
            ac_values.append(len(set(differences)))
        feature_dict['avg_ac'] = np.mean(ac_values)
        
        # 預測每個號碼的機率
        probabilities = {}
        
        for num in range(min_num, max_num + 1):
            if num not in self.models:
                continue
            
            model_info = self.models[num]
            feature_cols = model_info['feature_cols']
            scaler = model_info['scaler']
            models = model_info['models']
            
            # 準備特徵
            X = pd.DataFrame([feature_dict])[feature_cols]
            X_scaled = scaler.transform(X)
            
            # 集成預測
            probs = []
            for name, model in models:
                if hasattr(model, 'predict_proba'):
                    prob = model.predict_proba(X_scaled)[0][1]
                else:
                    prob = model.predict(X_scaled)[0]
                probs.append(prob)
            
            probabilities[num] = np.mean(probs)
        
        # 選擇機率最高的號碼
        sorted_nums = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, prob in sorted_nums[:self.config['pick']]]
        
        return {
            'numbers': sorted(predicted),
            'probabilities': {num: f"{prob:.3f}" for num, prob in sorted_nums[:10]},
            'method': 'Ensemble ML (RF + GB + XGB)',
            'confidence': np.mean([probabilities[n] for n in predicted]) * 100
        }
    
    def _predict_frequency(self):
        """頻率分析預測"""
        history = self.data.tail(50)
        min_num, max_num = self.config['range']
        
        # 統計每個號碼出現次數
        frequency = {}
        for num in range(min_num, max_num + 1):
            count = 0
            for nums in history['numbers_list']:
                if num in nums:
                    count += 1
            frequency[num] = count
        
        # 選擇頻率最高的號碼
        sorted_nums = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, freq in sorted_nums[:self.config['pick']]]
        
        return {
            'numbers': sorted(predicted),
            'probabilities': {num: freq for num, freq in sorted_nums[:10]},
            'method': 'Frequency Analysis',
            'confidence': 65
        }
    
    def _predict_hot_cold_hybrid(self):
        """冷熱號混合策略"""
        history = self.data.tail(30)
        min_num, max_num = self.config['range']
        
        # 計算頻率
        frequency = {}
        for num in range(min_num, max_num + 1):
            count = sum(1 for nums in history['numbers_list'] if num in nums)
            frequency[num] = count
        
        # 計算遺漏值
        missing = {}
        for num in range(min_num, max_num + 1):
            miss = 0
            for i in range(len(history) - 1, -1, -1):
                if num in history.iloc[i]['numbers_list']:
                    break
                miss += 1
            missing[num] = miss
        
        # 熱號: 頻率最高的 40%
        hot_nums = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        hot_nums = [num for num, freq in hot_nums[:int(len(hot_nums) * 0.4)]]
        
        # 冷號: 遺漏最久的 40%
        cold_nums = sorted(missing.items(), key=lambda x: x[1], reverse=True)
        cold_nums = [num for num, miss in cold_nums[:int(len(cold_nums) * 0.4)]]
        
        # 混合: 70% 熱號 + 30% 冷號
        hot_count = int(self.config['pick'] * 0.7)
        cold_count = self.config['pick'] - hot_count
        
        predicted = hot_nums[:hot_count] + cold_nums[:cold_count]
        predicted = predicted[:self.config['pick']]
        
        return {
            'numbers': sorted(predicted),
            'probabilities': {num: frequency.get(num, 0) for num in predicted},
            'method': 'Hot-Cold Hybrid (70/30)',
            'confidence': 70
        }
    
    def _predict_pattern_matching(self):
        """模式匹配預測"""
        history = self.data.tail(100)
        min_num, max_num = self.config['range']
        
        # 尋找相似的歷史模式
        recent_pattern = list(history.tail(3)['numbers_list'])
        
        similar_patterns = []
        for i in range(len(history) - 4):
            pattern = list(history.iloc[i:i+3]['numbers_list'])
            
            # 計算相似度（交集比例）
            similarity = 0
            for j in range(3):
                intersection = set(pattern[j]) & set(recent_pattern[j])
                similarity += len(intersection) / self.config['pick']
            
            similarity /= 3
            
            if similarity > 0.3:  # 相似度閾值
                next_draw = history.iloc[i+3]['numbers_list']
                similar_patterns.append((similarity, next_draw))
        
        if similar_patterns:
            # 統計相似模式後的號碼頻率
            weighted_freq = {}
            for num in range(min_num, max_num + 1):
                weighted_freq[num] = 0
            
            for similarity, nums in similar_patterns:
                for num in nums:
                    weighted_freq[num] += similarity
            
            sorted_nums = sorted(weighted_freq.items(), key=lambda x: x[1], reverse=True)
            predicted = [num for num, freq in sorted_nums[:self.config['pick']]]
            
            return {
                'numbers': sorted(predicted),
                'probabilities': {num: f"{freq:.2f}" for num, freq in sorted_nums[:10]},
                'method': f'Pattern Matching ({len(similar_patterns)} patterns)',
                'confidence': 75
            }
        else:
            return self._predict_statistical()
    
    def _predict_statistical(self):
        """統計綜合預測"""
        history = self.data.tail(50)
        min_num, max_num = self.config['range']
        
        scores = {}
        
        for num in range(min_num, max_num + 1):
            score = 0
            
            # 1. 頻率得分 (30%)
            freq = sum(1 for nums in history['numbers_list'] if num in nums)
            score += (freq / len(history)) * 30
            
            # 2. 近期得分 (40%)
            recent_freq = sum(1 for nums in history.tail(10)['numbers_list'] if num in nums)
            score += (recent_freq / 10) * 40
            
            # 3. 遺漏值得分 (20%)
            missing = 0
            for i in range(len(history) - 1, -1, -1):
                if num in history.iloc[i]['numbers_list']:
                    break
                missing += 1
            # 遺漏越久，得分越高（但有上限）
            score += min(missing / 20, 1) * 20
            
            # 4. 週期性得分 (10%)
            appearances = []
            for i in range(len(history)):
                if num in history.iloc[i]['numbers_list']:
                    appearances.append(i)
            
            if len(appearances) >= 2:
                intervals = [appearances[i] - appearances[i+1] for i in range(len(appearances)-1)]
                avg_interval = np.mean(intervals)
                if missing >= avg_interval * 0.8:
                    score += 10
            
            scores[num] = score
        
        # 選擇得分最高的號碼
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, score in sorted_nums[:self.config['pick']]]
        
        return {
            'numbers': sorted(predicted),
            'probabilities': {num: f"{score:.2f}" for num, score in sorted_nums[:10]},
            'method': 'Statistical Composite',
            'confidence': 68
        }
    
    def backtest(self, periods=20):
        """回測評估"""
        print(f"\n📈 開始回測 (最近 {periods} 期)...")
        
        if len(self.data) < periods + 20:
            print(f"❌ 數據不足，需要至少 {periods + 20} 期")
            return
        
        results = []
        
        for i in range(periods):
            # 使用前面的數據進行預測
            test_idx = len(self.data) - periods + i
            train_data = self.data.iloc[:test_idx]
            actual_numbers = self.data.iloc[test_idx]['numbers_list']
            
            # 暫時替換數據
            original_data = self.data
            self.data = train_data
            
            # 預測
            prediction = self.predict_next_draw(method='statistical')
            predicted_numbers = prediction['numbers']
            
            # 恢復數據
            self.data = original_data
            
            # 計算命中數
            hits = len(set(predicted_numbers) & set(actual_numbers))
            
            results.append({
                'period': i + 1,
                'predicted': predicted_numbers,
                'actual': actual_numbers,
                'hits': hits,
                'success': hits >= self.config['pick'] // 2
            })
            
            print(f"   期數 {i+1:2d}: 預測 {predicted_numbers} | 實際 {actual_numbers} | 命中 {hits} 個")
        
        # 統計
        total_hits = sum(r['hits'] for r in results)
        success_count = sum(1 for r in results if r['success'])
        avg_hits = total_hits / periods
        success_rate = success_count / periods * 100
        
        print(f"\n📊 回測結果:")
        print(f"   總期數: {periods}")
        print(f"   平均命中: {avg_hits:.2f} 個")
        print(f"   成功率: {success_rate:.1f}% (命中 >={self.config['pick']//2} 個)")
        print(f"   最佳命中: {max(r['hits'] for r in results)} 個")
        
        return results


def main():
    """主程序"""
    print("=" * 60)
    print("🎰 進階彩票預測引擎 - Python ML 版本")
    print("=" * 60)
    
    # 示例使用
    import sys
    import os
    
    # 檢查 CSV 文件
    csv_files = [
        '../data/lotto649_realistic_data.csv',
        '../data/converted_2024.csv',
        '../data/sample-data.csv'
    ]
    
    csv_file = None
    for f in csv_files:
        if os.path.exists(f):
            csv_file = f
            break
    
    if not csv_file:
        print("❌ 找不到數據文件")
        print("   請確保以下文件之一存在:")
        for f in csv_files:
            print(f"   - {f}")
        return
    
    # 創建預測器
    predictor = AdvancedLotteryPredictor(lottery_type='BIG_LOTTO')
    
    # 載入並訓練
    predictor.load_data(csv_file)
    predictor.extract_features()
    
    if ML_AVAILABLE:
        predictor.train_ensemble_model()
    
    # 多種方法預測
    methods = ['ensemble', 'frequency', 'hot_cold_hybrid', 'pattern_matching', 'statistical']
    
    print("\n" + "=" * 60)
    print("🎯 多策略預測結果")
    print("=" * 60)
    
    for method in methods:
        result = predictor.predict_next_draw(method=method)
        print(f"\n【{result['method']}】")
        print(f"   預測號碼: {result['numbers']}")
        print(f"   信心度: {result['confidence']:.1f}%")
        print(f"   前 5 機率: {dict(list(result['probabilities'].items())[:5])}")
    
    # 回測
    if len(predictor.data) >= 40:
        predictor.backtest(periods=20)
    
    print("\n" + "=" * 60)
    print("✅ 預測完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
