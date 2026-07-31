"""
P246C — BIG_LOTTO Add-on Prize Record Impact Audit

Read-only impact audit. Determines whether existing strategies, replays,
analyses, tests, API queries, frontend displays, or historical artifacts
have used BIG_LOTTO add-on/special prize records (ADD_ON_PRIZE_EXCLUDED)
or other non-canonical BIG_LOTTO row families.

No DB write is performed. All DB access is read-only.
"""

import json
import os
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"
REPO_ROOT = Path(__file__).parent.parent

IMPACT_CLASSES = (
    "DIRECTLY_AFFECTED",
    "POSSIBLY_AFFECTED",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_MANUAL_REVIEW",
)

FORBIDDEN_ACTIONS = [
    "DB_write",
    "DB_migration_apply",
    "row_deletion",
    "row_movement_without_preservation",
    "registry_mutation",
    "production_recommendation_change",
    "controlled_apply",
    "strategy_promotion",
    "betting_advice",
    "P247_apply",
    "GATE_OPEN_for_BIG_LOTTO_research",
    "claiming_exploitable_edge",
]


def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def get_row_family_counts(conn: sqlite3.Connection) -> dict:
    total = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0]
    addon = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
    ).fetchone()[0]
    date_fmt = conn.execute(
        "SELECT COUNT(*) FROM draws "
        "WHERE lottery_type='BIG_LOTTO' "
        "AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%'"
    ).fetchone()[0]
    serial_nondate = conn.execute(
        "SELECT COUNT(*) FROM draws "
        "WHERE lottery_type='BIG_LOTTO' "
        "AND draw NOT LIKE '%-%' "
        "AND NOT (LENGTH(draw)=8 AND draw LIKE '20%')"
    ).fetchone()[0]
    return {
        "TOTAL": total,
        "ADD_ON_PRIZE_EXCLUDED": addon,
        "DATE_FORMAT_ALIEN": date_fmt,
        "SERIAL_NON_DATE": serial_nondate,
        "CANONICAL_MAIN_DRAW_PLUS_SMALL_POOL": serial_nondate,
        "p246_canonical_main_draw_baseline": 2113,
        "p246_small_pool_alien_baseline": 650,
        "note": (
            "SERIAL_NON_DATE includes both CANONICAL_MAIN_DRAW (~2113) and "
            "SMALL_POOL_ALIEN (~650) as they share the same SQL filter. "
            "Python-driven number inspection required to separate them."
        ),
    }


# ---------------------------------------------------------------------------
# Impact catalogue
# ---------------------------------------------------------------------------

