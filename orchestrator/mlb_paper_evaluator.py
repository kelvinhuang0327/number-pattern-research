"""MLB Paper Recommendation Quality Evaluator.

Processes paper recommendation log files and matches them to ground truth game outcomes.
Calculates key metrics (evaluated_count, matched_count, hit_rate, Brier score, ROI)
and outputs structured, JSON-serializable summaries to evaluate model/strategy performance.

Safety Invariants:
  - Strict paper-only / offline execution.
  - No database writes.
  - No live API calls.
  - No real betting stake logic.
"""

from __future__ import annotations

import datetime
import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wbc_backend.recommendation.learning_outcome_join import (
    RESULT_TIMESTAMP_FIELDS,
    evaluate_learning_outcome_join,
)


# Minimum sample count for a strategy to be considered statistically meaningful.
# Strategies with fewer samples are marked DATA_LIMITED in the leaderboard.
SMALL_SAMPLE_THRESHOLD: int = 10


# P201: per-strategy learning-evidence status labels.
#   LEARNING_ELIGIBLE   — has >= threshold game-specific, non-fallback rows.
#   DATA_LIMITED        — has some eligible rows but below threshold.
#   LEARNING_INELIGIBLE — zero learning-eligible rows (only fallback/neutral/proxy).
#   UNKNOWN             — eligibility could not be determined (legacy direct call).
LEARNING_STATUS_ELIGIBLE: str = "LEARNING_ELIGIBLE"
LEARNING_STATUS_DATA_LIMITED: str = "DATA_LIMITED"
LEARNING_STATUS_INELIGIBLE: str = "LEARNING_INELIGIBLE"
LEARNING_STATUS_UNKNOWN: str = "UNKNOWN"


@dataclass
class PaperEvaluationMetrics:
    evaluated_count: int = 0
    matched_outcome_count: int = 0
    missing_outcome_count: int = 0
    coverage_rate: float = 0.0
    hit_rate: float = 0.0
    brier_score: float | None = None
    actual_paper_pnl: float = 0.0
    actual_paper_stake: float = 0.0
    actual_paper_roi: float = 0.0
    shadow_unit_pnl: float = 0.0
    shadow_unit_stake: float = 0.0
    shadow_unit_roi: float = 0.0
    binomial_p_value: float | None = None
    gate_segmentation: dict[str, Any] = field(default_factory=dict)
    confidence_segmentation: dict[str, Any] = field(default_factory=dict)
    # P180: strategy segmentation and deterministic leaderboard
    strategy_segmentation: dict[str, Any] = field(default_factory=dict)
    strategy_leaderboard: list[dict] = field(default_factory=list)
    # P201: learning-eligibility enforcement (counted over matched/scored rows).
    # Rows remain scored for auditability, but learning-ineligible rows
    # (neutral_fixed_prior / fallback / missing provenance) are counted
    # separately and must never be treated as strategy-improvement evidence.
    learning_eligible_count: int = 0
    learning_ineligible_count: int = 0
    learning_eligibility_segmentation: dict[str, Any] = field(default_factory=dict)


def calculate_binomial_p_value(hits: int, trials: int, p_null: float = 0.5) -> float:
    """Calculate the one-sided binomial p-value (probability of getting >= hits under H0)."""
    if trials == 0:
        return 1.0
    if hits > trials:
        return 0.0
    pval = 0.0
    for i in range(hits, trials + 1):
        try:
            comb = math.comb(trials, i)
            pval += comb * (p_null ** i) * ((1.0 - p_null) ** (trials - i))
        except (ValueError, OverflowError):
            continue
    return min(1.0, max(0.0, pval))


def _p205b_guard_applies(rec: dict, outcome: dict | None) -> bool:
    source_trace = rec.get("source_trace")
    if isinstance(source_trace, dict) and "provenance_contract_version" in source_trace:
        return True
    if outcome and any(outcome.get(field) for field in RESULT_TIMESTAMP_FIELDS):
        return True
    return False


