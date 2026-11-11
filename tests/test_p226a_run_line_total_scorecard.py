"""P226-A run line / total scorecard 測試（純標準庫；leakage / push / sign / 決定性 /
指標正確性 / 真實資料煙霧 / 治理掃描）。"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from wbc_backend.recommendation import run_line_total_scorecard as rlt

ROOT = Path(__file__).resolve().parents[1]
REAL_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
REAL_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta"]


def _write_asplayed(path: Path, n_days: int = 40) -> None:
    """前一季暖身格式（僅比分，無 RL/O-U）。"""
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


def _write_odds(path: Path, n_days: int = 80) -> None:
    """本季 odds 格式：比分 + Home RL Spread / RL Home / RL Away + O/U / Over / Under。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Away", "Away Score", "Home", "Home Score", "Status",
                    "Home ML", "Away ML", "Home RL Spread", "RL Home", "RL Away",
                    "O/U", "Over", "Under"])
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 2) % len(TEAMS)]
            hs, as_ = (5, 3) if i % 2 == 0 else (2, 4)   # 交替主客勝，無平手
            spread = "-1.5" if i % 2 == 0 else "+1.5"
            ou = "7.5" if i % 3 else "8.0"                # 部分整數線 → 可能 push
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


# ── 純函式單元：Poisson / Skellam ────────────────────────────────────────────
def test_poisson_pmf_known_values():
    assert rlt.poisson_pmf(0, 1.0) == pytest.approx(math.exp(-1.0), rel=1e-12)
    assert rlt.poisson_pmf(2, 2.0) == pytest.approx(2.0 * math.exp(-2.0), rel=1e-9)
    assert rlt.poisson_pmf(0, 0.0) == 1.0
    assert rlt.poisson_pmf(1, 0.0) == 0.0
    assert rlt.poisson_pmf(-1, 3.0) == 0.0


def test_poisson_pmf_array_matches_pointwise():
    for lam in (0.5, 2.3, 6.0, 11.7):
        arr = rlt.poisson_pmf_array(lam, 30)
        pointwise = [rlt.poisson_pmf(k, lam) for k in range(31)]
        for a, p in zip(arr, pointwise):
            assert a == pytest.approx(p, rel=1e-9, abs=1e-12)
        assert sum(arr) == pytest.approx(1.0, abs=1e-5)


def test_total_probabilities_sum_to_one():
    for lam_h, lam_a, line in [(4.0, 4.0, 7.5), (5.5, 3.2, 8.0), (2.0, 2.0, 4.0), (6.0, 7.0, 9.5)]:
        p_over, p_under, p_push = rlt.total_probabilities(lam_h, lam_a, line)
        assert p_over + p_under + p_push == pytest.approx(1.0, abs=1e-6)
        assert p_over >= 0.0 and p_under >= 0.0 and p_push >= 0.0


def test_total_probabilities_push_only_for_integer_line():
    _, _, p_push_half = rlt.total_probabilities(4.0, 4.0, 7.5)
    assert p_push_half == 0.0
    _, _, p_push_whole = rlt.total_probabilities(4.0, 4.0, 8.0)
    assert p_push_whole > 0.0


def test_run_line_probabilities_sum_to_one():
    for lam_h, lam_a, spread in [(4.0, 4.0, -1.5), (5.5, 3.2, 1.5), (4.5, 4.5, 0.0), (6.0, 3.0, -1.5)]:
        p_home, p_away, p_push = rlt.run_line_probabilities(lam_h, lam_a, spread)
        assert p_home + p_away + p_push == pytest.approx(1.0, abs=1e-6)
        assert p_home >= 0.0 and p_away >= 0.0 and p_push >= 0.0


def test_run_line_probabilities_no_realistic_push_on_half_line():
    # spread=+-1.5 -> threshold 非整數 -> D=home-away 為整數，P(D==threshold) 必為 0
    _, _, p_push = rlt.run_line_probabilities(4.5, 4.0, -1.5)
    assert p_push == 0.0
    _, _, p_push2 = rlt.run_line_probabilities(4.5, 4.0, 1.5)
    assert p_push2 == 0.0


