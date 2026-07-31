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
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wbc_backend.recommendation.local_retrain_scorecard import (
    american_to_prob,
    run_scorecard,
)


SCOPE = "LOCAL_PAPER_WORKFLOW_SNAPSHOT"
DISCLAIMER = (
    "Local historical replay and local prediction snapshot only. Paper-market "
    "metrics are for workflow validation, not live betting advice."
)

DEFAULT_MONEYLINE_MIN_EV = 0.01
DEFAULT_MONEYLINE_MIN_EDGE = 0.015
DEFAULT_KELLY_FRACTION = 0.25
DEFAULT_KELLY_CAP = 0.015


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


def _load_final_odds_rows(eval_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with eval_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            date_s = _first(row, "Date", "date")
            home = _first(row, "Home", "home_team")
            away = _first(row, "Away", "away_team")
            status = _first(row, "Status", "status") or "Final"
            if not date_s or not home or not away or status.lower() != "final":
                continue
            try:
                dt = datetime.strptime(date_s, "%Y-%m-%d")
            except ValueError:
                continue
            row = dict(row)
            row["_sort_date"] = dt.isoformat()
            rows.append(row)
    rows.sort(key=lambda r: (r["_sort_date"], _first(r, "Home"), _first(r, "Away")))
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
        indexed[_game_occurrence_key(base, counts[base])] = row
    return indexed


def _index_prediction_rows(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, int] = {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in predictions:
        base = _game_base_key(row["game_date"], row["away_team"], row["home_team"])
        counts[base] = counts.get(base, 0) + 1
        indexed[_game_occurrence_key(base, counts[base])] = row
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
        "claim_status": "PAPER_ONLY_BACKTEST_NOT_LIVE_BETTING_ADVICE",
    }


def build_local_2026_prediction_snapshot(
    *,
    prediction_path: Path,
    outcome_path: Path | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    rows = _read_jsonl(prediction_path)
    if not rows:
        return {
            "prediction_path": str(prediction_path),
            "rows": 0,
            "status": "NO_LOCAL_2026_PREDICTIONS",
        }

    dates = sorted({str(row.get("game_date")) for row in rows if row.get("game_date")})
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
    if outcome_path and outcome_path.exists():
        outcome_rows = [
            row for row in _read_jsonl(outcome_path)
            if row.get("outcome_available") is True and row.get("is_correct") is not None
        ]
        outcome_summary = _outcome_summary(outcome_rows)

    return {
        "prediction_path": str(prediction_path),
        "outcome_path": str(outcome_path) if outcome_path else None,
        "rows": len(rows),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "latest_local_prediction_date": latest_date,
        "latest_local_rows": len(latest_rows),
        "top_latest_predictions": formatted_latest,
        "outcome_attached_summary": outcome_summary,
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
        return {"n": n, "correct": correct, "accuracy": _ratio(correct, n)}

    return {
        "all_outcome_attached": summarize(rows),
        "primary_125": summarize([r for r in rows if r.get("rule_primary_125_flag") is True]),
        "shadow_100": summarize([r for r in rows if r.get("rule_shadow_100_flag") is True]),
        "tier_a_watchlist": summarize([r for r in rows if r.get("tier_a_watchlist_flag") is True]),
        "tier_b_candidate": summarize([r for r in rows if r.get("tier_b_candidate_flag") is True]),
    }


def run_workflow_snapshot(
    *,
    warmup_path: Path,
    eval_path: Path,
    prediction_2026_path: Path,
    outcome_2026_path: Path | None = None,
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

    return {
        "task": "MLB local prediction workflow snapshot",
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "inputs": {
            "warmup_path": str(warmup_path),
            "eval_path": str(eval_path),
            "prediction_2026_path": str(prediction_2026_path),
            "outcome_2026_path": str(outcome_2026_path) if outcome_2026_path else None,
        },
        "retrain_scorecard": {
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
            "summary": moneyline["summary"],
            "top_candidates": moneyline["top_candidates"],
        },
        "moneyline_backtest_rows": moneyline["rows"],
        "local_2026_prediction_snapshot": build_local_2026_prediction_snapshot(
            prediction_path=prediction_2026_path,
            outcome_path=outcome_2026_path,
        ),
        "claim_status": {
            "historical_only": True,
            "live_provider_called": False,
            "db_written": False,
            "production_enabled": False,
            "real_ticket_created": False,
        },
    }


def write_workflow_reports(payload: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "markdown": out_dir / "mlb_prediction_workflow_snapshot.md",
        "json": out_dir / "mlb_prediction_workflow_snapshot.json",
        "moneyline_csv": out_dir / "mlb_prediction_workflow_moneyline_backtest.csv",
        "latest_predictions_csv": out_dir / "mlb_prediction_workflow_latest_2026_predictions.csv",
    }

    _write_csv(payload["moneyline_backtest_rows"], paths["moneyline_csv"])
    _write_csv(
        payload["local_2026_prediction_snapshot"].get("top_latest_predictions", []),
        paths["latest_predictions_csv"],
    )

    json_payload = deepcopy(payload)
    json_payload["moneyline_backtest_rows"] = {
        "row_count": len(payload["moneyline_backtest_rows"]),
        "path": str(paths["moneyline_csv"]),
    }
    json_payload["output_paths"] = {key: str(path) for key, path in paths.items()}
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

    lines = [
        "# MLB Prediction Workflow Snapshot",
        "",
        f"**Scope:** `{payload['scope']}`",
        "",
        f"**Disclaimer:** {payload['disclaimer']}",
        "",
        "## Retrain Result",
        "",
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
            "## Moneyline Paper Workflow",
            "",
            f"- Prediction rows scored: `{ml['prediction_rows_scored']}`",
            f"- Paper candidates: `{ml['paper_candidate_count']}` "
            f"({ml['paper_candidate_rate']:.2%})",
            f"- Candidate hit rate: `{_pct_or_na(ml['hit_rate'])}`",
            f"- Net result units: `{ml['net_result_units']}`",
            f"- ROI on staked units: `{_pct_or_na(ml['roi_on_staked_units'])}`",
            f"- Avg EV per unit: `{_num_or_na(ml['avg_expected_value_per_unit'])}`",
            f"- Avg Kelly used: `{_pct_or_na(ml['avg_used_kelly_fraction'])}`",
            f"- Backtest CSV: `{paths['moneyline_csv']}`",
            "",
            "### Top Paper Moneyline Candidates",
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
            "## Local 2026 Prediction Snapshot",
            "",
            f"- Rows: `{latest.get('rows', 0)}`",
            f"- Date range: `{latest.get('date_range')}`",
            f"- Latest local prediction date: `{latest.get('latest_local_prediction_date')}`",
            f"- Latest prediction CSV: `{paths['latest_predictions_csv']}`",
        ]
    )
    outcome = latest.get("outcome_attached_summary")
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
            "## Output Files",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`: `{path}`")
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
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
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

