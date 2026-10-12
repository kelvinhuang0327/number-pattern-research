"""
Training Memory — 記錄每次 patch 的效果，防止重複失敗，驅動難度升級。

儲存於 runtime/agent_orchestrator/training_memory.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "training_memory.json"

# ── 難度等級 ──
DIFFICULTY_SIMPLE = 1    # 單一特徵修補、小閾值調整
DIFFICULTY_MEDIUM = 2    # 多特徵交叉、ensemble blend
DIFFICULTY_ADVANCED = 3  # regime 分層模型、組合策略邏輯

# ── 難度升降閾值 ──
PROMOTE_AFTER_N_SUCCESSES = 3   # N 次連續成功 → 升級難度
DEMOTE_AFTER_N_FAILURES = 2     # N 次連續失敗 → 降級難度

# ── 歷史紀錄上限 ──
MAX_HISTORY = 200


# ─────────────────────────────────────────────
# 核心 I/O
# ─────────────────────────────────────────────

def _empty_memory() -> dict:
    return {
        "difficulty_level": DIFFICULTY_SIMPLE,
        "consecutive_successes": 0,
        "consecutive_failures": 0,
        "patch_history": [],
        "failure_patterns": {},   # category → [method, ...]
        "success_rates": {},      # category → {total, success, partial}
        "regime_performance": {}, # regime → {brier_delta_sum, count}
        "last_updated": None,
    }


def load_memory() -> dict:
    """載入訓練記憶；不存在則回傳空結構。"""
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[TrainingMemory] 無法載入記憶檔，回傳空結構: %s", exc)
    return _empty_memory()


def _save_memory(mem: dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────
# 核心記錄函式
# ─────────────────────────────────────────────

def record_patch_result(
    patch_task_id: int,
    insight_id: str,
    category: str,
    method: str,
    decision: str,
    brier_delta: float,
    logloss_delta: float,
    n_samples: int,
    regime_breakdown: Optional[dict] = None,
) -> dict:
    """
    記錄一次 patch 驗證結果。

    decision 合法值：KEEP_PATCH | PARTIAL_KEEP | REJECT_PATCH | INSUFFICIENT_DATA
    回傳更新後的記憶 dict。
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "patch_task_id": patch_task_id,
        "insight_id": insight_id,
        "category": category,
        "method": method,
        "decision": decision,
        "brier_delta": brier_delta,
        "logloss_delta": logloss_delta,
        "n_samples": n_samples,
        "regime_breakdown": regime_breakdown or {},
        "timestamp": now,
    }

    # ── 加入歷史，上限 MAX_HISTORY ──
    mem["patch_history"].append(record)
    if len(mem["patch_history"]) > MAX_HISTORY:
        mem["patch_history"] = mem["patch_history"][-MAX_HISTORY:]

    # ── 更新成功率統計 ──
    sr = mem["success_rates"].setdefault(category, {"total": 0, "success": 0, "partial": 0})
    sr["total"] += 1

    is_success = decision in ("KEEP_PATCH", "PARTIAL_KEEP")
    if decision == "KEEP_PATCH":
        sr["success"] += 1
    elif decision == "PARTIAL_KEEP":
        sr["partial"] += 1

    # ── 更新連續計數 ──
    if is_success:
        mem["consecutive_successes"] = mem.get("consecutive_successes", 0) + 1
        mem["consecutive_failures"] = 0
    else:
        mem["consecutive_failures"] = mem.get("consecutive_failures", 0) + 1
        mem["consecutive_successes"] = 0
        # 記錄失敗模式（避免重複）
        fp = mem["failure_patterns"].setdefault(category, [])
        if method not in fp:
            fp.append(method)

    # ── 更新 regime 性能 ──
    for regime, metrics in (regime_breakdown or {}).items():
        rp = mem["regime_performance"].setdefault(
            regime, {"brier_delta_sum": 0.0, "count": 0}
        )
        bd = metrics.get("brier_delta", 0.0) if isinstance(metrics, dict) else 0.0
        rp["brier_delta_sum"] += bd
        rp["count"] += 1

    # ── 自動調整難度 ──
    _update_difficulty(mem)

    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] 記錄: category=%s method=%s decision=%s "
        "brier_delta=%.4f  difficulty=%d  "
        "consecutive_ok=%d  consecutive_fail=%d",
        category, method, decision, brier_delta,
        mem["difficulty_level"],
        mem["consecutive_successes"],
        mem["consecutive_failures"],
    )
    return mem


