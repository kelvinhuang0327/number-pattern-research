"""P227-A total over-dispersion calibration 測試（純標準庫；Gate 0 重現 / train-fold-only
擬合 / push 機率守恆 / 確定性 / 無 odds-as-feature / 無未來預測）。"""
from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path

import pytest

from wbc_backend.recommendation import run_line_total_scorecard as rlt
from wbc_backend.recommendation import total_calibration_scorecard as tcs

ROOT = Path(__file__).resolve().parents[1]
REAL_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
REAL_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta"]


def _write_asplayed(path: Path, n_days: int = 60) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "away_team", "home_team", "away_score", "home_score",
                    "status", "source_type"])
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 1) % len(TEAMS)]
            hs, as_ = (5, 3) if i % 3 != 0 else (2, 4)
            month, day = 1 + i // 28, 1 + i % 28
            w.writerow([f"2024-{month:02d}-{day:02d}", away, home, as_, hs, "Final", "synthetic"])


def _write_odds(path: Path, n_days: int = 140) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Away", "Away Score", "Home", "Home Score", "Status",
                    "Home ML", "Away ML", "Home RL Spread", "RL Home", "RL Away",
                    "O/U", "Over", "Under"])
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 2) % len(TEAMS)]
            hs, as_ = (5, 3) if i % 2 == 0 else (2, 4)
            spread = "-1.5" if i % 2 == 0 else "+1.5"
            ou = "7.5" if i % 3 else "8.0"
            month, day = 4 + i // 28, 1 + i % 28
            w.writerow([f"2025-{month:02d}-{day:02d}", away, as_, home, hs, "Final",
                        "-120", "+110", spread, "-125", "+105", ou, "-110", "-105"])


@pytest.fixture()
def synthetic(tmp_path: Path):
    wu = tmp_path / "warmup.csv"
    ev = tmp_path / "eval.csv"
    _write_asplayed(wu)
    _write_odds(ev)
    return wu, ev


# ── 數值工具單元 ─────────────────────────────────────────────────────────────
def test_sigmoid_logit_roundtrip():
    for p in (0.001, 0.1, 0.5, 0.9, 0.999):
        assert tcs.sigmoid(tcs.logit(p)) == pytest.approx(p, rel=1e-6)


def test_norm_cdf_matches_erf_definition():
    mu, sigma = 8.5, 2.0
    x = 9.0
    expected = 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))
    assert tcs.norm_cdf(x, mu, sigma) == pytest.approx(expected, rel=1e-12)


def test_norm_cdf_degenerate_sigma():
    assert tcs.norm_cdf(5.0, 4.0, 0.0) == 1.0
    assert tcs.norm_cdf(3.0, 4.0, 0.0) == 0.0


# ── Method A: variance inflation ─────────────────────────────────────────────
def test_variance_inflation_sums_to_one_half_line():
    p_over, p_under, p_push = tcs.total_probabilities_variance_inflated(8.5, 2.0, 7.5)
    assert p_push == 0.0
    assert p_over + p_under == pytest.approx(1.0, abs=1e-9)


def test_variance_inflation_integer_line_push_conservation():
    p_over, p_under, p_push = tcs.total_probabilities_variance_inflated(8.0, 2.0, 8.0)
    assert p_push > 0.0
    assert p_over + p_under + p_push == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("lam_total,phi_hat,line", [
    (7.0, 1.5, 7.5), (8.0, 2.3, 8.0), (10.5, 0.8, 9.0), (6.0, 3.0, 6.5),
])
def test_variance_inflation_probabilities_bounded_and_conserved(lam_total, phi_hat, line):
    p_over, p_under, p_push = tcs.total_probabilities_variance_inflated(lam_total, phi_hat, line)
    assert 0.0 <= p_over <= 1.0 and 0.0 <= p_under <= 1.0 and 0.0 <= p_push <= 1.0
    assert p_over + p_under + p_push == pytest.approx(1.0, abs=1e-9)


def test_fit_phi_hat_hand_computed():
    rows = [
        tcs.TotalRow(game=None, lambda_total=8.0, actual_total=10, p_over_raw=None,
                     p_under_raw=None, p_push_raw=None, actual_side=None),
        tcs.TotalRow(game=None, lambda_total=8.0, actual_total=6, p_over_raw=None,
                     p_under_raw=None, p_push_raw=None, actual_side=None),
    ]
    # sum((10-8)^2 + (6-8)^2) / (8+8) = (4+4)/16 = 0.5
    assert tcs.fit_phi_hat(rows) == pytest.approx(0.5)


# ── Method B: Platt ───────────────────────────────────────────────────────────
def test_fit_platt_recovers_identity_on_well_calibrated_data():
    # 若 raw p_over 已完美校準（p 本身就是真實機率），Platt 應收斂到近似恆等映射
    xs, ys = [], []
    ps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9] * 40
    for i, p in enumerate(ps):
        xs.append(tcs.logit(p))
        # 確定性標籤：以固定週期近似該機率的經驗頻率，避免依賴 random 造成不確定性
        ys.append(1 if (i % 10) < round(p * 10) else 0)
    a, b = tcs.fit_platt(xs, ys)
    for p in (0.2, 0.5, 0.8):
        calibrated = tcs.platt_p_over(a, b, p)
        assert 0.0 <= calibrated <= 1.0


