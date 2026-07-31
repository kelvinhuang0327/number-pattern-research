"""
P207-A — 本機 MLB 重訓 + 預測 Scorecard（純標準庫、防洩漏 walk-forward）
================================================================================
在本機歷史賽果上做「可比較的重訓 / 預測結果」，供人工檢視。

**嚴格範疇（僅本機歷史回測）**：
  - 純本機歷史 / replay 描述性回測，非未來預測能力宣稱。
  - 無下注建議、無 EV / ROI / payout / Kelly / CLV 宣稱。
  - 無 live 市場宣稱、無 production / DB / registry 變更、無發布。

**防洩漏設計**：
  - 完整日期切分：train 最後日嚴格早於 test 最早日，不共用日期。
  - 日期批次狀態：同日全部特徵/預測使用同一 pre-date state，完整批次
    預測固定後才一次套用該日賽果。
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
from dataclasses import dataclass, field, replace
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
SPLIT_STRATEGY = "complete_date_boundary_nearest_requested_row_fraction"
SPLIT_TIE_RULE = "earlier boundary (smaller train partition) wins equal-distance ties"

# 引用（非再驗證）現行 provenance 契約版本，供逐場輸出標記
PROVENANCE_CONTRACT_VERSION_REF = "p205a.v1"

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "descriptive backtest only; NO future prediction / hit-rate claim",
    "NO betting recommendation; NO EV/ROI/payout/Kelly/CLV claim",
    "NO live-market claim",
    "NO production / DB / registry mutation; NO real publication",
    "NO future-ticket mutation; NO strategy activation; NO leaderboard/evaluator change",
    "historical odds lack verified pregame timestamps (is_verified_real=False) — "
    "diagnostic/descriptive reference only; no verified betting edge",
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
@dataclass(frozen=True)
class Game:
    dt: datetime
    date: str
    home: str
    away: str
    home_win: int
    p_mkt: Optional[float] = None
    occurrence: int = 1
    matchup_count: int = 1

    @property
    def base_game_id(self) -> str:
        return f"{self.date}_{self.away}@{self.home}"

    @property
    def game_id(self) -> str:
        if self.matchup_count == 1:
            return self.base_game_id
        return f"{self.base_game_id}#{self.occurrence}"


def _first(d: dict, *keys) -> str:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _game_base_key(game: Game) -> tuple[str, str, str]:
    return game.date, game.away, game.home


def _game_sort_key(game: Game) -> tuple:
    """Canonical order independent of input order.

    Outcome/odds fields only disambiguate otherwise identical same-date matchups for
    replay identity. They never enter a predictive feature or an intra-date update.
    """
    return (
        game.dt,
        game.home,
        game.away,
        game.home_win,
        game.p_mkt is None,
        0.0 if game.p_mkt is None else game.p_mkt,
    )


def _assign_occurrences(games: list[Game]) -> list[Game]:
    totals: dict[tuple[str, str, str], int] = {}
    for game in games:
        key = _game_base_key(game)
        totals[key] = totals.get(key, 0) + 1
    seen: dict[tuple[str, str, str], int] = {}
    assigned: list[Game] = []
    for game in games:
        key = _game_base_key(game)
        seen[key] = seen.get(key, 0) + 1
        assigned.append(
            replace(game, occurrence=seen[key], matchup_count=totals[key])
        )
    return assigned


def load_games(path: Path) -> list[Game]:
    """統一載入器：支援 as-played(含 home_win 欄) 與 odds(由比分推導) 兩種格式。

    - home_win：優先讀 `home_win` 欄；否則由 Home/Away Score 推導。
    - p_mkt：若含 Home ML / Away ML 則去 vig，否則 None。
    - 僅保留 status=Final 且能取得 0/1 賽果的列。
    """
    games: list[Game] = []
    with open(path, newline="", encoding="utf-8") as f:
        for line_number, d in enumerate(csv.DictReader(f), start=2):
            date_s = _first(d, "date", "Date")
            home = _first(d, "home_team", "Home")
            away = _first(d, "away_team", "Away")
            status = _first(d, "status", "Status") or "Final"
            if status.lower() != "final":
                continue
            if not home or not away or not date_s or home.casefold() == away.casefold():
                raise ValueError(
                    f"malformed game identifier at {path}:{line_number}: "
                    f"date={date_s!r}, away={away!r}, home={home!r}"
                )
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(
                    f"malformed game date at {path}:{line_number}: {date_s!r}"
                ) from exc

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
    games.sort(key=_game_sort_key)
    return _assign_occurrences(games)


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


def iter_date_batches(games: list[Game]):
    """Yield canonically ordered complete-date batches with unique game identities."""
    ordered = sorted(games, key=_game_sort_key)
    seen_ids: set[str] = set()
    current_date: Optional[str] = None
    batch: list[Game] = []
    for game in ordered:
        if (
            not game.date
            or not game.home
            or not game.away
            or game.home.casefold() == game.away.casefold()
            or game.home_win not in (0, 1)
        ):
            raise ValueError(f"malformed game identity/state: {game!r}")
        if game.game_id in seen_ids:
            raise ValueError(f"duplicate canonical game_id: {game.game_id}")
        seen_ids.add(game.game_id)
        if current_date is not None and game.date != current_date:
            yield batch
            batch = []
        current_date = game.date
        batch.append(game)
    if batch:
        yield batch


@dataclass
class DateBatchedTeamState:
    """Rolling state whose only transition boundary is a complete game date."""

    elo: dict[str, float] = field(default_factory=dict)
    history_wins: dict[str, int] = field(default_factory=dict)
    history_games: dict[str, int] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.elo.get(team, ELO_INIT)

    def win_rate(self, team: str) -> float:
        wins = self.history_wins.get(team, 0)
        games = self.history_games.get(team, 0)
        return (wins + SMOOTH_K * 0.5) / (games + SMOOTH_K)

    def team_history_smooth_probability(self, home: str, away: str) -> float:
        """Return the selected P276 model probability from the current state.

        This is intentionally outcome-free: callers must advance the state through
        ``advance_date`` before invoking it.  Keeping the formula on the shared state
        object prevents the P278 shadow handoff from drifting from the corrected P276
        implementation.
        """
        if not home or not away or home.casefold() == away.casefold():
            raise ValueError(f"invalid matchup: away={away!r}, home={home!r}")
        home_rate, away_rate = self.win_rate(home), self.win_rate(away)
        denom = home_rate + away_rate - 2 * home_rate * away_rate
        p_log5 = (
            0.5
            if denom <= 0
            else (home_rate - home_rate * away_rate) / denom
        )
        return sigmoid(
            math.log(clip(p_log5) / clip(1 - p_log5)) + HOME_LOGIT_BUMP
        )

    def selected_model_state(self) -> dict[str, dict[str, int]]:
        """Canonical state used by ``retrained_team_history_smooth`` only."""
        teams = sorted(set(self.history_wins) | set(self.history_games))
        return {
            "history_wins": {team: self.history_wins.get(team, 0) for team in teams},
            "history_games": {team: self.history_games.get(team, 0) for team in teams},
        }

    def advance_date(self, games: list[Game], *, collect: bool) -> list[dict]:
        """Build a full date's features first, then apply its aggregate outcomes."""
        if not games:
            return []
        batch = sorted(games, key=_game_sort_key)
        dates = {game.date for game in batch}
        if len(dates) != 1:
            raise ValueError(f"date batch must contain exactly one date, got {sorted(dates)}")

        rows: list[dict] = []
        elo_deltas: dict[str, float] = {}
        win_deltas: dict[str, int] = {}
        game_deltas: dict[str, int] = {}

        # No state mutation occurs in this loop: every row sees one common pre-date state.
        for game in batch:
            eh, ea = self.rating(game.home), self.rating(game.away)
            home_games = self.history_games.get(game.home, 0)
            away_games = self.history_games.get(game.away, 0)
            f_elo = ((eh + HFA_ELO) - ea) * LN10_400
            expected_home = sigmoid(f_elo)
            if collect:
                p_hist = self.team_history_smooth_probability(game.home, game.away)
                rows.append(
                    {
                        "game": game,
                        "f_elo": f_elo,
                        "p_elo": expected_home,
                        "p_hist": p_hist,
                        "y": game.home_win,
                        "p_mkt": game.p_mkt,
                        "pre_date_home_elo": eh,
                        "pre_date_away_elo": ea,
                        "pre_date_home_games": home_games,
                        "pre_date_away_games": away_games,
                    }
                )

            home_delta = ELO_K * (game.home_win - expected_home)
            elo_deltas[game.home] = elo_deltas.get(game.home, 0.0) + home_delta
            elo_deltas[game.away] = elo_deltas.get(game.away, 0.0) - home_delta
            win_deltas[game.home] = win_deltas.get(game.home, 0) + game.home_win
            win_deltas[game.away] = win_deltas.get(game.away, 0) + (1 - game.home_win)
            game_deltas[game.home] = game_deltas.get(game.home, 0) + 1
            game_deltas[game.away] = game_deltas.get(game.away, 0) + 1

        # Simultaneous aggregate transition: update order cannot change the next date's state.
        for team in sorted(game_deltas):
            self.elo[team] = self.rating(team) + elo_deltas.get(team, 0.0)
            self.history_wins[team] = self.history_wins.get(team, 0) + win_deltas[team]
            self.history_games[team] = self.history_games.get(team, 0) + game_deltas[team]
        return rows


