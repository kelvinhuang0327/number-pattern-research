"""
P6-E — Strategy Promotion Freeze Rule
=======================================
正式凍結 POST_GAME_PROXY odds 來源的 optimizer promotion。

核心規則：
- 若 strategy result 來源包含 POST_GAME_PROXY_ONLY → promotion_status = BLOCKED_POST_GAME_PROXY_ONLY
- 即使 ROI、CI、p-value 看似通過，也不得 promoted
- CLV not ready → promotion blocked
- paper_only=false → raise

這是高於 P4 champion gate 的上游守衛（pre-gate）。
只有通過本 freeze check，才允許進入 P4 champion gate 評估。
"""
from __future__ import annotations

from wbc_backend.recommendation.clv_readiness_gate import (
    CLV_READY,
    BLOCKED_POST_GAME_PROXY_ONLY,
    BLOCKED_NO_PREGAME_ODDS,
    BLOCKED_NO_CLOSING_ODDS,
    BLOCKED_LOW_TIMESTAMP_COVERAGE,
    ClvGateError,
    evaluate_clv_readiness,
)
from wbc_backend.recommendation.odds_contract import OddsSourceType

# Promotion status constants
PROMOTION_ALLOWED                   = "PROMOTION_ALLOWED"
PROMOTION_BLOCKED_POST_GAME_PROXY   = "PROMOTION_BLOCKED_POST_GAME_PROXY_ONLY"
PROMOTION_BLOCKED_CLV_NOT_READY     = "PROMOTION_BLOCKED_CLV_NOT_READY"
PROMOTION_BLOCKED_PAPER_ONLY_FALSE  = "PROMOTION_BLOCKED_PAPER_ONLY_FALSE"
PROMOTION_BLOCKED_MISSING_ODDS_TYPE = "PROMOTION_BLOCKED_MISSING_ODDS_TYPE"


class PromotionFreezeError(ValueError):
    """Promotion freeze 合約違規。"""


def check_promotion_eligibility(
    strategy_result: dict,
    odds_snapshots: list,
) -> dict:
    """
    在 P4 champion gate 之前執行的上游 promotion freeze 守衛。

    Parameters
    ----------
    strategy_result : dict
        含 paper_only、roi、ci_low 等欄位的策略評估結果
    odds_snapshots : list of dict
        此策略使用的 odds 記錄（需含 source_type 欄位）

    Returns
    -------
    dict 包含：
      promotion_status : PROMOTION_ALLOWED 或 PROMOTION_BLOCKED_*
      reason           : 說明
      clv_status       : CLV gate 的詳細狀態
      paper_only       : True
    """
    # ── paper_only 守衛 ────────────────────────────────────────────────────
    if strategy_result.get("paper_only") is False:
        raise PromotionFreezeError(
            "[PromotionFreeze] strategy_result paper_only=false is forbidden."
        )
    for s in odds_snapshots:
        po = s.get("paper_only") if isinstance(s, dict) else getattr(s, "paper_only", None)
        if po is False:
            raise PromotionFreezeError(
                "[PromotionFreeze] odds_snapshot paper_only=false is forbidden."
            )

    # ── 檢查 odds_snapshots 是否提供 ──────────────────────────────────────
    if not odds_snapshots:
        return {
            "promotion_status": PROMOTION_BLOCKED_MISSING_ODDS_TYPE,
            "reason": "no odds_snapshots provided; cannot verify odds source type",
            "clv_status": None,
            "paper_only": True,
        }

    # ── CLV readiness gate ────────────────────────────────────────────────
    try:
        clv_result = evaluate_clv_readiness(odds_snapshots)
    except ClvGateError as e:
        raise PromotionFreezeError(str(e)) from e

    clv_status = clv_result["status"]

    if clv_status == BLOCKED_POST_GAME_PROXY_ONLY:
        return {
            "promotion_status": PROMOTION_BLOCKED_POST_GAME_PROXY,
            "reason": (
                "Odds source is POST_GAME_PROXY_ONLY. "
                "Cannot promote strategy without pregame/closing odds. "
                f"CLV gate reason: {clv_result['reason']}"
            ),
            "clv_status": clv_result,
            "paper_only": True,
        }

    if clv_status != CLV_READY:
        return {
            "promotion_status": PROMOTION_BLOCKED_CLV_NOT_READY,
            "reason": (
                f"CLV not ready ({clv_status}). "
                f"Cannot promote until pregame+closing odds are available. "
                f"CLV gate reason: {clv_result['reason']}"
            ),
            "clv_status": clv_result,
            "paper_only": True,
        }

    # ── CLV_READY → 允許進入 P4 champion gate ────────────────────────────
    return {
        "promotion_status": PROMOTION_ALLOWED,
        "reason": "CLV_READY: pregame+closing odds verified. Proceed to P4 champion gate.",
        "clv_status": clv_result,
        "paper_only": True,
    }


def current_dataset_promotion_status() -> dict:
    """
    對目前 P1 artifact（POST_GAME_PROXY 全體）輸出正式凍結狀態。
    供 P6-E artifact 生成使用。
    """
    mock_proxy_snapshots = [
        {"source_type": OddsSourceType.POST_GAME_PROXY.value, "paper_only": True}
        for _ in range(2430)
    ]
    result = check_promotion_eligibility(
        strategy_result={"paper_only": True},
        odds_snapshots=mock_proxy_snapshots,
    )
    result["dataset"] = "strategy_sim_v2_ha40_platt_with_outcomes_v2_20260519.jsonl"
    result["n_records"] = 2430
    result["annotation"] = (
        "paper_only=true. P6-E 正式凍結：目前 P1 artifact 所有 2430 筆記錄均為 "
        "POST_GAME_PROXY，optimizer promotion 被凍結，fixed_edge_5pct 保留為 champion。"
    )
    return result
