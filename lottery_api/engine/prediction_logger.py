"""
Prediction Logger — JSONL 結構化預測日誌
==========================================
借鑑 MiroFish SimulationRunner 的雙軌日誌設計:
  - JSONL: 每期一行，結構化，便於程式查詢
  - 開獎後自動 update_result() 填補結果欄位

設計原則:
  - 預測時只寫入預測資訊，result 欄位為 null
  - 開獎後透過 period 比對，填補 actual/match/m3+
  - 支援重複呼叫（同期同策略不重複寫入）

2026-03-12 Created (Phase 1-A, MiroFish Phase 1)
"""
import os
import json
import time
from datetime import datetime
from typing import List, Optional, Dict, Any


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PREDICTIONS_FILE = {
    'BIG_LOTTO':   'predictions_BIG_LOTTO.jsonl',
    'POWER_LOTTO': 'predictions_POWER_LOTTO.jsonl',
    'DAILY_539':   'predictions_DAILY_539.jsonl',
}


class PredictionLogger:
    """
    JSONL 預測日誌 — 每期預測自動記錄，開獎後自動比對

    Usage:
        logger = PredictionLogger()

        # 預測時呼叫 (quick_predict.py 結尾)
        logger.log_prediction(
            lottery_type='POWER_LOTTO',
            period='115000021',
            strategy='Fourier Rhythm',
            num_bets=2,
            bets=[[3,19,24,26,27,37], [4,6,23,31,35,38]],
            specials=[4, 4],
        )

        # 開獎後呼叫
        logger.update_result(
            lottery_type='POWER_LOTTO',
            period='115000021',
            actual_numbers=[1,11,14,17,29,32],
            actual_special=8,
        )

        # 查詢近期命中
        hits = logger.recent_hits('POWER_LOTTO', n=30)
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)

    def _filepath(self, lottery_type: str) -> str:
        fname = PREDICTIONS_FILE.get(lottery_type, f'predictions_{lottery_type}.jsonl')
        return os.path.join(self.data_dir, fname)

    def _load_all(self, lottery_type: str) -> List[Dict]:
        path = self._filepath(lottery_type)
        if not os.path.exists(path):
            return []
        records = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _save_all(self, lottery_type: str, records: List[Dict]):
        path = self._filepath(lottery_type)
        with open(path, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    def log_prediction(
        self,
        lottery_type: str,
        period: str,
        strategy: str,
        num_bets: int,
        bets: List[List[int]],
        specials: Optional[List[int]] = None,
    ) -> bool:
        """
        記錄預測（若同期同策略已存在則跳過）

        Returns: True=新增, False=已存在跳過
        """
        records = self._load_all(lottery_type)

        # 防重複
        for rec in records:
            if rec.get('period') == str(period) and rec.get('strategy') == strategy:
                return False

        entry = {
            'ts': int(time.time()),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'lottery_type': lottery_type,
            'period': str(period),
            'strategy': strategy,
            'num_bets': num_bets,
            'bets': [sorted(b) for b in bets],
            'specials': specials,
            # 開獎後填補
            'actual_numbers': None,
            'actual_special': None,
            'match_counts': None,
            'best_match': None,
            'is_m3plus': None,
            'is_m2plus': None,
        }

        path = self._filepath(lottery_type)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return True

    def update_result(
        self,
        lottery_type: str,
        period: str,
        actual_numbers: List[int],
        actual_special: Optional[int] = None,
    ) -> int:
        """
        開獎後更新結果，自動計算 match/M3+/M2+

        Returns: 更新筆數
        """
        records = self._load_all(lottery_type)
        actual_set = set(actual_numbers)
        updated = 0

        for rec in records:
            if rec.get('period') != str(period):
                continue
            if rec.get('actual_numbers') is not None:
                continue  # 已更新過，跳過

            bets = rec.get('bets', [])
            match_counts = [len(set(b) & actual_set) for b in bets]
            best_match = max(match_counts) if match_counts else 0

            rec['actual_numbers'] = sorted(actual_numbers)
            rec['actual_special'] = actual_special
            rec['match_counts'] = match_counts
            rec['best_match'] = best_match
            rec['is_m3plus'] = best_match >= 3
            rec['is_m2plus'] = best_match >= 2
            updated += 1

        if updated > 0:
            self._save_all(lottery_type, records)
        return updated

    def recent_hits(
        self,
        lottery_type: str,
        n: int = 30,
        metric: str = 'is_m3plus',
    ) -> Dict[str, Any]:
        """
        查詢近 n 期命中統計

        Returns:
            {
              'n': 30, 'hit_count': 5, 'rate': 0.167,
              'pending': 3,   # 尚未開獎
              'records': [...]
            }
        """
        records = self._load_all(lottery_type)
        # 按期號排序（時間由舊到新）
        records_sorted = sorted(records, key=lambda r: r.get('period', ''))
        recent = records_sorted[-n:] if len(records_sorted) >= n else records_sorted

        pending = sum(1 for r in recent if r.get('actual_numbers') is None)
        settled = [r for r in recent if r.get('actual_numbers') is not None]
        hit_count = sum(1 for r in settled if r.get(metric))
        rate = hit_count / len(settled) if settled else 0.0

        return {
            'n': len(recent),
            'settled': len(settled),
            'pending': pending,
            'hit_count': hit_count,
            'rate': round(rate, 5),
            'metric': metric,
            'records': recent,
        }

    def get_pending(self, lottery_type: str) -> List[Dict]:
        """取得尚未開獎（result=null）的預測清單"""
        records = self._load_all(lottery_type)
        return [r for r in records if r.get('actual_numbers') is None]

    def summary(self, lottery_type: str) -> Dict:
        """印出摘要統計"""
        records = self._load_all(lottery_type)
        settled = [r for r in records if r.get('actual_numbers') is not None]
        pending = [r for r in records if r.get('actual_numbers') is None]

        m3_rate = sum(1 for r in settled if r.get('is_m3plus')) / len(settled) if settled else 0
        m2_rate = sum(1 for r in settled if r.get('is_m2plus')) / len(settled) if settled else 0

        strategies = {}
        for r in settled:
            s = r.get('strategy', 'unknown')
            if s not in strategies:
                strategies[s] = {'total': 0, 'm3plus': 0, 'm2plus': 0}
            strategies[s]['total'] += 1
            if r.get('is_m3plus'):
                strategies[s]['m3plus'] += 1
            if r.get('is_m2plus'):
                strategies[s]['m2plus'] += 1

        return {
            'lottery_type': lottery_type,
            'total_predictions': len(records),
            'settled': len(settled),
            'pending': len(pending),
            'm3plus_rate': round(m3_rate, 5),
            'm2plus_rate': round(m2_rate, 5),
            'by_strategy': strategies,
        }


# ============================================================
# Singleton accessor
# ============================================================
_logger_instance: Optional[PredictionLogger] = None


def get_logger() -> PredictionLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PredictionLogger()
    return _logger_instance