def _row_learning_eligibility(
    rec: dict,
    outcome: dict | None = None,
    outcomes: list[dict] | None = None,
) -> tuple[bool, str | None]:
    """Read P200 learning-eligibility provenance from a recommendation row.

    Conservative P201 contract: a row is learning-eligible ONLY when its
    ``source_trace`` explicitly sets ``learning_eligible=True``.  Rows that are
    missing ``source_trace``, have a malformed ``source_trace``, omit the
    ``learning_eligible`` flag, or set it falsey (the current
    ``neutral_fixed_prior`` / fallback path) are treated as NOT learning-eligible.

    Such rows may still be scored for auditability, but they must never be
    silently counted as strategy-improvement / promotion evidence.

    Returns ``(is_eligible, block_reason)``.  ``block_reason`` is ``None`` only
    when the row is eligible.
    """
    if outcome is not None and _p205b_guard_applies(rec, outcome):
        decision = evaluate_learning_outcome_join(rec, outcomes or [outcome])
        return decision.learning_eligible, decision.block_reason

    source_trace = rec.get("source_trace")
    if not isinstance(source_trace, dict):
        # Legacy / pre-P200 rows have no provenance — classify conservatively.
        return False, "missing_source_trace_provenance"
    eligible = source_trace.get("learning_eligible")
    if eligible is True:
        return True, None
    if eligible is False:
        return False, source_trace.get("learning_block_reason") or "learning_eligible=false"
    # Flag absent or non-boolean → conservative (do not overclaim).
    return False, "learning_eligible_not_declared"


def build_strategy_leaderboard(
    strategy_segmentation: dict[str, Any],
    threshold: int = SMALL_SAMPLE_THRESHOLD,
    strategy_learning: dict[str, dict[str, int]] | None = None,
) -> list[dict]:
    """Build a deterministic strategy performance leaderboard.

    Each entry contains:
      - strategy_id
      - sample_count
      - hit_rate
      - brier_score
      - shadow_unit_roi
      - binomial_p_value
      - data_limited (True when sample_count < threshold)
      - rank (1-indexed)
      - learning_eligible_count / learning_ineligible_count (P201; None when
        eligibility was not supplied)
      - learning_status (P201; one of LEARNING_ELIGIBLE / DATA_LIMITED /
        LEARNING_INELIGIBLE / UNKNOWN)
      - promotable_learning_evidence (P201; True only when learning_status is
        LEARNING_ELIGIBLE)

    Ranking rules applied in order:
      1. hit_rate descending (higher is better)
      2. shadow_unit_roi descending (higher is better)
      3. strategy_id ascending (alphabetic; deterministic tie-breaker)

    Strategies below ``threshold`` are marked ``data_limited=True`` but are
    still ranked by the same rules.

    P201: when ``strategy_learning`` is supplied (mapping strategy_id →
    {"eligible": n, "ineligible": m}), each entry is classified for learning
    evidence.  A strategy with zero eligible rows is ``LEARNING_INELIGIBLE`` and
    is never ``promotable_learning_evidence``, regardless of its hit_rate.  When
    ``strategy_learning`` is omitted (legacy direct callers), eligibility is
    ``UNKNOWN`` and the entry is conservatively non-promotable.

    Safety: pure function — no DB writes, no live calls, no weight changes.
    """
    entries = []
    for sid, seg in strategy_segmentation.items():
        count = seg.get("count", 0)
        correct = seg.get("correct_count", 0)
        elig_n, inelig_n, learning_status, promotable = _classify_strategy_learning(
            sid, strategy_learning, threshold
        )
        entries.append(
            {
                "strategy_id": sid,
                "sample_count": count,
                "hit_rate": seg.get("hit_rate", 0.0),
                "brier_score": seg.get("brier_score"),
                "shadow_unit_roi": seg.get("shadow_unit_roi", 0.0),
                "binomial_p_value": round(
                    calculate_binomial_p_value(correct, count), 6
                ),
                "data_limited": count < threshold,
                "learning_eligible_count": elig_n,
                "learning_ineligible_count": inelig_n,
                "learning_status": learning_status,
                "promotable_learning_evidence": promotable,
            }
        )

    # Deterministic sort: hit_rate desc, shadow_unit_roi desc, strategy_id asc
    entries.sort(
        key=lambda e: (-e["hit_rate"], -e["shadow_unit_roi"], e["strategy_id"])
    )

    for i, entry in enumerate(entries, start=1):
        entry["rank"] = i

    return entries


