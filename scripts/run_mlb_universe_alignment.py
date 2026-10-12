#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.mlb_data.ids import make_mlb_game_id  # noqa: E402


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _build_prediction_universe(csv_path: Path) -> set[str]:
    df = pd.read_csv(csv_path)
    return set(
        df.apply(
            lambda r: make_mlb_game_id(
                str(r.get("Date", "")),
                str(r.get("Start Time (EDT)", "")),
                str(r.get("Away", "")),
                str(r.get("Home", "")),
            ),
            axis=1,
        )
    )


def _clv_counts(canonical_rows: list[dict[str, Any]]) -> dict[str, int]:
    pos = zero = neg = unavailable = 0
    for r in canonical_rows:
        d = r.get("decision_home_ml")
        c = r.get("closing_home_ml")
        if d is None or c is None:
            unavailable += 1
            continue
        # American -> implied probability
        def imp(x: float) -> float:
            x = float(x)
            return abs(x) / (abs(x) + 100.0) if x < 0 else 100.0 / (x + 100.0)

        clv = imp(c) - imp(d)
        if clv > 0:
            pos += 1
        elif clv < 0:
            neg += 1
        else:
            zero += 1
    return {"positive": pos, "zero": zero, "negative": neg, "unavailable": unavailable}


def main() -> None:
    csv_path = Path("data/mlb_2025/mlb_odds_2025_real.csv")
    canonical_path = Path("data/mlb_context_sources/odds_timeline_canonical.jsonl")
    out_path = Path("data/wbc_backend/reports/mlb_universe_alignment_report.json")

    prediction_ids = _build_prediction_universe(csv_path)
    canonical_rows = _load_jsonl(canonical_path)
    canonical_ids = {str(r.get("game_id", "")).strip() for r in canonical_rows if str(r.get("game_id", "")).strip()}
    overlap_ids = prediction_ids & canonical_ids

    mapping_success = len(overlap_ids) / max(1, len(prediction_ids))
    canonical_coverage = len(canonical_ids) / max(1, len(prediction_ids))

    providers = {
        "the_odds_api": bool(os.getenv("ODDS_API_KEY")),
        "sportsdataio": bool(os.getenv("SPORTSDATAIO_API_KEY")),
    }
    provider_ready = any(providers.values())

    strategy_options = [
        {
            "name": "expand_timeline_to_2025_full_universe",
            "target": ">=80% overlap",
            "feasibility_now": "blocked" if not provider_ready else "partial",
            "pros": "keeps current research/backtest universe unchanged",
            "cons": "requires paid historical odds provider with timestamped snapshots",
        },
        {
            "name": "shrink_eval_universe_to_timeline_supported_subset",
            "target": "100% of subset has timeline",
            "feasibility_now": "limited",
            "pros": "immediate CLV pipeline validation on supported games",
            "cons": "currently 0 overlap with 2025 prediction universe",
        },
        {
            "name": "hybrid_mode_debug_plus_production",
            "target": "separate debug universe and production universe",
            "feasibility_now": "ready",
            "pros": "unblocks asset QA now while preserving strict production gate",
            "cons": "does not solve scale until external 2025 timeline ingestion is connected",
        },
    ]

    chosen = "hybrid_mode_debug_plus_production"

    sandbox = {
        "timeline_games": len(canonical_rows),
        "timeline_clv_distribution": _clv_counts(canonical_rows),
        "decision_label_behavior_verification": "covered_by_unit_tests_only (rule-path valid, full label eval needs real outcomes + model predictions on same universe)",
    }

    payload = {
        "prediction_universe_games": len(prediction_ids),
        "timeline_universe_games": len(canonical_ids),
        "overlap_games": len(overlap_ids),
        "mapping_success_rate": round(mapping_success, 4),
        "coverage_pct_vs_prediction_universe": round(canonical_coverage, 4),
        "providers_ready": providers,
        "strategy_options": strategy_options,
        "chosen_strategy": chosen,
        "next_blocker": "missing_historical_2025_timestamped_odds_provider" if not provider_ready else "ingestion_scaling",
        "sandbox_validation": sandbox,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report_path": str(out_path), "chosen_strategy": chosen, "mapping_success_rate": payload["mapping_success_rate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