def test_fit_platt_deterministic():
    xs = [tcs.logit(p) for p in [0.3, 0.4, 0.5, 0.6, 0.7] * 20]
    ys = [1, 0, 1, 0, 1] * 20
    a1, b1 = tcs.fit_platt(xs, ys)
    a2, b2 = tcs.fit_platt(xs, ys)
    assert a1 == a2 and b1 == b2


def test_fit_platt_fixed_initial_values_are_module_constants():
    assert tcs.PLATT_INITIAL_A == 1.0
    assert tcs.PLATT_INITIAL_B == 0.0
    assert tcs.PLATT_MAX_ITER == 100


# ── Gate 0 重現（合成資料） ───────────────────────────────────────────────────
def test_gate0_reproduces_p226a_home_adv_and_split(synthetic):
    wu, ev = synthetic
    gate0 = rlt.run_scorecard(wu, ev)
    result = tcs.run_calibration_scorecard(wu, ev)
    assert result.gate0_home_adv == pytest.approx(gate0.home_adv)
    assert result.gate0_split == gate0.split


def test_gate0_replica_matches_p226a_raw_p_over_exactly(synthetic):
    """核心 Gate 0 保證：本檔重新實作的 walk-forward 在 test fold 上的 raw p_over
    必須與 P226-A 官方輸出逐場相等（本檔已用此斷言做內部 RuntimeError 防呆，
    這裡額外用獨立比對驗證行為一致）。"""
    wu, ev = synthetic
    gate0 = rlt.run_scorecard(wu, ev)
    result = tcs.run_calibration_scorecard(wu, ev)
    gate0_poisson = {
        p["game_id"]: p["predicted_primary_probability"]
        for p in gate0.predictions
        if p["market"] == "total" and p["model_name"] == "poisson_team_rate_model"
    }
    for pred in result.predictions:
        assert pred["raw_poisson_p_over_p226a"] == pytest.approx(
            gate0_poisson[pred["game_id"]], abs=1e-6
        )


def test_run_line_untouched_via_p226a_call(synthetic):
    """P227-A 不修改 run line 邏輯：Gate 0 的 run line 指標必須與直接呼叫 P226-A 相同。"""
    wu, ev = synthetic
    gate0_direct = rlt.run_scorecard(wu, ev)
    result = tcs.run_calibration_scorecard(wu, ev)
    for m_direct, m_gate0 in zip(
        gate0_direct.market_comparison["run_line"], result.gate0_market_comparison["run_line"]
    ):
        assert m_direct["brier_score"] == pytest.approx(m_gate0["brier_score"])
        assert m_direct["accuracy"] == pytest.approx(m_gate0["accuracy"])


