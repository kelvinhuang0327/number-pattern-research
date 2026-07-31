from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.wbc_pool_a import list_wbc_matches_a
from data.wbc_pool_b import list_wbc_matches_b
from data.wbc_pool_c import list_wbc_matches
from data.wbc_pool_d import list_wbc_matches_d
from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import AnalyzeRequest
from wbc_backend.models.ensemble import predict_matchup
from wbc_backend.pipeline.service import PredictionService
from wbc_backend.pipeline.wbc_rule_engine import apply_wbc_rules
from wbc_backend.reporting.strategy_replay_runtime_metadata import (
    prepare_runtime_strategy_metadata_request_kwargs,
)

OUT_PATH = Path("data/wbc_backend/reports/prediction_registry_replay.jsonl")


def _all_schedule_rows() -> list[dict[str, Any]]:
    return list_wbc_matches_a() + list_wbc_matches_b() + list_wbc_matches() + list_wbc_matches_d()


def _serialize_sub_models(sub_models: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for m in sub_models or []:
        rows.append(
            {
                "model_name": getattr(m, "model_name", ""),
                "home_win_prob": float(getattr(m, "home_win_prob", 0.5)),
                "away_win_prob": float(getattr(m, "away_win_prob", 0.5)),
                "confidence": float(getattr(m, "confidence", 0.5)),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build replay predictions for the registry.")
    parser.add_argument("--strategy-id", type=str, default=None)
    parser.add_argument("--strategy-metadata-registry", type=str, default=None)
    parser.add_argument("--current-lifecycle-state", type=str, default=None)
    parser.add_argument("--strict-strategy-metadata", action="store_true")
    args = parser.parse_args()

    cfg = AppConfig()
    service = PredictionService(cfg)
    rows = _all_schedule_rows()

    try:
        strategy_metadata_kwargs = prepare_runtime_strategy_metadata_request_kwargs(
            args.strategy_id,
            registry_path=args.strategy_metadata_registry,
            current_lifecycle_state=args.current_lifecycle_state,
            strict=args.strict_strategy_metadata,
        )
    except ValueError as exc:
        print(f"runtime strategy metadata blocked: {exc}")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    failures: list[str] = []
    with OUT_PATH.open("w", encoding="utf-8") as out:
        for g in rows:
            gid = str(g["game_id"]).upper()
            req = AnalyzeRequest(
                game_id=gid,
                line_total=7.5,
                line_spread_home=-1.5,
                **strategy_metadata_kwargs,
            )
            try:
                matchup = service._build_matchup(req)  # noqa: SLF001
                pred = predict_matchup(matchup, cfg.model)
                if matchup.tournament.upper().startswith("WBC"):
                    pred, _, _ = apply_wbc_rules(matchup, pred)
                # Enforce serving-boundary hard cap after all rule adjustments.
                pred.home_win_prob = max(0.15, min(0.85, float(pred.home_win_prob)))
                pred.away_win_prob = 1.0 - pred.home_win_prob
            except Exception as exc:
                failures.append(f"{gid}: {exc}")
                continue

            # Reconstructed pregame timestamp: 10 minutes before scheduled first pitch
            game_time = datetime.fromisoformat(str(g["game_time"]))
            recorded_at = game_time.astimezone(timezone.utc) - timedelta(minutes=10)
            row = {
                "recorded_at_utc": recorded_at.isoformat(),
                "game_id": gid,
                "prediction": {
                    "home_win_prob": float(pred.home_win_prob),
                    "away_win_prob": float(pred.away_win_prob),
                    "expected_home_runs": float(pred.expected_home_runs),
                    "expected_away_runs": float(pred.expected_away_runs),
                    "confidence_score": float(pred.confidence_score),
                    "sub_model_results": _serialize_sub_models(pred.sub_model_results),
                    "diagnostics": dict(pred.diagnostics or {}),
                },
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    print(f"wrote {count} replay predictions -> {OUT_PATH}")
    if failures:
        print(f"failures: {len(failures)}")
        for item in failures[:20]:
            print(" ", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
