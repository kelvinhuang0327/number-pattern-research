"""
P232-A — 2025 Single-Season Run Line Feature Ablation Scorecard（純標準庫）
================================================================================
針對 P226-A/P228-A 已重現、已驗證穩健的 run line Poisson team-rate 訊號
（test 期 accuracy 0.6008 / Brier 0.2395，優於 0.5 coinflip baseline 的
Brier 0.2500；train-fold-only Platt 校準後 Brier 0.2375），逐一移除
（ablate）該模型內可分離的特徵群組，檢驗訊號是否集中於單一脆弱特徵、還是
分散在多個特徵群組上都能存活。

**嚴格範疇（單一球季、僅本機、歷史 paper-only）**：
  - SINGLE-SEASON：僅使用 2025 一個球季（P230-A 盤點確認唯一同時具備比分＋
    run line 讓分/賠率的本機球季）；不做跨球季驗證，不擴充至 2024/2026。
  - 2025-ONLY / HISTORICAL PAPER-ONLY：純本機歷史 replay 回測，非未來預測。
  - PROVENANCE-UNVERIFIED：run line 讓分/賠率沿用 P226-A/P228-A/P230-A 已
    記載的已知限制——`mlb_odds_2025_real.csv` 為賽後單快照
    （is_verified_real=False），僅作 settlement / 讓分門檻使用，絕不進入
    模型輸入特徵。
  - NOT LIVE / NOT PRODUCTION / NOT REAL BETTING / NOT A PROVEN EDGE：無下注
    建議、無 EV/Kelly 宣稱、無 production/DB/registry 變更、無發布。

**本檔不修改 `run_line_total_scorecard.py`（P226-A）或
`run_line_robustness_scorecard.py`（P228-A）**：Gate 0（含 coinflip/poisson
baseline 與 train-fold-only Platt 校準）直接重用 P228-A 對外公開的
`run_split_grid()` / `gate0_check()` / `assert_gate0_matches_known_p226a_run_line_metrics()`
/ `run_train_fold_calibration()`，零重寫風險。特徵消融（本檔新增邏輯）另外
以與 P226-A/P228-A 完全等價的球隊得失分率 walk-forward 重新推導賽前元件
（off_h/def_h/off_a/def_a/league_avg），並以執行期斷言確保「全特徵」
（full_model）消融模式在 P226-A 預設 split 上與官方輸出逐指標相等，防止本檔
重新實作與既有已驗證模型各說各話。

**可消融的特徵群組（僅限 P226-A poisson_team_rate_model 實際使用的元件）**：
  - `ablate_offense_rate`   — 球隊滾動得分率（offense）替換為聯盟平均
  - `ablate_defense_rate`   — 球隊滾動失分率（defense）替換為聯盟平均
  - `ablate_team_strength_both` — offense + defense 同時替換為聯盟平均
    （本機模型沒有 Elo 特徵；此為「Elo / team strength」建議消融群組在本模型
    的最接近本機對應——移除全部球隊強度訊號，只留 home_adv）
  - `ablate_home_field`     — home_adv 固定為 1.0（移除主場優勢校準）

**不適用的建議特徵群組（本模型未使用，如實回報而非虛構特徵）**：
  - rest days（休息天數）——P226-A/P228-A poisson_team_rate_model 沒有休息
    天數輸入。
  - RSI / streak / recent-form —— 本模型使用的是收縮平滑滾動得失分率，並非
    RSI 或連勝/連敗 streak 特徵，本模型無獨立 RSI/streak 輸入可供消融。

**防洩漏設計（與 P226-A/P228-A 一致）**：
  - 嚴格時間切分：每個 split 的 train 期所有比賽日期 <= test 期最早日期。
  - run line 的盤口線值只作為 event threshold / settlement，絕不進入模型
    輸入特徵；美式賠率價格欄位全程不使用。
  - home_adv（每個消融模式獨立重新擬合，`ablate_home_field` 除外）只用 train
    fold 擬合，凍結後套用 test fold。
"""
from __future__ import annotations

