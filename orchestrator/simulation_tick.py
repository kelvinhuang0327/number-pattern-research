"""
Track C — Simulation / Paper Trading Tick

每 30 分鐘執行：
  1. 載入 trade_ledger.jsonl（leakage-free：僅使用 pregame predicted_prob）
  2. 壓力測試：odds shift / volatility spike / adversarial flip
  3. 計算各情境下的 Brier / ROI / CLV
  4. 寫入 research/simulation_results.jsonl
  5. 偵測弱點 → 觸發 insight 提取（若嚴重）
"""
from __future__ import annotations

import json
import logging
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from orchestrator import db
from orchestrator import execution_policy
from orchestrator.common import HARD_OFF_MODE, build_runtime_guard_message
from orchestrator import phase6_data_registry

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = _REPO_ROOT / "research" / "trade_ledger.jsonl"
SIM_RESULTS_PATH = _REPO_ROOT / "research" / "simulation_results.jsonl"
SIM_SUMMARY_PATH = _REPO_ROOT / "runtime" / "agent_orchestrator" / "simulation_summary.json"

# ── 弱點偵測閾值 ──
ROI_WEAKNESS_THRESHOLD = -0.15        # 任一情境 ROI < -15% → ROI_WEAKNESS
BRIER_REGRESSION_THRESHOLD = 0.10    # Brier 比基線惡化 >10% → BRIER_WEAKNESS
ADVERSARIAL_ROI_THRESHOLD = -0.30    # 對抗情境 ROI < -30% → ROBUSTNESS_WEAKNESS
MIN_SETTLED_RECORDS = 5              # 至少需要 N 筆結算紀錄才執行


# ─────────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────────

def _load_settled_records() -> list[dict]:
    """
    從 trade_ledger.jsonl 載入已結算紀錄。
    僅取 event_type=settlement、result in (win, loss)、roi 不為 null 的條目。
    """
    if not LEDGER_PATH.exists():
        return []

    records: list[dict] = []
    with LEDGER_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                row.get("event_type") == "settlement"
                and row.get("result") in ("win", "loss")
                and row.get("roi") is not None
                and row.get("predicted_prob") is not None
                and row.get("market_prob") is not None
            ):
                records.append(row)
    return records


# ─────────────────────────────────────────────
# 指標計算
# ─────────────────────────────────────────────

def _result_binary(result: str) -> int:
    """將比賽結果轉換為二元 label（從 predicted_prob 角度：押對 = 1）。"""
    return 1 if result == "win" else 0


def _compute_metrics(records: list[dict]) -> dict:
    """計算 Brier、ROI、CLV 等指標。"""
    if not records:
        return {"n": 0, "brier": None, "roi": None, "avg_clv": None, "total_pnl": None}

    n = len(records)
    brier_sum = 0.0
    roi_sum = 0.0
    stake_sum = 0.0
    pnl_sum = 0.0
    clv_list: list[float] = []

    for r in records:
        prob = float(r.get("predicted_prob", 0.5))
        outcome = _result_binary(r["result"])
        brier_sum += (prob - outcome) ** 2

        roi = r.get("roi") or 0.0
        pnl = r.get("pnl") or 0.0
        stake = r.get("stake") or 0.0
        roi_sum += roi
        pnl_sum += pnl
        stake_sum += stake

        clv = r.get("clv")
        if clv is not None:
            clv_list.append(float(clv))

    return {
        "n": n,
        "brier": round(brier_sum / n, 6),
        "roi": round(roi_sum / n, 6),
        "total_pnl": round(pnl_sum, 4),
        "avg_clv": round(sum(clv_list) / len(clv_list), 4) if clv_list else None,
    }


# ─────────────────────────────────────────────
# 擾動情境
# ─────────────────────────────────────────────

def _apply_odds_shift(records: list[dict], shift: float) -> list[dict]:
    """
    Odds shift 情境：market_prob 等比例移動 shift（+0.05 = 線更緊）。
    predicted_prob 不變（僅評估 edge 縮水情況）。
    """
    out: list[dict] = []
    for r in records:
        row = dict(r)
        mp = float(row.get("market_prob", 0.5))
        row["market_prob"] = max(0.01, min(0.99, mp + shift))
        # ROI 重算：若 edge 縮水到 <=0 則設為 loss (ROI=-1)
        edge = float(row.get("predicted_prob", 0.5)) - row["market_prob"]
        if edge <= 0.0 and row.get("decision") == "BET":
            row["roi"] = -1.0  # would not bet / forced loss
            row["pnl"] = -(row.get("stake") or 0.0)
        out.append(row)
    return out


