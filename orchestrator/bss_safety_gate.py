"""
Phase 37: BSS Safety Gate
==========================
當模型 BSS < 0（落後市場基準）時，強制封鎖非調查類任務，
防止已知劣質模型的預測結果流入生產部署流程。

允許任務類型（BSS < 0 時）:
  - INVESTIGATE_*    ← 根因分析
  - COLLECT_*        ← 資料蒐集
  - METRIC_REPAIR    ← 指標修復
  - DATA_REPAIR      ← 資料修復
  - audit_guard_*    ← 審計工具

硬性封鎖（BSS < 0 時）:
  - 生產預測任務
  - Patch 候選評估
  - Kelly 下注執行
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 允許在負 BSS 下執行的任務種類前綴
# ══════════════════════════════════════════════════════════════════════════════
_ALLOWED_TASK_KIND_PREFIXES_WHEN_BSS_NEGATIVE: tuple[str, ...] = (
    "investigate",
    "collect",
    "metric_repair",
    "data_repair",
    "audit_guard",
    "usage_budget",
    "frontend_health",
    "bss_root_cause",
)

# 硬性封鎖前綴（明確禁止）
_BLOCKED_TASK_KIND_PREFIXES_WHEN_BSS_NEGATIVE: tuple[str, ...] = (
    "production_prediction",
    "live_bet",
    "kelly_bet",
    "candidate_patch_eval",
    "patch_candidate",
    "clv_live",
)


@dataclass
class BssSafetyResult:
    """BSS 安全門評估結果"""
    bss: float
    baseline: float  # market_brier (基準 Brier)
    model_brier: float
    bss_negative: bool
    task_kind: str
    allowed: bool
    block_reason: str = ""
    recommendation: str = ""


def evaluate_bss_gate(
    bss: float,
    model_brier: float,
    baseline_brier: float,
    task_kind: str,
) -> BssSafetyResult:
    """
    評估特定任務是否可在當前 BSS 狀態下執行。

    Args:
        bss: Brier Skill Score（例如 -0.141 代表 -14.1%）
        model_brier: 模型 Brier Score
        baseline_brier: 市場基準 Brier Score
        task_kind: 任務種類識別碼（小寫 snake_case）

    Returns:
        BssSafetyResult

    Hard rule: bss < 0 時，只有 `_ALLOWED_TASK_KIND_PREFIXES_WHEN_BSS_NEGATIVE`
               中的任務才能通過。
    """
    bss_negative = bss < 0.0
    task_kind_lower = task_kind.lower().strip()

    if not bss_negative:
        return BssSafetyResult(
            bss=bss,
            baseline=baseline_brier,
            model_brier=model_brier,
            bss_negative=False,
            task_kind=task_kind,
            allowed=True,
            block_reason="",
            recommendation="BSS >= 0, no restriction.",
        )

    # BSS < 0 — 判斷是否屬於允許前綴
    is_allowed = any(
        task_kind_lower.startswith(prefix)
        for prefix in _ALLOWED_TASK_KIND_PREFIXES_WHEN_BSS_NEGATIVE
    )
    is_blocked = any(
        task_kind_lower.startswith(prefix)
        for prefix in _BLOCKED_TASK_KIND_PREFIXES_WHEN_BSS_NEGATIVE
    )

    if is_blocked or not is_allowed:
        reason = (
            f"BSS={bss:+.1%} < 0 (model_brier={model_brier:.4f} > "
            f"market_brier={baseline_brier:.4f}): "
            f"task_kind='{task_kind}' 被封鎖，模型落後市場不允許生產任務。"
        )
        recommendation = (
            "RECOMMEND: INVESTIGATE root cause → METRIC_REPAIR or DATA_REPAIR → "
            "re-backtest → re-validate BSS before re-enabling production."
        )
        logger.warning("[BssSafetyGate] BLOCKED task=%s | %s", task_kind, reason)
        return BssSafetyResult(
            bss=bss,
            baseline=baseline_brier,
            model_brier=model_brier,
            bss_negative=True,
            task_kind=task_kind,
            allowed=False,
            block_reason=reason,
            recommendation=recommendation,
        )

    # 允許的調查類任務
    logger.info(
        "[BssSafetyGate] ALLOWED investigative task=%s (BSS=%+.1%%)",
        task_kind,
        bss * 100,
    )
    return BssSafetyResult(
        bss=bss,
        baseline=baseline_brier,
        model_brier=model_brier,
        bss_negative=True,
        task_kind=task_kind,
        allowed=True,
        block_reason="",
        recommendation="BSS < 0 but task is in allowed investigative category.",
    )


def get_bss_from_report(report_data: dict) -> tuple[float, float, float] | None:
    """
    從回測 report dict 中提取 BSS、model_brier、market_brier。

    Returns:
        (bss, model_brier, market_brier) 或 None（若資料不足）
    """
    bss = report_data.get("brier_skill_score") or report_data.get("bss")
    model_brier = report_data.get("brier_score") or report_data.get("model_brier")
    market_brier = report_data.get("market_brier_score") or report_data.get("market_brier")

    if bss is None or model_brier is None or market_brier is None:
        return None

    return float(bss), float(model_brier), float(market_brier)


# ── 公開的單一入口函式 ────────────────────────────────────────────────────────

def check_bss_safety(
    task_kind: str,
    bss: float = -0.141,
    model_brier: float = 0.2796,
    market_brier: float = 0.2451,
) -> BssSafetyResult:
    """
    對外公開的 BSS 安全門檢查函式（使用 Phase 37 已知基準值為預設）。

    Usage::
        from orchestrator.bss_safety_gate import check_bss_safety
        result = check_bss_safety("production_prediction")
        if not result.allowed:
            raise RuntimeError(result.block_reason)
    """
    return evaluate_bss_gate(
        bss=bss,
        model_brier=model_brier,
        baseline_brier=market_brier,
        task_kind=task_kind,
    )
