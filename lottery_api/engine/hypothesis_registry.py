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
from collections import Counter
from typing import Optional, Dict, List, Any, Tuple


REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'hypothesis_registry.jsonl'
)

VALID_STATUSES = {'REGISTERED', 'VALIDATED', 'REJECTED', 'SUPERSEDED', 'PROVISIONAL'}

REFINED_STATUS_WEIGHTS = {
    'VALIDATED': 1.0,
    'STRONG_PROVISIONAL': 0.6,
    'WEAK_PROVISIONAL': 0.2,
    'SOFT_REJECT': -0.3,
    'REJECTED': -1.0,
}


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_window_metrics(entry: Dict) -> Dict[str, Any]:
    """Extract post-validation metrics from result_summary."""
    rs = entry.get('result_summary')
    if not isinstance(rs, dict):
        rs = {}

    edge_150 = _to_float(rs.get('edge_150', rs.get('window_150')))
    edge_300 = _to_float(rs.get('edge_300', rs.get('window_300', rs.get('window_500'))))
    edge_full = _to_float(rs.get('edge_full', rs.get('window_full')))
    perm_p = _to_float(rs.get('perm_p'))

    stability = None
    if edge_150 is not None and edge_300 is not None:
        hi = max(edge_150, edge_300)
        lo = min(edge_150, edge_300)
        if abs(hi) > 1e-12:
            stability = lo / hi

    sign_flip = False
    if edge_150 is not None and edge_300 is not None:
        sign_flip = (edge_150 * edge_300) < 0

    return {
        'edge_150': edge_150,
        'edge_300': edge_300,
        'edge_full': edge_full,
        'perm_p': perm_p,
        'stability': stability,
        'sign_flip': sign_flip,
    }


def _fallback_refined_status(fallback_status: str) -> str:
    if fallback_status == 'VALIDATED':
        return 'VALIDATED'
    if fallback_status == 'REJECTED':
        return 'REJECTED'
    return 'WEAK_PROVISIONAL'


def _is_clearly_negative(edge_300: float, edge_full: Optional[float]) -> bool:
    return edge_300 < 0 or (edge_full is not None and edge_full < -0.005)


def _is_soft_reject_zone(edge_300: float, sign_flip: bool) -> bool:
    return (-0.005 <= edge_300 <= 0.005) or sign_flip


def _classify_positive_edge(perm_p: Optional[float], stability: Optional[float]) -> str:
    perm_ok_005 = perm_p is not None and perm_p < 0.05
    perm_ok_020 = perm_p is not None and perm_p < 0.20
    stable_06 = stability is not None and stability > 0.6
    stable_05 = stability is not None and stability > 0.5

    if perm_ok_005 and stable_06:
        return 'VALIDATED'
    if perm_ok_020 and stable_05:
        return 'STRONG_PROVISIONAL'
    return 'WEAK_PROVISIONAL'


def _classify_refined_status(metrics: Dict[str, Any], fallback_status: str) -> str:
    """Classify refined status using only post-validation metrics."""
    edge_300 = metrics.get('edge_300')
    edge_full = metrics.get('edge_full')
    perm_p = metrics.get('perm_p')
    stability = metrics.get('stability')
    sign_flip = bool(metrics.get('sign_flip'))

    if edge_300 is None:
        return _fallback_refined_status(fallback_status)
    if _is_clearly_negative(edge_300, edge_full):
        return 'REJECTED'
    if _is_soft_reject_zone(edge_300, sign_flip):
        return 'SOFT_REJECT'
    if edge_300 > 0:
        return _classify_positive_edge(perm_p, stability)
    return 'REJECTED'


def _has_changed_fields(old_rs: Dict[str, Any], new_fields: Dict[str, Any]) -> bool:
    for k, v in new_fields.items():
        old_v = old_rs.get(k)
        if isinstance(v, float):
            if old_v is None:
                return True
            try:
                if abs(float(old_v) - v) > 1e-9:
                    return True
            except (TypeError, ValueError):
                return True
        elif old_v != v:
            return True
    return False


def _reclassify_group(group: List[Dict]) -> Tuple[int, int]:
    terminal = {'VALIDATED', 'PROVISIONAL', 'REJECTED'}
    scanned = 0
    updated = 0

    for e in group:
        if e.get('status') not in terminal:
            continue

        scanned += 1
        refined_fields = classify_refined_for_entry(e, peers_same_lottery=group)
        rs = e.get('result_summary')
        if not isinstance(rs, dict):
            rs = {}
        if not _has_changed_fields(rs, refined_fields):
            continue

        new_entry = dict(e)
        new_rs = dict(rs)
        new_rs.update(refined_fields)
        new_entry['result_summary'] = new_rs
        new_entry['_update'] = True
        _append(new_entry)
        updated += 1

    return scanned, updated