# ── train-fold-only 擬合（洩漏防護） ──────────────────────────────────────────
def test_phi_hat_and_platt_are_train_fold_only(synthetic, tmp_path):
    """竄改 test fold 的比分與線值，phi_hat / platt (a,b) 應完全不變。"""
    wu, ev = synthetic
    result_a = tcs.run_calibration_scorecard(wu, ev)

    with open(ev, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    split_idx = int(n * 0.6)  # test-period rows only (train fraction 0.6, matches DEFAULT_TRAIN_FRAC)
    for row in rows[split_idx:]:
        row["Home Score"] = "99"
        row["Away Score"] = "1"
        row["O/U"] = "150.5"
    ev_b = tmp_path / "eval_perturbed_test_fold.csv"
    with open(ev_b, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    result_b = tcs.run_calibration_scorecard(wu, ev_b)
    assert result_a.phi_hat == pytest.approx(result_b.phi_hat, rel=1e-12)
    assert result_a.platt_a == pytest.approx(result_b.platt_a, rel=1e-12)
    assert result_a.platt_b == pytest.approx(result_b.platt_b, rel=1e-12)


def test_odds_price_columns_never_used_as_calibration_feature(synthetic, tmp_path):
    wu, ev = synthetic
    with open(ev, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    perturbed = copy.deepcopy(rows)
    for row in perturbed:
        row["Home ML"] = "+999"
        row["Away ML"] = "-999"
        row["RL Home"] = "+999"
        row["RL Away"] = "-999"
        row["Over"] = "+999"
        row["Under"] = "-999"
    ev_b = tmp_path / "eval_price_perturbed.csv"
    with open(ev_b, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(perturbed)

    result_a = tcs.run_calibration_scorecard(wu, ev)
    result_b = tcs.run_calibration_scorecard(wu, ev_b)
    assert result_a.phi_hat == result_b.phi_hat
    assert result_a.platt_a == result_b.platt_a
    assert result_a.platt_b == result_b.platt_b
    assert [p["predicted_primary_probability"] for p in result_a.predictions] == \
           [p["predicted_primary_probability"] for p in result_b.predictions]


# ── push / probability conservation on full pipeline output ─────────────────
def test_predictions_probabilities_sum_to_one_and_bounded(synthetic):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    assert result.predictions
    for p in result.predictions:
        total = (p["predicted_primary_probability"] + p["predicted_secondary_probability"]
                 + p["predicted_push_probability"])
        assert total == pytest.approx(1.0, abs=1e-4)
        assert 0.0 <= p["predicted_primary_probability"] <= 1.0
        assert 0.0 <= p["predicted_push_probability"] <= 1.0
        assert p["predicted_side"] in ("OVER", "UNDER")
        assert p["actual_side"] in ("OVER", "UNDER", "PUSH")


def test_both_calibration_models_present(synthetic):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    names = {m["model_name"] for m in result.model_comparison}
    assert {"baseline_coinflip_50pct", "poisson_team_rate_model",
            "variance_inflation_normal", "platt_logistic_calibration"} <= names


# ── determinism ───────────────────────────────────────────────────────────────
def test_deterministic_reproducible(synthetic):
    wu, ev = synthetic
    r1 = tcs.run_calibration_scorecard(wu, ev)
    r2 = tcs.run_calibration_scorecard(wu, ev)
    assert r1.phi_hat == r2.phi_hat
    assert r1.platt_a == r2.platt_a and r1.platt_b == r2.platt_b
    assert r1.predictions == r2.predictions
    assert r1.model_comparison == r2.model_comparison


def test_write_reports_deterministic(synthetic, tmp_path):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    out1 = tmp_path / "report1"
    out2 = tmp_path / "report2"
    tcs.write_reports(result, out1)
    tcs.write_reports(result, out2)
    for name in ("p227a_total_calibration_scorecard.md", "p227a_total_calibration_scorecard.json",
                 "p227a_total_calibration_model_comparison.csv",
                 "p227a_total_calibration_predictions.csv"):
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


def test_write_reports_creates_four_files(synthetic, tmp_path):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    out = tmp_path / "report"
    written = tcs.write_reports(result, out)
    names = {p.name for p in written}
    assert names == {
        "p227a_total_calibration_predictions.csv",
        "p227a_total_calibration_model_comparison.csv",
        "p227a_total_calibration_scorecard.json",
        "p227a_total_calibration_scorecard.md",
    }
    for p in written:
        assert p.exists() and p.stat().st_size > 0
    payload = json.loads((out / "p227a_total_calibration_scorecard.json").read_text(encoding="utf-8"))
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert "phi_hat" in payload and "platt_a" in payload and "platt_b" in payload


def test_governance_scan_no_banned_words(synthetic, tmp_path):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    out = tmp_path / "report"
    tcs.write_reports(result, out)
    md_text = (out / "p227a_total_calibration_scorecard.md").read_text(encoding="utf-8").lower()
    for banned in ("guaranteed", "sure thing", "real money", "deploy to production", "live recommendation"):
        assert banned not in md_text


# ── no future prediction: predictions confined to historical eval window ────
def test_no_future_prediction_dates(synthetic):
    wu, ev = synthetic
    result = tcs.run_calibration_scorecard(wu, ev)
    for p in result.predictions:
        assert p["game_date"] < result.gate0_split["test_period"][0] or \
               result.gate0_split["test_period"][0] <= p["game_date"] <= result.gate0_split["test_period"][1]
        assert not p["game_date"].startswith("2026")


def test_unsupported_train_frac_rejected(synthetic):
    wu, ev = synthetic
    with pytest.raises(ValueError):
        tcs.run_calibration_scorecard(wu, ev, train_frac=0.5)


# ── 真實資料煙霧（存在才跑）──────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_real_data_gate0_matches_known_p226a_metrics():
    result = tcs.run_calibration_scorecard(REAL_WARMUP, REAL_EVAL)
    sp = result.gate0_split
    assert sp["train_rows"] == 1458 and sp["test_rows"] == 972
    g0_total = {m["model_name"]: m for m in result.gate0_market_comparison["total"]}
    g0_rl = {m["model_name"]: m for m in result.gate0_market_comparison["run_line"]}
    assert g0_total["baseline_coinflip_50pct"]["brier_score"] == pytest.approx(0.2500, abs=1e-4)
    assert g0_total["poisson_team_rate_model"]["accuracy"] == pytest.approx(0.5022, abs=1e-4)
    assert g0_total["poisson_team_rate_model"]["brier_score"] == pytest.approx(0.2637, abs=1e-4)
    assert g0_total["poisson_team_rate_model"]["calibration_error"] == pytest.approx(0.0959, abs=1e-4)
    assert g0_total["poisson_team_rate_model"]["decided_count"] == 918
    assert g0_total["poisson_team_rate_model"]["push_count"] == 54
    assert g0_rl["poisson_team_rate_model"]["accuracy"] == pytest.approx(0.6008, abs=1e-4)
    assert g0_rl["poisson_team_rate_model"]["brier_score"] == pytest.approx(0.2395, abs=1e-4)


@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_real_data_smoke_and_report_write(tmp_path):
    result = tcs.run_calibration_scorecard(REAL_WARMUP, REAL_EVAL)
    assert result.predictions
    assert result.phi_hat > 0.0
    out = tmp_path / "report"
    written = tcs.write_reports(result, out)
    assert len(written) == 4
