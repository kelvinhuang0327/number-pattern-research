"""P207-A 本機重訓 scorecard 測試（純標準庫；leakage / 決定性 / 指標正確性 / 真實資料煙霧）。"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
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


def _write_same_date_eval(
    path: Path, *, first_same_date_home_win: int = 1, reverse_same_date_rows: bool = False
) -> None:
    rows: list[list[object]] = []
    teams = ["Alpha", "Bravo", "Charlie", "Delta"]
    for i in range(30):
        date = f"2025-04-{i + 1:02d}"
        if i == 25:
            same_date = [
                [
                    date,
                    "Charlie",
                    2 if first_same_date_home_win else 5,
                    "Alpha",
                    5 if first_same_date_home_win else 2,
                    "Final",
                    "-110",
                    "-110",
                ],
                [date, "Alpha", 3, "Bravo", 4, "Final", "-110", "-110"],
            ]
            rows.extend(reversed(same_date) if reverse_same_date_rows else same_date)
        elif i == 26:
            # Alpha appears again on the next date so the completed prior-date update is visible.
            rows.append([date, "Delta", 3, "Alpha", 5, "Final", "-110", "-110"])
        else:
            home = teams[i % len(teams)]
            away = teams[(i + 1) % len(teams)]
            home_score, away_score = (5, 3) if i % 2 == 0 else (2, 4)
            rows.append(
                [date, away, away_score, home, home_score, "Final", "-110", "-110"]
            )
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["Date", "Away", "Away Score", "Home", "Home Score", "Status", "Home ML", "Away ML"]
        )
        writer.writerows(rows)


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


def test_selected_team_history_probability_is_shared_with_date_batched_rows():
    state = lrs.DateBatchedTeamState(
        history_wins={"Home": 8, "Away": 3},
        history_games={"Home": 10, "Away": 10},
    )
    probability = state.team_history_smooth_probability("Home", "Away")

    assert 0.5 < probability < 1.0
    assert state.selected_model_state() == {
        "history_wins": {"Away": 3, "Home": 8},
        "history_games": {"Away": 10, "Home": 10},
    }
    with pytest.raises(ValueError, match="invalid matchup"):
        state.team_history_smooth_probability("Same", "Same")


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
    assert r.split["train_period"][1] < r.split["test_period"][0]
    assert r.split["requested_train_frac"] == pytest.approx(0.60)
    assert r.split["effective_train_frac"] == pytest.approx(
        r.split["train_rows"] / (r.split["train_rows"] + r.split["test_rows"])
    )
    assert r.split["train_date_count"] + r.split["test_date_count"] == 60
    assert r.split["split_strategy"] == lrs.SPLIT_STRATEGY
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
    assert r1.split == r2.split
    assert r1.predictions == r2.predictions


def test_complete_date_split_tie_rule_prefers_earlier_boundary():
    games = [
        lrs.Game(datetime(2025, 4, 1), "2025-04-01", "H1", "A1", 1),
        lrs.Game(datetime(2025, 4, 2), "2025-04-02", "H2", "A2", 1),
        lrs.Game(datetime(2025, 4, 2), "2025-04-02", "H3", "A3", 0),
        lrs.Game(datetime(2025, 4, 3), "2025-04-03", "H4", "A4", 1),
    ]
    rows = [{"game": game} for game in games]

    train, test, split = lrs.select_complete_date_split(rows, 0.5)

    assert len(train) == 1
    assert len(test) == 3
    assert split["selected_boundary_date"] == "2025-04-01"
    assert split["tie_rule"] == lrs.SPLIT_TIE_RULE


def test_same_date_predictions_share_pre_date_state_and_update_after_batch(tmp_path):
    warmup = tmp_path / "warmup.csv"
    warmup.write_text("date,away_team,home_team,home_win,status\n", encoding="utf-8")
    base_path = tmp_path / "base.csv"
    changed_path = tmp_path / "changed.csv"
    _write_same_date_eval(base_path, first_same_date_home_win=1)
    _write_same_date_eval(changed_path, first_same_date_home_win=0)

    base = lrs.run_scorecard(warmup, base_path)
    changed = lrs.run_scorecard(warmup, changed_path)

    def probabilities(result):
        return {
            (row["game_id"], row["model_name"]): row["predicted_home_win_probability"]
            for row in result.predictions
        }

    base_probs = probabilities(base)
    changed_probs = probabilities(changed)
    same_date_second = "2025-04-26_Alpha@Bravo"
    next_date = "2025-04-27_Delta@Alpha"
    for model in ("elo_like_rating", "retrained_team_history_smooth"):
        assert base_probs[(same_date_second, model)] == changed_probs[(same_date_second, model)]
        assert base_probs[(next_date, model)] != changed_probs[(next_date, model)]

    feature_rows = lrs.build_date_batched_rows([], lrs.load_games(base_path))
    by_id = {row["game"].game_id: row for row in feature_rows}
    first = by_id["2025-04-26_Charlie@Alpha"]
    second = by_id[same_date_second]
    assert first["pre_date_home_elo"] == second["pre_date_away_elo"]
    assert first["pre_date_home_games"] == second["pre_date_away_games"]


def test_within_date_source_permutation_is_prediction_invariant(tmp_path):
    warmup = tmp_path / "warmup.csv"
    warmup.write_text("date,away_team,home_team,home_win,status\n", encoding="utf-8")
    eval_path = tmp_path / "evaluation.csv"
    _write_same_date_eval(eval_path)

    base = lrs.run_scorecard(warmup, eval_path)
    _write_same_date_eval(eval_path, reverse_same_date_rows=True)
    permuted = lrs.run_scorecard(warmup, eval_path)

    assert base.split == permuted.split
    assert base.predictions == permuted.predictions
    assert base.comparison == permuted.comparison


def test_metrics_are_recomputed_from_corrected_predictions(synthetic):
    warmup, evaluation = synthetic
    result = lrs.run_scorecard(warmup, evaluation)
    for comparison in result.comparison:
        predictions = [
            row for row in result.predictions
            if row["model_name"] == comparison["model_name"]
        ]
        recomputed = lrs.metrics(
            [float(row["predicted_home_win_probability"]) for row in predictions],
            [int(row["actual_home_win"]) for row in predictions],
        )
        assert comparison["accuracy"] == pytest.approx(recomputed["accuracy"])
        assert comparison["brier_score"] == pytest.approx(
            recomputed["brier_score"], abs=1e-6
        )


def test_duplicate_matchups_receive_deterministic_occurrences(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    rows = [
        ["2025-04-01", "Away", 5, "Home", 2, "Final", "+120", "-130"],
        ["2025-04-01", "Away", 3, "Home", 6, "Final", "-115", "+105"],
    ]
    for path, values in ((first, rows), (second, list(reversed(rows)))):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["Date", "Away", "Away Score", "Home", "Home Score", "Status", "Home ML", "Away ML"]
            )
            writer.writerows(values)

    first_games = lrs.load_games(first)
    second_games = lrs.load_games(second)
    assert [(game.game_id, game.home_win) for game in first_games] == [
        (game.game_id, game.home_win) for game in second_games
    ]
    assert [game.game_id for game in first_games] == [
        "2025-04-01_Away@Home#1",
        "2025-04-01_Away@Home#2",
    ]


def test_malformed_game_identifier_fails_clearly(tmp_path):
    path = tmp_path / "malformed.csv"
    path.write_text(
        "Date,Away,Away Score,Home,Home Score,Status\n"
        "2025-04-01,Same,2,Same,5,Final\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed game identifier"):
        lrs.load_games(path)


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
    assert r.split["train_period"][1] < r.split["test_period"][0]
    for m in r.comparison:
        assert 0.45 <= m["accuracy"] <= 0.65   # MLB 誠實可信區間
        assert 0.20 <= m["brier_score"] <= 0.30
    out = tmp_path / "report"
    written = lrs.write_reports(r, out)
    assert len(written) == 5
