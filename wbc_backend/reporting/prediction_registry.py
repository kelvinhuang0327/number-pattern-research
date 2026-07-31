from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import AnalyzeRequest, Matchup
from wbc_backend.reporting.strategy_replay_instrumentation import build_prediction_write_path_replay_metadata


def _issue_payload(issues: list[Any]) -> list[dict[str, Any]]:
    payload = []
    for issue in issues:
        if is_dataclass(issue):
            payload.append(asdict(issue))
        else:
            payload.append(
                {
                    "code": getattr(issue, "code", "unknown"),
                    "message": getattr(issue, "message", str(issue)),
                    "severity": getattr(issue, "severity", "INFO"),
                }
            )
    return payload


def _market_support_summary(top_bets: list[Any], portfolio_metrics: dict[str, Any] | None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for bet in top_bets:
        state = str(getattr(bet, "market_support_state", "") or "unknown")
        counts[state] = counts.get(state, 0) + 1

    primary = "unknown"
    if portfolio_metrics and portfolio_metrics.get("market_support_profile"):
        primary = str(portfolio_metrics.get("market_support_profile"))
    elif counts:
        primary = max(counts.items(), key=lambda item: item[1])[0]

    return {
        "primary": primary,
        "breakdown": counts,
        "tilt": str((portfolio_metrics or {}).get("market_support_tilt", "neutral")),
        "best_bet_state": str(getattr(top_bets[0], "market_support_state", "unknown")) if top_bets else "unknown",
    }


def append_prediction_record(
    *,
    config: AppConfig,
    request: AnalyzeRequest,
    matchup: Matchup,
    verification: Any,
    deployment_gate: Any,
    game_output: Any,
    pred: Any,
    sim: Any,
    top_bets: list[Any],
    decision_report: Any,
    calibration_metrics: dict[str, Any] | None,
    portfolio_metrics: dict[str, Any] | None,
) -> Path:
    target = Path(config.sources.prediction_registry_jsonl)
    target.parent.mkdir(parents=True, exist_ok=True)

    request_payload = asdict(request)
    replay_payload = build_prediction_write_path_replay_metadata(
        {
            "game_id": request.game_id,
            "request": request_payload,
            "verification": {
                "canonical_game_id": getattr(verification, "canonical_game_id", None),
            },
        }
    )

    record = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": request.game_id,
        "request": request_payload,
        "teams": {
            "away": matchup.away.team,
            "home": matchup.home.team,
        },
        "verification": {
            "status": getattr(verification, "status", "unknown"),
            "canonical_game_id": getattr(verification, "canonical_game_id", None),
            "used_fallback_lineup": getattr(verification, "used_fallback_lineup", False),
            "issues": _issue_payload(getattr(verification, "issues", [])),
        },
        "deployment_gate": deployment_gate.to_dict() if hasattr(deployment_gate, "to_dict") else deployment_gate,
        "game_output": asdict(game_output),
        "prediction": asdict(pred),
        "simulation": asdict(sim),
        "top_bets": [asdict(bet) for bet in top_bets],
        "market_support": _market_support_summary(top_bets, portfolio_metrics),
        "decision_report": asdict(decision_report) if is_dataclass(decision_report) else decision_report,
        "calibration_metrics": calibration_metrics or {},
        "portfolio_metrics": portfolio_metrics or {},
        **replay_payload,
    }

    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False))
        fh.write("\n")

    return target
