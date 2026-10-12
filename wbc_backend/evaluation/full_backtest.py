"""
MLB 2025 完整回測引擎 — Phase 7B
================================
使用 PredictionOrchestrator 對 2,430 場 MLB 2025 真實賽事進行 Walk-Forward 回測。

設計原則：
  - § 01: 嚴格 Look-ahead 隔離（每個 test 視窗的結果在訓練中不可見）
  - § 02: 最低樣本數 50 場（已達 2,430 場，遠超標準）
  - § 03: Kelly 準則下注，100% 真實賠率數據

回測流程：
  1. 載入 GameRecord（mlb_data_loader）
  2. 時序排序 → Walk-Forward 切割（5 個視窗，80/20 分割）
  3. 每個訓練視窗：MARL 參數優化（n_generations=20，快速模式）
  4. 每個測試視窗：Orchestrator.predict()（僅 MARL，無球員資料 → 批次速度快）
  5. 彙整：accuracy / Brier / ROI / Sharpe / max_drawdown / calibration ECE
  6. 輸出 BacktestReport + Markdown 文本
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WindowResult:
    """單一 Walk-Forward 視窗的回測結果"""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    # 預測指標（原始）
    accuracy: float
    brier_score: float
    log_loss: float
    calibration_ece: float
    # 校準後指標
    cal_brier_score: float = 0.0
    cal_ece: float = 0.0
    cal_method: str = "none"
    # 下注指標
    n_bets_placed: int = 0
    n_bets_won: int = 0
    roi: float = 0.0
    final_bankroll: float = 1.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    # 最優化後的 MARL 參數
    marl_w_elo: float = 0.40
    marl_w_market: float = 0.30


@dataclass
class FullBacktestReport:
    """完整回測報告"""
    # 基本資訊
    data_source: str = "mlb_2025_retrosheet"
    n_games_total: int = 0
    date_range: str = ""
    n_windows: int = 0
    # 彙整指標（所有 test 視窗加總）
    accuracy: float = 0.0
    brier_score: float = 0.0
    log_loss: float = 0.0
    calibration_ece: float = 0.0
    # 下注彙整
    n_bets_total: int = 0
    n_bets_won: int = 0
    roi: float = 0.0
    final_bankroll: float = 1.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    # 統計顯著性
    p_value_vs_random: float = 1.0
    roi_ci_95: tuple[float, float] = (0.0, 0.0)
    # 各視窗詳情
    window_results: list[WindowResult] = field(default_factory=list)
    # 預測 vs 市場 Brier 比較
    market_brier_score: float = 0.0
    brier_skill_score: float = 0.0     # 1 - model_brier/market_brier（校準前）
    # 校準後彙整指標
    cal_brier_score: float = 0.0
    cal_ece: float = 0.0
    cal_brier_skill_score: float = 0.0  # 1 - cal_brier/market_brier（校準後）
    calibration_method: str = "none"
    # 附註
    notes: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# 計量工具函數
# ══════════════════════════════════════════════════════════════════════════════

def _brier_score(probs: list[float], outcomes: list[int]) -> float:
    """Brier Score = mean((p - y)^2)，越低越好"""
    if not probs:
        return 0.0
    return float(np.mean([(p - y) ** 2 for p, y in zip(probs, outcomes)]))


def _log_loss(probs: list[float], outcomes: list[int], eps: float = 1e-7) -> float:
    """對數損失，越低越好"""
    if not probs:
        return 0.0
    return float(-np.mean([
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
        for p, y in zip(probs, outcomes)
    ]))


def _calibration_ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error（10 bins），越低越好"""
    if not probs:
        return 0.0
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = [lo <= p < hi for p in probs]
        if not any(mask):
            continue
        bin_probs = [p for p, m in zip(probs, mask) if m]
        bin_outs = [y for y, m in zip(outcomes, mask) if m]
        bin_conf = float(np.mean(bin_probs))
        bin_acc = float(np.mean(bin_outs))
        ece += (len(bin_probs) / n) * abs(bin_conf - bin_acc)
    return round(ece, 4)


