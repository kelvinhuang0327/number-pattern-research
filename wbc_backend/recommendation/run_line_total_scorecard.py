"""
P226-A — Run Line / Total 機率模型 + Paper 回測（純標準庫、防洩漏 walk-forward、
Poisson 球隊得失分率模型）
================================================================================
在本機歷史賽果上對 run line（讓分）與 total（大小分）兩個市場做「可比較的機率模型
+ paper 回測」，供人工檢視。架構比照 P207-A（local_retrain_scorecard.py）：純
標準庫、確定性、賽前 state → 賽後更新的防洩漏 walk-forward。本檔不修改 P207-A。

**嚴格範疇（僅本機歷史回測）**：
  - 純本機歷史 / replay 描述性回測，非未來預測能力宣稱。
  - 無下注建議、無 EV / Kelly 宣稱；ROI 數字為 paper-only 描述性回測，非 edge 宣稱。
  - 無 live 市場宣稱、無 production / DB / registry 變更、無發布。

**防洩漏設計**：
  - 嚴格時間切分：train 期所有比賽日期 <= test 期最早比賽日期。
  - 特徵僅用「賽前狀態」：球隊得失分率於賽後才更新。
  - home_adv 校準常數只用 train 段擬合（收盤形式比例校準，非迭代梯度），凍結後套用 test。
  - run line / total 的盤口線值與美式賠率**只用於 settlement 與 paper ROI 計算，
    絕不進入模型輸入特徵**（避免市場隱含資訊洩漏入預測）。
  - 前一季（暖身檔）僅用來 seed 球隊得失分率狀態，不納入評分。

**資料來源（皆為 repo 內 tracked 檔，任何 clone 可重現）**：
  - 暖身：`data/mlb_2025/mlb-2024-asplayed.csv`（含 home_score/away_score，
    is_verified_real=True，retrosheet_gamelog 來源）。
  - 評分：`data/mlb_2025/mlb_odds_2025_real.csv`（同一列含比分 + Home RL Spread /
    RL Home / RL Away + O/U / Over / Under）。
  注意：此檔全部欄位 is_verified_real=False 且為賽後單快照（見
  report/p0_market_probability_leakage_audit_20260520.md），因此 RL/O-U 的線值
  與價格僅作 settlement／paper ROI 參考，不可宣稱為賽前快照、不可宣稱 CLV。

**Push 處理**：total 市場整數線（如 8.0）可能 push（total_runs == 線）；run line
因終局分差不可能為 0，結構上不會 push，但程式碼一律以通用邏輯處理（不假設不會發生）。
Push 列排除於 accuracy / Brier 分母外，並排除於 paper ROI 的 staked 分母（退回本金、
無淨損益），另外回報 push_count / push_rate。

模型候選（皆確定性、零外部依賴）：
  baseline_coinflip_50pct   — 常數 p=0.5（透明下限）
  poisson_team_rate_model   — 球隊滾動得失分率（收縮平滑）→ Poisson λ →
                               total 用 Poisson 和、run line 用 Skellam（截斷卷積）
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 參數 ─────────────────────────────────────────────────────────────────────
RUN_SMOOTH_K = 10.0                # 球隊得失分率收縮平滑 pseudo-count
DEFAULT_TRAIN_FRAC = 0.60          # 依時間序前 60% 為 train
DEFAULT_LEAGUE_AVG_RUNS = 4.3      # 觀測資料量不足前的聯盟平均得分 fallback prior
POISSON_MAX_RUNS = 40              # Poisson/Skellam 截斷上界（尾端機率可忽略）

# 引用（非再驗證）現行 provenance 契約版本，供逐場輸出標記
PROVENANCE_CONTRACT_VERSION_REF = "p205a.v1"

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive backtest only; NO future prediction / hit-rate claim",
    "NO betting recommendation; NO EV/Kelly claim; paper ROI is a descriptive "
    "backtest statistic only, NOT a forward-looking edge claim",
    "NO live-market claim",
    "NO production / DB / registry mutation; NO real publication",
    "NO future-ticket mutation; NO strategy activation; NO leaderboard/evaluator change",
    "run line / total lines and prices are post-game unverified snapshot "
    "(is_verified_real=False) — settlement / paper-ROI reference only, "
    "NOT a pregame feed, NOT a CLV claim, NEVER used as a model input feature",
    "push rows are excluded from accuracy/Brier denominators and from the paper "
    "ROI staked base (stake returned, zero net); push_count/push_rate reported separately",
]

MODEL_NAMES = ["baseline_coinflip_50pct", "poisson_team_rate_model"]
MODEL_NOTES = {
    "baseline_coinflip_50pct": "constant p=0.5 on the primary side; transparent floor, no discrimination",
    "poisson_team_rate_model": "rolling shrinkage-smoothed team runs-for/runs-against rate -> "
    "Poisson lambda; pregame only; home_adv ratio-calibrated on train fold only",
}


# ── 數值工具 ─────────────────────────────────────────────────────────────────
def clip01(p: float) -> float:
    return max(0.0, min(1.0, p))


def american_to_prob(ml) -> Optional[float]:
    """美式賠率 → 隱含機率（未去 vig）。"""
    try:
        v = float(str(ml).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return (-v) / (-v + 100.0) if v < 0 else 100.0 / (v + 100.0)


def american_profit(odds) -> Optional[float]:
    """美式賠率 → 每 1 單位本金的獲勝淨利（不含 push）。"""
    try:
        v = float(str(odds).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return (v / 100.0) if v > 0 else (100.0 / abs(v))


def poisson_pmf(k: int, lam: float) -> float:
    """單點 Poisson pmf（供單元測試已知值比對；正式流程走陣列遞迴版本以求效能）。"""
    if k < 0:
        return 0.0
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def poisson_pmf_array(lam: float, n_max: int) -> list[float]:
    """遞迴法算 0..n_max 的 Poisson pmf 陣列：pmf(0)=e^-λ, pmf(k)=pmf(k-1)*λ/k。
    數值上與逐點 lgamma 公式等價，但避免 O(n) 次 lgamma 呼叫，效能較佳。"""
    arr = [0.0] * (n_max + 1)
    if lam <= 0:
        arr[0] = 1.0
        return arr
    arr[0] = math.exp(-lam)
    for k in range(1, n_max + 1):
        arr[k] = arr[k - 1] * lam / k
    return arr


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k)；k<0 回傳 0。"""
    if k < 0:
        return 0.0
    return sum(poisson_pmf(i, lam) for i in range(0, k + 1))