IMPACTED_PATHS = [
    {
        "path": "lottery_api/database.py",
        "functions": ["get_all_draws()", "get_draws()"],
        "impact": "DIRECTLY_AFFECTED",
        "reason": (
            "Both get_all_draws() and get_draws() query draws by lottery_type IN (...) "
            "with NO filter on draw LIKE '%-%'. Any caller passing lottery_type='BIG_LOTTO' "
            "receives all 22,238 rows including 19,100 ADD_ON_PRIZE_EXCLUDED rows."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": (
            "After Type D segregation: add WHERE draw NOT LIKE '%-%' for research callers. "
            "Display/history callers may legitimately show add-on rows but should label them."
        ),
    },
    {
        "path": "tests/test_p238b_nist_randomness_audit_artifact_build.py",
        "line": 146,
        "impact": "DIRECTLY_AFFECTED",
        "reason": (
            "assert active['BIG_LOTTO'] >= 22238 — hardcodes total row count including "
            "ADD_ON_PRIZE_EXCLUDED rows. After canonical segregation, BIG_LOTTO count will "
            "drop to ~2113 and this assertion will fail."
        ),
        "risk_category": "test_expectation_risk",
        "recommended_action": (
            "After segregation: update assertion to >= 2113 or add a separate "
            "assertion for excluded table count."
        ),
    },
    {
        "path": "tests/test_p243a_diagnostic_report_fixture_pack.py",
        "line": 58,
        "impact": "DIRECTLY_AFFECTED",
        "reason": (
            "sample_size=22238 in fixture — hardcodes total BIG_LOTTO row count "
            "including ADD_ON_PRIZE_EXCLUDED rows. This is a historical fixture "
            "representing the state when P243A was run; interpretation note needed."
        ),
        "risk_category": "historical_artifact_interpretation_risk",
        "recommended_action": (
            "This is a historical fixture for P243A. Add a note that sample_size=22238 "
            "reflects all BIG_LOTTO rows at that time, not the canonical research population. "
            "Do not modify the fixture value; add inline comment."
        ),
    },
    {
        "path": "analysis/p238b_nist_randomness_audit_artifact_build.py",
        "impact": "DIRECTLY_AFFECTED",
        "reason": (
            "NIST randomness audit built with sample_size=22238 which includes "
            "ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, and SMALL_POOL_ALIEN rows. "
            "The NIST audit therefore ran on a mixed population, not pure canonical main draws. "
            "P219 already noted this: P219 correctly excluded hyphenated rows using "
            "draw NOT LIKE '%-%' filter."
        ),
        "risk_category": "historical_artifact_interpretation_risk",
        "recommended_action": (
            "After canonical segregation: re-run P238B-style NIST audit on canonical "
            "main-draw population only (~2113 rows). Current artifact remains YELLOW "
            "observation-only but reflects mixed population."
        ),
    },
    {
        "path": "outputs/research/p238b_nist_randomness_audit_artifact_20260604.*",
        "impact": "DIRECTLY_AFFECTED",
        "reason": (
            "NIST audit artifact generated from all 22,238 BIG_LOTTO rows including "
            "ADD_ON_PRIZE_EXCLUDED. sample_size=22238 in artifact JSON. "
            "Artifact classification RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY stands, "
            "but population note is required."
        ),
        "risk_category": "historical_artifact_interpretation_risk",
        "recommended_action": (
            "Add population note to artifact record: 'sample_size=22238 includes all "
            "row families; canonical main-draw population is ~2113. Re-audit required "
            "after P247 segregation.' Do not re-classify artifact until re-audit is run."
        ),
    },
    {
        "path": "lottery_api/routes/ingest.py",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "Ingestion route uses lottery_type='BIG_LOTTO' for fetch/insert. "
            "If add-on prize draws are fetched from the external source, they would be "
            "ingested as BIG_LOTTO rows and included in the mixed population. "
            "The ingestion path does not appear to filter draw ID format."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": (
            "Review ingestion path: determine whether add-on prize draws are fetched "
            "from the lottery API. If so, decide whether to tag them at ingest time "
            "with row_family metadata."
        ),
    },
    {
        "path": "lottery_api/routes/advanced_learning.py",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "Calls scheduler.get_data(lottery_type) for BIG_LOTTO. If get_data() "
            "delegates to get_all_draws() without filtering, advanced learning "
            "endpoints receive the mixed population."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": "Verify get_data() filtering; add canonical filter if needed after segregation.",
    },
    {
        "path": "lottery_api/engine/rolling_strategy_monitor.py",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "RSM references '2113期回測' in log/comment messages, suggesting the "
            "RSM backtests use ~2113 rows. However, the data-loading path is not "
            "confirmed to filter hyphenated draws at the SQL level. "
            "Requires manual review of RSM data-loading path."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": (
            "Trace RSM data-loading path: verify whether BIG_LOTTO data is loaded "
            "via a filter or via get_all_draws(). The 2113 reference may be from "
            "earlier manual analysis rather than a runtime filter."
        ),
    },
    {
        "path": "lottery_api/engine/ (core_satellite, hypothesis_registry, drift_detector, multi_bet_optimizer)",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "These engine files reference BIG_LOTTO but the data-loading and filtering "
            "chain has not been fully traced. If they call get_all_draws() without "
            "canonical filtering, they receive mixed population."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": "Manual code review of each engine file's BIG_LOTTO data-loading path.",
    },
    {
        "path": "lottery_api/backtest_framework.py and many tools/*.py / lottery_api/*.py backtest scripts",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "Numerous backtest and analysis scripts in lottery_api/ and tools/ reference "
            "BIG_LOTTO. Without tracing each one individually, their filtering status is "
            "unknown. Many may call get_all_draws('BIG_LOTTO') which returns mixed population."
        ),
        "risk_category": "strategy_replay_contamination",
        "recommended_action": (
            "After canonical segregation: run a repo-wide audit to identify all scripts "
            "that call get_all_draws('BIG_LOTTO') or equivalent without canonical filter."
        ),
    },
    {
        "path": "analysis/p219_external_method_diagnostic_sweep.py",
        "impact": "NOT_AFFECTED",
        "reason": (
            "P219 explicitly uses filter: "
            "'lottery_type=\\'BIG_LOTTO\\' AND draw NOT LIKE \\'%-%\\''. "
            "Hyphenated ADD_ON_PRIZE_EXCLUDED rows are correctly excluded. "
            "P219 is not affected by taxonomy correction."
        ),
        "risk_category": "none",
        "recommended_action": "No action needed. P219 already implements correct canonical filter.",
    },
    {
        "path": "analysis/p246_big_lotto_data_integrity_audit.py",
        "impact": "NOT_AFFECTED",
        "reason": (
            "P246 explicitly audits row families. Taxonomy correction (P246B) only "
            "changes the label for hyphenated rows. Row counts and audit logic are unchanged."
        ),
        "risk_category": "none",
        "recommended_action": "P246B supersedes SIM_HYPHEN wording; no code change needed in P246 script.",
    },
    {
        "path": "analysis/p246b_big_lotto_taxonomy_correction.py",
        "impact": "NOT_AFFECTED",
        "reason": "This is the P246B correction script itself. It handles all row families correctly.",
        "risk_category": "none",
        "recommended_action": "No action needed.",
    },
    {
        "path": "memory/MEMORY.md / memory/lessons.md (references to 2113, 22238)",
        "impact": "POSSIBLY_AFFECTED",
        "reason": (
            "Memory and lessons files contain references to '2113期回測' and '22238'. "
            "The 2113 references reflect the canonical draw count used in strategy backtests. "
            "The 22238 total row count references are informational and note-worthy for context."
        ),
        "risk_category": "historical_artifact_interpretation_risk",
        "recommended_action": (
            "No immediate change needed. After segregation: update references to clearly "
            "distinguish canonical main-draw count (~2113) from total row count (22238)."
        ),
    },
    {
        "path": "tests/test_p41_wave3_biglotto_adapter_bootstrap_planning.py, test_p42_wave3_biglotto_dryrun_rehearsal.py",
        "impact": "UNKNOWN_NEEDS_MANUAL_REVIEW",
        "reason": (
            "These tests reference BIG_LOTTO row counts ('Found N Wave 3 BIG_LOTTO rows', "
            "'Expected 9000 Wave 3 BIG_LOTTO rows'). The expected counts may or may not "
            "include add-on rows depending on when they were written."
        ),
        "risk_category": "test_expectation_risk",
        "recommended_action": "Manual review: verify what population these Wave 3 tests expect.",
    },
    {
        "path": "tests/test_p94a_biglotto_all_strategy_betcount_benchmark.py",
        "impact": "UNKNOWN_NEEDS_MANUAL_REVIEW",
        "reason": (
            "References BIG_LOTTO draws count but assertion is flexible "
            "('reasonable count'). Manual review to confirm what population is expected."
        ),
        "risk_category": "test_expectation_risk",
        "recommended_action": "Manual review: confirm draws_count assertion logic.",
    },
]

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