@pytest.mark.parametrize("lam_h,lam_a", [(4.0, 4.0), (5.5, 3.0)])
def test_skellam_and_poisson_optional_scipy_cross_check(lam_h, lam_a):
    scipy_stats = pytest.importorskip("scipy.stats")
    # total 交叉驗證：Poisson(lam_h+lam_a)
    line = 7.5
    p_over, p_under, p_push = rlt.total_probabilities(lam_h, lam_a, line)
    sf = scipy_stats.poisson.sf(int(math.floor(line)), lam_h + lam_a)
    assert p_over == pytest.approx(sf, abs=1e-6)
    # run line 交叉驗證：Skellam(mu1=lam_h, mu2=lam_a)
    threshold = -1.5
    p_home, p_away, _ = rlt.run_line_probabilities(lam_h, lam_a, 1.5)
    expected_p_home = 1.0 - scipy_stats.skellam.cdf(int(math.floor(threshold)), lam_h, lam_a)
    assert p_home == pytest.approx(expected_p_home, abs=1e-4)


# ── 純函式單元：settlement ───────────────────────────────────────────────────
def test_settle_run_line_sign_convention():
    # spread=-1.5（主隊讓 1.5 分，主隊被看好）：贏 1 分不算 cover，贏 2+ 分才 cover
    assert rlt.settle_run_line(home_score=5, away_score=4, spread_home=-1.5) == "AWAY"
    assert rlt.settle_run_line(home_score=6, away_score=4, spread_home=-1.5) == "HOME"
    # spread=+1.5（主隊拿 1.5 分讓分，主隊是underdog）：輸 1 分仍 cover，輸 2+ 分才不 cover
    assert rlt.settle_run_line(home_score=4, away_score=5, spread_home=1.5) == "HOME"
    assert rlt.settle_run_line(home_score=3, away_score=5, spread_home=1.5) == "AWAY"
    # PK（spread=0.0）：終局分差恆不為 0，恆有明確一方
    assert rlt.settle_run_line(home_score=5, away_score=4, spread_home=0.0) == "HOME"
    assert rlt.settle_run_line(home_score=4, away_score=5, spread_home=0.0) == "AWAY"


def test_settle_total_push_detection():
    assert rlt.settle_total(home_score=4, away_score=4, ou_line=8.0) == "PUSH"
    assert rlt.settle_total(home_score=5, away_score=4, ou_line=8.0) == "OVER"
    assert rlt.settle_total(home_score=3, away_score=4, ou_line=8.0) == "UNDER"
    assert rlt.settle_total(home_score=5, away_score=3, ou_line=7.5) == "OVER"
    assert rlt.settle_total(home_score=3, away_score=3, ou_line=7.5) == "UNDER"


# ── metrics ─────────────────────────────────────────────────────────────────
def test_metrics_hand_computed():
    m = rlt.metrics([0.5, 0.5], [1, 0])
    assert m["n"] == 2
    assert m["accuracy"] == pytest.approx(0.5)
    assert m["brier_score"] == pytest.approx(0.25)


def test_metrics_empty():
    m = rlt.metrics([], [])
    assert m["n"] == 0 and m["accuracy"] is None and m["brier_score"] is None


def test_american_profit():
    assert rlt.american_profit("+110") == pytest.approx(1.10)
    assert rlt.american_profit("-120") == pytest.approx(100 / 120)
    assert rlt.american_profit("") is None


# ── 整合（合成資料）─────────────────────────────────────────────────────────
def test_leakage_train_strictly_before_test(synthetic):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    assert r.split["train_period"][1] <= r.split["test_period"][0]
    assert r.split["train_rows"] > 0 and r.split["test_rows"] > 0


def test_push_rows_excluded_from_decided_and_reported(synthetic):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    total_metrics = r.market_comparison["total"][0]
    assert total_metrics["push_count"] >= 1
    assert total_metrics["decided_count"] + total_metrics["push_count"] == total_metrics["row_count"]
    push_predictions = [p for p in r.predictions if p["market"] == "total" and p["is_push"]]
    assert push_predictions
    for p in push_predictions:
        assert p["correct"] is None


def test_probabilities_bounded_and_both_markets_present(synthetic):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    markets = {p["market"] for p in r.predictions}
    assert markets == {"run_line", "total"}
    for pr in r.predictions:
        assert 0.0 <= pr["predicted_primary_probability"] <= 1.0
        assert 0.0 <= pr["predicted_push_probability"] <= 1.0
        assert pr["predicted_side"] in ("HOME", "AWAY", "OVER", "UNDER")
        assert pr["actual_side"] in ("HOME", "AWAY", "OVER", "UNDER", "PUSH")


def test_both_model_names_present_per_market(synthetic):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    for market in ("run_line", "total"):
        names = {m["model_name"] for m in r.market_comparison[market]}
        assert names == {"baseline_coinflip_50pct", "poisson_team_rate_model"}


