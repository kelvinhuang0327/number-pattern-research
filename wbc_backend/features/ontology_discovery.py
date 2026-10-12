"""
統計本體自動發現 (Statistical Ontology Auto-Discovery) — Phase 5A
==================================================================
從歷史賽事資料自動發現特徵關係與交互作用，替代人工設計特徵。

方法：
  - 互信息 (Mutual Information, MI)：捕捉非線性特徵重要性
  - Pearson / Spearman 相關性：線性與單調關聯
  - 條件互信息：二階特徵交互作用發現

輸出：
  - 特徵重要性排名 (FeatureImportanceEntry list)
  - 建議新交互特徵清單 (InteractionCandidate list)
  - 低重要性特徵剪枝建議 (PruneCandidate list)
  - JSON 持久化 (save_ontology_report / load_ontology_report)

設計原則：
  - 零外部 API 依賴（scipy + sklearn 可選，均有備援）
  - 防 Look-ahead Leakage：所有計算基於歷史截止資料
  - 支援增量式更新（新增賽事資料後重新評估）
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── 設定值 ─────────────────────────────────────────────────────────────────
_MIN_SAMPLES = 20          # 最少有效樣本才執行分析
_PRUNE_THRESHOLD = 0.02    # 綜合分數 < 2% 建議剪枝
_STRONG_INTERACTION = 0.08
_MODERATE_INTERACTION = 0.03


# ══════════════════════════════════════════════════════════════════════════════
# 資料類別
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FeatureImportanceEntry:
    """單一特徵重要性條目"""
    feature_name: str
    mi_score: float         # 互信息分數（正規化，0-1）
    pearson_r: float        # Pearson 相關係數
    spearman_r: float       # Spearman 相關係數
    composite_score: float  # 綜合分數（60% MI + 20% |Pearson| + 20% |Spearman|）
    data_available: bool    # 是否有足夠樣本
    sample_count: int       # 有效樣本數


@dataclass
class InteractionCandidate:
    """建議的特徵交互作用"""
    feature_a: str
    feature_b: str
    interaction_name: str   # e.g. "woba_diff_x_bullpen_stress_diff"
    conditional_mi: float   # 條件互信息分數
    hypothesis: str         # 人類可讀假設
    strength: str           # "strong" | "moderate" | "weak"


@dataclass
class PruneCandidate:
    """建議剪枝的低重要性特徵"""
    feature_name: str
    composite_score: float
    reason: str


@dataclass
class OntologyReport:
    """完整本體發現報告"""
    n_samples: int
    n_features_analyzed: int
    feature_importance: list[FeatureImportanceEntry] = field(default_factory=list)
    interaction_candidates: list[InteractionCandidate] = field(default_factory=list)
    prune_candidates: list[PruneCandidate] = field(default_factory=list)
    top_k_features: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "n_features_analyzed": self.n_features_analyzed,
            "top_k_features": self.top_k_features,
            "feature_importance": [
                {
                    "name": e.feature_name,
                    "mi": round(e.mi_score, 4),
                    "pearson": round(e.pearson_r, 4),
                    "spearman": round(e.spearman_r, 4),
                    "composite": round(e.composite_score, 4),
                    "samples": e.sample_count,
                }
                for e in self.feature_importance
            ],
            "interaction_candidates": [
                {
                    "feature_a": ic.feature_a,
                    "feature_b": ic.feature_b,
                    "name": ic.interaction_name,
                    "cmi": round(ic.conditional_mi, 4),
                    "hypothesis": ic.hypothesis,
                    "strength": ic.strength,
                }
                for ic in self.interaction_candidates
            ],
            "prune_candidates": [
                {
                    "feature": p.feature_name,
                    "score": round(p.composite_score, 4),
                    "reason": p.reason,
                }
                for p in self.prune_candidates
            ],
            "timestamp": self.timestamp,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 統計計算（有備援，無硬性 sklearn 依賴）
# ══════════════════════════════════════════════════════════════════════════════

def _histogram_mi(x: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """備援：直方圖法估算互信息（不依賴 sklearn）"""
    try:
        edges = np.histogram_bin_edges(x, bins=n_bins)
        x_binned = np.digitize(x, edges[1:-1])
        n_x_bins = n_bins + 1
        n_y_vals = 2  # 二元結果 (0/1)

        c_xy = np.zeros((n_x_bins, n_y_vals), dtype=float)
        for xi, yi in zip(x_binned, y.astype(int)):
            c_xy[xi, int(bool(yi))] += 1
        c_xy /= max(len(x), 1)

        px = c_xy.sum(axis=1) + 1e-10
        py = c_xy.sum(axis=0) + 1e-10
        mi = 0.0
        for i in range(n_x_bins):
            for j in range(n_y_vals):
                if c_xy[i, j] > 1e-10:
                    mi += c_xy[i, j] * math.log(c_xy[i, j] / (px[i] * py[j]))
        return float(max(0.0, min(1.0, mi)))
    except Exception:
        return 0.0


def _safe_mi(x: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """互信息（優先 sklearn，備援直方圖法）"""
    try:
        from sklearn.feature_selection import mutual_info_classif  # type: ignore
        mi = mutual_info_classif(x.reshape(-1, 1), y.astype(int), random_state=42)[0]
        n_classes = len(np.unique(y))
        max_mi = math.log2(max(n_classes, 2))
        return float(min(1.0, mi / max_mi)) if max_mi > 0 else 0.0
    except Exception:
        return _histogram_mi(x, y, n_bins)


def _safe_pearson(x: np.ndarray, y: np.ndarray) -> float:
    """安全 Pearson 相關係數"""
    try:
        if x.std() < 1e-8 or y.std() < 1e-8:
            return 0.0
        r = float(np.corrcoef(x, y)[0, 1])
        return r if math.isfinite(r) else 0.0
    except Exception:
        return 0.0


def _safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman 相關係數（優先 scipy，備援 rank-Pearson）"""
    try:
        from scipy.stats import spearmanr  # type: ignore
        r, _ = spearmanr(x, y)
        return float(r) if math.isfinite(r) else 0.0
    except Exception:
        try:
            rx = np.argsort(np.argsort(x)).astype(float)
            ry = np.argsort(np.argsort(y)).astype(float)
            return _safe_pearson(rx, ry)
        except Exception:
            return 0.0


