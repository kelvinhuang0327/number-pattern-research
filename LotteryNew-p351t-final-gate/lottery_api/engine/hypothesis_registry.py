"""
Hypothesis Registry
===================
假說登記簿 — 防止事後挑選偏誤

核心功能:
  1. 每個新策略在開始回測前先登錄
  2. append-only JSONL 格式，不可修改歷史紀錄
  3. 重複假說偵測（避免再次探索已失敗的同型假說）
  4. 狀態追蹤: REGISTERED → VALIDATED / REJECTED / SUPERSEDED

設計原則:
  - 先登錄假說 → 再回測 → 才決定採納/拒絕
  - 不允許在回測後才登錄假說（防止 post-selection bias）
  - 失敗記憶庫: 新假說提交前自動比對失敗記憶

2026-03-05 Created
"""
import os
import json
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any


REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'hypothesis_registry.jsonl'
)

VALID_STATUSES = {'REGISTERED', 'VALIDATED', 'REJECTED', 'SUPERSEDED', 'PROVISIONAL'}

# 已知失敗模式關鍵字，提交時自動警告
_KNOWN_FAILURE_PATTERNS = [
    ('gap_pressure', 'SGP V3-V11 全拒絕，Gap Pressure 被頻率窗口吸收'),
    ('gap_dynamic', 'Gap Dynamic Threshold 16組全無改善'),
    ('hot_stop_rebound', '熱號休停回歸 p=0.4924 無信號'),
    ('shlc', 'SHLC 中頻矛盾指標 p=0.595 無預測力'),
    ('core_satellite', 'Core-Satellite 覆蓋損失 > 收益，Edge 持續負'),
    ('apriori', 'Apriori 全期 Edge 嚴重負向'),
    ('markov_single', 'Markov 單注 1500p Edge 為負'),
    ('attention_lstm', 'Attention LSTM Baseline 錯誤已廢棄'),
    ('cold_pool_15', 'pool=15 三窗口全劣化，維持 pool=12'),
    ('neighbor_inject', '鄰號共現 Lift<1.0 負相關，注入損害品質'),
    ('p1_deviation_539', 'P1+偏差互補是大樂透特有信號，539 Edge≈0'),
    ('short_term_hot', '5期熱號獨立注 Edge=0% p=0.522'),
    ('zone_constraint', 'Zone Constraint 在冷號框架反效果'),
    ('mab_fusion', 'MAB 稀疏無法收斂，多次失敗'),
]


def _compute_data_hash(lottery_type: str, n_periods: int) -> str:
    """計算資料庫目前最新期數的 hash，作為資料快照識別"""
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'lottery_v2.db'
    )
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            'SELECT draw FROM draws WHERE lottery_type=? ORDER BY date DESC LIMIT ?',
            (lottery_type, n_periods)
        )
        rows = c.fetchall()
        conn.close()
        h = hashlib.md5(str(rows).encode()).hexdigest()[:12]
        return h
    except Exception:
        return 'unknown'


