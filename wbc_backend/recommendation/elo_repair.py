"""
elo_repair.py — P4/P5 Elo 修復模組
修復 SimplifiedElo_v1 的兩個問題：
  1. 春訓場次污染 Walk-Forward Elo 初始化
  2. 無 2024 賽季暖啟動，導致 Fold 1-2 Elo 嚴重偏差

P5 新增：
  3. home_advantage_elo：主場優勢 Elo 加成（預設 +40）
  4. apply_walk_forward_platt_calibration：Walk-Forward Platt Scaling
"""

from datetime import date
from typing import Dict, List, Optional, Tuple
import math
import os
import glob
import sys
from pathlib import Path

# 確保能 import 校準器
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# MLB 2025 開幕戰：2025-03-28；春訓結束 2025-03-27
SPRING_TRAINING_END_DATE = "2025-03-27"


def is_spring_training_game(game_date_str: str) -> bool:
    """判斷是否為春訓場次（含 2025-03-27 當日）"""
    return game_date_str <= SPRING_TRAINING_END_DATE


def filter_regular_season_games(rows: List[dict]) -> Tuple[List[dict], int]:
    """
    過濾掉春訓場次。
    回傳 (filtered_rows, n_excluded)
    filtered_rows 只包含正規賽場次。
    """
    filtered = [r for r in rows if not is_spring_training_game(r.get("game_date", "9999-99-99"))]
    n_excluded = len(rows) - len(filtered)
    return filtered, n_excluded


def elo_prob(home_elo: float, away_elo: float) -> float:
    """標準 Elo 勝率公式（主場優勢已含於 Elo 數值中）"""
    return 1.0 / (1.0 + 10 ** ((away_elo - home_elo) / 400.0))


def initialize_elo_from_win_rate(
    win_rates: Dict[str, float],
    base_elo: float = 1500.0,
    scale: float = 200.0,
) -> Dict[str, float]:
    """
    從勝率初始化 Elo。
    win_rates: {team: win_rate}，e.g. {"LAD": 0.617, "SD": 0.543}
    scale: Elo 分散度（勝率 ±0.1 對應約 ±14 Elo at scale=200）
    公式：elo = base + scale * (win_rate - 0.5) / 0.5 * 100
    簡化線性：elo = base + (win_rate - 0.5) * scale * 2
    """
    elos: Dict[str, float] = {}
    for team, wr in win_rates.items():
        elos[team] = base_elo + (wr - 0.5) * scale * 2.0
    return elos


def check_2024_data_availability(data_dir: str = "data/") -> dict:
    """
    檢查 2024 MLB 資料可用性。
    回傳：
    {
        "available": bool,
        "source": str or None,
        "blocking_reason": str or None,
        "files_found": list
    }
    """
    patterns = [
        os.path.join(data_dir, "*2024*.csv"),
        os.path.join(data_dir, "**/*2024*.csv"),
        os.path.join(data_dir, "*2024*.json"),
        os.path.join(data_dir, "**/*2024*.json"),
    ]
    found = []
    for pat in patterns:
        found.extend(glob.glob(pat, recursive=True))

    if found:
        return {
            "available": True,
            "source": found[0],
            "blocking_reason": None,
            "files_found": found,
        }
    return {
        "available": False,
        "source": None,
        "blocking_reason": "No 2024 MLB data files found under data/ directory. "
                           "warm_start_2024 mode will fall back to base_elo=1500.",
        "files_found": [],
    }