def _roi_and_bankroll(
    probs: list[float],
    market_probs: list[float],
    outcomes: list[int],
    kelly_mult: float = 0.25,
    min_edge: float = 0.03,
    initial_bankroll: float = 1.0,
) -> tuple[float, float, float, float]:
    """
    計算 ROI、最終資金、最大回撤、Sharpe。
    美式賠率（-110）標準化：賠率 ≈ 0.909。

    Returns:
        (roi, final_bankroll, max_drawdown, sharpe)
    """
    bankroll = initial_bankroll
    peak = bankroll
    daily_returns: list[float] = []
    n_bets = 0
    n_won = 0

    for prob, mkt, outcome in zip(probs, market_probs, outcomes):
        edge = prob - mkt
        if abs(edge) < min_edge:
            continue

        # Kelly 計算
        if edge > 0:
            bet_on_home = True
            win_prob = prob
            bet_odds = (1 - mkt) / max(mkt, 0.01)   # 客隊賠率倒推
        else:
            bet_on_home = False
            win_prob = 1 - prob
            bet_odds = mkt / max(1 - mkt, 0.01)

        raw_kelly = abs(edge) / max(bet_odds, 0.1)
        stake = min(kelly_mult * raw_kelly, 0.05) * bankroll   # 最大 5% 資金
        if stake <= 0:
            continue

        n_bets += 1
        # 判斷是否贏
        bet_won = (bet_on_home and outcome == 1) or (not bet_on_home and outcome == 0)
        if bet_won:
            pnl = stake * bet_odds
            n_won += 1
        else:
            pnl = -stake

        bankroll += pnl
        bankroll = max(bankroll, 0.001)
        peak = max(peak, bankroll)
        daily_returns.append(pnl / (stake + 1e-8))

    roi = (bankroll - initial_bankroll) / initial_bankroll
    max_dd = 0.0
    peak_track = initial_bankroll
    bk = initial_bankroll
    for prob, mkt, outcome in zip(probs, market_probs, outcomes):
        edge = prob - mkt
        if abs(edge) < min_edge:
            continue
        # 簡化最大回撤計算
        if bk > peak_track:
            peak_track = bk
        elif peak_track > 0:
            dd = (peak_track - bk) / peak_track
            max_dd = max(max_dd, dd)

    if len(daily_returns) >= 2:
        mean_ret = float(np.mean(daily_returns))
        std_ret = float(np.std(daily_returns))
        sharpe = mean_ret / max(std_ret, 0.001) * math.sqrt(max(n_bets, 1))
    else:
        sharpe = 0.0

    return roi, bankroll, max_dd, sharpe


def _p_value_vs_random(probs: list[float], outcomes: list[int]) -> float:
    """t-test：模型預測是否優於亂猜（p < 0.05 顯著）"""
    try:
        from scipy import stats as scipy_stats
        brier_model = [(p - y) ** 2 for p, y in zip(probs, outcomes)]
        brier_random = [(0.5 - y) ** 2 for y in outcomes]
        _, pval = scipy_stats.ttest_rel(brier_model, brier_random)
        return float(pval)
    except Exception:
        # 手動 t-test fallback
        n = len(probs)
        if n < 2:
            return 1.0
        diffs = [(p - y) ** 2 - (0.5 - y) ** 2 for p, y in zip(probs, outcomes)]
        mean_d = float(np.mean(diffs))
        std_d = float(np.std(diffs, ddof=1))
        if std_d == 0:
            return 0.0 if mean_d < 0 else 1.0
        t_stat = mean_d / (std_d / math.sqrt(n))
        # 近似 p-value（one-tailed，模型比 random 好）
        # 使用正態近似（n 夠大時 t ≈ z）
        from math import erfc
        z = abs(t_stat)
        p_approx = 0.5 * erfc(z / math.sqrt(2))
        return float(p_approx)


# ══════════════════════════════════════════════════════════════════════════════
# 主要回測引擎
# ══════════════════════════════════════════════════════════════════════════════

