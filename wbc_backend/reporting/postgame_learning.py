from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wbc_backend.config.settings import AppConfig
from wbc_backend.strategy.live_retrainer import GameResult, run_retraining_cycle
from learning import self_learning


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_latest_prediction_record(
    *,
    config: AppConfig,
    game_id: str,
) -> dict[str, Any] | None:
    rows = _read_jsonl(Path(config.sources.prediction_registry_jsonl))
    matches = [row for row in rows if str(row.get("game_id")) == str(game_id)]
    if not matches:
        return None
    return matches[-1]


def extract_sub_model_predictions(record: dict[str, Any]) -> dict[str, float]:
    sub_models = record.get("prediction", {}).get("sub_model_results", [])
    predictions: dict[str, float] = {}
    for sub_model in sub_models:
        name = str(sub_model.get("model_name") or "").strip()
        home_win_prob = sub_model.get("home_win_prob")
        if not name or not isinstance(home_win_prob, (int, float)):
            continue
        predictions[name] = float(home_win_prob)
    return predictions


def _binary_log_loss(prob: float, actual: int) -> float:
    clipped = min(max(float(prob), 1e-6), 1.0 - 1e-6)
    return -(actual * math.log(clipped) + (1 - actual) * math.log(1 - clipped))


def _round_dict(values: dict[str, float], digits: int = 4) -> dict[str, float]:
    return {key: round(float(value), digits) for key, value in values.items()}


def _safe_div(numerator: float, denominator: float) -> float:
    if abs(float(denominator)) < 1e-12:
        return 0.0
    return float(numerator) / float(denominator)


def build_market_support_decision_note(summary: dict[str, Any]) -> str:
    groups = summary.get("groups")
    if not isinstance(groups, dict) or not groups:
        return "Market support evidence is insufficient; keep support multipliers neutral until more postgame samples accumulate."

    ranked = list(groups.items())
    leader_state, leader_metrics = ranked[0]
    if not isinstance(leader_metrics, dict):
        return "Market support evidence is mixed; keep current allocation conservative."

    leader_games = int(leader_metrics.get("games", 0) or 0)
    leader_acc = float(leader_metrics.get("winner_accuracy", 0.0) or 0.0)
    leader_brier = float(leader_metrics.get("avg_brier", 0.0) or 0.0)

    if leader_games < 3:
        return "Market support sample remains thin; treat recent support trends as observational rather than deployable."

    if leader_state == "tsl_direct" and leader_acc >= 0.60:
        return (
            "Recent postgame results favor TSL direct support; keep bankroll allocation biased toward fresh Taiwan-market-confirmed bets "
            "when EV and timing gates are otherwise similar."
        )
    if leader_state == "intl_only" and leader_acc >= 0.60:
        return (
            "Recent postgame results favor international-only support; keep Taiwan-market priors conservative unless direct TSL coverage is fresh "
            "and materially stronger."
        )
    if leader_state in {"tsl_stale", "tsl_unlisted_market", "tsl_unlisted_matchup"} and leader_brier >= 0.20:
        return (
            "Degraded Taiwan-market support remains unreliable in recent samples; continue downweighting stale or partially listed TSL signals."
        )

    return "Market support performance is mixed; prefer higher-EV bets but keep support-state penalties active until a clearer edge emerges."


def _build_prediction_summary(record: dict[str, Any]) -> dict[str, Any]:
    prediction = record.get("prediction", {})
    game_output = record.get("game_output", {})
    verification = record.get("verification", {})
    decision_report = record.get("decision_report", {})
    market_support = record.get("market_support", {})
    return {
        "recorded_at_utc": record.get("recorded_at_utc"),
        "predicted_home_win_prob": round(float(prediction.get("home_win_prob", 0.0)), 4),
        "predicted_away_win_prob": round(float(prediction.get("away_win_prob", 0.0)), 4),
        "predicted_home_score": round(float(game_output.get("predicted_home_score", 0.0)), 2),
        "predicted_away_score": round(float(game_output.get("predicted_away_score", 0.0)), 2),
        "confidence_index": round(float(game_output.get("confidence_index", 0.0)), 4),
        "verification_status": verification.get("status"),
        "used_fallback_lineup": bool(verification.get("used_fallback_lineup", False)),
        "decision": decision_report.get("decision"),
        "decision_reasoning": decision_report.get("reasoning", []),
        "market_support_primary": market_support.get("primary", "unknown"),
        "market_support_tilt": market_support.get("tilt", "neutral"),
        "best_bet_support_state": market_support.get("best_bet_state", "unknown"),
    }


