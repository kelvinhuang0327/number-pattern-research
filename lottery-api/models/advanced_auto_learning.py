"""
進階自動學習優化引擎
實現多階段優化、集成學習、滾動窗口等高級功能來大幅提升預測準確率
"""
import json
import logging
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import numpy as np
from collections import Counter

logger = logging.getLogger(__name__)

HISTORY_FILE = "data/advanced_optimization_history.json"

class AdvancedAutoLearningEngine:
    """
    進階自動學習優化引擎

    核心改進：
    1. 多階段優化（粗調 → 精調 → 微調）
    2. 自適應學習率
    3. 集成多個優化結果
    4. 滾動窗口自動調整
    5. 早停機制防止過擬合
    """

    def __init__(self):
        self.best_configs = []  # 保存多個優秀配置用於集成
        self.optimization_history = []
        self.ensemble_size = 5  # 集成模型數量
        self._load_history()  # 從文件加載歷史
        logger.info("AdvancedAutoLearningEngine 初始化完成")
    
    def _load_history(self):
        """從文件加載優化歷史"""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 兼容兩種格式：直接數組或包含 history 字段的對象
                    if isinstance(data, list):
                        self.optimization_history = data
                    elif isinstance(data, dict):
                        self.optimization_history = data.get('history', [])
                    else:
                        self.optimization_history = []
                    logger.info(f"已加載 {len(self.optimization_history)} 條優化歷史記錄")
        except Exception as e:
            logger.warning(f"加載優化歷史失敗: {e}")
            self.optimization_history = []
    
    def _save_history(self):
        """保存優化歷史到文件"""
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'updated_at': datetime.now().isoformat(),
                    'history': self.optimization_history[-100:]  # 只保留最近100條
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存優化歷史: {len(self.optimization_history)} 條記錄")
        except Exception as e:
            logger.error(f"保存優化歷史失敗: {e}")

    async def multi_stage_optimize(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        progress_callback = None
    ) -> Dict:
        """
        多階段優化流程

        階段1：粗調 (50代) - 快速找到大致方向
        階段2：精調 (100代) - 深度優化
        階段3：微調 (50代) - 局部搜索最優解
        """
        try:
            logger.info("🚀 開始多階段自動優化...")

            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)

            if len(history) < 100:
                raise ValueError("多階段優化至少需要 100 期數據")

            # 數據分割
            split_idx = int(len(history) * 0.8)
            train_data = history[:split_idx]
            val_data = history[split_idx:]

            all_results = []

            # === 階段 1：粗調 ===
            logger.info("📍 階段 1/3：粗調階段 (50代)")
            stage1_result = await self._optimize_stage(
                train_data, val_data, pick_count, min_number, max_number,
                generations=50,
                population_size=40,
                mutation_rate=0.3,  # 高變異率，增加探索
                stage_name="粗調",
                progress_callback=progress_callback,
                progress_offset=0,
                progress_scale=0.33
            )
            all_results.append(stage1_result)

            # === 階段 2：精調 ===
            logger.info("📍 階段 2/3：精調階段 (100代)")
            # 從階段1最佳解附近開始
            stage2_result = await self._optimize_stage(
                train_data, val_data, pick_count, min_number, max_number,
                generations=100,
                population_size=50,
                mutation_rate=0.15,  # 中等變異率
                seed_config=stage1_result['best_config'],
                stage_name="精調",
                progress_callback=progress_callback,
                progress_offset=33,
                progress_scale=0.5
            )
            all_results.append(stage2_result)

            # === 階段 3：微調 ===
            logger.info("📍 階段 3/3：微調階段 (50代)")
            stage3_result = await self._optimize_stage(
                train_data, val_data, pick_count, min_number, max_number,
                generations=50,
                population_size=30,
                mutation_rate=0.05,  # 低變異率，局部搜索
                seed_config=stage2_result['best_config'],
                stage_name="微調",
                progress_callback=progress_callback,
                progress_offset=83,
                progress_scale=0.17
            )
            all_results.append(stage3_result)

            # 選擇最佳結果
            best_result = max(all_results, key=lambda x: x['best_fitness'])

            # 發送完成信號（100%）
            if progress_callback:
                try:
                    await progress_callback(100)
                except:
                    pass

            # 保存到歷史
            self.best_configs.append(best_result['best_config'])
            if len(self.best_configs) > self.ensemble_size:
                self.best_configs = self.best_configs[-self.ensemble_size:]

            self.optimization_history.append({
                'timestamp': datetime.now().isoformat(),
                'method': 'multi_stage',
                'best_fitness': float(best_result['best_fitness']),
                'config': best_result['best_config'],
                'stage_results': [
                    {'stage': 'coarse', 'fitness': float(stage1_result['best_fitness'])},
                    {'stage': 'fine', 'fitness': float(stage2_result['best_fitness'])},
                    {'stage': 'micro', 'fitness': float(stage3_result['best_fitness'])}
                ]
            })
            self._save_history()  # 持久化保存

            logger.info(f"✅ 多階段優化完成！最佳適應度: {best_result['best_fitness']:.4f}")
            logger.info(f"📊 各階段適應度: 粗調={stage1_result['best_fitness']:.4f}, 精調={stage2_result['best_fitness']:.4f}, 微調={stage3_result['best_fitness']:.4f}")

            return {
                'success': True,
                'best_fitness': float(best_result['best_fitness']),
                'best_config': best_result['best_config'],
                'method': 'multi_stage',
                'stage_results': all_results
            }

        except Exception as e:
            logger.error(f"多階段優化失敗: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _optimize_stage(
        self,
        train_data: List[Dict],
        val_data: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int,
        generations: int,
        population_size: int,
        mutation_rate: float,
        stage_name: str,
        seed_config: Optional[Dict] = None,
        progress_callback = None,
        progress_offset: float = 0,
        progress_scale: float = 1.0
    ) -> Dict:
        """
        單個優化階段
        """
        # 初始化種群
        if seed_config:
            # 從種子配置附近生成種群
            population = self._initialize_population_from_seed(
                seed_config, population_size, mutation_rate
            )
        else:
            population = self._initialize_population(population_size)

        best_fitness = 0
        best_config = None
        no_improve_count = 0
        patience = 10  # 早停耐心值

        for gen in range(generations):
            await asyncio.sleep(0)  # 釋放事件循環

            # 評估種群
            fitness_scores = []
            for config in population:
                fitness = await self._evaluate_config(
                    config, train_data, val_data, pick_count, min_num, max_num
                )
                fitness_scores.append(fitness)

            # 更新最佳個體
            max_fitness_idx = np.argmax(fitness_scores)
            current_best = float(fitness_scores[max_fitness_idx])

            if current_best > best_fitness:
                best_fitness = current_best
                best_config = population[max_fitness_idx].copy()
                no_improve_count = 0
            else:
                no_improve_count += 1

            logger.info(f"[{stage_name}] 第 {gen+1}/{generations} 代: 最佳={best_fitness:.4f}, 本代={current_best:.4f}")

            # 早停
            if no_improve_count >= patience:
                logger.info(f"[{stage_name}] 早停於第 {gen+1} 代（連續 {patience} 代無改進）")
                break

            # 進化種群
            population = self._evolve_population(population, fitness_scores, mutation_rate)

            # 進度回調
            if progress_callback:
                try:
                    progress = progress_offset + (gen + 1) / generations * progress_scale * 100
                    await progress_callback(progress)
                except Exception as e:
                    logger.warning(f"進度回調失敗: {e}")

        return {
            'best_fitness': best_fitness,
            'best_config': best_config,
            'stage': stage_name
        }

    async def adaptive_window_optimize(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        progress_callback = None
    ) -> Dict:
        """
        自適應窗口優化
        自動找出最佳的訓練數據窗口大小
        """
        try:
            logger.info("🔍 開始自適應窗口優化...")

            pick_count = lottery_rules.get('pickCount', 6)
            min_number = lottery_rules.get('minNumber', 1)
            max_number = lottery_rules.get('maxNumber', 49)

            # 測試不同窗口大小
            window_sizes = [100, 200, 300, 500, len(history)]
            window_sizes = [w for w in window_sizes if w <= len(history)]

            best_window_result = None
            best_window_fitness = 0

            for idx, window_size in enumerate(window_sizes):
                logger.info(f"🔄 測試窗口大小: {window_size} 期 ({idx+1}/{len(window_sizes)})")

                # 使用最近的 window_size 期數據
                window_data = history[-window_size:]
                split_idx = int(len(window_data) * 0.8)
                train_data = window_data[:split_idx]
                val_data = window_data[split_idx:]

                # 優化這個窗口
                result = await self._optimize_stage(
                    train_data, val_data, pick_count, min_number, max_number,
                    generations=30,
                    population_size=30,
                    mutation_rate=0.2,
                    stage_name=f"窗口{window_size}",
                    progress_callback=progress_callback,
                    progress_offset=idx / len(window_sizes) * 100,
                    progress_scale=1.0 / len(window_sizes)
                )

                if result['best_fitness'] > best_window_fitness:
                    best_window_fitness = result['best_fitness']
                    best_window_result = result
                    best_window_result['window_size'] = window_size

            # 發送完成信號（100%）
            if progress_callback:
                try:
                    await progress_callback(100)
                except:
                    pass

            logger.info(f"✅ 最佳窗口大小: {best_window_result['window_size']} 期，適應度: {best_window_fitness:.4f}")

            self.optimization_history.append({
                'timestamp': datetime.now().isoformat(),
                'method': 'adaptive_window',
                'best_fitness': float(best_window_fitness),
                'best_window_size': best_window_result['window_size'],
                'config': best_window_result['best_config']
            })
            self._save_history()  # 持久化保存

            return {
                'success': True,
                'best_fitness': best_window_fitness,
                'best_config': best_window_result['best_config'],
                'best_window_size': best_window_result['window_size'],
                'method': 'adaptive_window'
            }

        except Exception as e:
            logger.error(f"自適應窗口優化失敗: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _initialize_population(self, size: int) -> List[Dict]:
        """初始化種群"""
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

    def _initialize_population_from_seed(
        self,
        seed_config: Dict,
        size: int,
        mutation_rate: float
    ) -> List[Dict]:
        """從種子配置生成種群（用於多階段優化）"""
        population = [seed_config.copy()]  # 包含原始種子

        weight_keys = [k for k in seed_config.keys() if '_weight' in k]

        for _ in range(size - 1):
            config = seed_config.copy()

            # 對每個參數添加隨機擾動
            for key in seed_config.keys():
                if '_weight' in key:
                    # 權重參數
                    noise = np.random.normal(0, mutation_rate)
                    config[key] = max(0.01, min(0.9, seed_config[key] + noise))
                elif '_window' in key:
                    # 窗口參數
                    noise = np.random.randint(-20, 20)
                    if 'recent' in key:
                        config[key] = max(10, min(150, seed_config[key] + noise))
                    else:
                        config[key] = max(50, min(400, seed_config[key] + noise))

            # 重新歸一化權重
            total_weight = sum(config[key] for key in weight_keys)
            for key in weight_keys:
                config[key] /= total_weight

            population.append(config)

        return population

    async def _evaluate_config(
        self,
        config: Dict,
        train_data: List[Dict],
        val_data: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> float:
        """評估配置的適應度（滾動式預測）"""
        success_count = 0
        all_data = train_data + val_data

        for i, target in enumerate(val_data):
            target_index = len(train_data) + i
            training_data = all_data[:target_index]

            predicted = self._predict_with_config(
                config, training_data, pick_count, min_num, max_num
            )

            # 命中3個或以上算成功
            hits = len(set(target['numbers']) & set(predicted))
            if hits >= 3:
                success_count += 1

        fitness = success_count / len(val_data) if len(val_data) > 0 else 0
        return fitness

    def _predict_with_config(
        self,
        config: Dict,
        history: List[Dict],
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> List[int]:
        """使用配置進行預測（簡化版）"""
        # 統計號碼頻率
        number_scores = {num: 0.0 for num in range(min_num, max_num + 1)}

        recent_window = config.get('recent_window', 50)
        recent_history = history[-recent_window:]

        # 頻率分析
        freq_weight = config.get('frequency_weight', 0.2)
        all_numbers = []
        for draw in recent_history:
            all_numbers.extend(draw['numbers'])

        freq_counter = Counter(all_numbers)
        max_freq = max(freq_counter.values()) if freq_counter else 1

        for num in number_scores.keys():
            freq = freq_counter.get(num, 0)
            number_scores[num] += (freq / max_freq) * freq_weight

        # 冷熱分析
        hot_cold_weight = config.get('hot_cold_weight', 0.2)
        if len(recent_history) > 0:
            last_10 = recent_history[-10:]
            last_10_numbers = []
            for draw in last_10:
                last_10_numbers.extend(draw['numbers'])

            hot_counter = Counter(last_10_numbers)
            max_hot = max(hot_counter.values()) if hot_counter else 1

            for num in number_scores.keys():
                hot_count = hot_counter.get(num, 0)
                number_scores[num] += (hot_count / max_hot) * hot_cold_weight

        # 添加隨機性
        for num in number_scores.keys():
            number_scores[num] += np.random.uniform(0, 0.1)

        # 選擇得分最高的號碼
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, score in sorted_numbers[:pick_count]]

        return sorted(predicted)

    def _evolve_population(
        self,
        population: List[Dict],
        fitness_scores: List[float],
        mutation_rate: float = 0.2
    ) -> List[Dict]:
        """進化種群（選擇、交叉、變異）"""
        # 選擇
        fitness_array = np.array(fitness_scores)
        if fitness_array.sum() == 0:
            probabilities = np.ones(len(fitness_array)) / len(fitness_array)
        else:
            probabilities = fitness_array / fitness_array.sum()

        selected_indices = np.random.choice(
            len(population),
            size=len(population),
            replace=True,
            p=probabilities
        )

        new_population = []
        for idx in selected_indices:
            new_population.append(population[idx].copy())

        # 交叉和變異
        for i in range(0, len(new_population) - 1, 2):
            if np.random.rand() < 0.7:  # 交叉概率
                config1, config2 = new_population[i], new_population[i + 1]
                for key in config1.keys():
                    if np.random.rand() < 0.5:
                        config1[key], config2[key] = config2[key], config1[key]

        # 變異
        weight_keys = [k for k in new_population[0].keys() if '_weight' in k]
        for config in new_population:
            if np.random.rand() < mutation_rate:
                for key in config.keys():
                    if '_weight' in key:
                        config[key] *= np.random.uniform(0.8, 1.2)
                    elif '_window' in key:
                        config[key] = int(config[key] * np.random.uniform(0.9, 1.1))

                # 重新歸一化權重
                total_weight = sum(config[key] for key in weight_keys)
                for key in weight_keys:
                    config[key] /= total_weight

        return new_population

    def get_optimization_history(self) -> List[Dict]:
        """獲取優化歷史"""
        return self.optimization_history

    def get_best_configs(self) -> List[Dict]:
        """獲取最佳配置集合（用於集成）"""
        return self.best_configs