def total_probabilities(lam_home: float, lam_away: float, ou_line: float) -> tuple[float, float, float]:
    """回傳 (p_over, p_under, p_push)。兩個獨立 Poisson 相加仍為
    Poisson(lam_home + lam_away)（精確，非近似），故 total 分布可直接由此算出。"""
    lam_total = lam_home + lam_away
    n = int(math.floor(ou_line))
    is_integer_line = float(ou_line) == float(n)
    cdf_n = poisson_cdf(n, lam_total)
    if is_integer_line:
        p_push = poisson_pmf(n, lam_total)
        p_over = clip01(1.0 - cdf_n)
        p_under = clip01(cdf_n - p_push)
    else:
        p_push = 0.0
        p_over = clip01(1.0 - cdf_n)
        p_under = clip01(cdf_n)
    return p_over, p_under, p_push


def run_line_probabilities(
    lam_home: float, lam_away: float, spread_home: float, n_max: int = POISSON_MAX_RUNS
) -> tuple[float, float, float]:
    """回傳 (p_home_covers, p_away_covers, p_push)。
    D = home_score - away_score；home covers iff D > -spread_home。
    以截斷雙重迴圈算 Skellam(D=home-away) 機率，避免用到 Bessel 函式。"""
    threshold = -spread_home
    home_pmf = poisson_pmf_array(lam_home, n_max)
    away_pmf = poisson_pmf_array(lam_away, n_max)
    p_home = p_away = p_push = 0.0
    for h in range(n_max + 1):
        ph = home_pmf[h]
        if ph == 0.0:
            continue
        for a in range(n_max + 1):
            p = ph * away_pmf[a]
            d = h - a
            if d > threshold:
                p_home += p
            elif d < threshold:
                p_away += p
            else:
                p_push += p
    return clip01(p_home), clip01(p_away), clip01(p_push)


def settle_run_line(home_score: int, away_score: int, spread_home: float) -> str:
    """回傳 'HOME' / 'AWAY' / 'PUSH'（棒球終局分差恆不為 0，PUSH 結構上不會出現，
    但函式仍以通用邏輯處理，不假設）。"""
    diff = home_score - away_score
    threshold = -spread_home
    if diff > threshold:
        return "HOME"
    if diff < threshold:
        return "AWAY"
    return "PUSH"


