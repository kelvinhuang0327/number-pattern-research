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

from wbc_backend.mlb_data.historical_odds_ingestion import (  # noqa: E402
    build_mlb_2025_historical_odds_timeline_asset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2025 MLB historical odds timeline canonical asset and QA report.")
    parser.add_argument("--output-path", default="data/mlb_context_sources/odds_timeline_canonical.jsonl")
    parser.add_argument("--qa-report-path", default="data/wbc_backend/reports/mlb_2025_odds_timeline_qa_report.json")
    parser.add_argument("--source-audit-path", default="data/wbc_backend/reports/mlb_odds_source_audit.json")
    parser.add_argument("--decision-lead-minutes", type=int, default=60)
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--fetch-external", action="store_true")
    args = parser.parse_args()

    summary = build_mlb_2025_historical_odds_timeline_asset(
        csv_path=args.csv_path,
        canonical_output_path=args.output_path,
        qa_report_path=args.qa_report_path,
        decision_lead_minutes=args.decision_lead_minutes,
        fetch_external=bool(args.fetch_external),
    )
    qa = json.loads(Path(args.qa_report_path).read_text(encoding="utf-8"))
    source_audit = [
        {
            "source_name": "Canonical local odds timeline sources",
            "interface": "data/mlb_context_sources/odds_timeline_canonical.jsonl + data/mlb_context_sources/odds_timeline.jsonl + data/tsl_odds_history.jsonl",
            "availability": any(
                Path(p).exists()
                for p in (
                    "data/mlb_context_sources/odds_timeline_canonical.jsonl",
                    "data/mlb_context_sources/odds_timeline.jsonl",
                    "data/tsl_odds_history.jsonl",
                )
            ),
            "historical_coverage": f"{qa.get('games_with_any_snapshot', 0)} games with snapshots",
            "granularity": "snapshot-level (mixed quality)",
            "timestamp_quality": "mixed; strict monotonicity validated in QA report",
            "cost_access_constraints": "in-repo local assets",
            "suitability": "research_only_unless_strict_coverage_passes",
        },
        {
            "source_name": "The Odds API v4 (external)",
            "interface": "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds",
            "availability": bool(os.getenv("ODDS_API_KEY")),
            "historical_coverage": "depends on account plan and retention",
            "granularity": "bookmaker snapshots",
            "timestamp_quality": "good when historical snapshots are available",
            "cost_access_constraints": "API key required; paid tiers for broad historical coverage",
            "suitability": "production_candidate",
        },
        {
            "source_name": "SportsDataIO MLB odds API (external)",
            "interface": "https://sportsdata.io/developers/api-documentation/mlb",
            "availability": bool(os.getenv("SPORTSDATAIO_API_KEY")),
            "historical_coverage": "vendor plan dependent",
            "granularity": "event + odds feed (plan-dependent)",
            "timestamp_quality": "vendor dependent",
            "cost_access_constraints": "paid subscription + API key",
            "suitability": "production_candidate",
        },
    ]

    qa_out = Path(args.qa_report_path)
    qa_out.parent.mkdir(parents=True, exist_ok=True)
    qa_out.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_out = Path(args.source_audit_path)
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps({"sources": source_audit}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "canonical_output_path": args.output_path,
                "qa_report_path": args.qa_report_path,
                "source_audit_path": args.source_audit_path,
                "total_games": summary.total_games,
                "games_strict_valid_count": summary.games_strict_valid_count,
                "coverage_rate": summary.coverage_rate,
                "mapping_success_rate": summary.mapping_success_rate,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