# ─────────────────────────────────────────────
# 難度升降邏輯
# ─────────────────────────────────────────────

def _update_difficulty(mem: dict) -> None:
    """根據連續成功/失敗自動調整難度等級。"""
    current = mem.get("difficulty_level", DIFFICULTY_SIMPLE)
    successes = mem.get("consecutive_successes", 0)
    failures = mem.get("consecutive_failures", 0)

    if successes >= PROMOTE_AFTER_N_SUCCESSES and current < DIFFICULTY_ADVANCED:
        mem["difficulty_level"] = current + 1
        mem["consecutive_successes"] = 0
        logger.info("[TrainingMemory] 難度提升: %d → %d", current, current + 1)
    elif failures >= DEMOTE_AFTER_N_FAILURES and current > DIFFICULTY_SIMPLE:
        mem["difficulty_level"] = current - 1
        mem["consecutive_failures"] = 0
        logger.info("[TrainingMemory] 難度降低: %d → %d", current, current - 1)


# ─────────────────────────────────────────────
# 查詢介面
# ─────────────────────────────────────────────

def get_current_difficulty() -> int:
    """取得目前訓練難度等級 (1-3)。"""
    return load_memory().get("difficulty_level", DIFFICULTY_SIMPLE)


def should_skip_method(category: str, method: str) -> bool:
    """若此 category+method 組合曾連續失敗，建議跳過。"""
    fp = load_memory().get("failure_patterns", {})
    return method in fp.get(category, [])


def get_failure_summary() -> dict:
    """
    取得各類別失敗摘要，供 planner 迴避重複錯誤。
    回傳: {category: {failed_methods, success_rate, total_attempts}}
    """
    mem = load_memory()
    summary: dict = {}
    for cat, methods in mem.get("failure_patterns", {}).items():
        sr = mem.get("success_rates", {}).get(cat, {})
        total = sr.get("total", 0)
        ok = sr.get("success", 0) + sr.get("partial", 0)
        summary[cat] = {
            "failed_methods": methods,
            "success_rate": round(ok / total, 3) if total > 0 else 0.0,
            "total_attempts": total,
        }
    return summary


def get_regime_performance() -> dict:
    """
    取得各 regime 的平均 brier_delta，供策略調整參考。
    回傳: {regime: avg_brier_delta}
    """
    mem = load_memory()
    result: dict = {}
    for regime, data in mem.get("regime_performance", {}).items():
        count = data.get("count", 0)
        if count > 0:
            result[regime] = round(data["brier_delta_sum"] / count, 4)
    return result


def get_recent_outcomes(n: int = 20) -> list[dict]:
    """取得最近 n 筆 patch 紀錄（最新在前）。"""
    mem = load_memory()
    history = mem.get("patch_history", [])
    return list(reversed(history[-n:]))


def get_success_rate(category: Optional[str] = None) -> float:
    """
    取得指定類別（或整體）的成功率（KEEP + PARTIAL 視為成功）。
    """
    mem = load_memory()
    if category:
        sr = mem.get("success_rates", {}).get(category, {})
        total = sr.get("total", 0)
        ok = sr.get("success", 0) + sr.get("partial", 0)
        return round(ok / total, 3) if total > 0 else 0.0
    # 整體
    total_all = 0
    ok_all = 0
    for sr in mem.get("success_rates", {}).values():
        total_all += sr.get("total", 0)
        ok_all += sr.get("success", 0) + sr.get("partial", 0)
    return round(ok_all / total_all, 3) if total_all > 0 else 0.0


