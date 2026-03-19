"""
模型緩存管理器
用於緩存已訓練的模型，避免重複訓練，大幅提升預測速度
"""
import hashlib
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ModelCache:
    """
    模型緩存管理器
    - 緩存已訓練的模型
    - 追蹤數據版本（通過哈希）
    - 自動失效過期緩存
    """
    
    def __init__(self, cache_ttl_hours: int = 24):
        """
        Args:
            cache_ttl_hours: 緩存有效期（小時），默認 24 小時
        """
        self.cache = {}  # {cache_key: {'model': model, 'timestamp': datetime, 'data_hash': str}}
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        logger.info(f"ModelCache 初始化完成，TTL={cache_ttl_hours}小時")
    
    def _compute_data_hash(self, history: list, lottery_rules: dict, extra_signature: Optional[str] = None) -> str:
        """計算數據哈希值 (輕量版)

        將原本使用最近 100 期完整序列改為僅使用：
        - 數據總期數
        - 最後一期 draw id 與日期
        - 規則 pickCount / maxNumber / minNumber
        - 額外簽名 (例如最佳配置哈希 / 版本號)

        目的：
        - 降低 JSON 序列化與排序成本 (先前 O(N))
        - 避免每次命中時仍需大量構造 recent 結構
        - 快速檢測同步或配置是否變更
        """
        last_draw = history[-1].get('draw') if history else None
        last_date = history[-1].get('date') if history else None
        data_repr = {
            'count': len(history),
            'last_draw': last_draw,
            'last_date': last_date,
            'pickCount': lottery_rules.get('pickCount'),
            'minNumber': lottery_rules.get('minNumber'),
            'maxNumber': lottery_rules.get('maxNumber'),
            'extra': extra_signature or ''
        }
        data_str = json.dumps(data_repr, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def _make_cache_key(self, lottery_type: str, model_type: str) -> str:
        """
        生成緩存鍵
        """
        return f"{lottery_type}_{model_type}"
    
    def get(
        self,
        lottery_type: str,
        model_type: str,
        history: list,
        lottery_rules: dict,
        extra_signature: Optional[str] = None
    ) -> Optional[Any]:
        """
        獲取緩存的模型
        
        Returns:
            如果緩存有效且數據未變化，返回緩存的模型；否則返回 None
        """
        cache_key = self._make_cache_key(lottery_type, model_type)
        
        if cache_key not in self.cache:
            logger.debug(f"緩存未命中: {cache_key}")
            return None
        
        cached = self.cache[cache_key]
        
        # 檢查是否過期
        if datetime.now() - cached['timestamp'] > self.cache_ttl:
            logger.info(f"緩存已過期: {cache_key}")
            del self.cache[cache_key]
            return None
        
        # 檢查數據是否變化
        current_hash = self._compute_data_hash(history, lottery_rules, extra_signature=extra_signature)
        if current_hash != cached['data_hash']:
            logger.info(f"數據已變化: {cache_key}")
            del self.cache[cache_key]
            return None
        
        logger.info(f"✅ 緩存命中: {cache_key}")
        return cached['model']
    
    def set(
        self,
        lottery_type: str,
        model_type: str,
        model: Any,
        history: list,
        lottery_rules: dict,
        extra_signature: Optional[str] = None
    ):
        """
        保存模型到緩存
        """
        cache_key = self._make_cache_key(lottery_type, model_type)
        data_hash = self._compute_data_hash(history, lottery_rules, extra_signature=extra_signature)
        
        self.cache[cache_key] = {
            'model': model,
            'timestamp': datetime.now(),
            'data_hash': data_hash,
            'signature': extra_signature or ''
        }
        
        logger.info(f"💾 模型已緩存: {cache_key}")
    
    def clear(self, lottery_type: Optional[str] = None, model_type: Optional[str] = None):
        """
        清除緩存
        
        Args:
            lottery_type: 如果指定，只清除該彩券類型的緩存
            model_type: 如果指定，只清除該模型類型的緩存
        """
        if lottery_type is None and model_type is None:
            # 清除所有緩存
            self.cache.clear()
            logger.info("🗑️ 已清除所有緩存")
        else:
            # 清除特定緩存
            keys_to_delete = []
            for key in self.cache.keys():
                parts = key.split('_')
                if len(parts) >= 2:
                    cached_lottery_type = parts[0]
                    cached_model_type = parts[1]
                    
                    if (lottery_type is None or cached_lottery_type == lottery_type) and \
                       (model_type is None or cached_model_type == model_type):
                        keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
                logger.info(f"🗑️ 已清除緩存: {key}")
    
    def get_stats(self) -> Dict:
        """
        獲取緩存統計信息
        """
        return {
            'total_cached': len(self.cache),
            'cached_models': list(self.cache.keys()),
            'cache_ttl_hours': self.cache_ttl.total_seconds() / 3600
        }

# 全局緩存實例
model_cache = ModelCache(cache_ttl_hours=24)
