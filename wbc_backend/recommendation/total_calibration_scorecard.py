"""
P227-A — Total Over-Dispersion Calibration（Paper-Only MVP，純標準庫、train-fold-only）
================================================================================
針對 P226-A 已知限制（`run_line_total_scorecard.py`：total 市場獨立 Poisson 假設
過度自信、Brier 0.2637 輸給 0.5 coinflip baseline 的 0.2500）做兩個 train-fold-only
的機率校準嘗試，回答：

  1. train-only 變異數膨脹（variance inflation）或 Platt/logistic 校準，
     能否改善 P226-A total 的 Brier / ECE？
  2. 本檔是否能先精確重現 P226-A Gate 0 指標，再談校準？
  3. 若兩個方法都打不贏 coinflip Brier 0.2500，能否誠實回報 no-improvement
     而不誇大？

**本檔不修改 `run_line_total_scorecard.py`（P226-A）**：為了在 train fold 上取得
P226-A 的賽前 walk-forward λ_total / raw p_over（P226-A 的 `run_scorecard()` 只回傳
test-period 的彙總結果，不對外暴露 train fold 逐場中間值），本檔重新實作一份與
P226-A 完全等價的球隊得失分率 walk-forward（沿用 P226-A 的常數與純函式：
`RUN_SMOOTH_K` / `DEFAULT_TRAIN_FRAC` / `DEFAULT_LEAGUE_AVG_RUNS` / `load_games` /
`total_probabilities` / `settle_total` / `metrics`），並以 Gate 0 測試斷言兩者在
test fold 上的 λ_total 與 raw p_over 逐場相等，確保重新實作與 P226-A 完全一致而
非各說各話。

**兩個校準手臂（皆 train-fold-only fit、確定性、零外部依賴）**：
  Method A — variance_inflation_normal：
    `phi_hat = sum((actual_total_i - lambda_total_i)^2) / sum(lambda_total_i)`
    （只用 train fold；只用比分與 P226-A raw λ_total，不用 O/U 線值擬合）。
    預測改用常態近似 `mu=lambda_total, variance=phi_hat*lambda_total`，
    `Phi` 以 `math.erf` 實作；整數線用連續性校正並保留
    `p_over + p_under + p_push = 1`。
  Method B — platt_logistic_calibration：
    對 P226-A raw Poisson `p_over` 的 logit 做 2 參數 Newton/IRLS 邏輯回歸
    （固定初始值 a=1.0,b=0.0、固定最大迭代次數），train-fold-only、排除 push 列；
    凍結後之 (a,b) 套用於 test fold。push 機率沿用原始 Poisson 模型輸出
    （Platt 只重新校準「非 push 條件下」over/under 的相對機率，不改動 push
    建模），故 `p_over_final=(1-p_push_raw)*p_over_calibrated`、
    `p_under_final=(1-p_push_raw)*(1-p_over_calibrated)`、`p_push_final=p_push_raw`，
    仍保證三者相加為 1。

**PIT-safety**：O/U 線值僅作 event threshold / settlement / evaluation，絕不進入
`phi_hat` 或 Platt 的擬合特徵；美式賠率價格欄位全程不使用。

**範疇**：純本機歷史 paper-only 回測，非未來預測、非下注建議、非 production/live。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from wbc_backend.recommendation.run_line_total_scorecard import (
    DEFAULT_LEAGUE_AVG_RUNS,
    DEFAULT_TRAIN_FRAC,
    RUN_SMOOTH_K,
    RLTGame,
    clip01,
    load_games,
    metrics,
    run_scorecard as p226a_run_scorecard,
    settle_total,
    total_probabilities,
)

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive backtest only; NO future prediction / hit-rate claim",
    "NO betting recommendation; NO EV/Kelly claim; NOT a proven edge",
    "NO live-market claim; NOT production; NOT real betting",
    "phi_hat and Platt (a,b) are fit on the train fold ONLY; never fit on O/U "
    "line, odds, or market-implied probability",
    "O/U line values are used ONLY as event threshold / settlement / evaluation; "
    "American odds prices are never read by this module",
    "push rows are excluded from accuracy/Brier/ECE denominators and from the "
    "Platt fit; push_count/push_rate reported separately",
]

CALIBRATION_MODEL_NAMES = ["variance_inflation_normal", "platt_logistic_calibration"]
REFERENCE_MODEL_NAMES = ["baseline_coinflip_50pct", "poisson_team_rate_model"]

PLATT_INITIAL_A = 1.0
PLATT_INITIAL_B = 0.0
PLATT_MAX_ITER = 100
PLATT_TOL = 1e-10
PROB_CLIP_LO = 1e-6
PROB_CLIP_HI = 1.0 - 1e-6


# ── 數值工具 ─────────────────────────────────────────────────────────────────
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


def norm_cdf(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0.0:
        return 1.0 if x >= mu else 0.0
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


# ── Walk-forward 重現（與 P226-A 等價，train fold 逐場中間值另外暴露）────────────
@dataclass
class TotalRow:
    game: RLTGame
    lambda_total: float
    actual_total: int
    p_over_raw: Optional[float]
    p_under_raw: Optional[float]
    p_push_raw: Optional[float]
    actual_side: Optional[str]


def _walk_forward_total_rows(warmup: list[RLTGame], evalg: list[RLTGame]) -> tuple[list[TotalRow], float]:
    """重新實作 P226-A 的球隊得失分率 walk-forward + home_adv 收盤形式比例校準，
    回傳含 train+test 全期的逐場 TotalRow（含賽前 lambda_total）與凍結後的 home_adv。
    公式與常數皆直接引用 `run_line_total_scorecard` 模組，僅迴圈結構重寫，
    以便在不修改 P226-A 檔案的前提下取得 train fold 的逐場中間值。"""
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

    def advance(g: RLTGame, collect: bool):
        avg = league_avg()
        off_h, def_h = team_off_rate(g.home), team_def_rate(g.home)
        off_a, def_a = team_off_rate(g.away), team_def_rate(g.away)
        lam_home_raw = (off_h * def_a) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        lam_away_raw = (off_a * def_h) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        out = (g, lam_home_raw, lam_away_raw) if collect else None
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
    raw_rows = [advance(g, collect=True) for g in evalg]

    split = int(len(raw_rows) * DEFAULT_TRAIN_FRAC)
    train_raw = raw_rows[:split]

    sum_actual_home = sum(g.home_score for g, _, _ in train_raw)
    sum_raw_home = sum(lam_home_raw for _, lam_home_raw, _ in train_raw)
    home_adv = sum_actual_home / sum_raw_home if sum_raw_home > 0 else 1.0

    rows: list[TotalRow] = []
    for g, lam_home_raw, lam_away_raw in raw_rows:
        lam_home = lam_home_raw * home_adv
        lam_away = lam_away_raw
        lam_total = lam_home + lam_away
        actual_total = g.home_score + g.away_score
        if g.ou_line is not None:
            p_over, p_under, p_push = total_probabilities(lam_home, lam_away, g.ou_line)
            actual_side = settle_total(g.home_score, g.away_score, g.ou_line)
        else:
            p_over = p_under = p_push = None
            actual_side = None
        rows.append(TotalRow(
            game=g, lambda_total=lam_total, actual_total=actual_total,
            p_over_raw=p_over, p_under_raw=p_under, p_push_raw=p_push,
            actual_side=actual_side,
        ))
    return rows, home_adv


# ── Method A: variance inflation / dispersion scaling ───────────────────────
def fit_phi_hat(train_rows: list[TotalRow]) -> float:
    """`phi_hat = sum((actual_total_i - lambda_total_i)^2) / sum(lambda_total_i)`，
    train fold 全部場次（不限有無 O/U 線），只用比分與 P226-A raw λ_total。"""
    num = sum((r.actual_total - r.lambda_total) ** 2 for r in train_rows)
    den = sum(r.lambda_total for r in train_rows)
    return num / den if den > 0 else 1.0


def total_probabilities_variance_inflated(
    lambda_total: float, phi_hat: float, ou_line: float
) -> tuple[float, float, float]:
    """常態近似：mu=lambda_total, variance=phi_hat*lambda_total。整數線用
    連續性校正（push = 落在 [line-0.5, line+0.5] 的機率質量），半線無 push。"""
    variance = max(0.0, phi_hat) * max(0.0, lambda_total)
    sigma = math.sqrt(variance)
    n = int(math.floor(ou_line))
    is_integer_line = float(ou_line) == float(n)
    if is_integer_line:
        p_over = 1.0 - norm_cdf(n + 0.5, lambda_total, sigma)
        p_under = norm_cdf(n - 0.5, lambda_total, sigma)
        p_push = 1.0 - p_over - p_under
    else:
        p_over = 1.0 - norm_cdf(ou_line, lambda_total, sigma)
        p_under = 1.0 - p_over
        p_push = 0.0
    return clip01(p_over), clip01(p_under), max(0.0, p_push)


# ── Method B: Platt / logistic calibration ──────────────────────────────────
def fit_platt(
    xs: list[float], ys: list[int],
    a0: float = PLATT_INITIAL_A, b0: float = PLATT_INITIAL_B,
    max_iter: int = PLATT_MAX_ITER, tol: float = PLATT_TOL,
) -> tuple[float, float]:
    """2 參數 Newton-Raphson 邏輯回歸：p=sigmoid(a*x+b)，x 為 raw p_over 的 logit。
    固定初始值與固定最大迭代次數，皆為純標準庫確定性運算。"""
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


def platt_p_over(a: float, b: float, p_over_raw: float) -> float:
    return sigmoid(a * logit(p_over_raw) + b)


# ── 結果容器 ─────────────────────────────────────────────────────────────────
@dataclass
class CalibrationResult:
    gate0_split: dict
    gate0_home_adv: float
    gate0_market_comparison: dict
    phi_hat: float
    platt_a: float
    platt_b: float
    calibration_train_n: int
    calibration_train_decided_n: int
    predictions: list[dict]
    model_comparison: list[dict]
    best_by_brier: str
    beats_poisson_brier: bool
    beats_coinflip_brier: bool


# ── 主流程 ───────────────────────────────────────────────────────────────────
def run_calibration_scorecard(
    warmup_path: Path, eval_path: Path, train_frac: float = DEFAULT_TRAIN_FRAC
) -> CalibrationResult:
    if train_frac != DEFAULT_TRAIN_FRAC:
        raise ValueError("P227-A only supports the P226-A default train_frac (Gate 0 parity)")

    # Gate 0：直接呼叫 P226-A 官方流程，取得可信賴的 test-period 彙總指標
    gate0 = p226a_run_scorecard(warmup_path, eval_path, train_frac=train_frac)

    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    rows, home_adv = _walk_forward_total_rows(warmup, evalg)
    if abs(home_adv - gate0.home_adv) > 1e-9:
        raise RuntimeError("P227-A replica home_adv diverged from P226-A Gate 0 home_adv")

    split = int(len(rows) * train_frac)
    train_rows, test_rows = rows[:split], rows[split:]

    # Gate 0 cross-check：test fold 逐場 raw p_over 必須與 P226-A 官方輸出逐場相等
    gate0_total_poisson_preds = [
        p for p in gate0.predictions
        if p["market"] == "total" and p["model_name"] == "poisson_team_rate_model"
    ]
    if len(gate0_total_poisson_preds) != sum(1 for r in test_rows if r.p_over_raw is not None):
        raise RuntimeError("P227-A replica test-fold row count diverged from P226-A Gate 0")
    for gate0_pred, r in zip(
        gate0_total_poisson_preds, (r for r in test_rows if r.p_over_raw is not None)
    ):
        if abs(round(r.p_over_raw, 6) - gate0_pred["predicted_primary_probability"]) > 1e-6:
            raise RuntimeError("P227-A replica raw p_over diverged from P226-A Gate 0")

    # Method A fit：train fold 全部場次（比分 + raw lambda_total），不看 O/U 線
    phi_hat = fit_phi_hat(train_rows)

    # Method B fit：train fold 有 O/U 線且非 push 的場次
    platt_train = [r for r in train_rows if r.p_over_raw is not None and r.actual_side != "PUSH"]
    xs = [logit(r.p_over_raw) for r in platt_train]
    ys = [1 if r.actual_side == "OVER" else 0 for r in platt_train]
    platt_a, platt_b = fit_platt(xs, ys)

    # Test fold 預測（兩個校準手臂）
    predictions: list[dict] = []
    records: dict[str, list[dict]] = {name: [] for name in CALIBRATION_MODEL_NAMES}
    for r in test_rows:
        if r.p_over_raw is None:
            continue
        g = r.game
        game_id = f"{g.date}_{g.away}@{g.home}"
        is_push = r.actual_side == "PUSH"

        p_over_a, p_under_a, p_push_a = total_probabilities_variance_inflated(
            r.lambda_total, phi_hat, g.ou_line
        )
        p_over_b_cal = platt_p_over(platt_a, platt_b, r.p_over_raw)
        p_push_b = r.p_push_raw
        p_over_b = (1.0 - p_push_b) * p_over_b_cal
        p_under_b = (1.0 - p_push_b) * (1.0 - p_over_b_cal)

        for name, (p_over, p_under, p_push) in (
            ("variance_inflation_normal", (p_over_a, p_under_a, p_push_a)),
            ("platt_logistic_calibration", (p_over_b, p_under_b, p_push_b)),
        ):
            predicted_side = "OVER" if p_over >= 0.5 else "UNDER"
            correct = None if is_push else int(predicted_side == r.actual_side)
            rec = {
                "predicted_primary_probability": p_over,
                "actual_side": r.actual_side, "is_push": is_push, "correct": correct,
            }
            records[name].append(rec)
            predictions.append({
                "game_id": game_id, "game_date": g.date,
                "home_team": g.home, "away_team": g.away,
                "market": "total", "line_value": g.ou_line,
                "model_name": name,
                "predicted_primary_probability": round(p_over, 6),
                "predicted_secondary_probability": round(p_under, 6),
                "predicted_push_probability": round(p_push, 6),
                "predicted_side": predicted_side, "actual_side": r.actual_side,
                "is_push": is_push, "correct": correct,
                "raw_poisson_p_over_p226a": round(r.p_over_raw, 6),
                "lambda_total_p226a": round(r.lambda_total, 6),
                "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY",
                "source_file": Path(eval_path).name,
            })

    def _summarize(name: str) -> dict:
        recs = records[name]
        decided = [rec for rec in recs if not rec["is_push"]]
        push_n = len(recs) - len(decided)
        preds = [rec["predicted_primary_probability"] for rec in decided]
        ys_ = [1 if rec["actual_side"] == "OVER" else 0 for rec in decided]
        m = metrics(preds, ys_)
        m.update({
            "market": "total", "model_name": name,
            "row_count": len(recs), "decided_count": len(decided),
            "push_count": push_n, "push_rate": push_n / len(recs) if recs else 0.0,
        })
        return m

    model_comparison: list[dict] = []
    for m in gate0.market_comparison["total"]:
        model_comparison.append({
            "market": "total", "model_name": m["model_name"],
            "row_count": m["row_count"], "decided_count": m["decided_count"],
            "push_count": m["push_count"], "push_rate": m["push_rate"],
            "accuracy": m["accuracy"], "log_loss": m["log_loss"],
            "brier_score": m["brier_score"], "calibration_error": m["calibration_error"],
            "notes": "reproduced from P226-A Gate 0 (unmodified upstream module)",
        })
    for name in CALIBRATION_MODEL_NAMES:
        m = _summarize(name)
        m["notes"] = "P227-A train-fold-only calibration of P226-A raw Poisson total"
        model_comparison.append(m)

    coinflip_brier = next(m["brier_score"] for m in model_comparison
                          if m["model_name"] == "baseline_coinflip_50pct")
    poisson_brier = next(m["brier_score"] for m in model_comparison
                         if m["model_name"] == "poisson_team_rate_model")
    best_by_brier = min(
        (m for m in model_comparison if m["brier_score"] is not None),
        key=lambda m: m["brier_score"],
    )["model_name"]
    best_brier_value = next(m["brier_score"] for m in model_comparison
                            if m["model_name"] == best_by_brier)

    return CalibrationResult(
        gate0_split=gate0.split, gate0_home_adv=gate0.home_adv,
        gate0_market_comparison=gate0.market_comparison,
        phi_hat=phi_hat, platt_a=platt_a, platt_b=platt_b,
        calibration_train_n=len(train_rows), calibration_train_decided_n=len(platt_train),
        predictions=predictions, model_comparison=model_comparison,
        best_by_brier=best_by_brier,
        beats_poisson_brier=best_brier_value < poisson_brier,
        beats_coinflip_brier=best_brier_value < coinflip_brier,
    )


# ── 報告輸出 ─────────────────────────────────────────────────────────────────
def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def write_reports(result: CalibrationResult, out_dir: Path) -> list[Path]:
    import csv
    import json

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    pred_p = out / "p227a_total_calibration_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(result.predictions[0].keys()) if result.predictions else [
            "game_id", "game_date", "home_team", "away_team", "market", "line_value",
            "model_name", "predicted_primary_probability", "predicted_secondary_probability",
            "predicted_push_probability", "predicted_side", "actual_side", "is_push",
            "correct", "raw_poisson_p_over_p226a", "lambda_total_p226a",
            "learning_guard_status", "source_file",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(result.predictions)
    written.append(pred_p)

    comp_fields = ["market", "model_name", "row_count", "decided_count", "push_count",
                   "push_rate", "accuracy", "log_loss", "brier_score", "calibration_error", "notes"]
    comp_p = out / "p227a_total_calibration_model_comparison.csv"
    with open(comp_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comp_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(result.model_comparison)
    written.append(comp_p)

    json_p = out / "p227a_total_calibration_scorecard.json"
    payload = {
        "task": "P227-A total over-dispersion calibration paper-only MVP",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "disclaimers": DISCLAIMERS,
        "gate0_reproduction": {
            "split": result.gate0_split, "home_adv": result.gate0_home_adv,
            "market_comparison": result.gate0_market_comparison,
        },
        "phi_hat": result.phi_hat,
        "platt_a": result.platt_a, "platt_b": result.platt_b,
        "calibration_train_n": result.calibration_train_n,
        "calibration_train_decided_n": result.calibration_train_decided_n,
        "model_comparison": result.model_comparison,
        "best_by_brier": result.best_by_brier,
        "beats_poisson_brier": result.beats_poisson_brier,
        "beats_coinflip_brier": result.beats_coinflip_brier,
    }
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    md_p = out / "p227a_total_calibration_scorecard.md"
    md: list[str] = []
    md.append("# P227-A — Total Over-Dispersion Calibration (Paper-Only MVP)\n")
    md.append("> **僅本機歷史 / replay 描述性回測。** 非未來預測、非下注建議、"
              "無 EV/Kelly 宣稱、無 live 市場宣稱、無 production/DB 變更、非已證實 edge。\n")
    md.append("## 範疇聲明")
    for d in DISCLAIMERS:
        md.append(f"- {d}")
    md.append("")
    sp = result.gate0_split
    md.append("## Gate 0 — P226-A 重現")
    md.append(f"- train_frac={sp['train_frac']}；訓練期 `{sp['train_period'][0]}`→"
              f"`{sp['train_period'][1]}`（{sp['train_rows']} 場）；"
              f"測試期 `{sp['test_period'][0]}`→`{sp['test_period'][1]}`（{sp['test_rows']} 場）")
    md.append(f"- home_adv（P226-A train-only 校準，逐場交叉核對相符）：`{result.gate0_home_adv:.4f}`")
    g0_total = {m["model_name"]: m for m in result.gate0_market_comparison["total"]}
    g0_rl = {m["model_name"]: m for m in result.gate0_market_comparison["run_line"]}
    md.append(f"- Total baseline_coinflip_50pct：accuracy={_fnum(g0_total['baseline_coinflip_50pct']['accuracy'])}"
              f"、brier={_fnum(g0_total['baseline_coinflip_50pct']['brier_score'])}")
    md.append(f"- Total poisson_team_rate_model：accuracy={_fnum(g0_total['poisson_team_rate_model']['accuracy'])}"
              f"、brier={_fnum(g0_total['poisson_team_rate_model']['brier_score'])}、"
              f"ECE={_fnum(g0_total['poisson_team_rate_model']['calibration_error'])}、"
              f"decided={g0_total['poisson_team_rate_model']['decided_count']}、"
              f"push={g0_total['poisson_team_rate_model']['push_count']}")
    md.append(f"- Run line poisson_team_rate_model（未變動，僅回歸檢查）：accuracy="
              f"{_fnum(g0_rl['poisson_team_rate_model']['accuracy'])}、"
              f"brier={_fnum(g0_rl['poisson_team_rate_model']['brier_score'])}\n")

    md.append("## Method A — Variance Inflation / Dispersion Scaling")
    md.append(f"- `phi_hat`（train fold {result.calibration_train_n} 場，不含 O/U 線輸入）："
              f"`{result.phi_hat:.6f}`")
    md.append("- 預測：常態近似 mu=lambda_total、variance=phi_hat*lambda_total、"
              "`Phi` 以 `math.erf` 實作；整數線用連續性校正並保留 p_over+p_under+p_push=1。\n")

    md.append("## Method B — Platt / Logistic Calibration")
    md.append(f"- 擬合樣本（train fold 排除 push）：{result.calibration_train_decided_n} 場")
    md.append(f"- 凍結係數：`a={result.platt_a:.6f}`、`b={result.platt_b:.6f}`")
    md.append("- 輸入：P226-A raw Poisson `p_over` 的 logit；輸出套用於 test fold raw p_over；"
              "push 機率沿用 P226-A 原始 Poisson 輸出（Platt 只重新校準條件式 over/under 分配）。\n")

    md.append("## 校準手臂比較（測試期，Total 市場）")
    md.append("| model | decided | push | accuracy | log_loss | brier_score | calibration_error |")
    md.append("|---|--:|--:|--:|--:|--:|--:|")
    for m in result.model_comparison:
        md.append(f"| {m['model_name']} | {m['decided_count']} | {m['push_count']} | "
                  f"{_fnum(m['accuracy'])} | {_fnum(m['log_loss'])} | {_fnum(m['brier_score'])} | "
                  f"{_fnum(m['calibration_error'])} |")
    md.append("")
    md.append(f"**最佳（Brier）**：`{result.best_by_brier}`")
    md.append(f"**是否優於 P226-A Poisson Brier 0.2637**：`{result.beats_poisson_brier}`")
    md.append(f"**是否優於 coinflip baseline Brier 0.2500**：`{result.beats_coinflip_brier}`\n")

    md.append("## 結論")
    if result.beats_coinflip_brier:
        md.append("- 至少一個 train-fold-only 校準手臂在測試期 Brier 優於 0.5 coinflip baseline，"
                  "顯示 over-dispersion 校準對 P226-A 獨立 Poisson 的過度自信問題有實質改善。")
    elif result.beats_poisson_brier:
        md.append("- 校準手臂修復了 P226-A Poisson 模型「輸給 coinflip」的問題（Brier 較 "
                  "poisson_team_rate_model 改善），但測試期 Brier 仍未優於 0.5 coinflip baseline"
                  "（0.2500）。誠實結論：over-dispersion 校準有幫助但尚不足以構成有效預測能力。")
    else:
        md.append("- **No-improvement**：本任務測試的兩個 train-fold-only 校準手臂（變異數膨脹、"
                  "Platt logistic）在測試期皆未能改善 P226-A poisson_team_rate_model 的 Brier，"
                  "亦未能打敗 0.5 coinflip baseline（0.2500）。這與 P227-F5A 設計審查的 "
                  "`GO_WITH_NO_IMPROVEMENT_FALLBACK` 預期情境一致：total 市場的過度自信問題"
                  "可能源自模型本身缺乏投手/牛棚層級資訊，而非機率校準層可單獨修復的形狀問題。"
                  "本報告誠實回報 no-improvement，不誇大、不宣稱 edge。")
    md.append("- 本報告為本機歷史 paper-only 回測，非未來預測、非下注建議、非 production/live、"
              "非已證實下注優勢。")
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
