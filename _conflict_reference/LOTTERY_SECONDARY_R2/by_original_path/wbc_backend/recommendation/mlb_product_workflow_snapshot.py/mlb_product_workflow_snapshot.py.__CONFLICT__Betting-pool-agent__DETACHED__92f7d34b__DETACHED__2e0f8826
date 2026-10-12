"""Local MLB prediction -> paper-market -> result workflow snapshot.

This module turns the existing local retrain scorecard into a product-facing
workflow artifact:

1. retrain/evaluate local historical models,
2. choose the current best local model,
3. connect its holdout predictions to Moneyline odds,
4. compute paper-only EV/Kelly/result metrics, and
5. show the latest local 2026 prediction snapshot.

It does not fetch live data, write a database, mutate production state, or
create real betting advice.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import _p275_prospective_availability_consumer_gate as p275
from wbc_backend.recommendation.local_retrain_scorecard import (
    american_to_prob,
    run_scorecard,
)


SCOPE = "LOCAL_PAPER_WORKFLOW_SNAPSHOT"
DISCLAIMER = (
    "Corrected 2025 date-batched local retraining/evaluation and a separate existing "
    "P84-B 2026 prediction snapshot, plus an explicitly separate retrospective P278-A "
    "paper-only corrected-model shadow and a P279-A outcome-free divergence baseline "
    "when supplied. The P279-A comparison measures prediction divergence only, uses no "
    "outcomes or odds, and does not establish model performance or superiority. "
    "Historical odds lack verified "
    "pregame timestamps, so "
    "Moneyline hit rate, EV, and ROI are diagnostic/descriptive only and do not establish "
    "a verified betting edge. The corrected retrained model did not generate or replace the "
    "P84-B snapshot, and the P278-A shadow is not a live or pregame publication."
)
REPO_ROOT = Path(__file__).resolve().parents[2]
CORRECTED_2025_RESULT_CONTEXT = "CORRECTED_2025_LOCAL_DATE_BATCHED_RETRAIN_EVALUATION"
EXISTING_2026_SNAPSHOT_CONTEXT = "EXISTING_2026_PREDICTION_SNAPSHOT"
EXPECTED_2026_SOURCE_VERSION = "p84b_diagnostic_baseline_v1"
EXPECTED_CORRECTED_SHADOW_VERSION = "p278a_corrected_moneyline_shadow_v1"
ODDS_TIMING_STATUS = "HISTORICAL_ODDS_PREGAME_TIMESTAMP_UNVERIFIED"
P274_PUBLICATION_ROOT = (
    REPO_ROOT / "data/mlb_2026/derived/p274_prospective_result_availability_index_v1"
)
DEFAULT_P274_INDEX_PATH = P274_PUBLICATION_ROOT / "index.json"
DEFAULT_P274_MANIFEST_PATH = P274_PUBLICATION_ROOT / "SHA256SUMS"
DEFAULT_MONEYLINE_DIVERGENCE_SUMMARY_PATH = (
    REPO_ROOT / "report/mlb_2026_moneyline_shadow_divergence_summary.json"
)
P274_COVERAGE_LIMITATION = (
    "P274 currently has only one prospective record and does not establish "
    "season-wide point-in-time coverage or replay readiness."
)

DEFAULT_MONEYLINE_MIN_EV = 0.01
DEFAULT_MONEYLINE_MIN_EDGE = 0.015
DEFAULT_KELLY_FRACTION = 0.25
DEFAULT_KELLY_CAP = 0.015


def _portable_input_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _portable_output_path(path: Path) -> str:
    """Keep report references stable across repo and /tmp reproducibility runs."""
    return str(Path(path.parent.name) / path.name)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_float(value: Any) -> float | None:
    try:
        f = float(str(value).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def american_to_decimal(value: Any) -> float | None:
    """Convert American odds to decimal odds."""
    v = _safe_float(value)
    if v is None or v == 0:
        return None
    if v > 0:
        return round(1.0 + v / 100.0, 6)
    return round(1.0 + 100.0 / abs(v), 6)


def calculate_ev_kelly(
    *,
    probability: float,
    decimal_odds: float,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    kelly_cap: float = DEFAULT_KELLY_CAP,
) -> dict[str, float]:
    """Return EV per staked unit and capped fractional Kelly."""
    probability = max(0.0, min(1.0, probability))
    if decimal_odds <= 1.0:
        return {
            "expected_value_per_unit": 0.0,
            "full_kelly_fraction": 0.0,
            "used_kelly_fraction": 0.0,
        }

    b = decimal_odds - 1.0
    ev = probability * decimal_odds - 1.0
    full_kelly = ev / b
    used_kelly = max(0.0, min(kelly_cap, full_kelly * kelly_fraction))
    return {
        "expected_value_per_unit": round(ev, 6),
        "full_kelly_fraction": round(max(0.0, full_kelly), 6),
        "used_kelly_fraction": round(used_kelly, 6),
    }


def _game_base_key(date_s: str, away: str, home: str) -> str:
    return "|".join(part.strip().lower() for part in (date_s, away, home))


def _game_occurrence_key(base_key: str, occurrence: int) -> str:
    return f"{base_key}#{occurrence}"


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _home_win_from_odds_row(row: dict[str, Any]) -> int | None:
    try:
        home_score = int(float(_first(row, "Home Score", "home_score")))
        away_score = int(float(_first(row, "Away Score", "away_score")))
    except (TypeError, ValueError):
        return None
    if home_score == away_score:
        return None
    return int(home_score > away_score)


def _odds_row_sort_key(row: dict[str, str]) -> tuple:
    home_prob, _ = _devig_home_away_probs(row.get("Home ML"), row.get("Away ML"))
    return (
        row["_sort_date"],
        _first(row, "Home", "home_team"),
        _first(row, "Away", "away_team"),
        int(row["_home_win"]),
        home_prob is None,
        0.0 if home_prob is None else home_prob,
    )


def _load_final_odds_rows(eval_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with eval_path.open(newline="", encoding="utf-8") as fh:
        for line_number, row in enumerate(csv.DictReader(fh), start=2):
            date_s = _first(row, "Date", "date")
            home = _first(row, "Home", "home_team")
            away = _first(row, "Away", "away_team")
            status = _first(row, "Status", "status") or "Final"
            if status.lower() != "final":
                continue
            if not date_s or not home or not away or home.casefold() == away.casefold():
                raise ValueError(
                    f"malformed game identifier at {eval_path}:{line_number}: "
                    f"date={date_s!r}, away={away!r}, home={home!r}"
                )
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(
                    f"malformed game date at {eval_path}:{line_number}: {date_s!r}"
                ) from exc
            home_win = _home_win_from_odds_row(row)
            if home_win is None:
                continue
            row = dict(row)
            row["_sort_date"] = dt.isoformat()
            row["_home_win"] = str(home_win)
            rows.append(row)
    rows.sort(key=_odds_row_sort_key)
    return rows


def _index_odds_rows(eval_path: Path) -> dict[str, dict[str, str]]:
    counts: dict[str, int] = {}
    indexed: dict[str, dict[str, str]] = {}
    for row in _load_final_odds_rows(eval_path):
        base = _game_base_key(
            _first(row, "Date", "date"),
            _first(row, "Away", "away_team"),
            _first(row, "Home", "home_team"),
        )
        counts[base] = counts.get(base, 0) + 1
        key = _game_occurrence_key(base, counts[base])
        if key in indexed:
            raise ValueError(f"duplicate canonical odds occurrence key: {key}")
        indexed[key] = row
    return indexed


def _index_prediction_rows(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, int] = {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in predictions:
        date_s = str(row.get("game_date") or "").strip()
        away = str(row.get("away_team") or "").strip()
        home = str(row.get("home_team") or "").strip()
        if not date_s or not away or not home or home.casefold() == away.casefold():
            raise ValueError(f"malformed prediction game identifier: {row!r}")
        base = _game_base_key(date_s, away, home)
        occurrence_raw = row.get("game_occurrence")
        if occurrence_raw is None:
            counts[base] = counts.get(base, 0) + 1
            occurrence = counts[base]
        else:
            try:
                occurrence = int(occurrence_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid game_occurrence for {base}: {occurrence_raw!r}") from exc
            if occurrence < 1:
                raise ValueError(f"invalid game_occurrence for {base}: {occurrence}")
        key = _game_occurrence_key(base, occurrence)
        if key in indexed:
            raise ValueError(f"duplicate canonical prediction occurrence key: {key}")
        indexed[key] = row
    return indexed


def _devig_home_away_probs(home_ml: Any, away_ml: Any) -> tuple[float | None, float | None]:
    ph = american_to_prob(home_ml)
    pa = american_to_prob(away_ml)
    if ph is None or pa is None or ph + pa <= 0:
        return None, None
    return ph / (ph + pa), pa / (ph + pa)


def build_market_coverage(eval_path: Path) -> dict[str, Any]:
    rows = _load_final_odds_rows(eval_path)
    total = len(rows)

    def has_all(row: dict[str, str], *keys: str) -> bool:
        return all(str(row.get(key, "")).strip() not in ("", "0") for key in keys)

    return {
        "source_file": str(eval_path),
        "final_game_rows": total,
        "markets": {
            "moneyline": {
                "status": "EVALUATED_IN_WORKFLOW",
                "rows_with_lines": sum(1 for r in rows if has_all(r, "Home ML", "Away ML")),
                "coverage": _ratio(sum(1 for r in rows if has_all(r, "Home ML", "Away ML")), total),
            },
            "run_line": {
                "status": "LINES_AND_RESULTS_AVAILABLE_MODEL_PROBABILITY_PENDING",
                "rows_with_lines": sum(
                    1 for r in rows if has_all(r, "Home RL Spread", "RL Away", "RL Home")
                ),
                "coverage": _ratio(
                    sum(1 for r in rows if has_all(r, "Home RL Spread", "RL Away", "RL Home")),
                    total,
                ),
            },
            "total_runs": {
                "status": "LINES_AND_RESULTS_AVAILABLE_MODEL_PROBABILITY_PENDING",
                "rows_with_lines": sum(1 for r in rows if has_all(r, "O/U", "Over", "Under")),
                "coverage": _ratio(sum(1 for r in rows if has_all(r, "O/U", "Over", "Under")), total),
            },
            "first_five": {
                "status": "NO_LOCAL_F5_LINES_OR_F5_RESULTS_IN_SOURCE",
                "rows_with_lines": 0,
                "coverage": 0.0,
            },
        },
    }


def build_moneyline_backtest(
    *,
    scorecard_predictions: list[dict[str, Any]],
    eval_path: Path,
    model_name: str,
    min_ev: float = DEFAULT_MONEYLINE_MIN_EV,
    min_edge: float = DEFAULT_MONEYLINE_MIN_EDGE,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    kelly_cap: float = DEFAULT_KELLY_CAP,
) -> dict[str, Any]:
    """Join holdout predictions to Moneyline odds and score paper candidates."""
    predictions = [
        row for row in scorecard_predictions if row.get("model_name") == model_name
    ]
    pred_index = _index_prediction_rows(predictions)
    odds_index = _index_odds_rows(eval_path)

    rows: list[dict[str, Any]] = []
    missing_odds = 0
    for key, pred in pred_index.items():
        odds = odds_index.get(key)
        if not odds:
            missing_odds += 1
            continue

        home_ml = _first(odds, "Home ML")
        away_ml = _first(odds, "Away ML")
        home_prob_mkt, away_prob_mkt = _devig_home_away_probs(home_ml, away_ml)
        if home_prob_mkt is None or away_prob_mkt is None:
            missing_odds += 1
            continue

        p_home = float(pred["predicted_home_win_probability"])
        side = pred["selected_side"]
        selected_prob = p_home if side == "HOME" else 1.0 - p_home
        selected_market_prob = home_prob_mkt if side == "HOME" else away_prob_mkt
        selected_american = home_ml if side == "HOME" else away_ml
        decimal_odds = american_to_decimal(selected_american)
        if decimal_odds is None:
            missing_odds += 1
            continue

        edge = selected_prob - selected_market_prob
        ev_kelly = calculate_ev_kelly(
            probability=selected_prob,
            decimal_odds=decimal_odds,
            kelly_fraction=kelly_fraction,
            kelly_cap=kelly_cap,
        )
        candidate = (
            ev_kelly["expected_value_per_unit"] >= min_ev
            and edge >= min_edge
            and ev_kelly["used_kelly_fraction"] > 0
        )
        action = "PAPER_CANDIDATE" if candidate else ("WATCH_ONLY" if edge > 0 else "PASS")
        stake = ev_kelly["used_kelly_fraction"] if candidate else 0.0
        correct = int(pred["correct"])
        result_units = 0.0
        if stake:
            result_units = stake * (decimal_odds - 1.0) if correct else -stake

        rows.append(
            {
                "game_date": pred["game_date"],
                "away_team": pred["away_team"],
                "home_team": pred["home_team"],
                "model_name": model_name,
                "predicted_home_win_probability": round(p_home, 6),
                "selected_side": side,
                "selected_side_probability": round(selected_prob, 6),
                "confidence_band": pred["confidence_band"],
                "home_ml": home_ml,
                "away_ml": away_ml,
                "selected_american_odds": selected_american,
                "selected_decimal_odds": round(decimal_odds, 6),
                "selected_market_prob_no_vig": round(selected_market_prob, 6),
                "model_edge_vs_market": round(edge, 6),
                "expected_value_per_unit": ev_kelly["expected_value_per_unit"],
                "full_kelly_fraction": ev_kelly["full_kelly_fraction"],
                "used_kelly_fraction": ev_kelly["used_kelly_fraction"],
                "paper_action": action,
                "actual_home_win": int(pred["actual_home_win"]),
                "correct": correct,
                "paper_result_units": round(result_units, 6),
                "guard_status": "PAPER_ONLY_LOCAL_REPLAY",
                "odds_timing_status": ODDS_TIMING_STATUS,
                "edge_claim_status": "DESCRIPTIVE_DIAGNOSTIC_NOT_VERIFIED_BETTING_EDGE",
            }
        )

    candidates = [row for row in rows if row["paper_action"] == "PAPER_CANDIDATE"]
    summary = _moneyline_summary(
        rows=rows,
        candidates=candidates,
        missing_odds=missing_odds,
        parameters={
            "model_name": model_name,
            "min_ev": min_ev,
            "min_edge": min_edge,
            "kelly_fraction": kelly_fraction,
            "kelly_cap": kelly_cap,
        },
    )
    top = sorted(
        candidates,
        key=lambda row: (
            -float(row["expected_value_per_unit"]),
            -float(row["selected_side_probability"]),
            row["game_date"],
            row["away_team"],
            row["home_team"],
        ),
    )[:12]
    return {"summary": summary, "rows": rows, "top_candidates": top}


def _moneyline_summary(
    *,
    rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    missing_odds: int,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    candidate_count = len(candidates)
    wins = sum(int(row["correct"]) for row in candidates)
    total_staked = sum(float(row["used_kelly_fraction"]) for row in candidates)
    net_units = sum(float(row["paper_result_units"]) for row in candidates)
    side_counts: dict[str, int] = {}
    for row in candidates:
        side_counts[row["selected_side"]] = side_counts.get(row["selected_side"], 0) + 1

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for row in sorted(candidates, key=lambda r: (r["game_date"], r["away_team"], r["home_team"])):
        equity += float(row["paper_result_units"])
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    return {
        "parameters": parameters,
        "prediction_rows_scored": len(rows),
        "missing_odds_rows": missing_odds,
        "paper_candidate_count": candidate_count,
        "paper_candidate_rate": _ratio(candidate_count, len(rows)),
        "hit_rate": _ratio(wins, candidate_count),
        "avg_expected_value_per_unit": _avg(candidates, "expected_value_per_unit"),
        "avg_model_edge_vs_market": _avg(candidates, "model_edge_vs_market"),
        "avg_used_kelly_fraction": _avg(candidates, "used_kelly_fraction"),
        "total_staked_units": round(total_staked, 6),
        "net_result_units": round(net_units, 6),
        "roi_on_staked_units": round(net_units / total_staked, 6) if total_staked else None,
        "max_drawdown_units": round(abs(max_drawdown), 6),
        "selection_distribution": side_counts,
        "odds_timing_status": ODDS_TIMING_STATUS,
        "claim_status": "DESCRIPTIVE_DIAGNOSTIC_NOT_VERIFIED_BETTING_EDGE",
    }


def build_local_2026_prediction_snapshot(
    *,
    prediction_path: Path,
    outcome_path: Path | None = None,
    feature_as_of_utc: str | None = None,
    availability_index_path: Path = DEFAULT_P274_INDEX_PATH,
    availability_manifest_path: Path = DEFAULT_P274_MANIFEST_PATH,
    limit: int = 12,
) -> dict[str, Any]:
    rows = _read_jsonl(prediction_path)
    if not rows:
        return {
            "prediction_path": _portable_input_path(prediction_path),
            "rows": 0,
            "status": "NO_LOCAL_2026_PREDICTIONS",
            "result_context": EXISTING_2026_SNAPSHOT_CONTEXT,
            "generated_by_corrected_retrained_model": False,
            "corrected_model_handoff_status": "NOT_PERFORMED",
        }

    dates = sorted({str(row.get("game_date")) for row in rows if row.get("game_date")})
    source_versions = sorted(
        {
            str(row.get("source_prediction_version"))
            for row in rows
            if row.get("source_prediction_version")
        }
    )
    source_version = source_versions[0] if len(source_versions) == 1 else None
    latest_date = dates[-1] if dates else None
    latest_rows = [row for row in rows if row.get("game_date") == latest_date]
    formatted_latest = [
        _format_2026_prediction_row(row)
        for row in sorted(
            latest_rows,
            key=lambda row: (
                -_selected_side_probability_2026(row),
                str(row.get("away_team")),
                str(row.get("home_team")),
            ),
        )[:limit]
    ]

    outcome_summary = None
    availability_coverage = None
    if outcome_path and outcome_path.exists():
        all_outcome_rows = _read_jsonl(outcome_path)
        raw_available_rows = [
            row for row in all_outcome_rows if row.get("outcome_available") is True
        ]
        gate_available_rows: list[dict[str, Any]] = []
        block_reason_counts: dict[str, int] = {}
        unavailable_before_observation = 0
        missing_or_invalid_evidence = 0

        for row in raw_available_rows:
            decision = p275.evaluate_result_availability(
                game_id=row.get("game_id"),
                feature_as_of_utc=feature_as_of_utc,
                index_path=availability_index_path,
                manifest_path=availability_manifest_path,
            )
            if decision.result_usage_allowed:
                gate_available_rows.append(row)
                continue
            reason = decision.block_reason or p275.INVALID_AVAILABILITY_EVIDENCE
            block_reason_counts[reason] = block_reason_counts.get(reason, 0) + 1
            if reason == p275.RESULT_NOT_YET_AVAILABLE:
                unavailable_before_observation += 1
            else:
                missing_or_invalid_evidence += 1

        result_metric_rows = [
            row for row in gate_available_rows if row.get("is_correct") is not None
        ]
        outcome_summary = _outcome_summary(result_metric_rows)
        availability_coverage = {
            "feature_as_of_utc": feature_as_of_utc,
            "index_path": _portable_input_path(availability_index_path),
            "manifest_path": _portable_input_path(availability_manifest_path),
            "total_outcome_rows": len(all_outcome_rows),
            "raw_outcome_available_true_rows": len(raw_available_rows),
            "gate_available_rows": len(gate_available_rows),
            "result_metric_rows": len(result_metric_rows),
            "unavailable_before_observation_rows": unavailable_before_observation,
            "missing_or_invalid_evidence_rows": missing_or_invalid_evidence,
            "classification_counts": {
                "available": len(gate_available_rows),
                "unavailable_before_observation": unavailable_before_observation,
                "missing_or_invalid_evidence": missing_or_invalid_evidence,
            },
            "block_reason_counts": dict(sorted(block_reason_counts.items())),
            "coverage_limitation": P274_COVERAGE_LIMITATION,
        }

    return {
        "prediction_path": _portable_input_path(prediction_path),
        "outcome_path": _portable_input_path(outcome_path),
        "rows": len(rows),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "latest_local_prediction_date": latest_date,
        "latest_local_rows": len(latest_rows),
        "top_latest_predictions": formatted_latest,
        "outcome_attached_summary": outcome_summary,
        "availability_gate_coverage": availability_coverage,
        "result_context": EXISTING_2026_SNAPSHOT_CONTEXT,
        "source_prediction_version": source_version,
        "source_prediction_versions": source_versions,
        "source_version_status": (
            "EXPECTED_DIAGNOSTIC_BASELINE"
            if source_version == EXPECTED_2026_SOURCE_VERSION
            else "OBSERVED_SOURCE_VERSION_REQUIRES_REVIEW"
        ),
        "freshness_status": "STALE_EXISTING_LOCAL_SNAPSHOT",
        "generated_by_corrected_retrained_model": False,
        "corrected_model_handoff_status": "NOT_PERFORMED",
        "claim_status": "LOCAL_SNAPSHOT_ONLY_NO_LIVE_ODDS",
    }


def _format_2026_prediction_row(row: dict[str, Any]) -> dict[str, Any]:
    p_home = float(row.get("model_probability") or 0.5)
    side = str(row.get("predicted_side") or "").upper()
    return {
        "game_date": row.get("game_date"),
        "away_team": row.get("away_team"),
        "home_team": row.get("home_team"),
        "predicted_side": side,
        "home_win_probability": round(p_home, 6),
        "selected_side_probability": round(_selected_side_probability_2026(row), 6),
        "source_prediction_version": row.get("source_prediction_version"),
        "paper_only": bool(row.get("paper_only")),
        "production_ready": bool(row.get("production_ready")),
    }


def _selected_side_probability_2026(row: dict[str, Any]) -> float:
    p_home = float(row.get("model_probability") or 0.5)
    side = str(row.get("predicted_side") or "").lower()
    return p_home if side == "home" else 1.0 - p_home


def _outcome_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def summarize(scoped: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(scoped)
        correct = sum(1 for row in scoped if row.get("is_correct") is True)
        return {
            "n": n,
            "correct": correct,
            "accuracy": _ratio(correct, n) if n else None,
        }

    return {
        "all_outcome_attached": summarize(rows),
        "primary_125": summarize([r for r in rows if r.get("rule_primary_125_flag") is True]),
        "shadow_100": summarize([r for r in rows if r.get("rule_shadow_100_flag") is True]),
        "tier_a_watchlist": summarize([r for r in rows if r.get("tier_a_watchlist_flag") is True]),
        "tier_b_candidate": summarize([r for r in rows if r.get("tier_b_candidate_flag") is True]),
    }


def build_corrected_shadow_snapshot(
    *,
    manifest_path: Path | None,
    prediction_path: Path | None,
    limit: int = 12,
) -> dict[str, Any]:
    """Load and verify the separate P278 shadow without touching P84-B rows."""
    if manifest_path is None or prediction_path is None:
        return {
            "status": "NOT_SUPPLIED",
            "artifact_version": None,
            "separate_from_p84b": True,
            "champion_activated": False,
        }
    manifest_path = Path(manifest_path)
    prediction_path = Path(prediction_path)
    if not manifest_path.exists() or not prediction_path.exists():
        return {
            "status": "MISSING",
            "manifest_path": _portable_input_path(manifest_path),
            "prediction_path": _portable_input_path(prediction_path),
            "artifact_version": None,
            "separate_from_p84b": True,
            "champion_activated": False,
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_version = manifest.get("artifact_version")
    if artifact_version != EXPECTED_CORRECTED_SHADOW_VERSION:
        raise ValueError(
            f"unexpected corrected shadow version: {artifact_version!r}"
        )
    expected_hash = manifest.get("artifacts", {}).get("predictions_csv_sha256")
    actual_hash = _sha256_file(prediction_path)
    if not expected_hash or actual_hash != expected_hash:
        raise ValueError("corrected shadow prediction checksum mismatch")

    with prediction_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = int(manifest.get("artifacts", {}).get("prediction_row_count", -1))
    if len(rows) != expected_rows:
        raise ValueError("corrected shadow prediction row-count mismatch")
    top_rows = [
        {
            "game_id": row.get("game_id"),
            "game_date": row.get("game_date"),
            "away_team": row.get("away_team"),
            "home_team": row.get("home_team"),
            "predicted_side": row.get("predicted_side"),
            "shadow_home_win_probability": float(
                row.get("shadow_home_win_probability") or 0.5
            ),
            "state_mode": row.get("state_mode"),
        }
        for row in rows[:limit]
    ]
    evaluation = manifest.get("outcome_evaluation", {})
    updates = manifest.get("p275_state_updates", {})
    return {
        "status": "AVAILABLE_RETROSPECTIVE_PAPER_ONLY",
        "manifest_path": _portable_input_path(manifest_path),
        "prediction_path": _portable_input_path(prediction_path),
        "artifact_version": artifact_version,
        "algorithm": manifest.get("model", {}).get("algorithm"),
        "row_count": len(rows),
        "state_mode": manifest.get("state_mode"),
        "source_git_commit": manifest.get("source_git_commit"),
        "model_code_config_fingerprint": manifest.get("model", {}).get(
            "model_code_config_fingerprint"
        ),
        "training_input_fingerprint": manifest.get("training", {}).get(
            "training_input_fingerprint"
        ),
        "prediction_input_fingerprint": manifest.get("prediction_input", {}).get(
            "prediction_input_fingerprint"
        ),
        "state_updates": {
            "attempted": updates.get("attempted"),
            "allowed": updates.get("allowed"),
            "denied": updates.get("denied"),
            "applied": updates.get("applied"),
        },
        "outcome_evaluation": {
            "denominator": evaluation.get("outcome_evaluation_denominator"),
            "accuracy": evaluation.get("accuracy"),
            "brier_score": evaluation.get("brier_score"),
            "roi": evaluation.get("roi"),
            "expected_value": evaluation.get("expected_value"),
            "kelly": evaluation.get("kelly"),
        },
        "top_predictions": top_rows,
        "retrospective": True,
        "paper_only": True,
        "diagnostic_only": True,
        "live_publication": False,
        "pregame_publication_verified": False,
        "production_ready": False,
        "separate_from_p84b": True,
        "p84b_replaced": False,
        "champion_activated": False,
    }


def build_moneyline_divergence_snapshot(summary_path: Path | None) -> dict[str, Any]:
    """Load the outcome-free P279 reference without evaluating either model."""
    if summary_path is None:
        return {
            "status": "NOT_SUPPLIED",
            "divergence_not_performance": True,
            "model_winner_declared": False,
            "champion_activated": False,
        }
    summary_path = Path(summary_path)
    if not summary_path.exists():
        return {
            "status": "MISSING",
            "summary_path": _portable_input_path(summary_path),
            "divergence_not_performance": True,
            "model_winner_declared": False,
            "champion_activated": False,
        }
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    contract = payload.get("comparison_contract", {})
    claims = payload.get("claims", {})
    if payload.get("comparison_version") != "p279a.moneyline_shadow_divergence.v1":
        raise ValueError("unexpected P279 Moneyline divergence comparison version")
    if (
        contract.get("outcome_fields_used") != "NONE"
        or contract.get("odds_fields_used") != "NONE"
        or contract.get("evaluation_denominator") != 0
    ):
        raise ValueError("P279 workflow reference is not outcome/odds isolated")
    if claims.get("model_winner_declared") is not False:
        raise ValueError("P279 workflow reference declares a model winner")
    if claims.get("champion_activated") is not False:
        raise ValueError("P279 workflow reference activates a champion")

    artifacts = payload.get("output_artifacts", {})
    alignment = payload.get("alignment", {})
    sources = payload.get("source_artifacts", {})
    return {
        "status": payload.get("status"),
        "summary_path": _portable_input_path(summary_path),
        "ledger_path": artifacts.get("ledger_csv"),
        "comparison_version": payload.get("comparison_version"),
        "p84b_model_version": sources.get("p84b", {}).get("model_version"),
        "p278_model_version": sources.get("p278", {}).get("model_version"),
        "shared_game_count": alignment.get("shared_game_count"),
        "outcome_fields_used": contract.get("outcome_fields_used"),
        "odds_fields_used": contract.get("odds_fields_used"),
        "evaluation_denominator": contract.get("evaluation_denominator"),
        "divergence_not_performance": True,
        "model_winner_declared": False,
        "champion_activated": False,
        "production_ready": False,
        "future_outcome_evaluation_requires_prospective_availability": claims.get(
            "future_outcome_evaluation_requires_prospective_availability"
        ),
    }


def run_workflow_snapshot(
    *,
    warmup_path: Path,
    eval_path: Path,
    prediction_2026_path: Path,
    outcome_2026_path: Path | None = None,
    feature_as_of_utc: str | None = None,
    availability_index_path: Path = DEFAULT_P274_INDEX_PATH,
    availability_manifest_path: Path = DEFAULT_P274_MANIFEST_PATH,
    corrected_shadow_manifest_path: Path | None = None,
    corrected_shadow_prediction_path: Path | None = None,
    moneyline_divergence_summary_path: Path | None = (
        DEFAULT_MONEYLINE_DIVERGENCE_SUMMARY_PATH
    ),
    min_ev: float = DEFAULT_MONEYLINE_MIN_EV,
    min_edge: float = DEFAULT_MONEYLINE_MIN_EDGE,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    kelly_cap: float = DEFAULT_KELLY_CAP,
) -> dict[str, Any]:
    scorecard = run_scorecard(warmup_path, eval_path)
    best_model = scorecard.best_by_brier
    moneyline = build_moneyline_backtest(
        scorecard_predictions=scorecard.predictions,
        eval_path=eval_path,
        model_name=best_model,
        min_ev=min_ev,
        min_edge=min_edge,
        kelly_fraction=kelly_fraction,
        kelly_cap=kelly_cap,
    )
    snapshot_2026 = build_local_2026_prediction_snapshot(
        prediction_path=prediction_2026_path,
        outcome_path=outcome_2026_path,
        feature_as_of_utc=feature_as_of_utc,
        availability_index_path=availability_index_path,
        availability_manifest_path=availability_manifest_path,
    )
    corrected_shadow = build_corrected_shadow_snapshot(
        manifest_path=corrected_shadow_manifest_path,
        prediction_path=corrected_shadow_prediction_path,
    )
    corrected_shadow_available = corrected_shadow.get("status") == (
        "AVAILABLE_RETROSPECTIVE_PAPER_ONLY"
    )
    moneyline_divergence = build_moneyline_divergence_snapshot(
        moneyline_divergence_summary_path
    )

    return {
        "task": "MLB local prediction workflow snapshot",
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "inputs": {
            "warmup_path": _portable_input_path(warmup_path),
            "eval_path": _portable_input_path(eval_path),
            "prediction_2026_path": _portable_input_path(prediction_2026_path),
            "outcome_2026_path": _portable_input_path(outcome_2026_path),
            "feature_as_of_utc": feature_as_of_utc,
            "availability_index_path": _portable_input_path(availability_index_path),
            "availability_manifest_path": _portable_input_path(availability_manifest_path),
            "corrected_shadow_manifest_path": _portable_input_path(
                corrected_shadow_manifest_path
            ),
            "corrected_shadow_prediction_path": _portable_input_path(
                corrected_shadow_prediction_path
            ),
            "moneyline_divergence_summary_path": _portable_input_path(
                moneyline_divergence_summary_path
            ),
        },
        "retrain_scorecard": {
            "result_context": CORRECTED_2025_RESULT_CONTEXT,
            "state_transition_contract": "PREDICT_FULL_DATE_THEN_UPDATE",
            "warmup_rows": scorecard.warmup_rows,
            "eval_rows": scorecard.eval_rows,
            "split": scorecard.split,
            "best_by_brier": best_model,
            "train_home_win_prior": round(scorecard.train_home_win_prior, 6),
            "platt": {
                "A": round(scorecard.platt["A"], 6),
                "B": round(scorecard.platt["B"], 6),
            },
            "model_comparison": [
                {
                    "model_name": row["model_name"],
                    "accuracy": round(float(row["accuracy"]), 6),
                    "brier_score": round(float(row["brier_score"]), 6),
                    "log_loss": round(float(row["log_loss"]), 6),
                    "calibration_error": round(float(row["calibration_error"]), 6),
                    "coverage": round(float(row["coverage"]), 6),
                }
                for row in scorecard.comparison
            ],
            "best_confidence_band_breakdown": scorecard.confidence_band_breakdown,
            "best_selected_side_distribution": scorecard.selected_side_distribution,
        },
        "market_coverage": build_market_coverage(eval_path),
        "moneyline_strategy": {
            "result_context": "CORRECTED_2025_HISTORICAL_ODDS_DIAGNOSTIC",
            "summary": moneyline["summary"],
            "top_candidates": moneyline["top_candidates"],
        },
        "moneyline_backtest_rows": moneyline["rows"],
        "local_2026_prediction_snapshot": snapshot_2026,
        "corrected_moneyline_shadow": corrected_shadow,
        "moneyline_shadow_divergence": moneyline_divergence,
        "claim_status": {
            "historical_only": True,
            "historical_odds_pregame_timestamps_verified": False,
            "verified_betting_edge_established": False,
            "corrected_model_generated_2026_snapshot": False,
            "corrected_model_to_2026_handoff_performed": corrected_shadow_available,
            "corrected_shadow_retrospective_only": corrected_shadow_available,
            "p84b_baseline_replaced": False,
            "champion_activated": False,
            "moneyline_divergence_uses_outcomes_or_odds": False,
            "moneyline_divergence_is_performance_evaluation": False,
            "moneyline_model_superiority_declared": False,
            "live_provider_called": False,
            "db_written": False,
            "production_enabled": False,
            "real_ticket_created": False,
        },
    }


def write_workflow_reports(
    payload: dict[str, Any],
    out_dir: Path,
    *,
    write_tabular_outputs: bool = True,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "markdown": out_dir / "mlb_prediction_workflow_snapshot.md",
        "json": out_dir / "mlb_prediction_workflow_snapshot.json",
        "moneyline_csv": out_dir / "mlb_prediction_workflow_moneyline_backtest.csv",
        "latest_predictions_csv": out_dir / "mlb_prediction_workflow_latest_2026_predictions.csv",
    }

    if write_tabular_outputs:
        _write_csv(payload["moneyline_backtest_rows"], paths["moneyline_csv"])
        _write_csv(
            payload["local_2026_prediction_snapshot"].get("top_latest_predictions", []),
            paths["latest_predictions_csv"],
        )

    json_payload = deepcopy(payload)
    json_payload["moneyline_backtest_rows"] = {
        "row_count": len(payload["moneyline_backtest_rows"]),
        "path": _portable_output_path(paths["moneyline_csv"]),
    }
    json_payload["output_paths"] = {
        key: _portable_output_path(path) for key, path in paths.items()
    }
    paths["json"].write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(render_markdown(payload, paths), encoding="utf-8")
    return paths


def render_markdown(payload: dict[str, Any], paths: dict[str, Path]) -> str:
    retrain = payload["retrain_scorecard"]
    ml = payload["moneyline_strategy"]["summary"]
    latest = payload["local_2026_prediction_snapshot"]
    shadow = payload.get("corrected_moneyline_shadow", {"status": "NOT_SUPPLIED"})
    divergence = payload.get(
        "moneyline_shadow_divergence",
        {
            "status": "NOT_SUPPLIED",
            "divergence_not_performance": True,
            "model_winner_declared": False,
            "champion_activated": False,
        },
    )

    lines = [
        "# MLB Prediction Workflow Snapshot",
        "",
        f"**Scope:** `{payload['scope']}`",
        "",
        f"**Disclaimer:** {payload['disclaimer']}",
        "",
        "## Corrected 2025 Local Retrain and Evaluation",
        "",
        f"- Result context: `{retrain['result_context']}`",
        f"- State transition: `{retrain['state_transition_contract']}`",
        f"- Warmup rows: `{retrain['warmup_rows']}`",
        f"- Evaluation rows: `{retrain['eval_rows']}`",
        (
            f"- Train: `{retrain['split']['train_period'][0]}` to "
            f"`{retrain['split']['train_period'][1]}` "
            f"({retrain['split']['train_rows']} games)"
        ),
        (
            f"- Test: `{retrain['split']['test_period'][0]}` to "
            f"`{retrain['split']['test_period'][1]}` "
            f"({retrain['split']['test_rows']} games)"
        ),
        (
            "- Complete-date counts: "
            f"train `{retrain['split']['train_date_count']}`, "
            f"test `{retrain['split']['test_date_count']}`"
        ),
        (
            "- Train fraction: requested "
            f"`{retrain['split']['requested_train_frac']:.6f}`, effective "
            f"`{retrain['split']['effective_train_frac']:.6f}`"
        ),
        f"- Split strategy: `{retrain['split']['split_strategy']}`",
        f"- Tie rule: `{retrain['split']['tie_rule']}`",
        (
            f"- Selected boundary: after `{retrain['split']['selected_boundary_date']}`; "
            f"test starts `{retrain['split']['selected_test_start_date']}`"
        ),
        f"- Best by Brier: `{retrain['best_by_brier']}`",
        "",
        "| Model | Accuracy | Brier | Log Loss | ECE |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in retrain["model_comparison"]:
        lines.append(
            f"| `{row['model_name']}` | {row['accuracy']:.4f} | "
            f"{row['brier_score']:.4f} | {row['log_loss']:.4f} | "
            f"{row['calibration_error']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Corrected 2025 Historical Moneyline Diagnostic",
            "",
            "- Historical odds do not have verified pregame timestamps.",
            "- Candidate hit rate, EV, Kelly, and ROI below are descriptive workflow "
            "diagnostics, not a verified betting edge or live wagering evidence.",
            f"- Odds timing status: `{ml['odds_timing_status']}`",
            f"- Claim status: `{ml['claim_status']}`",
            f"- Prediction rows scored: `{ml['prediction_rows_scored']}`",
            f"- Paper candidates: `{ml['paper_candidate_count']}` "
            f"({ml['paper_candidate_rate']:.2%})",
            f"- Candidate hit rate: `{_pct_or_na(ml['hit_rate'])}`",
            f"- Net result units: `{ml['net_result_units']}`",
            f"- ROI on staked units: `{_pct_or_na(ml['roi_on_staked_units'])}`",
            f"- Avg EV per unit: `{_num_or_na(ml['avg_expected_value_per_unit'])}`",
            f"- Avg Kelly used: `{_pct_or_na(ml['avg_used_kelly_fraction'])}`",
            f"- Backtest CSV: `{_portable_output_path(paths['moneyline_csv'])}`",
            "",
            "### Top Historical Paper Rows (Diagnostic Only)",
            "",
            "| Date | Game | Side | Sel Prob | Odds | EV | Kelly | Result |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["moneyline_strategy"]["top_candidates"]:
        game = f"{row['away_team']} @ {row['home_team']}"
        lines.append(
            f"| {row['game_date']} | {game} | {row['selected_side']} | "
            f"{float(row['selected_side_probability']):.2%} | "
            f"{row['selected_american_odds']} | "
            f"{float(row['expected_value_per_unit']):.3f} | "
            f"{float(row['used_kelly_fraction']):.2%} | "
            f"{float(row['paper_result_units']):.4f} |"
        )

    lines.extend(
        [
            "",
            "## Taiwan Sports Lottery Market Coverage",
            "",
            "| Market | Status | Rows With Lines | Coverage |",
            "|---|---|---:|---:|",
        ]
    )
    for market, row in payload["market_coverage"]["markets"].items():
        lines.append(
            f"| `{market}` | `{row['status']}` | {row['rows_with_lines']} | "
            f"{row['coverage']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Existing 2026 Prediction Snapshot (Separate and Stale)",
            "",
            f"- Result context: `{latest.get('result_context')}`",
            f"- Rows: `{latest.get('rows', 0)}`",
            f"- Date range: `{latest.get('date_range')}`",
            f"- Latest local prediction date: `{latest.get('latest_local_prediction_date')}`",
            f"- Snapshot source model/version: `{latest.get('source_prediction_version')}`",
            f"- Freshness status: `{latest.get('freshness_status')}`",
            "- Corrected 2025 retrained model generated these 2026 predictions: "
            f"`{latest.get('generated_by_corrected_retrained_model')}`",
            "- Corrected-model to 2026 prediction handoff: "
            f"`{latest.get('corrected_model_handoff_status')}`",
            "- Latest prediction CSV: "
            f"`{_portable_output_path(paths['latest_predictions_csv'])}`",
        ]
    )
    outcome = latest.get("outcome_attached_summary")
    availability = latest.get("availability_gate_coverage")
    if availability:
        lines.extend(
            [
                f"- Outcome rows: `{availability['total_outcome_rows']}`",
                "- Raw `outcome_available=true` rows: "
                f"`{availability['raw_outcome_available_true_rows']}`",
                f"- P275 gate-available rows: `{availability['gate_available_rows']}`",
                "- Unavailable-before-observation rows: "
                f"`{availability['unavailable_before_observation_rows']}`",
                "- Missing/invalid evidence rows: "
                f"`{availability['missing_or_invalid_evidence_rows']}`",
                f"- Availability coverage limitation: {availability['coverage_limitation']}",
            ]
        )
    if outcome:
        all_outcomes = outcome["all_outcome_attached"]
        lines.append(
            f"- Outcome-attached accuracy: `{_pct_or_na(all_outcomes['accuracy'])}` "
            f"({all_outcomes['correct']}/{all_outcomes['n']})"
        )

    lines.extend(
        [
            "",
            "| Date | Game | Side | Sel Prob | Version |",
            "|---|---|---|---:|---|",
        ]
    )
    for row in latest.get("top_latest_predictions", []):
        game = f"{row['away_team']} @ {row['home_team']}"
        lines.append(
            f"| {row['game_date']} | {game} | {row['predicted_side']} | "
            f"{float(row['selected_side_probability']):.2%} | "
            f"`{row['source_prediction_version']}` |"
        )

    lines.extend(
        [
            "",
            "## Corrected 2026 Moneyline Shadow (Separate and Retrospective)",
            "",
            f"- Status: `{shadow.get('status')}`",
            f"- Artifact version: `{shadow.get('artifact_version')}`",
            f"- Selected algorithm: `{shadow.get('algorithm')}`",
            f"- Rows: `{shadow.get('row_count', 0)}`",
            f"- State mode: `{shadow.get('state_mode')}`",
            "- Retrospective paper-only diagnostic; not a live or verified pregame "
            "publication.",
            "- Existing P84-B baseline replaced: "
            f"`{shadow.get('p84b_replaced', False)}`",
            f"- Champion activated: `{shadow.get('champion_activated', False)}`",
        ]
    )
    if shadow.get("status") == "AVAILABLE_RETROSPECTIVE_PAPER_ONLY":
        updates = shadow["state_updates"]
        evaluation = shadow["outcome_evaluation"]
        lines.extend(
            [
                f"- P275 update attempted / allowed / denied / applied: "
                f"`{updates['attempted']}` / `{updates['allowed']}` / "
                f"`{updates['denied']}` / `{updates['applied']}`",
                f"- Outcome-evaluation denominator: `{evaluation['denominator']}`",
                f"- Accuracy: `{_num_or_na(evaluation['accuracy'])}`",
                f"- Brier: `{_num_or_na(evaluation['brier_score'])}`",
                f"- ROI / EV / Kelly: `{_num_or_na(evaluation['roi'])}` / "
                f"`{_num_or_na(evaluation['expected_value'])}` / "
                f"`{_num_or_na(evaluation['kelly'])}`",
                "- No outcome-based comparative winner or betting edge is declared.",
            ]
        )

    lines.extend(
        [
            "",
            "## P279-A Outcome-Free Moneyline Prediction Divergence",
            "",
            f"- Status: `{divergence.get('status')}`",
            "- Comparison: existing P84-B baseline versus P278 corrected shadow.",
            f"- Comparison version: `{divergence.get('comparison_version')}`",
            f"- Shared games: `{divergence.get('shared_game_count', 0)}`",
            f"- Outcome fields used: `{divergence.get('outcome_fields_used', 'NONE')}`",
            f"- Odds fields used: `{divergence.get('odds_fields_used', 'NONE')}`",
            f"- Evaluation denominator: `{divergence.get('evaluation_denominator', 0)}`",
            "- This measures prediction divergence, not model performance.",
            "- Neither model is activated or declared superior.",
            "- Future performance evaluation requires prospectively available outcomes.",
            f"- Ledger: `{divergence.get('ledger_path')}`",
            f"- Summary: `{divergence.get('summary_path')}`",
        ]
    )

    lines.extend(
        [
            "",
            "## Output Files",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`: `{_portable_output_path(path)}`")
    lines.append("")
    return "\n".join(lines)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(sum(values) / len(values), 6) if values else None


def _ratio(num: int, den: int) -> float:
    return round(num / den, 6) if den else 0.0


def _pct_or_na(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.2%}"


def _num_or_na(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.6f}"