import csv
import json
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
    settle_run_line,
)
from wbc_backend.recommendation.run_line_robustness_scorecard import (
    BRIER_NEAR_TIE_TOLERANCE,
    SPLIT_GRID,
    assert_gate0_matches_known_p226a_run_line_metrics,
    gate0_check,
    run_split_grid as p228a_run_split_grid,
    run_train_fold_calibration,
)

DISCLAIMERS = [
    "SINGLE-SEASON: 2025 only; NOT a multi-season validation (multi-season expansion remains HOLD per P230-A/P231-F5A)",
    "2025-ONLY: evaluation universe is data/mlb_2025/mlb_odds_2025_real.csv (2025 season) only",
    "HISTORICAL PAPER-ONLY: local historical / replay descriptive backtest; NO future prediction / hit-rate claim",
    "PROVENANCE-UNVERIFIED: run line spread/prices are a post-game unverified snapshot (is_verified_real=False); "
    "settlement / event-threshold reference only, NEVER a model input feature",
    "NOT LIVE: NO live-market claim; no real-time provider access",
    "NOT PRODUCTION: NO production / DB / registry mutation; NO publication",
    "NOT REAL BETTING: NO betting recommendation; NO EV/Kelly claim",
    "NOT A PROVEN EDGE: descriptive feature-ablation research artifact only, not a validated betting edge",
    "this is a feature-ablation study of the EXISTING P226-A/P228-A model architecture; it does not add, "
    "retrain, or search over new features",
]

# ── 已知 P228-A train-fold-only Platt 校準 Brier（report/p228a_run_line_robustness_scorecard.json，
# PR#53／commit f95225f merged 版本）；僅用於真實資料 Gate 0 驗證，不套用於合成測試資料。
KNOWN_P228A_CALIBRATED_BRIER = 0.2375

ABLATION_VARIANTS = [
    "full_model",
    "ablate_offense_rate",
    "ablate_defense_rate",
    "ablate_team_strength_both",
    "ablate_home_field",
]

ABLATION_VARIANT_NOTES = {
    "full_model": "control; identical feature set to P226-A poisson_team_rate_model (offense rate + "
    "defense rate + home_adv, all present)",
    "ablate_offense_rate": "rolling run-scoring (offense) rate replaced by league-average runs for both "
    "teams; defense rate and home_adv unchanged",
    "ablate_defense_rate": "rolling run-allowing (defense) rate replaced by league-average runs for both "
    "teams; offense rate and home_adv unchanged",
    "ablate_team_strength_both": "closest local analog to an 'Elo / team strength' ablation: both offense "
    "and defense rates replaced by league-average runs for both teams (only home_adv still "
    "differentiates home from away lambda)",
    "ablate_home_field": "home_adv fixed at 1.0 (no home-field calibration applied); offense/defense "
    "rates unchanged",
}

NOT_APPLICABLE_FEATURE_GROUPS = [
    {
        "group": "rest_days",
        "status": "NOT_PRESENT_IN_BASELINE_MODEL",
        "note": "P226-A/P228-A poisson_team_rate_model has no rest-day input; there is no rest-day "
        "feature in this model to ablate.",
    },
    {
        "group": "rsi_streak_recent_form",
        "status": "NOT_PRESENT_IN_BASELINE_MODEL",
        "note": "P226-A/P228-A poisson_team_rate_model uses a shrinkage-smoothed rolling run rate, not "
        "an RSI or win/loss streak feature; there is no separate RSI/streak input in this model to "
        "ablate.",
    },
]


# ── 賽前元件 walk-forward（與 P226-A/P228-A 完全等價，僅多回傳 off/def 元件供消融組裝）───
@dataclass
class ComponentRow:
    game: RLTGame
    off_h: float
    def_h: float
    off_a: float
    def_a: float
    avg: float