def build_date_batched_rows(warmup: list[Game], evaluation: list[Game]) -> list[dict]:
    """Build deterministic evaluation rows under a common-pre-date state contract."""
    state = DateBatchedTeamState()
    for batch in iter_date_batches(warmup):
        state.advance_date(batch, collect=False)
    rows: list[dict] = []
    for batch in iter_date_batches(evaluation):
        rows.extend(state.advance_date(batch, collect=True))
    return rows


def select_complete_date_split(
    rows: list[dict], requested_train_frac: float
) -> tuple[list[dict], list[dict], dict]:
    """Choose the complete-date boundary nearest the requested row fraction.

    Equal-distance boundaries select the earlier boundary, hence the smaller train
    partition. This explicit rule keeps selection deterministic and conservative.
    """
    if not math.isfinite(requested_train_frac) or not 0.0 < requested_train_frac < 1.0:
        raise ValueError("requested_train_frac must be finite and strictly between 0 and 1")
    if len(rows) < 2:
        raise ValueError("at least two evaluation rows are required")

    ordered = sorted(rows, key=lambda row: _game_sort_key(row["game"]))
    game_ids = [row["game"].game_id for row in ordered]
    if len(game_ids) != len(set(game_ids)):
        raise ValueError("evaluation rows contain duplicate canonical game_id values")

    candidate_indices = [
        index
        for index in range(1, len(ordered))
        if ordered[index - 1]["game"].date != ordered[index]["game"].date
    ]
    if not candidate_indices:
        raise ValueError("complete-date split requires at least two distinct game dates")

    requested_rows = len(ordered) * requested_train_frac
    split_index = min(
        candidate_indices,
        key=lambda index: (abs(index - requested_rows), index),
    )
    train, test = ordered[:split_index], ordered[split_index:]
    train_dates = {row["game"].date for row in train}
    test_dates = {row["game"].date for row in test}
    overlap = train_dates & test_dates
    train_period = [train[0]["game"].date, train[-1]["game"].date]
    test_period = [test[0]["game"].date, test[-1]["game"].date]
    if overlap or train_period[1] >= test_period[0]:
        raise AssertionError(
            f"invalid complete-date split: overlap={sorted(overlap)}, "
            f"train_end={train_period[1]}, test_start={test_period[0]}"
        )

    metadata = {
        # Retain the legacy key for report consumers while making semantics explicit.
        "train_frac": requested_train_frac,
        "requested_train_frac": requested_train_frac,
        "effective_train_frac": len(train) / len(ordered),
        "split_strategy": SPLIT_STRATEGY,
        "tie_rule": SPLIT_TIE_RULE,
        "selected_boundary_date": train_period[1],
        "selected_test_start_date": test_period[0],
        "train_period": train_period,
        "test_period": test_period,
        "train_rows": len(train),
        "test_rows": len(test),
        "train_date_count": len(train_dates),
        "test_date_count": len(test_dates),
    }
    return train, test, metadata


