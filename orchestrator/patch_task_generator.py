"""
MLB Prediction Patch Task Generator
====================================
將結構化洞見（insight records）轉換為「模型修補任務」和「驗收回測任務」。

每個 patch task 都必須：
- 以 [PAPER MODE ONLY] 標記
- 只操作 wbc_backend/research/ 或 wbc_backend/evaluation/ 或 data/（非 live 檔）
- 包含 5 個明確 Phase（通過 task_quality_gate）
- 包含 3 組策略、150/500/1500 回測、Monte Carlo 1000+、measurable acceptance criteria

Hard rules（禁止修改的目標）：
- strategy/
- telegram_bot/
- live/
- data/tsl_crawler.py
- data/live_updater.py
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── 安全守護：永不允許作為 target 的路徑前綴 ─────────────────────────────────
_BLOCKED_TARGET_PREFIXES = (
    "strategy/",
    "telegram_bot/",
    "live/",
    "data/tsl_crawler",
    "data/live_updater",
)


def _is_safe_targets(target_files: list[str]) -> bool:
    """確認 target_files 不含任何 live 投注路徑。"""
    for f in target_files:
        for blocked in _BLOCKED_TARGET_PREFIXES:
            if f.startswith(blocked) or blocked in f:
                logger.warning("[PatchGen] Blocked live target: %s", f)
                return False
    return True


# ── Patch blueprint builders ─────────────────────────────────────────────────

def _calibration_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-calibration-platt-isotonic",
        "market_scope": "MLB moneyline pregame paper research",
        "analysis_family": "model-patch-calibration",
        "title": "MLB Calibration Patch: Regime-Stratified Platt vs Isotonic Recalibration",
        "focus_keys": "mlb_calibration,platt,isotonic,regime,brier,patch,paper_only",
        "signal_state_type": "model_patch_calibration",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的校準缺陷：{ins['weakness']}。\n"
            "在 wbc_backend/research/ 實作 regime-stratified Platt/Isotonic 校準器，"
            "驗收標準：小 regime Brier score 改善 >= 2%，不修改任何 live 投注邏輯。"
        ),
        "phase_1": (
            "建立至少 3 組校準修補策略：(1) regime-agnostic Platt scaling baseline、"
            "(2) regime-stratified Isotonic regression（依 mlb_regime_paper_report.json 的 regime 標籤分群）、"
            "(3) regime-adaptive switching（按預測信心分數動態選擇校準器）。\n"
            "從 data/wbc_backend/reports/mlb_decision_quality_report.json 提取各 regime 的現有"
            "Brier score / LogLoss / ECE 作為 patch 前 baseline。"
            "確認所有修補只在 wbc_backend/research/ 目錄下操作，禁止觸及 strategy/ / telegram_bot/。"
        ),
        "phase_2": (
            "對每組修補策略執行 150 / 500 / 1500 樣本回測，按 regime 輸出"
            "Brier score、LogLoss、ECE（Expected Calibration Error）、edge、sharpe、drawdown，"
            "與 patch 前 baseline 精確比較。至少 1 組策略達成小 regime Brier 改善 >= 2%。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，確認修補後校準器在壓力情境下穩定，"
            "分析 bankroll path 的 tail loss 與 worst decile drawdown，"
            "確認 patch 後策略的 Sharpe / Drawdown 不低於 baseline。"
        ),
        "phase_4": (
            "對每個修補方案驗證無 look-ahead leakage：校準器只使用 pregame 資料，"
            "不含開賽後統計；時間戳對齊確認；walk-forward 切割正確。"
            "記錄每個方案的 leakage 審查通過 / 失敗結果。"
        ),
        "phase_5": (
            "輸出修補結果報告（mlb_calibration_patch_result.md）：(1) baseline vs patch Brier/ECE 比較表、"
            "(2) 最終推薦校準方案與不推薦方案（含淘汰原因）、(3) paper mode 安全確認清單、"
            f"(4) 驗收標準確認（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


def _feature_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-feature-leakage-removal",
        "market_scope": "MLB moneyline / totals pregame paper research",
        "analysis_family": "model-patch-feature",
        "title": "MLB Feature Patch: Remove Leakage Features and Add Bullpen Fatigue Proxy",
        "focus_keys": "mlb_features,leakage_removal,bullpen_fatigue,starter_quality,patch,paper_only",
        "signal_state_type": "model_patch_feature",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的特徵問題：{ins['weakness']}。\n"
            "在 wbc_backend/research/ 中移除 leakage 風險特徵，新增 bullpen fatigue proxy 與 lineup strength proxy，"
            f"驗收標準：{ins['expected_metric']}。"
        ),
        "phase_1": (
            "從 wbc_backend/research/mlb_regime_feature_redesign.py 提取完整特徵清單，"
            "建立至少 3 組特徵修補策略：\n"
            "(1) 移除 top-3 leakage 特徵（使用開賽後統計的欄位）作為 baseline；\n"
            "(2) 移除 leakage 特徵 + 新增 bullpen fatigue proxy"
            "（days_since_last_game、pitches_last_3_days、inherited_runners_rate）；\n"
            "(3) 移除 leakage + 新增 bullpen fatigue + lineup strength proxy（batting_order_woba_sum）。\n"
            "確認所有修補只在 wbc_backend/research/ 目錄下操作。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，輸出 SHAP 值（確認 leakage 特徵已消失）、"
            "edge、sharpe、drawdown、Brier score，與 baseline 比較。"
            "確認移除 leakage 特徵後 Brier delta < -1%（不過度惡化）。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，測試新特徵集在不同資料缺口情境下"
            "（bullpen 資料缺失 20% / 40%）的策略穩定性。"
        ),
        "phase_4": (
            "逐一驗證每個新增特徵（bullpen fatigue、lineup strength proxy）無 look-ahead leakage，"
            "確認時間戳使用開賽前最新值，記錄 leakage 審查結果。"
        ),
        "phase_5": (
            "輸出特徵修補結果報告（mlb_feature_patch_result.md）：(1) 移除特徵清單與 leakage 確認、"
            "(2) 新增特徵 SHAP 貢獻排名、(3) Brier delta 比較表、"
            f"(4) 推薦特徵集與驗收標準確認（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


def _regime_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-regime-boundary-refinement",
        "market_scope": "MLB moneyline pregame by regime paper research",
        "analysis_family": "model-patch-regime",
        "title": "MLB Regime Patch: Refine small_edge / weak_starter Boundary and Add Volatility Regime",
        "focus_keys": "mlb_regime,small_edge,weak_starter,boundary,volatility,patch,paper_only",
        "signal_state_type": "model_patch_regime",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的 regime 分類問題：{ins['weakness']}。\n"
            "在 wbc_backend/research/ 中精調 small_edge / weak_starter_mismatch 邊界，"
            f"驗收標準：{ins['expected_metric']}。"
        ),
        "phase_1": (
            "從 data/wbc_backend/reports/mlb_regime_paper_report.json 提取各 regime 的樣本分布，"
            "建立至少 3 組邊界調整策略：\n"
            "(1) 現有邊界 ±5% 敏感性測試；\n"
            "(2) small_edge 分裂為 small_edge_high_confidence / small_edge_low_confidence；\n"
            "(3) 新增 volatility regime（implied_std > 閾值 且 bullpen_fatigue 高）。\n"
            "確認所有修補只在 wbc_backend/research/ 目錄下操作。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，輸出 regime Precision / Recall、"
            "edge、sharpe、drawdown，與現有邊界比較。"
            "確認調整後 regime precision >= 75%，誤分類率 < 20%。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，測試邊界調整在不同市場情境下的穩定性，"
            "分析 bankroll path 的 tail risk 與 worst decile drawdown。"
        ),
        "phase_4": (
            "確認新 regime 邊界定義只使用 pregame 特徵，不含開賽後統計，"
            "記錄每個邊界定義的 leakage 審查通過 / 失敗結果。"
        ),
        "phase_5": (
            "輸出 regime 修補結果報告（mlb_regime_patch_result.md）：(1) baseline vs patch regime Precision/Recall 表、"
            "(2) 新邊界定義與驗收標準確認、(3) 不推薦方案及淘汰原因、"
            f"(4) 驗收確認（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


def _clv_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-clv-closing-proxy",
        "market_scope": "MLB pregame odds timeline paper research",
        "analysis_family": "model-patch-clv",
        "title": "MLB CLV Patch: Closing Odds Proxy for Missing External Data and Staleness Filter",
        "focus_keys": "mlb_clv,closing_proxy,staleness_filter,odds_timeline,patch,paper_only",
        "signal_state_type": "model_patch_clv",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的 CLV 品質問題：{ins['weakness']}。\n"
            "實作替代收盤賠率 proxy 與 staleness filter（只操作 data/ 中非 live 檔案），"
            f"驗收標準：{ins['expected_metric']}。"
        ),
        "phase_1": (
            "從 data/mlb_context/odds_timeline.jsonl 計算現有外部收盤覆蓋率，"
            "建立至少 3 組 proxy 策略：\n"
            "(1) 線性外推（最後 2 個 pregame 賠率點 → 收盤估算）；\n"
            "(2) weighted market consensus（多 sportsbook 加權平均）；\n"
            "(3) staleness filter（timestamp stale > 30 min 標記並排除 CLV 計算）。\n"
            "確認所有操作只在 data/mlb_context/ 與 data/wbc_backend/ 目錄（非 live 檔案）下進行。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，輸出外部收盤覆蓋率、"
            "median CLV 計算誤差、edge、sharpe、drawdown，"
            "確認覆蓋率 >= 85%，median CLV 誤差 < 0.02。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，估算不同 proxy 誤差率下"
            "CLV 計算對 bankroll path 的影響，確認 proxy 方案在壓力情境下的穩定性。"
        ),
        "phase_4": (
            "驗證 proxy 計算只使用開賽前資料，不含開賽後統計，"
            "記錄每個 proxy 方案的 leakage 審查與 staleness 閾值設定。"
        ),
        "phase_5": (
            "輸出 CLV 修補結果報告（mlb_clv_patch_result.md）：(1) 覆蓋率改善表格（按 League / Month）、"
            "(2) median CLV 誤差比較、(3) 推薦 proxy 方案與不推薦方案、"
            f"(4) 驗收標準確認（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


def _feedback_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-feedback-settlement-tracker",
        "market_scope": "MLB paper-only settlement paper research",
        "analysis_family": "model-patch-feedback",
        "title": "MLB Feedback Patch: Settlement Completeness Tracker and ROI Attribution by Regime",
        "focus_keys": "mlb_settlement,roi_by_regime,bad_bet_filter,feedback_loop,patch,paper_only",
        "signal_state_type": "model_patch_feedback",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的回饋迴圈問題：{ins['weakness']}。\n"
            "實作結算完整性追蹤器與按 regime 的 ROI 分析（只操作 wbc_backend/evaluation/ / research/），"
            f"驗收標準：{ins['expected_metric']}。"
        ),
        "phase_1": (
            "從 research/trade_ledger.jsonl 計算現有結算完整性基線，"
            "建立至少 3 組修補策略：\n"
            "(1) settlement completeness tracker（標記未結算 > 7 天的記錄為 STALE）；\n"
            "(2) ROI attribution by regime（從 research/roi_tracking.json 按 regime 拆分計算）；\n"
            "(3) GOOD_BET / BAD_BET 標籤驗證（確認標籤在賽前固定，不因開賽後統計更新）。\n"
            "確認所有修補只在 wbc_backend/evaluation/ 與 research/ 目錄下操作。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，輸出結算率、labeling accuracy、"
            "ROI by regime、edge、sharpe、drawdown，"
            "確認結算率 >= 95%，GOOD_BET 標籤準確率 >= 90%。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，估算結算缺口（20% / 40% 缺失率情境）"
            "對 ROI 計算精確度的影響，分析 bankroll curve 在不同結算完整率下的 drawdown 分布。"
        ),
        "phase_4": (
            "確認所有回饋迴圈修補只使用 paper mode 資料，"
            "不影響任何 live 投注結算邏輯，記錄 leakage 審查通過 / 失敗結果。"
        ),
        "phase_5": (
            "輸出回饋迴圈修補結果報告（mlb_feedback_patch_result.md）：(1) 結算完整性改善表、"
            "(2) ROI by regime 分析、(3) GOOD_BET 標籤準確率驗收確認、"
            f"(4) 推薦修補方案（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


def _backtest_validity_patch(ins: dict) -> dict:
    return {
        "focus_area": "mlb-patch-backtest-split-leakage-fix",
        "market_scope": "MLB paper-only backtest paper research",
        "analysis_family": "model-patch-backtest",
        "title": "MLB Backtest Patch: Fix Walk-Forward Split Leakage and Add Pregame Timestamp Guard",
        "focus_keys": "mlb_backtest,split_leakage,timestamp_guard,walkforward,patch,paper_only",
        "signal_state_type": "model_patch_backtest",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 修正已識別的回測有效性問題：{ins['weakness']}。\n"
            "在 wbc_backend/research/ 中修正 walk-forward 分割並加入 pregame timestamp guard，"
            f"驗收標準：{ins['expected_metric']}。"
        ),
        "phase_1": (
            "從 wbc_backend/evaluation/mlb_decision_quality.py 審查現有 walk-forward 分割邏輯，"
            "建立至少 3 組修補策略：\n"
            "(1) timestamp hard cutoff guard（開賽前 30 分鐘截止，排除之後的賠率資料）；\n"
            "(2) walk-forward split boundary reinforcement（確認特徵滑動窗口不跨越 split 邊界）；\n"
            "(3) post-game odds exclusion filter（掃描 data/mlb_context/odds_timeline.jsonl，"
            "排除 timestamp > 開賽時間的賠率作為 pregame 特徵）。\n"
            "確認所有修補只在 wbc_backend/research/ / wbc_backend/evaluation/ 目錄下操作。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，輸出 split 違規數、"
            "post-game odds 污染率、edge（clean vs contaminated）、sharpe、drawdown，"
            "確認 split leakage < 2%，污染率 = 0%。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，估算 leakage 修正前後 edge 虛增幅度，"
            "確認 clean edge 與 contaminated edge 的差異 < 5%。"
        ),
        "phase_4": (
            "逐一確認每個修補點的 timestamp 對齊，記錄修補前後的 split 違規數與污染源清單。"
        ),
        "phase_5": (
            "輸出回測修補結果報告（mlb_backtest_patch_result.md）：(1) split 違規修正清單、"
            "(2) post-game odds 排除確認清單、(3) edge clean vs contaminated 比較表、"
            f"(4) 驗收標準確認（{ins['expected_metric']}）、(5) 請求生成 validation 任務。"
        ),
    }


# ── Validation blueprint ─────────────────────────────────────────────────────

def _build_validation_blueprint(ins: dict) -> dict:
    """patch task 完成後生成驗收回測任務。"""
    category_label = ins.get("category", "unknown").replace("_", " ").title()
    return {
        "focus_area": f"mlb-validation-{ins.get('category', 'unknown')}",
        "market_scope": "MLB paper-only backtest validation",
        "analysis_family": "model-validation-backtest",
        "title": f"MLB Validation: Backtest Verification of {category_label} Patch Results",
        "focus_keys": f"mlb_validation,{ins.get('category', 'unknown')},brier,logloss,roi,paper_only",
        "signal_state_type": "model_validation_backtest",
        "expected_duration_hours": 2,
        "insight_id": ins["id"],
        "safety_level": "paper_only",
        "objective": (
            f"[PAPER MODE ONLY] 驗收 {category_label} 修補效果。\n"
            "執行完整回測並與 patch 前 baseline 精確比較，"
            f"驗收標準：{ins['expected_metric']}。不修改任何 live 投注邏輯。"
        ),
        "phase_1": (
            "建立至少 3 組驗收策略：\n"
            "(1) patch 前 baseline（從既有回測紀錄或 data/wbc_backend/reports/ 中提取）；\n"
            "(2) patch 後回測（使用修補後的特徵集 / 校準器 / regime 邊界）；\n"
            "(3) patch 後 walk-forward 驗證（時間序列切割，確認無 look-ahead leakage）。\n"
            "確認所有驗收操作只在 wbc_backend/research/ / wbc_backend/evaluation/ 目錄進行。"
        ),
        "phase_2": (
            "對每組策略執行 150 / 500 / 1500 樣本回測，"
            "輸出 Brier score、LogLoss、ROI (paper)、CLV（如可用）、edge、sharpe、drawdown，"
            f"與 baseline 數值精確比較，量化改善幅度。驗收標準：{ins['expected_metric']}。"
        ),
        "phase_3": (
            "執行 Monte Carlo 1000 次以上模擬，確認 patch 後策略在壓力情境下穩定，"
            "分析 bankroll path 的 tail loss 與 worst decile drawdown，"
            "確認 patch 後策略的 Sharpe / Drawdown 不低於 baseline。"
        ),
        "phase_4": (
            "執行 paper mode 安全驗收清單：\n"
            "(1) 所有修補只在 research/ / evaluation/ 目錄；\n"
            "(2) 無 live 投注邏輯修改；\n"
            "(3) 所有特徵無 look-ahead leakage；\n"
            "(4) walk-forward 切割正確（無跨期污染）；\n"
            f"(5) 驗收指標達標（{ins['expected_metric']}）。"
        ),
        "phase_5": (
            f"輸出驗收報告（mlb_validation_{ins.get('category', 'unknown')}_result.md）："
            "(1) baseline vs patch 完整指標比較表；(2) 驗收標準確認清單；"
            "(3) 通過 / 失敗判定與原因；\n"
            "(4) 若通過：建議將 patch 結果納入下一輪 audit 基線；\n"
            "(5) 若失敗：記錄失敗原因，請求下一輪 patch 修正。"
        ),
    }


# ── Category → builder map ───────────────────────────────────────────────────
_PATCH_BUILDERS: dict[str, object] = {
    "calibration": _calibration_patch,
    "feature_quality": _feature_patch,
    "regime_detection": _regime_patch,
    "clv_odds_quality": _clv_patch,
    "feedback_loop": _feedback_patch,
    "backtest_validity": _backtest_validity_patch,
}


def generate_patch_tasks(insights: list[dict]) -> list[dict]:
    """
    將 PENDING 洞見轉換為 patch task dict 列表。
    安全守護：跳過任何 target_files 含 live 路徑的洞見。
    回傳：可直接餵給 planner 品質閘門的候選列表。
    """
    results: list[dict] = []
    for ins in insights:
        category = ins.get("category")
        builder = _PATCH_BUILDERS.get(category)
        if not builder:
            logger.warning("[PatchGen] Unknown category '%s', skipping insight %s.", category, ins.get("id"))
            continue
        if not _is_safe_targets(ins.get("target_files", [])):
            logger.warning("[PatchGen] Insight %s targets live files, skipping.", ins.get("id"))
            continue
        task = builder(ins)  # type: ignore[operator]
        results.append(task)
        logger.info("[PatchGen] Generated '%s' patch task for insight %s", category, ins.get("id"))
    return results


def generate_validation_task(ins: dict) -> dict:
    """
    patch task 完成後，為對應洞見生成驗收回測任務。
    安全守護：同樣確認 target_files 不含 live 路徑。
    """
    if not _is_safe_targets(ins.get("target_files", [])):
        logger.warning("[PatchGen] Insight %s targets live files, skip validation.", ins.get("id"))
        # Return minimal safe fallback (should never happen given upstream guard)
        raise ValueError(f"Insight {ins.get('id')} targets live files")
    return _build_validation_blueprint(ins)