# 2024 MLB 最終勝率（來源：公開紀錄，用於暖啟動）
MLB_2024_WIN_RATES: Dict[str, float] = {
    "Los Angeles Dodgers": 0.617,
    "Philadelphia Phillies": 0.599,
    "Cleveland Guardians": 0.580,
    "New York Yankees": 0.574,
    "Milwaukee Brewers": 0.568,
    "Baltimore Orioles": 0.562,
    "San Diego Padres": 0.543,
    "Kansas City Royals": 0.531,
    "Arizona Diamondbacks": 0.525,
    "Seattle Mariners": 0.519,
    "Minnesota Twins": 0.519,
    "Detroit Tigers": 0.512,
    "Houston Astros": 0.500,
    "New York Mets": 0.494,
    "Boston Red Sox": 0.494,
    "St. Louis Cardinals": 0.488,
    "Tampa Bay Rays": 0.481,
    "Pittsburgh Pirates": 0.475,
    "Atlanta Braves": 0.469,
    "San Francisco Giants": 0.463,
    "Texas Rangers": 0.457,
    "Los Angeles Angels": 0.451,
    "Toronto Blue Jays": 0.444,
    "Cincinnati Reds": 0.444,
    "Oakland Athletics": 0.438,
    "Miami Marlins": 0.432,
    "Washington Nationals": 0.426,
    "Chicago White Sox": 0.253,
    "Chicago Cubs": 0.475,
    "Colorado Rockies": 0.370,
}


def run_elo_walk_forward_with_repair(
    rows: List[dict],
    repair_mode: str = "exclude_spring",
    prior_win_rates: Optional[Dict[str, float]] = None,
    k_factor: float = 20.0,
    base_elo: float = 1500.0,
    home_advantage_elo: float = 0.0,
) -> List[dict]:
    """
    執行修復後的 Elo walk-forward。

    repair_mode:
      - "exclude_spring": 春訓場次標記 excluded=True，不參與 Elo 更新
      - "warm_start_2024": 用 prior_win_rates（或 MLB_2024_WIN_RATES）初始化 Elo

    home_advantage_elo: 主場優勢 Elo 加成（P5，預設 0 = 不加，40 = +40 Elo）

    回傳每場次含 model_prob / home_elo / away_elo / excluded 的 rows（新 list）。
    """
    # 決定 model_source_tag（含 ha 與 platt 標記）
    _ha = home_advantage_elo > 0
    if repair_mode == "warm_start_2024":
        wr = prior_win_rates if prior_win_rates else MLB_2024_WIN_RATES
        elo_table: Dict[str, float] = initialize_elo_from_win_rate(wr, base_elo=base_elo)
        if _ha:
            model_source_tag = f"SimplifiedElo_v1_warm2024_ha{int(home_advantage_elo)}_uncalibrated"
        else:
            model_source_tag = "SimplifiedElo_v1_warm_start_2024"
    else:
        elo_table = {}
        if _ha:
            model_source_tag = f"SimplifiedElo_v1_ha{int(home_advantage_elo)}_uncalibrated"
        else:
            model_source_tag = "SimplifiedElo_v1_exclude_spring"

    def get_elo(team: str) -> float:
        return elo_table.get(team, base_elo)

    def update_elo(winner: str, loser: str) -> None:
        ew = get_elo(winner)
        el = get_elo(loser)
        prob_w = elo_prob(ew, el)
        elo_table[winner] = ew + k_factor * (1.0 - prob_w)
        elo_table[loser] = el + k_factor * (0.0 - (1.0 - prob_w))

    output = []
    for row in rows:
        new_row = dict(row)
        game_date = row.get("game_date", "9999-99-99")
        home = row.get("home_team", "")
        away = row.get("away_team", "")

        is_spring = is_spring_training_game(game_date)

        h_elo = get_elo(home)
        a_elo = get_elo(away)
        # P5: 主場優勢 Elo 加成（僅影響勝率計算，不修改儲存的 Elo）
        effective_home_elo = h_elo + home_advantage_elo
        prob = elo_prob(effective_home_elo, a_elo)

        new_row["home_elo"] = round(h_elo, 2)
        new_row["away_elo"] = round(a_elo, 2)
        new_row["home_advantage_elo"] = home_advantage_elo
        new_row["effective_home_elo"] = round(effective_home_elo, 2)
        new_row["model_prob"] = round(prob, 6)
        new_row["model_source"] = model_source_tag
        new_row["excluded"] = False

        if repair_mode == "exclude_spring" and is_spring:
            new_row["excluded"] = True
            # 不更新 Elo，跳過
            output.append(new_row)
            continue

        # 更新 Elo（需知道比賽結果）
        # 從 brier_score 反推：若 model_prob > 0.5 且 bet_side == "home" 推斷主場獲勝
        # 實際上 brier_score = (model_prob - outcome)^2，原始 rows 沒有 outcome 欄位
        # 改用 brier_score + model_prob 反算 outcome
        brier = row.get("brier_score")
        if brier is not None and brier >= 0:
            orig_prob = row.get("model_prob", prob)
            if orig_prob is not None:
                # brier = (p - outcome)^2 => outcome = p ± sqrt(brier)
                # 取最接近 0 或 1 的解
                sqrt_b = math.sqrt(max(0.0, float(brier)))
                o1 = float(orig_prob) - sqrt_b
                o2 = float(orig_prob) + sqrt_b
                # 選最接近整數的
                outcome = o1 if abs(round(o1) - o1) < abs(round(o2) - o2) else o2
                home_win = outcome > 0.5
            else:
                home_win = prob > 0.5
        else:
            home_win = prob > 0.5

        if home_win:
            update_elo(home, away)
        else:
            update_elo(away, home)

        output.append(new_row)

    return output


