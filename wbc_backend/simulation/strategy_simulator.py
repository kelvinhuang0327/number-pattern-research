"""
wbc_backend/simulation/strategy_simulator.py

Minimal reusable strategy simulation API.

Key function:
    simulate_strategy(strategy_name, rows, date_start, date_end, ...) -> StrategySimulationResult

Reuses existing metric functions from wbc_backend/evaluation/metrics.py:
    - brier_score()
    - brier_skill_score()
    - expected_calibration_error()
    - american_moneyline_pair_to_no_vig()

Design notes:
- This is a simulation spine, not a profitability claim.
- ROI is computed from available data only; if result/odds are missing, ROI = None.
- Synthetic data is NOT faked. Missing metrics are returned as None with source_trace.
- paper_only always remains True.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from wbc_backend.evaluation.metrics import (
    american_moneyline_pair_to_no_vig,
    american_odds_to_implied_prob,
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)
from wbc_backend.simulation.strategy_simulation_result import StrategySimulationResult

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_AMERICAN_ZERO_SENTINEL = 0       # rows with 0 ML are unusable
_MIN_PROB = 1e-6
_MAX_PROB = 1.0 - 1e-6


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float | None = None) -> float | None:
    """Parse a value to float, returning default on failure."""
    if value is None:
        return default
    try:
        f = float(str(value).replace("+", "").strip())
        return f if math.isfinite(f) else default
    except (ValueError, TypeError):
        return default


def _american_to_decimal(ml: float) -> float:
    """Convert American odds to decimal odds."""
    if ml > 0:
        return (ml / 100.0) + 1.0
    else:
        return (100.0 / abs(ml)) + 1.0


def _kelly_fraction(edge: float, decimal_odds: float, cap: float) -> float:
    """Full Kelly fraction capped at `cap`."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    kelly = edge / b
    return max(0.0, min(cap, kelly))


def _parse_row_outcome(row: dict) -> int | None:
    """
    Determine actual outcome (1 = home win, 0 = home loss).
    Returns None if the game result is not available.
    """
    away_score = _safe_float(row.get("Away Score") or row.get("away_score"))
    home_score = _safe_float(row.get("Home Score") or row.get("home_score"))
    status = str(row.get("Status") or row.get("status") or "").strip().lower()

    if status not in ("final", "completed", "complete"):
        return None
    if away_score is None or home_score is None:
        return None
    return 1 if home_score > away_score else 0


def _parse_row_market_probs(row: dict) -> tuple[float | None, float | None]:
    """
    Extract no-vig home/away implied probs from American moneyline columns.
    Returns (home_no_vig, away_no_vig) or (None, None) if parsing fails.
    """
    home_ml_raw = row.get("Home ML") or row.get("home_ml")
    away_ml_raw = row.get("Away ML") or row.get("away_ml")
    if home_ml_raw is None or away_ml_raw is None:
        return None, None
    try:
        result = american_moneyline_pair_to_no_vig(home_ml_raw, away_ml_raw)
        return result["home_no_vig"], result["away_no_vig"]
    except Exception:
        return None, None


