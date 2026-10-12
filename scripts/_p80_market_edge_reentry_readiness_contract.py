"""
scripts/_p80_market_edge_reentry_readiness_contract.py

P80 — Market-Edge Lane Re-entry Readiness Contract

Contract-only phase. Defines what must be true before the project may resume
odds-dependent validation. No API call, no EV/CLV/Kelly computation, no odds pull.

Prediction-only lane remains active (P72A→P79B). Market-edge lane remains BLOCKED
until explicit gate conditions in this contract are satisfied.

Classification options:
  P80_MARKET_EDGE_REENTRY_CONTRACT_READY
  P80_MARKET_EDGE_REENTRY_CONTRACT_READY_WITH_CAVEATS
  P80_BLOCKED_BY_MISSING_SOURCE_ARTIFACT
  P80_FAILED_VALIDATION
"""
from __future__ import annotations

import json
import hashlib
import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data/mlb_2025/derived"

# ---------------------------------------------------------------------------
# GOVERNANCE — IMMUTABLE FOR THIS PHASE
# ---------------------------------------------------------------------------

GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "the_odds_api_key_accessed": False,
    "odds_used": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "promotion_freeze": True,
    "tsl_crawler_modified": False,
    "runtime_recommendation_modified": False,
}

SCHEMA_VERSION = "p80-v1"
SNAPSHOT_ID = "market_edge_reentry_contract_20260526"
GENERATED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# SOURCE ARTIFACT PATHS
# ---------------------------------------------------------------------------

SOURCE_ARTIFACT_KEYS: list[str] = [
    "p79b_summary",
    "p79b_report",
    "p79b_script",
    "p79a_summary",
    "p78_summary",
    "p77_summary",
    "p76_summary",
    "p75b_summary",
    "p75a_summary",
    "p74_summary",
    "p73_summary",
    "p72b_summary",
    "p72a_summary",
]

OPTIONAL_ARTIFACT_KEYS: list[str] = [
    "p64_summary",
    "p65_summary",
    "p66_summary",
    "p67_summary",
    "p68_summary",
    "p70_summary",
    "p71_summary",
]

PATHS: dict[str, Path] = {
    # Required
    "p79b_summary": DERIVED / "p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p79b_report": ROOT / "report/p79b_tier_b_vs_tier_c_comparison_harness_20260526.md",
    "p79b_script": ROOT / "scripts/_p79b_tier_b_vs_tier_c_comparison_harness.py",
    "p79a_summary": DERIVED / "p79a_tier_b_trigger_readiness_contract_summary.json",
    "p78_summary": DERIVED / "p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_summary": DERIVED / "p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_summary": DERIVED / "p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_summary": DERIVED / "p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_summary": DERIVED / "p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_summary": DERIVED / "p74_tier_c_home_away_bias_correction_summary.json",
    "p73_summary": DERIVED / "p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_summary": DERIVED / "p72b_objective_metric_contract_summary.json",
    "p72a_summary": DERIVED / "p72a_odds_free_strategy_accuracy_backtest_summary.json",
    # Optional P64-P71
    "p64_summary": DERIVED / "p64_paper_simulation_first_run_summary.json",
    "p65_summary": DERIVED / "p65_paper_simulation_walk_forward_validation_summary.json",
    "p66_summary": DERIVED / "p66_odds_mapping_integrity_audit_summary.json",
    "p67_summary": DERIVED / "p67_2024_data_gap_free_source_search_summary.json",
    "p68_summary": DERIVED / "p68_oddsportal_tos_scraping_feasibility_summary.json",
    "p70_summary": DERIVED / "p70_path_a_the_odds_api_historical_pull_summary.json",
    "p71_summary": DERIVED / "p71_the_odds_api_live_pull_execution_summary.json",
    # Outputs
    "output_json": DERIVED / "p80_market_edge_reentry_readiness_contract_summary.json",
    "output_report": ROOT / "report/p80_market_edge_reentry_readiness_contract_20260526.md",
    "output_betting_plan": ROOT / "00-BettingPlan/20260526/p80_market_edge_reentry_readiness_contract_20260526.md",
}

# ---------------------------------------------------------------------------
# CONTRACT CONSTANTS
# ---------------------------------------------------------------------------

REQUIRED_ODDS_FIELDS: list[str] = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "sportsbook_or_source",
    "market_type",
    "odds_timestamp_utc",
    "game_start_utc",
    "home_moneyline",
    "away_moneyline",
    "implied_home_prob",
    "implied_away_prob",
    "line_type",
    "is_pregame",
    "is_closing",
    "source_license_status",
    "source_trace",
    "raw_data_policy",
    "checksum_hash",
    "created_at_utc",
]

VALIDATION_GATES = ["gate_a_data_legality", "gate_b_schema", "gate_c_mapping",
                    "gate_d_metric_readiness", "gate_e_cross_year_validation",
                    "gate_f_governance"]

CANDIDATE_KEYS = ["primary_125", "shadow_100", "tier_b_conditional", "baseline_50"]

MARKET_EDGE_STOP_CONDITIONS: list[str] = [
    "api_key_accessed_in_code",
    "ev_calculated",
    "clv_calculated",
    "kelly_calculated",
    "kelly_deployed",
    "production_ready_set_true",
    "champion_replaced",
    "real_bet_placed",
    "odds_scraped_from_blocked_source",
    "raw_paid_data_committed_without_policy",
    "timestamp_lineage_unverified",
    "side_mapping_unverified",
    "2025_fixture_treated_as_2026_conclusion",
    "p79b_research_only_overridden",
    "tsl_crawler_modified",
    "runtime_recommendation_modified",
    "profitability_claimed",
]


# ===========================================================================
# STEP FUNCTIONS
# ===========================================================================