def _classify_strategy_learning(
    sid: str,
    strategy_learning: dict[str, dict[str, int]] | None,
    threshold: int,
) -> tuple[int | None, int | None, str, bool]:
    """Classify one strategy's learning-evidence status (P201).

    Returns ``(eligible_count, ineligible_count, learning_status, promotable)``.
    """
    learning = (strategy_learning or {}).get(sid)
    if learning is None:
        # Eligibility was not supplied — do not overclaim.
        return None, None, LEARNING_STATUS_UNKNOWN, False
    elig_n = int(learning.get("eligible", 0))
    inelig_n = int(learning.get("ineligible", 0))
    if elig_n <= 0:
        learning_status = LEARNING_STATUS_INELIGIBLE
    elif elig_n < threshold:
        learning_status = LEARNING_STATUS_DATA_LIMITED
    else:
        learning_status = LEARNING_STATUS_ELIGIBLE
    return elig_n, inelig_n, learning_status, learning_status == LEARNING_STATUS_ELIGIBLE


def _extract_pk(game_id: str) -> str:
    """Robustly extract the unique game PK suffix from a game ID string."""
    if not game_id:
        return ""
    if "_" in game_id:
        return game_id.split("_")[-1]
    if "-" in game_id:
        return game_id.split("-")[-1]
    return game_id


def load_paper_recommendations(paper_dir: str | Path) -> list[dict]:
    """Recursively load paper recommendations from JSONL files in the directory."""
    recommendations: list[dict] = []
    path = Path(paper_dir)
    if not path.exists():
        return recommendations

    for file_path in path.glob("**/*.jsonl"):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict):
                            recommendations.append(data)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return recommendations


def load_outcome_records(outcome_path: str | Path) -> list[dict]:
    """Load outcome records from an outcome-attached JSONL file."""
    outcomes: list[dict] = []
    path = Path(outcome_path)
    if not path.exists():
        return outcomes

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        outcomes.append(data)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return outcomes


