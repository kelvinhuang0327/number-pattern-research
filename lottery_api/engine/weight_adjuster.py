"""
Strategy Weight Auto-Adjuster — 策略權重自動調整機制
=====================================================
Result → Strategy Adjustment 閉環的核心模組。

設計原則：
  1. 讀取已解析的 prediction_results (resolve_pending 產生)
  2. 計算每個策略近 N 期的 Exponential Moving Average (EMA) 命中率
  3. 與 baseline 比較得到 edge
  4. 生成調整倍率寫入 strategy_states_*.json
  5. 平滑更新 (EMA α=0.15)，避免震盪
  6. 安全邊界 [0.5, 1.5]，避免極端

觸發點：
  ingest.py → resolve_pending() → adjust_weights()

不修改：
  - prediction engine（僅調整權重）
  - DB schema（只讀 prediction_results）
  - strategy_states 結構（只更新現有欄位 + 新增 feedback_* 欄位）

2026-04-15 Created — Closing the feedback loop
"""
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ──
_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, '..', 'data')
_DB_PATH = os.path.join(_HERE, '..', 'data', 'lottery_v2.db')

# 與 rolling_strategy_monitor.py 一致的基線
BASELINES = {
    'DAILY_539': {1: 0.114, 2: 0.216, 3: 0.305, 4: 0.385, 5: 0.455},
    'BIG_LOTTO': {1: 0.076, 2: 0.143, 3: 0.206, 4: 0.262, 5: 0.315},
    'POWER_LOTTO': {1: 0.076, 2: 0.143, 3: 0.206, 4: 0.262, 5: 0.315},
}

# 安全邊界
MIN_MULTIPLIER = 0.5   # 最差也只降到原權重的 50%
MAX_MULTIPLIER = 1.5   # 最好也只升到原權重的 150%
EMA_ALPHA = 0.15       # 平滑係數：越小越穩（0.1~0.3 合理）
LOOKBACK_PERIODS = 30  # 回顧期數
MIN_SAMPLES = 5        # 最少需要 5 筆才開始調整


@dataclass
class FeedbackRecord:
    """每次調整的完整記錄（可追溯、可回滾）"""
    timestamp: str
    lottery_type: str
    strategy_name: str
    recent_rate: float       # 近 N 期命中率
    baseline: float          # 隨機基準
    edge: float              # rate - baseline
    raw_multiplier: float    # 未平滑前的倍率
    smoothed_multiplier: float  # EMA 平滑後的倍率
    applied: bool            # 是否已寫入 strategy_states
    samples: int             # 樣本數


def _get_db_path() -> str:
    """嘗試多個 DB 路徑"""
    candidates = [
        _DB_PATH,
        os.path.join(_HERE, '..', '..', 'data', 'lottery_v2.db'),
    ]
    for p in candidates:
        ap = os.path.abspath(p)
        if os.path.exists(ap):
            return ap
    return os.path.abspath(_DB_PATH)


def _query_recent_performance(
    lottery_type: str,
    lookback: int = LOOKBACK_PERIODS,
) -> Dict[str, List[dict]]:
    """
    從 prediction_results 查詢各策略近 N 期的命中數據。

    返回:
        {strategy_name: [{"hit_count": int, "num_bets": int, "draw": str}, ...]}
    """
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        logger.warning(f"DB not found: {db_path}")
        return {}

    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        # 只取 VALID 快照（排除 RECONSTRUCTED），確保真實預測
        sql = """
            SELECT
                pi.strategy_name,
                pi.num_bets,
                pr.hit_count,
                pr.actual_draw,
                pr.resolved_at,
                prn.snapshot_source
            FROM prediction_results pr
            JOIN prediction_items  pi  ON pr.item_id = pi.id
            JOIN prediction_runs   prn ON pi.run_id  = prn.id
            WHERE prn.lottery_type = ?
              AND pi.status = 'RESOLVED'
              AND prn.snapshot_source = 'VALID'
              AND pi.strategy_name IS NOT NULL
              AND pi.strategy_name != ''
            ORDER BY pr.resolved_at DESC
        """
        rows = conn.execute(sql, (lottery_type,)).fetchall()
    finally:
        conn.close()

    # 分組
    by_strategy: Dict[str, List[dict]] = {}
    for row in rows:
        name = row['strategy_name']
        if name not in by_strategy:
            by_strategy[name] = []
        if len(by_strategy[name]) < lookback:
            by_strategy[name].append({
                'hit_count': row['hit_count'] or 0,
                'num_bets': row['num_bets'] or 1,
                'draw': row['actual_draw'] or '',
            })

    return by_strategy