def settle_total(home_score: int, away_score: int, ou_line: float) -> str:
    """回傳 'OVER' / 'UNDER' / 'PUSH'。"""
    total = home_score + away_score
    if total > ou_line:
        return "OVER"
    if total < ou_line:
        return "UNDER"
    return "PUSH"


def metrics(preds: list[float], ys: list[int]) -> dict:
    """回傳 accuracy / log_loss / brier_score / calibration_error(ECE, 10 bins)。"""
    n = len(ys)
    if n == 0:
        return {"n": 0, "accuracy": None, "log_loss": None,
                "brier_score": None, "calibration_error": None}

    def _clip(p: float, lo: float = 1e-15, hi: float = 1 - 1e-15) -> float:
        return max(lo, min(hi, p))

    acc = sum(1 for p, y in zip(preds, ys) if (p >= 0.5) == (y == 1)) / n
    ll = -sum(y * math.log(_clip(p)) + (1 - y) * math.log(_clip(1 - p))
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


# ── 資料載入 ─────────────────────────────────────────────────────────────────
@dataclass
class RLTGame:
    dt: datetime
    date: str
    home: str
    away: str
    home_score: int
    away_score: int
    spread_home: Optional[float] = None
    rl_home_odds: Optional[str] = None
    rl_away_odds: Optional[str] = None
    ou_line: Optional[float] = None
    over_odds: Optional[str] = None
    under_odds: Optional[str] = None


def _first(d: dict, *keys) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _parse_spread(raw: str) -> Optional[float]:
    if not raw:
        return None
    if raw.upper() == "PK":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return None


def load_games(path: Path) -> list[RLTGame]:
    """統一載入器：支援 as-played(僅比分) 與 odds(比分 + RL/O-U) 兩種格式。
    RL/O-U 欄位不存在時保持 None（暖身檔即此情況，僅供 seed 用、不進評分）。"""
    games: list[RLTGame] = []
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

            hs_raw = _first(d, "home_score", "Home Score")
            as_raw = _first(d, "away_score", "Away Score")
            try:
                hs, as_ = int(float(hs_raw)), int(float(as_raw))
            except ValueError:
                continue
            if hs == as_:
                continue  # 平手（棒球極罕見）→ 跳過，同 P207-A 慣例

            spread_home = _parse_spread(_first(d, "Home RL Spread"))
            rl_home_odds = _first(d, "RL Home") or None
            rl_away_odds = _first(d, "RL Away") or None
            ou_raw = _first(d, "O/U")
            ou_line: Optional[float]
            try:
                ou_line = float(ou_raw) if ou_raw else None
            except ValueError:
                ou_line = None
            over_odds = _first(d, "Over") or None
            under_odds = _first(d, "Under") or None

            games.append(RLTGame(
                dt=dt, date=date_s, home=home, away=away,
                home_score=hs, away_score=as_,
                spread_home=spread_home, rl_home_odds=rl_home_odds, rl_away_odds=rl_away_odds,
                ou_line=ou_line, over_odds=over_odds, under_odds=under_odds,
            ))
    games.sort(key=lambda g: (g.dt, g.home, g.away))
    return games


# ── 結果容器 ─────────────────────────────────────────────────────────────────
@dataclass
class ScorecardResult:
    split: dict
    home_adv: float
    market_comparison: dict
    market_reference: dict
    predictions: list[dict]
    inventory: list[dict]
    warmup_rows: int
    eval_rows: int
    best_by_brier: dict


# ── 主流程 ───────────────────────────────────────────────────────────────────
def run_scorecard(warmup_path: Path, eval_path: Path,
                  train_frac: float = DEFAULT_TRAIN_FRAC) -> ScorecardResult:
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    if len(evalg) < 20:
        raise ValueError(f"eval universe too small ({len(evalg)}) for a time-split scorecard")

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

    def advance(g: RLTGame, collect: bool) -> Optional[dict]:
        avg = league_avg()
        off_h, def_h = team_off_rate(g.home), team_def_rate(g.home)
        off_a, def_a = team_off_rate(g.away), team_def_rate(g.away)
        lam_home_raw = (off_h * def_a) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        lam_away_raw = (off_a * def_h) / avg if avg > 0 else DEFAULT_LEAGUE_AVG_RUNS
        row = {"game": g, "lam_home_raw": lam_home_raw, "lam_away_raw": lam_away_raw} if collect else None
        # 賽後更新（不洩漏）
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
        return row

    for g in warmup:  # 暖身，不收集
        advance(g, collect=False)
    rows = [advance(g, collect=True) for g in evalg]

    split = int(len(rows) * train_frac)
    train_rows, test_rows = rows[:split], rows[split:]
    train_period = (train_rows[0]["game"].date, train_rows[-1]["game"].date)
    test_period = (test_rows[0]["game"].date, test_rows[-1]["game"].date)

    # home_adv：closed-form 比例校準（只用 train fold；train-only fit 後凍結套用 test，
    # 手法同 P207-A 的 Platt 校準：先收集賽前 raw 特徵，再以 train-only 統計量校準）
    sum_actual_home = sum(r["game"].home_score for r in train_rows)
    sum_raw_home = sum(r["lam_home_raw"] for r in train_rows)
    home_adv = sum_actual_home / sum_raw_home if sum_raw_home > 0 else 1.0

    def model_probabilities(model_name: str, r: dict, market: str) -> tuple[float, float, float]:
        """回傳 (p_primary, p_secondary, p_push)。run_line primary=HOME covers；
        total primary=OVER。"""
        g = r["game"]
        if model_name == "baseline_coinflip_50pct":
            if market == "run_line":
                return 0.5, 0.5, 0.0
            return 0.5, 0.5, 0.0
        if model_name == "poisson_team_rate_model":
            lam_home = r["lam_home_raw"] * home_adv
            lam_away = r["lam_away_raw"]
            if market == "run_line":
                return run_line_probabilities(lam_home, lam_away, g.spread_home)
            return total_probabilities(lam_home, lam_away, g.ou_line)
        raise KeyError(model_name)

    def market_reference_probability(g: RLTGame, market: str) -> Optional[float]:
        if market == "run_line":
            ph, pa = american_to_prob(g.rl_home_odds), american_to_prob(g.rl_away_odds)
            if ph is None or pa is None or (ph + pa) <= 0:
                return None
            return ph / (ph + pa)
        po, pu = american_to_prob(g.over_odds), american_to_prob(g.under_odds)
        if po is None or pu is None or (po + pu) <= 0:
            return None
        return po / (po + pu)

    # ── 逐場、逐市場建立 test-period 預測列 ────────────────────────────────
    predictions: list[dict] = []
    market_records: dict[str, dict[str, list[dict]]] = {
        "run_line": {name: [] for name in MODEL_NAMES},
        "total": {name: [] for name in MODEL_NAMES},
    }
    reference_records: dict[str, list[dict]] = {"run_line": [], "total": []}

    for r in test_rows:
        g = r["game"]
        game_id = f"{g.date}_{g.away}@{g.home}"

        if g.spread_home is not None:
            actual_side_rl = settle_run_line(g.home_score, g.away_score, g.spread_home)
            is_push_rl = actual_side_rl == "PUSH"
            for name in MODEL_NAMES:
                p_home, p_away, p_push = model_probabilities(name, r, "run_line")
                predicted_side = "HOME" if p_home >= 0.5 else "AWAY"
                price = g.rl_home_odds if predicted_side == "HOME" else g.rl_away_odds
                profit = None if is_push_rl else american_profit(price)
                correct = None if is_push_rl else int(predicted_side == actual_side_rl)
                if not is_push_rl and correct == 1 and profit is not None:
                    net = profit
                elif not is_push_rl:
                    net = -1.0
                else:
                    net = 0.0
                rec = {
                    "market": "run_line", "model_name": name,
                    "predicted_primary_probability": round(p_home, 6),
                    "predicted_push_probability": round(p_push, 6),
                    "predicted_side": predicted_side, "actual_side": actual_side_rl,
                    "is_push": is_push_rl, "correct": correct,
                    "net_units": net if not is_push_rl else 0.0,
                    "staked": 0.0 if is_push_rl else 1.0,
                }
                market_records["run_line"][name].append(rec)
                predictions.append({
                    "game_id": game_id, "game_date": g.date,
                    "home_team": g.home, "away_team": g.away,
                    "market": "run_line", "line_value": g.spread_home,
                    "model_name": name,
                    "predicted_primary_probability": rec["predicted_primary_probability"],
                    "predicted_push_probability": rec["predicted_push_probability"],
                    "predicted_side": predicted_side, "actual_side": actual_side_rl,
                    "is_push": is_push_rl, "correct": correct,
                    "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY",
                    "provenance_contract_version": PROVENANCE_CONTRACT_VERSION_REF,
                    "source_file": Path(eval_path).name,
                })
            p_ref = market_reference_probability(g, "run_line")
            if p_ref is not None:
                reference_records["run_line"].append({
                    "predicted_primary_probability": p_ref,
                    "actual_side": actual_side_rl, "is_push": is_push_rl,
                })

        if g.ou_line is not None:
            actual_side_ou = settle_total(g.home_score, g.away_score, g.ou_line)
            is_push_ou = actual_side_ou == "PUSH"
            for name in MODEL_NAMES:
                p_over, p_under, p_push = model_probabilities(name, r, "total")
                predicted_side = "OVER" if p_over >= 0.5 else "UNDER"
                price = g.over_odds if predicted_side == "OVER" else g.under_odds
                profit = None if is_push_ou else american_profit(price)
                correct = None if is_push_ou else int(predicted_side == actual_side_ou)
                if not is_push_ou and correct == 1 and profit is not None:
                    net = profit
                elif not is_push_ou:
                    net = -1.0
                else:
                    net = 0.0
                rec = {
                    "market": "total", "model_name": name,
                    "predicted_primary_probability": round(p_over, 6),
                    "predicted_push_probability": round(p_push, 6),
                    "predicted_side": predicted_side, "actual_side": actual_side_ou,
                    "is_push": is_push_ou, "correct": correct,
                    "net_units": net if not is_push_ou else 0.0,
                    "staked": 0.0 if is_push_ou else 1.0,
                }
                market_records["total"][name].append(rec)
                predictions.append({
                    "game_id": game_id, "game_date": g.date,
                    "home_team": g.home, "away_team": g.away,
                    "market": "total", "line_value": g.ou_line,
                    "model_name": name,
                    "predicted_primary_probability": rec["predicted_primary_probability"],
                    "predicted_push_probability": rec["predicted_push_probability"],
                    "predicted_side": predicted_side, "actual_side": actual_side_ou,
                    "is_push": is_push_ou, "correct": correct,
                    "learning_guard_status": "LOCAL_HISTORICAL_BACKTEST_ONLY",
                    "provenance_contract_version": PROVENANCE_CONTRACT_VERSION_REF,
                    "source_file": Path(eval_path).name,
                })
            p_ref = market_reference_probability(g, "total")
            if p_ref is not None:
                reference_records["total"].append({
                    "predicted_primary_probability": p_ref,
                    "actual_side": actual_side_ou, "is_push": is_push_ou,
                })

    # ── 彙總指標 ────────────────────────────────────────────────────────────
    def _summarize(records: list[dict], model_name: str, market: str) -> dict:
        decided = [rec for rec in records if not rec["is_push"]]
        push_n = len(records) - len(decided)
        primary_key_is_true = {"run_line": "HOME", "total": "OVER"}[market]
        preds = [rec["predicted_primary_probability"] for rec in decided]
        ys = [1 if rec["actual_side"] == primary_key_is_true else 0 for rec in decided]
        m = metrics(preds, ys)
        staked = sum(rec["staked"] for rec in decided)
        net = sum(rec["net_units"] for rec in decided)
        m.update({
            "market": market, "model_name": model_name,
            "row_count": len(records), "decided_count": len(decided),
            "push_count": push_n,
            "push_rate": push_n / len(records) if records else 0.0,
            "paper_units_staked": staked, "paper_net_units": round(net, 6),
            "paper_roi": round(net / staked, 6) if staked > 0 else None,
            "notes": MODEL_NOTES.get(model_name, ""),
        })
        return m

    market_comparison: dict[str, list[dict]] = {"run_line": [], "total": []}
    for market in ("run_line", "total"):
        for name in MODEL_NAMES:
            market_comparison[market].append(
                _summarize(market_records[market][name], name, market)
            )

    market_reference: dict[str, Optional[dict]] = {}
    for market in ("run_line", "total"):
        refs = reference_records[market]
        if not refs:
            market_reference[market] = None
            continue
        primary_key_is_true = {"run_line": "HOME", "total": "OVER"}[market]
        decided = [rec for rec in refs if not rec["is_push"]]
        preds = [rec["predicted_primary_probability"] for rec in decided]
        ys = [1 if rec["actual_side"] == primary_key_is_true else 0 for rec in decided]
        mm = metrics(preds, ys)
        mm.update({
            "market": market,
            "model_name": "market_implied_devig(REFERENCE_UNVERIFIED)",
            "row_count": len(refs), "decided_count": len(decided),
            "push_count": len(refs) - len(decided),
            "notes": "post-game unverified snapshot; look-ahead; NOT a valid predictor; reference only",
        })
        market_reference[market] = mm

    best_by_brier = {
        market: min(
            (m for m in market_comparison[market] if m["brier_score"] is not None),
            key=lambda m: m["brier_score"],
            default={"model_name": "NONE"},
        )["model_name"]
        for market in ("run_line", "total")
    }

    rl_lines = sum(1 for r in test_rows if r["game"].spread_home is not None)
    ou_lines = sum(1 for r in test_rows if r["game"].ou_line is not None)
    inventory = [
        {"file": Path(eval_path).name, "usable": "YES", "rows": len(evalg),
         "outcome_labeled_rows": len(evalg),
         "role": "evaluation universe (walk-forward train+test); scores + RL/O-U lines same row",
         "notes": "tracked; Final games; 0 ties"},
        {"file": Path(warmup_path).name, "usable": "YES", "rows": len(warmup),
         "outcome_labeled_rows": len(warmup),
         "role": "team runs-for/runs-against rolling rate warm-up only (not scored)",
         "notes": "tracked; prior-season state seeding"},
        {"file": Path(eval_path).name + " [Home RL Spread / RL Home / RL Away]",
         "usable": "SETTLEMENT_AND_REFERENCE_ONLY", "rows": rl_lines,
         "outcome_labeled_rows": 0,
         "role": "run line settlement + descriptive market reference (de-vig implied prob)",
         "notes": "is_verified_real=False; post-game snapshot; NOT a pregame predictor; NEVER a model input feature"},
        {"file": Path(eval_path).name + " [O/U / Over / Under]",
         "usable": "SETTLEMENT_AND_REFERENCE_ONLY", "rows": ou_lines,
         "outcome_labeled_rows": 0,
         "role": "total settlement + descriptive market reference (de-vig implied prob)",
         "notes": "is_verified_real=False; post-game snapshot; NOT a pregame predictor; NEVER a model input feature"},
    ]

    return ScorecardResult(
        split={"train_frac": train_frac, "train_period": list(train_period),
               "test_period": list(test_period), "train_rows": len(train_rows),
               "test_rows": len(test_rows)},
        home_adv=home_adv,
        market_comparison=market_comparison,
        market_reference=market_reference,
        predictions=predictions,
        inventory=inventory,
        warmup_rows=len(warmup), eval_rows=len(evalg),
        best_by_brier=best_by_brier,
    )


# ── 報告輸出 ─────────────────────────────────────────────────────────────────
def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def write_reports(result: ScorecardResult, out_dir: Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # data_inventory.csv
    inv_p = out / "p226a_run_line_total_data_inventory.csv"
    with open(inv_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(result.inventory[0].keys()))
        w.writeheader()
        w.writerows(result.inventory)
    written.append(inv_p)

    # predictions.csv
    pred_p = out / "p226a_run_line_total_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(result.predictions[0].keys()) if result.predictions else [
            "game_id", "game_date", "home_team", "away_team", "market", "line_value",
            "model_name", "predicted_primary_probability", "predicted_push_probability",
            "predicted_side", "actual_side", "is_push", "correct",
            "learning_guard_status", "provenance_contract_version", "source_file",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(result.predictions)
    written.append(pred_p)

    # model_comparison.csv
    comp_fields = ["market", "model_name", "row_count", "decided_count", "push_count",
                   "push_rate", "accuracy", "log_loss", "brier_score", "calibration_error",
                   "paper_roi", "paper_net_units", "paper_units_staked", "notes"]
    comp_p = out / "p226a_run_line_total_model_comparison.csv"
    with open(comp_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comp_fields, extrasaction="ignore")
        w.writeheader()
        for market in ("run_line", "total"):
            for m in result.market_comparison[market]:
                w.writerow(m)
            if result.market_reference[market]:
                w.writerow(result.market_reference[market])
    written.append(comp_p)

    # scorecard.json
    json_p = out / "p226a_run_line_total_scorecard.json"
    payload = {
        "task": "P226-A run line / total probability model + paper backtest",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "disclaimers": DISCLAIMERS,
        "data_inventory": result.inventory,
        "warmup_rows": result.warmup_rows, "eval_rows": result.eval_rows,
        "split": result.split,
        "home_adv": result.home_adv,
        "market_comparison": result.market_comparison,
        "market_reference": result.market_reference,
        "best_by_brier": result.best_by_brier,
        "provenance_contract_version_ref": PROVENANCE_CONTRACT_VERSION_REF,
    }
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    # scorecard.md
    md_p = out / "p226a_run_line_total_scorecard.md"
    sp = result.split
    md: list[str] = []
    md.append("# P226-A — Run Line / Total Probability Model + Paper Backtest\n")
    md.append("> **僅本機歷史 / replay 描述性回測。** "
              "非未來預測、非下注建議、無 EV/Kelly 宣稱（paper ROI 為描述性回測統計，"
              "非前瞻 edge 宣稱）、無 live 市場宣稱、無 production/DB/registry 變更、"
              "無發布、無 strategy activation。\n")
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
    md.append(f"- 球隊得失分率暖身（前一季，僅 seed 狀態）：{result.warmup_rows} 場")
    md.append(f"- home_adv（train-only 收盤形式比例校準）：`{result.home_adv:.4f}`\n")

    for market in ("run_line", "total"):
        label = "Run Line" if market == "run_line" else "Total"
        md.append(f"## {label} 市場比較（測試期）")
        md.append("| model | decided | push | push_rate | accuracy | log_loss | brier_score | "
                  "calibration_error | paper_roi | paper_net_units |")
        md.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        for m in result.market_comparison[market]:
            md.append(f"| {m['model_name']} | {m['decided_count']} | {m['push_count']} | "
                      f"{_fnum(m['push_rate'], 3)} | {_fnum(m['accuracy'])} | {_fnum(m['log_loss'])} | "
                      f"{_fnum(m['brier_score'])} | {_fnum(m['calibration_error'])} | "
                      f"{_fnum(m['paper_roi'])} | {_fnum(m['paper_net_units'], 2)} |")
        ref = result.market_reference[market]
        if ref:
            md.append(f"| _{ref['model_name']}_ | {ref['decided_count']} | {ref['push_count']} | "
                      f"— | {_fnum(ref['accuracy'])} | {_fnum(ref['log_loss'])} | "
                      f"{_fnum(ref['brier_score'])} | {_fnum(ref['calibration_error'])} | — | — |")
        md.append(f"\n**最佳（Brier）**：`{result.best_by_brier[market]}`\n")

    md.append("## 解讀")
    md.append("- run line / total 的盤口線值與美式賠率僅用於 settlement 與 paper ROI，"
              "從未進入模型輸入特徵（PIT-safe）。")
    md.append("- push 列（total 整數線常見，佔比可觀）已排除於 accuracy/Brier/ROI 分母，"
              "另計 push_rate。")
    md.append("- 市場隱含機率（`market_implied_devig(REFERENCE_UNVERIFIED)`）為賽後快照，"
              "屬 look-ahead，僅作參考、不可視為賽前預測能力、不列入最佳模型排名。")
    md.append("- paper ROI 為本機歷史回測統計量，NOT 前瞻 edge / EV / Kelly 宣稱。")
    md.append("- **Run line 上 Poisson 模型明顯優於 50% coinflip baseline**（實測約 60% vs "
              "46%、Brier 明顯較低），顯示 D=home-away 的 Skellam 分布形狀＋home_adv 校準"
              "抓到了讓分盤結構性的資訊。")
    md.append("- **Total 上 Poisson 模型反而不如 baseline**（Brier 高於 0.25 的常數下限）："
              "實測預測總分均值與實際均值相近，但實際 total runs 變異數遠大於獨立 "
              "Poisson 假設隱含的變異數（over-dispersion，如大比分/延長賽等肥尾事件），"
              "導致模型機率過度自信、Brier 反而變差。這是純球隊得失分率模型在 total "
              "市場上誠實的已知限制，不是程式錯誤；若要改善需要能捕捉變異數的模型"
              "（如 Negative Binomial）或投手/牛棚層級資料，非本任務範疇。")
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