def clear_failure_pattern(category: str) -> None:
    """手動清除指定類別的失敗模式（允許再次嘗試）。"""
    mem = load_memory()
    if category in mem.get("failure_patterns", {}):
        del mem["failure_patterns"][category]
        mem["last_updated"] = datetime.now(timezone.utc).isoformat()
        _save_memory(mem)
        logger.info("[TrainingMemory] 已清除 category=%s 的失敗模式", category)


def get_summary_report() -> dict:
    """回傳完整摘要，供 CTO/排程器狀態展示。"""
    mem = load_memory()
    return {
        "difficulty_level": mem.get("difficulty_level", DIFFICULTY_SIMPLE),
        "consecutive_successes": mem.get("consecutive_successes", 0),
        "consecutive_failures": mem.get("consecutive_failures", 0),
        "total_patches_recorded": len(mem.get("patch_history", [])),
        "overall_success_rate": get_success_rate(),
        "failure_summary": get_failure_summary(),
        "regime_performance": get_regime_performance(),
        "last_updated": mem.get("last_updated"),
    }


# ─────────────────────────────────────────────
# Phase 6 CLV state recording
# ─────────────────────────────────────────────

# Maximum Phase 6 CLV state entries to retain in memory
MAX_PHASE6_STATES = 100


def record_phase6_clv_state(
    date: str,
    registry_rows: int,
    clv_pending: int,
    clv_computed: int,
    clv_blocked: int,
) -> dict:
    """
    Record a Phase 6U CLV state snapshot into training memory.

    CRITICAL CONSTRAINTS:
    - NEVER increments consecutive_successes (no game settlement yet).
    - NEVER increments consecutive_failures (no settlement yet).
    - Only records observational state for audit trail.
    - Settlement-based success judgement requires clv_computed > 0 AND
      a separate verification step comparing closing odds to predicted edge.

    Returns updated memory dict.
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    clv_state_label: str
    if clv_computed > 0:
        clv_state_label = "COMPUTED"
    elif clv_pending > 0:
        clv_state_label = "PENDING_CLOSING"
    else:
        clv_state_label = "BLOCKED_OR_EMPTY"

    entry = {
        "date": date,
        "registry_rows": registry_rows,
        "clv_pending": clv_pending,
        "clv_computed": clv_computed,
        "clv_blocked": clv_blocked,
        "clv_state": clv_state_label,
        "settlement_complete": False,   # Always False at recording time
        "reinforcement_eligible": clv_computed > 0,
        "recorded_at": now,
    }

    phase6_states: list[dict] = mem.get("phase6_states", [])
    phase6_states.append(entry)
    # Deduplicate by date — keep the most recent entry per date
    seen: dict[str, dict] = {}
    for e in phase6_states:
        seen[e["date"]] = e
    mem["phase6_states"] = list(seen.values())[-MAX_PHASE6_STATES:]

    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] Phase 6 CLV state recorded: date=%s "
        "registry=%d  pending=%d  computed=%d  blocked=%d  state=%s",
        date, registry_rows, clv_pending, clv_computed, clv_blocked, clv_state_label,
    )
    return mem


def get_phase6_clv_history() -> list[dict]:
    """Return all recorded Phase 6 CLV state snapshots (newest last)."""
    return load_memory().get("phase6_states", [])


# ─────────────────────────────────────────────
# Phase 7 CLV outcome recording
# ─────────────────────────────────────────────

# Maximum CLV outcome entries to retain
MAX_CLV_OUTCOMES = 200


def record_clv_outcome(
    prediction_id: str,
    clv_value: float,
    clv_direction: str,
    source: str,
    regime: str = "",
    market_type: str = "",
    selection: str = "",
) -> dict:
    """
    Record a realized CLV outcome for a single prediction.

    CRITICAL CONSTRAINTS:
    - Only call this when clv_status == "COMPUTED" (real closing odds available).
    - NEVER call for PENDING_CLOSING records.
    - NEVER increments consecutive_successes or consecutive_failures.
      CLV outcomes inform edge quality but are NOT model patch decisions.

    clv_direction should be one of:
      "positive"  — clv_value > +0.005  (market confirmed edge)
      "negative"  — clv_value < -0.005  (market moved against prediction)
      "flat"      — otherwise

    Returns updated memory dict.
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    # Validate direction
    valid_directions = {"positive", "negative", "flat"}
    if clv_direction not in valid_directions:
        clv_direction = "flat"

    entry = {
        "prediction_id": prediction_id,
        "clv_value": round(float(clv_value), 6),
        "clv_direction": clv_direction,
        "source": source,
        "regime": regime,
        "market_type": market_type,
        "selection": selection,
        "recorded_at": now,
    }

    clv_outcomes: list[dict] = mem.get("clv_outcomes", [])
    # Deduplicate by prediction_id — latest wins
    seen_ids: dict[str, dict] = {e["prediction_id"]: e for e in clv_outcomes}
    seen_ids[prediction_id] = entry
    mem["clv_outcomes"] = list(seen_ids.values())[-MAX_CLV_OUTCOMES:]

    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] CLV outcome recorded: prediction_id=%s  "
        "clv_value=%.4f  direction=%s  source=%s",
        prediction_id, clv_value, clv_direction, source,
    )
    return mem