def _compute_hit_rate(records: List[dict], metric_threshold: int = 2) -> float:
    """
    計算命中率：命中 >= metric_threshold 個號碼算成功。

    DAILY_539: M2+ (hit >= 2)
    BIG_LOTTO / POWER_LOTTO: M3+ (hit >= 3)
    """
    if not records:
        return 0.0
    hits = sum(1 for r in records if r['hit_count'] >= metric_threshold)
    return hits / len(records)


def _metric_threshold_for(lottery_type: str) -> int:
    """每個彩種的成功門檻"""
    return 2 if lottery_type == 'DAILY_539' else 3


def compute_multiplier(
    rate: float,
    baseline: float,
    prev_multiplier: float = 1.0,
    alpha: float = EMA_ALPHA,
) -> float:
    """
    根據命中率與基線計算調整倍率。

    公式：
        edge = rate - baseline
        raw_mult = 1.0 + tanh(edge / baseline)    # tanh 壓縮到 (-1, +1)
        smoothed = (1 - α) × prev + α × raw_mult  # EMA 平滑

    tanh 的好處：
        - edge = 0 → mult = 1.0（不調整）
        - edge >> 0 → mult → 2.0（上限）
        - edge << 0 → mult → 0.0（下限）
        - 自然平滑，避免線性公式的跳躍

    最終 clamp 到 [MIN_MULTIPLIER, MAX_MULTIPLIER]。
    """
    import math

    if baseline <= 0:
        return 1.0

    edge = rate - baseline
    # 正規化 edge：以 baseline 為尺度
    normalized_edge = edge / baseline
    # tanh 壓縮（×0.8 讓曲線不那麼陡峭）
    raw_mult = 1.0 + math.tanh(normalized_edge * 0.8)

    # EMA 平滑
    smoothed = (1.0 - alpha) * prev_multiplier + alpha * raw_mult

    # 安全邊界
    return max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, smoothed))


