#!/usr/bin/env python3
"""
P203-PRED-EVIDENCE — Leakage-Safe Calibration and Feature-Ablation Walk-Forward Study
=====================================================================================

研究證據工作（research-only evidence study），**非** production model promotion。

目標：使用現有授權的本地歷史資料（``data/mlb_data_loader.load_mlb_records()``，
2,430 場 MLB 2025，``data_source="mlb_2025_retrosheet"``），以可重現且無未來資料洩漏
（look-ahead leakage-free）的 chronological walk-forward 設計，判定：

  1. 校準（Platt/logistic calibration）是否改善 out-of-sample Brier score 或 log loss。
  2. 哪些既有 feature groups 提供正向 OOS 價值。
  3. 哪些 feature groups 造成退化或不穩定。
  4. 改善是否跨時間區段（folds / months / 機率帶）維持。
  5. 結果是否優於 frozen baseline 與 simple reference model。

嚴格邊界（本腳本強制）：
  - 純讀取本地已授權歷史資料；無網路、無 DB 寫入、無 MLB/StatsAPI endpoint。
  - 不修改任何既有 source/test/config/fixture/governance/report。
  - 不使用 P202D/P202E/P202G-B 空骨架作為已填充資料。
  - 僅產出兩份授權報告（JSON + Markdown）。
  - 不做 model/champion promotion、registry、controlled_apply。

洩漏控制（leakage controls）：
  - 評估單位 = 單一 canonical 比賽（``game_id``）。
  - chronological expanding-window folds；fold 邊界對齊「整日」，
    任一訓練時間戳嚴格早於其 test fold。
  - 每個 fold 內：特徵標準化、logistic 模型、Platt 校準皆只用「過去」資料擬合。
  - frozen baseline 與所有 candidate 在「相同 OOS 列集」上比較。
  - ``market_home_prob`` / ``ou_line`` 視為收盤線/賽後混入來源 → 排除於預測輸入。
  - 所有 ``actual_*`` 賽後欄位永不作為預測輸入。

用法：
  python scripts/p203_prediction_evidence_study.py
  python scripts/p203_prediction_evidence_study.py \
      --json report/p203_prediction_evidence_study_20260614.json \
      --md report/p203_prediction_evidence_study_20260614.md

可重現性：固定亂數種子；報告浮點四捨五入至固定位數；``generated_at`` 取自
``SOURCE_DATE_EPOCH`` 或固定預設值 → 重跑產生 byte-identical 輸出。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

# 允許從 repo 根目錄 import data.* / wbc_backend.*（直接執行腳本時 sys.path[0]=scripts/）
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── 可重現性與研究常數（在比較結果「之前」凍結）──────────────────────────────
SCHEMA_VERSION = "p203_pred_evidence_v1"
RANDOM_SEED = 20260614
N_SEGMENTS = 6                    # 6 個 date-disjoint 連續區段 → 5 個 expanding OOS folds
BOOTSTRAP_RESAMPLES = 2000        # block bootstrap by game-date
FLOAT_ROUND = 6                   # 報告浮點位數（確保 byte-identical 重跑）
ECE_BINS = 10                     # 固定 reliability bins
LOGLOSS_EPS = 1e-12
PROB_CLIP = 1e-6

# 固定 hyperparameters（不做 sweep；如需選擇僅能以 past-only inner validation）
LR_L2 = 1.0                       # 特徵 logistic 的 L2（截距不正則化）
PLATT_L2 = 1e-6                   # Platt 校準 logistic 的 L2
IRLS_MAX_ITER = 100
IRLS_TOL = 1e-9
INNER_CALIB_FRACTION = 0.20       # candidate 內層 past-only 校準切分（最後 20% 日期）

# 決策閘門值（在看到結果「之前」凍結）
LOGLOSS_MATERIAL_ABS = 0.01       # log loss 退化「顯著」之絕對門檻
SEGMENT_MIN_N = 100               # segment 樣本充足下限
MAJORITY_FOLDS = 3                # 5 folds 中需多數（>=3）改善

REPORT_DATE = "20260614"
DEFAULT_JSON = Path("report") / f"p203_prediction_evidence_study_{REPORT_DATE}.json"
DEFAULT_MD = Path("report") / f"p203_prediction_evidence_study_{REPORT_DATE}.md"

# 預設歷史資料來源（與 data/mlb_data_loader.py 一致；僅用於輸入指紋）
_SCORES_CSV = Path("data") / "mlb_2025" / "mlb-2025-asplayed.csv"
_ODDS_CSV = Path("data") / "mlb_2025" / "mlb_odds_2025_real.csv"

# 賽前特徵分組（provenance-based；僅使用實際存在於 GameRecord 的賽前欄位）
FEATURE_GROUPS: dict[str, list[str]] = {
    "elo": ["home_elo", "away_elo"],
    "offense": ["home_woba", "away_woba"],
    "pitching": ["home_fip", "away_fip"],
    "form": ["home_rsi", "away_rsi"],
    "schedule": ["home_rest_days", "away_rest_days"],
}
ALL_FEATURES: list[str] = [f for group in FEATURE_GROUPS.values() for f in group]

# 明確排除於預測輸入的欄位（洩漏風險 / 賽後）
EXCLUDED_PREDICTIVE_FIELDS: dict[str, str] = {
    "market_home_prob": "closing-line/post-season scrape provenance mixed with Elo fallback; "
                        "point-in-time pregame semantics NOT clear -> leakage risk, excluded as predictor",
    "ou_line": "over/under total line, same closing/post-game provenance concern -> excluded as predictor",
    "actual_home_score": "post-game outcome",
    "actual_away_score": "post-game outcome",
    "actual_home_win": "prediction target (post-game outcome), never an input",
    "actual_total_runs": "post-game outcome",
}

logger = logging.getLogger("p203")


# ════════════════════════════════════════════════════════════════════════════
# 純數值工具（deterministic）
# ════════════════════════════════════════════════════════════════════════════

def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, PROB_CLIP, 1.0 - PROB_CLIP)
    return np.log(p / (1.0 - p))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float,
                 max_iter: int = IRLS_MAX_ITER, tol: float = IRLS_TOL) -> np.ndarray:
    """Deterministic L2-regularised logistic regression via Newton-Raphson (IRLS).

    X 須已含截距欄（第 0 欄為 1）。截距不正則化。回傳權重向量。
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n, d = X.shape
    w = np.zeros(d, dtype=np.float64)
    reg = np.eye(d, dtype=np.float64) * l2
    reg[0, 0] = 0.0
    for _ in range(max_iter):
        p = _sigmoid(X @ w)
        wts = np.clip(p * (1.0 - p), 1e-12, None)
        grad = X.T @ (p - y) + reg @ w
        hess = X.T @ (X * wts[:, None]) + reg
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hess, grad, rcond=None)[0]
        w_new = w - step
        if np.max(np.abs(w_new - w)) < tol:
            return w_new
        w = w_new
    return w


