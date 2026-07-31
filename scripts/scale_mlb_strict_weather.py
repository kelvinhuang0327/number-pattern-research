#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.mlb_data.weather_scaling import scale_weather_coverage
from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.validator import validate_mlb_game_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Scale MLB STRICT_VALID via batch weather coverage.")
    parser.add_argument("--target-strict", type=int, default=200)
    parser.add_argument("--max-batches", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--min-gain-per-batch", type=int, default=20)
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    args = parser.parse_args()

    result = scale_weather_coverage(
        target_strict=args.target_strict,
        max_batches=args.max_batches,
        batch_size=args.batch_size,
        min_gain_per_batch=args.min_gain_per_batch,
        csv_path=args.csv_path,
    )
    rows = load_mlb_game_data(csv_path=args.csv_path, context_path="data/mlb_context")
    val = validate_mlb_game_data(rows)
    report = {
        "coverage_growth": {"before": result.strict_before, "after": result.strict_after, "delta": result.newly_strict},
        "strict_valid_rate": round(result.strict_after / max(1, len(rows)), 4),
        "weather_batch_efficiency": {
            "total_api_calls": result.api_calls,
            "cache_hit_rate": round(result.cache_hits / max(1, result.cache_hits + result.cache_misses), 4),
            "cache_hits": result.cache_hits,
            "cache_misses": result.cache_misses,
            "avg_latency_ms": result.avg_latency_ms,
            "batches_run": result.batches_run,
        },
        "status_distribution": {
            "STRICT_VALID": val.strict_valid_games,
            "RESEARCH_VALID": val.research_valid_games,
            "INVALID": val.invalid_games,
        },
        "batch_history": result.batch_history,
        "top_remaining_blocker": result.top_remaining_blocker,
        "status": result.status,
    }
    out = Path("data/wbc_backend/reports/mlb_weather_scale_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "strict_after": result.strict_after, "status": result.status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