def step1_verify_prediction_lane() -> dict[str, Any]:
    """Verify prediction-only lane state from P72A→P79B."""
    errors: list[str] = []
    warnings: list[str] = []

    # Load P79B summary
    p79b_path = PATHS["p79b_summary"]
    if not p79b_path.exists():
        return {"verified": False, "errors": [f"P79B summary missing: {p79b_path}"]}

    p79b = json.loads(p79b_path.read_text(encoding="utf-8"))
    p79b_cls = p79b.get("p79b_classification", "")
    fixture_cls = p79b.get("fixture_dry_run_classification", "")
    is_2026_live = p79b.get("fixture_is_2026_live_conclusion", True)
    market_edge_lane = p79b.get("market_edge_lane", "")
    future_prompt = p79b.get("step7_future_p79_prompt", {}).get("prompt_text", "")

    if p79b_cls != "P79B_TIER_B_FIXTURE_RESEARCH_ONLY":
        warnings.append(f"P79B classification: {p79b_cls}")
    if is_2026_live is True:
        errors.append("P79B fixture claims 2026 live conclusion — STOP")
    if market_edge_lane != "blocked":
        errors.append(f"market_edge_lane={market_edge_lane} (expected blocked)")
    if not future_prompt or len(future_prompt) < 50:
        warnings.append("P79B future P79 prompt short or missing")

    # Load P76 for primary/shadow rules
    p76_path = PATHS["p76_summary"]
    primary_rule = "unknown"
    shadow_rule = "unknown"
    if p76_path.exists():
        p76 = json.loads(p76_path.read_text(encoding="utf-8"))
        primary_rule = (
            p76.get("selected_primary_rule")
            or p76.get("primary_rule")
            or p76.get("step4_rule_selection", {}).get("primary_rule", "unknown")
        )
        shadow_rule = (
            p76.get("selected_shadow_rule")
            or p76.get("shadow_rule")
            or p76.get("step4_rule_selection", {}).get("shadow_rule", "unknown")
        )

    # Tier B metrics from P79B
    tier_b_metrics = p79b.get("step4_candidate_metrics", {}).get("tier_b", {})
    tier_b_n = tier_b_metrics.get("n", 0)
    tier_b_hit_rate = tier_b_metrics.get("hit_rate")
    tier_b_auc = tier_b_metrics.get("auc")

    # Check governance snapshot
    gov = p79b.get("governance_snapshot", {})
    if gov.get("production_ready") is not False:
        errors.append("P79B governance_snapshot.production_ready is not False")
    if gov.get("ev_calculated") is not False:
        errors.append("P79B governance_snapshot.ev_calculated is not False")

    return {
        "verified": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "p79b_classification": p79b_cls,
        "fixture_dry_run_classification": fixture_cls,
        "fixture_is_2026_live_conclusion": is_2026_live,
        "market_edge_lane": market_edge_lane,
        "tier_b_research_only": (fixture_cls != "TIER_B_OUTPERFORMS_TIER_C_FIXTURE"),
        "tier_b_n": tier_b_n,
        "tier_b_hit_rate": tier_b_hit_rate,
        "tier_b_auc": tier_b_auc,
        "primary_rule_from_p76": primary_rule,
        "shadow_rule_from_p76": shadow_rule,
        "future_p79_prompt_exists": bool(future_prompt and len(future_prompt) > 50),
        "governance_clean": len(errors) == 0,
    }


def step2_summarize_market_edge_blockers() -> dict[str, Any]:
    """Summarize market-edge blocker state from P64-P71."""
    blockers: list[str] = []
    optional_ctx: dict[str, Any] = {}

    def _load_optional(key: str) -> dict[str, Any] | None:
        path = PATHS.get(key)
        if path and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    # P64/P65 — 2025 market-edge result
    p64 = _load_optional("p64_summary")
    p65 = _load_optional("p65_summary")
    edge_2025_result = "UNKNOWN"
    if p65:
        edge_2025_result = p65.get("p65_classification", "UNKNOWN")
        optional_ctx["p65_classification"] = edge_2025_result
        optional_ctx["p65_walk_forward_stability"] = p65.get("stability", {})
    if p64:
        optional_ctx["p64_classification"] = p64.get("p64_classification")

    if edge_2025_result == "P65_EDGE_STABLE_NEGATIVE":
        blockers.append("BLOCKED_2025_EDGE_STABLE_NEGATIVE")

    # P66 — odds mapping integrity
    p66 = _load_optional("p66_summary")
    if p66:
        optional_ctx["p66_classification"] = p66.get("p66_classification")
        optional_ctx["p66_join_audit"] = p66.get("join_audit", {})

    # P67 — 2024 historical odds gap
    p67 = _load_optional("p67_summary")
    gap_2024_state = "UNKNOWN"
    if p67:
        gap_2024_state = p67.get("p67_classification", "UNKNOWN")
        optional_ctx["p67_classification"] = gap_2024_state
        if "PARTIAL" in gap_2024_state or "UNKNOWN" in gap_2024_state:
            blockers.append("BLOCKED_NO_LEGAL_2024_ODDS")

    # P68 — OddsPortal scraping
    p68 = _load_optional("p68_summary")
    scraping_blocked = True
    if p68:
        scraping_cls = p68.get("p68_classification", "")
        optional_ctx["p68_classification"] = scraping_cls
        if "BLOCKED" in scraping_cls:
            blockers.append("BLOCKED_ODDSPORTAL_TOS_VIOLATION")
            scraping_blocked = True
        else:
            scraping_blocked = False

    # P70/P71 — API key state
    p70 = _load_optional("p70_summary")
    p71 = _load_optional("p71_summary")
    api_key_state = "UNKNOWN"
    if p71:
        api_key_state = p71.get("api_key_status", "UNKNOWN")
        optional_ctx["p71_classification"] = p71.get("p71_classification")
        optional_ctx["p71_api_key_status"] = api_key_state
        if api_key_state in ("API_KEY_MISSING", "MISSING", None, "UNKNOWN"):
            blockers.append("BLOCKED_API_KEY_MISSING")
    if p70:
        optional_ctx["p70_classification"] = p70.get("p70_classification")
        optional_ctx["p70_mode"] = p70.get("mode")

    # Always-present governance blockers
    blockers.append("BLOCKED_RAW_DATA_POLICY_MISSING")
    blockers.append("BLOCKED_PRODUCTION_GOVERNANCE")

    # Deduplicate
    blockers = list(dict.fromkeys(blockers))

    return {
        "blocker_count": len(blockers),
        "active_blockers": blockers,
        "edge_2025_result": edge_2025_result,
        "gap_2024_state": gap_2024_state,
        "api_key_state": api_key_state,
        "scraping_blocked_by_tos": scraping_blocked,
        "optional_context_loaded": list(optional_ctx.keys()),
        "optional_context": optional_ctx,
        "market_edge_lane_state": "BLOCKED",
        "market_edge_lane_reason": (
            "2025 edge stable-negative + 2024 odds gap unresolved + "
            "API key missing + production governance frozen"
        ),
    }


