"""
自動學習優化引擎
使用遺傳算法自動優化預測策略的參數
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np
from collections import Counter

logger = logging.getLogger(__name__)

class AutoLearningEngine:
    """
    自動學習優化引擎
    使用遺傳算法優化預測策略參數
    """
    
    def __init__(self):
        self.best_config = None
        self.optimization_history = []
        logger.info("AutoLearningEngine 初始化完成")
    
    async def optimize(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        generations: int = 20,
        population_size: int = 30,
        progress_callback = None,
        max_data_limit: int = None,
        target_fitness: float = None,
        patience: int = 5
    ) -> Dict:
        """
        執行自動優化

        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            generations: 遺傳代數
            population_size: 種群大小
            progress_callback: 進度回調函數
            max_data_limit: 數據量限制（None=不限制，用於排程優化）
            target_fitness: 目標適應度（達到後提前停止，None=不啟用早停）

        Returns:
            優化結果和最佳配置
        """
        try:
            logger.info(f"開始自動優化: {generations} 代, 種群 {population_size}, 數據限制: {max_data_limit or '無限制'}")
            if target_fitness:
                logger.info(f"⭐ 目標適應度: {target_fitness:.4f} (達標後提前停止)")

            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)

            # 🔧 改進：可配置的數據量限制
            # - 手動優化（前端）: max_data_limit=500（前端已限制300期）
            # - 排程優化（後端）: max_data_limit=None（使用完整數據）
            if max_data_limit is not None and len(history) > max_data_limit:
                logger.info(f"數據量限制：{len(history)} 期 → {max_data_limit} 期")
                train_data = history[-max_data_limit:]
            else:
                train_data = history
                logger.info(f"使用完整數據：{len(train_data)} 期")
            
            if len(train_data) < 50:
                raise ValueError("數據不足，至少需要 50 期")
            
            # 分割數據：訓練集和驗證集
            split_idx = int(len(train_data) * 0.8)
            train_set = train_data[:split_idx]
            val_set = train_data[split_idx:]
            
            # 初始化種群
            population = self._initialize_population(population_size)
            
            best_fitness = 0
            best_config = None
            fitness_history = []
            no_improve_count = 0
            
            for gen in range(generations):
                # 🌐 讓出事件迴圈，避免長時間阻塞 (提升 /health, /api/ping 響應能力)
                await asyncio.sleep(0)
                # 評估種群
                fitness_scores = []
                for config in population:
                    fitness = await self._evaluate_config(
                        config, train_set, val_set, pick_count, min_number, max_number
                    )
                    fitness_scores.append(fitness)
                
                # 找出最佳個體
                max_fitness_idx = np.argmax(fitness_scores)
                if fitness_scores[max_fitness_idx] > best_fitness:
                    best_fitness = fitness_scores[max_fitness_idx]
                    best_config = population[max_fitness_idx].copy()
                    no_improve_count = 0
                
                # 記錄這一代的最佳適應度
                current_best = float(np.max(fitness_scores))
                fitness_history.append(current_best)

                logger.info(f"第 {gen+1} 代: 最佳適應度 {best_fitness:.4f} (本代最佳: {current_best:.4f})")

                # 🎯 早停檢查：達到目標適應度
                if target_fitness and best_fitness >= target_fitness:
                    logger.info(f"🎉 已達到目標適應度 {target_fitness:.4f}！提前停止於第 {gen+1}/{generations} 代")
                    logger.info(f"✅ 最終適應度: {best_fitness:.4f}")
                    break

                # 🛑 早停檢查：連續多代沒有提升
                if current_best <= best_fitness:
                    no_improve_count += 1
                else:
                    no_improve_count = 0
                if no_improve_count >= patience:
                    logger.info(f"🛑 早停：已連續 {no_improve_count} 代無提升，提前結束於第 {gen+1}/{generations} 代")
                    break

                # 選擇、交叉、變異
                population = self._evolve_population(population, fitness_scores)

                # 更新進度
                if progress_callback:
                    try:
                        progress = ((gen + 1) / generations) * 100
                        await progress_callback(progress)
                    except Exception as e:
                        logger.warning(f"進度回調失敗: {e}")
            
            # 保存最佳配置
            self.best_config = best_config
            self.optimization_history.append({
                'timestamp': datetime.now().isoformat(),
                'generations': generations,
                'best_fitness': float(best_fitness),
                'config': best_config
            })
            
            logger.info(f"優化完成: 最佳適應度 {best_fitness:.4f}")
            
            return {
                'success': True,
                'best_fitness': float(best_fitness),
                'best_config': best_config,
                'generations': generations,
                'fitness_history': fitness_history
            }
            
        except Exception as e:
            logger.error(f"自動優化失敗: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _initialize_population(self, size: int) -> List[Dict]:
        """
        初始化種群（策略參數配置）
        """
        population = []
        weight_keys = [
            'frequency_weight', 'missing_weight', 'hot_cold_weight', 'trend_weight',
            'zone_weight', 'last_digit_weight', 'odd_even_weight',
            'pair_weight', 'sum_band_weight', 'ac_band_weight', 'dynamic_zone_weight'
        ]
        
        for _ in range(size):
            config = {
                'frequency_weight': np.random.uniform(0.1, 0.5),
                'missing_weight': np.random.uniform(0.05, 0.3),
                'hot_cold_weight': np.random.uniform(0.05, 0.3),
                'trend_weight': np.random.uniform(0.05, 0.3),
                'zone_weight': np.random.uniform(0.05, 0.3),
                'last_digit_weight': np.random.uniform(0.05, 0.3),
                'odd_even_weight': np.random.uniform(0.05, 0.3),
                'pair_weight': np.random.uniform(0.02, 0.2),
                'sum_band_weight': np.random.uniform(0.02, 0.2),
                'ac_band_weight': np.random.uniform(0.02, 0.2),
                'dynamic_zone_weight': np.random.uniform(0.02, 0.2),
                'recent_window': int(np.random.uniform(20, 100)),
                'long_window': int(np.random.uniform(100, 300))
            }
            # 歸一化權重
            total_weight = sum(config[key] for key in weight_keys)
            for key in weight_keys:
                config[key] /= total_weight
            
            population.append(config)
        
        return population
    
    async def _evaluate_config(
        self, 
        config: Dict, 
        train_set: List[Dict], 
        val_set: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> float:
        """
        評估配置的適應度（在驗證集上的成功率）
        
        🔄 滾動式預測邏輯（與前端模擬測試一致）：
        - 預測第 N 期時，只使用前 N-1 期的數據
        - 不將當期結果加入歷史（避免數據洩漏）
        - 完全模擬實際使用場景
        """
        success_count = 0
        
        # 合併訓練集和驗證集，用於滾動預測
        all_data = train_set + val_set
        
        for i, target in enumerate(val_set):
            # 🔑 關鍵：只使用該期之前的所有數據
            # 計算該期在完整數據中的索引
            target_index = len(train_set) + i
            
            # 訓練數據 = 該期之前的所有數據
            training_data = all_data[:target_index]
            
            # 使用該期之前的數據進行預測
            predicted = self._predict_with_config(
                config, training_data, pick_count, min_num, max_num
            )
            
            # 評估命中數（主號碼）
            hits = len(set(target['numbers']) & set(predicted))

            # 🔧 評估特別號碼（如果有）
            if 'special' in target and target.get('special'):
                try:
                    target_numbers_set = set(target['numbers'])
                    target_numbers_set.add(int(target['special']))
                    # 重新計算命中數（包含特別號）
                    hits = len(target_numbers_set & set(predicted))
                except (ValueError, TypeError):
                    pass

            if hits >= 3:
                success_count += 1
        
        # 適應度 = 成功率
        fitness = success_count / len(val_set) if len(val_set) > 0 else 0
        
        return fitness
    
    def _predict_with_config(
        self,
        config: Dict,
        history: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        使用給定配置進行預測（完整混合策略）
        """
        scores = {num: 0.0 for num in range(min_num, max_num + 1)}
        
        # 1. 頻率分析
        if config.get('frequency_weight', 0) > 0:
            recent_window = min(config.get('recent_window', 20), len(history))
            recent_numbers = []
            for draw in history[-recent_window:]:
                recent_numbers.extend(draw['numbers'])
            freq = Counter(recent_numbers)
            max_freq = max(freq.values()) if freq else 1
            for num in range(min_num, max_num + 1):
                scores[num] += (freq.get(num, 0) / max_freq) * config['frequency_weight']
        
        # 2. 遺漏值分析
        if config.get('missing_weight', 0) > 0:
            missing = {num: 0 for num in range(min_num, max_num + 1)}
            for i in range(len(history) - 1, -1, -1):
                current_numbers = set(history[i]['numbers'])
                for num in range(min_num, max_num + 1):
                    if num not in current_numbers:
                        missing[num] += 1
                    else:
                        if missing[num] > 0: # 已經計數過，停止
                             pass # 這裡邏輯有點問題，應該是每個號碼獨立計數直到遇到該號碼
            
            # 修正遺漏值邏輯
            missing = {num: 0 for num in range(min_num, max_num + 1)}
            for num in range(min_num, max_num + 1):
                count = 0
                for i in range(len(history) - 1, -1, -1):
                    if num not in history[i]['numbers']:
                        count += 1
                    else:
                        break
                missing[num] = count
                
            max_missing = max(missing.values()) if missing else 1
            for num, miss_count in missing.items():
                scores[num] += (np.sqrt(miss_count / max_missing) if max_missing > 0 else 0) * config['missing_weight']

        # 3. 冷熱號平衡
        if config.get('hot_cold_weight', 0) > 0:
            # 簡化版：直接使用頻率分析的結果作為近期，長期設為全部
            all_numbers = []
            for draw in history:
                all_numbers.extend(draw['numbers'])
            long_freq = Counter(all_numbers)
            max_long = max(long_freq.values()) if long_freq else 1
            
            # 近期頻率已經在上面計算過，這裡重新計算以防萬一
            recent_window = 20
            recent_numbers = []
            for draw in history[-recent_window:]:
                recent_numbers.extend(draw['numbers'])
            recent_freq = Counter(recent_numbers)
            max_recent = max(recent_freq.values()) if recent_freq else 1
            
            for num in range(min_num, max_num + 1):
                r_score = recent_freq.get(num, 0) / max_recent
                l_score = long_freq.get(num, 0) / max_long
                scores[num] += (r_score * 0.6 + l_score * 0.4) * config['hot_cold_weight']

        # 4. 趨勢分析 (簡化版)
        if config.get('trend_weight', 0) > 0:
            if len(history) >= 40:
                mid = len(history) - 20
                early = history[:mid]
                late = history[mid:]
                
                early_nums = [n for d in early for n in d['numbers']]
                late_nums = [n for d in late for n in d['numbers']]
                
                early_freq = Counter(early_nums)
                late_freq = Counter(late_nums)
                
                for num in range(min_num, max_num + 1):
                    e_score = early_freq.get(num, 0) / len(early) if early else 0
                    l_score = late_freq.get(num, 0) / len(late) if late else 0
                    
                    trend_score = 0.5
                    if l_score > e_score: trend_score = 0.8
                    elif l_score < e_score: trend_score = 0.2
                    
                    scores[num] += trend_score * config['trend_weight']
            else:
                for num in range(min_num, max_num + 1):
                    scores[num] += 0.5 * config['trend_weight']

        # 5. 區間分析（固定分區）
        if config.get('zone_weight', 0) > 0:
            range_len = max_num - min_num + 1
            zone_size = max(1, range_len // 5)
            recent = history[-10:]
            zone_counts = Counter()
            for draw in recent:
                for num in draw['numbers']:
                    zone_idx = (num - min_num) // zone_size
                    zone_counts[zone_idx] += 1
            max_zone = max(zone_counts.values()) if zone_counts else 1
            for num in range(min_num, max_num + 1):
                z_idx = (num - min_num) // zone_size
                scores[num] += (zone_counts[z_idx] / max_zone) * config['zone_weight']

        # 5b. 動態區間分析（依近期密度自適應分區）
        if config.get('dynamic_zone_weight', 0) > 0 and len(history) >= 20:
            recent = history[-20:]
            # 以近期號碼密度估算區段邊界（四分位）
            recent_numbers = sorted([n for d in recent for n in d['numbers']])
            if recent_numbers:
                q1 = np.percentile(recent_numbers, 25)
                q2 = np.percentile(recent_numbers, 50)
                q3 = np.percentile(recent_numbers, 75)
                # 區段： [min,q1],[q1,q2],[q2,q3],[q3,max]
                zone_counts = [0,0,0,0]
                for n in recent_numbers:
                    if n <= q1: zone_counts[0] += 1
                    elif n <= q2: zone_counts[1] += 1
                    elif n <= q3: zone_counts[2] += 1
                    else: zone_counts[3] += 1
                max_zone = max(zone_counts) if zone_counts else 1
                for num in range(min_num, max_num + 1):
                    if num <= q1: zc = zone_counts[0]
                    elif num <= q2: zc = zone_counts[1]
                    elif num <= q3: zc = zone_counts[2]
                    else: zc = zone_counts[3]
                    scores[num] += (zc / max_zone) * config['dynamic_zone_weight']

        # 6. 尾數分析
        if config.get('last_digit_weight', 0) > 0:
            recent = history[-20:]
            digit_counts = Counter()
            for draw in recent:
                for num in draw['numbers']:
                    digit_counts[num % 10] += 1
            max_digit = max(digit_counts.values()) if digit_counts else 1
            for num in range(min_num, max_num + 1):
                scores[num] += (digit_counts[num % 10] / max_digit) * config['last_digit_weight']

        # 7. 奇偶分析
        if config.get('odd_even_weight', 0) > 0:
            recent = history[-20:]
            odd_count = sum(1 for d in recent for n in d['numbers'] if n % 2 != 0)
            total = sum(len(d['numbers']) for d in recent)
            odd_ratio = odd_count / total if total > 0 else 0.5
            
            for num in range(min_num, max_num + 1):
                is_odd = num % 2 != 0
                base = odd_ratio if is_odd else (1 - odd_ratio)
                scores[num] += (0.3 + base * 0.4) * config['odd_even_weight']

        # 8. 連號/配對（共現）分析
        if config.get('pair_weight', 0) > 0 and len(history) >= 30:
            window = min(60, len(history))
            recent = history[-window:]
            co_occurrence = Counter()
            for draw in recent:
                nums = sorted(draw['numbers'])
                # 計算所有二元組配對
                for i in range(len(nums)):
                    for j in range(i+1, len(nums)):
                        co_occurrence[(nums[i], nums[j])] += 1
            # 為每個號碼導出其與其它號碼的共現強度總和
            pair_strength = {n:0 for n in range(min_num, max_num+1)}
            for (a,b), cnt in co_occurrence.items():
                pair_strength[a] += cnt
                pair_strength[b] += cnt
            max_ps = max(pair_strength.values()) if pair_strength else 1
            for num in range(min_num, max_num+1):
                scores[num] += (pair_strength.get(num,0)/max_ps) * config['pair_weight']

        # 9. 和值/AC 值分段分析
        if (config.get('sum_band_weight', 0) > 0 or config.get('ac_band_weight', 0) > 0) and len(history) >= 40:
            recent = history[-80:] if len(history) >= 80 else history
            # 計算每期的和值與 AC 值
            sum_list = []
            ac_list = []
            for draw in recent:
                nums = sorted(draw['numbers'])
                s = sum(nums)
                # AC 值（Distinct pairwise difference count - (k-1)），簡化近似版
                diffs = set()
                for i in range(len(nums)):
                    for j in range(i+1, len(nums)):
                        diffs.add(nums[j]-nums[i])
                ac = max(0, len(diffs) - (len(nums)-1))
                sum_list.append(s)
                ac_list.append(ac)
            # 分段（四分位）
            sum_q1, sum_q2, sum_q3 = np.percentile(sum_list, [25,50,75]) if sum_list else (0,0,0)
            ac_q1, ac_q2, ac_q3 = np.percentile(ac_list, [25,50,75]) if ac_list else (0,0,0)
            # 估算號碼對分段的貢獻：以加入該號碼時的和值趨近常見區段為佳
            # 近似：以該號碼本身的位置（數值大小）近似對和值的貢獻；AC 用號碼與中位數的距離近似
            median_num = (min_num + max_num)/2
            sum_max = max(sum_list) if sum_list else 1
            ac_max = max(ac_list) if ac_list else 1
            for num in range(min_num, max_num+1):
                # 和值分段分數（偏向出現較多的區段）
                # 使用號碼值近似：小號偏向低和值區，大號偏向高和值區
                if config.get('sum_band_weight', 0) > 0 and sum_list:
                    if num <= median_num:
                        # 低區傾向（<= q2）
                        sum_band_score = (len([s for s in sum_list if s <= sum_q2]) / len(sum_list))
                    else:
                        # 高區傾向（> q2）
                        sum_band_score = (len([s for s in sum_list if s > sum_q2]) / len(sum_list))
                    scores[num] += sum_band_score * config['sum_band_weight']
                # AC 分段分數（靠近常見 AC 區段）
                if config.get('ac_band_weight', 0) > 0 and ac_list:
                    # 近似：與中位數距離越小，越可能落在常見 AC 區段
                    dist = abs(num - median_num)
                    # 正規化到 0..1，距離越小分數越高
                    ac_score = 1.0 - (dist / (max_num - min_num))
                    # 放大到與常見 AC 區段比例合成
                    common_ac_ratio = len([a for a in ac_list if ac_q1 <= a <= ac_q3]) / len(ac_list)
                    scores[num] += ac_score * common_ac_ratio * config['ac_band_weight']
        
        # 選擇得分最高的號碼
        sorted_numbers = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted([num for num, _ in sorted_numbers[:pick_count]])
    
    def _evolve_population(self, population: List[Dict], fitness_scores: List[float]) -> List[Dict]:
        """
        演化種群：選擇、交叉、變異
        """
        new_population = []
        
        # 精英保留（保留前 20%）
        elite_count = max(2, len(population) // 5)
        elite_indices = np.argsort(fitness_scores)[-elite_count:]
        for idx in elite_indices:
            new_population.append(population[idx].copy())
        
        # 填充剩餘人口
        while len(new_population) < len(population):
            # 錦標賽選擇
            parent1 = self._tournament_selection(population, fitness_scores)
            parent2 = self._tournament_selection(population, fitness_scores)
            
            # 交叉
            child = self._crossover(parent1, parent2)
            
            # 變異
            child = self._mutate(child)
            
            new_population.append(child)
        
        return new_population
    
    def _tournament_selection(self, population: List[Dict], fitness_scores: List[float], k: int = 3) -> Dict:
        """
        錦標賽選擇
        """
        indices = np.random.choice(len(population), k, replace=False)
        best_idx = indices[np.argmax([fitness_scores[i] for i in indices])]
        return population[best_idx].copy()
    
    def _crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """
        交叉操作（單點交叉）
        """
        child = {}
        keys = list(parent1.keys())
        crossover_point = np.random.randint(1, len(keys))
        
        for i, key in enumerate(keys):
            child[key] = parent1[key] if i < crossover_point else parent2[key]
        
        # 歸一化權重
        weight_keys = [
            'frequency_weight', 'missing_weight', 'hot_cold_weight', 'trend_weight',
            'zone_weight', 'last_digit_weight', 'odd_even_weight'
        ]
        
        # 檢查是否有任何權重鍵存在
        existing_keys = [k for k in weight_keys if k in child]
        if existing_keys:
            total_weight = sum(child[k] for k in existing_keys)
            if total_weight > 0:
                for key in existing_keys:
                    child[key] /= total_weight
        
        return child
    
    def _mutate(self, config: Dict, mutation_rate: float = 0.2) -> Dict:
        """
        變異操作
        """
        mutated = config.copy()
        
        for key in mutated:
            if np.random.random() < mutation_rate:
                if 'weight' in key:
                    # 權重微調
                    mutated[key] *= np.random.uniform(0.8, 1.2)
                elif 'window' in key:
                    # 窗口大小微調
                    mutated[key] = int(mutated[key] * np.random.uniform(0.8, 1.2))
                    mutated[key] = max(10, mutated[key])  # 最小值限制
        
        # 歸一化權重
        weight_keys = [
            'frequency_weight', 'missing_weight', 'hot_cold_weight', 'trend_weight',
            'zone_weight', 'last_digit_weight', 'odd_even_weight'
        ]
        
        existing_keys = [k for k in weight_keys if k in mutated]
        if existing_keys:
            total_weight = sum(mutated[k] for k in existing_keys)
            if total_weight > 0:
                for key in existing_keys:
                    mutated[key] /= total_weight
        
        return mutated
    
    def get_best_config(self) -> Dict:
        """
        獲取最佳配置
        """
        return self.best_config if self.best_config else {}
    
    def get_optimization_history(self) -> List[Dict]:
        """
        獲取優化歷史
        """
        return self.optimization_history