def fit_platt(scores: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Platt/logistic 校準：對 score 擬合 sigmoid(a + b*score)。回傳 (a, b)。"""
    s = np.asarray(scores, dtype=np.float64).reshape(-1, 1)
    X = np.hstack([np.ones((s.shape[0], 1)), s])
    w = fit_logistic(X, y, l2=PLATT_L2)
    return float(w[0]), float(w[1])


def apply_platt(scores: np.ndarray, a: float, b: float) -> np.ndarray:
    return _sigmoid(a + b * np.asarray(scores, dtype=np.float64))


def standardize_fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std = np.where(std < 1e-12, 1.0, std)
    return mean, std


def standardize_apply(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (X - mean) / std


# ════════════════════════════════════════════════════════════════════════════
# 指標（metrics）
# ════════════════════════════════════════════════════════════════════════════

def brier_score(p: np.ndarray, y: np.ndarray) -> float:
    p = np.asarray(p, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    return float(np.mean((p - y) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(np.asarray(p, dtype=np.float64), LOGLOSS_EPS, 1.0 - LOGLOSS_EPS)
    y = np.asarray(y, dtype=np.float64)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def expected_calibration_error(p: np.ndarray, y: np.ndarray, n_bins: int = ECE_BINS) -> float:
    p = np.asarray(p, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(p)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        if not np.any(mask):
            continue
        conf = float(np.mean(p[mask]))
        acc = float(np.mean(y[mask]))
        ece += (np.sum(mask) / n) * abs(conf - acc)
    return float(ece)


def calibration_line(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """以 logistic 回歸 y ~ logit(p) 估計 calibration intercept/slope（理想 0/1）。"""
    s = _logit(np.asarray(p, dtype=np.float64)).reshape(-1, 1)
    X = np.hstack([np.ones((s.shape[0], 1)), s])
    w = fit_logistic(X, np.asarray(y, dtype=np.float64), l2=PLATT_L2)
    return float(w[0]), float(w[1])


# ════════════════════════════════════════════════════════════════════════════
# 資料契約（data contract）
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StudyData:
    game_ids: list[str]
    dates: list[str]               # 'YYYY-MM-DD'，與 rows 對齊
    X: np.ndarray                  # (n, len(ALL_FEATURES)) 賽前特徵
    elo_prob: np.ndarray           # (n,) frozen Elo 賽前主隊勝率
    y: np.ndarray                  # (n,) actual_home_win
    feature_names: list[str]
    raw_count: int
    excluded_rows: list[dict]
    unique_dates: list[str]


def _elo_home_prob(home_elo: float, away_elo: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / 400.0))


def build_study_data(records: Sequence) -> StudyData:
    """將 GameRecord 轉為 leakage-safe 研究矩陣，並執行排除規則。

    排除（並計數）：target 非 {0,1}、日期不可解析、或任一特徵非有限值之列。
    """
    raw_count = len(records)
    excluded: list[dict] = []
    rows_feat: list[list[float]] = []
    rows_elo: list[float] = []
    rows_y: list[int] = []
    ids: list[str] = []
    dates: list[str] = []

    for r in records:
        gid = getattr(r, "game_id", None)
        gdate = getattr(r, "game_date", None)
        target = getattr(r, "actual_home_win", None)
        # target 驗證
        if target not in (0, 1):
            excluded.append({"game_id": gid, "reason": "target_not_binary", "value": str(target)})
            continue
        # 日期驗證
        try:
            datetime.strptime(str(gdate), "%Y-%m-%d")
        except (ValueError, TypeError):
            excluded.append({"game_id": gid, "reason": "unparseable_date", "value": str(gdate)})
            continue
        # 特徵抽取與有限性驗證
        feats: list[float] = []
        ok = True
        for name in ALL_FEATURES:
            val = getattr(r, name, None)
            try:
                fval = float(val)
            except (ValueError, TypeError):
                ok = False
                break
            if not math.isfinite(fval):
                ok = False
                break
            feats.append(fval)
        if not ok:
            excluded.append({"game_id": gid, "reason": "non_finite_feature"})
            continue
        # frozen Elo baseline
        he = float(getattr(r, "home_elo"))
        ae = float(getattr(r, "away_elo"))
        elo_p = _elo_home_prob(he, ae)
        if not math.isfinite(elo_p):
            excluded.append({"game_id": gid, "reason": "non_finite_elo_prob"})
            continue

        rows_feat.append(feats)
        rows_elo.append(elo_p)
        rows_y.append(int(target))
        ids.append(str(gid))
        dates.append(str(gdate))

    # 依 (date, game_id) 穩定排序，確保完全確定性與嚴格時序
    order = sorted(range(len(ids)), key=lambda i: (dates[i], ids[i]))
    X = np.array([rows_feat[i] for i in order], dtype=np.float64) if order else np.zeros((0, len(ALL_FEATURES)))
    elo_prob = np.array([rows_elo[i] for i in order], dtype=np.float64)
    y = np.array([rows_y[i] for i in order], dtype=np.float64)
    s_ids = [ids[i] for i in order]
    s_dates = [dates[i] for i in order]
    uniq_dates = sorted(set(s_dates))

    return StudyData(
        game_ids=s_ids, dates=s_dates, X=X, elo_prob=elo_prob, y=y,
        feature_names=list(ALL_FEATURES), raw_count=raw_count,
        excluded_rows=excluded, unique_dates=uniq_dates,
    )


# ════════════════════════════════════════════════════════════════════════════
# Walk-forward folds（expanding window, date-disjoint）
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Fold:
    index: int
    train_idx: np.ndarray
    test_idx: np.ndarray
    train_dates: tuple[str, str]
    test_dates: tuple[str, str]


def build_segments(dates: list[str], unique_dates: list[str], n_segments: int) -> list[list[str]]:
    """把 unique dates 依「累積比賽數」切成 n_segments 個 date-disjoint 連續區段。"""
    counts: dict[str, int] = {}
    for d in dates:
        counts[d] = counts.get(d, 0) + 1
    total = len(dates)
    target = total / n_segments
    segments: list[list[str]] = []
    cur: list[str] = []
    cum = 0
    seg_idx = 0
    for d in unique_dates:
        cur.append(d)
        cum += counts[d]
        # 當累積達到 (seg_idx+1)*target 且尚未到最後一段時切段
        if seg_idx < n_segments - 1 and cum >= target * (seg_idx + 1):
            segments.append(cur)
            cur = []
            seg_idx += 1
    if cur:
        segments.append(cur)
    # 合併殘段以確保恰好 n_segments（極端情況防護）
    while len(segments) > n_segments:
        last = segments.pop()
        segments[-1].extend(last)
    return segments


def build_folds(data: StudyData, n_segments: int = N_SEGMENTS) -> list[Fold]:
    """expanding window：fold i 訓練 segments[0..i]、測試 segment[i+1]，i=0..n_segments-2。"""
    segments = build_segments(data.dates, data.unique_dates, n_segments)
    date_to_idx: dict[str, list[int]] = {}
    for i, d in enumerate(data.dates):
        date_to_idx.setdefault(d, []).append(i)

    folds: list[Fold] = []
    for i in range(len(segments) - 1):
        train_dates = [d for seg in segments[: i + 1] for d in seg]
        test_dates = segments[i + 1]
        train_idx = np.array(sorted(j for d in train_dates for j in date_to_idx[d]), dtype=int)
        test_idx = np.array(sorted(j for d in test_dates for j in date_to_idx[d]), dtype=int)
        folds.append(Fold(
            index=i,
            train_idx=train_idx,
            test_idx=test_idx,
            train_dates=(train_dates[0], train_dates[-1]),
            test_dates=(test_dates[0], test_dates[-1]),
        ))
    return folds


def assert_no_leakage(data: StudyData, folds: list[Fold]) -> dict:
    """結構性洩漏檢查：所有訓練日期嚴格早於其 test fold 的最早日期；無 train/test 重疊。"""
    checks = {
        "n_folds": len(folds),
        "all_train_before_test": True,
        "no_index_overlap": True,
        "test_folds_disjoint": True,
        "violations": [],
    }
    seen_test: set[int] = set()
    for f in folds:
        max_train = max(data.dates[j] for j in f.train_idx)
        min_test = min(data.dates[j] for j in f.test_idx)
        if not (max_train < min_test):
            checks["all_train_before_test"] = False
            checks["violations"].append(
                {"fold": f.index, "max_train_date": max_train, "min_test_date": min_test})
        if set(f.train_idx) & set(f.test_idx):
            checks["no_index_overlap"] = False
            checks["violations"].append({"fold": f.index, "issue": "train_test_overlap"})
        ts = set(int(j) for j in f.test_idx)
        if ts & seen_test:
            checks["test_folds_disjoint"] = False
            checks["violations"].append({"fold": f.index, "issue": "test_fold_overlap"})
        seen_test |= ts
    checks["leakage_free"] = bool(
        checks["all_train_before_test"] and checks["no_index_overlap"] and checks["test_folds_disjoint"])
    return checks


# ════════════════════════════════════════════════════════════════════════════
# 模型（每個 fold 內只用過去資料擬合）
# ════════════════════════════════════════════════════════════════════════════

def predict_frozen_baseline(data: StudyData, fold: Fold) -> np.ndarray:
    """frozen Elo 賽前勝率（無擬合）。"""
    return data.elo_prob[fold.test_idx]


def predict_simple_reference(data: StudyData, fold: Fold) -> np.ndarray:
    """past-only 主隊勝率 climatology（常數）。"""
    base = float(np.mean(data.y[fold.train_idx]))
    return np.full(len(fold.test_idx), base, dtype=np.float64)


def predict_calibrated_baseline(data: StudyData, fold: Fold) -> np.ndarray:
    """Platt 校準 frozen Elo prob（校準器只用訓練 fold 擬合）。"""
    s_train = _logit(data.elo_prob[fold.train_idx])
    a, b = fit_platt(s_train, data.y[fold.train_idx])
    s_test = _logit(data.elo_prob[fold.test_idx])
    return apply_platt(s_test, a, b)


def _inner_split(data: StudyData, train_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """訓練 fold 內，依日期取最後 INNER_CALIB_FRACTION 的「日」作 past-only 校準集。"""
    tr_dates = sorted(set(data.dates[j] for j in train_idx))
    if len(tr_dates) < 5:
        return train_idx, train_idx  # 退化情況：回退（測試以小資料覆蓋）
    cut = int(math.ceil(len(tr_dates) * (1.0 - INNER_CALIB_FRACTION)))
    cut = min(max(cut, 1), len(tr_dates) - 1)
    inner_train_dates = set(tr_dates[:cut])
    inner_calib_dates = set(tr_dates[cut:])
    inner_train = np.array([j for j in train_idx if data.dates[j] in inner_train_dates], dtype=int)
    inner_calib = np.array([j for j in train_idx if data.dates[j] in inner_calib_dates], dtype=int)
    return inner_train, inner_calib


def _fit_feature_model(data: StudyData, train_idx: np.ndarray, feature_cols: list[int]):
    """回傳 predict(test_idx)->probs 的 closure；LR 於 inner-train、Platt 於 inner-calib（皆 past-only）。"""
    inner_train, inner_calib = _inner_split(data, train_idx)

    def _design(idx: np.ndarray, mean, std) -> np.ndarray:
        Xc = data.X[np.ix_(idx, feature_cols)]
        Xs = standardize_apply(Xc, mean, std)
        return np.hstack([np.ones((Xs.shape[0], 1)), Xs])

    Xtr_raw = data.X[np.ix_(inner_train, feature_cols)]
    mean, std = standardize_fit(Xtr_raw)
    w = fit_logistic(_design(inner_train, mean, std), data.y[inner_train], l2=LR_L2)

    # Platt 校準於 inner-calib 的 LR 原始機率
    calib_scores = _logit(_sigmoid(_design(inner_calib, mean, std) @ w))
    a, b = fit_platt(calib_scores, data.y[inner_calib])

    def predict(test_idx: np.ndarray) -> np.ndarray:
        raw = _sigmoid(_design(test_idx, mean, std) @ w)
        return apply_platt(_logit(raw), a, b)

    return predict


def predict_candidate_full(data: StudyData, fold: Fold) -> np.ndarray:
    cols = list(range(len(ALL_FEATURES)))
    return _fit_feature_model(data, fold.train_idx, cols)(fold.test_idx)


def make_ablation_predictor(dropped_group: str) -> Callable[[StudyData, Fold], np.ndarray]:
    kept = [f for g, fs in FEATURE_GROUPS.items() if g != dropped_group for f in fs]
    cols = [ALL_FEATURES.index(f) for f in kept]

    def _predict(data: StudyData, fold: Fold) -> np.ndarray:
        return _fit_feature_model(data, fold.train_idx, cols)(fold.test_idx)

    return _predict


# ════════════════════════════════════════════════════════════════════════════
# 跨 fold pooled OOS 評估
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelResult:
    name: str
    oos_pred: np.ndarray           # 對齊 pooled OOS 列（依 fold 順序串接）
    fold_brier: list[float]
    fold_logloss: list[float]


def evaluate_model(name: str, predict_fn: Callable[[StudyData, Fold], np.ndarray],
                   data: StudyData, folds: list[Fold]) -> ModelResult:
    preds: list[np.ndarray] = []
    fold_brier: list[float] = []
    fold_ll: list[float] = []
    for f in folds:
        p = predict_fn(data, f)
        yt = data.y[f.test_idx]
        preds.append(p)
        fold_brier.append(brier_score(p, yt))
        fold_ll.append(log_loss(p, yt))
    return ModelResult(name=name, oos_pred=np.concatenate(preds), fold_brier=fold_brier, fold_logloss=fold_ll)


def pooled_oos_layout(folds: list[Fold]) -> tuple[np.ndarray, list[str], list[str]]:
    """回傳 pooled OOS 的 (row_index_array, dates, game_ids 佔位用 idx)。"""
    idx = np.concatenate([f.test_idx for f in folds])
    return idx, [], []


def metrics_block(pred: np.ndarray, y: np.ndarray) -> dict:
    ci, sl = calibration_line(pred, y)
    return {
        "brier": round(brier_score(pred, y), FLOAT_ROUND),
        "log_loss": round(log_loss(pred, y), FLOAT_ROUND),
        "ece": round(expected_calibration_error(pred, y), FLOAT_ROUND),
        "calibration_intercept": round(ci, FLOAT_ROUND),
        "calibration_slope": round(sl, FLOAT_ROUND),
        "mean_pred": round(float(np.mean(pred)), FLOAT_ROUND),
        "n": int(len(pred)),
    }


# ════════════════════════════════════════════════════════════════════════════
# Block bootstrap（by game-date）for Brier improvement CI
# ════════════════════════════════════════════════════════════════════════════

def block_bootstrap_brier_delta(base_pred: np.ndarray, cand_pred: np.ndarray,
                                y: np.ndarray, oos_dates: list[str],
                                n_resamples: int, seed: int) -> dict:
    """以「比賽日」為區塊做 paired bootstrap，估計 Brier improvement = Brier_base - Brier_cand 的 95% CI。"""
    rng = np.random.default_rng(seed)
    date_index: dict[str, list[int]] = {}
    for i, d in enumerate(oos_dates):
        date_index.setdefault(d, []).append(i)
    unique = list(date_index.keys())
    blocks = [np.array(date_index[d], dtype=int) for d in unique]
    n_blocks = len(blocks)

    deltas = np.empty(n_resamples, dtype=np.float64)
    point = brier_score(base_pred, y) - brier_score(cand_pred, y)
    for b in range(n_resamples):
        pick = rng.integers(0, n_blocks, size=n_blocks)
        rows = np.concatenate([blocks[k] for k in pick])
        bb = brier_score(base_pred[rows], y[rows])
        cb = brier_score(cand_pred[rows], y[rows])
        deltas[b] = bb - cb
    lo = float(np.percentile(deltas, 2.5))
    hi = float(np.percentile(deltas, 97.5))
    return {
        "brier_improvement_point": round(point, FLOAT_ROUND),
        "brier_improvement_mean": round(float(np.mean(deltas)), FLOAT_ROUND),
        "ci95_low": round(lo, FLOAT_ROUND),
        "ci95_high": round(hi, FLOAT_ROUND),
        "ci_excludes_zero": bool(lo > 0.0 or hi < 0.0),
        "ci_lower_above_zero": bool(lo > 0.0),
        "n_resamples": int(n_resamples),
        "n_blocks": int(n_blocks),
        "definition": "brier_improvement = brier_baseline - brier_candidate (positive => candidate better)",
    }


# ════════════════════════════════════════════════════════════════════════════
# Segment stability
# ════════════════════════════════════════════════════════════════════════════

def _segment_deltas(base_pred, cand_pred, y, mask) -> dict:
    n = int(np.sum(mask))
    if n == 0:
        return {"n": 0, "insufficient": True}
    bb = brier_score(base_pred[mask], y[mask])
    cb = brier_score(cand_pred[mask], y[mask])
    return {
        "n": n,
        "baseline_brier": round(bb, FLOAT_ROUND),
        "candidate_brier": round(cb, FLOAT_ROUND),
        "brier_improvement": round(bb - cb, FLOAT_ROUND),
        "insufficient": bool(n < SEGMENT_MIN_N),
    }


def segment_stability(base_pred, cand_pred, y, oos_dates: list[str],
                      oos_fold_id: list[int], base_for_band: np.ndarray) -> dict:
    out: dict = {"by_fold": {}, "by_month": {}, "by_prob_band": {}}
    base_pred = np.asarray(base_pred)
    cand_pred = np.asarray(cand_pred)
    y = np.asarray(y)
    fold_arr = np.array(oos_fold_id)
    for fid in sorted(set(oos_fold_id)):
        out["by_fold"][f"fold_{fid}"] = _segment_deltas(base_pred, cand_pred, y, fold_arr == fid)
    months = np.array([d[:7] for d in oos_dates])
    for m in sorted(set(months.tolist())):
        out["by_month"][m] = _segment_deltas(base_pred, cand_pred, y, months == m)
    bands = [("p_lt_0.45", base_for_band < 0.45),
             ("p_0.45_0.55", (base_for_band >= 0.45) & (base_for_band <= 0.55)),
             ("p_gt_0.55", base_for_band > 0.55)]
    for label, mask in bands:
        out["by_prob_band"][label] = _segment_deltas(base_pred, cand_pred, y, mask)
    return out


# ════════════════════════════════════════════════════════════════════════════
# 決策閘門（在看到結果前凍結邏輯）
# ════════════════════════════════════════════════════════════════════════════

def decide_gate(primary: dict, boot: dict, base_metrics: dict, cand_metrics: dict,
                fold_improved: list[bool], segments: dict, leakage_free: bool) -> dict:
    point = boot["brier_improvement_point"]
    ci_lower_above_zero = boot["ci_lower_above_zero"]
    n_folds = len(fold_improved)
    n_improved = sum(1 for x in fold_improved if x)
    majority_folds = n_improved >= MAJORITY_FOLDS
    logloss_delta = cand_metrics["log_loss"] - base_metrics["log_loss"]  # 正 => candidate 更差
    logloss_not_worse = logloss_delta <= LOGLOSS_MATERIAL_ABS
    coverage_equal = base_metrics["n"] == cand_metrics["n"]

    # 「非單一小 segment 驅動」：機率帶中多數（>=2/3）改善，或移除最佳月份後仍正
    bands = segments["by_prob_band"]
    band_improved = [v["brier_improvement"] > 0 for v in bands.values() if not v.get("insufficient", True)]
    bands_majority = (sum(band_improved) >= max(1, (len(band_improved) // 2) + 1)) if band_improved else False
    months = {k: v for k, v in segments["by_month"].items() if not v.get("insufficient", True)}
    not_single_segment = bands_majority
    if not not_single_segment and len(months) >= 2:
        # 移除改善最大的月份後，整體（以各月加權）仍為正？
        contrib = sorted(months.items(), key=lambda kv: kv[1]["brier_improvement"], reverse=True)
        remaining = contrib[1:]
        if remaining:
            weighted = sum(v["brier_improvement"] * v["n"] for _, v in remaining)
            not_single_segment = weighted > 0

    material_worse = point < 0 and ci_lower_above_zero is False and (boot["ci95_high"] < 0)
    no_improvement_any = (n_improved == 0)

    positive = (
        point > 0
        and ci_lower_above_zero
        and logloss_not_worse
        and leakage_free
        and majority_folds
        and not_single_segment
        and coverage_equal
    )
    negative = (
        material_worse
        or no_improvement_any
    )
    if positive:
        classification = "POSITIVE"
    elif negative:
        classification = "NEGATIVE"
    else:
        classification = "INCONCLUSIVE"

    return {
        "classification": classification,
        "criteria": {
            "brier_point_improves": bool(point > 0),
            "ci95_lower_above_zero": bool(ci_lower_above_zero),
            "log_loss_not_materially_worse": bool(logloss_not_worse),
            "log_loss_delta": round(logloss_delta, FLOAT_ROUND),
            "leakage_free": bool(leakage_free),
            "majority_folds_improved": bool(majority_folds),
            "folds_improved": f"{n_improved}/{n_folds}",
            "not_single_segment_driven": bool(not_single_segment),
            "coverage_equal": bool(coverage_equal),
        },
        "thresholds": {
            "logloss_material_abs": LOGLOSS_MATERIAL_ABS,
            "majority_folds": MAJORITY_FOLDS,
            "segment_min_n": SEGMENT_MIN_N,
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# 輸入指紋 / 環境
# ════════════════════════════════════════════════════════════════════════════

def _sha256(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_rev(args: list[str]) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            pass
    # 固定預設值 → byte-identical 重跑（不使用 wall clock）
    return "2026-06-14T00:00:00Z"


def _round_recursive(obj):
    if isinstance(obj, float):
        return round(obj, FLOAT_ROUND)
    if isinstance(obj, dict):
        return {k: _round_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_recursive(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return round(float(obj), FLOAT_ROUND)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


# ════════════════════════════════════════════════════════════════════════════
# 研究主流程 → payload
# ════════════════════════════════════════════════════════════════════════════

def run_study(records: Sequence,
              scores_csv: Path = _SCORES_CSV,
              odds_csv: Path = _ODDS_CSV) -> dict:
    """執行完整研究，回傳確定性 JSON payload（不寫檔）。"""
    data = build_study_data(records)
    if len(data.y) == 0:
        raise ValueError("no eligible rows after data-contract filtering")
    folds = build_folds(data, N_SEGMENTS)
    if len(folds) < 3:
        raise ValueError(f"expected >=3 OOS folds, got {len(folds)}")
    leak = assert_no_leakage(data, folds)

    # pooled OOS 佈局
    oos_idx = np.concatenate([f.test_idx for f in folds])
    oos_dates = [data.dates[i] for i in oos_idx]
    oos_fold_id = [f.index for f in folds for _ in f.test_idx]
    y_oos = data.y[oos_idx]
    elo_oos = data.elo_prob[oos_idx]

    # 模型評估
    frozen = evaluate_model("frozen_baseline", predict_frozen_baseline, data, folds)
    calibrated = evaluate_model("calibrated_baseline", predict_calibrated_baseline, data, folds)
    reference = evaluate_model("simple_reference", predict_simple_reference, data, folds)
    candidate = evaluate_model("candidate_full", predict_candidate_full, data, folds)
    ablations = {
        g: evaluate_model(f"ablation_minus_{g}", make_ablation_predictor(g), data, folds)
        for g in FEATURE_GROUPS
    }

    # pooled 指標
    models_metrics = {
        "frozen_baseline": metrics_block(frozen.oos_pred, y_oos),
        "calibrated_baseline": metrics_block(calibrated.oos_pred, y_oos),
        "simple_reference": metrics_block(reference.oos_pred, y_oos),
        "candidate_full": metrics_block(candidate.oos_pred, y_oos),
    }
    for g, res in ablations.items():
        models_metrics[f"ablation_minus_{g}"] = metrics_block(res.oos_pred, y_oos)

    # 主要比較：candidate_full vs frozen_baseline
    primary_boot = block_bootstrap_brier_delta(
        frozen.oos_pred, candidate.oos_pred, y_oos, oos_dates, BOOTSTRAP_RESAMPLES, RANDOM_SEED)
    # 次要：calibration-only effect（calibrated vs frozen）
    calib_boot = block_bootstrap_brier_delta(
        frozen.oos_pred, calibrated.oos_pred, y_oos, oos_dates, BOOTSTRAP_RESAMPLES, RANDOM_SEED + 1)
    # candidate vs simple reference
    ref_boot = block_bootstrap_brier_delta(
        reference.oos_pred, candidate.oos_pred, y_oos, oos_dates, BOOTSTRAP_RESAMPLES, RANDOM_SEED + 2)

    # ablation：相對 candidate_full 的 Brier 變化（正 => 移除該組「變差」=> 該組有正面價值）
    cand_brier = models_metrics["candidate_full"]["brier"]
    ablation_summary = {}
    for g, res in ablations.items():
        abl_brier = models_metrics[f"ablation_minus_{g}"]["brier"]
        ablation_summary[g] = {
            "ablation_brier": abl_brier,
            "delta_vs_candidate": round(abl_brier - cand_brier, FLOAT_ROUND),
            "group_adds_value": bool(abl_brier > cand_brier),  # 移除後變差 => 該組有貢獻
        }

    # fold 改善（candidate vs frozen）
    fold_improved = [candidate.fold_brier[i] < frozen.fold_brier[i] for i in range(len(folds))]

    # segment 穩定度（candidate vs frozen）
    segments = segment_stability(frozen.oos_pred, candidate.oos_pred, y_oos,
                                 oos_dates, oos_fold_id, elo_oos)

    # 決策閘門
    gate = decide_gate(
        primary={}, boot=primary_boot,
        base_metrics=models_metrics["frozen_baseline"],
        cand_metrics=models_metrics["candidate_full"],
        fold_improved=fold_improved, segments=segments, leakage_free=leak["leakage_free"])

    classification = f"P203_PRED_EVIDENCE_{gate['classification']}"

    # 重複比賽鍵診斷（doubleheaders）
    key_counts: dict[tuple, int] = {}
    for r in records:
        k = (getattr(r, "game_date", None), getattr(r, "away_team", None), getattr(r, "home_team", None))
        key_counts[k] = key_counts.get(k, 0) + 1
    dup_keys = sum(c for c in key_counts.values() if c > 1)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": "P203-PRED-EVIDENCE",
        "task_type": "IMPLEMENTATION_RESEARCH",
        "generated_at": _generated_at(),
        "final_classification": classification,
        "verdict": gate["classification"],
        "non_actions": [
            "research evidence only; NOT production model promotion",
            "no model/champion/registry/controlled_apply mutation",
            "no recommendation/evaluator mutation",
            "no MLB/StatsAPI endpoint or network call",
            "no live/historical data acquisition",
            "no provider unlock; live transport remains HOLD",
        ],
        "environment": {
            "repo": _git_rev(["rev-parse", "--show-toplevel"]),
            "branch": _git_rev(["rev-parse", "--abbrev-ref", "HEAD"]),
            "head": _git_rev(["rev-parse", "HEAD"]),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "random_seed": RANDOM_SEED,
        },
        "data_contract": {
            "input_loader": "data.mlb_data_loader.load_mlb_records()",
            "scores_csv": str(scores_csv),
            "odds_csv": str(odds_csv),
            "scores_csv_sha256": _sha256(scores_csv),
            "odds_csv_sha256": _sha256(odds_csv),
            "data_source_tag": "mlb_2025_retrosheet",
            "raw_row_count": data.raw_count,
            "eligible_row_count": int(len(data.y)),
            "unique_game_ids": len(set(data.game_ids)),
            "duplicate_date_team_key_rows": dup_keys,
            "duplicate_handling": "canonical unit = game_id; rows sharing (date,away,home) are "
                                  "doubleheaders kept as distinct games (no dedup)",
            "date_range": [data.unique_dates[0], data.unique_dates[-1]],
            "unique_dates": len(data.unique_dates),
            "target_field": "actual_home_win",
            "target_meaning": "1 if home team final score > away team final score, else 0",
            "home_win_base_rate": round(float(np.mean(data.y)), FLOAT_ROUND),
            "frozen_baseline_source": "pre-game Elo win probability 1/(1+10^((away_elo-home_elo)/400))",
            "prediction_time_evidence": "all features are pre-game rolling state computed by the loader "
                                        "with strict look-ahead isolation (Elo/rolling stats updated only "
                                        "after each game); features for a game use only prior-game outcomes",
            "available_pregame_features": list(ALL_FEATURES),
            "excluded_predictive_fields": EXCLUDED_PREDICTIVE_FIELDS,
            "missing_value_handling": "rows with any non-finite feature, non-binary target, or unparseable "
                                      "date are excluded and counted",
            "excluded_row_count": len(data.excluded_rows),
            "excluded_rows_sample": data.excluded_rows[:20],
            "random_seed": RANDOM_SEED,
        },
        "walk_forward_design": {
            "scheme": "expanding-window chronological, date-disjoint segments",
            "n_segments": N_SEGMENTS,
            "n_oos_folds": len(folds),
            "primary_metric": "out-of-sample Brier score",
            "secondary_metrics": ["log_loss", "ECE(10 fixed bins)", "calibration intercept/slope", "coverage"],
            "folds": [
                {
                    "fold": f.index,
                    "train_n": int(len(f.train_idx)),
                    "test_n": int(len(f.test_idx)),
                    "train_date_range": list(f.train_dates),
                    "test_date_range": list(f.test_dates),
                }
                for f in folds
            ],
            "pooled_oos_n": int(len(y_oos)),
        },
        "leakage_controls": leak,
        "feature_groups": FEATURE_GROUPS,
        "calibration": {
            "primary_method": "Platt/logistic calibration (sigmoid(a+b*logit(p)))",
            "fit_rule": "calibrator fitted only on past (training-fold) rows; candidate uses an inner "
                        "past-only date split (last 20% of training dates) for calibration",
            "hyperparameters": {"lr_l2": LR_L2, "platt_l2": PLATT_L2,
                                "irls_max_iter": IRLS_MAX_ITER, "inner_calib_fraction": INNER_CALIB_FRACTION},
        },
        "model_metrics_pooled_oos": models_metrics,
        "comparisons": {
            "candidate_full_vs_frozen_baseline": primary_boot,
            "calibrated_baseline_vs_frozen_baseline": calib_boot,
            "candidate_full_vs_simple_reference": ref_boot,
        },
        "fold_level": {
            "frozen_baseline_brier": [round(x, FLOAT_ROUND) for x in frozen.fold_brier],
            "candidate_full_brier": [round(x, FLOAT_ROUND) for x in candidate.fold_brier],
            "candidate_improved_fold": fold_improved,
            "n_folds_candidate_improved": sum(1 for x in fold_improved if x),
        },
        "ablation_results": ablation_summary,
        "segment_stability": segments,
        "decision_gate": gate,
        "limitations": [
            "Features are crude proxies (rolling run-rate-based wOBA/FIP, win-rate RSI), not true "
            "game-specific point-in-time pitcher/lineup data.",
            "market_home_prob (closing line) is excluded as a predictor due to post-season scrape "
            "provenance; this study cannot speak to market-informed models.",
            "A null/inconclusive result reflects the proxy-feature ceiling, not necessarily a model "
            "implementation limit; it cannot by itself distinguish model limitation from data limitation.",
            "Single 2025 season; no cross-season generalisation tested.",
            "Calibration uses a single primary method (Platt); other calibrators not adopted as primary.",
        ],
        "next_step_options": {
            "if_positive": "package evidence (separate authorization); NO model/recommendation promotion; "
                           "NO live implementation",
            "if_negative": "package evidence; do not promote candidate; next task should diagnose the "
                           "binding data/model constraint; NO live implementation",
            "if_inconclusive": "package evidence; do not promote candidate; next task must narrow uncertainty "
                               "without relaxing leakage controls; NO live implementation",
        },
    }
    return _round_recursive(payload)


# ════════════════════════════════════════════════════════════════════════════
# Markdown 報告
# ════════════════════════════════════════════════════════════════════════════

def render_markdown(payload: dict) -> str:
    dc = payload["data_contract"]
    wf = payload["walk_forward_design"]
    mm = payload["model_metrics_pooled_oos"]
    comp = payload["comparisons"]
    gate = payload["decision_gate"]
    L: list[str] = []
    a = L.append

    a(f"# P203 Prediction Evidence Study — {payload['verdict']}")
    a("")
    a(f"- **Final classification:** `{payload['final_classification']}`")
    a(f"- **Task:** {payload['task_id']} ({payload['task_type']})")
    a(f"- **Generated at:** {payload['generated_at']}")
    a(f"- **HEAD:** `{payload['environment']['head']}` ({payload['environment']['branch']})")
    a("")

    a("## 1. Executive Verdict")
    a("")
    pb = comp["candidate_full_vs_frozen_baseline"]
    a(f"Primary comparison — **candidate_full vs frozen Elo baseline** (pooled OOS, "
      f"n={wf['pooled_oos_n']}):")
    a("")
    a(f"- Brier improvement (baseline − candidate) point estimate: **{pb['brier_improvement_point']}** "
      f"(95% CI [{pb['ci95_low']}, {pb['ci95_high']}], {pb['n_resamples']} block-bootstrap resamples).")
    a(f"- Frozen baseline Brier = {mm['frozen_baseline']['brier']}; "
      f"candidate_full Brier = {mm['candidate_full']['brier']}.")
    a(f"- Folds where candidate improved: {payload['fold_level']['n_folds_candidate_improved']}"
      f"/{wf['n_oos_folds']}.")
    a(f"- **Verdict: `{payload['verdict']}`.** Positive only if the 95% CI lower bound exceeds 0, "
      f"log loss does not materially worsen, a majority of folds improve, and the gain is not driven "
      f"by a single small segment.")
    a("")

    a("## 2. Scope and Non-Actions")
    a("")
    for s in payload["non_actions"]:
        a(f"- {s}")
    a("")

    a("## 3. Data Contract")
    a("")
    a(f"- Loader: `{dc['input_loader']}`; data_source tag `{dc['data_source_tag']}`.")
    a(f"- Raw rows: {dc['raw_row_count']}; eligible rows: {dc['eligible_row_count']}; "
      f"unique game_ids: {dc['unique_game_ids']}; excluded rows: {dc['excluded_row_count']}.")
    a(f"- Duplicate (date,away,home) rows: {dc['duplicate_date_team_key_rows']} — {dc['duplicate_handling']}.")
    a(f"- Date range: {dc['date_range'][0]} → {dc['date_range'][1]} ({dc['unique_dates']} unique dates).")
    a(f"- Target: `{dc['target_field']}` — {dc['target_meaning']}; home-win base rate "
      f"{dc['home_win_base_rate']}.")
    a(f"- Frozen baseline: {dc['frozen_baseline_source']}.")
    a(f"- Input fingerprints: scores `{dc['scores_csv_sha256']}`; odds `{dc['odds_csv_sha256']}`.")
    a("")
    a("Excluded predictive fields (leakage risk / post-game):")
    a("")
    for k, v in dc["excluded_predictive_fields"].items():
        a(f"- `{k}` — {v}")
    a("")

    a("## 4. Leakage Controls")
    a("")
    lc = payload["leakage_controls"]
    a(f"- Structural check `leakage_free` = **{lc['leakage_free']}** over {lc['n_folds']} folds.")
    a(f"- All train dates strictly before test fold: {lc['all_train_before_test']}; "
      f"no train/test index overlap: {lc['no_index_overlap']}; test folds disjoint: "
      f"{lc['test_folds_disjoint']}.")
    a(f"- {dc['prediction_time_evidence']}.")
    a(f"- Missing-value handling: {dc['missing_value_handling']}.")
    a("")

    a("## 5. Frozen Baseline")
    a("")
    fb = mm["frozen_baseline"]
    a(f"- Pre-game Elo win probability, no fitting. Brier {fb['brier']}, log loss {fb['log_loss']}, "
      f"ECE {fb['ece']}, calibration intercept/slope {fb['calibration_intercept']}/{fb['calibration_slope']}.")
    a("")

    a("## 6. Walk-Forward Design")
    a("")
    a(f"- {wf['scheme']}; {wf['n_segments']} segments → {wf['n_oos_folds']} OOS folds; "
      f"primary metric {wf['primary_metric']}.")
    a("")
    a("| Fold | Train n | Test n | Train dates | Test dates |")
    a("|---|---|---|---|---|")
    for f in wf["folds"]:
        a(f"| {f['fold']} | {f['train_n']} | {f['test_n']} | "
          f"{f['train_date_range'][0]}→{f['train_date_range'][1]} | "
          f"{f['test_date_range'][0]}→{f['test_date_range'][1]} |")
    a("")

    a("## 7. Calibration Result")
    a("")
    cal = payload["calibration"]
    cb = comp["calibrated_baseline_vs_frozen_baseline"]
    a(f"- Method: {cal['primary_method']}; {cal['fit_rule']}.")
    a(f"- Calibrated baseline Brier {mm['calibrated_baseline']['brier']} vs frozen "
      f"{mm['frozen_baseline']['brier']}; improvement {cb['brier_improvement_point']} "
      f"(95% CI [{cb['ci95_low']}, {cb['ci95_high']}]).")
    a(f"- Calibrated baseline ECE {mm['calibrated_baseline']['ece']} "
      f"(frozen {mm['frozen_baseline']['ece']}).")
    a("")

    a("## 8. Feature Groups")
    a("")
    for g, fs in payload["feature_groups"].items():
        a(f"- **{g}**: {', '.join(fs)}")
    a("")

    a("## 9. Ablation Results")
    a("")
    a("Delta vs candidate_full Brier (positive => removing the group worsens => group adds value):")
    a("")
    a("| Group removed | Ablation Brier | Δ vs candidate | Group adds value |")
    a("|---|---|---|---|")
    for g, v in payload["ablation_results"].items():
        a(f"| {g} | {v['ablation_brier']} | {v['delta_vs_candidate']} | {v['group_adds_value']} |")
    a("")

    a("## 10. Reference Model Comparison")
    a("")
    rb = comp["candidate_full_vs_simple_reference"]
    a(f"- Simple reference (past-only home-win climatology) Brier {mm['simple_reference']['brier']}.")
    a(f"- Candidate_full vs reference Brier improvement {rb['brier_improvement_point']} "
      f"(95% CI [{rb['ci95_low']}, {rb['ci95_high']}]).")
    a("")

    a("## 11. Segment Stability")
    a("")
    seg = payload["segment_stability"]
    a("By prob band (frozen baseline prob):")
    a("")
    a("| Band | n | Baseline Brier | Candidate Brier | Δ improvement | Insufficient |")
    a("|---|---|---|---|---|---|")
    for k, v in seg["by_prob_band"].items():
        if v.get("n", 0) == 0:
            a(f"| {k} | 0 | — | — | — | True |")
        else:
            a(f"| {k} | {v['n']} | {v['baseline_brier']} | {v['candidate_brier']} | "
              f"{v['brier_improvement']} | {v['insufficient']} |")
    a("")
    a("By fold:")
    a("")
    a("| Fold | n | Baseline Brier | Candidate Brier | Δ improvement |")
    a("|---|---|---|---|---|")
    for k, v in seg["by_fold"].items():
        a(f"| {k} | {v['n']} | {v['baseline_brier']} | {v['candidate_brier']} | {v['brier_improvement']} |")
    a("")

    a("## 12. Statistical Uncertainty")
    a("")
    a(f"- Paired block bootstrap by game-date, {pb['n_resamples']} resamples, fixed seed "
      f"{payload['environment']['random_seed']}, {pb['n_blocks']} date blocks.")
    a(f"- {pb['definition']}.")
    a(f"- Primary 95% CI for Brier improvement: [{pb['ci95_low']}, {pb['ci95_high']}]; "
      f"lower bound above zero: {pb['ci_lower_above_zero']}.")
    a("- Significance is **not** claimed from a point estimate alone.")
    a("")

    a("## 13. Success/Failure Gate")
    a("")
    a(f"- **Classification: {gate['classification']}.**")
    a("")
    a("| Criterion | Value |")
    a("|---|---|")
    for k, v in gate["criteria"].items():
        a(f"| {k} | {v} |")
    a("")
    a(f"- Thresholds: log-loss material abs {gate['thresholds']['logloss_material_abs']}, "
      f"majority folds {gate['thresholds']['majority_folds']}, segment min n "
      f"{gate['thresholds']['segment_min_n']}.")
    a("")

    a("## 14. Limitations")
    a("")
    for s in payload["limitations"]:
        a(f"- [Inferred] {s}")
    a("")

    a("## 15. Recommended Next Step")
    a("")
    verdict = payload["verdict"]
    key = {"POSITIVE": "if_positive", "NEGATIVE": "if_negative", "INCONCLUSIVE": "if_inconclusive"}[verdict]
    a(f"- {payload['next_step_options'][key]}")
    a("- Packaging (branch/commit/PR) is a separately authorized action; this study does not self-authorize it.")
    a("- Live transport remains HOLD; model/recommendation promotion and live implementation are NOT authorized.")
    a("")

    a("## 16. Required Completion Check")
    a("")
    a(f"- Eligible sample: {dc['eligible_row_count']} games (raw {dc['raw_row_count']}), "
      f"data_source `{dc['data_source_tag']}`.")
    a(f"- OOS folds: {wf['n_oos_folds']}; pooled OOS n: {wf['pooled_oos_n']}.")
    a(f"- Leakage-free: {payload['leakage_controls']['leakage_free']}.")
    a(f"- Primary Brier improvement: {pb['brier_improvement_point']} "
      f"(95% CI [{pb['ci95_low']}, {pb['ci95_high']}]).")
    a(f"- Final classification: `{payload['final_classification']}`.")
    a("- Network/API/DB/runtime/production mutations: NONE.")
    a("- Live transport: HOLD. Track B: not sent.")
    a("")
    return "\n".join(L) + "\n"


# ════════════════════════════════════════════════════════════════════════════
# 原子寫檔 / CLI
# ════════════════════════════════════════════════════════════════════════════

def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def dumps_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P203 leakage-safe prediction evidence study")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="output JSON path")
    parser.add_argument("--md", type=Path, default=DEFAULT_MD, help="output Markdown path")
    parser.add_argument("--scores-csv", type=Path, default=_SCORES_CSV)
    parser.add_argument("--odds-csv", type=Path, default=_ODDS_CSV)
    parser.add_argument("--print-only", action="store_true", help="print verdict, do not write files")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)

    from data.mlb_data_loader import load_mlb_records
    records = load_mlb_records(scores_csv=args.scores_csv, odds_csv=args.odds_csv)

    payload = run_study(records, scores_csv=args.scores_csv, odds_csv=args.odds_csv)
    json_text = dumps_json(payload)
    md_text = render_markdown(payload)

    if args.print_only:
        print(payload["final_classification"])
        return 0

    _atomic_write(args.json, json_text)
    _atomic_write(args.md, md_text)
    print(f"[P203] wrote {args.json} and {args.md}")
    print(f"[P203] final_classification = {payload['final_classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