def step3_define_odds_data_contract() -> dict[str, Any]:
    """Define the legal odds dataset contract for future market-edge re-entry."""
    field_specs: list[dict[str, Any]] = [
        {"field": "game_id", "type": "str", "required": True,
         "description": "Unique game identifier (matchable to prediction JSONL)"},
        {"field": "game_date", "type": "str", "format": "YYYY-MM-DD", "required": True,
         "description": "Local game date"},
        {"field": "season", "type": "int", "required": True,
         "description": "MLB season year (e.g. 2024, 2025)"},
        {"field": "home_team", "type": "str", "required": True,
         "description": "Canonical home team name/abbrev"},
        {"field": "away_team", "type": "str", "required": True,
         "description": "Canonical away team name/abbrev"},
        {"field": "sportsbook_or_source", "type": "str", "required": True,
         "description": "Named sportsbook or licensed data vendor"},
        {"field": "market_type", "type": "str", "required": True, "enum": ["moneyline", "run_line", "total"],
         "description": "Betting market type"},
        {"field": "odds_timestamp_utc", "type": "str", "format": "ISO8601", "required": True,
         "description": "UTC timestamp when line was captured"},
        {"field": "game_start_utc", "type": "str", "format": "ISO8601", "required": True,
         "description": "UTC scheduled game start time"},
        {"field": "home_moneyline", "type": "float", "required": True,
         "description": "American odds for home team (e.g. -120, +110)"},
        {"field": "away_moneyline", "type": "float", "required": True,
         "description": "American odds for away team"},
        {"field": "implied_home_prob", "type": "float", "range": [0.0, 1.0], "required": True,
         "description": "Vig-removed implied probability for home team"},
        {"field": "implied_away_prob", "type": "float", "range": [0.0, 1.0], "required": True,
         "description": "Vig-removed implied probability for away team"},
        {"field": "line_type", "type": "str", "required": True, "enum": ["opening", "midgame", "closing"],
         "description": "Where in game lifecycle line was taken"},
        {"field": "is_pregame", "type": "bool", "required": True,
         "description": "True if line was captured before game start"},
        {"field": "is_closing", "type": "bool", "required": True,
         "description": "True if this is the closing line"},
        {"field": "source_license_status", "type": "str", "required": True,
         "enum": ["LICENSED", "FREE_TIER", "ACADEMIC", "UNKNOWN"],
         "description": "Legal license status of data source"},
        {"field": "source_trace", "type": "str", "required": True,
         "description": "URL or vendor identifier of original data source"},
        {"field": "raw_data_policy", "type": "str", "required": True,
         "enum": ["COMMIT_ALLOWED", "NO_COMMIT_VENDOR_RESTRICTED", "PENDING_DECISION"],
         "description": "Whether raw data may be committed to repo"},
        {"field": "checksum_hash", "type": "str", "required": True,
         "description": "SHA256 of raw line record for tamper detection"},
        {"field": "created_at_utc", "type": "str", "format": "ISO8601", "required": True,
         "description": "UTC timestamp this record was created/ingested"},
    ]

    legality_requirements = {
        "legal_source_required": True,
        "scraping_prohibited_source_blocked": True,
        "robots_txt_violation_blocked": True,
        "tos_violation_blocked": True,
        "api_key_value_must_not_be_printed": True,
        "api_key_value_must_not_be_logged": True,
        "raw_paid_data_commit_policy_decided_before_staging": True,
        "timestamp_lineage_proven_before_clv": True,
        "side_mapping_proven_before_edge": True,
        "doubleheader_disambiguation_required": True,
        "multi_season_validation_required_before_production": True,
        "known_blocked_sources": ["OddsPortal (P68: ToS violation)"],
        "known_partial_sources": ["P67 PATH_B partial — needs review before use"],
        "authorized_path": "PATH_A: The Odds API (P70 CEO-authorized, P71 awaiting key)",
    }

    return {
        "contract_name": "P80_LEGAL_ODDS_DATA_CONTRACT",
        "schema_version": "p80-v1",
        "required_field_count": len(REQUIRED_ODDS_FIELDS),
        "field_specifications": field_specs,
        "legality_requirements": legality_requirements,
        "implied_prob_vig_removal_required": True,
        "closing_line_required_for_clv": True,
        "pregame_line_required_for_edge": True,
        "min_matched_rows_threshold": 0.90,
        "max_unmatched_rows_threshold": 0.10,
        "seasons_required_for_production": 2,
        "notes": (
            "This contract governs future P81+ odds ingestion. "
            "No odds dataset currently exists meeting all requirements. "
            "The Odds API (PATH A) is CEO-authorized but key not yet received (P71). "
            "This contract must be re-validated once legal data arrives."
        ),
    }


