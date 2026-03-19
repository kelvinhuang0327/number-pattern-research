"""
智能自動學習排程系統
定期執行策略評估 → 選擇最佳策略 → 優化參數 → 更新預測方法
"""
import asyncio
import logging
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from models.advanced_auto_learning import AdvancedAutoLearningEngine
from models.strategy_evaluator import StrategyEvaluator

import os

logger = logging.getLogger(__name__)

DATA_FILE = "data/lottery_history.json"
BEST_STRATEGY_FILE = "data/best_strategy.json"
LEARNING_LOG_FILE = "data/learning_log.json"

class SmartLearningScheduler:
    """
    智能自動學習排程調度器

    工作流程:
    1. 定期執行策略評估，找出成功率最高的策略
    2. 當成功率達到標準（可配置），更新為推薦策略
    3. 對推薦策略執行參數優化，進一步提升性能
    4. 將優化後的策略保存，供前端智能預測使用
    """

    def __init__(self, success_threshold: float = 0.30):
        """
        初始化智能排程器

        Args:
            success_threshold: 成功率閾值（默認30%，即至少命中3個號碼的比例）
        """
        self.scheduler = AsyncIOScheduler()
        self.auto_learning_engine = AdvancedAutoLearningEngine()
        self.strategy_evaluator = StrategyEvaluator()

        self.is_running = False
        self.success_threshold = success_threshold

        # 數據存儲（按彩券類型分類）
        self.data_by_type = {}
        self.lottery_rules_by_type = {}

        # 最佳策略緩存（按彩券類型）
        self.best_strategies = {}  # {'BIG_LOTTO': {'strategy': 'ensemble', 'success_rate': 0.35, ...}}

        # 學習歷史記錄
        self.learning_history = []

        # 嘗試從磁碟加載數據
        self.load_data_from_disk()
        self.load_best_strategies()
        self.load_learning_history()

        logger.info(f"SmartLearningScheduler 初始化完成（成功率閾值: {success_threshold*100}%）")

    def start(self, evaluation_schedule: str = "02:00", learning_schedule: str = "03:00"):
        """
        啟動排程

        Args:
            evaluation_schedule: 策略評估時間（格式: "HH:MM"）
            learning_schedule: 參數優化時間（格式: "HH:MM"）
        """
        try:
            # 添加策略評估任務
            eval_hour, eval_minute = map(int, evaluation_schedule.split(':'))
            self.scheduler.add_job(
                self._run_strategy_evaluation,
                trigger=CronTrigger(hour=eval_hour, minute=eval_minute),
                id='strategy_evaluation',
                name='每日策略評估',
                replace_existing=True
            )

            # 添加參數優化任務
            learn_hour, learn_minute = map(int, learning_schedule.split(':'))
            self.scheduler.add_job(
                self._run_parameter_optimization,
                trigger=CronTrigger(hour=learn_hour, minute=learn_minute),
                id='parameter_optimization',
                name='每日參數優化',
                replace_existing=True
            )

            if not self.scheduler.running:
                self.scheduler.start()

            self.is_running = True
            logger.info(f"智能排程已啟動:")
            logger.info(f"  - 策略評估: 每天 {evaluation_schedule}")
            logger.info(f"  - 參數優化: 每天 {learning_schedule}")

        except Exception as e:
            logger.error(f"啟動排程失敗: {str(e)}")
            raise

    def stop(self):
        """停止排程"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("智能排程已停止")

    async def _run_strategy_evaluation(self):
        """
        執行策略評估任務

        流程:
        1. 對每種彩券類型執行策略評估
        2. 找出成功率最高的策略
        3. 如果成功率達到閾值，更新為最佳策略
        4. 記錄評估結果
        """
        try:
            logger.info("=" * 60)
            logger.info("開始執行策略評估任務...")

            # 對每種彩券類型分別評估
            for lottery_type, history in self.data_by_type.items():
                if len(history) < 50:
                    logger.warning(f"{lottery_type}: 數據不足（{len(history)} 期），跳過")
                    continue

                logger.info(f"\n處理彩券類型: {lottery_type}")
                logger.info(f"數據量: {len(history)} 期")

                # 獲取彩券規則
                lottery_rules = self.lottery_rules_by_type.get(lottery_type, {
                    'pickCount': 6,
                    'minNumber': 1,
                    'maxNumber': 49
                })

                # 執行策略評估
                evaluation_result = self.strategy_evaluator.evaluate_all_strategies(
                    history=history,
                    lottery_rules=lottery_rules,
                    test_ratio=0.2,
                    min_train_size=30
                )

                if not evaluation_result.get('success'):
                    logger.error(f"{lottery_type}: 評估失敗 - {evaluation_result.get('error')}")
                    continue

                # 獲取最佳策略
                best_strategy_info = evaluation_result['best_strategy']
                strategy_name = best_strategy_info['strategy_name']
                success_rate = best_strategy_info['metrics']['success_rate']
                avg_hits = best_strategy_info['metrics']['avg_hits']

                logger.info(f"最佳策略: {strategy_name}")
                logger.info(f"成功率: {success_rate*100:.2f}%")
                logger.info(f"平均命中: {avg_hits:.2f} 個")

                # 檢查是否達到閾值
                if success_rate >= self.success_threshold:
                    logger.info(f"✅ 成功率達標（>= {self.success_threshold*100}%），更新最佳策略")

                    # 更新最佳策略
                    self.best_strategies[lottery_type] = {
                        'strategy_name': strategy_name,
                        'strategy_id': best_strategy_info['strategy_id'],
                        'success_rate': success_rate,
                        'avg_hits': avg_hits,
                        'perfect_hits': best_strategy_info['metrics']['perfect_hits'],
                        'score': best_strategy_info['score'],
                        'updated_at': datetime.now().isoformat(),
                        'data_size': len(history),
                        'evaluation_result': evaluation_result
                    }

                    # 保存到文件
                    self.save_best_strategies()

                else:
                    logger.warning(f"⚠️ 成功率未達標（{success_rate*100:.2f}% < {self.success_threshold*100}%）")
                    logger.warning(f"保持當前策略: {self.best_strategies.get(lottery_type, {}).get('strategy_name', 'None')}")

                # 記錄評估歷史
                self.learning_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'evaluation',
                    'lottery_type': lottery_type,
                    'best_strategy': strategy_name,
                    'success_rate': success_rate,
                    'avg_hits': avg_hits,
                    'reached_threshold': success_rate >= self.success_threshold
                })

            # 保存學習歷史
            self.save_learning_history()

            logger.info("策略評估任務完成")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"執行策略評估失敗: {str(e)}", exc_info=True)

    async def _run_parameter_optimization(self):
        """
        執行參數優化任務

        流程:
        1. 對已確定的最佳策略執行參數優化
        2. 使用遺傳算法微調策略參數
        3. 保存優化後的配置
        """
        try:
            logger.info("=" * 60)
            logger.info("開始執行參數優化任務...")

            # 對每種彩券類型的最佳策略進行優化
            for lottery_type, strategy_info in self.best_strategies.items():
                if lottery_type not in self.data_by_type:
                    logger.warning(f"{lottery_type}: 無數據，跳過優化")
                    continue

                history = self.data_by_type[lottery_type]
                if len(history) < 50:
                    logger.warning(f"{lottery_type}: 數據不足，跳過優化")
                    continue

                logger.info(f"\n優化彩券類型: {lottery_type}")
                logger.info(f"目標策略: {strategy_info['strategy_name']}")
                logger.info(f"當前成功率: {strategy_info['success_rate']*100:.2f}%")

                # 獲取彩券規則
                lottery_rules = self.lottery_rules_by_type.get(lottery_type, {
                    'pickCount': 6,
                    'minNumber': 1,
                    'maxNumber': 49
                })

                # 執行多階段參數優化
                optimization_result = await self.auto_learning_engine.multi_stage_optimize(
                    history=history,
                    lottery_rules=lottery_rules
                )

                if optimization_result.get('success'):
                    best_fitness = optimization_result['best_fitness']
                    logger.info(f"✅ 優化成功，適應度: {best_fitness:.4f}")

                    # 保存優化配置
                    config_file = f'data/best_config_{lottery_type}.json'
                    self._save_config(optimization_result['best_config'], config_file)

                    # 更新策略信息
                    strategy_info['optimized'] = True
                    strategy_info['optimization_fitness'] = best_fitness
                    strategy_info['optimized_at'] = datetime.now().isoformat()

                    # 記錄優化歷史
                    self.learning_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'type': 'optimization',
                        'lottery_type': lottery_type,
                        'strategy': strategy_info['strategy_name'],
                        'fitness': best_fitness,
                        'generations': 30
                    })
                else:
                    logger.error(f"❌ 優化失敗: {optimization_result.get('error')}")

            # 保存更新後的策略和歷史
            self.save_best_strategies()
            self.save_learning_history()

            logger.info("參數優化任務完成")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"執行參數優化失敗: {str(e)}", exc_info=True)

    async def manual_evaluation(self, lottery_type: str) -> dict:
        """
        手動觸發策略評估（供前端調用）

        Args:
            lottery_type: 彩券類型

        Returns:
            評估結果
        """
        try:
            history = self.data_by_type.get(lottery_type, [])
            if len(history) < 50:
                return {
                    'success': False,
                    'error': f'數據不足（{len(history)} 期），至少需要 50 期'
                }

            lottery_rules = self.lottery_rules_by_type.get(lottery_type, {
                'pickCount': 6,
                'minNumber': 1,
                'maxNumber': 49
            })

            # 執行評估
            result = self.strategy_evaluator.evaluate_all_strategies(
                history=history,
                lottery_rules=lottery_rules
            )

            # 如果成功且達標，更新最佳策略
            if result.get('success'):
                best = result['best_strategy']
                if best['metrics']['success_rate'] >= self.success_threshold:
                    self.best_strategies[lottery_type] = {
                        'strategy_name': best['strategy_name'],
                        'strategy_id': best['strategy_id'],
                        'success_rate': best['metrics']['success_rate'],
                        'avg_hits': best['metrics']['avg_hits'],
                        'updated_at': datetime.now().isoformat()
                    }
                    self.save_best_strategies()

            return result

        except Exception as e:
            logger.error(f"手動評估失敗: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def update_data(self, lottery_type: str, history: list, lottery_rules: dict):
        """
        更新特定彩券類型的數據

        Args:
            lottery_type: 彩券類型
            history: 歷史數據
            lottery_rules: 彩券規則
        """
        self.data_by_type[lottery_type] = history
        self.lottery_rules_by_type[lottery_type] = lottery_rules

        logger.info(f"數據已更新: {lottery_type} - {len(history)} 期")
        self.save_data_to_disk()

    def get_best_strategy(self, lottery_type: str) -> dict:
        """
        獲取指定彩券類型的最佳策略

        Args:
            lottery_type: 彩券類型

        Returns:
            最佳策略信息，如果不存在則返回 None
        """
        return self.best_strategies.get(lottery_type)

    def get_all_best_strategies(self) -> dict:
        """獲取所有彩券類型的最佳策略"""
        return self.best_strategies

    def set_success_threshold(self, threshold: float):
        """
        設置成功率閾值

        Args:
            threshold: 新的閾值（0.0 - 1.0）
        """
        if 0 <= threshold <= 1:
            self.success_threshold = threshold
            logger.info(f"成功率閾值已更新為: {threshold*100}%")
        else:
            raise ValueError("閾值必須在 0.0 到 1.0 之間")

    def save_data_to_disk(self):
        """保存數據到磁碟"""
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data_by_type': self.data_by_type,
                    'lottery_rules_by_type': self.lottery_rules_by_type
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"數據已保存至 {DATA_FILE}")
        except Exception as e:
            logger.error(f"保存數據失敗: {str(e)}")

    def load_data_from_disk(self):
        """從磁碟加載數據"""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.data_by_type = data.get('data_by_type', {})
                    self.lottery_rules_by_type = data.get('lottery_rules_by_type', {})
                logger.info(f"已從磁碟加載數據: {list(self.data_by_type.keys())}")
        except Exception as e:
            logger.error(f"加載數據失敗: {str(e)}")

    def save_best_strategies(self):
        """保存最佳策略到文件"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(BEST_STRATEGY_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'success_threshold': self.success_threshold,
                    'strategies': self.best_strategies
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"最佳策略已保存至 {BEST_STRATEGY_FILE}")
        except Exception as e:
            logger.error(f"保存最佳策略失敗: {str(e)}")

    def load_best_strategies(self):
        """從文件加載最佳策略"""
        try:
            if os.path.exists(BEST_STRATEGY_FILE):
                with open(BEST_STRATEGY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.best_strategies = data.get('strategies', {})
                    self.success_threshold = data.get('success_threshold', self.success_threshold)
                logger.info(f"已加載最佳策略: {list(self.best_strategies.keys())}")
        except Exception as e:
            logger.error(f"加載最佳策略失敗: {str(e)}")

    def save_learning_history(self):
        """保存學習歷史"""
        try:
            os.makedirs('data', exist_ok=True)
            # 只保留最近 100 條記錄
            recent_history = self.learning_history[-100:]
            with open(LEARNING_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(recent_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存學習歷史失敗: {str(e)}")

    def load_learning_history(self):
        """加載學習歷史"""
        try:
            if os.path.exists(LEARNING_LOG_FILE):
                with open(LEARNING_LOG_FILE, 'r', encoding='utf-8') as f:
                    self.learning_history = json.load(f)
                logger.info(f"已加載學習歷史: {len(self.learning_history)} 條")
        except Exception as e:
            logger.error(f"加載學習歷史失敗: {str(e)}")

    def get_schedule_status(self) -> dict:
        """獲取排程狀態"""
        jobs = []
        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                })

        return {
            'is_running': self.is_running,
            'success_threshold': self.success_threshold,
            'jobs': jobs,
            'best_strategies': self.best_strategies,
            'learning_history': self.learning_history[-10:],  # 最近10條
            'data_available': list(self.data_by_type.keys())
        }

    def _save_config(self, config: dict, filename: str):
        """保存配置到文件"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'config': config
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到 {filename}")
        except Exception as e:
            logger.error(f"保存配置失敗: {str(e)}")


# 全局智能調度器實例
smart_scheduler = SmartLearningScheduler(success_threshold=0.30)