def classify_refined_for_entry(entry: Dict, peers_same_lottery: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Compute refined_status + extracted metrics for one entry."""
    metrics = _extract_window_metrics(entry)
    refined_status = _classify_refined_status(metrics, entry.get('status', 'REGISTERED'))

    rank = None
    total_ranked = 0
    percentile = None

    if peers_same_lottery is not None:
        ranked = []
        for p in peers_same_lottery:
            pm = _extract_window_metrics(p)
            p_edge = pm.get('edge_300')
            if p_edge is None:
                continue
            ranked.append((p_edge, p.get('hypothesis_id')))

        ranked.sort(key=lambda x: x[0], reverse=True)
        total_ranked = len(ranked)
        hid = entry.get('hypothesis_id')
        for i, (_, rhid) in enumerate(ranked, start=1):
            if rhid == hid:
                rank = i
                break
        if rank is not None and total_ranked > 0:
            percentile = round((total_ranked - rank + 1) / total_ranked, 5)

    return {
        'refined_status': refined_status,
        'edge_150': metrics.get('edge_150'),
        'edge_300': metrics.get('edge_300'),
        'edge_full': metrics.get('edge_full'),
        'perm_p': metrics.get('perm_p'),
        'stability': metrics.get('stability'),
        'relative_edge_rank': rank,
        'relative_edge_rank_total': total_ranked,
        'relative_edge_percentile': percentile,
        'sign_flip': metrics.get('sign_flip'),
    }


def summarize_refined_distribution(entries: Optional[List[Dict]] = None) -> Dict[str, Dict[str, Any]]:
    """Count refined_status by lottery type and emit imbalance warnings."""
    if entries is None:
        entries = list_all()

    out: Dict[str, Dict[str, Any]] = {}
    by_lottery: Dict[str, List[Dict]] = {}
    for e in entries:
        by_lottery.setdefault(e.get('lottery', 'UNKNOWN'), []).append(e)

    for lt, group in by_lottery.items():
        counts = Counter()
        for e in group:
            status = e.get('status')
            if status not in ('VALIDATED', 'PROVISIONAL', 'REJECTED'):
                continue
            r = classify_refined_for_entry(e, peers_same_lottery=group).get('refined_status', 'WEAK_PROVISIONAL')
            counts[r] += 1

        warnings = []
        categories_present = len([k for k, v in counts.items() if v > 0])
        if categories_present < 3:
            warnings.append(
                f"refined_status categories={categories_present} (<3 target): distribution contrast is weak"
            )
        if counts.get('REJECTED', 0) == 0 and counts.get('SOFT_REJECT', 0) == 0:
            warnings.append("no negative refined signals (SOFT_REJECT/REJECTED)")

        out[lt] = {
            'counts': dict(counts),
            'categories_present': categories_present,
            'warnings': warnings,
        }

    return out


def compute_research_score(entries: List[Dict]) -> float:
    """Compute weighted research_score using refined_status mapping."""
    weighted = 0.0
    n = 0

    by_lottery: Dict[str, List[Dict]] = {}
    for e in entries:
        by_lottery.setdefault(e.get('lottery', 'UNKNOWN'), []).append(e)

    for group in by_lottery.values():
        for e in group:
            if e.get('status') not in ('VALIDATED', 'PROVISIONAL', 'REJECTED'):
                continue
            refined = classify_refined_for_entry(e, peers_same_lottery=group).get('refined_status')
            if refined not in REFINED_STATUS_WEIGHTS:
                continue
            weighted += REFINED_STATUS_WEIGHTS[refined]
            n += 1

    if n == 0:
        return 0.0
    return weighted / n


def reclassify_existing_refined_status(lottery: Optional[str] = None) -> Dict[str, Any]:
    """
    Reclassify existing hypotheses and persist refined fields in result_summary.
    Does not re-run validation; append-only update records are written only when
    refined fields changed.
    """
    entries = list_all()
    if lottery:
        entries = [e for e in entries if e.get('lottery') == lottery]

    by_lottery: Dict[str, List[Dict]] = {}
    for e in entries:
        by_lottery.setdefault(e.get('lottery', 'UNKNOWN'), []).append(e)

    updated = 0
    scanned = 0

    for group in by_lottery.values():
        group_scanned, group_updated = _reclassify_group(group)
        scanned += group_scanned
        updated += group_updated

    return {
        'status': 'ok',
        'lottery': lottery,
        'scanned': scanned,
        'updated': updated,
        'distribution': summarize_refined_distribution(list_all()),
    }

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
        print("[HypothesisRegistry] WARNING: 已有相似假說記錄:")
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

    # Backward compatible: keep original status, add refined_status to result_summary.
    if isinstance(update_entry['result_summary'], dict):
        peers = [
            e for e in entries
            if e.get('lottery') == found.get('lottery') and e.get('hypothesis_id') != hypothesis_id
        ]
        synthetic = dict(update_entry)
        refined = classify_refined_for_entry(synthetic, peers_same_lottery=peers + [synthetic])
        update_entry['result_summary'].update(refined)

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