def summarize_market_support_performance(
    *,
    config: AppConfig,
    group_by: str = "market_support_primary",
) -> dict[str, Any]:
    rows = _read_jsonl(Path(config.sources.postgame_results_jsonl))
    summary: dict[str, dict[str, float]] = {}

    for row in rows:
        evaluation = row.get("evaluation") or {}
        if not isinstance(evaluation, dict):
            continue

        state = str(evaluation.get(group_by) or "unknown")
        bucket = summary.setdefault(
            state,
            {
                "games": 0.0,
                "winner_correct": 0.0,
                "brier_sum": 0.0,
                "log_loss_sum": 0.0,
                "score_error_sum": 0.0,
            },
        )
        bucket["games"] += 1.0
        bucket["winner_correct"] += 1.0 if evaluation.get("winner_correct") else 0.0
        bucket["brier_sum"] += float(evaluation.get("home_win_brier", 0.0) or 0.0)
        bucket["log_loss_sum"] += float(evaluation.get("home_win_log_loss", 0.0) or 0.0)
        bucket["score_error_sum"] += float(evaluation.get("score_error_total_abs", 0.0) or 0.0)

    by_group: dict[str, Any] = {}
    total_games = 0.0
    for state, bucket in summary.items():
        games = float(bucket["games"])
        total_games += games
        by_group[state] = {
            "games": int(games),
            "winner_accuracy": round(_safe_div(bucket["winner_correct"], games), 4),
            "avg_brier": round(_safe_div(bucket["brier_sum"], games), 6),
            "avg_log_loss": round(_safe_div(bucket["log_loss_sum"], games), 6),
            "avg_total_score_error": round(_safe_div(bucket["score_error_sum"], games), 4),
        }

    ranked_groups = sorted(
        by_group.items(),
        key=lambda item: (
            -int(item[1]["games"]),
            -float(item[1]["winner_accuracy"]),
            float(item[1]["avg_brier"]),
        ),
    )

    summary_payload = {
        "group_by": group_by,
        "n_games": int(total_games),
        "groups": dict(ranked_groups),
        "decision_note": "",
    }
    summary_payload["decision_note"] = build_market_support_decision_note(summary_payload)
    return summary_payload


def write_market_support_performance_summary(
    *,
    config: AppConfig,
    group_by: str = "market_support_primary",
    filename: str = "market_support_performance_summary.json",
) -> Path:
    summary = summarize_market_support_performance(config=config, group_by=group_by)
    target = Path(config.sources.reports_dir) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _render_market_support_review_section(summary: dict[str, Any]) -> str:
    lines = [
        "## Market Support Trend",
        "",
        f"- 分組方式: `{summary.get('group_by', '')}`",
        f"- 累積樣本: `{summary.get('n_games', 0)}` 場",
    ]
    if summary.get("decision_note"):
        lines.append(f"- Decision Note: {summary.get('decision_note')}")
    groups = summary.get("groups")
    if isinstance(groups, dict) and groups:
        for state, metrics in list(groups.items())[:3]:
            if not isinstance(metrics, dict):
                continue
            lines.append(
                "- "
                f"`{state}`: games={int(metrics.get('games', 0))}, "
                f"acc={float(metrics.get('winner_accuracy', 0.0)):.1%}, "
                f"brier={float(metrics.get('avg_brier', 0.0)):.4f}, "
                f"logloss={float(metrics.get('avg_log_loss', 0.0)):.4f}"
            )
    else:
        lines.append("- 尚無可用樣本")
    return "\n".join(lines) + "\n"


def update_review_report_with_market_support_summary(
    *,
    config: AppConfig,
    summary: dict[str, Any] | None = None,
) -> Path:
    summary = summary or summarize_market_support_performance(config=config)
    if not summary.get("decision_note"):
        summary["decision_note"] = build_market_support_decision_note(summary)
    target = Path(config.sources.review_report_latest_md)
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = ""
    if target.exists():
        existing = target.read_text(encoding="utf-8")

    marker = "## Market Support Trend"
    rendered = _render_market_support_review_section(summary).strip()

    if marker in existing:
        start = existing.index(marker)
        next_header = existing.find("\n## ", start + len(marker))
        if next_header == -1:
            prefix = existing[:start]
            suffix = ""
        else:
            prefix = existing[:start]
            suffix = existing[next_header:]
        content = prefix.rstrip() + "\n\n" + rendered + ("\n" + suffix.lstrip() if suffix else "\n")
    elif existing.strip():
        content = existing.rstrip() + "\n\n" + rendered + "\n"
    else:
        content = rendered + "\n"

    target.write_text(content, encoding="utf-8")
    return target