def walk_forward_components(warmup: list[RLTGame], evalg: list[RLTGame]) -> list[ComponentRow]:
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

    def advance(g: RLTGame, collect: bool) -> Optional[ComponentRow]:
        avg = league_avg()
        off_h, def_h = team_off_rate(g.home), team_def_rate(g.home)
        off_a, def_a = team_off_rate(g.away), team_def_rate(g.away)
        out = ComponentRow(game=g, off_h=off_h, def_h=def_h, off_a=off_a, def_a=def_a, avg=avg) if collect else None
        # 賽後更新（不洩漏）——與 P226-A/P228-A 完全相同的狀態更新，消融只影響
        # 「組裝 lambda 時讀取哪個元件」，不影響狀態本身如何被記錄。
        runs_for_sum[g.home] = runs_for_sum.get(g.home, 0.0) + g.home_score
        runs_for_n[g.home] = runs_for_n.get(g.home, 0) + 1
        runs_for_sum[g.away] = runs_for_sum.get(g.away, 0.0) + g.away_score
        runs_for_n[g.away] = runs_for_n.get(g.away, 0) + 1
        runs_against_sum[g.home] = runs_against_sum.get(g.home, 0.0) + g.away_score
        runs_against_n[g.home] = runs_against_n.get(g.home, 0) + 1
        runs_against_sum[g.away] = runs_against_sum.get(g.away, 0.0) + g.home_score
        runs_against_n[g.away] = runs_against_n.get(g.away, 0) + 1
        nonlocal running_sum, running_count
        running_sum += g.home_score + g.away_score
        running_count += 2
        return out

    for g in warmup:
        advance(g, collect=False)
    return [advance(g, collect=True) for g in evalg]


def assemble_raw_lambdas(row: ComponentRow, mode: str) -> tuple[float, float]:
    """依消融模式組裝賽前 raw lambda（賽前狀態，未套用 home_adv）。"""
    avg = row.avg if row.avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
    ablate_offense = mode in ("ablate_offense_rate", "ablate_team_strength_both")
    ablate_defense = mode in ("ablate_defense_rate", "ablate_team_strength_both")
    eff_off_h = avg if ablate_offense else row.off_h
    eff_off_a = avg if ablate_offense else row.off_a
    eff_def_h = avg if ablate_defense else row.def_h
    eff_def_a = avg if ablate_defense else row.def_a
    lam_home_raw = (eff_off_h * eff_def_a) / avg
    lam_away_raw = (eff_off_a * eff_def_h) / avg
    return lam_home_raw, lam_away_raw


# ── 每個 (variant, train_frac) 的評估結果 ────────────────────────────────────
@dataclass
class AblationResult:
    variant: str
    train_frac: float
    train_rows: int
    test_rows: int
    home_adv: float
    coinflip_accuracy: float
    coinflip_brier: float
    accuracy: Optional[float]
    brier_score: Optional[float]
    calibration_error: Optional[float]
    decided_count: int
    delta_brier_vs_full: Optional[float] = None
    delta_accuracy_vs_full: Optional[float] = None
    beats_coinflip_brier: Optional[bool] = None
    not_worse_within_tolerance: Optional[bool] = None
    predictions: list = field(default_factory=list, repr=False)


