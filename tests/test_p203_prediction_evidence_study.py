"""Tests for P203 leakage-safe prediction evidence study.

純本地、無網路、無 DB、無檔案副作用（除明確的 tmp_path 輸出測試）。
使用 synthetic GameRecord-like 物件（SimpleNamespace），不依賴真實 CSV。
"""
from __future__ import annotations

import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import p203_prediction_evidence_study as p203


# ════════════════════════════════════════════════════════════════════════════
# Synthetic data
# ════════════════════════════════════════════════════════════════════════════

def _make_records(n_dates: int = 60, games_per_date: int = 4, seed: int = 7):
    """產生確定性、可學習的 synthetic 賽前資料（依 elo 差 + 雜訊決定結果）。"""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(20)]
    base_date = np.datetime64("2025-04-01")
    elo = {t: 1500.0 for t in teams}
    records = []
    gidx = 0
    for d in range(n_dates):
        day = (base_date + np.timedelta64(d, "D")).astype(str)
        order = rng.permutation(len(teams))
        for g in range(games_per_date):
            h = teams[order[(2 * g) % len(teams)]]
            a = teams[order[(2 * g + 1) % len(teams)]]
            he, ae = elo[h], elo[a]
            p_home = 1.0 / (1.0 + 10.0 ** ((ae - he) / 400.0))
            outcome = 1 if rng.random() < p_home else 0
            records.append(SimpleNamespace(
                game_id=f"SYN_{gidx:04d}_{day}_{a}_{h}",
                game_date=day,
                home_team=h, away_team=a,
                home_elo=round(he, 1), away_elo=round(ae, 1),
                home_woba=round(0.300 + rng.random() * 0.06, 3),
                away_woba=round(0.300 + rng.random() * 0.06, 3),
                home_fip=round(3.5 + rng.random() * 1.5, 2),
                away_fip=round(3.5 + rng.random() * 1.5, 2),
                home_rsi=round(40 + rng.random() * 40, 1),
                away_rsi=round(40 + rng.random() * 40, 1),
                home_rest_days=int(rng.integers(0, 4)),
                away_rest_days=int(rng.integers(0, 4)),
                market_home_prob=round(p_home, 4),
                ou_line=7.5,
                actual_home_score=5 if outcome else 3,
                actual_away_score=3 if outcome else 5,
                actual_home_win=outcome,
                actual_total_runs=8,
                data_source="mlb_2025_retrosheet",
            ))
            # 賽後更新 elo
            k = 20.0
            exp = p_home
            if outcome:
                elo[h] += k * (1 - exp); elo[a] -= k * (1 - exp)
            else:
                elo[h] -= k * exp; elo[a] += k * exp
            gidx += 1
    return records


@pytest.fixture(scope="module")
def synth_records():
    return _make_records()


@pytest.fixture(scope="module")
def synth_data(synth_records):
    return p203.build_study_data(synth_records)


@pytest.fixture(scope="module")
def synth_folds(synth_data):
    return p203.build_folds(synth_data, p203.N_SEGMENTS)


# ════════════════════════════════════════════════════════════════════════════
# Chronology / leakage
# ════════════════════════════════════════════════════════════════════════════

def test_chronological_fold_ordering(synth_data, synth_folds):
    assert len(synth_folds) >= 3
    for f in synth_folds:
        max_train = max(synth_data.dates[j] for j in f.train_idx)
        min_test = min(synth_data.dates[j] for j in f.test_idx)
        assert max_train < min_test, f"fold {f.index} train not strictly before test"


def test_no_train_test_overlap(synth_data, synth_folds):
    for f in synth_folds:
        assert not (set(f.train_idx.tolist()) & set(f.test_idx.tolist()))


def test_test_folds_disjoint(synth_folds):
    seen: set[int] = set()
    for f in synth_folds:
        ts = set(int(j) for j in f.test_idx)
        assert not (ts & seen)
        seen |= ts


def test_assert_no_leakage_passes_on_valid_folds(synth_data, synth_folds):
    checks = p203.assert_no_leakage(synth_data, synth_folds)
    assert checks["leakage_free"] is True
    assert checks["violations"] == []


