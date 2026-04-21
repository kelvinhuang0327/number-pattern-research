"""Dynamic EV gate helpers for jackpot-aware decisioning.

This module centralizes the current jackpot snapshot, DB fallback, EV gate,
Kelly cap, and stage-2 threshold evaluation so scripts and API routes can
share one implementation.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"
LOTTERY_TYPES = ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@lru_cache(maxsize=1)
def _load_snapshot_bundle() -> Dict[str, Any]:
    jackpot = _load_json(DATA_DIR / "jackpot_ev_analysis.json")
    ev = _load_json(DATA_DIR / "ev_analysis.json")
    kelly = _load_json(DATA_DIR / "kelly_analysis.json")
    proposal = _load_json(DATA_DIR / "decision_engine_v31_proposal.json")
    stage2 = _load_json(DATA_DIR / "stage2_recalibration.json")
    return {
        "jackpot": jackpot,
        "ev": ev,
        "kelly": kelly,
        "proposal": proposal,
        "stage2": stage2,
    }


def _latest_jackpot_from_db(lottery_type: str, db_path: Path) -> Optional[float]:
    if not db_path.exists():
        return None

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(draws)")
        columns = {row[1] for row in cursor.fetchall()}
        if "jackpot_amount" not in columns:
            return None

        cursor.execute(
            """
            SELECT jackpot_amount
            FROM draws
            WHERE lottery_type = ? AND jackpot_amount IS NOT NULL
            ORDER BY CAST(draw AS INTEGER) DESC
            LIMIT 1
            """,
            (lottery_type,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _safe_float(row[0])
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _choose_sequence(records: Dict[str, Any], preferred_key: Optional[str]) -> Iterable[Dict[str, Any]]:
    if preferred_key and preferred_key in records:
        return records.get(preferred_key, [])
    if records:
        first_key = next(iter(records.keys()))
        return records.get(first_key, [])
    return []


def _stage2_hit_flag(lottery_type: str, record: Dict[str, Any]) -> bool:
    if lottery_type == "DAILY_539":
        if record.get("is_m2plus") is not None:
            return bool(record.get("is_m2plus"))
        return bool(record.get("is_m3plus"))
    if record.get("is_m3plus") is not None:
        return bool(record.get("is_m3plus"))
    return bool(record.get("is_m2plus"))


def evaluate_stage2_gate(lottery_type: str) -> Dict[str, Any]:
    bundle = _load_snapshot_bundle()
    stage2_data = bundle["stage2"].get("by_lottery", {}).get(lottery_type, {})
    optimal_threshold = _safe_float(stage2_data.get("optimal_threshold"), 0.0) or 0.0
    best_strategy = stage2_data.get("best_strategy")

    monitor = _load_json(DATA_DIR / f"rolling_monitor_{lottery_type}.json")
    records = monitor.get("records", {}) if isinstance(monitor, dict) else {}
    seq = list(_choose_sequence(records, best_strategy))
    recent = seq[-50:]

    hit_flags = [_stage2_hit_flag(lottery_type, rec) for rec in recent if isinstance(rec, dict)]
    if hit_flags:
        rolling_hit_rate = sum(1 for flag in hit_flags if flag) / len(hit_flags)
        status = "PASS" if rolling_hit_rate >= optimal_threshold else "BELOW_THRESHOLD"
    else:
        rolling_hit_rate = None
        status = "NO_DATA"

    return {
        "lottery_type": lottery_type,
        "source_file": f"rolling_monitor_{lottery_type}.json",
        "best_strategy": best_strategy,
        "optimal_threshold": optimal_threshold,
        "rolling_50p_hit_rate": rolling_hit_rate,
        "sample_size": len(hit_flags),
        "status": status,
    }


def _resolve_current_jackpot(
    lottery_type: str,
    current_jackpot: Optional[float],
    db_path: Optional[str],
) -> Dict[str, Any]:
    if current_jackpot is not None:
        return {
            "current_jackpot": _safe_float(current_jackpot),
            "source": "provided",
        }

    db_candidate = _latest_jackpot_from_db(lottery_type, Path(db_path) if db_path else DEFAULT_DB_PATH)
    if db_candidate is not None:
        return {
            "current_jackpot": db_candidate,
            "source": "db_latest",
        }

    snapshot = _load_snapshot_bundle()["jackpot"].get("lotteries", {}).get(lottery_type, {})
    if snapshot:
        return {
            "current_jackpot": _safe_float(snapshot.get("current_jackpot")),
            "source": "snapshot_file",
        }

    return {
        "current_jackpot": None,
        "source": "theoretical_only",
    }


def _default_recommended_bet_count(lottery_type: str) -> int:
    if lottery_type == "DAILY_539":
        return 1
    if lottery_type == "POWER_LOTTO":
        return 2
    return 5


def _resolve_recommended_bet_count(
    lottery_type: str,
    jackpot_meta: Dict[str, Any],
    ev_meta: Dict[str, Any],
    kelly_meta: Dict[str, Any],
    proposal_decisions: Dict[str, Any],
    bet_summary: Dict[str, Any],
) -> int:
    candidate = (
        bet_summary.get(lottery_type, {}).get("recommended_bet_count")
        or jackpot_meta.get("bet_count")
        or ev_meta.get("bet_count")
        or kelly_meta.get("current_bet_count")
        or proposal_decisions.get(lottery_type, {}).get("recommended_bet_count")
    )
    recommended = _safe_int(candidate, 0)
    return recommended if recommended > 0 else _default_recommended_bet_count(lottery_type)


def _resolve_ev_metrics(
    jackpot_meta: Dict[str, Any],
    live_jackpot: Optional[float],
) -> Dict[str, Any]:
    breakeven_jackpot = _safe_float(jackpot_meta.get("breakeven_jackpot"))
    jackpot_probability = _safe_float(jackpot_meta.get("jackpot_probability"), 0.0) or 0.0
    non_jackpot_expected_payout = _safe_float(jackpot_meta.get("non_jackpot_expected_payout"), 0.0) or 0.0
    ticket_cost_total = _safe_float(jackpot_meta.get("ticket_cost_total"), 0.0) or 0.0

    current_expected_payout = None
    current_expected_net = None
    current_expected_roi = None
    if live_jackpot is not None:
        current_expected_payout = non_jackpot_expected_payout + jackpot_probability * live_jackpot
        current_expected_net = current_expected_payout - ticket_cost_total
        current_expected_roi = (current_expected_net / ticket_cost_total) if ticket_cost_total else None

    ev_gate_open = bool(live_jackpot is not None and breakeven_jackpot is not None and live_jackpot >= breakeven_jackpot)
    ev_gap = None if live_jackpot is None or breakeven_jackpot is None else live_jackpot - breakeven_jackpot

    return {
        "breakeven_jackpot": breakeven_jackpot,
        "current_expected_payout": current_expected_payout,
        "current_expected_net": current_expected_net,
        "current_expected_roi": current_expected_roi,
        "ev_gate_open": ev_gate_open,
        "ev_gap": ev_gap,
        "ticket_cost_total": ticket_cost_total,
    }


def _resolve_kelly_metrics(
    jackpot_meta: Dict[str, Any],
    ev_meta: Dict[str, Any],
    kelly_meta: Dict[str, Any],
    recommended_bet_count: int,
    ev_gate_open: bool,
) -> Dict[str, Any]:
    kelly_fraction_raw = _safe_float(kelly_meta.get("kelly_fraction_raw"), 0.0) or 0.0
    kelly_fraction = _safe_float(kelly_meta.get("recommended_fraction"), kelly_fraction_raw) or 0.0
    monthly_budget_reference = _safe_float(jackpot_meta.get("monthly_budget_reference"), 0.0) or 0.0

    monthly_budget_after_gate = monthly_budget_reference * kelly_fraction if ev_gate_open else 0.0
    exposure_weight_after_gate = kelly_fraction if ev_gate_open else 0.0
    n_bets_after_gate = recommended_bet_count if ev_gate_open else 0

    return {
        "kelly_fraction_raw": kelly_fraction_raw,
        "kelly_fraction": kelly_fraction,
        "monthly_budget_reference": monthly_budget_reference,
        "monthly_budget_after_gate": monthly_budget_after_gate,
        "exposure_weight_after_gate": exposure_weight_after_gate,
        "n_bets_after_gate": n_bets_after_gate,
        "strategy_name": jackpot_meta.get("strategy_name") or ev_meta.get("strategy_name") or kelly_meta.get("strategy_name"),
        "ticket_cost": jackpot_meta.get("ticket_cost"),
        "bet_count": jackpot_meta.get("bet_count") or ev_meta.get("bet_count") or kelly_meta.get("current_bet_count"),
    }


def evaluate_jackpot_gate(
    lottery_type: str,
    current_jackpot: Optional[float] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    bundle = _load_snapshot_bundle()
    jackpot_meta = bundle["jackpot"].get("lotteries", {}).get(lottery_type, {})
    ev_meta = bundle["ev"].get("lotteries", {}).get(lottery_type, {})
    kelly_meta = bundle["kelly"].get("lotteries", {}).get(lottery_type, {})
    proposal = bundle["proposal"]
    proposal_decisions = proposal.get("lottery_decisions", {})
    bet_summary = proposal.get("bet_sizing_summary", {})

    resolved = _resolve_current_jackpot(lottery_type, current_jackpot, db_path)
    live_jackpot = resolved["current_jackpot"]
    source = resolved["source"]

    ev_metrics = _resolve_ev_metrics(jackpot_meta, live_jackpot)
    recommended_bet_count = _resolve_recommended_bet_count(
        lottery_type,
        jackpot_meta,
        ev_meta,
        kelly_meta,
        proposal_decisions,
        bet_summary,
    )
    kelly_metrics = _resolve_kelly_metrics(
        jackpot_meta,
        ev_meta,
        kelly_meta,
        recommended_bet_count,
        ev_metrics["ev_gate_open"],
    )

    stage2_gate = evaluate_stage2_gate(lottery_type)

    confidence = "HIGH" if source in {"provided", "db_latest", "snapshot_file"} else "LOW"

    return {
        "lottery_type": lottery_type,
        "current_jackpot": live_jackpot,
        "current_jackpot_source": source,
        "current_jackpot_updated_at": jackpot_meta.get("current_jackpot_updated_at"),
        "breakeven_jackpot": ev_metrics["breakeven_jackpot"],
        "ev_gate_open": ev_metrics["ev_gate_open"],
        "ev_gate_recommendation": "OPEN" if ev_metrics["ev_gate_open"] else "CLOSE",
        "ev_gap": ev_metrics["ev_gap"],
        "current_expected_payout": ev_metrics["current_expected_payout"],
        "current_expected_net": ev_metrics["current_expected_net"],
        "current_expected_roi": ev_metrics["current_expected_roi"],
        "recommended_bet_count": recommended_bet_count,
        "n_bets_after_gate": kelly_metrics["n_bets_after_gate"],
        "monthly_budget_reference": kelly_metrics["monthly_budget_reference"],
        "monthly_budget_after_gate": kelly_metrics["monthly_budget_after_gate"],
        "kelly_fraction_raw": kelly_metrics["kelly_fraction_raw"],
        "kelly_fraction": kelly_metrics["kelly_fraction"],
        "exposure_weight_after_gate": kelly_metrics["exposure_weight_after_gate"],
        "strategy_name": kelly_metrics["strategy_name"],
        "ticket_cost": kelly_metrics["ticket_cost"],
        "bet_count": kelly_metrics["bet_count"],
        "proposal_recommendation": proposal_decisions.get(lottery_type, {}).get("recommended_action"),
        "confidence": confidence,
        "stage2_gate": stage2_gate,
        "summary": {
            "jackpot_source": source,
            "gate_status": "OPEN" if ev_metrics["ev_gate_open"] else "CLOSE",
            "gate_confidence": confidence,
        },
    }


def build_gate_snapshot(lottery_types: Iterable[str] = LOTTERY_TYPES) -> Dict[str, Any]:
    return {lt: evaluate_jackpot_gate(lt) for lt in lottery_types}


def format_gate_line(gate: Dict[str, Any]) -> str:
    jackpot = gate.get("current_jackpot")
    breakeven = gate.get("breakeven_jackpot")
    source = gate.get("current_jackpot_source", "unknown")
    status = "OPEN" if gate.get("ev_gate_open") else "CLOSE"
    current_text = f"{jackpot:,.0f}" if jackpot is not None else "N/A"
    breakeven_text = f"{breakeven:,.0f}" if breakeven is not None else "N/A"
    gap = gate.get("ev_gap")
    gap_text = f"{gap:+,.0f}" if gap is not None else "N/A"
    return (
        f"status={status} confidence={gate.get('confidence')} source={source} "
        f"current={current_text} breakeven={breakeven_text} gap={gap_text}"
    )


def format_stage2_line(gate: Dict[str, Any]) -> str:
    stage2 = gate.get("stage2_gate", {})
    hit_rate = stage2.get("rolling_50p_hit_rate")
    hit_rate_text = f"{hit_rate:.3f}" if hit_rate is not None else "N/A"
    threshold = stage2.get("optimal_threshold")
    threshold_text = f"{threshold:.3f}" if threshold is not None else "N/A"
    return (
        f"stage2={stage2.get('status', 'N/A')} hit_rate_50p={hit_rate_text} "
        f"threshold={threshold_text} best_strategy={stage2.get('best_strategy', 'N/A')}"
    )


class EVGate:
    """Compatibility wrapper for import checks and simple programmatic use."""

    @staticmethod
    def evaluate(lottery_type: str, current_jackpot: Optional[float] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
        return evaluate_jackpot_gate(lottery_type, current_jackpot=current_jackpot, db_path=db_path)

    @staticmethod
    def snapshot(lottery_types: Iterable[str] = LOTTERY_TYPES) -> Dict[str, Any]:
        return build_gate_snapshot(lottery_types)