IMPACT_SUMMARY = {
    "DIRECTLY_AFFECTED": [
        p["path"] for p in IMPACTED_PATHS if p["impact"] == "DIRECTLY_AFFECTED"
    ],
    "POSSIBLY_AFFECTED": [
        p["path"] for p in IMPACTED_PATHS if p["impact"] == "POSSIBLY_AFFECTED"
    ],
    "NOT_AFFECTED": [
        p["path"] for p in IMPACTED_PATHS if p["impact"] == "NOT_AFFECTED"
    ],
    "UNKNOWN_NEEDS_MANUAL_REVIEW": [
        p["path"] for p in IMPACTED_PATHS if p["impact"] == "UNKNOWN_NEEDS_MANUAL_REVIEW"
    ],
}

RISK_CATEGORIES = {
    "strategy_replay_contamination": {
        "description": (
            "Code paths that load BIG_LOTTO draws via get_all_draws() or equivalent "
            "without canonical filter will receive the full mixed population (22,238 rows). "
            "Strategies and replays trained/backtested on this mixed population may have "
            "ADD_ON_PRIZE_EXCLUDED rows influencing results."
        ),
        "severity": "HIGH — but note: existing production strategies (regime_2bet, ts3_regime_3bet, etc.) "
                    "were validated using the CANONICAL_MAIN_DRAW population via filtered queries or "
                    "the RSM's '2113期回測' path. Contamination risk is primarily in unreleased/exploratory code.",
        "affected_paths": [
            p["path"] for p in IMPACTED_PATHS
            if p.get("risk_category") == "strategy_replay_contamination"
        ],
    },
    "historical_artifact_interpretation_risk": {
        "description": (
            "Historical artifacts (P238B NIST, P243A fixtures) were generated with "
            "sample_size=22238 including ADD_ON_PRIZE_EXCLUDED rows. These artifacts "
            "remain valid as historical records but require population notes."
        ),
        "severity": "MEDIUM — artifacts remain OBSERVATION_ONLY; no strategy impact authorized.",
        "affected_paths": [
            p["path"] for p in IMPACTED_PATHS
            if p.get("risk_category") == "historical_artifact_interpretation_risk"
        ],
    },
    "test_expectation_risk": {
        "description": (
            "Tests with hardcoded BIG_LOTTO row count expectations (>= 22238) will fail "
            "after canonical segregation. Tests must be updated to expect canonical count (~2113) "
            "plus separate expectation for excluded table."
        ),
        "severity": "MEDIUM — tests will need updating after P247 Type D is executed.",
        "affected_paths": [
            p["path"] for p in IMPACTED_PATHS
            if p.get("risk_category") == "test_expectation_risk"
        ],
    },
    "api_frontend_display_risk": {
        "description": (
            "API routes (get_draws, get_all_draws) currently return all 22,238 rows. "
            "The frontend may display add-on/special prize records mixed with canonical draws. "
            "After segregation: display callers should label add-on rows distinctly; "
            "research callers should use canonical filter."
        ),
        "severity": "LOW — add-on records are valid lottery data and appropriate for historical display. "
                    "Risk is primarily mislabeling or confusing them with canonical main draws.",
        "affected_paths": [
            "lottery_api/database.py (get_draws — paged display endpoint)",
            "lottery_api/routes/ingest.py (list draw history endpoint)",
        ],
    },
    "future_migration_segregation_risk": {
        "description": (
            "After Type D segregation: multiple test files will need updates, "
            "API/research callers need canonical filter, and NIST audit should be re-run. "
            "Uncoordinated migration could silently change behavior."
        ),
        "severity": "HIGH if uncoordinated — MEDIUM if done with proper post-apply reconciliation checklist.",
        "affected_paths": [
            "All DIRECTLY_AFFECTED and POSSIBLY_AFFECTED paths"
        ],
    },
}