def _apply_volatility_spike(records: list[dict], magnitude: float, seed: int = 42) -> list[dict]:
    """
    Volatility spike 情境：在 predicted_prob 上加 magnitude 大小的隨機雜訊。
    使用固定 seed 確保可重現。
    """
    rng = random.Random(seed)
    out: list[dict] = []
    for r in records:
        row = dict(r)
        noise = rng.uniform(-magnitude, magnitude)
        prob = float(row.get("predicted_prob", 0.5))
        row["predicted_prob"] = max(0.01, min(0.99, prob + noise))
        out.append(row)
    return out


def _apply_adversarial_flip(records: list[dict], regime: Optional[str] = None) -> list[dict]:
    """
    對抗情境：將指定 regime（或全部）的 predicted_prob 翻轉為 1 - predicted_prob。
    模擬最差情況：模型判斷完全相反。
    """
    out: list[dict] = []
    for r in records:
        row = dict(r)
        if regime is None or row.get("regime") == regime:
            prob = float(row.get("predicted_prob", 0.5))
            row["predicted_prob"] = 1.0 - prob
            # ROI 也翻轉（因為下反邊）
            row["roi"] = -(row.get("roi") or 0.0)
            row["pnl"] = -(row.get("pnl") or 0.0)
        out.append(row)
    return out


# ─────────────────────────────────────────────
# 弱點偵測
# ─────────────────────────────────────────────

def _detect_weaknesses(scenarios: dict) -> list[str]:
    """根據各情境指標偵測系統弱點。"""
    weaknesses: list[str] = []

    baseline = scenarios.get("baseline", {})
    baseline_brier = baseline.get("brier")

    for name, metrics in scenarios.items():
        roi = metrics.get("roi")
        brier = metrics.get("brier")

        if roi is not None and roi < ROI_WEAKNESS_THRESHOLD:
            weaknesses.append(f"ROI_WEAKNESS:{name}(roi={roi:.3f})")

        if brier is not None and baseline_brier is not None:
            regression = (brier - baseline_brier) / (baseline_brier + 1e-9)
            if regression > BRIER_REGRESSION_THRESHOLD:
                weaknesses.append(f"BRIER_WEAKNESS:{name}(regression={regression:.1%})")

    adversarial_roi = scenarios.get("adversarial_flip", {}).get("roi")
    if adversarial_roi is not None and adversarial_roi < ADVERSARIAL_ROI_THRESHOLD:
        weaknesses.append(f"ROBUSTNESS_WEAKNESS(adversarial_roi={adversarial_roi:.3f})")

    return weaknesses


# ─────────────────────────────────────────────
# Phase 6T EV edge analysis (no settlement needed)
# ─────────────────────────────────────────────