def test_future_row_leakage_is_rejected(synth_data):
    """手工構造一個訓練含未來列的壞 fold → 必須被偵測。"""
    # 找出時間上較晚的列當「訓練」、較早的列當「測試」=> 違反時序
    n = len(synth_data.dates)
    late = np.array([n - 1], dtype=int)
    early = np.array([0], dtype=int)
    bad = p203.Fold(index=0, train_idx=late, test_idx=early,
                    train_dates=(synth_data.dates[-1], synth_data.dates[-1]),
                    test_dates=(synth_data.dates[0], synth_data.dates[0]))
    checks = p203.assert_no_leakage(synth_data, [bad])
    assert checks["leakage_free"] is False
    assert checks["all_train_before_test"] is False


def test_calibration_fitted_on_past_only(synth_data, synth_folds):
    """改動 test fold 的結果不得改變校準後的預測（證明校準只用訓練資料）。"""
    fold = synth_folds[0]
    pred_before = p203.predict_calibrated_baseline(synth_data, fold)
    mutated_y = synth_data.y.copy()
    for j in fold.test_idx:
        mutated_y[j] = 1 - mutated_y[j]
    mutated = p203.StudyData(
        game_ids=synth_data.game_ids, dates=synth_data.dates, X=synth_data.X,
        elo_prob=synth_data.elo_prob, y=mutated_y, feature_names=synth_data.feature_names,
        raw_count=synth_data.raw_count, excluded_rows=synth_data.excluded_rows,
        unique_dates=synth_data.unique_dates)
    pred_after = p203.predict_calibrated_baseline(mutated, fold)
    assert np.allclose(pred_before, pred_after)


def test_candidate_model_ignores_test_outcomes(synth_data, synth_folds):
    """candidate 模型預測不得隨 test fold 結果改變（無未來洩漏）。"""
    fold = synth_folds[1]
    before = p203.predict_candidate_full(synth_data, fold)
    mutated_y = synth_data.y.copy()
    for j in fold.test_idx:
        mutated_y[j] = 1 - mutated_y[j]
    mutated = p203.StudyData(
        game_ids=synth_data.game_ids, dates=synth_data.dates, X=synth_data.X,
        elo_prob=synth_data.elo_prob, y=mutated_y, feature_names=synth_data.feature_names,
        raw_count=synth_data.raw_count, excluded_rows=synth_data.excluded_rows,
        unique_dates=synth_data.unique_dates)
    after = p203.predict_candidate_full(mutated, fold)
    assert np.allclose(before, after)


# ════════════════════════════════════════════════════════════════════════════
# Data contract / exclusions
# ════════════════════════════════════════════════════════════════════════════

def test_duplicate_game_handling(synth_records):
    """同 (date,away,home) 但不同 game_id（doubleheader）皆保留為相異列。"""
    base = synth_records[0]
    dup = SimpleNamespace(**{**vars(base), "game_id": base.game_id + "_DH2"})
    data = p203.build_study_data(list(synth_records) + [dup])
    assert len(set(data.game_ids)) == len(data.game_ids)  # game_id 仍唯一
    assert data.game_ids.count  # list
    assert (base.game_id in data.game_ids) and (dup.game_id in data.game_ids)


def test_non_binary_target_excluded():
    recs = _make_records(n_dates=10, games_per_date=2)
    bad = SimpleNamespace(**{**vars(recs[0]), "game_id": "BAD_TARGET", "actual_home_win": None})
    data = p203.build_study_data(recs + [bad])
    assert "BAD_TARGET" not in data.game_ids
    assert any(e["reason"] == "target_not_binary" for e in data.excluded_rows)


def test_non_finite_feature_excluded():
    recs = _make_records(n_dates=10, games_per_date=2)
    bad = SimpleNamespace(**{**vars(recs[0]), "game_id": "BAD_FEAT", "home_woba": float("nan")})
    data = p203.build_study_data(recs + [bad])
    assert "BAD_FEAT" not in data.game_ids
    assert any(e["reason"] == "non_finite_feature" for e in data.excluded_rows)


def test_unparseable_date_excluded():
    recs = _make_records(n_dates=10, games_per_date=2)
    bad = SimpleNamespace(**{**vars(recs[0]), "game_id": "BAD_DATE", "game_date": "not-a-date"})
    data = p203.build_study_data(recs + [bad])
    assert "BAD_DATE" not in data.game_ids
    assert any(e["reason"] == "unparseable_date" for e in data.excluded_rows)


def test_postgame_fields_never_features():
    """賽後/收盤欄位必須不在預測特徵內，且明確列於排除清單。"""
    for forbidden in ("actual_home_win", "actual_home_score", "actual_total_runs",
                      "market_home_prob", "ou_line"):
        assert forbidden not in p203.ALL_FEATURES
        assert forbidden in p203.EXCLUDED_PREDICTIVE_FIELDS