def get_clv_outcomes(n: int = 50) -> list[dict]:
    """Return the most recent n CLV outcomes (newest last)."""
    mem = load_memory()
    outcomes = mem.get("clv_outcomes", [])
    return outcomes[-n:]


def get_clv_outcome_summary() -> dict:
    """
    Summarize recorded CLV outcomes.

    Returns:
      total          : int
      positive_count : int
      negative_count : int
      flat_count     : int
      avg_clv        : float | None
      positive_rate  : float  (0.0–1.0)
    """
    outcomes = get_clv_outcomes(n=MAX_CLV_OUTCOMES)
    if not outcomes:
        return {
            "total": 0,
            "positive_count": 0,
            "negative_count": 0,
            "flat_count": 0,
            "avg_clv": None,
            "positive_rate": 0.0,
        }
    pos = sum(1 for o in outcomes if o.get("clv_direction") == "positive")
    neg = sum(1 for o in outcomes if o.get("clv_direction") == "negative")
    flat = sum(1 for o in outcomes if o.get("clv_direction") == "flat")
    clv_vals = [float(o["clv_value"]) for o in outcomes if o.get("clv_value") is not None]
    avg_clv = round(sum(clv_vals) / len(clv_vals), 6) if clv_vals else None
    total = len(outcomes)
    return {
        "total": total,
        "positive_count": pos,
        "negative_count": neg,
        "flat_count": flat,
        "avg_clv": avg_clv,
        "positive_rate": round(pos / total, 3) if total > 0 else 0.0,
    }


# ─────────────────────────────────────────────
# Phase 8 Optimization State Transition recording
# ─────────────────────────────────────────────

MAX_STATE_TRANSITIONS = 200