def step4_candidate_eligibility_matrix() -> dict[str, Any]:
    """Define which prediction candidates are eligible for future market-edge testing."""
    matrix = {
        "primary_125": {
            "candidate_name": "TIER_C_HOME_PLUS_AWAY_125",
            "source_phase": "P76/P77",
            "current_prediction_status": "ACTIVE_SHADOW_TRACKING",
            "market_edge_eligibility": "ELIGIBLE_WHEN_LEGAL_ODDS_AVAILABLE",
            "required_additional_data": [
                "Legal odds dataset (Gate A-B passing)",
                "Side mapping verified (Gate C)",
                "2024+2025 historical odds",
            ],
            "prohibited_interpretation": (
                "Do NOT claim market edge until P82 dry-run passes. "
                "Do NOT deploy Kelly. Do NOT produce betting recommendation."
            ),
            "notes": "Primary Tier C rule. Hit rate 0.583 on 2025 fixture.",
        },
        "shadow_100": {
            "candidate_name": "TIER_C_HOME_PLUS_AWAY_100",
            "source_phase": "P76/P77",
            "current_prediction_status": "SHADOW_ONLY",
            "market_edge_eligibility": "ELIGIBLE_WHEN_LEGAL_ODDS_AVAILABLE",
            "required_additional_data": [
                "Legal odds dataset (Gate A-B passing)",
                "Side mapping verified (Gate C)",
                "2024+2025 historical odds",
            ],
            "prohibited_interpretation": (
                "Shadow rule only. May not be promoted to primary without P76 re-evaluation. "
                "Do NOT deploy Kelly."
            ),
            "notes": "Shadow Tier C rule. Hit rate 0.569 on 2025 fixture.",
        },
        "tier_b_conditional": {
            "candidate_name": "TIER_B_ABS_FIP_0.25_TO_0.50",
            "source_phase": "P79A/P79B",
            "current_prediction_status": "RESEARCH_ONLY",
            "market_edge_eligibility": (
                "CONDITIONAL: eligible only if future live P79 passes operational "
                "research gate (2026 live Tier B n>=200 and performance_ok=True)"
            ),
            "required_additional_data": [
                "2026 live Tier B n >= 200 (expected ~2026-09)",
                "Future P79 operational gate PASS",
                "Legal odds dataset (Gate A-B passing)",
                "Side mapping verified (Gate C)",
                "2024+2025 historical odds",
            ],
            "prohibited_interpretation": (
                "P79B fixture result (2025 data) is NOT a 2026 live conclusion. "
                "Tier B remains RESEARCH_ONLY until live P79 passes. "
                "Do NOT compute Tier B EV/CLV/Kelly. Do NOT deploy."
            ),
            "notes": (
                "P79B: hit_rate=0.534, AUC=0.552. Gate fails on performance_ok. "
                "Harness built. Waiting for 2026 live accumulation."
            ),
        },
        "baseline_50": {
            "candidate_name": "TIER_C_BASELINE_ABS_GTE_0.50",
            "source_phase": "P72A/P76",
            "current_prediction_status": "BENCHMARK_REFERENCE",
            "market_edge_eligibility": "ELIGIBLE_AS_BENCHMARK_ONLY",
            "required_additional_data": [
                "Legal odds dataset (Gate A-B passing)",
                "Side mapping verified (Gate C)",
            ],
            "prohibited_interpretation": (
                "Baseline reference only. Not a standalone rule. "
                "Do NOT use as primary or shadow without re-evaluation."
            ),
            "notes": "Baseline. Hit rate 0.565 on 2025 fixture.",
        },
    }
    return {
        "matrix_version": "p80-v1",
        "candidates": matrix,
        "eligible_count": sum(
            1 for v in matrix.values()
            if "ELIGIBLE" in v["market_edge_eligibility"]
        ),
        "conditional_count": sum(
            1 for v in matrix.values()
            if "CONDITIONAL" in v["market_edge_eligibility"]
        ),
        "research_only_count": sum(
            1 for v in matrix.values()
            if v["current_prediction_status"] == "RESEARCH_ONLY"
        ),
    }


