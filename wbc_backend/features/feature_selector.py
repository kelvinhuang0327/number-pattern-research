"""
特徵自動剪枝 (Auto Feature Pruning) — Phase 5C
===============================================
從 277+ 特徵中自動保留最高預測力的穩定子集，避免過擬合。

方法：
  - 排列重要性 (Permutation Importance)：打亂特徵後觀察準確度下降
  - SHAP 值（可選，若 shap 套件可用則啟用）
  - K-fold 穩定性過濾：只保留在各 fold 中皆重要的特徵

輸出：
  - FeatureSelectorResult：選出特徵 + 剔除特徵 + 重要性分數
  - JSON 持久化：每週自動更新，供 dynamic_ensemble.py 訓練前置使用

設計原則：
  - SHAP 為可選（graceful fallback 到排列重要性）
  - 支援最小 10 場數據（防止 WBC 樣本不足問題）
  - 穩定性過濾只在樣本 >= 30 場時啟用（避免過濾過嚴）
"""
from __future__ import annotations

import json
import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── 預設值 ────────────────────────────────────────────────────────────────
_DEFAULT_TOP_N = 50
_MIN_IMPORTANCE = 0.0        # 排列重要性 < 0 表示特徵無貢獻
_STABILITY_THRESHOLD = 0.3   # K-fold 穩定性 < 30% 剪枝（樣本 >= 30 才啟用）
_MIN_SAMPLES_FOR_STABILITY = 30


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FeatureSelectorResult:
    """特徵選擇結果"""
    selected_features: list[str]        # 最終保留特徵（按重要性降序）
    rejected_features: list[str]        # 被剪枝特徵
    importance_scores: dict[str, float] # feature_name → 綜合重要性分數
    method: str                         # "permutation" | "shap+permutation"
    n_samples: int
    n_features_in: int
    n_features_out: int
    stability_scores: dict[str, float]  # K-fold 穩定性 (0-1)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_features": self.selected_features,
            "rejected_features": self.rejected_features,
            "importance_scores": {k: round(v, 6) for k, v in self.importance_scores.items()},
            "method": self.method,
            "n_samples": self.n_samples,
            "n_features_in": self.n_features_in,
            "n_features_out": self.n_features_out,
            "stability_scores": {k: round(v, 4) for k, v in self.stability_scores.items()},
            "timestamp": self.timestamp,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 排列重要性
# ══════════════════════════════════════════════════════════════════════════════