def evaluate_paper_recommendations(
    recommendations: list[dict],
    outcomes: list[dict],
) -> PaperEvaluationMetrics:
    """Evaluate paper recommendations against ground-truth outcomes."""
    metrics = PaperEvaluationMetrics()
    metrics.evaluated_count = len(recommendations)
    if not recommendations:
        return metrics

    # Index outcomes by unique game PK suffix
    outcome_index: dict[str, dict] = {}
    for o in outcomes:
        game_id = o.get("game_id", "")
        pk = _extract_pk(game_id)
        if pk:
            outcome_index[pk] = o

    matched_recs: list[tuple[dict, dict]] = []
    for r in recommendations:
        r_id = r.get("game_id", "")
        pk = _extract_pk(r_id)
        if pk in outcome_index:
            outcome = outcome_index[pk]
            # Match is valid if outcome is available and winner is declared
            if outcome.get("outcome_available") and outcome.get("actual_winner") in {"home", "away"}:
                matched_recs.append((r, outcome))
                metrics.matched_outcome_count += 1
            else:
                metrics.missing_outcome_count += 1
        else:
            metrics.missing_outcome_count += 1

    metrics.coverage_rate = (
        round(metrics.matched_outcome_count / metrics.evaluated_count, 4)
        if metrics.evaluated_count > 0
        else 0.0
    )

    if not matched_recs:
        return metrics

    # Standard calculations
    correct_count = 0
    brier_sum = 0.0
    brier_count = 0

    # PnL tracking
    actual_pnl = 0.0
    actual_stake = 0.0
    shadow_pnl = 0.0

    # Segmentation containers
    gate_data: dict[str, list[tuple[dict, dict]]] = {}
    conf_data: dict[str, list[tuple[dict, dict]]] = {
        "low (0.50-0.55)": [],
        "mid (0.55-0.65)": [],
        "high (0.65-1.00)": [],
    }

    # P201: learning-eligibility accumulators (over matched/scored rows).
    learning_eligible_count = 0
    learning_ineligible_count = 0
    block_reason_counts: dict[str, int] = {}
    strategy_learning: dict[str, dict[str, int]] = {}

    for r, o in matched_recs:
        side = r.get("tsl_side", "").lower()
        winner = o.get("actual_winner", "").lower()
        is_hit = (side == winner)

        if is_hit:
            correct_count += 1

        # P201: classify learning eligibility from P200 source_trace provenance.
        sid_for_learning = r.get("strategy_id") or "UNATTRIBUTED"
        learn_bucket = strategy_learning.setdefault(
            sid_for_learning, {"eligible": 0, "ineligible": 0}
        )
        is_learning_eligible, block_reason = _row_learning_eligibility(
            r,
            outcome=o,
            outcomes=outcomes,
        )
        if is_learning_eligible:
            learning_eligible_count += 1
            learn_bucket["eligible"] += 1
        else:
            learning_ineligible_count += 1
            learn_bucket["ineligible"] += 1
            if block_reason:
                block_reason_counts[block_reason] = (
                    block_reason_counts.get(block_reason, 0) + 1
                )

        # Brier Score calculation: using model_prob_home
        prob_home = r.get("model_prob_home")
        if prob_home is not None:
            actual_home_win = 1.0 if winner == "home" else 0.0
            brier_sum += (float(prob_home) - actual_home_win) ** 2
            brier_count += 1

        # Simulated actual paper PnL
        stake = r.get("stake_units_paper", 0.0)
        odds = r.get("tsl_decimal_odds", 1.0)
        actual_stake += stake
        if is_hit:
            actual_pnl += stake * (odds - 1.0)
            shadow_pnl += (odds - 1.0)
        else:
            actual_pnl -= stake
            shadow_pnl -= 1.0

        # Segmentation - Gate Status
        gate_status = r.get("gate_status", "UNKNOWN")
        gate_data.setdefault(gate_status, []).append((r, o))

        # Segmentation - Confidence bands
        max_prob = max(float(r.get("model_prob_home", 0.5)), float(r.get("model_prob_away", 0.5)))
        if max_prob < 0.55:
            conf_key = "low (0.50-0.55)"
        elif max_prob < 0.65:
            conf_key = "mid (0.55-0.65)"
        else:
            conf_key = "high (0.65-1.00)"
        conf_data[conf_key].append((r, o))

    metrics.hit_rate = round(correct_count / len(matched_recs), 4)
    metrics.binomial_p_value = round(calculate_binomial_p_value(correct_count, len(matched_recs)), 6)

    if brier_count > 0:
        metrics.brier_score = round(brier_sum / brier_count, 6)

    metrics.actual_paper_pnl = round(actual_pnl, 4)
    metrics.actual_paper_stake = round(actual_stake, 4)
    metrics.actual_paper_roi = (
        round(actual_pnl / actual_stake, 4) if actual_stake > 0.0 else 0.0
    )

    metrics.shadow_unit_pnl = round(shadow_pnl, 4)
    metrics.shadow_unit_stake = float(len(matched_recs))
    metrics.shadow_unit_roi = round(shadow_pnl / len(matched_recs), 4)

    # Segment calculations
    for gate_status, items in gate_data.items():
        metrics.gate_segmentation[gate_status] = _evaluate_subset(items)

    for conf_band, items in conf_data.items():
        metrics.confidence_segmentation[conf_band] = _evaluate_subset(items)

    # P180: strategy segmentation — keyed by explicit strategy_id only.
    # strategy_id is read directly from the recommendation row; it MUST NOT be
    # inferred from filenames, model_ensemble_version, or indirect metadata.
    # Rows missing strategy_id (or with None/empty) are bucketed as UNATTRIBUTED.
    strategy_data: dict[str, list[tuple[dict, dict]]] = {}
    for r, o in matched_recs:
        sid = r.get("strategy_id") or "UNATTRIBUTED"
        strategy_data.setdefault(sid, []).append((r, o))

    for sid, items in strategy_data.items():
        metrics.strategy_segmentation[sid] = _evaluate_subset(items)

    # P201: surface learning-eligibility counts and pass per-strategy
    # eligibility into the leaderboard so fallback/neutral/proxy-only strategies
    # cannot be classified as promotable learning evidence.
    metrics.learning_eligible_count = learning_eligible_count
    metrics.learning_ineligible_count = learning_ineligible_count
    metrics.learning_eligibility_segmentation = {
        "eligible_count": learning_eligible_count,
        "ineligible_count": learning_ineligible_count,
        "block_reasons": block_reason_counts,
    }

    metrics.strategy_leaderboard = build_strategy_leaderboard(
        metrics.strategy_segmentation, strategy_learning=strategy_learning
    )

    return metrics


