"""P207-A 本機重訓 scorecard 測試（純標準庫；leakage / 決定性 / 指標正確性 / 真實資料煙霧）。"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from wbc_backend.recommendation import local_retrain_scorecard as lrs

ROOT = Path(__file__).resolve().parents[1]
REAL_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
REAL_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta"]


def _write_asplayed(path: Path, n_days: int = 40) -> None:
    """前一季暖身格式（含 home_win 欄）。確定性：主隊固定勝。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "away_team", "home_team", "home_win",
                    "status", "source_type"])
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 1) % len(TEAMS)]
            month, day = 1 + i // 28, 1 + i % 28
            w.writerow([f"2024-{month:02d}-{day:02d}", away, home,
                        i % 3 != 0 and 1 or 0, "Final", "synthetic"])


def _write_odds(path: Path, n_days: int = 60) -> None:
    """本季 odds 格式（由比分推導賽果 + Home/Away ML）。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Away", "Away Score", "Home", "Home Score",
                    "Status", "Home ML", "Away ML"])
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 2) % len(TEAMS)]
            hs, as_ = (5, 3) if i % 2 == 0 else (2, 4)   # 交替主客勝，無平手
            month, day = 4 + i // 28, 1 + i % 28
            w.writerow([f"2025-{month:02d}-{day:02d}", away, as_, home, hs,
                        "Final", "-120", "+110"])


@pytest.fixture()
def synthetic(tmp_path: Path):
    wu = tmp_path / "warmup.csv"
    ev = tmp_path / "eval.csv"
    _write_asplayed(wu)
    _write_odds(ev)
    return wu, ev


# ── 純函式單元 ───────────────────────────────────────────────────────────────
def test_metrics_hand_computed():
    m = lrs.metrics([0.5, 0.5], [1, 0])
    assert m["n"] == 2
    assert m["accuracy"] == pytest.approx(0.5)
    assert m["log_loss"] == pytest.approx(-math.log(0.5), rel=1e-9)
    assert m["brier_score"] == pytest.approx(0.25)
    assert m["calibration_error"] == pytest.approx(0.0, abs=1e-12)


def test_metrics_perfect_and_bounds():
    m = lrs.metrics([0.999999, 0.000001], [1, 0])
    assert m["accuracy"] == pytest.approx(1.0)
    assert 0.0 <= m["brier_score"] <= 1.0
    assert m["log_loss"] >= 0.0


def test_empty_metrics():
    m = lrs.metrics([], [])
    assert m["n"] == 0 and m["accuracy"] is None and m["brier_score"] is None


def test_confidence_band_boundaries():
    assert lrs.confidence_band(0.50) == "LOW"
    assert lrs.confidence_band(0.549) == "LOW"
    assert lrs.confidence_band(0.55) == "MEDIUM"
    assert lrs.confidence_band(0.649) == "MEDIUM"
    assert lrs.confidence_band(0.65) == "HIGH"
    assert lrs.confidence_band(0.40) == "MEDIUM"   # 客隊側 p_sel=0.60 → MEDIUM
    assert lrs.confidence_band(0.35) == "HIGH"     # 客隊側 p_sel=0.65 → HIGH（與 0.65 對稱）


def test_selected_side():
    assert lrs.selected_side(0.5) == "HOME"
    assert lrs.selected_side(0.7) == "HOME"
    assert lrs.selected_side(0.49) == "AWAY"


def test_american_to_prob():
    assert lrs.american_to_prob("-120") == pytest.approx(120 / 220)
    assert lrs.american_to_prob("+110") == pytest.approx(100 / 210)
    assert lrs.american_to_prob("") is None
    assert lrs.american_to_prob(None) is None


def test_platt_reduces_or_holds_train_logloss():
    # 建一組刻意 miscalibrated 的 raw logit，Platt 後 train logloss 不應變差
    fs = [(-2 + 0.05 * i) for i in range(80)]
    ys = [1 if lrs.sigmoid(1.7 * f - 0.3) > 0.5 else 0 for f in fs]
    A, B = lrs.fit_platt(fs, ys)
    raw = lrs.metrics([lrs.sigmoid(f) for f in fs], ys)["log_loss"]
    cal = lrs.metrics([lrs.sigmoid(A * f + B) for f in fs], ys)["log_loss"]
    assert cal <= raw + 1e-9


# ── 整合（合成資料）─────────────────────────────────────────────────────────
def test_leakage_train_strictly_before_test(synthetic):
    wu, ev = synthetic
    r = lrs.run_scorecard(wu, ev)
    assert r.split["train_period"][1] <= r.split["test_period"][0]
    assert r.split["train_rows"] > 0 and r.split["test_rows"] > 0


def test_probabilities_and_metrics_bounded(synthetic):
    wu, ev = synthetic
    r = lrs.run_scorecard(wu, ev)
    for pr in r.predictions:
        assert 0.0 <= pr["predicted_home_win_probability"] <= 1.0
        assert pr["selected_side"] in ("HOME", "AWAY")
        assert pr["confidence_band"] in ("LOW", "MEDIUM", "HIGH")
        assert pr["correct"] in (0, 1)
        assert pr["learning_guard_status"] == "LOCAL_HISTORICAL_BACKTEST_ONLY"
    for m in r.comparison:
        assert 0.0 <= m["accuracy"] <= 1.0
        assert 0.0 <= m["brier_score"] <= 1.0
        assert m["coverage"] == pytest.approx(1.0)


def test_baseline_is_constant_prior(synthetic):
    wu, ev = synthetic
    r = lrs.run_scorecard(wu, ev)
    base = [pr["predicted_home_win_probability"] for pr in r.predictions
            if pr["model_name"] == "baseline_fixed_prior"]
    assert base and len(set(base)) == 1
    assert base[0] == pytest.approx(round(r.train_home_win_prior, 6))


def test_all_four_models_present(synthetic):
    wu, ev = synthetic
    r = lrs.run_scorecard(wu, ev)
    names = {m["model_name"] for m in r.comparison}
    assert names == {"baseline_fixed_prior", "elo_like_rating",
                     "retrained_team_history_smooth", "calibrated_elo_recent_form"}


def test_deterministic_reproducible(synthetic):
    wu, ev = synthetic
    r1 = lrs.run_scorecard(wu, ev)
    r2 = lrs.run_scorecard(wu, ev)
    assert [m["brier_score"] for m in r1.comparison] == \
           [m["brier_score"] for m in r2.comparison]
    assert r1.platt == r2.platt
    assert r1.train_home_win_prior == r2.train_home_win_prior


def test_outcome_derived_from_scores_when_no_home_win_column(synthetic):
    _, ev = synthetic
    games = lrs.load_games(ev)
    assert games and all(g.home_win in (0, 1) for g in games)
    assert all(g.p_mkt is not None for g in games)   # ML present → market prob


def test_odds_absent_yields_status(tmp_path):
    # eval 檔無 ML 欄 → 市場參考不可得
    ev = tmp_path / "noodds.csv"
    with open(ev, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Away", "Away Score", "Home", "Home Score", "Status"])
        for i in range(60):
            hs, as_ = (5, 3) if i % 2 == 0 else (2, 4)
            w.writerow([f"2025-04-{1 + i % 28:02d}", TEAMS[(i + 2) % 4], as_,
                        TEAMS[i % 4], hs, "Final"])
    wu = tmp_path / "wu.csv"
    _write_asplayed(wu)
    r = lrs.run_scorecard(wu, ev)
    assert r.odds_metrics_status == "ODDS_NOT_AVAILABLE"
    assert r.market_reference is None


def test_write_reports_creates_five_files(synthetic, tmp_path):
    wu, ev = synthetic
    r = lrs.run_scorecard(wu, ev)
    out = tmp_path / "report"
    written = lrs.write_reports(r, out)
    names = {p.name for p in written}
    assert names == {
        "p207a_local_retrain_scorecard.md",
        "p207a_local_retrain_scorecard.json",
        "p207a_local_retrain_predictions.csv",
        "p207a_local_retrain_model_comparison.csv",
        "p207a_local_retrain_data_inventory.csv",
    }
    for p in written:
        assert p.exists() and p.stat().st_size > 0
    payload = json.loads((out / "p207a_local_retrain_scorecard.json").read_text(encoding="utf-8"))
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert "NO betting recommendation; NO EV/ROI/payout/Kelly/CLV claim" in payload["disclaimers"]


# ── 真實資料煙霧（存在才跑）──────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_real_data_smoke(tmp_path):
    r = lrs.run_scorecard(REAL_WARMUP, REAL_EVAL)
    assert r.eval_rows >= 2000              # 2025 全季量級
    assert r.split["train_rows"] + r.split["test_rows"] == r.eval_rows
    assert r.split["train_period"][1] <= r.split["test_period"][0]
    for m in r.comparison:
        assert 0.45 <= m["accuracy"] <= 0.65   # MLB 誠實可信區間
        assert 0.20 <= m["brier_score"] <= 0.30
    out = tmp_path / "report"
    written = lrs.write_reports(r, out)
    assert len(written) == 5