def run_ablation_variant(rows: list[ComponentRow], mode: str, train_frac: float) -> AblationResult:
    split = int(len(rows) * train_frac)
    train_rows, test_rows = rows[:split], rows[split:]

    if mode == "ablate_home_field":
        home_adv = 1.0
    else:
        sum_actual_home = sum(r.game.home_score for r in train_rows)
        sum_raw_home = sum(assemble_raw_lambdas(r, mode)[0] for r in train_rows)
        home_adv = sum_actual_home / sum_raw_home if sum_raw_home > 0 else 1.0

    predictions: list[dict] = []
    preds: list[float] = []
    ys: list[int] = []
    for r in test_rows:
        g = r.game
        if g.spread_home is None:
            continue
        lam_home_raw, lam_away_raw = assemble_raw_lambdas(r, mode)
        p_home, _p_away, p_push = run_line_probabilities(lam_home_raw * home_adv, lam_away_raw, g.spread_home)
        actual = settle_run_line(g.home_score, g.away_score, g.spread_home)
        is_push = actual == "PUSH"
        predictions.append({
            "game_id": f"{g.date}_{g.away}@{g.home}", "game_date": g.date,
            "home_team": g.home, "away_team": g.away,
            "market": "run_line", "line_value": g.spread_home,
            "variant": mode, "train_frac": train_frac,
            "predicted_home_probability": round(p_home, 6),
            "predicted_push_probability": round(p_push, 6),
            "predicted_side": "HOME" if p_home >= 0.5 else "AWAY",
            "actual_side": actual, "is_push": is_push,
            "correct": None if is_push else int((p_home >= 0.5) == (actual == "HOME")),
            "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY_SINGLE_SEASON_2025",
        })
        if is_push:
            continue
        # 與 P226-A 官方實作一致：指標由「已四捨五入至 6 位小數」的機率計算
        # （P226-A 的 rec["predicted_primary_probability"] 本就是 round(p_home, 6)
        # 後才進入 metrics()），確保 full_model 消融模式逐 bit 可重現官方數值。
        preds.append(round(p_home, 6))
        ys.append(1 if actual == "HOME" else 0)

    m = metrics(preds, ys)
    coinflip_m = metrics([0.5] * len(ys), ys) if ys else {"accuracy": None, "brier_score": None}

    return AblationResult(
        variant=mode, train_frac=train_frac,
        train_rows=len(train_rows), test_rows=len(test_rows),
        home_adv=round(home_adv, 6),
        coinflip_accuracy=coinflip_m["accuracy"], coinflip_brier=coinflip_m["brier_score"],
        accuracy=m["accuracy"], brier_score=m["brier_score"],
        calibration_error=m["calibration_error"], decided_count=m["n"],
        predictions=predictions,
    )


def compute_deltas_and_flags(results: list[AblationResult]) -> list[AblationResult]:
    full_by_frac = {r.train_frac: r for r in results if r.variant == "full_model"}
    for r in results:
        full = full_by_frac[r.train_frac]
        if r.variant == "full_model":
            r.delta_brier_vs_full = 0.0
            r.delta_accuracy_vs_full = 0.0
        else:
            r.delta_brier_vs_full = round(r.brier_score - full.brier_score, 6)
            r.delta_accuracy_vs_full = round(r.accuracy - full.accuracy, 6)
        r.beats_coinflip_brier = r.brier_score < r.coinflip_brier
        r.not_worse_within_tolerance = r.brier_score <= r.coinflip_brier + BRIER_NEAR_TIE_TOLERANCE
    return results


# ── 整體解讀（固定、預先設定規則；非依結果調整）──────────────────────────────
def interpret_results(results: list[AblationResult]) -> dict:
    variants = [v for v in ABLATION_VARIANTS if v != "full_model"]
    per_variant: dict[str, dict] = {}
    for v in variants:
        rows_v = [r for r in results if r.variant == v]
        all_beat = all(r.beats_coinflip_brier for r in rows_v)
        all_not_worse = all(r.not_worse_within_tolerance for r in rows_v)
        per_variant[v] = {
            "all_splits_beat_coinflip": all_beat,
            "all_splits_not_worse_within_tolerance": all_not_worse,
            "max_brier_degradation_vs_full": round(max(r.delta_brier_vs_full for r in rows_v), 6),
        }

    robust_variants = [v for v in variants if per_variant[v]["all_splits_beat_coinflip"]]
    fragile_variants = [v for v in variants if not per_variant[v]["all_splits_not_worse_within_tolerance"]]

    if len(robust_variants) == len(variants):
        label = "SIGNAL_PERSISTS_ACROSS_ABLATIONS"
    elif len(robust_variants) == 0:
        label = "SIGNAL_COLLAPSES_UNDER_ABLATION"
    elif 0 < len(robust_variants) < len(variants):
        label = "SIGNAL_DEPENDS_ON_FRAGILE_FEATURE_GROUP"
    else:
        label = "INCONCLUSIVE"

    return {
        "label": label,
        "per_variant": per_variant,
        "robust_variants": robust_variants,
        "fragile_variants": fragile_variants,
    }


# ── 結果容器 + 主流程 ────────────────────────────────────────────────────────
@dataclass
class FeatureAblationScorecardResult:
    gate0: dict
    ablation_results: list
    interpretation: dict
    warmup_rows: int
    eval_rows: int
    split_grid: list


