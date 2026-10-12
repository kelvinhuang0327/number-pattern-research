"""
遊戲依附關係處理模組
處理樂合彩系列與主遊戲之間的數據關聯
"""
from typing import List, Dict, Optional, Any
from config import lottery_config
import logging

logger = logging.getLogger(__name__)

class GameDependencyManager:
    """
    管理遊戲之間的依附關係
    例如：39樂合彩依附今彩539，49樂合彩依附大樂透
    """

    def get_parent_game(self, lottery_type: str) -> Optional[str]:
        """
        獲取指定彩券的父遊戲ID
        Args:
            lottery_type: 彩券類型ID
        Returns:
            父遊戲ID，如果不是子遊戲則返回None
        """
        rules = lottery_config.get_rules(lottery_type)
        if not rules:
            return None

        if getattr(rules, 'isSubGame', False):
            return getattr(rules, 'dependsOn', None)

        return None

    def get_child_games(self, lottery_type: str) -> List[str]:
        """
        獲取依附於指定彩券的所有子遊戲
        Args:
            lottery_type: 彩券類型ID
        Returns:
            子遊戲ID列表
        """
        child_games = []
        all_types = lottery_config.get_all_types()

        for type_id, rules in all_types.items():
            if getattr(rules, 'isSubGame', False):
                parent = getattr(rules, 'dependsOn', None)
                if parent == lottery_type:
                    child_games.append(type_id)

        return child_games

    def can_derive_from_parent(self, child_type: str, parent_draws: List[Dict]) -> bool:
        """
        檢查是否可以從父遊戲數據衍生子遊戲數據
        Args:
            child_type: 子遊戲類型
            parent_draws: 父遊戲開獎記錄
        Returns:
            是否可以衍生
        """
        if not parent_draws:
            return False

        parent_game = self.get_parent_game(child_type)
        if not parent_game:
            return False

        # 檢查父遊戲數據是否完整
        for draw in parent_draws:
            if draw.get('lotteryType') != parent_game:
                return False
            if 'numbers' not in draw or not draw['numbers']:
                return False

        return True

    def derive_child_draws(
        self,
        parent_draws: List[Dict],
        child_type: str,
        play_mode: str
    ) -> List[Dict]:
        """
        從父遊戲開獎記錄衍生子遊戲開獎記錄

        Args:
            parent_draws: 父遊戲開獎記錄列表
            child_type: 子遊戲類型（例如：'39_LOTTO'）
            play_mode: 玩法模式（例如：'二合', '三合', '四合'）

        Returns:
            衍生的子遊戲開獎記錄列表
        """
        child_rules = lottery_config.get_rules(child_type)
        if not child_rules:
            logger.error(f"找不到子遊戲規則: {child_type}")
            return []

        if not getattr(child_rules, 'isSubGame', False):
            logger.error(f"{child_type} 不是子遊戲")
            return []

        parent_game = getattr(child_rules, 'dependsOn', None)
        if not parent_game:
            logger.error(f"{child_type} 缺少父遊戲配置")
            return []

        # 驗證玩法模式
        play_modes = getattr(child_rules, 'playModes', None)
        if not play_modes or play_mode not in play_modes:
            logger.error(f"{child_type} 不支援玩法: {play_mode}")
            return []

        pick_count = play_modes[play_mode].pickCount

        child_draws = []
        for parent_draw in parent_draws:
            # 驗證父遊戲類型
            if parent_draw.get('lotteryType') != parent_game:
                continue

            parent_numbers = parent_draw.get('numbers', [])
            if not parent_numbers:
                continue

            # 特殊處理：大樂透需要排除特別號
            if parent_game == 'BIG_LOTTO' and child_type == '49_LOTTO':
                # 49樂合彩只使用大樂透的一般號碼，不含特別號
                # 父遊戲的numbers已經是排序後的6個號碼（不含特別號）
                pass

            # 威力彩：38樂合彩只使用第一區號碼
            if parent_game == 'POWER_LOTTO' and child_type == '38_LOTTO':
                # 威力彩的numbers已經是第一區的6個號碼
                pass

            # 今彩539：39樂合彩使用所有5個號碼
            if parent_game == 'DAILY_539' and child_type == '39_LOTTO':
                # 直接使用今彩539的5個號碼
                pass

            # 取前N個號碼（根據玩法模式）
            if len(parent_numbers) < pick_count:
                logger.warning(
                    f"父遊戲號碼數量不足: 需要 {pick_count}，實際 {len(parent_numbers)}"
                )
                continue

            child_numbers = parent_numbers[:pick_count]

            child_draw = {
                'date': parent_draw.get('date'),
                'draw': parent_draw.get('draw'),
                'numbers': child_numbers,
                'special': None,  # 樂合彩沒有特別號
                'lotteryType': child_type,
                'playMode': play_mode,
                'derivedFrom': parent_game,  # 標記來源
                'parentDraw': parent_draw.get('draw')  # 父遊戲期號
            }

            child_draws.append(child_draw)

        logger.info(
            f"從 {parent_game} 衍生 {len(child_draws)} 筆 {child_type}({play_mode}) 數據"
        )

        return child_draws

    def get_dependency_chain(self, lottery_type: str) -> List[str]:
        """
        獲取依附鏈（從子遊戲追溯到最頂層父遊戲）
        Args:
            lottery_type: 彩券類型
        Returns:
            依附鏈列表，從當前遊戲到最頂層父遊戲
        """
        chain = [lottery_type]
        current = lottery_type

        # 防止循環依附
        max_depth = 10
        depth = 0

        while depth < max_depth:
            parent = self.get_parent_game(current)
            if not parent:
                break

            if parent in chain:
                logger.error(f"檢測到循環依附: {' -> '.join(chain)} -> {parent}")
                break

            chain.append(parent)
            current = parent
            depth += 1

        return chain

    def validate_dependency_config(self) -> Dict[str, Any]:
        """
        驗證所有遊戲的依附配置是否正確
        Returns:
            驗證結果字典
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'dependencies': {}
        }

        all_types = lottery_config.get_all_types()

        for type_id, rules in all_types.items():
            if not getattr(rules, 'isSubGame', False):
                continue

            parent = getattr(rules, 'dependsOn', None)

            # 檢查父遊戲是否存在
            if not parent:
                results['valid'] = False
                results['errors'].append(
                    f"{type_id}: 子遊戲缺少 dependsOn 配置"
                )
                continue

            if parent not in all_types:
                results['valid'] = False
                results['errors'].append(
                    f"{type_id}: 父遊戲 {parent} 不存在"
                )
                continue

            # 檢查父遊戲不能也是子遊戲
            parent_rules = all_types[parent]
            if getattr(parent_rules, 'isSubGame', False):
                results['warnings'].append(
                    f"{type_id}: 父遊戲 {parent} 也是子遊戲（多層依附）"
                )

            # 記錄依附關係
            if parent not in results['dependencies']:
                results['dependencies'][parent] = []
            results['dependencies'][parent].append(type_id)

        return results

# Singleton instance
dependency_manager = GameDependencyManager()