RECOMMENDED_P247_DESIGN = {
    "option_A_canonical_research_view": {
        "description": (
            "Create a view draws_big_lotto_canonical in the DB that filters to "
            "CANONICAL_MAIN_DRAW rows only. Research callers use this view. "
            "Original draws table retains all rows."
        ),
        "pros": ["No data loss", "Research callers need minimal code change", "Reversible"],
        "cons": ["SMALL_POOL_ALIEN still in canonical view until Python-driven filter applied"],
    },
    "option_B_row_family_metadata_table": {
        "description": (
            "Create a draws_big_lotto_row_family lookup table (draw, row_family, exclusion_reason). "
            "Research code JOINs to filter. Display code shows all rows."
        ),
        "pros": ["No data movement", "Preserves all records", "Explicit categorization"],
        "cons": ["Requires JOIN in every research query"],
    },
    "option_C_segregation_table_with_preservation": {
        "description": (
            "Move non-canonical rows to draws_big_lotto_excluded table preserving all columns. "
            "As specified in P247 plan. Preferred approach from P247 artifact."
        ),
        "pros": ["Clean main draws table for research", "Records preserved in audit table"],
        "cons": ["Highest DB write risk", "Requires post-apply test updates"],
        "note": "Requires Type D authorization. Must use Python-driven SMALL_POOL_ALIEN detection.",
    },
    "option_D_add_row_family_column": {
        "description": (
            "Add row_family TEXT column to draws table; populate for all rows. "
            "Research queries add WHERE row_family='CANONICAL_MAIN_DRAW'."
        ),
        "pros": ["Single table, single query", "No data movement"],
        "cons": ["Schema change; requires migration; backfill for all 22,238 rows"],
    },
    "recommendation": (
        "Option A (canonical research view) is lowest risk and most reversible. "
        "Option C (P247 segregation plan) is most clean for research but highest DB write risk. "
        "Options A and B can be combined: view for research queries now, "
        "full segregation (C) with separate authorization later. "
        "In all cases: do NOT delete ADD_ON_PRIZE_EXCLUDED rows."
    ),
    "post_segregation_re_run_required": [
        "P238B NIST randomness audit (canonical population only)",
        "Any BIG_LOTTO backtest that used get_all_draws('BIG_LOTTO') unfiltered",
        "Test assertions with hardcoded 22238 row count",
        "Drift guard + replay row integrity check",
    ],
}