def _build_evaluation(
    *,
    prediction_record: dict[str, Any],
    home_score: int,
    away_score: int,
) -> dict[str, Any]:
    game_output = prediction_record.get("game_output", {})
    prediction = prediction_record.get("prediction", {})
    actual_home_win = 1 if home_score > away_score else 0
    pred_home_win_prob = float(prediction.get("home_win_prob", 0.0))
    pred_home_score = float(game_output.get("predicted_home_score", 0.0))
    pred_away_score = float(game_output.get("predicted_away_score", 0.0))
    predicted_total = pred_home_score + pred_away_score
    actual_total = home_score + away_score
    predicted_home_win = pred_home_win_prob >= 0.5

    return {
        "predicted_home_win": predicted_home_win,
        "winner_correct": predicted_home_win == bool(actual_home_win),
        "home_win_brier": round((pred_home_win_prob - actual_home_win) ** 2, 6),
        "home_win_log_loss": round(_binary_log_loss(pred_home_win_prob, actual_home_win), 6),
        "score_error_home_abs": round(abs(pred_home_score - home_score), 2),
        "score_error_away_abs": round(abs(pred_away_score - away_score), 2),
        "score_error_total_abs": round(abs(predicted_total - actual_total), 2),
        "actual_total_runs": actual_total,
        "predicted_total_runs": round(predicted_total, 2),
        "market_support_primary": prediction_record.get("market_support", {}).get("primary", "unknown"),
        "best_bet_support_state": prediction_record.get("market_support", {}).get("best_bet_state", "unknown"),
    }


def record_postgame_outcome(
    *,
    config: AppConfig,
    game_id: str,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    source_urls: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    prediction_record = load_latest_prediction_record(config=config, game_id=game_id)
    learning_payload: dict[str, Any] = {
        "applied": False,
        "summary": "Prediction record unavailable; learning skipped.",
    }

    record: dict[str, Any] = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": game_id,
        "teams": {
            "home": home_team,
            "away": away_team,
        },
        "actual_result": {
            "home_score": int(home_score),
            "away_score": int(away_score),
            "home_win": bool(home_score > away_score),
            "total_runs": int(home_score + away_score),
        },
        "source_urls": source_urls or [],
        "notes": notes or [],
        "prediction_summary": None,
        "evaluation": None,
        "learning": learning_payload,
    }

    if prediction_record:
        record["prediction_summary"] = _build_prediction_summary(prediction_record)
        record["evaluation"] = _build_evaluation(
            prediction_record=prediction_record,
            home_score=home_score,
            away_score=away_score,
        )

        sub_model_predictions = extract_sub_model_predictions(prediction_record)
        if sub_model_predictions:
            game_result = GameResult(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                home_win=home_score > away_score,
                total_runs=home_score + away_score,
            )
            health_report = run_retraining_cycle(
                [game_result],
                [sub_model_predictions],
            )
            # Legacy synchronization (as requested in research report)
            try:
                legacy_preds = {
                    name: {"away_wp": 1.0 - prob, "predicted_score": "0-0"} 
                    for name, prob in sub_model_predictions.items()
                }
                self_learning.log_result(
                    game_id=game_id,
                    actual_winner=home_team if home_score > away_score else away_team,
                    actual_away_score=away_score,
                    actual_home_score=home_score,
                    predictions=legacy_preds
                )
            except Exception as e:
                # logger not available here but we don't want to crash
                pass

            learning_payload = {
                "applied": True,
                "model_count": len(sub_model_predictions),
                "overall_health": health_report.overall_health,
                "summary": health_report.summary,
                "updated_weights": _round_dict(health_report.updated_weights),
                "retired_models": health_report.retired_models,
            }
        else:
            learning_payload = {
                "applied": False,
                "summary": "Prediction record found but sub-model probabilities missing; learning skipped.",
            }

    record["learning"] = learning_payload

    target = Path(config.sources.postgame_results_jsonl)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False))
        fh.write("\n")

    summary = summarize_market_support_performance(config=config)
    write_market_support_performance_summary(config=config)
    update_review_report_with_market_support_summary(config=config, summary=summary)

    return record
