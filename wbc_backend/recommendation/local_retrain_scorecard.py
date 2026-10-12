"""
P207-A — 本機 MLB 重訓 + 預測 Scorecard（純標準庫、防洩漏 walk-forward）
================================================================================
在本機歷史賽果上做「可比較的重訓 / 預測結果」，供人工檢視。

**嚴格範疇（僅本機歷史回測）**：
  - 純本機歷史 / replay 描述性回測，非未來預測能力宣稱。
  - 無下注建議、無 EV / ROI / payout / Kelly / CLV 宣稱。
  - 無 live 市場宣稱、無 production / DB / registry 變更、無發布。

**防洩漏設計**：
  - 嚴格時間切分：train 期所有比賽日期 <= test 期最早比賽日期。
  - 特徵僅用「賽前狀態」：Elo 於賽後才更新；隊史勝率為賽前累積。
  - Platt 校準 (A, B) 只用 train 段擬合，凍結後套用 test。
  - baseline 先驗只用 train 段主場勝率。
  - 前一季（暖身檔）僅用來 seed Elo / 滾動統計，不納入評分。

**資料來源（皆為 repo 內 tracked 檔，任何 clone 可重現）**：
  - 暖身：`data/mlb_2025/mlb-2024-asplayed.csv`（含 home_win 欄）。
  - 評分：`data/mlb_2025/mlb_odds_2025_real.csv`（含每場比分→推導 home_win；
    含 Home ML / Away ML→去 vig 市場隱含機率，僅描述參考）。
  注意：市場賠率 `is_verified_real=False` 且為賽後單快照，**非賽前**，
  因此僅作描述性參考、不列入模型排名。

模型候選（皆確定性、零外部依賴）：
  baseline_fixed_prior           — 常數 = train 主場勝率
  elo_like_rating                — 滾動 Elo(K=20) + 主場優勢，logit→機率
  retrained_team_history_smooth  — log5(平滑後隊伍勝率) + 主場 logit bump
  calibrated_elo_recent_form     — Elo logit 經 train 段 Platt 校準
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 參數 ─────────────────────────────────────────────────────────────────────
ELO_INIT = 1500.0
ELO_K = 20.0
HFA_ELO = 24.0                     # 主場優勢(Elo 點) → 同分時主勝率 ~53.4%
LN10_400 = math.log(10) / 400.0
SMOOTH_K = 10.0                    # 隊伍勝率平滑 pseudo-count（偏向 .500）
HOME_LOGIT_BUMP = 0.14            # log5 模型的主場優勢(logit)
DEFAULT_TRAIN_FRAC = 0.60          # 依時間序前 60% 為 train
PLATT_ITERS = 4000
PLATT_LR = 0.10

# 引用（非再驗證）現行 provenance 契約版本，供逐場輸出標記
PROVENANCE_CONTRACT_VERSION_REF = "p205a.v1"

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive backtest only; NO future prediction / hit-rate claim",
    "NO betting recommendation; NO EV/ROI/payout/Kelly/CLV claim",
    "NO live-market claim",
    "NO production / DB / registry mutation; NO real publication",
    "NO future-ticket mutation; NO strategy activation; NO leaderboard/evaluator change",
    "odds fields are post-game unverified snapshot (is_verified_real=False) — reference only",
]


# ── 數值工具 ─────────────────────────────────────────────────────────────────
def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def clip(p: float, lo: float = 1e-15, hi: float = 1 - 1e-15) -> float:
    return max(lo, min(hi, p))


def american_to_prob(ml) -> Optional[float]:
    """美式賠率 → 隱含機率（未去 vig）。"""
    try:
        v = float(str(ml).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return (-v) / (-v + 100.0) if v < 0 else 100.0 / (v + 100.0)


def confidence_band(p_home: float) -> str:
    p_sel = max(p_home, 1.0 - p_home)
    if p_sel < 0.55:
        return "LOW"
    if p_sel < 0.65:
        return "MEDIUM"
    return "HIGH"


def selected_side(p_home: float) -> str:
    return "HOME" if p_home >= 0.5 else "AWAY"


# ── 資料載入 ─────────────────────────────────────────────────────────────────
@dataclass
class Game:
    dt: datetime
    date: str
    home: str
    away: str
    home_win: int
    p_mkt: Optional[float] = None


def _first(d: dict, *keys) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def load_games(path: Path) -> list[Game]:
    """統一載入器：支援 as-played(含 home_win 欄) 與 odds(由比分推導) 兩種格式。

    - home_win：優先讀 `home_win` 欄；否則由 Home/Away Score 推導。
    - p_mkt：若含 Home ML / Away ML 則去 vig，否則 None。
    - 僅保留 status=Final 且能取得 0/1 賽果的列。
    """
    games: list[Game] = []
    with open(path, newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            date_s = _first(d, "date", "Date")
            home = _first(d, "home_team", "Home")
            away = _first(d, "away_team", "Away")
            status = _first(d, "status", "Status") or "Final"
            if status.lower() != "final" or not home or not away or not date_s:
                continue
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError:
                continue

            home_win: Optional[int] = None
            hw_raw = d.get("home_win")
            if hw_raw is not None and str(hw_raw).strip() != "":
                try:
                    hw = float(hw_raw)
                    if hw in (0.0, 1.0):
                        home_win = int(hw)
                except (TypeError, ValueError):
                    home_win = None
            if home_win is None:  # 由比分推導
                hs = _first(d, "home_score", "Home Score")
                as_ = _first(d, "away_score", "Away Score")
                try:
                    hsi, asi = int(float(hs)), int(float(as_))
                    if hsi == asi:
                        continue  # 平手（棒球極罕見）→ 跳過
                    home_win = 1 if hsi > asi else 0
                except (TypeError, ValueError):
                    continue

            p_mkt = None
            ph, pa = american_to_prob(d.get("Home ML")), american_to_prob(d.get("Away ML"))
            if ph is not None and pa is not None and (ph + pa) > 0:
                p_mkt = ph / (ph + pa)  # 去 vig

            games.append(Game(dt=dt, date=date_s, home=home, away=away,
                              home_win=home_win, p_mkt=p_mkt))
    games.sort(key=lambda g: (g.dt, g.home, g.away))
    return games


# ── 指標 ─────────────────────────────────────────────────────────────────────
def metrics(preds: list[float], ys: list[int]) -> dict:
    """回傳 accuracy / log_loss / brier_score / calibration_error(ECE, 10 bins)。"""
    n = len(ys)
    if n == 0:
        return {"n": 0, "accuracy": None, "log_loss": None,
                "brier_score": None, "calibration_error": None}
    acc = sum(1 for p, y in zip(preds, ys) if (p >= 0.5) == (y == 1)) / n
    ll = -sum(y * math.log(clip(p)) + (1 - y) * math.log(clip(1 - p))
              for p, y in zip(preds, ys)) / n
    brier = sum((p - y) ** 2 for p, y in zip(preds, ys)) / n
    bins: list[list[tuple[float, int]]] = [[] for _ in range(10)]
    for p, y in zip(preds, ys):
        bins[min(9, int(p * 10))].append((p, y))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        conf = sum(p for p, _ in b) / len(b)
        acc_b = sum(y for _, y in b) / len(b)
        ece += (len(b) / n) * abs(acc_b - conf)
    return {"n": n, "accuracy": acc, "log_loss": ll,
            "brier_score": brier, "calibration_error": ece}


def fit_platt(fs: list[float], ys: list[int],
              iters: int = PLATT_ITERS, lr: float = PLATT_LR) -> tuple[float, float]:
    """1-D Platt：p = sigmoid(A*f + B)，確定性梯度下降。"""
    A, B, n = 1.0, 0.0, len(ys)
    if n == 0:
        return A, B
    for _ in range(iters):
        gA = gB = 0.0
        for f, y in zip(fs, ys):
            p = sigmoid(A * f + B)
            gA += (p - y) * f
            gB += (p - y)
        A -= lr * gA / n
        B -= lr * gB / n
    return A, B


# ── 結果容器 ─────────────────────────────────────────────────────────────────
@dataclass
class ScorecardResult:
    split: dict
    train_home_win_prior: float
    platt: dict
    comparison: list[dict]
    market_reference: Optional[dict]
    predictions: list[dict]
    inventory: list[dict]
    odds_metrics_status: str
    outcome_metrics_status: str
    best_by_brier: str
    confidence_band_breakdown: dict
    selected_side_distribution: dict
    warmup_rows: int
    eval_rows: int


# ── 主流程 ───────────────────────────────────────────────────────────────────
def run_scorecard(warmup_path: Path, eval_path: Path,
                  train_frac: float = DEFAULT_TRAIN_FRAC) -> ScorecardResult:
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    if len(evalg) < 20:
        raise ValueError(f"eval universe too small ({len(evalg)}) for a time-split scorecard")

    elo: dict[str, float] = {}
    hist: dict[str, list[int]] = {}

    def get_elo(t: str) -> float:
        return elo.setdefault(t, ELO_INIT)

    def win_rate(t: str) -> float:
        r = hist.get(t, [])
        return (sum(r) + SMOOTH_K * 0.5) / (len(r) + SMOOTH_K)

    def advance(g: Game, collect: bool):
        eh, ea = get_elo(g.home), get_elo(g.away)
        f_elo = ((eh + HFA_ELO) - ea) * LN10_400   # 賽前 Elo logit
        row = None
        if collect:
            A_, B_ = win_rate(g.home), win_rate(g.away)
            denom = A_ + B_ - 2 * A_ * B_
            p_log5 = 0.5 if denom <= 0 else (A_ - A_ * B_) / denom
            p_hist = sigmoid(math.log(clip(p_log5) / clip(1 - p_log5)) + HOME_LOGIT_BUMP)
            row = {"game": g, "f_elo": f_elo, "p_elo": sigmoid(f_elo),
                   "p_hist": p_hist, "y": g.home_win, "p_mkt": g.p_mkt}
        # 賽後更新（不洩漏）
        e = sigmoid(f_elo)
        elo[g.home] = eh + ELO_K * (g.home_win - e)
        elo[g.away] = ea + ELO_K * ((1 - g.home_win) - (1 - e))
        hist.setdefault(g.home, []).append(g.home_win)
        hist.setdefault(g.away, []).append(1 - g.home_win)
        return row

    for g in warmup:            # 暖身，不收集
        advance(g, collect=False)
    rows = [advance(g, collect=True) for g in evalg]

    split = int(len(rows) * train_frac)
    train, test = rows[:split], rows[split:]
    train_period = (train[0]["game"].date, train[-1]["game"].date)
    test_period = (test[0]["game"].date, test[-1]["game"].date)

    prior = sum(r["y"] for r in train) / len(train)
    A, B = fit_platt([r["f_elo"] for r in train], [r["y"] for r in train])

    def p_cal(f: float) -> float:
        return sigmoid(A * f + B)

    def model_prob(name: str, r: dict) -> float:
        if name == "baseline_fixed_prior":
            return prior
        if name == "elo_like_rating":
            return r["p_elo"]
        if name == "retrained_team_history_smooth":
            return r["p_hist"]
        if name == "calibrated_elo_recent_form":
            return p_cal(r["f_elo"])
        raise KeyError(name)

    model_names = ["baseline_fixed_prior", "elo_like_rating",
                   "retrained_team_history_smooth", "calibrated_elo_recent_form"]
    model_notes = {
        "baseline_fixed_prior": "constant = train home-win rate; no discrimination",
        "elo_like_rating": "rolling Elo K=20 + HFA; pregame only",
        "retrained_team_history_smooth": "log5 of smoothed team win-rates + home logit bump; pregame only",
        "calibrated_elo_recent_form": "Elo logit Platt-calibrated on train fold only",
    }
    ys_test = [r["y"] for r in test]

    comparison: list[dict] = []
    for name in model_names:
        preds = [model_prob(name, r) for r in test]
        m = metrics(preds, ys_test)
        m.update({"model_name": name, "train_rows": len(train), "test_rows": len(test),
                  "coverage": len(preds) / len(test), "notes": model_notes[name]})
        comparison.append(m)

    # 市場參考（僅 test 中有 odds 的場次；非合法模型，不列入排名）
    mkt_pairs = [(r["p_mkt"], r["y"]) for r in test if r["p_mkt"] is not None]
    market_reference = None
    if mkt_pairs:
        mm = metrics([p for p, _ in mkt_pairs], [y for _, y in mkt_pairs])
        mm.update({"model_name": "market_implied_devig(REFERENCE_UNVERIFIED)",
                   "train_rows": 0, "test_rows": len(test),
                   "coverage": len(mkt_pairs) / len(test),
                   "notes": "post-game unverified snapshot; look-ahead; NOT a valid predictor"})
        market_reference = mm

    best = min(comparison, key=lambda m: m["brier_score"])["model_name"]

    # 逐場預測（每場 × 每模型一列）
    predictions: list[dict] = []
    for r in test:
        g = r["game"]
        for name in model_names:
            p = model_prob(name, r)
            predictions.append({
                "game_id": f"{g.date}_{g.away}@{g.home}",
                "game_date": g.date, "home_team": g.home, "away_team": g.away,
                "model_name": name,
                "predicted_home_win_probability": round(p, 6),
                "selected_side": selected_side(p),
                "confidence_band": confidence_band(p),
                "actual_home_win": g.home_win,
                "correct": int((p >= 0.5) == (g.home_win == 1)),
                "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY",
                "provenance_contract_version": PROVENANCE_CONTRACT_VERSION_REF,
                "source_file": Path(eval_path).name,
            })

    band_break: dict[str, dict] = {}
    side_dist: dict[str, int] = {}
    for pr in predictions:
        if pr["model_name"] != best:
            continue
        b = band_break.setdefault(pr["confidence_band"], {"n": 0, "correct": 0})
        b["n"] += 1
        b["correct"] += pr["correct"]
        side_dist[pr["selected_side"]] = side_dist.get(pr["selected_side"], 0) + 1

    inventory = [
        {"file": Path(eval_path).name, "usable": "YES", "rows": len(evalg),
         "outcome_labeled_rows": len(evalg),
         "role": "evaluation universe (walk-forward train+test); outcome derived from scores",
         "notes": "tracked; Final games; 0 ties"},
        {"file": Path(warmup_path).name, "usable": "YES", "rows": len(warmup),
         "outcome_labeled_rows": len(warmup),
         "role": "Elo / rolling warm-up only (not scored)",
         "notes": "tracked; prior-season state seeding"},
    ]
    odds_rows = sum(1 for g in evalg if g.p_mkt is not None)
    inventory.append(
        {"file": Path(eval_path).name + " [Home ML/Away ML]", "usable": "REFERENCE_ONLY",
         "rows": odds_rows, "outcome_labeled_rows": 0,
         "role": "descriptive market reference (de-vig implied prob)",
         "notes": "is_verified_real=False; post-game snapshot; NOT a valid pregame predictor"})

    return ScorecardResult(
        split={"train_frac": train_frac, "train_period": list(train_period),
               "test_period": list(test_period), "train_rows": len(train),
               "test_rows": len(test)},
        train_home_win_prior=prior, platt={"A": A, "B": B},
        comparison=comparison, market_reference=market_reference,
        predictions=predictions, inventory=inventory,
        odds_metrics_status="PRESENT_BUT_TIMING_UNVERIFIED" if odds_rows else "ODDS_NOT_AVAILABLE",
        outcome_metrics_status="AVAILABLE",
        best_by_brier=best, confidence_band_breakdown=band_break,
        selected_side_distribution=side_dist,
        warmup_rows=len(warmup), eval_rows=len(evalg))


# ── 報告輸出 ─────────────────────────────────────────────────────────────────
def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def write_reports(result: ScorecardResult, out_dir: Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # data_inventory.csv
    inv_p = out / "p207a_local_retrain_data_inventory.csv"
    with open(inv_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(result.inventory[0].keys()))
        w.writeheader()
        w.writerows(result.inventory)
    written.append(inv_p)

    # predictions.csv
    pred_p = out / "p207a_local_retrain_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(result.predictions[0].keys()))
        w.writeheader()
        w.writerows(result.predictions)
    written.append(pred_p)

    # model_comparison.csv
    comp_fields = ["model_name", "train_rows", "test_rows", "accuracy", "log_loss",
                   "brier_score", "calibration_error", "coverage", "notes"]
    comp_p = out / "p207a_local_retrain_model_comparison.csv"
    with open(comp_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comp_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(result.comparison)
        if result.market_reference:
            w.writerow(result.market_reference)
    written.append(comp_p)

    # scorecard.json
    json_p = out / "p207a_local_retrain_scorecard.json"
    payload = {
        "task": "P207-A local MLB retrain + prediction scorecard",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "disclaimers": DISCLAIMERS,
        "data_inventory": result.inventory,
        "warmup_rows": result.warmup_rows, "eval_rows": result.eval_rows,
        "split": result.split,
        "train_home_win_prior": result.train_home_win_prior,
        "platt": result.platt,
        "model_comparison": result.comparison,
        "market_reference": result.market_reference,
        "odds_metrics_status": result.odds_metrics_status,
        "outcome_metrics_status": result.outcome_metrics_status,
        "best_by_brier": result.best_by_brier,
        "best_confidence_band_breakdown": result.confidence_band_breakdown,
        "best_selected_side_distribution": result.selected_side_distribution,
        "provenance_contract_version_ref": PROVENANCE_CONTRACT_VERSION_REF,
    }
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    # scorecard.md
    md_p = out / "p207a_local_retrain_scorecard.md"
    sp = result.split
    md: list[str] = []
    md.append("# P207-A — Local MLB Retrain + Prediction Scorecard\n")
    md.append("> **僅本機歷史 / replay 描述性回測。** "
              "非未來預測、非下注建議、無 EV/ROI/payout/Kelly/CLV、"
              "無 live 市場宣稱、無 production/DB/registry 變更、無發布、無 strategy activation。\n")
    md.append("## 範疇聲明")
    for d in DISCLAIMERS:
        md.append(f"- {d}")
    md.append("")
    md.append("## 資料盤點")
    md.append("| file | usable | rows | outcome_labeled | role |")
    md.append("|---|---|--:|--:|---|")
    for it in result.inventory:
        md.append(f"| {it['file']} | {it['usable']} | {it['rows']} | "
                  f"{it['outcome_labeled_rows']} | {it['role']} |")
    md.append("")
    md.append("## 訓練 / 測試切分（嚴格時間序，train 期 < test 期）")
    md.append(f"- 訓練期：`{sp['train_period'][0]}` → `{sp['train_period'][1]}`（{sp['train_rows']} 場）")
    md.append(f"- 測試期：`{sp['test_period'][0]}` → `{sp['test_period'][1]}`（{sp['test_rows']} 場）")
    md.append(f"- Elo 暖身（前一季，僅 seed 狀態）：{result.warmup_rows} 場")
    md.append(f"- train 主場勝率先驗：`{result.train_home_win_prior:.4f}`；"
              f"Platt(A,B)=({result.platt['A']:.4f}, {result.platt['B']:.4f})")
    md.append(f"- odds 狀態：`{result.odds_metrics_status}`；outcome 狀態：`{result.outcome_metrics_status}`\n")
    md.append("## 模型比較（測試期）")
    md.append("| model | train | test | accuracy | log_loss | brier_score | calibration_error | coverage |")
    md.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for m in result.comparison:
        md.append(f"| {m['model_name']} | {m['train_rows']} | {m['test_rows']} | "
                  f"{_fnum(m['accuracy'])} | {_fnum(m['log_loss'])} | {_fnum(m['brier_score'])} | "
                  f"{_fnum(m['calibration_error'])} | {_fnum(m['coverage'], 3)} |")
    if result.market_reference:
        mr = result.market_reference
        md.append(f"| _{mr['model_name']}_ | — | {mr['test_rows']} | {_fnum(mr['accuracy'])} | "
                  f"{_fnum(mr['log_loss'])} | {_fnum(mr['brier_score'])} | "
                  f"{_fnum(mr['calibration_error'])} | {_fnum(mr['coverage'], 3)} |")
    md.append(f"\n**最佳（Brier）**：`{result.best_by_brier}`（市場行為 look-ahead，不列入排名）\n")
    md.append("## 最佳模型信心區間分佈（測試期）")
    md.append("| band | n | correct | hit_rate |")
    md.append("|---|--:|--:|--:|")
    for b in ("HIGH", "MEDIUM", "LOW"):
        if b in result.confidence_band_breakdown:
            d = result.confidence_band_breakdown[b]
            hr = d["correct"] / d["n"] if d["n"] else 0.0
            md.append(f"| {b} | {d['n']} | {d['correct']} | {hr:.4f} |")
    md.append(f"\nselected_side 分佈：`{result.selected_side_distribution}`\n")
    md.append("## 解讀")
    md.append("- 準確率 53–57% / Brier ~0.246 為 MLB 純球隊強度模型的誠實可信區間；"
              "再往上需 game-specific（逐場投手/休息/陣容）資料。")
    md.append("- 校準（Platt）主要改善 calibration_error（ECE），對 Brier 提升有限。")
    md.append("- 市場隱含機率為賽後快照，屬 look-ahead，僅作參考、不可視為賽前預測能力。")
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