def test_baseline_is_constant_half(synthetic):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    base_probs = [p["predicted_primary_probability"] for p in r.predictions
                  if p["model_name"] == "baseline_coinflip_50pct"]
    assert base_probs and set(base_probs) == {0.5}


def test_deterministic_reproducible(synthetic):
    wu, ev = synthetic
    r1 = rlt.run_scorecard(wu, ev)
    r2 = rlt.run_scorecard(wu, ev)
    assert r1.home_adv == r2.home_adv
    assert [m["brier_score"] for m in r1.market_comparison["run_line"]] == \
           [m["brier_score"] for m in r2.market_comparison["run_line"]]
    assert [m["brier_score"] for m in r1.market_comparison["total"]] == \
           [m["brier_score"] for m in r2.market_comparison["total"]]
    assert r1.predictions == r2.predictions


def test_odds_never_used_as_model_input_feature(tmp_path):
    """核心防洩漏保證：poisson_team_rate_model 的機率只應由比分 + RL/O-U 的
    *線值*（settlement 用）決定，改動 RL/O-U 的*價格*欄位不應改變模型機率。"""
    wu = tmp_path / "wu.csv"
    ev_a = tmp_path / "eval_a.csv"
    ev_b = tmp_path / "eval_b.csv"
    _write_asplayed(wu)
    _write_odds(ev_a)

    # 複製 ev_a 但把所有價格欄位改成完全不同的值（線值不變）
    with open(ev_a, newline="", encoding="utf-8") as fin:
        rows = list(csv.DictReader(fin))
    for row in rows:
        row["Home ML"] = "+999"
        row["Away ML"] = "-999"
        row["RL Home"] = "+999"
        row["RL Away"] = "-999"
        row["Over"] = "+999"
        row["Under"] = "-999"
    with open(ev_b, "w", newline="", encoding="utf-8") as fout:
        w = csv.DictWriter(fout, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    ra = rlt.run_scorecard(wu, ev_a)
    rb = rlt.run_scorecard(wu, ev_b)

    poisson_a = [p["predicted_primary_probability"] for p in ra.predictions
                 if p["model_name"] == "poisson_team_rate_model"]
    poisson_b = [p["predicted_primary_probability"] for p in rb.predictions
                 if p["model_name"] == "poisson_team_rate_model"]
    assert poisson_a == poisson_b


def test_write_reports_creates_five_files(synthetic, tmp_path):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    out = tmp_path / "report"
    written = rlt.write_reports(r, out)
    names = {p.name for p in written}
    assert names == {
        "p226a_run_line_total_scorecard.md",
        "p226a_run_line_total_scorecard.json",
        "p226a_run_line_total_predictions.csv",
        "p226a_run_line_total_model_comparison.csv",
        "p226a_run_line_total_data_inventory.csv",
    }
    for p in written:
        assert p.exists() and p.stat().st_size > 0
    payload = json.loads((out / "p226a_run_line_total_scorecard.json").read_text(encoding="utf-8"))
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert any("push" in d for d in payload["disclaimers"])


def test_governance_scan_no_banned_words(synthetic, tmp_path):
    wu, ev = synthetic
    r = rlt.run_scorecard(wu, ev)
    out = tmp_path / "report"
    rlt.write_reports(r, out)
    md_text = (out / "p226a_run_line_total_scorecard.md").read_text(encoding="utf-8").lower()
    for banned in ("guaranteed", "sure thing", "real money", "deploy to production"):
        assert banned not in md_text
    # 明確聲明必須存在（非禁用詞掃描，而是正面驗證 disclaimer 有進到 markdown）
    assert "no betting recommendation" in md_text or "no betting recommendation".lower() in md_text


# ── 真實資料煙霧（存在才跑）──────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_real_data_smoke(tmp_path):
    r = rlt.run_scorecard(REAL_WARMUP, REAL_EVAL)
    assert r.eval_rows >= 2400              # 2025 全季量級
    assert r.split["train_rows"] + r.split["test_rows"] == r.eval_rows
    assert r.split["train_period"][1] <= r.split["test_period"][0]
    for market in ("run_line", "total"):
        for m in r.market_comparison[market]:
            assert 0.0 <= m["accuracy"] <= 1.0
            assert 0.0 <= m["brier_score"] <= 1.0
            assert m["decided_count"] + m["push_count"] == m["row_count"]
    total_poisson = next(m for m in r.market_comparison["total"]
                          if m["model_name"] == "poisson_team_rate_model")
    assert total_poisson["push_count"] > 0   # 已知整數線 push 為真實現象
    out = tmp_path / "report"
    written = rlt.write_reports(r, out)
    assert len(written) == 5