def test_feature_group_membership_freeze():
    flat = [f for fs in p203.FEATURE_GROUPS.values() for f in fs]
    assert flat == p203.ALL_FEATURES
    assert len(set(flat)) == len(flat)  # 無重複


def test_ablation_drops_exactly_one_group(synth_data, synth_folds):
    for group, feats in p203.FEATURE_GROUPS.items():
        pred = p203.make_ablation_predictor(group)
        # 結構檢查：產生有效機率向量且長度對齊
        out = pred(synth_data, synth_folds[0])
        assert out.shape == (len(synth_folds[0].test_idx),)
        assert np.all((out >= 0) & (out <= 1))


# ════════════════════════════════════════════════════════════════════════════
# Metrics
# ════════════════════════════════════════════════════════════════════════════

def test_brier_known_value():
    p = np.array([1.0, 0.0, 0.5])
    y = np.array([1.0, 0.0, 1.0])
    # (0 + 0 + 0.25)/3
    assert math.isclose(p203.brier_score(p, y), 0.25 / 3, rel_tol=1e-12)


def test_logloss_known_value():
    p = np.array([0.5, 0.5])
    y = np.array([1.0, 0.0])
    assert math.isclose(p203.log_loss(p, y), -math.log(0.5), rel_tol=1e-9)


def test_logloss_clips_extremes():
    p = np.array([0.0, 1.0])
    y = np.array([1.0, 0.0])
    val = p203.log_loss(p, y)  # 不應為 inf
    assert math.isfinite(val) and val > 0


def test_perfect_brier_zero():
    p = np.array([1.0, 0.0, 1.0])
    y = np.array([1.0, 0.0, 1.0])
    assert p203.brier_score(p, y) == 0.0


def test_ece_perfect_calibration_low():
    rng = np.random.default_rng(0)
    p = rng.random(5000)
    y = (rng.random(5000) < p).astype(float)
    assert p203.expected_calibration_error(p, y) < 0.05


def test_logistic_recovers_sign():
    rng = np.random.default_rng(1)
    x = rng.normal(size=400)
    y = (rng.random(400) < p203._sigmoid(2.0 * x)).astype(float)
    X = np.hstack([np.ones((400, 1)), x.reshape(-1, 1)])
    w = p203.fit_logistic(X, y, l2=1e-6)
    assert w[1] > 0  # 正斜率


def test_platt_identity_on_calibrated_scores():
    rng = np.random.default_rng(2)
    p = rng.random(3000)
    y = (rng.random(3000) < p).astype(float)
    a, b = p203.fit_platt(p203._logit(p), y)
    cal = p203.apply_platt(p203._logit(p), a, b)
    # 已校準 → 校準後 Brier 不應比原始差太多
    assert p203.brier_score(cal, y) <= p203.brier_score(p, y) + 0.01


# ════════════════════════════════════════════════════════════════════════════
# Gate logic（POSITIVE / NEGATIVE / INCONCLUSIVE）
# ════════════════════════════════════════════════════════════════════════════

def _seg_all_improve():
    return {
        "by_prob_band": {
            "a": {"n": 500, "brier_improvement": 0.01, "insufficient": False},
            "b": {"n": 500, "brier_improvement": 0.01, "insufficient": False},
            "c": {"n": 500, "brier_improvement": 0.01, "insufficient": False},
        },
        "by_month": {"m1": {"n": 750, "brier_improvement": 0.01, "insufficient": False},
                     "m2": {"n": 750, "brier_improvement": 0.01, "insufficient": False}},
        "by_fold": {},
    }


def test_gate_positive():
    boot = {"brier_improvement_point": 0.01, "ci_lower_above_zero": True, "ci95_high": 0.02}
    base = {"log_loss": 0.69, "n": 1500}
    cand = {"log_loss": 0.68, "n": 1500}
    gate = p203.decide_gate({}, boot, base, cand,
                            fold_improved=[True, True, True, False, True],
                            segments=_seg_all_improve(), leakage_free=True)
    assert gate["classification"] == "POSITIVE"


def test_gate_negative_material_worse():
    boot = {"brier_improvement_point": -0.01, "ci_lower_above_zero": False, "ci95_high": -0.002}
    base = {"log_loss": 0.69, "n": 1500}
    cand = {"log_loss": 0.70, "n": 1500}
    gate = p203.decide_gate({}, boot, base, cand,
                            fold_improved=[False, False, False, False, False],
                            segments=_seg_all_improve(), leakage_free=True)
    assert gate["classification"] == "NEGATIVE"


