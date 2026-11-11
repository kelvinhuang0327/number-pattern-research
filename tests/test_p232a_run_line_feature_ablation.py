"""P232-A 2025 single-season run line feature ablation 測試（純標準庫；Gate 0 重現
P226-A/P228-A 已知指標／無 odds-as-feature／僅 2025 資料計分／單一球季與
provenance-unverified 免責聲明／無未來預測語言／無下注優勢宣稱／JSON-MD 數字一致／
P226-A・P227-A・P228-A・P229-A・P230-A 既有產出未被本任務變動）。"""
from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import pytest

from wbc_backend.recommendation import run_line_feature_ablation_scorecard as fab
from wbc_backend.recommendation import run_line_total_scorecard as rlt

ROOT = Path(__file__).resolve().parents[1]
REAL_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
REAL_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"

P226A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "run_line_total_scorecard.py"
P228A_MODULE_PATH = ROOT / "wbc_backend" / "recommendation" / "run_line_robustness_scorecard.py"
P226A_REPORT_JSON = ROOT / "report" / "p226a_run_line_total_scorecard.json"
P228A_REPORT_JSON = ROOT / "report" / "p228a_run_line_robustness_scorecard.json"
P230A_REPORT_JSON = ROOT / "report" / "p230a_local_multiseason_runline_data_audit.json"

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


def _write_odds(path: Path, n_days: int = 260) -> None:
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


# ── 消融群組定義 ──────────────────────────────────────────────────────────────
def test_ablation_variants_include_full_model_and_four_ablations():
    assert fab.ABLATION_VARIANTS == [
        "full_model",
        "ablate_offense_rate",
        "ablate_defense_rate",
        "ablate_team_strength_both",
        "ablate_home_field",
    ]
    for v in fab.ABLATION_VARIANTS:
        assert v in fab.ABLATION_VARIANT_NOTES


def test_not_applicable_feature_groups_documented_honestly():
    groups = {g["group"] for g in fab.NOT_APPLICABLE_FEATURE_GROUPS}
    assert groups == {"rest_days", "rsi_streak_recent_form"}
    for g in fab.NOT_APPLICABLE_FEATURE_GROUPS:
        assert g["status"] == "NOT_PRESENT_IN_BASELINE_MODEL"


# ── 元件組裝：消融確實移除該群組的球隊專屬資訊 ────────────────────────────────
def test_assemble_raw_lambdas_ablate_offense_forces_league_average():
    row = fab.ComponentRow(game=None, off_h=6.0, def_h=3.0, off_a=2.0, def_a=5.0, avg=4.3)
    lam_home_full, lam_away_full = fab.assemble_raw_lambdas(row, "full_model")
    lam_home_abl, lam_away_abl = fab.assemble_raw_lambdas(row, "ablate_offense_rate")
    assert lam_home_full != pytest.approx(lam_home_abl)
    # offense 消融後：eff_off_h=eff_off_a=avg，def 維持不變
    expected_home = (row.avg * row.def_a) / row.avg
    expected_away = (row.avg * row.def_h) / row.avg
    assert lam_home_abl == pytest.approx(expected_home)
    assert lam_away_abl == pytest.approx(expected_away)


def test_assemble_raw_lambdas_ablate_defense_forces_league_average():
    row = fab.ComponentRow(game=None, off_h=6.0, def_h=3.0, off_a=2.0, def_a=5.0, avg=4.3)
    lam_home_abl, lam_away_abl = fab.assemble_raw_lambdas(row, "ablate_defense_rate")
    expected_home = (row.off_h * row.avg) / row.avg
    expected_away = (row.off_a * row.avg) / row.avg
    assert lam_home_abl == pytest.approx(expected_home)
    assert lam_away_abl == pytest.approx(expected_away)


def test_assemble_raw_lambdas_ablate_team_strength_both_equals_league_average_for_both():
    row = fab.ComponentRow(game=None, off_h=6.0, def_h=3.0, off_a=2.0, def_a=5.0, avg=4.3)
    lam_home_abl, lam_away_abl = fab.assemble_raw_lambdas(row, "ablate_team_strength_both")
    assert lam_home_abl == pytest.approx(row.avg)
    assert lam_away_abl == pytest.approx(row.avg)