def register(
    name: str,
    lottery: str,
    theory_basis: str,
    expected_direction: str,
    test_thresholds: Dict[str, Any],
    seed: int = 42,
    n_periods: int = 1500,
    notes: str = ''
) -> Dict:
    """
    登錄新假說。回測開始前必須先呼叫此函數。

    Parameters
    ----------
    name             : 策略名稱（唯一識別，建議 snake_case）
    lottery          : BIG_LOTTO | POWER_LOTTO | DAILY_539
    theory_basis     : 信號理論來源（例：「冷號均值回歸」）
    expected_direction: 預期效果（例：「M3+ Edge > +1.0%」）
    test_thresholds  : 驗證門檻 dict，例：
                       {"perm_p": 0.05, "three_window": True, "min_edge": 1.0}
    seed             : random seed（固定可重現）
    n_periods        : 回測期數（用於資料 hash）
    notes            : 補充說明

    Returns
    -------
    hypothesis dict（已寫入 JSONL）
    """
    # 重複假說警告
    duplicates = _check_duplicate(name, lottery)
    if duplicates:
        print(f"[HypothesisRegistry] WARNING: 已有相似假說記錄:")
        for d in duplicates[:3]:
            print(f"  - {d['name']} ({d['status']}) @ {d['registered_at'][:10]}")

    # 失敗模式關鍵字掃描
    name_lower = name.lower() + ' ' + theory_basis.lower()
    for kw, reason in _KNOWN_FAILURE_PATTERNS:
        if kw in name_lower:
            print(f"[HypothesisRegistry] ⚠️  KNOWN_FAILURE: '{kw}' → {reason}")

    hypothesis_id = f"{lottery[:2]}_{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data_hash = _compute_data_hash(lottery, n_periods)

    entry = {
        'hypothesis_id': hypothesis_id,
        'name': name,
        'lottery': lottery,
        'theory_basis': theory_basis,
        'expected_direction': expected_direction,
        'test_thresholds': test_thresholds,
        'seed': seed,
        'n_periods': n_periods,
        'data_hash': data_hash,
        'notes': notes,
        'status': 'REGISTERED',
        'registered_at': datetime.now().isoformat(),
        'validated_at': None,
        'result_summary': None,
    }

    _append(entry)
    print(f"[HypothesisRegistry] Registered: {hypothesis_id}")
    return entry


def update_status(
    hypothesis_id: str,
    status: str,
    result_summary: Optional[Dict] = None
) -> bool:
    """
    更新假說狀態（REGISTERED → VALIDATED / REJECTED / SUPERSEDED / PROVISIONAL）

    由於 JSONL 是 append-only，更新以新行追加（latest wins）。
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    entries = list_all()
    found = next((e for e in entries if e['hypothesis_id'] == hypothesis_id), None)
    if not found:
        print(f"[HypothesisRegistry] ERROR: hypothesis_id not found: {hypothesis_id}")
        return False

    update_entry = dict(found)
    update_entry['status'] = status
    update_entry['validated_at'] = datetime.now().isoformat()
    update_entry['result_summary'] = result_summary or {}
    update_entry['_update'] = True  # 標記為更新記錄

    _append(update_entry)
    print(f"[HypothesisRegistry] Updated {hypothesis_id}: {found['status']} → {status}")
    return True


def list_all() -> List[Dict]:
    """讀取所有假說（latest state per hypothesis_id）"""
    if not os.path.exists(REGISTRY_PATH):
        return []

    seen = {}
    with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                hid = entry['hypothesis_id']
                seen[hid] = entry  # latest wins
            except json.JSONDecodeError:
                continue

    return list(seen.values())


def list_by_status(status: str) -> List[Dict]:
    return [e for e in list_all() if e['status'] == status]


def get(hypothesis_id: str) -> Optional[Dict]:
    entries = list_all()
    return next((e for e in entries if e['hypothesis_id'] == hypothesis_id), None)


def _check_duplicate(name: str, lottery: str) -> List[Dict]:
    """返回同名或非常相似的已有假說"""
    all_entries = list_all()
    name_lower = name.lower().replace('_', '')
    matches = []
    for e in all_entries:
        e_name = e['name'].lower().replace('_', '')
        if e['lottery'] == lottery and (
            e_name == name_lower or
            name_lower in e_name or
            e_name in name_lower
        ):
            matches.append(e)
    return matches


def _append(entry: Dict):
    """安全 append 到 JSONL"""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def show_summary():
    """顯示假說庫摘要"""
    entries = list_all()
    from collections import Counter
    status_counts = Counter(e['status'] for e in entries)
    lottery_counts = Counter(e['lottery'] for e in entries)
    print(f"\n=== Hypothesis Registry Summary ({len(entries)} total) ===")
    print("By status:", dict(status_counts))
    print("By lottery:", dict(lottery_counts))
    registered = [e for e in entries if e['status'] == 'REGISTERED']
    if registered:
        print(f"\nPending validation ({len(registered)}):")
        for e in registered:
            print(f"  [{e['lottery']}] {e['name']} @ {e['registered_at'][:10]}")


if __name__ == '__main__':
    show_summary()