# ── 主流程 ───────────────────────────────────────────────────────────────────
def run_scorecard(warmup_path: Path, eval_path: Path,
                  train_frac: float = DEFAULT_TRAIN_FRAC) -> ScorecardResult:
    warmup = load_games(Path(warmup_path))
    evalg = load_games(Path(eval_path))
    if len(evalg) < 20:
        raise ValueError(f"eval universe too small ({len(evalg)}) for a time-split scorecard")

    rows = build_date_batched_rows(warmup, evalg)
    train, test, split_metadata = select_complete_date_split(rows, train_frac)

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
                   "notes": "historical odds timestamp unverified; descriptive only; "
                            "NOT a verified pregame predictor or betting edge"})
        market_reference = mm

    best = min(comparison, key=lambda m: m["brier_score"])["model_name"]

    # 逐場預測（每場 × 每模型一列）
    predictions: list[dict] = []
    for r in test:
        g = r["game"]
        for name in model_names:
            p = model_prob(name, r)
            predictions.append({
                "game_id": g.game_id,
                "game_occurrence": g.occurrence,
                "game_date": g.date, "home_team": g.home, "away_team": g.away,
                "model_name": name,
                "predicted_home_win_probability": round(p, 6),
                "selected_side": selected_side(p),
                "confidence_band": confidence_band(p),
                "actual_home_win": g.home_win,
                "correct": int((p >= 0.5) == (g.home_win == 1)),
                "feature_state_cutoff": f"strictly_before_{g.date}",
                "state_transition_contract": "PREDICT_FULL_DATE_THEN_UPDATE",
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
         "role": "evaluation universe (date-batched train+test); outcome derived from scores",
         "notes": "tracked; Final games; common pre-date state; 0 ties"},
        {"file": Path(warmup_path).name, "usable": "YES", "rows": len(warmup),
         "outcome_labeled_rows": len(warmup),
         "role": "date-batched Elo / rolling warm-up only (not scored)",
         "notes": "tracked; prior-season state seeding; update after complete date"},
    ]
    odds_rows = sum(1 for g in evalg if g.p_mkt is not None)
    inventory.append(
        {"file": Path(eval_path).name + " [Home ML/Away ML]", "usable": "REFERENCE_ONLY",
         "rows": odds_rows, "outcome_labeled_rows": 0,
         "role": "descriptive market reference (de-vig implied prob)",
         "notes": "is_verified_real=False; pregame timestamp unverified; diagnostic only; "
                  "NOT a verified betting edge"})

    return ScorecardResult(
        split=split_metadata,
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
        w = csv.DictWriter(
            f, fieldnames=list(result.inventory[0].keys()), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(result.inventory)
    written.append(inv_p)

    # predictions.csv
    pred_p = out / "p207a_local_retrain_predictions.csv"
    with open(pred_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=list(result.predictions[0].keys()), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(result.predictions)
    written.append(pred_p)

    # model_comparison.csv
    comp_fields = ["model_name", "train_rows", "test_rows", "accuracy", "log_loss",
                   "brier_score", "calibration_error", "coverage", "notes"]
    comp_p = out / "p207a_local_retrain_model_comparison.csv"
    with open(comp_p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=comp_fields, extrasaction="ignore", lineterminator="\n"
        )
        w.writeheader()
        w.writerows(result.comparison)
        if result.market_reference:
            w.writerow(result.market_reference)
    written.append(comp_p)

    # scorecard.json
    json_p = out / "p207a_local_retrain_scorecard.json"
    payload = {
        "task": "P276-A corrected P207-A local MLB retrain + prediction scorecard",
        "scope": "LOCAL_HISTORICAL_REPLAY_ONLY",
        "result_context": "CORRECTED_2025_LOCAL_DATE_BATCHED_RETRAIN_EVALUATION",
        "state_transition_contract": "PREDICT_FULL_DATE_THEN_UPDATE",
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
    md.append("# P276-A — Corrected 2025 Local MLB Retrain + Prediction Scorecard\n")
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
    md.append("## 完整日期訓練 / 測試切分（train 最後日 < test 最早日）")
    md.append(
        f"- 訓練期：`{sp['train_period'][0]}` → `{sp['train_period'][1]}`"
        f"（{sp['train_rows']} 場 / {sp['train_date_count']} 日）"
    )
    md.append(
        f"- 測試期：`{sp['test_period'][0]}` → `{sp['test_period'][1]}`"
        f"（{sp['test_rows']} 場 / {sp['test_date_count']} 日）"
    )
    md.append(
        f"- requested train fraction: `{sp['requested_train_frac']:.6f}`；"
        f"effective: `{sp['effective_train_frac']:.6f}`"
    )
    md.append(f"- split strategy: `{sp['split_strategy']}`")
    md.append(f"- tie rule: `{sp['tie_rule']}`")
    md.append(
        f"- selected boundary: after `{sp['selected_boundary_date']}`; "
        f"test starts `{sp['selected_test_start_date']}`"
    )
    md.append(
        "- 狀態合約：同一 game_date 全部預測使用同一 pre-date state；"
        "該日所有預測固定後才一次更新。"
    )
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
    md.append(
        "- 歷史賠率沒有經驗證的賽前時間戳，僅作診斷/描述參考；"
        "命中率、EV 與 ROI 都不是經驗證的投注邊際。"
    )
    with open(md_p, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    written.append(md_p)

    return written