def _parse_row_model_prob(
    row: dict,
    market_home_prob: float | None,
) -> float | None:
    """
    Extract model probability for home win.
    Uses the 'model_prob_home' column if present, otherwise falls back to
    market prob as proxy (with source_trace noting the proxy).
    Returns None if no usable value is available.
    """
    model_prob = _safe_float(row.get("model_prob_home") or row.get("model_prob"))
    if model_prob is not None:
        return float(max(_MIN_PROB, min(_MAX_PROB, model_prob)))
    # Fallback: use market prob as proxy (must be noted in source_trace)
    if market_home_prob is not None:
        return float(max(_MIN_PROB, min(_MAX_PROB, market_home_prob)))
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def simulate_strategy(
    strategy_name: str,
    rows: list[dict],
    date_start: str,
    date_end: str,
    edge_threshold: float = 0.0,
    kelly_cap: float = 0.05,
    min_sample_size: int = 30,
    ece_threshold: float = 0.12,
    require_positive_bss: bool = True,
) -> StrategySimulationResult:
    """
    Run a walk-forward strategy simulation on historical rows.

    Parameters
    ----------
    strategy_name : str
        Human-readable strategy identifier.
    rows : list[dict]
        Historical game records. Expected keys (best-effort):
            Date, Away, Home, Away Score, Home Score, Status,
            Away ML, Home ML, model_prob_home (optional)
    date_start : str
        YYYY-MM-DD inclusive start date for the simulation window.
    date_end : str
        YYYY-MM-DD inclusive end date for the simulation window.
    edge_threshold : float
        Minimum model edge (model_prob - market_prob) to count a bet.
    kelly_cap : float
        Maximum Kelly fraction per bet (default 0.05 = 5%).
    min_sample_size : int
        Minimum filtered rows for a PASS gate (default 30).
    ece_threshold : float
        Maximum ECE for a PASS gate (default 0.12).
    require_positive_bss : bool
        If True, negative BSS blocks the gate (default True).

    Returns
    -------
    StrategySimulationResult
    """
    simulation_id = f"sim-{strategy_name[:24]}-{uuid.uuid4().hex[:8]}"
    generated_at = datetime.now(tz=timezone.utc)
    gate_reasons: list[str] = []
    source_trace: dict = {
        "strategy_name": strategy_name,
        "date_start": date_start,
        "date_end": date_end,
        "edge_threshold": edge_threshold,
        "kelly_cap": kelly_cap,
        "input_rows_total": len(rows),
        "model_prob_source": "column:model_prob_home",
        "market_prob_source": "american_moneyline_pair_to_no_vig(Home ML, Away ML)",
    }

    # ── 1. No rows at all ────────────────────────────────────────────────────
    if not rows:
        gate_reasons.append("No input rows provided.")
        return StrategySimulationResult(
            simulation_id=simulation_id,
            strategy_name=strategy_name,
            date_start=date_start,
            date_end=date_end,
            sample_size=0,
            bet_count=0,
            skipped_count=0,
            gate_status="BLOCKED_NO_RESULTS",
            gate_reasons=gate_reasons,
            generated_at_utc=generated_at,
            source_trace=source_trace,
        )

    # ── 2. Parse each row ────────────────────────────────────────────────────
    model_probs: list[float] = []
    market_probs: list[float] = []
    outcomes: list[float] = []
    edges: list[float] = []
    kelly_fractions: list[float] = []
    bet_returns: list[float] = []   # per-bet return (relative to 1 unit staked)
    skipped_rows = 0
    missing_market_data = 0
    missing_model_data = 0
    model_prob_is_market_proxy = False
    # P5: probability source tracking
    real_model_row_count = 0
    market_proxy_row_count = 0
    missing_model_prob_count = 0
    # P6: calibrated_model tracking
    calibrated_model_row_count = 0
    # P9: repaired_model_candidate tracking
    repaired_model_row_count = 0
    repaired_home_bias_removed_count = 0
    repaired_feature_version_seen: str | None = None
    # P10: feature_candidate tracking
    feature_candidate_row_count = 0
    # P13: walk-forward ML candidate tracking
    walk_forward_ml_candidate_count = 0
    ml_model_types_seen: set[str] = set()
    ml_feature_policies_seen: set[str] = set()
    ml_features_used_seen: set[str] = set()
    independent_feature_version_seen: str | None = None
    independent_feature_coverage_seen: dict | None = None
    # P7: OOF calibration tracking
    oof_modes_seen: set[str] = set()
    oof_leakage_safe_count = 0

    for row in rows:
        market_home_prob, market_away_prob = _parse_row_market_probs(row)
        if market_home_prob is None:
            skipped_rows += 1
            missing_market_data += 1
            continue

        model_prob = _parse_row_model_prob(row, market_home_prob)
        if model_prob is None:
            skipped_rows += 1
            missing_model_data += 1
            continue

        # Check if we're using market prob as model proxy and track source
        row_has_model_col = (
            row.get("model_prob_home") is not None
            or row.get("model_prob") is not None
        )
        row_prob_source = str(row.get("probability_source") or "").lower()

        # P7: detect walk-forward OOF calibration via calibration_source_trace
        row_cal_trace = row.get("calibration_source_trace")
        row_cal_mode: str | None = None
        row_leakage_safe: bool = False
        if row_cal_trace:
            import json as _json
            if isinstance(row_cal_trace, str):
                try:
                    row_cal_trace = _json.loads(row_cal_trace)
                except Exception:
                    row_cal_trace = {}
            if isinstance(row_cal_trace, dict):
                row_cal_mode = str(row_cal_trace.get("calibration_mode") or "")
                row_leakage_safe = bool(row_cal_trace.get("leakage_safe", False))

        if not row_has_model_col:
            model_prob_is_market_proxy = True
            market_proxy_row_count += 1
        elif "proxy" in row_prob_source or "market" in row_prob_source:
            market_proxy_row_count += 1
        elif "feature_candidate" in row_prob_source:
            # P10: feature_candidate
            feature_candidate_row_count += 1
            ifv = str(row.get("independent_feature_version") or "")
            if ifv and independent_feature_version_seen is None:
                independent_feature_version_seen = ifv
        elif "walk_forward_ml_candidate" in row_prob_source:
            walk_forward_ml_candidate_count += 1
            mt = str(row.get("ml_model_type") or "")
            if mt:
                ml_model_types_seen.add(mt)
            pol = str(row.get("ml_feature_policy") or "")
            if pol:
                ml_feature_policies_seen.add(pol)
            feats = str(row.get("ml_features_used") or "")
            if feats:
                for f in feats.split(","):
                    fs = f.strip()
                    if fs:
                        ml_features_used_seen.add(fs)
        elif "repaired" in row_prob_source:
            # P9: repaired model candidate
            repaired_model_row_count += 1
            if row.get("repaired_home_bias_removed"):
                repaired_home_bias_removed_count += 1
            fv = str(row.get("repaired_feature_version") or "")
            if fv and repaired_feature_version_seen is None:
                repaired_feature_version_seen = fv
        elif "calibrated" in row_prob_source:
            # P6/P7: calibrated candidate — tracked separately; detect OOF sub-type
            calibrated_model_row_count += 1
            # P13: calibrated rows can still originate from walk-forward ML candidate
            if row.get("ml_model_type"):
                walk_forward_ml_candidate_count += 1
                mt = str(row.get("ml_model_type") or "")
                if mt:
                    ml_model_types_seen.add(mt)
                pol = str(row.get("ml_feature_policy") or "")
                if pol:
                    ml_feature_policies_seen.add(pol)
                feats = str(row.get("ml_features_used") or "")
                if feats:
                    for f in feats.split(","):
                        fs = f.strip()
                        if fs:
                            ml_features_used_seen.add(fs)
            if row_cal_mode and row_cal_mode not in oof_modes_seen:
                oof_modes_seen.add(row_cal_mode)
            if row_leakage_safe:
                oof_leakage_safe_count += 1
        else:
            real_model_row_count += 1

        outcome = _parse_row_outcome(row)
        if outcome is None:
            skipped_rows += 1
            continue

        model_probs.append(model_prob)
        market_probs.append(market_home_prob)
        outcomes.append(float(outcome))

        edge = model_prob - market_home_prob
        edges.append(edge)

        # Kelly fraction for a bet on home side
        home_ml_raw = row.get("Home ML") or row.get("home_ml")
        decimal_odds = 2.0  # fallback
        if home_ml_raw is not None:
            try:
                ml_f = float(str(home_ml_raw).replace("+", "").strip())
                decimal_odds = _american_to_decimal(ml_f)
            except Exception:
                pass

        kf = _kelly_fraction(edge, decimal_odds, kelly_cap) if edge > edge_threshold else 0.0
        kelly_fractions.append(kf)

        # Simulate bet return if edge > threshold
        if edge > edge_threshold and kf > 0:
            # Return = +kf*(decimal_odds-1) if win, -kf if loss
            ret = kf * (decimal_odds - 1) if outcome == 1 else -kf
            bet_returns.append(ret)

    sample_size = len(model_probs)
    bet_count = len(bet_returns)
    skipped_count = skipped_rows

    source_trace["rows_parsed"] = sample_size
    source_trace["rows_skipped"] = skipped_count
    source_trace["missing_market_data"] = missing_market_data
    source_trace["missing_model_data"] = missing_model_data

    # P5: probability source mode classification
    if walk_forward_ml_candidate_count > 0 and calibrated_model_row_count == 0 and real_model_row_count == 0 and market_proxy_row_count == 0:
        probability_source_mode = "walk_forward_ml_candidate"
    elif feature_candidate_row_count > 0 and calibrated_model_row_count == 0 and real_model_row_count == 0 and market_proxy_row_count == 0:
        probability_source_mode = "feature_candidate"
    elif repaired_model_row_count > 0 and calibrated_model_row_count == 0 and real_model_row_count == 0 and market_proxy_row_count == 0:
        probability_source_mode = "repaired_model_candidate"
    elif calibrated_model_row_count > 0 and real_model_row_count == 0 and market_proxy_row_count == 0:
        probability_source_mode = "calibrated_model"
    elif real_model_row_count > 0 and calibrated_model_row_count == 0 and market_proxy_row_count == 0:
        probability_source_mode = "real_model"
    elif (real_model_row_count > 0 or calibrated_model_row_count > 0 or repaired_model_row_count > 0 or feature_candidate_row_count > 0) and market_proxy_row_count > 0:
        probability_source_mode = "mixed"
    elif market_proxy_row_count > 0:
        probability_source_mode = "market_proxy"
    else:
        probability_source_mode = "unknown"

    source_trace["probability_source_mode"] = probability_source_mode
    source_trace["real_model_count"] = real_model_row_count
    source_trace["calibrated_model_count"] = calibrated_model_row_count
    source_trace["market_proxy_count"] = market_proxy_row_count
    source_trace["missing_model_prob_count"] = missing_model_data
    if walk_forward_ml_candidate_count > 0:
        source_trace["walk_forward_ml_candidate_count"] = walk_forward_ml_candidate_count
        source_trace["ml_model_type"] = sorted(ml_model_types_seen)
        source_trace["ml_feature_policy"] = sorted(ml_feature_policies_seen)
        source_trace["ml_features_used"] = sorted(ml_features_used_seen)
        source_trace["leakage_safe"] = True
        source_trace["ml_candidate_note"] = (
            "P13 walk-forward ML candidate probabilities; "
            "paper-only and still requires positive BSS gate to pass"
        )
    # P10: feature_candidate tracking
    if feature_candidate_row_count > 0:
        source_trace["feature_candidate_count"] = feature_candidate_row_count
        if independent_feature_version_seen:
            source_trace["independent_feature_version"] = independent_feature_version_seen
        source_trace["leakage_safe"] = True
        source_trace["feature_candidate_note"] = (
            "P10 feature_candidate: independent baseball features (win_rate/rest/bullpen/starter_era/weather); "
            "paper-only, requires positive OOF BSS before promotion"
        )
    # P9: repaired model candidate tracking
    if repaired_model_row_count > 0:
        source_trace["repaired_model_candidate_count"] = repaired_model_row_count
        source_trace["repaired_home_bias_removed_count"] = repaired_home_bias_removed_count
        if repaired_feature_version_seen:
            source_trace["repaired_feature_version"] = repaired_feature_version_seen
        source_trace["repaired_model_note"] = (
            "P9 repaired_model_candidate: home_bias removed + independent features added; "
            "paper-only candidate, requires positive BSS before promotion"
        )

    # P6: if calibrated_model is used, emit appropriate calibration warning
    if calibrated_model_row_count > 0:
        # P7: detect OOF vs in-sample
        is_oof = "walk_forward_oof" in oof_modes_seen
        is_leakage_safe = oof_leakage_safe_count > 0 and oof_leakage_safe_count >= calibrated_model_row_count

        if is_oof and is_leakage_safe:
            cal_mode = "walk_forward_oof"
            source_trace["calibration_mode"] = cal_mode
            source_trace["oof_calibration_count"] = calibrated_model_row_count
            source_trace["leakage_safe"] = True
            source_trace["calibration_warning"] = (
                "walk-forward OOF calibration candidate; production still requires human approval"
            )
            source_trace["deployability_note"] = (
                "OOF calibration with leakage_safe=True; eligible for paper-only candidate evaluation"
            )
        else:
            cal_mode = list(oof_modes_seen)[0] if oof_modes_seen else "in_sample"
            source_trace["calibration_mode"] = cal_mode
            source_trace["oof_calibration_count"] = calibrated_model_row_count
            source_trace["leakage_safe"] = is_leakage_safe
            source_trace["calibration_warning"] = (
                "in-sample calibration candidate; not production deployable unless OOF validated"
            )
            source_trace["deployability_note"] = (
                "In-sample or non-leakage-safe calibration detected; gate cannot PASS"
            )
            if not is_leakage_safe:
                gate_reasons.append(
                    "WARNING: calibration source_trace.leakage_safe is False or missing — "
                    "gate cannot PASS for this calibration mode."
                )

    if model_prob_is_market_proxy:
        source_trace["model_prob_source"] = "market_implied_prob_proxy (no model_prob_home column)"
        gate_reasons.append(
            "WARNING: model_prob_home column not found — using market implied prob as proxy. "
            "BSS will be ~0 by construction. Do not interpret as model skill."
        )

    # ── 3. No usable rows ────────────────────────────────────────────────────
    if sample_size == 0:
        if missing_market_data > 0:
            gate_status = "BLOCKED_NO_MARKET_DATA"
            gate_reasons.append(
                f"All {skipped_count} rows missing market odds (Home ML / Away ML)."
            )
        else:
            gate_status = "BLOCKED_NO_RESULTS"
            gate_reasons.append(
                f"No rows with usable model prob, market prob, and final result. "
                f"Skipped: {skipped_count}."
            )
        return StrategySimulationResult(
            simulation_id=simulation_id,
            strategy_name=strategy_name,
            date_start=date_start,
            date_end=date_end,
            sample_size=0,
            bet_count=0,
            skipped_count=skipped_count,
            gate_status=gate_status,
            gate_reasons=gate_reasons,
            generated_at_utc=generated_at,
            source_trace=source_trace,
        )

    # ── 4. Compute metrics ───────────────────────────────────────────────────

    # Brier
    brier_model_val: float | None = None
    brier_market_val: float | None = None
    bss_val: float | None = None
    ece_val: float | None = None

    try:
        brier_model_val = round(brier_score(model_probs, outcomes), 6)
        brier_market_val = round(brier_score(market_probs, outcomes), 6)
        bss_val_raw = brier_skill_score(brier_model_val, brier_market_val)
        bss_val = round(bss_val_raw, 6) if bss_val_raw is not None else None
    except Exception as exc:
        gate_reasons.append(f"Brier computation failed: {exc}")
        source_trace["brier_error"] = str(exc)

    try:
        ece_result = expected_calibration_error(model_probs, outcomes)
        ece_val = round(ece_result["ece"], 6)
    except Exception as exc:
        gate_reasons.append(f"ECE computation failed: {exc}")
        source_trace["ece_error"] = str(exc)

    avg_model_prob = round(sum(model_probs) / len(model_probs), 6)
    avg_market_prob = round(sum(market_probs) / len(market_probs), 6)
    avg_edge = round(sum(edges) / len(edges), 6) if edges else None
    avg_kelly = round(sum(kelly_fractions) / len(kelly_fractions), 6) if kelly_fractions else None

    # ROI, Sharpe, Max Drawdown (from bet_returns)
    roi_pct: float | None = None
    sharpe_proxy: float | None = None
    max_drawdown_pct: float | None = None

    if bet_returns:
        total_staked = sum(abs(r) for r in bet_returns if r < 0) + sum(
            kf for kf in kelly_fractions if kf > 0
        )
        # ROI = sum(profit) / total_staked expressed as percent
        profit = sum(bet_returns)
        # Simpler: ROI = mean(return per bet) / mean(kelly stake) * 100
        mean_ret = sum(bet_returns) / len(bet_returns)
        mean_stake = sum(kf for kf in kelly_fractions if kf > 0) / bet_count if bet_count else 1.0
        roi_pct = round((mean_ret / mean_stake) * 100.0, 4) if mean_stake > 0 else None

        # Sharpe proxy = mean / std of returns (annualised proxy)
        n = len(bet_returns)
        if n > 1:
            mean_r = sum(bet_returns) / n
            variance = sum((r - mean_r) ** 2 for r in bet_returns) / (n - 1)
            std_r = math.sqrt(variance)
            sharpe_proxy = round(mean_r / std_r, 4) if std_r > 0 else None
        else:
            sharpe_proxy = None

        # Max drawdown proxy (rolling peak on cumulative bankroll delta)
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in bet_returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        max_drawdown_pct = round(max_dd * 100.0, 4)
    else:
        gate_reasons.append(
            f"No bets placed with edge_threshold={edge_threshold:.3f}. "
            "ROI, Sharpe, and max drawdown cannot be computed."
        )
        source_trace["roi_note"] = (
            f"No bets qualified (edge_threshold={edge_threshold:.3f}). "
            "ROI not available."
        )

    # ── 5. Determine gate status ─────────────────────────────────────────────
    gate_status: str = "PASS"

    if sample_size < min_sample_size:
        gate_status = "BLOCKED_LOW_SAMPLE"
        gate_reasons.append(
            f"sample_size={sample_size} < min_sample_size={min_sample_size}. "
            "Too few records for reliable evaluation."
        )

    elif missing_market_data == sample_size + missing_market_data:
        gate_status = "BLOCKED_NO_MARKET_DATA"
        gate_reasons.append("All rows missing market odds — cannot compute BSS baseline.")

    elif bss_val is not None and bss_val < 0 and require_positive_bss:
        gate_status = "BLOCKED_NEGATIVE_BSS"
        gate_reasons.append(
            f"Brier Skill Score = {bss_val:.4f} < 0. "
            "Model underperforms market baseline. "
            "require_positive_bss=True blocks this strategy."
        )

    elif ece_val is not None and ece_val > ece_threshold:
        gate_status = "BLOCKED_HIGH_ECE"
        gate_reasons.append(
            f"ECE = {ece_val:.4f} > ece_threshold={ece_threshold:.4f}. "
            "Model is poorly calibrated."
        )

    # Always paper-only — even PASS strategies remain paper-only
    if gate_status == "PASS":
        gate_reasons.append(
            "Gate: PASS — paper-only simulation. "
            "Production enablement requires separate governance clearance."
        )

    source_trace["gate_status"] = gate_status
    source_trace["sample_size"] = sample_size
    source_trace["bet_count"] = bet_count

    return StrategySimulationResult(
        simulation_id=simulation_id,
        strategy_name=strategy_name,
        date_start=date_start,
        date_end=date_end,
        sample_size=sample_size,
        bet_count=bet_count,
        skipped_count=skipped_count,
        avg_model_prob=avg_model_prob,
        avg_market_prob=avg_market_prob,
        brier_model=brier_model_val,
        brier_market=brier_market_val,
        brier_skill_score=bss_val,
        ece=ece_val,
        roi_pct=roi_pct,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_proxy=sharpe_proxy,
        avg_edge_pct=avg_edge,
        avg_kelly_fraction=avg_kelly,
        gate_status=gate_status,
        gate_reasons=gate_reasons,
        generated_at_utc=generated_at,
        source_trace=source_trace,
    )
