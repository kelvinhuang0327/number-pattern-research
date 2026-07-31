"""
P29 — External Data Contract Builder
paper_only=true / diagnostic_only=true

Designs the data contracts needed to break the 0.244 Brier ceiling.
No actual data is fetched. All contracts are design documents only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DATE = "2026-05-20"
os.makedirs("data/paper_recommendations", exist_ok=True)
os.makedirs("report", exist_ok=True)

COMMON_META = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_proposal": False,
    "promotion_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "live_api_call": False,
    "crawler_modified": False,
    "no_data_fetched": True,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "date": DATE,
}

# ── Contract helper ────────────────────────────────────────────────────────────

def field_def(name, typ, nullable, description, fallback, leakage_risk, freshness_sla, source, backtest_avail, prod_ready):
    return {
        "field_name": name, "type": typ, "nullable": nullable,
        "description": description, "fallback_rule": fallback,
        "leakage_risk": leakage_risk, "freshness_sla_hours": freshness_sla,
        "source_trace": source, "backtest_availability": backtest_avail,
        "production_readiness": prod_ready,
    }


# ── Contract 1: Starting Pitcher ──────────────────────────────────────────────
pitcher_contract = {
    "contract_name": "STARTING_PITCHER_PREGAME",
    "version": "v1.0-design",
    "purpose": "Capture SP quality and form before game start",
    "estimated_brier_improvement": {"low": 0.005, "high": 0.015, "unit": "Brier_points"},
    "fields": [
        field_def("game_id",          "str",   False, "Unique game identifier",
                  "N/A - required",    "NONE",  4,   "internal",           "YES_FROM_SCHEDULE",  "READY"),
        field_def("pitcher_name",     "str",   False, "Probable starter name (official lineup)",
                  "UNKNOWN",           "MEDIUM-confirm before first pitch",  2,
                  "MLB.com/API/rotowire", "PARTIAL-historical", "NEEDS_SOURCING"),
        field_def("pitcher_hand",     "str",   True,  "Pitcher handedness (L/R)",
                  "UNKNOWN",           "LOW",   24,  "Baseball-Reference/FanGraphs", "YES-from_stats", "NEEDS_SOURCING"),
        field_def("season_era",       "float", True,  "Season ERA up to game date (pre-game only)",
                  "league_avg=4.20",   "HIGH-must use season-to-date only",  24,
                  "FanGraphs/BRef",    "YES-season_to_date",  "NEEDS_SOURCING"),
        field_def("season_fip",       "float", True,  "Season FIP (ERA proxy, better regressor)",
                  "league_avg=4.20",   "HIGH-season_to_date_only",  24,
                  "FanGraphs",         "YES-season_to_date",  "NEEDS_SOURCING"),
        field_def("last3_era",        "float", True,  "ERA over last 3 starts",
                  "season_era",        "HIGH-last3_within_training_window",  4,
                  "FanGraphs/BRef",    "PARTIAL",               "NEEDS_SOURCING"),
        field_def("days_rest",        "int",   True,  "Days since last appearance",
                  "5",                 "LOW",   2,   "schedule",           "YES",                "NEEDS_SOURCING"),
        field_def("pitch_count_last", "int",   True,  "Pitch count in last start",
                  "90",                "LOW",   24,  "Gameday API",        "PARTIAL",            "NEEDS_SOURCING"),
        field_def("injury_flag",      "bool",  False, "SP scratched or injured (pre-game)",
                  "False",             "MEDIUM-must be before game time",  1,
                  "Rotoworld/Twitter", "NO-real_time_only",   "NEEDS_SOURCING"),
        field_def("snapshot_ts",      "str",   False, "ISO timestamp of data capture",
                  "N/A - required",    "NONE",  0,   "internal",           "YES",                "READY"),
    ],
    "anti_leakage_rules": [
        "NEVER use post-game stats (H, ER, IP from today's game)",
        "NEVER use injury info revealed after bet cutoff",
        "ALWAYS verify snapshot_ts < game_start_time",
        "Season stats must be computed from games with date < game_date",
        "last3 stats must exclude today's game",
    ],
    "free_data_sources": [
        "Baseball Reference (free, scraping OK for research)",
        "FanGraphs (free tier, season stats)",
        "MLB Stats API (official, free, pitcher game logs)",
    ],
}

# ── Contract 2: Bullpen ───────────────────────────────────────────────────────
bullpen_contract = {
    "contract_name": "BULLPEN_PREGAME",
    "version": "v1.0-design",
    "purpose": "Capture bullpen fatigue and availability before game",
    "estimated_brier_improvement": {"low": 0.002, "high": 0.007, "unit": "Brier_points"},
    "fields": [
        field_def("bullpen_ip_1d",    "float", False, "Bullpen innings pitched yesterday",
                  "0.0",              "LOW",   2,   "MLB Stats API",   "PARTIAL",  "NEEDS_SOURCING"),
        field_def("bullpen_ip_3d",    "float", False, "Bullpen IP last 3 days",
                  "3.0",              "LOW",   2,   "MLB Stats API",   "YES",      "NEEDS_SOURCING"),
        field_def("bullpen_ip_7d",    "float", False, "Bullpen IP last 7 days",
                  "7.0",              "LOW",   24,  "MLB Stats API",   "YES",      "NEEDS_SOURCING"),
        field_def("closer_available", "bool",  False, "Primary closer available",
                  "True",             "MEDIUM-pre-game flag",  1,
                  "Rotoworld",        "NO-real_time_only",     "NEEDS_SOURCING"),
        field_def("fatigue_score",    "float", True,  "Custom fatigue: IP_7d / (7*2.0) normalized",
                  "0.5",              "LOW",   24,  "computed_from_ip", "YES",     "COMPUTABLE_FROM_API"),
        field_def("season_bullpen_era", "float", True, "Team bullpen ERA season-to-date",
                  "league_avg=4.10",  "HIGH-season_to_date",   24,
                  "FanGraphs",        "YES",                   "NEEDS_SOURCING"),
        field_def("snapshot_ts",      "str",   False, "ISO timestamp",
                  "N/A",              "NONE",  0,   "internal",        "YES",     "READY"),
    ],
    "anti_leakage_rules": [
        "IP counts from today's game must be excluded",
        "snapshot_ts must be < game_start_time",
        "Closer availability is a real-time signal — must be sourced before first pitch",
    ],
    "free_data_sources": [
        "MLB Stats API (game logs, bullpen usage)",
        "FanGraphs team bullpen stats",
    ],
}

# ── Contract 3: Batting Form ──────────────────────────────────────────────────
batting_contract = {
    "contract_name": "BATTING_FORM_PREGAME",
    "version": "v1.0-design",
    "purpose": "Capture recent offensive form to supplement season averages",
    "estimated_brier_improvement": {"low": 0.003, "high": 0.010, "unit": "Brier_points"},
    "fields": [
        field_def("team_woba_season",  "float", True,  "Team wOBA season-to-date",
                  "league_avg=0.317",  "HIGH-season_to_date",  24, "FanGraphs", "YES", "NEEDS_SOURCING"),
        field_def("team_woba_7d",      "float", True,  "Team wOBA last 7 days",
                  "team_woba_season",  "HIGH-rolling_window",   4,  "BRef/FG",  "PARTIAL", "NEEDS_SOURCING"),
        field_def("team_woba_14d",     "float", True,  "Team wOBA last 14 days",
                  "team_woba_season",  "HIGH-rolling_window",   24, "BRef/FG",  "YES",     "NEEDS_SOURCING"),
        field_def("team_k_pct",        "float", True,  "Team strikeout rate season-to-date",
                  "league_avg=0.228",  "HIGH-season_to_date",   24, "FanGraphs", "YES",    "NEEDS_SOURCING"),
        field_def("team_bb_pct",       "float", True,  "Team walk rate season-to-date",
                  "league_avg=0.085",  "HIGH-season_to_date",   24, "FanGraphs", "YES",    "NEEDS_SOURCING"),
        field_def("vs_hand_split",     "str",   True,  "Offense vs R/L pitcher (facing today SP hand)",
                  "null",              "HIGH-requires SP hand + team splits", 24, "FG",     "PARTIAL", "NEEDS_SOURCING"),
        field_def("snapshot_ts",       "str",   False, "ISO timestamp",
                  "N/A",               "NONE",  0,  "internal",          "YES",    "READY"),
    ],
    "anti_leakage_rules": [
        "rolling_7d/14d must NOT include today's game",
        "season stats must be computed from games with date < game_date",
        "vs_hand_split requires SP hand to be known (not post-game)",
    ],
    "free_data_sources": ["FanGraphs team splits (free)", "Baseball Reference"],
}

# ── Contract 4: Lineup / Injury Proxy ────────────────────────────────────────
lineup_contract = {
    "contract_name": "LINEUP_INJURY_PROXY_PREGAME",
    "version": "v1.0-design",
    "purpose": "Capture lineup completeness and injury uncertainty pre-game",
    "estimated_brier_improvement": {"low": 0.002, "high": 0.006, "unit": "Brier_points",
                                     "note": "High uncertainty; confirmed lineup often unavailable early"},
    "fields": [
        field_def("confirmed_lineup_flag", "bool", False, "Official lineup submitted",
                  "False",             "MEDIUM-pre-game only",  1,   "MLB API",    "NO-real_time", "NEEDS_SOURCING"),
        field_def("missing_key_bats",  "int",   False, "Number of top-3 by wOBA on IL",
                  "0",                 "HIGH-requires IL list", 2,   "MLB API",    "PARTIAL",      "NEEDS_SOURCING"),
        field_def("injury_uncertainty","float", False, "Fraction of lineup spots uncertain",
                  "0.0",               "HIGH-pre-game only",    1,   "Rotoworld",  "NO",           "NEEDS_SOURCING"),
        field_def("stale_lineup_flag", "bool",  False, "Last known lineup > 4h before game",
                  "True",              "LOW",   0,   "internal",          "YES",              "COMPUTABLE"),
        field_def("snapshot_ts",       "str",   False, "ISO timestamp",
                  "N/A",               "NONE",  0,   "internal",          "YES",              "READY"),
    ],
    "anti_leakage_rules": [
        "NEVER use post-game lineup or injury updates",
        "confirmed_lineup_flag: only set True after official submission",
        "stale_lineup_flag: set True if data > 4h old at bet time",
    ],
    "free_data_sources": ["MLB Stats API (lineups)", "Rotoworld (injuries, fragile)"],
}

# ── Contract 5: Park / Weather ────────────────────────────────────────────────
park_contract = {
    "contract_name": "PARK_WEATHER_PREGAME",
    "version": "v1.0-design",
    "purpose": "Park factor and weather adjustments for run environment",
    "estimated_brier_improvement": {"low": 0.001, "high": 0.003, "unit": "Brier_points"},
    "fields": [
        field_def("park_factor_runs",  "float", False, "5-year park factor for runs (100=neutral)",
                  "100.0",             "LOW",   8760, "FanGraphs/BRef",    "YES-stable",     "NEEDS_SOURCING"),
        field_def("wind_mph",          "float", True,  "Wind speed (mph)",
                  "0.0",               "LOW",   2,   "OpenWeatherMap/NWS", "NO",             "NEEDS_SOURCING"),
        field_def("wind_direction",    "str",   True,  "Wind direction (IN/OUT/Cross/Calm)",
                  "CALM",              "LOW",   2,   "OpenWeatherMap",     "NO",             "NEEDS_SOURCING"),
        field_def("temperature_f",     "float", True,  "Temperature at first pitch (°F)",
                  "72.0",              "LOW",   2,   "OpenWeatherMap",     "NO",             "NEEDS_SOURCING"),
        field_def("roof_status",       "str",   True,  "OPEN/CLOSED/RETRACTABLE",
                  "OUTDOOR",           "LOW",   2,   "MLB schedule",       "PARTIAL",        "NEEDS_SOURCING"),
        field_def("snapshot_ts",       "str",   False, "ISO timestamp",
                  "N/A",               "NONE",  0,   "internal",          "YES",            "READY"),
    ],
    "anti_leakage_rules": [
        "Park factor must be computed from prior seasons only",
        "Weather must be forecast (not actual) at bet time",
        "Wind direction: categorical, not continuous, to avoid overfitting",
    ],
    "free_data_sources": ["OpenWeatherMap free tier", "NWS API (free)", "FanGraphs park factors"],
}

# ── Feature Readiness Matrix ──────────────────────────────────────────────────
readiness_matrix = {
    "market_odds_baseline": {
        "status": "CURRENTLY_AVAILABLE",
        "current_brier": 0.244354,
        "estimated_improvement": {"low": 0.0, "high": 0.0},
        "note": "Pure market odds achieve 0.2444 — baseline ceiling without external data",
    },
    "run_line_signal": {
        "status": "REPO_PROXY_AVAILABLE",
        "current_brier_proxy": "P28 tested: +0.000485 vs LogReg (no improvement)",
        "estimated_improvement": {"low": 0.0, "high": 0.001},
        "note": "RL odds already in CSV, but P28 tested and found no improvement",
    },
    "starting_pitcher": {
        "status": "EXTERNAL_REQUIRED",
        "estimated_improvement": {"low": 0.005, "high": 0.015},
        "source": "MLB Stats API / FanGraphs (free)",
        "leakage_risk": "HIGH - must enforce season_to_date only",
        "backtest_feasibility": "YES - FanGraphs has historical season stats",
    },
    "bullpen_fatigue": {
        "status": "EXTERNAL_REQUIRED",
        "estimated_improvement": {"low": 0.002, "high": 0.007},
        "source": "MLB Stats API game logs",
        "leakage_risk": "LOW",
        "backtest_feasibility": "YES",
    },
    "batting_form_rolling": {
        "status": "EXTERNAL_REQUIRED",
        "estimated_improvement": {"low": 0.003, "high": 0.010},
        "source": "FanGraphs / BRef",
        "leakage_risk": "HIGH - rolling window must respect date cutoff",
        "backtest_feasibility": "YES",
    },
    "lineup_injury_proxy": {
        "status": "EXTERNAL_REQUIRED",
        "estimated_improvement": {"low": 0.002, "high": 0.006},
        "source": "MLB API / Rotoworld",
        "leakage_risk": "HIGH - real-time signal, hard to backtest",
        "backtest_feasibility": "PARTIAL - IL list available historically",
    },
    "park_weather": {
        "status": "EXTERNAL_REQUIRED",
        "estimated_improvement": {"low": 0.001, "high": 0.003},
        "source": "OpenWeatherMap / FanGraphs",
        "leakage_risk": "LOW - park factor stable; weather forecast OK",
        "backtest_feasibility": "PARTIAL - historical weather not always free",
    },
    "prohibited_features": [
        "postgame stats (ERA/H/ER from today's game)",
        "closing_odds as pregame feature (future leakage)",
        "lineup updates after bet timestamp",
        "result-derived fields (runs scored, win probability after game start)",
        "unlicensed scraped PII data",
    ],
    "combined_estimated_ceiling": {
        "with_pitcher_only": {"brier_estimate": 0.234, "improvement_vs_market": 0.010},
        "with_pitcher_and_batting": {"brier_estimate": 0.228, "improvement_vs_market": 0.016},
        "with_full_external_stack": {"brier_estimate": 0.222, "improvement_vs_market": 0.022},
        "caveat": "Estimates are optimistic upper bounds; real gains may be lower due to proxy quality",
    },
}

# ── Write artifacts ───────────────────────────────────────────────────────────
contracts = {
    "starting_pitcher": pitcher_contract,
    "bullpen": bullpen_contract,
    "batting_form": batting_contract,
    "lineup_injury_proxy": lineup_contract,
    "park_weather": park_contract,
}

a_contract = {
    **COMMON_META,
    "artifact": "P29_EXTERNAL_DATA_CONTRACT",
    "purpose": "Design document for external features needed to break Brier ceiling of 0.244",
    "current_ceiling": {
        "brier_with_csv_only": 0.244354,
        "brier_with_orchestrator": 0.248703,
        "gap_to_target_0_24": 0.004354,
    },
    "contracts": contracts,
    "implementation_notes": [
        "NO data is fetched in this script — design document only",
        "MLB Stats API is free and official: https://statsapi.mlb.com",
        "FanGraphs CSV export is free for research use",
        "All contracts must enforce snapshot_ts < game_start_time",
        "Backtest feasibility rating: YES=historical data freely available, PARTIAL=some available, NO=real-time only",
    ],
}
with open("data/paper_recommendations/p29_external_data_contract_20260520.json", "w") as f:
    json.dump(a_contract, f, indent=2, ensure_ascii=False)

a_matrix = {
    **COMMON_META,
    "artifact": "P29_FEATURE_READINESS_MATRIX",
    "readiness_matrix": readiness_matrix,
    "summary": {
        "currently_available": ["market_odds_baseline"],
        "repo_proxy_available": ["run_line_signal"],
        "external_required": ["starting_pitcher", "bullpen_fatigue", "batting_form_rolling",
                               "lineup_injury_proxy", "park_weather"],
        "not_safe_to_use": readiness_matrix["prohibited_features"],
        "highest_impact_feature": "starting_pitcher",
        "lowest_effort_sourcing": "park_factor (stable, multi-year, FanGraphs CSV)",
        "feasibility_for_backtest": "starting_pitcher + bullpen + batting_form are all feasible for historical backtest",
    },
    "p29_decision": {
        "orchestrator_noise_found": True,
        "simplification_candidate": "P29_ORCHESTRATOR_NOISE_REMOVAL_CANDIDATE_FOUND",
        "external_data_contract_complete": True,
        "external_data_contract_status": "P29_EXTERNAL_DATA_CONTRACT_READY",
        "ceiling_analysis": "P29_EXTERNAL_FEATURES_REQUIRED_TO_BREAK_CEILING",
        "combined_final_classification": [
            "P29_ORCHESTRATOR_NOISE_REMOVAL_CANDIDATE_FOUND",
            "P29_EXTERNAL_DATA_CONTRACT_READY",
            "P29_EXTERNAL_FEATURES_REQUIRED_TO_BREAK_CEILING",
        ],
    },
}
with open("data/paper_recommendations/p29_feature_readiness_matrix_20260520.json", "w") as f:
    json.dump(a_matrix, f, indent=2, ensure_ascii=False)

print("External data contract and feature readiness matrix written.")
print("Contracts: SP, Bullpen, Batting, Lineup, Park/Weather")
print("Final classification: P29_ORCHESTRATOR_NOISE_REMOVAL_CANDIDATE_FOUND + P29_EXTERNAL_DATA_CONTRACT_READY")