def record_optimization_state_transition(
    new_state: str,
    reasons: list[str],
    previous_state: str = "",
) -> dict:
    """
    Record an optimization state transition for future analysis.

    CRITICAL CONSTRAINTS:
    - NEVER increments consecutive_successes or consecutive_failures.
    - NEVER affects difficulty level.
    - Only records scheduler state metadata for observability.

    Returns updated memory dict.
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    # Derive previous_state from last recorded transition if not supplied
    if not previous_state:
        transitions: list[dict] = mem.get("optimization_state_transitions", [])
        if transitions:
            previous_state = transitions[-1].get("new_state", "")

    # Skip recording if state is unchanged (avoids noise)
    if previous_state and previous_state == new_state:
        return mem

    entry = {
        "previous_state": previous_state,
        "new_state": new_state,
        "reasons": list(reasons),
        "timestamp": now,
    }

    transitions = mem.get("optimization_state_transitions", [])
    transitions.append(entry)
    if len(transitions) > MAX_STATE_TRANSITIONS:
        transitions = transitions[-MAX_STATE_TRANSITIONS:]
    mem["optimization_state_transitions"] = transitions

    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] OptState transition: %s → %s  reasons=%s",
        previous_state or "(initial)", new_state, reasons,
    )
    return mem


def get_optimization_state_transitions(n: int = 20) -> list[dict]:
    """Return the most recent n optimization state transitions (newest last)."""
    mem = load_memory()
    transitions = mem.get("optimization_state_transitions", [])
    return transitions[-n:]


# ─────────────────────────────────────────────
# Phase 20 Learning Cycle Recording
# ─────────────────────────────────────────────

MAX_LEARNING_CYCLES = 50


def record_learning_cycle(
    task_id: str,
    computed_clv_count: int,
    mean_clv: Optional[float],
    recommendation: str,
    learning_cycle_status: str,
    source: str = "sandbox/test",
    artifact_path: Optional[str] = None,
) -> dict:
    """
    Record a completed sandbox learning cycle into training memory.

    CRITICAL CONSTRAINTS:
    - source MUST be "sandbox/test" for all sandbox cycles.
    - NEVER increments consecutive_successes or consecutive_failures.
    - Does NOT affect difficulty_level.
    - Records observational learning evidence only — no production mutation.

    Args:
        task_id:               Unique task identifier for this cycle.
        computed_clv_count:    Number of COMPUTED CLV records analysed.
        mean_clv:              Mean CLV across all computed records (or None if empty).
        recommendation:        "HOLD" | "INVESTIGATE" | "CANDIDATE_PATCH".
        learning_cycle_status: "COMPLETED" | "PARTIAL" | "FAILED".
        source:                Marker string — always "sandbox/test" for Phase 20.
        artifact_path:         Absolute path to the Markdown artifact, if written.

    Returns:
        Updated memory dict (already saved to disk).
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    entry: dict = {
        "task_id": task_id,
        "computed_clv_count": computed_clv_count,
        "mean_clv": round(float(mean_clv), 6) if mean_clv is not None else None,
        "recommendation": recommendation,
        "learning_cycle_status": learning_cycle_status,
        "source": source,
        "artifact_path": artifact_path,
        "recorded_at": now,
    }

    cycles: list[dict] = mem.get("learning_cycles", [])
    cycles.append(entry)
    if len(cycles) > MAX_LEARNING_CYCLES:
        cycles = cycles[-MAX_LEARNING_CYCLES:]
    mem["learning_cycles"] = cycles
    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] Learning cycle recorded: task_id=%s  "
        "computed_clv=%d  mean_clv=%s  recommendation=%s  status=%s  source=%s",
        task_id,
        computed_clv_count,
        f"{mean_clv:.4f}" if mean_clv is not None else "N/A",
        recommendation,
        learning_cycle_status,
        source,
    )
    return mem


def get_learning_cycle_history(n: int = 20) -> list[dict]:
    """Return the most recent n learning cycles, newest last."""
    mem = load_memory()
    cycles = mem.get("learning_cycles", [])
    return cycles[-n:]


def get_latest_learning_cycle() -> Optional[dict]:
    """Return the most recent learning cycle entry, or None if none recorded."""
    cycles = get_learning_cycle_history(n=1)
    return cycles[0] if cycles else None


# ─────────────────────────────────────────────
# Phase 21 Patch Gate Recording
# ─────────────────────────────────────────────

MAX_GATE_DECISIONS = 50