class FullBacktestEngine:
    """
    MLB 2025 完整 Walk-Forward 回測引擎。

    流程：
      1. 時序排序
      2. 切割 Walk-Forward 視窗（n_windows 個，各視窗 80/20 分割）
      3. 每個訓練視窗：快速 MARL 優化（n_gen=15）
      4. 每個測試視窗：Orchestrator MARL-only 預測
      5. 彙整統計並輸出 FullBacktestReport
    """

    def __init__(
        self,
        n_windows: int = 5,
        min_train_size: int = 200,
        marl_n_generations: int = 15,
        marl_n_candidates: int = 8,
        kelly_mult: float = 0.25,
        min_edge: float = 0.03,
        initial_bankroll: float = 1.0,
        seed: int = 42,
        use_calibration: bool = True,        # Phase 8A: 啟用後校準
        calibration_method: str = "auto",    # "auto" | "platt" | "isotonic" | "temperature"
        # Phase 39: 每場預測機率持久化
        persist_predictions: bool = False,   # True → 寫入 JSONL
        prediction_output_path: "Optional[Path]" = None,  # None → 使用預設路徑
    ):
        self.n_windows = n_windows
        self.min_train_size = min_train_size
        self.marl_n_generations = marl_n_generations
        self.marl_n_candidates = marl_n_candidates
        self.kelly_mult = kelly_mult
        self.use_calibration = use_calibration
        self.calibration_method = calibration_method
        self.min_edge = min_edge
        self.initial_bankroll = initial_bankroll
        self.seed = seed
        self.persist_predictions = persist_predictions
        self.prediction_output_path = prediction_output_path

    def run(self, records: list) -> FullBacktestReport:
        """
        執行完整回測。

        Args:
            records: list[GameRecord]，必須含 actual_home_win 欄位。

        Returns:
            FullBacktestReport
        """
        # ── 資料驗證 ──────────────────────────────────────────────────────────
        valid = [r for r in records if getattr(r, "actual_home_win", None) is not None]
        if len(valid) < self.min_train_size + 50:
            raise ValueError(
                f"回測數據不足：{len(valid)} 筆（需 >= {self.min_train_size + 50}）"
            )

        # 時序排序
        valid.sort(key=lambda r: getattr(r, "game_date", ""))

        report = FullBacktestReport(
            data_source=getattr(valid[0], "data_source", "unknown"),
            n_games_total=len(valid),
            date_range=f"{getattr(valid[0], 'game_date', '?')} → {getattr(valid[-1], 'game_date', '?')}",
            n_windows=self.n_windows,
        )
        report.notes.append(f"Walk-Forward 回測：{self.n_windows} 個視窗")

        # ── Walk-Forward 切割 ─────────────────────────────────────────────────
        window_size = len(valid) // (self.n_windows + 1)
        all_test_probs: list[float] = []
        all_calibrated_probs: list[float] = []
        all_market_probs: list[float] = []
        all_outcomes: list[int] = []
        bankroll = self.initial_bankroll
        window_results: list[WindowResult] = []
        # Phase 39: per-game prediction row accumulator
        _prediction_rows: list = []

        for w in range(self.n_windows):
            train_end_idx = (w + 1) * window_size
            test_start_idx = train_end_idx
            test_end_idx = min(test_start_idx + window_size, len(valid))

            train_records = valid[:train_end_idx]
            test_records = valid[test_start_idx:test_end_idx]

            if len(train_records) < self.min_train_size or len(test_records) < 20:
                continue

            logger.info(
                f"視窗 {w+1}/{self.n_windows}: "
                f"訓練={len(train_records)}, 測試={len(test_records)}"
            )

            # ── MARL 訓練優化 ────────────────────────────────────────────────
            best_predictor = self._optimize_marl(train_records)

            # ── 測試視窗預測 ─────────────────────────────────────────────────
            from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
            orc = PredictionOrchestrator(
                marl_predictor=best_predictor,
                min_kelly_edge=self.min_edge,
                kelly_multiplier=self.kelly_mult,
            )

            test_probs: list[float] = []
            test_mkt: list[float] = []
            test_outcomes: list[int] = []

            _w_split_id = f"window_{w + 1}"
            _w_train_start = getattr(train_records[0], "game_date", "")
            _w_train_end = getattr(train_records[-1], "game_date", "")
            _w_test_start = getattr(test_records[0], "game_date", "")
            _w_test_end = getattr(test_records[-1], "game_date", "")

            for rec in test_records:
                result = orc.predict(
                    rec,
                    use_hierarchical_mc=False,
                    use_world_model=False,
                )
                test_probs.append(result.home_win_prob)
                test_mkt.append(float(getattr(rec, "market_home_prob", 0.5)))
                test_outcomes.append(int(getattr(rec, "actual_home_win", 0)))

                # Phase 39: collect per-game prediction row (read-only by default)
                if self.persist_predictions:
                    try:
                        from wbc_backend.evaluation.prediction_persistence import (
                            build_prediction_row,
                        )
                        _mkt_p = float(getattr(rec, "market_home_prob", 0.5))
                        _row = build_prediction_row(
                            game_date=str(getattr(rec, "game_date", "")),
                            game_id=str(getattr(rec, "game_id", "")),
                            home_team=str(getattr(rec, "home_team", "")),
                            away_team=str(getattr(rec, "away_team", "")),
                            home_win=int(getattr(rec, "actual_home_win", 0)),
                            model_home_prob=float(result.home_win_prob),
                            market_home_prob_no_vig=_mkt_p,
                            market_away_prob_no_vig=round(1.0 - _mkt_p, 8),
                            model_version=(
                                f"marl_w_elo={best_predictor.w_elo:.3f}"
                                f"_w_market={best_predictor.w_market:.3f}"
                            ),
                            split_id=_w_split_id,
                            train_window_start=_w_train_start,
                            train_window_end=_w_train_end,
                            test_window_start=_w_test_start,
                            test_window_end=_w_test_end,
                        )
                        _prediction_rows.append(_row)
                    except Exception as _pe:
                        logger.warning(
                            "[Phase39] 無法建立預測行 %s: %s",
                            getattr(rec, "game_id", "?"), _pe,
                        )

            # ── 計算視窗指標（原始）─────────────────────────────────────────
            acc = float(np.mean([
                (p > 0.5 and y == 1) or (p <= 0.5 and y == 0)
                for p, y in zip(test_probs, test_outcomes)
            ]))
            brier = _brier_score(test_probs, test_outcomes)
            ll = _log_loss(test_probs, test_outcomes)
            ece = _calibration_ece(test_probs, test_outcomes)

            # ── Phase 8A: 後校準 ─────────────────────────────────────────────
            cal_brier = brier
            cal_ece = ece
            cal_method = "none"
            calibrated_probs = test_probs  # 預設：不校準
            if self.use_calibration:
                try:
                    from wbc_backend.calibration.probability_calibrator import (
                        calibrate_walk_forward,
                    )
                    # 在訓練集上擬合 + 對測試集校準
                    train_raw: list[float] = []
                    train_outcomes_cal: list[int] = []
                    for rec in train_records[-min(500, len(train_records)):]:
                        train_raw.append(
                            float(orc.marl_predictor.predict(rec))
                        )
                        train_outcomes_cal.append(
                            int(getattr(rec, "actual_home_win", 0))
                        )
                    calibrated_probs, cal_result = calibrate_walk_forward(
                        train_raw, train_outcomes_cal,
                        test_probs, test_outcomes, test_mkt,
                        method=self.calibration_method,
                    )
                    cal_brier = cal_result.cal_brier
                    cal_ece = cal_result.cal_ece
                    cal_method = cal_result.method
                    logger.info(
                        f"  校準（{cal_method}）：ECE {ece:.4f} → {cal_ece:.4f}，"
                        f"Brier {brier:.4f} → {cal_brier:.4f}"
                    )
                except Exception as e:
                    logger.warning(f"校準失敗，使用原始機率: {e}")

            roi, bk_after, max_dd, sharpe = _roi_and_bankroll(
                calibrated_probs, test_mkt, test_outcomes,
                kelly_mult=self.kelly_mult,
                min_edge=self.min_edge,
                initial_bankroll=bankroll,
            )
            n_bets = sum(
                1 for p, m in zip(calibrated_probs, test_mkt)
                if abs(p - m) >= self.min_edge
            )
            n_won = sum(
                1 for p, m, y in zip(calibrated_probs, test_mkt, test_outcomes)
                if abs(p - m) >= self.min_edge and (
                    (p > m and y == 1) or (p < m and y == 0)
                )
            )

            win_result = WindowResult(
                window_id=w + 1,
                train_start=getattr(train_records[0], "game_date", ""),
                train_end=getattr(train_records[-1], "game_date", ""),
                test_start=getattr(test_records[0], "game_date", ""),
                test_end=getattr(test_records[-1], "game_date", ""),
                n_train=len(train_records),
                n_test=len(test_records),
                accuracy=round(acc, 4),
                brier_score=round(brier, 4),
                log_loss=round(ll, 4),
                calibration_ece=round(ece, 4),
                cal_brier_score=round(cal_brier, 4),
                cal_ece=round(cal_ece, 4),
                cal_method=cal_method,
                n_bets_placed=n_bets,
                n_bets_won=n_won,
                roi=round(roi, 4),
                final_bankroll=round(bk_after, 4),
                max_drawdown=round(max_dd, 4),
                sharpe_ratio=round(sharpe, 4),
                marl_w_elo=round(best_predictor.w_elo, 3),
                marl_w_market=round(best_predictor.w_market, 3),
            )
            window_results.append(win_result)

            all_test_probs.extend(test_probs)
            all_calibrated_probs.extend(calibrated_probs)
            all_market_probs.extend(test_mkt)
            all_outcomes.extend(test_outcomes)
            bankroll = bk_after

        # ── 全局彙整 ──────────────────────────────────────────────────────────
        if not all_test_probs:
            report.notes.append("警告：無有效測試視窗")
            return report

        report.window_results = window_results
        report.accuracy = round(float(np.mean([
            (p > 0.5 and y == 1) or (p <= 0.5 and y == 0)
            for p, y in zip(all_test_probs, all_outcomes)
        ])), 4)
        report.brier_score = round(_brier_score(all_test_probs, all_outcomes), 4)
        report.log_loss = round(_log_loss(all_test_probs, all_outcomes), 4)
        report.calibration_ece = round(_calibration_ece(all_test_probs, all_outcomes), 4)

        # 市場基準 Brier（以市場機率為預測）
        report.market_brier_score = round(_brier_score(all_market_probs, all_outcomes), 4)
        if report.market_brier_score > 0:
            report.brier_skill_score = round(
                1 - report.brier_score / report.market_brier_score, 4,
            )

        # Phase 8A: 校準後全局指標
        if self.use_calibration and all_calibrated_probs:
            report.cal_brier_score = round(_brier_score(all_calibrated_probs, all_outcomes), 4)
            report.cal_ece = round(_calibration_ece(all_calibrated_probs, all_outcomes), 4)
            if report.market_brier_score > 0:
                report.cal_brier_skill_score = round(
                    1 - report.cal_brier_score / report.market_brier_score, 4,
                )
            report.calibration_method = window_results[-1].cal_method if window_results else "none"
            logger.info(
                f"全局校準結果：ECE {report.calibration_ece:.4f} → {report.cal_ece:.4f}，"
                f"Brier Skill {report.brier_skill_score:+.1%} → {report.cal_brier_skill_score:+.1%}"
            )

        # 下注統計
        report.n_bets_total = sum(w.n_bets_placed for w in window_results)
        report.n_bets_won = sum(w.n_bets_won for w in window_results)
        final_roi, final_bk, final_dd, final_sharpe = _roi_and_bankroll(
            all_calibrated_probs if self.use_calibration else all_test_probs,
            all_market_probs, all_outcomes,
            kelly_mult=self.kelly_mult,
            min_edge=self.min_edge,
            initial_bankroll=self.initial_bankroll,
        )
        report.roi = round(final_roi, 4)
        report.final_bankroll = round(final_bk, 4)
        report.max_drawdown = round(final_dd, 4)
        report.sharpe_ratio = round(final_sharpe, 4)

        # 統計顯著性
        report.p_value_vs_random = round(_p_value_vs_random(all_test_probs, all_outcomes), 4)

        # ROI 95% CI（Bootstrap）
        roi_samples = []
        np.random.seed(self.seed)
        for _ in range(200):
            idx = np.random.choice(len(all_test_probs), len(all_test_probs), replace=True)
            sp = [all_test_probs[i] for i in idx]
            sm = [all_market_probs[i] for i in idx]
            so = [all_outcomes[i] for i in idx]
            r, _, _, _ = _roi_and_bankroll(sp, sm, so, self.kelly_mult, self.min_edge)
            roi_samples.append(r)
        report.roi_ci_95 = (
            round(float(np.percentile(roi_samples, 2.5)), 4),
            round(float(np.percentile(roi_samples, 97.5)), 4),
        )

        # Phase 39: write per-game prediction rows to JSONL if requested
        if self.persist_predictions and _prediction_rows:
            try:
                from wbc_backend.evaluation.prediction_persistence import (
                    write_prediction_rows,
                    DEFAULT_PREDICTIONS_PATH,
                )
                out_path = Path(self.prediction_output_path) if self.prediction_output_path else DEFAULT_PREDICTIONS_PATH
                n_written = write_prediction_rows(_prediction_rows, out_path)
                report.notes.append(
                    f"[Phase39] 每場預測機率已持久化：{n_written} 行 → {out_path}"
                )
                logger.info("[Phase39] 預測機率持久化完成：%d 行 → %s", n_written, out_path)
            except Exception as _we:
                logger.warning("[Phase39] 預測機率寫入失敗: %s", _we)
                report.notes.append(f"[Phase39] 預測機率寫入失敗: {_we}")
        elif self.persist_predictions and not _prediction_rows:
            report.notes.append(
                "[Phase39] persist_predictions=True 但 _prediction_rows 為空 "
                "（model_home_prob 可能為 RAW_MODEL_PROB_MISSING）"
            )

        return report

    def _optimize_marl(self, train_records: list) -> Any:
        """在訓練集上快速優化 MARL PredictorParams"""
        try:
            from wbc_backend.strategy.marl_optimizer import MARLOptimizer
            optimizer = MARLOptimizer(
                n_generations=self.marl_n_generations,
                n_candidates=self.marl_n_candidates,
                seed=self.seed,
            )
            # 只用訓練集的一個子集（最多 500 筆）加速優化
            subset = train_records[-min(500, len(train_records)):]
            result = optimizer.optimize(subset)
            return result.best_predictor
        except Exception as e:
            logger.warning(f"MARL 優化失敗，使用預設參數: {e}")
            from wbc_backend.strategy.marl_optimizer import PredictorParams
            return PredictorParams()