def _evaluate_subset(items: list[tuple[dict, dict]]) -> dict[str, Any]:
    """Helper to evaluate a specific subset of matched recommendations."""
    if not items:
        return {
            "count": 0,
            "correct_count": 0,
            "hit_rate": 0.0,
            "brier_score": None,
            "actual_paper_roi": 0.0,
            "shadow_unit_roi": 0.0,
        }

    correct = 0
    brier_sum = 0.0
    brier_count = 0
    actual_pnl = 0.0
    actual_stake = 0.0
    shadow_pnl = 0.0

    for r, o in items:
        side = r.get("tsl_side", "").lower()
        winner = o.get("actual_winner", "").lower()
        is_hit = (side == winner)

        if is_hit:
            correct += 1

        prob_home = r.get("model_prob_home")
        if prob_home is not None:
            actual_home_win = 1.0 if winner == "home" else 0.0
            brier_sum += (float(prob_home) - actual_home_win) ** 2
            brier_count += 1

        stake = r.get("stake_units_paper", 0.0)
        odds = r.get("tsl_decimal_odds", 1.0)
        actual_stake += stake
        if is_hit:
            actual_pnl += stake * (odds - 1.0)
            shadow_pnl += (odds - 1.0)
        else:
            actual_pnl -= stake
            shadow_pnl -= 1.0

    return {
        "count": len(items),
        "correct_count": correct,
        "hit_rate": round(correct / len(items), 4),
        "brier_score": round(brier_sum / brier_count, 6) if brier_count > 0 else None,
        "actual_paper_roi": round(actual_pnl / actual_stake, 4) if actual_stake > 0.0 else 0.0,
        "shadow_unit_roi": round(shadow_pnl / len(items), 4),
    }


def execute_evaluation(
    paper_dir: str | Path,
    outcome_path: str | Path,
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute evaluation and optionally write structured JSON summary file."""
    recs = load_paper_recommendations(paper_dir)
    outcomes = load_outcome_records(outcome_path)
    metrics = evaluate_paper_recommendations(recs, outcomes)

    result = {
        "evaluator_version": "p180_evaluator_v2",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metrics": asdict(metrics),
    }

    if summary_output_path:
        out_p = Path(summary_output_path)
        try:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except OSError:
            pass

    return result


def discover_paper_dates(paper_root: str | Path) -> list[str]:
    """Return sorted list of YYYY-MM-DD date strings found under paper_root."""
    root = Path(paper_root)
    if not root.exists():
        return []
    dates: list[str] = []
    for entry in root.iterdir():
        if entry.is_dir() and len(entry.name) == 10 and entry.name.count("-") == 2:
            dates.append(entry.name)
    return sorted(dates)


def execute_batch_evaluation(
    paper_root: str | Path,
    outcome_path: str | Path,
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate all date folders under paper_root and return per-date + aggregate summary."""
    dates = discover_paper_dates(paper_root)
    outcomes = load_outcome_records(outcome_path)

    per_date: dict[str, Any] = {}
    all_recs: list[dict] = []

    for date_str in dates:
        date_dir = Path(paper_root) / date_str
        recs = load_paper_recommendations(date_dir)
        metrics = evaluate_paper_recommendations(recs, outcomes)
        per_date[date_str] = {
            "evaluated_count": metrics.evaluated_count,
            "matched_outcome_count": metrics.matched_outcome_count,
            "missing_outcome_count": metrics.missing_outcome_count,
            "coverage_rate": metrics.coverage_rate,
            "hit_rate": metrics.hit_rate,
            "brier_score": metrics.brier_score,
            "actual_paper_roi": metrics.actual_paper_roi,
            "shadow_unit_roi": metrics.shadow_unit_roi,
            "binomial_p_value": metrics.binomial_p_value,
            # P201: learning-eligibility counts per date.
            "learning_eligible_count": metrics.learning_eligible_count,
            "learning_ineligible_count": metrics.learning_ineligible_count,
        }
        all_recs.extend(recs)

    aggregate_metrics = evaluate_paper_recommendations(all_recs, outcomes)

    result: dict[str, Any] = {
        "evaluator_version": "p180_evaluator_v2",
        "mode": "batch",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dates_found": dates,
        "dates_evaluated": len(dates),
        "total_rows": len(all_recs),
        "per_date": per_date,
        "aggregate": asdict(aggregate_metrics),
    }

    if summary_output_path:
        out_p = Path(summary_output_path)
        try:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except OSError:
            pass

    return result
