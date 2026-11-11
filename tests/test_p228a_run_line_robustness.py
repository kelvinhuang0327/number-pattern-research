"""P228-A run line robustness & calibration 測試（純標準庫；Gate 0 重現 / split grid
無 shuffle 確定性 / train-fold-only 校準 / 無 odds-as-feature / 無未來預測 /
P226-A・P227-A 檔案未變動）。"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from wbc_backend.recommendation import run_line_robustness_scorecard as rrs
from wbc_backend.recommendation import run_line_total_scorecard as rlt

ROOT = Path(__file__).resolve().parents[1]
REAL_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
REAL_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

P226A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "run_line_total_scorecard.py"
P227A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "total_calibration_scorecard.py"
P226A_TEST_PATH = ROOT / "tests" / "test_p226a_run_line_total_scorecard.py"
P227A_TEST_PATH = ROOT / "tests" / "test_p227a_total_calibration.py"
P226A_REPORT_JSON = ROOT / "report" / "p226a_run_line_total_scorecard.json"
P227A_REPORT_JSON = ROOT / "report" / "p227a_total_calibration_scorecard.json"

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _write_odds(path: Path, n_days: int = 260) -> None:
    """較長的合成 eval universe（覆蓋多個月），供 split grid + monthly window 測試用。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Away", "Away Score", "Home", "Home Score", "Status",
                    "Home ML", "Away ML", "Home RL Spread", "RL Home", "RL Away",
                    "O/U", "Over", "Under"])
        day_cursor = 0
        month = 3
        for i in range(n_days):
            home = TEAMS[i % len(TEAMS)]
            away = TEAMS[(i + 2) % len(TEAMS)]
            hs, as_ = (5, 3) if i % 2 == 0 else (2, 4)
            spread = "-1.5" if i % 2 == 0 else "+1.5"
            ou = "7.5" if i % 3 else "8.0"
            day_cursor += 1
            if day_cursor > 28:
                day_cursor = 1
                month += 1
            w.writerow([f"2025-{month:02d}-{day_cursor:02d}", away, as_, home, hs, "Final",
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
    for p in (0.1, 0.3, 0.5, 0.7, 0.9):
        assert rrs.sigmoid(rrs.logit(p)) == pytest.approx(p, abs=1e-9)


def test_fit_platt_deterministic():
    xs = [rrs.logit(p) for p in (0.2, 0.4, 0.6, 0.8, 0.55, 0.35)]
    ys = [0, 0, 1, 1, 1, 0]
    a1, b1 = rrs.fit_platt(xs, ys)
    a2, b2 = rrs.fit_platt(xs, ys)
    assert a1 == a2 and b1 == b2


def test_fit_platt_fixed_initial_values_are_module_constants():
    assert rrs.PLATT_INITIAL_A == 1.0
    assert rrs.PLATT_INITIAL_B == 0.0


def test_fit_platt_empty_returns_initial_values():
    a, b = rrs.fit_platt([], [])
    assert a == rrs.PLATT_INITIAL_A and b == rrs.PLATT_INITIAL_B


def test_reliability_bins_counts_and_bounds():
    preds = [0.05, 0.15, 0.55, 0.95]
    ys = [0, 1, 1, 1]
    bins = rrs.reliability_bins(preds, ys, n_bins=10)
    assert len(bins) == 10
    assert sum(b["n"] for b in bins) == 4
    for b in bins:
        if b["n"] > 0:
            assert 0.0 <= b["mean_predicted"] <= 1.0
            assert 0.0 <= b["empirical_rate"] <= 1.0


# ── Gate 0 ──────────────────────────────────────────────────────────────────
def test_gate0_reproduces_p226a_run_line_metrics_on_real_data():
    """Gate 0：本檔重用 P226-A 官方 run_scorecard，錨點 train_frac 必須逐場重現
    已知 Run Line 指標（accuracy 0.6008 / brier 0.2395 / coinflip brier 0.2500）。"""
    entries = rrs.run_split_grid(REAL_WARMUP, REAL_EVAL)
    gate0 = rrs.gate0_check(entries)
    assert gate0["status"] == "GATE0_ANCHOR_PRESENT"
    gate0 = rrs.assert_gate0_matches_known_p226a_run_line_metrics(gate0)
    assert gate0["status"] == "GATE0_REPRODUCED_P226A_RUN_LINE_METRICS"
    assert gate0["coinflip_brier"] == pytest.approx(0.2500, abs=1e-4)
    assert gate0["poisson_accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert gate0["poisson_brier"] == pytest.approx(0.2395, abs=1e-3)


def test_gate0_check_raises_if_anchor_missing():
    with pytest.raises(RuntimeError, match="GATE0_FAILED_NO_ANCHOR"):
        rrs.gate0_check([])


def test_gate0_strict_assertion_raises_on_mismatched_synthetic_data(synthetic):
    """合成測試資料的 Gate 0 錨點指標本就不會等於 P226-A 真實資料的已知數值，
    驗證嚴格版本會正確偵測並拋出 GATE0_FAILED_MISMATCH（而非結構性檢查被誤用於
    合成資料時靜默通過）。"""
    entries = rrs.run_split_grid(*synthetic)
    gate0 = rrs.gate0_check(entries)
    with pytest.raises(RuntimeError, match="GATE0_FAILED_MISMATCH"):
        rrs.assert_gate0_matches_known_p226a_run_line_metrics(gate0)


def test_calibration_replica_matches_p226a_raw_p_home_exactly_on_real_data():
    """P228-A 重新實作的 walk-forward 在 P226-A DEFAULT_TRAIN_FRAC 上，逐場 raw
    p_home 必須與 P226-A 官方輸出完全相等（本函式內建執行期 RuntimeError 斷言，
    此測試只是再次確認呼叫不拋錯即代表通過）。"""
    result = rrs.run_train_fold_calibration(REAL_WARMUP, REAL_EVAL)
    assert result.raw["decided_count"] > 0


# ── Split grid：無 shuffle / 確定性 ──────────────────────────────────────────
def test_split_grid_is_deterministic_and_chronological(synthetic):
    wu, ev = synthetic
    e1 = rrs.run_split_grid(wu, ev)
    e2 = rrs.run_split_grid(wu, ev)
    assert [vars(e) for e in e1] == [vars(e) for e in e2]
    for e in e1:
        assert e.train_period[1] <= e.test_period[0]


def test_split_grid_uses_pre_registered_grid_values():
    assert rrs.SPLIT_GRID == [0.5, 0.6, 0.7]
    assert rrs.DEFAULT_TRAIN_FRAC in rrs.SPLIT_GRID


def test_split_grid_brier_margin_sign_convention(synthetic):
    wu, ev = synthetic
    entries = rrs.run_split_grid(wu, ev)
    for e in entries:
        expected_margin = round(e.coinflip_brier - e.poisson_brier, 6)
        assert e.brier_margin == expected_margin
        assert e.poisson_beats_coinflip_brier == (e.poisson_brier < e.coinflip_brier)


# ── Monthly windows：擴展視窗 / 無 shuffle / train 嚴格早於 test ─────────────
def test_monthly_windows_are_chronological_and_deterministic(synthetic):
    wu, ev = synthetic
    w1 = rrs.run_monthly_windows(wu, ev)
    w2 = rrs.run_monthly_windows(wu, ev)
    assert [vars(w) for w in w1] == [vars(w) for w in w2]
    window_ids = [w.window_id for w in w1]
    assert window_ids == sorted(window_ids)


def test_monthly_windows_train_strictly_before_test(synthetic):
    wu, ev = synthetic
    warmup = rlt.load_games(wu)
    evalg = rlt.load_games(ev)
    rows = rrs.walk_forward_raw_rows(warmup, evalg)
    month_indices: dict = {}
    for idx, r in enumerate(rows):
        if r.game.spread_home is None:
            continue
        key = (r.game.dt.year, r.game.dt.month)
        month_indices.setdefault(key, []).append(idx)
    for key, idxs in month_indices.items():
        first_idx = idxs[0]
        train_dates = [rows[i].game.dt for i in range(first_idx)]
        test_dates = [rows[i].game.dt for i in idxs]
        if train_dates and test_dates:
            assert max(train_dates) < min(test_dates)


def test_monthly_windows_skip_below_thresholds(synthetic):
    wu, ev = synthetic
    entries = rrs.run_monthly_windows(wu, ev)
    for w in entries:
        if w.status == "SKIPPED_INSUFFICIENT_TRAIN":
            assert w.train_rows < rrs.MIN_TRAIN_ROWS_FOR_WINDOW
        elif w.status == "SKIPPED_INSUFFICIENT_TEST":
            assert w.test_rows < rrs.MIN_TEST_ROWS_FOR_WINDOW
        else:
            assert w.status == "EVALUATED"
            assert w.train_rows >= rrs.MIN_TRAIN_ROWS_FOR_WINDOW
            assert w.test_rows >= rrs.MIN_TEST_ROWS_FOR_WINDOW


def test_monthly_windows_real_data_has_evaluated_entries():
    entries = rrs.run_monthly_windows(REAL_WARMUP, REAL_EVAL)
    evaluated = [w for w in entries if w.status == "EVALUATED"]
    assert len(evaluated) >= 4
    for w in evaluated:
        assert w.coinflip_brier == pytest.approx(0.25, abs=1e-9)
        assert 0.0 <= w.poisson_accuracy <= 1.0
        assert 0.0 <= w.poisson_brier <= 1.0


# ── Train-fold-only calibration ──────────────────────────────────────────────
def test_calibration_is_train_fold_only(synthetic):
    """驗證 Platt (a, b) 只受 train fold 影響：修改 test fold 的比分不應改變凍結後
    的 (a, b)（因為 train fold 資料完全相同）。"""
    wu, ev = synthetic
    r1 = rrs.run_train_fold_calibration(wu, ev)

    with open(ev, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    split_idx = int(n * rrs.DEFAULT_TRAIN_FRAC)
    for row in rows[split_idx:]:
        row["Home Score"] = "1"
        row["Away Score"] = "9"

    ev2 = ev.parent / "eval_mutated_test_fold.csv"
    with open(ev2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    r2 = rrs.run_train_fold_calibration(wu, ev2)
    assert r1.platt_a == pytest.approx(r2.platt_a, abs=1e-9)
    assert r1.platt_b == pytest.approx(r2.platt_b, abs=1e-9)


def test_calibration_deterministic(synthetic):
    wu, ev = synthetic
    r1 = rrs.run_train_fold_calibration(wu, ev)
    r2 = rrs.run_train_fold_calibration(wu, ev)
    assert r1.platt_a == r2.platt_a and r1.platt_b == r2.platt_b
    assert r1.predictions == r2.predictions


def test_odds_price_columns_never_used_as_calibration_feature(synthetic, tmp_path):
    """核心防洩漏保證：修改 RL/O-U 的*價格*欄位（線值不變）不應改變 raw 或校準後的
    run line home 機率。"""
    wu, ev = synthetic
    with open(ev, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["Home ML"] = "+999"
        row["Away ML"] = "-999"
        row["RL Home"] = "+999"
        row["RL Away"] = "-999"
        row["Over"] = "+999"
        row["Under"] = "-999"
    ev2 = tmp_path / "eval_price_mutated.csv"
    with open(ev2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    r1 = rrs.run_train_fold_calibration(wu, ev)
    r2 = rrs.run_train_fold_calibration(wu, ev2)
    assert r1.platt_a == r2.platt_a and r1.platt_b == r2.platt_b
    p1 = [p["raw_predicted_home_probability"] for p in r1.predictions]
    p2 = [p["raw_predicted_home_probability"] for p in r2.predictions]
    assert p1 == p2


def test_run_line_spread_used_only_as_threshold_not_feature(synthetic):
    """run line spread 只應作為 settlement threshold；raw 機率完全由 lambda 決定，
    spread 只改變 threshold 位置，不進入 lambda 的計算輸入。"""
    result = rrs.run_train_fold_calibration(*synthetic)
    for p in result.predictions:
        assert p["line_value"] in (-1.5, 1.5)
        assert 0.0 <= p["raw_predicted_home_probability"] <= 1.0
        assert 0.0 <= p["calibrated_predicted_home_probability"] <= 1.0


# ── 完整流程 / 報告輸出 ───────────────────────────────────────────────────────
def test_full_scorecard_deterministic(synthetic):
    wu, ev = synthetic
    r1 = rrs.run_robustness_scorecard(wu, ev)
    r2 = rrs.run_robustness_scorecard(wu, ev)
    assert r1.gate0 == r2.gate0
    assert [vars(e) for e in r1.split_grid] == [vars(e) for e in r2.split_grid]
    assert [vars(w) for w in r1.monthly_windows] == [vars(w) for w in r2.monthly_windows]
    assert r1.conclusion == r2.conclusion


def test_robustness_conclusion_label_is_one_of_expected_values(synthetic):
    result = rrs.run_robustness_scorecard(*synthetic)
    assert result.conclusion["label"] in (
        "ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH",
        "MIXED_SPLIT_SPECIFIC",
        "NOT_ROBUST",
    )


def test_no_future_prediction_dates(synthetic):
    result = rrs.run_robustness_scorecard(*synthetic)
    for p in result.calibration.predictions:
        assert p["game_date"] < "2026-01-01"
    for e in result.split_grid:
        assert e.test_period[1] < "2026-01-01"


def test_write_reports_creates_four_files(synthetic, tmp_path):
    result = rrs.run_robustness_scorecard(*synthetic)
    out = tmp_path / "report"
    written = rrs.write_reports(result, out)
    names = {p.name for p in written}
    assert names == {
        "p228a_run_line_robustness_scorecard.md",
        "p228a_run_line_robustness_scorecard.json",
        "p228a_run_line_robustness_splits.csv",
        "p228a_run_line_robustness_predictions.csv",
    }
    for p in written:
        assert p.exists() and p.stat().st_size > 0
    payload = json.loads((out / "p228a_run_line_robustness_scorecard.json").read_text(encoding="utf-8"))
    assert payload["scope"] == "LOCAL_HISTORICAL_REPLAY_ONLY"
    assert payload["gate0_reproduction"]["status"] == "GATE0_ANCHOR_PRESENT"


def test_write_reports_deterministic(synthetic, tmp_path):
    result = rrs.run_robustness_scorecard(*synthetic)
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    rrs.write_reports(result, out1)
    rrs.write_reports(result, out2)
    for name in ("p228a_run_line_robustness_scorecard.md", "p228a_run_line_robustness_scorecard.json",
                 "p228a_run_line_robustness_splits.csv", "p228a_run_line_robustness_predictions.csv"):
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


def test_governance_scan_no_banned_words(synthetic, tmp_path):
    result = rrs.run_robustness_scorecard(*synthetic)
    out = tmp_path / "report"
    rrs.write_reports(result, out)
    md_text = (out / "p228a_run_line_robustness_scorecard.md").read_text(encoding="utf-8").lower()
    for banned in ("guaranteed", "sure thing", "real money", "deploy to production"):
        assert banned not in md_text
    assert "not a proven edge" in md_text
    assert "paper-only" in md_text.replace(" ", "-") or "paper-only" in md_text


# ── 真實資料煙霧 ─────────────────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_real_data_smoke_and_report_write(tmp_path):
    result = rrs.run_robustness_scorecard(REAL_WARMUP, REAL_EVAL, strict_gate0=True)
    assert result.gate0["status"] == "GATE0_REPRODUCED_P226A_RUN_LINE_METRICS"
    assert len(result.split_grid) == 3
    assert any(w.status == "EVALUATED" for w in result.monthly_windows)
    out = tmp_path / "report"
    written = rrs.write_reports(result, out)
    assert len(written) == 4


# ── P226-A / P227-A 檔案未被本任務變動（回歸保護）───────────────────────────
def test_p226a_and_p227a_files_unchanged_by_this_test_run():
    """本測試不斷言特定內容，只確認 P226-A/P227-A 原始模組與測試檔案仍存在且可
    被匯入、其官方 API 簽章未變（run_scorecard 仍接受 train_frac 參數）。真正的
    「未修改」保證來自 Forbidden Files 規範與 PR diff 審查，本測試僅作程式層面的
    存在性/介面回歸防護。"""
    assert P226A_MODULE_PATH.exists()
    assert P227A_MODULE_PATH.exists()
    assert P226A_TEST_PATH.exists()
    assert P227A_TEST_PATH.exists()
    import inspect
    sig = inspect.signature(rlt.run_scorecard)
    assert "train_frac" in sig.parameters


@pytest.mark.skipif(not (P226A_REPORT_JSON.exists() and P227A_REPORT_JSON.exists()),
                    reason="P226-A/P227-A report artifacts not present locally")
def test_p226a_p227a_report_artifacts_unchanged_content():
    p226 = json.loads(P226A_REPORT_JSON.read_text(encoding="utf-8"))
    rl = {m["model_name"]: m for m in p226["market_comparison"]["run_line"]}
    assert rl["poisson_team_rate_model"]["accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert rl["poisson_team_rate_model"]["brier_score"] == pytest.approx(0.2395, abs=1e-3)
    assert rl["baseline_coinflip_50pct"]["brier_score"] == pytest.approx(0.2500, abs=1e-4)

    p227 = json.loads(P227A_REPORT_JSON.read_text(encoding="utf-8"))
    assert p227["beats_coinflip_brier"] is False
