"""
棒球世界模型 (Baseball World Model) — Phase 6A
===============================================
借鑑 MiroFish「平行數字世界」概念，在逐打席（PA）層級模擬比賽。

核心差異 vs. 現有 monte_carlo.py：
  現有（Poisson）: 每局得分 ~ Gamma-Poisson(λ)，無個別球員資訊
  世界模型（PA）: 逐打席模擬，球員個性化習慣，捕捉尾端風險

模擬流程：
  1. 打席結果：BB / K / HBP / 安打 / 出局
     ↑ 由投手 k_pct/bb_pct + 打者 contact_pct/discipline 共同決定
  2. 壘包狀態：[0-7] Markov 轉移
  3. 得分積累：到第 3 出局為止
  4. 重複 N 次（預設 10,000）→ 分佈型預測

輸出 WorldModelResult：
  - home_win_prob / away_win_prob
  - score_distribution（含完整尾端）
  - expected_runs（主/客）
  - tail_risk_score：P(總分 ≥ 15)，捕捉爆炸性比賽
  - shutout_prob：P(某隊 0 分)
  - blowout_prob：P(分差 ≥ 7)
  - run_support_uncertainty：得分標準差（高 = 不確定性大）

設計原則：
  - 向後相容：可與 monte_carlo.py / hierarchical_mc.py 同時使用
  - 無外部依賴（pure numpy）
  - 球員特徵由 PitcherSnapshot / BatterSnapshot 提供，缺失時用聯盟平均
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from wbc_backend.domain.schemas import BatterSnapshot, PitcherSnapshot

logger = logging.getLogger(__name__)

# ── 聯盟平均基準（MLB 2025） ──────────────────────────────────────────────
_LG_K_PCT = 0.228
_LG_BB_PCT = 0.085
_LG_CONTACT_PCT = 0.773
_LG_BABIP = 0.296
_LG_BARREL_PCT = 0.081
_LG_HARD_HIT_PCT = 0.382
_LG_SPRINT_SPEED = 27.0
_LG_HR9 = 1.20
_LG_GB_PCT = 0.43


# ══════════════════════════════════════════════════════════════════════════════
# 資料類別
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PlayerProfile:
    """
    世界模型用的輕量球員資料（從 PitcherSnapshot / BatterSnapshot 提取）。
    支援以 name 字串建構（用聯盟平均作為 fallback）。
    """
    name: str
    role: str                    # "pitcher" | "batter"
    # 投手屬性
    k_pct: float = _LG_K_PCT
    bb_pct: float = _LG_BB_PCT
    hr9: float = _LG_HR9
    gb_pct: float = _LG_GB_PCT
    stuff_plus: float = 100.0
    # 打者屬性
    contact_pct: float = _LG_CONTACT_PCT
    babip: float = _LG_BABIP
    barrel_pct: float = _LG_BARREL_PCT
    hard_hit_pct: float = _LG_HARD_HIT_PCT
    sprint_speed: float = _LG_SPRINT_SPEED
    bb_rate: float = _LG_BB_PCT   # 打者四壞球率
    k_rate: float = _LG_K_PCT     # 打者三振率

    @classmethod
    def from_pitcher(cls, sp: PitcherSnapshot) -> "PlayerProfile":
        """從 PitcherSnapshot 建構投手 Profile"""
        k_pct = sp.k_per_9 / (sp.k_per_9 + sp.bb_per_9 + 24.0 + 1e-6)
        bb_pct = sp.bb_per_9 / (sp.k_per_9 + sp.bb_per_9 + 24.0 + 1e-6)
        hr9 = max(0.3, sp.era / 3.0)   # FIP-style HR/9 proxy
        gb_pct = _LG_GB_PCT + (sp.fip - 4.20) * (-0.02)  # 低 FIP → 更多 GB
        return cls(
            name=sp.name,
            role="pitcher",
            k_pct=float(np.clip(k_pct, 0.12, 0.38)),
            bb_pct=float(np.clip(bb_pct, 0.04, 0.18)),
            hr9=float(np.clip(hr9, 0.3, 2.5)),
            gb_pct=float(np.clip(gb_pct, 0.30, 0.65)),
            stuff_plus=float(np.clip(sp.stuff_plus, 50, 200)),
        )

    @classmethod
    def from_batter(cls, b: BatterSnapshot) -> "PlayerProfile":
        """從 BatterSnapshot 建構打者 Profile"""
        return cls(
            name=b.name,
            role="batter",
            contact_pct=float(np.clip(b.contact_pct, 0.55, 0.95)),
            babip=float(np.clip(b.babip, 0.220, 0.400)),
            barrel_pct=float(np.clip(b.barrel_pct, 0.01, 0.25)),
            hard_hit_pct=float(np.clip(b.hard_hit_pct, 0.20, 0.65)),
            sprint_speed=float(np.clip(b.sprint_speed, 22.0, 32.0)),
            bb_rate=float(np.clip(b.bb_pct, 0.04, 0.20)),
            k_rate=float(np.clip(b.k_pct, 0.08, 0.40)),
        )

    @classmethod
    def league_average_pitcher(cls, name: str = "Average SP") -> "PlayerProfile":
        return cls(name=name, role="pitcher")

    @classmethod
    def league_average_batter(cls, name: str = "Average Batter") -> "PlayerProfile":
        return cls(name=name, role="batter")


@dataclass
class WorldModelConfig:
    """世界模型配置"""
    n_simulations: int = 10_000     # 模擬場次數
    n_innings: int = 9               # 局數（含延長最多 12）
    max_innings: int = 12
    mercy_rule: bool = True          # WBC 慈悲規則
    mercy_lead_7th: int = 10        # 第 7 局起差 10 分
    mercy_lead_5th: int = 15        # 第 5 局起差 15 分
    hbp_rate: float = 0.010         # 觸身球機率（每打席）
    seed: int = 42


@dataclass
class WorldModelResult:
    """世界模型輸出（分佈型預測，非點預測）"""
    home_win_prob: float
    away_win_prob: float
    expected_home_runs: float
    expected_away_runs: float
    std_home_runs: float
    std_away_runs: float

    # 分佈指標
    tail_risk_score: float          # P(total >= 15)，爆炸性比賽
    shutout_prob_home: float        # P(主隊被完封)
    shutout_prob_away: float        # P(客隊被完封)
    blowout_prob: float             # P(|主分-客分| >= 7)
    extra_innings_prob: float       # P(延長賽)

    # 得分分佈（前 15 個最常見比分）
    score_distribution: dict[str, float] = field(default_factory=dict)
    # 各總分機率（0-25）
    total_runs_dist: dict[int, float] = field(default_factory=dict)

    n_simulations: int = 10_000


# ══════════════════════════════════════════════════════════════════════════════
# 打席結果模擬
# ══════════════════════════════════════════════════════════════════════════════

# 壘包狀態：bit mask 0=none, 1=1B, 2=2B, 4=3B
# 0-7 表示 8 種壘包狀態
# runs_on_hit[base_state][hit_type] = (runs_scored, new_base_state)
# 簡化：使用查表法（不完整的 Markov，但足夠準確）

def _simulate_pa(
    pitcher: PlayerProfile,
    batter: PlayerProfile,
    rng: np.random.Generator,
    hbp_rate: float = 0.010,
) -> str:
    """
    模擬單一打席（PA）結果。

    Returns:
        "K" | "BB" | "HBP" | "HR" | "2B" | "3B" | "1B" | "GO" | "FO" | "PO"
        GO = 滾地球出局, FO = 飛球出局, PO = 一般出局

    機率模型：
      1. BB：投手 bb_pct 調整打者 bb_rate
      2. K：投手 k_pct 調整打者 k_rate
      3. HBP：固定機率
      4. 安打/出局：由 babip, barrel_pct, hard_hit_pct 決定
    """
    roll = rng.random()
    cumsum = 0.0

    # 四壞球（投手主導）
    p_bb = float(np.clip(
        0.5 * pitcher.bb_pct + 0.5 * batter.bb_rate,
        0.03, 0.18,
    ))
    cumsum += p_bb
    if roll < cumsum:
        return "BB"

    # 三振
    p_k = float(np.clip(
        0.5 * pitcher.k_pct + 0.5 * batter.k_rate,
        0.10, 0.40,
    ))
    # stuff_plus 提升三振（每高 10 → +1%）
    p_k *= (1.0 + (pitcher.stuff_plus - 100) * 0.001)
    p_k = float(np.clip(p_k, 0.10, 0.40))
    cumsum += p_k
    if roll < cumsum:
        return "K"

    # 觸身球
    cumsum += hbp_rate
    if roll < cumsum:
        return "HBP"

    # 剩餘：有可能安打
    p_remaining = 1.0 - cumsum

    # 在有球遇到的情況下：
    # P(安打) ≈ BABIP × contact_pct + HR
    # P(HR)
    p_hr = float(np.clip(
        batter.barrel_pct * 0.5 + pitcher.hr9 / 27.0,
        0.005, 0.12,
    ))
    # P(2B/3B)
    p_xbh = float(np.clip(batter.hard_hit_pct * 0.15, 0.03, 0.10))
    p_3b = float(np.clip((batter.sprint_speed - 25) * 0.005, 0.005, 0.03))
    p_2b = p_xbh - p_3b
    # P(1B) = babip - hr - 2b - 3b
    p_1b = float(np.clip(batter.babip - p_hr - p_2b - p_3b, 0.08, 0.28))

    # 正規化
    total_contact = p_hr + p_2b + p_3b + p_1b
    scale = p_remaining / max(total_contact + (p_remaining - total_contact), 1e-8)

    # 安打類型
    sub_roll = rng.random()
    sub_cum = 0.0

    sub_cum += p_hr * scale
    if sub_roll < sub_cum:
        return "HR"
    sub_cum += p_3b * scale
    if sub_roll < sub_cum:
        return "3B"
    sub_cum += p_2b * scale
    if sub_roll < sub_cum:
        return "2B"
    sub_cum += p_1b * scale
    if sub_roll < sub_cum:
        return "1B"

    # 出局（滾地 vs 飛球）
    if rng.random() < pitcher.gb_pct:
        return "GO"   # 滾地球出局（GIDP 機率小）
    return "FO"   # 飛球出局


def _advance_runners(
    base_state: int,
    outcome: str,
    outs: int,
    rng: np.random.Generator,
    sprint_speed: float = _LG_SPRINT_SPEED,
) -> tuple[int, int]:
    """
    根據打席結果更新壘包狀態並計算本局得分。

    Args:
        base_state: 當前壘包（bit mask: 1=1B, 2=2B, 4=3B）
        outcome: PA 結果
        outs: 當前出局數（0-2）
        sprint_speed: 打者跑速（影響進壘決策）

    Returns:
        (runs_scored, new_base_state)
    """
    runs = 0
    # 快速跑者更可能多進一壘
    speed_bonus = max(0.0, (sprint_speed - 27.0) / 10.0)  # -0.5 ~ +0.5

    if outcome in ("GO", "FO", "K"):
        # 出局，但 FO 可能讓三壘跑者回來
        if outcome == "FO" and (base_state & 4) and outs < 2:
            # 犧牲飛球（簡化：60% 機率）
            if rng.random() < 0.55 + speed_bonus * 0.1:
                runs += 1
                base_state &= ~4   # 清除三壘
        # GO 可能 GIDP（有跑者在一壘時）
        # 簡化：不額外計算 GIDP 的二次出局
        return runs, base_state

    elif outcome == "BB" or outcome == "HBP":
        # 四壞球或觸身球：有人在壘的跑者依序前進
        # 滿壘 → 得 1 分
        if base_state == 7:  # 滿壘
            runs = 1
            base_state = 7  # 跑者都前進一個，但狀態不變（新打者上1B）
        elif (base_state & 1) and (base_state & 2):
            # 1B, 2B 有人 → 2B 跑者上3B，1B 跑者上2B，打者上1B
            base_state |= 4   # 三壘
            # 若三壘原本有人（已處理），不重複計分
        elif (base_state & 1):
            # 1B 有人 → 跑者上2B，打者上1B
            base_state |= 2
            base_state |= 1
        else:
            # 打者上1B
            base_state |= 1
        return runs, base_state

    elif outcome == "1B":
        # 跑者前進 1-2 壘（三壘跑者得分，二壘跑者通常到三壘）
        if base_state & 4:   # 三壘有人
            runs += 1
            base_state &= ~4
        if base_state & 2:   # 二壘有人 → 通常上三壘
            if rng.random() < 0.85 + speed_bonus * 0.1:
                base_state |= 4
            else:
                base_state |= 4  # 保守版也上三壘
            base_state &= ~2
        if base_state & 1:   # 一壘有人 → 通常上二壘
            base_state |= 2
            base_state &= ~1
        base_state |= 1      # 打者上一壘
        return runs, base_state

    elif outcome == "2B":
        # 三壘/二壘跑者得分，一壘跑者到三壘
        if base_state & 4:
            runs += 1
            base_state &= ~4
        if base_state & 2:
            runs += 1
            base_state &= ~2
        if base_state & 1:
            if rng.random() < 0.55 + speed_bonus * 0.2:
                runs += 1   # 快跑者衝本壘
                base_state &= ~1
            else:
                base_state |= 4  # 到三壘
                base_state &= ~1
        base_state |= 2      # 打者上二壘
        return runs, base_state

    elif outcome == "3B":
        # 所有跑者得分
        if base_state & 4:
            runs += 1
            base_state &= ~4
        if base_state & 2:
            runs += 1
            base_state &= ~2
        if base_state & 1:
            runs += 1
            base_state &= ~1
        base_state |= 4      # 打者上三壘
        return runs, base_state

    elif outcome == "HR":
        # 所有跑者（含打者）得分
        runner_count = bin(base_state).count("1") + 1  # +1 for batter
        runs += runner_count
        base_state = 0       # 清壘
        return runs, base_state

    return runs, base_state


# ══════════════════════════════════════════════════════════════════════════════
# 半局模擬
# ══════════════════════════════════════════════════════════════════════════════

def _simulate_half_inning(
    pitcher: PlayerProfile,
    lineup: list[PlayerProfile],
    lineup_pos: int,
    rng: np.random.Generator,
    hbp_rate: float = 0.010,
    max_pa: int = 20,   # 防止無限循環
) -> tuple[int, int]:
    """
    模擬半局（直到 3 出局）。

    Returns:
        (runs_scored, next_lineup_pos)
    """
    outs = 0
    base_state = 0   # 0 = 壘上無人
    runs = 0
    n_lineup = len(lineup) if lineup else 9
    pa_count = 0

    while outs < 3 and pa_count < max_pa:
        batter = lineup[lineup_pos % n_lineup] if lineup else PlayerProfile.league_average_batter()
        lineup_pos = (lineup_pos + 1) % n_lineup
        pa_count += 1

        outcome = _simulate_pa(pitcher, batter, rng, hbp_rate)

        if outcome in ("K", "GO", "FO"):
            # 計算犧牲飛球/出局壘包推進
            run_add, base_state = _advance_runners(base_state, outcome, outs, rng)
            runs += run_add
            outs += 1
        else:
            run_add, base_state = _advance_runners(base_state, outcome, outs, rng)
            runs += run_add

    return runs, lineup_pos % n_lineup


# ══════════════════════════════════════════════════════════════════════════════
# 主要 API
# ══════════════════════════════════════════════════════════════════════════════

def run_world_model(
    home_sp: Optional[PlayerProfile] = None,
    away_sp: Optional[PlayerProfile] = None,
    home_lineup: Optional[list[PlayerProfile]] = None,
    away_lineup: Optional[list[PlayerProfile]] = None,
    config: Optional[WorldModelConfig] = None,
) -> WorldModelResult:
    """
    執行棒球世界模型模擬（逐打席，分佈型預測）。

    Args:
        home_sp: 主隊先發投手 Profile（None = 聯盟平均）
        away_sp: 客隊先發投手 Profile（None = 聯盟平均）
        home_lineup: 主隊打線（None = 9 個聯盟平均打者）
        away_lineup: 客隊打線（None = 9 個聯盟平均打者）
        config: 模擬配置

    Returns:
        WorldModelResult（分佈型預測）
    """
    if config is None:
        config = WorldModelConfig()

    # 設定 fallback
    if home_sp is None:
        home_sp = PlayerProfile.league_average_pitcher("Home SP")
    if away_sp is None:
        away_sp = PlayerProfile.league_average_pitcher("Away SP")
    if not home_lineup:
        home_lineup = [PlayerProfile.league_average_batter(f"H{i+1}") for i in range(9)]
    if not away_lineup:
        away_lineup = [PlayerProfile.league_average_batter(f"A{i+1}") for i in range(9)]

    rng = np.random.default_rng(config.seed)
    n = config.n_simulations

    home_scores = np.zeros(n, dtype=int)
    away_scores = np.zeros(n, dtype=int)
    final_innings = np.zeros(n, dtype=int)

    for sim in range(n):
        h_score = 0
        a_score = 0
        h_lp = 0  # lineup position
        a_lp = 0
        game_ended = False

        for inn in range(1, config.max_innings + 1):
            if game_ended:
                break

            # 客隊上半局
            a_runs, a_lp = _simulate_half_inning(
                home_sp, away_lineup, a_lp, rng, config.hbp_rate,
            )
            a_score += a_runs

            # 主隊下半局（第 9 局後若落後不用打）
            if not (inn >= 9 and h_score > a_score):
                h_runs, h_lp = _simulate_half_inning(
                    away_sp, home_lineup, h_lp, rng, config.hbp_rate,
                )
                h_score += h_runs

            # WBC 慈悲規則
            if config.mercy_rule:
                lead = abs(h_score - a_score)
                if (inn == 5 and lead >= config.mercy_lead_5th) or \
                   (inn >= 7 and lead >= config.mercy_lead_7th):
                    game_ended = True

            # 標準賽末
            if inn >= 9 and h_score != a_score:
                game_ended = True

            final_innings[sim] = inn

        home_scores[sim] = h_score
        away_scores[sim] = a_score

    # ── 統計計算 ─────────────────────────────────────────────────────────────
    home_win = home_scores > away_scores
    totals = home_scores + away_scores
    margin = home_scores.astype(float) - away_scores.astype(float)

    home_win_prob = float(home_win.mean())
    expected_home = float(home_scores.mean())
    expected_away = float(away_scores.mean())
    std_home = float(home_scores.std())
    std_away = float(away_scores.std())

    tail_risk = float((totals >= 15).mean())
    shutout_home = float((home_scores == 0).mean())
    shutout_away = float((away_scores == 0).mean())
    blowout = float((np.abs(margin) >= 7).mean())
    extra_inn = float((final_innings > 9).mean())

    # 比分分佈（前 15 個）
    score_dist: dict[str, float] = {}
    for h, a in zip(home_scores[:min(n, 20000)], away_scores[:min(n, 20000)]):
        key = f"{h}-{a}"
        score_dist[key] = score_dist.get(key, 0) + 1
    top_scores = dict(sorted(score_dist.items(), key=lambda x: -x[1])[:15])
    for k in top_scores:
        top_scores[k] = round(top_scores[k] / min(n, 20000), 4)

    # 總分分佈（0-25）
    total_dist: dict[int, float] = {}
    for t in range(0, 26):
        total_dist[t] = round(float((totals == t).mean()), 4)

    return WorldModelResult(
        home_win_prob=round(home_win_prob, 4),
        away_win_prob=round(1 - home_win_prob, 4),
        expected_home_runs=round(expected_home, 3),
        expected_away_runs=round(expected_away, 3),
        std_home_runs=round(std_home, 3),
        std_away_runs=round(std_away, 3),
        tail_risk_score=round(tail_risk, 4),
        shutout_prob_home=round(shutout_home, 4),
        shutout_prob_away=round(shutout_away, 4),
        blowout_prob=round(blowout, 4),
        extra_innings_prob=round(extra_inn, 4),
        score_distribution=top_scores,
        total_runs_dist=total_dist,
        n_simulations=n,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 便捷函數：從 Snapshot 物件直接建構
# ══════════════════════════════════════════════════════════════════════════════

def run_world_model_from_snapshots(
    home_sp: Optional[PitcherSnapshot] = None,
    away_sp: Optional[PitcherSnapshot] = None,
    home_batters: Optional[list[BatterSnapshot]] = None,
    away_batters: Optional[list[BatterSnapshot]] = None,
    n_simulations: int = 10_000,
    seed: int = 42,
    mercy_rule: bool = True,
) -> WorldModelResult:
    """
    從 PitcherSnapshot / BatterSnapshot 直接執行世界模型。
    （與現有 pipeline 的整合介面）
    """
    home_pitcher = PlayerProfile.from_pitcher(home_sp) if home_sp else None
    away_pitcher = PlayerProfile.from_pitcher(away_sp) if away_sp else None
    home_lineup_p = [PlayerProfile.from_batter(b) for b in home_batters] if home_batters else None
    away_lineup_p = [PlayerProfile.from_batter(b) for b in away_batters] if away_batters else None

    config = WorldModelConfig(
        n_simulations=n_simulations,
        seed=seed,
        mercy_rule=mercy_rule,
    )
    return run_world_model(
        home_sp=home_pitcher,
        away_sp=away_pitcher,
        home_lineup=home_lineup_p,
        away_lineup=away_lineup_p,
        config=config,
    )
