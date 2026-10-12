"""
MARL Strategy Adapter — P6_MARL_OPTIMIZER_INTEGRATION
======================================================
將 P5 artifact（strategy_sim_v2_ha40_platt）轉換為 MARL-compatible 格式，
並提供 8 種策略的風險調整績效比較分析。

硬性約束：
- paper_only 永遠 True
- proxy ROI 必須標示非真實 CLV
- 不寫入 production channel
- actual_home_win 缺失時 reward 置零並標記 invalid_for_reward
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


# ══════════════════════════════════════════════════════════════════════════════
# 狀態、動作、獎勵、記錄 Dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MARLState:
    game_id: str
    game_date: str
    model_prob: float
    implied_prob: float
    edge: float
    kelly_fraction: float
    stake_unit: float
    walk_forward_fold: int
    odds_quality_tier: str
    home_win_ci_lower: Optional[float] = None
    home_win_ci_upper: Optional[float] = None


@dataclass
class MARLAction:
    bet: bool = False
    stake_multiplier: float = 1.0
    edge_threshold: float = 0.01
    kelly_fraction_multiplier: float = 0.25


@dataclass
class MARLReward:
    proxy_profit_loss: float = 0.0
    roi: float = 0.0
    drawdown_penalty: float = 0.0
    calibration_penalty: float = 0.0
    volatility_penalty: float = 0.0


@dataclass
class MARLRecord:
    state: MARLState
    action: MARLAction
    reward: MARLReward
    actual_home_win: Optional[int] = None   # 0 or 1
    paper_only: bool = True                 # 硬性約束：永遠 True
    source_trace: str = ""
    invalid_for_reward: bool = False        # actual_home_win 缺失時 True
    # P7 新增欄位
    true_profit_loss: Optional[float] = None  # 真實損益（actual_home_win 存在時計算）
    selected_side_win: Optional[int] = None   # 0 or 1
    reward_source: str = "EV_PROXY"           # "TRUE_OUTCOME" | "EV_PROXY"

    def to_dict(self) -> dict:
        d = asdict(self)
        # 確保 paper_only 不被下游覆蓋
        d["paper_only"] = True
        d["proxy_roi_disclaimer"] = (
            "proxy ROI — NOT real CLV. Based on POST_GAME_PROXY odds only."
        )
        return d


# ══════════════════════════════════════════════════════════════════════════════
# P5 row → MARLRecord 轉換
# ══════════════════════════════════════════════════════════════════════════════

def american_to_decimal_odds(american: float) -> float:
    """美式賠率轉歐式（Decimal）賠率"""
    if american >= 100:
        return american / 100.0 + 1.0
    else:
        return 100.0 / abs(american) + 1.0


def calc_true_pnl(
    side: str,
    actual_home_win: int,
    stake: float,
    home_ml: Optional[float],
    away_ml: Optional[float],
) -> float:
    """
    計算真實損益。
    side: "HOME" or "AWAY"
    actual_home_win: 1 = home 贏, 0 = away 贏
    stake: 下注金額（單位）
    home_ml / away_ml: 美式賠率（可為 None，預設 -110）
    profit = stake * (decimal_odds - 1) if win, else -stake
    """
    DEFAULT_ML = -110.0  # 美國常見 -110

    bet_side = side.upper() if side else ""
    if bet_side == "HOME":
        win = (actual_home_win == 1)
        odds = home_ml if home_ml is not None else DEFAULT_ML
    elif bet_side == "AWAY":
        win = (actual_home_win == 0)
        odds = away_ml if away_ml is not None else DEFAULT_ML
    else:
        return 0.0

    decimal = american_to_decimal_odds(float(odds))
    if win:
        return round(stake * (decimal - 1.0), 6)
    else:
        return round(-stake, 6)


def p5_row_to_marl_record(row: dict, policy: dict) -> Optional[MARLRecord]:
    """
    將 P5 artifact row 轉換為 MARLRecord。
    若 actual_home_win 缺失，reward 置為 0 並標記 invalid_for_reward。

    policy 格式：
    {
        "edge_threshold": 0.01,
        "kelly_fraction_multiplier": 0.25,
        "drawdown_penalty_weight": 0.1,
        "calibration_penalty_weight": 0.05
    }
    """
    edge_threshold = float(policy.get("edge_threshold", 0.01))
    kelly_mult = float(policy.get("kelly_fraction_multiplier", 0.25))
    drawdown_pw = float(policy.get("drawdown_penalty_weight", 0.1))
    calibration_pw = float(policy.get("calibration_penalty_weight", 0.05))

    # 解析 CI
    ci_raw = row.get("home_win_ci_95")
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    if isinstance(ci_raw, (list, tuple)) and len(ci_raw) == 2:
        ci_lower, ci_upper = float(ci_raw[0]), float(ci_raw[1])

    state = MARLState(
        game_id=row.get("game_id", ""),
        game_date=row.get("game_date", ""),
        model_prob=float(row.get("model_prob", 0.5)),
        implied_prob=float(row.get("implied_prob", 0.5)),
        edge=float(row.get("edge", 0.0)),
        kelly_fraction=float(row.get("kelly_fraction", 0.0)),
        stake_unit=float(row.get("stake_unit", 0.0)),
        walk_forward_fold=int(row.get("walk_forward_fold", 0)),
        odds_quality_tier=str(row.get("odds_quality_tier", "UNKNOWN")),
        home_win_ci_lower=ci_lower,
        home_win_ci_upper=ci_upper,
    )

    # 策略決策：是否下注
    edge = state.edge
    should_bet = (edge >= edge_threshold) and (row.get("bet_side", "NO_BET") != "NO_BET")
    adjusted_stake = state.stake_unit * kelly_mult / max(0.25, 1.0) * 4.0  # 正規化到 0.25 基準

    action = MARLAction(
        bet=should_bet,
        stake_multiplier=kelly_mult,
        edge_threshold=edge_threshold,
        kelly_fraction_multiplier=kelly_mult,
    )

    # 獎勵計算
    actual_home_win = row.get("actual_home_win")
    invalid_for_reward = actual_home_win is None

    if invalid_for_reward or not should_bet:
        reward = MARLReward(
            proxy_profit_loss=0.0,
            roi=0.0,
            drawdown_penalty=0.0,
            calibration_penalty=0.0,
            volatility_penalty=0.0,
        )
    else:
        actual_win = int(actual_home_win)
        bet_side = row.get("bet_side", "NO_BET")
        stake = state.stake_unit * kelly_mult / 0.25  # 依 kelly multiplier 調整

        # PnL 計算（proxy，非真實 CLV）
        home_ml = row.get("home_ml_odds", None)
        away_ml = row.get("away_ml_odds", None)

        if bet_side == "HOME":
            if actual_win == 1:
                if home_ml and home_ml > 0:
                    pnl = stake * home_ml / 100.0
                else:
                    pnl = stake * (100.0 / abs(home_ml)) if home_ml else stake * (100.0 / 110.0)
            else:
                pnl = -stake
        elif bet_side == "AWAY":
            if actual_win == 0:
                if away_ml and away_ml > 0:
                    pnl = stake * away_ml / 100.0
                else:
                    pnl = stake * (100.0 / abs(away_ml)) if away_ml else stake * (100.0 / 110.0)
            else:
                pnl = -stake
        else:
            pnl = 0.0

        roi = pnl / max(stake, 1e-8)

        # Calibration penalty：ECE 越高懲罰越重
        ece = float(row.get("ece", 0.035))
        calibration_penalty = calibration_pw * max(0.0, ece - 0.035)

        reward = MARLReward(
            proxy_profit_loss=round(pnl, 6),
            roi=round(roi, 6),
            drawdown_penalty=0.0,   # 由 calculate_cumulative_drawdown 事後填入
            calibration_penalty=round(calibration_penalty, 6),
            volatility_penalty=0.0,  # 由 aggregate_strategy_stats 事後填入
        )

    # ── P7: true PnL 計算 ────────────────────────────────────────────────
    true_pnl: Optional[float] = None
    selected_side_win: Optional[int] = None
    reward_source = "EV_PROXY"

    if actual_home_win is not None and should_bet:
        home_ml = row.get("home_ml_odds", None)
        away_ml = row.get("away_ml_odds", None)
        bet_side_str = row.get("bet_side", "NO_BET")
        stake_true = state.stake_unit * kelly_mult / 0.25
        true_pnl = calc_true_pnl(
            side=bet_side_str,
            actual_home_win=int(actual_home_win),
            stake=stake_true,
            home_ml=float(home_ml) if home_ml is not None else None,
            away_ml=float(away_ml) if away_ml is not None else None,
        )
        reward_source = "TRUE_OUTCOME"
        # selected_side_win
        bet_side_upper = bet_side_str.upper() if bet_side_str else ""
        ahw = int(actual_home_win)
        if bet_side_upper == "HOME":
            selected_side_win = ahw
        elif bet_side_upper == "AWAY":
            selected_side_win = 1 - ahw
        # 同步更新 proxy_profit_loss 為 true pnl
        reward.proxy_profit_loss = true_pnl
    elif actual_home_win is not None:
        # 有 actual 但未下注 → 僅記錄 selected_side_win
        ahw = int(actual_home_win)
        bet_side_upper = (row.get("bet_side", "") or "").upper()
        if bet_side_upper == "HOME":
            selected_side_win = ahw
        elif bet_side_upper == "AWAY":
            selected_side_win = 1 - ahw
        reward_source = "TRUE_OUTCOME"

    return MARLRecord(
        state=state,
        action=action,
        reward=reward,
        actual_home_win=int(actual_home_win) if actual_home_win is not None else None,
        paper_only=True,
        source_trace=str(row.get("source_trace", "")),
        invalid_for_reward=invalid_for_reward,
        true_profit_loss=true_pnl,
        selected_side_win=selected_side_win,
        reward_source=reward_source,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 風險計算工具
# ══════════════════════════════════════════════════════════════════════════════

def calculate_cumulative_drawdown(records: List[MARLRecord]) -> float:
    """
    計算最大累計回撤（peak-to-trough）。
    只考慮有效下注且有結算結果的記錄。
    """
    cumulative_pnl = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for rec in records:
        if not rec.action.bet or rec.invalid_for_reward:
            continue
        cumulative_pnl += rec.reward.proxy_profit_loss
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        trough = peak - cumulative_pnl
        if trough > max_drawdown:
            max_drawdown = trough

    return round(max_drawdown, 6)


def calculate_risk_adjusted_score(
    roi: float,
    drawdown: float,
    volatility: float,
    roi_weight: float = 0.6,
    drawdown_weight: float = 0.3,
    volatility_weight: float = 0.1,
) -> float:
    """風險調整分數：roi_weight * roi - drawdown_weight * drawdown - volatility_weight * vol"""
    return round(
        roi_weight * roi - drawdown_weight * drawdown - volatility_weight * volatility,
        6,
    )


# ══════════════════════════════════════════════════════════════════════════════
# P3 — Reward Contract（真實賽果版）
# ══════════════════════════════════════════════════════════════════════════════

# 明確禁止進入 reward 計算的欄位前綴
_PROHIBITED_EV_PROXY_PREFIXES = ("ev_proxy_",)

# 明確禁止的 hard-coded 賠率 literal（用於靜態分析守衛）
_FORBIDDEN_LITERALS = (110, -110, 1.1, -1.1)


def _check_prohibited_ev_proxy(record: dict) -> None:
    """若 record 中含有 ev_proxy_* 欄位，立即 raise ValueError。"""
    for key in record:
        for prefix in _PROHIBITED_EV_PROXY_PREFIXES:
            if key.startswith(prefix):
                raise ValueError(
                    f"[P3 Reward Contract] Prohibited EV-proxy field detected: "
                    f"'{key}' must not enter reward computation."
                )


def _get_artifact_decimal_odds(record: dict, side: str) -> Optional[float]:
    """
    從 artifact 欄位讀取 decimal odds。
    優先順序：
    1. payout_assumption_decimal（artifact 直接帶入）
    2. home_ml_odds / away_ml_odds（美式轉 decimal）
    禁止 hard-coded -110 / -1.1 fallback。
    若無任何 odds 欄位 → 回傳 None（caller 應 skip "missing_odds"）。
    """
    # payout_assumption_decimal 欄位（artifact 層帶入）
    pad = record.get("payout_assumption_decimal")
    if pad is not None:
        return float(pad)

    side_upper = (side or "").upper()
    if side_upper == "HOME":
        ml = record.get("home_ml_odds")
    elif side_upper == "AWAY":
        ml = record.get("away_ml_odds")
    else:
        return None

    if ml is None:
        return None
    return american_to_decimal_odds(float(ml))


def compute_true_outcome_reward(record: dict) -> dict:
    """
    P3 Reward Contract：僅允許真實賽果作為 reward 來源。

    允許的 reward 來源：
    - actual_outcome（actual_home_win 欄位）
    - selected_side（bet_side 欄位）
    - artifact decimal odds（home_ml_odds / away_ml_odds / payout_assumption_decimal）
    - stake_units_paper（stake_unit 欄位）
    - paper_only=true

    明確禁止：
    - ev_proxy_* 任何欄位 → raise ValueError
    - ambiguous_doubleheader=true → skip "ambiguous_doubleheader"
    - paper_only=false → raise ValueError
    - hard-coded -110 payout（本函式不含任何 110/1.1 literal）
    - predictor re-score（本函式不呼叫任何預測模型）

    回傳 dict：
    {
      "status": "ok" | "skip",
      "skip_reason": str | None,
      "reward": float | None,
      "reward_source": "TRUE_OUTCOME",
      "paper_only": True,
      "game_id": str,
      "bet_side": str,
      "actual_home_win": int | None,
      "stake_unit": float,
      "decimal_odds": float | None,
      "selected_side_win": int | None,
    }
    """
    # ── 禁止 EV-proxy 欄位 ─────────────────────────────────────────────────
    _check_prohibited_ev_proxy(record)

    # ── 禁止 paper_only=false ─────────────────────────────────────────────
    if record.get("paper_only") is False:
        raise ValueError(
            "[P3 Reward Contract] paper_only=false record is forbidden in reward computation."
        )

    game_id = record.get("game_id", "")
    bet_side = (record.get("bet_side") or "").upper()

    # ── 禁止 ambiguous_doubleheader ──────────────────────────────────────
    if record.get("ambiguous_doubleheader") is True:
        return {
            "status": "skip",
            "skip_reason": "ambiguous_doubleheader",
            "reward": None,
            "reward_source": "TRUE_OUTCOME",
            "paper_only": True,
            "game_id": game_id,
            "bet_side": bet_side,
            "actual_home_win": None,
            "stake_unit": float(record.get("stake_unit") or 0.0),
            "decimal_odds": None,
            "selected_side_win": None,
        }

    # ── 缺少 actual_outcome ───────────────────────────────────────────────
    actual_home_win = record.get("actual_home_win")
    if actual_home_win is None:
        return {
            "status": "skip",
            "skip_reason": "missing_outcome",
            "reward": None,
            "reward_source": "TRUE_OUTCOME",
            "paper_only": True,
            "game_id": game_id,
            "bet_side": bet_side,
            "actual_home_win": None,
            "stake_unit": float(record.get("stake_unit") or 0.0),
            "decimal_odds": None,
            "selected_side_win": None,
        }

    actual_home_win = int(actual_home_win)
    stake = float(record.get("stake_unit") or 0.0)

    # ── NO_BET 不計算 reward（skip with reason side_mismatch）─────────────
    if bet_side not in ("HOME", "AWAY"):
        return {
            "status": "skip",
            "skip_reason": "side_mismatch",
            "reward": None,
            "reward_source": "TRUE_OUTCOME",
            "paper_only": True,
            "game_id": game_id,
            "bet_side": bet_side,
            "actual_home_win": actual_home_win,
            "stake_unit": stake,
            "decimal_odds": None,
            "selected_side_win": None,
        }

    # ── 缺少 odds（禁止 hard-coded fallback）─────────────────────────────
    decimal_odds = _get_artifact_decimal_odds(record, bet_side)
    if decimal_odds is None:
        return {
            "status": "skip",
            "skip_reason": "missing_odds",
            "reward": None,
            "reward_source": "TRUE_OUTCOME",
            "paper_only": True,
            "game_id": game_id,
            "bet_side": bet_side,
            "actual_home_win": actual_home_win,
            "stake_unit": stake,
            "decimal_odds": None,
            "selected_side_win": None,
        }

    # ── selected_side_win 計算 ────────────────────────────────────────────
    if bet_side == "HOME":
        selected_side_win = actual_home_win          # 1=home 贏=我贏
    else:  # AWAY
        selected_side_win = 1 - actual_home_win      # 1=away 贏=我贏

    # ── Reward 計算（decimal odds formula）───────────────────────────────
    # Win:  reward = stake * (decimal_odds - 1)
    # Lose: reward = -stake
    # Push: reward = 0（棒球通常無平局，預留）
    if selected_side_win == 1:
        reward = round(stake * (decimal_odds - 1.0), 6)
    elif selected_side_win == 0:
        reward = round(-stake, 6)
    else:
        reward = 0.0  # push/draw

    return {
        "status": "ok",
        "skip_reason": None,
        "reward": reward,
        "reward_source": "TRUE_OUTCOME",
        "paper_only": True,
        "game_id": game_id,
        "bet_side": bet_side,
        "actual_home_win": actual_home_win,
        "stake_unit": stake,
        "decimal_odds": round(decimal_odds, 6),
        "selected_side_win": selected_side_win,
    }


def audit_reward_contract(
    records: list,
    output_path: Optional[str] = None,
) -> dict:
    """
    對 artifact records 跑 P3 reward contract audit。
    回傳 audit summary dict，可選擇寫入 JSON 檔案。
    """
    import json as _json

    n_total = len(records)
    valid_count = 0
    skip_missing_outcome = 0
    skip_missing_odds = 0
    skip_ambiguous = 0
    skip_paper_only_false = 0
    skip_side_mismatch = 0
    ev_proxy_errors = 0

    for r in records:
        try:
            result = compute_true_outcome_reward(r)
            if result["status"] == "ok":
                valid_count += 1
            else:
                reason = result.get("skip_reason", "")
                if reason == "missing_outcome":
                    skip_missing_outcome += 1
                elif reason == "missing_odds":
                    skip_missing_odds += 1
                elif reason == "ambiguous_doubleheader":
                    skip_ambiguous += 1
                elif reason == "side_mismatch":
                    skip_side_mismatch += 1
        except ValueError as e:
            msg = str(e)
            if "EV-proxy" in msg or "ev_proxy" in msg:
                ev_proxy_errors += 1
            elif "paper_only=false" in msg:
                skip_paper_only_false += 1

    audit = {
        "audit_date": "2026-05-20",
        "paper_only": True,
        "reward_formula": (
            "win → reward = stake_unit * (decimal_odds - 1); "
            "lose → reward = -stake_unit; push → reward = 0. "
            "decimal_odds 從 artifact 欄位讀取（payout_assumption_decimal → home/away_ml_odds 轉換），"
            "禁止 hard-coded -110 fallback。"
        ),
        "prohibited_fields": [
            "ev_proxy_*（任何以 ev_proxy_ 開頭的欄位）",
            "hard-coded -110 / -1.1 payout literal",
        ],
        "exclusion_rules": [
            "paper_only=false → raise ValueError（硬性終止）",
            "ambiguous_doubleheader=true → skip 'ambiguous_doubleheader'",
            "actual_home_win 缺失 → skip 'missing_outcome'",
            "無可用 odds → skip 'missing_odds'（禁止 hard-coded fallback）",
            "bet_side 非 HOME/AWAY → skip 'side_mismatch'",
            "ev_proxy_* 欄位存在 → raise ValueError",
            "禁止在 reward 函式內呼叫任何 predictor 模型（look-ahead leakage 防護）",
        ],
        "sample_records_audited": n_total,
        "valid_reward_count": valid_count,
        "skipped_missing_outcome": skip_missing_outcome,
        "skipped_missing_odds": skip_missing_odds,
        "skipped_ambiguous_doubleheader": skip_ambiguous,
        "skipped_paper_only_false": skip_paper_only_false,
        "skipped_side_mismatch": skip_side_mismatch,
        "ev_proxy_errors": ev_proxy_errors,
        "p4_usage_notes": (
            "P4 optimizer fitness 只應使用 status='ok' 的記錄。"
            "skipped_* 計數需寫入 P4 champion gate 的 exclusion log。"
            "禁止將 ev_proxy_* 欄位傳入 compute_risk_adjusted_fitness。"
        ),
        "annotation": (
            "此 audit 檔案為 P3 reward contract 驗證結果，"
            "所有計算基於真實賽果（actual_home_win），"
            "paper_only=true，不代表任何實盤獲利能力。"
        ),
    }

    if output_path:
        import os as _os
        _os.makedirs(_os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            _json.dump(audit, f, ensure_ascii=False, indent=2)

    return audit


def aggregate_strategy_stats(records: List[MARLRecord], strategy_name: str) -> dict:
    """
    彙總策略統計，回傳 dict 含核心指標。
    proxy ROI 非真實 CLV，已標示於輸出。
    """
    total_records = len(records)
    bet_records = [r for r in records if r.action.bet]
    valid_reward_records = [r for r in bet_records if not r.invalid_for_reward]

    total_bets = len(bet_records)
    coverage = total_bets / max(total_records, 1)

    pnls = [r.reward.proxy_profit_loss for r in valid_reward_records]
    wins = [r for r in valid_reward_records if r.reward.proxy_profit_loss > 0]
    hit_rate = len(wins) / max(len(valid_reward_records), 1)

    total_pnl = sum(pnls)
    total_staked = sum(r.state.stake_unit * r.action.stake_multiplier / 0.25
                       for r in valid_reward_records)
    proxy_roi = total_pnl / max(total_staked, 1e-8)

    average_edge = statistics.mean([r.state.edge for r in bet_records]) if bet_records else 0.0
    average_stake = statistics.mean([r.state.stake_unit for r in bet_records]) if bet_records else 0.0

    # Volatility（PnL 標準差）
    volatility = statistics.stdev(pnls) if len(pnls) >= 2 else 0.0

    max_drawdown = calculate_cumulative_drawdown(records)

    risk_adjusted_score = calculate_risk_adjusted_score(proxy_roi, max_drawdown, volatility)

    # Fold-level 統計
    fold_stats: Dict[int, dict] = {}
    for rec in valid_reward_records:
        fold = rec.state.walk_forward_fold
        if fold not in fold_stats:
            fold_stats[fold] = {"bets": 0, "wins": 0, "pnl": 0.0, "staked": 0.0}
        fold_stats[fold]["bets"] += 1
        if rec.reward.proxy_profit_loss > 0:
            fold_stats[fold]["wins"] += 1
        fold_stats[fold]["pnl"] += rec.reward.proxy_profit_loss
        fold_stats[fold]["staked"] += rec.state.stake_unit * rec.action.stake_multiplier / 0.25

    fold_level = {}
    for fold, fs in sorted(fold_stats.items()):
        fold_roi = fs["pnl"] / max(fs["staked"], 1e-8)
        fold_hit = fs["wins"] / max(fs["bets"], 1)
        fold_level[f"fold_{fold}"] = {
            "bets": fs["bets"],
            "hit_rate": round(fold_hit, 4),
            "proxy_roi": round(fold_roi, 4),
            "total_pnl": round(fs["pnl"], 4),
        }

    return {
        "strategy_name": strategy_name,
        "total_records": total_records,
        "total_bets": total_bets,
        "coverage": round(coverage, 4),
        "valid_reward_records": len(valid_reward_records),
        "proxy_roi": round(proxy_roi, 6),
        "proxy_roi_disclaimer": "proxy ROI — NOT real CLV. Based on POST_GAME_PROXY odds only.",
        "hit_rate": round(hit_rate, 4),
        "average_edge": round(average_edge, 6),
        "average_stake": round(average_stake, 6),
        "max_drawdown": round(max_drawdown, 6),
        "volatility": round(volatility, 6),
        "risk_adjusted_score": round(risk_adjusted_score, 6),
        "total_pnl": round(total_pnl, 6),
        "fold_level": fold_level,
        "paper_only": True,
    }