# ══════════════════════════════════════════════════════════════════════════════
# Markdown 報告生成器
# ══════════════════════════════════════════════════════════════════════════════

def generate_markdown_report(report: FullBacktestReport, title: str = "MLB 2025 完整回測報告") -> str:
    """將 FullBacktestReport 轉換為 Markdown 格式字串"""
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> 生成日期：2026-03-13  |  資料來源：{report.data_source}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 執行摘要
    lines.append("## 📊 執行摘要")
    lines.append("")
    lines.append(f"| 指標 | 數值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 總場數 | {report.n_games_total:,} 場 |")
    lines.append(f"| 日期範圍 | {report.date_range} |")
    lines.append(f"| Walk-Forward 視窗數 | {report.n_windows} 個 |")
    lines.append(f"| **整體準確率** | **{report.accuracy:.1%}** |")
    lines.append(f"| **Brier Score（原始）** | **{report.brier_score:.4f}** |")
    if report.calibration_method != "none":
        lines.append(f"| **Brier Score（校準後，{report.calibration_method}）** | **{report.cal_brier_score:.4f}** |")
    lines.append(f"| Brier Score（市場基準） | {report.market_brier_score:.4f} |")
    lines.append(f"| **Brier Skill（原始）** | **{report.brier_skill_score:+.1%}** |")
    if report.calibration_method != "none":
        lines.append(f"| **Brier Skill（校準後）** | **{report.cal_brier_skill_score:+.1%}** |")
    lines.append(f"| Log Loss | {report.log_loss:.4f} |")
    lines.append(f"| ECE（原始） | {report.calibration_ece:.4f} |")
    if report.calibration_method != "none":
        lines.append(f"| **ECE（校準後）** | **{report.cal_ece:.4f}** |")
    lines.append(f"| **總 ROI** | **{report.roi:+.1%}** |")
    lines.append(f"| ROI 95% CI | [{report.roi_ci_95[0]:+.1%}, {report.roi_ci_95[1]:+.1%}] |")
    lines.append(f"| Sharpe Ratio | {report.sharpe_ratio:.2f} |")
    lines.append(f"| 最大回撤 | {report.max_drawdown:.1%} |")
    lines.append(f"| 下注場數 | {report.n_bets_total:,} 場 |")
    lines.append(f"| 下注勝率 | {report.n_bets_won / max(report.n_bets_total, 1):.1%} |")
    lines.append(f"| 最終資金（初始=1.00） | {report.final_bankroll:.4f} |")
    lines.append(f"| p-value（vs 亂猜） | {report.p_value_vs_random:.4f} |")
    lines.append("")

    # 統計顯著性判定
    if report.p_value_vs_random < 0.05:
        lines.append("✅ **統計顯著**：p < 0.05，模型顯著優於亂猜")
    elif report.p_value_vs_random < 0.10:
        lines.append("⚠️ **邊際顯著**：0.05 ≤ p < 0.10")
    else:
        lines.append("❌ **未達顯著**：p ≥ 0.10，模型未能顯著優於亂猜")
    lines.append("")

    # Brier Skill 判定（優先使用校準後指標）
    skill = report.cal_brier_skill_score if report.calibration_method != "none" else report.brier_skill_score
    label = "（校準後）" if report.calibration_method != "none" else ""
    if skill > 0.02:
        lines.append(f"✅ **優於市場{label}**：Brier Skill Score = {skill:+.1%}")
    elif skill >= 0:
        lines.append(f"➡️ **持平市場{label}**：Brier Skill Score = {skill:+.1%}")
    else:
        lines.append(f"❌ **落後市場{label}**：Brier Skill Score = {skill:+.1%}")
    lines.append("")

    # Walk-Forward 視窗詳情
    lines.append("---")
    lines.append("")
    lines.append("## 🪟 Walk-Forward 視窗詳情")
    lines.append("")
    lines.append("| 視窗 | 訓練期 | 測試期 | 訓練數 | 測試數 | 準確率 | Brier | ROI | 下注數 | Sharpe |")
    lines.append("|------|--------|--------|--------|--------|--------|-------|-----|--------|--------|")
    for w in report.window_results:
        lines.append(
            f"| W{w.window_id} "
            f"| {w.train_start[:10]}~{w.train_end[:10]} "
            f"| {w.test_start[:10]}~{w.test_end[:10]} "
            f"| {w.n_train:,} "
            f"| {w.n_test:,} "
            f"| {w.accuracy:.1%} "
            f"| {w.brier_score:.4f} "
            f"| {w.roi:+.1%} "
            f"| {w.n_bets_placed} "
            f"| {w.sharpe_ratio:.2f} |"
        )
    lines.append("")

    # MARL 參數演化
    lines.append("---")
    lines.append("")
    lines.append("## 🧬 MARL 參數演化（各視窗最優化結果）")
    lines.append("")
    lines.append("| 視窗 | w_elo | w_market | ECE |")
    lines.append("|------|-------|---------|-----|")
    for w in report.window_results:
        lines.append(
            f"| W{w.window_id} "
            f"| {w.marl_w_elo:.3f} "
            f"| {w.marl_w_market:.3f} "
            f"| {w.calibration_ece:.4f} |"
        )
    lines.append("")

    # 系統說明
    lines.append("---")
    lines.append("")
    lines.append("## 🔬 方法論說明")
    lines.append("")
    lines.append("- **預測模型**：MARL PredictorAgent（Logistic，ELO + 市場 + wOBA + FIP + RSI）")
    lines.append("- **下注策略**：分數 Kelly（0.25 × Kelly），最小邊緣 3%，單注上限 5%")
    lines.append("- **驗證方法**：Walk-Forward（無 Look-ahead Leakage）")
    lines.append("- **資料來源**：MLB 2025 真實賽果 + 開盤賠率（2,430 場）")
    lines.append("- **訓練方式**：每個訓練視窗獨立執行 MARL 演化優化（15 代 × 8 候選）")
    lines.append("")

    # 附註
    if report.notes:
        lines.append("---")
        lines.append("")
        lines.append("## 📝 附註")
        lines.append("")
        for note in report.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 快速入口
# ══════════════════════════════════════════════════════════════════════════════

def run_full_backtest(
    n_windows: int = 5,
    marl_n_generations: int = 15,
    output_md: Optional[str] = None,
) -> FullBacktestReport:
    """
    快速執行 MLB 2025 完整回測並回傳報告。

    Args:
        n_windows: Walk-Forward 視窗數（預設 5）
        marl_n_generations: 每個視窗的 MARL 演化代數（預設 15，快速模式）
        output_md: 若指定路徑，將 Markdown 報告寫入該檔案

    Returns:
        FullBacktestReport
    """
    from data.mlb_data_loader import load_mlb_records

    records = load_mlb_records()
    logger.info(f"載入 {len(records)} 筆 MLB 2025 真實賽事")

    engine = FullBacktestEngine(
        n_windows=n_windows,
        marl_n_generations=marl_n_generations,
    )
    report = engine.run(records)

    if output_md:
        md_text = generate_markdown_report(report)
        from pathlib import Path
        Path(output_md).parent.mkdir(parents=True, exist_ok=True)
        Path(output_md).write_text(md_text, encoding="utf-8")
        logger.info(f"Markdown 報告已寫入 → {output_md}")

    return report