def test_assemble_raw_lambdas_signature_has_no_spread_or_odds_access():
    """結構性保證：assemble_raw_lambdas 只接受 ComponentRow（無 spread/odds 欄位）與
    mode 字串，讓分/賠率在函式簽章層級就不可能進入 lambda 組裝。"""
    sig = inspect.signature(fab.assemble_raw_lambdas)
    assert list(sig.parameters) == ["row", "mode"]
    assert not hasattr(fab.ComponentRow, "spread_home")


# ── Gate 0：重現 P226-A / P228-A 已知數值 ────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_gate0_reproduces_known_p226a_p228a_metrics_on_real_data():
    result = fab.run_feature_ablation_scorecard(REAL_WARMUP, REAL_EVAL, strict_gate0=True)
    g0 = result.gate0
    assert g0["status"] == "GATE0_REPRODUCED_P226A_RUN_LINE_METRICS"
    assert g0["coinflip_brier"] == pytest.approx(0.2500, abs=1e-4)
    assert g0["poisson_accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert g0["poisson_brier"] == pytest.approx(0.2395, abs=1e-3)
    assert g0["calibrated_status"] == "GATE0_REPRODUCED_P228A_CALIBRATED_BRIER"
    assert g0["calibrated_brier"] == pytest.approx(0.2375, abs=1e-3)


@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_full_model_ablation_replica_matches_official_numbers_without_raising():
    """`run_feature_ablation_scorecard` 內建執行期斷言：full_model 消融模式在錨點
    split 上必須與 P226-A/P228-A 官方輸出逐指標相等，否則會拋出
    GATE0_FAILED_ABLATION_REPLICA_DIVERGED_FROM_OFFICIAL。此測試確認呼叫成功
    即代表通過，並額外核對 full_model 列本身的數值。"""
    result = fab.run_feature_ablation_scorecard(REAL_WARMUP, REAL_EVAL, strict_gate0=True)
    anchor_full = next(
        r for r in result.ablation_results
        if r.variant == "full_model" and abs(r.train_frac - rlt.DEFAULT_TRAIN_FRAC) < 1e-9
    )
    assert anchor_full.accuracy == pytest.approx(0.6008, abs=1e-3)
    assert anchor_full.brier_score == pytest.approx(0.2395, abs=1e-3)
    assert anchor_full.coinflip_brier == pytest.approx(0.2500, abs=1e-4)
    assert anchor_full.delta_brier_vs_full == 0.0
    assert anchor_full.delta_accuracy_vs_full == 0.0


def test_gate0_check_reused_from_p228a_raises_if_anchor_missing():
    with pytest.raises(RuntimeError, match="GATE0_FAILED_NO_ANCHOR"):
        fab.gate0_check([])


# ── 無 odds/line/implied-probability 作為預測特徵 ────────────────────────────
def test_odds_price_columns_never_affect_ablation_predictions(synthetic, tmp_path):
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

    r1 = fab.run_feature_ablation_scorecard(wu, ev)
    r2 = fab.run_feature_ablation_scorecard(wu, ev2)
    for a, b in zip(r1.ablation_results, r2.ablation_results):
        assert a.variant == b.variant and a.train_frac == b.train_frac
        assert a.brier_score == pytest.approx(b.brier_score)
        assert a.accuracy == pytest.approx(b.accuracy)


def test_run_line_spread_used_only_as_settlement_threshold(synthetic):
    """spread 只能決定 predicted_side / actual_side 的門檻位置，不能改變
    raw lambda（結構性保證已由 assemble_raw_lambdas 簽章測試涵蓋）；這裡再從
    端對端預測輸出核對機率值域合理、線值確實被記錄為 settlement 用途。"""
    result = fab.run_feature_ablation_scorecard(*synthetic)
    anchor = [r for r in result.ablation_results if abs(r.train_frac - rlt.DEFAULT_TRAIN_FRAC) < 1e-9]
    for r in anchor:
        for p in r.predictions:
            assert p["line_value"] in (-1.5, 1.5)
            assert 0.0 <= p["predicted_home_probability"] <= 1.0


# ── 僅使用 2025 資料計分 ──────────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_only_2025_data_is_scored_on_real_data():
    result = fab.run_feature_ablation_scorecard(REAL_WARMUP, REAL_EVAL, strict_gate0=True)
    anchor = [r for r in result.ablation_results if abs(r.train_frac - rlt.DEFAULT_TRAIN_FRAC) < 1e-9]
    assert anchor
    for r in anchor:
        assert r.predictions
        for p in r.predictions:
            assert p["game_date"].startswith("2025-")
    # warmup (2024) rows are seed-only state, never scored
    assert result.warmup_rows > 0
    assert result.eval_rows == 2430


# ── 免責聲明 / 語言限制 ───────────────────────────────────────────────────────
def test_disclaimers_include_required_labels():
    text = " ".join(fab.DISCLAIMERS).lower()
    for required in ("single-season", "2025-only", "historical paper-only", "provenance-unverified",
                      "not live", "not production", "not real betting", "not a proven edge"):
        assert required in text


def test_write_reports_creates_three_files_and_no_future_or_edge_language(synthetic, tmp_path):
    result = fab.run_feature_ablation_scorecard(*synthetic)
    out = tmp_path / "report"
    written = fab.write_reports(result, out)
    names = {p.name for p in written}
    assert names == {
        "p232a_run_line_feature_ablation_scorecard.md",
        "p232a_run_line_feature_ablation_scorecard.json",
        "p232a_run_line_feature_ablation_comparison.csv",
        "p232a_run_line_feature_ablation_predictions.csv",
    }
    for p in written:
        assert p.exists() and p.stat().st_size > 0

    md_text = (out / "p232a_run_line_feature_ablation_scorecard.md").read_text(encoding="utf-8")
    md_lower = md_text.lower()
    for banned in ("guaranteed", "sure thing", "real money", "deploy to production"):
        assert banned not in md_lower
    assert "not a proven edge" in md_lower
    assert "single-season" in md_lower
    assert "provenance-unverified" in md_lower
    for p in result.ablation_results:
        for pred in p.predictions:
            assert pred["game_date"] < "2026-01-01"


def test_write_reports_deterministic(synthetic, tmp_path):
    result = fab.run_feature_ablation_scorecard(*synthetic)
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    fab.write_reports(result, out1)
    fab.write_reports(result, out2)
    for name in ("p232a_run_line_feature_ablation_scorecard.md",
                 "p232a_run_line_feature_ablation_scorecard.json",
                 "p232a_run_line_feature_ablation_comparison.csv",
                 "p232a_run_line_feature_ablation_predictions.csv"):
        assert (out1 / name).read_text(encoding="utf-8") == (out2 / name).read_text(encoding="utf-8")


# ── JSON 與 MD 關鍵數字一致 ───────────────────────────────────────────────────
@pytest.mark.skipif(not (REAL_WARMUP.exists() and REAL_EVAL.exists()),
                    reason="real tracked MLB data not present")
def test_json_and_md_agree_on_gate0_figures_real_data(tmp_path):
    result = fab.run_feature_ablation_scorecard(REAL_WARMUP, REAL_EVAL, strict_gate0=True)
    out = tmp_path / "report"
    fab.write_reports(result, out)
    payload = json.loads((out / "p232a_run_line_feature_ablation_scorecard.json").read_text(encoding="utf-8"))
    md_text = (out / "p232a_run_line_feature_ablation_scorecard.md").read_text(encoding="utf-8")

    g0 = payload["gate0_reproduction"]
    assert f"{g0['poisson_accuracy']:.4f}" in md_text
    assert f"{g0['poisson_brier']:.4f}" in md_text
    assert f"{g0['coinflip_brier']:.4f}" in md_text
    assert f"{g0['calibrated_brier']:.4f}" in md_text
    assert payload["interpretation"]["label"] in md_text


def test_interpretation_label_is_one_of_expected_values(synthetic):
    result = fab.run_feature_ablation_scorecard(*synthetic)
    assert result.interpretation["label"] in (
        "SIGNAL_PERSISTS_ACROSS_ABLATIONS",
        "SIGNAL_DEPENDS_ON_FRAGILE_FEATURE_GROUP",
        "SIGNAL_COLLAPSES_UNDER_ABLATION",
        "INCONCLUSIVE",
    )


def test_delta_brier_vs_full_is_zero_for_full_model(synthetic):
    result = fab.run_feature_ablation_scorecard(*synthetic)
    for r in result.ablation_results:
        if r.variant == "full_model":
            assert r.delta_brier_vs_full == 0.0
            assert r.delta_accuracy_vs_full == 0.0


def test_split_grid_matches_p228a_pre_registered_grid():
    assert fab.SPLIT_GRID == [0.5, 0.6, 0.7]


def test_deterministic_across_runs(synthetic):
    r1 = fab.run_feature_ablation_scorecard(*synthetic)
    r2 = fab.run_feature_ablation_scorecard(*synthetic)
    for a, b in zip(r1.ablation_results, r2.ablation_results):
        assert a.variant == b.variant and a.train_frac == b.train_frac
        assert a.brier_score == b.brier_score and a.accuracy == b.accuracy
    assert r1.interpretation == r2.interpretation


# ── P226-A / P227-A / P228-A / P229-A / P230-A 既有產出未被本任務變動 ────────
def test_p226a_p228a_source_files_still_exist_and_signatures_unchanged():
    """本任務不修改既有模組；本測試確認官方 API 簽章未變（run_scorecard /
    run_split_grid 仍接受 train_frac 參數），並確認本檔重用（而非複製貼上）
    這些既有函式。"""
    assert P226A_MODULE_PATH.exists()
    assert P228A_MODULE_PATH.exists()
    sig_226 = inspect.signature(rlt.run_scorecard)
    assert "train_frac" in sig_226.parameters
    import wbc_backend.recommendation.run_line_robustness_scorecard as rrs
    sig_228 = inspect.signature(rrs.run_split_grid)
    assert "split_grid" in sig_228.parameters
    assert fab.p228a_run_split_grid is rrs.run_split_grid
    assert fab.gate0_check is rrs.gate0_check
    assert fab.run_train_fold_calibration is rrs.run_train_fold_calibration


@pytest.mark.skipif(
    not (P226A_REPORT_JSON.exists() and P228A_REPORT_JSON.exists() and P230A_REPORT_JSON.exists()),
    reason="P226-A/P228-A/P230-A report artifacts not present locally",
)
def test_p226a_p228a_p230a_report_artifacts_unchanged_content():
    p226 = json.loads(P226A_REPORT_JSON.read_text(encoding="utf-8"))
    rl = {m["model_name"]: m for m in p226["market_comparison"]["run_line"]}
    assert rl["poisson_team_rate_model"]["accuracy"] == pytest.approx(0.6008, abs=1e-3)
    assert rl["poisson_team_rate_model"]["brier_score"] == pytest.approx(0.2395, abs=1e-3)
    assert rl["baseline_coinflip_50pct"]["brier_score"] == pytest.approx(0.2500, abs=1e-4)

    p228 = json.loads(P228A_REPORT_JSON.read_text(encoding="utf-8"))
    assert p228["gate0_reproduction"]["status"] == "GATE0_REPRODUCED_P226A_RUN_LINE_METRICS"
    assert p228["robustness_conclusion"]["label"] == "ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH"

    p230 = json.loads(P230A_REPORT_JSON.read_text(encoding="utf-8"))
    assert p230["recommended_next_technical_step"]["authorization_status"] == "NOT_AUTHORIZED_YET"
    seasons = {s["season"]: s["classification"] for s in p230["seasons"]}
    assert seasons["2025"] == "FULL_RUNLINE_EVAL_READY"
    assert seasons["2024"] == "LABEL_ONLY_NO_ODDS"
