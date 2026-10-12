from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class StrategyAdapter:
    """
    策略適配器
    根據彩券類型和數據特徵動態調整策略配置和權重
    """
    
    def adjust_available_models(self, models: List[Dict], lottery_type: Optional[str] = None, data_size: int = 0) -> List[Dict]:
        """
        根據上下文過濾可用模型列表
        """
        if not lottery_type and not data_size:
            return models
            
        adjusted = []
        for model in models:
            model_id = model.get('id')
            
            # Rule 1: Deep Learning requires sufficient data
            if model.get('category') == 'ai':
                if data_size > 0 and data_size < 50:
                    model['status'] = 'unavailable'
                    model['note'] = '數據不足 (需 >50 期)'
                else:
                    model['status'] = 'available'
            
            # Rule 2: Specific lottery type preferences
            if lottery_type == "DAILY_539":
                # Example: Daily 539 might not work well with some complex models
                pass
                
            adjusted.append(model)
            
        return adjusted

    def adapt_weights(self, base_weights: Dict[str, float], lottery_type: str, history: List[Dict]) -> Dict[str, float]:
        """
        根據彩種特性調整策略權重
        """
        adjusted = base_weights.copy()
        
        # 1. 大樂透 (6/49) - 偏向統計和頻率
        if lottery_type == "BIG_LOTTO":
            if 'frequency_weight' in adjusted:
                adjusted['frequency_weight'] *= 1.2
            if 'missing_weight' in adjusted:
                adjusted['missing_weight'] *= 1.1

        # 2. 威力彩 (6/38) - 偏向分區和冷熱
        elif lottery_type == "POWER_LOTTO":
            if 'zone_weight' in adjusted:
                adjusted['zone_weight'] *= 1.3
            if 'hot_cold_weight' in adjusted:
                adjusted['hot_cold_weight'] *= 1.2
                
        # 3. 今彩539 (5/39) - 偏向短期趨勢
        elif lottery_type == "DAILY_539":
            if 'trend_weight' in adjusted:
                adjusted['trend_weight'] *= 1.5
            if 'recent_window' in adjusted:
                # 縮短回測窗口
                adjusted['recent_window'] = max(10, min(30, adjusted.get('recent_window', 50)))

        # 4. 數據量不足時的調整
        if history and len(history) < 30:
            # 依賴純頻率與近期熱號
            if 'frequency_weight' in adjusted: adjusted['frequency_weight'] += 0.2
            if 'hot_cold_weight' in adjusted: adjusted['hot_cold_weight'] += 0.2
            # 降低複雜特徵權重
            if 'entropy_weight' in adjusted: adjusted['entropy_weight'] *= 0.5
            
        # Normalize
        total = sum(v for k, v in adjusted.items() if k.endswith('_weight'))
        if total > 0:
            for k in adjusted:
                if k.endswith('_weight'):
                    adjusted[k] /= total
                    
        return adjusted

# Singleton
strategy_adapter = StrategyAdapter()