def record_gate_decision(
    learning_cycle_id: str,
    gate_decision: str,
    reason: str,
    confidence: str,
    requires_human_review: bool,
    recommendation: str,
    computed_clv_count: int,
    source: str = "sandbox/test",
    generated_task_id: Optional[str] = None,
    allowed_task_family: Optional[str] = None,
) -> dict:
    """
    Record a learning patch gate evaluation result into training memory.

    CRITICAL CONSTRAINTS:
    - Does NOT modify patch_history or consecutive_successes/failures.
    - Does NOT create actual tasks — it only records the gate outcome.
    - source must reflect the true signal origin ("sandbox/test" or "production").

    Args:
        learning_cycle_id:    task_id from the corresponding learning cycle.
        gate_decision:        One of GATE_ALLOW_PATCH_CANDIDATE / GATE_HOLD /
                              GATE_INVESTIGATE_ONLY / GATE_REJECT_INSUFFICIENT_EVIDENCE.
        reason:               Human-readable explanation of the gate decision.
        confidence:           "low" | "medium" | "high".
        requires_human_review: True if the decision needs operator sign-off.
        recommendation:       Input recommendation ("HOLD" / "INVESTIGATE" / "CANDIDATE_PATCH").
        computed_clv_count:   Number of COMPUTED CLV records evaluated.
        source:               Origin marker — always "sandbox/test" for Phase 21 sandbox.
        generated_task_id:    ID of any task created as a result of this gate (or None).
        allowed_task_family:  Task family that was allowed, if any (or None).

    Returns:
        Updated memory dict (already saved to disk).
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    entry: dict = {
        "learning_cycle_id": learning_cycle_id,
        "gate_decision": gate_decision,
        "reason": reason,
        "confidence": confidence,
        "requires_human_review": requires_human_review,
        "recommendation": recommendation,
        "computed_clv_count": computed_clv_count,
        "source": source,
        "generated_task_id": generated_task_id,
        "allowed_task_family": allowed_task_family,
        "recorded_at": now,
    }

    decisions: list[dict] = mem.get("gate_decisions", [])
    decisions.append(entry)
    if len(decisions) > MAX_GATE_DECISIONS:
        decisions = decisions[-MAX_GATE_DECISIONS:]
    mem["gate_decisions"] = decisions
    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] Gate decision recorded: cycle_id=%s  gate=%s  "
        "confidence=%s  human_review=%s  task=%s  source=%s",
        learning_cycle_id,
        gate_decision,
        confidence,
        requires_human_review,
        generated_task_id or "(none)",
        source,
    )
    return mem


def get_gate_decision_history(n: int = 20) -> list[dict]:
    """Return the most recent n gate decisions, newest last."""
    mem = load_memory()
    decisions = mem.get("gate_decisions", [])
    return decisions[-n:]


def get_latest_gate_decision() -> Optional[dict]:
    """Return the most recent gate decision, or None if none recorded."""
    decisions = get_gate_decision_history(n=1)
    return decisions[0] if decisions else None


# ─────────────────────────────────────────────
# Phase 22 Patch Evaluation Recording
# ─────────────────────────────────────────────

MAX_PATCH_EVALUATIONS = 50


def record_patch_evaluation(
    gate_decision_id: str,
    task_id: str,
    evaluation_decision: str,
    baseline_metric: float | None,
    candidate_metric: float | None,
    delta: float | None,
    sample_count: int,
    source: str = "sandbox/test",
    learning_cycle_id: Optional[str] = None,
    artifact_path: Optional[str] = None,
) -> dict:
    """
    Record a calibration patch evaluation result into training memory.

    CRITICAL CONSTRAINTS:
    - This NEVER marks the evaluation as a production patch.
    - Does NOT modify patch_history (that is for production-validated patches).
    - Does NOT affect consecutive_successes / consecutive_failures counters.
    - source must reflect the true origin ("sandbox/test" always for Phase 22).

    Args:
        gate_decision_id:    ID of the gate decision that authorised this evaluation.
        task_id:             DB task ID of the calibration_patch_evaluation task.
        evaluation_decision: "KEEP_SANDBOX_CANDIDATE" | "REJECT_SANDBOX_CANDIDATE" |
                             "NEED_MORE_DATA".
        baseline_metric:     Baseline mean CLV (None if no data).
        candidate_metric:    Candidate mean CLV (None if no data).
        delta:               candidate_metric - baseline_metric (None if no data).
        sample_count:        Number of COMPUTED CLV records evaluated.
        source:              Always "sandbox/test" for Phase 22.
        learning_cycle_id:   ID of the originating learning cycle.
        artifact_path:       Path to the written Markdown artifact.

    Returns:
        Updated memory dict (already saved to disk).
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    entry: dict = {
        "gate_decision_id": gate_decision_id,
        "task_id": task_id,
        "evaluation_decision": evaluation_decision,
        "baseline_metric": baseline_metric,
        "candidate_metric": candidate_metric,
        "delta": delta,
        "sample_count": sample_count,
        "source": source,
        "production_patch_allowed": False,
        "learning_cycle_id": learning_cycle_id,
        "artifact_path": artifact_path,
        "recorded_at": now,
    }

    evaluations: list[dict] = mem.get("patch_evaluations", [])
    evaluations.append(entry)
    if len(evaluations) > MAX_PATCH_EVALUATIONS:
        evaluations = evaluations[-MAX_PATCH_EVALUATIONS:]
    mem["patch_evaluations"] = evaluations
    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] Patch evaluation recorded: gate=%s  task=%s  "
        "decision=%s  delta=%s  source=%s",
        gate_decision_id,
        task_id,
        evaluation_decision,
        f"{delta:.4f}" if delta is not None else "N/A",
        source,
    )
    return mem