def test_gate_inconclusive_ci_straddles_zero():
    boot = {"brier_improvement_point": 0.003, "ci_lower_above_zero": False, "ci95_high": 0.01}
    base = {"log_loss": 0.69, "n": 1500}
    cand = {"log_loss": 0.689, "n": 1500}
    gate = p203.decide_gate({}, boot, base, cand,
                            fold_improved=[True, False, True, False, False],
                            segments=_seg_all_improve(), leakage_free=True)
    assert gate["classification"] == "INCONCLUSIVE"


def test_gate_positive_requires_leakage_free():
    boot = {"brier_improvement_point": 0.01, "ci_lower_above_zero": True, "ci95_high": 0.02}
    base = {"log_loss": 0.69, "n": 1500}
    cand = {"log_loss": 0.68, "n": 1500}
    gate = p203.decide_gate({}, boot, base, cand,
                            fold_improved=[True, True, True, True, True],
                            segments=_seg_all_improve(), leakage_free=False)
    assert gate["classification"] != "POSITIVE"


# ════════════════════════════════════════════════════════════════════════════
# End-to-end study / schema / determinism / no side effects
# ════════════════════════════════════════════════════════════════════════════

def test_run_study_schema(synth_records):
    payload = p203.run_study(synth_records)
    required = {
        "schema_version", "task_id", "task_type", "generated_at", "final_classification",
        "verdict", "data_contract", "walk_forward_design", "leakage_controls",
        "feature_groups", "calibration", "model_metrics_pooled_oos", "comparisons",
        "fold_level", "ablation_results", "segment_stability", "decision_gate",
        "limitations", "next_step_options", "environment",
    }
    assert required.issubset(payload.keys())
    assert payload["final_classification"].startswith("P203_PRED_EVIDENCE_")
    assert payload["schema_version"] == p203.SCHEMA_VERSION


def test_identical_comparison_row_set(synth_records):
    """所有模型在相同 pooled OOS 列集評估 → n 相等。"""
    payload = p203.run_study(synth_records)
    mm = payload["model_metrics_pooled_oos"]
    ns = {m["n"] for m in mm.values()}
    assert len(ns) == 1
    assert ns.pop() == payload["walk_forward_design"]["pooled_oos_n"]


def test_deterministic_payload(synth_records):
    p1 = p203.run_study(synth_records)
    p2 = p203.run_study(synth_records)
    assert p203.dumps_json(p1) == p203.dumps_json(p2)


def test_deterministic_markdown(synth_records):
    p1 = p203.run_study(synth_records)
    md1 = p203.render_markdown(p1)
    md2 = p203.render_markdown(p203.run_study(synth_records))
    assert md1 == md2
    # 16 個必備章節
    for i in range(1, 17):
        assert f"## {i}." in md1


def test_json_is_valid_and_roundtrips(synth_records):
    payload = p203.run_study(synth_records)
    text = p203.dumps_json(payload)
    assert json.loads(text)["task_id"] == "P203-PRED-EVIDENCE"


def test_run_study_writes_no_files(synth_records, tmp_path, monkeypatch):
    """run_study 不得寫任何檔案（純計算）。"""
    monkeypatch.chdir(tmp_path)
    before = set(p.name for p in tmp_path.iterdir())
    p203.run_study(synth_records)
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after


def test_atomic_write_outputs(synth_records, tmp_path):
    payload = p203.run_study(synth_records)
    jpath = tmp_path / "out.json"
    mpath = tmp_path / "out.md"
    p203._atomic_write(jpath, p203.dumps_json(payload))
    p203._atomic_write(mpath, p203.render_markdown(payload))
    assert json.loads(jpath.read_text())["verdict"] in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}
    assert mpath.read_text().startswith("# P203 Prediction Evidence Study")


def test_no_network_or_db_imports():
    """模組不得 import 網路/DB 套件（靜態檢查）。"""
    import ast
    from pathlib import Path
    src = Path(p203.__file__).read_text()
    tree = ast.parse(src)
    forbidden = {"socket", "requests", "urllib", "http", "sqlite3", "telethon",
                 "psycopg2", "pymysql", "httpx", "aiohttp"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert n.name.split(".")[0] not in forbidden, f"forbidden import {n.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in forbidden, f"forbidden import-from {node.module}"


def test_generated_at_respects_source_date_epoch(synth_records, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    payload = p203.run_study(synth_records)
    assert payload["generated_at"] == "1970-01-01T00:00:00Z"
