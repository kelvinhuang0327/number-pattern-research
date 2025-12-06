"""
自動學習排程系統
定期執行優化任務
"""
import asyncio
import logging
import json
from datetime import datetime, time
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from models.auto_learning import AutoLearningEngine

import os

logger = logging.getLogger(__name__)

# 使用絕對路徑，確保從任何目錄執行都能正確找到配置文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "lottery_history.json")

class AutoLearningScheduler:
    """
    自動學習排程調度器
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.engine = AutoLearningEngine()
        self.is_running = False
        # 🚀 優化：分類存儲數據（按彩券類型）
        self.data_by_type = {}  # {'BIG_LOTTO': [...], 'POWER_LOTTO': [...]}
        self.latest_data = None  # 保留向後兼容
        self.lottery_rules = None
        self.current_progress = 0
        self.current_generation = 0
        self.total_generations = 0
        self.is_optimizing = False  # 新增：優化狀態標誌
        self.optimization_message = ""  # 新增：優化狀態訊息
        self.last_optimization_at = None  # 新增：最後一次優化完成時間戳
        self.target_fitness = None  # 🎯 新增：目標適應度（達標後停止）

        # 嘗試從磁碟加載數據
        self.load_data_from_disk()
        logger.info("AutoLearningScheduler 初始化完成（已啟用分類存儲與持久化）")
    
    def start(self, schedule_time: str = "02:00"):
        """
        啟動排程
        
        Args:
            schedule_time: 執行時間（格式: "HH:MM"）
        """
        try:
            hour, minute = map(int, schedule_time.split(':'))
            
            # 添加每日優化任務
            self.scheduler.add_job(
                self._run_optimization,
                trigger=CronTrigger(hour=hour, minute=minute),
                id='daily_optimization',
                name='每日自動優化',
                replace_existing=True
            )
            
            if not self.scheduler.running:
                self.scheduler.start()
            
            self.is_running = True
            logger.info(f"排程已啟動: 每天 {schedule_time} 執行優化")
            
        except Exception as e:
            logger.error(f"啟動排程失敗: {str(e)}")
            raise
    
    def stop(self):
        """
        停止排程
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("排程已停止")
    
    async def _run_optimization(self):
        """
        執行優化任務（內部方法）
        """
        try:
            self.is_optimizing = True
            self.optimization_message = "正在初始化優化任務..."
            logger.info("開始執行排程優化任務...")

            # 如果沒有數據，嘗試加載
            if not self.latest_data:
                self.load_data()

            if not self.latest_data or not self.lottery_rules:
                logger.warning("缺少數據或規則，跳過優化")
                self.is_optimizing = False
                self.optimization_message = "缺少數據或規則"
                return

            # 定義進度回調
            async def progress_callback(progress):
                self.current_progress = progress
                self.current_generation = int(progress / 100 * self.total_generations)
                self.optimization_message = f"正在優化第 {self.current_generation}/{self.total_generations} 代..."

            self.current_progress = 0
            self.total_generations = 30
            self.optimization_message = "開始優化..."
            
            # 🔧 排程優化使用完整數據（max_data_limit=None）
            # 將重運算優化移交至執行緒池，避免阻塞事件迴圈
            loop = asyncio.get_running_loop()
            def _run_opt():
                return asyncio.run(self.engine.optimize(
                    history=self.latest_data,
                    lottery_rules=self.lottery_rules,
                    generations=self.total_generations,
                    population_size=50,
                    progress_callback=progress_callback,
                    max_data_limit=None,  # 排程優化不限制數據量
                    target_fitness=self.target_fitness  # 🎯 目標適應度早停
                ))
            result = await loop.run_in_executor(None, _run_opt)
            
            self.current_progress = 100

            if result['success']:
                logger.info(f"優化成功: 適應度 {result['best_fitness']:.4f}")
                # 保存配置到文件
                lt = self._infer_lottery_type(self.latest_data)
                self._save_config(result['best_config'], lt)
                self.optimization_message = f"優化完成！適應度: {result['best_fitness']:.4f}"
                self.last_optimization_at = datetime.now().isoformat()
            else:
                logger.error(f"優化失敗: {result.get('error', 'Unknown')}")
                self.optimization_message = f"優化失敗: {result.get('error', 'Unknown')}"

            self.is_optimizing = False

        except Exception as e:
            logger.error(f"執行優化任務失敗: {str(e)}", exc_info=True)
            self.current_progress = 0
            self.is_optimizing = False
            self.optimization_message = f"優化失敗: {str(e)}"
    
    async def run_manual_optimization(
        self,
        history: list,
        lottery_rules: dict,
        generations: int = 20,
        population_size: int = 30,
        target_fitness: float = None
    ) -> dict:
        """
        手動觸發優化（前端發起）
        """
        # 🔧 手動優化限制數據量為 500 期（前端已限制 300 期）
        # 將重運算優化移交至執行緒池，避免阻塞事件迴圈
        loop = asyncio.get_running_loop()
        def _run_opt_manual():
            return asyncio.run(self.engine.optimize(
                history=history,
                lottery_rules=lottery_rules,
                generations=generations,
                population_size=population_size,
                max_data_limit=None,  # 使用完整數據進行優化
                target_fitness=target_fitness  # 🎯 支持目標適應度
            ))
        result = await loop.run_in_executor(None, _run_opt_manual)
        
        # ✅ 如果優化成功，保存配置到文件
        if result['success']:
            lt = self._infer_lottery_type(history)
            self._save_config(result['best_config'], lt)
            self.last_optimization_at = datetime.now().isoformat()
            
        return result
    
    def update_data(self, history: list, lottery_rules: dict):
        """
        更新數據（用於排程優化）
        🚀 優化：自動分類存儲，提升 100-1000 倍查詢速度
        """
        # 保留原始數據（向後兼容）
        self.latest_data = history
        self.lottery_rules = lottery_rules
        
        # 🚀 新增：按類型分類存儲
        self.data_by_type.clear()
        for draw in history:
            l_type = draw.get('lotteryType', 'UNKNOWN')
            if l_type not in self.data_by_type:
                self.data_by_type[l_type] = []
            self.data_by_type[l_type].append(draw)
            
        logger.info(f"數據已分類存儲: { {k: len(v) for k, v in self.data_by_type.items()} }")
        
        # 💾 持久化保存
        self.save_data_to_disk()

    def save_data_to_disk(self):
        """保存數據到磁碟"""
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data_by_type': self.data_by_type,
                    'lottery_rules': self.lottery_rules # Persist lottery_rules
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
                    self.lottery_rules = data.get('lottery_rules') # Load lottery_rules
                
                # 重建 latest_data (向後兼容)
                all_data = []
                for draws in self.data_by_type.values():
                    all_data.extend(draws)
                self.latest_data = all_data
                
                logger.info(f"已從磁碟加載數據: { {k: len(v) for k, v in self.data_by_type.items()} }")
            else:
                logger.info("無本地數據文件，等待同步")
        except Exception as e:
            logger.error(f"加載數據失敗: {str(e)}")
    
    def get_data(self, lottery_type: str) -> list:
        """
        🚀 快速獲取指定類型數據（O(1) 時間複雜度）
        
        Args:
            lottery_type: 彩券類型（如 'BIG_LOTTO'）
        
        Returns:
            該類型的所有數據，如果不存在則返回空列表
        """
        return self.data_by_type.get(lottery_type, [])
    
    def get_all_types(self) -> list:
        """
        獲取所有可用的彩券類型
        """
        return list(self.data_by_type.keys())

    def set_target_fitness(self, target: float):
        """
        🎯 設定目標適應度

        Args:
            target: 目標適應度值 (0.0 - 1.0)，None 表示禁用早停
        """
        if target is not None:
            if not (0 < target <= 1.0):
                raise ValueError("目標適應度必須在 0 到 1 之間")
            logger.info(f"⭐ 設定目標適應度: {target:.4f}")
        else:
            logger.info("⭐ 已禁用目標適應度早停")
        self.target_fitness = target

    def save_data(self, history: list, lottery_rules: dict):
        """
        保存數據到文件
        """
        try:
            import os
            os.makedirs('data', exist_ok=True)
            with open('data/latest_history.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'history': history,
                    'lottery_rules': lottery_rules
                }, f, ensure_ascii=False)
            logger.info("數據已保存到 data/latest_history.json")
        except Exception as e:
            logger.error(f"保存數據失敗: {str(e)}")

    def load_data(self):
        """
        從文件加載數據
        """
        try:
            with open('data/latest_history.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.latest_data = data.get('history')
                self.lottery_rules = data.get('lottery_rules')
                logger.info(f"數據已加載: {len(self.latest_data) if self.latest_data else 0} 筆")
        except FileNotFoundError:
            logger.warning("數據文件不存在")
        except Exception as e:
            logger.error(f"加載數據失敗: {str(e)}")
    
    def get_schedule_status(self) -> dict:
        """
        獲取排程狀態
        """
        jobs = []
        schedule_time = None

        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                }
                jobs.append(job_info)

                # 如果是每日優化任務，提取執行時間
                if job.id == 'daily_optimization' and isinstance(job.trigger, CronTrigger):
                    # 嘗試從 CronTrigger 獲取小時和分鐘
                    # CronTrigger 的 fields 是一個 list，包含 [year, month, day, week, day_of_week, hour, minute, second]
                    # 但直接訪問屬性更安全
                    try:
                        # apscheduler 3.x CronTrigger fields
                        fields = job.trigger.fields
                        # hour is index 5, minute is index 6
                        hour_field = fields[5]
                        minute_field = fields[6]
                        
                        # 這些字段通常是 BaseField 對象，str() 會返回表達式
                        # 如果是固定時間，它們的表達式就是數字
                        hour = str(hour_field)
                        minute = str(minute_field)
                        
                        # 確保格式為 HH:MM
                        schedule_time = f"{int(hour):02d}:{int(minute):02d}"
                    except Exception as e:
                        logger.warning(f"無法解析排程時間: {e}")

        return {
            'is_running': self.is_running,
            'schedule_time': schedule_time,  # 返回當前設定的時間
            'jobs': jobs,
            'progress': getattr(self, 'current_progress', 0),
            'optimization_history': self.engine.get_optimization_history(),
            'is_optimizing': getattr(self, 'is_optimizing', False),  # 新增：優化狀態
            'current_generation': getattr(self, 'current_generation', 0),  # 新增：當前代數
            'total_generations': getattr(self, 'total_generations', 0),  # 新增：總代數
            'optimization_message': getattr(self, 'optimization_message', ''),  # 新增：優化訊息
            'last_optimization_at': getattr(self, 'last_optimization_at', None),  # 新增：最後優化時間
            'target_fitness': getattr(self, 'target_fitness', None)  # 🎯 新增：目標適應度
        }
    
    def get_best_config(self, lottery_type: Optional[str] = None) -> dict:
        """
        獲取最佳配置
        優先順序：1. 指定彩種的文件配置 2. 內存配置 3. 通用文件配置
        """
        # 1. 先嘗試加載指定彩種的配置文件
        if lottery_type:
            file_cfg = self.load_config(lottery_type)
            if file_cfg:
                logger.info(f"使用 {lottery_type} 專屬配置")
                return file_cfg
        
        # 2. 嘗試使用內存中的配置
        cfg = self.engine.get_best_config()
        if cfg:
            return cfg
        
        # 3. 回退到通用配置文件
        general_cfg = self.load_config(None)
        if general_cfg:
            logger.info("使用通用配置文件")
            return general_cfg
        
        # 4. 如果還沒有，嘗試加載 BIG_LOTTO 作為默認
        default_cfg = self.load_config('BIG_LOTTO')
        if default_cfg:
            logger.info("使用 BIG_LOTTO 默認配置")
            return default_cfg
            
        return {}
    
    def _save_config(self, config: dict, lottery_type: Optional[str] = None):
        """
        保存配置到文件
        """
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            fname = os.path.join(DATA_DIR, 'best_config.json') if not lottery_type else os.path.join(DATA_DIR, f'best_config_{lottery_type}.json')
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'config': config
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到 {fname}")
        except Exception as e:
            logger.error(f"保存配置失敗: {str(e)}")
    
    def load_config(self, lottery_type: Optional[str] = None) -> dict:
        """
        從文件加載配置
        """
        try:
            fname = os.path.join(DATA_DIR, 'best_config.json') if not lottery_type else os.path.join(DATA_DIR, f'best_config_{lottery_type}.json')
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"配置已加載: {data.get('timestamp', 'Unknown')} ({fname})")
                return data.get('config', {})
        except FileNotFoundError:
            logger.warning("配置文件不存在")
            return {}
        except Exception as e:
            logger.error(f"加載配置失敗: {str(e)}")
            return {}

    def _infer_lottery_type(self, history: list) -> Optional[str]:
        """從歷史數據推斷主要彩種（最多數）"""
        try:
            counter = {}
            for d in history:
                lt = d.get('lotteryType')
                if not lt:
                    continue
                counter[lt] = counter.get(lt, 0) + 1
            if not counter:
                return None
            return max(counter.items(), key=lambda x: x[1])[0]
        except Exception:
            return None

# 全局調度器實例
scheduler = AutoLearningScheduler()