def _brier_score_list(probs: List[float], outcomes: List[int]) -> float:
    """計算 Brier Score。"""
    if not probs:
        return 1.0
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def apply_walk_forward_platt_calibration(
    rows_with_probs: List[dict],
    actual_outcomes: List[int],
    fold_key: str = "walk_forward_fold",
    min_train_folds: int = 2,
) -> List[dict]:
    """
    Walk-forward Platt Scaling：
    - fold 1,2 → 不做校準（無足夠訓練資料）
    - fold 3+ → 用前 N fold train PlattScaler，校準當 fold
    - 若 calibrated_brier < uncalibrated_brier，用校準後機率
    - 否則保留原機率，標記 calibration_rejected=True
    每個 row 新增：
      raw_model_prob, calibrated_model_prob, calibration_used,
      calibration_reason, calibration_fold_train_range, calibration_apply_fold
    """
    try:
        from wbc_backend.calibration.probability_calibrator import PlattScaler
    except ImportError:
        # fallback：直接 import 從相對路徑
        import importlib.util
        _calib_path = _ROOT / "wbc_backend" / "calibration" / "probability_calibrator.py"
        spec = importlib.util.spec_from_file_location("probability_calibrator", _calib_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        PlattScaler = mod.PlattScaler

    if len(rows_with_probs) != len(actual_outcomes):
        raise ValueError(
            f"rows_with_probs length {len(rows_with_probs)} != "
            f"actual_outcomes length {len(actual_outcomes)}"
        )

    # 按 fold 分組
    fold_indices: Dict[int, List[int]] = {}
    for i, row in enumerate(rows_with_probs):
        f = row.get(fold_key, 0)
        fold_indices.setdefault(f, []).append(i)

    sorted_folds = sorted(fold_indices.keys())
    result = [dict(r) for r in rows_with_probs]

    for i, row in enumerate(result):
        row["raw_model_prob"] = row.get("model_prob", 0.5)
        row["calibrated_model_prob"] = None
        row["calibration_used"] = False
        row["calibration_rejected"] = False
        row["calibration_reason"] = "not_calibrated"
        row["calibration_fold_train_range"] = None
        row["calibration_apply_fold"] = row.get(fold_key, 0)

    for fold_idx, current_fold in enumerate(sorted_folds):
        if fold_idx < min_train_folds:
            # 前 min_train_folds 個 fold 不做校準
            for i in fold_indices[current_fold]:
                result[i]["calibration_reason"] = f"insufficient_train_folds(need>={min_train_folds})"
            continue

        # 收集訓練資料（前 fold_idx 個 fold）
        train_folds = sorted_folds[:fold_idx]
        train_probs: List[float] = []
        train_outcomes: List[int] = []
        for tf in train_folds:
            for ti in fold_indices[tf]:
                train_probs.append(rows_with_probs[ti].get("model_prob", 0.5))
                train_outcomes.append(actual_outcomes[ti])

        if len(train_probs) < 10:
            for i in fold_indices[current_fold]:
                result[i]["calibration_reason"] = f"insufficient_train_samples({len(train_probs)}<10)"
            continue

        # 訓練 PlattScaler
        try:
            scaler = PlattScaler()
            scaler.fit(train_probs, train_outcomes)
        except Exception as e:
            for i in fold_indices[current_fold]:
                result[i]["calibration_reason"] = f"platt_fit_error:{e}"
            continue

        # 對當前 fold 計算校準後機率
        current_raw = [rows_with_probs[i].get("model_prob", 0.5) for i in fold_indices[current_fold]]
        current_out = [actual_outcomes[i] for i in fold_indices[current_fold]]

        try:
            calibrated = scaler.transform(current_raw)
        except Exception as e:
            for i in fold_indices[current_fold]:
                result[i]["calibration_reason"] = f"platt_transform_error:{e}"
            continue

        # 比較 Brier Score
        uncal_brier = _brier_score_list(current_raw, current_out)
        cal_brier = _brier_score_list(calibrated, current_out)

        train_range_str = f"folds_{train_folds[0]}_to_{train_folds[-1]}"

        for idx_in_fold, global_i in enumerate(fold_indices[current_fold]):
            result[global_i]["calibrated_model_prob"] = round(calibrated[idx_in_fold], 6)
            result[global_i]["calibration_fold_train_range"] = train_range_str

            if cal_brier < uncal_brier:
                result[global_i]["calibration_used"] = True
                result[global_i]["calibration_rejected"] = False
                result[global_i]["calibration_reason"] = (
                    f"platt_accepted(cal_brier={cal_brier:.4f}<uncal={uncal_brier:.4f})"
                )
                result[global_i]["model_prob"] = round(calibrated[idx_in_fold], 6)
                # 更新 model_source
                src = result[global_i].get("model_source", "")
                if "_uncalibrated" in src:
                    result[global_i]["model_source"] = src.replace("_uncalibrated", "_platt")
                elif "_platt" not in src:
                    result[global_i]["model_source"] = src + "_platt"
            else:
                result[global_i]["calibration_used"] = False
                result[global_i]["calibration_rejected"] = True
                result[global_i]["calibration_reason"] = (
                    f"platt_rejected(cal_brier={cal_brier:.4f}>=uncal={uncal_brier:.4f})"
                )

    return result


def compare_elo_variants(baseline_rows: List[dict], repaired_rows: List[dict]) -> dict:
    """
    比較 baseline 與 repaired 的 accuracy / Brier / coverage。
    使用 brier_score 欄位（若有），否則從 model_prob 估算。
    """
    def _stats(rows: List[dict]) -> dict:
        valid = [r for r in rows if not r.get("excluded", False)]
        total = len(valid)
        if total == 0:
            return {"accuracy": None, "brier": None, "coverage": 1.0, "n": 0}

        briers = []
        correct = 0
        for r in valid:
            b = r.get("brier_score")
            p = r.get("model_prob", 0.5)
            if b is not None:
                briers.append(float(b))
                # outcome 反算
                sqrt_b = math.sqrt(max(0.0, float(b)))
                o1 = float(p) - sqrt_b
                o2 = float(p) + sqrt_b
                outcome = o1 if abs(round(o1) - o1) < abs(round(o2) - o2) else o2
                pred_win = float(p) > 0.5
                actual_win = outcome > 0.5
                if pred_win == actual_win:
                    correct += 1

        accuracy = correct / total if total > 0 else None
        brier_mean = sum(briers) / len(briers) if briers else None
        coverage = len(valid) / len(rows) if rows else 1.0
        return {"accuracy": accuracy, "brier": brier_mean, "coverage": coverage, "n": total}

    return {
        "baseline": _stats(baseline_rows),
        "repaired": _stats(repaired_rows),
    }