def _permutation_importance(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_repeats: int = 5,
    random_state: int = 42,
) -> dict[str, float]:
    """
    排列重要性：打亂特徵值後觀察模型準確度下降幅度。
    使用輕量級邏輯回歸（速度快，不需複雜 ML）。
    若 sklearn 未安裝則退回相關性法。
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.inspection import permutation_importance as _pi
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf = LogisticRegression(C=1.0, max_iter=500, random_state=random_state, solver="lbfgs")
            clf.fit(X_scaled, y.astype(int))

        result = _pi(
            clf, X_scaled, y.astype(int),
            n_repeats=n_repeats,
            random_state=random_state,
            scoring="accuracy",
        )
        return {
            name: float(score)
            for name, score in zip(feature_names, result.importances_mean)
        }
    except ImportError:
        logger.info("sklearn 未安裝，使用備援相關性法計算重要性")
        return _correlation_importance(X, y, feature_names)
    except Exception as e:
        logger.warning("排列重要性計算失敗: %s，退回相關性法", e)
        return _correlation_importance(X, y, feature_names)


def _correlation_importance(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
) -> dict[str, float]:
    """備援：使用絕對 Pearson 相關係數作為重要性代理"""
    scores: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        xi = X[:, i]
        if xi.std() < 1e-8:
            scores[name] = 0.0
            continue
        try:
            r = float(np.corrcoef(xi, y)[0, 1])
            scores[name] = abs(r) if np.isfinite(r) else 0.0
        except Exception:
            scores[name] = 0.0
    return scores


# ══════════════════════════════════════════════════════════════════════════════
# SHAP（可選）
# ══════════════════════════════════════════════════════════════════════════════

def _shap_importance(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    random_state: int = 42,
) -> Optional[dict[str, float]]:
    """
    SHAP 特徵重要性（可選，需安裝 shap 套件）。
    使用淺層 RandomForest 作為基底模型（速度快）。
    未安裝或計算失敗時返回 None。
    """
    try:
        import shap  # type: ignore
        from sklearn.ensemble import RandomForestClassifier

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf = RandomForestClassifier(
                n_estimators=50, max_depth=4, random_state=random_state, n_jobs=1,
            )
            clf.fit(X, y.astype(int))

        explainer = shap.TreeExplainer(clf, feature_perturbation="interventional")
        shap_values = explainer.shap_values(X)

        # 二元分類：shap_values 可能是 [class0_vals, class1_vals]
        if isinstance(shap_values, list) and len(shap_values) == 2:
            shap_arr = np.abs(shap_values[1])
        else:
            shap_arr = np.abs(np.array(shap_values))

        mean_shap = shap_arr.mean(axis=0)
        return {name: float(v) for name, v in zip(feature_names, mean_shap)}

    except ImportError:
        logger.info("shap 未安裝，跳過 SHAP 分析（使用純排列重要性）")
        return None
    except Exception as e:
        logger.warning("SHAP 計算失敗: %s，退回排列重要性", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# K-fold 穩定性分析
# ══════════════════════════════════════════════════════════════════════════════

def _stability_scores(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_folds: int = 3,
    random_state: int = 42,
) -> dict[str, float]:
    """
    K-fold 穩定性分數：特徵在各 fold 的重要性一致性。
    穩定性 = 1 - CV（變異係數），值越高越穩定。
    樣本太少（< n_folds * 5）時返回預設 0.5。
    """
    n = len(y)
    if n < n_folds * 5:
        return {name: 0.5 for name in feature_names}

    rng = np.random.default_rng(random_state)
    indices = rng.permutation(n)
    fold_size = n // n_folds
    fold_imps: list[dict[str, float]] = []

    for k in range(n_folds):
        test_start = k * fold_size
        test_end = (k + 1) * fold_size
        train_idx = np.concatenate([indices[:test_start], indices[test_end:]])
        if len(train_idx) < 5:
            continue
        fi = _correlation_importance(X[train_idx], y[train_idx], feature_names)
        fold_imps.append(fi)

    if not fold_imps:
        return {name: 0.5 for name in feature_names}

    stability: dict[str, float] = {}
    for name in feature_names:
        vals = np.array([fi.get(name, 0.0) for fi in fold_imps])
        mean_v = float(vals.mean())
        std_v = float(vals.std())
        cv = std_v / (mean_v + 1e-8)
        stability[name] = float(np.clip(1.0 - cv, 0.0, 1.0))
    return stability


# ══════════════════════════════════════════════════════════════════════════════
# 主要 API
# ══════════════════════════════════════════════════════════════════════════════

def select_features(
    feature_matrix: dict[str, list[float]],
    outcomes: list[int],
    top_n: int = _DEFAULT_TOP_N,
    use_shap: bool = True,
    stability_threshold: float = _STABILITY_THRESHOLD,
    min_importance: float = _MIN_IMPORTANCE,
    random_state: int = 42,
) -> FeatureSelectorResult:
    """
    從特徵矩陣自動選出最穩定、最重要的特徵子集。

    Args:
        feature_matrix: {feature_name: [value_per_game]} 歷史特徵值
        outcomes: [1/0] 主隊勝負（1=主隊勝）
        top_n: 最多保留的特徵數量（預設 50）
        use_shap: 是否嘗試 SHAP（需安裝 shap 套件）
        stability_threshold: K-fold 穩定性門檻（低於此值剪枝）
        min_importance: 最低排列重要性門檻（< 0 的直接剪枝）
        random_state: 亂數種子（可重現性）

    Returns:
        FeatureSelectorResult（含 JSON 持久化方法）
    """
    import datetime

    y = np.array(outcomes, dtype=float)
    n_samples = len(y)

    # ── 建構特徵矩陣，處理 NaN ──────────────────────────────────────────────
    feature_names: list[str] = []
    X_cols: list[np.ndarray] = []

    for name, vals in feature_matrix.items():
        arr = np.array(vals, dtype=float)[:n_samples]
        if len(arr) < n_samples:
            arr = np.pad(arr, (0, n_samples - len(arr)), constant_values=np.nan)
        col_mean = float(np.nanmean(arr)) if np.isfinite(np.nanmean(arr)) else 0.0
        arr = np.where(np.isfinite(arr), arr, col_mean)
        X_cols.append(arr)
        feature_names.append(name)

    if not X_cols:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return FeatureSelectorResult(
            selected_features=[], rejected_features=[],
            importance_scores={}, method="none",
            n_samples=n_samples, n_features_in=0, n_features_out=0,
            stability_scores={}, timestamp=ts,
        )

    X = np.column_stack(X_cols)

    # ── 排列重要性 ───────────────────────────────────────────────────────────
    perm_imp = _permutation_importance(X, y, feature_names, random_state=random_state)

    # ── SHAP（可選）─────────────────────────────────────────────────────────
    shap_imp: Optional[dict[str, float]] = None
    method = "permutation"
    if use_shap and n_samples >= 15:
        shap_imp = _shap_importance(X, y, feature_names, random_state=random_state)
        if shap_imp is not None:
            method = "shap+permutation"

    # ── 合併重要性分數 ────────────────────────────────────────────────────────
    importance_scores: dict[str, float] = {}
    if shap_imp is not None:
        max_shap = max(shap_imp.values()) or 1.0
        max_perm = max((abs(v) for v in perm_imp.values()), default=1.0) or 1.0
        for name in feature_names:
            s_norm = shap_imp.get(name, 0.0) / max_shap
            p_norm = max(0.0, perm_imp.get(name, 0.0)) / max_perm
            importance_scores[name] = 0.6 * s_norm + 0.4 * p_norm
    else:
        for name in feature_names:
            importance_scores[name] = max(0.0, perm_imp.get(name, 0.0))

    # ── K-fold 穩定性 ────────────────────────────────────────────────────────
    stability = _stability_scores(X, y, feature_names, random_state=random_state)

    # ── 篩選特徵 ─────────────────────────────────────────────────────────────
    sorted_feats = sorted(
        feature_names,
        key=lambda n: importance_scores.get(n, 0.0),
        reverse=True,
    )

    selected: list[str] = []
    rejected: list[str] = []
    apply_stability = n_samples >= _MIN_SAMPLES_FOR_STABILITY

    for name in sorted_feats:
        imp = importance_scores.get(name, 0.0)
        stab = stability.get(name, 0.0)

        if len(selected) >= top_n:
            rejected.append(name)
        elif imp < min_importance:
            rejected.append(name)
        elif apply_stability and stab < stability_threshold:
            rejected.append(name)
        else:
            selected.append(name)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return FeatureSelectorResult(
        selected_features=selected,
        rejected_features=rejected,
        importance_scores=importance_scores,
        method=method,
        n_samples=n_samples,
        n_features_in=len(feature_names),
        n_features_out=len(selected),
        stability_scores=stability,
        timestamp=ts,
    )


def save_feature_selector_result(
    result: FeatureSelectorResult,
    path: str | Path,
) -> None:
    """將特徵選擇結果儲存為 JSON（每週自動更新用）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    logger.info(
        "特徵選擇結果已儲存 → %s（%d → %d 特徵，方法：%s）",
        p, result.n_features_in, result.n_features_out, result.method,
    )


def load_stable_features(path: str | Path) -> list[str]:
    """
    從 JSON 載入穩定特徵清單。
    供 dynamic_ensemble.py 訓練前置步驟使用。
    檔案不存在時返回空清單（fallback 到全特徵）。
    """
    p = Path(path)
    if not p.exists():
        logger.warning("特徵選擇結果不存在: %s，將使用全部特徵", p)
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("selected_features", [])
    logger.info("載入穩定特徵清單: %d 個特徵 (來自 %s)", len(features), p)
    return features