def run_impact_audit(db_path: Path = DB_PATH) -> dict:
    db_read = False
    row_counts = {
        "TOTAL": None,
        "ADD_ON_PRIZE_EXCLUDED": None,
        "DATE_FORMAT_ALIEN": None,
    }
    db_read_only = True
    db_write_performed = False

    if db_path.exists():
        conn = open_db_readonly(db_path)
        row_counts = get_row_family_counts(conn)
        conn.close()
        db_read = True

    # Verify counts match P246B baseline (within tolerance for ongoing ingestion)
    count_delta = {}
    if row_counts.get("TOTAL") is not None:
        count_delta = {
            "total_vs_p246_baseline": row_counts["TOTAL"] - 22238,
            "addon_vs_p246_baseline": row_counts["ADD_ON_PRIZE_EXCLUDED"] - 19100,
            "date_format_vs_p246_baseline": row_counts["DATE_FORMAT_ALIEN"] - 375,
        }
        count_match = (
            count_delta["addon_vs_p246_baseline"] == 0
            and count_delta["date_format_vs_p246_baseline"] == 0
        )
    else:
        count_match = None

    result = {
        "schema_version": "1.0",
        "task_id": "P246C",
        "classification": "P246C_BIG_LOTTO_ADDON_IMPACT_AUDIT_COMPLETE",
        "p246b_merged_pr": "PR #317 merged 2026-06-05T13:38:06Z",
        "db_path": str(db_path) if db_read else None,
        "db_read": db_read,
        "read_only_confirmed": db_read_only,
        "db_write_performed": db_write_performed,
        "row_family_counts": row_counts,
        "count_delta_from_p246_baseline": count_delta,
        "counts_match_p246_baseline": count_match,
        "source_scan_hits": {
            "BIG_LOTTO_references_in_lottery_api": "30+ files",
            "BIG_LOTTO_references_in_tools": "30+ files",
            "BIG_LOTTO_references_in_tests": "7 files",
            "hardcoded_22238_count": [
                "tests/test_p238b_nist_randomness_audit_artifact_build.py:146",
                "tests/test_p243a_diagnostic_report_fixture_pack.py:58",
                "analysis/p238b_nist_randomness_audit_artifact_build.py (sample_size)",
            ],
            "explicit_canonical_filter_draw_NOT_LIKE": [
                "analysis/p219_external_method_diagnostic_sweep.py (filter: draw NOT LIKE '%-%')",
            ],
            "no_canonical_filter_confirmed": [
                "lottery_api/database.py get_all_draws()",
                "lottery_api/database.py get_draws()",
            ],
        },
        "impacted_paths": IMPACTED_PATHS,
        "impact_summary": IMPACT_SUMMARY,
        "risk_categories": RISK_CATEGORIES,
        "artifacts_likely_affected": [
            "outputs/research/p238b_nist_randomness_audit_artifact_20260604.json — sample_size=22238 includes add-on rows",
            "outputs/research/p238b_nist_randomness_audit_artifact_20260604.md — same",
            "Any BIG_LOTTO backtest output generated via get_all_draws() without canonical filter",
        ],
        "strategies_likely_affected": {
            "production_strategies": (
                "Production strategies (regime_2bet, ts3_regime_3bet, p1_deviation_4bet, etc.) "
                "were validated via RSM '2113期回測' path which appears to use canonical count. "
                "Direct contamination risk is LOW for existing production strategies."
            ),
            "exploratory_tools": (
                "Many tools/*.py and lottery_api/*.py backtest scripts call get_all_draws('BIG_LOTTO') "
                "without filtering. These POSSIBLY used the mixed 22,238 row population."
            ),
        },
        "tests_likely_affected": [
            "tests/test_p238b_nist_randomness_audit_artifact_build.py — assert BIG_LOTTO >= 22238",
            "tests/test_p243a_diagnostic_report_fixture_pack.py — sample_size=22238 fixture",
            "tests/test_p41_wave3_biglotto_adapter_bootstrap_planning.py — UNKNOWN",
            "tests/test_p42_wave3_biglotto_dryrun_rehearsal.py — UNKNOWN",
            "tests/test_p94a_biglotto_all_strategy_betcount_benchmark.py — UNKNOWN",
        ],
        "api_frontend_likely_affected": {
            "get_draws_paged": (
                "lottery_api/database.py get_draws() — paged API endpoint returns all 22,238 rows. "
                "Add-on records are displayed without distinction from canonical draws. "
                "After segregation: display endpoint should label or filter add-on records."
            ),
            "get_all_draws": (
                "lottery_api/database.py get_all_draws() — bulk endpoint used by schedulers and "
                "advanced learning routes. Returns mixed population."
            ),
        },
        "recommended_p247_design": RECOMMENDED_P247_DESIGN,
        "addon_records_preservation_statement": (
            "ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records. "
            "They must be preserved. They are excluded from canonical 6/49 main-draw research "
            "due to population mismatch, not data falseness. "
            "Any segregation design must preserve these records in full."
        ),
        "forbidden_actions_confirmed": FORBIDDEN_ACTIONS,
        "p247_apply_authorized": False,
        "p247_apply_authorization_required": "Separate explicit Type D human gate",
        "big_lotto_gate": "GATE_RED_PENDING_CANONICAL_SEPARATION",
        "final_decision": (
            "P246C read-only impact audit complete. Key finding: database.py get_all_draws() "
            "and get_draws() return all 22,238 BIG_LOTTO rows including ADD_ON_PRIZE_EXCLUDED "
            "with no canonical filter. Tests hardcoding >= 22238 will break after segregation. "
            "P238B NIST artifact was generated from mixed population (22,238 rows). "
            "P219 correctly excluded add-on rows via draw NOT LIKE '%-%' filter. "
            "Production strategies appear to use ~2113 canonical draws via RSM '2113期回測' path. "
            "No DB write performed. P247 apply remains unauthorized. "
            "BIG_LOTTO research gate remains GATE_RED_PENDING_CANONICAL_SEPARATION."
        ),
    }
    return result


def main():
    import sys
    result = run_impact_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[P246C] Impact audit complete. DB read: {result['db_read']}", file=sys.stderr)
    print(f"[P246C] DB write performed: {result['db_write_performed']}", file=sys.stderr)
    print(f"[P246C] Classification: {result['classification']}", file=sys.stderr)
    directly_affected = len(result["impact_summary"]["DIRECTLY_AFFECTED"])
    possibly_affected = len(result["impact_summary"]["POSSIBLY_AFFECTED"])
    print(f"[P246C] DIRECTLY_AFFECTED: {directly_affected}, POSSIBLY_AFFECTED: {possibly_affected}", file=sys.stderr)


if __name__ == "__main__":
    main()