def _compute_phase6_ev_analysis() -> dict:
    """
    Load Phase 6T registry rows and compute EV edge scenarios.

    IMPORTANT CONSTRAINTS:
    - These rows have NO settled results → do NOT compute Brier or realized ROI.
    - PENDING_CLOSING CLV rows are explicitly excluded from CLV-based signals.
    - Only EV-based exposure scenarios are computed.

    Returns a dict with:
      n_registry_rows   : total 6T rows loaded
      n_eligible_ev     : rows with positive EV
      avg_ev_pct        : mean EV across eligible rows
      ev_shift_p3_safe  : rows remaining positive EV after +3% odds shift
      ev_shift_m3_safe  : rows remaining positive EV after -3% odds shift
      clv_pending       : count with PENDING_CLOSING — NOT used as CLV signal
      clv_computed      : count with COMPUTED — eligible for CLV signal
      clv_pending_excluded_from_reinforcement : always True (safety assertion)
      source            : "phase6t_registry"
    """
    p6_status = phase6_data_registry.get_phase6_status()
    dates = p6_status.get("dates", [])

    all_sim_rows: list[dict] = []
    for date in dates:
        rows_6t = phase6_data_registry.load_registry_6t_rows(date)
        sim_rows = phase6_data_registry.registry_rows_to_simulation_records(rows_6t)
        all_sim_rows.extend(sim_rows)

    n = len(all_sim_rows)
    if n == 0:
        return {
            "n_registry_rows": 0,
            "n_eligible_ev": 0,
            "avg_ev_pct": None,
            "ev_shift_p3_safe": 0,
            "ev_shift_m3_safe": 0,
            "clv_pending": p6_status.get("clv_pending_closing", 0),
            "clv_computed": p6_status.get("clv_computed", 0),
            "clv_pending_excluded_from_reinforcement": True,
            "source": "phase6t_registry",
        }

    eligible = [r for r in all_sim_rows if r["ev_percent"] > 0]
    n_eligible = len(eligible)
    avg_ev = (sum(r["ev_percent"] for r in eligible) / n_eligible) if n_eligible else 0.0

    # EV edge after +3% odds shift (market moves against us)
    ev_shift_p3 = 0
    ev_shift_m3 = 0
    for r in all_sim_rows:
        pred = r["predicted_prob"]
        mkt_tightened = min(0.99, r["market_prob"] + 0.03)
        mkt_loosened = max(0.01, r["market_prob"] - 0.03)
        if pred - mkt_tightened > 0:
            ev_shift_p3 += 1
        if pred - mkt_loosened > 0:
            ev_shift_m3 += 1

    return {
        "n_registry_rows": n,
        "n_eligible_ev": n_eligible,
        "avg_ev_pct": round(avg_ev, 4) if n_eligible else None,
        "ev_shift_p3_safe": ev_shift_p3,
        "ev_shift_m3_safe": ev_shift_m3,
        "clv_pending": p6_status.get("clv_pending_closing", 0),
        "clv_computed": p6_status.get("clv_computed", 0),
        "clv_pending_excluded_from_reinforcement": True,
        "source": "phase6t_registry",
    }


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def run_simulation_tick() -> dict:
    """
    Track C 主入口。

    回傳:
    {
        "status": "SUCCESS" | "SKIPPED" | "FAILED",
        "n_records": int,
        "scenarios": {scenario_name: metrics_dict},
        "weaknesses": [str],
        "weakness_detected": bool,
        "run_at": str,
    }
    """
    run_at = datetime.now(timezone.utc).isoformat()

    try:
        decision = execution_policy.evaluate_execution(
            runner="simulation_tick",
            background=True,
            manual_override=execution_policy.is_manual_run(os.environ),
        )
        if not decision["allowed"]:
            message = decision["message"]
            logger.info("[SimulationTick] %s", message)
            return {"status": "SKIPPED", "reason": message, "run_at": run_at}

        records = _load_settled_records()
        n = len(records)

        if n < MIN_SETTLED_RECORDS:
            logger.info(
                "[SimulationTick] 結算紀錄不足 (%d < %d)，跳過本輪",
                n, MIN_SETTLED_RECORDS,
            )
            return {"status": "SKIPPED", "n_records": n, "reason": "insufficient_settled_records",
                    "run_at": run_at}

        # ── 各壓力情境 ──
        scenarios: dict[str, dict] = {
            "baseline":      _compute_metrics(records),
            "odds_shift_p5": _compute_metrics(_apply_odds_shift(records, +0.05)),
            "odds_shift_m5": _compute_metrics(_apply_odds_shift(records, -0.05)),
            "volatility_10": _compute_metrics(_apply_volatility_spike(records, 0.10)),
            "adversarial_flip": _compute_metrics(_apply_adversarial_flip(records)),
        }

        # ── 按 regime 細分基線 ──
        regimes: dict[str, list[dict]] = {}
        for r in records:
            reg = r.get("regime") or "unknown"
            regimes.setdefault(reg, []).append(r)

        regime_metrics: dict[str, dict] = {
            reg: _compute_metrics(recs) for reg, recs in regimes.items()
        }

        # ── 弱點偵測 ──
        weaknesses = _detect_weaknesses(scenarios)
        weakness_detected = bool(weaknesses)

        # ── Phase 6T EV edge analysis ──
        phase6_ev = _compute_phase6_ev_analysis()

        result = {
            "status": "SUCCESS",
            "n_records": n,
            "scenarios": scenarios,
            "regime_breakdown": regime_metrics,
            "weaknesses": weaknesses,
            "weakness_detected": weakness_detected,
            "phase6_ev_analysis": phase6_ev,
            "run_at": run_at,
        }

        # ── 持久化：追加到 simulation_results.jsonl ──
        SIM_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SIM_RESULTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

        # ── 最新摘要快照 ──
        SIM_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SIM_SUMMARY_PATH.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        if weakness_detected:
            logger.warning(
                "[SimulationTick] 偵測到弱點: %s",
                ", ".join(weaknesses),
            )
        else:
            logger.info(
                "[SimulationTick] 成功 n=%d  baseline ROI=%.4f  Brier=%.4f  "
                "無嚴重弱點",
                n,
                scenarios["baseline"].get("roi", 0),
                scenarios["baseline"].get("brier", 0),
            )

        return result

    except Exception as exc:
        logger.exception("[SimulationTick] 執行失敗: %s", exc)
        return {"status": "FAILED", "error": str(exc), "run_at": run_at}


def get_latest_simulation_summary() -> Optional[dict]:
    """取得最新模擬摘要（若存在）。"""
    if SIM_SUMMARY_PATH.exists():
        try:
            return json.loads(SIM_SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def get_simulation_history(last_n: int = 20) -> list[dict]:
    """取得最近 N 筆模擬結果（最新在前）。"""
    if not SIM_RESULTS_PATH.exists():
        return []
    results: list[dict] = []
    with SIM_RESULTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(results[-last_n:]))