def _conditional_mi(
    x: np.ndarray,
    y: np.ndarray,
    target: np.ndarray,
    n_bins: int = 5,
) -> float:
    """
    近似條件互信息 CMI(x, y | target)。
    公式：MI(x*y, target) - (MI(x, target) + MI(y, target)) / 2
    值 > 0 表示 x 與 y 的聯合交互作用對 target 有額外貢獻。
    """
    xy = x * y
    mi_xy = _safe_mi(xy, target, n_bins)
    mi_x = _safe_mi(x, target, n_bins)
    mi_y = _safe_mi(y, target, n_bins)
    return float(max(0.0, mi_xy - (mi_x + mi_y) / 2.0))


# ══════════════════════════════════════════════════════════════════════════════
# 主要 API
# ══════════════════════════════════════════════════════════════════════════════

def discover_ontology(
    feature_matrix: dict[str, list[float]],
    outcomes: list[int],
    top_k: int = 30,
    max_interactions: int = 20,
    prune_threshold: float = _PRUNE_THRESHOLD,
) -> OntologyReport:
    """
    從歷史特徵矩陣與賽果自動發現特徵重要性與交互作用。

    Args:
        feature_matrix: {feature_name: [value_per_game]} 每場比賽的特徵值
        outcomes: 每場比賽主隊勝(1) / 客隊勝(0) 列表
        top_k: 回傳最重要特徵數量（供後續 ML 使用）
        max_interactions: 最多發現的交互作用數量
        prune_threshold: 綜合分數低於此值建議剪枝

    Returns:
        OntologyReport（含重要性、交互作用、剪枝建議）
    """
    import datetime

    y = np.array(outcomes, dtype=float)
    n_samples = len(y)

    if n_samples < _MIN_SAMPLES:
        logger.warning(
            "樣本數 %d < %d，本體發現結果可信度低，仍繼續計算",
            n_samples, _MIN_SAMPLES,
        )

    # ── Step 1: 計算每個特徵的重要性 ──────────────────────────────────────────
    importance_entries: list[FeatureImportanceEntry] = []
    feature_arrays: dict[str, np.ndarray] = {}  # 儲存有效特徵供交互分析

    for feat_name, values in feature_matrix.items():
        x = np.array(values, dtype=float)
        min_len = min(len(x), n_samples)
        x = x[:min_len]
        y_aligned = y[:min_len]

        mask = np.isfinite(x) & np.isfinite(y_aligned)
        n_valid = int(mask.sum())

        if n_valid < _MIN_SAMPLES:
            importance_entries.append(FeatureImportanceEntry(
                feature_name=feat_name,
                mi_score=0.0,
                pearson_r=0.0,
                spearman_r=0.0,
                composite_score=0.0,
                data_available=False,
                sample_count=n_valid,
            ))
            continue

        xv, yv = x[mask], y_aligned[mask]

        # 常數特徵（標準差為 0）無預測力，直接歸零
        if float(xv.std()) < 1e-8:
            importance_entries.append(FeatureImportanceEntry(
                feature_name=feat_name,
                mi_score=0.0,
                pearson_r=0.0,
                spearman_r=0.0,
                composite_score=0.0,
                data_available=True,
                sample_count=n_valid,
            ))
            continue

        feature_arrays[feat_name] = xv

        mi = _safe_mi(xv, yv)
        pr = _safe_pearson(xv, yv)
        sr = _safe_spearman(xv, yv)
        composite = 0.6 * mi + 0.2 * abs(pr) + 0.2 * abs(sr)

        importance_entries.append(FeatureImportanceEntry(
            feature_name=feat_name,
            mi_score=round(mi, 4),
            pearson_r=round(pr, 4),
            spearman_r=round(sr, 4),
            composite_score=round(composite, 4),
            data_available=True,
            sample_count=n_valid,
        ))

    # ── Step 2: 排序重要性 ────────────────────────────────────────────────────
    importance_entries.sort(key=lambda e: e.composite_score, reverse=True)
    top_k_features = [
        e.feature_name for e in importance_entries[:top_k]
        if e.data_available
    ]

    # ── Step 3: 發現二階交互作用（取 top 15 兩兩組合） ────────────────────────
    interaction_candidates: list[InteractionCandidate] = []
    top_feats = [f for f in top_k_features if f in feature_arrays][:15]

    if top_feats:
        # 對齊目標長度
        min_target_len = min(len(feature_arrays[f]) for f in top_feats)
        y_short = y[:min_target_len]

        for i in range(len(top_feats)):
            for j in range(i + 1, len(top_feats)):
                if len(interaction_candidates) >= max_interactions:
                    break
                fa, fb = top_feats[i], top_feats[j]
                xa = feature_arrays[fa][:min_target_len]
                xb = feature_arrays[fb][:min_target_len]
                min_len = min(len(xa), len(xb), len(y_short))

                cmi = _conditional_mi(xa[:min_len], xb[:min_len], y_short[:min_len])
                if cmi < 0.005:
                    continue

                strength = (
                    "strong" if cmi >= _STRONG_INTERACTION
                    else "moderate" if cmi >= _MODERATE_INTERACTION
                    else "weak"
                )
                interaction_candidates.append(InteractionCandidate(
                    feature_a=fa,
                    feature_b=fb,
                    interaction_name=f"{fa}_x_{fb}",
                    conditional_mi=round(cmi, 4),
                    hypothesis=(
                        f"交互特徵「{fa} × {fb}」"
                        f"對賽果預測力 {strength}（CMI={cmi:.3f}）"
                    ),
                    strength=strength,
                ))
            if len(interaction_candidates) >= max_interactions:
                break

        interaction_candidates.sort(key=lambda ic: ic.conditional_mi, reverse=True)

    # ── Step 4: 剪枝建議 ──────────────────────────────────────────────────────
    prune_candidates = [
        PruneCandidate(
            feature_name=e.feature_name,
            composite_score=e.composite_score,
            reason=(
                f"樣本不足（{e.sample_count} < {_MIN_SAMPLES}）"
                if not e.data_available
                else f"綜合分數 {e.composite_score:.4f} < 閾值 {prune_threshold:.4f}"
            ),
        )
        for e in importance_entries
        if e.composite_score < prune_threshold
    ]

    return OntologyReport(
        n_samples=n_samples,
        n_features_analyzed=len(feature_matrix),
        feature_importance=importance_entries,
        interaction_candidates=interaction_candidates,
        prune_candidates=prune_candidates,
        top_k_features=top_k_features,
        timestamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def save_ontology_report(report: OntologyReport, path: str | Path) -> None:
    """將本體報告儲存為 JSON"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(
        "本體報告已儲存 → %s（%d 特徵，%d 交互作用建議）",
        p, report.n_features_analyzed, len(report.interaction_candidates),
    )


def load_ontology_report(path: str | Path) -> dict[str, Any]:
    """從 JSON 載入本體報告（返回原始 dict）"""
    p = Path(path)
    if not p.exists():
        logger.warning("本體報告不存在: %s", p)
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)