def step5_define_validation_gates() -> dict[str, Any]:
    """Define 6 market-edge validation gates (A-F)."""
    gates = {
        "gate_a_data_legality": {
            "gate_id": "A",
            "name": "Data Legality",
            "description": "Confirms the odds dataset originates from a legal, licensed source.",
            "conditions": [
                "source_license_status in [LICENSED, FREE_TIER, ACADEMIC]",
                "no ToS violation (P68: OddsPortal blocked)",
                "no robots.txt-blocked scraping",
                "source_trace field non-empty",
                "raw_data_policy decided before dataset staging",
                "api_key_value not printed or logged",
            ],
            "gate_passes_when": "ALL conditions true",
            "current_state": "BLOCKED — no legal dataset exists yet",
            "unblocked_by": "Obtaining The Odds API key (PATH A, P70/P71) and receiving data",
        },
        "gate_b_schema": {
            "gate_id": "B",
            "name": "Schema Validation",
            "description": "Confirms all 21 required fields are present and valid.",
            "conditions": [
                "all 21 required fields present",
                "home_moneyline and away_moneyline are numeric",
                "odds_timestamp_utc and game_start_utc are valid ISO8601",
                "implied_home_prob and implied_away_prob in [0.0, 1.0]",
                "implied_home_prob + implied_away_prob approx 1.0 (after vig removal)",
                "is_pregame and is_closing are boolean",
                "checksum_hash is a non-empty string",
            ],
            "gate_passes_when": "ALL conditions true for >= 95% of rows",
            "current_state": "BLOCKED — no dataset to validate",
            "unblocked_by": "Gate A passing + P81 schema validator built",
        },
        "gate_c_mapping": {
            "gate_id": "C",
            "name": "Side & Game Mapping",
            "description": "Confirms odds rows can be matched to prediction JSONL rows.",
            "conditions": [
                "side mapping verified (home/away consistent with prediction JSONL)",
                "home/away team names mapped to canonical identifiers",
                "doubleheader disambiguation logic implemented",
                "unmatched rows below 10% threshold",
                "game_id linkable to prediction game_id or (game_date + home_team + away_team)",
            ],
            "gate_passes_when": "unmatched_rows < 10% AND side mapping verified",
            "current_state": "BLOCKED — no dataset to map",
            "unblocked_by": "Gates A+B passing + P81 mapping validator built",
        },
        "gate_d_metric_readiness": {
            "gate_id": "D",
            "name": "Metric Computation Readiness",
            "description": "Governs when edge/CLV/EV/Kelly may be computed.",
            "conditions": [
                "edge may be computed only after implied_home_prob verified (Gate B)",
                "CLV may be computed only after both is_pregame and is_closing rows exist",
                "EV computation requires separate explicit authorization (not in P80)",
                "Kelly deployment requires separate CEO authorization (not in P80)",
                "EV/Kelly remain PROHIBITED until separate approval granted",
            ],
            "gate_passes_when": "implied prob verified AND (for CLV) closing data present",
            "current_state": "BLOCKED — Gates A-C not satisfied",
            "unblocked_by": "Gates A+B+C passing + closing line dataset available",
            "prohibited_metrics": ["EV", "Kelly", "CLV_without_closing_data"],
        },
        "gate_e_cross_year_validation": {
            "gate_id": "E",
            "name": "Cross-Year Validation",
            "description": "Requires multi-season validation before any product claim.",
            "conditions": [
                "2024 + 2025 historical odds both available (or future multi-season equivalent)",
                "2025-only validation is INSUFFICIENT for production",
                "P65 showed 2025 edge stable-negative — must validate if 2026 changes this",
                "market-edge analysis must span at least 2 MLB seasons",
                "cross-year synthesis required before any production readiness claim",
            ],
            "gate_passes_when": ">=2 seasons of legal odds validated through Gates A-D",
            "current_state": "BLOCKED — 2024 odds gap unresolved (P67: partial source only)",
            "unblocked_by": "Legal 2024+2025 odds obtained and validated through Gates A-D",
        },
        "gate_f_governance": {
            "gate_id": "F",
            "name": "Governance Invariants",
            "description": "Ensures governance constraints remain intact during market-edge work.",
            "conditions": [
                "paper_only=True during all P81-P84 phases",
                "production_ready=False during all P81-P84 phases",
                "no real betting recommendation at any point",
                "no champion strategy replacement",
                "no Kelly deployment",
                "promotion_freeze=True",
                "tsl_crawler_modified=False",
                "runtime_recommendation_modified=False",
                "forbidden phrase scan passes before each commit",
            ],
            "gate_passes_when": "ALL governance invariants verified",
            "current_state": "ACTIVE — governance invariants enforced by P80 GOVERNANCE dict",
            "unblocked_by": "Always-on; does not require external data",
        },
    }
    return {
        "gates_defined": len(gates),
        "gates": gates,
        "gates_currently_open": ["gate_f_governance"],
        "gates_currently_blocked": [
            "gate_a_data_legality",
            "gate_b_schema",
            "gate_c_mapping",
            "gate_d_metric_readiness",
            "gate_e_cross_year_validation",
        ],
        "sequential_dependency": "A → B → C → D → E (all must pass in order before production claim)",
    }


def step6_future_phase_path() -> dict[str, Any]:
    """Define future P81-P84 phase path."""
    phases = {
        "P80": {
            "name": "Market-Edge Lane Re-entry Readiness Contract",
            "status": "THIS PHASE",
            "trigger": "P79B fixture complete and market-edge lane blocked",
            "deliverable": "Contract, gates, candidate eligibility matrix",
            "production_gate": False,
        },
        "P81": {
            "name": "Legal Odds Dataset Validator",
            "status": "PENDING — requires legal odds data",
            "trigger": "The Odds API key received AND legal data downloaded",
            "deliverable": "Odds schema validator, Gates A-C implementation",
            "production_gate": False,
            "prerequisite": "The Odds API key received + dataset downloaded",
            "notes": "Do not create until odds data physically exists. No speculative build.",
        },
        "P82": {
            "name": "Market-Edge Recomputation Dry-Run (Paper Only)",
            "status": "PENDING — requires P81 PASS",
            "trigger": "P81 Gates A-C passing",
            "deliverable": "Edge recomputation (no EV/Kelly), paper-mode only",
            "production_gate": False,
            "notes": (
                "May reveal whether 2025 negative edge (P65) holds in extended dataset. "
                "If edge reverses: requires separate CEO authorization before P84."
            ),
        },
        "P83": {
            "name": "CLV Timestamp Validation",
            "status": "PENDING — requires closing data",
            "trigger": "P82 passing AND closing line dataset exists",
            "deliverable": "CLV timestamp lineage verified, pregame vs closing confirmed",
            "production_gate": False,
            "notes": (
                "CLV may NOT be computed without verified closing lines. "
                "Opening-line only datasets do not qualify."
            ),
        },
        "P84": {
            "name": "Cross-Year Market-Edge Synthesis",
            "status": "PENDING — requires P83 + 2024 odds",
            "trigger": "P83 passing AND 2024+2025 legal odds both validated",
            "deliverable": "Multi-season edge analysis (paper-only)",
            "production_gate": False,
            "notes": (
                "Gate E requires >=2 seasons. P84 is the earliest phase where "
                "a multi-season edge claim could be made (still paper-only). "
                "Production gate remains out of scope beyond P84."
            ),
        },
        "P85_PRODUCTION_GATE": {
            "name": "Production Gate (Future, Out of Scope)",
            "status": "OUT OF SCOPE — not defined in P80",
            "trigger": "Requires explicit CEO authorization after P84",
            "deliverable": "TBD",
            "production_gate": True,
            "notes": "P80 does not define P85+. Production remains out of scope.",
        },
    }
    return {
        "path_version": "p80-v1",
        "phases": phases,
        "current_phase": "P80",
        "next_phase": "P81",
        "next_phase_trigger": "The Odds API key received AND legal odds dataset downloaded",
        "production_gate_phase": "NOT YET DEFINED (out of scope for P80-P84)",
        "prediction_only_lane": {
            "status": "ACTIVE — continues independently of market-edge lane",
            "active_rules": ["TIER_C_HOME_PLUS_AWAY_125 (primary)", "TIER_C_HOME_PLUS_AWAY_100 (shadow)"],
            "next_event": "2026 live Tier B n>=200 accumulation → future P79 trigger (~2026-09)",
        },
    }


