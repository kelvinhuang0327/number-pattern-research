"""
Track D — Strategy Feedback Loop Tick

由驗證結果觸發（通常每 5 分鐘檢查一次，有新決策才實際調整）：
  1. 讀取 insights.json 中最新 VALIDATED / PARTIAL / FAILED 洞見
  2. 結合 training_memory.json 的趨勢分析
  3. 結合 simulation_summary.json 的壓力測試結果
  4. 計算信心度/曝險調整量
  5. 更新 runtime/agent_orchestrator/strategy_state.json

調整規則：
  KEEP_PATCH   → confidence_weight += 0.05、exposure_level += 0.03
  PARTIAL_KEEP → confidence_weight += 0.02（謹慎加倉）
  REJECT_PATCH → confidence_weight -= 0.05、exposure_level -= 0.03
  FAILED       → confidence_weight -= 0.10（嚴重懲罰）
  Simulation ROI_WEAKNESS → exposure_level -= 0.05（壓力懲罰）

所有值均被 clip 到安全範圍：
  confidence_weight : [0.50, 1.50]
  exposure_level    : [0.25, 1.00]
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from orchestrator import db
from orchestrator import execution_policy
from orchestrator.common import HARD_OFF_MODE, build_runtime_guard_message
from orchestrator import phase6_data_registry

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "insights.json"
STRATEGY_STATE_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "strategy_state.json"
SIM_SUMMARY_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "simulation_summary.json"

# ── 調整幅度參數 ──
_DELTA = {
    "KEEP_PATCH":    {"confidence": +0.05, "exposure": +0.03},
    "PARTIAL_KEEP":  {"confidence": +0.02, "exposure": +0.00},
    "REJECT_PATCH":  {"confidence": -0.05, "exposure": -0.03},
    "INSUFFICIENT_DATA": {"confidence": +0.00, "exposure": +0.00},
    "FAILED":        {"confidence": -0.10, "exposure": -0.05},
}

# ── 信心/曝險安全範圍 ──
CONFIDENCE_MIN, CONFIDENCE_MAX = 0.50, 1.50
EXPOSURE_MIN, EXPOSURE_MAX = 0.25, 1.00

# ── 壓力測試懲罰 ──
SIM_ROI_WEAKNESS_PENALTY = -0.05

# ── 只處理自上次運行後的新決策 ──
_TERMINAL_STATUSES = {"VALIDATED", "PARTIAL", "FAILED"}


# ─────────────────────────────────────────────
# 狀態 I/O
# ─────────────────────────────────────────────

def _default_state() -> dict:
    return {
        "confidence_weight": 1.00,
        "exposure_level": 0.75,
        "regime_overrides": {},   # regime → {confidence_weight, exposure_level}
        "revert_flag": False,
        "last_processed_insight_ids": [],
        "consecutive_negative": 0,
        "consecutive_positive": 0,
        "last_updated": None,
        "update_history": [],     # 最近 50 筆調整記錄
    }


def load_strategy_state() -> dict:
    """載入策略狀態；不存在則回傳預設值。"""
    if STRATEGY_STATE_PATH.exists():
        try:
            return json.loads(STRATEGY_STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[StrategyTick] 無法載入策略狀態，使用預設值: %s", exc)
    return _default_state()


def _save_strategy_state(state: dict) -> None:
    STRATEGY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ─────────────────────────────────────────────
# 洞見讀取
# ─────────────────────────────────────────────

def _load_new_insights(last_processed_ids: list[str]) -> list[dict]:
    """
    載入 insights.json 中尚未處理的終態洞見
    (status in {VALIDATED, PARTIAL, FAILED})。
    """
    if not INSIGHTS_PATH.exists():
        return []
    try:
        all_insights = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    new_insights = [
        ins for ins in all_insights
        if ins.get("status") in _TERMINAL_STATUSES
        and ins.get("id") not in last_processed_ids
    ]
    return new_insights


def _insight_to_decision_key(ins: dict) -> str:
    """將 insight 狀態對應到調整鍵。"""
    status = ins.get("status", "")
    partial_reason = ins.get("partial_reason", "")

    if status == "VALIDATED":
        return "KEEP_PATCH"
    if status == "PARTIAL":
        reason = partial_reason or ""
        return "PARTIAL_KEEP" if "PARTIAL" in reason else "INSUFFICIENT_DATA"
    if status == "FAILED":
        return "FAILED"
    return "INSUFFICIENT_DATA"


# ─────────────────────────────────────────────
# 壓力測試整合
# ─────────────────────────────────────────────

def _load_sim_weakness_penalty() -> float:
    """若最新模擬偵測到 ROI_WEAKNESS，回傳懲罰值，否則回傳 0.0。"""
    if not SIM_SUMMARY_PATH.exists():
        return 0.0
    try:
        summary = json.loads(SIM_SUMMARY_PATH.read_text(encoding="utf-8"))
        weaknesses = summary.get("weaknesses", [])
        if any("ROI_WEAKNESS" in w for w in weaknesses):
            return SIM_ROI_WEAKNESS_PENALTY
    except Exception:
        pass
    return 0.0


# ─────────────────────────────────────────────
# Phase 6U CLV state gate
# ─────────────────────────────────────────────

# CLV state labels for Phase 6 integration
_PHASE6_CLV_STATE_COMPUTED   = "COMPUTED"
_PHASE6_CLV_STATE_PENDING    = "WAITING_FOR_MARKET_SETTLEMENT"
_PHASE6_CLV_STATE_NONE       = "NO_PHASE6_DATA"


def _load_phase6_clv_state() -> dict:
    """
    Load Phase 6U CLV status from the data registry.

    Returns:
      clv_state   : COMPUTED | WAITING_FOR_MARKET_SETTLEMENT | NO_PHASE6_DATA
      computed    : int — rows with real CLV
      pending     : int — rows still PENDING_CLOSING
      blocked     : int — rows BLOCKED by gate
      eligible_for_reinforcement : bool — True only if computed > 0
    """
    p6 = phase6_data_registry.get_phase6_status()
    computed = p6.get("clv_computed", 0)
    pending  = p6.get("clv_pending_closing", 0)
    blocked  = p6.get("clv_blocked", 0)

    if computed > 0:
        state = _PHASE6_CLV_STATE_COMPUTED
    elif pending > 0:
        state = _PHASE6_CLV_STATE_PENDING
    else:
        state = _PHASE6_CLV_STATE_NONE

    return {
        "clv_state": state,
        "computed": computed,
        "pending": pending,
        "blocked": blocked,
        "eligible_for_reinforcement": computed > 0,
    }


# ─────────────────────────────────────────────
# Phase 7 — CLV-based reinforcement signal
# ─────────────────────────────────────────────

_CLV_REINFORCE_THRESHOLD_POSITIVE = 0.010  # avg CLV > +1% → boost
_CLV_REINFORCE_THRESHOLD_NEGATIVE = -0.010 # avg CLV < -1% → penalize
_CLV_REINFORCE_DELTA = 0.02                # max delta per tick


def _load_computed_clv_records(reports_dir: Path | None = None) -> list[dict]:
    """
    Load COMPUTED CLV records from Phase 7 upgraded JSONL files.
    Returns only records with clv_status == "COMPUTED" and a numeric clv_value.
    """
    import re as _re
    rdir = reports_dir or (_REPO_ROOT / "data" / "wbc_backend" / "reports")
    rows: list[dict] = []
    for path in sorted(rdir.glob("clv_validation_records_6u_upgraded_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("clv_status") == "COMPUTED" and rec.get("clv_value") is not None:
                rows.append(rec)
    return rows


def _compute_clv_reinforcement_signal(
    computed_rows: list[dict],
) -> dict:
    """
    Compute a CLV-based reinforcement signal from COMPUTED records.

    Rules (per-tick, conservative):
      avg_clv > +0.010 → confidence_delta = +0.02  (market validated our edge)
      avg_clv < -0.010 → confidence_delta = -0.02  (market moved against us)
      else             → no adjustment

    Returns:
      avg_clv            : float | None
      confidence_delta   : float
      exposure_delta     : float
      n_computed         : int
      direction          : "positive" | "negative" | "flat" | "no_data"
      source             : "phase7_clv_reinforcement"
    """
    if not computed_rows:
        return {
            "avg_clv": None,
            "confidence_delta": 0.0,
            "exposure_delta": 0.0,
            "n_computed": 0,
            "direction": "no_data",
            "source": "phase7_clv_reinforcement",
        }

    clv_values = [
        float(r["clv_value"])
        for r in computed_rows
        if r.get("clv_value") is not None
    ]
    if not clv_values:
        return {
            "avg_clv": None,
            "confidence_delta": 0.0,
            "exposure_delta": 0.0,
            "n_computed": len(computed_rows),
            "direction": "no_data",
            "source": "phase7_clv_reinforcement",
        }

    avg_clv = round(sum(clv_values) / len(clv_values), 6)

    if avg_clv > _CLV_REINFORCE_THRESHOLD_POSITIVE:
        direction = "positive"
        confidence_delta = _CLV_REINFORCE_DELTA
    elif avg_clv < _CLV_REINFORCE_THRESHOLD_NEGATIVE:
        direction = "negative"
        confidence_delta = -_CLV_REINFORCE_DELTA
    else:
        direction = "flat"
        confidence_delta = 0.0

    return {
        "avg_clv": avg_clv,
        "confidence_delta": confidence_delta,
        "exposure_delta": 0.0,   # CLV does not directly adjust position sizing
        "n_computed": len(computed_rows),
        "direction": direction,
        "source": "phase7_clv_reinforcement",
    }


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def run_strategy_tick() -> dict:
    """
    Track D 主入口。

    回傳:
    {
        "status": "SUCCESS" | "SKIPPED" | "FAILED",
        "new_insights_processed": int,
        "confidence_weight": float,
        "exposure_level": float,
        "revert_flag": bool,
        "adjustments": [dict],
        "run_at": str,
    }
    """
    run_at = datetime.now(timezone.utc).isoformat()

    try:
        decision = execution_policy.evaluate_execution(
            runner="strategy_tick",
            background=True,
            manual_override=execution_policy.is_manual_run(os.environ),
        )
        if not decision["allowed"]:
            message = decision["message"]
            logger.info("[StrategyTick] %s", message)
            return {
                "status": "SKIPPED",
                "new_insights_processed": 0,
                "adjustments": [],
                "run_at": run_at,
                "reason": message,
            }

        state = load_strategy_state()
        last_processed = state.get("last_processed_insight_ids", [])

        new_insights = _load_new_insights(last_processed)

        if not new_insights:
            logger.debug("[StrategyTick] 無新洞見，跳過本輪")
            return {
                "status": "SKIPPED",
                "new_insights_processed": 0,
                "confidence_weight": state["confidence_weight"],
                "exposure_level": state["exposure_level"],
                "revert_flag": state.get("revert_flag", False),
                "adjustments": [],
                "run_at": run_at,
            }

        # ── 計算調整量 ──
        total_confidence_delta = 0.0
        total_exposure_delta = 0.0
        adjustments: list[dict] = []

        for ins in new_insights:
            key = _insight_to_decision_key(ins)
            delta = _DELTA.get(key, {"confidence": 0.0, "exposure": 0.0})
            total_confidence_delta += delta["confidence"]
            total_exposure_delta += delta["exposure"]

            adjustments.append({
                "insight_id": ins.get("id"),
                "status": ins.get("status"),
                "decision_key": key,
                "confidence_delta": delta["confidence"],
                "exposure_delta": delta["exposure"],
                "category": ins.get("category"),
            })

        # ── 壓力測試懲罰 ──
        sim_penalty = _load_sim_weakness_penalty()
        if sim_penalty != 0.0:
            total_exposure_delta += sim_penalty
            adjustments.append({
                "insight_id": "simulation_weakness",
                "status": "SIM_PENALTY",
                "decision_key": "SIM_ROI_WEAKNESS",
                "confidence_delta": 0.0,
                "exposure_delta": sim_penalty,
                "category": "simulation",
            })

        # ── Phase 6U CLV gate — block reinforcement on PENDING_CLOSING ──
        phase6_clv = _load_phase6_clv_state()
        if phase6_clv["pending"] > 0 and not phase6_clv["eligible_for_reinforcement"]:
            # All CLV is PENDING_CLOSING — do NOT apply CLV-based reinforcement.
            # EV-based adjustments from insight validation are still allowed.
            logger.info(
                "[StrategyTick] Phase 6U CLV state=%s (%d pending) — "
                "CLV-based reinforcement BLOCKED; insight-based adjustments proceed normally",
                phase6_clv["clv_state"],
                phase6_clv["pending"],
            )

        # ── Phase 7 CLV reinforcement (only when COMPUTED records exist) ──
        clv_reinforce: dict = {
            "avg_clv": None, "confidence_delta": 0.0, "exposure_delta": 0.0,
            "n_computed": 0, "direction": "no_data", "source": "phase7_clv_reinforcement",
        }
        if phase6_clv["eligible_for_reinforcement"]:
            computed_rows = _load_computed_clv_records()
            clv_reinforce = _compute_clv_reinforcement_signal(computed_rows)
            if clv_reinforce["confidence_delta"] != 0.0:
                total_confidence_delta += clv_reinforce["confidence_delta"]
                adjustments.append({
                    "insight_id": "phase7_clv_reinforcement",
                    "status": f"CLV_{clv_reinforce['direction'].upper()}",
                    "decision_key": "CLV_REINFORCE",
                    "confidence_delta": clv_reinforce["confidence_delta"],
                    "exposure_delta": 0.0,
                    "category": "phase7_clv",
                    "avg_clv": clv_reinforce.get("avg_clv"),
                    "n_computed": clv_reinforce.get("n_computed", 0),
                })
                logger.info(
                    "[StrategyTick] Phase 7 CLV reinforcement: avg_clv=%.4f  "
                    "direction=%s  confidence_delta=%.2f  n_computed=%d",
                    clv_reinforce.get("avg_clv", 0),
                    clv_reinforce["direction"],
                    clv_reinforce["confidence_delta"],
                    clv_reinforce.get("n_computed", 0),
                )

        # Record phase6 CLV state in strategy state for observability
        state["phase6_clv_state"] = phase6_clv
        state["phase7_clv_reinforce"] = clv_reinforce

        # ── 套用並 clip ──
        old_confidence = state["confidence_weight"]
        old_exposure = state["exposure_level"]

        new_confidence = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX,
            old_confidence + total_confidence_delta))
        new_exposure = max(EXPOSURE_MIN, min(EXPOSURE_MAX,
            old_exposure + total_exposure_delta))

        # ── 連續正/負計數 ──
        if total_confidence_delta > 0:
            state["consecutive_positive"] = state.get("consecutive_positive", 0) + 1
            state["consecutive_negative"] = 0
        elif total_confidence_delta < 0:
            state["consecutive_negative"] = state.get("consecutive_negative", 0) + 1
            state["consecutive_positive"] = 0

        # ── revert_flag：連續 3 次以上負面調整 ──
        state["revert_flag"] = state.get("consecutive_negative", 0) >= 3

        # ── 更新 regime overrides（若洞見有指定 regime）──
        for ins in new_insights:
            regime = ins.get("regime") or ins.get("source_signal_state_type", "")
            if regime and regime != "unknown":
                key = _insight_to_decision_key(ins)
                delta = _DELTA.get(key, {"confidence": 0.0, "exposure": 0.0})
                override = state["regime_overrides"].setdefault(regime, {
                    "confidence_weight": 1.00,
                    "exposure_level": 0.75,
                })
                override["confidence_weight"] = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX,
                    override["confidence_weight"] + delta["confidence"]))
                override["exposure_level"] = max(EXPOSURE_MIN, min(EXPOSURE_MAX,
                    override["exposure_level"] + delta["exposure"]))

        # ── 已處理洞見 ID ──
        processed_ids = last_processed + [ins.get("id") for ins in new_insights if ins.get("id")]
        # 保留最近 500 筆 ID 以避免無限增長
        state["last_processed_insight_ids"] = processed_ids[-500:]

        # ── 更新記錄（最近 50 筆）──
        history_entry = {
            "run_at": run_at,
            "confidence_before": old_confidence,
            "confidence_after": new_confidence,
            "exposure_before": old_exposure,
            "exposure_after": new_exposure,
            "n_insights": len(new_insights),
            "sim_penalty": sim_penalty,
            "revert_flag": state["revert_flag"],
        }
        update_history = state.get("update_history", [])
        update_history.append(history_entry)
        state["update_history"] = update_history[-50:]

        # ── 更新狀態 ──
        state["confidence_weight"] = new_confidence
        state["exposure_level"] = new_exposure
        state["last_updated"] = run_at

        _save_strategy_state(state)

        logger.info(
            "[StrategyTick] 處理 %d 筆洞見  "
            "confidence %.2f→%.2f  exposure %.2f→%.2f  "
            "revert_flag=%s",
            len(new_insights),
            old_confidence, new_confidence,
            old_exposure, new_exposure,
            state["revert_flag"],
        )

        return {
            "status": "SUCCESS",
            "new_insights_processed": len(new_insights),
            "confidence_weight": new_confidence,
            "exposure_level": new_exposure,
            "revert_flag": state["revert_flag"],
            "adjustments": adjustments,
            "phase6_clv_state": phase6_clv,
            "phase7_clv_reinforce": clv_reinforce,
            "run_at": run_at,
        }

    except Exception as exc:
        logger.exception("[StrategyTick] 執行失敗: %s", exc)
        return {"status": "FAILED", "error": str(exc), "run_at": run_at}


def get_strategy_state() -> dict:
    """取得目前策略狀態快照。"""
    return load_strategy_state()


def get_exposure_level() -> float:
    """快速取得目前曝險等級（供外部查詢）。"""
    return load_strategy_state().get("exposure_level", 0.75)


def get_confidence_weight() -> float:
    """快速取得目前信心權重（供外部查詢）。"""
    return load_strategy_state().get("confidence_weight", 1.00)


def is_revert_flagged() -> bool:
    """快速查詢是否觸發了回撤旗標。"""
    return bool(load_strategy_state().get("revert_flag", False))


def reset_strategy_state() -> None:
    """將策略狀態重置為預設值（謹慎使用）。"""
    _save_strategy_state(_default_state())
    logger.warning("[StrategyTick] 策略狀態已重置為預設值")