def run_feature_ablation_scorecard(warmup_path: Path, eval_path: Path,
                                    split_grid: list[float] = SPLIT_GRID,
                                    strict_gate0: bool = False) -> FeatureAblationScorecardResult:
    """`strict_gate0=True`（真實 tracked 2025 資料流程使用）額外驗證 Gate 0
    錨點是否重現 P226-A/P228-A 已知報告數值（含 train-fold-only Platt 校準
    Brier）；預設 False（供合成測試資料使用，只做結構性存在檢查）。"""
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    rows = walk_forward_components(warmup, evalg)

    # Gate 0：直接重用 P228-A 官方 split-grid（= P226-A 官方 poisson_team_rate_model），
    # 不重新實作 full_model 的信任來源。
    p228a_entries = p228a_run_split_grid(warmup_path, eval_path, split_grid=split_grid)
    gate0 = gate0_check(p228a_entries)
    if strict_gate0:
        gate0 = assert_gate0_matches_known_p226a_run_line_metrics(gate0)
        calibration = run_train_fold_calibration(warmup_path, eval_path)
        cal_brier = calibration.calibrated["brier_score"]
        if abs(cal_brier - KNOWN_P228A_CALIBRATED_BRIER) > 1e-3:
            raise RuntimeError(
                "GATE0_FAILED_CALIBRATED_BRIER_MISMATCH: expected P228-A train-fold-only Platt "
                f"calibrated brier≈{KNOWN_P228A_CALIBRATED_BRIER:.4f}, got {cal_brier:.4f}"
            )
        gate0 = dict(gate0)
        gate0["calibrated_brier"] = cal_brier
        gate0["calibrated_status"] = "GATE0_REPRODUCED_P228A_CALIBRATED_BRIER"

    all_results: list[AblationResult] = []
    for frac in split_grid:
        for mode in ABLATION_VARIANTS:
            all_results.append(run_ablation_variant(rows, mode, frac))

    # full_model 消融模式重新推導必須與官方 P226-A/P228-A 輸出逐指標相等
    # （同一公式、同一資料，應為精確相等；此斷言防止本檔重新實作各說各話）。
    anchor_full = next(
        r for r in all_results
        if r.variant == "full_model" and abs(r.train_frac - DEFAULT_TRAIN_FRAC) < 1e-9
    )
    if (abs(anchor_full.accuracy - gate0["poisson_accuracy"]) > 1e-9
            or abs(anchor_full.brier_score - gate0["poisson_brier"]) > 1e-9
            or abs(anchor_full.coinflip_brier - gate0["coinflip_brier"]) > 1e-9):
        raise RuntimeError(
            "GATE0_FAILED_ABLATION_REPLICA_DIVERGED_FROM_OFFICIAL: full_model ablation-mode "
            "reimplementation does not match official P226-A/P228-A run line numbers"
        )

    all_results = compute_deltas_and_flags(all_results)
    interpretation = interpret_results(all_results)

    return FeatureAblationScorecardResult(
        gate0=gate0, ablation_results=all_results, interpretation=interpretation,
        warmup_rows=len(warmup), eval_rows=len(evalg), split_grid=list(split_grid),
    )


