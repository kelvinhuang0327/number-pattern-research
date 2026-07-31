"""
P228-A — Run Line Robustness & Calibration Paper-Only Scorecard（純標準庫）
================================================================================
針對 P226-A 已知結果（run line：Poisson team-rate 模型 test 期 accuracy 0.6008 /
Brier 0.2395，優於 0.5 coinflip baseline 的 Brier 0.2500）做「是否為單一 split
巧合、還是跨時間穩健」的檢驗，並嘗試 train-fold-only 機率校準。回答：

  1. P226-A run line 優勢是否在多個時間序 split / 時間窗上都成立？
  2. train-fold-only 校準（Platt-style logistic）能否改善 run line 的
     Brier / ECE？
  3. run line 訊號是否穩健到可供後續歷史研究，還是 split-specific？
  4. 是否能全程確定性、純本機、明確 paper-only？

**本檔不修改 `run_line_total_scorecard.py`（P226-A）**：split-grid 檢驗直接呼叫
P226-A 對外公開的 `run_scorecard(warmup, eval, train_frac=...)`（該函式本就支援
任意 `train_frac`，純函式重用、零重寫風險）。月度滾動窗與 train-fold-only 校準
需要 train fold 逐場中間值（P226-A 的 `run_scorecard()` 不對外暴露），故本檔另外
重新實作一份與 P226-A 完全等價的球隊得失分率 walk-forward（沿用 P226-A 定義的
常數與純函式：`RUN_SMOOTH_K` / `DEFAULT_LEAGUE_AVG_RUNS` / `DEFAULT_TRAIN_FRAC` /
`load_games` / `run_line_probabilities` / `settle_run_line` / `metrics`），並以
Gate 0 執行期斷言：在 P226-A 的預設 `train_frac` 上，本檔重新實作的 home_adv 與
test fold 逐場 raw p_home 必須與 P226-A 官方輸出逐場相等，確保重新實作與 P226-A
完全一致而非各說各話（手法比照 P227-A `total_calibration_scorecard.py`）。

**防洩漏設計（與 P226-A 一致）**：
  - 嚴格時間切分：每個 split / 時間窗的 train 期所有比賽日期 <= test 期最早日期。
  - 月度滾動窗為擴展視窗（expanding window）walk-forward：每個月的 train fold
    僅由「該月第一場比賽之前」的所有歷史比賽組成，home_adv 只用該 train fold
    重新擬合、凍結後套用該月 test fold（不使用未來月份資訊）。
  - run line 的盤口線值只作為 event threshold / settlement，絕不進入模型輸入
    特徵；美式賠率價格欄位全程不使用。
  - Platt 校準的 (a, b) 只用 train fold 擬合，凍結後套用 test fold；固定初始值
    與固定最大迭代次數，純標準庫 Newton-Raphson，確定性。

**範疇**：純本機歷史 / replay 描述性回測，非未來預測、非下注建議、非
production/live、非已證實 edge。
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from wbc_backend.recommendation.run_line_total_scorecard import (
    DEFAULT_LEAGUE_AVG_RUNS,
    DEFAULT_TRAIN_FRAC,
    RUN_SMOOTH_K,
    RLTGame,
    load_games,
    metrics,
    run_line_probabilities,
    run_scorecard as p226a_run_scorecard,
    settle_run_line,
)

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive backtest only; NO future prediction / hit-rate claim",
    "NO betting recommendation; NO EV/Kelly claim; NOT a proven edge",
    "NO live-market claim; NOT production; NOT real betting",
    "chronological split grid and monthly windows are deterministic and "
    "no-shuffle; no random search was performed",
    "Platt calibration (a, b) is fit on the train fold ONLY; never fit on "
    "run line price, odds, or market-implied probability",
    "run line spread is used ONLY as event threshold / settlement; American "
    "odds prices are never read by this module",
    "push rows are excluded from accuracy/Brier/ECE denominators",
    "this MVP does not compute bootstrap confidence intervals; robustness is "
    "assessed via a pre-registered fixed Brier near-tie tolerance only",
]

# ── 參數（皆為執行前已決定的固定常數，非依結果調整）───────────────────────────
SPLIT_GRID = [0.5, 0.6, 0.7]          # 50/50, 60/40 (=P226-A DEFAULT_TRAIN_FRAC), 70/30
MIN_TRAIN_ROWS_FOR_WINDOW = 300        # 月度滾動窗最小 train fold 場數門檻
MIN_TEST_ROWS_FOR_WINDOW = 20          # 沿用 P226-A run_scorecard 的最小評估量門檻
BRIER_NEAR_TIE_TOLERANCE = 0.005       # 預先設定的固定容忍帶；小於此差值視為統計上
                                        # 的 near-tie 而非方向性反轉（未依結果調整）

PLATT_INITIAL_A = 1.0
PLATT_INITIAL_B = 0.0
PLATT_MAX_ITER = 100
PLATT_TOL = 1e-10
PROB_CLIP_LO = 1e-6
PROB_CLIP_HI = 1.0 - 1e-6


# ── 數值工具（與 P227-A 同構，獨立實作以保持本檔自足）────────────────────────
def clip_prob(p: float, lo: float = PROB_CLIP_LO, hi: float = PROB_CLIP_HI) -> float:
    return max(lo, min(hi, p))


def logit(p: float) -> float:
    pc = clip_prob(p)
    return math.log(pc / (1.0 - pc))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def fit_platt(
    xs: list[float], ys: list[int],
    a0: float = PLATT_INITIAL_A, b0: float = PLATT_INITIAL_B,
    max_iter: int = PLATT_MAX_ITER, tol: float = PLATT_TOL,
) -> tuple[float, float]:
    """2 參數 Newton-Raphson 邏輯回歸：p=sigmoid(a*x+b)，x 為 raw p_home 的 logit。
    固定初始值與固定最大迭代次數，純標準庫確定性運算；若樣本為空則回傳初始值。"""
    if not xs:
        return a0, b0
    a, b = a0, b0
    for _ in range(max_iter):
        ps = [sigmoid(a * x + b) for x in xs]
        grad_a = sum((y - p) * x for x, y, p in zip(xs, ys, ps))
        grad_b = sum((y - p) for y, p in zip(ys, ps))
        w = [p * (1.0 - p) for p in ps]
        h_aa = sum(wi * xi * xi for wi, xi in zip(w, xs))
        h_ab = sum(wi * xi for wi, xi in zip(w, xs))
        h_bb = sum(w)
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-15:
            break
        delta_a = (h_bb * grad_a - h_ab * grad_b) / det
        delta_b = (h_aa * grad_b - h_ab * grad_a) / det
        a += delta_a
        b += delta_b
        if abs(delta_a) < tol and abs(delta_b) < tol:
            break
    return a, b


def reliability_bins(preds: list[float], ys: list[int], n_bins: int = 10) -> list[dict]:
    """依預測機率切 n_bins 個桶，回報每桶樣本數、平均預測機率、實際命中率、
    校準差距（|empirical - mean_predicted|）。凍結預測後才計算，純描述性診斷。"""
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in zip(preds, ys):
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, y))
    out: list[dict] = []
    for i, b in enumerate(bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        if not b:
            out.append({"bin_lo": round(lo, 2), "bin_hi": round(hi, 2), "n": 0,
                        "mean_predicted": None, "empirical_rate": None, "gap": None})
            continue
        mean_p = sum(p for p, _ in b) / len(b)
        emp = sum(y for _, y in b) / len(b)
        out.append({"bin_lo": round(lo, 2), "bin_hi": round(hi, 2), "n": len(b),
                    "mean_predicted": round(mean_p, 4), "empirical_rate": round(emp, 4),
                    "gap": round(abs(emp - mean_p), 4)})
    return out


# ── Split-grid（直接重用 P226-A 官方 run_scorecard，零重寫風險）──────────────
@dataclass
class SplitGridEntry:
    train_frac: float
    train_period: list
    test_period: list
    train_rows: int
    test_rows: int
    coinflip_accuracy: float
    coinflip_brier: float
    poisson_accuracy: float
    poisson_brier: float
    poisson_ece: float
    poisson_decided: int
    poisson_beats_coinflip_brier: bool
    brier_margin: float          # coinflip_brier - poisson_brier；正值＝poisson 較優


def run_split_grid(warmup_path: Path, eval_path: Path,
                    split_grid: list[float] = SPLIT_GRID) -> list[SplitGridEntry]:
    entries: list[SplitGridEntry] = []
    for frac in split_grid:
        result = p226a_run_scorecard(warmup_path, eval_path, train_frac=frac)
        rl = {m["model_name"]: m for m in result.market_comparison["run_line"]}
        coinflip, poisson = rl["baseline_coinflip_50pct"], rl["poisson_team_rate_model"]
        margin = coinflip["brier_score"] - poisson["brier_score"]
        entries.append(SplitGridEntry(
            train_frac=frac,
            train_period=list(result.split["train_period"]),
            test_period=list(result.split["test_period"]),
            train_rows=result.split["train_rows"], test_rows=result.split["test_rows"],
            coinflip_accuracy=coinflip["accuracy"], coinflip_brier=coinflip["brier_score"],
            poisson_accuracy=poisson["accuracy"], poisson_brier=poisson["brier_score"],
            poisson_ece=poisson["calibration_error"], poisson_decided=poisson["decided_count"],
            poisson_beats_coinflip_brier=poisson["brier_score"] < coinflip["brier_score"],
            brier_margin=round(margin, 6),
        ))
    return entries


def gate0_check(entries: list[SplitGridEntry]) -> dict:
    """結構性 Gate 0（適用任意輸入資料，含合成測試資料）：split grid 必須包含
    P226-A 的 DEFAULT_TRAIN_FRAC 錨點；回傳該錨點指標供報告使用。是否與 P226-A
    在「真實 tracked MLB 資料」上的已知報告數值一致，由
    `assert_gate0_matches_known_p226a_run_line_metrics()` 另外驗證（只套用於真實
    資料，不假設合成測試資料會重現同一組數字）。"""
    anchor = next((e for e in entries if abs(e.train_frac - DEFAULT_TRAIN_FRAC) < 1e-9), None)
    if anchor is None:
        raise RuntimeError(
            "GATE0_FAILED_NO_ANCHOR: split grid must include P226-A DEFAULT_TRAIN_FRAC"
        )
    return {
        "status": "GATE0_ANCHOR_PRESENT",
        "anchor_train_frac": anchor.train_frac,
        "train_period": anchor.train_period, "test_period": anchor.test_period,
        "train_rows": anchor.train_rows, "test_rows": anchor.test_rows,
        "coinflip_accuracy": anchor.coinflip_accuracy, "coinflip_brier": anchor.coinflip_brier,
        "poisson_accuracy": anchor.poisson_accuracy, "poisson_brier": anchor.poisson_brier,
        "poisson_ece": anchor.poisson_ece,
    }


# 已知 P226-A Run Line 報告數值（report/p226a_run_line_total_scorecard.json，
# PR#52／commit 4ec7130 merged 版本）；僅用於對「真實 tracked MLB 資料」的 Gate 0
# 驗證，不套用於合成測試資料（合成資料的指標本就不會、也不需要重現這組數字）。
KNOWN_P226A_COINFLIP_BRIER = 0.2500
KNOWN_P226A_POISSON_ACCURACY = 0.6008
KNOWN_P226A_POISSON_BRIER = 0.2395


def assert_gate0_matches_known_p226a_run_line_metrics(gate0: dict) -> dict:
    """僅供真實資料流程（CLI / 真實資料測試）呼叫：驗證 Gate 0 錨點指標與 P226-A
    已知報告數值一致（既有報告精度內），一致則回傳升級狀態後的 gate0 dict。"""
    ok = (
        abs(gate0["coinflip_brier"] - KNOWN_P226A_COINFLIP_BRIER) < 1e-4
        and abs(gate0["poisson_accuracy"] - KNOWN_P226A_POISSON_ACCURACY) < 1e-3
        and abs(gate0["poisson_brier"] - KNOWN_P226A_POISSON_BRIER) < 1e-3
    )
    if not ok:
        raise RuntimeError(
            "GATE0_FAILED_MISMATCH: expected coinflip_brier=0.2500 poisson_accuracy=0.6008 "
            f"poisson_brier=0.2395, got coinflip_brier={gate0['coinflip_brier']:.4f} "
            f"poisson_accuracy={gate0['poisson_accuracy']:.4f} poisson_brier={gate0['poisson_brier']:.4f}"
        )
    upgraded = dict(gate0)
    upgraded["status"] = "GATE0_REPRODUCED_P226A_RUN_LINE_METRICS"
    return upgraded


# ── Walk-forward 重現（僅供月度滾動窗與校準取用 train fold 中間值）───────────
@dataclass
class RawRunLineRow:
    game: RLTGame
    lam_home_raw: float
    lam_away_raw: float


def walk_forward_raw_rows(warmup: list[RLTGame], evalg: list[RLTGame]) -> list[RawRunLineRow]:
    """重新推導 P226-A 賽前 raw 球隊得失分率 λ（單一循序 pass，狀態於賽後才更新）。
    重新實作（非 import 內部私有狀態）僅為了取得 P226-A `run_scorecard()` 不對外
    暴露的 train fold 逐場中間值；公式與常數皆直接引用本模組頂部 import 的
    P226-A 定義，且從未修改 `run_line_total_scorecard.py`。"""
    runs_for_sum: dict[str, float] = {}
    runs_for_n: dict[str, int] = {}
    runs_against_sum: dict[str, float] = {}
    runs_against_n: dict[str, int] = {}
    running_sum = 0.0
    running_count = 0

    def league_avg() -> float:
        return running_sum / running_count if running_count else DEFAULT_LEAGUE_AVG_RUNS

    def team_off_rate(team: str) -> float:
        avg = league_avg()
        s, n = runs_for_sum.get(team, 0.0), runs_for_n.get(team, 0)
        return (s + RUN_SMOOTH_K * avg) / (n + RUN_SMOOTH_K)

    def team_def_rate(team: str) -> float:
        avg = league_avg()
        s, n = runs_against_sum.get(team, 0.0), runs_against_n.get(team, 0)
        return (s + RUN_SMOOTH_K * avg) / (n + RUN_SMOOTH_K)

    def advance(g: RLTGame, collect: bool) -> Optional[RawRunLineRow]:
        avg = league_avg()
        off_h, def_h = team_off_rate(g.home), team_def_rate(g.home)
        off_a, def_a = team_off_rate(g.away), team_def_rate(g.away)
        lam_home_raw = (off_h * def_a) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        lam_away_raw = (off_a * def_h) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        out = RawRunLineRow(game=g, lam_home_raw=lam_home_raw, lam_away_raw=lam_away_raw) if collect else None
        nonlocal running_sum, running_count
        runs_for_sum[g.home] = runs_for_sum.get(g.home, 0.0) + g.home_score
        runs_for_n[g.home] = runs_for_n.get(g.home, 0) + 1
        runs_for_sum[g.away] = runs_for_sum.get(g.away, 0.0) + g.away_score
        runs_for_n[g.away] = runs_for_n.get(g.away, 0) + 1
        runs_against_sum[g.home] = runs_against_sum.get(g.home, 0.0) + g.away_score
        runs_against_n[g.home] = runs_against_n.get(g.home, 0) + 1
        runs_against_sum[g.away] = runs_against_sum.get(g.away, 0.0) + g.home_score
        runs_against_n[g.away] = runs_against_n.get(g.away, 0) + 1
        running_sum += g.home_score + g.away_score
        running_count += 2
        return out

    for g in warmup:
        advance(g, collect=False)
    return [advance(g, collect=True) for g in evalg]


def _home_adv_from_rows(rows: list[RawRunLineRow]) -> float:
    sum_actual_home = sum(r.game.home_score for r in rows)
    sum_raw_home = sum(r.lam_home_raw for r in rows)
    return sum_actual_home / sum_raw_home if sum_raw_home > 0 else 1.0


def _raw_p_home(r: RawRunLineRow, home_adv: float) -> Optional[float]:
    g = r.game
    if g.spread_home is None:
        return None
    p_home, _, _ = run_line_probabilities(r.lam_home_raw * home_adv, r.lam_away_raw, g.spread_home)
    return p_home


# ── 月度滾動窗（擴展視窗 walk-forward）───────────────────────────────────────
@dataclass
class WindowEntry:
    window_id: str
    status: str  # "EVALUATED" | "SKIPPED_INSUFFICIENT_TRAIN" | "SKIPPED_INSUFFICIENT_TEST"
    train_rows: int
    test_rows: int
    home_adv: Optional[float] = None
    coinflip_brier: Optional[float] = None
    poisson_accuracy: Optional[float] = None
    poisson_brier: Optional[float] = None
    poisson_ece: Optional[float] = None
    poisson_beats_coinflip_brier: Optional[bool] = None
    brier_margin: Optional[float] = None


def run_monthly_windows(warmup_path: Path, eval_path: Path) -> list[WindowEntry]:
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    rows = walk_forward_raw_rows(warmup, evalg)

    month_indices: dict[tuple[int, int], list[int]] = {}
    for idx, r in enumerate(rows):
        if r.game.spread_home is None:
            continue
        key = (r.game.dt.year, r.game.dt.month)
        month_indices.setdefault(key, []).append(idx)

    entries: list[WindowEntry] = []
    for key in sorted(month_indices):
        test_idx = month_indices[key]
        first_idx = test_idx[0]
        train_subset = rows[:first_idx]          # 擴展視窗：該月第一場之前的全部歷史
        window_id = f"{key[0]:04d}-{key[1]:02d}"

        if len(train_subset) < MIN_TRAIN_ROWS_FOR_WINDOW:
            entries.append(WindowEntry(window_id=window_id, status="SKIPPED_INSUFFICIENT_TRAIN",
                                        train_rows=len(train_subset), test_rows=len(test_idx)))
            continue

        home_adv = _home_adv_from_rows(train_subset)
        preds: list[float] = []
        ys: list[int] = []
        for idx in test_idx:
            r = rows[idx]
            g = r.game
            p_home = _raw_p_home(r, home_adv)
            actual = settle_run_line(g.home_score, g.away_score, g.spread_home)
            if actual == "PUSH":
                continue
            preds.append(p_home)
            ys.append(1 if actual == "HOME" else 0)

        if len(preds) < MIN_TEST_ROWS_FOR_WINDOW:
            entries.append(WindowEntry(window_id=window_id, status="SKIPPED_INSUFFICIENT_TEST",
                                        train_rows=len(train_subset), test_rows=len(preds)))
            continue

        m = metrics(preds, ys)
        coinflip_brier = metrics([0.5] * len(ys), ys)["brier_score"]
        entries.append(WindowEntry(
            window_id=window_id, status="EVALUATED",
            train_rows=len(train_subset), test_rows=len(preds), home_adv=round(home_adv, 6),
            coinflip_brier=coinflip_brier,
            poisson_accuracy=m["accuracy"], poisson_brier=m["brier_score"],
            poisson_ece=m["calibration_error"],
            poisson_beats_coinflip_brier=m["brier_score"] < coinflip_brier,
            brier_margin=round(coinflip_brier - m["brier_score"], 6),
        ))
    return entries


# ── Train-fold-only Platt 校準（於 P226-A 預設 split 上）─────────────────────
@dataclass
class CalibrationResult:
    train_frac: float
    platt_a: float
    platt_b: float
    train_n: int
    train_decided_n: int
    raw: dict
    calibrated: dict
    calibration_beats_raw_brier: bool
    calibration_beats_raw_ece: bool
    reliability_raw: list
    reliability_calibrated: list
    predictions: list


def run_train_fold_calibration(warmup_path: Path, eval_path: Path,
                                train_frac: float = DEFAULT_TRAIN_FRAC) -> CalibrationResult:
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    rows = walk_forward_raw_rows(warmup, evalg)

    split = int(len(rows) * train_frac)
    train_rows, test_rows = rows[:split], rows[split:]
    home_adv = _home_adv_from_rows(train_rows)

    # Gate 0 cross-check：P226-A DEFAULT_TRAIN_FRAC 上，home_adv 與 test fold 逐場
    # raw p_home 必須與 P226-A 官方輸出逐場相等（確保重新實作與 P226-A 完全一致）。
    if abs(train_frac - DEFAULT_TRAIN_FRAC) < 1e-9:
        official = p226a_run_scorecard(warmup_path, eval_path, train_frac=train_frac)
        if abs(home_adv - official.home_adv) > 1e-9:
            raise RuntimeError(
                "GATE0_FAILED_HOME_ADV_DIVERGED: P228-A calibration replica home_adv "
                f"({home_adv!r}) != P226-A official home_adv ({official.home_adv!r})"
            )
        official_rl_poisson = [
            p["predicted_primary_probability"] for p in official.predictions
            if p["market"] == "run_line" and p["model_name"] == "poisson_team_rate_model"
        ]
        replica_raw = [_raw_p_home(r, home_adv) for r in test_rows if r.game.spread_home is not None]
        if len(official_rl_poisson) != len(replica_raw):
            raise RuntimeError(
                "GATE0_FAILED_ROW_COUNT_DIVERGED: P228-A calibration replica test-fold "
                "row count diverged from P226-A official output"
            )
        for off_p, my_p in zip(official_rl_poisson, replica_raw):
            if abs(off_p - round(my_p, 6)) > 1e-6:
                raise RuntimeError(
                    "GATE0_FAILED_RAW_PROB_DIVERGED: P228-A calibration replica raw p_home "
                    "diverged from P226-A official output"
                )

    train_x: list[float] = []
    train_y: list[int] = []
    for r in train_rows:
        p_home = _raw_p_home(r, home_adv)
        if p_home is None:
            continue
        actual = settle_run_line(r.game.home_score, r.game.away_score, r.game.spread_home)
        if actual == "PUSH":
            continue
        train_x.append(logit(p_home))
        train_y.append(1 if actual == "HOME" else 0)

    platt_a, platt_b = fit_platt(train_x, train_y)

    predictions: list[dict] = []
    raw_preds: list[float] = []
    cal_preds: list[float] = []
    ys: list[int] = []
    for r in test_rows:
        p_home_raw = _raw_p_home(r, home_adv)
        if p_home_raw is None:
            continue
        g = r.game
        actual = settle_run_line(g.home_score, g.away_score, g.spread_home)
        is_push = actual == "PUSH"
        p_home_cal = sigmoid(platt_a * logit(p_home_raw) + platt_b)
        predictions.append({
            "game_id": f"{g.date}_{g.away}@{g.home}", "game_date": g.date,
            "home_team": g.home, "away_team": g.away,
            "market": "run_line", "line_value": g.spread_home,
            "split_train_frac": train_frac,
            "window_id": f"{g.dt.year:04d}-{g.dt.month:02d}",
            "raw_predicted_home_probability": round(p_home_raw, 6),
            "calibrated_predicted_home_probability": round(p_home_cal, 6),
            "actual_side": actual, "is_push": is_push,
            "raw_correct": None if is_push else int((p_home_raw >= 0.5) == (actual == "HOME")),
            "calibrated_correct": None if is_push else int((p_home_cal >= 0.5) == (actual == "HOME")),
            "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY",
            "source_file": Path(eval_path).name,
        })
        if is_push:
            continue
        raw_preds.append(p_home_raw)
        cal_preds.append(p_home_cal)
        ys.append(1 if actual == "HOME" else 0)

    m_raw = metrics(raw_preds, ys)
    m_cal = metrics(cal_preds, ys)

    return CalibrationResult(
        train_frac=train_frac, platt_a=platt_a, platt_b=platt_b,
        train_n=len(train_rows), train_decided_n=len(train_x),
        raw={"accuracy": m_raw["accuracy"], "brier_score": m_raw["brier_score"],
             "calibration_error": m_raw["calibration_error"], "decided_count": m_raw["n"]},
        calibrated={"accuracy": m_cal["accuracy"], "brier_score": m_cal["brier_score"],
                    "calibration_error": m_cal["calibration_error"], "decided_count": m_cal["n"]},
        calibration_beats_raw_brier=m_cal["brier_score"] < m_raw["brier_score"],
        calibration_beats_raw_ece=m_cal["calibration_error"] < m_raw["calibration_error"],
        reliability_raw=reliability_bins(raw_preds, ys),
        reliability_calibrated=reliability_bins(cal_preds, ys),
        predictions=predictions,
    )


# ── 穩健性結論（固定、預先設定規則；非依結果調整）────────────────────────────
def robustness_conclusion(split_entries: list[SplitGridEntry],
                           window_entries: list[WindowEntry]) -> dict:
    evaluated = [w for w in window_entries if w.status == "EVALUATED"]
    split_not_worse = [e for e in split_entries
                        if e.poisson_brier <= e.coinflip_brier + BRIER_NEAR_TIE_TOLERANCE]
    split_strict_win = [e for e in split_entries if e.poisson_beats_coinflip_brier]
    window_not_worse = [w for w in evaluated
                         if w.poisson_brier <= w.coinflip_brier + BRIER_NEAR_TIE_TOLERANCE]
    window_strict_win = [w for w in evaluated if w.poisson_beats_coinflip_brier]

    all_splits_not_worse = len(split_not_worse) == len(split_entries) and len(split_entries) > 0
    all_windows_not_worse = len(window_not_worse) == len(evaluated) and len(evaluated) > 0
    total_units = len(split_entries) + len(evaluated)
    total_strict_wins = len(split_strict_win) + len(window_strict_win)
    majority_strict_win = total_units > 0 and total_strict_wins >= 0.5 * total_units

    if all_splits_not_worse and all_windows_not_worse and majority_strict_win:
        label = "ROBUST_ENOUGH_FOR_FURTHER_HISTORICAL_RESEARCH"
    elif total_units > 0 and total_strict_wins >= 0.5 * total_units:
        label = "MIXED_SPLIT_SPECIFIC"
    else:
        label = "NOT_ROBUST"

    return {
        "brier_near_tie_tolerance": BRIER_NEAR_TIE_TOLERANCE,
        "split_grid_total": len(split_entries),
        "split_grid_strict_wins": len(split_strict_win),
        "split_grid_not_worse_within_tolerance": len(split_not_worse),
        "monthly_windows_evaluated": len(evaluated),
        "monthly_windows_skipped": len(window_entries) - len(evaluated),
        "monthly_windows_strict_wins": len(window_strict_win),
        "monthly_windows_not_worse_within_tolerance": len(window_not_worse),
        "label": label,
    }


# ── 結果容器 + 主流程 ────────────────────────────────────────────────────────
@dataclass
class RobustnessScorecardResult:
    gate0: dict
    split_grid: list
    monthly_windows: list
    calibration: CalibrationResult
    conclusion: dict


def run_robustness_scorecard(warmup_path: Path, eval_path: Path,
                              strict_gate0: bool = False) -> RobustnessScorecardResult:
    """`strict_gate0=True`（真實 tracked MLB 資料流程使用）額外驗證 Gate 0 錨點
    是否重現 P226-A 已知報告數值；預設 False（供合成測試資料使用，只做結構性
    存在檢查，不假設合成資料會重現同一組數字）。"""
    split_entries = run_split_grid(warmup_path, eval_path)
    gate0 = gate0_check(split_entries)
    if strict_gate0:
        gate0 = assert_gate0_matches_known_p226a_run_line_metrics(gate0)
    window_entries = run_monthly_windows(warmup_path, eval_path)
    calibration = run_train_fold_calibration(warmup_path, eval_path)
    conclusion = robustness_conclusion(split_entries, window_entries)
    return RobustnessScorecardResult(
        gate0=gate0, split_grid=split_entries, monthly_windows=window_entries,
        calibration=calibration, conclusion=conclusion,
    )


# ── 報告輸出 ─────────────────────────────────────────────────────────────────
def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def write_reports(result: RobustnessScorecardResult, out_dir: Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # splits.csv — split-grid + monthly windows 統一表
    splits_p = out / "p228a_run_line_robustness_splits.csv"
    split_fields = ["split_type", "split_id", "status", "train_rows", "test_rows",
                     "home_adv", "coinflip_brier", "poisson_accuracy", "poisson_brier",
                     "poisson_ece", "poisson_beats_coinflip_brier", "brier_margin"]
    with open(splits_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=split_fields)
        w.writeheader()
        for e in result.split_grid:
            w.writerow({
                "split_type": "chronological_fraction", "split_id": f"train_frac={e.train_frac}",
                "status": "EVALUATED", "train_rows": e.train_rows, "test_rows": e.test_rows,
                "home_adv": "", "coinflip_brier": e.coinflip_brier,
                "poisson_accuracy": e.poisson_accuracy, "poisson_brier": e.poisson_brier,
                "poisson_ece": e.poisson_ece,
                "poisson_beats_coinflip_brier": e.poisson_beats_coinflip_brier,
                "brier_margin": e.brier_margin,
            })
        for win in result.monthly_windows:
            w.writerow({
                "split_type": "monthly_window", "split_id": win.window_id,
                "status": win.status, "train_rows": win.train_rows, "test_rows": win.test_rows,
                "home_adv": win.home_adv if win.home_adv is not None else "",
                "coinflip_brier": win.coinflip_brier if win.coinflip_brier is not None else "",
                "poisson_accuracy": win.poisson_accuracy if win.poisson_accuracy is not None else "",
                "poisson_brier": win.poisson_brier if win.poisson_brier is not None else "",
                "poisson_ece": win.poisson_ece if win.poisson_ece is not None else "",
                "poisson_beats_coinflip_brier": win.poisson_beats_coinflip_brier
                if win.poisson_beats_coinflip_brier is not None else "",
                "brier_margin": win.brier_margin if win.brier_margin is not None else "",
            })
    written.append(splits_p)

    # predictions.csv — 主 split（P226-A DEFAULT_TRAIN_FRAC）逐場 raw + 校準預測
    pred_p = out / "p228a_run_line_robustness_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(result.calibration.predictions[0].keys()) if result.calibration.predictions else [
            "game_id", "game_date", "home_team", "away_team", "market", "line_value",
            "split_train_frac", "window_id", "raw_predicted_home_probability",
            "calibrated_predicted_home_probability", "actual_side", "is_push",
            "raw_correct", "calibrated_correct", "learning_guard_status", "source_file",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(result.calibration.predictions)
    written.append(pred_p)

    # scorecard.json
    json_p = out / "p228a_run_line_robustness_scorecard.json"
    payload = {
        "task": "P228-A run line robustness & calibration paper-only scorecard",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "disclaimers": DISCLAIMERS,
        "gate0_reproduction": result.gate0,
        "split_grid": [vars(e) for e in result.split_grid],
        "monthly_windows": [vars(w) for w in result.monthly_windows],
        "calibration": {
            "train_frac": result.calibration.train_frac,
            "platt_a": result.calibration.platt_a, "platt_b": result.calibration.platt_b,
            "train_n": result.calibration.train_n,
            "train_decided_n": result.calibration.train_decided_n,
            "raw": result.calibration.raw, "calibrated": result.calibration.calibrated,
            "calibration_beats_raw_brier": result.calibration.calibration_beats_raw_brier,
            "calibration_beats_raw_ece": result.calibration.calibration_beats_raw_ece,
            "reliability_raw": result.calibration.reliability_raw,
            "reliability_calibrated": result.calibration.reliability_calibrated,
        },
        "robustness_conclusion": result.conclusion,
    }
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    # scorecard.md
    md_p = out / "p228a_run_line_robustness_scorecard.md"
    md: list[str] = []
    md.append("# P228-A — Run Line Robustness & Calibration Paper-Only Scorecard\n")
    md.append("> **僅本機歷史 / replay 描述性回測。** 非未來預測、非下注建議、"
              "無 EV/Kelly 宣稱、無 live 市場宣稱、無 production/DB 變更、非已證實 edge。\n")
    md.append("## 範疇聲明")
    for d in DISCLAIMERS:
        md.append(f"- {d}")
    md.append("")

    g0 = result.gate0
    md.append("## Gate 0 — P226-A Run Line 重現")
    md.append(f"- 錨點 train_frac=`{g0['anchor_train_frac']}`；訓練期 `{g0['train_period'][0]}`→"
              f"`{g0['train_period'][1]}`（{g0['train_rows']} 場）；"
              f"測試期 `{g0['test_period'][0]}`→`{g0['test_period'][1]}`（{g0['test_rows']} 場）")
    md.append(f"- coinflip baseline：accuracy={_fnum(g0['coinflip_accuracy'])}、"
              f"brier={_fnum(g0['coinflip_brier'])}")
    md.append(f"- poisson_team_rate_model：accuracy={_fnum(g0['poisson_accuracy'])}、"
              f"brier={_fnum(g0['poisson_brier'])}、ECE={_fnum(g0['poisson_ece'])}")
    md.append(f"- **Gate 0 狀態**：`{g0['status']}`\n")

    md.append("## 1. Chronological Split Grid（無 shuffle、預先設定）")
    md.append("| train_frac | train_rows | test_rows | test_period | coinflip_brier | "
              "poisson_accuracy | poisson_brier | poisson_ece | beats_coinflip | brier_margin |")
    md.append("|--:|--:|--:|---|--:|--:|--:|--:|:--:|--:|")
    for e in result.split_grid:
        md.append(f"| {e.train_frac} | {e.train_rows} | {e.test_rows} | "
                  f"{e.test_period[0]}→{e.test_period[1]} | {_fnum(e.coinflip_brier)} | "
                  f"{_fnum(e.poisson_accuracy)} | {_fnum(e.poisson_brier)} | {_fnum(e.poisson_ece)} | "
                  f"{'YES' if e.poisson_beats_coinflip_brier else 'no'} | {_fnum(e.brier_margin, 6)} |")
    md.append("")

    md.append("## 2. Monthly Rolling Windows（擴展視窗 walk-forward，"
              f"train>={MIN_TRAIN_ROWS_FOR_WINDOW} 場 / test>={MIN_TEST_ROWS_FOR_WINDOW} 場 才評分）")
    md.append("| window | status | train_rows | test_rows | home_adv | coinflip_brier | "
              "poisson_accuracy | poisson_brier | poisson_ece | beats_coinflip | brier_margin |")
    md.append("|---|---|--:|--:|--:|--:|--:|--:|--:|:--:|--:|")
    for w in result.monthly_windows:
        if w.status != "EVALUATED":
            md.append(f"| {w.window_id} | {w.status} | {w.train_rows} | {w.test_rows} | "
                      "— | — | — | — | — | — | — |")
            continue
        md.append(f"| {w.window_id} | {w.status} | {w.train_rows} | {w.test_rows} | "
                  f"{_fnum(w.home_adv)} | {_fnum(w.coinflip_brier)} | {_fnum(w.poisson_accuracy)} | "
                  f"{_fnum(w.poisson_brier)} | {_fnum(w.poisson_ece)} | "
                  f"{'YES' if w.poisson_beats_coinflip_brier else 'no'} | {_fnum(w.brier_margin, 6)} |")
    md.append("")

    c = result.calibration
    md.append("## 3. Train-Fold-Only Platt Calibration（於 P226-A 預設 split 上）")
    md.append(f"- 擬合樣本（train fold 排除 push）：{c.train_decided_n} 場（train fold 共 {c.train_n} 場）")
    md.append(f"- 凍結係數：`a={c.platt_a:.6f}`、`b={c.platt_b:.6f}`")
    md.append("| | accuracy | brier_score | calibration_error(ECE) | decided_count |")
    md.append("|---|--:|--:|--:|--:|")
    md.append(f"| raw (P226-A Poisson) | {_fnum(c.raw['accuracy'])} | {_fnum(c.raw['brier_score'])} | "
              f"{_fnum(c.raw['calibration_error'])} | {c.raw['decided_count']} |")
    md.append(f"| calibrated (Platt) | {_fnum(c.calibrated['accuracy'])} | "
              f"{_fnum(c.calibrated['brier_score'])} | {_fnum(c.calibrated['calibration_error'])} | "
              f"{c.calibrated['decided_count']} |")
    md.append(f"\n**校準是否改善 Brier**：`{c.calibration_beats_raw_brier}`　"
              f"**校準是否改善 ECE**：`{c.calibration_beats_raw_ece}`\n")

    md.append("### Reliability Diagnostics（10 bins，凍結預測後計算）")
    md.append("| bin | n(raw) | mean_pred(raw) | empirical(raw) | gap(raw) | "
              "n(cal) | mean_pred(cal) | empirical(cal) | gap(cal) |")
    md.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for br, bc in zip(c.reliability_raw, c.reliability_calibrated):
        md.append(f"| [{br['bin_lo']},{br['bin_hi']}) | {br['n']} | {_fnum(br['mean_predicted'])} | "
                  f"{_fnum(br['empirical_rate'])} | {_fnum(br['gap'])} | {bc['n']} | "
                  f"{_fnum(bc['mean_predicted'])} | {_fnum(bc['empirical_rate'])} | {_fnum(bc['gap'])} |")
    md.append("")

    conc = result.conclusion
    md.append("## 4. 穩健性結論")
    md.append(f"- 判定規則（預先設定、非依結果調整）：Brier near-tie 容忍帶＝"
              f"`{conc['brier_near_tie_tolerance']}`；ROBUST 需「所有 split-grid 與所有已評分月度窗"
              "皆不劣於 coinflip 超過容忍帶」且「多數（split+window 合計）為嚴格勝出」；"
              "否則若嚴格勝出仍佔多數則為 MIXED/SPLIT-SPECIFIC；否則 NOT ROBUST。")
    md.append(f"- split-grid：{conc['split_grid_strict_wins']}/{conc['split_grid_total']} 嚴格勝出、"
              f"{conc['split_grid_not_worse_within_tolerance']}/{conc['split_grid_total']} 不劣於容忍帶")
    md.append(f"- monthly windows：{conc['monthly_windows_strict_wins']}/{conc['monthly_windows_evaluated']} "
              f"嚴格勝出、{conc['monthly_windows_not_worse_within_tolerance']}/"
              f"{conc['monthly_windows_evaluated']} 不劣於容忍帶"
              f"（另有 {conc['monthly_windows_skipped']} 個月因樣本不足被排除評分）")
    md.append(f"- **最終判定**：`{conc['label']}`\n")

    md.append("## 限制")
    md.append("- 本 MVP 未計算 bootstrap 信賴區間；穩健性僅以固定容忍帶＋split/window 計數判定，"
              "非嚴格統計檢定。")
    md.append("- 月度視窗樣本數隨賽季推進而增長（train fold 為擴展視窗），"
              "越早的月份 train fold 越薄、估計越不穩定，已用 "
              f"`MIN_TRAIN_ROWS_FOR_WINDOW={MIN_TRAIN_ROWS_FOR_WINDOW}` 排除過薄的月份"
              "（2025-03/04 因此被排除）。")
    md.append("- Platt 校準只在 P226-A 預設 60/40 split 上驗證，未對 split-grid 每個切分重跑校準。")
    md.append("- 單一球季（2025）＋暖身季（2024）資料，跨球季穩健性未經檢驗。")
    md.append("")
    md.append("## 免責聲明")
    md.append("- **HISTORICAL**：全部數字皆為歷史回測結果。")
    md.append("- **PAPER-ONLY**：無真實下注、無資金部署。")
    md.append("- **NOT LIVE**：無即時市場串接。")
    md.append("- **NOT PRODUCTION**：無 production/DB/registry 變更、無發布。")
    md.append("- **NOT REAL BETTING**：無下注建議、無 EV/Kelly 宣稱。")
    md.append("- **NOT A PROVEN EDGE**：本報告不構成已證實的下注優勢宣稱，"
              "僅為描述性、可重現的歷史統計分析，供後續研究參考。")
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