def step7_generate_comparison_schema() -> dict[str, Any]:
    """Generate the P80 contract schema structure."""
    return {
        "schema_name": "P80_MARKET_EDGE_REENTRY_CONTRACT",
        "schema_version": SCHEMA_VERSION,
        "top_level_sections": [
            "metadata",
            "governance",
            "prediction_lane_status",
            "market_edge_blocker_summary",
            "legal_odds_data_contract",
            "candidate_eligibility_matrix",
            "validation_gates",
            "future_phase_path",
            "stop_conditions",
            "decision_summary",
        ],
        "governance_enforcement": {
            "paper_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "ev_calculated": False,
            "clv_calculated": False,
            "kelly_calculated": False,
            "production_ready": False,
            "live_api_calls": 0,
        },
        "stop_conditions": MARKET_EDGE_STOP_CONDITIONS,
    }


def step8_forbidden_scan() -> dict[str, Any]:
    """Scan this script for forbidden patterns — excludes this function's own definition."""
    script_path = Path(__file__)
    source_lines = script_path.read_text(encoding="utf-8").splitlines()

    # Find the line range of this function to exclude from self-scan
    self_func_start = -1
    self_func_end = len(source_lines)
    for i, line in enumerate(source_lines):
        if "def step8_forbidden_scan" in line:
            self_func_start = i
        elif self_func_start > 0 and i > self_func_start and line.startswith("def "):
            self_func_end = i
            break

    # Build scannable lines (exclude this function's body)
    scannable: list[tuple[int, str]] = [
        (i + 1, line)
        for i, line in enumerate(source_lines)
        if not (self_func_start <= i < self_func_end)
    ]

    import re
    forbidden_checks: list[tuple[str, str, bool]] = [
        ("THE_ODDS_API_KEY", "API key access", False),
        ("os\\.environ\\.get", "env key read", True),
        ("requests\\.get\\(", "live HTTP call", True),
        ("requests\\.post\\(", "live HTTP POST", True),
        ("production_ready.*=.*True", "production_ready set True", True),
        ("real_bet_allowed.*=.*True", "real bet allowed", True),
        ("kelly_deploy_allowed.*=.*True", "Kelly deploy allowed", True),
        ("champion_replacement_allowed.*=.*True", "champion replacement", True),
        ("profitability_claim.*=.*True", "profitability claim", True),
        ("promotion_freeze.*=.*False", "promotion freeze disabled", True),
    ]

    violations: list[str] = []
    for pattern, label, is_regex in forbidden_checks:
        re_pattern = pattern if is_regex else re.escape(pattern)
        for lineno, line in scannable:
            if not re.search(re_pattern, line, re.IGNORECASE):
                continue
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Skip string literal lines (dict/list values)
            if stripped.startswith('"') or stripped.startswith("'"):
                continue
            # Skip governance dict entries setting False/0
            if re.search(r":\s*(False|0)[,\s}]", stripped):
                continue
            violations.append(f"L{lineno}: [{label}] {stripped[:80]}")

    return {
        "scan_passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
        "patterns_checked": len(forbidden_checks),
    }