def adjust_weights(lottery_type: str, dry_run: bool = False) -> Dict:
    """
    核心入口：讀取追蹤結果 → 計算調整 → 更新 strategy_states。

    Args:
        lottery_type: 彩種
        dry_run: True = 只計算不寫入

    Returns:
        {"adjusted": int, "skipped": int, "details": [...], "dry_run": bool}
    """
    result = {
        "lottery_type": lottery_type,
        "adjusted": 0,
        "skipped": 0,
        "details": [],
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
    }

    # 1. 查詢追蹤結果
    perf_data = _query_recent_performance(lottery_type, LOOKBACK_PERIODS)
    if not perf_data:
        logger.info(f"[WeightAdjuster] {lottery_type}: 無追蹤數據，跳過")
        result["skipped_reason"] = "no_tracking_data"
        return result

    # 2. 載入現有 strategy_states
    states_path = os.path.join(
        os.path.abspath(_DATA_DIR),
        f'strategy_states_{lottery_type}.json',
    )
    states = {}
    if os.path.exists(states_path):
        with open(states_path, 'r', encoding='utf-8') as f:
            states = json.load(f)

    # 3. 載入上次的 feedback 倍率（用於 EMA 平滑）
    feedback_path = os.path.join(
        os.path.abspath(_DATA_DIR),
        f'weight_feedback_{lottery_type}.json',
    )
    prev_feedback = {}
    if os.path.exists(feedback_path):
        with open(feedback_path, 'r', encoding='utf-8') as f:
            prev_feedback = json.load(f)

    metric_threshold = _metric_threshold_for(lottery_type)
    baselines = BASELINES.get(lottery_type, BASELINES['POWER_LOTTO'])
    new_feedback = {}

    # 4. 計算每個策略的調整倍率
    for strategy_name, records in perf_data.items():
        if len(records) < MIN_SAMPLES:
            result["skipped"] += 1
            result["details"].append({
                "strategy": strategy_name,
                "action": "skipped",
                "reason": f"insufficient_samples ({len(records)}/{MIN_SAMPLES})",
            })
            continue

        # 推斷 num_bets
        num_bets = records[0].get('num_bets', 1)
        baseline = baselines.get(num_bets, baselines.get(1, 0.076))

        # 命中率
        rate = _compute_hit_rate(records, metric_threshold)
        edge = rate - baseline

        # 前次倍率（用於 EMA）
        prev_mult = prev_feedback.get(strategy_name, {}).get('multiplier', 1.0)

        # 計算新倍率
        new_mult = compute_multiplier(rate, baseline, prev_mult, EMA_ALPHA)

        record = FeedbackRecord(
            timestamp=datetime.now().isoformat(),
            lottery_type=lottery_type,
            strategy_name=strategy_name,
            recent_rate=round(rate, 5),
            baseline=baseline,
            edge=round(edge, 5),
            raw_multiplier=round(1.0 + __import__('math').tanh((edge / baseline) * 0.8) if baseline > 0 else 1.0, 4),
            smoothed_multiplier=round(new_mult, 4),
            applied=not dry_run,
            samples=len(records),
        )

        new_feedback[strategy_name] = {
            'multiplier': round(new_mult, 4),
            'rate': round(rate, 5),
            'edge': round(edge, 5),
            'samples': len(records),
            'updated_at': datetime.now().isoformat(),
        }

        # 5. 更新 strategy_states（如果存在該策略）
        if strategy_name in states:
            if not dry_run:
                st = states[strategy_name]
                # 寫入 feedback 標記（新增欄位，不破壞既有結構）
                st['feedback_multiplier'] = round(new_mult, 4)
                st['feedback_rate'] = round(rate, 5)
                st['feedback_edge'] = round(edge, 5)
                st['feedback_samples'] = len(records)
                st['feedback_updated'] = datetime.now().isoformat()

                # 調整 edge_30p（核心：影響 _weight_from_strategy_state）
                # 用 feedback multiplier 修正 edge_30p
                original_edge = float(st.get('edge_30p', 0.0))
                st['edge_30p_original'] = original_edge  # 保存原始值（可回滾）
                st['edge_30p'] = round(original_edge * new_mult, 5)

            result["adjusted"] += 1
        else:
            result["skipped"] += 1

        result["details"].append(asdict(record))

    # 6. 寫入
    if not dry_run:
        # 寫入 strategy_states
        if states:
            with open(states_path, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=2, ensure_ascii=False)

        # 寫入 feedback 歷史（用於下次 EMA）
        with open(feedback_path, 'w', encoding='utf-8') as f:
            json.dump(new_feedback, f, indent=2, ensure_ascii=False)

        # 追加到審計日誌（append-only，可追溯）
        _append_audit_log(lottery_type, result)

    logger.info(
        f"[WeightAdjuster] {lottery_type}: "
        f"adjusted={result['adjusted']}, skipped={result['skipped']}, dry_run={dry_run}"
    )
    return result


def _append_audit_log(lottery_type: str, result: Dict):
    """追加審計日誌（append-only JSONL，完整可追溯）"""
    log_path = os.path.join(
        os.path.abspath(_DATA_DIR),
        f'weight_adjustment_log_{lottery_type}.jsonl',
    )
    try:
        entry = {
            'timestamp': result.get('timestamp', datetime.now().isoformat()),
            'adjusted': result.get('adjusted', 0),
            'skipped': result.get('skipped', 0),
            'details': result.get('details', []),
        }
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")


def rollback_weights(lottery_type: str) -> Dict:
    """
    回滾：將 edge_30p 恢復為 edge_30p_original，移除 feedback_* 欄位。

    只要 edge_30p_original 存在就可以回滾。
    """
    states_path = os.path.join(
        os.path.abspath(_DATA_DIR),
        f'strategy_states_{lottery_type}.json',
    )
    if not os.path.exists(states_path):
        return {"error": "states file not found"}

    with open(states_path, 'r', encoding='utf-8') as f:
        states = json.load(f)

    rolled_back = 0
    for name, st in states.items():
        if 'edge_30p_original' in st:
            st['edge_30p'] = st.pop('edge_30p_original')
            for key in list(st.keys()):
                if key.startswith('feedback_'):
                    del st[key]
            rolled_back += 1

    with open(states_path, 'w', encoding='utf-8') as f:
        json.dump(states, f, indent=2, ensure_ascii=False)

    logger.info(f"[WeightAdjuster] Rollback {lottery_type}: {rolled_back} strategies restored")
    return {"rolled_back": rolled_back, "lottery_type": lottery_type}


def adjust_all_types(dry_run: bool = False) -> Dict:
    """調整所有彩種的策略權重"""
    results = {}
    for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
        try:
            results[lt] = adjust_weights(lt, dry_run=dry_run)
        except Exception as e:
            logger.error(f"[WeightAdjuster] {lt} failed: {e}")
            results[lt] = {"error": str(e)}
    return results