def get_patch_evaluation_history(n: int = 20) -> list[dict]:
    """Return the most recent n patch evaluation records, newest last."""
    mem = load_memory()
    evaluations = mem.get("patch_evaluations", [])
    return evaluations[-n:]


def get_latest_patch_evaluation() -> Optional[dict]:
    """Return the most recent patch evaluation result, or None if none recorded."""
    evals = get_patch_evaluation_history(n=1)
    return evals[0] if evals else None


def update_gate_decision_generated_task_id(
    learning_cycle_id: str,
    generated_task_id: int | str,
) -> bool:
    """
    Update the most recent gate decision for learning_cycle_id with generated_task_id.

    Used by planner_tick to mark that a task has already been created for this gate
    decision, preventing duplicate task generation on subsequent planner ticks.

    Returns:
        True if a matching gate decision was found and updated, False otherwise.
    """
    mem = load_memory()
    decisions = mem.get("gate_decisions", [])
    updated = False
    for i in range(len(decisions) - 1, -1, -1):
        if decisions[i].get("learning_cycle_id") == learning_cycle_id:
            decisions[i]["generated_task_id"] = str(generated_task_id)
            decisions[i]["task_generated_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
            break
    if updated:
        mem["gate_decisions"] = decisions
        mem["last_updated"] = datetime.now(timezone.utc).isoformat()
        _save_memory(mem)
        logger.info(
            "[TrainingMemory] Gate decision updated: learning_cycle=%s  task_id=%s",
            learning_cycle_id,
            generated_task_id,
        )
    return updated


# ─────────────────────────────────────────────
# Phase 23 Patch Evaluation Decision Gate Recording
# ─────────────────────────────────────────────

MAX_PATCH_EVAL_GATE_DECISIONS = 50


def record_patch_evaluation_gate_decision(
    task_id: str,
    evaluation_decision: str,
    next_decision: str,
    reason: str,
    confidence: str,
    requires_human_review: bool,
    allowed_next_task_family: str | None = None,
    generated_task_id: str | int | None = None,
    gate_decision_id: str | None = None,
    source: str = "sandbox/test",
    delta: float | None = None,
    sample_count: int = 0,
) -> dict:
    """
    Record a Phase 23 patch evaluation gate decision into training memory.

    CRITICAL CONSTRAINTS:
    - production_patch_allowed is ALWAYS False.
    - Does NOT modify patch_history, consecutive counters, or CLV records.
    - generated_task_id captures any follow-up task created by the planner.

    Args:
        task_id:                 Phase 22 task that produced the evaluation result.
        evaluation_decision:     KEEP_SANDBOX_CANDIDATE | REJECT_SANDBOX_CANDIDATE | NEED_MORE_DATA
        next_decision:           Gate output: PROMOTE_TO_PRODUCTION_PROPOSAL | REJECT |
                                 REQUEST_MORE_DATA | HUMAN_REVIEW_REQUIRED | HOLD
        reason:                  Human-readable rationale.
        confidence:              "low" | "medium" | "high"
        requires_human_review:   Always True for PROMOTE decisions.
        allowed_next_task_family: Task family to create next (or None).
        generated_task_id:       If a follow-up task was already created.
        gate_decision_id:        ID of the upstream Phase 21/22 gate decision.
        source:                  "sandbox/test" or "production".
        delta:                   CLV delta from evaluation.
        sample_count:            Sample size used in evaluation.

    Returns:
        Updated memory dict (already saved to disk).
    """
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()

    entry: dict = {
        "task_id": task_id,
        "evaluation_decision": evaluation_decision,
        "next_decision": next_decision,
        "reason": reason,
        "confidence": confidence,
        "requires_human_review": requires_human_review,
        "allowed_next_task_family": allowed_next_task_family,
        "generated_task_id": str(generated_task_id) if generated_task_id is not None else None,
        "gate_decision_id": gate_decision_id,
        "source": source,
        "delta": delta,
        "sample_count": sample_count,
        # Safety contract — always hardcoded
        "production_patch_allowed": False,
        "production_model_modified": False,
        "external_llm_called": False,
        "recorded_at": now,
    }

    records: list[dict] = mem.get("patch_eval_gate_decisions", [])
    records.append(entry)
    if len(records) > MAX_PATCH_EVAL_GATE_DECISIONS:
        records = records[-MAX_PATCH_EVAL_GATE_DECISIONS:]
    mem["patch_eval_gate_decisions"] = records
    mem["last_updated"] = now
    _save_memory(mem)

    logger.info(
        "[TrainingMemory] Patch eval gate decision recorded: "
        "task=%s  eval=%s  next=%s  confidence=%s",
        task_id,
        evaluation_decision,
        next_decision,
        confidence,
    )
    return mem


def get_patch_evaluation_gate_history(n: int = 20) -> list[dict]:
    """Return the most recent n patch evaluation gate decisions, newest last."""
    mem = load_memory()
    records = mem.get("patch_eval_gate_decisions", [])
    return records[-n:]


def get_latest_patch_evaluation_gate_decision() -> Optional[dict]:
    """Return the most recent patch evaluation gate decision, or None."""
    history = get_patch_evaluation_gate_history(n=1)
    return history[0] if history else None


def update_patch_eval_gate_generated_task_id(
    task_id: str,
    generated_task_id: int | str,
) -> bool:
    """
    Update the most recent patch_eval_gate_decisions entry for task_id
    with the ID of the follow-up task that the planner created.

    Returns True if found and updated, False otherwise.
    """
    mem = load_memory()
    records = mem.get("patch_eval_gate_decisions", [])
    updated = False
    for i in range(len(records) - 1, -1, -1):
        if records[i].get("task_id") == str(task_id):
            records[i]["generated_task_id"] = str(generated_task_id)
            records[i]["task_generated_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
            break
    if updated:
        mem["patch_eval_gate_decisions"] = records
        mem["last_updated"] = datetime.now(timezone.utc).isoformat()
        _save_memory(mem)
        logger.info(
            "[TrainingMemory] Patch eval gate entry updated: task=%s  generated_task=%s",
            task_id,
            generated_task_id,
        )
    return updated