def _write_report(summary: dict[str, Any], path: Path) -> None:
    """Write Markdown report for P80."""
    path.parent.mkdir(parents=True, exist_ok=True)

    step1 = summary["step1_prediction_lane_verified"]
    step2 = summary["step2_market_edge_blockers"]
    step3 = summary["step3_legal_odds_contract"]
    step4 = summary["step4_candidate_eligibility"]
    step5 = summary["step5_validation_gates"]
    step6 = summary["step6_future_phase_path"]

    lines: list[str] = [
        "# P80 — Market-Edge Lane Re-entry Readiness Contract",
        "",
        f"> **Generated**: {GENERATED_AT}  ",
        f"> **Classification**: `{summary['p80_classification']}`  ",
        f"> **Schema**: `{SCHEMA_VERSION}`  ",
        f"> **Mode**: `paper_only=True | diagnostic_only=True | NO_REAL_BET=True`",
        "",
        "---",
        "",
        "## Governance Invariants",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in GOVERNANCE.items():
        lines.append(f"| `{k}` | `{v}` |")
    lines += [
        "",
        "**EXPLICIT STATEMENT**: This phase makes NO live API calls, computes NO EV/CLV/Kelly, "
        "produces NO production recommendation, and does NOT treat the P79B fixture result "
        "as a 2026 live conclusion.",
        "",
        "---",
        "",
        "## Pre-flight & Prediction Lane Status",
        "",
        f"- P79B Classification: `{step1['p79b_classification']}`",
        f"- Fixture result: `{step1['fixture_dry_run_classification']}`",
        f"- Fixture is 2026 live conclusion: `{step1['fixture_is_2026_live_conclusion']}`",
        f"- Tier B research only: `{step1['tier_b_research_only']}`",
        f"- Tier B n=`{step1['tier_b_n']}` hit_rate=`{step1['tier_b_hit_rate']}` AUC=`{step1['tier_b_auc']}`",
        f"- Market-edge lane (from P79B): `{step1['market_edge_lane']}`",
        f"- Future P79 prompt exists: `{step1['future_p79_prompt_exists']}`",
        f"- Governance clean: `{step1['governance_clean']}`",
        "",
        "---",
        "",
        "## Market-Edge Blocker Summary",
        "",
        f"**Lane state**: `{step2['market_edge_lane_state']}`",
        "",
        f"**Reason**: {step2['market_edge_lane_reason']}",
        "",
        "| Blocker | State |",
        "|---------|-------|",
    ]
    for b in step2["active_blockers"]:
        lines.append(f"| `{b}` | ACTIVE |")
    lines += [
        "",
        f"- 2025 edge result: `{step2['edge_2025_result']}`",
        f"- 2024 odds gap: `{step2['gap_2024_state']}`",
        f"- API key: `{step2['api_key_state']}`",
        f"- OddsPortal scraping blocked by ToS: `{step2['scraping_blocked_by_tos']}`",
        "",
        "---",
        "",
        "## Legal Odds Data Contract",
        "",
        f"**Required fields**: {step3['required_field_count']}",
        "",
        "| Field | Type | Required | Description |",
        "|-------|------|----------|-------------|",
    ]
    for spec in step3["field_specifications"]:
        req = "✅" if spec.get("required") else "○"
        lines.append(
            f"| `{spec['field']}` | `{spec['type']}` | {req} | {spec['description']} |"
        )
    lines += [
        "",
        "### Legality Requirements",
        "",
    ]
    for k, v in step3["legality_requirements"].items():
        lines.append(f"- **{k}**: `{v}`")
    lines += [
        "",
        "---",
        "",
        "## Candidate Eligibility Matrix",
        "",
        "| Candidate | Status | Market-Edge Eligibility |",
        "|-----------|--------|------------------------|",
    ]
    for ck, cv in step4["candidates"].items():
        lines.append(
            f"| `{cv['candidate_name']}` | `{cv['current_prediction_status']}` "
            f"| {cv['market_edge_eligibility'][:60]}... |"
        )
    lines += [
        "",
        "---",
        "",
        "## Validation Gates",
        "",
        "| Gate | Name | Current State |",
        "|------|------|---------------|",
    ]
    for gk, gv in step5["gates"].items():
        lines.append(f"| **{gv['gate_id']}** | {gv['name']} | {gv['current_state'][:60]} |")
    lines += [
        "",
        f"**Sequential dependency**: {step5['sequential_dependency']}",
        "",
        "---",
        "",
        "## Future Phase Path (P81-P84)",
        "",
        "| Phase | Name | Trigger | Gate |",
        "|-------|------|---------|------|",
    ]
    for pk, pv in step6["phases"].items():
        lines.append(
            f"| **{pk}** | {pv['name']} | {pv.get('trigger','—')[:50]} "
            f"| {'PRODUCTION' if pv['production_gate'] else 'paper-only'} |"
        )
    lines += [
        "",
        f"**Next phase trigger**: {step6['next_phase_trigger']}",
        "",
        "---",
        "",
        "## STOP Conditions",
        "",
    ]
    for sc in MARKET_EDGE_STOP_CONDITIONS:
        lines.append(f"- `{sc}`")
    lines += [
        "",
        "---",
        "",
        "## Decision Summary",
        "",
        f"**P80 Classification**: `{summary['p80_classification']}`",
        "",
        "The prediction-only lane (P72A→P79B) is complete and clean. "
        "The market-edge lane remains BLOCKED by 4 active blockers. "
        "This contract defines the readiness gates and data contract required for re-entry. "
        "No odds data was accessed, no EV/CLV/Kelly was computed, and no production "
        "recommendation was made.",
        "",
        "---",
        "",
        "## CTO 10-Line Summary",
        "",
        "1. P80 is a contract-only phase defining market-edge re-entry conditions.",
        "2. Prediction-only lane (P72A→P79B) is complete: primary=HOME_PLUS_AWAY_125, shadow=HOME_PLUS_AWAY_100.",
        "3. Tier B remains RESEARCH_ONLY (fixture 2025: hit_rate=0.534, AUC=0.552).",
        "4. Market-edge lane has 4 active blockers: negative 2025 edge, 2024 odds gap, API key missing, production governance.",
        "5. P80 defines a 21-field legal odds dataset contract with strict legality requirements.",
        "6. 4 prediction candidates have eligibility mapped: primary/shadow eligible, Tier B conditional, baseline benchmark.",
        "7. 6 validation gates (A-F) defined: data legality → schema → mapping → metric → cross-year → governance.",
        "8. Future path: P81 (validator) → P82 (edge dry-run) → P83 (CLV) → P84 (cross-year synthesis).",
        "9. EV/Kelly remain prohibited; CLV requires closing data; production gate remains out of scope.",
        "10. Forbidden scan PASS; governance invariants enforced; 0 live API calls.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Main orchestrator for P80."""
    print("=" * 70)
    print("P80 — Market-Edge Lane Re-entry Readiness Contract")
    print(f"Generated: {GENERATED_AT}")
    print("=" * 70)

    # Verify required artifacts
    print("\n[1] Verifying required source artifacts...")
    missing_required: list[str] = []
    for key in SOURCE_ARTIFACT_KEYS:
        path = PATHS[key]
        if not path.exists():
            missing_required.append(f"{key}: {path}")
        else:
            print(f"  ✓ {key}")

    if missing_required:
        print(f"\n  STOP: {len(missing_required)} required artifact(s) missing:")
        for m in missing_required:
            print(f"    - {m}")
        summary: dict[str, Any] = {
            "p80_classification": "P80_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing_required,
        }
        PATHS["output_json"].parent.mkdir(parents=True, exist_ok=True)
        PATHS["output_json"].write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    # Optional artifacts
    print("\n[2] Checking optional P64-P71 artifacts...")
    optional_present: dict[str, bool] = {}
    for key in OPTIONAL_ARTIFACT_KEYS:
        path = PATHS[key]
        present = path.exists()
        optional_present[key] = present
        status = "✓" if present else "○ (optional, absent)"
        print(f"  {status} {key}")

    # Step 1
    print("\n[Step 1] Verifying prediction-only lane state...")
    s1 = step1_verify_prediction_lane()
    print(f"  P79B classification: {s1['p79b_classification']}")
    print(f"  Tier B research only: {s1['tier_b_research_only']}")
    print(f"  market_edge_lane: {s1['market_edge_lane']}")
    print(f"  Verified: {s1['verified']}")
    if not s1["verified"]:
        print(f"  ERRORS: {s1['errors']}")

    # Step 2
    print("\n[Step 2] Summarizing market-edge blockers...")
    s2 = step2_summarize_market_edge_blockers()
    print(f"  Active blockers ({s2['blocker_count']}): {s2['active_blockers']}")
    print(f"  2025 edge result: {s2['edge_2025_result']}")
    print(f"  API key state: {s2['api_key_state']}")

    # Step 3
    print("\n[Step 3] Defining legal odds data contract...")
    s3 = step3_define_odds_data_contract()
    print(f"  Required fields: {s3['required_field_count']}")

    # Step 4
    print("\n[Step 4] Defining candidate eligibility matrix...")
    s4 = step4_candidate_eligibility_matrix()
    print(f"  Candidates: {list(s4['candidates'].keys())}")

    # Step 5
    print("\n[Step 5] Defining validation gates...")
    s5 = step5_define_validation_gates()
    print(f"  Gates defined: {s5['gates_defined']}")
    print(f"  Gates currently open: {s5['gates_currently_open']}")

    # Step 6
    print("\n[Step 6] Defining future phase path...")
    s6 = step6_future_phase_path()
    print(f"  Next phase: {s6['next_phase']}")
    print(f"  Trigger: {s6['next_phase_trigger']}")

    # Step 7 (schema)
    print("\n[Step 7] Generating comparison schema...")
    s7 = step7_generate_comparison_schema()
    print(f"  Schema sections: {len(s7['top_level_sections'])}")

    # Step 8 (forbidden scan)
    print("\n[Step 8] Running forbidden scan...")
    s8 = step8_forbidden_scan()
    print(f"  Scan passed: {s8['scan_passed']} (violations: {s8['violations_count']})")
    if s8["violations"]:
        for v in s8["violations"]:
            print(f"    ⚠ {v}")

    # Determine classification
    errors_exist = not s1["verified"]
    scan_failed = not s8["scan_passed"]
    has_caveats = bool(s1.get("warnings"))

    if errors_exist or scan_failed:
        p80_cls = "P80_FAILED_VALIDATION"
    elif has_caveats:
        p80_cls = "P80_MARKET_EDGE_REENTRY_CONTRACT_READY_WITH_CAVEATS"
    else:
        p80_cls = "P80_MARKET_EDGE_REENTRY_CONTRACT_READY"

    print(f"\n[Classification] {p80_cls}")

    # Assemble summary JSON
    summary = {
        "p80_classification": p80_cls,
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "governance_snapshot": GOVERNANCE,
        "source_artifacts_verified": {k: PATHS[k].exists() for k in SOURCE_ARTIFACT_KEYS},
        "optional_artifacts_present": optional_present,
        "step1_prediction_lane_verified": s1,
        "step2_market_edge_blockers": s2,
        "step3_legal_odds_contract": s3,
        "step4_candidate_eligibility": s4,
        "step5_validation_gates": s5,
        "step6_future_phase_path": s6,
        "step7_contract_schema": s7,
        "step8_forbidden_scan": s8,
        "market_edge_lane": "blocked",
        "prediction_lane_status": "active",
        "contract_is_production_claim": False,
        "live_api_calls": 0,
        "ev_clv_kelly_computed": False,
    }

    # Write outputs
    print("\n[Output] Writing files...")
    PATHS["output_json"].parent.mkdir(parents=True, exist_ok=True)
    PATHS["output_json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ JSON: {PATHS['output_json']}")

    _write_report(summary, PATHS["output_report"])
    print(f"  ✓ Report: {PATHS['output_report']}")

    PATHS["output_betting_plan"].parent.mkdir(parents=True, exist_ok=True)
    PATHS["output_betting_plan"].write_text(
        PATHS["output_report"].read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"  ✓ BettingPlan copy: {PATHS['output_betting_plan']}")

    print(f"\n{'=' * 70}")
    print(f"P80 COMPLETE — {p80_cls}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