# ── 報告輸出 ─────────────────────────────────────────────────────────────────
def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def write_reports(result: FeatureAblationScorecardResult, out_dir: Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # comparison.csv — 每個 (variant, train_frac) 一列
    comp_fields = ["variant", "train_frac", "train_rows", "test_rows", "decided_count",
                   "home_adv", "coinflip_accuracy", "coinflip_brier", "accuracy", "brier_score",
                   "calibration_error", "delta_brier_vs_full", "delta_accuracy_vs_full",
                   "beats_coinflip_brier", "not_worse_within_tolerance", "notes"]
    comp_p = out / "p232a_run_line_feature_ablation_comparison.csv"
    with open(comp_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comp_fields, extrasaction="ignore")
        w.writeheader()
        for r in result.ablation_results:
            row = {k: v for k, v in vars(r).items() if k != "predictions"}
            row["notes"] = ABLATION_VARIANT_NOTES.get(r.variant, "")
            w.writerow(row)
    written.append(comp_p)

    # predictions.csv — 錨點 split（P226-A DEFAULT_TRAIN_FRAC）逐場、逐 variant 預測
    anchor_predictions = [
        p for r in result.ablation_results
        if abs(r.train_frac - DEFAULT_TRAIN_FRAC) < 1e-9
        for p in r.predictions
    ]
    pred_p = out / "p232a_run_line_feature_ablation_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(anchor_predictions[0].keys()) if anchor_predictions else [
            "game_id", "game_date", "home_team", "away_team", "market", "line_value",
            "variant", "train_frac", "predicted_home_probability", "predicted_push_probability",
            "predicted_side", "actual_side", "is_push", "correct", "learning_guard_status",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(anchor_predictions)
    written.append(pred_p)

    # scorecard.json
    json_p = out / "p232a_run_line_feature_ablation_scorecard.json"
    payload = {
        "task": "P232-A 2025 single-season run line feature ablation scorecard",
        "scope": "LOCAL_HISTORICAL_REPLAY_SINGLE_SEASON_2025_ONLY",
        "disclaimers": DISCLAIMERS,
        "warmup_rows": result.warmup_rows, "eval_rows": result.eval_rows,
        "split_grid": result.split_grid,
        "gate0_reproduction": result.gate0,
        "feature_groups_tested": [
            {"variant": v, "note": ABLATION_VARIANT_NOTES[v]}
            for v in ABLATION_VARIANTS if v != "full_model"
        ],
        "feature_groups_not_applicable": NOT_APPLICABLE_FEATURE_GROUPS,
        "ablation_results": [
            {k: v for k, v in vars(r).items() if k != "predictions"}
            for r in result.ablation_results
        ],
        "interpretation": result.interpretation,
    }
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    # scorecard.md
    md_p = out / "p232a_run_line_feature_ablation_scorecard.md"
    md: list[str] = []
    md.append("# P232-A — 2025 Single-Season Run Line Feature Ablation Scorecard\n")
    md.append("> **單一球季（2025-only）、僅本機歷史 / replay 描述性回測、run line 讓分/賠率"
              "來源未經驗證（provenance-unverified）。** 非未來預測、非下注建議、無 EV/Kelly "
              "宣稱、無 live 市場宣稱、無 production/DB/registry 變更、非已證實 edge、"
              "非跨球季驗證。\n")
    md.append("## 範疇聲明")
    for d in DISCLAIMERS:
        md.append(f"- {d}")
    md.append("")

    g0 = result.gate0
    md.append("## Gate 0 — P226-A / P228-A Run Line 重現")
    md.append(f"- 錨點 train_frac=`{g0['anchor_train_frac']}`；訓練期 `{g0['train_period'][0]}`→"
              f"`{g0['train_period'][1]}`（{g0['train_rows']} 場）；"
              f"測試期 `{g0['test_period'][0]}`→`{g0['test_period'][1]}`（{g0['test_rows']} 場）")
    md.append(f"- coinflip baseline：accuracy={_fnum(g0['coinflip_accuracy'])}、"
              f"brier={_fnum(g0['coinflip_brier'])}")
    md.append(f"- poisson_team_rate_model（full_model）：accuracy={_fnum(g0['poisson_accuracy'])}、"
              f"brier={_fnum(g0['poisson_brier'])}、ECE={_fnum(g0['poisson_ece'])}")
    if "calibrated_brier" in g0:
        md.append(f"- train-fold-only Platt calibrated：brier={_fnum(g0['calibrated_brier'])}")
        md.append(f"- **Gate 0 校準狀態**：`{g0['calibrated_status']}`")
    md.append(f"- **Gate 0 狀態**：`{g0['status']}`\n")

    md.append("## 消融特徵群組")
    md.append("| variant | note |")
    md.append("|---|---|")
    for v in ABLATION_VARIANTS:
        md.append(f"| {v} | {ABLATION_VARIANT_NOTES[v]} |")
    md.append("")
    md.append("### 不適用的建議特徵群組（本模型未使用）")
    md.append("| group | status | note |")
    md.append("|---|---|---|")
    for g in NOT_APPLICABLE_FEATURE_GROUPS:
        md.append(f"| {g['group']} | {g['status']} | {g['note']} |")
    md.append("")

    md.append("## 消融結果（chronological split grid：0.5 / 0.6 / 0.7）")
    md.append("| variant | train_frac | test(decided) | accuracy | brier | ECE | "
              "delta_brier_vs_full | beats_coinflip | not_worse_tol |")
    md.append("|---|--:|--:|--:|--:|--:|--:|:--:|:--:|")
    for r in result.ablation_results:
        md.append(f"| {r.variant} | {r.train_frac} | {r.decided_count} | {_fnum(r.accuracy)} | "
                  f"{_fnum(r.brier_score)} | {_fnum(r.calibration_error)} | "
                  f"{_fnum(r.delta_brier_vs_full, 6)} | "
                  f"{'YES' if r.beats_coinflip_brier else 'no'} | "
                  f"{'YES' if r.not_worse_within_tolerance else 'no'} |")
    md.append("")

    interp = result.interpretation
    md.append("## 解讀")
    md.append(f"- 判定規則（預先設定、非依結果調整）：某 variant 在全部 split grid 上皆嚴格"
              "優於 coinflip（brier < coinflip_brier）視為「訊號存活」；全部 variant 皆存活"
              "→`SIGNAL_PERSISTS_ACROSS_ABLATIONS`；全部 variant 皆不存活"
              "→`SIGNAL_COLLAPSES_UNDER_ABLATION`；部分存活部分不存活"
              "→`SIGNAL_DEPENDS_ON_FRAGILE_FEATURE_GROUP`；其餘情況→`INCONCLUSIVE`。")
    md.append(f"- robust_variants（全部 split 皆存活）：{interp['robust_variants'] or '（無）'}")
    md.append(f"- fragile_variants（至少一個 split 劣於 coinflip 超過容忍帶）："
              f"{interp['fragile_variants'] or '（無）'}")
    md.append(f"- **最終判定**：`{interp['label']}`\n")

    md.append("## 限制")
    md.append("- **SINGLE-SEASON ONLY**：本研究僅使用 2025 一個球季；不構成跨球季穩健性宣稱，"
              "多球季擴充仍為 HOLD（P230-A/P231-F5A）。")
    md.append("- 本模型（poisson_team_rate_model）本身沒有 Elo、休息天數、RSI/streak 特徵；"
              "`ablate_team_strength_both` 是「Elo/team strength」建議消融群組在本模型的最接近"
              "本機對應，並非真正的 Elo 特徵消融。")
    md.append("- run line 讓分/賠率的來源未經驗證（is_verified_real=False、賽後單快照），"
              "沿用 P226-A/P228-A/P230-A 已記載的已知限制；本檔僅將讓分值作為 settlement "
              "門檻使用，從未作為模型輸入特徵。")
    md.append("- 本檔未計算 bootstrap 信賴區間；訊號存活判定僅以固定容忍帶＋split grid 計數"
              "判定，非嚴格統計檢定。")
    md.append("")
    md.append("## 免責聲明")
    md.append("- **SINGLE-SEASON / 2025-ONLY**：僅 2025 一季，非多球季驗證。")
    md.append("- **HISTORICAL / PAPER-ONLY**：全部數字皆為歷史回測結果，無真實下注、無資金部署。")
    md.append("- **PROVENANCE-UNVERIFIED**：run line 讓分/賠率為賽後單快照，非賽前 PIT 資料。")
    md.append("- **NOT LIVE / NOT PRODUCTION**：無即時市場串接、無 production/DB/registry 變更。")
    md.append("- **NOT REAL BETTING**：無下注建議、無 EV/Kelly 宣稱。")
    md.append("- **NOT A PROVEN EDGE**：本報告不構成已證實的下注優勢宣稱，僅為描述性、"
              "可重現的特徵消融研究，供後續研究參考。")
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
